"""
Rachad L3ERGONI Pro Clubs Bot — v6 (Pro Social Media Manager)
- Short, punchy Darija with clean French/English code-switching
- Anime-style stats cards (anime_image_gen)
- Real squad integration (squad.json)
- AllCalculatedRoast with position-aware roasts
- Realistic typing delays (1-7s max)
"""
import os
import io
import asyncio
import random
import logging
import time
import re
from typing import Dict, List

import discord
from discord.ext import commands, tasks

import scraper as _scraper
import gemini
import achievements
import roast_engine
from state import load_seen, save_seen
from human_darija import HumanDarija, HumanizedDiscordBot
import anime_image_gen as image_gen

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

async def _send(ch, text="", image=None, filename="image.png", emotion='thinking'):
    """Send with humanization and realistic typing delay."""
    text = (text or "").strip()
    text = text.replace("\n", "
")
    if not text and not image:
        return

    # Humanize the text before sending — SHORT, PRO STYLE
    if text:
        text = humanizer.humanize(text, emotion=emotion, intensity=0.6)

    # Calculate realistic typing delay — SHORTER for pro style
    word_count = len(text.split()) if text else 0
    if word_count <= 5:
        typing_time = random.randint(1, 2)
    elif word_count <= 12:
        typing_time = random.randint(2, 4)
    else:
        typing_time = random.randint(4, 7)

    # Brief "thinking" pause for longer messages
    if len(text) > 80 and random.random() < 0.2:
        typing_time += random.randint(1, 2)

    # Simulate typing
    async with ch.typing():
        await asyncio.sleep(typing_time)

    if image:
        image.seek(0)
        file = discord.File(image, filename=filename)
        await ch.send(text[:1900] or None, file=file)
    else:
        if len(text) <= 2000:
            await ch.send(text)
        else:
            # Split at sentence boundaries
            sentences = re.split(r"([.!?]+)", text)
            chunks = []
            current = ""
            for s in sentences:
                if len(current) + len(s) < 1900:
                    current += s
                else:
                    if current:
                        chunks.append(current.strip())
                    current = s
            if current:
                chunks.append(current.strip())

            for i, chunk in enumerate(chunks):
                await ch.send(chunk)
                if i < len(chunks) - 1:
                    await asyncio.sleep(random.randint(1, 2))

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

def _clean_lines(text, max_lines=3):
    """Keep only max_lines lines, clean and short."""
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
        await _send(channel, "Session déjà active!", emotion='disappointment')
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

    await _send(channel,
        f"Session démarrée! Check kol {POLL_MINUTES}min. Auto-stop après {TIMEOUT_MINUTES}min. !stop bach t7bss.",
        emotion='excitement')

async def _stop_session(reason="manual"):
    global _session_active
    _session_active = False
    if poll_matches.is_running():
        poll_matches.stop()

    ch = _match_channel()
    if not ch:
        return

    if reason == "timeout":
        await _send(ch,
            f"Session terminée. {TIMEOUT_MINUTES}min bla match. !roast quand tu rejoues!",
            emotion='disappointment')
    else:
        await _send(ch, "Session arrêtée. Safi.", emotion='thinking')

async def _post_match(ch, m):
    """Post match with short phrases, anime cards, and AllCalculatedRoast."""
    try:
        # 1. Match Header — SHORT
        emoji = _result_icon(m["result"])
        header = f"{emoji} **{m['our_goals']}-{m['opp_goals']}** vs **{m['opp_name']}**"
        await ch.send(header)

        # 2. AllCalculatedRoast: Silent Treatment for boring games
        if roast_engine.is_boring_game(m.get("players", []), m):
            silent = roast_engine.build_silent_treatment(m)
            await _send(ch, silent, emotion='disappointment')
            return

        # 3. AllCalculatedRoast: Achievements & Curses (Crowns) — SHORT
        if m.get("players"):
            chaos_results = achievements.evaluate_players(m["players"])
            chaos_report = achievements.format_chaos_report(chaos_results)
            if chaos_report:
                # Shorten to 2 lines max
                chaos_report = _clean_lines(chaos_report, 2)
                await _send(ch, chaos_report, emotion='excitement')

        # 4. AllCalculatedRoast: Position-aware Roast — SHORT
        if m.get("players"):
            roast_text = roast_engine.build_roast_text(
                roast_engine.get_roast_victims(m["players"]),
                m,
                m["players"]
            )
            if roast_text:
                roast_text = _clean_lines(roast_text, 2)
                await _send(ch, roast_text, emotion='laughter')

        # 5. AI Report (Darija) — SHORTENED TO 2 LINES
        report = await gemini.match_report(m)
        report = _clean_lines(report, 2)
        emotion = 'excitement' if m["result"] == "W" else 'disappointment'
        await _send(ch, report, emotion=emotion)

        # 6. MOTM with ANIME card
        if m.get("players"):
            best = m["players"][0]
            motm_text = humanizer.get_motm(best["name"], best["rating"], best["goals"], best["assists"])

            # Get player image path from squad
            player_data = humanizer.get_player(best["name"])
            img_path = player_data.get("image") if player_data else None

            loop = asyncio.get_event_loop()
            motm_img = await loop.run_in_executor(
                None,
                image_gen.make_motm_card,
                best["name"], best["rating"], best["goals"], best["assists"],
                f"vs {m['opp_name']}",
                img_path
            )
            await _send(ch, motm_text, motm_img, "motm.png", emotion='love')

    except Exception as e:
        logger.error(f"Post error: {e}")
        await ch.send(f"⚠️ Error: {str(e)[:100]}")

# ═══════════════════════════════════════════════════════════════════════════════
# ALL COMMANDS — HUMANIZED, SHORT, PRO
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

# ─── MATCH COMMANDS — SHORT OUTPUT ───

@bot.command(name="lastmatch", aliases=["report", "last"])
async def cmd_lastmatch(ctx):
    """Last match report + MOTM anime card + roast."""
    async with ctx.typing():
        matches = await _get_matches(1)
        if not matches:
            await _send(ctx.channel, "Ma3endnach match daba. Walo.", emotion='disappointment')
            return
        await _post_match(ctx.channel, matches[0])

@bot.command(name="match")
async def cmd_match(ctx, index: int = 1):
    """Match spécifique. !match 1 = dernier."""
    if not 1 <= index <= 10:
        await _send(ctx.channel, "Ghir 1-10. Z3ma...", emotion='thinking')
        return
    async with ctx.typing():
        matches = await _get_matches(10)
        if index > len(matches):
            await _send(ctx.channel, f"Ghir {len(matches)} matchs. Walo.", emotion='disappointment')
            return
        await _post_match(ctx.channel, matches[index - 1])

@bot.command(name="last5", aliases=["recap"])
async def cmd_last5(ctx):
    """5 derniers matchs + TOTW + performers."""
    await _send(ctx.channel, "Kan-load last 5...", emotion='thinking')
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach matches. Walo.", emotion='disappointment')
            return
        data = await _get_all_data(1)
        members = data.get("members", [])
        await _post_five_summary(ctx.channel, matches, members)

@bot.command(name="last10")
async def cmd_last10(ctx):
    """10 derniers matchs — SHORT recap."""
    await _send(ctx.channel, "Kan-load last 10...", emotion='thinking')
    async with ctx.typing():
        matches = await _get_matches(10)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        wins = sum(1 for m in matches if m["result"] == "W")
        draws = sum(1 for m in matches if m["result"] == "D")
        losses = sum(1 for m in matches if m["result"] == "L")
        gf = sum(m["our_goals"] for m in matches)
        ga = sum(m["opp_goals"] for m in matches)
        form = "".join(m["result"] for m in matches[:10])

        # SHORT summary — one block
        lines = [
            f"📊 LAST 10 — W:{wins} D:{draws} L:{losses} | {gf}-{ga} | Form: {form}",
            "",
        ]
        for m in matches:
            e = _result_icon(m["result"])
            lines.append(f"{e} {m['date']} — {m['our_goals']}-{m['opp_goals']} vs {m['opp_name']}")
        await ctx.send("\n".join(lines[:2000]))

        # AI analysis — SHORTENED
        text = await gemini.form_analysis(matches)
        text = _clean_lines(text, 2)
        await _send(ctx.channel, text, emotion='thinking')

@bot.command(name="results")
async def cmd_results(ctx):
    """Tableau résultats — SHORT."""
    async with ctx.typing():
        matches = await _get_matches(10)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        lines = ["📋 RÉSULTATS — Rachad L3ERGONI", ""]
        for i, m in enumerate(matches, 1):
            e = _result_icon(m["result"])
            lines.append(f"`{i:2}.` {e} `{m['our_goals']}-{m['opp_goals']}` vs **{m['opp_name']}** — {m['date']}")
        await ctx.send("\n".join(lines))

@bot.command(name="quickreport")
async def cmd_quickreport(ctx):
    """Rapport court — 1-2 lignes max."""
    async with ctx.typing():
        matches = await _get_matches(1)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        text = await gemini.quick_report(matches[0])
        text = _clean_lines(text, 2)
        emotion = 'excitement' if matches[0]["result"] == "W" else 'disappointment'
        await _send(ctx.channel, text, emotion=emotion)

@bot.command(name="schedule")
async def cmd_schedule(ctx):
    """Prochains adversaires — SHORT."""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        opponents = [m["opp_name"] for m in matches[:3]]
        text = await gemini.match_prediction(", ".join(opponents), matches)
        text = _clean_lines(text, 2)
        await _send(ctx.channel, f"Prochains: {', '.join(opponents)}\n\n{text}", emotion='thinking')

# ─── PLAYER COMMANDS — SHORT & ANIME CARDS ───

@bot.command(name="players")
async def cmd_players(ctx):
    """Liste squad — compact."""
    async with ctx.typing():
        data = await _get_all_data(1)
        members = data.get("members", [])
        if not members:
            await _send(ctx.channel, "Ma3endnach données membres. Walo.", emotion='disappointment')
            return
        lines = ["👥 SQUAD — Rachad L3ERGONI", ""]
        for m in sorted(members, key=lambda x: float(x.get("ratingAve", 0) or 0), reverse=True):
            name = m.get("proName") or m.get("name", "?")
            games = m.get("gamesPlayed", 0)
            goals = m.get("goals", 0)
            assists = m.get("assists", 0)
            rating = m.get("ratingAve", "?")
            pos = m.get("favoritePosition", "MID").upper()[:3]
            lines.append(f"**{name}** `{pos}` — {goals}G {assists}A | ⭐{rating} | {games}m")
        await ctx.send("\n".join(lines)[:2000])

@bot.command(name="player")
async def cmd_player(ctx, *, player_name: str = ""):
    """Stats joueur + ANIME card. !player Hamza"""
    if not player_name:
        await _send(ctx.channel, "Usage: !player Nom", emotion='thinking')
        return
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        agg = _aggregate_stats(matches)
        key = next((k for k in agg if player_name.lower() in k.lower()), None)
        if not key:
            await _send(ctx.channel, f"{player_name}? Ma3endnach stats. !players bach tchouf.", emotion='thinking')
            return
        s = agg[key]

        # Get player data for anime card
        player_data = humanizer.get_player(player_name)
        position = player_data.get("position", "MID") if player_data else "MID"
        img_path = player_data.get("image") if player_data else None

        # Short text
        lines = [
            f"👤 **{s['name']}** — 5 derniers matchs",
            f"🎮 {s['games']}m | ⚽{s['goals']}G | 🎯{s['assists']}A | ⭐{s['avg_rating']:.1f}",
        ]
        await ctx.send("\n".join(lines))

        # Anime stats card
        stats_dict = {
            "goals": s["goals"],
            "assists": s["assists"],
            "rating": s["avg_rating"],
            "shots": s["shots"],
            "tackles": s["tackles"],
            "passes_completed": s["passes_completed"],
        }
        loop = asyncio.get_event_loop()
        card_buf = await loop.run_in_executor(
            None,
            image_gen.make_player_stats_card,
            s["name"], stats_dict, position, img_path
        )
        await _send(ctx.channel, "", card_buf, f"{s['name']}_stats.png", emotion='excitement')

@bot.command(name="form")
async def cmd_form(ctx, *, player_name: str = ""):
    """Forme — SHORT. !form → team | !form Hamza → joueur"""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        if player_name:
            text = await gemini.player_form(player_name, matches)
            text = _clean_lines(text, 2)
            await _send(ctx.channel, text, emotion='thinking')
        else:
            text = await gemini.form_analysis(matches)
            text = _clean_lines(text, 2)
            await _send(ctx.channel, text, emotion='thinking')

@bot.command(name="topscorer")
async def cmd_topscorer(ctx):
    """Top buteurs — SHORT."""
    async with ctx.typing():
        matches = await _get_matches(5)
        data = await _get_all_data(1)
        text = await gemini.top_scorer_post(matches, data.get("members", []))
        text = _clean_lines(text, 3)
    await _send(ctx.channel, text, emotion='excitement')

@bot.command(name="topassists")
async def cmd_topassists(ctx):
    """Top assists — SHORT."""
    async with ctx.typing():
        matches = await _get_matches(5)
        data = await _get_all_data(1)
        text = await gemini.top_assists_post(matches, data.get("members", []))
        text = _clean_lines(text, 3)
    await _send(ctx.channel, text, emotion='excitement')

@bot.command(name="mvp")
async def cmd_mvp(ctx):
    """MVP 5 matchs + ANIME card."""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        agg = _aggregate_stats(matches)
        if not agg:
            await _send(ctx.channel, "Ma3endnach stats. Walo.", emotion='disappointment')
            return
        mvp = max(agg.values(), key=lambda x: x["avg_rating"] + x["goals"] * 0.5 + x["assists"] * 0.3)

        # Get player image
        player_data = humanizer.get_player(mvp["name"])
        img_path = player_data.get("image") if player_data else None

        # Anime card
        loop = asyncio.get_event_loop()
        mvp_img = await loop.run_in_executor(
            None,
            image_gen.make_motm_card,
            mvp["name"], mvp["avg_rating"], mvp["goals"], mvp["assists"],
            "MVP — Last 5 Matches",
            img_path
        )

        text = f"👑 MVP: {mvp['name']} | {mvp['games']}m | ⚽{mvp['goals']}G | 🎯{mvp['assists']}A | ⭐{mvp['avg_rating']:.1f}"
        await _send(ctx.channel, text, mvp_img, "mvp.png", emotion='love')

@bot.command(name="compare")
async def cmd_compare(ctx, player1: str = "", *, player2: str = ""):
    """Compare 2 joueurs — ANIME 1v1 card. !compare Hamza Karim"""
    if not player1 or not player2:
        await _send(ctx.channel, "Usage: !compare J1 J2", emotion='thinking')
        return
    await _send(ctx.channel, f"{player1} vs {player2}...", emotion='thinking')
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        result = await gemini.compare_players(player1, player2, matches)
        if isinstance(result, str):
            text = _clean_lines(result, 2)
            await _send(ctx.channel, text, emotion='laughter')
            return
        text, s1, s2 = result
        text = _clean_lines(text, 2)

        # Anime comparison card
        loop = asyncio.get_event_loop()
        card_buf = await loop.run_in_executor(None, lambda: image_gen.make_comparison_card(s1, s2))
    await _send(ctx.channel, text, card_buf, f"compare_{player1}_{player2}.png", emotion='excitement')

# ─── CONTENT COMMANDS — SHORT & HUMANIZED ───

@bot.command(name="motm")
async def cmd_motm(ctx, match_index: int = 1):
    """MOTM + ANIME card. !motm [1-5]"""
    async with ctx.typing():
        matches = await _get_matches(match_index)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        m = matches[match_index - 1]
        if not m.get("players"):
            await _send(ctx.channel, "Bla stats joueurs. Walo.", emotion='disappointment')
            return
        best = m["players"][0]

        player_data = humanizer.get_player(best["name"])
        img_path = player_data.get("image") if player_data else None

        loop = asyncio.get_event_loop()
        motm_text, motm_buf = await asyncio.gather(
            gemini.motm_post(m),
            loop.run_in_executor(None, lambda: image_gen.make_motm_card(
                best["name"], best["rating"], best["goals"], best["assists"],
                f"vs {m['opp_name']} ({m['our_goals']}-{m['opp_goals']})",
                img_path
            )),
        )
        motm_text = _clean_lines(motm_text or "", 2)
    await _send(ctx.channel, motm_text, motm_buf, "motm.png", emotion='love')

@bot.command(name="totw")
async def cmd_totw(ctx):
    """TOTW + ANIME card."""
    await _send(ctx.channel, "Building TOTW...", emotion='thinking')
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        loop = asyncio.get_event_loop()
        totw_text, totw_players = await gemini.team_of_the_week(matches)
        totw_text = _clean_lines(totw_text, 2)
        totw_img = await loop.run_in_executor(None, lambda: image_gen.make_totw_card(totw_players))
    await _send(ctx.channel, totw_text, totw_img, "totw.png", emotion='excitement')

@bot.command(name="hype")
async def cmd_hype(ctx, *, context: str = ""):
    """Hype — SHORT. !hype [adversaire]"""
    async with ctx.typing():
        if context:
            text = await gemini.hype_post(context)
            text = _clean_lines(text, 2)
        else:
            text = humanizer.get_hype("L3ERGONI")
    await _send(ctx.channel, text, emotion='excitement')

@bot.command(name="reaction")
async def cmd_reaction(ctx):
    """Réaction courte — 1-2 lignes."""
    async with ctx.typing():
        matches = await _get_matches(1)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        text = await gemini.reaction_post(matches[0])
        text = _clean_lines(text, 2)
    emotion = 'excitement' if matches[0]["result"] == "W" else 'disappointment'
    await _send(ctx.channel, text, emotion=emotion)

@bot.command(name="rankings")
async def cmd_rankings(ctx):
    """Top performers — SHORT."""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        data = await _get_all_data(1)
        text = await gemini.top_performers(matches, data.get("members", []))
        text = _clean_lines(text, 3)
    await _send(ctx.channel, text, emotion='excitement')

@bot.command(name="spotlight")
async def cmd_spotlight(ctx, *, player_name: str = ""):
    """Spotlight joueur — SHORT. !spotlight [nom]"""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        text = await gemini.player_spotlight(player_name, matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion='love')

# ─── FUN COMMANDS — SHORT ROASTS & BANTER ───

@bot.command(name="roastplayer")
async def cmd_roast(ctx, *, player_name: str = ""):
    """Roast brutal — SHORT. !roastplayer Hamza 🔥"""
    if not player_name:
        await _send(ctx.channel, "Kteb ism: !roastplayer Nom", emotion='thinking')
        return

    # Try squad-aware roast first
    player_data = humanizer.get_player(player_name)
    if player_data:
        roast = humanizer.get_roast(player_name)
        await _send(ctx.channel, roast, emotion='laughter')
        return

    await _send(ctx.channel, f"Roast dial {player_name}...", emotion='thinking')
    async with ctx.typing():
        matches = await _get_matches(5)
        text = await gemini.roast(player_name, matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion='laughter')

@bot.command(name="cheer")
async def cmd_cheer(ctx, *, player_name: str = ""):
    """Célèbre joueur — SHORT. !cheer Hamza 👏"""
    if not player_name:
        await _send(ctx.channel, "Kteb ism: !cheer Nom", emotion='thinking')
        return
    async with ctx.typing():
        matches = await _get_matches(5)
        text = await gemini.cheer(player_name, matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion='love')

@bot.command(name="banter")
async def cmd_banter(ctx):
    """Banter — SHORT."""
    async with ctx.typing():
        matches = await _get_matches(1)
        text = await gemini.banter(matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion='laughter')

@bot.command(name="meme")
async def cmd_meme(ctx):
    """Meme — SHORT."""
    async with ctx.typing():
        matches = await _get_matches(1)
        text = await gemini.meme_post(matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion='laughter')

@bot.command(name="drama")
async def cmd_drama(ctx):
    """Drama — SHORT."""
    async with ctx.typing():
        matches = await _get_matches(1)
        text = await gemini.drama_post(matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion='disappointment')

# ─── ALLCALCULATEDROAST — SHORT OUTPUT ───

@bot.command(name="roastreport")
async def cmd_roastreport(ctx):
    """Full roast — SHORTENED."""
    async with ctx.typing():
        matches = await _get_matches(1)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
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
            roast_text = _clean_lines(roast_text, 2)
            await _send(ctx.channel, roast_text, emotion='laughter')
        else:
            await _send(ctx.channel, "Kolchi mzyan. Bla roast! 🔥", emotion='excitement')

@bot.command(name="crowns")
async def cmd_crowns(ctx):
    """Crown leaderboard — compact."""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return

        all_crowns = {}
        for m in matches:
            if m.get("players"):
                results = achievements.evaluate_players(m["players"])
                crowns = achievements.count_crowns(results)
                for name, count in crowns.items():
                    all_crowns[name] = all_crowns.get(name, 0) + count

        if not all_crowns:
            await _send(ctx.channel, "Ghir klach. Ma3endnach crowns. Walo!", emotion='disappointment')
            return

        sorted_crowns = sorted(all_crowns.items(), key=lambda x: x[1], reverse=True)
        lines = ["🏆 CROWNS", ""]
        for i, (name, count) in enumerate(sorted_crowns, 1):
            medal = "👑" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅"
            lines.append(f"{medal} **{name}** — {count}")
        await ctx.send("\n".join(lines))

@bot.command(name="curses")
async def cmd_curses(ctx):
    """Curse leaderboard — compact."""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return

        all_curses = {}
        for m in matches:
            if m.get("players"):
                results = achievements.evaluate_players(m["players"])
                curses = achievements.count_curses(results)
                for name, count in curses.items():
                    all_curses[name] = all_curses.get(name, 0) + count

        if not all_curses:
            await _send(ctx.channel, "Mashi 7ed m3lih curse. Kolchi mzyan!", emotion='excitement')
            return

        sorted_curses = sorted(all_curses.items(), key=lambda x: x[1], reverse=True)
        lines = ["💀 CURSES", ""]
        for i, (name, count) in enumerate(sorted_curses, 1):
            emoji = "😈" if i == 1 else "👻" if i == 2 else "🧱" if i == 3 else "💀"
            lines.append(f"{emoji} **{name}** — {count}")
        await ctx.send("\n".join(lines))

@bot.command(name="funroast")
async def cmd_funroast(ctx, *, player_name: str = ""):
    """Fun lifetime roast — SHORT. !funroast Hamza"""
    if not player_name:
        await _send(ctx.channel, "Usage: !funroast Nom", emotion='thinking')
        return

    # Squad-aware roast first
    player_data = humanizer.get_player(player_name)
    if player_data:
        roast = humanizer.get_roast(player_name)
        await _send(ctx.channel, roast, emotion='laughter')
        return

    async with ctx.typing():
        matches = await _get_matches(10)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return

        agg = _aggregate_stats(matches)
        key = next((k for k in agg if player_name.lower() in k.lower()), None)
        if not key:
            await _send(ctx.channel, f"{player_name}? Ma3endnach stats.", emotion='thinking')
            return

        s = agg[key]
        stats = {
            "matches": s["games"],
            "goals": s["goals"],
            "assists": s["assists"],
            "rating_total": s["avg_rating"] * s["games"],
        }
        roast = roast_engine.get_fun_roast(s["name"], stats)
        roast = _clean_lines(roast, 2)
        await _send(ctx.channel, roast, emotion='laughter')

# ─── NEWS COMMANDS — SHORT ───

@bot.command(name="transfer", aliases=["rumour", "rumours"])
async def cmd_transfer(ctx):
    """Transfer rumor — SHORT. !transfer 🚨"""
    async with ctx.typing():
        matches = await _get_matches(5)
        data = await _get_all_data(1)
        text = await gemini.transfer_rumor(data.get("members", []), matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion='excitement')

@bot.command(name="breaking")
async def cmd_breaking(ctx):
    """Breaking news — SHORT. !breaking 📰"""
    async with ctx.typing():
        matches = await _get_matches(1)
        data = await _get_all_data(1)
        text = await gemini.breaking_news(matches, data.get("members", []))
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion='disappointment')

