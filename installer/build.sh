#!/bin/bash
# =============================================
# Build script para crear instaladores Linux y Windows
# Uso: ./installer/build.sh [--linux-only|--windows-only]
# =============================================

set -e

VERSION="0.1.0-alpha"
BUILD_DIR="./installer/build"
DEB_DIR="$BUILD_DIR/vantare-engine-${VERSION}"

echo "============================================="
echo "  Vantare Ingeniero IA - Build Installers"
echo "  Version: $VERSION"
echo "============================================="

# Parsear argumentos
BUILD_LINUX=true
BUILD_WINDOWS=true

for arg in "$@"; do
    case $arg in
        --linux-only)
            BUILD_WINDOWS=false
            ;;
        --windows-only)
            BUILD_LINUX=false
            ;;
    esac
done

# ====================
# LIMPIEZA PREVIA
# ====================
echo "[1/4] Limpiando builds anteriores..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
mkdir -p "$DEB_DIR"

# ====================
# CONSTRUIR LINUX DEB
# ====================
if [ "$BUILD_LINUX" = true ]; then
    echo "[2/4] Construyendo paquete Linux (DEB)..."

    # Crear estructura DEB
    mkdir -p "$DEB_DIR/DEBIAN"
    mkdir -p "$DEB_DIR/usr/bin"
    mkdir -p "$DEB_DIR/usr/share/doc/vantare-engine"
    mkdir -p "$DEB_DIR/usr/share/applications"
    mkdir -p "$DEB_DIR/etc/vantare"

    # Copiar ejecutables (si existen los builds)
    if [ -d "backend/dist/vantare-engine" ]; then
        cp -r backend/dist/vantare-engine/* "$DEB_DIR/usr/bin/"
        echo "  - Backend copiado"
    fi

    if [ -d "sidecar/dist/strategy-sidecar" ]; then
        cp -r sidecar/dist/strategy-sidecar/* "$DEB_DIR/usr/bin/"
        echo "  - Sidecar copiado"
    fi

    # Crear scripts de inicio
    cat > "$DEB_DIR/usr/bin/vantare-engine" << 'EOF'
#!/bin/bash
cd /usr/share/vantare-engine
./vantare-engine
EOF

    cat > "$DEB_DIR/usr/bin/vantare-sidecar" << 'EOF'
#!/bin/bash
cd /usr/share/vantare-engine
./strategy-sidecar
EOF

    chmod +x "$DEB_DIR/usr/bin/vantare-engine"
    chmod +x "$DEB_DIR/usr/bin/vantare-sidecar"

    # Control file (DEBIAN/control)
    cat > "$DEB_DIR/DEBIAN/control" << EOF
Package: vantare-engine
Version: ${VERSION}
Section: games
Priority: optional
Architecture: amd64
Depends: python3.12, libasound2, libcairo2
Maintainer: Vantare <info@vantare.es>
Description: Vantare Ingeniero IA - Race Strategy Assistant
 A real-time race strategy assistant for Le Mans Ultimate (LMU).
 Provides pit strategies, tire recommendations, and voice advice.
EOF

    # Pre-depends script
    cat > "$DEB_DIR/DEBIAN/preinst" << 'EOF'
#!/bin/bash
# Verificar dependencias
if ! command -v python3.12 &> /dev/null; then
    echo "Error: Python 3.12 no está instalado"
    echo "Instala con: sudo apt install python3.12"
    exit 1
fi
exit 0
EOF

    # Post-install script
    cat > "$DEB_DIR/DEBIAN/postinst" << 'EOF'
#!/bin/bash
# Crear enlace simbólico y configurar
if [ -f /usr/bin/vantare-engine ]; then
    ln -sf /usr/share/vantare-engine/vantare-engine /usr/bin/vantare-engine 2>/dev/null || true
fi

# Crear directorio de configuración del usuario
mkdir -p ~/.config/vantare
if [ ! -f ~/.config/vantare/config.env ]; then
    cp /etc/vantare/config.env.example ~/.config/vantare/config.env 2>/dev/null || true
fi

# Permisos
chmod +x /usr/bin/vantare-engine 2>/dev/null || true
chmod +x /usr/bin/vantare-sidecar 2>/dev/null || true

echo "Vantare Ingeniero IA instalado correctamente!"
echo "Para ejecutar: vantare-engine"
EOF

    # Pre-remove script
    cat > "$DEB_DIR/DEBIAN/prerm" << 'EOF'
#!/bin/bash
# Detener servicios si están corriendo
pkill -f vantare-engine 2>/dev/null || true
pkill -f strategy-sidecar 2>/dev/null || true
EOF

    # Post-remove script
    cat > "$DEB_DIR/DEBIAN/postrm" << 'EOF'
#!/bin/bash
# Limpiar archivos de configuración (opcional)
if [ "$1" = "purge" ]; then
    rm -rf ~/.config/vantare 2>/dev/null || true
fi
EOF

    chmod 755 "$DEB_DIR/DEBIAN/"*
    chmod 755 "$DEB_DIR/usr/bin/vantare-engine"
    chmod 755 "$DEB_DIR/usr/bin/vantare-sidecar"

    # Copiar LICENSE y docs
    cp LICENSE "$DEB_DIR/usr/share/doc/vantare-engine/" 2>/dev/null || true

    # Crear AppRun para AppImage (alternativa portable)
    cat > "$DEB_DIR/AppRun" << 'EOF'
#!/bin/bash
# AppRun - Ejecutable portable
SELF=$(readlink -f "$0")
APPDIR=$(dirname "$SELF")
cd "$APPDIR"
./vantare-engine
EOF
    chmod +x "$DEB_DIR/AppRun"

    # Crear AppImage
    echo "  Creando AppImage..."
    
    # Estructura simple para AppImage
    APPIMAGE_DIR="$BUILD_DIR/vantare-engine.AppImageDir"
    mkdir -p "$APPIMAGE_DIR"
    cp -r "$DEB_DIR/usr/bin" "$APPIMAGE_DIR/"
    
    # SquashFS para AppImage (requiere squashfs-tools)
    if command -v mksquashfs &> /dev/null; then
        mksquashfs "$APPIMAGE_DIR" "$BUILD_DIR/vantare-engine-${VERSION}.AppImage" -comp xz
        chmod +x "$BUILD_DIR/vantare-engine-${VERSION}.AppImage"
        echo "  - AppImage creado"
    fi

    # Generar DEB
    dpkg-deb --build "$DEB_DIR" "$BUILD_DIR/vantare-engine-${VERSION}_amd64.deb"
    echo "  - DEB creado: vantare-engine-${VERSION}_amd64.deb"
fi

# ====================
# CONSTRUIR WINDOWS NSIS
# ====================
if [ "$BUILD_WINDOWS" = true ]; then
    echo "[3/4] Construyendo instalador Windows (NSIS)..."
    
    # Verificar NSIS
    if ! command -v makensis &> /dev/null; then
        echo "  Advertencia: NSIS no instalado. Saltando Windows..."
        echo "  Instala con: sudo apt install nsis"
    else
        # Preparar archivos para Windows
        WIN_BUILD="$BUILD_DIR/windows"
        mkdir -p "$WIN_BUILD"
        
        # Copiar scripts y archivos
        cp -r installer/windows.nsi "$WIN_BUILD/"
        cp LICENSE "$WIN_BUILD/LICENSE.txt" 2>/dev/null || true
        cp backend/.env.example "$WIN_BUILD/config.env.example" 2>/dev/null || true
        
        # Si hay builds de backend y sidecar
        if [ -d "backend/dist/vantare-engine" ]; then
            mkdir -p "$WIN_BUILD/backend"
            cp -r backend/dist/vantare-engine "$WIN_BUILD/backend/vantare-engine"
        fi
        
        if [ -d "sidecar/dist/strategy-sidecar" ]; then
            mkdir -p "$WIN_BUILD/sidecar"
            cp -r sidecar/dist/strategy-sidecar "$WIN_BUILD/sidecar/strategy-sidecar"
        fi
        
        # Compilar NSIS
        cd "$WIN_BUILD"
        makensis windows.nsi
        cd - > /dev/null
        
        echo "  - NSIS installer creado"
    fi
fi

# ====================
# RESUMEN
# ====================
echo "[4/4] Builds completados!"
echo ""
echo "Archivos generados:"
ls -la "$BUILD_DIR"/

echo ""
echo "============================================="
echo "  INSTALADORES LISTOS"
echo "============================================="
echo ""
echo "Para crear release en GitHub:"
echo "  1. Subir archivos de $BUILD_DIR a GitHub Release"
echo "  2. O ejecutar: ./installer/create-release.sh"
echo ""