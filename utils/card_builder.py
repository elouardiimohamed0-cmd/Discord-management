"""Premium card builder — composites template + photo + stats. Cached forever."""
import os
import io
import hashlib
import logging
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from typing import Optional
from models import PlayerStats

logger = logging.getLogger("rachad_bot.card_builder")

class CardBuilder:
    CARD_W = 1440
    CARD_H = 2160

    def __init__(self, assets_dir: str = "assets", templates_dir: str = "assets/templates",
                 cache_dir: str = "cache/cards"):
        self.assets_dir = assets_dir
        self.templates_dir = templates_dir
        self.cache_dir = cache_dir
        os.makedirs(self.templates_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
        self._fonts = {}

    def _font(self, size: int, bold: bool = False):
        key = (size, bold)
        if key not in self._fonts:
            candidates = [
                f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
                f"/usr/share/fonts/truetype/liberation/LiberationSans{'-Bold' if bold else 'Regular'}.ttf",
                f"/usr/share/fonts/truetype/noto/NotoSans{'-Bold' if bold else '-Regular'}.ttf",
            ]
            for path in candidates:
                if path and os.path.exists(path):
                    try:
                        self._fonts[key] = ImageFont.truetype(path, size)
                        break
                    except Exception:
                        pass
            else:
                self._fonts[key] = ImageFont.load_default()
        return self._fonts[key]

    def _load_template(self, card_type: str) -> Optional[Image.Image]:
        path = os.path.join(self.templates_dir, f"{card_type}.png")
        if os.path.exists(path):
            return Image.open(path).convert("RGBA")
        return None

    def _load_player_photo(self, name: str, photo_path: Optional[str] = None, max_size=(1200, 1200)):
        def _try_load(path):
            if not path or not os.path.exists(path):
                return None
            try:
                img = Image.open(path).convert("RGBA")
                img.thumbnail(max_size, Image.LANCZOS)
                return img
            except Exception:
                return None

        if photo_path:
            img = _try_load(photo_path)
            if img:
                return img

        clean = name.replace(" ", "_").lower()
        upper = name.upper()
        title = name.title()
        candidates = [
            os.path.join(self.assets_dir, f"{name}.png"), os.path.join(self.assets_dir, f"{name}.jpg"),
            os.path.join(self.assets_dir, f"{clean}.png"), os.path.join(self.assets_dir, f"{clean}.jpg"),
            os.path.join(self.assets_dir, f"{upper}.png"), os.path.join(self.assets_dir, f"{upper}.jpg"),
            os.path.join(self.assets_dir, f"{title}.png"), os.path.join(self.assets_dir, f"{title}.jpg"),
        ]
        for path in candidates:
            img = _try_load(path)
            if img:
                return img
        return None

    def _cache_key(self, player: PlayerStats, card_type: str, match_id: str = "") -> str:
        data = f"{player.name}:{card_type}:{match_id}:{player.games}:{player.goals}:{player.assists}:{round(player.rating_pg, 2)}:{round(player.impact_score, 2)}"
        return hashlib.md5(data.encode()).hexdigest() + ".png"

    def build_card(self, player: PlayerStats, card_type: str, label: str,
                   match_id: str = "", photo_path: Optional[str] = None,
                   accent_color: tuple = (255, 215, 0)) -> io.BytesIO:
        """Build a premium card. Uses cache if available."""
        cache_key = self._cache_key(player, card_type, match_id)
        cache_path = os.path.join(self.cache_dir, cache_key)
        if os.path.exists(cache_path):
            with open(cache_path, "rb") as f:
                return io.BytesIO(f.read())

        W, H = self.CARD_W, self.CARD_H

        # 1. Load template or fallback to gradient
        template = self._load_template(card_type)
        if template:
            img = template.resize((W, H), Image.LANCZOS).convert("RGBA")
        else:
            from image_gen import _gradient_bg, PALETTES
            palette_map = {
                "mvp": "gold", "fraud": "red", "ghost": "purple",
                "carry": "blue", "court": "red", "playmaker": "green",
                "sniper": "blue", "ball_loser": "red", "match": "dark"
            }
            pal = PALETTES.get(palette_map.get(card_type, "gold"))
            img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")

        # 2. Vignette overlay
        vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        v_draw = ImageDraw.Draw(vignette)
        for i in range(150):
            alpha = int(50 * (1 - i / 150))
            v_draw.rectangle([i, i, W - i, H - i], outline=(0, 0, 0, alpha))
        img = Image.alpha_composite(img, vignette)

        draw = ImageDraw.Draw(img)

        # 3. Top label
        f_label = self._font(48, bold=True)
        draw.text((W // 2, 60), label.upper(), fill=accent_color, font=f_label, anchor="mm")

        # 4. Player name
        nickname = getattr(player, "_squad_info", {}).get("nickname", player.name)
        f_name = self._font(100, bold=True)
        draw.text((W // 2, 140), nickname.upper(), fill=(255, 255, 255), font=f_name, anchor="mm")

        # 5. Position badge
        position = getattr(player, "_squad_info", {}).get("position", "CM")
        f_pos = self._font(36, bold=True)
        bw, bh = 180, 70
        bx = W // 2 - bw // 2
        by = 220
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=15, fill=accent_color, outline=(255, 255, 255, 180), width=2)
        draw.text((W // 2, by + bh // 2), position.upper(), fill=(10, 10, 10), font=f_pos, anchor="mm")

        # 6. Player photo
        photo = self._load_player_photo(player.name, photo_path)
        photo_y = 340
        if photo:
            pw, ph = photo.width, photo.height
            px = (W - pw) // 2
            shadow = Image.new("RGBA", (pw + 80, ph + 80), (0, 0, 0, 0))
            s_draw = ImageDraw.Draw(shadow)
            s_draw.rounded_rectangle([20, 20, pw + 60, ph + 60], radius=40, fill=(*accent_color, 60))
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=40))
            img.paste(shadow, (px - 40, photo_y - 40), shadow)
            mask = Image.new("L", photo.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw, ph], radius=30, fill=255)
            img.paste(photo, (px, photo_y), mask)

        # 7. Stats grid
        stats_y = photo_y + (photo.height if photo else 800) + 100
        stats = [
            ("GAMES", str(player.games)), ("GOALS", str(player.goals)),
            ("ASSISTS", str(player.assists)), ("RATING", f"{round(player.rating_pg, 1)}"),
            ("PASS %", f"{round(player.pass_accuracy, 1)}%"), ("WIN %", f"{round(player.win_rate, 1)}%"),
            ("IMPACT", str(round(player.impact_score, 1))), ("POS LOST", str(player.possession_losses)),
        ]
        box_w = (W - 200) // 2
        box_h = 160
        gap_x, gap_y = 40, 30
        start_x = 80

        for i, (sl, sv) in enumerate(stats):
            col, row = i % 2, i // 2
            x = start_x + col * (box_w + gap_x)
            y = stats_y + row * (box_h + gap_y)
            box = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
            b_draw = ImageDraw.Draw(box)
            b_draw.rounded_rectangle([0, 0, box_w, box_h], radius=20, fill=(0, 0, 0, 130), outline=(*accent_color, 160), width=2)
            img.paste(box, (x, y), box)
            f_sl = self._font(30, bold=True)
            f_sv = self._font(56, bold=True)
            draw.text((x + 20, y + 15), sl, fill=(180, 180, 180), font=f_sl)
            draw.text((x + 20, y + 65), sv, fill=(255, 255, 255), font=f_sv)

        # 8. Footer
        f_foot = self._font(28)
        draw.text((W // 2, H - 50), "RACHAD L3ERGONI • PREMIUM", fill=(150, 150, 150), font=f_foot, anchor="mm")

        # 9. Finalize
        img = img.convert("RGB")
        img = ImageEnhance.Sharpness(img).enhance(1.1)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)

        # 10. Cache
        with open(cache_path, "wb") as f:
            f.write(buf.getvalue())
        buf.seek(0)
        logger.info("[CardBuilder] Built %s / %s", player.name, card_type)
        return buf
