"""Pottsfield Studio — Radiant 4K Studio Manifesto Cards Generator.

Generates three native 4K Lossless PNG editions in the official Pottsfield ACES HDR identity:
  1. pottsfield-manifesto-highlight-9x16.png (2160 x 3840) — Instagram / TikTok Story Highlight & Pinned Vertical Slide
  2. pottsfield-manifesto-pinned-4x5.png     (2160 x 2700) — Instagram / X / Facebook Pinned Profile Grid Post
  3. pottsfield-manifesto-community-1x1.png  (2160 x 2160) — YouTube Channel Community Tab Pinned Post
"""
import math
import os
import sys
import numpy as np
import cv2
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from engine import srgb_to_linear, linear_to_srgb_u8, aces_tonemap, clamp, smoothstep
from prepare_assets import HERO_IN_LOGO_SCALE, HERO_IN_LOGO_OX, HERO_IN_LOGO_OY
from build_youtube_banner import sdf_upscale_rgba, paste_hdr, draw_maple_leaf
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


def build_radiant_crest_hdr(d: dict, target_px: int) -> tuple:
    """
    Reconstructs the official Pottsfield Studio Crest at `target_px` using SDF vector-sharp edges,
    preserving the rich deep pumpkin-orange saturation and menacing black carved eyes 100% as-is,
    with a zero-padded radial halo margin so there is never a rectangular crop edge!
    """
    logo_srgb = d["logo_clean"]
    logo_lin = srgb_to_linear(logo_srgb)
    ink_mask = (logo_srgb.max(axis=2) > 20).astype(np.uint8) * 255

    M_h2l = np.float32([
        [HERO_IN_LOGO_SCALE, 0.0, HERO_IN_LOGO_OX],
        [0.0, HERO_IN_LOGO_SCALE, HERO_IN_LOGO_OY],
    ])
    sil_logo = cv2.warpAffine(d["hero_sil"], M_h2l, (1254, 1254), flags=cv2.INTER_LINEAR).astype(np.float32) / 255.0
    cav_logo = cv2.warpAffine(d["hero_cav"], M_h2l, (1254, 1254), flags=cv2.INTER_LINEAR).astype(np.float32) / 255.0
    bev_logo = cv2.warpAffine(d["hero_bevel"], M_h2l, (1254, 1254), flags=cv2.INTER_LINEAR).astype(np.float32) / 255.0

    n_raw = d["hero_normals"].astype(np.float32) / 255.0 * 2.0 - 1.0
    n_len = np.sqrt(np.sum(n_raw * n_raw, axis=2, keepdims=True) + 1e-8)
    n_unit = n_raw / n_len
    nrm_logo = cv2.warpAffine(n_unit, M_h2l, (1254, 1254), flags=cv2.INTER_LINEAR, borderValue=(0.0, 0.0, 1.0))

    word_occ = np.clip((d["w_potts"].astype(np.float32) + d["w_studio"].astype(np.float32)) / 180.0, 0.0, 1.0)
    shell = sil_logo * (1.0 - cav_logo) * (1.0 - word_occ * 0.88)

    rim = np.power(np.clip(1.0 - nrm_logo[:, :, 2], 0.0, 1.0), 2.1) * shell
    full_mask_u8 = np.clip(np.maximum(ink_mask, (sil_logo * 255.0).astype(np.uint8)), 0, 255)

    # Preserve rich fiery pumpkin-orange saturation (#F4730A) without washing out to pale peach!
    src_hdr = logo_lin * 1.04
    src_hdr += rim[:, :, None] * (LIN_ORANGE * 0.55 + LIN_GOLD * 0.30)[None, None, :]
    src_hdr += (bev_logo * shell)[:, :, None] * (LIN_ORANGE * 0.42 + LIN_GOLD * 0.28)[None, None, :]

    # Boost crimson STUDIO & wreath vibrancy against velvet black
    is_crim = ((logo_srgb[:, :, 0] > 70) & (logo_srgb[:, :, 1] < 48)).astype(np.float32)
    src_hdr += src_hdr * (0.42 * is_crim[:, :, None])

    ys, xs = np.where(full_mask_u8 > 20)
    y0, y1 = max(0, int(ys.min()) - 14), min(1254, int(ys.max()) + 14)
    x0, x1 = max(0, int(xs.min()) - 14), min(1254, int(xs.max()) + 14)

    crop_h, crop_w = y1 - y0, x1 - x0
    sc = target_px / float(max(crop_h, crop_w))
    rgb_2x, a_2x, bev_2x = sdf_upscale_rgba(src_hdr[y0:y1, x0:x1], full_mask_u8[y0:y1, x0:x1], scale=sc * 1.6)
    tw, th = int(round(crop_w * sc)), int(round(crop_h * sc))
    rgb_out = cv2.resize(rgb_2x, (tw, th), interpolation=cv2.INTER_AREA)
    a_out = cv2.resize(a_2x, (tw, th), interpolation=cv2.INTER_AREA)
    bev_out = cv2.resize(bev_2x, (tw, th), interpolation=cv2.INTER_AREA)
    rgb_out += np.maximum(bev_out, 0.0)[:, :, None] * (LIN_GOLD * 0.16)[None, None, :]

    # Zero-pad by 72px on all sides so any blur/shadow fades 100% smoothly with ZERO rectangular edge!
    pad = 72
    rgb_pad = np.zeros((th + 2 * pad, tw + 2 * pad, 3), dtype=np.float32)
    a_pad = np.zeros((th + 2 * pad, tw + 2 * pad), dtype=np.float32)
    rgb_pad[pad:pad + th, pad:pad + tw] = rgb_out
    a_pad[pad:pad + th, pad:pad + tw] = a_out
    return rgb_pad, a_pad


