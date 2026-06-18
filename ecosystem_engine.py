"""
ecosystem_engine.py — PHASE 4: Full Football Ecosystem
========================================================
DO NOT modify existing files. Only ADD this file + imports in bot.py.

Systems:
  1. FraudScoreSystem      — 0-100 fraud classification
  2. CarryScoreSystem      — weighted carry score
  3. GhostScoreSystem      — invisibility detection
  4. HallOfShame           — permanent worst records
  5. HallOfFame            — permanent best records
  6. RivalrySystem         — head-to-head with roast
  7. WeeklyAwards          — auto weekly winners
  8. MilestoneTracker      — auto milestone alerts
  9. ExcusesEngine         — fake excuses from history
  10. MatchPosterEngine    — premium match poster data

All data comes from:
  • current_club.matches (historical match data)
  • current_club.players (season totals)
  • squad.json (nicknames, images, bios)
  • memory.db (SQLite persistence)
"""

import math
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from models import PlayerStats, ClubStats, MatchResult


# ─────────────────────────────────────────────────────────────
# 1. FRAUD SCORE SYSTEM
# ─────────────────────────────────────────────────────────────

class FraudScoreSystem:
    """
    Real fraud scoring: 0-100
    0-30   = Safe
    31-60  = Suspicious
    61-80  = Fraud
    81-100 = Criminal
    """

    @classmethod
    def compute(cls, player: PlayerStats, match_stats: Optional[dict] = None) -> dict:
        """Compute fraud score from season stats + optional single-match stats."""
        score = 0
        breakdown = []
        g = max(player.games, 1)

        # Low rating (+30 max)
        rating = player.rating_pg
        if rating < 5.0:
            score += 30
            breakdown.append(("Rating < 5.0", 30))
        elif rating < 5.5:
            score += 25
            breakdown.append(("Rating < 5.5", 25))
        elif rating < 6.0:
            score += 15
            breakdown.append(("Rating < 6.0", 15))
        elif rating < 6.5:
            score += 5
            breakdown.append(("Rating < 6.5", 5))

        # High possession lost (+25 max)
        pl_pg = player.possession_losses / g
        if pl_pg > 20:
            score += 25
            breakdown.append(("Possession Lost > 20/match", 25))
        elif pl_pg > 15:
            score += 20
            breakdown.append(("Possession Lost > 15/match", 20))
        elif pl_pg > 10:
            score += 10
            breakdown.append(("Possession Lost > 10/match", 10))

        # Low pass accuracy (+20 max)
        pa = player.pass_accuracy
        if pa < 50:
            score += 20
            breakdown.append(("Pass Accuracy < 50%", 20))
        elif pa < 60:
            score += 15
            breakdown.append(("Pass Accuracy < 60%", 15))
        elif pa < 70:
            score += 10
            breakdown.append(("Pass Accuracy < 70%", 10))

        # Zero contribution (+15)
        if player.goals == 0 and player.assists == 0 and player.games > 3:
            score += 15
            breakdown.append(("Zero Goals + Assists (3+ games)", 15))

        # Missed chances (+10) — shots > 3, goals = 0 in a match context
        if match_stats:
            shots = match_stats.get("shots", 0)
            goals = match_stats.get("goals", 0)
            if shots > 3 and goals == 0:
                score += 10
                breakdown.append(("Missed Chances (3+ shots, 0 goals)", 10))
        else:
            if player.shots > 10 and player.goals == 0:
                score += 10
                breakdown.append(("Missed Chances (10+ shots, 0 goals)", 10))

        # Ghost performance (+10) — low involvement
        ghost_score = GhostScoreSystem.compute(player, match_stats)
        if ghost_score["is_ghost"]:
            score += 10
            breakdown.append(("Ghost Performance", 10))

        # Win rate penalty (+10 max)
        if player.win_rate < 30 and player.games > 5:
            score += 10
            breakdown.append(("Win Rate < 30%", 10))
        elif player.win_rate < 40 and player.games > 5:
            score += 5
            breakdown.append(("Win Rate < 40%", 5))

        # Cap at 100
        score = min(score, 100)

        classification = cls.classify(score)
        return {
            "score": score,
            "classification": classification,
            "breakdown": breakdown,
            "label": classification,
        }

    @classmethod
    def classify(cls, score: int) -> str:
        if score <= 30:
            return "Safe"
        elif score <= 60:
            return "Suspicious"
        elif score <= 80:
            return "Fraud"
        else:
            return "Criminal"

    @classmethod
    def compute_match_fraud(cls, match_stats: dict) -> dict:
        """Compute fraud for a single match's player_stats dict."""
        score = 0
        breakdown = []
        rating = match_stats.get("rating", 0)
        if rating > 10:
            rating = round(rating / 10.0, 1)

        if rating < 5.0:
            score += 30
            breakdown.append(("Rating < 5.0", 30))
        elif rating < 5.5:
            score += 25
            breakdown.append(("Rating < 5.5", 25))
        elif rating < 6.0:
            score += 15
            breakdown.append(("Rating < 6.0", 15))

        passes_att = match_stats.get("passes_attempted", 0)
        passes_comp = match_stats.get("passes_completed", 0)
        pl = passes_att - passes_comp
        if pl > 20:
            score += 25
            breakdown.append(("Possession Lost > 20", 25))
        elif pl > 15:
            score += 20
            breakdown.append(("Possession Lost > 15", 20))
        elif pl > 10:
            score += 10
            breakdown.append(("Possession Lost > 10", 10))

        pa = round(passes_comp / max(passes_att, 1) * 100, 1)
        if pa < 50:
            score += 20
            breakdown.append(("Pass Accuracy < 50%", 20))
        elif pa < 60:
            score += 15
            breakdown.append(("Pass Accuracy < 60%", 15))
        elif pa < 70:
            score += 10
            breakdown.append(("Pass Accuracy < 70%", 10))

        goals = match_stats.get("goals", 0)
        assists = match_stats.get("assists", 0)
        if goals == 0 and assists == 0:
            score += 15
            breakdown.append(("Zero Contribution", 15))

        shots = match_stats.get("shots", 0)
        if shots > 3 and goals == 0:
            score += 10
            breakdown.append(("Missed Chances", 10))

        touches = match_stats.get("touches", 0) or match_stats.get("passes_attempted", 0)
        if touches < 15:
            score += 10
            breakdown.append(("Ghost Performance", 10))

        score = min(score, 100)
        return {
            "score": score,
            "classification": cls.classify(score),
            "breakdown": breakdown,
        }


