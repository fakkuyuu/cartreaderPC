# Apply one reviewed candidate without silently resolving overlapping changes.
# On real merge conflicts, record the paths and restore the last accepted commit.
# Other Git failures are fatal rather than mistaken for size rejection.
function Invoke-SizeCandidatePatch([string]$worktree, [string]$candidate, [string]$accepted) {
  try {
    git -C $worktree cherry-pick --no-commit $candidate | Out-Host
    return @{status='applied'; paths=@()}
  } catch {
    $failure = $_
    $paths = @(git -C $worktree diff --name-only --diff-filter=U)
    git -C $worktree reset --hard $accepted | Out-Host
    if ((git -C $worktree rev-parse HEAD) -ne $accepted -or @(git -C $worktree status --porcelain).Count -ne 0) {
      throw 'Failed to restore clean accepted state after cherry-pick'
    }
    if ($paths.Count -eq 0) { throw $failure }
    return @{status='pending_conflict'; paths=$paths}
  }
}
