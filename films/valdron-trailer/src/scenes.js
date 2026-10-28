// scenes.js — All 21 handcrafted vertical pixel-art shots + model sheet (?sheet=1)
import {
  W, H, C, T, LUT, LIGHT_WARM, LIGHT_COOL, LIGHT_ICHOR,
  bayer4, bayer8, hash2, noise1, noise2, clamp, lerp, seg, ss, eo, eio, mod, stepFade,
} from './px.js';
import {
  drawKnight, drawKnightVisorClose, drawReveler,
  drawAlleyMutant, drawCrookedWatcher, drawMillBeast,
} from './chars.js';
import { drawGothicText } from './font.js';

// Helper: flickering torch / brazier fire with 12-fps pixel tongues + warm index-stepped halo
function drawTorch(fb, x, y, size, t) {
  const t12 = Math.floor(t * 12) / 12;
  const flk = Math.sin(t12 * 9.1 + x * 0.7) * 2;
  fb.lightHalo(x, y - size * 0.6, size * 1.4, size * 5.2 + flk, LIGHT_WARM, true);
  // Iron bracket / brazier bowl
  fb.poly([
    [x - size * 0.9, y], [x + size * 0.9, y],
    [x + size * 0.5, y + size * 0.8], [x - size * 0.5, y + size * 0.8],
  ], C.void);
  // Stepped pixel flame tongues
  for (let k = -2; k <= 2; k++) {
    const fh = size * (1.5 - Math.abs(k) * 0.25) + Math.sin(t12 * 13 + k * 2.3 + x) * size * 0.35;
    const fx = x + k * size * 0.3;
    fb.capsule(fx, y - 1, fx + flk * 0.3, y - fh, Math.max(1, size * 0.28), Math.abs(k) <= 1 ? C.gold : C.flame);
  }
  fb.disc(x, y - size * 0.35, Math.max(1, size * 0.35), C.spark);
}

// Helper: rising ash or ember motes
function drawMotes(fb, count, t, colA, colB, dirY = -18, windX = 6, seed = 17) {
  for (let i = 0; i < count; i++) {
    const x0 = hash2(i, 1, seed) * W;
    const y0 = hash2(i, 2, seed) * H;
    const sp = 0.6 + hash2(i, 3, seed) * 0.9;
    const x = mod(Math.round(x0 + t * windX * sp + Math.sin(t * 1.8 + i) * 5), W);
    const y = mod(Math.round(y0 + t * dirY * sp), H);
    const c = hash2(i, 4, seed) > 0.45 ? colA : colB;
    fb.px(x, y, c);
    if (hash2(i, 5, seed) > 0.82) fb.px(x + 1, y, c);
  }
}

// Helper: Bayer checker light shaft (25% edge, 50% core per pixel-art grammar)
function drawMoonShaft(fb, xTop, wTop, xBot, wBot, y0, y1, table = LIGHT_COOL) {
  for (let y = Math.max(0, y0); y < Math.min(H, y1); y++) {
    const u = (y - y0) / Math.max(1, y1 - y0);
    const cx = lerp(xTop, xBot, u);
    const hw = lerp(wTop, wBot, u) * 0.5;
    const xa = Math.max(0, Math.round(cx - hw));
    const xb = Math.min(W - 1, Math.round(cx + hw));
    for (let x = xa; x <= xb; x++) {
      const edge = 1 - Math.abs(x - cx) / Math.max(1, hw);
      const b = bayer4(x, y);
      if ((edge > 0.35 && ((x + y) & 1) === 0) || (edge <= 0.35 && b < 0.25)) {
        fb.d[y * W + x] = table[fb.d[y * W + x]];
      }
    }
  }
}

// Helper: Undulating mossy dark-fantasy valley floor + winding dark path (no flat horizon line!)
function drawMossyValley(fb, yHorizon, seed = 77) {
  for (let x = 0; x < W; x++) {
    const hill = Math.round(
      Math.sin(x * 0.032 + seed) * 9 +
      (noise1(x * 0.07, seed + 3) - 0.5) * 14
    );
    const yStart = Math.max(0, yHorizon + hill);
    for (let y = yStart; y < H; y++) {
      const u = (y - yStart) / Math.max(1, H - yStart);
      const pathCenter = 135 + Math.sin(u * 4.2 + seed) * (12 + u * 26);
      const pathW = 3 + u * 16;
      const distPath = Math.abs(x - pathCenter);
      const tuft = noise2(x * 0.14, y * 0.16, seed + 9);
      let c;
      if (distPath < pathW) {
        c = bayer4(x, y) < (distPath / pathW) ? C.moss1 : C.slate0;
      } else {
        const shade = clamp((1 - u * 0.72) * 0.65 + tuft * 0.45, 0, 0.99);
        const pal = [C.moss0, C.moss1, C.moss2, C.moss3, C.moss4];
        const idx = Math.floor(shade * (pal.length - 1));
        const f = shade * (pal.length - 1) - idx;
        c = bayer4(x, y) < f ? pal[idx + 1] : pal[idx];
      }
      fb.px(x, y, c);
    }
  }
}

// —— SHOT 01 (0.0–5.8s): Smoke, battlements & burning Loris standard ——
export function shot01(fb, t) {
  const u = seg(t, 0.0, 5.8);
  const camY = Math.round(lerp(0, 74, eio(u))); // integer vertical tilt down

  fb.vgrad(0, H, [C.void, C.abyss, C.wood0, C.wood1, C.rustW]);
  fb.stars(220 - camY, 55, 101, 0, camY * 0.3, t);

  // Distant fortress towers in smoke
  fb.gothicCitadel(72, 330 - Math.round(camY * 0.6), 75, 130, C.void, C.wood0, C.amber, C.flame, 12);
  fb.fogLayer(170 - camY * 0.5, 340 - camY * 0.5, t * 9, 0.85, C.wood0, C.wood2, 19);

  // Foreground Valdron crenellated battlements rising into frame as camera tilts down
  const wallY = 355 - camY;
  fb.rect(0, wallY, W, H - wallY, C.void);
  for (let mx = 6; mx < W; mx += 34) {
    fb.rect(mx, wallY - 22, 20, 22, C.slate0);
    fb.vline(mx, wallY - 22, wallY, C.amber);
    fb.hline(mx, mx + 19, wallY - 22, C.rustW);
  }
  // Stone masonry courses
  for (let y = wallY + 8; y < H; y += 16) {
    fb.hline(0, W - 1, y, C.slate0);
    for (let x = (y % 32 === 0 ? 12 : 28); x < W; x += 32) fb.vline(x, y, y + 16, C.slate0);
  }

  // Tall iron pike holding a torn, burning Loris banner
  const px = 176, py = wallY - 128;
  fb.vline(px, py, wallY, C.stone1);
  fb.vline(px - 1, py, wallY, C.amber);
  const t12 = Math.floor(t * 12) / 12;
  const snap = Math.sin(t12 * 7.5) * 6;
  fb.poly([
    [px, py + 8],
    [px + 48 + snap, py + 18],
    [px + 40 + snap * 1.3, py + 66],
    [px + 18 + snap * 0.6, py + 54],
    [px, py + 82],
  ], C.blood1);
  // Silver Loris crescent-star emblem half-charred
  fb.disc(px + 20 + snap * 0.4, py + 36, 7, C.steel);
  fb.disc(px + 23 + snap * 0.4, py + 35, 5, C.blood1);
  // Flames consuming the lower edge of the Loris banner
  drawTorch(fb, px + 26 + snap * 0.8, py + 62, 7, t);
  drawTorch(fb, 46, wallY - 26, 6, t + 1.1);

  drawMotes(fb, 65, t, C.gold, C.flame, -28, 9, 3);
  return u < 0.12 ? stepFade(LUT.feast, Math.round((1 - u / 0.12) * 3)) : LUT.feast;
}

