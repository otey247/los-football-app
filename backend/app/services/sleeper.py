"""Sleeper Fantasy Football API service with in-memory caching.

Besides wrapping the read-only Sleeper endpoints, this module is lightly
instrumented so the reporting layer can surface cache hit-rates, request
volume (to stay under Sleeper's ~1,000 calls/minute guidance) and per-endpoint
freshness/health (see :func:`get_cache_metrics` and :func:`get_endpoint_health`).
"""

import contextvars
import re
import threading
import time
from collections import OrderedDict, deque
from typing import Any

import httpx

SLEEPER_BASE_URL = "https://api.sleeper.app/v1"
# Cache TTL in seconds: player list gets a long TTL; matchups/rosters get shorter ones
_CACHE: OrderedDict[str, tuple[float, Any]] = OrderedDict()
_PLAYERS_TTL = 3600  # 1 hour – Sleeper recommends calling /players sparingly
_DEFAULT_TTL = 300   # 5 minutes
_MAX_CACHE_SIZE = 1024

# Sleeper publishes a soft limit of roughly 1,000 API calls per minute.
RATE_LIMIT_PER_MINUTE = 1000

# ---------------------------------------------------------------------------
# Instrumentation (cache + rate-limit + freshness analytics)
# ---------------------------------------------------------------------------
_metrics_lock = threading.Lock()
_metrics = {"hits": 0, "misses": 0, "errors": 0}
# Monotonic timestamps of outbound network calls, for a rolling per-minute rate.
_call_times: deque[float] = deque(maxlen=4096)
# Per-endpoint health: label -> {success_count, error_count, last_success, last_error, last_error_message}
_endpoint_state: dict[str, dict[str, Any]] = {}


def _endpoint_label(url: str) -> str:
    """Map a Sleeper URL to a coarse, ID-free label for analytics grouping."""
    path = url.replace(SLEEPER_BASE_URL, "")
    rules: list[tuple[str, str]] = [
        (r"^/league/[^/]+/matchups/\d+", "matchups"),
        (r"^/league/[^/]+/transactions/\d+", "transactions"),
        (r"^/league/[^/]+/rosters", "rosters"),
        (r"^/league/[^/]+/users", "users"),
        (r"^/league/[^/]+/drafts", "drafts"),
        (r"^/league/[^/]+/traded_picks", "traded_picks"),
        (r"^/league/[^/]+/winners_bracket", "winners_bracket"),
        (r"^/league/[^/]+/losers_bracket", "losers_bracket"),
        (r"^/league/[^/]+$", "league"),
        (r"^/draft/[^/]+/picks", "draft_picks"),
        (r"^/players/nfl", "players"),
        (r"^/stats/nfl", "player_stats"),
        (r"^/state/nfl", "nfl_state"),
        (r"^/user/[^/]+/leagues", "user_leagues"),
        (r"^/user/", "user"),
    ]
    for pattern, label in rules:
        if re.match(pattern, path):
            return label
    return "other"


def _record_call(label: str, *, error: bool, message: str = "") -> None:
    now_wall = time.time()
    with _metrics_lock:
        _call_times.append(time.monotonic())
        state = _endpoint_state.setdefault(
            label,
            {
                "success_count": 0,
                "error_count": 0,
                "last_success": None,
                "last_error": None,
                "last_error_message": None,
            },
        )
        if error:
            _metrics["errors"] += 1
            state["error_count"] += 1
            state["last_error"] = now_wall
            state["last_error_message"] = message[:300]
        else:
            state["success_count"] += 1
            state["last_success"] = now_wall


def _purge_expired(now: float) -> None:
    """Remove expired cache entries."""
    expired_urls = [
        cached_url
        for cached_url, (expires_at, _) in _CACHE.items()
        if expires_at <= now
    ]
    for cached_url in expired_urls:
        _CACHE.pop(cached_url, None)


def _get(url: str, ttl: int = _DEFAULT_TTL) -> Any:
    """Fetch *url* from Sleeper API, returning a cached response when fresh."""
    now = time.monotonic()
    _purge_expired(now)

    if url in _CACHE:
        expires_at, data = _CACHE[url]
        if now < expires_at:
            _CACHE.move_to_end(url)
            with _metrics_lock:
                _metrics["hits"] += 1
            return data
        _CACHE.pop(url, None)

    with _metrics_lock:
        _metrics["misses"] += 1
    label = _endpoint_label(url)
    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:  # noqa: BLE001 - record then re-raise for callers
        _record_call(label, error=True, message=str(exc))
        raise
    _record_call(label, error=False)

    _CACHE[url] = (now + ttl, data)
    _CACHE.move_to_end(url)
    if len(_CACHE) > _MAX_CACHE_SIZE:
        _CACHE.popitem(last=False)
    return data


def get_cache_metrics() -> dict[str, Any]:
    """Cache hit-rate and rolling request volume for the analytics dashboard."""
    cutoff = time.monotonic() - 60
    with _metrics_lock:
        hits = _metrics["hits"]
        misses = _metrics["misses"]
        errors = _metrics["errors"]
        calls_last_minute = sum(1 for t in _call_times if t >= cutoff)
    total_lookups = hits + misses
    hit_rate = round(hits / total_lookups * 100, 1) if total_lookups else 0.0
    headroom = max(0.0, RATE_LIMIT_PER_MINUTE - calls_last_minute)
    return {
        "cache_entries": len(_CACHE),
        "max_cache_size": _MAX_CACHE_SIZE,
        "hits": hits,
        "misses": misses,
        "errors": errors,
        "total_lookups": total_lookups,
        "hit_rate_pct": hit_rate,
        "network_calls": misses + errors,
        "calls_last_minute": calls_last_minute,
        "rate_limit_per_minute": RATE_LIMIT_PER_MINUTE,
        "rate_limit_used_pct": round(
            calls_last_minute / RATE_LIMIT_PER_MINUTE * 100, 1
        ),
        "rate_limit_headroom": int(headroom),
    }


def get_endpoint_health() -> list[dict[str, Any]]:
    """Per-endpoint success/error counts and age of the last successful fetch."""
    now_wall = time.time()
    rows: list[dict[str, Any]] = []
    with _metrics_lock:
        items = [(label, dict(state)) for label, state in _endpoint_state.items()]
    for label, state in items:
        last_success = state["last_success"]
        last_error = state["last_error"]
        rows.append(
            {
                "endpoint": label,
                "success_count": state["success_count"],
                "error_count": state["error_count"],
                "last_success_age_seconds": (
                    round(now_wall - last_success, 1)
                    if last_success is not None
                    else None
                ),
                "last_error_age_seconds": (
                    round(now_wall - last_error, 1)
                    if last_error is not None
                    else None
                ),
                "last_error_message": state["last_error_message"],
            }
        )
    rows.sort(key=lambda r: r["endpoint"])
    return rows


def reset_metrics() -> None:
    """Clear all instrumentation counters (used by tests)."""
    with _metrics_lock:
        _metrics.update({"hits": 0, "misses": 0, "errors": 0})
        _call_times.clear()
        _endpoint_state.clear()


# ---------------------------------------------------------------------------
# Low-level API helpers
# ---------------------------------------------------------------------------

def get_league(league_id: str) -> dict[str, Any]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}")


