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

async def _safe_followup(interaction: discord.Interaction, content: str = None, *, embed: discord.Embed = None, file: discord.File = None) -> None:
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

    @bot.tree.command(name="ping", description="Check if bot is alive")
    async def ping(interaction: discord.Interaction) -> None:
        try:
            await interaction.response.send_message("🟢 Pong! Bot is online.", ephemeral=True)
        except Exception as e:
            logger.error("Ping failed: %s", e)

    @bot.tree.command(name="sync", description="Fetch latest club data from Pro Clubs Tracker")
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
                svc.refresh(force=True, source="discord:/sync"),
                timeout=45.0
            )
            latest = snapshot.latest_match

            if not latest:
                msg = "✅ Sync complete. No new match found this scrape."
                await _safe_followup(interaction, msg)
                return

            result_emoji = "WIN" if latest.result == "W" else "LOSS" if latest.result == "L" else "DRAW"
            result_icon = "🟢" if latest.result == "W" else "🔴" if latest.result == "L" else "🟡"
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
                # FIX: Also try find_by_display_name as fallback
                if not identity and squad:
                    identity = squad.find_by_display_name(latest.mvp.display_name)
                mvp_name = identity.nickname if identity else latest.mvp.display_name
                lines.append(f"MVP: {mvp_name} ({latest.mvp.rating}⭐)")

            await _safe_followup(interaction, "\n".join(lines))

        except asyncio.TimeoutError:
            logger.error("Sync timed out after 45s")
            await _safe_followup(interaction, "⏳ Sync timed out. The scraper is taking too long. Try again in a minute.")
        except Exception as e:
            logger.error("Sync failed: %s", e, exc_info=True)
            await _safe_followup(interaction, f"❌ Sync failed: {str(e)[:500]}")

    @bot.tree.command(name="debug", description="Debug bot state and database")
    async def debug(interaction: discord.Interaction) -> None:
        """Debug command to check database state and identify issues."""
        if not await _safe_defer(interaction):
            return

        try:
            svc = _get_match_service(bot)
            if not svc:
                await _safe_followup(interaction, "❌ Match service not available.")
                return

            repo = getattr(svc, "repo", None)
            if not repo:
                await _safe_followup(interaction, "❌ Repository not available.")
                return

            # Query database state
            from src.data.database import Database
            db = getattr(repo, "db", None)

            lines = ["**🔍 Debug Report**", ""]

            # Check latest match from DB
            latest = repo.latest_match()
            if latest:
                lines.append(f"**DB Latest Match:** {latest.match_id}")
                lines.append(f"- Opponent: {latest.opponent}")
                lines.append(f"- Score: {latest.score_for}-{latest.score_against}")
                lines.append(f"- Players: {len(latest.players)}")
                if latest.mvp:
                    lines.append(f"- MVP: {latest.mvp.display_name} (rating: {latest.mvp.rating})")
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
                # Show sample lookups
                if all_players:
                    sample = all_players[0]
                    lines.append(f"- Sample: {sample.nickname} (ea_id={sample.ea_id})")
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
                stats = repo.get_scrape_stats(hours=24)
                lines.append(f"**Scrapes (24h):** {stats['total_attempts']} total, {stats['successes']} success, {stats['failures']} fail")
            except Exception as e:
                lines.append(f"**Scrape stats:** Error - {e}")

            await _safe_followup(interaction, "\n".join(lines))

        except Exception as e:
            logger.error("Debug command error: %s", e, exc_info=True)
            await _safe_followup(interaction, f"❌ Debug failed: {str(e)[:500]}")

    @bot.tree.command(name="status", description="Show current data status")
    async def status(interaction: discord.Interaction) -> None:
        if not await _safe_defer(interaction):
            return
        svc = _get_match_service(bot)
        if not svc:
            await _safe_followup(interaction, "❌ Match service not wired.")
            return
        st = svc.status()
        embed = discord.Embed(title="Bot Status", color=0x3498db)
        embed.add_field(name="Latest Match", value=st.get("latest_match_id") or "None", inline=False)
        embed.add_field(name="Score", value=st.get("latest_score") or "N/A", inline=True)
        embed.add_field(name="Opponent", value=st.get("opponent") or "N/A", inline=True)
        embed.add_field(name="Players", value=str(st.get("latest_players", 0)), inline=True)
        await _safe_followup(interaction, embed=embed)

    @bot.tree.command(name="player", description="Player profile, stats, lore, and card")
    @app_commands.describe(player="Nickname, EA ID, or PSN")
    async def player(interaction: discord.Interaction, player: str) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            match = _require_latest(bot)
            p, identity = _resolve_player(bot, player, match)
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.general_roast(p, identity) if roast else f"**{identity.nickname}** | Rating: {p.rating}"
            card_path = cards.generate_mvp_card(p, identity) if cards else None
            if card_path:
                await _safe_followup(interaction, content=text, file=discord.File(card_path))
            else:
                await _safe_followup(interaction, text)
        except Exception as e:
            logger.error("Player command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="mvp", description="Best performer from eligible match players")
    async def mvp(interaction: discord.Interaction) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            match = _require_latest(bot)
            if not match.mvp:
                await _safe_followup(interaction, "No MVP found in latest match.")
                return
            p = match.mvp
            squad = _get_squad(bot)
            identity = squad.find_by_ea_id(p.ea_id) if squad else None
            # FIX: Fallback to display_name lookup
            if not identity and squad:
                identity = squad.find_by_display_name(p.display_name)
            if not identity:
                await _safe_followup(interaction, f"MVP identity not found. EA ID: {p.ea_id}, Display: {p.display_name}")
                return
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.mvp_roast(p, identity) if roast else f"MVP: {identity.nickname}"
            card_path = cards.generate_mvp_card(p, identity) if cards else None
            if card_path:
                await _safe_followup(interaction, content=text, file=discord.File(card_path))
            else:
                await _safe_followup(interaction, text)
        except Exception as e:
            logger.error("MVP command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="fraud", description="Fraud verdict for a player")
    @app_commands.describe(player="Nickname, EA ID, or PSN (optional, defaults to worst)")
    async def fraud(interaction: discord.Interaction, player: Optional[str] = None) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            match = _require_latest(bot)
            if player:
                p, identity = _resolve_player(bot, player, match)
            else:
                if not match.fraud:
                    await _safe_followup(interaction, "No fraud detected.")
                    return
                p = match.fraud
                identity = _get_squad(bot).find_by_ea_id(p.ea_id)
                if not identity:
                    identity = _get_squad(bot).find_by_display_name(p.display_name)
            if not identity:
                await _safe_followup(interaction, f"Fraud identity not found. EA ID: {p.ea_id}, Display: {p.display_name}")
                return
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.fraud_roast(p, identity) if roast else f"Fraud: {identity.nickname}"
            card_path = cards.generate_fraud_card(p, identity) if cards else None
            if card_path:
                await _safe_followup(interaction, content=text, file=discord.File(card_path))
            else:
                await _safe_followup(interaction, text)
        except Exception as e:
            logger.error("Fraud command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="ghost", description="Ghost verdict from match activity")
    async def ghost(interaction: discord.Interaction) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            match = _require_latest(bot)
            if not match.ghost:
                await _safe_followup(interaction, "No ghost detected.")
                return
            p = match.ghost
            identity = _get_squad(bot).find_by_ea_id(p.ea_id)
            if not identity:
                identity = _get_squad(bot).find_by_display_name(p.display_name)
            if not identity:
                await _safe_followup(interaction, f"Ghost identity not found. EA ID: {p.ea_id}, Display: {p.display_name}")
                return
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.ghost_roast(p, identity) if roast else f"Ghost: {identity.nickname}"
            card_path = cards.generate_ghost_card(p, identity) if cards else None
            if card_path:
                await _safe_followup(interaction, content=text, file=discord.File(card_path))
            else:
                await _safe_followup(interaction, text)
        except Exception as e:
            logger.error("Ghost command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="carry", description="Who carried the squad")
    async def carry(interaction: discord.Interaction) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            match = _require_latest(bot)
            if not match.carry:
                await _safe_followup(interaction, "No carry detected.")
                return
            p = match.carry
            identity = _get_squad(bot).find_by_ea_id(p.ea_id)
            if not identity:
                identity = _get_squad(bot).find_by_display_name(p.display_name)
            if not identity:
                await _safe_followup(interaction, f"Carry identity not found. EA ID: {p.ea_id}, Display: {p.display_name}")
                return
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.carry_roast(p, identity) if roast else f"Carry: {identity.nickname}"
            card_path = cards.generate_carry_card(p, identity) if cards else None
            if card_path:
                await _safe_followup(interaction, content=text, file=discord.File(card_path))
            else:
                await _safe_followup(interaction, text)
        except Exception as e:
            logger.error("Carry command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="who_sold", description="Who sold the match")
    async def who_sold(interaction: discord.Interaction) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            match = _require_latest(bot)
            if not match.fraud:
                await _safe_followup(interaction, "No seller detected.")
                return
            p = match.fraud
            identity = _get_squad(bot).find_by_ea_id(p.ea_id)
            if not identity:
                identity = _get_squad(bot).find_by_display_name(p.display_name)
            if not identity:
                await _safe_followup(interaction, f"Identity not found. EA ID: {p.ea_id}, Display: {p.display_name}")
                return
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.who_sold_roast(p, identity) if roast else f"Sold: {identity.nickname}"
            card_path = cards.generate_fraud_card(p, identity) if cards else None
            if card_path:
                await _safe_followup(interaction, content=text, file=discord.File(card_path))
            else:
                await _safe_followup(interaction, text)
        except Exception as e:
            logger.error("WhoSold command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="ball_loser", description="Most dangerous ball loss merchant")
    async def ball_loser(interaction: discord.Interaction) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            match = _require_latest(bot)
            if not match.ball_loser:
                await _safe_followup(interaction, "No ball loser detected.")
                return
            p = match.ball_loser
            identity = _get_squad(bot).find_by_ea_id(p.ea_id)
            if not identity:
                identity = _get_squad(bot).find_by_display_name(p.display_name)
            if not identity:
                await _safe_followup(interaction, f"Identity not found. EA ID: {p.ea_id}, Display: {p.display_name}")
                return
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.ball_loser_roast(p, identity) if roast else f"Ball Loser: {identity.nickname}"
            card_path = cards.generate_ball_loser_card(p, identity) if cards else None
            if card_path:
                await _safe_followup(interaction, content=text, file=discord.File(card_path))
            else:
                await _safe_followup(interaction, text)
        except Exception as e:
            logger.error("BallLoser command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="playmaker", description="Chance creator and pass dictator")
    async def playmaker(interaction: discord.Interaction) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            match = _require_latest(bot)
            if not match.playmaker:
                await _safe_followup(interaction, "No playmaker detected.")
                return
            p = match.playmaker
            identity = _get_squad(bot).find_by_ea_id(p.ea_id)
            if not identity:
                identity = _get_squad(bot).find_by_display_name(p.display_name)
            if not identity:
                await _safe_followup(interaction, f"Identity not found. EA ID: {p.ea_id}, Display: {p.display_name}")
                return
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.playmaker_roast(p, identity) if roast else f"Playmaker: {identity.nickname}"
            card_path = cards.generate_playmaker_card(p, identity) if cards else None
            if card_path:
                await _safe_followup(interaction, content=text, file=discord.File(card_path))
            else:
                await _safe_followup(interaction, text)
        except Exception as e:
            logger.error("Playmaker command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="sniper", description="Finishing and shot efficiency king")
    async def sniper(interaction: discord.Interaction) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            match = _require_latest(bot)
            if not match.sniper:
                await _safe_followup(interaction, "No sniper detected.")
                return
            p = match.sniper
            identity = _get_squad(bot).find_by_ea_id(p.ea_id)
            if not identity:
                identity = _get_squad(bot).find_by_display_name(p.display_name)
            if not identity:
                await _safe_followup(interaction, f"Identity not found. EA ID: {p.ea_id}, Display: {p.display_name}")
                return
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.sniper_roast(p, identity) if roast else f"Sniper: {identity.nickname}"
            card_path = cards.generate_sniper_card(p, identity) if cards else None
            if card_path:
                await _safe_followup(interaction, content=text, file=discord.File(card_path))
            else:
                await _safe_followup(interaction, text)
        except Exception as e:
            logger.error("Sniper command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="compare", description="Compare two players")
    @app_commands.describe(player_one="First player", player_two="Second player")
    async def compare(interaction: discord.Interaction, player_one: str, player_two: str) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            match = _require_latest(bot)
            p1, id1 = _resolve_player(bot, player_one, match)
            p2, id2 = _resolve_player(bot, player_two, match)
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.compare_roast(p1, id1, p2, id2) if roast else f"{id1.nickname} vs {id2.nickname}"
            card_path = cards.generate_compare_card(p1, id1, p2, id2) if cards else None
            if card_path:
                await _safe_followup(interaction, content=text, file=discord.File(card_path))
            else:
                await _safe_followup(interaction, text)
        except Exception as e:
            logger.error("Compare command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="court_case", description="Open the tribunal case file")
    @app_commands.describe(player="Accused player")
    async def court_case(interaction: discord.Interaction, player: str) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            match = _require_latest(bot)
            p, identity = _resolve_player(bot, player, match)
            roast = _get_roast(bot)
            cards = _get_cards(bot)
            text = roast.court_case_roast(p, identity) if roast else f"Court: {identity.nickname}"
            card_path = cards.generate_court_card(p, identity) if cards else None
            if card_path:
                await _safe_followup(interaction, content=text, file=discord.File(card_path))
            else:
                await _safe_followup(interaction, text)
        except Exception as e:
            logger.error("CourtCase command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="club", description="Club summary and squad state")
    async def club(interaction: discord.Interaction) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            match = _require_latest(bot)
            embed = discord.Embed(
                title="Rachad FC Club Status",
                description=f"Latest: {match.score_for}-{match.score_against} vs {match.opponent}",
                color=0x3498db,
            )
            embed.add_field(name="Result", value=match.result, inline=True)
            embed.add_field(name="Players", value=str(len(match.players)), inline=True)
            await _safe_followup(interaction, embed=embed)
        except Exception as e:
            logger.error("Club command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="records", description="Club records and broken records")
    async def records(interaction: discord.Interaction) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            recs = _get_records(bot)
            if not recs:
                await _safe_followup(interaction, "❌ Records service not available.")
                return

            computed = recs.compute_all_records()
            recs.save_records(computed)

            embed = discord.Embed(
                title="Rachad FC Records",
                description="All-time club records",
                color=0xFFD700,
            )
            for rec in computed[:6]:
                embed.add_field(
                    name=rec["title"],
                    value=rec["text"],
                    inline=False,
                )
            await _safe_followup(interaction, embed=embed)
        except Exception as e:
            logger.error("Records command error: %s", e)
            await _safe_followup(interaction, f"❌ Error loading records: {e}")

    @bot.tree.command(name="form", description="Recent form for a player")
    @app_commands.describe(player="Player", matches="Number of recent matches")
    async def form(interaction: discord.Interaction, player: str, matches: int = 5) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            squad = _get_squad(bot)
            identity = squad.find(player) if squad else None
            if not identity:
                await _safe_followup(interaction, "❌ Player not found.")
                return
            svc = _get_match_service(bot)
            history = svc.player_history(identity.ea_id, limit=matches)
            if not history:
                await _safe_followup(interaction, "No history found.")
                return

            ratings = [h.rating for h in history]
            spark_chars = "▁▂▃▄▅▆▇█"
            min_r, max_r = min(ratings), max(ratings)
            if max_r == min_r:
                spark = "█" * len(ratings)
            else:
                spark = "".join(
                    spark_chars[int((r - min_r) / (max_r - min_r) * (len(spark_chars) - 1))]
                    for r in ratings
                )

            lines = [
                f"**{identity.nickname}** - Last {len(history)} matches",
                "```",
                f"Rating trend: {spark}",
                "```",
            ]
            for h in history:
                result_icon = "🟢" if h.rating >= 7 else "🟡" if h.rating >= 5 else "🔴"
                lines.append(f"{result_icon} Rating {h.rating} | G+A: {h.goals}+{h.assists} | Losses: {h.possession_losses}")

            recs = _get_records(bot)
            if recs:
                memory = recs.generate_memory(identity.ea_id)
                lines.append("")
                lines.append(memory)

            await _safe_followup(interaction, "\n".join(lines))
        except Exception as e:
            logger.error("Form command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="awards", description="Awards and weekly winners")
    async def awards(interaction: discord.Interaction) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            recs = _get_records(bot)
            if recs:
                fame = recs.get_hall_of_fame(limit=5)
                if fame:
                    lines = ["**Hall of Fame Top 5**"]
                    for i, f in enumerate(fame):
                        lines.append(f"{i+1}. {f['nickname']} - Avg {f['avg_rating']} ({f['matches']}M)")
                    await _safe_followup(interaction, "\n".join(lines))
                    return
            await _safe_followup(interaction, "Awards system active. Check daily channel for auto-posts.")
        except Exception as e:
            logger.error("Awards command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="legend", description="Legend card and lore")
    @app_commands.describe(player="Optional player")
    async def legend(interaction: discord.Interaction, player: Optional[str] = None) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            squad = _get_squad(bot)
            if player:
                identity = squad.find(player) if squad else None
            else:
                import random
                identity = random.choice(squad.all()) if squad else None
            if not identity:
                await _safe_followup(interaction, "❌ Player not found.")
                return
            cards = _get_cards(bot)
            card_path = cards.generate_legend_card(identity) if cards else None
            text = f"**{identity.nickname}** | {identity.personality or 'Legend'}\n{identity.raw.get('bio', '')}"
            if card_path:
                await _safe_followup(interaction, content=text, file=discord.File(card_path))
            else:
                await _safe_followup(interaction, text)
        except Exception as e:
            logger.error("Legend command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="hall_of_shame", description="Historic fraud museum")
    async def hall_of_shame(interaction: discord.Interaction) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            recs = _get_records(bot)
            if not recs:
                await _safe_followup(interaction, "❌ Records service not available.")
                return
            shame = recs.get_hall_of_shame(limit=10)
            if not shame:
                await _safe_followup(interaction, "No shame data yet. Need at least 5 matches per player.")
                return

            embed = discord.Embed(
                title="Hall of Shame",
                description="The worst of the worst. Minimum 5 matches.",
                color=0x8B0000,
            )
            for i, s in enumerate(shame):
                embed.add_field(
                    name=f"{i+1}. {s['nickname']}",
                    value=f"Avg Rating: {s['avg_rating']} | Losses: {s['losses']} | Cards: {s['cards']} ({s['matches']}M)",
                    inline=False,
                )
            await _safe_followup(interaction, embed=embed)
        except Exception as e:
            logger.error("HallOfShame command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="hall_of_fame", description="Historic elite performances")
    async def hall_of_fame(interaction: discord.Interaction) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            recs = _get_records(bot)
            if not recs:
                await _safe_followup(interaction, "❌ Records service not available.")
                return
            fame = recs.get_hall_of_fame(limit=10)
            if not fame:
                await _safe_followup(interaction, "No fame data yet. Need at least 5 matches per player.")
                return

            embed = discord.Embed(
                title="Hall of Fame",
                description="The elite. Minimum 5 matches.",
                color=0xFFD700,
            )
            for i, f in enumerate(fame):
                embed.add_field(
                    name=f"{i+1}. {f['nickname']}",
                    value=f"Avg Rating: {f['avg_rating']} | G+A: {f['goals']}+{f['assists']} ({f['matches']}M)",
                    inline=False,
                )
            await _safe_followup(interaction, embed=embed)
        except Exception as e:
            logger.error("HallOfFame command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="rivalry", description="Head-to-head between two players")
    @app_commands.describe(player_one="First player", player_two="Second player")
    async def rivalry(interaction: discord.Interaction, player_one: str, player_two: str) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            squad = _get_squad(bot)
            id1 = squad.find(player_one) if squad else None
            id2 = squad.find(player_two) if squad else None
            if not id1 or not id2:
                await _safe_followup(interaction, "❌ One or both players not found.")
                return

            recs = _get_records(bot)
            if not recs:
                await _safe_followup(interaction, "❌ Records service not available.")
                return

            data = recs.get_rivalry(id1.ea_id, id2.ea_id)
            if not data:
                await _safe_followup(interaction, "These players have never played together.")
                return

            embed = discord.Embed(
                title=f"⚔️ {data['player_one']} vs {data['player_two']}",
                description=f"Played together in {data['matches_together']} matches",
                color=0xFF4500,
            )
            embed.add_field(name=data['player_one'], value=f"Wins: {data['p1_wins']}\nAvg Rating: {data['p1_avg_rating']}", inline=True)
            embed.add_field(name="Draws", value=str(data['draws']), inline=True)
            embed.add_field(name=data['player_two'], value=f"Wins: {data['p2_wins']}\nAvg Rating: {data['p2_avg_rating']}", inline=True)

            if data['recent_matches']:
                recent = "\n".join(
                    f"{m['date']} vs {m['opponent']} ({m['result']}): {m['p1_rating']} vs {m['p2_rating']}"
                    for m in data['recent_matches']
                )
                embed.add_field(name="Recent battles", value=f"```\n{recent}\n```", inline=False)

            await _safe_followup(interaction, embed=embed)
        except Exception as e:
            logger.error("Rivalry command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="memory", description="Squad historian report for a player")
    @app_commands.describe(player="Player name")
    async def memory(interaction: discord.Interaction, player: str) -> None:
        if not await _safe_defer(interaction):
            return
        try:
            squad = _get_squad(bot)
            identity = squad.find(player) if squad else None
            if not identity:
                await _safe_followup(interaction, "❌ Player not found.")
                return
            recs = _get_records(bot)
            if not recs:
                await _safe_followup(interaction, "❌ Records service not available.")
                return
            text = recs.generate_memory(identity.ea_id)
            await _safe_followup(interaction, text)
        except Exception as e:
            logger.error("Memory command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="match_report", description="Latest match report with banter")
    async def match_report(interaction: discord.Interaction) -> None:
        if not await _safe_defer(interaction):
            return
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
                squad = _get_squad(bot)
                identity = squad.find_by_ea_id(mvp_id) if squad else None
                if not identity and squad:
                    identity = squad.find_by_display_name(match.mvp.display_name)
                name = identity.nickname if identity else match.mvp.display_name
                embed.add_field(name="MVP", value=name, inline=False)
            await _safe_followup(interaction, embed=embed)
        except Exception as e:
            logger.error("MatchReport command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    @bot.tree.command(name="leaderboard", description="Leaderboard by metric")
    @app_commands.describe(metric="goals, assists, rating, minutes, losses, saves, matches, key_passes, tackles")
    async def leaderboard(interaction: discord.Interaction, metric: str = "goals") -> None:
        if not await _safe_defer(interaction):
            return
        try:
            svc = _get_match_service(bot)
            repo = getattr(svc, "repo", None)
            if not repo:
                await _safe_followup(interaction, "❌ Repository not available.")
                return
            rows = repo.aggregate_leaderboard(metric=metric, limit=10)
            if not rows:
                await _safe_followup(interaction, "No data for leaderboard.")
                return
            cards = _get_cards(bot)
            card_path = cards.generate_leaderboard_card(metric.upper(), rows, metric) if cards else None
            lines = [f"**Leaderboard: {metric.upper()}**"]
            for i, row in enumerate(rows):
                lines.append(f"{i+1}. {row['display_name']} - {row['value']:.1f} ({row['matches']}M)")
            text = "\n".join(lines)
            if card_path:
                await _safe_followup(interaction, content=text, file=discord.File(card_path))
            else:
                await _safe_followup(interaction, text)
        except Exception as e:
            logger.error("Leaderboard command error: %s", e)
            await _safe_followup(interaction, f"❌ Error: {e}")

    logger.info("Registered all commands")