// —— SHOT 02 (5.8–11.7s): Valdron courtyard victory feast + forgotten Loris helm in mud ——
export function shot02(fb, t) {
  const u = seg(t, 5.8, 11.7);
  const camX = Math.round(lerp(0, 42, u)); // slow integer track right

  fb.vgrad(0, 290, [C.void, C.abyss, C.wood0, C.wood1]);
  // Courtyard arched stone colonnade (0.6x parallax)
  const bgX = Math.round(camX * 0.6);
  fb.rect(0, 145, W, 175, C.slate0);
  for (let k = -1; k < 6; k++) {
    const ax = k * 64 - (bgX % 64) + 18;
    fb.rect(ax - 8, 165, 16, 155, C.stone0);
    fb.ellipse(ax + 24, 185, 22, 26, C.void);
    fb.rect(ax + 2, 185, 44, 135, C.void);
    // Warm window glow higher up
    fb.rect(ax - 3, 122, 6, 14, C.amber);
  }

  // Cobblestone feast ground
  fb.vgrad(295, H, [C.wood1, C.wood0, C.void, C.moss0]);

  // Roaring courtyard braziers & banquet trestle tables (1.0x camera)
  drawTorch(fb, 68 - camX, 258, 9, t);
  drawTorch(fb, 206 - camX, 258, 9, t + 0.7);

  // Banquet table
  const tx = 75 - camX;
  fb.rect(tx, 292, 145, 7, C.wood2);
  fb.hline(tx, tx + 145, 292, C.amber);
  fb.rect(tx + 14, 299, 6, 22, C.wood1);
  fb.rect(tx + 124, 299, 6, 22, C.wood1);
  // Goblets & pitchers
  for (const gx of [92, 118, 154, 182, 202]) {
    fb.rect(gx - camX, 286, 4, 6, C.gold);
  }

  // Reveling soldiers toasting
  drawReveler(fb, 54 - camX, 320, 1.05, 0.1, t);
  drawReveler(fb, 108 - camX, 318, 1.1, 1.4, t);
  drawReveler(fb, 146 - camX, 316, 1.08, 2.7, t);
  drawReveler(fb, 192 - camX, 321, 1.12, 3.9, t);
  drawReveler(fb, 238 - camX, 323, 1.05, 5.1, t);

  // Foreground ditch (1.35x parallax): cold mud & cracked Loris helmet with broken crescent
  const fgX = Math.round(camX * 1.35);
  fb.poly([[0, 368], [W, 356], [W, H], [0, H]], C.void);
  const hx = 198 - fgX, hy = 386;
  fb.ellipse(hx, hy, 16, 12, C.stone0);
  fb.line(hx - 12, hy - 5, hx + 8, hy - 8, C.stone2, 2);
  // Crack & dark blood stain on the fallen Loris helm
  fb.line(hx - 2, hy - 11, hx + 3, hy + 4, C.void, 2);
  fb.ellipse(hx + 6, hy + 10, 18, 4, C.blood0);
  fb.ellipse(hx + 4, hy + 9, 10, 2, C.blood1);

  drawMotes(fb, 40, t, C.gold, C.amber, -20, 5, 8);
  return LUT.feast;
}

// —— SHOT 03 (11.7–16.7s): The Knight sets down his cup and walks out the postern arch ——
export function shot03(fb, t) {
  const u = seg(t, 11.7, 16.7);
  const walkU = seg(t, 12.9, 16.7);
  const camX = Math.round(lerp(0, 36, eio(walkU)));

  // Split staging: warm archway on far left, cold midnight sky opening on right!
  fb.vgrad(0, 330, [C.abyss, C.night, C.indigo, C.slate0]);
  fb.stars(210, 45, 303, camX * 0.2, 0, t);

  // Fortress postern wall & arched exit
  fb.rect(0, 80, 152 - camX, 265, C.slate0);
  fb.rect(0, 140, 58 - camX, 195, C.wood1); // warm hall interior behind him
  drawTorch(fb, 34 - camX, 206, 8, t);

  // Stone ledge where he leaves the untouched cup
  const lx = 86 - camX;
  fb.rect(lx - 12, 278, 26, 56, C.stone0);
  fb.hline(lx - 13, lx + 14, 278, C.stone2);
  if (t >= 12.6) {
    fb.rect(lx + 2, 271, 5, 7, C.amber);
    fb.hline(lx + 1, lx + 7, 271, C.gold);
  }

  // Rolling mossy hill outside the wall on the right
  fb.poly([
    [130 - camX, 332], [W, 314], [W, H], [0, H],
  ], C.moss0);
  fb.fogLayer(285, 355, t * 8 + camX, 0.55, C.night, C.cdeep, 31);

  // The Knight: lowers cup (11.7–12.9s), then walks steadily out into the night (12.9–16.7s)
  const kx = Math.round(lerp(76, 196, eio(walkU))) - camX;
  const ky = Math.round(lerp(336, 330, walkU));
  drawKnight(fb, kx, ky, {
    scale: 1.55,
    facing: 1,
    pose: t < 12.9 ? 'cup' : 'walk',
    prog: seg(t, 11.7, 12.9),
    t,
    rimCol: kx < 115 ? C.flame : C.cyan,
  });

  return LUT.full;
}

// —— SHOT 04 (16.7–20.0s): Outside the walls beneath a veiled moon — sword planted, visor nods in sleep ——
export function shot04(fb, t) {
  const u = seg(t, 16.7, 20.0);
  // Veiled nocturnal moorland sky (Reference 2 grammar)
  fb.vgrad(0, 260, [C.void, C.abyss, C.night, C.slate0]);
  fb.stars(160, 48, 404, 0, 0, t);
  fb.moon(178, 108, 22, 'veiled');
  fb.fogLayer(86, 142, t * 5, 0.85, C.void, C.slate0, 44); // dark clouds veiling moon

  // Distant mossy hills
  fb.cragSlope(-1, 190, 330, 125, C.void, C.moss1, C.moss2, 41);
  fb.cragSlope(1, 205, 340, 140, C.void, C.moss1, C.moss2, 42);

  // Foreground grassy ridge & boulder
  fb.poly([[0, 312], [118, 294], [W, 326], [W, H], [0, H]], C.moss0);
  for (let x = 0; x < W; x += 3) {
    const gy = Math.round(lerp(312, 296, clamp(x / 120, 0, 1)) + noise1(x * 0.1, 9) * 8);
    const sway = Math.round(Math.sin(t * 2.1 + x * 0.2) * 1.5);
    fb.line(x, gy + 8, x + sway, gy, x % 6 === 0 ? C.moss3 : C.moss2, 1);
  }
  // Craggy resting boulder on left
  fb.poly([[18, 338], [42, 268], [88, 282], [104, 342]], C.slate0);
  fb.poly([[42, 268], [76, 276], [66, 312], [34, 308]], C.stone0);

  // Planted greatsword in the turf (plunged at 17.4s)
  const plunge = ss(17.1, 17.45, t);
  const sy = Math.round(lerp(248, 272, plunge));
  fb.vline(154, sy, 332, C.stone3);
  fb.vline(153, sy, 332, C.silver);
  fb.hline(145, 163, sy + 14, C.stone2);
  fb.disc(154, sy - 2, 2.5, C.steel);

  // Sleeping Knight leaning against the boulder
  drawKnight(fb, 104, 340, {
    scale: 1.75,
    facing: 1,
    pose: 'sleep',
    t,
    rimCol: C.stone2,
  });

  return LUT.full;
}

