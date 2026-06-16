import os
import io
import random
import json
from typing import List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

class ImageGenerator:
    def __init__(self, assets_dir: str = "assets"):
        self.assets_dir = assets_dir
        self.fonts_dir = os.path.join(assets_dir, "fonts")
        self.players_dir = assets_dir  # images are in assets/ root
        self._load_squad_images()
        
        # Colors
        self.GOLD = (255, 215, 0)
        self.SILVER = (192, 192, 192)
        self.BRONZE = (205, 127, 50)
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.RED = (220, 20, 60)
        self.GREEN = (50, 205, 50)
        self.ORANGE = (255, 140, 0)
        self.BLUE = (30, 144, 255)
        self.PURPLE = (147, 0, 211)
        self.CYAN = (0, 255, 255)
        self.DARK_BG = (10, 10, 20)
        
        # Aura colors
        self.AURA_MVP = (255, 215, 0)      # Gold
        self.AURA_FRAUD = (220, 20, 60)    # Red
        self.AURA_CARRY = (147, 0, 211)    # Purple
        self.AURA_GHOST = (128, 128, 128)  # Gray
        self.AURA_BEAST = (0, 191, 255)    # Blue Lock cyan
        self.AURA_PLAYMAKER = (50, 205, 50) # Green
        self.AURA_SNIPER = (255, 69, 0)    # Orange red

    def _load_squad_images(self):
        """Map player names to image paths from squad.json."""
        self.player_images = {}
        try:
            with open("squad.json", "r", encoding="utf-8") as f:
                squad = json.load(f)
            for key, player in squad.items():
                name = player.get("name", key)
                img_path = player.get("image", "")
                if img_path and os.path.exists(img_path):
                    self.player_images[name] = img_path
        except Exception as e:
            print(f"⚠️ Could not load squad images: {e}")

    def _get_font(self, size: int, bold: bool = False):
        candidates = [
            os.path.join(self.fonts_dir, "Cairo-Bold.ttf" if bold else "Cairo-Regular.ttf"),
            os.path.join(self.fonts_dir, "NotoSansArabic-Bold.ttf" if bold else "NotoSansArabic-Regular.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
        return ImageFont.load_default()

    def _load_player_photo(self, name: str, target_size: Tuple[int, int] = (300, 300)) -> Optional[Image.Image]:
        """Load player image from squad.json mapping."""
        path = self.player_images.get(name)
        if not path or not os.path.exists(path):
            return None
        try:
            img = Image.open(path).convert("RGBA")
            img = img.resize(target_size, Image.LANCZOS)
            # Create circular mask
            mask = Image.new("L", target_size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse([0, 0, target_size[0], target_size[1]], fill=255)
            img.putalpha(mask)
            return img
        except Exception as e:
            print(f"⚠️ Failed to load image for {name}: {e}")
            return None

    def _create_gradient_bg(self, size: Tuple[int, int], color1: Tuple, color2: Tuple) -> Image.Image:
        img = Image.new('RGB', size)
        draw = ImageDraw.Draw(img)
        for y in range(size[1]):
            r = int(color1[0] + (color2[0] - color1[0]) * y / size[1])
            g = int(color1[1] + (color2[1] - color1[1]) * y / size[1])
            b = int(color1[2] + (color2[2] - color1[2]) * y / size[1])
            draw.line([(0, y), (size[0], y)], fill=(r, g, b))
        return img

    def _add_aura_effect(self, img: Image.Image, aura_color: Tuple[int, int, int], intensity: float = 1.0):
        """Add glowing aura behind the image."""
        w, h = img.size
        aura = Image.new("RGBA", (w + 100, h + 100), (0, 0, 0, 0))
        draw = ImageDraw.Draw(aura)
        # Multiple layers of glow
        for i in range(5, 0, -1):
            alpha = int(40 * intensity / i)
            offset = i * 8
            draw.ellipse(
                [offset, offset, w + 100 - offset, h + 100 - offset],
                fill=(*aura_color, alpha)
            )
        aura = aura.filter(ImageFilter.GaussianBlur(radius=15))
        # Composite
        base = Image.new("RGBA", (w + 100, h + 100), (0, 0, 0, 0))
        base.paste(aura, (0, 0), aura)
        base.paste(img, (50, 50), img)
        return base

    def _add_speed_lines(self, draw, size: Tuple[int, int], color: Tuple[int, int, int] = (255, 255, 255)):
        """Add anime speed lines radiating from center."""
        cx, cy = size[0] // 2, size[1] // 2
        for angle in range(0, 360, 15):
            import math
            rad = math.radians(angle)
            x2 = cx + int(math.cos(rad) * max(size))
            y2 = cy + int(math.sin(rad) * max(size))
            draw.line([(cx, cy), (x2, y2)], fill=(*color, 30), width=2)

    def _add_manga_text(self, draw, text: str, x: int, y: int, font, text_color: Tuple, glow_color: Tuple):
        """Add text with manga-style outline/glow."""
        # Glow/outline
        for dx in [-3, -2, -1, 1, 2, 3]:
            for dy in [-3, -2, -1, 1, 2, 3]:
                draw.text((x + dx, y + dy), text, fill=glow_color, font=font, anchor="mm")
        draw.text((x, y), text, fill=text_color, font=font, anchor="mm")

    def _add_badge(self, draw, x: int, y: int, text: str, color: Tuple, font):
        """Add a ranking badge."""
        padding = 15
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.rounded_rectangle(
            [x - w//2 - padding, y - h//2 - padding, x + w//2 + padding, y + h//2 + padding],
            radius=10, fill=color, outline=self.WHITE, width=3
        )
        draw.text((x, y), text, fill=self.WHITE, font=font, anchor="mm")

    def _get_aura_color(self, aura_type: str) -> Tuple[int, int, int]:
        return {
            "mvp": self.AURA_MVP,
            "fraud": self.AURA_FRAUD,
            "carry": self.AURA_CARRY,
            "ghost": self.AURA_GHOST,
            "beast": self.AURA_BEAST,
            "playmaker": self.AURA_PLAYMAKER,
            "sniper": self.AURA_SNIPER,
        }.get(aura_type, self.BLUE)

    def generate_anime_card(self, player, position: str = "CM", aura_type: str = "mvp", title: str = "") -> io.BytesIO:
        """Premium anime-style player card with aura and photo."""
        W, H = 800, 1000
        aura_color = self._get_aura_color(aura_type)
        
        # Background
        img = self._create_gradient_bg((W, H), (15, 15, 25), (5, 5, 10))
        draw = ImageDraw.Draw(img)
        
        # Speed lines
        self._add_speed_lines(draw, (W, H), aura_color)
        
        # Title
        font_title = self._get_font(48, bold=True)
        font_name = self._get_font(64, bold=True)
        font_stats = self._get_font(28)
        font_small = self._get_font(22)
        
        # Top title
        if title:
            self._add_manga_text(draw, title, W//2, 60, font_title, self.WHITE, aura_color)
        
        # Player name
        self._add_manga_text(draw, player.name.upper(), W//2, 140, font_name, self.WHITE, aura_color)
        draw.text((W//2, 210), f"#{position.upper()} • RACHAD L3ERGONI", fill=self.SILVER, font=font_small, anchor="mm")
        
        # Player photo with aura
        photo = self._load_player_photo(player.name, (280, 280))
        if photo:
            photo_with_aura = self._add_aura_effect(photo, aura_color, 1.2)
            img.paste(photo_with_aura, (W//2 - 190, 260), photo_with_aura)
        else:
            # Placeholder circle
            draw.ellipse([W//2-140, 280, W//2+140, 560], fill=(40, 40, 50), outline=aura_color, width=5)
            draw.text((W//2, 420), player.name[:2].upper(), fill=self.SILVER, font=font_name, anchor="mm")
        
        # Badge
        badge_text = aura_type.upper()
        self._add_badge(draw, W//2, 580, badge_text, aura_color, font_small)
        
        # Stats section
        y_start = 640
        stats = [
            ("⚡ IMPACT", round(player.impact_score, 1), 100),
            ("🎯 RATING", round(player.rating_pg, 1), 10),
            ("⚽ GOALS", player.goals, 50),
            ("🅰️ ASSISTS", player.assists, 50),
            ("🛡️ TACKLES", player.tackles, 50),
            ("📊 PASS %", round(player.pass_accuracy, 1), 100),
            ("❌ POSS LOST", player.possession_losses, 50),
        ]
        
        for i, (label, val, max_v) in enumerate(stats):
            y = y_start + i * 45
            # Bar background
            draw.rounded_rectangle([100, y, 700, y+35], radius=5, fill=(30, 30, 40))
            # Bar fill
            pct = min(val / max_v, 1.0) if max_v > 0 else 0
            fill_w = int(600 * pct)
            if fill_w > 0:
                bar_color = self.GREEN if pct > 0.7 else self.ORANGE if pct > 0.4 else self.RED
                draw.rounded_rectangle([100, y, 100+fill_w, y+35], radius=5, fill=bar_color)
            # Text
            draw.text((110, y+5), f"{label}: {val}", fill=self.WHITE, font=font_small)
        
        # Footer
        draw.text((W//2, H-40), "RACHAD L3ERGONI • ANIME EDITION", fill=(80, 80, 90), font=font_small, anchor="mm")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    def generate_mvp_card(self, player, position: str = "CM") -> io.BytesIO:
        return self.generate_anime_card(player, position, "mvp", "🔥 MAN OF THE MATCH")

    def generate_fraud_card(self, player, position: str = "CM") -> io.BytesIO:
        return self.generate_anime_card(player, position, "fraud", "🤡 FRAUD DETECTED")

    def generate_carry_card(self, player, position: str = "CM") -> io.BytesIO:
        return self.generate_anime_card(player, position, "carry", "💪 CARRY OF THE DAY")

    def generate_ghost_card(self, player, position: str = "CM") -> io.BytesIO:
        return self.generate_anime_card(player, position, "ghost", "👻 GHOST PLAYER")

    def generate_beast_card(self, player, position: str = "CM") -> io.BytesIO:
        """Blue Lock style beast mode card."""
        return self.generate_anime_card(player, position, "beast", "⚡ BEAST MODE")

    def generate_playmaker_card(self, player, position: str = "CM") -> io.BytesIO:
        return self.generate_anime_card(player, position, "playmaker", "🎨 PLAYMAKER")

    def generate_sniper_card(self, player, position: str = "CM") -> io.BytesIO:
        return self.generate_anime_card(player, position, "sniper", "🎯 SNIPER")

    def generate_court_case(self, player, position: str, evidence: List[str]) -> io.BytesIO:
        """Trial/court case card."""
        W, H = 800, 900
        img = self._create_gradient_bg((W, H), (25, 10, 10), (15, 5, 5))
        draw = ImageDraw.Draw(img)
        
        font_title = self._get_font(42, bold=True)
        font_name = self._get_font(52, bold=True)
        font_evidence = self._get_font(24)
        font_verdict = self._get_font(36, bold=True)
        
        # Header
        draw.text((W//2, 60), "⚖️ COURT OF FOOTBALL", fill=self.GOLD, font=font_title, anchor="mm")
        draw.text((W//2, 120), f"CASE AGAINST {player.name.upper()}", fill=self.RED, font=font_name, anchor="mm")
        
        # Photo
        photo = self._load_player_photo(player.name, (250, 250))
        if photo:
            img.paste(photo, (W//2-125, 170), photo)
        else:
            draw.ellipse([W//2-125, 170, W//2+125, 420], fill=(50, 30, 30), outline=self.RED, width=4)
        
        # Evidence
        y = 460
        draw.text((W//2, y), "📋 EVIDENCE:", fill=self.SILVER, font=font_evidence, anchor="mm")
        y += 50
        for ev in evidence[:6]:
            draw.text((100, y), f"• {ev}", fill=self.WHITE, font=font_evidence)
            y += 40
        
        # Verdict box
        y += 20
        draw.rounded_rectangle([80, y, W-80, y+120], radius=15, fill=(40, 10, 10), outline=self.RED, width=3)
        draw.text((W//2, y+35), "VERDICT:", fill=self.RED, font=font_evidence, anchor="mm")
        draw.text((W//2, y+80), "GUILTY • FRAUD CONFIRMED", fill=self.WHITE, font=font_verdict, anchor="mm")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    def generate_daily_card(self, player, stat_name: str, stat_value, roast_text: str, is_bad: bool = True) -> io.BytesIO:
        """Stat of the Day / Monster of the Day card."""
        W, H = 800, 900
        color1 = (35, 10, 10) if is_bad else (10, 25, 10)
        color2 = (15, 5, 5) if is_bad else (5, 15, 5)
        aura = self.AURA_FRAUD if is_bad else self.AURA_BEAST
        
        img = self._create_gradient_bg((W, H), color1, color2)
        draw = ImageDraw.Draw(img)
        
        font_title = self._get_font(44, bold=True)
        font_stat = self._get_font(72, bold=True)
        font_roast = self._get_font(26)
        font_small = self._get_font(22)
        
        title = "📉 STAT OF THE DAY" if is_bad else "🔥 MONSTER OF THE DAY"
        draw.text((W//2, 60), title, fill=self.GOLD if not is_bad else self.RED, font=font_title, anchor="mm")
        
        # Player
        photo = self._load_player_photo(player.name, (260, 260))
        if photo:
            photo_aura = self._add_aura_effect(photo, aura, 1.0)
            img.paste(photo_aura, (W//2-180, 120), photo_aura)
        
        draw.text((W//2, 420), player.name.upper(), fill=self.WHITE, font=self._get_font(48, bold=True), anchor="mm")
        
        # Big stat
        draw.text((W//2, 520), f"{stat_value}", fill=aura, font=font_stat, anchor="mm")
        draw.text((W//2, 600), stat_name.upper(), fill=self.SILVER, font=font_small, anchor="mm")
        
        # Roast text
        y = 660
        words = roast_text.split()
        lines = []
        line = []
        for word in words:
            line.append(word)
            if len(" ".join(line)) > 45:
                lines.append(" ".join(line[:-1]))
                line = [line[-1]]
        if line:
            lines.append(" ".join(line))
        
        for line in lines[:5]:
            draw.text((W//2, y), line, fill=self.WHITE, font=font_roast, anchor="mm")
            y += 38
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    def generate_leaderboard(self, players, metric: str = "impact_score") -> io.BytesIO:
        """Anime-style leaderboard."""
        count = min(len(players), 10)
        W, H = 900, 650 + count * 70
        img = self._create_gradient_bg((W, H), (12, 12, 22), (8, 8, 15))
        draw = ImageDraw.Draw(img)
        
        font_large = self._get_font(40, bold=True)
        font_medium = self._get_font(26, bold=True)
        font_small = self._get_font(22)
        
        draw.text((W//2, 40), f"🏆 RANKINGS — {metric.upper().replace('_', ' ')}", 
                 fill=self.GOLD, font=font_large, anchor="mm")
        
        headers = ["RANK", "PLAYER", "GAMES", "GOALS", "ASSISTS", "RATING", "VALUE"]
        x_positions = [60, 140, 320, 420, 520, 620, 740]
        
        for i, h in enumerate(headers):
            draw.text((x_positions[i], 110), h, fill=self.SILVER, font=font_medium)
        
        sorted_players = sorted(players, key=lambda p: getattr(p, metric, 0), reverse=True)
        
        for idx, p in enumerate(sorted_players[:10]):
            y = 170 + idx * 60
            color = self.GOLD if idx == 0 else self.SILVER if idx == 1 else self.BRONZE if idx == 2 else self.WHITE
            
            # Rank badge
            rank_text = ["🥇", "🥈", "🥉"][idx] if idx < 3 else f"{idx+1}"
            draw.text((x_positions[0], y), rank_text, fill=color, font=font_medium)
            draw.text((x_positions[1], y), p.name[:14], fill=self.WHITE, font=font_small)
            draw.text((x_positions[2], y), str(p.games), fill=self.SILVER, font=font_small)
            draw.text((x_positions[3], y), str(p.goals), fill=self.SILVER, font=font_small)
            draw.text((x_positions[4], y), str(p.assists), fill=self.SILVER, font=font_small)
            draw.text((x_positions[5], y), str(round(p.rating_pg, 1)), fill=self.SILVER, font=font_small)
            draw.text((x_positions[6], y), str(round(getattr(p, metric, 0), 1)), fill=color, font=font_small)
            
            draw.line([(40, y+45), (W-40, y+45)], fill=(35, 35, 45), width=1)
        
        draw.text((W//2, H-30), "RACHAD L3ERGONI • ANIME EDITION", fill=(70, 70, 80), font=font_small, anchor="mm")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    def generate_match_report(self, club, motm) -> io.BytesIO:
        W, H = 900, 750
        img = self._create_gradient_bg((W, H), (18, 22, 32), (8, 12, 18))
        draw = ImageDraw.Draw(img)
        
        font_large = self._get_font(44, bold=True)
        font_medium = self._get_font(30, bold=True)
        font_small = self._get_font(22)
        
        draw.text((W//2, 50), club.club_name, fill=self.WHITE, font=font_large, anchor="mm")
        draw.text((W//2, 110), f"Division {club.division} • Skill Rating {club.skill_rating}", 
                 fill=self.SILVER, font=font_small, anchor="mm")
        
        draw.text((W//2, 180), f"{club.wins}W — {club.losses}L — {club.draws}D", 
                 fill=self.GOLD, font=font_medium, anchor="mm")
        
        total = club.wins + club.losses + club.draws
        if total > 0:
            win_pct = club.wins / total
            draw.rectangle([150, 240, 750, 280], fill=(35, 35, 45))
            draw.rectangle([150, 240, 150 + int(600 * win_pct), 280], fill=self.GREEN)
            draw.text((W//2, 260), f"Win Rate: {round(win_pct*100, 1)}%", fill=self.WHITE, font=font_small, anchor="mm")
        
        # MVP section
        draw.text((W//2, 330), "👑 SEASON MVP", fill=self.GOLD, font=font_medium, anchor="mm")
        photo = self._load_player_photo(motm.name, (200, 200))
        if photo:
            img.paste(photo, (W//2-100, 370), photo)
        
        draw.text((W//2, 600), motm.name, fill=self.WHITE, font=font_large, anchor="mm")
        draw.text((W//2, 660), f"Impact: {round(motm.impact_score, 1)} • Goals: {motm.goals} • Assists: {motm.assists}", 
                 fill=self.SILVER, font=font_small, anchor="mm")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    def generate_roast_card(self, player, roast_text: str, position: str = "CM") -> io.BytesIO:
        W, H = 800, 700
        img = self._create_gradient_bg((W, H), (30, 10, 10), (15, 5, 5))
        draw = ImageDraw.Draw(img)
        
        font_large = self._get_font(40, bold=True)
        font_medium = self._get_font(26)
        font_roast = self._get_font(24)
        
        draw.text((W//2, 50), "🔥 ROAST REPORT", fill=self.RED, font=font_large, anchor="mm")
        draw.text((W//2, 110), f"{player.name} • {position.upper()}", fill=self.WHITE, font=font_medium, anchor="mm")
        
        photo = self._load_player_photo(player.name, (220, 220))
        if photo:
            img.paste(photo, (W//2-110, 150), photo)
        
        # Stats
        stats = [
            f"Rating: {round(player.rating_pg, 1)}",
            f"Goals: {player.goals}",
            f"Assists: {player.assists}",
            f"Pass: {round(player.pass_accuracy, 1)}%",
            f"Poss Lost: {player.possession_losses}",
            f"Impact: {round(player.impact_score, 1)}",
            f"Throwing: {round(player.throwing_score, 1)}",
        ]
        y = 400
        for s in stats:
            draw.text((W//2, y), s, fill=self.SILVER, font=font_medium, anchor="mm")
            y += 32
        
        # Roast box
        y += 10
        draw.rounded_rectangle([60, y, W-60, H-60], radius=15, fill=(25, 8, 8), outline=self.RED, width=2)
        
        words = roast_text.split()
        lines = []
        line = []
        for word in words:
            line.append(word)
            if len(" ".join(line)) > 50:
                lines.append(" ".join(line[:-1]))
                line = [line[-1]]
        if line:
            lines.append(" ".join(line))
        
        y += 30
        for line in lines[:6]:
            draw.text((W//2, y), line, fill=self.WHITE, font=font_roast, anchor="mm")
            y += 32
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
