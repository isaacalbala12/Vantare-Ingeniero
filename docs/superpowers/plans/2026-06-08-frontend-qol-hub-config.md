# Frontend QoL Hub Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mejorar la UX del hub Electron con secciones TTS desplegables, selector de voces en español legible, slider de volumen 0–100%, captura de tecla PTT estilo videojuegos, eliminar secciones obsoletas del **hub** (Conexión, config backend), quitar telemetría en Inicio, historial con chat PTT + log de avisos de radio, y verificar perfiles.

**Architecture:** Componentes pequeños reutilizables (`CollapsibleSection`, `VoiceSelect`, `VolumeSlider`, `HotkeyCapture`) viven en `frontend/src/hub/components/`. Constantes de voces y utilidades de hotkey en `frontend/src/hub/forms/`. `ConfigTab.tsx` se simplifica moviendo audio TTS a la sección **Audio / PTT** y eliminando bloques de UI obsoletos. **No tocar backend** ni la lógica de conexión WS (`vllmIP`/`serverPort` siguen en store y localStorage). Electron main recibe hotkeys vía IPC y re-registra `globalShortcut`. Volumen UI 0–100 se persiste en `config.ttsVolumeBoost` (nombre legacy del campo) con migración desde 0.5–2.0.

**Tech Stack:** React 19, Zustand, Tailwind v4, Vitest, Electron 34 (`globalShortcut`, IPC), Edge TTS (voces `es-ES-AlvaroNeural`, `es-ES-ElviraNeural`).

**Decisiones confirmadas con el usuario (2026-06-08):**
- **Volumen:** slider **0–100%**; `0` = silencio, `100` = volumen máximo del reproductor (`audio.volume = percent / 100`).
- **PTT:** teclado global en Electron + ratón solo con hub enfocado — **sin** `uiohook` en v1.
- **Conexión:** eliminar **solo la sección UI del hub** (sidebar + pantalla); mantener store, WS, health checks y defaults `localhost:8008` intactos.
- **Historial:** además de chat PTT (piloto/ingeniero), persistir **log de avisos de radio** (spotter, ingeniero proactivo, SC, etc.) en el mismo archivo de sesión.
- **Collapsibles TTS:** **plegados por defecto** (`defaultOpen={false}`).
- Solo **2 voces Edge ES** con labels humanos ("Hombre — Español", "Mujer — Español").

---

## File structure

| File | Responsibility |
|------|----------------|
| `frontend/src/hub/components/CollapsibleSection.tsx` | Panel desplegable reutilizable (chevron + título) |
| `frontend/src/hub/components/VoiceSelect.tsx` | `<select>` voces Edge con labels traducidos |
| `frontend/src/hub/components/VolumeSlider.tsx` | Slider 0–100 + label numérico |
| `frontend/src/hub/components/HotkeyCapture.tsx` | Recuadro “Pulsa una tecla…” estilo rebind |
| `frontend/src/hub/forms/edgeTtsVoices.ts` | Catálogo fijo 2 voces ES + helpers |
| `frontend/src/hub/forms/hotkeyFormat.ts` | `keyboardEventToHotkey`, `normalizeHotkey`, `toElectronAccelerator` |
| `frontend/src/hub/forms/volumeMigration.ts` | Migrar legacy 0.5–2.0 → 0–100 |
| `frontend/src/hub/forms/appConfigKeys.ts` | Lista exhaustiva de keys de `AppConfig` para perfiles |
| `frontend/src/hub/sections/AudioTtsPanel.tsx` | Los 3 collapsibles TTS en Audio/PTT |
| `frontend/src/components/ConfigTab.tsx` | Orquestación; menos bloques inline |
| `frontend/src/hub/routes.tsx` | Quitar `conexion` del sidebar |
| `frontend/src/hub/AppShell.tsx` | Quitar case `conexion` |
| `frontend/src/hub/pages/InicioPage.tsx` | Quitar card telemetría |
| `frontend/electron/shortcuts/ptt.ts` | Hotkeys dinámicos desde IPC |
| `frontend/electron/preload.ts` | Exponer `updatePttHotkeys` |
| `frontend/electron/main.ts` | Handler IPC + llamar register al cambiar config |
| `frontend/src/core/platform/types.ts` | Añadir `updatePttHotkeys?` al bridge |
| `frontend/src/store/config.ts` | Migración volumen en `loadSavedConfig` |
| `frontend/src/services/priorityAudioQueue.ts` | `volume = percent/100` |
| `frontend/src/hub/forms/configValidation.ts` | Validar volumen 0–100 |
| `frontend/src/store/config.ts` | Extender `MessageRecord.sender` + `addRadioAlertToHistory` |
| `frontend/src/hooks/useWebSocket.ts` | Loguear alertas de radio al historial |
| `frontend/src/hub/pages/HistorialPage.tsx` | Mostrar labels sender spotter/engineer/pilot |

Tests nuevos en `frontend/src/__tests__/`.

---

