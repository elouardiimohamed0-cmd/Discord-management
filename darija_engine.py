import random
from typing import List, Optional, Any
from models import PlayerStats
​
class DarijaEngine:
"""
Generates Darija (Moroccan Arabic) roasts, praises, captions, and reports
for the EA FC Pro Clubs Discord bot.
Phase 3 upgrade:
None-safe interpolation everywhere (no more literal "None" in output).
Expanded template pools (8–14 lines per category).
Defensive attribute access (handles partial PlayerStats objects).
All public method signatures preserved — drop-in replacement.
"""
────────────────────────────────────────────
CONSTRUCTOR
────────────────────────────────────────────
def init(self, squad_data):
Guard against string/None (legacy bug protection)
if isinstance(squad_data, str) or squad_data is None:
squad_data = {}
self.squad = squad_data
Normalize to a list of player dicts (handles flat dict AND "players" list)
players = []
if isinstance(squad_data, dict):
if "players" in squad_data and isinstance(squad_data.get("players"), list):
players = squad_data["players"]
else:
Flat dict like {"dictator": {...}, "shark": {...}}
players = list(squad_data.values())
elif isinstance(squad_data, list):
players = squad_data
self.nicknames = {}
self.bios = {}
for p in players:
if not isinstance(p, dict):
continue
name = p.get("name", "")
if isinstance(name, str) and name.strip():
self.nicknames[name.lower()] = p.get("nickname", "") or ""
self.bios[name.lower()] = p.get("bio", "") or ""
────────────────────────────────────────────
INTERNAL SAFETY HELPERS (Phase 3)
────────────────────────────────────────────
@staticmethod
def _safe(value: Any, fallback: str = "—") -> str:
"""Coerce any value to a printable string, never returning literal 'None'."""
if value is None:
return fallback
s = str(value).strip()
if not s or s.lower() == "none":
return fallback
return s
@staticmethod
def _attr(player: Any, name: str, fallback: Any = 0) -> Any:
"""Safe getattr that also normalizes None to a fallback."""
v = getattr(player, name, fallback)
if v is None:
return fallback
return v
def _name(self, player: Any) -> str:
return self._safe(self._attr(player, "name", "Unknown"), "Unknown")
def _pos(self, player: Any) -> str:
return self._safe(self._attr(player, "position", "CM"), "CM")
────────────────────────────────────────────
NICKNAME / BIO LOOKUP
────────────────────────────────────────────
def get_nickname(self, name: str) -> str:
if not isinstance(name, str) or not name.strip():
return ""
return self.nicknames.get(name.lower(), name)
def get_bio(self, name: str) -> str:
if not isinstance(name, str) or not name.strip():
return ""
return self.bios.get(name.lower(), "")
────────────────────────────────────────────
ROASTS
────────────────────────────────────────────
def roast(self, player: PlayerStats, roast_type: str = "general") -> str:
name = self._name(player)
nick = self._safe(self.get_nickname(name), name)
bio = self._safe(self.get_bio(name), "لاعب من المغرب")
pos = self._pos(player)
goals = self._attr(player, "goals", 0)
games = self._attr(player, "games", 0)
rating = round(float(self._attr(player, "rating_pg", 0.0) or 0.0), 1)
fraud_phrases = [
f" {name} ({nick}) — كيفاش كتقدر تلعب {pos} وما كتعرفش تلعب؟",
f" {name} — الأداء ديالك اليوم كيهضر بزاف على خيبتك.",
f" {name} — كنتي فالماتش ولا كنتي فالكافيه؟",
f" {name} — الـrating ديالك أقل من temperature ديال الثلاجة.",
f" {name} — {bio} ولكن اليوم كتبان بحال لاعب ديال iron 4.",
f" {name} — كتسجل {goals} goals فـ{games} games. هادا مشي average، هادا disaster.",
f" {name} — الكورة كتفوت عليك أكثر من الـnotifications ديال الـInstagram.",
f" {name} — كتضيع الكورة بزاف. حتى الكورة بدا ليها sympathy.",
f" {name} — كتبان بحال لاعب كيتعلم football من YouTube tutorials.",
f" {name} — rating {rating}؟ حتى الـAI ديال career mode كتدير أحسن.",
f" {name} — كل ماتش كتجي بـexcuse جديدة. خاصك تكتب book.",
f" {name} — الفريق كيلعب 10 vs 11 ملي كتكون فالملعب.",
f" {name} — كاين فرق بين {pos} و spectator؟ نتا غادي توضحلنا.",
f" {name} — هاد الأداء ماشي rebuild، هادا demolition.",
]
ghost_phrases = [
f" {name} — كنتي فالماتش ولا كنتي ghost؟",
f" {name} — 90 دقيقة وما شفناكش. حتى الـcamera ما لقتكش.",
f" {name} — كتبان بحال player invisible. حتى الـradar ما كتبانش.",
f" {name} — الأداء ديالك اليوم: 0 tackles, 0 interceptions, 0 presence.",
f" {name} — كتجري بلا ball. حتى الـwind كتجري أسرع منك.",
f" {name} — heatmap ديالك أكثر cold من Antarctica.",
f" {name} — minimap ما عمرها بانت فيها نقطة ديالك.",
f" {name} — كنت present فالماتش بحال WiFi signal فالـbasement.",
f" {name} — حتى الـcommentator نسا اسمك فالأخير.",
f" {name} — touches ديالك اليوم أقل من touches ديال الحارس.",
]
carry_phrases = [
f" {name} — كتجر الفريق بوحدك. باقي اللاعبين كيتفرجو.",
f" {name} — الأداء ديالك اليوم: goals {goals}, rating {rating}. الفريق بلاك بحال WiFi bla router.",
f" {name} — كتسجل أكثر من الـstriker. وكتدافع أكثر من الـdefender. شنو باغي تكون؟",
f" {name} — الـrating ديالك {rating}. هادا مشي rating، هادا cheat code.",
f" {name} — وحدك كتلعب ضد 11. وباقي كتربح.",
f" {name} — كتدير 1v11 وكتخرج فايز. هادا level ديال main character.",
f" {name} — الفريق كامل عايش على ضهرك. خصك chiropractor.",
f" {name} — حتى الـopposition بداو كيصفقو ليك.",
]
if roast_type == "fraud":
return random.choice(fraud_phrases)
elif roast_type == "ghost":
return random.choice(ghost_phrases)
elif roast_type == "carry":
return random.choice(carry_phrases)
else:
return random.choice(fraud_phrases + ghost_phrases)
────────────────────────────────────────────
PRAISES
────────────────────────────────────────────
def praise(self, player: PlayerStats) -> str:
name = self._name(player)
nick = self._safe(self.get_nickname(name), name)
goals = self._attr(player, "goals", 0)
assists = self._attr(player, "assists", 0)
rating = round(float(self._attr(player, "rating_pg", 0.0) or 0.0), 1)
phrases = [
f" {name} ({nick}) — الأداء ديالك اليوم كان أسطوري!",
f" {name} — كتسجل {goals} goals و {assists} assists. هادا مشي لاعب، هادا machine!",
f" {name} — الـrating ديالك {rating}. حتى الـMessi كيتفرج عليك.",
f" {name} — الفريق بلاك بحال phone bla battery.",
f" {name} — كتدافع، كتهاجم، كتباصي. شنو باغي تكون؟ Superhero؟",
f" {name} — هاد الأداء خاصو يدخل museum ديال football.",
f" {name} — كل touch ديالك كيشعل الجمهور.",
f" {name} — rating {rating} مع {goals} goals — هادا cheat code رسمي.",
f" {name} — الـopposition كانوا كيدعيو يخرج {nick} من الملعب.",
f" {name} — هاد الـperformance غادي يكون highlight ديال الweek.",
]
return random.choice(phrases)
────────────────────────────────────────────
MATCH HELPERS
────────────────────────────────────────────
def match_summary(self, match_result: dict) -> str:
if not isinstance(match_result, dict):
match_result = {}
score = self._safe(match_result.get("score"), "?-?")
opponent = self._safe(match_result.get("opponent"), "Unknown")
result = self._safe(match_result.get("result"), "D")
if result == "W":
return f" فوز {score} vs {opponent}! الفريق كامل شاد."
elif result == "L":
return f" خسارة {score} vs {opponent}. الفريق خاصو يتجمع."
else:
return f" تعادل {score} vs {opponent}. نتيجة عادلة."
def leaderboard_intro(self, club_name: str) -> str:
club_name = self._safe(club_name, "الفريق")
phrases = [
f" Leaderboard ديال {club_name} — الأرقام ما كتكدبش!",
f" {club_name} — شكون كيسيطر، شكون كيتسيطر عليه.",
f" ها هوا الحقيقة ديال {club_name} — بلا feelings، بلا emotions.",
f" {club_name} — الـrankings ديال هاد الأسبوع، خاصة لكل واحد يقرا بعينيه.",
f" {club_name} — الترتيب الرسمي. الـreceipts كاينين.",
]
return random.choice(phrases)
def player_card_caption(self, player: PlayerStats) -> str:
name = self._name(player)
nick = self._safe(self.get_nickname(name), name)
bio = self._safe(self.get_bio(name), "لاعب من المغرب")
rating = round(float(self._attr(player, "rating_pg", 0.0) or 0.0), 1)
goals = self._attr(player, "goals", 0)
assists = self._attr(player, "assists", 0)
line = f"Rating: {rating} | Goals: {goals} | Assists: {assists}"
if rating >= 8.0:
return (
f" {name} ({nick}) — {bio}n{line}n"
f"هادا لاعب كيبان مرة فالعمر."
)
elif rating >= 6.5:
return (
f" {name} ({nick}) — {bio}n{line}n"
f"أداء مقبول، ولكن يمكن أحسن."
)
else:
return (
f" {name} ({nick}) — {bio}n{line}n"
f"الأداء ديالك اليوم خاصو review."
)
────────────────────────────────────────────
COURT CASE / FRAUD VERDICT
────────────────────────────────────────────
def court_case(self, player: PlayerStats, charges: Optional[List[str]] = None) -> str:
name = self._name(player)
if not charges:
throwing = round(float(self._attr(player, "throwing_score", 0.0) or 0.0), 1)
error = round(float(self._attr(player, "error_score", 0.0) or 0.0), 1)
rating = round(float(self._attr(player, "rating_pg", 0.0) or 0.0), 1)
charges = [
f"Throwing score: {throwing}",
f"Error score: {error}",
f"Rating: {rating}",
]
text = f" المحكمة الرياضية — قضية {name}nn"
text += "التهم:n"
for i, charge in enumerate(charges, 1):
text += f"{i}. {self._safe(charge, '—')}n"
text += f"nالحكم: {name} مذنب فكل التهم. الحكم: lifetime ban من الـstarting XI."
return text
def fraud_verdict(self, player: PlayerStats) -> str:
name = self._name(player)
phrases = [
f" {name} — التحقيق خلص. الأدلة واضحة. Fraud confirmed.",
f" {name} — كتبان بحال لاعب، ولكن فالحقيقة كتبان بحال spectator.",
f" {name} — الـjury ما حتى تخيلت. الحكم: مذنب.",
f" {name} — fraud detector دار overheat ملي شافك.",
f" {name} — الـfans طالبين refund. والفريق طالب transfer.",
f" {name} — كل ماتش = receipt جديدة فالـcase file.",
]
return random.choice(phrases)
────────────────────────────────────────────
DIGEST / SUMMARY
────────────────────────────────────────────
def daily_digest(self, stats: dict) -> str:
if not isinstance(stats, dict):
stats = {}
text = " Daily Digestnn"
text += (
f"Games: {self._safe(stats.get('games'), '0')} | "
f"Wins: {self._safe(stats.get('wins'), '0')} | "
f"Losses: {self._safe(stats.get('losses'), '0')}n"
)
text += f"Top Scorer: {self._safe(stats.get('top_scorer'), 'N/A')}n"
text += f"Top Fraud: {self._safe(stats.get('top_fraud'), 'N/A')}n"
text += f"MOTM: {self._safe(stats.get('motm'), 'N/A')}n"
return text
────────────────────────────────────────────
HALL OF FAME / SHAME
────────────────────────────────────────────
def hall_of_fame(self, records: list) -> str:
if not records:
return " Hall of Famennما كاين حتى شي record لحد الآن."
text = " HALL OF FAME — التاريخ ما كينساشnn"
praises = [
"هادا الأداء ديال الأساطير.",
"التاريخ غادي يتذكر هاد اللحظة.",
"هادا مشي لاعب، هادا phenomenon.",
"الأرقام كتهضر بوحدها.",
"هادا level ديال Ballon d'Or.",
"الفريق بلا هاد اللاعب بحال WiFi bla router.",
"حتى الـopposition دارو standing ovation.",
"هادا highlight ديال الـseason.",
]
for rec in records[:3]:
pname = self._safe(getattr(rec, "player_name", None), "Unknown")
desc = self._safe(getattr(rec, "description", None), "—")
text += f" {pname} — {desc}n"
text += f"   {random.choice(praises)}nn"
return text
def fame_praise(self, player: PlayerStats) -> str:
name = self._name(player)
phrases = [
f" {name} — هادا لاعب كيبان مرة فالعمر.",
f" {name} — الأداء ديالو اليوم غادي يتدرس فالمدارس.",
f" {name} — من فاش كانت اللعبة لعبة، حتى بقات industry.",
f" {name} — هادا مشي performance، هادا masterpiece.",
f" {name} — الملعب كامل وقف ليه التحية.",
f" {name} — هاد الـrun ديالو غادي يدخل folklore.",
]
return random.choice(phrases)
def hall_of_shame_enhanced(self, records: list) -> str:
if not records:
return " Hall of Shamennما كاين حتى شي record لحد الآن."
text = " HALL OF SHAME — الأرقام ما كتكدبشnn"
roasts = self._shame_roasts()
for rec in records[:3]:
pname = self._safe(getattr(rec, "player_name", None), "Unknown")
desc = self._safe(getattr(rec, "description", None), "—")
text += f" {pname} — {desc}n"
text += f"   {random.choice(roasts)}nn"
return text
@staticmethod
def _shame_roasts() -> List[str]:
return [
"هادا الأداء خاصو يتعرض فالمحكمة.",
"التاريخ غادي يتذكرك، ولكن فالعكس.",
"هادا مشي لاعب، هادا case study.",
"الأرقام كتهضر بوحدها — وكتقول خايب.",
"هادا level ديال iron 4.",
"الفريق بلا هاد اللاعب كيكون أحسن.",
"VAR رفع يديه من داك الأداء.",
"حتى الـAI ما يخدمش بهاد الـlogic.",
"هاد الـperformance غادي يدخل training video — مثال على ما يجب تجنبه.",
]
────────────────────────────────────────────
RIVALRY
────────────────────────────────────────────
def rivalry_roast(self, winner: PlayerStats, loser: PlayerStats, stats: dict) -> str:
if not isinstance(stats, dict):
stats = {}
wname = self._name(winner)
lname = self._name(loser)
if stats.get("overall_winner") == wname:
diff = stats.get("p1_categories_won", 0)
else:
diff = stats.get("p2_categories_won", 0)
try:
diff_int = int(diff or 0)
except (TypeError, ValueError):
diff_int = 0
roasts = [
f" {lname} — {wname} كيدرك فكل شي. حتى فالخسارة كتخسر.",
f" {lname} — rivalry ماشي rivalry هادي bullying رسمي.",
f" {lname} — {wname} كيلعب ونت كتجي تشوف. هادا الفرق.",
f" {lname} — الأرقام كلها ضدك. حتى المحامي ديالك غادي يستقيل.",
f" {lname} — من بعد هاد المقارنة، خاصك تبدل hobby.",
f" {lname} — {wname} كيسجل أكثر، كيباصي أحسن، وكيفوز أكثر. ونت؟ كتاخد oxygen.",
f" {lname} — هاد المقارنة خاصها NSFW tag.",
]
text = random.choice(roasts)
text += f"nn الفرق: {diff_int} categories. هادا ماشي close، هادا massacre."
return text
def rivalry_tie(self, p1: PlayerStats, p2: PlayerStats) -> str:
n1 = self._name(p1)
n2 = self._name(p2)
phrases = [
f" {n1} و {n2} — بحال بحال. rivalry ماشي واضحة، ماشي حتى friendship.",
f" {n1} و {n2} — tie؟ فالfootball؟ هادا rare بزاف.",
f" {n1} و {n2} — كتبانو بحال twins، ولكن فالعكس.",
f" {n1} و {n2} — كل واحد كيقول راه الأحسن. الأرقام كتقول لا.",
]
return random.choice(phrases)
────────────────────────────────────────────
MILESTONES
────────────────────────────────────────────
def milestone_alert(self, player: PlayerStats, stat: str, threshold: int) -> str:
name = self._name(player)
stat_key = self._safe(stat, "stat")
try:
threshold_int = int(threshold)
except (TypeError, ValueError):
threshold_int = 0
emojis = {
"goals": "", "assists": "", "mvps": "", "frauds": "",
"possession_losses": "", "games": "", "tackles": "",
}
emoji = emojis.get(stat_key, "")
if stat_key == "goals":
return f" {name} وصل لـ {threshold_int} goals! {emoji}nالتاريخ كيتكتب بدمه."
elif stat_key == "assists":
return f" {name} وصل لـ {threshold_int} assists! {emoji}nصانع الألعاب الحقيقي."
elif stat_key == "mvps":
return f" {name} وصل لـ {threshold_int} MVPs! {emoji}nالملك ما كيحتاجش دليل."
elif stat_key == "frauds":
return f" {name} وصل لـ {threshold_int} frauds! {emoji}nهادا رقم تاريخي... فالعكس."
elif stat_key == "possession_losses":
return f" {name} وصل لـ {threshold_int} possession losses! {emoji}nالكرة خاصها restraining order."
elif stat_key == "games":
return f" {name} وصل لـ {threshold_int} games! {emoji}nولاء تاريخي للفريق."
elif stat_key == "tackles":
return f" {name} وصل لـ {threshold_int} tackles! {emoji}nالدفاع بدا من عندو."
else:
return f" {name} وصل لـ {threshold_int} {stat_key}! {emoji}"
────────────────────────────────────────────
EXCUSES
────────────────────────────────────────────
def excuses(self, player: PlayerStats) -> str:
name = self._name(player)
rating = float(self._attr(player, "rating_pg", 0.0) or 0.0)
poss_loss = float(self._attr(player, "possession_losses", 0) or 0)
goals = int(self._attr(player, "goals", 0) or 0)
games = int(self._attr(player, "games", 0) or 0)
pass_acc = float(self._attr(player, "pass_accuracy", 100.0) or 100.0)
excuses_pool = [
"الكونترول كان فيه lag", "النت كان مقطع", "اليد كانت مقلوبة", "القط قطع عليا النت",
"الكونترول ناقص البطارية", "الشاشة كانت مظلمة", "كنت لابس الجوارب و الزليج زلق",
"الكرسي كان مرتفع", "النور كان كيدور فعينيا", "الكونترول جديد وماشي معتاد عليه",
"الwifi ديال الجيران دخل", "العشا كان تقيل", "كنت سهران البارح",
"الخوخة ديال الداكرة كانت عاملة", "الجو كان حار", "الـair conditioning ديالي كان off",
"كنت كنتفكر فالexam", "الphone ديالي دار notification", "الأم كانت كتنادي",
"الwater bottle طاح فالكونترول", "القط مشى على الكونترول",
"الحارس كان كيدير glitch", "الgoalkeeper كان level 99", "القائم كان كيدافع عليا",
"الكورة ما بغاتش تدخل", "الـwind factor كان ضدي", "الـkeeper دار superman dive",
"كنت كنتجرب new finishing style", "الـformation ما كانتش مناسبة",
"الـtactics كانت zonal marking", "الملعب كان زلق",
"الحكم ما دارش foul", "الـlinesman كان عندو نظارة قديمة",
"الـserver كان فـEU وأنا فالمغرب", "الـping كان 200+",
"الـpatch الجديد كسر الـmechanics", "الـAI ديال الفريق كان NPC mode",
]
selected: List[str] = []
if rating < 6.0:
selected.append("الكونترول كان فيه lag")
if poss_loss > 10:
selected.append("النت كان مقطع")
if goals == 0 and games > 2:
selected.append("القط قطع عليا النت")
if pass_acc < 70:
selected.append("اليد كانت مقلوبة")
while len(selected) < 5:
exc = random.choice(excuses_pool)
if exc not in selected:
selected.append(exc)
random.shuffle(selected)
text = f" EXCUSES — {name}nn"
text += f"الدفاع ديال {name} فالمحكمة:nn"
for i, excuse in enumerate(selected[:5], 1):
text += f"{i}. {excuse}n"
text += "n الحكم: هاد الأعذار أضعف من defense ديال الفريق."
return text
────────────────────────────────────────────
WEEKLY AWARDS
────────────────────────────────────────────
def weekly_award(self, award_type: str, player: PlayerStats, score: float) -> str:
name = self._name(player)
try:
score_str = str(round(float(score), 1))
except (TypeError, ValueError):
score_str = "—"
if award_type == "fraud_of_the_week":
phrases = [
f" {name} — Fraud of the Week! Score: {score_str}/100.nهاد الأسبوع كامل كتخدم على راسك.",
f" {name} — Fraud of the Week!nالتحقيق مازال مفتوح.",
f" {name} — Fraud of the Week!nالأدلة واضحة بزاف.",
f" {name} — Fraud of the Week!nالـcase موثقة وموقعة.",
]
elif award_type == "ghost_of_the_week":
phrases = [
f" {name} — Ghost of the Week!nكنت مختافي حتى من الكاميرا.",
f" {name} — Ghost of the Week!n90 دقيقة ديال التخفي.",
f" {name} — Ghost of the Week!nحتى replay ما جابكش.",
f" {name} — Ghost of the Week!nminimap ديالك كان dark mode.",
]
elif award_type == "mvp_of_the_week":
phrases = [
f" {name} — MVP of the Week!nالفريق بلاك بحال WiFi bla router.",
f" {name} — MVP of the Week!nشاد الفريق فوق ضهرك.",
f" {name} — MVP of the Week!nأداء ديال الكبار.",
f" {name} — MVP of the Week!nهاد الأسبوع كان show ديالك.",
]
elif award_type == "ball_loser_of_the_week":
phrases = [
f" {name} — Ball Loser of the Week!nالكرة ما بقاتش باغيا تبقى عندك.",
f" {name} — Ball Loser of the Week!nكنت موزع رسمي ديال الكرات.",
f" {name} — Ball Loser of the Week!nRecord جديد فضياع الكرة.",
f" {name} — Ball Loser of the Week!nالـopposition قالو شكرا.",
]
elif award_type == "carry_of_the_week":
phrases = [
f" {name} — Carry of the Week!nالفريق كامل راكب فوق ضهرك.",
f" {name} — Carry of the Week!nإلى ما كنتيش فالملعب كون خسرنا.",
f" {name} — Carry of the Week!nكتجر الفريق بوحدك.",
f" {name} — Carry of the Week!nlone wolf، lone scorer.",
]
else:
phrases = [f" {name} — Winner! Score: {score_str}"]
return random.choice(phrases)
────────────────────────────────────────────
MATCH POSTER
────────────────────────────────────────────
def match_poster_caption(self, poster_data: dict) -> str:
if not isinstance(poster_data, dict):
poster_data = {}
result = self._safe(poster_data.get("result"), "D")
opponent = self._safe(poster_data.get("opponent"), "Unknown")
score = self._safe(poster_data.get("score"), "?-?")
if result == "W":
text = f" فوز {score} vs {opponent}!nn"
elif result == "L":
text = f" خسارة {score} vs {opponent}.nn"
else:
text = f" تعادل {score} vs {opponent}.nn"
mvp = poster_data.get("mvp")
if isinstance(mvp, dict):
text += (
f" MVP: {self._safe(mvp.get('name'), 'Unknown')} "
f"({self._safe(mvp.get('carry_score'), '0')} carry score)n"
)
fraud = poster_data.get("fraud")
if isinstance(fraud, dict):
text += (
f" Fraud: {self._safe(fraud.get('name'), 'Unknown')} "
f"({self._safe(fraud.get('fraud_score'), '0')} fraud score)n"
)
ghost = poster_data.get("ghost")
if isinstance(ghost, dict) and ghost.get("is_ghost"):
text += (
f" Ghost: {self._safe(ghost.get('name'), 'Unknown')} "
f"({self._safe(ghost.get('ghost_points'), '0')} ghost points)n"
)
carry = poster_data.get("carry")
if isinstance(carry, dict):
text += (
f" Carry: {self._safe(carry.get('name'), 'Unknown')} "
f"({self._safe(carry.get('carry_score'), '0')} carry score)n"
)
tp = poster_data.get("top_performer")
if isinstance(tp, dict):
text += (
f" Top: {self._safe(tp.get('name'), 'Unknown')} "
f"(Rating {self._safe(tp.get('rating'), '0')})n"
)
wp = poster_data.get("worst_performer")
if isinstance(wp, dict):
text += (
f" Worst: {self._safe(wp.get('name'), 'Unknown')} "
f"(Rating {self._safe(wp.get('rating'), '0')})n"
)
return text
────────────────────────────────────────────
BACKWARD-COMPAT SHIMS (called by bot.py)
────────────────────────────────────────────
def fraud(self, player: PlayerStats) -> str:
return self.fraud_verdict(player)
def carry(self, player: PlayerStats) -> str:
return self.praise(player)
def ghost(self, player: PlayerStats) -> str:
return self.roast(player, "ghost")
def ball_loser(self, player: PlayerStats) -> str:
return self.roast(player, "fraud")
def playmaker(self, player: PlayerStats) -> str:
return self.praise(player)
def keeper(self, player: PlayerStats) -> str:
name = self._name(player)
phrases = [
f" {name} — الحارس ديالنا كيتسطى!",
f" {name} — كيدافع بزاف، كيحبس بزاف.",
f" {name} — كيحمي المرمى بحال wall.",
f" {name} — clean sheet مع style.",
f" {name} — هاد الـsaves خاصها slow-mo replay.",
]
return random.choice(phrases)
def compare(self, p1: PlayerStats, p2: PlayerStats) -> str:
n1 = self._name(p1)
n2 = self._name(p2)
g1 = self._attr(p1, "goals", 0)
g2 = self._attr(p2, "goals", 0)
a1 = self._attr(p1, "assists", 0)
a2 = self._attr(p2, "assists", 0)
r1 = round(float(self._attr(p1, "rating_pg", 0.0) or 0.0), 1)
r2 = round(float(self._attr(p2, "rating_pg", 0.0) or 0.0), 1)
i1 = self._attr(p1, "impact_score", 0)
i2 = self._attr(p2, "impact_score", 0)
text = f" {n1} vs {n2}nn"
text += f"Goals: {g1} vs {g2}n"
text += f"Assists: {a1} vs {a2}n"
text += f"Rating: {r1} vs {r2}n"
text += f"Impact: {i1} vs {i2}n"
return text
def hall_of_shame(self, players: list) -> str:
if not players:
return " Hall of Shamennما كاين حتى شي player لحد الآن."
text = " HALL OF SHAME — الأرقام ما كتكدبشnn"
roasts = self._shame_roasts()
worst = sorted(
players,
key=lambda p: float(self._attr(p, "rating_pg", 0.0) or 0.0),
)[:3]
for p in worst:
pname = self._name(p)
rating = round(float(self._attr(p, "rating_pg", 0.0) or 0.0), 1)
text += f" {pname} — Rating: {rating}n"
text += f"   {random.choice(roasts)}nn"
return text
def match_report(self, result: str, match_players: list) -> str:
result_str = self._safe(result, "—")
text = f" Match Result: {result_str}nn"
if match_players:
for p in match_players:
pname = self._name(p)
g = self._attr(p, "goals", 0)
a = self._attr(p, "assists", 0)
r = round(float(self._attr(p, "rating_pg", 0.0) or 0.0), 1)
text += f"• {pname}: {g}G, {a}A, {r}Rn"
return text