# ─────────────────────────────────────────────────────────────
# 2. CARRY SCORE SYSTEM
# ─────────────────────────────────────────────────────────────

class CarryScoreSystem:
    """
    Carry score using:
    goals * 5 + assists * 4 + tackles * 2 + interceptions * 2
    + pass% * 0.5 + MOTM * 10 + rating * 5
    """

    @classmethod
    def compute(cls, player: PlayerStats) -> dict:
        g = max(player.games, 1)
        score = (
            player.goals * 5 +
            player.assists * 4 +
            player.tackles * 2 +
            player.interceptions * 2 +
            player.pass_accuracy * 0.5 +
            player.motm * 10 +
            player.rating_pg * 5
        )
        # Normalize per game for fairness
        score_pg = round(score / g, 1)

        classification = "Average"
        if score_pg >= 25:
            classification = "Legendary Carry"
        elif score_pg >= 18:
            classification = "Hard Carry"
        elif score_pg >= 12:
            classification = "Carry"
        elif score_pg >= 8:
            classification = "Helpful"
        else:
            classification = "Passenger"

        return {
            "total_score": round(score, 1),
            "score_per_game": score_pg,
            "classification": classification,
            "breakdown": {
                "goals": player.goals * 5,
                "assists": player.assists * 4,
                "tackles": player.tackles * 2,
                "interceptions": player.interceptions * 2,
                "pass_accuracy": round(player.pass_accuracy * 0.5, 1),
                "motm": player.motm * 10,
                "rating": round(player.rating_pg * 5, 1),
            }
        }

    @classmethod
    def compute_match_carry(cls, match_stats: dict) -> dict:
        """Compute carry for a single match."""
        goals = match_stats.get("goals", 0)
        assists = match_stats.get("assists", 0)
        tackles = match_stats.get("tackles", 0)
        interceptions = match_stats.get("interceptions", 0)
        passes_att = match_stats.get("passes_attempted", 0)
        passes_comp = match_stats.get("passes_completed", 0)
        pa = round(passes_comp / max(passes_att, 1) * 100, 1)
        motm = 1 if match_stats.get("motm", False) else 0
        rating = match_stats.get("rating", 0)
        if rating > 10:
            rating = round(rating / 10.0, 1)

        score = (
            goals * 5 + assists * 4 + tackles * 2 + interceptions * 2 +
            pa * 0.5 + motm * 10 + rating * 5
        )

        classification = "Average"
        if score >= 40:
            classification = "Legendary Carry"
        elif score >= 30:
            classification = "Hard Carry"
        elif score >= 20:
            classification = "Carry"
        elif score >= 12:
            classification = "Helpful"
        else:
            classification = "Passenger"

        return {
            "score": round(score, 1),
            "classification": classification,
        }


# ─────────────────────────────────────────────────────────────
# 3. GHOST SCORE SYSTEM
# ─────────────────────────────────────────────────────────────

class GhostScoreSystem:
    """
    Detect invisible players using:
    touches, passes, duels, shots, contributions
    Low involvement = ghost.
    """

    @classmethod
    def compute(cls, player: PlayerStats, match_stats: Optional[dict] = None) -> dict:
        if match_stats:
            return cls._compute_match_ghost(match_stats)

        g = max(player.games, 1)
        touches = getattr(player, "touches", 0) or (player.passes_made + player.possession_losses)
        passes = player.passes_made
        duels = player.tackles + player.interceptions
        shots = player.shots
        contrib = player.goals + player.assists

        # Per-game thresholds
        touches_pg = touches / g
        passes_pg = passes / g
        duels_pg = duels / g
        shots_pg = shots / g
        contrib_pg = contrib / g

        ghost_points = 0
        reasons = []

        if touches_pg < 20:
            ghost_points += 25
            reasons.append(f"Touches {round(touches_pg,1)}/game (< 20)")
        elif touches_pg < 30:
            ghost_points += 15
            reasons.append(f"Touches {round(touches_pg,1)}/game (< 30)")

        if passes_pg < 10:
            ghost_points += 20
            reasons.append(f"Passes {round(passes_pg,1)}/game (< 10)")
        elif passes_pg < 15:
            ghost_points += 10
            reasons.append(f"Passes {round(passes_pg,1)}/game (< 15)")

        if duels_pg < 2:
            ghost_points += 15
            reasons.append(f"Duels {round(duels_pg,1)}/game (< 2)")

        if shots_pg < 0.5 and contrib_pg == 0:
            ghost_points += 15
            reasons.append("No shots + no contributions")

        if contrib_pg == 0 and player.games > 3:
            ghost_points += 15
            reasons.append("Zero contributions (3+ games)")

        if player.minutes_played / g < 30:
            ghost_points += 10
            reasons.append("Avg minutes < 30")

        is_ghost = ghost_points >= 40
        severity = "None"
        if ghost_points >= 70:
            severity = "Phantom"
        elif ghost_points >= 50:
            severity = "Ghost"
        elif ghost_points >= 40:
            severity = "Shadow"
        elif ghost_points >= 20:
            severity = "Fading"

        return {
            "ghost_points": ghost_points,
            "is_ghost": is_ghost,
            "severity": severity,
            "reasons": reasons,
        }

    @classmethod
    def _compute_match_ghost(cls, match_stats: dict) -> dict:
        touches = match_stats.get("touches", 0) or match_stats.get("passes_attempted", 0)
        passes = match_stats.get("passes_attempted", 0)
        duels = match_stats.get("tackles", 0) + match_stats.get("interceptions", 0)
        shots = match_stats.get("shots", 0)
        contrib = match_stats.get("goals", 0) + match_stats.get("assists", 0)

        ghost_points = 0
        reasons = []

        if touches < 15:
            ghost_points += 25
            reasons.append(f"Touches {touches} (< 15)")
        elif touches < 25:
            ghost_points += 15
            reasons.append(f"Touches {touches} (< 25)")

        if passes < 8:
            ghost_points += 20
            reasons.append(f"Passes {passes} (< 8)")
        elif passes < 12:
            ghost_points += 10
            reasons.append(f"Passes {passes} (< 12)")

        if duels < 1:
            ghost_points += 15
            reasons.append(f"Duels {duels} (< 1)")

        if shots == 0 and contrib == 0:
            ghost_points += 15
            reasons.append("No shots + no contributions")

        is_ghost = ghost_points >= 40
        severity = "None"
        if ghost_points >= 70:
            severity = "Phantom"
        elif ghost_points >= 50:
            severity = "Ghost"
        elif ghost_points >= 40:
            severity = "Shadow"
        elif ghost_points >= 20:
            severity = "Fading"

        return {
            "ghost_points": ghost_points,
            "is_ghost": is_ghost,
            "severity": severity,
            "reasons": reasons,
        }


