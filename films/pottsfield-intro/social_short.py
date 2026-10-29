"""Viral 9:16 Social Launch Edition Renderer (YouTube Shorts, TikTok & Instagram Reels) for Pottsfield Studio."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import math
import os
import subprocess
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.environ.get("LIB", os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, LIB)
sys.path.insert(0, HERE)

import soundfile as sf
from core.audio import sfx
from core.audio import pluck as P
from timeline import FPS, TOTAL_FRAMES, DUR
from engine import PottsfieldEngine, srgb_to_linear, linear_to_srgb_u8, aces_tonemap, smoothstep, smootherstep, clamp

FONTS_DIR = os.path.join(HERE, "fonts")


def load_var_font(filename: str, size_px: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(os.path.join(FONTS_DIR, filename), size_px)
    if weight is not None:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


def draw_tracked_centered(draw: ImageDraw.ImageDraw, y: int, text: str, font: ImageFont.FreeTypeFont,
                          tracking: float, fill: tuple[int, int, int, int], canvas_w: int):
    """Render centered text with custom letter-spacing at 2x supersampled resolution."""
    advs = [draw.textlength(ch, font=font) for ch in text]
    total_w = sum(advs) + tracking * max(0, len(text) - 1)
    x = (canvas_w - total_w) * 0.5
    for ch, adv in zip(text, advs):
        draw.text((x, y), ch, font=font, fill=fill)
        x += adv + tracking


def draw_four_point_star(draw: ImageDraw.ImageDraw, cx: float, cy: float, r_outer: float, r_inner: float,
                         fill: tuple[int, int, int, int]):
    pts = []
    for k in range(8):
        ang = k * math.pi / 4.0 - math.pi / 2.0
        r = r_outer if k % 2 == 0 else r_inner
        pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
    draw.polygon(pts, fill=fill)


def build_card_plate(W: int, H: int, spec_fn) -> tuple[np.ndarray, np.ndarray]:
    """Render a 2x-supersampled RGBA typography plate -> (linear_rgb_float32, alpha_float32) at (H, W)."""
    ss = 2
    sw, sh = W * ss, H * ss
    img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    spec_fn(draw, sw, sh, ss)

    # Downsample cleanly with Lanczos
    img_1x = img.resize((W, H), resample=Image.Resampling.LANCZOS)
    rgba = np.array(img_1x, dtype=np.float32)
    alpha = rgba[:, :, 3] / 255.0
    # Un-premultiply safe sRGB -> linear
    rgb_srgb = rgba[:, :, :3] / 255.0
    rgb_lin = srgb_to_linear(rgb_srgb)

    # Add crisp dark ink drop-keep-shadow behind letters so readability is 100% over any ember/glow
    shadow = cv2.GaussianBlur(alpha, (0, 0), 3.8)
    shadow_shift = np.zeros_like(shadow)
    shadow_shift[3:, :] = shadow[:-3, :]
    total_alpha = np.clip(alpha + shadow_shift * 0.72 * (1.0 - alpha), 0.0, 1.0)
    rgb_out = rgb_lin * alpha[:, :, None]
    return rgb_out.astype(np.float32), total_alpha.astype(np.float32), alpha.astype(np.float32)


def apply_vertical_gradient(img_rgba: Image.Image, y0: int, y1: int,
                            col_top: tuple[int, int, int], col_bot: tuple[int, int, int]):
    """Tint non-transparent pixels within [y0:y1] with a rich vertical metallic/ember gradient."""
    arr = np.array(img_rgba, dtype=np.float32)
    sub = arr[y0:y1]
    a = sub[:, :, 3:4] / 255.0
    h = max(1, y1 - y0)
    t = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None, None]
    ct = np.array(col_top, dtype=np.float32)[None, None, :]
    cb = np.array(col_bot, dtype=np.float32)[None, None, :]
    grad = ct * (1.0 - t) + cb * t
    # Modulate existing luminance mask
    mask = (a > 0.01)
    sub[:, :, :3] = np.where(mask, grad, sub[:, :, :3])
    arr[y0:y1] = sub
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGBA")


class PottsfieldSocialEngine(PottsfieldEngine):
    """Extends PottsfieldEngine with custom 9:16 framing & pre-baked HDR woodcut/ember viral title plates."""

    def __init__(self, W: int = 1080, H: int = 1920):
        super().__init__()
        self.W = W
        self.H = H
        self._bake_typography_plates()

    def camera_state(self, t: float, W: int, H: int) -> dict:
        cam = super().camera_state(t, W, H)
        if H > W:
            # Shift visual stage slightly downward (+56 px) so Upper Hook Stage (y=220..525) & Lower CTA Stage (y=1450..1575)
            # sit in luxurious velvet-black negative space with zero overlap!
            cam["screen_cy"] += 56.0 * (H / 1920.0)
            cam["scale"] *= 0.955
        return cam

    def _bake_typography_plates(self):
        W, H = self.W, self.H

        # --- Plate 1A: Beat 1 Main Hook ("MOBILE GAMING / LOST ITS SOUL.") [0.03s .. 2.96s] ---
        def p1a(draw, sw, sh, ss):
            f_over = load_var_font("Montserrat[wght].ttf", 23 * ss, weight=650)
            f_h1 = load_var_font("Cinzel[wght].ttf", 58 * ss, weight=820)
            f_h2 = load_var_font("Cinzel[wght].ttf", 64 * ss, weight=880)

            # Crimson-amber pattern-interrupt overline + flanking stars (zero word repetition with headline!)
            draw_tracked_centered(draw, 240 * ss, "LET’S  BE  HONEST", f_over, 6.5 * ss, (218, 72, 56, 245), sw)
            draw_four_point_star(draw, (sw * 0.5) - 188 * ss, 254 * ss, 9 * ss, 2.8 * ss, (244, 115, 10, 255))
            draw_four_point_star(draw, (sw * 0.5) + 188 * ss, 254 * ss, 9 * ss, 2.8 * ss, (244, 115, 10, 255))

            draw_tracked_centered(draw, 286 * ss, "MOBILE GAMING", f_h1, 2.5 * ss, (250, 238, 218, 255), sw)
            draw_tracked_centered(draw, 358 * ss, "LOST ITS SOUL.", f_h2, 2.5 * ss, (255, 140, 24, 255), sw)

        ss = 2
        img1a = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
        p1a(ImageDraw.Draw(img1a), W * ss, H * ss, ss)
        img1a = apply_vertical_gradient(img1a, 282 * ss, 354 * ss, (254, 246, 232), (226, 198, 160))
        img1a = apply_vertical_gradient(img1a, 355 * ss, 438 * ss, (255, 182, 56), (242, 98, 8))
        self.p1a_rgb, self.p1a_sh_a, self.p1a_fg_a = self._finalize_rgba(img1a)

        # --- Plate 1B: Beat 1 Stamp Sub-line ("Endless brainrot. Fake ads. Zero story.") [1.00s .. 2.96s] ---
        img1b = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
        d1b = ImageDraw.Draw(img1b)
        f_it = ImageFont.truetype(os.path.join(FONTS_DIR, "IMFeENit28P.ttf"), 39 * ss)
        draw_tracked_centered(d1b, 444 * ss, "Endless brainrot. Fake ads. Zero story.", f_it, 0.5 * ss, (236, 212, 182, 250), W * ss)
        # Subtle thin crimson divider line above sub-line
        cx = (W * ss) // 2
        d1b.line([(cx - 190 * ss, 434 * ss), (cx + 190 * ss, 434 * ss)], fill=(185, 48, 42, 190), width=max(1, int(1.5 * ss)))
        self.p1b_rgb, self.p1b_sh_a, self.p1b_fg_a = self._finalize_rgba(img1b)

        # --- Plate 2: Beat 2 3D Ignition Turn ("WE'RE BRINGING IT BACK.") [3.00s .. 5.94s] ---
        img2 = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(img2)
        f2_h1 = load_var_font("Cinzel[wght].ttf", 55 * ss, weight=820)
        f2_h2 = load_var_font("Cinzel[wght].ttf", 66 * ss, weight=900)
        f2_sub = load_var_font("Montserrat[wght].ttf", 25 * ss, weight=700)
        f2_plat = load_var_font("Montserrat[wght].ttf", 22 * ss, weight=650)

        draw_tracked_centered(d2, 254 * ss, "WE’RE BRINGING", f2_h1, 2.5 * ss, (252, 242, 224, 255), W * ss)
        draw_tracked_centered(d2, 324 * ss, "IT BACK.", f2_h2, 3.5 * ss, (255, 138, 18, 255), W * ss)
        img2 = apply_vertical_gradient(img2, 250 * ss, 322 * ss, (255, 248, 236), (232, 206, 170))
        img2 = apply_vertical_gradient(img2, 322 * ss, 406 * ss, (255, 204, 78), (244, 102, 8))
        d2 = ImageDraw.Draw(img2)
        d2.line([(cx - 220 * ss, 414 * ss), (cx + 220 * ss, 414 * ss)], fill=(196, 54, 46, 210), width=max(1, int(1.5 * ss)))
        draw_tracked_centered(d2, 428 * ss, "DEEP 2D & 3D STORY ADVENTURES", f2_sub, 4.2 * ss, (248, 234, 212, 255), W * ss)
        draw_tracked_centered(d2, 468 * ss, "ANDROID FIRST  ·  WINDOWS PC NEXT", f2_plat, 4.8 * ss, (255, 140, 28, 250), W * ss)
        self.p2_rgb, self.p2_sh_a, self.p2_fg_a = self._finalize_rgba(img2)

        # --- Plate 3A: Beat 3 Upper Crest Header ("A LUMROOK STUDIO / Driven by Story. Lit by Soul.") [6.25s .. 9.72s] ---
        img3a = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
        d3a = ImageDraw.Draw(img3a)
        f3_over = load_var_font("Montserrat[wght].ttf", 23 * ss, weight=700)
        f3_motto = ImageFont.truetype(os.path.join(FONTS_DIR, "IMFeENit28P.ttf"), 50 * ss)
        draw_tracked_centered(d3a, 272 * ss, "A  LUMROOK  STUDIO", f3_over, 6.5 * ss, (216, 64, 56, 250), W * ss)
        draw_tracked_centered(d3a, 320 * ss, "“Driven by Story. Lit by Soul.”", f3_motto, 0.8 * ss, (255, 165, 52, 255), W * ss)
        img3a = apply_vertical_gradient(img3a, 316 * ss, 392 * ss, (255, 224, 148), (244, 118, 14))
        d3a = ImageDraw.Draw(img3a)
        draw_four_point_star(d3a, cx, 404 * ss, 10 * ss, 3.0 * ss, (244, 115, 10, 235))
        d3a.line([(cx - 140 * ss, 404 * ss), (cx - 22 * ss, 404 * ss)], fill=(185, 48, 42, 185), width=max(1, int(1.5 * ss)))
        d3a.line([(cx + 22 * ss, 404 * ss), (cx + 140 * ss, 404 * ss)], fill=(185, 48, 42, 185), width=max(1, int(1.5 * ss)))
        self.p3a_rgb, self.p3a_sh_a, self.p3a_fg_a = self._finalize_rgba(img3a)

        # --- Plate 3B: Beat 3 Lower Viral CTA ("FOLLOW FROM DAY 1 / ANDROID · WINDOWS") [6.80s .. 9.72s] ---
        img3b = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
        d3b = ImageDraw.Draw(img3b)
        f3_cta = load_var_font("Cinzel[wght].ttf", 38 * ss, weight=850)
        f3_pl = load_var_font("Montserrat[wght].ttf", 23 * ss, weight=700)
        draw_tracked_centered(d3b, 1468 * ss, "FOLLOW FROM DAY 1", f3_cta, 3.2 * ss, (254, 242, 222, 255), W * ss)
        draw_four_point_star(d3b, cx - 268 * ss, 1488 * ss, 10 * ss, 3.2 * ss, (255, 132, 18, 255))
        draw_four_point_star(d3b, cx + 268 * ss, 1488 * ss, 10 * ss, 3.2 * ss, (255, 132, 18, 255))
        draw_tracked_centered(d3b, 1524 * ss, "ANDROID   ·   WINDOWS PC", f3_pl, 5.5 * ss, (246, 122, 16, 255), W * ss)
        self.p3b_rgb, self.p3b_sh_a, self.p3b_fg_a = self._finalize_rgba(img3b)

        # Normalized X coordinate across screen [0..1] for horizontal ember-carve wipes
        xx = np.linspace(0.0, 1.0, W, dtype=np.float32)[None, :]
        self._x_norm = np.broadcast_to(xx, (H, W))
        self._x_rad = np.abs(self._x_norm - 0.5) * 2.0  # 0 at center -> 1 at edges

    def _finalize_rgba(self, img_2x: Image.Image) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        img_1x = img_2x.resize((self.W, self.H), resample=Image.Resampling.LANCZOS)
        rgba = np.array(img_1x, dtype=np.float32)
        fg_a = rgba[:, :, 3] / 255.0
        rgb_lin = srgb_to_linear(rgba[:, :, :3] / 255.0)
        shadow = cv2.GaussianBlur(fg_a, (0, 0), 4.2)
        sh_shift = np.zeros_like(shadow)
        sh_shift[3:, :] = shadow[:-3, :]
        tot_a = np.clip(fg_a + sh_shift * 0.78 * (1.0 - fg_a), 0.0, 1.0)
        return (rgb_lin * fg_a[:, :, None]).astype(np.float32), tot_a.astype(np.float32), fg_a.astype(np.float32)

    def _composite_plate(self, frame_hdr: np.ndarray, p_rgb: np.ndarray, p_tot_a: np.ndarray, p_fg_a: np.ndarray,
                         prog_in: float, fade_out: float, mode: str = "center", ember_boost: float = 1.0,
                         dy_px: int = 0):
        if prog_in <= 1e-3 or fade_out <= 1e-3:
            return frame_hdr

        coord = self._x_rad if mode == "center" else self._x_norm
        wipe = np.clip((prog_in * 1.22 - coord) / 0.18, 0.0, 1.0) * fade_out
        edge = np.exp(-((coord - prog_in * 1.12) / 0.075) ** 2) * (1.0 if prog_in < 0.98 else 0.0) * fade_out

        if dy_px != 0:
            M = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, float(dy_px)]], dtype=np.float32)
            p_rgb = cv2.warpAffine(p_rgb, M, (self.W, self.H), flags=cv2.INTER_LINEAR)
            p_tot_a = cv2.warpAffine(p_tot_a, M, (self.W, self.H), flags=cv2.INTER_LINEAR)
            p_fg_a = cv2.warpAffine(p_fg_a, M, (self.W, self.H), flags=cv2.INTER_LINEAR)

        a_eff = p_tot_a * wipe
        ember_hdr = (p_fg_a * edge)[:, :, None] * np.array([2.5, 1.05, 0.18], dtype=np.float32) * ember_boost
        # Soft warm bloom aura behind active letters
        glow = cv2.GaussianBlur(p_fg_a * wipe, (0, 0), 9.0) * 0.18 * ember_boost
        frame_hdr = frame_hdr + glow[:, :, None] * np.array([0.95, 0.28, 0.02], dtype=np.float32)
        frame_hdr = frame_hdr * (1.0 - a_eff[:, :, None]) + p_rgb * wipe[:, :, None] + ember_hdr
        return frame_hdr

    def render_frame(self, t: float, W: int = 1080, H: int = 1920) -> np.ndarray:
        assert W == self.W and H == self.H
        cam = self.camera_state(t, W, H)

        # Tighter viral Shorts loop fade: instant Frame-1 visibility (0.00->0.06s), crisp 0.26s loop kiss at end (9.70->9.97s)!
        boot_in = float(smoothstep(0.00, 0.05, t))
        boot_out = 1.0 - float(smootherstep(9.70, 9.97, t))
        master_fade = boot_in * boot_out
        if master_fade <= 1e-4:
            return np.zeros((H, W, 3), dtype=np.uint8)

        # Render full HDR visual scene using parent shaders + our shifted 9:16 camera!
        frame_hdr = np.zeros((H, W, 3), dtype=np.float32)

        if t >= 3.00:
            amb_str = (1.0 - 0.72 * float(smootherstep(5.5, 7.2, t))) * float(smoothstep(3.00, 3.25, t))
            if amb_str > 1e-3:
                lx, ly = self.world_to_screen(621.0, 900.0, cam)
                xx, yy = self._get_grid(W, H)
                rr = np.sqrt(((xx - lx) / (max(W, H) * 0.48)) ** 2 + ((yy - ly) / (max(W, H) * 0.48)) ** 2)
                glow_bg = np.exp(-(rr ** 1.7) * 2.1) * amb_str
                frame_hdr += glow_bg[:, :, None] * np.array([0.075, 0.020, 0.005], dtype=np.float32)

        bg_part = np.zeros_like(frame_hdr)
        fg_part = np.zeros_like(frame_hdr)
        self.render_3d_particles(bg_part, fg_part, t, cam)
        frame_hdr += bg_part

        hero_hdr, hero_alpha, hero_rays = self.shade_hero_pumpkin(t, cam)
        from prepare_assets import HERO_IN_LOGO_SCALE, HERO_IN_LOGO_OX, HERO_IN_LOGO_OY
        sc_hero = HERO_IN_LOGO_SCALE * cam["scale"]
        tx_hero = (HERO_IN_LOGO_OX - cam["cam_wx"]) * cam["scale"] + cam["screen_cx"]
        ty_hero = (HERO_IN_LOGO_OY - cam["cam_wy"]) * cam["scale"] + cam["screen_cy"]
        M_hero_screen = np.array([[sc_hero, 0.0, tx_hero], [0.0, sc_hero, ty_hero]], dtype=np.float32)
        interp_flag = cv2.INTER_AREA if sc_hero < 0.95 else cv2.INTER_LINEAR

        if t >= 5.96:
            crest_hdr, fg_leaf_over_hero = self.shade_crest_layers(t)
            M_world_screen = np.array([
                [cam["scale"], 0.0, -cam["cam_wx"] * cam["scale"] + cam["screen_cx"]],
                [0.0, cam["scale"], -cam["cam_wy"] * cam["scale"] + cam["screen_cy"]],
            ], dtype=np.float32)
            w_flag = cv2.INTER_AREA if cam["scale"] < 0.95 else cv2.INTER_LINEAR
            crest_scr = cv2.warpAffine(crest_hdr, M_world_screen, (W, H), flags=w_flag, borderMode=cv2.BORDER_CONSTANT)
            fg_leaf_scr = cv2.warpAffine(fg_leaf_over_hero, M_world_screen, (W, H), flags=w_flag, borderMode=cv2.BORDER_CONSTANT)
        else:
            crest_scr = None
            fg_leaf_scr = None

        hero_scr_hdr = cv2.warpAffine(hero_hdr, M_hero_screen, (W, H), flags=interp_flag, borderMode=cv2.BORDER_CONSTANT)
        hero_scr_a = cv2.warpAffine(hero_alpha, M_hero_screen, (W, H), flags=interp_flag, borderMode=cv2.BORDER_CONSTANT)
        rays_scr_src = cv2.warpAffine(hero_rays, M_hero_screen, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

        if crest_scr is not None:
            frame_hdr += crest_scr * (1.0 - hero_scr_a[:, :, None] * (1.0 - fg_leaf_scr[:, :, None]))
            hero_vis_a = hero_scr_a * (1.0 - fg_leaf_scr)
            frame_hdr = frame_hdr * (1.0 - hero_vis_a[:, :, None]) + hero_scr_hdr * hero_vis_a[:, :, None]
        else:
            frame_hdr = frame_hdr * (1.0 - hero_scr_a[:, :, None]) + hero_scr_hdr

        light_sx, light_sy = self.world_to_screen(621.0, 905.0, cam)
        frame_hdr += self.volumetric_god_rays(rays_scr_src, light_sx, light_sy, t) * 0.88

        bright = np.maximum(frame_hdr - 0.55, 0.0)
        b_small = cv2.GaussianBlur(bright, (0, 0), sigmaX=min(W, H) * 0.012)
        b_wide = cv2.GaussianBlur(cv2.resize(bright, (W // 4, H // 4), interpolation=cv2.INTER_AREA), (0, 0), sigmaX=7.5)
        b_wide = cv2.resize(b_wide, (W, H), interpolation=cv2.INTER_LINEAR)
        bloom_amt = 0.28 if t < 6.5 else 0.14
        frame_hdr += b_small * bloom_amt + b_wide * (bloom_amt * 0.85)
        frame_hdr += fg_part

        # =====================================================================
        # Viral HDR Typography Overlay (3-Beat Narrative Arc)
        # =====================================================================
        frame_idx = int(round(t * FPS))

        # BEAT 1 (0.02s .. 2.98s): Instant Frame-1 Hook!
        if t < 3.02:
            p_in = float(smootherstep(0.01, 0.30, t))
            f_out = 1.0 - float(smoothstep(2.88, 3.00, t))
            # Match 2-frame woodblock print registration jolt at t=1.00s!
            dy1 = -3 if frame_idx == 30 else (1 if frame_idx == 31 else 0)
            frame_hdr = self._composite_plate(frame_hdr, self.p1a_rgb, self.p1a_sh_a, self.p1a_fg_a,
                                              p_in, f_out, mode="center", ember_boost=0.85, dy_px=dy1)
            if t >= 1.00:
                p_sub = float(smootherstep(1.00, 1.22, t))
                frame_hdr = self._composite_plate(frame_hdr, self.p1b_rgb, self.p1b_sh_a, self.p1b_fg_a,
                                                  p_sub, f_out, mode="center", ember_boost=0.70, dy_px=dy1)

        # BEAT 2 (3.00s .. 5.98s): Blazes in on the 3.00s 3D Fire Explosion!
        if 3.00 <= t < 6.02:
            p2_in = float(smootherstep(3.00, 3.34, t))
            f2_out = 1.0 - float(smoothstep(5.78, 5.98, t))
            # Subtle impact punch settle at t=3.00s
            dt_ig = t - 3.00
            dy2 = int(round(-math.exp(-dt_ig * 14.0) * math.sin(dt_ig * 60.0) * 5.0))
            eb2 = 1.35 if dt_ig < 0.4 else 0.90
            frame_hdr = self._composite_plate(frame_hdr, self.p2_rgb, self.p2_sh_a, self.p2_fg_a,
                                              p2_in, f2_out, mode="center", ember_boost=eb2, dy_px=dy2)

        # BEAT 3 (6.20s .. 9.97s): Official Studio Reveal + Motto + Day-1 Follow CTA!
        if t >= 6.18:
            p3a_in = float(smootherstep(6.22, 6.78, t))
            frame_hdr = self._composite_plate(frame_hdr, self.p3a_rgb, self.p3a_sh_a, self.p3a_fg_a,
                                              p3a_in, 1.0, mode="ltr", ember_boost=0.95)
        if t >= 6.82:
            p3b_in = float(smootherstep(6.85, 7.28, t))
            # Subtle pulse on "FOLLOW FROM DAY 1" at t=8.0s so eyes glance down right before loop!
            cta_pulse = 0.85 + 0.35 * math.exp(-((t - 8.15) / 0.35) ** 2)
            frame_hdr = self._composite_plate(frame_hdr, self.p3b_rgb, self.p3b_sh_a, self.p3b_fg_a,
                                              p3b_in, 1.0, mode="center", ember_boost=cta_pulse)

        frame_hdr *= master_fade
        return linear_to_srgb_u8(aces_tonemap(frame_hdr))


def build_social_audio(base_wav_path: str, out_wav_path: str):
    """Adds an instant Frame-1 (t=0.03s) tactile spark/woodblock hook accent to mix.wav for maximum Shorts retention."""
    mix, sr = sf.read(base_wav_path, dtype="float32")
    # Add crisp warm harp A4 harmonic + woodblock tick at t=0.03s so Frame 1 has immediate audio-visual lock!
    hook_tick = sfx.click(pitch=0.95, v=0.14)
    hook_note = P.pluck("harp", "A4", dur=0.28, vel=0.42, harmonic=True) * 0.20
    sfx.add(mix, hook_tick, 0.03, gain=1.0, pan=0.0)
    sfx.add(mix, hook_note, 0.03, gain=1.0, pan=0.0)
    # Subtle soft chime on "FOLLOW FROM DAY 1" pulse at 8.15s
    cta_ping = P.pluck("music_box", "A5", dur=1.1, vel=0.48) * 0.14
    sfx.add(mix, cta_ping, 8.15, gain=1.0, pan=0.0)

    # Tame crest factor with transparent 5ms look-ahead limiter so loudnorm hits -14 LUFS at <= -1.2 dBTP
    for ch in range(mix.shape[1]):
        mix[:, ch] = sfx.limit(mix[:, ch], ceil=0.48, look=0.005)
    sf.write(out_wav_path, mix, sr, subtype="PCM_16")


_SOC_WORKER = None


def _init_soc(w: int, h: int):
    global _SOC_WORKER
    cv2.setNumThreads(1)
    _SOC_WORKER = PottsfieldSocialEngine(w, h)


def _render_soc_one(args):
    idx, w, h = args
    rgb = _SOC_WORKER.render_frame(idx / float(FPS), w, h)
    return idx, rgb.tobytes()


def render_social_short(out_mp4: str, poster_jpg: str, workers: int = 2):
    w, h = 1080, 1920
    os.makedirs(os.path.dirname(os.path.abspath(out_mp4)), exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{w}x{h}", "-r", str(FPS),
        "-i", "pipe:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "15",
        "-pix_fmt", "yuvj420p",
        out_mp4,
    ]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    tasks = [(i, w, h) for i in range(TOTAL_FRAMES)]
    poster_idx = int(round(8.15 * FPS))

    try:
        with ProcessPoolExecutor(max_workers=workers, initializer=_init_soc, initargs=(w, h)) as pool:
            for idx, raw_bytes in pool.map(_render_soc_one, tasks, chunksize=4):
                proc.stdin.write(raw_bytes)
                if poster_jpg and idx == poster_idx:
                    arr = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((h, w, 3))
                    Image.fromarray(arr).save(poster_jpg, quality=94)
                if (idx + 1) % 60 == 0 or idx + 1 == TOTAL_FRAMES:
                    print(f"  [Social 1080x1920] {idx + 1}/{TOTAL_FRAMES} frames ({time.time() - t0:.1f}s)", flush=True)
    finally:
        if proc.stdin:
            proc.stdin.close()
        rc = proc.wait()
        if rc != 0:
            sys.exit(f"ffmpeg encode failed: {rc}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview-stills", action="store_true")
    ap.add_argument("--audio-only", action="store_true")
    ap.add_argument("--out-raw", default=os.path.join(HERE, "out", "video_social_9x16.mp4"))
    ap.add_argument("--poster", default=os.path.join(HERE, "poster-launch-short.jpg"))
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()

    if args.preview_stills:
        eng = PottsfieldSocialEngine(1080, 1920)
        os.makedirs("/tmp/social_chk", exist_ok=True)
        for name, ts in [("beat1_hook.jpg", 1.65), ("beat2_turn.jpg", 3.65), ("beat3_crest_cta.jpg", 8.15)]:
            Image.fromarray(eng.render_frame(ts, 1080, 1920)).save(f"/tmp/social_chk/{name}", quality=93)
        print("Saved preview stills to /tmp/social_chk/")
    elif args.audio_only:
        build_social_audio(os.path.join(HERE, "out", "mix.wav"), os.path.join(HERE, "out", "mix_social.wav"))
    else:
        build_social_audio(os.path.join(HERE, "out", "mix.wav"), os.path.join(HERE, "out", "mix_social.wav"))
        render_social_short(args.out_raw, args.poster, workers=args.workers)
