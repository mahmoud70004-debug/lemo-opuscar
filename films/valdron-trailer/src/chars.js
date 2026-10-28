// chars.js — Sculpted dark-fantasy pixel rigs: Gothic Knight of Valdron, soldiers, uncanny mutated citizens & horrors
import { FB, C, T, bayer4, clamp, lerp, ss } from './px.js';

const spr = new FB(200, 240);

function blitOutlined(dst, ox, oy, w, h, rimCol = T, rimDir = -1) {
  // Pass 1: 4-neighbour 1-px obsidian outline
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      if (spr.d[y * spr.w + x] !== T) continue;
      if (
        spr.d[y * spr.w + (x - 1)] !== T ||
        spr.d[y * spr.w + (x + 1)] !== T ||
        spr.d[(y - 1) * spr.w + x] !== T ||
        spr.d[(y + 1) * spr.w + x] !== T
      ) {
        dst.px(ox + x, oy + y, C.void);
      }
    }
  }
  // Pass 2: Sprite interior + crisp 1-px directional rim highlight
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const c = spr.d[y * spr.w + x];
      if (c === T) continue;
      let outCol = c;
      if (rimCol !== T && spr.d[y * spr.w + (x + rimDir)] === T && spr.d[(y - 1) * spr.w + x] === T) {
        outCol = rimCol;
      }
      dst.px(ox + x, oy + y, outCol);
    }
  }
}

