"""card_generator.py — generates UHD cards, returns PIL Image objects."""
import os
from typing import Dict, Any
from PIL import Image

try:
    from phase2_image_gen import UHDImageGenerator
    _UHD_AVAILABLE = True
except ImportError:
    _UHD_AVAILABLE = False


class CardGenerator:
    """Generates player cards. Returns PIL Image objects for bot.py to stream."""

    def __init__(self):
        if _UHD_AVAILABLE:
            self._uhd = UHDImageGenerator(
                assets_dir=os.getenv("ASSETS_DIR", "assets"),
                resolution=(1440, 2160)
            )
        else:
            self._uhd = None

    def _generate(self, ea_name: str, stats: Dict[str, Any], aura: str) -> Image.Image:
        """Internal: generate card and return PIL Image."""
        if self._uhd:
            from player_mapper import get_mapper
            mapper = get_mapper()
            nickname = mapper.get_nickname(ea_name)
            overall = int(stats.get("rating", 7) * 10)
            overall = min(99, max(60, overall))
            position = stats.get("position", "CM")
            tmp_path = f"/tmp/card_{ea_name.replace('/', '_')}.png"
            self._uhd.generate_card(
                player_name=ea_name,
                nickname=nickname,
                overall=overall,
                position=position,
                aura=aura,
                stats=stats,
                output_path=tmp_path
            )
            return Image.open(tmp_path).convert("RGB")
        else:
            return self._fallback_card(ea_name, stats, aura)

    def _fallback_card(self, ea_name: str, stats: Dict[str, Any], aura: str) -> Image.Image:
        """Minimal fallback if UHD generator not available."""
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (800, 1000), (20, 20, 30))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
            small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except:
            font = ImageFont.load_default()
            small = font
        draw.text((50, 50), ea_name, fill=(255, 255, 255), font=font)
        draw.text((50, 120), f"Aura: {aura}", fill=(200, 200, 200), font=small)
        y = 200
        for k, v in stats.items():
            draw.text((50, y), f"{k}: {v}", fill=(180, 180, 180), font=small)
            y += 40
        return img

    def generate_player_card(self, ea_name: str, stats: Dict[str, Any]) -> Image.Image:
        from aura_system import get_aura_system
        aura_sys = get_aura_system()
        tier = aura_sys.determine_tier(stats)
        return self._generate(ea_name, stats, tier.value)

    def generate_mvp_card(self, ea_name: str, stats: Dict[str, Any]) -> Image.Image:
        return self._generate(ea_name, stats, "S-Tier")

    def generate_fraud_card(self, ea_name: str, stats: Dict[str, Any]) -> Image.Image:
        return self._generate(ea_name, stats, "Fraud")

    def generate_ghost_card(self, ea_name: str, stats: Dict[str, Any]) -> Image.Image:
        return self._generate(ea_name, stats, "Ghost")

    def generate_carry_card(self, ea_name: str, stats: Dict[str, Any]) -> Image.Image:
        return self._generate(ea_name, stats, "Carry")


def get_card_generator() -> CardGenerator:
    return CardGenerator()
