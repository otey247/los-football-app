# Sleeper Fantasy API Review Checklist

## API Usage
- [ ] Uses official base URL `https://api.sleeper.app/v1`
- [ ] Stores `user_id` instead of relying on username
- [ ] Caches `players/nfl` daily; never per-request
- [ ] Handles current NFL state from `/state/nfl` (not hardcoded week)
- [ ] Handles missing week/matchup data
- [ ] Handles empty transactions
- [ ] Handles missing player IDs (cache miss)

## League Context
- [ ] Fetches league metadata, rosters, and users
- [ ] Maps `roster_id` to owner (via `owner_id`)
- [ ] Reads scoring settings and roster positions

## Analysis
- [ ] Converts player IDs to names in output
- [ ] Pairs matchups by `matchup_id`
- [ ] Derives bench correctly (`players − starters`)
- [ ] Filters available players by current rosters
- [ ] Does not overstate recommendations; states confidence + assumptions
- [ ] Documents limitations (no projections/news from Sleeper)

## Reliability
- [ ] Uses timeouts
- [ ] Uses retries/backoff (incl. 429)
- [ ] Uses cache and deduplicates per-request calls
- [ ] Avoids excessive API calls
- [ ] Uses fixtures for tests (no live API in CI)

## Product
- [ ] User-facing errors are clear
- [ ] Recommendations are league-aware (scoring/roster)
- [ ] Dynasty/redraft/keeper context respected
- [ ] Data freshness is visible
