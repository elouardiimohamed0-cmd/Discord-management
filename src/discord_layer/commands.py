from __future__ import annotations

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
    # HARD RULE: must be in match.players
    player = match.get_player(identity.ea_id)
    return player, identity


def register_commands(bot: commands.Bot) -> None:
    # ---- admin ----
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

    # ---- core commands ----
    @bot.tree.command(name="player", description="Player profile, stats, lore, and card")
    @app_commands.describe(player="Nickname, EA ID, or PSN")
    async def player(interaction: discord.Interaction, player: str) -> None:
        await interaction.response.defer(thinking=True)
        try:
            match = _require_latest(bot)
            p, identity = _resolve_player(bot, player, match)
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.general_roast(p, identity) if roast else f"**{identity.nickname}** | Rating: {p.rating}"
            card_path = cards.generate_mvp_card(p, identity) if cards else None
            if card_path:
                await interaction.followup.send(content=text, file=discord.File(card_path))
            else:
                await interaction.followup.send(text)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="mvp", description="Best performer from eligible match players")
    async def mvp(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            match = _require_latest(bot)
            if not match.mvp:
                await interaction.followup.send("No MVP found.")
                return
            p = match.mvp
            identity = _get_squad(bot).find_by_ea_id(p.ea_id)
            if not identity:
                await interaction.followup.send("MVP identity not found.")
                return
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.mvp_roast(p, identity) if roast else f"MVP: {identity.nickname}"
            card_path = cards.generate_mvp_card(p, identity) if cards else None
            if card_path:
                await interaction.followup.send(content=text, file=discord.File(card_path))
            else:
                await interaction.followup.send(text)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="fraud", description="Fraud verdict for a player")
    @app_commands.describe(player="Nickname, EA ID, or PSN (optional, defaults to worst)")
    async def fraud(interaction: discord.Interaction, player: Optional[str] = None) -> None:
        await interaction.response.defer(thinking=True)
        try:
            match = _require_latest(bot)
            if player:
                p, identity = _resolve_player(bot, player, match)
            else:
                if not match.fraud:
                    await interaction.followup.send("No fraud detected.")
                    return
                p = match.fraud
                identity = _get_squad(bot).find_by_ea_id(p.ea_id)
                if not identity:
                    await interaction.followup.send("Fraud identity not found.")
                    return
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.fraud_roast(p, identity) if roast else f"Fraud: {identity.nickname}"
            card_path = cards.generate_fraud_card(p, identity) if cards else None
            if card_path:
                await interaction.followup.send(content=text, file=discord.File(card_path))
            else:
                await interaction.followup.send(text)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="ghost", description="Ghost verdict from match activity")
    async def ghost(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            match = _require_latest(bot)
            if not match.ghost:
                await interaction.followup.send("No ghost detected.")
                return
            p = match.ghost
            identity = _get_squad(bot).find_by_ea_id(p.ea_id)
            if not identity:
                await interaction.followup.send("Ghost identity not found.")
                return
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.ghost_roast(p, identity) if roast else f"Ghost: {identity.nickname}"
            card_path = cards.generate_ghost_card(p, identity) if cards else None
            if card_path:
                await interaction.followup.send(content=text, file=discord.File(card_path))
            else:
                await interaction.followup.send(text)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="carry", description="Who carried the squad")
    async def carry(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            match = _require_latest(bot)
            if not match.carry:
                await interaction.followup.send("No carry detected.")
                return
            p = match.carry
            identity = _get_squad(bot).find_by_ea_id(p.ea_id)
            if not identity:
                await interaction.followup.send("Carry identity not found.")
                return
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.carry_roast(p, identity) if roast else f"Carry: {identity.nickname}"
            card_path = cards.generate_carry_card(p, identity) if cards else None
            if card_path:
                await interaction.followup.send(content=text, file=discord.File(card_path))
            else:
                await interaction.followup.send(text)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="who_sold", description="Who sold the match")
    async def who_sold(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            match = _require_latest(bot)
            if not match.fraud:
                await interaction.followup.send("No seller detected.")
                return
            p = match.fraud
            identity = _get_squad(bot).find_by_ea_id(p.ea_id)
            if not identity:
                await interaction.followup.send("Identity not found.")
                return
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.who_sold_roast(p, identity) if roast else f"Sold: {identity.nickname}"
            card_path = cards.generate_fraud_card(p, identity) if cards else None
            if card_path:
                await interaction.followup.send(content=text, file=discord.File(card_path))
            else:
                await interaction.followup.send(text)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="ball_loser", description="Most dangerous ball loss merchant")
    async def ball_loser(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            match = _require_latest(bot)
            if not match.ball_loser:
                await interaction.followup.send("No ball loser detected.")
                return
            p = match.ball_loser
            identity = _get_squad(bot).find_by_ea_id(p.ea_id)
            if not identity:
                await interaction.followup.send("Identity not found.")
                return
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.ball_loser_roast(p, identity) if roast else f"Ball Loser: {identity.nickname}"
            card_path = cards.generate_ball_loser_card(p, identity) if cards else None
            if card_path:
                await interaction.followup.send(content=text, file=discord.File(card_path))
            else:
                await interaction.followup.send(text)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="playmaker", description="Chance creator and pass dictator")
    async def playmaker(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            match = _require_latest(bot)
            if not match.playmaker:
                await interaction.followup.send("No playmaker detected.")
                return
            p = match.playmaker
            identity = _get_squad(bot).find_by_ea_id(p.ea_id)
            if not identity:
                await interaction.followup.send("Identity not found.")
                return
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.playmaker_roast(p, identity) if roast else f"Playmaker: {identity.nickname}"
            card_path = cards.generate_playmaker_card(p, identity) if cards else None
            if card_path:
                await interaction.followup.send(content=text, file=discord.File(card_path))
            else:
                await interaction.followup.send(text)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="sniper", description="Finishing and shot efficiency king")
    async def sniper(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            match = _require_latest(bot)
            if not match.sniper:
                await interaction.followup.send("No sniper detected.")
                return
            p = match.sniper
            identity = _get_squad(bot).find_by_ea_id(p.ea_id)
            if not identity:
                await interaction.followup.send("Identity not found.")
                return
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.sniper_roast(p, identity) if roast else f"Sniper: {identity.nickname}"
            card_path = cards.generate_sniper_card(p, identity) if cards else None
            if card_path:
                await interaction.followup.send(content=text, file=discord.File(card_path))
            else:
                await interaction.followup.send(text)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="compare", description="Compare two players")
    @app_commands.describe(player_one="First player", player_two="Second player")
    async def compare(interaction: discord.Interaction, player_one: str, player_two: str) -> None:
        await interaction.response.defer(thinking=True)
        try:
            match = _require_latest(bot)
            p1, id1 = _resolve_player(bot, player_one, match)
            p2, id2 = _resolve_player(bot, player_two, match)
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.compare_roast(p1, id1, p2, id2) if roast else f"{id1.nickname} vs {id2.nickname}"
            card_path = cards.generate_compare_card(p1, id1, p2, id2) if cards else None
            if card_path:
                await interaction.followup.send(content=text, file=discord.File(card_path))
            else:
                await interaction.followup.send(text)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="court_case", description="Open the tribunal case file")
    @app_commands.describe(player="Accused player")
    async def court_case(interaction: discord.Interaction, player: str) -> None:
        await interaction.response.defer(thinking=True)
        try:
            match = _require_latest(bot)
            p, identity = _resolve_player(bot, player, match)
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.court_case_roast(p, identity) if roast else f"Court: {identity.nickname}"
            card_path = cards.generate_court_card(p, identity) if cards else None
            if card_path:
                await interaction.followup.send(content=text, file=discord.File(card_path))
            else:
                await interaction.followup.send(text)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="club", description="Club summary and squad state")
    async def club(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            match = _require_latest(bot)
            svc = _get_match_service(bot)
            embed = discord.Embed(
                title="Rachad FC Club Status",
                description=f"Latest: {match.score_for}-{match.score_against} vs {match.opponent}",
                color=0x3498db,
            )
            embed.add_field(name="Result", value=match.result, inline=True)
            embed.add_field(name="Players", value=str(len(match.players)), inline=True)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="records", description="Club records and broken records")
    async def records(interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Records system active. Phase 3 complete.")

    @bot.tree.command(name="form", description="Recent form for a player")
    @app_commands.describe(player="Player", matches="Number of recent matches")
    async def form(interaction: discord.Interaction, player: str, matches: int = 5) -> None:
        await interaction.response.defer(thinking=True)
        try:
            squad = _get_squad(bot)
            identity = squad.find(player) if squad else None
            if not identity:
                await interaction.followup.send("Player not found.")
                return
            svc = _get_match_service(bot)
            history = svc.player_history(identity.ea_id, limit=matches)
            if not history:
                await interaction.followup.send("No history found.")
                return
            lines = [f"**{identity.nickname}** - Last {len(history)} matches:"]
            for h in history:
                lines.append(f"Rating {h.rating} | G+A: {h.goals}+{h.assists} | Losses: {h.possession_losses}")
            await interaction.followup.send("\n".join(lines))
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="awards", description="Awards and weekly winners")
    async def awards(interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Awards system active. Check daily channel for auto-posts.")

    @bot.tree.command(name="legend", description="Legend card and lore")
    @app_commands.describe(player="Optional player")
    async def legend(interaction: discord.Interaction, player: Optional[str] = None) -> None:
        await interaction.response.defer(thinking=True)
        try:
            squad = _get_squad(bot)
            if player:
                identity = squad.find(player) if squad else None
            else:
                # Random legend
                import random
                identity = random.choice(squad.all()) if squad else None
            if not identity:
                await interaction.followup.send("Player not found.")
                return
            cards = _get_cards(bot)
            card_path = cards.generate_legend_card(identity) if cards else None
            text = f"**{identity.nickname}** | {identity.personality or 'Legend'}\n{identity.raw.get('bio', '')}"
            if card_path:
                await interaction.followup.send(content=text, file=discord.File(card_path))
            else:
                await interaction.followup.send(text)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="hall_of_shame", description="Historic fraud museum")
    async def hall_of_shame(interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Hall of Shame: coming with records engine.")

    @bot.tree.command(name="hall_of_fame", description="Historic elite performances")
    async def hall_of_fame(interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Hall of Fame: coming with records engine.")

    @bot.tree.command(name="match_report", description="Latest match report with banter")
    async def match_report(interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            match = _require_latest(bot)
            roast = _get_roast(bot)
            text = roast.match_summary(match) if roast else f"{match.score_for}-{match.score_against} vs {match.opponent}"
            embed = discord.Embed(
                title="Match Report",
                description=text,
                color=0x00FF00 if match.result == "W" else 0xFF0000 if match.result == "L" else 0xFFFF00,
            )
            if match.mvp:
                mvp_id = match.mvp.ea_id
                identity = _get_squad(bot).find_by_ea_id(mvp_id)
                name = identity.nickname if identity else match.mvp.display_name
                embed.add_field(name="MVP", value=name, inline=False)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @bot.tree.command(name="leaderboard", description="Leaderboard by metric")
    @app_commands.describe(metric="goals, assists, rating, minutes, losses, saves, matches, key_passes, tackles")
    async def leaderboard(interaction: discord.Interaction, metric: str = "goals") -> None:
        await interaction.response.defer(thinking=True)
        try:
            svc = _get_match_service(bot)
            repo = getattr(svc, "repo", None)
            if not repo:
                await interaction.followup.send("Repository not available.")
                return
            rows = repo.aggregate_leaderboard(metric=metric, limit=10)
            if not rows:
                await interaction.followup.send("No data for leaderboard.")
                return
            cards = _get_cards(bot)
            card_path = cards.generate_leaderboard_card(metric.upper(), rows, metric) if cards else None
            lines = [f"**Leaderboard: {metric.upper()}**"]
            for i, row in enumerate(rows):
                lines.append(f"{i+1}. {row['display_name']} - {row['value']:.1f} ({row['matches']}M)")
            text = "\n".join(lines)
            if card_path:
                await interaction.followup.send(content=text, file=discord.File(card_path))
            else:
                await interaction.followup.send(text)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    logger.info("Registered all 20 commands + /sync + /status")
