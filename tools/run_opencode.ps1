# One opencode invocation PER PAGE.
#
# Handing an agent CLI a 20-page list does not work: it processes the first page, decides the task
# is done and ends its turn. Looping outside the agent makes each call a single, unambiguous job,
# and makes the run resumable — a page whose file already exists is skipped, so a stopped run costs
# nothing to restart.
param(
  [Parameter(Mandatory=$true)][string]$Model,   # e.g. opencode-go/mimo-v2.5
  [Parameter(Mandatory=$true)][string]$Arm,     # e.g. R_mimo25_P2
  [string]$Prompt = "prompts/P2_blocks.txt",
  [int]$TimeoutSec = 600,
  # Restrict or reorder the run. The eight evaluation pages are the only ones that can produce a
  # ranking, so when a model turns out to be slow they are the ones worth spending its budget on:
  # nineteen pages of a twentieth-place arm are worth less than eight pages that let it be scored.
  [string[]]$Only = @()
)

# The repo root, derived from this script's own location — never hardcoded. A benchmark that
# carries an absolute path from the author's machine cannot be run by anyone else, and publishing
# one leaks the layout of a private disk.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$pages = @("003","008","009","012","015","017","023","024","025","028",
           "030","036","039","045","048","050","052","093","095","097")
if ($Only.Count -gt 0) { $pages = $Only }
New-Item -ItemType Directory -Force "runs\$Arm" | Out-Null

$done = 0; $skipped = 0; $failed = @()
foreach ($p in $pages) {
  $out = "runs\$Arm\p$p.json"
  if (Test-Path $out) { $skipped++; continue }
  $msg = "Read the file $Prompt in this directory - that is your instruction. " +
         "Then look at the image pages/p$p.webp with the read tool; the image is the only source " +
         "of truth. Never open any .json file in the pages directory. Apply the instruction to " +
         "what you see and write the resulting JSON object to $out - exactly the object the " +
         "instruction specifies plus a top level key page with the integer $([int]$p). " +
         "No markdown fence, no commentary. Write the file, then stop."
  # A per-page deadline. Without one, a single page that never returns stalls the whole arm: the
  # DeepSeek vision run sat on p015 for half an hour while nineteen pages waited behind it. A page
  # that blows the deadline is recorded as failed and the run moves on, which turns "the arm never
  # finished" into "the arm failed these pages" — a result rather than a gap.
  try {
    # Start-Job launches a FRESH PowerShell that does NOT inherit the caller's working directory.
    # Without the explicit Set-Location the agent runs from the user profile, cannot see
    # prompts/ or pages/, and writes nothing — twenty pages of silent no-ops that look like a slow
    # model. The root has to be passed in, not assumed.
    $job = Start-Job -ScriptBlock {
      param($cwd, $m, $t)
      Set-Location $cwd
      opencode run --model $m $t 2>&1 | Out-Null
    } -ArgumentList $root, $Model, $msg
    if (-not (Wait-Job $job -Timeout $TimeoutSec)) {
      Stop-Job $job
      # Stop-Job ends the JOB, not the native process it launched. Without this the timed-out
      # opencode keeps running, and the orphans accumulate: four of them were found alive at 18-38
      # minutes against a 15-minute deadline, holding API concurrency while the pages behind them
      # crawled. Kill anything older than the deadline — every such process is by definition one
      # this loop already gave up on.
      $deadline = (Get-Date).AddSeconds(-$TimeoutSec)
      Get-Process -Name opencode -ErrorAction SilentlyContinue |
        Where-Object { $_.StartTime -lt $deadline } |
        ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
    }
    Remove-Job $job -Force
  } catch {
    $failed += $p; continue
  }
  if (Test-Path $out) { $done++ } else { $failed += $p }
}
# Sweep before leaving. A run that finishes normally can still leave a child behind — three of them
# were found alive at 196-209 minutes after their runs had reported success, each holding a slot
# against the same subscription rate limit and slowing every later arm. Because they burn almost no
# CPU while hung, nothing surfaces them: they look like idle processes, and the only symptom is that
# some other model appears to be "slow" or to have a capacity ceiling.
$stale = Get-Process -Name opencode -ErrorAction SilentlyContinue |
  Where-Object { $_.StartTime -lt (Get-Date).AddSeconds(-$TimeoutSec) }
foreach ($s in $stale) {
  Write-Output "  sweeping stale opencode PID $($s.Id) (age $([math]::Round(((Get-Date)-$s.StartTime).TotalMinutes,0))m)"
  Stop-Process -Id $s.Id -Force -ErrorAction SilentlyContinue
}

Write-Output "$Arm : wrote $done, already had $skipped, failed $($failed.Count) $($failed -join ',')"
