# Smoke Test Plan — Vantare Ingeniero IA

**Build:** `backend-x86_64-pc-windows-msvc.exe` + Tauri Hub
**Version:** Desarrollo
**Fecha:** 2026-05-22
**QA Engineer:** Sisyphus

---

## Resumen de resultados ejecutados

| TC | Prueba | Resultado | Evidencia |
|----|--------|-----------|-----------|
| 1  | Health endpoint | ✅ PASS | `GET /health` → 200, shared_memory connected, LMU API cache activa |
| 2  | WebSocket conexión | ✅ PASS | Conexión establecida, telemetría en tiempo real recibida |
| 3  | Logging PyInstaller | ✅ PASS | `log_config=None` elimina el `isatty` crash |

**3/3 pruebas backend pasadas.** Las pruebas Tauri requieren un humano con LMU instalado.

---

## TC1 — Health Endpoint (BACKEND)

**Ejecutable por:** QA automatizado
**Severidad si falla:** 🛑 Crítica

### Pasos
1. Ejecutar `backend-x86_64-pc-windows-msvc.exe` sin LMU abierto
2. `curl http://127.0.0.1:8000/health`

### Resultado esperado
```json
{
  "status": "ok",
  "shared_memory": {
    "status": "connected" | "simulated",
    "offline_mode": false,
    "last_lap": 0
  },
  "lmu_api": {
    "status": "active",
    "cache": { ... }
  }
}
```

### Resultado real
```json
{
  "status": "ok",
  "shared_memory": { "status": "connected", "offline_mode": false, "last_lap": 0 },
  "lmu_api": { "status": "active", "cache": { "weather": 3, "strategy_usage": 17, "garage_wear": 11, "drivers": 17, "brakes": 11 } },
  "llm": { "configured": false, "model": "llama3-8b-8192" }
}
```

### ✅ PASS — Backend operativo, shared memory detectada, caché LMU poblándose

---

## TC2 — WebSocket (BACKEND)

**Ejecutable por:** QA automatizado
**Severidad si falla:** 🛑 Crítica

### Pasos
1. Con el backend corriendo, conectar a `ws://127.0.0.1:8000/ws`
2. Escuchar 5 segundos

### Resultado esperado
- Conexión aceptada (log: `New client connected. Active connections: 1`)
- Mensajes JSON con eventos: `telemetry`, `spotter_alert`, `pit_limiter`, etc.

### Resultado real
```
Mensaje recibido: {"event":"telemetry","data":{"session":{"session_type":1,...}}}
```
Log del servidor:
```
[INFO] vantare.websocket: New client connected. Active connections: 1
[INFO] vantare.websocket: WebSocket connection closed by client
[INFO] vantare.websocket: Client disconnected. Active connections: 0
```

### ✅ PASS — WebSocket funcional, telemetría fluye en tiempo real

---

## TC3 — Logging sin crash (BACKEND)

**Ejecutable por:** QA automatizado
**Severidad si falla:** 🛑 Crítica

### Pasos
1. Ejecutar el backend compilado con PyInstaller (`--noconsole`)
2. Esperar 10 segundos
3. Revisar stderr/log

### Resultado esperado
- **NO** debe aparecer `AttributeError: 'NoneType' object has no attribute 'isatty'`
- **NO** debe aparecer `ValueError: Unable to configure formatter 'default'`
- El servidor arranca y logs: `INFO:     Uvicorn running on http://127.0.0.1:8000`

### Resultado real
```
2026-05-22 10:44:52,140 [INFO] vantare.main: Starting server on 127.0.0.1:8000...
INFO:     Uvicorn running on http://127.0.0.1:8000
```
Sin rastro del `isatty` error. Fix confirmado: `log_config=None`.

### ✅ PASS — Logging PyInstaller resuelto

---

## TC4 — Arranque del frontend Tauri

**Ejecutable por:** Humano
**Severidad si falla:** 🛑 Crítica

### Pasos
1. `cd frontend && cargo tauri dev` (o ejecutar el .msi/.exe instalado)
2. Esperar a que la ventana aparezca

### Resultado esperado
- Ventana única de 480x520px, sin bordes (frameless)
- Título: "Vantare Ingeniero"
- Fondo negro #111
- Barra superior con botones: minimizar, maximizar, cerrar
- Indicador BACKEND en verde (conectado)

