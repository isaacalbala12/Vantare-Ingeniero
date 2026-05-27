#!/bin/bash
# =============================================
# Script para crear GitHub Release con installers
# Ejecutar después de installer/build.sh
# =============================================

set -e

VERSION="0.1.0-alpha"
BUILD_DIR="./installer/build"
REPO="isaac-albala/Vantare-Ingeniero"

echo "============================================="
echo "  Vantare Ingeniero - Create GitHub Release"
echo "  Version: $VERSION"
echo "============================================="

# Verificar que existen los archivos
if [ ! -d "$BUILD_DIR" ]; then
    echo "Error: No se encontró directorio de builds"
    echo "Ejecuta primero: ./installer/build.sh"
    exit 1
fi

# Listar archivos a subir
echo ""
echo "Archivos para el release:"
ls -la "$BUILD_DIR"/

# =============================================
# OPCIÓN 1: Usar GitHub CLI (gh)
# =============================================
if command -v gh &> /dev/null; then
    echo ""
    echo "Creando release con GitHub CLI..."
    
    # Crear tag si no existe
    if ! git rev-parse "$VERSION" &> /dev/null; then
        git tag "$VERSION"
        git push origin "$VERSION"
    fi
    
    # Crear release
    gh release create "$VERSION" \
        --title "Vantare Ingeniero IA v${VERSION}" \
        --notes "Release alpha de Vantare Ingeniero IA.
        
## Contenido del release

### Windows
- vantare-instalador-*.exe - Instalador NSIS (recomendado)
- vantare-engine-*.exe - Ejecutable portable

### Linux
- vantare-engine-${VERSION}_amd64.deb - Paquete Debian/Ubuntu
- vantare-engine-${VERSION}.AppImage - AppImage portable

## Requisitos

### Windows
- Windows 10/11
- Python 3.12 (incluido en el instalador)

### Linux
- Ubuntu 22.04+ o Debian 12+
- Python 3.12

## Instalación

### Windows
1. Descargar vantare-instalador-*.exe
2. Ejecutar como administrador
3. Seguir las instrucciones del asistente

### Linux
1. Descargar vantare-engine-*_amd64.deb
2. Ejecutar: sudo dpkg -i vantare-engine-*_amd64.deb
3. O usar AppImage directamente (no requiere instalación)

---
Generado automáticamente por GitHub Actions" \
        --prerelease \
        "$BUILD_DIR"/*

# Subir archivos individuales
for file in "$BUILD_DIR"/*; do
    if [ -f "$file" ]; then
        echo "  Subiendo: $(basename "$file")"
        gh release upload "$VERSION" "$file" --clobber
    fi
done

echo ""
echo "✅ Release creado: https://github.com/$REPO/releases/tag/$VERSION"

# =============================================
# OPCIÓN 2: Instrucciones manuales
# =============================================
else
    echo ""
    echo "⚠️ GitHub CLI (gh) no está instalado."
    echo ""
    echo "Para crear el release manualmente:"
    echo "  1. Ve a: https://github.com/$REPO/releases/new"
    echo "  2. Tag: $VERSION"
    echo "  3. Title: Vantare Ingeniero IA v$VERSION"
    echo "  4. Subida los archivos de: $BUILD_DIR/"
    echo "  5. Publica el release"
    echo ""
fi

echo ""
echo "============================================="
echo "  PROCESO COMPLETADO"
echo "============================================="