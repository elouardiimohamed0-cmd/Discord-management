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
            "{rating}؟ آش
