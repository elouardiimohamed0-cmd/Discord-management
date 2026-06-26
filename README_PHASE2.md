# Phase 2 — Data Engine (Pro Clubs Tracker + Playwright fallback)

This phase adds:
- SQLite normalized database schema
- ProClubsTracker client (httpx API + Playwright fallback)
- parser that builds Match objects where `match.players` is the source of truth
- persistence into `matches` and `player_match_stats`
- Discord commands: `/sync` and `/status`

Notes:
- `squad.json` is identity only (nickname/image/personality/tags). It never decides who played.
- Only players present in match payload are inserted for match-level stats.
