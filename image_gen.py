"""image_gen.py — EA FC Pro Clubs premium card generator.
Pillow-based with auto-generated templates and Pollinations AI photo PRIMARY.
NO local photo fallback — Pollinations is the main source.
"""

import io
import os
import math
import logging
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from typing import List, Optional, Dict
from models import PlayerStats, ClubStats

logger = logging.getLogger("rachad_bot.image_gen")

# ─── AUTO TEMPLATES ───
try:
    from auto_templates import get_template, TEMPLATE_GENERATORS
    AUTO_TEMPLATES_AVAILABLE = True
except ImportError:
    AUTO_TEMPLATES_AVAILABLE = False
    get_template = None
    TEMPLATE_GENERATORS = {}

# ─── POLLINATIONS AI PHOTOS & VIDEOS ───
try:
    from services.pollinations import PollinationsClient
    POLLINATIONS_AVAILABLE = True
except ImportError:
    POLLINATIONS_AVAILABLE = False
    PollinationsClient = None
    
# ─── CONSTANTS ───
CARD_W, CARD_H = 1440, 2160
MARGIN = 80

LABEL_TO_TEMPLATE = {
    "MAN OF THE MATCH": "mvp",
    "FRAUD DETECTED": "fraud",
    "GHOST DETECTED": "ghost",
    "CARRY DETECTED": "carry",
    "COURT CASE": "court",
    "PLAYMAKER": "playmaker",
    "SNIPER": "sniper",
    "BALL LOSER": "ball_loser",
    "CLUB LEGEND": "mvp",
    "PLAYER PROFILE": "mvp",
    "BIO": "mvp",
}

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

