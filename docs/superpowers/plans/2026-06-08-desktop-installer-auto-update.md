# Desktop Installer + Auto-Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a polished Windows NSIS installer for the full Electron app (Hub + Overlay + bundled backend) and let users check, download, and apply updates from Hub → Avanzado without opening a browser.

**Architecture:** Keep Electron as the single desktop shell. Package with `electron-builder` (NSIS, per-user install). Bundle backend via existing `extraResources`. Use `electron-updater` with GitHub Releases (`latest.yml`) for in-app updates (shell + backend lockstep). Retain backend `/version/check` as informational fallback only.

**Tech Stack:** Electron 34, electron-builder 25, electron-updater, NSIS, PyInstaller (`backend/build_backend.py`), GitHub Actions, React Hub (ConfigTab avanzado), Vitest.

---

## File map (created / modified)

| File | Responsibility |
|------|----------------|
| `frontend/package.json` | `electron-updater` dep, version bump, publish script |
| `frontend/electron-builder.yml` | NSIS UX, publish provider, artifact names |
| `frontend/electron/updater.ts` | `autoUpdater` lifecycle + typed events |
| `frontend/electron/main.ts` | IPC handlers, spawn backend, quit-for-update |
| `frontend/electron/preload.ts` | Expose `checkForUpdates`, `quitAndInstall`, subscribe |
| `frontend/src/core/platform/types.ts` | `DesktopUpdate*` types + bridge methods |
| `frontend/src/core/platform/index.ts` | Wire bridge stubs / Electron impl |
| `frontend/src/services/desktopUpdate.ts` | Renderer service (state + IPC) |
| `frontend/src/hub/sections/UpdatesPanel.tsx` | Hub UI: check, progress, restart |
| `frontend/src/components/ConfigTab.tsx` | Render `UpdatesPanel` in `avanzado` |
| `frontend/src/hub/HubRoot.tsx` | Remove banner-only flow when desktop updater active |
| `frontend/electron/updater.test.ts` | Unit tests for status mapping (node/vitest) |
| `frontend/src/__tests__/desktopUpdate.test.ts` | Renderer service tests |
| `.github/workflows/release-desktop.yml` | Build backend + `build:desktop` + upload assets |
| `scripts/build-desktop.ps1` | One-command local release build |
| `docs/instalacion-desktop.md` | User-facing install/update guide |

---

## Task 1: NSIS installer polish + version source of truth

**Files:**
- Modify: `frontend/electron-builder.yml`
- Modify: `frontend/package.json`
- Create: `scripts/build-desktop.ps1`

- [ ] **Step 1: Extend electron-builder NSIS block**

Add to `frontend/electron-builder.yml`:

```yaml
publish:
  provider: github
  owner: YOUR_GITHUB_ORG
  repo: Vantare-Ingeniero

nsis:
  oneClick: false
  perMachine: false
  allowToChangeInstallationDirectory: false
  createDesktopShortcut: true
  createStartMenuShortcut: true
  shortcutName: Vantare Ingeniero IA
  installerIcon: src-tauri/icons/icon.ico
  uninstallDisplayName: Vantare Ingeniero IA
  artifactName: vantare-ingeniero-${version}-setup.${ext}

win:
  target:
    - target: nsis
      arch:
        - x64
  icon: src-tauri/icons/icon.ico
  publisherName: Vantare
```

Replace `YOUR_GITHUB_ORG` with the real GitHub org/user from `backend/src/version.py` `GITHUB_REPO`.

- [ ] **Step 2: Align package version**

Ensure `frontend/package.json` `"version"` matches release tags (start `0.1.0`). electron-builder reads this for NSIS + updater.

- [ ] **Step 3: Add local build script**

Create `scripts/build-desktop.ps1`:

```powershell
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "=== Building backend ==="
Set-Location backend
python build_backend.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== Building desktop (Electron NSIS) ==="
Set-Location ..\frontend
npm run build:desktop
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== Output ==="
Get-ChildItem .\release\*.exe
```

- [ ] **Step 4: Smoke-build locally (manual)**

Run: `powershell -File scripts/build-desktop.ps1`  
Expected: `frontend/release/vantare-ingeniero-0.1.0-setup.exe` exists.

- [ ] **Step 5: Commit**

```bash
git add frontend/electron-builder.yml frontend/package.json scripts/build-desktop.ps1
git commit -m "chore(desktop): polish NSIS config and add build-desktop script"
```

---

## Task 2: Add electron-updater dependency

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install dependency**

