import os
import asyncio
import traceback
from datetime import datetime
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

import discord
from discord import app_commands
from discord.ext import commands

from config import Config, load_squad
from scraper import ProClubsTrackerScraper
from stats_engine import StatsEngine
from darija_engine import DarijaEngine
from image_gen import ImageGenerator
from memory import SquadMemory
from models import ClubStats, PlayerStats
from utils import fuzzy_find_player


# === Render Health Check Server ===
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Rachad L3ERGONI Bot is online")
    def log_message(self, format, *args):
        pass

def start_health_server():
    try:
        server = HTTPServer(("0.0.0.0", Config.PORT), HealthHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        print(f"✅ Health server on port {Config.PORT}")
    except Exception as e:
        print(f"⚠️ Health server error: {e}")


# === Bot Setup ===
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Global state
squad = load_squad()
scraper: Optional[ProClubsTrackerScraper] = None
darija = DarijaEngine(Config.DEFAULT_PERSONALITY)
imgen = ImageGenerator(Config.ASSETS_DIR)
memory = SquadMemory()
current_club: Optional[ClubStats] = None
_session_active = False


def get_squad_map():
    return {p.get("name", ""): p for p in squad.get("players", [])}

def find_player(query: str) -> Optional[PlayerStats]:
    if not current_club or not current_club.players:
        return None
    return fuzzy_find_player(query, current_club.players, squad)

async def ensure_data(ctx_or_interaction):
    global current_club
    if current_club and current_club.players:
        return True
    if not scraper:
        msg = "❌ Scraper not ready. Wait 10 seconds and retry."
        if isinstance(ctx_or_interaction, discord.Interaction):
            if not ctx_or_interaction.response.is_done():
                await ctx_or_interaction.response.send_message(msg)
            else:
                await ctx_or_interaction.followup.send(msg)
        else:
            await ctx_or_interaction.send(msg)
        return False
    try:
        msg = "⏳ جاري جلب البيانات من ProClubsTracker..."
        if isinstance(ctx_or_interaction, discord.Interaction):
            if not ctx_or_interaction.response.is_done():
                await ctx_or_interaction.response.send_message(msg)
            else:
                await ctx_or_interaction.followup.send(msg)
        else:
            await ctx_or_interaction.send(msg)
        club = await scraper.scrape_club()
        if not club or not club.players:
            err = "❌ ما قدرتش نجيب البيانات.\n\n**أسباب:**\n1. ProClubsTracker كيحجب cloud IPs\n2. Chromium ما كيهضرش فRender (memory)\n3. الURL غالط\n\n**شوف Render logs.**"
            if isinstance(ctx_or_interaction, discord.Interaction):
                await ctx_or_interaction.followup.send(err)
            else:
                await ctx_or_interaction.send(err)
            return False
        current_club = club
        current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
        ok = f"✅ Data loaded: **{len(club.players)}** players"
        if isinstance(ctx_or_interaction, discord.Interaction):
            await ctx_or_interaction.followup.send(ok)
        else:
            await ctx_or_interaction.send(ok)
        return True
    except Exception as e:
        traceback.print_exc()
        err = f"❌ Scrape error: `{str(e)[:300]}`"
        if isinstance(ctx_or_interaction, discord.Interaction):
            await ctx_or_interaction.followup.send(err)
        else:
            await ctx_or_interaction.send(err)
        return False


# === Events ===
@bot.event
async def on_ready():
    global scraper
    print(f"✅ Bot online as {bot.user}")
    scraper = ProClubsTrackerScraper(Config.PCT_CLUB_URL, headless=Config.HEADLESS, use_stealth=Config.STEALTH)
    await bot.change_presence(activity=discord.Game(name="Pro Clubs • /help or !help"))
    try:
        guild = discord.Object(id=Config.DISCORD_GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"✅ Slash commands synced to guild {Config.DISCORD_GUILD_ID}")
    except Exception as e:
        print(f"❌ Slash sync error: {e}")
    asyncio.create_task(startup_scrape())

async def startup_scrape():
    global current_club
    try:
        print("🔄 Startup scrape...")
        club = await scraper.scrape_club()
        if club and club.players:
            current_club = club
            current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
            print(f"✅ Startup OK: {len(club.players)} players")
        else:
            print("⚠️ Startup: no data")
    except Exception as e:
        print(f"❌ Startup scrape failed: {e}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ هاد الكوماند ما كاينش. جرب `!help` باش تشوف الكوماندات.")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ ناقصك parameter: `{error.param.name}`.")
        return
    print(f"Prefix error: {error}")
    traceback.print_exc()
    await ctx.send(f"❌ Error: `{str(error)[:300]}`")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    print(f"Slash error: {error}")
    traceback.print_exc()
    msg = f"❌ Error: `{str(error)[:500]}`"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg)
        else:
            await interaction.response.send_message(msg)
    except Exception:
        pass


