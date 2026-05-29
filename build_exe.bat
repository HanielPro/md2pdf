@echo off
REM Build a single-file Windows executable using PyInstaller
REM Usage: run this file in the repository root (Developer PowerShell or cmd)

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

REM If your markdowns reference files in `data/`, bundle that folder too
pyinstaller --onefile --name markdown_to_pdf --add-data "data;data" src\main.py

if %ERRORLEVEL% EQU 0 (
  echo Build successful. Dist file: dist\markdown_to_pdf.exe
) else (
  echo Build failed with errorlevel %ERRORLEVEL%.
)

pause