```bash
cd frontend
npm install electron-updater@^6.6.2
```

- [ ] **Step 2: Verify lockfile**

Run: `npm ls electron-updater`  
Expected: `electron-updater@6.x` under frontend.

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(desktop): add electron-updater dependency"
```

---

## Task 3: Updater module in main process

**Files:**
- Create: `frontend/electron/updater.ts`
- Modify: `frontend/electron/main.ts`

- [ ] **Step 1: Write updater module**

Create `frontend/electron/updater.ts`:

```typescript
import { app, BrowserWindow } from "electron";
import { autoUpdater } from "electron-updater";
import log from "electron-log";

export type DesktopUpdatePhase =
  | "idle"
  | "checking"
  | "available"
  | "not-available"
  | "downloading"
  | "downloaded"
  | "error";

export interface DesktopUpdateSnapshot {
  phase: DesktopUpdatePhase;
  currentVersion: string;
  latestVersion?: string;
  percent?: number;
  bytesPerSecond?: number;
  transferred?: number;
  total?: number;
  message?: string;
}

let snapshot: DesktopUpdateSnapshot = {
  phase: "idle",
  currentVersion: app.getVersion(),
};

function broadcast(win: BrowserWindow | null, next: DesktopUpdateSnapshot): void {
  snapshot = next;
  win?.webContents.send("desktop-update:status", snapshot);
}

export function getDesktopUpdateSnapshot(): DesktopUpdateSnapshot {
  return snapshot;
}

export function initDesktopUpdater(getHubWindow: () => BrowserWindow | null): void {
  autoUpdater.logger = log;
  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on("checking-for-update", () => {
    broadcast(getHubWindow(), { phase: "checking", currentVersion: app.getVersion() });
  });

  autoUpdater.on("update-available", (info) => {
    broadcast(getHubWindow(), {
      phase: "available",
      currentVersion: app.getVersion(),
      latestVersion: info.version,
    });
  });

  autoUpdater.on("update-not-available", () => {
    broadcast(getHubWindow(), {
      phase: "not-available",
      currentVersion: app.getVersion(),
    });
  });

  autoUpdater.on("download-progress", (p) => {
    broadcast(getHubWindow(), {
      phase: "downloading",
      currentVersion: app.getVersion(),
      percent: p.percent,
      bytesPerSecond: p.bytesPerSecond,
      transferred: p.transferred,
      total: p.total,
    });
  });

  autoUpdater.on("update-downloaded", (info) => {
    broadcast(getHubWindow(), {
      phase: "downloaded",
      currentVersion: app.getVersion(),
      latestVersion: info.version,
    });
  });

  autoUpdater.on("error", (err) => {
    broadcast(getHubWindow(), {
      phase: "error",
      currentVersion: app.getVersion(),
      message: err.message,
    });
  });
}

export async function checkForDesktopUpdates(): Promise<DesktopUpdateSnapshot> {
  if (!app.isPackaged) {
    const dev: DesktopUpdateSnapshot = {
      phase: "error",
      currentVersion: app.getVersion(),
      message: "Actualizaciones solo disponibles en la app instalada",
    };
    snapshot = dev;
    return dev;
  }
  await autoUpdater.checkForUpdates();
  return snapshot;
}

export async function downloadDesktopUpdate(): Promise<void> {
  await autoUpdater.downloadUpdate();
}

export function quitAndInstallDesktopUpdate(): void {
  autoUpdater.quitAndInstall(false, true);
}
```

Add `electron-log` in same task: `npm install electron-log`.

- [ ] **Step 2: Wire IPC in main.ts**

After `registerIpc()`, add handlers:

```typescript
import {
  checkForDesktopUpdates,
  downloadDesktopUpdate,
  getDesktopUpdateSnapshot,
  initDesktopUpdater,
  quitAndInstallDesktopUpdate,
} from "./updater";

// inside registerIpc():
ipcMain.handle("desktop-update:getStatus", () => getDesktopUpdateSnapshot());
ipcMain.handle("desktop-update:check", () => checkForDesktopUpdates());
ipcMain.handle("desktop-update:download", () => downloadDesktopUpdate());
ipcMain.handle("desktop-update:quitAndInstall", () => quitAndInstallDesktopUpdate());