export function drawKnight(dst, cx, footY, opts = {}) {
  const {
    scale = 1.0,
    facing = 1,
    pose = 'idle',
    t = 0,
    prog = 0,
    rimCol = C.steel,
    runeSword = false,
  } = opts;

  const W0 = 160, H0 = 190;
  spr.w = W0; spr.h = H0; spr.clip = [0, 0, W0, H0];
  spr.clear(T);

  const sx = 80, sy = 158;
  const s = scale;
  const tStep = Math.floor(t * 8) / 8;
  const breath = Math.round(Math.sin(tStep * 2.4) * 0.8);

  // Ground contact shadow on destination buffer
  dst.ellipse(cx, footY + 1, Math.round(10 * s), Math.max(2, Math.round(2.5 * s)), C.void);

  if (facing === 0) {
    // —— SCULPTED BACK-VIEW GOTHIC KNIGHT ——
    const walkBob = pose === 'walk' ? Math.abs(Math.sin(tStep * 5.2)) * 2 * s : 0;
    const hipY = sy - 21 * s - walkBob;
    const shY = sy - 37 * s - walkBob + breath;
    const headY = shY - 8.5 * s;

    // Armored boots & greaves peeking below cloak
    const stride = pose === 'walk' ? Math.sin(tStep * 5.2) * 3.5 * s : 0;
    spr.capsule(sx - 4.2 * s, hipY + 8 * s, sx - 4.5 * s, sy - Math.max(0, stride), Math.max(1.6, 2.2 * s), C.slate1);
    spr.capsule(sx + 4.2 * s, hipY + 8 * s, sx + 4.5 * s, sy - Math.max(0, -stride), Math.max(1.6, 2.2 * s), C.stone0);
    spr.hline(sx - 6 * s, sx - 3 * s, sy, C.stone1);
    spr.hline(sx + 3 * s, sx + 6 * s, sy, C.stone1);

    // Greatsword / Moon-Runed Blade rising diagonally behind right shoulder
    const bladeCol = runeSword ? C.cice : C.stone2;
    spr.line(sx + 7 * s, shY - 15 * s, sx + 14 * s, sy - 4 * s, bladeCol, Math.max(1, Math.round(1.9 * s)));
    spr.line(sx + 3.5 * s, shY - 8 * s, sx + 12 * s, shY - 10 * s, C.stone3, Math.max(1, Math.round(1.4 * s)));
    spr.disc(sx + 6.3 * s, shY - 16 * s, Math.max(1.2, 1.5 * s), C.steel);
    if (runeSword) {
      spr.line(sx + 7.5 * s, shY - 12 * s, sx + 13 * s, sy - 9 * s, C.cstar, 1);
    }

    // Layered Gothic Cloak with vertical pleats & jagged tattered hem
    const wind = Math.sin(tStep * 3.1) * 3.5 * s + (pose === 'cliff' ? 6.5 * s : 1.8 * s);
    const hemL = sx - 11 * s + wind * 0.25;
    const hemR = sx + 12 * s + wind;
    spr.poly([
      [sx - 8.5 * s, shY],
      [sx + 8.5 * s, shY],
      [hemR, sy - 5 * s],
      [sx + 6 * s + wind * 0.85, sy - 2 * s],
      [sx + 1 * s + wind * 0.65, sy - 6 * s],
      [sx - 4 * s + wind * 0.45, sy - 2 * s],
      [hemL, sy - 5 * s],
    ], C.cloak0);
    // Cloak mid-tone pleats & moonlit left edge
    spr.poly([
      [sx - 7 * s, shY + 2 * s],
      [sx - 1 * s, shY + 2 * s],
      [sx - 2 * s + wind * 0.5, sy - 4 * s],
      [hemL + 1.5 * s, sy - 5 * s],
    ], C.cloak1);
    spr.line(sx - 7.5 * s, shY + 1 * s, hemL + 1 * s, sy - 5 * s, C.cloak2, Math.max(1, Math.round(s)));
    spr.line(sx + 2 * s, shY + 3 * s, sx + 5 * s + wind * 0.75, sy - 4 * s, C.cloak1, 1);

    // Integrated Hood/Cowl & Segmented Steel Pauldrons (tucked cleanly into shoulders)
    spr.poly([
      [sx - 9.5 * s, shY + 2 * s], [sx - 4 * s, shY - 2 * s],
      [sx + 4 * s, shY - 2 * s], [sx + 9.5 * s, shY + 2 * s],
      [sx + 6 * s, shY + 5 * s], [sx - 6 * s, shY + 5 * s],
    ], C.stone0);
    // Left & right pauldron lames
    spr.poly([[sx - 10 * s, shY + 3 * s], [sx - 8 * s, shY - 1 * s], [sx - 4 * s, shY], [sx - 5 * s, shY + 4 * s]], C.stone2);
    spr.poly([[sx + 10 * s, shY + 3 * s], [sx + 8 * s, shY - 1 * s], [sx + 4 * s, shY], [sx + 5 * s, shY + 4 * s]], C.stone1);
    spr.hline(sx - 9 * s, sx - 5 * s, shY, C.steel);

    // Pointed Gothic Sallet Helm (peaked ridge + flared neck-guard, never a plain oval)
    spr.poly([
      [sx, headY - 6.5 * s],
      [sx + 4.8 * s, headY - 1 * s],
      [sx + 5.6 * s, headY + 4.5 * s],
      [sx - 5.6 * s, headY + 4.5 * s],
      [sx - 4.8 * s, headY - 1 * s],
    ], C.stone1);
    spr.poly([
      [sx, headY - 6.5 * s],
      [sx - 4.6 * s, headY - 1 * s],
      [sx - 5.2 * s, headY + 4 * s],
      [sx - 0.5 * s, headY + 4 * s],
    ], C.stone2);
    spr.vline(sx, headY - 6 * s, headY + 4.5 * s, C.steel);
    // Flowing dark plume from crown
    spr.capsule(sx + 0.5 * s, headY - 5 * s, sx + 6.5 * s + wind * 0.45, headY - 0.5 * s, Math.max(1, 1.3 * s), C.cloak2);

    blitOutlined(dst, Math.round(cx - sx), Math.round(footY - sy), W0, H0, rimCol, -1);
    return;
  }

  // —— SIDE / 3-4 PROFILE GOTHIC KNIGHT ——
  const dir = facing >= 0 ? 1 : -1;

  if (pose === 'sleep') {
    const slBreath = Math.sin(t * 1.4) * 1.1 * s;
    const hipX = sx - 4 * dir * s, hipY = sy - 5 * s;
    const shX = sx - 9 * dir * s, shY = sy - 20 * s + slBreath;
    spr.poly([
      [shX - 6 * dir * s, shY],
      [hipX - 10 * dir * s, sy],
      [hipX + 13 * dir * s, sy],
      [hipX + 4 * dir * s, hipY - 3 * s],
    ], C.cloak0);
    spr.line(shX - 5 * dir * s, shY + 1 * s, hipX - 8 * dir * s, sy - 1 * s, C.cloak1, Math.max(1, Math.round(s)));
    spr.capsule(hipX, hipY, hipX + 9 * dir * s, hipY - 4.5 * s, 2.5 * s, C.stone0);
    spr.capsule(hipX + 9 * dir * s, hipY - 4.5 * s, hipX + 15 * dir * s, sy - 1 * s, 2.2 * s, C.stone1);
    spr.disc(hipX + 9 * dir * s, hipY - 5 * s, 1.8 * s, C.steel);
    spr.capsule(hipX, hipY, shX, shY, 4.5 * s, C.stone1);
    spr.poly([
      [shX - 3 * dir * s, shY - 1 * s], [shX + 3 * dir * s, shY - 1 * s],
      [shX + 4 * dir * s, shY + 4 * s], [shX - 3 * dir * s, shY + 4 * s],
    ], C.stone2);
    const hx = shX + 3 * dir * s, hy = shY - 5.2 * s + slBreath * 0.5;
    spr.poly([
      [hx - 1 * dir * s, hy - 5.5 * s],
      [hx + 6 * dir * s, hy + 0.5 * s],
      [hx + 2 * dir * s, hy + 4.5 * s],
      [hx - 5 * dir * s, hy + 3.5 * s],
      [hx - 4.5 * dir * s, hy - 2 * s],
    ], C.stone1);
    spr.line(hx - 1 * dir * s, hy - 5 * s, hx + 5.5 * dir * s, hy + 0.5 * s, C.steel, Math.max(1, Math.round(s)));
    spr.capsule(shX + 1 * dir * s, shY + 2 * s, hipX + 8 * dir * s, hipY - 4 * s, 1.8 * s, C.stone2);

    blitOutlined(dst, Math.round(cx - sx), Math.round(footY - sy), W0, H0, rimCol, -dir);
    return;
  }

  const walkPhase = tStep * 5.6;
  const isWalk = pose === 'walk' || pose === 'lantern';
  const stride = isWalk ? Math.sin(walkPhase) * 6.5 * s : (pose === 'cleave' ? 7.5 * s : pose === 'guard' ? -5.5 * s : 2.0 * s);
  const bob = isWalk ? Math.abs(Math.cos(walkPhase)) * 1.8 * s : 0;
  const crouch = pose === 'guard' ? 4 * s : pose === 'cleave' ? 3 * s : pose === 'wake' ? (1 - prog) * 10 * s : 0;

  const hipX = sx, hipY = sy - 21 * s + bob + crouch;
  const lean = pose === 'cleave' ? lerp(-4, 6.5, prog) * dir * s : pose === 'guard' ? -3 * dir * s : isWalk ? 1.5 * dir * s : 0;
  const shX = hipX + lean, shY = hipY - 15.5 * s + breath * 0.6;
  const headX = shX + 1.5 * dir * s, headY = shY - 8 * s;

  // 1. Flowing tattered cloak behind torso
  const wind = Math.sin(tStep * 3.4) * 3.5 * s + (isWalk ? 4.5 * s : 2.0 * s);
  spr.poly([
    [shX - 3.5 * dir * s, shY - 1 * s],
    [shX + 1.5 * dir * s, shY + 2 * s],
    [hipX - (6 * s + wind * 0.5) * dir, sy - 2 * s],
    [hipX - (10 * s + wind * 0.8) * dir, sy - 6 * s],
    [hipX - (15 * s + wind) * dir, sy - 4 * s],
  ], C.cloak0);
  spr.line(shX - 3 * dir * s, shY, hipX - (13 * s + wind * 0.85) * dir, sy - 4.5 * s, C.cloak1, Math.max(1, Math.round(1.3 * s)));

  // 2. Back leg + sabaton foot
  const bKneeX = hipX - stride * 0.45 * dir + 2 * dir * s;
  const bKneeY = hipY + 10.5 * s;
  const bFootX = hipX - stride * dir;
  const bFootY = sy - (isWalk && Math.cos(walkPhase) < 0 ? Math.abs(Math.cos(walkPhase)) * 2 * s : 0);
  spr.capsule(hipX - 1 * dir * s, hipY, bKneeX, bKneeY, 2.3 * s, C.slate1);
  spr.capsule(bKneeX, bKneeY, bFootX, bFootY - 1 * s, 1.9 * s, C.stone0);
  spr.poly([
    [bFootX - 2 * dir * s, bFootY], [bFootX + 5 * dir * s, bFootY], [bFootX + 2 * dir * s, bFootY - 2.5 * s],
  ], C.stone0);

  // 3. Secondary hand prop (lantern / goblet / kite shield)
  if (pose === 'lantern') {
    const lx = shX + 11.5 * dir * s, ly = shY + 5 * s + Math.sin(tStep * 4) * s;
    spr.capsule(shX + 2 * dir * s, shY + 1 * s, lx, ly - 2 * s, 1.8 * s, C.stone0);
    spr.rect(lx - 2 * s, ly, 4.5 * s, 6.5 * s, C.stone2);
    spr.rect(lx - 1 * s, ly + 1.5 * s, 2.5 * s, 3.5 * s, C.gold);
  } else if (pose === 'cup') {
    const drop = ss(0.15, 0.75, prog);
    const gx = shX + lerp(9, 6, drop) * dir * s;
    const gy = shY + lerp(-2, 9, drop) * s;
    spr.capsule(shX + 2 * dir * s, shY + 1 * s, gx, gy, 1.8 * s, C.stone1);
    spr.rect(gx - 1.5 * s, gy - 2 * s, 3 * s, 4.5 * s, C.amber);
  } else if (pose === 'guard') {
    const shdX = shX + 10 * dir * s, shdY = shY + 4 * s;
    spr.poly([
      [shdX - 1 * dir * s, shdY - 9 * s],
      [shdX + 4.5 * dir * s, shdY - 6 * s],
      [shdX + 3.5 * dir * s, shdY + 9 * s],
      [shdX - 1 * dir * s, shdY + 13 * s],
    ], C.stone2);
    spr.line(shdX + 2.5 * dir * s, shdY - 6 * s, shdX + 2 * dir * s, shdY + 9 * s, C.steel, Math.max(1, Math.round(s)));
  }

  // 4. Sculpted Gothic Cuirass, Belt & Tasset Plates
  spr.poly([
    [shX - 4.2 * dir * s, shY - 1 * s],
    [shX + 4.8 * dir * s, shY],
    [hipX + 4.0 * dir * s, hipY],
    [hipX - 4.0 * dir * s, hipY],
  ], C.stone1);
  // Breastplate breast-ridge & waist belt
  spr.line(shX + 3.5 * dir * s, shY + 1 * s, hipX + 2.8 * dir * s, hipY - 2 * s, C.stone3, Math.max(1, Math.round(1.2 * s)));
  spr.hline(hipX - 4.2 * s, hipX + 4.2 * s, hipY - 1 * s, C.wood1);
  // Layered hip tassets
  spr.poly([
    [hipX - 2 * dir * s, hipY], [hipX + 4.2 * dir * s, hipY],
    [hipX + 5 * dir * s, hipY + 5.5 * s], [hipX - 1.5 * dir * s, hipY + 5.5 * s],
  ], C.stone2);

  // 5. Front leg + knee poleyn + pointed steel sabaton
  const fKneeX = hipX + stride * 0.5 * dir + 2.5 * dir * s;
  const fKneeY = hipY + 10.5 * s;
  const fFootX = hipX + stride * dir;
  const fFootY = sy - (isWalk && Math.cos(walkPhase) > 0 ? Math.cos(walkPhase) * 2.2 * s : 0);
  spr.capsule(hipX + 1 * dir * s, hipY + 2 * s, fKneeX, fKneeY, 2.4 * s, C.stone1);
  spr.capsule(fKneeX, fKneeY, fFootX, fFootY - 1 * s, 2.1 * s, C.stone2);
  spr.tri(fKneeX, fKneeY - 2 * s, fKneeX + 3.5 * dir * s, fKneeY, fKneeX, fKneeY + 2 * s, C.steel);
  spr.poly([
    [fFootX - 2 * dir * s, fFootY], [fFootX + 6 * dir * s, fFootY], [fFootX + 2 * dir * s, fFootY - 3 * s],
  ], C.stone2);

  // 6. Sculpted Beaked Sallet Helm + Gorget + Plume
  spr.rect(headX - 3 * s, headY + 3 * s, 6 * s, 3 * s, C.stone0); // gorget neck
  spr.poly([
    [headX - 0.5 * dir * s, headY - 6 * s],
    [headX + 4.5 * dir * s, headY - 2.5 * s],
    [headX + 7.5 * dir * s, headY + 0.8 * s],
    [headX + 2.5 * dir * s, headY + 4.2 * s],
    [headX - 5.5 * dir * s, headY + 3.5 * s],
    [headX - 4.5 * dir * s, headY - 2.5 * s],
  ], C.stone2);
  spr.line(headX - 0.5 * dir * s, headY - 5.8 * s, headX + 6.8 * dir * s, headY + 0.4 * s, C.steel, Math.max(1, Math.round(s)));
  // Dark visor slit + cold ocular glint
  spr.hline(headX + 2 * dir * s, headX + 6.5 * dir * s, headY + 0.2 * s, C.void);
  spr.px(Math.round(headX + 3.8 * dir * s), Math.round(headY + 0.2 * s), runeSword ? C.cstar : C.silver);
  // Sweeping plume
  spr.capsule(headX - 2.5 * dir * s, headY - 4.5 * s, headX - (8.5 * s + wind * 0.4) * dir, headY - 0.5 * s, Math.max(1, 1.3 * s), C.cloak2);

  // 7. Three-lame Gothic Pauldron, Vambrace & Greatsword
  spr.poly([
    [shX - 4.2 * dir * s, shY - 1.5 * s],
    [shX + 3.2 * dir * s, shY - 1.5 * s],
    [shX + 3.8 * dir * s, shY + 4.2 * s],
    [shX - 3.5 * dir * s, shY + 4.2 * s],
  ], C.stone2);
  spr.hline(shX - 3.8 * s, shX + 3.0 * s, shY - 1 * s, C.steel);
  spr.hline(shX - 3.5 * s, shX + 3.2 * s, shY + 1.5 * s, C.stone0);

  let handX = shX + 5 * dir * s, handY = shY + 11 * s;
  let swordAng = 0.95;

  if (pose === 'cleave') {
    const swing = prog < 0.35
      ? lerp(-0.55, -0.95, prog / 0.35)
      : lerp(-0.95, 2.15, Math.pow((prog - 0.35) / 0.65, 0.55));
    swordAng = swing;
    handX = shX + Math.sin(swing + 0.4) * 9 * dir * s;
    handY = shY - Math.cos(swing + 0.4) * 8 * s + 3 * s;
  } else if (pose === 'relic') {
    const lift = ss(0.1, 0.65, prog);
    swordAng = lerp(1.2, 0.05, lift);
    handX = shX + lerp(6, 7.5, lift) * dir * s;
    handY = shY + lerp(9, -5, lift) * s;
  } else if (pose === 'guard') {
    swordAng = -0.35;
    handX = shX - 3 * dir * s;
    handY = shY + 6 * s;
  } else if (pose === 'wake') {
    swordAng = lerp(1.55, 0.65, prog);
    handX = shX + 6 * dir * s;
    handY = shY + lerp(14, 9, prog) * s;
  }

  spr.capsule(shX, shY + 2 * s, handX, handY, 1.9 * s, C.stone2);
  spr.disc(handX, handY, 1.8 * s, C.steel);

  const bladeLen = (runeSword ? 32 : 28) * s;
  const tipX = handX + Math.sin(swordAng) * bladeLen * dir;
  const tipY = handY - Math.cos(swordAng) * bladeLen;
  const perpX = Math.cos(swordAng) * 5 * s * dir;
  const perpY = Math.sin(swordAng) * 5 * s;

  spr.line(handX, handY, tipX, tipY, runeSword ? C.cice : C.stone3, Math.max(1, Math.round(2.1 * s)));
  spr.line(handX, handY, tipX, tipY, runeSword ? C.cstar : C.silver, 1);
  spr.line(handX - perpX, handY - perpY, handX + perpX, handY + perpY, C.stone2, Math.max(1, Math.round(1.5 * s)));

  if (pose === 'cleave' && prog > 0.36 && prog < 0.74) {
    for (let k = 1; k <= 5; k++) {
      const a2 = swordAng - k * 0.22;
      const tx2 = handX + Math.sin(a2) * bladeLen * dir;
      const ty2 = handY - Math.cos(a2) * bladeLen;
      spr.line(handX + Math.sin(a2) * 13 * s * dir, handY - Math.cos(a2) * 13 * s, tx2, ty2, runeSword ? C.cyan : C.silver, 1);
    }
  }

  blitOutlined(dst, Math.round(cx - sx), Math.round(footY - sy), W0, H0, rimCol, -dir);
}

