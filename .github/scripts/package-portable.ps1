$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$temp = $env:RUNNER_TEMP
$sevenZip = Join-Path $env:ProgramFiles '7-Zip/7z.exe'
$seed = Join-Path $temp 'upstream-v15.5.zip'
$extracted = Join-Path $temp 'package'
$stage = Join-Path $extracted 'V15.5_Portable'
$archive = Join-Path $temp 'cartreaderPC-PC115-Portable.zip'

if (!(Select-String -Path "$repo/Cart_Reader/OSCR.cpp" -SimpleMatch '"V15.5-PC114"') -or
    !(Select-String -Path "$repo/pc/cartreader_pc.py" -SimpleMatch 'cartreaderPC PC115')) {
    throw 'Expected PC114 firmware and PC115 PC tool.'
}

curl.exe --fail --location --retry 3 --output $seed 'https://github.com/sanni/cartreader/releases/download/V15.5/V15.5_Portable.zip'
$expected = 'e39b323226cb4dc668e69a3e678926f3a9ad4ec7d2c5e48301bc55b5b293eab4'
if ((Get-FileHash -LiteralPath $seed).Hash -ne $expected) { throw 'Upstream IDE archive SHA256 mismatch.' }
& $sevenZip x $seed "-o$extracted" -y | Out-Host

$ide = (Resolve-Path -LiteralPath (Join-Path $stage 'Arduino IDE')).Path
foreach ($file in @('arduino.exe', 'java/bin/javaw.exe', 'examples/01.Basics/BareMinimum/BareMinimum.ino')) {
    if (!(Test-Path -LiteralPath (Join-Path $ide $file) -PathType Leaf)) {
        throw "Missing upstream IDE startup file: $file"
    }
}
$sketchbook = Join-Path $ide 'portable/sketchbook'

function Remove-IdeDirectory([string]$Path) {
    if (!(Test-Path -LiteralPath $Path)) { return }
    $target = (Resolve-Path -LiteralPath $Path).Path
    if (!$target.StartsWith($ide + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a directory outside the staged IDE: $target"
    }
    Remove-Item -LiteralPath $target -Recurse -Force
}

Remove-IdeDirectory (Join-Path $sketchbook 'Cart_Reader')
Copy-Item -LiteralPath "$repo/Cart_Reader" -Destination $sketchbook -Recurse
$sketch = "$sketchbook/Cart_Reader"
$unexpected = @(Get-ChildItem -LiteralPath $sketch -Recurse -File | Where-Object { $_.Extension -in '.hex', '.elf', '.o', '.a' })
if ($unexpected.Count) { throw 'Found prebuilt firmware files in the staged sketch.' }
if (@(Get-ChildItem -LiteralPath $ide -Filter Cart_Reader.ino -File -Recurse).Count -ne 1) {
    throw 'The staged IDE must contain exactly one Cart_Reader sketch.'
}

# Use the bundled compiler and libraries. Enable HW3 only in a disposable build copy.
$smoke = Join-Path $temp 'smoke'
$build = Join-Path $temp 'avr-build'
New-Item -ItemType Directory -Path $smoke, $build | Out-Null
Copy-Item -LiteralPath $sketch -Destination $smoke -Recurse
$config = Join-Path $smoke 'Cart_Reader/Config.h'
$configText = [IO.File]::ReadAllText($config)
$hw3 = '(?m)^([ \t]*)//[ \t]*(#define[ \t]+HW3\b)'
if ([regex]::Matches($configText, $hw3).Count -ne 1) { throw 'Expected exactly one commented HW3 definition.' }
[IO.File]::WriteAllText($config, ($configText -replace $hw3, '$1$2'))
& "$ide/arduino-builder.exe" -compile -hardware "$ide/hardware" -tools "$ide/tools-builder" -tools "$ide/hardware/tools/avr" -built-in-libraries "$ide/libraries" -libraries "$sketchbook/libraries" -fqbn 'arduino:avr:mega:cpu=atmega2560' -build-path $build "$smoke/Cart_Reader/Cart_Reader.ino"

python -m PyInstaller --noconfirm --onefile --windowed --name cartreaderPC --distpath $stage --workpath "$temp/pyi" --specpath $temp "$repo/pc/cartreader_pc.py"
$exe = Start-Process -FilePath "$stage/cartreaderPC.exe" -ArgumentList '--self-test' -WindowStyle Hidden -Wait -PassThru
if ($exe.ExitCode -ne 0) { throw "PC executable self-test failed: $($exe.ExitCode)" }
foreach ($entry in @('README.md', 'README_PC_USB.md', 'LICENSE', 'transfer_settings.json', 'sd')) {
    Copy-Item -LiteralPath (Join-Path $repo $entry) -Destination $stage -Recurse
}
@"
PC tool: PC115
Firmware source: V15.5-PC114
Source commit: $env:GITHUB_SHA
IDE seed: upstream V15.5_Portable.zip
IDE seed SHA256: $expected
"@ | Set-Content -LiteralPath "$stage/BUILD.txt" -Encoding utf8
@"
Windows Portable distribution with the PC115 tool and V15.5-PC114 firmware source.

- Extract the ZIP to a short path, such as C:\OSCR.
- Open V15.5_Portable and run cartreaderPC.exe for the PC tool. The PC cartridge databases are in sd. The upstream SD Card folder is also included.
- To build or upload the firmware, launch Arduino IDE/arduino.exe and open Cart_Reader from File > Sketchbook. Select your hardware in Config.h and use the Arduino Mega 2560 board setting.
- The bundled IDE and libraries originate from the upstream sanni/cartreader V15.5 Portable distribution. The firmware source in this ZIP comes from this release's commit.

PC115ツール、PC114ファームのソース、本家のPortable IDE一式、データベースを同梱しています。ZIPを短いパスに展開し、V15.5_Portable の cartreaderPC.exe を起動してください。ファームを書き込む場合は Arduino IDE/arduino.exe のスケッチブックから Cart_Reader を開き、Config.h で実機のHWを選択してください。

Source commit: $env:GITHUB_SHA
"@ | Set-Content -LiteralPath "$temp/portable-release-notes.md" -Encoding utf8

Push-Location $extracted
try {
    & $sevenZip a -tzip -mx=5 $archive 'V15.5_Portable' | Out-Host
} finally {
    Pop-Location
}
& $sevenZip t $archive | Out-Host
$hash = (Get-FileHash -LiteralPath $archive).Hash.ToLowerInvariant()
"$hash  $([IO.Path]::GetFileName($archive))" | Set-Content -LiteralPath "$archive.sha256" -Encoding ascii
