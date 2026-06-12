Rachad L3ERGONI Bot — Humanized Darija Integration
📦 Files Included
Table
File	Purpose	Action
human_darija.py	NEW — Humanization engine	Copy to your project root
darija_engine.py	NEW — Standalone Darija engine (optional)	Copy if you want to replace AI
bot_humanized.py	MODIFIED — Your bot with humanization	Replace your bot.py OR
Follow integration guide below
🚀 Quick Start (2 minutes)
Option A: Replace bot.py completely (EASIEST)
Backup your current bot.py:
bash
cp bot.py bot.py.backup
Copy the new files:
bash
cp human_darija.py /path/to/your/bot/
cp bot_humanized.py /path/to/your/bot/bot.py
Update requirements.txt (add random if not present — it's built-in):
plain
discord.py
openai
playwright
pillow
httpx
aiohttp
Restart your bot:
bash
python bot.py
✅ Done! Your bot now talks like a real Moroccan with typing delays and imperfections.
🔧 Option B: Manual Integration (if you customized bot.py)
If you made changes to bot.py that you want to keep, follow these steps:
Step 1: Add human_darija.py to your project
Copy human_darija.py to the same folder as your bot.py.
Step 2: Add the import
At the top of your bot.py, add:
Python
from human_darija import HumanDarija
Step 3: Initialize the humanizer
After creating your bot, add:
Python
humanizer = HumanDarija()
Step 4: Replace your _send() function
Find your _send() function and replace it with this humanized version:
Python
async def _send(ch, text="", image=None, filename="image.png", emotion='excitement'):
    """Send with humanization and realistic typing delay."""
    text = (text or "").strip()
    text = text.replace("\n", "
")
    if not text and not image:
        return

    # Humanize the text before sending
    if text:
        text = humanizer.humanize(text, emotion=emotion, intensity=0.75)

    # Calculate realistic typing delay
    word_count = len(text.split()) if text else 0
    if word_count <= 3:
        typing_time = random.randint(1, 3)
    elif word_count <= 8:
        typing_time = random.randint(3, 7)
    else:
        typing_time = random.randint(7, 15)

    # Add random "thinking" pause for longer messages
    if len(text) > 100 and random.random() < 0.3:
        typing_time += random.randint(2, 5)

    # Simulate typing
    async with ch.typing():
        await asyncio.sleep(typing_time)

    if image:
        image.seek(0)
        file = discord.File(image, filename=filename)
        await ch.send(text[:1900] or None, file=file)
    else:
        while text:
            chunk, text = text[:2000], text[2000:]
            await ch.send(chunk)
Step 5: Add emotion to your command calls
For each command, add the emotion parameter to _send():
Match reports (win/loss/draw):
Python
# Win
await _send(ctx.channel, report_text, emotion='excitement')
# Loss
await _send(ctx.channel, report_text, emotion='disappointment')
# Draw
await _send(ctx.channel, report_text, emotion='thinking')
Roasts:
Python
await _send(ctx.channel, roast_text, emotion='laughter')
Hype:
Python
await _send(ctx.channel, hype_text, emotion='excitement')
Praise/MOTM:
Python
await _send(ctx.channel, motm_text, emotion='love')
Banter:
Python
await _send(ctx.channel, banter_text, emotion='laughter')
Drama:
Python
await _send(ctx.channel, drama_text, emotion='disappointment')
Analytics/Stats:
Python
await _send(ctx.channel, stats_text, emotion='thinking')
🧪 Testing
After integration, test these commands:
plain
!lastmatch    → Should show typing delay then humanized report
!roastplayer Hamza  → Should show typing delay then humanized roast
!hype         → Should show typing delay then humanized hype
!banter       → Should show typing delay then humanized banter
!meme         → Should show typing delay then humanized meme
The bot should:
✅ Show "typing..." indicator for 3-15 seconds
✅ Use lowercase sometimes
✅ Add fillers like "safi", "walo", "z3ma"
✅ Mix English/French words naturally
✅ Have occasional typos and repeated letters
✅ Use contextual emojis (not random)
🎨 Customization
Adjust humanization intensity
In _send(), change the intensity parameter:
Python
text = humanizer.humanize(text, emotion=emotion, intensity=0.75)
0.3 = Slightly human (subtle)
0.7 = Very human (recommended)
0.95 = Maximum human (very chaotic, lots of typos)
Disable specific features
In human_darija.py, you can adjust probabilities:
Python
# In add_typing_imperfections():
if random.random() < 0.15:  # Lower = less lowercase starts

# In add_fillers():
if random.random() > 0.4:   # Lower = fewer fillers

# In code_switch():
if random.random() < 0.20: # Lower = less code-switching
Add your own fillers
In HumanDarija.__init__(), add to self.fillers:
Python
self.fillers = [
    "safi", "ah", "wa", "yallah", "ewa", "oh", "lla",
    # Add your own:
    "wakha hakkak", "z3ma", "ya3ni", "wallah", "b7al hdiya",
    "dima dima", "noss noss", "kif kif", "merra merra",
]
📁 Complete File List
Your project should now have these files:
plain
your-bot/
├── bot.py                    ← Modified with humanization
├── human_darija.py           ← NEW — Humanization engine
├── darija_engine.py          ← NEW — Standalone engine (optional)
├── gemini.py                 ← Your existing AI module
├── darija.py                 ← Your existing Darija module
├── ea_api.py                ← Your existing API module
├── scraper.py               ← Your existing scraper
├── achievements.py          ← Your existing achievements
├── roast_engine.py          ← Your existing roast engine
├── image_gen.py             ← Your existing image generator
├── state.py                 ← Your existing state module
├── requirements.txt         ← Updated dependencies
└── assets/                  ← Your existing assets folder
🆘 Troubleshooting
"Module not found: human_darija"
→ Make sure human_darija.py is in the same folder as bot.py
"Typing delay too long"
→ Lower the typing_time values in _send():
Python
if word_count <= 3:
    typing_time = random.randint(1, 2)  # Faster
"Too many typos"
→ Lower the intensity:
Python
text = humanizer.humanize(text, emotion=emotion, intensity=0.5)
"Not human enough"
→ Increase the intensity:
Python
text = humanizer.humanize(text, emotion=emotion, intensity=0.9)
"Bot doesn't show typing indicator"
→ Make sure async with ch.typing(): is working. Check bot permissions.
🎯 What Changed
Table
Before	After
Instant replies	3-15 second typing delays
Perfect grammar	Lowercase starts, typos
No fillers	"safi", "walo", "z3ma" everywhere
Pure Darija	Natural French/English mix
Clean punctuation	!!, ??, ...
No corrections	* correction  mid-sentence
Generic emoji	Contextual emoji placement
Robotic feel	Real Moroccan human feel
Made with 🔥 for Rachad L3ERGONI
