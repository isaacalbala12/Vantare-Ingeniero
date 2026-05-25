# Diagnóstico: Ventana Tauri Vacía — Plan de Investigación

> **For agentic workers:** This is a diagnosis-only plan. No code implementation is required. Each step is a verification that either confirms or rules out a hypothesis.

**Goal:** Identificar la causa raíz por la que la ventana de Tauri del Ingeniero de IA se abre vacía (transparente, sin interfaz React), a pesar de que el backend responde correctamente en `http://127.0.0.1:8008`.

**Síntoma:** La ventana Tauri (480×520, `transparent: true`, `decorations: false`) muestra un rectángulo vacío a través del cual se ve el escritorio. El backend FastAPI en puerto 8008 responde a `curl` correctamente.

**Hipótesis en orden de investigación (de más rápida/barata a más costosa):**
1. Error de directorio de ejecución (el comando se ejecuta desde la raíz en vez de `frontend/`)
2. Vite no está sirviendo contenido en `localhost:1420`
3. React no monta por un error JS durante la inicialización de módulos
4. La transparencia oculta el contenido (React sí monta, pero no se ve)

---

## Tarea 1: Verificar directorio de ejecución

**Archivos relevantes:** `frontend/package.json`, `frontend/src-tauri/tauri.conf.json`

- [ ] **Paso 1: Confirmar desde dónde se ejecuta `npm run tauri dev`**

    **Acción:** Preguntar al usuario o comprobar en el historial de terminal desde qué ruta se lanza el comando.

    **Comando esperado (correcto):**
    ```bash
    cd C:\Users\isaac\Desktop\Apps\Vantare Ingeniero\frontend
    npm run tauri dev
    ```

    **Comando incorrecto (causa del problema):**
    ```bash
    cd C:\Users\isaac\Desktop\Apps\Vantare Ingeniero
    npm run tauri dev
    ```
    Esto falla porque **no hay `package.json` en la raíz del proyecto**. NPM no encuentra el script `tauri` y reporta un error `npm ERR! missing script: tauri`.

    **Resultado esperado si es la causa:** El error es visible en la terminal donde se ejecuta el comando — no es "ventana vacía", sino que directamente no arranca. Esta causa probablemente **no** es la real.

- [ ] **Paso 2: Verificar que el `beforeDevCommand` se ejecuta correctamente**

    **Acción:** Revisar `frontend/src-tauri/tauri.conf.json` línea 8:
    ```json
    "beforeDevCommand": "npm run dev"
    ```

    Tauri ejecuta este comando desde el directorio donde está `src-tauri/` (es decir, `frontend/`). Si el usuario ejecuta `npm run tauri dev` desde `frontend/`, funciona. Si lo ejecuta desde otro sitio, Tauri CLI se queja antes de abrir ventana.

    **Diagnóstico:** Esta causa es **improbable** porque Tauri no abriría ninguna ventana si falla el `beforeDevCommand`.

---

## Tarea 2: Verificar que Vite sirve contenido en localhost:1420

**Archivos relevantes:** `frontend/vite.config.ts`, `frontend/index.html`

- [ ] **Paso 1: Probar acceso directo desde navegador**

    **Acción:** Abrir Chrome/Edge y navegar a `http://localhost:1420`

    **Resultado esperado (Vite funcionando):** Se ve la interfaz de React del Ingeniero (fondo oscuro, indicadores, etc.). Confirmaría que Vite y React funcionan correctamente y el problema está del lado de Tauri/WebView2.

    **Resultado esperado (Vite no funcionando):** Error de conexión "ERR_CONNECTION_REFUSED" o página en blanco. Indicaría que Vite no arrancó o no está en el puerto correcto.

- [ ] **Paso 2: Verificar qué proceso ocupa el puerto 1420**

    **Acción:** Ejecutar en PowerShell:
    ```powershell
    netstat -ano | findstr :1420
    ```

    **Resultado esperado (Vite funcionando):** Una línea con `LISTENING` en puerto 1420, con PID de `node.exe`.

    **Resultado esperado (Vite no funcionando):** Sin resultados. Vite no está corriendo.

- [ ] **Paso 3: Verificar la terminal de `npm run tauri dev`**

    **Acción:** Buscar en la salida de la terminal mensajes de Vite como:
    ```
    VITE v6.x.x  ready in XXX ms
    ➜  Local:   http://localhost:1420/
    ```

    Si no aparece, Vite no arrancó. Si aparece pero el navegador externo tampoco carga, puede ser error de bind (`host: true` en vite.config.ts escucha en `0.0.0.0`, pero `localhost` podría no resolverse en WebView2 en ciertos casos raros).

---

## Tarea 3: Verificar que React se monta (consola DevTools de Tauri)

**Archivos relevantes:** `frontend/src/main.tsx`, `frontend/src/App.tsx`, todos los hooks y componentes

