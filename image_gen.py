"""image_gen.py — PHASE 2.4
EA FC 26 / TOTY / TOTS / Blue Lock inspired card generator.
Resolution: 2160x3840 (UHD portrait)
"""

import io
import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from typing import List, Optional, Dict
from models import PlayerStats, ClubStats

# ─── PLAYER IMAGE LOADER ───

def load_player_image(player_name: str, assets_dir: str, size: tuple = (256, 256)) -> Image.Image:
    """
    Load player image from assets folder.
    Tries: assets/{nickname}.png -> .jpg -> .jpeg -> .webp
    Falls back to purple circle with initial.
    """
    name = player_name.strip()
    # Try exact match
    for ext in [".png", ".jpg", ".jpeg", ".webp"]:
        path = os.path.join(assets_dir, f"{name}{ext}")
        if os.path.exists(path):
            img = Image.open(path).convert("RGBA")
            img = img.resize(size, Image.LANCZOS)
            return img

    # Try lowercase
    for ext in [".png", ".jpg", ".jpeg", ".webp"]:
        path = os.path.join(assets_dir, f"{name.lower()}{ext}")
        if os.path.exists(path):
            img = Image.open(path).convert("RGBA")
            img = img.resize(size, Image.LANCZOS)
            return img

    # Try no spaces
    clean_name = name.replace(" ", "").replace("_", "")
    for ext in [".png", ".jpg", ".jpeg", ".webp"]:
        path = os.path.join(assets_dir, f"{clean_name}{ext}")
        if os.path.exists(path):
            img = Image.open(path).convert("RGBA")
            img = img.resize(size, Image.LANCZOS)
            return img

    # Fallback: dark circle with initial
    fallback = Image.new("RGBA", size, (30, 30, 30, 255))
    return fallback

# ─── CONSTANTS ───
CARD_W, CARD_H = 2160, 3840
MARGIN = 120

# Color palettes
PALETTES = {
    "gold": {
        "bg_top": (10, 8, 4), "bg_bot": (30, 22, 8),
        "accent": (255, 215, 0), "accent2": (218, 165, 32),
        "glow": (255, 200, 50), "text": (255, 248, 220),
        "text_dim": (200, 180, 140), "badge": (255, 215, 0),
    },
    "blue": {
        "bg_top": (2, 6, 18), "bg_bot": (8, 18, 45),
        "accent": (0, 191, 255), "accent2": (30, 144, 255),
        "glow": (0, 150, 255), "text": (230, 245, 255),
        "text_dim": (150, 180, 210), "badge": (0, 191, 255),
    },
    "red": {
        "bg_top": (18, 4, 4), "bg_bot": (45, 8, 8),
        "accent": (255, 50, 50), "accent2": (200, 30, 30),
        "glow": (255, 60, 60), "text": (255, 230, 230),
        "text_dim": (210, 150, 150), "badge": (255, 50, 50),
    },
    "purple": {
        "bg_top": (12, 4, 18), "bg_bot": (35, 10, 50),
        "accent": (186, 85, 211), "accent2": (147, 51, 234),
        "glow": (180, 60, 220), "text": (245, 230, 255),
        "text_dim": (180, 150, 200), "badge": (186, 85, 211),
    },
    "green": {
        "bg_top": (4, 14, 6), "bg_bot": (8, 35, 14),
        "accent": (50, 255, 100), "accent2": (30, 200, 70),
        "glow": (60, 255, 120), "text": (230, 255, 235),
        "text_dim": (150, 210, 170), "badge": (50, 255, 100),
    },
    "dark": {
        "bg_top": (8, 8, 8), "bg_bot": (20, 20, 20),
        "accent": (180, 180, 180), "accent2": (120, 120, 120),
        "glow": (150, 150, 150), "text": (240, 240, 240),
        "text_dim": (160, 160, 160), "badge": (200, 200, 200),
    },
}

