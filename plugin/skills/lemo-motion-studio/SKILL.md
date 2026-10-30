---
name: lemo-motion-studio
description: Orchestrate the repository's Motion Graphics & Animation skills (animation-principles, motion-art-direction, kinetic-typography, arabic-motion-graphics, motion-effects, launch-video, vox-explainer, javascript-animation, chart-animation, animated-infographic, explainer-video, diagram-animation, isometric-animation, whiteboard-animation, logo-animation, motion-background, svg-animation, lottie-animation, threejs-animation, shader-glsl, particle-system, remotion-video, manim) and render finished MP4 videos directly through Lemo-Opuscar's deterministic pipeline (core/render/video.mjs + core/audio/sfx.py + core/render/mux.sh) or Remotion/Manim. Use whenever designing custom motion graphics, animated promos, Arabic RTL reels, kinetic typography, UI/product animations, animated charts, or 2D/3D animations in this repository.
version: 1.0.0
---

# Lemo Motion Studio — Motion Graphics & Animation Orchestrator

Use this skill when designing **custom motion graphics or animations** beyond (or combined with) Lemo-Opuscar's 59 library styles. It routes your task to the right craft skills in `plugin/skills/` and bridges them directly into Lemo-Opuscar's zero-After-Effects rendering & audio pipeline (`core/`).

---

## 1. Skill Routing Matrix — Read Only What the Video Needs

Always pair **one foundation craft skill** (`animation-principles` or `motion-art-direction`) with the **domain skill(s)** matching the user's brief:

| Video / Animation Goal | Skills to Read (`plugin/skills/<name>/SKILL.md`) |
|---|---|
| **Any motion graphic** (timing, easing, weight, hierarchy) | `animation-principles` + `motion-art-direction` + `shot-composition` |
| **Arabic video / RTL Reel / Explainer / Promo (عربي)** | `arabic-motion-graphics` (ALWAYS read `plugin/skills/arabic-motion-graphics/references/rtl-arabic.md` before animating Arabic text!) |
| **Kinetic typography, title cards, captions, lyrics** | `kinetic-typography` + `beat-sync-editing` |
| **SaaS / App launch film, UI motion, product showcase** | `launch-video` + `motion-effects` + `color-motion` |
| **Vox-style documentary / collage explainer** | `vox-explainer` + `explainer-video` |
| **Narrated explainer, technical flow, architecture** | `explainer-video` + `diagram-animation` (or `isometric-animation` / `whiteboard-animation`) |
| **Animated charts, KPIs, bar-chart race, infographics** | `chart-animation` + `animated-infographic` |
| **Logo reveal, brand sting, intro/outro** | `logo-animation` + `motion-background` |
| **Pure 2D Canvas character / hand-drawn / procedural film** | `javascript-animation` + `soundtrack` |
| **SVG stroke draw-on, morphing, or Lottie JSON** | `svg-animation` / `lottie-animation` / `gsap-web` |
| **3D camera scenes, shaders, GPU particles** | `threejs-animation` + `shader-glsl` + `particle-system` |
| **Music-locked cuts, promos & showreels** | `beat-sync-editing` + `soundtrack` |
| **Math, physics, algorithms (3Blue1Brown style)** | `manim` |
| **Multi-scene React programmatic video** | `remotion-video` (and `arabic-motion-graphics/templates/remotion` for RTL) |

---

## 2. Choosing the Render Engine Inside This Repo

### Path A — Lemo-Opuscar Native Engine (Default, Fastest, Zero Extra License)
Best for **90% of motion graphics**: HTML5 + CSS/SVG + Canvas 2D + Three.js (`node_modules/three` is already in the repo root) rendered deterministically via headless Chromium + FFmpeg + procedural foley/music (`core/`).

1. Work in `films/<slug>/` (gitignored workspace folder for user videos).
2. Copy `plugin/skills/lemo-motion-studio/templates/motion-starter.html` to `films/<slug>/index.html`.
3. Expose Lemo-Opuscar's frame contract **plus** `window.seek` so recipes from `motion-effects` and `javascript-animation` work unmodified:
   ```js
   window.DUR = 18.0;                  // total duration in seconds
   window.EV  = [                      // frame-accurate audio cues for mix.py / sfx.py
     { t: 0.00, type: 'whoosh' },
     { t: 0.45, type: 'hit' },
   ];
   window.render = (t) => { /* pure deterministic function of time t (seconds) */ };
   window.seek   = window.render;      // alias for seek(t)-based motion skills
   await document.fonts.ready;
   window.READY  = true;               // set ONLY after fonts & local assets finish loading
   ```
