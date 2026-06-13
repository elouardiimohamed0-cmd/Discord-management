"""
Rachad L3ERGONI Bot - Image Generation Engine
Premium visual cards inspired by EA FC Ultimate Team, Futbin, Sofascore
"""

import os
import io
import math
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import numpy as np

# Color schemes by position
POSITION_COLORS = {
    "ST": ("#FF6B35", "#FF4500"),      # Orange-Red
    "LW": ("#FF6B35", "#FF4500"),
    "RW": ("#FF6B35", "#FF4500"),
    "CM": ("#4ECDC4", "#00CED1"),      # Cyan-Teal
    "CAM": ("#4ECDC4", "#00CED1"),
    "CDM": ("#4ECDC4", "#00CED1"),
    "CB": ("#45B7D1", "#1E90FF"),      # Blue
    "LB": ("#45B7D1", "#1E90FF"),
    "RB": ("#45B7D1", "#1E90FF"),
    "GK": ("#FFD93D", "#FFA500"),      # Gold-Orange
    "LM": ("#4ECDC4", "#00CED1"),
    "RM": ("#4ECDC4", "#00CED1")
}

DARK_BG = (18, 18, 28, 255)
CARD_BG = (25, 25, 40, 255)
ACCENT_GOLD = (255, 215, 0, 255)
ACCENT_RED = (255, 69, 69, 255)
ACCENT_GREEN = (50, 205, 50, 255)
TEXT_WHITE = (240, 240, 240, 255)
TEXT_GRAY = (160, 160, 180, 255)
TEXT_DARK = (80, 80, 100, 255)


