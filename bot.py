"""
Rachad L3ERGONI Pro Clubs Bot — Humanized Darija Version v5
- Uses human_darija.py for authentic Moroccan human speech
- Realistic typing delays and imperfections
- All AI output is post-processed to feel human
"""
import os
import io
import asyncio
import logging
import time
from typing import Dict, List

import discord
from discord.ext import commands, tasks

import scraper as _scraper
import gemini
import image_gen
import achievements
import roast_engine
from state import load_seen, save_seen
from human_darija import HumanDarija, HumanizedDiscordBot

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("RachadBot")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN not set!")

# ─── CONFIG ───
MATCH_CHANNEL_ID = int(os.environ.get("MATCH_CHANNEL_ID", 0)) or None
POLL_MINUTES = 5
TIMEOUT_MINUTES = 45

# ─── BOT ───
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ─── HUMANIZATION LAYER ───
humanizer = HumanDarija()

seen_matches = set()
_session_active = False
_last_match_id = None
_last_activity_ts = 0.0

# ─── HELPERS ───
def _match_channel():
    return bot.get_channel(MATCH_CHANNEL_ID) if MATCH_CHANNEL_ID else None

async def _send(ch, text="", image=None, filename="image.png", emotion='excitement'):
    """Send with humanization and realistic typing delay."""
    text = (text or "").strip()
    text = text.replace("\\n", "\n")
    if not text and not image:
        return

    # Humanize the text before sending
    if text:
        text = humanizer.humanize(text, emotion=emotion, intensity=0.75)

    # Calculate realistic typing delay
    word_count = len(text.split()) if text else 0
    if word_count <= 3:
        typing_time = random.randint(1, 3)
    elif word_count <= 8:
        typing_time = random.randint(3, 7)
    else:
        typing_time = random.randint(7, 15)

    # Add random "thinking" pause for longer messages
    if len(text) > 100 and random.random() < 0.3:
        typing_time += random.randint(2, 5)

    # Simulate typing
    async with ch.typing():
        await asyncio.sleep(typing_time)

    if image:
        image.seek(0)
        file = discord.File(image, filename=filename)
        await ch.send(text[:1900] or None, file=file)
    else:
        while text:
            chunk, text = text[:2000], text[2000:]
            await ch.send(chunk)

def _result_icon(r: str) -> str:
    return "🟢" if r == "W" else ("🟡" if r == "D" else "🔴")

def _aggregate_stats(matches: List[Dict]) -> Dict:
    """Aggregate player stats across matches."""
    agg = {}
    for m in matches:
        for p in m.get("players", []) or []:
            name = p.get("name", "Unknown")
            if name not in agg:
                agg[name] = {
                    "name": name,
                    "games": 0, "goals": 0, "assists": 0,
                    "shots": 0, "tackles": 0, "tackles_attempted": 0,
                    "interceptions": 0, "passes_attempted": 0, "passes_completed": 0,
                    "ratings": [], "avg_rating": 0.0,
                }
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
        ratings = agg[name]["ratings"]
        agg[name]["avg_rating"] = sum(ratings) / len(ratings) if ratings else 0

    return agg

def _clean_lines(text, max_lines=5):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    return '\n'.join(lines[:max_lines])

# ─── GET MATCHES SAFELY ─────────────────────────────────────────────────────

async def _get_matches(n: int = 5) -> List[Dict]:
    """Get matches safely with error handling."""
    try:
        data = await _scraper.fetch_all(max_matches=n, force=False)
        raw_matches = data.get("matches", [])
        if not raw_matches:
            logger.warning("No matches returned from scraper")
            return []
        return raw_matches
    except Exception as e:
        logger.error(f"Get matches error: {e}")
        return []

