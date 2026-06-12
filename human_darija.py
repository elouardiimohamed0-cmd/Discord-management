"""Rachad L3ERGONI - Bad Words Only Engine v2"""
import random
import re
import json
import os

SQUAD = {}
SQUAD_FILE = os.path.join(os.path.dirname(__file__), "squad.json")
if os.path.exists(SQUAD_FILE):
    with open(SQUAD_FILE, "r", encoding="utf-8") as fp:
        SQUAD = json.load(fp)

BAD_FILLERS = [
    "walo", "safi", "z3ma", "ya3ni", "wallah", "lla", "oh", "ah", "ewa",
    "hada", "dakchi", "bla", "kifach", "kif kif", "noss noss", "merra merra",
    "khawi", "m3a9ed", "m3a9ed l3cha", "chi haja", "chi wahd", "chi nhar",
    "chi blasa", "chi m3a9ed", "chi khawi"
]

FRENCH_TRASH = [
    "c'est fini", "c'est pas serieux", "la vie", "bon courage",
    "c'est la guerre", "dommage", "c'est clair", "bref", "voila",
    "c'est bon", "c'est tout", "fin", "point final", "n'importe quoi",
    "quelle honte", "c'est nul", "c'est naze", "c'est bidon",
    "c'est du n'importe quoi", "pathetique", "ridicule", "minable"
]

ENGLISH_TRASH = [
    "game over", "no way", "trash", "garbage", "waste", "clown", "bot",
    "npc", "afk", "sellout", "inting", "trolling", "throwing", "dog",
    "dogwater", "ass", "cheeks", "buns", "mid", "average", "do better",
    "be serious", "get real", "touch grass", "log off", "uninstall",
    "delete game", "go outside", "find a job", "retire"
]

TEMPLATES = {
    "disappointment": [
        "{content}. C'est fini. 😤",
        "{content}. Walo. Noss noss.",
        "Lla... {content}. Bon courage.",
        "{content}. Dommage. Safi.",
        "{content}. La vie.",
        "{content}. C'est pas serieux.",
        "{content}. Trash. 🗑️",
        "{content}. Game over."
    ],
    "thinking": [
        "{content}. Z3ma... 🤔",
        "{content}. Kif kif, wakha.",
        "Hmm... {content}. La vie.",
        "{content}. Noss noss.",
        "{content}. Ya3ni...",
        "{content}. Bref."
    ],
    "laughter": [
        "{content}. Hahaha walo! 😂",
        "Oh lala! {content}. C'est pas serieux!",
        "{content}. Wallah 3ib! 😭",
        "{content}. Hada chi haja! 🤣",
        "{content}. No way! 😂",
        "{content}. C'est clair! 😭",
        "{content}. Clown behavior. 🤡",
        "{content}. Dogwater. 🐕"
    ],
}

ROAST_TEMPLATES = {
    "goals": [
        "{player}: {goals} goals f {games} matchs. B7al chi taxi khawi.",
        "{player} f lbox: mafhemtech wach bghit ydefend wla ybki. {goals}G f {games}m.",
        "{player} striker? Z3ma... {goals} goals f {games} matchs. C'est fini.",
        "{player} l9ahba? L9ahba dial chi m3a9ed. {goals}G f {games}m. Dommage.",
        "{player}: {goals} buts. Bref. Retire.",
        "{player} f l3erd: {goals} goals. Hada chi haja. Uninstall."
    ],
    "assists": [
        "{player}: {assists} assists. Walo. Playmaker? Z3ma...",
        "{player} maestro? Lmaestro dial chi m3a9ed l3cha. {assists}A f {games}m.",
        "{player}: {assists} passes decisives. C'est nul. Do better.",
        "{player} kyl3b b raso, w raso f chi blasa khra. {assists} assists. Trash."
    ],
    "rating": [
        "{player}: ⭐{rating}/10. Pathetique. Find a job.",
        "{player} rating {rating}? Quelle honte. Go outside.",
        "{player}: {rating}/10. C'est bidon. Log off.",
        "{player} ⭐{rating}. Ridicule. Touch grass.",
        "{player} rating {rating}. Minable. Delete game."
    ],
    "defense": [
        "{player}: {tackles} tackles. B7al chi mur dial chi dar khawya.",
        "{player} defender? Z3ma... {tackles} tackles. C'est naze.",
        "{player}: {tackles} interceptions. Walo. Defense? N'importe quoi.",
        "{player} f ldefense: {tackles} tackles. Hada chi m3a9ed. Ass."
    ],
    "general": [
        "{player}. Walo. Safi.",
        "{player}: {games} matchs, {goals}G {assists}A. Bref. Walo.",
        "{player}. C'est tout. Point final.",
        "{player} f squad? Z3ma... Walo. C'est fini.",
        "{player}: {goals}G {assists}A f {games}m. Clown. 🤡",
        "{player}. {goals} buts. {assists} passes. Dommage. Retire.",
        "{player}: {games} matchs. {goals} goals. Average. Mid.",
        "{player}. {goals}G {assists}A. Dogwater. 🐕",
        "{player}: {games}m played. {goals}G. Garbage. 🗑️",
        "{player}. {goals} goals f {games} matchs. NPC behavior."
    ],
}

