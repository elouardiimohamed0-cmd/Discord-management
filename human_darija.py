"""
HUMAN DARIJA ENGINE v2.0 — Makes your Discord bot talk like a real Moroccan
Post-processing layer that transforms robotic AI output into authentic human speech.

Drop-in replacement: Just wrap your existing AI output with HumanDarija.humanize()
"""

import random
import re
import asyncio
from typing import Optional


class HumanDarija:
    """
    Transforms robotic Darija into authentic Moroccan human speech.
    This is a POST-PROCESSING layer — wrap your existing AI output with this.
    """

    def __init__(self):
        # Authentic Moroccan fillers (from real WhatsApp/Twitter analysis)
        self.fillers = [
            "safi", "ah", "wa", "yallah", "ewa", "oh", "lla", 
            "ayeh", "wayeh", "hmm", "hh", "hahaha", "oh wow", "ya salam",
            "bessa7", "sara7a", "f lwa9i3", "3la 7sab", "wakha hakkak",
            "ghir", "tani", "daba", "men ba3d", "merra merra", "z3ma",
            "wallah", "ya3ni", "b7al", "f7al", "3lach", "walo",
            "safi 3iyet", "daba walo", "ghadi nchoufou", "kif kif",
            "noss noss", "dima dima", "walo men walo", "ma3ndch shi",
            "sir t9awed", "diri 3qlek", "t7ashsham", "kaykhdem",
            "mashi 3adi", "9awi bzf", "khayb bzf", "mzyan bzf",
            "zwin bzf", "d3if bzf", "3ib w 7chouma", "ma3endna walo",
        ]

        # Natural sentence starters
        self.starters = [
            "", "", "", "ana", "rah", "wach", "3lach", "kan", "ghadi", 
            "koun", "khlini", "sir", "nta", "nti", "hadi", "hadchi", "dakchi",
            "b7al", "f7al", "3la", "men", "w", "o", "walakin", "ila",
            "safi", "wakha", "yallah", "ewa", "daba", "tani", "men ba3d",
        ]

        # English words Moroccans naturally drop in chat
        self.english_drops = [
            "ok", "okay", "sorry", "please", "thanks", "hello", "bye",
            "good", "bad", "nice", "cool", "happy", "sad", "love", "hate",
            "problem", "message", "phone", "email", "facebook", "google",
            "youtube", "wifi", "internet", "computer", "pizza", "taxi",
            "hotel", "restaurant", "weekend", "meeting", "project",
            "party", "birthday", "manager", "password", "online", "offline",
            "game", "play", "win", "loss", "draw", "team", "player",
            "goal", "shot", "pass", "defense", "attack", "midfield",
            "rating", "stats", "match", "MVP", "OP", "GG", "WP", "AFK",
        ]

        # French words (very common in Moroccan football chat)
        self.french_drops = [
            "merci", "pardon", "excuse", "bon", "mauvais", "tres",
            "beaucoup", "un peu", "oui", "non", "avec", "sans", "pour",
            "et", "ou", "mais", "si", "alors", "donc", "parce", "quoi",
            "qui", "quand", "comment", "pourquoi", "combien",
            "cafe", "telephone", "portable", "ordinateur", "internet",
            "probleme", "question", "reponse", "idee", "travail", "maison",
            "voiture", "argent", "temps", "jour", "nuit", "soir", "matin",
            "niveau", "performance", "resultat", "tirs", "faute",
            "formation", "tactique", "defense", "attaque", "milieu",
            "equipe", "joueur", "match", "buteur", "gardien", "arbitre",
            "carton", "hors-jeu", "corner", "penalty", "remplacement",
        ]

        # Emoji patterns by emotion
        self.emoji_patterns = {
            'excitement': ['🔥', '💪', '⚽', '🏆', '⭐', '🌟', '👏', '🎉'],
            'disappointment': ['💀', '😭', '😤', '🤦', '😑', '🤷', '🙄'],
            'laughter': ['😂', '🤣', '💀', '☠️', '😆', '😅'],
            'thinking': ['🤔', '🤨', '🧐', '😏', '🤷'],
            'love': ['❤️', '💖', '💕', '🫶', '💯'],
            'anger': ['😡', '🤬', '💢', '👿', '😤'],
        }

    def add_fillers(self, text: str, intensity: float = 0.4) -> str:
        """Add natural Moroccan fillers before/after sentences."""
        if random.random() > intensity or not text:
            return text

        filler = random.choice(self.fillers)
        position = random.choice(['before', 'after', 'both', 'mid'])

        if position == 'before':
            return f"{filler}, {text}"
        elif position == 'after':
            return f"{text}, {filler}"
        elif position == 'both':
            return f"{filler}, {text}, {filler}"
        else:  # mid
            sentences = text.split('. ')
            if len(sentences) > 1:
                mid = len(sentences) // 2
                sentences[mid] = f"{filler}, {sentences[mid]}"
                return '. '.join(sentences)
            return f"{filler}, {text}"

    def add_typing_imperfections(self, text: str) -> str:
        """Add human typing quirks."""
        if not text:
            return text

        # 15% chance lowercase start
        if random.random() < 0.15:
            text = text[0].lower() + text[1:]

        # 8% chance repeat letters
        words = text.split()
        result = []
        for word in words:
            if random.random() < 0.08 and len(word) > 3:
                if word[-1] in 'aeiou3o7':
                    word = word + word[-1] * random.randint(1, 2)
            result.append(word)
        text = ' '.join(result)

        # 10% multiple punctuation
        if random.random() < 0.10:
            if '!' in text:
                text = text.replace('!', '!!' if random.random() > 0.5 else '!!!')
            if '?' in text:
                text = text.replace('?', '??' if random.random() > 0.5 else '???')

        # 5% ellipsis
        if random.random() < 0.05 and '.' in text:
            text = text.replace('.', '...', 1)

        # 12% drop space after comma
        if random.random() < 0.12:
            text = text.replace(', ', ',', 1)

        return text

    def code_switch(self, text: str, probability: float = 0.20) -> str:
        """Naturally mix English/French words."""
        words = text.split()
        result = []

        for i, word in enumerate(words):
            if random.random() < probability and len(word) > 3:
                if random.random() < 0.6:
                    drop = random.choice(self.english_drops)
                else:
                    drop = random.choice(self.french_drops)

                if 0 < i < len(words) - 1 and word.isalpha():
                    result.append(drop)
                    continue
            result.append(word)

        return ' '.join(result)

    def add_mid_sentence_correction(self, text: str) -> str:
        """Add authentic mid-sentence correction."""
        if random.random() < 0.08:
            corrections = [
                "* correction ", "* walo ", "* ma3ndch ", "* z3ma ",
                "* b7al ", "* ya3ni ", "* wallah ",
            ]
            sentences = text.split('. ')
            if len(sentences) > 1:
                idx = random.randint(0, len(sentences) - 2)
                sentences[idx] += random.choice(corrections) + sentences[idx + 1]
                sentences.pop(idx + 1)
                return '. '.join(sentences)
        return text

    def add_reaction_emoji(self, text: str, emotion: str = 'excitement') -> str:
        """Add contextual emoji."""
        emojis = self.emoji_patterns.get(emotion, self.emoji_patterns['excitement'])

        if random.random() < 0.70:
            emoji = random.choice(emojis)
            position = random.choice(['end', 'mid', 'start'])

            if position == 'end':
                text = f"{text} {emoji}"
            elif position == 'start':
                text = f"{emoji} {text}"
            else:
                words = text.split()
                if len(words) > 3:
                    mid = len(words) // 2
                    words.insert(mid, emoji)
                    text = ' '.join(words)

        return text

    def abbreviate_common(self, text: str) -> str:
        """Use Moroccan chat abbreviations."""
        abbreviations = {
            r'wakha': ['wakha', 'wkh', 'wakha'],
            r'safi': ['safi', 'sf', 'safi'],
            r'ma3ndch': ['ma3ndch', 'm3ndch', 'ma3ndch'],
            r'walo': ['walo', 'wl', 'walo'],
            r'ghadi': ['ghadi', 'ghd', 'ghadi'],
            r'daba': ['daba', 'db', 'daba'],
            r'nta': ['nta', 'nt', 'nta'],
            r'nti': ['nti', 'nt', 'nti'],
            r'7na': ['7na', '7n', '7na'],
            r'ntoma': ['ntoma', 'ntm', 'ntoma'],
        }

        for pattern, replacements in abbreviations.items():
            if random.random() < 0.15:
                text = re.sub(pattern, random.choice(replacements), text, count=1)

        return text

    def add_street_slang(self, text: str) -> str:
        """Add authentic Moroccan street football slang."""
        slang_phrases = [
            "wakha hakkak", "z3ma", "ya3ni", "wallah", "b7al hdiya",
            "dima dima", "noss noss", "kif kif", "merra merra",
            "safi 3iyet", "walo men walo", "ma3ndch shi", "sir t9awed",
            "diri 3qlek", "t7ashsham", "kaykhdem", "mashi 3adi",
            "9awi bzf", "khayb bzf", "mzyan bzf", "zwin bzf",
            "d3if bzf", "3ib w 7chouma", "ma3endna walo",
        ]

        if random.random() < 0.25:
            slang = random.choice(slang_phrases)
            position = random.choice(['start', 'end', 'mid'])

            if position == 'start':
                text = f"{slang}, {text}"
            elif position == 'end':
                text = f"{text}, {slang}"
            else:
                words = text.split()
                if len(words) > 4:
                    mid = len(words) // 2
                    words.insert(mid, slang)
                    text = ' '.join(words)

        return text

    def humanize(self, text: str, emotion: str = 'excitement', 
                 intensity: float = 0.7) -> str:
        """
        Transform robotic text into authentic Moroccan human speech.

        Args:
            text: The AI-generated Darija text
            emotion: 'excitement', 'disappointment', 'laughter', 'thinking', 'love', 'anger'
            intensity: 0.0-1.0 how human to make it

        Returns:
            Humanized text string
        """
        if not text or len(text) < 5:
            return text

        text = self.add_fillers(text, intensity=0.4 * intensity)
        text = self.add_typing_imperfections(text)
        text = self.code_switch(text, probability=0.15 * intensity)
        text = self.add_mid_sentence_correction(text)
        text = self.add_reaction_emoji(text, emotion=emotion)
        text = self.abbreviate_common(text)
        text = self.add_street_slang(text)
        text = ' '.join(text.split())  # cleanup

        return text

    def humanize_match_report(self, text: str, result: str = 'W') -> str:
        """Humanize match report based on result."""
        emotion_map = {'W': 'excitement', 'L': 'disappointment', 'D': 'thinking'}
        emotion = emotion_map.get(result, 'excitement')
        return self.humanize(text, emotion=emotion, intensity=0.8)

    def humanize_roast(self, text: str) -> str:
        """Humanize roast text (more aggressive, more laughter)."""
        return self.humanize(text, emotion='laughter', intensity=0.9)

    def humanize_hype(self, text: str) -> str:
        """Humanize hype text (maximum energy)."""
        return self.humanize(text, emotion='excitement', intensity=0.95)

    def humanize_banter(self, text: str) -> str:
        """Humanize banter (toxic but funny)."""
        return self.humanize(text, emotion='laughter', intensity=0.85)

    def humanize_praise(self, text: str) -> str:
        """Humanize praise (genuine but not robotic)."""
        return self.humanize(text, emotion='love', intensity=0.6)