async def _get_all_data(n: int = 1) -> Dict:
    """Get all club data safely."""
    try:
        return await _scraper.fetch_all(max_matches=n, force=False)
    except Exception as e:
        logger.error(f"Get all data error: {e}")
        return {}

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION POLLING
# ═══════════════════════════════════════════════════════════════════════════════

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
        logger.info(f"🆕 New match: {mid}")

        await _post_match(_match_channel(), raw)

    except Exception as e:
        logger.error(f"Poll error: {e}")

@poll_matches.before_loop
async def before_poll():
    await bot.wait_until_ready()

async def _start_session(channel):
    global _session_active, _last_activity_ts, _last_match_id

    if _session_active:
        await channel.send("⏳ Session déjà active!")
        return

    try:
        data = await _scraper.fetch_all(max_matches=1, force=False)
        raw_matches = data.get("matches", [])
        if raw_matches:
            raw = raw_matches[0]
            _last_match_id = str(raw.get("match_id", ""))
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

async def _post_match(ch, m):
    """Post match with badges, roast engine, and MOTM photo."""
    try:
        # 1. Match Header
        emoji = _result_icon(m["result"])
        header = f"{emoji} **{m['our_goals']}-{m['opp_goals']}** vs **{m['opp_name']}**"
        await ch.send(header)

        # 2. AllCalculatedRoast: Silent Treatment for boring games
        if roast_engine.is_boring_game(m.get("players", []), m):
            silent = roast_engine.build_silent_treatment(m)
            await _send(ch, silent, emotion='disappointment')
            return

        # 3. AllCalculatedRoast: Achievements & Curses (Crowns)
        if m.get("players"):
            chaos_results = achievements.evaluate_players(m["players"])
            chaos_report = achievements.format_chaos_report(chaos_results)
            if chaos_report:
                await _send(ch, chaos_report, emotion='excitement')

        # 4. AllCalculatedRoast: Position-aware Roast Engine
        if m.get("players"):
            roast_text = roast_engine.build_roast_text(
                roast_engine.get_roast_victims(m["players"]),
                m,
                m["players"]
            )
            if roast_text:
                await _send(ch, roast_text, emotion='laughter')

        # 5. AI Report (Darija) — HUMANIZED
        report = await gemini.match_report(m)
        report = _clean_lines(report, 3)
        await _send(ch, report, emotion='excitement' if m["result"] == "W" else 'disappointment')

        # 6. MOTM with Photo
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
            await _send(ch, motm_text, motm_img, "motm.png", emotion='love')

    except Exception as e:
        logger.error(f"Post error: {e}")
        await ch.send(f"⚠️ Error posting match: {str(e)[:100]}")

# ═══════════════════════════════════════════════════════════════════════════════
# ALL COMMANDS — HUMANIZED
# ═══════════════════════════════════════════════════════════════════════════════

# ─── SESSION ───

@bot.command(name="roast")
async def cmd_roast_session(ctx):
    """Start session monitoring."""
    await _start_session(ctx.channel)

@bot.command(name="stop")
async def cmd_stop(ctx):
    """Stop session monitoring."""
    await _stop_session("manual")

# ─── MATCH COMMANDS ───

@bot.command(name="lastmatch", aliases=["report", "last"])
async def cmd_lastmatch(ctx):
    """Last match report + MOTM photo + roast engine."""
    async with ctx.typing():
        matches = await _get_matches(1)
        if not matches:
            await ctx.send("❌ Ma3endnach match daba 😴")
            return
        await _post_match(ctx.channel, matches[0])

@bot.command(name="match")
async def cmd_match(ctx, index: int = 1):
    """Rapport d'un match spécifique. !match 1 = dernier."""
    if not 1 <= index <= 10:
        await ctx.send("❌ Index bin 1 w 10.")
        return
    async with ctx.typing():
        matches = await _get_matches(10)
        if index > len(matches):
            await ctx.send(f"❌ Ghir {len(matches)} matchs disponibles.")
            return
        await _post_match(ctx.channel, matches[index - 1])

