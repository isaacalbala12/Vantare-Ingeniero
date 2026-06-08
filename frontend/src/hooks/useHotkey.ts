import { useEffect, useRef } from "react";
import { useAppStore } from "../store/config";

interface UseHotkeyProps {
  onKeyDown: () => void; // Inicia PTT
  onKeyUp: () => void;   // Finaliza PTT y envía
}

const isTauri = typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__ !== undefined;

const DEFAULT_PTT_HOTKEY = "Ctrl+Shift+Space";

/** No activar PTT mientras el usuario escribe en un campo de texto. */
function isEditableTarget(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return target.isContentEditable;
}

function hotkeyHasModifier(combo: string): boolean {
  const parts = combo.toLowerCase().split("+");
  return parts.some((p) =>
    ["ctrl", "control", "shift", "alt", "meta", "super", "win", "cmd"].includes(p),
  );
}

/** Teclas sueltas (P, A…) capturan globalmente todo el SO — solo permitir con modificador. */
function canRegisterGlobalHotkey(combo: string): boolean {
  if (hotkeyHasModifier(combo)) return true;
  const key = combo.split("+").pop()?.toLowerCase() ?? "";
  if (/^f([1-9]|1[0-2])$/.test(key)) return true;
  const safeSingleKeys = new Set([
    "capslock", "scrolllock", "pause", "numlock",
    "insert", "home", "end", "pageup", "pagedown",
  ]);
  return safeSingleKeys.has(key);
}

/**
 * Helper para comparar un KeyboardEvent con una hotkey string tipo "Ctrl+Shift+P".
 */
const matchesKeyCombo = (e: KeyboardEvent, combo: string): boolean => {
  const parts = combo.toLowerCase().split("+");
  const key = parts[parts.length - 1];

  const matchCtrl = (parts.includes("ctrl") || parts.includes("control")) ? e.ctrlKey : !e.ctrlKey;
  const matchShift = parts.includes("shift") ? e.shiftKey : !e.shiftKey;
  const matchAlt = parts.includes("alt") ? e.altKey : !e.altKey;
  // Meta/Windows key: si el combo lo especifica, debe estar presionado
  const matchMeta = parts.includes("meta") ? e.metaKey : true;

  let matchKey = false;
  if (key === "control" && e.key === "Control") matchKey = true;
  else if (key === "shift" && e.key === "Shift") matchKey = true;
  else if (key === "alt" && e.key === "Alt") matchKey = true;
  else if (key === "meta" && e.key === "Meta") matchKey = true;
  else if (e.key.toLowerCase() === key) matchKey = true;

  return matchCtrl && matchShift && matchAlt && matchMeta && matchKey;
};

/**
 * Hook para interceptar la pulsación de teclado PTT.
 *
 * Soporta dos modos:
 *   - Modo "two-key": START y STOP son diferentes → keydown de START activa, keydown/keyup de STOP desactiva.
 *   - Modo "toggle": START y STOP son iguales → keydown alterna START/STOP según el modo actual (press-to-toggle).
 *
 * Local keydown/keyup: SIEMPRE activos (tanto en navegador como en Tauri).
 *   Capturan la tecla cuando la ventana tiene el foco.
 *
 * Tauri global-shortcut: adicional (backup OS-level).
 *   Plugin global-shortcut para cuando la ventana NO tiene el foco.
 */
