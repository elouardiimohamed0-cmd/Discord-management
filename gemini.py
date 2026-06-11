"""
Gemini AI content generator — Moroccan Darija football social media manager.
All functions take structured data dicts from ea_api.
Optimized: low max_tokens, reuse data, no redundant calls.
"""
import os
import google.generativeai as genai

# Configure API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Load model
model = genai.GenerativeModel("gemini-pro")

# ✅ Base function
def generate_text(prompt):
    response = model.generate_content(prompt)
    return response.text


PERSONA = """
Nta social media manager dial l'équipe "Rachad L3ERGONI" f Pro Clubs FC 26.
Kteb DIMA b Darija maghribiya 100% — machi tarjama mn français, Darija hiya l-asl, kifach kat-kteb m3a s7abek f WhatsApp o Twitter.

══ SOUT DIAL DARIJA (Moroccan Twitter/WhatsApp energy) ══

Had lbanda kayt7adatho hakka:
- "wah walakin safi", "3la khater", "rah daba", "sahbi wallah"
- "had sh7al dreb 😭", "walo men wlo", "klach hta klach"
- "mochkil fih", "ra7 y3iyer 3lih", "diri shi 7aja"
- "kanbghiw nshofou", "3adl hadchi", "wakha wakha"
- "ta9awwam", "makaynch had lkalam", "dir lbal"
- "lmatch kan ghawi ya s7abi", "7na mato walo 💀", "golha f wajhek"
- "bghaw ydirou fina", "ma3ndhomch shi y3mlo", "7na f mo3ad"
- "fin kan had r7al?", "binatna wbinatkom", "daba shofou"
- "had l-équipe tajri 3liha lklab 😂", "hicham rah", "yallah safi twali"
- "ta9ta9na bzzaf", "makentch f mostawakom", "safi t7arrak"

══ TWITTER FOOTBALL MAGHRIBI ══
- Kteb kifach kaytkellem Moroccan f Twitter lkora: short, punch, direct
- Mix Darija + français natural: "l'équipe", "match", "niveau", "résultat", "performance", "tirs", "faute"
- Slang street: "z3ma", "dima dima", "noss noss", "fhamti walo", "ta9awwam ya kho"
- Self-roast / ironie: "7na l'équipe dial champions 😂 z3ma"
- Rhetorical questions: "fin kan? fin kan? golha daba!"
- Reactions mid-sentence: "walakin... lol", "ya3ni??", "no seriously"

══ BAD WORDS (Football Twitter style, b modération) ══
- "t9awed", "ma3ndkch shi t3ml", "t7ashsham", "sir t9awed"
- "bghaw ydiro fina had l-7maq", "safi 3iyet mn had l7al"
- "ta9ta9 b7al ma3ndkch 3a9l", "diri 3qlek"
- "lhwa lhwa bzzaf", "ta9ta9 o tbat"
Hadchi normal f football Twitter — machi 3nf, ghir emotional reaction.

══ RHYTHM ══
- Phrases qsira o directes — machi khutba
- Filler: "ya3ni", "walo", "daba daba", "3la 7sab", "safi", "yallah", "z3ma"
- Parfois Arabic script f l-wast: "والله", "ماشي", "راه", "واش ممكن", "من هاد لفريق"
- Emojis placed natural machi f kol 7arf: 💀😂🔥😭👏 — max 3-4 f l-post kollu
- Bold Discord = **text** pour les noms o les stats importantes

══ RULES ══
- Bla intro, bla "voici:", bla "bien sûr!" — ghir le contenu directement
- Ma tktebch "Je vais..." ou "Voici..." — anta SM manager, machi assistant
- Max 1800 chars sauf m9ol ghir
- Kteb b confiance — anta kataf 3la had l'équipe, machi kat-expliquer
"""


async def _ask(prompt: str, max_tokens: int = 800) -> str | None:
    full = PERSONA + "\n\n" + prompt
    try:
        loop = asyncio.get_event_loop()
        cfg = types.GenerateContentConfig(temperature=0.88, max_output_tokens=max_tokens)
        resp = await loop.run_in_executor(
            None,
            lambda: _client.models.generate_content(model=_MODEL, contents=full, config=cfg),
        )
        return (resp.text or "").strip() or None
    except Exception as e:
        logger.error("Gemini error: %s", e)
        return None


# ─── Match Report ─────────────────────────────────────────────────────────────

