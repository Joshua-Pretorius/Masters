param(
    [string]$SandboxRoot = "D:\Masters\outputs\sar_server_pipeline_local"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$sourceRoot = "D:\Masters\Data_Creation\meria_sa_plastic_s1_slc"
$sceneId = "MERIA_SA_004_Durban_before_20220420T032018"
$targetId = "MERIA_SA_004"
$targetRole = "before"

$dataRoot = Join-Path $SandboxRoot "data"
$jobRoot = Join-Path $SandboxRoot "job"
$rawRoot = Join-Path $dataRoot "raw"
$processedRoot = Join-Path $dataRoot "processed"
$patchesRoot = Join-Path $dataRoot "patches"
$stacksRoot = Join-Path $dataRoot "stacks"
$logsRoot = Join-Path $dataRoot "logs"
$manifestsRoot = Join-Path $dataRoot "manifests"
$shapefilesRoot = Join-Path $dataRoot "shapefiles"
$rawSlcRoot = Join-Path $rawRoot "slc"
$sceneShapefileRoot = Join-Path $shapefilesRoot $sceneId

$pathsToCreate = @(
    $dataRoot,
    $jobRoot,
    $rawRoot,
    $processedRoot,
    $patchesRoot,
    $stacksRoot,
    $logsRoot,
    $manifestsRoot,
    $shapefilesRoot,
    $rawSlcRoot,
    $sceneShapefileRoot
)

foreach ($path in $pathsToCreate) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

$pointsCsv = Join-Path $sourceRoot "MERIA_SA_plastic_points.csv"
$matchesCsv = Join-Path $sourceRoot "MERIA_SA_plastic_nearest_S1_SLC_before_after.csv"
$filteredPointsCsv = Join-Path $rawRoot "MERIA_SA_004_points.csv"
$filteredMatchesCsv = Join-Path $rawRoot "MERIA_SA_004_matches.csv"

Import-Csv -LiteralPath $pointsCsv |
    Where-Object { $_.obs_id -eq $targetId } |
    Export-Csv -LiteralPath $filteredPointsCsv -NoTypeInformation

Import-Csv -LiteralPath $matchesCsv |
    Where-Object { $_.obs_id -eq $targetId } |
    Export-Csv -LiteralPath $filteredMatchesCsv -NoTypeInformation

$sourceDigitisedRoot = Join-Path $sourceRoot "processed_slc\MERIA_SA_004_Durban\before_20220420T032018\digitised_patches"
$digitisedBaseName = "MERIA_SA_004_Durban_before_20220420T032018_digitised_patches"
$digitisedExtensions = @(".shp", ".shx", ".dbf", ".prj", ".cpg")

foreach ($ext in $digitisedExtensions) {
    $sourcePath = Join-Path $sourceDigitisedRoot ($digitisedBaseName + $ext)
    $destinationPath = Join-Path $sceneShapefileRoot ($digitisedBaseName + $ext)
    Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
}

$manifestPath = Join-Path $jobRoot "meria_sa_004_before.yaml"
$manifestText = @"
schema_version: 1
run_id: meria-sa-004-before-local
dataset_mode: sa
targets:
  - MERIA_SA_004:before
inputs:
  match_csv: /data/raw/MERIA_SA_004_matches.csv
  points_csv: /data/raw/MERIA_SA_004_points.csv
  raw_slc_root: /data/raw/slc
  shapefiles_root: /data/shapefiles
outputs:
  processed_root: /data/processed
  patches_root: /data/patches
  stacks_root: /data/stacks
  logs_root: /data/logs
  manifests_root: /data/manifests
stages:
  slc_process:
    enabled: true
    overwrite: true
    gpt: /opt/snap/bin/gpt
  patch_extract:
    enabled: true
    overwrite: true
  patch_stack:
    enabled: false
    overwrite: false
processing:
  subset_mode: aoi
  subswaths: [IW1, IW2, IW3]
  workers: 1
  cache_gb: 8
  patch_size: 256
  sar_band_order:
    - vv_db
    - vh_db
    - vv_vh_ratio_db
    - vv_minus_vh_db
    - vv_glcm_mean
    - vv_glcm_std
    - vv_glcm_entropy
    - decomp_entropy
    - decomp_anisotropy
    - decomp_alpha
"@

Set-Content -LiteralPath $manifestPath -Value $manifestText -Encoding UTF8

$summaryPath = Join-Path $jobRoot "setup_summary.txt"
$summaryText = @"
Sandbox root: $SandboxRoot
Target: ${targetId}:${targetRole}
Scene ID: $sceneId
Manifest: $manifestPath

This sandbox is ready for slc_process + patch_extract.
patch_stack is intentionally disabled because no MERIA_SA_004 biophysical rasters are available locally.
"@

Set-Content -LiteralPath $summaryPath -Value $summaryText -Encoding UTF8

Write-Output "Prepared local sandbox at $SandboxRoot"
Write-Output "Manifest written to $manifestPath"
