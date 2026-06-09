/** Matriz contrato audio — espejo de backend/tests/fixtures/audio_trigger_matrix.py */

export type WsEvent = "alert" | "llm_pending+advice_*" | "commentary_end" | "strategy_update" | "none";
export type TtsPriorityExpect = "IMMEDIATE" | "NORMAL" | "N/A";

export interface AudioContractRow {
  id: string;
  source: string;
  category: string;
  sampleMessage: string;
  audioPriority: string;
  severity: string;
  wsEvent: WsEvent;
  expectVoice: boolean;
  expectTtsPriority: TtsPriorityExpect;
}

export const SPOTTER_AUDIO_ROWS: AudioContractRow[] = [
  {
    id: "spotter:proximity_enter",
    source: "SpotterService",
    category: "proximity",
    sampleMessage: "Coche a la derecha",
    audioPriority: "2",
    severity: "INFO",
    wsEvent: "alert",
    expectVoice: true,
    expectTtsPriority: "IMMEDIATE",
  },
  {
    id: "spotter:proximity_clear",
    source: "SpotterService",
    category: "proximity",
    sampleMessage: "Despejado derecha",
    audioPriority: "2",
    severity: "INFO",
    wsEvent: "alert",
    expectVoice: true,
    expectTtsPriority: "IMMEDIATE",
  },
  {
    id: "spotter:three_wide",
    source: "SpotterService",
    category: "proximity",
    sampleMessage: "Tres coches de ancho",
    audioPriority: "3",
    severity: "WARNING",
    wsEvent: "alert",
    expectVoice: true,
    expectTtsPriority: "IMMEDIATE",
  },
  {
    id: "spotter:limiter_enter",
    source: "SpotterService",
    category: "limiter",
    sampleMessage: "Pit limiter no activado al entrar en boxes.",
    audioPriority: "4",
    severity: "CRITICAL",
    wsEvent: "alert",
    expectVoice: true,
    expectTtsPriority: "IMMEDIATE",
  },
  {
    id: "spotter:fuel_critical",
    source: "SpotterService",
    category: "fuel",
    sampleMessage: "¡Combustible crítico! Menos de 1 vuelta restante.",
    audioPriority: "4",
    severity: "CRITICAL",
    wsEvent: "alert",
    expectVoice: true,
    expectTtsPriority: "IMMEDIATE",
  },
  {
    id: "spotter:safety_car",
    source: "SpotterService",
    category: "safety_car",
    sampleMessage: "Safety car desplegado / FCY activo en pista.",
    audioPriority: "4",
    severity: "CRITICAL",
    wsEvent: "alert",
    expectVoice: true,
    expectTtsPriority: "IMMEDIATE",
  },
  {
    id: "spotter:last_lap",
    source: "SpotterService",
    category: "session",
    sampleMessage: "¡Última vuelta de la carrera!",
    audioPriority: "2",
    severity: "INFO",
    wsEvent: "alert",
    expectVoice: true,
    expectTtsPriority: "IMMEDIATE",
  },
  {
    id: "spotter:damage",
    source: "SpotterService",
    category: "damage",
    sampleMessage: "Daños detectados en el monoplaza.",
    audioPriority: "3",
    severity: "WARNING",
    wsEvent: "alert",
    expectVoice: true,
    expectTtsPriority: "IMMEDIATE",
  },
  {
    id: "spotter:gaps",
    source: "SpotterService",
    category: "gaps",
    sampleMessage: "Coche a 0.3s delante",
    audioPriority: "1",
    severity: "INFO",
    wsEvent: "alert",
    expectVoice: false,
    expectTtsPriority: "N/A",
  },
  {
    id: "spotter:ack",
    source: "SpotterService",
    category: "spotter",
    sampleMessage: "Spotter activado.",
    audioPriority: "1",
    severity: "INFO",
    wsEvent: "alert",
    expectVoice: false,
    expectTtsPriority: "N/A",
  },
  {
    id: "engine:pearl",
    source: "IntelligenceEngine",
    category: "pearl",
    sampleMessage: "Buen trabajo piloto.",
    audioPriority: "2",
    severity: "INFO",
    wsEvent: "alert",
    expectVoice: true,
    expectTtsPriority: "NORMAL",
  },
  {
    id: "pilot:advice",
    source: "PilotQuestion",
    category: "advice",
    sampleMessage: "Tu combustible aguanta unas ocho vueltas más.",
    audioPriority: "HIGH",
    severity: "INFO",
    wsEvent: "llm_pending+advice_*",
    expectVoice: true,
    expectTtsPriority: "NORMAL",
  },
];

