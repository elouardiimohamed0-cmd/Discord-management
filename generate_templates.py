"""generate_templates.py — Generate premium card template backgrounds.
Run once on boot (or manually) to create assets/templates/*.png
"""

import os
import math
from PIL import Image, ImageDraw, ImageFilter, ImageFont

CARD_W, CARD_H = 1440, 2160

PALETTES = {
    "mvp": {
        "bg_top": (10, 8, 4), "bg_bot": (30, 22, 8),
        "accent": (255, 215, 0), "accent2": (218, 165, 32),
        "glow": (255, 200, 50),
    },
    "fraud": {
        "bg_top": (18, 4, 4), "bg_bot": (45, 8, 8),
        "accent": (255, 50, 50), "accent2": (200, 30, 30),
        "glow": (255, 60, 60),
    },
    "ghost": {
        "bg_top": (8, 8, 12), "bg_bot": (18, 18, 30),
        "accent": (180, 180, 200), "accent2": (140, 140, 160),
        "glow": (160, 160, 180),
    },
    "carry": {
        "bg_top": (4, 14, 6), "bg_bot": (8, 35, 14),
        "accent": (50, 255, 100), "accent2": (30, 200, 70),
        "glow": (60, 255, 120),
    },
    "court": {
        "bg_top": (18, 10, 4), "bg_bot": (45, 25, 8),
        "accent": (255, 140, 0), "accent2": (200, 100, 0),
        "glow": (255, 120, 0),
    },
    "playmaker": {
        "bg_top": (4, 12, 18), "bg_bot": (8, 30, 45),
        "accent": (0, 191, 255), "accent2": (30, 144, 255),
        "glow": (0, 150, 255),
    },
    "sniper": {
        "bg_top": (12, 4, 18), "bg_bot": (35, 10, 50),
        "accent": (186, 85, 211), "accent2": (147, 51, 234),
        "glow": (180, 60, 220),
    },
    "ball_loser": {
        "bg_top": (25, 20, 5), "bg_bot": (50, 40, 10),
        "accent": (139, 90, 43), "accent2": (100, 65, 30),
        "glow": (160, 110, 50),
    },
}

def _load_font(size, bold=True):
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

