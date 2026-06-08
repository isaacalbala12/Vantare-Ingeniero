# Electron Hub + Overlay — Smoke Checklist

| Check | Esperado |
|-------|----------|
| Hub arranca 1920×1080 | Ventana con decorations, fondo opaco |
| Overlay toggle | Aparece derecha-centro sobre sim |
| Telemetría 20Hz | Inicio actualiza speed/lap |
| PTT global | Ctrl+Shift+Space alterna escucha/envío |
| TTS + duck | Juego baja volumen durante speech (duck_lmu.exe) |
| Spotter IMMEDIATE | Preempt engineer queue |
| Perfiles | Save/load API desde sección Perfiles |
| Historial | JSON en `%APPDATA%/Vantare/history` |
| Resize overlay | Ctrl+Shift+O activa redimensionado |
| Tray | Cerrar hub lo oculta; overlay sigue disponible |

## Comandos dev

```powershell
.\scripts\dev-electron.ps1
# o
cd frontend; npm run dev:electron
```

## Build desktop

```powershell
.\scripts\build-duck.ps1
cd frontend
npm run build:desktop
```
