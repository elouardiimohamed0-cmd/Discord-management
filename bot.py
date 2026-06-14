"""
Rachad L3ERGONI Bot — Main Discord Bot v12
Direct EA API. SQLite stats. Native Darija. Premium visuals.
"""

import asyncio
import io
import json
import logging
import os
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

from darija_engine import get_engine, PERSONALITIES
from stats_engine import get_stats_engine
from image_gen import get_image_generator
from ea_api import get_ea_api
from memory import get_memory

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MATCH_CHANNEL_ID = int(os.getenv("MATCH_CHANNEL_ID", "0"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID", "0"))
CLUB_ID = os.getenv("CLUB_ID", "1427607")
PLATFORM = os.getenv("PLATFORM", "common-gen5")
PORT = int(os.getenv("PORT", "10000"))

darija = get_engine("squad.json")
stats_engine = get_stats_engine("bot_data.db")
image_gen = get_image_generator("assets")
ea_api = get_ea_api(CLUB_ID, PLATFORM)
memory = get_memory("squad_memory.json")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class L3ERGONIBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.darija = darija
        self.stats = stats_engine
        self.images = image_gen
        self.ea = ea_api
        self.memory = memory
        self.squad = self._load_squad()
        self.session_active = False

    def _load_squad(self) -> dict:
        try:
            with open("squad.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Squad load error: %s", e)
            return {}

    def _find_squad_key(self, name: str) -> Optional[str]:
        name_clean = name.lower().strip()
        if name_clean in self.squad:
            return name_clean
        for key, info in self.squad.items():
            if info.get("name", "").lower().strip() == name_clean:
                return key
            if info.get("psn", "").lower().strip() == name_clean:
                return key
            if info.get("nickname", "").lower().strip() == name_clean:
                return key
            if name_clean in key or key in name_clean:
                return key
            if name_clean in info.get("name", "").lower():
                return key
            if name_clean in info.get("nickname", "").lower():
                return key
        return None

    async def setup_hook(self):
        self.auto_leaderboard.start()
        self.auto_match_check.start()
        await self.tree.sync()

    async def on_ready(self):
        logger.info("Logged in as %s | Guilds: %d | Club: %s", self.user, len(self.guilds), CLUB_ID)
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="Rachad L3ERGONI | !help")
        )

    @tasks.loop(hours=24)
    async def auto_leaderboard(self):
        now = datetime.now()
        if now.hour == 20 and now.minute < 5:
            channel = self.get_channel(LEADERBOARD_CHANNEL_ID)
            if channel:
                await self._post_leaderboard(channel, "daily", 5)

    @auto_leaderboard.before_loop
    async def before_auto_leaderboard(self):
        await self.wait_until_ready()

    @tasks.loop(minutes=10)
    async def auto_match_check(self):
        if not self.session_active:
            return
        try:
            matches = await self.ea.get_all_matches(max_per_type=5)
            added = 0
            for m in matches:
                if not self.stats.match_exists(m.match_id):
                    self.stats.add_match(m)
                    added += 1
            if added > 0:
                logger.info("Auto-sync: added %d new matches", added)
                channel = self.get_channel(MATCH_CHANNEL_ID)
                if channel:
                    await self._post_match_result(channel)
        except Exception as e:
            logger.error("Auto match check error: %s", e)

    @auto_match_check.before_loop
    async def before_auto_match_check(self):
        await self.wait_until_ready()

    async def _post_match_result(self, channel: discord.TextChannel):
        match = self.stats.get_last_match()
        if not match:
            return
        roast = self.darija.roast_match_result(match.team_goals, match.opponent_goals, match.opponent)
        card = self.images.generate_match_report_card(match.to_dict())
        card_bytes = self.images.to_bytes(card)
        embed = discord.Embed(
            title=f"{match.team_goals}-{match.opponent_goals} vs {match.opponent}",
            description=roast,
            color=0x00FF00 if match.result == "win" else 0xFF0000 if match.result == "loss" else 0xFFD700,
        )
        motm_name = next((n for n, p in match.player_stats.items() if p.motm), "")
        for name, ps in list(match.player_stats.items())[:6]:
            info = self.squad.get(name.lower(), {})
            nick = info.get("nickname", name)
            motm = "👑 " if ps.motm else ""
            embed.add_field(
                name=f"{motm}{nick}",
                value=f"{ps.goals}G {ps.assists}A | ⭐{ps.rating:.1f} | {ps.shots} shots",
                inline=True,
            )
        if motm_name:
            info = self.squad.get(motm_name.lower(), {})
            nick = info.get("nickname", motm_name)
            roast_motm = self.darija.roast_motm(nick, match.player_stats[motm_name].rating)
            embed.add_field(name="MOTM", value=roast_motm, inline=False)
        file = discord.File(io.BytesIO(card_bytes), filename="match.png")
        embed.set_image(url="attachment://match.png")
        await channel.send(embed=embed, file=file)

    async def _post_leaderboard(self, channel: discord.TextChannel, period: str, matches: int):
        leaderboard = self.stats.get_leaderboard(matches, "impact_score")
        if not leaderboard:
            await channel.send("z3ma... leaderboard? walo. chi m3a9ed. safi.")
            return
        card = self.images.generate_leaderboard_card(leaderboard, period)
        card_bytes = self.images.to_bytes(card)
        roasts = self.darija.roast_leaderboard(leaderboard)
        embed = discord.Embed(title=f"Leaderboard — {period.upper()}", description="\n".join(roasts[:3]), color=0xFFD700)
        file = discord.File(io.BytesIO(card_bytes), filename="leaderboard.png")
        embed.set_image(url="attachment://leaderboard.png")
        await channel.send(embed=embed, file=file)


