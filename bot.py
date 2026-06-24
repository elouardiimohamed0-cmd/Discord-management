try:
 import auto_templates
 AUTO_TEMPLATES_AVAILABLE = True
except ImportError:
 AUTO_TEMPLATES_AVAILABLE = False

import os
import io  # ✅ needed for io.BytesIO in _maybe_send_video
import sys
import asyncio
import logging
import traceback
import time
import json
import hashlib  # ✅ needed for video cache + match fingerprint
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import Config, load_squad
from scraper_service import ScraperService
from stats_engine import StatsEngine
from darija_engine import DarijaEngine
from image_gen import ImageGenerator
from memory import SquadMemory
from daily_engine import DailyEngine
from story_engine import StoryEngine
from models import ClubStats, PlayerStats, MatchResult
from utils import fuzzy_find_player

# ── PHASE 4 imports (defensive — bot won't crash if files missing) ──
PHASE4_AVAILABLE = False
FraudScoreSystem = None
CarryScoreSystem = None
GhostScoreSystem = None
HallOfShame = None
HallOfFame = None
RivalrySystem = None
WeeklyAwards = None
MilestoneTracker = None
ExcusesEngine = None
MatchPosterEngine = None
generate_match_poster = None
generate_hall_of_shame_card = None
generate_hall_of_fame_card = None
generate_rivalry_card = None
generate_milestone_card = None
generate_weekly_awards_card = None

try:
 from ecosystem_engine import (
  FraudScoreSystem, CarryScoreSystem, GhostScoreSystem,
  HallOfShame, HallOfFame, RivalrySystem, WeeklyAwards,
  MilestoneTracker, ExcusesEngine, MatchPosterEngine
 )
 from image_gen_ecosystem import (
  generate_match_poster, generate_hall_of_shame_card,
  generate_hall_of_fame_card, generate_rivalry_card,
  generate_milestone_card, generate_weekly_awards_card
 )
 PHASE4_AVAILABLE = True
 print("[PHASE4] Ecosystem engine loaded successfully")
except Exception as e:
 print(f"[PHASE4] Could not load ecosystem engine: {e}. Phase 4 commands disabled.")

# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
 level=logging.INFO,
 format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
 handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("rachad_bot")

# ─────────────────────────────────────────────────────────────
# MATCH POST DEDUPE (prevents reposting same match repeatedly)
# ─────────────────────────────────────────────────────────────
_LAST_POST_FP_PATH = os.getenv("LAST_MATCH_FP_PATH", "/tmp/rachad_last_match_fp.json")

def _match_fingerprint(m: MatchResult) -> str:
 """
 Stable fingerprint for a match so we don't repost the same one forever.
 """
 if not m:
  return ""
 try:
  opp = str(getattr(m, "opponent", "") or "")
  sf = int(getattr(m, "score_for", 0) or 0)
  sa = int(getattr(m, "score_against", 0) or 0)
  res = str(getattr(m, "result", "") or "")

  dt = getattr(m, "date", None)
  if isinstance(dt, datetime):
   dt_key = dt.replace(second=0, microsecond=0).isoformat()
  else:
   dt_key = str(dt or "")

  ps = getattr(m, "player_stats", None) or {}
  ps_count = len(ps) if isinstance(ps, dict) else 0

  raw = f"{opp}|{sf}|{sa}|{res}|{dt_key}|{ps_count}"
  return hashlib.sha256(raw.encode("utf-8")).hexdigest()
 except Exception:
  return ""

def _load_last_posted_fp() -> str:
 try:
  if not os.path.exists(_LAST_POST_FP_PATH):
   return ""
  with open(_LAST_POST_FP_PATH, "r", encoding="utf-8") as f:
   data = json.load(f)
  return str(data.get("fp", "") or "")
 except Exception:
  return ""

def _save_last_posted_fp(fp: str) -> None:
 try:
  with open(_LAST_POST_FP_PATH, "w", encoding="utf-8") as f:
   json.dump({"fp": fp, "saved_at": datetime.now().isoformat()}, f)
 except Exception:
  pass

_last_posted_match_fp = _load_last_posted_fp()

# ─────────────────────────────────────────────────────────────
# INSTANCE LOCK
# ─────────────────────────────────────────────────────────────
class InstanceLock:
 def __init__(self, path="/tmp/rachad_bot.lock"):
  self.path = path
  self.fd = None
 def acquire(self):
  import fcntl
  self.fd = open(self.path, "w")
  try:
   fcntl.lockf(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
   self.fd.write(str(os.getpid()))
   self.fd.flush()
   logger.info("Lock acquired (pid %s)", os.getpid())
   return True
  except (IOError, OSError):
   logger.error("Another instance running! Exiting.")
   return False
 def release(self):
  if self.fd:
   self.fd.close()

_instance_lock = InstanceLock()
if not _instance_lock.acquire():
 sys.exit(0)

# ─────────────────────────────────────────────────────────────
# RATE-LIMIT SENDER
# ─────────────────────────────────────────────────────────────
class DiscordRateLimiter:
 def __init__(self, max_429=5, circuit_seconds=300):
  self._consecutive_429 = 0
  self._max = max_429
  self._circuit_seconds = circuit_seconds
  self._circuit_open_until = 0
  self._lock = asyncio.Lock()

 async def _send(self, send_fn, *args, **kwargs):
  async with self._lock:
   if time.time() < self._circuit_open_until:
    logger.warning("Circuit breaker OPEN — skipping send")
    return None
   max_retries = 5
   base = 1.0
   for attempt in range(max_retries):
    try:
     result = await send_fn(*args, **kwargs)
     self._consecutive_429 = 0
     return result
    except discord.HTTPException as e:
     if e.status == 429:
      self._consecutive_429 += 1
      retry_after = getattr(e, "retry_after", base * (2 ** attempt))
      logger.warning("Discord 429 (attempt %d/%d). Retry after %.1fs", attempt + 1, max_retries, retry_after)
      if self._consecutive_429 >= self._max:
       logger.error("Too many 429s. Circuit breaker %ds", self._circuit_seconds)
       self._circuit_open_until = time.time() + self._circuit_seconds
       return None
      await asyncio.sleep(retry_after + 0.5)
     else:
      raise
    except Exception as e:
     logger.error("Send error: %s", e)
     raise
   logger.error("Max retries exceeded")
   return None

 async def ctx_send(self, ctx, *args, **kwargs):
  logger.info("[SEND] ctx.send #%s by %s", getattr(ctx.channel, "name", "?"), ctx.author.name)
  return await self._send(ctx.send, *args, **kwargs)

 async def interaction_send(self, interaction, *args, **kwargs):
  logger.info("[SEND] interaction by %s", interaction.user.name)
  if interaction.response.is_done():
   return await self._send(interaction.followup.send, *args, **kwargs)
  return await self._send(interaction.response.send_message, *args, **kwargs)

 async def channel_send(self, channel, *args, **kwargs):
  logger.info("[SEND] channel.send #%s", getattr(channel, "name", "?"))
  return await self._send(channel.send, *args, **kwargs)

rl = DiscordRateLimiter()

# ─────────────────────────────────────────────────────────────
# HEALTH SERVER
# ─────────────────────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200)
  self.send_header("Content-Type", "text/plain")
  self.end_headers()
  self.wfile.write(b"OK")
 def log_message(self, format, *args):
  pass

def start_health_server():
 try:
  server = HTTPServer(("0.0.0.0", Config.PORT), HealthHandler)
  t = threading.Thread(target=server.serve_forever, daemon=True)
  t.start()
  logger.info("Health server on port %s", Config.PORT)
 except Exception as e:
  logger.error("Health server error: %s", e)

start_health_server()

# ─────────────────────────────────────────────────────────────
# NICKNAME SYSTEM
# ─────────────────────────────────────────────────────────────
PSN_TO_NICKNAME = {}
NICKNAME_TO_PSN = {}

def _build_nickname_maps():
 global PSN_TO_NICKNAME, NICKNAME_TO_PSN
 PSN_TO_NICKNAME.clear()
 NICKNAME_TO_PSN.clear()
 players_iter = []
 if isinstance(squad, dict):
  if "players" in squad:
   players_iter = squad.get("players", [])
  else:
   players_iter = squad.values()
 elif isinstance(squad, list):
  players_iter = squad
 for p in players_iter:
  if not isinstance(p, dict):
   continue
  psn = p.get("psn", "") or p.get("PSN", "") or p.get("ea_id", "")
  nickname = p.get("name", "") or p.get("nickname", "")
  if psn and nickname:
   PSN_TO_NICKNAME[psn.lower()] = nickname
   NICKNAME_TO_PSN[nickname.lower()] = psn
 logger.info("[SQUAD] Nickname maps built: %d PSN->name, %d name->PSN",
  len(PSN_TO_NICKNAME), len(NICKNAME_TO_PSN))

def resolve_nickname(name):
 if not name or not isinstance(name, str):
  return name
 return PSN_TO_NICKNAME.get(name.lower(), name)

def resolve_query(query):
 if not query or not isinstance(query, str):
  return query
 return NICKNAME_TO_PSN.get(query.lower(), query)

def normalize_club_players(club):
 if not club or not getattr(club, "players", None):
  return
 for p in club.players:
  if hasattr(p, "name"):
   if not p.name or not isinstance(p.name, str) or not p.name.strip():
    p.name = "Unknown"
   else:
    resolved = resolve_nickname(p.name.strip())
    if resolved and isinstance(resolved, str) and resolved.strip():
     p.name = resolved.strip()
    else:
     p.name = p.name.strip()

# ─── MATCH-ONLY PLAYER FILTER ───
def _find_player_match_stats(latest: MatchResult, player: PlayerStats) -> Optional[dict]:
    """
    Return match.player_stats dict for this player (latest match).
    Uses _raw_psn first then name; includes contains fallback.
    """
    if not latest or not getattr(latest, "player_stats", None):
        return None
    ps = latest.player_stats or {}
    if not isinstance(ps, dict) or not ps:
        return None

    raw_psn = (getattr(player, "_raw_psn", "") or "").strip().lower()
    name = (getattr(player, "name", "") or "").strip().lower()

    for k, v in ps.items():
        if not isinstance(k, str):
            continue
        kl = k.strip().lower()
        if raw_psn and kl == raw_psn:
            return v
        if name and kl == name:
            return v

    for k, v in ps.items():
        if not isinstance(k, str):
            continue
        kl = k.strip().lower()
        if raw_psn and (raw_psn in kl or kl in raw_psn):
            return v
        if name and (name in kl or kl in name):
            return v

    return None

 raw_psn = (getattr(player, "_raw_psn", "") or "").strip().lower()
 name = (getattr(player, "name", "") or "").strip().lower()

 for k, v in ps.items():
  if not isinstance(k, str):
   continue
  kl = k.strip().lower()
  if raw_psn and kl == raw_psn:
   return v
  if name and kl == name:
   return v

 for k, v in ps.items():
  if not isinstance(k, str):
   continue
  kl = k.strip().lower()
  if raw_psn and (raw_psn in kl or kl in raw_psn):
   return v
  if name and (name in kl or kl in name):
   return v

 return None

# ─────────────────────────────────────────────────────────────
# BOT SETUP
# ─────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
 command_prefix="!",
 intents=intents,
 help_command=None,
 max_messages=10000,
)

squad = load_squad()
_build_nickname_maps()
scraper = ScraperService()
darija = DarijaEngine(squad)  # FIX: was Config.DEFAULT_PERSONALITY
imgen = ImageGenerator(Config.ASSETS_DIR)
memory = SquadMemory()
daily_engine = DailyEngine(darija)
story_engine = StoryEngine()
current_club = None
_session_active = False
_slash_synced = False
_startup_scrape_done = False
_data_cache_time = 0
DATA_CACHE_TTL = 600

