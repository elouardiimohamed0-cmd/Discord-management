"""
Rachad L3ERGONI Bot - Main Discord Bot v10
Ultimate: Hybrid scraper + Manual match entry + Fuzzy names + Photo fixes
"""

import os
import io
import asyncio
import json
import re
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

from darija_engine import get_engine, PERSONALITIES
from stats_engine import get_stats_engine
from image_gen import get_image_generator
from scraper import get_scraper

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MATCH_CHANNEL_ID = int(os.getenv("MATCH_CHANNEL_ID", "0"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID", "0"))
GENERAL_CHANNEL_ID = int(os.getenv("GENERAL_CHANNEL_ID", "0"))
CLUB_ID = os.getenv("CLUB_ID", "1427607")
PLATFORM = os.getenv("PLATFORM", "common-gen5")
PORT = int(os.getenv("PORT", "10000"))

darija = get_engine("squad.json")
stats_engine = get_stats_engine("match_data.json")
image_gen = get_image_generator("assets")
scraper = get_scraper(CLUB_ID, PLATFORM)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class L3ERGONIBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.darija = darija
        self.stats = stats_engine
        self.images = image_gen
        self.scraper = scraper
        self.squad = self._load_squad()
        self.session_active = False
        self.last_scraped_data = {}

    def _load_squad(self) -> dict:
        try:
            with open("squad.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Squad Load Error] {e}")
            return {}

    def _find_squad_key(self, name: str) -> Optional[str]:
        name_clean = name.lower().strip()
        if name_clean in self.squad:
            return name_clean
        for key, info in self.squad.items():
            if info.get("name", "").lower().strip() == name_clean: return key
            if info.get("psn", "").lower().strip() == name_clean: return key
            if info.get("nickname", "").lower().strip() == name_clean: return key
            if name_clean in key or key in name_clean: return key
            if name_clean in info.get("name", "").lower(): return key
            if name_clean in info.get("nickname", "").lower(): return key
        return None

    async def setup_hook(self):
        self.auto_leaderboard.start()
        self.auto_match_check.start()
        await self.tree.sync()

    async def on_ready(self):
        print(f"Rachad L3ERGONI Bot logged in as {self.user}")
        print(f"Connected to {len(self.guilds)} guilds")
        print(f"Club ID: {CLUB_ID} | Platform: {PLATFORM}")
        print(f"Squad loaded: {len(self.squad)} players")
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

    @tasks.loop(minutes=5)
    async def auto_match_check(self):
        if not self.session_active:
            return
        try:
            new_match = await self.scraper.check_new_match()
            if new_match:
                self.stats.add_match(new_match)
                channel = self.get_channel(MATCH_CHANNEL_ID)
                if channel:
                    await self._post_match_result(channel)
            else:
                added = await self.scraper.sync_to_stats_engine(self.stats, count=3)
                if added > 0:
                    channel = self.get_channel(MATCH_CHANNEL_ID)
                    if channel:
                        await self._post_match_result(channel)
        except Exception as e:
            print(f"[Auto Check Error] {e}")

    @auto_match_check.before_loop
    async def before_auto_match_check(self):
        await self.wait_until_ready()

    async def _post_match_result(self, channel: discord.TextChannel):
        match = self.stats.get_last_match()
        if not match:
            return
        roast = self.darija.roast_match_result(match.team_goals, match.opponent_goals, match.opponent)
        match_dict = match.to_dict()
        card = self.images.generate_match_report_card(match_dict)
        card_bytes = self.images.to_bytes(card)
        embed = discord.Embed(
            title=f"Match Result: {match.team_goals}-{match.opponent_goals} vs {match.opponent}",
            description=roast,
            color=0x00FF00 if match.result == "win" else 0xFF0000 if match.result == "loss" else 0xFFD700
        )
        for name, ps in list(match.player_stats.items())[:6]:
            info = self.squad.get(name.lower(), {})
            nick = info.get("nickname", name)
            motm = "👑 " if ps.motm else ""
            embed.add_field(name=f"{motm}{nick}", value=f"{ps.goals}G {ps.assists}A | ⭐{ps.rating:.1f} | {ps.shots} shots", inline=True)
        motm_name = next((n for n, p in match.player_stats.items() if p.motm), "")
        if motm_name:
            info = self.squad.get(motm_name.lower(), {})
            nick = info.get("nickname", motm_name)
            roast_motm = self.darija.roast_motm(nick, match.player_stats[motm_name].rating)
            embed.add_field(name="MOTM", value=roast_motm, inline=False)
        file = discord.File(io.BytesIO(card_bytes), filename="match_report.png")
        embed.set_image(url="attachment://match_report.png")
        await channel.send(embed=embed, file=file)

    async def _post_leaderboard(self, channel: discord.TextChannel, period: str, matches: int):
        leaderboard = self.stats.get_leaderboard(matches, "impact_score")
        if not leaderboard:
            await channel.send("z3ma... leaderboard? walo. chi m3a9ed. safi.")
            return
        card = self.images.generate_leaderboard_card(leaderboard, period)
        card_bytes = self.images.to_bytes(card)
        roasts = self.darija.roast_leaderboard(leaderboard)
        roast_text = "\n".join(roasts[:3])
        embed = discord.Embed(title=f"Leaderboard - {period.upper()}", description=roast_text, color=0xFFD700)
        file = discord.File(io.BytesIO(card_bytes), filename="leaderboard.png")
        embed.set_image(url="attachment://leaderboard.png")
        await channel.send(embed=embed, file=file)


bot = L3ERGONIBot()
bot.remove_command('help')


@bot.command(name="roast")
async def roast_cmd(ctx):
    bot.session_active = True
    await ctx.send(f"Session started! {bot.darija.banter()}\nMonitoring matches every 5 minutes...")


@bot.command(name="stop")
async def stop_cmd(ctx):
    bot.session_active = False
    await ctx.send("Session stopped. walo. safi.")


@bot.command(name="lastmatch")
async def lastmatch_cmd(ctx):
    match = bot.stats.get_last_match()
    if not match:
        await ctx.send("z3ma... last match? walo. chi m3a9ed. safi.\nTry: !addmatch")
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
        await ctx.send(f"z3ma... stats dial {name}? walo. chi m3a9ed. safi.\nTry: !sync or !addmatch")
        return
    card = bot.images.generate_player_card(name, stats, info)
    card_bytes = bot.images.to_bytes(card)
    roasts = bot.darija.roast_player(name, stats, 5)
    roast_text = "\n".join(roasts)
    embed = discord.Embed(title=f"{info.get('nickname', name)} - Stats Card", description=roast_text, color=0xFF6B35)
    file = discord.File(io.BytesIO(card_bytes), filename="player_card.png")
    embed.set_image(url="attachment://player_card.png")
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
    embed = discord.Embed(title="MVP - Last 5 Matches", description=roast, color=0xFFD700)
    file = discord.File(io.BytesIO(card_bytes), filename="mvp_card.png")
    embed.set_image(url="attachment://mvp_card.png")
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
    file = discord.File(io.BytesIO(card_bytes), filename="comparison.png")
    embed.set_image(url="attachment://comparison.png")
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
        club_info = await bot.scraper.get_club_info()
    except Exception:
        club_info = None
    team_stats = bot.stats.get_team_stats(20)
    if not team_stats and not club_info:
        await ctx.send("z3ma... club info? walo. chi m3a9ed. safi.")
        return
    embed = discord.Embed(title="Rachad L3ERGONI - Club Info", description="z3ma... club? walo. chi m3a9ed l3ba.", color=0xFF6B35)
    if club_info:
        embed.add_field(name="Club Name", value=club_info.get("name", "Rachad L3ERGONI"), inline=True)
        embed.add_field(name="Division", value=club_info.get("division", "N/A"), inline=True)
        embed.add_field(name="Skill Rating", value=club_info.get("skillRating", "N/A"), inline=True)
    if team_stats:
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
    roast = bot.darija._format("{name}. sold the match. z3ma... player? walo. delete game. trash. garbage.", name=nick)
    await ctx.send(roast)


@bot.command(name="carry_detector")
async def carry_detector_cmd(ctx):
    mvp_name, mvp_stats = bot.stats.get_mvp(10)
    if not mvp_name:
        await ctx.send("z3ma... carry? walo. chi m3a9ed. safi.")
        return
    info = bot.squad.get(mvp_name.lower(), {})
    nick = info.get("nickname", mvp_name)
    roast = bot.darija._format("{name}. carrying the team. z3ma... rest of the team? walo. chi m3a9ed l3ba.", name=nick)
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
    nick = info.get("nickname", name)
    if is_fraud:
        roast = bot.darija._format("{name}. FRAUD DETECTED. z3ma... player? walo. delete game. trash. garbage. 🗑️", name=nick)
    else:
        roast = bot.darija._format("{name}. z3ma... fraud? walo. chi m3a9ed. safi.", name=nick)
    embed = discord.Embed(title=f"Fraud Check - {nick}", description=roast, color=0xFF0000 if is_fraud else 0x00FF00)
    embed.add_field(name="Fraud Score", value=f"{fraud_score}/100", inline=True)
    embed.add_field(name="Reasons", value="\n".join(fraud_reasons) if fraud_reasons else "None", inline=True)
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
    roast = bot.darija._format("{name}. ballon d'or. z3ma... best? walo. chi m3a9ed l3ba. clown team.", name=nick)
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
    roast = bot.darija._format("{ghosts}. ghosts detected. z3ma... players? walo. delete game.", ghosts=", ".join(ghost_names))
    embed = discord.Embed(title="Ghost Detector 👻", description=roast, color=0x808080)
    for ghost in ghosts:
        stats = bot.stats.get_player_stats(bot.squad[ghost].get("name", ghost), 10)
        matches = stats.get("matches", 0) if stats else 0
        embed.add_field(name=bot.squad[ghost].get("nickname", ghost), value=f"{matches} matches played", inline=True)
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
        roast = bot.darija._format("{name}. pass the ball! z3ma... dribbler? walo. chi m3a9ed l3ba. team sport.", name=info.get("nickname", name))
    else:
        roast = bot.darija._format("{name}. z3ma... ball hog? walo. chi m3a9ed. safi.", name=info.get("nickname", name))
    await ctx.send(roast)


@bot.command(name="personality")
async def personality_cmd(ctx, mode: str):
    if mode.lower() in PERSONALITIES:
        bot.darija.set_personality(mode.lower())
        await ctx.send(f"Personality switched to {mode.upper()}. z3ma... change? walo. safi.")
    else:
        modes = ", ".join(PERSONALITIES.keys())
        await ctx.send(f"z3ma... personality? walo. Available: {modes}")


# ===================== DATA SYNC COMMANDS =====================

@bot.command(name="sync")
async def sync_cmd(ctx):
    await ctx.send("🔥 Syncing from all sources...")
    try:
        added = await bot.scraper.sync_to_stats_engine(bot.stats, count=10)
        if added > 0:
            await ctx.send(f"Synced {added} new matches. z3ma... data? walo. safi.")
        else:
            await ctx.send("z3ma... new matches? walo. chi m3a9ed. safi.\nTry: !force_sync or !addmatch")
    except Exception as e:
        await ctx.send(f"z3ma... sync? walo. Error: {e}")


@bot.command(name="force_sync")
async def force_sync_cmd(ctx):
    await ctx.send("🔥 Drilling ALL data sources...")
    try:
        all_data = await bot.scraper.scrape_all()
        if not all_data or not all_data.get("matches"):
            await ctx.send("z3ma... all sources empty? walo. chi m3a9ed. safi.\nUse !addmatch to enter matches manually.")
            return

        bot.last_scraped_data = all_data
        matches = all_data.get("matches", [])
        squad = bot.scraper._load_squad()
        added = 0
        for match in matches:
            if isinstance(match, dict) and "teams" in match:
                parsed = bot.scraper._parse_ea_match(match, squad)
            elif isinstance(match, str):
                parsed = bot.scraper._parse_pct_match(match, squad)
            else:
                parsed = bot.scraper._parse_pct_match(str(match), squad)
            if parsed and not bot.stats.match_exists(parsed["match_id"]):
                bot.stats.add_match(parsed)
                added += 1

        with open("scraped_raw.json", "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)

        await ctx.send(f"🔥 Force synced {added} new matches! Raw data saved to scraped_raw.json")
    except Exception as e:
        await ctx.send(f"z3ma... force sync? walo. Error: {e}")


@bot.command(name="raw_data")
async def raw_data_cmd(ctx):
    if not bot.last_scraped_data:
        await ctx.send("z3ma... raw data? walo. Run !force_sync first. safi.")
        return
    data = bot.last_scraped_data
    embed = discord.Embed(title="Raw Scraped Data", color=0xFF6B35)
    embed.add_field(name="Source", value=data.get("source", "unknown"), inline=True)
    embed.add_field(name="Matches", value=f"{len(data.get('matches', []))} matches", inline=True)
    embed.add_field(name="Players", value=f"{len(data.get('players', []))} players", inline=True)
    embed.add_field(name="DOM Rows", value=f"{len(data.get('table_rows', []))} rows", inline=True)
    embed.add_field(name="Timestamp", value=data.get("timestamp", "N/A"), inline=True)
    await ctx.send(embed=embed)


@bot.command(name="test_scraper")
async def test_scraper_cmd(ctx):
    await ctx.send("Testing all data sources...")
    try:
        all_data = await bot.scraper.scrape_all()
        if not all_data:
            await ctx.send("❌ All sources failed")
            return

        status = []
        status.append(f"📡 Source: {all_data.get('source', 'unknown')}")
        status.append(f"✅ Matches: {len(all_data.get('matches', []))}")
        status.append(f"✅ Players: {len(all_data.get('players', []))}")
        status.append(f"✅ DOM Rows: {len(all_data.get('table_rows', []))}")
        status.append(f"✅ DOM Elements: {len(all_data.get('dom_elements', []))}")

        matches = all_data.get("matches", [])
        if matches and isinstance(matches[0], dict) and "teams" in matches[0]:
            squad = bot.scraper._load_squad()
            parsed = bot.scraper._parse_ea_match(matches[0], squad)
            if parsed:
                status.append(f"✅ Match parsing: {parsed['opponent']} {parsed['team_goals']}-{parsed['opponent_goals']}")
                status.append(f"✅ Players in match: {len(parsed.get('player_stats', {}))}")

        await ctx.send("\n".join(status))
    except Exception as e:
        await ctx.send(f"❌ Scraper test failed: {e}")


# ===================== MANUAL MATCH ENTRY =====================

@bot.command(name="addmatch")
async def addmatch_cmd(ctx, *, match_text: str):
    """
    Manually add a match result.
    Usage: !addmatch <opponent> <score> [player_stats...]
    Examples:
      !addmatch FC Barcelona 3-2
      !addmatch Real Madrid 1-0 Shark:2G,1A Dictator:0G,1A
    """
    try:
        # Parse basic match info
        parts = match_text.strip().split()
        if len(parts) < 2:
            await ctx.send("Usage: !addmatch <opponent> <score> [player_stats]\nExample: !addmatch FC Barcelona 3-2")
            return

        # Find score pattern (e.g., 3-2, 1-0, 5-3)
        score_part = None
        score_idx = -1
        for i, part in enumerate(parts):
            if re.match(r'^\d+[-–]\d+$', part):
                score_part = part.replace("–", "-")
                score_idx = i
                break

        if not score_part:
            await ctx.send("z3ma... score? walo. Format: 3-2 or 1-0. safi.")
            return

        team_goals, opponent_goals = map(int, score_part.split("-"))
        opponent = " ".join(parts[:score_idx]) if score_idx > 0 else "Unknown"
        result = "win" if team_goals > opponent_goals else "loss" if team_goals < opponent_goals else "draw"

        # Parse player stats if provided (after score)
        player_stats = {}
        remaining = " ".join(parts[score_idx + 1:])
        if remaining:
            # Format: "Shark:2G,1A Dictator:0G,1A" or "Shark:2,1 Dictator:0,1"
            player_entries = remaining.split()
            for entry in player_entries:
                if ":" not in entry:
                    continue
                name_part, stats_part = entry.split(":", 1)
                key = bot._find_squad_key(name_part)
                if not key:
                    continue
                info = bot.squad[key]
                display_name = info.get("name", name_part)

                # Parse stats: "2G,1A" or "2,1" or "2G1A"
                goals = 0
                assists = 0
                if "G" in stats_part.upper() or "A" in stats_part.upper():
                    g_match = re.search(r'(\d+)G', stats_part, re.IGNORECASE)
                    a_match = re.search(r'(\d+)A', stats_part, re.IGNORECASE)
                    goals = int(g_match.group(1)) if g_match else 0
                    assists = int(a_match.group(1)) if a_match else 0
                else:
                    stat_nums = [int(x) for x in re.findall(r'\d+', stats_part)]
                    if len(stat_nums) >= 1: goals = stat_nums[0]
                    if len(stat_nums) >= 2: assists = stat_nums[1]

                player_stats[display_name] = {
                    "name": display_name, "position": info.get("position", "CM"),
                    "goals": goals, "assists": assists, "shots": goals + 2,
                    "shots_on_target": goals + 1, "passes_attempted": 20,
                    "passes_completed": 15, "pass_accuracy": 75.0,
                    "key_passes": assists * 2, "tackles": 2, "interceptions": 1,
                    "possession_losses": 5, "dribbles_attempted": 0,
                    "dribbles_completed": 0, "fouls": 0, "yellow_cards": 0,
                    "red_cards": 0, "rating": 7.0 if goals > 0 else 6.0,
                    "motm": False, "minutes_played": 90,
                    "distance_covered": 0.0, "sprint_speed": 0.0
                }

        match_id = f"manual_{int(datetime.now().timestamp())}"
        match_data = {
            "match_id": match_id, "date": datetime.now().isoformat(),
            "opponent": opponent, "team_goals": team_goals,
            "opponent_goals": opponent_goals, "result": result,
            "team_possession": 50.0, "opponent_possession": 50.0,
            "team_shots": team_goals * 3, "opponent_shots": opponent_goals * 3,
            "team_shots_on_target": team_goals * 2, "opponent_shots_on_target": opponent_goals * 2,
            "team_passes": 100, "opponent_passes": 100,
            "team_tackles": 10, "opponent_tackles": 10,
            "team_corners": 3, "opponent_corners": 3,
            "team_fouls": 5, "opponent_fouls": 5,
            "match_type": "gameType9", "player_stats": player_stats
        }

        bot.stats.add_match(match_data)
        await ctx.send(f"🔥 Match added: {team_goals}-{opponent_goals} vs {opponent} ({result.upper()})\nPlayers: {len(player_stats)}")
    except Exception as e:
        await ctx.send(f"z3ma... add match? walo. Error: {e}\nUsage: !addmatch <opponent> <score> [player_stats]")


@bot.command(name="addplayerstats")
async def addplayerstats_cmd(ctx, match_id: str, *, stats_text: str):
    """
    Add player stats to an existing match.
    Usage: !addplayerstats <match_id> <player>:<goals>G,<assists>A,...
    Example: !addplayerstats manual_12345 Shark:2G,1A
    """
    try:
        match = None
        for m in bot.stats.matches:
            if str(m.match_id) == match_id:
                match = m
                break

        if not match:
            await ctx.send(f"z3ma... match {match_id}? walo. Not found. safi.")
            return

        entries = stats_text.split()
        for entry in entries:
            if ":" not in entry:
                continue
            name_part, stats_part = entry.split(":", 1)
            key = bot._find_squad_key(name_part)
            if not key:
                continue
            info = bot.squad[key]
            display_name = info.get("name", name_part)

            goals = 0
            assists = 0
            g_match = re.search(r'(\d+)G', stats_part, re.IGNORECASE)
            a_match = re.search(r'(\d+)A', stats_part, re.IGNORECASE)
            goals = int(g_match.group(1)) if g_match else 0
            assists = int(a_match.group(1)) if a_match else 0

            match.player_stats[display_name] = {
                "name": display_name, "position": info.get("position", "CM"),
                "goals": goals, "assists": assists, "shots": goals + 2,
                "shots_on_target": goals + 1, "passes_attempted": 20,
                "passes_completed": 15, "pass_accuracy": 75.0,
                "key_passes": assists * 2, "tackles": 2, "interceptions": 1,
                "possession_losses": 5, "dribbles_attempted": 0,
                "dribbles_completed": 0, "fouls": 0, "yellow_cards": 0,
                "red_cards": 0, "rating": 7.0 if goals > 0 else 6.0,
                "motm": False, "minutes_played": 90,
                "distance_covered": 0.0, "sprint_speed": 0.0
            }

        bot.stats.save_data()
        await ctx.send(f"🔥 Stats added to match {match_id}. Players now: {len(match.player_stats)}")
    except Exception as e:
        await ctx.send(f"z3ma... add stats? walo. Error: {e}")


@bot.command(name="listmatches")
async def listmatches_cmd(ctx):
    """List all stored matches"""
    matches = bot.stats.matches[-10:]  # Last 10
    if not matches:
        await ctx.send("z3ma... matches? walo. No data. safi.")
        return

    embed = discord.Embed(title="Last 10 Matches", color=0xFF6B35)
    for m in matches:
        result_emoji = "🟢" if m.result == "win" else "🔴" if m.result == "loss" else "🟡"
        embed.add_field(
            name=f"{result_emoji} {m.team_goals}-{m.opponent_goals} vs {m.opponent}",
            value=f"ID: `{m.match_id}` | Players: {len(m.player_stats)}",
            inline=False
        )
    await ctx.send(embed=embed)


@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(
        title="Rachad L3ERGONI Bot - Commands",
        description="95% roast mode | Native Darija | Multi-source scraper + Manual entry | Real Photos",
        color=0xFF6B35
    )
    commands_list = [
        ("!roast", "Start session monitoring (5min auto-checks)"),
        ("!stop", "Stop session"),
        ("!lastmatch", "Last match + all stats + MOTM card"),
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
        ("!clubinfo", "Club info with live stats"),
        ("!worst", "Worst player of the week"),
        ("!who_sold", "Who sold the match"),
        ("!carry_detector", "Who is carrying the team"),
        ("!fraud_check <player>", "Check if player is fraud"),
        ("!ballon_dor", "Ballon d'Or of the squad"),
        ("!ghost_detector", "Detect inactive players"),
        ("!pass_the_ball <player>", "Call out ball hog"),
        ("!personality <mode>", "Switch personality (casablanca/analyst/toxic/coach/commentator/cafeteria)"),
        ("!sync", "Sync from all sources (skips duplicates)"),
        ("!force_sync", "🔥 Drill ALL data sources"),
        ("!raw_data", "Show summary of last scraped data"),
        ("!test_scraper", "Test all data sources"),
        ("!addmatch <opponent> <score> [stats]", "MANUAL: Add match result\nEx: !addmatch Barca 3-2 Shark:2G,1A"),
        ("!addplayerstats <match_id> <stats>", "MANUAL: Add stats to existing match"),
        ("!listmatches", "List all stored matches"),
        ("!help", "This message")
    ]
    for cmd, desc in commands_list:
        embed.add_field(name=cmd, value=desc, inline=False)
    embed.set_footer(text="Rachad L3ERGONI Pro Clubs | Made with 🔥 for the squad")
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
    print(f"[Health] Server running on port {PORT}")


async def main():
    await start_health_server()
    await asyncio.sleep(1)
    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