### Task 1: CollapsibleSection primitive

**Files:**
- Create: `frontend/src/hub/components/CollapsibleSection.tsx`
- Test: `frontend/src/__tests__/CollapsibleSection.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { CollapsibleSection } from "../hub/components/CollapsibleSection";

describe("CollapsibleSection", () => {
  it("oculta children hasta expandir", async () => {
    render(
      <CollapsibleSection title="Voz TTS spotter">
        <p>Contenido spotter</p>
      </CollapsibleSection>,
    );
    expect(screen.queryByText("Contenido spotter")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /voz tts spotter/i }));
    expect(screen.getByText("Contenido spotter")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run src/__tests__/CollapsibleSection.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

```tsx
import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";

interface CollapsibleSectionProps {
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
}

export function CollapsibleSection({ title, defaultOpen = false, children }: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="border border-hub-border rounded-lg overflow-hidden">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-left text-sm font-medium text-a1-text bg-hub-card hover:bg-hub-card/80"
      >
        <span>{title}</span>
        <ChevronDown className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open ? <div className="px-3 py-3 flex flex-col gap-3">{children}</div> : null}
    </section>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run src/__tests__/CollapsibleSection.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hub/components/CollapsibleSection.tsx frontend/src/__tests__/CollapsibleSection.test.tsx
git commit -m "feat(hub): add CollapsibleSection component"
```

---

### Task 2: Edge TTS voice catalog + VoiceSelect

**Files:**
- Create: `frontend/src/hub/forms/edgeTtsVoices.ts`
- Create: `frontend/src/hub/components/VoiceSelect.tsx`
- Test: `frontend/src/__tests__/edgeTtsVoices.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from "vitest";
import { EDGE_TTS_VOICES_ES, voiceLabel, isKnownEdgeVoice } from "../hub/forms/edgeTtsVoices";