# ─────────────────────────────────────────────────────────────
# DATA CONVERSION
# ─────────────────────────────────────────────────────────────
def resolve_image_path(photo_path: str) -> Optional[str]:
 if not photo_path:
  return None
 if os.path.exists(photo_path):
  return photo_path
 base, ext = os.path.splitext(photo_path)
 alts = []
 if ext.lower() == ".jpg":
  alts = [base + ".jpeg", base + ".JPEG", base + ".JPG"]
 elif ext.lower() == ".jpeg":
  alts = [base + ".jpg", base + ".JPG", base + ".JPEG"]
 elif ext.lower() == ".png":
  alts = [base + ".jpg", base + ".jpeg"]
 for alt in alts:
  if os.path.exists(alt):
   return alt
 return None

def get_squad_display_name(player_name: str) -> str:
 if not player_name or not isinstance(player_name, str):
  return player_name or "Unknown"
 sq = get_squad_map()
 for sq_name, info in sq.items():
  if sq_name and sq_name.lower() == player_name.strip().lower():
   return info.get("name", sq_name)
 for sq_name, info in sq.items():
  if sq_name and sq_name.lower() in player_name.lower():
   return info.get("name", sq_name)
 for sq_name, info in sq.items():
  if sq_name and player_name.lower() in sq_name.lower():
   return info.get("name", sq_name)
 return player_name

def _dict_to_club(data: dict) -> Optional[ClubStats]:
 if not data:
  return None
 try:
  club = ClubStats(
   club_name=data.get("club_name") or "Rachad L3ERGONI",
   division=data.get("division") or 6,
   skill_rating=data.get("skill_rating") or 0,
   wins=data.get("wins") or 0,
   losses=data.get("losses") or 0,
   draws=data.get("draws") or 0,
  )
  club.goals_scored = data.get("goals_scored") or 0
  club.goals_conceded = data.get("goals_conceded") or 0
  club.win_rate = data.get("win_rate") or 0.0
  club.last_updated = datetime.now()

  club.players = []
  for p in data.get("players", []):
   raw_name = p.get("name")
   pro_name = p.get("pro_name", "")
   psn_name = p.get("psn_name", "")
   if not raw_name or not isinstance(raw_name, str) or not raw_name.strip():
    raw_name = "Unknown"
   pct_name = raw_name.strip()

   sq_info = get_squad_info(pct_name)
   if not sq_info and pro_name:
    sq_info = get_squad_info(pro_name)
   if not sq_info and psn_name:
    sq_info = get_squad_info(psn_name)

   if sq_info:
    display_name = sq_info.get("name") or pct_name
    ps = PlayerStats(name=display_name)
    ps._squad_info = sq_info
   else:
    ps = PlayerStats(name=pct_name)
    ps._squad_info = {}

   ps._raw_psn = psn_name or pct_name

   for k, v in p.items():
    if hasattr(ps, k) and k != "name":
     setattr(ps, k, v)
   club.players.append(ps)

  club.matches = []
  for m in data.get("matches", []):
   try:
    date_val = m.get("date", datetime.now().isoformat())
    if isinstance(date_val, str):
     date_val = datetime.fromisoformat(date_val)
    mr = MatchResult(
     match_id=m.get("match_id", ""),
     date=date_val,
     opponent=m.get("opponent", "Unknown"),
     score_for=m.get("score_for", 0),
     score_against=m.get("score_against", 0),
     result=m.get("result", "D"),
     player_stats=m.get("player_stats", {}),
    )
    club.matches.append(mr)
   except Exception:
    pass
  return club
 except Exception as e:
  logger.error("Dict->Club conversion error: %s", e)
  return None

def get_squad_map():
 result = {}
 if isinstance(squad, dict):
  if "players" in squad:
   result = {p.get("name", ""): p for p in squad.get("players", []) if isinstance(p, dict)}
  else:
   result = {p.get("name", ""): p for p in squad.values() if isinstance(p, dict)}
 if not result:
  logger.warning("[SQUAD] squad.json loaded but get_squad_map() returned empty.")
 else:
  logger.info("[SQUAD] Loaded %d players from squad.json", len(result))
 return result

def get_squad_info(pct_name: str) -> dict:
 if not pct_name or not isinstance(pct_name, str):
  return {}
 sq = get_squad_map()
 pct_lower = pct_name.strip().lower()

 for sq_name, info in sq.items():
  if sq_name and sq_name.lower() == pct_lower:
   return info

 for info in sq.values():
  psn = (info.get("psn") or "").strip().lower()
  if psn and psn == pct_lower:
   return info

 for info in sq.values():
  pro = (info.get("proName") or info.get("ea_id") or "").strip().lower()
  if pro and pro == pct_lower:
   return info

 for sq_name, info in sq.items():
  if sq_name and (pct_lower in sq_name.lower() or sq_name.lower() in pct_lower):
   return info

 return {}

def _name_similarity(a: str, b: str) -> float:
 if not a or not b:
  return 0.0
 a, b = a.lower().strip(), b.lower().strip()
 if a == b:
  return 1.0
 if a in b or b in a:
  return max(len(a), len(b)) / max(len(a), len(b), 1) * 0.8
 common = sum((a + b).count(c) for c in set(a) & set(b))
 return common / max(len(a) + len(b), 1)

def find_player(query: str) -> Optional[PlayerStats]:
 if not current_club or not current_club.players:
  return None
 if not query or not isinstance(query, str):
  return None

 query_clean = query.strip().lower()
 players = current_club.players
 squad_map = get_squad_map()

 for p in players:
  name = getattr(p, "name", "")
  if name and isinstance(name, str) and name.strip().lower() == query_clean:
   return p

 resolved = resolve_query(query)
 if resolved and resolved.lower() != query_clean:
  for p in players:
   name = getattr(p, "name", "")
   if name and isinstance(name, str) and name.strip().lower() == resolved.lower().strip():
    return p

 for p in players:
  name = getattr(p, "name", "")
  if name and isinstance(name, str) and query_clean in name.strip().lower():
   return p

 for p in players:
  name = getattr(p, "name", "")
  if not name or not isinstance(name, str):
   continue
  info = squad_map.get(name.strip(), {})
  sq_name = (info.get("name") or "").strip().lower()
  if query_clean in sq_name or sq_name == query_clean:
   return p
  sq_psn = (info.get("psn") or info.get("PSN") or "").strip().lower()
  if query_clean in sq_psn or sq_psn == query_clean:
   return p
  sq_nick = (info.get("nickname") or "").strip().lower()
  if query_clean in sq_nick or sq_nick == query_clean:
   return p
  sq_pro = (info.get("proName") or "").strip().lower()
  if query_clean in sq_pro or sq_pro == query_clean:
   return p

 for sq_name, info in squad_map.items():
  sq_psn = (info.get("psn") or info.get("PSN") or "").strip().lower()
  sq_nick = (info.get("nickname") or "").strip().lower()
  sq_pro = (info.get("proName") or "").strip().lower()
  if query_clean == sq_psn or query_clean == sq_nick or query_clean == sq_pro or query_clean in sq_psn or query_clean in sq_nick or query_clean in sq_pro:
   for p in players:
    p_name = getattr(p, "name", "")
    if p_name and isinstance(p_name, str) and p_name.strip().lower() == sq_name.lower().strip():
     return p

 best_match = None
 best_score = 0.0
 for p in players:
  name = getattr(p, "name", "")
  if not name or not isinstance(name, str):
   continue
  score = _name_similarity(query_clean, name.strip())
  info = squad_map.get(name.strip(), {})
  for alias in [info.get("name"), info.get("psn"), info.get("PSN"), info.get("nickname"), info.get("proName")]:
   if alias and isinstance(alias, str):
    score = max(score, _name_similarity(query_clean, alias.strip()))
  if score > best_score:
   best_score = score
   best_match = p

 if best_score >= 0.5:
  logger.info("[FIND] Fuzzy match '%s' -> '%s' (score %.2f)", query, getattr(best_match, "name", "?"), best_score)
  return best_match

 logger.info("[FIND] No match found for '%s' among %d players", query, len(players))
 return None

def _is_data_fresh() -> bool:
 return current_club is not None and current_club.players and (time.time() - _data_cache_time) < DATA_CACHE_TTL

async def _fetch_club_data(force=False, source="background"):
 global current_club, _data_cache_time
 try:
  data = await scraper.get_club_data(force=force, source=source)
  if data:
   club = _dict_to_club(data)
   if club and club.players:
    current_club = club
    current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
    normalize_club_players(current_club)
    _data_cache_time = time.time()
    logger.info("Data loaded: %d players, %d matches", len(club.players), len(club.matches))
    return current_club
 except Exception as e:
  logger.error("Fetch error: %s", e)
  traceback.print_exc()
 return None

async def ensure_data(ctx: commands.Context):
 if _is_data_fresh():
  return True
 if current_club and current_club.players:
  valid_players = [p for p in current_club.players if getattr(p, "name", None) and isinstance(p.name, str) and p.name.strip()]
  if len(valid_players) > 0:
   return True
 await rl.ctx_send(ctx, "⏳ Data not loaded yet. Background sync in progress. Try again in a few minutes.")
 return False

async def ensure_data_interaction(interaction: discord.Interaction):
 if _is_data_fresh():
  return True
 if current_club and current_club.players:
  valid_players = [p for p in current_club.players if getattr(p, "name", None) and isinstance(p.name, str) and p.name.strip()]
  if len(valid_players) > 0:
   return True
 await rl.interaction_send(interaction, "⏳ Data not loaded yet. Background sync in progress. Try again in a few minutes.")
 return False

# ─────────────────────────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
 global _slash_synced, _startup_scrape_done
 logger.info("Bot online as %s", bot.user)
 await bot.change_presence(activity=discord.Game(name="!help or /help"))

 if not _slash_synced:
  try:
   guild = discord.Object(id=Config.DISCORD_GUILD_ID)
   bot.tree.copy_global_to(guild=guild)
   await bot.tree.sync(guild=guild)
   _slash_synced = True
   logger.info("Slash synced to guild %s", Config.DISCORD_GUILD_ID)
  except discord.HTTPException as e:
   if e.status == 429:
    logger.warning("Slash sync rate limited. Will retry on reconnect.")
    _slash_synced = False
   else:
    logger.error("Slash sync error: %s", e)
  except Exception as e:
   logger.error("Slash sync error: %s", e)

 if not _startup_scrape_done:
  asyncio.create_task(startup_scrape())
  _startup_scrape_done = True

 if not match_monitor.is_running():
  match_monitor.start()
  logger.info("Match monitor started")

 # ── PHASE 4 tasks (only if available) ──
 if PHASE4_AVAILABLE:
  if not weekly_awards_task.is_running():
   weekly_awards_task.start()
   logger.info("Weekly awards task started")
  if not milestone_monitor.is_running():
   milestone_monitor.start()
   logger.info("Milestone monitor started")
 else:
  logger.warning("[PHASE4] Tasks not started — ecosystem engine not available")

@bot.event
async def on_disconnect():
 logger.warning("Bot disconnected")

@bot.event
async def on_resumed():
 logger.info("Bot resumed")

async def startup_scrape():
 try:
  logger.info("Startup scrape...")
  await asyncio.sleep(5)
  await _fetch_club_data(force=False, source="startup")
 except Exception as e:
  logger.error("Startup scrape: %s", e)

