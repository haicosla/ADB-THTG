@echo off
cd /d "%~dp0"

echo ========================================
echo       DONG BO THTG ADB LEN GITHUB
echo ========================================
echo.

git add .

git diff --cached --quiet
if %errorlevel%==0 (
    echo Khong co thay doi.
    echo.
    pause
    exit /b
)

git commit -m "Auto sync %date% %time%"

git push origin main

echo.
echo ========================================
echo          DA DONG BO XONG
echo ========================================
pause