"""
Rachad L3ERGONI Bot - Main Discord Bot
Premium Moroccan Pro Clubs Discord Bot
Native Darija | Real Stats | Pro Visuals | 95% Roast Mode
"""

import os
import io
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

from darija_engine import get_engine, DarijaEngine, PERSONALITIES
from stats_engine import get_stats_engine, StatsEngine, PlayerMatchStats, MatchResult
from image_gen import get_image_generator, ImageGenerator
from scraper import get_scraper, ProClubsScraper

# Load environment variables
load_dotenv()

# Bot configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MATCH_CHANNEL_ID = int(os.getenv("MATCH_CHANNEL_ID", "0"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID", "0"))
GENERAL_CHANNEL_ID = int(os.getenv("GENERAL_CHANNEL_ID", "0"))
CLUB_ID = os.getenv("CLUB_ID", "")
PLATFORM = os.getenv("PLATFORM", "ps5")
PORT = int(os.getenv("PORT", "10000"))

# Initialize components
darija = get_engine("squad.json")
stats_engine = get_stats_engine("match_data.json")
image_gen = get_image_generator("assets")
scraper = get_scraper(CLUB_ID, PLATFORM)

# Bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Bot instance
class L3ERGONIBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.darija = darija
        self.stats = stats_engine
        self.images = image_gen
        self.scraper = scraper
        self.squad = self._load_squad()
        self.session_active = False
        self.session_task = None

    def _load_squad(self) -> dict:
        try:
            with open("squad.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    async def setup_hook(self):
        """Setup hook - start background tasks"""
        self.auto_leaderboard.start()
        self.auto_match_check.start()
        await self.tree.sync()

    async def on_ready(self):
        """Bot ready event"""
        print(f"Rachad L3ERGONI Bot logged in as {self.user}")
        print(f"Connected to {len(self.guilds)} guilds")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Rachad L3ERGONI | !help"
            )
        )

    @tasks.loop(hours=24)
    async def auto_leaderboard(self):
        """Auto post daily leaderboard at 20:00"""
        now = datetime.now()
        if now.hour == 20 and now.minute < 5:
            channel = self.get_channel(LEADERBOARD_CHANNEL_ID)
            if channel:
                await self._post_leaderboard(channel, "daily", 5)

    @auto_leaderboard.before_loop
    async def before_auto_leaderboard(self):
        await self.wait_until_ready()

    @tasks.loop(minutes=5)
    async def auto_match_check(self):
        """Check for new matches every 5 minutes"""
        if self.session_active:
            try:
                added = await self.scraper.sync_recent_matches(self.stats, count=3)
                if added > 0:
                    channel = self.get_channel(MATCH_CHANNEL_ID)
                    if channel:
                        await self._post_match_result(channel)
            except Exception as e:
                print(f"Auto match check error: {e}")

    @auto_match_check.before_loop
    async def before_auto_match_check(self):
        await self.wait_until_ready()

    async def _post_match_result(self, channel: discord.TextChannel):
        """Post match result with roast and card"""
        match = self.stats.get_last_match()
        if not match:
            return

        # Roast the result
        roast = self.darija.roast_match_result(match.team_goals, match.opponent_goals, match.opponent)

        # Generate match report card
        match_dict = match.to_dict()
        card = self.images.generate_match_report_card(match_dict)
        card_bytes = self.images.to_bytes(card)

        # Build embed
        embed = discord.Embed(
            title=f"Match Result: {match.team_goals}-{match.opponent_goals} vs {match.opponent}",
            description=roast,
            color=0x00FF00 if match.result == "win" else 0xFF0000 if match.result == "loss" else 0xFFD700
        )

        # Add player stats
        for name, ps in list(match.player_stats.items())[:6]:
            player_info = self.squad.get(name.lower(), {})
            nickname = player_info.get("nickname", name)
            motm_emoji = "👑 " if ps.motm else ""
            embed.add_field(
                name=f"{motm_emoji}{nickname}",
                value=f"{ps.goals}G {ps.assists}A | ⭐{ps.rating:.1f} | {ps.shots} shots",
                inline=True
            )

        # MOTM roast
        motm_name = next((name for name, ps in match.player_stats.items() if ps.motm), "")
        if motm_name:
            player_info = self.squad.get(motm_name.lower(), {})
            nickname = player_info.get("nickname", motm_name)
            motm_roast = self.darija.roast_motm(nickname, match.player_stats[motm_name].rating)
            embed.add_field(name="MOTM", value=motm_roast, inline=False)

        file = discord.File(io.BytesIO(card_bytes), filename="match_report.png")
        embed.set_image(url="attachment://match_report.png")

        await channel.send(embed=embed, file=file)

    async def _post_leaderboard(self, channel: discord.TextChannel, period: str, matches: int):
        """Post leaderboard card"""
        leaderboard = self.stats.get_leaderboard(matches, "impact_score")

        if not leaderboard:
            await channel.send("z3ma... leaderboard? walo. chi m3a9ed. safi.")
            return

        # Generate leaderboard card
        card = self.images.generate_leaderboard_card(leaderboard, period)
        card_bytes = self.images.to_bytes(card)

        # Roast entries
        roasts = self.darija.roast_leaderboard(leaderboard)
        roast_text = "\n".join(roasts[:3])

        embed = discord.Embed(
            title=f"Leaderboard - {period.upper()}",
            description=roast_text,
            color=0xFFD700
        )

        file = discord.File(io.BytesIO(card_bytes), filename="leaderboard.png")
        embed.set_image(url="attachment://leaderboard.png")

        await channel.send(embed=embed, file=file)