def get_users(league_id: str) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}/users")


def get_rosters(league_id: str) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}/rosters")


def get_matchups(league_id: str, week: int) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}/matchups/{week}")


def get_transactions(league_id: str, week: int) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}/transactions/{week}")


def get_drafts(league_id: str) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}/drafts")


def get_draft_picks(draft_id: str) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/draft/{draft_id}/picks")


def get_traded_picks(league_id: str) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}/traded_picks")


def get_winners_bracket(league_id: str) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}/winners_bracket")


def get_losers_bracket(league_id: str) -> list[dict[str, Any]]:
    return _get(f"{SLEEPER_BASE_URL}/league/{league_id}/losers_bracket")


def get_nfl_players() -> dict[str, Any]:
    return _get(f"{SLEEPER_BASE_URL}/players/nfl", ttl=_PLAYERS_TTL)


def get_player_stats(season: str, week: int, season_type: str = "regular") -> dict[str, Any]:
    return _get(
        f"{SLEEPER_BASE_URL}/stats/nfl/player/{season_type}/{season}/{week}",
        ttl=_DEFAULT_TTL,
    )


def get_nfl_state() -> dict[str, Any]:
    return _get(f"{SLEEPER_BASE_URL}/state/nfl", ttl=60)


def get_user(username_or_id: str) -> dict[str, Any]:
    """Look up a Sleeper user by username or numeric user_id."""
    return _get(f"{SLEEPER_BASE_URL}/user/{username_or_id}")


def get_user_leagues(user_id: str, season: str) -> list[dict[str, Any]]:
    """All NFL leagues a user belongs to for a given season."""
    return _get(f"{SLEEPER_BASE_URL}/user/{user_id}/leagues/nfl/{season}")


