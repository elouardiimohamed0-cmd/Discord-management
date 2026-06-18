"""
ecosystem_engine.py — PHASE 4: Full Football Ecosystem (Bulletproof)
======================================================================
Zero assumptions about PlayerStats attributes. Uses getattr everywhere.
"""

import math
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field

# Defensive import — if models missing, we define stubs
try:
    from models import PlayerStats, ClubStats, MatchResult
except Exception:
    PlayerStats = None
    MatchResult = None


# ─────────────────────────────────────────────────────────────
# 1. FRAUD SCORE SYSTEM
# ─────────────────────────────────────────────────────────────

class FraudScoreSystem:
    @classmethod
    def compute(cls, player, match_stats=None):
        score = 0
        breakdown = []
        g = max(getattr(player, "games", 0), 1)

        rating = getattr(player, "rating_pg", 0)
        if rating < 5.0:
            score += 30; breakdown.append(("Rating < 5.0", 30))
        elif rating < 5.5:
            score += 25; breakdown.append(("Rating < 5.5", 25))
        elif rating < 6.0:
            score += 15; breakdown.append(("Rating < 6.0", 15))
        elif rating < 6.5:
            score += 5; breakdown.append(("Rating < 6.5", 5))

        pl = getattr(player, "possession_losses", 0)
        pl_pg = pl / g
        if pl_pg > 20:
            score += 25; breakdown.append(("Possession Lost > 20/match", 25))
        elif pl_pg > 15:
            score += 20; breakdown.append(("Possession Lost > 15/match", 20))
        elif pl_pg > 10:
            score += 10; breakdown.append(("Possession Lost > 10/match", 10))

        pa = getattr(player, "pass_accuracy", 100)
        if pa < 50:
            score += 20; breakdown.append(("Pass Accuracy < 50%", 20))
        elif pa < 60:
            score += 15; breakdown.append(("Pass Accuracy < 60%", 15))
        elif pa < 70:
            score += 10; breakdown.append(("Pass Accuracy < 70%", 10))

        goals = getattr(player, "goals", 0)
        assists = getattr(player, "assists", 0)
        if goals == 0 and assists == 0 and g > 3:
            score += 15; breakdown.append(("Zero Goals + Assists (3+ games)", 15))

        shots = getattr(player, "shots", 0)
        if match_stats:
            ms_shots = match_stats.get("shots", 0)
            ms_goals = match_stats.get("goals", 0)
            if ms_shots > 3 and ms_goals == 0:
                score += 10; breakdown.append(("Missed Chances (3+ shots, 0 goals)", 10))
        else:
            if shots > 10 and goals == 0:
                score += 10; breakdown.append(("Missed Chances (10+ shots, 0 goals)", 10))

        # Ghost check (safe)
        ghost_score = GhostScoreSystem.compute(player, match_stats)
        if ghost_score.get("is_ghost"):
            score += 10; breakdown.append(("Ghost Performance", 10))

        wr = getattr(player, "win_rate", 50)
        if wr < 30 and g > 5:
            score += 10; breakdown.append(("Win Rate < 30%", 10))
        elif wr < 40 and g > 5:
            score += 5; breakdown.append(("Win Rate < 40%", 5))

        score = min(score, 100)
        classification = cls.classify(score)
        return {"score": score, "classification": classification, "breakdown": breakdown, "label": classification}

    @classmethod
    def classify(cls, score):
        if score <= 30: return "Safe"
        elif score <= 60: return "Suspicious"
        elif score <= 80: return "Fraud"
        else: return "Criminal"

    @classmethod
    def compute_match_fraud(cls, match_stats):
        score = 0; breakdown = []
        rating = match_stats.get("rating", 0)
        if rating > 10: rating = round(rating / 10.0, 1)
        if rating < 5.0: score += 30; breakdown.append(("Rating < 5.0", 30))
        elif rating < 5.5: score += 25; breakdown.append(("Rating < 5.5", 25))
        elif rating < 6.0: score += 15; breakdown.append(("Rating < 6.0", 15))

        passes_att = match_stats.get("passes_attempted", 0)
        passes_comp = match_stats.get("passes_completed", 0)
        pl = passes_att - passes_comp
        if pl > 20: score += 25; breakdown.append(("Possession Lost > 20", 25))
        elif pl > 15: score += 20; breakdown.append(("Possession Lost > 15", 20))
        elif pl > 10: score += 10; breakdown.append(("Possession Lost > 10", 10))

        pa = round(passes_comp / max(passes_att, 1) * 100, 1)
        if pa < 50: score += 20; breakdown.append(("Pass Accuracy < 50%", 20))
        elif pa < 60: score += 15; breakdown.append(("Pass Accuracy < 60%", 15))
        elif pa < 70: score += 10; breakdown.append(("Pass Accuracy < 70%", 10))

        goals = match_stats.get("goals", 0)
        assists = match_stats.get("assists", 0)
        if goals == 0 and assists == 0:
            score += 15; breakdown.append(("Zero Contribution", 15))

        shots = match_stats.get("shots", 0)
        if shots > 3 and goals == 0:
            score += 10; breakdown.append(("Missed Chances", 10))

        touches = match_stats.get("touches", 0) or match_stats.get("passes_attempted", 0)
        if touches < 15:
            score += 10; breakdown.append(("Ghost Performance", 10))

        score = min(score, 100)
        return {"score": score, "classification": cls.classify(score), "breakdown": breakdown}


