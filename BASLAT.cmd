@echo off
setlocal
cd /d "%~dp0"
title RIGLAB
where python >nul 2>nul
if errorlevel 1 (
    echo Python bulunamadi. Python kurulurken Add Python to PATH secenegini ac.
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    echo RIGLAB icin yerel Python ortami hazirlaniyor...
    python -m venv .venv
    if errorlevel 1 (
        pause
        exit /b 1
    )
)
echo RIGLAB bagimliliklari kontrol ediliyor...
".venv\Scripts\python.exe" -m pip --disable-pip-version-check install --quiet -r requirements.txt
if errorlevel 1 (
    echo Kurulum tamamlanamadi. Yukaridaki hata mesaji gerekli.
    pause
    exit /b 1
)
echo Site aciliyor. Bu pencere acik kalmali.
echo Sistemleri yonet dugmesinden ilan ve fiyatlarini elle ekleyebilirsin.
".venv\Scripts\python.exe" bot.py --source manual --port 0
set "RIGLAB_EXIT_CODE=%ERRORLEVEL%"
if not "%RIGLAB_EXIT_CODE%"=="0" pause
exit /b %RIGLAB_EXIT_CODE%
