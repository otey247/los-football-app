# Player Cache Strategy

`GET /players/nfl` returns the entire NFL player dictionary — a large payload.
Sleeper explicitly recommends saving it on your own servers and **not** calling
it more than once per day. Treat it as a daily batch job, never a per-request call.

## What to cache

Keyed by `player_id`, keep at least:

```
player_id, full_name, first_name, last_name, team, position,
fantasy_positions, status, injury_status, depth_chart_position,
years_exp, age, search_rank
```

This is enough to resolve names and enrich every other endpoint (rosters,
matchups, transactions, trending, drafts) which all return only player IDs.

## Suggested cache durations

| Data | Suggested TTL |
|---|---|
| All players (`/players/nfl`) | 24 hours |
| User profile | 1–24 hours |
| League metadata | 15 min – 24 h (shorter in active season) |
| Rosters | 1–15 min during active season |
| League users | 1–24 hours |
| Matchups | 30 s – 5 min during games |
| Transactions | 1–15 min |
| Traded picks | 15 min – 24 h |
| Draft picks | static once draft complete |
| NFL state | 5–30 min |

## Refresh pattern

1. Scheduled daily job calls `/players/nfl` once.
2. Upsert into a store (`sleeper_player_cache` table, Redis, or a JSON file).
3. Stamp `updated_at`.
4. All lookups read the cache; on a miss, fall back to the raw `player_id` in
   output and surface "player cache is stale — refresh and retry."

### Reference table (if persisting in SQL)

```sql
CREATE TABLE sleeper_player_cache (
  player_id  TEXT PRIMARY KEY,
  player_json JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## Rules

- **Do** cache large/static responses, deduplicate calls per request, batch
  analysis around a single league-context fetch, retry transient failures with
  backoff, and set timeouts.
- **Don't** call `/players/nfl` on page load, loop weeks with no cache, or poll
  matchups during live games without throttling.
- For CI, store a **subset** of players as a fixture — never the full payload.