# Create bot instance
bot = L3ERGONIBot()

# ==========================================
# COMMANDS
# ==========================================

@bot.command(name="roast")
async def roast_cmd(ctx: commands.Context):
    """Start session monitoring (checks every 5min)"""
    bot.session_active = True
    roast = bot.darija.banter()
    await ctx.send(f"Session started! {roast}\nMonitoring matches every 5 minutes...")

@bot.command(name="stop")
async def stop_cmd(ctx: commands.Context):
    """Stop session monitoring"""
    bot.session_active = False
    await ctx.send("Session stopped. walo. safi.")

@bot.command(name="lastmatch")
async def lastmatch_cmd(ctx: commands.Context):
    """Show last match with all player stats + MOTM card"""
    match = bot.stats.get_last_match()
    if not match:
        await ctx.send("z3ma... last match? walo. chi m3a9ed. safi.")
        return

    await bot._post_match_result(ctx.channel)

@bot.command(name="stats")
async def stats_cmd(ctx: commands.Context, *, player_name: str):
    """Show player stats + anime card"""
    player_key = player_name.lower().strip()
    player_info = bot.squad.get(player_key, {})

    if not player_info:
        await ctx.send(f"z3ma... {player_name}? walo. chi m3a9ed. safi.")
        return

    name = player_info.get("name", player_name)
    stats = bot.stats.get_player_stats(name, 5)

    if not stats:
        await ctx.send(f"z3ma... stats dial {name}? walo. chi m3a9ed. safi.")
        return

    # Generate player card
    card = bot.images.generate_player_card(name, stats, player_info)
    card_bytes = bot.images.to_bytes(card)

    # Generate roasts
    roasts = bot.darija.roast_player(name, stats, 5)
    roast_text = "\n".join(roasts)

    embed = discord.Embed(
        title=f"{player_info.get('nickname', name)} - Stats Card",
        description=roast_text,
        color=0xFF6B35
    )

    file = discord.File(io.BytesIO(card_bytes), filename="player_card.png")
    embed.set_image(url="attachment://player_card.png")

    await ctx.send(embed=embed, file=file)

