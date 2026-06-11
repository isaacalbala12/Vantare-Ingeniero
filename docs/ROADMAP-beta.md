# Roadmap Beta — Paridad Crew Chief (post-alpha)

> **Plan activo 0.3 → 1.1:** [`ROADMAP-1.0.md`](ROADMAP-1.0.md)  
> Este documento conserva la deuda explícita del cierre alpha/beta.

Elementos **explícitamente diferidos** del plan alpha. No implementar hasta cierre A8 + validación LMU.

## TTS premium
- **Gemini TTS** como voz premium por perfil (`PersonalityPack`)
- ElevenLabs producción opcional
- Voice packs descargables

## Overlays in-game
- Subtítulos always-on-top (estilo CC `SubtitleOverlay`)
- Gaps chart / tyre heat overlay
- VR SteamVR overlay window

## Pit management write
- REST PitMenu LMU: fuel/tyres/repairs por voz
- Validar API estable en LMU antes de implementar (`PitManagerEventHandlers_LMU.cs` en CC como referencia)

## Idioma
- Inglés + localización NumberProcessing estilo CC
- Voice packs EN

## SDK / integraciones
- SDK público estilo CrewChief
- CoDriver rally / pace notes
- Macros DOS / keypress por voz

## Cuándo promover a producción
1. Checklist `.omo/evidence/audio-lmu-validation.md` completo en 3+ circuitos
2. Gate CI `verify_audio_pipeline.py` + spotter en verde
3. MQTT E2E validado (`scripts/verify_mqtt_e2e.py`)
