"""
Rachad L3ERGONI Pro Clubs Discord Bot — v3
- Real data: proclubstracker.com JSON API (httpx, cached 30 min)
- 30+ commands in Moroccan Darija
- FIFA/anime-style images via Pillow
- Auto check every 6h for new matches
- Daily stat (10h UTC), spotlight (20h UTC), weekly recap (Sunday 20h UTC)
"""
import os
import io
import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

import ea_api
import gemini
import image_gen
import scraper as _scraper
from state import load_seen, save_seen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

TOKEN = os.environ[MTUxNDIzMzc5OTc5MjM5NDI3Mg.GfyxTa.3Dz1j6L03PhsHCWRkFnUc0Y_d8R0UBGS4LjmlE]

# ── Config ────────────────────────────────────────────────────────────────────

MATCH_CHECK_HOURS   = 6     # check for new matches every 6 hours
WEEKLY_DAY          = 6     # Sunday
WEEKLY_HOUR         = 20    # 20:00 UTC
DAILY_HOUR_AM       = 10    # Stat of the Day
DAILY_HOUR_PM       = 20    # Player Spotlight

# ── Bot Setup ─────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

_match_channel_id:   int | None = int(os.environ.get("MATCH_CHANNEL_ID",   0)) or None
_general_channel_id: int | None = int(os.environ.get("GENERAL_CHANNEL_ID", 0)) or None
seen_matches: set[str] = set()

_weekly_posted   = False
_daily_am_posted = False
_daily_pm_posted = False
_spotlight_index = 0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _match_ch()   -> discord.TextChannel | None:
    return bot.get_channel(_match_channel_id)   if _match_channel_id   else None
def _general_ch() -> discord.TextChannel | None:
    return bot.get_channel(_general_channel_id) if _general_channel_id else _match_ch()

async def _send(ch: discord.abc.Messageable, text: str = "",
                buf: io.BytesIO = None, filename: str = "image.png"):
    text = (text or "").strip()
    if not text and not buf:
        return
    if buf:
        buf.seek(0)
        f = discord.File(buf, filename=filename)
        first, rest = text[:2000], text[2000:]
        await ch.send(first or None, file=f)
        while rest:
            chunk, rest = rest[:2000], rest[2000:]
            await ch.send(chunk)
    else:
        while text:
            chunk, text = text[:2000], text[2000:]
            await ch.send(chunk)

async def _get_matches(n: int = 5, force: bool = False) -> list:
    data = await _scraper.fetch_all(max_matches=n, force=force)
    return data.get("matches", [])

async def _get_all(n: int = 5, force: bool = False) -> dict:
    return await _scraper.fetch_all(max_matches=n, force=force)

def _parse_all(raw_list: list) -> list:
    return [ea_api.parse_match(r) for r in raw_list]

def _result_icon(r: str) -> str:
    return "🟢" if r == "W" else ("🟡" if r == "D" else "🔴")


async def _post_match(channel, m: dict):
    """Full match package: poster + report + MOTM card + 3 reaction tweets."""
    try:
        loop = asyncio.get_event_loop()
        report_t = asyncio.create_task(gemini.match_report(m))
        motm_t   = asyncio.create_task(gemini.motm_post(m))
        tweets_t = asyncio.create_task(gemini.funny_reactions(m))

        poster_buf = await loop.run_in_executor(None, lambda: image_gen.make_match_poster(
            m["our_name"], m["opp_name"], m["our_goals"], m["opp_goals"], m["date"],
        ))
        report, motm_text, tweets = await asyncio.gather(report_t, motm_t, tweets_t)

        await _send(channel, report, poster_buf, f"match_{m['our_goals']}_{m['opp_goals']}.png")
        await asyncio.sleep(1.5)

        if motm_text and m["players"]:
            best = m["players"][0]
            motm_buf = await loop.run_in_executor(None, lambda: image_gen.make_motm_card(
                best["name"], best["rating"], best["goals"], best["assists"],
                match_context=f"vs {m['opp_name']} ({m['our_goals']}-{m['opp_goals']})",
            ))
            await _send(channel, motm_text, motm_buf, "motm.png")
            await asyncio.sleep(1.5)

        if tweets:
            await channel.send("🐦 **Réactions:**\n\n" + "\n\n".join(f"> {t}" for t in tweets))
    except Exception as e:
        logger.error("_post_match error: %s", e, exc_info=True)


