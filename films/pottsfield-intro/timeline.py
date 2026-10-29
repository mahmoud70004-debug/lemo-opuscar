"""Single source of truth for Pottsfield Studio 10s Official Intro timeline, beats, and audio-visual cues."""
import json
import os

FPS = 30
DUR = 10.0
TOTAL_FRAMES = int(round(DUR * FPS))  # 300 frames exact
BPM = 120.0
BEAT_SEC = 60.0 / BPM                 # 0.500 s = 15 frames exact
BAR_SEC = 4.0 * BEAT_SEC              # 2.000 s = 60 frames exact


def beat_to_sec(beat: float) -> float:
    return round(beat * BEAT_SEC, 6)


SECTIONS = [
    {"id": "woodcut_2d",   "bar": 1, "t0": 0.00, "t1": 2.15, "bpm": 120, "desc": "Act I: 2D woodcut relief carving in darkness"},
    {"id": "hush_spark",   "bar": 2, "t0": 2.15, "t1": 3.00, "bpm": 120, "desc": "Silence #1 breath + 2.75s eye spark anticipation"},
    {"id": "ignite_3d",    "bar": 2, "t0": 3.00, "t1": 4.75, "bpm": 120, "desc": "Act II: 2D->3D volumetric fire ignition & parallax"},
    {"id": "crane_dock",   "bar": 3, "t0": 4.75, "t1": 6.00, "bpm": 120, "desc": "3D crane pull-back + Silence #2 pre-lockup inhale"},
    {"id": "crest_bloom",  "bar": 4, "t0": 6.00, "t1": 7.40, "bpm": 120, "desc": "Act III: Crest vines, pumpkins, ring & Pottsfield STUDIO bloom"},
    {"id": "official_hold","bar": 5, "t0": 7.40, "t1": 10.00,"bpm": 120, "desc": "Living official emblem hold & clean boot fade to black"},
]

# Canonical visual & audio cues locked to the 120 BPM grid
CUES = {
    "wind_jcut_in":       {"beat": 0.0,  "t": beat_to_sec(0.0),  "type": "ambience", "pan":  0.00, "desc": "Cold autumn wind rises in darkness (J-cut)"},
    "carve_stem_strike":  {"beat": 0.5,  "t": beat_to_sec(0.5),  "type": "carve",    "pan":  0.04, "desc": "First woodcut gouge strikes twisted stem"},
    "carve_ribs_sweep":   {"beat": 1.25, "t": beat_to_sec(1.25), "type": "carve",    "pan": -0.10, "desc": "Curved gouges sweep down upper pumpkin ribs"},
    "cut_frontal_plate":  {"beat": 2.0,  "t": beat_to_sec(2.0),  "type": "plate_cut","pan":  0.00, "desc": "Hard print-registration cut to frontal Close-Up + brow carve"},
    "carve_grin_slice":   {"beat": 3.0,  "t": beat_to_sec(3.0),  "type": "carve",    "pan":  0.08, "desc": "9-tooth wicked grin carved symmetrically"},
    "silence_1_start":    {"beat": 4.3,  "t": beat_to_sec(4.3),  "type": "silence",  "pan":  0.00, "desc": "Real Silence #1 begins (near-silent tension)"},
    "eye_spark_ping":     {"beat": 5.5,  "t": beat_to_sec(5.5),  "type": "spark",    "pan": -0.22, "desc": "Single celesta A5 + flint spark in left eye"},
    "ignite_3d_boom":     {"beat": 6.0,  "t": beat_to_sec(6.0),  "type": "ignite",   "pan":  0.00, "desc": "TURN: 2D->3D inner fire explosion & volumetric god-rays"},
    "ember_swirl_gust":   {"beat": 7.0,  "t": beat_to_sec(7.0),  "type": "embers",   "pan":  0.18, "desc": "3D bokeh embers & autumn leaves swirl upward"},
    "motif_phrase_a":     {"beat": 8.0,  "t": beat_to_sec(8.0),  "type": "music",    "pan":  0.00, "desc": "Haunted autumn music-box & lute motif peaks"},
    "crane_pullback":     {"beat": 9.5,  "t": beat_to_sec(9.5),  "type": "camera",   "pan":  0.00, "desc": "Camera cranes up & pulls back toward full crest"},
    "silence_2_inhale":   {"beat": 11.3, "t": beat_to_sec(11.3), "type": "inhale",   "pan":  0.00, "desc": "Near-silence #2 reverse-ember inhale before lockup"},
    "crest_throne_lock":  {"beat": 12.0, "t": beat_to_sec(12.0), "type": "lockup",   "pan":  0.00, "desc": "Hero pumpkin docks in crest; vines & ring sprout"},
    "side_pumpkins_pop":  {"beat": 12.5, "t": beat_to_sec(12.5), "type": "foliage",  "pan":  0.00, "desc": "4 companion pumpkins & autumn maple leaves awaken"},
    "pottsfield_blaze":   {"beat": 13.0, "t": beat_to_sec(13.0), "type": "title",    "pan": -0.15, "desc": "Gothic 'Pottsfield' wordmark blazes across upper arch"},
    "studio_lock_chime":  {"beat": 14.5, "t": beat_to_sec(14.5), "type": "title",    "pan":  0.00, "desc": "'S T U D I O' crimson sub-title locks in"},
    "fade_to_boot_black": {"beat": 18.9, "t": beat_to_sec(18.9), "type": "fade",     "pan":  0.00, "desc": "Clean game-boot fade to pure #000000 black"},
}

SILENCES = [
    {"id": "pre_spark_hush",  "t0": 2.20, "t1": 2.72, "max_rms_db": -42.0},
    {"id": "pre_crest_inhale","t0": 5.68, "t1": 5.96, "max_rms_db": -26.0},
]


def export_json(out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    tl_path = os.path.join(out_dir, "timeline.json")
    ev_path = os.path.join(out_dir, "events.json")
    data = {
        "fps": FPS,
        "duration": DUR,
        "total_frames": TOTAL_FRAMES,
        "bpm": BPM,
        "beat_sec": BEAT_SEC,
        "bar_sec": BAR_SEC,
        "sections": SECTIONS,
        "cues": CUES,
        "silences": SILENCES,
    }
    with open(tl_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    events = [
        {"id": k, "t": v["t"], "beat": v["beat"], "type": v["type"], "pan": v["pan"], "desc": v["desc"]}
        for k, v in sorted(CUES.items(), key=lambda kv: kv[1]["t"])
    ]
    with open(ev_path, "w", encoding="utf-8") as f:
        json.dump({"duration": DUR, "fps": FPS, "events": events}, f, indent=2)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    export_json(here)
    print(f"Exported timeline.json & events.json ({len(CUES)} cues, {TOTAL_FRAMES} frames @ {FPS} fps)")