# ============================================================
# PREFIX COMMANDS ( !command )
# ============================================================

@bot.command(name="test")
async def cmd_test(ctx):
    await ctx.send("✅ Bot is working! Prefix commands registered. Try `!help` next.")

@bot.command(name="help")
async def cmd_help(ctx):
    embed = discord.Embed(
        title="🎮 Rachad L3ERGONI Bot",
        description="**الخطوة الأولى: دير `!sync` أو `/sync` باش يجيب البيانات**\n\nبعدها تقدر تستعمل كل شي:",
        color=0x1e90ff
    )
    cmds = [
        ("`!test`", "تأكد من أن البوت كيهضر"),
        ("`!sync` / `/sync`", "جلب البيانات (دير هادي الأول!)"),
        ("`!stats [player]` / `/stats`", "إحصائيات لاعب + كارطة"),
        ("`!mvp` / `/mvp`", "أفضل لاعب"),
        ("`!worst` / `/worst`", "أسوأ لاعب"),
        ("`!who_sold` / `/who_sold`", "شكون باع الماتش"),
        ("`!carry` / `/carry_detector`", "شكون كيجرّ الفريق"),
        ("`!fraud [player]` / `/fraud_check`", "فحص الفريق"),
        ("`!ballon` / `/ballon_dor`", "ترتيب Ballon d'Or"),
        ("`!ghost` / `/ghost_detector`", "كشف الغيّاب"),
        ("`!pass` / `/pass_the_ball`", "نادِي على اللي كيضيع الكورة"),
        ("`!leaderboard [metric]` / `/leaderboard`", "لوحة المتصدرين"),
        ("`!compare p1 p2` / `/compare`", "مقارنة 1v1"),
        ("`!lastmatch` / `/lastmatch`", "آخر ماتش"),
        ("`!club` / `/clubinfo`", "معلومات النادي"),
        ("`!banter` / `/banter`", "هضرة رياضية"),
        ("`!drama` / `/drama`", "دراما"),
        ("`!meme [player]` / `/meme`", "ميم بالدارجة"),
        ("`!transfer [player]` / `/transfer`", "إشاعة انتقال"),
        ("`!predict` / `/predict`", "توقع الماتش"),
        ("`!personality [mode]` / `/personality`", "تبديل الشخصية"),
        ("`!roast` / `/roast`", "بدء session monitoring"),
        ("`!stop` / `/stop`", "إيقاف session"),
        ("`!roastplayer [player]` / `/roastplayer`", "Roast لاعب"),
    ]
    for cmd, desc in cmds:
        embed.add_field(name=cmd, value=desc, inline=False)
    await ctx.send(embed=embed)

