"""
DARIJA CLEANER v3.0 — Light post-processing for Moroccan Darija AI output

KEY PRINCIPLE: Trust the AI. Only clean, don't destroy.
The AI (Llama 3.1) is trained on Moroccan Arabic and can generate authentic Darija.
Our job is just to remove occasional formal Arabic words that slip in.
"""

import re
import random
from typing import Dict, List

# ── LIGHT CLEANING: Only remove these formal Arabic words ─────────────────────
# These are words that make text sound robotic/MSA instead of street Darija

FORMAL_WORDS = [
    # MSA connectors that sound stiff in Darija
    'لقد', 'إنه', 'إنها', 'أنه', 'أنها', 'إن', 'أن',
    'بناءً على', 'استناداً إلى',
    'من الجدير', 'من المفيد', 'من الأفضل', 'من المستحسن',
    'باختصار', 'في النهاية', 'ختاماً', 'أخيراً', 'في الختام',
    'لذلك', 'وبالتالي',
    'من ناحية', 'من جهة', 'من ناحية أخرى',
    'على سبيل المثال', 'مثلاً', 'كمثال',
    'بمعنى', 'حيث', 'الذي', 'التي', 'الذين',
    'وذلك', 'وقد', 'قد',
    'يمكن', 'يمكننا', 'يمكنني', 'يجب', 'ينبغي',
    'من الضروري', 'من المفيد',
    'لا شك', 'من الواضح', 'من المؤكد', 'بلا شك',
    'تلخيصاً', 'بشكل مختصر', 'مختصراً',
    'بكل بساطة', 'ببساطة', 'بشكل مباشر', 'مباشرة',
    'بصراحة', 'صراحةً', 'بكل صراحة',
    'بكل أمانة', 'بأمانة', 'بكل موضوعية',
    'بكل حيادية', 'بحيادية', 'بكل شفافية',
    'بكل وضوح', 'بوضوح', 'بكل دقة', 'بدقة',
    'بكل تفصيل', 'بتفصيل',
    # French formalisms
    'très bien', 'très mal', 'beaucoup de', 'trop de',
    'parce que', 'alors', 'donc',
]

# ── REPLACEMENTS: Formal → Darija (only when exact match) ───────────────────

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

# ── FALLBACK TEMPLATES (only used when AI returns empty) ─────────────────────

TEMPLATES = {
    "win": [
        "🔥 **Rbe7na!** Match mzyan bzf, l'équipe khdemat b7al ma kaynch!",
        "🏆 Walo men walo! Rbe7na w l3adou ma 9derch y3ml walo!",
        "💪 Dominant match! Kay7kmou f terrain, kaydirou chi 7wayed!",
    ],
    "lose": [
        "💀 **Khsarna...** Safi 3iyet, hadchi ma jayinch!",
        "😭 Walo men walo! L3adou dar fina chi 7aja w 7na naymin!",
        "🔥 Khsar 3la 7sab, defense kaytferrej gha!",
    ],
    "draw": [
        "🟡 **T3adl...** Safi 3iyet, match khayb bzf!",
        "😑 Walo men walo, midfield gha pass pass bla result!",
    ],
    "roast": [
        "🔥 Fin kan had r7al? Kaydour f terrain b7al tourist!",
        "💀 Goal? Mission impossible walo men walo!",
    ],
    "praise": [
        "🔥 Dar match mzyan! Player kaykhdem bzzaf!",
        "👏 Rating zwin! Wach hadchi bssah?!",
    ],
    "hype": [
        "🔥 **RACHAD L3ERGONI!** Ghadi nrbe7houm walo men walo!",
        "💪 Team 9awya! Ghadi nkhssrouhoum inshallah!",
    ],
    "general": [
        "🤔 Daba walo, ghadi nchoufou chno ghadi yw9e3!",
        "⚽ Rachad L3ERGONI f lmatch! Yallah safi!",
    ],
}


def clean_darija(text: str, situation: str = "general") -> str:
    """
    Light cleaning of AI-generated Darija.

    STRATEGY: Trust the AI. Only remove obvious formal Arabic words.
    Do NOT replace sentences with random templates.
    """
    if not text or not text.strip():
        return _fallback_template(situation)

    # Step 1: Remove formal Arabic words (whole word only, case-insensitive)
    for word in FORMAL_WORDS:
        # Case-insensitive replacement
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        text = pattern.sub('', text)

    # Step 2: Replace formal French/Arabic phrases with Darija equivalents
    for formal, darija in REPLACEMENTS.items():
        if formal in text:
            text = text.replace(formal, darija)

    # Step 3: Clean up spacing
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\n\s*\n', '\n', text)

    # Step 4: Limit lines (max 8) and line length (max 140 chars)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    lines = lines[:8]

    result = []
    for line in lines:
        if len(line) > 140:
            # Break at last space before 140
            idx = line.rfind(' ', 0, 140)
            if idx > 0:
                result.append(line[:idx])
                remainder = line[idx+1:].strip()
                if remainder:
                    result.append(remainder[:140])
            else:
                result.append(line[:140])
        else:
            result.append(line)

    final = '\n'.join(result[:8])

    # Step 5: Validate — if completely broken, use fallback
    if not _is_valid_darija(final):
        return _fallback_template(situation)

    return final


def _is_valid_darija(text: str) -> bool:
    """Check if text looks like valid Darija (not random garbage)."""
    if not text or len(text) < 10:
        return False

    # Check for natural Darija patterns
    darija_markers = [
        'daba', 'ghadi', 'walo', 's7bi', 'safi', '3iyet', 'b7al', 'mashi', 'wach',
        'fin', 'kan', 'rbe7', 'khsar', '9awi', 'd3if', 'zwin', 'khayb', 'mzyan',
        '3la', '7it', 'walakin', 'dakchi', 'nti', '7na', 'ntoma', 'bzf', 'hta',
        'dyal', 'fih', '3lih', '3end', 'kay', 'kat', 'dar', 'l3eb', 'jou', 'match',
        'lgoal', 'lkeeper', 'ldefense', 'lmidfield', 'lattack', 'lteam', 'léquipe',
        'rachad', 'l3ergoni', 'pro clubs', 'fc 26',
    ]

    text_lower = text.lower()
    marker_count = sum(1 for m in darija_markers if m in text_lower)

    # Need at least 2 markers OR some emoji energy
    has_emoji = any(c in text for c in '🔥💀😂👏🟢🟡🔴⚽🎯⭐🏆📊🗓️⚔️🎮💥🛡️😈😱🚨📰🤔🤷🙏💪🎉😅😆🤣😤')

    return marker_count >= 2 or has_emoji


def _fallback_template(situation: str, **kwargs) -> str:
    """Generate fallback text when AI completely fails."""
    templates = TEMPLATES.get(situation, TEMPLATES["general"])
    if not templates:
        return "walo men walo 💀"

    selected = random.choice(templates)
    try:
        return selected.format(**kwargs)
    except KeyError:
        return selected


# ── ASYNC WRAPPER for gemini.py ───────────────────────────────────────────────

async def ask_and_clean(_ask_func, prompt: str, max_tokens: int = 300, situation: str = "general"):
    """
    Calls AI, then lightly cleans the output.

    Usage in gemini.py:
        from darija import ask_and_clean
        result = await ask_and_clean(_ask, prompt, max_tokens=700, situation="win")
    """
    raw = await _ask_func(prompt, max_tokens)
    if not raw:
        return _fallback_template(situation)

    return clean_darija(raw, situation)