@bot.command(name="roastplayer")
async def roastplayer_cmd(ctx: commands.Context, *, player_name: str):
    """Roast a specific player with data"""
    player_key = player_name.lower().strip()
    player_info = bot.squad.get(player_key, {})

    if not player_info:
        await ctx.send(f"z3ma... {player_name}? walo. chi m3a9ed. safi.")
        return

    name = player_info.get("name", player_name)
    stats = bot.stats.get_player_stats(name, 5)

    if not stats:
        await ctx.send(f"z3ma... roast dial {name}? walo. chi m3a9ed. safi.")
        return

    roasts = bot.darija.roast_player(name, stats, 5)
    for roast in roasts:
        await ctx.send(roast)

@bot.command(name="mvp")
async def mvp_cmd(ctx: commands.Context):
    """MVP of last 5 matches + card"""
    mvp_name, mvp_stats = bot.stats.get_mvp(5)

    if not mvp_name:
        await ctx.send("z3ma... mvp? walo. chi m3a9ed. safi.")
        return

    player_info = bot.squad.get(mvp_name.lower(), {})
    nickname = player_info.get("nickname", mvp_name)

    # Generate MOTM card
    card = bot.images.generate_motm_card(mvp_name, mvp_stats, player_info)
    card_bytes = bot.images.to_bytes(card)

    roast = bot.darija.roast_motm(nickname, mvp_stats.get("rating", 6.0))

    embed = discord.Embed(
        title=f"MVP - Last 5 Matches",
        description=roast,
        color=0xFFD700
    )

    file = discord.File(io.BytesIO(card_bytes), filename="mvp_card.png")
    embed.set_image(url="attachment://mvp_card.png")

    await ctx.send(embed=embed, file=file)

@bot.command(name="compare")
async def compare_cmd(ctx: commands.Context, p1: str, p2: str):
    """1v1 comparison + card"""
    p1_key = p1.lower().strip()
    p2_key = p2.lower().strip()

    p1_info = bot.squad.get(p1_key, {})
    p2_info = bot.squad.get(p2_key, {})

    if not p1_info or not p2_info:
        await ctx.send("z3ma... players? walo. chi m3a9ed. safi.")
        return

    p1_name = p1_info.get("name", p1)
    p2_name = p2_info.get("name", p2)

    p1_stats = bot.stats.get_player_stats(p1_name, 10)
    p2_stats = bot.stats.get_player_stats(p2_name, 10)

    if not p1_stats or not p2_stats:
        await ctx.send("z3ma... stats? walo. chi m3a9ed. safi.")
        return

    # Generate comparison card
    card = bot.images.generate_comparison_card(p1_name, p1_stats, p1_info, p2_name, p2_stats, p2_info)
    card_bytes = bot.images.to_bytes(card)

    roast = bot.darija.compare_players(p1_name, p1_stats, p2_name, p2_stats)

    embed = discord.Embed(
        title=f"{p1_info.get('nickname', p1_name)} VS {p2_info.get('nickname', p2_name)}",
        description=roast,
        color=0xFF6B35
    )

    file = discord.File(io.BytesIO(card_bytes), filename="comparison.png")
    embed.set_image(url="attachment://comparison.png")

    await ctx.send(embed=embed, file=file)

@bot.command(name="leaderboard")
async def leaderboard_cmd(ctx: commands.Context, period: str = "week"):
    """Full leaderboard with card"""
    period_map = {"day": 5, "week": 20, "month": 50, "all": 999}
    matches = period_map.get(period.lower(), 20)

    await bot._post_leaderboard(ctx.channel, period, matches)

@bot.command(name="banter")
async def banter_cmd(ctx: commands.Context):
    """Random football trash talk"""
    await ctx.send(bot.darija.banter())

@bot.command(name="drama")
async def drama_cmd(ctx: commands.Context):
    """Drama/polemique"""
    await ctx.send(bot.darija.drama())

