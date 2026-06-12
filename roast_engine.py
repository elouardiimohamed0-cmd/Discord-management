"""
Roast Engine v2.0 — Position-aware stat roasts with Darija output.
Inspired by AllCalculatedRoast — adds tiered severity, combo roasts, 
special events, and praise engine.

All output is in Moroccan Darija (street football Twitter style).
"""
import random
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────

PASS_THRESHOLD = 70       # % — all positions
CONVERSION_THRESHOLD = 40  # % — anyone with 3+ shots
TACKLE_THRESHOLD = 25      # % — mids/defenders, min 5 attempts
INT_THRESHOLD = 1          # count — mids/defenders
LOW_PASS_MAX_ATT = 7      # attempted passes — below this triggers caution
LOW_PASS_MAX_PCT = 90     # accuracy threshold for low pass caution

# ── Position bucketing ────────────────────────────────────────────────────────

_ATTACKER_KEYWORDS = {"attacking", "finisher", "forward", "striker", "winger", "second striker", "st", "cf", "lw", "rw"}
_MIDFIELDER_KEYWORDS = {"midfield", "creator", "magician", "recycler", "playmaker", "box to box", "defensive mid", "cdm", "cam", "cm"}
_DEFENDER_KEYWORDS = {"defend", "defensive boss", "sweeper", "centre back", "fullback", "wing back", "keeper", "goalkeeper", "cb", "lb", "rb"}

def _position_bucket(position: str) -> str:
    """Returns 'attacker', 'midfielder', 'defender', or 'unknown'."""
    p = position.lower()
    if any(k in p for k in _ATTACKER_KEYWORDS):
        return "attacker"
    if any(k in p for k in _MIDFIELDER_KEYWORDS):
        return "midfielder"
    if any(k in p for k in _DEFENDER_KEYWORDS):
        return "defender"
    return "unknown"

# ── Player Registry (customize with your squad) ───────────────────────────────
# Maps in-game name -> {discord_id, club, roasts dict}
# Add your players here!

PLAYER_REGISTRY: Dict[str, Dict] = {}

# ── Darija Roast Pools (per roast type) ─────────────────────────────────────

_PASSING_ROASTS = [
    "{pct}% passing. Had lpass ma wselch l7ed, walo men walo 😂",
    "{pct}% accuracy — kifach katpassi l3adou? b7al hdiya walakin! 💀",
    "Passing dial {pct}% — lball kayt7errek b7al robot, nti ma 3endekch l3a9l 😂",
    "{pct}% — kol pass katwsel l3adou. Service client dial lfr9 l5er! 🔥",
    "{pct}% passing. L3adou ma7tajch ypressik — nti kat3tihom lball b rask! 💀",
    "{pct}% — b7al ma katl3b m3a s7abek f WhatsApp, mashi f match! 😂",
    "Passing {pct}% — hadchi ma jayinch, safi 3iyet mn had l7al! 🔥",
    "{pct}% — l3adou kaychker fik, kat3tihom lball kolla merra! 💀",
]

_CONVERSION_ROASTS = [
    "{shots} shots, {goals} goals — {pct}% conversion. Lgoal kayt7errek b7al mission impossible! 💀",
    "{shots} attempts, {goals} goals. Lkeeper ma7tajch ydefend — nti kat3tih lball! 😂",
    "{pct}% conversion — lcrossbar katbghi walo! 🔥",
    "{shots} shots, {goals} goals. Had l3ab ma kaynch f had niveau! 💀",
    "{pct}% — lgoal kayn w nti katdour 3lih b7al tourist! 😂",
    "{shots} attempts, {goals} goals. Lkeeper ghadi ysmem waldo 3la smitek! 🔥",
    "{pct}% conversion — lwoodwork kat7s bzzaf mn nta! 💀",
    "{shots} shots, {goals} goals. Fin kan had r7al? Ma3endnach shi y3mlo! 😂",
]

