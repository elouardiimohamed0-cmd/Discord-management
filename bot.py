import os
import sys
import asyncio
import logging
import traceback
import time
import json
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

# ─── ACTIVE PLAYER FILTER ───
# Only keep players who appear in recent match data.
# This prevents inactive squad members from showing in commands.

def filter_active_players(club: ClubStats) -> None:
    """
    Remove players who don't appear in any recent match.
    Uses squad.json to bridge PSN mismatches (e.g., Kira69Meniari -> A999KIRA).
    """
    if not club or not club.matches:
        return

    active_psns = set()
    for m in club.matches:
        if hasattr(m, "player_stats") and m.player_stats:
            active_psns.update(m.player_stats.keys())

    if not active_psns:
        logger.warning("[FILTER] No match player data found, skipping filter")
        return

    squad_map = get_squad_map()
    filtered = []
    for p in club.players:
        p_name = getattr(p, "name", "")
        if not p_name:
            continue

        # Find PSN for this player via squad.json
        psn = None
        for sq_name, info in squad_map.items():
            if sq_name and sq_name.lower() == p_name.lower():
                psn = (info.get("psn") or "").strip()
                break

        if not psn:
            psn = p_name

        psn_lower = psn.lower()
        if psn_lower in active_psns or p_name.lower() in active_psns:
            filtered.append(p)
        else:
            logger.info("[FILTER] Excluding %s (PSN: %s): not in recent match data", p_name, psn)

    before = len(club.players)
    club.players = filtered
    after = len(club.players)
    logger.info("[FILTER] Active players: %d / %d (removed %d inactive)", after, before, before - after)


def get_match_players(club: ClubStats, match: MatchResult):
    """Return only players who played in a specific match."""
    if not hasattr(match, "player_stats") or not match.player_stats:
        return club.players

    match_psns = set(match.player_stats.keys())
    squad_map = get_squad_map()

    # Build reverse map: squad_name -> psn
    squad_to_psn = {}
    for sq_name, info in squad_map.items():
        psn = (info.get("psn") or "").strip().lower()
        if psn:
            squad_to_psn[sq_name.lower()] = psn

    result = []
    for p in club.players:
        p_name = getattr(p, "name", "").lower()
        psn = squad_to_psn.get(p_name, p_name)
        if psn in match_psns or p_name in match_psns:
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
darija = DarijaEngine(Config.DEFAULT_PERSONALITY)
imgen = ImageGenerator(Config.ASSETS_DIR)
memory = SquadMemory()
daily_engine = DailyEngine(darija)
story_engine = StoryEngine()
current_club = None
_session_active = False
_slash_synced = False
_startup_scrape_done = False
_data_cache_time = 0
DATA_CACHE_TTL = 600  # 10 minutes

# ─────────────────────────────────────────────────────────────
# DATA CONVERSION: dict -> ClubStats/PlayerStats
# ─────────────────────────────────────────────────────────────
# ─── IMAGE PATH RESOLVER (handles .jpg ↔ .jpeg fallback) ───
def resolve_image_path(photo_path: str) -> Optional[str]:
    """Try the exact path, then fallback extensions."""
    if not photo_path:
        return None
    if os.path.exists(photo_path):
        return photo_path
    # Try alternative extensions
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

# ─── SQUAD NAME RESOLVER ───
def get_squad_display_name(player_name: str) -> str:
    """Return the proper squad.json name for a player, or the original name."""
    if not player_name or not isinstance(player_name, str):
        return player_name or "Unknown"
    sq = get_squad_map()
    # Direct match (case-insensitive)
    for sq_name, info in sq.items():
        if sq_name and sq_name.lower() == player_name.strip().lower():
            return info.get("name", sq_name)
    # Check if any squad name is contained in player name
    for sq_name, info in sq.items():
        if sq_name and sq_name.lower() in player_name.lower():
            return info.get("name", sq_name)
    # Check if player name is contained in any squad name
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
            if not raw_name or not isinstance(raw_name, str) or not raw_name.strip():
                raw_name = "Unknown"
            pct_name = raw_name.strip()

            # Try to find squad.json info for this player
            sq_info = get_squad_info(pct_name)
            if not sq_info and pro_name:
                sq_info = get_squad_info(pro_name)

            if sq_info:
                # Use squad.json name for display
                display_name = sq_info.get("name") or pct_name
                ps = PlayerStats(name=display_name)
                ps._squad_info = sq_info  # internal attribute for image/position
            else:
                ps = PlayerStats(name=pct_name)
                ps._squad_info = {}

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

# ─────────────────────────────────────────────────────────────
# DATA LOADING (NO COMMAND SCraping)
# ─────────────────────────────────────────────────────────────
def get_squad_map():
    """Handle both {"players": [...]} and flat {nickname: {...}} squad.json structures."""
    result = {}
    if isinstance(squad, dict):
        if "players" in squad:
            result = {p.get("name", ""): p for p in squad.get("players", []) if isinstance(p, dict)}
        else:
            result = {p.get("name", ""): p for p in squad.values() if isinstance(p, dict)}
    if not result:
        logger.warning("[SQUAD] squad.json loaded but get_squad_map() returned empty. squad type=%s, keys=%s",
                       type(squad).__name__, list(squad.keys())[:10] if isinstance(squad, dict) else "N/A")
    else:
        logger.info("[SQUAD] Loaded %d players from squad.json", len(result))
    return result

# ─── SQUAD INFO RESOLVER ───
def get_squad_info(pct_name: str) -> dict:
    """Find squad.json entry by PCT name, PSN, proName, or nickname match."""
    if not pct_name or not isinstance(pct_name, str):
        return {}
    sq = get_squad_map()
    pct_lower = pct_name.strip().lower()

    # Direct match by name
    for sq_name, info in sq.items():
        if sq_name and sq_name.lower() == pct_lower:
            return info

    # Match by PSN
    for info in sq.values():
        psn = (info.get("psn") or "").strip().lower()
        if psn and psn == pct_lower:
            return info

    # Match by proName / ea_id
    for info in sq.values():
        pro = (info.get("proName") or info.get("ea_id") or "").strip().lower()
        if pro and pro == pct_lower:
            return info

    # Partial match
    for sq_name, info in sq.items():
        if sq_name and (pct_lower in sq_name.lower() or sq_name.lower() in pct_lower):
            return info

    return {}

