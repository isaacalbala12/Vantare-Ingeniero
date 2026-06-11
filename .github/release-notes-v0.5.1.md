## Vantare Ingeniero IA v0.5.1 — Fix auto-update (instaladores sin firma)

Corrige el error *"not signed by the application owner"* al actualizar desde versiones anteriores.

### Requisitos

- Windows 10/11 x64
- Le Mans Ultimate
- Clave API LLM (StepFun u OpenAI-compatible)

### Instalar / actualizar

**Si vienes de v0.2.x y el auto-update falló:** descarga e instala **`vantare-ingeniero-0.5.1-setup.exe`** manualmente (asset abajo). SmartScreen puede avisar — *Más información* → *Ejecutar de todas formas*.

A partir de v0.5.1, las actualizaciones automáticas desde Hub → Avanzado funcionan sin certificado de firma.

### Cambios

- Desactiva verificación Authenticode en el updater (`verifyUpdateCodeSignature` → noop en Windows)
- Quita `publisherName` del build hasta disponer de certificado de código

Incluye todo lo de **v0.5.0** (personalidades avanzadas) y **v0.4.0** (frases editables).

### Soporte

- [Changelog](https://github.com/isaacalbala12/Vantare-Ingeniero/blob/master/CHANGELOG.md)
- [Issues](https://github.com/isaacalbala12/Vantare-Ingeniero/issues)