@bot.event
async def on_command_error(ctx, error):
 if isinstance(error, commands.CommandNotFound):
  await rl.ctx_send(ctx, "هاد الكوماند ما كاينش. جرب !help.")
  return
 if isinstance(error, commands.MissingRequiredArgument):
  await rl.ctx_send(ctx, f"ناقصك parameter: {error.param.name}.")
  return
 if isinstance(error, commands.NotOwner):
  await rl.ctx_send(ctx, "غير الowner.")
  return
 if isinstance(error, commands.CommandOnCooldown):
  await rl.ctx_send(ctx, f"⏳ Cooldown: wait {error.retry_after:.1f}s.")
  return
 logger.error("Prefix error: %s", error)
 traceback.print_exc()
 await rl.ctx_send(ctx, f"Error: {str(error)[:300]}")

@bot.tree.error
async def on_app_command_error(interaction, error):
 logger.error("Slash error: %s", error)
 traceback.print_exc()
 msg = f"Error: {str(error)[:500]}"
 try:
  if isinstance(error, app_commands.CommandOnCooldown):
   msg = f"⏳ Cooldown: wait {error.retry_after:.1f}s."
  await rl.interaction_send(interaction, msg)
 except Exception:
  pass

@bot.before_invoke
async def log_command(ctx):
 logger.info("[CMD] %s by %s in #%s", ctx.command.name if ctx.command else "?", ctx.author.name, getattr(ctx.channel, "name", "DM"))

# ─────────────────────────────────────────────────────────────
# BACKGROUND TASKS
# ─────────────────────────────────────────────────────────────
@tasks.loop(minutes=10)
async def match_monitor():
 global current_club, _last_posted_match_fp
 try:
  data = await scraper.get_club_data(force=False, source="background")
  if not data:
   logger.warning("Match monitor: no data from scraper")
   return

  club = _dict_to_club(data)
  if not club or not club.matches:
   return

  latest = club.matches[0]
  fp = _match_fingerprint(latest)

  # Update in-memory state always
  current_club = club
  current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
  normalize_club_players(current_club)

  # Don't repost same match forever
  if fp and fp == _last_posted_match_fp:
   logger.info("Match monitor: same latest match fingerprint — skipping post")
   return

  result = f"{latest.score_for}-{latest.score_against}"
  match_players = get_match_players(current_club, latest)
  report = darija.match_report(result, match_players)

  match_ch = getattr(Config, "MATCH_CHANNEL_ID", 0)
  if match_ch:
   ch = bot.get_channel(match_ch)
   if ch:
    await rl.channel_send(ch, report)

  lb_ch = getattr(Config, "LEADERBORD_CHANNEL_ID", 0)
  if lb_ch:
   ch = bot.get_channel(lb_ch)
   if ch:
    color = 0x00ff00 if latest.result == "W" else 0xff0000 if latest.result == "L" else 0xffff00
    embed = discord.Embed(title=f"Match Report: {latest.opponent} {result}", description=report, color=color)
    await rl.channel_send(ch, embed)

  if fp:
   _last_posted_match_fp = fp
   _save_last_posted_fp(fp)

  logger.info("Auto-reported match: %s %s (fp=%s)", latest.opponent, result, fp[:10] if fp else "none")
 except Exception as e:
  logger.error("Match monitor error: %s", e)
  traceback.print_exc()

@match_monitor.before_loop
async def before_match_monitor():
 await bot.wait_until_ready()

# ── PHASE 4 BACKGROUND TASKS ──
@tasks.loop(hours=168)
async def weekly_awards_task():
 global current_club
 if not current_club or not current_club.players:
  return
 try:
  lb_ch = getattr(Config, "LEADERBORD_CHANNEL_ID", 0)
  if not lb_ch:
   return
  ch = bot.get_channel(lb_ch)
  if not ch:
   return
  winners = WeeklyAwards.determine_winners(current_club.players, current_club.matches)
  if not winners:
   return
  week_date = datetime.now().strftime("%d/%m/%Y")
  card = generate_weekly_awards_card(Config.ASSETS_DIR, winners, week_date)
  file = discord.File(card, filename="weekly_awards.png")
  text = WeeklyAwards.format_post(winners)
  embed = discord.Embed(title=f"📅 Weekly Awards — {week_date}", description=text, color=0xffd700)
  await rl.channel_send(ch, embed=embed, file=file)
  for w in winners:
   memory.record_weekly_award(week_date, w["award"], w["player"].name, w["score"], w["description"])
   memory.add_event("weekly", w["player"].name, w["award"], {"score": w["score"], "date": week_date})
  logger.info("Weekly awards posted")
 except Exception as e:
  logger.error("Weekly awards error: %s", e)
  traceback.print_exc()

@weekly_awards_task.before_loop
async def before_weekly_awards():
 await bot.wait_until_ready()
 now = datetime.now()
 days_until_sunday = (6 - now.weekday()) % 7
 if days_until_sunday == 0 and now.hour >= 20:
  days_until_sunday = 7
 target = now + timedelta(days=days_until_sunday)
 target = target.replace(hour=20, minute=0, second=0, microsecond=0)
 wait_seconds = (target - now).total_seconds()
 logger.info("Weekly awards: waiting %ds until %s", wait_seconds, target)
 await asyncio.sleep(wait_seconds)

@tasks.loop(minutes=10)
async def milestone_monitor():
 global current_club
 if not current_club or not current_club.players:
  return
 try:
  lb_ch = getattr(Config, "LEADERBORD_CHANNEL_ID", 0)
  ch = bot.get_channel(lb_ch) if lb_ch else None
  for p in current_club.players:
   already = {}
   for m in memory.get_milestones_alerted(p.name):
    already[m["key"]] = True
   alerts = MilestoneTracker.check_milestones(p, already)
   for alert in alerts:
    if ch:
     text = MilestoneTracker.format_alert(alert)
     card = generate_milestone_card(Config.ASSETS_DIR, alert)
     file = discord.File(card, filename="milestone.png")
     embed = discord.Embed(title="🚨 MILESTONE", description=text, color=0x00ff00)
     await rl.channel_send(ch, embed=embed, file=file)
    memory.record_milestone_alerted(p.name, alert["key"], alert["stat"], alert["threshold"])
    memory.add_event("milestone", p.name, "milestone", alert)
 except Exception as e:
  logger.error("Milestone monitor error: %s", e)

# ─────────────────────────────────────────────────────────────
# PREFIX COMMANDS — existing 21 + Phase 4 (conditional)
# ─────────────────────────────────────────────────────────────
@bot.command(name="ping")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_ping(ctx):
 await rl.ctx_send(ctx, "Pong! Bot is alive. Try !sync next.")

@bot.command(name="debug")
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_debug(ctx):
 scraper_ready = "Yes" if scraper else "No"
 data_loaded = "Yes" if current_club and current_club.players else "No"
 player_count = len(current_club.players) if current_club and current_club.players else 0
 cache_age = int(time.time() - _data_cache_time) if _data_cache_time else "N/A"
 metrics = scraper.metrics()
 db_stats = await scraper.db_stats()
 lines = [
  f"PCT_URL: {Config.PCT_CLUB_URL}",
  f"PORT: {Config.PORT}",
  f"Club ID: {Config.CLUB_ID}",
  f"Scraper ready: {scraper_ready}",
  f"Data loaded: {data_loaded}",
  f"Players: {player_count}",
  f"Cache age: {cache_age}s",
  f"Scraper cooldown: {metrics['cooldown']} ({metrics['cooldown_remaining']}s remaining)",
  f"Scraper rate limited: {metrics['rate_limited']}",
  f"Scraper requests/hour: {metrics['requests_hour']}/{scraper._max_per_hour}",
  f"Scraper last scrape: {metrics['last_scrape_age']}s ago",
  f"Scraper failures: {metrics['failures']}",
  f"DB scrapes (24h): {db_stats.get('total_attempts', 0)} attempts, {db_stats.get('successes', 0)} success, {db_stats.get('failures', 0)} fail",
  f"Phase 4 available: {PHASE4_AVAILABLE}",
 ]
 embed = discord.Embed(title="Debug Info", description="\n".join(lines), color=0x808080)
 await rl.ctx_send(ctx, embed=embed)

@bot.command(name="resync")
@commands.is_owner()
@commands.cooldown(1, 60, commands.BucketType.guild)
async def cmd_resync(ctx):
 async with ctx.typing():
  try:
   guild = discord.Object(id=Config.DISCORD_GUILD_ID)
   bot.tree.clear_commands(guild=guild)
   bot.tree.copy_global_to(guild=guild)
   await bot.tree.sync(guild=guild)
   await rl.ctx_send(ctx, "Slash commands re-synced.")
  except Exception as e:
   await rl.ctx_send(ctx, f"Resync failed: {e}")

@bot.command(name="help")
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_help(ctx):
 embed = discord.Embed(
  title="Rachad L3ERGONI Bot",
  description="الخطوة الأولى: دير !sync أو /sync\n\nبعدها تقدر تستعمل كل شي:",
  color=0x1e90ff
 )
 text = (
  "**Basic:** `!ping` `!debug` `!resync` `!sync`\n\n"
  "**Player Cards:** `!stats [player]` `!player [player]` `!bio [player]`\n\n"
  "**Rankings:** `!mvp` `!worst` `!carry` `!ballon` `!ghost` `!ball_loser` `!playmaker` `!sniper` `!keeper`\n\n"
  "**Roast Engine:** `!fraud [player]` `!who_sold` `!pass` `!court_case [player]` `!hall_of_shame`\n\n"
  "**Compare:** `!compare p1 p2` `!lastmatch` `!recent [1-10]` `!club` `!leaderboard [metric]`\n\n"
  "**Form & Records:** `!form [player] [N]` `!records` `!legend` `!match_report`\n\n"
  "**History:** `!rankings` `!awards`\n\n"
 )
 if PHASE4_AVAILABLE:
  text += (
   "**Ecosystem (Phase 4):** `!hall_of_fame` `!rivalry p1 p2` `!fraud_score [player]` `!carry_score [player]` `!ghost_score [player]` `!excuses [player]` `!match_poster`\n\n"
  )
 text += "**Settings:** `!sync`"
 embed.add_field(name="All Commands", value=text, inline=False)
 await rl.ctx_send(ctx, embed=embed)

@bot.command(name="sync")
@commands.cooldown(1, 30, commands.BucketType.user)
async def cmd_sync(ctx):
 async with ctx.typing():
  try:
   await rl.ctx_send(ctx, "⏳ جاري التحديث من ProClubsTracker...")
   club = await _fetch_club_data(force=True, source="manual_sync")
   if not club or not club.players:
    await rl.ctx_send(ctx, "ما قدرتش نجيب البيانات. Scraper metrics: " + str(scraper.metrics()))
    return
   embed = discord.Embed(
    title="Sync Complete",
    description=f"{len(club.players)} players loaded\nClub: {club.club_name} | Div {club.division}\nRecord: {club.wins}W — {club.losses}L — {club.draws}D",
    color=0x00ff00
   )
   await rl.ctx_send(ctx, embed=embed)
  except Exception as e:
   tb = traceback.format_exc()
   logger.error("SYNC ERROR: %s", tb)
   await rl.ctx_send(ctx, f"Sync failed: {str(e)[:800]}")

