"""
Rachad L3ERGONI Bot - Working Version
"""

import os
import io
import asyncio
import json
from datetime import datetime

import discord
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

bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command('help')

@bot.event
async def on_ready():
    print(f"✅ Bot ready: {bot.user}")

@bot.command(name="ping")
async def ping_cmd(ctx):
    await ctx.send("🏓 Pong!")

@bot.command(name="sync")
async def sync_cmd(ctx):
    await ctx.send("🔥 Syncing...")
    try:
        added = await scraper.sync_to_stats_engine(stats_engine, count=10)
        await ctx.send(f"✅ Synced {added} matches!")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command(name="force_sync")
async def force_sync_cmd(ctx):
    await ctx.send("🔥 Force syncing...")
    try:
        data = await scraper.scrape_all()
        matches = data.get("matches", [])
        for match in matches:
            parsed = scraper._convert_match(match, [])
            if parsed:
                stats_engine.add_match(parsed)
        await ctx.send(f"✅ Synced {len(matches)} matches!")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command(name="lastmatch")
async def lastmatch_cmd(ctx):
    match = stats_engine.get_last_match()
    if not match:
        await ctx.send("z3ma... last match? walo. chi m3a9ed. safi.")
        return
    await ctx.send(f"Last match: {match.team_goals}-{match.opponent_goals} vs {match.opponent}")

@bot.command(name="clubinfo")
async def clubinfo_cmd(ctx):
    team_stats = stats_engine.get_team_stats(20)
    if not team_stats:
        await ctx.send("z3ma... club info? walo. chi m3a9ed. safi.")
        return
    await ctx.send(f"Matches: {team_stats['matches']} | Wins: {team_stats['wins']}")

@bot.command(name="help")
async def help_cmd(ctx):
    await ctx.send("Commands: !ping, !sync, !force_sync, !lastmatch, !clubinfo, !help")

# Health server
async def start_health_server():
    from aiohttp import web
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

async def main():
    await start_health_server()
    await asyncio.sleep(1)
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
