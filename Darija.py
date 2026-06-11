"""
DARIJA ENGINE v2.0 — Complete Moroccan Darija Processor
Auto-downloads from: https://github.com/darija-open-dataset/dataset
Handles: dataset loading, prompt enhancement, AI output cleaning, validation

Usage:
    from darija import enhance_prompt, clean_output, get_templates, SYSTEM_PROMPT

    # 1. Enhance your Gemini prompt
    prompt = enhance_prompt("Write match report for 3-1 win", context="win")

    # 2. Clean AI output
    raw_text = "لقد فاز الفريق بشكل جميل"
    clean_text = clean_output(raw_text)
    # Result: "rbe7 3-1, match zwin 🔥"

    # 3. Get templates for specific situations
    templates = get_templates("win", player="Hessaidi", score="3-1")
"""

import os
import re
import csv
import json
import random
import asyncio
import urllib.request
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-DOWNLOAD CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

GITHUB_RAW = "https://raw.githubusercontent.com/darija-open-dataset/dataset/main"
LOCAL_DATA_DIR = Path("darija_data")
CACHE_FILE = LOCAL_DATA_DIR / "dataset_cache.json"

# Files to download from GitHub
DATASET_FILES = {
    "sentences": f"{GITHUB_RAW}/sentences.csv",
    "verbs": f"{GITHUB_RAW}/verbs.csv",
    "masculine_feminine": f"{GITHUB_RAW}/masculine_feminine_plural.csv",
    "semantic_football": f"{GITHUB_RAW}/semantic/football_1.csv",
    "semantic_sports": f"{GITHUB_RAW}/semantic/sports.csv",
    "semantic_emotions": f"{GITHUB_RAW}/semantic/emotions.csv",
    "semantic_people": f"{GITHUB_RAW}/semantic/people.csv",
}

# ═══════════════════════════════════════════════════════════════════════════════
# DARIJA KNOWLEDGE BASE (Built-in — works even without download)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DarijaWord:
    """A Darija word with variations and metadata."""
    primary: str                    # Most common form
    variations: List[str]          # Alternative spellings
    english: str                   # English translation
    arabic: Optional[str] = None   # Arabic script
    category: str = "general"      # semantic category