4. **Verify frames visually before full render** (mandatory):
   ```sh
   # Landscape 16:9 (1920x1080 default)
   node core/render/still.mjs films/<slug> 0.5 2.0 4.5 --range 0:18:1.5
   # Vertical 9:16 Reels / Shorts / TikTok
   node core/render/still.mjs films/<slug> 0.5 2.0 4.5 --size 1080x1920
   ```
   Inspect the generated JPEGs in `films/<slug>/stills/` with `read_file` to verify layout, contrast, Arabic shaping, and margins.
5. **Render video + synthesize sound + master to −14 LUFS**:
   ```sh
   node core/render/events.mjs films/<slug>
   node core/render/video.mjs films/<slug> --fps 30 --workers 3 --out films/<slug>/out/video.mp4
   # (Add --size 1080x1920 for vertical Reels/Shorts, or --size 1080x1080 for square)
   .venv/bin/python films/<slug>/mix.py
   sh core/render/mux.sh films/<slug>/out/video.mp4 films/<slug>/out/mix.wav films/<slug>/<slug>.mp4 30 0
   ```
   *(Pass `0` as the 5th argument to `mux.sh` for crisp vector/UI motion graphics without film grain, or omit for subtle organic grain.)*

### Path B — Remotion Engine (React Component Compositions)
Use when the user explicitly asks for a **Remotion** project (`remotion-video` / `arabic-motion-graphics` templates) or wants reusable React TSX compositions (`<Sequence>`, `<TransitionSeries>`, `spring()`). Build inside `films/<slug>/` with its own `package.json`.

### Path C — Manim Engine (Mathematical & Algorithmic Animations)
Use when the user asks for equation morphing, LaTeX proofs, coordinate-system transformations, or 3Blue1Brown-style animations (`manim` skill). Build inside `films/<slug>/` with a dedicated Python venv.

---

## 3. Non-Negotiable Motion Craft Rules

1. **Never use `linear` easing for discrete UI/type motion.**
   - Entrances decelerate (`eo` / `cubic-bezier(0.16, 1, 0.3, 1)` or `spring(t, 7, 0.35)` from `/core/lib.js`).
   - Exits accelerate (`ei` / `cubic-bezier(0.7, 0, 0.84, 0)`).
   - Repositioning on screen uses asymmetric ease-in-out (`cubic-bezier(0.65, 0, 0.35, 1)`).
2. **Three layers of motion on every shot:**
   - **Hero (Primary):** the single focal action the viewer's eye tracks.
   - **Support (Secondary):** staggered labels, subtle shadow/border response, counter roll.
   - **Texture (Ambient):** slow background drift, subtle grid breathing, or light sweep — **no dead frozen frames** except intentional dramatic holds.
3. **Arabic RTL Integrity (when designing in Arabic):**
   - Set `dir="rtl"` and `lang="ar"` on DOM containers; on Canvas 2D set `ctx.direction = 'rtl'` and `ctx.textAlign = 'right'`.
   - **NEVER split Arabic words into per-letter elements** — it breaks cursive letter joining (`بـسـم` -> `ب س م`). Always animate **by word**, **by line**, or via a **right-to-left `clip-path` wipe** on the intact word.
   - **NEVER add positive `letter-spacing`** on Arabic text (it severs connected glyphs).
   - Wrap embedded English brand names, URLs, `@handles`, or LTR numbers in `<bdi dir="ltr">...</bdi>`.
   - Self-host OFL Arabic fonts (e.g., **Cairo**, **Readex Pro**, **IBM Plex Sans Arabic**, **Tajawal**, **Alexandria**) in `films/<slug>/fonts/` and await `document.fonts.load(...)` before `window.READY = true`.
4. **Deterministic clock only:**
   - Never use unseeded `Math.random()`, `Date.now()`, CSS `@keyframes` running on wall-clock time, or state mutated from the previous frame inside `window.render(t)`. Parallel workers render segments out of order! Use `mulberry(seed)` and `hash(n)` from `/core/lib.js`.
