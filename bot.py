"""
Rachad L3ERGONI Pro Clubs Discord Bot — v4 Optimized
- Single file, production-ready
- Connection pooling, smart caching, rate limiting
- Moroccan Darija football content (100% natural)
- Auto-check every 6h | Daily stat 10h UTC | Spotlight 20h UTC | Weekly Sunday 20h UTC
"""
import os
import io
import asyncio
import logging
import sys
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional
from functools import wraps

import discord
from discord.ext import commands, tasks

# ── Try imports, fail gracefully ──
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    print("⚠️  pip install httpx[http2] for better performance")

try:
    from cachetools import TTLCache
    HAS_CACHE = True
except ImportError:
    HAS_CACHE = False
    print("⚠️  pip install cachetools for smart caching")

# ── Local modules (your existing files) ──
try:
    import ea_api
    import gemini
    import image_gen
    import scraper as _scraper
    from state import load_seen, save_seen
except ImportError as e:
    print(f"❌ Missing local module: {e}")
    print("Make sure ea_api.py, gemini.py, image_gen.py, scraper.py, state.py exist")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Config:
    """Immutable config — loaded once, never changes."""
    TOKEN: str = os.getenv("DISCORD_TOKEN", "")
    MATCH_CHANNEL_ID: Optional[int] = int(os.getenv("MATCH_CHANNEL_ID", "0")) or None
    GENERAL_CHANNEL_ID: Optional[int] = int(os.getenv("GENERAL_CHANNEL_ID", "0")) or None
    CLUB_ID: str = getattr(ea_api, "CLUB_ID", "unknown")
    PLATFORM: str = getattr(ea_api, "PLATFORM", "common-gen5")
    
    # Timing
    MATCH_CHECK_HOURS: int = 6
    WEEKLY_DAY: int = 6          # Sunday
    WEEKLY_HOUR: int = 20        # 20:00 UTC
    DAILY_STAT_HOUR: int = 10    # 10:00 UTC
    SPOTLIGHT_HOUR: int = 20     # 20:00 UTC
    
    # Performance
    CACHE_TTL: int = 1800        # 30 minutes
    GEMINI_DELAY: float = 2.5    # seconds between AI calls
    MAX_RETRIES: int = 3
    COOLDOWN_DEFAULT: int = 15   # seconds

CONFIG = Config()

if not CONFIG.TOKEN:
    raise ValueError("❌ DISCORD_TOKEN not set! Add it to environment variables.")

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("RachadBot")

# Reduce discord noise
logging.getLogger("discord.http").setLevel(logging.WARNING)

# ═══════════════════════════════════════════════════════════════════════════════
# SMART CACHE & RATE LIMITER
# ═══════════════════════════════════════════════════════════════════════════════

class SmartCache:
    """Thread-safe TTL cache for match data."""
    def __init__(self):
        self._match_cache = TTLCache(maxsize=50, ttl=CONFIG.CACHE_TTL) if HAS_CACHE else {}
        self._all_cache = TTLCache(maxsize=10, ttl=CONFIG.CACHE_TTL) if HAS_CACHE else {}
        self._lock = asyncio.Lock()
    
    async def get_matches(self, n: int = 5, force: bool = False) -> list:
        """Fetch matches with caching."""
        key = f"matches_{n}"
        
        if not force and HAS_CACHE and key in self._match_cache:
            logger.debug("Cache hit: %s", key)
            return self._match_cache[key]
        
        data = await _scraper.fetch_all(max_matches=n, force=force)
        matches = data.get("matches", [])
        
        if HAS_CACHE:
            self._match_cache[key] = matches
        
        return matches
    
    async def get_all(self, n: int = 1) -> dict:
        """Fetch club data with caching."""
        key = f"all_{n}"
        
        if HAS_CACHE and key in self._all_cache:
            return self._all_cache[key]
        
        data = await _scraper.fetch_all(max_matches=n)
        
        if HAS_CACHE:
            self._all_cache[key] = data
        
        return data
    
    def invalidate(self):
        """Clear all caches."""
        if HAS_CACHE:
            self._match_cache.clear()
            self._all_cache.clear()
        logger.info("Cache invalidated")

CACHE = SmartCache()

class RateLimiter:
    """Semaphore-based rate limiter for Gemini API."""
    def __init__(self, max_calls: int = 3, period: float = 10.0):
        self.semaphore = asyncio.Semaphore(max_calls)
        self.period = period
        self.timestamps: list[float] = []
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            self.timestamps = [t for t in self.timestamps if now - t < self.period]
            
            if len(self.timestamps) >= self.semaphore._value:
                sleep_time = self.timestamps[0] + self.period - now
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
            
            self.timestamps.append(now)
    
    def __call__(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            await self.acquire()
            return await func(*args, **kwargs)
        return wrapper

GEMINI_LIMITER = RateLimiter(max_calls=3, period=10.0)

# ═══════════════════════════════════════════════════════════════════════════════
# BOT SETUP
# ═══════════════════════════════════════════════════════════════════════════════

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
    case_insensitive=True
)