# ─── Player commands ──
@bot.command(name="stats")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_stats(ctx, *, player: str):
 if not await ensure_data(ctx): return
 target = find_player(player)
 if not target:
  await rl.ctx_send(ctx, f"ما لقيتش `{player}`.")
  return
 sq_info = getattr(target, "_squad_info", {}) or {}
 pos = sq_info.get("position", "CM")
 raw_img = sq_info.get("image")
 img_path = resolve_image_path(raw_img)
 display_name = target.name
 async with ctx.typing():
  try:
   card = imgen.generate_player_photo_card(target, pos, "gold", "PLAYER PROFILE", photo_path=img_path)
   file = discord.File(card, filename=f"{display_name}.png")
   embed = discord.Embed(title=f"📊 {display_name} — {pos}", color=0x1e90ff)
   embed.add_field(name="Games", value=str(target.games), inline=True)
   embed.add_field(name="Goals", value=str(target.goals), inline=True)
   embed.add_field(name="Assists", value=str(target.assists), inline=True)
   embed.add_field(name="Rating", value=f"{round(target.rating_pg, 1)}", inline=True)
   embed.add_field(name="Pass %", value=f"{round(target.pass_accuracy, 1)}%", inline=True)
   embed.add_field(name="Possession Lost", value=str(target.possession_losses), inline=True)
   embed.add_field(name="Impact", value=str(target.impact_score), inline=True)
   embed.add_field(name="MOTM", value=str(target.motm), inline=True)
   embed.add_field(name="Win %", value=f"{round(target.win_rate, 1)}%", inline=True)
   embed.add_field(name="Tackles", value=str(target.tackles), inline=True)
   await rl.ctx_send(ctx, file=file, embed=embed)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="player")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_player(ctx, *, player: str):
 if not await ensure_data(ctx): return
 target = find_player(player)
 if not target:
  await rl.ctx_send(ctx, f"ما لقيتش `{player}`.")
  return
 sq_info = getattr(target, "_squad_info", {}) or {}
 pos = sq_info.get("position", "CM")
 raw_img = sq_info.get("image")
 img_path = resolve_image_path(raw_img)
 display_name = target.name
 async with ctx.typing():
  try:
   card = imgen.generate_player_photo_card(target, pos, "purple", "PLAYER PROFILE", photo_path=img_path)
   file = discord.File(card, filename=f"{display_name}.png")
   embed = discord.Embed(title=f"👤 {display_name} — {pos}", color=0x1e90ff)
   embed.add_field(name="Games", value=str(target.games), inline=True)
   embed.add_field(name="Goals", value=str(target.goals), inline=True)
   embed.add_field(name="Assists", value=str(target.assists), inline=True)
   embed.add_field(name="Rating", value=f"{round(target.rating_pg, 1)}", inline=True)
   embed.add_field(name="Pass %", value=f"{round(target.pass_accuracy, 1)}%", inline=True)
   embed.add_field(name="Possession Lost", value=str(target.possession_losses), inline=True)
   embed.add_field(name="Impact", value=str(target.impact_score), inline=True)
   embed.add_field(name="MOTM", value=str(target.motm), inline=True)
   await rl.ctx_send(ctx, file=file, embed=embed)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="bio")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_bio(ctx, *, player: str):
 if not await ensure_data(ctx): return
 target = find_player(player)
 if not target:
  await rl.ctx_send(ctx, f"ما لقيتش `{player}`.")
  return
 sq_info = getattr(target, "_squad_info", {}) or {}
 bio_text = sq_info.get("bio", "") or "ما عنديش bio لـ هاد اللاعب."
 pos = sq_info.get("position", "CM")
 raw_img = sq_info.get("image")
 img_path = resolve_image_path(raw_img)
 display_name = target.name
 async with ctx.typing():
  try:
   card = imgen.generate_player_photo_card(target, pos, "gold", "BIO", photo_path=img_path)
   file = discord.File(card, filename=f"{display_name}.png")
   embed = discord.Embed(title=f"📝 BIO — {display_name}", description=bio_text, color=0x00ff7f)
   embed.add_field(name="Position", value=pos, inline=True)
   embed.add_field(name="Nickname", value=sq_info.get("nickname", display_name), inline=True)
   await rl.ctx_send(ctx, file=file, embed=embed)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

async def _maybe_send_video(channel, player, video_type, match_id=None):
 """Send a JSON2Video-generated video to the channel if API is available."""
 if not channel:
  return

 from services.json2video import JSON2VideoClient
 json2video = JSON2VideoClient()
 if not json2video.is_available():
  logger.info("[VIDEO] JSON2Video API key not set, skipping video")
  return

 prompts = {
  "mvp": "Cinematic golden MVP celebration, {name} spotlight, epic slow motion, crowd cheering, 3 seconds",
  "fraud": "Dramatic red fraud exposure, {name} spotlight, comedic shame walk, 3 seconds",
  "ghost": "Ghostly disappearance, {name} fading into purple mist, empty pitch, 3 seconds",
  "carry": "Epic superhuman carry, {name} lifting team, blue energy, cinematic, 3 seconds",
  "court": "Courtroom drama gavel slam, {name} on trial, dramatic lighting, 3 seconds",
  "match": "Epic stadium match intro, floodlights, crowd roar, green pitch, cinematic, 3 seconds",
 }

 name = getattr(player, 'name', 'Player') if player else 'Player'
 prompt = prompts.get(video_type, prompts["mvp"]).format(name=name)

 # ─── VIDEO CACHE ───
 cache_dir = "cache/videos"
 os.makedirs(cache_dir, exist_ok=True)
 safe_name = name.replace(" ", "_").replace("/", "_")
 cache_key = hashlib.md5(f"{safe_name}:{video_type}:{match_id or 'none'}".encode()).hexdigest()
 cache_path = os.path.join(cache_dir, f"{cache_key}.mp4")

 # Check cache first
 if os.path.exists(cache_path):
  try:
   with open(cache_path, "rb") as f:
    video_bytes = f.read()
   file = discord.File(io.BytesIO(video_bytes), filename=f"{safe_name}_{video_type}.mp4")
   await channel.send(file=file)
   logger.info("[VIDEO] Sent cached %s video for %s", video_type, name)
   return
  except Exception as e:
   logger.warning("[VIDEO] Cache read failed, regenerating: %s", e)

 # Generate new video
 try:
  logger.info("[VIDEO] Generating %s video for %s via JSON2Video...", video_type, name)
  video_bytes = await asyncio.to_thread(json2video.generate_video, prompt, duration=5)

  # Save to cache
  with open(cache_path, "wb") as f:
   f.write(video_bytes)

  # Send
  file = discord.File(io.BytesIO(video_bytes), filename=f"{safe_name}_{video_type}.mp4")
  await channel.send(file=file)
  logger.info("[VIDEO] Sent %s video for %s", video_type, name)

 except Exception as e:
  logger.error("[VIDEO] Failed to generate/send video: %s", e)

@bot.command(name="mvp")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_mvp(ctx):
 if not await ensure_data(ctx): return
 async with ctx.typing():
  try:
   mvp = StatsEngine.get_mvp(current_club.players)
   sq_info = getattr(mvp, "_squad_info", {}) or {}
   pos = sq_info.get("position", "CM")
   raw_img = sq_info.get("image")
   img_path = resolve_image_path(raw_img)
   display_name = mvp.name
   card = imgen.generate_player_photo_card(mvp, pos, "gold", "MAN OF THE MATCH", photo_path=img_path)
   file = discord.File(card, filename="mvp.png")
   embed = discord.Embed(title=f"🏆 MAN OF THE MATCH — {display_name}", color=0xffd700)
   embed.add_field(name="Goals", value=str(mvp.goals), inline=True)
   embed.add_field(name="Assists", value=str(mvp.assists), inline=True)
   embed.add_field(name="Rating", value=str(round(mvp.rating_pg, 1)), inline=True)
   embed.add_field(name="Impact", value=str(mvp.impact_score), inline=True)
   embed.add_field(name="Win %", value=f"{round(mvp.win_rate, 1)}%", inline=True)
   await rl.ctx_send(ctx, file=file, embed=embed)
   asyncio.create_task(_maybe_send_video(ctx.channel, mvp, "mvp"))
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="worst")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_worst(ctx):
 if not await ensure_data(ctx): return
 async with ctx.typing():
  try:
   worst = StatsEngine.get_worst(current_club.players)
   pos = get_squad_map().get(worst.name, {}).get("position", "CM")
   roast = darija.roast(worst, pos)
   embed = discord.Embed(title=f"🗑️ WORST PLAYER — {worst.name}", description=roast, color=0x8b0000)
   await rl.ctx_send(ctx, embed=embed)
   asyncio.create_task(_maybe_send_video(ctx.channel, worst, "fraud"))
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="who_sold")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_who_sold(ctx):
 if not await ensure_data(ctx): return
 async with ctx.typing():
  try:
   fraud = StatsEngine.get_fraud(current_club.players)
   roast = darija.fraud(fraud)
   embed = discord.Embed(title=f"🎭 FRAUD DETECTED — {fraud.name}", description=roast, color=0xff4500)
   await rl.ctx_send(ctx, embed=embed)
   asyncio.create_task(_maybe_send_video(ctx.channel, fraud, "fraud"))
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="carry")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_carry(ctx):
 if not await ensure_data(ctx): return
 async with ctx.typing():
  try:
   carry = StatsEngine.get_carry(current_club.players)
   praise = darija.carry(carry)
   embed = discord.Embed(title=f"💪 CARRY DETECTED — {carry.name}", description=praise, color=0x00ff00)
   await rl.ctx_send(ctx, embed=embed)
   asyncio.create_task(_maybe_send_video(ctx.channel, carry, "carry"))
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="fraud")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_fraud(ctx, *, player: str):
 if not await ensure_data(ctx): return
 target = find_player(player)
 if not target:
  await rl.ctx_send(ctx, f"ما لقيتش `{player}`.")
  return
 async with ctx.typing():
  try:
   is_fraud = target.throwing_score > 3.0
   if is_fraud:
    text = darija.fraud(target)
    color = 0xff0000
   else:
    text = f"✅ CLEAN\n\n{target.name} — Throwing: {target.throwing_score}\n\nهادا لاعب صحيح."
    color = 0x00ff00
   embed = discord.Embed(title=f"FRAUD CHECK — {target.name}", description=text, color=color)
   await rl.ctx_send(ctx, embed=embed)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="ballon")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_ballon(ctx):
 if not await ensure_data(ctx): return
 async with ctx.typing():
  try:
   ranked = sorted(current_club.players, key=lambda p: p.impact_score + p.clutch_score + p.goals * 2, reverse=True)
   embed = discord.Embed(title="🏆 BALLON D'OR", color=0xffd700)
   medals = ["🥇", "🥈", "🥉"]
   for i, p in enumerate(ranked[:5]):
    medal = medals[i] if i < 3 else f"{i+1}."
    embed.add_field(name=f"{medal} {p.name}", value=f"Impact: {p.impact_score} | Goals: {p.goals} | Rating: {round(p.rating_pg, 1)} | Win%: {round(p.win_rate, 1)}%", inline=False)
   await rl.ctx_send(ctx, embed=embed)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="ghost")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_ghost(ctx):
 if not await ensure_data(ctx): return
 async with ctx.typing():
  try:
   ghost = StatsEngine.get_ghost(current_club.players)
   roast = darija.ghost(ghost)
   embed = discord.Embed(title=f"👻 GHOST DETECTED — {ghost.name}", description=roast, color=0x9370db)
   await rl.ctx_send(ctx, embed=embed)
   asyncio.create_task(_maybe_send_video(ctx.channel, ghost, "ghost"))
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="pass")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_pass(ctx):
 if not await ensure_data(ctx): return
 async with ctx.typing():
  try:
   hog = StatsEngine.get_ball_hog(current_club.players)
   roast = darija.ball_loser(hog)
   embed = discord.Embed(title=f"⚽ PASS THE BALL! — {hog.name}", description=roast, color=0xffa500)
   await rl.ctx_send(ctx, embed=embed)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="leaderboard")
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_leaderboard(ctx, metric: str = "impact"):
 if not await ensure_data(ctx): return
 metric_map = {"impact": "impact_score", "goals": "goals", "assists": "assists", "rating": "rating_pg", "clutch": "clutch_score", "win_rate": "win_rate"}
 metric_value = metric_map.get(metric.lower(), "impact_score")
 async with ctx.typing():
  try:
   card = imgen.generate_leaderboard(current_club.players, metric_value)
   file = discord.File(card, filename="leaderboard.png")
   embed = discord.Embed(title=f"📊 Leaderboard — {metric.capitalize()}", color=0x1e90ff)
   await rl.ctx_send(ctx, embed=embed, file=file)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="compare")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_compare(ctx, player1: str, player2: str):
 if not await ensure_data(ctx): return
 p1 = find_player(player1)
 p2 = find_player(player2)
 if not p1 or not p2:
  await rl.ctx_send(ctx, "ما لقيتش players.")
  return
 async with ctx.typing():
  try:
   text = darija.compare(p1, p2)
   embed = discord.Embed(title="⚔️ 1v1 COMPARISON", description=text, color=0xff4500)
   embed.add_field(name=p1.name, value=f"Impact: {p1.impact_score}\nGoals: {p1.goals}\nAssists: {p1.assists}\nRating: {round(p1.rating_pg, 1)}\nWin%: {round(p1.win_rate, 1)}%", inline=True)
   embed.add_field(name=p2.name, value=f"Impact: {p2.impact_score}\nGoals: {p2.goals}\nAssists: {p2.assists}\nRating: {round(p2.rating_pg, 1)}\nWin%: {round(p2.win_rate, 1)}%", inline=True)
   await rl.ctx_send(ctx, embed=embed)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="lastmatch")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_lastmatch(ctx):
 if not await ensure_data(ctx): return
 if not current_club.matches:
  await rl.ctx_send(ctx, "ما لقيتش match history.")
  return
 try:
  last = current_club.matches[0]
  color = 0x00ff00 if last.result == "W" else 0xff0000 if last.result == "L" else 0xffff00
  embed = discord.Embed(title=f"⚽ Last Match: {last.score_for} - {last.score_against} vs {last.opponent}", description=f"Result: {last.result} • {last.date.strftime('%d/%m/%Y')}", color=color)
  await rl.ctx_send(ctx, embed=embed)
 except Exception as e:
  traceback.print_exc()
  await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="recent")
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_recent(ctx, limit: int = 5):
 if not await ensure_data(ctx):
  return

 try:
  limit = max(1, min(int(limit), 10))
 except Exception:
  limit = 5

 matches = getattr(current_club, "matches", []) or []

 if not matches:
  await rl.ctx_send(
   ctx,
   "No recent matches loaded. Run `!sync` first, then try again."
  )
  return

 recent = matches[:limit]

 embed = discord.Embed(
  title=f"Recent Matches — latest {len(recent)} available",
  description=(
   "This uses the recent match list currently available from PCT. "
   "Season player stats may include more than these matches."
  ),
  color=0x1e90ff,
 )

 for i, match in enumerate(recent, 1):
  opponent = getattr(match, "opponent", "Unknown")
  score_for = getattr(match, "score_for", "?")
  score_against = getattr(match, "score_against", "?")
  result = getattr(match, "result", "D")
  date = getattr(match, "date", "")

  emoji = "✅" if result == "W" else "❌" if result == "L" else "🤝"

  embed.add_field(
   name=f"{i}. {emoji} vs {opponent}",
   value=f"Score: {score_for}-{score_against}\nDate: {date}",
   inline=False,
  )

 await rl.ctx_send(ctx, embed=embed)

