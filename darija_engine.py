import random
from typing import List, Optional
from models import PlayerStats

class DarijaEngine:
    def __init__(self, squad_data: dict):
        self.squad = squad_data
        self.nicknames = {p.get("name", "").lower(): p.get("nickname", "") for p in squad_data.get("players", [])}
        self.bios = {p.get("name", "").lower(): p.get("bio", "") for p in squad_data.get("players", [])}

    def get_nickname(self, name: str) -> str:
        return self.nicknames.get(name.lower(), name)

    def get_bio(self, name: str) -> str:
        return self.bios.get(name.lower(), "")

    def roast(self, player: PlayerStats, roast_type: str = "general") -> str:
        name = player.name
        nick = self.get_nickname(name)
        bio = self.get_bio(name)
        pos = getattr(player, "position", "CM")

        fraud_phrases = [
            f"🔥 {name} ({nick}) — كيفاش كتقدر تلعب {pos} وما كتعرفش تلعب؟",
            f"🔥 {name} — الأداء ديالك اليوم كيهضر بزاف. كيهضر بزاف على خيبتك.",
            f"🔥 {name} — كنتي فالماتش ولا كنتي فالكافيه؟",
            f"🔥 {name} — الـrating ديالك أقل من temperature ديال الثلاجة.",
            f"🔥 {name} — {bio} ولكن اليوم كتبان بحال لاعب ديال iron 4.",
            f"🔥 {name} — كتسجل {player.goals} goals فـ{player.games} games. هادا مشي average، هادا disaster.",
            f"🔥 {name} — الكورة كتفوت عليك أكثر من الـnotifications ديال الـInstagram.",
            f"🔥 {name} — كتضيع الكورة بزاف. حتى الكورة بدا ليها sympathy.",
            f"🔥 {name} — الأداء ديالك اليوم كيهضر. كيهضر بزاف على خيبتك.",
            f"🔥 {name} — كتبان بحال لاعب كيتعلم football من YouTube tutorials.",
        ]

        ghost_phrases = [
            f"👻 {name} — كنتي فالماتش ولا كنتي ghost؟",
            f"👻 {name} — 90 دقيقة وما شفناكش. حتى الـcamera ما لقتكش.",
            f"👻 {name} — كتبان بحال player invisible. حتى الـradar ما كتبانش.",
            f"👻 {name} — الأداء ديالك اليوم: 0 tackles, 0 interceptions, 0 presence.",
            f"👻 {name} — كتجري بلا ball. حتى الـwind كتجري أسرع منك.",
        ]

        carry_phrases = [
            f"💪 {name} — كتجر الفريق بوحدك. باقي اللاعبين كيتفرجو.",
            f"💪 {name} — الأداء ديالك اليوم: goals {player.goals}, assists {player.assists}. الفريق بلاك بحال WiFi bla router.",
            f"💪 {name} — كتسجل أكثر من الـstriker. وكتدافع أكثر من الـdefender. شنو باغي تكون؟",
            f"💪 {name} — الـrating ديالك {player.rating_pg}. هادا مشي rating، هادا cheat code.",
        ]

        if roast_type == "fraud":
            return random.choice(fraud_phrases)
        elif roast_type == "ghost":
            return random.choice(ghost_phrases)
        elif roast_type == "carry":
            return random.choice(carry_phrases)
        else:
            return random.choice(fraud_phrases + ghost_phrases)

    def praise(self, player: PlayerStats) -> str:
        name = player.name
        nick = self.get_nickname(name)
        phrases = [
            f"🔥 {name} ({nick}) — الأداء ديالك اليوم كان أسطوري!",
            f"🔥 {name} — كتسجل {player.goals} goals و {player.assists} assists. هادا مشي لاعب، هادا machine!",
            f"🔥 {name} — الـrating ديالك {player.rating_pg}. حتى الـMessi كيتفرج عليك.",
            f"🔥 {name} — الفريق بلاك بحال phone bla battery.",
            f"🔥 {name} — كتدافع، كتهاجم، كتباصي. شنو باغي تكون؟ Superhero؟",
        ]
        return random.choice(phrases)

    def match_summary(self, match_result: dict) -> str:
        score = match_result.get("score", "?-?")
        opponent = match_result.get("opponent", "Unknown")
        result = match_result.get("result", "D")

        if result == "W":
            return f"✅ فوز {score} vs {opponent}! الفريق كامل شاد.",
        elif result == "L":
            return f"❌ خسارة {score} vs {opponent}. الفريق خاصو يتجمع.",
        else:
            return f"🤝 تعادل {score} vs {opponent}. نتيجة عادلة.",

    def leaderboard_intro(self, club_name: str) -> str:
        phrases = [
            f"📊 Leaderboard ديال {club_name} — الأرقام ما كتكدبش!",
            f"📊 {club_name} — شكون كيسيطر، شكون كيتسيطر عليه.",
            f"📊 ها هوا الحقيقة ديال {club_name} — بلا feelings، بلا emotions.",
        ]
        return random.choice(phrases)

    def player_card_caption(self, player: PlayerStats) -> str:
        name = player.name
        nick = self.get_nickname(name)
        bio = self.get_bio(name)

        if player.rating_pg >= 8.0:
            return f"🔥 {name} ({nick}) — {bio}\nRating: {player.rating_pg} | Goals: {player.goals} | Assists: {player.assists}\nهادا لاعب كيبان مرة فالعمر."
        elif player.rating_pg >= 6.5:
            return f"✅ {name} ({nick}) — {bio}\nRating: {player.rating_pg} | Goals: {player.goals} | Assists: {player.assists}\nأداء مقبول، ولكن يمكن أحسن."
        else:
            return f"💀 {name} ({nick}) — {bio}\nRating: {player.rating_pg} | Goals: {player.goals} | Assists: {player.assists}\nالأداء ديالك اليوم كيهضر. كيهضر بزاف على خيبتك."

    def court_case(self, player: PlayerStats, charges: List[str]) -> str:
        name = player.name
        text = f"⚖️ **المحكمة الرياضية — قضية {name}**\n\n"
        text += f"التهم:\n"
        for i, charge in enumerate(charges, 1):
            text += f"{i}. {charge}\n"
        text += f"\nالحكم: {name} مذنب فكل التهم. الحكم: lifetime ban من الـstarting XI."
        return text

    def fraud_verdict(self, player: PlayerStats) -> str:
        name = player.name
        phrases = [
            f"🎭 {name} — التحقيق خلص. الأدلة واضحة. Fraud confirmed.",
            f"🎭 {name} — كتبان بحال لاعب، ولكن فالحقيقة كتبان بحال spectator.",
            f"🎭 {name} — الأداء ديالك اليوم كيهضر. كيهضر بزاف على خيبتك.",
        ]
        return random.choice(phrases)

    def daily_digest(self, stats: dict) -> str:
        text = "📅 **Daily Digest**\n\n"
        text += f"Games: {stats.get('games', 0)} | Wins: {stats.get('wins', 0)} | Losses: {stats.get('losses', 0)}\n"
        text += f"Top Scorer: {stats.get('top_scorer', 'N/A')}\n"
        text += f"Top Fraud: {stats.get('top_fraud', 'N/A')}\n"
        text += f"MOTM: {stats.get('motm', 'N/A')}\n"
        return text

    # ────────────────────────────────────────────
    # PHASE 4 METHODS
    # ────────────────────────────────────────────

    def hall_of_fame(self, records: list) -> str:
        if not records:
            return "🏆 **Hall of Fame**\n\nما كاين حتى شي record لحد الآن."
        text = "🏆 **HALL OF FAME** — التاريخ ما كينساش\n\n"
        praises = [
            "هادا الأداء ديال الأساطير.",
            "التاريخ غادي يتذكر هاد اللحظة.",
            "هادا مشي لاعب، هادا phenomenon.",
            "الأرقام كتهضر بوحدها.",
            "هادا level ديال Ballon d'Or.",
            "الفريق بلا هاد اللاعب بحال WiFi bla router.",
        ]
        for rec in records[:3]:
            text += f"👑 {rec.player_name} — {rec.description}\n"
            text += f"   {random.choice(praises)}\n\n"
        return text

    def fame_praise(self, player: PlayerStats) -> str:
        phrases = [
            f"🔥 {player.name} — هادا لاعب كيبان مرة فالعمر.",
            f"🔥 {player.name} — الأداء ديالو اليوم غادي يتدرس فالمدارس.",
            f"🔥 {player.name} — من فاش كانت اللعبة لعبة، حتى بقات industry.",
            f"🔥 {player.name} — هادا مشي performance، هادا masterpiece.",
            f"🔥 {player.name} — الملعب كامل وقف ليه التحية.",
        ]
        return random.choice(phrases)

    def hall_of_shame_enhanced(self, records: list) -> str:
        if not records:
            return "🏛️ **Hall of Shame**\n\nما كاين حتى شي record لحد الآن."
        text = "🏛️ **HALL OF SHAME** — الأرقام ما كتكدبش\n\n"
        roasts = [
            "هادا الأداء خاصو يتعرض فالمحكمة.",
            "التاريخ غادي يتذكرك، ولكن فالعكس.",
            "هادا مشي لاعب، هادا case study.",
            "الأرقام كتهضر بوحدها — وكتقول خايب.",
            "هادا level ديال iron 4.",
            "الفريق بلا هاد اللاعب كيكون أحسن.",
            "VAR رفع يديه من داك الأداء.",
        ]
        for rec in records[:3]:
            text += f"💀 {rec.player_name} — {rec.description}\n"
            text += f"   {random.choice(roasts)}\n\n"
        return text

    def rivalry_roast(self, winner: PlayerStats, loser: PlayerStats, stats: dict) -> str:
        diff = stats.get("p1_categories_won", 0) if stats.get("overall_winner") == winner.name else stats.get("p2_categories_won", 0)
        roasts = [
            f"💀 {loser.name} — {winner.name} كيدرك فكل شي. حتى فالخسارة كتخسر.",
            f"💀 {loser.name} — rivalry ماشي rivalry هادي bullying رسمي.",
            f"💀 {loser.name} — {winner.name} كيلعب ونت كتجي تشوف. هادا الفرق.",
            f"💀 {loser.name} — الأرقام كلها ضدك. حتى المحامي ديالك غادي يستقيل.",
            f"💀 {loser.name} — من بعد هاد المقارنة، خاصك تبدل hobby.",
            f"💀 {loser.name} — {winner.name} كيسجل أكثر، كيباصي أحسن، وكيفوز أكثر. ونت؟ كتاخد oxygen.",
        ]
        text = random.choice(roasts)
        text += f"\n\n📊 الفرق: {diff} categories. هادا ماشي close، هادا massacre."
        return text

    def rivalry_tie(self, p1: PlayerStats, p2: PlayerStats) -> str:
        phrases = [
            f"🤝 {p1.name} و {p2.name} — بحال بحال. rivalry ماشي واضحة، ماشي حتى friendship.",
            f"🤝 {p1.name} و {p2.name} — tie؟ فالfootball؟ هادا rare بزاف.",
            f"🤝 {p1.name} و {p2.name} — كتبانو بحال twins، ولكن فالعكس.",
        ]
        return random.choice(phrases)

    def milestone_alert(self, player: PlayerStats, stat: str, threshold: int) -> str:
        emojis = {"goals": "⚽", "assists": "🅰️", "mvps": "🏆", "frauds": "🎭", "possession_losses": "💀", "games": "🎮", "tackles": "🛡️"}
        emoji = emojis.get(stat, "🔥")
        if stat == "goals":
            return f"🚨 {player.name} وصل لـ {threshold} goals! {emoji}\nالتاريخ كيتكتب بدمه."
        elif stat == "assists":
            return f"🚨 {player.name} وصل لـ {threshold} assists! {emoji}\nصانع الألعاب الحقيقي."
        elif stat == "mvps":
            return f"🚨 {player.name} وصل لـ {threshold} MVPs! {emoji}\nالملك ما كيحتاجش دليل."
        elif stat == "frauds":
            return f"🚨 {player.name} وصل لـ {threshold} frauds! {emoji}\nهادا رقم تاريخي... فالعكس."
        elif stat == "possession_losses":
            return f"🚨 {player.name} وصل لـ {threshold} possession losses! {emoji}\nالكرة خاصها restraining order."
        elif stat == "games":
            return f"🚨 {player.name} وصل لـ {threshold} games! {emoji}\nولاء تاريخي للفريق."
        elif stat == "tackles":
            return f"🚨 {player.name} وصل لـ {threshold} tackles! {emoji}\nالدفاع بدا من عندو."
        else:
            return f"🚨 {player.name} وصل لـ {threshold} {stat}! {emoji}"

    def excuses(self, player: PlayerStats) -> str:
        excuses_pool = [
            "الكونترول كان فيه lag", "النت كان مقطع", "اليد كانت مقلوبة", "القط قطع عليا النت",
            "الكونترول ناقص البطارية", "الشاشة كانت مظلمة", "كنت لابس الجوارب و الزليج زلق",
            "الكرسي كان مرتفع", "النور كان كيدور فعينيا", "الكونترول جديد وماشي معتاد عليه",
            "الwifi ديال الجيران دخل", "العشا كان تقيل", "كنت سهران البارح",
            "الخوخة ديال الداكرة كانت عاملة", "الجو كان حار", "ال conditioning ديالي كان off",
            "كنت كنتفكر فالexam", "الphone ديالي دار notification", "الأم كانت كتنادي",
            "الwater bottle طاح فالكونترول", "الcat walked on the controller",
            "الحارس كان كيدير glitch", "الgoalkeeper كان level 99", "القائم كان كيدافع عليا",
            "الكورة ما بغاتش تدخل", "الwind factor كان ضدي", "الkeeper دار superman dive",
            "كنت كنتجرب new finishing style", "الformation ما كانتش مناسبة", "الtactics كانت zonal marking",
            "الملعب كان زلق", "الحكم ما دارش foul", "الlinesman كان عندو نظارة قديمة",
        ]
        selected = []
        if player.rating_pg < 6.0:
            selected.append("الكونترول كان فيه lag")
        if player.possession_losses > 10:
            selected.append("النت كان مقطع")
        if player.goals == 0 and player.games > 2:
            selected.append("القط قطع عليا النت")
        if player.pass_accuracy < 70:
            selected.append("اليد كانت مقلوبة")
        while len(selected) < 4:
            exc = random.choice(excuses_pool)
            if exc not in selected:
                selected.append(exc)
        random.shuffle(selected)
        text = f"📝 **EXCUSES — {player.name}**\n\n"
        text += f"الدفاع ديال {player.name} فالمحكمة:\n\n"
        for i, excuse in enumerate(selected[:5], 1):
            text += f"{i}. {excuse}\n"
        text += "\n⚖️ **الحكم:** هاد الأعذار أضعف من defense ديال الفريق."
        return text

    def weekly_award(self, award_type: str, player: PlayerStats, score: float) -> str:
        if award_type == "fraud_of_the_week":
            phrases = [
                f"🎭 {player.name} — Fraud of the Week! Score: {score}/100.\nهاد الأسبوع كامل كتخدم على راسك.",
                f"🎭 {player.name} — Fraud of the Week!\nالتحقيق مازال مفتوح.",
                f"🎭 {player.name} — Fraud of the Week!\nالأدلة واضحة بزاف.",
            ]
        elif award_type == "ghost_of_the_week":
            phrases = [
                f"👻 {player.name} — Ghost of the Week!\nكنت مختافي حتى من الكاميرا.",
                f"👻 {player.name} — Ghost of the Week!\n90 دقيقة ديال التخفي.",
                f"👻 {player.name} — Ghost of the Week!\nحتى replay ما جابكش.",
            ]
        elif award_type == "mvp_of_the_week":
            phrases = [
                f"🏆 {player.name} — MVP of the Week!\nالفريق بلاك بحال WiFi bla router.",
                f"🏆 {player.name} — MVP of the Week!\nشاد الفريق فوق ضهرك.",
                f"🏆 {player.name} — MVP of the Week!\nأداء ديال الكبار.",
            ]
        elif award_type == "ball_loser_of_the_week":
            phrases = [
                f"💀 {player.name} — Ball Loser of the Week!\nالكرة ما بقاتش باغيا تبقى عندك.",
                f"💀 {player.name} — Ball Loser of the Week!\nكنت موزع رسمي ديال الكرات.",
                f"💀 {player.name} — Ball Loser of the Week!\nRecord جديد فضياع الكرة.",
            ]
        elif award_type == "carry_of_the_week":
            phrases = [
                f"💪 {player.name} — Carry of the Week!\nالفريق كامل راكب فوق ضهرك.",
                f"💪 {player.name} — Carry of the Week!\nإلى ما كنتيش فالملعب كون خسرنا.",
                f"💪 {player.name} — Carry of the Week!\nكتجر الفريق بوحدك.",
            ]
        else:
            phrases = [f"🏆 {player.name} — Winner! Score: {score}"]
        return random.choice(phrases)

    def match_poster_caption(self, poster_data: dict) -> str:
        result = poster_data.get("result", "D")
        opponent = poster_data.get("opponent", "Unknown")
        score = poster_data.get("score", "?-?")
        if result == "W":
            text = f"✅ فوز {score} vs {opponent}!\n\n"
        elif result == "L":
            text = f"❌ خسارة {score} vs {opponent}.\n\n"
        else:
            text = f"🤝 تعادل {score} vs {opponent}.\n\n"
        if poster_data.get("mvp"):
            mvp = poster_data["mvp"]
            text += f"🏆 MVP: {mvp['name']} ({mvp['carry_score']} carry score)\n"
        if poster_data.get("fraud"):
            fraud = poster_data["fraud"]
            text += f"🎭 Fraud: {fraud['name']} ({fraud['fraud_score']} fraud score)\n"
        if poster_data.get("ghost") and poster_data["ghost"]["is_ghost"]:
            ghost = poster_data["ghost"]
            text += f"👻 Ghost: {ghost['name']} ({ghost['ghost_points']} ghost points)\n"
        if poster_data.get("carry"):
            carry = poster_data["carry"]
            text += f"💪 Carry: {carry['name']} ({carry['carry_score']} carry score)\n"
        if poster_data.get("top_performer"):
            tp = poster_data["top_performer"]
            text += f"⭐ Top: {tp['name']} (Rating {tp['rating']})\n"
        if poster_data.get("worst_performer"):
            wp = poster_data["worst_performer"]
            text += f"📉 Worst: {wp['name']} (Rating {wp['rating']})\n"
        return text
