# Sleeper Fantasy Football API

A Claude Code skill for creating clients, dashboards, agents, and analysis tools
using the [Sleeper Fantasy Football API](https://docs.sleeper.com/).

The skill helps with: users, leagues, rosters, league users, matchups,
transactions, traded picks, drafts, players, trending adds/drops, player caching,
matchup analysis, waiver analysis, trade analysis, dynasty tools, and dashboards.

## Core idea

Build a normalized league context first, cache the large player dictionary daily,
and always make fantasy recommendations in the context of league scoring, roster
settings, availability, and data freshness. The public API is read-only and needs
no token — so correctness, caching, and rate-awareness are the real work.

## Layout

```
sleeper-fantasy-football-api/
  SKILL.md                      # entry point — principles, workflow, quick reference
  README.md
  references/                   # deep-dive guides loaded on demand
    sleeper-api-endpoints.md
    player-cache-strategy.md
    league-context-model.md
    matchup-analysis.md
    waiver-analysis.md
    trade-analysis.md
    dynasty-pick-tracking.md
    draft-analysis.md
    fantasy-recommendation-rules.md
    testing-fixtures.md
  templates/                    # ready-to-adapt code + report scaffolds
    sleeper_client.py
    sleeper-client.ts
    league-context.ts
    waiver-report.md
    matchup-report.md
    trade-analysis.md
    app-design.md
    review-checklist.md
  examples/                     # worked outputs
    league-dashboard.md
    weekly-waiver-report.md
    dynasty-trade-analysis.md
    draft-recap.md
    trending-player-report.md
```

## Source

API behavior described here follows the official Sleeper docs at
<https://docs.sleeper.com/>. The public API is read-only, requires no token, and
Sleeper recommends staying under ~1,000 calls/minute and caching `players/nfl`
no more than once per day.
