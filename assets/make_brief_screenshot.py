#!/usr/bin/env python3
"""Screenshot of the real demo brief (decentralized-ai-inference-2026-11-21.md).

Procedural render of verbatim excerpts from the actual brief file:
title, summary paragraph, and the three dated sources. No AI generation.
"""
import textwrap

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 900
BG = (238, 235, 247)
CARD = (255, 255, 255)
INK = (30, 27, 75)
MUTED = (107, 103, 135)
VIOLET = (124, 58, 237)
LINE = (226, 222, 240)

F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

title_f = ImageFont.truetype(FB, 34)
meta_f = ImageFont.truetype(F, 20)
h_f = ImageFont.truetype(FB, 23)
body_f = ImageFont.truetype(F, 21)
small_f = ImageFont.truetype(F, 18)

SUMMARY = (
    "Three articles from October\u2013November 2026 highlight the maturing decentralized "
    "AI inference landscape: a backend engineer argues that reliable job-queue primitives "
    "(retries, idempotency, timeouts) are the missing layer to make decentralized GPU "
    "inference feel like a normal cloud service (Nov 5); Antseed launches a peer-to-peer "
    "marketplace backed by a $2.4M Spark Capital-led round, letting developers tap frontier "
    "models at a fraction of centralized prices (Oct 6); and Cysic pivots its GPU fleet from "
    "ZK-proof generation to AI inference after L2 fee economics eroded its original "
    "business (Nov 3)."
)
SOURCES = [
    ("Decentralized AI Inference Needs a Boring Job Queue", "HackerNoon, 5 Nov 2026"),
    ("Antseed launches a decentralized marketplace for AI inference", "SiliconAngle, 6 Oct 2026"),
    ("Cysic shifts focus to AI inference as ZK proving demand fades", "CryptoBriefing, 3 Nov 2026"),
]

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# card
x0, y0, x1, y1 = 48, 40, W - 48, H - 40
d.rounded_rectangle([x0, y0, x1, y1], radius=24, fill=CARD)
# top accent bar
d.rounded_rectangle([x0, y0, x1, y0 + 10], radius=5, fill=VIOLET)

x = x0 + 56
y = y0 + 44
# header chip
d.rounded_rectangle([x, y, x + 150, y + 34], radius=17, fill=(237, 233, 254))
d.text((x + 18, y + 6), "BRIEFMINION", font=ImageFont.truetype(FB, 16), fill=VIOLET)
y += 56
d.text((x, y), "Research brief: decentralized AI inference", font=title_f, fill=INK)
y += 52
d.text((x, y), "Generated 2026-11-21  ·  OpenMinion 0.1 Python SDK  ·  3 sources, all dated",
       font=meta_f, fill=MUTED)
y += 44
d.line([(x, y), (x1 - 56, y)], fill=LINE, width=2)
y += 28

# Summary
d.text((x, y), "Summary", font=h_f, fill=VIOLET)
y += 38
for line in textwrap.wrap(SUMMARY, 92):
    d.text((x, y), line, font=body_f, fill=INK)
    y += 30
y += 22
d.line([(x, y), (x1 - 56, y)], fill=LINE, width=2)
y += 28

# Sources
d.text((x, y), "Sources", font=h_f, fill=VIOLET)
y += 38
for title, src in SOURCES:
    d.ellipse([x + 4, y + 8, x + 14, y + 18], fill=VIOLET)
    d.text((x + 26, y), title, font=body_f, fill=INK)
    y += 30
    d.text((x + 26, y), src, font=small_f, fill=MUTED)
    y += 36
y += 8
d.line([(x, y), (x1 - 56, y)], fill=LINE, width=2)
y += 24
d.text((x, y), "briefs/decentralized-ai-inference-2026-11-21.md   ·   research 160s / digest 86s / compose 60s",
       font=small_f, fill=MUTED)

img.save("brief-screenshot-1280.png", "PNG")
print("saved brief-screenshot-1280.png")
