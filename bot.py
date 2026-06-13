"""
Rachad L3ERGONI Bot - FIXED VERSION
"""

import os
import sys
import asyncio
import traceback

print("[STARTUP] Step 1: Imports starting...")

try:
    import discord
    from discord.ext import commands
    from dotenv import load_dotenv
    load_dotenv()
    print("[STARTUP] ✅ Core imports OK")
except Exception as e:
    print(f"[STARTUP] ❌ Core import failed: {e}")
    sys.exit(1)

print("[STARTUP] Step 2: Loading env vars...")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MATCH_CHANNEL_ID = int(os.getenv("MATCH_CHANNEL_ID", "0"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID", "0"))
GENERAL_CHANNEL_ID = int(os.getenv("GENERAL_CHANNEL_ID", "0"))
CLUB_ID = os.getenv("CLUB_ID", "1427607")
PLATFORM = os.getenv("PLATFORM", "common-gen5")
PORT = int(os.getenv("PORT", "10000"))

print(f"[STARTUP] ✅ Env vars: CLUB_ID={CLUB_ID}, PLATFORM={PLATFORM}")

print("[STARTUP] Step 3: Loading custom modules...")

# Initialize all to None first
darija = None
stats_engine = None
image_gen = None
scraper = None
PERSONALITIES = {}

try:
    from darija_engine import get_engine, PERSONALITIES as DARija_PERSONALITIES
    PERSONALITIES = DARija_PERSONALITIES
    darija = get_engine("squad.json")
    print("[STARTUP] ✅ darija_engine OK")
except Exception as e:
    print(f"[STARTUP] ⚠️ darija_engine: {e}")

try:
    from stats_engine import get_stats_engine
    stats_engine = get_stats_engine("match_data.json")
    print("[STARTUP] ✅ stats_engine OK")
except Exception as e:
    print(f"[STARTUP] ⚠️ stats_engine: {e}")

try:
    from image_gen import get_image_generator
    image_gen = get_image_generator("assets")
    print("[STARTUP] ✅ image_gen OK")
except Exception as e:
    print(f"[STARTUP] ⚠️ image_gen: {e}")

try:
    from scraper import get_scraper
    scraper = get_scraper(CLUB_ID, PLATFORM)
    print("[STARTUP] ✅ scraper OK")
except Exception as e:
    print(f"[STARTUP] ⚠️ scraper: {e}")
    traceback.print_exc()

print("[STARTUP] Step 4: Setting up Discord bot...")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class L3ERGONIBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        print("[STARTUP] ✅ Bot class created")
        
    async def setup_hook(self):
        print("[SETUP] setup_hook called")
        self.darija = darija
        self.stats = stats_engine
        self.images = image_gen
        self.scraper = scraper
        self.squad = self._load_squad()
        self.session_active = False
        print("[SETUP] ✅ Attributes set")

    def _load_squad(self) -> dict:
        try:
            import json
            with open("squad.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[SQUAD] ⚠️ Load failed: {e}")
            return {}

    async def on_ready(self):
        print(f"[READY] ✅ Bot ready: {self.user}")
        print(f"[READY] ✅ Guilds: {len(self.guilds)}")
        print(f"[READY] ✅ Commands: {len(self.commands)}")
        for cmd in self.commands:
            print(f"  - {cmd.name}")
        
    async def on_command_error(self, ctx, error):
        print(f"[ERROR] {error}")
        if isinstance(error, commands.CommandNotFound):
            print(f"[ERROR] Command not found: {ctx.message.content}")

    async def on_message(self, message):
        if message.author.bot:
            return
        print(f"[MESSAGE] '{message.content}' from {message.author}")
        await self.process_commands(message)

bot = L3ERGONIBot()
bot.remove_command('help')

@bot.command(name="ping")
async def ping_cmd(ctx):
    print(f"[COMMAND] !ping from {ctx.author}")
    await ctx.send("🏓 Pong!")

@bot.command(name="sync")
async def sync_cmd(ctx):
    print(f"[COMMAND] !sync from {ctx.author}")
    if bot.scraper is None:
        await ctx.send("❌ Scraper not available. Check logs.")
        return
    await ctx.send("🔥 Syncing from ProClubsTracker...")
    try:
        added = await bot.scraper.sync_to_stats_engine(bot.stats, count=10)
        await ctx.send(f"✅ Synced {added} matches!")
    except Exception as e:
        print(f"[SYNC] Error: {e}")
        traceback.print_exc()
        await ctx.send(f"❌ Error: {e}")

@bot.command(name="force_sync")
async def force_sync_cmd(ctx):
    print(f"[COMMAND] !force_sync from {ctx.author}")
    if bot.scraper is None:
        await ctx.send("❌ Scraper not available")
        return
    await ctx.send("🔥 Drilling ProClubsTracker for ALL data...")
    try:
        all_data = await bot.scraper.scrape_all()
        if not all_data:
            await ctx.send("❌ No data scraped")
            return
        
        matches = all_data.get("matches", [])
        players = all_data.get("players", [])
        
        added = 0
        for match in matches:
            parsed = bot.scraper._convert_match(match, players)
            if parsed:
                bot.stats.add_match(parsed)
                added += 1
        
        # Save raw data
        with open("proclubstracker_raw.json", "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)
        
        await ctx.send(f"🔥 Force synced {added} matches! Data saved.")
    except Exception as e:
        print(f"[FORCE_SYNC] Error: {e}")
        traceback.print_exc()
        await ctx.send(f"❌ Error: {e}")

@bot.command(name="lastmatch")
async def lastmatch_cmd(ctx):
    print(f"[COMMAND] !lastmatch from {ctx.author}")
    match = bot.stats.get_last_match()
    if not match:
        await ctx.send("z3ma... last match? walo. chi m3a9ed. safi.")
        return
    
    roast = bot.darija.roast_match_result(match.team_goals, match.opponent_goals, match.opponent) if bot.darija else "No roast engine"
    match_dict = match.to_dict()
    
    import io
    card = bot.images.generate_match_report_card(match_dict) if bot.images else None
    if card:
        card_bytes = bot.images.to_bytes(card)
        file = discord.File(io.BytesIO(card_bytes), filename="match_report.png")
        embed = discord.Embed(
            title=f"Match: {match.team_goals}-{match.opponent_goals} vs {match.opponent}",
            description=roast,
            color=0x00FF00 if match.result == "win" else 0xFF0000
        )
        embed.set_image(url="attachment://match_report.png")
        await ctx.send(embed=embed, file=file)
    else:
        await ctx.send(f"Last match: {match.team_goals}-{match.opponent_goals} vs {match.opponent} ({match.result})")

@bot.command(name="stats")
async def stats_cmd(ctx, *, player_name: str):
    print(f"[COMMAND] !stats from {ctx.author} for {player_name}")
    key = player_name.lower().strip()
    info = bot.squad.get(key, {})
    if not info:
        await ctx.send(f"z3ma... {player_name}? walo. chi m3a9ed. safi.")
        return
    
    name = info.get("name", player_name)
    stats = bot.stats.get_player_stats(name, 5)
    if not stats:
        await ctx.send(f"z3ma... stats dial {name}? walo. chi m3a9ed. safi.")
        return
    
    import io
    card = bot.images.generate_player_card(name, stats, info) if bot.images else None
    if card:
        card_bytes = bot.images.to_bytes(card)
        roasts = bot.darija.roast_player(name, stats, 5) if bot.darija else ["No roast engine"]
        roast_text = "\n".join(roasts)
        
        embed = discord.Embed(title=f"{info.get('nickname', name)} - Stats", description=roast_text, color=0xFF6B35)
        file = discord.File(io.BytesIO(card_bytes), filename="player_card.png")
        embed.set_image(url="attachment://player_card.png")
        await ctx.send(embed=embed, file=file)
    else:
        await ctx.send(f"Stats for {name}: {stats}")

@bot.command(name="help")
async def help_cmd(ctx):
    print(f"[COMMAND] !help from {ctx.author}")
    embed = discord.Embed(
        title="Rachad L3ERGONI Bot",
        description="ProClubsTracker.com Scraper | Darija Roast | Real Photos",
        color=0xFF6B35
    )
    commands_list = [
        ("!ping", "Test if bot works"),
        ("!sync", "Sync from ProClubsTracker (skips duplicates)"),
        ("!force_sync", "🔥 Drill ALL data from ProClubsTracker"),
        ("!lastmatch", "Show last match with card"),
        ("!stats <name>", "Player stats with premium card"),
        ("!help", "This message")
    ]
    for cmd, desc in commands_list:
        embed.add_field(name=cmd, value=desc, inline=False)
    await ctx.send(embed=embed)

# Health server
async def start_health_server():
    from aiohttp import web
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Rachad L3ERGONI Bot OK 🔥"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"[HEALTH] Server on port {PORT}")

async def main():
    print("[STARTUP] Step 5: Starting services...")
    await start_health_server()
    print("[STARTUP] ✅ Health server started")
    await asyncio.sleep(1)
    print("[STARTUP] Step 6: Starting bot...")
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    print("[STARTUP] ========== RACHAD L3ERGONI BOT ==========")
    asyncio.run(main())
