"""generate_templates.py — FAST premium card template generator.
Optimized: no pixel loops, bulk operations only. ~1-2 min total.
"""

import os
import random
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
    """Fast gradient using resize instead of pixel loop."""
    gradient = Image.new("RGB", (2, h), c1)
    draw = ImageDraw.Draw(gradient)
    for y in range(h):
        ratio = y / h
        r = int(c1[0] + (c2[0] - c1[0]) * ratio)
        g = int(c1[1] + (c2[1] - c1[1]) * ratio)
        b = int(c1[2] + (c2[2] - c1[2]) * ratio)
        draw.point((0, y), fill=(r, g, b))
        draw.point((1, y), fill=(r, g, b))
    return gradient.resize((w, h), Image.LANCZOS)


def _glow_circle_fast(img, cx, cy, radius, color, intensity=0.35):
    """Fast glow using radial gradient + blur."""
    overlay = Image.new("RGBA", (radius * 2, radius * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for r in range(radius, 0, -60):
        alpha = int(180 * intensity * (r / radius))
        draw.ellipse([radius - r, radius - r, radius + r, radius + r], fill=(*color, max(0, alpha // 3)))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=radius // 3))
    img.paste(overlay, (cx - radius, cy - radius), overlay)
    return img


def _add_vignette_fast(img, intensity=0.4):
    """Fast vignette using radial gradient + blur."""
    w, h = img.size
    overlay = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(overlay)
    cx, cy = w // 2, h // 2
    max_r = int((cx**2 + cy**2) ** 0.5)
    for r in range(max_r, 0, -80):
        alpha = int(255 * intensity * (r / max_r))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=max(0, alpha // 5))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=100))
    img = img.convert("RGBA")
    vignette = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vignette.putalpha(overlay)
    return Image.alpha_composite(img, vignette)


def _add_particles_fast(img, color, count=30):
    """Fast particles — just draw circles, no per-pixel noise."""
    draw = ImageDraw.Draw(img)
    for _ in range(count):
        x = random.randint(100, img.width - 100)
        y = random.randint(100, img.height - 100)
        r = random.randint(3, 8)
        alpha = random.randint(40, 120)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*color, alpha))
    return img


def _add_corner_accents(draw, w, h, color):
    """Decorative corner brackets."""
    l, t = 60, 8
    c = (*color, 200)
    draw.line([(20, 20), (20 + l, 20)], fill=c, width=t)
    draw.line([(20, 20), (20, 20 + l)], fill=c, width=t)
    draw.line([(w - 20 - l, 20), (w - 20, 20)], fill=c, width=t)
    draw.line([(w - 20, 20), (w - 20, 20 + l)], fill=c, width=t)
    draw.line([(20, h - 20), (20 + l, h - 20)], fill=c, width=t)
    draw.line([(20, h - 20 - l), (20, h - 20)], fill=c, width=t)
    draw.line([(w - 20 - l, h - 20), (w - 20, h - 20)], fill=c, width=t)
    draw.line([(w - 20, h - 20 - l), (w - 20, h - 20)], fill=c, width=t)


def generate_template(name, palette_name, label_text, output_dir="assets/templates"):
    """Generate a single premium template — FAST."""
    os.makedirs(output_dir, exist_ok=True)
    pal = PALETTES[palette_name]
    W, H = CARD_W, CARD_H
    
    print(f"[TEMPLATE] Generating {name}.png...")
    
    # Base gradient
    img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")
    
    # Glow effects (fast)
    img = _glow_circle_fast(img, W // 2, H // 3, 600, pal["glow"], 0.3)
    img = _glow_circle_fast(img, W // 4, H // 4, 350, pal["accent"], 0.2)
    img = _glow_circle_fast(img, W * 3 // 4, H * 2 // 3, 300, pal["accent2"], 0.15)
    
    # Vignette (fast)
    img = _add_vignette_fast(img, intensity=0.3)
    
    # Particles (fast)
    img = _add_particles_fast(img, pal["glow"], count=40)
    
    draw = ImageDraw.Draw(img)
    
    # Border
    draw.rectangle([4, 4, W - 4, H - 4], outline=(*pal["accent"], 200), width=10)
    draw.rectangle([14, 14, W - 14, H - 14], outline=(*pal["accent"], 60), width=2)
    
    # Corner accents
    _add_corner_accents(draw, W, H, pal["accent2"])
    
    # Top label bar
    bar_h = 100
    draw.rectangle([0, 0, W, bar_h], fill=(*pal["bg_top"], 220))
    draw.line([(0, bar_h), (W, bar_h)], fill=(*pal["accent"], 180), width=3)
    
    font = _load_font(44, bold=True)
    bbox = draw.textbbox((0, 0), label_text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 22), label_text, fill=(*pal["accent"], 255), font=font)
    
    # Bottom bar
    draw.rectangle([0, H - 70, W, H], fill=(*pal["bg_bot"], 220))
    draw.line([(0, H - 70), (W, H - 70)], fill=(*pal["accent"], 120), width=2)
    
    small_font = _load_font(24, bold=False)
    footer = "RACHAD L3ERGONI • PRO CLUBS TRACKER"
    bbox = draw.textbbox((0, 0), footer, font=small_font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, H - 48), footer, fill=(*pal["accent2"], 200), font=small_font)
    
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
