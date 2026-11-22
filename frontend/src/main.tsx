import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Self-hosted fonts so the UI looks the same offline. Domine is the typeface for all text
// (latin-ext covers the macrons in "dēcernō"); IBM Plex Mono is kept for incident numbers and times.
import "@fontsource/domine/latin-400.css";
import "@fontsource/domine/latin-500.css";
import "@fontsource/domine/latin-600.css";
import "@fontsource/domine/latin-700.css";
import "@fontsource/domine/latin-ext-400.css";
import "@fontsource/domine/latin-ext-600.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import { App } from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