export function useHotkey({ onKeyDown, onKeyUp }: UseHotkeyProps) {
  const { config } = useAppStore();
  const currentHotkey = config.pttHotkey || DEFAULT_PTT_HOTKEY;
  const stopHotkey = config.pttStopHotkey || DEFAULT_PTT_HOTKEY;
  const isToggleMode = currentHotkey.toLowerCase() === stopHotkey.toLowerCase();

  // Ref para evitar recrear callbacks
  const onKeyDownRef = useRef(onKeyDown);
  const onKeyUpRef = useRef(onKeyUp);

  useEffect(() => {
    onKeyDownRef.current = onKeyDown;
    onKeyUpRef.current = onKeyUp;
  }, [onKeyDown, onKeyUp]);

  // ─────────────────────────────────────────────────────────────
  // Manejador local (keydown/keyup — siempre activo, incluso en Tauri)
  // ─────────────────────────────────────────────────────────────
  useEffect(() => {

    let active = false;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (isEditableTarget(event.target)) return;

      // Modo toggle: keydown alterna START/STOP según el modo actual
      if (isToggleMode && matchesKeyCombo(event, currentHotkey)) {
        event.preventDefault();
        const mode = useAppStore.getState().radio.mode;
        console.log(`[useHotkey] Toggle keydown: ${currentHotkey} (mode=${mode})`);
        if (mode === "IDLE") {
          onKeyDownRef.current();
        } else if (mode === "LISTENING_PILOT") {
          onKeyUpRef.current();
        }
        return;
      }
      // Modo two-key: START keydown → activar
      if (!isToggleMode && matchesKeyCombo(event, currentHotkey) && !active) {
        active = true;
        event.preventDefault();
        console.log("[useHotkey] PTT Activado (keydown local)");
        onKeyDownRef.current();
        return;
      }
      // Modo two-key: STOP keydown → activar
      if (!isToggleMode && matchesKeyCombo(event, stopHotkey) && !active) {
        active = true;
        event.preventDefault();
        console.log("[useHotkey] PTT Activado (STOP keydown local)");
        onKeyDownRef.current();
      }
    };

    const handleKeyUp = (event: KeyboardEvent) => {
      if (isEditableTarget(event.target)) return;
      // Modo toggle: no requiere keyup (alternancia es solo keydown)
      if (isToggleMode) return;
      // Modo two-key: STOP keyup → desactivar
      if (!isToggleMode && matchesKeyCombo(event, stopHotkey) && active) {
        active = false;
        event.preventDefault();
        console.log("[useHotkey] PTT Desactivado (STOP keyup local)");
        onKeyUpRef.current();
        return;
      }
      // Modo two-key: START keyup → desactivar
      if (!isToggleMode && matchesKeyCombo(event, currentHotkey) && active) {
        active = false;
        event.preventDefault();
        console.log("[useHotkey] PTT Desactivado (START keyup local)");
        onKeyUpRef.current();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [currentHotkey, stopHotkey, isToggleMode]);

  // ─────────────────────────────────────────────────────────────
  // Registro global de Tauri (atajos start / stop)
  // ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isTauri) return;

    let cleanupFns: (() => void)[] = [];

    const setupGlobalShortcuts = async () => {
      try {
        const { register, unregister, isRegistered } = await import("@tauri-apps/plugin-global-shortcut");

        const keysToRegister = isToggleMode
          ? [currentHotkey]
          : [currentHotkey, stopHotkey];
        const globalKeys = keysToRegister.filter(canRegisterGlobalHotkey);
        if (globalKeys.length < keysToRegister.length) {
          console.warn(
            "[useHotkey] Atajo sin modificador (ej. P): PTT solo con ventana enfocada. " +
              "Usa Ctrl+Shift+Space para PTT global en juego.",
          );
        }

        // Limpiar registros previos
        for (const key of keysToRegister) {
          if (await isRegistered(key)) {
            await unregister(key);
          }
        }

        if (isToggleMode) {
          if (!canRegisterGlobalHotkey(currentHotkey)) {
            console.log(`[useHotkey] Atajo local only: ${currentHotkey}`);
            return;
          }
          // Un solo atajo toggle: IDLE→LISTENING, LISTENING→THINKING
          await register(currentHotkey, () => {
            const mode = useAppStore.getState().radio.mode;
            console.log(`[useHotkey] Global TOGGLE detectado: ${currentHotkey} (mode=${mode})`);
            if (mode === "IDLE") {
              onKeyDownRef.current();
            } else if (mode === "LISTENING_PILOT") {
              onKeyUpRef.current();
            }
          });
          cleanupFns.push(() => {
            unregister(currentHotkey).catch(() => {});
          });
          console.log(`[useHotkey] Atajo global toggle registrado: ${currentHotkey}`);
        } else {
          if (canRegisterGlobalHotkey(currentHotkey)) {
            await register(currentHotkey, () => {
              const mode = useAppStore.getState().radio.mode;
              console.log(`[useHotkey] Global START detectado: ${currentHotkey} (mode=${mode})`);
              if (mode === "IDLE") {
                onKeyDownRef.current();
              }
            });
            cleanupFns.push(() => {
              unregister(currentHotkey).catch(() => {});
            });
          }

          if (canRegisterGlobalHotkey(stopHotkey)) {
            await register(stopHotkey, () => {
              const mode = useAppStore.getState().radio.mode;
              console.log(`[useHotkey] Global STOP detectado: ${stopHotkey} (mode=${mode})`);
              if (mode === "LISTENING_PILOT") {
                onKeyUpRef.current();
              }
            });
            cleanupFns.push(() => {
              unregister(stopHotkey).catch(() => {});
            });
          }

          console.log(`[useHotkey] Atajos globales registrados: START=${currentHotkey}  STOP=${stopHotkey}`);
        }
      } catch (err) {
        console.error("[useHotkey] Error al registrar atajos globales en Tauri:", err);
      }
    };

    // Diferir registro: global-shortcut al arranque congela WebView2 en Windows
    const timer = window.setTimeout(() => {
      void setupGlobalShortcuts();
    }, 4000);

    return () => {
      window.clearTimeout(timer);
      for (const cleanup of cleanupFns) {
        cleanup();
      }
    };
  }, [currentHotkey, stopHotkey, isToggleMode]);

  return {
    isRegistered: true,
  };
}

export default useHotkey;