@bot.command(name="sync")
async def cmd_sync(ctx):
    async with ctx.typing():
        try:
            if not scraper:
                await ctx.send("❌ Scraper not ready.")
                return
            global current_club
            club = await scraper.scrape_club()
            if not club or not club.players:
                await ctx.send("❌ ما قدرتش نجيب البيانات. شوف Render logs.")
                return
            current_club = club
            current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
            embed = discord.Embed(
                title="🔄 Sync Complete",
                description=f"**{len(club.players)}** players loaded\nClub: {club.club_name} | Div {club.division}\nRecord: {club.wins}W — {club.losses}L — {club.draws}D",
                color=0x00ff00
            )
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Sync failed.\n```\n{str(e)[:500]}\n```")

@bot.command(name="stats")
async def cmd_stats(ctx, *, player: str):
    if not await ensure_data(ctx):
        return
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
            lines = [
                StatsEngine.interpret_stat("rating", target.rating_pg, pos),
                StatsEngine.interpret_stat("pass_accuracy", target.pass_accuracy, pos),
                StatsEngine.interpret_stat("impact_score", target.impact_score, pos),
            ]
            text = "\n".join(lines)
            embed = discord.Embed(title=f"📊 {target.name} — {pos}", description=text, color=0x1e90ff)
            embed.add_field(name="Impact", value=str(target.impact_score), inline=True)
            embed.add_field(name="Clutch", value=str(target.clutch_score), inline=True)
            embed.add_field(name="Error", value=str(target.error_score), inline=True)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="mvp")
async def cmd_mvp(ctx):
    if not await ensure_data(ctx):
        return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            mvp = StatsEngine.get_mvp(current_club.players)
            pos = squad_map.get(mvp.name, {}).get("position", "CM")
            card = imgen.generate_motm_card(mvp, pos)
            file = discord.File(card, filename="mvp.png")
            embed = discord.Embed(title="🏆 MAN OF THE MATCH", description=f"**{mvp.name}** — Impact: {mvp.impact_score}", color=0xffd700)
            embed.add_field(name="Goals", value=str(mvp.goals), inline=True)
            embed.add_field(name="Assists", value=str(mvp.assists), inline=True)
            embed.add_field(name="Rating", value=str(round(mvp.rating_pg, 1)), inline=True)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="worst")
async def cmd_worst(ctx):
    if not await ensure_data(ctx):
        return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            worst = StatsEngine.get_worst(current_club.players)
            pos = squad_map.get(worst.name, {}).get("position", "CM")
            roast = darija.roast(worst, pos)
            embed = discord.Embed(title="🗑️ WORST PLAYER", description=f"**{worst.name}** — Impact: {worst.impact_score}\n\n{roast}", color=0x8b0000)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="who_sold")
async def cmd_who_sold(ctx):
    if not await ensure_data(ctx):
        return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            fraud = StatsEngine.get_fraud(current_club.players)
            pos = squad_map.get(fraud.name, {}).get("position", "CM")
            roast = darija.roast(fraud, pos)
            embed = discord.Embed(title="🎭 FRAUD DETECTED", description=f"**{fraud.name}** — Throwing: {fraud.throwing_score}\n\n{roast}", color=0xff4500)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="carry")
async def cmd_carry(ctx):
    if not await ensure_data(ctx):
        return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            carry = StatsEngine.get_carry(current_club.players)
            pos = squad_map.get(carry.name, {}).get("position", "CM")
            praise = darija.praise(carry, pos)
            embed = discord.Embed(title="💪 CARRY DETECTED", description=f"**{carry.name}** — Impact: {carry.impact_score}\n\n{praise}", color=0x00ff00)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="fraud")
async def cmd_fraud(ctx, *, player: str):
    if not await ensure_data(ctx):
        return
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
                text = f"🚨 FRAUD CONFIRMED\n\n{target.name} — Throwing: {target.throwing_score}\n\n{darija.roast(target, pos)}"
                color = 0xff0000
            else:
                text = f"✅ CLEAN\n\n{target.name} — Throwing: {target.throwing_score}\n\nهادا لاعب صحيح."
                color = 0x00ff00
            embed = discord.Embed(title="FRAUD CHECK", description=text, color=color)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="ballon")
