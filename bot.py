import os
import asyncio
import json
import random
import threading
import traceback
from datetime import datetime
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler

import discord
from discord import app_commands
from discord.ext import commands, tasks

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
    port = Config.PORT
    try:
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        print(f"✅ Health check server running on port {port}")
    except Exception as e:
        print(f"⚠️ Health server failed to start on port {port}: {e}")


class RachadBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(command_prefix="!", intents=intents)
        
        # REMOVE default discord.py help command
        self.remove_command('help')
        
        self.squad = load_squad()
        self.scraper: Optional[ProClubsTrackerScraper] = None
        self.darija = DarijaEngine(Config.DEFAULT_PERSONALITY)
        self.imgen = ImageGenerator(Config.ASSETS_DIR)
        self.memory = SquadMemory()
        self.current_club: Optional[ClubStats] = None
        self._session_active = False
        self._last_match_count = 0
        self._fonts_ok = False
        
    async def setup_hook(self):
        print("🔄 Setting up bot...")
        self.scraper = ProClubsTrackerScraper(
            Config.PCT_CLUB_URL,
            headless=Config.HEADLESS,
            use_stealth=Config.STEALTH
        )
        self.auto_scraper.start()
        
        guild = discord.Object(id=Config.DISCORD_GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print(f"✅ Slash commands synced to guild {Config.DISCORD_GUILD_ID}")
        
        # Background startup scrape (non-blocking)
        asyncio.create_task(self._startup_scrape())
    
    async def _startup_scrape(self):
        """Try to scrape once on startup so data is ready immediately."""
        try:
            print("🔄 Startup scrape attempt...")
            club = await self.scraper.scrape_club()
            if club and club.players:
                self.current_club = club
                squad_map = self._get_squad_map()
                self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
                print(f"✅ Startup OK: {len(club.players)} players, {len(club.matches)} matches")
            else:
                print("⚠️ Startup scrape: no data returned")
        except Exception as e:
            print(f"❌ Startup scrape failed: {e}")
            traceback.print_exc()
    
    async def on_ready(self):
        print(f"✅ Rachad L3ERGONI Bot online as {self.user}")
        try:
            self.imgen._get_font(20)
            self._fonts_ok = True
        except Exception:
            self._fonts_ok = False
            print("⚠️ Arabic fonts not found in assets/fonts/")
        
        await self.change_presence(activity=discord.Game(name="Pro Clubs • /help"))
    
    async def on_command_error(self, ctx, error):
        """Handle prefix command errors gracefully."""
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("❌ هاد الكوماند ما كاينش. جرب `!help` باش تشوف الكوماندات.")
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ ناقصك parameter: `{error.param.name}`. جرب `!help` باش تشوف كيفاش تستعمل.")
            return
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ صبر {error.retry_after:.1f} seconds.")
            return
        
        print(f"Prefix command error: {error}")
        traceback.print_exc()
        await ctx.send(f"❌ Error: {str(error)[:300]}")
    
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle slash command errors gracefully."""
        print(f"Slash command error: {error}")
        traceback.print_exc()
        
        msg = f"❌ Error: {str(error)[:500]}"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg)
            else:
                await interaction.response.send_message(msg)
        except Exception:
            pass
    
    async def close(self):
        if self.scraper:
            await self.scraper.close()
        await super().close()
    
    def _get_squad_map(self):
        players = self.squad.get("players", [])
        return {p.get("name", ""): p for p in players}
    
    def _find_player(self, query: str) -> Optional[PlayerStats]:
        if not self.current_club or not self.current_club.players:
            return None
        return fuzzy_find_player(query, self.current_club.players, self.squad)
    
    async def _ensure_data(self, ctx_or_interaction) -> bool:
        """Returns True if data is available. Tells user what to do if not."""
        if self.current_club and self.current_club.players:
            return True
        
        # Try to scrape now
        try:
            msg = "⏳ جاري جلب البيانات من ProClubsTracker... صبر شوية."
            if isinstance(ctx_or_interaction, discord.Interaction):
                if not ctx_or_interaction.response.is_done():
                    await ctx_or_interaction.response.send_message(msg)
                else:
                    await ctx_or_interaction.followup.send(msg)
            else:
                await ctx_or_interaction.send(msg)
            
            club = await self.scraper.scrape_club()
            if not club or not club.players:
                err = "❌ ما قدرتش نجيب البيانات من ProClubsTracker.\n\n**جرب:**\n1. `/sync` مرة أخرى\n2. تأكد من أن الURL صحيح فالenv vars\n3. شوف Render logs باش تعرف المشكل"
                if isinstance(ctx_or_interaction, discord.Interaction):
                    await ctx_or_interaction.followup.send(err)
                else:
                    await ctx_or_interaction.send(err)
                return False
            
            self.current_club = club
            squad_map = self._get_squad_map()
            self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
            return True
            
        except Exception as e:
            print(f"Scrape error in _ensure_data: {e}")
            traceback.print_exc()
            err = f"❌ كاين مشكل فالscraper.\n```\n{str(e)[:300]}\n```\nجرب `/sync` مرة أخرى."
            if isinstance(ctx_or_interaction, discord.Interaction):
                await ctx_or_interaction.followup.send(err)
            else:
                await ctx_or_interaction.send(err)
            return False
    
    @tasks.loop(minutes=Config.SCRAPE_INTERVAL)
    async def auto_scraper(self):
        if not self._session_active:
            return
        try:
            club = await self.scraper.scrape_club()
            if not club or not club.players:
                return
            self.current_club = club
            squad_map = self._get_squad_map()
            club.players = StatsEngine.compute_all(club.players, squad_map)
            
            for p in club.players:
                self.memory.update_player(p.name, {
                    "games": p.games, "goals": p.goals, "assists": p.assists,
                    "rating": p.rating_pg, "possession_losses": p.possession_losses,
                })
            
            current_match_count = len(club.matches)
            if current_match_count > self._last_match_count:
                self._last_match_count = current_match_count
                channel = self.get_channel(Config.DISCORD_STATS_CHANNEL_ID)
                if channel and club.matches:
                    last = club.matches[0]
                    motm = StatsEngine.get_mvp(club.players)
                    embed = discord.Embed(
                        title=f"📊 New Match — {last.score_for}-{last.score_against} vs {last.opponent}",
                        color=0x00ff00 if last.result == "W" else 0xff0000 if last.result == "L" else 0xffff00
                    )
                    embed.add_field(name="MVP", value=f"{motm.name} (Impact: {motm.impact_score})", inline=False)
                    await channel.send(embed=embed)
        except Exception as e:
            print(f"Auto-scrape error: {e}")
            traceback.print_exc()
    
    @auto_scraper.before_loop
    async def before_auto_scraper(self):
        await self.wait_until_ready()
    
    # ============================================================
    # PREFIX COMMANDS
    # ============================================================
    
    @commands.command(name="help")
    async def cmd_help(self, ctx):
        embed = discord.Embed(
            title="🎮 Rachad L3ERGONI Bot",
            description="**الخطوة الأولى: دير `!sync` أو `/sync` باش يجيب البيانات**\n\nبعدها تقدر تستعمل كل شي:",
            color=0x1e90ff
        )
        cmds = [
            ("`!sync` / `/sync`", "جلب البيانات من ProClubsTracker (دير هادي الأول!)"),
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
        ]
        for cmd, desc in cmds:
            embed.add_field(name=cmd, value=desc, inline=False)
        await ctx.send(embed=embed)
    
    @commands.command(name="sync")
    async def cmd_sync(self, ctx):
        async with ctx.typing():
            try:
                club = await self.scraper.scrape_club()
                if not club or not club.players:
                    await ctx.send("❌ ما قدرتش نجيب البيانات من ProClubsTracker.\n\n**أسباب محتملة:**\n1. ProClubsTracker محمي ضد bots\n2. Chromium ما كيهضرش فRender (memory issue)\n3. الURL غالط\n\n**جرب:** شوف Render logs.")
                    return
                
                self.current_club = club
                squad_map = self._get_squad_map()
                self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
                
                embed = discord.Embed(
                    title="🔄 Sync Complete",
                    description=f"**{len(club.players)}** players loaded\nClub: {club.club_name} | Div {club.division}\nRecord: {club.wins}W — {club.losses}L — {club.draws}D",
                    color=0x00ff00
                )
                await ctx.send(embed=embed)
            except Exception as e:
                traceback.print_exc()
                await ctx.send(f"❌ Sync failed.\n```\n{str(e)[:500]}\n```\nشوف Render logs باش تعرف المشكل بالضبط.")
    
    @commands.command(name="stats")
    async def cmd_stats(self, ctx, *, player: str):
        if not await self._ensure_data(ctx):
            return
        
        target = self._find_player(player)
        if not target:
            await ctx.send(f"ما لقيتش `{player}`. جرب اسم آخر.")
            return
        
        squad_map = self._get_squad_map()
        pos = squad_map.get(target.name, {}).get("position", "CM")
        
        async with ctx.typing():
            try:
                card = self.imgen.generate_player_card(target, pos, division=self.current_club.division)
                file = discord.File(card, filename=f"{target.name}_card.png")
                
                lines = [
                    StatsEngine.interpret_stat("rating", target.rating_pg, pos),
                    StatsEngine.interpret_stat("pass_accuracy", target.pass_accuracy, pos),
                    StatsEngine.interpret_stat("impact_score", target.impact_score, pos),
                ]
                text = "\n".join(lines)
                
                embed = discord.Embed(
                    title=f"📊 {target.name} — {pos}",
                    description=text,
                    color=0x1e90ff
                )
                embed.add_field(name="Impact", value=str(target.impact_score), inline=True)
                embed.add_field(name="Clutch", value=str(target.clutch_score), inline=True)
                embed.add_field(name="Error", value=str(target.error_score), inline=True)
                
                await ctx.send(embed=embed, file=file)
            except Exception as e:
                traceback.print_exc()
                await ctx.send(f"❌ Error generating card: {str(e)[:300]}")
    
    @commands.command(name="mvp")
    async def cmd_mvp(self, ctx):
        if not await self._ensure_data(ctx):
            return
        
        async with ctx.typing():
            try:
                squad_map = self._get_squad_map()
                self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
                mvp = StatsEngine.get_mvp(self.current_club.players)
                pos = squad_map.get(mvp.name, {}).get("position", "CM")
                
                card = self.imgen.generate_motm_card(mvp, pos)
                file = discord.File(card, filename="mvp.png")
                
                embed = discord.Embed(
                    title="🏆 MAN OF THE MATCH",
                    description=f"**{mvp.name}** — Impact: {mvp.impact_score}",
                    color=0xffd700
                )
                embed.add_field(name="Goals", value=str(mvp.goals), inline=True)
                embed.add_field(name="Assists", value=str(mvp.assists), inline=True)
                embed.add_field(name="Rating", value=str(round(mvp.rating_pg, 1)), inline=True)
                await ctx.send(embed=embed, file=file)
            except Exception as e:
                traceback.print_exc()
                await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="worst")
    async def cmd_worst(self, ctx):
        if not await self._ensure_data(ctx):
            return
        
        async with ctx.typing():
            try:
                squad_map = self._get_squad_map()
                self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
                worst = StatsEngine.get_worst(self.current_club.players)
                pos = squad_map.get(worst.name, {}).get("position", "CM")
                roast = self.darija.roast(worst, pos)
                
                embed = discord.Embed(
                    title="🗑️ WORST PLAYER",
                    description=f"**{worst.name}** — Impact: {worst.impact_score}\n\n{roast}",
                    color=0x8b0000
                )
                await ctx.send(embed=embed)
            except Exception as e:
                traceback.print_exc()
                await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="who_sold")
    async def cmd_who_sold(self, ctx):
        if not await self._ensure_data(ctx):
            return
        
        async with ctx.typing():
            try:
                squad_map = self._get_squad_map()
                self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
                fraud = StatsEngine.get_fraud(self.current_club.players)
                pos = squad_map.get(fraud.name, {}).get("position", "CM")
                roast = self.darija.roast(fraud, pos)
                
                embed = discord.Embed(
                    title="🎭 FRAUD DETECTED",
                    description=f"**{fraud.name}** — Throwing: {fraud.throwing_score}\n\n{roast}",
                    color=0xff4500
                )
                await ctx.send(embed=embed)
            except Exception as e:
                traceback.print_exc()
                await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="carry")
    async def cmd_carry(self, ctx):
        if not await self._ensure_data(ctx):
            return
        
        async with ctx.typing():
            try:
                squad_map = self._get_squad_map()
                self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
                carry = StatsEngine.get_carry(self.current_club.players)
                pos = squad_map.get(carry.name, {}).get("position", "CM")
                praise = self.darija.praise(carry, pos)
                
                embed = discord.Embed(
                    title="💪 CARRY DETECTED",
                    description=f"**{carry.name}** — Impact: {carry.impact_score}\n\n{praise}",
                    color=0x00ff00
                )
                await ctx.send(embed=embed)
            except Exception as e:
                traceback.print_exc()
                await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="fraud")
    async def cmd_fraud(self, ctx, *, player: str):
        if not await self._ensure_data(ctx):
            return
        
        target = self._find_player(player)
        if not target:
            await ctx.send(f"ما لقيتش `{player}`.")
            return
        
        async with ctx.typing():
            try:
                squad_map = self._get_squad_map()
                pos = squad_map.get(target.name, {}).get("position", "CM")
                is_fraud = target.throwing_score > 3.0
                
                if is_fraud:
                    text = f"🚨 FRAUD CONFIRMED\n\n{target.name} — Throwing: {target.throwing_score}\n\n{self.darija.roast(target, pos)}"
                    color = 0xff0000
                else:
                    text = f"✅ CLEAN\n\n{target.name} — Throwing: {target.throwing_score}\n\nهادا لاعب صحيح."
                    color = 0x00ff00
                
                embed = discord.Embed(title="FRAUD CHECK", description=text, color=color)
                await ctx.send(embed=embed)
            except Exception as e:
                traceback.print_exc()
                await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="ballon")
    async def cmd_ballon(self, ctx):
        if not await self._ensure_data(ctx):
            return
        
        async with ctx.typing():
            try:
                squad_map = self._get_squad_map()
                self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
                ranked = sorted(self.current_club.players,
                               key=lambda p: p.impact_score + p.clutch_score + p.goals * 2,
                               reverse=True)
                
                embed = discord.Embed(title="🏆 BALLON D'OR", color=0xffd700)
                medals = ["🥇", "🥈", "🥉"]
                for i, p in enumerate(ranked[:5]):
                    medal = medals[i] if i < 3 else f"{i+1}."
                    embed.add_field(
                        name=f"{medal} {p.name}",
                        value=f"Impact: {p.impact_score} | Goals: {p.goals} | Rating: {round(p.rating_pg, 1)}",
                        inline=False
                    )
                await ctx.send(embed=embed)
            except Exception as e:
                traceback.print_exc()
                await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="ghost")
    async def cmd_ghost(self, ctx):
        if not await self._ensure_data(ctx):
            return
        
        async with ctx.typing():
            try:
                squad_map = self._get_squad_map()
                self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
                ghost = StatsEngine.get_ghost(self.current_club.players)
                pos = squad_map.get(ghost.name, {}).get("position", "CM")
                roast = self.darija.roast(ghost, pos)
                
                embed = discord.Embed(
                    title="👻 GHOST DETECTED",
                    description=f"**{ghost.name}** — {ghost.minutes_played}min / {ghost.games} games\n\n{roast}",
                    color=0x9370db
                )
                await ctx.send(embed=embed)
            except Exception as e:
                traceback.print_exc()
                await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="pass")
    async def cmd_pass(self, ctx):
        if not await self._ensure_data(ctx):
            return
        
        async with ctx.typing():
            try:
                squad_map = self._get_squad_map()
                self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
                hog = StatsEngine.get_ball_hog(self.current_club.players)
                pos = squad_map.get(hog.name, {}).get("position", "CM")
                roast = self.darija.roast(hog, pos)
                
                embed = discord.Embed(
                    title="⚽ PASS THE BALL!",
                    description=f"**{hog.name}** — {hog.possession_losses} lost / {hog.assists} assists\n\n{roast}",
                    color=0xffa500
                )
                await ctx.send(embed=embed)
            except Exception as e:
                traceback.print_exc()
                await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="leaderboard")
    async def cmd_leaderboard(self, ctx, metric: str = "impact"):
        if not await self._ensure_data(ctx):
            return
        
        metric_map = {
            "impact": "impact_score",
            "goals": "goals",
            "assists": "assists",
            "rating": "rating_pg",
            "clutch": "clutch_score",
        }
        metric_value = metric_map.get(metric.lower(), "impact_score")
        metric_name = metric.capitalize()
        
        async with ctx.typing():
            try:
                squad_map = self._get_squad_map()
                self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
                
                card = self.imgen.generate_leaderboard(self.current_club.players, metric_value)
                file = discord.File(card, filename="leaderboard.png")
                
                embed = discord.Embed(
                    title=f"📊 Leaderboard — {metric_name}",
                    color=0x1e90ff
                )
                await ctx.send(embed=embed, file=file)
            except Exception as e:
                traceback.print_exc()
                await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="compare")
    async def cmd_compare(self, ctx, player1: str, player2: str):
        if not await self._ensure_data(ctx):
            return
        
        p1 = self._find_player(player1)
        p2 = self._find_player(player2)
        if not p1 or not p2:
            await ctx.send("ما لقيتش واحد من players.")
            return
        
        async with ctx.typing():
            try:
                squad_map = self._get_squad_map()
                pos1 = squad_map.get(p1.name, {}).get("position", "CM")
                pos2 = squad_map.get(p2.name, {}).get("position", "CM")
                text = self.darija.compare(p1, p2, pos1, pos2)
                
                embed = discord.Embed(title="⚔️ 1v1 COMPARISON", description=text, color=0xff4500)
                embed.add_field(name=p1.name,
                               value=f"Impact: {p1.impact_score}\nGoals: {p1.goals}\nAssists: {p1.assists}\nRating: {round(p1.rating_pg, 1)}",
                               inline=True)
                embed.add_field(name=p2.name,
                               value=f"Impact: {p2.impact_score}\nGoals: {p2.goals}\nAssists: {p2.assists}\nRating: {round(p2.rating_pg, 1)}",
                               inline=True)
                await ctx.send(embed=embed)
            except Exception as e:
                traceback.print_exc()
                await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="lastmatch")
    async def cmd_lastmatch(self, ctx):
        if not await self._ensure_data(ctx):
            return
        
        if not self.current_club.matches:
            await ctx.send("ما لقيتش match history.")
            return
        
        try:
            last = self.current_club.matches[0]
            color = 0x00ff00 if last.result == "W" else 0xff0000 if last.result == "L" else 0xffff00
            embed = discord.Embed(
                title=f"⚽ Last Match: {last.score_for} - {last.score_against} vs {last.opponent}",
                description=f"Result: {last.result} • {last.date.strftime('%d/%m/%Y')}",
                color=color
            )
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="club")
    async def cmd_club(self, ctx):
        if not await self._ensure_data(ctx):
            return
        
        async with ctx.typing():
            try:
                squad_map = self._get_squad_map()
                self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
                motm = StatsEngine.get_mvp(self.current_club.players)
                
                card = self.imgen.generate_match_report(self.current_club, motm)
                file = discord.File(card, filename="club_report.png")
                
                embed = discord.Embed(
                    title=f"🏟️ {self.current_club.club_name}",
                    description=f"Division {self.current_club.division} • Skill {self.current_club.skill_rating}",
                    color=0x00ff00
                )
                await ctx.send(embed=embed, file=file)
            except Exception as e:
                traceback.print_exc()
                await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="banter")
    async def cmd_banter(self, ctx):
        try:
            text = self.darija.banter()
            embed = discord.Embed(title="☕ Cafeteria Banter", description=text, color=0xffa500)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="drama")
    async def cmd_drama(self, ctx):
        if not await self._ensure_data(ctx):
            return
        
        try:
            names = [p.name for p in self.current_club.players[:2]] if self.current_club.players else ["Player1", "Player2"]
            text = self.darija.drama(names)
            embed = discord.Embed(title="🍿 Drama Alert", description=text, color=0xff1493)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="meme")
    async def cmd_meme(self, ctx, *, player: str = "Player"):
        try:
            text = self.darija.meme(player)
            embed = discord.Embed(title="😂 Darija Meme", description=text, color=0x00ff7f)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="transfer")
    async def cmd_transfer(self, ctx, *, player: str):
        try:
            text = self.darija.transfer(player)
            embed = discord.Embed(title="📰 Transfer News", description=text, color=0x1e90ff)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="predict")
    async def cmd_predict(self, ctx):
        if not await self._ensure_data(ctx):
            return
        
        try:
            names = [p.name for p in self.current_club.players[:2]] if self.current_club.players else ["Player1", "Player2"]
            text = self.darija.predict(names)
            embed = discord.Embed(title="🔮 Match Prediction", description=text, color=0x9400d3)
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="personality")
    async def cmd_personality(self, ctx, mode: str):
        valid = ["casablanca", "analyst", "toxic", "coach", "commentator", "cafeteria"]
        if mode.lower() not in valid:
            await ctx.send(f"❌ Personality غير صحيح. Valid: {', '.join(valid)}")
            return
        
        try:
            self.darija.set_personality(mode.lower())
            embed = discord.Embed(
                title="🎭 Personality Switch",
                description=f"Changed to: **{mode.capitalize()}**",
                color=0x9370db
            )
            await ctx.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    @commands.command(name="roast")
    async def cmd_roast(self, ctx):
        self._session_active = True
        self.darija.set_personality("casablanca")
        embed = discord.Embed(
            title="🔥 ROAST MODE ACTIVATED",
            description="Session monitoring started. Auto-updates every 5 minutes.",
            color=0xff4500
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="stop")
    async def cmd_stop(self, ctx):
        self._session_active = False
        await ctx.send("⏹️ Session Stopped.")
    
    @commands.command(name="roastplayer")
    async def cmd_roastplayer(self, ctx, *, player: str):
        if not await self._ensure_data(ctx):
            return
        
        target = self._find_player(player)
        if not target:
            await ctx.send(f"ما لقيتش `{player}`.")
            return
        
        squad_map = self._get_squad_map()
        pos = squad_map.get(target.name, {}).get("position", "CM")
        
        async with ctx.typing():
            try:
                roast = self.darija.roast(target, pos)
                card = self.imgen.generate_roast_card(target, roast, pos)
                file = discord.File(card, filename=f"{target.name}_roast.png")
                
                embed = discord.Embed(
                    title=f"🔥 ROAST REPORT — {target.name}",
                    description=roast,
                    color=0xff0000
                )
                await ctx.send(embed=embed, file=file)
            except Exception as e:
                traceback.print_exc()
                await ctx.send(f"❌ Error: {str(e)[:300]}")
    
    # ============================================================
    # SLASH COMMANDS
    # ============================================================
    
    @app_commands.command(name="stats", description="Player stats + premium card")
    @app_commands.describe(player="Player name, PSN, or nickname")
    async def slash_stats(self, interaction: discord.Interaction, player: str):
        await interaction.response.defer()
        if not await self._ensure_data(interaction):
            return
        
        target = self._find_player(player)
        if not target:
            await interaction.followup.send(f"ما لقيتش `{player}`.")
            return
        
        squad_map = self._get_squad_map()
        pos = squad_map.get(target.name, {}).get("position", "CM")
        
        try:
            card = self.imgen.generate_player_card(target, pos, division=self.current_club.division)
            file = discord.File(card, filename=f"{target.name}_card.png")
            
            lines = [
                StatsEngine.interpret_stat("rating", target.rating_pg, pos),
                StatsEngine.interpret_stat("pass_accuracy", target.pass_accuracy, pos),
                StatsEngine.interpret_stat("impact_score", target.impact_score, pos),
            ]
            text = "\n".join(lines)
            
            embed = discord.Embed(
                title=f"📊 {target.name} — {pos}",
                description=text,
                color=0x1e90ff
            )
            embed.add_field(name="Impact", value=str(target.impact_score), inline=True)
            embed.add_field(name="Clutch", value=str(target.clutch_score), inline=True)
            embed.add_field(name="Error", value=str(target.error_score), inline=True)
            
            await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="roastplayer", description="Roast a specific player")
    @app_commands.describe(player="Player name, PSN, or nickname")
    async def slash_roastplayer(self, interaction: discord.Interaction, player: str):
        await interaction.response.defer()
        if not await self._ensure_data(interaction):
            return
        
        target = self._find_player(player)
        if not target:
            await interaction.followup.send(f"ما لقيتش `{player}`.")
            return
        
        squad_map = self._get_squad_map()
        pos = squad_map.get(target.name, {}).get("position", "CM")
        
        try:
            roast = self.darija.roast(target, pos)
            card = self.imgen.generate_roast_card(target, roast, pos)
            file = discord.File(card, filename=f"{target.name}_roast.png")
            
            embed = discord.Embed(
                title=f"🔥 ROAST REPORT — {target.name}",
                description=roast,
                color=0xff0000
            )
            await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="mvp", description="MVP of the season")
    async def slash_mvp(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await self._ensure_data(interaction):
            return
        
        try:
            squad_map = self._get_squad_map()
            self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
            mvp = StatsEngine.get_mvp(self.current_club.players)
            pos = squad_map.get(mvp.name, {}).get("position", "CM")
            
            card = self.imgen.generate_motm_card(mvp, pos)
            file = discord.File(card, filename="mvp.png")
            
            embed = discord.Embed(
                title="🏆 MAN OF THE MATCH",
                description=f"**{mvp.name}** — Impact: {mvp.impact_score}",
                color=0xffd700
            )
            embed.add_field(name="Goals", value=str(mvp.goals), inline=True)
            embed.add_field(name="Assists", value=str(mvp.assists), inline=True)
            embed.add_field(name="Rating", value=str(round(mvp.rating_pg, 1)), inline=True)
            await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="worst", description="Worst player of the week")
    async def slash_worst(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await self._ensure_data(interaction):
            return
        
        try:
            squad_map = self._get_squad_map()
            self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
            worst = StatsEngine.get_worst(self.current_club.players)
            pos = squad_map.get(worst.name, {}).get("position", "CM")
            roast = self.darija.roast(worst, pos)
            
            embed = discord.Embed(
                title="🗑️ WORST PLAYER",
                description=f"**{worst.name}** — Impact: {worst.impact_score}\n\n{roast}",
                color=0x8b0000
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="who_sold", description="Who sold the match")
    async def slash_who_sold(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await self._ensure_data(interaction):
            return
        
        try:
            squad_map = self._get_squad_map()
            self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
            fraud = StatsEngine.get_fraud(self.current_club.players)
            pos = squad_map.get(fraud.name, {}).get("position", "CM")
            roast = self.darija.roast(fraud, pos)
            
            embed = discord.Embed(
                title="🎭 FRAUD DETECTED",
                description=f"**{fraud.name}** — Throwing: {fraud.throwing_score}\n\n{roast}",
                color=0xff4500
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="carry_detector", description="Who is carrying the team")
    async def slash_carry(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await self._ensure_data(interaction):
            return
        
        try:
            squad_map = self._get_squad_map()
            self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
            carry = StatsEngine.get_carry(self.current_club.players)
            pos = squad_map.get(carry.name, {}).get("position", "CM")
            praise = self.darija.praise(carry, pos)
            
            embed = discord.Embed(
                title="💪 CARRY DETECTED",
                description=f"**{carry.name}** — Impact: {carry.impact_score}\n\n{praise}",
                color=0x00ff00
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="fraud_check", description="Check if a player is fraud")
    @app_commands.describe(player="Player name, PSN, or nickname")
    async def slash_fraud_check(self, interaction: discord.Interaction, player: str):
        await interaction.response.defer()
        if not await self._ensure_data(interaction):
            return
        
        target = self._find_player(player)
        if not target:
            await interaction.followup.send(f"ما لقيتش `{player}`.")
            return
        
        try:
            squad_map = self._get_squad_map()
            pos = squad_map.get(target.name, {}).get("position", "CM")
            is_fraud = target.throwing_score > 3.0
            
            if is_fraud:
                text = f"🚨 FRAUD\n\n{target.name} — Throwing: {target.throwing_score}\n\n{self.darija.roast(target, pos)}"
                color = 0xff0000
            else:
                text = f"✅ CLEAN\n\n{target.name} — Throwing: {target.throwing_score}\n\nهادا لاعب صحيح."
                color = 0x00ff00
            
            embed = discord.Embed(title="FRAUD CHECK", description=text, color=color)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="ballon_dor", description="Ballon d'Or ranking")
    async def slash_ballon_dor(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await self._ensure_data(interaction):
            return
        
        try:
            squad_map = self._get_squad_map()
            self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
            ranked = sorted(self.current_club.players,
                           key=lambda p: p.impact_score + p.clutch_score + p.goals * 2,
                           reverse=True)
            
            embed = discord.Embed(title="🏆 BALLON D'OR", color=0xffd700)
            medals = ["🥇", "🥈", "🥉"]
            for i, p in enumerate(ranked[:5]):
                medal = medals[i] if i < 3 else f"{i+1}."
                embed.add_field(
                    name=f"{medal} {p.name}",
                    value=f"Impact: {p.impact_score} | Goals: {p.goals} | Rating: {round(p.rating_pg, 1)}",
                    inline=False
                )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="ghost_detector", description="Detect inactive players")
    async def slash_ghost(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await self._ensure_data(interaction):
            return
        
        try:
            squad_map = self._get_squad_map()
            self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
            ghost = StatsEngine.get_ghost(self.current_club.players)
            pos = squad_map.get(ghost.name, {}).get("position", "CM")
            roast = self.darija.roast(ghost, pos)
            
            embed = discord.Embed(
                title="👻 GHOST DETECTED",
                description=f"**{ghost.name}** — {ghost.minutes_played}min / {ghost.games} games\n\n{roast}",
                color=0x9370db
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="pass_the_ball", description="Call out ball hog")
    async def slash_pass_ball(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await self._ensure_data(interaction):
            return
        
        try:
            squad_map = self._get_squad_map()
            self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
            hog = StatsEngine.get_ball_hog(self.current_club.players)
            pos = squad_map.get(hog.name, {}).get("position", "CM")
            roast = self.darija.roast(hog, pos)
            
            embed = discord.Embed(
                title="⚽ PASS THE BALL!",
                description=f"**{hog.name}** — {hog.possession_losses} lost / {hog.assists} assists\n\n{roast}",
                color=0xffa500
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="leaderboard", description="Leaderboard with visual card")
    @app_commands.describe(metric="Metric to rank by")
    @app_commands.choices(metric=[
        app_commands.Choice(name="Impact Score", value="impact_score"),
        app_commands.Choice(name="Goals", value="goals"),
        app_commands.Choice(name="Assists", value="assists"),
        app_commands.Choice(name="Rating", value="rating_pg"),
        app_commands.Choice(name="Clutch", value="clutch_score"),
    ])
    async def slash_leaderboard(self, interaction: discord.Interaction,
                               metric: app_commands.Choice[str]):
        await interaction.response.defer()
        if not await self._ensure_data(interaction):
            return
        
        try:
            squad_map = self._get_squad_map()
            self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
            
            card = self.imgen.generate_leaderboard(self.current_club.players, metric.value)
            file = discord.File(card, filename="leaderboard.png")
            
            embed = discord.Embed(
                title=f"📊 Leaderboard — {metric.name}",
                color=0x1e90ff
            )
            await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="compare", description="1v1 player comparison")
    @app_commands.describe(player1="First player", player2="Second player")
    async def slash_compare(self, interaction: discord.Interaction, player1: str, player2: str):
        await interaction.response.defer()
        if not await self._ensure_data(interaction):
            return
        
        p1 = self._find_player(player1)
        p2 = self._find_player(player2)
        if not p1 or not p2:
            await interaction.followup.send("ما لقيتش players.")
            return
        
        try:
            squad_map = self._get_squad_map()
            pos1 = squad_map.get(p1.name, {}).get("position", "CM")
            pos2 = squad_map.get(p2.name, {}).get("position", "CM")
            text = self.darija.compare(p1, p2, pos1, pos2)
            
            embed = discord.Embed(title="⚔️ 1v1 COMPARISON", description=text, color=0xff4500)
            embed.add_field(name=p1.name,
                           value=f"Impact: {p1.impact_score}\nGoals: {p1.goals}\nAssists: {p1.assists}\nRating: {round(p1.rating_pg, 1)}",
                           inline=True)
            embed.add_field(name=p2.name,
                           value=f"Impact: {p2.impact_score}\nGoals: {p2.goals}\nAssists: {p2.assists}\nRating: {round(p2.rating_pg, 1)}",
                           inline=True)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="lastmatch", description="Last match + result")
    async def slash_lastmatch(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await self._ensure_data(interaction):
            return
        
        if not self.current_club.matches:
            await interaction.followup.send("ما لقيتش match history.")
            return
        
        try:
            last = self.current_club.matches[0]
            color = 0x00ff00 if last.result == "W" else 0xff0000 if last.result == "L" else 0xffff00
            embed = discord.Embed(
                title=f"⚽ Last Match: {last.score_for} - {last.score_against} vs {last.opponent}",
                description=f"Result: {last.result} • {last.date.strftime('%d/%m/%Y')}",
                color=color
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="clubinfo", description="Club overview + match report card")
    async def slash_clubinfo(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await self._ensure_data(interaction):
            return
        
        try:
            squad_map = self._get_squad_map()
            self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
            motm = StatsEngine.get_mvp(self.current_club.players)
            
            card = self.imgen.generate_match_report(self.current_club, motm)
            file = discord.File(card, filename="club_report.png")
            
            embed = discord.Embed(
                title=f"🏟️ {self.current_club.club_name}",
                description=f"Division {self.current_club.division} • Skill {self.current_club.skill_rating}",
                color=0x00ff00
            )
            await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="banter", description="Football trash talk")
    async def slash_banter(self, interaction: discord.Interaction):
        try:
            text = self.darija.banter()
            embed = discord.Embed(title="☕ Cafeteria Banter", description=text, color=0xffa500)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="drama", description="Drama / polemique")
    async def slash_drama(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await self._ensure_data(interaction):
            return
        
        try:
            names = [p.name for p in self.current_club.players[:2]] if self.current_club.players else ["Player1", "Player2"]
            text = self.darija.drama(names)
            embed = discord.Embed(title="🍿 Drama Alert", description=text, color=0xff1493)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="meme", description="Meme b Darija")
    @app_commands.describe(player="Player name (optional)")
    async def slash_meme(self, interaction: discord.Interaction, player: str = None):
        try:
            target = player or "Player"
            text = self.darija.meme(target)
            embed = discord.Embed(title="😂 Darija Meme", description=text, color=0x00ff7f)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="transfer", description="Transfer rumor")
    @app_commands.describe(player="Player name")
    async def slash_transfer(self, interaction: discord.Interaction, player: str):
        try:
            text = self.darija.transfer(player)
            embed = discord.Embed(title="📰 Transfer News", description=text, color=0x1e90ff)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="predict", description="Match prediction")
    async def slash_predict(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await self._ensure_data(interaction):
            return
        
        try:
            names = [p.name for p in self.current_club.players[:2]] if self.current_club.players else ["Player1", "Player2"]
            text = self.darija.predict(names)
            embed = discord.Embed(title="🔮 Match Prediction", description=text, color=0x9400d3)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="personality", description="Switch bot personality")
    @app_commands.describe(mode="Personality mode")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Casablanca Street", value="casablanca"),
        app_commands.Choice(name="Football Analyst", value="analyst"),
        app_commands.Choice(name="Toxic Teammate", value="toxic"),
        app_commands.Choice(name="Coach", value="coach"),
        app_commands.Choice(name="Commentator", value="commentator"),
        app_commands.Choice(name="Cafeteria Banter", value="cafeteria"),
    ])
    async def slash_personality(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        try:
            self.darija.set_personality(mode.value)
            embed = discord.Embed(
                title="🎭 Personality Switch",
                description=f"Changed to: **{mode.name}**",
                color=0x9370db
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(f"❌ Error: {str(e)[:300]}")
    
    @app_commands.command(name="sync", description="Manual sync from ProClubsTracker")
    async def slash_sync(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            club = await self.scraper.scrape_club()
            if not club or not club.players:
                await interaction.followup.send(
                    "❌ ما قدرتش نجيب البيانات.\n\n**أسباب محتملة:**\n1. ProClubsTracker محمي ضد bots (cloud IP blocked)\n2. Chromium ما كيهضرش فRender (memory limit)\n3. الURL غالط\n\n**شوف Render logs باش تعرف المشكل بالضبط.**"
                )
                return
            
            self.current_club = club
            squad_map = self._get_squad_map()
            self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
            
            embed = discord.Embed(
                title="🔄 Sync Complete",
                description=f"**{len(club.players)}** players loaded\nClub: {club.club_name} | Div {club.division}\nRecord: {club.wins}W — {club.losses}L — {club.draws}D",
                color=0x00ff00
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.followup.send(
                f"❌ Sync failed.\n```\n{str(e)[:500]}\n```\n"
                "شوف Render logs."
            )
    
    @app_commands.command(name="help", description="Show all commands")
    async def slash_help(self, interaction: discord.Interaction):
        try:
            embed = discord.Embed(
                title="🎮 Rachad L3ERGONI Bot",
                description="**الخطوة الأولى: دير `/sync` أو `!sync` باش يجيب البيانات**\n\nبعدها تقدر تستعمل كل شي:",
                color=0x1e90ff
            )
            cmds = [
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
            ]
            for cmd, desc in cmds:
                embed.add_field(name=cmd, value=desc, inline=False)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(f"❌ Error: {str(e)[:300]}")


def main():
    start_health_server()
    bot = RachadBot()
    bot.run(Config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