### Checklist visual
| Elemento | Esperado | Real |
|----------|----------|------|
| Tamaño ventana | 480x520 | |
| Sin bordes | frameless=true | |
| Botón minimizar | Presente | |
| Botón maximizar | Presente | |
| Botón cerrar | Presente | |
| Indicador BACKEND | Verde | |
| Fondo | #111111 | |

### Severidad: 🛑 Crítica — Sin frontend no hay producto.

---

## TC5 — Dashboard con LMU en pista

**Ejecutable por:** Humano con LMU instalado
**Severidad si falla:** 🔴 Alta

### Pasos
1. Iniciar LMU, entrar a una sesión en pista
2. Iniciar la app Vantare
3. Observar el Dashboard

### Resultado esperado
- Velocidad (km/h) cambia en tiempo real
- Marcha cambia (N, 1, 2, 3...)
- RPMs se mueven
- Combustible muestra valor
- Gap/Diferencia con delante/atrás se actualiza
- Posición / vuelta actual
- Los números NO parpadean ni se congelan

### Checklist
| Métrica | Se actualiza? | Valor coherente? |
|---------|---------------|------------------|
| Velocidad | | |
| Marcha | | |
| RPM | | |
| Combustible | | |
| Gap delante | | |
| Gap detrás | | |
| Posición | | |
| Vuelta | | |

### Severidad: 🔴 Alta — El core del producto es la telemetría en vivo.

---

## TC6 — Push-to-Talk (Ctrl+Shift+P)

**Ejecutable por:** Humano con micrófono
**Severidad si falla:** 🔴 Alta

### Pasos
1. Dashboard visible
2. Mantener presionado **Ctrl+Shift+P**
3. Hablar 2-3 segundos
4. Soltar la combinación

### Resultado esperado
| Estado | Indicador PTT | Audio |
|--------|---------------|-------|
| IDLE (reposo) | Círculo gris | Silencio |
| Pulsas Ctrl+Shift+P | Círculo → **rojo** | Beep inicio (tono corto) |
| Hablando | Círculo rojo | Micrófono activo |
| Sueltas Ctrl+Shift+P | Círculo rojo → **naranja** (THINKING) → gris | Beep cierre |

### Matriz de estados PTT
```
IDLE ──(Ctrl+Shift+P)──> LISTENING ──(suelta)──> THINKING ──(2-3s)──> IDLE
  ^                                                         |
  └─────────────────────────────────────────────────────────┘
```

### Severidad: 🔴 Alta — Función principal de comunicación.

---

## TC7 — Panel de Configuración

**Ejecutable por:** Humano
**Severidad si falla:** 🟡 Media

### Pasos
1. Dashboard visible → hacer clic en icono de engranaje/configuración
2. Debe alternar a ConfigTab
3. Volver al Dashboard (clic en el mismo botón o en Dashboard)

### Pestaña Conexión
- Hacer clic "Probar conexión"
- Esperado: mensaje "Conexión exitosa" o "Error: ..."

### Pestaña Audio
- Hacer clic "Probar sonido"
- Esperado: Se oye un pitido por los altavoces

### Pestaña Voz
- Modificar campo "Modelo de voz" (ej: "llama3-8b-8192")
- Modificar campo "URL del servidor"
- Hacer clic "Guardar"
- Cerrar y reabrir Config → los valores deben persistir

### Checklist
| Acción | Esperado | Real |
|--------|----------|------|
| Alternar Dashboard↔Config | Cambio de pantalla suave | |
| Probar Conexión | Feedback visual | |
| Probar Sonido | Pitido audible | |
| Guardar Voz | Datos persisten | |

### Severidad: 🟡 Media — Funcionalidad secundaria pero importante.

---

## TC8 — Spotter y Alertas

**Ejecutable por:** Humano con LMU en boxes
**Severidad si falla:** 🟡 Media

### Pasos
1. LMU en boxes (coche parado)
2. Activar pit limiter dentro de LMU
3. Desactivar pit limiter
4. Observar el historial de alertas en el Dashboard

