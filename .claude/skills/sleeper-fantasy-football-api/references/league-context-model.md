# League Context Model

Always build a normalized league context **before** any analysis. It bundles
everything the analysis recipes need and prevents re-deriving ID maps or
re-fetching the same data.

## Fetch order

1. `GET /league/{league_id}` — metadata, scoring, roster positions, `draft_id`.
2. `GET /league/{league_id}/users` — display names, avatars, team names.
3. `GET /league/{league_id}/rosters` — rosters, records, points.
4. `GET /state/nfl` — current season/week (don't hardcode).
5. Player dictionary from the **daily cache** (not a live call).

Then fetch matchups, transactions, drafts, or trending only as the use case needs.

## Shape

```ts
type SleeperLeagueContext = {
  league: any;                              // /league/{id}
  users: any[];                             // /league/{id}/users
  rosters: any[];                           // /league/{id}/rosters
  playersById: Record<string, any>;        // from daily cache
  usersById: Record<string, any>;          // user_id -> user
  rostersById: Record<number, any>;         // roster_id -> roster
  ownersByRosterId: Record<number, any>;    // roster_id -> user (owner)
  currentState: any;                        // /state/nfl
};
```

Build it with `buildLeagueContext` in `templates/league-context.ts`.

## Helper maps to derive

- `players_by_id` — name + metadata resolution.
- `users_by_id` — `user_id → user`.
- `rosters_by_id` — `roster_id → roster`.
- `owners_by_roster_id` — `roster_id → owning user` (via `roster.owner_id`).
- `roster_id_by_owner_id` — reverse lookup.
- `matchups_by_matchup_id` — pair opponents (per use case).
- `transactions_by_type` — group `free_agent` / `waiver` / `trade`.

## Capture before analysis

Season, `league_id`, user (`user_id`), week, scoring format, roster settings, and
whether the league is dynasty / keeper / redraft. These determine which recipe and
which caveats apply. If any required value is missing, stop and ask (see SKILL.md
"Stop Conditions").