// —— SHOT 05 (20.0–26.7s): NATIVE MOVE — Silent Curse Flare & Palette Collapse Across Valdron ——
export function shot05(fb, t) {
  // Wide locked frame: sleeping Knight foreground left, Valdron's lit skyline far behind
  const wave = seg(t, 23.2, 26.3); // curse shockwave propagation 0 -> 1
  const flare = seg(t, 22.65, 23.25) * (1 - seg(t, 25.4, 26.6) * 0.5);

  fb.vgrad(0, H, [C.void, C.abyss, C.night, C.indigo, C.moss0, C.void]);
  fb.stars(200, 70, 505, 0, 0, t);

  // Distant ruined Loris spire on the far right horizon where the surviving sorcerer casts the curse
  const sx = 224, sy = 214;
  fb.poly([[192, 266], [224, 198], [256, 266]], C.void);
  fb.vline(sx, 174, 214, C.slate0);

  // Rolling dark moorland ridge beneath Valdron's distant walls
  fb.poly([[0, 250], [108, 244], [206, 258], [W, 254], [W, 355], [0, 355]], C.abyss);

  // Distant Kingdom of Valdron skyline (center-left) with warm feast windows that snuff out as wave passes!
  fb.gothicCitadel(108, 248, 86, 118, C.void, C.slate0, C.stone0, T, 55);
  fb.rect(36, 236, 144, 18, C.slate0);
  for (let i = 0; i < 18; i++) {
    const wx = 44 + i * 7.6;
    const wy = 226 + (i % 3) * 6 - (i > 6 && i < 12 ? 22 : 0);
    const dist = Math.hypot(wx - sx, wy - 176) / 210;
    const alive = wave < dist;
    if (alive) {
      fb.rect(wx, wy, 2, 3, i % 2 === 0 ? C.gold : C.flame);
      if (i % 4 === 0) fb.lightHalo(wx + 1, wy + 1, 2, 9, LIGHT_WARM, false);
    } else if (wave - dist < 0.10) {
      fb.rect(wx, wy, 2, 3, C.ichor3);
    } else {
      fb.rect(wx, wy, 2, 3, C.slate1);
    }
  }

  // At 22.7s (inside Real Silence #1): piercing emerald curse-star & organic Bayer-dithered mist shockwave
  if (t >= 22.65) {
    fb.lightHalo(sx, 176, 4 + flare * 7, 18 + flare * 30, LIGHT_ICHOR, true);
    fb.line(sx - 18 * flare, 176, sx + 18 * flare, 176, C.ichor4, 1);
    fb.line(sx, 176 - 24 * flare, sx, 176 + 24 * flare, C.ichor4, 1);
    fb.disc(sx, 176, 2.2, C.ichor4);
  }
  if (wave > 0 && wave < 1) {
    const rRing = wave * 245;
    for (let y = 30; y < 340; y++) {
      for (let x = 0; x < W; x++) {
        const warp = (noise2(x * 0.05, y * 0.05, 59) - 0.5) * 22;
        const d = Math.abs(Math.hypot(x - sx, y - 176) + warp - rRing);
        if (d < 22 && bayer8(x, y) < (1 - d / 22) * 0.68) {
          fb.d[y * W + x] = LIGHT_ICHOR[fb.d[y * W + x]];
        }
      }
    }
  }

  // Midground valley mist turning green-tinted
  fb.fogLayer(236, 305, t * 4, 0.7, C.night, wave > 0.4 ? C.ichor1 : C.slate0, 58);

  // Foreground ridge & sleeping Knight silhouette
  fb.poly([[0, 338], [135, 326], [W, 362], [W, H], [0, H]], C.void);
  fb.poly([[6, 350], [34, 298], [72, 312], [84, 355]], C.slate0);
  fb.vline(118, 294, 342, C.stone1);
  fb.hline(112, 124, 304, C.stone1);
  drawKnight(fb, 76, 352, { scale: 1.35, facing: 1, pose: 'sleep', t, rimCol: wave > 0.5 ? C.ichor2 : C.stone1 });

  // Step palette down 5 integer levels as the curse finishes
  const stepIdx = Math.min(4, Math.floor(wave * 4.99));
  return LUT.collapse[stepIdx];
}

// —— SHOT 06 (26.7–32.5s): Viscous green drop on gauntlet -> Knight wakes to ash & silence ——
export function shot06(fb, t) {
  fb.vgrad(0, 310, [C.void, C.abyss, C.cdeep, C.slate0]);
  fb.fogLayer(160, 320, t * 11, 0.85, C.slate0, C.cteal, 61);

  if (t < 28.15) {
    // Tight Macro Insert (26.7–28.4s): overhanging grass blade dripping viscous green ichor onto steel gauntlet
    fb.poly([[0, 310], [W, 290], [W, H], [0, H]], C.moss0);
    // Steel gauntlet fingers resting on ground
    fb.ellipse(136, 326, 58, 24, C.stone0);
    for (let k = 0; k < 4; k++) {
      fb.capsule(95 + k * 22, 318, 108 + k * 22, 344, 8, C.stone1);
      fb.line(95 + k * 22, 318, 108 + k * 22, 340, C.steel, 2);
    }
    // Overhanging grass blade from upper left
    fb.poly([[0, 96], [142, 168], [136, 176], [0, 124]], C.moss2);
    fb.line(0, 96, 142, 168, C.ichor2, 2);

    // Viscous green drop swelling (26.7–27.4s), falling (27.4–27.65s), splattering on steel (27.65s+)
    if (t < 27.40) {
      const swell = seg(t, 26.7, 27.4);
      fb.disc(140, 174 + swell * 5, 3 + swell * 3.5, C.ichor3);
      fb.px(139, 174 + Math.round(swell * 5), C.ichor4);
    } else if (t < 27.65) {
      const fall = seg(t, 27.40, 27.65);
      const dy = lerp(180, 314, fall * fall);
      fb.capsule(140, dy - 8, 140, dy, 3, C.ichor4);
    } else {
      // Glowing curse puddle spreading on the steel knuckle
      const sp = seg(t, 27.65, 28.4);
      fb.lightHalo(140, 316, 4, 24, LIGHT_ICHOR, true);
      fb.ellipse(140, 316, 10 + sp * 7, 4 + sp * 2, C.ichor3);
      fb.ellipse(140, 316, 5 + sp * 3, 2, C.ichor4);
    }
  } else {
    // Medium shot: Knight rises, gripping greatsword, scanning dead-silent Valdron skyline
    fb.gothicCitadel(192, 258, 68, 96, C.void, C.slate0, C.cteal, T, 55);
    fb.poly([[0, 336], [148, 322], [W, 344], [W, H], [0, H]], C.moss0);
    const wakeProg = ss(28.2, 30.8, t);
    drawKnight(fb, 96, 350, {
      scale: 1.85,
      facing: 1,
      pose: 'wake',
      prog: wakeProg,
      t,
      rimCol: C.cyan,
    });
    // Trace of glowing green ichor on turf
    fb.ellipse(118, 348, 7, 2, C.ichor3);
  }

  drawMotes(fb, 55, t, C.stone2, C.ichor2, 14, -12, 62); // falling grey ash
  return LUT.corpse;
}

// —— SHOT 07 (32.5–38.0s): Towering open portcullis leaking dark fog & creeping green veins ——
export function shot07(fb, t) {
  const u = seg(t, 32.5, 38.0);
  const camY = Math.round(lerp(56, 0, eio(u))); // integer tilt up monumental gatehouse

  fb.vgrad(0, 320, [C.void, C.abyss, C.cdeep, C.slate0]);
  fb.stars(150, 40, 707, 0, camY * 0.3, t);

  // Monumental Gothic Gatehouse filling vertical frame
  const gateTop = 64 - camY;
  fb.rect(12, gateTop + 44, W - 24, 310, C.slate0);
  // Central crenellated parapet
  for (let mx = 66; mx < 204; mx += 22) {
    fb.rect(mx, gateTop + 32, 13, 14, C.slate0);
    fb.vline(mx, gateTop + 32, gateTop + 46, C.stone1);
  }
  // Twin flanking turrets with needle spires
  fb.gothicCitadel(42, gateTop + 70, 40, 90, C.void, C.slate0, C.stone1, T, 71);
  fb.gothicCitadel(228, gateTop + 70, 40, 90, C.void, C.slate0, C.stone1, T, 72);

  // Stone masonry blocks & recessed machicolations
  for (let y = gateTop + 56; y < 350 - camY; y += 18) {
    fb.hline(14, W - 15, y, C.void);
    for (let x = (y % 36 === 0 ? 26 : 44); x < W - 20; x += 36) fb.vline(x, y, y + 18, C.void);
  }

  // Yawning pointed gate arch + beveled stone voussoirs
  const archX = 135, archW = 52, archTop = gateTop + 146, archBot = 352 - camY;
  fb.poly([
    [archX - archW - 6, archBot],
    [archX - archW - 6, archTop + 34],
    [archX, archTop - 7],
    [archX + archW + 6, archTop + 34],
    [archX + archW + 6, archBot],
  ], C.stone0);
  fb.poly([
    [archX - archW, archBot],
    [archX - archW, archTop + 34],
    [archX, archTop],
    [archX + archW, archTop + 34],
    [archX + archW, archBot],
  ], C.void);
  // Crooked iron portcullis teeth & crossbars hanging half-jammed
  fb.hline(archX - archW + 3, archX + archW - 3, archTop + 46, C.stone0);
  fb.hline(archX - archW + 2, archX + archW - 2, archTop + 66, C.stone0);
  for (let px = archX - archW + 8; px <= archX + archW - 8; px += 12) {
    const jam = Math.round((px - archX) * 0.14);
    fb.vline(px, archTop + 18, archTop + 78 + jam, C.stone0);
    fb.tri(px - 2, archTop + 78 + jam, px + 2, archTop + 78 + jam, px, archTop + 86 + jam, C.stone1);
  }

  // Rolling fog spilling out of the dark archway
  fb.fogLayer(archBot - 52, archBot + 28, -t * 14, 1.05, C.slate0, C.cteal, 74);

  // Dried arterial splatter & organic branching Loris ichor veins on the gate piers!
  fb.ellipse(archX - archW - 14, archBot - 6, 12, 5, C.blood0);
  fb.capsule(archX - archW - 14, archBot - 26, archX - archW - 11, archBot - 4, 3, C.blood1);
  fb.line(archX - archW - 17, archBot - 32, archX - archW - 13, archBot - 12, C.blood2, 1);

  fb.lightHalo(archX + archW + 10, archBot - 38, 4, 28, LIGHT_ICHOR, false);
  let vx = archX + archW + 6, vy = archBot + 2;
  for (let s = 0; s < 10; s++) {
    const nx = vx + Math.sin(s * 1.1) * 4 + 1;
    const ny = vy - 7;
    fb.line(vx, vy, nx, ny, s < 6 ? C.ichor3 : C.ichor2, s < 4 ? 2 : 1);
    if (s % 3 === 1) fb.line(nx, ny, nx + (s % 2 ? 9 : -8), ny - 9, C.ichor4, 1);
    vx = nx; vy = ny;
  }

  // Wet stone causeway & the lone Knight facing the dark gate (back view)
  fb.vgrad(archBot, H, [C.void, C.slate0, C.moss0]);
  drawKnight(fb, 135, archBot + 38, {
    scale: 1.35,
    facing: 0,
    pose: 'idle',
    t,
    rimCol: C.cyan,
  });

  drawMotes(fb, 40, t, C.stone1, C.ichor2, 10, -8, 75);
  return LUT.corpse;
}