def get_trending_players(
    add_drop: str = "add", lookback_hours: int = 24, limit: int = 50
) -> list[dict[str, Any]]:
    """Players ranked by add/drop activity over the lookback window.

    Returns ``[{"player_id": str, "count": int}, ...]``. ``count`` is market
    activity (how many leagues added/dropped the player), **not** a projection.
    """
    kind = "add" if add_drop not in ("add", "drop") else add_drop
    return _get(
        f"{SLEEPER_BASE_URL}/players/nfl/trending/{kind}"
        f"?lookback_hours={lookback_hours}&limit={limit}",
        ttl=_DEFAULT_TTL,
    )


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _build_user_map(users: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map roster_id -> user info for a league (users list contains roster_id)."""
    return {str(u["user_id"]): u for u in users}


def _roster_user_map(
    rosters: list[dict[str, Any]], users: list[dict[str, Any]]
) -> dict[int, dict[str, Any]]:
    """Map roster_id (int) -> user info."""
    uid_to_user = {str(u["user_id"]): u for u in users}
    result: dict[int, dict[str, Any]] = {}
    for r in rosters:
        rid = int(r["roster_id"])
        uid = str(r["owner_id"]) if r.get("owner_id") else None
        result[rid] = uid_to_user.get(uid, {"display_name": f"Team {rid}", "user_id": uid})
    return result


# ---------------------------------------------------------------------------
# Week-range window (custom date/week filtering on all analytics)
# ---------------------------------------------------------------------------
# Every stat collects weeks via ``_collect_all_matchups`` /
# ``_collect_all_transactions``. Rather than thread a start-week argument through
# all 25 stat functions, the active window's first week is held in a contextvar
# that the collectors honour. The endpoint layer sets it per request with
# ``week_window`` and it defaults to 1 (full season) everywhere else.
_window_start: contextvars.ContextVar[int] = contextvars.ContextVar(
    "sleeper_window_start", default=1
)


class week_window:  # noqa: N801 - used as a context manager
    """Restrict analytics collectors to weeks >= ``start`` for the block."""

    def __init__(self, start: int | None) -> None:
        self.start = max(1, start or 1)
        self._token: contextvars.Token[int] | None = None

    def __enter__(self) -> "week_window":
        self._token = _window_start.set(self.start)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._token is not None:
            _window_start.reset(self._token)
            self._token = None


# ---------------------------------------------------------------------------
# Stats calculators
# ---------------------------------------------------------------------------

def _collect_all_matchups(
    league_id: str, current_week: int
) -> dict[int, list[dict[str, Any]]]:
    """Return {week: [matchup_row, ...]} for the active window up to current_week.

    The window's first week comes from the ``week_window`` contextvar (default 1).
    """
    start = min(_window_start.get(), current_week)
    all_matchups: dict[int, list[dict[str, Any]]] = {}
    for w in range(start, current_week + 1):
        try:
            all_matchups[w] = get_matchups(league_id, w)
        except httpx.HTTPError:
            pass
    return all_matchups


def _team_week_table(
    all_matchups: dict[int, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    """
    Build a flat team-week fact table from raw matchup data.

    Each row: {week, roster_id, matchup_id, points, starters, players}
    """
    rows: list[dict[str, Any]] = []
    for week, week_matchups in all_matchups.items():
        for m in week_matchups:
            if m.get("roster_id") is None:
                continue
            rows.append(
                {
                    "week": week,
                    "roster_id": int(m["roster_id"]),
                    "matchup_id": m.get("matchup_id"),
                    "points": float(m.get("points") or 0),
                    "starters": m.get("starters") or [],
                    "players": m.get("players") or [],
                    "starters_points": m.get("starters_points") or [],
                    "players_points": m.get("players_points") or {},
                }
            )
    return rows


def _resolve_result(
    roster_id: int,
    matchup_id: int | None,
    points: float,
    week_rows: list[dict[str, Any]],
) -> str:
    """Return 'W', 'L', or 'T' for a team in a given week."""
    if matchup_id is None:
        return "T"
    opponent = next(
        (
            r
            for r in week_rows
            if r["matchup_id"] == matchup_id and r["roster_id"] != roster_id
        ),
        None,
    )
    if opponent is None:
        return "T"
    opp_pts = opponent["points"]
    if points > opp_pts:
        return "W"
    if points < opp_pts:
        return "L"
    return "T"


# ---------------------------------------------------------------------------
# Public stat functions (each returns a JSON-serialisable payload)
# ---------------------------------------------------------------------------

def stat_all_play_record(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#1 All-Play Record – virtual W/L against every opponent each week."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    totals: dict[int, dict[str, Any]] = {}
    for rid in rum:
        totals[rid] = {"roster_id": rid, "all_play_wins": 0, "all_play_losses": 0, "all_play_ties": 0}

    for week, _matchups in all_matchups.items():
        week_rows = [r for r in tw if r["week"] == week]
        scores = [(r["roster_id"], r["points"]) for r in week_rows]
        for rid, pts in scores:
            for opp_rid, opp_pts in scores:
                if opp_rid == rid:
                    continue
                if pts > opp_pts:
                    totals[rid]["all_play_wins"] += 1
                elif pts < opp_pts:
                    totals[rid]["all_play_losses"] += 1
                else:
                    totals[rid]["all_play_ties"] += 1

    result = []
    for rid, data in sorted(totals.items(), key=lambda x: x[1]["all_play_wins"], reverse=True):
        user = rum.get(rid, {})
        result.append({
            **data,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_expected_wins(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#2 Expected Wins – wins based on weekly score rank."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    n_teams = len(rosters)

    expected: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    for week in all_matchups:
        week_rows = sorted(
            [r for r in tw if r["week"] == week],
            key=lambda x: x["points"],
        )
        for rank, row in enumerate(week_rows):
            expected[row["roster_id"]] += rank / max(n_teams - 1, 1)

    result = []
    for rid, exp in sorted(expected.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "expected_wins": round(exp, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_luck_adjusted_standings(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#3 Luck-Adjusted Standings – actual wins vs expected wins."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    n_teams = len(rosters)

    actual_wins: dict[int, int] = {r["roster_id"]: 0 for r in rosters}
    expected: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}

    for week, _matchups in all_matchups.items():
        week_rows = [r for r in tw if r["week"] == week]
        sorted_rows = sorted(week_rows, key=lambda x: x["points"])
        for rank, row in enumerate(sorted_rows):
            expected[row["roster_id"]] += rank / max(n_teams - 1, 1)
        for row in week_rows:
            result_val = _resolve_result(
                row["roster_id"], row["matchup_id"], row["points"], week_rows
            )
            if result_val == "W":
                actual_wins[row["roster_id"]] += 1

    result = []
    for rid in actual_wins:
        user = rum.get(rid, {})
        luck = round(actual_wins[rid] - expected[rid], 2)
        result.append({
            "roster_id": rid,
            "actual_wins": actual_wins[rid],
            "expected_wins": round(expected[rid], 2),
            "luck_delta": luck,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["luck_delta"], reverse=True)
    return result


def stat_schedule_luck_index(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#4 Schedule Luck Index – average points scored against each team."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    opp_totals: dict[int, list[float]] = {r["roster_id"]: [] for r in rosters}
    for week, _matchups in all_matchups.items():
        week_rows = [r for r in tw if r["week"] == week]
        mid_map: dict[int, list[dict[str, Any]]] = {}
        for row in week_rows:
            mid = row["matchup_id"]
            if mid is None:
                continue
            mid_map.setdefault(mid, []).append(row)
        for _mid, pair in mid_map.items():
            if len(pair) == 2:
                opp_totals[pair[0]["roster_id"]].append(pair[1]["points"])
                opp_totals[pair[1]["roster_id"]].append(pair[0]["points"])

    result = []
    for rid, opp_scores in opp_totals.items():
        user = rum.get(rid, {})
        avg_opp = round(sum(opp_scores) / len(opp_scores), 2) if opp_scores else 0.0
        result.append({
            "roster_id": rid,
            "avg_opponent_score": avg_opp,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["avg_opponent_score"], reverse=True)
    return result


def stat_bad_beat_tracker(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#5 Bad Beats – losses where team scored in the top half of the league."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    bad_beats: dict[int, list[dict[str, Any]]] = {r["roster_id"]: [] for r in rosters}
    for week, _matchups in all_matchups.items():
        week_rows = [r for r in tw if r["week"] == week]
        n = len(week_rows)
        median = sorted(week_rows, key=lambda x: x["points"])[n // 2]["points"] if n else 0
        for row in week_rows:
            result_val = _resolve_result(
                row["roster_id"], row["matchup_id"], row["points"], week_rows
            )
            if result_val == "L" and row["points"] >= median:
                bad_beats[row["roster_id"]].append(
                    {"week": week, "points": row["points"]}
                )

    result = []
    for rid, beats in bad_beats.items():
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "bad_beat_count": len(beats),
            "instances": beats,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["bad_beat_count"], reverse=True)
    return result


def stat_fraud_win_tracker(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#6 Fraud Wins – wins where team scored in the bottom half."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    fraud_wins: dict[int, list[dict[str, Any]]] = {r["roster_id"]: [] for r in rosters}
    for week, _matchups in all_matchups.items():
        week_rows = [r for r in tw if r["week"] == week]
        n = len(week_rows)
        median = sorted(week_rows, key=lambda x: x["points"])[n // 2]["points"] if n else 0
        for row in week_rows:
            result_val = _resolve_result(
                row["roster_id"], row["matchup_id"], row["points"], week_rows
            )
            if result_val == "W" and row["points"] < median:
                fraud_wins[row["roster_id"]].append(
                    {"week": week, "points": row["points"]}
                )

    result = []
    for rid, wins in fraud_wins.items():
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "fraud_win_count": len(wins),
            "instances": wins,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["fraud_win_count"], reverse=True)
    return result


def _optimal_score(
    starters: list[str],
    players: list[str],
    players_points: dict[str, float],
) -> float:
    """Calculate optimal lineup score given roster slot requirements."""
    # Simplified: take the top N players by points where N = len(starters)
    n_starters = len(starters)
    if n_starters == 0:
        return 0.0
    all_scores = [float(players_points.get(p, 0)) for p in players]
    all_scores.sort(reverse=True)
    return sum(all_scores[:n_starters])


def stat_points_left_on_bench(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#7 Points Left on Bench – total missed optimal points per manager."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    bench_loss: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    for row in tw:
        rid = row["roster_id"]
        actual = row["points"]
        optimal = _optimal_score(
            row["starters"], row["players"], row["players_points"]
        )
        bench_loss[rid] += max(0.0, optimal - actual)

    result = []
    for rid, loss in sorted(bench_loss.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "total_bench_points_lost": round(loss, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_manager_efficiency(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#8 Manager Efficiency – actual / optimal score."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    data: dict[int, dict[str, float]] = {
        r["roster_id"]: {"actual": 0.0, "optimal": 0.0} for r in rosters
    }
    for row in tw:
        rid = row["roster_id"]
        actual = row["points"]
        optimal = _optimal_score(
            row["starters"], row["players"], row["players_points"]
        )
        data[rid]["actual"] += actual
        data[rid]["optimal"] += optimal

    result = []
    for rid, d in data.items():
        user = rum.get(rid, {})
        efficiency = round(d["actual"] / d["optimal"] * 100, 1) if d["optimal"] > 0 else 0.0
        result.append({
            "roster_id": rid,
            "total_actual_points": round(d["actual"], 2),
            "total_optimal_points": round(d["optimal"], 2),
            "efficiency_pct": efficiency,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["efficiency_pct"], reverse=True)
    return result


def stat_optimal_lineup_score(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#9 Optimal Lineup Score – best possible weekly scores per manager."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    totals: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    for row in tw:
        rid = row["roster_id"]
        totals[rid] += _optimal_score(
            row["starters"], row["players"], row["players_points"]
        )

    result = []
    for rid, pts in sorted(totals.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "total_optimal_points": round(pts, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_bench_blunder_award(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#10 Bench Blunder Award – single worst lineup decision per manager."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    worst: dict[int, dict[str, Any]] = {}
    for row in tw:
        rid = row["roster_id"]
        actual = row["points"]
        optimal = _optimal_score(
            row["starters"], row["players"], row["players_points"]
        )
        gap = max(0.0, optimal - actual)
        if rid not in worst or gap > worst[rid]["bench_blunder_points"]:
            worst[rid] = {"week": row["week"], "bench_blunder_points": round(gap, 2)}

    result = []
    for rid, blunder in sorted(worst.items(), key=lambda x: x[1]["bench_blunder_points"], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            **blunder,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_dead_lineup_penalty(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#11 Dead Lineup Penalty – points lost from starting zero-point players."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    penalty: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    for row in tw:
        rid = row["roster_id"]
        pp = row["players_points"]
        starters = row["starters"]
        bench = [p for p in row["players"] if p not in starters]
        # For each zero-point starter see if a bench player would have done better
        for starter in starters:
            s_pts = float(pp.get(starter, 0))
            if s_pts == 0:
                best_bench = max((float(pp.get(b, 0)) for b in bench), default=0.0)
                penalty[rid] += best_bench

    result = []
    for rid, pen in sorted(penalty.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "dead_lineup_penalty": round(pen, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def _collect_all_transactions(league_id: str, current_week: int) -> list[dict[str, Any]]:
    start = min(_window_start.get(), current_week)
    txns: list[dict[str, Any]] = []
    for w in range(start, current_week + 1):
        try:
            txns.extend(get_transactions(league_id, w))
        except httpx.HTTPError:
            pass
    return txns


def _player_week_points(
    tw: list[dict[str, Any]],
) -> dict[str, dict[int, float]]:
    """Build {player_id: {week: points}} from the team-week fact table."""
    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)
    return player_week_pts


def stat_waiver_roi(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#12 Waiver ROI – fantasy points gained from waiver/FA adds."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    # Build player -> points per week lookup
    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    roi: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    for txn in txns:
        if txn.get("type") not in ("free_agent", "waiver"):
            continue
        adds = txn.get("adds") or {}
        for pid, rid in adds.items():
            week_added = txn.get("leg", 1) or 1
            future_pts = sum(
                pts
                for w, pts in player_week_pts.get(pid, {}).items()
                if w >= week_added
            )
            roi[rid] = roi.get(rid, 0.0) + future_pts

    result = []
    for rid, pts in sorted(roi.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "waiver_roi_points": round(pts, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_faab_efficiency(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#13 FAAB Efficiency – points per FAAB dollar spent."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    faab_spent: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    faab_pts: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}

    for txn in txns:
        if txn.get("type") != "waiver":
            continue
        settings = txn.get("settings") or {}
        bid = float(settings.get("waiver_bid", 0) or 0)
        adds = txn.get("adds") or {}
        for pid, rid in adds.items():
            faab_spent[rid] = faab_spent.get(rid, 0.0) + bid
            week_added = txn.get("leg", 1) or 1
            future_pts = sum(
                pts
                for w, pts in player_week_pts.get(pid, {}).items()
                if w >= week_added
            )
            faab_pts[rid] = faab_pts.get(rid, 0.0) + future_pts

    result = []
    for rid in faab_spent:
        user = rum.get(rid, {})
        spent = faab_spent[rid]
        pts = faab_pts[rid]
        efficiency = round(pts / spent, 2) if spent > 0 else None
        result.append({
            "roster_id": rid,
            "faab_spent": round(spent, 2),
            "faab_points_gained": round(pts, 2),
            "points_per_dollar": efficiency,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: (x["points_per_dollar"] or 0), reverse=True)
    return result


def stat_drop_regret_index(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#14 Drop Regret Index – points scored after a manager dropped a player."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    regret: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}

    for txn in txns:
        if txn.get("type") not in ("free_agent", "waiver"):
            continue
        drops = txn.get("drops") or {}
        for pid, rid in drops.items():
            week_dropped = txn.get("leg", 1) or 1
            future_pts = sum(
                pts
                for w, pts in player_week_pts.get(pid, {}).items()
                if w > week_dropped
            )
            regret[rid] = regret.get(rid, 0.0) + future_pts

    result = []
    for rid, pts in sorted(regret.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "drop_regret_points": round(pts, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_free_agent_steal(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#15 Free Agent Steal of the Year – best $0 or low-cost pickup."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    steals: list[dict[str, Any]] = []
    nfl_players = get_nfl_players()

    for txn in txns:
        if txn.get("type") not in ("free_agent", "waiver"):
            continue
        settings = txn.get("settings") or {}
        bid = float(settings.get("waiver_bid", 0) or 0)
        if bid > 10:
            continue
        adds = txn.get("adds") or {}
        for pid, rid in adds.items():
            week_added = txn.get("leg", 1) or 1
            future_pts = sum(
                pts
                for w, pts in player_week_pts.get(pid, {}).items()
                if w >= week_added
            )
            player_info = nfl_players.get(pid, {})
            player_name = player_info.get("full_name", f"Player {pid}")
            user = rum.get(rid, {})
            steals.append({
                "roster_id": rid,
                "player_id": pid,
                "player_name": player_name,
                "faab_bid": bid,
                "points_after_add": round(future_pts, 2),
                "week_added": week_added,
                "display_name": user.get("display_name", f"Team {rid}"),
            })

    steals.sort(key=lambda x: x["points_after_add"], reverse=True)
    return steals[:25]


def stat_transaction_roi(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#16 Transaction ROI – net value from all adds minus all drops."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    net_roi: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}

    for txn in txns:
        if txn.get("type") not in ("free_agent", "waiver"):
            continue
        week_txn = txn.get("leg", 1) or 1
        for pid, rid in (txn.get("adds") or {}).items():
            pts = sum(
                p for w, p in player_week_pts.get(pid, {}).items() if w >= week_txn
            )
            net_roi[rid] = net_roi.get(rid, 0.0) + pts
        for pid, rid in (txn.get("drops") or {}).items():
            pts = sum(
                p for w, p in player_week_pts.get(pid, {}).items() if w >= week_txn
            )
            net_roi[rid] = net_roi.get(rid, 0.0) - pts

    result = []
    for rid, roi in sorted(net_roi.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "transaction_roi": round(roi, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_draft_roi(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#17 Draft ROI – actual season points vs expected value at draft slot."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    drafts = get_drafts(league_id)
    nfl_players = get_nfl_players()

    if not drafts:
        return []

    draft_id = drafts[0]["draft_id"]
    picks = get_draft_picks(draft_id)
    n_teams = len(rosters)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    pick_data: list[dict[str, Any]] = []
    for pick in picks:
        pid = pick.get("player_id")
        if not pid:
            continue
        pick_no = int(pick.get("pick_no", 1))
        roster_id = int(pick.get("roster_id", 0))
        total_pts = sum(player_week_pts.get(pid, {}).values())
        # Simple expected value: inverse of pick number scaled
        # Round 1 pick #1 is worth most; exponential decay
        expected_pts = max(0.0, 300 - (pick_no - 1) * (250 / max(n_teams * 15, 1)))
        surplus = total_pts - expected_pts
        player_info = nfl_players.get(pid, {})
        pick_data.append({
            "roster_id": roster_id,
            "player_id": pid,
            "player_name": player_info.get("full_name", f"Player {pid}"),
            "pick_no": pick_no,
            "total_points": round(total_pts, 2),
            "expected_points": round(expected_pts, 2),
            "surplus": round(surplus, 2),
        })

    # Aggregate by roster
    by_roster: dict[int, dict[str, Any]] = {}
    for row in pick_data:
        rid = row["roster_id"]
        if rid not in by_roster:
            by_roster[rid] = {"total_surplus": 0.0, "picks": []}
        by_roster[rid]["total_surplus"] += row["surplus"]
        by_roster[rid]["picks"].append(row)

    result = []
    for rid, d in sorted(by_roster.items(), key=lambda x: x[1]["total_surplus"], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "total_surplus": round(d["total_surplus"], 2),
            "pick_count": len(d["picks"]),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_best_draft_pick(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#18 Best Draft Pick – individual picks with highest surplus value."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    drafts = get_drafts(league_id)
    nfl_players = get_nfl_players()

    if not drafts:
        return []

    draft_id = drafts[0]["draft_id"]
    picks = get_draft_picks(draft_id)
    n_teams = len(rosters)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    pick_data: list[dict[str, Any]] = []
    for pick in picks:
        pid = pick.get("player_id")
        if not pid:
            continue
        pick_no = int(pick.get("pick_no", 1))
        roster_id = int(pick.get("roster_id", 0))
        total_pts = sum(player_week_pts.get(pid, {}).values())
        expected_pts = max(0.0, 300 - (pick_no - 1) * (250 / max(n_teams * 15, 1)))
        surplus = total_pts - expected_pts
        player_info = nfl_players.get(pid, {})
        user = rum.get(roster_id, {})
        pick_data.append({
            "roster_id": roster_id,
            "player_id": pid,
            "player_name": player_info.get("full_name", f"Player {pid}"),
            "pick_no": pick_no,
            "total_points": round(total_pts, 2),
            "expected_points": round(expected_pts, 2),
            "surplus": round(surplus, 2),
            "display_name": user.get("display_name", f"Team {roster_id}"),
        })

    pick_data.sort(key=lambda x: x["surplus"], reverse=True)
    return pick_data[:20]


def stat_worst_draft_pick(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#19 Worst Draft Pick – individual picks with the lowest surplus."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    drafts = get_drafts(league_id)
    nfl_players = get_nfl_players()

    if not drafts:
        return []

    draft_id = drafts[0]["draft_id"]
    picks = get_draft_picks(draft_id)
    n_teams = len(rosters)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    pick_data: list[dict[str, Any]] = []
    for pick in picks:
        pid = pick.get("player_id")
        if not pid:
            continue
        pick_no = int(pick.get("pick_no", 1))
        roster_id = int(pick.get("roster_id", 0))
        total_pts = sum(player_week_pts.get(pid, {}).values())
        expected_pts = max(0.0, 300 - (pick_no - 1) * (250 / max(n_teams * 15, 1)))
        surplus = total_pts - expected_pts
        player_info = nfl_players.get(pid, {})
        user = rum.get(roster_id, {})
        pick_data.append({
            "roster_id": roster_id,
            "player_id": pid,
            "player_name": player_info.get("full_name", f"Player {pid}"),
            "pick_no": pick_no,
            "total_points": round(total_pts, 2),
            "expected_points": round(expected_pts, 2),
            "surplus": round(surplus, 2),
            "display_name": user.get("display_name", f"Team {roster_id}"),
        })

    pick_data.sort(key=lambda x: x["surplus"])
    return pick_data[:20]


def stat_draft_capital_retention(
    league_id: str, current_week: int  # noqa: ARG001
) -> list[dict[str, Any]]:
    """#20 Draft Capital Retention – % of drafted players still on original roster."""
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    drafts = get_drafts(league_id)

    if not drafts:
        return []

    draft_id = drafts[0]["draft_id"]
    picks = get_draft_picks(draft_id)

    # Build current roster player map
    current_roster: dict[int, set[str]] = {}
    for r in rosters:
        rid = int(r["roster_id"])
        current_roster[rid] = set(r.get("players") or [])

    drafted_by: dict[int, list[str]] = {}
    for pick in picks:
        pid = pick.get("player_id")
        rid = int(pick.get("roster_id", 0))
        if pid:
            drafted_by.setdefault(rid, []).append(pid)

    result = []
    for rid, drafted in drafted_by.items():
        user = rum.get(rid, {})
        n_drafted = len(drafted)
        n_retained = sum(1 for p in drafted if p in current_roster.get(rid, set()))
        pct = round(n_retained / n_drafted * 100, 1) if n_drafted > 0 else 0.0
        result.append({
            "roster_id": rid,
            "drafted_count": n_drafted,
            "retained_count": n_retained,
            "retention_pct": pct,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["retention_pct"], reverse=True)
    return result


def stat_trade_value(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#21 Trade Value Won/Lost – rest-of-season points from traded assets."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    trade_net: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}

    for txn in txns:
        if txn.get("type") != "trade":
            continue
        week_trade = txn.get("leg", 1) or 1
        # adds = players received
        for pid, rid in (txn.get("adds") or {}).items():
            pts = sum(p for w, p in player_week_pts.get(pid, {}).items() if w > week_trade)
            trade_net[rid] = trade_net.get(rid, 0.0) + pts
        # drops = players sent away
        for pid, rid in (txn.get("drops") or {}).items():
            pts = sum(p for w, p in player_week_pts.get(pid, {}).items() if w > week_trade)
            trade_net[rid] = trade_net.get(rid, 0.0) - pts

    result = []
    for rid, net in sorted(trade_net.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "trade_value_net": round(net, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_immediate_trade_impact(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#22 Immediate Trade Impact – points from traded players in first 3 weeks."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    immediate: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}

    for txn in txns:
        if txn.get("type") != "trade":
            continue
        week_trade = txn.get("leg", 1) or 1
        for pid, rid in (txn.get("adds") or {}).items():
            pts = sum(
                p for w, p in player_week_pts.get(pid, {}).items()
                if week_trade < w <= week_trade + 3
            )
            immediate[rid] = immediate.get(rid, 0.0) + pts

    result = []
    for rid, pts in sorted(immediate.items(), key=lambda x: x[1], reverse=True):
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "immediate_trade_points": round(pts, 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    return result


def stat_trade_regret_tracker(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#23 Trade Regret Tracker – trades where one side clearly lost value."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    player_week_pts: dict[str, dict[int, float]] = {}
    for row in tw:
        for pid, pts in row["players_points"].items():
            player_week_pts.setdefault(pid, {})[row["week"]] = float(pts)

    regrets: list[dict[str, Any]] = []
    for txn in txns:
        if txn.get("type") != "trade":
            continue
        week_trade = txn.get("leg", 1) or 1
        adds = txn.get("adds") or {}
        drops = txn.get("drops") or {}
        # Collect sides
        sides: dict[int, dict[str, float]] = {}
        for pid, rid in adds.items():
            sides.setdefault(rid, {"received": 0.0, "sent": 0.0})
            pts = sum(p for w, p in player_week_pts.get(pid, {}).items() if w > week_trade)
            sides[rid]["received"] += pts
        for pid, rid in drops.items():
            sides.setdefault(rid, {"received": 0.0, "sent": 0.0})
            pts = sum(p for w, p in player_week_pts.get(pid, {}).items() if w > week_trade)
            sides[rid]["sent"] += pts

        if len(sides) < 2:
            continue
        roster_ids = list(sides.keys())
        for rid in roster_ids:
            user = rum.get(rid, {})
            net = sides[rid]["received"] - sides[rid]["sent"]
            regrets.append({
                "week": week_trade,
                "roster_id": rid,
                "received_points": round(sides[rid]["received"], 2),
                "sent_points": round(sides[rid]["sent"], 2),
                "net": round(net, 2),
                "display_name": user.get("display_name", f"Team {rid}"),
            })

    # Show the biggest losers (most negative net)
    regrets.sort(key=lambda x: x["net"])
    return regrets[:20]


def stat_playoff_odds(
    league_id: str, current_week: int, simulations: int = 1000
) -> list[dict[str, Any]]:
    """#24 Playoff Odds Simulator – Monte Carlo simulation of playoff chances."""
    import random

    league = get_league(league_id)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)

    total_weeks = int(league.get("settings", {}).get("playoff_week_start", 15)) - 1
    playoff_teams = int(league.get("settings", {}).get("playoff_teams", 6))

    # Calculate team strengths (average weekly score)
    team_scores: dict[int, list[float]] = {}
    for row in tw:
        team_scores.setdefault(row["roster_id"], []).append(row["points"])

    team_avg: dict[int, float] = {
        rid: sum(pts) / len(pts) if pts else 0.0
        for rid, pts in team_scores.items()
    }
    team_std: dict[int, float] = {}
    for rid, pts in team_scores.items():
        if len(pts) > 1:
            mean = team_avg[rid]
            team_std[rid] = (sum((p - mean) ** 2 for p in pts) / len(pts)) ** 0.5
        else:
            team_std[rid] = 20.0

    # Current standings
    actual_wins: dict[int, int] = {r["roster_id"]: 0 for r in rosters}
    for week, _matchups in all_matchups.items():
        week_rows = [r for r in tw if r["week"] == week]
        for row in week_rows:
            result_val = _resolve_result(
                row["roster_id"], row["matchup_id"], row["points"], week_rows
            )
            if result_val == "W":
                actual_wins[row["roster_id"]] += 1

    # Build remaining schedule (pair teams by matchup_id pattern)
    remaining_weeks = max(0, total_weeks - current_week)
    roster_ids = [r["roster_id"] for r in rosters]

    playoff_counts: dict[int, int] = dict.fromkeys(roster_ids, 0)

    for _ in range(simulations):
        sim_wins = dict(actual_wins)
        for _ in range(remaining_weeks):
            random.shuffle(roster_ids)
            for i in range(0, len(roster_ids) - 1, 2):
                a = roster_ids[i]
                b = roster_ids[i + 1]
                score_a = max(0, random.gauss(team_avg.get(a, 100), team_std.get(a, 20)))
                score_b = max(0, random.gauss(team_avg.get(b, 100), team_std.get(b, 20)))
                if score_a > score_b:
                    sim_wins[a] = sim_wins.get(a, 0) + 1
                else:
                    sim_wins[b] = sim_wins.get(b, 0) + 1
        # Top N by wins make playoffs
        sorted_by_wins = sorted(sim_wins.items(), key=lambda x: x[1], reverse=True)
        for rid, _ in sorted_by_wins[:playoff_teams]:
            playoff_counts[rid] += 1

    result = []
    for rid in roster_ids:
        user = rum.get(rid, {})
        odds = round(playoff_counts.get(rid, 0) / simulations * 100, 1)
        result.append({
            "roster_id": rid,
            "current_wins": actual_wins.get(rid, 0),
            "avg_score": round(team_avg.get(rid, 0), 2),
            "playoff_probability_pct": odds,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["playoff_probability_pct"], reverse=True)
    return result


def stat_dynasty_legacy_score(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """
    #25 Dynasty Legacy Score – season composite:
    wins (30%), total points (30%), playoff appearance (20%),
    manager efficiency (10%), waiver ROI (10%).
    """
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)

    # wins
    wins: dict[int, int] = {r["roster_id"]: 0 for r in rosters}
    total_pts: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    for week, _matchups in all_matchups.items():
        week_rows = [r for r in tw if r["week"] == week]
        for row in week_rows:
            total_pts[row["roster_id"]] += row["points"]
            result_val = _resolve_result(
                row["roster_id"], row["matchup_id"], row["points"], week_rows
            )
            if result_val == "W":
                wins[row["roster_id"]] += 1

    max_wins = max(wins.values(), default=1)
    max_pts = max(total_pts.values(), default=1)

    # playoff appearance from winners bracket
    try:
        bracket = get_winners_bracket(league_id)
        playoff_rids = {
            match.get("t1") for match in bracket if match.get("t1")
        } | {match.get("t2") for match in bracket if match.get("t2")}
    except Exception:
        playoff_rids = set()

    # manager efficiency (reuse calculation)
    eff_data: dict[int, dict[str, float]] = {
        r["roster_id"]: {"actual": 0.0, "optimal": 0.0} for r in rosters
    }
    for row in tw:
        rid = row["roster_id"]
        actual = row["points"]
        optimal = _optimal_score(row["starters"], row["players"], row["players_points"])
        eff_data[rid]["actual"] += actual
        eff_data[rid]["optimal"] += optimal

    try:
        waiver_rows = stat_waiver_roi(league_id, current_week)
        waiver_roi = {
            int(row["roster_id"]): float(row["waiver_roi_points"])
            for row in waiver_rows
        }
    except Exception:
        waiver_roi = dict.fromkeys(wins, 0.0)
    max_waiver_roi = max(waiver_roi.values(), default=0.0)

    result = []
    for rid in wins:
        user = rum.get(rid, {})
        win_score = wins[rid] / max_wins
        pts_score = total_pts[rid] / max_pts
        playoff_score = 1.0 if rid in playoff_rids else 0.0
        eff = eff_data[rid]
        eff_score = eff["actual"] / eff["optimal"] if eff["optimal"] > 0 else 0.0
        waiver_points = waiver_roi.get(rid, 0.0)
        waiver_score = waiver_points / max_waiver_roi if max_waiver_roi > 0 else 0.0

        legacy = round(
            win_score * 0.30
            + pts_score * 0.30
            + playoff_score * 0.20
            + eff_score * 0.10
            + waiver_score * 0.10,
            4,
        )
        result.append({
            "roster_id": rid,
            "legacy_score": legacy,
            "wins": wins[rid],
            "total_points": round(total_pts[rid], 2),
            "waiver_roi_points": round(waiver_points, 2),
            "made_playoffs": rid in playoff_rids,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["legacy_score"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# 2.4 Transactions: Waivers, Trades & Draft (TODO items 67–74)
# ---------------------------------------------------------------------------


def _draft_expected_points(pick_no: int, n_teams: int) -> float:
    """Expected season points for a draft slot (linear decay from pick #1)."""
    return max(0.0, 300 - (pick_no - 1) * (250 / max(n_teams * 15, 1)))


def stat_waiver_spend_efficiency(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#67 Waiver Spend Efficiency – FAAB spent vs fantasy points gained."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    player_week_pts = _player_week_points(tw)

    spent: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    points: dict[int, float] = {r["roster_id"]: 0.0 for r in rosters}
    claims: dict[int, int] = {r["roster_id"]: 0 for r in rosters}

    for txn in txns:
        if txn.get("type") not in ("free_agent", "waiver"):
            continue
        if txn.get("status") not in (None, "complete"):
            continue
        settings = txn.get("settings") or {}
        bid = float(settings.get("waiver_bid", 0) or 0)
        week_added = txn.get("leg", 1) or 1
        for pid, rid in (txn.get("adds") or {}).items():
            spent[rid] = spent.get(rid, 0.0) + bid
            claims[rid] = claims.get(rid, 0) + 1
            points[rid] = points.get(rid, 0.0) + sum(
                pts
                for w, pts in player_week_pts.get(pid, {}).items()
                if w >= week_added
            )

    result = []
    for rid in spent:
        user = rum.get(rid, {})
        dollars = spent[rid]
        pts = points[rid]
        result.append({
            "roster_id": rid,
            "faab_spent": round(dollars, 2),
            "points_gained": round(pts, 2),
            "points_per_dollar": round(pts / dollars, 2) if dollars > 0 else None,
            "claims": claims[rid],
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: (x["points_per_dollar"] or 0), reverse=True)
    return result


def stat_waiver_pickup_leaderboard(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#68 Best/Worst Waiver Pickups – season leaderboard of individual adds."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    nfl_players = get_nfl_players()
    player_week_pts = _player_week_points(tw)

    pickups: list[dict[str, Any]] = []
    for txn in txns:
        if txn.get("type") not in ("free_agent", "waiver"):
            continue
        if txn.get("status") not in (None, "complete"):
            continue
        settings = txn.get("settings") or {}
        bid = float(settings.get("waiver_bid", 0) or 0)
        week_added = txn.get("leg", 1) or 1
        for pid, rid in (txn.get("adds") or {}).items():
            future_pts = sum(
                pts
                for w, pts in player_week_pts.get(pid, {}).items()
                if w >= week_added
            )
            info = nfl_players.get(pid, {})
            user = rum.get(rid, {})
            pickups.append({
                "roster_id": rid,
                "player_id": pid,
                "player_name": info.get("full_name", f"Player {pid}"),
                "position": info.get("position"),
                "week_added": week_added,
                "faab_bid": round(bid, 2),
                "points_gained": round(future_pts, 2),
                "display_name": user.get("display_name", f"Team {rid}"),
                "avatar": user.get("avatar"),
            })

    pickups.sort(key=lambda x: x["points_gained"], reverse=True)
    # Tag rank so best (1..) and worst (negative) are both legible in exports.
    for i, row in enumerate(pickups):
        row["overall_rank"] = i + 1
    return pickups


def stat_trade_fairness(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """
    #69 Trade Fairness Evaluator – balances each completed trade by the
    rest-of-season points the exchanged assets actually produced.

    Sleeper exposes no projections, so realized rest-of-season production is the
    fairness proxy. A trade is "fair" when both sides received similar value.
    """
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    player_week_pts = _player_week_points(tw)

    trades: list[dict[str, Any]] = []
    for txn in txns:
        if txn.get("type") != "trade":
            continue
        if txn.get("status") not in (None, "complete"):
            continue
        week_trade = txn.get("leg", 1) or 1
        received: dict[int, float] = {}
        for pid, rid in (txn.get("adds") or {}).items():
            received[rid] = received.get(rid, 0.0) + sum(
                p for w, p in player_week_pts.get(pid, {}).items() if w > week_trade
            )
        roster_ids = list(received.keys())
        if len(roster_ids) != 2:
            continue
        a, b = roster_ids
        va, vb = received[a], received[b]
        total = va + vb
        # Fairness: 100 when even, → 0 as one side captures all the value.
        fairness = round((1 - abs(va - vb) / total) * 100, 1) if total > 0 else 100.0
        ua = rum.get(a, {})
        ub = rum.get(b, {})
        winner = ua if va >= vb else ub
        trades.append({
            "week": week_trade,
            "roster_id": a,
            "team_a": ua.get("display_name", f"Team {a}"),
            "team_b": ub.get("display_name", f"Team {b}"),
            "team_a_value": round(va, 2),
            "team_b_value": round(vb, 2),
            "value_gap": round(abs(va - vb), 2),
            "fairness_pct": fairness,
            "winner": winner.get("display_name", "—"),
            "display_name": (
                f"{ua.get('display_name', f'Team {a}')} ↔ "
                f"{ub.get('display_name', f'Team {b}')}"
            ),
            "avatar": ua.get("avatar"),
        })

    # Least fair (largest gap) first – those are the interesting ones.
    trades.sort(key=lambda x: x["value_gap"], reverse=True)
    return trades


def stat_trade_impact_tracker(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """
    #70 Trade Impact Tracker – how a completed trade has aged for both sides
    (net rest-of-season points received minus sent), with a clear winner.
    """
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    player_week_pts = _player_week_points(tw)

    trades: list[dict[str, Any]] = []
    for txn in txns:
        if txn.get("type") != "trade":
            continue
        if txn.get("status") not in (None, "complete"):
            continue
        week_trade = txn.get("leg", 1) or 1
        sides: dict[int, dict[str, float]] = {}
        for pid, rid in (txn.get("adds") or {}).items():
            sides.setdefault(rid, {"received": 0.0, "sent": 0.0})["received"] += sum(
                p for w, p in player_week_pts.get(pid, {}).items() if w > week_trade
            )
        for pid, rid in (txn.get("drops") or {}).items():
            sides.setdefault(rid, {"received": 0.0, "sent": 0.0})["sent"] += sum(
                p for w, p in player_week_pts.get(pid, {}).items() if w > week_trade
            )
        if len(sides) != 2:
            continue
        a, b = sides.keys()
        net_a = sides[a]["received"] - sides[a]["sent"]
        net_b = sides[b]["received"] - sides[b]["sent"]
        ua = rum.get(a, {})
        ub = rum.get(b, {})
        winner_rid = a if net_a >= net_b else b
        winner = rum.get(winner_rid, {})
        trades.append({
            "week": week_trade,
            "roster_id": winner_rid,
            "team_a": ua.get("display_name", f"Team {a}"),
            "team_a_net": round(net_a, 2),
            "team_b": ub.get("display_name", f"Team {b}"),
            "team_b_net": round(net_b, 2),
            "margin": round(abs(net_a - net_b), 2),
            "winner": winner.get("display_name", "—"),
            "display_name": (
                f"W{week_trade}: {winner.get('display_name', f'Team {winner_rid}')} won"
            ),
            "avatar": winner.get("avatar"),
        })

    trades.sort(key=lambda x: x["margin"], reverse=True)
    return trades


def _draft_pick_table(
    league_id: str, tw: list[dict[str, Any]], n_teams: int
) -> list[dict[str, Any]]:
    """Shared draft-pick fact rows: player, slot, points, expected, surplus."""
    drafts = get_drafts(league_id)
    if not drafts:
        return []
    picks = get_draft_picks(drafts[0]["draft_id"])
    nfl_players = get_nfl_players()
    player_week_pts = _player_week_points(tw)

    rows: list[dict[str, Any]] = []
    for pick in picks:
        pid = pick.get("player_id")
        if not pid:
            continue
        pick_no = int(pick.get("pick_no", 1))
        rnd = int(pick.get("round", 1))
        roster_id = int(pick.get("roster_id", 0))
        total_pts = sum(player_week_pts.get(pid, {}).values())
        expected = _draft_expected_points(pick_no, n_teams)
        info = nfl_players.get(pid, {})
        meta = pick.get("metadata") or {}
        rows.append({
            "roster_id": roster_id,
            "player_id": pid,
            "player_name": info.get("full_name")
            or f"{meta.get('first_name', '')} {meta.get('last_name', '')}".strip()
            or f"Player {pid}",
            "position": info.get("position") or meta.get("position"),
            "round": rnd,
            "pick_no": pick_no,
            "total_points": round(total_pts, 2),
            "expected_points": round(expected, 2),
            "surplus": round(total_pts - expected, 2),
        })
    return rows


def _letter_grade(avg_surplus: float) -> str:
    if avg_surplus >= 40:
        return "A"
    if avg_surplus >= 15:
        return "B"
    if avg_surplus >= -15:
        return "C"
    if avg_surplus >= -40:
        return "D"
    return "F"


def stat_draft_grade(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """#71 Draft Grade – drafted production vs draft-slot value, graded by team."""
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    pick_rows = _draft_pick_table(league_id, tw, len(rosters))
    if not pick_rows:
        return []

    by_roster: dict[int, list[dict[str, Any]]] = {}
    for row in pick_rows:
        by_roster.setdefault(row["roster_id"], []).append(row)

    result = []
    for rid, picks in by_roster.items():
        user = rum.get(rid, {})
        total_surplus = sum(p["surplus"] for p in picks)
        avg_surplus = total_surplus / len(picks) if picks else 0.0
        result.append({
            "roster_id": rid,
            "grade": _letter_grade(avg_surplus),
            "total_surplus": round(total_surplus, 2),
            "avg_surplus_per_pick": round(avg_surplus, 2),
            "picks": len(picks),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["total_surplus"], reverse=True)
    return result


def stat_draft_reach_steal(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """
    #72 Positional Runs & Reach/Steal – counts each team's steals and reaches
    plus how many of their picks landed inside a positional run.
    """
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    pick_rows = _draft_pick_table(league_id, tw, len(rosters))
    if not pick_rows:
        return []

    ordered = sorted(pick_rows, key=lambda x: x["pick_no"])

    # Detect positional runs: 3+ consecutive picks of the same position.
    in_run: set[int] = set()
    run_start = 0
    for i in range(1, len(ordered) + 1):
        same = (
            i < len(ordered)
            and ordered[i]["position"]
            and ordered[i]["position"] == ordered[run_start]["position"]
        )
        if not same:
            if i - run_start >= 3 and ordered[run_start]["position"]:
                for j in range(run_start, i):
                    in_run.add(ordered[j]["pick_no"])
            run_start = i

    STEAL, REACH = 50.0, -50.0
    agg: dict[int, dict[str, Any]] = {}
    for row in pick_rows:
        rid = row["roster_id"]
        d = agg.setdefault(
            rid, {"steals": 0, "reaches": 0, "picks_in_runs": 0, "best": 0.0}
        )
        if row["surplus"] >= STEAL:
            d["steals"] += 1
        elif row["surplus"] <= REACH:
            d["reaches"] += 1
        if row["pick_no"] in in_run:
            d["picks_in_runs"] += 1
        d["best"] = max(d["best"], row["surplus"])

    result = []
    for rid, d in agg.items():
        user = rum.get(rid, {})
        result.append({
            "roster_id": rid,
            "steals": d["steals"],
            "reaches": d["reaches"],
            "picks_in_runs": d["picks_in_runs"],
            "best_steal_points": round(d["best"], 2),
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: (x["steals"] - x["reaches"]), reverse=True)
    return result


def _dynasty_age_multiplier(age: float | None) -> float:
    """3-year discounted value multiplier from an age curve (peak ~24–27)."""
    if age is None:
        return 1.5
    if age <= 23:
        return 3.0
    if age <= 27:
        return 2.5
    if age <= 29:
        return 1.8
    if age <= 31:
        return 1.2
    return 0.7


def stat_keeper_dynasty_value(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """
    #73 Keeper/Dynasty Asset Valuation – projects each roster's multi-year
    value by weighting current production against an age-based value curve.
    """
    all_matchups = _collect_all_matchups(league_id, current_week)
    tw = _team_week_table(all_matchups)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)
    nfl_players = get_nfl_players()
    player_week_pts = _player_week_points(tw)

    weeks_played = max(1, len({row["week"] for row in tw}))

    result = []
    for r in rosters:
        rid = int(r["roster_id"])
        user = rum.get(rid, {})
        players = r.get("players") or []
        dynasty_value = 0.0
        ages: list[float] = []
        young_value = 0.0
        for pid in players:
            ppg = sum(player_week_pts.get(pid, {}).values()) / weeks_played
            info = nfl_players.get(pid, {})
            age = info.get("age")
            mult = _dynasty_age_multiplier(age)
            value = ppg * mult
            dynasty_value += value
            if age is not None:
                ages.append(float(age))
                if age <= 25:
                    young_value += value
        result.append({
            "roster_id": rid,
            "dynasty_value": round(dynasty_value, 2),
            "young_core_value": round(young_value, 2),
            "avg_age": round(sum(ages) / len(ages), 1) if ages else None,
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["dynasty_value"], reverse=True)
    return result


def stat_transaction_activity(
    league_id: str, current_week: int
) -> list[dict[str, Any]]:
    """
    #74 Transaction Activity Heatmap – per-manager move counts (trades, waivers,
    free agents) with a per-week breakdown for heatmap rendering.
    """
    txns = _collect_all_transactions(league_id, current_week)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    rum = _roster_user_map(rosters, users)

    def _new_counts() -> dict[str, Any]:
        return {
            "trades": 0,
            "waivers": 0,
            "free_agents": 0,
            "weekly": [0] * (current_week + 1),  # 1-indexed by week
        }

    counts: dict[int, dict[str, Any]] = {
        int(r["roster_id"]): _new_counts() for r in rosters
    }

    for txn in txns:
        if txn.get("status") not in (None, "complete"):
            continue
        ttype = txn.get("type")
        week = int(txn.get("leg", 1) or 1)
        # Attribute the move to every roster involved.
        involved: set[int] = set()
        for rid in txn.get("roster_ids") or []:
            involved.add(int(rid))
        for rid in (txn.get("adds") or {}).values():
            involved.add(int(rid))
        for rid in (txn.get("drops") or {}).values():
            involved.add(int(rid))
        for rid in involved:
            c = counts.setdefault(rid, _new_counts())
            if ttype == "trade":
                c["trades"] += 1
            elif ttype == "waiver":
                c["waivers"] += 1
            elif ttype == "free_agent":
                c["free_agents"] += 1
            if 0 <= week < len(c["weekly"]):
                c["weekly"][week] += 1

    result = []
    for rid, c in counts.items():
        user = rum.get(rid, {})
        total = c["trades"] + c["waivers"] + c["free_agents"]
        result.append({
            "roster_id": rid,
            "total_moves": total,
            "trades": c["trades"],
            "waivers": c["waivers"],
            "free_agents": c["free_agents"],
            "weekly": c["weekly"],
            "display_name": user.get("display_name", f"Team {rid}"),
            "avatar": user.get("avatar"),
        })
    result.sort(key=lambda x: x["total_moves"], reverse=True)
    return result