def render_rich_line_hdr(segments: list, tracking_px: int = 0,
                         glow_col: np.ndarray = LIN_ORANGE, glow_str: float = 0.38,
                         with_stars: bool = False) -> tuple:
    """
    Renders a single line of multi-styled, multi-colored 2x-supersampled HDR text.
    Each segment in `segments`: (text_str, font_path, size_px, weight, col_top_lin, col_bot_lin)
    """
    ss = 2
    trk = tracking_px * ss
    loaded = []
    max_sz = 0
    for txt, fp, sz, wt, c_top, c_bot in segments:
        fnt = load_font(fp, sz * ss, wt)
        advs = [fnt.getlength(c) for c in txt]
        loaded.append((txt, fnt, advs, sz, c_top, c_bot))
        max_sz = max(max_sz, sz)

    total_chars = sum(len(t[0]) for t in loaded)
    tw2 = sum(sum(t[2]) for t in loaded) + trk * max(total_chars - 1, 0)
    pad_x2 = int((max_sz * 2.5 + 48) * ss)
    pad_y2 = int((max_sz * 0.80 + 28) * ss)
    W2 = int(math.ceil(tw2 + 2 * pad_x2))
    H2 = int(math.ceil(max_sz * 1.54 * ss + 2 * pad_y2))
    W2 += W2 % 2
    H2 += H2 % 2

    ref_font = loaded[0][1]
    ref_asc, _ = ref_font.getmetrics()
    base_y2 = pad_y2 + ref_asc

    W1, H1 = W2 // ss, H2 // ss
    grain = make_woodcut_grain(H1, W1, seed=max_sz * 13 + total_chars)
    premult_rgb = np.zeros((H1, W1, 3), dtype=np.float32)
    union_m = np.zeros((H1, W1), dtype=np.float32)

    x_cur = (W2 - tw2) * 0.5
    x_start = x_cur
    char_idx = 0

    for txt, fnt, advs, sz, c_top, c_bot in loaded:
        asc, _ = fnt.getmetrics()
        y_draw = base_y2 - asc
        seg_img = Image.new("L", (W2, H2), 0)
        sdrw = ImageDraw.Draw(seg_img)
        for ch, adv in zip(txt, advs):
            sdrw.text((x_cur, y_draw), ch, fill=255, font=fnt)
            x_cur += adv + (trk if char_idx < total_chars - 1 else 0)
            char_idx += 1

        sm = cv2.resize(np.array(seg_img, dtype=np.float32) / 255.0, (W1, H1), interpolation=cv2.INTER_AREA)
        ys = np.where(sm.max(axis=1) > 0.05)[0]
        if len(ys):
            y0_g, y1_g = int(ys.min()), int(ys.max())
            ly = np.clip((np.arange(H1, dtype=np.float32)[:, None] - y0_g) / max(y1_g - y0_g, 1), 0.0, 1.0)
            s_rgb = (c_top[None, None, :] * (1.0 - ly[:, :, None]) + c_bot[None, None, :] * ly[:, :, None]) * grain[:, :, None]
            premult_rgb += s_rgb * sm[:, :, None]
            union_m = np.clip(union_m + sm, 0.0, 1.0)

    x_end = x_cur

    if with_stars:
        st_img = Image.new("L", (W2, H2), 0)
        sdrw = ImageDraw.Draw(st_img)
        cy_s = base_y2 - ref_asc * 0.36
        sr = max(int(max_sz * 0.38 * ss), 12)
        for sx_s in (x_start - sr * 3.1, x_end + sr * 3.1):
            pts = [
                (sx_s, cy_s - sr), (sx_s + sr * 0.26, cy_s - sr * 0.26),
                (sx_s + sr, cy_s), (sx_s + sr * 0.26, cy_s + sr * 0.26),
                (sx_s, cy_s + sr), (sx_s - sr * 0.26, cy_s + sr * 0.26),
                (sx_s - sr, cy_s), (sx_s - sr * 0.26, cy_s - sr * 0.26),
            ]
            sdrw.polygon(pts, fill=255)
        stm = cv2.resize(np.array(st_img, dtype=np.float32) / 255.0, (W1, H1), interpolation=cv2.INTER_AREA)
        premult_rgb += (LIN_GOLD * 1.50)[None, None, :] * stm[:, :, None]
        union_m = np.clip(union_m + stm, 0.0, 1.0)

    halo = cv2.GaussianBlur(union_m, (0, 0), sigmaX=10.5, sigmaY=10.5)
    alpha = np.clip(union_m + halo * 0.28 * glow_str, 0.0, 1.0)
    premult_total = premult_rgb + glow_col[None, None, :] * (halo * glow_str)[:, :, None]
    straight = premult_total / np.maximum(alpha[:, :, None], 1e-4)
    return straight.astype(np.float32), alpha.astype(np.float32)


