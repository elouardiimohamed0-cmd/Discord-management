"""
Gemini AI content generator — Moroccan Darija football social media manager.
Uses Groq API (Llama 3.1) with DODa-standard Darija prompts.

DODa (Darija Open Dataset) transliteration standard:
  3 = ع (ayn)    7 = ح (ha)     9 = ق (qaf)
  8 = ه (ha)     5 = خ (kha)    ch = ش (shin)
  gh = غ (ghayn)  kh = خ (kha)

Key fix: System prompt now includes DODa-standard examples.
No post-processing needed — AI generates clean Darija directly.
"""
import asyncio
import logging
import os
from openai import OpenAI

from darija import ask_and_clean

logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)


async def _ask(prompt: str, max_tokens: int = 300):
    try:
        loop = asyncio.get_event_loop()

        def call_api():
            return client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": DODA_PERSONA},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.85,
                max_tokens=max_tokens,
            )

        response = await loop.run_in_executor(None, call_api)
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"GROQ error: {e}")
        return None


# ── DODa-STANDARD SYSTEM PROMPT — Moroccan Darija Persona ─────────────────────

DODA_PERSONA = """
You are a Moroccan football social media manager for "Rachad L3ERGONI" Pro Clubs FC 26 team.
You write EXCLUSIVELY in Moroccan Darija using DODa (Darija Open Dataset) transliteration standard.

══ DODA TRANSLITERATION RULES ══
Use these standard mappings:
  3 = ع (ayn)     7 = ح (ha)      9 = ق (qaf)
  8 = ه (ha)      5 = خ (kha)     ch = ش (shin)
  gh = غ (ghayn)  kh = خ (kha)    ou = و (waw)

══ HOW TO WRITE DARIJA ══
- Write like a Moroccan talks on WhatsApp/Twitter about football
- Mix Darija + French naturally: "lmatch", "l'équipe", "niveau", "performance", "résultat"
- Use Moroccan slang: "z3ma", "dima dima", "noss noss", "fhamti walo", "ta9awwam ya kho"
- Short punchy sentences — NOT essays
- Natural fillers: "ya3ni", "walo", "daba", "safi", "z3ma", "b7al"
- Self-roast / irony: "7na l'équipe dial champions 😂 z3ma"
- Emotional reactions mid-sentence: "walakin... lol", "ya3ni??"
- Use Arabic script naturally: "والله", "ماشي", "راه", "واش ممكن"
- Emojis max 3-4 per post: 💀😂🔥😭👏
- Discord bold: **name** for important stats

══ DODa-STANDARD EXAMPLES (copy this style exactly) ══

Win: "🔥 Rbe7na ya s7abi! L'équipe darat match mzyan bzf, l3adou ma 9derch y3ml walo! **Rachad** 9awi bzf!"
Loss: "💀 Khsarna ya s7abi... Safi 3iyet mn had l7al. Defense kaytferrej gha, walo men walo! 3ib w 7chouma!"
Draw: "🟡 T3adl... Safi 3iyet, match khayb bzf! Midfield gha pass pass bla result. Walo men walo!"
Roast: "🔥 Fin kan **Hamza**? Kaydour f terrain b7al tourist! Goal = mission impossible walo men walo! 💀"
Praise: "🔥 **Karim** dar match mzyan! Player kaykhdem, mashi b7al l3ab! Rating zwin bzf! 👏"
Hype: "🔥 **RACHAD L3ERGONI!** Ghadi nrbe7houm walo men walo! 7na 7na walo ghayrina! 💪"

══ IMPORTANT RULES ══
- NO intro like "Voici" or "Je vais" — start directly with content
- NO formal Arabic words like "لقد", "إنه", "جميل", "أداء" — use Darija: "kan", "rbe7", "zwin", "mzyan"
- Max 800 chars for long posts, 200 for short tweets
- Be confident — you're the team SM manager, not an assistant
- Use DODa standard: 3 for ع, 7 for ح, 9 for ق, ch for ش, gh for غ
"""


# ─── Match Report ─────────────────────────────────────────────────────────────

