---
name: sleeper-fantasy-football-api
description: Use this skill when building, reviewing, debugging, or documenting fantasy football applications that use the Sleeper API for users, leagues, rosters, matchups, drafts, transactions, traded picks, NFL state, players, trending adds/drops, standings, playoff brackets, lineup analysis, waiver analysis, trade analysis, dynasty tools, or fantasy football dashboards.
---

# Sleeper Fantasy Football API Skill

Build reliable fantasy football applications, scripts, dashboards, agents, and
analysis tools using the [Sleeper API](https://docs.sleeper.com/).

## Core Principles

The Sleeper public API is **read-only** and does **not** require an API token,
so the engineering effort goes into using it correctly and efficiently:

- **Store `user_id`, not username.** Usernames can change; user IDs are stable.
- **Cache `players/nfl` daily.** It is a large payload Sleeper says not to fetch
  more than once per day.
- **Respect rate guidance.** Stay well under ~1,000 calls/minute or risk an IP block.
- **Build a normalized league context first** (users, rosters, players, state, ID maps)
  before doing any analysis.
- **Always apply league scoring + roster settings.** A recommendation changes
  drastically between PPR, half-PPR, standard, superflex, TE-premium, dynasty, IDP.
- **The API cannot modify anything** — no adds/drops, trades, or lineup changes.
- **Convert player IDs to names** in all user-facing output.

## When To Use

Use this skill when the user wants to: create a Sleeper API client; fetch a user
or their leagues; analyze a league, rosters, or matchups; map roster IDs to owners;
analyze waivers/transactions, trades, or traded picks; build dynasty/draft tools;
cache player data; fetch trending adds/drops; or build a fantasy dashboard or agent.

## Quick Reference

| Need | Endpoint |
|---|---|
| Resolve user | `GET /user/{username_or_user_id}` |
| User's leagues | `GET /user/{user_id}/leagues/nfl/{season}` |
| League metadata + scoring | `GET /league/{league_id}` |
| Rosters | `GET /league/{league_id}/rosters` |
| League users (names/avatars) | `GET /league/{league_id}/users` |
| Weekly matchups | `GET /league/{league_id}/matchups/{week}` |
| Transactions (adds/drops/trades/FAAB) | `GET /league/{league_id}/transactions/{round}` |
| Traded picks (dynasty) | `GET /league/{league_id}/traded_picks` |
| Playoff brackets | `GET /league/{league_id}/winners_bracket` / `losers_bracket` |
| Current season/week | `GET /state/nfl` |
| Drafts | `GET /league/{league_id}/drafts`, `GET /draft/{draft_id}`, `/picks`, `/traded_picks` |
| All players (cache daily!) | `GET /players/nfl` |
| Trending adds/drops | `GET /players/nfl/trending/{add\|drop}?lookback_hours=24&limit=25` |

Base URL: `https://api.sleeper.app/v1`

Full catalog with field notes: [references/sleeper-api-endpoints.md](references/sleeper-api-endpoints.md)

## Workflow

1. **Classify the use case** (dashboard, matchup analyzer, waiver assistant, trade
   analyzer, dynasty tracker, draft recap, agent). Capture season, league_id,
   user, week, scoring format, dynasty/redraft/keeper.
2. **Resolve user and/or league.** From a username: `GET /user/{username}` →
   store `user_id` → `GET /user/{user_id}/leagues/nfl/{season}`. From a league_id:
   fetch league, users, rosters.
3. **Build normalized league context** — see
   [references/league-context-model.md](references/league-context-model.md).
   Include scoring settings, roster positions, `roster_id → owner` map,
   `user_id → display name` map, cached player dictionary, current NFL state.
4. **Cache player data daily** — see
   [references/player-cache-strategy.md](references/player-cache-strategy.md).
5. **Normalize** with helper maps: `players_by_id`, `users_by_id`, `rosters_by_id`,
   `owners_by_roster_id`, `matchups_by_matchup_id`, `transactions_by_type`.
6. **Apply scoring context** — see
   [references/fantasy-recommendation-rules.md](references/fantasy-recommendation-rules.md).
7. **Generate output** with player names (not IDs), owner names, week/season
   context, confidence level, data limitations, and actionable next steps.

## Code Templates

Start from these instead of writing clients from scratch:

- Python client: [templates/sleeper_client.py](templates/sleeper_client.py)
- TypeScript client: [templates/sleeper-client.ts](templates/sleeper-client.ts)
- League context builder: [templates/league-context.ts](templates/league-context.ts)
- Report formats: [templates/](templates/) (`waiver-report.md`, `matchup-report.md`,
  `trade-analysis.md`, `app-design.md`, `review-checklist.md`)

## Analysis Recipes

- Matchups (pair by `matchup_id`, derive bench): [references/matchup-analysis.md](references/matchup-analysis.md)
- Waiver wire (availability + trending): [references/waiver-analysis.md](references/waiver-analysis.md)
- Trades: [references/trade-analysis.md](references/trade-analysis.md)
- Dynasty picks: [references/dynasty-pick-tracking.md](references/dynasty-pick-tracking.md)
- Drafts: [references/draft-analysis.md](references/draft-analysis.md)
- Testing & fixtures: [references/testing-fixtures.md](references/testing-fixtures.md)

Worked examples live in [examples/](examples/).

## Key Gotchas

1. **Usernames can change** — store `user_id`.
2. **`players/nfl` is large** — cache daily, never per-request.
3. **Matchups are one row per roster** — pair the two rows sharing a `matchup_id`.
4. **Bench is derived** — `bench = players − starters`.
5. **Scoring matters** — never recommend players without reading league scoring when a league is provided.
6. **Read-only API** — don't design features that add/drop, trade, or set lineups.
7. **Trending adds are market activity, not projections** — contextualize with availability, team need, scoring, role, injury.
8. **No projections/news/depth charts** — integrate and label a separate source if needed.

## Stop Conditions

Stop and ask when a required input is missing: league_id, season, or week for
league-specific analysis; which league when a user has several; or scoring/league
type for a trade analysis without league context. If the user gives only a
username, fetch their leagues and ask which one to analyze.

## Anti-Patterns

Do not: call `players/nfl` on every request; ignore league scoring; recommend
players without checking availability; show raw player IDs; treat trending adds as
projections; claim the API can modify a league; ignore rate guidance; assume
usernames are permanent; confuse `roster_id` with `user_id`; or make live
injury/projection claims without a separate current data source.