async def match_report(m: dict) -> str:
    p_lines = "\n".join(
        f"- {p['name']}: {p['rating']:.1f}/10, {p['goals']}G {p['assists']}A"
        for p in m["players"]
    ) or "Bla stats joueurs."

    emoji = "🟢" if m["result"] == "W" else ("🟡" if m["result"] == "D" else "🔴")
    prompt = f"""
Match report:
{emoji} **{m['our_name']}** {m['our_goals']} — {m['opp_goals']} **{m['opp_name']}**
Date: {m['date']}

Stats joueurs:
{p_lines}

Kteb b Darija:
1. Opening wa7d jomla choquante selon résultat (fouz = hype, khsara = drama, taw = "safi 3iyet")
2. Résumé match 2-3 jomla style commentateur maghribi
3. MOTM — chmen ra7el dar shi 7aja
4. Ila rating < 6.5 → critique funny/toxic dial worst player ("fin kan had r7al?")
5. Closing: épique ila fouz, dramatique ila khsara
Bold Discord, max 900 chars, Darija street 100%.
"""
    result = await _ask(prompt, max_tokens=700)
    if not result:
        lines = [f"{emoji} **{m['our_name']}** {m['our_goals']}—{m['opp_goals']} **{m['opp_name']}**\n"]
        for p in m["players"][:5]:
            lines.append(f"**{p['name']}** — {p['rating']:.1f}/10 ({p['goals']}G {p['assists']}A)")
        return "\n".join(lines)
    return result


# ─── Quick Report (short, no image) ───────────────────────────────────────────

async def quick_report(m: dict) -> str:
    emoji = "🟢" if m["result"] == "W" else ("🟡" if m["result"] == "D" else "🔴")
    best = m["players"][0] if m["players"] else None
    motm_info = f"MOTM: {best['name']} ({best['rating']:.1f}/10)" if best else ""
    prompt = f"""
Quick report, 2 jomla MAX b Darija street:
{emoji} {m['our_name']} {m['our_goals']}-{m['opp_goals']} {m['opp_name']} ({m['result']})
{motm_info}
Punchline directe, max 180 chars — kifach kaykteb Moroccan f Twitter lkora.
"""
    result = await _ask(prompt, max_tokens=150)
    fallback = f"{emoji} **{m['our_goals']}-{m['opp_goals']}** vs {m['opp_name']} — {motm_info}"
    return result or fallback


# ─── MOTM ─────────────────────────────────────────────────────────────────────

async def motm_post(m: dict) -> str | None:
    if not m["players"]:
        return None
    best = m["players"][0]
    prompt = f"""
Post MOTM b Darija (max 220 chars, style tweet maghribi):
**{best['name']}** | {best['rating']:.1f}/10 | {best['goals']}G {best['assists']}A
Match: {m['our_goals']}-{m['opp_goals']} vs {m['opp_name']}
Commence par 🌟 MOTM: — hype natural, machi robot.
"""
    result = await _ask(prompt, max_tokens=180)
    return result or f"🌟 **MOTM: {best['name']}** — {best['rating']:.1f}/10 ({best['goals']}G {best['assists']}A) 🔥"


# ─── Funny Reactions (3 tweets) ───────────────────────────────────────────────

async def funny_reactions(m: dict) -> list[str]:
    p_highlights = ", ".join(f"{p['name']} ({p['rating']:.1f})" for p in m["players"][:4])
    outcome = "WIN" if m["result"] == "W" else ("DRAW" if m["result"] == "D" else "LOSS")
    prompt = f"""
3 tweets b Darija Moroccan Twitter style 3la had match:
{m['our_name']} {m['our_goals']}-{m['opp_goals']} {m['opp_name']} ({outcome})
Joueurs: {p_highlights or 'bla stats'}

Format EXACT — ghir had 3 lignes:
TWEET1: [max 180 chars]
TWEET2: [max 180 chars]
TWEET3: [max 180 chars]

Chaque tweet b energy différente:
- TWEET1: fierté/hype ila fouz ou drama ila khsara
- TWEET2: provocation dial adversaire ou self-roast
- TWEET3: reaction funny/absurde ou "fin kan X?"
Darija street 100%, natural code-switch m3a français.
"""
    result = await _ask(prompt, max_tokens=350)
    tweets = []
    if result:
        for line in result.splitlines():
            for prefix in ["TWEET1:", "TWEET2:", "TWEET3:"]:
                if line.strip().startswith(prefix):
                    tweets.append(line.strip()[len(prefix):].strip())
    return tweets[:3]


