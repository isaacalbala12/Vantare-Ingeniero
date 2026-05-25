@echo off
REM ============================================================
REM  setup_venv.bat - Crea un virtualenv limpio con solo las
REM  dependencias reales del proyecto Vantare Ingeniero Backend
REM ============================================================
echo.
echo === Creando virtualenv limpio para Vantare Ingeniero Backend ===
echo.

set "BASE_DIR=%~dp0.."
cd /d "%BASE_DIR%"

REM 1. Eliminar venv anterior si existe
if exist ".venv" (
    echo [*] Eliminando virtualenv anterior...
    rmdir /s /q ".venv"
)

REM 2. Crear nuevo virtualenv
echo [1/4] Creando virtualenv...
python -m venv .venv
if %errorlevel% neq 0 (
    echo [ERROR] No se pudo crear el virtualenv
    pause
    exit /b 1
)

REM 3. Activar virtualenv e instalar pip actualizado
echo [2/4] Actualizando pip...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul

REM 4. Instalar SOLO las dependencias del proyecto
echo [3/4] Instalando dependencias del proyecto...
pip install -e . --no-cache-dir
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al instalar las dependencias del proyecto
    pause
    exit /b 1
)

REM 5. Instalar paquetes locales (shared-*) en modo editable
echo [4/4] Instalando paquetes locales (shared-telemetry, shared-strategy)...
pip install -e "%~dp0..\..\shared-telemetry" --no-cache-dir
pip install -e "%~dp0..\..\shared-strategy" --no-cache-dir

REM 6. Instalar pyinstaller SOLO en el venv (no global)
pip install pyinstaller --no-cache-dir

echo.
echo === Virtualenv creado exitosamente! ===
echo.
echo Para activarlo: .venv\Scripts\activate
echo Para correr en dev: python run_dev.py
echo Para hacer build: python build_backend.py
echo.
pause
