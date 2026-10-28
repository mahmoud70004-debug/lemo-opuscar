// px.js — 270×480 indexed dark-fantasy pixel engine (×4 nearest-neighbour → 1080×1920)
export const W = 270, H = 480, SCALE = 4;
export const T = 255;

// 48-colour Gothic Nocturnal Master Palette
// Inspired by the nocturnal midnight/cyan/moss aesthetic + warm torchlight Act I + protected curse greens & arterial rust
export const HEX = [
  // 0–7: Abyss & Midnight Sky ramp
  '#03050a', '#070c18', '#0c162b', '#132444', '#1d3863', '#2b548a', '#457cb5', '#73aed9',
  // 8–12: Astral Cyan Moon & Star ramp
  '#153e54', '#246d8c', '#3fa4c9', '#7adbf0', '#dcfbff',
  // 13–19: Obsidian & Gothic Stone ramp
  '#090b10', '#131822', '#1f2736', '#303b4f', '#46546e', '#667794', '#92a3bd',
  // 20–24: Desolate Moorland Moss & Night Grass ramp
  '#08130f', '#10241c', '#1c3b2d', '#2e5942', '#497d5e',
  // 25–32: Timber, Ember & Victory Torchlight ramp
  '#1b0f0b', '#331c13', '#572f1c', '#854825', '#bc6b2b', '#ed9b3b', '#ffd369', '#fff3bd',
  // 33–38: Muted Flesh, Cloak Indigo & Pale Steel ramp
  '#1c1624', '#33283d', '#54435e', '#827187', '#b8c3d1', '#eaf2fa',
  // 39–41: PROTECTED Dried Blood & Arterial Rust (survives cold collapse)
  '#29060b', '#5c0e17', '#9c1c27',
  // 42–46: PROTECTED Cursed Loris Ichor Green (exempt from all desaturation/collapse)
  '#092112', '#144725', '#27823e', '#58cf62', '#b8ff9e',
  // 47: Crisp Bone-Silver Caption Ink
  '#dde7f2',
];

export const C = {
  void: 0, abyss: 1, night: 2, indigo: 3, dusk: 4, royal: 5, sky: 6, mistB: 7,
  cdeep: 8, cteal: 9, cyan: 10, cice: 11, cstar: 12,
  ink: 13, slate0: 14, slate1: 15, stone0: 16, stone1: 17, stone2: 18, stone3: 19,
  moss0: 20, moss1: 21, moss2: 22, moss3: 23, moss4: 24,
  wood0: 25, wood1: 26, wood2: 27, rustW: 28, amber: 29, flame: 30, gold: 31, spark: 32,
  cloak0: 33, cloak1: 34, cloak2: 35, flesh: 36, steel: 37, silver: 38,
  blood0: 39, blood1: 40, blood2: 41,
  ichor0: 42, ichor1: 43, ichor2: 44, ichor3: 45, ichor4: 46,
  text: 47,
};

export const NPAL = HEX.length;
export const PROTECT = new Set([39, 40, 41, 42, 43, 44, 45, 46, 47]);

const hexToRgb = h => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
export const RGB = HEX.map(hexToRgb);
const lum = ([r, g, b]) => 0.299 * r + 0.587 * g + 0.114 * b;
export const pack = (r, g, b) => (255 << 24) | ((b & 255) << 16) | ((g & 255) << 8) | (r & 255);

function lutFrom(fn) {
  const L = new Uint32Array(256);
  for (let i = 0; i < NPAL; i++) {
    const [r, g, b] = fn(i);
    L[i] = pack(r, g, b);
  }
  return L;
}

// Lookup Tables for mood & palette-collapse native moves
export const LUT = {};
LUT.full = lutFrom(i => RGB[i]);

// Warm feast grade: deepens shadows slightly warm
LUT.feast = lutFrom(i => {
  if (PROTECT.has(i)) return RGB[i];
  const [r, g, b] = RGB[i];
  return [Math.min(255, Math.round(r * 1.06 + 4)), Math.round(g * 0.99), Math.round(b * 0.92)];
});

