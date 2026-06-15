"""API routes for player-level Sleeper analytics (TODO 2.2, #51–58)."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.api.routes.sleeper import _handle_sleeper_error, _requested_week
from app.core.config import settings
from app.services import player_analytics as pa

router = APIRouter(prefix="/player-analytics", tags=["player-analytics"])

_PLAYER_STAT_FUNCTIONS = {
    "player-consistency": pa.player_consistency,
    "positional-breakdown": pa.positional_breakdown,
    "usage-trends": pa.usage_trends,
    "points-above-replacement": pa.points_above_replacement,
    "buy-low-sell-high": pa.buy_low_sell_high,
    "injury-impact": pa.injury_impact,
    "rookie-breakout-watch": pa.rookie_breakout_watch,
    "streaming-tracker": pa.streaming_tracker,
}

PLAYER_STAT_META = [
    {"key": "player-consistency", "title": "Consistency vs Boom/Bust", "description": "Floor, ceiling, and volatility profile that classifies each player as consistent or boom/bust.", "category": "Player Profiles"},
    {"key": "positional-breakdown", "title": "Positional Scoring Breakdown", "description": "Share of each team's starting points coming from QB, RB, WR, TE, K, DEF, and FLEX.", "category": "Team Composition"},
    {"key": "usage-trends", "title": "Usage Trends", "description": "Touches, targets, snap share, and recent-vs-early usage trend from Sleeper player stats.", "category": "Usage"},
    {"key": "points-above-replacement", "title": "Points Above Replacement", "description": "Season points above a positional replacement baseline (VOR/VORP).", "category": "Player Value"},
    {"key": "buy-low-sell-high", "title": "Buy-Low / Sell-High", "description": "Flags players whose recent production diverges sharply from their season pace.", "category": "Player Value"},
    {"key": "injury-impact", "title": "Injury Impact", "description": "Current injury exposure and estimated points lost to missed games, per roster.", "category": "Availability"},
    {"key": "rookie-breakout-watch", "title": "Rookie / Breakout Watch", "description": "Rookies and young players whose production is accelerating week over week.", "category": "Emerging"},
    {"key": "streaming-tracker", "title": "Streaming Value Tracker", "description": "Ranks QB, K, and DEF options for matchup-based streaming by recent form.", "category": "Streaming"},
]


@router.get("/meta")
def get_player_stats_meta() -> list[dict[str, str]]:
    """Return metadata (key, title, description, category) for player analytics."""
    return PLAYER_STAT_META


@router.get("/stats/{stat_key}")
def get_player_stat(
    stat_key: str,
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """Calculate and return a specific player-analytics stat."""
    fn = _PLAYER_STAT_FUNCTIONS.get(stat_key)
    if fn is None:
        raise HTTPException(status_code=404, detail=f"Unknown stat: {stat_key}")
    lid = league_id or settings.SLEEPER_LEAGUE_ID
    if not lid:
        raise HTTPException(
            status_code=400,
            detail="No league_id provided and SLEEPER_LEAGUE_ID is not configured",
        )
    current = _requested_week(lid, week)
    try:
        return fn(lid, current)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)
