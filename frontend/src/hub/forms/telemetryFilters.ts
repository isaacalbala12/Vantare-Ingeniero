/**
 * Filtros compartidos para mensajes internos de radio/telemetría.
 * Extraídos de useWebSocket.ts para uso compartido con la store.
 */

export function isInternalRadioText(text: string): boolean {
  const trimmed = text.trim();
  return (
    trimmed.startsWith("---") ||
    trimmed.startsWith("...") ||
    trimmed.includes("Pérdida de comunicación")
  );
}
