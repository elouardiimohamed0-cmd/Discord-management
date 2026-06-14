"""
Rachad L3ERGONI Bot — Image Generator v3
Premium dark cards. FUT/Futbin inspired. Pure PIL.
"""

import io
import math
import os
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter


class ImageGenerator:
    def __init__(self, assets_path: str = "assets"):
        self.assets_path = assets_path
        self._photo_cache: Dict[str, Image.Image] = {}
        self._fonts = self._load_fonts()

    def _load_fonts(self) -> Dict[str, ImageFont.FreeTypeFont]:
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arial.ttf",
        ]
        bold = regular = None
        for p in paths:
            if os.path.exists(p):
                try:
                    if "Bold" in p or "-Bold" in p:
                        bold = ImageFont.truetype(p, 36) if bold is None else bold
                    else:
                        regular = ImageFont.truetype(p, 18) if regular is None else regular
                except Exception:
                    pass
        default = ImageFont.load_default()
        fonts = {
            "header": bold or default,
            "subheader": bold or default,
            "body": regular or default,
            "small": regular or default,
            "rating": bold or default,
        }
        if bold:
            try:
                fonts["subheader"] = ImageFont.truetype(bold.path, 26)
                fonts["rating"] = ImageFont.truetype(bold.path, 52)
            except Exception:
                pass
        if regular:
            try:
                fonts["small"] = ImageFont.truetype(regular.path, 14)
                fonts["body"] = ImageFont.truetype(regular.path, 20)
            except Exception:
                pass
        return fonts

    def _gradient(self, w: int, h: int, colors: List[Tuple[int, int, int]]) -> Image.Image:
        img = Image.new("RGB", (w, h))
        draw = ImageDraw.Draw(img)
        for y in range(h):
            ratio = y / h
            r = int(colors[0][0] * (1 - ratio) + colors[-1][0] * ratio)
            g = int(colors[0][1] * (1 - ratio) + colors[-1][1] * ratio)
            b = int(colors[0][2] * (1 - ratio) + colors[-1][2] * ratio)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        return img

    def _glow_bar(self, draw: ImageDraw.Draw, x: int, y: int, w: int, h: int, val: float, maxv: float, color: Tuple[int, int, int]):
        ratio = min(val / max(maxv, 1), 1.0)
        fw = int(w * ratio)
        draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=(35, 35, 45))
        if fw > 0:
            draw.rounded_rectangle([x, y, x + fw, y + h], radius=h // 2, fill=color)
        if fw > 2:
            glow = (min(color[0] + 60, 255), min(color[1] + 60, 255), min(color[2] + 60, 255))
            draw.line([(x, y), (x + fw, y)], fill=glow, width=2)

    def _hexagon(self, draw: ImageDraw.Draw, cx: int, cy: int, size: int, color: Tuple[int, int, int], text: str):
        pts = []
        for i in range(6):
            ang = math.pi * (60 * i - 30) / 180
            pts.append((cx + size * 0.5 * (1 + 0.9 * math.cos(ang)), cy + size * 0.5 * (1 + 0.9 * math.sin(ang))))
        draw.polygon(pts, fill=color, outline=(255, 255, 255))
        bbox = draw.textbbox((0, 0), text, font=self._fonts["rating"])
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((cx - tw // 2, cy - th // 2), text, fill=(255, 255, 255), font=self._fonts["rating"])

    def _load_photo(self, name: str) -> Optional[Image.Image]:
        if name in self._photo_cache:
            return self._photo_cache[name]
        variants = {name, name.lower(), name.upper(), name.replace(" ", "_"), name.replace(" ", ""), name.replace(" ", "-")}
        for ext in [".png", ".jpg", ".jpeg", ".webp"]:
            for v in variants:
                path = os.path.join(self.assets_path, f"{v}{ext}")
                if os.path.exists(path):
                    try:
                        img = Image.open(path).convert("RGBA")
                        self._photo_cache[name] = img
                        return img
                    except Exception:
                        continue
        return None

    def _round_mask(self, img: Image.Image, r: int) -> Image.Image:
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width, img.height], radius=r, fill=255)
        out = img.copy()
        if out.mode != "RGBA":
            out = out.convert("RGBA")
        out.putalpha(mask)
        return out

    def _tier_colors(self, rating: float) -> Tuple[List[Tuple[int, int, int]], str, Tuple[int, int, int]]:
        if rating >= 8.5:
            return ([(255, 215, 0), (255, 165, 0), (200, 120, 0)], "ELITE", (255, 215, 0))
        elif rating >= 7.5:
            return ([(0, 255, 255), (0, 200, 255), (80, 140, 255)], "PRO", (0, 220, 255))
        elif rating >= 6.5:
            return ([(180, 180, 180), (140, 140, 140), (100, 100, 100)], "STANDARD", (180, 180, 180))
        else:
            return ([(180, 50, 50), (140, 40, 40), (100, 30, 30)], "BRONZE", (200, 60, 60))

    def _pos_color(self, pos: str) -> Tuple[int, int, int]:
        pmap = {
            "GK": (0, 150, 255), "CB": (0, 200, 100), "LB": (0, 200, 100), "RB": (0, 200, 100),
            "CDM": (0, 180, 100), "CM": (255, 200, 0), "CAM": (255, 180, 0),
            "LM": (255, 200, 0), "RM": (255, 200, 0),
            "LW": (255, 100, 100), "RW": (255, 100, 100), "ST": (255, 80, 80),
        }
        return pmap.get(pos.upper(), (200, 200, 200))

    def generate_player_card(self, name: str, stats: dict, info: dict) -> Image.Image:
        w, h = 900, 1100
        rating = stats.get("rating", 6.0)
        grad, tier, accent = self._tier_colors(rating)
        card = self._gradient(w, h, grad)
        draw = ImageDraw.Draw(card)
        pos = info.get("position", "CM").upper()
        pcolor = self._pos_color(pos)

        # Photo
        photo = self._load_photo(name)
        if photo:
            ps = 320
            photo = photo.resize((ps, ps), Image.Resampling.LANCZOS)
            photo = self._round_mask(photo, 40)
            px = (w - ps) // 2
            py = 70
            card.paste(photo, (px, py), photo)

        # Name / Position / Tier
        nick = info.get("nickname", name)
        draw.text((w // 2, 430), nick, fill=(255, 255, 255), font=self._fonts["header"], anchor="mm")
        draw.text((w // 2, 480), f"{pos} | {tier}", fill=pcolor, font=self._fonts["subheader"], anchor="mm")

        # Hex rating
        self._hexagon(draw, w // 2, 560, 140, pcolor, f"{rating:.1f}")

        # Stat bars
        bars = [
            ("Goals", stats.get("goals", 0), 20, (255, 100, 100)),
            ("Assists", stats.get("assists", 0), 15, (100, 255, 100)),
            ("Pass Acc", stats.get("pass_accuracy", 0), 100, (100, 200, 255)),
            ("Tackles", stats.get("tackles", 0), 20, (255, 200, 100)),
            ("Impact", stats.get("impact_score", 0), 50, accent),
        ]
        by = 720
        for label, value, maxv, color in bars:
            draw.text((60, by), label, fill=(255, 255, 255), font=self._fonts["body"])
            self._glow_bar(draw, 240, by + 5, 580, 28, value, maxv, color)
            draw.text((840, by), str(value), fill=(255, 255, 255), font=self._fonts["body"])
            by += 60

        # Footer
        impact = stats.get("impact_score", 0)
        draw.text((w // 2, 1040), f"Impact Score: {impact:.1f}", fill=(255, 255, 255), font=self._fonts["subheader"], anchor="mm")
        return card

    def generate_motm_card(self, name: str, stats: dict, info: dict) -> Image.Image:
        w, h = 900, 1100
        grad = [(255, 215, 0), (255, 165, 0), (200, 120, 0)]
        card = self._gradient(w, h, grad)
        draw = ImageDraw.Draw(card)

        draw.text((w // 2, 80), "👑 MOTM", fill=(255, 215, 0), font=self._fonts["header"], anchor="mm")

        photo = self._load_photo(name)
        if photo:
            ps = 300
            photo = photo.resize((ps, ps), Image.Resampling.LANCZOS)
            photo = self._round_mask(photo, 40)
            card.paste(photo, ((w - ps) // 2, 160), photo)

        nick = info.get("nickname", name)
        draw.text((w // 2, 520), nick, fill=(255, 255, 255), font=self._fonts["header"], anchor="mm")

        rating = stats.get("rating", 6.0)
        self._hexagon(draw, w // 2, 600, 140, (255, 215, 0), f"{rating:.1f}")

        draw.text((w // 2, 780), f"Goals: {stats.get('goals', 0)}", fill=(255, 255, 255), font=self._fonts["subheader"], anchor="mm")
        draw.text((w // 2, 830), f"Assists: {stats.get('assists', 0)}", fill=(255, 255, 255), font=self._fonts["subheader"], anchor="mm")
        draw.text((w // 2, 880), f"Impact: {stats.get('impact_score', 0):.1f}", fill=(255, 255, 255), font=self._fonts["subheader"], anchor="mm")
        return card

    def generate_match_report_card(self, match_data: dict) -> Image.Image:
        w, h = 900, 700
        result = match_data.get("result", "draw")
        colors = {
            "win": [(0, 150, 50), (0, 100, 30)],
            "loss": [(150, 30, 30), (100, 20, 20)],
            "draw": [(150, 150, 50), (100, 100, 30)],
        }.get(result, [(80, 80, 80), (50, 50, 50)])
        card = self._gradient(w, h, colors)
        draw = ImageDraw.Draw(card)

        tg = match_data.get("team_goals", 0)
        og = match_data.get("opponent_goals", 0)
        opp = match_data.get("opponent", "Unknown")

        draw.text((w // 2, 120), f"{tg} - {og}", fill=(255, 255, 255), font=self._fonts["header"], anchor="mm")
        draw.text((w // 2, 200), f"vs {opp}", fill=(220, 220, 220), font=self._fonts["subheader"], anchor="mm")
        draw.text((w // 2, 260), result.upper(), fill=(255, 255, 255), font=self._fonts["header"], anchor="mm")

        pstats = match_data.get("player_stats", {})
        y = 360
        for i, (pname, ps) in enumerate(list(pstats.items())[:6]):
            line = f"{pname}: {ps.get('goals', 0)}G {ps.get('assists', 0)}A | ⭐{ps.get('rating', 6.0):.1f}"
            draw.text((60, y), line, fill=(255, 255, 255), font=self._fonts["body"])
            y += 50
        return card

    def generate_leaderboard_card(self, leaderboard: List[Tuple[str, dict]], period: str) -> Image.Image:
        w, h = 900, 1100
        dark = [(25, 25, 35), (15, 15, 25), (8, 8, 15)]
        card = self._gradient(w, h, dark)
        draw = ImageDraw.Draw(card)

        draw.text((w // 2, 60), f"Leaderboard — {period.upper()}", fill=(255, 215, 0), font=self._fonts["header"], anchor="mm")

        y = 160
        for i, (name, stats) in enumerate(leaderboard[:10]):
            rc = (255, 215, 0) if i == 0 else (200, 200, 200) if i == 1 else (205, 127, 50) if i == 2 else (150, 150, 150)
            draw.text((60, y), f"#{i+1}", fill=rc, font=self._fonts["subheader"])
            draw.text((140, y), name, fill=(255, 255, 255), font=self._fonts["body"])
            draw.text((560, y), f"Impact: {stats.get('impact_score', 0):.1f}", fill=(255, 255, 255), font=self._fonts["body"])
            draw.text((760, y), f"{stats.get('rating', 0):.1f}⭐", fill=(255, 215, 0), font=self._fonts["body"])
            y += 80
        return card

    def generate_comparison_card(self, n1: str, s1: dict, i1: dict, n2: str, s2: dict, i2: dict) -> Image.Image:
        w, h = 1100, 900
        dark = [(25, 25, 35), (15, 15, 25), (8, 8, 15)]
        card = self._gradient(w, h, dark)
        draw = ImageDraw.Draw(card)

        nick1 = i1.get("nickname", n1)
        nick2 = i2.get("nickname", n2)

        draw.text((275, 60), nick1, fill=(255, 100, 100), font=self._fonts["header"], anchor="mm")
        draw.text((825, 60), nick2, fill=(100, 100, 255), font=self._fonts["header"], anchor="mm")
        draw.text((550, 60), "VS", fill=(255, 255, 255), font=self._fonts["header"], anchor="mm")

        comps = [
            ("Goals", s1.get("goals", 0), s2.get("goals", 0)),
            ("Assists", s1.get("assists", 0), s2.get("assists", 0)),
            ("Rating", s1.get("rating", 0), s2.get("rating", 0)),
            ("Impact", s1.get("impact_score", 0), s2.get("impact_score", 0)),
            ("Pass %", s1.get("pass_accuracy", 0), s2.get("pass_accuracy", 0)),
        ]

        y = 180
        for label, v1, v2 in comps:
            c1 = (0, 255, 120) if v1 > v2 else (255, 255, 255)
            c2 = (0, 255, 120) if v2 > v1 else (255, 255, 255)
            draw.text((275, y), f"{v1}", fill=c1, font=self._fonts["subheader"], anchor="mm")
            draw.text((550, y), label, fill=(180, 180, 180), font=self._fonts["body"], anchor="mm")
            draw.text((825, y), f"{v2}", fill=c2, font=self._fonts["subheader"], anchor="mm")
            y += 100
        return card

    def to_bytes(self, img: Image.Image) -> bytes:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf.getvalue()


def get_image_generator(assets_path: str = "assets") -> ImageGenerator:
    return ImageGenerator(assets_path)