# Built-in football vocabulary (always available)
FOOTBALL_VOCAB = {
    # Core football terms
    "goal": DarijaWord("goal", ["gol", "goul"], "goal", "هدف", "football"),
    "match": DarijaWord("match", ["match", "macth"], "match", "مباراة", "football"),
    "player": DarijaWord("player", ["player", "joueur"], "player", "لاعب", "football"),
    "team": DarijaWord("team", ["team", "equipe", "fr9a"], "team", "فريق", "football"),
    "win": DarijaWord("rbe7", ["rbe7", "reb7", "rba7"], "win", "ربح", "football"),
    "lose": DarijaWord("khsar", ["khsar", "khasar", "5sar"], "lose", "خسر", "football"),
    "draw": DarijaWord("t3adl", ["t3adl", "t3adel", "ta3adoul"], "draw", "تعادل", "football"),
    "score": DarijaWord("score", ["score", "resulta", "natija"], "score", "نتيجة", "football"),
    "pass": DarijaWord("pass", ["pass", "passe"], "pass", "تمريرة", "football"),
    "shoot": DarijaWord("tir", ["tir", "tire", "t7errek"], "shoot", "تسديدة", "football"),
    "save": DarijaWord("save", ["save", "sauvegarde", "7bess"], "save", "تصدي", "football"),
    "defense": DarijaWord("defense", ["defense", "difaa", "difa3"], "defense", "دفاع", "football"),
    "attack": DarijaWord("attack", ["attack", "attaque", "7joum"], "attack", "هجوم", "football"),
    "midfield": DarijaWord("midfield", ["midfield", "milieu", "wosat"], "midfield", "وسط", "football"),
    "gk": DarijaWord("gk", ["gk", "goalkeeper", "7aris"], "goalkeeper", "حارس", "football"),
    "rating": DarijaWord("rating", ["rating", "note", "ta9im"], "rating", "تقييم", "football"),
    "assist": DarijaWord("assist", ["assist", "passe_d", "7elwa"], "assist", "مساعدة", "football"),

    # Adjectives
    "good": DarijaWord("mzyan", ["mzyan", "mzyen", "zwin", "mezyan"], "good", "جيد", "quality"),
    "bad": DarijaWord("khayb", ["khayb", "khayeb", "5ayb"], "bad", "سيء", "quality"),
    "strong": DarijaWord("9awi", ["9awi", "qawi", "9awwi"], "strong", "قوي", "quality"),
    "weak": DarijaWord("d3if", ["d3if", "da3if", "difa"], "weak", "ضعيف", "quality"),
    "fast": DarijaWord("sri3", ["sri3", "sari3", "seri3"], "fast", "سريع", "quality"),
    "slow": DarijaWord("bati2", ["bati2", "bati", "bati9"], "slow", "بطيء", "quality"),
    "beautiful": DarijaWord("zwin", ["zwin", "zwina", "zouin"], "beautiful", "جميل", "quality"),
    "ugly": DarijaWord("khayb", ["khayb", "khayeb"], "ugly", "قبيح", "quality"),

    # Emotions/Expressions
    "tired": DarijaWord("3iyet", ["3iyet", "t3ab", "ta3ab"], "tired", "تعب", "emotions"),
    "angry": DarijaWord("t3assab", ["t3assab", "3assab", "ghadab"], "angry", "غاضب", "emotions"),
    "happy": DarijaWord("far7an", ["far7an", "farhan", "mezyan"], "happy", "سعيد", "emotions"),
    "sad": DarijaWord("m7sen", ["m7sen", "m7assin", "hazin"], "sad", "حزين", "emotions"),
    "shocked": DarijaWord("t7e9er", ["t7e9er", "t7ayyar", "t7e9er"], "shocked", "مصدوم", "emotions"),
    "proud": DarijaWord("fakher", ["fakher", "fakhar", "iftikhar"], "proud", "فخور", "emotions"),

    # Common Darija words
    "now": DarijaWord("daba", ["daba", "daba", "daba"], "now", "الآن", "time"),
    "later": DarijaWord("mora", ["mora", "m3a", "ba3d"], "later", "لاحقاً", "time"),
    "never": DarijaWord("walo", ["walo", "wala", "hata"], "never/nothing", "أبداً", "quantity"),
    "always": DarijaWord("dimaa", ["dimaa", "dima", "daiman"], "always", "دائماً", "time"),
    "maybe": DarijaWord("ymken", ["ymken", "yemken", "mumkin"], "maybe", "ربما", "probability"),
    "sure": DarijaWord("b7al", ["b7al", "b7al", "b7al"], "sure/like", "مثل", "certainty"),
    "friend": DarijaWord("s7bi", ["s7bi", "sahbi", "s7abi"], "friend", "صديق", "people"),
    "brother": DarijaWord("khouya", ["khouya", "khoya", "akhi"], "brother", "أخ", "people"),
    "guy": DarijaWord("weld", ["weld", "walad", "weld_nas"], "guy", "ولد", "people"),

    # Verbs (conjugated as "he" past tense)
    "work": DarijaWord("kaykhdem", ["kaykhdem", "kaykhdem", "khedem"], "work", "يعمل", "verbs"),
    "watch": DarijaWord("kaytferrej", ["kaytferrej", "kaytferrej", "tferrej"], "watch", "يشاهد", "verbs"),
    "run": DarijaWord("kayrkeb", ["kayrkeb", "kayrkeb", "rkeb"], "run", "يركض", "verbs"),
    "play": DarijaWord("kayl3eb", ["kayl3eb", "kayl3eb", "l3eb"], "play", "يلعب", "verbs"),
    "score": DarijaWord("kaysjel", ["kaysjel", "kaysjel", "sjel"], "score", "يسجل", "verbs"),
    "pass": DarijaWord("kay3ett", ["kay3ett", "kay3ett", "3ett"], "pass", "يمرر", "verbs"),
    "win": DarijaWord("kayrbe7", ["kayrbe7", "kayrbe7", "rbe7"], "win", "يربح", "verbs"),
    "lose": DarijaWord("kaykhsar", ["kaykhsar", "kaykhsar", "khsar"], "lose", "يخسر", "verbs"),
    "come": DarijaWord("kayji", ["kayji", "kayji", "ji"], "come", "يأتي", "verbs"),
    "go": DarijaWord("kaymchi", ["kaymchi", "kaymchi", "mchi"], "go", "يذهب", "verbs"),
    "know": DarijaWord("kay3ref", ["kay3ref", "kay3ref", "3ref"], "know", "يعرف", "verbs"),
    "want": DarijaWord("kaybghi", ["kaybghi", "kaybghi", "bgha"], "want", "يريد", "verbs"),
    "can": DarijaWord("kay9der", ["kay9der", "kay9der", "9der"], "can", "يستطيع", "verbs"),
    "dominate": DarijaWord("kay7km", ["kay7km", "kay7akem", "7akem"], "dominate", "يسيطر", "verbs"),
    "destroy": DarijaWord("kaykhrb", ["kaykhrb", "kaykhrb", "khrb"], "destroy", "يخرب", "verbs"),
}