bot = L3ERGONIBot()
bot.remove_command("help")


@bot.command(name="roast")
async def roast_cmd(ctx):
    bot.session_active = True
    await ctx.send(f"Session started! {bot.darija.banter()}\nMonitoring matches every 10 minutes...")


@bot.command(name="stop")
async def stop_cmd(ctx):
    bot.session_active = False
    await ctx.send("Session stopped. walo. safi.")


@bot.command(name="lastmatch")
async def lastmatch_cmd(ctx):
    match = bot.stats.get_last_match()
    if not match:
        await ctx.send("z3ma... last match? walo. chi m3a9ed. safi.\nTry: !sync")
        return
    await bot._post_match_result(ctx.channel)


@bot.command(name="stats")
async def stats_cmd(ctx, *, player_name: str):
    key = bot._find_squad_key(player_name)
    if not key:
        await ctx.send(f"z3ma... {player_name}? walo. chi m3a9ed. safi.")
        return
    info = bot.squad[key]
    name = info.get("name", player_name)
    stats = bot.stats.get_player_stats(name, 5)
    if not stats:
        await ctx.send(f"z3ma... stats dial {name}? walo. chi m3a9ed. safi.\nTry: !sync")
        return
    card = bot.images.generate_player_card(name, stats, info)
    card_bytes = bot.images.to_bytes(card)
    roasts = bot.darija.roast_player(name, stats, 5)
    embed = discord.Embed(title=f"{info.get('nickname', name)} — Stats Card", description="\n".join(roasts), color=0xFF6B35)
    file = discord.File(io.BytesIO(card_bytes), filename="player.png")
    embed.set_image(url="attachment://player.png")
    await ctx.send(embed=embed, file=file)


@bot.command(name="roastplayer")
async def roastplayer_cmd(ctx, *, player_name: str):
    key = bot._find_squad_key(player_name)
    if not key:
        await ctx.send(f"z3ma... {player_name}? walo. chi m3a9ed. safi.")
        return
    info = bot.squad[key]
    name = info.get("name", player_name)
    stats = bot.stats.get_player_stats(name, 5)
    if not stats:
        await ctx.send(f"z3ma... roast dial {name}? walo. chi m3a9ed. safi.")
        return
    roasts = bot.darija.roast_player(name, stats, 5)
    for roast in roasts:
        await ctx.send(roast)


@bot.command(name="mvp")
async def mvp_cmd(ctx):
    mvp_name, mvp_stats = bot.stats.get_mvp(5)
    if not mvp_name:
        await ctx.send("z3ma... mvp? walo. chi m3a9ed. safi.")
        return
    info = bot.squad.get(mvp_name.lower(), {})
    nick = info.get("nickname", mvp_name)
    card = bot.images.generate_motm_card(mvp_name, mvp_stats, info)
    card_bytes = bot.images.to_bytes(card)
    roast = bot.darija.roast_motm(nick, mvp_stats.get("rating", 6.0))
    embed = discord.Embed(title="MVP — Last 5 Matches", description=roast, color=0xFFD700)
    file = discord.File(io.BytesIO(card_bytes), filename="mvp.png")
    embed.set_image(url="attachment://mvp.png")
    await ctx.send(embed=embed, file=file)


