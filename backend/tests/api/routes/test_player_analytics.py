"""Tests for the player-analytics routes (TODO 2.2, #51–58).

The Sleeper service is mocked at the low-level fetch helpers so the analytics
math runs against deterministic fixtures without any network calls.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import sleeper as svc

LEAGUE_ID = "test-league"
BASE = f"{settings.API_V1_STR}/player-analytics"

_PLAYERS: dict[str, dict[str, Any]] = {
    "p_qb1": {"full_name": "QB One", "position": "QB", "team": "KC", "years_exp": 5},
    "p_rb1": {
        "full_name": "RB Rookie",
        "position": "RB",
        "team": "SF",
        "years_exp": 0,
        "injury_status": "Questionable",
    },
    "p_wr1": {"full_name": "WR One", "position": "WR", "team": "MIA", "years_exp": 1},
    "p_def1": {"full_name": "D/ST One", "position": "DEF", "team": "DAL"},
    "p_k1": {"full_name": "Kicker One", "position": "K", "team": "BUF"},
}

# roster_id -> players
_ROSTER_PLAYERS = {
    1: ["p_qb1", "p_rb1", "p_def1"],
    2: ["p_wr1", "p_k1"],
}

# week -> roster_id -> {pid: points}
_WEEK_POINTS: dict[int, dict[int, dict[str, float]]] = {
    1: {1: {"p_qb1": 20.0, "p_rb1": 5.0, "p_def1": 8.0}, 2: {"p_wr1": 12.0, "p_k1": 9.0}},
    2: {1: {"p_qb1": 22.0, "p_rb1": 14.0, "p_def1": 6.0}, 2: {"p_wr1": 4.0, "p_k1": 7.0}},
    3: {1: {"p_qb1": 18.0, "p_rb1": 25.0, "p_def1": 10.0}, 2: {"p_wr1": 30.0, "p_k1": 8.0}},
}


@pytest.fixture(autouse=True)
def _mock_sleeper(monkeypatch: pytest.MonkeyPatch) -> None:
    def league(_lid: str) -> dict[str, Any]:
        return {
            "season": "2024",
            "settings": {"last_scored_leg": 3, "playoff_week_start": 15},
            "roster_positions": ["QB", "RB", "WR", "TE", "FLEX", "K", "DEF"],
        }

    def users(_lid: str) -> list[dict[str, Any]]:
        return [
            {"user_id": "u1", "display_name": "Alpha", "avatar": None},
            {"user_id": "u2", "display_name": "Beta", "avatar": None},
        ]

    def rosters(_lid: str) -> list[dict[str, Any]]:
        return [
            {"roster_id": 1, "owner_id": "u1", "players": _ROSTER_PLAYERS[1]},
            {"roster_id": 2, "owner_id": "u2", "players": _ROSTER_PLAYERS[2]},
        ]

    def matchups(_lid: str, week: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for rid, pts in _WEEK_POINTS.get(week, {}).items():
            rows.append({
                "roster_id": rid,
                "matchup_id": 1,
                "points": sum(pts.values()),
                "starters": list(pts.keys()),
                "players": list(pts.keys()),
                "players_points": pts,
            })
        return rows

    def player_stats(_season: str, week: int, _season_type: str = "regular") -> dict[str, Any]:
        return {
            "p_rb1": {"rush_att": 10 + week, "rec_tgt": 4, "off_snp": 40, "tm_off_snp": 60},
            "p_wr1": {"rush_att": 0, "rec_tgt": 8 + week, "off_snp": 50, "tm_off_snp": 60},
        }

    monkeypatch.setattr(svc, "get_league", league)
    monkeypatch.setattr(svc, "get_users", users)
    monkeypatch.setattr(svc, "get_rosters", rosters)
    monkeypatch.setattr(svc, "get_matchups", matchups)
    monkeypatch.setattr(svc, "get_nfl_players", lambda: _PLAYERS)
    monkeypatch.setattr(svc, "get_player_stats", player_stats)
    monkeypatch.setattr(svc, "get_nfl_state", lambda: {"week": 3, "season": "2024"})


def test_meta_lists_all_player_stats(client: TestClient) -> None:
    res = client.get(f"{BASE}/meta")
    assert res.status_code == 200
    keys = {row["key"] for row in res.json()}
    assert keys == {
        "player-consistency",
        "positional-breakdown",
        "usage-trends",
        "points-above-replacement",
        "buy-low-sell-high",
        "injury-impact",
        "rookie-breakout-watch",
        "streaming-tracker",
    }


def test_unknown_stat_returns_404(client: TestClient) -> None:
    res = client.get(f"{BASE}/stats/not-a-stat", params={"league_id": LEAGUE_ID})
    assert res.status_code == 404


def test_player_consistency(client: TestClient) -> None:
    res = client.get(f"{BASE}/stats/player-consistency", params={"league_id": LEAGUE_ID})
    assert res.status_code == 200
    rows = res.json()
    assert rows, "expected at least one rostered player"
    qb = next(r for r in rows if r["player_id"] == "p_qb1")
    assert qb["games"] == 3
    assert qb["ceiling"] == 22.0
    assert qb["floor"] == 18.0
    assert qb["classification"] == "Consistent"  # low variance
    assert qb["display_name"] == "Alpha"


def test_positional_breakdown_sums_starting_points(client: TestClient) -> None:
    res = client.get(f"{BASE}/stats/positional-breakdown", params={"league_id": LEAGUE_ID})
    assert res.status_code == 200
    rows = res.json()
    alpha = next(r for r in rows if r["display_name"] == "Alpha")
    # QB points across the 3 weeks: 20 + 22 + 18 = 60
    assert alpha["qb_points"] == 60.0
    # RB: 5 + 14 + 25 = 44, DEF: 8 + 6 + 10 = 24, total = 128
    assert alpha["total_points"] == 128.0
    assert abs(sum(alpha[f"{g}_pct"] for g in ("qb", "rb", "wr", "te", "k", "def", "flex")) - 100.0) < 0.5


def test_usage_trends_uses_player_stats(client: TestClient) -> None:
    res = client.get(f"{BASE}/stats/usage-trends", params={"league_id": LEAGUE_ID})
    assert res.status_code == 200
    rows = res.json()
    wr = next(r for r in rows if r["player_id"] == "p_wr1")
    assert wr["games"] == 3
    assert wr["snap_share_pct"] == pytest.approx(50 / 60 * 100, abs=0.1)
    assert wr["avg_targets"] > 0


def test_points_above_replacement(client: TestClient) -> None:
    res = client.get(
        f"{BASE}/stats/points-above-replacement", params={"league_id": LEAGUE_ID}
    )
    assert res.status_code == 200
    rows = res.json()
    assert all("vorp" in r for r in rows)


def test_buy_low_sell_high_flags(client: TestClient) -> None:
    res = client.get(f"{BASE}/stats/buy-low-sell-high", params={"league_id": LEAGUE_ID})
    assert res.status_code == 200
    rows = res.json()
    assert all(r["flag"] in ("Buy Low", "Sell High") for r in rows)


def test_injury_impact_flags_questionable_player(client: TestClient) -> None:
    res = client.get(f"{BASE}/stats/injury-impact", params={"league_id": LEAGUE_ID})
    assert res.status_code == 200
    rows = res.json()
    alpha = next(r for r in rows if r["display_name"] == "Alpha")
    injured_names = {p["player_name"] for p in alpha["injured"]}
    assert "RB Rookie" in injured_names


def test_rookie_breakout_watch_includes_rookie(client: TestClient) -> None:
    res = client.get(
        f"{BASE}/stats/rookie-breakout-watch", params={"league_id": LEAGUE_ID}
    )
    assert res.status_code == 200
    rows = res.json()
    rookie = next(r for r in rows if r["player_id"] == "p_rb1")
    assert rookie["flag"] == "Rookie"
    assert rookie["years_exp"] == 0


def test_streaming_tracker_only_qb_k_def(client: TestClient) -> None:
    res = client.get(f"{BASE}/stats/streaming-tracker", params={"league_id": LEAGUE_ID})
    assert res.status_code == 200
    rows = res.json()
    assert rows
    assert all(r["position"] in ("QB", "K", "DEF") for r in rows)
