# Dynasty Pick Tracking

## Inputs

`GET /league/{id}/traded_picks` (future picks across seasons),
`GET /draft/{draft_id}/traded_picks` (picks moved within a specific draft),
plus rosters and users for owner names.

## Pick ownership fields

Each traded pick has:

- `season` — the season the pick is for.
- `round` — the round.
- `owner_id` — the **original** owner's roster_id.
- `previous_owner_id` — who held it before the latest trade.
- `roster_id` — the **current** owner's roster_id.

To present "who owns the 2026 1st that originally belonged to Team X," map all
three roster_ids to owner display names via the league context.

## Output

- Current pick ownership table (season × round × current owner).
- Original owner and previous owner for each traded pick.
- A contender/rebuilder pick map (who is accumulating vs shedding future capital).
- Future-pick exposure per team (how many of their own picks they've traded away).

Always resolve roster_ids to owner names and state the season each pick belongs to.