# ─────────────────────────────────────────────────────────────
# 2. CARRY SCORE SYSTEM
# ─────────────────────────────────────────────────────────────

class CarryScoreSystem:
    @classmethod
    def compute(cls, player):
        g = max(getattr(player, "games", 0), 1)
        score = (
            getattr(player, "goals", 0) * 5 +
            getattr(player, "assists", 0) * 4 +
            getattr(player, "tackles", 0) * 2 +
            getattr(player, "interceptions", 0) * 2 +
            getattr(player, "pass_accuracy", 0) * 0.5 +
            getattr(player, "motm", 0) * 10 +
            getattr(player, "rating_pg", 0) * 5
        )
        score_pg = round(score / g, 1)
        if score_pg >= 25: classification = "Legendary Carry"
        elif score_pg >= 18: classification = "Hard Carry"
        elif score_pg >= 12: classification = "Carry"
        elif score_pg >= 8: classification = "Helpful"
        else: classification = "Passenger"
        return {
            "total_score": round(score, 1),
            "score_per_game": score_pg,
            "classification": classification,
            "breakdown": {
                "goals": getattr(player, "goals", 0) * 5,
                "assists": getattr(player, "assists", 0) * 4,
                "tackles": getattr(player, "tackles", 0) * 2,
                "interceptions": getattr(player, "interceptions", 0) * 2,
                "pass_accuracy": round(getattr(player, "pass_accuracy", 0) * 0.5, 1),
                "motm": getattr(player, "motm", 0) * 10,
                "rating": round(getattr(player, "rating_pg", 0) * 5, 1),
            }
        }

    @classmethod
    def compute_match_carry(cls, match_stats):
        goals = match_stats.get("goals", 0)
        assists = match_stats.get("assists", 0)
        tackles = match_stats.get("tackles", 0)
        interceptions = match_stats.get("interceptions", 0)
        passes_att = match_stats.get("passes_attempted", 0)
        passes_comp = match_stats.get("passes_completed", 0)
        pa = round(passes_comp / max(passes_att, 1) * 100, 1)
        motm = 1 if match_stats.get("motm", False) else 0
        rating = match_stats.get("rating", 0)
        if rating > 10: rating = round(rating / 10.0, 1)
        score = goals * 5 + assists * 4 + tackles * 2 + interceptions * 2 + pa * 0.5 + motm * 10 + rating * 5
        if score >= 40: classification = "Legendary Carry"
        elif score >= 30: classification = "Hard Carry"
        elif score >= 20: classification = "Carry"
        elif score >= 12: classification = "Helpful"
        else: classification = "Passenger"
        return {"score": round(score, 1), "classification": classification}


# ─────────────────────────────────────────────────────────────
# 3. GHOST SCORE SYSTEM
# ─────────────────────────────────────────────────────────────

