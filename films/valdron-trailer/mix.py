#!/usr/bin/env python3
"""
mix.py — Deterministic 48 kHz stereo original dark-fantasy score & frame-locked foley mixer for VALDRON.
Reads timeline.json + events.json -> writes work/mix.wav and prints spectral & silence verification.
"""
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, fftconvolve

HERE = Path(__file__).resolve().parent
LIB = Path(os.environ.get("LIB", HERE.parent.parent)).resolve()
sys.path.insert(0, str(LIB / "core" / "audio"))
import sfx  # noqa: E402

SR = 48000
RNG = np.random.default_rng(1309)


def midi_hz(m):
    return 440.0 * (2.0 ** ((m - 69.0) / 12.0))


def lp(x, fc, order=2):
    fc = min(max(fc, 25.0), SR * 0.46)
    return sosfilt(butter(order, fc, "low", fs=SR, output="sos"), x)


def hp(x, fc, order=2):
    fc = min(max(fc, 18.0), SR * 0.46)
    return sosfilt(butter(order, fc, "high", fs=SR, output="sos"), x)


def bp(x, lo, hi, order=2):
    lo = max(20.0, lo)
    hi = min(SR * 0.46, max(lo + 20.0, hi))
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def adsr(n, a=0.02, d=0.12, s=0.65, r=0.25):
    t = np.arange(n, dtype=np.float64) / SR
    dur = n / SR
    env = np.ones(n, dtype=np.float64) * s
    na = max(1, int(a * SR))
    nd = max(1, int(d * SR))
    nr = max(1, int(r * SR))
    if na < n:
        env[:na] = np.linspace(0.0, 1.0, na)
    else:
        return np.linspace(0.0, 1.0, n)
    end_d = min(n, na + nd)
    if end_d > na:
        env[na:end_d] = np.linspace(1.0, s, end_d - na)
    if nr < n:
        rel_start = max(0, n - nr)
        env[rel_start:] *= np.linspace(1.0, 0.0, n - rel_start)
    return env


def add_stereo(buf, sig, t0, gain=1.0, pan=0.0):
    s = int(round(t0 * SR))
    if sig.ndim == 1:
        if s >= len(buf) or s + len(sig) <= 0:
            return
        if s < 0:
            sig = sig[-s:]
            s = 0
        e = min(len(buf), s + len(sig))
        ang = (np.clip(pan, -1.0, 1.0) + 1.0) * (math.pi / 4.0)
        gl, gr = math.cos(ang) * 1.4142, math.sin(ang) * 1.4142
        seg_x = sig[: e - s] * gain
        buf[s:e, 0] += seg_x * gl
        buf[s:e, 1] += seg_x * gr
    else:
        if s >= len(buf) or s + len(sig) <= 0:
            return
        if s < 0:
            sig = sig[-s:]
            s = 0
        e = min(len(buf), s + len(sig))
        buf[s:e] += sig[: e - s] * gain


# —— ORIGINAL DARK-FANTASY SYNTHESIS INSTRUMENTS ——

def warbled_reed_key(midi, dur, detune_depth=0.0045, bright=1500.0):
    """Fragile tape-warbled antique reed/electric keyboard (nostalgic, slightly uncanny)."""
    n = int(round((dur + 0.35) * SR))
    t = np.arange(n) / SR
    f0 = midi_hz(midi)
    # Slow tape drift + gentle wow/flutter
    wow = detune_depth * np.sin(2 * np.pi * 4.3 * t + (midi % 7)) + 0.0022 * np.sin(2 * np.pi * 0.75 * t)
    ph = 2 * np.pi * np.cumsum(f0 * (1.0 + wow)) / SR
    sig = (
        0.62 * np.sin(ph)
        + 0.24 * np.sin(2 * ph + 0.3) * np.exp(-t * 1.6)
        + 0.14 * np.sin(3 * ph) * np.exp(-t * 2.8)
        + 0.06 * np.sin(4 * ph) * np.exp(-t * 4.5)
    )
    env = adsr(n, a=0.035, d=0.22, s=0.52, r=0.35)
    return lp(sig * env, bright)


def music_box_tine(midi, dur):
    """Haunted antique music-box / celesta tine with metallic inharmonic partial."""
    n = int(round((dur + 0.5) * SR))
    t = np.arange(n) / SR
    f0 = midi_hz(midi)
    sig = (
        0.72 * np.sin(2 * np.pi * f0 * t) * np.exp(-t * 2.4)
        + 0.22 * np.sin(2 * np.pi * f0 * 2.0 * t) * np.exp(-t * 5.5)
        + 0.15 * np.sin(2 * np.pi * f0 * 5.38 * t) * np.exp(-t * 16.0)
    )
    click_tr = hp(RNG.standard_normal(n), 3200) * np.exp(-t * 110.0) * 0.08
    return (sig + click_tr) * adsr(n, a=0.003, d=0.08, s=0.75, r=0.3)


