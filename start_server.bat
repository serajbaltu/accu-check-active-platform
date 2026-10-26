@echo off
chcp 65001 > nul
title Accu-Chek Active Platform
cd /d "%~dp0"

echo ========================================================
echo   Accu-Chek Active Diabetes Management Platform
echo ========================================================
echo.
echo Launching local server and dashboard on http://127.0.0.1:5050 ...
echo.

set CURL_CA_BUNDLE=
start "" http://127.0.0.1:5050
python -X utf8 server.py

pause
