$ErrorActionPreference = 'Stop'
$toolFolder = Join-Path $PSScriptRoot '.tools'
New-Item -ItemType Directory -Path $toolFolder -Force | Out-Null
Write-Host 'Resmi yt-dlp araci indiriliyor / guncelleniyor...'
Invoke-WebRequest -Uri 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe' -OutFile (Join-Path $toolFolder 'yt-dlp.exe')
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host 'FFmpeg bulunamadi. FFmpeg kurup PATH alanina ekledikten sonra yeniden baslatin.'
    Write-Host 'https://ffmpeg.org/download.html'
    exit 1
}
py -3 --version
if ($LASTEXITCODE -ne 0) { throw 'Python 3 kurulmali: https://www.python.org/downloads/' }
Write-Host 'Hazir. BASLAT.cmd dosyasina cift tiklayin.'
