@echo off
setlocal
cd /d "%~dp0"
set "RPG_TARGET=%~1"
if not defined RPG_TARGET set "RPG_TARGET=all"
set "RPG_STAGE="
if "%RPG_TARGET%"=="windows" set "RPG_STAGE=desktop"
if "%RPG_TARGET%"=="linux" set "RPG_STAGE=desktop"
if "%RPG_TARGET%"=="android" set "RPG_STAGE=android"
if "%RPG_TARGET%"=="all" set "RPG_STAGE=android"
if not defined RPG_STAGE (
  echo Usage: build-distribution.cmd [windows^|linux^|android^|all]
  exit /b 2
)
docker info >nul 2>nul
if errorlevel 1 (
  echo Demarrer Docker Desktop en mode conteneurs Linux, puis relancer.
  exit /b 1
)
if not exist dist mkdir dist
docker build --platform linux/amd64 --target %RPG_STAGE% -f deploy/build/Dockerfile -t jeux-rpg-build:%RPG_STAGE% .
if errorlevel 1 exit /b 1
if "%RPG_STAGE%"=="android" (
  if not exist .signing mkdir .signing
  docker run --rm --platform linux/amd64 --mount "type=bind,source=%cd%\dist,target=/out" --mount "type=bind,source=%cd%\.signing,target=/project/.signing" jeux-rpg-build:%RPG_STAGE% %RPG_TARGET%
) else (
  docker run --rm --platform linux/amd64 --mount "type=bind,source=%cd%\dist,target=/out" jeux-rpg-build:%RPG_STAGE% %RPG_TARGET%
)
exit /b %errorlevel%
