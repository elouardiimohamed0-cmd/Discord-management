"""Rachad L3ERGONI Bot — Compact v7
10-12 efficient commands. Auto daily/weekly/monthly leaderboards.
Only bad words, roasting, trash talk. No cheering, no praise.
"""
import os, io, asyncio, random, logging, time, re
from datetime import datetime, timedelta
from typing import Dict, List

import discord
from discord.ext import commands, tasks

import scraper as _scraper
import gemini
import achievements
import roast_engine
from state import load_seen, save_seen
from human_darija import HumanDarija
import anime_image_gen as image_gen

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("RachadBot")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN not set!")

MATCH_CHANNEL_ID = int(os.environ.get("MATCH_CHANNEL_ID", 0)) or None
POLL_MINUTES = 5
TIMEOUT_MINUTES = 45

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

humanizer = HumanDarija()
seen_matches = set()
_session_active = False
_last_match_id = None
_last_activity_ts = 0.0

# ─── HELPERS ───

def _match_channel():
    return bot.get_channel(MATCH_CHANNEL_ID) if MATCH_CHANNEL_ID else None

async def _send(ch, text="", image=None, filename="image.png", emotion="disappointment"):
    text = (text or "").strip()
    if not text and not image:
        return
    if text:
        text = humanizer.humanize(text, emotion=emotion, intensity=0.7)
    wc = len(text.split()) if text else 0
    if wc <= 5:
        tt = random.randint(1, 2)
    elif wc <= 12:
        tt = random.randint(2, 4)
    else:
        tt = random.randint(4, 7)
    if len(text) > 80 and random.random() < 0.2:
        tt += random.randint(1, 2)
    async with ch.typing():
        await asyncio.sleep(tt)
    if image:
        image.seek(0)
        file = discord.File(image, filename=filename)
        await ch.send(text[:1900] or None, file=file)
    else:
        if len(text) <= 2000:
            await ch.send(text)
        else:
            parts = []
            cur = ""
            for s in re.split(r"([.!?]+)", text):
                if len(cur) + len(s) < 1900:
                    cur += s
                else:
                    if cur:
                        parts.append(cur.strip())
                    cur = s
            if cur:
                parts.append(cur.strip())
            for i, p in enumerate(parts):
                await ch.send(p)
                if i < len(parts) - 1:
                    await asyncio.sleep(random.randint(1, 2))

def _result_icon(r: str) -> str:
    return "🟢" if r == "W" else ("🟡" if r == "D" else "🔴")

def _aggregate_stats(matches: List[Dict]) -> Dict:
    agg = {}
    for m in matches:
        for p in m.get("players", []) or []:
            name = p.get("name", "Unknown")
            if name not in agg:
                agg[name] = {"name": name, "games": 0, "goals": 0, "assists": 0, "shots": 0, "tackles": 0, "tackles_attempted": 0, "interceptions": 0, "passes_attempted": 0, "passes_completed": 0, "ratings": [], "avg_rating": 0.0}
            agg[name]["games"] += 1
            agg[name]["goals"] += p.get("goals", 0)
            agg[name]["assists"] += p.get("assists", 0)
            agg[name]["shots"] += p.get("shots", 0)
            agg[name]["tackles"] += p.get("tackles", 0)
            agg[name]["tackles_attempted"] += p.get("tackles_attempted", 0)
            agg[name]["interceptions"] += p.get("interceptions", 0)
            agg[name]["passes_attempted"] += p.get("passes_attempted", 0)
            agg[name]["passes_completed"] += p.get("passes_completed", 0)
            agg[name]["ratings"].append(p.get("rating", 0))
    for name in agg:
        r = agg[name]["ratings"]
        agg[name]["avg_rating"] = sum(r) / len(r) if r else 0
    return agg

def _clean_lines(text, max_lines=2):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return "\n".join(lines[:max_lines])

async def _get_matches(n: int = 5) -> List[Dict]:
    try:
        data = await _scraper.fetch_all(max_matches=n, force=False)
        return data.get("matches", [])
    except Exception as e:
        logger.error(f"Get matches error: {e}")
        return []

async def _get_all_data(n: int = 1) -> Dict:
    try:
        return await _scraper.fetch_all(max_matches=n, force=False)
    except Exception as e:
        logger.error(f"Get all data error: {e}")
        return {}

# ─── AUTO LEADERBOARD TASKS ───