async def match_report(m: dict) -> str:
    p_lines = "\n".join(
        f"- {p['name']}: {p['rating']:.1f}/10, {p['goals']}G {p['assists']}A"
        for p in m["players"]
    ) or "Bla stats joueurs."

    emoji = "🟢" if m["result"] == "W" else ("🟡" if m["result"] == "D" else "🔴")
    situation = "win" if m["result"] == "W" else "lose" if m["result"] == "L" else "draw"

    prompt = f"""
Match: {emoji} **{m['our_name']}** {m['our_goals']} — {m['opp_goals']} **{m['opp_name']}**
Joueurs:
{p_lines}

Write a match report in Moroccan Darija (DODa standard):
1. One shocking opening line based on result (win=hype, loss=drama, draw="safi 3iyet")
2. 2-3 sentences match summary in Moroccan commentator style
3. MOTM praise — who was amazing
4. If someone rated < 6.5, funny criticism: "fin kan had r7al?"
5. Closing: epic if win, dramatic if loss
Max 800 chars. Bold Discord. Darija street style. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=700, situation=situation)
    if not result:
        lines = [f"{emoji} **{m['our_name']}** {m['our_goals']}—{m['opp_goals']} **{m['opp_name']}**\n"]
        for p in m["players"][:5]:
            lines.append(f"**{p['name']}** — {p['rating']:.1f}/10 ({p['goals']}G {p['assists']}A)")
        return "\n".join(lines)
    return result


# ─── Quick Report ───────────────────────────────────────────────────────────

async def quick_report(m: dict) -> str:
    emoji = "🟢" if m["result"] == "W" else ("🟡" if m["result"] == "D" else "🔴")
    best = m["players"][0] if m["players"] else None
    motm_info = f"MOTM: {best['name']} ({best['rating']:.1f}/10)" if best else ""

    prompt = f"""
Quick match reaction in Moroccan Darija DODa standard (2 sentences MAX):
{emoji} {m['our_name']} {m['our_goals']}-{m['opp_goals']} {m['opp_name']} ({m['result']})
{motm_info}
Punchline direct — how a Moroccan tweets football. Max 180 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=150, situation="general")
    fallback = f"{emoji} **{m['our_goals']}-{m['opp_goals']}** vs {m['opp_name']} — {motm_info}"
    return result or fallback


# ─── MOTM ─────────────────────────────────────────────────────────────────────

async def motm_post(m: dict) -> str | None:
    if not m["players"]:
        return None
    best = m["players"][0]

    prompt = f"""
MOTM post in Moroccan Darija DODa standard (max 200 chars, tweet style):
**{best['name']}** | {best['rating']:.1f}/10 | {best['goals']}G {best['assists']}A
Match: {m['our_goals']}-{m['opp_goals']} vs {m['opp_name']}
Start with 🌟 MOTM: — natural hype, not robotic. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=180, situation="praise")
    return result or f"🌟 **MOTM: {best['name']}** — {best['rating']:.1f}/10 ({best['goals']}G {best['assists']}A) 🔥"


# ─── Funny Reactions (3 tweets) ───────────────────────────────────────────────

async def funny_reactions(m: dict) -> list[str]:
    p_highlights = ", ".join(f"{p['name']} ({p['rating']:.1f})" for p in m["players"][:4])
    outcome = "WIN" if m["result"] == "W" else ("DRAW" if m["result"] == "D" else "LOSS")

    prompt = f"""
3 tweets in Moroccan Darija DODa standard about this match:
{m['our_name']} {m['our_goals']}-{m['opp_goals']} {m['opp_name']} ({outcome})
Joueurs: {p_highlights or 'bla stats'}

Format EXACT — just these 3 lines:
TWEET1: [max 180 chars]
TWEET2: [max 180 chars]
TWEET3: [max 180 chars]

Energy:
- TWEET1: pride/hype if win, drama if loss
- TWEET2: trash talk opponent or self-roast
- TWEET3: funny/absurd reaction or "fin kan X?"
Darija street, natural French mix. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=350, situation="general")
    tweets = []
    if result:
        for line in result.splitlines():
            for prefix in ["TWEET1:", "TWEET2:", "TWEET3:"]:
                if line.strip().startswith(prefix):
                    tweets.append(line.strip()[len(prefix):].strip())
    return tweets[:3]


# ─── Reaction Post ───────────────────────────────────────────────────────────

