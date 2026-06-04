# LLM Migration

**Purpose:** Capture the current state of the LLM integration, the new architecture the user is moving to, the impact on existing code, the impact on tests, and a migration checklist. This is reference documentation, not a plan with dates.

---

## Current State

The backend talks to a VLLM-compatible OpenAI-style API at the URL configured in `LLM_BASE_URL` (read from `backend/.env`). The client is `VLLMClient` in `backend/src/intelligence/llm_client.py`. The model name comes from `LLM_MODEL`. The API key from `LLM_API_KEY`.

The LLM is used by the PTT (push-to-talk) workflow: the pilot presses the PTT hotkey, the audio is captured, transcribed, sent to the LLM with the live race context, and the LLM streams back an `advice_start` / `advice_token` / `advice_end` sequence over WebSocket to the frontend, which renders it in the radio overlay and queues it for TTS playback.

The LLM server is **currently down** ("server en reparación"). PTT and any other LLM-dependent workflow is therefore excluded from the pipeline review's scope. The Phase 4 stack-dev smoke was deferred with the user notified (per `.omo/plans/pipeline-review.md:1024`).

What still works without the LLM:

- CrewChief events (12 categories) — they fire on telemetry conditions, not LLM
- Spotter (deterministic + cartesian) — pure logic, no LLM
- Strategy sidecar (shared-strategy engine) — pure logic, no LLM
- WebSocket broadcast (crewchief_alert, strategy, telemetry binary)
- Config persistence (localStorage + .env)

What does NOT work without the LLM:

- PTT voice chat (the pilot cannot ask the LLM anything)
- LLM-driven advice (the radio overlay cannot show streamed tokens)
- TTS playback of LLM responses (no LLM response to TTS)
- The `/health` endpoint's `llm: true` field flips to `llm: false` (the lifespan tries to ping the LLM and fails)

---

## New Architecture

The user said: "The LLM server is being completely replaced. It will be a specific API and personal subscription that will be exposed (not directly, logically) along with the clients."

Three things to extract from this:

1. **Specific API, not OpenAI-compatible.** The new server is a custom API. The `VLLMClient` (which uses the `openai` SDK with `AsyncOpenAI(base_url=...)`) is the wrong abstraction. The client will need to be rewritten for the new protocol.

2. **Personal subscription.** The LLM credentials are per-user, not a shared service. This means the credentials cannot live in `backend/.env` (which is committed per `AGENTS.md`). The credentials have to be supplied at runtime by the user.

3. **Exposed through clients, not directly from backend.** The user said "exposed (not directly, logically) along with the clients". The interpretation: the clients (frontend Tauri, possibly the sidecar) hold the subscription credentials and make LLM calls directly, OR a thin proxy in the backend holds credentials and the clients go through that proxy. Either way, the backend does not have its own LLM_API_KEY in the way it does today.

---

## Impact on Existing Code

### `backend/src/intelligence/llm_client.py` (rewritten or replaced)

`VLLMClient.__init__` reads `settings.LLM_API_KEY`, `settings.LLM_BASE_URL`, `settings.LLM_MODEL`. The constructor warns when `LLM_API_KEY` is empty. The `AsyncOpenAI(base_url=..., api_key=..., timeout=...)` initialization is OpenAI-specific. All of this needs to change.

The streaming methods (`stream_advice`, `stream_pilot_response`, `evaluate_cycle` via `IntelligenceEngine`) emit `AdviceStartMessage`, `AdviceTokenMessage`, `AdviceEndMessage` over the broadcaster. The Pydantic message shapes (`src/models/messages.py`) are stable and can stay. The HTTP client, retry logic, timeout handling, and request shape need to be replaced with the new API's protocol.

### `backend/src/config/settings.py` (env keys change)

Current keys (from `backend/src/config/settings.py`):

```
LLM_API_KEY      (committed empty in .env)
LLM_BASE_URL     (committed in .env)
LLM_MODEL        (committed in .env)
```

After the migration:

- `LLM_API_KEY` is removed (no longer a server-side secret)
- `LLM_BASE_URL` may stay (the proxy endpoint, if there is one) or be removed (if the client talks to the LLM directly)
- `LLM_MODEL` may stay (the user picks the model)
- A new key like `LLM_PROXY_URL` or `LLM_CLIENT_CONFIG` is added if there is a proxy