async def cmd_ballon(ctx):
    if not await ensure_data(ctx):
        return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            ranked = sorted(current_club.players, key=lambda p: p.impact_score + p.clutch_score + p.goals * 2, reverse=True)
            embed = discord.Embed(title="🏆 BALLON D'OR", color=0xffd700)
            medals = ["🥇", "🥈", "🥉"]
            for i, p in enumerate(ranked[:5]):
                medal = medals[i] if i < 3 else f"{i+1}."
                embed.add_field(name=f"{medal} {p.name}", value=f"Impact: {p.impact_score} | Goals: {p.goals} | Rating: {round(p.rating_pg, 1)}", inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="ghost")
async def cmd_ghost(ctx):
    if not await ensure_data(ctx):
        return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            ghost = StatsEngine.get_ghost(current_club.players)
            pos = squad_map.get(ghost.name, {}).get("position", "CM")
            roast = darija.roast(ghost, pos)
            embed = discord.Embed(title="👻 GHOST DETECTED", description=f"**{ghost.name}** — {ghost.minutes_played}min / {ghost.games} games\n\n{roast}", color=0x9370db)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="pass")
async def cmd_pass(ctx):
    if not await ensure_data(ctx):
        return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            hog = StatsEngine.get_ball_hog(current_club.players)
            pos = squad_map.get(hog.name, {}).get("position", "CM")
            roast = darija.roast(hog, pos)
            embed = discord.Embed(title="⚽ PASS THE BALL!", description=f"**{hog.name}** — {hog.possession_losses} lost / {hog.assists} assists\n\n{roast}", color=0xffa500)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="leaderboard")
async def cmd_leaderboard(ctx, metric: str = "impact"):
    if not await ensure_data(ctx):
        return
    metric_map = {"impact": "impact_score", "goals": "goals", "assists": "assists", "rating": "rating_pg", "clutch": "clutch_score"}
    metric_value = metric_map.get(metric.lower(), "impact_score")
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            card = imgen.generate_leaderboard(current_club.players, metric_value)
            file = discord.File(card, filename="leaderboard.png")
            embed = discord.Embed(title=f"📊 Leaderboard — {metric.capitalize()}", color=0x1e90ff)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="compare")
async def cmd_compare(ctx, player1: str, player2: str):
    if not await ensure_data(ctx):
        return
    p1 = find_player(player1)
    p2 = find_player(player2)
    if not p1 or not p2:
        await ctx.send("ما لقيتش players.")
        return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            pos1 = squad_map.get(p1.name, {}).get("position", "CM")
            pos2 = squad_map.get(p2.name, {}).get("position", "CM")
            text = darija.compare(p1, p2, pos1, pos2)
            embed = discord.Embed(title="⚔️ 1v1 COMPARISON", description=text, color=0xff4500)
            embed.add_field(name=p1.name, value=f"Impact: {p1.impact_score}\nGoals: {p1.goals}\nAssists: {p1.assists}\nRating: {round(p1.rating_pg, 1)}", inline=True)
            embed.add_field(name=p2.name, value=f"Impact: {p2.impact_score}\nGoals: {p2.goals}\nAssists: {p2.assists}\nRating: {round(p2.rating_pg, 1)}", inline=True)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="lastmatch")
async def cmd_lastmatch(ctx):
    if not await ensure_data(ctx):
        return
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
        await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="club")
async def cmd_club(ctx):
    if not await ensure_data(ctx):
        return
    async with ctx.typing():
        try:
            squad_map = get_squad_map()
            current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
            motm = StatsEngine.get_mvp(current_club.players)
            card = imgen.generate_match_report(current_club, motm)
            file = discord.File(card, filename="club_report.png")
            embed = discord.Embed(title=f"🏟️ {current_club.club_name}", description=f"Division {current_club.division} • Skill {current_club.skill_rating}", color=0x00ff00)
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="banter")
async def cmd_banter(ctx):
    try:
        text = darija.banter()
        embed = discord.Embed(title="☕ Cafeteria Banter", description=text, color=0xffa500)
        await ctx.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="drama")
