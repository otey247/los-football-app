"""Tests for the Sleeper Team & League Performance stats (TODO #41–#50)."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import sleeper as svc

LEAGUE_ID = "test-league"

# Four teams, three completed weeks. Roster 1 is the high scorer, roster 4 the
# low scorer, so the resulting rankings are deterministic and easy to assert.
_USERS = [
    {"user_id": "u1", "display_name": "Alpha", "avatar": "a1"},
    {"user_id": "u2", "display_name": "Bravo", "avatar": "a2"},
    {"user_id": "u3", "display_name": "Charlie", "avatar": "a3"},
    {"user_id": "u4", "display_name": "Delta", "avatar": "a4"},
]

_ROSTERS = [
    {"roster_id": 1, "owner_id": "u1", "players": ["p1", "p2", "p3"]},
    {"roster_id": 2, "owner_id": "u2", "players": ["p4", "p5", "p6"]},
    {"roster_id": 3, "owner_id": "u3", "players": ["p7", "p8", "p9"]},
    {"roster_id": 4, "owner_id": "u4", "players": ["p10", "p11", "p12"]},
]

# week -> roster_id -> (matchup_id, points). Matchup 1 pairs rosters 1 & 2;
# matchup 2 pairs rosters 3 & 4. Roster 1 is the clear league leader.
_SCHEDULE: dict[int, dict[int, tuple[int, float]]] = {
    1: {1: (1, 120.0), 2: (1, 90.0), 3: (2, 100.0), 4: (2, 85.0)},
    2: {1: (1, 130.0), 2: (1, 95.0), 3: (2, 80.0), 4: (2, 110.0)},
    3: {1: (1, 115.0), 2: (1, 112.0), 3: (2, 118.0), 4: (2, 70.0)},
}


def _matchups_for_week(week: int) -> list[dict[str, Any]]:
    rows = []
    for roster_id, (matchup_id, points) in _SCHEDULE[week].items():
        starter = f"s{roster_id}"
        bench = f"b{roster_id}"
        rows.append(
            {
                "roster_id": roster_id,
                "matchup_id": matchup_id,
                "points": points,
                "starters": [starter],
                "players": [starter, bench],
                "starters_points": [points],
                # Bench player out-scores the starter to exercise optimal-lineup
                # and bench-points math.
                "players_points": {starter: points, bench: points + 5},
            }
        )
    return rows


@pytest.fixture(autouse=True)
def _mock_sleeper(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(svc, "get_league", lambda _lid: {"settings": {"playoff_week_start": 4}})
    monkeypatch.setattr(svc, "get_users", lambda _lid: _USERS)
    monkeypatch.setattr(svc, "get_rosters", lambda _lid: _ROSTERS)
    monkeypatch.setattr(svc, "get_matchups", lambda _lid, week: _matchups_for_week(week))
    monkeypatch.setattr(svc, "get_nfl_state", lambda: {"week": 3})
    yield


def _get_stat(client: TestClient, key: str) -> list[dict[str, Any]]:
    res = client.get(
        f"{settings.API_V1_STR}/sleeper/stats/{key}",
        params={"league_id": LEAGUE_ID, "week": 3},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert isinstance(data, list)
    return data


def test_meta_includes_team_performance(client: TestClient) -> None:
    res = client.get(f"{settings.API_V1_STR}/sleeper/meta")
    assert res.status_code == 200
    keys = {row["key"] for row in res.json()}
    expected = {
        "power-ranking-trend",
        "expected-vs-actual-wins",
        "points-for-against",
        "strength-of-schedule",
        "consistency-score",
        "all-play-standings",
        "roster-efficiency",
        "bench-points-ranking",
        "margin-of-victory",
        "cumulative-points-race",
    }
    assert expected <= keys


def test_power_ranking_trend(client: TestClient) -> None:
    data = _get_stat(client, "power-ranking-trend")
    assert len(data) == 4
    # Roster 1 always scores highest, so it leads the power ranking.
    assert data[0]["roster_id"] == 1
    assert data[0]["current_rank"] == 1
    leader_series = data[0]["series"]
    assert [pt["week"] for pt in leader_series] == [1, 2, 3]
    assert all(pt["rank"] == 1 for pt in leader_series)


def test_expected_vs_actual_wins(client: TestClient) -> None:
    data = _get_stat(client, "expected-vs-actual-wins")
    row1 = next(r for r in data if r["roster_id"] == 1)
    # Roster 1 wins all three head-to-head matchups against roster 2.
    assert row1["actual_wins"] == 3
    assert row1["actual_losses"] == 0
    assert "expected_wins" in row1 and "luck_delta" in row1


def test_points_for_against_quadrants(client: TestClient) -> None:
    data = _get_stat(client, "points-for-against")
    row1 = next(r for r in data if r["roster_id"] == 1)
    assert row1["points_for"] == pytest.approx(365.0)
    # High points-for, low points-against -> Contender.
    assert row1["quadrant"] == "Contender"
    assert "median_for" in row1


def test_strength_of_schedule(client: TestClient) -> None:
    data = _get_stat(client, "strength-of-schedule")
    for row in data:
        assert "past_sos" in row
        assert "remaining_sos" in row
        # Season is fully played in the fixture, so nothing remains.
        assert row["games_remaining"] == 0


def test_consistency_score(client: TestClient) -> None:
    data = _get_stat(client, "consistency-score")
    # Sorted most-consistent first; every team has a non-negative std dev.
    assert all(r["std_dev"] >= 0 for r in data)
    assert data == sorted(data, key=lambda r: r["std_dev"])
    for row in data:
        assert row["floor"] <= row["ceiling"]


def test_all_play_standings(client: TestClient) -> None:
    data = _get_stat(client, "all-play-standings")
    # Roster 1 tops the league every week except week 3 (roster 3 scores 118),
    # so it wins 8 of 9 virtual matchups.
    row1 = next(r for r in data if r["roster_id"] == 1)
    assert row1["all_play_wins"] == 8
    assert row1["all_play_losses"] == 1
    assert row1["win_pct"] == pytest.approx(88.9)
    assert data[0]["roster_id"] == 1


def test_roster_efficiency(client: TestClient) -> None:
    data = _get_stat(client, "roster-efficiency")
    for row in data:
        assert 0 <= row["efficiency_pct"] <= 100
        assert len(row["series"]) == 3
        # Optimal always exceeds actual because the bench out-scores the starter.
        assert row["total_optimal_points"] >= row["total_actual_points"]


def test_bench_points_ranking(client: TestClient) -> None:
    data = _get_stat(client, "bench-points-ranking")
    # Each team leaves exactly 5 bench points per week across 3 weeks.
    for row in data:
        assert row["total_bench_points"] == pytest.approx(15.0)
        assert row["worst_week"] in (1, 2, 3)


def test_margin_of_victory(client: TestClient) -> None:
    data = _get_stat(client, "margin-of-victory")
    row1 = next(r for r in data if r["roster_id"] == 1)
    # Roster 1 margins vs roster 2: +30, +35, +3 (the last a nailbiter).
    assert sorted(row1["margins"]) == [3.0, 30.0, 35.0]
    assert row1["nailbiters"] == 1


def test_cumulative_points_race(client: TestClient) -> None:
    data = _get_stat(client, "cumulative-points-race")
    row1 = next(r for r in data if r["roster_id"] == 1)
    assert [pt["cumulative_points"] for pt in row1["series"]] == [120.0, 250.0, 365.0]
    assert row1["total_points"] == pytest.approx(365.0)
    # Highest total leads.
    assert data[0]["roster_id"] == 1