export function drawKnightVisorClose(fb, cx, cy, t) {
  fb.ellipse(cx, cy, 66, 78, C.slate0);
  fb.ellipse(cx - 4, cy - 4, 60, 70, C.stone0);
  fb.poly([
    [cx - 56, cy - 18], [cx + 56, cy - 18],
    [cx + 64, cy + 16], [cx, cy + 40], [cx - 64, cy + 16],
  ], C.stone1);
  fb.vline(cx, cy - 72, cy + 38, C.stone3);
  fb.vline(cx - 1, cy - 72, cy + 38, C.steel);
  fb.line(cx - 54, cy - 8, cx, cy + 6, C.steel, 2);
  fb.line(cx + 54, cy - 8, cx, cy + 6, C.stone2, 2);

  fb.poly([[cx - 44, cy - 3], [cx - 6, cy + 6], [cx - 44, cy + 9]], C.void);
  fb.poly([[cx + 44, cy - 3], [cx + 6, cy + 6], [cx + 44, cy + 9]], C.void);

  const rx = Math.round(cx - 22 + Math.sin(t * 1.4) * 5);
  fb.disc(rx, cy + 3, 2, C.ichor3);
  fb.px(rx, cy + 3, C.ichor4);
  fb.disc(rx + 44, cy + 3, 2, C.ichor3);
  fb.px(rx + 44, cy + 3, C.ichor4);
  fb.line(cx - 48, cy + 18, cx - 16, cy + 29, C.ichor2, 2);

  const breath = 0.5 + 0.5 * Math.sin(t * 2.2);
  for (let i = 0; i < 4; i++) fb.disc(cx - 18 + i * 12, cy + 24 + (i % 2) * 5, 1.5, C.void);
  if (breath > 0.45) fb.fogLayer(cy + 28, cy + 76, t * 18, breath * 0.75, C.slate1, C.cteal, 41);
}

