import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./App.css";
import "./signalforge/motion/motion.css";
import { initMotionPreference } from "./signalforge/motion/motionPreference";

initMotionPreference();

const el = document.getElementById("root");
if (!el) throw new Error("missing #root element");
createRoot(el).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