@tasks.loop(hours=24)
async def daily_leaderboard():
    ch = _match_channel()
    if not ch:
        return
    matches = await _get_matches(5)
    if not matches:
        return
    agg = _aggregate_stats(matches)
    if not agg:
        return
    lines = ["📊 DAILY LEADERBOARD — Rachad L3ERGONI", ""]
    sorted_players = sorted(agg.values(), key=lambda x: (x["goals"] + x["assists"] * 0.5, x["avg_rating"]), reverse=True)
    for i, p in enumerate(sorted_players[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅"
        lines.append(f"{medal} **{p['name']}** — {p['goals']}G {p['assists']}A | ⭐{p['avg_rating']:.1f} | {p['games']}m")
    await _send(ch, "\n".join(lines), emotion="disappointment")

@daily_leaderboard.before_loop
async def before_daily():
    await bot.wait_until_ready()
    now = datetime.now()
    target = now.replace(hour=20, minute=0, second=0, microsecond=0)
    if target < now:
        target += timedelta(days=1)
    await asyncio.sleep((target - now).total_seconds())

@tasks.loop(hours=168)
async def weekly_leaderboard():
    ch = _match_channel()
    if not ch:
        return
    matches = await _get_matches(20)
    if not matches:
        return
    agg = _aggregate_stats(matches)
    if not agg:
        return
    lines = ["📊 WEEKLY LEADERBOARD — Rachad L3ERGONI", ""]
    sorted_players = sorted(agg.values(), key=lambda x: (x["goals"] + x["assists"] * 0.5, x["avg_rating"]), reverse=True)
    for i, p in enumerate(sorted_players[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅"
        lines.append(f"{medal} **{p['name']}** — {p['goals']}G {p['assists']}A | ⭐{p['avg_rating']:.1f} | {p['games']}m")
    await _send(ch, "\n".join(lines), emotion="disappointment")

@weekly_leaderboard.before_loop
async def before_weekly():
    await bot.wait_until_ready()
    now = datetime.now()
    target = now.replace(hour=20, minute=0, second=0, microsecond=0)
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0 and target < now:
        days_until_sunday = 7
    target += timedelta(days=days_until_sunday)
    await asyncio.sleep((target - now).total_seconds())

@tasks.loop(hours=720)
async def monthly_leaderboard():
    ch = _match_channel()
    if not ch:
        return
    matches = await _get_matches(50)
    if not matches:
        return
    agg = _aggregate_stats(matches)
    if not agg:
        return
    lines = ["📊 MONTHLY LEADERBOARD — Rachad L3ERGONI", ""]
    sorted_players = sorted(agg.values(), key=lambda x: (x["goals"] + x["assists"] * 0.5, x["avg_rating"]), reverse=True)
    for i, p in enumerate(sorted_players[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅"
        lines.append(f"{medal} **{p['name']}** — {p['goals']}G {p['assists']}A | ⭐{p['avg_rating']:.1f} | {p['games']}m")
    await _send(ch, "\n".join(lines), emotion="disappointment")

@monthly_leaderboard.before_loop
async def before_monthly():
    await bot.wait_until_ready()
    now = datetime.now()
    target = now.replace(day=1, hour=20, minute=0, second=0, microsecond=0)
    if target < now:
        if now.month == 12:
            target = target.replace(year=now.year + 1, month=1)
        else:
            target = target.replace(month=now.month + 1)
    await asyncio.sleep((target - now).total_seconds())

# ─── SESSION POLLING ───

@tasks.loop(minutes=POLL_MINUTES)
async def poll_matches():
    global _session_active, _last_activity_ts, _last_match_id
    if not _session_active:
        return
    idle_min = (time.monotonic() - _last_activity_ts) / 60
    if idle_min >= TIMEOUT_MINUTES:
        await _stop_session("timeout")
        return
    try:
        data = await _scraper.fetch_all(max_matches=1, force=True)
        raw_matches = data.get("matches", [])
        if not raw_matches:
            return
        raw = raw_matches[0]
        mid = str(raw.get("match_id", ""))
        if mid == _last_match_id or not mid:
            return
        _last_match_id = mid
        _last_activity_ts = time.monotonic()
        logger.info(f"New match: {mid}")
        await _post_match(_match_channel(), raw)
    except Exception as e:
        logger.error(f"Poll error: {e}")

@poll_matches.before_loop
async def before_poll():
    await bot.wait_until_ready()

async def _start_session(channel):
    global _session_active, _last_activity_ts, _last_match_id
    if _session_active:
        await _send(channel, "Session deja active!", emotion="disappointment")
        return
    try:
        data = await _scraper.fetch_all(max_matches=1, force=False)
        raw_matches = data.get("matches", [])
        if raw_matches:
            _last_match_id = str(raw_matches[0].get("match_id", ""))
    except:
        _last_match_id = None
    _session_active = True
    _last_activity_ts = time.monotonic()
    if not poll_matches.is_running():
        poll_matches.start()
    await _send(channel, f"Session demarree! Check kol {POLL_MINUTES}min. Auto-stop apres {TIMEOUT_MINUTES}min. !stop bach t7bss.", emotion="disappointment")

async def _stop_session(reason="manual"):
    global _session_active
    _session_active = False
    if poll_matches.is_running():
        poll_matches.stop()
    ch = _match_channel()
    if not ch:
        return
    if reason == "timeout":
        await _send(ch, f"Session terminee. {TIMEOUT_MINUTES}min bla match. !roast quand tu rejoues!", emotion="disappointment")
    else:
        await _send(ch, "Session arretee. Safi.", emotion="thinking")

async def _post_match(ch, m):
    try:
        emoji = _result_icon(m["result"])
        header = f"{emoji} **{m['our_goals']}-{m['opp_goals']}** vs **{m['opp_name']}**"
        await ch.send(header)

        if roast_engine.is_boring_game(m.get("players", []), m):
            silent = roast_engine.build_silent_treatment(m)
            await _send(ch, silent, emotion="disappointment")
            return

        if m.get("players"):
            chaos_results = achievements.evaluate_players(m["players"])
            chaos_report = achievements.format_chaos_report(chaos_results)
            if chaos_report:
                chaos_report = _clean_lines(chaos_report, 2)
                await _send(ch, chaos_report, emotion="laughter")

            roast_text = roast_engine.build_roast_text(
                roast_engine.get_roast_victims(m["players"]),
                m, m["players"]
            )
            if roast_text:
                roast_text = _clean_lines(roast_text, 2)
                await _send(ch, roast_text, emotion="laughter")

        report = await gemini.match_report(m)
        report = _clean_lines(report, 2)
        emotion = "disappointment" if m["result"] == "L" else "laughter"
        await _send(ch, report, emotion=emotion)

        # Individual player stats after match
        if m.get("players"):
            for p in m["players"]:
                player_data = humanizer.get_player(p["name"])
                position = player_data.get("position", "MID") if player_data else "MID"
                img_path = player_data.get("image") if player_data else None
                stats_text = f"{p['name']}: {p['goals']}G {p['assists']}A | ⭐{p['rating']:.1f} | {p['shots']} shots"
                await _send(ch, stats_text, emotion="disappointment")

        # MOTM with anime card
        if m.get("players"):
            best = m["players"][0]
            motm_text = humanizer.get_motm(best["name"], best["rating"], best["goals"], best["assists"])
            player_data = humanizer.get_player(best["name"])
            img_path = player_data.get("image") if player_data else None
            loop = asyncio.get_event_loop()
            motm_img = await loop.run_in_executor(
                None, image_gen.make_motm_card,
                best["name"], best["rating"], best["goals"], best["assists"],
                f"vs {m['opp_name']}", img_path
            )
            await _send(ch, motm_text, motm_img, "motm.png", emotion="laughter")
    except Exception as e:
        logger.error(f"Post error: {e}")
        await ch.send(f"Error: {str(e)[:100]}")

# ═══════════════════════════════════════════════════════════════════════════════
# 10-12 EFFICIENT COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="roast")
async def cmd_roast(ctx):
    """Start session monitoring."""
    await _start_session(ctx.channel)

@bot.command(name="stop")
async def cmd_stop(ctx):
    """Stop session monitoring."""
    await _stop_session("manual")

@bot.command(name="lastmatch", aliases=["last", "match"])
async def cmd_lastmatch(ctx):
    """Last match + all player stats + MOTM anime card."""
    async with ctx.typing():
        matches = await _get_matches(1)
        if not matches:
            await _send(ctx.channel, "Ma3endnach match daba. Walo.", emotion="disappointment")
            return
        await _post_match(ctx.channel, matches[0])

@bot.command(name="stats")
async def cmd_stats(ctx, *, player_name: str = ""):
    """Player stats + anime card. !stats Hamza"""
    if not player_name:
        await _send(ctx.channel, "Usage: !stats NomJoueur", emotion="thinking")
        return
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion="disappointment")
            return
        agg = _aggregate_stats(matches)
        key = next((k for k in agg if player_name.lower() in k.lower()), None)
        if not key:
            await _send(ctx.channel, f"{player_name}? Ma3endnach stats. !leaderboard bach tchouf.", emotion="thinking")
            return
        s = agg[key]
        player_data = humanizer.get_player(player_name)
        position = player_data.get("position", "MID") if player_data else "MID"
        img_path = player_data.get("image") if player_data else None
        stats_dict = {"goals": s["goals"], "assists": s["assists"], "rating": s["avg_rating"], "shots": s["shots"], "tackles": s["tackles"], "passes_completed": s["passes_completed"]}
        loop = asyncio.get_event_loop()
        card_buf = await loop.run_in_executor(None, image_gen.make_player_stats_card, s["name"], stats_dict, position, img_path)
        text = f"{s['name']}: {s['games']}m | {s['goals']}G {s['assists']}A | ⭐{s['avg_rating']:.1f}"
        await _send(ctx.channel, text, card_buf, f"{s['name']}_stats.png", emotion="disappointment")

@bot.command(name="roastplayer")
async def cmd_roastplayer(ctx, *, player_name: str = ""):
    """Roast a player. !roastplayer Hamza"""
    if not player_name:
        await _send(ctx.channel, "Kteb ism: !roastplayer Nom", emotion="thinking")
        return
    player_data = humanizer.get_player(player_name)
    if player_data:
        roast = humanizer.get_roast(player_name)
        await _send(ctx.channel, roast, emotion="laughter")
        return
    async with ctx.typing():
        matches = await _get_matches(5)
        text = await gemini.roast(player_name, matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion="laughter")

@bot.command(name="leaderboard", aliases=["lb", "rank"])
async def cmd_leaderboard(ctx, period: str = "day"):
    """Leaderboard: !leaderboard day/week/month/all"""
    async with ctx.typing():
        n = {"day": 5, "week": 20, "month": 50, "all": 100}.get(period.lower(), 5)
        matches = await _get_matches(n)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion="disappointment")
            return
        agg = _aggregate_stats(matches)
        if not agg:
            await _send(ctx.channel, "Ma3endnach stats. Walo.", emotion="disappointment")
            return
        lines = [f"📊 LEADERBOARD ({period.upper()}) — Rachad L3ERGONI", ""]
        sorted_players = sorted(agg.values(), key=lambda x: (x["goals"] + x["assists"] * 0.5, x["avg_rating"]), reverse=True)
        for i, p in enumerate(sorted_players[:10], 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅"
            lines.append(f"{medal} **{p['name']}** — {p['goals']}G {p['assists']}A | ⭐{p['avg_rating']:.1f} | {p['games']}m")
        await ctx.send("\n".join(lines))

@bot.command(name="mvp")
async def cmd_mvp(ctx):
    """MVP of last 5 matches + anime card."""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion="disappointment")
            return
        agg = _aggregate_stats(matches)
        if not agg:
            await _send(ctx.channel, "Ma3endnach stats. Walo.", emotion="disappointment")
            return
        mvp = max(agg.values(), key=lambda x: x["avg_rating"] + x["goals"] * 0.5 + x["assists"] * 0.3)
        player_data = humanizer.get_player(mvp["name"])
        img_path = player_data.get("image") if player_data else None
        loop = asyncio.get_event_loop()
        mvp_img = await loop.run_in_executor(None, image_gen.make_motm_card, mvp["name"], mvp["avg_rating"], mvp["goals"], mvp["assists"], "MVP — Last 5 Matches", img_path)
        text = f"👑 MVP: {mvp['name']} | {mvp['games']}m | {mvp['goals']}G {mvp['assists']}A | ⭐{mvp['avg_rating']:.1f}"
        await _send(ctx.channel, text, mvp_img, "mvp.png", emotion="laughter")

@bot.command(name="compare")
async def cmd_compare(ctx, p1: str = "", *, p2: str = ""):
    """Compare 2 players. !compare Hamza Karim"""
    if not p1 or not p2:
        await _send(ctx.channel, "Usage: !compare J1 J2", emotion="thinking")
        return
    await _send(ctx.channel, f"{p1} vs {p2}...", emotion="thinking")
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion="disappointment")
            return
        result = await gemini.compare_players(p1, p2, matches)
        if isinstance(result, str):
            text = _clean_lines(result, 2)
            await _send(ctx.channel, text, emotion="laughter")
            return
        text, s1, s2 = result
        text = _clean_lines(text, 2)
        loop = asyncio.get_event_loop()
        card_buf = await loop.run_in_executor(None, image_gen.make_comparison_card, s1, s2)
    await _send(ctx.channel, text, card_buf, f"compare_{p1}_{p2}.png", emotion="laughter")

@bot.command(name="banter")
async def cmd_banter(ctx):
    """Football banter trash talk."""
    async with ctx.typing():
        matches = await _get_matches(1)
        text = await gemini.banter(matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion="laughter")

@bot.command(name="drama")
async def cmd_drama(ctx):
    """Drama / polemique."""
    async with ctx.typing():
        matches = await _get_matches(1)
        text = await gemini.drama_post(matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion="disappointment")

@bot.command(name="meme")
async def cmd_meme(ctx):
    """Meme football b Darija."""
    async with ctx.typing():
        matches = await _get_matches(1)
        text = await gemini.meme_post(matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion="laughter")

@bot.command(name="transfer")
async def cmd_transfer(ctx):
    """Transfer rumor (humour)."""
    async with ctx.typing():
        matches = await _get_matches(5)
        data = await _get_all_data(1)
        text = await gemini.transfer_rumor(data.get("members", []), matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion="laughter")

@bot.command(name="predict")
async def cmd_predict(ctx, *, opponent: str = "Prochain adversaire"):
    """Prediction next match. !predict NomAdversaire"""
    async with ctx.typing():
        matches = await _get_matches(5)
        text = await gemini.match_prediction(opponent, matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion="thinking")

@bot.command(name="clubinfo")
async def cmd_clubinfo(ctx):
    """Club info."""
    async with ctx.typing():
        data = await _get_all_data(1)
    info = data.get("club_info") or {}
    s = data.get("club_stats") or {}
    lines = [
        f"🏟️ **{info.get('name','Rachad L3ERGONI')}**",
        f"🎮 common-gen5 | proclubstracker.com/club/1427607",
        f"W:{s.get('wins','?')} D:{s.get('ties','?')} L:{s.get('losses','?')} | SR:{s.get('skillRating','?')}",
    ]
    await ctx.send("\n".join(lines))

@bot.command(name="help")
async def cmd_help(ctx):
    lines = [
        "⚽ **Rachad L3ERGONI Bot** _(Bad Words Only · Auto Leaderboards · Anime Cards)_",
        "",
        "**🎮 SESSION** `!roast` `!stop`",
        "**📋 MATCH** `!lastmatch`",
        "**👥 PLAYERS** `!stats <nom>` `!roastplayer <nom>` `!mvp` `!compare <p1> <p2>`",
        "**📊 LEADERBOARD** `!leaderboard day/week/month/all`",
        "**😂 FUN** `!banter` `!drama` `!meme` `!transfer`",
        "**🔮 PREDICT** `!predict <adversaire>`",
        "**ℹ️ INFO** `!clubinfo` `!help`",
        "",
        "_Auto: matchs kol 5min · Daily LB 20h · Weekly LB dimanche 20h · Monthly LB 1er 20h_",
    ]
    await ctx.send("\n".join(lines))

# ─── EVENTS ───

@bot.event
async def on_ready():
    global seen_matches
    seen_matches = load_seen()
    logger.info(f"Bot ready: {bot.user}")
    logger.info(f"Session poll: every {POLL_MINUTES}min | Timeout: {TIMEOUT_MINUTES}min")
    logger.info(f"Auto leaderboards: Daily 20h | Weekly dimanche 20h | Monthly 1er 20h")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="your matches 👀"))
    if not daily_leaderboard.is_running():
        daily_leaderboard.start()
    if not weekly_leaderboard.is_running():
        weekly_leaderboard.start()
    if not monthly_leaderboard.is_running():
        monthly_leaderboard.start()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.content:
        logger.info("[MSG] #%s | %s: %s", getattr(message.channel, "name", "DM"), message.author.name, message.content[:80])
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await _send(ctx.channel, "Ma3ndekch permission!", emotion="disappointment")
    elif isinstance(error, commands.MissingRequiredArgument):
        await _send(ctx.channel, "Naqes argument — !help bach tchouf.", emotion="thinking")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        logger.error("Command error [%s]: %s", ctx.command, error, exc_info=True)
        await _send(ctx.channel, f"Error: {str(error)[:100]}", emotion="disappointment")

# ─── HEALTH SERVER ───
import aiohttp
from aiohttp import web

async def health_handler(request):
    return web.Response(text="Rachad L3ERGONI OK")

async def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    app = web.Application()
    app.router.add_get("/", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health server bound to port {port}")
    return runner

# ─── START ───
if __name__ == "__main__":
    async def main():
        runner = await start_health_server()
        await bot.start(TOKEN)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise
