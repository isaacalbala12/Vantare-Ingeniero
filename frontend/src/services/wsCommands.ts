let activeWs: WebSocket | null = null;

export function registerWsCommands(ws: WebSocket | null): void {
	activeWs = ws;
}

export function sendTestAudio(): boolean {
	return sendWsCommand("test_audio", {});
}

export function sendWsCommand(
	event: string,
	data: Record<string, unknown>,
): boolean {
	if (activeWs?.readyState !== WebSocket.OPEN) {
		console.warn("[wsCommands] WebSocket no conectado, no se envió:", event);
		return false;
	}
	activeWs.send(JSON.stringify({ event, data }));
	return true;
}
