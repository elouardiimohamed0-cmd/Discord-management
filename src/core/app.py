from __future__ import annotations

from dataclasses import dataclass

from src.core.config import Settings, load_settings
from src.data.database import Database
from src.data.repositories import ClubRepository
from src.discord_layer.bot import build_bot
from src.scraper.proclubs_tracker import ProClubsTrackerClient
from src.services.match_service import MatchService
from src.squad.registry import SquadRegistry


@dataclass
class AppContext:
    settings: Settings
    squad: SquadRegistry
    db: Database
    repo: ClubRepository
    pct: ProClubsTrackerClient
    matches: MatchService
    bot: object


def create_app() -> AppContext:
    settings = load_settings()
    squad = SquadRegistry.from_file(settings.squad_file)

    db = Database(settings.database_path)
    db.initialize()
    repo = ClubRepository(db)

    # store squad identities for enrichment (identity only)
    repo.upsert_identities(squad.all())

    pct = ProClubsTrackerClient(settings=settings, squad=squad, repository=repo)
    matches = MatchService(client=pct, repository=repo)

    bot = build_bot(settings=settings, squad=squad, match_service=matches)

    return AppContext(
        settings=settings,
        squad=squad,
        db=db,
        repo=repo,
        pct=pct,
        matches=matches,
        bot=bot,
    )
