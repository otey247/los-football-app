"""API routes for the coaching surface: actionable, predictive & social insights.

Covers TODO items 92-100:
* #92 start/sit, #93 waivers, #94 trade targets, #95 lineup nudges
* #96 rest-of-season outlook, #97 must-win flags, #98 regression warnings
* #99 rivalry / trash-talk index, #100 power-ranking committee (vote + blend)
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.api.routes.sleeper import _handle_sleeper_error, _requested_week
from app.core.config import settings
from app.models import CommitteeBallot, PowerRankingVote
from app.services import recommendations as rec

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _resolve_league(league_id: str) -> str:
    lid = league_id or settings.SLEEPER_LEAGUE_ID
    if not lid:
        raise HTTPException(
            status_code=400,
            detail="No league_id provided and SLEEPER_LEAGUE_ID is not configured",
        )
    return lid


@router.get("/meta")
def get_meta() -> dict[str, Any]:
    """Describe the available coaching features."""
    return {
        "features": [
            {"key": "start-sit", "title": "Start/Sit", "per_team": True,
             "description": "Optimal lineup with confidence-rated start/sit calls."},
            {"key": "waivers", "title": "Waiver Pickups", "per_team": True,
             "description": "Available trending adds ranked by need + opportunity."},
            {"key": "trade-targets", "title": "Trade Targets", "per_team": True,
             "description": "Partners deep where you're thin (and vice-versa)."},
            {"key": "lineup-nudges", "title": "Lineup Nudges", "per_team": False,
             "description": "Pre-lock alerts for risky or sub-optimal lineups."},
            {"key": "rest-of-season", "title": "Rest-of-Season Outlook", "per_team": False,
             "description": "Remaining schedule strength and swing matchups."},
            {"key": "must-win", "title": "Must-Win Flags", "per_team": False,
             "description": "Games that most swing each team's playoff odds."},
            {"key": "regression", "title": "Regression Warnings", "per_team": False,
             "description": "Teams over/underperforming their underlying scoring."},
            {"key": "rivalries", "title": "Rivalry Index", "per_team": False,
             "description": "Head-to-head grudge matches and trash talk."},
            {"key": "committee", "title": "Committee Rankings", "per_team": False,
             "description": "Members vote; we blend the crowd with the model."},
        ],
    }


@router.get("/teams")
def get_teams(league_id: str = Query(default="")) -> Any:
    """List teams (roster_id + name) for the per-team feature pickers."""
    lid = _resolve_league(league_id)
    try:
        return rec.list_teams(lid)
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


def _team_feature(
    fn: Any, league_id: str, roster_id: int, week: int | None
) -> Any:
    lid = _resolve_league(league_id)
    wk = _requested_week(lid, week)
    try:
        return fn(lid, roster_id, wk)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


def _league_feature(fn: Any, league_id: str, week: int | None) -> Any:
    lid = _resolve_league(league_id)
    wk = _requested_week(lid, week)
    try:
        return fn(lid, wk)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


@router.get("/start-sit")
def get_start_sit(
    roster_id: int = Query(...),
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#92 Start/sit recommendations for one team."""
    return _team_feature(rec.start_sit_recommendations, league_id, roster_id, week)


