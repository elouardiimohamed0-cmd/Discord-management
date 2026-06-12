"""
DARIJA ENGINE v5.0 — Rich Moroccan Darija with natural code-switching
Based on DODa standard + real vocabulary dataset.

STRATEGY: 
1. No text transformation/cleaning (that was destroying output)
2. Rich system prompt with vocabulary examples
3. Natural code-switching: Darija + French + English (how Moroccans actually talk)
4. Validation only — if AI fails, use curated fallback

DODa Transliteration:
  3 = ع (ayn)     7 = ح (ha)      9 = ق (qaf)
  8 = ه (ha)      5 = خ (kha)     ch = ش (shin)
  gh = غ (ghayn)  kh = خ (kha)    ou = و (waw)
"""

import random
from typing import Dict, List

# ── RICH DARIJA VOCABULARY (from dataset + common football terms) ────────────

# Football-specific Darija vocabulary
FOOTBALL_VOCAB = {
    # Match/results
    "win": ["rbe7", "rbe7na", "fouz", "ghaleb", "khsar l3adou"],
    "lose": ["khsar", "khsarna", "mghloub", "t7ashsham", "3iyet"],
    "draw": ["t3adl", "t3adlo", "noss noss", "safi 3iyet"],
    "match": ["lmatch", "ljou", "lw9t", "l9it3a"],
    "goal": ["lgoal", "lbut", "l7ejja", "sjel"],
    "shot": ["tir", "driba", "t9adda", "khdem"],
    "pass": ["pass", "l3ab", "wsel", "lfer9a"],
    "defense": ["ldefense", "l7erass", "lback", "d3if"],
    "attack": ["lattack", "l7jouma", "l9odam", "mokadem"],
    "team": ["lfr9", "l'équipe", "team", "s7ab"],

    # Player qualities
    "good": ["mzyan", "zwin", "9awi", "me3qoul", "kaykhdem"],
    "bad": ["khayb", "d3if", "ma3endou walo", "mashi 3adi", "t9awed"],
    "amazing": ["bzf", "3ez", "wa3er", "ma3ndch mtsl", "b7al chi 7wayed"],
    "terrible": ["walo men walo", "klach", "3ib", "7chouma", "ma jayinch"],

    # Reactions
    "wow": ["wach hadchi bssah", "walo men walo", "ma3ndch shi", "fin kan"],
    "laugh": ["hahaha", "😂", "💀", "wallah", "ya3ni"],
    "angry": ["sir t9awed", "diri 3qlek", "ma3ndch 3a9l", "t7ashsham"],
    "happy": ["yallah", "dima dima", "wakha", "safi", "z3ma"],

    # Common phrases
    "what": ["wach", "chkon", "chno", "fach", "3lash"],
    "how": ["kifach", "b7al", "ch7al", "kif", "ki"],
    "why": ["3lash", "7it", "b7al", "ya3ni"],
    "where": ["fin", "fyn", "mnin", "fblast"],
    "when": ["fach", "wqt", "daba", "ghadi"],

    # Time
    "now": ["daba", "daba daba", "tawa", "deja"],
    "later": ["ghadi", "m3a l3chiya", "b3d", "mn b3d"],
    "never": ["abadan", "walo", "ma3ndch", "blati"],
    "always": ["dima", "kolla merra", "merra", "bzzaf"],

    # Quantities
    "very": ["bzf", "bzzaf", "wa3er", "ma3ndch mtsl", "3ez"],
    "little": ["chwiya", "chwaya", "walo", "ma3ndch", "shwiya"],
    "many": ["bzzaf", "bzf", "kolla", "3la 7sab", "b7al"],
    "none": ["walo", "ma3ndch", "blati", "klach", "hatta chi wahd"],

    # People
    "friend": ["s7abi", "s7ab", "khouya", "3aziz", "l3ziz"],
    "enemy": ["l3adou", "3adou", "l5er", "lfr9 l5er", "opponent"],
    "player": ["l3ab", "player", "joueur", "l3ib", "l3ab"],
    "keeper": ["lkeeper", "l7aris", "goalkeeper", "lgoal", "l7ejja"],

    # Actions
    "play": ["l3eb", "kayl3eb", "kaykhdem", "dar", "khdem"],
    "score": ["sjel", "darb", "khdem", "rbe7", "fouz"],
    "miss": ["mased", "mamched", "khayb", "walo", "ma3ndch"],
    "run": ["jra", "kayjri", "mcha", "t7arak", "dour"],
    "stop": ["w9ef", "safi", "bda", "walo", "3iyet"],
}

