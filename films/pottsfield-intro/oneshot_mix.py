"""36.0-Second (100 BPM, 15-Bar) Beat-Synced Procedural Score & Foley Mix for Pottsfield One-Shot.

Follows motion-skills/skills/soundtrack/SKILL.md:
  - 100.0 BPM beat grid (1 beat = 0.60s, 1 bar = 2.40s, 15 bars = 36.00s)
  - Whole-bar chord changes in D Aeolian/Dorian -> warm D-add9 resolution
  - Staggered groove entry (no harsh >6 dB unintentional startle cuts)
  - Deliberate Bar-10 Silence Break (21.65s..22.25s) before the 2D Pumpkin Carving & 25.20s 3D Drop
  - Seamless musical & ambient loop seam from 36.00s -> 0.00s
"""
import json
import math
import os
import sys
import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from core.audio import sfx
from core.audio import pluck as P
from mix import stereo_reverb_ir

SR = 48000
DUR = 36.00
BPM = 100.0
BEAT = 60.0 / BPM   # 0.60s
BAR = 4.0 * BEAT    # 2.40s
sfx.SR = SR
P.SR = SR


def note_hz(name: str) -> float:
    names = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
             "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
    p = name[:-1]
    octv = int(name[-1])
    midi = 12 * (octv + 1) + names[p]
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def warm_pad_note(note: str, dur: float, vel: float = 0.25, bright: float = 0.5) -> np.ndarray:
    """Synthesizes a warm bowed cello/viola ensemble pad note with natural vibrato & rosin breath."""
    n = int(round(dur * SR))
    t = np.arange(n, dtype=np.float32) / SR
    f0 = note_hz(note)
    vib = 1.0 + 0.0028 * np.sin(2.0 * math.pi * 5.1 * t) * np.clip(t / 0.4, 0.0, 1.0)
    ph = np.cumsum(2.0 * math.pi * f0 * vib / SR)
    sig = (0.58 * np.sin(ph)
           + 0.24 * np.sin(2.0 * ph + 0.3)
           + 0.12 * bright * np.sin(3.0 * ph + 0.7)
           + 0.06 * bright * np.sin(4.0 * ph))
    sig = sfx.lp(sig.astype(np.float32), 900.0 + 950.0 * bright, 2)
    att = np.clip(t / min(0.32, dur * 0.35), 0.0, 1.0)
    rel = np.clip((dur - t) / min(0.48, dur * 0.40), 0.0, 1.0)
    env = (att ** 1.3) * (rel ** 1.5)
    return (sig * env * vel).astype(np.float32)


def frame_drum_hit(vel: float = 0.35, low_hz: float = 68.0) -> np.ndarray:
    """Warm organic autumn frame-drum / bodhran thump (never harsh EDM kick)."""
    dur = 0.34
    n = int(round(dur * SR))
    t = np.arange(n, dtype=np.float32) / SR
    f_sweep = low_hz + 52.0 * np.exp(-t / 0.028)
    ph = np.cumsum(2.0 * math.pi * f_sweep / SR)
    body = np.sin(ph) * np.exp(-t / 0.105)
    skin = sfx.bp(sfx.noise(dur), 180, 950, 2) * np.exp(-t / 0.024) * 0.28
    return ((body + skin) * vel).astype(np.float32)


def wood_scrape(dur: float, pitch_hz: float = 720.0, v: float = 0.16) -> np.ndarray:
    """Tactile woodcut gouge-chisel carving foley."""
    n = int(round(dur * SR))
    t = np.arange(n, dtype=np.float32) / SR
    grain = np.sin(2.0 * np.pi * (26.0 * t + 4.0 * np.sin(2.0 * np.pi * 6.0 * t))) * 0.35 + 0.65
    scrape = sfx.bp(sfx.noise(dur), pitch_hz * 0.6, min(pitch_hz * 2.1, 8000.0), 2) * grain
    env = np.clip(t / 0.02, 0.0, 1.0) * np.clip((dur - t) / 0.05, 0.0, 1.0)
    return (sfx.norm(scrape * env) * v).astype(np.float32)