/** Triggers ALERT_ONLY — texto fijo vía alert WS */
export const ALERT_ONLY_TRIGGER_ROWS: AudioContractRow[] = [
  {
    id: "trigger:BrakeWearCriticalTrigger",
    source: "IntelligenceEngine",
    category: "strategy",
    sampleMessage: "¡AVISO DE FRENOS! Desgaste superior al 80% detectado.",
    audioPriority: "CRITICAL",
    severity: "CRITICAL",
    wsEvent: "alert",
    expectVoice: true,
    expectTtsPriority: "IMMEDIATE",
  },
  {
    id: "trigger:MulticlassWarningTrigger",
    source: "IntelligenceEngine",
    category: "strategy",
    sampleMessage: "Atención multiclase en pista.",
    audioPriority: "HIGH",
    severity: "HIGH",
    wsEvent: "alert",
    expectVoice: true,
    expectTtsPriority: "IMMEDIATE",
  },
  {
    id: "trigger:DriverSwapTrigger",
    source: "IntelligenceEngine",
    category: "strategy",
    sampleMessage: "Cambio de piloto detectado.",
    audioPriority: "HIGH",
    severity: "HIGH",
    wsEvent: "alert",
    expectVoice: true,
    expectTtsPriority: "IMMEDIATE",
  },
  {
    id: "trigger:PenaltyMonitorTrigger",
    source: "IntelligenceEngine",
    category: "strategy",
    sampleMessage: "Penalización asignada.",
    audioPriority: "HIGH",
    severity: "HIGH",
    wsEvent: "alert",
    expectVoice: true,
    expectTtsPriority: "IMMEDIATE",
  },
];

/** Triggers LLM_REQUIRED — voz vía advice_end NORMAL */
export const LLM_TRIGGER_SAMPLE_ROWS: AudioContractRow[] = [
  {
    id: "trigger:FuelCriticalTrigger",
    source: "IntelligenceEngine",
    category: "advice",
    sampleMessage: "Planifica parada pronto, te quedan pocas vueltas de fuel.",
    audioPriority: "CRITICAL",
    severity: "CRITICAL",
    wsEvent: "llm_pending+advice_*",
    expectVoice: true,
    expectTtsPriority: "NORMAL",
  },
  {
    id: "trigger:TyreDegAccelTrigger",
    source: "IntelligenceEngine",
    category: "advice",
    sampleMessage: "Desgaste de neumáticos elevado, considera conservar.",
    audioPriority: "HIGH",
    severity: "HIGH",
    wsEvent: "llm_pending+advice_*",
    expectVoice: true,
    expectTtsPriority: "NORMAL",
  },
  {
    id: "trigger:PitWindowOpenedTrigger",
    source: "IntelligenceEngine",
    category: "advice",
    sampleMessage: "Ventana de paradas abierta, analiza estrategia.",
    audioPriority: "HIGH",
    severity: "HIGH",
    wsEvent: "llm_pending+advice_*",
    expectVoice: true,
    expectTtsPriority: "NORMAL",
  },
];

export const COMMENTARY_AUDIO_ROWS: AudioContractRow[] = [
  {
    id: "commentary:batch",
    source: "CommentaryOrchestrator",
    category: "commentary",
    sampleMessage: "Subiste a P3. Gap adelante +0.8s.",
    audioPriority: "NORMAL",
    severity: "INFO",
    wsEvent: "commentary_end",
    expectVoice: true,
    expectTtsPriority: "NORMAL",
  },
  {
    id: "commentary:race_start",
    source: "CommentaryOrchestrator",
    category: "commentary",
    sampleMessage: "¡Salida! ¡Vamos vamos vamos!",
    audioPriority: "HIGH",
    severity: "INFO",
    wsEvent: "commentary_end",
    expectVoice: true,
    expectTtsPriority: "NORMAL",
  },
];

export const ALL_AUDIO_CONTRACT_ROWS: AudioContractRow[] = [
  ...SPOTTER_AUDIO_ROWS,
  ...ALERT_ONLY_TRIGGER_ROWS,
  ...LLM_TRIGGER_SAMPLE_ROWS,
  ...COMMENTARY_AUDIO_ROWS,
];
