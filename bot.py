"""
Rachad L3ERGONI — Perfect Pro Clubs Bot
Features from AllCalculatedRoast + Direct EA API + Clean Darija
- Auto-detect matches every 30 min
- MVP photos with stats
- Simple commands
- No spam
"""
import os
import io
import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

import ea_api
import gemini
import image_gen
from state import load_seen, save_seen

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("RachadBot")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN not set!")

# ─── CONFIG ───
CHECK_INTERVAL = 30  # minutes
MATCH_CHANNEL_ID = int(os.environ.get("MATCH_CHANNEL_ID", 0)) or None

# ─── BOT ───
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

seen_matches = set()
client = ea_api.get_client()

# ─── HELPERS ───
def _match_channel():
    return bot.get_channel(MATCH_CHANNEL_ID) if MATCH_CHANNEL_ID else None

async def _send(ch, text="", image=None, filename="image.png"):
    text = (text or "").strip()
    if not text and not image:
        return
    if image:
        image.seek(0)
        file = discord.File(image, filename=filename)
        await ch.send(text[:1900] or None, file=file)
    else:
        while text:
            chunk, text = text[:2000], text[2000:]
            await ch.send(chunk)

# ═══════════════════════════════════════════════════════════════════════════════
# AUTO MATCH DETECTION (Every 30 min)
# ═══════════════════════════════════════════════════════════════════════════════

@tasks.loop(minutes=CHECK_INTERVAL)
async def check_matches():
    """Auto-detect new matches. Only post if NEW match found."""
    global seen_matches
    ch = _match_channel()
    if not ch:
        return
    
    try:
        raw_matches = await client.get_matches(5)
        if not raw_matches:
            return
        
        new_matches = []
        for r in raw_matches:
            mid = ea_api.get_match_id(r)
            if mid and mid not in seen_matches:
                new_matches.append(r)
                seen_matches.add(mid)
        
        if new_matches:
            save_seen(seen_matches)
            logger.info(f"🆕 {len(new_matches)} new match(es)")
            
            # Post ONLY the most recent new match
            m = ea_api.parse_match(new_matches[0])
            await _post_match(ch, m)
            
    except Exception as e:
        logger.error(f"Check error: {e}")

async def _post_match(ch, m):
    """Post match: report + MOTM photo. Clean and simple."""
    try:
        # 1. Match Report (short, clean)
        report = await gemini.match_report(m)
        report = _clean_length(report, max_lines=5)
        
        # 2. Match Poster
        loop = asyncio.get_event_loop()
        poster = await loop.run_in_executor(
            None,
            image_gen.make_match_poster,
            m["our_name"], m["opp_name"],
            m["our_goals"], m["opp_goals"], m["date"]
        )
        
        await _send(ch, report, poster, f"match_{m['our_goals']}_{m['opp_goals']}.png")
        await asyncio.sleep(2)
        
        # 3. MOTM with Photo (always)
        if m.get("players"):
            best = m["players"][0]
            motm_text = (
                f"🌟 **MOTM: {best['name']}**\\n"
                f"⭐ {best['rating']:.1f}/10 | ⚽ {best['goals']}G | 🎯 {best['assists']}A"
            )
            
            motm_img = await loop.run_in_executor(
                None,
                image_gen.make_motm_card,
                best["name"], best["rating"], best["goals"], best["assists"],
                f"vs {m['opp_name']}"
            )
            
            await _send(ch, motm_text, motm_img, "motm.png")
            
    except Exception as e:
        logger.error(f"Post error: {e}")
        await ch.send(f"⚠️ Match {m['our_goals']}-{m['opp_goals']} vs {m['opp_name']}")

