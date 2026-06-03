/**
 * T15 — Frontend config persistence across reload
 *
 * Verifies that:
 *   1. Vite dev server loads the React app
 *   2. The Zustand store (useAppStore) exposes `updateConfig(...)` which
 *      mutates `state.config` AND writes through to `localStorage`
 *      under the key `vantare_config`
 *   3. After a full page reload, the store re-hydrates from
 *      `localStorage` (via `loadSavedConfig()` in store/config.ts) and
 *      the previously written value is still present
 *
 * Strategy (no app code modifications — same pattern as T13):
 *   - page.evaluate() dynamically imports /src/store/config.ts (Vite
 *     serves source modules at the .ts path in dev) and reads /
 *     mutates `useAppStore.getState()`
 *   - We pick a string field (`wakeWord`) for a clear before/after
 *     assertion, write a sentinel value, then `page.reload()` and
 *     verify the sentinel survives the reload
 *   - We also peek at `localStorage.getItem("vantare_config")` to
 *     confirm the persistence layer is the one doing the work
 *
 * Backend note: the test is frontend-only. The FastAPI backend is not
 * required — the ConfigTab never talks to the network on its own, and
 * `updateConfig` only touches the local store + localStorage.
 */
import { test, expect, type ConsoleMessage } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

// ESM-safe __dirname shim (package.json has "type": "module")
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const REPO_ROOT = path.join(__dirname, "..", "..");
const EVIDENCE_DIR = path.join(REPO_ROOT, ".omo", "evidence", "pipeline-review");
const EVIDENCE_TXT = path.join(EVIDENCE_DIR, "task-15-config-persistence.txt");
const EVIDENCE_PNG = path.join(EVIDENCE_DIR, "task-15-config-persistence.png");
const LEARNINGS_MD = path.join(REPO_ROOT, ".omo", "notepads", "pipeline-review", "learnings.md");

// Errors expected when the FastAPI backend is not running.
// (T15 is frontend-only, but the App boots useWebSocket which still
// tries to reach ws://localhost:8008/ws — same noise as T13.)
const EXPECTED_BACKEND_PATTERNS: RegExp[] = [
  /Failed to load resource:\s*net::ERR_CONNECTION_REFUSED/,
  /WebSocket connection to 'ws:\/\/[^/']+\/ws' failed/,
  /\[useWebSocket\] Error de conexi\u00f3n/,
  /\[api\] Error fetching health/,
  /\[App\] Polling de salud fallido/,
];

function isExpectedBackendError(text: string): boolean {
  return EXPECTED_BACKEND_PATTERNS.some((re) => re.test(text));
}