- [ ] **Paso 1: Abrir DevTools de Tauri en la ventana vacía**

    **Acción:** Con la ventana de Tauri enfocada, pulsar `F12` o `Ctrl+Shift+I`. Alternativamente, se puede forzar la apertura desde Rust modificando `main.rs` temporalmente.

    Si no se puede abrir DevTools porque la ventana no tiene foco o no responde, probar:
    ```powershell
    # Desde otra terminal, enviar el atajo F12 a la ventana de Tauri
    # (No hay un comando directo, mejor modificar main.rs)
    ```

    **Solución alternativa:** Modificar `frontend/src-tauri/src/main.rs` para abrir DevTools automáticamente al arrancar. Añadir dentro del `.setup()`:
    ```rust
    // Temporal — para diagnóstico
    if let Some(window) = app.get_webview_window("main") {
        window.open_devtools();
    }
    ```

- [ ] **Paso 2: Inspeccionar la pestaña Console**

    **Acción:** En DevTools, ir a la pestaña **Console** y buscar errores en rojo.

    **Posibles errores a buscar:**
    ```
    - Failed to load module script: Expected a JavaScript module script but the server responded with a MIME type of...
    - Uncaught SyntaxError: import not found: ...
    - Uncaught TypeError: Cannot read properties of undefined (reading '...')
    - Uncaught ReferenceError: ... is not defined
    - Failed to fetch dynamically imported module
    - Uncaught (in promise) ... de @tauri-apps/api
    ```

- [ ] **Paso 3: Verificar que el DOM tiene el `<div id="root">` con contenido**

    **Acción:** En DevTools, ir a la pestaña **Elements** y buscar `<div id="root">`.

    **Si está vacío:** `createRoot` no se ejecutó — error de importación o ejecución en `main.tsx` o `App.tsx`.
    **Si tiene contenido:** React montó correctamente, el problema es visual (transparencia/CSS).

- [ ] **Paso 4: Verificar la pestaña Network**

    **Acción:** En DevTools, ir a **Network** y recargar (`Ctrl+R`).

    **Buscar:** ¿El `index.html` se cargó? (código 200). ¿Los módulos JS (`main.tsx`, `App.tsx`, hooks) se cargaron? ¿Hay errores 404 o falls de tipo MIME?

- [ ] **Paso 5: Forzar un console.log() para aislar hasta dónde llega la ejecución**

    **Acción:** Si DevTools no abre, añadir temporalmente un `console.log("=== MAIN ENTRY ===")` al inicio de `main.tsx` y otro al inicio del componente `App` en `App.tsx`.

    Luego observar la terminal de Tauri. Si Tauri captura `console.log` de la WebView, se verán ahí. (Tauri v2 no captura `console.log` por defecto, pero se puede configurar con un plugin o viendo DevTools).

---

## Tarea 4: Descartar que el problema sea la transparencia

**Archivos relevantes:** `frontend/src-tauri/tauri.conf.json`, `frontend/src/styles/index.css`

- [ ] **Paso 1: Desactivar `transparent: true` temporalmente**

    **Acción:** Modificar `frontend/src-tauri/tauri.conf.json`:
    ```json
    // Antes
    "transparent": true,
    
    // Después (temporal, solo diagnóstico)
    "transparent": false,
    ```

    **Resultado esperado si React funciona:** La ventana ahora tiene fondo blanco (o el color de fondo que ponga el HTML/CSS) y se ve la interfaz. Esto confirmaría que React renderiza correctamente pero no era visible por la transparencia.

    **Resultado esperado si React no funciona:** La ventana sigue vacía pero ahora con fondo blanco en vez de transparente. Confirmaría que React no monta.

- [ ] **Paso 2: Activar `decorations: true` temporalmente**

    **Acción:** En el mismo archivo:
    ```json
    "decorations": true,
    ```

    **Resultado:** Ayuda a visibilidad (se ve la barra de título de Windows) y descarta problemas de redimensionamiento. No arregla el contenido pero ayuda al diagnóstico visual.

- [ ] **Paso 3: Verificar que el CSS no fuerza transparencia total**

    **Acción:** Revisar `frontend/src/styles/index.css`:
    ```css
    :root { background-color: transparent; }
    body { background-color: transparent; }
    ```

    Si `transparent: false` en Tauri, estos estilos hacen que el body sea transparente sobre fondo blanco de Tauri. El componente `App` renderiza `<div className="w-screen h-screen ... bg-[#111]">`, que debería cubrir todo. Si React monta, se ve el fondo oscuro `#111`. Si React no monta, se ve blanco (porque `transparent: false` da fondo blanco por defecto en WebView2).

---

## Tarea 5: Verificar errores de compilación/transpilación

**Archivos relevantes:** `frontend/tsconfig.json`, toda la carpeta `frontend/src/`

