$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
. (Join-Path $PSScriptRoot 'size-conflict.ps1')
$repo = Join-Path $env:RUNNER_TEMP ('size-conflict-test-' + [guid]::NewGuid())
New-Item -ItemType Directory $repo | Out-Null
try {
  git -C $repo init -b main | Out-Host
  git -C $repo config user.name Test
  git -C $repo config user.email test@example.invalid
  Set-Content (Join-Path $repo 'a.ino') 'original'
  Set-Content (Join-Path $repo 'b.ino') 'original b'
  git -C $repo add .
  git -C $repo commit -m base | Out-Host
  $base = git -C $repo rev-parse HEAD
  git -C $repo switch -c conflicting | Out-Host
  Set-Content (Join-Path $repo 'a.ino') 'candidate'
  git -C $repo commit -am conflicting | Out-Host
  $conflict = git -C $repo rev-parse HEAD
  git -C $repo switch -c independent $base | Out-Host
  Set-Content (Join-Path $repo 'b.ino') 'candidate b'
  git -C $repo commit -am independent | Out-Host
  $independent = git -C $repo rev-parse HEAD
  git -C $repo switch main | Out-Host
  Set-Content (Join-Path $repo 'a.ino') 'accepted'
  git -C $repo commit -am accepted | Out-Host
  $accepted = git -C $repo rev-parse HEAD
  $r = Invoke-SizeCandidatePatch $repo $conflict $accepted
  if ($r.status -ne 'pending_conflict' -or $r.paths.Count -ne 1 -or $r.paths[0] -ne 'a.ino') { throw 'Conflict not retained' }
  if ((git -C $repo rev-parse HEAD) -ne $accepted -or (Get-Content (Join-Path $repo 'a.ino')) -ne 'accepted') { throw 'Accepted state not restored' }
  Write-Host 'PASS conflict deferred, accepted state restored'
  $r = Invoke-SizeCandidatePatch $repo $independent $accepted
  if ($r.status -ne 'applied' -or (Get-Content (Join-Path $repo 'b.ino')) -ne 'candidate b') { throw 'Independent patch after conflict failed' }
  Write-Host 'PASS subsequent candidate applied'
  git -C $repo reset --hard $accepted | Out-Host
  $failed = $false
  try { Invoke-SizeCandidatePatch $repo ('f' * 40) $accepted | Out-Null } catch { $failed = $true }
  if (!$failed) { throw 'Unexpected Git failure was swallowed' }
  Write-Host 'PASS non-conflict Git failure remains fatal'
} finally {
  Remove-Item -Recurse -Force $repo
}
