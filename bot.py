"""
Rachad L3ERGONI Pro Clubs Bot — Complete Working Version
Integrates with your existing: scraper.py, gemini.py, image_gen.py, state.py
"""
import os
import io
import asyncio
import logging
import time
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

# Import your existing modules
import scraper as _scraper
import gemini
import image_gen
import achievements
from state import load_seen, save_seen

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("RachadBot")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN not set!")

# ─── CONFIG ───
MATCH_CHANNEL_ID = int(os.environ.get("MATCH_CHANNEL_ID", 0)) or None
POLL_MINUTES = 5      # Check every 5 min when session active
TIMEOUT_MINUTES = 45  # Auto-stop after 45 min idle

# ─── BOT ───
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

seen_matches = set()
_session_active = False
_last_match_id = None
_last_activity_ts = 0.0

# ─── HELPERS ───
def _match_channel():
    return bot.get_channel(MATCH_CHANNEL_ID) if MATCH_CHANNEL_ID else None

async def _send(ch, text="", image=None, filename="image.png"):
    """Send text + optional image. Fix newline formatting."""
    text = (text or "").strip()
    # Fix literal \n in text
    text = text.replace("\\n", "\n")
    if not text and not image:
        return
    if image:
        image.seek(0)
        file = discord.File(image, filename=filename)
        await ch.send(text[:1900] or None, file=file)
    else:
        while text:
            chunk, text = text[:2000], text[2000:]
            await ch.send(chunk)

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION POLLING (Like AllCalculatedRoast !roast command)
# ═══════════════════════════════════════════════════════════════════════════════

@tasks.loop(minutes=POLL_MINUTES)
async def poll_matches():
    """Poll every 5 min during active session. Auto-stop after 45 min idle."""
    global _session_active, _last_activity_ts, _last_match_id

    if not _session_active:
        return

    # Check timeout
    idle_min = (time.monotonic() - _last_activity_ts) / 60
    if idle_min >= TIMEOUT_MINUTES:
        await _stop_session("timeout")
        return

    # Fetch from scraper (your working source)
    try:
        data = await _scraper.fetch_all(max_matches=1, force=False)
        raw_matches = data.get("matches", [])
        if not raw_matches:
            return

        # Get match ID
        raw = raw_matches[0]
        mid = str(raw.get("match_id", raw.get("id", raw.get("timestamp", ""))))

        if mid == _last_match_id or not mid:
            return  # No new match

        # NEW MATCH!
        _last_match_id = mid
        _last_activity_ts = time.monotonic()
        logger.info(f"🆕 New match: {mid}")

        # Parse using your existing ea_api or inline
        m = _parse_match(raw)
        if m:
            await _post_match(_match_channel(), m)

    except Exception as e:
        logger.error(f"Poll error: {e}")

@poll_matches.before_loop
async def before_poll():
    await bot.wait_until_ready()

async def _start_session(channel):
    """Start session monitoring."""
    global _session_active, _last_activity_ts, _last_match_id

    if _session_active:
        await channel.send("⏳ Session déjà active!")
        return

    # Get baseline
    try:
        data = await _scraper.fetch_all(max_matches=1, force=False)
        raw_matches = data.get("matches", [])
        if raw_matches:
            raw = raw_matches[0]
            _last_match_id = str(raw.get("match_id", raw.get("id", raw.get("timestamp", ""))))
    except:
        _last_match_id = None

    _session_active = True
    _last_activity_ts = time.monotonic()

    if not poll_matches.is_running():
        poll_matches.start()

    await channel.send(
        "🎮 **Session démarrée!**\n"
        f"• Check every {POLL_MINUTES} min\n"
        f"• Auto-stop après {TIMEOUT_MINUTES} min d'inactivité\n"
        f"• Type `!stop` pour arrêter manuellement"
    )

