"""
phase2_image_gen.py
UHD Card Generator — EA FC 26 Ultimate Team inspired.
Resolution: 1440x2160 (2K) or 2160x3840 (4K)
Uses real player photos from squad.json.
"""
import os
import io
import math
import json
from typing import Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

ASSETS_DIR = os.getenv("ASSETS_DIR", "assets")

# AURA CONFIGURATION
AURA_CONFIG = {
    "S-Tier": {
        "name": "MONSTER",
        "gradient": [(20, 0, 60), (80, 0, 120), (180, 50, 255)],
        "accent": (200, 100, 255),
        "glow": (150, 0, 255),
        "text": "S",
        "effect": "anime_energy",
    },
    "A-Tier": {
        "name": "ELITE",
        "gradient": [(60, 40, 0), (140, 100, 0), (255, 200, 50)],
        "accent": (255, 215, 0),
        "glow": (255, 180, 0),
        "text": "A",
        "effect": "golden_rays",
    },
    "B-Tier": {
        "name": "SOLID",
        "gradient": [(0, 40, 20), (0, 100, 60), (50, 255, 150)],
        "accent": (0, 255, 128),
        "glow": (0, 200, 100),
        "text": "B",
        "effect": "pulse",
    },
    "Fraud": {
        "name": "FRAUD",
        "gradient": [(80, 20, 20), (150, 50, 50), (255, 100, 100)],
        "accent": (255, 80, 80),
        "glow": (255, 0, 0),
        "text": "F",
        "effect": "clown",
    },
    "Ghost": {
        "name": "GHOST",
        "gradient": [(40, 40, 50), (80, 80, 100), (150, 150, 180)],
        "accent": (200, 200, 220),
        "glow": (180, 180, 200),
        "text": "G",
        "effect": "fog",
    },
    "Carry": {
        "name": "CARRY",
        "gradient": [(0, 20, 60), (0, 60, 120), (0, 150, 255)],
        "accent": (0, 200, 255),
        "glow": (0, 100, 255),
        "text": "K",
        "effect": "crown_aura",
    },
}