@bot.command(name="club")
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_club(ctx):
 if not await ensure_data(ctx): return
 async with ctx.typing():
  try:
   motm = StatsEngine.get_mvp(current_club.players)
   card = imgen.generate_match_report(current_club, motm)
   file = discord.File(card, filename="club_report.png")
   embed = discord.Embed(title=f"🏟️ {current_club.club_name}", description=f"Division {current_club.division} • Skill {current_club.skill_rating}", color=0x00ff00)
   await rl.ctx_send(ctx, embed=embed, file=file)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="court_case")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_court_case(ctx, *, player: str):
 if not await ensure_data(ctx): return
 target = find_player(player)
 if not target:
  await rl.ctx_send(ctx, f"ما لقيتش `{player}`.")
  return
 sq_info = getattr(target, "_squad_info", {}) or {}
 pos = sq_info.get("position", "CM")
 raw_img = sq_info.get("image")
 img_path = resolve_image_path(raw_img)
 display_name = target.name
 async with ctx.typing():
  try:
   text = darija.court_case(target)
   card = imgen.generate_player_photo_card(target, pos, "red", "COURT CASE", photo_path=img_path)
   file = discord.File(card, filename=f"{display_name}.png")
   color = 0xff0000 if target.throwing_score > 3.0 or target.rating_pg < 5.5 else 0x00ff00
   embed = discord.Embed(title=f"⚖️ COURT CASE: {display_name}", description=text, color=color)
   embed.add_field(name="Throwing", value=str(round(target.throwing_score, 1)), inline=True)
   embed.add_field(name="Error", value=str(round(target.error_score, 1)), inline=True)
   embed.add_field(name="Pass %", value=f"{round(target.pass_accuracy, 1)}%", inline=True)
   embed.add_field(name="Rating", value=str(round(target.rating_pg, 1)), inline=True)
   embed.add_field(name="Win %", value=f"{round(target.win_rate, 1)}%", inline=True)
   await rl.ctx_send(ctx, file=file, embed=embed)
   asyncio.create_task(_maybe_send_video(ctx.channel, target, "court"))
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="ball_loser")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_ball_loser(ctx):
 if not await ensure_data(ctx): return
 async with ctx.typing():
  try:
   loser = max(current_club.players, key=lambda p: p.possession_losses)
   roast = darija.ball_loser(loser)
   embed = discord.Embed(title=f"💀 BALL LOSER — {loser.name}", description=roast, color=0x8b0000)
   await rl.ctx_send(ctx, embed=embed)
   asyncio.create_task(_maybe_send_video(ctx.channel, None, "match"))
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="playmaker")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_playmaker(ctx):
 if not await ensure_data(ctx): return
 async with ctx.typing():
  try:
   pm = max(current_club.players, key=lambda p: p.assists * 2 + p.pass_accuracy)
   pos = get_squad_map().get(pm.name, {}).get("position", "CM")
   text = darija.playmaker(pm)
   img_path = get_squad_map().get(pm.name, {}).get("image")
   img_path = resolve_image_path(img_path)
   card = imgen.generate_player_photo_card(pm, pos, "green", "PLAYMAKER", photo_path=img_path)
   file = discord.File(card, filename=f"{pm.name}.png")
   embed = discord.Embed(title=f"🎨 PLAYMAKER — {pm.name}", description=text, color=0x00ff00)
   embed.add_field(name="Assists", value=str(pm.assists), inline=True)
   embed.add_field(name="Pass %", value=f"{round(pm.pass_accuracy, 1)}%", inline=True)
   embed.add_field(name="Rating", value=str(round(pm.rating_pg, 1)), inline=True)
   embed.add_field(name="Win %", value=f"{round(pm.win_rate, 1)}%", inline=True)
   await rl.ctx_send(ctx, file=file, embed=embed)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="sniper")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_sniper(ctx):
 if not await ensure_data(ctx): return
 async with ctx.typing():
  try:
   sniper = max(current_club.players, key=lambda p: p.goals * 2 + p.rating_pg)
   pos = get_squad_map().get(sniper.name, {}).get("position", "CM")
   img_path = get_squad_map().get(sniper.name, {}).get("image")
   img_path = resolve_image_path(img_path)
   card = imgen.generate_player_photo_card(sniper, pos, "blue", "SNIPER", photo_path=img_path)
   file = discord.File(card, filename=f"{sniper.name}.png")
   embed = discord.Embed(title=f"🎯 SNIPER — {sniper.name}", color=0xff4500)
   embed.add_field(name="Goals", value=str(sniper.goals), inline=True)
   embed.add_field(name="Rating", value=str(round(sniper.rating_pg, 1)), inline=True)
   embed.add_field(name="Impact", value=str(sniper.impact_score), inline=True)
   embed.add_field(name="Win %", value=f"{round(sniper.win_rate, 1)}%", inline=True)
   await rl.ctx_send(ctx, file=file, embed=embed)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="keeper")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_keeper(ctx):
 if not await ensure_data(ctx): return
 async with ctx.typing():
  try:
   gks = [p for p in current_club.players if get_squad_map().get(p.name, {}).get("position") == "GK"]
   if not gks:
    await rl.ctx_send(ctx, "ما لقيتش goalkeeper فالفريق.")
    return
   keeper = max(gks, key=lambda p: p.tackles + p.interceptions)
   text = darija.keeper(keeper)
   embed = discord.Embed(title=f"🧤 KEEPER — {keeper.name}", description=text, color=0x1e90ff)
   await rl.ctx_send(ctx, embed=embed)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="rankings")
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_rankings(ctx):
 if not await ensure_data(ctx): return
 async with ctx.typing():
  try:
   embed = discord.Embed(title="📊 ALL RANKINGS", color=0x1e90ff)
   mvp = StatsEngine.get_mvp(current_club.players)
   worst = StatsEngine.get_worst(current_club.players)
   fraud = StatsEngine.get_fraud(current_club.players)
   carry = StatsEngine.get_carry(current_club.players)
   ghost = StatsEngine.get_ghost(current_club.players)
   embed.add_field(name="🏆 MVP", value=f"{mvp.name} (Impact: {mvp.impact_score} | Win%: {round(mvp.win_rate, 1)}%)", inline=False)
   embed.add_field(name="🗑️ Worst", value=f"{worst.name} (Impact: {worst.impact_score} | Win%: {round(worst.win_rate, 1)}%)", inline=False)
   embed.add_field(name="🎭 Fraud", value=f"{fraud.name} (Throwing: {fraud.throwing_score} | Win%: {round(fraud.win_rate, 1)}%)", inline=False)
   embed.add_field(name="💪 Carry", value=f"{carry.name} (Impact: {carry.impact_score} | Win%: {round(carry.win_rate, 1)}%)", inline=False)
   embed.add_field(name="👻 Ghost", value=f"{ghost.name} ({ghost.minutes_played}min | Win%: {round(ghost.win_rate, 1)}%)", inline=False)
   await rl.ctx_send(ctx, embed=embed)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="awards")
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_awards(ctx):
 if not await ensure_data(ctx): return
 async with ctx.typing():
  try:
   embed = discord.Embed(title="🏅 SEASON AWARDS", color=0xffd700)
   mvp = StatsEngine.get_mvp(current_club.players)
   top_scorer = max(current_club.players, key=lambda p: p.goals)
   top_assist = max(current_club.players, key=lambda p: p.assists)
   fraud = StatsEngine.get_fraud(current_club.players)
   embed.add_field(name="🥇 Ballon d'Or", value=f"{mvp.name} (Win%: {round(mvp.win_rate, 1)}%)", inline=False)
   embed.add_field(name="⚽ Golden Boot", value=f"{top_scorer.name} ({top_scorer.goals} goals)", inline=False)
   embed.add_field(name="🅰️ Playmaker Award", value=f"{top_assist.name} ({top_assist.assists} assists)", inline=False)
   embed.add_field(name="🤡 Fraud of the Season", value=f"{fraud.name} ({fraud.throwing_score} throwing)", inline=False)
   await rl.ctx_send(ctx, embed=embed)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="form")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_form(ctx, *, player: str):
 if not await ensure_data(ctx): return
 num = 5
 parts = player.rsplit(" ", 1)
 if len(parts) == 2 and parts[1].isdigit():
  num = min(int(parts[1]), 20)
  player = parts[0]
 target = find_player(player)
 if not target:
  await rl.ctx_send(ctx, f"ما لقيتش `{player}`.")
  return
 if not current_club.matches:
  await rl.ctx_send(ctx, "ما لقيتش match history.")
  return
 raw_psn = getattr(target, "_raw_psn", target.name)
 matches_data = []
 for m in current_club.matches[:num]:
  ps = m.player_stats.get(raw_psn, {})
  if not ps:
   for pid, pstat in m.player_stats.items():
    if pid.lower() == target.name.lower():
     ps = pstat
     break
  if ps:
   pa = ps.get("passes_attempted", 0)
   pc = ps.get("passes_completed", 0)
   pass_acc = round(pc / max(pa, 1) * 100, 1) if pa > 0 else 0
   matches_data.append({
    "date": m.date.strftime("%d/%m"),
    "opponent": m.opponent,
    "rating": round(ps.get("rating", 0), 1),
    "goals": ps.get("goals", 0),
    "assists": ps.get("assists", 0),
    "pass_acc": pass_acc,
   })
 if not matches_data:
  await rl.ctx_send(ctx, f"ما لقيتش match history لـ {target.name}.")
  return
 async with ctx.typing():
  try:
   card = imgen.generate_form_card(target, matches_data, len(matches_data))
   file = discord.File(card, filename="form.png")
   embed = discord.Embed(title=f"📈 Form — {target.name} (Last {len(matches_data)})", color=0x00bfff)
   await rl.ctx_send(ctx, embed=embed, file=file)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="records")
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_records(ctx):
 if not await ensure_data(ctx): return
 if not current_club.matches:
  await rl.ctx_send(ctx, "ما لقيتش match history.")
  return
 matches = current_club.matches
 biggest_win = max(matches, key=lambda m: m.score_for - m.score_against)
 biggest_loss = min(matches, key=lambda m: m.score_for - m.score_against)
 most_goals_match = max(matches, key=lambda m: m.score_for)
 best_rating = 0.0
 best_rating_player = "None"
 for m in matches:
  for psn, ps in m.player_stats.items():
   r = ps.get("rating", 0)
   if r > best_rating:
    best_rating = r
    best_rating_player = psn
 streak = 0
 best_streak = 0
 for m in reversed(matches):
  if m.result == "W":
   streak += 1
   best_streak = max(best_streak, streak)
  else:
   streak = 0
 total_goals = sum(m.score_for for m in matches)
 total_matches = len(matches)
 win_rate = round(sum(1 for m in matches if m.result == "W") / total_matches * 100, 1) if total_matches > 0 else 0
 records = [
  ("Biggest Win", f"{biggest_win.score_for}-{biggest_win.score_against} vs {biggest_win.opponent}"),
  ("Biggest Loss", f"{biggest_loss.score_for}-{biggest_loss.score_against} vs {biggest_loss.opponent}"),
  ("Most Goals (Match)", f"{most_goals_match.score_for} vs {most_goals_match.opponent}"),
  ("Best Match Rating", f"{round(best_rating, 1)} by {best_rating_player}"),
  ("Longest Win Streak", f"{best_streak} matches"),
  ("Total Goals Scored", str(total_goals)),
  ("Total Matches", str(total_matches)),
  ("Win Rate", f"{win_rate}%"),
 ]
 async with ctx.typing():
  try:
   card = imgen.generate_records_card(current_club, records)
   file = discord.File(card, filename="records.png")
   embed = discord.Embed(title="🏆 Club Records", color=0xffd700)
   await rl.ctx_send(ctx, embed=embed, file=file)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="legend")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_legend(ctx):
 if not await ensure_data(ctx): return
 async with ctx.typing():
  try:
   mvp = StatsEngine.get_mvp(current_club.players)
   sq_info = getattr(mvp, "_squad_info", {}) or {}
   pos = sq_info.get("position", "CM")
   raw_img = sq_info.get("image")
   img_path = resolve_image_path(raw_img)
   display_name = mvp.name
   card = imgen.generate_player_photo_card(mvp, pos, "gold", "CLUB LEGEND", photo_path=img_path)
   file = discord.File(card, filename="legend.png")
   embed = discord.Embed(title=f"👑 CLUB LEGEND — {display_name}", color=0xffd700)
   embed.add_field(name="Goals", value=str(mvp.goals), inline=True)
   embed.add_field(name="Assists", value=str(mvp.assists), inline=True)
   embed.add_field(name="Rating", value=str(round(mvp.rating_pg, 1)), inline=True)
   embed.add_field(name="Impact", value=str(mvp.impact_score), inline=True)
   embed.add_field(name="Win %", value=f"{round(mvp.win_rate, 1)}%", inline=True)
   await rl.ctx_send(ctx, file=file, embed=embed)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="hall_of_shame")
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_hall_of_shame(ctx):
 if not await ensure_data(ctx): return
 async with ctx.typing():
  try:
   text = darija.hall_of_shame(current_club.players)
   embed = discord.Embed(title="🏛️ Hall of Shame", description=text, color=0x8b0000)
   await rl.ctx_send(ctx, embed=embed)
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="match_report")
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_match_report(ctx):
 if not await ensure_data(ctx): return
 if not current_club.matches:
  await rl.ctx_send(ctx, "ما لقيتش match history.")
  return
 async with ctx.typing():
  try:
   latest = current_club.matches[0]
   color = 0x00ff00 if latest.result == "W" else 0xff0000 if latest.result == "L" else 0xffff00
   embed = discord.Embed(title=f"📋 Match Report: {latest.opponent} {latest.score_for}-{latest.score_against}", description=f"Date: {latest.date.strftime('%d/%m/%Y')}", color=color)
   await rl.ctx_send(ctx, embed=embed)
   asyncio.create_task(_maybe_send_video(ctx.channel, None, "match", latest.match_id))
  except Exception as e:
   traceback.print_exc()
   await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

