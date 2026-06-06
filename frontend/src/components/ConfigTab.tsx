import React, { useState, useEffect, useRef } from "react";
import { useAppStore, AppConfig } from "../store/config";
import { getHealth, listProfiles, loadProfile, saveProfile, deleteProfile } from "../services/api";

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
  const [pttHotkey, setPttHotkey] = useState(config.pttHotkey ?? "P");
  const [pttStopHotkey, setPttStopHotkey] = useState(config.pttStopHotkey ?? "P");
  const [swearyMessages, setSwearyMessages] = useState(config.swearyMessages ?? false);
  const [spotterOffQualifying, setSpotterOffQualifying] = useState(config.spotterOffQualifying ?? true);
  const [spotterExcludeStopped, setSpotterExcludeStopped] = useState(config.spotterExcludeStopped ?? true);
  const [mqttEnabled, setMqttEnabled] = useState(config.mqttEnabled ?? false);
  const [mqttBroker, setMqttBroker] = useState(config.mqttBroker ?? "localhost");
  const [mqttPort, setMqttPort] = useState(config.mqttPort ?? 1883);

  // Estados de test y dispositivos
  const [testStatus, setTestStatus] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [micDevices, setMicDevices] = useState<MediaDeviceInfo[]>([]);
  const [localLevel, setLocalLevel] = useState(0);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);

  // Leer micLevel del store
  useAppStore((state) => state.radio.micLevel);

  // 1. Enumerar dispositivos de audio
  useEffect(() => {
    const getDevices = async () => {
      try {
        await navigator.mediaDevices.getUserMedia({ audio: true }).catch(() => {});
        const devices = await navigator.mediaDevices.enumerateDevices();
        setMicDevices(devices.filter((d) => d.kind === "audioinput"));
      } catch (e) {
        console.warn("Fallo al enumerar dispositivos:", e);
      }
    };
    getDevices();
  }, []);

  const refreshProfiles = async () => {
    const names = await listProfiles();
    setProfiles(names);
  };

  useEffect(() => {
    if (activeTab === "conexion") {
      refreshProfiles();
    }
  }, [activeTab]);

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
  });

  const applyLoadedConfig = (loaded: Record<string, unknown>) => {
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
  };

  const handleLoadProfile = async () => {
    if (!selectedProfile) return;
    const loaded = await loadProfile(selectedProfile);
    if (!loaded) {
      setProfileStatus("❌ No se pudo cargar el perfil");
      setTimeout(() => setProfileStatus(null), 3000);
      return;
    }
    applyLoadedConfig(loaded);
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

    updateConfig(buildConfigPayload());
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
              <span className="text-[9px] text-[#555] mt-1">START: inicia escucha</span>
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