# ─────────────────────────────────────────────────────────────
# 4. HALL OF SHAME — Permanent Worst Records
# ─────────────────────────────────────────────────────────────

@dataclass
class ShameRecord:
    category: str
    player_name: str
    value: float
    match_id: Optional[str] = None
    opponent: Optional[str] = None
    date: Optional[str] = None
    description: str = ""


class HallOfShame:
    """Track the worst performances ever recorded from match history."""

    CATEGORIES = [
        "worst_rating_ever",
        "most_possession_lost_ever",
        "biggest_fraud_performance",
        "worst_pass_accuracy_ever",
        "most_missed_chances_ever",
        "biggest_ghost_performance",
        "worst_carry_score_ever",
    ]

    @classmethod
    def scan_matches(cls, matches: List[MatchResult], players: List[PlayerStats]) -> List[ShameRecord]:
        """Scan all match history and return shame records."""
        records = []
        if not matches:
            return records

        # Build player name -> PSN mapping
        name_to_psn = {}
        for p in players:
            raw = getattr(p, "_raw_psn", p.name)
            name_to_psn[p.name] = raw
            name_to_psn[raw.lower()] = raw

        worst_rating = None
        most_pl = None
        biggest_fraud = None
        worst_pa = None
        most_missed = None
        biggest_ghost = None
        worst_carry = None

        for match in matches:
            if not match.player_stats:
                continue

            for psn_raw, stats in match.player_stats.items():
                # Find player name
                player_name = psn_raw
                for p in players:
                    if getattr(p, "_raw_psn", "").lower() == psn_raw.lower() or p.name.lower() == psn_raw.lower():
                        player_name = p.name
                        break

                rating = stats.get("rating", 0)
                if rating > 10:
                    rating = round(rating / 10.0, 1)

                passes_att = stats.get("passes_attempted", 0)
                passes_comp = stats.get("passes_completed", 0)
                pl = passes_att - passes_comp
                pa = round(passes_comp / max(passes_att, 1) * 100, 1)
                shots = stats.get("shots", 0)
                goals = stats.get("goals", 0)

                # Worst rating
                if worst_rating is None or rating < worst_rating.value:
                    worst_rating = ShameRecord(
                        category="worst_rating_ever",
                        player_name=player_name,
                        value=rating,
                        match_id=match.match_id,
                        opponent=match.opponent,
                        date=match.date.strftime("%d/%m/%Y") if hasattr(match.date, "strftime") else str(match.date),
                        description=f"Rating {rating} vs {match.opponent}"
                    )

                # Most possession lost
                if most_pl is None or pl > most_pl.value:
                    most_pl = ShameRecord(
                        category="most_possession_lost_ever",
                        player_name=player_name,
                        value=pl,
                        match_id=match.match_id,
                        opponent=match.opponent,
                        date=match.date.strftime("%d/%m/%Y") if hasattr(match.date, "strftime") else str(match.date),
                        description=f"{pl} possession losses vs {match.opponent}"
                    )

                # Worst pass accuracy (min 5 passes)
                if passes_att >= 5:
                    if worst_pa is None or pa < worst_pa.value:
                        worst_pa = ShameRecord(
                            category="worst_pass_accuracy_ever",
                            player_name=player_name,
                            value=pa,
                            match_id=match.match_id,
                            opponent=match.opponent,
                            date=match.date.strftime("%d/%m/%Y") if hasattr(match.date, "strftime") else str(match.date),
                            description=f"{pa}% pass accuracy vs {match.opponent}"
                        )

                # Most missed chances (3+ shots, 0 goals)
                if shots > 3 and goals == 0:
                    if most_missed is None or shots > most_missed.value:
                        most_missed = ShameRecord(
                            category="most_missed_chances_ever",
                            player_name=player_name,
                            value=shots,
                            match_id=match.match_id,
                            opponent=match.opponent,
                            date=match.date.strftime("%d/%m/%Y") if hasattr(match.date, "strftime") else str(match.date),
                            description=f"{shots} shots, 0 goals vs {match.opponent}"
                        )

                # Biggest fraud
                fraud = FraudScoreSystem.compute_match_fraud(stats)
                if biggest_fraud is None or fraud["score"] > biggest_fraud.value:
                    biggest_fraud = ShameRecord(
                        category="biggest_fraud_performance",
                        player_name=player_name,
                        value=fraud["score"],
                        match_id=match.match_id,
                        opponent=match.opponent,
                        date=match.date.strftime("%d/%m/%Y") if hasattr(match.date, "strftime") else str(match.date),
                        description=f"Fraud Score {fraud['score']} ({fraud['classification']}) vs {match.opponent}"
                    )

                # Biggest ghost
                ghost = GhostScoreSystem._compute_match_ghost(stats)
                if biggest_ghost is None or ghost["ghost_points"] > biggest_ghost.value:
                    biggest_ghost = ShameRecord(
                        category="biggest_ghost_performance",
                        player_name=player_name,
                        value=ghost["ghost_points"],
                        match_id=match.match_id,
                        opponent=match.opponent,
                        date=match.date.strftime("%d/%m/%Y") if hasattr(match.date, "strftime") else str(match.date),
                        description=f"Ghost Score {ghost['ghost_points']} ({ghost['severity']}) vs {match.opponent}"
                    )

                # Worst carry
                carry = CarryScoreSystem.compute_match_carry(stats)
                if worst_carry is None or carry["score"] < worst_carry.value:
                    worst_carry = ShameRecord(
                        category="worst_carry_score_ever",
                        player_name=player_name,
                        value=carry["score"],
                        match_id=match.match_id,
                        opponent=match.opponent,
                        date=match.date.strftime("%d/%m/%Y") if hasattr(match.date, "strftime") else str(match.date),
                        description=f"Carry Score {carry['score']} ({carry['classification']}) vs {match.opponent}"
                    )

        for rec in [worst_rating, most_pl, biggest_fraud, worst_pa, most_missed, biggest_ghost, worst_carry]:
            if rec:
                records.append(rec)

        return records

    @classmethod
    def get_records_text(cls, records: List[ShameRecord]) -> str:
        """Format shame records as Darija text."""
        if not records:
            return "🏛️ **Hall of Shame**\n\nما كاين حتى شي record لحد الآن."

        text = "🏛️ **HALL OF SHAME** — الأرقام ما كتكدبش\n\n"
        emojis = {
            "worst_rating_ever": "📉",
            "most_possession_lost_ever": "💀",
            "biggest_fraud_performance": "🎭",
            "worst_pass_accuracy_ever": "🎯",
            "most_missed_chances_ever": "❌",
            "biggest_ghost_performance": "👻",
            "worst_carry_score_ever": "🎒",
        }
        labels = {
            "worst_rating_ever": "Worst Rating Ever",
            "most_possession_lost_ever": "Most Possession Lost Ever",
            "biggest_fraud_performance": "Biggest Fraud Performance",
            "worst_pass_accuracy_ever": "Worst Pass Accuracy Ever",
            "most_missed_chances_ever": "Most Missed Chances Ever",
            "biggest_ghost_performance": "Biggest Ghost Performance",
            "worst_carry_score_ever": "Worst Carry Score Ever",
        }

        for rec in records:
            emoji = emojis.get(rec.category, "🔥")
            label = labels.get(rec.category, rec.category)
            text += f"{emoji} **{label}**\n"
            text += f"   {rec.player_name} — {rec.description}\n\n"

        return text


