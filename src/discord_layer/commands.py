from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.core.logging import get_logger

logger = get_logger(__name__)

REQUIRED_COMMANDS = [
    "player",
    "mvp",
    "fraud",
    "ghost",
    "carry",
    "who_sold",
    "ball_loser",
    "playmaker",
    "sniper",
    "compare",
    "court_case",
    "club",
    "records",
    "form",
    "awards",
    "legend",
    "hall_of_shame",
    "hall_of_fame",
    "match_report",
    "leaderboard",
]


def _phase_message(command: str) -> str:
    return (
        f"✅ `/{command}` is registered.\n"
        "Phase 2 is now wiring Pro Clubs Tracker + match.players truth. "
        "Phase 3 will add the full roast/stat/card behavior."
    )


def _get_match_service(bot: commands.Bot):
    return getattr(bot, "matches", None)


def register_commands(bot: commands.Bot) -> None:
    @bot.tree.command(name="sync", description="Fetch latest club data from Pro Clubs Tracker")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
    async def sync(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        svc = _get_match_service(bot)
        if not svc:
            await interaction.followup.send("Match service not wired.")
            return
        snapshot = await svc.refresh(force=True, source="discord:/sync")
        latest = snapshot.latest_match
        if not latest:
            await interaction.followup.send(f"Sync ok. Matches: {len(snapshot.matches)} (no latest match).")
            return
        await interaction.followup.send(
            f"✅ Sync ok. Latest: {latest.score_for}-{latest.score_against} vs {latest.opponent} | "
            f"match.players: {len(latest.players)}"
        )

    @bot.tree.command(name="status", description="Show current data status")
    async def status(interaction: discord.Interaction) -> None:
        svc = _get_match_service(bot)
        if not svc:
            await interaction.response.send_message("Match service not wired.")
            return
        st = svc.status()
        await interaction.response.send_message(
            "\n".join(
                [
                    "📊 Data status",
                    f"Latest match: {st.get('latest_match_id')}",
                    f"Score: {st.get('latest_score')} vs {st.get('opponent')}",
                    f"match.players: {st.get('latest_players')}",
                ]
            )
        )

    # ---- required command shells (still phase-3 logic later) ----
    @bot.tree.command(name="player", description="Player profile, stats, lore, and card")
    @app_commands.describe(player="Nickname, EA ID, or PSN")
    async def player(interaction: discord.Interaction, player: str) -> None:
        await interaction.response.send_message(_phase_message("player"))

    @bot.tree.command(name="mvp", description="Best performer from eligible match players")
    async def mvp(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("mvp"))

    @bot.tree.command(name="fraud", description="Fraud verdict for a player")
    @app_commands.describe(player="Nickname, EA ID, or PSN")
    async def fraud(interaction: discord.Interaction, player: Optional[str] = None) -> None:
        await interaction.response.send_message(_phase_message("fraud"))

    @bot.tree.command(name="ghost", description="Ghost verdict from match activity")
    async def ghost(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("ghost"))

    @bot.tree.command(name="carry", description="Who carried the squad")
    async def carry(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("carry"))

    @bot.tree.command(name="who_sold", description="Who sold the match")
    async def who_sold(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("who_sold"))

    @bot.tree.command(name="ball_loser", description="Most dangerous ball loss merchant")
    async def ball_loser(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("ball_loser"))

    @bot.tree.command(name="playmaker", description="Chance creator and pass dictator")
    async def playmaker(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("playmaker"))

    @bot.tree.command(name="sniper", description="Finishing and shot efficiency king")
    async def sniper(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("sniper"))

    @bot.tree.command(name="compare", description="Compare two players")
    @app_commands.describe(player_one="First player", player_two="Second player")
    async def compare(interaction: discord.Interaction, player_one: str, player_two: str) -> None:
        await interaction.response.send_message(_phase_message("compare"))

    @bot.tree.command(name="court_case", description="Open the tribunal case file")
    @app_commands.describe(player="Accused player")
    async def court_case(interaction: discord.Interaction, player: str) -> None:
        await interaction.response.send_message(_phase_message("court_case"))

    @bot.tree.command(name="club", description="Club summary and squad state")
    async def club(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("club"))

    @bot.tree.command(name="records", description="Club records and broken records")
    async def records(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("records"))

    @bot.tree.command(name="form", description="Recent form for a player")
    @app_commands.describe(player="Player", matches="Number of recent matches")
    async def form(interaction: discord.Interaction, player: str, matches: int = 5) -> None:
        await interaction.response.send_message(_phase_message("form"))

    @bot.tree.command(name="awards", description="Awards and weekly winners")
    async def awards(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("awards"))

    @bot.tree.command(name="legend", description="Legend card and lore")
    @app_commands.describe(player="Optional player")
    async def legend(interaction: discord.Interaction, player: Optional[str] = None) -> None:
        await interaction.response.send_message(_phase_message("legend"))

    @bot.tree.command(name="hall_of_shame", description="Historic fraud museum")
    async def hall_of_shame(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("hall_of_shame"))

    @bot.tree.command(name="hall_of_fame", description="Historic elite performances")
    async def hall_of_fame(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("hall_of_fame"))

    @bot.tree.command(name="match_report", description="Latest match report with banter")
    async def match_report(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(_phase_message("match_report"))

    @bot.tree.command(name="leaderboard", description="Leaderboard by metric")
    @app_commands.describe(metric="goals, assists, rating, minutes, losses, saves, matches")
    async def leaderboard(interaction: discord.Interaction, metric: str = "goals") -> None:
        await interaction.response.send_message(_phase_message("leaderboard"))

    logger.info("Registered required shells + /sync + /status")
