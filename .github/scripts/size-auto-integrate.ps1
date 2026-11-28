# Build reviewed candidates sequentially against the last accepted firmware.
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$repo = $env:GITHUB_WORKSPACE
. (Join-Path $PSScriptRoot 'size-policy.ps1')
. (Join-Path $PSScriptRoot 'size-conflict.ps1')
if ($env:GITHUB_REF -ne 'refs/heads/experiment/size-reduction-phase2') { throw 'Wrong target branch' }
$request = Get-Content (Join-Path $repo '.github/size-parallel-request.json') -Raw | ConvertFrom-Json -AsHashtable
if ($request.auto_integrate -ne $true -or $request.endpoints_only -eq $true) { throw 'Not an independent auto request' }
$base = [string]$request.base
$dry = $request.dry_run -eq $true
$start = if ($dry) { $base } else { $env:GITHUB_SHA }
git -C $repo merge-base --is-ancestor $base $env:GITHUB_SHA
if (!$dry) {
  $baseTree = git -C $repo rev-parse "$($base):Cart_Reader"
  $startTree = git -C $repo rev-parse "$($start):Cart_Reader"
  if ($baseTree -ne $startTree) { throw 'Firmware changed since candidate base' }
}
$temp = Join-Path $env:RUNNER_TEMP 'phase2-auto-build'
$out = Join-Path $env:RUNNER_TEMP 'phase2-auto-output'
$wt = Join-Path $env:RUNNER_TEMP 'phase2-auto-worktree'
New-Item -ItemType Directory -Force -Path $temp,$out | Out-Null
$report = [ordered]@{schema=3; acceptance_policy='flash_and_ram_nonincreasing_at_least_one_decreases'; id=$request.id; run_id=$env:GITHUB_RUN_ID; run_attempt=$env:GITHUB_RUN_ATTEMPT; base=$base; start=$start; dry_run=$dry; status='running'; candidates=@(); hardware_validation='pending'}
function Save-Report {
  $report | ConvertTo-Json -Depth 20 | Set-Content -Encoding utf8 (Join-Path $out 'integration.json')
}
Save-Report
$archive = Join-Path $temp 'upstream.zip'
curl.exe --fail --location --retry 3 --output $archive 'https://github.com/sanni/cartreader/releases/download/V15.5/V15.5_Portable.zip'
if ((Get-FileHash -LiteralPath $archive).Hash -ne 'e39b323226cb4dc668e69a3e678926f3a9ad4ec7d2c5e48301bc55b5b293eab4') { throw 'Upstream archive hash mismatch' }
& "$env:ProgramFiles/7-Zip/7z.exe" x $archive "-o$temp" -y | Out-Host
$ide = Join-Path $temp 'V15.5_Portable/Arduino IDE'
$sketchbook = Join-Path $ide 'portable/sketchbook'
$gcc = @(Get-ChildItem -LiteralPath "$ide/hardware" -Filter avr-gcc.exe -Recurse -File)
if ($gcc.Count -ne 1) { throw "Expected one bundled avr-gcc, got $($gcc.Count)" }
$version = & $gcc[0].FullName --version
$version | Out-Host
if (($version -join ' ') -notmatch '15\.2') { throw 'Expected AVR GCC 15.2' }
$sizeTool = Join-Path $gcc[0].DirectoryName 'avr-size.exe'