async def _post_five_summary(channel, matches: list, members: list):
    loop = asyncio.get_event_loop()
    summary_t    = asyncio.create_task(gemini.five_match_summary(matches))
    performers_t = asyncio.create_task(gemini.top_performers(matches, members))
    totw_t       = asyncio.create_task(gemini.team_of_the_week(matches))

    results_data = [{"opponent": m["opp_name"], "our_goals": m["our_goals"],
                     "opp_goals": m["opp_goals"], "date": m["date"]} for m in matches]
    summary_img  = await loop.run_in_executor(None, lambda: image_gen.make_five_match_summary(results_data))

    summary_text, performers_text, (totw_text, totw_players) = await asyncio.gather(
        summary_t, performers_t, totw_t)
    totw_img = await loop.run_in_executor(None, lambda: image_gen.make_totw_card(totw_players))

    await _send(channel, summary_text, summary_img, "last5.png")
    await asyncio.sleep(2)
    await _send(channel, performers_text)
    await asyncio.sleep(2)
    await _send(channel, totw_text, totw_img, "totw.png")


# ── Background Tasks ──────────────────────────────────────────────────────────

@tasks.loop(hours=MATCH_CHECK_HOURS)
async def check_new_matches():
    global seen_matches
    channel = _match_ch()
    if not channel:
        logger.info("No match channel set — skipping check")
        return
    raw = await _get_matches(5, force=True)   # force=True to bypass cache
    if not raw:
        logger.info("No matches returned")
        return
    new = []
    for r in raw:
        mid = ea_api.get_match_id(r)
        if mid and mid not in seen_matches:
            new.append(r); seen_matches.add(mid)
    if new:
        save_seen(seen_matches)
        logger.info("%d new match(es) detected", len(new))
    for r in reversed(new):
        m = ea_api.parse_match(r)
        await _post_match(channel, m)
        await asyncio.sleep(3)


@tasks.loop(minutes=30)
async def daily_weekly_check():
    global _weekly_posted, _daily_am_posted, _daily_pm_posted, _spotlight_index
    now = datetime.now(timezone.utc)
    ch  = _general_ch()
    if not ch:
        return
    hour, weekday = now.hour, now.weekday()
    if hour == 0:
        _daily_am_posted = False
        _daily_pm_posted = False

    # Morning: Stat of the Day
    if hour == DAILY_HOUR_AM and not _daily_am_posted:
        _daily_am_posted = True
        try:
            raw = await _get_matches(5)
            if raw:
                matches = _parse_all(raw)
                text = await gemini.stat_of_day(matches)
                if text:
                    await _send(ch, text)
        except Exception as e:
            logger.error("Stat of day error: %s", e)

    # Evening: Player Spotlight (not Sunday — that's weekly)
    if hour == DAILY_HOUR_PM and not _daily_pm_posted and weekday != WEEKLY_DAY:
        _daily_pm_posted = True
        try:
            raw = await _get_matches(5)
            if raw:
                matches = _parse_all(raw)
                agg = ea_api.aggregate_stats(matches)
                players = sorted(agg.keys(), key=lambda k: agg[k]["avg_rating"], reverse=True)
                if players:
                    spotlight_player = players[_spotlight_index % len(players)]
                    _spotlight_index += 1
                    text = await gemini.player_spotlight(spotlight_player, matches)
                    if text:
                        await _send(ch, text)
        except Exception as e:
            logger.error("Spotlight error: %s", e)

    # Sunday 20:00: Weekly Recap
    if weekday == WEEKLY_DAY and hour == WEEKLY_HOUR and not _weekly_posted:
        _weekly_posted = True
        _daily_pm_posted = True
        try:
            raw = await _get_matches(5)
            if raw:
                matches = _parse_all(raw)
                data = await _get_all(1)
                members = data.get("members", [])
                await _send(ch, "🗓️ **WEEKLY RECAP — Rachad L3ERGONI** 🏆")
                await asyncio.sleep(1)
                await _post_five_summary(ch, matches, members)
        except Exception as e:
            logger.error("Weekly recap error: %s", e)

    if weekday != WEEKLY_DAY:
        _weekly_posted = False