// Corpse-cold post-curse LUT: warm wood/fire hues drained into moonlit slate, while blood & green ichor stay vivid
const CORPSE_RAMP = [
  [4, 7, 13], [10, 16, 28], [18, 28, 45], [30, 44, 66],
  [46, 65, 92], [70, 94, 124], [104, 132, 163], [156, 184, 212],
];
LUT.corpse = lutFrom(i => {
  if (PROTECT.has(i)) return RGB[i];
  // Preserve cyan moon & moss subtle separation, drain warm fire/wood (25..32) completely
  const [r, g, b] = RGB[i];
  if (i >= 25 && i <= 32) {
    const idx = Math.min(7, Math.floor(Math.pow(lum([r, g, b]) / 255, 0.82) * 7.6));
    return CORPSE_RAMP[idx];
  }
  return [Math.round(r * 0.84), Math.round(g * 0.93), Math.min(255, Math.round(b * 1.06))];
});

// 5-step collapse sequence between feast and corpse (used in Shot 05 curse shockwave)
LUT.collapse = [0, 0.25, 0.5, 0.75, 1.0].map(k => lutFrom(i => {
  if (PROTECT.has(i)) return RGB[i];
  const a = RGB[i];
  const bIdx = Math.min(7, Math.floor(Math.pow(lum(a) / 255, 0.82) * 7.6));
  const b = (i >= 25 && i <= 32) ? CORPSE_RAMP[bIdx] : [a[0] * 0.84, a[1] * 0.93, Math.min(255, a[2] * 1.06)];
  return [
    Math.round(a[0] + (b[0] - a[0]) * k),
    Math.round(a[1] + (b[1] - a[1]) * k),
    Math.round(a[2] + (b[2] - a[2]) * k),
  ];
}));

// Step-fade darkening (integer palette steps, never alpha)
export function stepFade(baseLut, darkSteps) {
  // darkSteps: 0 (normal) to 4 (pure black)
  const s = Math.max(0, Math.min(4, Math.round(darkSteps)));
  if (s === 0) return baseLut;
  if (s === 4) {
    const Z = new Uint32Array(256);
    Z.fill(pack(0, 0, 0));
    return Z;
  }
  const mul = [1, 0.72, 0.44, 0.18, 0][s];
  const O = new Uint32Array(256);
  for (let i = 0; i < NPAL; i++) {
    const v = baseLut[i];
    const r = v & 255, g = (v >> 8) & 255, b = (v >> 16) & 255;
    O[i] = pack(Math.round(r * mul), Math.round(g * mul), Math.round(b * mul));
  }
  return O;
}

// Index-stepping lighting tables (moves a surface colour one step brighter along its material ramp, or toward warm torch / green curse)
export const LIGHT_COOL = new Uint8Array(256);
export const LIGHT_WARM = new Uint8Array(256);
export const LIGHT_ICHOR = new Uint8Array(256);
export const DARK_STEP = new Uint8Array(256);
for (let i = 0; i < 256; i++) { LIGHT_COOL[i] = i; LIGHT_WARM[i] = i; LIGHT_ICHOR[i] = i; DARK_STEP[i] = i; }

const RAMPS = [
  [0, 1, 2, 3, 4, 5, 6, 7],
  [8, 9, 10, 11, 12],
  [13, 14, 15, 16, 17, 18, 19],
  [20, 21, 22, 23, 24],
  [25, 26, 27, 28, 29, 30, 31, 32],
  [33, 34, 35, 36, 37, 38],
  [39, 40, 41],
  [42, 43, 44, 45, 46],
];
for (const r of RAMPS) {
  for (let k = 0; k < r.length; k++) {
    LIGHT_COOL[r[k]] = r[Math.min(r.length - 1, k + 1)];
    DARK_STEP[r[k]] = r[Math.max(0, k - 1)];
  }
}
// Warm remap for torchlight so grass/stone warms toward amber rather than turning neon
for (let i = 0; i < NPAL; i++) {
  if (i >= 20 && i <= 24) LIGHT_WARM[i] = 26 + Math.min(4, i - 20);
  else if (i >= 13 && i <= 19) LIGHT_WARM[i] = 25 + Math.min(6, i - 13);
  else if (i >= 0 && i <= 7) LIGHT_WARM[i] = 25 + Math.min(5, i);
  else LIGHT_WARM[i] = LIGHT_COOL[i];
}
// Curse green remap for eerie emerald glow on stone, fog, and armor
for (let i = 0; i < NPAL; i++) {
  if (i >= 42 && i <= 46) LIGHT_ICHOR[i] = Math.min(46, i + 1);
  else {
    const l = lum(RGB[i]);
    LIGHT_ICHOR[i] = l < 35 ? 42 : l < 75 ? 43 : l < 130 ? 44 : l < 190 ? 45 : 46;
  }
}

