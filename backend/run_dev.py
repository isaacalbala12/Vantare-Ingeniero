"""
Script de desarrollo: arranca el backend directamente con uvicorn.
NO ejecuta PyInstaller, por lo que los cambios se reflejan instantáneamente
con el hot-reload de uvicorn.

Uso:
    python run_dev.py                  # con hot-reload
    python run_dev.py --no-reload      # sin hot-reload
    python run_dev.py --port 8080      # puerto personalizado
"""
import os
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Arranca el backend en modo desarrollo")
    parser.add_argument("--no-reload", action="store_true", help="Desactivar hot-reload")
    parser.add_argument("--port", type=int, default=8008, help="Puerto (default: 8008)")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    args = parser.parse_args()

    # Asegurar que el directorio base está en sys.path para imports locales
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    # Añadir shared modules al path
    for shared in ["shared-telemetry", "shared-strategy"]:
        p = os.path.abspath(os.path.join(base_dir, "..", shared))
        if p not in sys.path:
            sys.path.insert(0, p)

    import uvicorn

    # Importar settings para obtener el puerto por defecto
    from src.config import settings

    reload = not args.no_reload

    print(f"{'='*60}")
    print(f"  Vantare Ingeniero IA - Backend (MODO DESARROLLO)")
    print(f"{'='*60}")
    print(f"  Host:         {args.host}")
    print(f"  Puerto:       {args.port} (default: {settings.PORT})")
    print(f"  Hot-reload:   {'ACTIVADO' if reload else 'DESACTIVADO'}")
    print(f"  PyInstaller:  NO (arranque directo con uvicorn)")
    print(f"{'='*60}")
    
    port = args.port or settings.PORT

    uvicorn.run(
        "src.main:app",
        host=args.host,
        port=port,
        reload=reload,
        log_level="info",
    )

if __name__ == "__main__":
    main()
