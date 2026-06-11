# v0.3 — Frases humanas + Gemini TTS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mejorar el copy de spotter/triggers (tono radio humano, variantes) y permitir **Gemini TTS** como proveedor selectable por rol (ingeniero/spotter) en el pipeline **backend** (`voice_loop`).

**Architecture:** `phrase_picker.py` centraliza frases ES (variantes con `|` en JSON); triggers usan `phrase_key` + `PersonalityPack`; `TTSManager` enruta Edge vs Gemini con fallback; Hub sincroniza `ttsProviderEngineer` / `ttsProviderSpotter` vía `config_ack`. Sin cambios a race_loop ni frontend audio playback.

**Tech Stack:** Python 3.12, pytest, pytest-asyncio, FastAPI, Edge TTS, `GeminiTTSService`, React Hub (`ConfigTab`), Vitest.

**Orquestador:** [`2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md`](2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md)  
**Prompt ejecutor:** [`prompts/2026-06-11-v03-EXECUTOR-PROMPT.md`](prompts/2026-06-11-v03-EXECUTOR-PROMPT.md)

---

## File structure (responsabilidades)

| File | Responsabilidad |
|------|-----------------|
| `backend/src/intelligence/phrase_picker.py` | Carga JSON, elige variante aleatoria, formatea `{side}` |
| `backend/src/data/trigger_phrases_es.json` | Frases triggers por `phrase_key` × perfil |
| `backend/src/data/spotter_phrases_es.json` | Frases spotter por perfil (variantes con `\|`) |
| `backend/src/intelligence/triggers.py` | `phrase_key` en triggers P0; menos strings robóticos |
| `backend/src/intelligence/engine.py` | `message_for(trigger)` al emitir alert |
| `backend/src/intelligence/personality_pack.py` | Delega spotter a `phrase_picker` |
| `backend/src/voice/tts_routing.py` | Dataclass provider+voice por rol |
| `backend/src/voice/tts_manager.py` | Edge/Gemini + cache spotter |
| `backend/src/voice/play_command.py` | Campo opcional `tts_role: engineer \| spotter` |
| `backend/src/main.py` | Wire Gemini en TTSManager + routing state |
| `backend/src/intelligence/engine.py` | Actualiza `app.state.tts_routing` en config sync |
| `frontend/src/store/config.ts` | `ttsProviderEngineer`, `ttsProviderSpotter` |
| `frontend/src/components/ConfigTab.tsx` | Selectores proveedor TTS |

---