@bot.command(name="compare")
async def compare_cmd(ctx, p1: str, p2: str):
    k1, k2 = bot._find_squad_key(p1), bot._find_squad_key(p2)
    if not k1 or not k2:
        await ctx.send("z3ma... players? walo. chi m3a9ed. safi.")
        return
    i1, i2 = bot.squad[k1], bot.squad[k2]
    n1, n2 = i1.get("name", p1), i2.get("name", p2)
    s1, s2 = bot.stats.get_player_stats(n1, 10), bot.stats.get_player_stats(n2, 10)
    if not s1 or not s2:
        await ctx.send("z3ma... stats? walo. chi m3a9ed. safi.")
        return
    card = bot.images.generate_comparison_card(n1, s1, i1, n2, s2, i2)
    card_bytes = bot.images.to_bytes(card)
    roast = bot.darija.compare_players(n1, s1, n2, s2)
    embed = discord.Embed(title=f"{i1.get('nickname', n1)} VS {i2.get('nickname', n2)}", description=roast, color=0xFF6B35)
    file = discord.File(io.BytesIO(card_bytes), filename="compare.png")
    embed.set_image(url="attachment://compare.png")
    await ctx.send(embed=embed, file=file)


@bot.command(name="leaderboard")
async def leaderboard_cmd(ctx, period: str = "week"):
    period_map = {"day": 5, "week": 20, "month": 50, "all": 999}
    matches = period_map.get(period.lower(), 20)
    await bot._post_leaderboard(ctx.channel, period, matches)


@bot.command(name="banter")
async def banter_cmd(ctx):
    await ctx.send(bot.darija.banter())


@bot.command(name="drama")
async def drama_cmd(ctx):
    await ctx.send(bot.darija.drama())


@bot.command(name="meme")
async def meme_cmd(ctx):
    await ctx.send(bot.darija.meme())


@bot.command(name="transfer")
async def transfer_cmd(ctx):
    await ctx.send(bot.darija.transfer())


@bot.command(name="predict")
async def predict_cmd(ctx, *, opponent: str):
    import random
    pred = random.choice(["win", "loss", "draw"])
    roast = bot.darija.predict(pred)
    embed = discord.Embed(title=f"Prediction: vs {opponent}", description=roast, color=0xFF6B35)
    await ctx.send(embed=embed)


@bot.command(name="clubinfo")
async def clubinfo_cmd(ctx):
    try:
        info = await bot.ea.get_club_info()
        members = await bot.ea.get_member_stats()
    except Exception as e:
        await ctx.send(f"z3ma... club info? walo. API error: {e}")
        return

    if not info:
        await ctx.send("z3ma... club info? walo. chi m3a9ed. safi.")
        return

    # EA returns a list with one dict usually
    club = info[0] if isinstance(info, list) else info
    embed = discord.Embed(title="Rachad L3ERGONI — Club Info", description="z3ma... club? walo. chi m3a9ed l3ba.", color=0xFF6B35)

    details = club.get("details", {})
    embed.add_field(name="Name", value=details.get("name", "Rachad L3ERGONI"), inline=True)
    embed.add_field(name="Division", value=details.get("division", "N/A"), inline=True)
    embed.add_field(name="Skill Rating", value=club.get("skillRating", "?"), inline=True)
    embed.add_field(name="Wins", value=club.get("wins", "?"), inline=True)
    embed.add_field(name="Losses", value=club.get("losses", "?"), inline=True)
    embed.add_field(name="Ties", value=club.get("ties", "?"), inline=True)
    embed.add_field(name="Goals", value=club.get("goals", "?"), inline=True)
    embed.add_field(name="Goals Against", value=club.get("goalsAgainst", "?"), inline=True)
    embed.add_field(name="Games Played", value=club.get("gamesPlayed", "?"), inline=True)
    embed.add_field(name="Best Division", value=club.get("bestDivision", "?"), inline=True)
    embed.add_field(name="Win Streak", value=club.get("wstreak", "?"), inline=True)
    embed.add_field(name="Members", value=str(len(members)) if isinstance(members, list) else "?", inline=True)

    await ctx.send(embed=embed)