# ─── Reaction Post (single) ───────────────────────────────────────────────────

async def reaction_post(m: dict) -> str:
    emoji = "🟢" if m["result"] == "W" else ("🟡" if m["result"] == "D" else "🔴")
    outcome = "WIN" if m["result"] == "W" else ("DRAW" if m["result"] == "D" else "LOSS")
    prompt = f"""
Réaction WhatsApp/Twitter b Darija pour: {emoji} {m['our_goals']}-{m['opp_goals']} vs {m['opp_name']} ({outcome})
Max 150 chars, punch direct — ila fouz: hype, ila khsara: "t7ashsham" energy, ila taw: "safi 3iyet".
"""
    result = await _ask(prompt, max_tokens=120)
    return result or f"{emoji} {m['our_goals']}-{m['opp_goals']} vs {m['opp_name']} 🔥"


# ─── 5-Match Summary ──────────────────────────────────────────────────────────

async def five_match_summary(matches: list[dict]) -> str:
    wins   = sum(1 for m in matches if m["result"] == "W")
    draws  = sum(1 for m in matches if m["result"] == "D")
    losses = sum(1 for m in matches if m["result"] == "L")
    gf     = sum(m["our_goals"] for m in matches)
    ga     = sum(m["opp_goals"] for m in matches)
    form   = " ".join(m["result"] for m in matches)

    results_block = "\n".join(
        f"- {m['date']}: {m['our_goals']}-{m['opp_goals']} vs {m['opp_name']} ({m['result']})"
        for m in matches
    )
    prompt = f"""
Summary 5 derniers matchs b Darija Moroccan:

{results_block}
W{wins} D{draws} L{losses} | {gf} buts pour / {ga} contre | Forme: {form}

Inclure b Darija:
1. Titre accrocheur 3la had l-période (fouz = hype, khsara = "safi 3iyet")
2. Résultats format Discord (emojis 🟢🟡🔴) — courts
3. Verdict honnête "wakha golha": kaynin mzyan wla katdiwzo?
4. Best match + worst match m3a commentaire
5. Closing motivant ou critique 3la 7sab les résultats
Max 800 chars.
"""
    result = await _ask(prompt, max_tokens=650)
    if result:
        return result
    lines = ["📊 **Derniers 5 matchs — Rachad L3ERGONI**", "",
             f"🏆 W: **{wins}** | 🟡 D: **{draws}** | 💀 L: **{losses}**",
             f"⚽ Buts: **{gf}** / **{ga}** | Form: **{form}**"]
    for m in matches:
        e = "🟢" if m["result"] == "W" else ("🟡" if m["result"] == "D" else "🔴")
        lines.append(f"{e} {m['our_goals']}-{m['opp_goals']} vs **{m['opp_name']}**")
    return "\n".join(lines)


# ─── Top Performers ───────────────────────────────────────────────────────────

async def top_performers(matches: list[dict], members: list = None) -> str:
    from ea_api import aggregate_stats
    agg = aggregate_stats(matches)
    if not agg:
        return "❌ Ma3endnach stats daba 😴"

    top_scorers = sorted(agg.values(), key=lambda x: x["goals"],      reverse=True)[:3]
    top_assists = sorted(agg.values(), key=lambda x: x["assists"],    reverse=True)[:3]
    top_rated   = sorted(agg.values(), key=lambda x: x["avg_rating"], reverse=True)[:3]

    scorer_lines = "\n".join(f"- {p['name']}: {p['goals']} goals" for p in top_scorers if p["goals"] > 0) or "Klach kolhom 💀"
    assist_lines = "\n".join(f"- {p['name']}: {p['assists']} assists" for p in top_assists if p["assists"] > 0) or "Ma3wenoch walo 🤦"
    rating_lines = "\n".join(f"- {p['name']}: {p['avg_rating']:.2f}/10" for p in top_rated)

    prompt = f"""
Rankings b Darija Moroccan (5 derniers matchs):

🥇 Scorers:
{scorer_lines}

🎯 Assisters:
{assist_lines}

⭐ Best Rated:
{rating_lines}

Post SM b Darija — medals 🥇🥈🥉, Discord bold, commentaire funny/toxic pour chaque joueur.
Ila shi wa7d ma dar walo → "fin kan had r7al?" energy.
Max 650 chars.
"""
    result = await _ask(prompt, max_tokens=550)
    return result or f"🏅 **Top Performers**\n{scorer_lines}"


