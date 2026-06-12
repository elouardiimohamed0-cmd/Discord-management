"""
Rachad L3ERGONI — Humanized Darija Engine v2 (Pro Social Media Style)
- Short phrases (max 2 sentences)
- Clean Darija with strategic French/English code-switching
- Real squad integration (no imagined players)
- Typing imperfections: light, natural
- Emotion-driven templates
"""
import random
import re

# ═══════════════════════════════════════════════════════════════════════════════
# SQUAD CONFIG — UPDATE THIS WITH YOUR REAL PLAYERS
# ═══════════════════════════════════════════════════════════════════════════════

SQUAD = {
    # Example structure — replace with your real squad from proclubstracker
    # "hamza": {
    #     "name": "Hamza",
    #     "position": "ST",
    #     "number": 9,
    #     "nickname": "L9ahba",
    #     "nationality": "MA",
    #     "style": "finisher"
    # },
}

# If you have a JSON file with squad data, load it:
import json
import os
SQUAD_FILE = os.path.join(os.path.dirname(__file__), "squad.json")
if os.path.exists(SQUAD_FILE):
    with open(SQUAD_FILE, "r", encoding="utf-8") as f:
        SQUAD = json.load(f)

# ═══════════════════════════════════════════════════════════════════════════════
# SHORT PHRASE BANKS — Moroccan Social Media Manager Style
# ═══════════════════════════════════════════════════════════════════════════════

FILLERS = {
    "end": ["safi", "walo", "noss noss", "kif kif", "merra merra"],
    "doubt": ["z3ma", "wallah", "lla", "ya3ni"],
    "reaction": ["oh", "ah", "yallah", "ewa", "wakha"],
    "agreement": ["dima dima", "wakha hakkak", "mzyan", "sahbi"],
}

FRENCH_PHRASES = [
    "c'est fini", "c'est pas sérieux", "la vie", "bon courage",
    "c'est la guerre", "trop fort", "incroyable", "dommage",
    "c'est clair", "pas mal", "bref", "voilà", "allez",
    "c'est bon", "c'est tout", "fin", "point final"
]

ENGLISH_PHRASES = [
    "let's go", "no way", "game over", "clutch", "goat",
    "vibes", "this is football", "unstoppable", "locked in",
    "clean", "cold", "fire", "next level", "easy", "facts"
]

# Emotion templates — MAX 2 sentences, punchy
TEMPLATES = {
    "excitement": [
        "WALLAH! {content} Let's go! 🔥",
        "{content}. Dima dima! 💪",
        "{content}. C'est trop fort! ⚡",
        "Oh lala! {content} Safi!",
        "{content}. Locked in! 🔒",
        "{content}. Fire! 🔥",
    ],
    "disappointment": [
        "{content}. C'est fini. 😤",
        "{content}. Walo. Noss noss.",
        "Lla... {content}. Bon courage.",
        "{content}. Dommage. Safi.",
        "{content}. La vie.",
        "{content}. C'est pas sérieux.",
    ],
    "thinking": [
        "{content}. Z3ma... 🤔",
        "{content}. Kif kif, wakha.",
        "Hmm... {content}. La vie.",
        "{content}. Noss noss.",
        "{content}. Ya3ni...",
        "{content}. Bref.",
    ],
    "laughter": [
        "{content}. Hahaha walo! 😂",
        "Oh lala! {content}. C'est pas sérieux!",
        "{content}. Wallah 3ib! 😭",
        "{content}. Hada chi haja! 🤣",
        "{content}. No way! 😂",
        "{content}. C'est clair! 😭",
    ],
    "love": [
        "{content}. Dima dima! ❤️",
        "WALLAH! {content}. Trop fort! 💚",
        "{content}. C'est incroyable! ✨",
        "{content}. Had l3eb! 🙌",
        "{content}. Goat! 🐐",
        "{content}. Clean! ✨",
    ],
}

# Context-specific short phrases
ROAST_TEMPLATES = [
    "{player}, {stat}. B7al chi taxi khawi.",
    "Ya {nickname}, c'est pas sérieous. Safi.",
    "{player} f lbox: mafhemtech wach bghit ydefend wla ybki.",
    "{player}, {position} dial chi m3a9ed. Dommage.",
    "{player}. {stat}. Walo.",
    "{player} kyl3b b raso, w raso f chi blasa khra.",
    "{player}: {stat}. C'est fini.",
    "{player}. {stat}. Z3ma...",
]

HYPE_TEMPLATES = [
    "{team}. Dima dima. Let's go! 🔥",
    "WALLAH! {team} f lmatch. C'est la guerre! ⚔️",
    "{team} locked in. No way back. 💪",
    "Oh lala! {team} vibes. Unstoppable! ⚡",
    "{team}. Fire. Clean. 🔥",
    "{team}. Goat mode. 🐐",
]

BANTER_TEMPLATES = [
    "Adversaire? {content}. Walo.",
    "{content}. C'est pas sérieux. 😂",
    "{content}. Hahaha dommage!",
    "{content}. La vie, sahbi.",
    "{content}. Easy.",
]

