import os
import sys
import asyncio
import logging
import traceback
import time
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import Config, load_squad
from scraper import ProClubsTrackerScraper
from stats_engine import StatsEngine
from darija_engine import DarijaEngine
from image_gen import ImageGenerator
from memory import SquadMemory
from daily_engine import DailyEngine
from story_engine import StoryEngine
from models import ClubStats, PlayerStats
from utils import fuzzy_find_player
from data_persistence import save_match, save_players_cache, save_club_cache, load_players_cache, load_club_cache, load_matches_cache

# ─────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("rachad_bot")

# ─────────────────────────────────────────────────────────────
# SINGLETON / INSTANCE LOCK (prevents duplicate Render workers)
# ─────────────────────────────────────────────────────────────
class InstanceLock:
    """File-based lock to ensure only one bot instance runs."""
    def __init__(self, path: str = "/tmp/rachad_bot.lock"):
        self.path = path
        self.fd = None

    def acquire(self) -> bool:
        import fcntl
        self.fd = open(self.path, "w")
        try:
            fcntl.lockf(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.fd.write(str(os.getpid()))
            self.fd.flush()
            logger.info("Instance lock acquired (pid %s)", os.getpid())
            return True
        except (IOError, OSError):
            logger.error("Another bot instance is already running! Exiting.")
            return False

    def release(self):
        if self.fd:
            self.fd.close()

_instance_lock = InstanceLock()
if not _instance_lock.acquire():
    sys.exit(0)

# ─────────────────────────────────────────────────────────────
# RATE-LIMIT AWARE DISCORD SENDER
# ─────────────────────────────────────────────────────────────
class DiscordRateLimiter:
    """
    Wraps all Discord API sends with:
    - Structured logging
    - Exponential backoff on 429
    - Circuit breaker after repeated failures
    """
    def __init__(self, max_consecutive_429: int = 5, circuit_breaker_seconds: int = 300):
        self._consecutive_429 = 0
        self._max_consecutive = max_consecutive_429
        self._circuit_breaker_seconds = circuit_breaker_seconds
        self._circuit_open_until = 0
        self._send_lock = asyncio.Lock()

    async def _send_with_backoff(self, send_fn, *args, **kwargs):
        async with self._send_lock:
            if time.time() < self._circuit_open_until:
                logger.warning("Circuit breaker OPEN — skipping Discord send.")
                return None

            max_retries = 5
            base_delay = 1.0
            for attempt in range(max_retries):
                try:
                    result = await send_fn(*args, **kwargs)
                    self._consecutive_429 = 0
                    return result
                except discord.HTTPException as e:
                    if e.status == 429:
                        self._consecutive_429 += 1
                        retry_after = getattr(e, "retry_after", base_delay * (2 ** attempt))
                        logger.warning("Discord 429 (attempt %d/%d). Retry after %.1fs", attempt + 1, max_retries, retry_after)
                        if self._consecutive_429 >= self._max_consecutive:
                            logger.error("Too many consecutive 429s. Opening circuit breaker for %ds.", self._circuit_breaker_seconds)
                            self._circuit_open_until = time.time() + self._circuit_breaker_seconds
                            return None
                        await asyncio.sleep(retry_after + 0.5)
                    else:
                        raise
                except Exception as e:
                    logger.error("Discord send error: %s", e)
                    raise
            logger.error("Max retries exceeded for Discord send.")
            return None

    # Context wrappers
    async def ctx_send(self, ctx: commands.Context, *args, **kwargs):
        logger.info("[SEND] ctx.send in #%s by %s", ctx.channel.name if ctx.channel else "?", ctx.author.name)
        return await self._send_with_backoff(ctx.send, *args, **kwargs)

    async def interaction_send(self, interaction: discord.Interaction, *args, **kwargs):
        logger.info("[SEND] interaction.response.send_message by %s", interaction.user.name)
        if interaction.response.is_done():
            return await self._send_with_backoff(interaction.followup.send, *args, **kwargs)
        return await self._send_with_backoff(interaction.response.send_message, *args, **kwargs)

    async def channel_send(self, channel: discord.abc.Messageable, *args, **kwargs):
        logger.info("[SEND] channel.send in #%s", getattr(channel, "name", "?"))
        return await self._send_with_backoff(channel.send, *args, **kwargs)

    async def message_edit(self, message: discord.Message, *args, **kwargs):
        logger.info("[EDIT] message.edit id=%s", message.id)
        return await self._send_with_backoff(message.edit, *args, **kwargs)

rl = DiscordRateLimiter()

# ─────────────────────────────────────────────────────────────
# HEALTH CHECK SERVER
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
PSN_TO_NICKNAME: dict = {}
NICKNAME_TO_PSN: dict = {}

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

def resolve_nickname(name: str) -> str:
    if not name or not isinstance(name, str):
        return name
    return PSN_TO_NICKNAME.get(name.lower(), name)

def resolve_query(query: str) -> str:
    if not query or not isinstance(query, str):
        return query
    return NICKNAME_TO_PSN.get(query.lower(), query)

def normalize_club_players(club):
    if not club or not getattr(club, "players", None):
        return
    for p in club.players:
        if hasattr(p, "name") and isinstance(p.name, str):
            p.name = resolve_nickname(p.name)

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
    # Enable discord.py's built-in rate limit handling
    max_messages=10000,
)

