"""Deterministic HDR Float32 2D-Woodcut -> 3D-Volumetric -> Official-Crest Renderer for Pottsfield Studio."""
import math
import os
import numpy as np
import cv2

from timeline import FPS, DUR
from prepare_assets import HERO_IN_LOGO_SCALE, HERO_IN_LOGO_OX, HERO_IN_LOGO_OY

HERE = os.path.dirname(os.path.abspath(__file__))
NPZ_PATH = os.path.join(HERE, "work", "prepared_assets.npz")


def clamp(x, lo=0.0, hi=1.0):
    return np.clip(x, lo, hi)


def smoothstep(e0: float, e1: float, x):
    u = np.clip((x - e0) / max(e1 - e0, 1e-6), 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def smootherstep(e0: float, e1: float, x):
    u = np.clip((x - e0) / max(e1 - e0, 1e-6), 0.0, 1.0)
    return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)


def srgb_to_linear(u8_or_f: np.ndarray) -> np.ndarray:
    s = u8_or_f.astype(np.float32) / 255.0 if u8_or_f.dtype == np.uint8 else u8_or_f
    return np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4).astype(np.float32)


def linear_to_srgb_u8(lin: np.ndarray) -> np.ndarray:
    c = np.maximum(lin, 0.0)
    s = np.where(c <= 0.0031308, c * 12.92, 1.055 * (c ** (1.0 / 2.4)) - 0.055)
    return np.clip(s * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)


def aces_tonemap(hdr: np.ndarray) -> np.ndarray:
    """Brand-faithful neutral-below-shoulder HDR tonemap: preserves exact sRGB brand colors <= 0.72 while rolling HDR > 0.72 smoothly to warm cream."""
    x = np.maximum(hdr, 0.0)
    lum = 0.2126 * x[:, :, 0] + 0.7152 * x[:, :, 1] + 0.0722 * x[:, :, 2]
    # Exact 1:1 linear response below knee=0.70, smooth asymptotic shoulder toward 1.0 above knee
    knee = 0.70
    above = np.maximum(lum - knee, 0.0)
    shoulder = knee + (1.0 - knee) * (1.0 - np.exp(-above / (1.0 - knee) * 0.85))
    mapped_lum = np.where(lum <= knee, lum, shoulder)
    scale = mapped_lum / np.maximum(lum, 1e-6)
    y_luma = x * scale[:, :, None]
    # Per-channel rolloff in super-bright HDR cores (> 1.0) so white-hot flames & sparks turn golden-ivory naturally
    y_chan = 1.0 - np.exp(-x * 1.15)
    hot = np.clip((lum - 0.85) / 1.8, 0.0, 1.0)[:, :, None]
    return y_luma * (1.0 - 0.68 * hot) + y_chan * (0.68 * hot)


