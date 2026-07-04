@echo off
echo xWavetable - Standalone EXE Build
echo ==================================

echo Pruefe Python...
python --version 2>nul || (
    echo FEHLER: Python nicht gefunden. Bitte von https://python.org installieren.
    pause & exit /b 1
)

echo Installiere Abhaengigkeiten...
pip install numpy pyinstaller

echo.
echo Optionales Drag+Drop (tkinterdnd2)?
set /p DND="Installieren? [j/N]: "
if /i "%DND%"=="j" pip install tkinterdnd2

echo.
echo Baue EXE...
pyinstaller xWavetable.spec --clean

echo.
if exist "dist\xWavetable.exe" (
    echo Fertig! EXE liegt unter: dist\xWavetable.exe
) else (
    echo FEHLER beim Build - siehe Ausgabe oben.
)
pause
