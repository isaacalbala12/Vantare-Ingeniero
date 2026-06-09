import { describe, it, expect, beforeEach } from "vitest";
import { useAppStore } from "../store/config";

describe("radio history", () => {
  beforeEach(() => useAppStore.setState({ radio: { ...useAppStore.getState().radio, messageHistory: [] } }));

  it("addRadioAlertToHistory guarda aviso spotter", () => {
    useAppStore.getState().addRadioAlertToHistory("spotter", "Hypercar doblando por la derecha", "proximity");
    const h = useAppStore.getState().radio.messageHistory;
    expect(h).toHaveLength(1);
    expect(h[0].sender).toBe("spotter");
    expect(h[0].category).toBe("proximity");
  });

  it("no duplica el mismo aviso consecutivo", () => {
    const { addRadioAlertToHistory } = useAppStore.getState();
    addRadioAlertToHistory("spotter", "Clear", "proximity");
    addRadioAlertToHistory("spotter", "Clear", "proximity");
    expect(useAppStore.getState().radio.messageHistory).toHaveLength(1);
  });
});
