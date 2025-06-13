@echo off
echo Suppression des dossiers __pycache__...
for /d /r %%i in (__pycache__) do (
    if exist "%%i" (
        echo Supprime : %%i
        rmdir /s /q "%%i"
    )
)
echo Termine.
cls