class PottsfieldEngine:
    def __init__(self):
        d = np.load(NPZ_PATH)
        self.S = 1254  # canonical square world resolution

        # Linear RGB base plates
        self.pump_lin = srgb_to_linear(d["pump_clean"])
        self.logo_lin = srgb_to_linear(d["logo_clean"])

        # Hero maps (1254 x 1254)
        self.hero_sil = d["hero_sil"].astype(np.float32) / 255.0
        self.hero_cav = d["hero_cav"].astype(np.float32) / 255.0
        self.hero_cav_depth = d["hero_cav_depth"].astype(np.float32) / 255.0
        self.hero_bevel = d["hero_bevel"].astype(np.float32) / 255.0
        self.woodcut_str = d["woodcut_strength"].astype(np.float32) / 255.0
        self.carve_order = d["carve_order"].astype(np.float32) / 255.0
        self.height_3d = d["height_3d"].astype(np.float32) / 255.0
        n_raw = d["hero_normals"].astype(np.float32) / 255.0 * 2.0 - 1.0
        n_len = np.sqrt(np.sum(n_raw * n_raw, axis=2, keepdims=True) + 1e-8)
        self.hero_normals = n_raw / n_len

        # Crest maps (1254 x 1254)
        self.w_hero_logo = d["w_hero_logo"].astype(np.float32) / 255.0
        self.w_potts = d["w_potts"].astype(np.float32) / 255.0
        self.potts_idx = d["potts_letter_idx"]
        self.w_studio = d["w_studio"].astype(np.float32) / 255.0
        self.studio_idx = d["studio_letter_idx"]
        self.w_ring = d["w_ring"].astype(np.float32) / 255.0
        self.ring_prog = d["ring_prog"].astype(np.float32) / 255.0
        self.w_stars = d["w_stars"].astype(np.float32) / 255.0
        self.w_wreath = d["w_wreath"].astype(np.float32) / 255.0
        self.wreath_prog = d["wreath_prog"].astype(np.float32) / 255.0
        self.side_cav = d["side_cav"].astype(np.float32) / 255.0

        # Precompute hero coordinate grids (1254 x 1254)
        yy, xx = np.mgrid[0:self.S, 0:self.S].astype(np.float32)
        self.hx = xx
        self.hy = yy
        # Normalized hero coords centered on pumpkin core (625, 720)
        self.h_nx = (xx - 625.0) / 440.0
        self.h_ny = (yy - 720.0) / 440.0
        self.h_rad = np.sqrt(self.h_nx ** 2 + self.h_ny ** 2)

        # Deterministic 3D ember & autumn leaf particles (seeded once, evaluated strictly as f(t))
        rng = np.random.default_rng(20261029)
        self.n_embers = 145
        self.emb_seed = {
            "x0": rng.uniform(-1.15, 1.15, self.n_embers).astype(np.float32),
            "y0": rng.uniform(-0.85, 1.15, self.n_embers).astype(np.float32),
            "z0": rng.uniform(-0.55, 0.72, self.n_embers).astype(np.float32),  # >0 = closer to camera (bokeh!)
            "vy": rng.uniform(0.14, 0.44, self.n_embers).astype(np.float32),
            "freq": rng.uniform(1.1, 3.4, self.n_embers).astype(np.float32),
            "phase": rng.uniform(0.0, 2 * math.pi, self.n_embers).astype(np.float32),
            "size": rng.uniform(1.8, 5.2, self.n_embers).astype(np.float32),
            "temp": rng.uniform(0.0, 1.0, self.n_embers).astype(np.float32),
            "burst": rng.uniform(0.0, 1.0, self.n_embers).astype(np.float32),
        }

        # 24 burst sparks specifically launched from the pumpkin eyes/grin at t=3.00s ignition!
        self.n_sparks = 34
        ang = rng.uniform(0, 2 * math.pi, self.n_sparks).astype(np.float32)
        spd = rng.uniform(0.32, 1.05, self.n_sparks).astype(np.float32)
        self.spk_seed = {
            "vx": np.cos(ang) * spd,
            "vy": np.sin(ang) * spd - 0.18,
            "vz": rng.uniform(-0.2, 0.55, self.n_sparks).astype(np.float32),
            "life": rng.uniform(0.65, 1.75, self.n_sparks).astype(np.float32),
            "size": rng.uniform(2.0, 4.6, self.n_sparks).astype(np.float32),
        }

        # Precompute bokeh sprite kernel cache & screen grid cache
        self._bokeh_cache = {}
        self._screen_grids = {}
        # Tight ROI around the 4 carved cavities [y: 550..990, x: 380..895] for 8x faster inner-fire turbulence
        self._cav_slice = (slice(550, 990), slice(380, 895))

    # -------------------------------------------------------------------------
    # Single World -> Screen Camera Function (DIRECTOR.md §10)
    # World space = 1254 x 1254 Official Crest coordinates!
    # In this space:
    #   Crest center = (623.0, 615.0)
    #   Docked Hero Pumpkin center (621.5, 647.5 in hero) -> (621.05, 912.58)
    # -------------------------------------------------------------------------
    def camera_state(self, t: float, W: int, H: int) -> dict:
        portrait = H > W
        # Base scale so full 1254x1254 crest fits comfortably in frame at t >= 6.0s
        if portrait:
            base_crest_px = 0.91 * W   # ~983 px on 1080x1920 -> crisp & commanding
            screen_cx = W * 0.50
            screen_cy = H * 0.492
        else:
            base_crest_px = 0.875 * H  # ~945 px on 1920x1080 -> ~78% visible ring height
            screen_cx = W * 0.50
            screen_cy = H * 0.506

        base_scale = base_crest_px / self.S  # world_px -> screen_px at zoom=1.0

        # Canonical hero center in world space
        hero_wx = HERO_IN_LOGO_OX + 621.5 * HERO_IN_LOGO_SCALE  # 621.05
        hero_wy = HERO_IN_LOGO_OY + 655.0 * HERO_IN_LOGO_SCALE  # 915.86
        stem_wx = HERO_IN_LOGO_OX + 605.0 * HERO_IN_LOGO_SCALE
        stem_wy = HERO_IN_LOGO_OY + 410.0 * HERO_IN_LOGO_SCALE

        reg_jx, reg_jy = 0.0, 0.0
        yaw_3d, pitch_3d = 0.0, 0.0

        if t < 1.00:
            # Shot 1: Macro woodcut blade tracking down stem & upper ribs
            u = smootherstep(0.0, 1.0, t)
            cam_wx = stem_wx * (1.0 - u) + hero_wx * u
            cam_wy = (stem_wy - 22.0) * (1.0 - u) + (hero_wy - 58.0) * u
            zoom = 3.85 * (1.0 - u) + 3.05 * u
        elif t < 3.00:
            # Shot 2: Hard print-plate cut to frontal Close-Up + creeping hush push-in
            frame_idx = int(round(t * FPS))
            if frame_idx == 30:
                reg_jx, reg_jy = 5.0, -3.5  # Woodcut impression registration snap!
            elif frame_idx == 31:
                reg_jx, reg_jy = -2.0, 1.5

            push = smootherstep(1.85, 2.95, t)
            antic = math.exp(-((t - 2.95) / 0.055) ** 2) * (-0.045) if t > 2.75 else 0.0
            zoom = 2.08 + 0.24 * push + antic
            # Subtle focus drift slightly toward the left eye spark at t=2.75s
            eye_pull = smootherstep(2.35, 2.92, t)
            cam_wx = hero_wx - 16.0 * eye_pull
            cam_wy = (hero_wy - 10.0) - 14.0 * eye_pull
        elif t < 4.75:
            # Shot 3: 3D Ignition recoil + dynamic 3D parallax orbit!
            dt = t - 3.00
            # Explosive punch-out from 2.28 -> 1.82 with crisp damped impact shake
            recoil = math.exp(-dt * 6.5) * 0.44
            shake = math.exp(-dt * 16.0) * math.sin(dt * 92.0) * 7.5
            reg_jx = shake * 0.8
            reg_jy = -shake * 0.6
            orbit_u = smootherstep(3.00, 4.75, t)
            zoom = 1.82 + recoil - 0.10 * orbit_u
            cam_wx = hero_wx + 12.0 * math.sin(dt * 2.1)
            cam_wy = hero_wy - 8.0 + 6.0 * math.cos(dt * 1.7)
            # True 3D normal/depth parallax angle!
            env_3d = math.sin(math.pi * clamp((t - 3.00) / 2.65, 0.0, 1.0))
            yaw_3d = 0.085 * math.sin(dt * 2.35 + 0.3) * env_3d
            pitch_3d = -0.052 * math.cos(dt * 1.85) * env_3d
        else:
            # Shot 4 & 5: Unbroken 3D crane-up & dolly pull-back onto full Crest (4.75s -> 6.05s) + living hold
            u_dock = smootherstep(4.75, 6.04, t)
            start_wx = hero_wx + 12.0 * math.sin(1.75 * 2.1)
            start_wy = hero_wy - 8.0 + 6.0 * math.cos(1.75 * 1.7)
            start_zoom = 1.72

            target_wx = 623.0
            target_wy = 615.0
            target_zoom = 1.00

            cam_wx = start_wx * (1.0 - u_dock) + target_wx * u_dock
            cam_wy = start_wy * (1.0 - u_dock) + target_wy * u_dock
            zoom = start_zoom * (1.0 - u_dock) + target_zoom * u_dock

            # Residual 3D parallax smoothly eases to 0.0 before t=5.85s
            if t < 5.85:
                dt = t - 3.00
                env_3d = (1.0 - smootherstep(4.75, 5.80, t)) * 0.55
                yaw_3d = 0.085 * math.sin(dt * 2.35 + 0.3) * env_3d
                pitch_3d = -0.052 * math.cos(dt * 1.85) * env_3d

            # Subtle throne-landing thump settle at t = 6.00s (Beat 12)
            if t >= 6.00:
                dt_lock = t - 6.00
                thump_y = math.exp(-dt_lock * 11.0) * math.sin(dt_lock * 34.0) * 4.2
                # Gentle living camera micro-drift during hold
                drift_x = math.sin(t * 1.15) * 0.85
                drift_y = math.cos(t * 0.92) * 0.85
                reg_jx += drift_x
                reg_jy += thump_y + drift_y

        scale = base_scale * zoom
        return {
            "W": W,
            "H": H,
            "portrait": portrait,
            "cam_wx": cam_wx,
            "cam_wy": cam_wy,
            "scale": scale,
            "zoom": zoom,
            "screen_cx": screen_cx + reg_jx,
            "screen_cy": screen_cy + reg_jy,
            "yaw_3d": yaw_3d,
            "pitch_3d": pitch_3d,
        }

    def world_to_screen(self, wx: float, wy: float, cam: dict) -> tuple[float, float]:
        sx = (wx - cam["cam_wx"]) * cam["scale"] + cam["screen_cx"]
        sy = (wy - cam["cam_wy"]) * cam["scale"] + cam["screen_cy"]
        return sx, sy

    # -------------------------------------------------------------------------
    # Hero Pumpkin Shader (1254 x 1254 HDR linear RGB + alpha + emissive rays)
    # -------------------------------------------------------------------------
    def shade_hero_pumpkin(self, t: float, cam: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Returns (hero_hdr_rgb, hero_alpha, emissive_ray_source_hdr) in 1254x1254 hero space."""
        S = self.S
        hdr = np.zeros((S, S, 3), dtype=np.float32)
        ray_src = np.zeros((S, S, 3), dtype=np.float32)

        # --- 1. Act I: 2D Woodcut Relief Layer (stepped on twos = 15 fps!) ---
        frame_2d = (int(math.floor(t * FPS)) // 2) * 2
        t_2d = frame_2d / FPS
        if t < 0.22:
            carve_p = 0.0
        elif t < 2.12:
            carve_p = float(smootherstep(0.22, 2.08, t_2d))
        else:
            carve_p = 1.0

        # Active woodcut strokes revealed up to carve_p
        if carve_p > 0.0 and t < 3.60:
            revealed = np.clip((carve_p - self.carve_order) / 0.035, 0.0, 1.0)
            # Subtle organic woodblock boil only during Act I
            strokes = self.woodcut_str * revealed
            # Bone-ivory woodcut print ink with warm burnt-orange burr along stroke edges
            ivory = np.array([0.88, 0.72, 0.48], dtype=np.float32)
            burr = np.array([0.85, 0.26, 0.04], dtype=np.float32)
            wood_rgb = strokes[:, :, None] * ivory + (strokes * (1.0 - strokes) * 1.8)[:, :, None] * burr

            # Bright molten gouge-knife frontier spark while actively carving (0.24s .. 2.08s)
            if 0.23 <= t <= 2.12:
                frontier = np.exp(-((self.carve_order - carve_p) / 0.022) ** 2) * (self.woodcut_str > 0.22)
                spark_col = np.array([3.4, 1.45, 0.28], dtype=np.float32)
                wood_rgb += frontier[:, :, None] * spark_col
                ray_src += frontier[:, :, None] * np.array([1.2, 0.45, 0.08], dtype=np.float32)
        else:
            wood_rgb = np.zeros_like(hdr)
            strokes = np.zeros((S, S), dtype=np.float32)

        # --- 2. Pre-Ignition Eye Spark at t = 2.75s .. 3.00s ---
        if 2.74 <= t < 3.08:
            u_spk = clamp((t - 2.74) / 0.26, 0.0, 1.0)
            # Primary spark glint in Left Eye (500, 669) + arcing ember toward Right Eye (805, 667)
            lx, ly = 500.0, 669.0
            dx, dy = self.hx - lx, self.hy - ly
            # 4-point star flare + core
            r2 = dx * dx + dy * dy + 1.0
            star = np.exp(-np.abs(dx) / 3.2) * np.exp(-np.abs(dy) / 48.0) + np.exp(-np.abs(dy) / 3.2) * np.exp(-np.abs(dx) / 48.0)
            core = 380.0 / (r2 + 28.0)
            pulse = math.sin(min(u_spk * 1.3, 1.0) * math.pi * 0.5) * (1.0 + 0.35 * math.sin(t * 55.0))
            flare = (star * 2.4 + core * 1.8) * pulse

            # Secondary mini-arc jumping to Right Eye right before t=3.00s
            if t >= 2.86:
                ua = clamp((t - 2.86) / 0.14, 0.0, 1.0)
                ax = lx * (1.0 - ua) + 805.0 * ua
                ay = 668.0 - 52.0 * math.sin(ua * math.pi)
                da2 = (self.hx - ax) ** 2 + (self.hy - ay) ** 2
                flare += (240.0 / (da2 + 24.0)) * math.sin(ua * math.pi)

            # Smooth radial window inside the 1254x1254 canvas so Lorentzian flare never hits canvas boundary!
            canvas_win = np.clip(1.0 - (self.h_rad / 1.15) ** 2, 0.0, 1.0) ** 2
            spk_hdr = (flare * canvas_win)[:, :, None] * np.array([3.8, 1.65, 0.30], dtype=np.float32)
            wood_rgb += spk_hdr
            ray_src += spk_hdr * 0.55

        # --- 3. Act II & III: 3D Normal-Mapped Pumpkin + Inner Jack-O'-Lantern Fire ---
        if t < 3.00:
            # Pure 2D woodcut silhouette on dark woodblock
            alpha = np.clip(strokes * 1.15, 0.0, 1.0)
            if 2.74 <= t:
                alpha = np.maximum(alpha, np.clip(wood_rgb.max(axis=2) * 0.6, 0.0, 1.0))
            return wood_rgb, alpha, ray_src

        # Radial 2D -> 3D transformation wave starting at t = 3.00s from core (625, 720)
        dt_ig = t - 3.00
        wave_radius = dt_ig * 3.15  # crosses entire pumpkin (h_rad ~ 1.15) in ~0.37s!
        w_3d = clamp((wave_radius - self.h_rad) / 0.16, 0.0, 1.0)
        wave_ring = np.exp(-((self.h_rad - wave_radius) / 0.085) ** 2) * (1.0 if dt_ig < 0.52 else 0.0) * self.hero_sil

        # Flicker envelope: lively flames in Act II, settling cleanly to canonical brand lockup in Act III
        flicker = 1.0 + 0.14 * math.sin(t * 17.3) * math.cos(t * 7.9) + 0.07 * math.sin(t * 29.1)
        # At t=3.0..5.1s: full dramatic 3D volumetric lantern!
        # At t=5.2..6.8s: smoothly transfers its excess fire into the blooming crest so the final logo is 100% crisp & exact!
        three_d_drama = 1.0 - smootherstep(5.15, 6.80, t)

        # Dynamic 3D key light + inner fire point light + cool midnight rim kiss
        yaw, pitch = cam["yaw_3d"], cam["pitch_3d"]
        lx = math.sin(t * 1.85) * 0.48 + yaw * 2.5
        ly = -0.24 + pitch * 2.2
        lz = 0.84
        l_norm = math.sqrt(lx * lx + ly * ly + lz * lz)
        lx, ly, lz = lx / l_norm, ly / l_norm, lz / l_norm

        N = self.hero_normals
        ndotl = np.clip(N[:, :, 0] * lx + N[:, :, 1] * ly + N[:, :, 2] * lz, 0.0, 1.0)
        # Grazing rim factor (masked strictly to orange flesh so black ink lines & stem edges stay crisp!)
        albedo = self.pump_lin
        ink_keep = np.clip(albedo.max(axis=2) * 3.2, 0.0, 1.0)
        rim = (np.clip(1.0 - N[:, :, 2], 0.0, 1.0) ** 2.4) * ink_keep
        # Blinn-Phong waxy pumpkin rind specular along curved lobes
        hx_v, hy_v, hz_v = lx * 0.5, ly * 0.5 - 0.15, lz + 0.95
        hlen = math.sqrt(hx_v * hx_v + hy_v * hy_v + hz_v * hz_v)
        ndoth = np.clip((N[:, :, 0] * hx_v + N[:, :, 1] * hy_v + N[:, :, 2] * hz_v) / max(hlen, 1e-6), 0.0, 1.0)
        spec = (ndoth ** 26.0) * 0.34 * three_d_drama * ink_keep

        # Rich 3D chiaroscuro in Act II (deep burnt-amber shadows on outer lobes, vivid lit center) -> exact 1.00 albedo in Act III!
        shade_3d = (0.24 + 1.02 * (ndotl ** 1.25)) * (flicker ** 0.30)
        shade_blend = shade_3d * three_d_drama + 1.00 * (1.0 - three_d_drama)

        flesh_hdr = albedo * shade_blend[:, :, None]
        warm_rim = rim[:, :, None] * np.array([0.75, 0.18, 0.01], dtype=np.float32) * (0.55 * three_d_drama)
        cool_kiss = (rim * np.clip(-self.h_nx * 0.6 - self.h_ny * 0.6, 0.0, 1.0))[:, :, None] * np.array([0.03, 0.06, 0.16], dtype=np.float32) * three_d_drama
        spec_hdr = spec[:, :, None] * np.array([1.0, 0.48, 0.12], dtype=np.float32) * (1.0 - self.hero_cav)[:, :, None]

        # Inner bevel bounce light around carved eyes, nose & teeth (vivid in Act II, subtle 6% living breath in Act III)
        bevel_boost = (1.55 * three_d_drama + 0.07) * flicker * ink_keep
        bevel_hdr = (self.hero_bevel * bevel_boost)[:, :, None] * np.array([1.25, 0.38, 0.02], dtype=np.float32)

        lit_pumpkin = flesh_hdr + warm_rim + cool_kiss + spec_hdr + bevel_hdr

        # --- Inner Jack-O'-Lantern Plasma Fire inside Carved Cavities (Eyes, Nose, Jagged Grin) ---
        # Blazes fiercely during Act II (3.0..5.2s) to shoot volumetric god-rays, then subsides cleanly to 0 in Act III
        # so the iconic pitch-black wicked eyes & 9 jagged teeth of the official Pottsfield logo stand out with 100% contrast!
        fire_env = three_d_drama * flicker
        if dt_ig < 0.22:
            fire_env *= 1.0 + 1.15 * (1.0 - dt_ig / 0.22)

        fx = self.h_nx[self._cav_slice] * 7.5
        fy = self.h_ny[self._cav_slice] * 7.5 + t * 5.8
        turb_roi = (
            0.50 * np.sin(fx * 2.1 + np.sin(fy * 1.7 + t * 3.1))
            + 0.30 * np.cos(fx * 4.3 - fy * 2.6 + t * 4.7)
            + 0.20 * np.sin((fx + fy) * 5.5 - t * 8.2)
        )
        cav_d_roi = self.hero_cav_depth[self._cav_slice]
        flame_roi = np.clip((cav_d_roi * 1.50 + 0.30 * turb_roi) * fire_env, 0.0, 2.3)
        edge_keep_roi = np.clip((cav_d_roi - 0.09) / 0.16, 0.0, 1.0)
        fv_roi = flame_roi * edge_keep_roi * self.hero_cav[self._cav_slice]

        cav_fire_hdr = np.zeros((S, S, 3), dtype=np.float32)
        cav_fire_hdr[self._cav_slice] = np.stack([
            fv_roi * 2.05,
            (fv_roi ** 1.55) * 0.72,
            (fv_roi ** 2.70) * 0.16,
        ], axis=2).astype(np.float32)

        full_3d_hdr = lit_pumpkin * (1.0 - self.hero_cav[:, :, None]) + cav_fire_hdr
        # Molten shock-ring strictly on the pumpkin flesh during 3.00..3.45s
        full_3d_hdr += (wave_ring * ink_keep)[:, :, None] * np.array([2.6, 0.95, 0.14], dtype=np.float32)

        # Blend 2D woodcut -> 3D lit pumpkin across w_3d
        hdr = wood_rgb * (1.0 - w_3d[:, :, None]) + full_3d_hdr * w_3d[:, :, None]
        alpha = np.clip(strokes * 1.15 * (1.0 - w_3d) + self.hero_sil * w_3d, 0.0, 1.0)

        # Emissive source for 3D volumetric god-rays: strictly from the 4 carved cavities (NO circular disc!)
        ray_power = (1.55 * three_d_drama) * flicker
        ray_src += (cav_fire_hdr * ray_power) * w_3d[:, :, None]

        # Apply true 3D heightfield parallax displacement (cv2.remap) when camera orbits in Shot 3!
        if abs(yaw) > 1e-4 or abs(pitch) > 1e-4:
            disp_x = (self.hx - yaw * self.height_3d * 135.0).astype(np.float32)
            disp_y = (self.hy - pitch * self.height_3d * 135.0).astype(np.float32)
            hdr = cv2.remap(hdr, disp_x, disp_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            alpha = cv2.remap(alpha, disp_x, disp_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            ray_src = cv2.remap(ray_src, disp_x, disp_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)

        return hdr, alpha, ray_src

    # -------------------------------------------------------------------------
    # Official Crest Bloom Shader (Act III: t >= 5.95s, 1254 x 1254 world space)
    # -------------------------------------------------------------------------
    def shade_crest_layers(self, t: float) -> tuple[np.ndarray, np.ndarray]:
        """Returns (crest_non_hero_hdr, fg_leaf_over_hero_alpha) in 1254x1254 crest space."""
        S = self.S
        if t < 5.96:
            return np.zeros((S, S, 3), dtype=np.float32), np.zeros((S, S), dtype=np.float32)

        flicker = 1.0 + 0.10 * math.sin(t * 14.2 + 0.8)

        # 1. Autumn Wreath (Vines, Maple Leaves, 4 Companion Pumpkins): blooms radially 6.00s -> 6.88s
        u_wr = smootherstep(5.98, 6.88, t)
        rev_wr = np.clip((u_wr * 1.18 - self.wreath_prog) / 0.16, 0.0, 1.0)
        edge_wr = np.exp(-((self.wreath_prog - u_wr * 1.12) / 0.055) ** 2) * (1.0 if t < 6.95 else 0.0)

        # 2. Crimson Outer Ring: sweeps from 6 o'clock -> 12 o'clock on both sides (6.04s -> 6.82s)
        u_rg = smootherstep(6.04, 6.82, t)
        rev_rg = np.clip((u_rg * 1.14 - self.ring_prog) / 0.12, 0.0, 1.0)
        edge_rg = np.exp(-((self.ring_prog - u_rg * 1.08) / 0.045) ** 2) * (1.0 if t < 6.90 else 0.0)

        # 3. Upper Stars & Moths: twinkle in 6.48s -> 7.15s
        rev_st = float(smootherstep(6.48, 7.15, t)) * np.ones((S, S), dtype=np.float32)

        # 4. "Pottsfield" 10 Gothic Letters (6.46s -> 7.22s, staggered left-to-right with blazing gold edge!)
        rev_po = np.zeros((S, S), dtype=np.float32)
        flash_po = np.zeros((S, S), dtype=np.float32)
        for idx in range(1, 11):
            t0_l = 6.46 + (idx - 1) * 0.056
            ul = float(smootherstep(t0_l, t0_l + 0.24, t))
            fl = math.exp(-((t - (t0_l + 0.11)) / 0.085) ** 2) if t >= t0_l - 0.05 else 0.0
            m = (self.potts_idx == idx)
            rev_po[m] = ul
            flash_po[m] = fl

        # 5. "S T U D I O" 6 Crimson Letters (7.10s -> 7.42s, crisp clean lock)
        rev_su = np.zeros((S, S), dtype=np.float32)
        flash_su = np.zeros((S, S), dtype=np.float32)
        for idx in range(1, 7):
            t0_s = 7.10 + (idx - 1) * 0.036
            us = float(smootherstep(t0_s, t0_s + 0.18, t))
            fs = math.exp(-((t - (t0_s + 0.08)) / 0.065) ** 2) if t >= t0_s - 0.04 else 0.0
            m = (self.studio_idx == idx)
            rev_su[m] = us
            flash_su[m] = fs

        # Combine non-hero Partition-of-Unity weights
        total_w = (
            self.w_wreath * rev_wr
            + self.w_ring * rev_rg
            + self.w_stars * rev_st
            + self.w_potts * rev_po
            + self.w_studio * rev_su
        )
        crest_hdr = self.logo_lin * total_w[:, :, None]

        # Add molten ember leading-edge sparks during reveal!
        logo_fg = np.clip(self.logo_lin.max(axis=2) * 4.0, 0.0, 1.0)
        ember_col = np.array([2.4, 0.95, 0.16], dtype=np.float32)
        crimson_col = np.array([1.9, 0.35, 0.08], dtype=np.float32)
        crest_hdr += (self.w_wreath * edge_wr * logo_fg)[:, :, None] * ember_col
        crest_hdr += (self.w_ring * edge_rg * logo_fg)[:, :, None] * crimson_col
        crest_hdr += (self.w_potts * flash_po)[:, :, None] * np.array([1.65, 0.72, 0.14], dtype=np.float32)
        crest_hdr += (self.w_studio * flash_su)[:, :, None] * np.array([1.25, 0.28, 0.10], dtype=np.float32)

        # Companion pumpkins' eyes flash warm during awakening (6.1..6.8s), then settle cleanly to pitch-black carved eyes!
        comp_glow = self.side_cav * rev_wr * (0.42 * math.exp(-max(0.0, t - 6.20) * 2.8)) * flicker
        crest_hdr += comp_glow[:, :, None] * np.array([1.15, 0.32, 0.02], dtype=np.float32)

        # Foreground maple leaf overlapping bottom-right of Hero Pumpkin reveals with wreath
        fg_over_hero = np.clip((1.0 - self.w_hero_logo) * rev_wr, 0.0, 1.0)
        return crest_hdr, fg_over_hero

    def _get_grid(self, W: int, H: int) -> tuple[np.ndarray, np.ndarray]:
        if (W, H) not in self._screen_grids:
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            self._screen_grids[(W, H)] = (xx, yy)
        return self._screen_grids[(W, H)]

    # -------------------------------------------------------------------------
    # Fast HDR Radial Volumetric God-Rays (Crepuscular Shafts)
    # -------------------------------------------------------------------------
    def volumetric_god_rays(self, ray_screen: np.ndarray, light_sx: float, light_sy: float, t: float) -> np.ndarray:
        """Multi-pass radial zoom accumulation in quarter-res float32 HDR, modulated by swirling autumn mist."""
        H, W, _ = ray_screen.shape
        qw, qh = W // 4, H // 4
        src = cv2.resize(ray_screen, (qw, qh), interpolation=cv2.INTER_AREA)
        if float(src.max()) < 1e-4:
            return np.zeros_like(ray_screen)
        # Pre-soften thin 1-px sources before radial march so crepuscular rays are 100% velvet-smooth with zero step echoes
        src = cv2.GaussianBlur(src, (0, 0), 2.2)

        cx, cy = light_sx * 0.25, light_sy * 0.25
        acc = np.zeros_like(src)
        n_steps = 18
        w_sum = 0.0
        for i in range(n_steps):
            u = (i + 0.5) / n_steps
            zoom = 1.0 + 2.25 * (u ** 1.30)
            wt = (1.0 - u) ** 1.15
            M = np.array([
                [zoom, 0.0, cx * (1.0 - zoom)],
                [0.0, zoom, cy * (1.0 - zoom)],
            ], dtype=np.float32)
            acc += cv2.warpAffine(src, M, (qw, qh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT) * wt
            w_sum += wt
        acc /= max(w_sum, 1e-6)

        gx, gy = self._get_grid(qw, qh)
        ang = np.arctan2(gy - cy, gx - cx)
        rad = np.sqrt((gx - cx) ** 2 + (gy - cy) ** 2) / max(qw, qh)
        shafts = (
            0.58
            + 0.28 * np.sin(ang * 8.0 + t * 0.90 + np.sin(rad * 5.0 - t * 1.1))
            + 0.18 * np.cos(ang * 15.0 - t * 1.40)
        )
        beam_tint = np.array([1.08, 0.68, 0.24], dtype=np.float32)
        acc *= shafts[:, :, None] * np.exp(-rad * 1.25)[:, :, None] * beam_tint[None, None, :]
        acc = cv2.GaussianBlur(acc, (0, 0), 2.4)
        return cv2.resize(acc, (W, H), interpolation=cv2.INTER_LINEAR)

    # -------------------------------------------------------------------------
    # Deterministic 3D Bokeh Ember & Spark Particle Layer
    # -------------------------------------------------------------------------
    def _bokeh_kernel(self, r_px: int) -> np.ndarray:
        r_px = max(1, min(r_px, 28))
        if r_px not in self._bokeh_cache:
            d = 2 * r_px + 1
            yy, xx = np.mgrid[-r_px:r_px + 1, -r_px:r_px + 1].astype(np.float32)
            rr = np.sqrt(xx * xx + yy * yy) / max(r_px, 1.0)
            if r_px <= 4:
                k = np.exp(-(rr * rr) * 2.2)
            else:
                # Real optical lens bokeh disc with soft rim highlight!
                disc = np.clip((1.05 - rr) * 3.5, 0.0, 1.0)
                ring = 0.68 + 0.38 * np.exp(-((rr - 0.82) / 0.22) ** 2)
                k = cv2.GaussianBlur(disc * ring, (3, 3), 0.7)
            k /= max(float(k.max()), 1e-6)
            self._bokeh_cache[r_px] = k.astype(np.float32)
        return self._bokeh_cache[r_px]

    def _splat(self, buf: np.ndarray, sx: float, sy: float, r_px: int, col: np.ndarray):
        H, W, _ = buf.shape
        ix, iy = int(round(sx)), int(round(sy))
        if ix < -r_px or ix >= W + r_px or iy < -r_px or iy >= H + r_px:
            return
        k = self._bokeh_kernel(r_px)
        x0, x1 = max(0, ix - r_px), min(W, ix + r_px + 1)
        y0, y1 = max(0, iy - r_px), min(H, iy + r_px + 1)
        kx0, kx1 = x0 - (ix - r_px), r_px * 2 + 1 - ((ix + r_px + 1) - x1)
        ky0, ky1 = y0 - (iy - r_px), r_px * 2 + 1 - ((iy + r_px + 1) - y1)
        buf[y0:y1, x0:x1] += k[ky0:ky1, kx0:kx1, None] * col[None, None, :]

    def render_3d_particles(self, buf_bg: np.ndarray, buf_fg: np.ndarray, t: float, cam: dict):
        W, H = cam["W"], cam["H"]
        span = max(W, H) * 0.55

        # Pre-ignition: only 6 faint cold dry-ash specks drifting slowly in darkness
        if t < 3.00:
            ash_vis = float(smoothstep(0.05, 0.65, t)) * (1.0 - 0.65 * float(smoothstep(2.15, 2.55, t)))
            for i in range(10):
                px = self.emb_seed["x0"][i] * 0.7 + 0.08 * math.sin(t * 0.9 + i)
                py = ((self.emb_seed["y0"][i] - t * 0.08 + 1.0) % 2.0) - 1.0
                sx = cam["screen_cx"] + px * span
                sy = cam["screen_cy"] + py * span
                col = np.array([0.14, 0.09, 0.05], dtype=np.float32) * ash_vis
                self._splat(buf_fg, sx, sy, 2, col)
            return

        # Post-ignition (t >= 3.00s): 3D rising embers with perspective parallax & optical DoF bokeh!
        dt = t - 3.00
        # At t=5.65..6.00s (Silence #2 inhale), embers subtly pull inward toward the crest center, then bloom!
        inhale = math.exp(-((t - 5.82) / 0.16) ** 2) * 0.22
        calm = 1.0 - 0.58 * float(smootherstep(6.8, 8.8, t))

        e = self.emb_seed
        for i in range(self.n_embers):
            z = e["z0"][i]
            persp = 1.0 / max(1.0 - z * 0.72, 0.28)
            # Upward buoyancy + swirling autumn eddy
            y = ((e["y0"][i] - dt * e["vy"][i] + 1.2) % 2.4) - 1.2
            x = e["x0"][i] + 0.14 * math.sin(dt * e["freq"][i] + e["phase"][i])
            if inhale > 0.001:
                x *= (1.0 - inhale)
                y *= (1.0 - inhale)

            # Parallax shift with camera 3D orbit!
            px = (x - cam["yaw_3d"] * z * 2.4) * persp
            py = (y - cam["pitch_3d"] * z * 2.4) * persp
            sx = cam["screen_cx"] + px * span
            sy = cam["screen_cy"] + py * span

            # Optical Circle-of-Confusion radius from |z| (focal plane z = 0)
            dof_blur = abs(z) * 22.0
            r_px = int(round((e["size"][i] * persp * 0.55 + dof_blur) * (min(W, H) / 1080.0)))
            # Energy conservation: large out-of-focus bokeh discs become softer & dreamier!
            inv_area = 1.0 / (1.0 + 0.16 * dof_blur * dof_blur)
            twinkle = 0.65 + 0.35 * math.sin(t * (5.0 + e["freq"][i] * 2.0) + e["phase"][i])
            gain = calm * twinkle * inv_area * float(smoothstep(3.00, 3.35, t))

            # Warm Pottsfield palette: crimson-ember -> vivid orange -> golden spark
            tp = e["temp"][i]
            col = np.array([
                1.85 * (0.7 + 0.5 * tp),
                0.58 * (0.3 + 0.9 * tp),
                0.08 * (0.1 + 1.2 * (tp ** 2)),
            ], dtype=np.float32) * gain

            target = buf_fg if z > 0.05 else buf_bg
            self._splat(target, sx, sy, r_px, col)

        # Ignition burst sparks (3.00s -> 4.80s) + Crest dock burst sparks (6.00s -> 7.40s)
        for t_burst, power, wy_off in [(3.00, 1.35, 912.0), (6.00, 0.95, 912.0)]:
            dtb = t - t_burst
            if 0.0 <= dtb < 1.80:
                bx0, by0 = self.world_to_screen(621.0, wy_off, cam)
                for k in range(self.n_sparks):
                    life = self.spk_seed["life"][k]
                    if dtb >= life:
                        continue
                    u = dtb / life
                    drag = (1.0 - math.exp(-dtb * 2.6)) / 2.6
                    sx = bx0 + self.spk_seed["vx"][k] * drag * span * 1.45
                    sy = by0 + (self.spk_seed["vy"][k] * drag - 0.22 * dtb * dtb) * span * 1.45
                    r_px = max(1, int(round(self.spk_seed["size"][k] * (1.0 - 0.5 * u))))
                    col = np.array([2.8, 1.15, 0.20], dtype=np.float32) * ((1.0 - u) ** 1.6) * power
                    self._splat(buf_fg, sx, sy, r_px, col)

    # -------------------------------------------------------------------------
    # Master Frame Render: render_frame(t, W, H) -> uint8 RGB (H, W, 3)
    # -------------------------------------------------------------------------
    def render_frame(self, t: float, W: int = 1920, H: int = 1080) -> np.ndarray:
        cam = self.camera_state(t, W, H)

        # Clean velvet black opening & closing boot handoff
        boot_in = float(smoothstep(0.00, 0.18, t))
        boot_out = 1.0 - float(smootherstep(9.45, 9.96, t))
        master_fade = boot_in * boot_out
        if master_fade <= 1e-4:
            return np.zeros((H, W, 3), dtype=np.uint8)

        frame_hdr = np.zeros((H, W, 3), dtype=np.float32)

        # 1. Subtle illuminated autumn night backdrop behind the lantern (only when fire is lit!)
        if t >= 3.00:
            amb_str = (1.0 - 0.72 * float(smootherstep(5.5, 7.2, t))) * float(smoothstep(3.00, 3.25, t))
            if amb_str > 1e-3:
                lx, ly = self.world_to_screen(621.0, 900.0, cam)
                xx, yy = self._get_grid(W, H)
                rr = np.sqrt(((xx - lx) / (max(W, H) * 0.48)) ** 2 + ((yy - ly) / (max(W, H) * 0.48)) ** 2)
                glow_bg = np.exp(-(rr ** 1.7) * 2.1) * amb_str
                frame_hdr += glow_bg[:, :, None] * np.array([0.075, 0.020, 0.005], dtype=np.float32)

        # 2. Background 3D embers (behind pumpkin & crest)
        bg_part = np.zeros_like(frame_hdr)
        fg_part = np.zeros_like(frame_hdr)
        self.render_3d_particles(bg_part, fg_part, t, cam)
        frame_hdr += bg_part

        # 3. Shade Hero Pumpkin in 1254x1254 space & warp directly to Screen via unified world->screen!
        hero_hdr, hero_alpha, hero_rays = self.shade_hero_pumpkin(t, cam)

        # Hero space -> Crest World space -> Screen space single combined affine matrix!
        # wx = HERO_IN_LOGO_OX + hx * HERO_IN_LOGO_SCALE
        # sx = (wx - cam_wx) * scale + screen_cx
        sc_hero = HERO_IN_LOGO_SCALE * cam["scale"]
        tx_hero = (HERO_IN_LOGO_OX - cam["cam_wx"]) * cam["scale"] + cam["screen_cx"]
        ty_hero = (HERO_IN_LOGO_OY - cam["cam_wy"]) * cam["scale"] + cam["screen_cy"]
        M_hero_screen = np.array([
            [sc_hero, 0.0, tx_hero],
            [0.0, sc_hero, ty_hero],
        ], dtype=np.float32)

        interp_flag = cv2.INTER_AREA if sc_hero < 0.95 else cv2.INTER_LINEAR

        # 4. Shade Official Crest non-hero layers in 1254x1254 world space & warp to screen
        if t >= 5.96:
            crest_hdr, fg_leaf_over_hero = self.shade_crest_layers(t)
            M_world_screen = np.array([
                [cam["scale"], 0.0, -cam["cam_wx"] * cam["scale"] + cam["screen_cx"]],
                [0.0, cam["scale"], -cam["cam_wy"] * cam["scale"] + cam["screen_cy"]],
            ], dtype=np.float32)
            w_flag = cv2.INTER_AREA if cam["scale"] < 0.95 else cv2.INTER_LINEAR
            crest_scr = cv2.warpAffine(crest_hdr, M_world_screen, (W, H), flags=w_flag, borderMode=cv2.BORDER_CONSTANT)
            fg_leaf_scr = cv2.warpAffine(fg_leaf_over_hero, M_world_screen, (W, H), flags=w_flag, borderMode=cv2.BORDER_CONSTANT)
            # Subtle organic autumn-magic ripple at t = 6.00..6.75s
            if t < 6.75:
                dt_l = t - 6.00
                if dt_l >= 0.0:
                    lx, ly = self.world_to_screen(621.0, 912.0, cam)
                    xx, yy = self._get_grid(W, H)
                    r_px = np.sqrt((xx - lx) ** 2 + (yy - ly) ** 2) / (min(W, H) * 0.5)
                    ang_s = np.arctan2(yy - ly, xx - lx)
                    wisp = 0.55 + 0.45 * np.sin(ang_s * 5.0 + dt_l * 3.0)
                    ring_r = dt_l * 1.55
                    shock = np.exp(-((r_px - ring_r) / 0.11) ** 2) * math.exp(-dt_l * 4.5) * wisp
                    frame_hdr += shock[:, :, None] * np.array([0.22, 0.06, 0.005], dtype=np.float32)
        else:
            crest_scr = None
            fg_leaf_scr = None

        hero_scr_hdr = cv2.warpAffine(hero_hdr, M_hero_screen, (W, H), flags=interp_flag, borderMode=cv2.BORDER_CONSTANT)
        hero_scr_a = cv2.warpAffine(hero_alpha, M_hero_screen, (W, H), flags=interp_flag, borderMode=cv2.BORDER_CONSTANT)
        rays_scr_src = cv2.warpAffine(hero_rays, M_hero_screen, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

        # Composite order:
        #   Background + Crest behind hero -> Hero Pumpkin -> Foreground crimson leaf tip overlapping hero -> Volumetric God-Rays + Bloom + FG Bokeh!
        if crest_scr is not None:
            # Crest wreath behind hero + Hero Pumpkin on top + Foreground crimson leaf tip seamlessly over lower-right rim!
            frame_hdr += crest_scr * (1.0 - hero_scr_a[:, :, None] * (1.0 - fg_leaf_scr[:, :, None]))
            hero_vis_a = hero_scr_a * (1.0 - fg_leaf_scr)
            frame_hdr = frame_hdr * (1.0 - hero_vis_a[:, :, None]) + hero_scr_hdr * hero_vis_a[:, :, None]
        else:
            frame_hdr = frame_hdr * (1.0 - hero_scr_a[:, :, None]) + hero_scr_hdr

        # 5. Add 3D Volumetric God-Rays streaming from the Pumpkin's core!
        light_sx, light_sy = self.world_to_screen(621.0, 905.0, cam)
        god_rays = self.volumetric_god_rays(rays_scr_src, light_sx, light_sy, t)
        frame_hdr += god_rays * 0.88

        # 6. Soft Optical HDR Bloom (dual-octave Gaussian glow on highlights > 0.65)
        bright = np.maximum(frame_hdr - 0.55, 0.0)
        b_small = cv2.GaussianBlur(bright, (0, 0), sigmaX=min(W, H) * 0.012)
        b_wide = cv2.GaussianBlur(cv2.resize(bright, (W // 4, H // 4), interpolation=cv2.INTER_AREA), (0, 0), sigmaX=7.5)
        b_wide = cv2.resize(b_wide, (W, H), interpolation=cv2.INTER_LINEAR)
        bloom_amt = 0.28 if t < 6.5 else 0.14  # cleaner crisp brand lockup in Act III
        frame_hdr += b_small * bloom_amt + b_wide * (bloom_amt * 0.85)

        # 7. Foreground 3D Bokeh Embers (passing in front of lens!)
        frame_hdr += fg_part

        # 8. Master Boot Fade & ACES Filmic Tone-Mapping -> sRGB uint8
        frame_hdr *= master_fade
        ldr_lin = aces_tonemap(frame_hdr)
        return linear_to_srgb_u8(ldr_lin)