def _name_similarity(a: str, b: str) -> float:
    """Simple similarity score: 0.0 to 1.0"""
    if not a or not b:
        return 0.0
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return 1.0
    if a in b or b in a:
        return max(len(a), len(b)) / max(len(a), len(b), 1) * 0.8
    # Count common characters
    common = sum((a + b).count(c) for c in set(a) & set(b))
    return common / max(len(a) + len(b), 1)

def find_player(query: str) -> Optional[PlayerStats]:
    """
    Find player by real name, nickname, PSN, or proName.
    Tries multiple strategies in order of specificity.
    """
    if not current_club or not current_club.players:
        return None
    if not query or not isinstance(query, str):
        return None

    query_clean = query.strip().lower()
    players = current_club.players
    squad_map = get_squad_map()

    # Strategy 1: Exact match on normalized player name
    for p in players:
        name = getattr(p, "name", "")
        if name and isinstance(name, str) and name.strip().lower() == query_clean:
            return p

    # Strategy 2: Exact match on resolved PSN/nickname
    resolved = resolve_query(query)
    if resolved and resolved.lower() != query_clean:
        for p in players:
            name = getattr(p, "name", "")
            if name and isinstance(name, str) and name.strip().lower() == resolved.lower().strip():
                return p

    # Strategy 3: Partial match on player name (contains)
    for p in players:
        name = getattr(p, "name", "")
        if name and isinstance(name, str) and query_clean in name.strip().lower():
            return p

    # Strategy 4: Partial match on squad name, PSN, nickname, or proName
    for p in players:
        name = getattr(p, "name", "")
        if not name or not isinstance(name, str):
            continue
        info = squad_map.get(name.strip(), {})
        # Check squad name
        sq_name = (info.get("name") or "").strip().lower()
        if query_clean in sq_name or sq_name == query_clean:
            return p
        # Check squad PSN
        sq_psn = (info.get("psn") or info.get("PSN") or "").strip().lower()
        if query_clean in sq_psn or sq_psn == query_clean:
            return p
        # Check squad nickname
        sq_nick = (info.get("nickname") or "").strip().lower()
        if query_clean in sq_nick or sq_nick == query_clean:
            return p
        # Check proName
        sq_pro = (info.get("proName") or "").strip().lower()
        if query_clean in sq_pro or sq_pro == query_clean:
            return p

    # Strategy 5: Reverse lookup - query might be a PSN/proName, find matching squad name
    for sq_name, info in squad_map.items():
        sq_psn = (info.get("psn") or info.get("PSN") or "").strip().lower()
        sq_nick = (info.get("nickname") or "").strip().lower()
        sq_pro = (info.get("proName") or "").strip().lower()
        if query_clean == sq_psn or query_clean == sq_nick or query_clean == sq_pro or query_clean in sq_psn or query_clean in sq_nick or query_clean in sq_pro:
            # Found squad entry matching query, now find player with that squad name
            for p in players:
                p_name = getattr(p, "name", "")
                if p_name and isinstance(p_name, str) and p_name.strip().lower() == sq_name.lower().strip():
                    return p

    # Strategy 6: Fuzzy match - find closest name by similarity
    best_match = None
    best_score = 0.0
    for p in players:
        name = getattr(p, "name", "")
        if not name or not isinstance(name, str):
            continue
        score = _name_similarity(query_clean, name.strip())
        # Also check squad aliases
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
    """Fetch from scraper service. ONLY called by background tasks or manual sync."""
    global current_club, _data_cache_time
    try:
        data = await scraper.get_club_data(force=force, source=source)
        if data:
            club = _dict_to_club(data)
            if club and club.players:
                current_club = club
                current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
                normalize_club_players(current_club)
                filter_active_players(current_club)  # ← ONLY SHOW PLAYERS WHO PLAYED
                _data_cache_time = time.time()
                logger.info("Data loaded: %d players, %d matches", len(club.players), len(club.matches))
                return current_club
    except Exception as e:
        logger.error("Fetch error: %s", e)
        traceback.print_exc()
        return None

async def ensure_data(ctx: commands.Context):
    """Commands NEVER scrape. They only check if cached data exists."""
    if _is_data_fresh():
        return True
    if current_club and current_club.players:
        # Validate that players have names
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
        except Exception as e:
            logger.error("Slash sync error: %s", e)

    if not _startup_scrape_done:
        asyncio.create_task(startup_scrape())
        _startup_scrape_done = True

    if not daily_post.is_running():
        daily_post.start()
        logger.info("Daily task started")
    if not match_monitor.is_running():
        match_monitor.start()
        logger.info("Match monitor started")

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
# BACKGROUND TASKS (ONLY these trigger scraping)
# ─────────────────────────────────────────────────────────────
@tasks.loop(hours=24)
async def daily_post():
    channel_id = getattr(Config, "DAILY_CHANNEL_ID", 0)
    if not channel_id or not current_club or not current_club.players:
        return
    try:
        channel = bot.get_channel(channel_id)
        if not channel:
            return
        pick = daily_engine.pick_stat_of_the_day(current_club.players)
        if not pick:
            return
        is_bad = pick.get("type") == "bad"
        sq_info = getattr(pick["player"], "_squad_info", {}) or {}
        raw_img = sq_info.get("image")
        img_path = resolve_image_path(raw_img)
        display_name = pick["player"].name
        card = imgen.generate_daily_card(pick["player"], pick["stat_name"], pick["stat_value"], pick["roast"], is_bad, photo_path=img_path)
        file = discord.File(card, filename="daily.png")
        embed = discord.Embed(title=pick.get("title", f"📊 Daily Stat — {display_name}"), description=pick["roast"], color=0xff0000 if is_bad else 0xffd700)
        await rl.channel_send(channel, embed=embed, file=file)
        logger.info("Daily post sent")
    except Exception as e:
        logger.error("Daily post error: %s", e)
        traceback.print_exc()

@daily_post.before_loop
async def before_daily():
    await bot.wait_until_ready()
    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    wait = (midnight - now).total_seconds()
    logger.info("Daily post waiting %.0fs until midnight", wait)
    await asyncio.sleep(min(wait, 3600))

