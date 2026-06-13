"""
Rachad L3ERGONI Bot - Image Generation Engine v2
Premium visual cards with REAL player photos
Inspired by EA FC Ultimate Team, Futbin, Sofascore
"""

import os
import io
import math
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import numpy as np

# Position colors (EA FC style)
POSITION_COLORS = {
    "ST": ("#FF6B35", "#FF4500"),   # Orange-Red (Attackers)
    "LW": ("#FF6B35", "#FF4500"),
    "RW": ("#FF6B35", "#FF4500"),
    "CM": ("#4ECDC4", "#00CED1"),   # Cyan-Teal (Midfielders)
    "CAM": ("#4ECDC4", "#00CED1"),
    "CDM": ("#4ECDC4", "#00CED1"),
    "CB": ("#45B7D1", "#1E90FF"),   # Blue (Defenders)
    "LB": ("#45B7D1", "#1E90FF"),
    "RB": ("#45B7D1", "#1E90FF"),
    "GK": ("#FFD93D", "#FFA500"),   # Gold-Orange (Goalkeepers)
    "LM": ("#4ECDC4", "#00CED1"),
    "RM": ("#4ECDC4", "#00CED1")
}

DARK_BG = (15, 15, 25)
CARD_BG = (25, 25, 40)
ACCENT_GOLD = (255, 215, 0)
ACCENT_RED = (255, 69, 69)
ACCENT_GREEN = (50, 205, 50)
TEXT_WHITE = (240, 240, 240)
TEXT_GRAY = (160, 160, 180)