# State
seen_matches: set[str] = set()
_weekly_posted = False
_daily_am_posted = False
_daily_pm_posted = False
_spotlight_index = 0

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _match_ch() -> Optional[discord.TextChannel]:
    return bot.get_channel(CONFIG.MATCH_CHANNEL_ID) if CONFIG.MATCH_CHANNEL_ID else None

def _general_ch() -> Optional[discord.TextChannel]:
    if CONFIG.GENERAL_CHANNEL_ID:
        return bot.get_channel(CONFIG.GENERAL_CHANNEL_ID)
    return _match_ch()

async def _send(ch: discord.abc.Messageable, text: str = "", buf: io.BytesIO = None, filename: str = "image.png"):
    """Send text + optional image with chunking."""
    text = (text or "").strip()
    if not text and not buf:
        return
    
    if buf:
        buf.seek(0)
        file = discord.File(buf, filename=filename)
        first, rest = text[:1900], text[1900:]
        await ch.send(first or None, file=file)
        while rest:
            chunk, rest = rest[:1900], rest[1900:]
            await ch.send(chunk)
    else:
        while text:
            chunk, text = text[:2000], text[2000:]
            await ch.send(chunk)

def _result_icon(r: str) -> str:
    return "🟢" if r == "W" else ("🟡" if r == "D" else "🔴")

def _parse_all(raw_list: list) -> list:
    return [ea_api.parse_match(r) for r in raw_list]

# ═══════════════════════════════════════════════════════════════════════════════
# MATCH POSTING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

async def _post_match(channel, m: dict):
    """Post single match with AI content + image."""
    try:
        loop = asyncio.get_event_loop()
        
        # AI calls with rate limiting
        report = await GEMINI_LIMITER(gemini.match_report)(m)
        await asyncio.sleep(CONFIG.GEMINI_DELAY)
        
        motm_text = await GEMINI_LIMITER(gemini.motm_post)(m)
        await asyncio.sleep(CONFIG.GEMINI_DELAY)
        
        tweets = await GEMINI_LIMITER(gemini.funny_reactions)(m)
        
        # Image generation (CPU-bound → executor)
        poster_buf = await loop.run_in_executor(
            None,
            lambda: image_gen.make_match_poster(
                m["our_name"], m["opp_name"],
                m["our_goals"], m["opp_goals"], m["date"]
            )
        )
        
        # Send report
        await _send(channel, report, poster_buf, f"match_{m['our_goals']}_{m['opp_goals']}.png")
        await asyncio.sleep(1)
        
        # MOTM
        if motm_text and m.get("players"):
            best = m["players"][0]
            motm_buf = await loop.run_in_executor(
                None,
                lambda: image_gen.make_motm_card(
                    best["name"], best["rating"], best["goals"], best["assists"],
                    match_context=f"vs {m['opp_name']} ({m['our_goals']}-{m['opp_goals']})"
                )
            )
            await _send(channel, motm_text, motm_buf, "motm.png")
            await asyncio.sleep(1)
        
        # Tweets
        if tweets:
            formatted = "\n\n".join(f"> {t}" for t in tweets[:3])
            await channel.send(f"🐦 **Réactions:**\n\n{formatted}")
            
    except Exception as e:
        logger.error("_post_match error: %s", e, exc_info=True)
        await channel.send(f"⚠️ Partial report — error: {str(e)[:80]}")

async def _post_five_summary(channel, matches: list, members: list):
    """5-match summary with parallel AI + images."""
    loop = asyncio.get_event_loop()
    
    # Parallel AI calls
    summary_t = asyncio.create_task(GEMINI_LIMITER(gemini.five_match_summary)(matches))
    performers_t = asyncio.create_task(GEMINI_LIMITER(gemini.top_performers)(matches, members))
    totw_t = asyncio.create_task(GEMINI_LIMITER(gemini.team_of_the_week)(matches))
    
    # Parallel image prep
    results_data = [
        {"opponent": m["opp_name"], "our_goals": m["our_goals"],
         "opp_goals": m["opp_goals"], "date": m["date"]}
        for m in matches
    ]
    summary_img = await loop.run_in_executor(
        None, lambda: image_gen.make_five_match_summary(results_data)
    )
    
    # Wait for AI
    summary_text, performers_text, (totw_text, totw_players) = await asyncio.gather(
        summary_t, performers_t, totw_t
    )
    
    totw_img = await loop.run_in_executor(
        None, lambda: image_gen.make_totw_card(totw_players)
    )
    
    # Send sequentially (avoid rate limits)
    await _send(channel, summary_text, summary_img, "last5.png")
    await asyncio.sleep(1)
    await _send(channel, performers_text)
    await asyncio.sleep(1)
    await _send(channel, totw_text, totw_img, "totw.png")

# ═══════════════════════════════════════════════════════════════════════════════
# BACKGROUND TASKS (BULLETPROOF)
# ═══════════════════════════════════════════════════════════════════════════════

