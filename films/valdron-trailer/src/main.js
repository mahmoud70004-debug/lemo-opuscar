// main.js — Deterministic director for VALDRON (270×480 native → 1080×1920 nearest-neighbour)
import { W, H, SCALE, C, FB, LUT, transitionFB, clamp } from './px.js';
import { drawCaptionCard, drawGothicText, measureLine } from './font.js';
import {
  shot01, shot02, shot03, shot04, shot05, shot06, shot07, shot08, shot09, shot10,
  shot11, shot12, shot13, shot14, shot15a, shot15b, shot15c, shot16, shot17, shot18, shot19,
  renderModelSheet,
} from './scenes.js';

const params = new URLSearchParams(location.search);
const IS_SHEET = params.get('sheet') === '1';
const IS_POSTER = params.get('poster') === '1';

const canvas = document.getElementById('stage');
canvas.width = W * SCALE;
canvas.height = H * SCALE;
const ctx = canvas.getContext('2d', { alpha: false });
ctx.imageSmoothingEnabled = false;

const offCanvas = document.createElement('canvas');
offCanvas.width = W;
offCanvas.height = H;
const offCtx = offCanvas.getContext('2d', { alpha: false });
const imgData = offCtx.createImageData(W, H);

const fbA = new FB(W, H);
const fbB = new FB(W, H);
const fbOut = new FB(W, H);

const SHOTS = [
  { id: 's01', t0: 0.0,   t1: 5.8,   fn: shot01,  trans: 'bayer',  tdur: 0.45 },
  { id: 's02', t0: 5.8,   t1: 11.7,  fn: shot02,  trans: 'bayer',  tdur: 0.45 },
  { id: 's03', t0: 11.7,  t1: 16.7,  fn: shot03,  trans: 'bayer',  tdur: 0.50 },
  { id: 's04', t0: 16.7,  t1: 20.0,  fn: shot04,  trans: 'bayer',  tdur: 0.60 },
  { id: 's05', t0: 20.0,  t1: 26.7,  fn: shot05,  trans: 'ichor',  tdur: 0.55 },
  { id: 's06', t0: 26.7,  t1: 32.5,  fn: shot06,  trans: 'bayer',  tdur: 0.50 },
  { id: 's07', t0: 32.5,  t1: 38.0,  fn: shot07,  trans: 'ichor',  tdur: 0.55 },
  { id: 's08', t0: 38.0,  t1: 45.0,  fn: shot08,  trans: 'bayer',  tdur: 0.45 },
  { id: 's09', t0: 45.0,  t1: 51.5,  fn: shot09,  trans: 'bayer',  tdur: 0.45 },
  { id: 's10', t0: 51.5,  t1: 60.0,  fn: shot10,  trans: 'none',   tdur: 0.00 }, // hard cut to close visor reaction!
  { id: 's11', t0: 60.0,  t1: 68.0,  fn: shot11,  trans: 'ichor',  tdur: 0.60 },
  { id: 's12', t0: 68.0,  t1: 75.5,  fn: shot12,  trans: 'bayer',  tdur: 0.40 },
  { id: 's13', t0: 75.5,  t1: 82.0,  fn: shot13,  trans: 'mosaic', tdur: 0.45 },
  { id: 's14', t0: 82.0,  t1: 88.5,  fn: shot14,  trans: 'none',   tdur: 0.00 },
  { id: 's15a', t0: 88.5, t1: 90.7,  fn: shot15a, trans: 'none',   tdur: 0.00 }, // protected-green match cut!
  { id: 's15b', t0: 90.7, t1: 92.9,  fn: shot15b, trans: 'none',   tdur: 0.00 }, // protected-green match cut!
  { id: 's15c', t0: 92.9, t1: 95.0,  fn: shot15c, trans: 'bayer',  tdur: 0.50 },
  { id: 's16', t0: 95.0,  t1: 100.0, fn: shot16,  trans: 'bayer',  tdur: 0.55 },
  { id: 's17', t0: 100.0, t1: 108.5, fn: shot17,  trans: 'ichor',  tdur: 0.65 },
  { id: 's18', t0: 108.5, t1: 113.5, fn: shot18,  trans: 'bayer',  tdur: 0.50 },
  { id: 's19', t0: 113.5, t1: 120.0, fn: shot19,  trans: 'none',   tdur: 0.00 },
];