@tasks.loop(minutes=10)  # Changed from 5 to 10 minutes
async def match_monitor():
    """Background task: scrape every 10 minutes. Commands NEVER scrape."""
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

        # Check if this is actually new
        if current_club and current_club.matches:
            last_id = getattr(current_club.matches[0], "match_id", "")
            if match_id == last_id:
                logger.info("Match monitor: no new match")
                return

        # Update current club
        current_club = club
        current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
        normalize_club_players(current_club)
        filter_active_players(current_club)

        result = f"{latest.score_for}-{latest.score_against}"
        
        # ONLY use players who played in THIS match
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

# ─────────────────────────────────────────────────────────────
# PREFIX COMMANDS (with cooldowns) — NEVER scrape
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
        "**Player Cards:** `!stats [player]` `!player [player]` `!anime_card [player]` `!beast_mode [player]`\n\n"
        "**Rankings:** `!mvp` `!worst` `!carry` `!ballon` `!ghost` `!ball_loser` `!playmaker` `!sniper` `!keeper`\n\n"
        "**Roast Engine:** `!fraud [player]` `!who_sold` `!pass` `!court_case [player]` `!serial_offender [player]` `!hall_of_shame`\n\n"
        "**Compare:** `!compare p1 p2` `!lastmatch` `!club` `!leaderboard [metric]`\n\n"
        "**History:** `!history [player]` `!rankings` `!awards`\n\n"
        "**Fun:** `!daily` `!story` `!banter` `!drama` `!meme [player]` `!transfer [player]` `!predict`\n\n"
        "**Settings:** `!personality [mode]` `!roast` `!stop` `!roastplayer [player]`"
    )
    embed.add_field(name="All Commands", value=text, inline=False)
    await rl.ctx_send(ctx, embed=embed)

@bot.command(name="sync")
@commands.cooldown(1, 30, commands.BucketType.user)
async def cmd_sync(ctx):
    """Manual sync — triggers ONE scrape via ScraperService."""
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

# ── Player commands (all read from current_club cache, NEVER scrape) ──
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
            card = imgen.generate_player_card(target, pos, division=current_club.division, photo_path=img_path)
            file = discord.File(card, filename=f"{display_name}_card.png")
            roast_text = darija.roast(target, pos)
            embed = discord.Embed(title=f"📊 {display_name} — {pos}", description=roast_text, color=0x1e90ff)
            embed.add_field(name="Impact", value=str(target.impact_score), inline=True)
            embed.add_field(name="Clutch", value=str(target.clutch_score), inline=True)
            embed.add_field(name="Error", value=str(target.error_score), inline=True)
            await rl.ctx_send(ctx, embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

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
            card = imgen.generate_mvp_card(mvp, pos, photo_path=img_path)
            file = discord.File(card, filename="mvp.png")
            mvp_text = darija.mvp(mvp)
            embed = discord.Embed(title=f"🏆 MAN OF THE MATCH — {display_name}", description=mvp_text, color=0xffd700)
            embed.add_field(name="Goals", value=str(mvp.goals), inline=True)
            embed.add_field(name="Assists", value=str(mvp.assists), inline=True)
            embed.add_field(name="Rating", value=str(round(mvp.rating_pg, 1)), inline=True)
            await rl.ctx_send(ctx, embed=embed, file=file)
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
            embed = discord.Embed(title="🗑️ WORST PLAYER", description=roast, color=0x8b0000)
            await rl.ctx_send(ctx, embed=embed)
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
            embed = discord.Embed(title="🎭 FRAUD DETECTED", description=roast, color=0xff4500)
            await rl.ctx_send(ctx, embed=embed)
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
            embed = discord.Embed(title="💪 CARRY DETECTED", description=praise, color=0x00ff00)
            await rl.ctx_send(ctx, embed=embed)
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
            embed = discord.Embed(title="FRAUD CHECK", description=text, color=color)
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
                embed.add_field(name=f"{medal} {p.name}", value=f"Impact: {p.impact_score} | Goals: {p.goals} | Rating: {round(p.rating_pg, 1)}", inline=False)
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
            pos = get_squad_map().get(ghost.name, {}).get("position", "CM")
            roast = darija.ghost(ghost)
            embed = discord.Embed(title="👻 GHOST DETECTED", description=roast, color=0x9370db)
            await rl.ctx_send(ctx, embed=embed)
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
            pos = get_squad_map().get(hog.name, {}).get("position", "CM")
            roast = darija.ball_loser(hog)
            embed = discord.Embed(title="⚽ PASS THE BALL!", description=roast, color=0xffa500)
            await rl.ctx_send(ctx, embed=embed)
        except Exception as e:
            traceback.print_exc()
            await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="leaderboard")
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_leaderboard(ctx, metric: str = "impact"):
    if not await ensure_data(ctx): return
    metric_map = {"impact": "impact_score", "goals": "goals", "assists": "assists", "rating": "rating_pg", "clutch": "clutch_score"}
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
            embed.add_field(name=p1.name, value=f"Impact: {p1.impact_score}\nGoals: {p1.goals}\nAssists: {p1.assists}\nRating: {round(p1.rating_pg, 1)}", inline=True)
            embed.add_field(name=p2.name, value=f"Impact: {p2.impact_score}\nGoals: {p2.goals}\nAssists: {p2.assists}\nRating: {round(p2.rating_pg, 1)}", inline=True)
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

@bot.command(name="banter")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_banter(ctx):
    try:
        text = darija.banter()
        embed = discord.Embed(title="☕ Cafeteria Banter", description=text, color=0xffa500)
        await rl.ctx_send(ctx, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="drama")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_drama(ctx):
    if not await ensure_data(ctx): return
    try:
        names = [p.name for p in current_club.players[:2]] if current_club.players else ["Player1", "Player2"]
        text = darija.drama(names)
        embed = discord.Embed(title="🍿 Drama Alert", description=text, color=0xff1493)
        await rl.ctx_send(ctx, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="meme")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_meme(ctx, *, player: str = "Player"):
    try:
        text = darija.meme(resolve_nickname(player))
        embed = discord.Embed(title="😂 Darija Meme", description=text, color=0x00ff7f)
        await rl.ctx_send(ctx, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="transfer")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_transfer(ctx, *, player: str):
    try:
        text = darija.transfer(resolve_nickname(player))
        embed = discord.Embed(title="📰 Transfer News", description=text, color=0x1e90ff)
        await rl.ctx_send(ctx, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="predict")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_predict(ctx):
    if not await ensure_data(ctx): return
    try:
        names = [p.name for p in current_club.players[:2]] if current_club.players else ["Player1", "Player2"]
        text = darija.predict(names)
        embed = discord.Embed(title="🔮 Match Prediction", description=text, color=0x9400d3)
        await rl.ctx_send(ctx, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="personality")
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_personality(ctx, mode: str):
    valid = ["casablanca", "analyst", "toxic", "coach", "commentator", "cafeteria"]
    if mode.lower() not in valid:
        await rl.ctx_send(ctx, f"Personality غير صحيح. Valid: {', '.join(valid)}")
        return
    try:
        darija.set_personality(mode.lower())
        embed = discord.Embed(title="🎭 Personality Switch", description=f"Changed to: **{mode.capitalize()}**", color=0x9370db)
        await rl.ctx_send(ctx, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="roast")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_roast(ctx):
    global _session_active
    _session_active = True
    darija.set_personality("casablanca")
    embed = discord.Embed(title="🔥 ROAST MODE ACTIVATED", description="Session monitoring started.", color=0xff4500)
    await rl.ctx_send(ctx, embed=embed)

