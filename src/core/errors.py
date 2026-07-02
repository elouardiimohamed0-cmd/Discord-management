"""Custom application exceptions."""


class NoMatchesFound(Exception):
    """Raised when no matches exist in the database."""
    pass


class PlayerNotInMatch(Exception):
    """Raised when a player is not found in a match."""
    pass


class SquadNotLoaded(Exception):
    """Raised when the squad registry failed to load."""
    pass


class ScrapeFailed(Exception):
    """Raised when the scraper fails after all retries."""
    pass
