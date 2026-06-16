"""
phase2_darija_engine.py
99% Roast Mode. Authentic Casablanca street football banter.
NO formal language. NO ChatGPT tone. NO corporate speak.
"""
import random
from typing import Dict, Any, List, Optional

class Phase2DarijaEngine:
    """Dedicated Darija language layer.
    Sources: Casablanca street football, derb slang, football banter.
    """

    TEMPLATES = {
        "low_rating": [
            "واش كنتي لاعب ولا جا غير السميّة ديالك؟",
            "rating ديالك محتاج محامي باش يدافع عليه.",
            "الخصم كان مرتاح ملي شافك دخلتي.",
            "آش هاد الكارثة؟ حتى الحارس كيشجع فيك.",
            "كنتيرن ديالك كيبان بلي كتضرب غير فالتراينينغ.",
            "حتى الbot فهم بلي كتبيع الماتشات.",
            "فين كنتي فهاد الماتش؟ حتى الكاميرا ما لقاتكش.",
            "لعبتك بحال شي ghost, باقي غير السميّة.",
            "EA Sports كتسول: واش هادا لاعب ولا spectator؟",
            "الcommentary كيسكت ملي كتاخد الكورة.",
        ],
        "low_goals": [
            "الكورة كانت كتشوفك وكتبدل الطريق.",
            "حتى المرمى الخاوي كتخاف تسجّل فيه.",
            "3 ديال الماتشات وما سجّلتي والو؟ حتى المدافع كيسجّل أكثر منك.",
            "شنو كتدير فالمرمى؟ كتصوّر مع العارضة؟",
            "هدف ديالك فهاد السيزون؟ ولا غير assist للخصم؟",
            "الكاميرا كتبقى zoom على غيرك باش الجمهور ما يشوفش لعبتك.",
        ],
        "low_assists": [
            "درتي assist للخصم أكثر من الفريق.",
            "Pass ديالك كتمشي للجمهور أكثر من اللاعبين.",
            "حتى الreferee عطا assist أكثر منك.",
            "كنتيرن ديالك: 'ما نعطي حتى شي حاجة'.",
            "كتباصي بحال إلا كتدير Morse code.",
        ],
        "high_possession_lost": [
            "الكورة ملي كتجيك كتبكي.",
            "possession lost: {value}. حتى الظهير كيحتفظ بالكورة أكثر منك.",
            "كل touch ديالك هو turnover.",
            "كنتيرن ديالك هو gift shop للخصم.",
            "الكورة كتجيك وكتقول: 'خلاص, ماشي معاك'.",
        ],
        "fraud": [
            "Fraud score ديالك: {value}. حتى الاحتيال كيحتشم منك.",
            "كتبان rating عالي وما كتدير والو. حتى الstat padding كيحتشم.",
            "هادا هو التعريف ديال fraud فالقاموس.",
            "كل ماتش كتخرج بلا ماتش ريسومي.",
            "الكاميرا كتبقى تقلب عليك فال replays.",
            "حتى EA Sports نساوك فال database.",
        ],
        "ghost": [
            "Ghost mode: ON. حتى ال radar ما كيبانش فيك.",
            "شكون {name}؟ حتى EA Sports نساوك.",
            "ما شفتكش فالماتش. ولا كنتي فالجمهور؟",
            "Presence ديالك 0%. حتى الظل ديالك كيتأخر.",
            "غادي نسقو ليك taxi باش تجي تلعب.",
        ],
        "carry": [
            "{name} كيحمل الفريق بحال شي donkey كيحمل الحطب.",
            "بلا {name} هاد الفريق كيبقى division 10.",
            "Impact score ديالك {value}. باقي اللاعبين كيتفرّجو.",
            "{name} كيلعب و 10 كيتفرجو — هادا الواقع.",
            "King aura activated. {name} هو الملك.",
        ],
        "mvp": [
            "{name} هو الملك. باقي اللاعبين كيغسلو ليه الكراسي.",
            "S-Tier performance. حتى الخصم كيتمنى يكون فالفريق ديالك.",
            "Monster mode activated. {name} كيلعب بلا رحمة.",
            "Ballon d'Or material. {name} كيسجل و كيدافع و كيمرر.",
        ],
        "general_roast": [
            "لعبتك بحال شي tutorial ديال كيفاش ما تلعبش.",
            "حتى IA فالcareer mode كتضحك عليك.",
            "فريق كامل كيتسنا منك وكتجيب disappointment.",
            "Skills ديالك محتاجين update, حتى FIFA 14 كان عندها mechanics أحسن.",
            "الكاميرا كتبقى zoom على غيرك باش الجمهور ما يشوفش لعبتك.",
            "حتى الcommentary كيسكت ملي كتاخد الكورة.",
            "Defense ديالك بحال باب دار مفتوح.",
            "Shooting ديالك كيحتاج GPS باش يلقى المرمى.",
            "Pace ديالك: 0. حتى turtle كتجري أكثر.",
            "Physicality ديالك: paper bag فالريح.",
            "Passing ديالك كتمشي للجمهور أكثر من اللاعبين.",
            "Dribbling ديالك بحال شي robot خاصو oil change.",
            "Positioning ديالك: lost. حتى GPS ما يقدر يلقيك.",
            "الفريق كيحتاج 11 player، ماشي 10 + {name} يتفرج.",
        ],
        "opening": [
            "سمع يا {name}...",
            "يا {name}, وخا نكون bot ما نقدرش نسكت...",
            "تنبيه: roast mode activated.",
            "يا {name}, هادا هو التقرير ديالك (ماشي زوين):",
            "الحقيقة كتوجع, و هادا هو الحقيقة ديالك:",
            "يا {name}, جبت ليك الحقيقة بلا سكر:",
        ],
        "closing": [
            "نصيحة: بيع الكونسول.",
            "الخلاصة: راجع لعبتك.",
            "verdict: guilty of fraud.",
            "الحكم: red card فالحياة.",
            "الجمهور كيطالب باش تبدل (substitution).",
            "EA Sports كتقول: 'please uninstall'.",
        ],
    }

    @classmethod
    def generate_roast(cls, player_name: str, stats: Dict[str, Any],
                       intensity: float = 0.99) -> str:
        """Generate a full Darija roast message."""
        lines = []
        opening = random.choice(cls.TEMPLATES["opening"]).format(name=player_name)
        lines.append(opening)
        lines.append("")
        roasts = []
        if stats.get("avg_rating", 10) < 6.0:
            roasts.append(random.choice(cls.TEMPLATES["low_rating"]))
        if stats.get("goals", 0) == 0 and stats.get("matches", 0) > 2:
            roasts.append(random.choice(cls.TEMPLATES["low_goals"]))
        if stats.get("assists", 0) == 0 and stats.get("matches", 0) > 2:
            roasts.append(random.choice(cls.TEMPLATES["low_assists"]))
        if stats.get("possession_losses", 0) > 15:
            tpl = random.choice(cls.TEMPLATES["high_possession_lost"])
            roasts.append(tpl.format(value=stats["possession_losses"]))
        if stats.get("throwing_score", 0) > 3.0 or stats.get("fraud_score", 0) > 50:
            tpl = random.choice(cls.TEMPLATES["fraud"])
            roasts.append(tpl.format(value=stats.get("fraud_score", stats.get("throwing_score", 0))))
        if stats.get("matches", 0) <= 1 or stats.get("minutes", 0) < 60:
            roasts.append(random.choice(cls.TEMPLATES["ghost"]).format(name=player_name))
        while len(roasts) < 4:
            tpl = random.choice(cls.TEMPLATES["general_roast"])
            roasts.append(tpl.format(name=player_name))
        random.shuffle(roasts)
        for r in roasts[:5]:
            lines.append("🔥 " + r)
        lines.append("")
        lines.append(random.choice(cls.TEMPLATES["closing"]))
        return "
