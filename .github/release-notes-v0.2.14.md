## Vantare Ingeniero IA v0.2.14 — Alpha inicial (Voice Beta)

Primera alpha pública de la re-arquitectura de voz: audio en backend, telemetría in-process y overlay sincronizado.

### Requisitos

- Windows 10/11 x64
- Le Mans Ultimate
- Clave API LLM (StepFun u OpenAI-compatible)

### Instalar

1. Descarga **`vantare-ingeniero-0.2.14-setup.exe`** (asset abajo)
2. Si SmartScreen advierte: *Más información* → *Ejecutar de todas formas*
3. Configura la clave LLM en el `.env` del backend empaquetado si no lo hiciste en instalaciones previas
4. Inicia desde el menú Inicio

### Cambios principales

- Pipeline de voz in-process con pygame (`voiceBackendPlayback=true`)
- Race loop nativo sin sidecar WS separado
- Overlay de radio sincronizado con eventos `voice_playback_start` / `voice_playback_end`
- Spotter cartesiano, monitores proactivos (combustible, lluvia, FCY, daños, pits)
- Contrato de voz documentado + gates de QA (`verify_beta_gate`, `verify_bundle_startup`)

### Limitaciones conocidas (alpha)

- Ducking LMU opcional (`duck_lmu.exe`) no incluido en el instalador
- Solo Windows x64

### Soporte

- [Instalación](https://github.com/isaacalbala12/Vantare-Ingeniero/blob/master/docs/instalacion-desktop.md)
- [Changelog completo](https://github.com/isaacalbala12/Vantare-Ingeniero/blob/master/CHANGELOG.md)
- [Issues](https://github.com/isaacalbala12/Vantare-Ingeniero/issues)