// —— SHOT 08 (38.0–45.0s): Deserted banquet street (dark mirror of Shot 02) ——
export function shot08(fb, t) {
  const u = seg(t, 38.0, 45.0);
  const camX = Math.round(lerp(0, 68, u));

  fb.vgrad(0, 290, [C.void, C.abyss, C.cdeep, C.slate0]);
  // Same courtyard colonnade from Shot 02, now cold, empty, fog-draped
  const bgX = Math.round(camX * 0.6);
  fb.rect(0, 140, W, 175, C.slate0);
  for (let k = -1; k < 6; k++) {
    const ax = k * 64 - (bgX % 64) + 18;
    fb.rect(ax - 8, 162, 16, 155, C.stone0);
    fb.ellipse(ax + 24, 182, 22, 26, C.void);
    fb.rect(ax + 2, 182, 44, 135, C.void);
  }

  // Swinging iron tavern sign on one broken chain (creaking in wind)
  const signX = 186 - bgX, signY = 166;
  const swing = Math.sin(t * 2.1) * 5;
  fb.hline(signX - 18, signX + 6, signY, C.stone1);
  fb.line(signX - 2, signY, signX - 2 + swing, signY + 12, C.stone2, 1);
  fb.poly([
    [signX - 10 + swing, signY + 12],
    [signX + 8 + swing, signY + 15],
    [signX + 6 + swing * 1.2, signY + 29],
    [signX - 12 + swing * 1.2, signY + 26],
  ], C.stone0);

  // Wet cobblestones
  fb.vgrad(295, H, [C.slate0, C.void, C.slate0, C.void]);

  // Cold extinguished braziers & overturned banquet table
  for (const bx of [68, 206]) {
    fb.poly([[bx - 8 - camX, 258], [bx + 8 - camX, 258], [bx + 4 - camX, 268], [bx - 4 - camX, 268]], C.stone0);
  }
  const tx = 112 - camX;
  fb.poly([[tx, 314], [tx + 122, 294], [tx + 125, 302], [tx + 3, 322]], C.stone0); // tilted broken table!
  // Congealed blood pool & glowing green drag-trail into open doorway
  fb.ellipse(tx + 44, 326, 26, 5, C.blood0);
  fb.ellipse(tx + 40, 326, 14, 3, C.blood1);
  fb.lightHalo(tx + 96, 318, 4, 24, LIGHT_ICHOR, false);
  fb.poly([[tx + 72, 330], [tx + 92, 329], [tx + 112, 312], [tx + 102, 312]], C.ichor2);
  fb.line(tx + 82, 329, tx + 106, 313, C.ichor3, 2);

  // Rolling ground mist
  fb.fogLayer(268, 338, t * 12 + camX, 0.78, C.slate0, C.cteal, 82);

  // The Knight walking slowly left-to-right investigating the carnage
  const kx = Math.round(lerp(56, 178, u)) - Math.round(camX * 0.45);
  drawKnight(fb, kx, 344, {
    scale: 1.55,
    facing: 1,
    pose: 'walk',
    t,
    rimCol: C.cyan,
  });

  return LUT.corpse;
}

// —— SHOT 09 (45.0–51.5s): Resident Evil fixed-angle cottage interior ——
export function shot09(fb, t) {
  const u = seg(t, 45.0, 51.5);
  // Dark interior walls & ceiling rafters
  fb.clear(C.void);
  fb.rect(18, 46, W - 36, 296, C.slate0);
  // Perspective timber ceiling beams
  for (let k = 0; k < 5; k++) {
    const bx = 24 + k * 56;
    fb.line(bx, 46, 135 + (bx - 135) * 0.65, 118, C.void, 4);
  }
  // Back wall plaster + smeared arterial handprint & drag streak!
  fb.rect(42, 118, W - 84, 176, C.stone0);
  fb.disc(188, 196, 5, C.blood1);
  for (let f = -2; f <= 2; f++) fb.line(188 + f * 2, 192, 189 + f * 2.5, 183, C.blood2, 1);
  fb.capsule(188, 198, 192, 236, 3, C.blood0);
  fb.line(188, 198, 191, 228, C.blood1, 2);

  // Open cottage doorway on left-center spilling cold moonlight
  const dx = 76, dy = 142, dw = 58, dh = 152;
  fb.rect(dx, dy, dw, dh, C.abyss);
  fb.vgrad(dy, dy + dh, [C.night, C.cdeep, C.slate0], dx, dx + dw);
  drawMoonShaft(fb, dx + 29, dw, dx + 56, dw * 1.6, dy + dh - 8, 385, LIGHT_COOL);

  // Wooden floorboards
  fb.vgrad(294, 420, [C.slate0, C.void, C.slate0]);
  for (let y = 302; y < 410; y += 14) fb.hline(14, W - 14, y, C.void);

  // Cellar trapdoor on right floor weeping upward with green curse mist!
  fb.poly([[162, 326], [224, 326], [238, 364], [154, 364]], C.void);
  fb.poly([[165, 329], [221, 329], [233, 361], [157, 361]], C.slate0);
  // Glowing green seam around the cellar hatch
  fb.hline(157, 233, 361, C.ichor3);
  fb.line(192, 329, 196, 361, C.ichor4, 2);
  fb.lightHalo(195, 348, 8, 42, LIGHT_ICHOR, true);
  fb.fogLayer(278, 366, -t * 9, 0.92, C.ichor1, C.ichor3, 93);

  // Knight stepping over threshold with dim lantern
  const kx = Math.round(lerp(92, 126, eo(u)));
  const ky = Math.round(lerp(312, 336, eo(u)));
  fb.lightHalo(kx + 18, ky - 36, 10, 56, LIGHT_WARM, false);
  drawKnight(fb, kx, ky, {
    scale: 1.55,
    facing: 1,
    pose: 'lantern',
    t,
    rimCol: C.ichor3,
  });

  // Foreground out-of-focus dark table silhouette framing bottom-left (classic survival horror staging)
  fb.rect(0, 368, 96, 14, C.void);
  fb.rect(72, 382, 12, 98, C.void);
  // Half-eaten bread & knocked mug in foreground silhouette
  fb.ellipse(38, 364, 11, 5, C.slate0);

  return LUT.corpse;
}