# ─── ANALYTICS COMMANDS — SHORT ───

@bot.command(name="stats")
async def cmd_stats(ctx):
    """Stats saison — compact."""
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
        wr = f"{w/total*100:.0f}%" if total else "?"
    except:
        wr = "?"

    lines = [
        f"📊 **{name}**",
        f"W:{s.get('wins','?')} D:{s.get('ties','?')} L:{s.get('losses','?')} | WR:{wr} | G:{s.get('gamesPlayed','?')}",
        f"⚽{s.get('goals','?')}/{s.get('goalsAgainst','?')} | SR:{s.get('skillRating','?')} | Div:{s.get('bestDivision','?')}",
        f"WS:{s.get('wstreak','?')} | UB:{s.get('unbeatenstreak','?')}",
    ]
    await ctx.send("\n".join(lines))

@bot.command(name="insights")
async def cmd_insights(ctx):
    """Insights — SHORT."""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        text = await gemini.insights(matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion='thinking')

@bot.command(name="trends")
async def cmd_trends(ctx):
    """Tendances — SHORT."""
    async with ctx.typing():
        matches = await _get_matches(10)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        text = await gemini.trends(matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion='thinking')

@bot.command(name="stat")
async def cmd_stat(ctx):
    """Stat du jour — SHORT."""
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        text = await gemini.stat_of_day(matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion='excitement')