_TACKLING_ROASTS = [
    "{pct}% tackle success — kat7eb lball walakin lball ma kaybghikch! 💀",
    "{made} from {attempted} tackles. L3adou kaymchi 3lik b7al ma nti ma kaynch! 😂",
    "{pct}% — tackle attempts b7al ma katdour f terrain b7al tourist! 🔥",
    "{attempted} tackles, {made} wins. L3adou kayferrej fik gha! 💀",
    "{pct}% tackle success — lground kat7s bzzaf mn nta! 😂",
    "{made} from {attempted} — ldefense ma kaynch, gha kaytferrej! 🔥",
    "{pct}% — b7al ma3ndkch shi y3mlo, sir t9awed! 💀",
    "{attempted} tackles, {made} won. L3adou kaybghi yl3b m3ak! 😂",
]

_INTERCEPTION_ROASTS = [
    "{count} interceptions — l3adou kaymchi 3lik b7al revolving door! 💀",
    "{count} — ma9ra lmatch walo, gha kaytferrej! 😂",
    "{count} interceptions. Lmidfield ma kaynch f had match! 🔥",
    "{count} — lball kaymchi 3lik b7al ma nti ma kaynch! 💀",
    "{count} interceptions. L3adou ma7tajch ypassik — nti ma kaynch! 😂",
    "{count} — lgame reading dial nta = zero! 💀",
    "{count} interceptions. Lposition ma3ndkch, lball ma3ndkch, walo! 🔥",
    "{count} — b7al ma katl3b f match wahdak, mashi m3a fr9! 😂",
]

_LOW_PASS_ROASTS = [
    "{pass_att} passes — lteam l3b 10v11 7it nti ma 3endekch lball! 💀",
    "{pass_att} passes — lball dyal s7abek, mashi dyalek b7al hdiya! 😂",
    "{pass_att} — ma3ndkch lball, ma3ndkch lpass, ma3ndkch walo! 🔥",
    "{pass_att} passes. Lcoach dar system, nti dart system dyalek! 💀",
    "{pass_att} — lteam kaytsnawek, nti ma kaynch! 😂",
]

# ── Combo Roasts (extreme stats) ────────────────────────────────────────────

_COMBO_ROASTS = {
    "finishing_collapse": [
        "{shots} shots, {goals} goals — lkeeper ghadi ysmem waldo 3la smitek! 💀",
        "{shots} attempts, {pct}% conversion — ma3ndkch lfinish, ma3ndkch l7al! 🔥",
        "{shots} shots — lnet dar missing person report 3lik! 😂",
        "{shots} shots, {pct}% — lcrossbar bgha y3rf chno bghiti! 💀",
    ],
    "ghost": [
        "Full match played — walo men walo, gha kaytferrej! 💀",
        "Nti f terrain? Allegedly! 😂",
        "Invisible performance — lball ma kaybghikch! 🔥",
        "Technically present, practically absent — hadchi ma jayinch! 💀",
    ],
    "selfish": [
        "{shots} shots, 0 assists — s7abek ma kaynch f l7sab dial nta! 💀",
        "Hero ball attempted, team play declined — {shots} shots! 😂",
        "{shots} attempts, 0 assists — kol touch = shot, walo m3a s7abek! 🔥",
        "Every touch became a shot — lconcept dial pass dar b7al hdiya! 💀",
    ],
}

# ── Extra lines & Special Events ────────────────────────────────────────────

_EXTRA_LINES = [
    "Lpanel kayt7ess!",
    "Ghadi nmchiw!",
    "Questions ghadi yts2alou!",
    "Hadchi ghadi ytreview!",
    "Lcoaching staff 3rfou!",
    "Training dar booked!",
    "Walo men walo!",
]

_SPECIAL_EVENTS = [
    "📺 VAR Review\n\nMor review dial replay...\nAyeh, kan khayb b7al ma kan!\n\n",
    "🎙️ Breaking news dial studio:\n\n",
    "📋 Official match report notation:\n\n",
    "⚠️ Flagged for review:\n\n",
]