async def cmd_drama(ctx):
    if not await ensure_data(ctx):
        return
    try:
        names = [p.name for p in current_club.players[:2]] if current_club.players else ["Player1", "Player2"]
        text = darija.drama(names)
        embed = discord.Embed(title="🍿 Drama Alert", description=text, color=0xff1493)
        await ctx.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="meme")
async def cmd_meme(ctx, *, player: str = "Player"):
    try:
        text = darija.meme(player)
        embed = discord.Embed(title="😂 Darija Meme", description=text, color=0x00ff7f)
        await ctx.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="transfer")
async def cmd_transfer(ctx, *, player: str):
    try:
        text = darija.transfer(player)
        embed = discord.Embed(title="📰 Transfer News", description=text, color=0x1e90ff)
        await ctx.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="predict")
async def cmd_predict(ctx):
    if not await ensure_data(ctx):
        return
    try:
        names = [p.name for p in current_club.players[:2]] if current_club.players else ["Player1", "Player2"]
        text = darija.predict(names)
        embed = discord.Embed(title="🔮 Match Prediction", description=text, color=0x9400d3)
        await ctx.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await ctx.send(f"❌ Error: `{str(e)[:300]}`")

@bot.command(name="personality")
async def cmd_personality(ctx, mode: str):
    valid = ["casablanca", "analyst", "toxic", "coach", "commentator", "cafeteria"]
    if mode.lower() not in valid:
        await ctx.send(f"❌ Personality غير صحيح. Valid: {', '.join(valid)}")
        return
    try:
        darija.set_personality(mode.lower())
        embed = discord.Embed(title="🎭 Personality Switch", description=f"Changed to: **{mode.capitalize()}**", color=0x9370db)
        await ctx.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await ctx.send(f"❌ Error: `{str(e)[:300]}`")

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
    if not await ensure_data(ctx):
        return
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
            await ctx.send(f"❌ Error: `{str(e)[:300]}`")


# ============================================================
# SLASH COMMANDS ( /command )
# ============================================================

