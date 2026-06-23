import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
​
CARD_W = 1440
CARD_H = 2160
@dataclass(frozen=True)
class CardTheme:
card_type: str
template_file: str
primary: Tuple[int, int, int]
secondary: Tuple[int, int, int]
accent: Tuple[int, int, int]
glow: Tuple[int, int, int]
dark: Tuple[int, int, int]
label: str
CARD_THEMES: Dict[str, CardTheme] = {
"mvp": CardTheme(
"mvp",
"mvp.png",
(255, 198, 41),
(20, 75, 180),
(255, 235, 130),
(30, 160, 255),
(12, 14, 24),
"MOST VALUABLE PLAYER",
),
"fraud": CardTheme(
"fraud",
"fraud.png",
(220, 20, 40),
(70, 0, 0),
(255, 80, 80),
(255, 35, 35),
(15, 10, 10),
"FRAUD WATCH",
),
"ghost": CardTheme(
"ghost",
"ghost.png",
(120, 120, 150),
(30, 25, 45),
(190, 190, 255),
(135, 90, 255),
(8, 8, 18),
"GHOST MODE",
),
"carry": CardTheme(
"carry",
"carry.png",
(160, 80, 255),
(40, 10, 90),
(230, 190, 255),
(170, 50, 255),
(15, 8, 30),
"TEAM CARRY",
),
"court_case": CardTheme(
"court_case",
"court_case.png",
(200, 160, 80),
(45, 30, 18),
(255, 220, 140),
(255, 180, 70),
(18, 13, 10),
"COURT CASE",
),
"ball_loser": CardTheme(
"ball_loser",
"ball_loser.png",
(255, 115, 20),
(95, 35, 0),
(255, 190, 80),
(255, 95, 20),
(20, 12, 5),
"BALL LOSER",
),
"playmaker": CardTheme(
"playmaker",
"playmaker.png",
(0, 210, 255),
(0, 55, 85),
(150, 245, 255),
(0, 230, 255),
(5, 15, 22),
"PLAYMAKER",
),
"sniper": CardTheme(
"sniper",
"sniper.png",
(210, 210, 210),
(25, 25, 30),
(255, 255, 255),
(255, 40, 40),
(7, 7, 10),
"SNIPER",
),
}
class ProCardEngine:
"""
Premium Pro Clubs card renderer.
Responsibilities:
Load player photo from local assets.
Load static card template from assets/templates.
Inject rating, position, nickname, and stats.
Add layered effects using Pillow.
Cache generated cards in cache/cards.
"""
def init(
self,
assets_dir: str = "assets",
templates_dir: str = "assets/templates",
output_dir: str = "cache/cards",
squad_file: str = "squad.json",
debug: bool = True,
):
self.assets_dir = assets_dir
self.templates_dir = templates_dir
self.output_dir = output_dir
self.squad_file = squad_file
self.debug = debug
self.squad = self._load_squad()
os.makedirs(self.output_dir, exist_ok=True)
────────────────────────────────────────────
PUBLIC API
────────────────────────────────────────────
def build_card(
self,
player: Any,
card_type: str,
force: bool = False,
output_name: Optional[str] = None,
) -> str:
card_type = self._normalize_card_type(card_type)
theme = CARD_THEMES[card_type]
player_data = self._player_to_dict(player)
player_name = self._safe_text(player_data.get("name"), "Unknown")
squad_info = self._find_squad_info(player_name, player_data)
nickname = self._safe_text(
squad_info.get("nickname")
or squad_info.get("name")
or player_name,
player_name,
)
position = self._safe_text(
squad_info.get("position")
or player_data.get("position")
or "CM",
"CM",
).upper()
rating = self._rating_value(player_data)
stats = self._stats_grid(player_data)
template_path = self._template_path(theme)
asset_path = self._resolve_player_asset(squad_info, player_name)
cache_key = self._cache_key(
card_type=card_type,
player_name=player_name,
nickname=nickname,
position=position,
rating=rating,
stats=stats,
asset_path=asset_path,
template_path=template_path,
)
output_path = self._output_path(card_type, nickname, output_name)
meta_path = output_path + ".json"
if not force and self._cache_valid(output_path, meta_path, cache_key):
self._debug(
player_name=player_name,
asset_path=asset_path,
template_path=template_path,
stats=stats,
output_path=output_path,
message="cache hit",
)
return output_path
if not os.path.exists(template_path):
raise FileNotFoundError(
f"Missing card template: {template_path}. "
f"Run python create_card_templates.py to generate static templates."
)
template = Image.open(template_path).convert("RGBA")
template = template.resize((CARD_W, CARD_H), Image.LANCZOS)
img = template.copy()
self._draw_base_overlays(img, theme)
self._draw_photo_panel(img, theme, asset_path, player_name)
self._draw_top_identity(img, theme, rating, position, nickname)
self._draw_bottom_stats(img, theme, stats)
self._draw_card_type_label(img, theme)
self._draw_finishing_effects(img, theme)
img = img.convert("RGB")
img.save(output_path, "PNG", optimize=True)
with open(meta_path, "w", encoding="utf-8") as f:
json.dump(
{
"cache_key": cache_key,
"player_name": player_name,
"nickname": nickname,
"position": position,
"rating": rating,
"card_type": card_type,
"asset_path": asset_path,
"template_path": template_path,
"output_path": output_path,
"stats": stats,
},
f,
ensure_ascii=False,
indent=2,
)
self._debug(
player_name=player_name,
asset_path=asset_path,
template_path=template_path,
stats=stats,
output_path=output_path,
message="generated",
)
return output_path
def build_mvp(self, player: Any, force: bool = False) -> str:
return self.build_card(player, "mvp", force=force)
def build_fraud(self, player: Any, force: bool = False) -> str:
return self.build_card(player, "fraud", force=force)
def build_ghost(self, player: Any, force: bool = False) -> str:
return self.build_card(player, "ghost", force=force)
def build_carry(self, player: Any, force: bool = False) -> str:
return self.build_card(player, "carry", force=force)
def build_court_case(self, player: Any, force: bool = False) -> str:
return self.build_card(player, "court_case", force=force)
def build_ball_loser(self, player: Any, force: bool = False) -> str:
return self.build_card(player, "ball_loser", force=force)
def build_playmaker(self, player: Any, force: bool = False) -> str:
return self.build_card(player, "playmaker", force=force)
def build_sniper(self, player: Any, force: bool = False) -> str:
return self.build_card(player, "sniper", force=force)
────────────────────────────────────────────
DATA LOADING
────────────────────────────────────────────
def _load_squad(self) -> Dict[str, Any]:
if not os.path.exists(self.squad_file):
return {"players": []}
try:
with open(self.squad_file, "r", encoding="utf-8") as f:
data = json.load(f)
if isinstance(data, dict):
if "players" in data and isinstance(data["players"], list):
return data
return {"players": list(data.values())}
if isinstance(data, list):
return {"players": data}
return {"players": []}
except Exception:
return {"players": []}
def _find_squad_info(self, player_name: str, player_data: Dict[str, Any]) -> Dict[str, Any]:
players = self.squad.get("players", [])
if not isinstance(players, list):
return {}
candidates = {
self._norm(player_name),
self._norm(player_data.get("name")),
self._norm(player_data.get("psn_name")),
self._norm(player_data.get("pro_name")),
self._norm(player_data.get("_raw_psn")),
}
candidates = {c for c in candidates if c}
for entry in players:
if not isinstance(entry, dict):
continue
names = {
self._norm(entry.get("name")),
self._norm(entry.get("nickname")),
self._norm(entry.get("psn")),
self._norm(entry.get("PSN")),
self._norm(entry.get("proName")),
self._norm(entry.get("ea_name")),
}
names = {n for n in names if n}
if candidates & names:
return entry
return {}
def _player_to_dict(self, player: Any) -> Dict[str, Any]:
if isinstance(player, dict):
return dict(player)
if hasattr(player, "model_dump"):
return dict(player.model_dump())
if hasattr(player, "dict"):
return dict(player.dict())
data: Dict[str, Any] = {}
for key in [
"name",
"position",
"games",
"rating",
"rating_pg",
"goals",
"assists",
"pass_accuracy",
"passes_made",
"possession_losses",
"motm",
"win_rate",
"impact_score",
"clean_sheets",
"tackles",
"psn_name",
"pro_name",
"_raw_psn",
]:
if hasattr(player, key):
data[key] = getattr(player, key)
return data
────────────────────────────────────────────
PATHS / CACHE
────────────────────────────────────────────
def _normalize_card_type(self, card_type: str) -> str:
key = self._slug(card_type)
aliases = {
"court": "court_case",
"courtcase": "court_case",
"ballloser": "ball_loser",
"ball_loser": "ball_loser",
"who_sold": "fraud",
"worst": "fraud",
}
key = aliases.get(key, key)
if key not in CARD_THEMES:
raise ValueError(f"Unknown card type: {card_type}. Available: {', '.join(CARD_THEMES)}")
return key
def _template_path(self, theme: CardTheme) -> str:
return os.path.join(self.templates_dir, theme.template_file)
def _output_path(self, card_type: str, nickname: str, output_name: Optional[str]) -> str:
if output_name:
filename = output_name
if not filename.lower().endswith(".png"):
filename += ".png"
else:
filename = f"{card_type}_{self._slug(nickname)}.png"
return os.path.join(self.output_dir, filename)
def _cache_key(
self,
card_type: str,
player_name: str,
nickname: str,
position: str,
rating: int,
stats: Dict[str, str],
asset_path: Optional[str],
template_path: str,
) -> str:
payload = {
"card_type": card_type,
"player_name": player_name,
"nickname": nickname,
"position": position,
"rating": rating,
"stats": stats,
"asset_path": asset_path,
"template_path": template_path,
"asset_mtime": os.path.getmtime(asset_path) if asset_path and os.path.exists(asset_path) else None,
"template_mtime": os.path.getmtime(template_path) if os.path.exists(template_path) else None,
}
raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
return hashlib.sha256(raw.encode("utf-8")).hexdigest()
def _cache_valid(self, output_path: str, meta_path: str, cache_key: str) -> bool:
if not os.path.exists(output_path) or not os.path.exists(meta_path):
return False
try:
with open(meta_path, "r", encoding="utf-8") as f:
meta = json.load(f)
return meta.get("cache_key") == cache_key
except Exception:
return False
def _resolve_player_asset(self, squad_info: Dict[str, Any], player_name: str) -> Optional[str]:
candidates = []
image_value = squad_info.get("image") if isinstance(squad_info, dict) else None
if image_value:
candidates.append(str(image_value))
candidates.extend(
[
os.path.join(self.assets_dir, f"{player_name}.png"),
os.path.join(self.assets_dir, f"{player_name}.jpg"),
os.path.join(self.assets_dir, f"{player_name}.jpeg"),
os.path.join(self.assets_dir, f"{player_name}.webp"),
os.path.join(self.assets_dir, f"{player_name.upper()}.png"),
os.path.join(self.assets_dir, f"{player_name.upper()}.jpg"),
os.path.join(self.assets_dir, f"{player_name.upper()}.jpeg"),
os.path.join(self.assets_dir, f"{player_name.upper()}.webp"),
]
)
for path in candidates:
if not path:
continue
if os.path.exists(path):
return path
if not os.path.isabs(path):
joined = os.path.join(".", path)
if os.path.exists(joined):
return joined
return self._case_insensitive_asset_search(candidates)
def _case_insensitive_asset_search(self, candidates) -> Optional[str]:
wanted = set()
for path in candidates:
if not path:
continue
wanted.add(os.path.basename(path).lower())
base, _ = os.path.splitext(os.path.basename(path))
for ext in [".png", ".jpg", ".jpeg", ".webp"]:
wanted.add((base + ext).lower())
if not os.path.isdir(self.assets_dir):
return None
try:
for filename in os.listdir(self.assets_dir):
if filename.lower() in wanted:
path = os.path.join(self.assets_dir, filename)
if os.path.exists(path):
return path
except Exception:
return None
return None
────────────────────────────────────────────
DRAWING
────────────────────────────────────────────
def _draw_base_overlays(self, img: Image.Image, theme: CardTheme) -> None:
overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
draw = ImageDraw.Draw(overlay)
Bottom readability panel.
draw.rounded_rectangle(
[70, 1510, CARD_W - 70, CARD_H - 95],
radius=44,
fill=(0, 0, 0, 150),
outline=(*theme.accent, 150),
width=3,
)
Top glass panel.
draw.rounded_rectangle(
[70, 70, CARD_W - 70, 375],
radius=42,
fill=(0, 0, 0, 95),
outline=(*theme.accent, 145),
width=3,
)
Main center frame.
draw.rounded_rectangle(
[95, 410, CARD_W - 95, 1510],
radius=55,
fill=(0, 0, 0, 45),
outline=(*theme.primary, 135),
width=4,
)
img.alpha_composite(overlay)
def _draw_photo_panel(
self,
img: Image.Image,
theme: CardTheme,
asset_path: Optional[str],
player_name: str,
) -> None:
photo_box = (105, 425, CARD_W - 105, 1500)
photo_w = photo_box[2] - photo_box[0]
photo_h = photo_box[3] - photo_box[1]
glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
glow_draw = ImageDraw.Draw(glow)
glow_draw.ellipse(
[145, 455, CARD_W - 145, 1545],
fill=(*theme.glow, 70),
)
glow = glow.filter(ImageFilter.GaussianBlur(55))
img.alpha_composite(glow)
if asset_path and os.path.exists(asset_path):
try:
photo = Image.open(asset_path).convert("RGBA")
photo = ImageOps.exif_transpose(photo)
photo.thumbnail((photo_w, photo_h), Image.LANCZOS)
x = photo_box[0] + (photo_w - photo.width) // 2
y = photo_box[1] + (photo_h - photo.height) // 2
shadow = Image.new("RGBA", (photo.width + 90, photo.height + 90), (0, 0, 0, 0))
shadow_draw = ImageDraw.Draw(shadow)
shadow_draw.rounded_rectangle(
[35, 35, photo.width + 55, photo.height + 55],
radius=42,
fill=(0, 0, 0, 190),
)
shadow = shadow.filter(ImageFilter.GaussianBlur(28))
img.alpha_composite(shadow, (x - 45, y - 35))
img.alpha_composite(photo, (x, y))
return
except Exception as e:
raise RuntimeError(f"Could not load player asset {asset_path}: {e}") from e
self._draw_missing_photo_placeholder(img, theme, player_name, photo_box)
def _draw_missing_photo_placeholder(
self,
img: Image.Image,
theme: CardTheme,
player_name: str,
box: Tuple[int, int, int, int],
) -> None:
draw = ImageDraw.Draw(img)
font_big = self._font(86, bold=True)
font_small = self._font(38, bold=False)
draw.rounded_rectangle(
box,
radius=55,
fill=(*theme.dark, 190),
outline=(*theme.accent, 170),
width=4,
)
cx = (box[0] + box[2]) // 2
cy = (box[1] + box[3]) // 2
draw.ellipse(
[cx - 170, cy - 290, cx + 170, cy + 50],
fill=(*theme.secondary, 210),
outline=(*theme.accent, 180),
width=5,
)
draw.rounded_rectangle(
[cx - 260, cy + 50, cx + 260, cy + 440],
radius=120,
fill=(*theme.secondary, 210),
outline=(*theme.accent, 180),
width=5,
)
draw.text(
(cx, box[3] - 125),
player_name.upper(),
fill=(240, 240, 240, 230),
font=font_big,
anchor="mm",
)
draw.text(
(cx, box[3] - 60),
"LOCAL PHOTO NOT FOUND",
fill=(*theme.accent, 230),
font=font_small,
anchor="mm",
)
def _draw_top_identity(
self,
img: Image.Image,
theme: CardTheme,
rating: int,
position: str,
nickname: str,
) -> None:
draw = ImageDraw.Draw(img)
rating_font = self._font(150, bold=True)
position_font = self._font(54, bold=True)
name_font = self._font(82, bold=True)
draw.text((135, 105), str(rating), font=rating_font, fill=theme.accent)
draw.text((150, 265), position, font=position_font, fill=(245, 245, 245))
safe_name = nickname.upper()
if len(safe_name) > 18:
safe_name = safe_name[:18]
draw.text(
(CARD_W - 115, 175),
safe_name,
font=name_font,
fill=(255, 255, 255),
anchor="ra",
)
draw.line(
[475, 285, CARD_W - 120, 285],
fill=(*theme.accent, 180),
width=4,
)
def _draw_card_type_label(self, img: Image.Image, theme: CardTheme) -> None:
draw = ImageDraw.Draw(img)
label_font = self._font(42, bold=True)
text = theme.label
draw.rounded_rectangle(
[430, 325, CARD_W - 430, 390],
radius=28,
fill=(*theme.primary, 215),
outline=(*theme.accent, 180),
width=2,
)
draw.text(
(CARD_W // 2, 357),
text,
font=label_font,
fill=(10, 10, 14),
anchor="mm",
)
def _draw_bottom_stats(
self,
img: Image.Image,
theme: CardTheme,
stats: Dict[str, str],
) -> None:
draw = ImageDraw.Draw(img)
label_font = self._font(31, bold=True)
value_font = self._font(58, bold=True)
keys = [
("GOALS", "goals"),
("ASSISTS", "assists"),
("RATING", "rating"),
("PASS %", "pass_pct"),
("WIN %", "win_pct"),
("POSS LOST", "possession_lost"),
("MOTM", "motm"),
("IMPACT", "impact"),
]
start_x = 110
start_y = 1580
gap_x = 28
gap_y = 28
box_w = (CARD_W - 220 - gap_x) // 2
box_h = 112
for idx, (label, key) in enumerate(keys):
col = idx % 2
row = idx // 2
x = start_x + col * (box_w + gap_x)
y = start_y + row * (box_h + gap_y)
draw.rounded_rectangle(
[x, y, x + box_w, y + box_h],
radius=24,
fill=(12, 14, 20, 195),
outline=(*theme.accent, 120),
width=2,
)
draw.text(
(x + 28, y + 18),
label,
font=label_font,
fill=(185, 190, 205),
)
draw.text(
(x + box_w - 28, y + 61),
stats.get(key, "0"),
font=value_font,
fill=(255, 255, 255),
anchor="rm",
)
def _draw_finishing_effects(self, img: Image.Image, theme: CardTheme) -> None:
effect = Image.new("RGBA", img.size, (0, 0, 0, 0))
draw = ImageDraw.Draw(effect)
Outer border.
draw.rounded_rectangle(
[32, 32, CARD_W - 32, CARD_H - 32],
radius=65,
outline=(*theme.accent, 220),
width=6,
)
draw.rounded_rectangle(
[48, 48, CARD_W - 48, CARD_H - 48],
radius=55,
outline=(*theme.primary, 150),
width=3,
)
if theme.card_type in {"fraud", "ball_loser"}:
self._draw_crack_lines(draw, theme)
elif theme.card_type == "ghost":
self._draw_ghost_lines(draw, theme)
elif theme.card_type == "sniper":
self._draw_sniper_lines(draw, theme)
else:
self._draw_energy_lines(draw, theme)
img.alpha_composite(effect)
def _draw_crack_lines(self, draw: ImageDraw.ImageDraw, theme: CardTheme) -> None:
lines = [
[(210, 470), (310, 610), (275, 740), (410, 925)],
[(1180, 520), (1080, 690), (1135, 830), (1010, 1020)],
[(250, 1480), (370, 1390), (510, 1440), (630, 1320)],
]
for line in lines:
draw.line(line, fill=(*theme.accent, 145), width=5)
def _draw_ghost_lines(self, draw: ImageDraw.ImageDraw, theme: CardTheme) -> None:
for y in range(520, 1440, 95):
draw.line(
[155, y, CARD_W - 155, y + 25],
fill=(*theme.accent, 55),
width=3,
)
def _draw_sniper_lines(self, draw: ImageDraw.ImageDraw, theme: CardTheme) -> None:
cx = CARD_W // 2
cy = 970
draw.ellipse([cx - 260, cy - 260, cx + 260, cy + 260], outline=(*theme.glow, 105), width=3)
draw.line([cx - 330, cy, cx + 330, cy], fill=(*theme.glow, 100), width=3)
draw.line([cx, cy - 330, cx, cy + 330], fill=(*theme.glow, 100), width=3)
def _draw_energy_lines(self, draw: ImageDraw.ImageDraw, theme: CardTheme) -> None:
for x in [130, CARD_W - 130]:
draw.line(
[x, 430, x + (70 if x < CARD_W // 2 else -70), 1485],
fill=(*theme.glow, 80),
width=5,
)
────────────────────────────────────────────
STATS
────────────────────────────────────────────
def _rating_value(self, player_data: Dict[str, Any]) -> int:
rating = self._num(player_data.get("rating_pg"), None)
if rating is None or rating <= 0:
rating = self._num(player_data.get("rating"), 0.0)
if rating > 10:
rating = rating / 10.0
return int(max(1, min(99, round(rating * 10))))
def _stats_grid(self, player_data: Dict[str, Any]) -> Dict[str, str]:
return {
"goals": str(self._int(player_data.get("goals"))),
"assists": str(self._int(player_data.get("assists"))),
"rating": f"{self._num(player_data.get('rating_pg'), self._num(player_data.get('rating'), 0.0)):.1f}",
"pass_pct": f"{self._num(player_data.get('pass_accuracy'), 0.0):.0f}",
"win_pct": f"{self._num(player_data.get('win_rate'), 0.0):.0f}",
"possession_lost": str(self._int(player_data.get("possession_losses"))),
"motm": str(self._int(player_data.get("motm"))),
"impact": f"{self._num(player_data.get('impact_score'), 0.0):.0f}",
}
────────────────────────────────────────────
FONTS / TEXT / DEBUG
────────────────────────────────────────────
def _font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
candidates = []
if bold:
candidates.extend(
[
"/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
"/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
"arialbd.ttf",
]
)
else:
candidates.extend(
[
"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
"/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
"arial.ttf",
]
)
for path in candidates:
try:
return ImageFont.truetype(path, size=size)
except Exception:
continue
return ImageFont.load_default()
def _debug(
self,
player_name: str,
asset_path: Optional[str],
template_path: str,
stats: Dict[str, str],
output_path: str,
message: str,
) -> None:
if not self.debug:
return
print("[CARD_ENGINE]", message)
print("[CARD_ENGINE] player name:", player_name)
print("[CARD_ENGINE] asset path:", asset_path or "NOT FOUND")
print("[CARD_ENGINE] template path:", template_path)
print("[CARD_ENGINE] stats loaded:", stats)
print("[CARD_ENGINE] final output path:", output_path)
@staticmethod
def _safe_text(value: Any, fallback: str = "") -> str:
if value is None:
return fallback
text = str(value).strip()
return text if text else fallback
@staticmethod
def _norm(value: Any) -> str:
if value is None:
return ""
return str(value).strip().lower()
@staticmethod
def _slug(value: Any) -> str:
text = str(value or "unknown").strip().lower()
text = re.sub(r"+", "_", text)
text = re.sub(r"+", "", text).strip("_")
return text or "unknown"
@staticmethod
def _num(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
try:
if value is None:
return default
return float(value)
except Exception:
return default
@staticmethod
def _int(value: Any, default: int = 0) -> int:
try:
if value is None:
return default
return int(float(value))
except Exception:
return default