The `.env` file is intentionally committed (per `AGENTS.md`), so any change to its keys is a public commit. Document the change in the commit message.

### `backend/src/routers/llm.py` (signature changes)

The `/llm/*` endpoints that the frontend calls (PTT, advice streaming) currently proxy through the backend. With the new architecture, the frontend may call the LLM directly. The endpoints might become a no-op (return 410 Gone) or be removed entirely.

The Phase 3 test `ws-connection.spec.ts` and the unit test `test_useWebSocket.test.ts` exercise the PTT flow indirectly. They will need updates.

### Frontend PTT workflow (`frontend/src/hooks/usePTT.ts`, `useAudioCapture.ts`)

The current PTT flow is:

1. Pilot presses PTT hotkey.
2. `useAudioCapture` records microphone audio.
3. Audio is sent over WS as binary to `ws://vllmIP:serverPort/ws` (the `/ws` endpoint in `websocket.py:251`).
4. Backend receives, transcribes (or forwards), calls LLM, streams response back.

After the migration, the audio is probably sent directly from the frontend to the new LLM API, OR the backend proxy is a thin pass-through. Either way, the WS payload shape and the binary encoding may change.

### `frontend/src/store/config.ts`

The store has `vllmIP` and `serverPort` fields. These are used by `useWebSocket.ts:108-110` to build the WS URL. If the LLM connection is no longer via the backend, the `vllmIP` field is repurposed (or removed) and the user enters the new LLM API endpoint.

The T15 test (`config-persistence.spec.ts`) currently asserts on `wakeWord`, `sensitivity`, `serverPort`. The `serverPort` assertion survives the migration. The T15 test does not need changes for the LLM migration, but Phase 3 / Phase 4 may add a new test for the new LLM API endpoint config.

### `.env` files

`backend/.env` has LLM-related keys. After the migration, those keys are removed (or repointed to a proxy). The frontend may need a new config screen for the personal subscription credentials (probably stored in OS keychain, not `.env` or `localStorage`).

---

## Impact on Tests

### Tests Excluded From the Pipeline Review

The plan explicitly excluded PTT from the review's scope. The plan reference is `.omo/plans/pipeline-review.md:17` ("LLM server is down — PTT workflow EXCLUDED from scope"). No PTT E2E tests were written. The unit tests for `llm_client.py` (`test_llm_client_advanced.py`, `test_llm_async.py`, `test_llm_router.py`) are not in the new test suite and were not modified.

### Tests That Will Need Updates After the Migration

When the new LLM server is in place, the following tests will need updates:

1. **`backend/tests/test_llm_client_advanced.py`** (and similar). The mock the old `VLLMClient` used is no longer valid. Rewrite to mock the new API. If the new API is not OpenAI-compatible, the test imports change entirely.
2. **`backend/tests/test_llm_async.py`**. Same as above.
3. **`backend/tests/test_llm_router.py`**. The router endpoints change.
4. **`frontend/src/__tests__/useWebSocket.test.ts`** (if it covers PTT). The WS payload shape may change.
5. **`frontend/src/__tests__/appStore.test.ts`** (if it covers PTT). The store actions may change.

### New Tests Needed After the Migration

1. **PTT E2E backend test.** The original Phase 1 / Phase 2 plan included a "PTT → LLM → advice" E2E. This was deferred. When the LLM is back, the test should follow the same "real components" pattern: real WS, real audio capture (or a fake `AudioCapture`), real LLM call (or a recorded-response fake), real `AdviceEndMessage` broadcast.
2. **LLM health check test.** The `/health` endpoint has an `llm` boolean. The current `test_health.py` may or may not cover this. After the migration, the health check should ping the new API and assert the result.
3. **Frontend PTT test.** The `usePTT` hook will need a Playwright test that exercises the hotkey → audio → WS → advice flow. This was out of scope for Phase 3.
4. **Proxy / direct-client test.** Depending on whether the new architecture is "client → LLM" or "client → backend proxy → LLM", a new test will verify the path. The proxy is the more conservative choice (credentials stay in one place) and the test would assert that the backend holds no LLM_API_KEY in its own env.

### Tests That Will NOT Change

- The 12 CrewChief event tests. The LLM is not in the loop.
- The 32 spotter tests. The LLM is not in the loop.
- The 14 strategy tests. The LLM is not in the loop.
- The 8 frame cache tests. The LLM is not in the loop.
- The 12 multi-client WS tests. The LLM is not in the loop.
- The 4 Playwright frontend tests. The LLM is filtered as an expected backend error.

