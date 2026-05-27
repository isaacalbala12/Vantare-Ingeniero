# Deuda Técnica: ¿Migrar a Rust?

> **Contexto:** 27 mayo 2026. Después del análisis de calidad completo, surgió la pregunta
> de si valdría la pena migrar componentes a Rust para mejorar eficiencia.
>
> **Veredicto:** ❌ **No recomendado.** El cuello de botella real (LLM ~1-3s) hace que
> cualquier ganancia en Python/Rust sea imperceptible para el usuario.

---

## Análisis por Componente

| Componente | Lenguaje actual | Líneas | ¿Mover a Rust? | Ganancia estimada |
|------------|:---------------:|:------:|:--------------:|:-----------------:|
| Backend lógico (FastAPI) | Python | 4,978 | ❌ No | ~5ms en un pipeline de 1-3s |
| Frontend (React + Zustand) | TypeScript | 3,510 | ❌ No | 0 (WebView2 corre JS igual) |
| Sidecar Windows | Python | 519 | ⚠️ Quizás | ~10ms, PyInstaller ya resuelve el deploy |
| Tauri shell | **Ya Rust** | 149 | ✅ Ya está | — |
| Shared libs | Python | 3,597 | ❌ No | Sin GIL en sidecar, pero coste alto |
| LLM (Qwen) | C++ (Hipfire) | — | N/A | Lenguaje irrelevante |

### ¿Por qué NO?

**1. El 99% del tiempo es el LLM**
```
Pipeline completo (evento → piloto oye):
├── Shared memory read:  <1ms
├── Python strategy:     ~5ms    ← 0.5%
├── WebSocket:           ~3ms    ← 0.3%
├── LLM (Qwen 3.5 4B):  1-3s    ← 99% 🔴
├── TTS (Edge/Azure):    ~300ms  ← ~0.2%
└── Audio playback:      ~50ms
```

Rust ganaría ~10ms en un pipeline de 1-3 segundos. **Imperceptible.**

**2. El ecosistema Python/TypeScript es el correcto para este proyecto**
- Desarrollo 3-5x más rápido que Rust
- FastAPI + Pydantic + ChromaDB no tienen equivalentes maduros en Rust
- El frontend React no puede ser nativo Rust (WebView2 corre JS)
- WASM (Yew/Dioxus) añade 2MB+ de bundle y pierde acceso al ecosistema React

**3. El sidecar ya tiene solución**
- PyInstaller lo empaqueta como `.exe` (sin dependencia de Python)
- La ganancia de Rust (~10ms sin GIL) no justifica reescribir 519 líneas

### ¿Dónde YA tenemos Rust?

La shell de Tauri (149 líneas) ya es Rust. Es exactamente donde debe estar:
- Gestión de procesos (sidecar)
- Bandeja del sistema (tray icon)
- Atajos globales de teclado
- Pre-calentamiento de micrófono

Esto es correcto. Tauri usa Rust para lo que Rust hace mejor: control de sistema operativo.

### ¿Cuándo tendría SENTIDO Rust?

| Escenario | Justificación |
|-----------|--------------|
| El sidecar necesita ser un producto standalone sin Python **y** sin Linux | ✅ Posible, pero PyInstaller ya lo resuelve |
| Aparece un cuello de botella en CPU que Rust elimina (no redes ni LLM) | ✅ Entonces sí |
| El frontend necesita WebGL/WebGPU pesado para visualización 3D | ⚠️ WASM podría tener sentido |
| El proyecto se vuelve 10x más grande y la mantenibilidad del Python es insostenible | ✅ Entonces considerar |

**Ninguno de estos escenarios se da hoy.**

### Opinión

> **No migrar a Rust.** El stack actual (Python FastAPI + React/TS + Tauri Rust shell)
> es la combinación óptima para un proyecto de este tamaño y naturaleza.
>
> El tiempo y esfuerzo que llevaría reescribir cualquiera de los componentes en Rust
> (~3-6 meses para el backend) se invierte mejor en:
> 1. Reducir complejidad del código Python existente (R1-R4, ~16h)
> 2. Completar Fase 7 (sidecar + Tauri, ~6.5h)
> 3. Optimizar el LLM (modelo más pequeño, cuántico, speculative decoding)
>
> **Donde ya estamos en Rust (Tauri shell), estamos bien. Donde no lo estamos,
> no merece la pena moverlo.**

---

## Documentos Relacionados

| Documento | Contenido |
|-----------|-----------|
| `docs/ai/2026-05-27-quality-analysis-findings.md` | Análisis de calidad completo |
| `docs/ai/2026-05-27-security-audit.md` | Auditoría de seguridad |
| `docs/ai/orchestrator.md` | Estado del proyecto y roadmap |
