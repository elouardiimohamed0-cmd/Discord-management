"""
Rachad L3ERGONI — Anime-Style Image Generator
- Anime/manga aesthetic for stats cards, MOTM, TOTW, comparisons
- Clean lines, bold typography, high contrast
- Power bars like anime games
- Manga speed lines, halftone dots
- Uses real player data (no imagined faces)
"""
import io
import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# ─── COLORS — Anime Palette ─────────────────────────────────────────────────

ANIME_COLORS = {
    "bg_dark": "#0a0a1a",
    "bg_mid": "#12122b",
    "bg_light": "#1a1a3e",
    "accent_red": "#ff2a6d",
    "accent_cyan": "#05d9e8",
    "accent_yellow": "#ffd700",
    "accent_green": "#00ff88",
    "accent_purple": "#b026ff",
    "accent_orange": "#ff6b35",
    "text_white": "#ffffff",
    "text_gray": "#a0a0c0",
    "text_gold": "#ffd700",
    "panel_bg": "#0f0f2a",
    "panel_border": "#ff2a6d",
    "speed_line": "#1a1a4e",
    "halftone": "#151530",
}

# Stat bar colors (anime power bar style)
STAT_COLORS = {
    "goals": "#ff2a6d",      # Red — attack
    "assists": "#ffd700",    # Gold — support
    "passes": "#05d9e8",     # Cyan — control
    "defense": "#b026ff",    # Purple — defense
    "speed": "#00ff88",      # Green — speed
    "rating": "#ff6b35",     # Orange — overall
    "tackles": "#b026ff",
    "interceptions": "#05d9e8",
    "shots": "#ff2a6d",
    "saves": "#ffd700",
}

# Position colors
POS_COLORS = {
    "GK": "#ffd700",   # Gold
    "DEF": "#b026ff",  # Purple
    "MID": "#05d9e8",  # Cyan
    "ST": "#ff2a6d",   # Red
    "FW": "#ff2a6d",
    "CAM": "#ff6b35",
    "CDM": "#00ff88",
    "LW": "#ff2a6d",
    "RW": "#ff2a6d",
    "LB": "#b026ff",
    "RB": "#b026ff",
    "CB": "#b026ff",
    "LM": "#05d9e8",
    "RM": "#05d9e8",
    "CM": "#05d9e8",
}


def _get_font(size, bold=False):
    """Get best available font for anime style."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    return ImageFont.load_default()


def _hex_to_rgb(hex_color):
    """Convert hex to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _draw_speed_lines(draw, width, height, color, density=40):
    """Draw manga speed lines background."""
    rgb = _hex_to_rgb(color)
    for i in range(0, width + height, density):
        # Diagonal lines from top-left
        draw.line([(i, 0), (i + 20, height)], fill=rgb, width=1)
        # Diagonal from top-right
        draw.line([(width - i, 0), (width - i - 20, height)], fill=rgb, width=1)


