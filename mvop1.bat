@echo off
setlocal

set "ZIP=mvop.zip"
set "TMP=mvop.zip.tmp"
set "URL=https://github.com/k25c2yf/BGI_utf8_for-Tayutama2AS/releases/download/V2.0/mvop.zip"
set "DEST=outputgbk"

if exist "%ZIP%" (
    echo [mvop] %ZIP% already exists, skipping download.
) else (
    echo [mvop] Downloading %ZIP% ...
    if exist "%TMP%" del /f /q "%TMP%"
    curl -L -o "%TMP%" "%URL%"
    if errorlevel 1 (
        echo [ERROR] Download failed!
        if exist "%TMP%" del /f /q "%TMP%"
        pause
        exit /b 1
    )
    if not exist "%TMP%" (
        echo [ERROR] Download failed!
        pause
        exit /b 1
    )
    ren "%TMP%" "%ZIP%"
)

echo [mvop] Extracting to %DEST% ...
if not exist "%DEST%" mkdir "%DEST%"
tar -xf "%ZIP%" -C "%DEST%"

if errorlevel 1 (
    echo [ERROR] Extraction failed!
    pause
    exit /b 1
)

echo [mvop] Done.
exit /b 0