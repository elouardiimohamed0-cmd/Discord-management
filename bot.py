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
import hashlib  # ✅ needed for video cache
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
def get_match_players(club: ClubStats, match: MatchResult):
    if not hasattr(match, "player_stats") or not match.player_stats:
        return club.players
    match_psns = set(k.lower() for k in match.player_stats.keys())
    result = []
    for p in club.players:
        raw_psn = getattr(p, "_raw_psn", "").lower()
        p_name = getattr(p, "name", "").lower()
        if raw_psn in match_psns or p_name in match_psns:
            result.append(p)
    return result if result else club.players

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
    """Resolve a squad.json image path to an actually-existing file.

    Handles three real-world mismatches:
      1. Exact path exists.
      2. Same basename, different extension/casing (.jpg vs .JPG vs .jpeg vs .png vs .webp).
      3. Case-insensitive filename (squad.json says DICTATOR.jpg but disk has
         Dictator.jpg — common on Linux/Fly which are case-sensitive).
    """
    if not photo_path:
        return None
    if os.path.exists(photo_path):
        return photo_path

    base, ext = os.path.splitext(photo_path)

    # 1) Same basename, different extension/casing
    ext_alts = (".jpg", ".jpeg", ".JPG", ".JPEG", ".png", ".PNG", ".webp", ".WEBP")
    for alt_ext in ext_alts:
        if alt_ext.lower() == ext.lower():
            continue
        alt = base + alt_ext
        if os.path.exists(alt):
            return alt

    # 2) Case-insensitive directory scan
    directory = os.path.dirname(photo_path) or "."
    target_name_lower = os.path.basename(photo_path).lower()
    target_base_lower = os.path.splitext(target_name_lower)[0]
    try:
        if os.path.isdir(directory):
            entries = os.listdir(directory)
            # Exact filename, any case
            for entry in entries:
                if entry.lower() == target_name_lower:
                    return os.path.join(directory, entry)
            # Same basename, any image extension, any case
            valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
            for entry in entries:
                e_base, e_ext = os.path.splitext(entry)
                if e_base.lower() == target_base_lower and e_ext.lower() in valid_exts:
                    return os.path.join(directory, entry)
    except OSError:
        pass

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
    global current_club
    try:
        data = await scraper.get_club_data(force=False, source="background")
        if not data:
            logger.warning("Match monitor: no data from scraper")
            return

        club = _dict_to_club(data)
        if not club or not club.matches:
            return

        latest = club.matches[0]
        match_id = getattr(latest, "match_id", None) or f"{latest.date}_{latest.opponent}"

        if current_club and current_club.matches:
            last_id = getattr(current_club.matches[0], "match_id", "")
            if match_id == last_id:
                logger.info("Match monitor: no new match")
                return

        current_club = club
        current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
        normalize_club_players(current_club)

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

        logger.info("Auto-reported match: %s %s", latest.opponent, result)
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
        "**Compare:** `!compare p1 p2` `!lastmatch` `!club` `!leaderboard [metric]`\n\n"
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
            # darija.roast(player, roast_type) — roast_type expects "fraud"/"ghost"/"carry"/"general".
            # Previously we passed pos ("CM" etc.) which silently fell through to the default.
            # The worst-impact player is conceptually a fraud, so route to fraud_phrases.
            roast = darija.roast(worst, "fraud")
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
            pos = get_squad_map().get(fraud.name, {}).get("position", "CM")
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
            pos = get_squad_map().get(carry.name, {}).get("position", "CM")
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
            pos = get_squad_map().get(target.name, {}).get("position", "CM")
            is_fraud = target.throwing_score > 3.0
            if is_fraud:
                text = darija.fraud(target)
                color = 0xff0000
            else:
                text = f"✅ CLEAN\n\n{target.name} — Throwing: {target.throwing_score}\n\nهادا لاعب صحيح."
                color = 0x00ff00
            emb