def hollow_wood_flute(midi, dur, vibrato=0.005):
    """Breathy lost-in-the-woods wooden flute / ocarina-like antique pipe."""
    n = int(round((dur + 0.2) * SR))
    t = np.arange(n) / SR
    f0 = midi_hz(midi)
    vib = vibrato * np.sin(2 * np.pi * 5.1 * t) * np.clip((t - 0.15) / 0.3, 0.0, 1.0)
    ph = 2 * np.pi * np.cumsum(f0 * (1.0 + vib)) / SR
    tone = 0.74 * np.sin(ph) + 0.18 * np.sin(3 * ph) + 0.06 * np.sin(2 * ph)
    chiff = bp(RNG.standard_normal(n), max(300.0, f0 * 0.8), min(6000.0, f0 * 2.6)) * (0.14 + 0.22 * np.exp(-t * 18.0))
    return lp((tone + chiff) * adsr(n, a=0.06, d=0.14, s=0.72, r=0.20), 2800.0)


def parlor_organ_pad(midis, dur, cutoff=1100.0):
    """Detuned gothic harmonium / parlor organ pad (kept >= MIDI 48 per low-end rule)."""
    n = int(round((dur + 0.4) * SR))
    t = np.arange(n) / SR
    acc = np.zeros(n, dtype=np.float64)
    for m in midis:
        m_safe = max(48, m)
        for det in (-0.0028, 0.0028):
            f = midi_hz(m_safe) * (1.0 + det)
            saw = 2.0 * ((t * f) % 1.0) - 1.0
            sq = np.sign(np.sin(2 * np.pi * f * t))
            acc += (0.55 * sq + 0.45 * saw) / (2.0 * len(midis))
    env = adsr(n, a=0.35, d=0.3, s=0.80, r=0.45)
    return lp(hp(acc, 110.0) * env, cutoff)


def retro_dark_bass(midi, dur):
    """Nocturnal dark-fantasy retro synth bass: controlled <120Hz + strong 2nd & 3rd harmonics."""
    n = int(round((dur + 0.06) * SR))
    t = np.arange(n) / SR
    f0 = midi_hz(midi)
    saw = 2.0 * ((t * f0) % 1.0) - 1.0
    sub_h2 = 0.55 * np.sin(2 * np.pi * f0 * 2.0 * t) + 0.38 * np.sin(2 * np.pi * f0 * 3.0 * t)
    raw = np.tanh((0.65 * saw + sub_h2) * 1.9)
    # Dynamic filter pluck envelope
    f_hi = lp(raw, 1450.0) * np.exp(-t * 9.0)
    f_lo = lp(raw, 420.0)
    sig = hp(0.65 * f_lo + 0.55 * f_hi, 42.0)
    return sig * adsr(n, a=0.006, d=0.08, s=0.62, r=0.05)


def dark_synth_lead(midi, dur, glide_from=None):
    """Haunting analog Dorian/Aeolian dark-synth lead."""
    n = int(round((dur + 0.18) * SR))
    t = np.arange(n) / SR
    f1 = midi_hz(midi)
    if glide_from is not None:
        f0 = midi_hz(glide_from)
        f_curve = f1 + (f0 - f1) * np.exp(-t * 16.0)
    else:
        f_curve = np.full(n, f1)
    vib = 0.004 * np.sin(2 * np.pi * 5.6 * t) * np.clip((t - 0.12) / 0.25, 0.0, 1.0)
    ph1 = np.cumsum(f_curve * (1.0 + vib)) / SR
    ph2 = np.cumsum(f_curve * 1.004 * (1.0 - vib * 0.6)) / SR
    pwm = np.where((ph1 % 1.0) < (0.36 + 0.12 * np.sin(2 * np.pi * 1.4 * t)), 1.0, -1.0)
    saw = 2.0 * (ph2 % 1.0) - 1.0
    sig = lp(0.55 * pwm + 0.45 * saw, 2300.0)
    return sig * adsr(n, a=0.025, d=0.15, s=0.70, r=0.18)


def cathedral_bell(midi=38, dur=6.8):
    """Colossal gothic bronze bell with authentic minor-third hum/prime/tierce/quint partials."""
    n = int(round(dur * SR))
    t = np.arange(n) / SR
    f0 = midi_hz(midi)  # D2 ~ 73.4 Hz, with strong upper partials so small speakers feel scale
    partials = [
        (0.5, 0.22, 4.8),   # hum
        (1.0, 0.65, 4.2),   # prime
        (1.2, 0.48, 3.1),   # minor third tierce!
        (1.5, 0.42, 3.6),   # fifth
        (2.0, 0.58, 2.7),   # nominal
        (2.5, 0.26, 1.9),
        (3.0, 0.22, 1.5),
        (4.2, 0.14, 0.9),
    ]
    sig = np.zeros(n, dtype=np.float64)
    for mult, amp, tau in partials:
        sig += amp * np.sin(2 * np.pi * f0 * mult * t) * np.exp(-t / tau)
    strike = bp(RNG.standard_normal(n), 450, 3600) * np.exp(-t * 36.0) * 0.35
    return sfx.norm(hp(sig + strike, 45.0)) * 0.95


