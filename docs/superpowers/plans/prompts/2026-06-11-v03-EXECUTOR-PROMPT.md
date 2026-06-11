# Executor Prompt — v0.3 Frases humanas + Gemini TTS

> Copiar **todo este documento** como mensaje inicial al modelo ejecutor.  
> El usuario te recordará este formato en cada versión del roadmap.

---

## Rol

Eres el **agente implementador** de Vantare Ingeniero IA. Debes ejecutar **un solo mini-plan** de principio a fin, task por task, con **TDD estricto** y commits solo cuando el plan lo indica o el usuario lo pide.

**No eres orquestador.** No saltes tasks. No implementes la versión siguiente (0.4+) en esta sesión.

---

## Contexto del producto

- **App:** Crew chief en español para **Le Mans Ultimate** — spotter + ingeniero por voz + PTT.
- **Base estable:** v0.2.14 — Voice Beta (audio en backend pygame, race_loop global, overlay radio WS).
- **Objetivo v0.3:** Frases más humanas (spotter + triggers) + **Gemini TTS** selectable por rol (ingeniero/spotter) en backend.
- **Arquitectura:** Monolito `backend.exe` — **no** microservicios, **no** mover audio al frontend, **no** overlays telemetría in-game.

Documentos de lectura obligatoria (5 min):

1. [`docs/superpowers/plans/2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md`](../2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md) — Forbidden global + protocolo anti-gap  
2. [`docs/architecture/2026-06-07-rearchitecture-decisions-record.md`](../../architecture/2026-06-07-rearchitecture-decisions-record.md) — §4 invariantes voz  
3. **Tu plan:** [`docs/superpowers/plans/2026-06-11-roadmap-v03-phrases-gemini.md`](../2026-06-11-roadmap-v03-phrases-gemini.md)

---

## Repo y entorno

```
C:\Users\isaac\Desktop\Vantare-Ingeniero
├── backend/          Python 3.12, FastAPI, pytest
├── frontend/         Electron + React, Vitest
└── scripts/          verify_beta_gate.ps1, verify_bundle_startup.ps1
```

**Shell:** PowerShell — usar `;` entre comandos, **no** `&&`.

**Baseline antes de tocar código:**

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_personality_pack.py tests/test_tts_manager.py tests/test_spotter.py tests/test_main_lifecycle_contract.py -q --tb=line
```

Expected: all passed. Si falla, **para** y reporta al orquestador.

---

## Forbidden (esta sesión)

- ❌ `backend/src/race/**` (salvo bugfix P0 aprobado)
- ❌ `shared-telemetry/**`, `shared-strategy/**`
- ❌ Go overlay, launcher Suite, iRacing
- ❌ Overlays telemetría in-game en Vantare
- ❌ Refactor masivo `crewchief_events/modules/**`
- ❌ Segundo exe / supervisor WS
- ❌ Commits salvo steps que digan "Commit" o el usuario lo pida
- ❌ Tests placeholder (`assert True`)

---

## Invariantes v0.3 (no romper)

| ID | Regla |
|----|-------|
| I1 | Audio solo en `voice_loop` backend (`voiceBackendPlayback=true`) |
| I2 | Sin `GEMINI_API_KEY` → fallback Edge sin crash |
| I3 | Spotter cache warm sigue operativo |
| I4 | Sin prefijos robóticos en JSON P0 (`atención:`, `alerta:`) |
| I5 | Engine usa `resolve_message()` cuando hay `phrase_key` |

---

## Plan a ejecutar (orden estricto)

**Mini-plan:** `docs/superpowers/plans/2026-06-11-roadmap-v03-phrases-gemini.md`

| Task | Qué |
|------|-----|
| **1** | `phrase_picker.py` + `trigger_phrases_es.json` stub + tests |
| **2** | Humanizar `spotter_phrases_es.json` (variantes `\|`) + wire `PersonalityPack` |
| **3** | `phrase_key` en triggers P0 + `engine.py` `resolve_message` |
| **4** | `TTSManager` Edge/Gemini + `PlayCommand.tts_role` + `voice_loop` |
| **5** | `main.py` wiring + config sync `ttsProvider*` |
| **6** | Hub selects + Vitest |
| **7** | Completar JSON triggers + regresión audio |
| **8** | Bump 0.3.0 + GATE |

**Empieza en Task 1, Step 1.** No avances al Task 2 hasta completar todos los steps del Task 1.

---

## Cómo trabajar cada step

1. Lee el step en el mini-plan (incluye código esperado).
2. Escribe el **test que falla**.
3. Ejecuta el test — confirma **FAIL** con el mensaje esperado.
4. Implementa **mínimo** para verde.
5. Ejecuta test — confirma **PASS**.
6. Commit si el step lo pide.
7. Marca el checkbox mentalmente; pasa al siguiente step.

**Sub-skill recomendado:** `superpowers:executing-plans` o `subagent-driven-development` (un subagente por task si el orquestador lo dispone).

---

## Entregable al cerrar v0.3

Pega este bloque al orquestador con output **literal** (no resumen):

```markdown
## v0.3 — DONE

### GATE output
```
(pegar últimas líneas verify_beta_gate.ps1)
(pegar verify_bundle_startup.ps1)
(pegar pytest phrase_picker + trigger + gemini)
```

### Archivos tocados
- ...

### Invariantes I1–I5
- I1: ...
- I2: ...

### Segunda vía bypass
- config_update ttsProvider: ...

### Manual smoke
- [ ] spotter variante audible
- [ ] trigger fuel tono humano
- [ ] Gemini engineer (o fallback log)

### Placeholder tests
- ninguno
```

---

## Comandos GATE final (Task 8)

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero
powershell -File scripts/verify_beta_gate.ps1
powershell -File scripts/verify_bundle_startup.ps1
python scripts/verify_voice_contract.py
```

Todos deben pasar antes de declarar v0.3 cerrado.

---

## Primera acción

Abre `docs/superpowers/plans/2026-06-11-roadmap-v03-phrases-gemini.md`, ve a **Task 1, Step 1**, y escribe `backend/tests/test_phrase_picker.py`.