def _gradient_bg(w, h, c1, c2):
    img = Image.new("RGB", (w, h), c1)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        ratio = y / h
        r = int(c1[0] + (c2[0] - c1[0]) * ratio)
        g = int(c1[1] + (c2[1] - c1[1]) * ratio)
        b = int(c1[2] + (c2[2] - c1[2]) * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img

def _glow_circle(img, cx, cy, radius, color, intensity=0.35):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for r in range(radius, 0, -30):
        alpha = int(200 * intensity * (r / radius))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*color, max(0, alpha // 4)))
    return Image.alpha_composite(img.convert("RGBA"), overlay)

def _add_noise(img, intensity=8):
    """Add subtle grain texture."""
    import random
    pixels = img.load()
    for i in range(0, img.width, 2):
        for j in range(0, img.height, 2):
            r, g, b = pixels[i, j]
            noise = random.randint(-intensity, intensity)
            pixels[i, j] = (
                max(0, min(255, r + noise)),
                max(0, min(255, g + noise)),
                max(0, min(255, b + noise)),
            )
    return img

def _add_vignette(img, color=(0, 0, 0), intensity=0.4):
    """Darken edges."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx, cy = img.width // 2, img.height // 2
    max_dist = math.sqrt(cx**2 + cy**2)
    for r in range(int(max_dist), 0, -20):
        alpha = int(255 * intensity * (r / max_dist))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*color, max(0, alpha // 6)))
    return Image.alpha_composite(img.convert("RGBA"), overlay)

def _add_scanlines(img):
    """Subtle horizontal lines for retro feel."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(0, img.height, 4):
        draw.line([(0, y), (img.width, y)], fill=(0, 0, 0, 15))
    return Image.alpha_composite(img.convert("RGBA"), overlay)

def _add_text_watermark(img, text, color, font_size=200):
    """Add large faded text as background element."""
    draw = ImageDraw.Draw(img)
    font = _load_font(font_size, bold=True)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (img.width - tw) // 2
    y = (img.height - th) // 2 - 200
    draw.text((x, y), text, fill=(*color, 25), font=font)
    return img

def _add_border(img, color, width=8):
    """Add premium border."""
    draw = ImageDraw.Draw(img)
    draw.rectangle([width//2, width//2, img.width - width//2, img.height - width//2], outline=(*color, 180), width=width)
    # Inner accent line
    draw.rectangle([width + 4, width + 4, img.width - width - 4, img.height - width - 4], outline=(*color, 60), width=2)
    return img

def _add_corner_accents(img, color):
    """Add decorative corner brackets."""
    draw = ImageDraw.Draw(img)
    l = 60
    t = 8
    c = (*color, 200)
    
    # Top-left
    draw.line([(20, 20), (20 + l, 20)], fill=c, width=t)
    draw.line([(20, 20), (20, 20 + l)], fill=c, width=t)
    
    # Top-right
    draw.line([(img.width - 20 - l, 20), (img.width - 20, 20)], fill=c, width=t)
    draw.line([(img.width - 20, 20), (img.width - 20, 20 + l)], fill=c, width=t)
    
    # Bottom-left
    draw.line([(20, img.height - 20), (20 + l, img.height - 20)], fill=c, width=t)
    draw.line([(20, img.height - 20 - l), (20, img.height - 20)], fill=c, width=t)
    
    # Bottom-right
    draw.line([(img.width - 20 - l, img.height - 20), (img.width - 20, img.height - 20)], fill=c, width=t)
    draw.line([(img.width - 20, img.height - 20 - l), (img.width - 20, img.height - 20)], fill=c, width=t)
    
    return img

def _add_particles(img, color, count=50):
    """Add floating particle dots."""
    import random
    draw = ImageDraw.Draw(img)
    for _ in range(count):
        x = random.randint(50, img.width - 50)
        y = random.randint(50, img.height - 50)
        r = random.randint(2, 6)
        alpha = random.randint(30, 100)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*color, alpha))
    return img

def generate_template(name, palette_name, label_text, output_dir="assets/templates"):
    """Generate a single premium template."""
    os.makedirs(output_dir, exist_ok=True)
    pal = PALETTES[palette_name]
    W, H = CARD_W, CARD_H
    
    print(f"[TEMPLATE] Generating {name}.png...")
    
    # Base gradient
    img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")
    
    # Glow effects
    img = _glow_circle(img, W // 2, H // 3, 700, pal["glow"], 0.25)
    img = _glow_circle(img, W // 4, H // 4, 400, pal["accent"], 0.15)
    img = _glow_circle(img, W * 3 // 4, H * 2 // 3, 350, pal["accent2"], 0.12)
    
    # Noise texture
    img = _add_noise(img, intensity=6)
    
    # Vignette
    img = _add_vignette(img, intensity=0.35)
    
    # Scanlines
    img = _add_scanlines(img)
    
    # Large watermark text
    img = _add_text_watermark(img, label_text, pal["accent"], font_size=180)
    
    # Border
    img = _add_border(img, pal["accent"], width=10)
    
    # Corner accents
    img = _add_corner_accents(img, pal["accent2"])
    
    # Particles
    img = _add_particles(img, pal["glow"], count=60)
    
    # Top label bar
    draw = ImageDraw.Draw(img)
    bar_h = 120
    draw.rectangle([0, 0, W, bar_h], fill=(*pal["bg_top"], 200))
    draw.line([(0, bar_h), (W, bar_h)], fill=(*pal["accent"], 150), width=3)
    
    font = _load_font(48, bold=True)
    bbox = draw.textbbox((0, 0), label_text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 30), label_text, fill=(*pal["accent"], 255), font=font)
    
    # Bottom bar
    draw.rectangle([0, H - 80, W, H], fill=(*pal["bg_bot"], 200))
    draw.line([(0, H - 80), (W, H - 80)], fill=(*pal["accent"], 100), width=2)
    
    small_font = _load_font(28, bold=False)
    footer = "RACHAD L3ERGONI • PRO CLUBS TRACKER"
    bbox = draw.textbbox((0, 0), footer, font=small_font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, H - 55), footer, fill=(*pal["accent2"], 180), font=small_font)
    
    # Save
    output_path = os.path.join(output_dir, f"{name}.png")
    img = img.convert("RGB")
    img.save(output_path, "PNG", optimize=True)
    print(f"[TEMPLATE] ✅ Saved: {output_path}")
    return output_path

def main():
    templates = [
        ("mvp", "mvp", "MAN OF THE MATCH"),
        ("fraud", "fraud", "FRAUD DETECTED"),
        ("ghost", "ghost", "GHOST DETECTED"),
        ("carry", "carry", "CARRY DETECTED"),
        ("court", "court", "COURT CASE"),
        ("playmaker", "playmaker", "PLAYMAKER"),
        ("sniper", "sniper", "SNIPER"),
        ("ball_loser", "ball_loser", "BALL LOSER"),
    ]
    
    print("=" * 50)
    print("GENERATING PREMIUM CARD TEMPLATES")
    print("=" * 50)
    
    for name, palette, label in templates:
        generate_template(name, palette, label)
    
    print("=" * 50)
    print("ALL TEMPLATES GENERATED SUCCESSFULLY")
    print("=" * 50)

if __name__ == "__main__":
    main()