// —— SHOT 10 (51.5–60.0s): OBSERVATIONAL HORROR HOLD — Motionless Citizen Slowly Elongates ——
export function shot10(fb, t) {
  // Locked claustrophobic gothic alley — camera refuses to cut away!
  fb.vgrad(0, 290, [C.void, C.abyss, C.cdeep, C.slate0]);

  // Overhanging medieval gable walls closing in from left & right
  fb.poly([[0, 0], [88, 72], [78, 315], [0, 365]], C.void);
  fb.poly([[W, 0], [186, 68], [196, 315], [W, 365]], C.void);
  // Timber framing & dim leaded windows on alley walls
  for (let y = 95; y < 290; y += 44) {
    fb.line(8, y, 78, y + 18, C.slate0, 2);
    fb.line(W - 8, y - 4, 196, y + 16, C.slate0, 2);
  }
  fb.rect(28, 132, 14, 22, C.slate1);
  fb.rect(226, 146, 14, 22, C.slate1);

  // Receding wet cobblestone alley perspective
  fb.poly([[78, 315], [196, 315], [W, H], [0, H]], C.slate0);
  for (let k = -3; k <= 3; k++) {
    fb.line(137 + k * 9, 315, 137 + k * 42, H, C.void, 1);
  }

  // Rolling alley fog
  fb.fogLayer(225, 336, t * 7, 0.82, C.slate0, C.cteal, 104);

  // 51.5–54.8s: completely human-looking motionless villager facing away.
  // 54.8–59.5s: slow, sickening anatomical elongation & head tilt (NO jump scare!).
  const mut = eio(seg(t, 54.8, 59.5));
  if (mut > 0.2) {
    fb.lightHalo(148, 286, 4, 22 + mut * 24, LIGHT_ICHOR, false);
  }
  drawAlleyMutant(fb, 148, 326, 1.38, mut, t);
  if (mut > 0.45) {
    // Pool of glowing green ichor forming at the figure's feet
    fb.ellipse(154, 327, 4 + mut * 9, 2, C.ichor3);
  }

  // Foreground left: the Knight approaches (51.5–53.6s), then freezes dead still watching!
  const walkIn = eo(seg(t, 51.5, 53.6));
  const kx = Math.round(lerp(42, 68, walkIn));
  const ky = Math.round(lerp(418, 396, walkIn));
  drawKnight(fb, kx, ky, {
    scale: 1.95,
    facing: 1,
    pose: t < 53.6 ? 'walk' : 'idle',
    t,
    rimCol: mut > 0.5 ? C.ichor3 : C.cyan,
  });

  return LUT.corpse;
}

// —— SHOT 11 (60.0–68.0s): Close Visor Glint -> Pull Wide to Crooked Watchers in Town Square ——
export function shot11(fb, t) {
  if (t < 62.1) {
    // Tight close-up on the Knight's steel visor catching the curse-green reflection
    fb.vgrad(0, H, [C.void, C.abyss, C.slate0, C.void]);
    fb.fogLayer(80, 380, t * 14, 0.65, C.slate0, C.ichor1, 111);
    drawKnightVisorClose(fb, 135, 226, t);
    return LUT.corpse;
  }

  // 62.1–68.0s: Wide pull-back across town square as fog thins to reveal 3 crooked silhouettes watching silently
  const u = seg(t, 62.1, 68.0);
  fb.vgrad(0, 295, [C.void, C.abyss, C.cdeep, C.slate0]);
  fb.stars(165, 45, 112, 0, 0, t);

  // Steep gothic town square gables
  fb.gothicCitadel(62, 292, 64, 110, C.void, C.slate0, C.stone0, T, 113);
  fb.gothicCitadel(212, 296, 68, 122, C.void, C.slate0, C.stone0, T, 114);
  fb.vgrad(292, H, [C.slate0, C.void, C.moss0]);

  // Stone town well in center midground
  fb.rect(120, 286, 30, 18, C.stone0);
  fb.hline(118, 152, 286, C.stone2);
  fb.line(123, 286, 123, 264, C.slate1, 2);
  fb.line(147, 286, 147, 264, C.slate1, 2);
  fb.tri(116, 264, 154, 264, 135, 250, C.void);

  // Three crooked mutated silhouettes emerging as fog parts!
  drawCrookedWatcher(fb, 135, 286, 44, 0, t);          // perched atop the stone well
  drawCrookedWatcher(fb, 54, 218, 38, 0, t + 1.3);     // standing impossibly tall on left gable roof
  drawCrookedWatcher(fb, 208, 298, 52, 0, t + 2.6);    // hunched on right cobbles

  // Fog thinning from 1.1 -> 0.55 to unveil them without a sudden jump
  fb.fogLayer(200, 326, t * 9, lerp(1.15, 0.52, u), C.slate0, C.cteal, 115);

  // Knight in foreground backing slowly toward the outer road, weapon ready
  drawKnight(fb, Math.round(lerp(104, 86, u)), 366, {
    scale: 1.48,
    facing: 1,
    pose: 'guard',
    t,
    rimCol: C.cyan,
  });

  return LUT.corpse;
}

// —— SHOT 12 (68.0–75.5s): 5-Layer Parallax Trek Through Cursed Unknown Woods ——
export function shot12(fb, t) {
  const u = seg(t, 68.0, 75.5);
  const camX = t * 24;

  // Deep nocturnal forest sky
  fb.vgrad(0, 320, [C.void, C.abyss, C.cdeep, C.moss1, C.moss0]);
  fb.moon(196, 88, 20, 'cyan');

  // Layer 1 (0.2x): Far spectral tree line
  for (let i = 0; i < 9; i++) {
    const tx = mod(i * 38 - Math.round(camX * 0.2), W + 30) - 15;
    fb.gnarledTree(tx, 278, 95 + (i % 3) * 18, C.abyss, T, 120 + i, Math.sin(t + i) * 0.6);
  }
  fb.fogLayer(210, 292, camX * 0.35, 0.9, C.cdeep, C.ichor1, 121);

  // Layer 2 (0.5x): Mid-far gnarled trunks + silent antlered-flesh watchers between trees!
  for (let i = 0; i < 6; i++) {
    const tx = mod(i * 56 - Math.round(camX * 0.5), W + 50) - 25;
    fb.gnarledTree(tx, 306, 138, C.slate0, C.cteal, 130 + i, Math.sin(t * 1.3 + i) * 0.8);
  }
  const wx1 = mod(210 - Math.round(camX * 0.5), W + 60) - 30;
  const wx2 = mod(95 - Math.round(camX * 0.5), W + 60) - 30;
  drawCrookedWatcher(fb, wx1, 304, 48, 1, t);
  drawCrookedWatcher(fb, wx2, 300, 42, 1, t + 2.0);

  // Layer 3 (0.8x): Hanging wicker wards (*Over the Garden Wall* eerie folk-dread touch)
  for (let i = 0; i < 3; i++) {
    const hx = mod(i * 105 - Math.round(camX * 0.8), W + 40) - 20;
    const sw = Math.sin(t * 2.3 + i) * 3;
    fb.line(hx, 148, hx + sw, 184, C.slate1, 1);
    fb.line(hx - 5 + sw, 188, hx + 5 + sw, 188, C.stone1, 1);
    fb.line(hx + sw, 182, hx + sw, 198, C.stone1, 1);
  }

  // Layer 4 (1.0x): Mossy forest path & marching Knight
  fb.poly([[0, 326], [W, 318], [W, H], [0, H]], C.moss0);
  fb.fogLayer(288, 352, camX * 0.9, 0.85, C.moss1, C.ichor2, 125);
  drawKnight(fb, Math.round(lerp(96, 142, u)), 348, {
    scale: 1.5,
    facing: 1,
    pose: 'walk',
    t,
    rimCol: C.cyan,
  });

  // Layer 5 (1.6x): Heavy black foreground trunks passing across frame
  const fgX = mod(260 - Math.round(camX * 1.6), W + 140) - 70;
  fb.rect(fgX, 0, 22, H, C.void);
  fb.vline(fgX + 22, 0, H, C.moss1);

  drawMotes(fb, 45, t, C.ichor3, C.cice, -8, -14, 129);
  return LUT.full;
}

