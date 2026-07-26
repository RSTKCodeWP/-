import "@fontsource-variable/archivo";
import "@fontsource-variable/urbanist";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "../index.css";
import "./landing.css";
import { GcsMock } from "./GcsMock";
import { LandingPage } from "./LandingPage";

/* Entry for the front-facing demonstration site (vite `--mode landing` → dist-landing/). It
 * shares the design tokens + bundled fonts (index.css) but is otherwise fully decoupled from the
 * operational console and the demo replay. */

const root = document.getElementById("landing-root");
if (!root) throw new Error("#landing-root not found");

// unlinked capture surface for the showcase screenshot; never navigated to from the site
const gcsConcept = window.location.hash === "#/gcs-concept";

createRoot(root).render(
  <StrictMode>{gcsConcept ? <GcsMock /> : <LandingPage />}</StrictMode>,
);
