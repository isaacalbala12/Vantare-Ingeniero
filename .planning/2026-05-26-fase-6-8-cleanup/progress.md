# Progress Log — Fase 6-8 Cleanup

## 2026-05-26

### Session Start
- **Action**: Created planning files (.planning/2026-05-26-fase-6-8-cleanup/)
- **Findings**: T6.1 y T6.2 ya completadas — tests existentes pasan con router real y VLLMClient
- **Remaining**: T6.3 (3 TS6133), T8.3 (advice_id logging), T8.4 (RuntimeError WS)

### Phase 1 Complete
- ✅ Verificado T6.1: 8/8 tests TTS pasan, usan router real
- ✅ Verificado T6.2: 4/4 tests LLM pasan, usan VLLMClient
- ✅ Identificados 3 TS6133: App.tsx(sendBinary), audioQueue.test.ts(vi), configStore.test.ts(AppConfig)
- ✅ Mapeados puntos de log sin advice_id en engine.py y llm_client.py
- ✅ Localizado punto de desconexión en websocket.py L174