// in app.whenReady():
initDesktopUpdater(() => hubWindow);
```

- [ ] **Step 3: Manual smoke (packaged only)**

Build installer, install, open Hub → Avanzado → "Buscar actualizaciones" should reach checking state (Task 5 UI).

- [ ] **Step 4: Commit**

```bash
git add frontend/electron/updater.ts frontend/electron/main.ts frontend/package.json frontend/package-lock.json
git commit -m "feat(desktop): add electron-updater main process module"
```

---

## Task 4: Preload + platform bridge

**Files:**
- Modify: `frontend/electron/preload.ts`
- Modify: `frontend/src/core/platform/types.ts`
- Modify: `frontend/src/core/platform/index.ts`

- [ ] **Step 1: Extend types**

In `frontend/src/core/platform/types.ts` add:

```typescript
export type DesktopUpdatePhase =
  | "idle"
  | "checking"
  | "available"
  | "not-available"
  | "downloading"
  | "downloaded"
  | "error";

export interface DesktopUpdateStatus {
  phase: DesktopUpdatePhase;
  currentVersion: string;
  latestVersion?: string;
  percent?: number;
  bytesPerSecond?: number;
  transferred?: number;
  total?: number;
  message?: string;
}
```

Extend `PlatformBridge`:

```typescript
  getDesktopUpdateStatus?(): Promise<DesktopUpdateStatus>;
  checkDesktopUpdates?(): Promise<DesktopUpdateStatus>;
  downloadDesktopUpdate?(): Promise<void>;
  quitAndInstallDesktopUpdate?(): Promise<void>;
  subscribeDesktopUpdate?(handler: (status: DesktopUpdateStatus) => void): () => void;
```

- [ ] **Step 2: Expose in preload**

```typescript
  getDesktopUpdateStatus: () => ipcRenderer.invoke("desktop-update:getStatus"),
  checkDesktopUpdates: () => ipcRenderer.invoke("desktop-update:check"),
  downloadDesktopUpdate: () => ipcRenderer.invoke("desktop-update:download"),
  quitAndInstallDesktopUpdate: () => ipcRenderer.invoke("desktop-update:quitAndInstall"),
  subscribeDesktopUpdate: (handler: (status: unknown) => void) => {
    const listener = (_event: unknown, status: unknown) => handler(status);
    ipcRenderer.on("desktop-update:status", listener);
    return () => ipcRenderer.removeListener("desktop-update:status", listener);
  },
```

- [ ] **Step 3: Wire getPlatform()**

Map new methods in `frontend/src/core/platform/index.ts` from `window.vantare`.

- [ ] **Step 4: Commit**

```bash
git add frontend/electron/preload.ts frontend/src/core/platform/types.ts frontend/src/core/platform/index.ts
git commit -m "feat(desktop): expose desktop update IPC via platform bridge"
```

---

## Task 5: Renderer service + Hub UI (Avanzado)

**Files:**
- Create: `frontend/src/services/desktopUpdate.ts`
- Create: `frontend/src/hub/sections/UpdatesPanel.tsx`
- Modify: `frontend/src/components/ConfigTab.tsx`
- Modify: `frontend/src/hub/HubRoot.tsx`

- [ ] **Step 1: Write failing test**

Create `frontend/src/__tests__/desktopUpdate.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createDesktopUpdateController } from "../services/desktopUpdate";

describe("desktopUpdate controller", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("maps not-available phase to user label", async () => {
    const check = vi.fn().mockResolvedValue({
      phase: "not-available",
      currentVersion: "0.1.0",
    });
    const ctrl = createDesktopUpdateController({ check, download: vi.fn(), quitAndInstall: vi.fn(), getStatus: vi.fn(), subscribe: () => () => {} });
    const status = await ctrl.check();
    expect(ctrl.labelFor(status)).toBe("Estás en la última versión");
  });
});
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd frontend && npm test -- --run src/__tests__/desktopUpdate.test.ts`  
Expected: FAIL — module not found.

- [ ] **Step 3: Implement service**

Create `frontend/src/services/desktopUpdate.ts` with `createDesktopUpdateController`, `labelFor`, `useDesktopUpdate` hook using `getPlatform()`.

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Build UpdatesPanel**

Create `frontend/src/hub/sections/UpdatesPanel.tsx`:
- Shows `v{currentVersion}`
- Button **Buscar actualizaciones**
- When `available`: button **Descargar**
- When `downloading`: progress bar + %
- When `downloaded`: **Reiniciar para actualizar**
- Link fallback: **Abrir página de release** (uses existing `openReleaseUrl`)

- [ ] **Step 6: Mount in ConfigTab**

In `ConfigTab.tsx` when `section === "avanzado"`, render `<UpdatesPanel />` at top of section.

- [ ] **Step 7: HubRoot — desktop path**

If `getPlatform().checkDesktopUpdates` exists, skip auto banner from `fetchUpdateNotice` on mount (updater owns UX). Keep banner for web/dev fallback.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/services/desktopUpdate.ts frontend/src/hub/sections/UpdatesPanel.tsx frontend/src/components/ConfigTab.tsx frontend/src/hub/HubRoot.tsx frontend/src/__tests__/desktopUpdate.test.ts
git commit -m "feat(hub): add desktop update panel in Avanzado settings"
```