def _draw_halftone(draw, width, height, color, dot_size=4, spacing=12):
    """Draw halftone dot pattern."""
    rgb = _hex_to_rgb(color)
    for y in range(0, height, spacing):
        for x in range(0, width, spacing):
            # Offset every other row
            ox = x + (spacing // 2) if (y // spacing) % 2 == 1 else x
            draw.ellipse([ox, y, ox + dot_size, y + dot_size], fill=rgb)


def _draw_glow_bar(draw, x, y, width, height, fill_percent, color, bg_color="#16213e"):
    """Draw anime-style glowing power bar."""
    rgb = _hex_to_rgb(color)
    bg_rgb = _hex_to_rgb(bg_color)

    # Background bar with rounded corners
    draw.rounded_rectangle([x, y, x + width, y + height], radius=height//2, fill=bg_rgb, outline=rgb, width=2)

    # Fill bar
    fill_width = int(width * fill_percent)
    if fill_width > 0:
        # Inner glow effect
        draw.rounded_rectangle([x + 2, y + 2, x + fill_width - 2, y + height - 2], radius=(height-4)//2, fill=rgb)
        # Bright center line
        center_y = y + height // 2
        draw.line([(x + 4, center_y), (x + fill_width - 4, center_y)], fill=(255, 255, 255), width=2)


def _draw_anime_header(draw, width, y_start, text, subtitle="", accent_color="#ff2a6d"):
    """Draw anime-style header bar with text."""
    rgb_accent = _hex_to_rgb(accent_color)
    header_height = 100

    # Header bar
    draw.rectangle([0, y_start, width, y_start + header_height], fill=rgb_accent)

    # Title
    font_title = _get_font(48, bold=True)
    font_sub = _get_font(24)

    draw.text((40, y_start + 20), text.upper(), fill=(255, 255, 255), font=font_title)
    if subtitle:
        draw.text((40, y_start + 65), subtitle, fill=(255, 255, 255), font=font_sub)

    return y_start + header_height


def _draw_stat_row(draw, y, label, value, max_val, bar_width, color, x_label=50, x_bar=250):
    """Draw a single stat row with label, bar, and value."""
    font_label = _get_font(22)
    font_value = _get_font(24, bold=True)

    # Label
    draw.text((x_label, y), label.upper(), fill=_hex_to_rgb(ANIME_COLORS["text_white"]), font=font_label)

    # Bar
    bar_height = 32
    fill_percent = min(value / max_val, 1.0) if max_val > 0 else 0
    _draw_glow_bar(draw, x_bar, y, bar_width, bar_height, fill_percent, color)

    # Value text
    draw.text((x_bar + bar_width + 20, y), str(value), fill=_hex_to_rgb(ANIME_COLORS["text_white"]), font=font_value)

    return y + 50


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC CARD GENERATORS
# ═══════════════════════════════════════════════════════════════════════════════

def make_motm_card(player_name, rating, goals, assists, match_info, player_image_path=None):
    """Create anime-style MOTM card."""
    width, height = 800, 1000
    img = Image.new("RGB", (width, height), _hex_to_rgb(ANIME_COLORS["bg_dark"]))
    draw = ImageDraw.Draw(img)

    # Background: speed lines + halftone
    _draw_speed_lines(draw, width, height, ANIME_COLORS["speed_line"], density=50)
    _draw_halftone(draw, width, height, ANIME_COLORS["halftone"], dot_size=3, spacing=16)

    # Header
    y = _draw_anime_header(draw, width, 0, "MOTM", f"Rachad L3ERGONI — {match_info}", "#ff2a6d")

    # Player section
    y += 40

    # Player image or placeholder
    img_x, img_y = 250, y
    img_size = 300
    if player_image_path and os.path.exists(player_image_path):
        try:
            pimg = Image.open(player_image_path).convert("RGBA")
            pimg = pimg.resize((img_size, img_size))
            # Create circular mask
            mask = Image.new("L", (img_size, img_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse([0, 0, img_size, img_size], fill=255)
            pimg = pimg.convert("RGBA")
            # Paste with mask
            img.paste(pimg, (img_x, img_y), mask)
            # Border circle
            draw.ellipse([img_x - 5, img_y - 5, img_x + img_size + 5, img_y + img_size + 5],
                        outline=_hex_to_rgb(ANIME_COLORS["accent_red"]), width=4)
        except Exception as e:
            # Fallback to placeholder
            draw.rectangle([img_x, img_y, img_x + img_size, img_y + img_size],
                          fill=_hex_to_rgb(ANIME_COLORS["panel_bg"]),
                          outline=_hex_to_rgb(ANIME_COLORS["accent_red"]), width=3)
            draw.text((img_x + 80, img_y + 130), "NO IMAGE", fill=_hex_to_rgb(ANIME_COLORS["text_gray"]), font=_get_font(24))
    else:
        # Placeholder with anime silhouette style
        draw.rectangle([img_x, img_y, img_x + img_size, img_y + img_size],
                      fill=_hex_to_rgb(ANIME_COLORS["panel_bg"]),
                      outline=_hex_to_rgb(ANIME_COLORS["accent_red"]), width=3)
        # Silhouette icon (simple circle + triangle)
        cx, cy = img_x + img_size // 2, img_y + img_size // 2
        draw.ellipse([cx - 40, cy - 60, cx + 40, cy + 20], fill=_hex_to_rgb(ANIME_COLORS["accent_red"]))
        draw.polygon([(cx, cy - 80), (cx - 50, cy + 20), (cx + 50, cy + 20)], fill=_hex_to_rgb(ANIME_COLORS["accent_red"]))
        draw.text((img_x + 60, img_y + img_size + 10), "PLAYER", fill=_hex_to_rgb(ANIME_COLORS["text_gray"]), font=_get_font(20))

    y += img_size + 60

    # Player name (big)
    font_name = _get_font(52, bold=True)
    draw.text((40, y), player_name.upper(), fill=_hex_to_rgb(ANIME_COLORS["text_white"]), font=font_name)
    y += 70

    # Rating badge (anime style)
    badge_size = 80
    badge_x = width - badge_size - 40
    draw.rounded_rectangle([badge_x, y - 10, badge_x + badge_size, y - 10 + badge_size],
                          radius=10, fill=_hex_to_rgb(ANIME_COLORS["accent_yellow"]))
    font_rating = _get_font(42, bold=True)
    rating_text = f"{rating:.1f}"
    # Center text in badge
    bbox = draw.textbbox((0, 0), rating_text, font=font_rating)
    text_w = bbox[2] - bbox[0]
    text_x = badge_x + (badge_size - text_w) // 2
    draw.text((text_x, y), rating_text, fill=_hex_to_rgb(ANIME_COLORS["bg_dark"]), font=font_rating)

    # Stats
    y += 30
    stats = [
        ("GOALS", goals, 10, STAT_COLORS["goals"]),
        ("ASSISTS", assists, 10, STAT_COLORS["assists"]),
        ("RATING", int(rating * 10), 100, STAT_COLORS["rating"]),
    ]
    bar_width = 400
    for label, val, max_val, color in stats:
        y = _draw_stat_row(draw, y, label, val, max_val, bar_width, color)

    # Quote box
    y += 30
    box_height = 120
    draw.rounded_rectangle([40, y, width - 40, y + box_height], radius=15,
                          fill=_hex_to_rgb(ANIME_COLORS["panel_bg"]),
                          outline=_hex_to_rgb(ANIME_COLORS["accent_yellow"]), width=2)

    quotes = [
        "B7al chi taxi khawi.",
        "C'est pas sérieux.",
        "Dima dima!",
        "WALLAH l3eb!",
        "Clean!",
        "Next level!",
    ]
    quote = random.choice(quotes)
    font_quote = _get_font(24)
    draw.text((60, y + 40), f'"{quote}"', fill=_hex_to_rgb(ANIME_COLORS["accent_yellow"]), font=font_quote)
    draw.text((60, y + 80), "— L3ERGONI Bot", fill=_hex_to_rgb(ANIME_COLORS["text_gray"]), font=_get_font(18))

    # Save to buffer
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def make_comparison_card(player1_stats, player2_stats):
    """Create anime-style 1v1 comparison card."""
    width, height = 900, 700
    img = Image.new("RGB", (width, height), _hex_to_rgb(ANIME_COLORS["bg_dark"]))
    draw = ImageDraw.Draw(img)

    # Background
    _draw_speed_lines(draw, width, height, ANIME_COLORS["speed_line"], density=60)

    # Header
    y = _draw_anime_header(draw, width, 0, "VS", "Rachad L3ERGONI — Head to Head", "#ff2a6d")
    y += 30

    # Player names
    p1_name = player1_stats.get("name", "Player 1")
    p2_name = player2_stats.get("name", "Player 2")

    font_name = _get_font(36, bold=True)
    draw.text((50, y), p1_name.upper(), fill=_hex_to_rgb(ANIME_COLORS["accent_cyan"]), font=font_name)
    draw.text((width - 50 - 200, y), p2_name.upper(), fill=_hex_to_rgb(ANIME_COLORS["accent_red"]), font=font_name)

    # VS badge
    vs_x = width // 2 - 40
    draw.rounded_rectangle([vs_x, y, vs_x + 80, y + 50], radius=10, fill=_hex_to_rgb(ANIME_COLORS["accent_yellow"]))
    font_vs = _get_font(28, bold=True)
    draw.text((vs_x + 15, y + 8), "VS", fill=_hex_to_rgb(ANIME_COLORS["bg_dark"]), font=font_vs)

    y += 80

    # Stats comparison
    stats_to_compare = [
        ("GOALS", "goals"),
        ("ASSISTS", "assists"),
        ("RATING", "rating"),
        ("SHOTS", "shots"),
        ("TACKLES", "tackles"),
    ]

    bar_width = 300
    for label, key in stats_to_compare:
        v1 = player1_stats.get(key, 0)
        v2 = player2_stats.get(key, 0)
        max_val = max(v1, v2, 1)

        # Left bar (Player 1)
        fill1 = v1 / max_val
        _draw_glow_bar(draw, 50, y, bar_width, 30, fill1, ANIME_COLORS["accent_cyan"])
        draw.text((50, y - 22), label, fill=_hex_to_rgb(ANIME_COLORS["text_gray"]), font=_get_font(16))
        draw.text((50 + bar_width + 10, y), str(v1), fill=_hex_to_rgb(ANIME_COLORS["text_white"]), font=_get_font(20, bold=True))

        # Right bar (Player 2)
        fill2 = v2 / max_val
        _draw_glow_bar(draw, width - 50 - bar_width, y, bar_width, 30, fill2, ANIME_COLORS["accent_red"])
        draw.text((width - 50 - bar_width - 50, y), str(v2), fill=_hex_to_rgb(ANIME_COLORS["text_white"]), font=_get_font(20, bold=True))

        y += 60

    # Winner indicator
    y += 20
    p1_score = sum(player1_stats.get(k, 0) for _, k in stats_to_compare)
    p2_score = sum(player2_stats.get(k, 0) for _, k in stats_to_compare)
    winner = p1_name if p1_score > p2_score else p2_name if p2_score > p1_score else "TIE"

    font_winner = _get_font(32, bold=True)
    if winner == "TIE":
        draw.text((width // 2 - 80, y), "NOSS NOSS", fill=_hex_to_rgb(ANIME_COLORS["accent_yellow"]), font=font_winner)
    else:
        winner_color = ANIME_COLORS["accent_cyan"] if winner == p1_name else ANIME_COLORS["accent_red"]
        draw.text((width // 2 - 100, y), f"{winner.upper()} WINS!", fill=_hex_to_rgb(winner_color), font=font_winner)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def make_totw_card(players_list):
    """Create anime-style Team of the Week card."""
    width, height = 900, 1200
    img = Image.new("RGB", (width, height), _hex_to_rgb(ANIME_COLORS["bg_dark"]))
    draw = ImageDraw.Draw(img)

    # Background
    _draw_speed_lines(draw, width, height, ANIME_COLORS["speed_line"], density=50)
    _draw_halftone(draw, width, height, ANIME_COLORS["halftone"], dot_size=3, spacing=14)

    # Header
    y = _draw_anime_header(draw, width, 0, "TOTW", "Team of the Week — Rachad L3ERGONI", "#ffd700")
    y += 40

    # Players list
    font_name = _get_font(26, bold=True)
    font_stats = _get_font(20)
    font_pos = _get_font(18)

    for i, player in enumerate(players_list[:11]):  # Max 11
        pos = player.get("position", "MID").upper()[:3]
        name = player.get("name", "Unknown")
        rating = player.get("rating", 0)
        goals = player.get("goals", 0)
        assists = player.get("assists", 0)

        pos_color = POS_COLORS.get(pos, ANIME_COLORS["accent_cyan"])

        # Row background
        row_height = 70
        row_color = ANIME_COLORS["panel_bg"] if i % 2 == 0 else ANIME_COLORS["bg_mid"]
        draw.rectangle([30, y, width - 30, y + row_height], fill=_hex_to_rgb(row_color))

        # Position badge
        badge_size = 40
        draw.rounded_rectangle([40, y + 15, 40 + badge_size, y + 15 + badge_size], radius=8, fill=_hex_to_rgb(pos_color))
        draw.text((45, y + 20), pos, fill=_hex_to_rgb(ANIME_COLORS["bg_dark"]), font=font_pos)

        # Name
        draw.text((100, y + 20), name.upper(), fill=_hex_to_rgb(ANIME_COLORS["text_white"]), font=font_name)

        # Stats
        stats_text = f"⭐{rating:.1f} | {goals}G {assists}A"
        draw.text((width - 250, y + 22), stats_text, fill=_hex_to_rgb(ANIME_COLORS["text_gray"]), font=font_stats)

        # Rating bar (mini)
        bar_width = 120
        bar_height = 8
        fill_pct = min(rating / 10, 1.0)
        bar_x = width - 130
        bar_y = y + 30
        draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], radius=4,
                              fill=_hex_to_rgb(ANIME_COLORS["bg_light"]))
        if fill_pct > 0:
            fill_width = int(bar_width * fill_pct)
            draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_width, bar_y + bar_height], radius=4,
                                  fill=_hex_to_rgb(STAT_COLORS["rating"]))

        y += row_height + 5

    # Footer
    y += 20
    draw.text((width // 2 - 150, y), "— L3ERGONI Bot —", fill=_hex_to_rgb(ANIME_COLORS["text_gray"]), font=_get_font(18))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def make_five_match_summary(results_data):
    """Create anime-style 5-match summary card."""
    width, height = 800, 900
    img = Image.new("RGB", (width, height), _hex_to_rgb(ANIME_COLORS["bg_dark"]))
    draw = ImageDraw.Draw(img)

    # Background
    _draw_speed_lines(draw, width, height, ANIME_COLORS["speed_line"], density=55)

    # Header
    y = _draw_anime_header(draw, width, 0, "LAST 5", "Rachad L3ERGONI — Match Recap", "#05d9e8")
    y += 40

    # Results
    font_result = _get_font(28, bold=True)
    font_opp = _get_font(22)
    font_date = _get_font(18)

    result_colors = {"W": "#00ff88", "D": "#ffd700", "L": "#ff2a6d"}

    for i, match in enumerate(results_data[:5]):
        result = "W" if match["our_goals"] > match["opp_goals"] else "D" if match["our_goals"] == match["opp_goals"] else "L"
        color = result_colors.get(result, "#ffffff")

        row_height = 100
        row_bg = ANIME_COLORS["panel_bg"] if i % 2 == 0 else ANIME_COLORS["bg_mid"]
        draw.rectangle([30, y, width - 30, y + row_height], fill=_hex_to_rgb(row_bg))

        # Result badge
        badge_size = 50
        draw.rounded_rectangle([40, y + 25, 40 + badge_size, y + 25 + badge_size], radius=10, fill=_hex_to_rgb(color))
        font_badge = _get_font(24, bold=True)
        draw.text((50, y + 32), result, fill=_hex_to_rgb(ANIME_COLORS["bg_dark"]), font=font_badge)

        # Score
        score_text = f"{match['our_goals']}-{match['opp_goals']}"
        draw.text((110, y + 25), score_text, fill=_hex_to_rgb(ANIME_COLORS["text_white"]), font=font_result)

        # Opponent
        opp = match.get("opponent", "Unknown")
        draw.text((110, y + 60), f"vs {opp}", fill=_hex_to_rgb(ANIME_COLORS["text_gray"]), font=font_opp)

        # Date
        date = match.get("date", "")
        if date:
            draw.text((width - 200, y + 35), date, fill=_hex_to_rgb(ANIME_COLORS["text_gray"]), font=font_date)

        y += row_height + 10

    # Form string
    y += 20
    form = "".join(
        "W" if m["our_goals"] > m["opp_goals"] else "D" if m["our_goals"] == m["opp_goals"] else "L"
        for m in results_data[:5]
    )
    font_form = _get_font(32, bold=True)
    draw.text((40, y), f"FORM: {form}", fill=_hex_to_rgb(ANIME_COLORS["accent_yellow"]), font=font_form)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def make_player_stats_card(player_name, stats_dict, position="MID", player_image_path=None):
    """Create anime-style player stats card with all stats."""
    width, height = 800, 1100
    img = Image.new("RGB", (width, height), _hex_to_rgb(ANIME_COLORS["bg_dark"]))
    draw = ImageDraw.Draw(img)

    # Background
    _draw_speed_lines(draw, width, height, ANIME_COLORS["speed_line"], density=45)
    _draw_halftone(draw, width, height, ANIME_COLORS["halftone"], dot_size=3, spacing=16)

    # Header with position color
    pos_color = POS_COLORS.get(position.upper()[:3], ANIME_COLORS["accent_cyan"])
    y = _draw_anime_header(draw, width, 0, player_name.upper(), f"Rachad L3ERGONI — {position}", pos_color)
    y += 40

    # Player image area
    img_x, img_y = 250, y
    img_size = 280
    if player_image_path and os.path.exists(player_image_path):
        try:
            pimg = Image.open(player_image_path).convert("RGBA").resize((img_size, img_size))
            mask = Image.new("L", (img_size, img_size), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, img_size, img_size], fill=255)
            img.paste(pimg, (img_x, img_y), mask)
            draw.ellipse([img_x - 5, img_y - 5, img_x + img_size + 5, img_y + img_size + 5],
                        outline=_hex_to_rgb(pos_color), width=4)
        except:
            draw.rectangle([img_x, img_y, img_x + img_size, img_y + img_size],
                          fill=_hex_to_rgb(ANIME_COLORS["panel_bg"]), outline=_hex_to_rgb(pos_color), width=3)
    else:
        draw.rectangle([img_x, img_y, img_x + img_size, img_y + img_size],
                      fill=_hex_to_rgb(ANIME_COLORS["panel_bg"]), outline=_hex_to_rgb(pos_color), width=3)
        draw.text((img_x + 60, img_y + 120), "NO IMAGE", fill=_hex_to_rgb(ANIME_COLORS["text_gray"]), font=_get_font(24))

    y += img_size + 50

    # Stats
    bar_width = 450
    stat_items = [
        ("GOALS", stats_dict.get("goals", 0), 20, "goals"),
        ("ASSISTS", stats_dict.get("assists", 0), 15, "assists"),
        ("RATING", int(stats_dict.get("rating", 0) * 10), 100, "rating"),
        ("SHOTS", stats_dict.get("shots", 0), 30, "shots"),
        ("TACKLES", stats_dict.get("tackles", 0), 20, "tackles"),
        ("PASSES", stats_dict.get("passes_completed", 0), 100, "passes"),
    ]

    for label, val, max_val, color_key in stat_items:
        color = STAT_COLORS.get(color_key, ANIME_COLORS["accent_cyan"])
        y = _draw_stat_row(draw, y, label, val, max_val, bar_width, color)

    # Quote
    y += 30
    box_height = 100
    draw.rounded_rectangle([40, y, width - 40, y + box_height], radius=15,
                          fill=_hex_to_rgb(ANIME_COLORS["panel_bg"]),
                          outline=_hex_to_rgb(ANIME_COLORS["accent_yellow"]), width=2)

    quotes = [
        "B7al chi taxi khawi.",
        "C'est pas sérieux.",
        "Dima dima!",
        "WALLAH l3eb!",
        "Clean!",
        "Next level!",
    ]
    quote = random.choice(quotes)
    font_quote = _get_font(22)
    draw.text((60, y + 35), f'"{quote}"', fill=_hex_to_rgb(ANIME_COLORS["accent_yellow"]), font=font_quote)
    draw.text((60, y + 70), "— L3ERGONI Bot", fill=_hex_to_rgb(ANIME_COLORS["text_gray"]), font=_get_font(16))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