# ─── Team of the Week ─────────────────────────────────────────────────────────

async def team_of_the_week(matches: list[dict]) -> tuple[str, list[tuple[str, float]]]:
    from ea_api import aggregate_stats
    agg = aggregate_stats(matches)
    top11 = sorted(agg.values(), key=lambda x: x["avg_rating"], reverse=True)[:11]
    player_tuples = [(p["name"], round(p["avg_rating"], 2)) for p in top11]

    player_lines = "\n".join(
        f"- {p['name']}: {p['avg_rating']:.2f}/10 | {p['goals']}G {p['assists']}A"
        for p in top11
    )
    prompt = f"""
Team of the Week b Darija Moroccan:

Top joueurs:
{player_lines}

Kteb:
1. Titre TOTW épique b Darija
2. 11 joueurs m3a positions (GK/DEF/MID/ATT) — bold Discord
3. Commentaire 3la top 3 (mzyanin walo? golha!)
4. Closing hype kat-hype l'équipe
Discord bold, max 750 chars.
"""
    result = await _ask(prompt, max_tokens=650)
    text = result or "🏆 **TEAM OF THE WEEK**\n" + "\n".join(f"⭐ **{n}** — {r:.2f}/10" for n, r in player_tuples)
    return text, player_tuples


# ─── Roast ────────────────────────────────────────────────────────────────────

async def roast(player_name: str, matches: list[dict], members: list = None) -> str:
    from ea_api import aggregate_stats
    agg = aggregate_stats(matches)
    player_key = next((k for k in agg if k.lower() == player_name.lower()), None)

    if player_key:
        s = agg[player_key]
        stats_block = (
            f"Games: {s['games']}, Goals: {s['goals']}, Assists: {s['assists']}, "
            f"Rating: {s['avg_rating']:.2f}/10, Shots: {s['shots']}"
        )
    else:
        stats_block = f"'{player_name}' — machi f l'équipe daba ou gha ma3rftoch 👀"

    prompt = f"""
Roast BRUTAL walakin funny b Darija Moroccan Twitter style:
Joueur: {player_name}
Stats: {stats_block}

Rules:
- Darija street 100% — kifach kat-roast s7abek f WhatsApp
- Utilise les vraies stats: ila nul → "fin kan had r7al?", ila bon → cherche chi 7aja bach t9arred
- Punchline directe b7al: "kaydribble o kaydribble walakin l-goal = mission impossible, walo men wlo 😂"
- Ila rating < 6 → "sir t3llm lkora qbel matji" energy
- Fini b réconciliation comique wa7d jomla (b7al "walakin 7na kanhibok s7abi 😂")
- Max 280 chars, punch immédiat
"""
    result = await _ask(prompt, max_tokens=250)
    return f"🔥 **ROAST: {player_name}**\n\n{result or f'{player_name} khaf mn lroast hahaha 😅'}"


# ─── Cheer ────────────────────────────────────────────────────────────────────

async def cheer(player_name: str, matches: list[dict]) -> str:
    from ea_api import aggregate_stats
    agg = aggregate_stats(matches)
    player_key = next((k for k in agg if k.lower() == player_name.lower()), None)

    if player_key:
        s = agg[player_key]
        stats_block = f"{s['goals']}G {s['assists']}A {s['avg_rating']:.2f}/10 f {s['games']} matchs"
    else:
        stats_block = "joueur dial l'équipe 💪"

    prompt = f"""
Post d'appréciation b Darija Moroccan pour {player_name}:
Stats: {stats_block}
Style: fan hyped, éloge exagéré b7al kayt7adath m3a s7abo, funny walakin sincère. Max 200 chars.
"""
    result = await _ask(prompt, max_tokens=180)
    return f"👏 **{player_name}**\n\n{result or f'Rah {player_name} kaydiri 7wayed! 💪🔥'}"


# ─── Banter ───────────────────────────────────────────────────────────────────

async def banter(matches: list[dict] = None) -> str:
    context = ""
    if matches:
        last = matches[0]
        context = f"Dernier match: {last['our_goals']}-{last['opp_goals']} vs {last['opp_name']} ({last['result']})"

    prompt = f"""
Post banter b Darija Moroccan Twitter football:
{context}
Style: trash talk dial adversaires, provocation, slightly toxic — kima Moroccan Football Twitter.
"Ma3ndhomch shi y3mlo kontra 7na" energy. Max 220 chars.
"""
    result = await _ask(prompt, max_tokens=200)
    return result or "😈 Rachad L3ERGONI — kol chi ghadi ye3raf men hna! 🔥"


