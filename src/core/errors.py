from __future__ import annotations


class BotError(Exception):
    """Base application error."""


class ConfigurationError(BotError):
    """Raised when required configuration is missing or invalid."""


class DataRuleViolation(BotError):
    """Raised when a hard data rule would be violated."""


class PlayerNotInMatch(DataRuleViolation):
    """Raised when a command tries to use a player absent from match.players."""
