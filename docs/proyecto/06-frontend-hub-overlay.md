# 06 — Frontend: Hub, overlay y config

Raíz: `frontend/src/`

---

## Estructura principal

```
frontend/
├── electron/           # Main process Electron
│   ├── main.ts         # Ventanas Hub + overlay
│   └── updater.ts      # electron-updater (v0.5.1: sin verify signature)
├── src/
│   ├── hub/            # UI configuración (React)
│   ├── components/     # ConfigTab, overlay apps
│   ├── store/          # Zustand config + app state
│   ├── hooks/          # useWebSocket, usePTT, …
│   └── services/       # api.ts, configUpdatePayload.ts
└── electron-builder.yml
```

---

## Hub (configuración)

Entrada Hub: rutas/secciones en `src/hub/`.

| Sección | Archivo clave | Función |
|---------|--------------|---------|
| Ingeniero / Voz | `PersonalityPanel.tsx` | Proactividad, perlas, preview tono |
| Audio | `PhraseEditorPanel.tsx` | Editor frases spotter/triggers |
| Avanzado | `ConfigTab.tsx` | Toggles, actualizaciones, migraciones |
| Perfiles | forms + store | Perfiles guardados |

### Config store (`store/config.ts`)

- Schema versionado (`configVersion`)
- Migraciones al cargar
- Campos v5+: `ttsProviderEngineer`, `ttsProviderSpotter`
- Campos v0.5+: `proactivityLevel`, `pearlFrequency`

### Sync WebSocket

`hooks/useWebSocket.ts`:

- Envía `config_update` al conectar / cambiar
- Espera `config_ack` con campos reflejados
- **I1:** todo campo nuevo debe estar en payload + ack

`services/configUpdatePayload.ts` — map store → WS payload.

`hub/forms/appConfigKeys.ts` — registro keys conocidas.

---

## Overlay

- Ventana transparente estilo F1 radio
- Muestra speaking/listening según eventos WS `voice_playback_start` / `voice_playback_end`
- **No** renderiza telemetría numérica (fuera de scope producto)

Archivos: `OverlayApp`, `overlay.html`, assets en `dist/`.

---

## Electron main process

| Concern | Módulo |
|---------|--------|
| Spawn backend | `electron/main.ts` — lanza `resources/backend/backend.exe` empaquetado |
| Auto-update | `electron/updater.ts` |
| IPC Hub ↔ main | eventos desktop-update |

Dev: `npm run dev:electron` — backend **manual** en `:8008`.

---

## API cliente (`services/api.ts`)

- `GET /health` — status backend, versión
- `GET/PUT /phrases` — frases usuario (v0.4)
- Helpers TTS/transcribe según necesidad

---

## Tests frontend

`src/__tests__/` — Vitest:

- `personalityConfig.test.ts` — proactivity, pearls, migración
- `phraseEditor.test.ts` — editor frases
- Tests config store, audio queue (legacy), filters

Comando: `npm test` (~290+ tests).

---

## Build desktop

```powershell
powershell -File scripts/build-desktop.ps1
# o
cd frontend && npm run build:desktop
```

Salida: `frontend/release/vantare-ingeniero-{version}-setup.exe` + `latest.yml`.

Binaries backend empaquetados en `frontend/src-tauri/binaries/backend/` (histórico path Tauri, reutilizado por Electron).

---

## Legado Tauri

`frontend/src-tauri/` — iconos, binaries, config Rust **no usada en release Electron actual**. No confundir con shell activo.

Documentación shell: [`../arquitectura-shell-desktop.md`](../arquitectura-shell-desktop.md).
