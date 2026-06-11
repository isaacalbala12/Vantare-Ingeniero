# v0.5 — Personalidades avanzadas Implementation Plan (Executor)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sincronizar Hub ↔ backend los ajustes de personalidad avanzada (sweary, verbosidad, proactividad, frecuencia de perlas) para que afecten prompts LLM, commentary batch, monitores proactivos y módulo CC de perlas.

**Architecture:** Extender `PersonalityPack` con runtime (`sweary`, `proactivity`, `pearl_frequency`); reutilizar `VerbosityController` existente (`silent|normal|detailed`); propagar vía `config_update` WS → `IntelligenceEngine.apply_runtime_config` → `game_state` session → módulos CC. Sin nuevo proceso ni LLM extra.

**Tech Stack:** Python 3.12, FastAPI WS, React Hub (ConfigTab), pytest, Vitest.

**Orquestador:** [`2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md`](2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md)  
**Spec base:** [`2026-06-11-roadmap-v05-personalities.md`](2026-06-11-roadmap-v05-personalities.md)

---

## Preconditions (obligatorio)

- [ ] **v0.4 GATE ✅** — usuario confirmó QA manual frases editables OK.
- [ ] **Commit v0.4** antes de empezar v0.5 (working tree tiene v0.4 + WIP v0.5 mezclado). Separar commits: `v0.4.0` primero, luego rama/commits v0.5.
- [ ] Leer [`docs/voice-contract.md`](../../voice-contract.md) — no romper I1–I5 de voz.

---

## Estado WIP (no reimplementar desde cero)

Ya existe código **sin commitear** (~70 % backend). **Auditar y completar**, no borrar salvo bug.

| Archivo | Hecho | Falta |
|---------|-------|-------|
| `backend/src/intelligence/personality_pack.py` | `PersonalityRuntime`, `apply_runtime`, `should_emit_proactive`, `tone_preview`, sweary en suffix | Tests |
| `backend/src/intelligence/pearls_of_wisdom.py` | `pearl_frequency` + `roll` en `on_event` | `import random` limpio; tests |
| `backend/src/intelligence/engine.py` | `apply_runtime_config`, snapshot, gate proactivo, `_emit_pearl` | Verificar sync sweary al arrancar |
| `backend/src/intelligence/commentary_orchestrator.py` | Gate `should_emit_proactive` en `enqueue` | Test |
| `backend/src/intelligence/crewchief_events/game_state.py` | Inyecta `sweary_messages`, `proactivity_level`, `pearl_frequency` | — |
| `backend/src/intelligence/crewchief_events/modules/pearls.py` | Lee `pearl_frequency`, early return si 0 | **Bug:** `_make_pearl` no pasa `pearl_frequency` a todos los calls (comeback/fast_lap/standard) |
| Frontend | — | **Todo:** schema, payload WS, Hub UI, tests |

---

## File map (v0.5)

| Acción | Path | Responsabilidad |
|--------|------|-----------------|
| Modify | `backend/src/intelligence/personality_pack.py` | Runtime personality + tono LLM |
| Modify | `backend/src/intelligence/pearls_of_wisdom.py` | Sampling por `pearl_frequency` |
| Modify | `backend/src/intelligence/crewchief_events/modules/pearls.py` | Pasar frequency a `PearlsService` |
| Modify | `backend/src/intelligence/engine.py` | Config apply + snapshot (ya parcial) |
| Modify | `backend/src/intelligence/commentary_orchestrator.py` | Gate proactividad (ya parcial) |
| Modify | `frontend/src/store/config.ts` | Nuevos campos config |
| Modify | `frontend/src/services/configUpdatePayload.ts` | Payload WS |
| Modify | `frontend/src/hooks/useWebSocket.ts` | Ack `config_ack` |
| Modify | `frontend/src/hub/forms/appConfigKeys.ts` | Keys válidas |
| Modify | `frontend/src/components/ConfigTab.tsx` | UI proactividad + perlas + preview |
| Create | `frontend/src/hub/sections/PersonalityPanel.tsx` | Panel reutilizable (opcional pero recomendado) |
| Modify | `backend/tests/test_personality_pack.py` | Tests v2 |
| Modify | `backend/tests/test_config_sync_ws.py` | Round-trip nuevos fields |
| Create | `backend/tests/test_pearls_frequency.py` | frequency 0 → sin perlas |
| Modify | `backend/tests/test_commentary_orchestrator.py` | Gate proactividad |
| Create | `frontend/src/__tests__/personalityConfig.test.ts` | Payload + preview helper |
| Modify | `CHANGELOG.md`, `backend/src/version.py`, `frontend/package.json` | Bump 0.5.0 al cierre |

