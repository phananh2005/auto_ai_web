@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo         DONG GOI UNG DUNG AUTO AI WEB (WINDOWS)
echo ========================================================

echo 1. Kiem tra Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] Khong tim thay Python trong PATH. Vui long cai Python hoac kich hoat venv!
    if "%~1" neq "--no-pause" pause
    exit /b 1
)

echo 2. Kiem tra PyInstaller...
python -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo PyInstaller chua duoc cai dat. Dang tien hanh cai dat...
    python -m pip install pyinstaller
    if %errorlevel% neq 0 (
        echo [LOI] Cai dat PyInstaller that bai!
        if "%~1" neq "--no-pause" pause
        exit /b 1
    )
)

echo 3. Bat dau dong goi voi PyInstaller...
python -m PyInstaller --noconfirm auto_ai_web.spec
if %errorlevel% neq 0 (
    echo [LOI] Qua trinh build that bai!
    if "%~1" neq "--no-pause" pause
    exit /b 1
)

echo 4. Kiem tra va dong goi trinh duyet Playwright...
set "PW_SRC=%LOCALAPPDATA%\ms-playwright"
set "PW_DEST=dist\auto_ai_web\ms-playwright"

if exist "%PW_SRC%" (
    echo Tim thay trinh duyet tai: %PW_SRC%
    echo Dang sao chep Chromium va FFmpeg vao %PW_DEST%...
    if not exist "%PW_DEST%" mkdir "%PW_DEST%"
    for /d %%D in ("%PW_SRC%\chromium*") do (
        echo   - Sao chep %%~nxD...
        xcopy /E /I /Y /Q "%%D" "%PW_DEST%\%%~nxD\" >nul 2>&1
    )
    for /d %%D in ("%PW_SRC%\ffmpeg*") do (
        echo   - Sao chep %%~nxD...
        xcopy /E /I /Y /Q "%%D" "%PW_DEST%\%%~nxD\" >nul 2>&1
    )
    echo [OK] Da tich hop trinh duyet Playwright thanh cong.
) else (
    echo [CANH BAO] Khong tim thay %PW_SRC%.
    echo Ban can chay "playwright install chromium" tren may dich hoac copy thu muc ms-playwright vao dist\auto_ai_web\
)

echo ========================================================
echo [HOAN TAT] Thu muc portable san sang tai: dist\auto_ai_web\
echo File thuc thi: dist\auto_ai_web\auto_ai_web.exe
echo ========================================================
if "%~1" neq "--no-pause" pause
