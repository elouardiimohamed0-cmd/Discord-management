from __future__ import annotations

import asyncio
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.core.errors import NoMatchesFound, PlayerNotInMatch
from src.core.logging import get_logger
from src.domain.models import Match

logger = get_logger(__name__)


def _get_match_service(bot: commands.Bot):
    return getattr(bot, "matches", None)


def _get_roast(bot: commands.Bot):
    return getattr(bot, "roast", None)


def _get_cards(bot: commands.Bot):
    return getattr(bot, "cards", None)


def _get_squad(bot: commands.Bot):
    return getattr(bot, "squad", None)


def _get_records(bot: commands.Bot):
    return getattr(bot, "records", None)


def _get_auto(bot: commands.Bot):
    return getattr(bot, "auto", None)


def _get_video(bot: commands.Bot):
    return getattr(bot, "video", None)


def _require_latest(bot: commands.Bot) -> Match:
    svc = _get_match_service(bot)
    if not svc:
        raise RuntimeError("Match service not available")
    match = svc.latest_match()
    if not match:
        raise NoMatchesFound("No matches found. Run /sync first.")
    return match


def _resolve_player(bot: commands.Bot, query: str, match: Match):
    squad = _get_squad(bot)
    identity = squad.find(query) if squad else None
    if not identity:
        raise PlayerNotInMatch(f"Player '{query}' not found in squad registry.")
    player = match.get_player(identity.ea_id)
    return player, identity


async def _safe_defer(interaction: discord.Interaction) -> bool:
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(thinking=True)
            return True
    except discord.errors.NotFound:
        logger.warning("Interaction token expired before defer")
        return False
    except Exception as e:
        logger.warning("Failed to defer interaction: %s", e)
        return False


async def _safe_followup(
    interaction: discord.Interaction,
    content: str = None,
    *,
    embed: discord.Embed = None,
    file: discord.File = None,
) -> None:
    try:
        kwargs = {}
        if content:
            kwargs["content"] = content
        if embed:
            kwargs["embed"] = embed
        if file:
            kwargs["file"] = file
        await interaction.followup.send(**kwargs)
    except discord.errors.NotFound:
        logger.warning("Followup failed: interaction token expired")
    except Exception as e:
        logger.error("Followup failed: %s", e)