// Valdron soldier revelling in courtyard (tabard, kettle-helm, boots, raised goblet)
export function drawReveler(dst, cx, footY, scale = 1.0, phase = 0, t = 0) {
  const W0 = 90, H0 = 110;
  spr.w = W0; spr.h = H0; spr.clip = [0, 0, W0, H0];
  spr.clear(T);
  const sx = 45, sy = 96;
  const t8 = Math.floor((t + phase) * 8) / 8;
  const sway = Math.sin(t8 * 3.8 + phase * 5) * 2.2 * scale;
  const toast = 0.5 + 0.5 * Math.sin(t8 * 3.2 + phase * 3);

  dst.ellipse(cx, footY + 1, Math.round(7 * scale), 2, C.void);

  // Boots & mail chausses
  spr.capsule(sx - 3.2 * scale, sy - 15 * scale, sx - 4 * scale, sy, 2 * scale, C.stone0);
  spr.capsule(sx + 3.2 * scale, sy - 15 * scale, sx + 4 * scale, sy, 2 * scale, C.wood1);
  // Valdron crimson-amber surcoat tabard + belt
  spr.poly([
    [sx - 6.5 * scale + sway * 0.5, sy - 31 * scale],
    [sx + 6.5 * scale + sway * 0.5, sy - 31 * scale],
    [sx + 7.5 * scale, sy - 13 * scale],
    [sx - 7.5 * scale, sy - 13 * scale],
  ], C.rustW);
  spr.hline(sx - 6.5 * scale, sx + 6.5 * scale, sy - 20 * scale, C.wood0);
  spr.vline(sx + sway * 0.3, sy - 30 * scale, sy - 14 * scale, C.amber);

  // Head & steel kettle-helm brim
  spr.disc(sx + sway * 0.7, sy - 35.5 * scale, 3.8 * scale, C.flesh);
  spr.poly([
    [sx - 6 * scale + sway * 0.7, sy - 37 * scale],
    [sx + 6 * scale + sway * 0.7, sy - 37 * scale],
    [sx + 3 * scale + sway * 0.7, sy - 41 * scale],
    [sx - 3 * scale + sway * 0.7, sy - 41 * scale],
  ], C.stone2);

  // Raised arm & golden goblet
  const gx = sx + (8 + toast * 3) * scale + sway;
  const gy = sy - (31 + toast * 11) * scale;
  spr.capsule(sx + 4.5 * scale + sway * 0.5, sy - 29 * scale, gx, gy, 1.7 * scale, C.stone1);
  spr.poly([
    [gx - 2 * scale, gy - 4 * scale], [gx + 2 * scale, gy - 4 * scale],
    [gx + 1 * scale, gy], [gx - 1 * scale, gy],
  ], C.gold);

  blitOutlined(dst, Math.round(cx - sx), Math.round(footY - sy), W0, H0, C.flame, 1);
}

