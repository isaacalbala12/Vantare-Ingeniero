import { useAppStore } from "../../store/config";

import { HubCard } from "../components/HubCard";

import { PowerToggle } from "../components/PowerToggle";

import { useServicePower } from "../hooks/useServicePower";



export function InicioPage() {

  const latestAdvice = useAppStore((s) => s.radio.latestAdvice);
  const currentTokens = useAppStore((s) => s.radio.currentTokens);
  const latestAlert = useAppStore((s) => s.radio.latestAlert);
  const mode = useAppStore((s) => s.radio.mode);

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

          El overlay aparece solo durante la radio: un chip arriba a la izquierda al mantener PTT
          (<span className="text-a1-accent">Escuchando</span>) y la tarjeta del ingeniero cuando habla.
          Fuera de eso permanece oculto. Requiere LMU en borderless o ventana.

        </p>

      </HubCard>

    </div>

  );

}