async def reaction_post(m: dict) -> str:
    emoji = "🟢" if m["result"] == "W" else ("🟡" if m["result"] == "D" else "🔴")
    outcome = "WIN" if m["result"] == "W" else ("DRAW" if m["result"] == "D" else "LOSS")

    prompt = f"""
WhatsApp/Twitter reaction in Moroccan Darija DODa standard:
{emoji} {m['our_goals']}-{m['opp_goals']} vs {m['opp_name']} ({outcome})
Max 150 chars, punch direct — win=hype, loss="t7ashsham", draw="safi 3iyet". Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=120, situation="general")
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
5-match summary in Moroccan Darija DODa standard:

{results_block}
W{wins} D{draws} L{losses} | {gf} buts pour / {ga} contre | Forme: {form}

Include:
1. Catchy title about this period (win=hype, loss="safi 3iyet")
2. Results in Discord format (emojis 🟢🟡🔴) — short
3. Honest verdict "wakha golha": good or bad?
4. Best match + worst match with comment
5. Closing motivating or critical based on results
Max 800 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=650, situation="general")
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
Rankings in Moroccan Darija DODa standard (last 5 matches):

🥇 Scorers:
{scorer_lines}

🎯 Assisters:
{assist_lines}

⭐ Best Rated:
{rating_lines}

SM post in Darija — medals 🥇🥈🥉, Discord bold, funny/toxic comment per player.
If someone did nothing → "fin kan had r7al?" energy.
Max 650 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=550, situation="praise")
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
Team of the Week in Moroccan Darija DODa standard:

Top players:
{player_lines}

Write:
1. Epic TOTW title in Darija
2. 11 players with positions (GK/DEF/MID/ATT) — bold Discord
3. Comment on top 3 (good or bad? say it!)
4. Closing hype for the team
Discord bold, max 750 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=650, situation="praise")
    text = result or "🏆 **TEAM OF THE WEEK**\n" + "\n".join(f"⭐ **{n}** — {r:.2f}/10" for n, r in player_tuples)
    return text, player_tuples


# ─── Roast ───────────────────────────────────────────────────────────────────

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
BRUTAL but funny roast in Moroccan Darija DODa standard Twitter style:
Player: {player_name}
Stats: {stats_block}

Rules:
- Darija street 100% — like roasting friends on WhatsApp
- Use real stats: if bad → "fin kan had r7al?", if good → find something to mock
- Punchline: "kaydribble o kaydribble walakin l-goal = mission impossible, walo men wlo 😂"
- If rating < 6 → "sir t3llm lkora qbel matji" energy
- End with one funny reconciliation line ("walakin 7na kanhibok s7abi 😂")
- Max 280 chars, immediate punch. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=250, situation="roast")
    return f"🔥 **ROAST: {player_name}**\n\n{result or f'{player_name} khaf mn lroast hahaha 😅'}"


# ─── Cheer ───────────────────────────────────────────────────────────────────

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
Appreciation post in Moroccan Darija DODa standard for {player_name}:
Stats: {stats_block}
Style: hyped fan, exaggerated praise like talking to friends, funny but sincere. Max 200 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=180, situation="praise")
    return f"👏 **{player_name}**\n\n{result or f'Rah {player_name} kaydiri 7wayed! 💪🔥'}"


# ─── Banter ───────────────────────────────────────────────────────────────────

async def banter(matches: list[dict] = None) -> str:
    context = ""
    if matches:
        last = matches[0]
        context = f"Last match: {last['our_goals']}-{last['opp_goals']} vs {last['opp_name']} ({last['result']})"

    prompt = f"""
Trash talk post in Moroccan Darija DODa standard football Twitter:
{context}
Style: provocation, slightly toxic — "Ma3ndhomch shi y3mlo kontra 7na" energy. Max 220 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=200, situation="general")
    return result or "😈 Rachad L3ERGONI — kol chi ghadi ye3raf men hna! 🔥"


# ─── Meme Post ────────────────────────────────────────────────────────────────

async def meme_post(matches: list[dict] = None) -> str:
    last_result = ""
    if matches:
        m = matches[0]
        last_result = f"Last: {m['our_goals']}-{m['opp_goals']} vs {m['opp_name']} ({m['result']})"

    prompt = f"""
Meme football post in Moroccan Darija DODa standard for Rachad L3ERGONI.
{last_result}
Style: Moroccan meme format ("Rachad L3ERGONI f attack: ✅ f defense: ✅ f..." or "had l-équipe waqila..." or "ana o s7abi wqt..."), situational football humor. Max 200 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=180, situation="general")
    return f"😂 {result or 'Rachad L3ERGONI quand yji lmatch final: 💪🔥'}"


# ─── Drama Post ───────────────────────────────────────────────────────────────

async def drama_post(matches: list[dict] = None) -> str:
    if matches:
        m = matches[0]
        context = f"{m['our_goals']}-{m['opp_goals']} vs {m['opp_name']} ({m['result']})"
    else:
        context = "saison en cours"

    prompt = f"""