// UNCANNY BODY-HORROR CITIZEN (Shot 10 centerpiece)
export function drawAlleyMutant(dst, cx, footY, scale = 1.4, mut = 0, t = 0) {
  const W0 = 140, H0 = 200;
  spr.w = W0; spr.h = H0; spr.clip = [0, 0, W0, H0];
  spr.clear(T);

  const sx = 70, sy = 180;
  const m = clamp(mut, 0, 1);
  const twitch = m > 0.05 ? Math.sin(Math.floor(t * 12) * 2.9) * m * 1.4 * scale : 0;

  dst.ellipse(cx, footY + 1, Math.round(9 * scale), 2, C.void);

  const stretch = m * 18 * scale;
  const waistY = sy - 24 * scale - stretch * 0.35;
  const chestY = waistY - 16 * scale - stretch * 0.65;

  // Tattered shawl skirt with ragged hem
  spr.poly([
    [sx - 6 * scale, waistY],
    [sx + 6 * scale, waistY],
    [sx + 9 * scale, sy],
    [sx + 3 * scale, sy - 2 * scale],
    [sx - 2 * scale, sy],
    [sx - 8 * scale, sy - 1 * scale],
  ], C.slate0);
  spr.line(sx - 2 * scale, waistY + 2, sx - 4 * scale, sy - 1, C.slate1, 1);

  // Elongating spine & pale protruding rib-spurs
  spr.capsule(sx, waistY, sx + twitch * 0.5, chestY, lerp(5.5, 3.8, m) * scale, C.cloak0);
  if (m > 0.3) {
    for (let i = 0; i < 4; i++) {
      const ry = lerp(chestY + 4 * scale, waistY - 3 * scale, i / 3);
      const ribSpan = (m - 0.3) * 8 * scale * (1 - i * 0.14);
      spr.line(sx - ribSpan, ry, sx + ribSpan * 1.2, ry - 1.5 * scale, C.flesh, 1);
      spr.px(Math.round(sx), Math.round(ry), C.ichor2);
    }
  }

  const lShX = sx - 6.5 * scale + twitch * 0.4;
  const lShY = chestY - m * 4 * scale;
  const rShX = sx + 6.5 * scale + twitch * 0.4;
  const rShY = chestY + m * 5 * scale;
  spr.line(lShX, lShY, rShX, rShY, C.cloak1, Math.max(1, Math.round(2.5 * scale)));

  const lHandX = lShX - lerp(2, 7, m) * scale;
  const lHandY = lShY + lerp(14, 21, m) * scale;
  spr.capsule(lShX, lShY, lHandX, lHandY, 1.6 * scale, C.slate1);

  const rElbX = rShX + lerp(1.5, 5.5, m) * scale;
  const rElbY = rShY + lerp(9, 19, m) * scale;
  const rWristX = rElbX + lerp(-0.5, 2.5, m) * scale + twitch;
  const rWristY = rElbY + lerp(8, 22, m) * scale;
  spr.capsule(rShX, rShY, rElbX, rElbY, 1.6 * scale, C.slate1);
  spr.capsule(rElbX, rElbY, rWristX, rWristY, 1.3 * scale, m > 0.4 ? C.flesh : C.slate1);

  if (m > 0.25) {
    const fLen = lerp(2, 9, m) * scale;
    for (let f = -1; f <= 1; f++) {
      const fx = rWristX + f * 2.6 * scale + Math.sin(t * 9 + f * 2) * m * scale;
      const fy = rWristY + fLen + (f === 0 ? 2 * scale : 0);
      spr.line(rWristX, rWristY, fx, fy, C.flesh, 1);
      if (m > 0.55) spr.px(Math.round(fx), Math.round(fy + 1), C.ichor3);
    }
    const dripPhase = (t * 1.3) % 1;
    const dripY = lerp(rWristY + fLen, sy, dripPhase * dripPhase);
    if (m > 0.5) spr.px(Math.round(rWristX), Math.round(dripY), C.ichor4);
  }

  const neckLen = lerp(3, 10, m) * scale;
  const tiltAng = lerp(0.03, 0.78, m);
  const headX = sx + Math.sin(tiltAng) * neckLen + twitch * 0.7;
  const headY = chestY - Math.cos(tiltAng) * neckLen - 3 * scale;
  spr.capsule(sx, chestY, headX, headY + 2 * scale, 1.7 * scale, m > 0.35 ? C.flesh : C.cloak0);
  spr.ellipse(headX, headY, 4.4 * scale, 5.2 * scale, C.cloak0);
  spr.line(headX - 3 * scale, headY - 3 * scale, headX + 3 * scale, headY + 2 * scale, C.cloak1, 1);

  if (m > 0.68) {
    const ex = Math.round(sx + 3 * scale), ey = Math.round(chestY - 3 * scale);
    spr.px(ex, ey, C.ichor4);
    spr.px(ex + 2, ey - 3, C.cstar);
    spr.px(Math.round(headX + 2 * scale), Math.round(headY + 1 * scale), C.ichor3);
  }

  blitOutlined(dst, Math.round(cx - sx), Math.round(footY - sy), W0, H0, m > 0.4 ? C.ichor2 : C.slate1, 1);
}