@bot.tree.command(name="test", description="Test if bot is responding")
async def slash_test(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Slash commands work! Try `/sync` next.")

@bot.tree.command(name="sync", description="Manual sync from ProClubsTracker")
async def slash_sync(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        if not scraper:
            await interaction.followup.send("❌ Scraper not ready.")
            return
        global current_club
        club = await scraper.scrape_club()
        if not club or not club.players:
            await interaction.followup.send("❌ ما قدرتش نجيب البيانات. شوف Render logs.")
            return
        current_club = club
        current_club.players = StatsEngine.compute_all(current_club.players, get_squad_map())
        embed = discord.Embed(title="🔄 Sync Complete", description=f"**{len(club.players)}** players loaded", color=0x00ff00)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Sync failed.\n```\n{str(e)[:500]}\n```")

@bot.tree.command(name="stats", description="Player stats + premium card")
@app_commands.describe(player="Player name, PSN, or nickname")
async def slash_stats(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    if not await ensure_data(interaction):
        return
    target = find_player(player)
    if not target:
        await interaction.followup.send(f"ما لقيتش `{player}`.")
        return
    squad_map = get_squad_map()
    pos = squad_map.get(target.name, {}).get("position", "CM")
    try:
        card = imgen.generate_player_card(target, pos, division=current_club.division)
        file = discord.File(card, filename=f"{target.name}_card.png")
        lines = [
            StatsEngine.interpret_stat("rating", target.rating_pg, pos),
            StatsEngine.interpret_stat("pass_accuracy", target.pass_accuracy, pos),
            StatsEngine.interpret_stat("impact_score", target.impact_score, pos),
        ]
        text = "\n".join(lines)
        embed = discord.Embed(title=f"📊 {target.name} — {pos}", description=text, color=0x1e90ff)
        embed.add_field(name="Impact", value=str(target.impact_score), inline=True)
        embed.add_field(name="Clutch", value=str(target.clutch_score), inline=True)
        embed.add_field(name="Error", value=str(target.error_score), inline=True)
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="mvp", description="MVP of the season")
async def slash_mvp(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data(interaction):
        return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        mvp = StatsEngine.get_mvp(current_club.players)
        pos = squad_map.get(mvp.name, {}).get("position", "CM")
        card = imgen.generate_motm_card(mvp, pos)
        file = discord.File(card, filename="mvp.png")
        embed = discord.Embed(title="🏆 MAN OF THE MATCH", description=f"**{mvp.name}** — Impact: {mvp.impact_score}", color=0xffd700)
        embed.add_field(name="Goals", value=str(mvp.goals), inline=True)
        embed.add_field(name="Assists", value=str(mvp.assists), inline=True)
        embed.add_field(name="Rating", value=str(round(mvp.rating_pg, 1)), inline=True)
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="worst", description="Worst player of the week")
async def slash_worst(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data(interaction):
        return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        worst = StatsEngine.get_worst(current_club.players)
        pos = squad_map.get(worst.name, {}).get("position", "CM")
        roast = darija.roast(worst, pos)
        embed = discord.Embed(title="🗑️ WORST PLAYER", description=f"**{worst.name}** — Impact: {worst.impact_score}\n\n{roast}", color=0x8b0000)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="who_sold", description="Who sold the match")
async def slash_who_sold(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data(interaction):
        return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        fraud = StatsEngine.get_fraud(current_club.players)
        pos = squad_map.get(fraud.name, {}).get("position", "CM")
        roast = darija.roast(fraud, pos)
        embed = discord.Embed(title="🎭 FRAUD DETECTED", description=f"**{fraud.name}** — Throwing: {fraud.throwing_score}\n\n{roast}", color=0xff4500)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="carry_detector", description="Who is carrying the team")
async def slash_carry(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data(interaction):
        return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        carry = StatsEngine.get_carry(current_club.players)
        pos = squad_map.get(carry.name, {}).get("position", "CM")
        praise = darija.praise(carry, pos)
        embed = discord.Embed(title="💪 CARRY DETECTED", description=f"**{carry.name}** — Impact: {carry.impact_score}\n\n{praise}", color=0x00ff00)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="fraud_check", description="Check if a player is fraud")
@app_commands.describe(player="Player name, PSN, or nickname")
async def slash_fraud_check(interaction: discord.Interaction, player: str):
    await interaction.response.defer()
    if not await ensure_data(interaction):
        return
    target = find_player(player)
    if not target:
        await interaction.followup.send(f"ما لقيتش `{player}`.")
        return
    try:
        squad_map = get_squad_map()
        pos = squad_map.get(target.name, {}).get("position", "CM")
        is_fraud = target.throwing_score > 3.0
        if is_fraud:
            text = f"🚨 FRAUD\n\n{target.name} — Throwing: {target.throwing_score}\n\n{darija.roast(target, pos)}"
            color = 0xff0000
        else:
            text = f"✅ CLEAN\n\n{target.name} — Throwing: {target.throwing_score}\n\nهادا لاعب صحيح."
            color = 0x00ff00
        embed = discord.Embed(title="FRAUD CHECK", description=text, color=color)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="ballon_dor", description="Ballon d'Or ranking")
async def slash_ballon_dor(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data(interaction):
        return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        ranked = sorted(current_club.players, key=lambda p: p.impact_score + p.clutch_score + p.goals * 2, reverse=True)
        embed = discord.Embed(title="🏆 BALLON D'OR", color=0xffd700)
        medals = ["🥇", "🥈", "🥉"]
        for i, p in enumerate(ranked[:5]):
            medal = medals[i] if i < 3 else f"{i+1}."
            embed.add_field(name=f"{medal} {p.name}", value=f"Impact: {p.impact_score} | Goals: {p.goals} | Rating: {round(p.rating_pg, 1)}", inline=False)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="ghost_detector", description="Detect inactive players")
async def slash_ghost(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data(interaction):
        return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        ghost = StatsEngine.get_ghost(current_club.players)
        pos = squad_map.get(ghost.name, {}).get("position", "CM")
        roast = darija.roast(ghost, pos)
        embed = discord.Embed(title="👻 GHOST DETECTED", description=f"**{ghost.name}** — {ghost.minutes_played}min / {ghost.games} games\n\n{roast}", color=0x9370db)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="pass_the_ball", description="Call out ball hog")
async def slash_pass_ball(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data(interaction):
        return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        hog = StatsEngine.get_ball_hog(current_club.players)
        pos = squad_map.get(hog.name, {}).get("position", "CM")
        roast = darija.roast(hog, pos)
        embed = discord.Embed(title="⚽ PASS THE BALL!", description=f"**{hog.name}** — {hog.possession_losses} lost / {hog.assists} assists\n\n{roast}", color=0xffa500)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Error: `{str(e)[:300]}`")

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
    if not await ensure_data(interaction):
        return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        card = imgen.generate_leaderboard(current_club.players, metric.value)
        file = discord.File(card, filename="leaderboard.png")
        embed = discord.Embed(title=f"📊 Leaderboard — {metric.name}", color=0x1e90ff)
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="compare", description="1v1 player comparison")
@app_commands.describe(player1="First player", player2="Second player")
async def slash_compare(interaction: discord.Interaction, player1: str, player2: str):
    await interaction.response.defer()
    if not await ensure_data(interaction):
        return
    p1 = find_player(player1)
    p2 = find_player(player2)
    if not p1 or not p2:
        await interaction.followup.send("ما لقيتش players.")
        return
    try:
        squad_map = get_squad_map()
        pos1 = squad_map.get(p1.name, {}).get("position", "CM")
        pos2 = squad_map.get(p2.name, {}).get("position", "CM")
        text = darija.compare(p1, p2, pos1, pos2)
        embed = discord.Embed(title="⚔️ 1v1 COMPARISON", description=text, color=0xff4500)
        embed.add_field(name=p1.name, value=f"Impact: {p1.impact_score}\nGoals: {p1.goals}\nAssists: {p1.assists}\nRating: {round(p1.rating_pg, 1)}", inline=True)
        embed.add_field(name=p2.name, value=f"Impact: {p2.impact_score}\nGoals: {p2.goals}\nAssists: {p2.assists}\nRating: {round(p2.rating_pg, 1)}", inline=True)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="lastmatch", description="Last match + result")
