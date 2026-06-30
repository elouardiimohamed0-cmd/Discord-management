from __future__ import annotations

import asyncio
from dataclasses import dataclass

from src.core.config import Settings, load_settings
from src.core.logging import configure_logging
from src.data.database import Database
from src.data.repositories import ClubRepository
from src.discord_layer.bot import build_bot
from src.engine.card_engine import CardEngine
from src.engine.roast_engine import RoastEngine
from src.engine.video_engine import VideoEngine
from src.scraper.proclubs_tracker import ProClubsTrackerClient
from src.services.auto_service import AutoContentService
from src.services.match_service import MatchService
from src.services.records_service import RecordsService
from src.squad.registry import SquadRegistry


@dataclass
class AppContext:
    settings: Settings
    squad: SquadRegistry
    db: Database
    repo: ClubRepository
    pct: ProClubsTrackerClient
    matches: MatchService
    roast: RoastEngine
    cards: CardEngine
    video: VideoEngine
    records: RecordsService
    auto: AutoContentService
    bot: object


def create_app() -> AppContext:
    settings = load_settings()
    configure_logging(settings.log_level)

    squad = SquadRegistry.from_file(settings.squad_file)

    db = Database(settings.database_path)
    db.initialize()
    repo = ClubRepository(db)
    repo.upsert_identities(squad.all())

    pct = ProClubsTrackerClient(settings=settings, squad=squad, repository=repo)
    matches = MatchService(client=pct, repository=repo, squad=squad)

    roast = RoastEngine(repository=repo, squad=squad)
    cards = CardEngine(settings=settings, squad=squad)
    video = VideoEngine(settings=settings, squad=squad)
    records = RecordsService(repository=repo, squad=squad)

    auto = AutoContentService(
        settings=settings,
        repository=repo,
        squad=squad,
        roast=roast,
        cards=cards,
        video=video,
    )

    bot = build_bot(
        settings=settings,
        squad=squad,
        match_service=matches,
        roast=roast,
        cards=cards,
        video=video,
        records=records,
        auto=auto,
    )

    # Pre-warm browser in background so first /sync is fast
    asyncio.create_task(pct.prewarm())

    return AppContext(
        settings=settings,
        squad=squad,
        db=db,
        repo=repo,
        pct=pct,
        matches=matches,
        roast=roast,
        cards=cards,
        video=video,
        records=records,
        auto=auto,
        bot=bot,
    )
