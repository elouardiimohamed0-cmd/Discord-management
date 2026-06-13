"""
Rachad L3ERGONI Bot - Image Generator
Premium cards with real photos, gradients, glowing bars
NO numpy dependency - pure PIL only
"""

import os
import io
from typing import Dict, List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter


class ImageGenerator:
    """Generate premium visual cards for player stats, match reports, etc."""

    # Position colors
    POSITION_COLORS = {
        "gk": (0, 150, 255),      # Blue
        "def": (0, 200, 100),     # Green
        "mid": (255, 200, 0),     # Yellow
        "fwd": (255, 80, 80),     # Red
        "st": (255, 80, 80),      # Red
        "lw": (255, 100, 100),    # Light Red
        "rw": (255, 100, 100),    # Light Red
        "cam": (255, 180, 0),     # Orange
        "cm": (255, 200, 0),      # Yellow
        "cdm": (0, 180, 100),     # Dark Green
        "lb": (0, 200, 100),      # Green
        "rb": (0, 200, 100),      # Green
        "cb": (0, 180, 100),      # Dark Green
        "lm": (255, 200, 0),      # Yellow
        "rm": (255, 200, 0),      # Yellow
    }

    # Default gradient colors
    GRADIENTS = {
        "gold": [(255, 215, 0), (255, 165, 0), (255, 140, 0)],
        "elite": [(0, 255, 255), (0, 200, 255), (100, 150, 255)],
        "standard": [(255, 100, 100), (255, 80, 80), (200, 50, 50)],
        "dark": [(30, 30, 40), (20, 20, 30), (10, 10, 20)],
    }

    def __init__(self, assets_path: str = "assets"):
        self.assets_path = assets_path
        self.fonts = {}
        self._load_fonts()

    def _load_fonts(self):
        """Load fonts - fallback to default if custom fonts not found"""
        try:
            # Try to load a bold font for headers
            self.fonts["header"] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            self.fonts["subheader"] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            self.fonts["body"] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            self.fonts["small"] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            self.fonts["rating"] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        except:
            # Fallback to default font
            self.fonts["header"] = ImageFont.load_default()
            self.fonts["subheader"] = ImageFont.load_default()
            self.fonts["body"] = ImageFont.load_default()
            self.fonts["small"] = ImageFont.load_default()
            self.fonts["rating"] = ImageFont.load_default()

    def _get_gradient(self, width: int, height: int, colors: List[Tuple[int, int, int]]) -> Image.Image:
        """Create a vertical gradient background"""
        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)

        for y in range(height):
            ratio = y / height
            # Interpolate between colors
            if len(colors) == 2:
                r = int(colors[0][0] * (1 - ratio) + colors[1][0] * ratio)
                g = int(colors[0][1] * (1 - ratio) + colors[1][1] * ratio)
                b = int(colors[0][2] * (1 - ratio) + colors[1][2] * ratio)
            else:
                # Use first and last color for simple gradient
                r = int(colors[0][0] * (1 - ratio) + colors[-1][0] * ratio)
                g = int(colors[0][1] * (1 - ratio) + colors[-1][1] * ratio)
                b = int(colors[0][2] * (1 - ratio) + colors[-1][2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        return img

    def _draw_glowing_bar(self, draw: ImageDraw.Draw, x: int, y: int, width: int, height: int, 
                          value: float, max_value: float, color: Tuple[int, int, int]):
        """Draw a glowing stat bar"""
        ratio = min(value / max(max_value, 1), 1.0)
        fill_width = int(width * ratio)

        # Background bar
        draw.rounded_rectangle([x, y, x + width, y + height], radius=height//2, fill=(40, 40, 50))

        # Fill bar
        if fill_width > 0:
            draw.rounded_rectangle([x, y, x + fill_width, y + height], radius=height//2, fill=color)

        # Glow effect (simulated with brighter color on top edge)
        if fill_width > 2:
            glow_color = (min(color[0] + 50, 255), min(color[1] + 50, 255), min(color[2] + 50, 255))
            draw.line([(x, y), (x + fill_width, y)], fill=glow_color, width=2)

    def _draw_hexagon_rating(self, draw: ImageDraw.Draw, x: int, y: int, size: int, rating: float, color: Tuple[int, int, int]):
        """Draw a hexagon rating badge"""
        # Draw hexagon
        points = []
        for i in range(6):
            angle = 60 * i - 30
            rad = 3.14159 * angle / 180
            px = x + size * 0.5 * (1 + 0.9 * __import__("math").cos(rad))
            py = y + size * 0.5 * (1 + 0.9 * __import__("math").sin(rad))
            points.append((px, py))

        draw.polygon(points, fill=color, outline=(255, 255, 255))

        # Draw rating text
        text = f"{rating:.1f}"
        bbox = draw.textbbox((0, 0), text, font=self.fonts.get("rating", self.fonts["body"]))
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = x + (size - text_width) // 2
        text_y = y + (size - text_height) // 2
        draw.text((text_x, text_y), text, fill=(255, 255, 255), font=self.fonts.get("rating", self.fonts["body"]))

    def _load_player_photo(self, name: str) -> Optional[Image.Image]:
        """Load player photo from assets folder"""
        # Try multiple extensions
        for ext in [".png", ".jpg", ".jpeg", ".webp"]:
            path = os.path.join(self.assets_path, f"{name}{ext}")
            if os.path.exists(path):
                try:
                    img = Image.open(path).convert("RGBA")
                    return img
                except:
                    continue

        # Try with different name formats
        name_variants = [name, name.lower(), name.upper(), name.replace(" ", "_"), name.replace(" ", "")]
        for variant in name_variants:
            for ext in [".png", ".jpg", ".jpeg", ".webp"]:
                path = os.path.join(self.assets_path, f"{variant}{ext}")
                if os.path.exists(path):
                    try:
                        img = Image.open(path).convert("RGBA")
                        return img
                    except:
                        continue

        return None

    def _round_image_corners(self, img: Image.Image, radius: int) -> Image.Image:
        """Round corners of an image using alpha mask"""
        # Create rounded mask
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([0, 0, img.width, img.height], radius=radius, fill=255)

        # Apply mask
        result = img.copy()
        if result.mode != "RGBA":
            result = result.convert("RGBA")
        result.putalpha(mask)
        return result

    def generate_player_card(self, name: str, stats: dict, info: dict) -> Image.Image:
        """Generate a premium player stat card"""
        width, height = 800, 1000

        # Determine card tier based on rating
        rating = stats.get("rating", 6.0)
        if rating >= 8.5:
            gradient_colors = self.GRADIENTS["gold"]
            tier = "ELITE"
        elif rating >= 7.0:
            gradient_colors = self.GRADIENTS["elite"]
            tier = "PRO"
        else:
            gradient_colors = self.GRADIENTS["standard"]
            tier = "STANDARD"

        # Create base
        card = self._get_gradient(width, height, gradient_colors)
        draw = ImageDraw.Draw(card)

        # Position color
        position = info.get("position", "CM").lower()
        pos_color = self.POSITION_COLORS.get(position, (200, 200, 200))

        # Draw player photo
        photo = self._load_player_photo(name)
        if photo:
            photo_size = 300
            photo = photo.resize((photo_size, photo_size), Image.Resampling.LANCZOS)
            photo = self._round_image_corners(photo, 30)

            # Center photo at top
            photo_x = (width - photo_size) // 2
            photo_y = 80
            card.paste(photo, (photo_x, photo_y), photo)

        # Draw name and position
        nickname = info.get("nickname", name)
        draw.text((width//2, 420), nickname, fill=(255, 255, 255), font=self.fonts["header"], anchor="mm")
        draw.text((width//2, 460), f"{position.upper()} | {tier}", fill=pos_color, font=self.fonts["subheader"], anchor="mm")

        # Draw hexagon rating
        self._draw_hexagon_rating(draw, width//2 - 60, 500, 120, rating, pos_color)

        # Draw stat bars
        stats_to_show = [
            ("Goals", stats.get("goals", 0), 20, (255, 100, 100)),
            ("Assists", stats.get("assists", 0), 15, (100, 255, 100)),
            ("Pass Acc", stats.get("pass_accuracy", 0), 100, (100, 200, 255)),
            ("Tackles", stats.get("tackles", 0), 20, (255, 200, 100)),
            ("Rating", stats.get("rating", 6.0), 10, pos_color),
        ]

        bar_y = 650
        for label, value, max_val, color in stats_to_show:
            draw.text((50, bar_y), label, fill=(255, 255, 255), font=self.fonts["body"])
            self._draw_glowing_bar(draw, 200, bar_y, 500, 25, value, max_val, color)
            draw.text((710, bar_y), str(value), fill=(255, 255, 255), font=self.fonts["body"])
            bar_y += 50

        # Add impact score at bottom
        impact = stats.get("impact_score", 0)
        draw.text((width//2, 950), f"Impact Score: {impact:.1f}", fill=(255, 255, 255), font=self.fonts["subheader"], anchor="mm")

        return card

    def generate_motm_card(self, name: str, stats: dict, info: dict) -> Image.Image:
        """Generate Man of the Match card"""
        width, height = 800, 1000
        gradient_colors = self.GRADIENTS["gold"]

        card = self._get_gradient(width, height, gradient_colors)
        draw = ImageDraw.Draw(card)

        # Crown icon text
        draw.text((width//2, 80), "👑 MOTM", fill=(255, 215, 0), font=self.fonts["header"], anchor="mm")

        # Player photo
        photo = self._load_player_photo(name)
        if photo:
            photo_size = 280
            photo = photo.resize((photo_size, photo_size), Image.Resampling.LANCZOS)
            photo = self._round_image_corners(photo, 30)
            card.paste(photo, ((width - photo_size)//2, 150), photo)

        # Name and stats
        nickname = info.get("nickname", name)
        draw.text((width//2, 480), nickname, fill=(255, 255, 255), font=self.fonts["header"], anchor="mm")

        rating = stats.get("rating", 6.0)
        self._draw_hexagon_rating(draw, width//2 - 60, 530, 120, rating, (255, 215, 0))

        # Key stats
        draw.text((width//2, 700), f"Goals: {stats.get('goals', 0)}", fill=(255, 255, 255), font=self.fonts["subheader"], anchor="mm")
        draw.text((width//2, 740), f"Assists: {stats.get('assists', 0)}", fill=(255, 255, 255), font=self.fonts["subheader"], anchor="mm")
        draw.text((width//2, 780), f"Impact: {stats.get('impact_score', 0):.1f}", fill=(255, 255, 255), font=self.fonts["subheader"], anchor="mm")

        return card

    def generate_match_report_card(self, match_data: dict) -> Image.Image:
        """Generate match result card"""
        width, height = 800, 600

        result = match_data.get("result", "draw")
        if result == "win":
            colors = [(0, 150, 50), (0, 100, 30)]
        elif result == "loss":
            colors = [(150, 30, 30), (100, 20, 20)]
        else:
            colors = [(150, 150, 50), (100, 100, 30)]

        card = self._get_gradient(width, height, colors)
        draw = ImageDraw.Draw(card)

        # Score
        team_goals = match_data.get("team_goals", 0)
        opponent_goals = match_data.get("opponent_goals", 0)
        opponent = match_data.get("opponent", "Unknown")

        draw.text((width//2, 100), f"{team_goals} - {opponent_goals}", fill=(255, 255, 255), font=self.fonts["header"], anchor="mm")
        draw.text((width//2, 160), f"vs {opponent}", fill=(200, 200, 200), font=self.fonts["subheader"], anchor="mm")
        draw.text((width//2, 200), result.upper(), fill=(255, 255, 255), font=self.fonts["header"], anchor="mm")

        # Player stats summary
        player_stats = match_data.get("player_stats", {})
        y = 300
        for i, (pname, pstats) in enumerate(list(player_stats.items())[:5]):
            draw.text((50, y), f"{pname}: {pstats.get('goals', 0)}G {pstats.get('assists', 0)}A | {pstats.get('rating', 6.0):.1f}⭐", 
                     fill=(255, 255, 255), font=self.fonts["body"])
            y += 40

        return card

    def generate_leaderboard_card(self, leaderboard: List[Tuple[str, dict]], period: str) -> Image.Image:
        """Generate leaderboard card"""
        width, height = 800, 1000
        card = self._get_gradient(width, height, self.GRADIENTS["dark"])
        draw = ImageDraw.Draw(card)

        draw.text((width//2, 50), f"Leaderboard - {period.upper()}", fill=(255, 215, 0), font=self.fonts["header"], anchor="mm")

        y = 150
        for i, (name, stats) in enumerate(leaderboard[:10]):
            rank_color = (255, 215, 0) if i == 0 else (200, 200, 200) if i == 1 else (205, 127, 50) if i == 2 else (150, 150, 150)

            draw.text((50, y), f"#{i+1}", fill=rank_color, font=self.fonts["subheader"])
            draw.text((120, y), name, fill=(255, 255, 255), font=self.fonts["body"])
            draw.text((500, y), f"Impact: {stats.get('impact_score', 0):.1f}", fill=(255, 255, 255), font=self.fonts["body"])
            draw.text((650, y), f"{stats.get('rating', 0):.1f}⭐", fill=(255, 215, 0), font=self.fonts["body"])
            y += 70

        return card

    def generate_comparison_card(self, n1: str, s1: dict, i1: dict, n2: str, s2: dict, i2: dict) -> Image.Image:
        """Generate 1v1 player comparison card"""
        width, height = 1000, 800
        card = self._get_gradient(width, height, self.GRADIENTS["dark"])
        draw = ImageDraw.Draw(card)

        # Headers
        nick1 = i1.get("nickname", n1)
        nick2 = i2.get("nickname", n2)

        draw.text((250, 50), nick1, fill=(255, 100, 100), font=self.fonts["header"], anchor="mm")
        draw.text((750, 50), nick2, fill=(100, 100, 255), font=self.fonts["header"], anchor="mm")
        draw.text((500, 50), "VS", fill=(255, 255, 255), font=self.fonts["header"], anchor="mm")

        # Stats comparison
        stats_compare = [
            ("Goals", s1.get("goals", 0), s2.get("goals", 0)),
            ("Assists", s1.get("assists", 0), s2.get("assists", 0)),
            ("Rating", s1.get("rating", 0), s2.get("rating", 0)),
            ("Impact", s1.get("impact_score", 0), s2.get("impact_score", 0)),
            ("Pass %", s1.get("pass_accuracy", 0), s2.get("pass_accuracy", 0)),
        ]

        y = 150
        for label, v1, v2 in stats_compare:
            color1 = (0, 255, 100) if v1 > v2 else (255, 255, 255)
            color2 = (0, 255, 100) if v2 > v1 else (255, 255, 255)

            draw.text((250, y), f"{v1}", fill=color1, font=self.fonts["subheader"], anchor="mm")
            draw.text((500, y), label, fill=(200, 200, 200), font=self.fonts["body"], anchor="mm")
            draw.text((750, y), f"{v2}", fill=color2, font=self.fonts["subheader"], anchor="mm")
            y += 80

        return card

    def to_bytes(self, img: Image.Image) -> bytes:
        """Convert PIL Image to bytes for Discord upload"""
        buf = io.BytesIO()
        img = img.convert("RGB")
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf.getvalue()


def get_image_generator(assets_path: str = "assets") -> ImageGenerator:
    return ImageGenerator(assets_path)
