#!/usr/bin/env python3
"""BriefMinion logo — procedural, no AI generation.

Concept: a validated research brief. White document (the brief) with a
folded corner, text lines, and a violet approval seal with a checkmark
(human approval before writing to disk). A thin orbit ring with 4 dots
around it = the 4 phases (research, digest, compose, save).
Background: deep indigo -> violet gradient with a soft glow and a faint
dot grid (live sources / network).
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SS = 2            # supersample factor
W = 1024 * SS     # work size
OUT = "briefminion-logo-1024.png"


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def main():
    # ---- background: diagonal gradient + radial glow (numpy) ----
    yy, xx = np.mgrid[0:W, 0:W].astype(np.float32)
    t = (xx + yy) / (2 * W)  # 0 top-left -> 1 bottom-right
    c1 = np.array([22, 11, 46], dtype=np.float32)    # deep indigo
    c2 = np.array([76, 29, 149], dtype=np.float32)   # violet
    img = c1[None, None, :] + (c2 - c1)[None, None, :] * t[:, :, None]
    # radial glow behind center
    cx, cy = W * 0.5, W * 0.46
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (W * 0.62)
    glow = np.clip(1 - r, 0, 1) ** 2 * 46
    img += glow[:, :, None] * np.array([0.62, 0.42, 1.0], dtype=np.float32)
    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

    # ---- faint dot grid ----
    grid = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    step = 72 * SS
    for gx in range(step // 2, W, step):
        for gy in range(step // 2, W, step):
            r0 = 3.5 * SS
            gd.ellipse([gx - r0, gy - r0, gx + r0, gy + r0], fill=(255, 255, 255, 16))
    base.alpha_composite(grid)

    # ---- orbit ring (tilted ellipse) + 4 phase dots ----
    orbit = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    od = ImageDraw.Draw(orbit)
    rx, ry = 430 * SS, 300 * SS
    od.ellipse([W / 2 - rx, W / 2 - ry, W / 2 + rx, W / 2 + ry],
               outline=(255, 255, 255, 80), width=5 * SS)
    orbit = orbit.rotate(16, resample=Image.BICUBIC, center=(W / 2, W / 2))
    base.alpha_composite(orbit)
    # dots on the rotated ellipse
    dots = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dots)
    ang = math.radians(-16)
    for deg, col in [(30, (255, 255, 255, 255)),
                     (120, (196, 181, 253, 255)),
                     (210, (167, 139, 250, 255)),
                     (300, (255, 255, 255, 255))]:
        a = math.radians(deg)
        ex, ey = rx * math.cos(a), ry * math.sin(a)
        # rotate by -16 deg (PIL rotate(16) is counter-clockwise in image coords)
        px = ex * math.cos(ang) - ey * math.sin(ang)
        py = ex * math.sin(ang) + ey * math.cos(ang)
        x, y = W / 2 + px, W / 2 + py
        r0 = 13 * SS
        dd.ellipse([x - r0, y - r0, x + r0, y + r0], fill=col)
    base.alpha_composite(dots)

    # ---- document shadow ----
    sh = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    doc = [312 * SS, 300 * SS, 712 * SS, 724 * SS]
    sd.rounded_rectangle([doc[0] + 10 * SS, doc[1] + 18 * SS,
                          doc[2] + 10 * SS, doc[3] + 18 * SS],
                         radius=36 * SS, fill=(0, 0, 0, 110))
    sh = sh.filter(ImageFilter.GaussianBlur(18 * SS))
    base.alpha_composite(sh)

    # ---- document ----
    d = ImageDraw.Draw(base)
    d.rounded_rectangle(doc, radius=36 * SS, fill=(255, 255, 255, 255))
    # folded corner (top-right)
    fx0, fy0 = 640 * SS, 300 * SS
    fx1, fy1 = 712 * SS, 372 * SS
    d.polygon([(fx0, fy0), (fx1, fy0), (fx1, fy1)], fill=(220, 214, 240, 255))
    d.line([(fx0, fy0), (fx1, fy1)], fill=(196, 181, 253, 255), width=4 * SS)
    # title bar
    d.rounded_rectangle([352 * SS, 352 * SS, 560 * SS, 376 * SS],
                        radius=12 * SS, fill=(124, 58, 237, 255))
    # text lines
    for y, wdt in [(424, 320), (472, 320), (520, 244), (568, 284)]:
        d.rounded_rectangle([352 * SS, y * SS, (352 + wdt) * SS, (y + 20) * SS],
                            radius=10 * SS, fill=(139, 135, 184, 255))

    # ---- approval seal (violet circle + white check) ----
    seal_c = (672 * SS, 664 * SS)
    sr = 92 * SS
    d.ellipse([seal_c[0] - sr, seal_c[1] - sr, seal_c[0] + sr, seal_c[1] + sr],
              fill=(124, 58, 237, 255), outline=(255, 255, 255, 255), width=10 * SS)
    d.line([(624 * SS, 664 * SS), (656 * SS, 696 * SS), (724 * SS, 624 * SS)],
           fill=(255, 255, 255, 255), width=26 * SS, joint="curve")

    # ---- downscale to 1024 HD + save ----
    out = base.convert("RGB").resize((1024, 1024), Image.LANCZOS)
    out.save(OUT, "PNG")
    print("saved", OUT)


if __name__ == "__main__":
    main()
