"""UHD Card Generator - EA FC 26 Ultimate Team inspired cards.
Generates 1440x2160 premium player cards with aura effects.
"""
import os
import math
import random
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance, ImageOps
import numpy as np

import config
from aura_system import AuraTier, AuraConfig, AURA_CONFIGS, get_aura_system
from player_mapper import get_mapper

# Card dimensions
CARD_W = config.CARD_WIDTH  # 1440
CARD_H = config.CARD_HEIGHT  # 2160

@dataclass
class CardColors:
    """Color scheme for a card type."""
    bg_top: Tuple[int, int, int]
    bg_bottom: Tuple[int, int, int]
    accent: Tuple[int, int, int]
    text_primary: Tuple[int, int, int]
    text_secondary: Tuple[int, int, int]
    stat_bar_fill: Tuple[int, int, int]
    stat_bar_bg: Tuple[int, int, int]
    glow: Tuple[int, int, int, int]

# Card type color schemes
CARD_SCHEMES = {
    "gold_metal": CardColors(
        bg_top=(212, 175, 55),
        bg_bottom=(139, 90, 43),
        accent=(255, 215, 0),
        text_primary=(30, 20, 10),
        text_secondary=(80, 60, 30),
        stat_bar_fill=(255, 215, 0),
        stat_bar_bg=(60, 45, 20),
        glow=(255, 215, 0, 120),
    ),
    "purple_blue_energy": CardColors(
        bg_top=(75, 0, 130),
        bg_bottom=(0, 0, 139),
        accent=(138, 43, 226),
        text_primary=(240, 240, 255),
        text_secondary=(180, 180, 220),
        stat_bar_fill=(138, 43, 226),
        stat_bar_bg=(30, 20, 60),
        glow=(138, 43, 226, 180),
    ),
    "green_neon": CardColors(
        bg_top=(0, 100, 0),
        bg_bottom=(0, 50, 0),
        accent=(50, 205, 50),
        text_primary=(240, 255, 240),
        text_secondary=(150, 220, 150),
        stat_bar_fill=(50, 205, 50),
        stat_bar_bg=(20, 40, 20),
        glow=(50, 205, 50, 140),
    ),
    "blue_lock_king": CardColors(
        bg_top=(0, 0, 80),
        bg_bottom=(0, 0, 40),
        accent=(65, 105, 225),
        text_primary=(220, 230, 255),
        text_secondary=(150, 170, 220),
        stat_bar_fill=(0, 191, 255),
        stat_bar_bg=(20, 30, 60),
        glow=(0, 191, 255, 200),
    ),
    "clown_circus": CardColors(
        bg_top=(180, 50, 50),
        bg_bottom=(100, 20, 20),
        accent=(255, 0, 0),
        text_primary=(255, 240, 240),
        text_secondary=(220, 150, 150),
        stat_bar_fill=(255, 80, 80),
        stat_bar_bg=(60, 20, 20),
        glow=(255, 0, 0, 150),
    ),
    "ghost_transparent": CardColors(
        bg_top=(100, 100, 110),
        bg_bottom=(60, 60, 70),
        accent=(200, 200, 210),
        text_primary=(240, 240, 245),
        text_secondary=(180, 180, 190),
        stat_bar_fill=(200, 200, 210),
        stat_bar_bg=(50, 50, 60),
        glow=(255, 255, 255, 80),
    ),
    "toty": CardColors(
        bg_top=(0, 40, 80),
        bg_bottom=(0, 20, 40),
        accent=(0, 191, 255),
        text_primary=(220, 240, 255),
        text_secondary=(150, 190, 220),
        stat_bar_fill=(0, 191, 255),
        stat_bar_bg=(20, 30, 50),
        glow=(0, 191, 255, 180),
    ),
    "tots": CardColors(
        bg_top=(0, 80, 60),
        bg_bottom=(0, 40, 30),
        accent=(0, 255, 127),
        text_primary=(220, 255, 240),
        text_secondary=(150, 220, 180),
        stat_bar_fill=(0, 255, 127),
        stat_bar_bg=(20, 50, 40),
        glow=(0, 255, 127, 160),
    ),
}