# ── Events ────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    global seen_matches
    seen_matches = load_seen()
    logger.info("✅ Bot ready: %s | Club: %s", bot.user, ea_api.CLUB_ID)
    logger.info("   Match check: every %dh | Prefix: !", MATCH_CHECK_HOURS)
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
                    message.author.name, message.content[:100])
    await bot.process_commands(message)


# ── MATCH Commands ────────────────────────────────────────────────────────────

@bot.command(name="last5")
async def cmd_last5(ctx):
    """Analyse des 5 derniers matchs + performers + TOTW."""
    await ctx.send("⏳ Kan-load last 5 matchs... 🤖")
    async with ctx.typing():
        raw = await _get_matches(5)
        if not raw:
            await ctx.send("❌ Ma3endnach matches daba 😴"); return
        matches = _parse_all(raw)
        data = await _get_all(1)
        await _post_five_summary(ctx.channel, matches, data.get("members", []))

@bot.command(name="last10")
async def cmd_last10(ctx):
    """Analyse des 10 derniers matchs."""
    await ctx.send("⏳ Kan-load last 10 matchs... 🤖")
    async with ctx.typing():
        raw = await _get_matches(10)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        matches = _parse_all(raw)
        wins   = sum(1 for m in matches if m["result"]=="W")
        draws  = sum(1 for m in matches if m["result"]=="D")
        losses = sum(1 for m in matches if m["result"]=="L")
        gf     = sum(m["our_goals"] for m in matches)
        ga     = sum(m["opp_goals"] for m in matches)
        form   = "".join(m["result"] for m in matches[:10])
        lines  = [
            "📊 **LAST 10 MATCHS — Rachad L3ERGONI**",
            f"🏆 W: **{wins}** | 🟡 D: **{draws}** | 💀 L: **{losses}**",
            f"⚽ {gf} pour / {ga} contre | Form: `{form}`",
            "",
        ]
        for m in matches:
            e = _result_icon(m["result"])
            lines.append(f"{e} {m['date']} — **{m['our_goals']}-{m['opp_goals']}** vs {m['opp_name']}")
        await ctx.send("\n".join(lines[:2000]))

        text = await gemini.form_analysis(matches)
        await _send(ctx.channel, text)

@bot.command(name="match")
async def cmd_match(ctx, index: int = 1):
    """Rapport d'un match spécifique. !match 1 = dernier."""
    if not 1 <= index <= 10:
        await ctx.send("❌ Index bin 1 w 10."); return
    await ctx.send(f"⏳ Match #{index}...")
    async with ctx.typing():
        raw = await _get_matches(10)
        if index > len(raw):
            await ctx.send(f"❌ Ghir {len(raw)} matchs disponibles."); return
        m = ea_api.parse_match(raw[index - 1])
        await _post_match(ctx.channel, m)

@bot.command(name="lastmatch")
async def cmd_lastmatch(ctx):
    """Rapport complet du dernier match."""
    await ctx.send("⏳ Dernier match...")
    async with ctx.typing():
        raw = await _get_matches(1)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        m = ea_api.parse_match(raw[0])
        await _post_match(ctx.channel, m)

@bot.command(name="report")
async def cmd_report(ctx):
    """Alias de !lastmatch."""
    await cmd_lastmatch(ctx)

@bot.command(name="quickreport")
async def cmd_quickreport(ctx):
    """Rapport court du dernier match (1-2 lignes)."""
    async with ctx.typing():
        raw = await _get_matches(1)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        m = ea_api.parse_match(raw[0])
        text = await gemini.quick_report(m)
        await ctx.send(text)

