---
name: open-media-sourcing
description: Search, download, audit, and license-log real photographs, screenshots, documents, and archive footage from Wikimedia Commons, Internet Archive, NASA, and open-web search instead of drawing empty placeholder wireframes in code. Use whenever a motion-graphics, documentary, or viral reel project needs real visual assets, UI screenshots, B-roll, or archival textures.
---

# Open Media Sourcing & Asset Audit

Never ship a motion-graphics or explainer film made purely of empty code-drawn boxes when the story calls for **real screenshots, photographs, archival documents, or textured B-roll**.

## 1. Sourcing Priority
1. **User-supplied assets first** (official logos, product/gameplay screenshots, recordings). Never redraw an official logo or fake a product screenshot when the real file exists.
2. **Open-web & public-archive search**:
   - Use built-in `image_search` (when available in the agent host) for real UI screenshots, app store pages, product comparisons, and photographic plates.
   - Use `scripts/footage.py` (standard-library Python CLI) to query **Wikimedia Commons**, **Internet Archive**, and **NASA** with automatic license and attribution logging (`SOURCES.jsonl` → `SOURCES.md`):
     ```bash
     python3 plugin/skills/open-media-sourcing/scripts/footage.py search commons "medieval manuscript" --type image
     python3 plugin/skills/open-media-sourcing/scripts/footage.py search archive "blacksmith forge"
     python3 plugin/skills/open-media-sourcing/scripts/footage.py fetch commons:"File:Example.jpg" --name plate1
     python3 plugin/skills/open-media-sourcing/scripts/footage.py md
     ```
3. **Bespoke art plates** (`generate_image` when available) only for stylized fictional worlds, atmospheric backdrops, or textures—never to fake real historical evidence or real third-party interfaces.

## 2. Mandatory Visual Asset Audit (Contact Sheet Gate)
Before compositing any downloaded asset into a film:
1. Check pixel dimensions (`>= 600px` on the long edge for cards/insets; `>= 1080px` for full-bleed plates; never upscale beyond `1.5x` modern / `2.5x` archival).
2. Tile candidate images onto an audit contact sheet with index numbers and resolutions, and **inspect the sheet visually**:
   - Reject stock-watermarked thumbnails (`Dreamstime`, `Shutterstock`, `Getty`, `iStock`, `Alamy` diagonal watermarks).
   - Reject blurry `150x150` thumbnails or unrelated blog header banners.
   - Verify crops keep key UI elements (buttons, counters, headlines, faces) unobstructed.

## 3. Compositing Real Assets into Motion Graphics
- **Never float a raw screenshot on flat solid `#000000` black.**
  - Build a **full-bleed depth backdrop** (blurred, color-graded mosaic or environment plate moving at `0.3x` parallax + subtle film grain + vignette).
  - Frame foreground screenshots as **physical mixed-media cards**: rounded or torn edges, multi-pass elevation drop shadow (`blur 40px`), subtle glass specular sheen, and a crisp `JetBrains Mono` source/evidence chip (`PLAY STORE · TOP CHARTS`, `AD VS GAMEPLAY`).
  - Direct the viewer's eye inside dense screenshots using **Visual Investigation moves**: clockwise-drawn highlight circles, ×3–×4 sniper-loupe pixel magnifiers, and kinetic camera push-ins.
