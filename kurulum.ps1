$ErrorActionPreference = 'Stop'
$toolFolder = Join-Path $PSScriptRoot '.tools'
New-Item -ItemType Directory -Path $toolFolder -Force | Out-Null
Write-Host 'Resmi yt-dlp araci indiriliyor / guncelleniyor...'
Invoke-WebRequest -Uri 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe' -OutFile (Join-Path $toolFolder 'yt-dlp.exe')
$ariaExe = Join-Path $toolFolder 'aria2c.exe'
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (Test-Path -LiteralPath $csc) {
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
    & $csc /nologo /optimize /out:$ariaExe $csPath
    Remove-Item $csPath -Force -ErrorAction SilentlyContinue
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host 'FFmpeg bulunamadi. FFmpeg kurup PATH alanina ekledikten sonra yeniden baslatin.'
    Write-Host 'https://ffmpeg.org/download.html'
    exit 1
}
py -3 --version
if ($LASTEXITCODE -ne 0) { throw 'Python 3 kurulmali: https://www.python.org/downloads/' }
Write-Host 'Hazir. BASLAT.cmd dosyasina cift tiklayin.'
