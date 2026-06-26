import hashlib
import json
import os
import re
from typing import Any, Dict, Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
​
CARD_W = 1440
CARD_H = 2160
THEMES = {
"mvp": {
"top": (10, 28, 70),
"bottom": (190, 140, 20),
"accent": (255, 220, 80),
"glow": (40, 150, 255),
"label": "MOST VALUABLE PLAYER",
},
"fraud": {
"top": (35, 0, 0),
"bottom": (150, 10, 20),
"accent": (255, 70, 70),
"glow": (255, 30, 30),
"label": "FRAUD WATCH",
},
"ghost": {
"top": (5, 5, 18),
"bottom": (45, 35, 75),
"accent": (180, 180, 255),
"glow": (120, 80, 255),
"label": "GHOST MODE",
},
"carry": {
"top": (20, 5, 45),
"bottom": (95, 30, 170),
"accent": (220, 170, 255),
"glow": (175, 70, 255),
"label": "TEAM CARRY",
},
"court_case": {
"top": (25, 16, 8),
"bottom": (130, 85, 35),
"accent": (255, 210, 130),
"glow": (255, 170, 60),
"label": "COURT CASE",
},
"ball_loser": {
"top": (35, 15, 0),
"bottom": (185, 75, 10),
"accent": (255, 165, 60),
"glow": (255, 110, 20),
"label": "BALL LOSER",
},
"playmaker": {
"top": (0, 22, 36),
"bottom": (0, 110, 150),
"accent": (130, 245, 255),
"glow": (0, 220, 255),
"label": "PLAYMAKER",
},
"sniper": {
"top": (5, 5, 8),
"bottom": (55, 55, 65),
"accent": (245, 245, 245),
"glow": (255, 40, 40),
"label": "SNIPER",
},
}
class ProCardEngine:
def init(
self,
assets_dir: str = "assets",
output_dir: str = "cache/cards",
squad_file: str = "squad.json",
debug: bool = True,
):
self.assets_dir = assets_dir
self.output_dir = output_dir
self.squad_file = squad_file
self.debug = debug
self.squad = self._load_squad()
os.makedirs(self.output_dir, exist_ok=True)
def build_card(
self,
player: Any,
card_type: str = "mvp",
force: bool = False,
output_name: Optional[str] = None,
) -> str:
card_type = self._normalize_card_type(card_type)
theme = THEMES[card_type]
player_data = self._player_to_dict(player)
player_name = self._safe_text(player_data.get("name"), "Unknown")
squad_info = self._find_squad_info(player_name, player_data)
nickname = self._safe_text(
squad_info.get("nickname") or squad_info.get("name") or player_name,
player_name,
)
position = self._safe_text(
squad_info.get("position") or player_data.get("position") or "CM",
"CM",
).upper()
rating = self._rating_value(player_data)
stats = self._stats_grid(player_data)
asset_path = self._resolve_player_asset(squad_info, player_name)
if output_name:
filename = output_name if output_name.endswith(".png") else f"{output_name}.png"
else:
filename = f"{card_type}_{self._slug(nickname)}.png"
output_path = os.path.join(self.output_dir, filename)
meta_path = output_path + ".json"
cache_key = self._cache_key(card_type, player_name, nickname, position, rating, stats, asset_path)
if not force and self._cache_valid(output_path, meta_path, cache_key):
self._debug(player_name, asset_path, "built-in", stats, output_path, "cache hit")
return output_path
img = self._make_background(theme, card_type)
self._draw_photo(img, theme, asset_path, player_name)
self._draw_identity(img, theme, rating, position, nickname)
self._draw_stats(img, theme, stats)
self._draw_finish(img, theme, card_type)
img.convert("RGB").save(output_path, "PNG", optimize=True)
with open(meta_path, "w", encoding="utf-8") as f:
json.dump(
{
"cache_key": cache_key,
"player": player_name,
"nickname": nickname,
"position": position,
"rating": rating,
"card_type": card_type,
"asset_path": asset_path,
"stats": stats,
"output_path": output_path,
},
f,
ensure_ascii=False,
indent=2,
)
self._debug(player_name, asset_path, "built-in", stats, output_path, "generated")
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
def _make_background(self, theme: Dict[str, Any], card_type: str) -> Image.Image:
img = Image.new("RGBA", (CARD_W, CARD_H))
top = theme["top"]
bottom = theme["bottom"]
for y in range(CARD_H):
ratio = y / max(CARD_H - 1, 1)
r = int(top[0] + (bottom[0] - top[0]) * ratio)
g = int(top[1] + (bottom[1] - top[1]) * ratio)
b = int(top[2] + (bottom[2] - top[2]) * ratio)
for x in range(CARD_W):
img.putpixel((x, y), (r, g, b, 255))
self._add_glow(img, theme["glow"], (CARD_W // 2, 720), 760, 120)
self._add_glow(img, theme["accent"], (CARD_W // 2, 1540), 620, 70)
overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
draw = ImageDraw.Draw(overlay)
for x in range(-CARD_H, CARD_W, 110):
draw.line(
[(x, CARD_H), (x + CARD_H, 0)],
fill=(*theme["accent"], 32),
width=4,
)
draw.rounded_rectangle(
[35, 35, CARD_W - 35, CARD_H - 35],
radius=75,
outline=(*theme["accent"], 230),
width=8,
)
draw.rounded_rectangle(
[60, 60, CARD_W - 60, CARD_H - 60],
radius=60,
outline=(*theme["glow"], 130),
width=4,
)
draw.rounded_rectangle(
[80, 80, CARD_W - 80, 400],
radius=48,
fill=(0, 0, 0, 120),
outline=(*theme["accent"], 120),
width=3,
)
draw.rounded_rectangle(
[100, 425, CARD_W - 100, 1500],
radius=58,
fill=(0, 0, 0, 55),
outline=(*theme["accent"], 110),
width=4,
)
draw.rounded_rectangle(
[80, 1525, CARD_W - 80, CARD_H - 95],
radius=48,
fill=(0, 0, 0, 145),
outline=(*theme["accent"], 120),
width=3,
)
if card_type == "fraud":
cracks = [
[(240, 500), (330, 650), (290, 800), (430, 980)],
[(1160, 520), (1060, 720), (1130, 900), (980, 1080)],
[(250, 1460), (400, 1370), (560, 1445), (700, 1330)],
]
for crack in cracks:
draw.line(crack, fill=(*theme["accent"], 150), width=6)
elif card_type == "ghost":
for y in range(500, 1470, 90):
draw.line(
[150, y, CARD_W - 150, y + 25],
fill=(*theme["accent"], 55),
width=4,
)
elif card_type == "sniper":
cx = CARD_W // 2
cy = 965
draw.ellipse(
[cx - 320, cy - 320, cx + 320, cy + 320],
outline=(*theme["glow"], 120),
width=4,
)
draw.line([cx - 430, cy, cx + 430, cy], fill=(*theme["glow"], 120), width=4)
draw.line([cx, cy - 430, cx, cy + 430], fill=(*theme["glow"], 120), width=4)
elif card_type == "playmaker":
for y in [620, 790, 960, 1130, 1300]:
draw.line([160, y, CARD_W - 160, y], fill=(*theme["glow"], 70), width=4)
for x in [360, 720, 1080]:
draw.ellipse([x - 14, y - 14, x + 14, y + 14], fill=(*theme["glow"], 120))
else:
draw.line([150, 430, 235, 1485], fill=(*theme["glow"], 90), width=6)
draw.line([CARD_W - 150, 430, CARD_W - 235, 1485], fill=(*theme["glow"], 90), width=6)
img.alpha_composite(overlay)
return img
def _add_glow(self, img: Image.Image, color, center, radius: int, alpha: int) -> None:
layer = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
draw = ImageDraw.Draw(layer)
cx, cy = center
draw.ellipse(
[cx - radius, cy - radius, cx + radius, cy + radius],
fill=(color[0], color[1], color[2], alpha),
)
layer = layer.filter(ImageFilter.GaussianBlur(max(1, radius // 4)))
img.alpha_composite(layer)
def _draw_photo(self, img: Image.Image, theme: Dict[str, Any], asset_path: Optional[str], player_name: str) -> None:
box = (105, 425, CARD_W - 105, 1500)
box_w = box[2] - box[0]
box_h = box[3] - box[1]
if asset_path and os.path.exists(asset_path):
try:
photo = Image.open(asset_path).convert("RGBA")
photo = ImageOps.exif_transpose(photo)
photo.thumbnail((box_w, box_h), Image.LANCZOS)
x = box[0] + (box_w - photo.width) // 2
y = box[1] + (box_h - photo.height) // 2
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
except Exception as exc:
raise RuntimeError(f"Could not load player asset {asset_path}: {exc}") from exc
draw = ImageDraw.Draw(img)
accent = theme["accent"]
glow = theme["glow"]
draw.rounded_rectangle(
box,
radius=55,
fill=(0, 0, 0, 120),
outline=(*accent, 160),
width=4,
)
cx = (box[0] + box[2]) // 2
cy = (box[1] + box[3]) // 2
draw.ellipse(
[cx - 170, cy - 300, cx + 170, cy + 40],
fill=(*glow, 160),
outline=(*accent, 180),
width=5,
)
draw.rounded_rectangle(
[cx - 280, cy + 60, cx + 280, cy + 450],
radius=130,
fill=(*glow, 130),
outline=(*accent, 180),
width=5,
)
draw.text(
(cx, box[3] - 120),
player_name.upper(),
fill=(255, 255, 255),
font=self._font(76, True),
anchor="mm",
)
draw.text(
(cx, box[3] - 55),
"LOCAL PHOTO NOT FOUND",
fill=(*accent, 230),
font=self._font(36, False),
anchor="mm",
)
def _draw_identity(self, img: Image.Image, theme: Dict[str, Any], rating: int, position: str, nickname: str) -> None:
draw = ImageDraw.Draw(img)
accent = theme["accent"]
draw.text((135, 105), str(rating), font=self._font(150, True), fill=accent)
draw.text((150, 265), position, font=self._font(54, True), fill=(245, 245, 245))
safe_name = nickname.upper()
if len(safe_name) > 18:
safe_name = safe_name[:18]
draw.text(
(CARD_W - 115, 170),
safe_name,
font=self._font(82, True),
fill=(255, 255, 255),
anchor="ra",
)
draw.line([475, 285, CARD_W - 120, 285], fill=(*accent, 180), width=4)
draw.rounded_rectangle(
[430, 325, CARD_W - 430, 390],
radius=28,
fill=(*accent, 215),
outline=(255, 255, 255, 130),
width=2,
)
draw.text(
(CARD_W // 2, 357),
theme["label"],
font=self._font(42, True),
fill=(10, 10, 14),
anchor="mm",
)
def _draw_stats(self, img: Image.Image, theme: Dict[str, Any], stats: Dict[str, str]) -> None:
draw = ImageDraw.Draw(img)
accent = theme["accent"]
items = [
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
for index, item in enumerate(items):
label, key = item
col = index % 2
row = index // 2
x = start_x + col * (box_w + gap_x)
y = start_y + row * (box_h + gap_y)
draw.rounded_rectangle(
[x, y, x + box_w, y + box_h],
radius=24,
fill=(12, 14, 20, 195),
outline=(*accent, 120),
width=2,
)
draw.text(
(x + 28, y + 18),
label,
font=self._font(31, True),
fill=(185, 190, 205),
)
draw.text(
(x + box_w - 28, y + 61),
stats.get(key, "0"),
font=self._font(58, True),
fill=(255, 255, 255),
anchor="rm",
)
def _draw_finish(self, img: Image.Image, theme: Dict[str, Any], card_type: str) -> None:
draw = ImageDraw.Draw(img)
accent = theme["accent"]
draw.rounded_rectangle(
[32, 32, CARD_W - 32, CARD_H - 32],
radius=65,
outline=(*accent, 220),
width=6,
)
def _load_squad(self) -> Dict[str, Any]:
if not os.path.exists(self.squad_file):
return {"players": []}
try:
with open(self.squad_file, "r", encoding="utf-8") as file:
data = json.load(file)
if isinstance(data, dict):
if isinstance(data.get("players"), list):
return data
return {"players": list(data.values())}
if isinstance(data, list):
return {"players": data}
except Exception:
pass
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
candidates = {item for item in candidates if item}
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
names = {item for item in names if item}
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
data = {}
keys = [
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
]
for key in keys:
if hasattr(player, key):
data[key] = getattr(player, key)
return data
def _resolve_player_asset(self, squad_info: Dict[str, Any], player_name: str) -> Optional[str]:
candidates = []
image_value = squad_info.get("image") if isinstance(squad_info, dict) else None
if image_value:
candidates.append(str(image_value))
for ext in [".png", ".jpg", ".jpeg", ".webp"]:
candidates.append(os.path.join(self.assets_dir, player_name + ext))
candidates.append(os.path.join(self.assets_dir, player_name.upper() + ext))
candidates.append(os.path.join(self.assets_dir, player_name.lower() + ext))
for path in candidates:
if path and os.path.exists(path):
return path
if os.path.isdir(self.assets_dir):
wanted = {os.path.basename(path).lower() for path in candidates if path}
for filename in os.listdir(self.assets_dir):
if filename.lower() in wanted:
path = os.path.join(self.assets_dir, filename)
if os.path.exists(path):
return path
return None
def _normalize_card_type(self, card_type: str) -> str:
key = self._slug(card_type)
aliases = {
"court": "court_case",
"courtcase": "court_case",
"ballloser": "ball_loser",
"who_sold": "fraud",
"worst": "fraud",
}
key = aliases.get(key, key)
if key not in THEMES:
raise ValueError(f"Unknown card type: {card_type}")
return key
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
def _cache_key(
self,
card_type: str,
player_name: str,
nickname: str,
position: str,
rating: int,
stats: Dict[str, str],
asset_path: Optional[str],
) -> str:
payload = {
"card_type": card_type,
"player_name": player_name,
"nickname": nickname,
"position": position,
"rating": rating,
"stats": stats,
"asset_path": asset_path,
"asset_mtime": os.path.getmtime(asset_path) if asset_path and os.path.exists(asset_path) else None,
}
raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
return hashlib.sha256(raw.encode("utf-8")).hexdigest()
def _cache_valid(self, output_path: str, meta_path: str, cache_key: str) -> bool:
if not os.path.exists(output_path) or not os.path.exists(meta_path):
return False
try:
with open(meta_path, "r", encoding="utf-8") as file:
meta = json.load(file)
return meta.get("cache_key") == cache_key
except Exception:
return False
def _font(self, size: int, bold: bool = False):
paths = []
if bold:
paths.extend(
[
"/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
"/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
"arialbd.ttf",
]
)
else:
paths.extend(
[
"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
"/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
"arial.ttf",
]
)
for path in paths:
try:
return ImageFont.truetype(path, size=size)
except Exception:
pass
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
text = re.sub(r"+", "", text)
text = text.strip("_")
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