class GhostScoreSystem:
    @classmethod
    def compute(cls, player, match_stats=None):
        if match_stats:
            return cls._compute_match_ghost(match_stats)
        g = max(getattr(player, "games", 0), 1)
        # Safe attribute access
        passes_made = getattr(player, "passes_made", 0)
        possession_losses = getattr(player, "possession_losses", 0)
        touches = getattr(player, "touches", 0) or (passes_made + possession_losses)
        passes = passes_made
        duels = getattr(player, "tackles", 0) + getattr(player, "interceptions", 0)
        shots = getattr(player, "shots", 0)
        goals = getattr(player, "goals", 0)
        assists = getattr(player, "assists", 0)
        minutes = getattr(player, "minutes_played", 90 * g)

        touches_pg = touches / g
        passes_pg = passes / g
        duels_pg = duels / g
        shots_pg = shots / g
        contrib_pg = (goals + assists) / g

        ghost_points = 0; reasons = []
        if touches_pg < 20: ghost_points += 25; reasons.append(f"Touches {round(touches_pg,1)}/game (< 20)")
        elif touches_pg < 30: ghost_points += 15; reasons.append(f"Touches {round(touches_pg,1)}/game (< 30)")
        if passes_pg < 10: ghost_points += 20; reasons.append(f"Passes {round(passes_pg,1)}/game (< 10)")
        elif passes_pg < 15: ghost_points += 10; reasons.append(f"Passes {round(passes_pg,1)}/game (< 15)")
        if duels_pg < 2: ghost_points += 15; reasons.append(f"Duels {round(duels_pg,1)}/game (< 2)")
        if shots_pg < 0.5 and contrib_pg == 0: ghost_points += 15; reasons.append("No shots + no contributions")
        if contrib_pg == 0 and g > 3: ghost_points += 15; reasons.append("Zero contributions (3+ games)")
        if minutes / g < 30: ghost_points += 10; reasons.append("Avg minutes < 30")

        is_ghost = ghost_points >= 40
        if ghost_points >= 70: severity = "Phantom"
        elif ghost_points >= 50: severity = "Ghost"
        elif ghost_points >= 40: severity = "Shadow"
        elif ghost_points >= 20: severity = "Fading"
        else: severity = "None"
        return {"ghost_points": ghost_points, "is_ghost": is_ghost, "severity": severity, "reasons": reasons}

    @classmethod
    def _compute_match_ghost(cls, match_stats):
        touches = match_stats.get("touches", 0) or match_stats.get("passes_attempted", 0)
        passes = match_stats.get("passes_attempted", 0)
        duels = match_stats.get("tackles", 0) + match_stats.get("interceptions", 0)
        shots = match_stats.get("shots", 0)
        contrib = match_stats.get("goals", 0) + match_stats.get("assists", 0)
        ghost_points = 0; reasons = []
        if touches < 15: ghost_points += 25; reasons.append(f"Touches {touches} (< 15)")
        elif touches < 25: ghost_points += 15; reasons.append(f"Touches {touches} (< 25)")
        if passes < 8: ghost_points += 20; reasons.append(f"Passes {passes} (< 8)")
        elif passes < 12: ghost_points += 10; reasons.append(f"Passes {passes} (< 12)")
        if duels < 1: ghost_points += 15; reasons.append(f"Duels {duels} (< 1)")
        if shots == 0 and contrib == 0: ghost_points += 15; reasons.append("No shots + no contributions")
        is_ghost = ghost_points >= 40
        if ghost_points >= 70: severity = "Phantom"
        elif ghost_points >= 50: severity = "Ghost"
        elif ghost_points >= 40: severity = "Shadow"
        elif ghost_points >= 20: severity = "Fading"
        else: severity = "None"
        return {"ghost_points": ghost_points, "is_ghost": is_ghost, "severity": severity, "reasons": reasons}


