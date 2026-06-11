import { describe, expect, it, vi } from "vitest";
import { sendTestAudio, registerWsCommands } from "../services/wsCommands";

describe("sendTestAudio", () => {
	it("sends test_audio event", () => {
		const ws = {
			readyState: WebSocket.OPEN,
			send: vi.fn(),
		} as unknown as WebSocket;
		registerWsCommands(ws);
		sendTestAudio();
		expect(ws.send).toHaveBeenCalledWith(
			JSON.stringify({ event: "test_audio", data: {} }),
		);
	});
});
