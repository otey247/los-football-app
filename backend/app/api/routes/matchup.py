"""API routes for matchup & win-probability analytics (TODO #59-#66)."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.routes.sleeper import (
    _current_week,
    _handle_sleeper_error,
    _requested_week,
)
from app.core.config import settings
from app.services import matchup as svc

router = APIRouter(prefix="/matchup", tags=["matchup"])


def _resolve_league(league_id: str) -> str:
    lid = league_id or settings.SLEEPER_LEAGUE_ID
    if not lid:
        raise HTTPException(
            status_code=400,
            detail="No league_id provided and SLEEPER_LEAGUE_ID is not configured",
        )
    return lid


def _upcoming_week(league_id: str, week: int | None) -> int:
    """Default to the week after the latest completed week (clamped to 18)."""
    if week is not None:
        return week
    return min(_current_week(league_id) + 1, 18)


@router.get("/meta")
def get_matchup_meta() -> dict[str, Any]:
    """Describe the available matchup & win-probability features."""
    return {"features": svc.FEATURES}


@router.get("/win-probability")
def get_win_probability(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#59 Pre-game win probability for each matchup in the (upcoming) week."""
    lid = _resolve_league(league_id)
    wk = _upcoming_week(lid, week)
    try:
        return svc.pregame_win_probability(lid, wk)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


@router.get("/live-win-probability")
def get_live_win_probability(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#60 Live in-game win probability for the current week."""
    lid = _resolve_league(league_id)
    wk = _requested_week(lid, week)
    try:
        return svc.live_win_probability(lid, wk)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


@router.get("/projection-accuracy")
def get_projection_accuracy(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#61 Projected vs actual score accuracy over the season."""
    lid = _resolve_league(league_id)
    wk = _requested_week(lid, week)
    try:
        return svc.projection_accuracy(lid, wk)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


@router.get("/lineup-options")
def get_lineup_options(
    roster_id: int = Query(...),
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#62 Starters & bench (with projections) for the what-if selector."""
    lid = _resolve_league(league_id)
    wk = _upcoming_week(lid, week)
    try:
        return svc.lineup_options(lid, roster_id, wk)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


class WhatIfRequest(BaseModel):
    league_id: str = ""
    roster_id: int
    week: int | None = None
    swap_out: str
    swap_in: str


@router.post("/what-if")
def post_what_if(body: WhatIfRequest) -> Any:
    """#62 Project the delta from swapping a starter for a bench player."""
    lid = _resolve_league(body.league_id)
    wk = _upcoming_week(lid, body.week)
    try:
        return svc.what_if(lid, body.roster_id, wk, body.swap_out, body.swap_in)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


@router.get("/clinch-scenarios")
def get_clinch_scenarios(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#63 Tiebreaker, clinch and elimination scenario calculator."""
    lid = _resolve_league(league_id)
    wk = _requested_week(lid, week)
    try:
        return svc.clinch_scenarios(lid, wk)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


@router.get("/season-simulation")
def get_season_simulation(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
    simulations: int = Query(default=2000, ge=100, le=20000),
) -> Any:
    """#64 Monte Carlo season simulation for projected final standings."""
    lid = _resolve_league(league_id)
    wk = _requested_week(lid, week)
    try:
        return svc.season_simulation(lid, wk, simulations)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


@router.get("/playoff-odds")
def get_playoff_odds(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
    simulations: int = Query(default=2000, ge=100, le=20000),
) -> Any:
    """#65 Playoff probability per team, updated weekly."""
    lid = _resolve_league(league_id)
    wk = _requested_week(lid, week)
    try:
        return svc.playoff_odds(lid, wk, simulations)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


@router.get("/championship-odds")
def get_championship_odds(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
    simulations: int = Query(default=2000, ge=100, le=20000),
) -> Any:
    """#66 Championship odds and projected bracket paths."""
    lid = _resolve_league(league_id)
    wk = _requested_week(lid, week)
    try:
        return svc.championship_odds(lid, wk, simulations)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)