def snes_dark_echo(stereo_buf, taps=((0.21, 0.34, -0.35), (0.36, 0.24, 0.35), (0.53, 0.15, -0.15))):
    """Filtered multi-tap stereo echo (dark 2.3 kHz loop like 16-bit console DSP)."""
    out = stereo_buf.copy()
    mono = lp(0.5 * (stereo_buf[:, 0] + stereo_buf[:, 1]), 2300.0)
    for delay_s, g, pan in taps:
        d = int(round(delay_s * SR))
        if d < len(out):
            ang = (pan + 1.0) * (math.pi / 4.0)
            out[d:, 0] += mono[:-d] * g * math.cos(ang) * 1.414
            out[d:, 1] += mono[:-d] * g * math.sin(ang) * 1.414
    return out


# —— PROCEDURAL DARK-FANTASY FOLEY BANK ——

def make_foley(ev_type):
    if ev_type == "fire_swell":
        d = 2.4
        crk = hp(sfx.noise(d), 2400) * (RNG.random(int(d * SR)) > 0.992) * 2.5
        bed = bp(sfx.brown(d), 120, 900) * 0.55
        return sfx.norm((bed + lp(crk, 6500)) * np.sin(np.pi * sfx.t_(d) / d))
    if ev_type == "banner_snap":
        d = 0.28
        tt = sfx.t_(d)
        return sfx.norm(bp(sfx.noise(d), 280, 2200) * np.exp(-tt * 14.0) + sfx.thump(0.5, 95)[: len(tt)])
    if ev_type == "cut_drum":
        d = 0.85
        tt = sfx.t_(d)
        body = np.sin(2 * np.pi * 64 * tt * (1 - 0.22 * tt)) * np.exp(-tt * 4.2)
        h2 = 0.45 * np.sin(2 * np.pi * 128 * tt) * np.exp(-tt * 6.5)
        skin = bp(sfx.noise(d), 300, 1800) * np.exp(-tt * 22.0) * 0.45
        return sfx.norm(body + h2 + skin)
    if ev_type == "goblet_clink":
        d = 0.32
        tt = sfx.t_(d)
        p = 0.92 + RNG.random() * 0.22
        ring = (
            0.6 * np.sin(2 * np.pi * 2480 * p * tt) * np.exp(-tt * 14.0)
            + 0.4 * np.sin(2 * np.pi * 3920 * p * tt) * np.exp(-tt * 22.0)
        )
        return sfx.norm(ring + sfx.click(1.4, 0.35)[: len(tt)] if len(tt) <= 2880 else np.pad(sfx.click(1.4, 0.35), (0, len(tt) - len(sfx.click()))) + ring)
    if ev_type == "cup_set":
        return sfx.clack(0.78, 0.85)
    if ev_type == "step_stone":
        d = 0.16
        tt = sfx.t_(d)
        heel = bp(sfx.noise(d), 450, 2600) * np.exp(-tt * 38.0)
        plate = 0.35 * np.sin(2 * np.pi * 1420 * tt) * np.exp(-tt * 45.0)
        th = 0.45 * np.sin(2 * np.pi * 105 * tt) * np.exp(-tt * 28.0)
        return sfx.norm(heel + plate + th)
    if ev_type == "step_wet":
        st = make_foley("step_stone")
        d = len(st) / SR
        tt = sfx.t_(d)
        squelch = bp(sfx.noise(d), 1400, 5200) * np.exp(-tt * 26.0) * 0.45
        return sfx.norm(st * 0.8 + squelch)
    if ev_type == "step_wood":
        d = 0.18
        tt = sfx.t_(d)
        wood = (
            0.6 * np.sin(2 * np.pi * 165 * tt) * np.exp(-tt * 24.0)
            + 0.4 * np.sin(2 * np.pi * 340 * tt) * np.exp(-tt * 32.0)
            + bp(sfx.noise(d), 300, 1600) * np.exp(-tt * 35.0) * 0.5
        )
        return sfx.norm(wood)
    if ev_type == "step_brush":
        d = 0.17
        tt = sfx.t_(d)
        return sfx.norm(bp(sfx.noise(d), 900, 4800) * np.exp(-tt * 20.0) + 0.3 * np.sin(2 * np.pi * 92 * tt) * np.exp(-tt * 28.0))
    if ev_type == "sword_turf":
        d = 0.55
        tt = sfx.t_(d)
        ring = 0.45 * np.sin(2 * np.pi * 1680 * tt) * np.exp(-tt * 7.5) + 0.25 * np.sin(2 * np.pi * 2890 * tt) * np.exp(-tt * 11.0)
        earth = bp(sfx.noise(d), 180, 1400) * np.exp(-tt * 14.0) * 0.8 + np.sin(2 * np.pi * 78 * tt) * np.exp(-tt * 12.0) * 0.6
        return sfx.norm(ring + earth)
    if ev_type == "sword_draw":
        d = 0.65
        tt = sfx.t_(d)
        scrape = bp(sfx.noise(d), 2200, 6500) * np.sin(np.pi * np.clip(tt / 0.42, 0, 1)) * 0.55
        zing = 0.55 * np.sin(2 * np.pi * (1450 + 620 * tt) * tt) * np.exp(-tt * 5.0)
        return sfx.norm(scrape + zing)
    if ev_type == "armor_settle":
        d = 0.26
        tt = sfx.t_(d)
        cloth = bp(sfx.noise(d), 500, 2400) * np.sin(np.pi * tt / d) * 0.6
        chink = 0.4 * np.sin(2 * np.pi * 1950 * tt) * np.exp(-tt * 28.0)
        return sfx.norm(cloth + chink)
    if ev_type == "curse_shudder":
        # First sound breaking Real Silence #1 at 25.00s!
        d = 2.6
        tt = sfx.t_(d)
        sub = (0.55 * np.sin(2 * np.pi * 46 * tt) + 0.50 * np.sin(2 * np.pi * 92 * tt) + 0.32 * np.sin(2 * np.pi * 138 * tt)) * np.exp(-tt * 1.25)
        glass = (0.38 * np.sin(2 * np.pi * 1480 * tt) + 0.34 * np.sin(2 * np.pi * 1568 * tt)) * np.exp(-tt * 1.8)
        rum = bp(sfx.brown(d), 55, 280) * np.exp(-tt * 1.4) * 0.55
        fade_in = np.clip(tt / 0.03, 0.0, 1.0)
        return sfx.norm((sub + glass + rum) * fade_in)
    if ev_type == "ichor_drip":
        d = 0.34
        tt = sfx.t_(d)
        f = 580 + 1350 * np.exp(-tt * 28.0) + 420 * (tt / d)
        drop = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 15.0)
        ring = 0.35 * np.sin(2 * np.pi * 2180 * tt) * np.exp(-tt * 11.0)
        return sfx.norm(drop + ring)
    if ev_type == "gate_groan":
        d = 1.6
        tt = sfx.t_(d)
        saw = 2.0 * ((tt * 58.0 * (1 + 0.08 * np.sin(2 * np.pi * 3.2 * tt))) % 1.0) - 1.0
        return sfx.norm(bp(saw, 120, 950) * np.sin(np.pi * tt / d) * 0.8 + bp(sfx.brown(d), 60, 260) * 0.5)
    if ev_type in ("chain_creak", "door_creak"):
        return sfx.creak(0.9)
    if ev_type == "ichor_hiss":
        d = 1.2
        tt = sfx.t_(d)
        return sfx.norm(bp(sfx.noise(d), 1600, 5800) * np.sin(np.pi * tt / d) ** 1.5)
    if ev_type == "bone_shift":
        # Sickening wet joint/vertebra elongation click (psychological body horror)
        d = 0.42
        tt = sfx.t_(d)
        snap1 = hp(sfx.noise(d), 1600) * np.exp(-tt * 65.0) * 0.9
        snap2 = np.roll(hp(sfx.noise(d), 1100) * np.exp(-tt * 50.0) * 0.7, int(0.085 * SR))
        snap2[: int(0.085 * SR)] = 0.0
        wet = bp(sfx.noise(d), 650, 2900) * np.sin(np.pi * np.clip(tt / 0.32, 0, 1)) * 0.48
        low = np.sin(2 * np.pi * 135 * tt) * np.exp(-tt * 22.0) * 0.5
        return sfx.norm(snap1 + snap2 + wet + low)
    if ev_type in ("hollow_rasp", "beast_rasp"):
        d = 1.15 if ev_type == "hollow_rasp" else 0.95
        tt = sfx.t_(d)
        formant1 = bp(sfx.noise(d), 380, 820) * (0.6 + 0.4 * np.sin(2 * np.pi * 19.0 * tt))
        formant2 = bp(sfx.noise(d), 1350, 2600) * 0.55
        sub_growl = np.sin(2 * np.pi * (88 - 18 * tt) * tt) * 0.35
        env = np.sin(np.pi * tt / d) ** 1.3
        return sfx.norm((formant1 + formant2 + sub_growl) * env)
    if ev_type == "sub_pulse":
        return sfx.heartbeat(0.95)
    if ev_type == "synth_riser":
        d = 0.82
        tt = sfx.t_(d)
        f = 95.0 * (2.0 ** (2.2 * (tt / d)))
        saw = 2.0 * ((np.cumsum(f) / SR) % 1.0) - 1.0
        return sfx.norm(lp(saw, 1900) * (tt / d) ** 1.6 + sfx.whoosh(d, 0.6))
    if ev_type == "shield_acid":
        d = 0.75
        tt = sfx.t_(d)
        clang = (0.6 * np.sin(2 * np.pi * 680 * tt) + 0.45 * np.sin(2 * np.pi * 1190 * tt)) * np.exp(-tt * 12.0)
        sizzle = bp(sfx.noise(d), 2200, 7200) * np.exp(-tt * 3.8) * 0.75
        th = sfx.thump(0.6, 85)
        th_pad = np.pad(th[: len(tt)], (0, max(0, len(tt) - len(th))))
        return sfx.norm(clang + sizzle + th_pad)
    if ev_type == "heavy_cleave":
        d = 0.95
        tt = sfx.t_(d)
        swish = sfx.whoosh(0.28, 0.85)
        imp_t = max(0, len(tt) - int(0.18 * SR))
        tt2 = sfx.t_(imp_t / SR)
        blade = (0.55 * np.sin(2 * np.pi * 920 * tt2) + 0.4 * np.sin(2 * np.pi * 1860 * tt2)) * np.exp(-tt2 * 8.5)
        burst = bp(sfx.noise(imp_t / SR), 120, 3400) * np.exp(-tt2 * 9.0) * 0.85
        sub = (0.6 * np.sin(2 * np.pi * 62 * tt2) + 0.4 * np.sin(2 * np.pi * 124 * tt2)) * np.exp(-tt2 * 7.0)
        out = np.zeros(len(tt))
        out[: len(swish)] += swish
        s0 = int(0.18 * SR)
        out[s0 : s0 + len(blade)] += blade + burst + sub
        return sfx.norm(out)
    if ev_type == "rune_ignite":
        d = 1.9
        tt = sfx.t_(d)
        chime = sum(
            a * np.sin(2 * np.pi * midi_hz(m) * tt) * np.exp(-tt / tau)
            for m, a, tau in [(62, 0.5, 1.4), (69, 0.55, 1.3), (74, 0.6, 1.1), (81, 0.4, 0.85), (86, 0.25, 0.6)]
        )
        shimmer = bp(sfx.noise(d), 1800, 6200) * np.exp(-tt * 2.5) * 0.25
        return sfx.norm(chime + shimmer)
    if ev_type in ("boss_impact", "stone_crack", "hall_door", "throne_shift", "title_carve"):
        d = 1.25
        tt = sfx.t_(d)
        sub = (0.55 * np.sin(2 * np.pi * 54 * tt) + 0.45 * np.sin(2 * np.pi * 108 * tt)) * np.exp(-tt * 3.2)
        crk = bp(sfx.noise(d), 180, 2600) * np.exp(-tt * 6.5) * 0.75
        return sfx.norm(sub + crk)
    if ev_type == "belfry_toll":
        return cathedral_bell(45, 2.2)
    if ev_type == "cathedral_bell":
        return cathedral_bell(38, 6.8)
    if ev_type == "caption_glyph":
        d = 0.45
        tt = sfx.t_(d)
        stone = bp(sfx.noise(d), 220, 950) * np.exp(-tt * 14.0) * 0.35
        tone = 0.5 * np.sin(2 * np.pi * midi_hz(50) * tt) * np.exp(-tt * 5.5)
        return sfx.norm(stone + tone) * 0.55
    return sfx.click(1.0, 0.3)