@bot.command(name="meme")
async def meme_cmd(ctx: commands.Context):
    """Meme b Darija"""
    await ctx.send(bot.darija.meme())

@bot.command(name="transfer")
async def transfer_cmd(ctx: commands.Context):
    """Transfer rumor (humour)"""
    await ctx.send(bot.darija.transfer())

@bot.command(name="predict")
async def predict_cmd(ctx: commands.Context, *, opponent: str):
    """Match prediction with roast"""
    import random
    predictions = ["win", "loss", "draw"]
    pred = random.choice(predictions)
    roast = bot.darija.predict(pred)

    embed = discord.Embed(
        title=f"Prediction: vs {opponent}",
        description=roast,
        color=0xFF6B35
    )
    await ctx.send(embed=embed)

@bot.command(name="clubinfo")
async def clubinfo_cmd(ctx: commands.Context):
    """Club info with stats"""
    team_stats = bot.stats.get_team_stats(20)

    if not team_stats:
        await ctx.send("z3ma... club info? walo. chi m3a9ed. safi.")
        return

    embed = discord.Embed(
        title="Rachad L3ERGONI - Club Info",
        description="z3ma... club? walo. chi m3a9ed l3ba.",
        color=0xFF6B35
    )

    embed.add_field(name="Matches", value=team_stats["matches"], inline=True)
    embed.add_field(name="Wins", value=team_stats["wins"], inline=True)
    embed.add_field(name="Losses", value=team_stats["losses"], inline=True)
    embed.add_field(name="Win Rate", value=f"{team_stats['win_rate']}%", inline=True)
    embed.add_field(name="Goals Scored", value=team_stats["goals_scored"], inline=True)
    embed.add_field(name="Goals Conceded", value=team_stats["goals_conceded"], inline=True)
    embed.add_field(name="Current Streak", value=team_stats["current_streak"], inline=True)
    embed.add_field(name="Best Streak", value=f"{team_stats['best_streak']} wins", inline=True)

    await ctx.send(embed=embed)

@bot.command(name="worst")
async def worst_cmd(ctx: commands.Context):
    """Worst player of the week"""
    worst_name, worst_stats = bot.stats.get_worst_player(7)

    if not worst_name:
        await ctx.send("z3ma... worst player? walo. chi m3a9ed. safi.")
        return

    player_info = bot.squad.get(worst_name.lower(), {})
    nickname = player_info.get("nickname", worst_name)

    roast = bot.darija._format_roast(
        "{name}. worst of the week. z3ma... player? walo. delete game.",
        name=nickname
    )

    embed = discord.Embed(
        title="Worst Player of the Week 🗑️",
        description=roast,
        color=0xFF0000
    )

    embed.add_field(name="Rating", value=f"{worst_stats.get('rating', 0):.1f}", inline=True)
    embed.add_field(name="Error Score", value=f"{worst_stats.get('error_score', 0)}", inline=True)
    embed.add_field(name="Possession Losses", value=worst_stats.get("possession_losses", 0), inline=True)

    await ctx.send(embed=embed)

@bot.command(name="who_sold")
async def who_sold_cmd(ctx: commands.Context):
    """Who sold the match"""
    worst_name, worst_stats = bot.stats.get_worst_player(1)

    if not worst_name:
        await ctx.send("z3ma... who sold? walo. chi m3a9ed. safi.")
        return

    player_info = bot.squad.get(worst_name.lower(), {})
    nickname = player_info.get("nickname", worst_name)

    roast = bot.darija._format_roast(
        "{name}. sold the match. z3ma... player? walo. delete game. trash. garbage.",
        name=nickname
    )

    await ctx.send(roast)

