"""
DARIJA CLEANER v1.0 — Post-processes AI output for authentic Moroccan Darija
Usage: from darija import clean_darija, validate_darija, ask_and_clean
"""

import re
import random
from typing import Dict, List, Optional

# ═══════════════════════════════════════════════════════════════════════════════
# FORBIDDEN FORMAL WORDS (Auto-remove from AI output)
# ═══════════════════════════════════════════════════════════════════════════════

FORMAL_ARABIC = [
    'لقد', 'إنه', 'إنها', 'أنه', 'أنها', 'إن', 'أن',
    'جميل', 'جيد', 'سيئ', 'رائع', 'ممتاز', 'فظيع', 'سيء',
    'أداء', 'أداؤه', 'أداءه', 'أدائها',
    'لقد فاز', 'لقد خسر', 'لقد سجل', 'لقد قدم', 'لقد كان', 'لقد لعب',
    'أعتقد', 'أظن', 'أفكر', 'أحسب',
    'بشكل', 'بطريقة', 'بأسلوب',
    'من المهم', 'يجب أن', 'ينبغي', 'لابد', 'من الضروري',
    'في الواقع', 'حقيقة', 'الحقيقة', 'في الحقيقة',
    'بخصوص', 'فيما يتعلق', 'بخصوص',
    'أود أن أشير', 'أود أن', 'أشير إلى',
    'بناءً على', 'استناداً إلى', 'بناء على',
    'من الجدير', 'من المفيد', 'من الأفضل', 'من المستحسن',
    'باختصار', 'في النهاية', 'ختاماً', 'أخيراً', 'في الختام',
    'لذلك', 'وبالتالي', 'علاوة على', 'إضافة إلى',
    'من ناحية', 'من جهة', 'من ناحية أخرى',
    'على سبيل المثال', 'مثلاً', 'كمثال',
    'بمعنى', 'أي', 'حيث', 'الذي', 'التي', 'الذين',
    'وذلك', 'وقد', 'قد', 'كان', 'كانت', 'يكون', 'تكون',
    'يمكن', 'يمكننا', 'يمكنني', 'يجب', 'ينبغي',
    'من الممكن', 'من المفترض', 'من البديهي',
    'لا شك', 'من الواضح', 'من المؤكد', 'بلا شك',
    'تلخيصاً', 'بشكل مختصر', 'مختصراً',
    'بكل بساطة', 'ببساطة', 'بشكل مباشر', 'مباشرة',
    'بصراحة', 'صراحةً', 'بكل صراحة',
    'بكل أمانة', 'بأمانة', 'بكل موضوعية',
    'بكل حيادية', 'بحيادية', 'بكل شفافية',
    'بكل وضوح', 'بوضوح', 'بكل دقة', 'بدقة',
    'بكل تفصيل', 'بتفصيل', 'بكل تفصيل',
]

# French formalisms that sound robotic
FORMAL_FRENCH = [
    'très', 'beaucoup', 'trop', 'maintenant',
    'parce que', 'alors', 'donc', 'mais', 'ou',
    'et', 'avec', 'pour', 'dans', 'sur',
    'de', 'des', 'le', 'la', 'les',
    'un', 'une', 'ce', 'cette', 'mon', 'ton', 'son',
    'notre', 'votre', 'leur', 'je', 'tu', 'il', 'elle',
    'nous', 'vous', 'ils', 'elles',
    'suis', 'es', 'est', 'sommes', 'êtes', 'sont',
    'ai', 'as', 'a', 'avons', 'avez', 'ont',
    'faire', 'fais', 'fait', 'faisons', 'faites', 'font',
    'aller', 'vais', 'vas', 'va', 'allons', 'allez', 'vont',
    'venir', 'viens', 'vient', 'venons', 'venez', 'viennent',
    'pouvoir', 'peux', 'peut', 'pouvons', 'pouvez', 'peuvent',
    'vouloir', 'veux', 'veut', 'voulons', 'voulez', 'veulent',
    'savoir', 'sais', 'sait', 'savons', 'savez', 'savent',
    'penser', 'pense', 'penses', 'pensons', 'pensez', 'pensent',
    'dire', 'dis', 'dit', 'disons', 'dites', 'disent',
    'voir', 'vois', 'voit', 'voyons', 'voyez', 'voient',
    'falloir', 'faut', 'fallait', 'fallu',
    'devoir', 'dois', 'doit', 'devons', 'devez', 'doivent',
]

