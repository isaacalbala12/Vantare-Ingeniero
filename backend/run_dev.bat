@echo off
REM ============================================================
REM  run_dev.bat - Arranca el backend en modo desarrollo
REM  Usa uvicorn directamente (SIN PyInstaller)
REM  Los cambios en .py se reflejan automaticamente con hot-reload
REM ============================================================

set "BASE_DIR=%~dp0"
cd /d "%BASE_DIR%"

REM Intentar activar virtualenv si existe
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [i] Virtualenv activado
) else (
    echo [!] No se encontro .venv. Usando Python del sistema.
    echo    Ejecuta primero: scripts\setup_venv.bat
)

echo.
echo === Arrancando backend en MODO DESARROLLO ===
echo    Host: 127.0.0.1:8008
echo    Hot-reload: ACTIVADO
echo    PyInstaller: NO
echo.
python run_dev.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Fallo al arrancar. Asegurate de tener las dependencias instaladas.
    echo    Ejecuta: scripts\setup_venv.bat
    pause
)