# ── Praise Engine ───────────────────────────────────────────────────────────

PRAISE_PASS_THRESHOLD = 88
PRAISE_CONV_THRESHOLD = 60
PRAISE_TACKLE_THRESHOLD = 70
PRAISE_INT_THRESHOLD = 5
PRAISE_RATING_THRESHOLD = 9.0
PRAISE_ASSIST_THRESHOLD = 3

_PASSING_PRAISES = [
    "{pct}% passing — lball kaymchi b7al ma kaynch gha nta! 🔥",
    "{pct}% accuracy — distribution zwin bzf, mzyan! 👏",
    "{pct}% — lteam l3b 3la 7sab dial nta, player kaykhdem! 🔥",
    "Passing {pct}% — lvision kayn, lexecution kayn, walo men walo! 👏",
]

_CONVERSION_PRAISES = [
    "{goals} from {shots} — {pct}% conversion, clinical! 🔥",
    "{pct}% conversion — lgoal kayn w nti katwsel b7al hdiya! 👏",
    "{goals} goals from {shots} shots — finisher 3ez! 🔥",
    "{pct}% — lkeeper ma 9derch y3ml walo, nti 9awi bzf! 👏",
]

_TACKLING_PRAISES = [
    "{pct}% tackle success — ldefense kayn, l3adou ma 9derch y3ml walo! 🔥",
    "{made} from {attempted} tackles — brick wall! 👏",
    "{pct}% — l3adou kaymchi 3lik b7al ma nti 9awi! 🔥",
    "{made} tackles won — ldefense dial nta = mission accomplished! 👏",
]

_INTERCEPTION_PRAISES = [
    "{count} interceptions — lgame reading dial nta = next level! 🔥",
    "{count} — l3adou ma 9derch ypassik, nti f blast kolla merra! 👏",
    "{count} interceptions — lmidfield kayn b7al ma kaynch gha nta! 🔥",
    "{count} — lball kayji w nti katwsel, walo men walo! 👏",
]

_RATING_PRAISES = [
    "{rating} rating — unplayable tonight, l3adou ma 9derch! 🔥",
    "{rating} — man of the match, no discussion! 👏",
    "{rating} — lplayer dial lmatch, walo men walo! 🔥",
    "{rating} — on another level, l3adou kayt7ess! 👏",
]

_ASSIST_PRAISES = [
    "{assists} assists — playmaker dial lmatch! 🔥",
    "{assists} — lteam l3b 3la 7sab dial nta, vision zwin! 👏",
    "{assists} assists — kol assist = goal, walo men walo! 🔥",
    "{assists} — lpass dial nta kaywsel b7al hdiya! 👏",
]

_LOW_PASS_CAUTIONS = [
    "Walakin {pass_att} passes — be brave, get on the ball more! 💀",
    "{pass_att} passes — lteam needs you involved, ma tkhafch! 😂",
    "Be bold — {pass_att} passes ma kaynch enough, demand the ball! 🔥",
]

# ── Silent Treatment ─────────────────────────────────────────────────────────

_SILENT_TREATMENT = [
    "🎙️ Lpanel bgha silence — had performance ma ghadi ndiscussionouh!",
    "🎙️ Lanalysts chafou lfootage w mchaw — walo men walo!",
    "🎙️ Studio walo — lproducers ma3endhomch shi y3mlo!",
    "🎙️ Lpanel t7essaw — had match ma wqe3ch!",
    "🎙️ Lpundits mchaw — lmatch ma kaynch entertainment!",
    "🎙️ Highlight reel reviewed — ma kaynch highlights!",
    "🎙️ Gary Neville tferr lmicrophone — Jamie Carragher kaytferrej f l7it!",
]

# ── Public Interface ─────────────────────────────────────────────────────────