test.describe("T15 — Frontend config persists across reload", () => {
  test("updateConfig + reload -> value survives (localStorage-backed)", async ({ page, baseURL }) => {
    const consoleErrors: string[] = [];
    const onConsole = (msg: ConsoleMessage) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    };
    const onPageError = (err: Error) => {
      consoleErrors.push(err.message);
    };
    page.on("console", onConsole);
    page.on("pageerror", onPageError);

    // Informational probe — backend is not required for this test.
    let backendReachable = false;
    try {
      const probe = await page.request.get("http://localhost:8008/health", { timeout: 2000 });
      backendReachable = probe.ok();
    } catch {
      backendReachable = false;
    }

    const t0 = Date.now();

    // -----------------------------------------------------------------
    // PHASE 1 — load app, snapshot initial config, write sentinel value
    // -----------------------------------------------------------------
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page).toHaveTitle(/Vantare/i);

    // Sentinel values: a unique wakeWord + a numeric sensitivity.
    // We write both so the test covers string AND number fields.
    const SENTINEL_WAKE_WORD = "t15-persistencia-vantare";
    const SENTINEL_SENSITIVITY = 73;
    const SENTINEL_PORT = 8765;

    // Read the initial config so we can prove it actually changed.
    const initial = await page.evaluate(async () => {
      // @ts-ignore — runtime URL resolved by Vite dev server
      const mod: any = await import("/src/store/config.ts");
      const s = mod.useAppStore.getState();
      return {
        vllmIP: s.config.vllmIP,
        serverPort: s.config.serverPort,
        micDevice: s.config.micDevice,
        speakerDevice: s.config.speakerDevice,
        wakeWord: s.config.wakeWord,
        sensitivity: s.config.sensitivity,
        pttHotkey: s.config.pttHotkey,
        pttStopHotkey: s.config.pttStopHotkey,
        wakeWordEnabled: s.config.wakeWordEnabled,
      };
    });

    // Write the sentinel. updateConfig() mutates the store AND
    // writes the full new config to localStorage("vantare_config").
    const written = await page.evaluate(
      async ({ ww, sens, port }) => {
        // @ts-ignore — runtime URL resolved by Vite dev server
        const mod: any = await import("/src/store/config.ts");
        const store = mod.useAppStore;
        store.getState().updateConfig({
          wakeWord: ww,
          sensitivity: sens,
          serverPort: port,
        });
        const after = store.getState().config;
        const lsRaw = window.localStorage.getItem("vantare_config");
        return {
          after: {
            wakeWord: after.wakeWord,
            sensitivity: after.sensitivity,
            serverPort: after.serverPort,
          },
          lsRaw,
        };
      },
      { ww: SENTINEL_WAKE_WORD, sens: SENTINEL_SENSITIVITY, port: SENTINEL_PORT },
    );

    // In-memory assertions: store should reflect the new values
    // immediately, even before the reload.
    expect(written.after.wakeWord).toBe(SENTINEL_WAKE_WORD);
    expect(written.after.sensitivity).toBe(SENTINEL_SENSITIVITY);
    expect(written.after.serverPort).toBe(SENTINEL_PORT);

    // localStorage must contain the full config object including
    // our sentinel — this is what the store will read on reload.
    expect(written.lsRaw, "updateConfig should have written to localStorage").not.toBeNull();
    const lsParsed = JSON.parse(written.lsRaw!);
    expect(lsParsed.wakeWord).toBe(SENTINEL_WAKE_WORD);
    expect(lsParsed.sensitivity).toBe(SENTINEL_SENSITIVITY);
    expect(lsParsed.serverPort).toBe(SENTINEL_PORT);

    // -----------------------------------------------------------------
    // PHASE 2 — reload the page and re-read the store
    // -----------------------------------------------------------------
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page).toHaveTitle(/Vantare/i);

    // The store factory re-runs on import, which means
    // loadSavedConfig() pulls from localStorage. We re-import the
    // module to get the freshly-initialized store.
    const afterReload = await page.evaluate(async () => {
      // @ts-ignore — runtime URL resolved by Vite dev server
      const mod: any = await import("/src/store/config.ts");
      const s = mod.useAppStore.getState();
      const lsRaw = window.localStorage.getItem("vantare_config");
      return {
        vllmIP: s.config.vllmIP,
        serverPort: s.config.serverPort,
        micDevice: s.config.micDevice,
        speakerDevice: s.config.speakerDevice,
        wakeWord: s.config.wakeWord,
        sensitivity: s.config.sensitivity,
        pttHotkey: s.config.pttHotkey,
        pttStopHotkey: s.config.pttStopHotkey,
        wakeWordEnabled: s.config.wakeWordEnabled,
        lsRaw,
      };
    });

    // --- THE PERSISTENCE ASSERTIONS ---
    expect(afterReload.wakeWord, "wakeWord should survive reload").toBe(SENTINEL_WAKE_WORD);
    expect(afterReload.sensitivity, "sensitivity should survive reload").toBe(SENTINEL_SENSITIVITY);
    expect(afterReload.serverPort, "serverPort should survive reload").toBe(SENTINEL_PORT);

    // Untouched fields should still match their initial values.
    expect(afterReload.vllmIP).toBe(initial.vllmIP);
    expect(afterReload.micDevice).toBe(initial.micDevice);
    expect(afterReload.speakerDevice).toBe(initial.speakerDevice);
    expect(afterReload.pttHotkey).toBe(initial.pttHotkey);
    expect(afterReload.pttStopHotkey).toBe(initial.pttStopHotkey);
    expect(afterReload.wakeWordEnabled).toBe(initial.wakeWordEnabled);

    // localStorage should still be the persistence-of-record.
    expect(afterReload.lsRaw).not.toBeNull();
    const lsAfter = JSON.parse(afterReload.lsRaw!);
    expect(lsAfter.wakeWord).toBe(SENTINEL_WAKE_WORD);
    expect(lsAfter.sensitivity).toBe(SENTINEL_SENSITIVITY);
    expect(lsAfter.serverPort).toBe(SENTINEL_PORT);

    // -----------------------------------------------------------------
    // PHASE 3 — clean up: restore the original config so the test
    // leaves no residue for the next run / for a human developer.
    // -----------------------------------------------------------------
    const restoreResult = await page.evaluate(
      async (orig) => {
        // @ts-ignore — runtime URL resolved by Vite dev server
        const mod: any = await import("/src/store/config.ts");
        mod.useAppStore.getState().updateConfig({
          wakeWord: orig.wakeWord,
          sensitivity: orig.sensitivity,
          serverPort: orig.serverPort,
        });
        const after = mod.useAppStore.getState().config;
        return {
          wakeWord: after.wakeWord,
          sensitivity: after.sensitivity,
          serverPort: after.serverPort,
        };
      },
      {
        wakeWord: initial.wakeWord,
        sensitivity: initial.sensitivity,
        serverPort: initial.serverPort,
      },
    );
    expect(restoreResult.wakeWord).toBe(initial.wakeWord);
    expect(restoreResult.sensitivity).toBe(initial.sensitivity);
    expect(restoreResult.serverPort).toBe(initial.serverPort);

    // -----------------------------------------------------------------
    // EVIDENCE — screenshot + text summary
    // -----------------------------------------------------------------
    fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
    await page.screenshot({ path: EVIDENCE_PNG, fullPage: true });

    const elapsed = Date.now() - t0;
    const evidenceLines: string[] = [
      "TASK 15 — Frontend Config Persistence Across Reload",
      "===================================================",
      `Date: ${new Date().toISOString()}`,
      `BaseURL: ${baseURL}`,
      `Backend reachable at probe time: ${backendReachable}`,
      "",
      "Sentinel values written via updateConfig:",
      `  wakeWord     = ${JSON.stringify(SENTINEL_WAKE_WORD)}`,
      `  sensitivity  = ${SENTINEL_SENSITIVITY}`,
      `  serverPort   = ${SENTINEL_PORT}`,
      "",
      "Phase 1 — in-memory after updateConfig:",
      `  wakeWord     = ${JSON.stringify(written.after.wakeWord)}`,
      `  sensitivity  = ${written.after.sensitivity}`,
      `  serverPort   = ${written.after.serverPort}`,
      `  localStorage["vantare_config"] present: ${written.lsRaw !== null}`,
      "",
      "Phase 2 — after page.reload():",
      `  wakeWord     = ${JSON.stringify(afterReload.wakeWord)}`,
      `  sensitivity  = ${afterReload.sensitivity}`,
      `  serverPort   = ${afterReload.serverPort}`,
      `  vllmIP (untouched)        = ${JSON.stringify(afterReload.vllmIP)}`,
      `  micDevice (untouched)     = ${JSON.stringify(afterReload.micDevice)}`,
      `  speakerDevice (untouched) = ${JSON.stringify(afterReload.speakerDevice)}`,
      `  pttHotkey (untouched)     = ${JSON.stringify(afterReload.pttHotkey)}`,
      `  wakeWordEnabled (untouched) = ${afterReload.wakeWordEnabled}`,
      `  localStorage["vantare_config"] present: ${afterReload.lsRaw !== null}`,
      "",
      "Phase 3 — restore:",
      `  wakeWord     = ${JSON.stringify(restoreResult.wakeWord)}`,
      `  sensitivity  = ${restoreResult.sensitivity}`,
      `  serverPort   = ${restoreResult.serverPort}`,
      "",
      `Total elapsed (ms): ${elapsed}`,
      `Console errors: ${consoleErrors.length} (expected backend-related: ${consoleErrors.filter(isExpectedBackendError).length})`,
      `Screenshot: ${EVIDENCE_PNG}`,
    ];
    fs.writeFileSync(EVIDENCE_TXT, evidenceLines.join("\n") + "\n", "utf8");

    // No UNEXPECTED console errors (allow the same backend noise as T13).
    const unexpectedErrors = consoleErrors.filter((t) => !isExpectedBackendError(t));
    if (unexpectedErrors.length > 0) {
      // eslint-disable-next-line no-console
      console.log("Unexpected console errors:\n" + unexpectedErrors.map((e) => "  " + e).join("\n"));
    }
    expect(unexpectedErrors).toEqual([]);

    // -----------------------------------------------------------------
    // LEARNINGS — append a T15 block to the shared learnings file
    // -----------------------------------------------------------------
    fs.mkdirSync(path.dirname(LEARNINGS_MD), { recursive: true });
    const stamp = new Date().toISOString();
    const learningBlock = [
      "",
      `## T15 — Frontend config persistence across reload (${stamp})`,
      "",
      "**Status:** test created, passes (write -> reload -> read cycle).",
      "",
      "**File:** `frontend/e2e/config-persistence.spec.ts`",
      "",
      "**Approach (no app code changes):**",
      "- `page.evaluate()` dynamically imports `/src/store/config.ts`",
      "  (Vite serves source modules at the .ts path in dev) and calls",
      "  `useAppStore.getState().updateConfig({...})` — the same setter",
      "  the ConfigTab UI uses.",
      "- Three sentinels are written (string `wakeWord`, number",
      "  `sensitivity`, number `serverPort`) so both string and number",
      "  fields are exercised.",
      "- After `page.reload()` we re-import the store module (Vite",
      "  re-serves it, the store factory re-runs, and `loadSavedConfig()`",
      "  pulls the values back from `localStorage.getItem('vantare_config')`).",
      "- Untouched fields are asserted to equal the original values,",
      "  proving the persistence is field-granular, not a wholesale",
      "  overwrite of the AppConfig shape.",
      "- Phase 3 restores the original values so the test is idempotent",
      "  and leaves no residue for the next run.",
      "",
      "**Findings:**",
      `- Backend reachability (port 8008): ${backendReachable ? "UP" : "DOWN (expected in test env)"}`,
      `- updateConfig writes through to localStorage key: "vantare_config"`,
      `- After reload: wakeWord/sensitivity/serverPort survived exactly`,
      `- localStorage still contains the sentinel values after reload`,
      `- Untouched fields (vllmIP, micDevice, speakerDevice, pttHotkey,`,
      `  wakeWordEnabled) all matched the initial values byte-for-byte`,
      "",
      "**Gotchas:**",
      "- The setter on the store is `updateConfig(partial)`, not",
      "  `setConfig(...)` — the plan doc used the wrong name.",
      "- `updateConfig` does NOT validate the partial: it just spreads",
      "  it over the current config and writes the whole new object to",
      "  localStorage. So sending `{ wakeWord: '...' }` is enough to",
      "  mutate that single field while leaving the rest alone.",
      "- On reload the store factory re-runs `loadSavedConfig()`, which",
      "  falls back to hard-coded defaults if `localStorage` is empty",
      "  or unparseable — useful behavior to know for negative tests.",
      "- The plan mentioned testing `.env` hot-reload, but T15 is a",
      "  frontend-only test and the backend `.env` flow is out of scope",
      "  (it would belong in a backend integration test instead).",
      "",
    ].join("\n");
    fs.appendFileSync(LEARNINGS_MD, learningBlock, "utf8");
  });
});
