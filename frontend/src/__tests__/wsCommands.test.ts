import { describe, it, expect, vi, beforeEach } from "vitest";
import { sendWsCommand, registerWsCommands } from "../services/wsCommands";

describe("sendWsCommand", () => {
  beforeEach(() => {
    registerWsCommands(null);
  });

  it("sends spotter and engineer commands when socket is open", () => {
    const send = vi.fn();
    registerWsCommands({ readyState: WebSocket.OPEN, send } as unknown as WebSocket);

    expect(sendWsCommand("spotter_command", { action: "enable" })).toBe(true);
    expect(sendWsCommand("engineer_command", { action: "disable" })).toBe(true);

    expect(send).toHaveBeenCalledTimes(2);
    expect(JSON.parse(send.mock.calls[0][0])).toEqual({
      event: "spotter_command",
      data: { action: "enable" },
    });
  });

  it("returns false when socket is closed", () => {
    expect(sendWsCommand("engineer_command", { action: "enable" })).toBe(false);
  });
});
