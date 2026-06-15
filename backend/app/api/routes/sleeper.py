"""API routes for Sleeper fantasy football stats."""

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.services import sleeper as svc

router = APIRouter(prefix="/sleeper", tags=["sleeper"])

_STAT_FUNCTIONS = {
    "all-play-record": svc.stat_all_play_record,
    "expected-wins": svc.stat_expected_wins,
    "luck-adjusted-standings": svc.stat_luck_adjusted_standings,
    "schedule-luck-index": svc.stat_schedule_luck_index,
    "bad-beat-tracker": svc.stat_bad_beat_tracker,
    "fraud-win-tracker": svc.stat_fraud_win_tracker,
    "points-left-on-bench": svc.stat_points_left_on_bench,
    "manager-efficiency": svc.stat_manager_efficiency,
    "optimal-lineup-score": svc.stat_optimal_lineup_score,
    "bench-blunder-award": svc.stat_bench_blunder_award,
    "dead-lineup-penalty": svc.stat_dead_lineup_penalty,
    "waiver-roi": svc.stat_waiver_roi,
    "faab-efficiency": svc.stat_faab_efficiency,
    "drop-regret-index": svc.stat_drop_regret_index,
    "free-agent-steal": svc.stat_free_agent_steal,
    "transaction-roi": svc.stat_transaction_roi,
    "draft-roi": svc.stat_draft_roi,
    "best-draft-pick": svc.stat_best_draft_pick,
    "worst-draft-pick": svc.stat_worst_draft_pick,
    "draft-capital-retention": svc.stat_draft_capital_retention,
    "trade-value": svc.stat_trade_value,
    "immediate-trade-impact": svc.stat_immediate_trade_impact,
    "trade-regret-tracker": svc.stat_trade_regret_tracker,
    "playoff-odds": svc.stat_playoff_odds,
    "dynasty-legacy-score": svc.stat_dynasty_legacy_score,
    # 2.1 Team & League Performance
    "power-ranking-trend": svc.stat_power_ranking_trend,
    "expected-vs-actual-wins": svc.stat_expected_vs_actual_wins,
    "points-for-against": svc.stat_points_for_against,
    "strength-of-schedule": svc.stat_strength_of_schedule,
    "consistency-score": svc.stat_consistency_score,
    "all-play-standings": svc.stat_all_play_standings,
    "roster-efficiency": svc.stat_roster_efficiency,
    "bench-points-ranking": svc.stat_bench_points_ranking,
    "margin-of-victory": svc.stat_margin_of_victory,
    "cumulative-points-race": svc.stat_cumulative_points_race,
}