@bot.command(name="stop")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_stop(ctx):
    global _session_active
    _session_active = False
    await rl.ctx_send(ctx, "⏹️ Session Stopped.")

@bot.command(name="roastplayer")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_roastplayer(ctx, *, player: str):
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
            roast = darija.roast(target, pos)
            card = imgen.generate_roast_card(target, roast, pos, photo_path=img_path)
            file = discord.File(card, filename=f"{display_name}_roast.png")
            embed = discord.Embed(title=f"🔥 ROAST REPORT — {display_name}", description=roast, color=0xff0000)
            await rl.ctx_send(ctx, embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="serial_offender")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_serial_offender(ctx, *, player: str = None):
    if not await ensure_data(ctx): return
    if not player:
        target = min(current_club.players, key=lambda p: p.rating_pg)
    else:
        target = find_player(player)
    if not target:
        await rl.ctx_send(ctx, "ما لقيتش player.")
        return
    async with ctx.typing():
        try:
            bad_games = memory.get_consecutive_bad_games(target.name) if hasattr(memory, 'get_consecutive_bad_games') else 0
            text = darija.serial_offender(target, bad_games)
            embed = discord.Embed(title=f"🚨 Serial Offender — {target.name}", description=text, color=0x8b0000)
            await rl.ctx_send(ctx, embed=embed)
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
            card = imgen.generate_anime_card(target, pos, "mvp", "PLAYER PROFILE", photo_path=img_path)
            file = discord.File(card, filename=f"{display_name}_profile.png")
            lines = [
                f"**Position:** {pos}",
                f"**Games:** {target.games}",
                f"**Goals:** {target.goals} | **Assists:** {target.assists}",
                f"**Rating:** {round(target.rating_pg, 1)}",
                f"**Impact:** {target.impact_score} | **Clutch:** {target.clutch_score}",
                f"**Pass Accuracy:** {round(target.pass_accuracy, 1)}%",
                f"**Possession Lost:** {target.possession_losses}",
            ]
            embed = discord.Embed(title=f"👤 {display_name}", description="\n".join(lines), color=0x1e90ff)
            await rl.ctx_send(ctx, embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="anime_card")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_anime_card(ctx, *, player: str):
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
            card = imgen.generate_anime_card(target, pos, "beast", "⚡ ANIME LEGEND", photo_path=img_path)
            file = discord.File(card, filename=f"{display_name}_anime.png")
            embed = discord.Embed(title=f"⚡ {display_name}", color=0x00ffff)
            await rl.ctx_send(ctx, embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="beast_mode")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_beast_mode(ctx, *, player: str = None):
    if not await ensure_data(ctx): return
    if player:
        target = find_player(player)
    else:
        target = max(current_club.players, key=lambda p: p.impact_score) if current_club.players else None
    if not target:
        await rl.ctx_send(ctx, "ما لقيتش player.")
        return
    sq_info = getattr(target, "_squad_info", {}) or {}
    pos = sq_info.get("position", "CM")
    raw_img = sq_info.get("image")
    img_path = resolve_image_path(raw_img)
    display_name = target.name
    async with ctx.typing():
        try:
            card = imgen.generate_beast_card(target, pos, photo_path=img_path)
            file = discord.File(card, filename="beast.png")
            embed = discord.Embed(title=f"⚡ BEAST MODE — {display_name}",
                                  description=f"Impact: {target.impact_score} | Goals: {target.goals} | Rating: {round(target.rating_pg, 1)}",
                                  color=0x00bfff)
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
            card = imgen.generate_court_case(target, pos, ["Evidence generated by Roast Engine"], photo_path=img_path)
            file = discord.File(card, filename="court.png")
            color = 0xff0000 if target.throwing_score > 3.0 or target.rating_pg < 5.5 else 0x00ff00
            embed = discord.Embed(title=f"⚖️ COURT CASE: {display_name}", description=text, color=color)
            await rl.ctx_send(ctx, embed=embed, file=file)
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
            pos = get_squad_map().get(loser.name, {}).get("position", "CM")
            roast = darija.ball_loser(loser)
            embed = discord.Embed(title="💀 BALL LOSER", description=roast, color=0x8b0000)
            await rl.ctx_send(ctx, embed=embed)
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
            card = imgen.generate_playmaker_card(pm, pos, photo_path=img_path)
            file = discord.File(card, filename="playmaker.png")
            embed = discord.Embed(title="🎨 PLAYMAKER", description=text, color=0x00ff00)
            await rl.ctx_send(ctx, embed=embed, file=file)
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
            card = imgen.generate_sniper_card(sniper, pos, photo_path=img_path)
            file = discord.File(card, filename="sniper.png")
            embed = discord.Embed(title="🎯 SNIPER", description=f"**{sniper.name}** — {sniper.goals} goals | Rating: {round(sniper.rating_pg, 1)}", color=0xff4500)
            await rl.ctx_send(ctx, embed=embed, file=file)
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
            embed = discord.Embed(title="🧤 KEEPER", description=text, color=0x1e90ff)
            await rl.ctx_send(ctx, embed=embed)
        except Exception as e:
            traceback.print_exc()
            await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="history")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_history(ctx, *, player: str):
    if not await ensure_data(ctx): return
    target = find_player(player)
    if not target:
        await rl.ctx_send(ctx, f"ما لقيتش `{player}`.")
        return
    try:
        mem = memory.get_player_memory(target.name)
        if not mem:
            await rl.ctx_send(ctx, f"ما عنديش تاريخ لـ {target.name}.")
            return
        embed = discord.Embed(title=f"📜 History — {target.name}", color=0x9370db)
        embed.add_field(name="Total Games", value=mem["total_games"], inline=True)
        embed.add_field(name="Total Goals", value=mem["total_goals"], inline=True)
        embed.add_field(name="Total Assists", value=mem["total_assists"], inline=True)
        embed.add_field(name="Best Rating", value=mem["best_rating"], inline=True)
        embed.add_field(name="Worst Rating", value=mem["worst_rating"], inline=True)
        embed.add_field(name="Consecutive Bad", value=mem["consecutive_bad"], inline=True)
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
            embed.add_field(name="🏆 MVP", value=f"{mvp.name} (Impact: {mvp.impact_score})", inline=False)
            embed.add_field(name="🗑️ Worst", value=f"{worst.name} (Impact: {worst.impact_score})", inline=False)
            embed.add_field(name="🎭 Fraud", value=f"{fraud.name} (Throwing: {fraud.throwing_score})", inline=False)
            embed.add_field(name="💪 Carry", value=f"{carry.name} (Impact: {carry.impact_score})", inline=False)
            embed.add_field(name="👻 Ghost", value=f"{ghost.name} ({ghost.minutes_played}min)", inline=False)
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
            embed.add_field(name="🥇 Ballon d'Or", value=mvp.name, inline=False)
            embed.add_field(name="⚽ Golden Boot", value=f"{top_scorer.name} ({top_scorer.goals} goals)", inline=False)
            embed.add_field(name="🅰️ Playmaker Award", value=f"{top_assist.name} ({top_assist.assists} assists)", inline=False)
            embed.add_field(name="🤡 Fraud of the Season", value=f"{fraud.name} ({fraud.throwing_score} throwing)", inline=False)
            await rl.ctx_send(ctx, embed=embed)
        except Exception as e:
            traceback.print_exc()
            await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="daily")
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_daily(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            pick = daily_engine.pick_stat_of_the_day(current_club.players)
            if not pick:
                await rl.ctx_send(ctx, "ما قدرتش نجيب daily stat.")
                return
            is_bad = pick.get("type") == "bad"
            raw_img = get_squad_map().get(pick["player"].name, {}).get("image")
            img_path = resolve_image_path(raw_img)
            display_name = get_squad_display_name(pick["player"].name)
            card = imgen.generate_daily_card(pick["player"], pick["stat_name"], pick["stat_value"], pick["roast"], is_bad, photo_path=img_path)
            file = discord.File(card, filename="daily.png")
            embed = discord.Embed(title=pick.get("title", f"📊 Daily Stat — {display_name}"), description=pick["roast"], color=0xff0000 if is_bad else 0xffd700)
            await rl.ctx_send(ctx, embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

@bot.command(name="story")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_story(ctx):
    if not await ensure_data(ctx): return
    try:
        text = story_engine.generate_story(current_club.players)
        embed = discord.Embed(title="📖 Story of the Day", description=text, color=0x9370db)
        await rl.ctx_send(ctx, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.ctx_send(ctx, f"Error: {str(e)[:300]}")

# ─────────────────────────────────────────────────────────────
# SLASH COMMANDS (with cooldowns) — NEVER scrape
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

@bot.tree.command(name="stats", description="Player stats + premium card")
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
        card = imgen.generate_player_card(target, pos, division=current_club.division, photo_path=img_path)
        file = discord.File(card, filename=f"{display_name}_card.png")
        roast_text = darija.roast(target, pos)
        embed = discord.Embed(title=f"📊 {display_name} — {pos}", description=roast_text, color=0x1e90ff)
        embed.add_field(name="Impact", value=str(target.impact_score), inline=True)
        embed.add_field(name="Clutch", value=str(target.clutch_score), inline=True)
        embed.add_field(name="Error", value=str(target.error_score), inline=True)
        await rl.interaction_send(interaction, embed=embed, file=file)
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
        card = imgen.generate_anime_card(target, pos, "mvp", "PLAYER PROFILE", photo_path=img_path)
        file = discord.File(card, filename=f"{display_name}_profile.png")
        lines = [
            f"**Position:** {pos}",
            f"**Games:** {target.games}",
            f"**Goals:** {target.goals} | **Assists:** {target.assists}",
            f"**Rating:** {round(target.rating_pg, 1)}",
            f"**Impact:** {target.impact_score} | **Clutch:** {target.clutch_score}",
            f"**Pass Accuracy:** {round(target.pass_accuracy, 1)}%",
        ]
        embed = discord.Embed(title=f"👤 {display_name}", description="\n".join(lines), color=0x1e90ff)
        await rl.interaction_send(interaction, embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="anime_card", description="Premium anime player card")
@app_commands.describe(player="Player name")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_anime_card(interaction: discord.Interaction, player: str):
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
        card = imgen.generate_anime_card(target, pos, "beast", "⚡ ANIME LEGEND", photo_path=img_path)
        file = discord.File(card, filename=f"{display_name}_anime.png")
        embed = discord.Embed(title=f"⚡ {display_name}", color=0x00ffff)
        await rl.interaction_send(interaction, embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="beast_mode", description="Beast Mode card")
@app_commands.describe(player="Player name (optional)")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_beast_mode(interaction: discord.Interaction, player: str = None):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    if player:
        target = find_player(player)
    else:
        target = max(current_club.players, key=lambda p: p.impact_score) if current_club.players else None
    if not target:
        await rl.interaction_send(interaction, "ما لقيتش player.")
        return
    sq_info = getattr(target, "_squad_info", {}) or {}
    pos = sq_info.get("position", "CM")
    raw_img = sq_info.get("image")
    img_path = resolve_image_path(raw_img)
    display_name = target.name
    try:
        card = imgen.generate_beast_card(target, pos, photo_path=img_path)
        file = discord.File(card, filename="beast.png")
        embed = discord.Embed(title=f"⚡ BEAST MODE — {display_name}",
                              description=f"Impact: {target.impact_score} | Goals: {target.goals} | Rating: {round(target.rating_pg, 1)}",
                              color=0x00bfff)
        await rl.interaction_send(interaction, embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="court_case", description="Put a player on trial")
@app_commands.describe(player="Player name")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_court_case(interaction: discord.Interaction, player: str):
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
        text = darija.court_case(target)
        card = imgen.generate_court_case(target, pos, ["Evidence generated by Roast Engine"], photo_path=img_path)
        file = discord.File(card, filename="court.png")
        color = 0xff0000 if target.throwing_score > 3.0 or target.rating_pg < 5.5 else 0x00ff00
        embed = discord.Embed(title=f"⚖️ COURT CASE: {display_name}", description=text, color=color)
        await rl.interaction_send(interaction, embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="mvp", description="MVP of the season")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_mvp(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        mvp = StatsEngine.get_mvp(current_club.players)
        sq_info = getattr(mvp, "_squad_info", {}) or {}
        pos = sq_info.get("position", "CM")
        raw_img = sq_info.get("image")
        img_path = resolve_image_path(raw_img)
        display_name = mvp.name
        card = imgen.generate_mvp_card(mvp, pos, photo_path=img_path)
        file = discord.File(card, filename="mvp.png")
        mvp_text = darija.mvp(mvp)
        embed = discord.Embed(title="🏆 MAN OF THE MATCH", description=mvp_text, color=0xffd700)
        embed.add_field(name="Goals", value=str(mvp.goals), inline=True)
        embed.add_field(name="Assists", value=str(mvp.assists), inline=True)
        embed.add_field(name="Rating", value=str(round(mvp.rating_pg, 1)), inline=True)
        await rl.interaction_send(interaction, embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="worst", description="Worst player of the week")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_worst(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        worst = StatsEngine.get_worst(current_club.players)
        pos = get_squad_map().get(worst.name, {}).get("position", "CM")
        roast = darija.roast(worst, pos)
        embed = discord.Embed(title="🗑️ WORST PLAYER", description=roast, color=0x8b0000)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="who_sold", description="Who sold the match")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_who_sold(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        fraud = StatsEngine.get_fraud(current_club.players)
        pos = get_squad_map().get(fraud.name, {}).get("position", "CM")
        roast = darija.fraud(fraud)
        embed = discord.Embed(title="🎭 FRAUD DETECTED", description=roast, color=0xff4500)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="carry_detector", description="Who is carrying the team")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_carry(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        carry = StatsEngine.get_carry(current_club.players)
        pos = get_squad_map().get(carry.name, {}).get("position", "CM")
        praise = darija.carry(carry)
        embed = discord.Embed(title="💪 CARRY DETECTED", description=praise, color=0x00ff00)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="fraud_check", description="Check if a player is fraud")
@app_commands.describe(player="Player name, PSN, or nickname")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_fraud_check(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    target = find_player(player)
    if not target:
        await rl.interaction_send(interaction, f"ما لقيتش `{player}`.")
        return
    try:
        pos = get_squad_map().get(target.name, {}).get("position", "CM")
        is_fraud = target.throwing_score > 3.0
        if is_fraud:
            text = darija.fraud(target)
            color = 0xff0000
        else:
            text = f"✅ CLEAN\n\n{target.name} — Throwing: {target.throwing_score}\n\nهادا لاعب صحيح."
            color = 0x00ff00
        embed = discord.Embed(title="FRAUD CHECK", description=text, color=color)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="ballon_dor", description="Ballon d'Or ranking")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_ballon_dor(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        ranked = sorted(current_club.players, key=lambda p: p.impact_score + p.clutch_score + p.goals * 2, reverse=True)
        embed = discord.Embed(title="🏆 BALLON D'OR", color=0xffd700)
        medals = ["🥇", "🥈", "🥉"]
        for i, p in enumerate(ranked[:5]):
            medal = medals[i] if i < 3 else f"{i+1}."
            embed.add_field(name=f"{medal} {p.name}", value=f"Impact: {p.impact_score} | Goals: {p.goals} | Rating: {round(p.rating_pg, 1)}", inline=False)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="ghost_detector", description="Detect inactive players")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_ghost(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        ghost = StatsEngine.get_ghost(current_club.players)
        pos = get_squad_map().get(ghost.name, {}).get("position", "CM")
        roast = darija.ghost(ghost)
        embed = discord.Embed(title="👻 GHOST DETECTED", description=roast, color=0x9370db)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="pass_the_ball", description="Call out ball hog")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_pass_ball(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        hog = StatsEngine.get_ball_hog(current_club.players)
        pos = get_squad_map().get(hog.name, {}).get("position", "CM")
        roast = darija.ball_loser(hog)
        embed = discord.Embed(title="⚽ PASS THE BALL!", description=roast, color=0xffa500)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="ball_loser", description="Most possession losses")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_ball_loser(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        loser = max(current_club.players, key=lambda p: p.possession_losses)
        pos = get_squad_map().get(loser.name, {}).get("position", "CM")
        roast = darija.ball_loser(loser)
        embed = discord.Embed(title="💀 BALL LOSER", description=roast, color=0x8b0000)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="playmaker", description="Best creator")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_playmaker(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        pm = max(current_club.players, key=lambda p: p.assists * 2 + p.pass_accuracy)
        pos = get_squad_map().get(pm.name, {}).get("position", "CM")
        text = darija.playmaker(pm)
        img_path = get_squad_map().get(pm.name, {}).get("image")
        card = imgen.generate_playmaker_card(pm, pos, photo_path=img_path)
        file = discord.File(card, filename="playmaker.png")
        embed = discord.Embed(title="🎨 PLAYMAKER", description=text, color=0x00ff00)
        await rl.interaction_send(interaction, embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="sniper", description="Best finisher")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_sniper(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        sniper = max(current_club.players, key=lambda p: p.goals * 2 + p.rating_pg)
        pos = get_squad_map().get(sniper.name, {}).get("position", "CM")
        img_path = get_squad_map().get(sniper.name, {}).get("image")
        card = imgen.generate_sniper_card(sniper, pos, photo_path=img_path)
        file = discord.File(card, filename="sniper.png")
        embed = discord.Embed(title="🎯 SNIPER", description=f"**{sniper.name}** — {sniper.goals} goals | Rating: {round(sniper.rating_pg, 1)}", color=0xff4500)
        await rl.interaction_send(interaction, embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="keeper", description="Best goalkeeper")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_keeper(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        gks = [p for p in current_club.players if get_squad_map().get(p.name, {}).get("position") == "GK"]
        if not gks:
            await rl.interaction_send(interaction, "ما لقيتش goalkeeper فالفريق.")
            return
        keeper = max(gks, key=lambda p: p.tackles + p.interceptions)
        text = darija.keeper(keeper)
        embed = discord.Embed(title="🧤 KEEPER", description=text, color=0x1e90ff)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="leaderboard", description="Leaderboard with visual card")
@app_commands.describe(metric="Metric to rank by")
@app_commands.choices(metric=[
    app_commands.Choice(name="Impact Score", value="impact_score"),
    app_commands.Choice(name="Goals", value="goals"),
    app_commands.Choice(name="Assists", value="assists"),
    app_commands.Choice(name="Rating", value="rating_pg"),
    app_commands.Choice(name="Clutch", value="clutch_score"),
])
@app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
async def slash_leaderboard(interaction: discord.Interaction, metric: app_commands.Choice[str]):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        card = imgen.generate_leaderboard(current_club.players, metric.value)
        file = discord.File(card, filename="leaderboard.png")
        embed = discord.Embed(title=f"📊 Leaderboard — {metric.name}", color=0x1e90ff)
        await rl.interaction_send(interaction, embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="compare", description="1v1 player comparison")
@app_commands.describe(player1="First player", player2="Second player")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_compare(interaction: discord.Interaction, player1: str, player2: str):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    p1 = find_player(player1)
    p2 = find_player(player2)
    if not p1 or not p2:
        await rl.interaction_send(interaction, "ما لقيتش players.")
        return
    try:
        text = darija.compare(p1, p2)
        embed = discord.Embed(title="⚔️ 1v1 COMPARISON", description=text, color=0xff4500)
        embed.add_field(name=p1.name, value=f"Impact: {p1.impact_score}\nGoals: {p1.goals}\nAssists: {p1.assists}\nRating: {round(p1.rating_pg, 1)}", inline=True)
        embed.add_field(name=p2.name, value=f"Impact: {p2.impact_score}\nGoals: {p2.goals}\nAssists: {p2.assists}\nRating: {round(p2.rating_pg, 1)}", inline=True)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="lastmatch", description="Last match + result")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_lastmatch(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    if not current_club.matches:
        await rl.interaction_send(interaction, "ما لقيتش match history.")
        return
    try:
        last = current_club.matches[0]
        color = 0x00ff00 if last.result == "W" else 0xff0000 if last.result == "L" else 0xffff00
        embed = discord.Embed(title=f"⚽ Last Match: {last.score_for} - {last.score_against} vs {last.opponent}", description=f"Result: {last.result} • {last.date.strftime('%d/%m/%Y')}", color=color)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="clubinfo", description="Club overview + match report card")
@app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
async def slash_clubinfo(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        motm = StatsEngine.get_mvp(current_club.players)
        card = imgen.generate_match_report(current_club, motm)
        file = discord.File(card, filename="club_report.png")
        embed = discord.Embed(title=f"🏟️ {current_club.club_name}", description=f"Division {current_club.division} • Skill {current_club.skill_rating}", color=0x00ff00)
        await rl.interaction_send(interaction, embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="history", description="Player performance history")
@app_commands.describe(player="Player name")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_history(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    target = find_player(player)
    if not target:
        await rl.interaction_send(interaction, f"ما لقيتش `{player}`.")
        return
    try:
        mem = memory.get_player_memory(target.name)
        if not mem:
            await rl.interaction_send(interaction, f"ما عنديش تاريخ لـ {target.name}.")
            return
        embed = discord.Embed(title=f"📜 History — {target.name}", color=0x9370db)
        embed.add_field(name="Total Games", value=mem["total_games"], inline=True)
        embed.add_field(name="Total Goals", value=mem["total_goals"], inline=True)
        embed.add_field(name="Total Assists", value=mem["total_assists"], inline=True)
        embed.add_field(name="Best Rating", value=mem["best_rating"], inline=True)
        embed.add_field(name="Worst Rating", value=mem["worst_rating"], inline=True)
        embed.add_field(name="Consecutive Bad", value=mem["consecutive_bad"], inline=True)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="rankings", description="All rankings")
@app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
async def slash_rankings(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        embed = discord.Embed(title="📊 ALL RANKINGS", color=0x1e90ff)
        mvp = StatsEngine.get_mvp(current_club.players)
        worst = StatsEngine.get_worst(current_club.players)
        fraud = StatsEngine.get_fraud(current_club.players)
        carry = StatsEngine.get_carry(current_club.players)
        ghost = StatsEngine.get_ghost(current_club.players)
        embed.add_field(name="🏆 MVP", value=f"{mvp.name} (Impact: {mvp.impact_score})", inline=False)
        embed.add_field(name="🗑️ Worst", value=f"{worst.name} (Impact: {worst.impact_score})", inline=False)
        embed.add_field(name="🎭 Fraud", value=f"{fraud.name} (Throwing: {fraud.throwing_score})", inline=False)
        embed.add_field(name="💪 Carry", value=f"{carry.name} (Impact: {carry.impact_score})", inline=False)
        embed.add_field(name="👻 Ghost", value=f"{ghost.name} ({ghost.minutes_played}min)", inline=False)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="awards", description="Season awards")
@app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
async def slash_awards(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        embed = discord.Embed(title="🏅 SEASON AWARDS", color=0xffd700)
        mvp = StatsEngine.get_mvp(current_club.players)
        top_scorer = max(current_club.players, key=lambda p: p.goals)
        top_assist = max(current_club.players, key=lambda p: p.assists)
        fraud = StatsEngine.get_fraud(current_club.players)
        embed.add_field(name="🥇 Ballon d'Or", value=mvp.name, inline=False)
        embed.add_field(name="⚽ Golden Boot", value=f"{top_scorer.name} ({top_scorer.goals} goals)", inline=False)
        embed.add_field(name="🅰️ Playmaker Award", value=f"{top_assist.name} ({top_assist.assists} assists)", inline=False)
        embed.add_field(name="🤡 Fraud of the Season", value=f"{fraud.name} ({fraud.throwing_score} throwing)", inline=False)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="daily", description="Stat of the Day")
@app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
async def slash_daily(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        pick = daily_engine.pick_stat_of_the_day(current_club.players)
        if not pick:
            await rl.interaction_send(interaction, "ما قدرتش نجيب daily stat.")
            return
        is_bad = pick.get("type") == "bad"
        sq_info = getattr(pick["player"], "_squad_info", {}) or {}
        raw_img = sq_info.get("image")
        img_path = resolve_image_path(raw_img)
        display_name = pick["player"].name
        card = imgen.generate_daily_card(pick["player"], pick["stat_name"], pick["stat_value"], pick["roast"], is_bad, photo_path=img_path)
        file = discord.File(card, filename="daily.png")
        embed = discord.Embed(title=pick.get("title", f"📊 Daily Stat — {display_name}"), description=pick["roast"], color=0xff0000 if is_bad else 0xffd700)
        await rl.interaction_send(interaction, embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="story", description="Story of the Day")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_story(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        text = story_engine.generate_story(current_club.players)
        embed = discord.Embed(title="📖 Story of the Day", description=text, color=0x9370db)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="banter", description="Football trash talk")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_banter(interaction: discord.Interaction):
    try:
        text = darija.banter()
        embed = discord.Embed(title="☕ Cafeteria Banter", description=text, color=0xffa500)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="drama", description="Drama / polemique")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_drama(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        names = [p.name for p in current_club.players[:2]] if current_club.players else ["Player1", "Player2"]
        text = darija.drama(names)
        embed = discord.Embed(title="🍿 Drama Alert", description=text, color=0xff1493)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="meme", description="Meme b Darija")
@app_commands.describe(player="Player name (optional)")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_meme(interaction: discord.Interaction, player: str = None):
    try:
        target = player or "Player"
        text = darija.meme(resolve_nickname(target))
        embed = discord.Embed(title="😂 Darija Meme", description=text, color=0x00ff7f)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="transfer", description="Transfer rumor")
@app_commands.describe(player="Player name")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_transfer(interaction: discord.Interaction, player: str):
    try:
        text = darija.transfer(resolve_nickname(player))
        embed = discord.Embed(title="📰 Transfer News", description=text, color=0x1e90ff)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="predict", description="Match prediction")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_predict(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        names = [p.name for p in current_club.players[:2]] if current_club.players else ["Player1", "Player2"]
        text = darija.predict(names)
        embed = discord.Embed(title="🔮 Match Prediction", description=text, color=0x9400d3)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="personality", description="Switch bot personality")
@app_commands.describe(mode="Personality mode")
@app_commands.choices(mode=[
    app_commands.Choice(name="Casablanca Street", value="casablanca"),
    app_commands.Choice(name="Football Analyst", value="analyst"),
    app_commands.Choice(name="Toxic Teammate", value="toxic"),
    app_commands.Choice(name="Coach", value="coach"),
    app_commands.Choice(name="Commentator", value="commentator"),
    app_commands.Choice(name="Cafeteria Banter", value="cafeteria"),
])
@app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
async def slash_personality(interaction: discord.Interaction, mode: app_commands.Choice[str]):
    try:
        darija.set_personality(mode.value)
        embed = discord.Embed(title="🎭 Personality Switch", description=f"Changed to: **{mode.name}**", color=0x9370db)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="roast", description="Activate roast mode")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_roast(interaction: discord.Interaction):
    global _session_active
    _session_active = True
    darija.set_personality("casablanca")
    embed = discord.Embed(title="🔥 ROAST MODE ACTIVATED", description="Session monitoring started.", color=0xff4500)
    await rl.interaction_send(interaction, embed=embed)

@bot.tree.command(name="stop", description="Stop roast session")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_stop(interaction: discord.Interaction):
    global _session_active
    _session_active = False
    await rl.interaction_send(interaction, "⏹️ Session Stopped.")

@bot.tree.command(name="roastplayer", description="Roast a specific player")
@app_commands.describe(player="Player name")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_roastplayer(interaction: discord.Interaction, player: str):
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
        roast = darija.roast(target, pos)
        card = imgen.generate_roast_card(target, roast, pos, photo_path=img_path)
        file = discord.File(card, filename=f"{display_name}_roast.png")
        embed = discord.Embed(title=f"🔥 ROAST REPORT — {display_name}", description=roast, color=0xff0000)
        await rl.interaction_send(interaction, embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="serial_offender", description="Player with repeated bad performances")
@app_commands.describe(player="Player to investigate (optional)")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_serial_offender(interaction: discord.Interaction, player: str = None):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    if not player:
        target = min(current_club.players, key=lambda p: p.rating_pg)
    else:
        target = find_player(player)
    if not target:
        await rl.interaction_send(interaction, "ما لقيتش player.")
        return
    try:
        bad_games = memory.get_consecutive_bad_games(target.name) if hasattr(memory, 'get_consecutive_bad_games') else 0
        text = darija.serial_offender(target, bad_games)
        embed = discord.Embed(title=f"🚨 Serial Offender — {target.name}", description=text, color=0x8b0000)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="hall_of_shame", description="Worst performances ever recorded")
@app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
async def slash_hall_of_shame(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        text = darija.hall_of_shame(current_club.players)
        embed = discord.Embed(title="🏛️ Hall of Shame", description=text, color=0x8b0000)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="help", description="Show all commands")
@app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
async def slash_help(interaction: discord.Interaction):
    try:
        embed = discord.Embed(
            title="Rachad L3ERGONI Bot",
            description="الخطوة الأولى: دير /sync أو !sync\n\nبعدها تقدر تستعمل كل شي:",
            color=0x1e90ff
        )
        text = (
            "**Basic:** /ping /debug /resync /sync\n\n"
            "**Player Cards:** /stats [player] /player [player] /anime_card [player] /beast_mode [player]\n\n"
            "**Rankings:** /mvp /worst /carry_detector /ballon_dor /ghost_detector /ball_loser /playmaker /sniper /keeper\n\n"
            "**Roast Engine:** /fraud_check [player] /who_sold /pass_the_ball /court_case [player] /serial_offender [player] /hall_of_shame\n\n"
            "**Compare:** /compare p1 p2 /lastmatch /clubinfo /leaderboard\n\n"
            "**History:** /history [player] /rankings /awards\n\n"
            "**Fun:** /daily /story /banter /drama /meme [player] /transfer [player] /predict\n\n"
            "**Settings:** /personality [mode] /roast /stop /roastplayer [player]"
        )
        embed.add_field(name="All Commands", value=text, inline=False)
        await rl.interaction_send(interaction, embed=embed)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

# ─────────────────────────────────────────────────────────────
# MAIN ENTRY — Clean process per attempt
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
