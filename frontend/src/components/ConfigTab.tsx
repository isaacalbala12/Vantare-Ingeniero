import React, { useState, useEffect, useRef } from "react";
import { useAppStore, AppConfig } from "../store/config";
import { sendConfigUpdate } from "../services/configUpdateWs";
import { validateSpotterFields } from "../hub/forms/configValidation";
import { AudioTtsPanel } from "../hub/sections/AudioTtsPanel";
import { UpdatesPanel } from "../hub/sections/UpdatesPanel";
import { HotkeyCapture } from "../hub/components/HotkeyCapture";
import { assertFullAppConfig } from "../hub/forms/appConfigKeys";
import { migrateTtsVolumePercent } from "../hub/forms/volumeMigration";
import {
  deleteProfile,
  getHealth,
  listProfiles,
  loadProfile,
  saveProfile,
} from "../services/api";

type TabName = "conexion" | "audio" | "voz";

export type ConfigHubSection =
  | "audio"
  | "ingeniero"
  | "spotter"
  | "perfiles"
  | "avanzado";

interface ConfigTabProps {
  section?: ConfigHubSection;
}

/**
 * Panel de configuración unificado con 3 pestañas:
 * - Conexión: IP del servidor, puerto, test de conexión
 * - Audio: dispositivo de micrófono, sensibilidad, vúmetro
 * - Voz: hotkey PTT, palabra de activación
 */