def get_roast_victims(players: List[Dict]) -> List[Dict]:
    """Check each player's stats against position-aware thresholds."""
    victims = []
    seen = set()

    for p in players:
        name = p.get("name", "")
        position = p.get("position", "")
        bucket = _position_bucket(position)

        # Pass accuracy (all positions)
        attempted = p.get("passes_attempted", 0)
        completed = p.get("passes_completed", 0)
        if attempted >= 5:
            pass_pct = round(completed / attempted * 100)
            if pass_pct < PASS_THRESHOLD and (name, "passing") not in seen:
                victims.append({**p, "roast_type": "passing", "pass_pct": pass_pct})
                seen.add((name, "passing"))

        # Conversion rate — anyone with enough shots
        shots = p.get("shots", 0)
        goals = p.get("goals", 0)
        if shots >= 3:
            conv_pct = round(goals / shots * 100)
            if conv_pct < CONVERSION_THRESHOLD and (name, "conversion") not in seen:
                victims.append({**p, "roast_type": "conversion",
                               "conv_pct": conv_pct, "shots": shots, "goals": goals})
                seen.add((name, "conversion"))

        # Midfielder / Defender: tackle success
        if bucket in ("midfielder", "defender", "unknown"):
            tkl_made = p.get("tackles", 0)
            tkl_att = p.get("tackles_attempted", 0)
            if tkl_att >= 5:
                tkl_pct = round(tkl_made / tkl_att * 100)
                if tkl_pct < TACKLE_THRESHOLD and (name, "tackling") not in seen:
                    victims.append({**p, "roast_type": "tackling",
                                   "tkl_pct": tkl_pct, "tkl_made": tkl_made, "tkl_att": tkl_att})
                    seen.add((name, "tackling"))

        # Midfielder / Defender: interceptions
        if bucket in ("midfielder", "defender"):
            ints = p.get("interceptions", 0)
            if ints < INT_THRESHOLD and (name, "interceptions") not in seen:
                victims.append({**p, "roast_type": "interceptions", "int_count": ints})
                seen.add((name, "interceptions"))

    return victims


def get_praise_candidates(players: List[Dict]) -> List[Dict]:
    """Return players who deserve praise based on their stats."""
    praised = []
    for p in players:
        reasons = []
        att = p.get("passes_attempted", 0)
        comp = p.get("passes_completed", 0)
        shots = p.get("shots", 0)
        goals = p.get("goals", 0)
        tkl_att = p.get("tackles_attempted", 0)
        tkl_made = p.get("tackles", 0)
        ints = p.get("interceptions", 0)
        rating = p.get("rating", 0.0)
        assists = p.get("assists", 0)

        if att >= 5:
            pct = round(comp / att * 100)
            if pct >= PRAISE_PASS_THRESHOLD:
                reasons.append({"type": "passing", "pct": pct})

        if shots >= 3:
            conv = round(goals / shots * 100)
            if conv >= PRAISE_CONV_THRESHOLD:
                reasons.append({"type": "conversion", "conv_pct": conv, "shots": shots, "goals": goals})

        if tkl_att >= 5:
            tpct = round(tkl_made / tkl_att * 100)
            if tpct >= PRAISE_TACKLE_THRESHOLD:
                reasons.append({"type": "tackling", "tkl_pct": tpct, "tkl_made": tkl_made, "tkl_att": tkl_att})

        if ints >= PRAISE_INT_THRESHOLD:
            reasons.append({"type": "interceptions", "count": ints})

        if rating >= PRAISE_RATING_THRESHOLD:
            reasons.append({"type": "rating", "rating": rating})

        if assists >= PRAISE_ASSIST_THRESHOLD:
            reasons.append({"type": "assists", "assists": assists})

        if reasons:
            caution = None
            if att >= 3 and att < LOW_PASS_MAX_ATT:
                caution = {"type": "low_pass_caution", "pass_att": att}
            praised.append({**p, "praise_reasons": reasons, "caution": caution})

    return praised


