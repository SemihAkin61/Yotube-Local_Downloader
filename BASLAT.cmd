@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 baslat.py
if errorlevel 1 (
 echo Site acilamadi. Python 3 kurulu oldugundan ve 8765 portunun bos oldugundan emin ol.
 pause
)