export const ConfigTab: React.FC<ConfigTabProps> = ({ section }) => {
  const { config, connectivity, updateConfig, applyProfileConfig, setMicLevel } = useAppStore();
  const sectionToTab = (s?: ConfigHubSection): TabName => {
    if (s === "audio") return "audio";
    return "voz";
  };
  const [activeTab, setActiveTab] = useState<TabName>(sectionToTab(section));

  const [profiles, setProfiles] = useState<string[]>([]);
  const [selectedProfile, setSelectedProfile] = useState("");
  const [newProfileName, setNewProfileName] = useState("");
  const [profileStatus, setProfileStatus] = useState<string | null>(null);

  // Estados locales para los campos del formulario
  const [vllmIP, setVllmIP] = useState(config.vllmIP);
  const [serverPort, setServerPort] = useState(config.serverPort ?? 8008);
  const [micDevice, setMicDevice] = useState(config.micDevice);
  const [sensitivity, setSensitivity] = useState(config.sensitivity ?? 50);
  const [pttHotkey, setPttHotkey] = useState(config.pttHotkey ?? "Ctrl+Shift+Space");
  const [pttStopHotkey, setPttStopHotkey] = useState(config.pttStopHotkey ?? "Ctrl+Shift+Space");
  const [swearyMessages, setSwearyMessages] = useState(config.swearyMessages ?? false);
  const [spotterOffQualifying, setSpotterOffQualifying] = useState(config.spotterOffQualifying ?? true);
  const [spotterExcludeStopped, setSpotterExcludeStopped] = useState(config.spotterExcludeStopped ?? true);
  const [mqttEnabled, setMqttEnabled] = useState(config.mqttEnabled ?? false);
  const [mqttBroker, setMqttBroker] = useState(config.mqttBroker ?? "localhost");
  const [mqttPort, setMqttPort] = useState(config.mqttPort ?? 1883);
  const [personalityProfileId, setPersonalityProfileId] = useState<AppConfig["personalityProfileId"]>(
    config.personalityProfileId ?? "standard",
  );
  const [verbosityLevel, setVerbosityLevel] = useState<AppConfig["verbosityLevel"]>(
    config.verbosityLevel ?? "normal",
  );
  const [ttsVoiceEngineer, setTtsVoiceEngineer] = useState(config.ttsVoiceEngineer ?? "es-ES-AlvaroNeural");
  const [ttsVoiceSpotter, setTtsVoiceSpotter] = useState(config.ttsVoiceSpotter ?? "es-ES-ElviraNeural");
  const [spotterClearDelayS, setSpotterClearDelayS] = useState(config.spotterClearDelayS ?? 0.15);
  const [spotterHoldRepeatS, setSpotterHoldRepeatS] = useState(config.spotterHoldRepeatS ?? 3.0);
  const [spotterGapFrequencyS, setSpotterGapFrequencyS] = useState(config.spotterGapFrequencyS ?? 30);
  const [spotterCarLengthM, setSpotterCarLengthM] = useState(config.spotterCarLengthM ?? 4.5);
  const [spotterMinSpeedMs, setSpotterMinSpeedMs] = useState(config.spotterMinSpeedMs ?? 10.0);
  const [spotterRaceStartDelayS, setSpotterRaceStartDelayS] = useState(config.spotterRaceStartDelayS ?? 20.0);
  const [brakingZonesMute, setBrakingZonesMute] = useState(config.brakingZonesMute ?? false);
  const [ttsVolumeBoost, setTtsVolumeBoost] = useState(config.ttsVolumeBoost ?? 100);

  // Estados de test y dispositivos
  const [testStatus, setTestStatus] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [micDevices, setMicDevices] = useState<MediaDeviceInfo[]>([]);
  const [localLevel, setLocalLevel] = useState(0);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const prevTabRef = useRef<TabName>(activeTab);

  const hydrateRuntimeFieldsFromStore = () => {
    setPersonalityProfileId(config.personalityProfileId ?? "standard");
    setVerbosityLevel(config.verbosityLevel ?? "normal");
    setBrakingZonesMute(config.brakingZonesMute ?? false);
    setSwearyMessages(config.swearyMessages ?? false);
    setSpotterClearDelayS(config.spotterClearDelayS ?? 0.15);
    setSpotterHoldRepeatS(config.spotterHoldRepeatS ?? 3.0);
    setSpotterGapFrequencyS(config.spotterGapFrequencyS ?? 30);
    setSpotterCarLengthM(config.spotterCarLengthM ?? 4.5);
    setSpotterMinSpeedMs(config.spotterMinSpeedMs ?? 10.0);
    setSpotterRaceStartDelayS(config.spotterRaceStartDelayS ?? 20.0);
    setSpotterOffQualifying(config.spotterOffQualifying ?? true);
    setSpotterExcludeStopped(config.spotterExcludeStopped ?? true);
  };

  // Leer micLevel del store
  useAppStore((state) => state.radio.micLevel);

  // 1. Enumerar dispositivos (sin getUserMedia hasta pestaña Audio — evita modal WebView2)
  useEffect(() => {
    const listDevices = async () => {
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        setMicDevices(devices.filter((d) => d.kind === "audioinput"));
      } catch (e) {
        console.warn("Fallo al enumerar dispositivos:", e);
      }
    };
    void listDevices();
  }, []);

  useEffect(() => {
    if (activeTab !== "audio") return;
    const refreshWithLabels = async () => {
      try {
        await navigator.mediaDevices.getUserMedia({ audio: true }).catch(() => {});
        const devices = await navigator.mediaDevices.enumerateDevices();
        setMicDevices(devices.filter((d) => d.kind === "audioinput"));
      } catch (e) {
        console.warn("Fallo al refrescar dispositivos de audio:", e);
      }
    };
    void refreshWithLabels();
  }, [activeTab]);

  const refreshProfiles = async () => {
    const names = await listProfiles();
    setProfiles(names);
  };

  useEffect(() => {
    if (section) setActiveTab(sectionToTab(section));
  }, [section]);

  useEffect(() => {
    if (section === "perfiles" || activeTab === "conexion") {
      refreshProfiles();
    }
  }, [activeTab, section]);

  useEffect(() => {
    if (prevTabRef.current !== "voz" && activeTab === "voz") {
      hydrateRuntimeFieldsFromStore();
    }
    prevTabRef.current = activeTab;
  }, [activeTab, config]);

  const buildConfigPayload = (): AppConfig => {
    const payload: AppConfig = {
      vllmIP: vllmIP.trim(),
      serverPort: Number(serverPort),
      micDevice,
      speakerDevice: config.speakerDevice,
      wakeWord: config.wakeWord,
      sensitivity,
      pttHotkey: pttHotkey.trim(),
      pttStopHotkey: pttStopHotkey.trim(),
      wakeWordEnabled: config.wakeWordEnabled,
      swearyMessages,
      spotterOffQualifying,
      spotterExcludeStopped,
      mqttEnabled,
      mqttBroker: mqttBroker.trim(),
      mqttPort: Number(mqttPort),
      personalityProfileId,
      verbosityLevel,
      ttsVoiceEngineer: ttsVoiceEngineer.trim(),
      ttsVoiceSpotter: ttsVoiceSpotter.trim(),
      ttsBackend: config.ttsBackend ?? "edge",
      spotterClearDelayS: Number(spotterClearDelayS),
      spotterOverlapDelayS: config.spotterOverlapDelayS ?? 2.0,
      spotterHoldRepeatS: Number(spotterHoldRepeatS),
      spotterGapFrequencyS: Number(spotterGapFrequencyS),
      spotterCarLengthM: Number(spotterCarLengthM),
      spotterMinSpeedMs: Number(spotterMinSpeedMs),
      spotterRaceStartDelayS: Number(spotterRaceStartDelayS),
      brakingZonesMute,
      speakOnlyWhenSpokenTo: config.speakOnlyWhenSpokenTo,
      ttsVolumeBoost: Number(ttsVolumeBoost),
      spotterEnabled: config.spotterEnabled,
      engineerEnabled: config.engineerEnabled,
    };
    assertFullAppConfig(payload);
    return payload;
  };

  const applyLoadedConfig = (loaded: Record<string, unknown>): AppConfig => {
    const merged: AppConfig = {
      ...config,
      ...loaded,
    } as AppConfig;
    applyProfileConfig(merged);
    setVllmIP(merged.vllmIP);
    setServerPort(merged.serverPort);
    setMicDevice(merged.micDevice);
    setSensitivity(merged.sensitivity);
    setPttHotkey(merged.pttHotkey);
    setPttStopHotkey(merged.pttStopHotkey);
    setSwearyMessages(merged.swearyMessages);
    setSpotterOffQualifying(merged.spotterOffQualifying);
    setSpotterExcludeStopped(merged.spotterExcludeStopped);
    setMqttEnabled(merged.mqttEnabled ?? false);
    setMqttBroker(merged.mqttBroker ?? "localhost");
    setMqttPort(merged.mqttPort ?? 1883);
    setPersonalityProfileId(merged.personalityProfileId ?? "standard");
    setVerbosityLevel(merged.verbosityLevel ?? "normal");
    setTtsVoiceEngineer(merged.ttsVoiceEngineer ?? "es-ES-AlvaroNeural");
    setTtsVoiceSpotter(merged.ttsVoiceSpotter ?? "es-ES-ElviraNeural");
    setSpotterClearDelayS(merged.spotterClearDelayS ?? 0.15);
    setSpotterHoldRepeatS(merged.spotterHoldRepeatS ?? 3.0);
    setSpotterGapFrequencyS(merged.spotterGapFrequencyS ?? 30);
    setSpotterCarLengthM(merged.spotterCarLengthM ?? 4.5);
    setSpotterMinSpeedMs(merged.spotterMinSpeedMs ?? 10.0);
    setSpotterRaceStartDelayS(merged.spotterRaceStartDelayS ?? 20.0);
    setBrakingZonesMute(merged.brakingZonesMute ?? false);
    setTtsVolumeBoost(migrateTtsVolumePercent(merged.ttsVolumeBoost));
    return merged;
  };

  const handleLoadProfile = async () => {
    if (!selectedProfile) return;
    const loaded = await loadProfile(selectedProfile);
    if (!loaded) {
      setProfileStatus("❌ No se pudo cargar el perfil");
      setTimeout(() => setProfileStatus(null), 3000);
      return;
    }
    const merged = applyLoadedConfig(loaded);
    sendConfigUpdate(merged);
    setProfileStatus(`✅ Perfil "${selectedProfile}" cargado`);
    setTimeout(() => setProfileStatus(null), 2500);
  };

  const handleSaveProfile = async () => {
    const name = (newProfileName || selectedProfile).trim();
    if (!name) {
      setProfileStatus("❌ Indica un nombre de perfil");
      setTimeout(() => setProfileStatus(null), 3000);
      return;
    }
    const ok = await saveProfile(name, buildConfigPayload() as unknown as Record<string, unknown>);
    if (!ok) {
      setProfileStatus("❌ Error al guardar perfil");
      setTimeout(() => setProfileStatus(null), 3000);
      return;
    }
    setSelectedProfile(name);
    setNewProfileName("");
    await refreshProfiles();
    setProfileStatus(`✅ Perfil "${name}" guardado`);
    setTimeout(() => setProfileStatus(null), 2500);
  };

  const handleDeleteProfile = async () => {
    if (!selectedProfile) return;
    const ok = await deleteProfile(selectedProfile);
    if (!ok) {
      setProfileStatus("❌ Error al eliminar");
      setTimeout(() => setProfileStatus(null), 3000);
      return;
    }
    setSelectedProfile("");
    await refreshProfiles();
    setProfileStatus("✅ Perfil eliminado");
    setTimeout(() => setProfileStatus(null), 2500);
  };

  // 2. Captura local de audio para el vúmetro (solo en pestaña Audio)
  useEffect(() => {
    let animationFrameId: number;

    const startMic = async () => {
      if (activeTab !== "audio") return;
      try {
        const constraints = {
          audio: micDevice && micDevice !== "default" ? { deviceId: { exact: micDevice } } : true,
        };
        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        streamRef.current = stream;

        const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
        const audioContext = new AudioCtx();
        audioContextRef.current = audioContext;

        const source = audioContext.createMediaStreamSource(stream);
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);

        const dataArray = new Uint8Array(analyser.frequencyBinCount);

        const updateLevel = () => {
          if (activeTab !== "audio") return;
          analyser.getByteFrequencyData(dataArray);
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
          }
          const avg = sum / dataArray.length;
          const pct = Math.min(100, Math.round(avg * 2.2));
          setLocalLevel(pct);
          setMicLevel(pct);
          animationFrameId = requestAnimationFrame(updateLevel);
        };
        updateLevel();
      } catch (e) {
        console.warn("Fallo al iniciar el vúmetro:", e);
      }
    };

    const stopMic = () => {
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }
      setLocalLevel(0);
      setMicLevel(0);
    };

    if (activeTab === "audio") {
      startMic();
    } else {
      stopMic();
    }

    return stopMic;
  }, [activeTab, micDevice]);

  // 3. Test de conexión
  const handleTestConnection = async () => {
    setTestStatus("Probando...");
    try {
      const health = await getHealth();
      if (health?.status === "ok") {
        setTestStatus("✅ Backend OK");
      } else {
        setTestStatus("❌ Backend no responde");
      }
    } catch (e) {
      setTestStatus("❌ Error de conexión");
    }
    setTimeout(() => setTestStatus(null), 3000);
  };

  // 4. Guardar configuración con validación
  const handleSave = () => {
    // Validar IP
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$|^localhost$|^[a-zA-Z0-9.-]+$/;
    if (!vllmIP.trim() || !ipRegex.test(vllmIP.trim())) {
      setSaveStatus("❌ IP inválida (ej: 192.168.1.100 o localhost)");
      setTimeout(() => setSaveStatus(null), 3000);
      return;
    }
    // Validar puerto
    const portNum = Number(serverPort);
    if (isNaN(portNum) || portNum < 1 || portNum > 65535) {
      setSaveStatus("❌ Puerto debe ser 1-65535");
      setTimeout(() => setSaveStatus(null), 3000);
      return;
    }
    // Validar hotkey START (no vacío)
    if (!pttHotkey.trim()) {
      setSaveStatus("❌ START no puede estar vacío");
      setTimeout(() => setSaveStatus(null), 3000);
      return;
    }
    // Validar hotkey STOP (no vacío)
    if (!pttStopHotkey.trim()) {
      setSaveStatus("❌ STOP no puede estar vacío");
      setTimeout(() => setSaveStatus(null), 3000);
      return;
    }
    // Prevenir atajos peligrosos conocidos
    const dangerousKeys = ["alt+f4", "ctrl+w", "ctrl+q", "f12"];
    const startLower = pttHotkey.trim().toLowerCase();
    const stopLower = pttStopHotkey.trim().toLowerCase();
    if (dangerousKeys.includes(startLower) || dangerousKeys.includes(stopLower)) {
      setSaveStatus("❌ Atajo reservado del sistema. Elige otro.");
      setTimeout(() => setSaveStatus(null), 3000);
      return;
    }
    const isBareKey = (combo: string) => {
      const trimmed = combo.trim();
      if (/^mouse/i.test(trimmed)) return false;
      if (/^pad\d+:b\d+$/i.test(trimmed)) return false;
      const parts = trimmed.split("+");
      if (parts.length > 1) return false;
      const key = parts[0].toLowerCase();
      return !/^f([1-9]|1[0-2])$/.test(key);
    };
    if (isBareKey(startLower) || isBareKey(stopLower)) {
      setSaveStatus("❌ Usa modificador (ej. Ctrl+Shift+Space) — teclas sueltas interfieren al escribir.");
      setTimeout(() => setSaveStatus(null), 4000);
      return;
    }

    const spotterValidation = validateSpotterFields({
      spotterClearDelayS: Number(spotterClearDelayS),
      spotterHoldRepeatS: Number(spotterHoldRepeatS),
      spotterGapFrequencyS: Number(spotterGapFrequencyS),
      spotterCarLengthM: Number(spotterCarLengthM),
      spotterMinSpeedMs: Number(spotterMinSpeedMs),
      spotterRaceStartDelayS: Number(spotterRaceStartDelayS),
      ttsVolumeBoost: Number(ttsVolumeBoost),
    });
    if (!spotterValidation.ok) {
      setSaveStatus("❌ Revisa valores spotter/TTS (clear ≥0.1s, hold ≥0.5s, gap 5–120s, longitud 3–8m, volumen 0–100)");
      setTimeout(() => setSaveStatus(null), 4000);
      return;
    }

    const payload = buildConfigPayload();
    updateConfig(payload);
    sendConfigUpdate(payload);
    setSaveStatus("✅ Guardado");
    setTimeout(() => setSaveStatus(null), 2000);
  };

  // Barra de vúmetro
  const Vumeter: React.FC<{ level: number; label?: string }> = ({ level, label }) => (
    <div className="flex flex-col gap-1">
      {label && <span className="text-[10px] text-[#aaa]">{label}</span>}
      <div className="h-2 bg-[#222] rounded overflow-hidden w-full">
        <div 
          className="h-full bg-[#8a2be2] transition-none"
          style={{ width: `${level}%` }}
        />
      </div>
      <span className="text-[10px] text-[#666]">{level}%</span>
    </div>
  );

  const showIngeniero = !section || section === "ingeniero" || section === "avanzado";
  const showSpotter = !section || section === "spotter" || section === "avanzado";
  const showPtt = !section || section === "audio";
  const showAudioFields = !section || section === "audio";
  const showMqtt = !section || section === "avanzado";
  const showProfilesOnly = section === "perfiles";
  const showVozSection =
    (activeTab === "voz" && !section) ||
    section === "ingeniero" ||
    section === "spotter" ||
    section === "avanzado";
  const hubMode = Boolean(section);

  return (
    <div className={`w-full h-full flex flex-col text-white ${hubMode ? "hub-root" : ""}`} style={{ fontFamily: "var(--font-a1-body, system-ui, sans-serif)" }}>
      {/* Tabs */}
      {!section && (
      <div className="flex border-b border-hub-border">
        {(["conexion", "audio", "voz"] as TabName[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-2 text-[11px] font-bold uppercase tracking-wider transition-none ${
              activeTab === tab
                ? "text-a1-accent border-b-2 border-a1-accent"
                : "text-a1-text-muted hover:text-a1-text"
            }`}
          >
            {tab === "conexion" ? "Conexión" : tab === "audio" ? "Audio" : "Voz"}
          </button>
        ))}
      </div>
      )}

      {/* Contenido de tabs */}
      <div className="flex-1 overflow-auto px-3 py-3">
        
        {/* TAB: CONEXIÓN (oculta en hub mode) */}
        {(!hubMode && activeTab === "conexion" || showProfilesOnly) && (
          <div className="flex flex-col gap-3">
            {!showProfilesOnly && (
              <>
            <div className="flex flex-col gap-1">
              <label className="hub-label">IP del Servidor</label>
              <input
                type="text"
                value={vllmIP}
                onChange={(e) => setVllmIP(e.target.value)}
                className="hub-input"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="hub-label">Puerto</label>
              <input
                type="number"
                value={serverPort}
                onChange={(e) => setServerPort(Number(e.target.value))}
                className="hub-input w-24"
              />
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleTestConnection}
                className="hub-btn-primary"
              >
                Probar conexión
              </button>
              {testStatus && (
                <span className="text-[12px] text-a1-text-muted">{testStatus}</span>
              )}
            </div>
            {connectivity.backendHealth && (
              <div className="mt-2 p-2 bg-hub-card border border-hub-border rounded text-[10px] flex flex-col gap-1">
                <div className="text-a1-text-muted uppercase tracking-wider mb-1">Estado del Backend:</div>
                <div>Shared Memory: <span className={connectivity.backendHealth.shared_memory ? "text-emerald-400" : "text-red-400"}>{connectivity.backendHealth.shared_memory ? "ON" : "OFF"}</span></div>
                <div>LMU API: <span className={connectivity.backendHealth.lmu_api ? "text-emerald-400" : "text-red-400"}>{connectivity.backendHealth.lmu_api ? "ON" : "OFF"}</span></div>
                <div>LLM: <span className={connectivity.backendHealth.llm ? "text-emerald-400" : "text-red-400"}>{connectivity.backendHealth.llm ? "ON" : "OFF"}</span></div>
                <div>WebSocket: <span className={connectivity.backendHealth.websocket ? "text-emerald-400" : "text-red-400"}>{connectivity.backendHealth.websocket ? "ON" : "OFF"}</span></div>
              </div>
            )}
              </>
            )}
            {(section === "perfiles" || (!section && activeTab === "conexion")) && (
            <div className="mt-3 p-2 bg-hub-card border border-hub-border rounded flex flex-col gap-2">
              <div className="text-[10px] text-[#666] uppercase tracking-wider">Perfiles</div>
              <select
                value={selectedProfile}
                onChange={(e) => setSelectedProfile(e.target.value)}
                className="bg-[#111] border border-[#333] rounded px-2 py-1.5 text-[12px] text-white"
              >
                <option value="">Seleccionar perfil...</option>
                {profiles.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
              <input
                type="text"
                placeholder="Nombre nuevo (ej: endurance)"
                value={newProfileName}
                onChange={(e) => setNewProfileName(e.target.value)}
                className="bg-[#111] border border-[#333] rounded px-2 py-1.5 text-[12px] text-white"
              />
              <div className="flex gap-2 flex-wrap">
                <button onClick={handleLoadProfile} className="text-[10px] bg-[#333] px-2 py-1 rounded uppercase">Cargar</button>
                <button onClick={handleSaveProfile} className="text-[10px] bg-[#333] px-2 py-1 rounded uppercase">Guardar</button>
                <button onClick={handleDeleteProfile} className="text-[10px] bg-[#442222] px-2 py-1 rounded uppercase">Eliminar</button>
              </div>
              {profileStatus && <span className="text-[11px] text-a1-text-muted">{profileStatus}</span>}
            </div>
            )}
            {!showProfilesOnly && (
            <button
              onClick={handleSave}
              className="mt-2 hub-btn-secondary w-fit"
            >
              {saveStatus || "Guardar"}
            </button>
            )}
          </div>
        )}

        {/* TAB: AUDIO */}
        {(activeTab === "audio" || section === "audio") && section !== "perfiles" && showAudioFields && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Dispositivo de Micrófono</label>
              <select
                value={micDevice}
                onChange={(e) => setMicDevice(e.target.value)}
                className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1.5 text-[12px] text-white focus:border-[#8a2be2] focus:outline-none"
              >
                <option value="default">Predeterminado</option>
                {micDevices.map((d) => (
                  <option key={d.deviceId} value={d.deviceId}>
                    {d.label || `Micrófono ${d.deviceId.slice(0, 8)}`}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Sensibilidad ({sensitivity}%)</label>
              <input
                type="range"
                min="10"
                max="100"
                value={sensitivity}
                onChange={(e) => setSensitivity(Number(e.target.value))}
                className="w-full accent-[#8a2be2]"
              />
            </div>
            <div className="mt-2">
              <Vumeter level={localLevel} label="Nivel del micrófono" />
            </div>
            <AudioTtsPanel
              ttsVoiceEngineer={ttsVoiceEngineer}
              ttsVoiceSpotter={ttsVoiceSpotter}
              ttsVolumeBoost={ttsVolumeBoost}
              onEngineerVoice={setTtsVoiceEngineer}
              onSpotterVoice={setTtsVoiceSpotter}
              onVolume={setTtsVolumeBoost}
            />
            {section === "audio" && showPtt && (
              <>
                <HotkeyCapture label="Tecla PTT (START)" value={pttHotkey} onChange={setPttHotkey} />
                <HotkeyCapture label="Tecla PTT (STOP)" value={pttStopHotkey} onChange={setPttStopHotkey} />
                <p className="text-[10px] text-a1-text-muted leading-relaxed">
                  En pista: atajos globales de teclado. Si START y STOP son distintos, STOP solo con el hub
                  enfocado. Botones del ratón solo con el hub enfocado.
                </p>
              </>
            )}
            <button
              onClick={handleSave}
              className="mt-2 hub-btn-secondary w-fit"
            >
              {saveStatus || "Guardar"}
            </button>
          </div>
        )}

        {/* TAB: VOZ / secciones hub */}
        {showVozSection && (
          <div className="flex flex-col gap-3">
            {section === "avanzado" && <UpdatesPanel />}
            {showPtt && (
              <>
            <HotkeyCapture label="Tecla PTT (START)" value={pttHotkey} onChange={setPttHotkey} />
            <HotkeyCapture label="Tecla PTT (STOP)" value={pttStopHotkey} onChange={setPttStopHotkey} />
              </>
            )}
            {showIngeniero && (
              <>
            <label className="flex items-center gap-2 text-[12px] text-a1-text cursor-pointer">
              <input
                type="checkbox"
                checked={swearyMessages}
                onChange={(e) => setSwearyMessages(e.target.checked)}
                className="accent-a1-accent"
              />
              Lenguaje de paddock (juramentos opcionales)
            </label>
            <div className="flex flex-col gap-1">
              <label className="hub-label">Perfil de personalidad</label>
              <select
                value={personalityProfileId}
                onChange={(e) => setPersonalityProfileId(e.target.value as AppConfig["personalityProfileId"])}
                className="hub-input"
              >
                <option value="formal">Formal</option>
                <option value="standard">Estándar</option>
                <option value="aggressive">Agresivo</option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="hub-label">Verbosidad del ingeniero</label>
              <select
                value={verbosityLevel}
                onChange={(e) => setVerbosityLevel(e.target.value as AppConfig["verbosityLevel"])}
                className="hub-input"
              >
                <option value="silent">Silencioso (solo crítico + spotter)</option>
                <option value="normal">Normal</option>
                <option value="detailed">Detallado</option>
              </select>
            </div>
            <label className="flex items-center gap-2 text-[12px] text-a1-text cursor-pointer">
              <input
                type="checkbox"
                checked={brakingZonesMute}
                onChange={(e) => setBrakingZonesMute(e.target.checked)}
                className="accent-a1-accent"
              />
              Silenciar TTS del ingeniero al frenar (zonas de frenada)
            </label>
              </>
            )}
            {showSpotter && (
              <>
            <div className="grid grid-cols-2 gap-2 mt-1">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Clear delay (s)</label>
                <input type="number" step="0.05" min="0.1" max="5" value={spotterClearDelayS}
                  onChange={(e) => setSpotterClearDelayS(Number(e.target.value))}
                  className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-[12px] text-white" />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Hold repeat (s)</label>
                <input type="number" step="0.5" min="0.5" max="30" value={spotterHoldRepeatS}
                  onChange={(e) => setSpotterHoldRepeatS(Number(e.target.value))}
                  className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-[12px] text-white" />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Gap frequency (s)</label>
                <input type="number" step="1" min="10" max="120" value={spotterGapFrequencyS}
                  onChange={(e) => setSpotterGapFrequencyS(Number(e.target.value))}
                  className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-[12px] text-white" />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Car length (m)</label>
                <input type="number" step="0.1" min="3.5" max="6.5" value={spotterCarLengthM}
                  onChange={(e) => setSpotterCarLengthM(Number(e.target.value))}
                  className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-[12px] text-white" />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Min speed (m/s)</label>
                <input type="number" step="1" min="0" max="40" value={spotterMinSpeedMs}
                  onChange={(e) => setSpotterMinSpeedMs(Number(e.target.value))}
                  className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-[12px] text-white" />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Race start delay (s)</label>
                <input type="number" step="1" min="0" max="120" value={spotterRaceStartDelayS}
                  onChange={(e) => setSpotterRaceStartDelayS(Number(e.target.value))}
                  className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-[12px] text-white" />
              </div>
            </div>
            <label className="flex items-center gap-2 text-[12px] text-[#ccc] cursor-pointer">
              <input
                type="checkbox"
                checked={spotterOffQualifying}
                onChange={(e) => setSpotterOffQualifying(e.target.checked)}
                className="accent-[#8a2be2]"
              />
              Silenciar spotter en clasificación (SC y combustible siguen activos)
            </label>
            <label className="flex items-center gap-2 text-[12px] text-a1-text cursor-pointer">
              <input
                type="checkbox"
                checked={spotterExcludeStopped}
                onChange={(e) => setSpotterExcludeStopped(e.target.checked)}
                className="accent-a1-accent"
              />
              Ignorar coches parados o en boxes
            </label>
              </>
            )}
            {showMqtt && (
              <>
            <label className="flex items-center gap-2 text-[12px] text-a1-text cursor-pointer">
              <input
                type="checkbox"
                checked={mqttEnabled}
                onChange={(e) => setMqttEnabled(e.target.checked)}
                className="accent-a1-accent"
              />
              Publicar telemetría vía MQTT (broker local)
            </label>
            {mqttEnabled && (
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  value={mqttBroker}
                  onChange={(e) => setMqttBroker(e.target.value)}
                  placeholder="Broker"
                  className="hub-input"
                />
                <input
                  type="number"
                  value={mqttPort}
                  onChange={(e) => setMqttPort(Number(e.target.value))}
                  placeholder="Puerto"
                  className="hub-input"
                />
              </div>
            )}
            <div className="text-[11px] text-a1-text-muted">
              Overlay resize: <span className="text-a1-accent">Ctrl+Shift+O</span>
            </div>
            <div className="flex flex-col gap-1">
              <label className="hub-label">Variante overlay</label>
              <select
                defaultValue={localStorage.getItem("overlayVariant") ?? "a1"}
                onChange={(e) => localStorage.setItem("overlayVariant", e.target.value)}
                className="hub-input max-w-xs"
              >
                <option value="a1">A1 — Racing red</option>
                <option value="a2">A2 — Terracota (preview)</option>
                <option value="a3">A3 — Minimal (preview)</option>
              </select>
            </div>
              </>
            )}
            {showPtt && (
            <div className="mt-2 p-2 bg-hub-card border border-hub-border rounded text-[11px] text-a1-text-muted">
              {pttHotkey.trim().toLowerCase() === pttStopHotkey.trim().toLowerCase()
                ? "Modo toggle: pulsa y suelta el botón PTT para transmitir."
                : "Pulsa START para hablar, pulsa STOP para enviar y recibir respuesta."}
              {" "}
              Volante/mando: asigna con el hub abierto; en pista funciona aunque el simulador tenga el foco.
            </div>
            )}
            <button
              onClick={handleSave}
              className="mt-2 hub-btn-secondary w-fit"
            >
              {saveStatus || "Guardar"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ConfigTab;