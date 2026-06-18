"""image_gen.py — EA FC Pro Clubs premium card generator.
Resolution: 2160x3840 (UHD portrait)
Pure Pillow — no Groq, no AI, no randomness.
"""

import io
import os
import math
import logging
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from typing import List, Optional, Dict
from models import PlayerStats, ClubStats

logger = logging.getLogger("rachad_bot.image_gen")

# ─── PLAYER IMAGE LOADER ───

def _load_player_photo(name: str, assets_dir: str, size=(1400, 1400), photo_path: Optional[str] = None):
    """Load player photo with debug logging."""
    print(f"[PHOTO DEBUG] Player: {name}, Asset path: {photo_path}, Assets dir: {assets_dir}")

    if photo_path and os.path.exists(photo_path):
        try:
            img = Image.open(photo_path).convert("RGBA")
            img = img.resize(size, Image.LANCZOS)
            print(f"[PHOTO DEBUG] ✅ Loaded from explicit path: {photo_path}")
            return img
        except Exception as e:
            print(f"[PHOTO DEBUG] ❌ Failed explicit path: {photo_path} — {e}")

    # Search by name variations
    clean = name.replace(" ", "_").lower()
    upper = name.upper()
    title = name.title()

    candidates = [
        os.path.join(assets_dir, f"{name}.png"),
        os.path.join(assets_dir, f"{name}.jpg"),
        os.path.join(assets_dir, f"{name}.jpeg"),
        os.path.join(assets_dir, f"{clean}.png"),
        os.path.join(assets_dir, f"{clean}.jpg"),
        os.path.join(assets_dir, f"{clean}.jpeg"),
        os.path.join(assets_dir, f"{upper}.png"),
        os.path.join(assets_dir, f"{upper}.jpg"),
        os.path.join(assets_dir, f"{upper}.jpeg"),
        os.path.join(assets_dir, f"{title}.png"),
        os.path.join(assets_dir, f"{title}.jpg"),
        os.path.join(assets_dir, f"{title}.jpeg"),
    ]

    for path in candidates:
        if os.path.exists(path):
            try:
                img = Image.open(path).convert("RGBA")
                img = img.resize(size, Image.LANCZOS)
                print(f"[PHOTO DEBUG] ✅ Loaded from search: {path}")
                return img
            except Exception as e:
                print(f"[PHOTO DEBUG] ❌ Failed search path: {path} — {e}")

    print(f"[PHOTO DEBUG] ❌ No photo found for: {name}")
    return None


