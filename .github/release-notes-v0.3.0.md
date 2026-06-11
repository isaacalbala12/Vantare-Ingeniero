## Vantare Ingeniero IA v0.3.0 — Frases humanas + Gemini TTS

Copy de radio más natural y **Gemini TTS** selectable por rol, sobre la base estable Voice Beta (v0.2.14).

### Requisitos

- Windows 10/11 x64
- Le Mans Ultimate
- Clave API LLM (StepFun u OpenAI-compatible)
- `GEMINI_API_KEY` **opcional** — solo si eliges proveedor Gemini en Hub → Audio

### Instalar

1. Descarga **`vantare-ingeniero-0.3.0-setup.exe`** (asset abajo, generado por CI al publicar el tag)
2. Si SmartScreen advierte: *Más información* → *Ejecutar de todas formas*
3. Configura `LLM_API_KEY` (y opcionalmente `GEMINI_API_KEY`) en el `.env` del backend empaquetado
4. Inicia desde el menú Inicio

### Cambios principales

- **Frases humanas** spotter + triggers P0 con variantes por perfil (standard/formal/aggressive)
- **Gemini TTS** por rol (ingeniero / spotter) desde el Hub; fallback Edge automático
- Crew Chief usa frases del picker en fuel, desgaste, pits, FCY
- Caché spotter coherente con voz Edge; bypass al usar Gemini spotter

### Limitaciones conocidas

- Sin clonación de voz (roadmap 1.0)
- Ducking LMU opcional (`duck_lmu.exe`) no incluido en el instalador
- Solo Windows x64 + LMU

### Soporte

- [Instalación](https://github.com/isaacalbala12/Vantare-Ingeniero/blob/master/docs/instalacion-desktop.md)
- [Changelog completo](https://github.com/isaacalbala12/Vantare-Ingeniero/blob/master/CHANGELOG.md)
- [Issues](https://github.com/isaacalbala12/Vantare-Ingeniero/issues)
