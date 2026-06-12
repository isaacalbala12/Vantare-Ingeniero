import { useAppStore } from "../../store/config";
import { t } from "../../i18n/strings";

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

  const uiLanguage = useAppStore((s) => s.config.uiLanguage);
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
    backendHealth?.shared_memory ? t(uiLanguage, "telemetrySourceLmu") : t(uiLanguage, "telemetrySourceWaiting");
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

      <HubCard title={t(uiLanguage, "radioServices")} className="xl:col-span-2">

        <p className="text-sm text-a1-text-muted mb-4">
          {t(uiLanguage, "radioDescription")}
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">

          <PowerToggle

            label={t(uiLanguage, "engineerLabel")}

            description={t(uiLanguage, "engineerDesc")}

            enabled={engineerEnabled}

            disabled={!wsConnected}

            onToggle={toggleEngineer}

          />

          <PowerToggle

            label={t(uiLanguage, "spotterLabel")}

            description={t(uiLanguage, "spotterDesc")}

            enabled={spotterEnabled}

            disabled={!wsConnected}

            onToggle={toggleSpotter}

          />

        </div>

        {!wsConnected ? (
          <p className="mt-3 text-xs text-a1-text-muted">
            {t(uiLanguage, "connecting")}
          </p>
        ) : null}
        {syncError ? (
          <p className="mt-3 text-xs text-a1-accent-bright">{syncError}</p>
        ) : null}
      </HubCard>





      <HubCard title={t(uiLanguage, "liveTelemetry")}>
        <div className="flex items-center justify-between mb-3">
          <span className="text-[10px] uppercase tracking-widest text-a1-text-muted">
            {telemetrySource}
          </span>
          <span
            className={`text-[10px] uppercase tracking-widest ${
              telemetryLive ? "text-emerald-400" : "text-a1-text-muted"
            }`}
          >
            {telemetryLive ? t(uiLanguage, "onTrack") : wsStatus === "CONNECTED" ? t(uiLanguage, "connected") : t(uiLanguage, "noLink")}
          </span>
        </div>
        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-a1-text-muted">{t(uiLanguage, "speed")}</dt>
            <dd className="text-lg font-semibold text-a1-text">{formatSpeedKmh(speed)}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-a1-text-muted">{t(uiLanguage, "gear")}</dt>
            <dd className="text-lg font-semibold text-a1-text">{gearLabel}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-a1-text-muted">{t(uiLanguage, "lap")}</dt>
            <dd className="text-lg font-semibold text-a1-text">{lap > 0 ? lap : "—"}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-a1-text-muted">{t(uiLanguage, "position")}</dt>
            <dd className="text-lg font-semibold text-a1-text">P{position || "—"}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-a1-text-muted">{t(uiLanguage, "fuel")}</dt>
            <dd className="text-lg font-semibold text-a1-text">{fuel > 0 ? `${fuel.toFixed(1)} L` : "—"}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-a1-text-muted">{t(uiLanguage, "ahead")}</dt>
            <dd className="text-lg font-semibold text-a1-text">{formatGap(gapAhead)}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-widest text-a1-text-muted">{t(uiLanguage, "behind")}</dt>
            <dd className="text-lg font-semibold text-a1-text">{formatGap(gapBehind)}</dd>
          </div>
        </dl>
        {!telemetryLive && wsStatus === "CONNECTED" ? (
          <p className="mt-3 text-xs text-a1-text-muted">
            {t(uiLanguage, "enterTrack")}
          </p>
        ) : null}
      </HubCard>

      <HubCard title={t(uiLanguage, "radio")}>

        <div className="text-[10px] uppercase tracking-widest text-a1-accent mb-2">{mode === "IDLE" ? t(uiLanguage, "idle") : mode.replace("_", " ")}</div>

        <p className="text-sm text-a1-text leading-relaxed">
          {mode === "THINKING_LLM"
            ? (currentTokens || t(uiLanguage, "thinking"))
            : (latestAdvice || t(uiLanguage, "radioSilent"))}
        </p>

        {latestAlert ? (

          <p className="mt-3 text-sm text-a1-accent-bright">{t(uiLanguage, "spotterAlert", { text: latestAlert })}</p>

        ) : null}

      </HubCard>



      <HubCard title={t(uiLanguage, "inGameOverlay")} className="xl:col-span-2">

        <p className="text-sm text-a1-text-muted leading-relaxed">
          {t(uiLanguage, "overlayDesc")}
        </p>

      </HubCard>

    </div>

  );

}