@bot.command(name="predict")
async def cmd_predict(ctx, *, opponent: str = "Prochain adversaire"):
    """Prediction — SHORT. !predict Nom"""
    async with ctx.typing():
        matches = await _get_matches(5)
        text = await gemini.match_prediction(opponent, matches)
        text = _clean_lines(text, 2)
    await _send(ctx.channel, text, emotion='thinking')

@bot.command(name="clubinfo")
async def cmd_clubinfo(ctx):
    """Info club — SHORT."""
    async with ctx.typing():
        data = await _get_all_data(1)
    info = data.get("club_info") or {}
    lines = [
        f"🏟️ **{info.get('name','Rachad L3ERGONI')}**",
        f"🎮 common-gen5 | proclubstracker.com/club/1427607",
    ]
    await ctx.send("\n".join(lines))

# ─── ADMIN COMMANDS ───

@bot.command(name="setchannel")
@commands.has_permissions(manage_channels=True)
async def cmd_setchannel(ctx, channel_type: str = "match"):
    global MATCH_CHANNEL_ID
    if channel_type == "match":
        MATCH_CHANNEL_ID = ctx.channel.id
        await _send(ctx.channel, f"Match channel set! Auto-check kol {POLL_MINUTES}h 🔔", emotion='excitement')
    elif channel_type == "general":
        await _send(ctx.channel, "General channel set! 📅", emotion='excitement')
    else:
        await _send(ctx.channel, "Usage: !setchannel match ou !setchannel general", emotion='thinking')

