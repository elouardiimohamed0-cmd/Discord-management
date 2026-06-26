# Phase 1 — Core Architecture

This phase replaces the tangled single-file bot shape with a clean application shell.

What is included:
- typed settings
- structured logging
- Discord client factory
- all required slash commands registered safely
- squad identity registry
- hard data-rule helpers: `match.players` is the source of truth
- app context / dependency container

What comes next:
- Phase 2: Pro Clubs Tracker + Playwright data engine and normalized DB
- Phase 3: real command handlers powered by the data engine
