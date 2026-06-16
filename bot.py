import os
import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import Config, load_squad
from scraper import ProClubsTrackerScraper
from stats_engine import StatsEngine
from darija_engine import DarijaEngine
from image_gen import ImageGenerator
from memory import SquadMemory
from daily_engine import DailyEngine
from story_engine import StoryEngine
from models import ClubStats, PlayerStats
from utils import fuzzy_find_player

# === PHASE 2.1: Nickname System ===
PSN_TO_NICKNAME: dict = {}
NICKNAME_TO_PSN: dict = {}

def _build_nickname_maps():
    global PSN_TO_NICKNAME, NICKNAME_TO_PSN
    PSN_TO_NICKNAME.clear()
    NICKNAME_TO_PSN.clear()
    players_iter = []
    if isinstance(squad, dict):
        if "players" in squad:
            players_iter = squad.get("players", [])
        else:
            players_iter = squad.values()
    elif isinstance(squad, list):
        players_iter = squad
    for p in players_iter:
        if not isinstance(p, dict):
            continue
        psn = p.get("psn", "") or p.get("PSN", "") or p.get("ea_id", "")
        nickname = p.get("name", "") or p.get("nickname", "")
        if psn and nickname:
            PSN_TO_NICKNAME[psn.lower()] = nickname
            NICKNAME_TO_PSN[nickname.lower()] = psn

def resolve_nickname(name: str) -> str:
    if not name or not isinstance(name, str):
        return name
    return PSN_TO_NICKNAME.get(name.lower(), name)

def resolve_query(query: str) -> str:
    if not query or not isinstance(query, str):
        return query
    return PSN_TO_NICKNAME.get(query.lower(), query)

def normalize_club_players(club):
    if not club or not getattr(club, "players", None):
        return
    for p in club.players:
        if hasattr(p, "name") and isinstance(p.name, str):
            p.name = resolve_nickname(p.name)

# === Health Check Server ===
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def start_health_server():
    try:
        server = HTTPServer(("0.0.0.0", Config.PORT), HealthHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        print(f"Health server on port {Config.PORT}")
    except Exception as e:
        print(f"Health server error: {e}")

start_health_server()

# === Bot Setup ===
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

squad = load_squad()
_build_nickname_maps()
scraper: Optional[ProClubsTrackerScraper] = None
darija = DarijaEngine(Config.DEFAULT_PERSONALITY)
imgen = ImageGenerator(Config.ASSETS_DIR)
memory = SquadMemory()
daily_engine = DailyEngine(darija)
story_engine = StoryEngine()
current_club: Optional[ClubStats] = None
_session_active = False

def get_squad_map():
    return {p.get("name", ""): p for p in squad.get("players", [])}

def find_player(query: str) -> Optional[PlayerStats]:
    if not current_club or not current_club.players:
        return None
    resolved = resolve_query(query)
    return fuzzy_find_player(resolved, current_club.players, squad)

async def ensure_data(ctx):
    global current_club
    if current_club and current_club.players:
        return True
    if not scraper:
        await ctx.send("Scraper not ready. Wait 10s.")
        return False
    async with ctx.typing():
        await ctx.send("جاري جلب البيانات...")
        try:
            club = await scraper.scrape_club()
            if not club or not club.players:
                await ctx.send("ما قدرتش نجيب البيانات من ProClubsTracker. جرب !sync مرة أخرى.")
                return False
            current_club = club
            current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
            normalize_club_players(current_club)
            await ctx.send(f"Loaded {len(club.players)} players")
            return True
        except Exception as e:
            tb = traceback.format_exc()
            print(f"SCRAPE ERROR: {tb}")
            await ctx.send(f"Scrape failed: {str(e)[:800]}")
            return False

async def ensure_data_interaction(interaction: discord.Interaction):
    global current_club
    if current_club and current_club.players:
        return True
    if not scraper:
        await interaction.followup.send("Scraper not ready.")
        return False
    try:
        await interaction.followup.send("جاري جلب البيانات...")
        club = await scraper.scrape_club()
        if not club or not club.players:
            await interaction.followup.send("ما قدرتش نجيب البيانات من ProClubsTracker. جرب /sync مرة أخرى.")
            return False
        current_club = club
        current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
        normalize_club_players(current_club)
        await interaction.followup.send(f"Loaded {len(club.players)} players")
        return True
    except Exception as e:
        tb = traceback.format_exc()
        print(f"SCRAPE ERROR: {tb}")
        await interaction.followup.send(f"Scrape failed: {str(e)[:800]}")
        return False

# === Events ===
@bot.event
async def on_ready():
    global scraper
    print(f"Bot online as {bot.user}")
    scraper = ProClubsTrackerScraper(Config.PCT_CLUB_URL)
    await bot.change_presence(activity=discord.Game(name="!help or /help"))
    try:
        guild = discord.Object(id=Config.DISCORD_GUILD_ID)
        bot.tree.clear_commands(guild=guild)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"Slash synced to {Config.DISCORD_GUILD_ID}")
    except Exception as e:
        print(f"Slash sync: {e}")
    asyncio.create_task(startup_scrape())
    daily_post.start()
    match_monitor.start()

async def startup_scrape():
    global current_club
    try:
        print("Startup scrape...")
        club = await scraper.scrape_club()
        if club and club.players:
            current_club = club
            current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
            normalize_club_players(current_club)
            print(f"Startup: {len(club.players)} players")
        else:
            print("Startup: no data")
    except Exception as e:
        print(f"Startup scrape: {e}")
        traceback.print_exc()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("هاد الكوماند ما كاينش. جرب !help باش تشوف الكوماندات.")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"ناقصك parameter: {error.param.name}.")
        return
    if isinstance(error, commands.NotOwner):
        await ctx.send("غير الowner يقدر يدير هاد الكوماند.")
        return
    print(f"Prefix error: {error}")
    traceback.print_exc()
    await ctx.send(f"Error: {str(error)[:300]}")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    print(f"Slash error: {error}")
    traceback.print_exc()
    msg = f"Error: {str(error)[:500]}"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg)
        else:
            await interaction.response.send_message(msg)
    except Exception:
        pass

# === DAILY LOOP ===
@tasks.loop(hours=24)
async def daily_post():
    channel_id = getattr(Config, "DAILY_CHANNEL_ID", 0)
    if not channel_id or not current_club or not current_club.players:
        return
    try:
        channel = bot.get_channel(channel_id)
        if not channel:
            return
        pick = daily_engine.pick_stat_of_the_day(current_club.players)
        if not pick:
            return
        is_bad = pick.get("type") == "bad"
        card = imgen.generate_daily_card(pick["player"], pick["stat_name"], pick["stat_value"], pick["roast"], is_bad)
        file = discord.File(card, filename="daily.png")
        embed = discord.Embed(title=pick["title"], description=pick["roast"], color=0xff0000 if is_bad else 0xffd700)
        await channel.send(embed=embed, file=file)
    except Exception as e:
        print(f"Daily post error: {e}")

@daily_post.before_loop
async def before_daily():
    await bot.wait_until_ready()

# === MATCH AUTO-REPORTING (PHASE 3) ===
_last_match_id = None