@bot.command(name="weekly")
@commands.has_permissions(manage_channels=True)
async def cmd_weekly(ctx):
    """Weekly recap manuel (admin)."""
    await _send(ctx.channel, "Generating weekly recap...", emotion='thinking')
    async with ctx.typing():
        matches = await _get_matches(5)
        if not matches:
            await _send(ctx.channel, "Ma3endnach data. Walo.", emotion='disappointment')
            return
        data = await _get_all_data(1)
        await _post_five_summary(ctx.channel, matches, data.get("members", []))

@bot.command(name="refreshdata")
@commands.has_permissions(manage_channels=True)
async def cmd_refreshdata(ctx):
    """Force refresh."""
    await _send(ctx.channel, "Forçage refresh...", emotion='thinking')
    _scraper.invalidate_cache()
    matches = await _get_matches(5)
    if matches:
        await _send(ctx.channel, f"Data refreshed — {len(matches)} matchs!", emotion='excitement')
    else:
        await _send(ctx.channel, "Refresh failed. Walo.", emotion='disappointment')

@bot.command(name="ping")
async def cmd_ping(ctx):
    """Test connexion."""
    cache_age = int(_scraper.cache_age_seconds())
    cache_str = f"{cache_age}s" if cache_age < 3600 else "stale"
    await _send(ctx.channel, f"Pong ✅ | Cache: {cache_str} | Check: kol {POLL_MINUTES}min", emotion='thinking')

