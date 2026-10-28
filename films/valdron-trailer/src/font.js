// font.js — Original gothic-serif pixel bitmap font (height 9 px native = 36 px at 1080×1920)
import { C, SCALE, bayer8, clamp } from './px.js';

// Each glyph is an array of 9 rows; '#' = ink, '.' = empty. Variable width for natural gothic kerning.
const GLYPHS = {
  A: [
    '..##..',
    '.####.',
    '##..##',
    '##..##',
    '######',
    '##..##',
    '##..##',
    '###.##',
    '......',
  ],
  B: [
    '#####.',
    '.##.##',
    '.##.##',
    '.####.',
    '.##.##',
    '.##.##',
    '.##.##',
    '#####.',
    '......',
  ],
  C: [
    '.####.',
    '##..##',
    '##....',
    '##....',
    '##....',
    '##....',
    '##..##',
    '.####.',
    '......',
  ],
  D: [
    '#####.',
    '.##.##',
    '.##.##',
    '.##.##',
    '.##.##',
    '.##.##',
    '.##.##',
    '#####.',
    '......',
  ],
  E: [
    '######',
    '.##..#',
    '.##...',
    '.####.',
    '.##...',
    '.##...',
    '.##..#',
    '######',
    '......',
  ],
  F: [
    '######',
    '.##..#',
    '.##...',
    '.####.',
    '.##...',
    '.##...',
    '.##...',
    '####..',
    '......',
  ],
  G: [
    '.####.',
    '##..##',
    '##....',
    '##....',
    '##.###',
    '##..##',
    '##..##',
    '.#####',
    '......',
  ],
  H: [
    '###.##',
    '.##.##',
    '.##.##',
    '.#####',
    '.##.##',
    '.##.##',
    '.##.##',
    '###.##',
    '......',
  ],
  I: [
    '####',
    '.##.',
    '.##.',
    '.##.',
    '.##.',
    '.##.',
    '.##.',
    '####',
    '....',
  ],
  J: [
    '..####',
    '...##.',
    '...##.',
    '...##.',
    '...##.',
    '##.##.',
    '##.##.',
    '.###..',
    '......',
  ],
  K: [
    '###.##',
    '.##.##',
    '.####.',
    '.###..',
    '.####.',
    '.##.##',
    '.##.##',
    '###.##',
    '......',
  ],
  L: [
    '####..',
    '.##...',
    '.##...',
    '.##...',
    '.##...',
    '.##...',
    '.##..#',
    '######',
    '......',
  ],
  M: [
    '##...##',
    '###.###',
    '#######',
    '##.#.##',
    '##...##',
    '##...##',
    '##...##',
    '###.###',
    '.......',
  ],
  N: [
    '##..##',
    '###.##',
    '######',
    '##.###',
    '##..##',
    '##..##',
    '##..##',
    '###.##',
    '......',
  ],
  O: [
    '.####.',
    '##..##',
    '##..##',
    '##..##',
    '##..##',
    '##..##',
    '##..##',
    '.####.',
    '......',
  ],
  P: [
    '#####.',
    '.##.##',
    '.##.##',
    '.##.##',
    '.####.',
    '.##...',
    '.##...',
    '####..',
    '......',
  ],
  Q: [
    '.####.',
    '##..##',
    '##..##',
    '##..##',
    '##..##',
    '##.###',
    '.#####',
    '....##',
    '......',
  ],
  R: [
    '#####.',
    '.##.##',
    '.##.##',
    '.####.',
    '.####.',
    '.##.##',
    '.##.##',
    '###.##',
    '......',
  ],
  S: [
    '.####.',
    '##..##',
    '###...',
    '.###..',
    '...###',
    '....##',
    '##..##',
    '.####.',
    '......',
  ],
  T: [
    '######',
    '#.##.#',
    '..##..',
    '..##..',
    '..##..',
    '..##..',
    '..##..',
    '.####.',
    '......',
  ],
  U: [
    '###.##',
    '.##.##',
    '.##.##',
    '.##.##',
    '.##.##',
    '.##.##',
    '.##.##',
    '..###.',
    '......',
  ],
  V: [
    '##..##',
    '##..##',
    '##..##',
    '##..##',
    '##..##',
    '.####.',
    '.####.',
    '..##..',
    '......',
  ],
  W: [
    '##...##',
    '##...##',
    '##...##',
    '##.#.##',
    '#######',
    '###.###',
    '##...##',
    '##...##',
    '.......',
  ],
  X: [
    '##..##',
    '##..##',
    '.####.',
    '..##..',
    '.####.',
    '##..##',
    '##..##',
    '###.##',
    '......',
  ],
  Y: [
    '##..##',
    '##..##',
    '.####.',
    '..##..',
    '..##..',
    '..##..',
    '..##..',
    '.####.',
    '......',
  ],
  Z: [
    '######',
    '#...##',
    '...##.',
    '..##..',
    '.##...',
    '##....',
    '##...#',
    '######',
    '......',
  ],
  '.': [
    '...',
    '...',
    '...',
    '...',
    '...',
    '...',
    '.##',
    '.##',
    '...',
  ],
  ',': [
    '...',
    '...',
    '...',
    '...',
    '...',
    '...',
    '.##',
    '.##',
    '##.',
  ],
  "'": [
    '.##',
    '.##',
    '##.',
    '...',
    '...',
    '...',
    '...',
    '...',
    '...',
  ],
  '-': [
    '....',
    '....',
    '....',
    '####',
    '....',
    '....',
    '....',
    '....',
    '....',
  ],
  ':': [
    '...',
    '...',
    '.##',
    '.##',
    '...',
    '.##',
    '.##',
    '...',
    '...',
  ],
  '!': [
    '.##',
    '.##',
    '.##',
    '.##',
    '.##',
    '...',
    '.##',
    '.##',
    '...',
  ],
  ' ': [
    '...',
    '...',
    '...',
    '...',
    '...',
    '...',
    '...',
    '...',
    '...',
  ],
};

