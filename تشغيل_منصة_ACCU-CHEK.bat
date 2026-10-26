@echo off
chcp 65001 > nul
title منصة ACCU-CHEK Active لتحليل بيانات السكر
cd /d "%~dp0"

echo ========================================================
echo   منصة ACCU-CHEK Active - نظام القراءة والتحليل السريري
echo ========================================================
echo.
echo جاري تشغيل الخادم المحلي وفتح لوحة التحكم في المتصفح...
echo.

set CURL_CA_BUNDLE=
start "" http://127.0.0.1:5050
python -X utf8 server.py

pause
