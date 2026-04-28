"""Generate a 700x450 DMG background image."""
from PIL import Image, ImageDraw

W, H = 700, 450

# ── Colours ──────────────────────────────────────────────────────────────────
BG_TOP    = (245, 245, 247)   # near-white (Apple-ish)
BG_BOT    = (225, 226, 230)   # slightly darker at the bottom
DIVIDER   = (200, 201, 205)
ARROW_CLR = (160, 162, 168)
LABEL_CLR = (120, 122, 128)

img  = Image.new("RGB", (W, H))
draw = ImageDraw.Draw(img)

# ── Vertical gradient background ─────────────────────────────────────────────
for y in range(H):
    t = y / (H - 1)
    r = int(BG_TOP[0] + t * (BG_BOT[0] - BG_TOP[0]))
    g = int(BG_TOP[1] + t * (BG_BOT[1] - BG_TOP[1]))
    b = int(BG_TOP[2] + t * (BG_BOT[2] - BG_TOP[2]))
    draw.line([(0, y), (W, y)], fill=(r, g, b))

# ── Subtle horizontal divider between the two icon rows ──────────────────────
# row 1 midpoint ~150, row 2 midpoint ~320; divider sits between them at y=238
draw.line([(40, 238), (W - 40, 238)], fill=DIVIDER, width=1)

# ── Arrow from app (150,150) → Applications (550,150) ────────────────────────
# Drawn as a wide, gentle shape so it's visible under the icons but unobtrusive
ax1, ax2, ay = 220, 480, 150     # start x, end x, y (below icon centres)
arrow_y = ay + 20                 # sit just below the icon row

# shaft
draw.rectangle([(ax1, arrow_y - 3), (ax2, arrow_y + 3)], fill=ARROW_CLR)

# arrowhead (right-pointing triangle)
head = [(ax2, arrow_y - 11), (ax2 + 20, arrow_y), (ax2, arrow_y + 11)]
draw.polygon(head, fill=ARROW_CLR)

# ── "Drag to install" label centred on the arrow ─────────────────────────────
label   = "drag to install"
font_sz = 13
# PIL default font; scale by drawing individual pixels isn't practical —
# use the built-in bitmap font which is small but sufficient.
try:
    from PIL import ImageFont
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_sz)
except Exception:
    font = ImageFont.load_default()

bbox  = draw.textbbox((0, 0), label, font=font)
tw    = bbox[2] - bbox[0]
tx    = (ax1 + ax2) // 2 - tw // 2
ty    = arrow_y + 10
draw.text((tx, ty), label, fill=LABEL_CLR, font=font)

# ── Save ─────────────────────────────────────────────────────────────────────
out = "assets/dmg-background.png"
img.save(out, "PNG")
print(f"Saved {W}x{H} → {out}")
