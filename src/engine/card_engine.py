from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from src.core.config import Settings
from src.core.logging import get_logger
from src.domain.models import PlayerIdentity, PlayerMatchStats
from src.squad.registry import SquadRegistry

logger = get_logger(__name__)

CARD_WIDTH = 1440
CARD_HEIGHT = 2160


class CardEngine:
    def __init__(self, settings: Settings, squad: SquadRegistry):
        self.settings = settings
        self.squad = squad
        self.templates_dir = settings.templates_dir
        self.assets_dir = settings.assets_dir
        self.cache_dir = settings.cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_templates()
        self._load_fonts()

    def _load_fonts(self) -> None:
        self.font_title = self._get_font(72)
        self.font_name = self._get_font(96)
        self.font_stat = self._get_font(48)
        self.font_small = self._get_font(36)
        self.font_tiny = self._get_font(28)

    def _get_font(self, size: int):
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "arial.ttf",
        ]
        for c in candidates:
            if os.path.exists(c):
                return ImageFont.truetype(c, size)
        return ImageFont.load_default()

    def _ensure_templates(self) -> None:
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        types = ["mvp", "fraud", "ghost", "carry", "court", "playmaker", "sniper", "ball_loser", "legend"]
        for t in types:
            path = self.templates_dir / f"{t}_bg.png"
            if not path.exists():
                self._generate_template_bg(t, path)

    def _generate_template_bg(self, card_type: str, path: Path) -> None:
        colors = {
            "mvp": (255, 215, 0),
            "fraud": (220, 20, 60),
            "ghost": (138, 43, 226),
            "carry": (0, 191, 255),
            "court": (139, 69, 19),
            "playmaker": (50, 205, 50),
            "sniper": (255, 69, 0),
            "ball_loser": (128, 128, 128),
            "legend": (255, 223, 0),
        }
        base = colors.get(card_type, (30, 30, 30))
        img = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), (18, 18, 22))
        draw = ImageDraw.Draw(img)
        for y in range(CARD_HEIGHT):
            r = int(base[0] * (1 - y / CARD_HEIGHT) + 18 * (y / CARD_HEIGHT))
            g = int(base[1] * (1 - y / CARD_HEIGHT) + 18 * (y / CARD_HEIGHT))
            b = int(base[2] * (1 - y / CARD_HEIGHT) + 22 * (y / CARD_HEIGHT))
            draw.line([(0, y), (CARD_WIDTH, y)], fill=(r, g, b))
        for i in range(0, CARD_WIDTH, 80):
            for j in range(0, CARD_HEIGHT, 70):
                draw.polygon(
                    [(i + 20, j), (i + 60, j), (i + 80, j + 35), (i + 60, j + 70), (i + 20, j + 70), (i, j + 35)],
                    outline=(255, 255, 255, 8),
                )
        img.save(path)
        logger.info("Generated template: %s", path)

    def _load_player_image(self, identity: PlayerIdentity) -> Image.Image:
        if identity.image:
            img_path = self.assets_dir / identity.image
            if img_path.exists():
                return Image.open(img_path).convert("RGBA")
        return Image.new("RGBA", (600, 800), (40, 40, 45, 255))

    def _create_base_card(self, card_type: str, title: str, color: tuple):
        bg_path = self.templates_dir / f"{card_type}_bg.png"
        if bg_path.exists():
            card = Image.open(bg_path).convert("RGBA").copy()
        else:
            card = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), (18, 18, 22, 255))
        draw = ImageDraw.Draw(card)
        draw.rectangle([(0, 0), (CARD_WIDTH, 140)], fill=(*color, 220))
        draw.text((CARD_WIDTH // 2, 70), title, font=self.font_title, fill=(255, 255, 255), anchor="mm")
        draw.rectangle([(0, CARD_HEIGHT - 100), (CARD_WIDTH, CARD_HEIGHT)], fill=(0, 0, 0, 180))
        return card, draw

    def _paste_player_image(self, card: Image.Image, identity: PlayerIdentity, x: int = 720, y: int = 900) -> None:
        player_img = self._load_player_image(identity)
        player_img = player_img.resize((500, 667), Image.LANCZOS)
        glow = Image.new("RGBA", (540, 707), (255, 255, 255, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.ellipse([(10, 10), (530, 697)], fill=(255, 255, 255, 40))
        card.paste(glow, (x - 270, y - 333), glow)
        card.paste(player_img, (x - 250, y - 333), player_img)

    def _draw_stats_block(self, draw: ImageDraw.Draw, player: PlayerMatchStats, x: int, y: int) -> None:
        stats = [
            ("Rating", f"{player.rating:.1f}"),
            ("Goals", str(player.goals)),
            ("Assists", str(player.assists)),
            ("Shots", str(player.shots)),
            ("Pass%", f"{player.pass_accuracy:.0f}%"),
            ("Tackles", str(player.tackles)),
            ("Losses", str(player.possession_losses)),
        ]
        for i, (label, value) in enumerate(stats):
            row_y = y + i * 80
            draw.rounded_rectangle([(x, row_y), (x + 400, row_y + 70)], radius=12, fill=(0, 0, 0, 160))
            draw.text((x + 20, row_y + 35), label, font=self.font_small, fill=(200, 200, 200), anchor="lm")
            draw.text((x + 380, row_y + 35), value, font=self.font_stat, fill=(255, 255, 255), anchor="rm")

    def _save_card(self, card: Image.Image, name: str) -> Path:
        path = self.cache_dir / f"{name}.png"
        card.convert("RGB").save(path, quality=95)
        return path

    def generate_mvp_card(self, player: PlayerMatchStats, identity: PlayerIdentity) -> Path:
        card, draw = self._create_base_card("mvp", "MVP OF THE MATCH", (255, 215, 0))
        self._paste_player_image(card, identity, 720, 700)
        draw.text((720, 1100), identity.nickname, font=self.font_name, fill=(255, 255, 255), anchor="mm")
        draw.text((720, 1200), identity.personality or "Unknown Style", font=self.font_stat, fill=(255, 215, 0), anchor="mm")
        self._draw_stats_block(draw, player, 520, 1300)
        return self._save_card(card, f"mvp_{identity.ea_id}_{player.match_id}")

    def generate_fraud_card(self, player: PlayerMatchStats, identity: PlayerIdentity) -> Path:
        card, draw = self._create_base_card("fraud", "FRAUD ALERT", (220, 20, 60))
        self._paste_player_image(card, identity, 720, 700)
        draw.text((720, 1100), identity.nickname, font=self.font_name, fill=(255, 255, 255), anchor="mm")
        draw.text((720, 1200), "VERDICT: GUILTY", font=self.font_stat, fill=(220, 20, 60), anchor="mm")
        self._draw_stats_block(draw, player, 520, 1300)
        draw.text((720, 1600), "FRAUD", font=self._get_font(140), fill=(220, 20, 60, 120), anchor="mm")
        return self._save_card(card, f"fraud_{identity.ea_id}_{player.match_id}")

    def generate_ghost_card(self, player: PlayerMatchStats, identity: PlayerIdentity) -> Path:
        card, draw = self._create_base_card("ghost", "GHOST MODE", (138, 43, 226))
        self._paste_player_image(card, identity, 720, 700)
        draw.text((720, 1100), identity.nickname, font=self.font_name, fill=(255, 255, 255), anchor="mm")
        draw.text((720, 1200), f"Minutes: {player.minutes}", font=self.font_stat, fill=(138, 43, 226), anchor="mm")
        self._draw_stats_block(draw, player, 520, 1300)
        return self._save_card(card, f"ghost_{identity.ea_id}_{player.match_id}")

    def generate_carry_card(self, player: PlayerMatchStats, identity: PlayerIdentity) -> Path:
        card, draw = self._create_base_card("carry", "CARRY DETECTED", (0, 191, 255))
        self._paste_player_image(card, identity, 720, 700)
        draw.text((720, 1100), identity.nickname, font=self.font_name, fill=(255, 255, 255), anchor="mm")
        draw.text((720, 1200), "TEAM ON HIS BACK", font=self.font_stat, fill=(0, 191, 255), anchor="mm")
        self._draw_stats_block(draw, player, 520, 1300)
        return self._save_card(card, f"carry_{identity.ea_id}_{player.match_id}")

    def generate_court_card(self, player: PlayerMatchStats, identity: PlayerIdentity) -> Path:
        card, draw = self._create_base_card("court", "TRIBUNAL", (139, 69, 19))
        self._paste_player_image(card, identity, 720, 700)
        draw.text((720, 1100), identity.nickname, font=self.font_name, fill=(255, 255, 255), anchor="mm")
        draw.text((720, 1200), "CASE FILE #001", font=self.font_stat, fill=(139, 69, 19), anchor="mm")
        self._draw_stats_block(draw, player, 520, 1300)
        draw.text((720, 1650), "GUILTY", font=self._get_font(120), fill=(139, 69, 19, 150), anchor="mm")
        return self._save_card(card, f"court_{identity.ea_id}_{player.match_id}")

    def generate_playmaker_card(self, player: PlayerMatchStats, identity: PlayerIdentity) -> Path:
        card, draw = self._create_base_card("playmaker", "PLAYMAKER", (50, 205, 50))
        self._paste_player_image(card, identity, 720, 700)
        draw.text((720, 1100), identity.nickname, font=self.font_name, fill=(255, 255, 255), anchor="mm")
        draw.text((720, 1200), "VISION 99", font=self.font_stat, fill=(50, 205, 50), anchor="mm")
        self._draw_stats_block(draw, player, 520, 1300)
        return self._save_card(card, f"playmaker_{identity.ea_id}_{player.match_id}")

    def generate_sniper_card(self, player: PlayerMatchStats, identity: PlayerIdentity) -> Path:
        card, draw = self._create_base_card("sniper", "SNIPER", (255, 69, 0))
        self._paste_player_image(card, identity, 720, 700)
        draw.text((720, 1100), identity.nickname, font=self.font_name, fill=(255, 255, 255), anchor="mm")
        eff = (player.goals / max(player.shots, 1)) * 100
        draw.text((720, 1200), f"Efficiency: {eff:.0f}%", font=self.font_stat, fill=(255, 69, 0), anchor="mm")
        self._draw_stats_block(draw, player, 520, 1300)
        return self._save_card(card, f"sniper_{identity.ea_id}_{player.match_id}")

    def generate_ball_loser_card(self, player: PlayerMatchStats, identity: PlayerIdentity) -> Path:
        card, draw = self._create_base_card("ball_loser", "BALL LOSER", (128, 128, 128))
        self._paste_player_image(card, identity, 720, 700)
        draw.text((720, 1100), identity.nickname, font=self.font_name, fill=(255, 255, 255), anchor="mm")
        draw.text((720, 1200), f"Lost: {player.possession_losses}x", font=self.font_stat, fill=(128, 128, 128), anchor="mm")
        self._draw_stats_block(draw, player, 520, 1300)
        return self._save_card(card, f"ball_loser_{identity.ea_id}_{player.match_id}")

    def generate_legend_card(self, identity: PlayerIdentity) -> Path:
        card, draw = self._create_base_card("legend", "HALL OF FAME", (255, 223, 0))
        self._paste_player_image(card, identity, 720, 700)
        draw.text((720, 1100), identity.nickname, font=self.font_name, fill=(255, 255, 255), anchor="mm")
        draw.text((720, 1200), identity.personality or "Legend", font=self.font_stat, fill=(255, 223, 0), anchor="mm")
        if identity.raw.get("bio"):
            draw.text((720, 1300), identity.raw["bio"][:80], font=self.font_small, fill=(200, 200, 200), anchor="mm")
        return self._save_card(card, f"legend_{identity.ea_id}")

    def generate_compare_card(self, p1: PlayerMatchStats, id1: PlayerIdentity, p2: PlayerMatchStats, id2: PlayerIdentity) -> Path:
        card = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), (18, 18, 22, 255))
        draw = ImageDraw.Draw(card)
        draw.rectangle([(0, 0), (CARD_WIDTH // 2, CARD_HEIGHT)], fill=(30, 30, 40, 255))
        draw.rectangle([(CARD_WIDTH // 2, 0), (CARD_WIDTH, CARD_HEIGHT)], fill=(40, 30, 30, 255))
        draw.text((CARD_WIDTH // 2, 80), "VS", font=self._get_font(100), fill=(255, 255, 255), anchor="mm")
        self._paste_player_image(card, id1, CARD_WIDTH // 4, 600)
        draw.text((CARD_WIDTH // 4, 1000), id1.nickname, font=self.font_name, fill=(255, 255, 255), anchor="mm")
        self._draw_stats_block(draw, p1, 120, 1100)
        self._paste_player_image(card, id2, CARD_WIDTH * 3 // 4, 600)
        draw.text((CARD_WIDTH * 3 // 4, 1000), id2.nickname, font=self.font_name, fill=(255, 255, 255), anchor="mm")
        self._draw_stats_block(draw, p2, CARD_WIDTH // 2 + 120, 1100)
        return self._save_card(card, f"compare_{id1.ea_id}_{id2.ea_id}")

    def generate_leaderboard_card(self, title: str, rows: list, metric: str) -> Path:
        card, draw = self._create_base_card("mvp", title.upper(), (255, 215, 0))
        y = 300
        for i, row in enumerate(rows[:10]):
            name = row.get("display_name", "Unknown")
            value = row.get("value", 0)
            matches = row.get("matches", 0)
            color = (255, 215, 0) if i == 0 else (200, 200, 200) if i == 1 else (205, 127, 50) if i == 2 else (150, 150, 150)
            draw.rounded_rectangle([(200, y), (CARD_WIDTH - 200, y + 80)], radius=10, fill=(0, 0, 0, 160))
            draw.text((240, y + 40), f"{i+1}.", font=self.font_stat, fill=color, anchor="lm")
            draw.text((350, y + 40), name, font=self.font_stat, fill=(255, 255, 255), anchor="lm")
            draw.text((CARD_WIDTH - 240, y + 40), f"{value:.1f} ({matches}M)", font=self.font_stat, fill=color, anchor="rm")
            y += 100
        return self._save_card(card, f"leaderboard_{metric}")
