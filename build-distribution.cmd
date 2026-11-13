@echo off
setlocal
cd /d "%~dp0"
python scripts\build_distribution.py
exit /b %errorlevel%