@tasks.loop(minutes=5)
async def match_monitor():
    global _last_match_id, current_club
    if not current_club or not current_club.matches or not scraper:
        return
    try:
        fresh_club = await scraper.scrape_club()
        if not fresh_club or not fresh_club.matches:
            return
        latest = fresh_club.matches[0]
        match_id = getattr(latest, "match_id", None) or f"{latest.date}_{latest.opponent}"
        if _last_match_id is None:
            _last_match_id = match_id
            return
        if match_id == _last_match_id:
            return
        _last_match_id = match_id
        current_club = fresh_club
        current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
        normalize_club_players(current_club)
        result = f"{latest.score_for}-{latest.score_against}"
        report = darija.match_report(result, current_club.players)
        match_channel_id = getattr(Config, "MATCH_CHANNEL_ID", 0)
        if match_channel_id:
            match_channel = bot.get_channel(match_channel_id)
            if match_channel:
                await match_channel.send(report)
        leaderboard_channel_id = getattr(Config, "LEADERBORD_CHANNEL_ID", 0)
        if leaderboard_channel_id:
            lb_channel = bot.get_channel(leaderboard_channel_id)
            if lb_channel:
                color = 0x00ff00 if latest.result == "W" else 0xff0000 if latest.result == "L" else 0xffff00
                embed = discord.Embed(title=f"Match Report: {latest.opponent} {result}", description=report, color=color)
                await lb_channel.send(embed=embed)
        print(f"Auto-reported match: {latest.opponent} {result}")
    except Exception as e:
        print(f"Match monitor error: {e}")
        traceback.print_exc()

@match_monitor.before_loop
async def before_match_monitor():
    await bot.wait_until_ready()

# ============================================================
# PREFIX COMMANDS
# ============================================================

@bot.command(name="ping")
async def cmd_ping(ctx):
    await ctx.send("Pong! Bot is alive. Try !sync next.")

@bot.command(name="debug")
async def cmd_debug(ctx):
    scraper_ready = "Yes" if scraper else "No"
    data_loaded = "Yes" if current_club and current_club.players else "No"
    player_count = len(current_club.players) if current_club and current_club.players else 0
    lines = [
        f"PCT_URL: {Config.PCT_CLUB_URL}",
        f"PORT: {Config.PORT}",
        f"Club ID: {Config.CLUB_ID}",
        f"Platform: {Config.PCT_PLATFORM}",
        f"Scraper ready: {scraper_ready}",
        f"Data loaded: {data_loaded}",
        f"Players: {player_count}",
    ]
    embed = discord.Embed(title="Debug Info", description="\n".join(lines), color=0x808080)
    await ctx.send(embed=embed)

@bot.command(name="resync")
@commands.is_owner()
async def cmd_resync(ctx):
    async with ctx.typing():
        try:
            guild = discord.Object(id=Config.DISCORD_GUILD_ID)
            bot.tree.clear_commands(guild=guild)
            await bot.tree.sync(guild=guild)
            await ctx.send("Slash commands re-synced. Try /leaderboard now.")
        except Exception as e:
            await ctx.send(f"Resync failed: {e}")

@bot.command(name="help")
async def cmd_help(ctx):
    embed = discord.Embed(
        title="Rachad L3ERGONI Bot",
        description="الخطوة الأولى: دير !sync أو /sync\n\nبعدها تقدر تستعمل كل شي:",
        color=0x1e90ff
    )
    cmds = [
        ("!ping", "تأكد من أن البوت كيهضر"),
        ("!debug", "معلومات تقنية"),
        ("!resync", "إصلاح slash commands"),
        ("!sync / /sync", "جلب البيانات"),
        ("!stats [player] / /stats", "إحصائيات لاعب + anime card"),
        ("!player [player] / /player", "البروفيل الكامل"),
        ("!mvp / /mvp", "أفضل لاعب + anime MVP card"),
        ("!worst / /worst", "أسوأ لاعب"),
        ("!who_sold / /who_sold", "شكون باع الماتش"),
        ("!carry / /carry_detector", "شكون كيجرّ الفريق"),
        ("!fraud [player] / /fraud_check", "فحص الفريق + anime fraud card"),
        ("!ballon / /ballon_dor", "ترتيب Ballon d Or"),
        ("!ghost / /ghost_detector", "كشف الغيّاب + anime ghost card"),
        ("!pass / /pass_the_ball", "نادِي على اللي كيضيع الكورة"),
        ("!ball_loser / /ball_loser", "أكثر واحد كيضيع الكورة"),
        ("!playmaker / /playmaker", "أحسن creator"),
        ("!sniper / /sniper", "أحسن finisher"),
        ("!keeper / /keeper", "أحسن حارس"),
        ("!leaderboard [metric] / /leaderboard", "لوحة المتصدرين anime style"),
        ("!compare p1 p2 / /compare", "مقارنة 1v1"),
        ("!lastmatch / /lastmatch", "آخر ماتش"),
        ("!club / /clubinfo", "معلومات النادي"),
        ("!history [player] / /history", "تاريخ اللاعب"),
        ("!rankings / /rankings", "كل الترتيبات"),
        ("!awards / /awards", "جوائز الموسم"),
        ("!anime_card [player] / /anime_card", "كارطة anime premium"),
        ("!beast_mode [player] / /beast_mode", "Beast Mode card"),
        ("!court_case [player] / /court_case", "محاكمة اللاعب"),
        ("!serial_offender [player] / /serial_offender", "المجرم المتسلسل"),
        ("!hall_of_shame / /hall_of_shame", "صالة العار"),
        ("!daily / /daily", "Stat of the Day يدوي"),
        ("!story / /story", "قصة اليوم"),
        ("!banter / /banter", "هضرة رياضية"),
        ("!drama / /drama", "دراما"),
        ("!meme [player] / /meme", "ميم بالدارجة"),
        ("!transfer [player] / /transfer", "إشاعة انتقال"),
        ("!predict / /predict", "توقع الماتش"),
        ("!personality [mode] / /personality", "تبديل الشخصية"),
        ("!roast / /roast", "بدء session monitoring"),
        ("!stop / /stop", "إيقاف session"),
        ("!roastplayer [player] / /roastplayer", "Roast لاعب"),
    ]
    for cmd, desc in cmds:
        embed.add_field(name=cmd, value=desc, inline=False)
    await ctx.send(embed=embed)

@bot.command(name="sync")
async def cmd_sync(ctx):
    async with ctx.typing():
        try:
            if not scraper:
                await ctx.send("Scraper not ready.")
                return
            global current_club
            club = await scraper.scrape_club()
            if not club or not club.players:
                await ctx.send("ما قدرتش نجيب البيانات. شوف Render logs.")
                return
            current_club = club
            current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
            normalize_club_players(current_club)
            embed = discord.Embed(
                title="Sync Complete",
                description=f"{len(club.players)} players loaded\nClub: {club.club_name} | Div {club.division}\nRecord: {club.wins}W — {club.losses}L — {club.draws}D",
                color=0x00ff00
            )
            await ctx.send(embed=embed)
        except Exception as e:
            tb = traceback.format_exc()
            print(f"SYNC ERROR: {tb}")
            await ctx.send(f"Sync failed: {str(e)[:800]}")

# === PHASE 1 COMMANDS (updated for PHASE 3 roast-first) ===