// 4×4 and 8×8 Bayer ordered dither matrices
const B4 = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];
export const bayer4 = (x, y) => (B4[((y & 3) << 2) | (x & 3)] + 0.5) / 16;

const B8 = [
  0, 32, 8, 40, 2, 34, 10, 42,
  48, 16, 56, 24, 50, 18, 58, 26,
  12, 44, 4, 36, 14, 46, 6, 38,
  60, 28, 52, 20, 62, 30, 54, 22,
  3, 35, 11, 43, 1, 33, 9, 41,
  51, 19, 59, 27, 49, 17, 57, 25,
  15, 47, 7, 39, 13, 45, 5, 37,
  63, 31, 55, 23, 61, 29, 53, 21,
];
export const bayer8 = (x, y) => (B8[((y & 7) << 3) | (x & 7)] + 0.5) / 64;

// Deterministic hash & smooth noise
export function hash2(x, y = 0, z = 0) {
  let h = (Math.imul(x | 0, 374761393) + Math.imul(y | 0, 668265263) + Math.imul(z | 0, 2147483647)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}
export function noise1(x, seed = 0) {
  const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f);
  return hash2(i, seed) * (1 - u) + hash2(i + 1, seed) * u;
}
export function noise2(x, y, seed = 0) {
  const ix = Math.floor(x), iy = Math.floor(y);
  const fx = x - ix, fy = y - iy;
  const ux = fx * fx * (3 - 2 * fx), uy = fy * fy * (3 - 2 * fy);
  const a = hash2(ix, iy, seed), b = hash2(ix + 1, iy, seed);
  const c = hash2(ix, iy + 1, seed), d = hash2(ix + 1, iy + 1, seed);
  return (a * (1 - ux) + b * ux) * (1 - uy) + (c * (1 - ux) + d * ux) * uy;
}