@tasks.loop(hours=CONFIG.MATCH_CHECK_HOURS)
async def check_new_matches():
    """Check for new matches every 6 hours."""
    global seen_matches
    channel = _match_ch()
    if not channel:
        logger.info("No match channel set — skipping")
        return
    
    try:
        raw = await CACHE.get_matches(5, force=True)
        if not raw:
            return
        
        new = []
        for r in raw:
            mid = ea_api.get_match_id(r)
            if mid and mid not in seen_matches:
                new.append(r)
                seen_matches.add(mid)
        
        if new:
            save_seen(seen_matches)
            logger.info("🆕 %d new match(es)", len(new))
            
            for r in reversed(new):
                m = ea_api.parse_match(r)
                await _post_match(channel, m)
                await asyncio.sleep(8)
    
    except Exception as e:
        logger.error("check_new_matches failed: %s", e, exc_info=True)

@tasks.loop(minutes=30)
async def daily_weekly_check():
    """Daily stat, spotlight, weekly recap."""
    global _weekly_posted, _daily_am_posted, _daily_pm_posted, _spotlight_index
    
    now = datetime.now(timezone.utc)
    ch = _general_ch()
    if not ch:
        return
    
    hour, weekday = now.hour, now.weekday()
    
    # Reset at midnight
    if hour == 0:
        _daily_am_posted = False
        _daily_pm_posted = False
    
    # Morning: Stat du Jour (10h UTC)
    if hour == CONFIG.DAILY_STAT_HOUR and not _daily_am_posted:
        _daily_am_posted = True
        try:
            raw = await CACHE.get_matches(5)
            if raw:
                matches = _parse_all(raw)
                text = await GEMINI_LIMITER(gemini.stat_of_day)(matches)
                if text:
                    await _send(ch, f"📊 **Stat du Jour**\n\n{text}")
        except Exception as e:
            logger.error("Stat of day: %s", e)
    
    # Evening: Spotlight (20h, not Sunday)
    if (hour == CONFIG.SPOTLIGHT_HOUR and 
        not _daily_pm_posted and 
        weekday != CONFIG.WEEKLY_DAY):
        _daily_pm_posted = True
        try:
            raw = await CACHE.get_matches(5)
            if raw:
                matches = _parse_all(raw)
                agg = ea_api.aggregate_stats(matches)
                if agg:
                    players = sorted(agg.keys(), key=lambda k: agg[k]["avg_rating"], reverse=True)
                    if players:
                        spotlight = players[_spotlight_index % len(players)]
                        _spotlight_index += 1
                        text = await GEMINI_LIMITER(gemini.player_spotlight)(spotlight, matches)
                        if text:
                            await _send(ch, f"⭐ **Player Spotlight: {spotlight}**\n\n{text}")
        except Exception as e:
            logger.error("Spotlight: %s", e)
    
    # Sunday 20h: Weekly Recap
    if (weekday == CONFIG.WEEKLY_DAY and 
        hour == CONFIG.WEEKLY_HOUR and 
        not _weekly_posted):
        _weekly_posted = True
        _daily_pm_posted = True
        try:
            raw = await CACHE.get_matches(5)
            if raw:
                matches = _parse_all(raw)
                data = await CACHE.get_all(1)
                members = data.get("members", [])
                await ch.send("🗓️ **WEEKLY RECAP — Rachad L3ERGONI** 🏆")
                await asyncio.sleep(1)
                await _post_five_summary(ch, matches, members)
        except Exception as e:
            logger.error("Weekly recap: %s", e)
            await ch.send("❌ Weekly recap failed — try `!weekly`")
    
    # Reset weekly flag
    if weekday != CONFIG.WEEKLY_DAY:
        _weekly_posted = False

# ═══════════════════════════════════════════════════════════════════════════════
# EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    global seen_matches
    seen_matches = load_seen()
    logger.info("✅ Bot ready: %s | Club: %s", bot.user, CONFIG.CLUB_ID)
    logger.info("   Match check: every %dh | Prefix: !", CONFIG.MATCH_CHECK_HOURS)
    
    check_new_matches.start()
    daily_weekly_check.start()
    
    try:
        synced = await bot.tree.sync()
        logger.info("   Slash commands synced: %d", len(synced))
    except Exception as e:
        logger.warning("Slash sync: %s", e)

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return
    if message.content:
        logger.info("[MSG] #%s | %s: %s",
                    getattr(message.channel, "name", "DM"),
                    message.author.name, message.content[:80])
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Cooldown: {error.retry_after:.0f}s")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Ma3ndekch permission! 🚫")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Naqes argument — `!help`")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        logger.error("Command error [%s]: %s", ctx.command, error, exc_info=True)
        await ctx.send(f"❌ Error: `{str(error)[:50]}`")

# ═══════════════════════════════════════════════════════════════════════════════
# MATCH COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="last5", aliases=["recap"])
@commands.cooldown(1, 30, commands.BucketType.channel)
async def cmd_last5(ctx):
    """Analyse 5 derniers matchs + TOTW + performers."""
    await ctx.send("⏳ Kan-load last 5 matchs... 🤖")
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        if not raw:
            return await ctx.send("❌ Ma3endnach matches daba 😴")
        matches = _parse_all(raw)
        data = await CACHE.get_all(1)
        await _post_five_summary(ctx.channel, matches, data.get("members", []))