// Build deterministic frame-accurate sound event list (respects [22.5,25.0] and [100.0,102.4] true silences!)
function buildSoundEvents(timeline) {
  const ev = [];
  const push = (t, type, gain = 1.0, pan = 0.0, extra = {}) => ev.push({ t: +t.toFixed(3), type, gain, pan, ...extra });

  // Act I: Battle embers, feast clinks, departure footsteps, sword plant
  push(0.15, 'fire_swell', 0.85, 0.1);
  push(1.10, 'banner_snap', 0.75, 0.25);
  push(3.60, 'banner_snap', 0.65, 0.20);
  push(5.80, 'cut_drum', 0.85, 0.0);
  for (const ct of [6.4, 7.9, 9.5, 10.8]) push(ct, 'goblet_clink', 0.55, (ct % 2 === 0 ? -0.3 : 0.3));
  push(12.55, 'cup_set', 0.70, -0.2);
  for (let s = 13.1; s <= 16.4; s += 0.68) push(s, 'step_stone', 0.62, 0.15);
  push(17.40, 'sword_turf', 0.90, 0.10);
  push(18.30, 'armor_settle', 0.55, -0.1);

  // Act II: [22.5–25.0 TRUE SILENCE], broken at 25.00s by curse shudder; waking drip & gate creak J-cut
  push(25.00, 'curse_shudder', 1.00, 0.0);
  push(27.64, 'ichor_drip', 0.92, 0.05);
  push(28.35, 'armor_settle', 0.72, -0.1);
  push(29.80, 'sword_draw', 0.85, 0.15);
  push(32.50, 'gate_groan', 0.80, 0.0);
  push(37.40, 'chain_creak', 0.72, 0.28); // J-cut into dead street!

  // Act III: Deserted street steps, cottage wood creak, alley stop, slow bone-horror clicks & rasp
  for (let s = 38.4; s <= 44.6; s += 0.76) push(s, 'step_wet', 0.65, -0.1 + (s - 38.4) * 0.04);
  push(40.90, 'chain_creak', 0.65, 0.25);
  push(45.10, 'door_creak', 0.78, -0.3);
  for (let s = 46.1; s <= 49.4; s += 0.92) push(s, 'step_wood', 0.68, -0.1);
  push(48.80, 'ichor_hiss', 0.65, 0.32);
  for (let s = 51.7; s <= 53.5; s += 0.82) push(s, 'step_wet', 0.62, -0.25);
  // Footsteps freeze at 53.5s; slow anatomical mutation sounds:
  push(55.10, 'bone_shift', 0.88, 0.12);
  push(56.55, 'bone_shift', 0.94, 0.16);
  push(57.90, 'ichor_drip', 0.75, 0.18);
  push(58.45, 'hollow_rasp', 0.88, 0.14);
  push(60.00, 'sub_pulse', 0.85, 0.0);
  push(67.20, 'synth_riser', 0.80, 0.0); // J-cut into Act IV woods!

  // Act IV: Woods trek, mill ambush, acid block, heavy cleave, forge rune ignition, 3 boss montage hits
  for (let s = 68.3; s <= 75.0; s += 0.625) push(s, 'step_brush', 0.50, 0.0);
  push(76.15, 'beast_rasp', 0.90, 0.30);
  push(78.10, 'shield_acid', 0.95, 0.10);
  push(79.70, 'heavy_cleave', 1.00, 0.05);
  push(83.80, 'rune_ignite', 0.95, 0.0);
  push(88.50, 'boss_impact', 0.95, -0.15);
  push(90.70, 'belfry_toll', 0.95, 0.15);
  push(92.90, 'stone_crack', 0.92, 0.0);

  // Act V: [100.0–102.4 TRUE SILENCE], broken at 102.40s by colossal cathedral bell!
  push(102.40, 'cathedral_bell', 1.00, 0.0);
  push(108.55, 'hall_door', 0.78, 0.0);
  push(110.80, 'throne_shift', 0.75, 0.0);
  push(113.80, 'title_carve', 0.90, 0.0);

  // Subtle low stone resonance synced to caption cards (outside silences)
  for (const cap of timeline.captions) {
    push(cap.t0, 'caption_glyph', 0.42, 0.0);
  }
  return ev.sort((a, b) => a.t - b.t);
}

