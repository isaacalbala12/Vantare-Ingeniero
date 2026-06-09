import { createRoot } from "react-dom/client";
import { OverlayApp } from "./OverlayApp";
import "./overlay.css";

document.documentElement.classList.add("overlay-shell");
document.body.classList.add("overlay-shell");

createRoot(document.getElementById("root")!).render(<OverlayApp />);
