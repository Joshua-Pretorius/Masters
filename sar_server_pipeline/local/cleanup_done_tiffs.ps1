<#
Preview or remove local TIFF rasters from completed digitising batches.

The batch hierarchy, GeoPackages, manifests, projects, and other files stay in
place. This script never contacts Skua or Google Drive.

Usage:
  powershell -NoProfile -File .\cleanup_done_tiffs.ps1
  powershell -NoProfile -File .\cleanup_done_tiffs.ps1 -List
  powershell -NoProfile -File .\cleanup_done_tiffs.ps1 -BatchName golden_kolkata_2020
  powershell -NoProfile -File .\cleanup_done_tiffs.ps1 -Apply
#>
param(
    [string[]]$BatchName,
    [switch]$List,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$doneRoot = 'D:\Joshua\Done'
if (-not (Test-Path -LiteralPath $doneRoot -PathType Container)) {
    throw "Completed-batch folder not found: $doneRoot"
}
$doneRoot = (Get-Item -LiteralPath $doneRoot).FullName.TrimEnd('\')
$batchDirs = @(Get-ChildItem -LiteralPath $doneRoot -Directory | Sort-Object Name)
if ($BatchName.Count -gt 0) {
    $requested = @($BatchName | Select-Object -Unique)
    $batchDirs = @($batchDirs | Where-Object { $_.Name -in $requested })
    foreach ($name in $requested) {
        if ($name -notin @($batchDirs | ForEach-Object { $_.Name })) {
            throw "Requested batch not found directly under $doneRoot : $name"
        }
    }
}
if ($batchDirs.Count -eq 0) {
    throw "No batch folders found in $doneRoot"
}

$targets = New-Object 'System.Collections.Generic.List[System.IO.FileInfo]'
$journals = New-Object 'System.Collections.Generic.List[string]'
$pendingWal = New-Object 'System.Collections.Generic.List[string]'
$summary = @()
foreach ($batch in $batchDirs) {
    if (($batch.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing a linked batch directory: $($batch.FullName)"
    }

    $metadataDir = Join-Path $batch.FullName ("digitising_batches\" + $batch.Name)
    $returnList = Join-Path $metadataDir 'return_files.txt'
    $manifest = Join-Path $metadataDir 'batch_manifest.json'
    if (-not (Test-Path -LiteralPath $returnList -PathType Leaf) -or
        -not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
        throw "Missing return_files.txt or batch_manifest.json in $metadataDir"
    }

    $gpkgPaths = @(Get-Content -LiteralPath $returnList | Where-Object { $_.Trim() })
    if ($gpkgPaths.Count -eq 0) {
        throw "Empty return list: $returnList"
    }
    foreach ($relativePath in $gpkgPaths) {
        $relativePath = $relativePath.Trim().Replace('/', '\')
        if ([IO.Path]::IsPathRooted($relativePath) -or
            $relativePath -match '(^|\\)\.\.(\\|$)' -or
            -not $relativePath.EndsWith('.gpkg', [StringComparison]::OrdinalIgnoreCase)) {
            throw "Unsafe or unexpected return path in $returnList : $relativePath"
        }
        $gpkg = Join-Path $batch.FullName $relativePath
        if (-not (Test-Path -LiteralPath $gpkg -PathType Leaf)) {
            throw "Listed GeoPackage is missing: $gpkg"
        }
        foreach ($suffix in @('-wal', '-shm')) {
            $journal = $gpkg + $suffix
            if (Test-Path -LiteralPath $journal -PathType Leaf) {
                $journals.Add($journal)
                if ($suffix -eq '-wal' -and (Get-Item -LiteralPath $journal).Length -gt 0) {
                    $pendingWal.Add($journal)
                }
            }
        }
    }

    $processed = Join-Path $batch.FullName 'processed'
    $tiffs = @()
    if (Test-Path -LiteralPath $processed -PathType Container) {
        $tiffs = @(Get-ChildItem -LiteralPath $processed -Recurse -File |
            Where-Object {
                $_.Extension -in @('.tif', '.tiff') -and
                ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0
            })
    }
    foreach ($tiff in $tiffs) {
        $batchPrefix = $batch.FullName.TrimEnd('\') + '\'
        if (-not $tiff.FullName.StartsWith($batchPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "TIFF resolved outside its batch: $($tiff.FullName)"
        }
        $targets.Add($tiff)
    }
    $bytes = ($tiffs | Measure-Object -Property Length -Sum).Sum
    $summary += [pscustomobject]@{
        Batch = $batch.Name
        GeoPackages = $gpkgPaths.Count
        TIFFs = $tiffs.Count
        GiB = [math]::Round(($bytes / 1GB), 2)
    }
}

$summary | Format-Table -AutoSize | Out-Host
$totalBytes = ($targets | Measure-Object -Property Length -Sum).Sum
Write-Host ("Total: {0} TIFFs, {1:N2} GiB" -f $targets.Count, ($totalBytes / 1GB))
Write-Host 'Scope: .tif/.tiff files under each completed batch\processed only. No folders or other file types are removed.'

if ($journals.Count -gt 0) {
    Write-Warning "Found $($journals.Count) GeoPackage journal files, including $($pendingWal.Count) nonempty WAL files. Do not copy GeoPackages while QGIS is editing them."
    if ($pendingWal.Count -gt 0) {
        $pendingWal | ForEach-Object { Write-Host "  Pending WAL: $_" }
    }
}
if ($List) {
    $targets | ForEach-Object { Write-Host $_.FullName }
}
if (-not $Apply) {
    Write-Host 'Preview only. Run again with -Apply to remove the listed TIFFs.'
    return
}
if (Get-Process -Name 'qgis*' -ErrorAction SilentlyContinue) {
    throw 'Cleanup cancelled because QGIS is running. Close QGIS and retry.'
}
if ($pendingWal.Count -gt 0) {
    throw 'Cleanup cancelled because nonempty GeoPackage WAL files may contain unsaved edits.'
}

$confirmation = Read-Host 'Type DELETE TIFFS to remove these files'
if ($confirmation -cne 'DELETE TIFFS') {
    throw 'Cleanup cancelled; confirmation did not match.'
}
foreach ($tiff in $targets) {
    Remove-Item -LiteralPath $tiff.FullName -Force -ErrorAction Stop
}
Write-Host "Removed $($targets.Count) TIFFs. Batch folder structure and GeoPackages remain."