### Forbidden (global orquestador)

- ❌ `shared-telemetry/**`
- ❌ Go / iRacing / Suite
- ❌ Refactor race_loop / voice_loop

---

## Invariantes GATE v0.5

| ID | Invariante | Verificación |
|----|------------|--------------|
| I1 | `config_ack` incluye `proactivityLevel`, `pearlFrequency`, `swearyMessages`, `personalityProfileId`, `verbosityLevel` | `test_config_sync_ws.py` |
| I2 | `sweary=False` → suffix sin “lenguaje coloquial” | `test_personality_pack.py` |
| I3 | `verbosity=silent` bloquea ingeniero proactivo (MEDIUM) pero no CRITICAL | `test_verbosity_controller.py` (ya existe; no regresionar) |
| I4 | `proactivity=low` bloquea commentary LOW vía `should_emit_proactive` | `test_commentary_orchestrator.py` |
| I5 | `pearlFrequency=0` → 0 perlas en 100 intentos deterministas | `test_pearls_frequency.py` |

---

### Task 0: Pre-flight y baseline

**Files:** repo root

- [ ] **Step 1: Ver estado git**

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero
git status --short
```

- [ ] **Step 2: Commit v0.4 si aún no está en remoto** (solo si el usuario lo pidió; si no, continuar en WIP pero documentar en commit message).

- [ ] **Step 3: Baseline tests backend personalidad**

```powershell
cd backend
python -m pytest tests/test_personality_pack.py tests/test_verbosity_controller.py tests/test_config_sync_ws.py -q --tb=short
```

Expected: PASS (tests actuales; pueden fallar tras cambios — anotar).

- [ ] **Step 4: Commit checkpoint**

```bash
git add -A
git commit -m "chore: v0.5 WIP baseline before personality executor tasks"
```

(Solo si el usuario autorizó commit; si no, skip.)

---

### Task 1: Tests PersonalityPack v2

**Files:**
- Modify: `backend/tests/test_personality_pack.py`
- Modify: `backend/src/intelligence/personality_pack.py` (solo si tests fallan)

- [ ] **Step 1: Añadir tests**

```python
# backend/tests/test_personality_pack.py — añadir al final

def test_sweary_profile_injects_tone_suffix():
    pack = PersonalityPack(profile_id="aggressive", sweary=True)
    suffix = pack.engineer_system_suffix().lower()
    assert pack.sweary_enabled is True
    assert "lenguaje coloquial" in suffix or "paddock" in suffix


def test_sweary_off_no_colloquial_suffix():
    pack = PersonalityPack(profile_id="standard", sweary=False)
    suffix = pack.engineer_system_suffix().lower()
    assert "lenguaje coloquial" not in suffix


def test_proactivity_low_blocks_low_priority():
    pack = PersonalityPack(proactivity="low")
    assert pack.should_emit_proactive("CRITICAL") is True
    assert pack.should_emit_proactive("HIGH") is True
    assert pack.should_emit_proactive("MEDIUM") is False
    assert pack.should_emit_proactive("LOW") is False


def test_proactivity_high_allows_low():
    pack = PersonalityPack(proactivity="high")
    assert pack.should_emit_proactive("LOW") is True