async def _stop_session(reason="manual"):
    """Stop session monitoring."""
    global _session_active
    _session_active = False
    if poll_matches.is_running():
        poll_matches.stop()

    ch = _match_channel()
    if not ch:
        return

    if reason == "timeout":
        await ch.send(
            "⏹️ **Session terminée**\n"
            f"Pas de nouveau match depuis {TIMEOUT_MINUTES} min.\n"
            "Type `!roast` quand tu rejoues!"
        )
    else:
        await ch.send("⏹️ **Session arrêtée**")

# ─── Match Parser ───

def _parse_match(raw: Dict) -> Dict:
    """Parse match from scraper format."""
    try:
        return {
            "match_id": str(raw.get("match_id", raw.get("id", ""))),
            "our_name": raw.get("our_name", "Rachad L3ERGONI"),
            "opp_name": raw.get("opp_name", "Unknown"),
            "our_goals": int(raw.get("our_goals", 0)),
            "opp_goals": int(raw.get("opp_goals", 0)),
            "result": raw.get("result", "?"),
            "date": raw.get("date", ""),
            "players": raw.get("players", []),
        }
    except Exception as e:
        logger.error(f"Parse error: {e}")
        return {}

def _aggregate_stats(matches: list) -> dict:
    """Aggregate player stats."""
    agg = {}
    for m in matches:
        for p in m.get("players", []):
            name = p.get("name", "Unknown")
            if name not in agg:
                agg[name] = {
                    "name": name,
                    "games": 0, "goals": 0, "assists": 0,
                    "shots": 0, "tackles": 0,
                    "ratings": [], "avg_rating": 0.0,
                }
            agg[name]["games"] += 1
            agg[name]["goals"] += p.get("goals", 0)
            agg[name]["assists"] += p.get("assists", 0)
            agg[name]["shots"] += p.get("shots", 0)
            agg[name]["tackles"] += p.get("tackles", 0)
            agg[name]["ratings"].append(p.get("rating", 0))

    for name in agg:
        ratings = agg[name]["ratings"]
        agg[name]["avg_rating"] = sum(ratings) / len(ratings) if ratings else 0

    return agg

async def _post_match(ch, m):
    """Post match with achievements and MOTM photo."""
    try:
        # 1. Match Header
        emoji = "🟢" if m["result"] == "W" else ("🟡" if m["result"] == "D" else "🔴")
        header = f"{emoji} **{m['our_goals']}-{m['opp_goals']}** vs **{m['opp_name']}**"
        await ch.send(header)

        # 2. Player Badges (Achievements/Curses)
        if m.get("players"):
            badge_lines = []
            for p in m["players"]:
                badges = achievements.evaluate_player(p)
                badge_str = achievements.format_badges(badges)
                if badge_str:
                    badge_lines.append(f"**{p['name']}** {badge_str}")

            if badge_lines:
                await ch.send("🏅 **Badges:**\n" + "\n".join(badge_lines[:5]))

        # 3. Short AI Report (max 3 lines)
        report = await gemini.match_report(m)
        report = _clean_lines(report, 3)
        await ch.send(report)

        # 4. MOTM with Photo
        if m.get("players"):
            best = m["players"][0]
            motm_text = f"🌟 **MOTM: {best['name']}** ⭐ {best['rating']:.1f}/10"

            loop = asyncio.get_event_loop()
            motm_img = await loop.run_in_executor(
                None,
                image_gen.make_motm_card,
                best["name"], best["rating"], best["goals"], best["assists"],
                f"vs {m['opp_name']}"
            )
            await _send(ch, motm_text, motm_img, "motm.png")

    except Exception as e:
        logger.error(f"Post error: {e}")