@bot.command(name="last5", aliases=["recap"])
async def cmd_last5(ctx):
    """Analyse des 5 derniers matchs + TOTW + performers + roast leaderboard."""
    await ctx.send("⏳ Kan-load last 5 matchs... 🤖")
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await ctx.send("❌ Ma3endnach matches daba 😴")
            return
        data = await _get_all_data(1)
        members = data.get("members", [])
        await _post_five_summary(ctx.channel, matches, members)

@bot.command(name="last10")
async def cmd_last10(ctx):
    """Analyse des 10 derniers matchs."""
    await ctx.send("⏳ Kan-load last 10 matchs... 🤖")
    async with ctx.typing():
        matches = await _get_matches(10)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
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
            "",
        ]
        for m in matches:
            e = _result_icon(m["result"])
            lines.append(f"{e} {m['date']} — **{m['our_goals']}-{m['opp_goals']}** vs {m['opp_name']}")
        await ctx.send("\n".join(lines[:2000]))

        text = await gemini.form_analysis(matches)
        await _send(ctx.channel, text, emotion='thinking')

@bot.command(name="results")
async def cmd_results(ctx):
    """Tableau des 10 derniers résultats."""
    async with ctx.typing():
        matches = await _get_matches(10)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        lines = ["📋 **RÉSULTATS — Rachad L3ERGONI**", ""]
        for i, m in enumerate(matches, 1):
            e = _result_icon(m["result"])
            lines.append(f"`{i:2}.` {e} `{m['our_goals']}-{m['opp_goals']}` vs **{m['opp_name']}** — {m['date']}")
        await ctx.send("\n".join(lines))

@bot.command(name="quickreport")
async def cmd_quickreport(ctx):
    """Rapport court du dernier match (1-2 lignes)."""
    async with ctx.typing():
        matches = await _get_matches(1)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        text = await gemini.quick_report(matches[0])
        await _send(ctx.channel, text, emotion='excitement' if matches[0]["result"] == "W" else 'disappointment')

@bot.command(name="schedule")
async def cmd_schedule(ctx):
    """Prochains matchs (basé sur la forme récente)."""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        opponents = [m["opp_name"] for m in matches[:3]]
        text = await gemini.match_prediction(", ".join(opponents), matches)
        await _send(ctx.channel, f"🗓️ **Prochains adversaires potentiels:**\n{', '.join(opponents)}\n\n{text}", emotion='thinking')

# ─── PLAYER COMMANDS ───

@bot.command(name="players")
async def cmd_players(ctx):
    """Liste tous les joueurs avec stats saison."""
    async with ctx.typing():
        data = await _get_all_data(1)
        members = data.get("members", [])
        if not members:
            await ctx.send("❌ Ma3endnach données membres 😴")
            return
        lines = ["👥 **SQUAD — Rachad L3ERGONI**", ""]
        for m in sorted(members, key=lambda x: float(x.get("ratingAve", 0) or 0), reverse=True):
            name = m.get("proName") or m.get("name", "?")
            games = m.get("gamesPlayed", 0)
            goals = m.get("goals", 0)
            assists = m.get("assists", 0)
            rating = m.get("ratingAve", "?")
            pos = m.get("favoritePosition", "MID").upper()[:3]
            lines.append(f"**{name}** `{pos}` — {goals}G {assists}A | ⭐ {rating} | {games} matchs")
        await ctx.send("\n".join(lines)[:2000])

@bot.command(name="player")
async def cmd_player(ctx, *, player_name: str = ""):
    """Stats d'un joueur. !player Hamza"""
    if not player_name:
        await ctx.send("Usage: `!player NomJoueur`")
        return
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        agg = _aggregate_stats(matches)
        key = next((k for k in agg if player_name.lower() in k.lower()), None)
        if not key:
            await ctx.send(f"❌ **{player_name}** — ma3endnach stats f les derniers matchs.\nTry: `!players` bach tchouf l'ism exact.")
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