@router.get("/waivers")
def get_waivers(
    roster_id: int = Query(...),
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#93 Waiver pickup suggestions for one team."""
    return _team_feature(rec.waiver_suggestions, league_id, roster_id, week)


@router.get("/trade-targets")
def get_trade_targets(
    roster_id: int = Query(...),
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#94 Trade target suggestions for one team."""
    return _team_feature(rec.trade_targets, league_id, roster_id, week)


@router.get("/lineup-nudges")
def get_lineup_nudges(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#95 Optimal-lineup nudges across the league."""
    return _league_feature(rec.lineup_nudges, league_id, week)


@router.get("/rest-of-season")
def get_rest_of_season(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#96 Rest-of-season outlook with swing matchups."""
    return _league_feature(rec.rest_of_season_outlook, league_id, week)


@router.get("/must-win")
def get_must_win(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#97 Must-win game flags."""
    return _league_feature(rec.must_win_flags, league_id, week)


@router.get("/regression")
def get_regression(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#98 Regression / luck warnings."""
    return _league_feature(rec.regression_warnings, league_id, week)


@router.get("/rivalries")
def get_rivalries(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#99 Rivalry / trash-talk index."""
    return _league_feature(rec.rivalry_index, league_id, week)


# ---------------------------------------------------------------------------
# #100 Power-ranking committee mode
# ---------------------------------------------------------------------------


def _blend_committee(
    session: SessionDep, league_id: str, week: int
) -> dict[str, Any]:
    model = rec.power_ranking_model(league_id, week)

    votes = session.exec(
        select(PowerRankingVote).where(
            PowerRankingVote.league_id == league_id,
            PowerRankingVote.week == week,
        )
    ).all()

    voters = {v.voter_id for v in votes}
    # Average crowd rank per roster.
    crowd_ranks: dict[int, list[int]] = {}
    for v in votes:
        crowd_ranks.setdefault(v.roster_id, []).append(v.rank)
    crowd_avg = {
        rid: sum(ranks) / len(ranks) for rid, ranks in crowd_ranks.items()
    }
    # Convert average crowd rank into a 1..N crowd ranking.
    crowd_order = sorted(crowd_avg, key=lambda rid: crowd_avg[rid])
    crowd_rank = {rid: i + 1 for i, rid in enumerate(crowd_order)}

    rows: list[dict[str, Any]] = []
    for row in model:
        rid = row["roster_id"]
        m_rank = row["model_rank"]
        c_rank = crowd_rank.get(rid)
        if c_rank is not None:
            blended_score = (m_rank + c_rank) / 2
            disagreement = m_rank - c_rank
        else:
            blended_score = float(m_rank)
            disagreement = 0
        rows.append(
            {
                **row,
                "crowd_rank": c_rank,
                "crowd_avg_rank": round(crowd_avg[rid], 2)
                if rid in crowd_avg
                else None,
                "disagreement": disagreement,
                "_blend": blended_score,
            }
        )

    rows.sort(key=lambda r: (r["_blend"], r["model_rank"]))
    for i, row in enumerate(rows, start=1):
        row["blended_rank"] = i
        del row["_blend"]

    return {
        "week": week,
        "voter_count": len(voters),
        "has_votes": bool(voters),
        "rankings": rows,
        "model": model,
        "note": (
            "Blended rank averages the model rank with the crowd's average rank. "
            "Disagreement = model rank − crowd rank (positive = crowd is higher "
            "on the team than the model)."
        ),
    }


@router.get("/committee")
def get_committee(
    *,
    session: SessionDep,
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """#100 Blended model + crowd power rankings with disagreement."""
    lid = _resolve_league(league_id)
    wk = _requested_week(lid, week)
    try:
        return _blend_committee(session, lid, wk)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


@router.post("/committee/vote")
def submit_committee_vote(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    body: CommitteeBallot,
) -> Any:
    """#100 Submit (or replace) the current user's power-ranking ballot."""
    lid = _resolve_league(body.league_id)
    wk = _requested_week(lid, body.week)
    if not body.rankings:
        raise HTTPException(status_code=400, detail="Ballot cannot be empty")

    ranks = [item.rank for item in body.rankings]
    if len(set(ranks)) != len(ranks):
        raise HTTPException(status_code=400, detail="Ranks must be unique")
    roster_ids = [item.roster_id for item in body.rankings]
    if len(set(roster_ids)) != len(roster_ids):
        raise HTTPException(status_code=400, detail="Each team may appear once")

    # Replace any prior ballot from this voter for this league/week.
    prior = session.exec(
        select(PowerRankingVote).where(
            PowerRankingVote.league_id == lid,
            PowerRankingVote.week == wk,
            PowerRankingVote.voter_id == current_user.id,
        )
    ).all()
    for vote in prior:
        session.delete(vote)
    for item in body.rankings:
        session.add(
            PowerRankingVote(
                league_id=lid,
                week=wk,
                voter_id=current_user.id,
                roster_id=item.roster_id,
                rank=item.rank,
            )
        )
    session.commit()
    return _blend_committee(session, lid, wk)
