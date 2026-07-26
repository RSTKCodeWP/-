/* Phase 7 Task 7.6 - the single in-app docs source.
 *
 * One content definition, rendered by `DocsPanel` and shared across all three surfaces (Electron
 * app, web app, demo site) because they all run this React UI. It is the same content family as
 * the root README: the pipeline overview, the four metric families with their real figures, the
 * versioned tool list, and the honesty disclosures. Every number here traces to a real artifact
 * produced in an earlier build phase (the content gate, docs/documentation/OUTLINE.md); nothing
 * is invented. Figures resolve relative to the page base so they load under Electron file://,
 * a GitHub Pages subpath, and a server root alike. */

export interface DocFigure {
  src: string; // relative to BASE_URL/docs/
  alt: string;
  caption: string;
}

export interface DocSection {
  id: string;
  heading: string;
  body: string[];
  figures?: DocFigure[];
  table?: { columns: string[]; rows: string[][] };
}

export interface DocTool {
  name: string;
  version: string;
  group: "service" | "ui";
}

export const DOC_TAGLINE =
  "A ground-control station for post-hurricane drone search-and-rescue.";

export const DOC_INTRO =
  "HADES ingests a live FPV-drone video feed, runs real-time human detection on the frames, " +
  "computes real-world survivor coordinates with honest uncertainty, and presents detections " +
  "plus a live survivor map in a coordinator UI that runs on a 16 GB MacBook Air in the field.";

export const DOC_HONESTY =
  "Every number below traces to a real artifact from an earlier build phase. Detection metrics " +
  "are on a custom by-scene HERIDAL held-out split (not the official test split, so they are " +
  "not directly comparable to published benchmarks). Localization numbers are from a calibrated " +
  "synthetic simulator (tagged sim); they prove the method is correct and the uncertainty is " +
  "honest, and they will move when the real labeled-with-pose flight set lands. The latency p95 " +
  "is a dev-floor measured under software GL, not the binding field number.";

