"""Tests for the matchup & win-probability analytics routes (#59-#66).

The Sleeper client is monkeypatched with a small synthetic 4-team league so the
endpoints can be exercised without hitting the live API.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import sleeper as svc

# --- Synthetic league fixture data -----------------------------------------

LEAGUE_ID = "test-league"

_ROSTERS = [
    {"roster_id": 1, "owner_id": "u1", "players": ["a1", "a2", "a3"], "starters": ["a1", "a2"]},
    {"roster_id": 2, "owner_id": "u2", "players": ["b1", "b2", "b3"], "starters": ["b1", "b2"]},
    {"roster_id": 3, "owner_id": "u3", "players": ["c1", "c2", "c3"], "starters": ["c1", "c2"]},
    {"roster_id": 4, "owner_id": "u4", "players": ["d1", "d2", "d3"], "starters": ["d1", "d2"]},
]

_USERS = [
    {"user_id": "u1", "display_name": "Alpha", "avatar": None},
    {"user_id": "u2", "display_name": "Bravo", "avatar": None},
    {"user_id": "u3", "display_name": "Charlie", "avatar": None},
    {"user_id": "u4", "display_name": "Delta", "avatar": None},
]


def _row(rid: str, mid: int, pts: float, starters: list[str], pp: dict[str, float]) -> dict[str, Any]:
    return {
        "roster_id": int(rid),
        "matchup_id": mid,
        "points": pts,
        "starters": starters,
        "players": starters + [f"{starters[0][0]}3"],
        "starters_points": [pp.get(s, 0) for s in starters],
        "players_points": pp,
    }


_MATCHUPS: dict[int, list[dict[str, Any]]] = {
    1: [
        _row("1", 1, 120.0, ["a1", "a2"], {"a1": 70, "a2": 50, "a3": 30}),
        _row("2", 1, 100.0, ["b1", "b2"], {"b1": 60, "b2": 40, "b3": 25}),
        _row("3", 2, 90.0, ["c1", "c2"], {"c1": 50, "c2": 40, "c3": 35}),
        _row("4", 2, 110.0, ["d1", "d2"], {"d1": 65, "d2": 45, "d3": 20}),
    ],
    2: [
        _row("1", 1, 80.0, ["a1", "a2"], {"a1": 45, "a2": 35, "a3": 40}),
        _row("3", 1, 110.0, ["c1", "c2"], {"c1": 60, "c2": 50, "c3": 15}),
        _row("2", 2, 130.0, ["b1", "b2"], {"b1": 75, "b2": 55, "b3": 10}),
        _row("4", 2, 95.0, ["d1", "d2"], {"d1": 55, "d2": 40, "d3": 30}),
    ],
    # Week 3 is the upcoming (unplayed) week: pairings present, zero points.
    3: [
        _row("1", 1, 0.0, ["a1", "a2"], {}),
        _row("4", 1, 0.0, ["d1", "d2"], {}),
        _row("2", 2, 0.0, ["b1", "b2"], {}),
        _row("3", 2, 0.0, ["c1", "c2"], {}),
    ],
}

_PLAYERS = {
    pid: {"full_name": pid.upper(), "position": "WR", "team": "FA"}
    for pid in ["a1", "a2", "a3", "b1", "b2", "b3", "c1", "c2", "c3", "d1", "d2", "d3"]
}


@pytest.fixture(autouse=True)
def _patch_sleeper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "get_league", lambda lid: {
        "settings": {"playoff_week_start": 4, "playoff_teams": 2, "last_scored_leg": 2}
    })
    monkeypatch.setattr(svc, "get_rosters", lambda lid: _ROSTERS)
    monkeypatch.setattr(svc, "get_users", lambda lid: _USERS)
    monkeypatch.setattr(svc, "get_matchups", lambda lid, week: _MATCHUPS.get(week, []))
    monkeypatch.setattr(svc, "get_nfl_state", lambda: {"week": 3, "season": "2025"})
    monkeypatch.setattr(svc, "get_nfl_players", lambda: _PLAYERS)
    # Ensure a configured league id so endpoints resolve without query params.
    monkeypatch.setattr(settings, "SLEEPER_LEAGUE_ID", LEAGUE_ID)


def test_meta(client: TestClient) -> None:
    r = client.get("/api/v1/matchup/meta")
    assert r.status_code == 200
    keys = {f["key"] for f in r.json()["features"]}
    assert {"win-probability", "playoff-odds", "championship-odds"} <= keys


def test_pregame_win_probability(client: TestClient) -> None:
    r = client.get(f"/api/v1/matchup/win-probability?league_id={LEAGUE_ID}")
    assert r.status_code == 200
    body = r.json()
    assert body["week"] == 3  # upcoming week
    assert len(body["matchups"]) == 2
    for m in body["matchups"]:
        a, b = m["matchup"]
        assert 0 <= a["win_probability"] <= 100
        assert round(a["win_probability"] + b["win_probability"], 1) == 100.0


def test_live_win_probability(client: TestClient) -> None:
    r = client.get(f"/api/v1/matchup/live-win-probability?league_id={LEAGUE_ID}&week=2")
    assert r.status_code == 200
    for m in r.json()["matchups"]:
        a, b = m["matchup"]
        assert "current_points" in a
        assert round(a["win_probability"] + b["win_probability"], 1) == 100.0


def test_projection_accuracy(client: TestClient) -> None:
    r = client.get(f"/api/v1/matchup/projection-accuracy?league_id={LEAGUE_ID}")
    assert r.status_code == 200
    overall = r.json()["overall"]
    assert overall["scored_samples"] > 0
    assert 0 <= (overall["pick_accuracy"] or 0) <= 100


def test_lineup_options_and_what_if(client: TestClient) -> None:
    opts = client.get(
        f"/api/v1/matchup/lineup-options?league_id={LEAGUE_ID}&roster_id=1&week=3"
    ).json()
    assert {p["player_id"] for p in opts["starters"]} == {"a1", "a2"}
    assert [p["player_id"] for p in opts["bench"]] == ["a3"]

    res = client.post(
        "/api/v1/matchup/what-if",
        json={
            "league_id": LEAGUE_ID,
            "roster_id": 1,
            "week": 3,
            "swap_out": "a2",
            "swap_in": "a3",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["swap_out"]["player_id"] == "a2"
    assert body["swap_in"]["player_id"] == "a3"
    assert "delta" in body

    # Invalid swap (bench player not a starter) -> 400.
    bad = client.post(
        "/api/v1/matchup/what-if",
        json={"league_id": LEAGUE_ID, "roster_id": 1, "week": 3, "swap_out": "a3", "swap_in": "a2"},
    )
    assert bad.status_code == 400


def test_clinch_scenarios(client: TestClient) -> None:
    r = client.get(f"/api/v1/matchup/clinch-scenarios?league_id={LEAGUE_ID}")
    assert r.status_code == 200
    body = r.json()
    assert body["playoff_teams"] == 2
    assert len(body["teams"]) == 4
    for t in body["teams"]:
        assert t["status"] in {"clinched", "eliminated", "in_contention"}
        assert t["games_remaining"] == 1  # one remaining week (week 3)


def test_season_simulation(client: TestClient) -> None:
    r = client.get(
        f"/api/v1/matchup/season-simulation?league_id={LEAGUE_ID}&simulations=500"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["simulations"] == 500
    total = sum(t["playoff_probability"] for t in body["teams"])
    # With 2 playoff spots the probabilities should sum to ~200%.
    assert 190 <= total <= 210
    for t in body["teams"]:
        assert len(t["seed_distribution"]) == 4


def test_playoff_odds_with_trend(client: TestClient) -> None:
    r = client.get(
        f"/api/v1/matchup/playoff-odds?league_id={LEAGUE_ID}&simulations=300"
    )
    assert r.status_code == 200
    teams = r.json()["teams"]
    assert all(0 <= t["playoff_probability"] <= 100 for t in teams)
    assert all(len(t["trend"]) >= 1 for t in teams)


def test_championship_odds_and_bracket(client: TestClient) -> None:
    r = client.get(
        f"/api/v1/matchup/championship-odds?league_id={LEAGUE_ID}&simulations=500"
    )
    assert r.status_code == 200
    body = r.json()
    champ_total = sum(t["championship_probability"] for t in body["teams"])
    assert 95 <= champ_total <= 105  # exactly one champion per sim
    assert len(body["projected_bracket"]) >= 1
