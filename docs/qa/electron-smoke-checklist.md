# Electron — Smoke Checklist (dev + instalador)

## Instalador empaquetado (primer deploy)

| Check | Esperado |
|-------|----------|
| Primera apertura | Hub visible con sidebar (no pantalla negra) |
| Header health | Backend online tras ~5–15 s (backend.exe en resources) |
| LMU con sim abierto | Indicador LMU verde |
| Hub → Avanzado → Actualizaciones | Versión instalada + buscar updates |
| Overlay toggle | Tarjeta speaking/listening sobre el sim |
| Cerrar ventana | Hub se oculta; icono en tray |
| Tray → Salir | Cierra app y backend |

## Desarrollo (`npm run dev:electron`)

| Check | Esperado |
|-------|----------|
| Hub arranca 1920×1080 | Ventana con decorations, fondo opaco |
| Backend manual | `python backend/run_dev.py` en :8008 |
| Overlay toggle | Aparece derecha-centro sobre sim |
| Telemetría 20Hz | Inicio actualiza speed/lap |
| PTT global | Ctrl+Shift+Space alterna escucha/envío |
| TTS + duck | Juego baja volumen durante speech (duck_lmu.exe) |
| Spotter IMMEDIATE | Preempt engineer queue |
| Perfiles | Save/load API desde sección Perfiles |
| Historial | JSON en `%APPDATA%/vantare/` o userData Electron |

## Comandos

```powershell
.\scripts\dev-electron.ps1
# o
cd frontend; npm run dev:electron
```

## Build + verificación local

```powershell
powershell -File scripts/build-desktop.ps1
powershell -File scripts/verify-desktop-artifacts.ps1
```

## CI

- **Pre-release:** Actions → Pre-Release Gate (build sin publicar)
- **Release:** tag `v*` → Release Desktop

Runbook: [first-deploy-runbook.md](../launch/first-deploy-runbook.md)
