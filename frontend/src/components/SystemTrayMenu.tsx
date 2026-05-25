import React, { useState } from "react";
import { useAppStore } from "../store/config";
import { Monitor, Settings, LogOut, Radio } from "lucide-react";

/**
 * Componente interactivo y de diagnóstico del SystemTray (Bandeja del Sistema).
 * Muestra el estado del WebSocket y expone las opciones del menú de bandeja:
 * "Mostrar Radio Overlay", "Configuración" y "Salir".
 * Utiliza llamadas nativas a Tauri v2 con fallbacks robustos para navegadores web estándar.
 */
export const SystemTrayMenu: React.FC = () => {
  const { connectivity } = useAppStore();
  const [showMenu, setShowMenu] = useState(true);

  const isConnected = connectivity.wsStatus === "CONNECTED";

  // Acción: Mostrar el Overlay principal (Ventana 'main')
  const handleShowOverlay = async () => {
    try {
      const { WebviewWindow } = await import("@tauri-apps/api/webviewWindow");
      const mainWin = await WebviewWindow.getByLabel("main");
      if (mainWin) {
        await mainWin.show();
        await mainWin.setFocus();
      }
    } catch (e) {
      console.warn("Entorno Web: Abriendo ventana principal en simulador...");
      window.location.hash = "main";
    }
  };

  // Acción: Abrir la ventana de configuración (Ventana 'config')
  const handleOpenConfig = async () => {
    try {
      const { WebviewWindow } = await import("@tauri-apps/api/webviewWindow");
      const configWin = await WebviewWindow.getByLabel("config");
      if (configWin) {
        await configWin.show();
        await configWin.setFocus();
      }
    } catch (e) {
      console.warn("Entorno Web: Abriendo panel de configuración...");
      window.location.hash = "config";
    }
  };

  // Acción: Salir de la aplicación de forma limpia
  const handleExitApp = async () => {
    const confirmExit = window.confirm("¿Seguro que deseas salir de Vantare Ingeniero?");
    if (!confirmExit) return;

    try {
      const { getCurrentWindow } = await import("@tauri-apps/api/window");
      const appWindow = getCurrentWindow();
      if (appWindow) {
        await appWindow.close();
      }
    } catch (e) {
      console.warn("Entorno Web: Cerrando la sesión simulada...");
      alert("Aplicación cerrada (simulado en navegador).");
    }
  };

  return (
    <div className="w-full max-w-sm mx-auto p-4 select-none">
      {/* Contenedor principal de estilo Viga de Cristal */}
      <div className="relative bg-[#0b0416]/90 border border-purple-500/30 rounded-lg p-5 shadow-2xl overflow-hidden text-silver">
        {/* Esquinas decorativas MOTEC */}
        <div className="absolute top-0 left-0 w-2 h-2 border-t border-l border-purple-500/60" />
        <div className="absolute top-0 right-0 w-2 h-2 border-t border-r border-purple-500/60" />
        <div className="absolute bottom-0 left-0 w-2 h-2 border-b border-l border-purple-500/60" />
        <div className="absolute bottom-0 right-0 w-2 h-2 border-b border-r border-purple-500/60" />

        {/* Cabecera / Info del Icono en Bandeja */}
        <div className="flex items-center justify-between border-b border-purple-500/15 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <div className="relative flex h-3 w-3">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                isConnected ? "bg-green-400" : "bg-red-400"
              }`} />
              <span className={`relative inline-flex rounded-full h-3 w-3 ${
                isConnected ? "bg-green-500" : "bg-red-500"
              }`} />
            </div>
            <span className="font-rajdhani font-bold text-xs tracking-wider">
              ICONO DE BANDEJA // {isConnected ? "ACTIVO" : "OFFLINE"}
            </span>
          </div>
          <span className="text-[10px] font-mono text-zinc-500">
            WS_PORT: 8008
          </span>
        </div>

        {/* Simulación del Widget de la Bandeja */}
        <div className="flex flex-col items-center justify-center p-6 border border-purple-500/10 rounded bg-zinc-900/40 mb-4">
          <div className="relative p-4 bg-zinc-900/60 border border-zinc-700 rounded-full cursor-pointer hover:border-purple-500/50 transition-all duration-200"
               onClick={() => setShowMenu(!showMenu)}>
            <Radio className={`w-8 h-8 transition-colors duration-300 ${
              isConnected ? "text-green-400 drop-shadow-[0_0_8px_rgba(34,197,94,0.5)]" : "text-red-500 drop-shadow-[0_0_8px_rgba(239,68,68,0.5)]"
            }`} />
          </div>
          <p className="text-[10px] font-inter text-zinc-400 mt-2 text-center">
            {isConnected 
              ? "Bandeja activa y conectada. Haz clic para desplegar opciones."
              : "Bandeja desconectada del servidor local de LMU."}
          </p>
        </div>

        {/* Menú Contextual Desplegado */}
        {showMenu && (
          <div className="space-y-1.5 border-t border-purple-500/10 pt-4">
            <button
              onClick={handleShowOverlay}
              className="w-full flex items-center justify-between px-3 py-2 rounded text-xs text-white hover:text-purple-500 bg-zinc-900/30 border border-zinc-700 hover:border-purple-500/30 hover:bg-purple-500/5 transition-all duration-150"
            >
              <span className="flex items-center gap-2">
                <Monitor size={12} className="text-purple-500" />
                Mostrar Radio Overlay
              </span>
              <span className="text-[8px] font-mono text-zinc-500">MAIN_HUD</span>
            </button>

            <button
              onClick={handleOpenConfig}
              className="w-full flex items-center justify-between px-3 py-2 rounded text-xs text-white hover:text-purple-500 bg-zinc-900/30 border border-zinc-700 hover:border-purple-500/30 hover:bg-purple-500/5 transition-all duration-150"
            >
              <span className="flex items-center gap-2">
                <Settings size={12} className="text-purple-500" />
                Abrir Configuración
              </span>
              <span className="text-[8px] font-mono text-zinc-500">CONFIG_UI</span>
            </button>

            <button
              onClick={handleExitApp}
              className="w-full flex items-center justify-between px-3 py-2 rounded text-xs text-red-400 hover:text-red-300 bg-red-950/5 border border-zinc-700 hover:border-red-500/20 hover:bg-red-950/15 transition-all duration-150"
            >
              <span className="flex items-center gap-2">
                <LogOut size={12} />
                Salir de la Aplicación
              </span>
              <span className="text-[8px] font-mono text-zinc-500">HALT</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default SystemTrayMenu;
