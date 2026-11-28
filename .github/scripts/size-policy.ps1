# Pareto improvement: neither resource may increase; at least one must decrease.
function Test-SizeImprovement([int]$flashDelta, [int]$ramDelta) {
  return ($flashDelta -le 0 -and $ramDelta -le 0 -and ($flashDelta -lt 0 -or $ramDelta -lt 0))
}
