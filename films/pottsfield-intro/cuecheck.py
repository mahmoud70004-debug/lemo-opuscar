"""Verify 0 ms cue alignment between picture timeline and audio mix, plus silence depth checks."""
import json
import math
import os
import sys
import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    tl = json.load(open(os.path.join(HERE, "timeline.json"), encoding="utf-8"))
    ac = json.load(open(os.path.join(HERE, "out", "audio_cues.json"), encoding="utf-8"))
    wav, sr = sf.read(os.path.join(HERE, "out", "mix.wav"))

    placed = {c["id"]: c["t_audio"] for c in ac["cues"]}
    max_ms = 0.0
    missing = []
    for cid, spec in tl["cues"].items():
        if cid not in placed:
            missing.append(cid)
            continue
        diff_ms = abs(placed[cid] - spec["t"]) * 1000.0
        max_ms = max(max_ms, diff_ms)

    if missing:
        sys.exit(f"FAIL: cues missing from mix.py: {missing}")
    if max_ms > 1.0:
        sys.exit(f"FAIL: max cue drift {max_ms:.2f} ms > 1.0 ms")

    print(f"✓ Cues verified: {len(tl['cues'])}/{len(tl['cues'])} cues aligned, max offset = {max_ms:.2f} ms")

    for s in tl["silences"]:
        i0, i1 = int(s["t0"] * sr), int(s["t1"] * sr)
        seg = wav[i0:i1]
        rms_db = 20.0 * math.log10(float(np.sqrt(np.mean(seg ** 2))) + 1e-12)
        ok = rms_db <= s["max_rms_db"]
        print(f"{'✓' if ok else '✗'} Silence '{s['id']}' [{s['t0']:.2f}s..{s['t1']:.2f}s]: {rms_db:.1f} dBFS (limit {s['max_rms_db']:.1f} dBFS)")
        if not ok:
            sys.exit(f"FAIL: silence {s['id']} too loud ({rms_db:.1f} dBFS)")


if __name__ == "__main__":
    main()