# ─────────────────────────────────────────────────────────────
# 5. HALL OF FAME — Permanent Best Records
# ─────────────────────────────────────────────────────────────

@dataclass
class FameRecord:
    category: str
    player_name: str
    value: float
    match_id: Optional[str] = None
    opponent: Optional[str] = None
    date: Optional[str] = None
    description: str = ""


class HallOfFame:
    """Track the best performances ever recorded from match history."""

    CATEGORIES = [
        "highest_rating_ever",
        "most_goals_in_match",
        "most_assists_in_match",
        "best_carry_performance",
        "best_defender_performance",
        "most_mvps_season",
    ]

    @classmethod
    def scan_matches(cls, matches: List[MatchResult], players: List[PlayerStats]) -> List[FameRecord]:
        """Scan all match history and return fame records."""
        records = []
        if not matches:
            return records

        highest_rating = None
        most_goals = None
        most_assists = None
        best_carry = None
        best_defender = None

        for match in matches:
            if not match.player_stats:
                continue

            for psn_raw, stats in match.player_stats.items():
                player_name = psn_raw
                for p in players:
                    if getattr(p, "_raw_psn", "").lower() == psn_raw.lower() or p.name.lower() == psn_raw.lower():
                        player_name = p.name
                        break

                rating = stats.get("rating", 0)
                if rating > 10:
                    rating = round(rating / 10.0, 1)
                goals = stats.get("goals", 0)
                assists = stats.get("assists", 0)
                tackles = stats.get("tackles", 0)
                interceptions = stats.get("interceptions", 0)

                # Highest rating
                if highest_rating is None or rating > highest_rating.value:
                    highest_rating = FameRecord(
                        category="highest_rating_ever",
                        player_name=player_name,
                        value=rating,
                        match_id=match.match_id,
                        opponent=match.opponent,
                        date=match.date.strftime("%d/%m/%Y") if hasattr(match.date, "strftime") else str(match.date),
                        description=f"Rating {rating} vs {match.opponent}"
                    )

                # Most goals in one match
                if most_goals is None or goals > most_goals.value:
                    most_goals = FameRecord(
                        category="most_goals_in_match",
                        player_name=player_name,
                        value=goals,
                        match_id=match.match_id,
                        opponent=match.opponent,
                        date=match.date.strftime("%d/%m/%Y") if hasattr(match.date, "strftime") else str(match.date),
                        description=f"{goals} goals vs {match.opponent}"
                    )

                # Most assists in one match
                if most_assists is None or assists > most_assists.value:
                    most_assists = FameRecord(
                        category="most_assists_in_match",
                        player_name=player_name,
                        value=assists,
                        match_id=match.match_id,
                        opponent=match.opponent,
                        date=match.date.strftime("%d/%m/%Y") if hasattr(match.date, "strftime") else str(match.date),
                        description=f"{assists} assists vs {match.opponent}"
                    )

                # Best carry performance
                carry = CarryScoreSystem.compute_match_carry(stats)
                if best_carry is None or carry["score"] > best_carry.value:
                    best_carry = FameRecord(
                        category="best_carry_performance",
                        player_name=player_name,
                        value=carry["score"],
                        match_id=match.match_id,
                        opponent=match.opponent,
                        date=match.date.strftime("%d/%m/%Y") if hasattr(match.date, "strftime") else str(match.date),
                        description=f"Carry Score {carry['score']} ({carry['classification']}) vs {match.opponent}"
                    )

                # Best defender performance (tackles + interceptions)
                def_score = tackles * 2 + interceptions * 1.5
                if best_defender is None or def_score > best_defender.value:
                    best_defender = FameRecord(
                        category="best_defender_performance",
                        player_name=player_name,
                        value=round(def_score, 1),
                        match_id=match.match_id,
                        opponent=match.opponent,
                        date=match.date.strftime("%d/%m/%Y") if hasattr(match.date, "strftime") else str(match.date),
                        description=f"{tackles} tackles + {interceptions} interceptions vs {match.opponent}"
                    )

        # Most MVPs from season totals
        if players:
            mvp_player = max(players, key=lambda p: p.motm)
            if mvp_player.motm > 0:
                most_mvps = FameRecord(
                    category="most_mvps_season",
                    player_name=mvp_player.name,
                    value=mvp_player.motm,
                    description=f"{mvp_player.motm} MVPs this season"
                )
                records.append(most_mvps)

        for rec in [highest_rating, most_goals, most_assists, best_carry, best_defender]:
            if rec:
                records.append(rec)

        return records

    @classmethod
    def get_records_text(cls, records: List[FameRecord]) -> str:
        if not records:
            return "🏆 **Hall of Fame**\n\nما كاين حتى شي record لحد الآن."

        text = "🏆 **HALL OF FAME** — التاريخ ما كينساش\n\n"
        emojis = {
            "highest_rating_ever": "⭐",
            "most_goals_in_match": "⚽",
            "most_assists_in_match": "🅰️",
            "best_carry_performance": "💪",
            "best_defender_performance": "🛡️",
            "most_mvps_season": "🏆",
        }
        labels = {
            "highest_rating_ever": "Highest Rating Ever",
            "most_goals_in_match": "Most Goals in One Match",
            "most_assists_in_match": "Most Assists in One Match",
            "best_carry_performance": "Best Carry Performance",
            "best_defender_performance": "Best Defender Performance",
            "most_mvps_season": "Most MVPs This Season",
        }

        for rec in records:
            emoji = emojis.get(rec.category, "👑")
            label = labels.get(rec.category, rec.category)
            text += f"{emoji} **{label}**\n"
            text += f"   {rec.player_name} — {rec.description}\n\n"

        return text