class ImageGenerator:
    """Premium image generation for stats cards and reports"""

    def __init__(self, assets_dir: str = "assets"):
        self.assets_dir = assets_dir
        self._ensure_fonts()

    def _ensure_fonts(self):
        """Ensure fonts are available - use default if custom not found"""
        self.font_paths = {
            "title": None,
            "header": None,
            "body": None,
            "small": None
        }
        # Try to find system fonts
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arial.ttf"
        ]
        for path in font_candidates:
            if os.path.exists(path):
                if "Bold" in path or "bold" in path.lower():
                    self.font_paths["title"] = path
                    self.font_paths["header"] = path
                else:
                    self.font_paths["body"] = path
                    self.font_paths["small"] = path
                break

    def _get_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        """Get font at specified size"""
        path = self.font_paths["title"] if bold else self.font_paths["body"]
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                pass
        return ImageFont.load_default()

    def _create_gradient_background(self, width: int, height: int, color1: Tuple, color2: Tuple) -> Image.Image:
        """Create gradient background"""
        img = Image.new("RGBA", (width, height))
        draw = ImageDraw.Draw(img)
        for y in range(height):
            ratio = y / height
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b, 255))
        return img

    def _draw_stat_bar(self, draw: ImageDraw.Draw, x: int, y: int, width: int, height: int, 
                       value: float, max_value: float, color: Tuple, bg_color: Tuple = (40, 40, 60, 255)):
        """Draw a glowing stat bar"""
        # Background bar
        draw.rounded_rectangle([x, y, x + width, y + height], radius=height//2, fill=bg_color)
        # Value bar
        if max_value > 0:
            fill_width = int((value / max_value) * width)
            fill_width = min(fill_width, width)
            if fill_width > 0:
                draw.rounded_rectangle([x, y, x + fill_width, y + height], radius=height//2, fill=color)
                # Glow effect
                glow = Image.new("RGBA", (width, height + 4), (0, 0, 0, 0))
                glow_draw = ImageDraw.Draw(glow)
                glow_draw.rounded_rectangle([0, 2, fill_width, height + 2], radius=height//2, 
                                            fill=(color[0], color[1], color[2], 80))

    def _draw_hexagon(self, draw: ImageDraw.Draw, center: Tuple, size: int, fill: Tuple, outline: Optional[Tuple] = None):
        """Draw a hexagon shape"""
        points = []
        for i in range(6):
            angle = math.pi / 3 * i - math.pi / 6
            x = center[0] + size * math.cos(angle)
            y = center[1] + size * math.sin(angle)
            points.append((x, y))
        draw.polygon(points, fill=fill)
        if outline:
            draw.polygon(points, outline=outline, width=2)

    def generate_player_card(self, name: str, stats: dict, player_info: dict) -> Image.Image:
        """Generate premium player stats card"""
        width, height = 800, 1100
        position = player_info.get("position", "ST")
        colors = POSITION_COLORS.get(position, ("#FF6B35", "#FF4500"))
        color1 = tuple(int(colors[0][i:i+2], 16) for i in (1, 3, 5)) + (255,)
        color2 = tuple(int(colors[1][i:i+2], 16) for i in (1, 3, 5)) + (255,)

        # Create base image
        img = Image.new("RGBA", (width, height), DARK_BG)
        draw = ImageDraw.Draw(img)

        # Top gradient header
        header_height = 200
        header = self._create_gradient_background(width, header_height, color1, color2)
        img.paste(header, (0, 0))

        # Add noise texture overlay
        noise = np.random.randint(0, 20, (header_height, width, 4), dtype=np.uint8)
        noise_img = Image.fromarray(noise, "RGBA")
        noise_img.putalpha(30)
        img.paste(noise_img, (0, 0), noise_img)

        # Player number badge
        number = str(player_info.get("number", "?"))
        draw.ellipse([30, 30, 110, 110], fill=(255, 255, 255, 230))
        font_num = self._get_font(48, bold=True)
        bbox = draw.textbbox((0, 0), number, font=font_num)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        draw.text((70 - text_w//2, 70 - text_h//2), number, fill=(20, 20, 30, 255), font=font_num)

        # Position badge
        draw.rounded_rectangle([120, 35, 200, 75], radius=15, fill=(255, 255, 255, 200))
        font_pos = self._get_font(24, bold=True)
        bbox = draw.textbbox((0, 0), position, font=font_pos)
        text_w = bbox[2] - bbox[0]
        draw.text((160 - text_w//2, 42), position, fill=(20, 20, 30, 255), font=font_pos)

        # Player name
        font_name = self._get_font(52, bold=True)
        nickname = player_info.get("nickname", name)
        draw.text((30, 130), nickname, fill=TEXT_WHITE, font=font_name)

        # Real name subtitle
        font_sub = self._get_font(24)
        draw.text((30, 185), f"@{name} | Rachad L3ERGONI", fill=(255, 255, 255, 180), font=font_sub)

        # Rating hexagon
        rating = stats.get("rating", 6.0)
        rating_color = ACCENT_GREEN if rating >= 7.5 else ACCENT_GOLD if rating >= 6.5 else ACCENT_RED
        self._draw_hexagon(draw, (700, 100), 60, (30, 30, 50, 255), rating_color)
        self._draw_hexagon(draw, (700, 100), 50, rating_color)
        font_rating = self._get_font(42, bold=True)
        bbox = draw.textbbox((0, 0), f"{rating:.1f}", font=font_rating)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        draw.text((700 - text_w//2, 100 - text_h//2), f"{rating:.1f}", fill=TEXT_WHITE, font=font_rating)

        # Stats section
        y_offset = 240
        font_label = self._get_font(22)
        font_value = self._get_font(26, bold=True)

        # Section title
        font_section = self._get_font(32, bold=True)
        draw.text((30, y_offset), "PERFORMANCE STATS", fill=TEXT_WHITE, font=font_section)
        draw.line([(30, y_offset + 45), (770, y_offset + 45)], fill=(60, 60, 80, 255), width=2)
        y_offset += 70

        # Stats to display with bars
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

        for label, value, max_val, per_match_key in stat_items:
            # Label
            draw.text((30, y_offset), label, fill=TEXT_GRAY, font=font_label)

            # Value
            val_text = f"{value}"
            if per_match_key and per_match_key in stats:
                val_text += f" ({stats[per_match_key]:.1f}/match)"
            draw.text((400, y_offset), val_text, fill=TEXT_WHITE, font=font_value)

            # Bar
            bar_color = ACCENT_GREEN if (label == "Pass Accuracy" and value >= 80) or (label == "Dribble Success" and value >= 70) else                        ACCENT_GOLD if (label == "Pass Accuracy" and value >= 60) or (label == "Dribble Success" and value >= 50) else                        ACCENT_RED if label in ["Possession Losses"] else color1

            self._draw_stat_bar(draw, 30, y_offset + 35, 740, 12, value, max_val, bar_color)
            y_offset += 65

        # Advanced metrics section
        y_offset += 20
        draw.text((30, y_offset), "ADVANCED METRICS", fill=TEXT_WHITE, font=font_section)
        draw.line([(30, y_offset + 45), (770, y_offset + 45)], fill=(60, 60, 80, 255), width=2)
        y_offset += 70

        advanced_items = [
            ("Impact Score", stats.get("impact_score", 0), 50),
            ("Clutch Score", stats.get("clutch_score", 0), 20),
            ("Error Score", stats.get("error_score", 0), 30),
            ("Passing Influence", stats.get("passing_influence", 0), 30),
            ("Defensive Contribution", stats.get("defensive_contribution", 0), 25),
            ("Offensive Contribution", stats.get("offensive_contribution", 0), 30),
        ]

        for label, value, max_val in advanced_items:
            draw.text((30, y_offset), label, fill=TEXT_GRAY, font=font_label)
            draw.text((400, y_offset), f"{value:.1f}", fill=TEXT_WHITE, font=font_value)
            bar_color = ACCENT_GREEN if value >= max_val * 0.7 else ACCENT_GOLD if value >= max_val * 0.4 else ACCENT_RED
            self._draw_stat_bar(draw, 30, y_offset + 35, 740, 12, value, max_val, bar_color)
            y_offset += 65

        # Form indicator
        y_offset += 20
        form = stats.get("form_trend", "stable")
        form_color = ACCENT_GREEN if form == "up" else ACCENT_RED if form == "down" else ACCENT_GOLD
        form_emoji = "📈" if form == "up" else "📉" if form == "down" else "➡️"
        draw.rounded_rectangle([30, y_offset, 300, y_offset + 50], radius=25, fill=(40, 40, 60, 255))
        draw.text((50, y_offset + 8), f"Form: {form_emoji} {form.upper()}", fill=form_color, font=font_value)

        # MOTM count
        motm = stats.get("motm_count", 0)
        draw.rounded_rectangle([320, y_offset, 550, y_offset + 50], radius=25, fill=(40, 40, 60, 255))
        draw.text((340, y_offset + 8), f"MOTM: {motm}x", fill=ACCENT_GOLD, font=font_value)

        # Matches played
        matches = stats.get("matches", 0)
        draw.rounded_rectangle([570, y_offset, 770, y_offset + 50], radius=25, fill=(40, 40, 60, 255))
        draw.text((590, y_offset + 8), f"Matches: {matches}", fill=TEXT_WHITE, font=font_value)

        # Footer
        draw.text((30, height - 50), "Rachad L3ERGONI Pro Clubs | Generated by AI", 
                 fill=(100, 100, 120, 255), font=self._get_font(16))

        return img

    def generate_motm_card(self, name: str, stats: dict, player_info: dict) -> Image.Image:
        """Generate MOTM card with special styling"""
        width, height = 800, 1000
        img = Image.new("RGBA", (width, height), DARK_BG)
        draw = ImageDraw.Draw(img)

        # Gold gradient header
        header = self._create_gradient_background(width, 220, (255, 215, 0, 255), (255, 165, 0, 255))
        img.paste(header, (0, 0))

        # MOTM crown icon (text-based)
        font_crown = self._get_font(80, bold=True)
        draw.text((350, 20), "👑", fill=(255, 255, 255, 255), font=font_crown)

        # MOTM title
        font_title = self._get_font(48, bold=True)
        draw.text((30, 120), "MAN OF THE MATCH", fill=(20, 20, 30, 255), font=font_title)

        # Player name
        nickname = player_info.get("nickname", name)
        font_name = self._get_font(56, bold=True)
        draw.text((30, 240), nickname, fill=ACCENT_GOLD, font=font_name)

        # Rating
        rating = stats.get("rating", 6.0)
        font_rating = self._get_font(72, bold=True)
        draw.text((600, 240), f"{rating:.1f}", fill=ACCENT_GOLD, font=font_rating)

        # Stats
        y_offset = 350
        font_label = self._get_font(22)
        font_value = self._get_font(26, bold=True)

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
            draw.text((400, y_offset), str(value), fill=TEXT_WHITE, font=font_value)
            y_offset += 60

        # Quote box
        y_offset += 30
        draw.rounded_rectangle([30, y_offset, 770, y_offset + 120], radius=20, fill=(40, 40, 60, 255))
        font_quote = self._get_font(24, bold=True)
        draw.text((50, y_offset + 20), "z3ma... best of the worst. 🤡", fill=ACCENT_GOLD, font=font_quote)
        draw.text((50, y_offset + 60), "c'est pas serieux. clown team.", fill=TEXT_GRAY, font=self._get_font(20))

        # Footer
        draw.text((30, height - 50), "Rachad L3ERGONI Pro Clubs | MOTM Card", 
                 fill=(100, 100, 120, 255), font=self._get_font(16))

        return img

    def generate_comparison_card(self, p1_name: str, p1_stats: dict, p1_info: dict,
                                  p2_name: str, p2_stats: dict, p2_info: dict) -> Image.Image:
        """Generate 1v1 comparison card"""
        width, height = 900, 700
        img = Image.new("RGBA", (width, height), DARK_BG)
        draw = ImageDraw.Draw(img)

        # VS badge in center
        draw.ellipse([375, 20, 525, 170], fill=(255, 69, 69, 255))
        font_vs = self._get_font(60, bold=True)
        bbox = draw.textbbox((0, 0), "VS", font=font_vs)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        draw.text((450 - text_w//2, 95 - text_h//2), "VS", fill=TEXT_WHITE, font=font_vs)

        # Player 1 (left)
        color1 = POSITION_COLORS.get(p1_info.get("position", "ST"), ("#FF6B35", "#FF4500"))
        c1 = tuple(int(color1[0][i:i+2], 16) for i in (1, 3, 5)) + (255,)

        p1_nick = p1_info.get("nickname", p1_name)
        font_name = self._get_font(36, bold=True)
        draw.text((30, 200), p1_nick, fill=c1, font=font_name)

        # Player 2 (right)
        color2 = POSITION_COLORS.get(p2_info.get("position", "ST"), ("#4ECDC4", "#00CED1"))
        c2 = tuple(int(color2[0][i:i+2], 16) for i in (1, 3, 5)) + (255,)

        p2_nick = p2_info.get("nickname", p2_name)
        bbox = draw.textbbox((0, 0), p2_nick, font=font_name)
        text_w = bbox[2] - bbox[0]
        draw.text((870 - text_w, 200), p2_nick, fill=c2, font=font_name)

        # Stats comparison
        y_offset = 280
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

            # Left bar
            bar1_width = int((v1 / max_val) * 350) if max_val > 0 else 0
            bar1_color = c1 if v1 >= v2 else (80, 80, 100, 255)
            draw.rounded_rectangle([30, y_offset + 30, 30 + bar1_width, y_offset + 50], 
                                  radius=10, fill=bar1_color)
            draw.text((30, y_offset + 30), f"{v1}", fill=TEXT_WHITE, font=font_value)

            # Right bar
            bar2_width = int((v2 / max_val) * 350) if max_val > 0 else 0
            bar2_color = c2 if v2 >= v1 else (80, 80, 100, 255)
            draw.rounded_rectangle([870 - bar2_width, y_offset + 30, 870, y_offset + 50], 
                                  radius=10, fill=bar2_color)
            bbox = draw.textbbox((0, 0), f"{v2}", font=font_value)
            text_w = bbox[2] - bbox[0]
            draw.text((870 - text_w, y_offset + 30), f"{v2}", fill=TEXT_WHITE, font=font_value)

            y_offset += 70

        # Winner indicator
        p1_score = sum(p1_stats.get(k, 0) for k in ["goals", "assists", "rating", "impact_score"])
        p2_score = sum(p2_stats.get(k, 0) for k in ["goals", "assists", "rating", "impact_score"])
        winner = p1_nick if p1_score > p2_score else p2_nick if p2_score > p1_score else "NOSS NOSS"

        draw.rounded_rectangle([200, height - 100, 700, height - 40], radius=30, fill=(40, 40, 60, 255))
        font_winner = self._get_font(28, bold=True)
        draw.text((230, height - 90), f"Winner: {winner}", fill=ACCENT_GOLD, font=font_winner)

        return img

    def generate_leaderboard_card(self, leaderboard: List[Tuple[str, dict]], period: str = "weekly") -> Image.Image:
        """Generate leaderboard card"""
        width, height = 800, 900
        img = Image.new("RGBA", (width, height), DARK_BG)
        draw = ImageDraw.Draw(img)

        # Header
        header = self._create_gradient_background(width, 120, (255, 215, 0, 255), (255, 165, 0, 255))
        img.paste(header, (0, 0))

        font_title = self._get_font(42, bold=True)
        draw.text((30, 30), f"LEADERBOARD - {period.upper()}", fill=(20, 20, 30, 255), font=font_title)

        # Entries
        y_offset = 150
        font_rank = self._get_font(36, bold=True)
        font_name = self._get_font(28, bold=True)
        font_stats = self._get_font(20)

        for i, (name, stats) in enumerate(leaderboard[:10]):
            # Rank badge
            rank_color = ACCENT_GOLD if i == 0 else (192, 192, 192, 255) if i == 1 else (205, 127, 50, 255) if i == 2 else (60, 60, 80, 255)
            draw.ellipse([20, y_offset, 70, y_offset + 50], fill=rank_color)
            bbox = draw.textbbox((0, 0), str(i+1), font=font_rank)
            text_w = bbox[2] - bbox[0]
            draw.text((45 - text_w//2, y_offset + 5), str(i+1), fill=TEXT_WHITE, font=font_rank)

            # Name
            draw.text((80, y_offset + 5), name, fill=TEXT_WHITE, font=font_name)

            # Stats
            rating = stats.get("rating", 0)
            goals = stats.get("goals", 0)
            assists = stats.get("assists", 0)
            draw.text((400, y_offset + 10), f"{rating:.1f}⭐ | {goals}G {assists}A", 
                     fill=TEXT_GRAY, font=font_stats)

            # Rating bar
            self._draw_stat_bar(draw, 80, y_offset + 45, 700, 8, rating, 10, 
                               ACCENT_GREEN if rating >= 7.5 else ACCENT_GOLD if rating >= 6.5 else ACCENT_RED)

            y_offset += 75

        return img

    def generate_match_report_card(self, match: dict) -> Image.Image:
        """Generate match report card"""
        width, height = 800, 1000
        img = Image.new("RGBA", (width, height), DARK_BG)
        draw = ImageDraw.Draw(img)

        # Header with result color
        result = match.get("result", "draw")
        result_color = ACCENT_GREEN if result == "win" else ACCENT_RED if result == "loss" else ACCENT_GOLD
        header = self._create_gradient_background(width, 150, result_color, 
                                                   tuple(max(0, c - 50) for c in result_color[:3]) + (255,))
        img.paste(header, (0, 0))

        # Score
        team_goals = match.get("team_goals", 0)
        opponent_goals = match.get("opponent_goals", 0)
        opponent = match.get("opponent", "Unknown")

        font_score = self._get_font(64, bold=True)
        score_text = f"{team_goals} - {opponent_goals}"
        bbox = draw.textbbox((0, 0), score_text, font=font_score)
        text_w = bbox[2] - bbox[0]
        draw.text((400 - text_w//2, 30), score_text, fill=TEXT_WHITE, font=font_score)

        font_opp = self._get_font(28)
        draw.text((30, 100), f"vs {opponent}", fill=(255, 255, 255, 200), font=font_opp)

        # Team stats comparison
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

            # Team bar (left)
            team_width = int(team_pct * 350)
            draw.rounded_rectangle([30, y_offset + 30, 30 + team_width, y_offset + 50], 
                                  radius=10, fill=(50, 205, 50, 255))
            draw.text((30, y_offset + 30), str(team_val), fill=TEXT_WHITE, font=font_value)

            # Opp bar (right)
            opp_width = int((1 - team_pct) * 350)
            draw.rounded_rectangle([770 - opp_width, y_offset + 30, 770, y_offset + 50], 
                                  radius=10, fill=(255, 69, 69, 255))
            bbox = draw.textbbox((0, 0), str(opp_val), font=font_value)
            text_w = bbox[2] - bbox[0]
            draw.text((770 - text_w, y_offset + 30), str(opp_val), fill=TEXT_WHITE, font=font_value)

            y_offset += 70

        # Player stats section
        y_offset += 20
        draw.text((30, y_offset), "PLAYER STATS", fill=TEXT_WHITE, font=self._get_font(32, bold=True))
        draw.line([(30, y_offset + 45), (770, y_offset + 45)], fill=(60, 60, 80, 255), width=2)
        y_offset += 70

        player_stats = match.get("player_stats", {})
        font_ps = self._get_font(20)

        for name, ps in list(player_stats.items())[:8]:
            motm_badge = "👑 " if ps.get("motm") else ""
            draw.text((30, y_offset), f"{motm_badge}{name}", fill=TEXT_WHITE, font=font_ps)
            draw.text((300, y_offset), f"{ps.get('goals', 0)}G {ps.get('assists', 0)}A", fill=TEXT_GRAY, font=font_ps)
            draw.text((450, y_offset), f"⭐{ps.get('rating', 6.0)}", fill=ACCENT_GOLD, font=font_ps)
            draw.text((550, y_offset), f"{ps.get('shots', 0)} shots", fill=TEXT_GRAY, font=font_ps)
            y_offset += 35

        return img

    def save_image(self, img: Image.Image, path: str) -> str:
        """Save image to file and return path"""
        img.save(path, "PNG", quality=95)
        return path

    def to_bytes(self, img: Image.Image) -> bytes:
        """Convert image to bytes for Discord upload"""
        buffer = io.BytesIO()
        img.save(buffer, "PNG", quality=95)
        buffer.seek(0)
        return buffer.getvalue()


# Singleton instance
_image_gen = None

def get_image_generator(assets_dir: str = "assets") -> ImageGenerator:
    global _image_gen
    if _image_gen is None:
        _image_gen = ImageGenerator(assets_dir)
    return _image_gen