@bot.command(name="worst")
async def worst_cmd(ctx):
    worst_name, worst_stats = bot.stats.get_worst_player(7)
    if not worst_name:
        await ctx.send("z3ma... worst player? walo. chi m3a9ed. safi.")
        return
    info = bot.squad.get(worst_name.lower(), {})
    nick = info.get("nickname", worst_name)
    roast = bot.darija._format("{name}. worst of the week. z3ma... player? walo. delete game.", name=nick)
    embed = discord.Embed(title="Worst Player of the Week 🗑️", description=roast, color=0xFF0000)
    embed.add_field(name="Rating", value=f"{worst_stats.get('rating', 0):.1f}", inline=True)
    embed.add_field(name="Error Score", value=f"{worst_stats.get('error_score', 0)}", inline=True)
    embed.add_field(name="Possession Losses", value=worst_stats.get("possession_losses", 0), inline=True)
    await ctx.send(embed=embed)


@bot.command(name="who_sold")
async def who_sold_cmd(ctx):
    worst_name, worst_stats = bot.stats.get_worst_player(1)
    if not worst_name:
        await ctx.send("z3ma... who sold? walo. chi m3a9ed. safi.")
        return
    info = bot.squad.get(worst_name.lower(), {})
    nick = info.get("nickname", worst_name)
    roast = bot.darija._format(
        "{name}. sold the match. z3ma... player? walo. delete game. trash. garbage.", name=nick
    )
    await ctx.send(roast)


@bot.command(name="carry_detector")
async def carry_detector_cmd(ctx):
    mvp_name, mvp_stats = bot.stats.get_mvp(10)
    if not mvp_name:
        await ctx.send("z3ma... carry? walo. chi m3a9ed. safi.")
        return
    info = bot.squad.get(mvp_name.lower(), {})
    nick = info.get("nickname", mvp_name)
    roast = bot.darija._format(
        "{name}. carrying the team. z3ma... rest of the team? walo. chi m3a9ed l3ba.", name=nick
    )
    embed = discord.Embed(title="Carry Detector 🏋️", description=roast, color=0xFFD700)
    embed.add_field(name="Impact Score", value=f"{mvp_stats.get('impact_score', 0):.1f}", inline=True)
    embed.add_field(name="Goals", value=mvp_stats.get("goals", 0), inline=True)
    embed.add_field(name="Assists", value=mvp_stats.get("assists", 0), inline=True)
    await ctx.send(embed=embed)


@bot.command(name="fraud_check")
async def fraud_check_cmd(ctx, *, player_name: str):
    key = bot._find_squad_key(player_name)
    if not key:
        await ctx.send(f"z3ma... {player_name}? walo. chi m3a9ed. safi.")
        return
    info = bot.squad[key]
    name = info.get("name", player_name)
    stats = bot.stats.get_player_stats(name, 10)
    if not stats:
        await ctx.send(f"z3ma... fraud check dial {name}? walo. chi m3a9ed. safi.")
        return
    is_fraud, roast, score, reasons = bot.darija.fraud_check(name, stats)
    embed = discord.Embed(title=f"Fraud Check — {info.get('nickname', name)}", description=roast, color=0xFF0000 if is_fraud else 0x00FF00)
    embed.add_field(name="Fraud Score", value=f"{score}/100", inline=True)
    embed.add_field(name="Reasons", value="\n".join(reasons) if reasons else "None", inline=True)
    await ctx.send(embed=embed)


@bot.command(name="ballon_dor")
async def ballon_dor_cmd(ctx):
    leaderboard = bot.stats.get_leaderboard(50, "impact_score")
    if not leaderboard:
        await ctx.send("z3ma... ballon d'or? walo. chi m3a9ed. safi.")
        return
    winner_name, winner_stats = leaderboard[0]
    info = bot.squad.get(winner_name.lower(), {})
    nick = info.get("nickname", winner_name)
    roast = bot.darija._format(
        "{name}. ballon d'or. z3ma... best? walo. chi m3a9ed l3ba. clown team.", name=nick
    )
    embed = discord.Embed(title="Ballon d'Or 🏆", description=roast, color=0xFFD700)
    embed.add_field(name="Winner", value=nick, inline=True)
    embed.add_field(name="Impact Score", value=f"{winner_stats.get('impact_score', 0):.1f}", inline=True)
    embed.add_field(name="Goals", value=winner_stats.get("goals", 0), inline=True)
    embed.add_field(name="Assists", value=winner_stats.get("assists", 0), inline=True)
    embed.add_field(name="Rating", value=f"{winner_stats.get('rating', 0):.1f}", inline=True)
    await ctx.send(embed=embed)