# ═══════════════════════════════════════════════════════════════════════════════
# DARIJA REPLACEMENTS (Formal -> Natural Darija)
# ═══════════════════════════════════════════════════════════════════════════════

REPLACEMENTS = {
    'لقد': '',
    'إنه': '', 'إنها': '', 'أنه': '', 'أنها': '',
    'جميل': 'zwin', 'جيد': 'mzyan', 'سيئ': 'khayb',
    'أداء': 'performance',
    'لقد فاز': 'rbe7', 'لقد خسر': 'khsar', 'لقد سجل': 'sjel',
    'لقد قدم': 'dar', 'لقد كان': 'kan', 'لقد لعب': 'l3eb',
    'أعتقد': 'kan7sab', 'أظن': 'kan7sab',
    'بشكل': '', 'بطريقة': '',
    'من المهم': 'mohim', 'يجب أن': 'khass', 'ينبغي': 'khass',
    'في الواقع': 'f l7a9i9a', 'حقيقة': '7a9i9a',
    'بخصوص': '3la', 'فيما يتعلق': '3la',
    'أود أن أشير': 'bghit nwerrek', 'بناءً على': '3la 7sab',
    'من الجدير': 'mohim', 'باختصار': 'b mokhtasar',
    'في النهاية': 'f l5itam', 'لذلك': 'dakchi 3la',
    'وبالتالي': 'dakchi 3la', 'علاوة على': 'm3a',
    'من ناحية': 'mn n7iya', 'من جهة': 'mn jiha',
    'إضافة إلى': 'm3a', 'فضلاً عن': 'm3a',
    'على سبيل المثال': 'b7al', 'مثلاً': 'b7al',
    'بمعنى': 'b ma3na', 'أي': 'ya3ni',
    'حيث': 'f blast', 'الذي': 'li', 'التي': 'li',
    'وذلك': 'dakchi', 'وقد': 'w',
    'كان': 'kan', 'كانت': 'kant',
    'يمكن': 'ymken', 'يمكننا': 'ymken lna',
    'يجب': 'khass', 'ينبغي': 'khass',
    'من الضروري': 'mohim', 'من المفيد': 'mzyan',
    'من الأفضل': '7sen', 'من المستحسن': '7sen',
    'très bien': 'mzyan bzf',
    'très mal': 'khayb bzf',
    'beaucoup de': 'bzf',
    'trop de': 'bzf',
    'maintenant': 'daba',
    'parce que': '7it',
    'alors': 'dakchi',
    'donc': 'dakchi',
    'mais': 'walakin',
    'et': 'w',
    'avec': 'm3a',
    'pour': 'b',
    'dans': 'f',
    'sur': '3la',
    'de': 'dyal',
    'des': 'dyal',
    'le': 'had',
    'la': 'had',
    'les': 'had',
    'un': 'wa7ed',
    'une': 'wa7ed',
    'ce': 'had',
    'cette': 'had',
    'mon': 'dyali',
    'ton': 'dyalek',
    'son': 'dyalo',
    'notre': 'dyalna',
    'votre': 'dyalkom',
    'leur': 'dyalhom',
    'je': 'ana',
    'tu': 'nti',
    'il': 'howa',
    'elle': 'hiya',
    'nous': '7na',
    'vous': 'ntoma',
    'ils': 'homa',
    'suis': 'kaykoun',
    'es': 'kaykoun',
    'est': 'kaykoun',
    'sommes': 'kaykounou',
    'êtes': 'kaykounou',
    'sont': 'kaykounou',
    'ai': '3endi',
    'as': '3endek',
    'a': '3endo',
    'avons': '3endna',
    'avez': '3endkom',
    'ont': '3endhom',
    'faire': 'dar',
    'fais': 'kaydir',
    'fait': 'kaydir',
    'faisons': 'kaydiro',
    'faites': 'kaydiro',
    'font': 'kaydiro',
    'aller': 'mchi',
    'vais': 'kaymchi',
    'vas': 'kaymchi',
    'va': 'kaymchi',
    'allons': 'kaymchiw',
    'allez': 'kaymchiw',
    'vont': 'kaymchiw',
    'venir': 'ji',
    'viens': 'kayji',
    'vient': 'kayji',
    'venons': 'kayjiw',
    'venez': 'kayjiw',
    'viennent': 'kayjiw',
    'pouvoir': '9der',
    'peux': 'kay9der',
    'peut': 'kay9der',
    'pouvons': 'kay9derou',
    'pouvez': 'kay9derou',
    'peuvent': 'kay9derou',
    'vouloir': 'bgha',
    'veux': 'kaybghi',
    'veut': 'kaybghi',
    'voulons': 'kaybghiw',
    'voulez': 'kaybghiw',
    'veulent': 'kaybghiw',
    'savoir': '3ref',
    'sais': 'kay3ref',
    'sait': 'kay3ref',
    'savons': 'kay3refou',
    'savez': 'kay3refou',
    'savent': 'kay3refou',
    'penser': '7sab',
    'pense': 'kay7sab',
    'penses': 'kay7sab',
    'pensons': 'kay7sabou',
    'pensez': 'kay7sabou',
    'pensent': 'kay7sabou',
    'dire': 'goul',
    'dis': 'kaygoul',
    'dit': 'kaygoul',
    'disons': 'kaygoulou',
    'dites': 'kaygoulou',
    'disent': 'kaygoulou',
    'voir': 'chouf',
    'vois': 'kaychouf',
    'voit': 'kaychouf',
    'voyons': 'kaychoufou',
    'voyez': 'kaychoufou',
    'voient': 'kaychoufou',
    'falloir': 'khass',
    'faut': 'khass',
    'fallait': 'kan khass',
    'fallu': 'khass',
    'devoir': 'khass',
    'dois': 'khass',
    'doit': 'khass',
    'devons': 'khass',
    'devez': 'khass',
    'doivent': 'khass',
}