def shatter_burst_sfx(v: float = 0.42) -> np.ndarray:
    """Crisp wood + glass + ember sparkle burst for the t=4.80s fake-ad shatter!"""
    dur = 0.85
    n = int(round(dur * SR))
    thump = frame_drum_hit(vel=0.55, low_hz=62.0)
    out = np.zeros(n, dtype=np.float32)
    out[:len(thump)] += thump
    rng = np.random.default_rng(480)
    for _ in range(9):
        dt = float(rng.uniform(0.0, 0.26))
        idx = int(dt * SR)
        f_sh = float(rng.uniform(1650.0, 4400.0))
        sub_n = min(int(0.18 * SR), n - idx)
        if sub_n <= 0:
            continue
        ts = np.arange(sub_n, dtype=np.float32) / SR
        ping = (np.sin(2 * math.pi * f_sh * ts) + 0.5 * np.sin(2 * math.pi * f_sh * 1.47 * ts)) * np.exp(-ts / 0.045)
        out[idx:idx + sub_n] += ping * 0.16
    crunch = sfx.bp(sfx.noise(0.22), 700, 3800, 2) * np.exp(-np.arange(int(0.22 * SR)) / (0.045 * SR)) * 0.35
    out[:len(crunch)] += crunch
    return (sfx.norm(out) * v).astype(np.float32)


def whip_whoosh_sfx(dur: float = 0.58, v: float = 0.24, upward: bool = False) -> np.ndarray:
    """Cinematic warm air-rush whoosh synced to camera whip-tilts."""
    n = int(round(dur * SR))
    t = np.arange(n, dtype=np.float32) / SR
    u = t / dur
    env = np.sin(np.pi * np.clip(u, 0.0, 1.0)) ** 1.6
    lo_b = sfx.bp(sfx.brown(dur), 140, 520, 2)
    hi_b = sfx.bp(sfx.noise(dur), 500, 1900, 2)
    tilt = u if upward else (1.0 - 0.5 * u)
    sig = (0.68 * lo_b + 0.36 * hi_b * tilt) * env
    return (sfx.norm(sig) * v).astype(np.float32)


