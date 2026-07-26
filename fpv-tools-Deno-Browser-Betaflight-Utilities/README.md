# FPV Tools

Browser-based utilities for Betaflight configuration and FPV drone setup. All tools run entirely in your browser — no account, no server-side processing, no data collection. Installable as a PWA and works offline after your first visit.

## Tools

### 🔀 CLI Merge
**Path:** `./cli-merge/`

Compare two Betaflight CLI dumps side-by-side and generate a merged output. Useful for:
- Merging settings from two different configurations
- Comparing tune changes across revisions
- Extracting specific sections from full dumps

Inputs accept pasted text, a file picker, or drag-and-drop from your desktop. The tool follows an **A = base / B = import** convention, detects the Betaflight version in each dump's header, and validates the merged output (unknown keys, duplicates, malformed lines, missing `save`) using A's firmware version as the target.

### 📈 Rate Profile Comparison
**Path:** `./rate-profile/`

Compare two Betaflight Actual Rates profiles with real-time visualization. Features:
- **Dual profile editor** — adjust roll, pitch, yaw, throttle on two profiles simultaneously
- **Throttle limit** — Off/Scale/Clip mode plus a 25-100% limit slider, matching Betaflight's `throttle_limit_*` settings
- **Live graphs** — see rate curves and throttle response update instantly
- **Collapsible graph panels** — hide individual graphs; the state is remembered between visits
- **Overlay or side-by-side view** — choose how you compare
- **Profile history** — save, name, and load profiles from browser localStorage
- **CLI import/export** — paste Betaflight dumps to load settings; copy CLI commands back
- **Visibility toggles** — focus on specific profiles or axes
- **Mobile-responsive** — works on tablet and phone

### 🔩 Prop / Motor Sizer
**Path:** `./prop-motor-sizer/`

Characterize an FPV powertrain from prop size, blade count, motor size, KV, battery cells, and all-up weight — or leave any of those blank and get suggested ranges derived from what you did enter. Features:
- **Flight character verdicts** — thrust-to-weight interpretation, motor/prop torque match, KV-vs-voltage rev match, and tip-speed warnings
- **Estimated numbers** — static thrust, hover throttle, RPM under load, tip speed (Mach), pitch speed, hover and full-throttle current draw, disc loading
- **Suggested ranges** — e.g. pick a 5″ prop on 6S and get a recommended KV band and a list of suitable stator sizes; enter a motor and get the prop diameters it suits
- **Style-aware** — cinematic / long-range / freestyle / racing biases pitch, KV, and AUW recommendations
- **Presets** — tiny whoop, 3″ 4S, 5″ 6S freestyle, 5″ 4S race, 7″ long-range starting points
- **Advanced panel** — adjust the motor load factor, battery chemistry (LiPo/LiHV/Li-Ion) and voltage basis (full charge / nominal / under load), and altitude; add battery capacity for a hover-endurance estimate; or enter one thrust-stand measurement to calibrate the whole model to your bench numbers
- Inputs persist in localStorage; estimates are simplified-physics ballparks (±20–30% unless calibrated), not thrust-stand data

## Getting Started

1. **Open fpv-tools in your browser:** https://cori.github.io/fpv-tools/
2. **Pick a tool** from the hub
3. **Use it** — everything happens in your browser

## Development

### Adding a New Tool

1. Create a new directory: `your-tool/`
2. Include `index.html` as the entry point (can reference `your-tool/src/` modules if needed)
3. Add the shared header for consistent navigation and PWA support:
   ```html
   <link rel="stylesheet" href="../assets/site-header.css">
   ...
   <fpv-header root="../" icon="🔧" heading="Your Tool" subtitle="What it does"></fpv-header>
   <script type="module" src="../assets/site-header.js"></script>
   ```
   `root` is the relative path back to the site root — it drives the
   back-to-home link plus the manifest/service-worker/icon links, so every
   new tool gets navigation and offline support without extra wiring.
4. Add the new page's URLs to `PRECACHE_URLS` in `sw.js` and bump `CACHE_NAME`
   so it's available offline
5. Add a card to the hub in the main `index.html`
6. Commit and push — GitHub Pages will deploy automatically

### Tech Stack

- **Vanilla HTML/CSS/JS** — no frameworks, no build step
- **ES6 modules** — for clean code organization
- **HTML5 Canvas** — for graphs and visualizations
- **localStorage** — for client-side data persistence
- **Mobile-responsive CSS** — flexbox/grid, media queries

### Style Guide

- Dark theme (GitHub-inspired colors)
- Orange accent color (`#e07b39`) for key UI elements
- Card-based layout for tools
- Monospace fonts for technical content (CLI, values)

### Testing

Some tools include unit tests. Run with:
```bash
npm test
```

## Architecture

```
fpv-tools/
├── index.html              # Hub page with tool links
├── manifest.json            # PWA manifest (install on mobile/desktop)
├── sw.js                    # Service worker — offline caching for all pages
├── assets/
│   ├── site-header.js       # <fpv-header> shared nav/PWA-wiring component
│   ├── site-header.css      # Shared header styles
│   └── icons/                # PWA icons (generated by scripts/generate-icons.mjs)
├── cli-merge/
│   ├── index.html          # CLI Merge tool
│   └── src/
│       ├── parser.js
│       ├── output.js
│       └── validator.js
├── rate-profile/
│   ├── index.html          # Rate Profile tool
│   ├── styles.css          # Tool-specific styles
│   └── src/
│       ├── app.js          # Main controller
│       ├── rate-calculator.js
│       ├── cli-parser.js
│       ├── graph-renderer.js
│       └── profile-manager.js
├── igow/
│   ├── index.html          # IGOW Challenge Reference tool
│   └── igow.db              # SQLite dataset (queried via sql.js)
├── prop-motor-sizer/
│   ├── index.html          # Prop / Motor Sizer tool
│   ├── styles.css
│   └── src/
│       ├── app.js          # DOM wiring and rendering
│       └── sizer-calculator.js  # Pure sizing math (tested)
└── .github/
    └── workflows/
        ├── deploy.yml      # GitHub Pages auto-deploy on push
        └── test.yml        # Deno test suite on push/PR
```

### Installability & Offline Support

Every page links `manifest.json` and registers `sw.js` through the shared
`<fpv-header>` component. On a supported browser (e.g. Chrome/Edge on
Android or desktop), visiting the site once lets you "Install" it as an
app; after that first visit, the service worker serves cached pages so the
tools keep working without a network connection.

## License

MIT