@bot.command(name="stats")
async def cmd_stats(ctx, *, player: str):
    if not await ensure_data(ctx): return
    target = find_player(player)
    if not target:
        await ctx.send(f"ما لقيتش `{player}`.")
        return
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    async with ctx.typing():
        try:
            card = imgen.generate_player_card(target, pos, division=current_club.division)
            file = discord.File(card, filename=f"{target.name}_card.png")
            roast_text = darija.roast(target, pos)
            embed = discord.Embed(title=f"📊 {target.name} — {pos}", description=roast_text, color=0x1e90ff)
            embed.add_field(name="Impact", value=str(target.impact_score), inline=True)
            embed.add_field(name="Clutch", value=str(target.clutch_score), inline=True)
            embed.add_field(name="Error", value=str(target.error_score), inline=True)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="mvp")
async def cmd_mvp(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            normalize_club_players(current_club)
            mvp = StatsEngine.get_mvp(current_club.players)
            pos = squad_map.get(mvp.name, {}).get("position", "CM")
            card = imgen.generate_mvp_card(mvp, pos)
            file = discord.File(card, filename="mvp.png")
            mvp_text = darija.mvp(mvp)
            embed = discord.Embed(title="🏆 MAN OF THE MATCH", description=mvp_text, color=0xffd700)
            embed.add_field(name="Goals", value=str(mvp.goals), inline=True)
            embed.add_field(name="Assists", value=str(mvp.assists), inline=True)
            embed.add_field(name="Rating", value=str(round(mvp.rating_pg, 1)), inline=True)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="worst")
async def cmd_worst(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            normalize_club_players(current_club)
            worst = StatsEngine.get_worst(current_club.players)
            pos = squad_map.get(worst.name, {}).get("position", "CM")
            roast = darija.roast(worst, pos)
            embed = discord.Embed(title="🗑️ WORST PLAYER", description=roast, color=0x8b0000)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="who_sold")
async def cmd_who_sold(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            normalize_club_players(current_club)
            fraud = StatsEngine.get_fraud(current_club.players)
            pos = squad_map.get(fraud.name, {}).get("position", "CM")
            roast = darija.fraud(fraud)
            embed = discord.Embed(title="🎭 FRAUD DETECTED", description=roast, color=0xff4500)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="carry")
async def cmd_carry(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            normalize_club_players(current_club)
            carry = StatsEngine.get_carry(current_club.players)
            pos = squad_map.get(carry.name, {}).get("position", "CM")
            praise = darija.carry(carry)
            embed = discord.Embed(title="💪 CARRY DETECTED", description=praise, color=0x00ff00)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="fraud")
async def cmd_fraud(ctx, *, player: str):
    if not await ensure_data(ctx): return
    target = find_player(player)
    if not target:
        await ctx.send(f"ما لقيتش `{player}`.")
        return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            pos = squad_map.get(target.name, {}).get("position", "CM")
            is_fraud = target.throwing_score > 3.0
            if is_fraud:
                text = darija.fraud(target)
                color = 0xff0000
            else:
                text = f"✅ CLEAN\n\n{target.name} — Throwing: {target.throwing_score}\n\nهادا لاعب صحيح."
                color = 0x00ff00
            embed = discord.Embed(title="FRAUD CHECK", description=text, color=color)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="ballon")
async def cmd_ballon(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            normalize_club_players(current_club)
            ranked = sorted(current_club.players, key=lambda p: p.impact_score + p.clutch_score + p.goals * 2, reverse=True)
            embed = discord.Embed(title="🏆 BALLON D'OR", color=0xffd700)
            medals = ["🥇", "🥈", "🥉"]
            for i, p in enumerate(ranked[:5]):
                medal = medals[i] if i < 3 else f"{i+1}."
                embed.add_field(name=f"{medal} {p.name}", value=f"Impact: {p.impact_score} | Goals: {p.goals} | Rating: {round(p.rating_pg, 1)}", inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="ghost")
async def cmd_ghost(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            normalize_club_players(current_club)
            ghost = StatsEngine.get_ghost(current_club.players)
            pos = squad_map.get(ghost.name, {}).get("position", "CM")
            roast = darija.ghost(ghost)
            embed = discord.Embed(title="👻 GHOST DETECTED", description=roast, color=0x9370db)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="pass")
async def cmd_pass(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            normalize_club_players(current_club)
            hog = StatsEngine.get_ball_hog(current_club.players)
            pos = squad_map.get(hog.name, {}).get("position", "CM")
            roast = darija.ball_loser(hog)
            embed = discord.Embed(title="⚽ PASS THE BALL!", description=roast, color=0xffa500)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="leaderboard")
async def cmd_leaderboard(ctx, metric: str = "impact"):
    if not await ensure_data(ctx): return
    metric_map = {"impact": "impact_score", "goals": "goals", "assists": "assists", "rating": "rating_pg", "clutch": "clutch_score"}
    metric_value = metric_map.get(metric.lower(), "impact_score")
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            normalize_club_players(current_club)
            card = imgen.generate_leaderboard(current_club.players, metric_value)
            file = discord.File(card, filename="leaderboard.png")
            embed = discord.Embed(title=f"📊 Leaderboard — {metric.capitalize()}", color=0x1e90ff)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="compare")
async def cmd_compare(ctx, player1: str, player2: str):
    if not await ensure_data(ctx): return
    p1 = find_player(player1)
    p2 = find_player(player2)
    if not p1 or not p2:
        await ctx.send("ما لقيتش players.")
        return
    async with ctx.typing():
        try:
            text = darija.compare(p1, p2)
            embed = discord.Embed(title="⚔️ 1v1 COMPARISON", description=text, color=0xff4500)
            embed.add_field(name=p1.name, value=f"Impact: {p1.impact_score}\nGoals: {p1.goals}\nAssists: {p1.assists}\nRating: {round(p1.rating_pg, 1)}", inline=True)
            embed.add_field(name=p2.name, value=f"Impact: {p2.impact_score}\nGoals: {p2.goals}\nAssists: {p2.assists}\nRating: {round(p2.rating_pg, 1)}", inline=True)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="lastmatch")
async def cmd_lastmatch(ctx):
    if not await ensure_data(ctx): return
    if not current_club.matches:
        await ctx.send("ما لقيتش match history.")
        return
    try:
        last = current_club.matches[0]
        color = 0x00ff00 if last.result == "W" else 0xff0000 if last.result == "L" else 0xffff00
        embed = discord.Embed(title=f"⚽ Last Match: {last.score_for} - {last.score_against} vs {last.opponent}", description=f"Result: {last.result} • {last.date.strftime('%d/%m/%Y')}", color=color)
        await ctx.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="club")
async def cmd_club(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            normalize_club_players(current_club)
            motm = StatsEngine.get_mvp(current_club.players)
            card = imgen.generate_match_report(current_club, motm)
            file = discord.File(card, filename="club_report.png")
            embed = discord.Embed(title=f"🏟️ {current_club.club_name}", description=f"Division {current_club.division} • Skill {current_club.skill_rating}", color=0x00ff00)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="banter")
async def cmd_banter(ctx):
    try:
        text = darija.banter()
        embed = discord.Embed(title="☕ Cafeteria Banter", description=text, color=0xffa500)
        await ctx.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="drama")