# Common Darija expressions (natural code-switching)
COMMON_EXPRESSIONS = [
    "walo men walo",
    "safi 3iyet",
    "daba walo",
    "ghadi nchoufou",
    "b7al hdiya",
    "kif kif",
    "noss noss",
    "dima dima",
    "z3ma",
    "ya3ni",
    "wallah",
    "wakha",
    "safi",
    "yallah",
    "fin kan",
    "3adl hadchi",
    "ma3ndch shi",
    "sir t9awed",
    "diri 3qlek",
    "t7ashsham",
    "kaykhdem",
    "mashi 3adi",
    "9awi bzf",
    "khayb bzf",
    "mzyan bzf",
    "zwin bzf",
    "d3if bzf",
    "3ib w 7chouma",
    "ma3endna walo",
    "7na l'équipe dial champions... z3ma! 😂",
    "ghadi n9lb fihom",
    "mochkil 3lihom",
    "kolchi ghadi ye3raf men hna",
    "bghaw ydirou fina",
    "ma3ndhomch shi y3mlo",
    "7na f mo3ad",
    "fin kan had r7al",
    "binatna wbinatkom",
    "daba shofou",
    "had l-équipe tajri 3liha lklab 😂",
    "hicham rah",
    "yallah safi twali",
    "ta9ta9na bzzaf",
    "makentch f mostawakom",
    "safi t7arrak",
    "kanb9aw nchoufou f film",
    "mashi normal hadchi",
    "wach ghadi n9oul lik",
    "s7bi wallah",
    "3la khater",
    "rah daba",
    "had sh7al dreb 😭",
    "klach hta klach",
    "mochkil fih",
    "ra7 y3iyer 3lih",
    "diri shi 7aja",
    "kanbghiw nshofou",
    "ta9awwam",
    "makaynch had lkalam",
    "dir lbal",
    "lmatch kan ghawi ya s7abi",
    "7na mato walo 💀",
    "golha f wajhek",
    "bghaw ydiro fina had l-7maq",
    "safi 3iyet mn had l7al",
    "ta9ta9 b7al ma3ndkch 3a9l",
    "lhwa lhwa bzzaf",
    "ta9ta9 o tbat",
]

# ── FALLBACK TEMPLATES (curated, natural Darija + code-switching) ────────────

FALLBACKS = {
    "win": [
        "🔥 **Rbe7na ya s7abi!** L'équipe darat match mzyan bzf, l3adou ma 9derch y3ml walo! **Rachad** 9awi bzf!",
        "🏆 Walo men walo! Rbe7na w l3adou ma 9derch y3ml walo! Dima dima Rachad L3ERGONI!",
        "💪 Dominant match! Kay7kmou f terrain, kaydirou chi 7wayed! Golha f wajhoum! 🔥",
        "🟢 Rbe7 3la 7sab! Lmatch kan ghawi, kolchi kaykhdem bzzaf! Safi twali!",
        "🔥 Wach hadchi bssah? Rbe7na b7al hdiya! L'équipe 9awya ya s7abi! 💪",
    ],
    "lose": [
        "💀 **Khsarna ya s7abi...** Safi 3iyet mn had l7al. Defense kaytferrej gha, walo men walo!",
        "😭 Walo men walo! L3adou dar fina chi 7aja w 7na naymin! 3ib w 7chouma!",
        "🔴 Khsar 3la 7sab! Team d3ifa, ma3endna walo! Fin kan had r7al? 💀",
        "💀 Lkeeper ma7tajch ydefend — nti kat3tih lball b rask! Safi 3iyet!",
        "🔥 Ma3ndhomch shi y3mlo kontra 7na... z3ma! 😂 Khsarna walo men walo!",
    ],
    "draw": [
        "🟡 **T3adl...** Safi 3iyet, match khayb bzf! Midfield gha pass pass bla result!",
        "😑 Walo men walo, ma3ndna walo f had match! B7al ma katl3b m3a s7abek!",
        "🟡 Noss noss... Ma jayinch hadchi! Ghadi nchoufou chno ghadi yw9e3!",
    ],
    "roast": [
        "🔥 Fin kan **{player}**? Kaydour f terrain b7al tourist! Goal = mission impossible walo men walo! 💀",
        "💀 **{player}** ma3ndou walo! Lkeeper ghadi ysmem waldo 3la smitek! Sir t9awed!",
        "😂 **{player}** kaydribble o kaydribble walakin l-goal = walo men walo! 3ib w 7chouma!",
        "🔥 **{player}** t9awed 3la had niveau... Sir t3llm lkora qbel matji! 💀",
        "💀 **{player}** kayt7errek b7al robot! Ma3ndch l3a9l f had match!",
    ],
    "praise": [
        "🔥 **{player}** dar match mzyan! Player kaykhdem, mashi b7al l3ab! 9awi bzf!",
        "👏 **{player}** rating zwin! Wach hadchi bssah? Dar chi 7wayed!",
        "🌟 **{player}** kayferrej f l3ab! Juj goals dyalo ma jayinch b7al hdiya!",
        "🔥 **{player}** kay7km f terrain! Mashi 3adi, player 3ez! 💪",
    ],
    "hype": [
        "🔥 **RACHAD L3ERGONI!** Ghadi nrbe7houm walo men walo! 7na 7na walo ghayrina! 💪",
        "💪 Ghadi nkhssrouhoum! Team 9awya, mashi 3adiya! Yallah! 🔥",
        "🏆 Dima dima! Rachad L3ERGONI ghadi t7km f lmatch! Golha f wajhoum!",
        "🔥 Ma3ndhomch shi y3mlo kontra 7na! Ghadi ndouzou 3lihoum! 💪",
    ],
    "general": [
        "🤔 Daba walo, ghadi nchoufou chno ghadi yw9e3!",
        "⚽ Rachad L3ERGONI f lmatch! Yallah safi!",
        "🏆 L'équipe dial champions... z3ma! 😂",
        "🔥 Walo men walo! Safi 3iyet mn had l7al!",
        "💪 7na mato walo! Ghadi nrbe7houm inshallah!",
    ],
}