# ─────────────────────────────────────────────────────────────
# 4. HALL OF SHAME
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
    CATEGORIES = [
        "worst_rating_ever", "most_possession_lost_ever", "biggest_fraud_performance",
        "worst_pass_accuracy_ever", "most_missed_chances_ever", "biggest_ghost_performance",
        "worst_carry_score_ever",
    ]

    @classmethod
    def scan_matches(cls, matches, players):
        records = []
        if not matches: return records
        # Build lookup
        name_to_psn = {}
        for p in players:
            raw = getattr(p, "_raw_psn", getattr(p, "name", ""))
            name_to_psn[getattr(p, "name", "")] = raw
            name_to_psn[raw.lower()] = raw

        worst_rating = most_pl = biggest_fraud = worst_pa = most_missed = biggest_ghost = worst_carry = None

        for match in matches:
            ps = getattr(match, "player_stats", None)
            if not ps: continue
            for psn_raw, stats in ps.items():
                player_name = psn_raw
                for p in players:
                    if getattr(p, "_raw_psn", "").lower() == psn_raw.lower() or getattr(p, "name", "").lower() == psn_raw.lower():
                        player_name = p.name; break

                rating = stats.get("rating", 0)
                if rating > 10: rating = round(rating / 10.0, 1)
                passes_att = stats.get("passes_attempted", 0)
                passes_comp = stats.get("passes_completed", 0)
                pl = passes_att - passes_comp
                pa = round(passes_comp / max(passes_att, 1) * 100, 1)
                shots = stats.get("shots", 0)
                goals = stats.get("goals", 0)

                mdate = getattr(match, "date", "")
                if hasattr(mdate, "strftime"): mdate = mdate.strftime("%d/%m/%Y")
                else: mdate = str(mdate)

                if worst_rating is None or rating < worst_rating.value:
                    worst_rating = ShameRecord("worst_rating_ever", player_name, rating, match.match_id, match.opponent, mdate, f"Rating {rating} vs {match.opponent}")
                if most_pl is None or pl > most_pl.value:
                    most_pl = ShameRecord("most_possession_lost_ever", player_name, pl, match.match_id, match.opponent, mdate, f"{pl} possession losses vs {match.opponent}")
                if passes_att >= 5 and (worst_pa is None or pa < worst_pa.value):
                    worst_pa = ShameRecord("worst_pass_accuracy_ever", player_name, pa, match.match_id, match.opponent, mdate, f"{pa}% pass accuracy vs {match.opponent}")
                if shots > 3 and goals == 0 and (most_missed is None or shots > most_missed.value):
                    most_missed = ShameRecord("most_missed_chances_ever", player_name, shots, match.match_id, match.opponent, mdate, f"{shots} shots, 0 goals vs {match.opponent}")

                fraud = FraudScoreSystem.compute_match_fraud(stats)
                if biggest_fraud is None or fraud["score"] > biggest_fraud.value:
                    biggest_fraud = ShameRecord("biggest_fraud_performance", player_name, fraud["score"], match.match_id, match.opponent, mdate, f"Fraud Score {fraud['score']} ({fraud['classification']}) vs {match.opponent}")

                ghost = GhostScoreSystem._compute_match_ghost(stats)
                if biggest_ghost is None or ghost["ghost_points"] > biggest_ghost.value:
                    biggest_ghost = ShameRecord("biggest_ghost_performance", player_name, ghost["ghost_points"], match.match_id, match.opponent, mdate, f"Ghost Score {ghost['ghost_points']} ({ghost['severity']}) vs {match.opponent}")

                carry = CarryScoreSystem.compute_match_carry(stats)
                if worst_carry is None or carry["score"] < worst_carry.value:
                    worst_carry = ShameRecord("worst_carry_score_ever", player_name, carry["score"], match.match_id, match.opponent, mdate, f"Carry Score {carry['score']} ({carry['classification']}) vs {match.opponent}")

        for rec in [worst_rating, most_pl, biggest_fraud, worst_pa, most_missed, biggest_ghost, worst_carry]:
            if rec: records.append(rec)
        return records

    @classmethod
    def get_records_text(cls, records):
        if not records: return "🏛️ **Hall of Shame**\n\nما كاين حتى شي record لحد الآن."
        text = "🏛️ **HALL OF SHAME** — الأرقام ما كتكدبش\n\n"
        emojis = {"worst_rating_ever": "📉", "most_possession_lost_ever": "💀", "biggest_fraud_performance": "🎭",
                  "worst_pass_accuracy_ever": "🎯", "most_missed_chances_ever": "❌", "biggest_ghost_performance": "👻",
                  "worst_carry_score_ever": "🎒"}
        labels = {"worst_rating_ever": "Worst Rating Ever", "most_possession_lost_ever": "Most Possession Lost Ever",
                  "biggest_fraud_performance": "Biggest Fraud Performance", "worst_pass_accuracy_ever": "Worst Pass Accuracy Ever",
                  "most_missed_chances_ever": "Most Missed Chances Ever", "biggest_ghost_performance": "Biggest Ghost Performance",
                  "worst_carry_score_ever": "Worst Carry Score Ever"}
        for rec in records:
            emoji = emojis.get(rec.category, "🔥")
            label = labels.get(rec.category, rec.category)
            text += f"{emoji} **{label}**\n   {rec.player_name} — {rec.description}\n\n"
        return text