async def cmd_drama(ctx):
    if not await ensure_data(ctx): return
    try:
        names = [p.name for p in current_club.players[:2]] if current_club.players else ["Player1", "Player2"]
        text = darija.drama(names)
        embed = discord.Embed(title="🍿 Drama Alert", description=text, color=0xff1493)
        await ctx.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="meme")
async def cmd_meme(ctx, *, player: str = "Player"):
    try:
        text = darija.meme(resolve_nickname(player))
        embed = discord.Embed(title="😂 Darija Meme", description=text, color=0x00ff7f)
        await ctx.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="transfer")
async def cmd_transfer(ctx, *, player: str):
    try:
        text = darija.transfer(resolve_nickname(player))
        embed = discord.Embed(title="📰 Transfer News", description=text, color=0x1e90ff)
        await ctx.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="predict")
async def cmd_predict(ctx):
    if not await ensure_data(ctx): return
    try:
        names = [p.name for p in current_club.players[:2]] if current_club.players else ["Player1", "Player2"]
        text = darija.predict(names)
        embed = discord.Embed(title="🔮 Match Prediction", description=text, color=0x9400d3)
        await ctx.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="personality")
async def cmd_personality(ctx, mode: str):
    valid = ["casablanca", "analyst", "toxic", "coach", "commentator", "cafeteria"]
    if mode.lower() not in valid:
        await ctx.send(f"Personality غير صحيح. Valid: {', '.join(valid)}")
        return
    try:
        darija.set_personality(mode.lower())
        embed = discord.Embed(title="🎭 Personality Switch", description=f"Changed to: **{mode.capitalize()}**", color=0x9370db)
        await ctx.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="roast")
async def cmd_roast(ctx):
    global _session_active
    _session_active = True
    darija.set_personality("casablanca")
    embed = discord.Embed(title="🔥 ROAST MODE ACTIVATED", description="Session monitoring started.", color=0xff4500)
    await ctx.send(embed=embed)

@bot.command(name="stop")
async def cmd_stop(ctx):
    global _session_active
    _session_active = False
    await ctx.send("⏹️ Session Stopped.")

@bot.command(name="roastplayer")
async def cmd_roastplayer(ctx, *, player: str):
    if not await ensure_data(ctx): return
    target = find_player(player)
    if not target:
        await ctx.send(f"ما لقيتش `{player}`.")
        return
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    async with ctx.typing():
        try:
            roast = darija.roast(target, pos)
            card = imgen.generate_roast_card(target, roast, pos)
            file = discord.File(card, filename=f"{target.name}_roast.png")
            embed = discord.Embed(title=f"🔥 ROAST REPORT — {target.name}", description=roast, color=0xff0000)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

# === NEW PHASE 3 COMMANDS ===

@bot.command(name="serial_offender")
async def cmd_serial_offender(ctx, *, player: str):
    if not await ensure_data(ctx): return
    target = find_player(player)
    if not target:
        await ctx.send(f"ما لقيتش `{player}`.")
        return
    async with ctx.typing():
        try:
            bad_games = memory.get_consecutive_bad_games(target.name) if hasattr(memory, 'get_consecutive_bad_games') else 0
            text = darija.serial_offender(target, bad_games)
            embed = discord.Embed(title=f"🚨 Serial Offender — {target.name}", description=text, color=0x8b0000)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="hall_of_shame")
async def cmd_hall_of_shame(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            normalize_club_players(current_club)
            text = darija.hall_of_shame(current_club.players)
            embed = discord.Embed(title="🏛️ Hall of Shame", description=text, color=0x8b0000)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

# === PHASE 2 COMMANDS (updated for PHASE 3) ===

@bot.command(name="player")
async def cmd_player(ctx, *, player: str):
    if not await ensure_data(ctx): return
    target = find_player(player)
    if not target:
        await ctx.send(f"ما لقيتش `{player}`.")
        return
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    async with ctx.typing():
        try:
            card = imgen.generate_anime_card(target, pos, "mvp", "PLAYER PROFILE")
            file = discord.File(card, filename=f"{target.name}_profile.png")
            lines = [
                f"**Position:** {pos}",
                f"**Games:** {target.games}",
                f"**Goals:** {target.goals} | **Assists:** {target.assists}",
                f"**Rating:** {round(target.rating_pg, 1)}",
                f"**Impact:** {target.impact_score} | **Clutch:** {target.clutch_score}",
                f"**Pass Accuracy:** {round(target.pass_accuracy, 1)}%",
                f"**Possession Lost:** {target.possession_losses}",
            ]
            embed = discord.Embed(title=f"👤 {target.name}", description="\n".join(lines), color=0x1e90ff)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="anime_card")
async def cmd_anime_card(ctx, *, player: str):
    if not await ensure_data(ctx): return
    target = find_player(player)
    if not target:
        await ctx.send(f"ما لقيتش `{player}`.")
        return
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    async with ctx.typing():
        try:
            card = imgen.generate_anime_card(target, pos, "beast", "⚡ ANIME LEGEND")
            file = discord.File(card, filename=f"{target.name}_anime.png")
            embed = discord.Embed(title=f"⚡ {target.name}", color=0x00ffff)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="beast_mode")
async def cmd_beast_mode(ctx, *, player: str = None):
    if not await ensure_data(ctx): return
    if player:
        target = find_player(player)
    else:
        target = max(current_club.players, key=lambda p: p.impact_score) if current_club.players else None
    if not target:
        await ctx.send("ما لقيتش player.")
        return
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    async with ctx.typing():
        try:
            card = imgen.generate_beast_card(target, pos)
            file = discord.File(card, filename="beast.png")
            embed = discord.Embed(title=f"⚡ BEAST MODE — {target.name}",
                                  description=f"Impact: {target.impact_score} | Goals: {target.goals} | Rating: {round(target.rating_pg, 1)}",
                                  color=0x00bfff)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="court_case")
async def cmd_court_case(ctx, *, player: str):
    if not await ensure_data(ctx): return
    target = find_player(player)
    if not target:
        await ctx.send(f"ما لقيتش `{player}`.")
        return
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    async with ctx.typing():
        try:
            text = darija.court_case(target)
            card = imgen.generate_court_case(target, pos, ["Evidence generated by Roast Engine"])
            file = discord.File(card, filename="court.png")
            color = 0xff0000 if target.throwing_score > 3.0 or target.rating_pg < 5.5 else 0x00ff00
            embed = discord.Embed(title=f"⚖️ COURT CASE: {target.name}", description=text, color=color)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="ball_loser")
async def cmd_ball_loser(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            normalize_club_players(current_club)
            loser = max(current_club.players, key=lambda p: p.possession_losses)
            pos = squad_map.get(loser.name, {}).get("position", "CM")
            roast = darija.ball_loser(loser)
            embed = discord.Embed(title="💀 BALL LOSER", description=roast, color=0x8b0000)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="playmaker")
async def cmd_playmaker(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            normalize_club_players(current_club)
            pm = max(current_club.players, key=lambda p: p.assists * 2 + p.pass_accuracy)
            pos = squad_map.get(pm.name, {}).get("position", "CM")
            text = darija.playmaker(pm)
            card = imgen.generate_playmaker_card(pm, pos)
            file = discord.File(card, filename="playmaker.png")
            embed = discord.Embed(title="🎨 PLAYMAKER", description=text, color=0x00ff00)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="sniper")
