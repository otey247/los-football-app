# Testing & Fixtures

## Unit tests (no network)

Test the pure logic:

- Endpoint path construction.
- Player name resolution (hit, miss → falls back to id).
- roster/user mapping (`owners_by_roster_id`, reverse lookup).
- Matchup pairing by `matchup_id`.
- Bench derivation (`players − starters`).
- Trending availability filtering (rostered removed, position filter).
- Transaction parsing (adds/drops/trade/FAAB).
- Error handling (404, 429, timeout, malformed JSON, cache miss).

## Integration tests (mocked HTTP)

Mock the HTTP layer and assert the client calls the right paths/params for:
user, league, rosters, users, matchups, transactions, players cache, trending.

## Golden fixtures

Save trimmed sample responses for: league, users, rosters, matchups,
transactions, traded picks, a **players subset**, trending add/drop, draft picks.

## Avoid

- Calling the live Sleeper API in CI.
- Depending on a private league that may change between runs.
- Committing the full `/players/nfl` payload — subset or compress it.