export function measureLine(str, scale = 1, tracking = 1) {
  const s = str.toUpperCase();
  let w = 0;
  for (let i = 0; i < s.length; i++) {
    const g = GLYPHS[s[i]] || GLYPHS[' '];
    w += g[0].length * scale + (i < s.length - 1 ? tracking * scale : 0);
  }
  return { w, h: 8 * scale };
}

// Wrap a caption string into centered lines that fit comfortably within maxW native pixels
export function wrapCaption(str, maxW = 236, scale = 1, tracking = 1) {
  const words = str.toUpperCase().split(/\s+/);
  const lines = [];
  let cur = '';
  for (const word of words) {
    const cand = cur ? `${cur} ${word}` : word;
    if (measureLine(cand, scale, tracking).w <= maxW || !cur) {
      cur = cand;
    } else {
      lines.push(cur);
      cur = word;
    }
  }
  if (cur) lines.push(cur);
  return lines;
}

// Draw text with 8-neighbour obsidian outline + row gradient + Bayer dissolve reveal
export function drawGothicText(fb, str, cx, yTop, opts = {}) {
  const {
    scale = 1,
    tracking = 1,
    rowCols = [C.silver, C.text, C.text, C.steel, C.steel, C.stone3, C.stone2, C.stone2],
    outlineCol = C.void,
    dissolve = 1.0,
    curseVein = false,
  } = opts;
  const s = str.toUpperCase();
  const { w, h } = measureLine(s, scale, tracking);
  const xStart = Math.round(cx - w / 2);
  const yStart = Math.round(yTop);

  // Pass 1: 8-neighbour outline
  let xCur = xStart;
  for (let i = 0; i < s.length; i++) {
    const g = GLYPHS[s[i]] || GLYPHS[' '];
    const gw = g[0].length;
    for (let r = 0; r < 9; r++) {
      for (let c = 0; c < gw; c++) {
        if (g[r][c] !== '#') continue;
        for (let sy = 0; sy < scale; sy++) {
          for (let sx = 0; sx < scale; sx++) {
            const px = xCur + c * scale + sx;
            const py = yStart + r * scale + sy;
            if (dissolve < 1 && bayer8(px, py) >= dissolve) continue;
            for (let oy = -1; oy <= 1; oy++) {
              for (let ox = -1; ox <= 1; ox++) {
                if (ox !== 0 || oy !== 0) fb.px(px + ox, py + oy, outlineCol);
              }
            }
          }
        }
      }
    }
    xCur += gw * scale + tracking * scale;
  }

  // Pass 2: Glyph fill
  xCur = xStart;
  for (let i = 0; i < s.length; i++) {
    const g = GLYPHS[s[i]] || GLYPHS[' '];
    const gw = g[0].length;
    for (let r = 0; r < 9; r++) {
      const baseCol = rowCols[Math.min(rowCols.length - 1, r)];
      for (let c = 0; c < gw; c++) {
        if (g[r][c] !== '#') continue;
        for (let sy = 0; sy < scale; sy++) {
          for (let sx = 0; sx < scale; sx++) {
            const px = xCur + c * scale + sx;
            const py = yStart + r * scale + sy;
            if (dissolve < 1 && bayer8(px, py) >= dissolve) continue;
            let col = baseCol;
            if (curseVein && Math.abs((px - xStart) - (py - yStart) * 1.4 - 18) < 2.2) {
              col = sy === 0 ? C.ichor4 : C.ichor3;
            }
            fb.px(px, py, col);
          }
        }
      }
    }
    xCur += gw * scale + tracking * scale;
  }

  return { x0: xStart - 1, y0: yStart - 1, x1: xStart + w + 1, y1: yStart + h + 1 };
}

