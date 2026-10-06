$ErrorActionPreference = 'Stop'
$siteUrl = 'http://127.0.0.1:8765'
$projectFolder = $PSScriptRoot
$launcherMutex = New-Object System.Threading.Mutex($false, 'Local\YouTubeIndiriciLauncher')
$hasLock = $false

function Test-Downloader {
    try {
        $config = Invoke-RestMethod -Uri "$siteUrl/api/config" -TimeoutSec 2
        if ($config.app -eq 'youtube-indirici') {
            return $true
        }
        throw '8765 portunda baska bir uygulama calisiyor.'
    } catch [System.Net.WebException] {
        if ($_.Exception.Response) { throw '8765 portunda baska bir uygulama calisiyor.' }
        return $false
    }
}

try {
    $braveCandidates = @(
        (Join-Path $env:ProgramFiles 'BraveSoftware\Brave-Browser\Application\brave.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'BraveSoftware\Brave-Browser\Application\brave.exe'),
        (Join-Path $env:LOCALAPPDATA 'BraveSoftware\Brave-Browser\Application\brave.exe')
    )
    $bravePath = $braveCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $bravePath) { throw 'Brave bulunamadi. Brave tarayicisini kurup tekrar deneyin.' }

    try { $hasLock = $launcherMutex.WaitOne(30000) }
    catch [System.Threading.AbandonedMutexException] { $hasLock = $true }
    if (-not $hasLock) { throw 'Site zaten baslatiliyor. Biraz sonra yeniden deneyin.' }

    if (-not (Test-Downloader)) {
        $pythonLauncher = Get-Command pyw.exe -ErrorAction SilentlyContinue
        if (-not $pythonLauncher) { throw 'Python 3 baslaticisi bulunamadi. Python kurulumunu kontrol edin.' }
        $serverPath = Join-Path $projectFolder 'server.py'
        Start-Process -FilePath $pythonLauncher.Source -ArgumentList @('-3', ('"' + $serverPath + '"'), '--no-browser') -WorkingDirectory $projectFolder -WindowStyle Hidden
        $ready = $false
        for ($attempt = 0; $attempt -lt 40; $attempt++) {
            Start-Sleep -Milliseconds 500
            if (Test-Downloader) { $ready = $true; break }
        }
        if (-not $ready) { throw 'Site baslatilamadi. Python kurulumunu ve 8765 portunu kontrol edin.' }
    }
    Start-Process -FilePath $bravePath -ArgumentList @('--new-tab', $siteUrl)
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'YouTube Indirici', 'OK', 'Error') | Out-Null
} finally {
    if ($hasLock) { $launcherMutex.ReleaseMutex() }
    $launcherMutex.Dispose()
}