@bot.command(name="form")
async def cmd_form(ctx, *, player_name: str = ""):
    """Analyse de forme. !form → team | !form Hamza → joueur"""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        if player_name:
            text = await gemini.player_form(player_name, matches)
            await _send(ctx.channel, text, emotion='thinking')
        else:
            text = await gemini.form_analysis(matches)
            await _send(ctx.channel, text, emotion='thinking')

@bot.command(name="topscorer")
async def cmd_topscorer(ctx):
    """Classement des meilleurs buteurs."""
    async with ctx.typing():
        matches = await _get_matches(5)
        data = await _get_all_data(1)
        text = await gemini.top_scorer_post(matches, data.get("members", []))
    await _send(ctx.channel, text, emotion='excitement')

@bot.command(name="topassists")
async def cmd_topassists(ctx):
    """Classement des meilleurs assisteurs."""
    async with ctx.typing():
        matches = await _get_matches(5)
        data = await _get_all_data(1)
        text = await gemini.top_assists_post(matches, data.get("members", []))
    await _send(ctx.channel, text, emotion='excitement')

@bot.command(name="mvp")
async def cmd_mvp(ctx):
    """MVP des 5 derniers matchs avec photo."""
    async with ctx.typing():
        matches = await _get_matches(5)
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
        await _send(ctx.channel, text, mvp_img, "mvp.png", emotion='love')

@bot.command(name="compare")
async def cmd_compare(ctx, player1: str = "", *, player2: str = ""):
    """Compare 2 joueurs. !compare Hamza Karim"""
    if not player1 or not player2:
        await ctx.send("Usage: `!compare Joueur1 Joueur2`")
        return
    await ctx.send(f"⚔️ **{player1}** vs **{player2}**...")
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        result = await gemini.compare_players(player1, player2, matches)
        if isinstance(result, str):
            await _send(ctx.channel, result, emotion='laughter')
            return
        text, s1, s2 = result
        loop = asyncio.get_event_loop()
        card_buf = await loop.run_in_executor(None, lambda: image_gen.make_comparison_card(s1, s2))
    await _send(ctx.channel, text, card_buf, f"compare_{player1}_{player2}.png", emotion='excitement')

# ─── CONTENT COMMANDS — HUMANIZED ───

@bot.command(name="motm")
async def cmd_motm(ctx, match_index: int = 1):
    """Man of the Match. !motm [1-5]"""
    async with ctx.typing():
        matches = await _get_matches(match_index)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        m = matches[match_index - 1]
        if not m.get("players"):
            await ctx.send("❌ Bla stats joueurs pour ce match.")
            return
        best = m["players"][0]
        loop = asyncio.get_event_loop()
        motm_text, motm_buf = await asyncio.gather(
            gemini.motm_post(m),
            loop.run_in_executor(None, lambda: image_gen.make_motm_card(
                best["name"], best["rating"], best["goals"], best["assists"],
                f"vs {m['opp_name']} ({m['our_goals']}-{m['opp_goals']})"
            )),
        )
    await _send(ctx.channel, motm_text or "", motm_buf, "motm.png", emotion='love')

@bot.command(name="totw")
async def cmd_totw(ctx):
    """Team of the Week avec image."""
    await ctx.send("⏳ Building TOTW...")
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        loop = asyncio.get_event_loop()
        totw_text, totw_players = await gemini.team_of_the_week(matches)
        totw_img = await loop.run_in_executor(None, lambda: image_gen.make_totw_card(totw_players))
    await _send(ctx.channel, totw_text, totw_img, "totw.png", emotion='excitement')

@bot.command(name="hype")
async def cmd_hype(ctx, *, context: str = ""):
    """Post de motivation. !hype [adversaire]"""
    async with ctx.typing():
        text = await gemini.hype_post(context)
    await _send(ctx.channel, text, emotion='excitement')