export const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
export const lerp = (a, b, t) => a + (b - a) * t;
export const seg = (t, a, b) => clamp((t - a) / (b - a), 0, 1);
export const ss = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
export const eo = t => { t = clamp(t, 0, 1); return 1 - (1 - t) * (1 - t) * (1 - t); };
export const ei = t => { t = clamp(t, 0, 1); return t * t * t; };
export const eio = t => { t = clamp(t, 0, 1); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
export const mod = (n, m) => ((n % m) + m) % m;

// Indexed Framebuffer
export class FB {
  constructor(w = W, h = H) {
    this.w = w;
    this.h = h;
    this.d = new Uint8Array(w * h);
    this.clip = [0, 0, w, h];
  }

  clear(c = 0) { this.d.fill(c); }

  px(x, y, c) {
    if (c === T) return;
    x = x | 0; y = y | 0;
    const [cx, cy, cw, ch] = this.clip;
    if (x < cx || y < cy || x >= cw || y >= ch) return;
    this.d[y * this.w + x] = c;
  }

  get(x, y) {
    x = x | 0; y = y | 0;
    if (x < 0 || y < 0 || x >= this.w || y >= this.h) return 0;
    return this.d[y * this.w + x];
  }

  rect(x, y, w, h, c) {
    if (c === T || w <= 0 || h <= 0) return;
    const x0 = Math.max(this.clip[0], Math.round(x));
    const y0 = Math.max(this.clip[1], Math.round(y));
    const x1 = Math.min(this.clip[2], Math.round(x + w));
    const y1 = Math.min(this.clip[3], Math.round(y + h));
    if (x1 <= x0 || y1 <= y0) return;
    for (let py = y0; py < y1; py++) {
      this.d.fill(c, py * this.w + x0, py * this.w + x1);
    }
  }

  hline(x0, x1, y, c) {
    if (c === T) return;
    y = Math.round(y);
    if (y < this.clip[1] || y >= this.clip[3]) return;
    const a = Math.max(this.clip[0], Math.round(Math.min(x0, x1)));
    const b = Math.min(this.clip[2] - 1, Math.round(Math.max(x0, x1)));
    if (a <= b) this.d.fill(c, y * this.w + a, y * this.w + b + 1);
  }

  vline(x, y0, y1, c) {
    if (c === T) return;
    x = Math.round(x);
    if (x < this.clip[0] || x >= this.clip[2]) return;
    const a = Math.max(this.clip[1], Math.round(Math.min(y0, y1)));
    const b = Math.min(this.clip[3] - 1, Math.round(Math.max(y0, y1)));
    for (let y = a; y <= b; y++) this.d[y * this.w + x] = c;
  }

  line(x0, y0, x1, y1, c, thick = 1) {
    x0 = Math.round(x0); y0 = Math.round(y0);
    x1 = Math.round(x1); y1 = Math.round(y1);
    const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0);
    const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
    let err = dx + dy;
    const r = thick >> 1;
    for (;;) {
      if (thick <= 1) this.px(x0, y0, c);
      else this.rect(x0 - r, y0 - r, thick, thick, c);
      if (x0 === x1 && y0 === y1) break;
      const e2 = 2 * err;
      if (e2 >= dy) { err += dy; x0 += sx; }
      if (e2 <= dx) { err += dx; y0 += sy; }
    }
  }

  capsule(x0, y0, x1, y1, r, c) {
    x0 = Math.round(x0); y0 = Math.round(y0);
    x1 = Math.round(x1); y1 = Math.round(y1);
    const steps = Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0)));
    for (let i = 0; i <= steps; i++) {
      const u = i / steps;
      this.disc(Math.round(x0 + (x1 - x0) * u), Math.round(y0 + (y1 - y0) * u), r, c);
    }
  }

  disc(cx, cy, r, c) {
    if (c === T || r < 0) return;
    cx = Math.round(cx); cy = Math.round(cy);
    const ri = Math.ceil(r), rr = r * r + r * 0.55;
    for (let dy = -ri; dy <= ri; dy++) {
      const dxMax = Math.floor(Math.sqrt(Math.max(0, rr - dy * dy)));
      this.hline(cx - dxMax, cx + dxMax, cy + dy, c);
    }
  }

  ellipse(cx, cy, rx, ry, c) {
    if (c === T || rx <= 0 || ry <= 0) return;
    cx = Math.round(cx); cy = Math.round(cy);
    const ryi = Math.ceil(ry);
    for (let dy = -ryi; dy <= ryi; dy++) {
      const u = dy / ry;
      if (Math.abs(u) > 1) continue;
      const dx = Math.floor(rx * Math.sqrt(1 - u * u));
      this.hline(cx - dx, cx + dx, cy + dy, c);
    }
  }

  tri(x0, y0, x1, y1, x2, y2, c) {
    if (c === T) return;
    const minX = Math.max(this.clip[0], Math.floor(Math.min(x0, x1, x2)));
    const maxX = Math.min(this.clip[2] - 1, Math.ceil(Math.max(x0, x1, x2)));
    const minY = Math.max(this.clip[1], Math.floor(Math.min(y0, y1, y2)));
    const maxY = Math.min(this.clip[3] - 1, Math.ceil(Math.max(y0, y1, y2)));
    const area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0);
    if (Math.abs(area) < 0.001) return;
    const s = area > 0 ? 1 : -1;
    for (let y = minY; y <= maxY; y++) {
      for (let x = minX; x <= maxX; x++) {
        const px = x + 0.5, py = y + 0.5;
        const w0 = ((x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)) * s;
        const w1 = ((x0 - x2) * (py - y2) - (y0 - y2) * (px - x2)) * s;
        const w2 = ((x1 - x0) * (py - y0) - (y1 - y0) * (px - x0)) * s;
        if (w0 >= 0 && w1 >= 0 && w2 >= 0) this.d[y * this.w + x] = c;
      }
    }
  }

  poly(pts, c) {
    if (pts.length < 3 || c === T) return;
    for (let i = 1; i < pts.length - 1; i++) {
      this.tri(pts[0][0], pts[0][1], pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], c);
    }
  }

  // Vertical multi-stop Bayer-dithered gradient
  vgrad(y0, y1, stops, x0 = 0, x1 = this.w) {
    const ya = Math.max(this.clip[1], Math.round(y0));
    const yb = Math.min(this.clip[3], Math.round(y1));
    const xa = Math.max(this.clip[0], Math.round(x0));
    const xb = Math.min(this.clip[2], Math.round(x1));
    const n = stops.length - 1;
    for (let y = ya; y < yb; y++) {
      const u = clamp((y - y0) / Math.max(1, y1 - y0), 0, 0.9999) * n;
      const idx = Math.floor(u), f = u - idx;
      const cA = stops[idx], cB = stops[idx + 1];
      for (let x = xa; x < xb; x++) {
        this.d[y * this.w + x] = bayer4(x, y) < f ? cB : cA;
      }
    }
  }

  // Radial index-stepping light halo (torchlight, curse flare, cyan moon aura, rune blade)
  lightHalo(cx, cy, rInner, rOuter, table = LIGHT_WARM, doubleInner = true) {
    cx = Math.round(cx); cy = Math.round(cy);
    const x0 = Math.max(this.clip[0], Math.floor(cx - rOuter));
    const x1 = Math.min(this.clip[2] - 1, Math.ceil(cx + rOuter));
    const y0 = Math.max(this.clip[1], Math.floor(cy - rOuter));
    const y1 = Math.min(this.clip[3] - 1, Math.ceil(cy + rOuter));
    for (let y = y0; y <= y1; y++) {
      for (let x = x0; x <= x1; x++) {
        const d = Math.hypot(x - cx, y - cy);
        if (d > rOuter) continue;
        const cur = this.d[y * this.w + x];
        if (d <= rInner) {
          this.d[y * this.w + x] = doubleInner ? table[table[cur]] : table[cur];
        } else {
          const u = 1 - (d - rInner) / Math.max(1, rOuter - rInner);
          const b = bayer4(x, y);
          if (doubleInner && u > 0.65 && b < (u - 0.65) / 0.35) {
            this.d[y * this.w + x] = table[table[cur]];
          } else if (b < u) {
            this.d[y * this.w + x] = table[cur];
          }
        }
      }
    }
  }

  // Scrolling Bayer-dithered mist / fog bank
  fogLayer(y0, y1, scrollX, density, colLow, colHigh, seed = 11) {
    const ya = Math.max(this.clip[1], Math.round(y0));
    const yb = Math.min(this.clip[3], Math.round(y1));
    const h = Math.max(1, y1 - y0);
    for (let y = ya; y < yb; y++) {
      const v = (y - y0) / h;
      const envY = Math.sin(Math.PI * clamp(v, 0, 1));
      for (let x = this.clip[0]; x < this.clip[2]; x++) {
        const n = noise2((x + scrollX) * 0.045, y * 0.06, seed) * 0.68
                + noise2((x * 1.7 - scrollX * 0.5) * 0.09, y * 0.11, seed + 7) * 0.32;
        const val = n * envY * density;
        const b = bayer8(x, y);
        if (val > 0.62 && b < (val - 0.35)) this.d[y * this.w + x] = colHigh;
        else if (val > 0.24 && b < val) this.d[y * this.w + x] = colLow;
      }
    }
  }

  // Starry nocturnal sky field (pinpoint stars + rare twinkling cross-stars)
  stars(yMax, count, seed, scrollX = 0, scrollY = 0, t = 0) {
    for (let i = 0; i < count; i++) {
      const sx = mod(Math.round(hash2(i, 1, seed) * this.w - scrollX * (0.1 + 0.15 * hash2(i, 4, seed))), this.w);
      const sy = Math.round(hash2(i, 2, seed) * yMax - scrollY);
      if (sy < 0 || sy >= yMax) continue;
      const tw = 0.5 + 0.5 * Math.sin(t * (1.8 + hash2(i, 3, seed) * 2.5) + i * 1.7);
      if (tw < 0.22) continue;
      const bright = hash2(i, 5, seed);
      if (bright > 0.90) {
        this.px(sx, sy, C.cstar);
        if (tw > 0.65) {
          this.px(sx - 1, sy, C.cyan); this.px(sx + 1, sy, C.cyan);
          this.px(sx, sy - 1, C.cyan); this.px(sx, sy + 1, C.cyan);
        }
      } else if (bright > 0.55) {
        this.px(sx, sy, C.mistB);
      } else {
        this.px(sx, sy, C.dusk);
      }
    }
  }

  // Blazing astral star-burst (homage to Reference 1 grammar)
  astralBeacon(cx, cy, rGlow, rayLen, pulse = 1.0) {
    cx = Math.round(cx); cy = Math.round(cy);
    this.lightHalo(cx, cy, rGlow * 0.25, rGlow, LIGHT_COOL, true);
    // Diagonal and cardinal diffraction spikes
    const L = Math.round(rayLen * pulse);
    const Ld = Math.round(rayLen * 0.48 * pulse);
    for (let i = -L; i <= L; i++) {
      const a = 1 - Math.abs(i) / Math.max(1, L);
      const col = a > 0.65 ? C.cstar : a > 0.35 ? C.cice : C.cyan;
      if (a > 0.15 || (Math.abs(i) & 1) === 0) {
        this.px(cx + i, cy, col);
        this.px(cx, cy + Math.round(i * 1.25), col);
      }
    }
    for (let i = -Ld; i <= Ld; i++) {
      const a = 1 - Math.abs(i) / Math.max(1, Ld);
      if (a > 0.25) {
        const col = a > 0.6 ? C.cice : C.cteal;
        this.px(cx + i, cy + i, col);
        this.px(cx + i, cy - i, col);
      }
    }
    this.disc(cx, cy, 3, C.cstar);
  }

  // Giant textured cyan or veiled moon (homage to Reference 2 & 3 grammar)
  moon(cx, cy, r, style = 'cyan') {
    cx = Math.round(cx); cy = Math.round(cy);
    const pal = style === 'cyan'
      ? [C.cdeep, C.cteal, C.cyan, C.cice, C.cstar]
      : [C.slate1, C.stone0, C.stone1, C.stone2, C.stone3];
    this.lightHalo(cx, cy, r * 0.9, r * 1.55, LIGHT_COOL, false);
    const ri = Math.ceil(r);
    for (let dy = -ri; dy <= ri; dy++) {
      for (let dx = -ri; dx <= ri; dx++) {
        const d2 = dx * dx + dy * dy;
        if (d2 > r * r) continue;
        const nx = dx / r, ny = dy / r;
        const crater = noise2((nx + 2) * 3.4, (ny + 2) * 3.4, 91) * 0.45
                     + noise2((nx + 5) * 7.5, (ny + 5) * 7.5, 92) * 0.22;
        const rim = Math.sqrt(Math.max(0, 1 - (nx * nx + ny * ny)));
        const shade = clamp(0.32 + rim * 0.52 - ny * 0.18 - crater * 0.36, 0, 0.999) * (pal.length - 1);
        const idx = Math.floor(shade), f = shade - idx;
        this.px(cx + dx, cy + dy, bayer4(cx + dx, cy + dy) < f ? pal[idx + 1] : pal[idx]);
      }
    }
  }

  // Gothic Cathedral / Citadel Silhouette with spires, buttresses, lancet arches & rim lighting
  gothicCitadel(cx, baseY, scaleW, scaleH, colBody = C.void, colMid = C.slate0, colRim = C.slate1, litWindowCol = T, seed = 31) {
    cx = Math.round(cx); baseY = Math.round(baseY);
    const towers = [
      [-0.78, 0.36, 0.11], [-0.52, 0.56, 0.14], [-0.28, 0.74, 0.17],
      [0.0, 1.00, 0.22],
      [0.27, 0.71, 0.16], [0.51, 0.52, 0.14], [0.76, 0.34, 0.10],
    ];
    // Base massif
    this.poly([
      [cx - scaleW * 0.92, baseY],
      [cx - scaleW * 0.68, baseY - scaleH * 0.30],
      [cx + scaleW * 0.68, baseY - scaleH * 0.30],
      [cx + scaleW * 0.92, baseY],
    ], colBody);

    for (let ti = 0; ti < towers.length; ti++) {
      const [ox, hFrac, wFrac] = towers[ti];
      const tx = Math.round(cx + ox * scaleW);
      const tw = Math.max(4, Math.round(wFrac * scaleW));
      const th = Math.round(hFrac * scaleH);
      const bodyTop = baseY - Math.round(th * 0.62);
      const spireTop = baseY - th;

      // Tower shaft
      this.rect(tx - (tw >> 1), bodyTop, tw, baseY - bodyTop, colBody);
      // Left moonlight rim & subtle vertical ribbing
      this.vline(tx - (tw >> 1), bodyTop, baseY, colRim);
      if (tw >= 8) this.vline(tx - (tw >> 1) + 2, bodyTop + 4, baseY, colMid);

      // Needle spire
      this.tri(tx - (tw >> 1) - 1, bodyTop, tx + (tw >> 1) + 1, bodyTop, tx, spireTop, colBody);
      this.line(tx - (tw >> 1) - 1, bodyTop, tx, spireTop, colRim);
      // Finial spike
      this.vline(tx, spireTop - Math.max(4, Math.round(scaleH * 0.07)), spireTop, colRim);

      // Side pinnacles (crockets)
      const pinH = Math.max(4, Math.round(th * 0.14));
      this.tri(tx - (tw >> 1) - 2, bodyTop + 2, tx - (tw >> 1) + 1, bodyTop + 2, tx - (tw >> 1) - 1, bodyTop - pinH, colBody);
      this.tri(tx + (tw >> 1) - 1, bodyTop + 2, tx + (tw >> 1) + 2, bodyTop + 2, tx + (tw >> 1) + 1, bodyTop - pinH, colBody);

      // Lancet windows
      if (tw >= 10) {
        const wy = bodyTop + Math.round((baseY - bodyTop) * 0.24);
        const wh = Math.max(5, Math.round((baseY - bodyTop) * 0.26));
        this.vline(tx - 2, wy + 2, wy + wh, colMid);
        this.vline(tx + 2, wy + 2, wy + wh, colMid);
        if (litWindowCol !== T && hash2(ti, seed, 9) > 0.25) {
          this.vline(tx, wy + 2, wy + wh - 2, litWindowCol);
        }
      }
    }
  }

  // Craggy mountain / mossy valley ridge (homage to Reference 1, 2, 3 foregrounds)
  cragSlope(side, yTop, yBot, xEdge, colDark, colMid, colGrass, seed = 5) {
    // side: -1 = left valley wall, +1 = right valley wall
    for (let y = Math.max(0, Math.round(yTop)); y < Math.min(this.h, Math.round(yBot)); y++) {
      const u = (y - yTop) / Math.max(1, yBot - yTop);
      const jag = (noise1(y * 0.06, seed) - 0.5) * 26 + (noise1(y * 0.19, seed + 3) - 0.5) * 9;
      const span = Math.round(lerp(18, xEdge, Math.pow(u, 0.82)) + jag);
      if (side < 0) {
        const xr = clamp(span, 0, this.w - 1);
        for (let x = 0; x <= xr; x++) {
          const distFromRim = xr - x;
          const facet = noise2(x * 0.11, y * 0.09, seed + 11);
          let c = colDark;
          if (distFromRim < 4) c = colGrass;
          else if (distFromRim < 14 && bayer4(x, y) < (1 - distFromRim / 14) * 0.85) c = colGrass;
          else if (facet > 0.56 && bayer4(x, y) < (facet - 0.35)) c = colMid;
          this.px(x, y, c);
        }
      } else {
        const xl = clamp(this.w - span, 0, this.w - 1);
        for (let x = xl; x < this.w; x++) {
          const distFromRim = x - xl;
          const facet = noise2(x * 0.11, y * 0.09, seed + 21);
          let c = colDark;
          if (distFromRim < 4) c = colGrass;
          else if (distFromRim < 14 && bayer4(x, y) < (1 - distFromRim / 14) * 0.85) c = colGrass;
          else if (facet > 0.58 && bayer4(x, y) < (facet - 0.38)) c = colMid;
          this.px(x, y, c);
        }
      }
    }
  }

  // Gnarled leafless dark-fantasy tree with twisted branches
  gnarledTree(x, baseY, height, col = C.void, rimCol = T, seed = 1, sway = 0) {
    const drawBranch = (x0, y0, len, ang, thick, depth) => {
      if (depth <= 0 || len < 3) return;
      const x1 = x0 + Math.sin(ang) * len + sway * (4 - depth) * 0.7;
      const y1 = y0 - Math.cos(ang) * len;
      this.line(x0, y0, x1, y1, col, Math.max(1, Math.round(thick)));
      if (rimCol !== T && thick >= 2) this.line(x0 - Math.ceil(thick * 0.4), y0, x1 - Math.ceil(thick * 0.4), y1, rimCol, 1);
      const nSub = depth >= 3 ? 3 : 2;
      for (let k = 0; k < nSub; k++) {
        const spread = (k - (nSub - 1) / 2) * (0.55 + hash2(depth, k, seed) * 0.25);
        const subLen = len * (0.62 + hash2(k, depth, seed + 2) * 0.18);
        drawBranch(x1, y1, subLen, ang + spread, thick * 0.62, depth - 1);
      }
    };
    drawBranch(x, baseY, height * 0.42, (hash2(seed, 1) - 0.5) * 0.16, Math.max(2, height * 0.045), 4);
  }

  // Render indexed framebuffer through LUT into an RGBA ImageData(270, 480)
  present(imgData, lut = LUT.full) {
    const out = new Uint32Array(imgData.data.buffer);
    const src = this.d;
    for (let i = 0; i < src.length; i++) out[i] = lut[src[i]];
  }
}