export const DOC_SECTIONS: DocSection[] = [
  {
    id: "overview",
    heading: "Pipeline",
    body: [
      "Video displays at full frame rate while detection, tracking, and localization run " +
        "decoupled, so a survivor pin never costs a dropped video frame. One contact flows " +
        "through seven single-responsibility stages.",
      "Two localhost WebSocket channels carry the data, one binary (JPEG frames) and one JSON " +
        "(detections and telemetry), aligned by frame_id so every overlay lands on its frame.",
    ],
    figures: [
      {
        src: "figures/fig-arch.png",
        alt: "HADES pipeline architecture",
        caption: "FrameSource to Detector to Tracker to Projector to Confirmation to Fuse to UI.",
      },
    ],
  },
  {
    id: "detection",
    heading: "Detection",
    body: [
      "YOLO11s fine-tuned on HERIDAL and SARD, single person class, exported to Core ML (FP16) " +
        "and served on the Apple Neural Engine. Evaluated by center-distance matching on 376 " +
        "held-out HERIDAL frames. The fine-tune is the win: stock COCO YOLO11s barely fires on " +
        "tiny aerial people, and FP16 quantization did not cost accuracy.",
      "Shipped FP16 model at the default operating point: recall 0.551, precision 0.676. The 960 " +
        "input resolution was chosen on the same held-out set, so treat 0.551 as an estimate " +
        "pending the curated disaster footage.",
    ],
    figures: [
      {
        src: "figures/showcase-before-after.png",
        alt: "Stock vs fine-tuned detector on a real HERIDAL frame",
        caption: "Stock YOLO11s (left) vs the HADES SAR fine-tune (right), same real frame.",
      },
      {
        src: "figures/fig-detection-conf-sweep.png",
        alt: "Detection operating points",
        caption: "Recall and precision across the confidence sweep.",
      },
    ],
    table: {
      columns: ["Operating point (conf)", "Recall", "Precision"],
      rows: [
        ["0.25 (default)", "0.51", "0.62"],
        ["0.10", "0.63", "0.46"],
        ["0.05 (recall-first)", "0.69", "0.37"],
      ],
    },
  },
  {
    id: "localization",
    heading: "Localization",
    body: [
      "Monocular ray-to-ground fusion with a Monte Carlo uncertainty ellipse. Error grows " +
        "cleanly with slant range and pitch: near-nadir is PINPOINT-grade, oblique standoff is " +
        "AREA-grade. The system is heading-limited (no magnetometer); the ellipse reflects that " +
        "rather than reporting false precision.",
      "The calibration chart is the credibility check. A matched control covers about 95% (the " +
        "arithmetic is right), and an out-of-schema time-sync offset the Monte Carlo cannot " +
        "model collapses coverage to 25%. That collapse is the evidence the metric measures the " +
        "world, not its own math.",
    ],
    figures: [
      {
        src: "figures/fig-loc-error-by-geometry.png",
        alt: "Localization error by geometry",
        caption: "Median and p90 meter error by slant range and pitch (sim).",
      },
      {
        src: "figures/fig-coverage-calibration.png",
        alt: "Uncertainty calibration",
        caption: "Coverage per noise pairing vs the 95% target; the time-sync collapse (sim).",
      },
    ],
    table: {
      columns: ["Geometry (range x pitch)", "median (sim)", "p90 (sim)", "coverage"],
      rows: [
        ["30 to 80 m, near-nadir", "1.2 m", "2.2 m", "0.97"],
        ["80 to 150 m, near-nadir", "7.6 m", "15.6 m", "0.80"],
        ["150 to 300 m, oblique 65+ deg", "11.8 m", "17.4 m", "1.00"],
      ],
    },
  },
  {
    id: "realtime",
    heading: "Real-time",
    body: [
      "The latency budget is in-app glass-to-glass at 120 ms. Video runs at 30 fps; detection " +
        "runs decoupled at 10 fps or better. All three candidate resolutions clear the detection " +
        "gate on a fanless MacBook Air M4, and a 5.6x speedup over CPU at 640 px confirms the ANE " +
        "serves the model.",
      "In-app latency on the dev machine: p50 1.9 ms, p95 22.4 ms, max 33.6 ms over 90 frames, " +
        "clearing the 120 ms budget by 5x at p95. This is a dev-floor under software GL with " +
        "small canned frames; the on-device field run on real-resolution frames is pending.",
    ],
    figures: [
      {
        src: "figures/fig-fps-by-resolution.png",
        alt: "Detector throughput by resolution",
        caption: "ANE forward-pass FPS per resolution with the 10 fps detection gate.",
      },
      {
        src: "figures/fig-latency-budget.png",
        alt: "In-app latency budget",
        caption: "Measured p50/p95/max against the 120 ms budget (dev floor).",
      },
    ],
    table: {
      columns: ["Resolution", "Detector throughput (ANE)", "Clears 10 fps gate"],
      rows: [
        ["640 px", "293 fps", "yes"],
        ["960 px (shipped)", "63 fps", "yes"],
        ["1280 px", "57 fps", "yes"],
      ],
    },
  },
];

// Versions read from the lockfiles (service/uv.lock, the cluster requirements lock, ui/pnpm-lock).
export const DOC_TOOLS: DocTool[] = [
  { name: "Ultralytics YOLO11", version: "8.4.76", group: "service" },
  { name: "PyTorch", version: "2.11.0 (cu128)", group: "service" },
  { name: "Core ML Tools", version: "8.x", group: "service" },
  { name: "NumPy", version: "1.26.4", group: "service" },
  { name: "ONNX Runtime", version: "1.27.0", group: "service" },
  { name: "PyAV", version: "17.1.0", group: "service" },
  { name: "OpenCV", version: "4.11.0", group: "service" },
  { name: "Pydantic", version: "2.13.4", group: "service" },
  { name: "websockets", version: "16.0", group: "service" },
  { name: "Electron", version: "33.4.11", group: "ui" },
  { name: "React", version: "18.3.1", group: "ui" },
  { name: "TypeScript", version: "5.9.3", group: "ui" },
  { name: "Vite", version: "6.4.3", group: "ui" },
  { name: "Tailwind CSS", version: "3.4.19", group: "ui" },
  { name: "MapLibre GL", version: "5.24.0", group: "ui" },
  { name: "Zustand", version: "5.0.14", group: "ui" },
  { name: "Playwright", version: "1.61.0", group: "ui" },
];
