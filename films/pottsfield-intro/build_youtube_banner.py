"""Pottsfield Studio — 4K (3840x2160) & 2.5K (2560x1440) YouTube Channel Banner Generator.

Engineered for 100% crispness and zero clipping across ALL 4 YouTube viewports:
  - Modern Android / iOS YouTube App Rounded Pill (aspect 3.0462:1 inside center 29.375% height)
  - Classic Mobile Safe Box (1546x423 @ 2.5K / 2319x634 @ 4K)
  - Tablet & Desktop Wide Header (2560x423 @ 2.5K / 3840x634 @ 4K)
  - Smart TV Full 16:9 Key-Art Mural (2560x1440 / 3840x2160)
"""
import math
import os
import sys
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from engine import srgb_to_linear, linear_to_srgb_u8, aces_tonemap, clamp, smoothstep
from prepare_assets import HERO_IN_LOGO_SCALE, HERO_IN_LOGO_OX, HERO_IN_LOGO_OY
from oneshot_graphics import (
    CINZEL_PATH,
    FELL_IT_PATH,
    MONTSERRAT_PATH,
    LIN_IVORY,
    LIN_GOLD,
    LIN_ORANGE,
    LIN_CRIMSON,
    load_font,
    make_woodcut_grain,
)


def sdf_upscale_rgba(rgb_lin_crop: np.ndarray, mask_u8: np.ndarray, scale: float) -> tuple:
    """
    Reconstructs razor-sharp anti-aliased vector-grade edges at `scale`x resolution using
    Signed Distance Fields (cv2.distanceTransform), eliminating bitmap stair-stepping on zoom!
    """
    th, tw = int(round(mask_u8.shape[0] * scale)), int(round(mask_u8.shape[1] * scale))
    fg = (mask_u8 > 110).astype(np.uint8)
    bg = 1 - fg
    dist_in = cv2.distanceTransform(fg, cv2.DIST_L2, 5)
    dist_out = cv2.distanceTransform(bg, cv2.DIST_L2, 5)
    sdf = dist_in - dist_out

    sdf_up = cv2.resize(sdf, (tw, th), interpolation=cv2.INTER_CUBIC) * scale
    alpha_up = np.clip(0.5 + sdf_up / 1.35, 0.0, 1.0).astype(np.float32)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    rgb_pad = rgb_lin_crop.copy()
    valid = (mask_u8 > 40).astype(np.uint8)
    for _ in range(5):
        dil_rgb = cv2.dilate(rgb_pad, kernel)
        dil_v = cv2.dilate(valid, kernel)
        fill = (valid == 0) & (dil_v > 0)
        rgb_pad[fill] = dil_rgb[fill]
        valid = dil_v

    rgb_up = cv2.resize(rgb_pad, (tw, th), interpolation=cv2.INTER_LANCZOS4)

    gy, gx = np.gradient(np.clip(sdf_up, 0.0, 14.0))
    rim_band = np.exp(-((sdf_up - 2.4) / 2.6) ** 2) * alpha_up
    bevel = np.clip((-0.45 * gx - 0.65 * gy) * 0.35, -0.25, 0.45) * rim_band
    return rgb_up.astype(np.float32), alpha_up, bevel.astype(np.float32)


def paste_hdr(canvas_hdr: np.ndarray, src_rgb: np.ndarray, src_a: np.ndarray,
              x0: int, y0: int, shadow_sigma: float = 0.0, shadow_str: float = 0.0):
    """Alpha-blends linear HDR plate (src_rgb, src_a) onto canvas_hdr at top-left (x0, y0)."""
    H, W, _ = canvas_hdr.shape
    sh, sw = src_a.shape
    sx0, sy0 = max(0, -x0), max(0, -y0)
    dx0, dy0 = max(0, x0), max(0, y0)
    dx1, dy1 = min(W, x0 + sw), min(H, y0 + sh)
    if dx1 <= dx0 or dy1 <= dy0:
        return
    sx1, sy1 = sx0 + (dx1 - dx0), sy0 + (dy1 - dy0)

    roi = canvas_hdr[dy0:dy1, dx0:dx1]
    a_sub = src_a[sy0:sy1, sx0:sx1]
    if shadow_sigma > 0.5 and shadow_str > 0.01:
        sh_m = cv2.GaussianBlur(a_sub, (0, 0), sigmaX=shadow_sigma, sigmaY=shadow_sigma)
        roi *= (1.0 - np.clip(sh_m * shadow_str, 0.0, 0.94)[:, :, None])

    roi[:] = roi * (1.0 - a_sub[:, :, None]) + src_rgb[sy0:sy1, sx0:sx1] * a_sub[:, :, None]