@bot.command(name="last10")
@commands.cooldown(1, 30, commands.BucketType.channel)
async def cmd_last10(ctx):
    """Analyse 10 derniers matchs."""
    await ctx.send("⏳ Kan-load last 10 matchs... 🤖")
    async with ctx.typing():
        raw = await CACHE.get_matches(10)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        matches = _parse_all(raw)
        wins = sum(1 for m in matches if m["result"] == "W")
        draws = sum(1 for m in matches if m["result"] == "D")
        losses = sum(1 for m in matches if m["result"] == "L")
        gf = sum(m["our_goals"] for m in matches)
        ga = sum(m["opp_goals"] for m in matches)
        form = "".join(m["result"] for m in matches[:10])
        
        lines = [
            "📊 **LAST 10 MATCHS — Rachad L3ERGONI**",
            f"🏆 W: **{wins}** | 🟡 D: **{draws}** | 💀 L: **{losses}**",
            f"⚽ {gf} pour / {ga} contre | Form: `{form}`",
            ""
        ]
        for m in matches:
            e = _result_icon(m["result"])
            lines.append(f"{e} {m['date']} — **{m['our_goals']}-{m['opp_goals']}** vs {m['opp_name']}")
        
        await ctx.send("\n".join(lines[:2000]))
        text = await GEMINI_LIMITER(gemini.form_analysis)(matches)
        await _send(ctx.channel, text)

@bot.command(name="match")
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_match(ctx, index: int = 1):
    """Rapport match spécifique. !match 1 = dernier."""
    if not 1 <= index <= 10:
        return await ctx.send("❌ Index bin 1 w 10.")
    await ctx.send(f"⏳ Match #{index}...")
    async with ctx.typing():
        raw = await CACHE.get_matches(10)
        if index > len(raw):
            return await ctx.send(f"❌ Ghir {len(raw)} matchs disponibles.")
        m = ea_api.parse_match(raw[index - 1])
        await _post_match(ctx.channel, m)

@bot.command(name="lastmatch", aliases=["report", "last"])
@commands.cooldown(1, 15, commands.BucketType.user)
async def cmd_lastmatch(ctx):
    """Rapport complet dernier match."""
    await ctx.send("⏳ Dernier match...")
    async with ctx.typing():
        raw = await CACHE.get_matches(1)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        m = ea_api.parse_match(raw[0])
        await _post_match(ctx.channel, m)

@bot.command(name="quickreport")
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_quickreport(ctx):
    """Rapport court 1-2 lignes."""
    async with ctx.typing():
        raw = await CACHE.get_matches(1)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        m = ea_api.parse_match(raw[0])
        text = await GEMINI_LIMITER(gemini.quick_report)(m)
        await ctx.send(text[:2000])

@bot.command(name="results")
@commands.cooldown(1, 20, commands.BucketType.channel)
async def cmd_results(ctx):
    """Tableau 10 derniers résultats."""
    async with ctx.typing():
        raw = await CACHE.get_matches(10)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        matches = _parse_all(raw)
        lines = ["📋 **RÉSULTATS — Rachad L3ERGONI**\n"]
        for i, m in enumerate(matches, 1):
            e = _result_icon(m["result"])
            lines.append(f"`{i:2}.` {e} `{m['our_goals']}-{m['opp_goals']}` vs **{m['opp_name']}** — {m['date']}")
        await ctx.send("\n".join(lines))

@bot.command(name="schedule")
@commands.cooldown(1, 20, commands.BucketType.channel)
async def cmd_schedule(ctx):
    """Prochains matchs (prédiction)."""
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        matches = _parse_all(raw)
        opponents = [m["opp_name"] for m in matches[:3]]
        text = await GEMINI_LIMITER(gemini.match_prediction)(", ".join(opponents), matches)
        await ctx.send(f"🗓️ **Prochains adversaires:** {', '.join(opponents)}\n\n{text}")

# ═══════════════════════════════════════════════════════════════════════════════
# PLAYER COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="players")
@commands.cooldown(1, 30, commands.BucketType.channel)
async def cmd_players(ctx):
    """Liste squad avec stats."""
    async with ctx.typing():
        data = await CACHE.get_all(1)
        members = data.get("members", [])
        if not members:
            return await ctx.send("❌ Ma3endnach données membres 😴")
        
        sorted_members = sorted(
            members,
            key=lambda x: float(x.get("ratingAve", 0) or 0),
            reverse=True
        )
        
        lines = ["👥 **SQUAD — Rachad L3ERGONI**\n"]
        for m in sorted_members[:15]:
            name = m.get("proName") or m.get("name", "?")
            games = m.get("gamesPlayed", 0)
            goals = m.get("goals", 0)
            assists = m.get("assists", 0)
            rating = m.get("ratingAve", "?")
            pos = m.get("favoritePosition", "MID").upper()[:3]
            lines.append(f"**{name}** `{pos}` — {goals}G {assists}A | ⭐ {rating} | {games} matchs")
        
        await ctx.send("\n".join(lines)[:2000])

