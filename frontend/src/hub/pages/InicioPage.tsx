import { useAppStore } from "../../store/config";

import { HubCard } from "../components/HubCard";

import { PowerToggle } from "../components/PowerToggle";

import { useServicePower } from "../hooks/useServicePower";



function formatSpeedKmh(speedKmh: number): string {
  return Number.isFinite(speedKmh) && speedKmh > 0 ? `${Math.round(speedKmh)} km/h` : "—";
}

function formatGap(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds === 0) return "—";
  return seconds > 0 ? `+${seconds.toFixed(1)}s` : `${seconds.toFixed(1)}s`;
}

export function InicioPage() {

  const latestAdvice = useAppStore((s) => s.radio.latestAdvice);
  const currentTokens = useAppStore((s) => s.radio.currentTokens);
  const latestAlert = useAppStore((s) => s.radio.latestAlert);
  const mode = useAppStore((s) => s.radio.mode);
  const wsStatus = useAppStore((s) => s.connectivity.wsStatus);
  const backendHealth = useAppStore((s) => s.connectivity.backendHealth);
  const speed = useAppStore((s) => s.telemetry.speed ?? 0);
  const gear = useAppStore((s) => s.telemetry.gear ?? 0);
  const fuel = useAppStore((s) => s.telemetry.fuel ?? 0);
  const lap = useAppStore((s) => s.telemetry.lap ?? 0);
  const position = useAppStore((s) => s.telemetry.position ?? 0);
  const gapAhead = useAppStore((s) => s.telemetry.gaps?.ahead ?? 0);
  const gapBehind = useAppStore((s) => s.telemetry.gaps?.behind ?? 0);
  const telemetrySource =
    backendHealth?.shared_memory ? "LMU (memoria compartida)" : "Esperando sesión";
  const gearLabel = gear === 0 ? "—" : gear === -1 ? "R" : String(gear);
  const telemetryLive = wsStatus === "CONNECTED" && speed > 1;

  const {

    spotterEnabled,

    engineerEnabled,

    wsConnected,
    syncError,
    toggleSpotter,
    toggleEngineer,
  } = useServicePower();



  return (

    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

      <HubCard title="Servicios de radio" className="xl:col-span-2">

        <p className="text-sm text-a1-text-muted mb-4">

          Enciende solo lo que necesites en pista. El PTT sigue disponible con el ingeniero apagado.

        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">

          <PowerToggle

            label="Ingeniero"

            description="Comentarios proactivos, estrategia y alertas del jefe de pista."

            enabled={engineerEnabled}

            disabled={!wsConnected}

            onToggle={toggleEngineer}

          />

          <PowerToggle

            label="Spotter"

            description="Avisos de tráfico, adelantamientos y proximidad en pista."

            enabled={spotterEnabled}

            disabled={!wsConnected}

            onToggle={toggleSpotter}

          />

        </div>

        {!wsConnected ? (
          <p className="mt-3 text-xs text-a1-text-muted">
            Conectando al backend… (el arranque puede tardar hasta 30 s la primera vez)
          </p>
        ) : null}
        {syncError ? (
          <p className="mt-3 text-xs text-a1-accent-bright">{syncError}</p>
        ) : null}
      </HubCard>





      <HubCard title="Telemetría en vivo">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[10px] uppercase tracking-widest text-a1-text-muted">
            {telemetrySource}
          </span>
          <span
            className={`text-[10px] uppercase tracking-widest ${
              telemetryLive ? "text-emerald-400" : "text-a1-text-muted"
            }`}
          >
            {telemetryLive ? "En pista" : wsStatus === "CONNECTED" ? "Conectado" : "Sin enlace"}
          </span>
        </div>
        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-a1-text-muted">Velocidad</dt>
            <dd className="text-lg font-semibold text-a1-text">{formatSpeedKmh(speed)}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-a1-text-muted">Marcha</dt>
            <dd className="text-lg font-semibold text-a1-text">{gearLabel}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-a1-text-muted">Vuelta</dt>
            <dd className="text-lg font-semibold text-a1-text">{lap > 0 ? lap : "—"}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-a1-text-muted">Posición</dt>
            <dd className="text-lg font-semibold text-a1-text">P{position || "—"}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-a1-text-muted">Combustible</dt>
            <dd className="text-lg font-semibold text-a1-text">{fuel > 0 ? `${fuel.toFixed(1)} L` : "—"}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-a1-text-muted">Delante</dt>
            <dd className="text-lg font-semibold text-a1-text">{formatGap(gapAhead)}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-a1-text-muted">Detrás</dt>
            <dd className="text-lg font-semibold text-a1-text">{formatGap(gapBehind)}</dd>
          </div>
        </dl>
        {!telemetryLive && wsStatus === "CONNECTED" ? (
          <p className="mt-3 text-xs text-a1-text-muted">
            Entra en pista con LMU en ejecución. Si sigue en cero, revisa que la sesión no esté en menú.
          </p>
        ) : null}
      </HubCard>

      <HubCard title="Radio">

        <div className="text-[10px] uppercase tracking-widest text-a1-accent mb-2">{mode.replace("_", " ")}</div>

        <p className="text-sm text-a1-text leading-relaxed">
          {mode === "THINKING_LLM"
            ? (currentTokens || "Pensando…")
            : (latestAdvice || "Radio silenciosa. Usa PTT para hablar con el ingeniero.")}
        </p>

        {latestAlert ? (

          <p className="mt-3 text-sm text-a1-accent-bright">Spotter: {latestAlert}</p>

        ) : null}

      </HubCard>



      <HubCard title="Overlay in-game" className="xl:col-span-2">

        <p className="text-sm text-a1-text-muted leading-relaxed">

          El overlay aparece al mantener PTT (<span className="text-a1-accent">Escuchando</span>)
          y cuando suena radio — ingeniero o spotter (<span className="text-a1-accent">Hablando</span>).
          Fuera de eso permanece oculto. Requiere LMU en borderless o ventana y spotter/ingeniero encendidos.

        </p>

      </HubCard>

    </div>

  );

}