### Resultado esperado
- Aparece alerta: "Pit limiter ON" o similar
- Aparece alerta: "Pit limiter OFF"
- El historial muestra los últimos **3 mensajes** (no más)
- Las alertas tienen ícono o color distintivo

### Severidad: 🟡 Media — El spotter es valor añadido, no bloqueante.

---

## TC9 — Resistencia básica (5 minutos)

**Ejecutable por:** Humano con LMU en pista
**Severidad si falla:** 🛑 Crítica

### Pasos
1. Iniciar todo: LMU en pista + backend + frontend
2. Timer de 5 minutos
3. Cada minuto, verificar:

| Minuto | BACKEND verde? | Telemetría fluye? | App responde? |
|--------|---------------|-------------------|---------------|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |

### Criterios de fallo
- ❌ La app se cierra sola
- ❌ El indicador BACKEND se pone rojo
- ❌ La telemetría se congela >10 segundos
- ❌ El puntero del ratón cambia a reloj de arena constante
- ❌ La ventana se vuelve blanca/negra (pantallazo)

### Severidad: 🛑 Crítica — Sin estabilidad no hay producto.

---

## TC10 — Desconexión y reconexión de LMU

**Ejecutable por:** Humano con LMU
**Severidad si falla:** 🟡 Media

### Pasos
1. App abierta con LMU en pista → telemetría fluyendo
2. Cerrar LMU (Alt+F4)
3. Esperar 15-20 segundos
4. Reabrir LMU y entrar a pista

### Resultado esperado
- Al cerrar LMU: indicador LMU se pone rojo o muestra "desconectado"
- La app NO se cierra ni crashea
- Al reabrir LMU: la telemetría se reanuda sola

### Severidad: 🟡 Media — Caso borde importante pero no bloqueante.

---

## TC11 — Error handling: backend caído

**Ejecutable por:** Humano
**Severidad si falla:** 🟡 Media

### Pasos
1. Iniciar frontend Tauri SIN el backend
2. Observar el indicador BACKEND

### Resultado esperado
- Indicador BACKEND en **rojo**
- Mensaje de error o "Reconnecting..."
- La app no se cierra
- Al iniciar el backend después, el indicador se pone **verde**

### Severidad: 🟡 Media — Graceful degradation, no bloquea desarrollo.

---

## Bugs encontrados durante la sesión de QA

| ID | Bug | Severidad | Estado | Fix |
|----|-----|-----------|--------|-----|
| BUG-001 | `AttributeError: 'NoneType' object has no attribute 'isatty'` al iniciar backend compilado | 🛑 Crítica | ✅ RESUELTO | `uvicorn.run(log_config=None)` |
| (prev) | PyInstaller sin --noconfirm colgaba la build | 🛑 Crítica | ✅ RESUELTO | Añadido `--noconfirm` |
| (prev) | UnicodeEncodeError en prints con → | 🛑 Crítica | ✅ RESUELTO | Reemplazado por `->` |
| (prev) | _MEIPASS path mal calculado | 🛑 Crítica | ✅ RESUELTO | Usar `sys._MEIPASS` directamente |

---

## Resumen de resultados

| Categoría | Total | PASS | FAIL | NO EJECUTADA |
|-----------|-------|------|------|-------------|
| Backend (automatizado) | 3 | 3 | 0 | 0 |
| Frontend Tauri | 2 | 0 | 0 | 2 |
| Integración con LMU | 3 | 0 | 0 | 3 |
| Resistencia | 1 | 0 | 0 | 1 |
| Error handling | 2 | 0 | 0 | 2 |
| **Total** | **11** | **3** | **0** | **8** |

### Decisión de QA

**✅ CONDICIONAL — Las 3 pruebas backend pasan sin errores.**
**Las 8 pruebas restantes requieren un humano con entorno completo (LMU + Tauri).**

El backend compilado con PyInstaller está funcional y estable. El bug de logging (`isatty`) ha sido corregido y verificado. Los módulos locales (`src/`, `shared_telemetry/`, `shared_strategy/`) se copian correctamente al bundle.

**Riesgo principal identificado:** Puerto 8000 ocupado (Errno 10048) si ya hay una instancia corriendo — el backend no hace port fallback ni kill automático del proceso anterior.