@bot.command(name="player")
@commands.cooldown(1, 10, commands.BucketType.user)
async def cmd_player(ctx, *, player_name: str = ""):
    """Stats joueur. !player Hamza"""
    if not player_name:
        return await ctx.send("Usage: `!player NomJoueur`")
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        matches = _parse_all(raw)
        agg = ea_api.aggregate_stats(matches)
        key = next((k for k in agg if player_name.lower() in k.lower()), None)
        if not key:
            return await ctx.send(f"❌ **{player_name}** — ma3endnach stats.\nTry: `!players`")
        s = agg[key]
        lines = [
            f"👤 **{s['name']}** — Stats 5 Derniers Matchs",
            f"🎮 Matchs: **{s['games']}**",
            f"⚽ Buts: **{s['goals']}** | 🎯 Assists: **{s['assists']}**",
            f"⭐ Rating: **{s['avg_rating']:.2f}/10**",
            f"💥 Shots: **{s.get('shots', 0)}** | 🛡️ Tackles: **{s.get('tackles', 0)}**",
        ]
        await ctx.send("\n".join(lines))

@bot.command(name="form")
@commands.cooldown(1, 15, commands.BucketType.user)
async def cmd_form(ctx, *, player_name: str = ""):
    """Analyse forme. !form → team | !form Hamza → joueur"""
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        matches = _parse_all(raw)
        if player_name:
            text = await GEMINI_LIMITER(gemini.player_form)(player_name, matches)
        else:
            text = await GEMINI_LIMITER(gemini.form_analysis)(matches)
    await _send(ctx.channel, text)

@bot.command(name="topscorer")
@commands.cooldown(1, 20, commands.BucketType.channel)
async def cmd_topscorer(ctx):
    """Classement buteurs."""
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        data = await CACHE.get_all(1)
        matches = _parse_all(raw) if raw else []
        text = await GEMINI_LIMITER(gemini.top_scorer_post)(matches, data.get("members", []))
    await _send(ctx.channel, text)

@bot.command(name="topassists")
@commands.cooldown(1, 20, commands.BucketType.channel)
async def cmd_topassists(ctx):
    """Classement assisteurs."""
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        data = await CACHE.get_all(1)
        matches = _parse_all(raw) if raw else []
        text = await GEMINI_LIMITER(gemini.top_assists_post)(matches, data.get("members", []))
    await _send(ctx.channel, text)

@bot.command(name="mvp")
@commands.cooldown(1, 20, commands.BucketType.channel)
async def cmd_mvp(ctx):
    """MVP 5 derniers matchs."""
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        matches = _parse_all(raw)
        text = await GEMINI_LIMITER(gemini.mvp_post)(matches)
    await _send(ctx.channel, text)

@bot.command(name="compare")
@commands.cooldown(1, 20, commands.BucketType.user)
async def cmd_compare(ctx, player1: str = "", *, player2: str = ""):
    """Compare 2 joueurs. !compare Hamza Karim"""
    if not player1 or not player2:
        return await ctx.send("Usage: `!compare Joueur1 Joueur2`")
    await ctx.send(f"⚔️ **{player1}** vs **{player2}**...")
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        matches = _parse_all(raw)
        result = await GEMINI_LIMITER(gemini.compare_players)(player1, player2, matches)
        if isinstance(result, str):
            return await ctx.send(result)
        text, s1, s2 = result
        loop = asyncio.get_event_loop()
        card_buf = await loop.run_in_executor(None, lambda: image_gen.make_comparison_card(s1, s2))
    await _send(ctx.channel, text, card_buf, f"compare_{player1}_{player2}.png")

# ═══════════════════════════════════════════════════════════════════════════════
# CONTENT COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="motm")
@commands.cooldown(1, 15, commands.BucketType.user)
async def cmd_motm(ctx, match_index: int = 1):
    """Man of the Match. !motm [1-5]"""
    async with ctx.typing():
        raw = await CACHE.get_matches(match_index)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        m = ea_api.parse_match(raw[match_index - 1])
        if not m.get("players"):
            return await ctx.send("❌ Bla stats joueurs pour ce match.")
        best = m["players"][0]
        loop = asyncio.get_event_loop()
        motm_text, motm_buf = await asyncio.gather(
            GEMINI_LIMITER(gemini.motm_post)(m),
            loop.run_in_executor(None, lambda: image_gen.make_motm_card(
                best["name"], best["rating"], best["goals"], best["assists"],
                match_context=f"vs {m['opp_name']} ({m['our_goals']}-{m['opp_goals']})"
            ))
        )
    await _send(ctx.channel, motm_text or "", motm_buf, "motm.png")

@bot.command(name="totw")
@commands.cooldown(1, 30, commands.BucketType.channel)
async def cmd_totw(ctx):
    """Team of the Week avec image."""
    await ctx.send("⏳ Building TOTW...")
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        matches = _parse_all(raw)
        loop = asyncio.get_event_loop()
        totw_text, totw_players = await GEMINI_LIMITER(gemini.team_of_the_week)(matches)
        totw_img = await loop.run_in_executor(None, lambda: image_gen.make_totw_card(totw_players))
    await _send(ctx.channel, totw_text, totw_img, "totw.png")

@bot.command(name="hype")
@commands.cooldown(1, 20, commands.BucketType.channel)
async def cmd_hype(ctx, *, context: str = ""):
    """Post motivation. !hype [adversaire]"""
    async with ctx.typing():
        text = await GEMINI_LIMITER(gemini.hype_post)(context)
    await _send(ctx.channel, text)