# ─── Meme Post ────────────────────────────────────────────────────────────────

async def meme_post(matches: list[dict] = None) -> str:
    last_result = ""
    if matches:
        m = matches[0]
        last_result = f"Dernier: {m['our_goals']}-{m['opp_goals']} vs {m['opp_name']} ({m['result']})"

    prompt = f"""
Meme football post b Darija Moroccan pour Rachad L3ERGONI.
{last_result}
Style: format meme maghribi (b7al "Rachad L3ERGONI f l-attack: ✅ f ldefense: ✅ f..." ou "had l-équipe waqila..." ou "ana o s7abi wqt..."),
situational humor dial football. Max 200 chars.
"""
    result = await _ask(prompt, max_tokens=180)
    return f"😂 {result or 'Rachad L3ERGONI quand yji lmatch final: 💪🔥'}"


# ─── Drama Post ───────────────────────────────────────────────────────────────

async def drama_post(matches: list[dict] = None) -> str:
    if matches:
        m = matches[0]
        context = f"{m['our_goals']}-{m['opp_goals']} vs {m['opp_name']} ({m['result']})"
    else:
        context = "saison en cours"

    prompt = f"""
Post drama/polémique funny b Darija Moroccan sur: {context}
Style: exagéré, théâtral, kima kayt7adath Moroccan Twitter 3la chi scandal kbir —
"ma9dl t9addar walo", "kif kif f kol match", "والله ما صدقت" energy. Max 220 chars.
"""
    result = await _ask(prompt, max_tokens=190)
    return f"😱 {result or 'DRAMA f Rachad L3ERGONI! Chi 7aja waqe3at! 😱'}"


# ─── Hype Post ────────────────────────────────────────────────────────────────

async def hype_post(context: str = "") -> str:
    prompt = f"""
Hype post motivant b Darija Moroccan pour Rachad L3ERGONI.
{f'Context: {context}' if context else 'Pre-match motivation.'}
Style: war cry, ultra confiant, rally l'équipe — "7na 7na walo ghayrina" energy.
Max 220 chars, punch direct.
"""
    result = await _ask(prompt, max_tokens=200)
    return result or "🔥 RACHAD L3ERGONI — MA3NDHOMCH SHI Y3MLO KONTRA! LET'S GO! 💪⚽"


# ─── Match Prediction ─────────────────────────────────────────────────────────

async def match_prediction(opponent: str, recent_matches: list[dict]) -> str:
    wins = sum(1 for m in recent_matches if m["result"] == "W")
    losses = sum(1 for m in recent_matches if m["result"] == "L")
    gf = sum(m["our_goals"] for m in recent_matches)
    form = "".join(m["result"] for m in recent_matches[:5])

    prompt = f"""
Prediction b Darija Moroccan: Rachad L3ERGONI vs {opponent}
Forme: {form} | W{wins} L{losses} | {gf} buts marqués

Inclure:
1. Score prédit (ex: 3-1) m3a confiance
2. Analyse tactique funny b Darija (1-2 jomla)
3. Joueur clé dial match
4. Verdict confiant — "ghadi n9lb fihom" ou "mochkil 3lihom"
Max 280 chars.
"""
    result = await _ask(prompt, max_tokens=250)
    return f"🎯 **PREDICTION: vs {opponent}**\n\n{result or 'Gemini khaf ye-predict 😅'}"


# ─── Transfer / Breaking News ──────────────────────────────────────────────────

async def transfer_rumor(members: list = None, matches: list[dict] = None) -> str:
    from ea_api import aggregate_stats
    players = []
    if matches:
        agg = aggregate_stats(matches)
        players = [p["name"] for p in sorted(agg.values(), key=lambda x: x["avg_rating"], reverse=True)[:5]]
    elif members:
        players = [m.get("proName") or m.get("name", "?") for m in members[:5]]
    players_str = ", ".join(players) if players else "nos stars"

    prompt = f"""
Transfer rumor FAKE (entertainment) b Darija Moroccan:
Joueurs: {players_str}
Style: 🚨 EXCLU, journaliste dramatique maghribi, complètement inventé walakin crédible.
"Sma3t mn masdar mowataq" energy. Max 220 chars.
"""
    result = await _ask(prompt, max_tokens=200)
    return f"🚨 **TRANSFER NEWS**\n\n{result or '🚨 EXCLU: Rachad L3ERGONI f discussions ma3 club kayn! 👀'}"


