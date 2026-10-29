"""Procedural Woodcut + Volumetric HDR Motion-Graphics Assets for the 36s Pottsfield One-Shot Film.

Every plate and parametric shape uses the exact Pottsfield Studio palette:
  - Woodcut Ivory Ink:     sRGB (255, 243, 223)
  - Molten Spark Gold:     sRGB (255, 196,  92)
  - Harvest Lantern Orange:sRGB (244, 115,  10)  #F4730A
  - Autumn Crimson Ink:    sRGB (168,  36,  36)  #A82424
  - Velvet Night Black:    sRGB (  0,   0,   0)  #000000
"""
import math
import os
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

from engine import srgb_to_linear, clamp, smoothstep, smootherstep

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(HERE, "fonts")

CINZEL_PATH = os.path.join(FONTS_DIR, "Cinzel[wght].ttf")
FELL_IT_PATH = os.path.join(FONTS_DIR, "IMFeENit28P.ttf")
FELL_RM_PATH = os.path.join(FONTS_DIR, "IMFeENrm28P.ttf")
MONTSERRAT_PATH = os.path.join(FONTS_DIR, "Montserrat[wght].ttf")

# Canonical linear RGB colors
LIN_IVORY = srgb_to_linear(np.array([[[255, 243, 223]]], dtype=np.uint8))[0, 0]
LIN_GOLD = srgb_to_linear(np.array([[[255, 198, 96]]], dtype=np.uint8))[0, 0]
LIN_ORANGE = srgb_to_linear(np.array([[[244, 115, 10]]], dtype=np.uint8))[0, 0]
LIN_CRIMSON = srgb_to_linear(np.array([[[178, 38, 38]]], dtype=np.uint8))[0, 0]
LIN_COLD_GREY = srgb_to_linear(np.array([[[138, 128, 124]]], dtype=np.uint8))[0, 0]


# =============================================================================
# Easing Vocabulary (locked per motion-skills/motion-art-direction)
# =============================================================================
def ease_out_expo(u: float) -> float:
    u = float(np.clip(u, 0.0, 1.0))
    return 1.0 if u >= 0.9999 else 1.0 - math.pow(2.0, -10.0 * u)


def ease_in_expo(u: float) -> float:
    u = float(np.clip(u, 0.0, 1.0))
    return 0.0 if u <= 0.0001 else math.pow(2.0, 10.0 * (u - 1.0))


def ease_in_out_cubic(u: float) -> float:
    u = float(np.clip(u, 0.0, 1.0))
    return 4.0 * u * u * u if u < 0.5 else 1.0 - math.pow(-2.0 * u + 2.0, 3.0) / 2.0


def ease_out_back(u: float, overshoot: float = 1.45) -> float:
    u = float(np.clip(u, 0.0, 1.0))
    c1 = overshoot
    c3 = c1 + 1.0
    return 1.0 + c3 * math.pow(u - 1.0, 3.0) + c1 * math.pow(u - 1.0, 2.0)