@bot.command(name="reaction")
async def cmd_reaction(ctx):
    """Réaction courte sur le dernier match."""
    async with ctx.typing():
        matches = await _get_matches(1)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        text = await gemini.reaction_post(matches[0])
    await _send(ctx.channel, text, emotion='excitement' if matches[0]["result"] == "W" else 'disappointment')

@bot.command(name="rankings")
async def cmd_rankings(ctx):
    """Top performers des 5 derniers matchs."""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        data = await _get_all_data(1)
        text = await gemini.top_performers(matches, data.get("members", []))
    await _send(ctx.channel, text, emotion='excitement')

@bot.command(name="spotlight")
async def cmd_spotlight(ctx, *, player_name: str = ""):
    """Spotlight d'un joueur. !spotlight [nom]"""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        text = await gemini.player_spotlight(player_name, matches)
    await _send(ctx.channel, text, emotion='love')

# ─── FUN COMMANDS — HUMANIZED ───

@bot.command(name="roastplayer")
async def cmd_roast(ctx, *, player_name: str = ""):
    """Roast brutal d'un joueur. !roastplayer Hamza 🔥"""
    if not player_name:
        await ctx.send("Kteb ism: `!roastplayer NomDuJoueur` 🔥")
        return
    await ctx.send(f"🔥 Incoming roast dial **{player_name}**...")
    async with ctx.typing():
        matches = await _get_matches(5)
        text = await gemini.roast(player_name, matches)
        text = _clean_lines(text, 4)
    await _send(ctx.channel, text, emotion='laughter')

@bot.command(name="cheer")
async def cmd_cheer(ctx, *, player_name: str = ""):
    """Célèbre un joueur. !cheer Hamza 👏"""
    if not player_name:
        await ctx.send("Kteb ism: `!cheer NomDuJoueur` 👏")
        return
    async with ctx.typing():
        matches = await _get_matches(5)
        text = await gemini.cheer(player_name, matches)
    await _send(ctx.channel, text, emotion='love')

@bot.command(name="banter")
async def cmd_banter(ctx):
    """Football banter trash talk 😈"""
    async with ctx.typing():
        matches = await _get_matches(1)
        text = await gemini.banter(matches)
    await _send(ctx.channel, text, emotion='laughter')

@bot.command(name="meme")
async def cmd_meme(ctx):
    """Meme football b Darija 😂"""
    async with ctx.typing():
        matches = await _get_matches(1)
        text = await gemini.meme_post(matches)
    await _send(ctx.channel, text, emotion='laughter')

@bot.command(name="drama")
async def cmd_drama(ctx):
    """Drama / polémique exagérée 😱"""
    async with ctx.typing():
        matches = await _get_matches(1)
        text = await gemini.drama_post(matches)
    await _send(ctx.channel, text, emotion='disappointment')

# ─── ALLCALCULATEDROAST FEATURES ───

@bot.command(name="roastreport")
async def cmd_roastreport(ctx):
    """AllCalculatedRoast: Full pundit roast report for last match."""
    async with ctx.typing():
        matches = await _get_matches(1)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        m = matches[0]

        if roast_engine.is_boring_game(m.get("players", []), m):
            await _send(ctx.channel, roast_engine.build_silent_treatment(m), emotion='disappointment')
            return

        roast_text = roast_engine.build_roast_text(
            roast_engine.get_roast_victims(m.get("players", [])),
            m,
            m.get("players", [])
        )
        if roast_text:
            await _send(ctx.channel, roast_text, emotion='laughter')
        else:
            await ctx.send("✅ Kolchi mzyan f had match — bla roast! 🔥")

