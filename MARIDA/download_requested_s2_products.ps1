param(
    [string]$CredentialPath = 'C:\Users\Joshua Pretorius\Desktop\Corpenicus_creds.txt',
    [string]$OutputDirectory = 'D:\Masters\MARIDA\downloads\16PDC\2018-10-24\copernicus_products'
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression

$products = @(
    @{ Name = 'S2A_MSIL1C_20181024T161331_N0500_R140_T16PCC_20230728T071849.SAFE'; Id = '6d9bfe3b-a89b-4025-9e33-528a1ff26d0d'; Size = 658287519 },
    @{ Name = 'S2A_MSIL1C_20181024T161331_N0500_R140_T16PDC_20230728T071849.SAFE'; Id = '07521eeb-cd36-4eec-8eac-45cef5ca68bf'; Size = 748985118 },
    @{ Name = 'S2A_MSIL2A_20181024T161331_N0500_R140_T16PEC_20230729T044439.SAFE'; Id = '848138e1-6e2d-4cd2-9861-13348e098f13'; Size = 1012230773 }
)

$credentialLines = Get-Content -LiteralPath $CredentialPath
$clientId = ($credentialLines | Where-Object { $_ -match '^CLIENT_ID\s*[:=]' } | Select-Object -First 1) -replace '^CLIENT_ID\s*[:=]\s*', ''
$clientSecret = ($credentialLines | Where-Object { $_ -match '^CLIENT_SECRET\s*[:=]' } | Select-Object -First 1) -replace '^CLIENT_SECRET\s*[:=]\s*', ''
if (-not $clientId -or -not $clientSecret) { throw 'Expected CLIENT_ID and CLIENT_SECRET in credential file.' }

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
foreach ($product in $products) {
    $target = Join-Path $OutputDirectory ($product.Name + '.zip')
    $partial = $target + '.partial'
    if ((Test-Path -LiteralPath $target) -and (Get-Item -LiteralPath $target).Length -eq $product.Size) {
        Write-Output "SKIP $($product.Name): expected byte count already present"
        continue
    }

    $token = Invoke-RestMethod -Method Post -Uri 'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token' -Body @{
        grant_type = 'client_credentials'; client_id = $clientId; client_secret = $clientSecret
    } -TimeoutSec 30
    $client = [System.Net.Http.HttpClient]::new()
    $client.Timeout = [TimeSpan]::FromHours(2)
    $client.DefaultRequestHeaders.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new('Bearer', $token.access_token)
    $uri = "https://download.dataspace.copernicus.eu/odata/v1/Products($($product.Id))/`$value"
    Write-Output "START $($product.Name) ($($product.Size) bytes)"
    try {
        $response = $client.GetAsync($uri, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
        try {
            $response.EnsureSuccessStatusCode() | Out-Null
            if ($response.Content.Headers.ContentLength -ne $product.Size) { throw 'Catalogue and download sizes differ.' }
            $inputStream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
            try {
                $outputStream = [System.IO.File]::Open($partial, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
                try {
                    $buffer = [byte[]]::new(4MB)
                    $total = [long]0
                    $nextReport = [long]100MB
                    while (($count = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                        $outputStream.Write($buffer, 0, $count)
                        $total += $count
                        if ($total -ge $nextReport) {
                            Write-Output "PROGRESS $($product.Name) $total/$($product.Size)"
                            $nextReport += [long]100MB
                        }
                    }
                } finally { $outputStream.Dispose() }
            } finally { $inputStream.Dispose() }
        } finally { $response.Dispose() }
    } finally { $client.Dispose() }

    if ((Get-Item -LiteralPath $partial).Length -ne $product.Size) { throw "Incomplete download: $($product.Name)" }
    $archive = [System.IO.Compression.ZipFile]::OpenRead($partial)
    try {
        if ($archive.Entries.Count -lt 10) { throw "Unexpected ZIP contents: $($product.Name)" }
        Write-Output "ZIP_ENTRIES $($product.Name) $($archive.Entries.Count)"
    } finally { $archive.Dispose() }
    Move-Item -LiteralPath $partial -Destination $target -Force
    Write-Output "DONE $target"
}