def validate_darija(text: str) -> bool:
    """Check if text looks like valid Darija (with natural code-switching)."""
    if not text or len(text) < 10:
        return False

    # Check for Darija markers (relaxed — allows English/French mixed in)
    darija_markers = [
        'daba', 'ghadi', 'walo', 's7abi', 'safi', '3iyet', 'b7al', 'mashi', 'wach',
        'fin', 'kan', 'rbe7', 'khsar', '9awi', 'd3if', 'zwin', 'khayb', 'mzyan',
        '3la', '7it', 'walakin', 'dakchi', 'nti', '7na', 'ntoma', 'bzf', 'hta',
        'dyal', 'fih', '3lih', '3end', 'kay', 'kat', 'dar', 'l3eb', 'jou', 'match',
        'lgoal', 'lkeeper', 'ldefense', 'lmidfield', 'lattack', 'lteam', 'léquipe',
        'rachad', 'l3ergoni', 'pro clubs', 'fc 26', 'ya', 's7ab', '3ziz',
        '3nd', '7na', '9bl', '5ayb', 'ch7al', 'bghit', 'khdem',
        'm3ak', 'm3a', '3lik', '3la', '7it', '7wayed', '7ssen', '7sab',
        'z3ma', 'ya3ni', 'wallah', 'wakha', 'dima', 'noss', 't9awed',
        't7ashsham', 'sir', 'diri', '3qlek', 'ma3ndch', '3a9l',
        'ghadi', 'daba', 'safi', 'walo', 'bzf', 'mzyan', 'khayb',
        'rbe7', 'khsar', 't3adl', 'fouz', '3ib', '7chouma',
    ]

    text_lower = text.lower()
    marker_count = sum(1 for m in darija_markers if m in text_lower)

    # Also check for natural code-switching (English/French words)
    code_switch_markers = [
        'match', 'team', 'player', 'goal', 'rating', 'win', 'loss', 'draw',
        'équipe', 'niveau', 'performance', 'résultat', 'tirs', 'faute',
        'formation', 'tactique', 'défense', 'attaque', 'milieu',
    ]
    code_count = sum(1 for m in code_switch_markers if m in text_lower)

    # Has emoji?
    has_emoji = any(c in text for c in '🔥💀😂👏🟢🟡🔴⚽🎯⭐🏆📊🗓️⚔️🎮💥🛡️😈😱🚨📰🤔🤷🙏💪🎉😅😆🤣😤')

    # Valid if: has Darija markers OR code-switching + emoji
    return marker_count >= 2 or (code_count >= 1 and has_emoji)


def get_fallback(situation: str, **kwargs) -> str:
    """Get curated fallback with natural Darija + code-switching."""
    templates = FALLBACKS.get(situation, FALLBACKS["general"])
    selected = random.choice(templates)
    try:
        return selected.format(**kwargs)
    except KeyError:
        return selected


# ── ASYNC WRAPPER — Validation + fallback, NO text transformation ────────────

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