# ─────────────────────────────────────────────────────────────
# 6. RIVALRY SYSTEM
# ─────────────────────────────────────────────────────────────

class RivalrySystem:
    """Head-to-head comparison with roast winner."""

    @classmethod
    def compare(cls, p1: PlayerStats, p2: PlayerStats, matches: List[MatchResult]) -> dict:
        """Full rivalry comparison."""
        # Direct matchups: find matches where both played
        both_played = 0
        p1_wins = 0
        p2_wins = 0
        p1_goals_h2h = 0
        p2_goals_h2h = 0

        p1_psn = getattr(p1, "_raw_psn", p1.name).lower()
        p2_psn = getattr(p2, "_raw_psn", p2.name).lower()

        for match in matches:
            if not match.player_stats:
                continue
            psns = [k.lower() for k in match.player_stats.keys()]
            if p1_psn in psns and p2_psn in psns:
                both_played += 1
                s1 = match.player_stats.get(p1_psn, match.player_stats.get(p1.name, {}))
                s2 = match.player_stats.get(p2_psn, match.player_stats.get(p2.name, {}))
                g1 = s1.get("goals", 0)
                g2 = s2.get("goals", 0)
                p1_goals_h2h += g1
                p2_goals_h2h += g2
                if g1 > g2:
                    p1_wins += 1
                elif g2 > g1:
                    p2_wins += 1

        # Season totals comparison
        stats = {
            "p1_name": p1.name,
            "p2_name": p2.name,
            "goals": {"p1": p1.goals, "p2": p2.goals, "winner": p1.name if p1.goals > p2.goals else p2.name if p2.goals > p1.goals else "Tie"},
            "assists": {"p1": p1.assists, "p2": p2.assists, "winner": p1.name if p1.assists > p2.assists else p2.name if p2.assists > p1.assists else "Tie"},
            "rating": {"p1": round(p1.rating_pg, 1), "p2": round(p2.rating_pg, 1), "winner": p1.name if p1.rating_pg > p2.rating_pg else p2.name if p2.rating_pg > p1.rating_pg else "Tie"},
            "win_rate": {"p1": round(p1.win_rate, 1), "p2": round(p2.win_rate, 1), "winner": p1.name if p1.win_rate > p2.win_rate else p2.name if p2.win_rate > p1.win_rate else "Tie"},
            "possession_lost": {"p1": p1.possession_losses, "p2": p2.possession_losses, "winner": p1.name if p1.possession_losses < p2.possession_losses else p2.name if p2.possession_losses < p1.possession_losses else "Tie"},
            "motm": {"p1": p1.motm, "p2": p2.motm, "winner": p1.name if p1.motm > p2.motm else p2.name if p2.motm > p1.motm else "Tie"},
            "impact": {"p1": p1.impact_score, "p2": p2.impact_score, "winner": p1.name if p1.impact_score > p2.impact_score else p2.name if p2.impact_score > p1.impact_score else "Tie"},
            "h2h_matches": both_played,
            "h2h_p1_wins": p1_wins,
            "h2h_p2_wins": p2_wins,
            "h2h_p1_goals": p1_goals_h2h,
            "h2h_p2_goals": p2_goals_h2h,
        }

        # Overall winner = who won more categories
        p1_wins_cat = 0
        p2_wins_cat = 0
        for cat in ["goals", "assists", "rating", "win_rate", "possession_lost", "motm", "impact"]:
            w = stats[cat]["winner"]
            if w == p1.name:
                p1_wins_cat += 1
            elif w == p2.name:
                p2_wins_cat += 1

        if p1_wins_cat > p2_wins_cat:
            overall_winner = p1.name
            overall_loser = p2.name
        elif p2_wins_cat > p1_wins_cat:
            overall_winner = p2.name
            overall_loser = p1.name
        else:
            overall_winner = "Tie"
            overall_loser = "Tie"

        stats["overall_winner"] = overall_winner
        stats["overall_loser"] = overall_loser
        stats["p1_categories_won"] = p1_wins_cat
        stats["p2_categories_won"] = p2_wins_cat

        return stats

    @classmethod
    def format_text(cls, stats: dict) -> str:
        p1 = stats["p1_name"]
        p2 = stats["p2_name"]
        winner = stats["overall_winner"]
        loser = stats["overall_loser"]

        text = f"⚔️ **RIVALRY: {p1} vs {p2}**\n\n"
        text += f"📊 **Season Totals**\n"
        text += f"   Goals: {p1} {stats['goals']['p1']} — {stats['goals']['p2']} {p2} (🏆 {stats['goals']['winner']})\n"
        text += f"   Assists: {p1} {stats['assists']['p1']} — {stats['assists']['p2']} {p2} (🏆 {stats['assists']['winner']})\n"
        text += f"   Rating: {p1} {stats['rating']['p1']} — {stats['rating']['p2']} {p2} (🏆 {stats['rating']['winner']})\n"
        text += f"   Win %: {p1} {stats['win_rate']['p1']}% — {stats['win_rate']['p2']}% {p2} (🏆 {stats['win_rate']['winner']})\n"
        text += f"   Possession Lost: {p1} {stats['possession_lost']['p1']} — {stats['possession_lost']['p2']} {p2} (🏆 {stats['possession_lost']['winner']})\n"
        text += f"   MOTM: {p1} {stats['motm']['p1']} — {stats['motm']['p2']} {p2} (🏆 {stats['motm']['winner']})\n"
        text += f"   Impact: {p1} {stats['impact']['p1']} — {stats['impact']['p2']} {p2} (🏆 {stats['impact']['winner']})\n\n"

        if stats["h2h_matches"] > 0:
            text += f"🥊 **Head-to-Head** ({stats['h2h_matches']} matches together)\n"
            text += f"   {p1}: {stats['h2h_p1_goals']} goals, {stats['h2h_p1_wins']} match wins\n"
            text += f"   {p2}: {stats['h2h_p2_goals']} goals, {stats['h2h_p2_wins']} match wins\n\n"
        else:
            text += "🥊 **Head-to-Head**: ما لعبوش مع بعض فنفس الماتشات فالhistory.\n\n"

        if winner != "Tie":
            text += f"🏆 **WINNER: {winner}** ({stats['p1_categories_won'] if winner == p1 else stats['p2_categories_won']}/7 categories)\n"
            text += f"💀 **LOSER: {loser}** — {loser} كيحتاج lawyer باش يدافع على راسو.\n"
        else:
            text += "🤝 **RESULT: TIE** — بحال بحال، rivalry ماشي واضحة.\n"

        return text


