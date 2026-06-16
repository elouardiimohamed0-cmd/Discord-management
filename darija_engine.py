"""Darija language engine - Casablanca street football banter.
Built with patterns inspired by DODa (Darija Open Dataset).
Uses Latin Darija transcription: 3=ع, 7=ح, 9=ق, 5=خ, 8=ه, 2=ء
"""
import random
from typing import List, Dict, Optional
from dataclasses import dataclass

# DODa-inspired vocabulary bank
VOCAB = {
    "insults": [
        "7mar", "zamel", "3arss", "bni9", "khasi", "m9ewed", "fer9", "b7al chi 7wayej",
        "weld l9a7ba", "s7ab lmo3jiza", "fer9 lfer9", "3ayel", "s7ab l3ayla",
    ],
    "reactions_bad": [
        "wakha", "yak", "oh lala", "a si mohamed", "a 3chiri", "ya 3ami",
        "wakha a khay", "oh 7bibi", "a sidi", "ya 7mar", "wakha a 7mar",
    ],
    "reactions_shock": [
        "a 3chiri", "oh lala", "ya 3ami", "wakha", "a sidi", "oh 7bibi",
        "ya weld l9a7ba", "a 7bibi", "wakha a khay", "ya zamel",
    ],
    "praise": [
        "3ziz", "wa3er", "s7ab", "m3alem", "m3allam", "s7i7", "nadi",
        "mochkil", "b7al lferrari", "mochkil f l3b", "s7ab l3b",
    ],
    "football_terms": [
        "tir", "passe", "dribble", "takle", "defense", "goal", "assist",
        "match", "liga", "champion", "botola", "coupe", "tournoi",
        "l3b", "tiran", "terain", "gardian", "defans", "milieu", "attak",
    ],
    "casablanca_slang": [
        "khay", "3chiri", "s7abi", "7bibi", "a sidi", "a 3ami", "ya zin",
        "wakha", "yak", "safi", "wakha a khay", "3ziz 3liya", "s7ab",
        "nadi", "m3alem", "m3allam", "s7i7", "b7al", "b7al chi", "f7al",
    ],
    "intensifiers": [
        "bzzaf", "3er", "mazal", "mazal mazal", "b7al chi", "f7al",
        "chi", "wa3er", "s7ab", "m3alem", "wa3er bzzaf", "s7ab bzzaf",
    ],
}

@dataclass
class PhraseTemplate:
    category: str
    templates: List[str]
    severity: int  # 1-10