# ─── PHASE 4 PREFIX COMMANDS (conditional) ───
if PHASE4_AVAILABLE:
 @bot.command(name="hall_of_fame")
 @commands.cooldown(1, 10, commands.BucketType.user)
 async def cmd_hall_of_fame(ctx):
  if not await ensure_data(ctx): return
  if not current_club.matches:
   await rl.ctx_send(ctx, "ما لقيتش match history باش نبني Hall of Fame.")
   return
  async with ctx.typing():
   try:
    records = HallOfFame.scan_matches(current_club.matches, current_club.players)
    if not records:
     await rl.ctx_send(ctx, "🏆 **Hall of Fame**\n\nما كاين حتى شي record لحد الآن.")
     return
    card = generate_hall_of_fame_card(Config.ASSETS_DIR, records, current_club.club_name)
    file = discord.File(card, filename="hall_of_fame.png")
    text = HallOfFame.get_records_text(records)
    embed = discord.Embed(title="🏆 Hall of Fame", description=text, color=0xffd700)
    await rl.ctx_send(ctx, embed=embed, file=file)
   except Exception as e:
    traceback.print_exc()
    await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

 @bot.command(name="rivalry")
 @commands.cooldown(1, 5, commands.BucketType.user)
 async def cmd_rivalry(ctx, player1: str, player2: str):
  if not await ensure_data(ctx): return
  p1 = find_player(player1)
  p2 = find_player(player2)
  if not p1 or not p2:
   await rl.ctx_send(ctx, "ما لقيتش players.")
   return
  async with ctx.typing():
   try:
    stats = RivalrySystem.compare(p1, p2, current_club.matches)
    text = RivalrySystem.format_text(stats)
    sq1 = getattr(p1, "_squad_info", {}) or {}
    sq2 = getattr(p2, "_squad_info", {}) or {}
    p1_photo = resolve_image_path(sq1.get("image"))
    p2_photo = resolve_image_path(sq2.get("image"))
    card = generate_rivalry_card(Config.ASSETS_DIR, stats, p1_photo, p2_photo)
    file = discord.File(card, filename="rivalry.png")
    embed = discord.Embed(title=f"⚔️ Rivalry: {p1.name} vs {p2.name}", description=text, color=0xff4500)
    await rl.ctx_send(ctx, embed=embed, file=file)
    memory.record_rivalry_result(p1.name, p2.name, stats["overall_winner"])
   except Exception as e:
    traceback.print_exc()
    await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

 @bot.command(name="fraud_score")
 @commands.cooldown(1, 5, commands.BucketType.user)
 async def cmd_fraud_score(ctx, *, player: str):
  """
  FIX: Fraud score must use latest match stats (match.players only).
  """
  if not await ensure_data(ctx): return
  target = find_player(player)
  if not target:
   await rl.ctx_send(ctx, f"ما لقيتش `{player}`.")
   return
  if not current_club.matches:
   await rl.ctx_send(ctx, "ما لقيتش match history. دير !sync.")
   return
  latest = current_club.matches[0]
  ms = _find_player_match_stats(latest, target)
  if not ms:
   await rl.ctx_send(ctx, f"⚠️ {target.name} ما لعبش آخر ماتش. (match.players only)")
   return
  async with ctx.typing():
   try:
    fraud = FraudScoreSystem.compute_match_fraud(ms)
    sq_info = getattr(target, "_squad_info", {}) or {}
    pos = sq_info.get("position", "CM")
    img_path = resolve_image_path(sq_info.get("image"))
    color_map = {"Safe": 0x00ff00, "Suspicious": 0xffa500, "Fraud": 0xff4500, "Criminal": 0xff0000}
    color = color_map.get(fraud["classification"], 0xff0000)
    card = imgen.generate_player_photo_card(target, pos, "red" if fraud["score"] > 60 else "gold", f"FRAUD(MATCH): {fraud['classification']}", photo_path=img_path)
    file = discord.File(card, filename=f"{target.name}_fraud_match.png")
    embed = discord.Embed(title=f"🎭 Fraud Score (Latest Match) — {target.name}", color=color)
    embed.add_field(name="Score", value=f"{fraud['score']}/100", inline=True)
    embed.add_field(name="Classification", value=fraud["classification"], inline=True)
    breakdown_text = "\n".join([f"• {desc}: +{pts}" for desc, pts in fraud["breakdown"]])
    embed.add_field(name="Breakdown", value=breakdown_text or "Clean sheet", inline=False)
    embed.set_footer(text=f"vs {latest.opponent} • {latest.score_for}-{latest.score_against}")
    await rl.ctx_send(ctx, file=file, embed=embed)
   except Exception as e:
    traceback.print_exc()
    await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="carry_score")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_carry_score(ctx, *, player: str):
    """
    Carry score must use latest match stats ONLY (match.players only).
    """
    if not await ensure_data(ctx): return
    if not current_club or not getattr(current_club, "matches", None):
        await rl.ctx_send(ctx, "ما لقيتش match history. دير !sync.")
        return

    target = find_player(player)
    if not target:
        await rl.ctx_send(ctx, f"ما لقيتش `{player}`.")
        return

    latest = current_club.matches[0]
    ms = _find_player_match_stats(latest, target)
    if not ms:
        await rl.ctx_send(ctx, f"⚠️ {target.name} ما لعبش آخر ماتش. (match.players only)")
        return

    async with ctx.typing():
        try:
            carry = CarryScoreSystem.compute_match_carry(ms)

            sq_info = getattr(target, "_squad_info", {}) or {}
            pos = sq_info.get("position", "CM")
            img_path = resolve_image_path(sq_info.get("image"))

            card = imgen.generate_player_photo_card(
                target,
                pos,
                "blue",
                f"CARRY(MATCH): {carry['classification']}",
                photo_path=img_path
            )
            file = discord.File(card, filename=f"{target.name}_carry_match.png")

            embed = discord.Embed(title=f"💪 Carry Score (Latest Match) — {target.name}", color=0x00bfff)
            embed.add_field(name="Score", value=str(carry["score"]), inline=True)
            embed.add_field(name="Classification", value=carry["classification"], inline=True)

            passes_att = ms.get("passes_attempted", 0)
            passes_comp = ms.get("passes_completed", 0)
            pass_pct = round(passes_comp / max(passes_att, 1) * 100, 1) if passes_att else 0.0

            rating = ms.get("rating", 0)
            if rating and rating > 10:
                rating = round(rating / 10.0, 1)

            evidence = (
                f"Goals: {ms.get('goals', 0)} | Assists: {ms.get('assists', 0)} | "
                f"Tackles: {ms.get('tackles', 0)} | Interceptions: {ms.get('interceptions', 0)}\n"
                f"Pass%: {pass_pct} | Poss Lost: {max(0, passes_att - passes_comp)} | Rating: {rating}"
            )
            embed.add_field(name="Evidence (match.players)", value=evidence, inline=False)
            embed.set_footer(text=f"vs {latest.opponent} • {latest.score_for}-{latest.score_against}")

            await rl.ctx_send(ctx, file=file, embed=embed)

        except Exception as e:
            traceback.print_exc()
            await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

 @bot.command(name="ghost_score")
 @commands.cooldown(1, 5, commands.BucketType.user)
 async def cmd_ghost_score(ctx, *, player: str):
  """
  FIX: Ghost score must use latest match stats (match.players only).
  """
  if not await ensure_data(ctx): return
  target = find_player(player)
  if not target:
   await rl.ctx_send(ctx, f"ما لقيتش `{player}`.")
   return
  if not current_club.matches:
   await rl.ctx_send(ctx, "ما لقيتش match history. دير !sync.")
   return
  latest = current_club.matches[0]
  ms = _find_player_match_stats(latest, target)
  if not ms:
   await rl.ctx_send(ctx, f"⚠️ {target.name} ما لعبش آخر ماتش. (match.players only)")
   return
  async with ctx.typing():
   try:
    ghost = GhostScoreSystem._compute_match_ghost(ms)
    sq_info = getattr(target, "_squad_info", {}) or {}
    pos = sq_info.get("position", "CM")
    img_path = resolve_image_path(sq_info.get("image"))
    color = 0x9370db if ghost["is_ghost"] else 0x00ff00
    card = imgen.generate_player_photo_card(target, pos, "purple", f"GHOST(MATCH): {ghost['severity']}", photo_path=img_path)
    file = discord.File(card, filename=f"{target.name}_ghost_match.png")
    embed = discord.Embed(title=f"👻 Ghost Score (Latest Match) — {target.name}", color=color)
    embed.add_field(name="Ghost Points", value=str(ghost["ghost_points"]), inline=True)
    embed.add_field(name="Severity", value=ghost["severity"], inline=True)
    embed.add_field(name="Is Ghost?", value="Yes" if ghost["is_ghost"] else "No", inline=True)
    reasons = "\n".join([f"• {r}" for r in ghost["reasons"]])
    embed.add_field(name="Reasons", value=reasons or "No ghost signs detected", inline=False)
    embed.set_footer(text=f"vs {latest.opponent} • {latest.score_for}-{latest.score_against}")
    await rl.ctx_send(ctx, file=file, embed=embed)
   except Exception as e:
    traceback.print_exc()
    await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

 @bot.command(name="excuses")
 @commands.cooldown(1, 5, commands.BucketType.user)
 async def cmd_excuses(ctx, *, player: str):
  if not await ensure_data(ctx): return
  target = find_player(player)
  if not target:
   await rl.ctx_send(ctx, f"ما لقيتش `{player}`.")
   return
  async with ctx.typing():
   try:
    text = darija.excuses(target)
    embed = discord.Embed(title=f"📝 Excuses — {target.name}", description=text, color=0x1e90ff)
    await rl.ctx_send(ctx, embed=embed)
   except Exception as e:
    traceback.print_exc()
    await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

 @bot.command(name="match_poster")
 @commands.cooldown(1, 10, commands.BucketType.user)
 async def cmd_match_poster(ctx):
  if not await ensure_data(ctx): return
  if not current_club.matches:
   await rl.ctx_send(ctx, "ما لقيتش match history.")
   return
  async with ctx.typing():
   try:
    last = current_club.matches[0]
    poster_data = MatchPosterEngine.build_poster_data(last, current_club.players)
    if not poster_data:
     await rl.ctx_send(ctx, "ما قدرتش نبني poster — ما كاينش player stats.")
     return
    photo_paths = {}
    for mp in poster_data.get("all_players", []):
     pobj = mp.get("player_obj")
     if pobj:
      sq = getattr(pobj, "_squad_info", {}) or {}
      photo_paths[mp["name"]] = resolve_image_path(sq.get("image"))
    card = generate_match_poster(Config.ASSETS_DIR, poster_data, photo_paths)
    file = discord.File(card, filename="match_poster.png")
    embed = discord.Embed(title=f"🎨 Match Poster: {poster_data['opponent']} {poster_data['score']}", color=0xffd700)
    await rl.ctx_send(ctx, embed=embed, file=file)
   except Exception as e:
    traceback.print_exc()
    await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

