# Motion Skills — Local Project Index (`iart-ai/motion-skills`)

Upstream source: https://github.com/iart-ai/motion-skills (MIT License)

All **56 skills** across the **19 packs** are installed locally under `motion-skills/skills/<skill-name>/SKILL.md` (with `references/`, `scripts/`, and `templates/` intact) so every Pottsfield Studio video and motion-graphics workflow in this repository can load them offline without external network calls.

## Core Skills Used for Pottsfield Studio Short-Form & Launch Films
- `motion-skills/skills/short-form-video/SKILL.md` — 9:16 retention engineering, Frame-0 hooks, pattern interrupts, 900×1400 universal safe box, seamless frame-matched loops.
- `motion-skills/skills/motion-art-direction/SKILL.md` — Motion-Language Spec, Hero/Support/Texture hierarchy, restraint pass, hold discipline.
- `motion-skills/skills/animation-principles/SKILL.md` — Easing curves, 1/3 Simultaneity & Distance rules, anticipation, follow-through.
- `motion-skills/skills/shot-composition/SKILL.md` — 3-layer parallax (`0.28x / 0.62x / 1.04x`), camera push/pan/whip-tilt/portal-dive grammar, safe margins.
- `motion-skills/skills/kinetic-typography/SKILL.md` — Baseline mask-up reveals, directional gouge wipes, tight display tracking.
- `motion-skills/skills/launch-video/SKILL.md` — Sound-leads-picture beat grid, drop-synced hero reveals, >=3s clean End-Card hold.
- `motion-skills/skills/javascript-animation/SKILL.md` — Continuous world-space blocking (`storyboard.md`), pure `f(t)` frame determinism, visual self-check loop.
- `motion-skills/skills/soundtrack/SKILL.md` — Whole-bar harmonic maps, non-startling groove entrances, pre-payoff silence breaks.

## Verification Scripts (`motion-skills/tools/verify/`)
- `bash motion-skills/tools/verify/probe-mp4.sh <video.mp4> [WxH] [fps]`
- `bash motion-skills/tools/verify/contact-sheet.sh <sheet.png> <frame1.png> ...`