@bot.command(name="ghost_detector")
async def ghost_detector_cmd(ctx):
    ghosts = []
    for key, info in bot.squad.items():
        stats = bot.stats.get_player_stats(info.get("name", key), 10)
        if not stats or stats.get("matches", 0) < 3:
            ghosts.append(key)
    if not ghosts:
        await ctx.send("z3ma... ghosts? walo. kolchi kayl3b. safi.")
        return
    ghost_names = [bot.squad[g].get("nickname", g) for g in ghosts]
    roast = bot.darija._format(
        "{ghosts}. ghosts detected. z3ma... players? walo. delete game.", ghosts=", ".join(ghost_names)
    )
    embed = discord.Embed(title="Ghost Detector 👻", description=roast, color=0x808080)
    for ghost in ghosts:
        stats = bot.stats.get_player_stats(bot.squad[ghost].get("name", ghost), 10)
        matches = stats.get("matches", 0) if stats else 0
        embed.add_field(name=bot.squad[ghost].get("nickname", ghost), value=f"{matches} matches", inline=True)
    await ctx.send(embed=embed)


@bot.command(name="pass_the_ball")
async def pass_the_ball_cmd(ctx, *, player_name: str):
    key = bot._find_squad_key(player_name)
    if not key:
        await ctx.send(f"z3ma... {player_name}? walo. chi m3a9ed. safi.")
        return
    info = bot.squad[key]
    name = info.get("name", player_name)
    stats = bot.stats.get_player_stats(name, 5)
    if not stats:
        await ctx.send(f"z3ma... stats dial {name}? walo. chi m3a9ed. safi.")
        return
    dribbles = stats.get("dribbles_attempted", 0)
    passes = stats.get("passes_attempted", 0)
    if dribbles > passes * 0.5:
        roast = bot.darija._format(
            "{name}. pass the ball! z3ma... dribbler? walo. chi m3a9ed l3ba. team sport.", name=info.get("nickname", name)
        )
    else:
        roast = bot.darija._format(
            "{name}. z3ma... ball hog? walo. chi m3a9ed. safi.", name=info.get("nickname", name)
        )
    await ctx.send(roast)


@bot.command(name="personality")
async def personality_cmd(ctx, mode: str):
    if mode.lower() in PERSONALITIES:
        bot.darija.set_personality(mode.lower())
        await ctx.send(f"Personality switched to {mode.upper()}. z3ma... change? walo. safi.")
    else:
        modes = ", ".join(PERSONALITIES.keys())
        await ctx.send(f"z3ma... personality? walo. Available: {modes}")


@bot.command(name="sync")
async def sync_cmd(ctx, count: int = 15):
    await ctx.send("🔥 Syncing from EA servers directly...")
    try:
        matches = await bot.ea.get_all_matches(max_per_type=count)
        added = 0
        for m in matches:
            if not bot.stats.match_exists(m.match_id):
                bot.stats.add_match(m)
                added += 1
        if added > 0:
            await ctx.send(f"Synced {added} new matches from EA. z3ma... data? walo. safi.")
        else:
            await ctx.send("z3ma... new matches? walo. kolchi up-to-date. safi.")
    except Exception as e:
        await ctx.send(f"z3ma... sync? walo. Error: {e}")


@bot.command(name="force_sync")
async def force_sync_cmd(ctx):
    await ctx.send("🔥 Drilling EA API for ALL match types...")
    try:
        matches = await bot.ea.get_all_matches(max_per_type=50)
        added = 0
        for m in matches:
            if not bot.stats.match_exists(m.match_id):
                bot.stats.add_match(m)
                added += 1
        await ctx.send(f"🔥 Force synced {added} new matches from EA API!")
    except Exception as e:
        await ctx.send(f"z3ma... force sync? walo. Error: {e}")