// —— SHOT 13 (75.5–82.0s): Blighted Watermill Bridge & Desperate Cleave ——
export function shot13(fb, t) {
  // Integer recoil screen shake when beast acid hits shield (78.1s) & when greatsword cleaves (79.7s)
  let shakeX = 0, shakeY = 0;
  for (const hitT of [78.1, 79.7]) {
    const dt = t - hitT;
    if (dt >= 0 && dt < 0.34) {
      const amp = Math.ceil((1 - dt / 0.34) * 3);
      const fr = Math.floor(dt * 24);
      shakeX = (fr % 2 === 0 ? 1 : -1) * amp;
      shakeY = (fr % 3 === 0 ? -1 : 1) * Math.max(1, amp - 1);
    }
  }

  fb.vgrad(0, 290, [C.void, C.abyss, C.cdeep, C.moss1]);

  // Ruined timber watermill with pitched gable roof, stone base & spoked paddle-wheel
  const mx = 192 + shakeX, my = 224 + shakeY;
  fb.rect(144 + shakeX, 186 + shakeY, 114, 108, C.slate0);
  fb.tri(136 + shakeX, 186 + shakeY, 266 + shakeX, 186 + shakeY, 200 + shakeX, 126 + shakeY, C.void);
  fb.line(136 + shakeX, 186 + shakeY, 200 + shakeX, 126 + shakeY, C.stone1, 2);
  fb.rect(166 + shakeX, 204 + shakeY, 16, 24, C.void);
  const wr = 38;
  for (let a = 0; a < 10; a++) {
    const ang = a * (Math.PI / 5) + t * 0.45;
    const rx1 = mx + Math.cos(ang) * wr, ry1 = my + Math.sin(ang) * wr;
    const rx2 = mx + Math.cos(ang + Math.PI / 5) * wr, ry2 = my + Math.sin(ang + Math.PI / 5) * wr;
    fb.line(mx, my, rx1, ry1, C.stone0, 2);
    fb.line(rx1, ry1, rx2, ry2, C.stone1, 2);
  }

  // Green-poisoned mill river below
  fb.vgrad(326 + shakeY, H, [C.ichor0, C.void, C.ichor1, C.void]);
  fb.fogLayer(268 + shakeY, 336 + shakeY, t * 18, 0.8, C.moss1, C.ichor2, 133);

  // Arched stone bridge
  fb.poly([[0, 314 + shakeY], [135, 304 + shakeY], [W, 316 + shakeY], [W, 352 + shakeY], [0, 352 + shakeY]], C.slate0);
  fb.hline(0, W - 1, 308 + shakeY, C.stone1);

  // Action choreography:
  // 75.5–78.0: Beast lunges left; 78.0–79.1: Knight guards acid splash; 79.1–82.0: Knight cleaves through!
  const lunge = ss(76.0, 78.1, t) * (1 - ss(79.6, 80.3, t));
  const beastRecoil = ss(79.65, 80.5, t);
  const isCleave = t >= 79.05;
  const cleaveProg = seg(t, 79.05, 80.4);

  // Acid spray droplets on shield block (78.0–78.9s)
  if (t >= 78.0 && t < 79.0) {
    const sp = seg(t, 78.0, 79.0);
    fb.lightHalo(112 + shakeX, 286 + shakeY, 5, 28, LIGHT_ICHOR, true);
    for (let k = 0; k < 12; k++) {
      const ang = 1.9 + hash2(k, 1, 13) * 1.8;
      const dist = sp * (18 + hash2(k, 2, 13) * 26);
      fb.disc(112 + Math.cos(ang) * dist + shakeX, 284 + Math.sin(ang) * dist + shakeY, 1.5, C.ichor4);
    }
  }

  // Draw Beast (dissolves in green/ash spray after 80.2s cleave impact)
  if (t < 81.2) {
    drawMillBeast(fb, 184 + shakeX, 316 + shakeY, 1.28, lunge, beastRecoil, t);
  }
  if (t >= 79.65 && t < 81.4) {
    const burst = seg(t, 79.65, 81.4);
    fb.lightHalo(154 + shakeX, 282 + shakeY, 6, 38 * (1 - burst * 0.5), LIGHT_ICHOR, true);
    for (let i = 0; i < 22; i++) {
      const ang = hash2(i, 3, 99) * Math.PI * 2;
      const d = burst * (14 + hash2(i, 4, 99) * 48);
      fb.px(Math.round(158 + Math.cos(ang) * d), Math.round(278 + Math.sin(ang) * d), i % 2 === 0 ? C.ichor4 : C.cstar);
    }
  }

  // Draw Knight on left of bridge
  const kx = Math.round(lerp(82, isCleave ? 124 : 76, isCleave ? eo(cleaveProg) : ss(77.6, 78.2, t))) + shakeX;
  drawKnight(fb, kx, 314 + shakeY, {
    scale: 1.52,
    facing: 1,
    pose: isCleave ? 'cleave' : (t >= 77.5 ? 'guard' : 'walk'),
    prog: cleaveProg,
    t,
    rimCol: C.cice,
  });

  drawMotes(fb, 50, t, C.ichor3, C.stone2, -16, -10, 137);
  return LUT.full;
}

// —— SHOT 14 (82.0–88.5s): Ruined Vault-Smithy & Moon-Runed Greatsword Relic ——
export function shot14(fb, t) {
  const u = seg(t, 82.0, 88.5);
  const camY = Math.round(lerp(28, 0, eio(u))); // slow crane up the raised rune-blade

  fb.vgrad(0, H, [C.void, C.abyss, C.night, C.slate0, C.void]);

  // Gothic vaulted stone ribs of the ruined smithy
  for (let k = 0; k < 3; k++) {
    const ax = 30 + k * 105;
    fb.rect(ax - 8, 60 - camY, 16, 310, C.slate0);
    fb.line(ax, 120 - camY, 135, 36 - camY, C.stone0, 3);
  }
  // Cold cyan moonlight shaft falling diagonally onto the rune-anvil
  drawMoonShaft(fb, 168, 44, 135, 92, 0, 355 - camY, LIGHT_COOL);

  // Cracked stone forge altar / anvil at center
  const ay = 342 - camY;
  fb.poly([[96, ay], [174, ay], [164, ay - 24], [106, ay - 24]], C.stone0);
  fb.hline(104, 166, ay - 24, C.steel);
  fb.rect(82, ay, 106, 16, C.slate0);

  // Ignition of the Moon-Runed Blade at 83.8s, banishing creeping green rot!
  const ignite = ss(83.6, 84.8, t);
  const rotRadius = lerp(52, 8, ignite);
  if (rotRadius > 12) {
    fb.hline(60, Math.round(60 + rotRadius), ay + 14, C.ichor2);
    fb.hline(Math.round(210 - rotRadius), 210, ay + 14, C.ichor2);
  }

  if (ignite > 0.05) {
    fb.lightHalo(128, ay - 76, 8 + ignite * 12, 34 + ignite * 42, LIGHT_COOL, true);
    // Floating astral rune motes
    for (let i = 0; i < 16; i++) {
      const ang = t * 1.6 + i * 0.4;
      const r = 16 + (i % 4) * 11 * ignite;
      fb.px(Math.round(128 + Math.cos(ang) * r), Math.round(ay - 68 + Math.sin(ang * 1.3) * r * 1.4), C.cstar);
    }
  }

  // Knight raising the Moon-Runed Greatsword
  drawKnight(fb, 118, ay + 12, {
    scale: 1.72,
    facing: 1,
    pose: 'relic',
    prog: seg(t, 82.4, 85.2),
    t,
    rimCol: C.cstar,
    runeSword: t >= 83.5,
  });

  return LUT.full;
}

// —— SHOT 15a (88.5–90.7s): Escalation 1 — Sunken Mire Colossus (Match point 135, 232) ——
export function shot15a(fb, t) {
  const u = seg(t, 88.5, 90.7);
  fb.vgrad(0, 285, [C.void, C.abyss, C.cdeep, C.moss1]);
  fb.cragSlope(-1, 180, 310, 95, C.void, C.moss1, C.moss2, 151);
  fb.cragSlope(1, 175, 310, 105, C.void, C.moss1, C.moss2, 152);

  // Towering Sunken Mire Colossus rising out of black-green swamp water; glowing heart at (135, 232)!
  const rise = eo(u) * 18;
  const by = Math.round(298 - rise);
  fb.ellipse(135, by - 42, 46, 54, C.void);
  fb.poly([[82, by], [96, by - 88], [135, by - 112], [174, by - 88], [188, by]], C.slate0);
  // Antler-crown of dead roots & rusted spears
  for (let k = -3; k <= 3; k++) {
    fb.line(135 + k * 10, by - 96, 135 + k * 19, by - 134 - Math.abs(k) * 4, C.void, 2);
  }
  // Protected curse-green core locked at screen (135, 232) for match cut!
  fb.lightHalo(135, 232, 8, 42, LIGHT_ICHOR, true);
  fb.disc(135, 232, 9, C.ichor3);
  fb.disc(135, 232, 4.5, C.ichor4);

  // Black mire water with glowing ripples
  fb.vgrad(296, H, [C.ichor0, C.void, C.moss0, C.void]);
  fb.hline(72, 198, 298, C.ichor3);

  // Knight dashing right-to-left across foreground causeway with rune-blade arc
  drawKnight(fb, Math.round(lerp(66, 102, u)), 352, {
    scale: 1.45,
    facing: 1,
    pose: 'cleave',
    prog: u,
    t,
    rimCol: C.cstar,
    runeSword: true,
  });
  return LUT.full;
}

