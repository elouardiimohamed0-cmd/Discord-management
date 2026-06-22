#!/usr/bin/env python3
"""
Safe Phase 2 recovery + patcher for Discord-management.

What this script does:
1. Backs up current bot.py and image_gen.py.
2. Downloads clean upstream bot.py and image_gen.py from GitHub.
3. Applies ONLY the intended Phase 2 fixes:
   - bot.py:
     B12: resolve_image_path becomes case-insensitive and supports more extensions.
     B3: !worst and /worst use darija.roast(worst, "fraud") instead of passing position.
   - image_gen.py:
     B4/B11: local squad image photo_path is primary, Fal AI is fallback.
4. Writes patched bot.py and image_gen.py.
5. Runs py_compile safety checks.

It does NOT touch:
- stats_engine.py
- memory.py
- darija_engine.py
- scraper
- database
- Playwright
- .env
"""

from __future__ import annotations

import datetime
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
​
RAW_BASE = "https://raw.githubusercontent.com/elouardiimohamed0-cmd/Discord-management/main"
ROOT = Path(file).resolve().parent
BOT_PATH = ROOT / "bot.py"
IMAGE_GEN_PATH = ROOT / "image_gen.py"
def log(msg: str) -> None:
print(f"[phase2-safe] {msg}")
def download_text(url: str) -> str:
log(f"Downloading {url}")
with urllib.request.urlopen(url, timeout=30) as response:
return response.read().decode("utf-8")
def backup(path: Path) -> None:
if not path.exists():
log(f"Backup skipped, file does not exist: {path.name}")
return
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
backup_path = path.with_suffix(path.suffix + f".before-phase2-safe-{stamp}.bak")
shutil.copy2(path, backup_path)
log(f"Backed up {path.name} -> {backup_path.name}")
def patch_bot_py(src: str) -> str:
"""
Apply safe bot.py Phase 2 fixes:
replace resolve_image_path function
fix two worst roast routing lines
"""
new_resolve = '''def resolve_image_path(photo_path: str) -> Optional[str]:
"""
Resolve a squad image path safely.
Phase 2 fix:
exact path still wins
supports jpg/jpeg/png/webp extension fallbacks
supports case-insensitive filename lookup inside the target directory
This keeps squad.json as the source of truth for nickname/image only.
It does NOT force absent squad players and does NOT include opponents.
"""
if not photo_path:
return None
1) Exact path
if os.path.exists(photo_path):
return photo_path
base, ext = os.path.splitext(photo_path)
ext_lower = ext.lower()
2) Extension fallbacks
candidate_exts = [".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG", ".WEBP"]
candidates = []
if ext:
for candidate_ext in candidate_exts:
candidates.append(base + candidate_ext)
else:
for candidate_ext in candidate_exts:
candidates.append(photo_path + candidate_ext)
for candidate in candidates:
if os.path.exists(candidate):
return candidate
3) Case-insensitive directory scan
directory = os.path.dirname(photo_path) or "."
filename = os.path.basename(photo_path)
if not os.path.isdir(directory):
return None
wanted_names = {filename.lower()}
wanted_base, wanted_ext = os.path.splitext(filename)
if wanted_ext:
for candidate_ext in candidate_exts:
wanted_names.add((wanted_base + candidate_ext).lower())
else:
for candidate_ext in candidate_exts:
wanted_names.add((filename + candidate_ext).lower())
try:
for existing_name in os.listdir(directory):
if existing_name.lower() in wanted_names:
resolved = os.path.join(directory, existing_name)
if os.path.exists(resolved):
return resolved
except OSError:
return None
return None
'''
pattern = re.compile(
r'^def resolve_image_path(photo_path: str) -> Optional[str]:n'
r'(?:^[ t].n|^s$)*?',
re.MULTILINE,
)
match = pattern.search(src)
if not match:
raise RuntimeError("Could not find resolve_image_path() in bot.py")
src = src[:match.start()] + new_resolve + src[match.end():]
Fix both prefix !worst and slash /worst.
old_pattern = re.compile(
r'(?m)^([ t]*)pos = get_squad_map().get(worst.name, {}).get("position", "CM")n'
r'^1roast = darija.roast(worst, pos)'
)
replacement = (
r'1# Worst player should use a fraud-style roast. '
r'Passing the position here makes DarijaEngine fall back to the wrong roast pool.n'
r'1roast = darija.roast(worst, "fraud")'
)
src, count = old_pattern.subn(replacement, src)
if count != 2:
raise RuntimeError(
f"Expected to patch exactly 2 worst roast call sites in bot.py, patched {count}"
)
log("Patched bot.py: resolve_image_path + 2 worst roast call sites")
return src
def patch_image_gen_py(src: str) -> str:
"""
Apply safe image_gen.py Phase 2 fixes:
generate_player_photo_card: local photo_path primary, Fal fallback
generate_daily_card: local photo_path primary, Fal fallback
This avoids replacing the full 600+ line file and keeps the rest unchanged.
"""
───────────────────────────────────────────
Patch generate_player_photo_card photo source block
───────────────────────────────────────────
old_player_block_pattern = re.compile(
r'(?s)'
r'[ t]*# ─── FAL AI PHOTO IS PRIMARY ───n'
r'[ t]*card_type = LABEL_TO_TEMPLATE.get(label, "player")n'
r'[ t]*photo = Nonenn'
r'[ t]*# Try Fal firstn'
r'[ t]*ai_bytes = self._generate_ai_photo(player.name, card_type)n'
r'[ t]*if ai_bytes:n'
r'[ t]*try:n'
r'[ t]*ai_img = Image.open(io.BytesIO(ai_bytes)).convert("RGBA")n'
r'[ t]*ai_img.thumbnail((photo_max_w, photo_max_h), Image.LANCZOS)n'
r'[ t]*photo = ai_imgn'
r'[ t]*logger.info("[PHOTO] Using Fal AI photo for %s", player.name)n'
r'[ t]*except Exception as e:n'
r'[ t]*logger.error("[PHOTO] Failed to load Fal image: %s", e)nn'
)
new_player_block = '''    # ─── LOCAL SQUAD PHOTO IS PRIMARY, FAL AI IS FALLBACK ───
card_type = LABEL_TO_TEMPLATE.get(label, "player")
photo = None
1) Try local squad photo first
if photo_path and os.path.exists(photo_path):
try:
local_img = Image.open(photo_path).convert("RGBA")
local_img.thumbnail((photo_max_w, photo_max_h), Image.LANCZOS)
photo = local_img
logger.info("[PHOTO] Using local squad photo for %s: %s", player.name, photo_path)
except Exception as e:
logger.error("[PHOTO] Failed to load local image %s: %s", photo_path, e)
photo = None
2) Fal AI fallback only if local photo is missing/unreadable
if photo is None:
ai_bytes = self._generate_ai_photo(player.name, card_type)
if ai_bytes:
try:
ai_img = Image.open(io.BytesIO(ai_bytes)).convert("RGBA")
ai_img.thumbnail((photo_max_w, photo_max_h), Image.LANCZOS)
photo = ai_img
logger.info("[PHOTO] Using Fal AI fallback photo for %s", player.name)
except Exception as e:
logger.error("[PHOTO] Failed to load Fal image: %s", e)
'''
src, count_player = old_player_block_pattern.subn(new_player_block, src)
if count_player != 1:
raise RuntimeError(
f"Expected to patch 1 generate_player_photo_card photo block, patched {count_player}"
)
Update misleading comments/docstring if present.
src = src.replace(
'# PHOTO-ONLY PLAYER CARD (Fal AI primary)',
'# PHOTO-ONLY PLAYER CARD (local squad photo primary, Fal AI fallback)',
)
src = src.replace(
'"""Clean photo card. Fal AI photo is PRIMARY. No local file fallback."""',
'"""Clean photo card. Local squad photo is PRIMARY. Fal AI is fallback."""',
)
───────────────────────────────────────────
Patch generate_daily_card source block
───────────────────────────────────────────
old_daily_block_pattern = re.compile(
r'(?s)'
r'[ t]*# Fal AI photo for daily cardn'
r'[ t]*card_type = "mvp" if not is_bad else "fraud"n'
r'[ t]*ai_bytes = self._generate_ai_photo(player.name, card_type)n'
r'[ t]*if ai_bytes:n'
)
new_daily_block = '''    # Local squad photo is primary for daily card; Fal AI is fallback
card_type = "mvp" if not is_bad else "fraud"
ai_bytes = None
if photo_path and os.path.exists(photo_path):
try:
with open(photo_path, "rb") as f:
ai_bytes = f.read()
logger.info("[PHOTO] Using local squad photo for daily card %s: %s", player.name, photo_path)
except Exception as e:
logger.error("[PHOTO] Daily card local image failed: %s", e)
ai_bytes = None
if ai_bytes is None:
ai_bytes = self._generate_ai_photo(player.name, card_type)
if ai_bytes:
'''
src, count_daily = old_daily_block_pattern.subn(new_daily_block, src)
if count_daily != 1:
raise RuntimeError(
f"Expected to patch 1 generate_daily_card photo block, patched {count_daily}"
)
log("Patched image_gen.py: local photo primary + Fal fallback")
return src
def write_file(path: Path, content: str) -> None:
path.write_text(content, encoding="utf-8")
log(f"Wrote {path.name}")
def compile_check(paths: list[Path]) -> None:
for path in paths:
log(f"Compiling {path.name}")
result = subprocess.run(
[sys.executable, "-m", "py_compile", str(path)],
cwd=str(ROOT),
text=True,
capture_output=True,
)
if result.returncode != 0:
print(result.stdout)
print(result.stderr)
raise RuntimeError(f"py_compile failed for {path.name}")
log(f"Compile OK: {path.name}")
def main() -> int:
log("Starting safe Phase 2 recovery")
backup(BOT_PATH)
backup(IMAGE_GEN_PATH)
bot_src = download_text(f"{RAW_BASE}/bot.py")
image_src = download_text(f"{RAW_BASE}/image_gen.py")
patched_bot = patch_bot_py(bot_src)
patched_image = patch_image_gen_py(image_src)
write_file(BOT_PATH, patched_bot)
write_file(IMAGE_GEN_PATH, patched_image)
compile_targets = [BOT_PATH, IMAGE_GEN_PATH]
If user already applied Phase 1 / Phase 3 files, compile-check them too when present.
for optional_name in ["stats_engine.py", "memory.py", "darija_engine.py"]:
optional_path = ROOT / optional_name
if optional_path.exists():
compile_targets.append(optional_path)
compile_check(compile_targets)
log("SUCCESS: Phase 2 safe files are ready.")
log("Next: deploy with: fly deploy -a discord-management --config fly.toml")
return 0
if name == "main":
try:
raise SystemExit(main())
except Exception as exc:
print(f"n[phase2-safe] ERROR: {exc}", file=sys.stderr)
print("[phase2-safe] No deploy was run. Fix the error above first.", file=sys.stderr)
raise SystemExit(1)