# ─── HELP — SHORT ───

@bot.command(name="help", aliases=["pchelp", "commands"])
async def cmd_help(ctx):
    lines = [
        "⚽ **Rachad L3ERGONI Bot** _(Pro Social Media Manager · Anime Cards · Short Darija)_",
        "",
        "**🎮 SESSION** `!roast` `!stop`",
        "**📋 MATCH** `!lastmatch` `!last5` `!last10` `!results` `!match <1-10>` `!quickreport` `!schedule`",
        "**👥 PLAYERS** `!players` `!player <nom>` `!form [nom]` `!topscorer` `!topassists` `!mvp` `!compare <p1> <p2>`",
        "**🎬 CONTENT** `!motm [1-5]` `!totw` `!hype [adv]` `!reaction` `!rankings` `!spotlight [nom]`",
        "**🔥 ROAST** `!roastreport` `!crowns` `!curses` `!funroast <nom>` `!roastplayer <nom>`",
        "**😂 FUN** `!cheer <nom>` `!banter` `!meme` `!drama`",
        "**📰 NEWS** `!transfer` `!breaking`",
        "**📊 ANALYTICS** `!stats` `!insights` `!trends` `!stat` `!predict <adv>` `!clubinfo`",
        "**⚙️ ADMIN** `!setchannel match` `!weekly` `!refreshdata` `!ping`",
        "",
        "_Auto: matchs kol 5min · Session: 45min timeout · Short phrases · Anime cards_",
    ]
    await ctx.send("\n".join(lines))