// —— SHOT 15b (90.7–92.9s): Escalation 2 — Plague Belfry Inverted Horror (Match point 135, 232) ——
export function shot15b(fb, t) {
  const u = seg(t, 90.7, 92.9);
  fb.vgrad(0, H, [C.void, C.abyss, C.night, C.slate0]);

  // Tall gothic belfry interior walls & arched lancets
  fb.rect(0, 0, 36, H, C.void);
  fb.rect(W - 36, 0, 36, H, C.void);
  fb.ellipse(135, 168, 66, 96, C.cdeep);
  fb.vline(135, 68, 270, C.void);

  // Giant cracked bronze bell + inverted multi-limbed horror clinging at (135, 232)!
  fb.poly([[102, 188], [168, 188], [182, 248], [88, 248]], C.slate0);
  fb.hline(88, 182, 248, C.stone2);
  // Spidery limbs gripping rafters
  for (let k = 0; k < 6; k++) {
    const side = k < 3 ? -1 : 1;
    const ly = 198 + (k % 3) * 20;
    fb.line(135 + side * 18, 232, side < 0 ? 36 : W - 36, ly + Math.sin(t * 9 + k) * 6, C.void, 2);
  }
  // Glowing green bell-clapper / horror eye locked at (135, 232)!
  fb.lightHalo(135, 232, 9, 46 + Math.sin(u * Math.PI) * 20, LIGHT_ICHOR, true);
  fb.disc(135, 232, 8, C.ichor3);
  fb.disc(135, 232, 4, C.ichor4);

  // Bayer shockwave rings radiating outward
  const rWave = u * 165;
  for (let a = 0; a < 48; a++) {
    const ang = (a / 48) * Math.PI * 2;
    fb.px(Math.round(135 + Math.cos(ang) * rWave), Math.round(232 + Math.sin(ang) * rWave), C.cice);
  }

  // Knight below looking up on belfry beam
  fb.rect(36, 366, W - 72, 12, C.void);
  drawKnight(fb, 118, 366, { scale: 1.35, facing: 1, pose: 'guard', t, rimCol: C.cstar, runeSword: true });
  return LUT.full;
}

// —— SHOT 15c (92.9–95.0s): Escalation 3 — Shattered Loris Relief Weeping Green Sap (Match 135, 232) ——
export function shot15c(fb, t) {
  const u = seg(t, 92.9, 95.0);
  fb.clear(C.void);
  // Carved ancient stone tablet filling frame — visual clue of Valdron's slaughter of Loris
  const pad = Math.round(lerp(28, 14, u));
  fb.rect(pad, 64, W - pad * 2, 344, C.slate0);
  fb.rect(pad + 8, 74, W - (pad + 8) * 2, 324, C.stone0);

  // Carved Loris crescent-sun above kneeling figures pierced by spears
  fb.disc(135, 138, 22, C.stone2);
  fb.disc(142, 135, 17, C.stone0);
  for (let i = 0; i < 5; i++) {
    const fx = 76 + i * 29;
    // Spear shafts angled down from left
    fb.line(fx - 18, 168, fx + 6, 268, C.slate0, 2);
    // Fallen robed silhouettes of Loris
    fb.ellipse(fx + 6, 286, 9, 16, C.slate1);
  }

  // Deep jagged fissure splitting the relief right through (135, 232), weeping curse-green sap!
  fb.line(122, 92, 135, 232, C.void, 4);
  fb.line(135, 232, 149, 376, C.void, 4);
  fb.line(123, 102, 135, 232, C.ichor3, 2);
  fb.line(135, 232, 148, 368, C.ichor4, 2);
  fb.lightHalo(135, 232, 8, 44, LIGHT_ICHOR, true);
  fb.disc(135, 232, 6, C.ichor4);

  return LUT.corpse;
}

// —— SHOT 16 (95.0–100.0s): Nocturnal Valley & Astral Beacon Spire (Reference 1 Grammar) ——
export function shot16(fb, t) {
  const u = seg(t, 95.0, 100.0);
  const camY = Math.round(lerp(18, 0, eio(u)));

  // Deep midnight-to-royal-blue vertical sky with pinpoint stars (Reference 1 palette logic)
  fb.vgrad(0, 280, [C.void, C.abyss, C.night, C.indigo, C.dusk, C.royal]);
  fb.stars(230, 95, 160, 0, camY * 0.2, t);

  // Curling nocturnal cloud banks framing the central sky cathedral
  fb.fogLayer(88, 215, t * 4, 0.72, C.night, C.royal, 161);

  // Piercing astral star-burst directly over the central spire!
  const pulse = 0.92 + 0.08 * Math.sin(t * 3.2);
  fb.astralBeacon(135, 86 - Math.round(camY * 0.4), 52, 48, pulse);

  // Jagged mountain peak & towering needle-spired Gothic Citadel at center
  fb.poly([
    [18, 292 - camY], [78, 218 - camY], [135, 192 - camY], [194, 222 - camY], [254, 292 - camY],
  ], C.abyss);
  fb.poly([
    [78, 218 - camY], [135, 192 - camY], [148, 255 - camY], [64, 262 - camY],
  ], C.indigo);
  fb.gothicCitadel(135, 214 - camY, 68, 92, C.void, C.night, C.royal, C.cice, 162);

  // Misty valley chasm
  fb.fogLayer(246 - camY, 318 - camY, -t * 5, 0.85, C.indigo, C.sky, 163);

  // Undulating mossy emerald valley floor, winding stony path & rocky crag slopes on left and right
  drawMossyValley(fb, 286 - camY, 160);
  fb.cragSlope(-1, 215 - camY, H, 108, C.void, C.indigo, C.moss3, 164);
  fb.cragSlope(1, 232 - camY, H, 116, C.void, C.indigo, C.moss3, 165);

  // Scattered dark mossy boulders in foreground meadow
  for (const [bx, by, br] of [[96, 396, 12], [166, 378, 9], [132, 432, 16], [192, 444, 14]]) {
    fb.ellipse(bx, by - camY, br * 1.4, br * 0.8, C.void);
    fb.ellipse(bx - 2, by - 2 - camY, br * 1.1, br * 0.55, C.indigo);
  }

  return LUT.full;
}

// —— SHOT 17 (100.0–108.5s): SIGNATURE SHOT — Giant Cyan Moon, Citadel & Lone Knight Crane-Tilt ——
export function shot17(fb, t) {
  const u = seg(t, 100.0, 108.5);
  // Long majestic integer crane-tilt from foreground crags up to the giant cyan moon & citadel!
  const camY = Math.round(lerp(72, 0, eio(u)));

  // Pitch-black star-pricked upper sky -> cyan mist horizon (Reference 3 iconic contrast!)
  fb.vgrad(0, 310 - Math.round(camY * 0.5), [C.void, C.void, C.abyss, C.cdeep, C.cteal]);
  fb.stars(190, 58, 170, 0, camY * 0.25, t);

  // Colossal textured Cyan Full Moon centered behind the King's Citadel!
  const moonY = 128 - Math.round(camY * 0.45);
  fb.moon(135, moonY, 64, 'cyan');

  // Towering Gothic Royal Citadel silhouetted in razor-sharp black & cyan rim-light against the moon
  const citY = 264 - Math.round(camY * 0.65);
  fb.gothicCitadel(135, citY, 82, 168, C.void, C.slate0, C.cteal, C.ichor3, 171);

  // Sea of cyan-grey mist swirling around the crags below the castle
  fb.fogLayer(224 - Math.round(camY * 0.7), 316 - Math.round(camY * 0.7), t * 6, 1.05, C.cdeep, C.cyan, 172);
  // Jagged dark monolith crags jutting out of the mist
  fb.poly([[108, 304 - camY], [120, 268 - camY], [134, 304 - camY]], C.void);
  fb.poly([[148, 308 - camY], [156, 282 - camY], [165, 308 - camY]], C.void);

  // Undulating mossy valley & framing crag walls (organic rolling terrain!)
  drawMossyValley(fb, 298 - camY, 177);
  fb.cragSlope(-1, 240 - camY, H, 92, C.void, C.slate0, C.moss3, 173);
  fb.cragSlope(1, 232 - camY, H, 98, C.void, C.slate0, C.moss3, 174);

  // Solitary cloaked Knight standing on foreground rocky outcrop facing the Citadel!
  const ky = 376 - camY;
  fb.poly([[54, ky + 16], [76, ky - 4], [116, ky + 2], [132, ky + 22]], C.void);
  drawKnight(fb, 92, ky, {
    scale: 1.58,
    facing: 0,
    pose: 'cliff',
    t,
    rimCol: C.cice,
    runeSword: true,
  });

  return LUT.full;
}