Drama/controversy post in Moroccan Darija DODa standard about: {context}
Style: exaggerated, theatrical, like Moroccan Twitter on a big scandal — "ma9dl t9addar walo", "kif kik f kol match", "والله ما صدقت" energy. Max 220 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=190, situation="general")
    return f"😱 {result or 'DRAMA f Rachad L3ERGONI! Chi 7aja waqe3at! 😱'}"


# ─── Hype Post ───────────────────────────────────────────────────────────────

async def hype_post(context: str = "") -> str:
    prompt = f"""
Hype/motivation post in Moroccan Darija DODa standard for Rachad L3ERGONI.
{f'Context: {context}' if context else 'Pre-match motivation.'}
Style: war cry, ultra confident, rally the team — "7na 7na walo ghayrina" energy.
Max 220 chars, punch direct. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=200, situation="hype")
    return result or "🔥 RACHAD L3ERGONI — MA3NDHOMCH SHI Y3MLO KONTRA! LET'S GO! 💪⚽"


# ─── Match Prediction ─────────────────────────────────────────────────────────

async def match_prediction(opponent: str, recent_matches: list[dict]) -> str:
    wins = sum(1 for m in recent_matches if m["result"] == "W")
    losses = sum(1 for m in recent_matches if m["result"] == "L")
    gf = sum(m["our_goals"] for m in recent_matches)
    form = "".join(m["result"] for m in recent_matches[:5])

    prompt = f"""
Prediction in Moroccan Darija DODa standard: Rachad L3ERGONI vs {opponent}
Form: {form} | W{wins} L{losses} | {gf} buts scored

Include:
1. Predicted score (e.g. 3-1) with confidence
2. Funny tactical analysis in Darija (1-2 sentences)
3. Key player for the match
4. Confident verdict — "ghadi n9lb fihom" or "mochkil 3lihom"
Max 280 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=250, situation="general")
    return f"🎯 **PREDICTION: vs {opponent}**\n\n{result or 'Le7ya khaf ye-predict 😅'}"


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
FAKE transfer rumor (entertainment) in Moroccan Darija DODa standard:
Players: {players_str}
Style: 🚨 EXCLU, dramatic Moroccan journalist, completely invented but credible.
"Sma3t mn masdar mowataq" energy. Max 220 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=200, situation="general")
    return f"🚨 **TRANSFER NEWS**\n\n{result or '🚨 EXCLU: Rachad L3ERGONI f discussions ma3 club kayn! 👀'}"