def render_tracked_text_hdr(text: str, font_path: str, size_px: int, weight: int,
                            tracking: int, col_top: np.ndarray, col_bot: np.ndarray,
                            glow_col: np.ndarray, glow_str: float = 0.42,
                            with_stars: bool = False) -> tuple:
    """Renders 2x supersampled tracked display/italic text into straight linear HDR (rgb, alpha)."""
    ss = 2
    font = load_font(font_path, size_px * ss, weight)
    trk = tracking * ss
    advs = [font.getlength(c) for c in text]
    tw2 = sum(advs) + trk * max(len(text) - 1, 0)
    pad_x2 = int((size_px * 2.8 + 44) * ss)
    pad_y2 = int((size_px * 0.80 + 26) * ss)
    W2 = int(math.ceil(tw2 + 2 * pad_x2))
    H2 = int(math.ceil(size_px * 1.48 * ss + 2 * pad_y2))
    W2 += W2 % 2
    H2 += H2 % 2

    img = Image.new("L", (W2, H2), 0)
    drw = ImageDraw.Draw(img)
    x_cur = (W2 - tw2) * 0.5
    x_start = x_cur
    y_cur = pad_y2
    for ch, adv in zip(text, advs):
        drw.text((x_cur, y_cur), ch, fill=255, font=font)
        x_cur += adv + trk
    x_end = x_cur - trk

    if with_stars:
        bbox = font.getbbox(text)
        cy_s = y_cur + 0.5 * (bbox[1] + bbox[3])
        sr = max(int(size_px * 0.36 * ss), 12)
        for sx_s in (x_start - sr * 3.1, x_end + sr * 3.1):
            pts = [
                (sx_s, cy_s - sr), (sx_s + sr * 0.26, cy_s - sr * 0.26),
                (sx_s + sr, cy_s), (sx_s + sr * 0.26, cy_s + sr * 0.26),
                (sx_s, cy_s + sr), (sx_s - sr * 0.26, cy_s + sr * 0.26),
                (sx_s - sr, cy_s), (sx_s - sr * 0.26, cy_s - sr * 0.26),
            ]
            drw.polygon(pts, fill=255)

    W1, H1 = W2 // ss, H2 // ss
    m = cv2.resize(np.array(img, dtype=np.float32) / 255.0, (W1, H1), interpolation=cv2.INTER_AREA)
    ys = np.where(m.max(axis=1) > 0.05)[0]
    y0_g, y1_g = (int(ys.min()), int(ys.max())) if len(ys) else (0, H1 - 1)
    ly = np.clip((np.arange(H1, dtype=np.float32)[:, None] - y0_g) / max(y1_g - y0_g, 1), 0.0, 1.0)

    grain = make_woodcut_grain(H1, W1, seed=size_px + len(text))
    fill_rgb = (col_top[None, None, :] * (1.0 - ly[:, :, None]) + col_bot[None, None, :] * ly[:, :, None]) * grain[:, :, None]
    halo = cv2.GaussianBlur(m, (0, 0), sigmaX=9.0, sigmaY=9.0)
    alpha = np.clip(m + halo * 0.26 * glow_str, 0.0, 1.0)
    premult = fill_rgb * m[:, :, None] + glow_col[None, None, :] * (halo * glow_str)[:, :, None]
    straight = premult / np.maximum(alpha[:, :, None], 1e-4)
    return straight.astype(np.float32), alpha.astype(np.float32)


def draw_maple_leaf(draw_sil: ImageDraw.ImageDraw, draw_edg: ImageDraw.ImageDraw,
                    cx: float, cy: float, sz: float, angle: float):
    """Draws an organic 5-lobed autumn maple/oak leaf silhouette + woodcut stem/vein."""
    ca, sa = math.cos(angle), math.sin(angle)
    # 5-lobe maple leaf contour in local leaf coordinates
    local_pts = [
        (0.0, -1.05), (0.22, -0.58), (0.82, -0.68), (0.48, -0.18),
        (0.95, 0.16), (0.36, 0.34), (0.42, 0.78), (0.0, 0.56),
        (-0.42, 0.78), (-0.36, 0.34), (-0.95, 0.16), (-0.48, -0.18),
        (-0.82, -0.68), (-0.22, -0.58),
    ]
    pts = [(cx + (px * ca - py * sa) * sz, cy + (px * sa + py * ca) * sz) for px, py in local_pts]
    draw_sil.polygon(pts, fill=255)
    draw_edg.polygon(pts, outline=220)


