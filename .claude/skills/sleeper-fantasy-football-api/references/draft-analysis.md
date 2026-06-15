# Draft Analysis / Recap

## Inputs

`GET /draft/{draft_id}` (metadata: `type`, `settings`, `draft_order`,
`slot_to_roster_id`), `GET /draft/{draft_id}/picks`, plus league, users,
rosters, and cached players. Get `draft_id` from `/league/{id}` or
`/league/{id}/drafts`.

## Pick fields

Each pick: `player_id`, `picked_by` (user_id), `roster_id`, `round`, `pick_no`
(overall), `draft_slot`, and a `metadata` block (name, position, team, etc.).

## What to produce

- Pick-by-pick recap (overall pick → player → drafting team).
- Per-team draft classes grouped by `roster_id`/`picked_by`.
- Position runs (clusters of same-position picks across consecutive selections).
- Value picks and reaches — only if you bring an external ADP/ranking source, and
  label it as such (Sleeper provides no rankings/projections).
- Rookie / dynasty framing for startup or rookie drafts.

## Notes

- For auction drafts, picks include amount in `metadata` — surface spend per team.
- If `status` is not `complete`, the recap is partial; say so.
- Map `picked_by`/`roster_id` to owner names; show player names, not IDs.
