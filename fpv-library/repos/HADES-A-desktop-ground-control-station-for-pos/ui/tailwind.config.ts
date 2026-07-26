import type { Config } from "tailwindcss";

/* Tokens are CSS RGB-channel variables in src/styles/tokens.css; Tailwind maps each to
 * rgb(var(--token) / <alpha-value>) so the opacity modifier works (DESIGN-SYSTEM §9.1).
 * Components use these UTILITIES (bg-surface-1, text-text-hi, font-mono) — never arbitrary
 * [var(--x)] values, which bypass the scale and invite the off-token drift §6 forbids. */

const channel = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

// Status color utilities are composed dynamically (statusToken(state) → `text-st-*` /
// `bg-st-*` / `border-st-*`), so Tailwind's JIT can't see them in source — safelist them or
// they get purged from the built CSS and the status colors silently don't render.
const STATUS = ["nominal", "info", "caution", "warning", "critical", "stale"];
const statusSafelist = STATUS.flatMap((s) => [
  `text-st-${s}`,
  `bg-st-${s}`,
  `border-st-${s}`,
  `bg-st-${s}/10`,
  `bg-st-${s}/20`,
]);

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  safelist: statusSafelist,
  theme: {
    extend: {
      colors: {
        "bg-void": channel("bg-void"),
        "bg-base": channel("bg-base"),
        "video-letterbox": channel("video-letterbox"),
        "surface-1": channel("surface-1"),
        "surface-2": channel("surface-2"),
        "surface-3": channel("surface-3"),
        "surface-4": channel("surface-4"),
        hairline: channel("hairline"),
        "hairline-strong": channel("hairline-strong"),
        "text-hi": channel("text-hi"),
        "text-mid": channel("text-mid"),
        "text-lo": channel("text-lo"),
        "text-disabled": channel("text-disabled"),
        "text-on-accent": channel("text-on-accent"),
        "blue-core": channel("blue-core"),
        "blue-bright": channel("blue-bright"),
        "blue-track": channel("blue-track"),
        "st-nominal": channel("st-nominal"),
        "st-info": channel("st-info"),
        "st-caution": channel("st-caution"),
        "st-warning": channel("st-warning"),
        "st-critical": channel("st-critical"),
        "st-stale": channel("st-stale"),
      },
      spacing: {
        px: "var(--sp-px)",
        0.5: "var(--sp-0_5)",
        1: "var(--sp-1)",
        2: "var(--sp-2)",
        3: "var(--sp-3)",
        4: "var(--sp-4)",
        6: "var(--sp-6)",
        8: "var(--sp-8)",
        12: "var(--sp-12)",
        "rail-w": "var(--rail-w)",
        "rail-w-labelled": "var(--rail-w-labelled)",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        pill: "var(--radius-pill)",
      },
      fontFamily: {
        ui: "var(--font-ui)",
        mono: "var(--font-mono)",
      },
      fontSize: {
        "2xs": "var(--text-2xs)",
        xs: "var(--text-xs)",
        sm: "var(--text-sm)",
        base: "var(--text-base)",
        lg: "var(--text-lg)",
        xl: "var(--text-xl)",
        "2xl": "var(--text-2xl)",
        "3xl": "var(--text-3xl)",
        "4xl": "var(--text-4xl)",
      },
      boxShadow: {
        focus: "var(--ring-focus)",
        selected: "var(--ring-selected)",
        alert: "var(--alert-glow)",
        // The craft-layer card/pop elevation (UI-overhaul pivot). Day defines the soft warm
        // shadows; Night leaves them unset → `none`, so dark chrome stays appropriately flat
        // (shadows read poorly on dark; dark uses surface-step + hairline for depth instead).
        card: "var(--shadow-card, none)",
        pop: "var(--shadow-pop, none)",
        float: "var(--shadow-float, none)",
      },
      zIndex: {
        base: "var(--z-base)",
        "map-overlay": "var(--z-map-overlay)",
        docked: "var(--z-docked)",
        "status-strip": "var(--z-status-strip)",
        popover: "var(--z-popover)",
        dialog: "var(--z-dialog)",
        "shortcut-sheet": "var(--z-shortcut-sheet)",
        "toast-alert": "var(--z-toast-alert)",
      },
      transitionTimingFunction: {
        standard: "var(--ease-standard)",
        entrance: "var(--ease-entrance)",
        exit: "var(--ease-exit)",
      },
      transitionDuration: {
        micro: "90ms",
        select: "140ms",
        base: "200ms",
        pin: "400ms",
        enter: "340ms",
        cross: "120ms",
      },
    },
  },
  plugins: [],
} satisfies Config;