DRAMA_TEMPLATES = [
    "{content}. C'est fini. 😤",
    "{content}. Wallah 3ib!",
    "{content}. Lla!",
    "{content}. C'est pas sérieux.",
    "{content}. Dommage. Bref.",
]


class HumanDarija:
    """Humanize bot output to short, punchy Moroccan social media style."""

    def __init__(self, squad=None):
        self.squad = squad or SQUAD
        self._roast_cache = {}
        self._hype_cache = {}

    def humanize(self, text, emotion="thinking", intensity=0.6):
        """Main entry: convert any text to short, pro Darija style."""
        if not text or intensity <= 0:
            return text

        # Step 1: Brutal shortening — max 2 sentences, cut fluff
        text = self._shorten(text)

        # Step 2: Apply emotion template
        text = self._apply_emotion(text, emotion)

        # Step 3: Strategic code-switching (French/English where it hits)
        text = self._code_switch(text, intensity)

        # Step 4: ONE filler max, at the end, context-aware
        text = self._add_filler(text, intensity)

        # Step 5: Very light imperfections (lowercase starts, occasional repeat)
        text = self._add_imperfections(text, intensity)

        return text.strip()

    def _shorten(self, text):
        """Cut to max 2 sentences. Remove fluff words."""
        # Remove filler words that make text long
        fluff = [
            r"(very|really|actually|basically|just|so|quite|rather|pretty)",
            r"(in my opinion|i think|i believe|to be honest|frankly)",
            r"(it seems that|it appears that|you know what)",
            r"(let me tell you|as you can see|as we all know)",
        ]
        for pattern in fluff:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # Clean up extra spaces
        text = re.sub(r"\s+", " ", text).strip()

        # Split sentences, keep max 2
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) > 2:
            sentences = sentences[:2]

        # Rejoin with periods
        result = ". ".join(sentences)
        if result and not result.endswith((".", "!", "?")):
            result += "."
        return result

    def _apply_emotion(self, text, emotion):
        """Wrap in short emotion template."""
        templates = TEMPLATES.get(emotion, TEMPLATES["thinking"])
        template = random.choice(templates)
        return template.format(content=text)

    def _code_switch(self, text, intensity):
        """Insert French or English phrase where it adds impact."""
        if random.random() > intensity * 0.35:
            return text

        phrases = FRENCH_PHRASES + ENGLISH_PHRASES
        phrase = random.choice(phrases)

        # 60% at end (punchline), 40% in middle (emphasis)
        if random.random() < 0.6:
            # At end — replace last period or append
            if text.endswith((".", "!", "?")):
                return f"{text[:-1]} {phrase}."
            return f"{text} {phrase}."
        else:
            # In middle — insert after first clause
            words = text.split()
            if len(words) > 4:
                mid = len(words) // 2
                words.insert(mid, phrase)
                return " ".join(words)
            return f"{text} {phrase}."

    def _add_filler(self, text, intensity):
        """Add ONE filler at the end, contextually chosen."""
        if random.random() > intensity * 0.25:
            return text

        # Choose filler based on text tone
        lowered = text.lower()
        if any(w in lowered for w in ["win", "goal", "victory", "3-0", "3-1", "let's go", "fire"]):
            filler = random.choice(FILLERS["agreement"])
        elif any(w in lowered for w in ["?", "z3ma", "hmm", "thinking"]):
            filler = random.choice(FILLERS["doubt"])
        elif any(w in lowered for w in ["oh", "ah", "wallah", "lala"]):
            filler = random.choice(FILLERS["reaction"])
        else:
            filler = random.choice(FILLERS["end"])

        # Append naturally
        if text.endswith((".", "!", "?")):
            return f"{text[:-1]} {filler}."
        return f"{text} {filler}."

    def _add_imperfections(self, text, intensity):
        """Very light typos — natural, not chaotic."""
        if random.random() > intensity * 0.15:
            return text

        # 25% chance lowercase start (casual)
        if random.random() < 0.25 and text[0].isupper():
            text = text[0].lower() + text[1:]

        # Occasional repeated punctuation for emphasis
        if random.random() < 0.1 and "!" in text:
            text = text.replace("!", "!!", 1)
        if random.random() < 0.05 and "?" in text:
            text = text.replace("?", "??", 1)

        # Very rare: dropped article (Moroccan style)
        if random.random() < 0.08:
            text = re.sub(r"(the|a|an)\s+", "", text, count=1, flags=re.IGNORECASE)

        return text

    # ═════════════════════════════════════════════════════════════════════════
    # SQUAD-AWARE CONTENT GENERATORS
    # ═════════════════════════════════════════════════════════════════════════

    def get_player(self, name):
        """Get player from squad by name (fuzzy match)."""
        name_lower = name.lower().strip()
        # Exact match
        if name_lower in self.squad:
            return self.squad[name_lower]
        # Partial match
        for key, player in self.squad.items():
            if name_lower in key or key in name_lower:
                return player
            if name_lower in player.get("name", "").lower():
                return player
        return None

    def get_roast(self, player_name, stat_line="", context=None):
        """Generate short, contextual roast for real player."""
        player = self.get_player(player_name)
        if not player:
            return f"{player_name}? Ma3rfoch. Wach 3andna f squad?"

        p_name = player.get("name", player_name)
        nickname = player.get("nickname", p_name)
        position = player.get("position", "MID")

        # Build contextual stat line if not provided
        if not stat_line and context:
            stat_line = self._build_stat_line(context)

        template = random.choice(ROAST_TEMPLATES)
        return template.format(
            player=p_name,
            nickname=nickname,
            position=position,
            stat=stat_line or "walo"
        )

    def get_hype(self, team_name="L3ERGONI"):
        """Short hype line."""
        template = random.choice(HYPE_TEMPLATES)
        return template.format(team=team_name)

    def get_banter(self, content=""):
        """Short banter line."""
        template = random.choice(BANTER_TEMPLATES)
        return template.format(content=content or "walo")

    def get_drama(self, content=""):
        """Short drama line."""
        template = random.choice(DRAMA_TEMPLATES)
        return template.format(content=content or "walo")

    def get_stats_summary(self, player_name, stats_dict):
        """One-line stat summary."""
        if not stats_dict:
            return f"{player_name}? Walo f stats. Z3ma."

        # Pick best/worst stat for punchline
        best = max(stats_dict.items(), key=lambda x: x[1])
        worst = min(stats_dict.items(), key=lambda x: x[1])

        if best[1] >= 8:
            return f"{player_name}: {best[0]} = {best[1]}. Trop fort! 📊"
        elif worst[1] <= 3:
            return f"{player_name}: {worst[0]} = {worst[1]}. C'est pas sérieux. 📉"
        else:
            return f"{player_name}: {best[0]} = {best[1]}. Kif kif. 📊"

    def get_match_result(self, our_goals, opp_goals, opp_name, result):
        """Short match result announcement."""
        if result == "W":
            return f"{our_goals}-{opp_goals} vs {opp_name}. WALLAH! Let's go! 🔥"
        elif result == "D":
            return f"{our_goals}-{opp_goals} vs {opp_name}. Noss noss. Kif kif."
        else:
            return f"{our_goals}-{opp_goals} vs {opp_name}. Dommage. C'est fini. 😤"

    def get_motm(self, player_name, rating, goals, assists):
        """Short MOTM announcement."""
        player = self.get_player(player_name)
        nickname = player.get("nickname", player_name) if player else player_name

        lines = [
            f"MOTM: {nickname}. ⭐ {rating}/10",
            f"{goals}G {assists}A. Trop fort! 🌟",
            f"{player_name}. {goals} buts, {assists} assists. Clean! ✨",
        ]
        return random.choice(lines)

    def _build_stat_line(self, context):
        """Build short stat line from context dict."""
        if not context:
            return "walo"
        parts = []
        if "goals" in context:
            parts.append(f"{context['goals']}G")
        if "assists" in context:
            parts.append(f"{context['assists']}A")
        if "rating" in context:
            parts.append(f"⭐{context['rating']}")
        return " ".join(parts) if parts else "walo"