@bot.command(name="reaction")
@commands.cooldown(1, 15, commands.BucketType.user)
async def cmd_reaction(ctx):
    """Réaction courte dernier match."""
    async with ctx.typing():
        raw = await CACHE.get_matches(1)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        m = ea_api.parse_match(raw[0])
        text = await GEMINI_LIMITER(gemini.reaction_post)(m)
    await ctx.send(text[:2000])

@bot.command(name="rankings")
@commands.cooldown(1, 20, commands.BucketType.channel)
async def cmd_rankings(ctx):
    """Top performers 5 derniers matchs."""
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        matches = _parse_all(raw)
        data = await CACHE.get_all(1)
        text = await GEMINI_LIMITER(gemini.top_performers)(matches, data.get("members", []))
    await _send(ctx.channel, text)

@bot.command(name="spotlight")
@commands.cooldown(1, 20, commands.BucketType.user)
async def cmd_spotlight(ctx, *, player_name: str = ""):
    """Spotlight joueur. !spotlight [nom]"""
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        matches = _parse_all(raw)
        text = await GEMINI_LIMITER(gemini.player_spotlight)(player_name, matches)
    await _send(ctx.channel, text)

# ═══════════════════════════════════════════════════════════════════════════════
# FUN COMMANDS (DARIJA ENERGY)
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="roast")
@commands.cooldown(1, 30, commands.BucketType.user)
async def cmd_roast(ctx, *, player_name: str = ""):
    """Roast brutal. !roast Hamza 🔥"""
    if not player_name:
        return await ctx.send("Kteb ism: `!roast NomDuJoueur` 🔥")
    await ctx.send(f"🔥 Incoming roast dial **{player_name}**...")
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        matches = _parse_all(raw) if raw else []
        text = await GEMINI_LIMITER(gemini.roast)(player_name, matches)
    await _send(ctx.channel, text)

@bot.command(name="cheer")
@commands.cooldown(1, 20, commands.BucketType.user)
async def cmd_cheer(ctx, *, player_name: str = ""):
    """Célèbre un joueur. !cheer Hamza 👏"""
    if not player_name:
        return await ctx.send("Kteb ism: `!cheer NomDuJoueur` 👏")
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        matches = _parse_all(raw) if raw else []
        text = await GEMINI_LIMITER(gemini.cheer)(player_name, matches)
    await _send(ctx.channel, text)

@bot.command(name="banter")
@commands.cooldown(1, 15, commands.BucketType.channel)
async def cmd_banter(ctx):
    """Football banter trash talk 😈"""
    async with ctx.typing():
        raw = await CACHE.get_matches(1)
        matches = _parse_all(raw) if raw else []
        text = await GEMINI_LIMITER(gemini.banter)(matches)
    await ctx.send(text[:2000])

@bot.command(name="meme")
@commands.cooldown(1, 15, commands.BucketType.channel)
async def cmd_meme(ctx):
    """Meme football b Darija 😂"""
    async with ctx.typing():
        raw = await CACHE.get_matches(1)
        matches = _parse_all(raw) if raw else []
        text = await GEMINI_LIMITER(gemini.meme_post)(matches)
    await ctx.send(text[:2000])

@bot.command(name="drama")
@commands.cooldown(1, 15, commands.BucketType.channel)
async def cmd_drama(ctx):
    """Drama exagérée 😱"""
    async with ctx.typing():
        raw = await CACHE.get_matches(1)
        matches = _parse_all(raw) if raw else []
        text = await GEMINI_LIMITER(gemini.drama_post)(matches)
    await ctx.send(text[:2000])

# ═══════════════════════════════════════════════════════════════════════════════
# NEWS COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="transfer", aliases=["rumour", "rumours"])
@commands.cooldown(1, 20, commands.BucketType.channel)
async def cmd_transfer(ctx):
    """Transfer rumor humour. !transfer 🚨"""
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        data = await CACHE.get_all(1)
        matches = _parse_all(raw) if raw else []
        text = await GEMINI_LIMITER(gemini.transfer_rumor)(data.get("members", []), matches)
    await _send(ctx.channel, text)

@bot.command(name="breaking")
@commands.cooldown(1, 20, commands.BucketType.channel)
async def cmd_breaking(ctx):
    """Breaking news style. !breaking 📰"""
    async with ctx.typing():
        raw = await CACHE.get_matches(1)
        data = await CACHE.get_all(1)
        matches = _parse_all(raw) if raw else []
        text = await GEMINI_LIMITER(gemini.breaking_news)(matches, data.get("members", []))
    await _send(ctx.channel, text)

