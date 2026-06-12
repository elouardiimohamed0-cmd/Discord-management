"""
DARIJA VALIDATOR v4.0 — No cleaning, just validation.
Based on DODa (Darija Open Dataset) standards:
  3=ع, 7=ح, 9=ق, 8=ه, 5=خ, ch=ش, gh=غ, kh=خ

STRATEGY: Trust the AI. Give it proper DODa examples in the system prompt.
Only validate output. If broken, use curated fallback templates.
"""

import random
from typing import Dict, List

# ── DODa-Standard Darija Examples (for reference, used in prompts) ─────────

DODA_EXAMPLES = {
    "win": [
        "🔥 Rbe7na ya s7abi! L'équipe darat match mzyan bzf, l3adou ma 9derch y3ml walo!",
        "🏆 Walo men walo! Rbe7na w l3adou ma 9derch y3ml walo! **Rachad** 9awi bzf!",
        "💪 Dominant match! Kay7kmou f terrain, kaydirou chi 7wayed! Golha f wajhoum!",
        "🟢 Rbe7 3la 7sab! Lmatch kan ghawi, kolchi kaykhdem bzzaf!",
    ],
    "lose": [
        "💀 Khsarna ya s7abi... Safi 3iyet mn had l7al. Defense gha kaytferrej!",
        "😭 Walo men walo! L3adou dar fina chi 7aja w 7na naymin! 3ib w 7chouma!",
        "🔴 Khsar 3la 7sab! Team d3ifa, ma3endna walo! Fin kan had r7al?",
        "💀 Lkeeper ma7tajch ydefend — nti kat3tih lball b rask! Safi 3iyet!",
    ],
    "draw": [
        "🟡 T3adl... Safi 3iyet, match khayb bzf! Midfield gha pass pass bla result!",
        "😑 Walo men walo! Ma3ndna walo f had match! B7al ma katl3b m3a s7abek!",
    ],
    "roast": [
        "🔥 Fin kan **{player}**? Kaydour f terrain b7al tourist! Goal = mission impossible!",
        "💀 **{player}** ma3ndou walo! Lkeeper ghadi ysmem waldo 3la smitek!",
        "😂 **{player}** kaydribble o kaydribble walakin l-goal = walo men walo!",
        "🔥 **{player}** t9awed 3la had niveau... Sir t3llm lkora qbel matji!",
    ],
    "praise": [
        "🔥 **{player}** dar match mzyan! Player kaykhdem, mashi b7al l3ab!",
        "👏 **{player}** rating zwin! Wach hadchi bssah? 9awi bzf!",
        "🌟 **{player}** kayferrej f l3ab! Juj goals dyalo ma jayinch b7al hdiya!",
    ],
    "hype": [
        "🔥 **RACHAD L3ERGONI!** Ghadi nrbe7houm walo men walo! 7na 7na walo ghayrina!",
        "💪 Ghadi nkhssrouhoum! Team 9awya, mashi 3adiya! Yallah!",
    ],
    "general": [
        "🤔 Daba walo, ghadi nchoufou chno ghadi yw9e3!",
        "⚽ Rachad L3ERGONI f lmatch! Yallah safi!",
        "🏆 L'équipe dial champions... z3ma! 😂",
    ],
}


def validate_darija(text: str) -> bool:
    """Check if text contains valid Darija patterns (DODa standard)."""
    if not text or len(text) < 10:
        return False

    # DODa-standard Darija markers
    markers = [
        'daba', 'ghadi', 'walo', 's7abi', 'safi', '3iyet', 'b7al', 'mashi', 'wach',
        'fin', 'kan', 'rbe7', 'khsar', '9awi', 'd3if', 'zwin', 'khayb', 'mzyan',
        '3la', '7it', 'walakin', 'dakchi', 'nti', '7na', 'ntoma', 'bzf', 'hta',
        'dyal', 'fih', '3lih', '3end', 'kay', 'kat', 'dar', 'l3eb', 'jou', 'match',
        'lgoal', 'lkeeper', 'ldefense', 'lmidfield', 'lattack', 'lteam', 'léquipe',
        'rachad', 'l3ergoni', 'pro clubs', 'fc 26', 'ya', 's7abi', 's7ab',
        # DODa standard transliteration
        '3nd', '7na', '9bl', '5ayb', 'ch7al', 'ghadi', 'bghit', 'khdem',
        'm3ak', 'm3a', '3lik', '3la', '7it', '7wayed', '7ssen', '7sab',
    ]

    text_lower = text.lower()
    marker_count = sum(1 for m in markers if m in text_lower)

    # Need at least 2 markers OR some emoji energy
    has_emoji = any(c in text for c in '🔥💀😂👏🟢🟡🔴⚽🎯⭐🏆📊🗓️⚔️🎮💥🛡️😈😱🚨📰🤔🤷🙏💪🎉😅😆🤣😤')

    return marker_count >= 2 or has_emoji


def get_fallback(situation: str, **kwargs) -> str:
    """Get curated fallback template when AI fails."""
    templates = DODA_EXAMPLES.get(situation, DODA_EXAMPLES["general"])
    selected = random.choice(templates)
    try:
        return selected.format(**kwargs)
    except KeyError:
        return selected


# ── ASYNC WRAPPER — NO CLEANING, just validation + fallback ───────────────────

async def ask_and_clean(_ask_func, prompt: str, max_tokens: int = 300, situation: str = "general"):
    """
    Calls AI, validates output, uses fallback if invalid.
    NO text transformation — preserves AI output exactly.
    """
    raw = await _ask_func(prompt, max_tokens)
    if not raw:
        return get_fallback(situation)

    # Just validate — don't clean/transform
    if validate_darija(raw):
        return raw

    # If invalid, use fallback
    return get_fallback(situation)