- [ ] **Paso 1: Ejecutar `tsc` manualmente para ver errores de TypeScript**

    **Acción:** En `frontend/`:
    ```bash
    npx tsc --noEmit
    ```

    **Resultado esperado:** Lista de errores de TypeScript.

    **Errores esperados:**
    - `App.tsx`: `sendBinary` is declared but its value is never read. (por `noUnusedLocals: true`)
    - Posibles errores de tipos en hooks o componentes.

    **Nota:** `vite dev` usa esbuild y NO valida `noUnusedLocals`/`noUnusedParameters`, así que estos errores no causarían la ventana vacía en dev. Pero sí romperían `npm run build`.

- [ ] **Paso 2: Verificar que no hay errores de sintaxis en los imports dinámicos**

    **Acción:** Buscar imports dinámicos `import(...)` que puedan fallar en el contexto de WebView2.

    Archivos problemáticos:
    - `frontend/src/hooks/useHotkey.ts`: `import("@tauri-apps/plugin-global-shortcut")` — dentro de `useEffect`, atrapado con `try/catch`, no bloquea el render inicial.
    - `frontend/src/components/SystemTrayMenu.tsx`: `import("@tauri-apps/api/webviewWindow")` — dentro de handlers, atrapado con `try/catch`.
    - `frontend/src/App.tsx`: `import("@tauri-apps/api/event")` — dentro de `useEffect`, atrapado con `try/catch`.

    Ninguno de estos debería bloquear el render inicial porque todos están dentro de `useEffect` o manejadores de eventos.

---

## Tarea 6: Verificar errores de WebView2 (navegador interno de Tauri)

**Archivos relevantes:** `frontend/src-tauri/tauri.conf.json`, Rust crates

- [ ] **Paso 1: Verificar que WebView2 Runtime está instalado**

    **Acción:** En Windows:
    ```powershell
    Get-ItemProperty "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" | Select-Object name, version
    ```

    O simplemente abrir Edge y verificar que funciona. WebView2 viene con Windows 11 por defecto, pero podría estar desactualizado o corrupto.

- [ ] **Paso 2: Probar con `devUrl` apuntando a una URL estática conocida**

    **Acción:** Cambiar temporalmente `devUrl` en `tauri.conf.json` a una URL que sepas que funciona:
    ```json
    "devUrl": "https://example.com",
    ```

    **Resultado esperado (WebView2 funciona):** La ventana muestra la página de example.com. Descarta problemas de WebView2.

    **Resultado esperado (WebView2 no funciona):** La ventana sigue vacía o muestra error. Problema con WebView2.

---

## Tarea 7: Verificar versión de dependencias (compatibilidad Tauri v2)

**Archivos relevantes:** `frontend/src-tauri/Cargo.toml`, `frontend/package.json`

- [ ] **Paso 1: Verificar compatibilidad de versiones**

    **Acción:** Comparar versiones en `package.json` y `Cargo.toml`:

    ```json
    // package.json
    "@tauri-apps/api": "^2.2.0",
    "@tauri-apps/plugin-global-shortcut": "^2.2.0",
    "@tauri-apps/plugin-opener": "^2.2.0",
    "@tauri-apps/cli": "^2.2.0"
    ```

    ```toml
    # Cargo.toml
    tauri = { version = "2", features = ["tray-icon"] }
    tauri-plugin-opener = "2"
    tauri-plugin-shell = "2"
    tauri-plugin-global-shortcut = "2"
    tauri-plugin-websocket = "2"
    ```

    **Verificar:** Que las versiones npm y Rust sean compatibles (ej: `@tauri-apps/api@2.2.x` con `tauri@2.2.x`). Generalmente son compatibles dentro de la misma rama v2.

- [ ] **Paso 2: Verificar `npm install` completo**

    **Acción:** En `frontend/`:
    ```bash
    npm ls --depth=0
    ```

    Verificar que todos los paquetes están instalados y no hay dependencias faltantes o con conflictos.

---

## Árbol de decisión de diagnóstico

```
¿La terminal muestra errores de Vite o Rust?
├── Sí → Arreglar error de compilación/terminal
└── No → ¿http://localhost:1420 funciona en navegador externo?
    ├── No → Vite no arranca → Revisar beforeDevCommand, puertos
    └── Sí → ¿La consola DevTools de Tauri muestra errores JS?
        ├── Sí → Arreglar error específico (import, tipo, etc.)
        └── No → ¿El DOM tiene el div#root con contenido?
            ├── No → React no monta → Revisar main.tsx, imports estáticos
            └── Sí → ¿Transparent=false muestra el contenido?
                ├── No → Problema de CSS/estilos/Tailwind
                └── Sí → La transparencia era el problema
```

---

## Resumen de verificación rápida (checklist mínimo)

1. [ ] `cd frontend && npm run tauri dev` — terminal sin errores
2. [ ] `http://localhost:1420` en navegador externo — muestra la app
3. [ ] F12 en ventana Tauri → Console — sin errores
4. [ ] F12 → Elements → `<div id="root">` — tiene hijos de React
5. [ ] `transparent: false` temporal — contenido visible

Cualquier paso que falle apunta directamente a la causa raíz.