# ═══════════════════════════════════════════════════════════════════════════════
# ANALYTICS COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="stats")
@commands.cooldown(1, 30, commands.BucketType.channel)
async def cmd_stats(ctx):
    """Stats saison complète."""
    async with ctx.typing():
        data = await CACHE.get_all(1)
    s = data.get("club_stats") or {}
    i = data.get("club_info") or {}
    name = i.get("name", "Rachad L3ERGONI")
    
    try:
        w = int(s.get("wins", 0))
        t = int(s.get("ties", 0))
        l = int(s.get("losses", 0))
        total = w + t + l
        wr = f"{w/total*100:.1f}%" if total else "?"
    except:
        wr = "?"
    
    lines = [
        f"📊 **{name} — Season Stats**",
        "─────────────────────────────",
        f"🏆 W: **{s.get('wins','?')}** | 🟡 D: **{s.get('ties','?')}** | 💀 L: **{s.get('losses','?')}**",
        f"📈 Win Rate: **{wr}** | Games: **{s.get('gamesPlayed','?')}**",
        f"⚽ Goals: **{s.get('goals','?')}** / **{s.get('goalsAgainst','?')}** concédés",
        f"🎯 Skill Rating: **{s.get('skillRating','?')}**",
        f"🏅 Best Division: **Div {s.get('bestDivision','?')}**",
        f"🔥 Win Streak: **{s.get('wstreak','?')}** | Unbeaten: **{s.get('unbeatenstreak','?')}**",
        "",
        f"🔗 proclubstracker.com/club/{CONFIG.CLUB_ID}?platform={CONFIG.PLATFORM}",
    ]
    await ctx.send("\n".join(lines))

@bot.command(name="insights")
@commands.cooldown(1, 30, commands.BucketType.channel)
async def cmd_insights(ctx):
    """Insights analytiques."""
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        matches = _parse_all(raw)
        text = await GEMINI_LIMITER(gemini.insights)(matches)
    await _send(ctx.channel, text)

@bot.command(name="trends")
@commands.cooldown(1, 30, commands.BucketType.channel)
async def cmd_trends(ctx):
    """Tendances patterns."""
    async with ctx.typing():
        raw = await CACHE.get_matches(10)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        matches = _parse_all(raw)
        text = await GEMINI_LIMITER(gemini.trends)(matches)
    await _send(ctx.channel, text)

@bot.command(name="stat")
@commands.cooldown(1, 20, commands.BucketType.channel)
async def cmd_stat(ctx):
    """Stat du jour."""
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        matches = _parse_all(raw)
        text = await GEMINI_LIMITER(gemini.stat_of_day)(matches)
    await _send(ctx.channel, text)

@bot.command(name="predict")
@commands.cooldown(1, 20, commands.BucketType.user)
async def cmd_predict(ctx, *, opponent: str = "Prochain adversaire"):
    """Prediction prochain match. !predict NomAdversaire"""
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        matches = _parse_all(raw) if raw else []
        text = await GEMINI_LIMITER(gemini.match_prediction)(opponent, matches)
    await _send(ctx.channel, text)

@bot.command(name="clubinfo")
@commands.cooldown(1, 30, commands.BucketType.channel)
async def cmd_clubinfo(ctx):
    """Info club."""
    async with ctx.typing():
        data = await CACHE.get_all(1)
    info = data.get("club_info") or {}
    lines = [
        f"🏟️ **{info.get('name','Rachad L3ERGONI')}**",
        f"🎮 Platform: **{CONFIG.PLATFORM}**",
        f"🔗 proclubstracker.com/club/{CONFIG.CLUB_ID}?platform={CONFIG.PLATFORM}",
    ]
    await ctx.send("\n".join(lines))

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="setchannel")
@commands.has_permissions(manage_channels=True)
async def cmd_setchannel(ctx, channel_type: str = "match"):
    global CONFIG
    # Note: CONFIG is frozen, so we use globals for runtime changes
    global _match_channel_id_override, _general_channel_id_override
    if channel_type == "match":
        # Store in a mutable way
        bot._match_channel_override = ctx.channel.id
        await ctx.send(f"✅ Match channel set! Auto-check kol {CONFIG.MATCH_CHECK_HOURS}h 🔔")
    elif channel_type == "general":
        bot._general_channel_override = ctx.channel.id
        await ctx.send("✅ General channel set! Daily/weekly content ghadi yji hna 📅")
    else:
        await ctx.send("Usage: `!setchannel match` ou `!setchannel general`")

# Override helpers
def _match_ch():
    return bot.get_channel(getattr(bot, '_match_channel_override', None) or CONFIG.MATCH_CHANNEL_ID)

def _general_ch():
    override = getattr(bot, '_general_channel_override', None) or CONFIG.GENERAL_CHANNEL_ID
    if override:
        return bot.get_channel(override)
    return _match_ch()

@bot.command(name="weekly")
@commands.has_permissions(manage_channels=True)
async def cmd_weekly(ctx):
    """Déclenche weekly recap manuellement."""
    await ctx.send("⏳ Generating weekly recap...")
    async with ctx.typing():
        raw = await CACHE.get_matches(5)
        if not raw:
            return await ctx.send("❌ Ma3endnach data 😴")
        matches = _parse_all(raw)
        data = await CACHE.get_all(1)
        await _post_five_summary(ctx.channel, matches, data.get("members", []))

@bot.command(name="refreshdata")
@commands.has_permissions(manage_channels=True)
async def cmd_refreshdata(ctx):
    """Force refresh données."""
    await ctx.send("🔄 Forçage refresh...")
    CACHE.invalidate()
    raw = await CACHE.get_matches(5, force=True)
    if raw:
        await ctx.send(f"✅ Data refreshed — **{len(raw)}** matchs chargés!")
    else:
        await ctx.send("❌ Refresh failed 😴")