def build_score(dur):
    n_total = int(round(dur * SR))
    music = np.zeros((n_total, 2), dtype=np.float64)

    # —— MOVEMENT I (0.0–20.0s, 72 BPM): Muffled War-Horns + Fragile Tape-Warbled Reed Keyboard ——
    beat1 = 60.0 / 72.0  # 0.8333 s
    # Original D-Dorian -> D-Aeolian nostalgic progression: Dm9 | C6 | Bbmaj7 | Am7 | Gm7 | Dm/A
    chords_m1 = [
        (0.0, [50, 57, 60, 64]),
        (3.333, [48, 55, 57, 64]),
        (6.667, [46, 53, 57, 62]),
        (10.000, [45, 52, 57, 60]),
        (13.333, [50, 55, 58, 62]),
        (16.667, [50, 57, 62]),
    ]
    for t0, ch in chords_m1:
        cdur = 3.25 if t0 < 16.0 else 4.2
        pad = parlor_organ_pad(ch, cdur, cutoff=900.0 if t0 < 13.0 else 560.0)
        add_stereo(music, pad, t0, gain=0.19, pan=0.0)

    # Fragile warbled keyboard melody (original wistful intervals, thinning as Knight leaves the hall)
    mel_m1 = [
        (0.83, 69, 1.4), (2.50, 67, 0.8),
        (4.17, 64, 1.5), (5.83, 62, 0.8),
        (7.50, 65, 1.4), (9.17, 64, 0.8),
        (10.83, 60, 1.5), (12.50, 57, 1.4),
        (14.50, 62, 1.6), (16.67, 57, 2.2), (19.20, 50, 2.6),
    ]
    for idx, (t0, m, d) in enumerate(mel_m1):
        cutoff = 1650.0 if t0 < 14.0 else max(480.0, 1500.0 - (t0 - 14.0) * 165.0)
        note = warbled_reed_key(m, d, detune_depth=0.0052, bright=cutoff)
        add_stereo(music, note, t0, gain=0.28, pan=-0.18 if idx % 2 == 0 else 0.18)

    # Slow ceremonial frame drum in Act I (stops at 16.7s when Knight steps onto hill)
    t_drum = 0.0
    while t_drum < 16.5:
        hit = make_foley("cut_drum")
        add_stereo(music, lp(hit, 520.0), t_drum, gain=0.20, pan=0.0)
        t_drum += beat1 * 2.0

    # —— [22.50–25.00s: REAL SILENCE #1 — enforced strictly later] ——

    # —— MOVEMENT II (25.0–38.0s): Haunted Music-Box Droplets in Filtered Dark Echo ——
    mbox_layer = np.zeros((n_total, 2), dtype=np.float64)
    # Original unsettling Phrygian/minor-2nd droplets (A5-Bb5-E5-F5-D5)
    mbox_notes = [
        (26.20, 81, 1.2), (27.95, 82, 1.4), (29.90, 76, 1.5),
        (31.80, 77, 1.3), (33.40, 74, 1.8), (35.30, 73, 1.4), (36.80, 69, 1.6),
    ]
    for i, (t0, m, d) in enumerate(mbox_notes):
        add_stereo(mbox_layer, music_box_tine(m, d), t0, gain=0.27, pan=-0.25 if i % 2 == 0 else 0.25)

    # —— MOVEMENT III (38.0–68.0s, 64 BPM): Hollow Wooden Flute & Locrian Parlor Organ ——
    # 38.0–53.5s: Deserted street & Resident Evil cottage investigation
    organ_m3 = [
        (38.0, [50, 56, 62], 6.8),
        (45.0, [49, 55, 62], 6.3),
        (51.5, [50, 57, 63], 2.2),
    ]
    for t0, ch, d in organ_m3:
        add_stereo(music, parlor_organ_pad(ch, d, cutoff=780.0), t0, gain=0.17, pan=0.0)

    flute_m3 = [
        (38.9, 74, 1.7), (40.9, 75, 1.5), (42.8, 68, 2.0),
        (45.8, 72, 1.6), (47.8, 71, 1.4), (49.5, 65, 1.9),
        (51.9, 68, 1.5),
    ]
    for i, (t0, m, d) in enumerate(flute_m3):
        add_stereo(mbox_layer, hollow_wood_flute(m, d), t0, gain=0.26, pan=0.2 if i % 2 else -0.2)

    # 53.6–59.8s (Shot 10 body-horror elongation): Music thins to ONE trembling microtonal reed drone!
    n_hold = int(round(6.3 * SR))
    t_h = np.arange(n_hold) / SR
    bend = 1.0 + 0.018 * (t_h / 6.3) ** 2 + 0.004 * np.sin(2 * np.pi * 6.5 * t_h)
    ph_h = 2 * np.pi * np.cumsum(midi_hz(62) * bend) / SR
    reed_tension = lp(0.65 * np.sin(ph_h) + 0.35 * np.sin(2 * ph_h), 1200.0) * adsr(n_hold, 0.5, 0.2, 0.85, 0.4)
    add_stereo(music, reed_tension, 53.55, gain=0.19, pan=0.08)

    # 60.0–68.0s (Shot 11 crooked watchers): Dissonant cluster swell
    add_stereo(music, parlor_organ_pad([50, 56, 61, 65], 7.4, cutoff=1050.0), 60.1, gain=0.22, pan=0.0)
    for i, (t0, m) in enumerate([(62.4, 77), (64.1, 76), (65.8, 70)]):
        add_stereo(mbox_layer, music_box_tine(m, 1.5), t0, gain=0.25, pan=-0.2 + i * 0.2)

    music += snes_dark_echo(mbox_layer)

    # —— MOVEMENT IV (68.0–99.8s, 96 BPM): Nocturnal Dark-Fantasy Synth Pulse ——
    beat4 = 60.0 / 96.0      # 0.625 s
    eighth4 = beat4 * 0.5    # 0.3125 s
    # 12.8 bars of 4/4 (bar = 2.50s) from 68.0 to 99.8s
    # Bass progression per bar: Dm | Dm | Bb | C | Gm | Bb | A | Dm (repeats & escalates)
    bass_roots = [38, 38, 34, 36, 43, 34, 33, 38, 38, 41, 34, 33, 38]
    for bar_idx, root in enumerate(bass_roots):
        bar_t0 = 68.0 + bar_idx * 2.50
        if bar_t0 >= 99.6:
            break
        pattern = [0, 0, 12, 0, 7, 0, 10, 7]
        for step_i, semi in enumerate(pattern):
            nt = bar_t0 + step_i * eighth4
            if nt >= 99.55:
                break
            vel = 0.32 if step_i % 2 == 0 else 0.23
            add_stereo(music, retro_dark_bass(root + semi, eighth4 * 0.88), nt, gain=vel, pan=0.0)

        # Bit-crushed dark kick on beats 1 & 3, gated industrial snare on beats 2 & 4
        for b_i in range(4):
            bt = bar_t0 + b_i * beat4
            if bt >= 99.55:
                break
            if b_i in (0, 2):
                tt_k = sfx.t_(0.22)
                kick = (0.65 * np.sin(2 * np.pi * (95 * np.exp(-tt_k * 16) + 52) * tt_k) + 0.35 * np.sin(2 * np.pi * 116 * tt_k)) * np.exp(-tt_k * 11.0)
                click_k = bp(sfx.noise(0.22), 900, 3200) * np.exp(-tt_k * 55.0) * 0.35
                add_stereo(music, kick + click_k, bt, gain=0.28, pan=0.0)
            else:
                tt_s = sfx.t_(0.20)
                sn = bp(sfx.noise(0.20), 500, 4800) * np.exp(-tt_s * 15.0)
                sn = np.round(sn * 12.0) / 12.0  # subtle 90s retro bit-crush!
                add_stereo(music, sn, bt, gain=0.20, pan=0.05)

    # Haunting original dark-synth lead entering in woods & soaring through smithy & boss montage
    lead_m4 = [
        (69.25, 62, 1.2, None), (70.50, 65, 0.9, 62), (71.75, 69, 1.3, 65), (73.25, 67, 1.5, None),
        (75.50, 70, 1.1, 67),   (76.75, 69, 1.1, None), (78.00, 65, 1.2, None), (79.70, 74, 1.9, 69),
        (83.00, 69, 1.4, None), (84.50, 74, 1.4, 69), (86.00, 76, 1.2, None), (87.25, 77, 1.1, 76),
        (88.50, 74, 2.0, None), (90.70, 76, 2.0, 74), (92.90, 73, 1.9, 76),
        (95.00, 74, 2.4, 73),   (97.50, 69, 2.1, None),
    ]
    lead_bus = np.zeros((n_total, 2), dtype=np.float64)
    for i, (t0, m, d, gl) in enumerate(lead_m4):
        add_stereo(lead_bus, dark_synth_lead(m, d, glide_from=gl), t0, gain=0.23, pan=-0.15 if i % 2 == 0 else 0.15)
    music += snes_dark_echo(lead_bus)

    # —— [100.00–102.40s: REAL SILENCE #2 — enforced strictly later] ——

    # —— MOVEMENT V (102.4–120.0s): Moon Over the Crown & Dying Warbled Coda ——
    add_stereo(music, parlor_organ_pad([50, 57, 62, 69], 10.6, cutoff=920.0), 102.55, gain=0.22, pan=0.0)
    add_stereo(music, hollow_wood_flute(74, 3.2), 104.2, gain=0.20, pan=-0.18)
    add_stereo(music, hollow_wood_flute(73, 2.8), 109.2, gain=0.19, pan=0.18)

    # L-cut Coda over VALDRON title card (113.8–119.8s): broken nostalgic reed keyboard resolving into darkness
    coda_notes = [
        (113.80, 50, 5.2), (113.85, 57, 5.1), (114.35, 64, 4.6), (115.20, 65, 3.9), (116.40, 69, 3.1),
    ]
    for i, (t0, m, d) in enumerate(coda_notes):
        add_stereo(music, warbled_reed_key(m, d, detune_depth=0.006, bright=1050.0), t0, gain=0.24, pan=(i - 2) * 0.12)

    return music


