# Sleeper Fantasy App Design

## Product Goal
<one sentence>

## Core Features
- ...

## API Endpoints Used
| Feature | Sleeper Endpoint |
|---|---|

## Architecture
```
Frontend / Agent
   -> Fantasy API Service
   -> Sleeper Client
   -> Cache Layer
   -> Sleeper API
   -> Analysis Engine
   -> Recommendation / Report Output
```

### Components
| Component | Purpose |
|---|---|
| SleeperClient | Typed wrapper for API endpoints |
| PlayerCache | Daily player dictionary cache |
| LeagueContextBuilder | Combines league, rosters, users, state, players |
| AnalysisEngine | Matchup / waiver / roster / trade / draft analysis |
| RecommendationEngine | Waiver / trade / lineup recommendations |
| API Layer | Exposes app endpoints |
| UI Dashboard | Displays league insights |
| Job Scheduler | Refreshes players and league data |
| Observability | Logs API calls, cache hits, failures |

## Data Model
```sql
CREATE TABLE sleeper_player_cache (
  player_id   TEXT PRIMARY KEY,
  player_json JSONB NOT NULL,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sleeper_league_snapshot (
  league_id     TEXT NOT NULL,
  season        TEXT NOT NULL,
  week          INTEGER,
  snapshot_type TEXT NOT NULL,
  payload       JSONB NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (league_id, season, week, snapshot_type)
);

CREATE TABLE sleeper_analysis_run (
  id            BIGSERIAL PRIMARY KEY,
  league_id     TEXT NOT NULL,
  season        TEXT,
  week          INTEGER,
  analysis_type TEXT NOT NULL,
  result        JSONB NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## Caching Strategy
See `references/player-cache-strategy.md`.

## MVP Scope
- ...

## Production Risks
- Rate limiting / IP block if `players/nfl` is over-called.
- Stale player cache breaks name resolution.
- No projections/news from Sleeper — needs a labeled external source.

## Agent tool surface (if exposing to an LLM)
Expose bounded tools, not raw HTTP:
- `get_sleeper_user(username_or_user_id)`
- `get_user_leagues(user_id, season)`
- `get_league_context(league_id)`
- `get_week_matchups(league_id, week)`
- `get_available_trending_players(league_id, trend_type, lookback_hours, limit)`
- `analyze_roster(league_id, roster_id)`
- `analyze_trade(league_id, side_a_assets, side_b_assets)`
- `get_draft_recap(draft_id)`

Avoid `raw_http_get(url)`, `fetch_everything()`, `run_arbitrary_sleeper_query()`.
