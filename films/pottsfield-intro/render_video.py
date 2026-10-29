"""Parallel deterministic frame renderer piping RGB24 frames directly to ffmpeg."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import os
import subprocess
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from timeline import FPS, TOTAL_FRAMES
from engine import PottsfieldEngine

_WORKER_ENG = None


def _init_worker():
    global _WORKER_ENG
    cv2.setNumThreads(1)
    _WORKER_ENG = PottsfieldEngine()


def _render_one(args):
    idx, w, h = args
    t = idx / float(FPS)
    rgb = _WORKER_ENG.render_frame(t, w, h)
    return idx, rgb.tobytes()


def render_mp4(w: int, h: int, out_mp4: str, poster_jpg: str | None = None, workers: int = 2):
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
    poster_frame_idx = int(round(8.00 * FPS))

    try:
        with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as pool:
            for idx, raw_bytes in pool.map(_render_one, tasks, chunksize=4):
                proc.stdin.write(raw_bytes)
                if poster_jpg and idx == poster_frame_idx:
                    arr = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((h, w, 3))
                    Image.fromarray(arr).save(poster_jpg, quality=94)
                if (idx + 1) % 60 == 0 or idx + 1 == TOTAL_FRAMES:
                    el = time.time() - t0
                    print(f"  [{w}x{h}] {idx + 1}/{TOTAL_FRAMES} frames ({el:.1f}s)", flush=True)
    finally:
        if proc.stdin:
            proc.stdin.close()
        rc = proc.wait()
        if rc != 0:
            sys.exit(f"ffmpeg rawvideo encode failed with exit code {rc}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="1920x1080", help="WxH resolution")
    ap.add_argument("--out", required=True, help="Output silent video MP4 path")
    ap.add_argument("--poster", default="", help="Optional poster JPG path")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()

    w_s, h_s = args.size.lower().split("x")
    w, h = int(w_s), int(h_s)
    render_mp4(w, h, args.out, poster_jpg=args.poster or None, workers=args.workers)


if __name__ == "__main__":
    main()
