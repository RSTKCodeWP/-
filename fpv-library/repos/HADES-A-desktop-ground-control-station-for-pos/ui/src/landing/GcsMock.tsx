import "./gcs.css";

/* Concept render of the HADES ground-control screen, purpose-built for the marketing
 * showcase screenshot (hidden route, linked nowhere). Simple chrome, one accent, and the
 * scene is honest: the aerial base is a real HERIDAL search frame, the four contacts are
 * real detections from the shipped model on that exact frame (their confidences included),
 * and the feed crop shows the top detection with its real box. The flight path, telemetry
 * chips, and graphs illustrate a mission in progress. */

const BASE = import.meta.env.BASE_URL ?? "/";

const CONTACTS = [
  { id: "C-01", x: 56.4, y: 17.3, conf: 0.73, grid: "33T XJ 0641 2519", t: "14:06:41Z", state: "CONFIRMED" },
  { id: "C-02", x: 49.8, y: 10.9, conf: 0.73, grid: "33T XJ 0638 2524", t: "14:06:12Z", state: "CONFIRMED" },
  { id: "C-03", x: 72.8, y: 20.7, conf: 0.71, grid: "33T XJ 0652 2517", t: "14:04:58Z", state: "TRACKING" },
  { id: "C-04", x: 67.0, y: 27.2, conf: 0.71, grid: "33T XJ 0648 2512", t: "14:03:36Z", state: "TRACKING" },
];

// serpentine survey path over the sector, in % of the map viewport
const PATH = "M 6 88 L 6 72 L 94 72 L 94 54 L 6 54 L 6 36 L 94 36 L 94 18 L 46 18";
const FLOWN = "M 6 88 L 6 72 L 94 72 L 94 54 L 6 54 L 6 36 L 60 36";

const EVENTS = [
  { t: "13:58", label: "Launch" },
  { t: "14:03", label: "C-04" },
  { t: "14:05", label: "C-03" },
  { t: "14:06", label: "C-01 C-02" },
  { t: "14:11", label: "Now", now: true },
];

const DETS_PER_MIN = [0, 1, 0, 2, 3, 1, 4, 2, 5, 3, 2, 1, 2];

export function GcsMock() {
  return (
    <div className="gcs">
      <header className="gcs-top">
        <div className="gcs-brand">
          <img src={`${BASE}landing/logo.png`} alt="" />
          <div>
            <strong>HADES Ground Control</strong>
            <span>Sector B-4, grid search</span>
          </div>
        </div>
        <div className="gcs-chips">
          <span className="gcs-chip"><i className="ok" />Link 98%</span>
          <span className="gcs-chip"><i className="ok" />GPS 14 sat</span>
          <span className="gcs-chip">Alt 42 m</span>
          <span className="gcs-chip">Speed 6.2 m/s</span>
          <span className="gcs-chip">Battery 68%</span>
        </div>
        <div className="gcs-clock">
          <span className="gcs-rec"><i />REC</span>
          <time>14:11:26Z</time>
        </div>
      </header>

      <div className="gcs-body">
        <section className="gcs-map">
          <img src={`${BASE}landing/gcs-map.jpg`} alt="" className="gcs-map-img" />
          <svg className="gcs-map-overlay" viewBox="0 0 100 62.5" preserveAspectRatio="none">
            <path d={PATH} className="gcs-path-planned" pathLength={100} />
            <path d={FLOWN} className="gcs-path-flown" pathLength={100} />
          </svg>
          {/* drone at the end of the flown path */}
          <div className="gcs-drone" style={{ left: "60%", top: "36%" }}>
            <svg viewBox="0 0 24 24" aria-hidden>
              <path d="M12 2 L17 20 L12 16 L7 20 Z" fill="currentColor" />
            </svg>
          </div>
          {CONTACTS.map((c) => (
            <div key={c.id} className={`gcs-pin ${c.state === "CONFIRMED" ? "is-confirmed" : ""}`} style={{ left: `${c.x}%`, top: `${c.y}%` }}>
              <span className="gcs-pin-ring" />
              <span className="gcs-pin-dot" />
              <span className="gcs-pin-tag">{c.id}</span>
            </div>
          ))}
          <div className="gcs-map-hud">
            <span>50 m</span>
            <i />
          </div>
          <div className="gcs-map-title">Search area, live aerial</div>
        </section>

        <aside className="gcs-side">
          <section className="gcs-panel gcs-feed">
            <header>
              <h3>Camera</h3>
              <span className="gcs-feed-live"><i />30 fps</span>
            </header>
            <div className="gcs-feed-frame">
              <img src={`${BASE}landing/gcs-feed.jpg`} alt="" />
              <span className="gcs-feed-conf">person 0.74</span>
            </div>
          </section>

          <section className="gcs-panel">
            <header>
              <h3>Contacts</h3>
              <span className="gcs-count">4</span>
            </header>
            <ul className="gcs-contacts">
              {CONTACTS.map((c) => (
                <li key={c.id}>
                  <span className={`gcs-dot ${c.state === "CONFIRMED" ? "ok" : "mid"}`} />
                  <strong>{c.id}</strong>
                  <span className="gcs-grid">{c.grid}</span>
                  <span className="gcs-conf">{c.conf.toFixed(2)}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="gcs-panel">
            <header>
              <h3>Detections / min</h3>
              <span className="gcs-count">61% covered</span>
            </header>
            <svg className="gcs-bars" viewBox="0 0 130 34" preserveAspectRatio="none" aria-hidden>
              {DETS_PER_MIN.map((v, i) => (
                <rect key={i} x={i * 10 + 1.5} width={7} y={32 - v * 6} height={v * 6 + 2} rx={1.5} />
              ))}
            </svg>
            <div className="gcs-coverage"><i style={{ width: "61%" }} /></div>
          </section>
        </aside>
      </div>

      <footer className="gcs-timeline">
        <div className="gcs-timeline-track">
          <i className="gcs-timeline-fill" style={{ width: "78%" }} />
          {EVENTS.map((e, i) => (
            <span key={e.t} className={`gcs-ev ${e.now ? "is-now" : ""}`} style={{ left: `${8 + i * 19}%` }}>
              <i />
              <em>{e.t}</em>
              <strong>{e.label}</strong>
            </span>
          ))}
        </div>
      </footer>
    </div>
  );
}
