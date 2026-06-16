import random
from typing import List, Dict, Optional
from models import PlayerStats, ClubStats

class DarijaEngine:
    PERSONALITIES = {
        "casablanca": {
            "prefixes": ["آش هادا", "واخا", "صافي", "هادشي", "ياك", "أودي"],
            "suffixes": ["آ صاحبي", "يا لعيب", "يا fraud", "يا ghost", "يا باطل"],
            "style": "street_casablanca"
        },
        "analyst": {
            "prefixes": ["من ناحية تحليلية", "إحصائياً", "بناءً على البيانات"],
            "suffixes": ["هادا التحليل العلمي", "الأرقام ما كتكذبش"],
            "style": "analytical"
        },
        "toxic": {
            "prefixes": ["أودي", "ياك", "واش كنتي", "بغيت نفهم"],
            "suffixes": ["يا باطل", "يا خايب", "يا مسكين", "يا فاشل"],
            "style": "toxic_teammate"
        },
        "coach": {
            "prefixes": ["غادي نقوللك شي حاجة", "سمع مني", "هادشي باش تتعلم"],
            "suffixes": ["غادي تحتاج تتمرن", "هادا مشكل ديال mindset", "غادي نبدلوك position"],
            "style": "coach"
        },
        "commentator": {
            "prefixes": ["يا سلام", "يا لطيف", "يا ربي", "شوف شوف"],
            "suffixes": ["هادا مستوى", "هادا فن", "هادا كارثة"],
            "style": "commentator"
        },
        "cafeteria": {
            "prefixes": ["سمعتيه", "الناس كتهضر", "فالكافيتيريا", "الراجل"],
            "suffixes": ["هادا لي كاين", "هادا شنو واقع", "هادا رأي العامة"],
            "style": "gossip"
        }
    }
    
    ROAST_TEMPLATES = {
        "rating_low": [
            "Rating {rating}؟ هادي ماشي note، هادي warning آ {name}.",
            "{rating}؟ اليوم كنتي NPC رسمي يا {name}.",
            "واش كنتي لاعب ولا كنتي كتشوف المباراة من التلفون يا {name}؟ Rating {rating} هادي عيب.",
            "Rating {rating} — المدافع ديال الخصم لعب ضدك وتهنى يا {name}.",
            "{rating}؟ الله يعطيك الصحة، درتي cardio مزيان ولكن الكرة بقات كتسناك يا {name}.",
        ],
        "rating_high": [
            "Rating {rating} — هادا Ballon d'Or ولا غير lucky game يا {name}؟",
            "{rating}؟ آش بغيتي نصقفو ليك ولا شنو؟ هادي مرة واحة ما غاديش تعاود يا {name}.",
            "Rating {rating} — الكاميرا كتصورك اليوم يا {name}.",
        ],
        "goals_zero": [
            "جبت {goals} أهداف — الحارس دار save أكثر منك يا {name}.",
            "{goals} goals فـ {games} games؟ واش كنتي لاعب ولا referee يا {name}؟",
            "المشكل ماشي فالفريق، المشكل فداك لي لابس رقمك يا {name}. {goals} goals هادي كارثة.",
            "الكرة كانت عندك أكثر من اللازم وهادشي كارثة يا {name}. {goals} goals؟",
        ],
        "goals_good": [
            "جبت {goals} أهداف — مزيان، ولكن داك 11% الباقي خاصو تحقيق يا {name}.",
            "{goals} goals — كتسجل بحال Haaland ولكن فالدفاع كتبان بحال Maguire يا {name}.",
        ],
        "assists_zero": [
            "0 assists — واش كتباصي للخصم ولا شنو يا {name}؟",
            "0 assists فـ {games} games — هادا ماشي teamwork، هادا solo queue يا {name}.",
            "كتحتاج تفهم: الكرة ماشي ديالك وحدك يا {name}. 0 assists هادي عيب.",
        ],
        "possession_losses": [
            "ضيعتي {possession_losses} كرة — يعني سجلتي وكملتي المهمة ديالك فتخريب الفريق يا {name}.",
            "{possession_losses} possession losses؟ كتجري فالتيران بحال إلا عندك 300 ping يا {name}.",
            "ضيعتي {possession_losses} كرة — هادا ماشي Pro Clubs، هادا charity يا {name}.",
            "كل مرة كتضيع الكرة، الحارس ديالنا كيتصل ب insurance يا {name}. {possession_losses} مرات.",
        ],
        "fraud": [
            "Throwing score {throwing_score} — هادا رسمي fraud يا {name}.",
            "Error score {error_score} — كتضرب فريقك أكثر من الخصم يا {name}.",
            "Impact score {impact_score} — واش كتجبد الteam لتحت ولا شنو يا {name}؟",
            "Clutch score {clutch_score} — فالضغط كتختفي بحال Casper يا {name}.",
        ],
        "ghost": [
            "لعبتي {games} games و {minutes} minutes — واش كتجي تشوف المباراة ولا تلعب يا {name}؟",
            "{minutes} minutes فـ {games} games — هادا substitute ديال substitute يا {name}.",
            "غادي نسقو ليك taxi باش تجي تلعب، ماشي غير تشوف يا {name}.",
        ],
        "ball_hog": [
            "Possession losses {possession_losses} و assists {assists} — كتباغي تلعب وحدك وكتخسر وحدك يا {name}.",
            "Pass the ball يا {name}! {possession_losses} مرة ضيعتيها و {assists} باصة صحيحة.",
            "كتباصي بحال إلا كتدير Morse code يا {name}. {assists} assists هادي ماشي كافية.",
        ],
        "carry": [
            "Impact score {impact_score} — كتجبد الفريق فظهرك يا {name}.",
            "Clutch score {clutch_score} — كتبان فالضغط بحال Messi يا {name}.",
            "هادا لي كيسميو carry — {name} بلا ما يتكلم.",
            "{name} كيلعب و 10 كيتفرجو — هادا الواقع.",
        ],
        "win_rate": [
            "Win rate {win_rate}% — فريقك كيخسر بسببك يا {name}.",
            "{win_rate}% wins — هادا ماشي win rate، هادا survival rate يا {name}.",
            "فالgames لي كتفوز فيهم، كون غير ما كتلعبش يا {name}.",
        ],
        "pass_accuracy": [
            "Pass accuracy {pass_accuracy}% — كتباصي الكرة بحال إلا كتدير raffle يا {name}.",
            "{pass_accuracy}% — 3ndak {fail_pct}% ديال التخربيق فكل باصة يا {name}.",
            "{pass_accuracy}% pass accuracy — يعني فالأغلبية كنتي صاحي، ولكن داك {fail_pct}% الباقي خاصو تحقيق يا {name}.",
        ],
        "defender_bad": [
            "{tackles} tackles و {interceptions} interceptions — المدافع ديال الخصم كيتضحك عليك يا {name}.",
            "Clean sheets {clean_sheets} — الحارس كيتسنا منك أكثر من ما كتسنا منو يا {name}.",
            "Goals conceded {goals_conceded} — واش كتدافع ولا كتفتح باب ليهم يا {name}؟",
        ],
        "general": [
            "هاد رابع أسبوع وانت كتضيع performance يا {name}.",
            "آخر clean sheet عندك قديم أكثر من بعض أعضاء السيرفر يا {name}.",
            "{name} — كتبان بحال لاعب فريق مقهى، ماشي Pro Clubs.",
            "واش كتجي تلعب ولا تجي تدير social experiment يا {name}؟",
            "الفريق كيحتاج 11 player، ماشي 10 + {name} يتفرج.",
            "يا {name}، EA Sports كتسول عليك: واش باقي كتلعب ولا retired؟",
        ]
    }
    
    def __init__(self, personality: str = "casablanca"):
        self.personality = personality if personality in self.PERSONALITIES else "casablanca"
        self.style = self.PERSONALITIES[self.personality]
    
    def set_personality(self, p: str):
        if p in self.PERSONALITIES:
            self.personality = p
            self.style = self.PERSONALITIES[p]
    
    def _format(self, template: str, player: PlayerStats, extra: Dict = None) -> str:
        data = {
            "name": player.name,
            "rating": round(player.rating_pg, 1),
            "goals": player.goals,
            "games": player.games,
            "assists": player.assists,
            "possession_losses": player.possession_losses,
            "throwing_score": player.throwing_score,
            "error_score": player.error_score,
            "impact_score": player.impact_score,
            "clutch_score": player.clutch_score,
            "win_rate": player.win_rate,
            "pass_accuracy": round(player.pass_accuracy, 1),
            "fail_pct": round(100 - player.pass_accuracy, 1),
            "tackles": player.tackles,
            "interceptions": player.interceptions,
            "clean_sheets": player.clean_sheets,
            "goals_conceded": player.goals_conceded,
            "minutes": player.minutes_played,
        }
        if extra:
            data.update(extra)
        return template.format(**data)
    
    def _add_personality(self, text: str) -> str:
        prefix = random.choice(self.style["prefixes"]) if random.random() < 0.3 else ""
        suffix = random.choice(self.style["suffixes"]) if random.random() < 0.4 else ""
        
        # Human-like imperfections — only affect Latin text occasionally
        if random.random() < 0.08:
            text = text.lower()
        if random.random() < 0.08:
            text = text.replace("،", ",")
        if random.random() < 0.15:
            text = text.replace(".", "")
        
        parts = [p for p in [prefix, text, suffix] if p]
        return " ".join(parts)
    
    def roast(self, player: PlayerStats, position: str = "CM") -> str:
        roasts = []
        
        if player.rating_pg < 5.5:
            roasts.extend(self.ROAST_TEMPLATES["rating_low"])
        elif player.rating_pg > 8.0:
            roasts.extend(self.ROAST_TEMPLATES["rating_high"])
        
        if player.goals == 0 and player.games > 3:
            roasts.extend(self.ROAST_TEMPLATES["goals_zero"])
        elif player.goals_pg > 1.0:
            roasts.extend(self.ROAST_TEMPLATES["goals_good"])
        
        if player.assists == 0 and player.games > 3:
            roasts.extend(self.ROAST_TEMPLATES["assists_zero"])
        
        if player.possession_losses > 10:
            roasts.extend(self.ROAST_TEMPLATES["possession_losses"])
        
        if player.throwing_score > 3.0:
            roasts.extend(self.ROAST_TEMPLATES["fraud"])
        
        if player.games > 0 and player.minutes_played / max(player.games, 1) < 60:
            roasts.extend(self.ROAST_TEMPLATES["ghost"])
        
        if player.possession_losses > player.assists * 5 and player.assists < 3:
            roasts.extend(self.ROAST_TEMPLATES["ball_hog"])
        
        if player.win_rate < 40 and player.games > 5:
            roasts.extend(self.ROAST_TEMPLATES["win_rate"])
        
        if player.pass_accuracy < 70 and player.games > 3:
            roasts.extend(self.ROAST_TEMPLATES["pass_accuracy"])
        elif player.pass_accuracy > 90:
            roasts.extend(self.ROAST_TEMPLATES["pass_accuracy"])
        
        if position in ["CB", "LB", "RB", "GK"] and player.tackles + player.interceptions < 5 and player.games > 3:
            roasts.extend(self.ROAST_TEMPLATES["defender_bad"])
        
        roasts.extend(self.ROAST_TEMPLATES["general"])
        
        if not roasts:
            roasts = ["{name} — ما عنديش شي حاجة نقولها، وهادا فشل فحدو."]
        
        chosen = random.choice(roasts)
        text = self._format(chosen, player)
        return self._add_personality(text)
    
    def praise(self, player: PlayerStats, position: str = "CM") -> str:
        praises = [
            "Impact score {impact_score} — {name} كيلعب مزيان اليوم، صافي.",
            "Rating {rating} — {name} كتبان لي كتعرف شنو كتدير.",
            "{name} — هادا لي كيسميو performance.",
            "Win rate {win_rate}% — {name} كيجيب الwins، ماشي غير الexcuses.",
        ]
        chosen = random.choice(praises)
        return self._format(chosen, player)
    
    def generate(self, player: PlayerStats, position: str = "CM", roast_freq: float = 0.95) -> str:
        if random.random() < roast_freq:
            return self.roast(player, position)
        return self.praise(player, position)
    
    def compare(self, p1: PlayerStats, p2: PlayerStats, pos1: str = "CM", pos2: str = "CM") -> str:
        winner = p1 if p1.impact_score > p2.impact_score else p2
        loser = p2 if winner == p1 else p1
        
        templates = [
            "{winner} كيدر {loser} فجيبو — Impact {w_score} vs {l_score}.",
            "هادا 1v1: {winner} كيفوز بلا مناقشة. {loser} كيبقى يتفرج.",
            "{winner} كيلعب football، {loser} كيلعب something else.",
            "Statistics ما كتكذبش: {winner} ({w_score}) >>> {loser} ({l_score}).",
        ]
        chosen = random.choice(templates)
        return chosen.format(
            winner=winner.name,
            loser=loser.name,
            w_score=winner.impact_score,
            l_score=loser.impact_score
        )
    
    def match_summary(self, club: ClubStats, motm: PlayerStats) -> str:
        templates = [
            "الفوز {wins}، الخسارة {losses}، التعادل {draws}. MOTM: {motm} بـ Impact {impact}.",
            "Season summary: {wins} wins، {losses} defeats. {motm} كيجبد الفريق.",
            "Division {division}، Skill {skill}. {motm} كيلعب و 10 كيتفرجو.",
        ]
        chosen = random.choice(templates)
        return chosen.format(
            wins=club.wins,
            losses=club.losses,
            draws=club.draws,
            motm=motm.name,
            impact=round(motm.impact_score, 1),
            division=club.division,
            skill=club.skill_rating
        )
    
    def banter(self) -> str:
        banters = [
            "سمعتيه؟ الفريق ديالنا كيفوز بلا ما يلعبو — هادا التأثير ديال الpresence.",
            "الكافيتيريا كتهضر: الcoach غادي يبدل formation.",
            "واش كتعرف شنو فرق بيننا و Barça؟ هوما كيفوزو.",
            "هدفنا الموسم الجاي: نلعبو 11 player فنفس الوقت.",
            "الفريق ديالنا بحال WiFi ديال الدار — كيتقطع من فترة لفترة.",
        ]
        return random.choice(banters)
    
    def drama(self, players: List[str]) -> str:
        if len(players) < 2:
            players = ["Player1", "Player2"]
        p1, p2 = players[0], players[1]
        dramas = [
            f"سمعتيه؟ {p1} غادي يمشي لفريق آخر بسبب {p2}.",
            f"الكافيتيريا كتهضر: {p1} و {p2} كيتخاصمو فالvoice chat.",
            f"بلا ما نهضر بزاف، {p1} ضرب {p2} فالlast match و ما بانش ليه.",
            f"واش كتعرف شنو واقع بين {p1} و {p2}؟ هادشي كبير.",
        ]
        return random.choice(dramas)
    
    def meme(self, player: str) -> str:
        memes = [
            f"{player}: 'أنا كندافع' — also {player}: 0 tackles.",
            f"صورة {player} وهو كيتفرج فالdefense.",
            f"{player} كيدخل التيران بحال إلا كيدخل l'hammam.",
            f"واش {player} كيلعب ب controller ولا ب remote ديال التلفاز؟",
        ]
        return random.choice(memes)
    
    def transfer(self, player: str) -> str:
        rumors = [
            f"BREAKING: {player} غادي ينتقل لـ PSG ب 200M. صافي، هادشي رسمي.",
            f"Sky Sports: {player} فالمفاوضات مع Barcelona. واخا، غادي يبرد البانكة.",
            f"Fabrizio Romano: {player} to Real Madrid — here we go! ولكن فالأحلام ديالو.",
            f"{player} غادي يمشي لـ Al-Nassr ب 300M. Ronaldo كيتسناو.",
        ]
        return random.choice(rumors)
    
    def predict(self, players: List[str]) -> str:
        if len(players) < 2:
            players = ["Player1", "Player2"]
        p1, p2 = players[0], players[1]
        predictions = [
            f"ال prediction ديالي: غادي نخسرو 3-1 و {p1} غادي يضيع penalty.",
            f"غادي نفوزو 2-0، {p1} غادي يسجل و {p2} غادي يضيع open goal.",
            f"التعادل 1-1، و {p1} غادي يطرد فالدقيقة 70.",
            f"غادي نخسرو 4-0. {p1} غادي يدير own goal و {p2} غادي يتصاب فالwarmup.",
        ]
        return random.choice(predictions)
