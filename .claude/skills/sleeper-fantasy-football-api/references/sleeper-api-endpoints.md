# Sleeper API Endpoint Catalog

Base URL: `https://api.sleeper.app/v1`

**Auth:** none — the public API is read-only and requires no token.
**Rate guidance:** stay under ~1,000 calls/minute or risk an IP block.
**Sport:** fantasy football uses `nfl` as the sport path value.

## Users

### `GET /user/{username_or_user_id}`
Resolve a username or user ID to a user object (`user_id`, `username`,
`display_name`, `avatar`).

> Store `user_id`, **not** username — usernames can change over time.

### `GET /user/{user_id}/leagues/nfl/{season}`
All of a user's NFL leagues for a season. `season` is a string, e.g. `"2025"`.

### `GET /user/{user_id}/drafts/nfl/{season}`
All drafts a user participated in for the season.

## Leagues

### `GET /league/{league_id}`
League metadata: `name`, `season`, `status`, `settings`, `scoring_settings`,
`roster_positions`, `draft_id`, `previous_league_id` (for league history chains),
`total_rosters`.

### `GET /league/{league_id}/rosters`
All rosters. Each has `roster_id`, `owner_id`, `players` (all player IDs),
`starters`, `reserve`, `taxi`, and a `settings` block with `wins`, `losses`,
`ties`, `fpts`, `fpts_against`, `fpts_decimal`.

### `GET /league/{league_id}/users`
All users in the league, with `display_name`, `avatar`, and a `metadata` block
that may hold `team_name`. Use to map `user_id → display name`.

> `roster_id` (1..N within a league) is **not** the same as `user_id`. Join
> rosters to users via `roster.owner_id === user.user_id`.

### `GET /league/{league_id}/matchups/{week}`
One object **per team**. The two objects sharing a `matchup_id` are opponents.
Fields: `roster_id`, `matchup_id`, `points`, `starters`, `players`,
`starters_points`, `players_points` (per-player scoring when available).
Bench = `players − starters`.

### `GET /league/{league_id}/transactions/{round}`
Adds, drops, waivers, trades, and FAAB for a week (`round` = week number).
Each transaction has `type` (`free_agent`, `waiver`, `trade`), `status`,
`adds`/`drops` (`{player_id: roster_id}`), `roster_ids`, `draft_picks`,
`waiver_budget`, `settings` (FAAB bid), `created`.

### `GET /league/{league_id}/traded_picks`
All traded future draft picks (dynasty/keeper). Each: `season`, `round`,
`roster_id` (current owner), `previous_owner_id`, `owner_id` (original).

### `GET /league/{league_id}/winners_bracket` / `GET /league/{league_id}/losers_bracket`
Playoff bracket structure. Each matchup node: `r` (round), `m` (match id),
`t1`/`t2` (roster ids or `{w|l: m}` references), `w`/`l` (winner/loser once decided).

## State

### `GET /state/nfl`
`season`, `season_type` (`pre`/`regular`/`post`/`off`), `week`, `leg`,
`display_week`, `league_season`. Use this to know the "current" week — don't
hardcode it.

## Drafts

- `GET /league/{league_id}/drafts` — all drafts for a league.
- `GET /draft/{draft_id}` — draft metadata: `type` (snake/auction/linear),
  `status`, `settings`, `draft_order`, `slot_to_roster_id`.
- `GET /draft/{draft_id}/picks` — every pick: `player_id`, `picked_by`,
  `roster_id`, `round`, `pick_no`, `draft_slot`, `metadata`.
- `GET /draft/{draft_id}/traded_picks` — picks traded within this draft.

## Players

### `GET /players/nfl`
The full player dictionary keyed by `player_id`. **Large payload** — Sleeper
asks that you cache it and call it at most once per day. Each player has
`full_name`, `first_name`, `last_name`, `team`, `position`, `fantasy_positions`,
`status`, `injury_status`, `depth_chart_position`, `years_exp`, `age`,
`search_rank`, etc. See `player-cache-strategy.md`.

### `GET /players/nfl/trending/{add|drop}?lookback_hours=24&limit=25`
Players ranked by add/drop activity over the lookback window (default 24h).
Returns `[{ player_id, count }]`. `count` is market activity, **not** a
projection — see `waiver-analysis.md`.

## Error handling

| Situation | Handling |
|---|---|
| User/league not found | `404` (or `null`/empty) — return a clear "check username vs user_id" message |
| Rate limited / block risk | `429` — back off (exponential) and retry; throttle client-side |
| No matchups/transactions yet | empty array — say data isn't available for that week yet |
| Draft not complete | picks empty/partial — don't claim a final recap |
| Player ID missing from cache | fall back to the raw id and flag a stale cache |
| Network timeout | retry with backoff; always set a timeout |