async def cmd_sniper(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            normalize_club_players(current_club)
            sniper = max(current_club.players, key=lambda p: p.goals * 2 + p.rating_pg)
            pos = squad_map.get(sniper.name, {}).get("position", "CM")
            card = imgen.generate_sniper_card(sniper, pos)
            file = discord.File(card, filename="sniper.png")
            embed = discord.Embed(title="🎯 SNIPER", description=f"**{sniper.name}** — {sniper.goals} goals | Rating: {round(sniper.rating_pg, 1)}", color=0xff4500)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="keeper")
async def cmd_keeper(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            normalize_club_players(current_club)
            gks = [p for p in current_club.players if squad_map.get(p.name, {}).get("position") == "GK"]
            if not gks:
                await ctx.send("ما لقيتش goalkeeper فالفريق.")
                return
            keeper = max(gks, key=lambda p: p.tackles + p.interceptions)
            text = darija.keeper(keeper)
            embed = discord.Embed(title="🧤 KEEPER", description=text, color=0x1e90ff)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="history")
async def cmd_history(ctx, *, player: str):
    if not await ensure_data(ctx): return
    target = find_player(player)
    if not target:
        await ctx.send(f"ما لقيتش `{player}`.")
        return
    try:
        mem = memory.get_player_memory(target.name)
        if not mem:
            await ctx.send(f"ما عنديش تاريخ لـ {target.name}.")
            return
        embed = discord.Embed(title=f"📜 History — {target.name}", color=0x9370db)
        embed.add_field(name="Total Games", value=mem["total_games"], inline=True)
        embed.add_field(name="Total Goals", value=mem["total_goals"], inline=True)
        embed.add_field(name="Total Assists", value=mem["total_assists"], inline=True)
        embed.add_field(name="Best Rating", value=mem["best_rating"], inline=True)
        embed.add_field(name="Worst Rating", value=mem["worst_rating"], inline=True)
        embed.add_field(name="Consecutive Bad", value=mem["consecutive_bad"], inline=True)
        await ctx.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="rankings")
async def cmd_rankings(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            normalize_club_players(current_club)
            embed = discord.Embed(title="📊 ALL RANKINGS", color=0x1e90ff)
            mvp = StatsEngine.get_mvp(current_club.players)
            worst = StatsEngine.get_worst(current_club.players)
            fraud = StatsEngine.get_fraud(current_club.players)
            carry = StatsEngine.get_carry(current_club.players)
            ghost = StatsEngine.get_ghost(current_club.players)
            embed.add_field(name="🏆 MVP", value=f"{mvp.name} (Impact: {mvp.impact_score})", inline=False)
            embed.add_field(name="🗑️ Worst", value=f"{worst.name} (Impact: {worst.impact_score})", inline=False)
            embed.add_field(name="🎭 Fraud", value=f"{fraud.name} (Throwing: {fraud.throwing_score})", inline=False)
            embed.add_field(name="💪 Carry", value=f"{carry.name} (Impact: {carry.impact_score})", inline=False)
            embed.add_field(name="👻 Ghost", value=f"{ghost.name} ({ghost.minutes_played}min)", inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="awards")
async def cmd_awards(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            normalize_club_players(current_club)
            embed = discord.Embed(title="🏅 SEASON AWARDS", color=0xffd700)
            mvp = StatsEngine.get_mvp(current_club.players)
            top_scorer = max(current_club.players, key=lambda p: p.goals)
            top_assist = max(current_club.players, key=lambda p: p.assists)
            fraud = StatsEngine.get_fraud(current_club.players)
            embed.add_field(name="🥇 Ballon d'Or", value=mvp.name, inline=False)
            embed.add_field(name="⚽ Golden Boot", value=f"{top_scorer.name} ({top_scorer.goals} goals)", inline=False)
            embed.add_field(name="🅰️ Playmaker Award", value=f"{top_assist.name} ({top_assist.assists} assists)", inline=False)
            embed.add_field(name="🤡 Fraud of the Season", value=f"{fraud.name} ({fraud.throwing_score} throwing)", inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="daily")
async def cmd_daily(ctx):
    if not await ensure_data(ctx): return
    async with ctx.typing():
        try:
            pick = daily_engine.pick_stat_of_the_day(current_club.players)
            if not pick:
                await ctx.send("ما قدرتش نجيب daily stat.")
                return
            is_bad = pick.get("type") == "bad"
            card = imgen.generate_daily_card(pick["player"], pick["stat_name"], pick["stat_value"], pick["roast"], is_bad)
            file = discord.File(card, filename="daily.png")
            embed = discord.Embed(title=pick["title"], description=pick["roast"], color=0xff0000 if is_bad else 0xffd700)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"Error: {str(e)[:300]}")

@bot.command(name="story")
async def cmd_story(ctx):
    if not await ensure_data(ctx): return
    try:
        text = story_engine.generate_story(current_club.players)
        embed = discord.Embed(title="📖 Story of the Day", description=text, color=0x9370db)
        await ctx.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await ctx.send(f"Error: {str(e)[:300]}")

# ============================================================
# SLASH COMMANDS
# ============================================================

@bot.tree.command(name="ping", description="Test if bot is responding")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! Try /sync next.")

@bot.tree.command(name="debug", description="Show bot state for troubleshooting")
async def slash_debug(interaction: discord.Interaction):
    scraper_ready = "Yes" if scraper else "No"
    data_loaded = "Yes" if current_club and current_club.players else "No"
    player_count = len(current_club.players) if current_club and current_club.players else 0
    lines = [
        f"PCT_URL: {Config.PCT_CLUB_URL}",
        f"PORT: {Config.PORT}",
        f"Club ID: {Config.CLUB_ID}",
        f"Platform: {Config.PCT_PLATFORM}",
        f"Scraper ready: {scraper_ready}",
        f"Data loaded: {data_loaded}",
        f"Players: {player_count}",
    ]
    embed = discord.Embed(title="Debug Info", description="\n".join(lines), color=0x808080)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="sync", description="Manual sync from ProClubsTracker")
async def slash_sync(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        if not scraper:
            await interaction.followup.send("Scraper not ready.")
            return
        global current_club
        club = await scraper.scrape_club()
        if not club or not club.players:
            await interaction.followup.send("ما قدرتش نجيب البيانات. شوف Render logs.")
            return
        current_club = club
        current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
        normalize_club_players(current_club)
        embed = discord.Embed(title="Sync Complete", description=f"{len(club.players)} players loaded", color=0x00ff00)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"SYNC ERROR: {tb}")
        await interaction.followup.send(f"Sync failed: {str(e)[:800]}")

