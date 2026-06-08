import React, { useState, useEffect, useRef } from "react";
import { useAppStore, AppConfig } from "../store/config";
import { sendConfigUpdate } from "../services/configUpdateWs";

type TabName = "conexion" | "audio" | "voz";

/**
 * Panel de configuración unificado con 3 pestañas:
 * - Conexión: IP del servidor, puerto, test de conexión
 * - Audio: dispositivo de micrófono, sensibilidad, vúmetro
 * - Voz: hotkey PTT, palabra de activación
 */
export const ConfigTab: React.FC = () => {
  const { config, connectivity, updateConfig, applyProfileConfig, setMicLevel } = useAppStore();
  const [activeTab, setActiveTab] = useState<TabName>("conexion");

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
  const [ttsVolumeBoost, setTtsVolumeBoost] = useState(config.ttsVolumeBoost ?? 1.0);

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
    if (activeTab === "conexion") {
      refreshProfiles();
    }
  }, [activeTab]);

  useEffect(() => {
    if (prevTabRef.current !== "voz" && activeTab === "voz") {
      hydrateRuntimeFieldsFromStore();
    }
    prevTabRef.current = activeTab;
  }, [activeTab, config]);

  const buildConfigPayload = (): AppConfig => ({
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
    ttsVolumeBoost: Number(ttsVolumeBoost),
  });

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
    setTtsVolumeBoost(merged.ttsVolumeBoost ?? 1.0);
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
      if (health.status === "ok") {
        setTestStatus("✅ Backend OK");
      } else {
        setTestStatus(`⚠️ ${health.status}`);
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
      const parts = combo.trim().split("+");
      if (parts.length > 1) return false;
      const key = parts[0].toLowerCase();
      return !/^f([1-9]|1[0-2])$/.test(key);
    };
    if (isBareKey(startLower) || isBareKey(stopLower)) {
      setSaveStatus("❌ Usa modificador (ej. Ctrl+Shift+Space) — teclas sueltas interfieren al escribir.");
      setTimeout(() => setSaveStatus(null), 4000);
      return;
    }

    const spotterClear = Number(spotterClearDelayS);
    const spotterHoldRepeat = Number(spotterHoldRepeatS);
    const spotterGap = Number(spotterGapFrequencyS);
    const spotterLength = Number(spotterCarLengthM);
    const spotterMinSpeed = Number(spotterMinSpeedMs);
    const spotterRaceStart = Number(spotterRaceStartDelayS);
    const volumeBoost = Number(ttsVolumeBoost);
    if (
      !Number.isFinite(spotterClear) || spotterClear < 0.1 || spotterClear > 10 ||
      !Number.isFinite(spotterHoldRepeat) || spotterHoldRepeat < 0.5 || spotterHoldRepeat > 30 ||
      !Number.isFinite(spotterGap) || spotterGap < 5 || spotterGap > 120 ||
      !Number.isFinite(spotterLength) || spotterLength < 3 || spotterLength > 8 ||
      !Number.isFinite(spotterMinSpeed) || spotterMinSpeed < 0 || spotterMinSpeed > 40 ||
      !Number.isFinite(spotterRaceStart) || spotterRaceStart < 0 || spotterRaceStart > 120 ||
      !Number.isFinite(volumeBoost) || volumeBoost < 0.5 || volumeBoost > 2
    ) {
      setSaveStatus("❌ Revisa valores spotter/TTS (clear ≥0.1s, hold ≥0.5s, gap 5–120s, longitud 3–8m, volumen 0.5–2)");
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

  return (
    <div className="w-full h-full flex flex-col text-white" style={{ fontFamily: "system-ui, sans-serif" }}>
      {/* Tabs */}
      <div className="flex border-b border-[#222]">
        {(["conexion", "audio", "voz"] as TabName[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-2 text-[11px] font-bold uppercase tracking-wider transition-none ${
              activeTab === tab
                ? "text-[#8a2be2] border-b-2 border-[#8a2be2]"
                : "text-[#555] hover:text-[#888]"
            }`}
          >
            {tab === "conexion" ? "Conexión" : tab === "audio" ? "Audio" : "Voz"}
          </button>
        ))}
      </div>

      {/* Contenido de tabs */}
      <div className="flex-1 overflow-auto px-3 py-3">
        
        {/* TAB: CONEXIÓN */}
        {activeTab === "conexion" && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">IP del Servidor</label>
              <input
                type="text"
                value={vllmIP}
                onChange={(e) => setVllmIP(e.target.value)}
                className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1.5 text-[13px] text-white focus:border-[#8a2be2] focus:outline-none"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Puerto</label>
              <input
                type="number"
                value={serverPort}
                onChange={(e) => setServerPort(Number(e.target.value))}
                className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1.5 text-[13px] text-white focus:border-[#8a2be2] focus:outline-none w-24"
              />
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleTestConnection}
                className="bg-[#8a2be2] hover:bg-[#9d3ff3] text-white text-[11px] font-bold uppercase tracking-wider px-3 py-1.5 rounded transition-none"
              >
                Probar conexión
              </button>
              {testStatus && (
                <span className="text-[12px] text-[#aaa]">{testStatus}</span>
              )}
            </div>
            {/* Estado del backend */}
            {connectivity.backendHealth && (
              <div className="mt-2 p-2 bg-[#1a1a1a] border border-[#222] rounded text-[10px] flex flex-col gap-1">
                <div className="text-[#666] uppercase tracking-wider mb-1">Estado del Backend:</div>
                <div>Shared Memory: <span className={connectivity.backendHealth.shared_memory ? "text-[#4f4]" : "text-[#f44]"}>{connectivity.backendHealth.shared_memory ? "ON" : "OFF"}</span></div>
                <div>LMU API: <span className={connectivity.backendHealth.lmu_api ? "text-[#4f4]" : "text-[#f44]"}>{connectivity.backendHealth.lmu_api ? "ON" : "OFF"}</span></div>
                <div>LLM: <span className={connectivity.backendHealth.llm ? "text-[#4f4]" : "text-[#f44]"}>{connectivity.backendHealth.llm ? "ON" : "OFF"}</span></div>
                <div>WebSocket: <span className={connectivity.backendHealth.websocket ? "text-[#4f4]" : "text-[#f44]"}>{connectivity.backendHealth.websocket ? "ON" : "OFF"}</span></div>
              </div>
            )}
            <div className="mt-3 p-2 bg-[#1a1a1a] border border-[#222] rounded flex flex-col gap-2">
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
              {profileStatus && <span className="text-[11px] text-[#aaa]">{profileStatus}</span>}
            </div>
            <button
              onClick={handleSave}
              className="mt-2 bg-[#333] hover:bg-[#444] text-white text-[11px] font-bold uppercase tracking-wider px-3 py-1.5 rounded transition-none"
            >
              {saveStatus || "Guardar"}
            </button>
          </div>
        )}

        {/* TAB: AUDIO */}
        {activeTab === "audio" && (
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
            <button
              onClick={handleSave}
              className="mt-2 bg-[#333] hover:bg-[#444] text-white text-[11px] font-bold uppercase tracking-wider px-3 py-1.5 rounded transition-none"
            >
              {saveStatus || "Guardar"}
            </button>
          </div>
        )}

        {/* TAB: VOZ */}
        {activeTab === "voz" && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Tecla PTT</label>
              <input
                type="text"
                value={pttHotkey}
                onChange={(e) => setPttHotkey(e.target.value)}
                className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1.5 text-[13px] text-white focus:border-[#8a2be2] focus:outline-none"
              />
              <span className="text-[9px] text-[#555] mt-1">START: inicia escucha (recomendado: Ctrl+Shift+Space)</span>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Tecla PTT (STOP)</label>
              <input
                type="text"
                value={pttStopHotkey}
                onChange={(e) => setPttStopHotkey(e.target.value)}
                className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1.5 text-[13px] text-white focus:border-[#8a2be2] focus:outline-none"
              />
              <span className="text-[9px] text-[#555] mt-1">STOP: envía y recibe respuesta</span>
            </div>
            <label className="flex items-center gap-2 text-[12px] text-[#ccc] cursor-pointer">
              <input
                type="checkbox"
                checked={swearyMessages}
                onChange={(e) => setSwearyMessages(e.target.checked)}
                className="accent-[#8a2be2]"
              />
              Lenguaje de paddock (juramentos opcionales)
            </label>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Perfil de personalidad</label>
              <select
                value={personalityProfileId}
                onChange={(e) => setPersonalityProfileId(e.target.value as AppConfig["personalityProfileId"])}
                className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1.5 text-[13px] text-white focus:border-[#8a2be2] focus:outline-none"
              >
                <option value="formal">Formal</option>
                <option value="standard">Estándar</option>
                <option value="aggressive">Agresivo</option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Verbosidad del ingeniero</label>
              <select
                value={verbosityLevel}
                onChange={(e) => setVerbosityLevel(e.target.value as AppConfig["verbosityLevel"])}
                className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1.5 text-[13px] text-white focus:border-[#8a2be2] focus:outline-none"
              >
                <option value="silent">Silencioso (solo crítico + spotter)</option>
                <option value="normal">Normal</option>
                <option value="detailed">Detallado</option>
              </select>
            </div>
            <div className="grid grid-cols-1 gap-2">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Voz TTS ingeniero</label>
                <input
                  type="text"
                  value={ttsVoiceEngineer}
                  onChange={(e) => setTtsVoiceEngineer(e.target.value)}
                  className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1.5 text-[13px] text-white focus:border-[#8a2be2] focus:outline-none"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Voz TTS spotter</label>
                <input
                  type="text"
                  value={ttsVoiceSpotter}
                  onChange={(e) => setTtsVoiceSpotter(e.target.value)}
                  className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1.5 text-[13px] text-white focus:border-[#8a2be2] focus:outline-none"
                />
              </div>
            </div>
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
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-[#aaa] uppercase tracking-wider">TTS volume boost</label>
                <input type="number" step="0.1" min="0.5" max="1" value={ttsVolumeBoost}
                  onChange={(e) => setTtsVolumeBoost(Number(e.target.value))}
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
            <label className="flex items-center gap-2 text-[12px] text-[#ccc] cursor-pointer">
              <input
                type="checkbox"
                checked={spotterExcludeStopped}
                onChange={(e) => setSpotterExcludeStopped(e.target.checked)}
                className="accent-[#8a2be2]"
              />
              Ignorar coches parados o en boxes
            </label>
            <label className="flex items-center gap-2 text-[12px] text-[#ccc] cursor-pointer">
              <input
                type="checkbox"
                checked={brakingZonesMute}
                onChange={(e) => setBrakingZonesMute(e.target.checked)}
                className="accent-[#8a2be2]"
              />
              Silenciar TTS del ingeniero al frenar (zonas de frenada)
            </label>
            <label className="flex items-center gap-2 text-[12px] text-[#ccc] cursor-pointer">
              <input
                type="checkbox"
                checked={mqttEnabled}
                onChange={(e) => setMqttEnabled(e.target.checked)}
                className="accent-[#8a2be2]"
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
                  className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-[12px] text-white"
                />
                <input
                  type="number"
                  value={mqttPort}
                  onChange={(e) => setMqttPort(Number(e.target.value))}
                  placeholder="Puerto"
                  className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-[12px] text-white"
                />
              </div>
            )}
            <div className="mt-2 p-2 bg-[#1a1a1a] border border-[#222] rounded text-[10px] flex flex-col gap-1.5">
              <div className="text-[#666] uppercase tracking-wider mb-1">Configuración del Backend:</div>
              <div className="flex justify-between">
                <span className="text-[#888]">Motor LLM:</span>
                <span className="text-[#aaa]">CrofAI</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#888]">Modelo:</span>
                <span className={connectivity.backendHealth?.llm ? "text-[#4f4]" : "text-[#f44]"}>
                  {connectivity.backendHealth?.llm ? "deepseek-v4-flash" : "No configurado"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#888]">TTS:</span>
                <span className="text-[#aaa]">Piper (lessac-medium)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#888]">Estado:</span>
                <span className={connectivity.backendHealth?.llm ? "text-[#4f4]" : "text-[#f44]"}>
                  {connectivity.backendHealth?.llm ? "Conectado" : "Desconectado"}
                </span>
              </div>
            </div>
            <div className="mt-2 p-2 bg-[#1a1a1a] border border-[#222] rounded text-[11px] text-[#666]">
              {pttHotkey.trim().toLowerCase() === pttStopHotkey.trim().toLowerCase()
                ? "Modo toggle: pulsa y suelta la tecla PTT para transmitir."
                : "Pulsa START para hablar, pulsa STOP para enviar y recibir respuesta."}
            </div>
            <button
              onClick={handleSave}
              className="mt-2 bg-[#333] hover:bg-[#444] text-white text-[11px] font-bold uppercase tracking-wider px-3 py-1.5 rounded transition-none"
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