def build_ambience(dur):
    n_total = int(round(dur * SR))
    amb = np.zeros((n_total, 2), dtype=np.float64)

    # 0.0–22.0s: Crackling distant bonfires & muffled victory hall murmur
    d1 = 22.2
    bed1 = bp(sfx.brown(d1), 95, 680) * 0.35
    sparks = hp(sfx.noise(d1), 2800) * (RNG.random(int(d1 * SR)) > 0.996) * 1.4
    env1 = np.ones(int(d1 * SR))
    env1[-int(3.5 * SR) :] = np.linspace(1.0, 0.0, int(3.5 * SR))
    add_stereo(amb, (bed1 + lp(sparks, 6000)) * env1, 0.0, gain=0.11, pan=-0.1)

    # 25.2–68.0s: Cold nocturnal ash-wind & hollow street draft
    d2 = 42.8
    tt2 = sfx.t_(d2)
    wind2 = bp(sfx.brown(d2), 140, 950) * (0.55 + 0.45 * np.sin(2 * np.pi * 0.14 * tt2))
    hiss2 = bp(sfx.noise(d2), 900, 2600) * (0.25 + 0.2 * np.sin(2 * np.pi * 0.21 * tt2 + 1.1))
    add_stereo(amb, wind2, 25.2, gain=0.09, pan=-0.2)
    add_stereo(amb, hiss2, 25.2, gain=0.04, pan=0.25)

    # 68.0–99.8s: Cursed canopy rustle & mill river rush
    d3 = 31.8
    tt3 = sfx.t_(d3)
    canopy = bp(sfx.noise(d3), 400, 2400) * (0.4 + 0.3 * np.sin(2 * np.pi * 0.31 * tt3))
    add_stereo(amb, canopy, 68.0, gain=0.055, pan=0.0)

    # 102.5–119.4s: High citadel wind & cavern air
    d4 = 16.9
    tt4 = sfx.t_(d4)
    air4 = bp(sfx.brown(d4), 110, 720) * np.sin(np.pi * tt4 / d4)
    add_stereo(amb, air4, 102.5, gain=0.08, pan=0.0)

    return amb