@bot.tree.command(name="stats", description="Player stats + premium card")
@app_commands.describe(player="Player name, PSN, or nickname")
async def slash_stats(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    target = find_player(player)
    if not target:
        await interaction.followup.send(f"ما لقيتش `{player}`.")
        return
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    try:
        card = imgen.generate_player_card(target, pos, division=current_club.division)
        file = discord.File(card, filename=f"{target.name}_card.png")
        roast_text = darija.roast(target, pos)
        embed = discord.Embed(title=f"📊 {target.name} — {pos}", description=roast_text, color=0x1e90ff)
        embed.add_field(name="Impact", value=str(target.impact_score), inline=True)
        embed.add_field(name="Clutch", value=str(target.clutch_score), inline=True)
        embed.add_field(name="Error", value=str(target.error_score), inline=True)
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="player", description="Complete player profile with anime card")
@app_commands.describe(player="Player name")
async def slash_player(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    target = find_player(player)
    if not target:
        await interaction.followup.send(f"ما لقيتش `{player}`.")
        return
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    try:
        card = imgen.generate_anime_card(target, pos, "mvp", "PLAYER PROFILE")
        file = discord.File(card, filename=f"{target.name}_profile.png")
        lines = [
            f"**Position:** {pos}",
            f"**Games:** {target.games}",
            f"**Goals:** {target.goals} | **Assists:** {target.assists}",
            f"**Rating:** {round(target.rating_pg, 1)}",
            f"**Impact:** {target.impact_score} | **Clutch:** {target.clutch_score}",
            f"**Pass Accuracy:** {round(target.pass_accuracy, 1)}%",
        ]
        embed = discord.Embed(title=f"👤 {target.name}", description="\n".join(lines), color=0x1e90ff)
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="anime_card", description="Premium anime player card")
@app_commands.describe(player="Player name")
async def slash_anime_card(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    target = find_player(player)
    if not target:
        await interaction.followup.send(f"ما لقيتش `{player}`.")
        return
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    try:
        card = imgen.generate_anime_card(target, pos, "beast", "⚡ ANIME LEGEND")
        file = discord.File(card, filename=f"{target.name}_anime.png")
        embed = discord.Embed(title=f"⚡ {target.name}", color=0x00ffff)
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="beast_mode", description="Beast Mode card (best performance)")
@app_commands.describe(player="Player name (optional)")
async def slash_beast_mode(interaction: discord.Interaction, player: str = None):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    if player:
        target = find_player(player)
    else:
        target = max(current_club.players, key=lambda p: p.impact_score) if current_club.players else None
    if not target:
        await interaction.followup.send("ما لقيتش player.")
        return
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    try:
        card = imgen.generate_beast_card(target, pos)
        file = discord.File(card, filename="beast.png")
        embed = discord.Embed(title=f"⚡ BEAST MODE — {target.name}",
                              description=f"Impact: {target.impact_score} | Goals: {target.goals} | Rating: {round(target.rating_pg, 1)}",
                              color=0x00bfff)
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="court_case", description="Put a player on trial")
@app_commands.describe(player="Player name")
async def slash_court_case(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    target = find_player(player)
    if not target:
        await interaction.followup.send(f"ما لقيتش `{player}`.")
        return
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    try:
        text = darija.court_case(target)
        card = imgen.generate_court_case(target, pos, ["Evidence generated by Roast Engine"])
        file = discord.File(card, filename="court.png")
        color = 0xff0000 if target.throwing_score > 3.0 or target.rating_pg < 5.5 else 0x00ff00
        embed = discord.Embed(title=f"⚖️ COURT CASE: {target.name}", description=text, color=color)
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="mvp", description="MVP of the season")
async def slash_mvp(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        normalize_club_players(current_club)
        mvp = StatsEngine.get_mvp(current_club.players)
        pos = squad_map.get(mvp.name, {}).get("position", "CM")
        card = imgen.generate_mvp_card(mvp, pos)
        file = discord.File(card, filename="mvp.png")
        mvp_text = darija.mvp(mvp)
        embed = discord.Embed(title="🏆 MAN OF THE MATCH", description=mvp_text, color=0xffd700)
        embed.add_field(name="Goals", value=str(mvp.goals), inline=True)
        embed.add_field(name="Assists", value=str(mvp.assists), inline=True)
        embed.add_field(name="Rating", value=str(round(mvp.rating_pg, 1)), inline=True)
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="worst", description="Worst player of the week")
async def slash_worst(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        normalize_club_players(current_club)
        worst = StatsEngine.get_worst(current_club.players)
        pos = squad_map.get(worst.name, {}).get("position", "CM")
        roast = darija.roast(worst, pos)
        embed = discord.Embed(title="🗑️ WORST PLAYER", description=roast, color=0x8b0000)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="who_sold", description="Who sold the match")
async def slash_who_sold(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        normalize_club_players(current_club)
        fraud = StatsEngine.get_fraud(current_club.players)
        pos = squad_map.get(fraud.name, {}).get("position", "CM")
        roast = darija.fraud(fraud)
        embed = discord.Embed(title="🎭 FRAUD DETECTED", description=roast, color=0xff4500)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="carry_detector", description="Who is carrying the team")
async def slash_carry(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        normalize_club_players(current_club)
        carry = StatsEngine.get_carry(current_club.players)
        pos = squad_map.get(carry.name, {}).get("position", "CM")
        praise = darija.carry(carry)
        embed = discord.Embed(title="💪 CARRY DETECTED", description=praise, color=0x00ff00)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="fraud_check", description="Check if a player is fraud")
@app_commands.describe(player="Player name, PSN, or nickname")
async def slash_fraud_check(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    target = find_player(player)
    if not target:
        await interaction.followup.send(f"ما لقيتش `{player}`.")
        return
    try:
        squad_map = get_squad_map()
        pos = squad_map.get(target.name, {}).get("position", "CM")
        is_fraud = target.throwing_score > 3.0
        if is_fraud:
            text = darija.fraud(target)
            color = 0xff0000
        else:
            text = f"✅ CLEAN\n\n{target.name} — Throwing: {target.throwing_score}\n\nهادا لاعب صحيح."
            color = 0x00ff00
        embed = discord.Embed(title="FRAUD CHECK", description=text, color=color)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="ballon_dor", description="Ballon d'Or ranking")
async def slash_ballon_dor(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        normalize_club_players(current_club)
        ranked = sorted(current_club.players, key=lambda p: p.impact_score + p.clutch_score + p.goals * 2, reverse=True)
        embed = discord.Embed(title="🏆 BALLON D'OR", color=0xffd700)
        medals = ["🥇", "🥈", "🥉"]
        for i, p in enumerate(ranked[:5]):
            medal = medals[i] if i < 3 else f"{i+1}."
            embed.add_field(name=f"{medal} {p.name}", value=f"Impact: {p.impact_score} | Goals: {p.goals} | Rating: {round(p.rating_pg, 1)}", inline=False)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="ghost_detector", description="Detect inactive players")
async def slash_ghost(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        normalize_club_players(current_club)
        ghost = StatsEngine.get_ghost(current_club.players)
        pos = squad_map.get(ghost.name, {}).get("position", "CM")
        roast = darija.ghost(ghost)
        embed = discord.Embed(title="👻 GHOST DETECTED", description=roast, color=0x9370db)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="pass_the_ball", description="Call out ball hog")
async def slash_pass_ball(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        normalize_club_players(current_club)
        hog = StatsEngine.get_ball_hog(current_club.players)
        pos = squad_map.get(hog.name, {}).get("position", "CM")
        roast = darija.ball_loser(hog)
        embed = discord.Embed(title="⚽ PASS THE BALL!", description=roast, color=0xffa500)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="ball_loser", description="Most possession losses")
