import random
from datetime import datetime
from typing import List, Optional, Dict
from models import PlayerStats, ClubStats
from darija_engine import DarijaEngine

class DailyEngine:
    def __init__(self):
        self.darija = DarijaEngine("casablanca")
    
    def pick_stat_of_the_day(self, players: List[PlayerStats]) -> Optional[Dict]:
        """80% chance bad stat, 20% chance good stat (monster)."""
        is_bad = random.random() < 0.8
        
        if is_bad:
            # Bad stats pool
            candidates = [
                self._most_possession_lost(players),
                self._lowest_rating(players),
                self._worst_pass_accuracy(players),
                self._most_ghost(players),
                self._highest_throwing(players),
            ]
            result = random.choice([c for c in candidates if c])
            if result:
                result["type"] = "bad"
                result["title"] = "📉 Stat of the Day"
            return result
        else:
            # Monster / good stat
            candidates = [
                self._best_rating(players),
                self._most_goals(players),
                self._most_assists(players),
                self._highest_impact(players),
                self._best_win_rate(players),
            ]
            result = random.choice([c for c in candidates if c])
            if result:
                result["type"] = "good"
                result["title"] = "🔥 Monster of the Day"
            return result
    
    def _most_possession_lost(self, players: List[PlayerStats]) -> Optional[Dict]:
        if not players:
            return None
        p = max(players, key=lambda x: x.possession_losses)
        if p.possession_losses <= 0:
            return None
        roast = f"اليوم الجائزة كتسلم لـ {p.name}. {p.possession_losses} possession losses. الكرة كانت خارجة من عندو أسرع من الانترنت فالعالم القروي."
        return {"player": p, "stat_name": "Possession Lost", "stat_value": p.possession_losses, "roast": roast}
    
    def _lowest_rating(self, players: List[PlayerStats]) -> Optional[Dict]:
        eligible = [p for p in players if p.games > 0]
        if not eligible:
            return None
        p = min(eligible, key=lambda x: x.rating_pg)
        if p.rating_pg > 8:
            return None
        roast = f"Rating {round(p.rating_pg, 1)}؟ {p.name} اليوم كنتي NPC رسمي. واش كنتي لاعب ولا كنتي كتشوف المباراة من التلفون؟"
        return {"player": p, "stat_name": "Lowest Rating", "stat_value": round(p.rating_pg, 1), "roast": roast}
    
    def _worst_pass_accuracy(self, players: List[PlayerStats]) -> Optional[Dict]:
        eligible = [p for p in players if p.games > 0 and p.pass_accuracy > 0]
        if not eligible:
            return None
        p = min(eligible, key=lambda x: x.pass_accuracy)
        if p.pass_accuracy > 80:
            return None
        roast = f"Pass accuracy {round(p.pass_accuracy, 1)}%؟ {p.name} كتباصي الكرة بحال إلا كتدير raffle. 3ndak {round(100-p.pass_accuracy, 1)}% ديال التخربيق فكل باصة."
        return {"player": p, "stat_name": "Pass Accuracy", "stat_value": round(p.pass_accuracy, 1), "roast": roast}
    
    def _most_ghost(self, players: List[PlayerStats]) -> Optional[Dict]:
        eligible = [p for p in players if p.games > 0]
        if not eligible:
            return None
        p = min(eligible, key=lambda x: x.minutes_played / max(x.games, 1))
        mins_per_game = p.minutes_played // max(p.games, 1)
        if mins_per_game > 70:
            return None
        roast = f"{p.name} لعبتي {p.games} games و {p.minutes_played} minutes. واش كتجي تشوف المباراة ولا تلعب؟"
        return {"player": p, "stat_name": "Ghost Minutes", "stat_value": mins_per_game, "roast": roast}
    
    def _highest_throwing(self, players: List[PlayerStats]) -> Optional[Dict]:
        eligible = [p for p in players if p.games > 0]
        if not eligible:
            return None
        p = max(eligible, key=lambda x: x.throwing_score)
        if p.throwing_score < 2:
            return None
        roast = f"Throwing score {round(p.throwing_score, 1)}. {p.name} هادا رسمي fraud. كتضرب فريقك أكثر من الخصم."
        return {"player": p, "stat_name": "Throwing Score", "stat_value": round(p.throwing_score, 1), "roast": roast}
    
    def _best_rating(self, players: List[PlayerStats]) -> Optional[Dict]:
        eligible = [p for p in players if p.games > 0]
        if not eligible:
            return None
        p = max(eligible, key=lambda x: x.rating_pg)
        roast = f"Rating {round(p.rating_pg, 1)}! {p.name} هاد السيد شاد الفريق فوق كتافو. هادا Ballon d'Or material."
        return {"player": p, "stat_name": "Best Rating", "stat_value": round(p.rating_pg, 1), "roast": roast}
    
    def _most_goals(self, players: List[PlayerStats]) -> Optional[Dict]:
        eligible = [p for p in players if p.goals > 0]
        if not eligible:
            return None
        p = max(eligible, key=lambda x: x.goals)
        roast = f"{p.goals} goals! {p.name} كتسجل بحال Haaland. المدافعين ديال الخصم كيتسناو منك أكثر من ما كتسنا من الضربة الجزائية."
        return {"player": p, "stat_name": "Goals", "stat_value": p.goals, "roast": roast}
    
    def _most_assists(self, players: List[PlayerStats]) -> Optional[Dict]:
        eligible = [p for p in players if p.assists > 0]
        if not eligible:
            return None
        p = max(eligible, key=lambda x: x.assists)
        roast = f"{p.assists} assists! {p.name} كتباصي بحال De Bruyne. كل باصة ديالك كتولد goal."
        return {"player": p, "stat_name": "Assists", "stat_value": p.assists, "roast": roast}
    
    def _highest_impact(self, players: List[PlayerStats]) -> Optional[Dict]:
        if not players:
            return None
        p = max(players, key=lambda x: x.impact_score)
        roast = f"Impact {round(p.impact_score, 1)}! {p.name} كتجبد الفريق فظهرك. هادا لي كيسميو carry."
        return {"player": p, "stat_name": "Impact Score", "stat_value": round(p.impact_score, 1), "roast": roast}
    
    def _best_win_rate(self, players: List[PlayerStats]) -> Optional[Dict]:
        eligible = [p for p in players if p.games > 3]
        if not eligible:
            return None
        p = max(eligible, key=lambda x: x.win_rate)
        roast = f"Win rate {round(p.win_rate, 1)}%! {p.name} كيجيب الwins. فريقك كيفوز بسببك."
        return {"player": p, "stat_name": "Win Rate", "stat_value": round(p.win_rate, 1), "roast": roast}
