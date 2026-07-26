import { ArrowRight, ArrowUpRight, Minus, Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { BeforeAfter } from "./BeforeAfter";
import { gsap, ScrollTrigger, scrollToTop, usePanelGrow, useParallax, useReveals, useSmoothScroll } from "./motion";

/* HADES demonstration site v3. One family (Archivo), one accent (the logo teal), warm
 * tinted neutrals, and a static floating-drone hero (Cubo grammar: the product sits centered
 * on the page's own background, lifted by a soft shadow). Every product image is real output;
 * every number is measured. No demo links: the site shows, it does not hand out the console. */

const BASE = import.meta.env.BASE_URL ?? "/";
const A = (p: string) => `${BASE}landing/${p}`;

/* ---------------- hash router ---------------- */
type Route = "home" | "technology" | "team";
function parseRoute(): Route {
  const h = location.hash.replace(/^#\/?/, "");
  return h === "technology" || h === "team" ? h : "home";
}

export function LandingPage() {
  const [route, setRoute] = useState<Route>(parseRoute);
  useSmoothScroll();
  useEffect(() => {
    const onHash = () => {
      ScrollTrigger.getAll().forEach((t) => t.kill());
      // switching sections always lands at the top of the new page (drives Lenis, not just window)
      scrollToTop();
      setRoute(parseRoute());
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  // after the new route's DOM is in place, pin it to the top again (the new page may be taller /
  // reveals re-arm, so a single pre-render scroll isn't always enough)
  useEffect(() => {
    scrollToTop();
  }, [route]);
  useReveals([route]);
  useParallax([route]);
  usePanelGrow([route]);

  return (
    <div className="landing">
      <Nav route={route} />
      {route === "home" && <Home />}
      {route === "technology" && <Technology />}
      {route === "team" && <Team />}
      <Footer />
    </div>
  );
}

/* ---------------- nav ---------------- */
function Nav({ route }: { route: Route }) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 24);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  const link = (to: Route, label: string) => (
    <a href={to === "home" ? "#/" : `#/${to}`} className={`nav-link ${route === to ? "is-active" : ""}`}>
      {label}
    </a>
  );
  return (
    <header className={`site-nav ${scrolled ? "is-scrolled" : ""}`}>
      <a href="#/" className="nav-brand" aria-label="HADES home">
        <img src={A("logo.png")} alt="" />
        <span>HADES</span>
      </a>
      <nav className="nav-links">
        {link("home", "Overview")}
        {link("technology", "Technology")}
        {link("team", "Team")}
      </nav>
    </header>
  );
}

/* =================================================================== HOME */
function Home() {
  return (
    <main>
      <Hero />
      <Statement />
      <LogoStrip />
      <SeeSection />
      <PipelineRail />
      <Showcase />
      <Inspiration />
      <MetricsSection />
      <Closing />
    </main>
  );
}

/* ---- hero: the Cubo grammar. The drone is a single high-quality static render, centered and
   floated on the page's OWN background with a soft drop-shadow (no WebGL, no frame sequence).
   The wordmark sits behind it; a short caption and the four-step verb list frame it. On scroll
   the drone drifts gently DOWN (parallax lag) while the copy lifts UP into the next section —
   the "words get picked up by the page" feel. All transform-only, GPU, 60fps. ---- */
const HERO_WORDS = ["Detect", "Localize", "Confirm", "Coordinate"];
function Hero() {
  const droneRef = useRef<HTMLImageElement>(null);
  const copyRef = useRef<HTMLDivElement>(null);

  // Cubo hero grammar (from teardown): the copy RIDES UP as the page scrolls — it leads slightly
  // and does NOT fade (the words just get lifted off the top), while the drone LAGS behind with a
  // gentle downward parallax (~0.85:1) and a barely-there scale-down, so it lingers and floats as
  // the words leave. Continuous + reversible; user-scroll-driven, so it always runs.
  useEffect(() => {
    const drone = droneRef.current;
    const copy = copyRef.current;
    if (!drone || !copy) return;
    const tl = gsap.timeline({
      scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: 0.6 },
    });
    // drone lags down + shrinks ~1.5% (the Cubo float)
    tl.fromTo(drone, { yPercent: 0, scale: 1 }, { yPercent: 16, scale: 0.985, ease: "none" }, 0);
    // copy leads up, NO fade (rides the page off the top like Cubo, not a dissolve)
    tl.fromTo(copy, { yPercent: 0 }, { yPercent: -22, ease: "none" }, 0);
    return () => {
      tl.scrollTrigger?.kill();
      tl.kill();
    };
  }, []);

  return (
    <section className="hero">
      <div className="hero-copy" ref={copyRef}>
        <span className="hero-word" aria-hidden>
          HADES
        </span>
        <img
          src={A("drone-poster.png")}
          alt="The HADES search-and-rescue drone"
          className="hero-drone"
          ref={droneRef}
          draggable={false}
          fetchPriority="high"
        />
        <p className="hero-desc">
          An end to end system for post hurricane search and rescue: drone, detection, and
          ground control.
        </p>
        <ol className="hero-steps" aria-hidden>
          {HERO_WORDS.map((w, i) => (
            <li key={w} style={{ "--si": String(i) } as React.CSSProperties}>
              {w}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/* ---- statement: the promise, revealed word by word as you scroll through it ---- */
const STATEMENT =
  "HADES turns a live drone feed into located survivors on a map. Real time detection, real world coordinates, one laptop, no network.";
function Statement() {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const words = el.querySelectorAll<HTMLElement>("span");
    const tween = gsap.fromTo(
      words,
      { opacity: 0.14 },
      {
        opacity: 1,
        ease: "none",
        stagger: 0.06,
        scrollTrigger: { trigger: el, start: "top 78%", end: "bottom 45%", scrub: 0.4 },
      },
    );
    return () => {
      tween.scrollTrigger?.kill();
      tween.kill();
    };
  }, []);
  return (
    <section className="statement">
      <div className="statement-main">
        <p className="statement-kick" data-reveal="left">
          The mission
        </p>
        <h2 ref={ref} className="statement-text">
          {STATEMENT.split(" ").map((w, i) => (
            <span key={i}>{w} </span>
          ))}
        </h2>
      </div>
      <ul className="statement-points">
        {[
          { k: "On-device", v: "The whole loop runs on one laptop with the network off." },
          { k: "Real-time", v: "Detection at ten frames a second while video plays at thirty." },
          { k: "Honest", v: "Every contact carries an uncertainty radius, never a false pin." },
        ].map((p, i) => (
          <li key={p.k} data-reveal="right" style={{ "--si": String(i) } as React.CSSProperties}>
            <strong>{p.k}</strong>
            <span>{p.v}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/* ---- recognition ---- */
const LOGOS = [
  { src: "logos/duke-pratt.svg", alt: "Duke Pratt School of Engineering", h: 46 },
  { src: "logos/mit-solve.png", alt: "MIT Solve", h: 34 },
  { src: "logos/day-of-ai.png", alt: "Day of AI", h: 58 },
  { src: "logos/ncsef.png", alt: "North Carolina Science and Engineering Fair", h: 58 },
  { src: "logos/samsung-sft.png", alt: "Samsung Solve for Tomorrow", h: 68 },
];
function LogoStrip() {
  return (
    <section className="logo-strip">
      <p className="logo-strip-label" data-reveal>
        Recognized and supported by
      </p>
      <div className="logo-strip-row">
        {LOGOS.map((l) => (
          <img key={l.src} src={A(l.src)} alt={l.alt} style={{ height: l.h }} loading="lazy" data-reveal="up" />
        ))}
      </div>
    </section>
  );
}

/* ---- the before/after moment ---- */
function SeeSection() {
  return (
    <section className="section">
      <div className="section-head" data-reveal="left">
        <h2 className="section-title">
          See what the eye
          <br />
          <span className="ink-faint">cannot.</span>
        </h2>
        <p className="section-lede">
          A survivor is a handful of pixels in a four thousand pixel aerial frame. This is a real
          frame from the HERIDAL search and rescue test set. Drag the divider: every box is live
          output from the shipped model, not an illustration.
        </p>
      </div>
      <div data-reveal="zoom">
        <BeforeAfter />
      </div>
    </section>
  );
}

/* ---- pipeline: a connected flow DIAGRAM (frame -> found). Four stages linked by arrows read as
   one system, sitting on the "Offline, by design" foundation that carries the whole loop. ---- */
const STEPS = [
  {
    n: "01",
    title: "Detect",
    body: "A YOLO11 model fine tuned on aerial search imagery finds people in every frame, on the laptop's neural engine.",
  },
  {
    n: "02",
    title: "Localize",
    body: "Each detection becomes a ray through the aircraft's pose, intersected with the ground to give a real coordinate and an uncertainty radius.",
  },
  {
    n: "03",
    title: "Confirm",
    body: "Tracks persist across frames and cluster in world space. Confidence builds and contacts get promoted.",
  },
  {
    n: "04",
    title: "Coordinate",
    body: "One contact, three views: map, video, list, over a single selection. Every event lands in the mission log.",
  },
];
function PipelineRail() {
  return (
    <section className="rail-section">
      <div className="section-head rail-head" data-reveal>
        <h2 className="section-title">Frame to found.</h2>
        <p className="section-lede">
          One loop turns a live frame into a located survivor. Each stage feeds the next, and the
          whole pipeline runs offline on a single laptop.
        </p>
      </div>
      <div className="flow" data-reveal="up">
        <ol className="flow-track">
          {STEPS.map((s) => (
            <li key={s.n} className="flow-node">
              <span className="flow-num">{s.n}</span>
              <h3 className="flow-title">{s.title}</h3>
              <p className="flow-body">{s.body}</p>
            </li>
          ))}
        </ol>
        <div className="flow-base">
          <span className="flow-base-label">Offline, by design</span>
          <p className="flow-base-body">
            The whole loop runs with the network off. Map tiles are cached before the mission,
            inference stays on the laptop, nothing phones home. Built for the hour after the storm,
            when nothing else works.
          </p>
        </div>
      </div>
    </section>
  );
}

/* ---- the ground station, shown not linked ---- */
function Showcase() {
  return (
    <section className="section">
      <div className="section-head" data-reveal="right">
        <h2 className="section-title">One screen runs the search.</h2>
        <p className="section-lede">
          The coordinator's view: live aerial imagery with the flight path, confirmed contacts
          with their confidence, the camera with its detections, and a mission timeline. The
          scene below is a real search frame and the four contacts are real model output.
        </p>
      </div>
      <figure className="shot" data-reveal="zoom" data-parallax="0.05">
        <img
          src={A("dashboard.png")}
          alt="The HADES ground control screen: aerial search area with flight path and four located contacts, camera feed with a detection, contact list and mission timeline"
        />
      </figure>
      <dl className="shot-notes">
        <div data-reveal="left">
          <dt>One selection</dt>
          <dd>Click a survivor anywhere and the map, the video, and the list agree.</dd>
        </div>
        <div data-reveal>
          <dt>Honest uncertainty</dt>
          <dd>Every contact shows an uncertainty radius, not a false-precision pin.</dd>
        </div>
        <div data-reveal="right">
          <dt>Video never blocks</dt>
          <dd>Detection can fall behind under load. The feed and the operator do not.</dd>
        </div>
      </dl>
    </section>
  );
}

/* ---- why we built it ---- */
function Inspiration() {
  return (
    <section className="inspo">
      <div className="inspo-grid">
        <div className="inspo-copy" data-reveal="left">
          <h2 className="section-title">It started with our friends.</h2>
          <p>
            NCSSM is a residential school. Our classmates come from every corner of North
            Carolina, and when Hurricane Helene hit the western part of the state, some of their
            families and hometowns were cut off: no cell service, no power, roads gone.
          </p>
          <p>
            We kept asking the same question. When nothing works, how do you find people fast?
            We decided our answer would come from the skills we already had: drones, math, and
            code. HADES is that answer, built end to end at our desks and on our workbench.
          </p>
        </div>
        <figure className="inspo-photo" data-reveal="right" data-parallax="0.06">
          <img src={A("team.jpg")} alt="The HADES team at NCSSM with the Samsung hardware they won" />
          <figcaption>
            The team with the $10,000 in Samsung hardware we won through Samsung Solve for Tomorrow.
          </figcaption>
        </figure>
      </div>
    </section>
  );
}

/* ---- measured, not claimed ---- */
const METRICS = [
  { value: 0.85, fmt: (v: number) => v.toFixed(2), unit: "recall", note: "current model on the HERIDAL test split" },
  { value: 1.1, fmt: (v: number) => v.toFixed(1), unit: "meters median error", note: "localization against surveyed ground truth" },
  { value: 22.4, fmt: (v: number) => v.toFixed(1), unit: "ms glass to glass", note: "95th percentile in-app latency" },
  { value: 32, fmt: (v: number) => String(Math.round(v)), unit: "GB MacBook Air", note: "the whole system, offline, in the field" },
];
function MetricsSection() {
  return (
    <section className="section section-tight">
      <div className="section-head" data-reveal>
        <h2 className="section-title">Measured, not claimed.</h2>
        <p className="section-lede">
          Every number is validated against labeled ground truth and reported honestly,
          including where it falls short.
        </p>
      </div>
      <div className="metric-grid">
        {METRICS.map((m) => (
          <Metric key={m.unit} m={m} />
        ))}
      </div>
    </section>
  );
}
function Metric({ m }: { m: (typeof METRICS)[number] }) {
  const numRef = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = numRef.current;
    if (!el) return;
    const state = { v: 0 };
    const tween = gsap.to(state, {
      v: m.value,
      duration: 1.4,
      ease: "power4.out",
      scrollTrigger: { trigger: el, start: "top 85%", once: true },
      onUpdate: () => {
        el.textContent = m.fmt(state.v);
      },
    });
    return () => {
      tween.scrollTrigger?.kill();
      tween.kill();
    };
  }, [m]);
  return (
    <div className="metric" data-reveal>
      <span className="metric-num" ref={numRef}>
        0
      </span>
      <span className="metric-unit">{m.unit}</span>
      <span className="metric-note">{m.note}</span>
    </div>
  );
}

/* ---- closing ---- */
function Closing() {
  return (
    <section className="closing" data-reveal>
      <h2 className="closing-title">
        Built for the hour
        <br />
        after the storm.
      </h2>
      <a href="#/technology" className="pill pill-dark">
        Explore the technology <ArrowRight size={16} aria-hidden />
      </a>
    </section>
  );
}

/* =================================================================== TECHNOLOGY */
const FAQS = [
  { q: "Does it work without a connection?", a: "Yes, by design. Detect, localize, and display run entirely on the laptop with the network off. Map tiles are cached before a mission and nothing is sent to the cloud." },
  { q: "How accurate is the detection?", a: "The current model reaches 0.85 recall on the HERIDAL aerial search test split, measured against labeled ground truth, with its limits disclosed rather than hidden." },
  { q: "How close are the coordinates?", a: "Median localization error is about 1.1 meters against known ground truth in calibrated tests, and every contact carries an honest uncertainty radius instead of a false precision pin." },
  { q: "What does it run on?", a: "An Apple Silicon MacBook. The field machine is a 32 GB MacBook Air. Video plays at 30 frames a second, detection runs decoupled at 10 or better, and latency stays inside the 120 ms budget." },
  { q: "What is the aircraft?", a: "A 3D printed airframe over an F405 flight controller, 2306 motors, a DJI O4 Pro air unit for the video link, ELRS for control and telemetry, and a 6S battery. The hero model is the actual CAD assembly, and every part is listed below." },
  { q: "What happens when it finds someone?", a: "The detection becomes a tracked contact, gets confirmed across frames, and lands on the map with coordinates and an uncertainty radius. Every event is written to the mission log so a coordinator can task a ground team immediately." },
  { q: "Does it record or upload video?", a: "No model or tile fetch at runtime and no telemetry phoning home. The only optional network use is an operator triggered export after the mission, once connectivity returns." },
];
function Technology() {
  return (
    <main className="page">
      <section className="section page-hero">
        <h1 className="page-title" data-reveal>
          A search party
          <br />
          <span className="ink-faint">in a backpack.</span>
        </h1>
        <p className="section-lede" data-reveal>
          Two processes on one laptop: a Python detection service that captures, detects, and
          georeferences, and a coordinator interface, joined by two local sockets carrying
          frames on one side and detections with telemetry on the other, aligned frame for
          frame.
        </p>
      </section>

      <section className="section section-tight">
        <ol className="tech-list">
          {[
            {
              t: "Detection tuned for aerial search",
              p: "YOLO11s, fine tuned on the HERIDAL and SARD aerial search datasets and exported to Core ML for the Apple Neural Engine. Input resolution 960, chosen because recall peaks there on held out scenes while clearing the frame budget six times over.",
            },
            {
              t: "Coordinates with an honest radius",
              p: "Each detection is projected by monocular ray to ground intersection from the aircraft's position, altitude, and camera pose. Confirmed contacts are fused across frames with a Monte Carlo uncertainty estimate.",
            },
            {
              t: "Video that never blocks",
              p: "The feed decodes in hardware and always displays at full frame rate. Detection runs decoupled and drops to latest. Under load the boxes thin out; the video never stutters.",
            },
            {
              t: "Degrades gracefully",
              p: "Link loss, dropped frames, mid stream resolution changes, a throttled fanless laptop. The pipeline is built against all of them, and the field target is a stock MacBook Air with the network off.",
            },
          ].map((row, i) => (
            <li key={row.t} className="tech-row" data-reveal="up">
              <span className="tech-num">{String(i + 1).padStart(2, "0")}</span>
              <h3>{row.t}</h3>
              <p>{row.p}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="section section-tight">
        <div className="section-head" data-reveal>
          <h2 className="section-title">The aircraft, part by part.</h2>
          <p className="section-lede">
            The drone is built, not bought: every component below is on the workbench today, and
            the assembly you can spin on the home page is its actual CAD.
          </p>
        </div>
        <ul className="craft-list">
          {[
            { part: "3D printed airframe", role: "A monocoque printed in-house. It carries the whole stack and takes the crashes we learn from." },
            { part: "DJI O4 Pro air unit and camera", role: "The digital video link. It flies the survivor's eye view back to the laptop in real time." },
            { part: "F405 flight controller", role: "Keeps the aircraft level and streams attitude and GPS telemetry, which the localizer needs to turn pixels into coordinates." },
            { part: "ELRS receiver", role: "The control link. Long range, low latency, and a second telemetry path over serial." },
            { part: "2306 motors with 5 inch tri-blades", role: "Four of each. Sized for post-storm wind, not for racing." },
            { part: "6S battery", role: "Sets the flight time. Every choice upstream is weighed against the minutes of air time it costs." },
          ].map((c) => (
            <li key={c.part} className="craft-row" data-reveal="up">
              <strong>{c.part}</strong>
              <span>{c.role}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="section faq-section">
        <div className="faq-grid">
          <div>
            <h2 className="section-title" data-reveal>
              The hard questions.
            </h2>
            <Faq />
          </div>
          <figure className="faq-photo" data-reveal="right">
            <img src={A("drone-build-1.jpg")} alt="The assembled HADES airframe held in one hand" />
          </figure>
        </div>
      </section>
    </main>
  );
}

function Faq() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <ul className="faq" data-reveal>
      {FAQS.map((f, i) => {
        const isOpen = open === i;
        return (
          <li key={f.q}>
            <button type="button" onClick={() => setOpen(isOpen ? null : i)} aria-expanded={isOpen} className="faq-q">
              <span>{f.q}</span>
              {isOpen ? <Minus size={20} aria-hidden /> : <Plus size={20} aria-hidden />}
            </button>
            <div className="faq-a" style={{ gridTemplateRows: isOpen ? "1fr" : "0fr" }}>
              <div>
                <p>{f.a}</p>
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/* =================================================================== TEAM */
/* the student team: face-in-circle avatars + names. Update names here if fuller attribution is
   wanted. */
const TEAM = [
  { name: "Aarush Jain", img: "aarush.png" },
  { name: "Ryan Cannon", img: "ryan.png" },
  { name: "Soham Gaonkar", img: "soham.png" },
  { name: "Andy Lin", img: "andy.png" },
];
function Team() {
  return (
    <main className="page">
      <section className="section page-hero">
        <h1 className="page-title" data-reveal>
          Students who
          <br />
          <span className="ink-faint">ship hardware.</span>
        </h1>
        <p className="section-lede" data-reveal>
          HADES is built by a student team at the North Carolina School of Science and
          Mathematics: airframe, avionics, detection model, localization math, and the
          coordinator interface, end to end.
        </p>
      </section>

      <section className="section section-tight">
        <ul className="team-grid">
          {TEAM.map((m) => (
            <li key={m.name} className="team-member" data-reveal="up">
              <span className="team-avatar">
                <img src={A(`team/${m.img}`)} alt={m.name} loading="lazy" />
              </span>
              <strong className="team-name">{m.name}</strong>
            </li>
          ))}
        </ul>
      </section>

      <section className="section">
        <div className="section-head" data-reveal>
          <h2 className="section-title">Built, not bought.</h2>
          <p className="section-lede">
            The airframe is printed, the stack is soldered, and the code is ours. The assembly
            you can spin on the home page exists on a workbench.
          </p>
        </div>
        <div className="build-grid">
          <figure className="build-shot" data-reveal="left">
            <img src={A("drone-build-1.jpg")} alt="The assembled HADES airframe in hand" loading="lazy" />
            <figcaption>First assembly, motors mounted</figcaption>
          </figure>
          <figure className="build-shot" data-reveal="right">
            <img src={A("drone-build-2.jpg")} alt="The HADES workbench mid build" loading="lazy" />
            <figcaption>The bench, avionics and iteration</figcaption>
          </figure>
        </div>
      </section>

      <section className="section section-tight">
        <div className="section-head" data-reveal>
          <h2 className="section-title">Recognition.</h2>
        </div>
        <ul className="honor-list">
          {[
            { logo: "logos/samsung-sft.png", name: "Samsung Solve for Tomorrow", note: "national program, community problem engineering" },
            { logo: "logos/ncsef.png", name: "NC Science and Engineering Fair", note: "state level competition" },
            { logo: "logos/duke-pratt.svg", name: "Duke Pratt School of Engineering", note: "mentorship and review" },
            { logo: "logos/mit-solve.png", name: "MIT Solve", note: "global challenge community" },
            { logo: "logos/day-of-ai.png", name: "Day of AI", note: "AI education program" },
          ].map((h) => (
            <li key={h.name} className="honor-row" data-reveal>
              <img src={A(h.logo)} alt="" />
              <div>
                <strong>{h.name}</strong>
                <span>{h.note}</span>
              </div>
              <ArrowUpRight size={18} className="honor-arrow" aria-hidden />
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}

/* ---------------- footer ---------------- */
function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-panel" data-grow>
        <div className="footer-grid">
          <div data-reveal="left">
            <h2 className="footer-title">Find them faster.</h2>
            <p className="footer-sub">Between a demo and a fielded tool. Built for the hour after the storm.</p>
          </div>
          <div className="footer-col" data-reveal>
            <h3>Explore</h3>
            <a href="#/">Overview</a>
            <a href="#/technology">Technology</a>
            <a href="#/team">Team</a>
          </div>
          <div className="footer-col" data-reveal="right">
            <h3>Project</h3>
            <a href="https://github.com/ajain189/HADES" rel="noreferrer" target="_blank">
              GitHub
            </a>
            <a href="https://github.com/ajain189/HADES/tree/main/docs" rel="noreferrer" target="_blank">
              Documentation
            </a>
            <a href="https://www.ncssm.edu" rel="noreferrer" target="_blank">
              NCSSM
            </a>
          </div>
        </div>
        <div className="footer-base">
          <span>HADES Ground Control</span>
          <span>On device search and rescue</span>
        </div>
        <div className="footer-word" data-reveal="zoom" aria-hidden>
          HADES
        </div>
      </div>
    </footer>
  );
}
