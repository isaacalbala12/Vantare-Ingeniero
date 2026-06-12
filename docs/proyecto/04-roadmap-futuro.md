# 04 — Roadmap futuro (0.6 → 1.1)

> Visión extendida: [`../ROADMAP-1.0.md`](../ROADMAP-1.0.md)  
> Orquestación: [`../superpowers/plans/2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md`](../superpowers/plans/2026-06-11-roadmap-1.0-ORCHESTRATOR-INDEX.md)

---

## Mapa visual

```
0.2.14 ──► 0.3 ──► 0.4 ──► 0.5 ──► 0.6 ──► 0.7 ──► 0.8 ──► 0.9 ──► 1.0 ──► 1.1
 stable     voz      UX       persona   EN      ask     pit     ship    clone   iR+Suite
   ✅        ✅       ✅        ✅       NEXT
```

---

## v0.6 — Inglés (SIGUIENTE)

**Objetivo:** Soporte inglés completo para **toda la app**: interfaz Hub/overlay, frases, TTS y números/tiempos. El onboarding con selección inicial de idioma queda fuera de v0.6 y se hará en una versión futura.

| Entregable | Descripción |
|------------|-------------|
| `spotter_phrases_en.json` | Paridad keys con ES |
| `trigger_phrases_en.json` | Triggers P0 en EN |
| `PhraseCatalog` locale-aware | `load(locale="es"\|"en")` |
| `number_speech.py` | Gaps/tiempos estilo CC NumberProcessing |
| Hub + overlay | UI principal localizada con `uiLanguage` |
| Config idioma | Selector simple `uiLanguage` / `voiceLanguage` sin onboarding |
| TTS | Voces EN por perfil en PersonalityPack |

**Regla de implementación:** hacerlo de la forma más sencilla posible: diccionario de strings pequeño y explícito en frontend, sin librería i18n pesada, sin refactor masivo de componentes y sin cambiar arquitectura.

**Mini-plan:** [`../superpowers/plans/2026-06-11-roadmap-v06-english.md`](../superpowers/plans/2026-06-11-roadmap-v06-english.md)  
**Precondición:** v0.5 GATE ✅

---

## v0.7 — Comandos ingeniero (PTT consultable)

**Objetivo:** Preguntas tipo "¿cuánta gasolina me queda?" con **datos deterministas** + LLM solo redacta.

| Tool | Fuente datos |
|------|--------------|
| fuel | StrategyService / telemetría |
| damage | damage_report / CC module |
| tyres | tyre monitor |
| gaps | timings |
| opponents | opponent tracker |
| session time | race time module |

**Patrón:** tool → dato duro → LLM formatea (prohibido inventar cifras).

**Mini-plan:** [`../superpowers/plans/2026-06-11-roadmap-v07-engineer-commands.md`](../superpowers/plans/2026-06-11-roadmap-v07-engineer-commands.md)

---

## v0.8 — Pit Manager LMU

**Objetivo:** Configurar boxes por voz con confirmación + escritura REST LMU.

| P0 | API |
|----|-----|
| Fuel add / to end | REST PitMenu |
| Tyres all/front/rear | REST |
| Repairs none/body/all | REST |
| Virtual energy % | LMU-specific |
| Fuel ration % | LMU-specific |

**Guard:** solo en pit lane / menú válido.

Referencia CC: `PitManagerEventHandlers_LMU.cs` (solo lectura conceptual).

**Mini-plan:** [`../superpowers/plans/2026-06-11-roadmap-v08-pit-manager-lmu.md`](../superpowers/plans/2026-06-11-roadmap-v08-pit-manager-lmu.md)

---

## v0.9 — Hardening LMU (ship quality)

**Objetivo:** Producto listo para usuarios exigentes sin abrir iRacing.

| Entregable |
|------------|
| `verify-release.ps1` + `verify_beta_gate.ps1` green |
| Auto-update E2E CI → Hub |
| `duck_lmu.exe` en bundle |
| Evidencia **≥3 circuitos × ≥2 condiciones** |
| Sin launcher, sin Go, sin iRacing |

**Mini-plan:** [`../superpowers/plans/2026-06-11-roadmap-v09-hardening-lmu.md`](../superpowers/plans/2026-06-11-roadmap-v09-hardening-lmu.md)

---

## v1.0 — Clonación de voz

**Objetivo:** Un timbre clonado por perfil + fallback Gemini/Edge.

| Entregable |
|------------|
| Flujo consentimiento + muestra audio mínima |
| Integración TTS clonado en `TTSManager` |
| Release stable (no pre-release) |

**Mini-plan:** [`../superpowers/plans/2026-06-11-roadmap-v10-voice-clone.md`](../superpowers/plans/2026-06-11-roadmap-v10-voice-clone.md)

---

## v1.1 — iRacing + Suite Go

**Objetivo:** Segundo sim + convivencia opcional con overlay Go (repo externo).

| Fase | Entregable |
|------|------------|
| 1.1a | Read iRSDK + session state |
| 1.1b | Spotter iRacing |
| 1.1c | Triggers endurance iRacing |
| 1.1d | Pit/comandos iRacing |
| 1.1e | Selector sim + Suite launcher opcional |

**Requisito:** `shared-telemetry` Rust con mappers LMU + iRacing.

**Mini-plan:** [`../superpowers/plans/2026-06-11-roadmap-v11-iracing-suite.md`](../superpowers/plans/2026-06-11-roadmap-v11-iracing-suite.md)

---

## Forbidden global (0.6 → 1.0)

No implementar hasta la versión indicada:

| Prohibido | Hasta |
|-----------|-------|
| Edits `shared-telemetry/` | 1.1 |
| Go / Suite / iRacing | 1.1 |
| Overlays telemetría in Vantare | nunca (1.1 = Go aparte) |
| CrewChiefV4 runtime | nunca |
| Segundo exe + supervisor WS | nunca (ADR-004-R1) |
| Refactor masivo `crewchief_events/modules/*` | salvo wiring mínimo por versión |

---

## Criterio para pasar de versión (GATE)

1. Todos los tasks del mini-plan ✅
2. pytest + vitest del mini-plan green
3. Orquestador revisa diff vs **Files FORBIDDEN** del mini-plan
4. Invariantes I1–I5 voice contract sin regresión
5. Bump version + CHANGELOG + tag + release
6. Smoke manual según checklist versión

Protocolo anti-gap: trace-the-flag con `rg`, tests reales (no placeholders), segunda vía config/WS.
