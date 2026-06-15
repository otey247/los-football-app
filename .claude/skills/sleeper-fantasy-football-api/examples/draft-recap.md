# Example: Draft Recap

Snake startup draft recap.

## Build steps
1. `GET /league/{id}` → `draft_id`.
2. `GET /draft/{draft_id}` (type, slot_to_roster_id), `GET /draft/{draft_id}/picks`.
3. Resolve `picked_by`/`roster_id` to owners; player names from cache.

## Output

# Draft Recap — Sunday Funday Startup (2025, snake)

## First Round
| Pick | Player | Pos | Team | Drafted By |
|---:|---|---|---|---|
| 1.01 | Ja'Marr Chase | WR | CIN | mike |
| 1.02 | Bijan Robinson | RB | ATL | dana |
| ... | ... | ... | ... | ... |

## Team Draft Classes
- mike: Chase (1.01), … — built around elite WR.
- dana: Bijan (1.02), … — RB-anchored.

## Position Runs
- Picks 1.05–1.09: four straight RBs (positional run).

## Notes
- Value/reach calls would require an external ADP source (not Sleeper) — omitted.
- Draft status: complete.