def draw_panoramic_autumn_world(hdr: np.ndarray):
    """
    Paints the 3840x2160 16:9 dark-autumn atmospheric world in deep obsidian velvet (#040100 -> #000000)
    matching the Pottsfield avatar & One-Shot film, with warm localized lantern pools!
    """
    H, W, _ = hdr.shape  # 2160 x 3840
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

    # 1. Deep Obsidian Velvet Base + Focused Localized Lantern Pools (rich contrast, never washed-out brown!)
    wing_glow = (
        0.042 * np.exp(-(((xx - W * 0.17) / 520.0) ** 2 + ((yy - H * 0.50) / 360.0) ** 2))
        + 0.042 * np.exp(-(((xx - W * 0.83) / 520.0) ** 2 + ((yy - H * 0.50) / 360.0) ** 2))
        + 0.032 * np.exp(-(((xx - W * 0.50) / 760.0) ** 2 + ((yy - H * 0.49) / 260.0) ** 2))
        + 0.030 * np.exp(-(((xx - W * 0.66) / 540.0) ** 2 + ((yy - H * 0.17) / 260.0) ** 2))
    )
    hdr[:] += wing_glow[:, :, None] * (LIN_ORANGE * 0.80 + LIN_CRIMSON * 0.32)[None, None, :]

    # 2. Analytic True Crescent Harvest Moon in Smart TV Upper Sky (X=2540, Y=335 — zero circle artifact!)
    mx, my, mr = 2540.0, 335.0, 175.0
    r_outer = np.sqrt((xx - mx) ** 2 + (yy - my) ** 2) - mr
    r_inner = np.sqrt((xx - (mx + 62.0)) ** 2 + (yy - (my - 26.0)) ** 2) - (mr * 0.90)
    cres_sdf = np.maximum(r_outer, -r_inner)
    cres_fill = clamp(1.0 - smoothstep(-1.5, 1.5, cres_sdf))
    cres_rim = np.exp(-(cres_sdf / 2.2) ** 2) * clamp(1.0 - smoothstep(-3.0, 3.0, r_outer + 8.0))
    cres_halo = cv2.GaussianBlur(cres_fill, (0, 0), sigmaX=32.0, sigmaY=32.0)
    hdr[:] += (
        cres_fill[:, :, None] * (LIN_GOLD * 0.52 + LIN_ORANGE * 0.22)[None, None, :]
        + cres_rim[:, :, None] * (LIN_IVORY * 0.55)[None, None, :]
        + cres_halo[:, :, None] * (LIN_ORANGE * 0.25)[None, None, :]
    )

    # 3. Far Hills & Gothic Lantern Spire (strictly outside Mobile Pill!)
    sil_far = Image.new("L", (W, H), 0)
    edg_far = Image.new("L", (W, H), 0)
    lan_far = Image.new("L", (W, H), 0)
    ds_f, de_f, dl_f = ImageDraw.Draw(sil_far), ImageDraw.Draw(edg_far), ImageDraw.Draw(lan_far)

    hill_pts = [(0, H)]
    for x in range(0, W + 40, 40):
        center_dip = 110.0 * math.exp(-((x - W * 0.5) / 920.0) ** 2)
        yh = int(1478 + center_dip - 56.0 * math.sin(x * 0.0028) - 30.0 * math.cos(x * 0.0061))
        hill_pts.append((x, yh))
    hill_pts.append((W, H))
    ds_f.polygon(hill_pts, fill=255)
    de_f.line(hill_pts[1:-1], fill=175, width=4)

    # Distant Gothic Spire on outer-left Tablet/Desktop hill (X = 590)
    tx, ty = 590, 1425
    spire = [(tx - 54, ty + 80), (tx - 40, ty - 185), (tx - 60, ty - 185),
             (tx, ty - 365), (tx + 60, ty - 185), (tx + 40, ty - 185), (tx + 54, ty + 80)]
    ds_f.polygon(spire, fill=255)
    de_f.line(spire, fill=205, width=4)
    dl_f.rounded_rectangle([tx - 15, ty - 165, tx + 15, ty - 106], radius=14, fill=255)

    # 4. Midground Gnarled Gothic Autumn Oaks in Desktop Wings (kept 100% clear of X=[945..2895] Android Pill!)
    sil_mid = Image.new("L", (W, H), 0)
    edg_mid = Image.new("L", (W, H), 0)
    lan_mid = Image.new("L", (W, H), 0)
    ds_m, de_m, dl_m = ImageDraw.Draw(sil_mid), ImageDraw.Draw(edg_mid), ImageDraw.Draw(lan_mid)

    rng_t = np.random.default_rng(202615)
    oak_specs = [
        (165,  1, 1.10),
        (435,  1, 0.86),
        (3405, -1, 0.86),
        (3675, -1, 1.10),
    ]
    for bx, inward_dir, sc_t in oak_specs:
        by = 1700
        top_y = int(1700 - 930 * sc_t)
        trunk_w = 50 * sc_t
        pts_l, pts_r = [], []
        for s in range(18):
            u = s / 17.0
            yy_s = by - (by - top_y) * u
            curve = inward_dir * (u ** 1.5) * 78.0 * sc_t + math.sin(u * 2.5 + bx) * 18.0
            tw = trunk_w * (1.0 - 0.62 * u)
            pts_l.append((bx + curve - tw, yy_s))
            pts_r.append((bx + curve + tw, yy_s))
        ds_m.polygon(pts_l + pts_r[::-1], fill=255)
        de_m.line(pts_l, fill=215, width=4)
        de_m.line(pts_r, fill=215, width=4)
        for bf in (-0.32, 0.26):
            bark = [(0.5 * (pts_l[s][0] + pts_r[s][0]) + bf * (pts_r[s][0] - pts_l[s][0]), pts_l[s][1])
                    for s in range(16)]
            de_m.line(bark, fill=120, width=2)

        tx_top = 0.5 * (pts_l[-1][0] + pts_r[-1][0])
        ty_top = pts_l[-1][1]

        # Bough reach capped at 315*sc_t so inward tip ends at X ~ 775 (left) and X ~ 3065 (right) — well outside X=[954..2886]!
        boughs = [
            (inward_dir,  310 * sc_t,  85 * sc_t, 0.78, True),
            (inward_dir,  220 * sc_t, -185 * sc_t, 0.55, False),
            (-inward_dir, 210 * sc_t, -115 * sc_t, 0.65, True),
        ]
        for b_dir, rx, ry, hu, hang_l in boughs:
            bl, br = [], []
            for s in range(12):
                u = s / 11.0
                cx_b = tx_top + b_dir * u * rx
                cy_b = ty_top + u * ry - math.sin(u * math.pi) * 56.0 * sc_t
                bw = 14.0 * sc_t * (1.0 - 0.78 * u)
                bl.append((cx_b, cy_b - bw))
                br.append((cx_b, cy_b + bw))
            ds_m.polygon(bl + br[::-1], fill=255)
            de_m.line(bl, fill=215, width=3)
            de_m.line(br, fill=175, width=2)

            tip_x, tip_y = bl[-1]
            for _ in range(6):
                ang = float(rng_t.uniform(0, 2 * math.pi))
                lx_c = tip_x + float(rng_t.uniform(-34, 34))
                ly_c = tip_y + float(rng_t.uniform(-28, 28))
                draw_maple_leaf(ds_m, de_m, lx_c, ly_c, sz=18.0 * sc_t, angle=ang)

            if hang_l:
                hi = int(round(hu * 11))
                ax_l, ay_l = int(br[hi][0]), int(br[hi][1])
                lx, ly = ax_l, ay_l + int(84 * sc_t)
                de_m.line([(ax_l, ay_l), (lx, ly - 30)], fill=220, width=3)
                cap = [(lx - 28, ly - 22), (lx, ly - 40), (lx + 28, ly - 22)]
                ds_m.polygon(cap, fill=255)
                de_m.polygon(cap, outline=245)
                ds_m.rounded_rectangle([lx - 22, ly - 22, lx + 22, ly + 28], radius=9, fill=255)
                de_m.rounded_rectangle([lx - 22, ly - 22, lx + 22, ly + 28], radius=9, outline=250, width=4)
                dl_m.ellipse([lx - 15, ly - 15, lx + 15, ly + 20], fill=255)

    grain = make_woodcut_grain(H, W, seed=404)
    f_sil = np.array(sil_far, dtype=np.float32) / 255.0
    f_edg = np.array(edg_far, dtype=np.float32) / 255.0
    f_lan = np.array(lan_far, dtype=np.float32) / 255.0

    m_sil = np.array(sil_mid, dtype=np.float32) / 255.0
    m_edg = np.array(edg_mid, dtype=np.float32) / 255.0
    m_lan = np.array(lan_mid, dtype=np.float32) / 255.0

    hdr[:] = hdr * (1.0 - f_sil[:, :, None] * 0.94) + np.array([0.005, 0.0015, 0.001], dtype=np.float32)[None, None, :] * f_sil[:, :, None]
    hdr[:] += (f_edg * grain * 0.42)[:, :, None] * (LIN_ORANGE * 0.72 + LIN_IVORY * 0.22)[None, None, :]
    f_halo = cv2.GaussianBlur(f_lan, (0, 0), sigmaX=28.0, sigmaY=28.0)
    hdr[:] += f_lan[:, :, None] * (LIN_GOLD * 1.35)[None, None, :] + f_halo[:, :, None] * (LIN_ORANGE * 0.85)[None, None, :]

    hdr[:] = hdr * (1.0 - m_sil[:, :, None] * 0.96) + np.array([0.003, 0.001, 0.0008], dtype=np.float32)[None, None, :] * m_sil[:, :, None]
    hdr[:] += (m_edg * grain * 0.65)[:, :, None] * (LIN_ORANGE * 0.92 + LIN_GOLD * 0.28)[None, None, :]
    m_halo_tight = cv2.GaussianBlur(m_lan, (0, 0), sigmaX=22.0, sigmaY=22.0)
    m_halo_wide = cv2.GaussianBlur(cv2.resize(m_lan, (W // 4, H // 4), interpolation=cv2.INTER_AREA), (0, 0), sigmaX=24.0)
    m_halo_wide = cv2.resize(m_halo_wide, (W, H), interpolation=cv2.INTER_LINEAR)
    hdr[:] += (
        m_lan[:, :, None] * (LIN_IVORY * 1.85)[None, None, :]
        + m_halo_tight[:, :, None] * (LIN_GOLD * 1.40)[None, None, :]
        + m_halo_wide[:, :, None] * (LIN_ORANGE * 1.25)[None, None, :]
    )

    # 5. Subtle Golden & Crimson Ember Bokeh
    rng_p = np.random.default_rng(202612)
    for _ in range(130):
        px = float(rng_p.uniform(40, W - 40))
        py = float(rng_p.uniform(40, H - 40))
        if 1180 < px < 2660 and 790 < py < 1365:
            continue
        rad = float(rng_p.uniform(3.0, 13.0))
        r_box = int(rad * 3.8)
        x0, y0 = max(0, int(px) - r_box), max(0, int(py) - r_box)
        x1, y1 = min(W, int(px) + r_box + 1), min(H, int(py) + r_box + 1)
        gx = xx[y0:y1, x0:x1] - px
        gy = yy[y0:y1, x0:x1] - py
        r2 = gx * gx + gy * gy
        win = (1.0 - np.clip(r2 / float(r_box * r_box), 0.0, 1.0)) ** 2
        orb = np.exp(-r2 / (2.0 * (rad * 0.55) ** 2)) * win
        col = LIN_GOLD * float(rng_p.uniform(0.16, 0.48)) if rng_p.random() > 0.35 else LIN_CRIMSON * 0.42
        hdr[y0:y1, x0:x1] += orb[:, :, None] * col[None, None, :]


def extract_clean_interior_components(mask_crop: np.ndarray, min_area: int = 25) -> np.ndarray:
    """Keeps ONLY complete connected components that do NOT touch any border of mask_crop (zero clipped wings/letters!)."""
    h, w = mask_crop.shape
    num, labels, stats, _ = cv2.connectedComponentsWithStats((mask_crop > 80).astype(np.uint8))
    clean = np.zeros_like(mask_crop)
    for i in range(1, num):
        x, y, cw, ch, area = stats[i]
        if area < min_area:
            continue
        if x <= 1 or y <= 1 or (x + cw) >= w - 1 or (y + ch) >= h - 1:
            continue
        clean[labels == i] = 255
    return clean


def build_banner():
    W, H = 3840, 2160
    cx, cy = W // 2, H // 2  # (1920, 1080)

    d = np.load(os.path.join(HERE, "work", "prepared_assets.npz"))
    logo_srgb = d["logo_clean"]
    logo_lin = srgb_to_linear(logo_srgb)

    hdr = np.zeros((H, W, 3), dtype=np.float32)
    draw_panoramic_autumn_world(hdr)

    # Focused warm ember aura directly behind Pottsfield STUDIO (surrounded by deep velvet obsidian!)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    hero_back = np.exp(-(((xx - cx) / 480.0) ** 2 + ((yy - (cy - 18.0)) / 165.0) ** 2))
    hdr += hero_back[:, :, None] * (LIN_ORANGE * 0.085 + LIN_CRIMSON * 0.045)[None, None, :]

    ink_all = (logo_srgb.max(axis=2) > 22).astype(np.uint8) * 255

    # Build exact registered hero-pumpkin silhouette mask in 1254x1254 logo space so we know the curved boundary!
    M_h2l = np.float32([
        [HERO_IN_LOGO_SCALE, 0.0, HERO_IN_LOGO_OX],
        [0.0, HERO_IN_LOGO_SCALE, HERO_IN_LOGO_OY],
    ])
    hero_sil_in_logo = cv2.warpAffine(d["hero_sil"], M_h2l, (1254, 1254), flags=cv2.INTER_LINEAR)
    # Dilate hero silhouette slightly + feather by 28px so where companion pumpkins tucked behind the hero pumpkin,
    # they fade out along a natural round pumpkin curve — ZERO straight vertical crop line!
    hero_occ = cv2.GaussianBlur((hero_sil_in_logo > 80).astype(np.float32), (0, 0), sigmaX=18.0, sigmaY=18.0)
    non_hero_fade = np.clip(1.0 - hero_occ * 1.35, 0.0, 1.0)

    # =========================================================================
    # 1. LEFT & RIGHT ORGANIC HARVEST WREATH BRACKETS (ZERO HARD CROP EDGES!)
    # =========================================================================
    # Strictly exclude ring, hero, Pottsfield, AND STUDIO (`w_studio < 15`) so zero letter slivers ever appear!
    wreath_clean = np.zeros_like(ink_all)
    valid_wreath = (
        (ink_all > 0)
        & (d["w_ring"] < 120)
        & (hero_sil_in_logo < 90)
        & (d["w_potts"] < 25)
        & (d["w_studio"] < 15)
    )
    wreath_clean[valid_wreath] = 255

    # Extract Left Wreath [515:1120, 105:495] & Right Wreath [495:1125, 765:1145]
    for side, (sy0, sy1, sx0, sx1), target_cx, target_cy in [
        ("L", (515, 1120, 105, 495), 1205, 1085),
        ("R", (495, 1125, 765, 1145), 2635, 1082),
    ]:
        sub_m = wreath_clean[sy0:sy1, sx0:sx1].copy()
        # Drop any tiny disconnected border slivers at top/bottom/outer edges
        num_c, lab_c, stats_c, _ = cv2.connectedComponentsWithStats((sub_m > 0).astype(np.uint8))
        for cid in range(1, num_c):
            bx_c, by_c, bw_c, bh_c, area_c = stats_c[cid]
            if area_c < 90:
                sub_m[lab_c == cid] = 0
            elif by_c <= 2 and area_c < 1800:  # remove clipped top leaf/butterfly slivers
                sub_m[lab_c == cid] = 0

        sub_rgb = logo_lin[sy0:sy1, sx0:sx1].copy()
        sub_fade = non_hero_fade[sy0:sy1, sx0:sx1].copy()
        # Also apply smooth organic radial+inner feather so inner side towards Pottsfield melts into velvet black!
        sh_h, sh_w = sub_m.shape
        yy_s, xx_s = np.mgrid[0:sh_h, 0:sh_w].astype(np.float32)
        if side == "L":
            inner_soft = 1.0 - smoothstep(sh_w * 0.68, sh_w * 0.96, xx_s)
        else:
            inner_soft = smoothstep(sh_w * 0.04, sh_w * 0.32, xx_s)
        vert_soft = smoothstep(0.0, 26.0, yy_s) * (1.0 - smoothstep(sh_h - 32.0, float(sh_h), yy_s))
        env_mask = sub_fade * inner_soft * vert_soft

        sc_w = 0.70
        r2, a2, _ = sdf_upscale_rgba(sub_rgb, sub_m, scale=sc_w * 2.0)
        ww = int(round(sh_w * sc_w))
        wh = int(round(sh_h * sc_w))
        rw_f = cv2.resize(r2, (ww, wh), interpolation=cv2.INTER_AREA) * 1.15
        aw_f = cv2.resize(a2, (ww, wh), interpolation=cv2.INTER_AREA) * cv2.resize(env_mask, (ww, wh), interpolation=cv2.INTER_LINEAR)

        bright_p = np.clip((rw_f[:, :, 0] - 0.32) * 2.2, 0.0, 1.0) * aw_f
        p_halo = cv2.GaussianBlur(bright_p, (0, 0), sigmaX=15.0, sigmaY=15.0)
        hdr_x0, hdr_y0 = target_cx - ww // 2, target_cy - wh // 2
        paste_hdr(hdr, rw_f, aw_f, hdr_x0, hdr_y0, shadow_sigma=14.0, shadow_str=0.85)
        hx0, hy0 = max(0, hdr_x0), max(0, hdr_y0)
        hx1, hy1 = min(W, hdr_x0 + ww), min(H, hdr_y0 + wh)
        if hx1 > hx0 and hy1 > hy0:
            hdr[hy0:hy1, hx0:hx1] += p_halo[:hy1 - hy0, :hx1 - hx0, None] * (LIN_ORANGE * 0.26)[None, None, :]

    # =========================================================================
    # 2. COMPLETE UNCLIPPED BUTTERFLIES & 4-POINT STARS FROM OFFICIAL LOGO
    # =========================================================================
    keep_stars = (d["w_stars"] > 110) & (d["w_ring"] < 100) & (d["w_potts"] < 40)
    stars_only = np.zeros_like(ink_all)
    stars_only[(ink_all > 0) & keep_stars] = 255

    # Widen crop boxes [120:545, 130:430] & [120:545, 825:1120] and filter ONLY interior whole components!
    for (sy0, sy1, sx0, sx1), dst_x, dst_y in [
        ((125, 535, 132, 430), 1295, 795),
        ((125, 535, 825, 1122), 2345, 795),
    ]:
        sm = extract_clean_interior_components(stars_only[sy0:sy1, sx0:sx1], min_area=30)
        if sm.max() == 0:
            continue
        sr_rgb = logo_lin[sy0:sy1, sx0:sx1]
        r2, a2, _ = sdf_upscale_rgba(sr_rgb, sm, scale=1.5)
        sw_t = int(round(sm.shape[1] * 0.75))
        sh_t = int(round(sm.shape[0] * 0.75))
        paste_hdr(hdr,
                  cv2.resize(r2, (sw_t, sh_t), interpolation=cv2.INTER_AREA) * 1.25,
                  cv2.resize(a2, (sw_t, sh_t), interpolation=cv2.INTER_AREA),
                  dst_x, dst_y, shadow_sigma=6.0, shadow_str=0.55)

    # =========================================================================
    # 3. HERO 'Pottsfield STUDIO' 4K SDF WORDMARK (CRISP & UNCLIPPED!)
    # =========================================================================
    keep_word = (d["w_potts"] > 90) | (d["w_studio"] > 90)
    letters_only_mask = np.zeros_like(ink_all)
    letters_only_mask[(ink_all > 0) & keep_word] = 255
    lyl0 = int(np.where(letters_only_mask > 0)[0].min()) - 10
    lyl1 = int(np.where(letters_only_mask > 0)[0].max()) + 10
    lxl0 = int(np.where(letters_only_mask > 0)[1].min()) - 10
    lxl1 = int(np.where(letters_only_mask > 0)[1].max()) + 10

    sc_word = 1.02
    rgb_let_2x, a_let_2x, bev_let_2x = sdf_upscale_rgba(
        logo_lin[lyl0:lyl1, lxl0:lxl1], letters_only_mask[lyl0:lyl1, lxl0:lxl1], scale=sc_word * 2.0
    )
    tw_let = int(round((lxl1 - lxl0) * sc_word))
    th_let = int(round((lyl1 - lyl0) * sc_word))
    rgb_let = cv2.resize(rgb_let_2x, (tw_let, th_let), interpolation=cv2.INTER_AREA)
    a_let = cv2.resize(a_let_2x, (tw_let, th_let), interpolation=cv2.INTER_AREA)
    bev_let = cv2.resize(bev_let_2x, (tw_let, th_let), interpolation=cv2.INTER_AREA)

    is_potts_bright = (rgb_let[:, :, 0] > 0.25).astype(np.float32)
    # Boost STUDIO crimson slightly too so it reads boldly on OLED phones!
    is_studio_crim = ((rgb_let[:, :, 0] <= 0.25) & (a_let > 0.2)).astype(np.float32)
    rgb_let_hdr = (
        rgb_let * (1.14 + 0.28 * bev_let[:, :, None] + 0.30 * is_studio_crim[:, :, None])
        + (LIN_GOLD * 0.24)[None, None, :] * (np.maximum(bev_let, 0.0) * is_potts_bright)[:, :, None]
    )

    let_x0 = cx - tw_let // 2 + 8
    let_y0 = 834

    let_glow = cv2.GaussianBlur(a_let, (0, 0), sigmaX=18.0, sigmaY=18.0)
    gx0, gy0 = max(0, let_x0), max(0, let_y0)
    gx1, gy1 = min(W, let_x0 + tw_let), min(H, let_y0 + th_let)
    hdr[gy0:gy1, gx0:gx1] += let_glow[:gy1 - gy0, :gx1 - gx0, None] * (LIN_ORANGE * 0.22)[None, None, :]
    paste_hdr(hdr, rgb_let_hdr, a_let, let_x0, let_y0, shadow_sigma=16.0, shadow_str=0.90)

    # =========================================================================
    # 4. TOP OVERLINE & BOTTOM TAGLINE (100% INSIDE ANDROID PILL SAFE ZONE!)
    # =========================================================================
    c_crim_bright = srgb_to_linear(np.array([[[238, 92, 68]]], dtype=np.uint8))[0, 0]
    over_rgb, over_a = render_tracked_text_hdr(
        "A   L U M R O O K   S T U D I O",
        MONTSERRAT_PATH, size_px=19, weight=700, tracking=6,
        col_top=c_crim_bright * 1.15, col_bot=LIN_CRIMSON * 1.25,
        glow_col=LIN_CRIMSON, glow_str=0.35, with_stars=True
    )
    paste_hdr(hdr, over_rgb, over_a, cx - over_a.shape[1] // 2, 804 - over_a.shape[0] // 2,
              shadow_sigma=8.0, shadow_str=0.88)

    div_cx = cx + 24
    div_y = 1220
    for dx in range(-220, 221):
        w_line = 1.0 - abs(dx) / 220.0
        if abs(dx) > 18:
            hdr[div_y - 1:div_y + 2, div_cx + dx] += (LIN_CRIMSON * 0.85 * w_line)[None, :]
    for dy_s in range(-7, 8):
        for dx_s in range(-7, 8):
            if abs(dx_s) * 0.35 + abs(dy_s) <= 2.6 or abs(dy_s) * 0.35 + abs(dx_s) <= 2.6:
                hdr[div_y + dy_s, div_cx + dx_s] = LIN_GOLD * 1.50

    c_cream = srgb_to_linear(np.array([[[252, 236, 212]]], dtype=np.uint8))[0, 0]
    tag_rgb, tag_a = render_tracked_text_hdr(
        "“Driven by Story. Lit by Soul.”",
        FELL_IT_PATH, size_px=34, weight=None, tracking=1,
        col_top=LIN_IVORY * 1.10, col_bot=c_cream * 0.98,
        glow_col=LIN_ORANGE, glow_str=0.36, with_stars=False
    )
    paste_hdr(hdr, tag_rgb, tag_a, div_cx - tag_a.shape[1] // 2, 1266 - tag_a.shape[0] // 2,
              shadow_sigma=10.0, shadow_str=0.90)

    plat_rgb, plat_a = render_tracked_text_hdr(
        "2D & 3D STORY WORLDS   ·   ANDROID  &  WINDOWS PC",
        MONTSERRAT_PATH, size_px=17, weight=700, tracking=5,
        col_top=LIN_GOLD * 1.06, col_bot=LIN_ORANGE * 0.98,
        glow_col=LIN_ORANGE, glow_str=0.30, with_stars=False
    )
    paste_hdr(hdr, plat_rgb, plat_a, div_cx - plat_a.shape[1] // 2, 1322 - plat_a.shape[0] // 2,
              shadow_sigma=8.0, shadow_str=0.88)

    # =========================================================================
    # 5. OPTICAL HDR BLOOM & ACES FILMIC TONEMAPPING -> LOSSLESS PNG EXPORTS
    # =========================================================================
    bright = np.maximum(hdr - 0.55, 0.0)
    b_q = cv2.resize(bright, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    bloom = cv2.resize(
        cv2.GaussianBlur(b_q, (0, 0), sigmaX=4.0) * 0.14 + cv2.GaussianBlur(b_q, (0, 0), sigmaX=14.0) * 0.12,
        (W, H), interpolation=cv2.INTER_LINEAR
    )
    hdr += bloom

    banner_4k_u8 = linear_to_srgb_u8(aces_tonemap(hdr))
    banner_2k_u8 = cv2.resize(banner_4k_u8, (2560, 1440), interpolation=cv2.INTER_AREA)

    # Save 1) 4K (3840x2160) Lossless PNG (< 6 MB YouTube limit — MAXIMUM POSSIBLE QUALITY!)
    out_4k_png = os.path.join(HERE, "pottsfield-youtube-banner-4k.png")
    Image.fromarray(banner_4k_u8).save(out_4k_png, optimize=True)

    # Save 2) Official Standard 2560x1440 Lossless PNG
    out_2k_png = os.path.join(HERE, "pottsfield-youtube-banner-2560x1440.png")
    Image.fromarray(banner_2k_u8).save(out_2k_png, optimize=True)

    # Remove old 4k.jpg if present so repo stays super clean
    old_jpg = os.path.join(HERE, "pottsfield-youtube-banner-4k.jpg")
    if os.path.exists(old_jpg):
        os.remove(old_jpg)

    print(f"Saved 4K   PNG (3840x2160): {out_4k_png} ({os.path.getsize(out_4k_png)/1e6:.2f} MB)")
    print(f"Saved 2.5K PNG (2560x1440): {out_2k_png} ({os.path.getsize(out_2k_png)/1e6:.2f} MB)")

    # =========================================================================
    # 6. REAL-DEVICE PROOF PREVIEWS (ANDROID SCREENSHOT + DESKTOP + TV)
    # =========================================================================
    os.makedirs("/tmp/banner_qa", exist_ok=True)
    sc_path = "/tmp/arena-coding-uploads/Screenshot_2026-10-29-21-37-36-569_com.google.android.youtube-edit.jpg"
    if os.path.exists(sc_path):
        sc_orig = np.array(Image.open(sc_path).convert("RGB"))
        sc_sim = sc_orig.copy()
        crop_h = 634
        crop_w = int(round(crop_h * (990.0 / 325.0)))  # 1931 px
        cx0, cx1 = cx - crop_w // 2, cx - crop_w // 2 + crop_w
        cy0, cy1 = cy - crop_h // 2, cy - crop_h // 2 + crop_h
        mob_slice = cv2.resize(banner_4k_u8[cy0:cy1, cx0:cx1], (990, 325), interpolation=cv2.INTER_AREA)

        pmask = Image.new("L", (990, 325), 0)
        ImageDraw.Draw(pmask).rounded_rectangle([0, 0, 989, 324], radius=38, fill=255)
        pm = (np.array(pmask, dtype=np.float32) / 255.0)[:, :, None]
        bg_yt = np.array([[[15, 15, 15]]], dtype=np.float32)
        comp_pill = (mob_slice.astype(np.float32) * pm + bg_yt * (1.0 - pm)).astype(np.uint8)
        sc_sim[135:135 + 325, 45:45 + 990] = comp_pill
        Image.fromarray(sc_sim).save("/tmp/banner_qa/android_simulated.jpg", quality=95)

        # Also save a workspace preview image showing Before vs After on Android + Desktop Strip!
        before_after = np.vstack([
            sc_orig,
            np.full((12, sc_orig.shape[1], 3), 38, dtype=np.uint8),
            sc_sim,
        ])
        Image.fromarray(before_after).save("/tmp/banner_qa/before_vs_after_android.jpg", quality=95)

    desk_strip = cv2.resize(banner_4k_u8[cy - 317:cy + 317, :], (1920, 317), interpolation=cv2.INTER_AREA)
    Image.fromarray(desk_strip).save("/tmp/banner_qa/desktop_strip.jpg", quality=95)

    tv_preview = cv2.resize(banner_4k_u8, (1920, 1080), interpolation=cv2.INTER_AREA)
    Image.fromarray(tv_preview).save("/tmp/banner_qa/tv_full_16x9.jpg", quality=95)


if __name__ == "__main__":
    build_banner()