@bot.command(name="results")
async def cmd_results(ctx):
    """Tableau des 10 derniers résultats."""
    async with ctx.typing():
        raw = await _get_matches(10)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        matches = _parse_all(raw)
        lines = ["📋 **RÉSULTATS — Rachad L3ERGONI**", ""]
        for i, m in enumerate(matches, 1):
            e = _result_icon(m["result"])
            lines.append(f"`{i:2}.` {e} `{m['our_goals']}-{m['opp_goals']}` vs **{m['opp_name']}** — {m['date']}")
        await ctx.send("\n".join(lines))

@bot.command(name="schedule")
async def cmd_schedule(ctx):
    """Prochains matchs (basé sur la forme récente + adversaires)."""
    async with ctx.typing():
        raw = await _get_matches(5)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        matches = _parse_all(raw)
        opponents = [m["opp_name"] for m in matches[:3]]
        opp_str = ", ".join(opponents)
        text = await gemini.match_prediction(opp_str, matches)
        await ctx.send(f"🗓️ **Prochains adversaires potentiels:**\n{', '.join(opponents)}\n\n{text}")


# ── PLAYER Commands ───────────────────────────────────────────────────────────

@bot.command(name="players")
async def cmd_players(ctx):
    """Liste tous les joueurs avec stats saison."""
    async with ctx.typing():
        data = await _get_all(1)
        members = data.get("members", [])
        if not members:
            await ctx.send("❌ Ma3endnach données membres 😴"); return
        lines = ["👥 **SQUAD — Rachad L3ERGONI**", ""]
        for m in sorted(members, key=lambda x: float(x.get("ratingAve", 0) or 0), reverse=True):
            name = m.get("proName") or m.get("name", "?")
            games = m.get("gamesPlayed", "?")
            goals = m.get("goals", "?")
            assists = m.get("assists", "?")
            rating = m.get("ratingAve", "?")
            pos = m.get("favoritePosition", "MID").upper()[:3]
            lines.append(f"**{name}** `{pos}` — {goals}G {assists}A | {rating} avg | {games} matchs")
        await ctx.send("\n".join(lines)[:2000])

@bot.command(name="player")
async def cmd_player(ctx, *, player_name: str = ""):
    """Stats d'un joueur. !player Hamza"""
    if not player_name:
        await ctx.send("Usage: `!player NomJoueur`"); return
    async with ctx.typing():
        raw = await _get_matches(5)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        matches = _parse_all(raw)
        agg = ea_api.aggregate_stats(matches)
        key = next((k for k in agg if k.lower() == player_name.lower()), None)
        if not key:
            await ctx.send(f"❌ **{player_name}** — ma3endnach stats f les derniers matchs.\nTry: `!players` bach tchouf l'ism exact."); return
        s = agg[key]
        lines = [
            f"👤 **{s['name']}** — Stats 5 Derniers Matchs",
            f"🎮 Matchs: **{s['games']}**",
            f"⚽ Buts: **{s['goals']}** | 🎯 Assists: **{s['assists']}**",
            f"⭐ Rating: **{s['avg_rating']:.2f}/10**",
            f"💥 Shots: **{s['shots']}** | 🛡️ Tackles: **{s['tackles']}**",
        ]
        await ctx.send("\n".join(lines))

@bot.command(name="form")
async def cmd_form(ctx, *, player_name: str = ""):
    """Analyse de forme. !form → team | !form Hamza → joueur"""
    async with ctx.typing():
        raw = await _get_matches(5)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        matches = _parse_all(raw)
        if player_name:
            text = await gemini.player_form(player_name, matches)
        else:
            text = await gemini.form_analysis(matches)
    await _send(ctx.channel, text)

@bot.command(name="topscorer")
async def cmd_topscorer(ctx):
    """Classement des meilleurs buteurs."""
    async with ctx.typing():
        raw = await _get_matches(5)
        data = await _get_all(1)
        matches = _parse_all(raw) if raw else []
        text = await gemini.top_scorer_post(matches, data.get("members", []))
    await _send(ctx.channel, text)