@bot.command(name="crowns")
async def cmd_crowns(ctx):
    """AllCalculatedRoast: Show crown leaderboard."""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return

        all_crowns = {}
        for m in matches:
            if m.get("players"):
                results = achievements.evaluate_players(m["players"])
                crowns = achievements.count_crowns(results)
                for name, count in crowns.items():
                    all_crowns[name] = all_crowns.get(name, 0) + count

        if not all_crowns:
            await ctx.send("🏆 **Crown Leaderboard**\n\nGhir klach 💀 — ma3endnach crowns daba!")
            return

        sorted_crowns = sorted(all_crowns.items(), key=lambda x: x[1], reverse=True)
        lines = ["🏆 **CROWN LEADERBOARD**", ""]
        for i, (name, count) in enumerate(sorted_crowns, 1):
            medal = "👑" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅"
            lines.append(f"{medal} **{name}** — {count} crown{'s' if count > 1 else ''}")

        await ctx.send("\n".join(lines))

@bot.command(name="curses")
async def cmd_curses(ctx):
    """AllCalculatedRoast: Show curse leaderboard."""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return

        all_curses = {}
        for m in matches:
            if m.get("players"):
                results = achievements.evaluate_players(m["players"])
                curses = achievements.count_curses(results)
                for name, count in curses.items():
                    all_curses[name] = all_curses.get(name, 0) + count

        if not all_curses:
            await ctx.send("💀 **Curse Leaderboard**\n\nMashi 7ed m3lih curse — kolchi mzyan!")
            return

        sorted_curses = sorted(all_curses.items(), key=lambda x: x[1], reverse=True)
        lines = ["💀 **CURSE LEADERBOARD**", ""]
        for i, (name, count) in enumerate(sorted_curses, 1):
            emoji = "😈" if i == 1 else "👻" if i == 2 else "🧱" if i == 3 else "💀"
            lines.append(f"{emoji} **{name}** — {count} curse{'s' if count > 1 else ''}")

        await ctx.send("\n".join(lines))

@bot.command(name="funroast")
async def cmd_funroast(ctx, *, player_name: str = ""):
    """AllCalculatedRoast: Fun lifetime roast. !funroast Hamza"""
    if not player_name:
        await ctx.send("Usage: `!funroast NomDuJoueur`")
        return

    async with ctx.typing():
        matches = await _get_matches(10)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return

        agg = _aggregate_stats(matches)
        key = next((k for k in agg if player_name.lower() in k.lower()), None)
        if not key:
            await ctx.send(f"❌ **{player_name}** — ma3endnach stats.")
            return

        s = agg[key]
        stats = {
            "matches": s["games"],
            "goals": s["goals"],
            "assists": s["assists"],
            "rating_total": s["avg_rating"] * s["games"],
        }
        roast = roast_engine.get_fun_roast(s["name"], stats)
        await _send(ctx.channel, roast, emotion='laughter')

# ─── NEWS COMMANDS — HUMANIZED ───

@bot.command(name="transfer", aliases=["rumour", "rumours"])
async def cmd_transfer(ctx):
    """Transfer rumor (humour). !transfer 🚨"""
    async with ctx.typing():
        matches = await _get_matches(5)
        data = await _get_all_data(1)
        text = await gemini.transfer_rumor(data.get("members", []), matches)
    await _send(ctx.channel, text, emotion='excitement')

@bot.command(name="breaking")
async def cmd_breaking(ctx):
    """Breaking news style. !breaking 📰"""
    async with ctx.typing():
        matches = await _get_matches(1)
        data = await _get_all_data(1)
        text = await gemini.breaking_news(matches, data.get("members", []))
    await _send(ctx.channel, text, emotion='disappointment')

# ─── ANALYTICS COMMANDS — HUMANIZED ───

@bot.command(name="stats")
async def cmd_stats(ctx):
    """Stats saison complète du club."""
    async with ctx.typing():
        data = await _get_all_data(1)
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

@bot.command(name="insights")
async def cmd_insights(ctx):
    """Insights analytiques sur les 5 derniers matchs."""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        text = await gemini.insights(matches)
    await _send(ctx.channel, text, emotion='thinking')

@bot.command(name="trends")
async def cmd_trends(ctx):
    """Tendances et patterns de jeu."""
    async with ctx.typing():
        matches = await _get_matches(10)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        text = await gemini.trends(matches)
    await _send(ctx.channel, text, emotion='thinking')

