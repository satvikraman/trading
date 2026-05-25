@echo off

REM Run from the batch file folder so relative .venv paths resolve reliably
pushd %~dp0

REM Activate .venv instead of conda
call .\.venv\Scripts\activate.bat

:START
python src/paytm/appPaytm.py
TIMEOUT /T 5 /NOBREAK

FOR /F "delims=" %%a IN ('powershell -NoL -NoP -Command "(Get-Date).Hour"') DO (SET /A "HOUR=%%a")
FOR /F "delims=" %%a IN ('powershell -NoL -NoP -Command "(Get-Date).Minute"') DO (SET /A "MIN=%%a")
IF %HOUR% LSS 15 (
    ECHO "Restarting appPayTm at " %HOUR%:%MIN%
    goto START
)
IF %HOUR% LEQ 15 (
    IF %MIN% LEQ 30 (
        ECHO "Restarting appPayTm at " %HOUR%:%MIN%
        goto START
    )
)

popd
