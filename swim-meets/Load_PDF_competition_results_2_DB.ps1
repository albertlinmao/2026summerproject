#!/usr/bin/env pwsh
#
# Load PDF competition results into the database (Supabase).
#
# Currently loads all figure result PDFs from:
#   swim-meets/2025/20251207_Monte Johnson Figure Meet_Tukwila_WA
#
# Usage:
#   ./swim-meets/Load_PDF_competition_results_2_DB.ps1
#
# Add a --dry-run flag to preview without inserting:
#   ./swim-meets/Load_PDF_competition_results_2_DB.ps1 -DryRun

param(
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$MeetDir = Join-Path $PSScriptRoot "2025\20251207_Monte Johnson Figure Meet_Tukwila_WA"

if (-not (Test-Path -LiteralPath $MeetDir)) {
    Write-Host "ERROR: Meet directory not found: $MeetDir"
    exit 1
}

$scriptArgs = @()
if ($DryRun) { $scriptArgs += "--dry-run" }

$figurePdfs = Get-ChildItem -LiteralPath $MeetDir -Filter *_figure.pdf | Sort-Object Name
if (-not $figurePdfs) {
    Write-Host "ERROR: No *_figure.pdf files found in $MeetDir"
    exit 1
}

Write-Host "Loading $($figurePdfs.Count) figure result PDFs from $MeetDir ..."
& python (Join-Path $ProjectRoot "scripts\ingest_figures.py") @($figurePdfs.FullName) $scriptArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Done."