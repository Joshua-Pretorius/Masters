param(
    [string]$VenvDir = "D:\Masters\.venvs\domain_ssl",
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$requirements = Join-Path $repoRoot "requirements-domain-ssl.txt"
$processScript = Join-Path $repoRoot "Scripts\Preprocessing\process_drift_slc.py"
$gptPath = "C:\Program Files\esa-snap\bin\gpt.exe"

function Resolve-Python {
    param([string]$Preferred)

    if ($Preferred) {
        return @{
            Command = $Preferred
            Args = @()
        }
    }

    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{
            Command = "py"
            Args = @("-3.11")
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{
            Command = "python"
            Args = @()
        }
    }

    throw "No Python launcher found. Install Python 3.11 x64 first, then rerun this script."
}

$python = Resolve-Python -Preferred $PythonExe

Write-Host "Repo root: $repoRoot"
Write-Host "Requirements: $requirements"
Write-Host "Venv: $VenvDir"

if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment..."
    & $python.Command @($python.Args + @("-m", "venv", $VenvDir))
}
else {
    Write-Host "Virtual environment already exists."
}

$venvPython = Join-Path $VenvDir "Scripts\python.exe"
$venvActivate = Join-Path $VenvDir "Scripts\Activate.ps1"

if (-not (Test-Path $venvPython)) {
    throw "Expected venv python at $venvPython but it was not created."
}

Write-Host "Upgrading pip tooling..."
& $venvPython -m pip install --upgrade pip setuptools wheel

Write-Host "Installing Domain_SSL requirements..."
& $venvPython -m pip install -r $requirements

$importCheck = @'
import cdsapi
import copernicusmarine
import geopandas
import numpy
import pandas
import rasterio
import requests
import rioxarray
import shapely
import tqdm
import xarray
print("Python imports OK")
'@

Write-Host "Verifying imports..."
& $venvPython -c $importCheck

if (Test-Path $gptPath) {
    Write-Host "SNAP GPT found: $gptPath"
}
else {
    Write-Warning "SNAP GPT not found at $gptPath. Download-only mode will still work, but preprocessing will not."
}

Write-Host ""
Write-Host "Activate later with:"
Write-Host "  & '$venvActivate'"
Write-Host ""
Write-Host "Run download-only with:"
Write-Host "  & '$venvPython' '$processScript' --download-only --keep-zip"
Write-Host ""
Write-Host "If Earthdata credentials are not in C:\Users\Joshua Pretorius\_netrc, set them first:"
Write-Host "  `$env:EDL_USER='your_username'"
Write-Host "  `$env:EDL_PASS='your_password'"