async def breaking_news(matches: list[dict] = None, members: list = None) -> str:
    context = ""
    if matches:
        m = matches[0]
        context = f"Dernier résultat: {m['our_goals']}-{m['opp_goals']} vs {m['opp_name']}"

    prompt = f"""
Post "Breaking News" style b Darija Moroccan sur Rachad L3ERGONI:
{context}
Style: journaliste dramatique maghribi, BREAKING urgent, "wakha golha" energy.
Peut être résultat, performance, ou rumeur inventée funny. Max 220 chars.
"""
    result = await _ask(prompt, max_tokens=200)
    return f"📰 **BREAKING**\n\n{result or '📰 BREAKING: Rachad L3ERGONI kadir 7wayed f l-saison! 🔥'}"


# ─── Form Analysis ────────────────────────────────────────────────────────────

async def form_analysis(matches: list[dict]) -> str:
    wins   = sum(1 for m in matches if m["result"] == "W")
    draws  = sum(1 for m in matches if m["result"] == "D")
    losses = sum(1 for m in matches if m["result"] == "L")
    gf     = sum(m["our_goals"] for m in matches)
    ga     = sum(m["opp_goals"] for m in matches)
    form   = "".join(m["result"] for m in matches)

    results_block = "\n".join(
        f"- {m['date']}: {m['our_goals']}-{m['opp_goals']} vs {m['opp_name']} ({m['result']})"
        for m in matches
    )
    prompt = f"""
Analyse de forme b Darija Moroccan ({len(matches)} matchs):

{results_block}
W{wins} D{draws} L{losses} | +{gf} -{ga} | Form: {form}

1. État de forme: "kaynin f niveau" / "noss noss" / "safi 3iyet" selon results
2. Offensive + défensive b Darija honest
3. Tendance dial match prochain
4. Conseil tactique funny ou critique
Max 450 chars.
"""
    result = await _ask(prompt, max_tokens=380)
    return f"📈 **ANALYSE DE FORME**\n\n{result or f'W{wins} D{draws} L{losses} — Form: {form}'}"


# ─── Player Form ──────────────────────────────────────────────────────────────

async def player_form(player_name: str, matches: list[dict]) -> str:
    from ea_api import aggregate_stats
    agg = aggregate_stats(matches)
    player_key = next((k for k in agg if k.lower() == player_name.lower()), None)

    if not player_key:
        return f"❌ **{player_name}** — ma3endnach stats f les derniers matchs 😴"

    s = agg[player_key]
    ratings_str = " → ".join(f"{r:.1f}" for r in s.get("ratings", []))

    prompt = f"""
Analyse de forme individuelle b Darija Moroccan pour {player_name}:
{s['games']} matchs | {s['goals']}G {s['assists']}A | Rating: {s['avg_rating']:.2f}/10
Ratings: {ratings_str or 'N/A'}

1. Verdict: "f7al" / "3adl" / "khas y7ssen" m3a commentaire honest
2. Point fort + point faible b Darija
3. Reaction funny dial s7abo f WhatsApp
Max 300 chars.
"""
    result = await _ask(prompt, max_tokens=260)
    fallback = f"{s['goals']}G {s['assists']}A {s['avg_rating']:.2f}/10 avg"
    return f"📊 **FORM: {player_name}**\n\n{result or fallback}"


# ─── Insights ─────────────────────────────────────────────────────────────────

async def insights(matches: list[dict]) -> str:
    wins   = sum(1 for m in matches if m["result"] == "W")
    losses = sum(1 for m in matches if m["result"] == "L")
    gf     = sum(m["our_goals"] for m in matches)
    ga     = sum(m["opp_goals"] for m in matches)
    biggest_win  = max(matches, key=lambda m: m["our_goals"] - m["opp_goals"], default=None)
    biggest_loss = min(matches, key=lambda m: m["our_goals"] - m["opp_goals"], default=None)

    prompt = f"""
Insights b Darija Moroccan (derniers {len(matches)} matchs):
W{wins} L{losses} | {gf} buts pour / {ga} contre
Biggest win: {biggest_win['our_goals'] if biggest_win else '?'}-{biggest_win['opp_goals'] if biggest_win else '?'} vs {biggest_win['opp_name'] if biggest_win else '?'}
Biggest loss: {biggest_loss['our_goals'] if biggest_loss else '?'}-{biggest_loss['opp_goals'] if biggest_loss else '?'} vs {biggest_loss['opp_name'] if biggest_loss else '?'}

3-4 insights intéressants 3la patterns dial jeu, style data analyst + Darija funny.
"Wakha golha" energy — honest walakin ma t9arrechch bzzaf.
Max 450 chars.
"""
    result = await _ask(prompt, max_tokens=380)
    return f"🔍 **INSIGHTS**\n\n{result or f'W{wins} L{losses} | {gf} pour / {ga} contre'}"