# ═══════════════════════════════════════════════════════════════════════════════
# AUTHENTIC DARIJA TEMPLATES (Fallback when AI fails)
# ═══════════════════════════════════════════════════════════════════════════════

TEMPLATES = {
    "win": [
        "**{player}** dar match mzyan 🔥",
        "wach hadchi bssah???",
        "t9awed 3la had niveau",
        "kanb9aw nchoufou f film",
        "mashi normal hadchi",
        "rbe7 {score}!!!",
        "juj goals dyalo ma jayinch b7al hdiya",
        "player kaykhdem, mashi b7al l3ab",
        "rbe7 3la 7sab",
        "dominant match, walo men walo",
        "kay7kmou f terrain",
        "machi 9bel, machi m3a",
        "wach ghadi n9oul lik???",
        "safi, rbe7na, mashi muhim",
    ],
    "lose": [
        "walo men walo 💀",
        "fin kan **{player}**?",
        "kaydour f terrain b7al tourist",
        "goal? mission impossible 💀",
        "yji lmatch ykhtarbo",
        "safi 3iyet",
        "defense kaytferrej gha 💀",
        "midfield gha pass pass bla result",
        "gk kayt7errek b7al robot",
        "khsar 3la 7sab",
        "team d3ifa, mashi 9awya",
        "hadchi ma jayinch",
        "wach hadchi l3ab wala match?",
        "3ib w 7chouma",
        "ma 3endna walo",
        "khayb, khayb bzf",
        "safi, 3iyet, mashi bghina",
    ],
    "draw": [
        "safi 3iyet",
        "3ib w 7chouma",
        "walo men walo",
        "match khayb",
        "midfield gha pass pass bla result",
        "t3adl? ma3ndna walo",
        "safi, 3iyet, mashi bghina",
        "hadchi ma jayinch",
        "wach hadchi l3ab wala match?",
    ],
    "roast": [
        "fin kan **{player}**? kaydour f terrain b7al tourist 💀",
        "**{player}** goal? mission impossible walo men walo",
        "**{player}** t9awed 3la had niveau...",
        "**{player}** kayji lmatch ykhtarbo",
        "**{player}** ma3ndou walo f had match",
        "**{player}** defense kaytferrej gha 💀",
        "**{player}** kayt7errek b7al robot",
        "**{player}** ma jayinch f had niveau",
        "walakin kanbghiwk s7bi 😂",
        "**{player}** 3iyet walo men walo",
        "**{player}** khsar lina match b7al hdiya",
    ],
    "praise": [
        "**{player}** dar match mzyan 🔥",
        "**{player}** player kaykhdem",
        "**{player}** rating {rating}? wach hadchi bssah!",
        "juj goals dyalo ma jayinch b7al hdiya",
        "**{player}** kay7km f terrain",
        "**{player}** 9awi bzf",
        "**{player}** mashi 3adi, player 3ez",
        "**{player}** kayferrej f l3ab",
        "**{player}** sjel goals b7al hdiya",
        "**{player}** assist? 7elwa bzf",
    ],
    "hype": [
        "ghadi nrbe7houm!!!",
        "mashi 3adi had match",
        "rachad l3ergoni ghadi t7km",
        "ghadi nkhssrouhoum",
        "walo men walo ghadi yw9e3",
        "team 9awya, mashi 3adiya",
        "ghadi ndouzou 3lihoum",
        "match ghadi ykoun zwin",
        "rbe7 wala mout",
        "ghadi nferrjou f7alna",
    ],
    "general": [
        "daba walo",
        "ghadi nchoufou",
        "safi, mashi muhim",
        "wach hadchi bssah?",
        "fin kan had r7al?",
        "t9awed 3la had niveau",
        "kanb9aw nchoufou f film",
        "mashi normal hadchi",
        "walo men walo",
        "s7bi, hadchi kayferrej",
        "3iyet walo men walo",
        "daba, ghadi, walo",
        "b7al hdiya, b7al dik",
        "safi, 3iyet, mashi bghina",
        "ma 3endna walo",
        "khayb, khayb bzf",
        "zwin, zwin bzf",
        "mzyan, mzyan bzf",
        "9awi, 9awi bzf",
        "d3if, d3if bzf",
    ],
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def clean_darija(text: str, situation: str = "general") -> str:
    """
    Clean AI-generated text to ensure authentic Moroccan Darija.

    Args:
        text: Raw AI output from Groq/Llama
        situation: "win", "lose", "draw", "roast", "praise", "hype", "general"

    Returns:
        Clean, natural Darija text
    """
    if not text or not text.strip():
        return _fallback_template(situation)

    # Step 1: Remove formal Arabic words
    for word in FORMAL_ARABIC:
        text = text.replace(word, '')
        text = text.replace(word + ' ', ' ')
        text = text.replace(' ' + word, ' ')

    # Step 2: Replace formal phrases with Darija
    for formal, darija in REPLACEMENTS.items():
        text = text.replace(formal, darija)
        # Try with capital first letter
        if formal:
            text = text.replace(formal.capitalize(), darija.capitalize() if darija else '')

    # Step 3: Clean up double spaces, empty lines
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\n\s*\n', '\n', text)

    # Step 4: Enforce line limits (max 7 lines)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    lines = lines[:7]

    # Step 5: Enforce line length (max 120 chars)
    result = []
    for line in lines:
        if len(line) > 120:
            # Break at last space before 120
            idx = line.rfind(' ', 0, 120)
            if idx > 0:
                result.append(line[:idx])
                remainder = line[idx+1:].strip()
                if remainder:
                    result.append(remainder[:120])
            else:
                result.append(line[:120])
        else:
            result.append(line)

    # Step 6: Ensure energy at end
    if result and not any(c in result[-1] for c in '🔥💀😂👏!!!???'):
        result[-1] += random.choice([' 🔥', ' 💀', ' 😂', ' !!!', ' ???'])

    final = '\n'.join(result[:7])

    # Step 7: Validate — if still bad, use template
    validation = validate_darija(final)
    if not validation["is_natural"]:
        return _fallback_template(situation)

    return final


def validate_darija(text: str) -> Dict:
    """
    Validate if text is natural Darija.

    Returns:
        {"score": 0-100, "is_natural": bool, "issues": [str]}
    """
    score = 100
    issues = []

    # Check for formal Arabic (BAD)
    formal_found = []
    for pattern in FORMAL_ARABIC:
        if pattern in text:
            formal_found.append(pattern)
            score -= 15

    if formal_found:
        issues.append(f"Formal Arabic: {', '.join(formal_found[:3])}")

    # Check for natural Darija patterns (GOOD)
    good_patterns = [
        r'\b[wk]a[yt][a-z]+\b',
        r'\b[37]+[a-z]+\b',
        r'\b[a-z]+[379]\b',
        r'\bdaba\b', r'\bghadi\b', r'\bwalo\b',
        r'\bs7bi\b', r'\bsafi\b', r'\b3iyet\b',
        r'\bb7al\b', r'\bmashi\b', r'\bwach\b',
        r'\bfin\b', r'\bt9awed\b', r'\bkan\b',
    ]

    good_count = 0
    for pattern in good_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            good_count += 1
            score += 3

    if good_count < 2:
        issues.append("Too few natural Darija patterns")
        score -= 10

    # Check length
    lines = [l for l in text.split('\n') if l.strip()]
    if len(lines) > 7:
        score -= 10
        issues.append(f"Too many lines ({len(lines)})")

    # Check emoji count
    emoji_count = sum(1 for c in text if c in '🔥💀😂👏🟢🟡🔴⚽🎯⭐🏆📊🗓️🐦⚔️🎮💥🛡️😈😱🚨📰')
    if emoji_count > 4:
        score -= 5
        issues.append(f"Too many emojis ({emoji_count})")

    score = max(0, min(100, score))

    return {
        "score": score,
        "is_natural": score >= 70 and good_count >= 2,
        "issues": issues,
        "good_patterns": good_count,
    }


def _fallback_template(situation: str, **kwargs) -> str:
    """Generate fallback text from templates when AI fails."""
    templates = TEMPLATES.get(situation, TEMPLATES["general"])
    if not templates:
        return "walo men walo 💀"

    n = min(5, len(templates))
    selected = random.sample(templates, n)

    formatted = []
    for t in selected:
        try:
            formatted.append(t.format(**kwargs))
        except KeyError:
            if "{player}" in t and "player" not in kwargs:
                continue
            if "{rating}" in t and "rating" not in kwargs:
                continue
            formatted.append(t)

    return '\n'.join(formatted[:5])


def get_templates(situation: str, **kwargs) -> List[str]:
    """Get authentic Darija templates for a situation."""
    return TEMPLATES.get(situation, TEMPLATES["general"])


# ═══════════════════════════════════════════════════════════════════════════════
# ASYNC WRAPPER for gemini.py integration
# ═══════════════════════════════════════════════════════════════════════════════

async def ask_and_clean(_ask_func, prompt: str, max_tokens: int = 300, situation: str = "general"):
    """
    Wrapper for your existing _ask function.
    Calls AI, then cleans the output.

    Usage in gemini.py:
        from darija import ask_and_clean
        result = await ask_and_clean(_ask, prompt, max_tokens=700, situation="win")
    """
    raw = await _ask_func(prompt, max_tokens)
    if not raw:
        return _fallback_template(situation)

    return clean_darija(raw, situation)