const timeline = await fetch('./timeline.json').then(r => r.json());
window.DUR = timeline.dur;
window.EV = buildSoundEvents(timeline);

function findShotIndex(t) {
  for (let i = 0; i < SHOTS.length; i++) {
    if (t < SHOTS[i].t1 || i === SHOTS.length - 1) return i;
  }
  return SHOTS.length - 1;
}

window.render = (t) => {
  t = clamp(t, 0, window.DUR);

  if (IS_SHEET) {
    const lut = renderModelSheet(fbOut);
    fbOut.present(imgData, lut);
    offCtx.putImageData(imgData, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(offCanvas, 0, 0, W * SCALE, H * SCALE);
    return;
  }

  if (IS_POSTER) {
    fbOut.clear(0);
    const lut = shot17(fbOut, 106.5);
    drawGothicText(fbOut, 'VALDRON', 135, 398, {
      scale: 3,
      tracking: 1,
      rowCols: [C.cstar, C.cice, C.silver, C.steel, C.cyan, C.cteal, C.stone1, C.slate1],
      outlineCol: 0,
      dissolve: 1.0,
      curseVein: true,
    });
    drawGothicText(fbOut, 'LUMROOK GAME STUDIO', 135, 434, {
      scale: 1,
      tracking: 1,
      dissolve: 1.0,
    });
    fbOut.present(imgData, lut);
    offCtx.putImageData(imgData, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(offCanvas, 0, 0, W * SCALE, H * SCALE);
    return;
  }

  const idx = findShotIndex(t);
  const sh = SHOTS[idx];
  fbA.clear(0);
  const lutA = sh.fn(fbA, t) || LUT.full;

  let activeLut = lutA;
  const rem = sh.t1 - t;
  if (sh.trans !== 'none' && sh.tdur > 0 && idx < SHOTS.length - 1 && rem <= sh.tdur) {
    const nextSh = SHOTS[idx + 1];
    const p = clamp(1 - rem / sh.tdur, 0, 1);
    fbB.clear(0);
    const lutB = nextSh.fn(fbB, Math.max(nextSh.t0, t)) || LUT.full;
    transitionFB(fbOut, fbA, fbB, p, sh.trans);
    activeLut = p < 0.5 ? lutA : lutB;
  } else {
    fbOut.d.set(fbA.d);
  }

  // Burn synchronized English caption card if active
  for (const cap of timeline.captions) {
    if (t >= cap.t0 && t <= cap.t1) {
      drawCaptionCard(fbOut, cap, t, false);
    }
  }

  fbOut.present(imgData, activeLut);
  offCtx.putImageData(imgData, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(offCanvas, 0, 0, W * SCALE, H * SCALE);
};

// Expose full, stable text bounding boxes in 1080×1920 viewport pixels for readcheck.mjs
window.TEXTS = (t) => {
  if (IS_SHEET) return [];
  const res = [];
  for (const cap of timeline.captions) {
    if (t >= cap.t0 && t <= cap.t1) {
      res.push(drawCaptionCard(fbOut, cap, t, true));
    }
  }
  for (const ti of timeline.titles) {
    if (t >= ti.t0 && t <= ti.t1) {
      const sc = ti.id === 'title_main' ? 4 : 1;
      const yTop = ti.id === 'title_main' ? 206 : 264;
      const { w, h } = measureLine(ti.text, sc, 1);
      const x0 = Math.round(135 - w / 2) * SCALE;
      res.push({
        id: ti.id,
        text: ti.text,
        x0,
        y0: yTop * SCALE,
        x1: x0 + w * SCALE,
        y1: (yTop + h) * SCALE,
      });
    }
  }
  return res;
};

window.render(0);
window.READY = true;
