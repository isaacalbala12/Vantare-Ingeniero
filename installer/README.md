# =============================================
# Vantare Ingeniero IA - Release Alpha v0.1.0
# =============================================

## Tabla de Contenidos
- [Instaladores Disponibles](#instaladores-disponibles)
- [Instalación Windows](#instalación-windows)
- [Instalación Linux](#instalación-linux)
- [Requisitos del Sistema](#requisitos-del-sistema)
- [Configuración Post-Instalación](#configuración-post-instalación)
- [Solución de Problemas](#solución-de-problemas)

---

## Instaladores Disponibles

| Archivo | Plataforma | Tipo | Recomendado |
|---------|-----------|------|-------------|
| `vantare-instalador-0.1.0-alpha.exe` | Windows | NSIS Installer | ✅ |
| `vantare-engine-0.1.0-alpha.deb` | Linux (Debian/Ubuntu) | Paquete DEB | ✅ |
| `vantare-engine-0.1.0-alpha.AppImage` | Linux | Portable | Alternativa |

---

## Instalación Windows

### Opción 1: Instalador (Recomendado)

1. **Descarga** el archivo `vantare-instalador-0.1.0-alpha.exe`

2. **Ejecuta** como Administrador (clic derecho → "Ejecutar como administrador")

3. **Sigue** las instrucciones del asistente de instalación:
   - Acepta los términos de licencia
   - Elige la carpeta de instalación (por defecto: `C:\Program Files\Vantare Ingeniero IA`)
   - Crea accesos directos en Desktop y Menú Inicio

4. **Finaliza** la instalación

5. **Ejecuta** desde:
   - Acceso directo en Desktop
   - Menú Inicio → Vantare Ingeniero IA

### Opción 2: Portable (Sin instalación)

1. Descarga `vantare-engine.exe`
2. Ejecuta directamente (no requiere instalación)

---

## Instalación Linux

### Opción 1: Paquete DEB (Recomendado para Ubuntu/Debian)

```bash
# 1. Descarga el archivo .deb

# 2. Instala con dpkg (requiere sudo)
sudo dpkg -i vantare-engine-0.1.0-alpha.deb

# 3. Si hay errores de dependencias, ejecuta:
sudo apt-get install -f

# 4. Ejecuta:
vantare-engine
```

### Opción 2: AppImage (Portable)

```bash
# 1. Descarga el archivo .AppImage

# 2. Dale permisos de ejecución
chmod +x vantare-engine-0.1.0-alpha.AppImage

# 3. Ejecuta directamente (no requiere instalación)
./vantare-engine-0.1.0-alpha.AppImage
```

---

## Requisitos del Sistema

### Windows
- **SO**: Windows 10 o Windows 11 (64-bit)
- **RAM**: 4 GB mínimo
- **Espacio**: 500 MB libre
- **Python**: Incluido en el instalador (no requiere instalación manual)

### Linux
- **SO**: Ubuntu 22.04+ o Debian 12+ (64-bit)
- **RAM**: 4 GB mínimo
- **Espacio**: 500 MB libre
- **Python**: 3.12 (instalar con `sudo apt install python3.12`)
- **Librerías**: `libasound2`, `libcairo2` (normalmente pré-instaladas)

---

## Configuración Post-Instalación

### Windows
1. **Primera ejecución**: El instalador crea un archivo de configuración en:
   `%USERPROFILE%\.vantare\config.env`

2. **Configurar LLM**: Edita el archivo `config.env` y añade:
   ```env
   LLM_BASE_URL=https://tu-tunnel-cloudflare.trycloudflare.com/v1
   LLM_API_KEY=tu-api-key
   ```

3. **Reinicia** la aplicación

### Linux
1. **Primera ejecución**: El instalador crea un archivo de configuración en:
   `~/.config/vantare/config.env`

2. **Configurar LLM**: Edita el archivo `config.env` y añade:
   ```env
   LLM_BASE_URL=https://tu-tunnel-cloudflare.trycloudflare.com/v1
   LLM_API_KEY=tu-api-key
   ```

3. **Ejecuta**:
   ```bash
   vantare-engine
   ```

---

## Solución de Problemas

### "Python 3.12 no encontrado" (Linux)
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev
```

### "No se puede conectar al backend" (Windows)
1. Verifica que el puerto 8008 no esté en uso: `netstat -an | grep 8008`
2. Ejecuta como Administrador

### "Error de permisos" (Linux)
```bash
# Dar permisos de ejecución al ejecutable
chmod +x /usr/bin/vantare-engine

# O ejecutar con permisos de administrador
sudo /usr/bin/vantare-engine
```

### "LLM no responde"
1. Verifica que el tunnel de Cloudflare esté activo
2. Actualiza la URL en `config.env`
3. Reinicia la aplicación

---

## Desinstalación

### Windows
- Ve a **Configuración → Aplicaciones → Vantare Ingeniero IA → Desinstalar**
- O ejecuta `%PROGRAMFILES%\Vantare Ingeniero IA\uninstall.exe`

### Linux
```bash
sudo dpkg -r vantare-engine
```

---

## Soporte

Para reportar problemas o solicitar ayuda:
- GitHub Issues: https://github.com/isaac-albala/Vantare-Ingeniero/issues
- Documentación: https://github.com/isaac-albala/Vantare-Ingeniero#readme

---

**Vantare Ingeniero IA v0.1.0-alpha**
*Asistente de estrategia de carreras en tiempo real para Le Mans Ultimate*