def build_roast_text(victims: List[Dict], match_info: Dict,
                     all_players: List[Dict] = None) -> str:
    """Build Darija roast text for all victims."""
    from collections import defaultdict

    roasts_by_player = defaultdict(list)
    for v in victims:
        roasts_by_player[v["name"]].append(v)

    praise_source = all_players if all_players else list({v["name"]: v for v in victims}.values())
    praised_by_player = defaultdict(list)
    for p in get_praise_candidates(praise_source):
        for reason in p["praise_reasons"]:
            praised_by_player[p["name"]].append({**p, **reason})

    all_names = set(roasts_by_player.keys()) | set(praised_by_player.keys())
    if not all_names:
        return ""

    lines = ["📺 **Pundit Verdict — Darija Style**", ""]
    score_opp = f"{match_info.get('our_goals','?')}-{match_info.get('opp_goals','?')} vs {match_info.get('opp_name','?')}"

    for name in all_names:
        lines.append(f"**{name}**")
        lines.append("")

        praises = praised_by_player.get(name, [])
        if praises:
            lines.append("✅ **The Good:**")
            for p in praises:
                rtype = p.get("type", "")
                praise = _pick_praise(rtype, p)
                lines.append(f"  {praise}")
            lines.append("")

        roasts = roasts_by_player.get(name, [])
        if roasts:
            if praises:
                lines.append("💀 **However...**")
            for v in roasts:
                rtype = v["roast_type"]
                roast = _pick_roast(rtype, v)
                lines.append(f"  {roast}")
            lines.append("")

    lines.append(f"_Score: {score_opp}_")
    return "\n".join(lines)