// —— SHOT 18 (108.5–113.5s): Ruined King's Throne Nave — Withheld Presence & Mist Swallow ——
export function shot18(fb, t) {
  const u = seg(t, 108.5, 113.5);
  const swallow = eio(seg(t, 111.9, 113.45)); // green/obsidian Bayer mist swallows frame at end

  fb.vgrad(0, H, [C.void, C.abyss, C.cdeep, C.void]);

  // Shattered cyan rose window high in the King's Hall
  const ry = Math.round(lerp(132, 118, u));
  fb.disc(135, ry, 42, C.cdeep);
  fb.disc(135, ry, 34, C.cyan);
  for (let a = 0; a < 12; a++) {
    const ang = (a / 12) * Math.PI * 2;
    fb.line(135, ry, 135 + Math.cos(ang) * 42, ry + Math.sin(ang) * 42, C.void, 2);
  }
  drawMoonShaft(fb, 135, 64, 135, 136, ry + 20, 385, LIGHT_COOL);

  // Towering cathedral nave columns
  for (const px of [34, 72, 198, 236]) {
    fb.rect(px - 7, 40, 14, 345, C.void);
    fb.vline(px + (px < 135 ? 7 : -7), 40, 345, C.slate1);
  }

  // Vast, barely-seen multi-jointed colossal silhouette shifting behind the back pillars!
  const shift = Math.sin(t * 1.5) * 4;
  fb.capsule(92 + shift, 238, 112 + shift, 178, 8, C.void);
  fb.capsule(178 - shift, 242, 160 - shift, 174, 8, C.void);
  fb.px(Math.round(114 + shift), 182, C.ichor3);
  fb.px(Math.round(158 - shift), 180, C.ichor3);

  // Stepped dais & empty blood-stained Royal Throne
  fb.poly([[64, 356], [206, 356], [182, 312], [88, 312]], C.slate0);
  fb.rect(118, 266, 34, 46, C.void);
  fb.tri(116, 266, 154, 266, 135, 240, C.void);
  fb.capsule(132, 292, 142, 326, 3, C.blood1);

  // Nameless motionless robed silhouette standing above the throne + floating curse-green shards (withholding Aleister!)
  const sx = 135, sy = 308;
  fb.poly([[sx - 8, sy], [sx - 5, sy - 34], [sx + 5, sy - 34], [sx + 8, sy]], C.void);
  fb.ellipse(sx, sy - 38, 4.5, 5.5, C.void);
  fb.lightHalo(sx, sy - 28, 6, 38, LIGHT_ICHOR, true);
  for (let i = 0; i < 5; i++) {
    const ang = t * 1.4 + i * 1.25;
    const fx = Math.round(sx + Math.cos(ang) * 18);
    const fy = Math.round(sy - 28 + Math.sin(ang * 1.5) * 10);
    fb.px(fx, fy, C.ichor4);
    fb.px(fx, fy + 1, C.ichor3);
  }

  // Rising emerald-indigo Bayer mist veiling the frame (never pure black, avoiding mid-film black frames!)
  if (swallow > 0) {
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        const n = noise2(x * 0.06, y * 0.06, 188);
        const v = swallow * 1.25 - (1 - y / H) * 0.22 + (n - 0.5) * 0.24;
        if (bayer8(x, y) < v) {
          fb.d[y * W + x] = n > 0.62 ? C.cdeep : (n > 0.36 ? C.ichor0 : C.abyss);
        }
      }
    }
    drawMotes(fb, 34, t, C.cice, C.ichor3, -12, 4, 189);
  }
  return LUT.corpse;
}

// —— SHOT 19 (113.5–120.0s): Monumental End Title Card — VALDRON ——
export function shot19(fb, t) {
  fb.clear(C.abyss);
  fb.vgrad(0, H, [C.void, C.abyss, C.cdeep, C.abyss, C.void]);

  // Subtle gothic spire watermark silhouette behind title
  fb.gothicCitadel(135, 292, 62, 118, C.void, C.slate0, C.cteal, T, 191);
  fb.fogLayer(226, 332, t * 5, 0.78, C.night, C.ichor1, 192);
  drawMotes(fb, 44, t, C.cice, C.ichor3, -10, 4, 193);

  const disMain = clamp(Math.min((t - 113.80) / 0.65, (119.55 - t) / 0.45), 0, 1);
  const disSub = clamp(Math.min((t - 114.20) / 0.60, (119.55 - t) / 0.45), 0, 1);

  if (disMain > 0) {
    if (disMain > 0.5) {
      fb.hline(48, 222, 248, C.slate1);
      fb.hline(88, 182, 248, C.cteal);
      fb.disc(135, 248, 2.5, C.ichor3);
      fb.px(135, 248, C.ichor4);
    }
    drawGothicText(fb, 'VALDRON', 135, 206, {
      scale: 4,
      tracking: 1,
      rowCols: [C.cstar, C.cice, C.silver, C.steel, C.cyan, C.cteal, C.stone1, C.slate1],
      outlineCol: C.void,
      dissolve: disMain,
      curseVein: true,
    });
  }
  if (disSub > 0) {
    drawGothicText(fb, 'LUMROOK GAME STUDIO', 135, 264, {
      scale: 1,
      tracking: 1,
      rowCols: [C.silver, C.steel, C.steel, C.stone2, C.stone2, C.stone1, C.stone1, C.stone1],
      outlineCol: C.void,
      dissolve: disSub,
    });
  }

  const endDark = seg(t, 119.55, 119.95) * 2;
  return stepFade(LUT.full, endDark);
}

// —— MODEL & HORROR LOOK SHEET (?sheet=1) for DIRECTOR.md §5 verification ——
export function renderModelSheet(fb) {
  fb.vgrad(0, H, [C.abyss, C.night, C.slate0, C.abyss]);
  drawGothicText(fb, 'VALDRON MODEL SHEET', 135, 14, { scale: 1, tracking: 1 });

  // Row 1: The Knight turnaround & key poses
  fb.hline(14, W - 14, 126, C.slate1);
  drawKnight(fb, 46, 122, { scale: 1.45, facing: 1, pose: 'idle', t: 0.4, rimCol: C.cyan });
  drawKnight(fb, 112, 122, { scale: 1.45, facing: 0, pose: 'cliff', t: 0.4, rimCol: C.cice, runeSword: true });
  drawKnight(fb, 188, 122, { scale: 1.45, facing: 1, pose: 'cleave', prog: 0.55, t: 0.4, rimCol: C.cstar, runeSword: true });
  drawGothicText(fb, 'KNIGHT: PROFILE / BACK / CLEAVE', 135, 132, { scale: 1 });

  // Row 2: Uncanny Body-Horror Stages (Townsfolk -> Elongated Mutant)
  fb.hline(14, W - 14, 276, C.slate1);
  drawAlleyMutant(fb, 54, 272, 1.25, 0.0, 0.5);
  drawAlleyMutant(fb, 135, 272, 1.25, 0.52, 1.2);
  drawAlleyMutant(fb, 216, 272, 1.25, 1.0, 2.1);
  drawGothicText(fb, 'CURSE STAGES: STILL / BENT / CHANGED', 135, 282, { scale: 1 });

  // Row 3: Regional Beast & Visor Close
  fb.hline(14, W - 14, 412, C.slate1);
  drawMillBeast(fb, 86, 408, 1.05, 0.6, 0, 1.0);
  drawCrookedWatcher(fb, 202, 408, 62, 1, 1.0);

  // Master 48-colour palette swatch bar along bottom
  for (let i = 0; i < 48; i++) {
    const sx = 15 + (i % 24) * 10;
    const sy = 436 + Math.floor(i / 24) * 14;
    fb.rect(sx, sy, 9, 11, i);
  }
  return LUT.full;
}