@bot.command(name="topassists")
async def cmd_topassists(ctx):
    """Classement des meilleurs assisteurs."""
    async with ctx.typing():
        raw = await _get_matches(5)
        data = await _get_all(1)
        matches = _parse_all(raw) if raw else []
        text = await gemini.top_assists_post(matches, data.get("members", []))
    await _send(ctx.channel, text)

@bot.command(name="mvp")
async def cmd_mvp(ctx):
    """MVP des 5 derniers matchs."""
    async with ctx.typing():
        raw = await _get_matches(5)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        matches = _parse_all(raw)
        text = await gemini.mvp_post(matches)
    await _send(ctx.channel, text)

@bot.command(name="compare")
async def cmd_compare(ctx, player1: str = "", *, player2: str = ""):
    """Compare 2 joueurs. !compare Hamza Karim"""
    if not player1 or not player2:
        await ctx.send("Usage: `!compare Joueur1 Joueur2`"); return
    await ctx.send(f"⚔️ **{player1}** vs **{player2}**...")
    async with ctx.typing():
        raw = await _get_matches(5)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        matches = _parse_all(raw)
        result = await gemini.compare_players(player1, player2, matches)
        if isinstance(result, str):
            await ctx.send(result); return
        text, s1, s2 = result
        loop = asyncio.get_event_loop()
        card_buf = await loop.run_in_executor(None, lambda: image_gen.make_comparison_card(s1, s2))
    await _send(ctx.channel, text, card_buf, f"compare_{player1}_{player2}.png")


# ── CONTENT Commands ──────────────────────────────────────────────────────────

@bot.command(name="motm")
async def cmd_motm(ctx, match_index: int = 1):
    """Man of the Match. !motm [1-5]"""
    async with ctx.typing():
        raw = await _get_matches(match_index)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        m = ea_api.parse_match(raw[match_index - 1])
        if not m["players"]:
            await ctx.send("❌ Bla stats joueurs pour ce match."); return
        best = m["players"][0]
        loop = asyncio.get_event_loop()
        motm_text, motm_buf = await asyncio.gather(
            gemini.motm_post(m),
            loop.run_in_executor(None, lambda: image_gen.make_motm_card(
                best["name"], best["rating"], best["goals"], best["assists"],
                match_context=f"vs {m['opp_name']} ({m['our_goals']}-{m['opp_goals']})",
            )),
        )
    await _send(ctx.channel, motm_text or "", motm_buf, "motm.png")

@bot.command(name="totw")
async def cmd_totw(ctx):
    """Team of the Week avec image."""
    await ctx.send("⏳ Building TOTW...")
    async with ctx.typing():
        raw = await _get_matches(5)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        matches = _parse_all(raw)
        loop = asyncio.get_event_loop()
        totw_text, totw_players = await gemini.team_of_the_week(matches)
        totw_img = await loop.run_in_executor(None, lambda: image_gen.make_totw_card(totw_players))
    await _send(ctx.channel, totw_text, totw_img, "totw.png")

@bot.command(name="recap")
async def cmd_recap(ctx):
    """Récap complet derniers 5 matchs."""
    await ctx.send("⏳ Kan-generate recap complet...")
    async with ctx.typing():
        raw = await _get_matches(5)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        matches = _parse_all(raw)
        data = await _get_all(1)
        await _post_five_summary(ctx.channel, matches, data.get("members", []))

@bot.command(name="hype")
async def cmd_hype(ctx, *, context: str = ""):
    """Post de motivation. !hype [adversaire]"""
    async with ctx.typing():
        text = await gemini.hype_post(context)
    await _send(ctx.channel, text)

@bot.command(name="reaction")
async def cmd_reaction(ctx):
    """Réaction courte sur le dernier match."""
    async with ctx.typing():
        raw = await _get_matches(1)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        m = ea_api.parse_match(raw[0])
        text = await gemini.reaction_post(m)
    await ctx.send(text)

@bot.command(name="rankings")
async def cmd_rankings(ctx):
    """Top performers des 5 derniers matchs."""
    async with ctx.typing():
        raw = await _get_matches(5)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        matches = _parse_all(raw)
        data = await _get_all(1)
        text = await gemini.top_performers(matches, data.get("members", []))
    await _send(ctx.channel, text)