async def breaking_news(matches: list[dict] = None, members: list = None) -> str:
    context = ""
    if matches:
        m = matches[0]
        context = f"Last result: {m['our_goals']}-{m['opp_goals']} vs {m['opp_name']}"

    prompt = f"""
"Breaking News" style in Moroccan Darija DODa standard about Rachad L3ERGONI:
{context}
Style: dramatic Moroccan journalist, BREAKING urgent, "wakha golha" energy.
Can be result, performance, or invented funny rumor. Max 220 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=200, situation="general")
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
Form analysis in Moroccan Darija DODa standard ({len(matches)} matches):

{results_block}
W{wins} D{draws} L{losses} | +{gf} -{ga} | Form: {form}

1. Form state: "kaynin f niveau" / "noss noss" / "safi 3iyet" based on results
2. Offense + defense in Darija, honest
3. Trend for next match
4. Funny tactical advice or criticism
Max 450 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=380, situation="general")
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
Individual form analysis in Moroccan Darija DODa standard for {player_name}:
{s['games']} matches | {s['goals']}G {s['assists']}A | Rating: {s['avg_rating']:.2f}/10
Ratings: {ratings_str or 'N/A'}

1. Verdict: "f7al" / "3adl" / "khas y7ssen" with honest comment
2. Strength + weakness in Darija
3. Funny WhatsApp reaction from friends
Max 300 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=260, situation="general")
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
Insights in Moroccan Darija DODa standard (last {len(matches)} matches):
W{wins} L{losses} | {gf} buts pour / {ga} contre
Biggest win: {biggest_win['our_goals'] if biggest_win else '?'}-{biggest_win['opp_goals'] if biggest_win else '?'} vs {biggest_win['opp_name'] if biggest_win else '?'}
Biggest loss: {biggest_loss['our_goals'] if biggest_loss else '?'}-{biggest_loss['opp_goals'] if biggest_loss else '?'} vs {biggest_loss['opp_name'] if biggest_loss else '?'}

3-4 interesting insights on game patterns, data analyst + funny Darija style.
"Wakha golha" energy — honest but not too harsh.
Max 450 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=380, situation="general")
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
Trends in Moroccan Darija DODa standard for Rachad L3ERGONI:
Results: {results_str}
Goals scored: {gf_per_match}
Goals conceded: {ga_per_match}
Top scorer: {top_scorer['name'] if top_scorer else '?'} ({top_scorer['goals'] if top_scorer else 0} goals)

Trends (scoring, conceding, momentum) — analyst style in Darija, honest but not a sermon.
Max 400 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=350, situation="general")
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
"Stat of the Day" in Moroccan Darija DODa standard:
Top scorer: {top_scorer['name'] if top_scorer else '?'} ({top_scorer['goals'] if top_scorer else 0} goals)
Best rated: {top_rated['name'] if top_rated else '?'} ({top_rated['avg_rating']:.2f}/10 avg)
Total goals: {total_goals} f {len(matches)} matches | Wins: {wins}

Pick the most impressive stat, present it SM infographic style in Darija. Max 180 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=160, situation="general")
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
Player spotlight in Moroccan Darija DODa standard: **{s['name']}**
{s['games']} matches | {s['goals']}G {s['assists']}A | {s['avg_rating']:.2f}/10 avg

SM player profile: sincere compliments + small funny jabs in Darija. Max 250 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=220, situation="praise")
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
Top scorers post in Moroccan Darija DODa standard:
{scorer_lines}

SM ranking post in Darija, funny comment for #1, shout-out or jab for others. Max 400 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=350, situation="praise")
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
Top assisters post in Moroccan Darija DODa standard:
{assist_lines}

SM ranking post in Darija, comment on the team's passer. Max 350 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=300, situation="general")
    return f"🎯 **TOP ASSISTS**\n\n{result or assist_lines}"


# ─── MVP Post ─────────────────────────────────────────────────────────────────

async def mvp_post(matches: list[dict]) -> str:
    from ea_api import aggregate_stats
    agg = aggregate_stats(matches)
    if not agg:
        return "❌ Ma3endnach stats 😴"

    mvp = max(agg.values(), key=lambda x: x["avg_rating"] + x["goals"] * 0.5 + x["assists"] * 0.3)
    prompt = f"""
MVP post in Moroccan Darija DODa standard for: **{mvp['name']}**
{mvp['goals']}G {mvp['assists']}A | {mvp['avg_rating']:.2f}/10 avg | {mvp['games']} matchs

Style: maximum hype coronation, "had r7al kaykhdem bzzaf" energy. Max 250 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=220, situation="praise")
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
        return f"❌ Ma3endnach stats dial **{p1_name}** ou **{p2_name}**.", None, None
    if not s1:
        return f"❌ Ma3endnach stats dial **{p1_name}**.", None, None
    if not s2:
        return f"❌ Ma3endnach stats dial **{p2_name}**.", None, None

    prompt = f"""
Head-to-head in Moroccan Darija DODa standard Twitter style:
**{s1['name']}**: {s1['goals']}G {s1['assists']}A | {s1['avg_rating']:.2f}/10 | {s1['games']} matchs
**{s2['name']}**: {s2['goals']}G {s2['assists']}A | {s2['avg_rating']:.2f}/10 | {s2['games']} matchs

1. Epic battle title in Darija
2. Stats side-by-side (Discord table ✅❌)
3. Final funny/toxic verdict — say it confidently, not "both are good"
Max 400 chars. Use DODa: 3,7,9,ch,gh.
"""
    result = await ask_and_clean(_ask, prompt, max_tokens=380, situation="general")
    if not result:
        winner = s1["name"] if s1["avg_rating"] >= s2["avg_rating"] else s2["name"]
        result = (f"**{s1['name']}** vs **{s2['name']}**\n"
                  f"Goals: {s1['goals']} vs {s2['goals']}\n"
                  f"Assists: {s1['assists']} vs {s2['assists']}\n"
                  f"Rating: {s1['avg_rating']:.2f} vs {s2['avg_rating']:.2f}\n"
                  f"🏆 **{winner}** wins!")
    return result, s1, s2