def draw_4pt_star(hdr: np.ndarray, cx: float, cy: float, r_long: float, r_short: float, col_hdr: np.ndarray):
    """Draws an anti-aliased glowing 4-point star at (cx, cy) onto linear HDR canvas."""
    H, W, _ = hdr.shape
    pad = int(r_long * 2.4) + 8
    x0, y0 = max(0, int(cx) - pad), max(0, int(cy) - pad)
    x1, y1 = min(W, int(cx) + pad), min(H, int(cy) + pad)
    if x1 <= x0 or y1 <= y0:
        return
    ss = 2
    sw, sh = (x1 - x0) * ss, (y1 - y0) * ss
    img = Image.new("L", (sw, sh), 0)
    drw = ImageDraw.Draw(img)
    lx, ly = (cx - x0) * ss, (cy - y0) * ss
    rl, rs = r_long * ss, r_short * ss
    pts = [
        (lx, ly - rl), (lx + rs, ly - rs),
        (lx + rl, ly), (lx + rs, ly + rs),
        (lx, ly + rl), (lx - rs, ly + rs),
        (lx - rl, ly), (lx - rs, ly - rs),
    ]
    drw.polygon(pts, fill=255)
    m = cv2.resize(np.array(img, dtype=np.float32) / 255.0, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
    halo = cv2.GaussianBlur(m, (0, 0), sigmaX=7.5, sigmaY=7.5)
    roi = hdr[y0:y1, x0:x1]
    roi[:] = roi * (1.0 - m[:, :, None] * 0.85) + col_hdr[None, None, :] * m[:, :, None] + (col_hdr * 0.48)[None, None, :] * halo[:, :, None]


def draw_ornate_divider(hdr: np.ndarray, cx: int, cy: int, half_w: int, col_line: np.ndarray, star_r: float = 11.0):
    """Draws a tapering woodcut horizontal rule with a central 4-point golden star and side diamonds."""
    for dx in range(-half_w, half_w + 1):
        adx = abs(dx)
        if adx < int(star_r * 1.9):
            continue
        t = 1.0 - adx / float(half_w)
        hdr[cy - 1:cy + 2, cx + dx] += (col_line * (t ** 1.3))[None, :]
    draw_4pt_star(hdr, cx, cy, r_long=star_r, r_short=star_r * 0.25, col_hdr=LIN_GOLD * 1.65)
    for sgn in (-1, 1):
        draw_4pt_star(hdr, cx + sgn * int(half_w * 0.55), cy, r_long=star_r * 0.48, r_short=star_r * 0.16, col_hdr=LIN_ORANGE * 1.30)


def draw_manifesto_world_and_frame(hdr: np.ndarray, fx0: int, fy0: int, fx1: int, fy1: int):
    """
    Paints the radiant dark-autumn background, illuminated chamfered Gothic woodcut frame [fx0..fx1, fy0..fy1],
    and FOREGROUND overhanging oak lantern boughs + crescent moon in the outer sky/corners so lanterns
    blaze at 100% golden HDR radiance without ever being dimmed by the frame backing!
    """
    H, W, _ = hdr.shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

    # 1. Deep Obsidian Velvet Base + Radiant Corner Lantern Pools
    corner_glow = (
        0.075 * np.exp(-(((xx - W * 0.10) / (W * 0.26)) ** 2 + ((yy - H * 0.10) / (H * 0.18)) ** 2))
        + 0.075 * np.exp(-(((xx - W * 0.90) / (W * 0.26)) ** 2 + ((yy - H * 0.10) / (H * 0.18)) ** 2))
        + 0.065 * np.exp(-(((xx - W * 0.10) / (W * 0.25)) ** 2 + ((yy - H * 0.91) / (H * 0.17)) ** 2))
        + 0.065 * np.exp(-(((xx - W * 0.90) / (W * 0.25)) ** 2 + ((yy - H * 0.91) / (H * 0.17)) ** 2))
    )
    hdr[:] += corner_glow[:, :, None] * (LIN_ORANGE * 0.92 + LIN_CRIMSON * 0.36)[None, None, :]

    # 2. Crescent Harvest Moon in Upper Sky (cleanly placed in open sky clear of corner branches!)
    if fy0 >= 220:
        mx, my, mr = W * 0.78, fy0 * 0.46, 78.0
    else:
        mx, my, mr = W * 0.79, fy0 * 0.50, min(fy0 * 0.34, 52.0)
    r_out = np.sqrt((xx - mx) ** 2 + (yy - my) ** 2) - mr
    r_in = np.sqrt((xx - (mx + mr * 0.36)) ** 2 + (yy - (my - mr * 0.16)) ** 2) - (mr * 0.89)
    cres_sdf = np.maximum(r_out, -r_in)
    cres_fill = clamp(1.0 - smoothstep(-1.5, 1.5, cres_sdf))
    cres_halo = cv2.GaussianBlur(cres_fill, (0, 0), sigmaX=22.0, sigmaY=22.0)
    hdr[:] += cres_fill[:, :, None] * (LIN_GOLD * 0.88 + LIN_ORANGE * 0.30)[None, None, :] + cres_halo[:, :, None] * (LIN_ORANGE * 0.40)[None, None, :]

    # 3. Illuminated Obsidian-Velvet Chamfered Gothic Frame (drawn BEFORE foreground corner lanterns!)
    grain = make_woodcut_grain(H, W, seed=707)
    chamfer = 48
    outer_pts = [
        (fx0 + chamfer, fy0), (fx1 - chamfer, fy0),
        (fx1, fy0 + chamfer), (fx1, fy1 - chamfer),
        (fx1 - chamfer, fy1), (fx0 + chamfer, fy1),
        (fx0, fy1 - chamfer), (fx0, fy0 + chamfer),
    ]
    pad_in = 18
    ic = chamfer - 6
    inner_pts = [
        (fx0 + pad_in + ic, fy0 + pad_in), (fx1 - pad_in - ic, fy0 + pad_in),
        (fx1 - pad_in, fy0 + pad_in + ic), (fx1 - pad_in, fy1 - pad_in - ic),
        (fx1 - pad_in - ic, fy1 - pad_in), (fx0 + pad_in + ic, fy1 - pad_in),
        (fx0 + pad_in, fy1 - pad_in - ic), (fx0 + pad_in, fy0 + pad_in + ic),
    ]

    f_fill = Image.new("L", (W, H), 0)
    ImageDraw.Draw(f_fill).polygon(outer_pts, fill=255)
    fm = np.array(f_fill, dtype=np.float32) / 255.0

    # Deepen interior to pure velvet obsidian (#030100) for maximum OLED radiance!
    hdr[:] = hdr * (1.0 - fm[:, :, None] * 0.90) + np.array([0.0024, 0.0007, 0.0004], dtype=np.float32)[None, None, :] * fm[:, :, None]

    # Subtle radial ember warmth behind the crest & glory headline (smoothly decaying well inside frame!)
    inner_aura = (
        0.055 * np.exp(-(((xx - W * 0.5) / (W * 0.30)) ** 2 + ((yy - (fy0 + (fy1 - fy0) * 0.19)) / ((fy1 - fy0) * 0.13)) ** 2))
        + 0.042 * np.exp(-(((xx - W * 0.5) / (W * 0.34)) ** 2 + ((yy - (fy0 + (fy1 - fy0) * 0.55)) / ((fy1 - fy0) * 0.12)) ** 2))
    ) * fm
    hdr[:] += inner_aura[:, :, None] * (LIN_ORANGE * 0.88 + LIN_CRIMSON * 0.36)[None, None, :]

    b_outer = Image.new("L", (W, H), 0)
    b_inner = Image.new("L", (W, H), 0)
    ImageDraw.Draw(b_outer).polygon(outer_pts, outline=255, width=6)
    ImageDraw.Draw(b_inner).polygon(inner_pts, outline=255, width=2)
    bo = np.array(b_outer, dtype=np.float32) / 255.0
    bi = np.array(b_inner, dtype=np.float32) / 255.0
    bo_glow = cv2.GaussianBlur(bo, (0, 0), sigmaX=13.0, sigmaY=13.0)

    hdr[:] += (
        (bo * grain)[:, :, None] * (LIN_ORANGE * 1.32 + LIN_GOLD * 0.58)[None, None, :]
        + bo_glow[:, :, None] * (LIN_ORANGE * 0.52)[None, None, :]
        + (bi * grain)[:, :, None] * (LIN_CRIMSON * 1.12 + LIN_GOLD * 0.30)[None, None, :]
    )

    for sx, sy in [
        (fx0 + chamfer * 0.5, fy0 + chamfer * 0.5),
        (fx1 - chamfer * 0.5, fy0 + chamfer * 0.5),
        (fx1 - chamfer * 0.5, fy1 - chamfer * 0.5),
        (fx0 + chamfer * 0.5, fy1 - chamfer * 0.5),
    ]:
        draw_4pt_star(hdr, sx, sy, r_long=16.0, r_short=4.2, col_hdr=LIN_GOLD * 1.75)
    draw_4pt_star(hdr, W * 0.5, fy0, r_long=21.0, r_short=5.2, col_hdr=LIN_GOLD * 1.90)
    draw_4pt_star(hdr, W * 0.5, fy1, r_long=19.0, r_short=4.8, col_hdr=LIN_GOLD * 1.80)

    # 4. FOREGROUND Corner Oak Boughs & Glowing Hanging Lanterns (strictly in outer sky/side margins!)
    sil = Image.new("L", (W, H), 0)
    edg = Image.new("L", (W, H), 0)
    lan = Image.new("L", (W, H), 0)
    ds, de, dl = ImageDraw.Draw(sil), ImageDraw.Draw(edg), ImageDraw.Draw(lan)

    rng = np.random.default_rng(202699 + H)
    # Place boughs so lanterns hang in the left/right outer columns (X ~ 85 and X ~ W-85) cleanly outside fx0..fx1!
    reach_top = max(int(fx0 * 0.92), 145)
    reach_bot = max(int(fx0 * 0.88), 135)
    top_y = max(int(fy0 * 0.28), 32)
    bot_y = min(int(fy1 + (H - fy1) * 0.35), H - 82)

    for side_x, dir_x in [(0, 1), (W, -1)]:
        for anchor_y, reach_x, drop_y in [
            (top_y, reach_top,  28),
            (bot_y, reach_bot, -24),
        ]:
            bl, br = [], []
            for s in range(12):
                u = s / 11.0
                cx_b = side_x + dir_x * u * reach_x
                cy_b = anchor_y + u * drop_y - math.sin(u * math.pi) * 24.0
                bw = 15.0 * (1.0 - 0.72 * u)
                bl.append((cx_b, cy_b - bw))
                br.append((cx_b, cy_b + bw))
            ds.polygon(bl + br[::-1], fill=255)
            de.line(bl, fill=220, width=3)
            de.line(br, fill=175, width=2)
            tx_b, ty_b = bl[-1]
            for _ in range(4):
                draw_maple_leaf(ds, de, tx_b + float(rng.uniform(-20, 20)), ty_b + float(rng.uniform(-18, 18)),
                                sz=14.5, angle=float(rng.uniform(0, 6.28)))

            hi = 6
            ax_l, ay_l = int(br[hi][0]), int(br[hi][1])
            lx, ly = ax_l, min(ay_l + 56, H - 34)
            de.line([(ax_l, ay_l), (lx, ly - 22)], fill=230, width=3)
            cap = [(lx - 20, ly - 15), (lx, ly - 29), (lx + 20, ly - 15)]
            ds.polygon(cap, fill=255)
            de.polygon(cap, outline=245)
            ds.rounded_rectangle([lx - 16, ly - 15, lx + 16, ly + 20], radius=7, fill=255)
            de.rounded_rectangle([lx - 16, ly - 15, lx + 16, ly + 20], radius=7, outline=250, width=3)
            dl.ellipse([lx - 11, ly - 10, lx + 11, ly + 15], fill=255)

    m_sil = np.array(sil, dtype=np.float32) / 255.0
    m_edg = np.array(edg, dtype=np.float32) / 255.0
    m_lan = np.array(lan, dtype=np.float32) / 255.0
    hdr[:] = hdr * (1.0 - m_sil[:, :, None] * 0.95) + np.array([0.003, 0.001, 0.0008], dtype=np.float32)[None, None, :] * m_sil[:, :, None]
    hdr[:] += (m_edg * grain * 0.68)[:, :, None] * (LIN_ORANGE * 0.95 + LIN_GOLD * 0.30)[None, None, :]
    l_tight = cv2.GaussianBlur(m_lan, (0, 0), sigmaX=19.0, sigmaY=19.0)
    l_wide = cv2.resize(cv2.GaussianBlur(cv2.resize(m_lan, (W // 4, H // 4), interpolation=cv2.INTER_AREA), (0, 0), sigmaX=20.0), (W, H))
    hdr[:] += m_lan[:, :, None] * (LIN_IVORY * 2.1)[None, None, :] + l_tight[:, :, None] * (LIN_GOLD * 1.55)[None, None, :] + l_wide[:, :, None] * (LIN_ORANGE * 1.30)[None, None, :]

    # 5. Floating Golden & Crimson Embers along outer margins
    rng_e = np.random.default_rng(202655 + H)
    for _ in range(115):
        px = float(rng_e.uniform(22, W - 22))
        py = float(rng_e.uniform(22, H - 22))
        if (fx0 + 48) < px < (fx1 - 48) and (fy0 + 48) < py < (fy1 - 48):
            continue
        rad = float(rng_e.uniform(3.5, 13.0))
        rb = int(rad * 3.6)
        x0, y0 = max(0, int(px) - rb), max(0, int(py) - rb)
        x1, y1 = min(W, int(px) + rb + 1), min(H, int(py) + rb + 1)
        gx, gy = xx[y0:y1, x0:x1] - px, yy[y0:y1, x0:x1] - py
        r2 = gx * gx + gy * gy
        orb = np.exp(-r2 / (2.0 * (rad * 0.55) ** 2)) * ((1.0 - np.clip(r2 / float(rb * rb), 0.0, 1.0)) ** 2)
        col = LIN_GOLD * float(rng_e.uniform(0.28, 0.68)) if rng_e.random() > 0.35 else LIN_CRIMSON * 0.58
        hdr[y0:y1, x0:x1] += orb[:, :, None] * col[None, None, :]


def draw_pledge_plaque(hdr: np.ndarray, cx: int, cy: int, pw: int, ph: int):
    """Draws a radiant crimson-and-gold rimmed obsidian callout plaque behind the Anti-Brainrot pledge."""
    H, W, _ = hdr.shape
    x0, y0 = cx - pw // 2, cy - ph // 2
    x1, y1 = cx + pw // 2, cy + ph // 2
    ch = 26
    pts = [
        (x0 + ch, y0), (x1 - ch, y0), (x1, y0 + ch), (x1, y1 - ch),
        (x1 - ch, y1), (x0 + ch, y1), (x0, y1 - ch), (x0, y0 + ch),
    ]
    fill_i = Image.new("L", (W, H), 0)
    rim_i = Image.new("L", (W, H), 0)
    ImageDraw.Draw(fill_i).polygon(pts, fill=255)
    ImageDraw.Draw(rim_i).polygon(pts, outline=255, width=4)

    fm = np.array(fill_i, dtype=np.float32) / 255.0
    rm = np.array(rim_i, dtype=np.float32) / 255.0
    rg = cv2.GaussianBlur(rm, (0, 0), sigmaX=14.0, sigmaY=14.0)

    hdr[:] = hdr * (1.0 - fm[:, :, None] * 0.68) + (LIN_CRIMSON * 0.105 + LIN_ORANGE * 0.040)[None, None, :] * fm[:, :, None]
    hdr[:] += rm[:, :, None] * (LIN_ORANGE * 1.32 + LIN_CRIMSON * 0.58)[None, None, :] + rg[:, :, None] * (LIN_CRIMSON * 0.52 + LIN_ORANGE * 0.34)[None, None, :]
    draw_4pt_star(hdr, x0, cy, r_long=14.0, r_short=3.6, col_hdr=LIN_GOLD * 1.70)
    draw_4pt_star(hdr, x1, cy, r_long=14.0, r_short=3.6, col_hdr=LIN_GOLD * 1.70)


def render_card_edition(d: dict, W: int, H: int, fx0: int, fy0: int, fx1: int, fy1: int,
                        sc: float, crest_px: int, layout_y: dict, out_path: str):
    """Renders one complete 4K radiant manifesto card edition and saves as Lossless PNG."""
    cx = W // 2
    hdr = np.zeros((H, W, 3), dtype=np.float32)
    draw_manifesto_world_and_frame(hdr, fx0, fy0, fx1, fy1)

    c_ivory_hi = LIN_IVORY * 1.15
    c_ivory_lo = srgb_to_linear(np.array([[[246, 226, 200]]], dtype=np.uint8))[0, 0]
    c_gold_hi = LIN_GOLD * 1.55
    c_gold_lo = LIN_ORANGE * 1.20
    c_flame_hi = LIN_GOLD * 1.38 + LIN_ORANGE * 0.52
    c_flame_lo = LIN_ORANGE * 1.48 + LIN_CRIMSON * 0.26
    c_crim_hi = srgb_to_linear(np.array([[[252, 112, 82]]], dtype=np.uint8))[0, 0] * 1.28

    # 1. Top Overline: ✦ A LUMROOK STUDIO ✦
    ov_rgb, ov_a = render_rich_line_hdr(
        [("A   L U M R O O K   S T U D I O", MONTSERRAT_PATH, int(round(24 * sc)), 700, c_crim_hi, LIN_CRIMSON * 1.28)],
        tracking_px=int(round(5 * sc)), glow_col=LIN_CRIMSON, glow_str=0.44, with_stars=True
    )
    paste_hdr(hdr, ov_rgb, ov_a, cx - ov_a.shape[1] // 2, layout_y["overline"] - ov_a.shape[0] // 2, 8.0, 0.88)

    # 2. Radiant Pottsfield Crest (zero-padded 72px so halo fades 100% smoothly without any box edge!)
    crest_rgb, crest_a = build_radiant_crest_hdr(d, target_px=crest_px)
    crest_cy = layout_y["crest_cy"]
    crest_glow = cv2.GaussianBlur(crest_a, (0, 0), sigmaX=22.0, sigmaY=22.0)
    gx0, gy0 = cx - crest_a.shape[1] // 2, crest_cy - crest_a.shape[0] // 2
    sx0, sy0 = max(0, -gx0), max(0, -gy0)
    dx0, dy0 = max(0, gx0), max(0, gy0)
    dx1, dy1 = min(W, gx0 + crest_a.shape[1]), min(H, gy0 + crest_a.shape[0])
    hdr[dy0:dy1, dx0:dx1] += (
        crest_glow[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0), None]
        * (LIN_ORANGE * 0.24 + LIN_CRIMSON * 0.10)[None, None, :]
    )
    paste_hdr(hdr, crest_rgb, crest_a, gx0, gy0, 18.0, 0.92)

    # 3. Manifesto Ribbon Title: ✦ OUR MISSION & VISION ✦
    mv_rgb, mv_a = render_rich_line_hdr(
        [("O U R   M I S S I O N   &   V I S I O N", CINZEL_PATH, int(round(34 * sc)), 800, c_gold_hi, c_gold_lo)],
        tracking_px=int(round(4 * sc)), glow_col=LIN_ORANGE, glow_str=0.55, with_stars=True
    )
    paste_hdr(hdr, mv_rgb, mv_a, cx - mv_a.shape[1] // 2, layout_y["title"] - mv_a.shape[0] // 2, 10.0, 0.90)

    # 4. Block 1 — Who We Are (+14% larger, bold key terms)
    sz_b1 = int(round(40 * sc))
    b1_lines = [
        [
            ("Pottsfield Studio ", MONTSERRAT_PATH, sz_b1, 800, c_gold_hi, c_flame_lo),
            ("is a ", MONTSERRAT_PATH, sz_b1, 500, c_ivory_hi, c_ivory_lo),
            ("2D & 3D", MONTSERRAT_PATH, sz_b1, 800, c_gold_hi, c_gold_lo),
        ],
        [
            ("game development studio — on ", MONTSERRAT_PATH, sz_b1, 500, c_ivory_hi, c_ivory_lo),
            ("Android", MONTSERRAT_PATH, sz_b1, 800, c_gold_hi, c_flame_lo),
            (" now,", MONTSERRAT_PATH, sz_b1, 500, c_ivory_hi, c_ivory_lo),
        ],
        [
            ("with more platforms to follow in the future.", MONTSERRAT_PATH, sz_b1, 500, c_ivory_hi, c_ivory_lo),
        ],
    ]
    for idx, segs in enumerate(b1_lines):
        lr, la = render_rich_line_hdr(segs, tracking_px=1, glow_col=LIN_ORANGE, glow_str=0.34)
        ly_c = layout_y["b1_top"] + idx * layout_y["b1_step"]
        paste_hdr(hdr, lr, la, cx - la.shape[1] // 2, ly_c - la.shape[0] // 2, 9.0, 0.88)

    draw_ornate_divider(hdr, cx, layout_y["div1"], half_w=int(round(480 * sc)), col_line=LIN_CRIMSON * 1.10, star_r=11.5 * sc)

    # 5. Block 2 — Purpose & Restoring the Glory of Gaming Worldwide
    lead_rgb, lead_a = render_rich_line_hdr(
        [("Our goal is to bring a distinct new breed of games", FELL_IT_PATH, int(round(49 * sc)), None, c_ivory_hi, c_ivory_lo)],
        tracking_px=1, glow_col=LIN_ORANGE, glow_str=0.38
    )
    paste_hdr(hdr, lead_rgb, lead_a, cx - lead_a.shape[1] // 2, layout_y["b2_lead"] - lead_a.shape[0] // 2, 10.0, 0.90)

    sz_glory = int(round(64 * sc))
    for idx, g_txt in enumerate(["TO RESTORE THE GLORY", "OF GAMING WORLDWIDE"]):
        gr, ga = render_rich_line_hdr(
            [(g_txt, CINZEL_PATH, sz_glory, 900, c_flame_hi, c_flame_lo)],
            tracking_px=int(round(3 * sc)), glow_col=LIN_ORANGE, glow_str=0.72
        )
        gy_c = layout_y["b2_hero"] + idx * layout_y["b2_step"]
        paste_hdr(hdr, gr, ga, cx - ga.shape[1] // 2, gy_c - ga.shape[0] // 2, 14.0, 0.92)

    # 6. Block 3 — Radiant Anti-Fake-Ads & Anti-Brainrot Pledge Plaque
    plaque_cy = layout_y["plaque_cy"]
    plaque_w = int(round(1610 * sc))
    plaque_h = int(round(224 * sc))
    draw_pledge_plaque(hdr, cx, plaque_cy, plaque_w, plaque_h)

    p1_rgb, p1_a = render_rich_line_hdr(
        [
            ("NO FAKE ADS", CINZEL_PATH, int(round(45 * sc)), 900, c_gold_hi, c_flame_lo),
            ("   ·   ", CINZEL_PATH, int(round(45 * sc)), 900, c_crim_hi, LIN_CRIMSON),
            ("NO “BRAINROT” GAMES", CINZEL_PATH, int(round(45 * sc)), 900, c_gold_hi, c_flame_lo),
        ],
        tracking_px=int(round(2 * sc)), glow_col=LIN_ORANGE, glow_str=0.62
    )
    paste_hdr(hdr, p1_rgb, p1_a, cx - p1_a.shape[1] // 2, plaque_cy - int(round(38 * sc)) - p1_a.shape[0] // 2, 10.0, 0.90)

    p2_rgb, p2_a = render_rich_line_hdr(
        [("PACKED WITH ANNOYING IN-GAME ADS!", MONTSERRAT_PATH, int(round(30 * sc)), 800, c_ivory_hi, c_crim_hi)],
        tracking_px=int(round(4 * sc)), glow_col=LIN_CRIMSON, glow_str=0.48
    )
    paste_hdr(hdr, p2_rgb, p2_a, cx - p2_a.shape[1] // 2, plaque_cy + int(round(44 * sc)) - p2_a.shape[0] // 2, 9.0, 0.90)

    # 7. Block 4 — Call to Action: Be Part of Our Journey / Evolving Global Gaming
    cta1_rgb, cta1_a = render_rich_line_hdr(
        [("BE PART OF OUR JOURNEY.", CINZEL_PATH, int(round(52 * sc)), 800, c_gold_hi, c_gold_lo)],
        tracking_px=int(round(3 * sc)), glow_col=LIN_ORANGE, glow_str=0.60
    )
    paste_hdr(hdr, cta1_rgb, cta1_a, cx - cta1_a.shape[1] // 2, layout_y["cta1"] - cta1_a.shape[0] // 2, 12.0, 0.90)

    cta2_rgb, cta2_a = render_rich_line_hdr(
        [("BE PART OF EVOLVING THE GLOBAL GAMING WORLD.", MONTSERRAT_PATH, int(round(29 * sc)), 700, c_ivory_hi, c_gold_lo)],
        tracking_px=int(round(3 * sc)), glow_col=LIN_ORANGE, glow_str=0.40
    )
    paste_hdr(hdr, cta2_rgb, cta2_a, cx - cta2_a.shape[1] // 2, layout_y["cta2"] - cta2_a.shape[0] // 2, 9.0, 0.88)

    draw_ornate_divider(hdr, cx, layout_y["div2"], half_w=int(round(420 * sc)), col_line=LIN_ORANGE * 1.0, star_r=10.5 * sc)

    # 8. Block 5 — Warm Studio Team Sign-off & Handle
    sig1_rgb, sig1_a = render_rich_line_hdr(
        [("With regards,", FELL_IT_PATH, int(round(45 * sc)), None, c_ivory_hi, c_ivory_lo)],
        tracking_px=1, glow_col=LIN_ORANGE, glow_str=0.34
    )
    paste_hdr(hdr, sig1_rgb, sig1_a, cx - sig1_a.shape[1] // 2, layout_y["sig1"] - sig1_a.shape[0] // 2, 9.0, 0.88)

    sig2_rgb, sig2_a = render_rich_line_hdr(
        [("THE POTTSFIELD TEAM", CINZEL_PATH, int(round(39 * sc)), 800, c_flame_hi, c_flame_lo)],
        tracking_px=int(round(5 * sc)), glow_col=LIN_ORANGE, glow_str=0.58, with_stars=True
    )
    paste_hdr(hdr, sig2_rgb, sig2_a, cx - sig2_a.shape[1] // 2, layout_y["sig2"] - sig2_a.shape[0] // 2, 10.0, 0.90)

    hnd_rgb, hnd_a = render_rich_line_hdr(
        [("@PottsfieldStudio", MONTSERRAT_PATH, int(round(24 * sc)), 700, c_gold_hi * 0.88, c_crim_hi * 0.88)],
        tracking_px=int(round(3 * sc)), glow_col=LIN_ORANGE, glow_str=0.30
    )
    paste_hdr(hdr, hnd_rgb, hnd_a, cx - hnd_a.shape[1] // 2, layout_y["handle"] - hnd_a.shape[0] // 2, 8.0, 0.85)

    # 9. Optical Multi-Radius HDR Bloom + ACES Filmic Tonemapping
    bright = np.maximum(hdr - 0.50, 0.0)
    bq = cv2.resize(bright, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    bloom = cv2.resize(
        cv2.GaussianBlur(bq, (0, 0), sigmaX=4.5) * 0.18 + cv2.GaussianBlur(bq, (0, 0), sigmaX=15.0) * 0.15,
        (W, H), interpolation=cv2.INTER_LINEAR
    )
    hdr += bloom

    srgb_u8 = linear_to_srgb_u8(aces_tonemap(hdr))
    Image.fromarray(srgb_u8).save(out_path, optimize=True)
    print(f"Saved {W}x{H} Lossless PNG: {out_path} ({os.path.getsize(out_path)/1e6:.2f} MB)")


def main():
    d = np.load(os.path.join(HERE, "work", "prepared_assets.npz"))

    # 1) 9:16 Story Highlight & TikTok Pinned Slide (2160 x 3840) — clears top/bottom Story UI bars!
    render_card_edition(
        d, W=2160, H=3840,
        fx0=145, fy0=285, fx1=2015, fy1=3515,
        sc=1.02, crest_px=775,
        layout_y={
            "overline":  395,
            "crest_cy":  875,
            "title":     1395,
            "b1_top":    1545,
            "b1_step":   72,
            "div1":      1805,
            "b2_lead":   1920,
            "b2_hero":   2050,
            "b2_step":   92,
            "plaque_cy": 2445,
            "cta1":      2760,
            "cta2":      2862,
            "div2":      3000,
            "sig1":      3120,
            "sig2":      3232,
            "handle":    3372,
        },
        out_path=os.path.join(HERE, "pottsfield-manifesto-highlight-9x16.png"),
    )

    # 2) 4:5 Pinned Profile Grid Post — Instagram / X / Facebook (2160 x 2700)
    render_card_edition(
        d, W=2160, H=2700,
        fx0=175, fy0=155, fx1=1985, fy1=2545,
        sc=0.90, crest_px=560,
        layout_y={
            "overline":  242,
            "crest_cy":  595,
            "title":     975,
            "b1_top":    1085,
            "b1_step":   58,
            "div1":      1292,
            "b2_lead":   1380,
            "b2_hero":   1478,
            "b2_step":   76,
            "plaque_cy": 1785,
            "cta1":      2018,
            "cta2":      2098,
            "div2":      2195,
            "sig1":      2282,
            "sig2":      2368,
            "handle":    2462,
        },
        out_path=os.path.join(HERE, "pottsfield-manifesto-pinned-4x5.png"),
    )

    # 3) 1:1 Square Community Post — YouTube Posts Tab (2160 x 2160)
    render_card_edition(
        d, W=2160, H=2160,
        fx0=185, fy0=135, fx1=1975, fy1=2025,
        sc=0.76, crest_px=430,
        layout_y={
            "overline":  202,
            "crest_cy":  472,
            "title":     762,
            "b1_top":    848,
            "b1_step":   48,
            "div1":      1018,
            "b2_lead":   1088,
            "b2_hero":   1166,
            "b2_step":   62,
            "plaque_cy": 1412,
            "cta1":      1595,
            "cta2":      1660,
            "div2":      1736,
            "sig1":      1805,
            "sig2":      1872,
            "handle":    1952,
        },
        out_path=os.path.join(HERE, "pottsfield-manifesto-community-1x1.png"),
    )


if __name__ == "__main__":
    main()