# Phrase database - 99% roast, 1% serious
PHRASE_DB = {
    # === PLAYER ROASTS (performance based) ===
    "roast_low_rating": PhraseTemplate(
        "roast",
        [
            "wakha {nickname}, rating ديالك {rating}؟ هادا رقم ديال لاعب كيبيع لبناني ف l7anout.",
            "{nickname} a khay, rating {rating}؟ حتى lbotola كتضحك عليك.",
            "a {nickname}, rating ديالك {rating}؟ الكورة كانت كتشوفك وكتبدل الطريق.",
            "{nickname} ya 7mar, {rating} rating؟ حتى lgardian ديال lfar9 l5or كيضرب أحسن منك.",
            "wakha {nickname}, {rating}؟ rating ديالك محتاج محامي باش يدافع عليه.",
            "{nickname} a 3chiri, {rating} rating؟ الخصم كان مرتاح ملي شافك ف terain.",
            "a {nickname}, {rating}؟ حتى chi 3ayel f derb sultan كيلعب أحسن منك.",
            "{nickname} ya zamel, rating {rating}؟ درتي assist للخصم أكثر من الفريق.",
            "wakha a khay {nickname}, {rating}؟ كتبان ف terain ب7al chi far9a f l3ers.",
            "{nickname} a sidi, {rating} rating؟ حتى lbotola كتسول عليك: واش هادا لاعب ولا جا غير السميّة ديالك؟",
        ],
        8
    ),
    "roast_zero_stats": PhraseTemplate(
        "roast",
        [
            "{nickname} a 7mar, {stat}={value}؟ حتى l3ayel ديال 7 snin كيدير أحسن منك.",
            "a {nickname}, {stat}={value}؟ واش كنتي f terain ولا كتشرب atay f lbar؟",
            "{nickname} ya zamel, {stat}={value}؟ حتى lfar9a ديال l5or كتضحك عليك.",
            "wakha {nickname}, {stat}={value}؟ آش هاد الكارثة؟",
            "{nickname} a 3chiri, {stat}={value}؟ كتبان ب7al chi 7wayej ف terain.",
            "a {nickname}, {stat}={value}؟ حتى lbotola كتسول: واش هادا لاعب ولا spectateur؟",
            "{nickname} ya khay, {stat}={value}؟ درتي l9ahba l3onwan ديال lmatch.",
            "wakha a sidi {nickname}, {stat}={value}؟ rating ديالك محتاج chi 3ibara كبيرة.",
            "{nickname} a 7bibi, {stat}={value}؟ الخصم كان كيستناك b7al chi hadiya.",
            "a {nickname}, {stat}={value}؟ حتى l3ayel ديال sidi bernoussi كيلعب أحسن.",
        ],
        9
    ),
    "roast_high_possession_lost": PhraseTemplate(
        "roast",
        [
            "{nickname} a 7mar, possession lost {value}؟ كتدي lball l3nd l5or b7al chi livreur.",
            "a {nickname}, {value} possession lost؟ حتى chi zbel ماشي بحالك ف terain.",
            "{nickname} ya zamel, {value}؟ كتدي lball l3nd l5or أكثر من l3ayel ديالو.",
            "wakha {nickname}, possession lost {value}؟ آش هاد الكارثة؟",
            "{nickname} a 3chiri, {value} possession lost؟ كتبان ب7al chi 7wayej.",
            "a {nickname}, {value}؟ حتى lbotola كتسول: واش هادا لاعب ولا جاسوس؟",
            "{nickname} ya khay, {value} possession lost؟ درتي l9ahba l3onwan.",
            "wakha a sidi {nickname}, {value}؟ lball كتجري منك أسرع من chi 3ayel.",
            "{nickname} a 7bibi, {value}؟ الخصم كان كيستناك b7al chi 3ayel.",
            "a {nickname}, {value} possession lost؟ حتى l3ayel ديال derb sultan كيلعب أحسن.",
        ],
        9
    ),
    "roast_fraud": PhraseTemplate(
        "roast",
        [
            "{nickname} ya 7mar, fraud score {score}؟ واش كنتي لاعب ولا جا غير السميّة ديالك؟",
            "a {nickname}, fraud score {score}؟ حتى l3ayel ديال 7 snin كيدير أحسن.",
            "{nickname} ya zamel, {score} fraud؟ كتبان b7al chi far9a f l3ers.",
            "wakha {nickname}, fraud {score}؟ آش هاد الكارثة؟",
            "{nickname} a 3chiri, {score} fraud؟ كتدي lball l3nd l5or أكثر من l3ayel ديالو.",
            "a {nickname}, {score} fraud؟ حتى lbotola كتسول: واش هادا لاعب ولا spectateur؟",
            "{nickname} ya khay, {score} fraud؟ درتي l9ahba l3onwan ديال lmatch.",
            "wakha a sidi {nickname}, {score}؟ lball كتجري منك أسرع من chi 3ayel.",
            "{nickname} a 7bibi, {score} fraud؟ الخصم كان كيستناك b7al chi hadiya.",
            "a {nickname}, {score}؟ حتى l3ayel ديال sidi bernoussi كيلعب أحسن.",
        ],
        10
    ),
    "roast_ghost": PhraseTemplate(
        "roast",
        [
            "{nickname} ya 7mar, {games} games؟ واش كنتي لاعب ولا ghost؟",
            "a {nickname}, {games} games؟ حتى l3ayel ديال 7 snin كيلعب أكثر منك.",
            "{nickname} ya zamel, {games}؟ كتبان b7al chi far9a f l3ers.",
            "wakha {nickname}, {games} games؟ آش هاد الكارثة؟",
            "{nickname} a 3chiri, {games} games؟ كتدي lball l3nd l5or أكثر من l3ayel ديالو.",
            "a {nickname}, {games} games؟ حتى lbotola كتسول: واش هادا لاعب ولا جاسوس؟",
            "{nickname} ya khay, {games} games؟ درتي l9ahba l3onwan ديال lmatch.",
            "wakha a sidi {nickname}, {games}؟ lball كتجري منك أسرع من chi 3ayel.",
            "{nickname} a 7bibi, {games} games؟ الخصم كان كيستناك b7al chi hadiya.",
            "a {nickname}, {games} games؟ حتى l3ayel ديال sidi bernoussi كيلعب أحسن.",
        ],
        10
    ),

    # === MVP / PRAISE (1% serious) ===
    "praise_mvp": PhraseTemplate(
        "praise",
        [
            "{nickname} ya m3alem, {stat}={value}؟ وااعر بزاااف!",
            "a {nickname}, {stat}={value}؟ س7اب ل3ب، كتبان ب7ال فراري ف terain.",
            "{nickname} ya wa3er, {value} {stat}؟ ماشي مشكل، كتسوق lmatch ب7ال hamilton.",
            "wakha {nickname}, {stat}={value}؟ نادي، كتضرب أحسن من chi 9a7ba.",
            "{nickname} a 3ziz, {value}؟ كتبان b7al chi champion f lbotola.",
        ],
        2
    ),
    "praise_carry": PhraseTemplate(
        "praise",
        [
            "{nickname} ya m3alem, كتحمل lfar9a ب7ال chi king؟ وااعر!",
            "a {nickname}, carry score {score}؟ ماشي مشكل، كتسوق lmatch ب7ال hamilton.",
            "{nickname} ya wa3er, {score} carry؟ كتضرب أحسن من chi 9a7ba.",
            "wakha {nickname}, carry {score}؟ نادي، كتبان b7al chi champion.",
            "{nickname} a 3ziz, {score}؟ كتحمل lfar9a b7al chi 3ziz.",
        ],
        2
    ),

    # === GENERAL BANTER ===
    "match_reaction_bad": PhraseTemplate(
        "roast",
        [
            "wakha a khay, lmatch ديال {team}؟ آش هاد الكارثة؟",
            "a {team} ya 7mar, كتضربو b7al chi 3ayel f derb sultan.",
            "{team} ya zamel, lmatch ديالكم؟ حتى l3ayel ديال 7 snin كيلعب أحسن.",
            "wakha {team}, lmatch؟ كتبانو b7al chi far9a f l3ers.",
            "a {team} a 3chiri, lmatch ديالكم؟ آش هاد الكارثة؟",
        ],
        7
    ),
    "match_reaction_good": PhraseTemplate(
        "praise",
        [
            "wakha a khay, lmatch ديال {team}؟ وااعر بزاااف!",
            "a {team} ya m3alem, كتضربو b7al chi champion.",
            "{team} ya wa3er, lmatch ديالكم؟ س7اب ل3ب.",
            "wakha {team}, lmatch؟ كتبانو b7ال فراري.",
            "a {team} a 3ziz, لmatch ديالكم؟ نادي.",
        ],
        3
    ),

    # === STAT OF THE DAY ===
    "stat_of_day_roast": PhraseTemplate(
        "roast",
        [
            "STAT OF THE DAY: {nickname} - {stat}={value}. a {nickname} ya 7mar, واش كنتي لاعب ولا جا غير السميّة ديالك؟",
            "STAT OF THE DAY: {nickname} - {stat}={value}. {nickname} a 3chiri, آش هاد الكارثة؟",
            "STAT OF THE DAY: {nickname} - {stat}={value}. a {nickname}, حتى l3ayel ديال sidi bernoussi كيلعب أحسن.",
            "STAT OF THE DAY: {nickname} - {stat}={value}. {nickname} ya zamel, rating ديالك محتاج محامي.",
            "STAT OF THE DAY: {nickname} - {stat}={value}. a {nickname} a sidi, الكورة كانت كتشوفك وكتبدل الطريق.",
        ],
        9
    ),
    "stat_of_day_mvp": PhraseTemplate(
        "praise",
        [
            "STAT OF THE DAY: {nickname} - {stat}={value}. {nickname} ya m3alem, وااعر بزاااف!",
            "STAT OF THE DAY: {nickname} - {stat}={value}. a {nickname}, كتبان b7ال فراري ف terain.",
            "STAT OF THE DAY: {nickname} - {stat}={value}. {nickname} ya wa3er, س7اب ل3ب.",
            "STAT OF THE DAY: {nickname} - {stat}={value}. a {nickname} a 3ziz, نادي.",
            "STAT OF THE DAY: {nickname} - {stat}={value}. {nickname} ya khay, كتضرب أحسن من chi 9a7ba.",
        ],
        2
    ),

    # === RANKINGS ===
    "rankings_intro": PhraseTemplate(
        "general",
        [
            "wakha a khay, hia lclassement ديال lfar9a:",
            "a 3chiri, hia lclassement، شوف واش كاين شي 7mar:",
            "yak a sidi, hia lclassement ديال l3ayel:",
            "wakha, hia lclassement، شوف chi wa7ed ماشي f blaso:",
        ],
        5
    ),
    "rankings_entry": PhraseTemplate(
        "general",
        [
            "{rank}. {nickname} - {stat}={value} (a {nickname} ya {insult}, {comment})",
            "{rank}. {nickname} - {stat}={value} ({comment})",
            "{rank}. {nickname} - {value} {stat} ({comment})",
        ],
        5
    ),

    # === CLUB ===
    "club_summary": PhraseTemplate(
        "general",
        [
            "wakha a khay, lfar9a ديالنا {club_name}:",
            "a 3chiri, hia lfar9a ديال {club_name}:",
            "yak a sidi, {club_name}:",
        ],
        4
    ),

    # === WHO SOLD ===
    "who_sold": PhraseTemplate(
        "roast",
        [
            "{nickname} ya 7mar, كتدي lmatch l3nd l5or ب7ال chi livreur. واش كنتي لاعب ولا جاسوس؟",
            "a {nickname}, كتدي lball l3nd l5or أكثر من l3ayel ديالو. آش هاد الكارثة؟",
            "{nickname} ya zamel, حتى l3ayel ديال 7 snين كيلعب أحسن منك. درتي l9ahba l3onوان.",
            "wakha {nickname}, lmatch ديالك؟ كتبان b7al chi far9a f l3ers.",
            "a {nickname} a 3chiri, كتدي lmatch l3nd l5or. rating ديالك محتاج محامي.",
        ],
        9
    ),

    # === GREETINGS ===
    "greeting": PhraseTemplate(
        "general",
        [
            "wakha a khay, {bot_name} hna:",
            "a 3chiri, {bot_name} وصل:",
            "yak a sidi, {bot_name} ف l7anout:",
            "wakha, {bot_name} جا باش يضرب l3ayel:",
            "a 7bibi, {bot_name} hna باش يحكم f lfar9a:",
        ],
        3
    ),

    # === COMMAND RESPONSES ===
    "command_error": PhraseTemplate(
        "roast",
        [
            "a 7mar, command ماشي صحيح. واش كتقرأ ولا كتشوف ب7ال chi 3ayel؟",
            "{nickname} ya zamel, command خاطئ. حتى l3ayel ديال 7 snين كيفهم أحسن منك.",
            "wakha a khay, command ماشي صحيح. آش هاد الكارثة؟",
            "a {nickname}, command خاطئ. كتبان b7al chi 7wayej f terain.",
        ],
        6
    ),
    "command_success": PhraseTemplate(
        "general",
        [
            "wakha a khay, hia linfo:",
            "a 3chiri, hia linfo ديالك:",
            "yak a sidi, hia linfo:",
            "wakha, hia linfo، شوف chi wa7ed ماشي f blaso:",
        ],
        3
    ),
}

