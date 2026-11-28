$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'size-policy.ps1')
$cases = @(
  @{flash=-1; ram=-1; accept=$true},
  @{flash=-1; ram=0; accept=$true},
  @{flash=-1; ram=1; accept=$false},
  @{flash=0; ram=-1; accept=$true},
  @{flash=0; ram=0; accept=$false},
  @{flash=0; ram=1; accept=$false},
  @{flash=1; ram=-1; accept=$false},
  @{flash=1; ram=0; accept=$false},
  @{flash=1; ram=1; accept=$false}
)
foreach ($c in $cases) {
  $actual = Test-SizeImprovement $c.flash $c.ram
  if ($actual -ne $c.accept) { throw "Policy mismatch: Flash=$($c.flash) RAM=$($c.ram) expected=$($c.accept) actual=$actual" }
  Write-Host "PASS Flash=$($c.flash) RAM=$($c.ram) accept=$actual"
}
Write-Host "All 9 size-policy cases passed."