async def slash_lastmatch(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data(interaction):
        return
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
        await interaction.followup.send(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="clubinfo", description="Club overview + match report card")
async def slash_clubinfo(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data(interaction):
        return
    try:
        squad_map = get_squad_map()
        current_club.players = StatsEngine.compute_all(current_club.players, squad_map)
        motm = StatsEngine.get_mvp(current_club.players)
        card = imgen.generate_match_report(current_club, motm)
        file = discord.File(card, filename="club_report.png")
        embed = discord.Embed(title=f"🏟️ {current_club.club_name}", description=f"Division {current_club.division} • Skill {current_club.skill_rating}", color=0x00ff00)
        await interaction.followup.send(embed=embed, file=file)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="banter", description="Football trash talk")
async def slash_banter(interaction: discord.Interaction):
    try:
        text = darija.banter()
        embed = discord.Embed(title="☕ Cafeteria Banter", description=text, color=0xffa500)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.response.send_message(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="drama", description="Drama / polemique")
async def slash_drama(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data(interaction):
        return
    try:
        names = [p.name for p in current_club.players[:2]] if current_club.players else ["Player1", "Player2"]
        text = darija.drama(names)
        embed = discord.Embed(title="🍿 Drama Alert", description=text, color=0xff1493)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="meme", description="Meme b Darija")
@app_commands.describe(player="Player name (optional)")
async def slash_meme(interaction: discord.Interaction, player: str = None):
    try:
        target = player or "Player"
        text = darija.meme(target)
        embed = discord.Embed(title="😂 Darija Meme", description=text, color=0x00ff7f)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.response.send_message(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="transfer", description="Transfer rumor")
@app_commands.describe(player="Player name")
async def slash_transfer(interaction: discord.Interaction, player: str):
    try:
        text = darija.transfer(player)
        embed = discord.Embed(title="📰 Transfer News", description=text, color=0x1e90ff)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.response.send_message(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="predict", description="Match prediction")
async def slash_predict(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await ensure_data(interaction):
        return
    try:
        names = [p.name for p in current_club.players[:2]] if current_club.players else ["Player1", "Player2"]
        text = darija.predict(names)
        embed = discord.Embed(title="🔮 Match Prediction", description=text, color=0x9400d3)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Error: `{str(e)[:300]}`")

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
        await interaction.response.send_message(f"❌ Error: `{str(e)[:300]}`")

@bot.tree.command(name="help", description="Show all commands")
async def slash_help(interaction: discord.Interaction):
    try:
        embed = discord.Embed(
            title="🎮 Rachad L3ERGONI Bot",
            description="**الخطوة الأولى: دير `/sync` أو `!sync` باش يجيب البيانات**\n\nبعدها تقدر تستعمل كل شي:",
            color=0x1e90ff
        )
        cmds = [
            ("`/test` / `!test`", "تأكد من أن البوت كيهضر"),
            ("`/sync` / `!sync`", "جلب البيانات (دير هادي الأول!)"),
            ("`/stats [player]` / `!stats [player]`", "إحصائيات لاعب + كارطة"),
            ("`/mvp` / `!mvp`", "أفضل لاعب"),
            ("`/worst` / `!worst`", "أسوأ لاعب"),
            ("`/who_sold` / `!who_sold`", "شكون باع الماتش"),
            ("`/carry_detector` / `!carry`", "شكون كيجرّ الفريق"),
            ("`/fraud_check [player]` / `!fraud [player]`", "فحص الفريق"),
            ("`/ballon_dor` / `!ballon`", "ترتيب Ballon d'Or"),
            ("`/ghost_detector` / `!ghost`", "كشف الغيّاب"),
            ("`/pass_the_ball` / `!pass`", "نادِي على اللي كيضيع الكورة"),
            ("`/leaderboard` / `!leaderboard [metric]`", "لوحة المتصدرين"),
            ("`/compare [p1] [p2]` / `!compare p1 p2`", "مقارنة 1v1"),
            ("`/lastmatch` / `!lastmatch`", "آخر ماتش"),
            ("`/clubinfo` / `!club`", "معلومات النادي"),
            ("`/banter` / `!banter`", "هضرة رياضية"),
            ("`/drama` / `!drama`", "دراما"),
            ("`/meme [player]` / `!meme [player]`", "ميم بالدارجة"),
            ("`/transfer [player]` / `!transfer [player]`", "إشاعة انتقال"),
            ("`/predict` / `!predict`", "توقع الماتش"),
            ("`/personality [mode]` / `!personality [mode]`", "تبديل الشخصية"),
            ("`/roast` / `!roast`", "بدء session monitoring"),
            ("`/stop` / `!stop`", "إيقاف session"),
            ("`/roastplayer [player]` / `!roastplayer [player]`", "Roast لاعب"),
        ]
        for cmd, desc in cmds:
            embed.add_field(name=cmd, value=desc, inline=False)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        traceback.print_exc()
        await interaction.response.send_message(f"❌ Error: `{str(e)[:300]}`")


def main():
    start_health_server()
    bot.run(Config.DISCORD_TOKEN)

if __name__ == "__main__":
    main()