def _pick_roast(rtype: str, v: Dict) -> str:
    shots = v.get("shots", 0)
    goals = v.get("goals", 0)
    assists = v.get("assists", 0)
    pct = v.get("pass_pct", v.get("conv_pct", v.get("tkl_pct", 0)))
    made = v.get("tkl_made", 0)
    att = v.get("tkl_att", 0)
    count = v.get("int_count", 0)
    pass_att = v.get("pass_att", 0)
    remaining = max(att - made, 0) if att > 0 else 0

    # Combo triggers
    template = None
    if rtype == "conversion" and shots >= 6 and pct < 20:
        template = random.choice(_COMBO_ROASTS["finishing_collapse"])
    elif shots == 0 and pass_att > 0 and pass_att < 6 and count == 0:
        template = random.choice(_COMBO_ROASTS["ghost"])
    elif rtype == "conversion" and shots >= 5 and assists == 0:
        template = random.choice(_COMBO_ROASTS["selfish"])

    # Normal selection
    if template is None:
        if rtype == "passing":
            pool = _PASSING_ROASTS
        elif rtype == "conversion":
            pool = _CONVERSION_ROASTS
        elif rtype == "tackling":
            pool = _TACKLING_ROASTS
        elif rtype == "interceptions":
            pool = _INTERCEPTION_ROASTS
        elif rtype == "low_passes":
            pool = _LOW_PASS_ROASTS
        else:
            pool = _PASSING_ROASTS

        tier = _get_tier(rtype, pct)
        n = len(pool)
        if tier == "nuclear":
            template = random.choice(pool[max(0, n - max(n // 3, 1)):])
        elif tier == "heavy":
            template = random.choice(pool[n // 3: max(n // 3 + 1, 2 * n // 3)])
        else:
            template = random.choice(pool[:max(n // 2, 1)])

    roast = template.format(
        name=v.get("name", ""), pct=pct, shots=shots, goals=goals, assists=assists,
        made=made, attempted=att, count=count,
        pass_att=pass_att, remaining=remaining,
    )

    # Rare special event intro (10% chance)
    if random.random() < 0.10:
        roast = random.choice(_SPECIAL_EVENTS) + roast

    # Occasional extra kicker (20% chance)
    if random.random() < 0.20:
        roast += "\n\n_" + random.choice(_EXTRA_LINES) + "_"

    return roast


def _pick_praise(rtype: str, v: Dict) -> str:
    pct = v.get("pct", v.get("conv_pct", v.get("tkl_pct", 0)))
    shots = v.get("shots", 0)
    goals = v.get("goals", 0)
    made = v.get("tkl_made", 0)
    att = v.get("tkl_att", 0)
    count = v.get("count", 0)
    rating = v.get("rating", 0.0)
    assists = v.get("assists", 0)

    if rtype == "passing":
        pool = _PASSING_PRAISES
    elif rtype == "conversion":
        pool = _CONVERSION_PRAISES
    elif rtype == "tackling":
        pool = _TACKLING_PRAISES
    elif rtype == "interceptions":
        pool = _INTERCEPTION_PRAISES
    elif rtype == "rating":
        pool = _RATING_PRAISES
    elif rtype == "assists":
        pool = _ASSIST_PRAISES
    else:
        pool = _PASSING_PRAISES

    template = random.choice(pool) if pool else f"{v.get('name','')} had a great {rtype} performance."

    return template.format(
        name=v.get("name", ""), pct=pct, shots=shots, goals=goals,
        made=made, attempted=att, count=count,
        rating=rating, assists=assists,
    )


def _get_tier(rtype: str, pct: int) -> str:
    if rtype == "conversion":
        if pct < 20: return "nuclear"
        if pct < 35: return "heavy"
        return "mild"
    if rtype == "passing":
        if pct < 50: return "nuclear"
        if pct < 62: return "heavy"
        return "mild"
    if rtype == "tackling":
        if pct < 15: return "nuclear"
        if pct < 30: return "heavy"
        return "mild"
    return "mild"


# ── Silent Treatment ─────────────────────────────────────────────────────────

def is_boring_game(players: List[Dict], match_data: Dict) -> bool:
    """Return True if the game qualifies for the silent treatment."""
    if not players:
        return False

    result = match_data.get("result", "")
    if result == "W":
        if all(p.get("rating", 0) < 7.5 for p in players):
            return True

    team_goals = sum(p.get("goals", 0) for p in players)
    if team_goals > 0:
        def _has_standout(p):
            att = p.get("passes_attempted", 0)
            pas_pct = p.get("passes_completed", 0) / max(att, 1) * 100 if att >= 10 else 0
            return (
                p.get("goals", 0) > 0
                or p.get("assists", 0) > 0
                or p.get("interceptions", 0) >= 2
                or pas_pct >= 80
                or p.get("rating", 0) >= 8.0
            )
        if not any(_has_standout(p) for p in players):
            return True

    return False


def build_silent_treatment(match_data: Dict) -> str:
    """Build the silent treatment for boring games."""
    score = f"{match_data.get('our_goals','?')}-{match_data.get('opp_goals','?')}"
    opponent = match_data.get("opp_name", "Unknown")
    line = random.choice(_SILENT_TREATMENT)
    return f"📺 **Pundit Verdict**\n\n{line}\n\n_Score: {score} vs {opponent}_"


# ── Fun Roast (lifetime stats) ───────────────────────────────────────────────

def get_fun_roast(player_name: str, stats: Dict) -> str:
    """Generate a fun roast based on lifetime stats."""
    matches = stats.get("matches", 0)
    goals = stats.get("goals", 0)
    assists = stats.get("assists", 0)
    rating_total = stats.get("rating_total", 0)
    avg_rating = round(rating_total / max(matches, 1), 2)

    roasts = [
        f"{goals} goals f {matches} matchs — {avg_rating}/10 average. Hadchi ma jayinch! 💀",
        f"{matches} matchs, {goals} goals, {assists} assists. Lgoal drought mashi drought — desert! 🔥",
        f"Average rating {avg_rating} f {matches} matchs. Lalgorithm dial EA 3rf walo! 😂",
        f"{goals} goals f {matches} games. Lkeeper ghadi ysmem waldo 3la smitek! 💀",
        f"Lifetime: {goals}G {assists}A f {matches} matchs. Consistent — consistently khayb! 🔥",
    ]

    return random.choice(roasts)