def _clean_length(text, max_lines=5):
    """Keep text short and clean."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    return '\n'.join(lines[:max_lines])

# ═══════════════════════════════════════════════════════════════════════════════
# COMMANDS (Simple & Clear)
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="lastmatch")
async def cmd_lastmatch(ctx):
    """Last match report + MOTM photo."""
    async with ctx.typing():
        raw = await client.get_matches(1)
        if not raw:
            await ctx.send("❌ Ma3endnach match daba 😴")
            return
        m = ea_api.parse_match(raw[0])
        await _post_match(ctx.channel, m)

@bot.command(name="match")
async def cmd_match(ctx, num: int = 1):
    """Specific match (1=last, 2=before, etc.)."""
    if num < 1 or num > 10:
        await ctx.send("❌ Ghir bin 1 w 10 😅")
        return
    async with ctx.typing():
        raw = await client.get_matches(10)
        if num > len(raw):
            await ctx.send(f"❌ Ghir {len(raw)} matchs")
            return
        m = ea_api.parse_match(raw[num - 1])
        await _post_match(ctx.channel, m)

@bot.command(name="results")
async def cmd_results(ctx):
    """Quick table: last 10 results."""
    async with ctx.typing():
        raw = await client.get_matches(10)
        if not raw:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        lines = ["📋 **RESULTATS**", ""]
        for i, r in enumerate(raw, 1):
            m = ea_api.parse_match(r)
            icon = "🟢" if m["result"] == "W" else "🟡" if m["result"] == "D" else "🔴"
            lines.append(f"`{i}.` {icon} `{m['our_goals']}-{m['opp_goals']}` vs **{m['opp_name']}**")
        await ctx.send("\n".join(lines))

@bot.command(name="player")
async def cmd_player(ctx, *, name: str = ""):
    """Player stats from last 5 matches. Usage: !player Hamza"""
    if not name:
        await ctx.send("❌ Kteb ism: `!player Hamza`")
        return
    async with ctx.typing():
        raw = await client.get_matches(5)
        matches = [ea_api.parse_match(r) for r in raw]
        agg = ea_api.aggregate_stats(matches)
        key = next((k for k in agg if name.lower() in k.lower()), None)
        if not key:
            await ctx.send(f"❌ **{name}** — ma3endnach stats 😴")
            return
        s = agg[key]
        lines = [
            f"👤 **{s['name']}** — Last 5",
            f"🎮 {s['games']}m | ⚽ {s['goals']}G | 🎯 {s['assists']}A",
            f"⭐ Rating: **{s['avg_rating']:.2f}/10**",
            f"💥 Shots: {s['shots']} | 🛡️ Tackles: {s['tackles']}",
        ]
        await ctx.send("\n".join(lines))

@bot.command(name="players")
async def cmd_players(ctx):
    """Full squad list."""
    async with ctx.typing():
        members = await client.get_members()
        if not members:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        lines = ["👥 **SQUAD**", ""]
        for m in sorted(members, key=lambda x: float(x.get("ratingAve", 0) or 0), reverse=True)[:15]:
            name = m.get("proName") or m.get("name", "?")
            rating = m.get("ratingAve", "?")
            games = m.get("gamesPlayed", 0)
            goals = m.get("goals", 0)
            assists = m.get("assists", 0)
            pos = m.get("favoritePosition", "MID").upper()[:3]
            lines.append(f"**{name}** `{pos}` — {goals}G {assists}A | ⭐ {rating} | {games}m")
        await ctx.send("\n".join(lines)[:2000])

@bot.command(name="mvp")
async def cmd_mvp(ctx):
    """MVP photo + stats (last 5 matches)."""
    async with ctx.typing():
        raw = await client.get_matches(5)
        matches = [ea_api.parse_match(r) for r in raw]
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        agg = ea_api.aggregate_stats(matches)
        if not agg:
            await ctx.send("❌ Ma3endnach stats 😴")
            return
        mvp = max(agg.values(), key=lambda x: x["avg_rating"] + x["goals"] * 0.5 + x["assists"] * 0.3)
        
        # Generate MVP photo
        loop = asyncio.get_event_loop()
        mvp_img = await loop.run_in_executor(
            None,
            image_gen.make_motm_card,
            mvp["name"], mvp["avg_rating"], mvp["goals"], mvp["assists"],
            "MVP — Last 5 Matches"
        )
        
        text = (
            f"👑 **MVP: {mvp['name']}**\\n"
            f"🎮 {mvp['games']}m | ⚽ {mvp['goals']}G | 🎯 {mvp['assists']}A\\n"
            f"⭐ Rating: **{mvp['avg_rating']:.2f}/10**"
        )
        await _send(ctx.channel, text, mvp_img, "mvp.png")

@bot.command(name="roast")
async def cmd_roast(ctx, *, name: str = ""):
    """Roast a player. Usage: !roast Hamza 🔥"""
    if not name:
        await ctx.send("❌ Kteb ism: `!roast Hamza`")
        return
    async with ctx.typing():
        raw = await client.get_matches(5)
        matches = [ea_api.parse_match(r) for r in raw]
        text = await gemini.roast(name, matches)
        text = _clean_length(text, max_lines=4)
        await ctx.send(text[:2000])

@bot.command(name="stats")
async def cmd_stats(ctx):
    """Club season stats."""
    async with ctx.typing():
        info = await client.get_club_info()
        s = info.get("club_stats", info.get("stats", {}))
        w = int(s.get("wins", 0))
        t = int(s.get("ties", 0))
        l = int(s.get("losses", 0))
        total = w + t + l
        wr = f"{w/total*100:.1f}%" if total else "?"
        lines = [
            f"📊 **Rachad L3ERGONI**",
            f"🏆 W: **{w}** | 🟡 D: **{t}** | 💀 L: **{l}**",
            f"📈 Win Rate: **{wr}** | Games: **{s.get('gamesPlayed', '?')}**",
            f"⚽ Goals: **{s.get('goals', '?')}** / **{s.get('goalsAgainst', '?')}**",
            f"🎯 Skill Rating: **{s.get('skillRating', '?')}**",
            f"🏅 Best Division: **Div {s.get('bestDivision', '?')}**",
            f"🔗 proclubstracker.com/club/{ea_api.CLUB_ID}?platform={ea_api.PLATFORM}",
        ]
        await ctx.send("\n".join(lines))

@bot.command(name="compare")
async def cmd_compare(ctx, p1: str = "", *, p2: str = ""):
    """Compare 2 players. Usage: !compare Hamza Karim"""
    if not p1 or not p2:
        await ctx.send("❌ Usage: `!compare Hamza Karim`")
        return
    async with ctx.typing():
        raw = await client.get_matches(5)
        matches = [ea_api.parse_match(r) for r in raw]
        agg = ea_api.aggregate_stats(matches)
        s1 = next((agg[k] for k in agg if p1.lower() in k.lower()), None)
        s2 = next((agg[k] for k in agg if p2.lower() in k.lower()), None)
        if not s1 or not s2:
            await ctx.send("❌ Ma3endnach stats dial wa7ed menhoum 😴")
            return
        
        # Generate comparison image
        loop = asyncio.get_event_loop()
        compare_img = await loop.run_in_executor(
            None,
            image_gen.make_comparison_card,
            s1, s2
        )
        
        winner = s1["name"] if s1["avg_rating"] >= s2["avg_rating"] else s2["name"]
        text = (
            f"⚔️ **{s1['name']}** vs **{s2['name']}**\\n"
            f"⚽ Goals: {s1['goals']} vs {s2['goals']}\\n"
            f"🎯 Assists: {s1['assists']} vs {s2['assists']}\\n"
            f"⭐ Rating: {s1['avg_rating']:.2f} vs {s2['avg_rating']:.2f}\\n"
            f"🏆 **{winner}** wins!"
        )
        await _send(ctx.channel, text, compare_img, f"compare_{p1}_{p2}.png")

@bot.command(name="form")
async def cmd_form(ctx):
    """Team form (last 5 matches)."""
    async with ctx.typing():
        raw = await client.get_matches(5)
        matches = [ea_api.parse_match(r) for r in raw]
        if not matches:
            await ctx.send("❌ Ma3endnach data 😴")
            return
        results = "".join(m["result"] for m in matches)
        wins = sum(1 for m in matches if m["result"] == "W")
        losses = sum(1 for m in matches if m["result"] == "L")
        gf = sum(m["our_goals"] for m in matches)
        ga = sum(m["opp_goals"] for m in matches)
        
        lines = [
            f"📈 **FORM — Last 5**",
            f"**{results}** | W{wins} L{losses}",
            f"⚽ {gf} pour / {ga} contre",
        ]
        await ctx.send("\n".join(lines))

@bot.command(name="help")
async def cmd_help(ctx):
    """Show all commands."""
    lines = [
        "⚽ **Rachad L3ERGONI Bot**",
        "═══════════════════════════════════",
        "",
        "**📋 MATCHES**",
        "`!lastmatch` — Last match + MOTM photo",
        "`!match 2` — Specific match (1=last, 2=before...)",
        "`!results` — Results table (last 10)",
        "`!form` — Team form (last 5)",
        "",
        "**👥 PLAYERS**",
        "`!player Hamza` — Player stats (last 5)",
        "`!players` — Full squad list",
        "`!mvp` — MVP photo + stats",
        "`!roast Hamza` — Roast player 🔥",
        "`!compare Hamza Karim` — Compare 2 players",
        "",
        "**📊 CLUB**",
        "`!stats` — Season stats",
        "",
        "**🤖 AUTO**",
        "Bot checks every 30 min for new matches",
        "Auto-posts report + MOTM photo when found",
        "",
        "_Simple. Clean. No spam._",
    ]
    await ctx.send("\n".join(lines))

@bot.command(name="ping")
async def cmd_ping(ctx):
    await ctx.send(f"Pong ✅ | Latency: {bot.latency*1000:.0f}ms")

# ─── EVENTS ───

@bot.event
async def on_ready():
    global seen_matches
    seen_matches = load_seen()
    logger.info(f"✅ Bot ready: {bot.user}")
    check_matches.start()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Naqes argument — `!help`")
        return
    logger.error(f"Command error: {error}")
    await ctx.send(f"❌ Error: `{str(error)[:50]}`")

# ─── HEALTH SERVER ───
def start_health_server():
    import threading
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    port = int(os.environ.get("PORT", 10000))
    class H(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Rachad L3ERGONI OK")
        def log_message(self, *a): pass
    s = HTTPServer(("0.0.0.0", port), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()

# ─── START ───
if __name__ == "__main__":
    start_health_server()
    bot.run(TOKEN)
