"""Premium Pro Clubs Discord Bot - EA FC style with Casablanca banter.
Commands: /stats, /player, /mvp, /fraud, /who_sold, /rankings, /roast, /ghost, /carry, /club
"""
import os
import json
import sqlite3
import random
import asyncio
from pathlib import Path
from datetime import datetime, time
from typing import Dict, Optional, List
from io import BytesIO

import discord
from discord import app_commands, File, Embed, Interaction
from discord.ext import commands, tasks

import config
from aura_system import get_aura_system, AuraTier
from card_generator import get_card_generator
from roast_engine import get_roast_engine
from darija_engine import get_darija_engine
from player_mapper import get_mapper
from daily_content import get_daily_system

# ============== DATA LAYER (DO NOT MODIFY) ==============
# Assumes existing working data collection

class DataLayer:
    """Interface to existing working data. DO NOT MODIFY collection logic."""

    def __init__(self):
        self.match_db = config.MATCH_DB
        self.squad_file = config.SQUAD_FILE
        self._cache: Dict[str, Dict] = {}
        self._last_update = None

    def _load_squad(self) -> List[Dict]:
        """Load squad from squad.json."""
        if not self.squad_file.exists():
            return []
        try:
            with open(self.squad_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            return data.get("players", data.get("members", []))
        except Exception as e:
            print(f"[DataLayer] Error loading squad: {e}")
            return []

    def _load_stats_from_db(self) -> Dict[str, Dict]:
        """Load aggregated stats from matches.db."""
        stats = {}
        if not Path(self.match_db).exists():
            return stats

        try:
            conn = sqlite3.connect(self.match_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check table structure
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            if "matches" in tables:
                # Aggregate from matches table
                cursor.execute("""
                    SELECT 
                        player_name,
                        COUNT(*) as games,
                        AVG(rating) as rating,
                        SUM(goals) as goals,
                        SUM(assists) as assists,
                        SUM(tackles) as tackles,
                        SUM(interceptions) as interceptions,
                        SUM(possession_lost) as possession_lost,
                        AVG(pass_accuracy) as pass_accuracy,
                        SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) as wins,
                        SUM(motm) as motm,
                        AVG(impact) as impact
                    FROM matches
                    GROUP BY player_name
                """)
                for row in cursor.fetchall():
                    d = dict(row)
                    name = d.pop("player_name", "")
                    if name:
                        stats[name] = {
                            "games": d.get("games", 0) or 0,
                            "rating": round(d.get("rating", 7) or 7, 1),
                            "goals": d.get("goals", 0) or 0,
                            "assists": d.get("assists", 0) or 0,
                            "tackles": d.get("tackles", 0) or 0,
                            "interceptions": d.get("interceptions", 0) or 0,
                            "possession_lost": d.get("possession_lost", 0) or 0,
                            "pass_accuracy": round(d.get("pass_accuracy", 0) or 0, 1),
                            "wins": d.get("wins", 0) or 0,
                            "motm": d.get("motm", 0) or 0,
                            "impact": round(d.get("impact", 5) or 5, 1),
                        }

            conn.close()
        except Exception as e:
            print(f"[DataLayer] Error loading DB: {e}")

        return stats

    def get_all_stats(self) -> Dict[str, Dict]:
        """Get all player stats."""
        # Use cached if recent
        if self._cache and self._last_update:
            # Cache for 2 minutes
            if (datetime.now() - self._last_update).seconds < 120:
                return self._cache

        stats = self._load_stats_from_db()

        # Ensure all squad members exist
        squad = self._load_squad()
        for player in squad:
            name = player.get("name") or player.get("ea_name") or player.get("username", "")
            if name and name not in stats:
                stats[name] = {
                    "games": 0, "rating": 0, "goals": 0, "assists": 0,
                    "tackles": 0, "interceptions": 0, "possession_lost": 0,
                    "pass_accuracy": 0, "wins": 0, "motm": 0, "impact": 0,
                }

        # Calculate derived stats
        for name, s in stats.items():
            games = max(s.get("games", 1), 1)
            s["win_rate"] = round((s.get("wins", 0) / games) * 100, 1)
            s["fraud_score"] = get_aura_system().calculate_fraud_score(s)

        self._cache = stats
        self._last_update = datetime.now()
        return stats

    def get_player_stats(self, ea_name: str) -> Optional[Dict]:
        """Get stats for a specific player."""
        all_stats = self.get_all_stats()
        return all_stats.get(ea_name)

    def get_recent_matches(self, limit: int = 10) -> List[Dict]:
        """Get recent matches."""
        matches = []
        if not Path(self.match_db).exists():
            return matches
        try:
            conn = sqlite3.connect(self.match_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM matches
                ORDER BY match_date DESC, id DESC
                LIMIT ?
            """, (limit,))
            for row in cursor.fetchall():
                matches.append(dict(row))
            conn.close()
        except Exception as e:
            print(f"[DataLayer] Error getting matches: {e}")
        return matches

# ============== BOT SETUP ==============

class ProClubsBot(commands.Bot):
    """Premium Pro Clubs Discord Bot."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

        self.data = DataLayer()
        self.aura = get_aura_system()
        self.cards = get_card_generator()
        self.roast = get_roast_engine()
        self.darija = get_darija_engine()
        self.mapper = get_mapper()
        self.daily = get_daily_system()

        # Track command usage for audit
        self.command_stats: Dict[str, Dict] = {}

    async def setup_hook(self):
        """Setup slash commands and background tasks."""
        guild = discord.Object(id=config.DISCORD_GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

        # Start background tasks
        self.daily_post_task.start()
        self.data_refresh_task.start()

    # ============== BACKGROUND TASKS ==============

    @tasks.loop(minutes=1)
    async def data_refresh_task(self):
        """Refresh data cache periodically."""
        self.data.get_all_stats()

    @tasks.loop(time=time(config.DAILY_POST_HOUR, config.DAILY_POST_MINUTE))
    async def daily_post_task(self):
        """Post daily stat of the day."""
        channel = self.get_channel(config.GENERAL_CHANNEL_ID)
        if not channel:
            return

        stats = self.data.get_all_stats()
        if not stats:
            return

        content = self.daily.select_stat_of_day(stats)
        msg_data = self.daily.format_discord_message(content)

        embed = Embed(
            title=msg_data["title"],
            description=msg_data["description"],
            color=msg_data["color"],
            timestamp=datetime.utcnow(),
        )

        if content.card_path and Path(content.card_path).exists():
            file = File(content.card_path, filename="stat_of_day.png")
            embed.set_image(url="attachment://stat_of_day.png")
            await channel.send(embed=embed, file=file)
        else:
            await channel.send(embed=embed)

    # ============== EVENTS ==============

    async def on_ready(self):
        """Bot ready event."""
        print(f"[Bot] Logged in as {self.user} (ID: {self.user.id})")
        print(f"[Bot] Guild ID: {config.DISCORD_GUILD_ID}")
        print(f"[Bot] Commands synced")

        greeting = self.darija.greeting("ProClubsTracker")
        print(f"[Bot] {greeting}")

    async def on_command_error(self, ctx, error):
        """Handle command errors."""
        if isinstance(error, commands.CommandNotFound):
            return

        nickname = self.mapper.get_nickname(str(ctx.author))
        msg = self.darija.command_error(nickname)
        await ctx.send(msg)

    async def on_app_command_error(self, interaction: Interaction, error):
        """Handle slash command errors."""
        nickname = self.mapper.get_nickname(str(interaction.user))
        msg = self.darija.command_error(nickname)

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

# ============== COMMAND HELPERS ==============

def _get_player_by_input(bot: ProClubsBot, user_input: str) -> Optional[tuple]:
    """Resolve player input to (ea_name, stats)."""
    stats = bot.data.get_all_stats()

    # Try exact match
    if user_input in stats:
        return user_input, stats[user_input]

    # Try nickname
    ea_name = bot.mapper.get_ea_name(user_input)
    if ea_name in stats:
        return ea_name, stats[ea_name]

    # Try case-insensitive
    for name, s in stats.items():
        if name.lower() == user_input.lower():
            return name, s

    # Try partial match on nickname
    nick = bot.mapper.get_nickname(user_input)
    for name, s in stats.items():
        if bot.mapper.get_nickname(name).lower() == nick.lower():
            return name, s

    return None

def _generate_card_file(bot: ProClubsBot, ea_name: str, stats: Dict, 
                        card_type: str = "standard") -> File:
    """Generate card image and return as Discord File."""
    if card_type == "mvp":
        card = bot.cards.generate_mvp_card(ea_name, stats)
    elif card_type == "fraud":
        card = bot.cards.generate_fraud_card(ea_name, stats)
    elif card_type == "ghost":
        card = bot.cards.generate_ghost_card(ea_name, stats)
    elif card_type == "carry":
        card = bot.cards.generate_carry_card(ea_name, stats)
    else:
        card = bot.cards.generate_player_card(ea_name, stats)

    buf = BytesIO()
    card.save(buf, format="PNG", quality=95)
    buf.seek(0)
    nickname = bot.mapper.get_nickname(ea_name)
    return File(buf, filename=f"{nickname}_card.png")

def _track_command(bot: ProClubsBot, command_name: str, success: bool, error: Optional[str] = None):
    """Track command usage for audit."""
    if command_name not in bot.command_stats:
        bot.command_stats[command_name] = {"success": 0, "fail": 0, "errors": []}

    if success:
        bot.command_stats[command_name]["success"] += 1
    else:
        bot.command_stats[command_name]["fail"] += 1
        if error:
            bot.command_stats[command_name]["errors"].append(error)

# ============== SLASH COMMANDS ==============

bot = ProClubsBot()

@bot.tree.command(name="stats", description="Show player stats with premium card")
@app_commands.describe(player="Player name or nickname")
async def stats_cmd(interaction: Interaction, player: str):
    """Show player stats with premium card."""
    await interaction.response.defer()

    try:
        result = _get_player_by_input(bot, player)
        if not result:
            nickname = bot.mapper.get_nickname(player)
            msg = bot.darija.command_error(nickname)
            await interaction.followup.send(msg)
            _track_command(bot, "stats", False, "player_not_found")
            return

        ea_name, stats = result
        nickname = bot.mapper.get_nickname(ea_name)

        # Generate card
        card_file = _generate_card_file(bot, ea_name, stats)

        # Build embed
        overall = int(bot.aura.calculate_overall(stats))
        tier = bot.aura.determine_tier(stats)

        embed = Embed(
            title=f"{nickname} • {overall} OVR • {tier.value}",
            description=bot.darija.command_success(),
            color=discord.Color.gold() if tier == AuraTier.A_TIER else discord.Color.purple(),
        )
        embed.set_image(url=f"attachment://{nickname}_card.png")

        # Add stat fields
        embed.add_field(name="Games", value=stats.get("games", 0), inline=True)
        embed.add_field(name="Rating", value=stats.get("rating", 0), inline=True)
        embed.add_field(name="Goals", value=stats.get("goals", 0), inline=True)
        embed.add_field(name="Assists", value=stats.get("assists", 0), inline=True)
        embed.add_field(name="Win Rate", value=f"{stats.get('win_rate', 0)}%", inline=True)
        embed.add_field(name="Impact", value=stats.get("impact", 0), inline=True)

        await interaction.followup.send(embed=embed, file=card_file)
        _track_command(bot, "stats", True)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")
        _track_command(bot, "stats", False, str(e))

@bot.tree.command(name="player", description="Show detailed player profile")
@app_commands.describe(player="Player name or nickname")
async def player_cmd(interaction: Interaction, player: str):
    """Show detailed player profile."""
    await interaction.response.defer()

    try:
        result = _get_player_by_input(bot, player)
        if not result:
            msg = bot.darija.command_error(bot.mapper.get_nickname(player))
            await interaction.followup.send(msg)
            _track_command(bot, "player", False, "player_not_found")
            return

        ea_name, stats = result
        nickname = bot.mapper.get_nickname(ea_name)

        card_file = _generate_card_file(bot, ea_name, stats)

        overall = int(bot.aura.calculate_overall(stats))
        tier = bot.aura.determine_tier(stats)
        fraud = stats.get("fraud_score", 0)

        embed = Embed(
            title=f"👤 {nickname} - Full Profile",
            description=f"**{ea_name}** | {stats.get('position', 'CM')} | {tier.value} Aura",
            color=discord.Color.purple(),
        )
        embed.set_image(url=f"attachment://{nickname}_card.png")

        # All stats
        fields = [
            ("Overall", overall, True),
            ("Games", stats.get("games", 0), True),
            ("Rating", stats.get("rating", 0), True),
            ("Goals", stats.get("goals", 0), True),
            ("Assists", stats.get("assists", 0), True),
            ("Pass %", f"{stats.get('pass_accuracy', 0)}%", True),
            ("Tackles", stats.get("tackles", 0), True),
            ("Interceptions", stats.get("interceptions", 0), True),
            ("Poss Lost", stats.get("possession_lost", 0), True),
            ("Win Rate", f"{stats.get('win_rate', 0)}%", True),
            ("Impact", stats.get("impact", 0), True),
            ("Fraud Score", f"{fraud}/100", True),
        ]

        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

        await interaction.followup.send(embed=embed, file=card_file)
        _track_command(bot, "player", True)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")
        _track_command(bot, "player", False, str(e))

@bot.tree.command(name="mvp", description="Show MVP of the team")
async def mvp_cmd(interaction: Interaction):
    """Show team MVP."""
    await interaction.response.defer()

    try:
        stats = bot.data.get_all_stats()
        if not stats:
            await interaction.followup.send("No data available.")
            _track_command(bot, "mvp", False, "no_data")
            return

        # Find MVP by overall
        best = None
        best_score = -1
        for ea_name, s in stats.items():
            games = s.get("games", 0)
            if games >= 3:
                overall = bot.aura.calculate_overall(s)
                if overall > best_score:
                    best_score = overall
                    best = (ea_name, s)

        if not best:
            await interaction.followup.send("No qualified MVP found.")
            _track_command(bot, "mvp", False, "no_qualified")
            return

        ea_name, s = best
        nickname = bot.mapper.get_nickname(ea_name)

        card_file = _generate_card_file(bot, ea_name, s, "mvp")
        praise = bot.roast.mvp_praise(ea_name, s)

        embed = Embed(
            title=f"👑 MVP: {nickname}",
            description=praise,
            color=discord.Color.gold(),
        )
        embed.set_image(url=f"attachment://{nickname}_card.png")

        await interaction.followup.send(embed=embed, file=card_file)
        _track_command(bot, "mvp", True)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")
        _track_command(bot, "mvp", False, str(e))

@bot.tree.command(name="fraud", description="Expose the biggest fraud")
async def fraud_cmd(interaction: Interaction):
    """Expose the biggest fraud."""
    await interaction.response.defer()

    try:
        stats = bot.data.get_all_stats()
        if not stats:
            await interaction.followup.send("No data available.")
            _track_command(bot, "fraud", False, "no_data")
            return

        # Find biggest fraud
        worst = None
        worst_score = -1
        for ea_name, s in stats.items():
            games = s.get("games", 0)
            if games >= 3:
                fraud = bot.aura.calculate_fraud_score(s)
                if fraud > worst_score:
                    worst_score = fraud
                    worst = (ea_name, s)

        if not worst:
            await interaction.followup.send("No qualified fraud found.")
            _track_command(bot, "fraud", False, "no_qualified")
            return

        ea_name, s = worst
        nickname = bot.mapper.get_nickname(ea_name)

        card_file = _generate_card_file(bot, ea_name, s, "fraud")
        accusation = bot.roast.fraud_accusation(ea_name, s)

        embed = Embed(
            title=f"🤡 FRAUD EXPOSED: {nickname}",
            description=accusation,
            color=discord.Color.red(),
        )
        embed.set_image(url=f"attachment://{nickname}_card.png")

        await interaction.followup.send(embed=embed, file=card_file)
        _track_command(bot, "fraud", True)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")
        _track_command(bot, "fraud", False, str(e))

@bot.tree.command(name="who_sold", description="Find who sold the last match")
async def who_sold_cmd(interaction: Interaction):
    """Find who sold the last match."""
    await interaction.response.defer()

    try:
        matches = bot.data.get_recent_matches(1)
        if not matches:
            await interaction.followup.send("No recent matches found.")
            _track_command(bot, "who_sold", False, "no_matches")
            return

        last_match = matches[0]
        result = last_match.get("result", "")

        if result == "W":
            await interaction.followup.send("Last match was a WIN. No one sold... this time.")
            _track_command(bot, "who_sold", True)
            return

        # Find worst performer in last match
        match_id = last_match.get("match_id", "")

        # Query all players from that match
        worst_player = None
        worst_rating = 999

        try:
            conn = sqlite3.connect(config.MATCH_DB)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT player_name, rating, goals, assists, possession_lost
                FROM matches WHERE match_id = ? ORDER BY rating ASC LIMIT 1
            """, (match_id,))
            row = cursor.fetchone()
            if row:
                worst_player = dict(row)
            conn.close()
        except Exception as e:
            print(f"[who_sold] DB error: {e}")

        if not worst_player:
            await interaction.followup.send("Could not determine who sold.")
            _track_command(bot, "who_sold", False, "db_error")
            return

        ea_name = worst_player.get("player_name", "Unknown")
        nickname = bot.mapper.get_nickname(ea_name)
        stats = bot.data.get_player_stats(ea_name) or {}

        card_file = _generate_card_file(bot, ea_name, stats, "fraud")
        sold_msg = bot.roast.who_sold(ea_name, stats)

        embed = Embed(
            title=f"🚨 WHO SOLD?",
            description=sold_msg,
            color=discord.Color.dark_red(),
        )
        embed.add_field(name="Match Result", value=result, inline=True)
        embed.add_field(name="Rating", value=worst_player.get("rating", "N/A"), inline=True)
        embed.add_field(name="Poss Lost", value=worst_player.get("possession_lost", 0), inline=True)
        embed.set_image(url=f"attachment://{nickname}_card.png")

        await interaction.followup.send(embed=embed, file=card_file)
        _track_command(bot, "who_sold", True)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")
        _track_command(bot, "who_sold", False, str(e))

@bot.tree.command(name="rankings", description="Show team rankings")
@app_commands.describe(stat="Stat to rank by (goals, assists, rating, wins, impact, fraud)")
async def rankings_cmd(interaction: Interaction, stat: str = "overall"):
    """Show team rankings."""
    await interaction.response.defer()

    try:
        stats = bot.data.get_all_stats()
        if not stats:
            await interaction.followup.send("No data available.")
            _track_command(bot, "rankings", False, "no_data")
            return

        valid_stats = ["goals", "assists", "rating", "wins", "impact", "fraud_score", 
                       "win_rate", "possession_lost", "overall"]

        if stat.lower() not in valid_stats and stat.lower() != "overall":
            stat = "overall"

        # Calculate overall if needed
        players = []
        for ea_name, s in stats.items():
            games = s.get("games", 0)
            if games < 1:
                continue

            if stat == "overall":
                value = bot.aura.calculate_overall(s)
            else:
                value = s.get(stat, 0)

            players.append((ea_name, value, s))

        # Sort (descending, except possession_lost and fraud_score we might want ascending for good)
        reverse = True
        if stat in ["possession_lost", "fraud_score"]:
            reverse = False  # Lower is better for these

        players.sort(key=lambda x: x[1], reverse=reverse)

        # Build message
        intro = bot.darija.rankings_intro()
        lines = [intro, ""]

        for idx, (ea_name, value, s) in enumerate(players[:10], 1):
            nickname = bot.mapper.get_nickname(ea_name)
            line = bot.darija.rankings_entry(idx, nickname, stat, round(value, 1))
            lines.append(line)

        embed = Embed(
            title=f"📊 Rankings - {stat.upper()}",
            description="\n".join(lines),
            color=discord.Color.blue(),
        )

        await interaction.followup.send(embed=embed)
        _track_command(bot, "rankings", True)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")
        _track_command(bot, "rankings", False, str(e))

@bot.tree.command(name="roast", description="Roast a player")
@app_commands.describe(player="Player to roast")
async def roast_cmd(interaction: Interaction, player: str):
    """Roast a player."""
    await interaction.response.defer()

    try:
        result = _get_player_by_input(bot, player)
        if not result:
            msg = bot.darija.command_error(bot.mapper.get_nickname(player))
            await interaction.followup.send(msg)
            _track_command(bot, "roast", False, "player_not_found")
            return

        ea_name, stats = result
        nickname = bot.mapper.get_nickname(ea_name)

        card_file = _generate_card_file(bot, ea_name, stats)
        roast_msg = bot.roast.roast(ea_name, stats)

        embed = Embed(
            title=f"🔥 ROAST: {nickname}",
            description=roast_msg,
            color=discord.Color.orange(),
        )
        embed.set_image(url=f"attachment://{nickname}_card.png")

        await interaction.followup.send(embed=embed, file=card_file)
        _track_command(bot, "roast", True)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")
        _track_command(bot, "roast", False, str(e))

@bot.tree.command(name="ghost", description="Find the ghosts (inactive players)")
async def ghost_cmd(interaction: Interaction):
    """Find ghost players."""
    await interaction.response.defer()

    try:
        stats = bot.data.get_all_stats()
        if not stats:
            await interaction.followup.send("No data available.")
            _track_command(bot, "ghost", False, "no_data")
            return

        ghosts = []
        for ea_name, s in stats.items():
            games = s.get("games", 0)
            if games < 3 and games >= 0:
                ghosts.append((ea_name, s))

        if not ghosts:
            await interaction.followup.send("No ghosts found. Everyone is playing!")
            _track_command(bot, "ghost", True)
            return

        lines = ["👻 **GHOST DETECTED** 👻", ""]
        files = []

        for ea_name, s in ghosts[:5]:
            nickname = bot.mapper.get_nickname(ea_name)
            accusation = bot.roast.ghost_accusation(ea_name, s)
            lines.append(accusation)
            lines.append("\n")

            # Generate ghost card for first ghost
            if len(files) == 0:
                card_file = _generate_card_file(bot, ea_name, s, "ghost")
                files.append(card_file)

        embed = Embed(
            title="👻 Ghost Report",
            description="\n".join(lines),
            color=discord.Color.light_grey(),
        )

        if files:
            embed.set_image(url="attachment://ghost_card.png")
            await interaction.followup.send(embed=embed, file=files[0])
        else:
            await interaction.followup.send(embed=embed)

        _track_command(bot, "ghost", True)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")
        _track_command(bot, "ghost", False, str(e))

@bot.tree.command(name="carry", description="Find the carry of the team")
async def carry_cmd(interaction: Interaction):
    """Find the team carry."""
    await interaction.response.defer()

    try:
        stats = bot.data.get_all_stats()
        if not stats:
            await interaction.followup.send("No data available.")
            _track_command(bot, "carry", False, "no_data")
            return

        # Find carry: high impact + high win rate
        best = None
        best_score = -1
        for ea_name, s in stats.items():
            games = max(s.get("games", 1), 1)
            if games < 5:
                continue

            impact = s.get("impact", 0)
            wr = (s.get("wins", 0) / games) * 100
            overall = bot.aura.calculate_overall(s)

            carry_score = impact * 10 + wr + overall * 0.5
            if carry_score > best_score:
                best_score = carry_score
                best = (ea_name, s)

        if not best:
            await interaction.followup.send("No qualified carry found.")
            _track_command(bot, "carry", False, "no_qualified")
            return

        ea_name, s = best
        nickname = bot.mapper.get_nickname(ea_name)

        card_file = _generate_card_file(bot, ea_name, s, "carry")
        praise = bot.roast.carry_praise(ea_name, s)

        embed = Embed(
            title=f"🎯 CARRY: {nickname}",
            description=praise,
            color=discord.Color.blue(),
        )
        embed.set_image(url=f"attachment://{nickname}_card.png")

        await interaction.followup.send(embed=embed, file=card_file)
        _track_command(bot, "carry", True)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")
        _track_command(bot, "carry", False, str(e))

@bot.tree.command(name="club", description="Show club summary")
async def club_cmd(interaction: Interaction):
    """Show club summary."""
    await interaction.response.defer()

    try:
        stats = bot.data.get_all_stats()
        if not stats:
            await interaction.followup.send("No data available.")
            _track_command(bot, "club", False, "no_data")
            return

        total_games = sum(s.get("games", 0) for s in stats.values())
        total_goals = sum(s.get("goals", 0) for s in stats.values())
        total_assists = sum(s.get("assists", 0) for s in stats.values())
        total_wins = sum(s.get("wins", 0) for s in stats.values())

        avg_rating = 0
        count = 0
        for s in stats.values():
            if s.get("games", 0) > 0:
                avg_rating += s.get("rating", 0)
                count += 1
        avg_rating = round(avg_rating / max(count, 1), 1)

        intro = bot.darija.club_summary("Pro Clubs")

        embed = Embed(
            title="🏟️ Club Summary",
            description=intro,
            color=discord.Color.green(),
        )

        embed.add_field(name="Total Games", value=total_games, inline=True)
        embed.add_field(name="Total Goals", value=total_goals, inline=True)
        embed.add_field(name="Total Assists", value=total_assists, inline=True)
        embed.add_field(name="Total Wins", value=total_wins, inline=True)
        embed.add_field(name="Avg Rating", value=avg_rating, inline=True)
        embed.add_field(name="Players", value=len(stats), inline=True)

        await interaction.followup.send(embed=embed)
        _track_command(bot, "club", True)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")
        _track_command(bot, "club", False, str(e))

# ============== LEGACY PREFIX COMMANDS (Fallback) ==============

@bot.command(name="ping")
async def ping_cmd(ctx):
    """Test command."""
    await ctx.send("Pong! ProClubsTracker is online.")

@bot.command(name="audit")
async def audit_cmd(ctx):
    """Show command audit report."""
    lines = ["**Command Audit Report**", ""]
    for cmd, data in bot.command_stats.items():
        total = data["success"] + data["fail"]
        rate = (data["success"] / total * 100) if total > 0 else 0
        lines.append(f"`/{cmd}`: {data['success']}/{total} ({rate:.0f}% success)")
        if data["errors"]:
            lines.append(f"  Recent errors: {', '.join(data['errors'][-3:])}")

    await ctx.send("\n".join(lines))

# ============== MAIN ==============

def main():
    """Run the bot."""
    if not config.DISCORD_TOKEN:
        print("[Bot] ERROR: DISCORD_TOKEN not set")
        return

    bot.run(config.DISCORD_TOKEN)

if __name__ == "__main__":
    main()