def _clean_lines(text, max_lines=3):
    """Keep only first N lines."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    return '\n'.join(lines[:max_lines])

# ═══════════════════════════════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="roast")
async def cmd_roast_session(ctx):
    """Start session monitoring (like AllCalculatedRoast)."""
    await _start_session(ctx.channel)

@bot.command(name="stop")
async def cmd_stop(ctx):
    """Stop session monitoring."""
    await _stop_session("manual")

@bot.command(name="lastmatch")
async def cmd_lastmatch(ctx):
    """Last match report + MOTM photo."""
    async with ctx.typing():
        data = await _scraper.fetch_all(max_matches=1, force=False)
        raw_matches = data.get("matches", [])
        if not raw_matches:
            await ctx.send("❌ Ma3endnach match 😴")
            return
        m = _parse_match(raw_matches[0])
        if not m:
            await ctx.send("❌ Error parsing match 😴")
            return
        await _post_match(ctx.channel, m)

@bot.command(name="match")
async def cmd_match(ctx, num: int = 1):
    """Specific match (1=last, 2=before, etc.)."""
    if num < 1 or num > 10:
        await ctx.send("❌ Ghir bin 1 w 10 😅")
        return
    async with ctx.typing():
        data = await _scraper.fetch_all(max_matches=10, force=False)
        raw_matches = data.get("matches", [])
        if num > len(raw_matches):
            await ctx.send(f"❌ Ghir {len(raw_matches)} matchs disponibles")
            return
        m = _parse_match(raw_matches[num - 1])
        if not m:
            await ctx.send("❌ Error parsing match 😴")
            return
        await _post_match(ctx.channel, m)

@bot.command(name="results")
async def cmd_results(ctx):
    """Quick results table (last 10)."""
    async with ctx.typing():
        data = await _scraper.fetch_all(max_matches=10, force=False)
        raw_matches = data.get("matches", [])
        if not raw_matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        lines = ["📋 **RESULTATS — Rachad L3ERGONI**", ""]
        for i, r in enumerate(raw_matches, 1):
            m = _parse_match(r)
            if not m:
                continue
            icon = "🟢" if m["result"] == "W" else ("🟡" if m["result"] == "D" else "🔴")
            lines.append(f"`{i}.` {icon} `{m['our_goals']}-{m['opp_goals']}` vs **{m['opp_name']}** — {m['date']}")
        await ctx.send("\n".join(lines))

@bot.command(name="player")
async def cmd_player(ctx, *, name: str = ""):
    """Player stats from last 5 matches. Usage: !player Hamza"""
    if not name:
        await ctx.send("❌ Kteb ism: `!player Hamza`")
        return
    async with ctx.typing():
        data = await _scraper.fetch_all(max_matches=5, force=False)
        raw_matches = data.get("matches", [])
        matches = [_parse_match(r) for r in raw_matches if _parse_match(r)]
        agg = _aggregate_stats(matches)
        key = next((k for k in agg if name.lower() in k.lower()), None)
        if not key:
            await ctx.send(f"❌ **{name}** — ma3endnach stats f les derniers matchs 😴")
            return
        s = agg[key]
        lines = [
            f"👤 **{s['name']}** — Stats 5 Derniers Matchs",
            f"🎮 Matchs: **{s['games']}**",
            f"⚽ Buts: **{s['goals']}** | 🎯 Assists: **{s['assists']}**",
            f"⭐ Rating: **{s['avg_rating']:.2f}/10**",
            f"💥 Shots: **{s['shots']}** | 🛡️ Tackles: **{s['tackles']}**",
        ]
        await ctx.send("\n".join(lines))

@bot.command(name="players")
async def cmd_players(ctx):
    """Liste tous les joueurs avec stats saison."""
    async with ctx.typing():
        data = await _scraper.fetch_all(max_matches=1, force=False)
        members = data.get("members", [])
        if not members:
            await ctx.send("❌ Ma3endnach données membres 😴")
            return
        lines = ["👥 **SQUAD — Rachad L3ERGONI**", ""]
        for m in sorted(members, key=lambda x: float(x.get("ratingAve", 0) or 0), reverse=True)[:15]:
            name = m.get("proName") or m.get("name", "?")
            games = m.get("gamesPlayed", 0)
            goals = m.get("goals", 0)
            assists = m.get("assists", 0)
            rating = m.get("ratingAve", "?")
            pos = m.get("favoritePosition", "MID").upper()[:3]
            lines.append(f"**{name}** `{pos}` — {goals}G {assists}A | ⭐ {rating} | {games} matchs")
        await ctx.send("\n".join(lines)[:2000])

@bot.command(name="mvp")
async def cmd_mvp(ctx):
    """MVP des 5 derniers matchs avec photo."""
    async with ctx.typing():
        data = await _scraper.fetch_all(max_matches=5, force=False)
        raw_matches = data.get("matches", [])
        matches = [_parse_match(r) for r in raw_matches if _parse_match(r)]
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        agg = _aggregate_stats(matches)
        if not agg:
            await ctx.send("❌ Ma3endnach stats 😴")
            return
        mvp = max(agg.values(), key=lambda x: x["avg_rating"] + x["goals"] * 0.5 + x["assists"] * 0.3)

        loop = asyncio.get_event_loop()
        mvp_img = await loop.run_in_executor(
            None,
            image_gen.make_motm_card,
            mvp["name"], mvp["avg_rating"], mvp["goals"], mvp["assists"],
            "MVP — Last 5 Matches"
        )

        text = (
            f"👑 **MVP: {mvp['name']}**\n"
            f"🎮 {mvp['games']} matchs | ⚽ {mvp['goals']} buts | 🎯 {mvp['assists']} assists\n"
            f"⭐ Rating: **{mvp['avg_rating']:.2f}/10**"
        )
        await _send(ctx.channel, text, mvp_img, "mvp.png")

@bot.command(name="roastplayer")
async def cmd_roast_player(ctx, *, name: str = ""):
    """Roast brutal d'un joueur. Usage: !roastplayer Hamza 🔥"""
    if not name:
        await ctx.send("❌ Kteb ism: `!roastplayer NomDuJoueur` 🔥")
        return
    async with ctx.typing():
        data = await _scraper.fetch_all(max_matches=5, force=False)
        raw_matches = data.get("matches", [])
        matches = [_parse_match(r) for r in raw_matches if _parse_match(r)]
        text = await gemini.roast(name, matches)
        text = _clean_lines(text, 4)
        await ctx.send(text[:2000])