# ─────────────────────────────────────────────────────────────
# 7. WEEKLY AWARDS
# ─────────────────────────────────────────────────────────────

class WeeklyAwards:
    """Determine weekly award winners from current club data."""

    AWARD_CATEGORIES = [
        ("fraud_of_the_week", "Fraud of the Week", "fraud", "max"),
        ("ghost_of_the_week", "Ghost of the Week", "ghost", "max"),
        ("mvp_of_the_week", "MVP of the Week", "mvp", "max"),
        ("ball_loser_of_the_week", "Ball Loser of the Week", "ball_loser", "max"),
        ("carry_of_the_week", "Carry of the Week", "carry", "max"),
    ]

    @classmethod
    def determine_winners(cls, players: List[PlayerStats], matches: List[MatchResult]) -> List[dict]:
        """Determine all weekly winners."""
        winners = []
        if not players:
            return winners

        # Fraud of the week = highest fraud score
        fraud_scores = [(FraudScoreSystem.compute(p)["score"], p) for p in players]
        fraud_winner = max(fraud_scores, key=lambda x: x[0])
        winners.append({
            "award": "fraud_of_the_week",
            "title": "🎭 Fraud of the Week",
            "player": fraud_winner[1],
            "score": fraud_winner[0],
            "description": f"{fraud_winner[1].name} — Fraud Score {fraud_winner[0]}/100 ({FraudScoreSystem.classify(fraud_winner[0])})"
        })

        # Ghost of the week = highest ghost points
        ghost_scores = [(GhostScoreSystem.compute(p)["ghost_points"], p) for p in players]
        ghost_winner = max(ghost_scores, key=lambda x: x[0])
        if ghost_winner[0] >= 40:
            winners.append({
                "award": "ghost_of_the_week",
                "title": "👻 Ghost of the Week",
                "player": ghost_winner[1],
                "score": ghost_winner[0],
                "description": f"{ghost_winner[1].name} — Ghost Score {ghost_winner[0]} ({GhostScoreSystem.compute(ghost_winner[1])['severity']})"
            })

        # MVP of the week = highest impact
        mvp = max(players, key=lambda p: p.impact_score)
        winners.append({
            "award": "mvp_of_the_week",
            "title": "🏆 MVP of the Week",
            "player": mvp,
            "score": mvp.impact_score,
            "description": f"{mvp.name} — Impact {mvp.impact_score} | Goals {mvp.goals} | Rating {round(mvp.rating_pg, 1)}"
        })

        # Ball loser of the week = most possession losses
        bl = max(players, key=lambda p: p.possession_losses)
        winners.append({
            "award": "ball_loser_of_the_week",
            "title": "💀 Ball Loser of the Week",
            "player": bl,
            "score": bl.possession_losses,
            "description": f"{bl.name} — {bl.possession_losses} possession losses | Pass Acc {round(bl.pass_accuracy, 1)}%"
        })

        # Carry of the week = highest carry score
        carry_scores = [(CarryScoreSystem.compute(p)["score_per_game"], p) for p in players]
        carry_winner = max(carry_scores, key=lambda x: x[0])
        winners.append({
            "award": "carry_of_the_week",
            "title": "💪 Carry of the Week",
            "player": carry_winner[1],
            "score": carry_winner[0],
            "description": f"{carry_winner[1].name} — Carry Score {carry_winner[0]}/game ({CarryScoreSystem.compute(carry_winner[1])['classification']})"
        })

        return winners

    @classmethod
    def format_post(cls, winners: List[dict]) -> str:
        text = "📅 **WEEKLY AWARDS** — الأسبوع اللي فات\n\n"
        for w in winners:
            text += f"{w['title']}\n"
            text += f"   🏆 {w['description']}\n\n"
        text += "الأرقام ما كتكدبش. الجاي أحسن."
        return text


