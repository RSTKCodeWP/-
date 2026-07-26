import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";
import electron from "vite-plugin-electron/simple";

// Vite injects `crossorigin` on the built <script>/<link> tags. Over `file://` (opening the
// static build by double-clicking the .html) that triggers a CORS block → the CSS + JS silently
// fail to load and you get raw unstyled HTML. The static demo + landing site are meant to be
// openable as local files, so strip `crossorigin` from their emitted HTML.
function fileProtocolSafe(): Plugin {
  return {
    name: "file-protocol-safe",
    enforce: "post",
    transformIndexHtml(html) {
      return (
        html
          // strip crossorigin (CORS-blocks the CSS/JS over file://)
          .replace(/\s+crossorigin(="[^"]*")?/g, "")
          // ES modules can't run over file:// — with an IIFE bundle the script is classic, so
          // emit `<script defer>` instead of `<script type="module">`.
          .replace(/<script type="module"/g, "<script defer")
      );
    },
  };
}

// Two build targets share ONE config (Phase 6 / adversarial-panel R3):
//  - default (Electron app): bundles the renderer + the Electron main/preload via the plugin.
//  - `--mode web` (the static demo site): DROPS the Electron plugin (its Node-touching main/
//    preload would be dead weight in a browser bundle) and emits to `dist-web/` so it never
//    collides with the Electron `dist/`. `base: "./"` is kept for BOTH — relative asset/font
//    URLs resolve identically under a GitHub-Pages subpath, a Netlify/Vercel root, AND file://;
//    a hard-coded `/HADES/` base would break the latter two (verified, DESIGN-SYSTEM §9.2).
export default defineConfig(({ mode }) => {
  const web = mode === "web";
  // `--mode landing` builds the front-facing DEMONSTRATION site (CuboCruise-style marketing
  // page) from its own `landing.html` entry → `dist-landing/`. Like `web` it drops the Electron
  // plugin (pure browser) and keeps `base: "./"` so it deploys under any subpath / file://. It
  // is fully decoupled from the operational app + the demo replay; it only shares design tokens.
  const landing = mode === "landing";
  const browserOnly = web || landing;
  return {
    base: "./",
    plugins: [
      react(),
      // the landing site is opened as a local file → make its HTML file://-safe (classic script,
      // no crossorigin). Only landing uses the IIFE bundle, so only it gets the module→defer swap.
      ...(landing ? [fileProtocolSafe()] : []),
      ...(browserOnly
        ? []
        : [
            electron({
              main: { entry: "electron/main.ts" },
              preload: { input: "electron/preload.ts" },
              renderer: {},
            }),
          ]),
    ],
    build: {
      outDir: landing ? "dist-landing" : web ? "dist-web" : "dist",
      emptyOutDir: true,
      // The landing site is meant to be opened as a LOCAL FILE (double-click the .html). ES
      // `<script type=module>` is blocked over file:// by CORS no matter what, so emit a single
      // CLASSIC (IIFE) bundle with everything inlined — runs from file:// AND http. `modulePreload`
      // off so no module-preload links are injected either.
      ...(landing
        ? {
            modulePreload: false,
            rollupOptions: {
              input: "landing.html",
              output: { format: "iife" as const, inlineDynamicImports: true },
            },
          }
        : {}),
    },
  };
});