def test_pearl_frequency_clamped():
    pack = PersonalityPack(pearl_frequency=2.5)
    assert pack.pearl_frequency == 1.0
    pack.apply_runtime(pearl_frequency=-0.1)
    assert pack.pearl_frequency == 0.0
```

- [ ] **Step 2: Run tests**

```powershell
cd backend
python -m pytest tests/test_personality_pack.py -v
```

Expected: PASS (WIP ya implementa la lógica).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_personality_pack.py
git commit -m "test: personality pack v2 sweary proactivity pearl frequency"
```

---

### Task 2: Fix CC Pearls module (pearl_frequency wiring)

**Files:**
- Modify: `backend/src/intelligence/crewchief_events/modules/pearls.py`

- [ ] **Step 1: Test CC pearls pasa frequency**

Crear `backend/tests/test_pearls_cc_module.py`:

```python
from src.intelligence.crewchief_events.modules.pearls import PearlsEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def _ctx(session_overrides=None):
    session = {
        "verbosity_level": "detailed",
        "sweary_messages": False,
        "pearl_frequency": 0.0,
    }
    if session_overrides:
        session.update(session_overrides)
    return CrewChiefFrameContext(
        previous=None,
        current={"standing_position": 5, "lap_number": 1},
        strategy={},
        session=session,
        now_monotonic=0.0,
    )


def test_pearls_module_respects_zero_frequency():
    mod = PearlsEvent()
    assert mod.evaluate(_ctx()) == []
```

- [ ] **Step 2: Run test — debe fallar si comeback path ignora frequency**

```powershell
python -m pytest tests/test_pearls_cc_module.py -v
```

- [ ] **Step 3: Fix `_make_pearl` y todos los call sites**

Reemplazar en `pearls.py`:

```python
    def _make_pearl(
        self,
        pearl_type: PearlType,
        sweary: bool,
        max_pearls: int,
        pearl_frequency: float,
        *,
        roll: float | None = None,
    ) -> CrewChiefMessage | None:
        text = self._pearls.on_event(
            pearl_type,
            sweary=sweary,
            max_per_race=max_pearls,
            pearl_frequency=pearl_frequency,
            roll=roll,
        )
        if not text:
            return None
        event_id = f"pearl_{pearl_type.value}"
        return CrewChiefMessage(
            event_id=event_id,
            text=render_template(event_id, {"message": text}),
            priority=CrewChiefPriority.LOW,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=12000,
        )
```

Y en `evaluate`, **todos** los calls:

```python
if msg := self._make_pearl(PearlType.OVERTAKE, sweary, max_pearls, pearl_freq):
```

(idem COMEBACK, FAST_LAP, STANDARD)

- [ ] **Step 4: Re-run tests — PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/intelligence/crewchief_events/modules/pearls.py backend/tests/test_pearls_cc_module.py
git commit -m "fix: CC pearls module honors pearl_frequency on all event types"
```

---

### Task 3: PearlsService frequency 0 (100 rolls)

**Files:**
- Modify: `backend/src/intelligence/pearls_of_wisdom.py`
- Create: `backend/tests/test_pearls_frequency.py`

- [ ] **Step 1: Test determinista**

```python
# backend/tests/test_pearls_frequency.py
from src.intelligence.pearls_of_wisdom import PearlType, PearlsService


def test_pearl_frequency_zero_never_emits():
    svc = PearlsService()
    for _ in range(100):
        assert svc.on_event(PearlType.STANDARD, pearl_frequency=0.0, roll=0.0) is None


def test_pearl_frequency_one_always_emits_when_under_cap():
    svc = PearlsService()
    msg = svc.on_event(PearlType.STANDARD, pearl_frequency=1.0, roll=0.0)
    assert msg
