import os
from PIL import Image, ImageDraw, ImageFilter
​
CARD_W = 1440
CARD_H = 2160
TEMPLATE_DIR = "assets/templates"
THEMES = {
"mvp": {
"top": (10, 28, 70),
"bottom": (190, 140, 20),
"accent": (255, 220, 80),
"glow": (40, 150, 255),
"label": "MVP",
},
"fraud": {
"top": (35, 0, 0),
"bottom": (150, 10, 20),
"accent": (255, 70, 70),
"glow": (255, 30, 30),
"label": "FRAUD",
},
"ghost": {
"top": (5, 5, 18),
"bottom": (45, 35, 75),
"accent": (180, 180, 255),
"glow": (120, 80, 255),
"label": "GHOST",
},
"carry": {
"top": (20, 5, 45),
"bottom": (95, 30, 170),
"accent": (220, 170, 255),
"glow": (175, 70, 255),
"label": "CARRY",
},
"court_case": {
"top": (25, 16, 8),
"bottom": (130, 85, 35),
"accent": (255, 210, 130),
"glow": (255, 170, 60),
"label": "COURT CASE",
},
"ball_loser": {
"top": (35, 15, 0),
"bottom": (185, 75, 10),
"accent": (255, 165, 60),
"glow": (255, 110, 20),
"label": "BALL LOSER",
},
"playmaker": {
"top": (0, 22, 36),
"bottom": (0, 110, 150),
"accent": (130, 245, 255),
"glow": (0, 220, 255),
"label": "PLAYMAKER",
},
"sniper": {
"top": (5, 5, 8),
"bottom": (55, 55, 65),
"accent": (245, 245, 245),
"glow": (255, 40, 40),
"label": "SNIPER",
},
}
def make_gradient(top_color, bottom_color):
img = Image.new("RGBA", (CARD_W, CARD_H))
for y in range(CARD_H):
ratio = y / max(CARD_H - 1, 1)
r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)
for x in range(CARD_W):
img.putpixel((x, y), (r, g, b, 255))
return img
def add_glow(img, color, center, radius, alpha):
layer = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
draw = ImageDraw.Draw(layer)
cx, cy = center
draw.ellipse(
[cx - radius, cy - radius, cx + radius, cy + radius],
fill=(color[0], color[1], color[2], alpha),
)
layer = layer.filter(ImageFilter.GaussianBlur(radius // 4))
img.alpha_composite(layer)
def add_lines(img, color):
layer = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
draw = ImageDraw.Draw(layer)
for x in range(-CARD_H, CARD_W, 110):
draw.line(
[(x, CARD_H), (x + CARD_H, 0)],
fill=(color[0], color[1], color[2], 35),
width=4,
)
img.alpha_composite(layer)
def add_card_frame(img, theme):
draw = ImageDraw.Draw(img)
accent = theme["accent"]
glow = theme["glow"]
draw.rounded_rectangle(
[35, 35, CARD_W - 35, CARD_H - 35],
radius=75,
outline=(accent[0], accent[1], accent[2], 230),
width=8,
)
draw.rounded_rectangle(
[60, 60, CARD_W - 60, CARD_H - 60],
radius=60,
outline=(glow[0], glow[1], glow[2], 130),
width=4,
)
draw.rounded_rectangle(
[80, 80, CARD_W - 80, 400],
radius=48,
fill=(0, 0, 0, 120),
outline=(accent[0], accent[1], accent[2], 120),
width=3,
)
draw.rounded_rectangle(
[100, 425, CARD_W - 100, 1500],
radius=58,
fill=(0, 0, 0, 55),
outline=(accent[0], accent[1], accent[2], 110),
width=4,
)
draw.rounded_rectangle(
[80, 1525, CARD_W - 80, CARD_H - 95],
radius=48,
fill=(0, 0, 0, 145),
outline=(accent[0], accent[1], accent[2], 120),
width=3,
)
def add_theme_effects(img, name, theme):
draw = ImageDraw.Draw(img)
accent = theme["accent"]
glow = theme["glow"]
if name == "fraud":
cracks = [
[(240, 500), (330, 650), (290, 800), (430, 980)],
[(1160, 520), (1060, 720), (1130, 900), (980, 1080)],
[(250, 1460), (400, 1370), (560, 1445), (700, 1330)],
]
for crack in cracks:
draw.line(crack, fill=(accent[0], accent[1], accent[2], 150), width=6)
elif name == "ghost":
for y in range(500, 1470, 90):
draw.line(
[150, y, CARD_W - 150, y + 25],
fill=(accent[0], accent[1], accent[2], 55),
width=4,
)
elif name == "sniper":
cx = CARD_W // 2
cy = 965
draw.ellipse(
[cx - 320, cy - 320, cx + 320, cy + 320],
outline=(glow[0], glow[1], glow[2], 120),
width=4,
)
draw.line([cx - 430, cy, cx + 430, cy], fill=(glow[0], glow[1], glow[2], 120), width=4)
draw.line([cx, cy - 430, cx, cy + 430], fill=(glow[0], glow[1], glow[2], 120), width=4)
elif name == "playmaker":
for y in [620, 790, 960, 1130, 1300]:
draw.line([160, y, CARD_W - 160, y], fill=(glow[0], glow[1], glow[2], 70), width=4)
for x in [360, 720, 1080]:
draw.ellipse(
[x - 14, y - 14, x + 14, y + 14],
fill=(glow[0], glow[1], glow[2], 120),
)
else:
draw.line([150, 430, 235, 1485], fill=(glow[0], glow[1], glow[2], 90), width=6)
draw.line([CARD_W - 150, 430, CARD_W - 235, 1485], fill=(glow[0], glow[1], glow[2], 90), width=6)
def make_template(name, theme):
img = make_gradient(theme["top"], theme["bottom"])
add_glow(img, theme["glow"], (CARD_W // 2, 700), 760, 120)
add_glow(img, theme["accent"], (CARD_W // 2, 1540), 620, 70)
add_lines(img, theme["accent"])
add_card_frame(img, theme)
add_theme_effects(img, name, theme)
return img.convert("RGB")
def main():
os.makedirs(TEMPLATE_DIR, exist_ok=True)
os.makedirs("cache/cards", exist_ok=True)
for name, theme in THEMES.items():
output_path = os.path.join(TEMPLATE_DIR, f"{name}.png")
img = make_template(name, theme)
img.save(output_path, "PNG", optimize=True)
print(f"Created {output_path}")
print("Created cache/cards")
return 0
if name == "main":
raise SystemExit(main())