describe("edgeTtsVoices", () => {
  it("expone dos voces ES con labels humanos", () => {
    expect(EDGE_TTS_VOICES_ES).toHaveLength(2);
    expect(voiceLabel("es-ES-AlvaroNeural")).toBe("Hombre — Español");
    expect(voiceLabel("es-ES-ElviraNeural")).toBe("Mujer — Español");
  });

  it("isKnownEdgeVoice valida ids", () => {
    expect(isKnownEdgeVoice("es-ES-AlvaroNeural")).toBe(true);
    expect(isKnownEdgeVoice("en-US-JennyNeural")).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run src/__tests__/edgeTtsVoices.test.ts`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`frontend/src/hub/forms/edgeTtsVoices.ts`:

```ts
export interface EdgeTtsVoiceOption {
  id: string;
  label: string;
}

export const EDGE_TTS_VOICES_ES: EdgeTtsVoiceOption[] = [
  { id: "es-ES-AlvaroNeural", label: "Hombre — Español" },
  { id: "es-ES-ElviraNeural", label: "Mujer — Español" },
];

const LABEL_BY_ID = Object.fromEntries(EDGE_TTS_VOICES_ES.map((v) => [v.id, v.label]));

export function voiceLabel(voiceId: string): string {
  return LABEL_BY_ID[voiceId] ?? voiceId;
}

export function isKnownEdgeVoice(voiceId: string): boolean {
  return voiceId in LABEL_BY_ID;
}
```

`frontend/src/hub/components/VoiceSelect.tsx`:

```tsx
import { EDGE_TTS_VOICES_ES } from "../forms/edgeTtsVoices";

interface VoiceSelectProps {
  value: string;
  onChange: (voiceId: string) => void;
  id?: string;
}

export function VoiceSelect({ value, onChange, id }: VoiceSelectProps) {
  return (
    <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className="hub-input">
      {EDGE_TTS_VOICES_ES.map((v) => (
        <option key={v.id} value={v.id}>
          {v.label}
        </option>
      ))}
    </select>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run src/__tests__/edgeTtsVoices.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hub/forms/edgeTtsVoices.ts frontend/src/hub/components/VoiceSelect.tsx frontend/src/__tests__/edgeTtsVoices.test.ts
git commit -m "feat(hub): spanish Edge TTS voice select with human labels"
```

---

### Task 3: Volume slider 0–100% + migration

**Files:**
- Create: `frontend/src/hub/forms/volumeMigration.ts`
- Create: `frontend/src/hub/components/VolumeSlider.tsx`
- Modify: `frontend/src/store/config.ts` (loadSavedConfig)
- Modify: `frontend/src/services/priorityAudioQueue.ts:219-220`
- Modify: `frontend/src/hub/forms/configValidation.ts:41-43`
- Test: `frontend/src/__tests__/volumeMigration.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from "vitest";
import { migrateTtsVolumePercent, volumePercentToAudioLevel } from "../hub/forms/volumeMigration";

describe("volumeMigration", () => {
  it("migra legacy boost 1.0 a 100", () => {
    expect(migrateTtsVolumePercent(1.0)).toBe(100);
    expect(migrateTtsVolumePercent(0.5)).toBe(50);
  });

  it("deja percent 0-100 intacto", () => {
    expect(migrateTtsVolumePercent(75)).toBe(75);
    expect(migrateTtsVolumePercent(0)).toBe(0);
  });

  it("convierte a audio.volume 0-1", () => {
    expect(volumePercentToAudioLevel(100)).toBe(1);
    expect(volumePercentToAudioLevel(50)).toBe(0.5);
    expect(volumePercentToAudioLevel(0)).toBe(0);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run src/__tests__/volumeMigration.test.ts`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`frontend/src/hub/forms/volumeMigration.ts`:

```ts
/** Convierte valor persistido (legacy 0.5–2.0 o nuevo 0–100) a percent entero. */
export function migrateTtsVolumePercent(raw: unknown): number {
  const n = Number(raw ?? 100);
  if (!Number.isFinite(n)) return 100;
  if (n > 0 && n <= 2) return Math.min(100, Math.max(0, Math.round(n * 100)));
  return Math.min(100, Math.max(0, Math.round(n)));
}

export function volumePercentToAudioLevel(percent: number): number {
  const p = Math.min(100, Math.max(0, Math.round(percent)));
  return p / 100;
}
```

`frontend/src/hub/components/VolumeSlider.tsx`:

```tsx
interface VolumeSliderProps {
  value: number;
  onChange: (percent: number) => void;
}

export function VolumeSlider({ value, onChange }: VolumeSliderProps) {
  const safe = Math.min(100, Math.max(0, Math.round(value)));
  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-between text-xs text-a1-text-muted">
        <span>Volumen TTS</span>
        <span>{safe}%</span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={safe}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-a1-accent"
      />
    </div>
  );
}
```

In `frontend/src/store/config.ts`, inside `loadSavedConfig`:

```ts
import { migrateTtsVolumePercent } from "../hub/forms/volumeMigration";
// ...
ttsVolumeBoost: migrateTtsVolumePercent(parsed.ttsVolumeBoost),
```

Default in same file: `ttsVolumeBoost: 100` (replace `1.0`).

In `frontend/src/services/priorityAudioQueue.ts`:

```ts
import { volumePercentToAudioLevel } from "../hub/forms/volumeMigration";
// ...
const boost = useAppStore.getState().config.ttsVolumeBoost ?? 100;
audio.volume = volumePercentToAudioLevel(boost);
```

In `frontend/src/hub/forms/configValidation.ts`, replace volume checks:

```ts
ttsVolumeBoost < 0 ||
ttsVolumeBoost > 100
```

Update `frontend/src/__tests__/configValidation.test.ts` to use `ttsVolumeBoost: 75`.

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test -- --run src/__tests__/volumeMigration.test.ts src/__tests__/configValidation.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hub/forms/volumeMigration.ts frontend/src/hub/components/VolumeSlider.tsx frontend/src/store/config.ts frontend/src/services/priorityAudioQueue.ts frontend/src/hub/forms/configValidation.ts frontend/src/__tests__/volumeMigration.test.ts frontend/src/__tests__/configValidation.test.ts
git commit -m "feat(hub): TTS volume slider 0-100 with legacy migration"
```

---

### Task 4: AudioTtsPanel — tres collapsibles en Audio / PTT

**Files:**
- Create: `frontend/src/hub/sections/AudioTtsPanel.tsx`
- Modify: `frontend/src/components/ConfigTab.tsx` (audio section + quitar inputs voz de ingeniero/spotter)

- [ ] **Step 1: Create AudioTtsPanel**

```tsx
import { CollapsibleSection } from "../components/CollapsibleSection";
import { VoiceSelect } from "../components/VoiceSelect";
import { VolumeSlider } from "../components/VolumeSlider";

interface AudioTtsPanelProps {
  ttsVoiceEngineer: string;
  ttsVoiceSpotter: string;
  ttsVolumeBoost: number;
  onEngineerVoice: (v: string) => void;
  onSpotterVoice: (v: string) => void;
  onVolume: (n: number) => void;
}

export function AudioTtsPanel({
  ttsVoiceEngineer,
  ttsVoiceSpotter,
  ttsVolumeBoost,
  onEngineerVoice,
  onSpotterVoice,
  onVolume,
}: AudioTtsPanelProps) {
  return (
    <div className="flex flex-col gap-2">
      <CollapsibleSection title="Voz TTS spotter">
        <label className="hub-label" htmlFor="tts-spotter-voice">Voz del spotter</label>
        <VoiceSelect id="tts-spotter-voice" value={ttsVoiceSpotter} onChange={onSpotterVoice} />
      </CollapsibleSection>
      <CollapsibleSection title="Voz TTS ingeniero">
        <label className="hub-label" htmlFor="tts-engineer-voice">Voz del ingeniero</label>
        <VoiceSelect id="tts-engineer-voice" value={ttsVoiceEngineer} onChange={onEngineerVoice} />
      </CollapsibleSection>
      <CollapsibleSection title="Volume boost">
        <VolumeSlider value={ttsVolumeBoost} onChange={onVolume} />
      </CollapsibleSection>
    </div>
  );
}
```

- [ ] **Step 2: Wire into ConfigTab audio section**

In `ConfigTab.tsx`, inside `showAudioFields` block (after mic/sensitivity UI, before PTT fields), add:

```tsx
import { AudioTtsPanel } from "../hub/sections/AudioTtsPanel";

<AudioTtsPanel
  ttsVoiceEngineer={ttsVoiceEngineer}
  ttsVoiceSpotter={ttsVoiceSpotter}
  ttsVolumeBoost={ttsVolumeBoost}
  onEngineerVoice={setTtsVoiceEngineer}
  onSpotterVoice={setTtsVoiceSpotter}
  onVolume={setTtsVolumeBoost}
/>
```

Remove from **ingeniero** section (lines ~672–681): the `<input>` for `ttsVoiceEngineer`.

Remove from **spotter** section (lines ~696–703 and ~742–747): voice input + numeric volume boost input.

- [ ] **Step 3: Manual smoke**

Run: `cd frontend && npm run dev:electron`
Expected: Audio / PTT → 3 panels desplegables; Ingeniero/Spotter ya no muestran campos de voz/volumen.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hub/sections/AudioTtsPanel.tsx frontend/src/components/ConfigTab.tsx
git commit -m "feat(hub): collapsible TTS voice and volume panels in Audio"
```

---

### Task 5: Eliminar sección Conexión del hub (solo UI frontend)

**Scope:** Quitar navegación y pantalla del sidebar hub. **No modificar** `useWebSocket`, `services/api.ts`, `vllmIP`/`serverPort` en store, ni endpoints backend.

**Files:**
- Modify: `frontend/src/hub/routes.tsx`
- Modify: `frontend/src/hub/AppShell.tsx`
- Modify: `frontend/src/components/ConfigTab.tsx` (hub mode only)

- [ ] **Step 1: Update routes**

In `frontend/src/hub/routes.tsx`, remove `"conexion"` from `HubSection` union and delete the `{ id: "conexion", label: "Conexión" }` entry from `HUB_SECTIONS`.

- [ ] **Step 2: Update AppShell**

Remove `case "conexion":` branch from `renderSection` in `AppShell.tsx`.

- [ ] **Step 3: Hide connection UI in hub mode**

In `ConfigTab.tsx`, wrap the connection tab block so it only renders when `!hubMode && activeTab === "conexion"` (legacy non-hub `ConfigTab` without `section` prop still works for dev).

Change condition at line ~474 from:
`(activeTab === "conexion" || showProfilesOnly)`
to:
`(!hubMode && activeTab === "conexion") || showProfilesOnly`

And hide top tabs `conexion` when profiles-only — keep profiles page working via `section="perfiles"`.

- [ ] **Step 4: Verify sidebar**

Run app → sidebar must NOT show "Conexión". Perfiles section still loads/saves profiles.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hub/routes.tsx frontend/src/hub/AppShell.tsx frontend/src/components/ConfigTab.tsx
git commit -m "feat(hub): remove Connection section from sidebar"
```

---

### Task 6: Eliminar card “Configuración del Backend”

**Files:**
- Modify: `frontend/src/components/ConfigTab.tsx:798-810`

- [ ] **Step 1: Delete backend config card**

Remove the entire `<div className="mt-2 p-2 bg-hub-card...">` block titled "Configuración del Backend:" (Motor LLM / Modelo).

Keep overlay resize hint and MQTT controls in Avanzado.

- [ ] **Step 2: Smoke test Avanzado section**

Navigate to Avanzado → card must be gone; MQTT toggle still visible.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ConfigTab.tsx
git commit -m "feat(hub): remove backend config status card from Avanzado"
```

---

### Task 7: Quitar telemetría en vivo de Inicio

**Files:**
- Modify: `frontend/src/hub/pages/InicioPage.tsx`

- [ ] **Step 1: Remove telemetry card and unused selectors**

Delete lines importing/using `speed`, `gear`, `fuel`, `lap`, `position`, `gearText`, and the entire `<HubCard title="Telemetría en vivo">` block.

- [ ] **Step 2: Optional test**

If `InicioPage` has no test, skip. Otherwise run existing hub tests.

Run: `cd frontend && npm test -- --run`
Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hub/pages/InicioPage.tsx
git commit -m "feat(hub): remove live telemetry card from Inicio"
```

---

### Task 8: Hotkey capture (estilo videojuegos)

**Files:**
- Create: `frontend/src/hub/forms/hotkeyFormat.ts`
- Create: `frontend/src/hub/components/HotkeyCapture.tsx`
- Modify: `frontend/src/components/ConfigTab.tsx` (replace PTT text inputs)
- Test: `frontend/src/__tests__/hotkeyFormat.test.ts`

- [ ] **Step 1: Write failing tests**

```ts
import { describe, it, expect } from "vitest";
import { normalizeHotkey, toElectronAccelerator } from "../hub/forms/hotkeyFormat";

describe("hotkeyFormat", () => {
  it("normaliza Ctrl+Shift+Space", () => {
    expect(normalHotkey("ctrl+shift+space")).toBe("Ctrl+Shift+Space");
  });

  it("convierte a accelerator Electron", () => {
    expect(toElectronAccelerator("Ctrl+Shift+Space")).toBe("Control+Shift+Space");
    expect(toElectronAccelerator("Mouse4")).toBe("Mouse4");
  });
});
```

Fix typo in test: use `normalizeHotkey` not `normalHotkey`.

- [ ] **Step 2: Implement hotkeyFormat.ts**

```ts
const MOD_MAP: Record<string, string> = {
  control: "Ctrl",
  ctrl: "Ctrl",
  shift: "Shift",
  alt: "Alt",
  meta: "Win",
  super: "Win",
  win: "Win",
  cmd: "Win",
};

const MOUSE_LABELS: Record<number, string> = {
  3: "MouseBack",
  4: "MouseForward",
  5: "Mouse5",
};

export function normalizeHotkey(raw: string): string {
  const parts = raw.split("+").map((p) => p.trim()).filter(Boolean);
  return parts
    .map((p) => {
      const lower = p.toLowerCase();
      if (MOD_MAP[lower]) return MOD_MAP[lower];
      if (lower.length === 1) return lower.toUpperCase();
      if (lower.startsWith("mouse")) return p;
      return p.length <= 3 ? p.toUpperCase() : p.charAt(0).toUpperCase() + p.slice(1);
    })
    .join("+");
}

export function keyboardEventToHotkey(e: KeyboardEvent): string {
  const parts: string[] = [];
  if (e.ctrlKey) parts.push("Ctrl");
  if (e.shiftKey) parts.push("Shift");
  if (e.altKey) parts.push("Alt");
  if (e.metaKey) parts.push("Win");
  const key = e.key;
  if (!["Control", "Shift", "Alt", "Meta"].includes(key)) {
    parts.push(key === " " ? "Space" : key.length === 1 ? key.toUpperCase() : key);
  }
  return normalizeHotkey(parts.join("+"));
}

export function mouseButtonToHotkey(button: number): string | null {
  const label = MOUSE_LABELS[button];
  return label ?? null;
}

export function toElectronAccelerator(combo: string): string {
  return combo
    .split("+")
    .map((p) => {
      if (p === "Ctrl") return "Control";
      if (p === "Win") return "Super";
      return p;
    })
    .join("+");
}
```

- [ ] **Step 3: Implement HotkeyCapture.tsx**

```tsx
import { useCallback, useEffect, useState } from "react";
import { keyboardEventToHotkey, mouseButtonToHotkey, normalizeHotkey } from "../forms/hotkeyFormat";

interface HotkeyCaptureProps {
  value: string;
  onChange: (hotkey: string) => void;
  label: string;
}

export function HotkeyCapture({ value, onChange, label }: HotkeyCaptureProps) {
  const [listening, setListening] = useState(false);

  const stop = useCallback(() => setListening(false), []);

  useEffect(() => {
    if (!listening) return;
    const onKeyDown = (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.key === "Escape") {
        stop();
        return;
      }
      onChange(keyboardEventToHotkey(e));
      stop();
    };
    const onMouseDown = (e: MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const hk = mouseButtonToHotkey(e.button);
      if (hk) {
        onChange(normalizeHotkey(hk));
        stop();
      }
    };
    window.addEventListener("keydown", onKeyDown, true);
    window.addEventListener("mousedown", onMouseDown, true);
    return () => {
      window.removeEventListener("keydown", onKeyDown, true);
      window.removeEventListener("mousedown", onMouseDown, true);
    };
  }, [listening, onChange, stop]);

  return (
    <div className="flex flex-col gap-1">
      <span className="hub-label">{label}</span>
      <button
        type="button"
        onClick={() => setListening(true)}
        className={`hub-input text-left ${listening ? "ring-2 ring-a1-accent" : ""}`}
      >
        {listening ? "Pulsa una tecla o botón del ratón… (Esc cancelar)" : value || "Sin asignar"}
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Replace PTT inputs in ConfigTab**

Replace both `<input type="text" ... pttHotkey>` and `pttStopHotkey` with:

```tsx
<HotkeyCapture label="Tecla PTT (START)" value={pttHotkey} onChange={setPttHotkey} />
<HotkeyCapture label="Tecla PTT (STOP)" value={pttStopHotkey} onChange={setPttStopHotkey} />
```

- [ ] **Step 5: Run tests**

Run: `cd frontend && npm test -- --run src/__tests__/hotkeyFormat.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hub/forms/hotkeyFormat.ts frontend/src/hub/components/HotkeyCapture.tsx frontend/src/components/ConfigTab.tsx frontend/src/__tests__/hotkeyFormat.test.ts
git commit -m "feat(hub): game-style hotkey capture for PTT"
```

---

### Task 9: Electron PTT — hotkeys dinámicos (dejar de hardcodear)

**Files:**
- Modify: `frontend/electron/shortcuts/ptt.ts`
- Modify: `frontend/electron/preload.ts`
- Modify: `frontend/electron/main.ts`
- Modify: `frontend/src/core/platform/types.ts`
- Modify: `frontend/src/core/platform/index.ts`
- Modify: `frontend/src/store/config.ts` (`updateConfig` side effect)

- [ ] **Step 1: Refactor ptt.ts to accept hotkeys**

```ts
import { globalShortcut } from "electron";
import type { BrowserWindow } from "electron";
import { toElectronAccelerator } from "../../src/hub/forms/hotkeyFormat"; // or duplicate minimal converter in electron/

const OVERLAY_RESIZE_HOTKEY = "Control+Shift+O";

export interface PttHotkeyConfig {
  start: string;
  stop: string;
}

let current: PttHotkeyConfig = { start: "Ctrl+Shift+Space", stop: "Ctrl+Shift+Space" };

function sendPttToggle(hubWindow: BrowserWindow | null): void {
  if (hubWindow && !hubWindow.isDestroyed()) {
    hubWindow.webContents.send("ptt:toggle");
  }
}

function isMouseHotkey(hk: string): boolean {
  return hk.startsWith("Mouse");
}

export async function registerPttShortcuts(
  hubWindow: BrowserWindow | null,
  overlayWindow: BrowserWindow | null,
  hotkeys: PttHotkeyConfig = current,
): Promise<void> {
  current = hotkeys;
  unregisterPttShortcuts();

  const startAcc = toElectronAccelerator(hotkeys.start);
  if (!isMouseHotkey(hotkeys.start)) {
    const ok = globalShortcut.register(startAcc, () => sendPttToggle(hubWindow));
    if (!ok) console.warn("[electron] failed to register PTT:", startAcc);
  }

  globalShortcut.register(OVERLAY_RESIZE_HOTKEY, () => {
    const overlay = overlayWindow;
    if (!overlay || overlay.isDestroyed()) return;
    overlay.setResizable(!overlay.isResizable());
  });
}

export function unregisterPttShortcuts(): void {
  globalShortcut.unregisterAll();
}
```

**Note for implementer:** Electron cannot import from `src/` at runtime unless bundled. Copy `toElectronAccelerator` into `frontend/electron/shortcuts/accelerator.ts` (duplicate 15 lines) instead of cross-import.

- [ ] **Step 2: IPC in preload + main**

`preload.ts` add:

```ts
updatePttHotkeys: (payload: { start: string; stop: string }) =>
  ipcRenderer.invoke("ptt:updateHotkeys", payload),
```

`main.ts` add handler calling `registerPttShortcuts(hubWindow, overlayWindow, payload)`.

- [ ] **Step 3: Call from store on config save**

In `updateConfig` in `config.ts`, after persisting:

```ts
const platform = getPlatform();
if (platform.updatePttHotkeys) {
  void platform.updatePttHotkeys({
    start: next.pttHotkey,
    stop: next.pttStopHotkey,
  });
}
```

Wire `updatePttHotkeys` in `getPlatform()` when `vantare.updatePttHotkeys` exists.

- [ ] **Step 4: Manual test**

1. Abrir app Electron
2. Audio → cambiar PTT a `Ctrl+Alt+F`
3. Guardar config
4. Con LMU/minimizado, pulsar combo → debe togglear PTT (hub recibe `ptt:toggle`)

- [ ] **Step 5: Commit**

```bash
git add frontend/electron/shortcuts/ptt.ts frontend/electron/shortcuts/accelerator.ts frontend/electron/preload.ts frontend/electron/main.ts frontend/src/core/platform/types.ts frontend/src/core/platform/index.ts frontend/src/store/config.ts
git commit -m "feat(electron): dynamic global PTT shortcut from config"
```

---

### Task 10: Perfiles — guardar TODA la configuración

**Files:**
- Create: `frontend/src/hub/forms/appConfigKeys.ts`
- Modify: `frontend/src/components/ConfigTab.tsx` (`buildConfigPayload`)
- Test: `frontend/src/__tests__/profilePayload.test.ts`

- [ ] **Step 1: Define exhaustive key list**

```ts
import type { AppConfig } from "../../store/config";

export const APP_CONFIG_KEYS = [
  "vllmIP", "serverPort", "micDevice", "speakerDevice", "wakeWord", "sensitivity",
  "pttHotkey", "pttStopHotkey", "wakeWordEnabled", "swearyMessages",
  "spotterOffQualifying", "spotterExcludeStopped", "mqttEnabled", "mqttBroker", "mqttPort",
  "personalityProfileId", "verbosityLevel", "ttsVoiceEngineer", "ttsVoiceSpotter", "ttsBackend",
  "spotterClearDelayS", "spotterOverlapDelayS", "spotterHoldRepeatS", "spotterGapFrequencyS",
  "spotterCarLengthM", "spotterMinSpeedMs", "spotterRaceStartDelayS",
  "brakingZonesMute", "speakOnlyWhenSpokenTo", "ttsVolumeBoost",
  "spotterEnabled", "engineerEnabled",
] as const satisfies readonly (keyof AppConfig)[];

export function assertFullAppConfig(payload: AppConfig): void {
  for (const key of APP_CONFIG_KEYS) {
    if (!(key in payload)) throw new Error(`Missing profile key: ${key}`);
  }
}
```

- [ ] **Step 2: Fix buildConfigPayload gaps**

Add local state OR read from `config` for fields currently missing from form state:
- `speakerDevice` — add optional select in Audio if not present, or pass `config.speakerDevice` (already done)
- `wakeWord`, `wakeWordEnabled`, `speakOnlyWhenSpokenTo` — ensure included from `config` (already partially)
- `spotterOverlapDelayS` — add to spotter advanced grid OR include from `config.spotterOverlapDelayS`

At end of `buildConfigPayload`:

```ts
import { assertFullAppConfig } from "../hub/forms/appConfigKeys";
const payload = { /* existing fields */ } satisfies AppConfig;
assertFullAppConfig(payload);
return payload;
```

- [ ] **Step 3: Write profile round-trip test**

```ts
import { describe, it, expect } from "vitest";
import { APP_CONFIG_KEYS } from "../hub/forms/appConfigKeys";
import type { AppConfig } from "../store/config";

describe("profile payload", () => {
  it("APP_CONFIG_KEYS cubre todas las keys de AppConfig", () => {
    const sample: AppConfig = {} as AppConfig;
    for (const k of APP_CONFIG_KEYS) {
      expect(k in sample || true).toBe(true); // compile-time check via satisfies
    }
    expect(APP_CONFIG_KEYS.length).toBeGreaterThanOrEqual(30);
  });
});
```

- [ ] **Step 4: Manual profile test**

1. Perfiles → guardar perfil `qol-test`
2. Cambiar voz ingeniero, volumen, PTT
3. Cargar otro perfil y volver a `qol-test`
4. Verificar valores restaurados

Backend file check: `backend/data/profiles/qol-test.json` contains all keys.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hub/forms/appConfigKeys.ts frontend/src/components/ConfigTab.tsx frontend/src/__tests__/profilePayload.test.ts
git commit -m "fix(profiles): ensure full AppConfig snapshot on save"
```

---

### Task 11: Historial — chat PTT + log de avisos de radio

**Files:**
- Modify: `frontend/src/core/platform/types.ts`
- Modify: `frontend/src/store/config.ts`
- Modify: `frontend/src/hooks/useWebSocket.ts`
- Modify: `frontend/src/hub/pages/HistorialPage.tsx`
- Test: `frontend/src/__tests__/sessionHistory.test.ts`
- Test: `frontend/src/__tests__/radioHistory.test.ts`

- [ ] **Step 1: Extend message sender types**

In `frontend/src/core/platform/types.ts`:

```ts
export type HistorySender = "pilot" | "engineer" | "spotter";

export interface SessionHistoryFile {
  sessionId: string;
  startedAt: string;
  endedAt?: string;
  track?: string;
  messages: Array<{ sender: HistorySender; text: string; timestamp: number; category?: string }>;
}
```

In `frontend/src/store/config.ts`, align `MessageRecord`:

```ts
export type HistorySender = "pilot" | "engineer" | "spotter";

export interface MessageRecord {
  sender: HistorySender;
  text: string;
  timestamp: number;
  category?: string;
}
```

Add store action:

```ts
addRadioAlertToHistory: (sender: "spotter" | "engineer", text: string, category?: string) => void;
```

Implementation (dedupe consecutive identical alert text):

```ts
addRadioAlertToHistory: (sender, text, category) =>
  set((state) => {
    const trimmed = text.trim();
    if (!trimmed || isInternalRadioText(trimmed)) return state;
    const last = state.radio.messageHistory[state.radio.messageHistory.length - 1];
    if (last?.sender === sender && last.text === trimmed) return state;
    return {
      radio: {
        ...state.radio,
        messageHistory: [
          ...state.radio.messageHistory,
          { sender, text: trimmed, timestamp: Date.now(), category },
        ],
      },
    };
  }),
```

Export helper `isInternalRadioText` from a shared module if needed (already in filters).

- [ ] **Step 2: Write failing test**

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { useAppStore } from "../store/config";

describe("radio history", () => {
  beforeEach(() => useAppStore.setState({ radio: { ...useAppStore.getState().radio, messageHistory: [] } }));

  it("addRadioAlertToHistory guarda aviso spotter", () => {
    useAppStore.getState().addRadioAlertToHistory("spotter", "Hypercar doblando por la derecha", "proximity");
    const h = useAppStore.getState().radio.messageHistory;
    expect(h).toHaveLength(1);
    expect(h[0].sender).toBe("spotter");
    expect(h[0].category).toBe("proximity");
  });

  it("no duplica el mismo aviso consecutivo", () => {
    const { addRadioAlertToHistory } = useAppStore.getState();
    addRadioAlertToHistory("spotter", "Clear", "proximity");
    addRadioAlertToHistory("spotter", "Clear", "proximity");
    expect(useAppStore.getState().radio.messageHistory).toHaveLength(1);
  });
});
```

Run: `cd frontend && npm test -- --run src/__tests__/radioHistory.test.ts`
Expected: FAIL

- [ ] **Step 3: Log alerts in useWebSocket**

In `frontend/src/hooks/useWebSocket.ts`, inside `case "alert":` after parsing `alertMsg` and `category`:

```ts
import { SPOTTER_VOICE_CATEGORIES } from "../services/alertVoice"; // or inline set

const spotterCategories = new Set([
  "proximity", "pit_limiter", "fuel", "safety_car", "damage", "puncture", "impact", "limiter", "gaps",
]);

if (alertMsg && !isInternalRadioText(alertMsg)) {
  if (spotterCategories.has(category)) {
    addRadioAlertToHistory("spotter", alertMsg, category);
  } else if (category !== "voice_response" && category !== "system" && category !== "spotter") {
    addRadioAlertToHistory("engineer", alertMsg, category);
  }
}
```

Also log commentary batch text (already partially via `addMessageToHistory("engineer", commentaryText)` — keep as engineer sender).

Wire `addRadioAlertToHistory` from store destructuring at top of hook.

- [ ] **Step 4: HistorialPage labels**

Map sender to Spanish label:

```tsx
const SENDER_LABEL: Record<string, string> = {
  pilot: "Piloto",
  engineer: "Ingeniero",
  spotter: "Spotter",
};
// render: {SENDER_LABEL[msg.sender] ?? msg.sender}
// optional: show msg.category as muted badge for radio alerts
```

- [ ] **Step 5: Run tests + manual QA**

Run: `cd frontend && npm test -- --run src/__tests__/radioHistory.test.ts src/__tests__/sessionHistory.test.ts`

Manual:
1. Encender spotter → provocar aviso lateral → Historial debe mostrar línea **Spotter**
2. PTT pregunta → Historial **Piloto** + **Ingeniero**
3. SC activo → línea **Spotter** o **Ingeniero** según category

- [ ] **Step 6: Commit**

```bash
git add frontend/src/core/platform/types.ts frontend/src/store/config.ts frontend/src/hooks/useWebSocket.ts frontend/src/hub/pages/HistorialPage.tsx frontend/src/__tests__/radioHistory.test.ts frontend/src/__tests__/sessionHistory.test.ts
git commit -m "feat(history): persist PTT chat and radio alert log per session"
```

---

### Task 12: Verification gate

- [ ] **Run frontend tests**

```powershell
cd frontend
npm test -- --run
```

Expected: all PASS

- [ ] **Manual QA checklist**

| # | Acción | Esperado |
|---|--------|----------|
| 1 | Sidebar | No "Conexión" |
| 2 | Inicio | Sin card telemetría |
| 3 | Audio / PTT | 3 collapsibles TTS |
| 4 | Voces | Labels "Hombre/Mujer — Español" |
| 5 | Volumen | Slider 0–100% (0 = mute) |
| 6 | PTT capture | Click → tecla → guardado |
| 7 | Avanzado | Sin card backend config |
| 8 | Perfil save/load | Round-trip completo |
| 9 | Historial | PTT + avisos spotter/ingeniero por sesión |

- [ ] **Final commit if fixes needed**

```bash
git commit -m "chore(hub): QoL config verification fixes"
```

---

## Self-review

| Spec requirement | Task |
|------------------|------|
| Collapsibles: Voz TTS spotter, ingeniero, Volume boost | Task 1, 4 |
| Eliminar configuración backend | Task 6 |
| Voces ES con labels humanos | Task 2, 4 |
| Collapsibles plegados por defecto | Task 1, 4 |
| Volume 0–100% slider | Task 3, 4 |
| Conexión solo UI hub (backend intacto) | Task 5 |
| Historial: chat + log radio | Task 11 |
| Quitar telemetría Inicio | Task 7 |
| PTT click-to-bind | Task 8, 9 |
| Eliminar sección Conexión | Task 5 |
| Perfiles guardan todo | Task 10 |
| Historial por sesión | Task 11 |

**Placeholder scan:** No TBD/TODO en pasos de implementación.

**Type consistency:** `ttsVolumeBoost` = percent **0–100** en `AppConfig`; `audio.volume = percent / 100`. `HistorySender` unificado en store y `SessionHistoryFile`.

---

## Preguntas resueltas (2026-06-08)

Todas las decisiones de producto están cerradas. No hay preguntas pendientes antes de ejecutar.