# ─── FONT LOADER ───

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
        self._pollinations = None
        self._media_cache = {}  # In-memory cache
        self._cache_dir = "cache/pollinations"
        os.makedirs(self._cache_dir, exist_ok=True)

    def _font(self, size, bold=False):
        key = (size, bold)
        if key not in self.fonts:
            self.fonts[key] = _load_font(size, bold)
        return self.fonts[key]

    def _get_pollinations(self):
        """Lazy-init Pollinations client."""
        if self._pollinations is None and POLLINATIONS_AVAILABLE:
            self._pollinations = PollinationsClient()
        return self._pollinations

    def _get_cached_photo_path(self, player_name: str, card_type: str) -> Optional[str]:
        """Check if we have a cached AI photo on disk."""
        safe_name = player_name.replace(" ", "_").replace("/", "_")
        cache_path = os.path.join(self._cache_dir, f"{safe_name}_{card_type}.png")
        if os.path.exists(cache_path):
            return cache_path
        return None

    def _save_photo_cache(self, player_name: str, card_type: str, img_bytes: bytes) -> str:
        """Save AI photo to disk cache."""
        safe_name = player_name.replace(" ", "_").replace("/", "_")
        cache_path = os.path.join(self._cache_dir, f"{safe_name}_{card_type}.png")
        with open(cache_path, "wb") as f:
            f.write(img_bytes)
        return cache_path

    def _generate_ai_photo(self, player_name: str, card_type: str = "player") -> Optional[bytes]:
        """Generate an AI player photo using Pollinations. Returns PNG bytes or None."""
        if not POLLINATIONS_AVAILABLE:
            logger.warning("[POLLINATIONS] Module not available")
            return None

        client = self._get_pollinations()
        if not client or not client.is_available():
            logger.warning("[POLLINATIONS] API key not set — cannot generate AI photo for %s", player_name)
            return None

        # Check in-memory cache
        cache_key = f"pollinations:{player_name}:{card_type}"
        if cache_key in self._media_cache:
            logger.info("[POLLINATIONS] Using in-memory cache for %s", player_name)
            return self._media_cache[cache_key]

        # Check disk cache
        cached_path = self._get_cached_photo_path(player_name, card_type)
        if cached_path:
            try:
                with open(cached_path, "rb") as f:
                    img_bytes = f.read()
                self._media_cache[cache_key] = img_bytes
                logger.info("[POLLINATIONS] Using disk cache for %s", player_name)
                return img_bytes
            except Exception as e:
                logger.error("[POLLINATIONS] Disk cache read failed: %s", e)

        # Generate new photo
        prompts = {
            "mvp": f"Professional football player portrait, {player_name}, golden lighting, stadium background, heroic pose, photorealistic, 4K, sports photography, wearing orange jersey",
            "fraud": f"Football player portrait, {player_name}, dramatic red lighting, disappointed expression, dark moody stadium, photorealistic, 4K, wearing orange jersey",
            "ghost": f"Football player portrait, {player_name}, ethereal purple lighting, fading ghostly effect, mysterious atmosphere, photorealistic, 4K, wearing orange jersey",
            "carry": f"Football player portrait, {player_name}, heroic blue lighting, powerful stance, energy aura, photorealistic, 4K, wearing orange jersey",
            "court": f"Football player portrait, {player_name}, courtroom lighting, serious expression, dramatic shadows, photorealistic, 4K, wearing orange jersey",
            "playmaker": f"Football player portrait, {player_name}, green field lighting, creative pose, ball control, photorealistic, 4K, wearing orange jersey",
            "sniper": f"Football player portrait, {player_name}, focused expression, target crosshair overlay, precision pose, photorealistic, 4K, wearing orange jersey",
            "ball_loser": f"Football player portrait, {player_name}, dark grey lighting, embarrassed expression, broken ball nearby, photorealistic, 4K, wearing orange jersey",
            "player": f"Professional football player portrait, {player_name}, neutral stadium lighting, confident pose, photorealistic, 4K, sports photography, wearing orange jersey",
        }
        prompt = prompts.get(card_type, prompts["player"])

        try:
            logger.info("[POLLINATIONS] Generating AI photo for %s (type: %s)", player_name, card_type)
            img_bytes = client.generate_image(prompt, width=1024, height=1536)

            # Save to caches
            self._media_cache[cache_key] = img_bytes
            self._save_photo_cache(player_name, card_type, img_bytes)

            logger.info("[POLLINATIONS] Generated and cached AI photo for %s", player_name)
            return img_bytes
        except Exception as e:
            logger.error("[POLLINATIONS] Failed to generate photo for %s: %s", player_name, e)
            return None

    def _load_template_for_label(self, label: str):
        """Check assets/templates/ first, then auto-generate if not found."""
        card_type = LABEL_TO_TEMPLATE.get(label)
        if not card_type:
            return None

        # 1. Try file-based template
        path = os.path.join(self.assets_dir, "templates", f"{card_type}.png")
        if os.path.exists(path):
            return Image.open(path)

        # 2. Auto-generate template
        if AUTO_TEMPLATES_AVAILABLE and get_template:
            logger.info("[TEMPLATE] Auto-generating %s template for label: %s", card_type, label)
            return get_template(card_type)

        return None

    # ───────────────────────────────────────────
    # PHOTO-ONLY PLAYER CARD (Pollinations AI primary)
    # ───────────────────────────────────────────
    def generate_player_photo_card(self, player, pos, palette_name="gold", label="PLAYER", photo_path=None):
        """Clean photo card. Pollinations AI photo is PRIMARY. No local file fallback."""
        pal = PALETTES.get(palette_name, PALETTES["gold"])
        W, H = CARD_W, CARD_H

        # ─── PREMIUM TEMPLATE CHECK ───
        template = self._load_template_for_label(label)
        if template:
            img = template.resize((W, H), Image.LANCZOS).convert("RGBA")
            draw = ImageDraw.Draw(img)
        else:
            img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")
            img = _glow_circle(img, W // 2, H // 3, 700, pal["glow"], 0.2)
            draw = ImageDraw.Draw(img)

        nickname = getattr(player, "_squad_info", {}).get("nickname", player.name)
        f_name = self._font(90, bold=True)
        draw.text((W // 2, 70), nickname.upper(), fill=pal["text"], font=f_name, anchor="mm")

        f_pos = self._font(40, bold=True)
        pw, ph = 160, 70
        px = W // 2 - pw // 2
        draw.rounded_rectangle([px, 125, px + pw, 125 + ph], radius=15, fill=pal["accent"], outline=pal["accent2"], width=2)
        draw.text((W // 2, 125 + ph // 2), pos.upper(), fill=(10, 10, 10), font=f_pos, anchor="mm")

        photo_max_w = W - 100
        photo_max_h = H - 320

        # ─── POLLINATIONS AI PHOTO IS PRIMARY ───
        card_type = LABEL_TO_TEMPLATE.get(label, "player")
        photo = None

        # Try Pollinations first
        ai_bytes = self._generate_ai_photo(player.name, card_type)
        if ai_bytes:
            try:
                ai_img = Image.open(io.BytesIO(ai_bytes)).convert("RGBA")
                ai_img.thumbnail((photo_max_w, photo_max_h), Image.LANCZOS)
                photo = ai_img
                logger.info("[PHOTO] Using Pollinations AI photo for %s", player.name)
            except Exception as e:
                logger.error("[PHOTO] Failed to load Pollinations image: %s", e)

        # If Pollinations fails, show placeholder with player name
        if photo is None:
            logger.warning("[PHOTO] No AI photo available for %s — showing placeholder", player.name)

        if photo:
            px = (W - photo.width) // 2
            py = 220 + (photo_max_h - photo.height) // 2

            shadow = Image.new("RGBA", (photo.width + 80, photo.height + 80), (0, 0, 0, 0))
            s_draw = ImageDraw.Draw(shadow)
            s_draw.rounded_rectangle([20, 20, photo.width + 60, photo.height + 60], radius=40, fill=(*pal["glow"], 60))
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=40))
            img.paste(shadow, (px - 40, py - 40), shadow)

            mask = Image.new("L", photo.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, photo.width, photo.height], radius=30, fill=255)
            img.paste(photo, (px, py), mask)
        else:
            # Placeholder when Pollinations fails
            f_err = self._font(50, bold=True)
            draw.text((W // 2, H // 2 - 50), f"{player.name}", fill=pal["text"], font=f_err, anchor="mm")
            f_sub = self._font(30)
            draw.text((W // 2, H // 2 + 20), "AI Photo Generation Failed", fill=pal["text_dim"], font=f_sub, anchor="mm")
            f_sub2 = self._font(24)
            draw.text((W // 2, H // 2 + 60), "Check POLLINATIONS_API_KEY", fill=pal["text_dim"], font=f_sub2, anchor="mm")

        f_foot = self._font(28)
        draw.text((W // 2, H - 35), f"RACHAD L3ERGONI • {label}", fill=pal["text_dim"], font=f_foot, anchor="mm")

        img = img.convert("RGB")
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.1)

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf

    # ─── FIXED: all wrappers pass photo_path= (not photo_override=) ───
    def generate_player_card(self, player, pos, division=6, photo_path=None):
        return self.generate_player_photo_card(player, pos, "gold", "PLAYER PROFILE", photo_path=photo_path)

    def generate_mvp_card(self, player, pos, photo_path=None):
        return self.generate_player_photo_card(player, pos, "gold", "MAN OF THE MATCH", photo_path=photo_path)

    def generate_roast_card(self, player, roast_text, pos, photo_path=None):
        return self.generate_player_photo_card(player, pos, "red", "FRAUD DETECTED", photo_path=photo_path)

    def generate_anime_card(self, player, pos, style, label, photo_path=None):
        return self.generate_player_photo_card(player, pos, "purple", "ANIME LEGEND", photo_path=photo_path)

    def generate_beast_card(self, player, pos, photo_path=None):
        return self.generate_player_photo_card(player, pos, "blue", "BEAST MODE", photo_path=photo_path)

    def generate_court_case(self, player, pos, evidence, photo_path=None):
        return self.generate_player_photo_card(player, pos, "red", "COURT CASE", photo_path=photo_path)

    def generate_playmaker_card(self, player, pos, photo_path=None):
        return self.generate_player_photo_card(player, pos, "green", "PLAYMAKER", photo_path=photo_path)

    def generate_sniper_card(self, player, pos, photo_path=None):
        return self.generate_player_photo_card(player, pos, "blue", "SNIPER", photo_path=photo_path)

    def generate_legend_card(self, player, pos, photo_path=None):
        return self.generate_player_photo_card(player, pos, "gold", "CLUB LEGEND", photo_path=photo_path)

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

        # Pollinations AI photo for daily card
        card_type = "mvp" if not is_bad else "fraud"
        ai_bytes = self._generate_ai_photo(player.name, card_type)
        if ai_bytes:
            try:
                photo = Image.open(io.BytesIO(ai_bytes)).convert("RGBA")
                photo.thumbnail((1200, 1200), Image.LANCZOS)
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
            except Exception as e:
                logger.error("[PHOTO] Daily card Pollinations failed: %s", e)

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

    def generate_form_card(self, player, matches_data, num_matches):
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

        row_h = 280
        start_y = 340
        f_label = self._font(32, bold=True)
        f_val = self._font(48, bold=True)
        f_small = self._font(36)

        ratings = []
        for i, md in enumerate(matches_data[:num_matches]):
            y = start_y + i * row_h
            draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + row_h - 20], radius=20, fill=(25, 25, 25, 200), outline=(*pal["accent"], 80), width=2)

            draw.text((MARGIN + 30, y + 15), f"{md['date']} vs {md['opponent']}", fill=pal["text_dim"], font=f_label)

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

    def generate_records_card(self, club, records):
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