@bot.command(name="carry_detector")
async def carry_detector_cmd(ctx: commands.Context):
    """Detect who is carrying the team"""
    mvp_name, mvp_stats = bot.stats.get_mvp(10)

    if not mvp_name:
        await ctx.send("z3ma... carry? walo. chi m3a9ed. safi.")
        return

    player_info = bot.squad.get(mvp_name.lower(), {})
    nickname = player_info.get("nickname", mvp_name)

    roast = bot.darija._format_roast(
        "{name}. carrying the team. z3ma... rest of the team? walo. chi m3a9ed l3ba.",
        name=nickname
    )

    embed = discord.Embed(
        title="Carry Detector 🏋️",
        description=roast,
        color=0xFFD700
    )

    embed.add_field(name="Impact Score", value=f"{mvp_stats.get('impact_score', 0):.1f}", inline=True)
    embed.add_field(name="Goals", value=mvp_stats.get("goals", 0), inline=True)
    embed.add_field(name="Assists", value=mvp_stats.get("assists", 0), inline=True)

    await ctx.send(embed=embed)

@bot.command(name="fraud_check")
async def fraud_check_cmd(ctx: commands.Context, *, player_name: str):
    """Check if a player is a fraud"""
    player_key = player_name.lower().strip()
    player_info = bot.squad.get(player_key, {})

    if not player_info:
        await ctx.send(f"z3ma... {player_name}? walo. chi m3a9ed. safi.")
        return

    name = player_info.get("name", player_name)
    stats = bot.stats.get_player_stats(name, 10)

    if not stats:
        await ctx.send(f"z3ma... fraud check dial {name}? walo. chi m3a9ed. safi.")
        return

    # Fraud detection logic
    fraud_score = 0
    fraud_reasons = []

    if stats.get("goals", 0) == 0 and stats.get("assists", 0) == 0:
        fraud_score += 50
        fraud_reasons.append("0 goals, 0 assists")

    if stats.get("rating", 10) < 6.0:
        fraud_score += 30
        fraud_reasons.append(f"Rating {stats['rating']:.1f}")

    if stats.get("possession_losses", 0) > 15:
        fraud_score += 20
        fraud_reasons.append(f"{stats['possession_losses']} possession losses")

    is_fraud = fraud_score >= 50

    nickname = player_info.get("nickname", name)

    if is_fraud:
        roast = bot.darija._format_roast(
            "{name}. FRAUD DETECTED. z3ma... player? walo. delete game. trash. garbage. 🗑️",
            name=nickname
        )
    else:
        roast = bot.darija._format_roast(
            "{name}. z3ma... fraud? walo. chi m3a9ed. safi.",
            name=nickname
        )

    embed = discord.Embed(
        title=f"Fraud Check - {nickname}",
        description=roast,
        color=0xFF0000 if is_fraud else 0x00FF00
    )

    embed.add_field(name="Fraud Score", value=f"{fraud_score}/100", inline=True)
    embed.add_field(name="Reasons", value="\n".join(fraud_reasons) if fraud_reasons else "None", inline=True)

    await ctx.send(embed=embed)

@bot.command(name="ballon_dor")
async def ballon_dor_cmd(ctx: commands.Context):
    """Ballon d'Or of the squad"""
    leaderboard = bot.stats.get_leaderboard(50, "impact_score")

    if not leaderboard:
        await ctx.send("z3ma... ballon d'or? walo. chi m3a9ed. safi.")
        return

    winner_name, winner_stats = leaderboard[0]
    player_info = bot.squad.get(winner_name.lower(), {})
    nickname = player_info.get("nickname", winner_name)

    roast = bot.darija._format_roast(
        "{name}. ballon d'or. z3ma... best? walo. chi m3a9ed l3ba. clown team.",
        name=nickname
    )

    embed = discord.Embed(
        title="Ballon d'Or 🏆",
        description=roast,
        color=0xFFD700
    )

    embed.add_field(name="Winner", value=nickname, inline=True)
    embed.add_field(name="Impact Score", value=f"{winner_stats.get('impact_score', 0):.1f}", inline=True)
    embed.add_field(name="Goals", value=winner_stats.get("goals", 0), inline=True)
    embed.add_field(name="Assists", value=winner_stats.get("assists", 0), inline=True)
    embed.add_field(name="Rating", value=f"{winner_stats.get('rating', 0):.1f}", inline=True)

    await ctx.send(embed=embed)