// Native pixel transitions between two rendered framebuffers A and B
export function transitionFB(out, fbA, fbB, p, kind = 'bayer') {
  p = clamp(p, 0, 1);
  if (p <= 0) { out.d.set(fbA.d); return; }
  if (p >= 1) { out.d.set(fbB.d); return; }
  const w = out.w, h = out.h;
  if (kind === 'ichor') {
    // Creeping vertical tendrils of protected curse-green wiping from A to B
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const n = noise1(x * 0.08, 77) * 0.28 + bayer8(x, y) * 0.16;
        const edge = p * 1.44 - (1 - y / h) * 0.28 - n;
        const idx = y * w + x;
        if (edge > 0.09) out.d[idx] = fbB.d[idx];
        else if (edge > 0.0) out.d[idx] = edge > 0.045 ? C.ichor2 : C.ichor1;
        else out.d[idx] = fbA.d[idx];
      }
    }
  } else if (kind === 'mosaic') {
    const src = p < 0.5 ? fbA : fbB;
    const u = p < 0.5 ? p * 2 : (1 - p) * 2;
    const blk = Math.max(1, Math.round(1 + u * 11));
    for (let y = 0; y < h; y += blk) {
      for (let x = 0; x < w; x += blk) {
        const c = src.get(Math.min(w - 1, x + (blk >> 1)), Math.min(h - 1, y + (blk >> 1)));
        out.rect(x, y, blk, blk, c);
      }
    }
  } else {
    // Crisp 8×8 Bayer ordered dissolve (zero alpha blur!)
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const idx = y * w + x;
        out.d[idx] = bayer8(x, y) < p ? fbB.d[idx] : fbA.d[idx];
      }
    }
  }
}
