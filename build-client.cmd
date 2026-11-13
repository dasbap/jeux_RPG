@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Installer Node.js 22.12 ou plus recent, puis relancer cette commande.
  exit /b 1
)
where python >nul 2>nul
if errorlevel 1 (
  echo Installer Python 3.11 ou plus recent, puis relancer cette commande.
  exit /b 1
)
call npm --prefix desktop ci --no-audit
if errorlevel 1 exit /b 1
call npm --prefix desktop run build:win
if errorlevel 1 exit /b 1
echo Application creee : %~dp0dist\client\Jeux-RPG.exe