# ─── Trends ───────────────────────────────────────────────────────────────────

async def trends(matches: list[dict]) -> str:
    from ea_api import aggregate_stats
    agg = aggregate_stats(matches)

    gf_per_match = [m["our_goals"] for m in matches]
    ga_per_match = [m["opp_goals"] for m in matches]
    results_str  = "".join(m["result"] for m in matches)
    top_scorer   = max(agg.values(), key=lambda x: x["goals"], default=None) if agg else None

    prompt = f"""
Trends b Darija Moroccan pour Rachad L3ERGONI:
Résultats: {results_str}
Buts marqués: {gf_per_match}
Buts concédés: {ga_per_match}
Top scorer: {top_scorer['name'] if top_scorer else '?'} ({top_scorer['goals'] if top_scorer else 0} goals)

Trends (scoring, conceding, momentum) — style analyst b Darija, honest walakin machi khutba.
Max 400 chars.
"""
    result = await _ask(prompt, max_tokens=350)
    return f"📉📈 **TRENDS**\n\n{result or f'Résultats: {results_str}'}"


# ─── Stat of the Day ──────────────────────────────────────────────────────────

async def stat_of_day(matches: list[dict]) -> str:
    from ea_api import aggregate_stats
    agg = aggregate_stats(matches)
    if not agg:
        return ""

    top_scorer = max(agg.values(), key=lambda x: x["goals"], default=None)
    top_rated  = max(agg.values(), key=lambda x: x["avg_rating"], default=None)
    total_goals = sum(m["our_goals"] for m in matches)
    wins = sum(1 for m in matches if m["result"] == "W")

    prompt = f"""
"Stat du Jour" b Darija Moroccan:
Top scorer: {top_scorer['name'] if top_scorer else '?'} ({top_scorer['goals'] if top_scorer else 0} goals)
Best rated: {top_rated['name'] if top_rated else '?'} ({top_rated['avg_rating']:.2f}/10 avg)
Total buts: {total_goals} f {len(matches)} matchs | Wins: {wins}

Choisit la stat la plus impressionnante, présente-la style infographie SM b Darija. Max 180 chars.
"""
    result = await _ask(prompt, max_tokens=160)
    return f"📊 **STAT DU JOUR**\n\n{result or f'⚽ {total_goals} buts f {len(matches)} matchs — {wins} victoires'}"


# ─── Player Spotlight ─────────────────────────────────────────────────────────

async def player_spotlight(player_name: str, matches: list[dict]) -> str:
    from ea_api import aggregate_stats
    agg = aggregate_stats(matches)
    player_key = next((k for k in agg if k.lower() == player_name.lower()), None)

    if not player_key and agg:
        player_key = max(agg, key=lambda k: agg[k]["avg_rating"])
    if not player_key:
        return ""

    s = agg[player_key]
    prompt = f"""
Player spotlight b Darija Moroccan: **{s['name']}**
{s['games']} matchs | {s['goals']}G {s['assists']}A | {s['avg_rating']:.2f}/10 avg

Profil joueur SM: compliments sincères + petites piques funny b Darija. Max 250 chars.
"""
    result = await _ask(prompt, max_tokens=220)
    fallback = f"{s['goals']}G {s['assists']}A {s['avg_rating']:.2f}/10 avg"
    return f"🔦 **PLAYER SPOTLIGHT: {s['name']}**\n\n{result or fallback}"


# ─── Top Scorer Post ──────────────────────────────────────────────────────────

async def top_scorer_post(matches: list[dict], members: list = None) -> str:
    from ea_api import aggregate_stats, aggregate_from_members
    agg = aggregate_stats(matches)

    if not agg and members:
        agg = aggregate_from_members(members)

    if not agg:
        return "❌ Ma3endnach stats 😴"

    scorers = sorted(agg.values(), key=lambda x: x["goals"], reverse=True)[:5]
    scorer_lines = "\n".join(
        f"{'🥇' if i==0 else '🥈' if i==1 else '🥉' if i==2 else f'{i+1}.'} "
        f"**{p['name']}** — {p['goals']} buts ({p['games']} matchs)"
        for i, p in enumerate(scorers)
    )

    prompt = f"""
Top scorers post b Darija Moroccan:
{scorer_lines}

Post classement SM b Darija, commentaire funny pour le #1, shout-out ou pique pour les autres. Max 400 chars.
"""
    result = await _ask(prompt, max_tokens=350)
    return f"⚽ **TOP SCORERS**\n\n{result or scorer_lines}"