```

- [ ] **Step 2: Run — PASS** (WIP ya implementado; si falla, arreglar `pearls_of_wisdom.py`).

- [ ] **Step 3: Limpieza opcional en `pearls_of_wisdom.py`**

Cambiar `__import__("random").random()` por `import random` al tope y `random.random()`.

- [ ] **Step 4: Commit**

```bash
git add backend/src/intelligence/pearls_of_wisdom.py backend/tests/test_pearls_frequency.py
git commit -m "test: pearl frequency zero blocks all pearls"
```

---

### Task 4: Config sync WS (I1)

**Files:**
- Modify: `backend/tests/test_config_sync_ws.py`
- Modify: `backend/src/intelligence/engine.py` (solo si snapshot incompleto)

- [ ] **Step 1: Extender test**

```python
def test_config_payload_includes_personality_v2_fields():
    eng = IntelligenceEngine(broadcast_callback=lambda m: None)
    cfg = {
        "personalityProfileId": "aggressive",
        "verbosityLevel": "silent",
        "swearyMessages": True,
        "proactivityLevel": "low",
        "pearlFrequency": 0.25,
    }
    eng.apply_runtime_config(cfg)
    snap = eng.runtime_config_snapshot()
    assert snap["personalityProfileId"] == "aggressive"
    assert snap["verbosityLevel"] == "silent"
    assert snap["swearyMessages"] is True
    assert snap["proactivityLevel"] == "low"
    assert snap["pearlFrequency"] == 0.25
    assert eng.personality.sweary_enabled is True
```

- [ ] **Step 2: Run**

```powershell
python -m pytest tests/test_config_sync_ws.py -v
```

Expected: PASS (snapshot WIP ya incluye campos en `engine.py` L703–704).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_config_sync_ws.py
git commit -m "test: config_ack round-trip personality v2 fields"
```

---

### Task 5: Commentary orchestrator proactivity gate

**Files:**
- Modify: `backend/tests/test_commentary_orchestrator.py` (crear si no existe)

- [ ] **Step 1: Test**

```python
import pytest
from src.intelligence.commentary_orchestrator import CommentaryOrchestrator
from src.intelligence.personality_pack import PersonalityPack
from src.intelligence.verbosity_controller import VerbosityController


def test_commentary_blocked_when_proactivity_low_and_priority_low():
    orch = CommentaryOrchestrator(
        verbosity=VerbosityController("detailed"),
        personality=PersonalityPack(proactivity="low"),
    )
    ok = orch.enqueue("fuel_low", "Gasolina baja", priority="LOW")
    assert ok is False
    assert orch.pending_count() == 0


def test_commentary_allowed_when_proactivity_high():
    orch = CommentaryOrchestrator(
        verbosity=VerbosityController("detailed"),
        personality=PersonalityPack(proactivity="high"),
    )
    ok = orch.enqueue("fuel_low", "Gasolina baja", priority="LOW")
    assert ok is True
```

- [ ] **Step 2: Run — PASS** (gate ya en `commentary_orchestrator.py` L78–80).

- [ ] **Step 3: Commit**

---

### Task 6: Frontend schema + payload WS

**Files:**
- Modify: `frontend/src/store/config.ts`
- Modify: `frontend/src/services/configUpdatePayload.ts`
- Modify: `frontend/src/hub/forms/appConfigKeys.ts`
- Modify: `frontend/src/hooks/useWebSocket.ts`

- [ ] **Step 1: Extender `AppConfig` en `config.ts`**

```typescript
proactivityLevel: "low" | "normal" | "high";
pearlFrequency: number; // 0.0 – 1.0 en store; UI puede mostrar 0–100 %
```

Defaults en `defaultConfig`:

```typescript
proactivityLevel: "normal",
pearlFrequency: 0.5,
```

En migración/load (`loadConfigFromStorage` o equivalente):

```typescript
proactivityLevel: parsed.proactivityLevel ?? "normal",
pearlFrequency: typeof parsed.pearlFrequency === "number" ? parsed.pearlFrequency : 0.5,
```