class ImageGenerator:
    """Premium image generation for stats cards and reports"""

    def __init__(self, assets_dir: str = "assets"):
        self.assets_dir = assets_dir
        self._load_fonts()

    def _load_fonts(self):
        """Load system fonts"""
        self.fonts = {}
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arial.ttf"
        ]
        for path in candidates:
            if os.path.exists(path):
                if "Bold" in path or "bold" in path.lower():
                    self.fonts["bold"] = path
                else:
                    self.fonts["regular"] = path
                break
        if "bold" not in self.fonts and "regular" in self.fonts:
            self.fonts["bold"] = self.fonts["regular"]

    def _get_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        path = self.fonts.get("bold" if bold else "regular")
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                pass
        return ImageFont.load_default()

    def _load_player_photo(self, image_path: str, size: Tuple[int, int] = (350, 450)) -> Optional[Image.Image]:
        """Load and process player photo - supports .png, .jpeg, .jpg"""
        try:
            # Try the exact path first
            if not os.path.exists(image_path):
                # Try alternative extensions
                base = os.path.splitext(image_path)[0]
                for ext in ['.png', '.jpeg', '.jpg', '.PNG', '.JPEG', '.JPG']:
                    alt_path = base + ext
                    if os.path.exists(alt_path):
                        image_path = alt_path
                        break
                else:
                    return None

            img = Image.open(image_path).convert("RGBA")
            img = img.resize(size, Image.LANCZOS)
            # Create rounded mask
            mask = Image.new("L", size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([0, 0, size[0], size[1]], radius=30, fill=255)
            img.putalpha(mask)
            return img
        except Exception as e:
            print(f"[Photo Error] {image_path}: {e}")
            return None

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        return tuple(int(hex_color[i:i+2], 16) for i in (1, 3, 5))

    def _draw_gradient(self, draw: ImageDraw.Draw, width: int, height: int, color1: Tuple, color2: Tuple):
        for y in range(height):
            ratio = y / height
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

    def _draw_stat_bar(self, draw: ImageDraw.Draw, x: int, y: int, width: int, height: int,
                       value: float, max_value: float, color: Tuple, bg: Tuple = (40, 40, 60)):
        draw.rounded_rectangle([x, y, x + width, y + height], radius=height//2, fill=bg)
        if max_value > 0:
            fill_width = min(int((value / max_value) * width), width)
            if fill_width > 0:
                draw.rounded_rectangle([x, y, x + fill_width, y + height], radius=height//2, fill=color)

    def generate_player_card(self, name: str, stats: dict, player_info: dict) -> Image.Image:
        """Generate premium player card with REAL photo"""
        width, height = 900, 1200
        position = player_info.get("position", "ST")
        colors = POSITION_COLORS.get(position, ("#FF6B35", "#FF4500"))
        color1 = self._hex_to_rgb(colors[0])
        color2 = self._hex_to_rgb(colors[1])

        img = Image.new("RGB", (width, height), DARK_BG)
        draw = ImageDraw.Draw(img)

        # Gradient header
        self._draw_gradient(draw, width, 220, color1, color2)

        # Noise overlay
        noise = np.random.randint(0, 15, (220, width, 3), dtype=np.uint8)
        noise_img = Image.fromarray(noise, "RGB")
        img.paste(noise_img, (0, 0))

        # Load REAL player photo
        photo_path = player_info.get("image", "")
        photo = self._load_player_photo(photo_path, (350, 450))
        if photo:
            img.paste(photo, (520, 40), photo)

        # Level badge
        level = player_info.get("level", 1)
        draw.rounded_rectangle([width-140, 20, width-20, 95], radius=15, fill=(20, 20, 30))
        font_lvl = self._get_font(18)
        draw.text((width-130, 25), "LVL", fill=TEXT_GRAY, font=font_lvl)
        font_lvl_big = self._get_font(40, bold=True)
        draw.text((width-135, 45), str(level), fill=ACCENT_GOLD, font=font_lvl_big)

        # Position badge
        draw.rounded_rectangle([30, 25, 110, 75], radius=15, fill=(255, 255, 255))
        font_pos = self._get_font(28, bold=True)
        draw.text((48, 33), position, fill=(20, 20, 30), font=font_pos)

        # Style badge
        style = player_info.get("style", "Player")
        style_width = len(style) * 14 + 20
        draw.rounded_rectangle([120, 25, 120 + style_width, 75], radius=15, fill=(255, 255, 255, 180))
        font_style = self._get_font(20)
        draw.text((135, 38), style.upper(), fill=(20, 20, 30), font=font_style)

        # Name
        nickname = player_info.get("nickname", name)
        font_name = self._get_font(56, bold=True)
        draw.text((30, 105), nickname.upper(), fill=TEXT_WHITE, font=font_name)

        # PSN + Club
        psn = player_info.get("psn", name)
        font_psn = self._get_font(22)
        draw.text((30, 175), f"@{psn} | Rachad L3ERGONI", fill=(255, 255, 255, 180), font=font_psn)

        # Rating hexagon
        rating = stats.get("rating", 6.0)
        rating_color = ACCENT_GREEN if rating >= 7.5 else ACCENT_GOLD if rating >= 6.5 else ACCENT_RED
        cx, cy, r = 420, 130, 55
        points = []
        for i in range(6):
            angle = math.pi / 3 * i - math.pi / 6
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        draw.polygon(points, fill=(30, 30, 50), outline=rating_color, width=3)
        draw.polygon([(cx + p[0]*0.85 - cx*0.85 + cx, cy + p[1]*0.85 - cy*0.85 + cy) for p in points], fill=rating_color)
        font_rating = self._get_font(36, bold=True)
        bbox = draw.textbbox((0, 0), f"{rating:.1f}", font=font_rating)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((cx - tw//2, cy - th//2), f"{rating:.1f}", fill=TEXT_WHITE, font=font_rating)

        # Stats section
        y_offset = 260
        font_section = self._get_font(32, bold=True)
        draw.text((30, y_offset), "MATCH STATS (Last 5)", fill=TEXT_WHITE, font=font_section)
        draw.line([(30, y_offset + 45), (width - 30, y_offset + 45)], fill=(60, 60, 80), width=2)
        y_offset += 70

        stat_items = [
            ("Goals", stats.get("goals", 0), 10, "goals_per_match"),
            ("Assists", stats.get("assists", 0), 10, "assists_per_match"),
            ("Shots", stats.get("shots", 0), 20, "shots_per_match"),
            ("Pass Accuracy", stats.get("pass_accuracy", 0), 100, None),
            ("Key Passes", stats.get("key_passes", 0), 15, "key_passes_per_match"),
            ("Tackles", stats.get("tackles", 0), 15, "tackles_per_match"),
            ("Possession Losses", stats.get("possession_losses", 0), 20, "possession_losses_per_match"),
            ("Dribble Success", stats.get("dribble_success", 0), 100, None),
        ]

        font_label = self._get_font(22)
        font_value = self._get_font(26, bold=True)

        for label, value, max_val, per_key in stat_items:
            draw.text((30, y_offset), label, fill=TEXT_GRAY, font=font_label)
            val_text = f"{value}"
            if per_key and per_key in stats:
                val_text += f" ({stats[per_key]:.1f}/match)"
            draw.text((400, y_offset), val_text, fill=TEXT_WHITE, font=font_value)

            bar_color = ACCENT_GREEN if (label == "Pass Accuracy" and value >= 80) or (label == "Dribble Success" and value >= 70) else                        ACCENT_GOLD if (label == "Pass Accuracy" and value >= 60) or (label == "Dribble Success" and value >= 50) else                        ACCENT_RED if label == "Possession Losses" else color1
            self._draw_stat_bar(draw, 30, y_offset + 35, 740, 12, value, max_val, bar_color)
            y_offset += 65

        # Advanced metrics
        y_offset += 20
        draw.text((30, y_offset), "ADVANCED METRICS", fill=TEXT_WHITE, font=font_section)
        draw.line([(30, y_offset + 45), (width - 30, y_offset + 45)], fill=(60, 60, 80), width=2)
        y_offset += 70

        advanced = [
            ("Impact Score", stats.get("impact_score", 0), 50),
            ("Clutch Score", stats.get("clutch_score", 0), 20),
            ("Error Score", stats.get("error_score", 0), 30),
            ("Passing Influence", stats.get("passing_influence", 0), 30),
            ("Defensive Contribution", stats.get("defensive_contribution", 0), 25),
            ("Offensive Contribution", stats.get("offensive_contribution", 0), 30),
        ]

        for label, value, max_val in advanced:
            draw.text((30, y_offset), label, fill=TEXT_GRAY, font=font_label)
            draw.text((400, y_offset), f"{value:.1f}", fill=TEXT_WHITE, font=font_value)
            bar_color = ACCENT_GREEN if value >= max_val * 0.7 else ACCENT_GOLD if value >= max_val * 0.4 else ACCENT_RED
            self._draw_stat_bar(draw, 30, y_offset + 35, 740, 12, value, max_val, bar_color)
            y_offset += 65

        # Form + badges
        y_offset += 20
        form = stats.get("form_trend", "stable")
        form_color = ACCENT_GREEN if form == "up" else ACCENT_RED if form == "down" else ACCENT_GOLD
        form_emoji = "📈" if form == "up" else "📉" if form == "down" else "➡️"
        draw.rounded_rectangle([30, y_offset, 260, y_offset + 50], radius=25, fill=(40, 40, 60))
        draw.text((50, y_offset + 10), f"Form: {form_emoji} {form.upper()}", fill=form_color, font=font_value)

        motm = stats.get("motm_count", 0)
        draw.rounded_rectangle([280, y_offset, 480, y_offset + 50], radius=25, fill=(40, 40, 60))
        draw.text((300, y_offset + 10), f"MOTM: {motm}x", fill=ACCENT_GOLD, font=font_value)

        matches = stats.get("matches", 0)
        draw.rounded_rectangle([500, y_offset, 700, y_offset + 50], radius=25, fill=(40, 40, 60))
        draw.text((520, y_offset + 10), f"Matches: {matches}", fill=TEXT_WHITE, font=font_value)

        # Roast box
        y_offset += 80
        draw.rounded_rectangle([30, y_offset, width - 30, y_offset + 100], radius=20, fill=(40, 40, 60))
        font_roast_title = self._get_font(22, bold=True)
        font_roast = self._get_font(18)
        draw.text((50, y_offset + 12), "🔥 DARIJA ROAST", fill=color1, font=font_roast_title)

        # Generate roast text based on stats
        roasts = self._generate_card_roasts(player_info, stats)
        for i, roast in enumerate(roasts[:2]):
            draw.text((50, y_offset + 42 + i * 25), roast, fill=TEXT_WHITE, font=font_roast)

        # Footer
        draw.text((30, height - 35), "Rachad L3ERGONI Pro Clubs | Live EA FC Stats | 95% Roast Mode",
                 fill=(100, 100, 120), font=self._get_font(14))

        return img

    def _generate_card_roasts(self, player_info: dict, stats: dict) -> List[str]:
        """Generate contextual roasts for the card"""
        nickname = player_info.get("nickname", "Player")
        roasts = []

        if stats.get("goals", 0) == 0:
            roasts.append(f"{nickname}: 0 goals. z3ma... striker? walo. delete game.")
        elif stats.get("goals", 0) < stats.get("matches", 1) * 0.5:
            roasts.append(f"{nickname}: {stats['goals']} goals f {stats['matches']} matchs. b7al chi taxi khawya.")

        if stats.get("possession_losses", 0) > 15:
            roasts.append(f"{nickname}: {stats['possession_losses']} possession losses. z3ma... ballon d'or? hahahaha.")

        if stats.get("rating", 10) < 6.5:
            roasts.append(f"{nickname}: {stats['rating']:.1f}/10. pathetique. find a job.")

        if not roasts:
            roasts.append(f"{nickname}. walo. safi. chi m3a9ed l3ba.")

        return roasts

    def generate_motm_card(self, name: str, stats: dict, player_info: dict) -> Image.Image:
        """Generate MOTM card with gold styling and real photo"""
        width, height = 900, 1100
        img = Image.new("RGB", (width, height), DARK_BG)
        draw = ImageDraw.Draw(img)

        # Gold gradient header
        self._draw_gradient(draw, width, 220, (255, 215, 0), (255, 165, 0))

        # Crown
        font_crown = self._get_font(70, bold=True)
        draw.text((width//2 - 35, 20), "👑", fill=(20, 20, 30), font=font_crown)

        # MOTM title
        font_title = self._get_font(42, bold=True)
        draw.text((30, 110), "MAN OF THE MATCH", fill=(20, 20, 30), font=font_title)

        # Real photo
        photo_path = player_info.get("image", "")
        photo = self._load_player_photo(photo_path, (300, 380))
        if photo:
            img.paste(photo, (550, 240), photo)

        # Name
        nickname = player_info.get("nickname", name)
        font_name = self._get_font(52, bold=True)
        draw.text((30, 250), nickname.upper(), fill=ACCENT_GOLD, font=font_name)

        # Rating
        rating = stats.get("rating", 6.0)
        font_rating = self._get_font(64, bold=True)
        draw.text((600, 250), f"{rating:.1f}", fill=ACCENT_GOLD, font=font_rating)

        # Key stats
        y_offset = 340
        font_label = self._get_font(22)
        font_value = self._get_font(28, bold=True)

        key_stats = [
            ("Goals", stats.get("goals", 0)),
            ("Assists", stats.get("assists", 0)),
            ("Pass Accuracy", f"{stats.get('pass_accuracy', 0)}%"),
            ("Key Passes", stats.get("key_passes", 0)),
            ("Tackles", stats.get("tackles", 0)),
            ("Impact Score", f"{stats.get('impact_score', 0):.1f}"),
        ]

        for label, value in key_stats:
            draw.text((30, y_offset), label, fill=TEXT_GRAY, font=font_label)
            draw.text((350, y_offset), str(value), fill=TEXT_WHITE, font=font_value)
            y_offset += 55

        # Roast quote
        y_offset += 30
        draw.rounded_rectangle([30, y_offset, width - 30, y_offset + 100], radius=20, fill=(40, 40, 60))
        font_quote = self._get_font(22, bold=True)
        draw.text((50, y_offset + 20), f"{nickname} MOTM. {rating:.1f}/10.", fill=ACCENT_GOLD, font=font_quote)
        draw.text((50, y_offset + 55), "z3ma... best of the worst. 🤡 clown team.", fill=TEXT_GRAY, font=self._get_font(18))

        # Footer
        draw.text((30, height - 40), "Rachad L3ERGONI Pro Clubs | MOTM Card",
                 fill=(100, 100, 120), font=self._get_font(14))

        return img

    def generate_comparison_card(self, p1_name: str, p1_stats: dict, p1_info: dict,
                                  p2_name: str, p2_stats: dict, p2_info: dict) -> Image.Image:
        """Generate 1v1 comparison with real photos"""
        width, height = 1000, 800
        img = Image.new("RGB", (width, height), DARK_BG)
        draw = ImageDraw.Draw(img)

        # VS badge
        cx, cy = width // 2, 80
        draw.ellipse([cx - 75, cy - 75, cx + 75, cy + 75], fill=ACCENT_RED)
        font_vs = self._get_font(52, bold=True)
        bbox = draw.textbbox((0, 0), "VS", font=font_vs)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((cx - tw//2, cy - th//2), "VS", fill=TEXT_WHITE, font=font_vs)

        # Player 1 (left)
        c1 = self._hex_to_rgb(POSITION_COLORS.get(p1_info.get("position", "ST"), ("#FF6B35", "#FF4500"))[0])
        p1_photo = self._load_player_photo(p1_info.get("image", ""), (200, 260))
        if p1_photo:
            img.paste(p1_photo, (50, 180), p1_photo)

        p1_nick = p1_info.get("nickname", p1_name)
        font_name = self._get_font(32, bold=True)
        draw.text((50, 460), p1_nick.upper(), fill=c1, font=font_name)

        # Player 2 (right)
        c2 = self._hex_to_rgb(POSITION_COLORS.get(p2_info.get("position", "ST"), ("#4ECDC4", "#00CED1"))[0])
        p2_photo = self._load_player_photo(p2_info.get("image", ""), (200, 260))
        if p2_photo:
            img.paste(p2_photo, (750, 180), p2_photo)

        p2_nick = p2_info.get("nickname", p2_name)
        bbox = draw.textbbox((0, 0), p2_nick.upper(), font=font_name)
        tw = bbox[2] - bbox[0]
        draw.text((950 - tw, 460), p2_nick.upper(), fill=c2, font=font_name)

        # Stats comparison
        y_offset = 530
        font_label = self._get_font(20)
        font_value = self._get_font(24, bold=True)

        compare_stats = [
            ("Rating", "rating", 10),
            ("Goals", "goals", 10),
            ("Assists", "assists", 10),
            ("Pass Accuracy", "pass_accuracy", 100),
            ("Impact Score", "impact_score", 50),
        ]

        for label, key, max_val in compare_stats:
            v1 = p1_stats.get(key, 0)
            v2 = p2_stats.get(key, 0)

            draw.text((30, y_offset), label, fill=TEXT_GRAY, font=font_label)

            bar1 = int((v1 / max_val) * 400) if max_val > 0 else 0
            bar1_color = c1 if v1 >= v2 else (80, 80, 100)
            draw.rounded_rectangle([30, y_offset + 28, 30 + bar1, y_offset + 48], radius=10, fill=bar1_color)
            draw.text((30, y_offset + 28), str(v1), fill=TEXT_WHITE, font=font_value)

            bar2 = int((v2 / max_val) * 400) if max_val > 0 else 0
            bar2_color = c2 if v2 >= v1 else (80, 80, 100)
            draw.rounded_rectangle([970 - bar2, y_offset + 28, 970, y_offset + 48], radius=10, fill=bar2_color)
            bbox = draw.textbbox((0, 0), str(v2), font=font_value)
            tw = bbox[2] - bbox[0]
            draw.text((970 - tw, y_offset + 28), str(v2), fill=TEXT_WHITE, font=font_value)

            y_offset += 65

        # Winner
        p1_score = sum(p1_stats.get(k, 0) for k in ["goals", "assists", "rating", "impact_score"])
        p2_score = sum(p2_stats.get(k, 0) for k in ["goals", "assists", "rating", "impact_score"])
        winner = p1_nick if p1_score > p2_score else p2_nick if p2_score > p1_score else "NOSS NOSS"

        draw.rounded_rectangle([250, height - 90, 750, height - 40], radius=30, fill=(40, 40, 60))
        font_winner = self._get_font(26, bold=True)
        draw.text((280, height - 80), f"Winner: {winner}", fill=ACCENT_GOLD, font=font_winner)

        return img

    def generate_leaderboard_card(self, leaderboard: List, period: str = "weekly") -> Image.Image:
        """Generate leaderboard card"""
        width, height = 900, 1000
        img = Image.new("RGB", (width, height), DARK_BG)
        draw = ImageDraw.Draw(img)

        # Gold header
        self._draw_gradient(draw, width, 120, (255, 215, 0), (255, 165, 0))

        font_title = self._get_font(40, bold=True)
        draw.text((30, 25), f"LEADERBOARD - {period.upper()}", fill=(20, 20, 30), font=font_title)

        y_offset = 150
        font_rank = self._get_font(32, bold=True)
        font_name = self._get_font(26, bold=True)
        font_stats = self._get_font(18)

        for i, (name, stats) in enumerate(leaderboard[:10]):
            rank_color = ACCENT_GOLD if i == 0 else (192, 192, 192) if i == 1 else (205, 127, 50) if i == 2 else (60, 60, 80)
            draw.ellipse([20, y_offset, 70, y_offset + 50], fill=rank_color)
            bbox = draw.textbbox((0, 0), str(i+1), font=font_rank)
            tw = bbox[2] - bbox[0]
            draw.text((45 - tw//2, y_offset + 5), str(i+1), fill=TEXT_WHITE, font=font_rank)

            draw.text((80, y_offset + 5), name, fill=TEXT_WHITE, font=font_name)

            rating = stats.get("rating", 0)
            goals = stats.get("goals", 0)
            assists = stats.get("assists", 0)
            draw.text((400, y_offset + 12), f"{rating:.1f}⭐ | {goals}G {assists}A", fill=TEXT_GRAY, font=font_stats)

            self._draw_stat_bar(draw, 80, y_offset + 42, 700, 8, rating, 10,
                               ACCENT_GREEN if rating >= 7.5 else ACCENT_GOLD if rating >= 6.5 else ACCENT_RED)

            y_offset += 75

        return img

    def generate_match_report_card(self, match: dict) -> Image.Image:
        """Generate match report card"""
        width, height = 900, 1100
        img = Image.new("RGB", (width, height), DARK_BG)
        draw = ImageDraw.Draw(img)

        result = match.get("result", "draw")
        result_color = ACCENT_GREEN if result == "win" else ACCENT_RED if result == "loss" else ACCENT_GOLD
        self._draw_gradient(draw, width, 150, result_color, tuple(max(0, c - 50) for c in result_color))

        team_goals = match.get("team_goals", 0)
        opponent_goals = match.get("opponent_goals", 0)
        opponent = match.get("opponent", "Unknown")

        font_score = self._get_font(60, bold=True)
        score_text = f"{team_goals} - {opponent_goals}"
        bbox = draw.textbbox((0, 0), score_text, font=font_score)
        tw = bbox[2] - bbox[0]
        draw.text((width//2 - tw//2, 25), score_text, fill=TEXT_WHITE, font=font_score)

        font_opp = self._get_font(26)
        draw.text((30, 95), f"vs {opponent}", fill=(255, 255, 255, 180), font=font_opp)

        y_offset = 180
        font_label = self._get_font(22)
        font_value = self._get_font(24, bold=True)

        team_stats = [
            ("Possession", match.get("team_possession", 50), match.get("opponent_possession", 50)),
            ("Shots", match.get("team_shots", 0), match.get("opponent_shots", 0)),
            ("Shots on Target", match.get("team_shots_on_target", 0), match.get("opponent_shots_on_target", 0)),
            ("Passes", match.get("team_passes", 0), match.get("opponent_passes", 0)),
            ("Tackles", match.get("team_tackles", 0), match.get("opponent_tackles", 0)),
            ("Corners", match.get("team_corners", 0), match.get("opponent_corners", 0)),
        ]

        for label, team_val, opp_val in team_stats:
            draw.text((30, y_offset), label, fill=TEXT_GRAY, font=font_label)

            total = team_val + opp_val if team_val + opp_val > 0 else 1
            team_pct = team_val / total

            team_width = int(team_pct * 400)
            draw.rounded_rectangle([30, y_offset + 30, 30 + team_width, y_offset + 50], radius=10, fill=ACCENT_GREEN)
            draw.text((30, y_offset + 30), str(team_val), fill=TEXT_WHITE, font=font_value)

            opp_width = int((1 - team_pct) * 400)
            draw.rounded_rectangle([870 - opp_width, y_offset + 30, 870, y_offset + 50], radius=10, fill=ACCENT_RED)
            bbox = draw.textbbox((0, 0), str(opp_val), font=font_value)
            tw = bbox[2] - bbox[0]
            draw.text((870 - tw, y_offset + 30), str(opp_val), fill=TEXT_WHITE, font=font_value)

            y_offset += 70

        # Player stats
        y_offset += 20
        draw.text((30, y_offset), "PLAYER STATS", fill=TEXT_WHITE, font=self._get_font(30, bold=True))
        draw.line([(30, y_offset + 45), (870, y_offset + 45)], fill=(60, 60, 80), width=2)
        y_offset += 70

        player_stats = match.get("player_stats", {})
        font_ps = self._get_font(18)

        for name, ps in list(player_stats.items())[:8]:
            motm_badge = "👑 " if ps.get("motm") else ""
            draw.text((30, y_offset), f"{motm_badge}{name}", fill=TEXT_WHITE, font=font_ps)
            draw.text((300, y_offset), f"{ps.get('goals', 0)}G {ps.get('assists', 0)}A", fill=TEXT_GRAY, font=font_ps)
            draw.text((450, y_offset), f"⭐{ps.get('rating', 6.0)}", fill=ACCENT_GOLD, font=font_ps)
            draw.text((550, y_offset), f"{ps.get('shots', 0)} shots", fill=TEXT_GRAY, font=font_ps)
            y_offset += 35

        return img

    def to_bytes(self, img: Image.Image) -> bytes:
        buffer = io.BytesIO()
        img.save(buffer, "PNG", quality=95)
        buffer.seek(0)
        return buffer.getvalue()

    def save(self, img: Image.Image, path: str):
        img.save(path, "PNG", quality=95)
        return path


_image_gen = None

def get_image_generator(assets_dir: str = "assets") -> ImageGenerator:
    global _image_gen
    if _image_gen is None:
        _image_gen = ImageGenerator(assets_dir)
    return _image_gen
