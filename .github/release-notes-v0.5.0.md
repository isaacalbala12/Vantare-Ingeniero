## Vantare Ingeniero IA v0.5.0 — Frases editables + Personalidades avanzadas

Incluye **v0.4** (frases spotter/triggers editables) y **v0.5** (proactividad, perlas, preview de tono) sobre la base v0.3.0.

### Requisitos

- Windows 10/11 x64
- Le Mans Ultimate
- Clave API LLM (StepFun u OpenAI-compatible)
- `GEMINI_API_KEY` **opcional** — solo si eliges proveedor Gemini en Hub → Audio

### Instalar

1. Descarga **`vantare-ingeniero-0.5.0-setup.exe`** (asset abajo)
2. Si SmartScreen advierte: *Más información* → *Ejecutar de todas formas*
3. Configura `LLM_API_KEY` (y opcionalmente `GEMINI_API_KEY`) en el `.env` del backend empaquetado
4. Inicia desde el menú Inicio

### Cambios principales

**v0.5 — Personalidades avanzadas**
- Proactividad del ingeniero: Baja / Normal / Alta (filtro por prioridad)
- Frecuencia de perlas de sabiduría (0–100%)
- Preview de tono en Hub → Voz → Ingeniero
- Sync `proactivityLevel` y `pearlFrequency` vía WebSocket

**v0.4 — Frases editables**
- Editor Hub → Audio → Frases personalizadas (export/import JSON)
- Overrides en `%APPDATA%/Vantare/phrases/user_phrases.json`
- REST `/phrases` con merge y hot-reload de caché spotter

### Limitaciones conocidas

- Sin clonación de voz (roadmap 1.0)
- Ducking LMU opcional (`duck_lmu.exe`) no incluido en el instalador
- Solo Windows x64 + LMU

### Soporte

- [Instalación](https://github.com/isaacalbala12/Vantare-Ingeniero/blob/master/docs/instalacion-desktop.md)
- [Changelog completo](https://github.com/isaacalbala12/Vantare-Ingeniero/blob/master/CHANGELOG.md)
- [Issues](https://github.com/isaacalbala12/Vantare-Ingeniero/issues)
