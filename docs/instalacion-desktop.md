# Instalación y actualizaciones (Windows)

## Instalar

1. Abre [GitHub Releases](https://github.com/isaacalbala12/Vantare-Ingeniero/releases) y descarga el instalador más reciente: `vantare-ingeniero-X.Y.Z-setup.exe`.
2. Ejecuta el instalador. Si Windows SmartScreen advierte sobre un editor desconocido, elige **Más información** → **Ejecutar de todas formas** (hasta que el binario esté firmado con certificado de código).
3. Inicia **Vantare Ingeniero IA** desde el menú Inicio o el acceso directo del escritorio.

El instalador incluye:

- Hub y overlay (Electron)
- Backend empaquetado (PyInstaller)
- Utilidad `duck_lmu` para bajar volumen del juego durante TTS

## Actualizar desde la app

1. Abre el Hub → **Avanzado** → sección **Actualizaciones**.
2. Pulsa **Buscar actualizaciones**.
3. Si hay versión nueva, pulsa **Descargar** y espera a que termine la barra de progreso.
4. Pulsa **Reiniciar para actualizar**.

La app instalada y el backend se actualizan juntos en un solo instalador (lockstep).

## Modo desarrollo

Si ejecutas con `npm run dev:electron`, las actualizaciones automáticas están desactivadas. Usa Releases o el script local:

```powershell
powershell -File scripts/build-desktop.ps1
```

## Build local del instalador

Requisitos: Python 3.12+, Node 22+, backend compilado con PyInstaller.

```powershell
powershell -File scripts/build-desktop.ps1
```

Salida: `frontend/release/vantare-ingeniero-<version>-setup.exe`

## Instalador legacy

El script `installer/windows.nsi` (solo backend) está obsoleto. Usa `electron-builder` vía `npm run build:desktop`.