async def slash_ball_loser(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        normalize_club_players(current_club)
        loser = max(current_club.players, key=lambda p: p.possession_losses)
        pos = squad_map.get(loser.name, {}).get("position", "CM")
        roast = darija.ball_loser(loser)
        embed = discord.Embed(title="💀 BALL LOSER", description=roast, color=0x8b0000)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="playmaker", description="Best creator")
async def slash_playmaker(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        normalize_club_players(current_club)
        pm = max(current_club.players, key=lambda p: p.assists * 2 + p.pass_accuracy)
        pos = squad_map.get(pm.name, {}).get("position", "CM")
        text = darija.playmaker(pm)
        card = imgen.generate_playmaker_card(pm, pos)
        file = discord.File(card, filename="playmaker.png")
        embed = discord.Embed(title="🎨 PLAYMAKER", description=text, color=0x00ff00)
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="sniper", description="Best finisher")
async def slash_sniper(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        normalize_club_players(current_club)
        sniper = max(current_club.players, key=lambda p: p.goals * 2 + p.rating_pg)
        pos = squad_map.get(sniper.name, {}).get("position", "CM")
        card = imgen.generate_sniper_card(sniper, pos)
        file = discord.File(card, filename="sniper.png")
        embed = discord.Embed(title="🎯 SNIPER", description=f"**{sniper.name}** — {sniper.goals} goals | Rating: {round(sniper.rating_pg, 1)}", color=0xff4500)
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="keeper", description="Best goalkeeper")
async def slash_keeper(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        normalize_club_players(current_club)
        gks = [p for p in current_club.players if squad_map.get(p.name, {}).get("position") == "GK"]
        if not gks:
            await interaction.followup.send("ما لقيتش goalkeeper فالفريق.")
            return
        keeper = max(gks, key=lambda p: p.tackles + p.interceptions)
        text = darija.keeper(keeper)
        embed = discord.Embed(title="🧤 KEEPER", description=text, color=0x1e90ff)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="leaderboard", description="Leaderboard with visual card")
@app_commands.describe(metric="Metric to rank by")
@app_commands.choices(metric=[
    app_commands.Choice(name="Impact Score", value="impact_score"),
    app_commands.Choice(name="Goals", value="goals"),
    app_commands.Choice(name="Assists", value="assists"),
    app_commands.Choice(name="Rating", value="rating_pg"),
    app_commands.Choice(name="Clutch", value="clutch_score"),
])
async def slash_leaderboard(interaction: discord.Interaction, metric: app_commands.Choice[str]):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        normalize_club_players(current_club)
        card = imgen.generate_leaderboard(current_club.players, metric.value)
        file = discord.File(card, filename="leaderboard.png")
        embed = discord.Embed(title=f"📊 Leaderboard — {metric.name}", color=0x1e90ff)
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="compare", description="1v1 player comparison")
@app_commands.describe(player1="First player", player2="Second player")
async def slash_compare(interaction: discord.Interaction, player1: str, player2: str):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    p1 = find_player(player1)
    p2 = find_player(player2)
    if not p1 or not p2:
        await interaction.followup.send("ما لقيتش players.")
        return
    try:
        text = darija.compare(p1, p2)
        embed = discord.Embed(title="⚔️ 1v1 COMPARISON", description=text, color=0xff4500)
        embed.add_field(name=p1.name, value=f"Impact: {p1.impact_score}\nGoals: {p1.goals}\nAssists: {p1.assists}\nRating: {round(p1.rating_pg, 1)}", inline=True)
        embed.add_field(name=p2.name, value=f"Impact: {p2.impact_score}\nGoals: {p2.goals}\nAssists: {p2.assists}\nRating: {round(p2.rating_pg, 1)}", inline=True)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="lastmatch", description="Last match + result")
async def slash_lastmatch(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    if not current_club.matches:
        await interaction.followup.send("ما لقيتش match history.")
        return
    try:
        last = current_club.matches[0]
        color = 0x00ff00 if last.result == "W" else 0xff0000 if last.result == "L" else 0xffff00
        embed = discord.Embed(title=f"⚽ Last Match: {last.score_for} - {last.score_against} vs {last.opponent}", description=f"Result: {last.result} • {last.date.strftime('%d/%m/%Y')}", color=color)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="clubinfo", description="Club overview + match report card")
async def slash_clubinfo(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        normalize_club_players(current_club)
        motm = StatsEngine.get_mvp(current_club.players)
        card = imgen.generate_match_report(current_club, motm)
        file = discord.File(card, filename="club_report.png")
        embed = discord.Embed(title=f"🏟️ {current_club.club_name}", description=f"Division {current_club.division} • Skill {current_club.skill_rating}", color=0x00ff00)
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="history", description="Player performance history")
@app_commands.describe(player="Player name")
async def slash_history(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    target = find_player(player)
    if not target:
        await interaction.followup.send(f"ما لقيتش `{player}`.")
        return
    try:
        mem = memory.get_player_memory(target.name)
        if not mem:
            await interaction.followup.send(f"ما عنديش تاريخ لـ {target.name}.")
            return
        embed = discord.Embed(title=f"📜 History — {target.name}", color=0x9370db)
        embed.add_field(name="Total Games", value=mem["total_games"], inline=True)
        embed.add_field(name="Total Goals", value=mem["total_goals"], inline=True)
        embed.add_field(name="Total Assists", value=mem["total_assists"], inline=True)
        embed.add_field(name="Best Rating", value=mem["best_rating"], inline=True)
        embed.add_field(name="Worst Rating", value=mem["worst_rating"], inline=True)
        embed.add_field(name="Consecutive Bad", value=mem["consecutive_bad"], inline=True)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="rankings", description="All rankings")
async def slash_rankings(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        normalize_club_players(current_club)
        embed = discord.Embed(title="📊 ALL RANKINGS", color=0x1e90ff)
        mvp = StatsEngine.get_mvp(current_club.players)
        worst = StatsEngine.get_worst(current_club.players)
        fraud = StatsEngine.get_fraud(current_club.players)
        carry = StatsEngine.get_carry(current_club.players)
        ghost = StatsEngine.get_ghost(current_club.players)
        embed.add_field(name="🏆 MVP", value=f"{mvp.name} (Impact: {mvp.impact_score})", inline=False)
        embed.add_field(name="🗑️ Worst", value=f"{worst.name} (Impact: {worst.impact_score})", inline=False)
        embed.add_field(name="🎭 Fraud", value=f"{fraud.name} (Throwing: {fraud.throwing_score})", inline=False)
        embed.add_field(name="💪 Carry", value=f"{carry.name} (Impact: {carry.impact_score})", inline=False)
        embed.add_field(name="👻 Ghost", value=f"{ghost.name} ({ghost.minutes_played}min)", inline=False)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="awards", description="Season awards")
