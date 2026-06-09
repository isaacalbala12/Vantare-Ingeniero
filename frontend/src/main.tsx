import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import HubRoot from "./hub/HubRoot";
import { OverlayApp } from "./overlay/OverlayApp";
import "./styles/index.css";

const isOverlay =
  window.location.pathname.endsWith("overlay.html") ||
  new URLSearchParams(window.location.search).get("mode") === "overlay";

const root = createRoot(document.getElementById("root")!);
if (isOverlay) {
  document.documentElement.classList.add("overlay-shell");
  document.body.classList.add("overlay-shell");
  root.render(<OverlayApp />);
} else {
  root.render(
    <StrictMode>
      <HubRoot />
    </StrictMode>,
  );
}