".join(lines)

    @classmethod
    def generate_mvp_praise(cls, player_name: str, stats: Dict[str, Any]) -> str:
        """Generate MVP praise in Darija."""
        lines = [
            f"👑 {player_name} - الملك ديال الليلة!",
            "",
            f"Impact Score: {stats.get('impact_score', 0)} - كتسنا منك الغدارة و جبت الغدارة!",
            f"Goals: {stats.get('goals', 0)} | Assists: {stats.get('assists', 0)} | MOTM: {stats.get('motm', 0)}",
            "",
        ]
        tpl = random.choice(cls.TEMPLATES["mvp"])
        lines.append(tpl.format(name=player_name, value=stats.get("impact_score", 0)))
        lines.append("")
        lines.append("S-Tier. Monster. King. 🏆")
        return "
".join(lines)

    @classmethod
    def generate_carry_message(cls, player_name: str, stats: Dict[str, Any]) -> str:
        lines = [
            f"🎒 {player_name} - CARRY CONFIRMED",
            "",
            f"Win Rate: {stats.get('win_rate', 0)}% | Impact: {stats.get('impact_score', 0)}",
            "",
        ]
        tpl = random.choice(cls.TEMPLATES["carry"])
        lines.append(tpl.format(name=player_name, value=stats.get("impact_score", 0)))
        lines.append("")
        lines.append("بلاك هاد الفريق كيسقط.")
        return "
