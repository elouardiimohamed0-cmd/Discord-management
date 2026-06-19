"""auto_templates.py — Generate premium card templates on-the-fly using Pillow.
No external image files needed. Creates templates dynamically.
"""

import io
import os
import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

CARD_W, CARD_H = 1440, 2160

def _load_font(size: int, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def _gradient_bg(w, h, c1, c2, direction="vertical"):
    img = Image.new("RGB", (w, h), c1)
    draw = ImageDraw.Draw(img)
    if direction == "vertical":
        for y in range(h):
            ratio = y / h
            r = int(c1[0] + (c2[0] - c1[0]) * ratio)
            g = int(c1[1] + (c2[1] - c1[1]) * ratio)
            b = int(c1[2] + (c2[2] - c1[2]) * ratio)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
    else:
        for x in range(w):
            ratio = x / w
            r = int(c1[0] + (c2[0] - c1[0]) * ratio)
            g = int(c1[1] + (c2[1] - c1[1]) * ratio)
            b = int(c1[2] + (c2[2] - c1[2]) * ratio)
            draw.line([(x, 0), (x, h)], fill=(r, g, b))
    return img

def _radial_gradient(w, h, center_color, edge_color):
    img = Image.new("RGB", (w, h), edge_color)
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    max_r = int(math.sqrt(cx**2 + cy**2))
    for r in range(max_r, 0, -5):
        ratio = r / max_r
        r_col = int(center_color[0] + (edge_color[0] - center_color[0]) * ratio)
        g_col = int(center_color[1] + (edge_color[1] - center_color[1]) * ratio)
        b_col = int(center_color[2] + (edge_color[2] - center_color[2]) * ratio)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(r_col, g_col, b_col))
    return img

def _add_noise(img, intensity=15):
    arr = img.copy().convert("RGB")
    pixels = arr.load()
    w, h = arr.size
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = pixels[x, y]
            noise = random.randint(-intensity, intensity)
            pixels[x, y] = (
                max(0, min(255, r + noise)),
                max(0, min(255, g + noise)),
                max(0, min(255, b + noise))
            )
    return arr

def _add_scanlines(img, spacing=4, alpha=30):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(0, img.height, spacing):
        draw.line([(0, y), (img.width, y)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay)

def _add_vignette(img, intensity=0.4):
    w, h = img.size
    vignette = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(vignette)
    cx, cy = w // 2, h // 2
    max_dist = math.sqrt(cx**2 + cy**2)
    for r in range(int(max_dist), 0, -20):
        alpha = int(180 * intensity * (r / max_dist))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, max(0, min(255, alpha))))
    return Image.alpha_composite(img.convert("RGBA"), vignette)

def _add_glow_lines(img, color, num_lines=8):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size
    for _ in range(num_lines):
        x1 = random.randint(0, w)
        y1 = random.randint(0, h // 3)
        x2 = random.randint(0, w)
        y2 = random.randint(h * 2 // 3, h)
        for width in range(20, 0, -4):
            alpha = int(40 * (width / 20))
            draw.line([(x1, y1), (x2, y2)], fill=(*color, alpha), width=width)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=30))
    return Image.alpha_composite(img.convert("RGBA"), overlay)

