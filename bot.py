import os
import asyncio
import json
import random
from datetime import datetime
from typing import Optional

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

class RachadBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(command_prefix="!", intents=intents)
        
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
        self.scraper = ProClubsTrackerScraper(
            Config.PCT_CLUB_URL, 
            headless=Config.HEADLESS, 
            use_stealth=Config.STEALTH
        )
        self.auto_scraper.start()
        
        guild = discord.Object(id=Config.DISCORD_GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
    
    async def on_ready(self):
        print(f"Rachad L3ERGONI Bot online as {self.user}")
        
        # Font check
        try:
            test_font = self.imgen._get_font(20)
            self._fonts_ok = True
        except Exception:
            self._fonts_ok = False
            print("⚠️ WARNING: Arabic fonts not found. Install Cairo/Noto fonts in assets/fonts/")
        
        await self.change_presence(activity=discord.Game(name="Pro Clubs • /help"))
    
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
    
    async def _ensure_scraped(self):
        if not self.current_club:
            self.current_club = await self.scraper.scrape_club()
            squad_map = self._get_squad_map()
            self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
    
    @tasks.loop(minutes=Config.SCRAPE_INTERVAL)
    async def auto_scraper(self):
        if not self._session_active:
            return
        
        try:
            club = await self.scraper.scrape_club()
            if not club:
                return
            
            self.current_club = club
            squad_map = self._get_squad_map()
            club.players = StatsEngine.compute_all(club.players, squad_map)
            
            # Update memory (store current totals, not incremental)
            for p in club.players:
                self.memory.update_player(p.name, {
                    "games": p.games,
                    "goals": p.goals,
                    "assists": p.assists,
                    "rating": p.rating_pg,
                    "possession_losses": p.possession_losses,
                })
            
            # Only announce if new matches detected
            current_match_count = len(club.matches)
            if current_match_count > self._last_match_count:
                self._last_match_count = current_match_count
                
                channel = self.get_channel(Config.DISCORD_STATS_CHANNEL_ID)
                if channel and club.matches:
                    last = club.matches[0]
                    motm = StatsEngine.get_mvp(club.players)
                    
                    embed = discord.Embed(
                        title=f"📊 New Match Detected — {last.score_for}-{last.score_against} vs {last.opponent}",
                        description=f"Division {club.division} • {club.wins}W {club.losses}L {club.draws}D",
                        color=0x00ff00 if last.result == "W" else 0xff0000 if last.result == "L" else 0xffff00
                    )
                    embed.add_field(name="MVP", value=f"{motm.name} (Impact: {motm.impact_score})", inline=False)
                    await channel.send(embed=embed)
                    
        except Exception as e:
            print(f"Auto-scrape error: {e}")
    
    @auto_scraper.before_loop
    async def before_auto_scraper(self):
        await self.wait_until_ready()
    
    # --- SLASH COMMANDS ---
    
    @app_commands.command(name="roast", description="Start session monitoring + auto-roast mode")
    async def slash_roast(self, interaction: discord.Interaction):
        self._session_active = True
        self.darija.set_personality("casablanca")
        
        await interaction.response.defer()
        await self._ensure_scraped()
        
        embed = discord.Embed(
            title="🔥 ROAST MODE ACTIVATED",
            description="Session monitoring started. Auto-updates every 5 minutes.",
            color=0xff4500
        )
        embed.add_field(name="Status", value="✅ Active", inline=True)
        embed.add_field(name="Personality", value="Casablanca Street", inline=True)
        embed.add_field(name="Frequency", value="95% Roast / 5% Praise", inline=True)
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="stop", description="Stop session monitoring")
    async def slash_stop(self, interaction: discord.Interaction):
        self._session_active = False
        embed = discord.Embed(
            title="⏹️ Session Stopped",
            description="Auto-monitoring disabled. See you next session.",
            color=0x808080
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="stats", description="Player stats + premium card")
    @app_commands.describe(player="Player name, PSN, or nickname")
    async def slash_stats(self, interaction: discord.Interaction, player: str):
        await interaction.response.defer()
        await self._ensure_scraped()
        
        target = self._find_player(player)
        if not target:
            await interaction.followup.send(f"ما لقيتش player باسم {player} آ صاحبي.")
            return
        
        squad_map = self._get_squad_map()
        pos = squad_map.get(target.name, {}).get("position", "CM")
        
        card = self.imgen.generate_player_card(target, pos, division=self.current_club.division)
        file = discord.File(card, filename=f"{target.name}_card.png")
        
        # Use Darija interpretation instead of raw numbers
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
    
    @app_commands.command(name="roastplayer", description="Roast a specific player")
    @app_commands.describe(player="Player name, PSN, or nickname")
    async def slash_roastplayer(self, interaction: discord.Interaction, player: str):
        await interaction.response.defer()
        await self._ensure_scraped()
        
        target = self._find_player(player)
        if not target:
            await interaction.followup.send(f"ما لقيتش {player} فالفريق.")
            return
        
        squad_map = self._get_squad_map()
        pos = squad_map.get(target.name, {}).get("position", "CM")
        
        roast = self.darija.roast(target, pos)
        card = self.imgen.generate_roast_card(target, roast, pos)
        file = discord.File(card, filename=f"{target.name}_roast.png")
        
        embed = discord.Embed(
            title=f"🔥 ROAST REPORT — {target.name}",
            description=roast,
            color=0xff0000
        )
        
        await interaction.followup.send(embed=embed, file=file)
    
    @app_commands.command(name="mvp", description="MVP of the season")
    async def slash_mvp(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._ensure_scraped()
        
        squad_map = self._get_squad_map()
        self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
        
        mvp = StatsEngine.get_mvp(self.current_club.players)
        pos = squad_map.get(mvp.name, {}).get("position", "CM")
        
        card = self.imgen.generate_motm_card(mvp, pos)
        file = discord.File(card, filename="mvp.png")
        
        embed = discord.Embed(
            title="🏆 MAN OF THE MATCH",
            description=f"**{mvp.name}** — Impact Score: {mvp.impact_score}",
            color=0xffd700
        )
        embed.add_field(name="Goals", value=str(mvp.goals), inline=True)
        embed.add_field(name="Assists", value=str(mvp.assists), inline=True)
        embed.add_field(name="Rating", value=str(round(mvp.rating_pg, 1)), inline=True)
        
        await interaction.followup.send(embed=embed, file=file)
    
    @app_commands.command(name="worst", description="Worst player of the week")
    async def slash_worst(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._ensure_scraped()
        
        squad_map = self._get_squad_map()
        self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
        
        worst = StatsEngine.get_worst(self.current_club.players)
        pos = squad_map.get(worst.name, {}).get("position", "CM")
        
        roast = self.darija.roast(worst, pos)
        
        embed = discord.Embed(
            title="🗑️ WORST PLAYER OF THE WEEK",
            description=f"**{worst.name}** — Impact: {worst.impact_score}\n\n{roast}",
            color=0x8b0000
        )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="who_sold", description="Who sold the match")
    async def slash_who_sold(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._ensure_scraped()
        
        squad_map = self._get_squad_map()
        self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
        
        fraud = StatsEngine.get_fraud(self.current_club.players)
        pos = squad_map.get(fraud.name, {}).get("position", "CM")
        
        roast = self.darija.roast(fraud, pos)
        
        embed = discord.Embed(
            title="🎭 FRAUD DETECTED",
            description=f"**{fraud.name}** — Throwing Score: {fraud.throwing_score}\n\n{roast}",
            color=0xff4500
        )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="carry_detector", description="Who is carrying the team")
    async def slash_carry(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._ensure_scraped()
        
        squad_map = self._get_squad_map()
        self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
        
        carry = StatsEngine.get_carry(self.current_club.players)
        pos = squad_map.get(carry.name, {}).get("position", "CM")
        
        praise = self.darija.praise(carry, pos)
        
        embed = discord.Embed(
            title="💪 CARRY DETECTED",
            description=f"**{carry.name}** — Impact: {carry.impact_score} / Clutch: {carry.clutch_score}\n\n{praise}",
            color=0x00ff00
        )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="fraud_check", description="Check if a player is fraud")
    @app_commands.describe(player="Player name, PSN, or nickname")
    async def slash_fraud_check(self, interaction: discord.Interaction, player: str):
        await interaction.response.defer()
        await self._ensure_scraped()
        
        target = self._find_player(player)
        if not target:
            await interaction.followup.send(f"ما لقيتش {player}.")
            return
        
        squad_map = self._get_squad_map()
        pos = squad_map.get(target.name, {}).get("position", "CM")
        
        fraud_threshold = 3.0
        is_fraud = target.throwing_score > fraud_threshold
        
        if is_fraud:
            text = f"🚨 FRAUD CONFIRMED\n\n{target.name} — Throwing Score: {target.throwing_score}\n\n{self.darija.roast(target, pos)}"
            color = 0xff0000
        else:
            text = f"✅ CLEAN\n\n{target.name} — Throwing Score: {target.throwing_score}\n\nهادا لاعب صحيح، ما كيخونش."
            color = 0x00ff00
        
        embed = discord.Embed(title="FRAUD CHECK", description=text, color=color)
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="ballon_dor", description="Ballon d'Or ranking")
    async def slash_ballon_dor(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._ensure_scraped()
        
        squad_map = self._get_squad_map()
        self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
        
        ranked = sorted(self.current_club.players, 
                       key=lambda p: p.impact_score + p.clutch_score + p.goals * 2, 
                       reverse=True)
        
        embed = discord.Embed(title="🏆 BALLON D'OR — Rachad L3ERGONI", color=0xffd700)
        
        medals = ["🥇", "🥈", "🥉"]
        for i, p in enumerate(ranked[:5]):
            medal = medals[i] if i < 3 else f"{i+1}."
            embed.add_field(
                name=f"{medal} {p.name}",
                value=f"Impact: {p.impact_score} | Goals: {p.goals} | Rating: {round(p.rating_pg, 1)}",
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="ghost_detector", description="Detect inactive players")
    async def slash_ghost(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._ensure_scraped()
        
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
    
    @app_commands.command(name="pass_the_ball", description="Call out ball hog")
    async def slash_pass_ball(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._ensure_scraped()
        
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
        await self._ensure_scraped()
        
        squad_map = self._get_squad_map()
        self.current_club.players = StatsEngine.compute_all(self.current_club.players, squad_map)
        
        card = self.imgen.generate_leaderboard(self.current_club.players, metric.value)
        file = discord.File(card, filename="leaderboard.png")
        
        embed = discord.Embed(
            title=f"📊 Leaderboard — {metric.name}",
            color=0x1e90ff
        )
        
        await interaction.followup.send(embed=embed, file=file)
    
    @app_commands.command(name="compare", description="1v1 player comparison")
    @app_commands.describe(player1="First player", player2="Second player")
    async def slash_compare(self, interaction: discord.Interaction, player1: str, player2: str):
        await interaction.response.defer()
        await self._ensure_scraped()
        
        p1 = self._find_player(player1)
        p2 = self._find_player(player2)
        
        if not p1 or not p2:
            await interaction.followup.send("ما لقيتش واحد من players. جرب أسماء أخرى.")
            return
        
        squad_map = self._get_squad_map()
        pos1 = squad_map.get(p1.name, {}).get("position", "CM")
        pos2 = squad_map.get(p2.name, {}).get("position", "CM")
        
        text = self.darija.compare(p1, p2, pos1, pos2)
        
        embed = discord.Embed(
            title="⚔️ 1v1 COMPARISON",
            description=text,
            color=0xff4500
        )
        
        embed.add_field(name=p1.name, 
                       value=f"Impact: {p1.impact_score}\nGoals: {p1.goals}\nAssists: {p1.assists}\nRating: {round(p1.rating_pg, 1)}",
                       inline=True)
        embed.add_field(name=p2.name,
                       value=f"Impact: {p2.impact_score}\nGoals: {p2.goals}\nAssists: {p2.assists}\nRating: {round(p2.rating_pg, 1)}",
                       inline=True)
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="lastmatch", description="Last match + result")
    async def slash_lastmatch(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._ensure_scraped()
        
        if not self.current_club.matches:
            await interaction.followup.send("ما لقيتش match history. جرب /sync.")
            return
        
        last = self.current_club.matches[0]
        color = 0x00ff00 if last.result == "W" else 0xff0000 if last.result == "L" else 0xffff00
        
        embed = discord.Embed(
            title=f"⚽ Last Match: {last.score_for} - {last.score_against} vs {last.opponent}",
            description=f"Result: {last.result} • {last.date.strftime('%d/%m/%Y')}",
            color=color
        )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="clubinfo", description="Club overview + match report card")
    async def slash_clubinfo(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._ensure_scraped()
        
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
    
    @app_commands.command(name="banter", description="Football trash talk")
    async def slash_banter(self, interaction: discord.Interaction):
        text = self.darija.banter()
        embed = discord.Embed(title="☕ Cafeteria Banter", description=text, color=0xffa500)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="drama", description="Drama / polemique")
    async def slash_drama(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._ensure_scraped()
        
        names = [p.name for p in self.current_club.players[:2]] if self.current_club.players else ["Player1", "Player2"]
        text = self.darija.drama(names)
        embed = discord.Embed(title="🍿 Drama Alert", description=text, color=0xff1493)
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="meme", description="Meme b Darija")
    @app_commands.describe(player="Player name (optional)")
    async def slash_meme(self, interaction: discord.Interaction, player: str = None):
        target = player or "Player"
        text = self.darija.meme(target)
        embed = discord.Embed(title="😂 Darija Meme", description=text, color=0x00ff7f)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="transfer", description="Transfer rumor")
    @app_commands.describe(player="Player name")
    async def slash_transfer(self, interaction: discord.Interaction, player: str):
        text = self.darija.transfer(player)
        embed = discord.Embed(title="📰 Transfer News", description=text, color=0x1e90ff)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="predict", description="Match prediction")
    async def slash_predict(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._ensure_scraped()
        
        names = [p.name for p in self.current_club.players[:2]] if self.current_club.players else ["Player1", "Player2"]
        text = self.darija.predict(names)
        embed = discord.Embed(title="🔮 Match Prediction", description=text, color=0x9400d3)
        await interaction.followup.send(embed=embed)
    
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
        self.darija.set_personality(mode.value)
        embed = discord.Embed(
            title="🎭 Personality Switch",
            description=f"Bot personality changed to: **{mode.name}**",
            color=0x9370db
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="sync", description="Manual sync from ProClubsTracker")
    async def slash_sync(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        club = await self.scraper.scrape_club()
        self.current_club = club
        
        embed = discord.Embed(
            title="🔄 Manual Sync Complete",
            description=f"Synced {len(club.players)} players from ProClubsTracker",
            color=0x00ff00
        )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="help", description="Show all commands")
    async def slash_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎮 Rachad L3ERGONI Bot — Commands",
            description="The Moroccan Pro Clubs AI that roasts with real data",
            color=0x1e90ff
        )
        
        commands_list = [
            ("/roast", "Start session monitoring"),
            ("/stop", "Stop session"),
            ("/stats [player]", "Player stats + premium card"),
            ("/roastplayer [player]", "Roast specific player"),
            ("/mvp", "MVP of the season"),
            ("/worst", "Worst player of the week"),
            ("/who_sold", "Who sold the match"),
            ("/carry_detector", "Who is carrying"),
            ("/fraud_check [player]", "Check if fraud"),
            ("/ballon_dor", "Ballon d'Or ranking"),
            ("/ghost_detector", "Detect inactive players"),
            ("/pass_the_ball", "Call out ball hog"),
            ("/leaderboard [metric]", "Visual leaderboard"),
            ("/compare [p1] [p2]", "1v1 comparison"),
            ("/lastmatch", "Last match result"),
            ("/clubinfo", "Club overview card"),
            ("/banter", "Football trash talk"),
            ("/drama", "Drama / polemique"),
            ("/meme [player]", "Meme b Darija"),
            ("/transfer [player]", "Transfer rumor"),
            ("/predict", "Match prediction"),
            ("/personality [mode]", "Switch personality"),
            ("/sync", "Manual sync from ProClubsTracker"),
        ]
        
        for cmd, desc in commands_list:
            embed.add_field(name=cmd, value=desc, inline=False)
        
        await interaction.response.send_message(embed=embed)

def main():
    bot = RachadBot()
    bot.run(Config.DISCORD_TOKEN)

if __name__ == "__main__":
    main()