STAT_META = [
    {"key": "all-play-record", "title": "All-Play Record", "description": "What each team's record would be if they played every other team every week.", "category": "Power Rankings"},
    {"key": "expected-wins", "title": "Expected Wins", "description": "Wins implied by weekly scoring rank instead of actual schedule.", "category": "Power Rankings"},
    {"key": "luck-adjusted-standings", "title": "Luck-Adjusted Standings", "description": "Difference between actual wins and expected wins.", "category": "Power Rankings"},
    {"key": "schedule-luck-index", "title": "Schedule Luck Index", "description": "Ranks teams by how unlucky they were based on points allowed.", "category": "Schedule Luck"},
    {"key": "bad-beat-tracker", "title": "Bad Beat Tracker", "description": "Losses where a team scored in the top half of the league.", "category": "Schedule Luck"},
    {"key": "fraud-win-tracker", "title": "Fraud Win Tracker", "description": "Wins where a team scored in the bottom half of the league.", "category": "Schedule Luck"},
    {"key": "points-left-on-bench", "title": "Points Left on Bench", "description": "Difference between actual lineup score and best possible lineup score.", "category": "Lineup Optimization"},
    {"key": "manager-efficiency", "title": "Manager Efficiency", "description": "Actual lineup score divided by optimal lineup score.", "category": "Lineup Optimization"},
    {"key": "optimal-lineup-score", "title": "Optimal Lineup Score", "description": "Best legal lineup a manager could have started.", "category": "Lineup Optimization"},
    {"key": "bench-blunder-award", "title": "Bench Blunder Award", "description": "Biggest missed opportunity from leaving points on the bench.", "category": "Weekly Awards"},
    {"key": "dead-lineup-penalty", "title": "Dead Lineup Penalty", "description": "Points lost from starting inactive or zero-point players.", "category": "Lineup Optimization"},
    {"key": "waiver-roi", "title": "Waiver ROI", "description": "Fantasy points gained from waiver or free-agent adds.", "category": "Waivers"},
    {"key": "faab-efficiency", "title": "FAAB Efficiency", "description": "Fantasy points generated per FAAB dollar spent.", "category": "Waivers"},
    {"key": "drop-regret-index", "title": "Drop Regret Index", "description": "Points scored by a player after being dropped by a manager.", "category": "Waivers"},
    {"key": "free-agent-steal", "title": "Free Agent Steal of the Year", "description": "Best post-acquisition production from a low-cost pickup.", "category": "Waivers"},
    {"key": "transaction-roi", "title": "Transaction ROI", "description": "Net value created by all adds, drops, and waiver moves.", "category": "Waivers"},
    {"key": "draft-roi", "title": "Draft ROI", "description": "Compares drafted player production against draft cost.", "category": "Draft Analysis"},
    {"key": "best-draft-pick", "title": "Best Draft Pick", "description": "Highest surplus value relative to draft slot.", "category": "Draft Analysis"},
    {"key": "worst-draft-pick", "title": "Worst Draft Pick", "description": "Lowest value relative to draft slot.", "category": "Draft Analysis"},
    {"key": "draft-capital-retention", "title": "Draft Capital Retention", "description": "Percentage of drafted players still rostered by original manager.", "category": "Draft Analysis"},
    {"key": "trade-value", "title": "Trade Value Won/Lost", "description": "Compares rest-of-season points from assets exchanged in a trade.", "category": "Trade Analysis"},
    {"key": "immediate-trade-impact", "title": "Immediate Trade Impact", "description": "Points from traded players in first 3 weeks after trade.", "category": "Trade Analysis"},
    {"key": "trade-regret-tracker", "title": "Trade Regret Tracker", "description": "Flags trades where one side clearly lost value.", "category": "Trade Analysis"},
    {"key": "playoff-odds", "title": "Playoff Odds Simulator", "description": "Monte Carlo simulation of remaining season and playoff chances.", "category": "Playoff"},
    {"key": "dynasty-legacy-score", "title": "Dynasty Legacy Score", "description": "Season composite score combining wins, points, playoffs, efficiency, and transactions.", "category": "Playoff"},
    {"key": "power-ranking-trend", "title": "Power Ranking Trend", "description": "Each team's power-ranking movement week over week as a trend line.", "category": "Team & League Performance", "chart": "rank-trend"},
    {"key": "expected-vs-actual-wins", "title": "Expected vs Actual Wins", "description": "Luck-adjusted record: wins implied by weekly scoring rank vs real wins.", "category": "Team & League Performance"},
    {"key": "points-for-against", "title": "Points For / Against", "description": "Scatter of points scored vs points allowed with quadrant labeling.", "category": "Team & League Performance", "chart": "scatter"},
    {"key": "strength-of-schedule", "title": "Strength of Schedule", "description": "Schedule difficulty already played and still remaining, per team.", "category": "Team & League Performance"},
    {"key": "consistency-score", "title": "Consistency / Volatility", "description": "Standard deviation of weekly scores with floor and ceiling.", "category": "Team & League Performance"},
    {"key": "all-play-standings", "title": "All-Play Standings", "description": "Record if every team played every other team each week, with win %.", "category": "Team & League Performance"},
    {"key": "roster-efficiency", "title": "Roster Efficiency", "description": "Points scored vs optimal lineup points, tracked per week.", "category": "Team & League Performance"},
    {"key": "bench-points-ranking", "title": "Bench Points Left on the Table", "description": "Optimal-minus-actual points left on the bench, ranked league-wide.", "category": "Team & League Performance"},
    {"key": "margin-of-victory", "title": "Margin of Victory", "description": "Blowout and nailbiter distribution from weekly scoring margins.", "category": "Team & League Performance", "chart": "margin"},
    {"key": "cumulative-points-race", "title": "Cumulative Points Race", "description": "Running points total over the full season as a race line chart.", "category": "Team & League Performance", "chart": "points-race"},
]


def _current_week(league_id: str) -> int:
    """Return the current NFL week, clamped to the league's completed weeks."""
    try:
        nfl_state = svc.get_nfl_state()
        week = int(nfl_state.get("week") or 1)
        league = svc.get_league(league_id)
        last_scored = int(league.get("settings", {}).get("last_scored_leg", week))
        return min(week, last_scored)
    except Exception:
        return 1


def _requested_week(league_id: str, week: int | None) -> int:
    current = _current_week(league_id)
    return min(week, current) if week is not None else current


def _handle_sleeper_error(exc: Exception, league_id: str = "") -> None:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
        detail = f"League '{league_id}' not found on Sleeper" if league_id else "League not found on Sleeper"
        raise HTTPException(status_code=404, detail=detail)
    raise HTTPException(status_code=502, detail=f"Sleeper API error: {exc}")


@router.get("/meta")
def get_stats_meta() -> list[dict[str, str]]:
    """Return metadata (key, title, description, category) for every stat."""
    return STAT_META


@router.get("/league-info")
def get_league_info(
    league_id: str = Query(default=""),
) -> Any:
    """Return basic league information from Sleeper."""
    lid = league_id or settings.SLEEPER_LEAGUE_ID
    if not lid:
        raise HTTPException(status_code=400, detail="No league_id provided and SLEEPER_LEAGUE_ID is not configured")
    try:
        league = svc.get_league(lid)
        users = svc.get_users(lid)
        rosters = svc.get_rosters(lid)
        nfl_state = svc.get_nfl_state()
        return {
            "league": league,
            "users": users,
            "rosters": rosters,
            "nfl_state": nfl_state,
        }
    except Exception as exc:
        _handle_sleeper_error(exc, lid)


@router.get("/stats/{stat_key}")
def get_stat(
    stat_key: str,
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    """
    Calculate and return a specific stat.
    stat_key must be one of the 25 supported stats.
    """
    fn = _STAT_FUNCTIONS.get(stat_key)
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
    except Exception as exc:
        _handle_sleeper_error(exc, lid)