# ─────────────────────────────────────────────────────────────
# 5. HALL OF FAME
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
    CATEGORIES = ["highest_rating_ever", "most_goals_in_match", "most_assists_in_match", "best_carry_performance", "best_defender_performance", "most_mvps_season"]

    @classmethod
    def scan_matches(cls, matches, players):
        records = []
        if not matches: return records
        highest_rating = most_goals = most_assists = best_carry = best_defender = None

        for match in matches:
            ps = getattr(match, "player_stats", None)
            if not ps: continue
            for psn_raw, stats in ps.items():
                player_name = psn_raw
                for p in players:
                    if getattr(p, "_raw_psn", "").lower() == psn_raw.lower() or getattr(p, "name", "").lower() == psn_raw.lower():
                        player_name = p.name; break

                rating = stats.get("rating", 0)
                if rating > 10: rating = round(rating / 10.0, 1)
                goals = stats.get("goals", 0)
                assists = stats.get("assists", 0)
                tackles = stats.get("tackles", 0)
                interceptions = stats.get("interceptions", 0)

                mdate = getattr(match, "date", "")
                if hasattr(mdate, "strftime"): mdate = mdate.strftime("%d/%m/%Y")
                else: mdate = str(mdate)

                if highest_rating is None or rating > highest_rating.value:
                    highest_rating = FameRecord("highest_rating_ever", player_name, rating, match.match_id, match.opponent, mdate, f"Rating {rating} vs {match.opponent}")
                if most_goals is None or goals > most_goals.value:
                    most_goals = FameRecord("most_goals_in_match", player_name, goals, match.match_id, match.opponent, mdate, f"{goals} goals vs {match.opponent}")
                if most_assists is None or assists > most_assists.value:
                    most_assists = FameRecord("most_assists_in_match", player_name, assists, match.match_id, match.opponent, mdate, f"{assists} assists vs {match.opponent}")

                carry = CarryScoreSystem.compute_match_carry(stats)
                if best_carry is None or carry["score"] > best_carry.value:
                    best_carry = FameRecord("best_carry_performance", player_name, carry["score"], match.match_id, match.opponent, mdate, f"Carry Score {carry['score']} ({carry['classification']}) vs {match.opponent}")

                def_score = tackles * 2 + interceptions * 1.5
                if best_defender is None or def_score > best_defender.value:
                    best_defender = FameRecord("best_defender_performance", player_name, round(def_score, 1), match.match_id, match.opponent, mdate, f"{tackles} tackles + {interceptions} interceptions vs {match.opponent}")

        if players:
            mvp_player = max(players, key=lambda p: getattr(p, "motm", 0))
            if getattr(mvp_player, "motm", 0) > 0:
                records.append(FameRecord("most_mvps_season", mvp_player.name, mvp_player.motm, description=f"{mvp_player.motm} MVPs this season"))

        for rec in [highest_rating, most_goals, most_assists, best_carry, best_defender]:
            if rec: records.append(rec)
        return records

    @classmethod
    def get_records_text(cls, records):
        if not records: return "🏆 **Hall of Fame**\n\nما كاين حتى شي record لحد الآن."
        text = "🏆 **HALL OF FAME** — التاريخ ما كينساش\n\n"
        emojis = {"highest_rating_ever": "⭐", "most_goals_in_match": "⚽", "most_assists_in_match": "🅰️",
                  "best_carry_performance": "💪", "best_defender_performance": "🛡️", "most_mvps_season": "🏆"}
        labels = {"highest_rating_ever": "Highest Rating Ever", "most_goals_in_match": "Most Goals in One Match",
                  "most_assists_in_match": "Most Assists in One Match", "best_carry_performance": "Best Carry Performance",
                  "best_defender_performance": "Best Defender Performance", "most_mvps_season": "Most MVPs This Season"}
        for rec in records:
            emoji = emojis.get(rec.category, "👑")
            label = labels.get(rec.category, rec.category)
            text += f"{emoji} **{label}**\n   {rec.player_name} — {rec.description}\n\n"
        return text


# ─────────────────────────────────────────────────────────────
# 6. RIVALRY SYSTEM
# ─────────────────────────────────────────────────────────────

