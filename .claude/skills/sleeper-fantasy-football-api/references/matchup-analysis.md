# Matchup Analysis

## Inputs

`GET /league/{id}/matchups/{week}`, plus rosters, users, cached players, and
league `scoring_settings`.

## Pairing

The matchups endpoint returns **one row per roster**. The two rows that share a
`matchup_id` are opponents. Group by `matchup_id` (see `pairMatchups` in
`templates/league-context.ts`).

```ts
const pairs = pairMatchups(matchups); // [{ matchupId, teams: [a, b] }]
```

## Bench

Bench players are derived: `bench = players − starters`.

```ts
const bench = getBenchPlayerIds(matchup); // players not in starters
```

If `players_points` is present in the payload for your league/week, use it for
exact per-player and bench totals. If it is absent, **do not** assert exact
bench points — report it as unavailable.

## What to analyze

- Starter points and matchup winner per `matchup_id`.
- Closest games and biggest blowouts (smallest/largest point gaps).
- Best-scoring bench player (a lineup mistake signal) when per-player points exist.
- Underperforming starters vs the rest of the roster.
- Injury flags on starters (`injury_status` from the player cache).

## Output

Use `templates/matchup-report.md`. Always show player names (not IDs) and owner
names (not `roster_id`), and state the week/season. If `players_points` was
missing, note it under data limitations.
