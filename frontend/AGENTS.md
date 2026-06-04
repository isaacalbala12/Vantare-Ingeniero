# FRONTEND

**Branch:** `feature/benchmark-llm` | **Updated:** 2026-06-01

## OVERVIEW

Tauri v2 desktop app — React 18 + TypeScript + Vite. Overlay UI for the AI race engineer: PTT voice chat, radio overlay, system tray, config panel.

## STRUCTURE

```
src/
├── main.tsx             # React entry point
├── App.tsx              # Root component
├── App.css              # Global styles
├── components/          # UI components
│   ├── ChatBubble.tsx       # LLM response display
│   ├── ConfigTab.tsx        # Settings panel
│   ├── PTTIndicator.tsx     # Push-to-talk status
│   ├── RadioOverlay.tsx     # In-game radio overlay
│   └── SystemTrayMenu.tsx   # System tray context menu
├── hooks/               # Custom React hooks
│   ├── useAudioCapture.ts   # Microphone capture
│   ├── useAudioContext.ts   # Audio context management
│   ├── useHotkey.ts         # Global hotkey binding
│   ├── usePTT.ts            # Push-to-talk state
│   └── useWebSocket.ts      # WebSocket connection to backend
├── services/            # API & utilities
│   ├── api.ts               # REST API client
│   ├── audioQueue.ts        # Audio playback queue
│   └── msgpack.ts           # MessagePack codec for WS
├── store/               # Zustand state management
│   ├── appStore.ts          # Global app state
│   └── config.ts            # User config
├── assets/              # Static assets
├── styles/              # Style sheets
└── __tests__/           # Vitest test files (8 tests)
```

## WHERE TO LOOK

| Task | File |
|------|------|
| WebSocket connection | `src/hooks/useWebSocket.ts` |
| PTT voice input | `src/hooks/usePTT.ts` + `src/hooks/useAudioCapture.ts` |
| App state | `src/store/appStore.ts` |
| Radio overlay UI | `src/components/RadioOverlay.tsx` |
| Settings | `src/components/ConfigTab.tsx` + `src/store/config.ts` |
| API calls | `src/services/api.ts` |
| Audio output | `src/services/audioQueue.ts` |

## CONVENTIONS

- **React 18** functional components + hooks (no class components)
- **Zustand** for state management (no Redux)
- **WebSocket** via native `WebSocket` API (no socket.io)
- **MessagePack** for binary WS payloads (`@msgpack/msgpack`)
- **Vitest** for testing (8 tests covering store, services, WebSocket)
- **Tauri v2** — Rust backend via `@tauri-apps/api`
- **Vite** bundler with TypeScript

## COMMANDS

```bash
# Install dependencies
npm install

# Dev server
npm run dev

# Run tests
npx vitest

# Run tests with UI
npx vitest --ui

# Build Tauri desktop app
npm run tauri build

# TypeScript check
npx tsc --noEmit
```