# ─────────────────────────────────────────────────────────────
# 8. MILESTONE TRACKER
# ─────────────────────────────────────────────────────────────

MILESTONE_THRESHOLDS = {
    "goals": [50, 100, 150, 200, 250, 300],
    "assists": [50, 100, 150, 200, 250, 300],
    "mvps": [10, 25, 50, 75, 100],
    "frauds": [10, 25, 50, 75, 100],  # fun milestone
    "possession_losses": [100, 250, 500, 750, 1000],
    "games": [50, 100, 200, 300, 500],
    "tackles": [100, 250, 500, 750, 1000],
}


class MilestoneTracker:
    """Auto-detect and announce milestones."""

    @classmethod
    def check_milestones(cls, player: PlayerStats, already_alerted: dict) -> List[dict]:
        """Check if player crossed any milestone thresholds."""
        alerts = []
        stats_map = {
            "goals": player.goals,
            "assists": player.assists,
            "mvps": player.motm,
            "frauds": 0,  # computed from fraud score history
            "possession_losses": player.possession_losses,
            "games": player.games,
            "tackles": player.tackles,
        }

        for stat_name, thresholds in MILESTONE_THRESHOLDS.items():
            current = stats_map.get(stat_name, 0)
            for threshold in thresholds:
                if current >= threshold:
                    key = f"{player.name}_{stat_name}_{threshold}"
                    if key not in already_alerted:
                        alerts.append({
                            "player": player.name,
                            "stat": stat_name,
                            "threshold": threshold,
                            "current": current,
                            "key": key,
                        })

        return alerts

    @classmethod
    def format_alert(cls, alert: dict) -> str:
        player = alert["player"]
        stat = alert["stat"]
        threshold = alert["threshold"]
        current = alert["current"]

        emojis = {
            "goals": "⚽",
            "assists": "🅰️",
            "mvps": "🏆",
            "frauds": "🎭",
            "possession_losses": "💀",
            "games": "🎮",
            "tackles": "🛡️",
        }
        emoji = emojis.get(stat, "🔥")

        texts = {
            "goals": f"🚨 {player} وصل لـ {threshold} goals! {emoji}\nالتاريخ كيتكتب بدمه.",
            "assists": f"🚨 {player} وصل لـ {threshold} assists! {emoji}\nصانع الألعاب الحقيقي.",
            "mvps": f"🚨 {player} وصل لـ {threshold} MVPs! {emoji}\nالملك ما كيحتاجش دليل.",
            "frauds": f"🚨 {player} وصل لـ {threshold} frauds! {emoji}\nهادا رقم تاريخي... فالعكس.",
            "possession_losses": f"🚨 {player} وصل لـ {threshold} possession losses! {emoji}\nالكرة خاصها restraining order.",
            "games": f"🚨 {player} وصل لـ {threshold} games! {emoji}\nولاء تاريخي للفريق.",
            "tackles": f"🚨 {player} وصل لـ {threshold} tackles! {emoji}\nالدفاع بدا من عندو.",
        }
        return texts.get(stat, f"🚨 {player} وصل لـ {threshold} {stat}! {emoji}")


# ─────────────────────────────────────────────────────────────
# 9. EXCUSES ENGINE
# ─────────────────────────────────────────────────────────────