function Measure-Firmware([string]$ref, [string]$short, [bool]$analyze = $false) {
  $src = Join-Path $temp "src-$short"
  $build = Join-Path $temp "build-$short"
  $zip = Join-Path $temp "$short.zip"
  New-Item -ItemType Directory -Path $src,$build | Out-Null
  git -C $repo archive --format=zip "--output=$zip" $ref Cart_Reader
  Expand-Archive -LiteralPath $zip -DestinationPath $src
  $config = Join-Path $src 'Cart_Reader/Config.h'
  $cfg = [IO.File]::ReadAllText($config)
  $pattern = '(?m)^([ \t]*)//[ \t]*(#define[ \t]+HW3\b)'
  if ([regex]::Matches($cfg,$pattern).Count -ne 1) { throw 'Expected one commented HW3 definition' }
  $cfg = $cfg -replace $pattern, '$1$2'
  # Explicitly enable the additional HW3 cartridge cores used in the local test profile.
  foreach ($core in @('ENABLE_NGP','ENABLE_MSX','ENABLE_PCE','ENABLE_POKE','ENABLE_SFM','ENABLE_SV','ENABLE_ST','ENABLE_VBOY','ENABLE_WS')) {
    $corePattern = '(?m)^([ \t]*)//[ \t]*(#define[ \t]+' + $core + '\b)'
    if ([regex]::Matches($cfg,$corePattern).Count -ne 1) { throw "Unexpected core configuration: $core" }
    $cfg = $cfg -replace $corePattern, '$1$2'
  }
  $active = [regex]::Replace($cfg, '(?s)/\*.*?\*/', '')
  $active = [regex]::Replace($active, '(?m)//.*$', '')
  if ($active -match '(?m)^\s*#define\s+HW[1245]\b') { throw 'Unexpected board define' }
  if ($active -match '(?m)^\s*#define\s+ENABLE_FLASH(?:8|16)?\b') { throw 'FLASH configuration not OFF' }
  [IO.File]::WriteAllText($config, $cfg)
  Write-Host "=== Config: $short (comments excluded; conditional defines still listed) ==="
  $active -split "`n" | Select-String '^\s*#define\s+(HW\d|ENABLE_|OPTION_|PC_)' | Out-Host
  $log = Join-Path $out "$short-build.log"
  $buildArgs = @('-compile','-verbose','-hardware',"$ide/hardware",'-tools',"$ide/tools-builder",'-tools',"$ide/hardware/tools/avr",'-built-in-libraries',"$ide/libraries",'-libraries',"$sketchbook/libraries",'-fqbn','arduino:avr:mega:cpu=atmega2560','-prefs','compiler.c.elf.extra_flags=-Wl,--relax -flto-partition=none','-build-path',$build,"$src/Cart_Reader/Cart_Reader.ino")
  & "$ide/arduino-builder.exe" @buildArgs 2>&1 | Tee-Object -FilePath $log | Out-Host
  $logText = Get-Content -LiteralPath $log -Raw
  foreach ($flag in @('-Os','-mcall-prologues','--relax','-flto-partition=none')) {
    if (!$logText.Contains($flag)) { throw "Missing expected compiler/linker flag $flag" }
  }
  $elf = Join-Path $build 'Cart_Reader.ino.elf'
  $sections = & $sizeTool -A $elf
  $sections | Out-Host
  $sizes = @{}
  foreach ($line in $sections) {
    if ($line -match '^\s*(\.[\w.]+)\s+(\d+)\s+') { $sizes[$Matches[1]] = [int]$Matches[2] }
  }
  if (!$sizes.ContainsKey('.text') -or !$sizes.ContainsKey('.data') -or !$sizes.ContainsKey('.bss')) { throw 'Missing ELF size sections' }
  $flash = $sizes['.text'] + $sizes['.data']
  $ram = $sizes['.data'] + $sizes['.bss'] + $sizes['.noinit']

  if ($analyze) {
    $analysisArgs = @((Join-Path $repo '.github/scripts/size-elf-analysis.py'), '--elf', $elf, '--bin-dir', $gcc[0].DirectoryName, '--out', $out, '--short', $short)
    if ($short -ne 'auto-base') { $analysisArgs += @('--baseline', (Join-Path $out 'auto-base-symbols.json')) }
    & python @analysisArgs | Out-Host
  }
  return @{flash=[int]$flash; ram=[int]$ram}
}
function Check-Candidate([string]$head) {
  $parents = (git -C $repo rev-list --parents -n 1 $head).Split(' ')
  if ($parents.Count -ne 2 -or $parents[1] -ne $base) { throw 'Candidate is not a single non-merge commit from base' }
  $changes = @(git -C $repo diff --raw --no-renames $base $head)
  if (!$changes.Count) { throw 'Empty candidate' }
  foreach ($change in $changes) {
    if ($change -notmatch '^:100644 100644 [0-9a-f]+ [0-9a-f]+ M\tCart_Reader/[A-Za-z0-9_./-]+\.(ino|h|hpp|cpp|c|S)$' -or $change -match '(?i)/Config\.h$') {
      throw "Forbidden candidate change: $change"
    }
  }
}
try {
  $initial = Measure-Firmware $start 'auto-base' $true
  if ($initial.flash -ne $request.expected_base_flash -or $initial.ram -ne $request.expected_base_ram) { throw 'Auto baseline calibration mismatch' }
  $report.baseline = $initial
  $current = $initial
  $accepted = $start
  git -C $repo worktree add -b phase2-auto-local $wt $start | Out-Host
  git -C $wt config user.name 'github-actions[bot]'
  git -C $wt config user.email '41898282+github-actions[bot]@users.noreply.github.com'
  $eligible = @()
  $index = 0
  foreach ($candidate in $request.candidates) {
    $index++
    $item = [ordered]@{id=$candidate.id; head=$candidate.head; order=$index; resubmission=$candidate.resubmission; independent_flash=$null; independent_ram=$null; independent_delta=$null; independent_ram_delta=$null; decision='rejected'; reason=''; before_flash=$null; before_ram=$null; trial_flash=$null; trial_ram=$null; incremental_delta=$null; incremental_ram_delta=$null; accepted_commit=$null; conflict_paths=@(); conflict_onto=$null}
    $report.candidates += $item
    try {
      if ($candidate.reviewed -ne $true) { throw 'Candidate not reviewed' }
      Check-Candidate $candidate.head
      $p = Join-Path $repo ("candidate-reports/size-candidate-" + $candidate.id + "/results.json")
      $r = Get-Content -LiteralPath $p -Raw | ConvertFrom-Json -AsHashtable
      if ($r.run_id -ne $env:GITHUB_RUN_ID -or $r.run_attempt -ne $env:GITHUB_RUN_ATTEMPT -or $r.workflow_commit -ne $env:GITHUB_SHA -or $r.request.id -ne $candidate.id -or $r.request.base -ne $base -or $r.request.head -ne $candidate.head -or $r.results.Count -ne 2 -or $r.results[0].commit -ne $base -or $r.results[1].commit -ne $candidate.head) { throw 'Invalid or stale independent result' }
      if ($r.status -ne 'ok' -or $r.baseline_matches_local -ne $true -or $r.results[0].status -ne 'ok' -or $r.results[1].status -ne 'ok' -or $r.results[0].flash -ne $initial.flash -or $r.results[0].ram -ne $initial.ram) { throw 'Independent build or calibration failed' }
      if ($null -eq $r.results[1].flash -or $null -eq $r.results[1].ram) { throw 'Missing independent size' }
      $item.independent_flash = [int]$r.results[1].flash
      $item.independent_ram = [int]$r.results[1].ram
      if ($item.independent_flash -le 0 -or $item.independent_ram -lt 0) { throw 'Invalid independent size' }
      $item.independent_delta = $item.independent_flash - $initial.flash
      $item.independent_ram_delta = $item.independent_ram - $initial.ram
      if (!(Test-SizeImprovement $item.independent_delta $item.independent_ram_delta)) { throw 'Independent Flash/RAM policy rejected' }
      $item.decision = 'eligible'
      $eligible += $item
    } catch { $item.reason = $_.Exception.Message }
    Save-Report
  }
  foreach ($item in ($eligible | Sort-Object { $_.independent_delta }, { $_.independent_ram_delta }, { $_.order })) {
    $item.before_flash = $current.flash
    $item.before_ram = $current.ram
    $patch = Invoke-SizeCandidatePatch $wt $item.head $accepted
    if ($patch.status -eq 'pending_conflict') {
      $item.decision = 'pending_conflict'
      $item.reason = 'Manual semantic merge and remeasurement required'
      $item.conflict_paths = @($patch.paths)
      $item.conflict_onto = $accepted
      Save-Report
      continue
    }
    try {
      if (!(git -C $wt diff --cached --name-only)) { throw 'Empty cumulative patch' }
      git -C $wt commit -m ("Auto size trial: " + $item.id + " (" + $item.head + ")") | Out-Host
      $trial = git -C $wt rev-parse HEAD
      $measured = Measure-Firmware $trial ("auto-trial-" + $item.order)
      $item.trial_flash = $measured.flash
      $item.trial_ram = $measured.ram
      $item.incremental_delta = $measured.flash - $current.flash
      $item.incremental_ram_delta = $measured.ram - $current.ram
      if (!(Test-SizeImprovement $item.incremental_delta $item.incremental_ram_delta)) { throw 'Cumulative Flash/RAM policy rejected' }
      $accepted = $trial
      $current = $measured
      $item.decision = 'adopted'
      $item.accepted_commit = $accepted
      $item.reason = 'Neither resource increased and at least one decreased'
    } catch {
      $item.decision = 'rejected'
      $item.reason = $_.Exception.Message
      git -C $wt reset --hard $accepted | Out-Host
    }
    Save-Report
  }
  if ((git -C $wt rev-parse HEAD) -ne $accepted) { throw 'Unexpected cumulative head' }
  $final = Measure-Firmware $accepted 'auto-final' $true
  if ($final.flash -ne $current.flash -or $final.ram -ne $current.ram) { throw 'Final rebuild does not match accepted measurement' }
  if ((git -C $repo rev-parse "$($base):Cart_Reader/Config.h") -ne (git -C $repo rev-parse "$($accepted):Cart_Reader/Config.h")) { throw 'Config.h changed' }
  $report.final = $final
  $report.delta = $final.flash - $initial.flash
  $report.ram_delta = $final.ram - $initial.ram
  if ($final.flash -gt $initial.flash -or $final.ram -gt $initial.ram) { throw 'Final size exceeds baseline' }
  $report.firmware_commit = $accepted
  $report.pending_count = @($report.candidates | Where-Object decision -eq 'pending_conflict').Count
  $report.pending = @($report.candidates | Where-Object decision -eq 'pending_conflict' | ForEach-Object {
    @{id=$_.id; original_base=$base; original_head=$_.head; conflict_onto=$_.conflict_onto; paths=$_.conflict_paths; independent_flash_delta=$_.independent_delta; independent_ram_delta=$_.independent_ram_delta; rebase_onto_firmware=$accepted; expected_base_flash=$final.flash; expected_base_ram=$final.ram; resubmission=$_.resubmission}
  })
  # Maintain one canonical queue. Resubmissions must point back to exactly one prior hold.
  $queuePath = Join-Path $wt 'size-auto-results/pending-work.json'
  if (Test-Path -LiteralPath $queuePath) {
    $queue = Get-Content -LiteralPath $queuePath -Raw | ConvertFrom-Json -AsHashtable
  } else {
    $queue = [ordered]@{schema=1; description='Canonical queue of unresolved automatic size-reduction work.'; updated_by_run_id=$null; items=@()}
  }
  if ($null -eq $queue.items) { $queue.items = @() }
  foreach ($item in $report.candidates) {
    if ($null -ne $item.resubmission) {
      $link = $item.resubmission
      if ([string]::IsNullOrWhiteSpace([string]$link.original_run_id) -or [string]::IsNullOrWhiteSpace([string]$link.original_candidate_sha) -or [string]$link.target_base_sha -ne $base -or [string]$link.candidate_sha -ne [string]$item.head) {
        throw ('Invalid resubmission lineage for ' + $item.id)
      }
      $matches = @($queue.items | Where-Object {
        [string]$_.original.run_id -eq [string]$link.original_run_id -and
        [string]$_.original.candidate_sha -eq [string]$link.original_candidate_sha
      })
      if ($matches.Count -ne 1) { throw ('Resubmission for ' + $item.id + ' must match exactly one pending-work entry; found ' + $matches.Count) }
      $held = $matches[0]
      $held.latest_resubmission = @{request_id=$request.id; run_id=$env:GITHUB_RUN_ID; candidate_sha=$item.head; target_base_sha=$base; measurement_record=('size-measurements/' + $request.id + '-' + $env:GITHUB_RUN_ID + '-' + $env:GITHUB_RUN_ATTEMPT + '.json'); integration_record=('size-auto-results/' + $request.id + '-' + $env:GITHUB_RUN_ID + '-' + $env:GITHUB_RUN_ATTEMPT + '.json'); decision=$item.decision; accepted_commit=$item.accepted_commit}
      if ($item.decision -eq 'pending_conflict') {
        $held.status = 'pending'
        $held.latest_conflict = @{candidate_sha=$item.head; files=$item.conflict_paths; conflict_onto_sha=$item.conflict_onto; rebase_onto_firmware=$accepted}
      } else {
        $held.status = 'resolved'
        $held.result = @{decision=$item.decision; reason=$item.reason; independent_flash_delta=$item.independent_delta; independent_ram_delta=$item.independent_ram_delta; incremental_flash_delta=$item.incremental_delta; incremental_ram_delta=$item.incremental_ram_delta; accepted_commit=$item.accepted_commit; final_firmware_commit=$accepted; final_flash=$final.flash; final_ram=$final.ram; hardware_validation='pending'}
      }
      $held.updated_by_run_id = $env:GITHUB_RUN_ID
    } elseif ($item.decision -eq 'pending_conflict') {
      $key = $env:GITHUB_RUN_ID + '/' + $item.id
      $existing = @($queue.items | Where-Object { $_.key -eq $key })
      if ($existing.Count -eq 0) {
        $queue.items += @{key=$key; status='pending'; candidate_id=$item.id; original=@{run_id=$env:GITHUB_RUN_ID; candidate_id=$item.id; base_sha=$base; candidate_sha=$item.head; integration_record=('size-auto-results/' + $request.id + '-' + $env:GITHUB_RUN_ID + '-' + $env:GITHUB_RUN_ATTEMPT + '.json'); pending_record=('size-auto-results/' + $request.id + '-' + $env:GITHUB_RUN_ID + '-' + $env:GITHUB_RUN_ATTEMPT + '-pending.json'); conflict_files=$item.conflict_paths; conflict_onto_sha=$item.conflict_onto; rebase_onto_firmware=$accepted}; created_by_run_id=$env:GITHUB_RUN_ID}
      }
    }
  }
  $queue.updated_by_run_id = $env:GITHUB_RUN_ID
  $queue | ConvertTo-Json -Depth 20 | Set-Content -Encoding utf8 $queuePath
  $report.status = 'measured'
  Save-Report
  $md = @(("# " + $request.id + " automatic integration"), "", "Run: $($env:GITHUB_RUN_ID)/$($env:GITHUB_RUN_ATTEMPT). Dry run: $dry. Hardware validation pending.", "", "Baseline: $($initial.flash) B / RAM $($initial.ram) B. Final: $($final.flash) B / RAM $($final.ram) B. Flash delta: $($report.delta) B. RAM delta: $($report.ram_delta) B.", "", '| Candidate | Independent Flash delta | Independent RAM delta | Cumulative Flash delta | Cumulative RAM delta | Decision | Reason |', '| --- | ---: | ---: | ---: | ---: | --- | --- |')
  foreach ($item in $report.candidates) {
    $reason = $item.reason -replace '[\r\n|]', ' '
    $md += "| $($item.id) | $($item.independent_delta) | $($item.independent_ram_delta) | $($item.incremental_delta) | $($item.incremental_ram_delta) | $($item.decision) | $reason |"
  }
  $md += @('', "Pending conflicts: $($report.pending_count). Not rejected; resolve against the final accepted firmware and submit as new reviewed independent candidates.")
  foreach ($pending in $report.pending) {
    $md += "- $($pending.id): original head $($pending.original_head); paths $($pending.paths -join ', '); rebase onto $($pending.rebase_onto_firmware)"
  }
  ConvertTo-Json -InputObject @($report.pending) -Depth 12 | Set-Content -Encoding utf8 (Join-Path $out 'pending-conflicts.json')
  $md | Set-Content -Encoding utf8 (Join-Path $out 'integration.md')
  $md | Add-Content $env:GITHUB_STEP_SUMMARY
  $dest = Join-Path $wt 'size-auto-results'
  New-Item -ItemType Directory -Force $dest | Out-Null
  $name = "$($request.id)-$($env:GITHUB_RUN_ID)-$($env:GITHUB_RUN_ATTEMPT)"
  Copy-Item (Join-Path $out 'integration.json') (Join-Path $dest "$name.json")
  Copy-Item (Join-Path $out 'integration.md') (Join-Path $dest "$name.md")
  Copy-Item (Join-Path $out 'pending-conflicts.json') (Join-Path $dest "$name-pending.json")
  git -C $wt add -- size-auto-results
  git -C $wt commit -m "Finalize automatic size integration $name (Flash $($report.delta) B, RAM $($report.ram_delta) B)" | Out-Host
  $commit = git -C $wt rev-parse HEAD
  git -C $wt bundle create (Join-Path $out 'integration.bundle') refs/heads/phase2-auto-local "^$start" | Out-Host
  @{commit=$commit; start=$start; dry_run=$dry; workflow_commit=$env:GITHUB_SHA} | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $out 'manifest.json')
} catch {
  $report.status = 'error'
  $report.error = $_.Exception.Message
  Save-Report
  throw
}