export function drawCrookedWatcher(fb, cx, footY, h = 42, variant = 0, t = 0) {
  const sway = Math.sin(t * 1.7 + variant * 2.1) * 1.5;
  const midY = footY - h * 0.54;
  const shY = footY - h * 0.84;
  fb.line(cx - h * 0.1, footY, cx - h * 0.16, midY, C.void, 2);
  fb.line(cx - h * 0.16, midY, cx + sway * 0.4, shY + h * 0.16, C.void, 2);
  fb.line(cx + h * 0.1, footY, cx + h * 0.18, midY + 3, C.void, 2);
  fb.line(cx + h * 0.18, midY + 3, cx + sway * 0.4, shY + h * 0.16, C.void, 2);
  fb.capsule(cx + sway * 0.4, shY + h * 0.16, cx + sway, shY, Math.max(1.5, h * 0.065), C.slate0);
  fb.line(cx - h * 0.12 + sway, shY + 2, cx - h * 0.17 + sway, footY - h * 0.18, C.void, 1);
  fb.line(cx + h * 0.12 + sway, shY + 2, cx + h * 0.20 + sway, footY - h * 0.12, C.void, 1);
  const hx = cx + sway + h * 0.08, hy = shY - h * 0.11;
  fb.ellipse(hx, hy, Math.max(2, h * 0.07), Math.max(2.5, h * 0.09), C.void);
  if (variant === 1) {
    fb.line(hx - 2, hy - 2, hx - h * 0.18, hy - h * 0.24, C.void, 1);
    fb.line(hx - h * 0.10, hy - h * 0.13, hx - h * 0.05, hy - h * 0.26, C.void, 1);
    fb.line(hx + 2, hy - 2, hx + h * 0.22, hy - h * 0.26, C.void, 1);
  }
  fb.px(Math.round(hx + 1), Math.round(hy), C.ichor4);
  fb.px(Math.round(hx - 2), Math.round(hy + 1), C.ichor3);
}