def register_commands(bot: commands.Bot) -> None:
    # ============================================================
    # /ping
    # ============================================================
    @bot.tree.command(name="ping", description="Check if bot is alive")
    async def ping(interaction: discord.Interaction) -> None:
        try:
            await interaction.response.send_message(
                "🟢 Pong! Bot is online.", ephemeral=True
            )
        except Exception as e:
            logger.error("Ping failed: %s", e)

    # ============================================================
    # /sync
    # ============================================================
    @bot.tree.command(
        name="sync", description="Fetch latest club data from Pro Clubs Tracker"
    )
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
    async def sync(interaction: discord.Interaction) -> None:
        if not await _safe_defer(interaction):
            return

        svc = _get_match_service(bot)
        if not svc:
            await _safe_followup(interaction, "❌ Match service not wired.")
            return

        try:
            snapshot = await asyncio.wait_for(
                svc.refresh(force=True, source="discord:/sync"), timeout=45.0
            )
            latest = snapshot.latest_match

            if not latest:
                msg = "✅ Sync complete. No new match found this scrape."
                await _safe_followup(interaction, msg)
                return

            result_emoji = (
                "WIN"
                if latest.result == "W"
                else "LOSS" if latest.result == "L" else "DRAW"
            )
            result_icon = (
                "🟢"
                if latest.result == "W"
                else "🔴" if latest.result == "L" else "🟡"
            )
            lines = [
                "**Sync complete**",
                "",
                "**Latest Match**",
                f"Score: **{latest.score_for}-{latest.score_against}** vs {latest.opponent}",
                f"Result: {result_icon} {result_emoji}",
                f"Players: {len(latest.players)}",
            ]

            if latest.mvp:
                mvp_id = latest.mvp.ea_id
                squad = _get_squad(bot)
                identity = squad.find_by_ea_id(mvp_id) if squad else None
                if not identity and squad:
                    identity = squad.find_by_display_name(latest.mvp.display_name)
                mvp_name = identity.nickname if identity else latest.mvp.display_name
                lines.append(f"MVP: {mvp_name} ({latest.mvp.rating}⭐)")

            await _safe_followup(interaction, "\n".join(lines))

        except asyncio.TimeoutError:
            logger.error("Sync timed out after 45s")
            await _safe_followup(
                interaction,
                "⏳ Sync timed out. The scraper is taking too long. Try again in a minute.",
            )
        except Exception as e:
            logger.error("Sync failed: %s", e, exc_info=True)
            await _safe_followup(
                interaction, f"❌ Sync failed: {str(e)[:500]}"
            )

    # ============================================================
    # /status — Show bot status and latest match info
    # ============================================================
    @bot.tree.command(name="status", description="Show bot status and latest match")
    async def status(interaction: discord.Interaction) -> None:
        """Show bot status and latest match info."""
        if not await _safe_defer(interaction):
            return

        try:
            svc = _get_match_service(bot)
            if not svc:
                await _safe_followup(
                    interaction, "❌ Match service not available."
                )
                return

            match = svc.latest_match()
            if not match:
                await _safe_followup(
                    interaction, "❌ No matches found. Run `/sync` first."
                )
                return

            embed = discord.Embed(
                title="🤖 Bot Status",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(
                name="Latest Match",
                value=match.match_id or "N/A",
                inline=False,
            )
            embed.add_field(
                name="Score",
                value=f"{match.score_for}-{match.score_against}",
                inline=True,
            )
            embed.add_field(
                name="Opponent", value=match.opponent, inline=True
            )
            embed.add_field(
                name="Players", value=str(len(match.players)), inline=True
            )

            await _safe_followup(interaction, embed=embed)

        except Exception as e:
            logger.error("Status command error: %s", e, exc_info=True)
            await _safe_followup(
                interaction, f"❌ Error: {str(e)[:500]}"
            )

    # ============================================================
    # /stats — Show player stats from latest match
    # ============================================================
    @bot.tree.command(
        name="stats", description="Show player stats from the latest match"
    )
    @app_commands.describe(
        player="Player name (nickname, PSN, or EA ID)"
    )
    async def stats(interaction: discord.Interaction, player: str) -> None:
        """Show detailed stats for a player from the latest match."""
        if not await _safe_defer(interaction):
            return

        try:
            match = _require_latest(bot)
            player_stats, identity = _resolve_player(bot, player, match)

            embed = discord.Embed(
                title=f"📊 Stats for {identity.nickname if identity else player}",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(
                name="Rating", value=f"{player_stats.rating}⭐", inline=True
            )
            embed.add_field(
                name="Goals", value=str(player_stats.goals), inline=True
            )
            embed.add_field(
                name="Assists",
                value=str(player_stats.assists),
                inline=True,
            )
            embed.add_field(
                name="Shots", value=str(player_stats.shots), inline=True
            )
            embed.add_field(
                name="Pass Accuracy",
                value=f"{player_stats.pass_accuracy}%",
                inline=True,
            )
            embed.add_field(
                name="Minutes",
                value=str(player_stats.minutes),
                inline=True,
            )
            embed.add_field(
                name="Tackles",
                value=str(player_stats.tackles),
                inline=True,
            )
            embed.add_field(
                name="Saves",
                value=str(player_stats.saves),
                inline=True,
            )
            embed.add_field(
                name="Possession Losses",
                value=str(player_stats.possession_losses),
                inline=True,
            )

            await _safe_followup(interaction, embed=embed)

        except PlayerNotInMatch as e:
            await _safe_followup(interaction, f"❌ {e}")
        except NoMatchesFound as e:
            await _safe_followup(interaction, f"❌ {e}")
        except Exception as e:
            logger.error("Stats command error: %s", e, exc_info=True)
            await _safe_followup(
                interaction, "❌ An unexpected error occurred."
            )

    # ============================================================
    # /form — Show player form history
    # ============================================================
    @bot.tree.command(
        name="form", description="Show player form over recent matches"
    )
    @app_commands.describe(player="Player name")
    async def form(interaction: discord.Interaction, player: str) -> None:
        """Show player form over recent matches."""
        if not await _safe_defer(interaction):
            return

        try:
            squad = _get_squad(bot)
            if not squad:
                await _safe_followup(
                    interaction, "❌ Squad registry not loaded."
                )
                return

            identity = squad.find(player)
            if not identity:
                await _safe_followup(
                    interaction, f"❌ Player '{player}' not found."
                )
                return

            svc = _get_match_service(bot)
            if not svc:
                await _safe_followup(
                    interaction, "❌ Match service not available."
                )
                return

            repo = getattr(svc, "repo", None)
            if not repo:
                await _safe_followup(
                    interaction, "❌ Repository not available."
                )
                return

            player_matches = repo.player_matches(identity.ea_id, limit=10)
            if not player_matches:
                await _safe_followup(interaction, "📭 No history found.")
                return

            lines = [
                f"📈 Form for **{identity.nickname}** (last {len(player_matches)} matches)",
                "",
            ]
            for pm in player_matches:
                lines.append(
                    f"• Rating: {pm.rating} | Goals: {pm.goals} | Assists: {pm.assists} | Minutes: {pm.minutes}"
                )

            await _safe_followup(interaction, "\n".join(lines))

        except Exception as e:
            logger.error("Form command error: %s", e, exc_info=True)
            await _safe_followup(
                interaction, f"❌ Error loading form: {str(e)[:500]}"
            )

    # ============================================================
    # /records — Show club records
    # ============================================================
    @bot.tree.command(
        name="records", description="Show club records and achievements"
    )
    async def records(interaction: discord.Interaction) -> None:
        """Show club records and achievements."""
        if not await _safe_defer(interaction):
            return

        try:
            records_svc = _get_records(bot)
            if not records_svc:
                await _safe_followup(
                    interaction, "❌ Records service not available."
                )
                return

            all_records = records_svc.compute_all_records()
            if not all_records:
                await _safe_followup(
                    interaction, "📭 No records found yet."
                )
                return

            embed = discord.Embed(
                title="🏆 Club Records",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow(),
            )

            for rec in all_records[:10]:  # Show top 10
                embed.add_field(
                    name=rec["title"],
                    value=f"{rec['text']} (value: {rec['value']})",
                    inline=False,
                )

            await _safe_followup(interaction, embed=embed)

        except Exception as e:
            logger.error("Records command error: %s", e, exc_info=True)
            await _safe_followup(
                interaction, f"❌ Error loading records: {str(e)[:500]}"
            )

    # ============================================================
    # /sniper — Show best shooter from latest match
    # ============================================================
    @bot.tree.command(
        name="sniper", description="Show the best shooter from the latest match"
    )
    async def sniper(interaction: discord.Interaction) -> None:
        """Show the best shooter from the latest match."""
        if not await _safe_defer(interaction):
            return

        try:
            match = _require_latest(bot)
            if not match.players:
                await _safe_followup(
                    interaction, "❌ No player data in latest match."
                )
                return

            best_shooter = match.sniper
            if not best_shooter:
                await _safe_followup(
                    interaction,
                    "🎯 No eligible shooters found (need at least 1 shot).",
                )
                return

            squad = _get_squad(bot)
            identity = (
                squad.find_by_ea_id(best_shooter.ea_id)
                if squad
                else None
            )
            if not identity and squad:
                identity = squad.find_by_display_name(
                    best_shooter.display_name
                )

            name = identity.nickname if identity else best_shooter.display_name
            accuracy = (
                best_shooter.goals / max(best_shooter.shots, 1)
            ) * 100
            on_target_pct = (
                best_shooter.shots_on_target / max(best_shooter.shots, 1)
            ) * 100

            embed = discord.Embed(
                title="🎯 Match Sniper",
                description=f"**{name}**",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(
                name="Goals", value=str(best_shooter.goals), inline=True
            )
            embed.add_field(
                name="Shots", value=str(best_shooter.shots), inline=True
            )
            embed.add_field(
                name="Shot Accuracy",
                value=f"{accuracy:.1f}%",
                inline=True,
            )
            embed.add_field(
                name="On Target",
                value=f"{on_target_pct:.1f}%",
                inline=True,
            )

            await _safe_followup(interaction, embed=embed)

        except NoMatchesFound as e:
            await _safe_followup(interaction, f"❌ {e}")
        except Exception as e:
            logger.error("Sniper command error: %s", e, exc_info=True)
            await _safe_followup(
                interaction, f"❌ Error: {str(e)[:500]}"
            )

    # ============================================================
    # /awards — Show awards system status
    # ============================================================
    @bot.tree.command(
        name="awards", description="Show awards system status"
    )
    async def awards(interaction: discord.Interaction) -> None:
        """Show awards system status."""
        if not await _safe_defer(interaction):
            return

        try:
            auto = _get_auto(bot)
            if auto and getattr(auto, "awards_enabled", False):
                await _safe_followup(
                    interaction,
                    "🏆 Awards system active. Check daily channel for auto-posts.",
                )
            else:
                await _safe_followup(
                    interaction,
                    "🏆 Awards system is configured. Daily posts will appear in the designated channel.",
                )

        except Exception as e:
            logger.error("Awards command error: %s", e, exc_info=True)
            await _safe_followup(
                interaction, f"❌ Error: {str(e)[:500]}"
            )

    # ============================================================
    # /mvp — Show MVP from latest match
    # ============================================================
    @bot.tree.command(
        name="mvp", description="Show the MVP from the latest match"
    )
    async def mvp(interaction: discord.Interaction) -> None:
        """Show the MVP from the latest match."""
        if not await _safe_defer(interaction):
            return

        try:
            match = _require_latest(bot)
            if not match.players:
                await _safe_followup(
                    interaction, "❌ No player data in latest match."
                )
                return

            mvp_stats = match.mvp
            if not mvp_stats:
                await _safe_followup(
                    interaction, "❌ Could not determine MVP."
                )
                return

            squad = _get_squad(bot)
            identity = (
                squad.find_by_ea_id(mvp_stats.ea_id) if squad else None
            )
            if not identity and squad:
                identity = squad.find_by_display_name(
                    mvp_stats.display_name
                )

            name = identity.nickname if identity else mvp_stats.display_name

            embed = discord.Embed(
                title="👑 Match MVP",
                description=f"**{name}**",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(
                name="Rating", value=f"{mvp_stats.rating}⭐", inline=True
            )
            embed.add_field(
                name="Goals", value=str(mvp_stats.goals), inline=True
            )
            embed.add_field(
                name="Assists",
                value=str(mvp_stats.assists),
                inline=True,
            )

            await _safe_followup(interaction, embed=embed)

        except NoMatchesFound as e:
            await _safe_followup(interaction, f"❌ {e}")
        except Exception as e:
            logger.error("MVP command error: %s", e, exc_info=True)
            await _safe_followup(
                interaction, f"❌ Error: {str(e)[:500]}"
            )

    # ============================================================
    # /fraud — Show fraud of the match
    # ============================================================
    @bot.tree.command(
        name="fraud", description="Show the fraud of the latest match"
    )
    async def fraud(interaction: discord.Interaction) -> None:
        """Show the fraud (worst performer) of the latest match."""
        if not await _safe_defer(interaction):
            return

        try:
            match = _require_latest(bot)
            if not match.players:
                await _safe_followup(
                    interaction, "❌ No player data in latest match."
                )
                return

            fraud_stats = match.fraud
            if not fraud_stats:
                await _safe_followup(
                    interaction, "❌ Could not determine fraud."
                )
                return

            squad = _get_squad(bot)
            identity = (
                squad.find_by_ea_id(fraud_stats.ea_id)
                if squad
                else None
            )
            if not identity and squad:
                identity = squad.find_by_display_name(
                    fraud_stats.display_name
                )

            name = identity.nickname if identity else fraud_stats.display_name

            embed = discord.Embed(
                title="🤡 Match Fraud",
                description=f"**{name}**",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(
                name="Rating",
                value=f"{fraud_stats.rating}⭐",
                inline=True,
            )
            embed.add_field(
                name="Possession Losses",
                value=str(fraud_stats.possession_losses),
                inline=True,
            )
            embed.add_field(
                name="Minutes",
                value=str(fraud_stats.minutes),
                inline=True,
            )

            await _safe_followup(interaction, embed=embed)

        except NoMatchesFound as e:
            await _safe_followup(interaction, f"❌ {e}")
        except Exception as e:
            logger.error("Fraud command error: %s", e, exc_info=True)
            await _safe_followup(
                interaction, f"❌ Error: {str(e)[:500]}"
            )

    # ============================================================
    # /carry — Show carry of the match
    # ============================================================
    @bot.tree.command(
        name="carry", description="Show the carry of the latest match"
    )
    async def carry(interaction: discord.Interaction) -> None:
        """Show the carry (best goal contributor) of the latest match."""
        if not await _safe_defer(interaction):
            return

        try:
            match = _require_latest(bot)
            if not match.players:
                await _safe_followup(
                    interaction, "❌ No player data in latest match."
                )
                return

            carry_stats = match.carry
            if not carry_stats:
                await _safe_followup(
                    interaction, "❌ Could not determine carry."
                )
                return

            squad = _get_squad(bot)
            identity = (
                squad.find_by_ea_id(carry_stats.ea_id)
                if squad
                else None
            )
            if not identity and squad:
                identity = squad.find_by_display_name(
                    carry_stats.display_name
                )

            name = identity.nickname if identity else carry_stats.display_name

            embed = discord.Embed(
                title="💪 Match Carry",
                description=f"**{name}**",
                color=discord.Color.purple(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(
                name="Goals + Assists",
                value=str(carry_stats.goals + carry_stats.assists),
                inline=True,
            )
            embed.add_field(
                name="Rating",
                value=f"{carry_stats.rating}⭐",
                inline=True,
            )
            embed.add_field(
                name="Key Passes",
                value=str(carry_stats.key_passes),
                inline=True,
            )

            await _safe_followup(interaction, embed=embed)

        except NoMatchesFound as e:
            await _safe_followup(interaction, f"❌ {e}")
        except Exception as e:
            logger.error("Carry command error: %s", e, exc_info=True)
            await _safe_followup(
                interaction, f"❌ Error: {str(e)[:500]}"
            )

    # ============================================================
    # /roast — Roast a player
    # ============================================================
    @bot.tree.command(name="roast", description="Roast a player")
    @app_commands.describe(player="Player name to roast")
    async def roast(interaction: discord.Interaction, player: str) -> None:
        """Roast a player based on their latest performance."""
        if not await _safe_defer(interaction):
            return

        try:
            match = _require_latest(bot)
            player_stats, identity = _resolve_player(bot, player, match)

            roast_engine = _get_roast(bot)
            if roast_engine:
                roast_text = roast_engine.roast(
                    identity.nickname if identity else player,
                    player_stats,
                )
            else:
                roast_text = f"{identity.nickname if identity else player} had a rating of {player_stats.rating}... that's something, I guess."

            embed = discord.Embed(
                title="🔥 Roast",
                description=roast_text,
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )

            await _safe_followup(interaction, embed=embed)

        except PlayerNotInMatch as e:
            await _safe_followup(interaction, f"❌ {e}")
        except NoMatchesFound as e:
            await _safe_followup(interaction, f"❌ {e}")
        except Exception as e:
            logger.error("Roast command error: %s", e, exc_info=True)
            await _safe_followup(
                interaction, f"❌ Error: {str(e)[:500]}"
            )

    # ============================================================
    # /card — Generate a player card
    # ============================================================
    @bot.tree.command(
        name="card", description="Generate a player card"
    )
    @app_commands.describe(player="Player name")
    async def card(interaction: discord.Interaction, player: str) -> None:
        """Generate a player card image."""
        if not await _safe_defer(interaction):
            return

        try:
            match = _require_latest(bot)
            player_stats, identity = _resolve_player(bot, player, match)

            card_engine = _get_cards(bot)
            if card_engine:
                file = card_engine.generate(
                    identity.nickname if identity else player,
                    player_stats,
                )
                await _safe_followup(interaction, file=file)
            else:
                await _safe_followup(
                    interaction,
                    f"📇 Card for {identity.nickname if identity else player}: Rating {player_stats.rating} | Goals: {player_stats.goals} | Assists: {player_stats.assists}",
                )

        except PlayerNotInMatch as e:
            await _safe_followup(interaction, f"❌ {e}")
        except NoMatchesFound as e:
            await _safe_followup(interaction, f"❌ {e}")
        except Exception as e:
            logger.error("Card command error: %s", e, exc_info=True)
            await _safe_followup(
                interaction, f"❌ Error: {str(e)[:500]}"
            )

    # ============================================================
    # /leaderboard — Show leaderboard
    # ============================================================
    @bot.tree.command(
        name="leaderboard", description="Show the club leaderboard"
    )
    @app_commands.describe(
        metric="Metric to rank by (goals, assists, rating, saves)"
    )
    async def leaderboard(
        interaction: discord.Interaction,
        metric: str = "goals",
    ) -> None:
        """Show the club leaderboard by metric."""
        if not await _safe_defer(interaction):
            return

        try:
            svc = _get_match_service(bot)
            if not svc:
                await _safe_followup(
                    interaction, "❌ Match service not available."
                )
                return

            repo = getattr(svc, "repo", None)
            if not repo:
                await _safe_followup(
                    interaction, "❌ Repository not available."
                )
                return

            allowed_metrics = ["goals", "assists", "rating", "saves", "minutes", "tackles"]
            if metric.lower() not in allowed_metrics:
                await _safe_followup(
                    interaction,
                    f"❌ Invalid metric. Choose from: {', '.join(allowed_metrics)}",
                )
                return

            leaderboard_data = repo.aggregate_leaderboard(
                metric=metric.lower(), limit=10
            )

            if not leaderboard_data:
                await _safe_followup(
                    interaction, "📭 No data for leaderboard."
                )
                return

            embed = discord.Embed(
                title=f"🏅 Leaderboard — {metric.title()}",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )

            squad = _get_squad(bot)
            for i, entry in enumerate(leaderboard_data, 1):
                identity = (
                    squad.find_by_ea_id(entry["ea_id"])
                    if squad
                    else None
                )
                name = (
                    identity.nickname
                    if identity
                    else entry["display_name"]
                )
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"#{i}")
                embed.add_field(
                    name=f"{medal} {name}",
                    value=f"{metric.title()}: {entry['value']:.1f} | Matches: {entry['matches']}",
                    inline=False,
                )

            await _safe_followup(interaction, embed=embed)

        except Exception as e:
            logger.error("Leaderboard command error: %s", e, exc_info=True)
            await _safe_followup(
                interaction, f"❌ Error: {str(e)[:500]}"
            )

    # ============================================================
    # /halloffame — Show hall of fame
    # ============================================================
    @bot.tree.command(
        name="halloffame", description="Show the Hall of Fame"
    )
    async def halloffame(interaction: discord.Interaction) -> None:
        """Show the Hall of Fame (best performers)."""
        if not await _safe_defer(interaction):
            return

        try:
            records_svc = _get_records(bot)
            if not records_svc:
                await _safe_followup(
                    interaction, "❌ Records service not available."
                )
                return

            hof = records_svc.get_hall_of_fame(limit=10)
            if not hof:
                await _safe_followup(
                    interaction, "📭 Hall of Fame is empty."
                )
                return

            embed = discord.Embed(
                title="🌟 Hall of Fame",
                description="Best performers (min 5 matches)",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow(),
            )

            for i, entry in enumerate(hof, 1):
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"#{i}")
                embed.add_field(
                    name=f"{medal} {entry['nickname']}",
                    value=f"Avg Rating: {entry['avg_rating']} | Matches: {entry['matches']} | Goals: {entry['goals']} | Assists: {entry['assists']}",
                    inline=False,
                )

            await _safe_followup(interaction, embed=embed)

        except Exception as e:
            logger.error("Hall of Fame error: %s", e, exc_info=True)
            await _safe_followup(
                interaction, f"❌ Error: {str(e)[:500]}"
            )

    # ============================================================
    # /hallofshame — Show hall of shame
    # ============================================================
    @bot.tree.command(
        name="hallofshame", description="Show the Hall of Shame"
    )
    async def hallofshame(interaction: discord.Interaction) -> None:
        """Show the Hall of Shame (worst performers)."""
        if not await _safe_defer(interaction):
            return

        try:
            records_svc = _get_records(bot)
            if not records_svc:
                await _safe_followup(
                    interaction, "❌ Records service not available."
                )
                return

            hos = records_svc.get_hall_of_shame(limit=10)
            if not hos:
                await _safe_followup(
                    interaction, "📭 Hall of Shame is empty."
                )
                return

            embed = discord.Embed(
                title="💩 Hall of Shame",
                description="Worst performers (min 5 matches)",
                color=discord.Color.dark_red(),
                timestamp=discord.utils.utcnow(),
            )

            for i, entry in enumerate(hos, 1):
                embed.add_field(
                    name=f"#{i} {entry['nickname']}",
                    value=f"Avg Rating: {entry['avg_rating']} | Matches: {entry['matches']} | Losses: {entry['losses']} | Cards: {entry['cards']}",
                    inline=False,
                )

            await _safe_followup(interaction, embed=embed)

        except Exception as e:
            logger.error("Hall of Shame error: %s", e, exc_info=True)
            await _safe_followup(
                interaction, f"❌ Error: {str(e)[:500]}"
            )

    # ============================================================
    # /debug
    # ============================================================
    @bot.tree.command(
        name="debug", description="Debug bot state and database"
    )
    async def debug(interaction: discord.Interaction) -> None:
        """Debug command to check database state and identify issues."""
        if not await _safe_defer(interaction):
            return

        try:
            svc = _get_match_service(bot)
            if not svc:
                await _safe_followup(
                    interaction, "❌ Match service not available."
                )
                return

            repo = getattr(svc, "repo", None)
            if not repo:
                await _safe_followup(
                    interaction, "❌ Repository not available."
                )
                return

            from src.data.database import Database

            db = getattr(repo, "db", None)

            lines = ["**🔍 Debug Report**", ""]

            # Check latest match from DB
            latest = repo.latest_match()
            if latest:
                lines.append(f"**DB Latest Match:** {latest.match_id}")
                lines.append(f"- Opponent: {latest.opponent}")
                lines.append(
                    f"- Score: {latest.score_for}-{latest.score_against}"
                )
                lines.append(f"- Players: {len(latest.players)}")
                if latest.mvp:
                    lines.append(
                        f"- MVP: {latest.mvp.display_name} (rating: {latest.mvp.rating})"
                    )
            else:
                lines.append("**DB Latest Match:** None ❌")

            lines.append("")

            # Check total matches
            all_matches = repo.last_matches(limit=100)
            lines.append(f"**Total matches in DB:** {len(all_matches)}")

            # Check squad registry
            squad = _get_squad(bot)
            if squad:
                all_players = squad.all()
                lines.append(f"**Squad players:** {len(all_players)}")
                lines.append(f"- By EA ID: {len(squad._by_ea_id)}")
                lines.append(f"- By nickname: {len(squad._by_nickname)}")
                lines.append(f"- By PSN: {len(squad._by_psn)}")
                if all_players:
                    sample = all_players[0]
                    lines.append(
                        f"- Sample: {sample.nickname} (ea_id={sample.ea_id})"
                    )
            else:
                lines.append("**Squad:** Not loaded ❌")

            lines.append("")

            # Check DB file path
            if db:
                lines.append(f"**DB Path:** {db.path}")
                lines.append(f"**DB exists:** {db.path.exists()}")
            else:
                lines.append("**DB:** Not accessible ❌")

            # Check scrape log
            try:
                stats = (
                    repo.get_scrape_stats()
                    if hasattr(repo, "get_scrape_stats")
                    else None
                )
                if stats:
                    lines.append(
                        f"**Scrapes (24h):** {stats['total_attempts']} total, {stats['successes']} success, {stats['failures']} fail"
                    )
                else:
                    lines.append("**Scrape stats:** Not available")
            except Exception as e:
                lines.append(f"**Scrape stats:** Error - {e}")

            await _safe_followup(interaction, "\n".join(lines))

        except Exception as e:
            logger.error("Debug command error: %s", e, exc_info=True)
            await _safe_followup(
                interaction, f"❌ Debug failed: {str(e)[:500]}"
            )