def build_oneshot_mix():
    n_total = int(round(DUR * SR))
    amb_bus = np.zeros((n_total, 2), dtype=np.float32)
    fol_bus = np.zeros((n_total, 2), dtype=np.float32)
    mus_dry = np.zeros((n_total, 2), dtype=np.float32)
    mus_rev = np.zeros((n_total, 2), dtype=np.float32)

    cues = []

    def add_cue(name: str, t_s: float):
        cues.append({"name": name, "t": round(float(t_s), 4)})

    def place_mus(sig: np.ndarray, t_s: float, gain: float = 1.0, pan: float = 0.0, rev: float = 0.32):
        sfx.add(mus_dry, sig, t_s, gain=gain * (1.0 - 0.25 * rev), pan=pan)
        sfx.add(mus_rev, sig, t_s, gain=gain * rev, pan=-pan * 0.5)

    # =========================================================================
    # 1. CONTINUOUS AUTUMN NIGHT WIND & HEARTH AMBIENCE (Ducked cleanly in Hush!)
    # =========================================================================
    t_arr = np.arange(n_total, dtype=np.float64) / SR
    wind_l = sfx.bp(sfx.brown(DUR), 210, 820, 2)
    wind_r = sfx.bp(sfx.brown(DUR), 240, 910, 2)
    s_in = 1.0 / (1.0 + np.exp(-np.clip((t_arr - 21.68) / 0.08, -40.0, 40.0)))
    s_out = 1.0 / (1.0 + np.exp(np.clip((t_arr - 25.12) / 0.08, -40.0, 40.0)))
    hush_env = (1.0 - 0.96 * s_in * s_out).astype(np.float32)
    amb_bus[:, 0] += wind_l * 0.024 * hush_env
    amb_bus[:, 1] += wind_r * 0.024 * hush_env

    # Warm lantern hearth crackle during Story Diorama (13.4..16.8s) & Hero 3D Drop/Crest (25.2..35.2s)
    sfx.add(amb_bus, sfx.roar(3.4, v=0.036), 13.40, gain=1.0, pan=0.0)
    sfx.add(amb_bus, sfx.roar(9.8, v=0.044), 25.22, gain=1.0, pan=0.0)

    # =========================================================================
    # 2. FRAME-ACCURATE VISUAL FOLEY CUES
    # =========================================================================
    add_cue("hook_frame0", 0.00)
    sfx.add(fol_bus, sfx.click(pitch=1.05, v=0.14), 0.02, gain=1.0, pan=0.0)

    # Camera push into phone + 4 Fake-Ad clutter stamps!
    add_cue("phone_zoom_in", 2.40)
    sfx.add(fol_bus, whip_whoosh_sfx(0.45, v=0.15), 2.38, gain=1.0, pan=0.0)
    for idx, bt in enumerate([2.52, 3.04, 3.56, 4.06]):
        add_cue(f"fake_ad_stamp_{idx+1}", bt)
        sfx.add(fol_bus, sfx.clack(v=0.20), bt, gain=1.0, pan=(-0.18 if idx % 2 == 0 else 0.18))
        sfx.add(fol_bus, sfx.click(pitch=1.30 + 0.12 * idx, v=0.16), bt + 0.015, gain=1.0, pan=0.0)

    # Pre-shatter glass crackle -> SHATTER + WHIP-TILT 1 (4.80s)!
    sfx.add(fol_bus, wood_scrape(0.55, pitch_hz=1250.0, v=0.14), 4.20, gain=1.0, pan=0.0)
    add_cue("shatter_whip_1", 4.80)
    sfx.add(fol_bus, shatter_burst_sfx(v=0.44), 4.80, gain=1.0, pan=0.0)
    sfx.add(fol_bus, whip_whoosh_sfx(0.62, v=0.26), 4.82, gain=1.0, pan=0.0)

    # X-slash on Fake-Ad emblem (5.42s)
    add_cue("emblem_x_slash", 5.42)
    sfx.add(fol_bus, wood_scrape(0.32, pitch_hz=960.0, v=0.20), 5.42, gain=1.0, pan=0.08)

    # Horizontal Gouge-Spark Rewrite ("NO FAKE ADS." -> "NO BRAINROT." at 7.16s)
    add_cue("gouge_slice_rewrite", 7.16)
    sfx.add(fol_bus, wood_scrape(0.40, pitch_hz=1150.0, v=0.22), 7.16, gain=1.0, pan=0.0)
    sfx.add(fol_bus, whip_whoosh_sfx(0.38, v=0.20), 7.18, gain=1.0, pan=0.15)

    # Glide 2 into Story Diorama (9.60s) + 3D Lantern Wave (13.45s)
    add_cue("diorama_glide_2", 9.60)
    sfx.add(fol_bus, whip_whoosh_sfx(0.80, v=0.21), 9.60, gain=1.0, pan=-0.08)
    add_cue("diorama_3d_lantern_wave", 13.45)
    sfx.add(fol_bus, sfx.ignite(v=0.20), 13.45, gain=1.0, pan=0.10)

    # Whip-Tilt 3 into Platform Stage (16.80s) + Phone->PC Spring Morph (19.20s)!
    add_cue("platform_whip_3", 16.80)
    sfx.add(fol_bus, whip_whoosh_sfx(0.58, v=0.25), 16.80, gain=1.0, pan=0.0)
    sfx.add(fol_bus, sfx.clack(v=0.18), 17.24, gain=1.0, pan=0.0)

    add_cue("windows_pc_morph", 19.20)
    sfx.add(fol_bus, sfx.click(pitch=0.92, v=0.18), 19.12, gain=1.0, pan=0.0)
    sfx.add(fol_bus, whip_whoosh_sfx(0.48, v=0.24, upward=True), 19.20, gain=1.0, pan=0.0)
    sfx.add(fol_bus, sfx.clack(v=0.20), 19.52, gain=1.0, pan=0.0)

    # Portal Dive into Darkness & Musical Silence Break (21.60s)!
    add_cue("portal_dive_silence", 21.60)
    sfx.add(fol_bus, whip_whoosh_sfx(0.60, v=0.28), 21.55, gain=1.0, pan=0.0)

    # 2D Woodcut Hero Pumpkin Carving Foley (22.28s .. 24.85s)
    carve_hits = [
        (22.28, 0.42, 820.0, 0.19, -0.08),   # stem
        (22.82, 0.55, 680.0, 0.18,  0.10),   # outer ribs
        (23.48, 0.34, 980.0, 0.21, -0.14),   # eyes
        (23.95, 0.28, 1080.0, 0.19, 0.12),   # nose
        (24.32, 0.52, 760.0, 0.21,  0.00),   # jagged grin
    ]
    for tc, cdur, cpitch, cv, cpan in carve_hits:
        sfx.add(fol_bus, wood_scrape(cdur, pitch_hz=cpitch, v=cv), tc, gain=1.0, pan=cpan)
        sfx.add(fol_bus, sfx.click(pitch=1.15, v=cv * 0.65), tc, gain=1.0, pan=cpan)

    # THE 3D VOLUMETRIC SPARK DROP (25.20s = Bar 11.5)!
    add_cue("hero_pumpkin_3d_drop", 25.20)
    sfx.add(fol_bus, sfx.click(pitch=1.45, v=0.28), 25.20, gain=1.0, pan=0.0)
    sfx.add(fol_bus, sfx.ignite(v=0.34), 25.20, gain=1.0, pan=0.0)
    sfx.add(fol_bus, frame_drum_hit(vel=0.52, low_hz=54.0), 25.20, gain=1.0, pan=0.0)

    # Full Circular Pottsfield STUDIO Crest Bloom (27.60s)
    add_cue("pottsfield_crest_bloom", 27.60)
    sfx.add(fol_bus, whip_whoosh_sfx(0.85, v=0.20, upward=True), 27.60, gain=1.0, pan=0.0)

    # End-Card CTA settle & pulse (30.85s, 32.40s) + Upward Loop Whip (35.20s -> 36.00s)!
    add_cue("cta_badge_in", 30.85)
    sfx.add(fol_bus, sfx.click(pitch=1.25, v=0.14), 30.88, gain=1.0, pan=0.0)
    add_cue("loop_whip_up", 35.20)
    sfx.add(fol_bus, whip_whoosh_sfx(0.76, v=0.26, upward=True), 35.20, gain=1.0, pan=0.0)

    # =========================================================================
    # 3. 15-BAR HARMONIC SCORE @ 100 BPM (Whole-Bar Progression in D Minor)
    # =========================================================================
    bar_plan = [
        # Ch 1: Hook & Fake-Ad Tension (Bars 0, 1)
        (0, "D2",  ["D4", "A4", "E5", "F5", "A4", "F4", "E4", "A4"], ["D3", "A3"], 0.15),
        (1, "Bb1", ["Bb3", "F4", "C5", "D5", "F4", "D4", "C4", "F4"], ["Bb2", "F3"], 0.28),
        # Ch 2: Shatter & Anti-Brainrot Groove (Bars 2, 3)
        (2, "D2",  ["D4", "F4", "A4", "D5", "C5", "A4", "F4", "A4"], ["D3", "A3", "F4"], 0.68),
        (3, "G2",  ["G3", "D4", "Bb4", "A4", "G4", "F4", "E4", "C#4"], ["G2", "D3", "Bb3"], 0.75),
        # Ch 3: Story Diorama 2D -> 3D Worlds (Bars 4, 5, 6)
        (4, "F2",  ["F3", "C4", "A4", "C5", "E5", "C5", "A4", "F4"], ["F3", "C4", "A4"], 0.62),
        (5, "C2",  ["C4", "G4", "C5", "E5", "G5", "E5", "C5", "G4"], ["C3", "G3", "E4"], 0.72),
        (6, "D2",  ["D4", "A4", "F5", "E5", "D5", "A4", "F4", "E4"], ["D3", "A3", "F4"], 0.85),
        # Ch 4: Android First -> Windows PC Next (Bars 7, 8)
        (7, "G2",  ["G3", "D4", "G4", "Bb4", "D5", "Bb4", "G4", "D4"], ["G2", "D3", "Bb3"], 0.82),
        (8, "A1",  ["A3", "E4", "A4", "D5", "C#5", "E5", "A4", "G4"], ["A2", "E3", "C#4"], 0.90),
    ]

    eighth = BEAT * 0.5  # 0.30s
    for b_idx, bass_n, arp_notes, pad_ns, grv in bar_plan:
        t_bar = b_idx * BAR
        for pn in pad_ns:
            place_mus(warm_pad_note(pn, BAR + 0.25, vel=0.14 + 0.08 * grv, bright=0.45 + 0.35 * grv),
                      t_bar, gain=1.0, pan=0.0, rev=0.42)
        place_mus(P.pluck("upright_bass_pizz", bass_n, dur=1.25, vel=0.52 + 0.22 * grv), t_bar, gain=0.48, pan=0.0, rev=0.12)
        if grv >= 0.60:
            place_mus(P.pluck("upright_bass_pizz", bass_n, dur=0.95, vel=0.46), t_bar + 2.0 * BEAT, gain=0.40, pan=0.0, rev=0.12)
            sfx.add(mus_dry, frame_drum_hit(vel=0.30 * grv), t_bar, gain=1.0, pan=0.0)
            sfx.add(mus_dry, frame_drum_hit(vel=0.20 * grv, low_hz=82.0), t_bar + 1.5 * BEAT, gain=1.0, pan=0.0)
            sfx.add(mus_dry, frame_drum_hit(vel=0.26 * grv), t_bar + 2.0 * BEAT, gain=1.0, pan=0.0)

        for k, nn in enumerate(arp_notes):
            tk = t_bar + k * eighth
            inst = "music_box" if (b_idx < 2 or k % 2 == 0) else "harp"
            pan_k = -0.22 + 0.44 * (k % 3) / 2.0
            place_mus(P.pluck(inst, nn, dur=0.85, vel=0.50 + 0.15 * grv),
                      tk, gain=0.24, pan=pan_k, rev=0.38)
            if 4 <= b_idx <= 6 and k in (0, 3, 6):
                place_mus(P.pluck("nylon_guitar", nn, dur=1.05, vel=0.58), tk, gain=0.25, pan=-pan_k, rev=0.30)

    # Bar 9..10.5 (21.60s .. 25.20s): THE SILENCE BREAK + 2D Carving Music-Box Harmonics!
    whisper_notes = [(22.42, "D5", 0.15), (23.25, "F5", 0.14), (24.05, "A5", 0.16), (24.75, "C#5", 0.17)]
    for tw, nw, gw in whisper_notes:
        place_mus(P.pluck("music_box", nw, dur=1.4, vel=0.45), tw, gain=gw, pan=0.08, rev=0.55)

    # =========================================================================
    # 4. BAR 10.5 .. 15 (25.20s .. 36.00s): THE 3D LANTERN DROP -> CREST -> LOOP!
    # =========================================================================
    finale_chords = [
        (25.20, 2.40, "D2",  ["D3", "A3", "D4", "F4"], [(0.0, "A5"), (0.6, "G5"), (1.2, "F5"), (1.8, "E5")]),
        (27.60, 2.40, "Bb1", ["Bb2", "F3", "Bb3", "D4"], [(0.0, "D5"), (0.6, "F5"), (1.2, "A5"), (1.8, "C6")]),
        (30.00, 2.80, "D2",  ["D3", "A3", "E4", "F#4"], [(0.0, "D6"), (0.9, "A5"), (1.8, "F#5")]),
        (32.80, 2.40, "D2",  ["D3", "A3", "D4", "F#4"], [(0.0, "E5"), (1.2, "D5")]),
    ]
    for t_c, d_c, b_n, pads, mel in finale_chords:
        for pn in pads:
            place_mus(warm_pad_note(pn, d_c + 0.45, vel=0.22, bright=0.80), t_c, gain=1.0, pan=0.0, rev=0.48)
        place_mus(P.pluck("upright_bass_pizz", b_n, dur=min(d_c, 2.0), vel=0.72), t_c, gain=0.55, pan=0.0, rev=0.16)
        if t_c < 30.0:
            sfx.add(mus_dry, frame_drum_hit(vel=0.38, low_hz=58.0), t_c, gain=1.0, pan=0.0)
            sfx.add(mus_dry, frame_drum_hit(vel=0.26, low_hz=72.0), t_c + 1.20, gain=1.0, pan=0.0)
        for dt_m, mn in mel:
            place_mus(P.pluck("music_box", mn, dur=1.5, vel=0.66), t_c + dt_m, gain=0.26, pan=0.12, rev=0.48)
            place_mus(P.pluck("harp", mn, dur=1.4, vel=0.62), t_c + dt_m + 0.015, gain=0.24, pan=-0.14, rev=0.42)

    # Radiant Crest Harp Glissando at t = 27.60s!
    crest_gliss = ["D4", "F4", "A4", "C5", "D5", "F5", "A5", "D6"]
    for i, gn in enumerate(crest_gliss):
        place_mus(P.pluck("harp", gn, dur=1.6, vel=0.64), 27.60 + i * 0.055, gain=0.22, pan=-0.25 + 0.07 * i, rev=0.46)

    # Subtle bell shimmer on "FOLLOW FROM DAY 1" beacon pulse at t = 32.40s
    place_mus(P.pluck("music_box", "A5", dur=1.5, vel=0.55), 32.40, gain=0.22, pan=0.0, rev=0.50)

    # Loop Seam Rising Harp Glissando (35.20s -> 35.92s) leading directly back to Frame 0 D4/D5!
    loop_gliss = ["D4", "E4", "F4", "A4", "C5", "D5"]
    for i, gn in enumerate(loop_gliss):
        place_mus(P.pluck("harp", gn, dur=0.75, vel=0.55), 35.22 + i * 0.11, gain=0.22, pan=-0.18 + 0.07 * i, rev=0.35)

    # =========================================================================
    # 5. REVERB, SILENCE GATE, SUB-BALANCE & TRANSPARENT LIMITING
    # =========================================================================
    ir_l, ir_r = stereo_reverb_ir(rt60=1.70, dur=2.2)
    rev_l = fftconvolve(mus_rev[:, 0], ir_l)[:n_total]
    rev_r = fftconvolve(mus_rev[:, 1], ir_r)[:n_total]
    mus_bus = mus_dry + np.stack([rev_l, rev_r], axis=1).astype(np.float32) * 0.52

    # Carve clean musical hush gate at [21.65 .. 22.38s] so reverb tail drops into sacred darkness!
    g_in = 1.0 / (1.0 + np.exp(-np.clip((t_arr - 21.64) / 0.035, -40.0, 40.0)))
    g_out = 1.0 / (1.0 + np.exp(np.clip((t_arr - 22.36) / 0.025, -40.0, 40.0)))
    mus_bus *= (1.0 - 0.96 * g_in * g_out)[:, None].astype(np.float32)

    mix = amb_bus + fol_bus + mus_bus

    # Clean 32 Hz high-pass so phone speakers & desktop subwoofers translate cleanly
    sos_hp = butter(2, 32.0, "high", fs=SR, output="sos")
    for ch in range(2):
        mix[:, ch] = sosfilt(sos_hp, mix[:, ch])

    # Smooth 15ms micro-ramp at t=0 and t=36.00s so infinite Shorts/Reels loop never clicks!
    ramp = int(0.015 * SR)
    mix[:ramp] *= np.linspace(0.0, 1.0, ramp, dtype=np.float32)[:, None]
    mix[-ramp:] *= np.linspace(1.0, 0.0, ramp, dtype=np.float32)[:, None]

    # Transparent 5ms look-ahead peak taming so two-pass loudnorm hits -14.0 LUFS cleanly with zero warnings
    peak = float(np.abs(mix).max())
    if peak > 0:
        mix *= 0.62 / peak
    for ch in range(2):
        mix[:, ch] = sfx.limit(mix[:, ch], ceil=0.46, look=0.005)

    out_dir = os.path.join(HERE, "out")
    os.makedirs(out_dir, exist_ok=True)
    wav_path = os.path.join(out_dir, "mix_oneshot.wav")
    sf.write(wav_path, mix, SR, subtype="PCM_16")

    s0, s1 = int(21.95 * SR), int(22.24 * SR)
    hush_rms_db = 20.0 * math.log10(float(np.sqrt(np.mean(mix[s0:s1] ** 2) + 1e-12)))
    cues_path = os.path.join(out_dir, "oneshot_cues.json")
    with open(cues_path, "w", encoding="utf-8") as f:
        json.dump({"bpm": BPM, "duration": DUR, "hush_rms_db": round(hush_rms_db, 2), "cues": cues}, f, indent=2)

    print(f"Wrote {wav_path} ({DUR:.2f}s @ {SR} Hz, {len(cues)} beat-synced cues, hush={hush_rms_db:.1f} dBFS)")


if __name__ == "__main__":
    build_oneshot_mix()
