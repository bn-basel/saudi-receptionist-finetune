# Continue a paused or stopped training run from its latest checkpoint, with the settings it was started with
# (read from runs/<run>/data.json, so the run continues exactly as it began).
# Usage:  .\scripts\resume_training.ps1            (resumes gold_v4)
#         .\scripts\resume_training.ps1 gold_v5
# Close games and other GPU-heavy apps first: training needs ~12 GB of the card's 16.
param([string]$Run = "gold_v4")
$root = Join-Path $PSScriptRoot ".."
$data = Join-Path $root "runs\$Run\data.json"
if (-not (Test-Path $data)) { Write-Host "No runs\$Run\data.json: was this run ever started?"; exit 1 }
$a = (Get-Content $data -Raw | ConvertFrom-Json).args
$last = Get-ChildItem (Join-Path $root "runs\$Run") -Directory -Filter "checkpoint-*" |
        Sort-Object { [int]($_.Name -replace 'checkpoint-', '') } | Select-Object -Last 1
if (-not $last) { Write-Host "No checkpoint in runs\$Run yet: start it again without resuming."; exit 1 }
Remove-Item (Join-Path $root "runs\$Run\PAUSE") -ErrorAction SilentlyContinue
Write-Host "Resuming $Run from $($last.Name) (epochs $($a.epochs), checkpoint every $($a.save_every) steps)."
Write-Host "Progress is in runs\$Run\train.log. To pause again: .\scripts\pause_training.ps1 $Run"
$env:PYTHONIOENCODING = "utf-8"
Set-Location $root
$extra = @()  # settings added later; older runs (Gemma, own split) have neither
if ($a.model) { $extra += @("--model", $a.model) }
if ($a.split_from) { $extra += @("--split-from", $a.split_from) }
if ($a.empty_thought) { $extra += @("--empty-thought") }
uv run python scripts/train.py --run $Run --epochs $a.epochs --save-every $a.save_every --max-len $a.max_len `
    --lr $a.lr --rank $a.rank --accum $a.accum --val-share $a.val_share --seed $a.seed --mem-fraction $a.mem_fraction `
    @extra --resume