def _load_font(size: int, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

def _hexagon_points(cx, cy, radius):
    points = []
    for i in range(6):
        angle = math.pi / 3 * i - math.pi / 6
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        points.append((x, y))
    return points

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

def _load_player_photo(name: str, assets_dir: str, size=(1400, 1400), photo_path: Optional[str] = None):
    """
    Load player photo. If photo_path is provided, use it directly.
    Otherwise search by name in assets_dir.
    """
    # If explicit path provided, try it first
    if photo_path and os.path.exists(photo_path):
        try:
            img = Image.open(photo_path).convert("RGBA")
            img = img.resize(size, Image.LANCZOS)
            return img
        except Exception:
            pass

    # Fallback: search by name
    clean = name.replace(" ", "_").lower()
    candidates = [
        os.path.join(assets_dir, f"{name}.png"),
        os.path.join(assets_dir, f"{name}.jpg"),
        os.path.join(assets_dir, f"{name}.jpeg"),
        os.path.join(assets_dir, f"{clean}.png"),
        os.path.join(assets_dir, f"{clean}.jpg"),
        os.path.join(assets_dir, f"{clean}.jpeg"),
    ]
    # Also try uppercase
    upper = name.upper()
    candidates.extend([
        os.path.join(assets_dir, f"{upper}.png"),
        os.path.join(assets_dir, f"{upper}.jpg"),
        os.path.join(assets_dir, f"{upper}.jpeg"),
    ])
    # Try title case
    title = name.title()
    candidates.extend([
        os.path.join(assets_dir, f"{title}.png"),
        os.path.join(assets_dir, f"{title}.jpg"),
        os.path.join(assets_dir, f"{title}.jpeg"),
    ])

    for path in candidates:
        if os.path.exists(path):
            try:
                img = Image.open(path).convert("RGBA")
                img = img.resize(size, Image.LANCZOS)
                return img
            except Exception:
                pass
    return None

def _draw_stat_box(draw, x, y, w, h, label, value, palette, font_label, font_value):
    pal = palette
    _draw_rounded_rect(draw, (x, y, x + w, y + h), 20, (30, 30, 30, 180), (*pal["accent"], 120), 3)
    draw.text((x + 30, y + 20), label, fill=pal["text_dim"], font=font_label)
    draw.text((x + 30, y + 80), str(value), fill=pal["text"], font=font_value)

def _draw_rounded_rect(draw, xy, radius, fill, outline=None, width=2):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)