@bot.command(name="stats")
async def cmd_stats(ctx):
    """Stats saison complète du club."""
    async with ctx.typing():
        data = await _scraper.fetch_all(max_matches=1, force=False)
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
            f"🔗 proclubstracker.com/club/1427607?platform=common-gen5",
        ]
        await ctx.send("\n".join(lines))

@bot.command(name="help")
async def cmd_help(ctx):
    lines = [
        "⚽ **Rachad L3ERGONI Bot**",
        "═══════════════════════════════════",
        "",
        "**🎮 SESSION**",
        "`!roast` — Start session monitoring (checks every 5 min)",
        "`!stop` — Stop session monitoring",
        "",
        "**📋 MATCHES**",
        "`!lastmatch` — Last match + MOTM photo",
        "`!match 2` — Specific match (1=last, 2=before...)",
        "`!results` — Results table (last 10)",
        "",
        "**👥 PLAYERS**",
        "`!player Hamza` — Player stats (last 5)",
        "`!players` — Full squad list",
        "`!mvp` — MVP photo + stats",
        "`!roastplayer Hamza` — Roast player 🔥",
        "",
        "**📊 CLUB**",
        "`!stats` — Season stats",
        "",
        "_Simple. Clean. No spam._",
    ]
    await ctx.send("\n".join(lines))

@bot.command(name="ping")
async def cmd_ping(ctx):
    await ctx.send(f"Pong ✅ | Latency: {bot.latency*1000:.0f}ms")

# ─── EVENTS ───

@bot.event
async def on_ready():
    global seen_matches
    seen_matches = load_seen()
    logger.info(f"✅ Bot ready: {bot.user}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="your matches 👀"))

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Naqes argument — `!help` bach tchouf l'usage.")
        return
    logger.error(f"Command error: {error}")
    await ctx.send(f"❌ Error: `{str(error)[:50]}`")

# ─── HEALTH SERVER ───
def start_health_server():
    import threading
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    port = int(os.environ.get("PORT", 10000))
    class H(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Rachad L3ERGONI OK")
        def log_message(self, *a): pass
    s = HTTPServer(("0.0.0.0", port), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()

# ─── START ───
if __name__ == "__main__":
    start_health_server()
    bot.run(TOKEN)