MATCH_ROASTS = {
    "win_big": [
        "{score} vs {opp}. WALLAH! Adversaire chi m3a9ed l3cha. 🤡",
        "{score}. Easy. Clown team. 🗑️",
        "{score} vs {opp}. C'est nul. Adversaire trash.",
        "{score}. Dommage dial {opp}. Retire."
    ],
    "win_small": [
        "{score} vs {opp}. B7al chi match dial chi m3a9ed. Walo.",
        "{score}. Z3ma... Kif kif. Noss noss.",
        "{score} vs {opp}. C'est pas serieux. Do better.",
        "{score}. Pathetique. Win b 1 goal? Average."
    ],
    "draw": [
        "{score} vs {opp}. Noss noss. Walo. C'est fini.",
        "{score}. Kif kif. Z3ma... Bref.",
        "{score} vs {opp}. Dommage. Draw? Trash.",
        "{score}. La vie. N'importe quoi."
    ],
    "loss": [
        "{score} vs {opp}. Lla... C'est fini. Bon courage. 😤",
        "{score}. Dommage. {opp} ferk fina. Walo.",
        "{score} vs {opp}. Pathetique. Hada chi haja. 🤡",
        "{score}. Trash. Garbage. Delete game. 🗑️",
        "{score} vs {opp}. Ridicule. Minable. Retire.",
        "{score}. Clown performance. Dogwater. 🐕",
        "{score} vs {opp}. N'importe quoi. C'est naze.",
        "{score}. Ass. Cheeks. Buns. Uninstall."
    ],
}

MOTM_ROASTS = [
    "MOTM: {player}. ⭐{rating}. Z3ma... Best of the worst. 🤡",
    "{player} MOTM. ⭐{rating}. C'est pas serieux. Clown team.",
    "MOTM {player}. ⭐{rating}. Walo. Best of trash. 🗑️",
    "{player} best player. ⭐{rating}. Dommage. Still mid.",
    "MOTM: {player}. ⭐{rating}. Hada chi haja. Average at best.",
    "{player} ⭐{rating}. MOTM? Z3ma... C'est bidon."
]


