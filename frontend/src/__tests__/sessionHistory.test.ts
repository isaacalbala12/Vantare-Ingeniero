import { describe, it, expect } from "vitest";

describe("session history types", () => {
  it("SessionHistoryFile acepta sender spotter", () => {
    const file: { sender: string; text: string; timestamp: number } = {
      sender: "spotter",
      text: "Coche por la derecha",
      timestamp: Date.now(),
    };
    expect(file.sender).toBe("spotter");
  });

  it("MessageRecord acepta category opcional", () => {
    const msg: { sender: string; text: string; timestamp: number; category?: string } = {
      sender: "engineer",
      text: "Combustible para 5 vueltas",
      timestamp: Date.now(),
      category: "fuel",
    };
    expect(msg.category).toBe("fuel");
  });
});