async def slash_awards(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        normalize_club_players(current_club)
        embed = discord.Embed(title="🏅 SEASON AWARDS", color=0xffd700)
        mvp = StatsEngine.get_mvp(current_club.players)
        top_scorer = max(current_club.players, key=lambda p: p.goals)
        top_assist = max(current_club.players, key=lambda p: p.assists)
        fraud = StatsEngine.get_fraud(current_club.players)
        embed.add_field(name="🥇 Ballon d'Or", value=mvp.name, inline=False)
        embed.add_field(name="⚽ Golden Boot", value=f"{top_scorer.name} ({top_scorer.goals} goals)", inline=False)
        embed.add_field(name="🅰️ Playmaker Award", value=f"{top_assist.name} ({top_assist.assists} assists)", inline=False)
        embed.add_field(name="🤡 Fraud of the Season", value=f"{fraud.name} ({fraud.throwing_score} throwing)", inline=False)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="daily", description="Stat of the Day")
async def slash_daily(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        pick = daily_engine.pick_stat_of_the_day(current_club.players)
        if not pick:
            await interaction.followup.send("ما قدرتش نجيب daily stat.")
            return
        is_bad = pick.get("type") == "bad"
        card = imgen.generate_daily_card(pick["player"], pick["stat_name"], pick["stat_value"], pick["roast"], is_bad)
        file = discord.File(card, filename="daily.png")
        embed = discord.Embed(title=pick["title"], description=pick["roast"], color=0xff0000 if is_bad else 0xffd700)
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="story", description="Story of the Day")
async def slash_story(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        text = story_engine.generate_story(current_club.players)
        embed = discord.Embed(title="📖 Story of the Day", description=text, color=0x9370db)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="banter", description="Football trash talk")
async def slash_banter(interaction: discord.Interaction):
    try:
        text = darija.banter()
        embed = discord.Embed(title="☕ Cafeteria Banter", description=text, color=0xffa500)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.response.send_message(f"Error: {str(e)[:300]}")

@bot.tree.command(name="drama", description="Drama / polemique")
async def slash_drama(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        names = [p.name for p in current_club.players[:2]] if current_club.players else ["Player1", "Player2"]
        text = darija.drama(names)
        embed = discord.Embed(title="🍿 Drama Alert", description=text, color=0xff1493)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="meme", description="Meme b Darija")
@app_commands.describe(player="Player name (optional)")
async def slash_meme(interaction: discord.Interaction, player: str = None):
    try:
        target = player or "Player"
        text = darija.meme(resolve_nickname(target))
        embed = discord.Embed(title="😂 Darija Meme", description=text, color=0x00ff7f)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.response.send_message(f"Error: {str(e)[:300]}")

@bot.tree.command(name="transfer", description="Transfer rumor")
@app_commands.describe(player="Player name")
async def slash_transfer(interaction: discord.Interaction, player: str):
    try:
        text = darija.transfer(resolve_nickname(player))
        embed = discord.Embed(title="📰 Transfer News", description=text, color=0x1e90ff)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.response.send_message(f"Error: {str(e)[:300]}")

@bot.tree.command(name="predict", description="Match prediction")
async def slash_predict(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data_interaction(interaction): return
    try:
        names = [p.name for p in current_club.players[:2]] if current_club.players else ["Player1", "Player2"]
        text = darija.predict(names)
        embed = discord.Embed(title="🔮 Match Prediction", description=text, color=0x9400d3)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"Error: {str(e)[:300]}")

@bot.tree.command(name="personality", description="Switch bot personality")
@app_commands.describe(mode="Personality mode")
@app_commands.choices(mode=[
    app_commands.Choice(name="Casablanca Street", value="casablanca"),
    app_commands.Choice(name="Football Analyst", value="analyst"),
    app_commands.Choice(name="Toxic Teammate", value="toxic"),
    app_commands.Choice(name="Coach", value="coach"),
    app_commands.Choice(name="Commentator", value="commentator"),
    app_commands.Choice(name="Cafeteria Banter", value="cafeteria"),
])
async def slash_personality(interaction: discord.Interaction, mode: app_commands.Choice[str]):
    try:
        darija.set_personality(mode.value)
        embed = discord.Embed(title="🎭 Personality Switch", description=f"Changed to: **{mode.name}**", color=0x9370db)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.response.send_message(f"Error: {str(e)[:300]}")

@bot.tree.command(name="help", description="Show all commands")
async def slash_help(interaction: discord.Interaction):
    try:
        embed = discord.Embed(
            title="Rachad L3ERGONI Bot",
            description="الخطوة الأولى: دير /sync أو !sync\n\nبعدها تقدر تستعمل كل شي:",
            color=0x1e90ff
        )
        cmds = [
            ("/ping / !ping", "تأكد من أن البوت كيهضر"),
            ("/debug / !debug", "معلومات تقنية"),
            ("/resync / !resync", "إصلاح slash commands"),
            ("/sync / !sync", "جلب البيانات"),
            ("/stats [player] / !stats [player]", "إحصائيات + anime card"),
            ("/player [player] / !player [player]", "البروفيل الكامل"),
            ("/mvp / !mvp", "أفضل لاعب + anime MVP"),
            ("/worst / !worst", "أسوأ لاعب"),
            ("/who_sold / !who_sold", "شكون باع الماتش"),
            ("/carry_detector / !carry", "شكون كيجرّ"),
            ("/fraud_check [player] / !fraud [player]", "فحص + anime fraud card"),
            ("/ballon_dor / !ballon", "Ballon d'Or"),
            ("/ghost_detector / !ghost", "Ghost + anime card"),
            ("/pass_the_ball / !pass", "Ball hog"),
            ("/ball_loser / !ball_loser", "أكثر واحد كيضيع"),
            ("/playmaker / !playmaker", "أحسن creator"),
            ("/sniper / !sniper", "أحسن finisher"),
            ("/keeper / !keeper", "أحسن حارس"),
            ("/leaderboard / !leaderboard [metric]", "لوحة المتصدرين"),
            ("/compare / !compare", "مقارنة 1v1"),
            ("/lastmatch / !lastmatch", "آخر ماتش"),
            ("/clubinfo / !club", "معلومات النادي"),
            ("/history [player] / !history [player]", "تاريخ اللاعب"),
            ("/rankings / !rankings", "كل الترتيبات"),
            ("/awards / !awards", "جوائز الموسم"),
            ("/anime_card [player] / !anime_card [player]", "كارطة anime"),
            ("/beast_mode [player] / !beast_mode [player]", "Beast Mode"),
            ("/court_case [player] / !court_case [player]", "محاكمة"),
            ("/serial_offender [player] / !serial_offender [player]", "المجرم المتسلسل"),
            ("/hall_of_shame / !hall_of_shame", "صالة العار"),
            ("/daily / !daily", "Stat of the Day"),
            ("/story / !story", "قصة اليوم"),
            ("/banter / !banter", "هضرة"),
            ("/drama / !drama", "دراما"),
            ("/meme / !meme", "ميم"),
            ("/transfer / !transfer", "إشاعة انتقال"),
            ("/predict / !predict", "توقع"),
            ("/personality / !personality", "شخصية"),
            ("/roast / !roast", "Roast mode"),
            ("/stop / !stop", "إيقاف"),
            ("/roastplayer / !roastplayer", "Roast لاعب"),
        ]
        for cmd, desc in cmds:
            embed.add_field(name=cmd, value=desc, inline=False)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.response.send_message(f"Error: {str(e)[:300]}")

if __name__ == "__main__":
    bot.run(Config.DISCORD_TOKEN)