class DarijaEngine:
    """Generates authentic Casablanca street football banter in Darija."""

    def __init__(self, personality: str = "casablanca"):
        self.personality = personality
        self.vocab = VOCAB
        self.phrases = PHRASE_DB
        random.seed()

    def _format(self, template: str, **kwargs) -> str:
        """Format a template with variables, adding random insults if appropriate."""
        # Add random insult if not present
        if "insult" not in kwargs and "{insult}" in template:
            kwargs["insult"] = random.choice(self.vocab["insults"])
        if "comment" not in kwargs and "{comment}" in template:
            comments = [
                "حتى l3ayel ديال derb sultan كيلعب أحسن",
                "آش هاد الكارثة",
                "كتبان b7al chi 7wayej",
                "rating ديالك محتاج محامي",
                "الكورة كانت كتشوفك وكتبدل الطريق",
                "درتي assist للخصم أكثر من الفريق",
                "الخصم كان مرتاح ملي شافك",
                "واش كنتي لاعب ولا جا غير السميّة ديالك",
                "حتى lgardian ديال lfar9 l5or كيضرب أحسن منك",
                "كتدي lball l3nd l5or b7al chi livreur",
            ]
            kwargs["comment"] = random.choice(comments)
        return template.format(**kwargs)

    def generate(self, category: str, **kwargs) -> str:
        """Generate a phrase from a category."""
        template_obj = self.phrases.get(category)
        if not template_obj:
            return f"wakha a khay, hia linfo: {kwargs}"

        template = random.choice(template_obj.templates)
        return self._format(template, **kwargs)

    def roast_player(self, nickname: str, stats: Dict, severity: int = 9) -> str:
        """Generate a roast for a player based on stats."""
        rating = stats.get("rating", 7.0)
        games = stats.get("games", 0)
        goals = stats.get("goals", 0)
        assists = stats.get("assists", 0)
        poss_lost = stats.get("possession_lost", 0)

        # Determine roast type based on worst stat
        if games < 3:
            return self.generate("roast_ghost", nickname=nickname, games=games)

        if poss_lost > 50:
            return self.generate("roast_high_possession_lost", nickname=nickname, value=poss_lost)

        if rating < 6.0:
            return self.generate("roast_low_rating", nickname=nickname, rating=rating)

        if goals == 0 and games > 5:
            return self.generate("roast_zero_stats", nickname=nickname, stat="goals", value=goals)

        if assists == 0 and games > 5:
            return self.generate("roast_zero_stats", nickname=nickname, stat="assists", value=assists)

        # Generic roast
        return self.generate("roast_fraud", nickname=nickname, score=stats.get("fraud_score", 50))

    def praise_player(self, nickname: str, stats: Dict) -> str:
        """Generate praise (1% serious)."""
        stat_name = random.choice(["goals", "assists", "rating", "impact"])
        value = stats.get(stat_name, 0)
        return self.generate("praise_mvp", nickname=nickname, stat=stat_name, value=value)

    def stat_of_day(self, nickname: str, stat_name: str, value, is_roast: bool = True) -> str:
        """Generate stat of the day message."""
        if is_roast:
            return self.generate("stat_of_day_roast", nickname=nickname, stat=stat_name, value=value)
        return self.generate("stat_of_day_mvp", nickname=nickname, stat=stat_name, value=value)

    def match_reaction(self, team_name: str, won: bool = False) -> str:
        """Generate match reaction."""
        if won:
            return self.generate("match_reaction_good", team=team_name)
        return self.generate("match_reaction_bad", team=team_name)

    def rankings_intro(self) -> str:
        return self.generate("rankings_intro")

    def rankings_entry(self, rank: int, nickname: str, stat: str, value) -> str:
        return self.generate("rankings_entry", rank=rank, nickname=nickname, stat=stat, value=value)

    def who_sold(self, nickname: str) -> str:
        return self.generate("who_sold", nickname=nickname)

    def club_summary(self, club_name: str) -> str:
        return self.generate("club_summary", club_name=club_name)

    def greeting(self, bot_name: str = "ProClubsTracker") -> str:
        return self.generate("greeting", bot_name=bot_name)

    def command_error(self, nickname: str = "7mar") -> str:
        return self.generate("command_error", nickname=nickname)

    def command_success(self) -> str:
        return self.generate("command_success")

    def add_casablanca_flavor(self, text: str) -> str:
        """Add Casablanca street flavor to any text."""
        prefixes = [
            "wakha a khay, ",
            "a 3chiri, ",
            "yak a sidi, ",
            "oh lala, ",
            "a 7bibi, ",
            "wakha, ",
        ]
        suffixes = [
            " سير تعلم ل3b.",
            " حتى l3ayel ديال derb sultan كيلعب أحسن.",
            " آش هاد الكارثة؟",
            " rating ديالك محتاج محامي.",
            " واش كنتي لاعب ولا جا غير السميّة ديالك؟",
        ]

        # 30% chance to add prefix/suffix
        if random.random() < 0.3:
            text = random.choice(prefixes) + text
        if random.random() < 0.3:
            text = text + random.choice(suffixes)

        return text

# Global instance
_darija = None

def get_darija_engine(personality: str = "casablanca") -> DarijaEngine:
    global _darija
    if _darija is None:
        _darija = DarijaEngine(personality)
    return _darija