@bot.command(name="stat")
async def cmd_stat(ctx):
    """Stat du jour."""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        text = await gemini.stat_of_day(matches)
    await _send(ctx.channel, text, emotion='excitement')

@bot.command(name="predict")
async def cmd_predict(ctx, *, opponent: str = "Prochain adversaire"):
    """Prediction du prochain match. !predict NomAdversaire"""
    async with ctx.typing():
        matches = await _get_matches(5)
        text = await gemini.match_prediction(opponent, matches)
    await _send(ctx.channel, text, emotion='thinking')

@bot.command(name="clubinfo")
async def cmd_clubinfo(ctx):
    """Info du club."""
    async with ctx.typing():
        data = await _get_all_data(1)
    info = data.get("club_info") or {}
    lines = [
        f"🏟️ **{info.get('name','Rachad L3ERGONI')}**",
        f"🎮 Platform: **common-gen5**",
        f"🔗 proclubstracker.com/club/1427607?platform=common-gen5",
    ]
    await ctx.send("\n".join(lines))

# ─── ADMIN COMMANDS ───

@bot.command(name="setchannel")
@commands.has_permissions(manage_channels=True)
async def cmd_setchannel(ctx, channel_type: str = "match"):
    global MATCH_CHANNEL_ID
    if channel_type == "match":
        MATCH_CHANNEL_ID = ctx.channel.id
        await ctx.send(f"✅ Match channel set! Auto-check kol {POLL_MINUTES}h 🔔")
    elif channel_type == "general":
        await ctx.send("✅ General channel set! 📅")
    else:
        await ctx.send("Usage: `!setchannel match` ou `!setchannel general`")

@bot.command(name="weekly")
@commands.has_permissions(manage_channels=True)
async def cmd_weekly(ctx):
    """Déclenche le weekly recap manuellement (admin)."""
    await ctx.send("⏳ Generating weekly recap...")
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        data = await _get_all_data(1)
        await _post_five_summary(ctx.channel, matches, data.get("members", []))

@bot.command(name="refreshdata")
@commands.has_permissions(manage_channels=True)
async def cmd_refreshdata(ctx):
    """Force re-fetch des données (ignore cache)."""
    await ctx.send("🔄 Forçage refresh des données...")
    _scraper.invalidate_cache()
    matches = await _get_matches(5)
    if matches:
        await ctx.send(f"✅ Data refreshed — **{len(matches)}** matchs chargés!")
    else:
        await ctx.send("❌ Refresh failed 😴")

@bot.command(name="ping")
async def cmd_ping(ctx):
    """Test de connexion."""
    cache_age = int(_scraper.cache_age_seconds())
    cache_str = f"{cache_age}s" if cache_age < 3600 else "stale"
    await ctx.send(f"Pong ✅ | Cache: **{cache_str}** | Check: kol **{POLL_MINUTES}min**")

# ─── HELP ───

@bot.command(name="help", aliases=["pchelp", "commands"])
async def cmd_help(ctx):
    lines = [
        "⚽ **Rachad L3ERGONI Bot** _(Humanized Darija · PCT API · Pillow Images · AllCalculatedRoast)_",
        "══════════════════════════════════════════",
        "",
        "**🎮 SESSION**",
        "`!roast` — Start session monitoring (checks every 5 min)",
        "`!stop` — Stop session monitoring",
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
        "`!motm [1-5]` · `!totw` · `!hype [adversaire]`",
        "`!reaction` · `!rankings` · `!spotlight [nom]`",
        "",
        "**🔥 ALLCALCULATEDROAST** — Gamification",
        "`!roastreport` — Full pundit roast (position-aware)",
        "`!crowns` — Crown leaderboard (achievements)",
        "`!curses` — Curse leaderboard",
        "`!funroast <nom>` — Lifetime fun roast",
        "",
        "**😂 FUN** — Banter & Humour",
        "`!roastplayer <nom>` 🔥 · `!cheer <nom>` 👏 · `!banter` 😈",
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
        "_Auto: matchs kol 5min 🔔 · Session: 45min timeout · Humanized Darija 100%_",
    ]
    await ctx.send("\n".join(lines))