# ── FUN Commands ──────────────────────────────────────────────────────────────

@bot.command(name="roast")
async def cmd_roast(ctx, *, player_name: str = ""):
    """Roast brutal d'un joueur. !roast Hamza 🔥"""
    if not player_name:
        await ctx.send("Kteb ism: `!roast NomDuJoueur` 🔥"); return
    await ctx.send(f"🔥 Incoming roast dial **{player_name}**...")
    async with ctx.typing():
        raw = await _get_matches(5)
        matches = _parse_all(raw) if raw else []
        text = await gemini.roast(player_name, matches)
    await _send(ctx.channel, text)

@bot.command(name="cheer")
async def cmd_cheer(ctx, *, player_name: str = ""):
    """Célèbre un joueur. !cheer Hamza 👏"""
    if not player_name:
        await ctx.send("Kteb ism: `!cheer NomDuJoueur` 👏"); return
    async with ctx.typing():
        raw = await _get_matches(5)
        matches = _parse_all(raw) if raw else []
        text = await gemini.cheer(player_name, matches)
    await _send(ctx.channel, text)

@bot.command(name="banter")
async def cmd_banter(ctx):
    """Football banter trash talk 😈"""
    async with ctx.typing():
        raw = await _get_matches(1)
        matches = _parse_all(raw) if raw else []
        text = await gemini.banter(matches)
    await ctx.send(text)

@bot.command(name="meme")
async def cmd_meme(ctx):
    """Meme football b Darija 😂"""
    async with ctx.typing():
        raw = await _get_matches(1)
        matches = _parse_all(raw) if raw else []
        text = await gemini.meme_post(matches)
    await ctx.send(text)

@bot.command(name="drama")
async def cmd_drama(ctx):
    """Drama / polémique exagérée 😱"""
    async with ctx.typing():
        raw = await _get_matches(1)
        matches = _parse_all(raw) if raw else []
        text = await gemini.drama_post(matches)
    await ctx.send(text)


# ── NEWS Commands ─────────────────────────────────────────────────────────────

@bot.command(name="transfer")
async def cmd_transfer(ctx):
    """Transfer rumor (humour). !transfer 🚨"""
    async with ctx.typing():
        raw = await _get_matches(5)
        data = await _get_all(1)
        matches = _parse_all(raw) if raw else []
        text = await gemini.transfer_rumor(data.get("members", []), matches)
    await _send(ctx.channel, text)

@bot.command(name="rumour")
async def cmd_rumour(ctx):
    """Alias de !transfer."""
    await cmd_transfer(ctx)

@bot.command(name="rumours")
async def cmd_rumours(ctx):
    """Alias de !transfer."""
    await cmd_transfer(ctx)

@bot.command(name="breaking")
async def cmd_breaking(ctx):
    """Breaking news style. !breaking 📰"""
    async with ctx.typing():
        raw = await _get_matches(1)
        data = await _get_all(1)
        matches = _parse_all(raw) if raw else []
        text = await gemini.breaking_news(matches, data.get("members", []))
    await _send(ctx.channel, text)


# ── ANALYTICS Commands ────────────────────────────────────────────────────────

@bot.command(name="stats")
async def cmd_stats(ctx):
    """Stats saison complète du club."""
    async with ctx.typing():
        data = await _get_all(1)
    s = data.get("club_stats") or {}
    i = data.get("club_info") or {}
    name = i.get("name", "Rachad L3ERGONI")
    wr = "?"
    try:
        w, t, l = int(s.get("wins",0)), int(s.get("ties",0)), int(s.get("losses",0))
        total = w + t + l
        wr = f"{w/total*100:.1f}%" if total else "?"
    except:
        pass
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
        f"🔗 proclubstracker.com/club/{ea_api.CLUB_ID}?platform=common-gen5",
    ]
    await ctx.send("\n".join(lines))

@bot.command(name="insights")
async def cmd_insights(ctx):
    """Insights analytiques sur les 5 derniers matchs."""
    async with ctx.typing():
        raw = await _get_matches(5)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        matches = _parse_all(raw)
        text = await gemini.insights(matches)
    await _send(ctx.channel, text)