class HumanDarija:
    """ONLY bad words, roasting, trash talk. No positivity."""

    def __init__(self, squad=None):
        self.squad = squad or SQUAD

    def humanize(self, text, emotion="disappointment", intensity=0.7):
        if not text or intensity <= 0:
            return text
        text = self._shorten(text)
        text = self._apply_emotion(text, emotion)
        text = self._code_switch(text, intensity)
        text = self._add_filler(text, intensity)
        text = self._add_imperfections(text, intensity)
        return text.strip()

    def _shorten(self, text):
        # Remove fluff words
        fluff = [
            r"\b(very|really|actually|basically|just|so|quite|rather|pretty)\b",
            r"\b(in my opinion|i think|i believe|to be honest|frankly)\b",
            r"\b(it seems that|it appears that|you know what)\b",
            r"\b(let me tell you|as you can see|as we all know)\b",
        ]
        for pattern in fluff:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()
        # Keep max 2 sentences
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) > 2:
            sentences = sentences[:2]
        result = ". ".join(sentences)
        if result and not result.endswith((".", "!", "?")):
            result += "."
        return result

    def _apply_emotion(self, text, emotion):
        templates = TEMPLATES.get(emotion, TEMPLATES["thinking"])
        template = random.choice(templates)
        return template.format(content=text)

    def _code_switch(self, text, intensity):
        if random.random() > intensity * 0.35:
            return text
        phrases = FRENCH_TRASH + ENGLISH_TRASH
        phrase = random.choice(phrases)
        if random.random() < 0.6:
            if text.endswith((".", "!", "?")):
                return f"{text[:-1]} {phrase}."
            return f"{text} {phrase}."
        else:
            words = text.split()
            if len(words) > 4:
                mid = len(words) // 2
                words.insert(mid, phrase)
                return " ".join(words)
            return f"{text} {phrase}."

    def _add_filler(self, text, intensity):
        if random.random() > intensity * 0.25:
            return text
        lowered = text.lower()
        if any(w in lowered for w in ["win", "goal", "victory", "3-0", "3-1", "let's go", "fire"]):
            filler = random.choice(["wakha", "mzyan", "dima dima"])
        elif any(w in lowered for w in ["?", "z3ma", "hmm", "thinking"]):
            filler = random.choice(["z3ma", "wallah", "lla"])
        elif any(w in lowered for w in ["oh", "ah", "wallah", "lala"]):
            filler = random.choice(["oh", "ah", "yallah", "ewa"])
        else:
            filler = random.choice(BAD_FILLERS)
        if text.endswith((".", "!", "?")):
            return f"{text[:-1]} {filler}."
        return f"{text} {filler}."

    def _add_imperfections(self, text, intensity):
        if random.random() > intensity * 0.15:
            return text
        if random.random() < 0.25 and text[0].isupper():
            text = text[0].lower() + text[1:]
        if random.random() < 0.1 and "!" in text:
            text = text.replace("!", "!!", 1)
        if random.random() < 0.05 and "?" in text:
            text = text.replace("?", "??", 1)
        if random.random() < 0.08:
            text = re.sub(r"\b(the|a|an)\s+", "", text, count=1, flags=re.IGNORECASE)
        return text

    def get_player(self, name):
        name_lower = name.lower().strip()
        if name_lower in self.squad:
            return self.squad[name_lower]
        for key, player in self.squad.items():
            if name_lower in key or key in name_lower:
                return player
            if name_lower in player.get("name", "").lower():
                return player
        return None

    def get_roast(self, player_name, stat_line="", context=None):
        player = self.get_player(player_name)
        if not player:
            return f"{player_name}? Ma3rfoch. Wach 3andna f squad?"
        p_name = player.get("name", player_name)
        nickname = player.get("nickname", p_name)
        position = player.get("position", "MID")
        if not stat_line and context:
            stat_line = self._build_stat_line(context)
        template = random.choice(ROAST_TEMPLATES["general"])
        return template.format(
            player=p_name, nickname=nickname, position=position,
            stat=stat_line or "walo", games=context.get("games", 0) if context else 0,
            goals=context.get("goals", 0) if context else 0,
            assists=context.get("assists", 0) if context else 0,
            rating=context.get("rating", 0) if context else 0,
            tackles=context.get("tackles", 0) if context else 0
        )

    def get_match_result(self, our_goals, opp_goals, opp_name, result):
        if result == "W":
            diff = our_goals - opp_goals
            key = "win_big" if diff >= 3 else "win_small"
        elif result == "D":
            key = "draw"
        else:
            key = "loss"
        template = random.choice(MATCH_ROASTS[key])
        return template.format(score=f"{our_goals}-{opp_goals}", opp=opp_name)

    def get_motm(self, player_name, rating, goals, assists):
        player = self.get_player(player_name)
        nickname = player.get("nickname", player_name) if player else player_name
        template = random.choice(MOTM_ROASTS)
        return template.format(player=nickname, rating=f"{rating:.1f}")

    def get_stats_summary(self, player_name, stats_dict):
        if not stats_dict:
            return f"{player_name}? Walo f stats. Z3ma."
        best = max(stats_dict.items(), key=lambda x: x[1])
        worst = min(stats_dict.items(), key=lambda x: x[1])
        if best[1] >= 8:
            return f"{player_name}: {best[0]} = {best[1]}. Trop fort! 📊"
        elif worst[1] <= 3:
            return f"{player_name}: {worst[0]} = {worst[1]}. C'est pas serieux. 📉"
        else:
            return f"{player_name}: {best[0]} = {best[1]}. Kif kif. 📊"

    def _build_stat_line(self, context):
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
    def __init__(self, bot_instance, intensity=0.7):
        self.bot = bot_instance
        self.humanizer = HumanDarija()
        self.intensity = intensity

    async def send(self, channel, text="", image=None, filename="image.png", emotion="disappointment"):
        text = (text or "").strip()
        if not text and not image:
            return
        if text:
            text = self.humanizer.humanize(text, emotion=emotion, intensity=self.intensity)
        word_count = len(text.split()) if text else 0
        if word_count <= 5:
            typing_time = random.randint(1, 2)
        elif word_count <= 12:
            typing_time = random.randint(2, 4)
        else:
            typing_time = random.randint(4, 7)
        if len(text) > 80 and random.random() < 0.2:
            typing_time += random.randint(1, 2)
        async with channel.typing():
            await asyncio.sleep(typing_time)
        if image:
            image.seek(0)
            file = discord.File(image, filename=filename)
            await channel.send(text[:1900] or None, file=file)
        else:
            if len(text) <= 2000:
                await channel.send(text)
            else:
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