# ─────────────────────────────────────────────────────────────
# SLASH COMMANDS — existing + Phase 4 (conditional)
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="ping", description="Test if bot is responding")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_ping(interaction: discord.Interaction):
 await rl.interaction_send(interaction, "Pong! Try /sync next.")

@bot.tree.command(name="debug", description="Show bot state")
@app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
async def slash_debug(interaction: discord.Interaction):
 scraper_ready = "Yes" if scraper else "No"
 data_loaded = "Yes" if current_club and current_club.players else "No"
 player_count = len(current_club.players) if current_club and current_club.players else 0
 cache_age = int(time.time() - _data_cache_time) if _data_cache_time else "N/A"
 metrics = scraper.metrics()
 db_stats = await scraper.db_stats()
 sq_map = get_squad_map()
 sq_names = list(sq_map.keys())[:5] if sq_map else ["EMPTY - squad.json missing?"]
 lines = [
  f"PCT_URL: {Config.PCT_CLUB_URL}",
  f"PORT: {Config.PORT}",
  f"Club ID: {Config.CLUB_ID}",
  f"Scraper ready: {scraper_ready}",
  f"Data loaded: {data_loaded}",
  f"Players: {player_count}",
  f"Cache age: {cache_age}s",
  f"Squad.json loaded: {len(sq_map)} players",
  f"Squad sample: {', '.join(sq_names)}",
  f"Scraper cooldown: {metrics['cooldown']} ({metrics['cooldown_remaining']}s)",
  f"Scraper rate limited: {metrics['rate_limited']}",
  f"Scraper requests/hour: {metrics['requests_hour']}/{scraper._max_per_hour}",
  f"Scraper last scrape: {metrics['last_scrape_age']}s ago",
  f"Scraper failures: {metrics['failures']}",
  f"DB scrapes (24h): {db_stats.get('total_attempts', 0)} attempts, {db_stats.get('successes', 0)} success",
  f"Phase 4 available: {PHASE4_AVAILABLE}",
 ]
 embed = discord.Embed(title="Debug Info", description="\n".join(lines), color=0x808080)
 await rl.interaction_send(interaction, embed=embed)

@bot.tree.command(name="sync", description="Manual sync from ProClubsTracker")
@app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
async def slash_sync(interaction: discord.Interaction):
 await interaction.response.defer()
 try:
  await rl.interaction_send(interaction, "⏳ جاري التحديث من ProClubsTracker...")
  club = await _fetch_club_data(force=True, source="manual_sync")
  if not club or not club.players:
   await rl.interaction_send(interaction, "ما قدرتش نجيب البيانات. Scraper metrics: " + str(scraper.metrics()))
   return
  embed = discord.Embed(title="Sync Complete", description=f"{len(club.players)} players loaded", color=0x00ff00)
  await rl.interaction_send(interaction, embed=embed)
 except Exception as e:
  tb = traceback.format_exc()
  logger.error("SYNC ERROR: %s", tb)
  await rl.interaction_send(interaction, f"Sync failed: {str(e)[:800]}")

@bot.tree.command(name="stats", description="Player stats + premium photo card")
@app_commands.describe(player="Player name, PSN, or nickname")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_stats(interaction: discord.Interaction, player: str):
 await interaction.response.defer()
 if not await ensure_data_interaction(interaction): return
 target = find_player(player)
 if not target:
  await rl.interaction_send(interaction, f"ما لقيتش `{player}`.")
  return
 sq_info = getattr(target, "_squad_info", {}) or {}
 pos = sq_info.get("position", "CM")
 raw_img = sq_info.get("image")
 img_path = resolve_image_path(raw_img)
 display_name = target.name
 try:
  card = imgen.generate_player_photo_card(target, pos, "gold", "PLAYER PROFILE", photo_path=img_path)
  file = discord.File(card, filename=f"{display_name}.png")
  embed = discord.Embed(title=f"📊 {display_name} — {pos}", color=0x1e90ff)
  embed.add_field(name="Games", value=str(target.games), inline=True)
  embed.add_field(name="Goals", value=str(target.goals), inline=True)
  embed.add_field(name="Assists", value=str(target.assists), inline=True)
  embed.add_field(name="Rating", value=f"{round(target.rating_pg, 1)}", inline=True)
  embed.add_field(name="Pass %", value=f"{round(target.pass_accuracy, 1)}%", inline=True)
  embed.add_field(name="Possession Lost", value=str(target.possession_losses), inline=True)
  embed.add_field(name="Impact", value=str(target.impact_score), inline=True)
  embed.add_field(name="MOTM", value=str(target.motm), inline=True)
  embed.add_field(name="Win %", value=f"{round(target.win_rate, 1)}%", inline=True)
  embed.add_field(name="Tackles", value=str(target.tackles), inline=True)
  await rl.interaction_send(interaction, file=file, embed=embed)
  asyncio.create_task(_maybe_send_video(interaction.channel, target, "mvp"))
 except Exception as e:
  traceback.print_exc()
  await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="player", description="Complete player profile")
@app_commands.describe(player="Player name")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_player(interaction: discord.Interaction, player: str):
 await interaction.response.defer()
 if not await ensure_data_interaction(interaction): return
 target = find_player(player)
 if not target:
  await rl.interaction_send(interaction, f"ما لقيتش `{player}`.")
  return
 sq_info = getattr(target, "_squad_info", {}) or {}
 pos = sq_info.get("position", "CM")
 raw_img = sq_info.get("image")
 img_path = resolve_image_path(raw_img)
 display_name = target.name
 try:
  card = imgen.generate_player_photo_card(target, pos, "purple", "PLAYER PROFILE", photo_path=img_path)
  file = discord.File(card, filename=f"{display_name}.png")
  embed = discord.Embed(title=f"👤 {display_name} — {pos}", color=0x1e90ff)
  embed.add_field(name="Games", value=str(target.games), inline=True)
  embed.add_field(name="Goals", value=str(target.goals), inline=True)
  embed.add_field(name="Assists", value=str(target.assists), inline=True)
  embed.add_field(name="Rating", value=f"{round(target.rating_pg, 1)}", inline=True)
  embed.add_field(name="Pass %", value=f"{round(target.pass_accuracy, 1)}%", inline=True)
  embed.add_field(name="Possession Lost", value=str(target.possession_losses), inline=True)
  embed.add_field(name="Impact", value=str(target.impact_score), inline=True)
  embed.add_field(name="MOTM", value=str(target.motm), inline=True)
  await rl.interaction_send(interaction, file=file, embed=embed)
 except Exception as e:
  traceback.print_exc()
  await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="bio", description="Show player bio from squad.json")
