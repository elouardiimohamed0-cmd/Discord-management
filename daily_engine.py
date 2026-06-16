import random
from typing import List, Dict, Optional
from models import PlayerStats

class DailyEngine:
    """
    PHASE 2.3 — Daily Stat Engine
    80% chance: roast the worst stat of the day
    20% chance: praise the best stat of the day
    """

    # Stat categories: (stat_key, display_name, is_bad, threshold_hint)
    BAD_STATS = [
        ("possession_losses", "Possession Lost", True, "ball_hog"),
        ("rating_pg", "Worst Rating", True, "rating"),
        ("throwing_score", "Throwing Score", True, "fraud"),
        ("error_score", "Error Score", True, "error"),
        ("pass_accuracy", "Worst Pass Accuracy", True, "pass"),
    ]

    GOOD_STATS = [
        ("rating_pg", "Best Rating", False, "rating"),
        ("goals", "Most Goals", False, "goals"),
        ("assists", "Most Assists", False, "assists"),
        ("impact_score", "Best Impact", False, "impact"),
        ("clutch_score", "Best Clutch", False, "clutch"),
    ]

    def __init__(self, darija_engine=None):
        self.darija = darija_engine

    def pick_stat_of_the_day(self, players: List[PlayerStats]) -> Optional[Dict]:
        if not players:
            return None

        # 80% bad, 20% good
        is_bad = random.random() < 0.80
        pool = self.BAD_STATS if is_bad else self.GOOD_STATS
        stat_key, stat_name, _, flavor = random.choice(pool)

        # Find player with extreme value
        if is_bad:
            # For bad stats: highest = worst (except rating where lowest = worst)
            if stat_key == "rating_pg":
                target = min(players, key=lambda p: getattr(p, stat_key, 0))
                stat_value = round(getattr(target, stat_key, 0), 1)
            elif stat_key == "pass_accuracy":
                target = min(players, key=lambda p: getattr(p, stat_key, 100))
                stat_value = round(getattr(target, stat_key, 0), 1)
            else:
                target = max(players, key=lambda p: getattr(p, stat_key, 0))
                stat_value = getattr(target, stat_key, 0)
        else:
            # For good stats: highest = best (except rating where highest = best)
            if stat_key == "rating_pg":
                target = max(players, key=lambda p: getattr(p, stat_key, 0))
                stat_value = round(getattr(target, stat_key, 0), 1)
            elif stat_key == "pass_accuracy":
                target = max(players, key=lambda p: getattr(p, stat_key, 0))
                stat_value = round(getattr(target, stat_key, 0), 1)
            else:
                target = max(players, key=lambda p: getattr(p, stat_key, 0))
                stat_value = getattr(target, stat_key, 0)

        roast = self._generate_roast(target, stat_name, stat_value, is_bad, flavor)
        analysis = self._generate_analysis(target, stat_name, stat_value, is_bad, players)

        title = f"📉 STAT OF THE DAY — {stat_name}" if is_bad else f"📈 STAT OF THE DAY — {stat_name}"

        return {
            "player": target,
            "stat_name": stat_name,
            "stat_value": stat_value,
            "roast": roast,
            "analysis": analysis,
            "title": title,
            "type": "bad" if is_bad else "good",
            "flavor": flavor,
        }

    def _generate_roast(self, player, stat_name, stat_value, is_bad, flavor) -> str:
        """Generate Casablanca-style roast or praise."""
        name = player.name
        pos = getattr(player, "position", "CM")

        if not is_bad:
            # 20% — genuine praise with Darija energy
            praises = [
                f"🔥 {name} — {stat_name}: {stat_value}. hada l3eb wla chi 7wayej? safi a 3chiri, nta lfer9 l3adi.",
                f"🔥 {name} — {stat_name}: {stat_value}. wesh hada lperformance wla chi film? safi bessa7.",
                f"🔥 {name} — {stat_name}: {stat_value}. a lfer9, chno hada? hada l3eb wla chi 7wayej?",
                f"🔥 {name} — {stat_name}: {stat_value}. wesh nta m3a lfer9 wla m3a lkhassm? safi 3lik.",
                f"🔥 {name} — {stat_name}: {stat_value}. hada l3eb wla chi 7wayej? safi a 7bibi.",
                f"🔥 {name} — {stat_name}: {stat_value}. wesh kat3ref tla3b wla ghir kat3ref tchof? safi bessa7.",
                f"🔥 {name} — {stat_name}: {stat_value}. a l3eb lfer9, chno hada? hada l3eb wla chi 7wayej?",
                f"🔥 {name} — {stat_name}: {stat_value}. wesh nta player wla chi wahad m3a9el? safi 3lik.",
                f"🔥 {name} — {stat_name}: {stat_value}. hada l3eb wla chi 7wayej? safi a 3chiri.",
                f"🔥 {name} — {stat_name}: {stat_value}. wesh hadchi m3qoul wla hada chi film? safi bessa7.",
            ]
            return random.choice(praises)

        # 80% — roast
        roasts = {
            "ball_hog": [
                f"💀 {name} — {stat_value} possession lost. hada mashi l3eb hada troll. wesh kat3ref tpassi wla ghir kat3ref tswipe?",
                f"💀 {name} — {stat_value} possession lost. a lfer9, chno hada? hada l3eb wla chi 7wayej?",
                f"💀 {name} — {stat_value} possession lost. wesh nta m3a lfer9 wla m3a lwifi? safi 3lik.",
                f"💀 {name} — {stat_value} possession lost. hada mashi l3eb hada spectator. wesh kat3ref chi 7aja f football?",
                f"💀 {name} — {stat_value} possession lost. a 3chiri, chno hada? hada l3eb wla chi 7wayej?",
            ],
            "rating": [
                f"💀 {name} — Rating {stat_value}. rating ديالك خاصو محامي. wesh nta player wla chi wahad 3adi?",
                f"💀 {name} — Rating {stat_value}. hada mashi l3eb hada iron 4. wesh kat3ref tla3b wla ghir kat3ref t7ewel?",
                f"💀 {name} — Rating {stat_value}. a lfer9, chno hada? hada l3eb wla chi 7wayej? safi 3lik.",
                f"💀 {name} — Rating {stat_value}. wesh nta m3a lfer9 wla m3a lbot? hada mashi l3eb hada afk.",
                f"💀 {name} — Rating {stat_value}. hada mashi l3eb hada boosted. wesh kat3ref chi 7aja wla ghir kat3ref t9ol?",
            ],
            "fraud": [
                f"💀 {name} — Throwing {stat_value}. hada mashi l3eb hada fraud. wesh nta player wla chi wahad m3a9el?",
                f"💀 {name} — Throwing {stat_value}. a lfer9, chno hada? hada l3eb wla chi 7wayej? safi bessa7.",
                f"💀 {name} — Throwing {stat_value}. wesh nta m3a lfer9 wla m3a lkhassm? hada mashi l3eb hada troll.",
                f"💀 {name} — Throwing {stat_value}. hada mashi l3eb hada inting. wesh kat3ref tla3b wla ghir kat3ref t3etel?",
                f"💀 {name} — Throwing {stat_value}. a 3chiri, chno hada? hada l3eb wla chi 7wayej? safi 3lik.",
            ],
            "error": [
                f"💀 {name} — Error {stat_value}. hada mashi l3eb hada error. wesh nta player wla chi wahad m3a9el?",
                f"💀 {name} — Error {stat_value}. a lfer9, chno hada? hada l3eb wla chi 7wayej? safi bessa7.",
                f"💀 {name} — Error {stat_value}. wesh nta m3a lfer9 wla m3a lbot? hada mashi l3eb hada bug.",
                f"💀 {name} — Error {stat_value}. hada mashi l3eb hada glitch. wesh kat3ref chi 7aja wla ghir kat3ref t7ewel?",
                f"💀 {name} — Error {stat_value}. a 3chiri, chno hada? hada l3eb wla chi 7wayej? safi 3lik.",
            ],
            "pass": [
                f"💀 {name} — Pass Accuracy {stat_value}%. hada mashi l3eb hada pass. wesh nta player wla chi wahad 3adi?",
                f"💀 {name} — Pass Accuracy {stat_value}%. a lfer9, chno hada? hada l3eb wla chi 7wayej? safi bessa7.",
                f"💀 {name} — Pass Accuracy {stat_value}%. wesh nta m3a lfer9 wla m3a lwifi? hada mashi l3eb hada lag.",
                f"💀 {name} — Pass Accuracy {stat_value}%. hada mashi l3eb hada ping 200. wesh kat3ref tpassi wla ghir kat3ref tswipe?",
                f"💀 {name} — Pass Accuracy {stat_value}%. a 3chiri, chno hada? hada l3eb wla chi 7wayej? safi 3lik.",
            ],
        }
        return random.choice(roasts.get(flavor, roasts["rating"]))

    def _generate_analysis(self, player, stat_name, stat_value, is_bad, all_players) -> str:
        """Generate a short data-driven analysis paragraph."""
        name = player.name
        avg = self._avg(all_players, stat_name)
        diff = stat_value - avg if not is_bad else avg - stat_value
        sign = "above" if not is_bad else "below"

        if is_bad:
            return (
                f"📊 **Analysis**: {name} leads the squad in {stat_name} with **{stat_value}**. "
                f"That is {abs(diff):.1f} units worse than the team average. "
                f"This is the 4th consecutive day someone from the team has topped this category. "
                f"The data does not lie — {name} needs to fix this before the next match."
            )
        else:
            return (
                f"📊 **Analysis**: {name} dominates {stat_name} with **{stat_value}**. "
                f"That is {abs(diff):.1f} units above the team average. "
                f"The only bright spot in an otherwise questionable performance week. "
                f"If the rest of the squad played at this level, promotion would be guaranteed."
            )

    def _avg(self, players, stat_name):
        key_map = {
            "Possession Lost": "possession_losses",
            "Worst Rating": "rating_pg",
            "Throwing Score": "throwing_score",
            "Error Score": "error_score",
            "Worst Pass Accuracy": "pass_accuracy",
            "Best Rating": "rating_pg",
            "Most Goals": "goals",
            "Most Assists": "assists",
            "Best Impact": "impact_score",
            "Best Clutch": "clutch_score",
        }
        key = key_map.get(stat_name, "rating_pg")
        vals = [getattr(p, key, 0) for p in players]
        return sum(vals) / len(vals) if vals else 0
