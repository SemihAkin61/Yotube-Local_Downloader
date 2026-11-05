$ErrorActionPreference = 'Stop'
# PowerShell 5.1'de ilerleme cubugu indirmeyi asiri yavaslatir; kapatiyoruz.
$ProgressPreference = 'SilentlyContinue'
# Eski Windows surumlerinde GitHub icin TLS 1.2 gerekir.
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$toolFolder = Join-Path $PSScriptRoot '.tools'
New-Item -ItemType Directory -Path $toolFolder -Force | Out-Null

Write-Host 'Resmi yt-dlp araci indiriliyor / guncelleniyor...'
$ytdlp = Join-Path $toolFolder 'yt-dlp.exe'
$ytdlpTemp = "$ytdlp.download"
try {
    Invoke-WebRequest -Uri 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe' -OutFile $ytdlpTemp -UseBasicParsing
    if ((Get-Item -LiteralPath $ytdlpTemp).Length -lt 1MB) { throw 'Indirilen yt-dlp dosyasi eksik gorunuyor.' }
    Move-Item -LiteralPath $ytdlpTemp -Destination $ytdlp -Force
} catch {
    Remove-Item -LiteralPath $ytdlpTemp -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $ytdlp) {
        Write-Host "UYARI: yt-dlp guncellenemedi, mevcut surum kullanilacak. ($($_.Exception.Message))"
        Write-Host 'Uygulama aciksa tarayici sekmesini kapatip birkac saniye sonra tekrar deneyin.'
    } else {
        throw "yt-dlp indirilemedi. Internet baglantinizi kontrol edin. ($($_.Exception.Message))"
    }
}

# Hizli (cok baglantili) indirme yardimcisi: yt-dlp bunu harici indirici olarak cagirir.
$ariaExe = Join-Path $toolFolder 'aria2c.exe'
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (Test-Path -LiteralPath $csc) {
    Write-Host 'Hizli indirme yardimcisi hazirlaniyor...'
    $csPath = Join-Path $toolFolder 'launcher.cs'
    Set-Content -Path $csPath -Encoding UTF8 -Value @'
using System;
using System.Diagnostics;
using System.IO;
class Program {
    static int Main(string[] args) {
        string dir = AppDomain.CurrentDomain.BaseDirectory;
        string server = Path.GetFullPath(Path.Combine(dir, "..", "server.py"));
        var psi = new ProcessStartInfo("py", "-3 \"" + server + "\" --fast-dl") { UseShellExecute = false };
        psi.EnvironmentVariables["FAST_DL_ARGC"] = args.Length.ToString();
        for (int i = 0; i < args.Length; i++) psi.EnvironmentVariables["FAST_DL_ARG_" + i] = args[i];
        var p = Process.Start(psi);
        p.WaitForExit();
        return p.ExitCode;
    }
}
'@
    & $csc /nologo /optimize /out:$ariaExe $csPath | Out-Host
    $compiled = $LASTEXITCODE -eq 0
    Remove-Item $csPath -Force -ErrorAction SilentlyContinue
    if (-not $compiled) {
        Write-Host 'UYARI: Hizli indirme yardimcisi hazirlanamadi. Indirme yine calisir ancak daha yavas olabilir.'
    }
} else {
    Write-Host 'UYARI: .NET derleyicisi bulunamadi; hizli indirme yardimcisi atlandi. Indirme yine calisir ancak daha yavas olabilir.'
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host 'FFmpeg bulunamadi. FFmpeg kurup PATH alanina ekledikten sonra yeniden baslatin.'
    Write-Host 'https://ffmpeg.org/download.html'
    exit 1
}
py -3 --version
if ($LASTEXITCODE -ne 0) { throw 'Python 3 kurulmali: https://www.python.org/downloads/' }
Write-Host 'Hazir. AC.vbs (arka planda) veya BASLAT.cmd dosyasina cift tiklayin.'