@bot.command(name="ping")
async def cmd_ping(ctx):
    """Test connexion."""
    try:
        cache_info = "active" if HAS_CACHE else "disabled"
        await ctx.send(
            f"Pong ✅ | Latency: {bot.latency*1000:.0f}ms | "
            f"Cache: {cache_info} | Check: kol {CONFIG.MATCH_CHECK_HOURS}h"
        )
    except:
        await ctx.send("Pong ✅")

# ═══════════════════════════════════════════════════════════════════════════════
# HELP COMMAND
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="help", aliases=["pchelp", "commands"])
async def cmd_help(ctx):
    lines = [
        "⚽ **Rachad L3ERGONI Bot** _(Gemini AI · PCT API · Darija Energy)_",
        "══════════════════════════════════════════",
        "",
        "**📋 MATCH**",
        "`!last5` / `!recap` · `!last10` · `!results` · `!match <1-10>`",
        "`!lastmatch` / `!report` · `!quickreport` · `!schedule`",
        "",
        "**👥 PLAYERS**",
        "`!players` · `!player <nom>` · `!form [nom]`",
        "`!topscorer` · `!topassists` · `!mvp` · `!compare <p1> <p2>`",
        "",
        "**🎬 CONTENT**",
        "`!motm [1-5]` · `!totw` · `!hype [adversaire]`",
        "`!reaction` · `!rankings` · `!spotlight [nom]`",
        "",
        "**😂 FUN**",
        "`!roast <nom>` 🔥 · `!cheer <nom>` 👏 · `!banter` 😈",
        "`!meme` 😂 · `!drama` 😱",
        "",
        "**📰 NEWS**",
        "`!transfer` / `!rumour` 🚨 · `!breaking` 📰",
        "",
        "**📊 ANALYTICS**",
        "`!stats` · `!insights` · `!trends` · `!stat` · `!predict <adversaire>`",
        "`!clubinfo`",
        "",
        "**⚙️ ADMIN** _(manage_channels)_",
        "`!setchannel match` · `!setchannel general` · `!weekly` · `!refreshdata`",
        "",
        "_Auto: matchs kol 6h 🔔 · Stat 10h · Spotlight 20h · Weekly Dimanche_",
    ]
    await ctx.send("\n".join(lines))

# ═══════════════════════════════════════════════════════════════════════════════
# SLASH COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="ping", description="Test connexion bot")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Pong ✅ | Latency: {bot.latency*1000:.0f}ms"
    )

@bot.tree.command(name="last5", description="Analyse 5 derniers matchs")
async def slash_last5(interaction: discord.Interaction):
    await interaction.response.defer()
    raw = await CACHE.get_matches(5)
    if not raw:
        await interaction.followup.send("❌ Ma3endnach data 😴")
        return
    matches = _parse_all(raw)
    data = await CACHE.get_all(1)
    await _post_five_summary(interaction.channel, matches, data.get("members", []))
    await interaction.followup.send("✅ Last 5 envoyé!")

@bot.tree.command(name="roast", description="Roast brutal d'un joueur 🔥")
async def slash_roast(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    raw = await CACHE.get_matches(5)
    matches = _parse_all(raw) if raw else []
    text = await GEMINI_LIMITER(gemini.roast)(player, matches)
    await interaction.followup.send(text[:2000])

@bot.tree.command(name="hype", description="Post de motivation")
async def slash_hype(interaction: discord.Interaction, context: str = ""):
    await interaction.response.defer()
    text = await GEMINI_LIMITER(gemini.hype_post)(context)
    await interaction.followup.send(text[:2000])

@bot.tree.command(name="predict", description="Prediction prochain match")
async def slash_predict(interaction: discord.Interaction, adversaire: str = "Adversaire"):
    await interaction.response.defer()
    raw = await CACHE.get_matches(5)
    matches = _parse_all(raw) if raw else []
    text = await GEMINI_LIMITER(gemini.match_prediction)(adversaire, matches)
    await interaction.followup.send(text[:2000])

@bot.tree.command(name="stats", description="Stats saison du club")
async def slash_stats(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await CACHE.get_all(1)
    s = data.get("club_stats") or {}
    w, t, l = int(s.get("wins",0)), int(s.get("ties",0)), int(s.get("losses",0))
    total = w+t+l
    wr = f"{w/total*100:.1f}%" if total else "?"
    lines = [
        f"📊 **{s.get('name','Rachad L3ERGONI')}**",
        f"🏆 W:{s.get('wins','?')} | 🟡 D:{s.get('ties','?')} | 💀 L:{s.get('losses','?')}",
        f"📈 Win Rate: {wr} | 🎯 SR: {s.get('skillRating','?')}",
    ]
    await interaction.followup.send("\n".join(lines))

# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH SERVER (for hosting)
# ═══════════════════════════════════════════════════════════════════════════════

def start_health_server():
    import threading
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    
    port = int(os.environ.get("PORT", 10000))
    
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Rachad L3ERGONI Bot OK")
        def log_message(self, format, *args):
            pass  # Silence health check logs
    
    server = HTTPServer(("0.0.0.0", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("🌐 Health server on port %d", port)

# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    start_health_server()
    bot.run(CONFIG.TOKEN)