// Draw synchronized narrative caption plaque in lower cinematic safe zone (y = 398..448 native)
// Returns viewport-space (1080×1920) bounding box for readcheck.mjs
export function drawCaptionCard(fb, cap, t, measureOnly = false) {
  const fadeIn = clamp((t - cap.t0) / 0.32, 0, 1);
  const fadeOut = clamp((cap.t1 - t) / 0.32, 0, 1);
  const vis = Math.min(fadeIn, fadeOut);

  const lines = wrapCaption(cap.text, 232, 1, 1);
  const lineH = 13;
  const totalH = lines.length * lineH - 4;
  const yBase = cap.pos === 'mid' ? 236 : 408;
  const yTop = Math.round(yBase - totalH / 2);

  let minX = 999, maxX = 0;
  for (const ln of lines) {
    const { w } = measureLine(ln, 1, 1);
    const x0 = Math.round(135 - w / 2);
    minX = Math.min(minX, x0);
    maxX = Math.max(maxX, x0 + w);
  }

  if (!measureOnly && vis > 0) {
    // Subtle Bayer-dithered dark shadow band behind caption so text is 100% legible over fog/grass
    const padX = 10, padY = 6;
    for (let y = yTop - padY; y <= yTop + totalH + padY; y++) {
      for (let x = minX - padX; x <= maxX + padX; x++) {
        const edgeX = Math.min(x - (minX - padX), (maxX + padX) - x) / 10;
        const edgeY = Math.min(y - (yTop - padY), (yTop + totalH + padY) - y) / 5;
        const e = clamp(Math.min(edgeX, edgeY), 0, 1) * vis * 0.86;
        if (bayer8(x, y) < e) fb.px(x, y, C.void);
      }
    }
    // Delicate gothic hairlines with curse-green pinpoint diamond accents
    if (vis > 0.6) {
      fb.hline(minX - 2, maxX + 2, yTop - 4, C.slate1);
      fb.hline(minX - 2, maxX + 2, yTop + totalH + 4, C.slate1);
      fb.px(135, yTop - 4, C.ichor2);
      fb.px(135, yTop + totalH + 4, C.ichor2);
    }
    for (let i = 0; i < lines.length; i++) {
      drawGothicText(fb, lines[i], 135, yTop + i * lineH, {
        scale: 1,
        tracking: 1,
        dissolve: vis,
      });
    }
  }

  return {
    id: cap.id,
    text: cap.text,
    x0: (minX - 2) * SCALE,
    y0: (yTop - 2) * SCALE,
    x1: (maxX + 2) * SCALE,
    y1: (yTop + totalH + 2) * SCALE,
  };
}
