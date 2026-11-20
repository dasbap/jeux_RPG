@echo off
cd /d "%~dp0"
if exist ".venv-reprise\Scripts\python.exe" (
  ".venv-reprise\Scripts\python.exe" -m scripts.image_to_3d %*
) else (
  python -m scripts.image_to_3d %*
)
if errorlevel 1 pause