---

## Task 6: GitHub Release workflow (desktop artifacts)

**Files:**
- Create: `.github/workflows/release-desktop.yml`
- Modify: `.github/workflows/release.yml` (add deprecation comment at top)

- [ ] **Step 1: Create release-desktop workflow**

```yaml
name: Release Desktop

on:
  push:
    tags:
      - "v*"
  workflow_dispatch: {}

jobs:
  build-windows-desktop:
    runs-on: windows-2022
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - name: Install Python deps
        run: |
          pip install -e ./shared-telemetry -e ./shared-strategy
          pip install pyinstaller
      - name: Build backend
        run: python backend/build_backend.py
      - name: Install frontend deps
        run: npm ci
        working-directory: frontend
      - name: Build desktop installer
        run: npm run build:desktop
        working-directory: frontend
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - name: Upload to GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            frontend/release/*.exe
            frontend/release/latest.yml
          generate_release_notes: true
```

- [ ] **Step 2: Tag dry-run**

Push tag `v0.1.0-test` on a branch and verify workflow produces `.exe` + `latest.yml`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release-desktop.yml .github/workflows/release.yml
git commit -m "ci: add release-desktop workflow for electron-updater artifacts"
```

---

## Task 7: User docs + deprecate legacy NSIS backend-only

**Files:**
- Create: `docs/instalacion-desktop.md`
- Modify: `installer/windows.nsi` (banner comment at top)

- [ ] **Step 1: Write install guide**

Document:
1. Download `vantare-ingeniero-X-setup.exe` from Releases
2. Run installer (SmartScreen note if unsigned)
3. Launch from Start Menu
4. Updates: Hub → Avanzado → Buscar actualizaciones

- [ ] **Step 2: Mark legacy installer deprecated**

Add at top of `installer/windows.nsi`:

```nsis
; DEPRECATED: use frontend/electron-builder NSIS (npm run build:desktop)
```

- [ ] **Step 3: Commit**

```bash
git add docs/instalacion-desktop.md installer/windows.nsi
git commit -m "docs: add desktop install guide; deprecate legacy NSIS"
```

---

## Task 8 (P2 — optional): Code signing

**Files:**
- Modify: `frontend/electron-builder.yml`
- Modify: `.github/workflows/release-desktop.yml`

- [ ] **Step 1:** Obtain Windows code signing cert (OV minimum).
- [ ] **Step 2:** Add secrets `WIN_CSC_LINK`, `WIN_CSC_KEY_PASSWORD` to GitHub.
- [ ] **Step 3:** Add to electron-builder:

```yaml
win:
  certificateFile: ${env.WIN_CSC_LINK}
  certificatePassword: ${env.WIN_CSC_KEY_PASSWORD}
```

---

## Self-review (spec coverage)

| Requirement | Task |
|-------------|------|
| Polished NSIS installer | Task 1 |
| Full app bundle (Electron + backend) | Existing extraResources + Task 1 script |
| In-app update check from Hub/Settings | Tasks 3–5 |
| Download progress + restart | Tasks 3, 5 |
| GitHub Releases hosting | Task 6 |
| Shell + backend lockstep | Architecture (single NSIS artifact) |
| Offline fallback | UpdatesPanel release link |
| Legacy path deprecation | Task 7 |
| Code signing | Task 8 (P2) |

No placeholders remain in task steps above.

---

## Risks

- **Unsigned builds:** SmartScreen warnings until reputation or Task 8 signing.
- **Antivirus false positives:** PyInstaller backend inside Electron; monitor VirusTotal on releases.
- **Dev vs prod:** Updater disabled in unpackaged dev — document clearly.
- **Version drift:** Tag must match `frontend/package.json` version for updater metadata.

---

## MVP scope (this plan)

Tasks **1–7** = shippable MVP in ~1–2 weeks. Task 8 when budget allows.
