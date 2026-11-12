@echo off
rem Arranca NeuroDAC con el entorno .venv, sin uv. Doble clic para usarlo.
rem La primera vez hay que instalar con tools\instalar_sin_uv.ps1.
rem Sin etiquetas ni saltos a proposito: son lo que falla en cmd.exe cuando
rem un .bat llega con finales de linea LF.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo No encuentro el entorno .venv. Primero instala NeuroDAC con:
    echo   powershell -ExecutionPolicy Bypass -File tools\instalar_sin_uv.ps1
    echo.
    pause
    exit /b 1
)
echo Arrancando NeuroDAC. El navegador se abre en unos segundos.
echo Para detenerlo, cierra esta ventana o presiona CTRL + C.
start "" cmd /c "timeout /t 6 /nobreak >nul & start http://127.0.0.1:8050/"
".venv\Scripts\python.exe" interfaz.py
pause