# ─── CONSTANTS ───
CARD_W, CARD_H = 2160, 3840
MARGIN = 120

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

        # Subtle glow
        img = _glow_circle(img, W // 2, H // 3, 900, pal["glow"], 0.2)
        img = _glow_circle(img, W // 2, H * 2 // 3, 700, pal["accent2"], 0.15)
        draw = ImageDraw.Draw(img)

        # ── TOP: Rating (left), Nickname (center), Position (right) ──
        rating = round(getattr(player, "rating_pg", 7.0), 1)

        # Rating hexagon (top-left)
        hex_x = 280
        hex_y = 280
        hex_r = 140
        hex_pts = _hexagon_points(hex_x, hex_y, hex_r)
        for offset in [30, 20, 10]:
            glow_pts = _hexagon_points(hex_x, hex_y, hex_r + offset)
            alpha = int(60 - offset * 1.5)
            draw.polygon(glow_pts, fill=(*pal["glow"], alpha))
        draw.polygon(hex_pts, fill=(15, 15, 15, 240), outline=pal["accent"], width=4)
        f_rating = self._font(180, bold=True)
        draw.text((hex_x, hex_y), str(rating), fill=pal["badge"], font=f_rating, anchor="mm")
        f_ovr = self._font(36, bold=True)
        draw.text((hex_x, hex_y + 95), "OVR", fill=pal["text_dim"], font=f_ovr, anchor="mm")

        # Nickname from squad.json (top-center)
        nickname = getattr(player, "_squad_info", {}).get("nickname", player.name)
        f_nick = self._font(120, bold=True)
        draw.text((W // 2, 200), nickname.upper(), fill=pal["text"], font=f_nick, anchor="mm")

        # Position badge (top-right)
        pos_x = W - 280
        pos_y = 280
        f_pos = self._font(56, bold=True)
        pw, ph = 200, 85
        px = pos_x - pw // 2
        draw.rounded_rectangle([px, pos_y - ph // 2, px + pw, pos_y + ph // 2], radius=18, fill=pal["accent"], outline=pal["accent2"], width=3)
        draw.text((pos_x, pos_y), pos.upper(), fill=(10, 10, 10), font=f_pos, anchor="mm")

        # ── CENTER: Large player photo (main focus) ──
        photo_y = 500
        photo_size = (1400, 1400)
        photo = _load_player_photo(player.name, self.assets_dir, photo_size, photo_path=photo_override)

        print(f"[CARD DEBUG] Player: {player.name}, Nickname: {nickname}, Asset path: {photo_override}, Exists: {photo is not None}")

        if photo:
            px = (W - photo.width) // 2
            py = photo_y
            # Large soft glow behind photo
            shadow = Image.new("RGBA", (photo.width + 120, photo.height + 120), (0, 0, 0, 0))
            s_draw = ImageDraw.Draw(shadow)
            s_draw.rounded_rectangle([30, 30, photo.width + 90, photo.height + 90], radius=50, fill=(*pal["glow"], 50))
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=50))
            img.paste(shadow, (px - 60, py - 60), shadow)
            # Photo with rounded mask
            mask = Image.new("L", photo.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, photo.width, photo.height], radius=40, fill=255)
            img.paste(photo, (px, py), mask)
        else:
            # Fallback silhouette
            sil_y = photo_y + 300
            draw.ellipse([W // 2 - 350, sil_y, W // 2 + 350, sil_y + 700], fill=(35, 35, 35, 200), outline=pal["accent"], width=4)
            draw.ellipse([W // 2 - 140, sil_y - 180, W // 2 + 140, sil_y + 180], fill=(35, 35, 35, 200), outline=pal["accent"], width=4)
            f_sil = self._font(70, bold=True)
            draw.text((W // 2, sil_y + 400), player.name, fill=pal["text_dim"], font=f_sil, anchor="mm")

        # ── BOTTOM: Stats grid (2×4) ──
        stats = [
            ("GOALS", getattr(player, "goals", 0)),
            ("ASSISTS", getattr(player, "assists", 0)),
            ("RATING", round(getattr(player, "rating_pg", 0), 1)),
            ("PASS %", f"{round(getattr(player, 'pass_accuracy', 0), 1)}%"),
            ("WIN %", f"{round(getattr(player, 'win_rate', 0), 1)}%"),
            ("POSS LOST", getattr(player, "possession_losses", 0)),
            ("IMPACT", round(getattr(player, "impact_score", 0), 1)),
            ("MOTM", getattr(player, "motm", 0)),
        ]
        if extra_stats:
            stats = extra_stats

        grid_y = 2100
        box_w = (W - MARGIN * 3) // 2
        box_h = 180
        gap_x = MARGIN
        gap_y = 24
        f_stat_label = self._font(34, bold=True)
        f_stat_val = self._font(68, bold=True)

        for i, (s_label, s_val) in enumerate(stats[:8]):
            col = i % 2
            row = i // 2
            x = MARGIN + col * (box_w + gap_x)
            y = grid_y + row * (box_h + gap_y)

            # Clean dark box with thin accent border
            draw.rounded_rectangle([x, y, x + box_w, y + box_h], radius=20, fill=(22, 22, 22, 180), outline=(*pal["accent"], 100), width=2)
            draw.text((x + 30, y + 16), s_label, fill=pal["text_dim"], font=f_stat_label)
            draw.text((x + 30, y + 70), str(s_val), fill=pal["text"], font=f_stat_val)

        # ── FOOTER ──
        f_foot = self._font(34)
        draw.text((W // 2, H - 70), "RACHAD L3ERGONI • PRO CLUBS TRACKER", fill=pal["text_dim"], font=f_foot, anchor="mm")

        # Final composite and sharpen
        img = img.convert("RGB")
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.2)

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf

    # ───────────────────────────────────────────
    # PUBLIC CARD METHODS
    # ───────────────────────────────────────────

    def generate_player_card(self, player, pos, division=6, photo_path=None):
        return self._build_fc_card(player, pos, "gold", "PLAYER PROFILE", photo_override=photo_path)

    def generate_mvp_card(self, player, pos, photo_path=None):
        return self._build_fc_card(player, pos, "gold", "MAN OF THE MATCH", photo_override=photo_path)

    def generate_roast_card(self, player, roast_text, pos, photo_path=None):
        # Roast card uses red theme with custom stats
        stats = [
            ("THROWING", round(getattr(player, "throwing_score", 0), 1)),
            ("ERROR", round(getattr(player, "error_score", 0), 1)),
            ("PASS %", f"{round(getattr(player, 'pass_accuracy', 0), 1)}%"),
            ("IMPACT", round(getattr(player, "impact_score", 0), 1)),
            ("POSS LOST", getattr(player, "possession_losses", 0)),
            ("RATING", round(getattr(player, "rating_pg", 0), 1)),
            ("GOALS", getattr(player, "goals", 0)),
            ("ASSISTS", getattr(player, "assists", 0)),
        ]
        return self._build_fc_card(player, pos, "red", "FRAUD DETECTED", extra_stats=stats, photo_override=photo_path)

    def generate_anime_card(self, player, pos, style, label, photo_path=None):
        return self._build_fc_card(player, pos, "purple", label, photo_override=photo_path)

    def generate_beast_card(self, player, pos, photo_path=None):
        return self._build_fc_card(player, pos, "blue", "BEAST MODE", photo_override=photo_path)

    def generate_court_case(self, player, pos, evidence, photo_path=None):
        stats = [
            ("THROWING", round(getattr(player, "throwing_score", 0), 1)),
            ("ERROR", round(getattr(player, "error_score", 0), 1)),
            ("PASS %", f"{round(getattr(player, 'pass_accuracy', 0), 1)}%"),
            ("IMPACT", round(getattr(player, "impact_score", 0), 1)),
            ("POSS LOST", getattr(player, "possession_losses", 0)),
            ("RATING", round(getattr(player, "rating_pg", 0), 1)),
            ("GOALS", getattr(player, "goals", 0)),
            ("ASSISTS", getattr(player, "assists", 0)),
        ]
        return self._build_fc_card(player, pos, "red", "COURT CASE", extra_stats=stats, photo_override=photo_path)

    def generate_playmaker_card(self, player, pos, photo_path=None):
        return self._build_fc_card(player, pos, "green", "PLAYMAKER", photo_override=photo_path)

    def generate_sniper_card(self, player, pos, photo_path=None):
        return self._build_fc_card(player, pos, "blue", "SNIPER", photo_override=photo_path)

    def generate_leaderboard(self, players, metric):
        pal = PALETTES["dark"]
        W, H = CARD_W, CARD_H
        img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")
        img = _glow_circle(img, W // 2, H // 2, 800, pal["glow"], 0.2)
        draw = ImageDraw.Draw(img)

        f_title = self._font(80, bold=True)
        draw.text((W // 2, 80), f"LEADERBOARD — {metric.upper().replace('_', ' ')}", fill=pal["accent"], font=f_title, anchor="mm")

        sorted_players = sorted(players, key=lambda p: getattr(p, metric, 0), reverse=True)[:5]
        row_h = 500
        start_y = 250
        f_rank = self._font(100, bold=True)
        f_name = self._font(70, bold=True)
        f_val = self._font(90, bold=True)
        medals = ["🥇", "🥈", "🥉", "4.", "5."]

        for i, p in enumerate(sorted_players):
            y = start_y + i * row_h
            draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + row_h - 30], radius=30, fill=(30, 30, 30, 200), outline=(*pal["accent"], 100), width=2)
            draw.text((MARGIN + 60, y + row_h // 2 - 30), medals[i], fill=pal["text"], font=f_rank)
            draw.text((MARGIN + 200, y + row_h // 2 - 30), p.name, fill=pal["text"], font=f_name)
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

        motm_y = 420
        f_motm = self._font(60, bold=True)
        draw.text((W // 2, motm_y), "MAN OF THE MATCH", fill=pal["accent2"], font=f_motm, anchor="mm")
        f_mname = self._font(120, bold=True)
        draw.text((W // 2, motm_y + 120), motm.name.upper(), fill=pal["text"], font=f_mname, anchor="mm")
        f_mstats = self._font(50)
        draw.text((W // 2, motm_y + 260), f"Impact: {motm.impact_score} | Goals: {motm.goals} | Rating: {round(motm.rating_pg, 1)}", fill=pal["text_dim"], font=f_mstats, anchor="mm")

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

        nickname = getattr(player, "_squad_info", {}).get("nickname", player.name)
        f_name = self._font(130, bold=True)
        draw.text((W // 2, 1600), nickname.upper(), fill=pal["text"], font=f_name, anchor="mm")

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

    # ───────────────────────────────────────────
    # FORM CARD — Last N Matches Trend
    # ───────────────────────────────────────────
    def generate_form_card(self, player, matches_data, num_matches):
        """Form card showing last N matches trend."""
        pal = PALETTES["blue"]
        W, H = CARD_W, CARD_H
        img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")
        img = _glow_circle(img, W // 2, H // 3, 800, pal["glow"], 0.3)
        draw = ImageDraw.Draw(img)

        nickname = getattr(player, "_squad_info", {}).get("nickname", player.name)
        f_title = self._font(90, bold=True)
        draw.text((W // 2, 80), f"FORM — LAST {num_matches} MATCHES", fill=pal["accent"], font=f_title, anchor="mm")

        f_name = self._font(110, bold=True)
        draw.text((W // 2, 200), nickname.upper(), fill=pal["text"], font=f_name, anchor="mm")

        # Match rows
        row_h = 280
        start_y = 340
        f_label = self._font(32, bold=True)
        f_val = self._font(48, bold=True)
        f_small = self._font(36)

        ratings = []
        for i, md in enumerate(matches_data[:num_matches]):
            y = start_y + i * row_h
            draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + row_h - 20], radius=20, fill=(25, 25, 25, 200), outline=(*pal["accent"], 80), width=2)

            # Date + Opponent
            draw.text((MARGIN + 30, y + 15), f"{md['date']} vs {md['opponent']}", fill=pal["text_dim"], font=f_label)

            # Stats
            stats = [
                ("RATING", f"{md['rating']}"),
                ("GOALS", str(md['goals'])),
                ("ASSISTS", str(md['assists'])),
                ("PASS %", f"{md['pass_acc']}%"),
            ]
            box_w = (W - MARGIN * 2 - 60) // 4
            for j, (sl, sv) in enumerate(stats):
                x = MARGIN + 30 + j * (box_w + 10)
                sy = y + 70
                draw.text((x, sy), sl, fill=pal["text_dim"], font=f_small)
                draw.text((x, sy + 45), sv, fill=pal["text"], font=f_val)

            ratings.append(md['rating'])

        # Trend
        if len(ratings) >= 2:
            half = len(ratings) // 2
            avg_first = sum(ratings[:half]) / max(half, 1)
            avg_last = sum(ratings[half:]) / max(len(ratings) - half, 1)
            if avg_last > avg_first + 0.3:
                trend = "📈 IMPROVING"
                trend_color = (50, 255, 100)
            elif avg_last < avg_first - 0.3:
                trend = "📉 DECLINING"
                trend_color = (255, 50, 50)
            else:
                trend = "➡️ STABLE"
                trend_color = (255, 255, 100)
        else:
            trend = "➡️ STABLE"
            trend_color = (255, 255, 100)

        trend_y = start_y + num_matches * row_h + 40
        f_trend = self._font(80, bold=True)
        draw.text((W // 2, trend_y), trend, fill=trend_color, font=f_trend, anchor="mm")

        avg_rating = sum(ratings) / max(len(ratings), 1)
        f_avg = self._font(60)
        draw.text((W // 2, trend_y + 100), f"Avg Rating: {round(avg_rating, 1)}", fill=pal["text_dim"], font=f_avg, anchor="mm")

        f_foot = self._font(36)
        draw.text((W // 2, H - 80), "RACHAD L3ERGONI • FORM TRACKER", fill=pal["text_dim"], font=f_foot, anchor="mm")

        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf

    # ───────────────────────────────────────────
    # RECORDS CARD — Club Historical Records
    # ───────────────────────────────────────────
    def generate_records_card(self, club, records):
        """Club records card."""
        pal = PALETTES["gold"]
        W, H = CARD_W, CARD_H
        img = _gradient_bg(W, H, (8, 6, 2), (25, 18, 6)).convert("RGBA")
        img = _glow_circle(img, W // 2, H // 3, 700, pal["glow"], 0.25)
        draw = ImageDraw.Draw(img)

        f_title = self._font(100, bold=True)
        draw.text((W // 2, 80), "🏆 CLUB RECORDS", fill=pal["accent"], font=f_title, anchor="mm")

        f_sub = self._font(50)
        draw.text((W // 2, 180), club.club_name.upper(), fill=pal["text"], font=f_sub, anchor="mm")

        row_h = 200
        start_y = 280
        f_rec = self._font(40, bold=True)
        f_val = self._font(56, bold=True)

        for i, (label, value) in enumerate(records[:8]):
            y = start_y + i * row_h
            draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + row_h - 20], radius=20, fill=(30, 25, 15, 200), outline=(*pal["accent"], 100), width=2)
            draw.text((MARGIN + 40, y + row_h // 2 - 30), label, fill=pal["text_dim"], font=f_rec)
            draw.text((W - MARGIN - 40, y + row_h // 2 - 30), str(value), fill=pal["accent"], font=f_val, anchor="rm")

        f_foot = self._font(36)
        draw.text((W // 2, H - 80), "RACHAD L3ERGONI • RECORDS", fill=pal["text_dim"], font=f_foot, anchor="mm")

        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf

    # ───────────────────────────────────────────
    # LEGEND CARD — Club Legend (MVP reframe)
    # ───────────────────────────────────────────
    def generate_legend_card(self, player, pos, photo_path=None):
        """Legend card — same as MVP but with LEGEND label."""
        return self._build_fc_card(player, pos, "gold", "CLUB LEGEND", photo_override=photo_path)
