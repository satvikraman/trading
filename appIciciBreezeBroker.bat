@echo off

call C:\Users\Admin\anaconda3\Scripts\activate.bat C:\Users\Admin\anaconda3
call conda activate trd_chrome
CD /D D:\araman\trading-breeze\trading

IF NOT EXIST .\credentials.json (
    CALL decrypt.bat
)


:START
python src/icici/appIciciBreeze.py
TIMEOUT /T 5 /NOBREAK

FOR /F "delims=" %%a IN ('powershell -NoL -NoP -Command "(Get-Date).Hour"') DO (SET /A "HOUR=%%a")
FOR /F "delims=" %%a IN ('powershell -NoL -NoP -Command "(Get-Date).Minute"') DO (SET /A "MIN=%%a")
IF %HOUR% LSS 15 (
    ECHO "Restarting appIciciBreeze at " %HOUR%:%MIN%
    goto START
)
IF %HOUR% LEQ 15 (
    IF %MIN% LEQ 30 (
        ECHO "Restarting appIciciBreeze at " %HOUR%:%MIN%
        goto START
    )
)

