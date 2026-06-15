import random
from typing import List, Dict, Optional
from models import PlayerStats

class StoryEngine:
    """Builds narratives, rivalries, and legends from player history."""
    
    def __init__(self):
        self.narratives = {
            "possession_king": [
                "هاد {weeks} أسبوع و{player} فالصدارة ديال ضياع الكرة.",
                "{player} عندو {count} أسبوع متتالي فالtop 3 ديال possession losses.",
                "واش {player} كتباصي للخصم ولا شنو؟ هاد {count} مرة ضيعتيها هاد الشهر.",
            ],
            "rating_drop": [
                "مازال ما فاقوش من داك rating {rating} ديال {player}.",
                "{player} دار rating {rating} — هادا ماشي note، هادي warning رسمي.",
                "من بعد داك الماتش، {player} بقا كيتسناو فالbench.",
            ],
            "mvp_streak": [
                "{player} عندو {count} MVPs هاد الشهر. هادا لي كيسميو dominance.",
                "{count} MVPs فالشهر؟ {player} كيلعب و 10 كيتفرجو.",
                "الفريق بلا {player} بحال WiFi بلا router.",
            ],
            "fraud_streak": [
                "{player} فالtop 3 ديال frauds {count} مرات هاد الشهر. هادا رسمي problem.",
                "واش {player} كتجي تلعب ولا تجي تدير social experiment؟ {count} مرات فالfraud list.",
            ],
            "rivalry": [
                "{p1} و {p2} بحال Messi و Ronaldo — ولكن فالعكس.",
                "كل مرة {p1} كيلعب مزيان، {p2} كيختفي. rivalry واضحة.",
                "{p1} كيدر {p2} فالتسجيل بـ {diff} هدف. هادا 1v1 ماشي متساوي.",
            ],
            "legend": [
                "{player} بقا legend فالسيرفر. {count} performances مزيانة متتالية.",
                "الhistory غادي تتذكر {player} بحال {count} MVPs و {goals} goals.",
                "{player} — من فاش كانت اللعبة لعبة، حتى بقات industry.",
            ],
        }
    
    def build_possession_narrative(self, player: PlayerStats, weeks_top: int = 1) -> str:
        tmpl = random.choice(self.narratives["possession_king"])
        return tmpl.format(player=player.name, weeks=weeks_top, count=weeks_top)
    
    def build_rating_narrative(self, player: PlayerStats, worst_rating: float) -> str:
        tmpl = random.choice(self.narratives["rating_drop"])
        return tmpl.format(player=player.name, rating=round(worst_rating, 1))
    
    def build_mvp_narrative(self, player: PlayerStats, mvp_count: int) -> str:
        tmpl = random.choice(self.narratives["mvp_streak"])
        return tmpl.format(player=player.name, count=mvp_count)
    
    def build_fraud_narrative(self, player: PlayerStats, fraud_count: int) -> str:
        tmpl = random.choice(self.narratives["fraud_streak"])
        return tmpl.format(player=player.name, count=fraud_count)
    
    def build_rivalry(self, p1: PlayerStats, p2: PlayerStats) -> str:
        diff = abs(p1.goals - p2.goals)
        tmpl = random.choice(self.narratives["rivalry"])
        return tmpl.format(p1=p1.name, p2=p2.name, diff=diff)
    
    def build_legend(self, player: PlayerStats, good_games: int) -> str:
        tmpl = random.choice(self.narratives["legend"])
        return tmpl.format(player=player.name, count=good_games, goals=player.goals)
    
    def generate_story(self, players: List[PlayerStats]) -> str:
        """Generate a random story from current data."""
        stories = []
        
        # Find possession king
        if players:
            poss_king = max(players, key=lambda p: p.possession_losses)
            if poss_king.possession_losses > 10:
                stories.append(self.build_possession_narrative(poss_king))
        
        # Find MVP
        if players:
            mvp = max(players, key=lambda p: p.impact_score)
            if mvp.impact_score > 50:
                stories.append(self.build_mvp_narrative(mvp, random.randint(2, 5)))
        
        # Find fraud
        if players:
            fraud = max(players, key=lambda p: p.throwing_score)
            if fraud.throwing_score > 3:
                stories.append(self.build_fraud_narrative(fraud, random.randint(2, 4)))
        
        if not stories:
            return "ما بانش لي شي story هاد اليوم. كلشي average."
        
        return "\n\n".join(stories[:2])