class ImageGenerator:
    def __init__(self, assets_dir: str = "assets"):
        self.assets_dir = assets_dir
        self.fonts = {}

    def _font(self, size, bold=False):
        key = (size, bold)
        if key not in self.fonts:
            self.fonts[key] = _load_font(size, bold)
        return self.fonts[key]

    # ───────────────────────────────────────────
    # CORE EA FC PRO CARD BUILDER
    # ───────────────────────────────────────────
    def _build_fc_card(self, player, pos, palette_name, label, extra_stats=None, photo_override=None):
        pal = PALETTES.get(palette_name, PALETTES["gold"])
        W, H = CARD_W, CARD_H

        # Base gradient
        img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")

        # ── AURA / GLOW ──
        img = _glow_circle(img, W // 2, H // 3, 900, pal["glow"], 0.25)
        img = _glow_circle(img, W // 2, H * 2 // 3, 700, pal["accent2"], 0.15)

        draw = ImageDraw.Draw(img)

        # ── TOP LABEL ──
        f_label = self._font(56, bold=True)
        draw.text((W // 2, 60), label, fill=pal["accent"], font=f_label, anchor="mm")

        # ── RATING HEXAGON ──
        rating = round(getattr(player, "rating_pg", 7.0), 1)
        hex_y = 320
        hex_r = 160
        hex_pts = _hexagon_points(W // 2, hex_y, hex_r)
        # Glow behind hex
        for offset in [40, 30, 20, 10]:
            glow_pts = _hexagon_points(W // 2, hex_y, hex_r + offset)
            alpha = int(80 - offset * 1.5)
            draw.polygon(glow_pts, fill=(*pal["glow"], alpha))
        # Hex body
        draw.polygon(hex_pts, fill=(20, 20, 20, 240), outline=pal["accent"])
        # Rating number
        f_rating = self._font(220, bold=True)
        draw.text((W // 2, hex_y), str(rating), fill=pal["badge"], font=f_rating, anchor="mm")
        # "OVR" text
        f_ovr = self._font(40, bold=True)
        draw.text((W // 2, hex_y + 110), "OVR", fill=pal["text_dim"], font=f_ovr, anchor="mm")

        # ── PLAYER PHOTO ──
        photo_y = 900
        photo_size = (1300, 1300)
        photo = _load_player_photo(player.name, self.assets_dir, photo_size, photo_path=photo_override)
        if photo:
            # Center photo
            px = (W - photo.width) // 2
            py = photo_y
            # Shadow / glow behind photo
            shadow = Image.new("RGBA", (photo.width + 80, photo.height + 80), (0, 0, 0, 0))
            s_draw = ImageDraw.Draw(shadow)
            s_draw.rounded_rectangle([20, 20, photo.width + 60, photo.height + 60], radius=40, fill=(*pal["glow"], 60))
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=30))
            img.paste(shadow, (px - 40, py - 40), shadow)
            # Photo with rounded mask
            mask = Image.new("L", photo.size, 0)
            m_draw = ImageDraw.Draw(mask)
            m_draw.rounded_rectangle([0, 0, photo.width, photo.height], radius=40, fill=255)
            img.paste(photo, (px, py), mask)
        else:
            # Silhouette placeholder (dark, no face)
            sil_y = photo_y + 200
            draw.ellipse([W // 2 - 300, sil_y, W // 2 + 300, sil_y + 600], fill=(40, 40, 40, 200), outline=pal["accent"], width=4)
            draw.ellipse([W // 2 - 120, sil_y - 150, W // 2 + 120, sil_y + 150], fill=(40, 40, 40, 200), outline=pal["accent"], width=4)
            f_sil = self._font(60, bold=True)
            draw.text((W // 2, sil_y + 350), player.name, fill=pal["text_dim"], font=f_sil, anchor="mm")

        # ── NAME & POSITION ──
        name_y = 2320
        f_name = self._font(140, bold=True)
        draw.text((W // 2, name_y), player.name.upper(), fill=pal["text"], font=f_name, anchor="mm")

        # Position badge
        pos_y = 2500
        f_pos = self._font(60, bold=True)
        pw, ph = 220, 90
        px = (W - pw) // 2
        draw.rounded_rectangle([px, pos_y, px + pw, pos_y + ph], radius=20, fill=pal["accent"], outline=pal["accent2"], width=3)
        draw.text((W // 2, pos_y + ph // 2), pos.upper(), fill=(10, 10, 10), font=f_pos, anchor="mm")

        # ── DIVIDER ──
        div_y = 2660
        draw.line([(MARGIN, div_y), (W - MARGIN, div_y)], fill=pal["accent"], width=4)
        # Small diamond in middle
        d = 12
        draw.polygon([(W // 2, div_y - d), (W // 2 + d, div_y), (W // 2, div_y + d), (W // 2 - d, div_y)], fill=pal["accent"])

        # ── STATS GRID ──
        stats = [
            ("GOALS", getattr(player, "goals", 0)),
            ("ASSISTS", getattr(player, "assists", 0)),
            ("PASS %", f"{round(getattr(player, 'pass_accuracy', 0), 1)}%"),
            ("IMPACT", round(getattr(player, "impact_score", 0), 1)),
            ("FRAUD", round(getattr(player, "throwing_score", 0), 1)),
            ("CLUTCH", round(getattr(player, "clutch_score", 0), 1)),
        ]
        if extra_stats:
            stats = extra_stats

        grid_y = 2740
        box_w = (W - MARGIN * 3) // 2
        box_h = 200
        gap_x = MARGIN
        gap_y = 30
        f_stat_label = self._font(38, bold=True)
        f_stat_val = self._font(72, bold=True)

        for i, (s_label, s_val) in enumerate(stats[:6]):
            col = i % 2
            row = i // 2
            x = MARGIN + col * (box_w + gap_x)
            y = grid_y + row * (box_h + gap_y)

            # Box bg
            draw.rounded_rectangle([x, y, x + box_w, y + box_h], radius=24, fill=(25, 25, 25, 200), outline=(*pal["accent"], 150), width=3)
            # Label
            draw.text((x + 30, y + 18), s_label, fill=pal["text_dim"], font=f_stat_label)
            # Value
            draw.text((x + 30, y + 70), str(s_val), fill=pal["text"], font=f_stat_val)

        # ── BOTTOM FOOTER ──
        f_foot = self._font(36)
        draw.text((W // 2, H - 80), "RACHAD L3ERGONI • PRO CLUBS TRACKER", fill=pal["text_dim"], font=f_foot, anchor="mm")

        # Final composite and sharpen
        img = img.convert("RGB")
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.2)

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf

    # ───────────────────────────────────────────
    # PUBLIC CARD METHODS (all bot.py interfaces)
    # ───────────────────────────────────────────

    def generate_player_card(self, player, pos, division=6, photo_path=None):
        """Standard player profile card — Gold theme."""
        return self._build_fc_card(player, pos, "gold", "PLAYER PROFILE", photo_override=photo_path)

    def generate_mvp_card(self, player, pos, photo_path=None):
        """MVP card — TOTY Gold theme."""
        return self._build_fc_card(player, pos, "gold", "MAN OF THE MATCH", photo_override=photo_path)

    def generate_roast_card(self, player, roast_text, pos, photo_path=None):
        """Roast card — Red theme with roast text baked in."""
        pal = PALETTES["red"]
        W, H = CARD_W, CARD_H
        img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")
        img = _glow_circle(img, W // 2, H // 3, 800, pal["glow"], 0.3)
        draw = ImageDraw.Draw(img)

        f_label = self._font(60, bold=True)
        draw.text((W // 2, 70), "⚠️ FRAUD DETECTED", fill=pal["accent"], font=f_label, anchor="mm")

        # Rating
        rating = round(getattr(player, "rating_pg", 7.0), 1)
        hex_y = 300
        hex_r = 150
        hex_pts = _hexagon_points(W // 2, hex_y, hex_r)
        draw.polygon(hex_pts, fill=(20, 20, 20, 240), outline=pal["accent"])
        f_rating = self._font(200, bold=True)
        draw.text((W // 2, hex_y), str(rating), fill=pal["badge"], font=f_rating, anchor="mm")

        # Photo
        photo = _load_player_photo(player.name, self.assets_dir, (1200, 1200), photo_path=photo_path)
        if photo:
            px = (W - photo.width) // 2
            py = 650
            shadow = Image.new("RGBA", (photo.width + 80, photo.height + 80), (0, 0, 0, 0))
            s_draw = ImageDraw.Draw(shadow)
            s_draw.rounded_rectangle([20, 20, photo.width + 60, photo.height + 60], radius=40, fill=(*pal["glow"], 80))
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=30))
            img.paste(shadow, (px - 40, py - 40), shadow)
            mask = Image.new("L", photo.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, photo.width, photo.height], radius=40, fill=255)
            img.paste(photo, (px, py), mask)

        # Name
        f_name = self._font(130, bold=True)
        draw.text((W // 2, 2000), player.name.upper(), fill=pal["text"], font=f_name, anchor="mm")

        # Position
        f_pos = self._font(55, bold=True)
        pw, ph = 200, 80
        px = (W - pw) // 2
        draw.rounded_rectangle([px, 2140, px + pw, 2140 + ph], radius=18, fill=pal["accent"], outline=pal["accent2"], width=3)
        draw.text((W // 2, 2140 + ph // 2), pos.upper(), fill=(10, 10, 10), font=f_pos, anchor="mm")

        # Roast text box
        roast_y = 2320
        box_pad = 80
        f_roast = self._font(48)
        lines = []
        words = roast_text.split()
        line = ""
        for w in words:
            if len(line + " " + w) < 50:
                line += " " + w if line else w
            else:
                lines.append(line)
                line = w
        if line:
            lines.append(line)
        text_h = len(lines) * 70 + 60
        draw.rounded_rectangle([MARGIN, roast_y, W - MARGIN, roast_y + text_h], radius=30, fill=(20, 20, 20, 220), outline=pal["accent"], width=4)
        for i, ln in enumerate(lines):
            draw.text((W // 2, roast_y + 50 + i * 70), ln, fill=pal["text"], font=f_roast, anchor="mm")

        # Footer stats
        stats = [
            ("THROWING", round(getattr(player, "throwing_score", 0), 1)),
            ("ERROR", round(getattr(player, "error_score", 0), 1)),
            ("PASS %", f"{round(getattr(player, 'pass_accuracy', 0), 1)}%"),
            ("IMPACT", round(getattr(player, "impact_score", 0), 1)),
        ]
        grid_y = roast_y + text_h + 80
        box_w = (W - MARGIN * 3) // 2
        box_h = 180
        f_slab = self._font(36, bold=True)
        f_sval = self._font(64, bold=True)
        for i, (sl, sv) in enumerate(stats):
            col = i % 2
            row = i // 2
            x = MARGIN + col * (box_w + MARGIN)
            y = grid_y + row * (box_h + 30)
            draw.rounded_rectangle([x, y, x + box_w, y + box_h], radius=20, fill=(25, 25, 25, 200), outline=(*pal["accent"], 120), width=3)
            draw.text((x + 30, y + 15), sl, fill=pal["text_dim"], font=f_slab)
            draw.text((x + 30, y + 65), str(sv), fill=pal["text"], font=f_sval)

        f_foot = self._font(36)
        draw.text((W // 2, H - 80), "RACHAD L3ERGONI • FRAUD ALERT", fill=pal["text_dim"], font=f_foot, anchor="mm")

        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf

    def generate_anime_card(self, player, pos, style, label, photo_path=None):
        """Blue Lock / Anime style card — Purple theme."""
        pal = PALETTES["purple"]
        W, H = CARD_W, CARD_H
        img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")
        img = _glow_circle(img, W // 2, H // 3, 900, pal["glow"], 0.3)
        img = _glow_circle(img, W // 2, H * 2 // 3, 600, pal["accent2"], 0.2)
        draw = ImageDraw.Draw(img)

        # Top label
        f_label = self._font(60, bold=True)
        draw.text((W // 2, 70), label.upper(), fill=pal["accent"], font=f_label, anchor="mm")

        # Rating
        rating = round(getattr(player, "rating_pg", 7.0), 1)
        hex_y = 300
        hex_r = 160
        hex_pts = _hexagon_points(W // 2, hex_y, hex_r)
        draw.polygon(hex_pts, fill=(20, 20, 20, 240), outline=pal["accent"])
        f_rating = self._font(220, bold=True)
        draw.text((W // 2, hex_y), str(rating), fill=pal["badge"], font=f_rating, anchor="mm")
        f_ovr = self._font(40, bold=True)
        draw.text((W // 2, hex_y + 110), "OVR", fill=pal["text_dim"], font=f_ovr, anchor="mm")

        # Photo
        photo = _load_player_photo(player.name, self.assets_dir, (1300, 1300), photo_path=photo_path)
        if photo:
            px = (W - photo.width) // 2
            py = 650
            shadow = Image.new("RGBA", (photo.width + 100, photo.height + 100), (0, 0, 0, 0))
            s_draw = ImageDraw.Draw(shadow)
            s_draw.rounded_rectangle([20, 20, photo.width + 80, photo.height + 80], radius=40, fill=(*pal["glow"], 100))
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=40))
            img.paste(shadow, (px - 50, py - 50), shadow)
            mask = Image.new("L", photo.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, photo.width, photo.height], radius=40, fill=255)
            img.paste(photo, (px, py), mask)

        # Name
        f_name = self._font(140, bold=True)
        draw.text((W // 2, 2000), player.name.upper(), fill=pal["text"], font=f_name, anchor="mm")

        # Position
        f_pos = self._font(55, bold=True)
        pw, ph = 200, 80
        px = (W - pw) // 2
        draw.rounded_rectangle([px, 2140, px + pw, 2140 + ph], radius=18, fill=pal["accent"], outline=pal["accent2"], width=3)
        draw.text((W // 2, 2140 + ph // 2), pos.upper(), fill=(10, 10, 10), font=f_pos, anchor="mm")

        # Stats
        stats = [
            ("GOALS", getattr(player, "goals", 0)),
            ("ASSISTS", getattr(player, "assists", 0)),
            ("PASS %", f"{round(getattr(player, 'pass_accuracy', 0), 1)}%"),
            ("IMPACT", round(getattr(player, "impact_score", 0), 1)),
            ("FRAUD", round(getattr(player, "throwing_score", 0), 1)),
            ("CLUTCH", round(getattr(player, "clutch_score", 0), 1)),
        ]
        grid_y = 2300
        box_w = (W - MARGIN * 3) // 2
        box_h = 180
        f_slab = self._font(38, bold=True)
        f_sval = self._font(72, bold=True)
        for i, (sl, sv) in enumerate(stats):
            col = i % 2
            row = i // 2
            x = MARGIN + col * (box_w + MARGIN)
            y = grid_y + row * (box_h + 30)
            draw.rounded_rectangle([x, y, x + box_w, y + box_h], radius=24, fill=(25, 25, 25, 200), outline=(*pal["accent"], 150), width=3)
            draw.text((x + 30, y + 15), sl, fill=pal["text_dim"], font=f_slab)
            draw.text((x + 30, y + 70), str(sv), fill=pal["text"], font=f_sval)

        f_foot = self._font(36)
        draw.text((W // 2, H - 80), "RACHAD L3ERGONI • ANIME EDITION", fill=pal["text_dim"], font=f_foot, anchor="mm")

        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf

    def generate_beast_card(self, player, pos, photo_path=None):
        """Beast Mode — Blue theme."""
        return self._build_fc_card(player, pos, "blue", "BEAST MODE", photo_override=photo_path)

    def generate_court_case(self, player, pos, evidence, photo_path=None):
        """Court Case — Red theme with evidence list."""
        pal = PALETTES["red"]
        W, H = CARD_W, CARD_H
        img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")
        img = _glow_circle(img, W // 2, H // 3, 800, pal["glow"], 0.3)
        draw = ImageDraw.Draw(img)

        f_label = self._font(60, bold=True)
        draw.text((W // 2, 70), "⚖️ COURT CASE", fill=pal["accent"], font=f_label, anchor="mm")

        # Rating
        rating = round(getattr(player, "rating_pg", 7.0), 1)
        hex_y = 300
        hex_r = 150
        hex_pts = _hexagon_points(W // 2, hex_y, hex_r)
        draw.polygon(hex_pts, fill=(20, 20, 20, 240), outline=pal["accent"])
        f_rating = self._font(200, bold=True)
        draw.text((W // 2, hex_y), str(rating), fill=pal["badge"], font=f_rating, anchor="mm")

        # Photo
        photo = _load_player_photo(player.name, self.assets_dir, (1100, 1100), photo_path=photo_path)
        if photo:
            px = (W - photo.width) // 2
            py = 600
            shadow = Image.new("RGBA", (photo.width + 80, photo.height + 80), (0, 0, 0, 0))
            s_draw = ImageDraw.Draw(shadow)
            s_draw.rounded_rectangle([20, 20, photo.width + 60, photo.height + 60], radius=40, fill=(*pal["glow"], 80))
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=30))
            img.paste(shadow, (px - 40, py - 40), shadow)
            mask = Image.new("L", photo.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, photo.width, photo.height], radius=40, fill=255)
            img.paste(photo, (px, py), mask)

        # Name
        f_name = self._font(120, bold=True)
        draw.text((W // 2, 1800), player.name.upper(), fill=pal["text"], font=f_name, anchor="mm")
        f_pos = self._font(50, bold=True)
        draw.text((W // 2, 1940), pos.upper(), fill=pal["text_dim"], font=f_pos, anchor="mm")

        # Evidence box
        ev_y = 2040
        f_ev = self._font(42)
        line_h = 65
        box_h = len(evidence) * line_h + 80
        draw.rounded_rectangle([MARGIN, ev_y, W - MARGIN, ev_y + box_h], radius=24, fill=(20, 20, 20, 220), outline=pal["accent"], width=3)
        for i, ev in enumerate(evidence):
            draw.text((MARGIN + 40, ev_y + 40 + i * line_h), f"• {ev}", fill=pal["text"], font=f_ev)

        # Verdict
        verdict = "GUILTY" if getattr(player, "throwing_score", 0) > 3.0 or getattr(player, "rating_pg", 7) < 5.5 else "NOT GUILTY"
        v_y = ev_y + box_h + 60
        v_color = pal["accent"] if verdict == "GUILTY" else (50, 255, 100)
        f_verdict = self._font(100, bold=True)
        draw.text((W // 2, v_y), verdict, fill=v_color, font=f_verdict, anchor="mm")

        f_foot = self._font(36)
        draw.text((W // 2, H - 80), "RACHAD L3ERGONI • COURT OF LAW", fill=pal["text_dim"], font=f_foot, anchor="mm")

        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf

    def generate_playmaker_card(self, player, pos, photo_path=None):
        """Playmaker — Green theme."""
        return self._build_fc_card(player, pos, "green", "PLAYMAKER", photo_override=photo_path)

    def generate_sniper_card(self, player, pos, photo_path=None):
        """Sniper — Blue theme."""
        return self._build_fc_card(player, pos, "blue", "SNIPER", photo_override=photo_path)

    def generate_leaderboard(self, players, metric):
        """Leaderboard card — Dark theme with top 5."""
        pal = PALETTES["dark"]
        W, H = CARD_W, CARD_H
        img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")
        img = _glow_circle(img, W // 2, H // 2, 800, pal["glow"], 0.2)
        draw = ImageDraw.Draw(img)

        f_title = self._font(80, bold=True)
        draw.text((W // 2, 80), f"LEADERBOARD — {metric.upper().replace('_', ' ')}", fill=pal["accent"], font=f_title, anchor="mm")

        # Sort players
        sorted_players = sorted(players, key=lambda p: getattr(p, metric, 0), reverse=True)[:5]
        row_h = 500
        start_y = 250
        f_rank = self._font(100, bold=True)
        f_name = self._font(70, bold=True)
        f_val = self._font(90, bold=True)
        medals = ["🥇", "🥈", "🥉", "4.", "5."]

        for i, p in enumerate(sorted_players):
            y = start_y + i * row_h
            # Row bg
            draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + row_h - 30], radius=30, fill=(30, 30, 30, 200), outline=(*pal["accent"], 100), width=2)
            # Medal / Rank
            draw.text((MARGIN + 60, y + row_h // 2 - 30), medals[i], fill=pal["text"], font=f_rank)
            # Name
            draw.text((MARGIN + 200, y + row_h // 2 - 30), p.name, fill=pal["text"], font=f_name)
            # Value
            val = getattr(p, metric, 0)
            if isinstance(val, float):
                val = round(val, 1)
            draw.text((W - MARGIN - 60, y + row_h // 2 - 30), str(val), fill=pal["accent"], font=f_val, anchor="rm")

        f_foot = self._font(36)
        draw.text((W // 2, H - 80), "RACHAD L3ERGONI • PRO CLUBS TRACKER", fill=pal["text_dim"], font=f_foot, anchor="mm")

        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf

    def generate_match_report(self, club, motm):
        """Club info / match report — Dark Gold theme."""
        pal = PALETTES["gold"]
        W, H = CARD_W, CARD_H
        img = _gradient_bg(W, H, (5, 5, 5), (20, 15, 5)).convert("RGBA")
        img = _glow_circle(img, W // 2, H // 3, 700, pal["glow"], 0.2)
        draw = ImageDraw.Draw(img)

        f_title = self._font(90, bold=True)
        draw.text((W // 2, 100), club.club_name.upper(), fill=pal["accent"], font=f_title, anchor="mm")

        f_sub = self._font(50)
        draw.text((W // 2, 220), f"Division {club.division} • Skill {club.skill_rating}", fill=pal["text_dim"], font=f_sub, anchor="mm")
        draw.text((W // 2, 300), f"{club.wins}W — {club.losses}L — {club.draws}D", fill=pal["text"], font=f_sub, anchor="mm")

        # MOTM section
        motm_y = 420
        f_motm = self._font(60, bold=True)
        draw.text((W // 2, motm_y), "MAN OF THE MATCH", fill=pal["accent2"], font=f_motm, anchor="mm")

        f_mname = self._font(120, bold=True)
        draw.text((W // 2, motm_y + 120), motm.name.upper(), fill=pal["text"], font=f_mname, anchor="mm")

        f_mstats = self._font(50)
        draw.text((W // 2, motm_y + 260), f"Impact: {motm.impact_score} | Goals: {motm.goals} | Rating: {round(motm.rating_pg, 1)}", fill=pal["text_dim"], font=f_mstats, anchor="mm")

        # Recent matches
        match_y = motm_y + 400
        f_match = self._font(48, bold=True)
        draw.text((W // 2, match_y), "RECENT MATCHES", fill=pal["accent"], font=f_match, anchor="mm")

        f_mrow = self._font(42)
        for i, m in enumerate(club.matches[:5]):
            y = match_y + 80 + i * 90
            color = (50, 255, 100) if m.result == "W" else (255, 50, 50) if m.result == "L" else (255, 255, 0)
            draw.text((MARGIN + 40, y), f"{m.result}", fill=color, font=f_mrow)
            draw.text((MARGIN + 200, y), f"{m.score_for} - {m.score_against} vs {m.opponent}", fill=pal["text"], font=f_mrow)
            draw.text((W - MARGIN - 40, y), m.date.strftime("%d/%m/%Y"), fill=pal["text_dim"], font=f_mrow, anchor="rm")

        f_foot = self._font(36)
        draw.text((W // 2, H - 80), "RACHAD L3ERGONI • MATCH REPORT", fill=pal["text_dim"], font=f_foot, anchor="mm")

        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf

    def generate_daily_card(self, player, stat_name, stat_value, roast, is_bad=False, photo_path=None):
        """Daily Stat card — Red for bad, Gold for good."""
        pal = PALETTES["red"] if is_bad else PALETTES["gold"]
        W, H = CARD_W, CARD_H
        img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")
        img = _glow_circle(img, W // 2, H // 3, 800, pal["glow"], 0.35)
        draw = ImageDraw.Draw(img)

        title = "📉 STAT OF THE DAY" if is_bad else "📈 STAT OF THE DAY"
        f_title = self._font(70, bold=True)
        draw.text((W // 2, 80), title, fill=pal["accent"], font=f_title, anchor="mm")

        f_stat = self._font(60)
        draw.text((W // 2, 180), f"{stat_name}: {stat_value}", fill=pal["text"], font=f_stat, anchor="mm")

        # Photo
        photo = _load_player_photo(player.name, self.assets_dir, (1200, 1200), photo_path=photo_path)
        if photo:
            px = (W - photo.width) // 2
            py = 320
            shadow = Image.new("RGBA", (photo.width + 80, photo.height + 80), (0, 0, 0, 0))
            s_draw = ImageDraw.Draw(shadow)
            s_draw.rounded_rectangle([20, 20, photo.width + 60, photo.height + 60], radius=40, fill=(*pal["glow"], 100))
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=30))
            img.paste(shadow, (px - 40, py - 40), shadow)
            mask = Image.new("L", photo.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, photo.width, photo.height], radius=40, fill=255)
            img.paste(photo, (px, py), mask)

        # Name
        f_name = self._font(130, bold=True)
        draw.text((W // 2, 1600), player.name.upper(), fill=pal["text"], font=f_name, anchor="mm")

        # Roast text
        roast_y = 1760
        f_roast = self._font(50)
        words = roast.split()
        lines = []
        line = ""
        for w in words:
            if len(line + " " + w) < 55:
                line += " " + w if line else w
            else:
                lines.append(line)
                line = w
        if line:
            lines.append(line)
        text_h = len(lines) * 80 + 60
        draw.rounded_rectangle([MARGIN, roast_y, W - MARGIN, roast_y + text_h], radius=30, fill=(20, 20, 20, 220), outline=pal["accent"], width=4)
        for i, ln in enumerate(lines):
            draw.text((W // 2, roast_y + 50 + i * 80), ln, fill=pal["text"], font=f_roast, anchor="mm")

        # Mini stats
        stats = [
            ("GOALS", getattr(player, "goals", 0)),
            ("ASSISTS", getattr(player, "assists", 0)),
            ("RATING", round(getattr(player, "rating_pg", 0), 1)),
        ]
        grid_y = roast_y + text_h + 80
        box_w = (W - MARGIN * 4) // 3
        box_h = 160
        f_slab = self._font(36, bold=True)
        f_sval = self._font(64, bold=True)
        for i, (sl, sv) in enumerate(stats):
            x = MARGIN + i * (box_w + MARGIN // 2)
            y = grid_y
            draw.rounded_rectangle([x, y, x + box_w, y + box_h], radius=20, fill=(25, 25, 25, 200), outline=(*pal["accent"], 120), width=3)
            draw.text((x + 20, y + 10), sl, fill=pal["text_dim"], font=f_slab)
            draw.text((x + 20, y + 60), str(sv), fill=pal["text"], font=f_sval)

        f_foot = self._font(36)
        draw.text((W // 2, H - 80), "RACHAD L3ERGONI • DAILY STAT", fill=pal["text_dim"], font=f_foot, anchor="mm")

        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf
