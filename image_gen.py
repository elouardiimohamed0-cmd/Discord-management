"""
FIFA-style matchday graphic generator using Pillow.
Produces: match poster, MOTM card, 5-match summary, TOTW card.
"""
import io
import os
import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ─── Font Loader ─────────────────────────────────────────────────────────────

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
FONT_BOLD = os.path.join(ASSETS, "Oswald-Bold.ttf")
FONT_REG  = os.path.join(ASSETS, "Oswald-Regular.ttf")
DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
DEJAVU_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    paths = [FONT_BOLD if bold else FONT_REG, DEJAVU_BOLD if bold else DEJAVU_REG]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ─── Color Palette ────────────────────────────────────────────────────────────

BG_DARK   = (8, 8, 14)
BG_CARD   = (14, 16, 24)
BG_PANEL  = (20, 22, 34)
WHITE     = (255, 255, 255)
GRAY      = (140, 145, 165)
GREEN_NEON = (0, 255, 140)
RED_NEON   = (255, 60, 80)
YELLOW_NEON = (255, 210, 0)
BLUE_NEON   = (0, 180, 255)
GOLD       = (255, 185, 0)


def result_color(our: int, opp: int):
    if our > opp:
        return GREEN_NEON
    elif our < opp:
        return RED_NEON
    return YELLOW_NEON


def result_label(our: int, opp: int) -> str:
    if our > opp:
        return "VICTOIRE"
    elif our < opp:
        return "DÉFAITE"
    return "MATCH NUL"


# ─── Drawing Helpers ──────────────────────────────────────────────────────────

def _centered_text(draw: ImageDraw.ImageDraw, text: str, y: int, font, color, width: int):
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (width - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), text, font=font, fill=color)


def _glow_rect(img: Image.Image, x1, y1, x2, y2, color, radius=3):
    """Draw a glowing neon line."""
    draw = ImageDraw.Draw(img)
    for r in range(radius, 0, -1):
        alpha = int(80 / r)
        c = color + (alpha,)
        draw.rectangle([x1 - r, y1 - r, x2 + r, y2 + r], fill=c)
    draw.rectangle([x1, y1, x2, y2], fill=color)


def _draw_noise(draw: ImageDraw.ImageDraw, w: int, h: int, density: float = 0.006):
    """Subtle dark noise texture."""
    count = int(w * h * density)
    for _ in range(count):
        x = random.randint(0, w - 1)
        y = random.randint(0, h - 1)
        v = random.randint(30, 55)
        draw.point((x, y), fill=(v, v, v))


def _gradient_bg(w: int, h: int, top_color=(8, 8, 14), bot_color=(18, 20, 32)) -> Image.Image:
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(top_color[0] + (bot_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bot_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bot_color[2] - top_color[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def _draw_diagonal_stripes(img: Image.Image, color, alpha=12):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size
    for i in range(-h, w + h, 60):
        draw.line([(i, 0), (i + h, h)], fill=color + (alpha,), width=25)
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay)
    return img.convert("RGB")


# ─── Match Poster ─────────────────────────────────────────────────────────────

def make_match_poster(
    home_name: str,
    away_name: str,
    home_goals: int,
    away_goals: int,
    match_date: str = "",
    competition: str = "Pro Clubs · Division 6",
) -> io.BytesIO:
    W, H = 900, 500
    accent = result_color(home_goals, away_goals)

    img = _gradient_bg(W, H, (6, 6, 12), (20, 18, 36))
    img = _draw_diagonal_stripes(img, (255, 255, 255))
    draw = ImageDraw.Draw(img)
    _draw_noise(draw, W, H)

    # Top neon bar
    _glow_rect(img, 0, 0, W, 5, accent, radius=6)

    # Competition label
    comp_font = _font(18, bold=False)
    _centered_text(draw, competition.upper(), 22, comp_font, GRAY, W)

    # Team name fonts
    team_font = _font(52, bold=True)
    score_font = _font(110, bold=True)
    vs_font = _font(22, bold=False)
    result_font = _font(28, bold=True)
    date_font = _font(20, bold=False)

    # Left team (home)
    home_display = home_name.upper()
    if len(home_display) > 14:
        home_display = home_display[:13] + "."
    bbox = draw.textbbox((0, 0), home_display, font=team_font)
    home_w = bbox[2] - bbox[0]
    draw.text((W // 4 - home_w // 2, 140), home_display, font=team_font, fill=WHITE)

    # Right team (away)
    away_display = away_name.upper()
    if len(away_display) > 14:
        away_display = away_display[:13] + "."
    bbox = draw.textbbox((0, 0), away_display, font=team_font)
    away_w = bbox[2] - bbox[0]
    draw.text((3 * W // 4 - away_w // 2, 140), away_display, font=team_font, fill=WHITE)

    # Score
    score_str = f"{home_goals}  —  {away_goals}"
    bbox = draw.textbbox((0, 0), score_str, font=score_font)
    score_w = bbox[2] - bbox[0]
    score_x = (W - score_w) // 2
    # Shadow
    draw.text((score_x + 3, 193), score_str, font=score_font, fill=(0, 0, 0))
    draw.text((score_x, 190), score_str, font=score_font, fill=WHITE)

    # Glowing center divider
    _glow_rect(img, W // 2 - 1, 130, W // 2 + 1, 340, accent, radius=4)

    # Result banner
    res_label = result_label(home_goals, away_goals)
    banner_y = 340
    draw.rectangle([0, banner_y, W, banner_y + 55], fill=accent)
    bbox = draw.textbbox((0, 0), res_label, font=result_font)
    rx = (W - (bbox[2] - bbox[0])) // 2
    draw.text((rx, banner_y + 14), res_label, font=result_font, fill=BG_DARK)

    # Date
    if match_date:
        _centered_text(draw, match_date, 410, date_font, GRAY, W)

    # Footer
    footer_font = _font(16, bold=False)
    _centered_text(draw, "RACHAD L3ERGONI · FC 26 PRO CLUBS", H - 28, footer_font, GRAY, W)

    # Bottom neon bar
    _glow_rect(img, 0, H - 5, W, H, accent, radius=4)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ─── MOTM Card ────────────────────────────────────────────────────────────────

def make_motm_card(
    player_name: str,
    rating: float,
    goals: int,
    assists: int,
    position: str = "—",
    match_context: str = "",
) -> io.BytesIO:
    W, H = 700, 420

    img = _gradient_bg(W, H, (10, 8, 20), (25, 20, 45))
    img = _draw_diagonal_stripes(img, (255, 215, 0))
    draw = ImageDraw.Draw(img)
    _draw_noise(draw, W, H)

    # Gold top bar
    _glow_rect(img, 0, 0, W, 5, GOLD, radius=6)

    # MOTM label
    motm_font = _font(22, bold=True)
    _centered_text(draw, "🏆  MAN OF THE MATCH  🏆", 18, motm_font, GOLD, W)

    # Separator
    draw.line([(50, 54), (W - 50, 54)], fill=(60, 55, 80), width=1)

    # Player name
    name_font = _font(58, bold=True)
    name_display = player_name.upper()
    bbox = draw.textbbox((0, 0), name_display, font=name_font)
    nw = bbox[2] - bbox[0]
    if nw > W - 60:
        name_font = _font(42, bold=True)
    _centered_text(draw, name_display, 68, name_font, WHITE, W)

    # Rating circle
    cx, cy, cr = 155, 260, 70
    # Outer ring
    draw.ellipse([cx - cr - 5, cy - cr - 5, cx + cr + 5, cy + cr + 5], outline=GOLD, width=3)
    draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(30, 25, 50))
    rating_font = _font(48, bold=True)
    r_str = f"{rating:.1f}"
    bbox = draw.textbbox((0, 0), r_str, font=rating_font)
    draw.text((cx - (bbox[2] - bbox[0]) // 2, cy - (bbox[3] - bbox[1]) // 2 - 5), r_str, font=rating_font, fill=GOLD)
    sub_font = _font(14, bold=False)
    _centered_text_at = lambda text, cx_, cy_, font_, color_: draw.text(
        (cx_ - (draw.textbbox((0,0), text, font=font_)[2] - draw.textbbox((0,0), text, font=font_)[0]) // 2, cy_),
        text, font=font_, fill=color_
    )
    sub_font2 = _font(13, bold=False)
    sub_txt = "RATING"
    bbox = draw.textbbox((0, 0), sub_txt, font=sub_font2)
    draw.text((cx - (bbox[2] - bbox[0]) // 2, cy + 28), sub_txt, font=sub_font2, fill=GRAY)

    # Stats grid
    stat_font = _font(36, bold=True)
    label_font = _font(14, bold=False)
    stats = [("GOALS", str(goals)), ("ASSISTS", str(assists))]
    stat_x_start = 280
    for i, (label, val) in enumerate(stats):
        sx = stat_x_start + i * 180
        sy = 220
        # Box
        draw.rectangle([sx, sy, sx + 150, sy + 90], fill=(25, 22, 42), outline=(50, 45, 75), width=1)
        # Value
        bbox = draw.textbbox((0, 0), val, font=stat_font)
        draw.text((sx + 75 - (bbox[2] - bbox[0]) // 2, sy + 12), val, font=stat_font, fill=WHITE)
        # Label
        bbox = draw.textbbox((0, 0), label, font=label_font)
        draw.text((sx + 75 - (bbox[2] - bbox[0]) // 2, sy + 60), label, font=label_font, fill=GRAY)

    # Match context
    if match_context:
        ctx_font = _font(18, bold=False)
        _centered_text(draw, match_context, 350, ctx_font, GRAY, W)

    # Footer
    footer_font = _font(14, bold=False)
    _centered_text(draw, "RACHAD L3ERGONI · FC 26 PRO CLUBS", H - 22, footer_font, GRAY, W)
    _glow_rect(img, 0, H - 4, W, H, GOLD, radius=3)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ─── 5-Match Summary ─────────────────────────────────────────────────────────

def make_five_match_summary(results: list[dict]) -> io.BytesIO:
    """
    results: list of dicts with keys: opponent, our_goals, opp_goals, date
    """
    W, H = 900, 340
    img = _gradient_bg(W, H, (6, 8, 16), (18, 20, 34))
    draw = ImageDraw.Draw(img)
    _draw_noise(draw, W, H)

    _glow_rect(img, 0, 0, W, 5, BLUE_NEON, radius=5)

    title_font = _font(24, bold=True)
    _centered_text(draw, "DERNIERS 5 MATCHS · RACHAD L3ERGONI", 18, title_font, WHITE, W)
    draw.line([(40, 56), (W - 40, 56)], fill=(40, 45, 65), width=1)

    tile_w = 160
    tile_h = 210
    gap = (W - 5 * tile_w) // 6
    start_x = gap
    tile_y = 72

    team_font  = _font(13, bold=True)
    score_font = _font(36, bold=True)
    res_font   = _font(14, bold=True)
    date_font  = _font(11, bold=False)

    for i, r in enumerate(results[:5]):
        tx = start_x + i * (tile_w + gap)
        og = r.get("our_goals", 0)
        opg = r.get("opp_goals", 0)
        acc = result_color(og, opg)
        opp = r.get("opponent", "???")
        date_str = r.get("date", "")

        # Tile BG
        draw.rectangle([tx, tile_y, tx + tile_w, tile_y + tile_h], fill=(18, 20, 32), outline=acc, width=2)

        # Top accent
        draw.rectangle([tx, tile_y, tx + tile_w, tile_y + 4], fill=acc)

        # Opponent name
        opp_display = opp.upper()[:11]
        bbox = draw.textbbox((0, 0), opp_display, font=team_font)
        draw.text((tx + (tile_w - (bbox[2] - bbox[0])) // 2, tile_y + 14), opp_display, font=team_font, fill=WHITE)

        # Score
        score_str = f"{og}-{opg}"
        bbox = draw.textbbox((0, 0), score_str, font=score_font)
        draw.text((tx + (tile_w - (bbox[2] - bbox[0])) // 2, tile_y + 68), score_str, font=score_font, fill=WHITE)

        # Result pill
        res_str = result_label(og, opg)[:3]
        res_bg = acc
        pill_y = tile_y + 125
        pill_h = 28
        draw.rectangle([tx + 20, pill_y, tx + tile_w - 20, pill_y + pill_h], fill=res_bg)
        bbox = draw.textbbox((0, 0), res_str, font=res_font)
        draw.text((tx + (tile_w - (bbox[2] - bbox[0])) // 2, pill_y + 6), res_str, font=res_font, fill=BG_DARK)

        # Date
        if date_str:
            bbox = draw.textbbox((0, 0), date_str, font=date_font)
            draw.text((tx + (tile_w - (bbox[2] - bbox[0])) // 2, tile_y + 168), date_str, font=date_font, fill=GRAY)

    # Overall row at bottom
    wins   = sum(1 for r in results[:5] if r.get("our_goals", 0) > r.get("opp_goals", 0))
    draws  = sum(1 for r in results[:5] if r.get("our_goals", 0) == r.get("opp_goals", 0))
    losses = sum(1 for r in results[:5] if r.get("our_goals", 0) < r.get("opp_goals", 0))
    gf     = sum(r.get("our_goals", 0) for r in results[:5])
    ga     = sum(r.get("opp_goals", 0) for r in results[:5])

    summary_font = _font(16, bold=False)
    summary = f"W {wins}   D {draws}   L {losses}     {gf} buts pour  /  {ga} buts contre"
    _centered_text(draw, summary, tile_y + tile_h + 16, summary_font, GRAY, W)

    _glow_rect(img, 0, H - 4, W, H, BLUE_NEON, radius=3)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ─── TOTW Card ────────────────────────────────────────────────────────────────

FORMATION_POSITIONS = {
    11: [
        (450, 420),  # GK
        (160, 310), (330, 290), (570, 290), (740, 310),  # DEF
        (200, 195), (450, 175), (700, 195),              # MID
        (280, 95),  (450, 72),  (620, 95),               # ATT
    ]
}


def make_totw_card(players: list[tuple[str, float]]) -> io.BytesIO:
    """players: list of (name, avg_rating) top 11, best first."""
    W, H = 900, 560

    # Pitch background
    img = Image.new("RGB", (W, H), (12, 50, 18))
    draw = ImageDraw.Draw(img)

    # Pitch markings
    def pitch_line(x1, y1, x2, y2):
        draw.line([(x1, y1), (x2, y2)], fill=(25, 75, 30), width=2)

    # Stripes
    stripe_h = H // 10
    for i in range(10):
        c = (14, 54, 20) if i % 2 == 0 else (11, 46, 16)
        draw.rectangle([0, i * stripe_h, W, (i + 1) * stripe_h], fill=c)

    # Pitch lines
    margin_x, margin_y = 50, 40
    pitch_line(margin_x, margin_y, W - margin_x, margin_y)
    pitch_line(margin_x, H - margin_y, W - margin_x, H - margin_y)
    pitch_line(margin_x, margin_y, margin_x, H - margin_y)
    pitch_line(W - margin_x, margin_y, W - margin_x, H - margin_y)
    pitch_line(margin_x, H // 2, W - margin_x, H // 2)

    # Center circle
    cx, cy = W // 2, H // 2
    draw.ellipse([cx - 70, cy - 70, cx + 70, cy + 70], outline=(25, 75, 30), width=2)
    draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(25, 75, 30))

    # Penalty areas
    pa_w, pa_h = 220, 110
    draw.rectangle([cx - pa_w // 2, margin_y, cx + pa_w // 2, margin_y + pa_h], outline=(25, 75, 30), width=2)
    draw.rectangle([cx - pa_w // 2, H - margin_y - pa_h, cx + pa_w // 2, H - margin_y], outline=(25, 75, 30), width=2)

    # Title overlay at top
    overlay = Image.new("RGBA", (W, 55), (0, 0, 0, 160))
    img = img.convert("RGBA")
    img.alpha_composite(overlay, (0, 0))
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)

    title_font = _font(26, bold=True)
    _centered_text(draw, "⭐  TEAM OF THE WEEK  ⭐", 14, title_font, GOLD, W)

    # Player cards
    positions = FORMATION_POSITIONS[11]
    name_font = _font(13, bold=True)
    rating_font = _font(15, bold=True)

    for i, (px, py) in enumerate(positions):
        if i >= len(players):
            break
        name, rating = players[i]
        display = name[:12].upper()
        card_w, card_h = 110, 48
        cx_ = px - card_w // 2
        cy_ = py - card_h // 2

        # Card BG
        card_color = (255, 185, 0) if rating >= 8.5 else ((200, 200, 200) if rating >= 7.0 else (160, 80, 80))
        card_alpha = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_alpha)
        card_draw.rounded_rectangle([0, 0, card_w - 1, card_h - 1], radius=6, fill=(0, 0, 0, 185))
        card_draw.rounded_rectangle([0, 0, card_w - 1, 4], radius=6, fill=card_color + (230,))
        img_rgba = img.convert("RGBA")
        img_rgba.alpha_composite(card_alpha, (cx_, cy_))
        img = img_rgba.convert("RGB")
        draw = ImageDraw.Draw(img)

        # Player name
        bbox = draw.textbbox((0, 0), display, font=name_font)
        nw = bbox[2] - bbox[0]
        draw.text((px - nw // 2, cy_ + 10), display, font=name_font, fill=WHITE)

        # Rating
        r_str = f"{rating:.1f}"
        bbox = draw.textbbox((0, 0), r_str, font=rating_font)
        draw.text((px - (bbox[2] - bbox[0]) // 2, cy_ + 27), r_str, font=rating_font, fill=card_color)

    # Footer
    footer_font = _font(13, bold=False)
    _centered_text(draw, "RACHAD L3ERGONI · FC 26 PRO CLUBS", H - 20, footer_font, (100, 140, 100), W)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ─── Player Comparison Card ───────────────────────────────────────────────────

def make_comparison_card(
    p1: dict,   # {name, goals, assists, avg_rating, games, shots}
    p2: dict,
) -> io.BytesIO:
    W, H = 860, 480
    P1_COLOR = (0, 180, 255)   # blue
    P2_COLOR = (0, 255, 140)   # green

    img = _gradient_bg(W, H, (6, 8, 18), (20, 18, 36))
    img = _draw_diagonal_stripes(img, (255, 255, 255))
    draw = ImageDraw.Draw(img)
    _draw_noise(draw, W, H)

    # Top bar
    _glow_rect(img, 0, 0, W // 2, 5, P1_COLOR, radius=5)
    _glow_rect(img, W // 2, 0, W, 5, P2_COLOR, radius=5)

    # Title
    title_font = _font(22, bold=True)
    _centered_text(draw, "⚔️  HEAD TO HEAD  ⚔️", 14, title_font, WHITE, W)

    # VS divider
    draw.line([(W // 2, 50), (W // 2, H - 40)], fill=(40, 45, 65), width=2)
    vs_font = _font(36, bold=True)
    vs_text = "VS"
    bbox = draw.textbbox((0, 0), vs_text, font=vs_font)
    vx = W // 2 - (bbox[2] - bbox[0]) // 2
    draw.rectangle([vx - 12, 195, vx + (bbox[2]-bbox[0]) + 12, 195 + (bbox[3]-bbox[1]) + 12], fill=(25, 22, 40))
    draw.text((vx, 198), vs_text, font=vs_font, fill=GRAY)

    # Player name headers
    name_font = _font(32, bold=True)
    for player, cx, color in [(p1, W // 4, P1_COLOR), (p2, 3 * W // 4, P2_COLOR)]:
        name = player.get("name", "?").upper()
        if len(name) > 12:
            name = name[:11] + "."
        bbox = draw.textbbox((0, 0), name, font=name_font)
        nw = bbox[2] - bbox[0]
        draw.text((cx - nw // 2, 55), name, font=name_font, fill=color)

    # Stats rows
    stat_labels = [
        ("GOALS",    "goals",      lambda x: str(x)),
        ("ASSISTS",  "assists",    lambda x: str(x)),
        ("AVG RTG",  "avg_rating", lambda x: f"{x:.2f}"),
        ("GAMES",    "games",      lambda x: str(x)),
        ("SHOTS",    "shots",      lambda x: str(x)),
    ]

    val_font   = _font(30, bold=True)
    label_font = _font(14, bold=False)
    bar_y_start = 105

    for i, (label, key, fmt) in enumerate(stat_labels):
        row_y = bar_y_start + i * 64

        # Row bg alternating
        row_color = (18, 20, 32) if i % 2 == 0 else (22, 24, 38)
        draw.rectangle([0, row_y, W, row_y + 58], fill=row_color)

        v1 = p1.get(key, 0) or 0
        v2 = p2.get(key, 0) or 0
        max_val = max(float(v1), float(v2), 0.01)

        # Left value (player 1)
        s1 = fmt(v1)
        bbox = draw.textbbox((0, 0), s1, font=val_font)
        draw.text((W // 4 - (bbox[2] - bbox[0]) // 2, row_y + 8), s1, font=val_font,
                  fill=P1_COLOR if float(v1) >= float(v2) else GRAY)

        # Right value (player 2)
        s2 = fmt(v2)
        bbox = draw.textbbox((0, 0), s2, font=val_font)
        draw.text((3 * W // 4 - (bbox[2] - bbox[0]) // 2, row_y + 8), s2, font=val_font,
                  fill=P2_COLOR if float(v2) >= float(v1) else GRAY)

        # Center label
        bbox = draw.textbbox((0, 0), label, font=label_font)
        lw = bbox[2] - bbox[0]
        draw.text((W // 2 - lw // 2, row_y + 22), label, font=label_font, fill=GRAY)

        # Mini progress bars
        bar_h = 6
        bar_max_w = 110
        bar_bottom = row_y + 52

        # P1 bar (right-aligned from center)
        b1w = int(bar_max_w * float(v1) / max_val)
        draw.rectangle([W // 2 - 10 - b1w, bar_bottom - bar_h, W // 2 - 10, bar_bottom], fill=P1_COLOR)

        # P2 bar (left-aligned from center)
        b2w = int(bar_max_w * float(v2) / max_val)
        draw.rectangle([W // 2 + 10, bar_bottom - bar_h, W // 2 + 10 + b2w, bar_bottom], fill=P2_COLOR)

    # Winner banner
    wins_p1 = sum(1 for _, key, fmt in stat_labels if (p1.get(key) or 0) >= (p2.get(key) or 0))
    wins_p2 = len(stat_labels) - wins_p1
    winner  = p1 if wins_p1 > wins_p2 else p2
    w_color = P1_COLOR if wins_p1 > wins_p2 else P2_COLOR

    banner_font = _font(18, bold=True)
    banner_text = f"🏆 WINNER: {winner.get('name','?').upper()}"
    bbox = draw.textbbox((0, 0), banner_text, font=banner_font)
    bw = bbox[2] - bbox[0]
    bx = W // 2 - bw // 2
    draw.rectangle([bx - 20, H - 38, bx + bw + 20, H - 8], fill=w_color)
    draw.text((bx, H - 35), banner_text, font=banner_font, fill=BG_DARK)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