@bot.command(name="test_api")
async def test_api_cmd(ctx):
    await ctx.send("Testing EA API connection...")
    try:
        info = await bot.ea.get_club_info()
        members = await bot.ea.get_member_stats()
        matches = await bot.ea.get_matches("friendlyMatch", 1)
        status = [
            f"✅ Club Info: {len(info)} fields",
            f"✅ Members: {len(members) if isinstance(members, list) else 'N/A'}",
            f"✅ Friendly Matches: {len(matches)}",
        ]
        if matches:
            m = matches[0]
            status.append(f"✅ Latest: {m.team_goals}-{m.opponent_goals} vs {m.opponent_name}")
        await ctx.send("\n".join(status))
    except Exception as e:
        await ctx.send(f"❌ EA API test failed: {e}")


@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(
        title="Rachad L3ERGONI Bot — Commands",
        description="95% roast mode | Native Darija | Direct EA API | Real Photos | Premium Visuals",
        color=0xFF6B35,
    )
    cmds = [
        ("!roast", "Start session monitoring (10min auto-checks)"),
        ("!stop", "Stop session"),
        ("!lastmatch", "Last match + premium card"),
        ("!stats <player>", "Player stats + premium card with REAL photo"),
        ("!roastplayer <player>", "Roast specific player with live data"),
        ("!mvp", "MVP of last 5 matches + gold card"),
        ("!compare <p1> <p2>", "1v1 comparison + side-by-side card"),
        ("!leaderboard <period>", "Leaderboard (day/week/month/all) + card"),
        ("!banter", "Football trash talk"),
        ("!drama", "Drama/polemique"),
        ("!meme", "Meme b Darija"),
        ("!transfer", "Transfer rumor (humour)"),
        ("!predict <opponent>", "Match prediction"),
        ("!clubinfo", "Club info with live stats from EA API"),
        ("!worst", "Worst player of the week"),
        ("!who_sold", "Who sold the match"),
        ("!carry_detector", "Who is carrying the team"),
        ("!fraud_check <player>", "Check if player is fraud"),
        ("!ballon_dor", "Ballon d'Or of the squad"),
        ("!ghost_detector", "Detect inactive players"),
        ("!pass_the_ball <player>", "Call out ball hog"),
        ("!personality <mode>", "Switch personality (casablanca/analyst/toxic/coach/commentator/cafeteria)"),
        ("!sync [count]", "Sync from EA API (skips duplicates)"),
        ("!force_sync", "🔥 Drill ALL data from EA API"),
        ("!test_api", "Test EA API connection"),
        ("!help", "This message"),
    ]
    for cmd, desc in cmds:
        embed.add_field(name=cmd, value=desc, inline=False)
    embed.set_footer(text="Rachad L3ERGONI Pro Clubs | Direct EA API | Made with 🔥 for the squad")
    await ctx.send(embed=embed)


# Slash commands
@bot.tree.command(name="stats", description="Show player stats with premium card")
@app_commands.describe(player="Player name (e.g., Shark, Dictator, Modamir)")
async def slash_stats(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    ctx = await commands.Context.from_interaction(interaction)
    await stats_cmd(ctx, player_name=player)


@bot.tree.command(name="roast", description="Roast a player")
@app_commands.describe(player="Player name")
async def slash_roast(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    ctx = await commands.Context.from_interaction(interaction)
    await roastplayer_cmd(ctx, player_name=player)


@bot.tree.command(name="mvp", description="MVP of last 5 matches")
async def slash_mvp(interaction: discord.Interaction):
    await interaction.response.defer()
    ctx = await commands.Context.from_interaction(interaction)
    await mvp_cmd(ctx)


@bot.tree.command(name="compare", description="Compare two players")
@app_commands.describe(player1="First player", player2="Second player")
async def slash_compare(interaction: discord.Interaction, player1: str, player2: str):
    await interaction.response.defer()
    ctx = await commands.Context.from_interaction(interaction)
    await compare_cmd(ctx, p1=player1, p2=player2)


@bot.tree.command(name="leaderboard", description="Show leaderboard")
@app_commands.describe(period="Time period (day/week/month/all)")
async def slash_leaderboard(interaction: discord.Interaction, period: str = "week"):
    await interaction.response.defer()
    ctx = await commands.Context.from_interaction(interaction)
    await leaderboard_cmd(ctx, period=period)


# Health server
async def start_health_server():
    from aiohttp import web
    async def health(request):
        return web.Response(text="Rachad L3ERGONI Bot is alive! 🔥")
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("[Health] Server running on port %d", PORT)


async def main():
    await start_health_server()
    await asyncio.sleep(1)
    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