class RivalrySystem:
    @classmethod
    def compare(cls, p1, p2, matches):
        both_played = 0; p1_wins = 0; p2_wins = 0; p1_goals_h2h = 0; p2_goals_h2h = 0
        p1_psn = getattr(p1, "_raw_psn", getattr(p1, "name", "")).lower()
        p2_psn = getattr(p2, "_raw_psn", getattr(p2, "name", "")).lower()

        for match in matches:
            ps = getattr(match, "player_stats", None)
            if not ps: continue
            psns = [k.lower() for k in ps.keys()]
            if p1_psn in psns and p2_psn in psns:
                both_played += 1
                s1 = ps.get(p1_psn, ps.get(getattr(p1, "name", ""), {}))
                s2 = ps.get(p2_psn, ps.get(getattr(p2, "name", ""), {}))
                g1 = s1.get("goals", 0); g2 = s2.get("goals", 0)
                p1_goals_h2h += g1; p2_goals_h2h += g2
                if g1 > g2: p1_wins += 1
                elif g2 > g1: p2_wins += 1

        stats = {
            "p1_name": getattr(p1, "name", "?"), "p2_name": getattr(p2, "name", "?"),
            "goals": {"p1": getattr(p1, "goals", 0), "p2": getattr(p2, "goals", 0), "winner": getattr(p1, "name", "") if getattr(p1, "goals", 0) > getattr(p2, "goals", 0) else getattr(p2, "name", "") if getattr(p2, "goals", 0) > getattr(p1, "goals", 0) else "Tie"},
            "assists": {"p1": getattr(p1, "assists", 0), "p2": getattr(p2, "assists", 0), "winner": getattr(p1, "name", "") if getattr(p1, "assists", 0) > getattr(p2, "assists", 0) else getattr(p2, "name", "") if getattr(p2, "assists", 0) > getattr(p1, "assists", 0) else "Tie"},
            "rating": {"p1": round(getattr(p1, "rating_pg", 0), 1), "p2": round(getattr(p2, "rating_pg", 0), 1), "winner": getattr(p1, "name", "") if getattr(p1, "rating_pg", 0) > getattr(p2, "rating_pg", 0) else getattr(p2, "name", "") if getattr(p2, "rating_pg", 0) > getattr(p1, "rating_pg", 0) else "Tie"},
            "win_rate": {"p1": round(getattr(p1, "win_rate", 0), 1), "p2": round(getattr(p2, "win_rate", 0), 1), "winner": getattr(p1, "name", "") if getattr(p1, "win_rate", 0) > getattr(p2, "win_rate", 0) else getattr(p2, "name", "") if getattr(p2, "win_rate", 0) > getattr(p1, "win_rate", 0) else "Tie"},
            "possession_lost": {"p1": getattr(p1, "possession_losses", 0), "p2": getattr(p2, "possession_losses", 0), "winner": getattr(p1, "name", "") if getattr(p1, "possession_losses", 0) < getattr(p2, "possession_losses", 0) else getattr(p2, "name", "") if getattr(p2, "possession_losses", 0) < getattr(p1, "possession_losses", 0) else "Tie"},
            "motm": {"p1": getattr(p1, "motm", 0), "p2": getattr(p2, "motm", 0), "winner": getattr(p1, "name", "") if getattr(p1, "motm", 0) > getattr(p2, "motm", 0) else getattr(p2, "name", "") if getattr(p2, "motm", 0) > getattr(p1, "motm", 0) else "Tie"},
            "impact": {"p1": getattr(p1, "impact_score", 0), "p2": getattr(p2, "impact_score", 0), "winner": getattr(p1, "name", "") if getattr(p1, "impact_score", 0) > getattr(p2, "impact_score", 0) else getattr(p2, "name", "") if getattr(p2, "impact_score", 0) > getattr(p1, "impact_score", 0) else "Tie"},
            "h2h_matches": both_played, "h2h_p1_wins": p1_wins, "h2h_p2_wins": p2_wins,
            "h2h_p1_goals": p1_goals_h2h, "h2h_p2_goals": p2_goals_h2h,
        }
        p1_wins_cat = sum(1 for cat in ["goals", "assists", "rating", "win_rate", "possession_lost", "motm", "impact"] if stats[cat]["winner"] == getattr(p1, "name", ""))
        p2_wins_cat = sum(1 for cat in ["goals", "assists", "rating", "win_rate", "possession_lost", "motm", "impact"] if stats[cat]["winner"] == getattr(p2, "name", ""))
        if p1_wins_cat > p2_wins_cat: overall_winner = getattr(p1, "name", ""); overall_loser = getattr(p2, "name", "")
        elif p2_wins_cat > p1_wins_cat: overall_winner = getattr(p2, "name", ""); overall_loser = getattr(p1, "name", "")
        else: overall_winner = "Tie"; overall_loser = "Tie"
        stats["overall_winner"] = overall_winner
        stats["overall_loser"] = overall_loser
        stats["p1_categories_won"] = p1_wins_cat
        stats["p2_categories_won"] = p2_wins_cat
        return stats

    @classmethod
    def format_text(cls, stats):
        p1 = stats["p1_name"]; p2 = stats["p2_name"]; winner = stats["overall_winner"]; loser = stats["overall_loser"]
        text = f"⚔️ **RIVALRY: {p1} vs {p2}**\n\n📊 **Season Totals**\n"
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
    @classmethod
    def determine_winners(cls, players, matches):
        winners = []
        if not players: return winners
        fraud_scores = [(FraudScoreSystem.compute(p)["score"], p) for p in players]
        fraud_winner = max(fraud_scores, key=lambda x: x[0])
        winners.append({"award": "fraud_of_the_week", "title": "🎭 Fraud of the Week", "player": fraud_winner[1], "score": fraud_winner[0], "description": f"{fraud_winner[1].name} — Fraud Score {fraud_winner[0]}/100 ({FraudScoreSystem.classify(fraud_winner[0])})"})

        ghost_scores = [(GhostScoreSystem.compute(p)["ghost_points"], p) for p in players]
        ghost_winner = max(ghost_scores, key=lambda x: x[0])
        if ghost_winner[0] >= 40:
            winners.append({"award": "ghost_of_the_week", "title": "👻 Ghost of the Week", "player": ghost_winner[1], "score": ghost_winner[0], "description": f"{ghost_winner[1].name} — Ghost Score {ghost_winner[0]} ({GhostScoreSystem.compute(ghost_winner[1])['severity']})"})

        mvp = max(players, key=lambda p: getattr(p, "impact_score", 0))
        winners.append({"award": "mvp_of_the_week", "title": "🏆 MVP of the Week", "player": mvp, "score": getattr(mvp, "impact_score", 0), "description": f"{mvp.name} — Impact {getattr(mvp, 'impact_score', 0)} | Goals {getattr(mvp, 'goals', 0)} | Rating {round(getattr(mvp, 'rating_pg', 0), 1)}"})

        bl = max(players, key=lambda p: getattr(p, "possession_losses", 0))
        winners.append({"award": "ball_loser_of_the_week", "title": "💀 Ball Loser of the Week", "player": bl, "score": getattr(bl, "possession_losses", 0), "description": f"{bl.name} — {getattr(bl, 'possession_losses', 0)} possession losses | Pass Acc {round(getattr(bl, 'pass_accuracy', 0), 1)}%"})

        carry_scores = [(CarryScoreSystem.compute(p)["score_per_game"], p) for p in players]
        carry_winner = max(carry_scores, key=lambda x: x[0])
        winners.append({"award": "carry_of_the_week", "title": "💪 Carry of the Week", "player": carry_winner[1], "score": carry_winner[0], "description": f"{carry_winner[1].name} — Carry Score {carry_winner[0]}/game ({CarryScoreSystem.compute(carry_winner[1])['classification']})"})
        return winners

    @classmethod
    def format_post(cls, winners):
        text = "📅 **WEEKLY AWARDS** — الأسبوع اللي فات\n\n"
        for w in winners:
            text += f"{w['title']}\n   🏆 {w['description']}\n\n"
        text += "الأرقام ما كتكدبش. الجاي أحسن."
        return text


