import os
from typing import Tuple

from PIL import Image, ImageDraw, ImageFilter
​
CARD_W = 1440
CARD_H = 2160
TEMPLATE_DIR = "assets/templates"
THEMES = {
"mvp": {
"primary": (255, 198, 41),
"secondary": (20, 75, 180),
"accent": (255, 235, 130),
"glow": (30, 160, 255),
"dark": (12, 14, 24),
},
"fraud": {
"primary": (220, 20, 40),
"secondary": (70, 0, 0),
"accent": (255, 80, 80),
"glow": (255, 35, 35),
"dark": (15, 10, 10),
},
"ghost": {
"primary": (120, 120, 150),
"secondary": (30, 25, 45),
"accent": (190, 190, 255),
"glow": (135, 90, 255),
"dark": (8, 8, 18),
},
"carry": {
"primary": (160, 80, 255),
"secondary": (40, 10, 90),
"accent": (230, 190, 255),
"glow": (170, 50, 255),
"dark": (15, 8, 30),
},
"court_case": {
"primary": (200, 160, 80),
"secondary": (45, 30, 18),
"accent": (255, 220, 140),
"glow": (255, 180, 70),
"dark": (18, 13, 10),
},
"ball_loser": {
"primary": (255, 115, 20),
"secondary": (95, 35, 0),
"accent": (255, 190, 80),
"glow": (255, 95, 20),
"dark": (20, 12, 5),
},
"playmaker": {
"primary": (0, 210, 255),
"secondary": (0, 55, 85),
"accent": (150, 245, 255),
"glow": (0, 230, 255),
"dark": (5, 15, 22),
},
"sniper": {
"primary": (210, 210, 210),
"secondary": (25, 25, 30),
"accent": (255, 255, 255),
"glow": (255, 40, 40),
"dark": (7, 7, 10),
},
}
def lerp(a: int, b: int, t: float) -> int:
return int(a + (b - a) * t)
def gradient(
size: Tuple[int, int],
top: Tuple[int, int, int],
bottom: Tuple[int, int, int],
) -> Image.Image:
width, height = size
img = Image.new("RGBA", size)
pixels = img.load()
for y in range(height):
t = y / max(height - 1, 1)
r = lerp(top[0], bottom[0], t)
g = lerp(top[1], bottom[1], t)
b = lerp(top[2], bottom[2], t)
for x in range(width):
pixels[x, y] = (r, g, b, 255)
return img
def add_radial_glow(
img: Image.Image,
color: Tuple[int, int, int],
center: Tuple[int, int],
radius: int,
alpha: int,
) -> None:
layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
draw = ImageDraw.Draw(layer)
cx, cy = center
draw.ellipse(
[cx - radius, cy - radius, cx + radius, cy + radius],
fill=(*color, alpha),
)
layer = layer.filter(ImageFilter.GaussianBlur(max(1, radius // 4)))
img.alpha_composite(layer)
def add_diagonal_texture(img: Image.Image, color: Tuple[int, int, int]) -> None:
layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
draw = ImageDraw.Draw(layer)
for x in range(-CARD_H, CARD_W, 95):
draw.line(
[(x, CARD_H), (x + CARD_H, 0)],
fill=(*color, 22),
width=3,
)
img.alpha_composite(layer)
def add_noise_dots(img: Image.Image, color: Tuple[int, int, int]) -> None:
layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
draw = ImageDraw.Draw(layer)
for i in range(520):
x = (i * 137) % CARD_W
y = (i * 251) % CARD_H
radius = 1 + (i % 3)
alpha = 20 + (i % 35)
draw.ellipse(
[x - radius, y - radius, x + radius, y + radius],
fill=(*color, alpha),
)
img.alpha_composite(layer)
def add_card_shape(img: Image.Image, theme: dict) -> None:
draw = ImageDraw.Draw(img)
primary = theme["primary"]
accent = theme["accent"]
dark = theme["dark"]
Outer card frame.
draw.rounded_rectangle(
[35, 35, CARD_W - 35, CARD_H - 35],
radius=75,
fill=(0, 0, 0, 0),
outline=(*accent, 210),
width=8,
)
draw.rounded_rectangle(
[55, 55, CARD_W - 55, CARD_H - 55],
radius=62,
fill=(0, 0, 0, 0),
outline=(*primary, 150),
width=4,
)
Top panel.
draw.rounded_rectangle(
[75, 75, CARD_W - 75, 390],
radius=48,
fill=(*dark, 125),
outline=(*accent, 120),
width=3,
)
Bottom stats panel.
draw.rounded_rectangle(
[75, 1510, CARD_W - 75, CARD_H - 95],
radius=48,
fill=(0, 0, 0, 145),
outline=(*accent, 120),
width=3,
)
Center player area.
draw.rounded_rectangle(
[95, 410, CARD_W - 95, 1510],
radius=60,
fill=(0, 0, 0, 45),
outline=(*primary, 130),
width=4,
)
def add_theme_specific(img: Image.Image, name: str, theme: dict) -> None:
draw = ImageDraw.Draw(img)
accent = theme["accent"]
glow = theme["glow"]
if name == "fraud":
cracks = [
[(210, 470), (310, 610), (275, 740), (410, 925)],
[(1180, 520), (1080, 690), (1135, 830), (1010, 1020)],
[(250, 1480), (370, 1390), (510, 1440), (630, 1320)],
]
for line in cracks:
draw.line(line, fill=(*accent, 135), width=5)
elif name == "ghost":
for y in range(490, 1480, 75):
draw.line(
[130, y, CARD_W - 130, y + 18],
fill=(*accent, 42),
width=3,
)
elif name == "sniper":
cx, cy = CARD_W // 2, 965
draw.ellipse(
[cx - 310, cy - 310, cx + 310, cy + 310],
outline=(*glow, 115),
width=3,
)
draw.line(
[cx - 390, cy, cx + 390, cy],
fill=(*glow, 100),
width=3,
)
draw.line(
[cx, cy - 390, cx, cy + 390],
fill=(*glow, 100),
width=3,
)
elif name == "court_case":
for x in range(130, CARD_W - 130, 120):
draw.line(
[x, 500, x + 60, 1470],
fill=(*accent, 36),
width=8,
)
elif name == "ball_loser":
for i in range(10):
y = 520 + i * 88
draw.arc(
[120, y, 350, y + 230],
20,
320,
fill=(*accent, 70),
width=5,
)
elif name == "playmaker":
for y in [620, 790, 960, 1130, 1300]:
draw.line(
[160, y, CARD_W - 160, y],
fill=(*glow, 55),
width=3,
)
for x in [360, 720, 1080]:
draw.ellipse(
[x - 12, y - 12, x + 12, y + 12],
fill=(*glow, 105),
)
else:
for x in [145, CARD_W - 145]:
direction = 80 if x < CARD_W // 2 else -80
draw.line(
[x, 430, x + direction, 1485],
fill=(*glow, 75),
width=5,
)
def make_template(name: str, theme: dict) -> Image.Image:
img = gradient((CARD_W, CARD_H), theme["dark"], theme["secondary"])
add_radial_glow(img, theme["glow"], (CARD_W // 2, 700), 780, 115)
add_radial_glow(img, theme["primary"], (CARD_W // 2, 1530), 660, 75)
add_diagonal_texture(img, theme["accent"])
add_noise_dots(img, theme["accent"])
add_card_shape(img, theme)
add_theme_specific(img, name, theme)
return img.convert("RGB")
def main() -> int:
os.makedirs(TEMPLATE_DIR, exist_ok=True)
os.makedirs("cache/cards", exist_ok=True)
for name, theme in THEMES.items():
path = os.path.join(TEMPLATE_DIR, f"{name}.png")
img = make_template(name, theme)
img.save(path, "PNG", optimize=True)
print(f"Created {path}")
print("Created cache/cards")
return 0
if name == "main":
raise SystemExit(main())