@bot.command(name="trends")
async def cmd_trends(ctx):
    """Tendances et patterns de jeu."""
    async with ctx.typing():
        raw = await _get_matches(10)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        matches = _parse_all(raw)
        text = await gemini.trends(matches)
    await _send(ctx.channel, text)

@bot.command(name="stat")
async def cmd_stat(ctx):
    """Stat du jour."""
    async with ctx.typing():
        raw = await _get_matches(5)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        matches = _parse_all(raw)
        text = await gemini.stat_of_day(matches)
    await _send(ctx.channel, text)

@bot.command(name="spotlight")
async def cmd_spotlight(ctx, *, player_name: str = ""):
    """Spotlight d'un joueur. !spotlight [nom]"""
    async with ctx.typing():
        raw = await _get_matches(5)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        matches = _parse_all(raw)
        text = await gemini.player_spotlight(player_name, matches)
    await _send(ctx.channel, text)

@bot.command(name="predict")
async def cmd_predict(ctx, *, opponent: str = "Prochain adversaire"):
    """Prediction du prochain match. !predict NomAdversaire"""
    async with ctx.typing():
        raw = await _get_matches(5)
        matches = _parse_all(raw) if raw else []
        text = await gemini.match_prediction(opponent, matches)
    await _send(ctx.channel, text)

@bot.command(name="clubinfo")
async def cmd_clubinfo(ctx):
    """Info du club."""
    async with ctx.typing():
        data = await _get_all(1)
    info = data.get("club_info") or {}
    lines = [
        f"🏟️ **{info.get('name','Rachad L3ERGONI')}**",
        f"🎮 Platform: **{ea_api.PLATFORM}**",
        f"🔗 proclubstracker.com/club/{ea_api.CLUB_ID}?platform=common-gen5",
    ]
    await ctx.send("\n".join(lines))


# ── ADMIN Commands ────────────────────────────────────────────────────────────

@bot.command(name="setchannel")
@commands.has_permissions(manage_channels=True)
async def cmd_setchannel(ctx, channel_type: str = "match"):
    global _match_channel_id, _general_channel_id
    if channel_type == "match":
        _match_channel_id = ctx.channel.id
        await ctx.send(f"✅ Match channel set! Auto-check kol {MATCH_CHECK_HOURS}h 🔔")
    elif channel_type == "general":
        _general_channel_id = ctx.channel.id
        await ctx.send("✅ General channel set! Daily/weekly content ghadi yji hna 📅")
    else:
        await ctx.send("Usage: `!setchannel match` ou `!setchannel general`")

@bot.command(name="weekly")
@commands.has_permissions(manage_channels=True)
async def cmd_weekly(ctx):
    """Déclenche le weekly recap manuellement (admin)."""
    await ctx.send("⏳ Generating weekly recap...")
    async with ctx.typing():
        raw = await _get_matches(5)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴"); return
        matches = _parse_all(raw)
        data = await _get_all(1)
        await _post_five_summary(ctx.channel, matches, data.get("members", []))

@bot.command(name="refreshdata")
@commands.has_permissions(manage_channels=True)
async def cmd_refreshdata(ctx):
    """Force re-fetch des données (ignore cache)."""
    await ctx.send("🔄 Forçage refresh des données...")
    _scraper.invalidate_cache()
    raw = await _get_matches(5, force=True)
    if raw:
        await ctx.send(f"✅ Data refreshed — **{len(raw)}** matchs chargés!")
    else:
        await ctx.send("❌ Refresh failed 😴")

@bot.command(name="ping")
async def cmd_ping(ctx):
    """Test de connexion."""
    cache_age = int(_scraper.cache_age_seconds())
    cache_str = f"{cache_age}s" if cache_age < 3600 else "stale"
    await ctx.send(f"Pong ✅ | Cache: **{cache_str}** | Match check: kol **{MATCH_CHECK_HOURS}h**")


# ── HELP Command ──────────────────────────────────────────────────────────────

