# Pipeline — PlaybackModerator (paridad CC)

## Objetivo de paridad

Reproducir **`Audio/PlaybackModerator.cs` + `Sounds.cs` + NAudio**: una sola cola con prioridades, spotter interrumpe ingeniero, ducking del juego, mensajes que expiran si llegan tarde.

**La voz es distinta (TTS); las reglas de cola no.**

## CC: reglas de playback

| Regla CC | Comportamiento | Vantare |
|----------|----------------|---------|
| Spotter vs ingeniero | Spotter **corta** mensaje largo ingeniero | `enqueueImmediate` preempt NORMAL ✓ |
| `playMessageImmediately` | Bypass total cola | IMMEDIATE unshift ✓ |
| Prioridad numérica | Mensaje alto antes que bajo | IMMEDIATE queue antes NORMAL ✓ |
| Un stream audio | Un reproductor activo | `PriorityAudioQueue` serial ✓ |
| Message expiry | ~2 s — no hablar obsoleto | `ttl` parcial — **deuda** |
| Ducking juego | Baja volumen sim | `duck_lmu` Tauri ✓ |
| Background player | Música/pearls separado | No equivalente |

## Mapeo canal CC → WebSocket → frontend

```mermaid
flowchart LR
  subgraph backend
    SPOT[Spotter alert]
    ENG[Engineer message]
    LLM[advice_end PTT]
  end
  subgraph ws
    A[event=alert]
    C[event=commentary_end]
    D[event=advice_end]
  end
  subgraph fe
    AV[alertVoice filter]
    PAQ[priorityAudioQueue]
    TTS[/tts API]
  end
  SPOT --> A --> AV --> PAQ
  ENG --> C --> PAQ
  LLM --> D --> PAQ
  PAQ --> TTS
```

### CC-parity target routing

| Origen CC | Vantare objetivo | Hoy |
|-----------|------------------|-----|
| Spotter IMPORTANT | `alert` IMMEDIATE | ✓ |
| Engineer normal | **Mensaje individual NORMAL** | `commentary_end` batch ✗ |
| Engineer urgent | IMMEDIATE o HIGH alert | Parcial |
| PTT respuesta | NORMAL stream | `advice_*` ✓ (delta CC) |

## Prioridades (tabla práctica)

| Nivel | Ejemplos CC | Vantare TTS |
|-------|-------------|-------------|
| Crítico / immediate | Limiter, SC deploy, pit now penalty | IMMEDIATE, preempt |
| Alto | Damage major, FCY phase | IMMEDIATE o HIGH |
| Medio | Gap update, push | NORMAL (no batch futuro) |
| Bajo | DRS, pearls | NORMAL + verbosity / mute |

Frontend: `frontend/src/services/priorityAudioQueue.ts`

Filtros voz: `alertVoice.ts` — categorías sin voz (`gaps` UI-only por decisión alpha, CC tiene toggle).

## TTS vs WAV

| CC | Vantare |
|----|---------|
| WAV pregrabado por frase | TTS generado |
| Latencia ~0 ms disco | +200 ms–2 s API |
| Mismo texto por pack | `spotter_phrases_es.json` + plantillas ingeniero |

**Paridad:** mismo **texto semántico** (templates P0), no mismo archivo de audio.

## Preemption LLM (delta Vantare, alineado espíritu CC)

CC interrumpe TTS largo si llega spotter. Vantare:

- `advice_start` → `clearPendingNormalTts`
- IMMEDIATE durante stream LLM ✓

Ver `.omo/evidence/cc-audit-2026-06.md` #18–19.

## Archivos

| Capa | Archivo |
|------|---------|
| Backend mensajes | `models/messages.py` |
| Broadcast | `transport/broadcaster`, `websocket.py` |
| Frontend WS | `hooks/useWebSocket.ts` |
| Cola | `services/priorityAudioQueue.ts` |
| TTS | `services/ttsCache.ts`, backend `tts_service.py` |
| Duck | Tauri `duck_lmu` |

## Verificación

- `scripts/verify_audio_pipeline.py`
- `backend/tests/test_preemption*.py`
- `frontend` audio trigger matrix fixtures

## Deuda paridad

1. **Expiry 2 s** — no reproducir alert si cola retrasada (LMU-02).
2. **No batch `commentary_end`** para mensajes CC-individual.
3. **Saturación TTS** al entrar pista — CC no dispara 20 WAV a la vez; respetar cooldowns Events.

---

*Antes: `06-playback-tts.md` — renombrado con foco PlaybackModerator CC.*