def load_font(path: str, size: int, weight: int = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(path, size=size)
    if weight is not None:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


# =============================================================================
# Woodcut Hatching Field Generator (matches hero pumpkin carved ink aesthetic)
# =============================================================================
def make_woodcut_grain(h: int, w: int, seed: int = 42) -> np.ndarray:
    """Returns subtle woodcut line-etch modulation in [0.78, 1.06] so vector art feels carved, never sterile."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    diag1 = 0.5 + 0.5 * np.sin((xx * 0.85 + yy * 0.42) * 0.52)
    diag2 = 0.5 + 0.5 * np.sin((xx * -0.35 + yy * 0.92) * 0.31)
    noise = rng.uniform(0.0, 1.0, (max(h // 3, 1), max(w // 3, 1))).astype(np.float32)
    noise = cv2.resize(noise, (w, h), interpolation=cv2.INTER_LINEAR)
    etch = 0.80 + 0.16 * diag1 * (0.55 + 0.45 * noise) + 0.08 * diag2
    return etch.astype(np.float32)


# =============================================================================
# Kinetic Typography Line Plate Builder (2x supersampled, single-focus clarity)
# =============================================================================
class KineticTextPlate:
    """Pre-baked HDR linear RGB + alpha plate for crisp baseline mask-up or gouge-wipe reveals."""

    def __init__(self, lines_spec: list, width: int = 960, pad_y: int = 36, seed: int = 7):
        """
        lines_spec: list of dicts:
          {"text": str, "font": (path, size_px, weight), "tracking": int,
           "style": "ivory" | "orange" | "gold" | "crimson" | "italic_cream",
           "gap_after": int}
        """
        ss = 2
        W2 = width * ss
        measured = []
        total_h2 = pad_y * 2 * ss
        for item in lines_spec:
            fpath, fsize, fw = item["font"]
            font = load_font(fpath, fsize * ss, fw)
            trk = item.get("tracking", 0) * ss
            txt = item["text"]
            advs = []
            max_ascent, max_descent = fsize * ss, int(fsize * 0.35 * ss)
            for ch in txt:
                adv = font.getlength(ch)
                advs.append(adv)
            line_w2 = sum(advs) + trk * max(len(txt) - 1, 0)
            line_h2 = int(fsize * 1.24 * ss)
            gap2 = item.get("gap_after", 10) * ss
            measured.append((item, font, advs, trk, line_w2, line_h2, gap2))
            total_h2 += line_h2 + gap2

        H2 = max(total_h2, 64 * ss)
        line_masks = []
        line_bounds = []  # (y0_1x, y1_1x, style)

        y_cur = pad_y * ss
        for item, font, advs, trk, lw2, lh2, gap2 in measured:
            img = Image.new("L", (W2, H2), 0)
            drw = ImageDraw.Draw(img)
            x_cur = 0.5 * (W2 - lw2)
            x_start = x_cur
            for ch, adv in zip(item["text"], advs):
                drw.text((x_cur, y_cur), ch, fill=255, font=font)
                x_cur += adv + trk
            x_end = x_cur - trk
            # Optional crisp vector 4-point Pottsfield stars flanking an overline (never rely on font glyphs!)
            if item.get("stars", False):
                sr = max(int(lh2 * 0.24), 10)
                sy_star = y_cur + lh2 * 0.45
                for sx_star in (x_start - sr * 2.8, x_end + sr * 2.8):
                    pts = [
                        (sx_star, sy_star - sr), (sx_star + sr * 0.26, sy_star - sr * 0.26),
                        (sx_star + sr, sy_star), (sx_star + sr * 0.26, sy_star + sr * 0.26),
                        (sx_star, sy_star + sr), (sx_star - sr * 0.26, sy_star + sr * 0.26),
                        (sx_star - sr, sy_star), (sx_star - sr * 0.26, sy_star - sr * 0.26),
                    ]
                    drw.polygon(pts, fill=255)
            m_1x = cv2.resize(np.array(img, dtype=np.float32) / 255.0,
                              (width, H2 // ss), interpolation=cv2.INTER_AREA)
            line_masks.append((m_1x, item["style"]))
            line_bounds.append((y_cur // ss, (y_cur + lh2) // ss, item["style"]))
            y_cur += lh2 + gap2

        H1 = H2 // ss
        self.w = width
        self.h = H1
        self.line_bounds = line_bounds
        grain = make_woodcut_grain(H1, width, seed=seed)
        yy = np.linspace(0.0, 1.0, H1, dtype=np.float32)[:, None]

        # Build per-line linear HDR premultiplied RGB + alpha + soft dark readability backing
        self.lines_rgb = []
        self.lines_alpha = []
        self.lines_shadow = []

        for idx, (m, style) in enumerate(line_masks):
            y0, y1, _ = line_bounds[idx]
            ly = np.clip((np.arange(H1, dtype=np.float32)[:, None] - y0) / max(y1 - y0, 1), 0.0, 1.0)
            if style == "ivory":
                col = (LIN_IVORY[None, None, :] * (1.08 - 0.14 * ly[:, :, None]) * grain[:, :, None])
                glow_col = LIN_ORANGE * 0.42
            elif style == "orange":
                top_c = LIN_GOLD * 1.18
                bot_c = LIN_ORANGE * 1.05
                col = (top_c[None, None, :] * (1.0 - ly[:, :, None]) + bot_c[None, None, :] * ly[:, :, None]) * grain[:, :, None]
                glow_col = LIN_ORANGE * 0.72
            elif style == "gold":
                col = (LIN_GOLD[None, None, :] * (1.12 - 0.16 * ly[:, :, None]) * grain[:, :, None])
                glow_col = LIN_ORANGE * 0.55
            elif style == "crimson":
                c_hi = srgb_to_linear(np.array([[[232, 84, 62]]], dtype=np.uint8))[0, 0]
                col = c_hi[None, None, :] * grain[:, :, None]
                glow_col = LIN_CRIMSON * 0.45
            else:  # italic_cream
                c_cr = srgb_to_linear(np.array([[[248, 224, 192]]], dtype=np.uint8))[0, 0]
                col = c_cr[None, None, :] * (0.96 + 0.04 * grain[:, :, None])
                glow_col = LIN_ORANGE * 0.32

            # Subtle HDR ember halo around glyphs
            halo = cv2.GaussianBlur(m, (0, 0), sigmaX=7.5, sigmaY=7.5)
            rgb = col * m[:, :, None] + glow_col[None, None, :] * (halo[:, :, None] * 0.65)
            alpha = np.clip(m + halo * 0.22, 0.0, 1.0)

            # Deep soft readability cushion so glyphs read effortlessly on ANY phone brightness
            sh_wide = cv2.GaussianBlur(m, (0, 0), sigmaX=16.0, sigmaY=12.0) * 0.82
            sh_tight = cv2.GaussianBlur(m, (0, 0), sigmaX=3.2, sigmaY=3.2) * 0.92
            sh = np.clip(sh_wide + sh_tight, 0.0, 0.94)

            self.lines_rgb.append(rgb.astype(np.float32))
            self.lines_alpha.append(alpha.astype(np.float32))
            self.lines_shadow.append(sh.astype(np.float32))

    def composite_onto(self, frame_hdr: np.ndarray, cx: float, cy: float,
                       enter_t: float, stagger: float = 0.10, dur: float = 0.42,
                       exit_u: float = 0.0, mode: str = "mask_up",
                       scale: float = 1.0, slice_u: float = -1.0,
                       reveal_ltr_u: float = -1.0):
        """
        Composites this text plate centered at (cx, cy) onto frame_hdr with:
          - Per-line staggered baseline mask-up reveal (kinetic-typography standard)
          - Optional horizontal gouge-slice wipe-out (slice_u in [0..1])
          - Optional horizontal gouge-slice wipe-in (reveal_ltr_u in [0..1])
          - Clean ease-in upward drift on exit_u in [0..1]
        """
        if enter_t <= 0.0 or exit_u >= 0.999:
            return
        H, W, _ = frame_hdr.shape
        out_fade = 1.0 - ease_in_expo(exit_u) if mode == "fade_exit" else (1.0 - ease_in_out_cubic(exit_u))
        y_exit_off = -54.0 * ease_in_out_cubic(exit_u)

        for idx in range(len(self.lines_rgb)):
            u_in = (enter_t - idx * stagger) / max(dur, 1e-4)
            if u_in <= 0.0:
                continue
            p_in = 1.0 if mode == "ltr_wipe" else ease_out_expo(min(u_in, 1.0))
            op = p_in * out_fade
            if op <= 0.003:
                continue

            rgb_src = self.lines_rgb[idx]
            a_src = self.lines_alpha[idx]
            sh_src = self.lines_shadow[idx]
            y0_b, y1_b, _ = self.line_bounds[idx]
            line_h = max(y1_b - y0_b, 1)

            rise_px = (1.0 - p_in) * (line_h * 0.82) if mode == "mask_up" else 0.0

            pw = int(round(self.w * scale))
            ph = int(round(self.h * scale))
            if abs(scale - 1.0) > 0.01:
                rgb_s = cv2.resize(rgb_src, (pw, ph), interpolation=cv2.INTER_LINEAR)
                a_s = cv2.resize(a_src, (pw, ph), interpolation=cv2.INTER_LINEAR)
                sh_s = cv2.resize(sh_src, (pw, ph), interpolation=cv2.INTER_LINEAR)
            else:
                rgb_s, a_s, sh_s = rgb_src, a_src, sh_src
            ph, pw = a_s.shape

            if rise_px > 0.4:
                shift = int(round(rise_px * scale))
                rgb_sh = np.zeros_like(rgb_s)
                a_sh = np.zeros_like(a_s)
                sh_sh = np.zeros_like(sh_s)
                if shift < ph:
                    rgb_sh[shift:] = rgb_s[:ph - shift]
                    a_sh[shift:] = a_s[:ph - shift]
                    sh_sh[shift:] = sh_s[:ph - shift]
                clip_bot = min(ph, int(round((y1_b + 12) * scale)))
                if clip_bot < ph:
                    soft = np.clip((clip_bot + 6 - np.arange(ph, dtype=np.float32)) / 6.0, 0.0, 1.0)[:, None]
                    rgb_sh *= soft[:, :, None]
                    a_sh *= soft
                    sh_sh *= soft
                rgb_s, a_s, sh_s = rgb_sh, a_sh, sh_sh

            # Gouge-spark horizontal wipe-out (keeps right of slice_u)
            if 0.0 <= slice_u <= 1.05:
                xx_u = np.linspace(0.0, 1.0, pw, dtype=np.float32)[None, :]
                keep = smoothstep(slice_u + 0.02, slice_u + 0.09, xx_u)
                edge = np.exp(-((xx_u - slice_u) / 0.032) ** 2) * a_s
                rgb_s = rgb_s * keep[:, :, None] + (LIN_GOLD * 2.2)[None, None, :] * edge[:, :, None]
                a_s = np.clip(a_s * keep + edge * 0.8, 0.0, 1.0)
                sh_s = sh_s * keep

            # Gouge-spark horizontal wipe-in (reveals left of reveal_ltr_u — zero letter collision!)
            if 0.0 <= reveal_ltr_u <= 1.05:
                xx_u = np.linspace(0.0, 1.0, pw, dtype=np.float32)[None, :]
                show = 1.0 - smoothstep(reveal_ltr_u - 0.09, reveal_ltr_u - 0.02, xx_u)
                edge = np.exp(-((xx_u - reveal_ltr_u) / 0.032) ** 2) * a_s
                rgb_s = rgb_s * show[:, :, None] + (LIN_ORANGE * 2.0)[None, None, :] * edge[:, :, None]
                a_s = np.clip(a_s * show + edge * 0.7, 0.0, 1.0)
                sh_s = sh_s * show

            x0 = int(round(cx - pw * 0.5))
            y0 = int(round(cy - ph * 0.5 + y_exit_off))
            x1, y1 = x0 + pw, y0 + ph

            sx0, sy0 = max(0, -x0), max(0, -y0)
            dx0, dy0 = max(0, x0), max(0, y0)
            dx1, dy1 = min(W, x1), min(H, y1)
            if dx1 <= dx0 or dy1 <= dy0:
                continue
            sx1, sy1 = sx0 + (dx1 - dx0), sy0 + (dy1 - dy0)

            roi = frame_hdr[dy0:dy1, dx0:dx1]
            sh_roi = sh_s[sy0:sy1, sx0:sx1] * op
            a_roi = a_s[sy0:sy1, sx0:sx1] * op
            rgb_roi = rgb_s[sy0:sy1, sx0:sx1] * op

            roi *= (1.0 - sh_roi[:, :, None] * 0.86)
            roi[:] = roi * (1.0 - a_roi[:, :, None]) + rgb_roi


# =============================================================================
# Chapter 1 & 2 Assets: Woodcut Smartphone + Fake-Ad Clutter + Shatter Shards
# =============================================================================
def build_fake_ad_stamps() -> list:
    """Builds 4 crisp woodcut-stamped 'soulless mobile ad' pop-up cards that slam inside the phone screen."""
    specs = [
        ("99% FAIL!", "IQ: 12?!", (215, 52, 46), (255, 232, 185), 320, 148),
        ("x999 GATE!", "TAP! TAP!", (190, 68, 24), (255, 240, 210), 336, 140),
        ("VIP $99.99", "BUY NOW!", (168, 36, 36), (255, 224, 168), 324, 142),
        ("BRAINROT", "AD  0:30", (124, 34, 34), (245, 228, 206), 344, 152),
    ]
    cards = []
    f_big = load_font(MONTSERRAT_PATH, 42, 800)
    f_sub = load_font(MONTSERRAT_PATH, 26, 700)
    for idx, (t1, t2, bg_srgb, fg_srgb, cw, ch) in enumerate(specs):
        ss = 2
        W2, H2 = cw * ss, ch * ss
        img = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # Double-lined woodcut stamp box
        d.rounded_rectangle([8, 8, W2 - 8, H2 - 8], radius=24,
                            fill=(26, 10, 8, 242), outline=(*bg_srgb, 255), width=7)
        d.rounded_rectangle([20, 20, W2 - 20, H2 - 20], radius=16,
                            fill=None, outline=(*fg_srgb, 185), width=3)
        # Tiny fake "[X]" corner button every mobile gamer hates!
        d.rectangle([W2 - 64, 20, W2 - 22, 62], fill=(*bg_srgb, 255))
        d.line([W2 - 54, 30, W2 - 32, 52], fill=(255, 245, 230, 255), width=5)
        d.line([W2 - 54, 52, W2 - 32, 30], fill=(255, 245, 230, 255), width=5)

        f1_2 = load_font(MONTSERRAT_PATH, 40 * ss, 800)
        f2_2 = load_font(MONTSERRAT_PATH, 24 * ss, 700)
        w1 = f1_2.getlength(t1)
        w2 = f2_2.getlength(t2)
        d.text(((W2 - w1) * 0.5 - 14, 34), t1, fill=(*fg_srgb, 255), font=f1_2)
        d.text(((W2 - w2) * 0.5, 138), t2, fill=(255, 165, 72, 255), font=f2_2)

        arr = cv2.resize(np.array(img, dtype=np.float32) / 255.0, (cw, ch), interpolation=cv2.INTER_AREA)
        grain = make_woodcut_grain(ch, cw, seed=100 + idx)
        lin_rgb = srgb_to_linear(arr[:, :, :3]) * grain[:, :, None] * arr[:, :, 3:4]
        cards.append((lin_rgb.astype(np.float32), arr[:, :, 3].astype(np.float32)))
    return cards


def build_emblem_slash_plate(size: int = 340) -> tuple:
    """Builds two woodcut kinetic emblems for Chapter 2:
      1) Crossed-out fake-ad play triangle & dollar badge (for 'NO FAKE ADS.')
      2) Dissolving brainrot spiral-gear bursting into warm autumn fireflies (for 'NO BRAINROT.')
    """
    ss = 2
    S2 = size * ss
    # Emblem A: Broken Ad Play-Button slashed by Crimson/Gold Woodcut X
    img_a = Image.new("L", (S2, S2), 0)
    da = ImageDraw.Draw(img_a)
    cx, cy = S2 // 2, S2 // 2
    # Octagonal woodcut badge ring
    da.ellipse([64, 64, S2 - 64, S2 - 64], outline=210, width=9)
    da.ellipse([84, 84, S2 - 84, S2 - 84], outline=120, width=4)
    # Play triangle inside
    pts = [(cx - 58, cy - 82), (cx - 58, cy + 82), (cx + 88, cy)]
    da.polygon(pts, outline=235, width=10)
    m_a_base = cv2.resize(np.array(img_a, dtype=np.float32) / 255.0, (size, size), interpolation=cv2.INTER_AREA)

    img_slash = Image.new("L", (S2, S2), 0)
    ds = ImageDraw.Draw(img_slash)
    ds.line([92, S2 - 92, S2 - 92, 92], fill=255, width=22)
    ds.line([108, 108, S2 - 108, S2 - 108], fill=255, width=16)
    m_a_slash = cv2.resize(np.array(img_slash, dtype=np.float32) / 255.0, (size, size), interpolation=cv2.INTER_AREA)

    # Emblem B: Hypnotic endless-loop gear cracking into 4 warm stars/leaves
    img_b = Image.new("L", (S2, S2), 0)
    db = ImageDraw.Draw(img_b)
    for k in range(12):
        a0 = k * (2 * math.pi / 12)
        x1 = cx + math.cos(a0) * 165
        y1 = cy + math.sin(a0) * 165
        x2 = cx + math.cos(a0) * 225
        y2 = cy + math.sin(a0) * 225
        db.line([x1, y1, x2, y2], fill=200, width=24)
    db.arc([cx - 175, cy - 175, cx + 175, cy + 175], start=18, end=155, fill=240, width=14)
    db.arc([cx - 175, cy - 175, cx + 175, cy + 175], start=198, end=335, fill=240, width=14)
    # Four crisp 4-point Pottsfield stars emerging from the broken center!
    for sx, sy, sr in [(cx, cy, 78), (cx - 135, cy - 115, 34), (cx + 142, cy - 95, 30), (cx + 115, cy + 128, 32)]:
        star = [
            (sx, sy - sr), (sx + sr * 0.24, sy - sr * 0.24),
            (sx + sr, sy), (sx + sr * 0.24, sy + sr * 0.24),
            (sx, sy + sr), (sx - sr * 0.24, sy + sr * 0.24),
            (sx - sr, sy), (sx - sr * 0.24, sy - sr * 0.24),
        ]
        db.polygon(star, fill=255)
    m_b = cv2.resize(np.array(img_b, dtype=np.float32) / 255.0, (size, size), interpolation=cv2.INTER_AREA)
    return m_a_base, m_a_slash, m_b


# =============================================================================
# Chapter 3 Assets: 4-Plane 2D Woodcut -> 3D Volumetric Story World Diorama
# =============================================================================
def build_story_diorama_planes(w: int = 1640, h: int = 1120) -> dict:
    """
    Pre-renders 4 wide multi-plane parallax layers (1640 x 1120) in BOTH:
      - 2D Woodcut Ivory Ink state
      - 3D Volumetric Harvest-Lantern Lit state
    so as the One-Shot camera glides laterally + pushes in (9.6s -> 16.8s),
    the world seamlessly transforms from flat carved woodcut ink into glowing 3D depth!
    """
    grain = make_woodcut_grain(h, w, seed=303)

    # --- PLANE 1 (Far Background 0.28x parallax): Harvest Moon + Distant Gothic Ruin Spire ---
    p1_sil = Image.new("L", (w, h), 0)
    p1_edge = Image.new("L", (w, h), 0)
    d_sil, d_edg = ImageDraw.Draw(p1_sil), ImageDraw.Draw(p1_edge)
    # Giant crescent harvest moon at upper-right
    mx, my, mr = int(w * 0.64), int(h * 0.30), 155
    d_edg.ellipse([mx - mr, my - mr, mx + mr, my + mr], outline=220, width=5)
    # Distant rolling hills + gothic clock/lantern tower silhouette
    hill1 = [(0, int(h * 0.78))]
    for x in range(0, w + 40, 40):
        yh = int(h * 0.68 - 58 * math.sin(x * 0.0042) - 32 * math.cos(x * 0.009))
        hill1.append((x, yh))
    hill1.append((w, h))
    hill1.append((0, h))
    d_sil.polygon(hill1, fill=255)
    d_edg.line(hill1[1:-2], fill=235, width=4)
    # Distant spire on hill crest
    tx, ty = int(w * 0.44), int(h * 0.60)
    spire = [(tx - 46, ty + 90), (tx - 36, ty - 70), (tx - 52, ty - 70),
             (tx, ty - 205), (tx + 52, ty - 70), (tx + 36, ty - 70), (tx + 46, ty + 90)]
    d_sil.polygon(spire, fill=255)
    d_edg.line(spire, fill=245, width=4)
    # Spire glowing window
    p1_win = Image.new("L", (w, h), 0)
    ImageDraw.Draw(p1_win).rounded_rectangle([tx - 13, ty - 58, tx + 13, ty - 12], radius=12, fill=255)

    # --- PLANE 2 (Midground 0.62x parallax): Crooked Autumn Oaks + Hanging Paper Lanterns ---
    p2_sil = Image.new("L", (w, h), 0)
    p2_edge = Image.new("L", (w, h), 0)
    p2_lant = Image.new("L", (w, h), 0)
    ds2, de2, dl2 = ImageDraw.Draw(p2_sil), ImageDraw.Draw(p2_edge), ImageDraw.Draw(p2_lant)

    # Ground ridge
    ridge2 = [(0, h)]
    for x in range(0, w + 32, 32):
        yr = int(h * 0.80 - 28 * math.sin(x * 0.006 + 1.1))
        ridge2.append((x, yr))
    ridge2.append((w, h))
    ds2.polygon(ridge2, fill=255)
    de2.line(ridge2[1:-1], fill=240, width=5)

    # Three gnarled Gothic autumn oaks with multi-forked branches, autumn leaf clusters & hanging lanterns!
    rng_tree = np.random.default_rng(777)
    tree_xs = [int(w * 0.21), int(w * 0.56), int(w * 0.84)]
    for idx, bx in enumerate(tree_xs):
        by = int(h * 0.81)
        trunk_w = 40 if idx != 1 else 34
        pts_l, pts_r = [], []
        for s in range(14):
            u = s / 13.0
            yy = by - u * 410
            sway = math.sin(u * 2.1 + idx * 1.4) * 32 - u * 12 * ((-1) ** idx)
            tw = trunk_w * (1.0 - 0.58 * u)
            pts_l.append((bx + sway - tw, yy))
            pts_r.append((bx + sway + tw, yy))
        poly = pts_l + pts_r[::-1]
        ds2.polygon(poly, fill=255)
        de2.line(pts_l, fill=245, width=4)
        de2.line(pts_r, fill=225, width=4)
        for b in (-0.32, 0.24):
            bark = [(bx + math.sin((s / 13.0) * 2.1 + idx * 1.4) * 32 - (s / 13.0) * 12 * ((-1) ** idx)
                     + b * trunk_w * (1.0 - 0.56 * (s / 13.0)),
                     by - (s / 13.0) * 380) for s in range(12)]
            de2.line(bark, fill=145, width=2)

        top_x = 0.5 * (pts_l[-1][0] + pts_r[-1][0])
        top_y = pts_l[-1][1]
        # Asymmetric gnarled boughs reaching upward & outward + secondary twigs + carved autumn leaf clusters!
        bough_specs = [
            (-1, 210, -115, 0.65, True),
            (-1, 130, -185, 0.45, False),
            (1, 205, -95, 0.72, True),
            (1, 125, -170, 0.48, False),
        ]
        for dir_s, reach_x, reach_y, hang_u, has_lantern in bough_specs:
            br_l, br_r = [], []
            for s in range(11):
                u = s / 10.0
                cx_b = top_x + dir_s * (u * reach_x)
                cy_b = top_y + u * reach_y + math.sin(u * 2.7 + idx) * 22
                bw = 11.0 * (1.0 - 0.78 * u)
                br_l.append((cx_b, cy_b - bw))
                br_r.append((cx_b, cy_b + bw))
            ds2.polygon(br_l + br_r[::-1], fill=255)
            de2.line(br_l, fill=240, width=3)
            de2.line(br_r, fill=195, width=2)

            # Secondary forked twig near tip
            tx0, ty0 = br_l[6]
            twig = [(tx0, ty0), (tx0 + dir_s * 38, ty0 - 46), (tx0 + dir_s * 68, ty0 - 62)]
            de2.line(twig, fill=215, width=3)
            ds2.line(twig, fill=255, width=5)

            # Cluster of carved autumn leaves at bough tips!
            tip_x, tip_y = br_l[-1]
            for k in range(5):
                ang = float(rng_tree.uniform(0, 2 * math.pi))
                ox = float(rng_tree.uniform(-34, 34))
                oy = float(rng_tree.uniform(-26, 26))
                lx_c, ly_c = tip_x + ox, tip_y + oy
                ca, sa = math.cos(ang), math.sin(ang)
                leaf = [
                    (lx_c - ca * 14, ly_c - sa * 14),
                    (lx_c - sa * 8, ly_c + ca * 8),
                    (lx_c + ca * 16, ly_c + sa * 16),
                    (lx_c + sa * 8, ly_c - ca * 8),
                ]
                ds2.polygon(leaf, fill=255)
                de2.polygon(leaf, outline=225)

            if has_lantern:
                hi = int(round(hang_u * 10))
                ax_l, ay_l = int(br_r[hi][0]), int(br_r[hi][1])
                lx, ly = ax_l, ay_l + 56
                de2.line([(ax_l, ay_l), (lx, ly - 22)], fill=225, width=3)
                # Pointed iron lantern cap + warm glowing glass cage
                cap = [(lx - 22, ly - 16), (lx, ly - 30), (lx + 22, ly - 16)]
                ds2.polygon(cap, fill=255)
                de2.polygon(cap, outline=245)
                ds2.rounded_rectangle([lx - 17, ly - 16, lx + 17, ly + 22], radius=7, fill=255)
                de2.rounded_rectangle([lx - 17, ly - 16, lx + 17, ly + 22], radius=7, outline=250, width=3)
                dl2.ellipse([lx - 12, ly - 11, lx + 12, ly + 16], fill=255)

    # --- PLANE 3 (Foreground 1.05x parallax): Stone Bridge + Cloaked Story Traveler with Blazing Lantern ---
    p3_sil = Image.new("L", (w, h), 0)
    p3_edge = Image.new("L", (w, h), 0)
    p3_lant = Image.new("L", (w, h), 0)
    ds3, de3, dl3 = ImageDraw.Draw(p3_sil), ImageDraw.Draw(p3_edge), ImageDraw.Draw(p3_lant)

    # Arched stone bridge across lower third
    bridge_top = []
    for x in range(0, w + 24, 24):
        ux = (x - w * 0.48) / (w * 0.42)
        yb = int(h * 0.86 + 64 * (ux * ux))
        bridge_top.append((x, yb))
    ds3.polygon([(0, h)] + bridge_top + [(w, h)], fill=255)
    de3.line(bridge_top, fill=255, width=6)

    # Cloaked traveler standing on bridge crest (x = 0.47*w) holding up a glowing lantern!
    hx, hy = int(w * 0.47), int(h * 0.855)
    cloak = [
        (hx - 44, hy + 6),
        (hx - 28, hy - 98),
        (hx - 18, hy - 146),
        (hx + 2, hy - 182),   # pointed pilgrim/autumn hood tip!
        (hx + 22, hy - 144),
        (hx + 46, hy - 116),  # raised arm holding lantern staff
        (hx + 34, hy - 86),
        (hx + 42, hy + 6),
    ]
    ds3.polygon(cloak, fill=255)
    de3.line(cloak + [cloak[0]], fill=255, width=5)
    # Lantern staff + blazing hero lantern held forward!
    lx_h, ly_h = hx + 76, hy - 134
    de3.line([(hx + 38, hy - 110), (lx_h, ly_h - 28)], fill=255, width=5)
    de3.line([(lx_h, ly_h - 28), (lx_h, ly_h - 14)], fill=240, width=3)
    ds3.rounded_rectangle([lx_h - 20, ly_h - 14, lx_h + 20, ly_h + 30], radius=9, fill=255)
    de3.rounded_rectangle([lx_h - 20, ly_h - 14, lx_h + 20, ly_h + 30], radius=9, outline=255, width=4)
    dl3.ellipse([lx_h - 15, ly_h - 8, lx_h + 15, ly_h + 24], fill=255)

    def to_f(im):
        return (np.array(im, dtype=np.float32) / 255.0)

    return {
        "w": w, "h": h, "grain": grain,
        "p1_sil": to_f(p1_sil), "p1_edge": to_f(p1_edge), "p1_win": to_f(p1_win),
        "p2_sil": to_f(p2_sil), "p2_edge": to_f(p2_edge), "p2_lant": to_f(p2_lant),
        "p3_sil": to_f(p3_sil), "p3_edge": to_f(p3_edge), "p3_lant": to_f(p3_lant),
        "hero_lantern": (lx_h, ly_h + 8),
        "moon": (mx, my, mr),
    }


# =============================================================================
# Parametric SDF Device Morph: Vertical Android Phone -> Widescreen Windows PC
# =============================================================================
class ParametricDeviceMorph:
    """
    Renders a tactile woodcut-ink + HDR-lit device centered on a 760x660 canvas that smoothly
    morphs from:
      - u = 0.0: Sleek Vertical Android Smartphone (250 x 460 px)
      - u = 1.0: Widescreen Windows PC Monitor + neck + stand base (580 x 350 px + stand)
    with a warm living miniature pumpkin-lantern glowing inside the screen!
    """

    def __init__(self, cw: int = 780, ch: int = 680):
        self.cw = cw
        self.ch = ch
        yy, xx = np.mgrid[0:ch, 0:cw].astype(np.float32)
        self.xx = xx - cw * 0.5
        self.yy = yy - ch * 0.46
        self.grain = make_woodcut_grain(ch, cw, seed=808)

    @staticmethod
    def _sd_round_box(px: np.ndarray, py: np.ndarray, bx: float, by: float, r: float) -> np.ndarray:
        qx = np.abs(px) - (bx - r)
        qy = np.abs(py) - (by - r)
        out_d = np.sqrt(np.maximum(qx, 0.0) ** 2 + np.maximum(qy, 0.0) ** 2)
        in_d = np.minimum(np.maximum(qx, qy), 0.0)
        return out_d + in_d - r

    def render_onto_hdr(self, frame_hdr: np.ndarray, cx: float, cy: float,
                        u_morph: float, inner_glow: float, scale: float = 1.0,
                        cold_broken: float = 0.0, crack_amt: float = 0.0,
                        opacity: float = 1.0, mini_pump: np.ndarray = None,
                        mini_pump_mask: np.ndarray = None) -> tuple:
        """
        Draws the woodcut-ink smartphone (u_morph=0) OR morphed Windows PC monitor (u_morph=1)
        onto frame_hdr, and returns (scr_cx, scr_cy, scr_half_w, scr_half_h) in screen space!
        """
        if opacity <= 0.003:
            return (cx, cy, 100.0, 180.0)

        u = float(np.clip(u_morph, 0.0, 1.0))
        # Outer body half-extents: Phone (134, 244, r=34) -> PC Monitor (292, 184, r=20)
        bx = 134.0 * (1.0 - u) + 292.0 * u
        by = 244.0 * (1.0 - u) + 184.0 * u
        rad = 34.0 * (1.0 - u) + 20.0 * u

        # Inner screen half-extents
        sbx = bx - (18.0 * (1.0 - u) + 20.0 * u)
        sby = by - (34.0 * (1.0 - u) + 22.0 * u)
        srad = max(rad - 12.0, 8.0)

        px = self.xx / max(scale, 1e-4)
        py = self.yy / max(scale, 1e-4)

        d_outer = self._sd_round_box(px, py, bx, by, rad)
        d_inner = self._sd_round_box(px, py, sbx, sby, srad)

        # Monitor neck + base emerge smoothly as u_morph -> 1.0!
        stand_alpha = smoothstep(0.18, 0.85, u)
        neck_y0 = by + 2.0
        neck_h = 46.0 * stand_alpha
        d_neck = self._sd_round_box(px, py - (neck_y0 + neck_h * 0.5), 26.0, max(neck_h * 0.5, 2.0), 4.0)
        base_y = by + neck_h + 10.0
        d_base = self._sd_round_box(px, py - base_y, 118.0 * stand_alpha + 4.0, 10.0, 6.0)

        # Anti-aliased masks
        body_mask = clamp(1.0 - smoothstep(-1.2, 1.2, d_outer))
        scr_mask = clamp(1.0 - smoothstep(-1.2, 1.2, d_inner))
        bezel_mask = clamp(body_mask - scr_mask)

        # Crisp double woodcut ink strokes on outer rim, inner screen rim, and PC stand
        outer_rim = np.exp(-(d_outer / 2.4) ** 2) + 0.55 * np.exp(-((d_outer + 7.5) / 1.6) ** 2)
        inner_rim = np.exp(-(d_inner / 2.0) ** 2)
        stand_fill = stand_alpha * clamp(np.maximum(1.0 - smoothstep(-1.2, 1.2, d_neck),
                                                    1.0 - smoothstep(-1.2, 1.2, d_base)))
        stand_rim = stand_alpha * (np.exp(-(d_neck / 2.2) ** 2) + np.exp(-(d_base / 2.2) ** 2))

        # Phone speaker slit (fades out as u -> 1) & PC power LED dot (fades in as u -> 1)
        d_spk = self._sd_round_box(px, py + (by - 17.0), 28.0, 3.0, 2.0)
        spk_mask = (1.0 - u) * clamp(1.0 - smoothstep(-1.0, 1.0, d_spk))

        grain = self.grain
        # Dark velvet bezel & screen interior
        rgb = np.zeros((self.ch, self.cw, 3), dtype=np.float32)
        alpha = np.clip(np.maximum(body_mask, stand_fill), 0.0, 1.0)

        # Bezel fill: deep dark umber
        bezel_col = np.array([0.012, 0.004, 0.003], dtype=np.float32)
        rgb += (bezel_mask + stand_fill)[:, :, None] * bezel_col[None, None, :]

        # Screen fill: either cold/flickering soulless screen (Chapter 1) OR warm harvest lantern world (Chapter 4)!
        rn = np.sqrt((px / max(sbx, 1.0)) ** 2 + (py / max(sby, 1.0)) ** 2)
        if cold_broken > 0.01:
            cold_bg = LIN_COLD_GREY[None, None, :] * (0.045 * (1.0 - 0.45 * np.clip(rn, 0.0, 1.2)))[:, :, None]
            rgb += scr_mask[:, :, None] * cold_bg * cold_broken

        if inner_glow > 0.005:
            warm_core = (LIN_GOLD[None, None, :] * (0.85 * np.exp(-(rn * 1.45) ** 2))[:, :, None]
                         + LIN_ORANGE[None, None, :] * (0.42 * np.exp(-(rn * 0.88) ** 2))[:, :, None]
                         + LIN_CRIMSON[None, None, :] * (0.14 * (1.0 - np.clip(rn * 0.65, 0.0, 1.0)))[:, :, None])
            rgb += scr_mask[:, :, None] * warm_core * inner_glow

            # Stamp glowing miniature hero pumpkin silhouette/lantern right in the center of the device screen!
            if mini_pump is not None and mini_pump_mask is not None:
                mh, mw = mini_pump_mask.shape
                target_h = int(round(min(sby * 1.42, 220.0) * scale))
                target_w = max(int(round(target_h * (mw / mh))), 16)
                target_h = max(target_h, 16)
                mp_rgb = cv2.resize(mini_pump, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
                mp_a = cv2.resize(mini_pump_mask, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
                y0_p = int(round(self.ch * 0.46 - target_h * 0.5))
                x0_p = int(round(self.cw * 0.50 - target_w * 0.5))
                y1_p, x1_p = y0_p + target_h, x0_p + target_w
                if 0 <= x0_p and x1_p <= self.cw and 0 <= y0_p and y1_p <= self.ch:
                    clip_a = mp_a * scr_mask[y0_p:y1_p, x0_p:x1_p] * min(inner_glow * 1.15, 1.0)
                    roi_p = rgb[y0_p:y1_p, x0_p:x1_p]
                    roi_p[:] = roi_p * (1.0 - clip_a[:, :, None]) + mp_rgb * (inner_glow * 1.25) * clip_a[:, :, None]

        # Optional jagged crack lines across the soulless screen in Chapter 1 before shatter!
        if crack_amt > 0.01:
            c1 = np.exp(-((py - (0.58 * px - 18.0 * np.sin(px * 0.045))) / 2.2) ** 2)
            c2 = np.exp(-((py - (-0.72 * px + 14.0 * np.cos(px * 0.06))) / 1.9) ** 2)
            cracks = np.clip(c1 + c2, 0.0, 1.0) * scr_mask * crack_amt
            rgb += cracks[:, :, None] * (LIN_GOLD * 1.65)[None, None, :]

        # Ink strokes on rim (warm ivory + subtle harvest-orange glow)
        rim_col = LIN_IVORY * (1.0 - 0.35 * cold_broken) + LIN_ORANGE * (0.45 * inner_glow)
        strokes = np.clip(outer_rim + 0.80 * inner_rim + stand_rim + 0.75 * spk_mask, 0.0, 1.35) * grain
        rgb += strokes[:, :, None] * rim_col[None, None, :]
        alpha = np.clip(alpha + strokes * 0.85, 0.0, 1.0)

        # Soft outer warm halo when inner_glow > 0 (feathered to exact 0 at canvas borders!)
        if inner_glow > 0.02:
            edge_x = np.minimum(self.xx + self.cw * 0.5, self.cw * 0.5 - self.xx)
            edge_y = np.minimum(self.yy + self.ch * 0.46, self.ch * 0.54 - self.yy)
            border_fade = smoothstep(0.0, 72.0, np.minimum(edge_x, edge_y))
            glow_map = np.exp(-np.maximum(d_outer, 0.0) / 24.0) * (0.34 * inner_glow) * border_fade
            rgb += glow_map[:, :, None] * LIN_ORANGE[None, None, :]
            alpha = np.clip(alpha + glow_map * 0.35, 0.0, 1.0)

        # Blit centered at (cx, cy_adj) onto frame_hdr
        H, W, _ = frame_hdr.shape
        x0 = int(round(cx - self.cw * 0.5))
        y0 = int(round(cy - self.ch * 0.46))
        x1, y1 = x0 + self.cw, y0 + self.ch

        sx0, sy0 = max(0, -x0), max(0, -y0)
        dx0, dy0 = max(0, x0), max(0, y0)
        dx1, dy1 = min(W, x1), min(H, y1)
        if dx1 > dx0 and dy1 > dy0:
            sx1, sy1 = sx0 + (dx1 - dx0), sy0 + (dy1 - dy0)
            roi = frame_hdr[dy0:dy1, dx0:dx1]
            a_r = alpha[sy0:sy1, sx0:sx1, None] * opacity
            roi[:] = roi * (1.0 - a_r) + rgb[sy0:sy1, sx0:sx1] * opacity

        return (cx, cy, sbx * scale, sby * scale)


def build_cta_pill_plate(width: int = 780, height: int = 192) -> tuple:
    """Builds the clean End-Card CTA badge ('FOLLOW FROM DAY 1' / 'ANDROID · WINDOWS PC') for Chapter 7."""
    ss = 2
    W2, H2 = width * ss, height * ss
    img_rim = Image.new("L", (W2, H2), 0)
    img_txt1 = Image.new("L", (W2, H2), 0)
    img_txt2 = Image.new("L", (W2, H2), 0)
    img_fill = Image.new("L", (W2, H2), 0)

    dr_rim = ImageDraw.Draw(img_rim)
    dr_fill = ImageDraw.Draw(img_fill)
    dr_t1 = ImageDraw.Draw(img_txt1)
    dr_t2 = ImageDraw.Draw(img_txt2)

    # Tight sleek pill [y: 26 .. 226] in 2x coords (100px tall in 1x), centered cleanly around FOLLOW FROM DAY 1!
    pad_x, py0, py1 = 68, 26, 226
    dr_fill.rounded_rectangle([pad_x, py0, W2 - pad_x, py1], radius=98, fill=255)
    dr_rim.rounded_rectangle([pad_x, py0, W2 - pad_x, py1], radius=98, outline=255, width=6)
    dr_rim.rounded_rectangle([pad_x + 14, py0 + 14, W2 - pad_x - 14, py1 - 14], radius=84, outline=150, width=2)

    f1 = load_font(CINZEL_PATH, 38 * ss, 800)
    f2 = load_font(MONTSERRAT_PATH, 23 * ss, 700)

    def draw_tracked(draw_obj, text, y_top, font, trk):
        advs = [font.getlength(c) for c in text]
        tw = sum(advs) + trk * max(len(text) - 1, 0)
        x = (W2 - tw) * 0.5
        for c, a in zip(text, advs):
            draw_obj.text((x, y_top), c, fill=255, font=font)
            x += a + trk
        return x - tw - trk, x - trk

    # Draw text WITHOUT Unicode symbols and add crisp vector 4-point Pottsfield stars!
    bbox1 = f1.getbbox("FOLLOW FROM DAY 1")
    th1 = bbox1[3] - bbox1[1]
    y_t1 = int(round(0.5 * (py0 + py1) - th1 * 0.5 - bbox1[1]))
    x_l, x_r = draw_tracked(dr_t1, "FOLLOW FROM DAY 1", y_t1, f1, 4 * ss)
    # Vector 4-point stars on left & right inside pill!
    cy_p = 0.5 * (py0 + py1)
    sr = 22
    for sx_s in (0.5 * (pad_x + 36 + x_l) + 18, 0.5 * (x_r + W2 - pad_x - 36) - 18):
        pts = [
            (sx_s, cy_p - sr), (sx_s + sr * 0.26, cy_p - sr * 0.26),
            (sx_s + sr, cy_p), (sx_s + sr * 0.26, cy_p + sr * 0.26),
            (sx_s, cy_p + sr), (sx_s - sr * 0.26, cy_p + sr * 0.26),
            (sx_s - sr, cy_p), (sx_s - sr * 0.26, cy_p - sr * 0.26),
        ]
        dr_t1.polygon(pts, fill=255)

    draw_tracked(dr_t2, "ANDROID   ·   WINDOWS PC", py1 + 42, f2, 7 * ss)

    m_rim = cv2.resize(np.array(img_rim, dtype=np.float32) / 255.0, (width, height), interpolation=cv2.INTER_AREA)
    m_fill = cv2.resize(np.array(img_fill, dtype=np.float32) / 255.0, (width, height), interpolation=cv2.INTER_AREA)
    m_t1 = cv2.resize(np.array(img_txt1, dtype=np.float32) / 255.0, (width, height), interpolation=cv2.INTER_AREA)
    m_t2 = cv2.resize(np.array(img_txt2, dtype=np.float32) / 255.0, (width, height), interpolation=cv2.INTER_AREA)

    grain = make_woodcut_grain(height, width, seed=909)
    rgb = (
        m_fill[:, :, None] * np.array([0.024, 0.007, 0.004], dtype=np.float32)[None, None, :]
        + m_rim[:, :, None] * (LIN_ORANGE * 0.95)[None, None, :] * grain[:, :, None]
        + m_t1[:, :, None] * (LIN_IVORY * 1.12)[None, None, :] * grain[:, :, None]
        + m_t2[:, :, None] * (LIN_GOLD * 0.96)[None, None, :]
    )
    halo = cv2.GaussianBlur(m_rim + m_t1 * 0.7, (0, 0), sigmaX=9.0, sigmaY=9.0)
    rgb += halo[:, :, None] * (LIN_ORANGE * 0.42)[None, None, :]
    alpha = np.clip(m_fill * 0.90 + m_rim + m_t1 + m_t2 + halo * 0.25, 0.0, 1.0)
    return rgb.astype(np.float32), alpha.astype(np.float32)