def _add_particles(img, color, count=50):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size
    for _ in range(count):
        x = random.randint(0, w)
        y = random.randint(0, h)
        size = random.randint(2, 8)
        alpha = random.randint(30, 120)
        draw.ellipse([x, y, x + size, y + size], fill=(*color, alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay)

def _add_border_glow(img, color, width=8):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size
    for i in range(width):
        alpha = int(100 * (1 - i / width))
        draw.rectangle([i, i, w - 1 - i, h - 1 - i], outline=(*color, alpha), width=1)
    return Image.alpha_composite(img.convert("RGBA"), overlay)

def _add_hex_pattern(img, color, size=60):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size
    hex_h = size * math.sqrt(3) / 2
    for row in range(-1, int(h / hex_h) + 2):
        for col in range(-1, int(w / size) + 2):
            x = col * size * 1.5 + (row % 2) * size * 0.75
            y = row * hex_h
            pts = []
            for i in range(6):
                angle = math.pi / 3 * i - math.pi / 6
                px = x + size * 0.4 * math.cos(angle)
                py = y + size * 0.4 * math.sin(angle)
                pts.append((px, py))
            draw.polygon(pts, outline=(*color, 25), width=1)
    return Image.alpha_composite(img.convert("RGBA"), overlay)

def _add_title_banner(img, text, y_pos, font_size=100, text_color=(255, 255, 255), 
                       banner_color=(0, 0, 0, 180), accent_color=(255, 215, 0)):
    draw = ImageDraw.Draw(img)
    font = _load_font(font_size, bold=True)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pad_x, pad_y = 60, 30

    banner_w = text_w + pad_x * 2
    banner_h = text_h + pad_y * 2
    banner_x = (img.width - banner_w) // 2
    banner_y = y_pos - pad_y

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    o_draw = ImageDraw.Draw(overlay)
    o_draw.rounded_rectangle(
        [banner_x, banner_y, banner_x + banner_w, banner_y + banner_h],
        radius=20, fill=banner_color
    )
    # Accent line
    o_draw.rectangle([banner_x, banner_y + banner_h - 6, banner_x + banner_w, banner_y + banner_h], 
                     fill=(*accent_color, 200))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(img)
    draw.text((img.width // 2, y_pos + text_h // 2), text, fill=text_color, font=font, anchor="mm")
    return img

def _add_corner_accents(img, color, size=80):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size
    thickness = 6
    # Top-left
    draw.line([(20, 20 + size), (20, 20), (20 + size, 20)], fill=(*color, 200), width=thickness)
    # Top-right
    draw.line([(w - 20 - size, 20), (w - 20, 20), (w - 20, 20 + size)], fill=(*color, 200), width=thickness)
    # Bottom-left
    draw.line([(20, h - 20 - size), (20, h - 20), (20 + size, h - 20)], fill=(*color, 200), width=thickness)
    # Bottom-right
    draw.line([(w - 20 - size, h - 20), (w - 20, h - 20), (w - 20, h - 20 - size)], fill=(*color, 200), width=thickness)
    return Image.alpha_composite(img.convert("RGBA"), overlay)

# ═══════════════════════════════════════════════════════════════
# TEMPLATE GENERATORS — One per card type
# ═══════════════════════════════════════════════════════════════

def generate_mvp_template():
    """Golden MVP template — luxurious gold theme."""
    img = _radial_gradient(CARD_W, CARD_H, (40, 30, 5), (10, 8, 2))
    img = img.convert("RGBA")

    # Golden glow from center-top
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for r in range(800, 0, -20):
        alpha = int(60 * (r / 800))
        draw.ellipse([CARD_W//2 - r, CARD_H//4 - r, CARD_W//2 + r, CARD_H//4 + r], 
                     fill=(255, 215, 0, max(0, min(255, alpha))))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=50))
    img = Image.alpha_composite(img, overlay)

    img = _add_hex_pattern(img, (255, 215, 0), size=80)
    img = _add_particles(img, (255, 200, 50), count=80)
    img = _add_vignette(img, intensity=0.5)
    img = _add_border_glow(img, (255, 215, 0), width=10)
    img = _add_corner_accents(img, (255, 215, 0), size=100)

    # Trophy icon area hint
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.polygon([
        (CARD_W//2, 180), (CARD_W//2 - 40, 260), (CARD_W//2 + 40, 260)
    ], fill=(255, 215, 0, 120))
    draw.polygon([
        (CARD_W//2, 170), (CARD_W//2 - 30, 240), (CARD_W//2 + 30, 240)
    ], fill=(255, 230, 100, 180))
    img = Image.alpha_composite(img, overlay)

    img = _add_title_banner(img, "MAN OF THE MATCH", 300, font_size=90, 
                            text_color=(255, 248, 220), banner_color=(0, 0, 0, 160),
                            accent_color=(255, 215, 0))

    return img.convert("RGBA")

def generate_fraud_template():
    """Red fraud exposure template — dramatic warning theme."""
    img = _radial_gradient(CARD_W, CARD_H, (60, 5, 5), (15, 3, 3))
    img = img.convert("RGBA")

    # Red warning glow
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for r in range(700, 0, -20):
        alpha = int(50 * (r / 700))
        draw.ellipse([CARD_W//2 - r, CARD_H//3 - r, CARD_W//2 + r, CARD_H//3 + r], 
                     fill=(255, 30, 30, max(0, min(255, alpha))))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=50))
    img = Image.alpha_composite(img, overlay)

    # Warning stripes at top
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    stripe_h = 30
    for i in range(0, CARD_W, stripe_h * 2):
        draw.rectangle([i, 0, i + stripe_h, 80], fill=(255, 200, 0, 150))
        draw.rectangle([i + stripe_h, 0, i + stripe_h * 2, 80], fill=(200, 30, 30, 150))
    img = Image.alpha_composite(img, overlay)

    img = _add_scanlines(img, spacing=6, alpha=25)
    img = _add_vignette(img, intensity=0.6)
    img = _add_border_glow(img, (255, 50, 50), width=12)
    img = _add_corner_accents(img, (255, 50, 50), size=100)

    # Warning triangle
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.polygon([
        (CARD_W//2, 160), (CARD_W//2 - 50, 250), (CARD_W//2 + 50, 250)
    ], fill=(255, 200, 0, 150), outline=(255, 50, 50, 200), width=4)
    draw.text((CARD_W//2, 220), "!", fill=(255, 50, 50, 200), font=_load_font(60, bold=True), anchor="mm")
    img = Image.alpha_composite(img, overlay)

    img = _add_title_banner(img, "FRAUD DETECTED", 300, font_size=90,
                            text_color=(255, 230, 230), banner_color=(60, 5, 5, 180),
                            accent_color=(255, 50, 50))

    return img.convert("RGBA")

def generate_ghost_template():
    """Purple ghost template — ethereal disappearing theme."""
    img = _radial_gradient(CARD_W, CARD_H, (35, 10, 50), (8, 3, 15))
    img = img.convert("RGBA")

    # Purple mist glow
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for r in range(900, 0, -25):
        alpha = int(40 * (r / 900))
        draw.ellipse([CARD_W//2 - r, CARD_H//2 - r, CARD_W//2 + r, CARD_H//2 + r], 
                     fill=(147, 51, 234, max(0, min(255, alpha))))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=60))
    img = Image.alpha_composite(img, overlay)

    img = _add_particles(img, (180, 100, 255), count=100)
    img = _add_vignette(img, intensity=0.55)
    img = _add_border_glow(img, (186, 85, 211), width=10)
    img = _add_corner_accents(img, (186, 85, 211), size=100)

    # Ghost icon
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    # Ghost body
    draw.ellipse([CARD_W//2 - 35, 150, CARD_W//2 + 35, 220], fill=(200, 180, 255, 120))
    draw.ellipse([CARD_W//2 - 25, 130, CARD_W//2 + 25, 180], fill=(220, 200, 255, 150))
    # Eyes
    draw.ellipse([CARD_W//2 - 15, 155, CARD_W//2 - 5, 165], fill=(255, 255, 255, 200))
    draw.ellipse([CARD_W//2 + 5, 155, CARD_W//2 + 15, 165], fill=(255, 255, 255, 200))
    img = Image.alpha_composite(img, overlay)

    img = _add_title_banner(img, "GHOST DETECTED", 300, font_size=90,
                            text_color=(245, 230, 255), banner_color=(25, 5, 40, 180),
                            accent_color=(186, 85, 211))

    return img.convert("RGBA")

def generate_carry_template():
    """Blue carry template — heroic energy theme."""
    img = _radial_gradient(CARD_W, CARD_H, (5, 15, 45), (2, 6, 18))
    img = img.convert("RGBA")

    # Blue energy glow
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for r in range(800, 0, -20):
        alpha = int(55 * (r / 800))
        draw.ellipse([CARD_W//2 - r, CARD_H//3 - r, CARD_W//2 + r, CARD_H//3 + r], 
                     fill=(0, 150, 255, max(0, min(255, alpha))))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=50))
    img = Image.alpha_composite(img, overlay)

    img = _add_glow_lines(img, (0, 191, 255), num_lines=12)
    img = _add_particles(img, (100, 200, 255), count=70)
    img = _add_vignette(img, intensity=0.45)
    img = _add_border_glow(img, (0, 191, 255), width=10)
    img = _add_corner_accents(img, (0, 191, 255), size=100)

    # Lightning bolt
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.polygon([
        (CARD_W//2 - 5, 150), (CARD_W//2 + 20, 200), 
        (CARD_W//2 + 5, 200), (CARD_W//2 + 10, 260),
        (CARD_W//2 - 20, 200), (CARD_W//2 - 5, 200)
    ], fill=(0, 200, 255, 180), outline=(255, 255, 255, 100), width=2)
    img = Image.alpha_composite(img, overlay)

    img = _add_title_banner(img, "CARRY DETECTED", 300, font_size=90,
                            text_color=(230, 245, 255), banner_color=(5, 15, 45, 180),
                            accent_color=(0, 191, 255))

    return img.convert("RGBA")

def generate_court_template():
    """Red court template — legal drama theme."""
    img = _gradient_bg(CARD_W, CARD_H, (20, 5, 5), (45, 10, 10), direction="vertical")
    img = img.convert("RGBA")

    # Wood floor pattern
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(400, CARD_H - 200, 40):
        draw.line([(0, y), (CARD_W, y)], fill=(80, 40, 20, 30), width=2)
    img = Image.alpha_composite(img, overlay)

    # Dramatic spotlight
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for r in range(600, 0, -20):
        alpha = int(50 * (r / 600))
        draw.ellipse([CARD_W//2 - r, CARD_H//3 - r, CARD_W//2 + r, CARD_H//3 + r], 
                     fill=(255, 50, 50, max(0, min(255, alpha))))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=50))
    img = Image.alpha_composite(img, overlay)

    img = _add_vignette(img, intensity=0.6)
    img = _add_border_glow(img, (180, 30, 30), width=12)
    img = _add_corner_accents(img, (180, 30, 30), size=100)

    # Gavel
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle([CARD_W//2 - 30, 160, CARD_W//2 + 30, 200], radius=5, fill=(120, 60, 30, 200))
    draw.rounded_rectangle([CARD_W//2 - 8, 200, CARD_W//2 + 8, 260], radius=3, fill=(100, 50, 25, 200))
    img = Image.alpha_composite(img, overlay)

    img = _add_title_banner(img, "COURT CASE", 300, font_size=100,
                            text_color=(255, 230, 230), banner_color=(40, 8, 8, 180),
                            accent_color=(180, 30, 30))

    return img.convert("RGBA")

def generate_playmaker_template():
    """Green playmaker template — creative field theme."""
    img = _radial_gradient(CARD_W, CARD_H, (5, 35, 10), (3, 15, 5))
    img = img.convert("RGBA")

    # Green energy
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for r in range(800, 0, -20):
        alpha = int(50 * (r / 800))
        draw.ellipse([CARD_W//2 - r, CARD_H//3 - r, CARD_W//2 + r, CARD_H//3 + r], 
                     fill=(50, 255, 100, max(0, min(255, alpha))))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=50))
    img = Image.alpha_composite(img, overlay)

    # Field lines
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.line([(CARD_W//2, 400), (CARD_W//2, CARD_H - 200)], fill=(255, 255, 255, 40), width=3)
    draw.ellipse([CARD_W//2 - 200, CARD_H//2 - 200, CARD_W//2 + 200, CARD_H//2 + 200], 
                 outline=(255, 255, 255, 30), width=3)
    img = Image.alpha_composite(img, overlay)

    img = _add_particles(img, (100, 255, 150), count=60)
    img = _add_vignette(img, intensity=0.45)
    img = _add_border_glow(img, (50, 255, 100), width=10)
    img = _add_corner_accents(img, (50, 255, 100), size=100)

    img = _add_title_banner(img, "PLAYMAKER", 300, font_size=100,
                            text_color=(230, 255, 235), banner_color=(5, 35, 10, 180),
                            accent_color=(50, 255, 100))

    return img.convert("RGBA")

def generate_sniper_template():
    """Blue sniper template — precision target theme."""
    img = _radial_gradient(CARD_W, CARD_H, (5, 10, 35), (2, 5, 15))
    img = img.convert("RGBA")

    # Target glow
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for r in range(700, 0, -15):
        alpha = int(45 * (r / 700))
        draw.ellipse([CARD_W//2 - r, CARD_H//3 - r, CARD_W//2 + r, CARD_H//3 + r], 
                     fill=(255, 80, 0, max(0, min(255, alpha))))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=50))
    img = Image.alpha_composite(img, overlay)

    # Target crosshair
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx, cy = CARD_W//2, 200
    for r in [30, 50, 70]:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 80, 0, 150), width=3)
    draw.line([(cx - 90, cy), (cx + 90, cy)], fill=(255, 80, 0, 150), width=3)
    draw.line([(cx, cy - 90), (cx, cy + 30)], fill=(255, 80, 0, 150), width=3)
    img = Image.alpha_composite(img, overlay)

    img = _add_vignette(img, intensity=0.5)
    img = _add_border_glow(img, (255, 100, 0), width=10)
    img = _add_corner_accents(img, (255, 100, 0), size=100)

    img = _add_title_banner(img, "SNIPER", 300, font_size=110,
                            text_color=(255, 240, 230), banner_color=(20, 8, 5, 180),
                            accent_color=(255, 100, 0))

    return img.convert("RGBA")

def generate_ball_loser_template():
    """Dark ball loser template — shame theme."""
    img = _radial_gradient(CARD_W, CARD_H, (20, 20, 20), (5, 5, 5))
    img = img.convert("RGBA")

    # Gray gloom
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for r in range(700, 0, -20):
        alpha = int(40 * (r / 700))
        draw.ellipse([CARD_W//2 - r, CARD_H//3 - r, CARD_W//2 + r, CARD_H//3 + r], 
                     fill=(100, 100, 100, max(0, min(255, alpha))))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=50))
    img = Image.alpha_composite(img, overlay)

    img = _add_scanlines(img, spacing=8, alpha=20)
    img = _add_vignette(img, intensity=0.7)
    img = _add_border_glow(img, (80, 80, 80), width=10)
    img = _add_corner_accents(img, (80, 80, 80), size=100)

    # Broken ball
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.ellipse([CARD_W//2 - 25, 170, CARD_W//2 + 25, 220], outline=(150, 150, 150, 150), width=3)
    draw.line([(CARD_W//2 - 30, 180), (CARD_W//2 + 10, 210)], fill=(150, 150, 150, 150), width=3)
    draw.line([(CARD_W//2 + 10, 180), (CARD_W//2 - 30, 210)], fill=(150, 150, 150, 150), width=3)
    img = Image.alpha_composite(img, overlay)

    img = _add_title_banner(img, "BALL LOSER", 300, font_size=100,
                            text_color=(200, 200, 200), banner_color=(15, 15, 15, 200),
                            accent_color=(120, 120, 120))

    return img.convert("RGBA")

# ═══════════════════════════════════════════════════════════════
# TEMPLATE REGISTRY
# ═══════════════════════════════════════════════════════════════

TEMPLATE_GENERATORS = {
    "mvp": generate_mvp_template,
    "fraud": generate_fraud_template,
    "ghost": generate_ghost_template,
    "carry": generate_carry_template,
    "court": generate_court_template,
    "playmaker": generate_playmaker_template,
    "sniper": generate_sniper_template,
    "ball_loser": generate_ball_loser_template,
}

def get_template(card_type: str):
    """Get a template image for the given card type. Returns PIL Image or None."""
    generator = TEMPLATE_GENERATORS.get(card_type)
    if generator:
        return generator()
    return None

def save_all_templates(output_dir: str = "assets/templates"):
    """Generate and save all templates to disk."""
    os.makedirs(output_dir, exist_ok=True)
    for name, generator in TEMPLATE_GENERATORS.items():
        img = generator()
        path = os.path.join(output_dir, f"{name}.png")
        img.convert("RGB").save(path, "PNG", optimize=True)
        print(f"Saved template: {path}")

if __name__ == "__main__":
    save_all_templates()