// Sculpted Split-Ribbed Mill Horror (gnarled digitigrade haunches, ragged miller apron, bone mandibles)
export function drawMillBeast(dst, cx, footY, scale = 1.25, lunge = 0, recoil = 0, t = 0) {
  const W0 = 160, H0 = 170;
  spr.w = W0; spr.h = H0; spr.clip = [0, 0, W0, H0];
  spr.clear(T);
  const sx = 82 + (-lunge * 14 + recoil * 12) * scale, sy = 152;
  const pulse = Math.sin(t * 7) * 1.5 * scale;

  dst.ellipse(cx + Math.round((-lunge * 14 + recoil * 12) * scale), footY + 1, Math.round(16 * scale), 3, C.void);

  // Digitigrade crooked haunches & tattered miller apron strips
  const hipY = sy - 24 * scale;
  // Back haunch
  spr.capsule(sx - 5 * scale, hipY, sx - 13 * scale, sy - 11 * scale, 2.8 * scale, C.slate0);
  spr.capsule(sx - 13 * scale, sy - 11 * scale, sx - 10 * scale, sy, 2.0 * scale, C.void);
  // Front haunch
  spr.capsule(sx + 6 * scale, hipY, sx + 15 * scale, sy - 12 * scale, 3.2 * scale, C.cloak0);
  spr.capsule(sx + 15 * scale, sy - 12 * scale, sx + 12 * scale, sy, 2.2 * scale, C.slate1);
  // Ragged cloth strips hanging between legs
  spr.poly([[sx - 6 * scale, hipY], [sx + 6 * scale, hipY], [sx + 2 * scale, sy - 4 * scale], [sx - 4 * scale, sy - 6 * scale]], C.slate0);

  // Embedded splintered wooden mill-wheel rim & spokes fused into right shoulder
  const wx = sx + 8 * scale, wy = sy - 39 * scale, wr = 17 * scale;
  for (let a = 0; a < 7; a++) {
    const ang = a * 0.9 + t * 0.6;
    const ex = wx + Math.cos(ang) * wr, ey = wy + Math.sin(ang) * wr;
    spr.line(wx, wy, ex, ey, C.wood1, 2);
    spr.line(ex, ey, wx + Math.cos(ang + 0.5) * wr, wy + Math.sin(ang + 0.5) * wr, C.wood2, 1);
  }

  // Arched grotesque torso & dorsal spine spikes
  spr.poly([
    [sx - 11 * scale, sy - 34 * scale],
    [sx - 2 * scale, sy - 48 * scale],
    [sx + 12 * scale, sy - 42 * scale],
    [sx + 9 * scale, hipY],
    [sx - 8 * scale, hipY],
  ], C.cloak0);
  for (let sp = 0; sp < 4; sp++) {
    const px = sx + (-1 + sp * 3.5) * scale, py = sy - (47 - sp * 2) * scale;
    spr.tri(px - 2, py + 3, px + 2, py + 3, px + 2, py - 4 * scale, C.flesh);
  }

  // Split ribcage glowing with cursed Loris ichor + pale bone fronds
  spr.ellipse(sx - 4 * scale, sy - 33 * scale, 5.5 * scale, 8.5 * scale + pulse * 0.3, C.ichor2);
  spr.disc(sx - 5 * scale, sy - 33 * scale, 3 * scale, C.ichor4);
  for (let r = -2; r <= 2; r++) {
    const ry = sy - (33 + r * 3.6) * scale;
    spr.line(sx + 2 * scale, ry, sx - (12 + lunge * 4) * scale, ry - 1.5 * scale, C.silver, 1);
  }

  // Two asymmetric forelimbs: one dragging iron chain, one hyper-extended claw lunging left
  const elbX = sx - (12 + lunge * 6) * scale, elbY = sy - 32 * scale;
  const clawX = sx - (22 + lunge * 12) * scale, clawY = sy - (25 - lunge * 5) * scale;
  spr.capsule(sx - 5 * scale, sy - 40 * scale, elbX, elbY, 2.4 * scale, C.cloak1);
  spr.capsule(elbX, elbY, clawX, clawY, 2.0 * scale, C.flesh);
  for (let k = -1; k <= 1; k++) {
    spr.line(clawX, clawY, clawX - 8 * scale, clawY + k * 4.2 * scale, C.silver, 1);
    spr.px(Math.round(clawX - 8 * scale), Math.round(clawY + k * 4.2 * scale), C.ichor4);
  }

  // Twisted inverted villager head fused sideways at collar
  spr.ellipse(sx - 8 * scale, sy - 46 * scale, 4.8 * scale, 4.2 * scale, C.flesh);
  spr.hline(sx - 12 * scale, sx - 6 * scale, sy - 44 * scale, C.void); // gaping jaw
  spr.px(Math.round(sx - 10 * scale), Math.round(sy - 47 * scale), C.ichor4);
  spr.px(Math.round(sx - 8 * scale), Math.round(sy - 46 * scale), C.cstar);

  blitOutlined(dst, Math.round(cx - 82), Math.round(footY - sy), W0, H0, recoil > 0.2 ? C.cstar : C.ichor3, -1);
}