@app_commands.describe(player="Player name")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_bio(interaction: discord.Interaction, player: str):
 await interaction.response.defer()
 if not await ensure_data_interaction(interaction): return
 target = find_player(player)
 if not target:
  await rl.interaction_send(interaction, f"ما لقيتش `{player}`.")
  return
 sq_info = getattr(target, "_squad_info", {}) or {}
 bio_text = sq_info.get("bio", "") or "ما عنديش bio لـ هاد اللاعب."
 pos = sq_info.get("position", "CM")
 raw_img = sq_info.get("image")
 img_path = resolve_image_path(raw_img)
 display_name = target.name
 try:
  card = imgen.generate_player_photo_card(target, pos, "gold", "BIO", photo_path=img_path)
  file = discord.File(card, filename=f"{display_name}.png")
  embed = discord.Embed(title=f"📝 BIO — {display_name}", description=bio_text, color=0x00ff7f)
  embed.add_field(name="Position", value=pos, inline=True)
  embed.add_field(name="Nickname", value=sq_info.get("nickname", display_name), inline=True)
  await rl.interaction_send(interaction, file=file, embed=embed)
 except Exception as e:
  traceback.print_exc()
  await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="help", description="Show all commands")
@app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
async def slash_help(interaction: discord.Interaction):
 await interaction.response.defer()
 try:
  embed = discord.Embed(
   title="Rachad L3ERGONI Bot",
   description="الخطوة الأولى: دير /sync أو !sync\n\nبعدها تقدر تستعمل كل شي:",
   color=0x1e90ff
  )
  text = (
   "**Basic:** /ping /debug /resync /sync\n\n"
   "**Player Cards:** /stats [player] /player [player] /bio [player]\n\n"
   "**Rankings:** /mvp /worst /carry_detector /ballon_dor /ghost_detector /ball_loser /playmaker /sniper /keeper\n\n"
   "**Roast Engine:** /fraud_check [player] /who_sold /pass_the_ball /court_case [player] /hall_of_shame\n\n"
   "**Compare:** /compare p1 p2 /lastmatch /clubinfo /leaderboard\n\n"
   "**Form & Records:** /form [player] [N] /records /legend /match_report\n\n"
   "**History:** /rankings /awards\n\n"
  )
  if PHASE4_AVAILABLE:
   text += (
    "**Ecosystem (Phase 4):** /hall_of_fame /rivalry p1 p2 /fraud_score [player] /carry_score [player] /ghost_score [player] /excuses [player] /match_poster\n\n"
   )
  text += "**Settings:** /sync"
  embed.add_field(name="All Commands", value=text, inline=False)
  await rl.interaction_send(interaction, embed=embed)
 except Exception as e:
  traceback.print_exc()
  await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

# ─── PHASE 4 SLASH COMMANDS (conditional) ───
if PHASE4_AVAILABLE:
 @bot.tree.command(name="fraud_score", description="Fraud score (latest match only)")
 @app_commands.describe(player="Player name")
 @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
 async def slash_fraud_score(interaction: discord.Interaction, player: str):
  await interaction.response.defer()
  if not await ensure_data_interaction(interaction): return
  target = find_player(player)
  if not target:
   await rl.interaction_send(interaction, f"ما لقيتش `{player}`.")
   return
  if not current_club.matches:
   await rl.interaction_send(interaction, "ما لقيتش match history. دير /sync.")
   return
  latest = current_club.matches[0]
  ms = _find_player_match_stats(latest, target)
  if not ms:
   await rl.interaction_send(interaction, f"⚠️ {target.name} ما لعبش آخر ماتش. (match.players only)")
   return
  try:
   fraud = FraudScoreSystem.compute_match_fraud(ms)
   sq_info = getattr(target, "_squad_info", {}) or {}
   pos = sq_info.get("position", "CM")
   img_path = resolve_image_path(sq_info.get("image"))
   color_map = {"Safe": 0x00ff00, "Suspicious": 0xffa500, "Fraud": 0xff4500, "Criminal": 0xff0000}
   color = color_map.get(fraud["classification"], 0xff0000)
   card = imgen.generate_player_photo_card(target, pos, "red" if fraud["score"] > 60 else "gold", f"FRAUD(MATCH): {fraud['classification']}", photo_path=img_path)
   file = discord.File(card, filename=f"{target.name}_fraud_match.png")
   embed = discord.Embed(title=f"🎭 Fraud Score (Latest Match) — {target.name}", color=color)
   embed.add_field(name="Score", value=f"{fraud['score']}/100", inline=True)
   embed.add_field(name="Classification", value=fraud["classification"], inline=True)
   breakdown_text = "\n".join([f"• {desc}: +{pts}" for desc, pts in fraud["breakdown"]])
   embed.add_field(name="Breakdown", value=breakdown_text or "Clean sheet", inline=False)
   embed.set_footer(text=f"vs {latest.opponent} • {latest.score_for}-{latest.score_against}")
   await rl.interaction_send(interaction, file=file, embed=embed)
  except Exception as e:
   traceback.print_exc()
   await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="carry_score", description="Carry score (latest match only)")
@app_commands.describe(player="Player name")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_carry_score(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    if not current_club or not getattr(current_club, "matches", None):
        await rl.interaction_send(interaction, "ما لقيتش match history. دير /sync.")
        return

    target = find_player(player)
    if not target:
        await rl.interaction_send(interaction, f"ما لقيتش `{player}`.")
        return

    latest = current_club.matches[0]
    ms = _find_player_match_stats(latest, target)
    if not ms:
        await rl.interaction_send(interaction, f"⚠️ {target.name} ما لعبش آخر ماتش. (match.players only)")
        return

    try:
        carry = CarryScoreSystem.compute_match_carry(ms)

        sq_info = getattr(target, "_squad_info", {}) or {}
        pos = sq_info.get("position", "CM")
        img_path = resolve_image_path(sq_info.get("image"))

        card = imgen.generate_player_photo_card(
            target,
            pos,
            "blue",
            f"CARRY(MATCH): {carry['classification']}",
            photo_path=img_path
        )
        file = discord.File(card, filename=f"{target.name}_carry_match.png")

        embed = discord.Embed(title=f"💪 Carry Score (Latest Match) — {target.name}", color=0x00bfff)
        embed.add_field(name="Score", value=str(carry["score"]), inline=True)
        embed.add_field(name="Classification", value=carry["classification"], inline=True)

        passes_att = ms.get("passes_attempted", 0)
        passes_comp = ms.get("passes_completed", 0)
        pass_pct = round(passes_comp / max(passes_att, 1) * 100, 1) if passes_att else 0.0

        rating = ms.get("rating", 0)
        if rating and rating > 10:
            rating = round(rating / 10.0, 1)

        evidence = (
            f"Goals: {ms.get('goals', 0)} | Assists: {ms.get('assists', 0)} | "
            f"Tackles: {ms.get('tackles', 0)} | Interceptions: {ms.get('interceptions', 0)}\n"
            f"Pass%: {pass_pct} | Poss Lost: {max(0, passes_att - passes_comp)} | Rating: {rating}"
        )
        embed.add_field(name="Evidence (match.players)", value=evidence, inline=False)
        embed.set_footer(text=f"vs {latest.opponent} • {latest.score_for}-{latest.score_against}")

        await rl.interaction_send(interaction, file=file, embed=embed)

    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

 @bot.tree.command(name="ghost_score", description="Ghost score (latest match only)")
 @app_commands.describe(player="Player name")
 @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
 async def slash_ghost_score(interaction: discord.Interaction, player: str):
  await interaction.response.defer()
  if not await ensure_data_interaction(interaction): return
  target = find_player(player)
  if not target:
   await rl.interaction_send(interaction, f"ما لقيتش `{player}`.")
   return
  if not current_club.matches:
   await rl.interaction_send(interaction, "ما لقيتش match history. دير /sync.")
   return
  latest = current_club.matches[0]
  ms = _find_player_match_stats(latest, target)
  if not ms:
   await rl.interaction_send(interaction, f"⚠️ {target.name} ما لعبش آخر ماتش. (match.players only)")
   return
  try:
   ghost = GhostScoreSystem._compute_match_ghost(ms)
   sq_info = getattr(target, "_squad_info", {}) or {}
   pos = sq_info.get("position", "CM")
   img_path = resolve_image_path(sq_info.get("image"))
   color = 0x9370db if ghost["is_ghost"] else 0x00ff00
   card = imgen.generate_player_photo_card(target, pos, "purple", f"GHOST(MATCH): {ghost['severity']}", photo_path=img_path)
   file = discord.File(card, filename=f"{target.name}_ghost_match.png")
   embed = discord.Embed(title=f"👻 Ghost Score (Latest Match) — {target.name}", color=color)
   embed.add_field(name="Ghost Points", value=str(ghost["ghost_points"]), inline=True)
   embed.add_field(name="Severity", value=ghost["severity"], inline=True)
   embed.add_field(name="Is Ghost?", value="Yes" if ghost["is_ghost"] else "No", inline=True)
   reasons = "\n".join([f"• {r}" for r in ghost["reasons"]])
   embed.add_field(name="Reasons", value=reasons or "No ghost signs detected", inline=False)
   embed.set_footer(text=f"vs {latest.opponent} • {latest.score_for}-{latest.score_against}")
   await rl.interaction_send(interaction, file=file, embed=embed)
  except Exception as e:
   traceback.print_exc()
   await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

# ─────────────────────────────────────────────────────────────
# MAIN ENTRY
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
 backoff = load_backoff_state() if 'load_backoff_state' in globals() else {"consecutive_429s": 0, "last_429_time": 0}
 consecutive_429s = backoff.get("consecutive_429s", 0)
 last_429_time = backoff.get("last_429_time", 0)

 time_since_last_429 = time.time() - last_429_time
 if consecutive_429s > 0 and time_since_last_429 < 7200:
  initial_delay = min(300 * (2 ** min(consecutive_429s, 5)), 3600)
  logger.info("[STARTUP] Recent 429 history (%d). Waiting %ds...", consecutive_429s, initial_delay)
  for i in range(initial_delay):
   time.sleep(1)
   if i % 60 == 0 and i > 0:
    logger.info("[STARTUP] Still waiting... %d/%d", i, initial_delay)
  consecutive_429s = 0
  save_backoff_state(0, 0) if 'save_backoff_state' in globals() else None

 startup_delay = int(os.getenv("DISCORD_STARTUP_DELAY", "15"))
 if startup_delay > 0:
  logger.info("[STARTUP] Waiting %ds before Discord login...", startup_delay)
  time.sleep(startup_delay)

 try:
  logger.info("[STARTUP] Connecting to Discord...")
  bot.run(Config.DISCORD_TOKEN, reconnect=True)
  logger.info("[SHUTDOWN] Bot disconnected normally.")
 except discord.HTTPException as e:
  is_cloudflare = "cloudflare" in str(e).lower() or "1015" in str(e)
  is_429 = e.status == 429
  if is_429 or is_cloudflare:
   new_consecutive = consecutive_429s + 1
   delay = min(300 * (2 ** min(new_consecutive, 6)), 3600)
   if is_cloudflare:
    logger.error("[FATAL] Cloudflare 1015. Sleeping %ds then exit for fresh restart...", delay)
   else:
    logger.error("[FATAL] Discord 429. Sleeping %ds then exit for fresh restart...", delay)
   save_backoff_state(new_consecutive, time.time()) if 'save_backoff_state' in globals() else None
   for i in range(delay):
    time.sleep(1)
    if i % 60 == 0 and i > 0:
     logger.info("[BACKOFF] Waiting... %d/%d", i, delay)
   logger.info("[BACKOFF] Sleep complete. Exiting for fresh process.")
   sys.exit(0)
  else:
   logger.error("[FATAL] Discord HTTP %d: %s", e.status, e)
   sys.exit(0)
 except Exception as e:
  logger.error("[FATAL] Unexpected error: %s", e)
  traceback.print_exc()
  sys.exit(0)