# ─── INTERNAL HELPERS ───

async def _post_five_summary(channel, matches: list, members: list):
    """5-match summary with ANIME cards + short text."""
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

    # SHORTEN all text
    summary_text = _clean_lines(summary_text, 2)
    performers_text = _clean_lines(performers_text, 2)
    totw_text = _clean_lines(totw_text, 2)

    totw_img = await loop.run_in_executor(None, lambda: image_gen.make_totw_card(totw_players))

    await _send(channel, summary_text, summary_img, "last5.png", emotion='excitement')
    await asyncio.sleep(1)
    await _send(channel, performers_text, emotion='excitement')
    await asyncio.sleep(1)
    await _send(channel, totw_text, totw_img, "totw.png", emotion='excitement')

    # Crowns/Curses — compact
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
        lines = []
        if all_crowns:
            sorted_crowns = sorted(all_crowns.items(), key=lambda x: x[1], reverse=True)[:3]
            lines.append("👑 **Crowns:** " + " | ".join([f"{n}:{c}" for n, c in sorted_crowns]))
        if all_curses:
            sorted_curses = sorted(all_curses.items(), key=lambda x: x[1], reverse=True)[:3]
            lines.append("💀 **Curses:** " + " | ".join([f"{n}:{c}" for n, c in sorted_curses]))
        await channel.send("\n".join(lines))

# ─── EVENTS ───

@bot.event
async def on_ready():
    global seen_matches
    seen_matches = load_seen()
    logger.info(f"✅ Bot ready: {bot.user}")
    logger.info(f"   Session poll: every {POLL_MINUTES}min | Timeout: {TIMEOUT_MINUTES}min")
    logger.info(f"   Style: Pro Social Media Manager · Short phrases · Anime cards")
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
        await _send(ctx.channel, "Ma3ndekch permission! 🚫", emotion='disappointment')
    elif isinstance(error, commands.MissingRequiredArgument):
        await _send(ctx.channel, "Naqes argument — !help bach tchouf.", emotion='thinking')
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        logger.error("Command error [%s]: %s", ctx.command, error, exc_info=True)
        await _send(ctx.channel, f"Error: {str(error)[:100]}", emotion='disappointment')

# ─── HEALTH SERVER (Render) ───
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