def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def _create_gradient(width: int, height: int, color1: Tuple[int, int, int], 
                     color2: Tuple[int, int, int], direction: str = "vertical") -> Image.Image:
    """Create a gradient image."""
    base = Image.new('RGB', (width, height), color1)
    draw = ImageDraw.Draw(base)

    if direction == "vertical":
        for y in range(height):
            ratio = y / height
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
    else:
        for x in range(width):
            ratio = x / width
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            draw.line([(x, 0), (x, height)], fill=(r, g, b))

    return base

def _create_radial_gradient(width: int, height: int, center: Tuple[int, int],
                            color_inner: Tuple[int, int, int], 
                            color_outer: Tuple[int, int, int]) -> Image.Image:
    """Create a radial gradient."""
    base = Image.new('RGB', (width, height), color_outer)
    pixels = base.load()
    cx, cy = center
    max_dist = math.sqrt(max(cx, width - cx)**2 + max(cy, height - cy)**2)

    for y in range(height):
        for x in range(width):
            dist = math.sqrt((x - cx)**2 + (y - cy)**2)
            ratio = min(dist / max_dist, 1.0)
            r = int(color_inner[0] * (1 - ratio) + color_outer[0] * ratio)
            g = int(color_inner[1] * (1 - ratio) + color_outer[1] * ratio)
            b = int(color_inner[2] * (1 - ratio) + color_outer[2] * ratio)
            pixels[x, y] = (r, g, b)

    return base

def _add_glow(draw: ImageDraw.Draw, center: Tuple[int, int], radius: int, 
              color: Tuple[int, int, int, int], steps: int = 20):
    """Add a glow effect."""
    for i in range(steps, 0, -1):
        alpha = int(color[3] * (i / steps) * 0.3)
        r = radius + i * 3
        glow_color = (color[0], color[1], color[2], alpha)
        draw.ellipse([center[0] - r, center[1] - r, center[0] + r, center[1] + r], 
                     outline=glow_color, width=2)