# ─── Top Assists Post ─────────────────────────────────────────────────────────

async def top_assists_post(matches: list[dict], members: list = None) -> str:
    from ea_api import aggregate_stats, aggregate_from_members
    agg = aggregate_stats(matches)

    if not agg and members:
        agg = aggregate_from_members(members)

    if not agg:
        return "❌ Ma3endnach stats 😴"

    assisters = sorted(agg.values(), key=lambda x: x["assists"], reverse=True)[:5]
    assist_lines = "\n".join(
        f"{'🥇' if i==0 else '🥈' if i==1 else '🥉' if i==2 else f'{i+1}.'} "
        f"**{p['name']}** — {p['assists']} assists ({p['games']} matchs)"
        for i, p in enumerate(assisters)
    )

    prompt = f"""
Top assisteurs post b Darija Moroccan:
{assist_lines}

Post classement SM b Darija, commentaire 3la l-passeur dial l'équipe. Max 350 chars.
"""
    result = await _ask(prompt, max_tokens=300)
    return f"🎯 **TOP ASSISTS**\n\n{result or assist_lines}"


# ─── MVP Post ─────────────────────────────────────────────────────────────────

async def mvp_post(matches: list[dict]) -> str:
    from ea_api import aggregate_stats
    agg = aggregate_stats(matches)
    if not agg:
        return "❌ Ma3endnach stats 😴"

    mvp = max(agg.values(), key=lambda x: x["avg_rating"] + x["goals"] * 0.5 + x["assists"] * 0.3)
    prompt = f"""
MVP post b Darija Moroccan pour: **{mvp['name']}**
{mvp['goals']}G {mvp['assists']}A | {mvp['avg_rating']:.2f}/10 avg | {mvp['games']} matchs

Style: couronnement hype maximal, "had r7al kaykhdem bzzaf" energy. Max 250 chars.
"""
    result = await _ask(prompt, max_tokens=220)
    fallback = f"{mvp['goals']}G {mvp['assists']}A — {mvp['avg_rating']:.2f}/10 💪"
    return f"👑 **MVP: {mvp['name']}**\n\n{result or fallback}"


# ─── Compare Players ──────────────────────────────────────────────────────────

async def compare_players(p1_name: str, p2_name: str, matches: list[dict]):
    from ea_api import aggregate_stats
    agg = aggregate_stats(matches)

    def _find(name):
        return next((agg[k] for k in agg if k.lower() == name.lower()), None)

    s1, s2 = _find(p1_name), _find(p2_name)

    if not s1 and not s2:
        return f"❌ Ma3endnach stats dial **{p1_name}** ou **{p2_name}**."
    if not s1:
        return f"❌ Ma3endnach stats dial **{p1_name}**."
    if not s2:
        return f"❌ Ma3endnach stats dial **{p2_name}**."

    prompt = f"""
Head-to-head b Darija Moroccan Twitter:
**{s1['name']}**: {s1['goals']}G {s1['assists']}A | {s1['avg_rating']:.2f}/10 | {s1['games']} matchs
**{s2['name']}**: {s2['goals']}G {s2['assists']}A | {s2['avg_rating']:.2f}/10 | {s2['games']} matchs

1. Titre battle épique b Darija
2. Stats side-by-side (tableau Discord ✅❌)
3. Verdict final funny/toxic — golha b confiance, machi "les deux sont bons"
Max 400 chars.
"""
    result = await _ask(prompt, max_tokens=380)
    if not result:
        winner = s1["name"] if s1["avg_rating"] >= s2["avg_rating"] else s2["name"]
        result = (f"**{s1['name']}** vs **{s2['name']}**\n"
                  f"Goals: {s1['goals']} vs {s2['goals']}\n"
                  f"Assists: {s1['assists']} vs {s2['assists']}\n"
                  f"Rating: {s1['avg_rating']:.2f} vs {s2['avg_rating']:.2f}\n"
                  f"🏆 **{winner}** wins!")
    return result, s1, s2