".join(lines)

    @classmethod
    def generate_ghost_message(cls, player_name: str) -> str:
        tpl = random.choice(cls.TEMPLATES["ghost"])
        return f"👻 GHOST ALERT

{tpl.format(name=player_name)}

ما بانش. ما سمعناش. ما وجدناش."

    @classmethod
    def generate_fraud_message(cls, player_name: str, stats: Dict[str, Any]) -> str:
        lines = [
            f"🤡 FRAUD ALERT: {player_name}",
            "",
            f"Fraud Score: {stats.get('fraud_score', stats.get('throwing_score', 0))}/100",
            f"Rating: {stats.get('avg_rating', 0)} | Goals: {stats.get('goals', 0)} | Impact: {stats.get('impact_score', 0)}",
            "",
        ]
        tpl = random.choice(cls.TEMPLATES["fraud"])
        lines.append(tpl.format(value=stats.get("fraud_score", stats.get("throwing_score", 0))))
        lines.append("")
        lines.append("الحكم: GUILTY.")
        return "
".join(lines)

    @classmethod
    def generate_stat_of_day(cls, player_name: str, stat_name: str,
                              stat_value: Any, is_bad: bool = True) -> str:
        if is_bad:
            lines = [
                "📊 STAT OF THE DAY",
                "",
                f"Player: {player_name}",
                f"Stat: {stat_name}",
                f"Value: {stat_value}",
                "",
            ]
            tpl = random.choice(cls.TEMPLATES["general_roast"])
            lines.append(tpl.format(name=player_name))
            lines.append("")
            lines.append("#ProClubs #Fraud #StatOfTheDay")
        else:
            lines = [
                "📊 STAT OF THE DAY - MVP EDITION",
                "",
                f"Player: {player_name}",
                f"Stat: {stat_name}",
                f"Value: {stat_value}",
                "",
                "Monster performance! 👑",
                "",
                "#ProClubs #MVP #StatOfTheDay"
            ]
        return "
".join(lines)

    @classmethod
    def generate_who_sold(cls, player_name: str, stats: Dict[str, Any]) -> str:
        lines = [
            "🛒 WHO SOLD?",
            "",
            f"الفائز: {player_name}",
            f"Rating: {stats.get('avg_rating', 0)} | Goals: {stats.get('goals', 0)} | Assists: {stats.get('assists', 0)}",
            "",
            f"{player_name} باع الماتش بحال شي broker.",
            "الحكم: GUILTY OF TREASON.",
        ]
        return "
".join(lines)

    @classmethod
    def generate_club_roast(cls, team_stats: Dict[str, Any]) -> str:
        lines = [
            "🏟️ CLUB ROAST",
            "",
            f"Win Rate: {team_stats.get('win_rate', 0)}% - حتى AI كتفوز أكثر منكم.",
            f"Goals Scored: {team_stats.get('goals_for', 0)} - المرمى كيتمنى يتسجل فيه أكثر.",
            f"Goals Against: {team_stats.get('goals_against', 0)} - Defense ديالكم بحال باب مفتوح.",
            "",
            "الخلاصة: راجعوا لعبتكم كاملين.",
        ]
        return "
".join(lines)