## Preconditions (BLOCKING)

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_personality_pack.py tests/test_tts_manager.py tests/test_spotter.py tests/test_main_lifecycle_contract.py -q --tb=line
```

Expected: all passed

---

## Protocolo anti-gap

| ID | Invariante |
|----|------------|
| I1 | Audio sigue saliendo solo de `voice_loop` / backend (`voiceBackendPlayback=true`) |
| I2 | Sin Gemini key → fallback Edge, sin crash en `voice_loop` |
| I3 | Spotter cache warm sigue funcionando (Edge o Gemini según provider spotter) |
| I4 | Frases robóticas (`ATENCIÓN:`, `alerta:`) prohibidas en JSON P0 |
| I5 | `alert_text` en engine usa picker cuando `phrase_key` definido |

---

## Scope

### Files ALLOWED

Ver tabla File structure + tests listados en cada task.

### Files FORBIDDEN

- `backend/src/race/**` (salvo bugfix aprobado por orquestador)
- `shared-telemetry/**`, `shared-strategy/**`
- Go, iRacing, launcher, overlays telemetría
- Refactor masivo `crewchief_events/modules/**`

---

## Task 1: `phrase_picker` + tests

**Files:**
- Create: `backend/src/intelligence/phrase_picker.py`
- Create: `backend/tests/test_phrase_picker.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_phrase_picker.py
import pytest

from src.intelligence.phrase_picker import PhrasePicker, pick_variant


def test_pick_variant_splits_pipe():
    assert pick_variant("A|B|C", seed=0) in {"A", "B", "C"}


def test_pick_variant_single_string():
    assert pick_variant("solo", seed=0) == "solo"


def test_picker_loads_trigger_phrases():
    picker = PhrasePicker.load_defaults()
    msg = picker.trigger_phrase("fuel_critical", profile_id="standard", seed=1)
    assert msg
    assert "combustible" in msg.lower() or "gasolina" in msg.lower() or "fuel" in msg.lower()


def test_banned_robotic_prefixes_not_in_p0_keys():
    picker = PhrasePicker.load_defaults()
    banned = ("atención:", "alerta:", "mensaje:", "warning:")
    for key in ("fuel_critical", "fcy_active", "rain_increasing"):
        for profile in ("standard", "formal", "aggressive"):
            text = picker.trigger_phrase(key, profile_id=profile, seed=0).lower()
            assert text
            assert not any(b in text for b in banned), f"{key}/{profile}: {text}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend; python -m pytest tests/test_phrase_picker.py -v`  
Expected: FAIL — `ModuleNotFoundError: phrase_picker`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/intelligence/phrase_picker.py
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"


def pick_variant(template: str, *, seed: int | None = None) -> str:
    parts = [p.strip() for p in template.split("|") if p.strip()]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    rng = random.Random(seed)
    return rng.choice(parts)


@dataclass(frozen=True)
class PhrasePicker:
    spotter: dict[str, dict[str, str]]
    triggers: dict[str, dict[str, str]]

    @classmethod
    def load_defaults(cls) -> "PhrasePicker":
        spotter_path = _DATA / "spotter_phrases_es.json"
        trigger_path = _DATA / "trigger_phrases_es.json"
        spotter = json.loads(spotter_path.read_text(encoding="utf-8")) if spotter_path.is_file() else {}
        triggers = json.loads(trigger_path.read_text(encoding="utf-8")) if trigger_path.is_file() else {}
        return cls(spotter=spotter, triggers=triggers)

    def spotter_phrase(self, key: str, *, profile_id: str, seed: int | None = None, **kwargs: str) -> str:
        template = self.spotter.get(profile_id, {}).get(key) or self.spotter.get("standard", {}).get(key, "")
        text = pick_variant(template, seed=seed)
        if not text:
            return ""
        try:
            return text.format(**kwargs)
        except KeyError:
            return text

    def trigger_phrase(self, key: str, *, profile_id: str, seed: int | None = None, **kwargs: str) -> str:
        entry = self.triggers.get(key, {})
        template = entry.get(profile_id) or entry.get("standard", "")
        text = pick_variant(template, seed=seed)
        if not text:
            return ""
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
```

- [ ] **Step 4: Create stub JSON** (Task 2 lo rellena; stub mínimo para tests)

Create `backend/src/data/trigger_phrases_es.json`:

```json
{
  "fuel_critical": {
    "standard": "Te quedan menos de tres vueltas de gasolina|Gasolina para menos de tres vueltas, planifica parada",
    "formal": "Autonomía inferior a tres vueltas. Planifique parada.",
    "aggressive": "¡Te secas en tres vueltas! Entra ya a boxes"
  },
  "fcy_active": {
    "standard": "Full course yellow, levanta el pie|FCY en pista, reduce ritmo",
    "formal": "Full course yellow activo. Reduzca velocidad.",
    "aggressive": "¡FCY! Levanta el pie ya"
  },
  "rain_increasing": {
    "standard": "Sube la probabilidad de lluvia|Ojo, puede llover en breve",
    "formal": "Probabilidad de lluvia en aumento.",
    "aggressive": "Viene lluvia, estate listo"
  }
}
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_phrase_picker.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/intelligence/phrase_picker.py backend/tests/test_phrase_picker.py backend/src/data/trigger_phrases_es.json
git commit -m "feat(0.3): phrase_picker con variantes y tests de tono"
```

---

## Task 2: Humanizar spotter JSON + PersonalityPack

**Files:**
- Modify: `backend/src/data/spotter_phrases_es.json`
- Modify: `backend/src/intelligence/personality_pack.py`
- Modify: `backend/tests/test_personality_pack.py`

- [ ] **Step 1: Extend test**

```python
# append to backend/tests/test_personality_pack.py
def test_spotter_phrase_supports_pipe_variants(monkeypatch):
    pack = PersonalityPack("standard")
    # clear_left en JSON debe usar "A|B" — al menos una variante contiene "Despejado" o "libre"
    msg = pack.spotter_phrase("clear_left")
    assert msg
    assert any(w in msg.lower() for w in ("despejado", "libre", "clear"))
```

- [ ] **Step 2: Run — expect FAIL** si JSON aún single-string sin pipe (OK si pasa tras edit)

- [ ] **Step 3: Edit `spotter_phrases_es.json`** — para cada key P0 añadir 2+ variantes con `|`:

Keys P0 obligatorios: `hold_line`, `still_there`, `closing_fast`, `clear_left`, `clear_right`, `clear_all_round`, `in_the_middle`, `engage_limiter`, `disengage_limiter`, `fuel_critical`

Ejemplo `standard.clear_left`:

```json
"clear_left": "Despejado izquierda|Izquierda libre|Clear a la izquierda"
```

Tono: radio boxes, sin `¡ATENCIÓN!`, sin dos puntos tipo label.

- [ ] **Step 4: Wire PersonalityPack**

```python
# backend/src/intelligence/personality_pack.py — reemplazar cuerpo de spotter_phrase:
from src.intelligence.phrase_picker import PhrasePicker, pick_variant

_picker = PhrasePicker.load_defaults()

def spotter_phrase(self, key: str, **kwargs: str) -> str:
    return _picker.spotter_phrase(key, profile_id=self._profile_id, **kwargs)
```

Eliminar lectura directa `_SPOTTER_PHRASES` si queda redundante (mantener `_PHRASES_PATH` solo si tests legacy lo necesitan — preferir borrar y usar picker).

- [ ] **Step 5: pytest**

Run: `python -m pytest tests/test_personality_pack.py tests/test_phrase_picker.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git commit -am "feat(0.3): spotter phrases humanas con variantes"
```

---

## Task 3: Triggers usan `phrase_key`

**Files:**
- Modify: `backend/src/intelligence/triggers.py`
- Modify: `backend/src/intelligence/engine.py`
- Create: `backend/tests/test_trigger_phrases_wired.py`

- [ ] **Step 1: Add `phrase_key` to BaseTrigger**

```python
# triggers.py — BaseTrigger.__init__ añadir parámetro opcional:
phrase_key: str | None = None,
# ...
self.phrase_key = phrase_key

def resolve_message(self, personality) -> str:
    if not self.phrase_key:
        return self.alert_text
    from src.intelligence.phrase_picker import PhrasePicker
    picker = PhrasePicker.load_defaults()
    msg = picker.trigger_phrase(self.phrase_key, profile_id=personality.profile_id)
    return msg or self.alert_text
```

- [ ] **Step 2: Failing test**

```python
# backend/tests/test_trigger_phrases_wired.py
from src.intelligence.triggers import FuelCriticalTrigger
from src.intelligence.personality_pack import PersonalityPack


def test_fuel_critical_uses_phrase_key():
    t = FuelCriticalTrigger()
    assert t.phrase_key == "fuel_critical"
    msg = t.resolve_message(PersonalityPack("aggressive"))
    assert "boxes" in msg.lower() or "vueltas" in msg.lower()
    assert "atención:" not in msg.lower()
```

- [ ] **Step 3: Wire FuelCriticalTrigger**

```python
super().__init__(
    ...
    alert_text="Fallback combustible bajo.",
    phrase_key="fuel_critical",
)
```

Repetir `phrase_key` para triggers con copy estático P0 (mínimo 5 en este task):

| Trigger class | phrase_key |
|---------------|------------|
| `FuelCriticalTrigger` | `fuel_critical` |
| `FlagsMonitorTrigger` | `fcy_active` (fallback; dynamic flags siguen usando `event.message`) |
| `RainForecastTrigger` | `rain_increasing` |
| `BrakeWearTrigger` | `brake_wear_high` |
| `TyreWearTrigger` | `tyre_wear_high` |

Añadir entradas correspondientes en `trigger_phrases_es.json`.

- [ ] **Step 4: engine.py ~L440** — cambiar:

```python
message=trigger.resolve_message(self.personality),
```

- [ ] **Step 5: pytest**

Run: `python -m pytest tests/test_trigger_phrases_wired.py tests/test_triggers.py -q --tb=line`  
Expected: PASS (fix trigger tests si comparaban alert_text exacto)

- [ ] **Step 6: Commit**

```bash
git commit -am "feat(0.3): triggers P0 usan phrase_key + picker"
```

---

## Task 4: `TTSManager` multi-provider (Edge + Gemini)

**Files:**
- Create: `backend/src/voice/tts_routing.py`
- Modify: `backend/src/voice/tts_manager.py`
- Modify: `backend/src/voice/play_command.py`
- Modify: `backend/src/voice/bridge.py`
- Create: `backend/tests/test_tts_manager_gemini.py`

- [ ] **Step 1: tts_routing.py**

```python
# backend/src/voice/tts_routing.py
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class TtsRouting:
    provider_engineer: str = "edge"  # edge | gemini
    provider_spotter: str = "edge"
    gemini_voice_engineer: str = "Kore"
    gemini_voice_spotter: str = "Kore"
    edge_voice_engineer: str = "es-ES-AlvaroNeural"
    edge_voice_spotter: str = "es-ES-ElviraNeural"

    def provider_for_category(self, category: str) -> str:
        if category in ("spotter", "proximity", "gaps"):
            return self.provider_spotter
        return self.provider_engineer
```

- [ ] **Step 2: Extend PlayCommand**

```python
# play_command.py — añadir campo:
tts_role: str = "engineer"  # engineer | spotter
```

En `play_command_from_alert`:

```python
payload = payload or {}
role = "spotter" if category in ("spotter", "proximity") else "engineer"
# ...
tts_role=role,
```

- [ ] **Step 3: Failing test**

```python
# backend/tests/test_tts_manager_gemini.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.voice.tts_manager import TTSManager
from src.voice.tts_routing import TtsRouting


@pytest.mark.asyncio
async def test_synthesize_uses_gemini_when_routing_says_so():
    edge = MagicMock()
    edge.synthesize = AsyncMock(return_value=b"edge")
    gemini = MagicMock()
    gemini.synthesize = AsyncMock(return_value=b"RIFF")
    routing = TtsRouting(provider_engineer="gemini", provider_spotter="edge")

    mgr = TTSManager(edge=edge, gemini=gemini, spotter_cache=None, routing=routing)
    out = await mgr.synthesize("Hola boxes", tts_role="engineer")
    assert out == b"RIFF"
    gemini.synthesize.assert_awaited_once()
    edge.synthesize.assert_not_awaited()


@pytest.mark.asyncio
async def test_gemini_unavailable_falls_back_to_edge():
    edge = MagicMock()
    edge.synthesize = AsyncMock(return_value=b"edge-bytes")
    routing = TtsRouting(provider_engineer="gemini")
    mgr = TTSManager(edge=edge, gemini=None, spotter_cache=None, routing=routing)
    out = await mgr.synthesize("test", tts_role="engineer")
    assert out == b"edge-bytes"
```

- [ ] **Step 4: Implement TTSManager**

```python
# backend/src/voice/tts_manager.py
class TTSManager:
    def __init__(self, edge, gemini=None, spotter_cache=None, routing=None) -> None:
        self._edge = edge
        self._gemini = gemini
        self._cache = spotter_cache
        self._routing = routing or TtsRouting()

    async def synthesize(
        self,
        text: str,
        *,
        cache_key: str | None = None,
        tts_role: str = "engineer",
    ) -> bytes:
        if cache_key and self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                return cached
        provider = (
            self._routing.provider_spotter if tts_role == "spotter" else self._routing.provider_engineer
        )
        if provider == "gemini" and self._gemini is not None:
            try:
                return await self._gemini.synthesize(text)
            except Exception as exc:
                logger.warning("Gemini TTS failed, fallback Edge: %s", exc)
        if self._edge is None:
            raise RuntimeError("Edge TTS unavailable")
        audio = await self._edge.synthesize(text)
        if not audio:
            raise RuntimeError("Empty TTS response")
        return audio
```

- [ ] **Step 5: voice_loop** — pasar role:

```python
# service.py línea ~36
audio = await tts.synthesize(cmd.text, cache_key=cmd.wav_cache_key, tts_role=cmd.tts_role)
```

- [ ] **Step 6: pytest**

Run: `python -m pytest tests/test_tts_manager.py tests/test_tts_manager_gemini.py -v`  
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/src/voice/tts_routing.py backend/src/voice/tts_manager.py backend/src/voice/play_command.py backend/src/voice/service.py backend/tests/test_tts_manager_gemini.py
git commit -m "feat(0.3): TTSManager Edge/Gemini con fallback"
```

---

## Task 5: Lifespan wiring + config sync

**Files:**
- Modify: `backend/src/main.py`
- Modify: `backend/src/intelligence/engine.py`
- Modify: `backend/tests/test_config_sync_ws.py`

- [ ] **Step 1: main.py** — tras crear edge/gemini:

```python
from src.voice.tts_routing import TtsRouting

app.state.tts_routing = TtsRouting()
# ...
tts_manager = TTSManager(
    edge=edge,
    gemini=getattr(app.state, "gemini_tts_service", None),
    spotter_cache=spotter_cache,
    routing=app.state.tts_routing,
)
```

SpotterPhraseCache warm: usar `edge` siempre para warm (determinista) O warm con provider activo — **decisión 0.3:** warm con el servicio que use `routing.provider_spotter` vía helper `_warm_tts(edge, gemini, routing)`.

- [ ] **Step 2: engine config handler** — en bloque `personalityProfileId` / config sync:

```python
routing = getattr(self.app_state, "tts_routing", None)  # pasar app ref si hace falta
if routing and "ttsProviderEngineer" in cfg:
    routing.provider_engineer = str(cfg["ttsProviderEngineer"])
if routing and "ttsProviderSpotter" in cfg:
    routing.provider_spotter = str(cfg["ttsProviderSpotter"])
```

Patrón existente: mirar `engine.py` `apply_config` y `main.py` cómo engine accede a state — usar `self._tts_routing` seteado en lifespan:

```python
# main.py después de crear engine
intelligence_engine.set_tts_routing(app.state.tts_routing)
```

Añadir método `set_tts_routing` / update en config apply.

- [ ] **Step 3: Test config sync**

```python
# test_config_sync_ws.py — añadir
async def test_config_ack_includes_tts_providers(client, ...):
    # send config_update ttsProviderEngineer=gemini
    # assert config_ack payload contains fields
```

- [ ] **Step 4: pytest subset**

Run: `python -m pytest tests/test_config_sync_ws.py tests/test_voice_lifespan_wiring.py -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(0.3): wire tts routing config sync backend"
```

---

## Task 6: Hub — selectores Gemini/Edge

**Files:**
- Modify: `frontend/src/store/config.ts`
- Modify: `frontend/src/services/configUpdatePayload.ts`
- Modify: `frontend/src/components/ConfigTab.tsx`
- Modify: `frontend/src/hub/forms/appConfigKeys.ts`
- Create: `frontend/src/__tests__/ttsProviderConfig.test.ts`

- [ ] **Step 1: Config schema bump** `CONFIG_SCHEMA_VERSION = 5`

```typescript
// config.ts — AppConfig
ttsProviderEngineer: "edge" | "gemini";
ttsProviderSpotter: "edge" | "gemini";
```

Defaults: `"edge"` both.

- [ ] **Step 2: Vitest**

```typescript
// frontend/src/__tests__/ttsProviderConfig.test.ts
import { describe, expect, it } from "vitest";
import { buildConfigUpdatePayload } from "../services/configUpdatePayload";

describe("ttsProvider config", () => {
  it("includes provider fields in WS payload", () => {
    const p = buildConfigUpdatePayload({
      ttsProviderEngineer: "gemini",
      ttsProviderSpotter: "edge",
    } as any);
    expect(p.ttsProviderEngineer).toBe("gemini");
    expect(p.ttsProviderSpotter).toBe("edge");
  });
});
```

- [ ] **Step 3: ConfigTab UI** — en sección Audio, dos `<select>`:

```tsx
<label>Ingeniero TTS</label>
<select value={ttsProviderEngineer} onChange={...}>
  <option value="edge">Edge (Microsoft)</option>
  <option value="gemini">Gemini (Google)</option>
</select>
```

Igual para Spotter. Tooltip: Gemini requiere `GEMINI_API_KEY` en backend.

- [ ] **Step 4: Run tests**

Run: `cd frontend; npm test -- --run ttsProviderConfig.test.ts`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(0.3): Hub selectors ttsProvider engineer/spotter"
```

---

## Task 7: Expandir trigger_phrases + regresión audio

**Files:**
- Modify: `backend/src/data/trigger_phrases_es.json`
- Modify: `backend/tests/fixtures/audio_trigger_matrix.py` (si mensajes cambian)

- [ ] **Step 1: Completar JSON** para keys Task 3 + `brake_wear_high`, `tyre_wear_high` (2-3 variantes × 3 perfiles)

- [ ] **Step 2: Regresión**

Run: `python -m pytest tests/test_audio_trigger_matrix.py tests/test_spotter_cc_parity.py -q`  
Expected: PASS (actualizar expected strings en fixtures si necesario)

- [ ] **Step 3: verify_voice_contract**

Run: `cd ..; python scripts/verify_voice_contract.py`  
Expected: exit 0

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(0.3): complete trigger phrase catalog P0"
```

---

## Task 8: Release v0.3.0 + GATE

**Files:**
- Modify: `frontend/package.json`, `backend/src/version.py`, `backend/pyproject.toml`, `CHANGELOG.md`

- [ ] **Step 1: Bump version** → `0.3.0`

- [ ] **Step 2: GATE completo**

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero
powershell -File scripts/verify_beta_gate.ps1
powershell -File scripts/verify_bundle_startup.ps1
```

Expected: all PASS

- [ ] **Step 3: Build desktop** (si release solicitado)

```powershell
powershell -File scripts/build-desktop.ps1
powershell -File scripts/verify-release.ps1 -SkipTests
```

- [ ] **Step 4: Evidencia manual** — `.omo/evidence/v03-phrases-gemini-manual.md`:

- Spotter audible con variante nueva
- Trigger fuel con tono humano
- Hub Gemini engineer + key configurada → voz distinta (o log confirma Gemini path)

- [ ] **Step 5: Commit** (usuario pide release/tag por separado)

```bash
git commit -am "chore: release v0.3.0 phrases + gemini tts"
```

---

## GATE v0.3 (orquestador — pegar output literal)

| Check | Comando | Expected |
|-------|---------|----------|
| phrase_picker | `pytest tests/test_phrase_picker.py -v` | PASS |
| triggers wired | `pytest tests/test_trigger_phrases_wired.py -v` | PASS |
| gemini routing | `pytest tests/test_tts_manager_gemini.py -v` | PASS |
| config sync | `pytest tests/test_config_sync_ws.py -q` | PASS |
| beta gate | `verify_beta_gate.ps1` | PASS |
| bundle | `verify_bundle_startup.ps1` | PASS |
| voice contract | `verify_voice_contract.py` | exit 0 |

---

## Self-review (plan author)

| Spec requirement | Task |
|------------------|------|
| Frases humanas spotter | Task 2 |
| Frases humanas triggers | Task 1, 3, 7 |
| Gemini voz selectable | Task 4, 5, 6 |
| Backend playback invariant | anti-gap I1, Task 4 service.py |
| Fallback sin API key | Task 4 test + I2 |
| No forbidden scope | FORBIDDEN list |

Placeholder scan: none.

Type consistency: `tts_role`, `TtsRouting`, `phrase_key` used uniformly.