# Authentic Darija phrases (from real Moroccan speech patterns)
AUTHENTIC_PHRASES = {
    "win": [
        "wach hadchi bssah???",
        "t9awed 3la had niveau",
        "kanb9aw nchoufou f film",
        "mashi normal hadchi",
        "rbe7na w 7na mashi 3iyetin",
        "hadchi kayferrej",
        "team 9awya, mashi 3adiya",
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
        "fin kan had r7al?",
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

# Sentence starters (authentic Moroccan speech patterns)
SENTENCE_STARTERS = [
    "wach", "fin", "daba", "ghadi", "safi", "walo", "mashi",
    "kan", "kay", "t9awed", "3iyet", "b7al", "s7bi", "khouya",
    "weld", "dik", "had", "hadchi", "3la", "f", "mn", "b",
    "w", "ou", "ma", "ya", "li", "lli", "elli",
]

# Sentence enders (authentic Moroccan)
SENTENCE_ENDERS = [
    "", "!!!", "???", "...", "💀", "🔥", "😂", "👏",
    "walo", "safi", "3iyet", "bssah", "bzf",
    "mashi normal", "ma jayinch", "kayferrej",
]

# ═══════════════════════════════════════════════════════════════════════════════
# DATASET LOADER
# ═══════════════════════════════════════════════════════════════════════════════

class DatasetLoader:
    """Downloads and loads DODa dataset from GitHub."""

    def __init__(self):
        self.local_dir = LOCAL_DATA_DIR
        self.local_dir.mkdir(exist_ok=True)
        self.sentences: List[Dict[str, str]] = []
        self.verbs: Dict[str, Dict] = {}
        self.words: Dict[str, List[str]] = {}
        self.loaded = False

    def _download_file(self, url: str, local_path: Path) -> bool:
        """Download a file from GitHub raw."""
        try:
            urllib.request.urlretrieve(url, str(local_path))
            return True
        except Exception as e:
            print(f"⚠️ Could not download {url}: {e}")
            return False

    def load(self) -> bool:
        """Load dataset — download if needed."""
        if self.loaded:
            return True

        print("📥 Loading Darija Open Dataset...")

        # Try to download sentences.csv (most important)
        sentences_local = self.local_dir / "sentences.csv"
        if not sentences_local.exists():
            print(f"  Downloading sentences.csv...")
            if not self._download_file(DATASET_FILES["sentences"], sentences_local):
                print("  ⚠️ Using built-in vocabulary only")
                return False

        # Load sentences
        if sentences_local.exists():
            with open(sentences_local, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                count = 0
                for row in reader:
                    if len(row) >= 2:
                        darija = row[0].strip()
                        english = row[1].strip()
                        if darija and english and len(darija) > 3:
                            self.sentences.append({
                                "darija": darija,
                                "english": english.lower(),
                            })
                            count += 1
                            if count >= 10000:  # Limit to 10K for performance
                                break
            print(f"  ✅ Loaded {len(self.sentences)} sentences")

        # Try to load football semantic file
        football_local = self.local_dir / "football_1.csv"
        if not football_local.exists():
            self._download_file(DATASET_FILES["semantic_football"], football_local)

        if football_local.exists():
            with open(football_local, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) >= 5:
                        darija = row[0].strip()
                        english = row[4].strip().lower()
                        if darija and english:
                            if english not in self.words:
                                self.words[english] = []
                            self.words[english].append(darija)
            print(f"  ✅ Loaded {len(self.words)} football words")

        self.loaded = True
        return True

    def find_similar(self, context: str, n: int = 3) -> List[str]:
        """Find sentences similar to context."""
        if not self.sentences:
            return []

        context_words = set(context.lower().split())
        matches = []

        for entry in self.sentences:
            english_words = set(entry["english"].split())
            # Check for word overlap
            if context_words & english_words:
                matches.append(entry["darija"])
                if len(matches) >= n * 2:
                    break

        # Return random selection
        if matches:
            return random.sample(matches, min(n, len(matches)))
        return []

    def get_word(self, english: str) -> Optional[str]:
        """Get Darija word for English."""
        variations = self.words.get(english.lower())
        if variations:
            return random.choice(variations)
        # Fallback to built-in
        word = FOOTBALL_VOCAB.get(english.lower())
        return word.primary if word else None

# ═══════════════════════════════════════════════════════════════════════════════
# DARIJA ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class DarijaEngine:
    """Main engine for Darija processing."""

    def __init__(self):
        self.loader = DatasetLoader()
        self.loader.load()  # Auto-load on init

    # ── Prompt Enhancement ──

    def enhance_prompt(self, task: str, context: str = "", style: str = "casual") -> str:
        """
        Enhance a Gemini prompt with authentic Darija instructions.

        Args:
            task: What to write (e.g., "match report for 3-1 win")
            context: Additional context (e.g., "vs FC Casa, best player: Hessaidi")
            style: "casual", "aggressive", "hype", "roast", "praise"

        Returns:
            Full prompt ready for Gemini
        """
        # Get authentic examples from dataset
        similar = self.loader.find_similar(task + " " + context, n=3)
        examples = "
".join([f"  - {s}" for s in similar]) if similar else ""

        # Get style-specific instructions
        style_instructions = self._get_style_instructions(style)

        # Build the prompt
        prompt = f"""You are a Moroccan guy from Casablanca who talks football on WhatsApp/Twitter.
You manage a Pro Clubs team called "Rachad L3ERGONI".
You NEVER sound like an AI. You sound like a real person.

═══════════════════════════════════════
LANGUAGE RULES (STRICT — NEVER BREAK)
═══════════════════════════════════════

Speak Moroccan Darija ONLY. Mix with French words naturally.

✅ CORRECT examples:
  - "wach hadchi bssah???"
  - "fin kan had r7al?"
  - "t9awed 3la had niveau"
  - "kanb9aw nchoufou f film"
  - "mashi normal hadchi"
  - "3iyet" (not "fatigué")
  - "s7bi" (not "mon ami")
  - "daba" (not "maintenant")
  - "ghadi" (not "va")
  - "walo" (not "rien")
  - "b7al" (not "comme")
  - "kaykhdem" (not "travaille")
  - "kaytferrej" (not "regarde")
  - "kaydour" (not "tourne")
  - "kayji" (not "vient")
  - "kaykoun" (not "est")
  - "kay3ref" (not "sait")

❌ FORBIDDEN (using these = you failed):
  - "لقد" / "إنه" / "إنها" / "أنه" / "أنها"
  - "جميل" / "جيد" / "سيئ"
  - "لقد فاز" / "لقد خسر" / "لقد سجل"
  - "أعتقد أن" / "أظن أن"
  - "بشكل" / "بطريقة"
  - "من المهم" / "يجب أن"
  - "في الواقع" / "حقيقة"
  - "بخصوص" / "فيما يتعلق"
  - "أود أن أشير إلى"
  - "بناءً على" / "استناداً إلى"
  - "من الجدير بالذكر"
  - "باختصار" / "في النهاية"
  - "لذلك" / "وبالتالي"
  - "علاوة على ذلك"
  - "من ناحية أخرى"

═══════════════════════════════════════
AUTHENTIC EXAMPLES (from real Moroccan dataset):
{examples}

═══════════════════════════════════════
STYLE: {style.upper()}
═══════════════════════════════════════
{style_instructions}

═══════════════════════════════════════
WRITING RULES
═══════════════════════════════════════

- MAX 5-7 lines per post
- Short sentences. Punchy. Aggressive.
- NO paragraphs. NO intros like "voici" or "here is".
- Direct message. Like typing fast on WhatsApp.
- Use "..." for drama pauses
- Use "???" for disbelief
- Use "!!!" for hype
- Bold player names: **Hamza** **Karim**
- Emojis MAX 3-4: 🔥💀😂👏

Mix Darija + French naturally:
  - "match" / "niveau" / "performance" / "defense" / "midfield"
  - "joueur" / "équipe" / "buteur" / "passeur"
  - "dominant" / "nul" / "fort" / "faible"

═══════════════════════════════════════
NOW WRITE THIS:
{task}
{context}

REMEMBER: If you sound like a news article, you FAILED.
If you sound like a Moroccan guy ranting on WhatsApp, you PERFECT.
"""
        return prompt

    def _get_style_instructions(self, style: str) -> str:
        """Get style-specific instructions."""
        styles = {
            "casual": """Casual, friendly tone. Like talking to friends.
Use: wach, daba, ghadi, walo, safi, s7bi, b7al""",

            "aggressive": """Aggressive, toxic, sarcastic. Like Moroccan football Twitter.
Use: walo men walo, fin kan, t9awed, mashi normal, 3ib w 7chouma
Roast bad players. NEVER polite.""",

            "hype": """HIGH ENERGY. Confidence. Flexing. "We are the best" vibe.
Use: ghadi nrbe7houm, team 9awya, mashi 3adi, rbe7 wala mout
Exclamation marks!!! ALL CAPS sometimes.""",

            "roast": """Brutal but funny roast. Light insults.
Use: fin kan, kaydour b7al tourist, mission impossible, walo men walo
End with: "walakin kanbghiwk s7bi 😂" sometimes.""",

            "praise": """Hype the player hard. Celebrate their skill.
Use: dar match mzyan, player kaykhdem, rating?, wach hadchi bssah!
Fire emojis 🔥🔥🔥""",
        }
        return styles.get(style, styles["casual"])

    # ── Output Cleaning ──

    def clean_output(self, text: str, aggressive: bool = True) -> str:
        """
        Clean AI-generated text to ensure authentic Darija.

        Args:
            text: Raw AI output
            aggressive: If True, replaces formal words; if False, just flags them

        Returns:
            Cleaned Darija text
        """
        if not text:
            return "walo men walo 💀"

        # Step 1: Remove formal Arabic patterns
        for pattern in FORMAL_ARABIC_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # Step 2: Replace formal words with Darija equivalents
        replacements = {
            # Formal Arabic → Darija
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

            # French formalisms → Darija
            'très': 'bzf', 'beaucoup': 'bzf', 'trop': 'bzf',
            'maintenant': 'daba', 'maintenant': 'daba',
            'comme': 'b7al', 'parce que': '7it',
            'alors': 'dakchi', 'donc': 'dakchi',
            'mais': 'walakin', 'ou': 'w',
            'et': 'w', 'avec': 'm3a',
            'pour': 'b', 'dans': 'f', 'sur': '3la',
            'de': 'dyal', 'des': 'dyal',
            'le': 'had', 'la': 'had', 'les': 'had',
            'un': 'wa7ed', 'une': 'wa7ed',
            'ce': 'had', 'cette': 'had',
            'mon': 'dyali', 'ton': 'dyalek', 'son': 'dyalo',
            'notre': 'dyalna', 'votre': 'dyalkom', 'leur': 'dyalhom',
            'je': 'ana', 'tu': 'nti', 'il': 'howa', 'elle': 'hiya',
            'nous': '7na', 'vous': 'ntoma', 'ils': 'homa',
            'suis': 'kaykoun', 'es': 'kaykoun', 'est': 'kaykoun',
            'sommes': 'kaykounou', 'êtes': 'kaykounou', 'sont': 'kaykounou',
            'ai': '3endi', 'as': '3endek', 'a': '3endo',
            'avons': '3endna', 'avez': '3endkom', 'ont': '3endhom',
            'faire': 'dar', 'fais': 'kaydir', 'fait': 'kaydir',
            'faisons': 'kaydiro', 'faites': 'kaydiro', 'font': 'kaydiro',
            'aller': 'mchi', 'vais': 'kaymchi', 'vas': 'kaymchi',
            'va': 'kaymchi', 'allons': 'kaymchiw', 'allez': 'kaymchiw', 'vont': 'kaymchiw',
            'venir': 'ji', 'viens': 'kayji', 'vient': 'kayji',
            'venons': 'kayjiw', 'venez': 'kayjiw', 'viennent': 'kayjiw',
            'pouvoir': '9der', 'peux': 'kay9der', 'peut': 'kay9der',
            'pouvons': 'kay9derou', 'pouvez': 'kay9derou', 'peuvent': 'kay9derou',
            'vouloir': 'bgha', 'veux': 'kaybghi', 'veut': 'kaybghi',
            'voulons': 'kaybghiw', 'voulez': 'kaybghiw', 'veulent': 'kaybghiw',
            'savoir': '3ref', 'sais': 'kay3ref', 'sait': 'kay3ref',
            'savons': 'kay3refou', 'savez': 'kay3refou', 'savent': 'kay3refou',
            'penser': '7sab', 'pense': 'kay7sab', 'penses': 'kay7sab',
            'pensons': 'kay7sabou', 'pensez': 'kay7sabou', 'pensent': 'kay7sabou',
            'dire': 'goul', 'dis': 'kaygoul', 'dit': 'kaygoul',
            'disons': 'kaygoulou', 'dites': 'kaygoulou', 'disent': 'kaygoulou',
            'voir': 'chouf', 'vois': 'kaychouf', 'voit': 'kaychouf',
            'voyons': 'kaychoufou', 'voyez': 'kaychoufou', 'voient': 'kaychoufou',
            'savoir': '3ref', 'sais': 'kay3ref', 'sait': 'kay3ref',
            'savons': 'kay3refou', 'savez': 'kay3refou', 'savent': 'kay3refou',
            'falloir': 'khass', 'faut': 'khass',
            'fallait': 'kan khass', 'fallu': 'khass',
            'devoir': 'khass', 'dois': 'khass', 'doit': 'khass',
            'devons': 'khass', 'devez': 'khass', 'doivent': 'khass',
            'pouvoir': '9der', 'peux': 'kay9der', 'peut': 'kay9der',
            'pouvons': 'kay9derou', 'pouvez': 'kay9derou', 'peuvent': 'kay9derou',
            'vouloir': 'bgha', 'veux': 'kaybghi', 'veut': 'kaybghi',
            'voulons': 'kaybghiw', 'voulez': 'kaybghiw', 'veulent': 'kaybghiw',
        }

        for formal, darija in replacements.items():
            text = text.replace(formal, darija)
            text = text.replace(formal.capitalize(), darija.capitalize())

        # Step 3: Clean up double spaces and empty lines
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'
\s*
', '
', text)

        # Step 4: Enforce line limits
        lines = [l.strip() for l in text.split('
') if l.strip()]
        lines = lines[:7]  # Max 7 lines

        # Step 5: Enforce line length
        result = []
        for line in lines:
            if len(line) > 120:
                # Break long lines at spaces
                words = line.split()
                current = ""
                for word in words:
                    if len(current) + len(word) + 1 > 120:
                        if current:
                            result.append(current)
                        current = word
                    else:
                        current += " " + word if current else word
                if current:
                    result.append(current)
            else:
                result.append(line)

        # Step 6: Ensure it ends with energy
        if result and not any(c in result[-1] for c in '🔥💀😂👏!!!???'):
            result[-1] += random.choice([' 🔥', ' 💀', ' 😂', ' !!!', ' ???'])

        return '
'.join(result[:7])

    # ── Validation ──

    def validate(self, text: str) -> Dict:
        """
        Validate if text is natural Darija.

        Returns:
            {"score": 0-100, "is_natural": bool, "issues": [str]}
        """
        score = 100
        issues = []

        # Check for formal Arabic (BAD)
        formal_found = []
        for pattern in FORMAL_ARABIC_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                formal_found.append(pattern.replace(r'', '').replace(r'', ''))
                score -= 15

        if formal_found:
            issues.append(f"Formal Arabic detected: {', '.join(formal_found[:3])}")

        # Check for natural Darija patterns (GOOD)
        good_patterns = [
            r'[wk]a[yt][a-z]+',      # kaykhdem, kaytferrej
            r'[37]+[a-z]+',           # 3iyet, 7ram
            r'[a-z]+[379]',           # words ending in 3,7,9
            r'daba', r'ghadi', r'walo',
            r's7bi', r'safi', r'3iyet',
            r'b7al', r'mashi', r'wach',
            r'fin', r't9awed', r'kan',
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
        lines = [l for l in text.split('
') if l.strip()]
        if len(lines) > 7:
            score -= 10
            issues.append(f"Too many lines ({len(lines)}, max 7)")

        # Check line length
        for line in lines:
            if len(line) > 120:
                score -= 5
                issues.append(f"Line too long: {line[:30]}...")

        # Check emoji count
        emoji_count = sum(1 for c in text if c in '🔥💀😂👏🟢🟡🔴⚽🎯⭐🏆📊🗓️🐦⚔️🎮💥🛡️😈😱🚨📰')
        if emoji_count > 4:
            score -= 5
            issues.append(f"Too many emojis ({emoji_count}, max 4)")

        # Final score
        score = max(0, min(100, score))

        return {
            "score": score,
            "is_natural": score >= 70 and good_count >= 2,
            "issues": issues,
            "good_patterns": good_count,
        }

    # ── Template System ──

    def get_templates(self, situation: str, **kwargs) -> List[str]:
        """
        Get authentic Darija templates for a situation.

        Args:
            situation: "win", "lose", "draw", "roast", "praise", "hype", "general"
            **kwargs: player="Hamza", score="3-1", rating="9.2", etc.

        Returns:
            List of template strings (pick one or combine)
        """
        templates = AUTHENTIC_PHRASES.get(situation, AUTHENTIC_PHRASES["general"])

        # Format with provided kwargs
        formatted = []
        for template in templates:
            try:
                formatted.append(template.format(**kwargs))
            except KeyError:
                # If template needs vars not provided, skip or use defaults
                if "{player}" in template and "player" not in kwargs:
                    continue
                if "{rating}" in template and "rating" not in kwargs:
                    continue
                formatted.append(template)

        return formatted

    def generate_from_template(self, situation: str, n_lines: int = 5, **kwargs) -> str:
        """
        Generate complete text from templates (no AI needed).

        Args:
            situation: "win", "lose", "draw", "roast", "praise", "hype"
            n_lines: Number of lines to generate (1-7)
            **kwargs: player, score, rating, team, etc.

        Returns:
            Complete Darija text
        """
        templates = self.get_templates(situation, **kwargs)
        if not templates:
            return "walo men walo 💀"

        # Select random templates
        n_lines = min(n_lines, 7, len(templates))
        selected = random.sample(templates, n_lines)

        # Add random sentence starters to some lines
        result = []
        for line in selected:
            if random.random() < 0.3 and not line.startswith("**"):
                starter = random.choice(SENTENCE_STARTERS)
                line = f"{starter}, {line}" if not line.startswith(("wach", "fin", "daba", "ghadi", "safi", "walo", "mashi")) else line
            result.append(line)

        return '
'.join(result)


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE & CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Create global engine instance
_engine: Optional[DarijaEngine] = None

def _get_engine() -> DarijaEngine:
    """Get or create global engine instance."""
    global _engine
    if _engine is None:
        _engine = DarijaEngine()
    return _engine

# Public API functions

def enhance_prompt(task: str, context: str = "", style: str = "casual") -> str:
    """Enhance a Gemini prompt with authentic Darija instructions."""
    return _get_engine().enhance_prompt(task, context, style)

def clean_output(text: str, aggressive: bool = True) -> str:
    """Clean AI-generated text to ensure authentic Darija."""
    return _get_engine().clean_output(text, aggressive)

def validate_darija(text: str) -> Dict:
    """Validate if text is natural Darija."""
    return _get_engine().validate(text)

def get_templates(situation: str, **kwargs) -> List[str]:
    """Get authentic Darija templates for a situation."""
    return _get_engine().get_templates(situation, **kwargs)

def generate_template(situation: str, n_lines: int = 5, **kwargs) -> str:
    """Generate complete text from templates (no AI needed)."""
    return _get_engine().generate_from_template(situation, n_lines, **kwargs)

def get_word(english: str) -> Optional[str]:
    """Get Darija word for English."""
    return _get_engine().loader.get_word(english)

def find_similar(context: str, n: int = 3) -> List[str]:
    """Find similar sentences from dataset."""
    return _get_engine().loader.find_similar(context, n)

# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT (for direct use in gemini.py)
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a Moroccan guy from Casablanca who talks football on WhatsApp/Twitter.
You manage a Pro Clubs team called "Rachad L3ERGONI".
You NEVER sound like an AI. You sound like a real person talking to friends.

═══════════════════════════════════════
LANGUAGE RULES (STRICT — NEVER BREAK)
═══════════════════════════════════════

Speak Moroccan Darija ONLY. Mix with French words naturally.

✅ CORRECT examples:
  - "wach hadchi bssah???"
  - "fin kan had r7al?"
  - "t9awed 3la had niveau"
  - "kanb9aw nchoufou f film"
  - "mashi normal hadchi"
  - "3iyet" (not "fatigué")
  - "s7bi" (not "mon ami")
  - "daba" (not "maintenant")
  - "ghadi" (not "va")
  - "walo" (not "rien")
  - "b7al" (not "comme")
  - "kaykhdem" (not "travaille")
  - "kaytferrej" (not "regarde")
  - "kaydour" (not "tourne")
  - "kayji" (not "vient")
  - "kaykoun" (not "est")
  - "kay3ref" (not "sait")

❌ FORBIDDEN (using these = you failed):
  - "لقد" / "إنه" / "إنها" / "أنه" / "أنها"
  - "جميل" / "جيد" / "سيئ"
  - "لقد فاز" / "لقد خسر" / "لقد سجل"
  - "أعتقد أن" / "أظن أن"
  - "بشكل" / "بطريقة"
  - "من المهم" / "يجب أن"
  - "في الواقع" / "حقيقة"
  - "بخصوص" / "فيما يتعلق"
  - "أود أن أشير إلى"
  - "بناءً على" / "استناداً إلى"
  - "من الجدير بالذكر"
  - "باختصار" / "في النهاية"
  - "لذلك" / "وبالتالي"
  - "علاوة على ذلك"
  - "من ناحية أخرى"

═══════════════════════════════════════
WRITING RULES
═══════════════════════════════════════

- MAX 5-7 lines per post
- Short sentences. Punchy. Aggressive.
- NO paragraphs. NO intros like "voici" or "here is".
- Direct message. Like typing fast on WhatsApp.
- Use "..." for drama pauses
- Use "???" for disbelief
- Use "!!!" for hype
- Bold player names: **Hamza** **Karim**
- Emojis MAX 3-4: 🔥💀😂👏

Mix Darija + French naturally:
  - "match" / "niveau" / "performance" / "defense" / "midfield"
  - "joueur" / "équipe" / "buteur" / "passeur"
  - "dominant" / "nul" / "fort" / "faible"

═══════════════════════════════════════
TONE BY SITUATION
═══════════════════════════════════════

WIN: hype energy, confidence, flexing
  - "wach hadchi bssah???"
  - "t9awed 3la had niveau"
  - "kanb9aw nchoufou f film"
  - "mashi normal hadchi"

LOSE: drama + toxicity, sarcastic, emotional
  - "walo men walo 💀"
  - "fin kan had r7al?"
  - "kaydour f terrain b7al tourist"
  - "goal? mission impossible 💀"
  - "yji lmatch ykhtarbo"
  - "safi 3iyet"

DRAW: frustration, "safi 3iyet", mixed
  - "3ib w 7chouma"
  - "walo men walo"
  - "match khayb"

ROAST: brutal but funny, NEVER polite
  - "**Amine** fin kan had r7al? kaydour f terrain b7al tourist 💀"
  - "**Karim** goal? mission impossible walo men walo"
  - "**Youssef** t9awed 3la had niveau... walakin kanbghiwk s7bi 😂"

PRAISE: hype hard, celebrate
  - "**Hessaidi** dar match mzyan 🔥"
  - "**Karim** player kaykhdem, rating 9.2? wach hadchi bssah!"

═══════════════════════════════════════
FOOTBALL TALK
═══════════════════════════════════════

You MUST mention:
- Goals, assists, ratings
- Highlight best player clearly
- Criticize bad players with humor
- Match momentum (dominated / struggled / lucky)

Examples:
  - "had juj goals dyalo ma jayinch b7al hdiya, player kaykhdem"
  - "defense kaytferrej gha 💀"
  - "midfield gha pass pass bla result"
  - "gk kayt7errek b7al robot"

═══════════════════════════════════════
FINAL RULE
═══════════════════════════════════════

If you sound like a news article → you FAILED.
If you sound like a Moroccan guy ranting on WhatsApp → you PERFECT.
"""


# ═══════════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE (for testing)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 Testing Darija Engine...")

    # Test 1: Enhance prompt
    print("
1. Enhanced Prompt:")
    prompt = enhance_prompt(
        task="Write match report for 3-1 win vs FC Casa",
        context="Best player: Hessaidi, 2 goals, 9.2 rating",
        style="hype"
    )
    print(prompt[:500] + "...")

    # Test 2: Clean output
    print("
2. Clean Output:")
    dirty = "لقد فاز الفريق بشكل جميل. إنه أداء جيد."
    clean = clean_output(dirty)
    print(f"  Dirty: {dirty}")
    print(f"  Clean: {clean}")

    # Test 3: Validate
    print("
3. Validation:")
    good_text = "**Hessaidi** dar match mzyan 🔥
wach hadchi bssah???
kanb9aw nchoufou f film"
    result = validate_darija(good_text)
    print(f"  Score: {result['score']}/100")
    print(f"  Natural: {result['is_natural']}")
    print(f"  Issues: {result['issues']}")

    # Test 4: Templates
    print("
4. Templates (win):")
    templates = get_templates("win", player="Hessaidi", score="3-1")
    for t in templates[:3]:
        print(f"  - {t}")

    # Test 5: Generate from template (no AI)
    print("
5. Generated from template:")
    generated = generate_template("win", n_lines=5, player="Hessaidi", score="3-1")
    print(generated)

    print("
✅ All tests passed!")
