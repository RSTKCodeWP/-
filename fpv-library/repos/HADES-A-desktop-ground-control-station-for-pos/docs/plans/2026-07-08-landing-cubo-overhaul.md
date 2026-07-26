# Landing Cubo Overhaul + Speed — Implementation Plan

> **For Claude:** Use superpowers:executing-plans / subagent-driven-development to implement.

**Goal:** Make the HADES landing site fast and cohesive by matching Cubo Cruise's scroll feel —
a static floating-drone hero, smooth Lenis+GSAP scroll, once-only reveals with continuous
parallax, a "Frame to found" diagram, refined button micro-interactions, and a proper team page.

**Architecture:** Remove the two heavy hero paths (149-frame canvas scrubber + bundled three.js)
and replace with a single static high-res drone render on a matching background. Keep Lenis + GSAP
ScrollTrigger; retune to Cubo's exact values. Parallax (words lift, panel grows) is the cohesion
layer and tracks scroll both directions; fade-ins fire once.

**Tech Stack:** React + TS + Vite, Lenis, GSAP ScrollTrigger, CSS. (No three.js on the landing
after P1; no new animation library — GSAP+Lenis already cover Cubo's stack.)

---

## Research basis (done)
- Cubo teardown: floating device = static PNG on matching bg + `drop-shadow(0 24px 27px rgba(0,0,0,.25))`;
  Lenis smooth scroll; reveals fire ONCE (`opacity:0→1`, `y40`/`x±40`/`scale0.9`, dur 0.8s,
  ease `[0.28,0.41,0.56,1]`); hero words `translateY -` (lift) while device `translateY +` (lag);
  bottom panel `scale 1→0.9` clamped; buttons = arrow icon cross-fade on hover (no scale).
- Perf profile of live site: 154 network requests (149 = hero frames, ~11MB); per-scroll canvas
  repaint + a never-stopping `getBoundingClientRect` rAF; three.js `DroneHero` still imported.

## Locked decisions (from user)
- Hero = static high-res drone PNG (fastest + most Cubo). No 3D, no frame scrubber.
- Reveals = match Cubo: fire once + continuous parallax both directions.
- Frame to found → diagram.
- Team page: face-in-circle + names, isolated/cutout photos, remove group photo; organize loose files.

---

## PHASE 1 — SPEED

### Task 1.1: Remove the frame-scrubber + three.js hero paths
**Files:** Modify `ui/src/landing/LandingPage.tsx`; delete `ui/src/landing/VideoScrollHero.tsx`,
`ui/src/landing/DroneHero.tsx`; remove `public/landing/hero-frames/` + dist copies.
- Replace `<VideoScrollHero>`/`<DroneHero>` render with the static hero (Task 2.1).
- Drop the `HERO_MODE` switch + both imports.
- Verify: `grep -r "three\|VideoScrollHero\|DroneHero\|hero-frames" ui/src/landing` → clean.
- Verify: built landing bundle shrinks; network requests drop from 154 to < 15.

### Task 1.2: Prune unused motion machinery
**Files:** `ui/src/landing/motion.ts`, `landing.css`.
- Remove `--herofade` wiring if only the scrubber used it; keep Lenis + useReveals + useParallax.
- Confirm no per-frame rAF remains except Lenis's ticker.

**Verify P1:** local build, serve, Chrome trace at 1440px — scroll stays ~60fps, requests < 15,
bundle smaller. Commit: `perf(landing): drop frame-scrubber and three.js hero`.

---

## PHASE 2 — CUBO FEEL

### Task 2.1: Static floating-drone hero
**Files:** render a high-res transparent-bg drone PNG from `drone.glb` (headless Blender or an
existing render) → `public/landing/drone-hero.png`; `LandingPage.tsx` hero; `landing.css`.
- Centered, matching bg, `drop-shadow(0 24px 27px rgba(0,0,0,.25))`, responsive max box.
- Scroll parallax: drone `translateY +`, hero words/buttons `translateY -` (lift into next section),
  smoothed (GSAP scrub ~1 or a lerped setter).

### Task 2.2: Retune reveals to Cubo + audit coverage
**Files:** `motion.ts`, `LandingPage.tsx`.
- Reveal FROM/TO to `y40`/`x±40`/`scale0.9`→0, `opacity 0→1`, dur 0.8, ease `[0.28,0.41,0.56,1]`,
  `once:true`. Add `data-reveal` to EVERY section currently missing one.

### Task 2.3: Bottom black panel grow-on-scroll
**Files:** `landing.css`, `motion.ts`/footer.
- Scroll-linked `scale 1 → 0.9` clamped on the footer panel wrapper (continuous, both directions).

### Task 2.4: "Frame to found" → diagram
**Files:** `LandingPage.tsx` (`PipelineRail` → a flow diagram), `landing.css`.
- Replace 5 cards with a connected pipeline diagram (Detect→Localize→Confirm→Coordinate + Offline).

### Task 2.5: Button/link micro-interactions
**Files:** `landing.css`, relevant components.
- Arrow cross-fade/slide on hover for pills/links; refine nav + faq + footer link interactions.

**Verify P2:** browser review at desktop+mobile, both motion modes; compare feel to Cubo.
Commit per task. Then push (triggers Vercel deploy hook).

---

## PHASE 3 — TEAM PAGE (assets in hand)
Photos: `Aarush_Pic.png`, `Ryan_pic.png`, `Soham_Pic.png`, `andy_pic.png` (currently repo root).
- Task 3.1: Cutout/isolate each photo (bg-remove), normalize to square, → `public/landing/team/`.
- Task 3.2: Team page = face-in-circle grid + names under "Students who ship hardware";
  remove the `team.jpg` group photo.
- Task 3.3: Organize loose root files (PNGs, `HADES_logo.png`, strays) into proper dirs; commit.

## Review
(fill in as phases complete)