def _add_light_streaks(img: Image.Image, color: Tuple[int, int, int], count: int = 5) -> Image.Image:
    """Add diagonal light streaks."""
    draw = ImageDraw.Draw(img, 'RGBA')
    w, h = img.size
    for _ in range(count):
        x1 = random.randint(0, w)
        y1 = random.randint(0, h // 2)
        x2 = x1 + random.randint(200, 600)
        y2 = y1 + random.randint(400, 800)
        alpha = random.randint(20, 60)
        streak_color = (*color, alpha)
        draw.line([(x1, y1), (x2, y2)], fill=streak_color, width=random.randint(2, 6))
    return img

def _add_noise(img: Image.Image, intensity: int = 5) -> Image.Image:
    """Add subtle noise for texture."""
    arr = np.array(img)
    noise = np.random.randint(-intensity, intensity + 1, arr.shape, dtype=np.int16)
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

def _create_stat_bar(width: int, height: int, fill_ratio: float, 
                     fill_color: Tuple[int, int, int], 
                     bg_color: Tuple[int, int, int]) -> Image.Image:
    """Create a rounded stat bar."""
    bar = Image.new('RGBA', (width, height), (*bg_color, 255))
    draw = ImageDraw.Draw(bar)

    # Rounded corners
    radius = height // 2
    fill_w = int(width * fill_ratio)

    if fill_w > 0:
        fill_img = Image.new('RGBA', (fill_w, height), (*fill_color, 255))
        fill_draw = ImageDraw.Draw(fill_img)
        fill_draw.rounded_rectangle([0, 0, fill_w, height], radius=radius, fill=(*fill_color, 255))
        bar.paste(fill_img, (0, 0), fill_img)

    # Border
    draw.rounded_rectangle([0, 0, width - 1, height - 1], radius=radius, 
                           outline=(255, 255, 255, 60), width=2)

    return bar

def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Get a font, with fallbacks."""
    font_names = []
    if bold:
        font_names = ["Arial Bold", "DejaVuSans-Bold", "LiberationSans-Bold", 
                      "NotoSans-Bold", "FreeSans-Bold", "Arial"]
    else:
        font_names = ["Arial", "DejaVuSans", "LiberationSans", 
                      "NotoSans", "FreeSans"]

    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except:
            continue

    return ImageFont.load_default()

def _load_player_photo(photo_path: Optional[Path], target_size: Tuple[int, int]) -> Optional[Image.Image]:
    """Load and process player photo."""
    if not photo_path or not photo_path.exists():
        return None

    try:
        img = Image.open(photo_path).convert("RGBA")
        img = img.resize(target_size, Image.Resampling.LANCZOS)
        return img
    except Exception as e:
        print(f"[CardGen] Error loading photo {photo_path}: {e}")
        return None

def _create_card_mask(width: int, height: int, corner_radius: int = 40) -> Image.Image:
    """Create a rounded rectangle mask."""
    mask = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, width - 1, height - 1], radius=corner_radius, fill=255)
    return mask

def _create_eafc_card_shape(width: int, height: int) -> Image.Image:
    """Create EA FC style card shape mask."""
    mask = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(mask)

    # Main rounded rectangle
    cr = 60
    draw.rounded_rectangle([0, 0, width - 1, height - 1], radius=cr, fill=255)

    # Top notch for rating
    notch_w = 200
    notch_h = 120
    nx = 40
    ny = 40
    draw.polygon([
        (nx, ny), (nx + notch_w, ny), (nx + notch_w - 30, ny + notch_h), (nx + 30, ny + notch_h)
    ], fill=255)

    return mask

def _add_metal_texture(img: Image.Image, colors: CardColors) -> Image.Image:
    """Add metallic texture overlay."""
    w, h = img.size
    # Diagonal lines
    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    accent = colors.accent
    for i in range(0, w + h, 20):
        alpha = random.randint(5, 20)
        draw.line([(i, 0), (0, i)], fill=(*accent, alpha), width=1)

    img = Image.alpha_composite(img.convert('RGBA'), overlay)
    return img

def _add_vignette(img: Image.Image, intensity: float = 0.3) -> Image.Image:
    """Add vignette effect."""
    w, h = img.size
    vignette = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(vignette)

    cx, cy = w // 2, h // 2
    max_dist = math.sqrt(cx**2 + cy**2)

    for r in range(0, int(max_dist), 5):
        alpha = int(255 * intensity * (r / max_dist))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(0, 0, 0, alpha), width=5)

    return Image.alpha_composite(img.convert('RGBA'), vignette)

def _add_aura_glow(img: Image.Image, center: Tuple[int, int], radius: int,
                   color: Tuple[int, int, int, int], intensity: float = 1.0) -> Image.Image:
    """Add anime-style aura glow behind player."""
    w, h = img.size
    glow = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)

    # Multiple layers of glow
    for i in range(15, 0, -1):
        alpha = int(color[3] * (i / 15) * 0.15 * intensity)
        r = radius + i * 8
        glow_color = (color[0], color[1], color[2], alpha)
        draw.ellipse([center[0] - r, center[1] - r, center[0] + r, center[1] + r], 
                     fill=glow_color)

    # Composite glow behind
    base = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    base = Image.alpha_composite(base, glow)
    base = Image.alpha_composite(base, img.convert('RGBA'))

    return base

def _add_energy_lines(img: Image.Image, color: Tuple[int, int, int], count: int = 20) -> Image.Image:
    """Add anime energy lines radiating from center."""
    w, h = img.size
    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    cx, cy = w // 2, h // 3

    for _ in range(count):
        angle = random.uniform(0, 2 * math.pi)
        length = random.randint(100, 400)
        x1 = cx + math.cos(angle) * 150
        y1 = cy + math.sin(angle) * 150
        x2 = cx + math.cos(angle) * (150 + length)
        y2 = cy + math.sin(angle) * (150 + length)
        alpha = random.randint(30, 100)
        draw.line([(x1, y1), (x2, y2)], fill=(*color, alpha), width=random.randint(2, 4))

    return Image.alpha_composite(img.convert('RGBA'), overlay)

class CardGenerator:
    """Generates premium UHD player cards."""

    def __init__(self):
        self.aura = get_aura_system()
        self.mapper = get_mapper()
        self.card_w = CARD_W
        self.card_h = CARD_H

    def _get_scheme(self, aura_tier: AuraTier) -> CardColors:
        """Get color scheme for aura tier."""
        config = AURA_CONFIGS.get(aura_tier)
        if not config:
            return CARD_SCHEMES["gold_metal"]
        return CARD_SCHEMES.get(config.card_bg, CARD_SCHEMES["gold_metal"])

    def _create_base_card(self, colors: CardColors) -> Image.Image:
        """Create the base card background."""
        # Main gradient background
        bg = _create_gradient(self.card_w, self.card_h, colors.bg_top, colors.bg_bottom)

        # Add radial glow from center
        glow = _create_radial_gradient(self.card_w, self.card_h, 
                                       (self.card_w // 2, self.card_h // 3),
                                       colors.accent, colors.bg_top)
        bg = Image.blend(bg, glow, 0.3)

        # Add light streaks
        bg = _add_light_streaks(bg, colors.accent, count=8)

        # Add noise texture
        bg = _add_noise(bg, intensity=3)

        return bg

    def _draw_card_frame(self, draw: ImageDraw.Draw, colors: CardColors):
        """Draw the card frame/border."""
        # Outer border
        draw.rounded_rectangle([20, 20, self.card_w - 20, self.card_h - 20], 
                               radius=50, outline=(*colors.accent, 200), width=4)

        # Inner border
        draw.rounded_rectangle([40, 40, self.card_w - 40, self.card_h - 40], 
                               radius=40, outline=(255, 255, 255, 80), width=2)

    def _draw_rating_section(self, draw: ImageDraw.Draw, colors: CardColors,
                             overall: int, position: str, aura_tier: AuraTier):
        """Draw the top-left rating section."""
        # Rating background
        rating_bg_x = 80
        rating_bg_y = 80
        rating_bg_w = 220
        rating_bg_h = 280

        draw.rounded_rectangle([rating_bg_x, rating_bg_y, 
                                rating_bg_x + rating_bg_w, rating_bg_y + rating_bg_h],
                               radius=20, fill=(20, 20, 20, 200))

        # Overall number
        font_big = _get_font(140, bold=True)
        draw.text((rating_bg_x + rating_bg_w // 2, rating_bg_y + 60), 
                  str(overall), fill=colors.accent, font=font_big, anchor="mm")

        # Position
        font_pos = _get_font(50, bold=True)
        draw.text((rating_bg_x + rating_bg_w // 2, rating_bg_y + 180), 
                  position, fill=colors.text_primary, font=font_pos, anchor="mm")

        # Aura tier badge
        font_aura = _get_font(36, bold=True)
        aura_text = aura_tier.value
        draw.text((rating_bg_x + rating_bg_w // 2, rating_bg_y + 240), 
                  aura_text, fill=colors.accent, font=font_aura, anchor="mm")

    def _draw_player_name(self, draw: ImageDraw.Draw, colors: CardColors,
                          nickname: str, ea_name: str):
        """Draw player name in center-top."""
        # Main nickname
        font_name = _get_font(90, bold=True)
        draw.text((self.card_w // 2, 420), nickname, 
                  fill=colors.text_primary, font=font_name, anchor="mm")

        # EA name below (smaller)
        font_ea = _get_font(40, bold=False)
        draw.text((self.card_w // 2, 500), ea_name, 
                  fill=colors.text_secondary, font=font_ea, anchor="mm")

    def _draw_player_photo(self, card: Image.Image, colors: CardColors,
                           photo_path: Optional[Path], aura_tier: AuraTier):
        """Draw player photo with aura effects."""
        photo_area = (360, 560, 1080, 1360)  # x1, y1, x2, y2
        photo_w = photo_area[2] - photo_area[0]
        photo_h = photo_area[3] - photo_area[1]
        center = (self.card_w // 2, (photo_area[1] + photo_area[3]) // 2)

        # Add aura glow behind photo
        aura_config = AURA_CONFIGS.get(aura_tier)
        if aura_config:
            glow_color = aura_config.glow_color
            card = _add_aura_glow(card, center, 250, glow_color, intensity=1.2)

        # Add energy lines for S-tier and Carry
        if aura_tier in (AuraTier.S_TIER, AuraTier.CARRY):
            card = _add_energy_lines(card, colors.accent, count=30)

        # Load and place photo
        photo = _load_player_photo(photo_path, (photo_w, photo_h))
        if photo:
            # Create circular mask for photo
            mask = Image.new('L', (photo_w, photo_h), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([0, 0, photo_w - 1, photo_h - 1], 
                                        radius=30, fill=255)

            # Add border to photo
            bordered = Image.new('RGBA', (photo_w + 8, photo_h + 8), (*colors.accent, 255))
            bordered.paste(photo, (4, 4), photo)

            # Apply mask
            final_mask = Image.new('L', (photo_w + 8, photo_h + 8), 0)
            final_draw = ImageDraw.Draw(final_mask)
            final_draw.rounded_rectangle([0, 0, photo_w + 7, photo_h + 7], 
                                       radius=34, fill=255)

            card.paste(bordered, (photo_area[0] - 4, photo_area[1] - 4), final_mask)
        else:
            # Placeholder with initials
            draw = ImageDraw.Draw(card)
            draw.rounded_rectangle([photo_area[0], photo_area[1], 
                                    photo_area[2], photo_area[3]],
                                   radius=30, fill=(30, 30, 30, 200),
                                   outline=colors.accent, width=4)
            font_init = _get_font(120, bold=True)
            initials = "".join([n[0] for n in nickname.split()[:2]]) if 'nickname' in locals() else "??"
            draw.text((self.card_w // 2, (photo_area[1] + photo_area[3]) // 2),
                      initials, fill=colors.text_secondary, font=font_init, anchor="mm")

        return card

    def _draw_stats(self, card: Image.Image, colors: CardColors, stats: Dict):
        """Draw statistics at bottom of card."""
        draw = ImageDraw.Draw(card)

        # Stats area
        stats_y_start = 1480
        stats_h = 580
        margin_x = 80

        # Background for stats
        draw.rounded_rectangle([margin_x, stats_y_start, 
                              self.card_w - margin_x, stats_y_start + stats_h],
                             radius=30, fill=(10, 10, 10, 180))

        # Define stats to display
        stat_defs = [
            ("GOALS", stats.get("goals", 0), 100),
            ("ASSISTS", stats.get("assists", 0), 100),
            ("RATING", stats.get("rating", 7.0), 10),
            ("PASS %", stats.get("pass_accuracy", 0), 100),
            ("MOTM", stats.get("motm", 0), 50),
            ("TACKLES", stats.get("tackles", 0), 100),
            ("INTERCEPT", stats.get("interceptions", 0), 100),
            ("POSS LOST", stats.get("possession_lost", 0), 100),
            ("WIN RATE", stats.get("win_rate", 0), 100),
            ("IMPACT", stats.get("impact", 5.0), 10),
            ("FRAUD", stats.get("fraud_score", 0), 100),
        ]

        # Layout: 2 columns
        col_w = (self.card_w - 2 * margin_x - 60) // 2
        row_h = 90
        cols = 2

        font_label = _get_font(32, bold=True)
        font_value = _get_font(36, bold=True)

        for idx, (label, value, max_val) in enumerate(stat_defs):
            col = idx % cols
            row = idx // cols

            x = margin_x + 30 + col * (col_w + 30)
            y = stats_y_start + 30 + row * row_h

            # Label
            draw.text((x, y), label, fill=colors.text_secondary, font=font_label, anchor="lm")

            # Value
            val_x = x + 180
            draw.text((val_x, y), str(value), fill=colors.text_primary, font=font_value, anchor="lm")

            # Bar
            bar_x = val_x + 80
            bar_w = col_w - 280
            bar_h = 24

            ratio = min(float(value) / max_val, 1.0) if max_val > 0 else 0
            bar = _create_stat_bar(bar_w, bar_h, ratio, colors.stat_bar_fill, colors.stat_bar_bg)
            card.paste(bar, (bar_x, y - bar_h // 2), bar)

        return card

    def _draw_club_logo_area(self, draw: ImageDraw.Draw, colors: CardColors,
                             club_name: str = "PRO CLUBS"):
        """Draw club logo/name area."""
        # Top right area
        x = self.card_w - 280
        y = 100

        draw.rounded_rectangle([x, y, x + 200, y + 80], 
                               radius=15, fill=(20, 20, 20, 200),
                               outline=colors.accent, width=2)

        font_club = _get_font(28, bold=True)
        draw.text((x + 100, y + 40), club_name, 
                  fill=colors.text_primary, font=font_club, anchor="mm")

    def _draw_footer(self, draw: ImageDraw.Draw, colors: CardColors,
                     footer_text: str = "PRO CLUBS TRACKER • ANIME EDITION"):
        """Draw footer text."""
        font_footer = _get_font(28, bold=False)
        draw.text((self.card_w // 2, self.card_h - 50), footer_text,
                  fill=colors.text_secondary, font=font_footer, anchor="mm")

    def generate_player_card(self, ea_name: str, stats: Dict, 
                             card_type: str = "standard") -> Image.Image:
        """Generate a complete player card."""
        nickname = self.mapper.get_nickname(ea_name)
        position = self.mapper.get_position(ea_name)
        photo_path = self.mapper.get_photo_path(ea_name)

        # Determine aura
        aura_tier = self.aura.determine_tier(stats)
        overall = int(self.aura.calculate_overall(stats))

        # Get colors
        colors = self._get_scheme(aura_tier)

        # Create base
        card = self._create_base_card(colors).convert('RGBA')

        # Draw frame
        draw = ImageDraw.Draw(card)
        self._draw_card_frame(draw, colors)

        # Rating section
        self._draw_rating_section(draw, colors, overall, position, aura_tier)

        # Club logo
        self._draw_club_logo_area(draw, colors)

        # Player name
        self._draw_player_name(draw, colors, nickname, ea_name)

        # Player photo with aura
        card = self._draw_player_photo(card, colors, photo_path, aura_tier)

        # Stats
        card = self._draw_stats(card, colors, stats)

        # Footer
        draw = ImageDraw.Draw(card)
        self._draw_footer(draw, colors, 
                         f"{nickname.upper()} • {aura_tier.value.upper()} AURA • PRO CLUBS")

        # Add vignette
        card = _add_vignette(card, intensity=0.2)

        return card.convert('RGB')

    def generate_mvp_card(self, ea_name: str, stats: Dict) -> Image.Image:
        """Generate MVP card with special effects."""
        # Force S-tier aura for MVP
        stats_copy = dict(stats)
        stats_copy["impact"] = max(stats_copy.get("impact", 5), 9.0)

        card = self.generate_player_card(ea_name, stats_copy, "mvp")

        # Add extra glow
        colors = CARD_SCHEMES["purple_blue_energy"]
        card = _add_aura_glow(card.convert('RGBA'), 
                             (self.card_w // 2, self.card_h // 2), 
                             400, colors.glow, intensity=0.5)

        return card.convert('RGB')

    def generate_fraud_card(self, ea_name: str, stats: Dict) -> Image.Image:
        """Generate fraud card with clown effects."""
        card = self.generate_player_card(ea_name, stats, "fraud")

        # Add red vignette
        w, h = card.size
        vignette = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(vignette)
        for r in range(0, max(w, h), 10):
            alpha = int(100 * (r / max(w, h)))
            draw.ellipse([w//2 - r, h//2 - r, w//2 + r, h//2 + r], 
                        outline=(255, 0, 0, alpha), width=5)

        card = Image.alpha_composite(card.convert('RGBA'), vignette)
        return card.convert('RGB')

    def generate_ghost_card(self, ea_name: str, stats: Dict) -> Image.Image:
        """Generate ghost card with transparent effects."""
        card = self.generate_player_card(ea_name, stats, "ghost")

        # Desaturate and add transparency effect
        card = card.convert('RGBA')
        enhancer = ImageEnhance.Brightness(card)
        card = enhancer.enhance(0.7)

        return card.convert('RGB')

    def generate_carry_card(self, ea_name: str, stats: Dict) -> Image.Image:
        """Generate carry card with Blue Lock style."""
        # Force carry aura
        stats_copy = dict(stats)
        stats_copy["impact"] = max(stats_copy.get("impact", 5), 8.5)

        card = self.generate_player_card(ea_name, stats_copy, "carry")

        # Add crown/king effect
        colors = CARD_SCHEMES["blue_lock_king"]
        card = _add_energy_lines(card.convert('RGBA'), colors.accent, count=40)
        card = _add_aura_glow(card, (self.card_w // 2, self.card_h // 3), 
                             350, colors.glow, intensity=1.5)

        return card.convert('RGB')

    def save_card(self, card: Image.Image, path: Path, quality: int = 95):
        """Save card with high quality."""
        card.save(path, "PNG", quality=quality)
        return path

# Global instance
_generator = None

def get_card_generator() -> CardGenerator:
    global _generator
    if _generator is None:
        _generator = CardGenerator()
    return _generator
