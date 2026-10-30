$ErrorActionPreference = 'Stop'
$job = $PSScriptRoot
$python = 'C:\Users\Joshua Pretorius\anaconda3\envs\opendrift\python.exe'
foreach ($name in @('process.pid','finish.pid')) {
    $file = Join-Path $job $name
    if (Test-Path -LiteralPath $file) {
        $existing = Get-Process -Id ([int](Get-Content -LiteralPath $file)) -ErrorAction SilentlyContinue
        if ($existing) { throw "A job worker is still running: $name. Check its status before restarting." }
    }
}
$processor = Start-Process -FilePath $python -ArgumentList @('-m','pipeline','slc_process','--manifest',"$job\local_job.yaml") -WorkingDirectory 'D:\Masters\sar_server_pipeline' -RedirectStandardOutput "$job\run.stdout.log" -RedirectStandardError "$job\run.stderr.log" -WindowStyle Hidden -PassThru
$processor.Id | Set-Content "$job\process.pid"
$finisher = Start-Process -FilePath $python -ArgumentList "$job\finish_local.py" -WorkingDirectory 'D:\Masters\sar_server_pipeline' -RedirectStandardOutput "$job\finish.stdout.log" -RedirectStandardError "$job\finish.stderr.log" -WindowStyle Hidden -PassThru
$finisher.Id | Set-Content "$job\finish.pid"
Write-Output "Local processor: $($processor.Id); completion worker: $($finisher.Id)"
