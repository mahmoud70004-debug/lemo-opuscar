"""Procedural Score, Foley & Stereo Mix for Pottsfield Studio Official 10s Intro."""
import json
import math
import os
import sys
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, fftconvolve

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.environ.get("LIB", os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.insert(0, LIB)
sys.path.insert(0, HERE)

from core.audio import sfx
from core.audio import pluck as P
from timeline import DUR, CUES, SILENCES

SR = sfx.SR  # 48000 Hz
RNG = np.random.default_rng(20261031)


# =============================================================================
# Custom Physical & Atmospheric Synthesizers
# =============================================================================
def stereo_reverb_ir(rt60: float = 1.85, dur: float = 2.4) -> tuple[np.ndarray, np.ndarray]:
    """Warm wooden-hall / autumn-clearing stereo impulse response."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    decay = np.exp(-6.91 * t / rt60)
    # Early reflections + diffuse velvet tail, high-damped so treble melts warmly
    ir_l = RNG.standard_normal(n) * decay
    ir_r = RNG.standard_normal(n) * decay
    # Early wood reflections (8..55 ms)
    for ms, g, side in [(11, 0.55, 0), (17, 0.48, 1), (26, 0.38, 0), (34, 0.34, 1), (47, 0.25, 0)]:
        idx = int(ms * 0.001 * SR)
        if idx < n:
            if side == 0:
                ir_l[idx] += g
            else:
                ir_r[idx] += g
    sos_lp = butter(2, 3400, "low", fs=SR, output="sos")
    sos_hp = butter(2, 135, "high", fs=SR, output="sos")
    ir_l = sosfilt(sos_hp, sosfilt(sos_lp, ir_l))
    ir_r = sosfilt(sos_hp, sosfilt(sos_lp, ir_r))
    # Smooth 4ms attack so dry transients stay punchy
    att = min(int(0.004 * SR), n)
    ir_l[:att] *= np.linspace(0, 1, att)
    ir_r[:att] *= np.linspace(0, 1, att)
    norm = max(np.sqrt(np.sum(ir_l ** 2)), 1e-6)
    return (ir_l / norm).astype(np.float32), (ir_r / norm).astype(np.float32)


def bowed_cello(pitch: str, dur: float, vel: float = 0.7, att: float = 0.28, rel: float = 0.55) -> np.ndarray:
    """Warm bowed cello/contrabass with rosin bow friction, subtle vibrato, and wooden body formants."""
    f0 = P._hz(P.midi(pitch))
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    # Natural delayed vibrato
    vib_env = np.clip((t - 0.25) / 0.45, 0.0, 1.0)
    f_inst = f0 * (2.0 ** ((0.11 * vib_env * np.sin(2 * np.pi * 5.1 * t)) / 12.0))
    phase = 2 * np.pi * np.cumsum(f_inst) / SR

    # Rich odd+even bowed string harmonic series (softened upper harmonics, warm 2nd & 3rd so small speakers sing!)
    sig = np.zeros(n, dtype=np.float64)
    for k in range(1, 14):
        if k * f0 >= SR * 0.42:
            break
        amp = (1.0 / (k ** 1.22)) * (1.25 if k in (2, 3) else 1.0)
        det = np.sin(phase * k + 0.08 * np.sin(2 * np.pi * (1.3 + 0.4 * k) * t))
        sig += amp * det

    # Subtle rosin bow hair breath
    rosin = sfx.bp(RNG.standard_normal(n), max(400, f0 * 3), min(4200, f0 * 16), 2) * 0.045
    sig = sig + rosin

    # Cello wooden body resonances
    body = (
        0.55 * sfx.bp(sig, 95, 220, 2)
        + 0.45 * sfx.bp(sig, 220, 520, 2)
        + 0.25 * sfx.bp(sig, 520, 1250, 2)
    )
    sig = 0.45 * sfx.lp(sig, 1800, 2) + 0.55 * body

    # Smooth bow envelope
    env = np.ones(n, dtype=np.float64)
    na = max(1, int(att * SR))
    nd = int(dur * SR)
    nr = n - nd
    env[:na] = 0.5 * (1.0 - np.cos(np.pi * np.arange(na) / na))
    if nr > 0:
        env[nd:] = np.exp(-5.2 * np.arange(nr) / max(nr, 1)) * np.linspace(1.0, 0.0, nr)
    return (sfx.norm(sig * env) * vel).astype(np.float32)


def woodcut_gouge_foley(dur: float = 0.36, speed: float = 1.0, v: float = 1.0) -> np.ndarray:
    """Woodcut knife gouging end-grain block: sharp blade bite + fibrous wood-grain tearing + chip ticks."""
    tt = sfx.t_(dur)
    n = len(tt)
    # Initial chisel bite
    bite = sfx.hp(sfx.noise(dur), 2100) * sfx.env_exp(dur, 0.008) * 0.85
    # Fibrous wood-grain scrape (band-passed noise modulated by grain ridges at ~55*speed Hz)
    grain_mod = (0.45 + 0.55 * np.abs(np.sin(2 * np.pi * 52.0 * speed * tt + 0.4 * np.sin(2 * np.pi * 9 * tt)))) ** 1.8
    env = np.sin(np.pi * tt / dur) ** 0.75
    scrape = sfx.bp(sfx.noise(dur), 850, 3900, 2) * grain_mod * env
    wood_body = sfx.bp(sfx.noise(dur), 260, 680, 2) * env * 0.45
    out = bite + scrape + wood_body
    # 2 tiny flying wood-chip ticks near the end of the stroke
    for frac in (0.62, 0.84):
        idx = int(frac * n)
        ck = sfx.click(pitch=1.35 + 0.2 * speed, v=0.35)
        e = min(n, idx + len(ck))
        out[idx:e] += ck[:e - idx]
    return (sfx.norm(out) * v).astype(np.float32)


def leaf_rustle_foley(dur: float = 0.45, v: float = 1.0) -> np.ndarray:
    """Crisp dry autumn maple leaves fluttering."""
    tt = sfx.t_(dur)
    crisp = sfx.bp(sfx.noise(dur), 2400, 8500, 2)
    flutter = (np.abs(np.sin(2 * np.pi * 19.0 * tt + RNG.random() * 3.0)) ** 3.2)
    env = np.sin(np.pi * tt / dur) ** 1.2
    return (sfx.norm(crisp * flutter * env) * v).astype(np.float32)


def flint_spark_and_arc(v: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Crisp spark snap in Left Eye (2.75s) + tiny sizzling ember zip across to Right Eye."""
    d1 = 0.16
    tt = sfx.t_(d1)
    snap = sfx.hp(sfx.noise(d1), 3500) * sfx.env_exp(d1, 0.003)
    ping = (
        np.sin(2 * np.pi * 3520 * tt) * sfx.env_exp(d1, 0.035) * 0.6
        + np.sin(2 * np.pi * 5840 * tt) * sfx.env_exp(d1, 0.018) * 0.4
    )
    spark = (sfx.norm(snap + ping) * v).astype(np.float32)

    d2 = 0.14
    t2 = sfx.t_(d2)
    sizzle = sfx.bp(sfx.noise(d2), 3200, 9500, 2) * np.sin(np.pi * t2 / d2)
    return spark, (sfx.norm(sizzle) * v * 0.45).astype(np.float32)


def hearth_ignition_boom(v: float = 1.0) -> np.ndarray:
    """Deep cinematic jack-o'-lantern fire eruption: tight sub punch + warm flame FWOOSH + resin crackles."""
    d = 1.35
    tt = sfx.t_(d)
    # Controlled punchy warm body (58 -> 38 Hz, short decay so low-end stays tight & balanced!)
    punch = np.sin(2 * np.pi * (58.0 - 16.0 * tt) * tt) * sfx.env_exp(d, 0.19) * 0.62
    harm2 = np.sin(2 * np.pi * (116.0 - 32.0 * tt) * tt) * sfx.env_exp(d, 0.15) * 0.42
    # Swept warm flame whoosh (180 -> 1400 -> 450 Hz)
    rush_lo = sfx.bp(sfx.noise(d), 140, 620, 2) * np.exp(-tt / 0.42) * np.minimum(1.0, tt / 0.025)
    rush_hi = sfx.bp(sfx.noise(d), 650, 2800, 2) * np.exp(-tt / 0.24) * np.minimum(1.0, tt / 0.012) * 0.75
    # Pine-resin micro crackles
    crackle = sfx.hp(sfx.noise(d), 3200) * (RNG.random(len(tt)) > 0.992) * np.exp(-tt / 0.65) * 1.4
    return (sfx.norm(punch + harm2 + rush_lo + rush_hi + crackle) * v).astype(np.float32)


def reverse_inhale_shimmer(dur: float = 0.33, v: float = 1.0) -> np.ndarray:
    """Soft reverse-ember harmonic air pulling inward right before Beat 12 (t=6.00s) crest bloom."""
    tt = sfx.t_(dur)
    ramp = (tt / dur) ** 2.4
    air = sfx.bp(sfx.noise(dur), 700, 3600, 2) * ramp * 0.45
    # Soft D5 + A5 harmonicair swell
    tones = (np.sin(2 * np.pi * 587.33 * tt) + 0.6 * np.sin(2 * np.pi * 880.0 * tt)) * ramp * 0.55
    out = air + tones
    out[-192:] *= np.linspace(1.0, 0.0, 192)
    return (sfx.norm(out) * v).astype(np.float32)


def golden_title_shimmer(dur: float = 0.78, v: float = 1.0) -> np.ndarray:
    """Warm ember-sparkle brush sweeping across 'Pottsfield'."""
    tt = sfx.t_(dur)
    env = np.sin(np.pi * tt / dur) ** 0.9
    fizz = sfx.bp(sfx.noise(dur), 2600, 8200, 2) * (0.4 + 0.6 * (RNG.random(len(tt)) > 0.96)) * env * 0.45
    glow = (
        np.sin(2 * np.pi * 1174.66 * tt) * 0.5
        + np.sin(2 * np.pi * 1760.00 * tt) * 0.35
        + np.sin(2 * np.pi * 1479.98 * tt) * 0.30
    ) * env * 0.35
    return (sfx.norm(fizz + glow) * v).astype(np.float32)


# =============================================================================
# Build Full Stem-Separated Mix & Verify Cue Alignment
# =============================================================================
def build_mix():
    n_total = int(round(DUR * SR))
    amb_bus = np.zeros((n_total, 2), dtype=np.float32)
    fol_bus = np.zeros((n_total, 2), dtype=np.float32)
    mus_dry = np.zeros((n_total, 2), dtype=np.float32)
    mus_send = np.zeros((n_total, 2), dtype=np.float32)

    cue_log = []

    def mark(cue_id: str, t_placed: float):
        cue_log.append({"id": cue_id, "t_audio": round(float(t_placed), 6), "t_target": CUES[cue_id]["t"]})

    # -------------------------------------------------------------------------
    # 1. AMBIENCE LAYER (Autumn wind J-cut + Warm Lantern Hearth Bed)
    # -------------------------------------------------------------------------
    mark("wind_jcut_in", 0.00)
    t_full = np.arange(n_total) / SR
    # Cold dry autumn night breeze (240..950 Hz), ducked to true silence in [2.18..2.75] and [5.66..5.98]!
    wind_l = sfx.bp(sfx.brown(DUR), 220, 880, 2)
    wind_r = sfx.bp(sfx.brown(DUR), 250, 960, 2)
    wind_env = (
        np.clip(t_full / 0.22, 0.0, 1.0)
        * (1.0 - 0.995 * np.exp(-((t_full - 2.46) / 0.22) ** 6))   # Silence #1
        * (1.0 - 0.92 * np.exp(-((t_full - 5.82) / 0.14) ** 4))    # Silence #2
        * np.clip((9.75 - t_full) / 0.65, 0.0, 1.0)
    )
    amb_bus[:, 0] += wind_l * wind_env * 0.032
    amb_bus[:, 1] += wind_r * wind_env * 0.032

    # Warm hearth lantern crackle bed during Act II (3.08s .. 5.58s) & gentle glow in Act III (6.05s .. 9.30s)
    hearth_bed = sfx.roar(2.50, v=0.055)
    sfx.add(amb_bus, hearth_bed, 3.08, gain=1.0, pan=0.0)
    hearth_tail = sfx.lp(sfx.roar(3.20, v=0.025), 2600, 2)
    sfx.add(amb_bus, hearth_tail, 6.08, gain=1.0, pan=0.0)

    # -------------------------------------------------------------------------
    # 2. PROCEDURAL FOLEY LAYER (Every visual action has a material sound!)
    # -------------------------------------------------------------------------
    # Early dry leaf whispers in darkness
    sfx.add(fol_bus, leaf_rustle_foley(0.38, v=0.09), 0.10, pan=-0.38)
    sfx.add(fol_bus, leaf_rustle_foley(0.34, v=0.07), 0.82, pan=0.34)

    # Act I: 2D Woodcut Gouge Carves
    mark("carve_stem_strike", 0.25)
    sfx.add(fol_bus, woodcut_gouge_foley(0.38, speed=1.05, v=0.30), 0.25, pan=0.04)

    mark("carve_ribs_sweep", 0.625)
    sfx.add(fol_bus, woodcut_gouge_foley(0.34, speed=1.20, v=0.25), 0.625, pan=-0.12)

    # Beat 2.0 (1.00s): Hard print-plate impression cut + dual eye-brow gouge!
    mark("cut_frontal_plate", 1.00)
    sfx.add(fol_bus, sfx.clack(pitch=0.78, v=0.34), 1.00, pan=0.0)
    sfx.add(fol_bus, sfx.thump(v=0.20, f=95), 1.00, pan=0.0)
    sfx.add(fol_bus, woodcut_gouge_foley(0.42, speed=0.95, v=0.27), 1.03, pan=-0.16)
    sfx.add(fol_bus, woodcut_gouge_foley(0.36, speed=1.10, v=0.24), 1.24, pan=0.18)

    # Beat 3.0 (1.50s): 9-tooth wicked grin carve!
    mark("carve_grin_slice", 1.50)
    sfx.add(fol_bus, woodcut_gouge_foley(0.52, speed=1.30, v=0.30), 1.50, pan=0.06)

    mark("silence_1_start", 2.15)

    # Beat 5.5 (2.75s): Flint spark in Left Eye + tiny fire-arc zip to Right Eye!
    mark("eye_spark_ping", 2.75)
    spk_snap, spk_arc = flint_spark_and_arc(v=0.36)
    sfx.add(fol_bus, spk_snap, 2.75, pan=-0.22)
    sfx.add(fol_bus, spk_arc, 2.86, pan=0.16)

    # Beat 6.0 (3.00s): THE TURN — 2D -> 3D Inner Fire Eruption!
    mark("ignite_3d_boom", 3.00)
    sfx.add(fol_bus, hearth_ignition_boom(v=0.68), 3.00, pan=0.0)

    # Beat 7.0 (3.50s): Swirling 3D embers & autumn leaves gust!
    mark("ember_swirl_gust", 3.50)
    sfx.add(fol_bus, sfx.whoosh(d=0.48, v=0.14), 3.50, pan=0.18)
    sfx.add(fol_bus, leaf_rustle_foley(0.46, v=0.12), 3.54, pan=0.26)

    # Beat 9.5 (4.75s): Smooth 3D crane pull-back air
    mark("crane_pullback", 4.75)
    sfx.add(fol_bus, sfx.whoosh(d=0.62, v=0.10), 4.75, pan=-0.08)

    # Beat 11.3 (5.65s): Silence #2 reverse-ember inhale (J-cut #2 into Beat 12 lockup!)
    mark("silence_2_inhale", 5.65)
    sfx.add(fol_bus, reverse_inhale_shimmer(dur=0.34, v=0.22), 5.65, pan=0.0)

    # Beat 12.0 (6.00s): Hero Pumpkin docks in Crest Throne + Vines & Ring sprout!
    mark("crest_throne_lock", 6.00)
    sfx.add(fol_bus, sfx.thump(v=0.36, f=74), 6.00, pan=0.0)
    sfx.add(fol_bus, sfx.clack(pitch=0.92, v=0.22), 6.00, pan=0.0)
    sfx.add(fol_bus, leaf_rustle_foley(0.58, v=0.15), 6.04, pan=-0.30)
    sfx.add(fol_bus, leaf_rustle_foley(0.58, v=0.15), 6.08, pan=0.30)

    # Beat 12.5 (6.25s): 4 Companion Pumpkins pop warm left & right!
    mark("side_pumpkins_pop", 6.25)
    for dt_p, pan_p, pv in [(0.00, -0.35, 0.14), (0.07, 0.34, 0.14), (0.14, -0.22, 0.11), (0.20, 0.32, 0.12)]:
        sfx.add(fol_bus, sfx.pop(v=pv) * 0.7, 6.25 + dt_p, pan=pan_p)

    # Beat 13.0 (6.50s): Gothic "Pottsfield" blazes across upper arch!
    mark("pottsfield_blaze", 6.50)
    sfx.add(fol_bus, golden_title_shimmer(dur=0.72, v=0.20), 6.50, pan=-0.12)
    sfx.add(fol_bus, golden_title_shimmer(dur=0.65, v=0.18), 6.62, pan=0.18)

    # Beat 14.5 (7.25s): "S T U D I O" crimson lock tick!
    mark("studio_lock_chime", 7.25)
    sfx.add(fol_bus, sfx.click(pitch=1.25, v=0.18), 7.25, pan=0.0)

    # Final faint hearth ember tick during hold (8.10s) & visual fade cue at 9.45s
    sfx.add(fol_bus, sfx.click(pitch=1.8, v=0.06), 8.12, pan=0.15)
    mark("fade_to_boot_black", 9.45)

    # -------------------------------------------------------------------------
    # 3. ORIGINAL MUSICAL SCORE (Haunted Autumn Music-Box, Plucked Lute/Harp & Cello)
    # -------------------------------------------------------------------------
    def add_inst(sig: np.ndarray, at: float, gain: float, pan: float = 0.0, rev: float = 0.38):
        sfx.add(mus_dry, sig, at, gain=gain * (1.0 - 0.3 * rev), pan=pan)
        sfx.add(mus_send, sig, at, gain=gain * rev, pan=pan * 0.6)

    # Act I: Sparse woody upright bass pizzicato on carve beats (cut cleanly before Silence #1 at 2.15s!)
    add_inst(P.pluck("upright_bass_pizz", "D2", dur=0.65, vel=0.62, release=0.18), 0.25, gain=0.46, pan=-0.05, rev=0.18)
    add_inst(P.pluck("upright_bass_pizz", "A1", dur=0.72, vel=0.58, release=0.18), 1.00, gain=0.44, pan=0.05, rev=0.18)
    add_inst(P.pluck("guqin", "D4", dur=0.42, vel=0.48, harmonic=True, release=0.16), 1.50, gain=0.28, pan=0.10, rev=0.20)

    # Beat 5.5 (2.75s): THE SPARK — Single crystal music-box + harp harmonic A5 out of pure silence!
    add_inst(P.pluck("music_box", "A5", dur=0.35, vel=0.78), 2.75, gain=0.52, pan=-0.22, rev=0.45)
    add_inst(P.pluck("harp", "A4", dur=0.30, vel=0.55, harmonic=True), 2.75, gain=0.30, pan=-0.18, rev=0.40)

    # Beat 6.0 (3.00s): Act II 3D Ignition — Bowed Cello Fifth + Harp/Lute Bloom + Pottsfield Motif!
    add_inst(bowed_cello("D2", dur=2.15, vel=0.48, att=0.16, rel=0.35), 3.00, gain=0.42, pan=-0.10, rev=0.30)
    add_inst(bowed_cello("A2", dur=2.15, vel=0.44, att=0.20, rel=0.35), 3.00, gain=0.38, pan=0.12, rev=0.32)
    add_inst(P.strum("harp", ["D3", "A3", "D4", "F4", "A4"], dur=2.10, vel=0.72, spread=0.032), 3.00, gain=0.48, pan=-0.14, rev=0.45)
    add_inst(P.strum("nylon_guitar", ["D3", "A3", "D4", "F4"], dur=1.85, vel=0.68, spread=0.024), 3.02, gain=0.40, pan=0.18, rev=0.35)

    # Iconic 5-note Haunted Autumn Motif (D Dorian: D5 - F5 - A5 - G5 - E5)
    motif_notes = [
        (3.000, "D5", 0.65, 0.80, -0.12),
        (3.500, "F5", 0.60, 0.76,  0.14),
        (4.000, "A5", 0.55, 0.85, -0.08),
        (4.375, "G5", 0.48, 0.74,  0.12),
        (4.750, "E5", 0.72, 0.82, -0.15),  # Dorian sixth on crane pull-back!
        (5.250, "D5", 0.32, 0.65,  0.05),
    ]
    mark("motif_phrase_a", 4.00)
    for t_n, note, d_n, vel_n, pan_n in motif_notes:
        add_inst(P.pluck("music_box", note, dur=d_n, vel=vel_n), t_n, gain=0.46, pan=pan_n, rev=0.48)
        # Double softly an octave lower on plucked harp for body warmth
        oct_low = note[:-1] + str(int(note[-1]) - 1)
        add_inst(P.pluck("harp", oct_low, dur=d_n + 0.15, vel=vel_n * 0.68), t_n, gain=0.28, pan=-pan_n * 0.7, rev=0.42)

    # Beat 12.0 (6.00s): Act III — THE OFFICIAL POTTSFIELD CREST CHORD (Open D5 -> Golden D Major/Add9 Glow!)
    add_inst(bowed_cello("D2", dur=2.65, vel=0.52, att=0.14, rel=1.10), 6.00, gain=0.44, pan=-0.12, rev=0.42)
    add_inst(bowed_cello("A2", dur=2.70, vel=0.48, att=0.18, rel=1.10), 6.00, gain=0.40, pan=0.12, rev=0.42)
    # Warm Picardy F#3 cello glow swelling gently at 6.50s as "Pottsfield" illuminates in golden-orange!
    add_inst(bowed_cello("F#3", dur=2.25, vel=0.38, att=0.42, rel=1.05), 6.48, gain=0.34, pan=0.04, rev=0.48)

    add_inst(P.strum("acoustic_guitar", ["D3", "A3", "D4", "E4", "A4"], dur=2.85, vel=0.76, spread=0.028), 6.00, gain=0.46, pan=-0.20, rev=0.44)
    add_inst(P.strum("harp", ["D4", "A4", "D5", "E5", "A5"], dur=2.95, vel=0.74, spread=0.036), 6.02, gain=0.44, pan=0.20, rev=0.50)

    # Ascending golden dust glissando tracking "P-o-t-t-s-f-i-e-l-d" (6.50s .. 7.05s)
    gliss = ["D5", "E5", "F#5", "A5", "B5", "D6"]
    for idx, p_g in enumerate(gliss):
        tg = 6.50 + idx * 0.095
        pg = -0.28 + 0.56 * (idx / (len(gliss) - 1))
        add_inst(P.pluck("harp", p_g, dur=2.1, vel=0.64), tg, gain=0.26, pan=pg, rev=0.55)

    # Beat 14.5 (7.25s): "S T U D I O" Final Signature Lock Bell/Music-Box Harmonic (D6 + A5)
    add_inst(P.pluck("music_box", "D6", dur=2.0, vel=0.82), 7.25, gain=0.44, pan=0.04, rev=0.55)
    add_inst(P.pluck("music_box", "A5", dur=2.1, vel=0.72), 7.26, gain=0.34, pan=-0.06, rev=0.55)
    add_inst(P.pluck("guqin", "D5", dur=2.2, vel=0.74, harmonic=True), 7.25, gain=0.38, pan=0.0, rev=0.52)

    # -------------------------------------------------------------------------
    # 4. STEREO REVERB, SILENCE CARVING, SIDECHAIN DUCKING & LOW-END BALANCE
    # -------------------------------------------------------------------------
    ir_l, ir_r = stereo_reverb_ir(rt60=1.75, dur=2.3)
    rev_l = fftconvolve(mus_send[:, 0], ir_l)[:n_total]
    rev_r = fftconvolve(mus_send[:, 1], ir_r)[:n_total]
    mus_bus = mus_dry + np.stack([rev_l, rev_r], axis=1) * 0.52

    # Enforce Real Silence #1 (2.18s .. 2.74s) & Pre-Lockup Hush #2 (5.66s .. 5.98s) on music + reverb tails!
    sil1_gate = 1.0 - 0.992 * (
        1.0 / (1.0 + np.exp(-(t_full - 2.17) / 0.022))
        * (1.0 / (1.0 + np.exp((t_full - 2.735) / 0.012)))
    )
    sil2_gate = 1.0 - 0.88 * (
        1.0 / (1.0 + np.exp(-(t_full - 5.66) / 0.030))
        * (1.0 / (1.0 + np.exp((t_full - 5.985) / 0.015)))
    )
    mus_bus *= (sil1_gate * sil2_gate)[:, None].astype(np.float32)

    # Duck music ~2.8 dB briefly under the 3.00s fire ignition & 6.00s throne lockup transients!
    duck = (
        1.0
        - 0.28 * np.exp(-np.maximum(0.0, t_full - 3.00) / 0.16) * (t_full >= 3.00)
        - 0.20 * np.exp(-np.maximum(0.0, t_full - 6.00) / 0.14) * (t_full >= 6.00)
    )
    mus_bus *= duck[:, None].astype(np.float32)

    mix = amb_bus + fol_bus + mus_bus

    # Clean 30 Hz high-pass + gentle sub-shelf check so 20-120 Hz sits ~ -3 dB below rest (TECHNIQUE.md §5)
    sos_sub_hp = butter(2, 32.0, "high", fs=SR, output="sos")
    for ch in range(2):
        mix[:, ch] = sosfilt(sos_sub_hp, mix[:, ch])

    # Measure low-end balance (20-120 Hz vs 120-10000 Hz)
    mono = 0.5 * (mix[:, 0] + mix[:, 1])
    low_band = sfx.bp(mono, 20, 120, 2)
    rest_band = sfx.bp(mono, 120, 10000, 2)
    e_low = np.sqrt(np.mean(low_band ** 2) + 1e-12)
    e_rest = np.sqrt(np.mean(rest_band ** 2) + 1e-12)
    ratio_db = 20.0 * math.log10(e_low / e_rest)
    if ratio_db > -2.2:
        # Trim 32-115 Hz slightly so small phone speakers AND desktop subwoofers sound equally crisp!
        atten = 1.0 - (1.0 - 10.0 ** ((-3.0 - ratio_db) / 20.0))
        for ch in range(2):
            sub_c = sfx.bp(mix[:, ch], 25, 118, 2)
            mix[:, ch] -= sub_c * float(np.clip(atten, 0.0, 0.65))
        mono = 0.5 * (mix[:, 0] + mix[:, 1])
        e_low = np.sqrt(np.mean(sfx.bp(mono, 20, 120, 2) ** 2) + 1e-12)
        e_rest = np.sqrt(np.mean(sfx.bp(mono, 120, 10000, 2) ** 2) + 1e-12)
        ratio_db = 20.0 * math.log10(e_low / e_rest)

    # Smooth fade-in (15 ms) and clean digital silence fade-out by 9.97s (L-cut over 9.45s picture fade!)
    fi = int(0.015 * SR)
    mix[:fi] *= np.linspace(0.0, 1.0, fi)[:, None]
    fo_start = int(9.40 * SR)
    fo_end = int(9.97 * SR)
    mix[fo_start:fo_end] *= (0.5 * (1.0 + np.cos(np.pi * np.arange(fo_end - fo_start) / (fo_end - fo_start))))[:, None]
    mix[fo_end:] = 0.0

    # Gentle look-ahead peak taming to -3 dBFS (~0.707) so mux.sh two-pass linear loudnorm hits -14.0 LUFS / <= -1.2 dBTP!
    peak = float(np.abs(mix).max())
    if peak > 0:
        mix *= 0.62 / peak
    for ch in range(2):
        mix[:, ch] = sfx.limit(mix[:, ch], ceil=0.68, look=0.005)

    out_dir = os.path.join(HERE, "out")
    os.makedirs(out_dir, exist_ok=True)
    wav_path = os.path.join(out_dir, "mix.wav")
    sf.write(wav_path, mix, SR, subtype="PCM_16")

    # Save cue verification report for cuecheck.py
    with open(os.path.join(out_dir, "audio_cues.json"), "w", encoding="utf-8") as f:
        json.dump({"cues": cue_log, "low_to_rest_db": round(ratio_db, 2)}, f, indent=2)

    print(f"Wrote {wav_path} ({DUR:.2f}s @ {SR} Hz, low/rest={ratio_db:.2f} dB, peak={20*math.log10(np.abs(mix).max()):.2f} dBFS)")


if __name__ == "__main__":
    build_mix()