- [ ] **Step 2: `configUpdatePayload.ts`**

```typescript
proactivityLevel: cfg.proactivityLevel ?? "normal",
pearlFrequency: cfg.pearlFrequency ?? 0.5,
```

- [ ] **Step 3: `appConfigKeys.ts`** — añadir `"proactivityLevel"`, `"pearlFrequency"`.

- [ ] **Step 4: `useWebSocket.ts`** — en handler `config_ack`, parchear:

```typescript
if (typeof ackCfg.proactivityLevel === "string") {
  patch.proactivityLevel = ackCfg.proactivityLevel;
}
if (typeof ackCfg.pearlFrequency === "number") {
  patch.pearlFrequency = ackCfg.pearlFrequency;
}
```

- [ ] **Step 5: Vitest**

Crear `frontend/src/__tests__/personalityConfig.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { buildConfigUpdatePayload } from "../services/configUpdatePayload";

describe("personality config payload", () => {
  it("includes proactivityLevel and pearlFrequency", () => {
    const p = buildConfigUpdatePayload({
      proactivityLevel: "low",
      pearlFrequency: 0.3,
    } as any);
    expect(p.proactivityLevel).toBe("low");
    expect(p.pearlFrequency).toBe(0.3);
  });
});
```

```powershell
cd frontend
npm test -- personalityConfig --run
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/store/config.ts frontend/src/services/configUpdatePayload.ts frontend/src/hub/forms/appConfigKeys.ts frontend/src/hooks/useWebSocket.ts frontend/src/__tests__/personalityConfig.test.ts
git commit -m "feat(frontend): config schema and WS payload for personality v2"
```

---

### Task 7: Hub UI — Personalidad avanzada

**Files:**
- Modify: `frontend/src/components/ConfigTab.tsx`
- Create (recomendado): `frontend/src/hub/sections/PersonalityPanel.tsx`

Ubicación: sección **Ingeniero** (`showIngeniero`), debajo de verbosidad existente.

- [ ] **Step 1: Helper preview (sin API)**

En `PersonalityPanel.tsx`:

```typescript
export function engineerTonePreview(
  profileId: "formal" | "standard" | "aggressive",
  sweary: boolean,
): string {
  const tones: Record<string, string> = {
    formal: "Tono profesional y preciso. Sin muletillas. Máximo 2 frases.",
    standard: "Tono de radio de boxes: directo, claro, motivador sin excesos.",
    aggressive: "Tono enérgico y exigente. Empuja al piloto. Máximo 2 frases contundentes.",
  };
  let text = tones[profileId] ?? tones.standard;
  if (sweary) {
    text += " Lenguaje coloquial de paddock permitido; evita prefijos robóticos tipo «Atención».";
  }
  return text;
}
```

- [ ] **Step 2: UI controls**

- `<select proactivityLevel>`: Baja / Normal / Alta (`low|normal|high`)
- `<input type="range" min={0} max={100}>` para perlas — guardar `pearlFrequency = value / 100`
- `<p className="text-[10px] text-a1-text-muted">` preview con `engineerTonePreview(personalityProfileId, swearyMessages)`

- [ ] **Step 3: Wire state en `ConfigTab.tsx`**

Añadir `proactivityLevel`, `pearlFrequency` a state local + `buildConfigPayload` + hydrate desde store.

- [ ] **Step 4: Test preview helper**

```typescript
import { engineerTonePreview } from "../hub/sections/PersonalityPanel";

it("preview adds sweary hint", () => {
  const t = engineerTonePreview("aggressive", true);
  expect(t.toLowerCase()).toContain("paddock");
});
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hub/sections/PersonalityPanel.tsx frontend/src/components/ConfigTab.tsx frontend/src/__tests__/personalityConfig.test.ts
git commit -m "feat(hub): personality proactivity pearl slider and tone preview"
```

---

### Task 8: Engine init sync sweary → personality