def enforce_silences(buf, silences):
    """Guarantee true digital zero inside designated dramatic silences with click-free 45ms cosine ramps."""
    ramp = int(0.045 * SR)
    for t0, t1 in silences:
        s0 = max(0, int(round(t0 * SR)))
        s1 = min(len(buf), int(round(t1 * SR)))
        if s0 >= s1:
            continue
        # Ramp down before s0
        r0 = max(0, s0 - ramp)
        if s0 > r0:
            w = 0.5 * (1.0 + np.cos(np.linspace(0.0, math.pi, s0 - r0)))[:, None]
            buf[r0:s0] *= w
        # Exact zero across [s0, s1]
        buf[s0:s1] = 0.0
        # Ramp up after s1
        r1 = min(len(buf), s1 + ramp)
        if r1 > s1:
            w = 0.5 * (1.0 - np.cos(np.linspace(0.0, math.pi, r1 - s1)))[:, None]
            buf[s1:r1] *= w


def main():
    timeline = json.loads((HERE / "timeline.json").read_text())
    ev_path = HERE / "events.json"
    events = json.loads(ev_path.read_text())["ev"] if ev_path.exists() else []
    dur = float(timeline["dur"])
    n_total = int(round(dur * SR))

    music = build_score(dur)
    amb = build_ambience(dur)
    foley = np.zeros((n_total, 2), dtype=np.float64)

    for ev in events:
        sig = make_foley(ev["type"])
        add_stereo(foley, sig, float(ev["t"]), gain=float(ev.get("gain", 1.0)) * 0.42, pan=float(ev.get("pan", 0.0)))

    # Duck music subtly (-3.5 dB) under major foley impacts (cleave, curse shudder, bell, bone-shifts)
    foley_env = lp(np.abs(foley[:, 0]) + np.abs(foley[:, 1]), 14.0)
    duck = 1.0 / (1.0 + 2.2 * np.clip(foley_env - 0.08, 0.0, 1.0))
    mix = music * duck[:, None] + amb + foley

    # Balance low-end (20–120 Hz vs 120–16000 Hz per TECHNIQUE.md §5)
    mono = 0.5 * (mix[:, 0] + mix[:, 1])
    rms_low = math.sqrt(float(np.mean(bp(mono, 22, 120) ** 2)) + 1e-12)
    rms_rest = math.sqrt(float(np.mean(bp(mono, 120, 15000) ** 2)) + 1e-12)
    low_ratio_db = 20.0 * math.log10(rms_low / rms_rest)
    if low_ratio_db > -2.2:
        # Trim sub-115 Hz gently so bass stays punchy without mud
        sub_bandL = lp(mix[:, 0], 115.0)
        sub_bandR = lp(mix[:, 1], 115.0)
        trim = 1.0 - min(0.55, (low_ratio_db - (-3.0)) * 0.08)
        mix[:, 0] = (mix[:, 0] - sub_bandL) + sub_bandL * trim
        mix[:, 1] = (mix[:, 1] - sub_bandR) + sub_bandR * trim

    # Enforce the two true silences ([22.5, 25.0] and [100.0, 102.4]) + clean end fade at 119.85–120.0s
    enforce_silences(mix, timeline["silences"])
    end_fade = int(0.35 * SR)
    mix[-end_fade:] *= np.linspace(1.0, 0.0, end_fade)[:, None]
    mix[-int(0.08 * SR) :] = 0.0

    # Gentle bus compression + look-ahead peak limiting so linear loudnorm hits -14.0 LUFS / -1.2 dBTP cleanly
    sub_warmL = lp(mix[:, 0], 115.0) * 0.22
    sub_warmR = lp(mix[:, 1], 115.0) * 0.22
    mix[:, 0] += sub_warmL
    mix[:, 1] += sub_warmR
    peak = float(np.max(np.abs(mix)))
    if peak > 0:
        mix = mix * (0.72 / peak)
    mix[:, 0] = sfx.limit(sfx.compress(mix[:, 0], thr=0.28, ratio=2.8, att=0.006, rel=0.12), ceil=0.54)
    mix[:, 1] = sfx.limit(sfx.compress(mix[:, 1], thr=0.28, ratio=2.8, att=0.006, rel=0.12), ceil=0.54)
    # Re-zero the exact inner silence windows after dynamics
    for t0, t1 in timeline["silences"]:
        s0 = int(round((t0 + 0.05) * SR))
        s1 = int(round((t1 - 0.05) * SR))
        mix[s0:s1] = 0.0

    out_dir = HERE / "work"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_wav = out_dir / "mix.wav"
    sf.write(str(out_wav), mix.astype(np.float32), SR, subtype="PCM_16")

    mono_f = 0.5 * (mix[:, 0] + mix[:, 1])
    rms_low2 = math.sqrt(float(np.mean(bp(mono_f, 22, 120) ** 2)) + 1e-12)
    rms_rest2 = math.sqrt(float(np.mean(bp(mono_f, 120, 15000) ** 2)) + 1e-12)
    sil1_max = float(np.max(np.abs(mix[int(22.6 * SR) : int(24.9 * SR)])))
    sil2_max = float(np.max(np.abs(mix[int(100.1 * SR) : int(102.3 * SR)])))
    print(
        f"wrote {out_wav} ({dur:.1f}s @ {SR}Hz) | "
        f"low/rest={20*math.log10(rms_low2/rms_rest2):.2f} dB | "
        f"silence1_peak={sil1_max:.6f} | silence2_peak={sil2_max:.6f} | "
        f"events_mixed={len(events)}"
    )


if __name__ == "__main__":
    main()
