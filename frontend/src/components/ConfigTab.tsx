import React, { useState, useEffect, useRef } from "react";
import { useAppStore, type InterruptThreshold } from "../store/config";
import { getHealth } from "../services/api";

type TabName = "conexion" | "audio" | "voz" | "spotter" | "avanzado";

/**
 * Panel de configuración unificado con 5 pestañas:
 * - Conexión: IP del servidor, puerto, test de conexión
 * - Audio: micrófono, sensibilidad, VAD, vúmetro
 * - Voz: hotkey PTT, palabra de activación
 * - Spotter: parámetros del spotter automático
 * - Avanzado: TTS, templates, driver name
 */
export const ConfigTab: React.FC = () => {
  const { config, connectivity, updateConfig, setMicLevel } = useAppStore();
  const [activeTab, setActiveTab] = useState<TabName>("conexion");

  // Estados locales para los campos del formulario
  const [vllmIP, setVllmIP] = useState(config.vllmIP);
  const [serverPort, setServerPort] = useState(config.serverPort ?? 8008);
  const [micDevice, setMicDevice] = useState(config.micDevice);
  const [sensitivity, setSensitivity] = useState(config.sensitivity ?? 50);
  const [pttHotkey, setPttHotkey] = useState(config.pttHotkey ?? "P");
  const [pttStopHotkey, setPttStopHotkey] = useState(config.pttStopHotkey ?? "P");
  // Audio tab
  const [chiefVoice, setChiefVoice] = useState(config.chiefVoice);
  const [spotterVoice, setSpotterVoice] = useState(config.spotterVoice);
  const [chiefRate, setChiefRate] = useState(config.chiefRate);
  const [spotterRate, setSpotterRate] = useState(config.spotterRate);
  const [chiefPitch, setChiefPitch] = useState(config.chiefPitch);
  const [spotterPitch, setSpotterPitch] = useState(config.spotterPitch);
  const [spotterVolumeBoost, setSpotterVolumeBoost] = useState(config.spotterVolumeBoost);
  const [audioOutputDevice, setAudioOutputDevice] = useState(config.audioOutputDevice);
  const [interruptThreshold, setInterruptThreshold] = useState<InterruptThreshold>(config.interruptThreshold);
  const [autoVerbosityEnabled, setAutoVerbosityEnabled] = useState(config.autoVerbosityEnabled);
  // Spotter tab
  const [spotterGapForClear, setSpotterGapForClear] = useState(config.spotterGapForClear);
  const [spotterOverlapDelay, setSpotterOverlapDelay] = useState(config.spotterOverlapDelay);
  const [spotterClearDelay, setSpotterClearDelay] = useState(config.spotterClearDelay);
  const [spotterRepeatFrequency, setSpotterRepeatFrequency] = useState(config.spotterRepeatFrequency);
  const [spotterMinSpeed, setSpotterMinSpeed] = useState(config.spotterMinSpeed);
  const [spotterMaxClosingSpeed, setSpotterMaxClosingSpeed] = useState(config.spotterMaxClosingSpeed);
  const [spotterEnable3Wide, setSpotterEnable3Wide] = useState(config.spotterEnable3Wide);
  // Advanced tab
  const [driverName, setDriverName] = useState(config.driverName);
  const [workerUrl, setWorkerUrl] = useState(config.workerUrl);
  const [enableTemplates, setEnableTemplates] = useState(config.enableTemplates);

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

    updateConfig({
      vllmIP: vllmIP.trim(),
      serverPort: portNum,
      micDevice,
      sensitivity,
      pttHotkey: pttHotkey.trim(),
      pttStopHotkey: pttStopHotkey.trim(),
      // Audio
      chiefVoice,
      spotterVoice,
      chiefRate,
      spotterRate,
      chiefPitch,
      spotterPitch,
      spotterVolumeBoost,
      audioOutputDevice,
      interruptThreshold,
      autoVerbosityEnabled,
      // Spotter
      spotterGapForClear,
      spotterOverlapDelay,
      spotterClearDelay,
      spotterRepeatFrequency,
      spotterMinSpeed,
      spotterMaxClosingSpeed,
      spotterEnable3Wide,
      // Advanced
      driverName,
      workerUrl: workerUrl.trim(),
      enableTemplates,
    });
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
        {(["conexion", "audio", "voz", "spotter", "avanzado"] as TabName[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-2 text-[11px] font-bold uppercase tracking-wider transition-none ${
              activeTab === tab
                ? "text-[#8a2be2] border-b-2 border-[#8a2be2]"
                : "text-[#555] hover:text-[#888]"
            }`}
          >
            {tab === "conexion" ? "Conexión" : tab === "audio" ? "Audio" : tab === "voz" ? "Voz" : tab === "spotter" ? "Spotter" : "Avanzado"}
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
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Salida de Audio</label>
              <input
                type="text"
                value={audioOutputDevice}
                onChange={(e) => setAudioOutputDevice(e.target.value)}
                placeholder="default"
                className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1.5 text-[13px] text-white focus:border-[#8a2be2] focus:outline-none"
              />
              <span className="text-[9px] text-[#555]">Vacío = dispositivo por defecto</span>
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

            <div className="border-t border-[#222] my-1" />

            {/* Voz del Jefe */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Voz del Jefe de Equipo</label>
              <input
                type="text"
                value={chiefVoice}
                onChange={(e) => setChiefVoice(e.target.value)}
                placeholder="es-ES-AlvaroNeural"
                className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1.5 text-[13px] text-white focus:border-[#8a2be2] focus:outline-none"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Voz del Spotter</label>
              <input
                type="text"
                value={spotterVoice}
                onChange={(e) => setSpotterVoice(e.target.value)}
                placeholder="es-MX-JorgeNeural"
                className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1.5 text-[13px] text-white focus:border-[#8a2be2] focus:outline-none"
              />
            </div>

            {/* Ajustes TTS */}
            <div className="flex gap-2">
              <div className="flex flex-col gap-1 flex-1">
                <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Ritmo Jefe ({chiefRate})</label>
                <input
                  type="range"
                  min="-50"
                  max="50"
                  value={chiefRate}
                  onChange={(e) => setChiefRate(Number(e.target.value))}
                  className="w-full accent-[#8a2be2]"
                />
              </div>
              <div className="flex flex-col gap-1 flex-1">
                <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Ritmo Spotter ({spotterRate})</label>
                <input
                  type="range"
                  min="-50"
                  max="50"
                  value={spotterRate}
                  onChange={(e) => setSpotterRate(Number(e.target.value))}
                  className="w-full accent-[#8a2be2]"
                />
              </div>
            </div>

            <div className="flex gap-2">
              <div className="flex flex-col gap-1 flex-1">
                <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Tono Jefe ({chiefPitch})</label>
                <input
                  type="range"
                  min="-50"
                  max="50"
                  value={chiefPitch}
                  onChange={(e) => setChiefPitch(Number(e.target.value))}
                  className="w-full accent-[#8a2be2]"
                />
              </div>
              <div className="flex flex-col gap-1 flex-1">
                <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Tono Spotter ({spotterPitch})</label>
                <input
                  type="range"
                  min="-50"
                  max="50"
                  value={spotterPitch}
                  onChange={(e) => setSpotterPitch(Number(e.target.value))}
                  className="w-full accent-[#8a2be2]"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Boost Volumen Spotter ({spotterVolumeBoost}%)</label>
              <input
                type="range"
                min="0"
                max="100"
                value={spotterVolumeBoost}
                onChange={(e) => setSpotterVolumeBoost(Number(e.target.value))}
                className="w-full accent-[#8a2be2]"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Umbral de Interrupción</label>
              <select
                value={interruptThreshold}
                onChange={(e) => setInterruptThreshold(e.target.value as InterruptThreshold)}
                className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1.5 text-[12px] text-white focus:border-[#8a2be2] focus:outline-none"
              >
                <option value="NEVER">Nunca interrumpir</option>
                <option value="SPOTTER">Solo spotter</option>
                <option value="CRITICAL">Crítico y spotter</option>
                <option value="IMPORTANT">Todo importante</option>
              </select>
            </div>

            <div className="flex items-center justify-between">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Verbosidad Automática</label>
              <button
                onClick={() => setAutoVerbosityEnabled(!autoVerbosityEnabled)}
                className={`w-10 h-5 rounded-full transition-none flex items-center ${
                  autoVerbosityEnabled ? "bg-[#8a2be2]" : "bg-[#333]"
                }`}
              >
                <div
                  className={`w-4 h-4 bg-white rounded-full transition-none ${
                    autoVerbosityEnabled ? "ml-[20px]" : "ml-[2px]"
                  }`}
                />
              </button>
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
            <div className="flex items-center justify-between">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Palabra de Activación</label>
              <input
                type="text"
                value={config.wakeWord}
                readOnly
                className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-[12px] text-[#888] w-28 text-center"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Wake Word Activada</label>
              <button
                onClick={() => updateConfig({ wakeWordEnabled: !config.wakeWordEnabled })}
                className={`w-10 h-5 rounded-full transition-none flex items-center ${
                  config.wakeWordEnabled ? "bg-[#8a2be2]" : "bg-[#333]"
                }`}
              >
                <div
                  className={`w-4 h-4 bg-white rounded-full transition-none ${
                    config.wakeWordEnabled ? "ml-[20px]" : "ml-[2px]"
                  }`}
                />
              </button>
            </div>
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
                <span className="text-[#aaa]">Edge TTS ({chiefVoice})</span>
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

        {/* TAB: SPOTTER */}
        {activeTab === "spotter" && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Distancia para "Clear" ({spotterGapForClear}m)</label>
              <input
                type="range"
                min="1.0"
                max="20.0"
                step="0.5"
                value={spotterGapForClear}
                onChange={(e) => setSpotterGapForClear(Number(e.target.value))}
                className="w-full accent-[#8a2be2]"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Delay Overlap ({spotterOverlapDelay}ms)</label>
              <input
                type="range"
                min="50"
                max="1000"
                step="50"
                value={spotterOverlapDelay}
                onChange={(e) => setSpotterOverlapDelay(Number(e.target.value))}
                className="w-full accent-[#8a2be2]"
              />
              <span className="text-[9px] text-[#555]">Ms antes de decir "coche a la izquierda"</span>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Delay "Clear" ({spotterClearDelay}ms)</label>
              <input
                type="range"
                min="50"
                max="2000"
                step="50"
                value={spotterClearDelay}
                onChange={(e) => setSpotterClearDelay(Number(e.target.value))}
                className="w-full accent-[#8a2be2]"
              />
              <span className="text-[9px] text-[#555]">Ms antes de decir "clear"</span>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Frecuencia de Repetición ({spotterRepeatFrequency}s)</label>
              <input
                type="range"
                min="0.5"
                max="10.0"
                step="0.5"
                value={spotterRepeatFrequency}
                onChange={(e) => setSpotterRepeatFrequency(Number(e.target.value))}
                className="w-full accent-[#8a2be2]"
              />
              <span className="text-[9px] text-[#555]">Segundos entre "sigue ahí"</span>
            </div>
            <div className="flex gap-2">
              <div className="flex flex-col gap-1 flex-1">
                <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Vel. Mínima ({spotterMinSpeed} m/s)</label>
                <input
                  type="range"
                  min="0"
                  max="30"
                  step="0.5"
                  value={spotterMinSpeed}
                  onChange={(e) => setSpotterMinSpeed(Number(e.target.value))}
                  className="w-full accent-[#8a2be2]"
                />
              </div>
              <div className="flex flex-col gap-1 flex-1">
                <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Cierre Máx ({spotterMaxClosingSpeed} m/s)</label>
                <input
                  type="range"
                  min="5.0"
                  max="60.0"
                  step="1.0"
                  value={spotterMaxClosingSpeed}
                  onChange={(e) => setSpotterMaxClosingSpeed(Number(e.target.value))}
                  className="w-full accent-[#8a2be2]"
                />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Detectar 3 Anchos</label>
              <button
                onClick={() => setSpotterEnable3Wide(!spotterEnable3Wide)}
                className={`w-10 h-5 rounded-full transition-none flex items-center ${
                  spotterEnable3Wide ? "bg-[#8a2be2]" : "bg-[#333]"
                }`}
              >
                <div
                  className={`w-4 h-4 bg-white rounded-full transition-none ${
                    spotterEnable3Wide ? "ml-[20px]" : "ml-[2px]"
                  }`}
                />
              </button>
            </div>
            <button
              onClick={handleSave}
              className="mt-2 bg-[#333] hover:bg-[#444] text-white text-[11px] font-bold uppercase tracking-wider px-3 py-1.5 rounded transition-none"
            >
              {saveStatus || "Guardar"}
            </button>
          </div>
        )}

        {/* TAB: AVANZADO */}
        {activeTab === "avanzado" && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Nombre del Piloto</label>
              <input
                type="text"
                value={driverName}
                onChange={(e) => setDriverName(e.target.value)}
                placeholder="Ej: Carlos"
                className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1.5 text-[13px] text-white focus:border-[#8a2be2] focus:outline-none"
              />
              <span className="text-[9px] text-[#555]">Se usa en plantillas &#123;driver_name&#125;</span>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">URL del Worker Proxy</label>
              <input
                type="text"
                value={workerUrl}
                onChange={(e) => setWorkerUrl(e.target.value)}
                placeholder="https://vantare-llm-proxy.workers.dev"
                className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1.5 text-[13px] text-white focus:border-[#8a2be2] focus:outline-none"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="text-[10px] text-[#aaa] uppercase tracking-wider">Plantillas Habilitadas</label>
              <button
                onClick={() => setEnableTemplates(!enableTemplates)}
                className={`w-10 h-5 rounded-full transition-none flex items-center ${
                  enableTemplates ? "bg-[#8a2be2]" : "bg-[#333]"
                }`}
              >
                <div
                  className={`w-4 h-4 bg-white rounded-full transition-none ${
                    enableTemplates ? "ml-[20px]" : "ml-[2px]"
                  }`}
                />
              </button>
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