**Files:**
- Modify: `backend/src/intelligence/engine.py`
- Modify: `backend/src/main.py` (si arranque no sincroniza)

- [ ] **Step 1: Tras crear `PersonalityPack()` en engine `__init__`, llamar:**

```python
self.personality.apply_runtime(sweary=self.sweary_messages)
```

- [ ] **Step 2: En `main.py` lifespan, después de asignar `sweary_messages` desde settings:**

```python
intelligence_engine.personality.apply_runtime(sweary=intelligence_engine.sweary_messages)
```

- [ ] **Step 3: Run subset**

```powershell
python -m pytest tests/test_personality_pack.py tests/test_config_sync_ws.py -q
```

- [ ] **Step 4: Commit**

---

### Task 9: Release GATE v0.5.0

**Files:**
- Modify: `backend/src/version.py` → `0.5.0`
- Modify: `frontend/package.json` → `0.5.0`
- Modify: `backend/pyproject.toml` → `0.5.0`
- Modify: `CHANGELOG.md`, `README.md`

- [ ] **Step 1: Suite backend personalidad**

```powershell
cd backend
python -m pytest tests/test_personality_pack.py tests/test_pearls_frequency.py tests/test_pearls_cc_module.py tests/test_config_sync_ws.py tests/test_verbosity_controller.py tests/test_commentary_orchestrator.py -q
```

Expected: all PASS.

- [ ] **Step 2: Frontend**

```powershell
cd frontend
npm test -- personalityConfig --run
```

- [ ] **Step 3: Build desktop (opcional pre-release)**

```powershell
powershell -File scripts/build-desktop.ps1
```

- [ ] **Step 4: QA manual (5 min)**

1. Hub → Ingeniero → perfil **Agresivo** + **sweary** ON → preview muestra paddock.
2. Proactividad **Baja** + verbosidad **Detallada** → menos comentarios batch (LOW filtrados).
3. Perlas **0%** → no pearls en carrera (o casi ninguna).
4. Guardar → reiniciar app → valores persisten + `config_ack` refleja campos.

- [ ] **Step 5: Commit release docs**

```bash
git add CHANGELOG.md README.md backend/src/version.py frontend/package.json backend/pyproject.toml
git commit -m "chore: release v0.5.0 advanced personality settings"
```

(Tag/push solo si el usuario lo pide.)

---

## Comandos rápidos (executor)

```powershell
# Backend gate v0.5
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_personality_pack.py tests/test_pearls_frequency.py tests/test_pearls_cc_module.py tests/test_config_sync_ws.py tests/test_commentary_orchestrator.py -q

# Frontend
cd ..\frontend
npm test -- personalityConfig --run

# Dev loop (sin build)
cd ..
powershell -File scripts/dev-electron.ps1
```

---

## Self-review (plan vs spec v0.5)

| Requisito spec | Task |
|----------------|------|
| sweary en tono LLM | Task 1, 7 (preview), 8 |
| verbosidad | Ya existe; Task 4 no regresionar I3 |
| proactividad | Task 1, 4, 5, 6, 7 |
| pearl_frequency | Task 2, 3, 6, 7 |
| Hub UI | Task 7 |
| config WS round-trip | Task 4, 6 |
| Release 0.5 | Task 9 |

**Gap conocido fuera de scope v0.5:** caché TTS no precalienta todas las variantes/perfiles — no bloqueante GATE.

---

## Execution handoff

Plan guardado en `docs/superpowers/plans/2026-06-11-v05-personalities-EXECUTOR.md`.

**Opciones de ejecución:**

1. **Subagent-Driven (recomendado)** — un subagente por Task (0→9), revisión entre tasks. Skill: `superpowers:subagent-driven-development`.

2. **Inline en otra terminal** — pegar este plan al executor y seguir tasks en orden con skill `superpowers:executing-plans`; checkpoint tras Task 4 y Task 7.

¿Cuál prefieres?