@bot.command(name="ghost_detector")
async def ghost_detector_cmd(ctx: commands.Context):
    """Detect ghost players (low activity)"""
    ghosts = []
    for name in bot.squad:
        stats = bot.stats.get_player_stats(bot.squad[name]["name"], 10)
        if not stats or stats.get("matches", 0) < 3:
            ghosts.append(name)

    if not ghosts:
        await ctx.send("z3ma... ghosts? walo. kolchi kayl3b. safi.")
        return

    ghost_names = [bot.squad[g].get("nickname", g) for g in ghosts]
    roast = bot.darija._format_roast(
        "{ghosts}. ghosts detected. z3ma... players? walo. delete game.",
        ghosts=", ".join(ghost_names)
    )

    embed = discord.Embed(
        title="Ghost Detector 👻",
        description=roast,
        color=0x808080
    )

    for ghost in ghosts:
        stats = bot.stats.get_player_stats(bot.squad[ghost]["name"], 10)
        matches = stats.get("matches", 0) if stats else 0
        embed.add_field(
            name=bot.squad[ghost].get("nickname", ghost),
            value=f"{matches} matches played",
            inline=True
        )

    await ctx.send(embed=embed)

@bot.command(name="pass_the_ball")
async def pass_the_ball_cmd(ctx: commands.Context, *, player_name: str):
    """Call out a ball hog"""
    player_key = player_name.lower().strip()
    player_info = bot.squad.get(player_key, {})

    if not player_info:
        await ctx.send(f"z3ma... {player_name}? walo. chi m3a9ed. safi.")
        return

    name = player_info.get("name", player_name)
    stats = bot.stats.get_player_stats(name, 5)

    if not stats:
        await ctx.send(f"z3ma... stats dial {name}? walo. chi m3a9ed. safi.")
        return

    dribbles = stats.get("dribbles_attempted", 0)
    passes = stats.get("passes_attempted", 0)

    if dribbles > passes * 0.5:
        roast = bot.darija._format_roast(
            "{name}. pass the ball! z3ma... dribbler? walo. chi m3a9ed l3ba. team sport.",
            name=player_info.get("nickname", name)
        )
    else:
        roast = bot.darija._format_roast(
            "{name}. z3ma... ball hog? walo. chi m3a9ed. safi.",
            name=player_info.get("nickname", name)
        )

    await ctx.send(roast)

@bot.command(name="personality")
async def personality_cmd(ctx: commands.Context, mode: str):
    """Switch bot personality"""
    if mode.lower() in PERSONALITIES:
        bot.darija.set_personality(mode.lower())
        await ctx.send(f"Personality switched to {mode.upper()}. z3ma... change? walo. safi.")
    else:
        modes = ", ".join(PERSONALITIES.keys())
        await ctx.send(f"z3ma... personality? walo. Available: {modes}")

@bot.command(name="sync")
async def sync_cmd(ctx: commands.Context):
    """Manually sync recent matches from EA API"""
    try:
        added = await bot.scraper.sync_recent_matches(bot.stats, count=10)
        if added > 0:
            await ctx.send(f"Synced {added} new matches. z3ma... data? walo. safi.")
        else:
            await ctx.send("z3ma... new matches? walo. chi m3a9ed. safi.")
    except Exception as e:
        await ctx.send(f"z3ma... sync? walo. Error: {e}")

