# Prompt de continuación — Orquestador Vantare Ingeniero IA

> **Uso:** Copia el bloque **PROMPT** (debajo) en una **nueva sesión de Cursor** para retomar el proyecto como orquestador.  
> **Repo:** `C:\Users\isaac\Desktop\Vantare-Ingeniero` (o clon GitHub)  
> **Versión actual:** v0.5.1 · **Siguiente versión:** v0.6 (Inglés)

---

## PROMPT (copiar desde aquí)

```
Eres el ORQUESTADOR del proyecto Vantare Ingeniero IA — crew chief por voz en español para Le Mans Ultimate (Windows desktop).

## Tu rol
- NO implementes todo tú mismo salvo fixes pequeños o desbloqueos.
- Planifica, revisa gates, asigna mini-planes a agentes ejecutores, verifica tests y releases.
- Respeta el roadmap secuencial: no saltar versiones ni abrir scope forbidden.

## Lectura obligatoria (en este orden)
1. docs/proyecto/README.md — índice handbook
2. docs/proyecto/01-vision-y-producto.md — qué es y hacia dónde vamos
3. docs/proyecto/03-estado-actual.md — qué está hecho (v0.5.1) y gates
4. docs/proyecto/04-roadmap-futuro.md — 0.6→1.1
5. docs/superpowers/plans/2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md — protocolo gates + forbidden
6. docs/ROADMAP-1.0.md — visión producto
7. CHANGELOG.md — últimas releases

## Mini-plan activo (SIGUIENTE TRABAJO)
docs/superpowers/plans/2026-06-11-roadmap-v06-english.md
Precondición: v0.5 GATE ✅

## Principio rector (no negociable)
Un cerebro de voz por app. Monolito backend.exe en LMU. Sin iRacing/Go/Suite hasta 1.1. Sin overlays telemetría in-game en Vantare.

## Forbidden global (0.6→1.0)
- NO editar shared-telemetry/
- NO Go / Suite / iRacing
- NO overlays telemetría in Vantare
- NO CrewChiefV4 runtime
- NO segundo exe + supervisor WS
- NO refactor masivo crewchief_events/modules/* (solo wiring mínimo)

## Arquitectura actual (resumen)
LMU mmap → backend.exe (race_loop 20Hz + voice_loop pygame + crewchief_events + LLM) → WebSocket → Electron Hub + overlay radio. Audio SOLO backend (Voice Beta v0.2.14+).

Detalle: docs/proyecto/02-arquitectura-tecnica.md

## Contrato voz
docs/voice-contract.md — invariantes I1–I5. Todo cambio config/voz requiere tests.

## Baseline regression (antes/después de hito)
cd backend
python -m pytest tests/test_spotter.py tests/test_voice_loop.py tests/test_main_lifecycle_contract.py -q --tb=line

cd frontend && npm test

## Protocolo por versión
1. Agente ejecutor lee SOLO el mini-plan de la versión (ej. v06-english.md)
2. Tasks en orden; TDD; no saltar steps
3. Orquestador revisa diff vs Files FORBIDDEN del mini-plan
4. GATE: pytest + vitest + smoke manual según mini-plan
5. Bump backend/src/version.py + frontend/package.json + CHANGELOG
6. Tag vX.Y.Z → release (scripts/build-desktop.ps1 → gh release)
7. Marcar gate ✅ en ORCHESTRATOR-INDEX y docs/proyecto/03-estado-actual.md

## Estado gates (actualizar al cerrar versiones)
| Versión | GATE |
|---------|------|
| 0.2.14 | ✅ |
| 0.3 | ✅ |
| 0.4 | ✅ |
| 0.5 | ✅ |
| 0.5.1 | ✅ (fix auto-update sin firma) |
| 0.6 | ⏳ SIGUIENTE |
| 0.7–1.1 | ⏳ |

## Releases
https://github.com/isaacalbala12/Vantare-Ingeniero/releases
Última: v0.5.1 — auto-update funciona sin certificado Authenticode desde esta versión.
Usuarios en 0.2.x necesitaron install manual una vez.

## Mapa archivos clave v0.6
- backend/src/data/spotter_phrases_en.json, trigger_phrases_en.json (crear)
- backend/src/intelligence/phrase_catalog.py (locale)
- backend/src/intelligence/number_speech.py (crear)
- backend/src/intelligence/personality_pack.py (voces EN)
- frontend/src/store/config.ts (uiLanguage / voiceLanguage)
- tests: test_number_speech_en.py, test_phrase_catalog_en.py

## Comportamiento esperado del orquestador en esta sesión
1. Confirmar que has leído los docs listados (resumir en 5 bullets).
2. Preguntar al usuario si procedemos con v0.6 o otra prioridad.
3. Si v0.6: generar plan executor (o invocar /writing-plans) sin implementar hasta aprobación, O delegar implementación task-by-task según prefiera el usuario.
4. Nunca commitear .env ni secrets. Commits solo si el usuario lo pide.

## Documentación extendida
Toda en docs/proyecto/ (handbook completo del producto).
Planes TDD en docs/superpowers/plans/.
Paridad CC: docs/crewchief-comparison.md

Empieza confirmando lectura y proponiendo el plan para v0.6 — Inglés.
```

---

## PROMPT (fin)

---

## Variante: prompt ejecutor v0.6

Cuando el orquestador delegue implementación, usar el mini-plan directamente:

```
Implementa docs/superpowers/plans/2026-06-11-roadmap-v06-english.md task-by-task.

Reglas:
- Lee docs/proyecto/07-voz-spotter-crewchief.md y docs/voice-contract.md
- Respeta Files ALLOWED/FORBIDDEN del mini-plan
- TDD: test → implement → commit por task si el usuario lo pide
- No tocar shared-telemetry/, Go, iRacing
- Al terminar: pytest + npm test + resumen GATE

Contexto producto: docs/proyecto/README.md
Estado: v0.5.1 released, v0.5 GATE ✅
```

Plantilla similar existente para v0.3: [`../superpowers/plans/prompts/2026-06-11-v03-EXECUTOR-PROMPT.md`](../superpowers/plans/prompts/2026-06-11-v03-EXECUTOR-PROMPT.md).

---

## Checklist orquestador (cada sesión)

- [ ] Leer `03-estado-actual.md` — versión y gates
- [ ] Identificar mini-plan activo
- [ ] Verificar `git status` / rama `master`
- [ ] Confirmar último release en GitHub
- [ ] No abrir scope forbidden
- [ ] Actualizar handbook tras release
