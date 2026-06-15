# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

**Los Football** — a full-stack fantasy football web app for commissioner
workflows, league storytelling, and Sleeper-powered analytics. It serves
advanced fantasy stat cards (power rankings, schedule luck, lineup optimization,
waivers, draft/trade analysis, playoff outlook, weekly awards), a commissioner
blog with a super-admin CMS, and authenticated dashboards.

## Tech stack

- **Backend:** FastAPI, SQLModel, PostgreSQL, Alembic, Pydantic (Python ≥3.10, `uv`)
- **Frontend:** React, TypeScript, Vite, TanStack Router/Query, Tailwind, shadcn/ui (Bun)
- **Integration:** Sleeper fantasy football API (read-only, no token)
- **Tooling:** Docker Compose, Pytest, Playwright, Ruff, MyPy, Biome

## Repository layout

```
backend/
  app/
    api/routes/          # FastAPI routes (incl. sleeper.py, blog.py, users.py)
    services/sleeper.py  # Sleeper API client + in-memory TTL cache
    core/config.py       # settings incl. SLEEPER_LEAGUE_ID
    models.py, crud.py   # SQLModel models and CRUD
    alembic/             # DB migrations
  tests/
frontend/
  src/
    lib/footballApi.ts   # frontend Sleeper/blog API client + types
    routes/_layout/fantasy-stats.tsx
.claude/skills/          # Claude Code skills (see below)
```

## Common commands

Full stack: `docker compose up --build` → frontend `:5173`, API `:8000`, docs `:8000/docs`.

Backend (`cd backend`):
```bash
uv sync
uv run fastapi dev app/main.py
uv run pytest
uv run ruff check
uv run mypy .
```

Frontend (`cd frontend`):
```bash
bun install
bun run dev
bun run lint
bun run build
bun run test   # Playwright E2E; needs services up + FIRST_SUPERUSER[_PASSWORD]
```

## Conventions

- Backend is `mypy --strict` and Ruff-clean; keep new code typed and linted.
- Schema changes go through Alembic migrations in `backend/app/alembic/versions/`.
- Frontend API types live in `frontend/src/lib/footballApi.ts`; the generated
  client lives in `frontend/src/client/` (don't hand-edit generated files).
- Match the style of surrounding code; run the linters above before considering a change done.

## Sleeper API work — use the skill

This app is Sleeper-powered. **Whenever you build, review, debug, or document
anything touching the Sleeper API** (users, leagues, rosters, matchups, drafts,
transactions, traded picks, NFL state, players, trending adds/drops, or any of
the stat-card analytics), use the **`sleeper-fantasy-football-api`** skill in
[`.claude/skills/sleeper-fantasy-football-api/`](.claude/skills/sleeper-fantasy-football-api/).

It documents the endpoint catalog, caching strategy, league-context model, and
the matchup/waiver/trade/dynasty/draft analysis recipes, plus the non-obvious
rules: store `user_id` not username; cache `/players/nfl` (the existing
`services/sleeper.py` uses a 1-hour TTL, well within Sleeper's "≤ once/day"
guidance for the large player payload); stay under ~1,000 calls/min; pair
matchups by `matchup_id`; derive bench as `players − starters`; and always apply
league scoring settings to any recommendation.

Existing integration points to extend rather than reinvent:
- `backend/app/services/sleeper.py` — the cached client.
- `backend/app/api/routes/sleeper.py` — the API routes.
- `frontend/src/lib/footballApi.ts` — frontend types and calls.