# ─────────────────────────────────────────────────────────────
# 8. MILESTONE TRACKER
# ─────────────────────────────────────────────────────────────

MILESTONE_THRESHOLDS = {
    "goals": [50, 100, 150, 200, 250, 300],
    "assists": [50, 100, 150, 200, 250, 300],
    "mvps": [10, 25, 50, 75, 100],
    "frauds": [10, 25, 50, 75, 100],
    "possession_losses": [100, 250, 500, 750, 1000],
    "games": [50, 100, 200, 300, 500],
    "tackles": [100, 250, 500, 750, 1000],
}

class MilestoneTracker:
    @classmethod
    def check_milestones(cls, player, already_alerted):
        alerts = []
        stats_map = {
            "goals": getattr(player, "goals", 0),
            "assists": getattr(player, "assists", 0),
            "mvps": getattr(player, "motm", 0),
            "frauds": 0,
            "possession_losses": getattr(player, "possession_losses", 0),
            "games": getattr(player, "games", 0),
            "tackles": getattr(player, "tackles", 0),
        }
        for stat_name, thresholds in MILESTONE_THRESHOLDS.items():
            current = stats_map.get(stat_name, 0)
            for threshold in thresholds:
                if current >= threshold:
                    key = f"{getattr(player, 'name', 'unknown')}_{stat_name}_{threshold}"
                    if key not in already_alerted:
                        alerts.append({"player": getattr(player, "name", "unknown"), "stat": stat_name, "threshold": threshold, "current": current, "key": key})
        return alerts

    @classmethod
    def format_alert(cls, alert):
        player = alert["player"]; stat = alert["stat"]; threshold = alert["threshold"]
        emojis = {"goals": "⚽", "assists": "🅰️", "mvps": "🏆", "frauds": "🎭", "possession_losses": "💀", "games": "🎮", "tackles": "🛡️"}
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
    "rating": ["الكونترول كان فيه lag", "اليد كانت مقلوبة", "القط قطع عليا النت", "الكونترول ناقص البطارية", "الشاشة كانت مظلمة", "كنت لابس الجوارب و الزليج زلق", "الكرسي كان مرتفع", "النور كان كيدور فعينيا", "الكونترول جديد وماشي معتاد عليه", "الwifi ديال الجيران دخل"],
    "possession": ["النت كان مقطع", "الخصم كان كيدير hack", "الكورة كانت مبلولة", "الملعب كان زلق", "الحكم ما دارش foul", "كنت كنتسنا pass وما جاتش", "الlinesman كان عندو نظارة قديمة", "الكاميرا كانت كتبطئ", "الgame mode كان فالnight mode"],
    "goals": ["الحارس كان كيدير glitch", "الgoalkeeper كان level 99", "القائم كان كيدافع عليا", "الكورة ما بغاتش تدخل", "الwind factor كان ضدي", "الkeeper دار superman dive", "الpitch كان مائل", "الball physics كانت خايبة", "كنت كنتجرب new finishing style"],
    "ghost": ["كنت كنتجرب position جديدة", "الcoach قالي نبقى فالخلف", "كنت كنتسنا instruction من الvoice chat", "الماتش كان tactical", "كنت كنتدرب defensive positioning", "الformation ما كانتش مناسبة", "كنت كنتجرب role جديد", "الtactics كانت zonal marking"],
    "general": ["العشا كان تقيل", "كنت سهران البارح", "الخوخة ديال الداكرة كانت عاملة", "الجو كان حار", "ال conditioning ديالي كان off", "كنت كنتفكر فالexam", "الphone ديالي دار notification", "الأم كانت كتنادي", "الwater bottle طاح فالكونترول", "الcat walked on the controller"],
}