class UHDImageGenerator:
    """Generates premium UHD player cards."""

    def __init__(self, assets_dir: str = "assets", resolution: Tuple[int, int] = (1440, 2160)):
        self.assets_dir = assets_dir
        self.width, self.height = resolution
        self._squad_data = {}
        self._load_squad()
        self._init_fonts()

    def _load_squad(self):
        paths = ["squad.json", f"{self.assets_dir}/squad.json"]
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f2:
                        self._squad_data = json.load(f2)
                        break
                except:
                    pass

    def _init_fonts(self):
        self.font_paths = {
            "bold": self._find_font(["DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]),
            "regular": self._find_font(["DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]),
            "arabic": self._find_font(["NotoSansArabic-Bold.ttf", "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf"]),
        }

    def _find_font(self, candidates):
        for c in candidates:
            if c and os.path.exists(c):
                return c
        return None

    def _get_font(self, size: int, style: str = "regular"):
        path = self.font_paths.get(style, self.font_paths["regular"])
        try:
            return ImageFont.truetype(path, size) if path else ImageFont.load_default()
        except:
            return ImageFont.load_default()

    def _resolve_photo(self, player_name: str) -> str:
        """Find player photo from squad.json with fallbacks."""
        for key, player in self._squad_data.items():
            if player.get("name", "") == player_name or player.get("psn", "") == player_name or key == player_name:
                img = player.get("image", "")
                if img and os.path.exists(img):
                    return img
                name = player.get("name", key)
                psn = player.get("psn", "")
                for ext in [".png", ".jpg", ".jpeg"]:
                    for base in [name, psn, key]:
                        for prefix in [self.assets_dir, "assets", "", f"{self.assets_dir}/"]:
                            path = f"{prefix}{base}{ext}"
                            if os.path.exists(path):
                                return path
        return ""

    def generate_card(self, player_name: str, nickname: str, overall: int,
                     position: str, aura: str, stats: Dict[str, Any],
                     output_path: str = "card.png") -> str:
        """Generate full UHD card."""
        config = AURA_CONFIG.get(aura, AURA_CONFIG["B-Tier"])
        img = Image.new("RGB", (self.width, self.height), (10, 10, 15))
        draw = ImageDraw.Draw(img)
        self._draw_gradient_background(img, config["gradient"])
        self._draw_aura_effect(img, config)
        self._draw_frame(img, config)
        self._draw_top_section(draw, img, overall, nickname, position, config)
        photo_path = self._resolve_photo(player_name)
        self._draw_player_photo(img, photo_path, config)
        self._draw_stats_section(draw, img, stats, config)
        img = self._apply_final_effects(img, config)
        img.save(output_path, "PNG", quality=95)
        return output_path

    def _draw_gradient_background(self, img, colors):
        draw = ImageDraw.Draw(img)
        c1, c2, c3 = colors
        for y in range(self.height):
            ratio = y / self.height
            if ratio < 0.5:
                r = int(c1[0] + (c2[0] - c1[0]) * (ratio * 2))
                g = int(c1[1] + (c2[1] - c1[1]) * (ratio * 2))
                b = int(c1[2] + (c2[2] - c1[2]) * (ratio * 2))
            else:
                r = int(c2[0] + (c3[0] - c2[0]) * ((ratio - 0.5) * 2))
                g = int(c2[1] + (c3[1] - c2[1]) * ((ratio - 0.5) * 2))
                b = int(c2[2] + (c3[2] - c2[2]) * ((ratio - 0.5) * 2))
            draw.line([(0, y), (self.width, y)], fill=(r, g, b))

    def _draw_aura_effect(self, img, config):
        glow = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw_glow = ImageDraw.Draw(glow)
        center_x = self.width // 2
        center_y = int(self.height * 0.45)
        for i in range(8):
            radius = 300 + i * 60
            alpha = max(0, 40 - i * 5)
            color = config["glow"] + (alpha,)
            draw_glow.ellipse(
                [center_x - radius, center_y - radius,
                 center_x + radius, center_y + radius],
                fill=color
            )
        if config["effect"] in ["anime_energy", "crown_aura"]:
            for angle in range(0, 360, 15):
                rad = math.radians(angle)
                x1 = center_x + math.cos(rad) * 200
                y1 = center_y + math.sin(rad) * 200
                x2 = center_x + math.cos(rad) * 500
                y2 = center_y + math.sin(rad) * 500
                draw_glow.line([(x1, y1), (x2, y2)], fill=config["accent"] + (30,), width=3)
        glow = glow.filter(ImageFilter.GaussianBlur(radius=40))
        img.paste(glow, (0, 0), glow)

    def _draw_frame(self, img, config):
        draw = ImageDraw.Draw(img)
        accent = config["accent"]
        border_width = 8
        for i in range(border_width):
            alpha = int(255 * (1 - i / border_width))
            color = accent + (alpha,)
            draw.rectangle(
                [i, i, self.width - 1 - i, self.height - 1 - i],
                outline=color, width=1
            )
        margin = 60
        draw.rectangle(
            [margin, margin, self.width - margin, self.height - margin],
            outline=accent, width=2
        )
        corner_size = 40
        for x, y in [(margin, margin), (self.width - margin, margin),
                     (margin, self.height - margin), (self.width - margin, self.height - margin)]:
            draw.rectangle([x - corner_size//2, y - corner_size//2,
                          x + corner_size//2, y + corner_size//2],
                         outline=accent, width=3)

    def _draw_top_section(self, draw, img, overall, nickname, position, config):
        accent = config["accent"]
        circle_x, circle_y = 140, 140
        circle_radius = 90
        glow = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.ellipse(
            [circle_x - circle_radius - 20, circle_y - circle_radius - 20,
             circle_x + circle_radius + 20, circle_y + circle_radius + 20],
            fill=config["glow"] + (100,)
        )
        glow = glow.filter(ImageFilter.GaussianBlur(radius=20))
        img.paste(glow, (0, 0), glow)
        draw.ellipse(
            [circle_x - circle_radius, circle_y - circle_radius,
             circle_x + circle_radius, circle_y + circle_radius],
            fill=(20, 20, 25), outline=accent, width=6
        )
        font_big = self._get_font(100, "bold")
        text = str(overall)
        bbox = draw.textbbox((0, 0), text, font=font_big)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        draw.text((circle_x - text_w//2, circle_y - text_h//2 - 10), text,
                 fill=(255, 255, 255), font=font_big, stroke_width=3, stroke_fill=(0, 0, 0))
        font_pos = self._get_font(36, "bold")
        bbox = draw.textbbox((0, 0), position, font=font_pos)
        text_w = bbox[2] - bbox[0]
        draw.text((circle_x - text_w//2, circle_y + circle_radius + 20), position,
                 fill=accent, font=font_pos, stroke_width=2, stroke_fill=(0, 0, 0))
        font_name = self._get_font(72, "bold")
        bbox = draw.textbbox((0, 0), nickname, font=font_name)
        text_w = bbox[2] - bbox[0]
        name_x = self.width // 2 + 50
        name_y = 120
        name_glow = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        ng_draw = ImageDraw.Draw(name_glow)
        ng_draw.text((name_x, name_y), nickname, fill=config["glow"] + (120,), font=font_name)
        name_glow = name_glow.filter(ImageFilter.GaussianBlur(radius=15))
        img.paste(name_glow, (0, 0), name_glow)
        draw.text((name_x, name_y), nickname, fill=(255, 255, 255), font=font_name,
                 stroke_width=4, stroke_fill=(0, 0, 0))
        badge_x = self.width - 140
        badge_y = 140
        badge_radius = 70
        draw.ellipse(
            [badge_x - badge_radius, badge_y - badge_radius,
             badge_x + badge_radius, badge_y + badge_radius],
            fill=config["gradient"][2], outline=accent, width=5
        )
        font_tier = self._get_font(60, "bold")
        tier_text = config["text"]
        bbox = draw.textbbox((0, 0), tier_text, font=font_tier)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        draw.text((badge_x - text_w//2, badge_y - text_h//2), tier_text,
                 fill=(255, 255, 255), font=font_tier, stroke_width=3, stroke_fill=(0, 0, 0))
        font_aura = self._get_font(28, "bold")
        aura_name = config["name"]
        bbox = draw.textbbox((0, 0), aura_name, font=font_aura)
        text_w = bbox[2] - bbox[0]
        draw.text((badge_x - text_w//2, badge_y + badge_radius + 15), aura_name,
                 fill=accent, font=font_aura, stroke_width=2, stroke_fill=(0, 0, 0))

    def _draw_player_photo(self, img, photo_path, config):
        if not photo_path or not os.path.exists(photo_path):
            self._draw_silhouette(img, config)
            return
        try:
            photo = Image.open(photo_path).convert("RGBA")
            target_w = int(self.width * 0.55)
            target_h = int(self.height * 0.50)
            photo.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
            mask = Image.new("L", photo.size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([0, 0, photo.width, photo.height], radius=40, fill=255)
            photo.putalpha(mask)
            x = (self.width - photo.width) // 2
            y = int(self.height * 0.32) - photo.height // 2
            shadow = Image.new("RGBA", (photo.width + 40, photo.height + 40), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle([20, 20, photo.width + 20, photo.height + 20],
                               radius=40, fill=(0, 0, 0, 100))
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=20))
            img.paste(shadow, (x - 20, y - 20), shadow)
            img.paste(photo, (x, y), photo)
        except Exception as e:
            print(f"Photo error: {e}")
            self._draw_silhouette(img, config)

    def _draw_silhouette(self, img, config):
        draw = ImageDraw.Draw(img)
        center_x = self.width // 2
        center_y = int(self.height * 0.35)
        draw.ellipse([center_x - 100, center_y - 120, center_x + 100, center_y + 80],
                    fill=(40, 40, 50), outline=config["accent"], width=4)
        draw.ellipse([center_x - 60, center_y - 180, center_x + 60, center_y - 60],
                    fill=(50, 50, 60), outline=config["accent"], width=3)
        font = self._get_font(40, "bold")
        draw.text((center_x - 80, center_y + 100), "NO PHOTO", fill=(150, 150, 150), font=font)

    def _draw_stats_section(self, draw, img, stats, config):
        accent = config["accent"]
        stats_y_start = int(self.height * 0.68)
        stats_height = int(self.height * 0.30)
        panel = Image.new("RGBA", (self.width, stats_height), (0, 0, 0, 0))
        panel_draw = ImageDraw.Draw(panel)
        panel_draw.rectangle([0, 0, self.width, stats_height],
                            fill=(10, 10, 15, 180))
        panel = panel.filter(ImageFilter.GaussianBlur(radius=5))
        img.paste(panel, (0, stats_y_start), panel)
        display_stats = [
            ("GOALS", stats.get("goals", 0)),
            ("ASSISTS", stats.get("assists", 0)),
            ("RATING", stats.get("avg_rating", 0.0)),
            ("WIN %", f"{stats.get('win_rate', 0)}%"),
            ("MOTM", stats.get("motm", 0)),
            ("TACKLES", stats.get("tackles", 0)),
            ("INTER", stats.get("interceptions", 0)),
            ("POS LOST", stats.get("possession_losses", 0)),
            ("IMPACT", stats.get("impact_score", 0)),
            ("FRAUD", stats.get("fraud_score", 0)),
        ]
        cols = 5
        rows = 2
        cell_w = self.width // cols
        cell_h = stats_height // rows
        for idx, (label, value) in enumerate(display_stats):
            if idx >= cols * rows:
                break
            col = idx % cols
            row = idx // cols
            x = col * cell_w + cell_w // 2
            y = stats_y_start + row * cell_h + cell_h // 2 - 30
            cell_margin = 15
            draw.rounded_rectangle(
                [x - cell_w//2 + cell_margin, y - 20,
                 x + cell_w//2 - cell_margin, y + 80],
                radius=15, fill=(20, 20, 30, 200), outline=accent, width=2
            )
            font_label = self._get_font(22, "bold")
            bbox = draw.textbbox((0, 0), label, font=font_label)
            text_w = bbox[2] - bbox[0]
            draw.text((x - text_w//2, y - 10), label, fill=(180, 180, 180), font=font_label)
            font_value = self._get_font(38, "bold")
            val_str = str(value)
            bbox = draw.textbbox((0, 0), val_str, font=font_value)
            text_w = bbox[2] - bbox[0]
            draw.text((x - text_w//2, y + 25), val_str, fill=(255, 255, 255),
                     font=font_value, stroke_width=2, stroke_fill=(0, 0, 0))

    def _apply_final_effects(self, img, config):
        vignette = Image.new("RGBA", img.size, (0, 0, 0, 0))
        v_draw = ImageDraw.Draw(vignette)
        for i in range(min(self.width, self.height) // 2, 0, -50):
            alpha = int(30 * (1 - i / (min(self.width, self.height) // 2)))
            v_draw.rectangle([i, i, self.width - i, self.height - i],
                           outline=(0, 0, 0, alpha), width=50)
        img = Image.alpha_composite(img.convert("RGBA"), vignette).convert("RGB")
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.3)
        img = ImageEnhance.Color(img).enhance(1.2)
        return img

    def generate_to_bytes(self, player_name, nickname, overall, position, aura, stats):
        path = self.generate_card(player_name, nickname, overall, position, aura, stats,
                                   output_path="/tmp/card_temp.png")
        with open(path, "rb") as f2:
            buf = io.BytesIO(f2.read())
        buf.seek(0)
        return buf

    def generate_player_card(self, player, stats, aura, output_path="/tmp/card.png"):
        """Convenience: player is a PlayerStats-like object."""
        return self.generate_card(
            player_name=player.name,
            nickname=getattr(player, "nickname", player.name),
            overall=getattr(player, "level", 75),
            position=getattr(player, "position", "CM"),
            aura=aura,
            stats=stats,
            output_path=output_path
        )
