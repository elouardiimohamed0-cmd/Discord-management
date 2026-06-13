Rachad L3ERGONI Bot v2
Premium Discord Bot for EA FC / FIFA Pro Clubs
Features
Native Moroccan Darija - Uses DODa (Darija Open Dataset) patterns + authentic slang
95% Roast Mode - Every response is a roast, backed by real data
Real Statistics - Every possible stat from EA FC Pro Clubs API
Premium Visuals - Cards inspired by EA FC Ultimate Team, Futbin, Sofascore
6 Personalities - Casablanca Street, Analyst, Toxic, Coach, Commentator, Cafeteria
Auto Leaderboards - Daily/Weekly/Monthly with visual cards
Auto Match Detection - Checks every 5 minutes during sessions
Advanced Metrics - Impact Score, Clutch Score, Error Score, Throwing Score, Form Index
Commands
Table
Command	Description
!roast	Start session monitoring
!stop	Stop session
!lastmatch	Last match + all stats + MOTM card
!stats <name>	Player stats + premium card
!roastplayer <name>	Roast specific player
!mvp	MVP of last 5 matches
!compare <p1> <p2>	1v1 comparison
!leaderboard <period>	Leaderboard (day/week/month/all)
!banter	Football trash talk
!drama	Drama/polemique
!meme	Meme b Darija
!transfer	Transfer rumor
!predict <opponent>	Match prediction
!clubinfo	Club info
!worst	Worst player of the week
!who_sold	Who sold the match
!carry_detector	Who is carrying
!fraud_check <name>	Check if fraud
!ballon_dor	Ballon d'Or
!ghost_detector	Detect inactive players
!pass_the_ball <name>	Call out ball hog
!personality <mode>	Switch personality
!sync	Manual sync from EA API
!help	All commands
Setup
Install dependencies:
bash
pip install -r requirements.txt
Configure environment:
bash
cp .env.example .env
# Edit .env with your Discord token, channel IDs, and EA API details
Edit squad.json:
Add your real players with positions, numbers, nicknames, and images.
Add player photos:
Place PNG images in assets/ folder matching paths in squad.json.
Run the bot:
bash
python bot.py
Deployment (Render)
Push to GitHub
Connect Render to your repo
Set environment variables in Render dashboard
Deploy!
Darija Language System
The bot uses:
DODa (Darija Open Dataset) spelling conventions
Authentic Moroccan gamer slang
French/English code-switching where it hits harder
500+ positive word filter (no praise allowed)
Human-like imperfections (lowercase starts, dropped articles)
Stats Engine
Collects every available stat:
Goals, Assists, Shots, Passes, Tackles, Interceptions
Possession Losses, Dribbles, Fouls, Cards
Distance Covered, Sprint Speed, Minutes Played
Advanced metrics:
Impact Score: Weighted offensive + defensive contribution
Clutch Score: Performance in close matches
Error Score: Possession losses + fouls + cards weighted
Throwing Score: Error score / rating ratio
Form Index: Recent trend vs previous performance
Passing Influence: Key passes + pass accuracy weighted
Defensive Contribution: Tackles + interceptions weighted
Offensive Contribution: Goals + shots on target + key passes weighted
File Structure
plain
your-bot/
├── bot.py              # Main Discord bot (24 commands)
├── darija_engine.py    # Native Darija engine (95% roast)
├── stats_engine.py     # Real stats + advanced metrics
├── image_gen.py        # Premium visual cards
├── scraper.py          # EA FC Pro Clubs API scraper
├── squad.json          # Player database (EDIT THIS)
├── match_data.json     # Match history storage
├── requirements.txt    # Dependencies
├── .env.example        # Environment template
├── assets/             # Player photos
└── README.md           # This file
License
MIT - Made with 🔥 for Rachad L3ERGONI