The pipeline review's value is in those tests catching the 5 real production bugs. The LLM migration does not invalidate that work.

---

## Migration Checklist

This is a non-exhaustive list of touch points. The actual migration will reveal more.

### Pre-migration (now)

- [x] Document the current state and the new architecture (this file).
- [x] Document which tests are excluded (this file + `.omo/plans/pipeline-review.md:17`).
- [x] Snapshot the 5 test files that exercise LLM-adjacent code paths (`test_llm_client_advanced.py`, `test_llm_async.py`, `test_llm_router.py`, `useWebSocket.test.ts`, `appStore.test.ts`).
- [ ] Decide: client → LLM direct, or client → backend proxy → LLM.
- [ ] Decide: where do the credentials live (OS keychain, Tauri store, encrypted `.env`)?

### Migration step 1: backend proxy (if applicable)

- [ ] Define the new LLM client interface (probably in `backend/src/intelligence/llm_client.py`, but rewritten).
- [ ] Update `backend/src/config/settings.py` to drop `LLM_API_KEY` and add the new keys.
- [ ] Update `backend/src/routers/llm.py` (or remove it) to match the new architecture.
- [ ] Update `backend/src/services/audio_player.py` if TTS changes.
- [ ] Run `test_health.py` to confirm the new health check shape.
- [ ] Run the existing Phase 1 backend tests to confirm no regressions in non-LLM paths.

### Migration step 2: frontend

- [ ] Update `frontend/src/store/config.ts` to add/remove the LLM-related fields.
- [ ] Update `frontend/src/hooks/useWebSocket.ts` to use the new payload shapes.
- [ ] Update `frontend/src/hooks/usePTT.ts` if the audio capture → LLM path changes.
- [ ] Update `frontend/src/components/ConfigTab.tsx` to expose the new credentials config UI.
- [ ] Run `npx vitest` to confirm the unit tests still pass.
- [ ] Run `npx playwright test` to confirm the E2E tests still pass (with the backend-down error filter).

### Migration step 3: new tests

- [ ] Write a PTT E2E test that exercises the full flow with the new architecture.
- [ ] Write a LLM health check test.
- [ ] Write a frontend PTT test (Playwright).
- [ ] If a proxy is used, write a test that asserts the backend does not hold credentials in its own env (only the proxy does).

### Migration step 4: documentation

- [ ] Update `backend/AGENTS.md` to reflect the new LLM architecture.
- [ ] Update `backend/.env` (committed per AGENTS.md) with the new keys.
- [ ] Update `frontend/AGENTS.md` to reflect the new PTT flow.
- [ ] Update the user-facing docs (README, install instructions).

---

## Open Questions

These are the questions the migration will surface. They are not blockers for the test review (which is LLM-excluded), but they are blockers for the migration itself.

1. **Direct or proxied?** Client → LLM direct, or client → backend proxy → LLM. Trade-off: direct is simpler and lower latency; proxied keeps credentials in one place and lets the backend add observability, rate limiting, and audit logging.
2. **Credentials storage.** OS keychain, Tauri store, encrypted local file? Each has different security and UX trade-offs.
3. **Streaming protocol.** Server-Sent Events (SSE), WebSocket, gRPC, HTTP chunked? Each has different complexity on the frontend.
4. **Model selection.** User picks the model, or is it fixed by the subscription? Affects whether `LLM_MODEL` stays in config.
5. **Cost / rate limiting.** Who enforces the rate limit? The new API, the client, the proxy? Affects the test surface.
6. **Fallback behavior.** When the LLM is unreachable, does PTT fail silently, queue, or show an error? The current `/health` endpoint surfaces a boolean; the new one may surface more detail.

---

## Cross-References

- `BUGS.md` — Bugs 1-5 are LLM-independent. None of them block the migration.
- `TEST-INVENTORY.md` — which tests are LLM-adjacent and which are not.
- `MAINTENANCE.md` — how to write the new PTT E2E test when the migration lands.
- `ARCHITECTURE.md` — the pipeline diagram shows where the LLM sits today; that section will be redrawn for the new architecture.
- `.omo/plans/pipeline-review.md:17, 471, 1024` — the original PTT-exclusion note.