@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    """Show all commands"""
    embed = discord.Embed(
        title="Rachad L3ERGONI Bot - Commands",
        description="95% roast mode | Native Darija | Real Stats | Pro Visuals",
        color=0xFF6B35
    )

    commands_list = [
        ("!roast", "Start session monitoring (5min checks)"),
        ("!stop", "Stop session"),
        ("!lastmatch", "Last match + all stats + MOTM card"),
        ("!stats <name>", "Player stats + premium card"),
        ("!roastplayer <name>", "Roast specific player with data"),
        ("!mvp", "MVP of last 5 matches + card"),
        ("!compare <p1> <p2>", "1v1 comparison + card"),
        ("!leaderboard <period>", "Leaderboard (day/week/month/all) + card"),
        ("!banter", "Football trash talk"),
        ("!drama", "Drama/polemique"),
        ("!meme", "Meme b Darija"),
        ("!transfer", "Transfer rumor (humour)"),
        ("!predict <opponent>", "Match prediction"),
        ("!clubinfo", "Club info with all stats"),
        ("!worst", "Worst player of the week"),
        ("!who_sold", "Who sold the match"),
        ("!carry_detector", "Who is carrying the team"),
        ("!fraud_check <name>", "Check if player is fraud"),
        ("!ballon_dor", "Ballon d'Or of the squad"),
        ("!ghost_detector", "Detect inactive players"),
        ("!pass_the_ball <name>", "Call out ball hog"),
        ("!personality <mode>", "Switch personality (casablanca/analyst/toxic/coach/commentator/cafeteria)"),
        ("!sync", "Manually sync matches from EA API"),
        ("!help", "This message")
    ]

    for cmd, desc in commands_list:
        embed.add_field(name=cmd, value=desc, inline=False)

    embed.set_footer(text="Rachad L3ERGONI Pro Clubs | Made with 🔥 for the squad")

    await ctx.send(embed=embed)

# ==========================================
# SLASH COMMANDS (Modern Discord)
# ==========================================

@bot.tree.command(name="stats", description="Show player stats with premium card")
@app_commands.describe(player="Player name")
async def slash_stats(interaction: discord.Interaction, player: str):
    ctx = await commands.Context.from_interaction(interaction)
    await stats_cmd(ctx, player_name=player)
    await interaction.response.send_message("Stats sent!")

@bot.tree.command(name="roast", description="Roast a player")
@app_commands.describe(player="Player name")
async def slash_roast(interaction: discord.Interaction, player: str):
    ctx = await commands.Context.from_interaction(interaction)
    await roastplayer_cmd(ctx, player_name=player)
    await interaction.response.send_message("Roast sent!")

@bot.tree.command(name="mvp", description="MVP of last 5 matches")
async def slash_mvp(interaction: discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    await mvp_cmd(ctx)
    await interaction.response.send_message("MVP sent!")

@bot.tree.command(name="compare", description="Compare two players")
@app_commands.describe(player1="First player", player2="Second player")
async def slash_compare(interaction: discord.Interaction, player1: str, player2: str):
    ctx = await commands.Context.from_interaction(interaction)
    await compare_cmd(ctx, p1=player1, p2=player2)
    await interaction.response.send_message("Comparison sent!")

@bot.tree.command(name="leaderboard", description="Show leaderboard")
@app_commands.describe(period="Time period (day/week/month/all)")
async def slash_leaderboard(interaction: discord.Interaction, period: str = "week"):
    ctx = await commands.Context.from_interaction(interaction)
    await leaderboard_cmd(ctx, period=period)
    await interaction.response.send_message("Leaderboard sent!")

# ==========================================
# HEALTH SERVER (for Render)
# ==========================================

async def start_health_server():
    """Start simple health check server for Render"""
    from aiohttp import web

    async def health(request):
        return web.Response(text="Rachad L3ERGONI Bot is alive!")

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Health server running on port {PORT}")

# ==========================================
# MAIN
# ==========================================

async def main():
    """Main entry point"""
    # Start health server in background
    asyncio.create_task(start_health_server())

    # Start bot
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