@bot.command(name="help", aliases=["pchelp", "commands"])
async def cmd_help(ctx):
    lines = [
        "⚽ **Rachad L3ERGONI Bot** _(Gemini AI · PCT API · Pillow Images)_",
        "══════════════════════════════════════════",
        "",
        "**📋 MATCH** — Résultats & Rapports",
        "`!last5` · `!last10` · `!results` · `!match <1-10>`",
        "`!lastmatch` / `!report` · `!quickreport` · `!schedule`",
        "",
        "**👥 PLAYERS** — Stats & Comparaisons",
        "`!players` · `!player <nom>` · `!form [nom]`",
        "`!topscorer` · `!topassists` · `!mvp` · `!compare <p1> <p2>`",
        "",
        "**🎬 CONTENT** — Posts & Reports",
        "`!motm [1-5]` · `!totw` · `!recap` · `!hype [adversaire]`",
        "`!reaction` · `!rankings` · `!spotlight [nom]`",
        "",
        "**😂 FUN** — Banter & Humour",
        "`!roast <nom>` 🔥 · `!cheer <nom>` 👏 · `!banter` 😈",
        "`!meme` 😂 · `!drama` 😱",
        "",
        "**📰 NEWS** — Rumeurs & Breaking",
        "`!transfer` / `!rumour` 🚨 · `!breaking` 📰",
        "",
        "**📊 ANALYTICS** — Stats & Insights",
        "`!stats` · `!insights` · `!trends` · `!stat` · `!predict <adversaire>`",
        "`!clubinfo`",
        "",
        "**⚙️ ADMIN** _(manage_channels)_",
        "`!setchannel match` · `!setchannel general` · `!weekly` · `!refreshdata`",
        "",
        "_Auto: matchs kol 6h 🔔 · Stat du jour 10h · Spotlight 20h · Weekly Dimanche_",
    ]
    await ctx.send("\n".join(lines))


# ── Slash Commands ────────────────────────────────────────────────────────────

@bot.tree.command(name="ping", description="Test connexion bot")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong ✅ | Cache: {int(_scraper.cache_age_seconds())}s")

@bot.tree.command(name="last5", description="Analyse des 5 derniers matchs")
async def slash_last5(interaction: discord.Interaction):
    await interaction.response.defer()
    raw = await _get_matches(5)
    if not raw:
        await interaction.followup.send("❌ Ma3endnach data 😴"); return
    matches = _parse_all(raw)
    data = await _get_all(1)
    await _post_five_summary(interaction.channel, matches, data.get("members",[]))
    await interaction.followup.send("✅")

@bot.tree.command(name="roast", description="Roast brutal d'un joueur 🔥")
async def slash_roast(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    raw = await _get_matches(5)
    matches = _parse_all(raw) if raw else []
    text = await gemini.roast(player, matches)
    await interaction.followup.send(text[:2000])

@bot.tree.command(name="hype", description="Post de motivation")
async def slash_hype(interaction: discord.Interaction, context: str = ""):
    await interaction.response.defer()
    text = await gemini.hype_post(context)
    await interaction.followup.send(text[:2000])

@bot.tree.command(name="predict", description="Prediction du prochain match")
async def slash_predict(interaction: discord.Interaction, adversaire: str = "Adversaire"):
    await interaction.response.defer()
    raw = await _get_matches(5)
    matches = _parse_all(raw) if raw else []
    text = await gemini.match_prediction(adversaire, matches)
    await interaction.followup.send(text[:2000])

@bot.tree.command(name="stats", description="Stats saison du club")
async def slash_stats(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx_like = type("C", (), {"channel": interaction.channel, "send": interaction.followup.send})()
    await cmd_stats(ctx_like)


# ── Error Handler ─────────────────────────────────────────────────────────────

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Ma3ndekch permission! 🚫")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Naqes argument — `!help` bach tchouf l'usage.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        logger.error("Command error [%s]: %s", ctx.command, error, exc_info=True)
        await ctx.send(f"❌ Error: `{error}`")


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN not set")
    bot.run(TOKEN)
