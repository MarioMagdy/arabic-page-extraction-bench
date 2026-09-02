# One codex invocation PER PAGE — the codex sibling of run_opencode.ps1, same contract:
# resumable (a page whose file exists is skipped), one unambiguous job per call.
# The prompt goes in on STDIN; a positional prompt hangs waiting for stdin.
param(
  [Parameter(Mandatory=$true)][string]$Model,   # e.g. gpt-5.6-terra
  [Parameter(Mandatory=$true)][string]$Arm,     # e.g. W_terra_P2
  [string]$Prompt = "prompts/P2_blocks.txt",
  [string]$Effort = "medium"
)

# The repo root, derived from this script's own location — never hardcoded. A benchmark that
# carries an absolute path from the author's machine cannot be run by anyone else, and publishing
# one leaks the layout of a private disk.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$pages = @("003","008","009","012","015","017","023","024","025","028",
           "030","036","039","045","048","050","052","093","095","097")
New-Item -ItemType Directory -Force "runs\$Arm" | Out-Null

$done = 0; $skipped = 0; $failed = @()
foreach ($p in $pages) {
  $out = "runs\$Arm\p$p.json"
  if (Test-Path $out) { $skipped++; continue }
  $msg = "Read the file $Prompt in this directory - that is your instruction. " +
         "Then look at the image pages/p$p.webp; the image is the only source of truth. " +
         "Never open any .json file in the pages directory. Apply the instruction to what you " +
         "see and write the resulting JSON object to $out - exactly the object the instruction " +
         "specifies plus a top level key page with the integer $([int]$p). " +
         "No markdown fence, no commentary. Write the file, then stop."
  try {
    $msg | codex exec --model $Model -c model_reasoning_effort="$Effort" `
        --sandbox danger-full-access --skip-git-repo-check 2>&1 | Out-Null
  } catch {
    $failed += $p; continue
  }
  if (Test-Path $out) { $done++ } else { $failed += $p }
}
Write-Output "$Arm : wrote $done, already had $skipped, failed $($failed.Count) $($failed -join ',')"
