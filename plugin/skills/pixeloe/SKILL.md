---
name: pixeloe
description: High-density, detail-oriented pixel art synthesis and image pixelization via Contrast-Aware Outline Expansion (KohakuBlueleaf/PixelOE, Apache-2.0) combined with CIELAB weighted K-means palette quantization and ordered Bayer dithering. Use whenever converting high-res artwork/screenshots into crisp, ultra-detailed pixel art without blurry mixels or lost thin outlines.
---

# PixelOE — Detail-Oriented Contrast-Aware Pixelization

Bundled from [`KohakuBlueleaf/PixelOE`](https://github.com/KohakuBlueleaf/PixelOE) (`Apache-2.0`, `lib/` contains the pure Python/NumPy/OpenCV pipeline).

## Why Standard Downsampling Fails High-Density Pixel Art
Naive nearest-neighbor or bilinear downsampling destroys 1-pixel ink outlines, sword edges, eyes, and gothic architectural filigree. **PixelOE** solves this in four deterministic stages:
1. **Contrast-Aware Outline Expansion (`lib/outline.py`)**: Detects local luminance/contrast extrema in sliding patches and morphologically expands dark ink lines and bright highlights *before* downscaling so fine silhouettes survive intact.
2. **Contrast-Aware Downsampling (`lib/downscale.py`)**: `mode="contrast"` (or `"k-centroid"`) selects representative texels preserving local edge contrast rather than averaging into muddy grays.
3. **Weighted CIELAB K-Means Quantization (`lib/color.py`)**: Maps colors to a disciplined 24–64 color palette weighted by perceptual edge importance, followed by optional ordered **Bayer 4×4 / 8×8 dithering**.
4. **Integer Nearest-Neighbor Upscaling**: Scales the logical pixel grid (`360×640` × `3` = `1080×1920`, or `540×960` × `2` = `1080×1920`) with `INTER_NEAREST` / `imageSmoothingEnabled = false` so every pixel is an exact integer square (`0` mixels).

## Python Usage (`plugin/skills/pixeloe/lib`)

```python
import cv2
from plugin.skills.pixeloe.lib.pixelize import pixelize

bgr = cv2.imread("source.jpg")
# Ultra-dense 360x640 logical grid (upscales 3x to 1080x1920)
px_low = pixelize(
    bgr,
    mode="contrast",
    target_size=(640, 360),  # (H, W) logical pixel resolution
    patch_size=4,
    thickness=2,             # expand crisp dark ink outlines
    colors=40,               # tight dark-fantasy palette
    colors_with_weight=True,
    no_upscale=True,         # keep exact logical grid for pixel-level animation!
)
```

## Golden Rules for High-Density Dark-Fantasy Pixel Video
- **Logical Grid Discipline**: For `1080×1920` (`9:16`) vertical reels, author on an exact divisor grid:
  - **`360×640` (`×3` integer scale)** — classic PC-98 / *Blasphemous* / *Vermis* high-density pixel art where individual pixel clusters, Bayer 4×4 dithering, and 1px black outlines read crisply on mobile screens.
  - **`540×960` (`×2` integer scale)** — ultra-fine micro-pixel density for wide architectural vistas.
- **Animate on the Logical Grid First**: Render parallax shifts, animated rain streaks, torchlight/moonlight Bayer dither flicker, cape wind, eye blinks, and sword-slash sprite arcs in integer logical coordinates (`Math.round`), then upscale once to `1080×1920` with `ctx.imageSmoothingEnabled = false`.