EXCUSES_LIBRARY = {
    "rating": [
        "الكونترول كان فيه lag",
        "اليد كانت مقلوبة",
        "القط قطع عليا النت",
        "الكونترول ناقص البطارية",
        "الشاشة كانت مظلمة",
        "كنت لابس الجوارب و الزليج زلق",
        "الكرسي كان مرتفع",
        "النور كان كيدور فعينيا",
        "الكونترول جديد وماشي معتاد عليه",
        "الwifi ديال الجيران دخل",
    ],
    "possession": [
        "النت كان مقطع",
        "الخصم كان كيدير hack",
        "الكورة كانت مبلولة",
        "الملعب كان زلق",
        "الحكم ما دارش foul",
        "كنت كنتسنا pass وما جاتش",
        "الlinesman كان عندو نظارة قديمة",
        "الكاميرا كانت كتبطئ",
        "الgame mode كان فالnight mode",
    ],
    "goals": [
        "الحارس كان كيدير glitch",
        "الgoalkeeper كان level 99",
        "القائم كان كيدافع عليا",
        "الكورة ما بغاتش تدخل",
        "الwind factor كان ضدي",
        "الkeeper دار superman dive",
        "الpitch كان مائل",
        "الball physics كانت خايبة",
        "كنت كنتجرب new finishing style",
    ],
    "ghost": [
        "كنت كنتجرب position جديدة",
        "الcoach قالي نبقى فالخلف",
        "كنت كنتسنا instruction من الvoice chat",
        "الماتش كان tactical",
        "كنت كنتدرب defensive positioning",
        "الformation ما كانتش مناسبة",
        "كنت كنتجرب role جديد",
        "الtactics كانت zonal marking",
    ],
    "general": [
        "العشا كان تقيل",
        "كنت سهران البارح",
        "الخوخة ديال الداكرة كانت عاملة",
        "الجو كان حار",
        "ال conditioning ديالي كان off",
        "كنت كنتفكر فالexam",
        "الphone ديالي دار notification",
        "الأم كانت كتنادي",
        "الwater bottle طاح فالكونترول",
        "الcat walked on the controller",
    ],
}


class ExcusesEngine:
    """Generate fake excuses based on player history."""

    @classmethod
    def generate(cls, player: PlayerStats, match_stats: Optional[dict] = None) -> str:
        """Generate 3-5 excuses based on player's actual weaknesses."""
        excuses = []

        # Pick excuses based on player's worst stats
        if player.rating_pg < 6.0:
            excuses.append(random.choice(EXCUSES_LIBRARY["rating"]))
        if player.possession_losses > 10:
            excuses.append(random.choice(EXCUSES_LIBRARY["possession"]))
        if player.goals == 0 and player.games > 2:
            excuses.append(random.choice(EXCUSES_LIBRARY["goals"]))
        if player.pass_accuracy < 70:
            excuses.append(random.choice(EXCUSES_LIBRARY["possession"]))

        ghost = GhostScoreSystem.compute(player)
        if ghost["is_ghost"]:
            excuses.append(random.choice(EXCUSES_LIBRARY["ghost"]))

        # Always add 1-2 general excuses
        excuses.append(random.choice(EXCUSES_LIBRARY["general"]))
        if random.random() < 0.5:
            excuses.append(random.choice(EXCUSES_LIBRARY["general"]))

        # Shuffle and format
        random.shuffle(excuses)
        text = f"📝 **EXCUSES — {player.name}**\n\n"
        text += "الدفاع ديال {player.name} فالمحكمة:\n\n"
        for i, excuse in enumerate(excuses[:5], 1):
            text += f"{i}. {excuse}\n"

        text += "\n⚖️ **الحكم:** هاد الأعذار أضعف من defense ديال الفريق."
        return text


# ─────────────────────────────────────────────────────────────
# 10. MATCH POSTER ENGINE
# ─────────────────────────────────────────────────────────────

class MatchPosterEngine:
    """Generate match poster data from a single match."""

    @classmethod
    def build_poster_data(cls, match: MatchResult, players: List[PlayerStats]) -> dict:
        """Build all data needed for a match poster."""
        if not match.player_stats:
            return {}

        # Build player lookup
        player_map = {}
        for p in players:
            player_map[p.name.lower()] = p
            player_map[getattr(p, "_raw_psn", "").lower()] = p

        match_players = []
        for psn_raw, stats in match.player_stats.items():
            player = player_map.get(psn_raw.lower())
            if not player:
                for p in players:
                    if p.name.lower() in psn_raw.lower() or psn_raw.lower() in p.name.lower():
                        player = p
                        break

            rating = stats.get("rating", 0)
            if rating > 10:
                rating = round(rating / 10.0, 1)

            fraud = FraudScoreSystem.compute_match_fraud(stats)
            carry = CarryScoreSystem.compute_match_carry(stats)
            ghost = GhostScoreSystem._compute_match_ghost(stats)

            match_players.append({
                "name": player.name if player else psn_raw,
                "stats": stats,
                "rating": rating,
                "fraud_score": fraud["score"],
                "fraud_class": fraud["classification"],
                "carry_score": carry["score"],
                "carry_class": carry["classification"],
                "ghost_points": ghost["ghost_points"],
                "is_ghost": ghost["is_ghost"],
                "player_obj": player,
            })

        if not match_players:
            return {}

        # Determine awards
        mvp = max(match_players, key=lambda x: x["carry_score"])
        fraud = max(match_players, key=lambda x: x["fraud_score"])
        ghost = max(match_players, key=lambda x: x["ghost_points"])
        carry = max(match_players, key=lambda x: x["carry_score"])
        top_performer = max(match_players, key=lambda x: x["rating"])
        worst_performer = min(match_players, key=lambda x: x["rating"])

        return {
            "match": match,
            "score": f"{match.score_for}-{match.score_against}",
            "opponent": match.opponent,
            "result": match.result,
            "mvp": mvp,
            "fraud": fraud,
            "ghost": ghost if ghost["is_ghost"] else None,
            "carry": carry,
            "top_performer": top_performer,
            "worst_performer": worst_performer,
            "all_players": match_players,
        }