# ─── INTERNAL HELPERS ───

async def _post_five_summary(channel, matches: list, members: list):
    """5-match summary with parallel AI + images + AllCalculatedRoast leaderboards."""
    loop = asyncio.get_event_loop()

    summary_t = asyncio.create_task(gemini.five_match_summary(matches))
    performers_t = asyncio.create_task(gemini.top_performers(matches, members))
    totw_t = asyncio.create_task(gemini.team_of_the_week(matches))

    results_data = [
        {"opponent": m["opp_name"], "our_goals": m["our_goals"],
         "opp_goals": m["opp_goals"], "date": m["date"]}
        for m in matches
    ]
    summary_img = await loop.run_in_executor(
        None, lambda: image_gen.make_five_match_summary(results_data)
    )

    summary_text, performers_text, (totw_text, totw_players) = await asyncio.gather(
        summary_t, performers_t, totw_t
    )
    totw_img = await loop.run_in_executor(None, lambda: image_gen.make_totw_card(totw_players))

    await _send(channel, summary_text, summary_img, "last5.png", emotion='excitement')
    await asyncio.sleep(1)
    await _send(channel, performers_text, emotion='excitement')
    await asyncio.sleep(1)
    await _send(channel, totw_text, totw_img, "totw.png", emotion='excitement')

    # AllCalculatedRoast: Crown/Curse leaderboard
    all_crowns = {}
    all_curses = {}
    for m in matches:
        if m.get("players"):
            results = achievements.evaluate_players(m["players"])
            crowns = achievements.count_crowns(results)
            curses = achievements.count_curses(results)
            for name, count in crowns.items():
                all_crowns[name] = all_crowns.get(name, 0) + count
            for name, count in curses.items():
                all_curses[name] = all_curses.get(name, 0) + count

    if all_crowns or all_curses:
        lines = ["🏆 **Gamification Recap**", ""]
        if all_crowns:
            sorted_crowns = sorted(all_crowns.items(), key=lambda x: x[1], reverse=True)[:3]
            lines.append("👑 **Crowns:**")
            for name, count in sorted_crowns:
                lines.append(f"  {name}: {count} crown{'s' if count > 1 else ''}")
            lines.append("")
        if all_curses:
            sorted_curses = sorted(all_curses.items(), key=lambda x: x[1], reverse=True)[:3]
            lines.append("💀 **Curses:**")
            for name, count in sorted_curses:
                lines.append(f"  {name}: {count} curse{'s' if count > 1 else ''}")
        await channel.send("\n".join(lines))

# ─── EVENTS ───

@bot.event
async def on_ready():
    global seen_matches
    seen_matches = load_seen()
    logger.info(f"✅ Bot ready: {bot.user}")
    logger.info(f"   Session poll: every {POLL_MINUTES}min | Timeout: {TIMEOUT_MINUTES}min")
    logger.info(f"   Humanization: ENABLED — Darija street style with typing delays")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="your matches 👀"))

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.content:
        logger.info("[MSG] #%s | %s: %s",
                    getattr(message.channel, "name", "DM"),
                    message.author.name, message.content[:80])
    await bot.process_commands(message)

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
        await ctx.send(f"❌ Error: `{str(error)[:100]}`")

# ─── HEALTH SERVER (for Render deployment) ───
import aiohttp
from aiohttp import web

async def health_handler(request):
    return web.Response(text="Rachad L3ERGONI OK")

async def start_health_server():
    """Start aiohttp health server — Render detects this port."""
    port = int(os.environ.get("PORT", 10000))
    app = web.Application()
    app.router.add_get("/", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"✅ Health server bound to port {port}")
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
