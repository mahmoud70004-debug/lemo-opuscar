"""Preprocess Pottsfield Studio artwork into exact 2D woodcut, 3D normal/height, cavity, and crest layers."""
import os
import numpy as np
from PIL import Image
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(HERE, "assets")
WORK_DIR = os.path.join(HERE, "work")

# Exact canonical transform mapping 1254x1254 pumpkin_hero canvas into 1254x1254 logo_full canvas
HERO_IN_LOGO_SCALE = 0.4365
HERO_IN_LOGO_OX = 349.76
HERO_IN_LOGO_OY = 629.95


def prepare():
    os.makedirs(WORK_DIR, exist_ok=True)
    pump_u8 = np.array(Image.open(os.path.join(ASSETS_DIR, "pumpkin_hero.png")).convert("RGB"))
    logo_u8 = np.array(Image.open(os.path.join(ASSETS_DIR, "logo_full.png")).convert("RGB"))
    H, W, _ = pump_u8.shape  # 1254 x 1254

    # Clean tiny background compression noise (< 8/255 in pure black corners)
    pump_clean = pump_u8.astype(np.float32)
    pump_lum = pump_clean.max(axis=2)
    bg_soft = np.clip((pump_lum - 8.0) / 14.0, 0.0, 1.0)

    # 1. Exact outer silhouette of Hero Pumpkin (solid inside, including dark eyes/mouth/grooves)
    binary = (pump_lum > 24).astype(np.uint8) * 255
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
    ff = closed.copy()
    cv2.floodFill(ff, np.zeros((H + 2, W + 2), np.uint8), (0, 0), 128)
    sil_raw = (ff != 128).astype(np.float32)
    hero_sil = cv2.GaussianBlur(sil_raw, (5, 5), 0.9)
    # Zero out exterior noise
    pump_clean *= np.clip(hero_sil * 1.4, 0.0, 1.0)[:, :, None]

    # 2. Extract exact 4 jack-o'-lantern carved cavities (Left Eye, Right Eye, Nose, Mouth)
    dark_in_sil = ((sil_raw > 0.5) & (pump_lum < 40)).astype(np.uint8)
    seeds = cv2.erode(dark_in_sil, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    n_cc, cc_labels, cc_stats, cc_cent = cv2.connectedComponentsWithStats(seeds)

    cav_seeds = np.zeros((H, W), dtype=np.uint8)
    cav_boxes = {}
    for cid in range(1, n_cc):
        area = cc_stats[cid, cv2.CC_STAT_AREA]
        cx, cy = cc_cent[cid]
        if area > 1200 and cy > 540:  # excludes stem collar shadow near y~421
            if cy < 720 and cx < 630:
                name = "left_eye"
            elif cy < 720 and cx >= 630:
                name = "right_eye"
            elif cy < 810:
                name = "nose"
            else:
                name = "mouth"
            cav_seeds[cc_labels == cid] = 255
            cav_boxes[name] = (float(cx), float(cy))

    # Geodesic dilation inside dark_in_sil so cavities fill cleanly right up to the orange bevel edge
    cav_mask_u8 = cav_seeds.copy()
    k_dil = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    for _ in range(18):
        nxt = cv2.dilate(cav_mask_u8, k_dil) & (dark_in_sil * 255)
        if np.array_equal(nxt, cav_mask_u8):
            break
        cav_mask_u8 = nxt

    hero_cav = cv2.GaussianBlur(cav_mask_u8.astype(np.float32) / 255.0, (5, 5), 0.8)
    cav_dist_px = cv2.distanceTransform((cav_mask_u8 > 127).astype(np.uint8), cv2.DIST_L2, 5)
    hero_cav_depth = np.clip(cav_dist_px / 38.0, 0.0, 1.0).astype(np.float32)

    # Inner bevel rim mask: orange pixels within ~18 px outside the carved cavities catch intense bounce light!
    outside_cav_dist = cv2.distanceTransform((cav_mask_u8 == 0).astype(np.uint8), cv2.DIST_L2, 5)
    flesh_mask = np.clip(hero_sil - hero_cav, 0.0, 1.0)
    orange_vivid = np.clip((pump_clean[:, :, 0] - 50.0) / 180.0, 0.0, 1.0)
    hero_bevel = (np.exp(-outside_cav_dist / 10.5) * flesh_mask * orange_vivid).astype(np.float32)

    # 3. 2D Woodcut Relief Stroke Field & Progressive Carve Order
    # Combine: (a) outer silhouette knife contour, (b) cavity rim knife contour, (c) interior artist ink grooves
    sil_edge = cv2.morphologyEx(sil_raw, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    cav_edge = cv2.morphologyEx((cav_mask_u8 > 127).astype(np.float32), cv2.MORPH_GRADIENT,
                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    # Interior ink grooves: inside flesh_mask where luminance drops below surrounding orange
    local_max = cv2.dilate(pump_lum, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    ink_grooves = np.clip((local_max - pump_lum) / 145.0, 0.0, 1.0) * flesh_mask * (1.0 - hero_cav)
    woodcut_strength = np.clip(np.maximum(np.maximum(sil_edge * 0.95, cav_edge * 1.0), ink_grooves * 0.92), 0.0, 1.0)
    woodcut_strength = cv2.GaussianBlur(woodcut_strength, (3, 3), 0.5).astype(np.float32)

    # Carve progression order P(x, y) in [0, 1]:
    # Stem & crown first (y=204..520) -> ribs & eyes (y=520..780) -> wicked jagged grin & base (y=780..1091)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    y_norm = np.clip((yy - 204.0) / (1091.0 - 204.0), 0.0, 1.0)
    x_sym = np.abs(xx - 621.5) / 440.0
    # Slight organic angular sweep so strokes travel down ribs and outward from brow/mouth center
    carve_order = np.clip(0.76 * y_norm + 0.24 * x_sym, 0.0, 1.0)
    # Make cavities' sharp rims carve briskly in two crisp gestures (eyes at ~0.52..0.68, grin at ~0.72..0.94)
    is_eye_zone = (yy > 555) & (yy < 745) & (np.abs(xx - 650) < 260) & (cav_edge > 0.15)
    is_grin_zone = (yy >= 745) & (yy < 995) & (cav_edge > 0.15)
    carve_order = np.where(is_eye_zone, 0.50 + 0.18 * x_sym, carve_order)
    carve_order = np.where(is_grin_zone, 0.72 + 0.24 * (np.abs(xx - 633.0) / 260.0), carve_order).astype(np.float32)

    # 4. Sculpted 3D Heightfield & Surface Normal Map for Act II-III 3D Lighting & Parallax
    dist_in_sil = cv2.distanceTransform((sil_raw > 0.5).astype(np.uint8), cv2.DIST_L2, 5)
    d_norm = np.clip(dist_in_sil / (dist_in_sil.max() + 1e-6), 0.0, 1.0)
    # Spherical dome profile: steep near rim, full volume in center
    dome = np.sqrt(np.clip(1.0 - (1.0 - np.clip(d_norm * 1.35, 0.0, 1.0)) ** 2, 0.0, 1.0))
    dome = cv2.GaussianBlur(dome, (31, 31), 9.0)
    # Indent along real vertical pumpkin rib creases for authentic 3D lobes
    groove_blur = cv2.GaussianBlur(ink_grooves, (21, 21), 5.5)
    rib_relief = dome * (1.0 - 0.24 * groove_blur)
    # Recess carved cavities into the shell with beveled walls
    cav_recess = cv2.GaussianBlur(hero_cav, (13, 13), 3.2)
    unmasked_h = rib_relief * (1.0 - 0.78 * cav_recess)
    height_3d = (unmasked_h * hero_sil).astype(np.float32)

    # Compute normals from interior heightfield attenuated near silhouette edge so stem/rim have zero step-cliff halo
    inner_fade = cv2.erode(sil_raw, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
    inner_fade = cv2.GaussianBlur(inner_fade, (15, 15), 4.0)
    gx = cv2.Sobel(unmasked_h, cv2.CV_32F, 1, 0, ksize=5) * 2.4 * inner_fade
    gy = cv2.Sobel(unmasked_h, cv2.CV_32F, 0, 1, ksize=5) * 2.4 * inner_fade
    # Add smooth spherical X/Y tilt across the whole pumpkin dome for rich 3D lighting!
    dome_nx = np.clip((xx - 621.5) / 430.0, -0.88, 0.88) * hero_sil
    dome_ny = np.clip((yy - 675.0) / 445.0, -0.88, 0.88) * hero_sil
    nx = -gx + dome_nx * 0.72
    ny = -gy + dome_ny * 0.65
    nz = np.sqrt(np.maximum(1.0 - np.clip(nx * nx + ny * ny, 0.0, 0.92), 0.08))
    n_len = np.sqrt(nx * nx + ny * ny + nz * nz + 1e-8)
    hero_normals = np.stack([nx / n_len, ny / n_len, nz / n_len], axis=2).astype(np.float32)

    # =========================================================================
    # 5. Partition-of-Unity Semantic Decomposition of Official Crest (logo_full)
    # =========================================================================
    logo_clean = logo_u8.astype(np.float32)
    logo_lum = logo_clean.max(axis=2)
    logo_fg = logo_lum > 12.0
    logo_clean *= np.clip((logo_lum - 7.0) / 12.0, 0.0, 1.0)[:, :, None]

    # Map hero_sil into logo_full canvas via exact affine warp
    M_hero_to_logo = np.array([
        [HERO_IN_LOGO_SCALE, 0.0, HERO_IN_LOGO_OX],
        [0.0, HERO_IN_LOGO_SCALE, HERO_IN_LOGO_OY],
    ], dtype=np.float32)
    hero_sil_in_logo = cv2.warpAffine(hero_sil, M_hero_to_logo, (W, H), flags=cv2.INTER_AREA)

    R, G, B = logo_clean[:, :, 0], logo_clean[:, :, 1], logo_clean[:, :, 2]

    # Detect foreground crimson maple leaf overlapping lower-right of Hero Pumpkin in logo_full
    is_crimson_over_hero = (hero_sil_in_logo > 0.2) & (R > 75.0) & (G < 0.34 * R) & (yy > 980) & (xx > 740)
    fg_leaf_mask = cv2.GaussianBlur(
        cv2.dilate(is_crimson_over_hero.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))).astype(np.float32),
        (5, 5), 0.8
    )
    w_hero_logo = np.clip(hero_sil_in_logo * (1.0 - fg_leaf_mask), 0.0, 1.0)

    # Extract 10 exact letters of "Pottsfield" (bright orange in upper half, area > 4000)
    is_orange = (R > 135) & (G > 48) & (R > 1.42 * G) & (G > 1.55 * B)
    n_o, lab_o, stat_o, cent_o = cv2.connectedComponentsWithStats(is_orange.astype(np.uint8))
    potts_comps = []
    for i in range(1, n_o):
        area = stat_o[i, cv2.CC_STAT_AREA]
        cx, cy = cent_o[i]
        if cy < 480 and area > 4000:
            potts_comps.append((cx, i))
    potts_comps.sort(key=lambda t: t[0])
    assert len(potts_comps) == 10, f"Expected 10 Pottsfield letter components, got {len(potts_comps)}"

    potts_raw = np.zeros((H, W), dtype=np.uint8)
    potts_letter_idx = np.zeros((H, W), dtype=np.uint8)
    for rank, (_, cid) in enumerate(potts_comps, start=1):
        m = (lab_o == cid)
        # Dilate by 2px within non-black foreground to capture anti-aliased edge pixels cleanly
        m_dil = cv2.dilate(m.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))) > 0
        m_dil = m_dil & logo_fg & (potts_letter_idx == 0)
        potts_raw[m_dil] = 255
        potts_letter_idx[m_dil] = rank
    w_potts = cv2.GaussianBlur(potts_raw.astype(np.float32) / 255.0, (3, 3), 0.45)

    # Extract 6 exact letters of "S T U D I O" inside [415:855, 520:605]
    studio_box = np.zeros((H, W), dtype=np.uint8)
    studio_box[520:605, 415:855] = logo_fg[520:605, 415:855].astype(np.uint8)
    n_s, lab_s, stat_s, cent_s = cv2.connectedComponentsWithStats(studio_box)
    studio_comps = []
    for i in range(1, n_s):
        if stat_s[i, cv2.CC_STAT_AREA] > 400:
            studio_comps.append((cent_s[i][0], i))
    studio_comps.sort(key=lambda t: t[0])
    assert len(studio_comps) == 6, f"Expected 6 STUDIO letters, got {len(studio_comps)}"

    studio_raw = np.zeros((H, W), dtype=np.uint8)
    studio_letter_idx = np.zeros((H, W), dtype=np.uint8)
    for rank, (_, cid) in enumerate(studio_comps, start=1):
        m = cv2.dilate((lab_s == cid).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))) > 0
        m = m & logo_fg & (studio_letter_idx == 0)
        studio_raw[m] = 255
        studio_letter_idx[m] = rank
    w_studio = cv2.GaussianBlur(studio_raw.astype(np.float32) / 255.0, (3, 3), 0.45)

    # Outer crimson ring: elliptical band around (623, 615) with rx=515, ry=538
    ex = (xx - 623.0) / 515.0
    ey = (yy - 615.0) / 538.0
    rho = np.sqrt(ex * ex + ey * ey)
    ring_band = np.exp(-((rho - 0.996) / 0.020) ** 4)
    # Keep only crimson ring pixels (exclude bright orange leaves where G > 0.36 * R, and bottom wreath foliage)
    is_crimson_tone = np.clip((0.38 * R - G) / 25.0, 0.0, 1.0)
    w_ring = np.clip(ring_band * is_crimson_tone * (1.0 - w_potts) * (1.0 - w_studio) * (1.0 - w_hero_logo), 0.0, 1.0).astype(np.float32)
    # Angular sweep from bottom (6 o'clock = 0.0) up both sides to top (12 o'clock = 1.0)
    theta_from_bottom = np.abs(np.arctan2(ex, ey)) / np.pi  # ey>0 is bottom (theta=0), ey<0 is top (theta=1)
    ring_prog = np.clip(theta_from_bottom, 0.0, 1.0).astype(np.float32)

    # Upper inner stars & moths (inside ring, y < 545, excluding Pottsfield & STUDIO)
    upper_sky = np.clip((545.0 - yy) / 25.0, 0.0, 1.0) * np.clip((0.965 - rho) / 0.02, 0.0, 1.0)
    w_stars = np.clip(upper_sky * (1.0 - w_potts) * (1.0 - w_studio) * (1.0 - w_ring), 0.0, 1.0).astype(np.float32)

    # Remaining Partition-of-Unity weight = Autumn Wreath (Vines, Maple Leaves, 4 Companion Pumpkins)!
    used = np.clip(w_hero_logo + w_potts + w_studio + w_ring + w_stars, 0.0, 1.0)
    w_wreath = np.clip(1.0 - used, 0.0, 1.0).astype(np.float32)

    # Radial outward bloom distance from Hero Pumpkin center in logo (621.0, 912.6)
    rad_from_hero = np.sqrt((xx - 621.0) ** 2 + ((yy - 912.6) * 1.05) ** 2)
    wreath_prog = np.clip((rad_from_hero - 135.0) / 430.0, 0.0, 1.0).astype(np.float32)

    # Companion pumpkins' eye/mouth cavities so they also softly flicker with inner candle warmth in Act III!
    comp_centers = [(348, 892, 95), (408, 1018, 52), (898, 775, 82), (890, 938, 75)]
    side_cav = np.zeros((H, W), dtype=np.float32)
    for cx_c, cy_c, rad_c in comp_centers:
        in_p = ((xx - cx_c) ** 2 + (yy - cy_c) ** 2) < (rad_c * 0.72) ** 2
        dark_c = in_p & (logo_lum < 34.0) & (w_hero_logo < 0.1)
        # Keep cavities > 35 px so rib lines aren't mistaken for eyes
        nc, lc, sc, _ = cv2.connectedComponentsWithStats(dark_c.astype(np.uint8))
        for k in range(1, nc):
            if sc[k, cv2.CC_STAT_AREA] > 45:
                side_cav[lc == k] = 1.0
    side_cav = cv2.GaussianBlur(side_cav, (5, 5), 0.9).astype(np.float32)

    out_npz = os.path.join(WORK_DIR, "prepared_assets.npz")
    np.savez_compressed(
        out_npz,
        pump_clean=pump_clean.astype(np.uint8),
        hero_sil=(hero_sil * 255).astype(np.uint8),
        hero_cav=(hero_cav * 255).astype(np.uint8),
        hero_cav_depth=(hero_cav_depth * 255).astype(np.uint8),
        hero_bevel=(hero_bevel * 255).astype(np.uint8),
        woodcut_strength=(woodcut_strength * 255).astype(np.uint8),
        carve_order=(carve_order * 255).astype(np.uint8),
        height_3d=(height_3d * 255).astype(np.uint8),
        hero_normals=((hero_normals * 0.5 + 0.5) * 255).astype(np.uint8),
        logo_clean=logo_clean.astype(np.uint8),
        w_hero_logo=(w_hero_logo * 255).astype(np.uint8),
        w_potts=(w_potts * 255).astype(np.uint8),
        potts_letter_idx=potts_letter_idx,
        w_studio=(w_studio * 255).astype(np.uint8),
        studio_letter_idx=studio_letter_idx,
        w_ring=(w_ring * 255).astype(np.uint8),
        ring_prog=(ring_prog * 255).astype(np.uint8),
        w_stars=(w_stars * 255).astype(np.uint8),
        w_wreath=(w_wreath * 255).astype(np.uint8),
        wreath_prog=(wreath_prog * 255).astype(np.uint8),
        side_cav=(side_cav * 255).astype(np.uint8),
    )
    print(f"Prepared assets saved -> {out_npz} ({os.path.getsize(out_npz)/1e6:.2f} MB)")
    print("Hero cavities:", cav_boxes)
    # Check partition-of-unity exact reconstruction error on non-hero crest
    sum_w = w_hero_logo + w_potts + w_studio + w_ring + w_stars + w_wreath
    print(f"Partition-of-unity sum min={sum_w.min():.5f}, max={sum_w.max():.5f}")


if __name__ == "__main__":
    prepare()
