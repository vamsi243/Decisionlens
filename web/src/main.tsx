import "@fontsource-variable/inter";
import "@fontsource-variable/geist";
import "@fontsource/dm-mono/400.css";
import "@fontsource/dm-mono/500.css";
import "./styles/index.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { loadRuntimeConfig } from "./lib/api";

void loadRuntimeConfig().then(() =>
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  ),
);
