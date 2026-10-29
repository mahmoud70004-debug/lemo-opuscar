"""36.0-Second (1080-Frame @ 30fps) Continuous One-Shot Viral Renderer for Pottsfield Studio.

Implements the motion-skills architecture:
  - Single Focal Point & 1/3 Simultaneity Rule (never stack heavy reading over active logo animation)
  - 100 BPM Beat Grid (1 beat = 0.60s, 1 bar = 2.40s, 15 bars = 36.00s)
  - Continuous World-Space Camera (wy: 0 -> 9600 mod 9600) + Directional Whip-Tilt Blur + Portal Dive
  - Guiding Golden Spark connecting every chapter in one unbroken shot
  - Matched Frame 0 / Frame 1079 composition for an invisible infinite Shorts/Reels/TikTok loop
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import math
import os
import subprocess
import sys
import time
import numpy as np
import cv2
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from engine import (
    PottsfieldEngine,
    aces_tonemap,
    linear_to_srgb_u8,
    srgb_to_linear,
    clamp,
    smoothstep,
    smootherstep,
)
from oneshot_graphics import (
    CINZEL_PATH,
    FELL_IT_PATH,
    MONTSERRAT_PATH,
    LIN_IVORY,
    LIN_GOLD,
    LIN_ORANGE,
    LIN_CRIMSON,
    KineticTextPlate,
    ParametricDeviceMorph,
    build_fake_ad_stamps,
    build_emblem_slash_plate,
    build_story_diorama_planes,
    build_cta_pill_plate,
    ease_out_expo,
    ease_in_out_cubic,
    ease_out_back,
)

FPS_OS = 30
DUR_OS = 36.0
FRAMES_OS = int(round(DUR_OS * FPS_OS))  # 1080 frames
BPM = 100.0
BEAT = 60.0 / BPM     # 0.60s
BAR = 4.0 * BEAT      # 2.40s
STATION_H = 1920.0
WORLD_PERIOD = 5.0 * STATION_H  # 9600.0 px


class PottsfieldOneShotEngine:
    def __init__(self, w: int = 1080, h: int = 1920):
        self.w = w
        self.h = h
        self.logo_engine = PottsfieldEngine()

        # Crop FULL unclipped miniature glowing pumpkin from 1254x1254 hero plate for inside Android/PC screens!
        p_rgb = self.logo_engine.pump_lin[190:1150, 150:1100].copy()
        p_sil = self.logo_engine.hero_sil[190:1150, 150:1100].copy()
        p_cav = self.logo_engine.hero_cav[190:1150, 150:1100].copy()
        p_mini = p_rgb * p_sil[:, :, None] + (LIN_GOLD * 1.65)[None, None, :] * p_cav[:, :, None]
        self.mini_pump_rgb = p_mini.astype(np.float32)
        self.mini_pump_a = p_sil.astype(np.float32)

        # Prebuild vector/SDF & woodcut assets
        self.device_morph = ParametricDeviceMorph(cw=780, ch=680)
        self.fake_ads = build_fake_ad_stamps()
        self.emblem_ad_base, self.emblem_ad_slash, self.emblem_gear = build_emblem_slash_plate(size=330)
        self.diorama = build_story_diorama_planes(w=1640, h=1120)
        self.cta_rgb, self.cta_a = build_cta_pill_plate(width=780, height=192)

        # Deterministic Voronoi/polygon shatter shards for the t=4.80s spark impact!
        rng = np.random.default_rng(20261030)
        self.n_shards = 44
        ang = rng.uniform(0.0, 2.0 * math.pi, self.n_shards).astype(np.float32)
        spd = rng.uniform(280.0, 960.0, self.n_shards).astype(np.float32)
        self.shards = {
            "x0": rng.uniform(-110.0, 110.0, self.n_shards).astype(np.float32),
            "y0": rng.uniform(-190.0, 190.0, self.n_shards).astype(np.float32),
            "vx": np.cos(ang) * spd,
            "vy": np.sin(ang) * spd - 140.0,
            "rot0": rng.uniform(0.0, math.pi, self.n_shards).astype(np.float32),
            "vrot": rng.uniform(-6.5, 6.5, self.n_shards).astype(np.float32),
            "sz": rng.uniform(14.0, 42.0, self.n_shards).astype(np.float32),
            "warm": rng.uniform(0.0, 1.0, self.n_shards).astype(np.float32),
        }

        # Continuous 3-layer ambient embers across the entire 36s periodic world!
        self.n_amb = 90
        self.amb = {
            "x": rng.uniform(40.0, w - 40.0, self.n_amb).astype(np.float32),
            "wy": rng.uniform(0.0, WORLD_PERIOD, self.n_amb).astype(np.float32),
            "depth": rng.choice([0.28, 0.62, 1.18], size=self.n_amb, p=[0.45, 0.35, 0.20]).astype(np.float32),
            "vy": rng.uniform(35.0, 95.0, self.n_amb).astype(np.float32),
            "ph": rng.uniform(0.0, 2.0 * math.pi, self.n_amb).astype(np.float32),
            "rad": rng.uniform(2.2, 6.8, self.n_amb).astype(np.float32),
            "warm": rng.uniform(0.0, 1.0, self.n_amb).astype(np.float32),
        }

        # Prebuild Kinetic Typography Plates (strictly 2-6 words per plate, single focal point!)
        # 1. Hook (0.00 - 2.65s, and 35.75 - 36.00s loop seam): ALREADY UP AT FRAME 0!
        self.txt_hook = KineticTextPlate([
            {"text": "POTTSFIELD  STUDIO", "font": (MONTSERRAT_PATH, 23, 700), "tracking": 6, "style": "crimson", "gap_after": 16, "stars": True},
            {"text": "REMEMBER WHEN", "font": (CINZEL_PATH, 62, 800), "tracking": 3, "style": "ivory", "gap_after": 8},
            {"text": "GAMES HAD A SOUL?", "font": (CINZEL_PATH, 62, 900), "tracking": 2, "style": "orange", "gap_after": 6},
        ], width=960, seed=11)

        # 2a. Chapter 2 Beat A (5.42 - 7.35s): "NO FAKE ADS."
        self.txt_no_ads = KineticTextPlate([
            {"text": "NO FAKE ADS.", "font": (CINZEL_PATH, 78, 900), "tracking": 3, "style": "ivory", "gap_after": 6},
        ], width=940, seed=21)

        # 2b. Chapter 2 Beat B (7.22 - 9.55s): "NO BRAINROT."
        self.txt_no_rot = KineticTextPlate([
            {"text": "NO BRAINROT.", "font": (CINZEL_PATH, 80, 900), "tracking": 3, "style": "orange", "gap_after": 6},
        ], width=940, seed=22)

        # 3a. Chapter 3 Beat A (10.10 - 13.10s): "JUST REAL STORIES."
        self.txt_stories = KineticTextPlate([
            {"text": "JUST REAL", "font": (CINZEL_PATH, 66, 800), "tracking": 3, "style": "ivory", "gap_after": 6},
            {"text": "STORIES.", "font": (CINZEL_PATH, 76, 900), "tracking": 4, "style": "gold", "gap_after": 6},
        ], width=920, seed=31)

        # 3b. Chapter 3 Beat B (13.25 - 16.70s): "2D & 3D WORLDS / Built with Vision & Soul."
        self.txt_worlds = KineticTextPlate([
            {"text": "2D & 3D WORLDS", "font": (CINZEL_PATH, 68, 900), "tracking": 3, "style": "orange", "gap_after": 10},
            {"text": "Built with Vision & Soul.", "font": (FELL_IT_PATH, 44, None), "tracking": 1, "style": "italic_cream", "gap_after": 6},
        ], width=940, seed=32)

        # 4a. Chapter 4 Beat A (17.25 - 19.18s): "ANDROID FIRST."
        self.txt_android = KineticTextPlate([
            {"text": "LAUNCHING ON", "font": (MONTSERRAT_PATH, 24, 700), "tracking": 7, "style": "crimson", "gap_after": 12},
            {"text": "ANDROID FIRST.", "font": (CINZEL_PATH, 70, 900), "tracking": 3, "style": "ivory", "gap_after": 6},
        ], width=940, seed=41)

        # 4b. Chapter 4 Beat B (19.25 - 21.52s): "WINDOWS PC NEXT."
        self.txt_pc = KineticTextPlate([
            {"text": "FOLLOWED BY", "font": (MONTSERRAT_PATH, 24, 700), "tracking": 7, "style": "gold", "gap_after": 12},
            {"text": "WINDOWS PC NEXT.", "font": (CINZEL_PATH, 64, 900), "tracking": 2, "style": "orange", "gap_after": 6},
        ], width=960, seed=42)

        # 6. End-Card Header (30.15 - 35.25s, ONLY after full Pottsfield Crest finishes animating!)
        self.txt_end_top = KineticTextPlate([
            {"text": "A   L U M R O O K   S T U D I O", "font": (MONTSERRAT_PATH, 24, 700), "tracking": 6, "style": "crimson", "gap_after": 14},
            {"text": "“Driven by Story. Lit by Soul.”", "font": (FELL_IT_PATH, 46, None), "tracking": 1, "style": "italic_cream", "gap_after": 6},
        ], width=940, seed=61)

        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        self.scr_x = xx
        self.scr_y = yy
        self.rad_vig = np.sqrt(((xx - w * 0.5) / (w * 0.65)) ** 2 + ((yy - h * 0.5) / (h * 0.58)) ** 2)

    # -------------------------------------------------------------------------
    # Continuous One-Shot Camera Trajectory: world_y(t) in [0 .. 9600]
    # -------------------------------------------------------------------------
    def camera_wy(self, t: float) -> tuple:
        """Returns (wy, wy_velocity_px_per_sec) for authentic directional whip-tilt motion blur."""
        dt = 1.0 / 120.0
        wy0 = self._raw_wy(t)
        wy1 = self._raw_wy(min(t + dt, DUR_OS))
        vel = (wy1 - wy0) / dt
        return wy0, vel

    @staticmethod
    def _raw_wy(t: float) -> float:
        wy = 0.0
        # Whip 1: 4.80s -> 5.44s (Station 0 -> Station 1: 0 -> 1920)
        if t > 4.80:
            wy += STATION_H * ease_in_out_cubic((t - 4.80) / 0.64)
        # Glide 2: 9.60s -> 10.45s (Station 1 -> Station 2: 1920 -> 3840)
        if t > 9.60:
            wy += STATION_H * ease_in_out_cubic((t - 9.60) / 0.85)
        # Whip 3: 16.80s -> 17.42s (Station 2 -> Station 3: 3840 -> 5760)
        if t > 16.80:
            wy += STATION_H * ease_in_out_cubic((t - 16.80) / 0.62)
        # Portal Dive 4: 21.60s -> 22.30s (Station 3 -> Station 4: 5760 -> 7680)
        if t > 21.60:
            wy += STATION_H * ease_in_out_cubic((t - 21.60) / 0.70)
        # Upward Whip-Loop 5: 35.20s -> 36.00s (Station 4 -> Station 0 wrap: 7680 -> 9600 == 0!)
        if t > 35.20:
            wy += STATION_H * ease_in_out_cubic((t - 35.20) / 0.80)
        return wy

    # -------------------------------------------------------------------------
    # Guiding Golden Spark Position in Screen Coordinates (One continuous entity!)
    # -------------------------------------------------------------------------
    def spark_screen_pos(self, t: float, wy: float) -> tuple:
        """Returns (sx, sy, intensity) of the continuous Guiding Spark across all 36s."""
        cx = self.w * 0.5
        if t < 2.40:
            # Gentle figure-8 hover between Hook text and Smartphone top bezel (matches t=36.00s!)
            ang = 2.0 * math.pi * (t / 2.40)
            sx = cx + 68.0 * math.sin(ang)
            sy = 805.0 + 18.0 * math.sin(2.0 * ang)
            return sx, sy, 0.95
        elif t < 4.80:
            # Orbits tighter and dives straight into phone screen center at t=4.80s!
            u = (t - 2.40) / 2.40
            ang = 2.0 * math.pi * (u * 2.0)
            rad = (1.0 - smoothstep(0.55, 0.98, u)) * 135.0
            sx = cx + math.sin(ang) * rad
            sy = (805.0 * (1.0 - ease_in_out_cubic(min(u * 1.4, 1.0)))
                  + 980.0 * ease_in_out_cubic(min(u * 1.4, 1.0)))
            boost = 1.0 + 1.8 * smoothstep(0.82, 1.0, u)
            return sx, sy, boost
        elif t < 5.45:
            # Carries the eye through Whip-Tilt 1 right onto Emblem 1!
            u = (t - 4.80) / 0.65
            sx = cx + 45.0 * math.sin(u * math.pi)
            sy = 980.0 * (1.0 - u) + 735.0 * u
            return sx, sy, 2.2 - 0.8 * u
        elif t < 7.15:
            # Traces the X-slash on the Fake-Ad emblem, then hovers ready at left edge
            u = (t - 5.45) / 1.70
            if u < 0.35:
                v = u / 0.35
                sx = (cx - 95.0) * (1.0 - v) + (cx + 95.0) * v
                sy = (735.0 + 95.0) * (1.0 - v) + (735.0 - 95.0) * v
                return sx, sy, 1.65
            else:
                v = ease_in_out_cubic((u - 0.35) / 0.65)
                sx = (cx + 95.0) * (1.0 - v) + 140.0 * v
                sy = 640.0 * (1.0 - v) + 1090.0 * v
                return sx, sy, 1.05
        elif t < 7.58:
            # HORIZONTAL GOUGE SLICE across "NO FAKE ADS." -> "NO BRAINROT."!
            u = ease_out_expo((t - 7.15) / 0.43)
            sx = 140.0 + u * 800.0
            sy = 1090.0 - 12.0 * math.sin(u * math.pi)
            return sx, sy, 2.35
        elif t < 9.60:
            # Rises gracefully to orbit the dissolving gear stars
            u = ease_in_out_cubic((t - 7.58) / 2.02)
            ang = u * 2.5 * math.pi
            sx = (940.0 * (1.0 - u) + cx * u) + 85.0 * math.cos(ang) * u
            sy = (1090.0 * (1.0 - u) + 735.0 * u) + 85.0 * math.sin(ang) * u
            return sx, sy, 1.15
        elif t < 16.80:
            # Glides into Station 2 Diorama and lights the traveler's lantern at t=14.1s!
            u = (t - 9.60) / 7.20
            sx = cx + 145.0 * math.sin(u * 2.2 * math.pi)
            sy = 780.0 + 360.0 * smoothstep(0.05, 0.55, u) - 60.0 * smoothstep(0.75, 1.0, u)
            flare = 1.15 + 1.5 * math.exp(-((t - 14.10) / 0.32) ** 2)
            return sx, sy, flare
        elif t < 21.60:
            # Dives into center of Android Phone -> Windows PC screen heart!
            u = (t - 16.80) / 4.80
            sx = cx + 36.0 * math.sin(u * 4.0 * math.pi) * (1.0 - smoothstep(0.7, 1.0, u))
            sy = 825.0 + 22.0 * math.cos(u * 4.0 * math.pi)
            flare = 1.1 + 1.4 * math.exp(-((t - 19.22) / 0.22) ** 2)
            return sx, sy, flare
        elif t < 35.15:
            # During PottsfieldEngine sequence (21.6 -> 35.15s), PottsfieldEngine renders its own carving gouge spark!
            # Fade external guiding spark smoothly out during carving/crest, then re-awaken at pumpkin stem at 35.0s!
            if t < 22.45:
                op = 1.0 - smoothstep(21.85, 22.42, t)
                return cx, 880.0, 1.4 * op
            elif t > 34.85:
                op = smoothstep(34.85, 35.15, t)
                return cx, 940.0, 1.35 * op
            return cx, 940.0, 0.0
        else:
            # 35.15s -> 36.00s: Shoots upward from pumpkin stem back to exact t=0.00s position (cx, 805)!
            u = ease_in_out_cubic((t - 35.15) / 0.85)
            sx = cx + 38.0 * math.sin(u * math.pi)
            sy = 940.0 * (1.0 - u) + 805.0 * u
            return sx, sy, 1.95 - 1.0 * u

    # -------------------------------------------------------------------------
    # Station Renderers (each drawn in local station coords, offset by sy_off = station_wy - wy)
    # -------------------------------------------------------------------------
    def _draw_station_0_hook(self, hdr: np.ndarray, t: float, sy_off: float, is_wrap: bool = False):
        """Station 0 (wy = 0 or 9600): Hook Headline + Woodcut Smartphone + Fake-Ad Overload."""
        if abs(sy_off) > self.h * 1.25:
            return
        cx = self.w * 0.5
        t_eff = 0.0 if is_wrap else t

        # Camera push-in on phone during 2.40s -> 4.80s!
        push_u = ease_in_out_cubic((t_eff - 2.38) / 2.25) if not is_wrap and t_eff > 2.38 else 0.0
        phone_scale = 1.0 + 0.54 * push_u
        phone_cy = (1175.0 * (1.0 - push_u) + 980.0 * push_u) + sy_off

        # Cold broken screen flicker + rising golden cracks right before t=4.80s shatter!
        flick = 0.75 + 0.25 * math.sin(t_eff * 19.0) * math.cos(t_eff * 7.0)
        crack = smoothstep(3.30, 4.76, t_eff) if not is_wrap else 0.0
        pre_shatter_glow = 0.55 * smoothstep(4.25, 4.79, t_eff) if not is_wrap else 0.0

        # Hide intact phone at t >= 4.80s (when it shatters into shards!)
        if is_wrap or t_eff < 4.80:
            scr_cx, scr_cy, sbx, sby = self.device_morph.render_onto_hdr(
                hdr, cx=cx, cy=phone_cy,
                u_morph=0.0, inner_glow=pre_shatter_glow,
                scale=phone_scale, cold_broken=flick, crack_amt=crack, opacity=1.0
            )

            # During 2.50s -> 4.80s: Slam the 4 Fake-Ad Clutter Cards inside the zoomed phone screen!
            if not is_wrap and 2.48 <= t_eff < 4.80:
                beat_times = [2.52, 3.04, 3.56, 4.06]
                offsets = [(-18, -125), (16, -32), (-14, 62), (10, 148)]
                for idx, (bt, (ox, oy)) in enumerate(zip(beat_times, offsets)):
                    if t_eff < bt:
                        continue
                    pop = ease_out_back(min((t_eff - bt) / 0.24, 1.0), overshoot=1.65)
                    c_rgb, c_a = self.fake_ads[idx]
                    cw_s = max(int(round(c_rgb.shape[1] * 0.72 * phone_scale * pop)), 12)
                    ch_s = max(int(round(c_rgb.shape[0] * 0.72 * phone_scale * pop)), 12)
                    c_rgb_r = cv2.resize(c_rgb, (cw_s, ch_s), interpolation=cv2.INTER_LINEAR)
                    c_a_r = cv2.resize(c_a, (cw_s, ch_s), interpolation=cv2.INTER_LINEAR)

                    px0 = int(round(scr_cx + ox * phone_scale - cw_s * 0.5))
                    py0 = int(round(scr_cy + oy * phone_scale - ch_s * 0.5))
                    # Clip inside screen box
                    x_min = max(0, int(round(scr_cx - sbx + 6)))
                    x_max = min(self.w, int(round(scr_cx + sbx - 6)))
                    y_min = max(0, int(round(scr_cy - sby + 6)))
                    y_max = min(self.h, int(round(scr_cy + sby - 6)))

                    dx0, dy0 = max(x_min, px0), max(y_min, py0)
                    dx1, dy1 = min(x_max, px0 + cw_s), min(y_max, py0 + ch_s)
                    if dx1 > dx0 and dy1 > dy0:
                        sx0, sy0 = dx0 - px0, dy0 - py0
                        roi = hdr[dy0:dy1, dx0:dx1]
                        aa = c_a_r[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0), None]
                        roi[:] = roi * (1.0 - aa) + c_rgb_r[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)]

        # Hook Headline: ALREADY crisp & settled at t=0.00s (enter_t=10.0 so u_in=1.0 on Frame 0 & Frame 1079!)
        # Exits smoothly upward at 2.25s -> 2.75s BEFORE fake-ad cards pile up!
        hook_exit = clamp((t_eff - 2.22) / 0.52) if not is_wrap else 0.0
        self.txt_hook.composite_onto(
            hdr, cx=cx, cy=515.0 + sy_off,
            enter_t=10.0, exit_u=hook_exit, mode="mask_up"
        )

    def _draw_shatter_burst(self, hdr: np.ndarray, t: float):
        """Renders the 44 woodcut/ember shards exploding outward at t=4.80s..6.15s."""
        if not (4.80 <= t <= 6.20):
            return
        dt = t - 4.80
        fade = 1.0 - smoothstep(0.55, 1.38, dt)
        if fade <= 0.004:
            return
        # Initial golden impact flash at t=4.80s
        if dt < 0.22:
            fl = math.exp(-dt / 0.055) * 0.85
            rn = np.sqrt(((self.scr_x - 540.0) / 380.0) ** 2 + ((self.scr_y - 960.0) / 380.0) ** 2)
            hdr += (LIN_GOLD * fl)[None, None, :] * np.exp(-(rn ** 2))[:, :, None]

        cx, cy = 540.0, 960.0 - 420.0 * smoothstep(0.0, 0.65, dt)
        for i in range(self.n_shards):
            px = cx + self.shards["x0"][i] + self.shards["vx"][i] * dt
            py = cy + self.shards["y0"][i] + self.shards["vy"][i] * dt + 480.0 * (dt ** 2)
            sz = self.shards["sz"][i] * (1.0 - 0.45 * min(dt, 1.2))
            if px < -50 or px > self.w + 50 or py < -50 or py > self.h + 50 or sz < 3:
                continue
            ang = float(self.shards["rot0"][i] + self.shards["vrot"][i] * dt)
            c, s = math.cos(ang), math.sin(ang)
            pts = np.array([
                [px + c * sz - s * sz * 0.4, py + s * sz + c * sz * 0.4],
                [px - c * sz * 0.8 - s * sz * 0.5, py - s * sz * 0.8 + c * sz * 0.5],
                [px + c * sz * 0.2 + s * sz * 0.7, py + s * sz * 0.2 - c * sz * 0.7],
            ], dtype=np.int32)
            x0, y0 = max(0, int(pts[:, 0].min()) - 2), max(0, int(pts[:, 1].min()) - 2)
            x1, y1 = min(self.w, int(pts[:, 0].max()) + 3), min(self.h, int(pts[:, 1].max()) + 3)
            if x1 <= x0 or y1 <= y0:
                continue
            mask = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)
            cv2.fillConvexPoly(mask, pts - np.array([[x0, y0]]), 255, lineType=cv2.LINE_AA)
            mf = (mask.astype(np.float32) / 255.0) * fade
            col = LIN_GOLD * 1.45 if self.shards["warm"][i] > 0.45 else LIN_CRIMSON * 1.25
            roi = hdr[y0:y1, x0:x1]
            roi[:] = roi * (1.0 - mf[:, :, None] * 0.75) + col[None, None, :] * mf[:, :, None]

    def _draw_station_1_manifesto(self, hdr: np.ndarray, t: float, sy_off: float):
        """Station 1 (wy = 1920): 'NO FAKE ADS.' -> horizontal gouge slice -> 'NO BRAINROT.'"""
        if abs(sy_off) > self.h * 1.25:
            return
        cx = self.w * 0.5

        # Subtle micro beat-punch at t=7.20s!
        punch = 1.0 + 0.065 * math.exp(-((t - 7.24) / 0.16) ** 2) if t >= 7.18 else 1.0

        # Emblem slot centered at y_local = 735
        ey = int(round(735.0 + sy_off))
        es = self.emblem_ad_base.shape[0]
        ex0, ey0 = int(round(cx - es * 0.5)), int(round(ey - es * 0.5))
        ex1, ey1 = ex0 + es, ey0 + es

        if 0 <= ex0 and ex1 <= self.w and 0 <= ey0 and ey1 <= self.h:
            roi = hdr[ey0:ey1, ex0:ex1]
            if t < 7.26:
                # Emblem A: Fake-Ad badge + animated X-slash!
                in_a = ease_out_expo((t - 5.22) / 0.38)
                out_a = 1.0 - smoothstep(7.14, 7.26, t)
                slash_p = smoothstep(5.40, 5.75, t)
                xx_u = np.linspace(0.0, 1.0, es, dtype=np.float32)[None, :]
                sl_m = self.emblem_ad_slash * (1.0 - smoothstep(slash_p - 0.06, slash_p + 0.06, xx_u))
                base_m = self.emblem_ad_base * in_a * out_a
                sl_m = sl_m * in_a * out_a
                roi[:] += base_m[:, :, None] * (LIN_IVORY * 0.85)[None, None, :]
                roi[:] += sl_m[:, :, None] * (LIN_ORANGE * 1.85)[None, None, :]
            if t >= 7.18:
                # Emblem B: Broken endless-gear morphing into glowing Pottsfield stars!
                in_b = ease_out_back(min((t - 7.18) / 0.36, 1.0), overshoot=1.35)
                out_b = 1.0 - smoothstep(9.45, 9.85, t)
                ang_deg = (t - 7.18) * 26.0
                M = cv2.getRotationMatrix2D((es * 0.5, es * 0.5), ang_deg, max(in_b, 0.05))
                rot_b = cv2.warpAffine(self.emblem_gear, M, (es, es), flags=cv2.INTER_LINEAR)
                roi[:] += (rot_b * out_b)[:, :, None] * (LIN_GOLD * 1.35)[None, None, :]

        # Synchronized Gouge-Spark Rewrite at 7.15s..7.58s:
        #   - Right of spark: "NO FAKE ADS." being carved away!
        #   - Left of spark:  "NO BRAINROT." revealed cleanly in its wake — ZERO overlapping letters!
        wipe_u = ease_out_expo(clamp((t - 7.15) / 0.43)) if t >= 7.15 else -1.0
        if t < 7.58:
            self.txt_no_ads.composite_onto(
                hdr, cx=cx, cy=1090.0 + sy_off,
                enter_t=max(0.0, t - 5.38), dur=0.38,
                exit_u=0.0, mode="mask_up", scale=punch, slice_u=wipe_u
            )

        if t >= 7.16:
            rev_u = wipe_u if t < 7.58 else -1.0
            self.txt_no_rot.composite_onto(
                hdr, cx=cx, cy=1090.0 + sy_off,
                enter_t=1.0, dur=0.36,
                exit_u=clamp((t - 9.40) / 0.45), mode="ltr_wipe", scale=punch,
                reveal_ltr_u=rev_u
            )

    def _draw_station_2_diorama(self, hdr: np.ndarray, t: float, sy_off: float):
        """Station 2 (wy = 3840): 4-Plane Parallax 2D Woodcut -> 3D Lantern Story World."""
        if abs(sy_off) > self.h * 1.25:
            return
        cx = self.w * 0.5

        # Lateral camera pan across the wide 1640px diorama + subtle zoom!
        pan_u = ease_in_out_cubic(clamp((t - 9.80) / 6.90))
        cam_pan_x = -150.0 + 300.0 * pan_u

        # 2D Woodcut -> 3D Volumetric Lantern wave triggered at t=13.55s..15.20s!
        mix_3d = smootherstep(13.45, 15.10, t)
        carve_in = smootherstep(9.70, 10.75, t)

        dw, dh = self.diorama["w"], self.diorama["h"]
        y_top = int(round(590.0 + sy_off))
        y_bot = y_top + dh

        if y_bot > 0 and y_top < self.h:
            dy0, dy1 = max(0, y_top), min(self.h, y_bot)
            sy0 = dy0 - y_top
            sy1 = sy0 + (dy1 - dy0)
            roi_h = dy1 - dy0
            roi = hdr[dy0:dy1, :]

            # Smooth vertical feather at top & bottom of diorama so sky & ground melt seamlessly into velvet night!
            yy_n = np.linspace(sy0 / dh, sy1 / dh, roi_h, dtype=np.float32)[:, None]
            dio_feather = smoothstep(0.01, 0.22, yy_n) * (1.0 - smoothstep(0.86, 0.995, yy_n))

            # Warm atmospheric 3D sunset/lantern sky gradient behind trees as mix_3d blooms!
            if mix_3d > 0.005:
                sky_glow = (LIN_ORANGE[None, None, :] * 0.28 * np.exp(-((yy_n - 0.66) / 0.25) ** 2)[:, :, None]
                            + LIN_CRIMSON[None, None, :] * 0.16 * np.exp(-((yy_n - 0.44) / 0.28) ** 2)[:, :, None])
                roi[:] += sky_glow * (mix_3d * dio_feather[:, :, None])

            # Composite each depth plane with true differential parallax!
            planes = [
                ("p1", 0.28, 0.42, np.array([0.020, 0.006, 0.005], dtype=np.float32)),
                ("p2", 0.62, 0.72, np.array([0.012, 0.004, 0.003], dtype=np.float32)),
                ("p3", 1.04, 1.05, np.array([0.005, 0.002, 0.002], dtype=np.float32)),
            ]
            for prefix, p_spd, ink_str, sil_3d_col in planes:
                x_center_in_d = dw * 0.5 + cam_pan_x * p_spd
                sx0 = int(round(x_center_in_d - self.w * 0.5))
                sx0 = int(np.clip(sx0, 0, dw - self.w))
                sx1 = sx0 + self.w

                sil = self.diorama[f"{prefix}_sil"][sy0:sy1, sx0:sx1] * dio_feather
                edg = self.diorama[f"{prefix}_edge"][sy0:sy1, sx0:sx1] * carve_in * dio_feather
                grn = self.diorama["grain"][sy0:sy1, sx0:sx1]

                # Occlude far planes cleanly behind nearer silhouettes
                occ = sil * clamp(carve_in * 1.2)
                fill_col = sil_3d_col * mix_3d
                roi[:] = roi * (1.0 - occ[:, :, None] * 0.94) + fill_col[None, None, :] * occ[:, :, None]

                # 2D Woodcut Ivory Ink edges morphing into warm 3D Harvest Rim-Light!
                edge_col = LIN_IVORY * (1.0 - 0.55 * mix_3d) + (LIN_ORANGE * 1.35) * mix_3d
                roi[:] += (edg * grn * ink_str)[:, :, None] * edge_col[None, None, :]

                # Glowing lanterns on this plane!
                lant_key = "p1_win" if prefix == "p1" else f"{prefix}_lant"
                lant = self.diorama[lant_key][sy0:sy1, sx0:sx1] * dio_feather
                lant_on = 0.28 * carve_in + 1.35 * mix_3d * (0.90 + 0.10 * math.sin(t * 9.0 + p_spd * 4.0))
                if lant_on > 0.01:
                    halo = cv2.GaussianBlur(lant, (0, 0), sigmaX=18.0, sigmaY=18.0) * dio_feather
                    roi[:] += lant[:, :, None] * (LIN_GOLD * 1.6 * lant_on)[None, None, :]
                    roi[:] += halo[:, :, None] * (LIN_ORANGE * 1.4 * lant_on)[None, None, :]

        # Sequential Single-Focus Titles in clean upper sky (y_local = 435):
        if t < 13.22:
            self.txt_stories.composite_onto(
                hdr, cx=cx, cy=435.0 + sy_off,
                enter_t=max(0.0, t - 10.05), stagger=0.10, dur=0.42,
                exit_u=clamp((t - 12.82) / 0.38), mode="mask_up"
            )
        if t >= 13.20:
            self.txt_worlds.composite_onto(
                hdr, cx=cx, cy=435.0 + sy_off,
                enter_t=t - 13.20, stagger=0.12, dur=0.42,
                exit_u=clamp((t - 16.48) / 0.36), mode="mask_up"
            )

    def _draw_station_3_platforms(self, hdr: np.ndarray, t: float, sy_off: float):
        """Station 3 (wy = 5760): Parametric Android Phone -> Windows PC Spring Morph + Portal Dive!"""
        if abs(sy_off) > self.h * 1.35 and not (21.55 <= t <= 22.35):
            return
        cx = self.w * 0.5

        # Anticipation dip (19.06..19.20s) -> Snappy Spring Morph Phone(0) -> PC Monitor(1) at 19.20s!
        if t < 19.20:
            u_morph = 0.0
            antic = 1.0 - 0.06 * math.sin(clamp((t - 19.04) / 0.16) * math.pi) if t > 19.04 else 1.0
        else:
            u_morph = float(np.clip(ease_out_back(min((t - 19.20) / 0.56, 1.0), overshoot=1.18), 0.0, 1.0))
            antic = 1.0

        # Portal Dive through the PC Monitor glass at t = 21.55s -> 22.32s!
        if t >= 21.55:
            dive_u = ease_in_out_cubic(clamp((t - 21.55) / 0.75))
            portal_scale = 1.0 + 4.8 * (dive_u ** 2.2)
            portal_op = 1.0 - smoothstep(0.62, 0.98, dive_u)
            dev_cy = 815.0 * (1.0 - dive_u) + 960.0 * dive_u
        else:
            portal_scale = antic
            portal_op = 1.0
            dev_cy = 815.0 + sy_off

        glow_pulse = (0.85 + 0.15 * math.sin(t * 5.2)) * smoothstep(16.95, 17.45, t)
        if t >= 21.55:
            # Fade inner miniature pumpkin during portal dive so we fly into pure dark velvet!
            glow_pulse *= (1.0 - smoothstep(21.55, 21.95, t))

        self.device_morph.render_onto_hdr(
            hdr, cx=cx, cy=dev_cy,
            u_morph=u_morph, inner_glow=glow_pulse,
            scale=portal_scale, cold_broken=0.0, crack_amt=0.0,
            opacity=portal_op,
            mini_pump=self.mini_pump_rgb, mini_pump_mask=self.mini_pump_a
        )

        # Clean sequential platform titles below the device (y_local = 1320):
        if t < 19.24:
            self.txt_android.composite_onto(
                hdr, cx=cx, cy=1315.0 + sy_off,
                enter_t=max(0.0, t - 17.24), stagger=0.08, dur=0.38,
                exit_u=clamp((t - 18.92) / 0.30), mode="mask_up"
            )
        if 19.22 <= t < 21.65:
            self.txt_pc.composite_onto(
                hdr, cx=cx, cy=1315.0 + sy_off,
                enter_t=t - 19.22, stagger=0.08, dur=0.38,
                exit_u=clamp((t - 21.25) / 0.35), mode="mask_up"
            )

    def _render_logo_hdr(self, t_logo: float, dy_shift: float, scale_mul: float = 1.0) -> np.ndarray:
        """Renders PottsfieldEngine directly in linear HDR with custom vertical camera shift & scale."""
        from prepare_assets import HERO_IN_LOGO_SCALE, HERO_IN_LOGO_OX, HERO_IN_LOGO_OY
        W, H = self.w, self.h
        le = self.logo_engine
        cam = le.camera_state(t_logo, W, H)
        cam["screen_cy"] += dy_shift
        cam["scale"] *= scale_mul

        frame_hdr = np.zeros((H, W, 3), dtype=np.float32)
        if t_logo >= 3.00:
            amb_str = (1.0 - 0.72 * float(smootherstep(5.5, 7.2, t_logo))) * float(smoothstep(3.00, 3.25, t_logo))
            if amb_str > 1e-3:
                lx, ly = le.world_to_screen(621.0, 900.0, cam)
                xx, yy = le._get_grid(W, H)
                rr = np.sqrt(((xx - lx) / (max(W, H) * 0.48)) ** 2 + ((yy - ly) / (max(W, H) * 0.48)) ** 2)
                glow_bg = np.exp(-(rr ** 1.7) * 2.1) * amb_str
                frame_hdr += glow_bg[:, :, None] * np.array([0.075, 0.020, 0.005], dtype=np.float32)

        bg_part = np.zeros_like(frame_hdr)
        fg_part = np.zeros_like(frame_hdr)
        le.render_3d_particles(bg_part, fg_part, t_logo, cam)
        frame_hdr += bg_part

        hero_hdr, hero_alpha, hero_rays = le.shade_hero_pumpkin(t_logo, cam)
        sc_hero = HERO_IN_LOGO_SCALE * cam["scale"]
        tx_hero = (HERO_IN_LOGO_OX - cam["cam_wx"]) * cam["scale"] + cam["screen_cx"]
        ty_hero = (HERO_IN_LOGO_OY - cam["cam_wy"]) * cam["scale"] + cam["screen_cy"]
        M_hero_screen = np.array([[sc_hero, 0.0, tx_hero], [0.0, sc_hero, ty_hero]], dtype=np.float32)
        interp_flag = cv2.INTER_AREA if sc_hero < 0.95 else cv2.INTER_LINEAR

        if t_logo >= 5.96:
            crest_hdr, fg_leaf_over_hero = le.shade_crest_layers(t_logo)
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
        rays_scr_src = cv2.warpAffine(hero_rays, M_hero_screen, (W, H), flags=interp_flag, borderMode=cv2.BORDER_CONSTANT)

        if crest_scr is not None:
            frame_hdr += crest_scr * (1.0 - hero_scr_a[:, :, None] * (1.0 - fg_leaf_scr[:, :, None]))
            hero_vis_a = hero_scr_a * (1.0 - fg_leaf_scr)
            frame_hdr = frame_hdr * (1.0 - hero_vis_a[:, :, None]) + hero_scr_hdr * hero_vis_a[:, :, None]
        else:
            frame_hdr = frame_hdr * (1.0 - hero_scr_a[:, :, None]) + hero_scr_hdr

        light_sx, light_sy = le.world_to_screen(621.0, 905.0, cam)
        frame_hdr += le.volumetric_god_rays(rays_scr_src, light_sx, light_sy, t_logo) * 0.88

        bright = np.maximum(frame_hdr - 0.55, 0.0)
        q_bright = cv2.resize(bright, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
        b_small = cv2.resize(cv2.GaussianBlur(q_bright, (0, 0), sigmaX=3.2), (W, H), interpolation=cv2.INTER_LINEAR)
        b_wide = cv2.resize(cv2.GaussianBlur(q_bright, (0, 0), sigmaX=8.0), (W, H), interpolation=cv2.INTER_LINEAR)
        bloom_amt = 0.28 if t_logo < 6.5 else 0.14
        frame_hdr += b_small * bloom_amt + b_wide * (bloom_amt * 0.85)
        frame_hdr += fg_part
        return frame_hdr

    def _draw_station_4_hero_and_crest(self, hdr: np.ndarray, t: float, sy_off: float):
        """
        Station 4 (wy = 7680, t = 21.8s .. 35.95s):
          - 22.20s .. 30.00s: ZERO TEXT! Pure 2D Woodcut Pumpkin Carving -> 3D Lantern Drop (25.20s) -> Full Crest!
          - 30.00s .. 35.20s: Crest settles upward calmly; Tagline + 'FOLLOW FROM DAY 1' CTA hold cleanly!
        """
        if t < 21.95 or abs(sy_off) > self.h * 1.25:
            return

        if t <= 25.20:
            u = clamp((t - 22.10) / (25.20 - 22.10))
            t_logo = 0.18 + u * (3.00 - 0.18)
        elif t <= 27.60:
            u = (t - 25.20) / (27.60 - 25.20)
            t_logo = 3.00 + u * (6.00 - 3.00)
        elif t <= 30.00:
            u = (t - 27.60) / (30.00 - 27.60)
            t_logo = 6.00 + u * (7.65 - 6.00)
        else:
            u = clamp((t - 30.00) / 5.20)
            t_logo = 7.65 + u * (8.85 - 7.65)

        settle_u = ease_in_out_cubic(clamp((t - 29.85) / 0.80))
        end_card_lift = -95.0 * settle_u
        scale_mul = 1.0 - 0.11 * settle_u  # Gently settles to 0.89x so top & bottom text have huge breathing room!
        logo_hdr = self._render_logo_hdr(t_logo, dy_shift=sy_off + end_card_lift, scale_mul=scale_mul)

        in_fade = smoothstep(21.95, 22.35, t)
        hdr[:] += logo_hdr * in_fade

        # ONLY AFTER the full Pottsfield STUDIO crest finishes blooming (t >= 30.10s):
        if t >= 30.10:
            exit_end = clamp((t - 35.05) / 0.35)
            # Top signature ("A LUMROOK STUDIO / Driven by Story. Lit by Soul.")
            self.txt_end_top.composite_onto(
                hdr, cx=self.w * 0.5, cy=345.0 + sy_off,
                enter_t=t - 30.10, stagger=0.12, dur=0.45,
                exit_u=exit_end, mode="mask_up"
            )
            # Bottom CTA Pill ("FOLLOW FROM DAY 1 / ANDROID · WINDOWS PC") at t >= 30.85s
            if t >= 30.85:
                cta_in = ease_out_back(min((t - 30.85) / 0.48, 1.0), overshoot=1.18)
                cta_op = clamp((t - 30.85) / 0.32) * (1.0 - exit_end)
                # Subtle warm beacon pulse at t = 32.40s
                pulse = 1.0 + 0.28 * math.exp(-((t - 32.40) / 0.36) ** 2)
                cw_p = max(int(round(self.cta_rgb.shape[1] * cta_in)), 16)
                ch_p = max(int(round(self.cta_rgb.shape[0] * cta_in)), 16)
                c_rgb = cv2.resize(self.cta_rgb, (cw_p, ch_p), interpolation=cv2.INTER_LINEAR) * pulse
                c_a = cv2.resize(self.cta_a, (cw_p, ch_p), interpolation=cv2.INTER_LINEAR) * cta_op

                x0 = int(round(self.w * 0.5 - cw_p * 0.5))
                y0 = int(round(1435.0 + sy_off - ch_p * 0.5))
                dx0, dy0 = max(0, x0), max(0, y0)
                dx1, dy1 = min(self.w, x0 + cw_p), min(self.h, y0 + ch_p)
                if dx1 > dx0 and dy1 > dy0:
                    sx0, sy0 = dx0 - x0, dy0 - y0
                    roi = hdr[dy0:dy1, dx0:dx1]
                    aa = c_a[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0), None]
                    roi[:] = roi * (1.0 - aa) + c_rgb[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)]

    # -------------------------------------------------------------------------
    # Continuous Ambient Embers + Guiding Golden Spark Ribbon + Fast HDR Bloom
    # -------------------------------------------------------------------------
    def _draw_ambient_embers_and_spark(self, hdr: np.ndarray, t: float, wy: float):
        # 1. 3-Layer Parallax Periodic World Embers (ensures Frame 0 == Frame 1080 seamlessly!)
        # Make t_loop periodic over 36.0s so particle positions match identically at t=0 and t=36!
        omega = 2.0 * math.pi / DUR_OS
        # Suppress ambient embers slightly during the pre-drop hush (21.8..24.8s) so darkness feels sacred
        amb_gain = 1.0 - 0.72 * (smoothstep(21.7, 22.3, t) * (1.0 - smoothstep(24.9, 25.4, t)))
        for i in range(self.n_amb):
            d = float(self.amb["depth"][i])
            # Integer drift cycles per 36s so wy wraps cleanly mod WORLD_PERIOD!
            wy_i = (self.amb["wy"][i] - (t / DUR_OS) * STATION_H * 2.0) % WORLD_PERIOD
            # Project periodic world y relative to camera wy*d
            dy = (wy_i - (wy * d) % WORLD_PERIOD) % WORLD_PERIOD
            if dy > self.h + 40.0:
                if dy > WORLD_PERIOD - 40.0:
                    dy -= WORLD_PERIOD
                else:
                    continue
            px = float(self.amb["x"][i] + 24.0 * d * math.sin(omega * t * 3.0 + self.amb["ph"][i]))
            py = float(dy)
            r = int(round(self.amb["rad"][i] * (0.65 + 0.55 * d)))
            x0, y0 = max(0, int(px) - r * 3), max(0, int(py) - r * 3)
            x1, y1 = min(self.w, int(px) + r * 3 + 1), min(self.h, int(py) + r * 3 + 1)
            if x1 <= x0 or y1 <= y0:
                continue
            gx = self.scr_x[y0:y1, x0:x1] - px
            gy = self.scr_y[y0:y1, x0:x1] - py
            falloff = np.exp(-(gx * gx + gy * gy) / max(2.0 * (r * 0.85) ** 2, 1.5))
            col = LIN_GOLD * 0.24 if self.amb["warm"][i] > 0.5 else LIN_ORANGE * 0.20
            twinkle = (0.65 + 0.35 * math.sin(omega * t * 6.0 + self.amb["ph"][i])) * amb_gain
            hdr[y0:y1, x0:x1] += falloff[:, :, None] * (col * twinkle)[None, None, :]

        # 2. Continuous Guiding Golden Spark + 10-Sample Subframe Comet Ribbon (zero square ROI clipping!)
        sx, sy, s_int = self.spark_screen_pos(t, wy)
        if s_int > 0.02:
            for k in range(9, -1, -1):
                tk = max(0.0, t - k * 0.011)
                wyk = self._raw_wy(tk)
                xk, yk, ik = self.spark_screen_pos(tk, wyk)
                if ik <= 0.01:
                    continue
                w_tail = ((10 - k) / 10.0) ** 2.1
                r_max = 82.0 if k == 0 else (24.0 + 42.0 * w_tail)
                x0, y0 = max(0, int(xk - r_max)), max(0, int(yk - r_max))
                x1, y1 = min(self.w, int(xk + r_max) + 1), min(self.h, int(yk + r_max) + 1)
                if x1 <= x0 or y1 <= y0:
                    continue
                gx = self.scr_x[y0:y1, x0:x1] - xk
                gy = self.scr_y[y0:y1, x0:x1] - yk
                r2 = gx * gx + gy * gy
                win = (1.0 - np.clip(r2 / (r_max * r_max), 0.0, 1.0)) ** 2
                core = np.exp(-r2 / (2.0 * (2.6 if k == 0 else 4.2) ** 2)) * win
                halo = np.exp(-r2 / (2.0 * (18.0 * w_tail + 4.5) ** 2)) * win
                gain = ik * (0.55 if k == 0 else 0.13 * w_tail)
                hdr[y0:y1, x0:x1] += (
                    core[:, :, None] * (LIN_IVORY * 2.4 * gain)[None, None, :]
                    + halo[:, :, None] * (LIN_ORANGE * 1.25 * gain)[None, None, :]
                )

    # -------------------------------------------------------------------------
    # Master Frame Renderer (Pure deterministic function of t in [0, 36.0))
    # -------------------------------------------------------------------------
    def render_frame(self, t: float) -> np.ndarray:
        wy, wy_vel = self.camera_wy(t)

        # Warm ambient hearth background (deep velvet black edges + subtle ember core)
        hearth_lvl = 0.008 + 0.010 * math.sin(2.0 * math.pi * t / DUR_OS)
        # Drop background to pure velvet black during the pre-spark hush (22.0..25.1s)!
        hush_duck = 1.0 - 0.92 * (smoothstep(21.7, 22.3, t) * (1.0 - smoothstep(25.0, 25.3, t)))
        bg_glow = np.maximum(1.0 - 0.85 * self.rad_vig, 0.0) * hearth_lvl * hush_duck
        hdr = np.zeros((self.h, self.w, 3), dtype=np.float32)
        hdr[:, :, 0] = bg_glow * 0.95
        hdr[:, :, 1] = bg_glow * 0.24
        hdr[:, :, 2] = bg_glow * 0.10

        # Render active world stations relative to continuous camera wy!
        self._draw_station_0_hook(hdr, t, sy_off=0.0 - wy, is_wrap=False)
        self._draw_station_1_manifesto(hdr, t, sy_off=STATION_H * 1.0 - wy)
        self._draw_station_2_diorama(hdr, t, sy_off=STATION_H * 2.0 - wy)
        self._draw_station_3_platforms(hdr, t, sy_off=STATION_H * 3.0 - wy)
        self._draw_station_4_hero_and_crest(hdr, t, sy_off=STATION_H * 4.0 - wy)
        # Periodic wrap of Station 0 at wy = 9600 for the seamless 35.20s -> 36.00s One-Shot Loop!
        if t >= 35.05:
            self._draw_station_0_hook(hdr, t, sy_off=STATION_H * 5.0 - wy, is_wrap=True)

        # Explosion shards at t=4.80s..6.20s
        self._draw_shatter_burst(hdr, t)

        # Continuous ambient embers + Guiding Golden Spark
        self._draw_ambient_embers_and_spark(hdr, t, wy)

        # Fast Multi-Scale Linear HDR Bloom (1/4 + 1/8 pyramid — identical to full-res wide blur at 8x speed!)
        # Skip double-bloom during [22.3..30.0s] where PottsfieldEngine already applied calibrated bloom
        ext_bloom_w = 1.0 - 0.78 * (smoothstep(22.2, 22.8, t) * (1.0 - smoothstep(30.0, 30.8, t)))
        if ext_bloom_w > 0.05:
            bright = np.maximum(hdr - 0.28, 0.0)
            q_w, q_h = self.w // 4, self.h // 4
            b_q = cv2.resize(bright, (q_w, q_h), interpolation=cv2.INTER_AREA)
            b1 = cv2.GaussianBlur(b_q, (0, 0), sigmaX=4.5, sigmaY=4.5)
            b2 = cv2.GaussianBlur(b_q, (0, 0), sigmaX=14.0, sigmaY=14.0)
            bloom = cv2.resize(b1 * 0.24 + b2 * 0.18, (self.w, self.h), interpolation=cv2.INTER_LINEAR)
            hdr += bloom * ext_bloom_w

        # Authentic Directional Vertical Motion Blur during high-speed camera Whip-Tilts!
        speed_px_per_frame = abs(wy_vel) / float(FPS_OS)
        if speed_px_per_frame > 18.0:
            k_len = int(np.clip(round(speed_px_per_frame * 0.42), 5, 65))
            if k_len % 2 == 0:
                k_len += 1
            kernel = np.zeros((k_len, 1), dtype=np.float32)
            kernel[:, 0] = 1.0 / k_len
            hdr = cv2.filter2D(hdr, -1, kernel, borderType=cv2.BORDER_REPLICATE)

        return linear_to_srgb_u8(aces_tonemap(hdr))


_OS_WORKER = None


def _init_os_worker(w: int, h: int):
    global _OS_WORKER
    cv2.setNumThreads(1)
    _OS_WORKER = PottsfieldOneShotEngine(w, h)


def _render_os_one(idx: int):
    rgb = _OS_WORKER.render_frame(idx / float(FPS_OS))
    return idx, rgb.tobytes()


def render_oneshot_video(out_mp4: str, poster_jpg: str, workers: int = 2):
    w, h = 1080, 1920
    os.makedirs(os.path.dirname(os.path.abspath(out_mp4)), exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{w}x{h}", "-r", str(FPS_OS),
        "-i", "pipe:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "15",
        "-pix_fmt", "yuvj420p",
        out_mp4,
    ]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    poster_idx = int(round(32.40 * FPS_OS))

    try:
        with ProcessPoolExecutor(max_workers=workers, initializer=_init_os_worker, initargs=(w, h)) as pool:
            for idx, raw_bytes in pool.map(_render_os_one, range(FRAMES_OS), chunksize=6):
                proc.stdin.write(raw_bytes)
                if poster_jpg and idx == poster_idx:
                    arr = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((h, w, 3))
                    Image.fromarray(arr).save(poster_jpg, quality=94)
                if (idx + 1) % 120 == 0 or idx + 1 == FRAMES_OS:
                    print(f"  [OneShot 1080x1920] {idx + 1}/{FRAMES_OS} frames ({time.time() - t0:.1f}s)", flush=True)
    finally:
        if proc.stdin:
            proc.stdin.close()
        rc = proc.wait()
        if rc != 0:
            sys.exit(f"ffmpeg encode failed: {rc}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", action="store_true", help="Render key storyboard stills for visual QA")
    ap.add_argument("--out-raw", default=os.path.join(HERE, "out", "video_oneshot_9x16.mp4"))
    ap.add_argument("--poster", default=os.path.join(HERE, "poster-viral-oneshot.jpg"))
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()

    if args.stills:
        eng = PottsfieldOneShotEngine(1080, 1920)
        os.makedirs("/tmp/oneshot_chk", exist_ok=True)
        sample_ts = [
            ("00_hook_f0.jpg", 0.00),
            ("01_fake_ads_zoom.jpg", 4.35),
            ("02_shatter_whip.jpg", 5.02),
            ("03_no_fake_ads.jpg", 6.20),
            ("04_gouge_slice.jpg", 7.34),
            ("05_no_brainrot.jpg", 8.40),
            ("06_stories_2d.jpg", 11.40),
            ("07_worlds_3d.jpg", 15.40),
            ("08_android_first.jpg", 18.20),
            ("09_windows_pc.jpg", 20.40),
            ("10_pumpkin_carve.jpg", 24.10),
            ("11_pumpkin_3d_drop.jpg", 26.20),
            ("12_crest_bloom.jpg", 29.30),
            ("13_end_card_cta.jpg", 32.40),
            ("14_loop_whip.jpg", 35.60),
            ("15_loop_f1079.jpg", 1079.0 / 30.0),
        ]
        t0 = time.time()
        for fname, ts in sample_ts:
            rgb = eng.render_frame(ts)
            Image.fromarray(rgb).save(f"/tmp/oneshot_chk/{fname}", quality=92)
        print(f"Rendered {len(sample_ts)} stills in {time.time() - t0:.2f}s -> /tmp/oneshot_chk/")
    else:
        render_oneshot_video(args.out_raw, args.poster, workers=args.workers)