class HumanizedDiscordBot:
    """Wrapper for Discord bot with humanized send."""

    def __init__(self, bot_instance, intensity=0.6):
        self.bot = bot_instance
        self.humanizer = HumanDarija()
        self.intensity = intensity

    async def send(self, channel, text="", image=None, filename="image.png", emotion="thinking"):
        """Send with humanization and realistic typing delay."""
        text = (text or "").strip()
        if not text and not image:
            return

        # Humanize
        if text:
            text = self.humanizer.humanize(text, emotion=emotion, intensity=self.intensity)

        # Calculate typing delay — SHORTER for pro style
        word_count = len(text.split()) if text else 0
        if word_count <= 5:
            typing_time = random.randint(1, 2)
        elif word_count <= 12:
            typing_time = random.randint(2, 4)
        else:
            typing_time = random.randint(4, 7)

        # Brief "thinking" pause for longer messages
        if len(text) > 80 and random.random() < 0.2:
            typing_time += random.randint(1, 2)

        # Simulate typing
        async with channel.typing():
            await asyncio.sleep(typing_time)

        # Send
        if image:
            image.seek(0)
            file = discord.File(image, filename=filename)
            await channel.send(text[:1900] or None, file=file)
        else:
            if len(text) <= 2000:
                await channel.send(text)
            else:
                # Split at sentence boundaries
                sentences = re.split(r"([.!?]+)", text)
                chunks = []
                current = ""
                for s in sentences:
                    if len(current) + len(s) < 1900:
                        current += s
                    else:
                        if current:
                            chunks.append(current.strip())
                        current = s
                if current:
                    chunks.append(current.strip())

                for i, chunk in enumerate(chunks):
                    await channel.send(chunk)
                    if i < len(chunks) - 1:
                        await asyncio.sleep(random.randint(1, 2))