# ============================================================
# DISCORD BOT INTEGRATION — HumanizedDiscordBot
# ============================================================

class HumanizedDiscordBot:
    """
    Wrapper that adds humanization + realistic typing delays to your bot.
    """

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.humanizer = HumanDarija()
        self.user_contexts = {}

    async def send_humanized(self, channel, text: str, emotion: str = 'excitement',
                            image=None, filename: str = "image.png",
                            typing_time: Optional[int] = None):
        """
        Send a humanized message with realistic typing delay.

        Usage: Replace `await ctx.send(text)` with:
            await bot_wrapper.send_humanized(ctx.channel, text, emotion='excitement')
        """
        if typing_time is None:
            word_count = len(text.split())
            if word_count <= 3:
                typing_time = random.randint(1, 3)
            elif word_count <= 8:
                typing_time = random.randint(3, 7)
            else:
                typing_time = random.randint(7, 15)

        if len(text) > 100 and random.random() < 0.3:
            typing_time += random.randint(2, 5)

        async with channel.typing():
            await asyncio.sleep(typing_time)

        humanized = self.humanizer.humanize(text, emotion=emotion)

        if image:
            image.seek(0)
            import discord
            file = discord.File(image, filename=filename)
            await channel.send(humanized[:1900] or None, file=file)
        else:
            while humanized:
                chunk, humanized = humanized[:2000], humanized[2000:]
                await channel.send(chunk)

    async def on_message_humanized(self, message):
        """Handle incoming message with humanized response."""
        if message.author == self.bot.user:
            return

        intent = self._detect_intent(message.content)
        emotion = self._detect_emotion(message.content)
        response = self._generate_response(intent, emotion)
        await self.send_humanized(message.channel, response, emotion=emotion)

    def _detect_intent(self, message: str) -> str:
        msg = message.lower()
        if any(w in msg for w in ['salam', 'ahlan', 'sba7', 'msa', 'hello', 'hi']):
            return 'greeting'
        elif any(w in msg for w in ['chokran', 'shokran', 'merci', 'thanks']):
            return 'thanks'
        elif any(w in msg for w in ['bye', 'bslama', 'thella', 'au revoir']):
            return 'farewell'
        elif '?' in msg or msg.startswith(('wach', '3lach', 'fin', 'ch7al', 'imta')):
            return 'question'
        else:
            return 'statement'

    def _detect_emotion(self, message: str) -> str:
        msg = message.lower()
        if any(w in msg for w in ['fr7an', 'zwin', 'mezian', 'good', 'happy', 'great']):
            return 'excitement'
        elif any(w in msg for w in ['khayb', 'mkta2eb', '3yit', 'bad', 'sad']):
            return 'disappointment'
        elif any(w in msg for w in ['haha', 'lol', 'mdr', '😂']):
            return 'laughter'
        else:
            return 'excitement'

    def _generate_response(self, intent: str, emotion: str) -> str:
        responses = {
            'greeting': [
                "Salam! Kidayr?",
                "Ahlan! Wach kat3awd?",
                "Sba7 nnour! Kif rask?",
                "Wach nta bikhir?",
            ],
            'thanks': [
                "Walo! 3la rwah!",
                "Machi mochkil! Hania!",
                "Safi! Ghir 3la khater!",
            ],
            'farewell': [
                "Bslama! Nchoufouk men ba3d!",
                "Thella! Yallah!",
                "Safi! Bslama 3likom!",
            ],
            'question': [
                "Ma3rftch! Khlini nfekker!",
                "Wakha! Nchouf!",
                "Safi! Ghadi n9oul lik!",
            ],
            'statement': [
                "Safi fhemt!",
                "Wakha nchouf!",
                "KanDen hadchi!",
                "Ma3rftch!",
            ],
        }
        return random.choice(responses.get(intent, responses['statement']))