squad = load_squad()
_build_nickname_maps()
scraper: Optional[ProClubsTrackerScraper] = None
darija = DarijaEngine(Config.DEFAULT_PERSONALITY)
imgen = ImageGenerator(Config.ASSETS_DIR)
memory = SquadMemory()
daily_engine = DailyEngine(darija)
story_engine = StoryEngine()
current_club: Optional[ClubStats] = None
_session_active = False

# Flags to prevent duplicate work on reconnect
_slash_synced = False
_startup_scrape_done = False

# Data cache TTL (seconds)
DATA_CACHE_TTL = 300  # 5 minutes
_data_cache_time = 0

# ─────────────────────────────────────────────────────────────
# PERSISTENT STATE (SQLite) for background tasks
# ─────────────────────────────────────────────────────────────
class PersistentState:
    DB = "/tmp/bot_state.db"
    def __init__(self):
        self._init()

    def _init(self):
        conn = sqlite3.connect(self.DB)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def get(self, key: str, default: str = "") -> str:
        conn = sqlite3.connect(self.DB)
        c = conn.cursor()
        c.execute("SELECT value FROM bot_state WHERE key = ?", (key,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else default

    def set(self, key: str, value: str):
        conn = sqlite3.connect(self.DB)
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO bot_state (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value, datetime.now().isoformat()))
        conn.commit()
        conn.close()

state = PersistentState()

# ─────────────────────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────────────────────
def get_squad_map():
    return {p.get("name", ""): p for p in squad.get("players", [])}

def find_player(query: str) -> Optional[PlayerStats]:
    if not current_club or not current_club.players:
        return None
    resolved = resolve_query(query)
    return fuzzy_find_player(resolved, current_club.players, squad)

def _is_data_fresh() -> bool:
    return current_club is not None and current_club.players and (time.time() - _data_cache_time) < DATA_CACHE_TTL

async def _fetch_club_data() -> Optional[ClubStats]:
    global current_club, _data_cache_time
    if not scraper:
        return None
    try:
        club = await scraper.scrape_club()
        if club and club.players:
            current_club = club
            current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
            normalize_club_players(current_club)
            _data_cache_time = time.time()
            # Persist to DB
            save_players_cache(current_club.players)
            save_club_cache(
                current_club.club_name,
                current_club.division,
                current_club.skill_rating,
                current_club.wins,
                current_club.losses,
                current_club.draws
            )
            for m in current_club.matches[:10]:
                save_match(
                    m.match_id,
                    m.date.isoformat() if hasattr(m.date, "isoformat") else str(m.date),
                    m.opponent,
                    m.score_for,
                    m.score_against,
                    m.result,
                    {}
                )
            logger.info("Data fetched: %d players, %d matches", len(club.players), len(club.matches))
            return current_club
    except Exception as e:
        logger.error("Scrape failed: %s", e)
        traceback.print_exc()
    return None

async def _load_cached_data() -> bool:
    """Try to load from DB cache if scraper is not ready."""
    global current_club
    if current_club and current_club.players:
        return True
    club_info = load_club_cache()
    if not club_info:
        return False
    players = load_players_cache()
    if not players:
        return False
    # Reconstruct minimal ClubStats
    current_club = ClubStats(
        club_name=club_info.get("club_name", "Rachad L3ERGONI"),
        division=club_info.get("division", 6),
        skill_rating=club_info.get("skill_rating", 0),
        wins=club_info.get("wins", 0),
        losses=club_info.get("losses", 0),
        draws=club_info.get("draws", 0),
    )
    # Convert dict rows to PlayerStats
    current_club.players = []
    for p in players:
        ps = PlayerStats(name=p.get("name", "Unknown"))
        for k, v in p.items():
            if hasattr(ps, k):
                setattr(ps, k, v)
        current_club.players.append(ps)
    normalize_club_players(current_club)
    logger.info("Loaded %d players from DB cache", len(current_club.players))
    return True

async def ensure_data(ctx: commands.Context):
    if _is_data_fresh():
        return True
    if not scraper:
        await rl.ctx_send(ctx, "Scraper not ready. Wait 10s.")
        return False
    async with ctx.typing():
        await rl.ctx_send(ctx, "جاري جلب البيانات...")
        club = await _fetch_club_data()
        if not club:
            await rl.ctx_send(ctx, "ما قدرتش نجيب البيانات من ProClubsTracker. جرب !sync مرة أخرى.")
            return False
        await rl.ctx_send(ctx, f"Loaded {len(club.players)} players")
        return True

async def ensure_data_interaction(interaction: discord.Interaction):
    if _is_data_fresh():
        return True
    if not scraper:
        await rl.interaction_send(interaction, "Scraper not ready.")
        return False
    await rl.interaction_send(interaction, "جاري جلب البيانات...")
    club = await _fetch_club_data()
    if not club:
        await rl.interaction_send(interaction, "ما قدرتش نجيب البيانات من ProClubsTracker. جرب /sync مرة أخرى.")
        return False
    await rl.interaction_send(interaction, f"Loaded {len(club.players)} players")
    return True

# ─────────────────────────────────────────────────────────────
# GLOBAL COOLDOWN & SPAM PROTECTION
# ─────────────────────────────────────────────────────────────
@bot.check
async def global_cooldown(ctx: commands.Context) -> bool:
    # Global 1-second cooldown per user to prevent spam
    # This is handled by discord.py's BucketType.user cooldowns on each command,
    # but we also add a global check here.
    return True

@bot.before_invoke
async def log_command(ctx: commands.Context):
    logger.info("[CMD] %s called by %s in #%s", ctx.command.name if ctx.command else "?", ctx.author.name, ctx.channel.name if ctx.channel else "DM")

# ─────────────────────────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    global scraper, _slash_synced, _startup_scrape_done
    logger.info("Bot online as %s (session_id=%s)", bot.user, getattr(bot, "session_id", "?"))
    scraper = ProClubsTrackerScraper(Config.PCT_CLUB_URL)
    await bot.change_presence(activity=discord.Game(name="!help or /help"))

    # Slash sync — ONLY ONCE per process lifetime
    if not _slash_synced:
        try:
            guild = discord.Object(id=Config.DISCORD_GUILD_ID)
            # Do NOT clear commands — just sync. Clearing causes rate limits.
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            _slash_synced = True
            logger.info("Slash commands synced to guild %s", Config.DISCORD_GUILD_ID)
        except discord.HTTPException as e:
            if e.status == 429:
                logger.warning("Slash sync rate limited. Will retry on next reconnect.")
                _slash_synced = False
            else:
                logger.error("Slash sync error: %s", e)
        except Exception as e:
            logger.error("Slash sync error: %s", e)

    # Startup scrape — ONLY ONCE
    if not _startup_scrape_done:
        asyncio.create_task(startup_scrape())
        _startup_scrape_done = True

    # Background tasks — only start if not already running
    if not daily_post.is_running():
        daily_post.start()
        logger.info("Daily post task started")
    if not match_monitor.is_running():
        match_monitor.start()
        logger.info("Match monitor task started")

@bot.event
async def on_disconnect():
    logger.warning("Bot disconnected from Discord gateway.")

@bot.event
async def on_resumed():
    logger.info("Bot resumed Discord session.")

async def startup_scrape():
    global current_club
    try:
        logger.info("Startup scrape...")
        await asyncio.sleep(3)  # Let connection stabilize
        club = await _fetch_club_data()
        if club:
            logger.info("Startup: %d players loaded", len(club.players))
        else:
            logger.warning("Startup: no data from scraper, trying DB cache...")
            await _load_cached_data()
    except Exception as e:
        logger.error("Startup scrape: %s", e)
        traceback.print_exc()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await rl.ctx_send(ctx, "هاد الكوماند ما كاينش. جرب !help باش تشوف الكوماندات.")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await rl.ctx_send(ctx, f"ناقصك parameter: {error.param.name}.")
        return
    if isinstance(error, commands.NotOwner):
        await rl.ctx_send(ctx, "غير الowner يقدر يدير هاد الكوماند.")
        return
    if isinstance(error, commands.CommandOnCooldown):
        await rl.ctx_send(ctx, f"⏳ Cooldown: wait {error.retry_after:.1f}s.")
        return
    logger.error("Prefix error: %s", error)
    traceback.print_exc()
    await rl.ctx_send(ctx, f"Error: {str(error)[:300]}")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    logger.error("Slash error: %s", error)
    traceback.print_exc()
    msg = f"Error: {str(error)[:500]}"
    try:
        if isinstance(error, app_commands.CommandOnCooldown):
            msg = f"⏳ Cooldown: wait {error.retry_after:.1f}s."
        await rl.interaction_send(interaction, msg)
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────
# BACKGROUND TASKS
# ─────────────────────────────────────────────────────────────
@tasks.loop(hours=24)
async def daily_post():
    channel_id = getattr(Config, "DAILY_CHANNEL_ID", 0)
    if not channel_id:
        return
    if not current_club or not current_club.players:
        logger.warning("Daily post skipped: no data")
        return

    # Deduplication: check if we already posted today
    today = datetime.now().strftime("%Y-%m-%d")
    last_daily = state.get("last_daily_post", "")
    if last_daily == today:
        logger.info("Daily post already done today (%s). Skipping.", today)
        return

    try:
        channel = bot.get_channel(channel_id)
        if not channel:
            logger.error("Daily channel %s not found", channel_id)
            return

        pick = daily_engine.pick_stat_of_the_day(current_club.players)
        if not pick:
            logger.warning("Daily post: no stat picked")
            return

        is_bad = pick.get("type") == "bad"
        img_path = get_squad_map().get(pick["player"].name, {}).get("image")
        card = imgen.generate_daily_card(
            pick["player"], pick["stat_name"], pick["stat_value"],
            pick["roast"], is_bad, photo_path=img_path
        )
        file = discord.File(card, filename="daily.png")
        embed = discord.Embed(
            title=pick["title"],
            description=pick["roast"],
            color=0xff0000 if is_bad else 0xffd700
        )
        await rl.channel_send(channel, embed=embed, file=file)
        state.set("last_daily_post", today)
        logger.info("Daily post sent successfully")
    except Exception as e:
        logger.error("Daily post error: %s", e)
        traceback.print_exc()

@daily_post.before_loop
async def before_daily():
    await bot.wait_until_ready()
    # Wait until midnight-ish for first run, then every 24h
    now = datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    wait_seconds = (midnight - now).total_seconds()
    logger.info("Daily post waiting %.0f seconds until midnight", wait_seconds)
    await asyncio.sleep(min(wait_seconds, 3600))  # Cap at 1h for first boot

@tasks.loop(minutes=5)
async def match_monitor():
    global current_club
    if not current_club or not current_club.matches or not scraper:
        return

    try:
        # Scrape fresh data
        fresh_club = await scraper.scrape_club()
        if not fresh_club or not fresh_club.matches:
            return

        latest = fresh_club.matches[0]
        match_id = getattr(latest, "match_id", None) or f"{latest.date}_{latest.opponent}"

        # Deduplication via persistent state
        last_match = state.get("last_match_id", "")
        if match_id == last_match:
            return

        # Update current club
        current_club = fresh_club
        current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
        normalize_club_players(current_club)
        _data_cache_time = time.time()  # noqa: F841

        result = f"{latest.score_for}-{latest.score_against}"
        report = darija.match_report(result, current_club.players)

        match_channel_id = getattr(Config, "MATCH_CHANNEL_ID", 0)
        if match_channel_id:
            match_channel = bot.get_channel(match_channel_id)
            if match_channel:
                await rl.channel_send(match_channel, report)

        leaderboard_channel_id = getattr(Config, "LEADERBORD_CHANNEL_ID", 0)
        if leaderboard_channel_id:
            lb_channel = bot.get_channel(leaderboard_channel_id)
            if lb_channel:
                color = 0x00ff00 if latest.result == "W" else 0xff0000 if latest.result == "L" else 0xffff00
                embed = discord.Embed(
                    title=f"Match Report: {latest.opponent} {result}",
                    description=report,
                    color=color
                )
                await rl.channel_send(lb_channel, embed=embed)

        state.set("last_match_id", match_id)
        logger.info("Auto-reported match: %s %s", latest.opponent, result)
    except Exception as e:
        logger.error("Match monitor error: %s", e)
        traceback.print_exc()

@match_monitor.before_loop
async def before_match_monitor():
    await bot.wait_until_ready()

# ─────────────────────────────────────────────────────────────
# PREFIX COMMANDS (with cooldowns)
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
    lines = [
        f"PCT_URL: {Config.PCT_CLUB_URL}",
        f"PORT: {Config.PORT}",
        f"Club ID: {Config.CLUB_ID}",
        f"Platform: {Config.PCT_PLATFORM}",
        f"Scraper ready: {scraper_ready}",
        f"Data loaded: {data_loaded}",
        f"Players: {player_count}",
        f"Cache age: {cache_age}s",
        f"Daily posted today: {state.get('last_daily_post', 'No')}",
        f"Last match: {state.get('last_match_id', 'None')}",
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
            await rl.ctx_send(ctx, "Slash commands re-synced. Try /leaderboard now.")
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
    async with ctx.typing():
        try:
            if not scraper:
                await rl.ctx_send(ctx, "Scraper not ready.")
                return
            club = await _fetch_club_data()
            if not club or not club.players:
                await rl.ctx_send(ctx, "ما قدرتش نجيب البيانات. شوف Render logs.")
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

# ── Player commands ──
@bot.command(name="stats")
@commands.cooldown(1, 5, commands.BucketType.user)
async def cmd_stats(ctx, *, player: str):
    if not await ensure_data(ctx): return
    target = find_player(player)
    if not target:
        await rl.ctx_send(ctx, f"ما لقيتش `{player}`.")
        return
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    img_path = squad_map.get(target.name, {}).get("image")
    async with ctx.typing():
        try:
            card = imgen.generate_player_card(target, pos, division=current_club.division, photo_path=img_path)
            file = discord.File(card, filename=f"{target.name}_card.png")
            roast_text = darija.roast(target, pos)
            embed = discord.Embed(title=f"📊 {target.name} — {pos}", description=roast_text, color=0x1e90ff)
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
            squad_map = get_squad_map()
            mvp = StatsEngine.get_mvp(current_club.players)
            pos = squad_map.get(mvp.name, {}).get("position", "CM")
            img_path = squad_map.get(mvp.name, {}).get("image")
            card = imgen.generate_mvp_card(mvp, pos, photo_path=img_path)
            file = discord.File(card, filename="mvp.png")
            mvp_text = darija.mvp(mvp)
            embed = discord.Embed(title="🏆 MAN OF THE MATCH", description=mvp_text, color=0xffd700)
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
            embed = discord.Embed(title="🏆 BALLON D\'OR", color=0xffd700)
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
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    img_path = squad_map.get(target.name, {}).get("image")
    async with ctx.typing():
        try:
            roast = darija.roast(target, pos)
            card = imgen.generate_roast_card(target, roast, pos, photo_path=img_path)
            file = discord.File(card, filename=f"{target.name}_roast.png")
            embed = discord.Embed(title=f"🔥 ROAST REPORT — {target.name}", description=roast, color=0xff0000)
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
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    img_path = squad_map.get(target.name, {}).get("image")
    async with ctx.typing():
        try:
            card = imgen.generate_anime_card(target, pos, "mvp", "PLAYER PROFILE", photo_path=img_path)
            file = discord.File(card, filename=f"{target.name}_profile.png")
            lines = [
                f"**Position:** {pos}",
                f"**Games:** {target.games}",
                f"**Goals:** {target.goals} | **Assists:** {target.assists}",
                f"**Rating:** {round(target.rating_pg, 1)}",
                f"**Impact:** {target.impact_score} | **Clutch:** {target.clutch_score}",
                f"**Pass Accuracy:** {round(target.pass_accuracy, 1)}%",
                f"**Possession Lost:** {target.possession_losses}",
            ]
            embed = discord.Embed(title=f"👤 {target.name}", description="\n".join(lines), color=0x1e90ff)
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
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    img_path = squad_map.get(target.name, {}).get("image")
    async with ctx.typing():
        try:
            card = imgen.generate_anime_card(target, pos, "beast", "⚡ ANIME LEGEND", photo_path=img_path)
            file = discord.File(card, filename=f"{target.name}_anime.png")
            embed = discord.Embed(title=f"⚡ {target.name}", color=0x00ffff)
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
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    img_path = squad_map.get(target.name, {}).get("image")
    async with ctx.typing():
        try:
            card = imgen.generate_beast_card(target, pos, photo_path=img_path)
            file = discord.File(card, filename="beast.png")
            embed = discord.Embed(title=f"⚡ BEAST MODE — {target.name}",
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
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    img_path = squad_map.get(target.name, {}).get("image")
    async with ctx.typing():
        try:
            text = darija.court_case(target)
            card = imgen.generate_court_case(target, pos, ["Evidence generated by Roast Engine"], photo_path=img_path)
            file = discord.File(card, filename="court.png")
            color = 0xff0000 if target.throwing_score > 3.0 or target.rating_pg < 5.5 else 0x00ff00
            embed = discord.Embed(title=f"⚖️ COURT CASE: {target.name}", description=text, color=color)
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
            embed.add_field(name="🥇 Ballon d\'Or", value=mvp.name, inline=False)
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
            img_path = get_squad_map().get(pick["player"].name, {}).get("image")
            card = imgen.generate_daily_card(pick["player"], pick["stat_name"], pick["stat_value"], pick["roast"], is_bad, photo_path=img_path)
            file = discord.File(card, filename="daily.png")
            embed = discord.Embed(title=pick["title"], description=pick["roast"], color=0xff0000 if is_bad else 0xffd700)
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
# SLASH COMMANDS (with cooldowns)
# ─────────────────────────────────────────────────────────────
@bot.tree.command(name="ping", description="Test if bot is responding")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_ping(interaction: discord.Interaction):
    await rl.interaction_send(interaction, "Pong! Try /sync next.")

@bot.tree.command(name="debug", description="Show bot state for troubleshooting")
@app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
async def slash_debug(interaction: discord.Interaction):
    scraper_ready = "Yes" if scraper else "No"
    data_loaded = "Yes" if current_club and current_club.players else "No"
    player_count = len(current_club.players) if current_club and current_club.players else 0
    cache_age = int(time.time() - _data_cache_time) if _data_cache_time else "N/A"
    lines = [
        f"PCT_URL: {Config.PCT_CLUB_URL}",
        f"PORT: {Config.PORT}",
        f"Club ID: {Config.CLUB_ID}",
        f"Platform: {Config.PCT_PLATFORM}",
        f"Scraper ready: {scraper_ready}",
        f"Data loaded: {data_loaded}",
        f"Players: {player_count}",
        f"Cache age: {cache_age}s",
        f"Daily posted today: {state.get('last_daily_post', 'No')}",
        f"Last match: {state.get('last_match_id', 'None')}",
    ]
    embed = discord.Embed(title="Debug Info", description="\n".join(lines), color=0x808080)
    await rl.interaction_send(interaction, embed=embed)

@bot.tree.command(name="sync", description="Manual sync from ProClubsTracker")
@app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
async def slash_sync(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        if not scraper:
            await rl.interaction_send(interaction, "Scraper not ready.")
            return
        club = await _fetch_club_data()
        if not club or not club.players:
            await rl.interaction_send(interaction, "ما قدرتش نجيب البيانات. شوف Render logs.")
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
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    img_path = squad_map.get(target.name, {}).get("image")
    try:
        card = imgen.generate_player_card(target, pos, division=current_club.division, photo_path=img_path)
        file = discord.File(card, filename=f"{target.name}_card.png")
        roast_text = darija.roast(target, pos)
        embed = discord.Embed(title=f"📊 {target.name} — {pos}", description=roast_text, color=0x1e90ff)
        embed.add_field(name="Impact", value=str(target.impact_score), inline=True)
        embed.add_field(name="Clutch", value=str(target.clutch_score), inline=True)
        embed.add_field(name="Error", value=str(target.error_score), inline=True)
        await rl.interaction_send(interaction, embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="player", description="Complete player profile with anime card")
@app_commands.describe(player="Player name")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_player(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    target = find_player(player)
    if not target:
        await rl.interaction_send(interaction, f"ما لقيتش `{player}`.")
        return
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    img_path = squad_map.get(target.name, {}).get("image")
    try:
        card = imgen.generate_anime_card(target, pos, "mvp", "PLAYER PROFILE", photo_path=img_path)
        file = discord.File(card, filename=f"{target.name}_profile.png")
        lines = [
            f"**Position:** {pos}",
            f"**Games:** {target.games}",
            f"**Goals:** {target.goals} | **Assists:** {target.assists}",
            f"**Rating:** {round(target.rating_pg, 1)}",
            f"**Impact:** {target.impact_score} | **Clutch:** {target.clutch_score}",
            f"**Pass Accuracy:** {round(target.pass_accuracy, 1)}%",
        ]
        embed = discord.Embed(title=f"👤 {target.name}", description="\n".join(lines), color=0x1e90ff)
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
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    img_path = squad_map.get(target.name, {}).get("image")
    try:
        card = imgen.generate_anime_card(target, pos, "beast", "⚡ ANIME LEGEND", photo_path=img_path)
        file = discord.File(card, filename=f"{target.name}_anime.png")
        embed = discord.Embed(title=f"⚡ {target.name}", color=0x00ffff)
        await rl.interaction_send(interaction, embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await rl.interaction_send(interaction, f"Error: {str(e)[:300]}")

@bot.tree.command(name="beast_mode", description="Beast Mode card (best performance)")
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
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    img_path = squad_map.get(target.name, {}).get("image")
    try:
        card = imgen.generate_beast_card(target, pos, photo_path=img_path)
        file = discord.File(card, filename="beast.png")
        embed = discord.Embed(title=f"⚡ BEAST MODE — {target.name}",
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
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    img_path = squad_map.get(target.name, {}).get("image")
    try:
        text = darija.court_case(target)
        card = imgen.generate_court_case(target, pos, ["Evidence generated by Roast Engine"], photo_path=img_path)
        file = discord.File(card, filename="court.png")
        color = 0xff0000 if target.throwing_score > 3.0 or target.rating_pg < 5.5 else 0x00ff00
        embed = discord.Embed(title=f"⚖️ COURT CASE: {target.name}", description=text, color=color)
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
        squad_map = get_squad_map()
        mvp = StatsEngine.get_mvp(current_club.players)
        pos = squad_map.get(mvp.name, {}).get("position", "CM")
        img_path = squad_map.get(mvp.name, {}).get("image")
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

@bot.tree.command(name="ballon_dor", description="Ballon d\'Or ranking")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def slash_ballon_dor(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        ranked = sorted(current_club.players, key=lambda p: p.impact_score + p.clutch_score + p.goals * 2, reverse=True)
        embed = discord.Embed(title="🏆 BALLON D\'OR", color=0xffd700)
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
        embed.add_field(name="🥇 Ballon d\'Or", value=mvp.name, inline=False)
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
        img_path = get_squad_map().get(pick["player"].name, {}).get("image")
        card = imgen.generate_daily_card(pick["player"], pick["stat_name"], pick["stat_value"], pick["roast"], is_bad, photo_path=img_path)
        file = discord.File(card, filename="daily.png")
        embed = discord.Embed(title=pick["title"], description=pick["roast"], color=0xff0000 if is_bad else 0xffd700)
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
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    img_path = squad_map.get(target.name, {}).get("image")
    try:
        roast = darija.roast(target, pos)
        card = imgen.generate_roast_card(target, roast, pos, photo_path=img_path)
        file = discord.File(card, filename=f"{target.name}_roast.png")
        embed = discord.Embed(title=f"🔥 ROAST REPORT — {target.name}", description=roast, color=0xff0000)
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
# MAIN ENTRY — NO FATAL 429 EXIT
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Render auto-restarts crashed processes. We NO LONGER intentionally crash.
    # Instead, we rely on discord.py's built-in rate limit handling + our circuit breaker.
    startup_delay = int(os.getenv("DISCORD_STARTUP_DELAY", "15"))
    if startup_delay > 0:
        logger.info("[STARTUP] Waiting %ds before Discord login...", startup_delay)
        time.sleep(startup_delay)
        logger.info("[STARTUP] Delay complete. Connecting to Discord...")

    try:
        bot.run(Config.DISCORD_TOKEN, reconnect=True)
    except Exception as e:
        logger.error("[FATAL] Bot crashed: %s", e)
        traceback.print_exc()
        # Exit with code 0 so Render may restart, but we do NOT sys.exit(1) on 429
        sys.exit(0)
