@echo off
setlocal
call "%~dp0build-distribution.cmd" windows
exit /b %errorlevel%