class ExcusesEngine:
    @classmethod
    def generate(cls, player):
        excuses = []
        if getattr(player, "rating_pg", 10) < 6.0: excuses.append(random.choice(EXCUSES_LIBRARY["rating"]))
        if getattr(player, "possession_losses", 0) > 10: excuses.append(random.choice(EXCUSES_LIBRARY["possession"]))
        if getattr(player, "goals", 0) == 0 and getattr(player, "games", 0) > 2: excuses.append(random.choice(EXCUSES_LIBRARY["goals"]))
        if getattr(player, "pass_accuracy", 100) < 70: excuses.append(random.choice(EXCUSES_LIBRARY["possession"]))
        ghost = GhostScoreSystem.compute(player)
        if ghost.get("is_ghost"): excuses.append(random.choice(EXCUSES_LIBRARY["ghost"]))
        while len(excuses) < 4:
            exc = random.choice(EXCUSES_LIBRARY["general"])
            if exc not in excuses: excuses.append(exc)
        random.shuffle(excuses)
        text = f"📝 **EXCUSES — {getattr(player, 'name', 'Unknown')}**\n\n"
        text += f"الدفاع ديال {getattr(player, 'name', 'Unknown')} فالمحكمة:\n\n"
        for i, excuse in enumerate(excuses[:5], 1): text += f"{i}. {excuse}\n"
        text += "\n⚖️ **الحكم:** هاد الأعذار أضعف من defense ديال الفريق."
        return text


# ─────────────────────────────────────────────────────────────
# 10. MATCH POSTER ENGINE
# ─────────────────────────────────────────────────────────────

class MatchPosterEngine:
    @classmethod
    def build_poster_data(cls, match, players):
        ps = getattr(match, "player_stats", None)
        if not ps: return {}
        player_map = {}
        for p in players:
            player_map[getattr(p, "name", "").lower()] = p
            player_map[getattr(p, "_raw_psn", "").lower()] = p

        match_players = []
        for psn_raw, stats in ps.items():
            player = player_map.get(psn_raw.lower())
            if not player:
                for p in players:
                    if getattr(p, "name", "").lower() in psn_raw.lower() or psn_raw.lower() in getattr(p, "name", "").lower():
                        player = p; break

            rating = stats.get("rating", 0)
            if rating > 10: rating = round(rating / 10.0, 1)
            fraud = FraudScoreSystem.compute_match_fraud(stats)
            carry = CarryScoreSystem.compute_match_carry(stats)
            ghost = GhostScoreSystem._compute_match_ghost(stats)
            match_players.append({
                "name": getattr(player, "name", psn_raw) if player else psn_raw,
                "stats": stats, "rating": rating,
                "fraud_score": fraud["score"], "fraud_class": fraud["classification"],
                "carry_score": carry["score"], "carry_class": carry["classification"],
                "ghost_points": ghost["ghost_points"], "is_ghost": ghost["is_ghost"],
                "player_obj": player,
            })
        if not match_players: return {}
        mvp = max(match_players, key=lambda x: x["carry_score"])
        fraud = max(match_players, key=lambda x: x["fraud_score"])
        ghost = max(match_players, key=lambda x: x["ghost_points"])
        carry = max(match_players, key=lambda x: x["carry_score"])
        top = max(match_players, key=lambda x: x["rating"])
        worst = min(match_players, key=lambda x: x["rating"])
        return {
            "match": match, "score": f"{getattr(match, 'score_for', 0)}-{getattr(match, 'score_against', 0)}",
            "opponent": getattr(match, "opponent", "Unknown"), "result": getattr(match, "result", "D"),
            "mvp": mvp, "fraud": fraud, "ghost": ghost if ghost["is_ghost"] else None,
            "carry": carry, "top_performer": top, "worst_performer": worst, "all_players": match_players,
        }
