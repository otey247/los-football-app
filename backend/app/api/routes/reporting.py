"""API routes for data, reporting & instrumentation.

Covers the league's reporting surface: stat exports, the historical season
archive, custom week-range analytics, saved/scheduled reports emailed to the
commissioner, product-usage analytics, a scoring-settings reader, a multi-league
aggregate dashboard, Sleeper cache/rate-limit analytics, a data-freshness/health
monitor, team benchmarking, and a correlation explorer.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.api.routes.sleeper import (
    STAT_META,
    _handle_sleeper_error,
    _requested_week,
    _resolve_stat,
)
from app.core.config import settings
from app.models import (
    Message,
    ScheduledReport,
    ScheduledReportCreate,
    ScheduledReportPublic,
    ScheduledReportsPublic,
    ScheduledReportUpdate,
    UsageEvent,
    UsageEventCreate,
    UsageSummary,
    UsageSummaryRow,
)
from app.services import reporting as rpt
from app.services import sleeper as svc
from app.utils import send_email

router = APIRouter(prefix="/reporting", tags=["reporting"])


def _resolve_league(league_id: str) -> str:
    lid = league_id or settings.SLEEPER_LEAGUE_ID
    if not lid:
        raise HTTPException(
            status_code=400,
            detail="No league_id provided and SLEEPER_LEAGUE_ID is not configured",
        )
    return lid


@router.get("/meta")
def get_reporting_meta() -> dict[str, Any]:
    """Describe the reporting features available."""
    return {
        "emails_enabled": settings.emails_enabled,
        "features": [
            {"key": "exports", "title": "Stat Exports", "description": "Download any stat card as CSV or JSON."},
            {"key": "season-archive", "title": "Season Archive", "description": "Cross-season standings, champions and all-time records."},
            {"key": "scoring-settings", "title": "Scoring Settings", "description": "The league's scoring format and roster rules."},
            {"key": "multi-league", "title": "Multi-League View", "description": "Aggregate standings across all of a manager's leagues."},
            {"key": "cache-stats", "title": "Cache & Rate Limit", "description": "Sleeper cache hit-rate and request volume."},
            {"key": "health", "title": "Data Health", "description": "Freshness monitor flagging stale or failed syncs."},
            {"key": "benchmark", "title": "Benchmarking", "description": "A team's metrics vs league and historical averages."},
            {"key": "correlations", "title": "Correlation Explorer", "description": "Relationships between team-level metrics."},
            {"key": "scheduled-reports", "title": "Scheduled Reports", "description": "Saved reports emailed to the commissioner."},
        ],
    }


# ---------------------------------------------------------------------------
# #76 Historical season archive
# ---------------------------------------------------------------------------
@router.get("/season-archive")
def get_season_archive(league_id: str = Query(default="")) -> Any:
    lid = _resolve_league(league_id)
    try:
        return rpt.season_archive(lid)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


# ---------------------------------------------------------------------------
# #80 Scoring-settings reader
# ---------------------------------------------------------------------------
@router.get("/scoring-settings")
def get_scoring_settings(league_id: str = Query(default="")) -> Any:
    lid = _resolve_league(league_id)
    try:
        return rpt.scoring_settings_summary(lid)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


# ---------------------------------------------------------------------------
# #81 Multi-league aggregate dashboard
# ---------------------------------------------------------------------------
@router.get("/multi-league")
def get_multi_league(
    username: str = Query(..., min_length=1),
    season: str = Query(default=""),
) -> Any:
    season_val = season
    if not season_val:
        try:
            season_val = str(svc.get_nfl_state().get("season") or "")
        except Exception:  # noqa: BLE001
            season_val = ""
    if not season_val:
        raise HTTPException(status_code=400, detail="Could not determine the NFL season")
    try:
        return rpt.multi_league_dashboard(username.strip(), season_val)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc)


# ---------------------------------------------------------------------------
# #82 Cache + rate-limit analytics
# ---------------------------------------------------------------------------
@router.get("/cache-stats")
def get_cache_stats() -> dict[str, Any]:
    return svc.get_cache_metrics()


# ---------------------------------------------------------------------------
# #83 Data-freshness / health monitor
# ---------------------------------------------------------------------------
@router.get("/health")
def get_health() -> Any:
    endpoints = svc.get_endpoint_health()
    metrics = svc.get_cache_metrics()

    nfl_state: dict[str, Any] = {}
    try:
        nfl_state = svc.get_nfl_state()
    except Exception:  # noqa: BLE001
        nfl_state = {}

    alerts: list[dict[str, Any]] = []
    for ep in endpoints:
        # A more recent error than success means the last sync failed.
        err_age = ep["last_error_age_seconds"]
        ok_age = ep["last_success_age_seconds"]
        if err_age is not None and (ok_age is None or err_age < ok_age):
            alerts.append(
                {
                    "level": "error",
                    "endpoint": ep["endpoint"],
                    "message": ep["last_error_message"] or "Last sync failed",
                }
            )
    if metrics["calls_last_minute"] >= svc.RATE_LIMIT_PER_MINUTE * 0.8:
        alerts.append(
            {
                "level": "warning",
                "endpoint": "rate-limit",
                "message": f"{metrics['calls_last_minute']} calls in the last minute "
                f"(limit {metrics['rate_limit_per_minute']})",
            }
        )

    status = "ok"
    if any(a["level"] == "error" for a in alerts):
        status = "error"
    elif alerts:
        status = "warning"

    return {
        "status": status,
        "season": nfl_state.get("season"),
        "week": nfl_state.get("week"),
        "season_type": nfl_state.get("season_type"),
        "endpoints": endpoints,
        "metrics": metrics,
        "alerts": alerts,
    }


# ---------------------------------------------------------------------------
# #84 Benchmarking
# ---------------------------------------------------------------------------
@router.get("/benchmark")
def get_benchmark(
    roster_id: int = Query(..., ge=1),
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
    start_week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    lid = _resolve_league(league_id)
    through = _requested_week(lid, week)
    try:
        with svc.week_window(start_week):
            return rpt.benchmark(lid, roster_id, through)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


# ---------------------------------------------------------------------------
# #85 Correlation explorer
# ---------------------------------------------------------------------------
@router.get("/correlations")
def get_correlations(
    league_id: str = Query(default=""),
    week: int | None = Query(default=None, ge=1, le=18),
    start_week: int | None = Query(default=None, ge=1, le=18),
) -> Any:
    lid = _resolve_league(league_id)
    through = _requested_week(lid, week)
    try:
        with svc.week_window(start_week):
            return rpt.correlations(lid, through)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)


# ---------------------------------------------------------------------------
# #79 Product usage analytics
# ---------------------------------------------------------------------------
@router.post("/usage", status_code=201)
def record_usage(
    *, session: SessionDep, current_user: CurrentUser, body: UsageEventCreate
) -> Message:
    """Record a product-usage event (which cards/views are engaged with)."""
    event = UsageEvent(
        event_type=body.event_type,
        target=body.target,
        path=body.path,
        user_id=current_user.id,
    )
    session.add(event)
    session.commit()
    return Message(message="recorded")


@router.get(
    "/usage/summary",
    dependencies=[Depends(get_current_active_superuser)],
)
def usage_summary(*, session: SessionDep, limit: int = Query(default=50, le=500)) -> UsageSummary:
    """Aggregate usage counts by event type + target (super admin)."""
    total = session.exec(select(func.count()).select_from(UsageEvent)).one()
    stmt = (
        select(
            UsageEvent.event_type,
            UsageEvent.target,
            func.count().label("count"),
        )
        .group_by(UsageEvent.event_type, UsageEvent.target)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = [
        UsageSummaryRow(event_type=et, target=tgt, count=count)
        for et, tgt, count in session.exec(stmt).all()
    ]
    return UsageSummary(total_events=int(total), rows=rows)


# ---------------------------------------------------------------------------
# #78 Saved / scheduled reports emailed to the commissioner
# ---------------------------------------------------------------------------
def _report_to_public(report: ScheduledReport) -> ScheduledReportPublic:
    return ScheduledReportPublic.model_validate(report, from_attributes=True)


@router.get(
    "/reports",
    dependencies=[Depends(get_current_active_superuser)],
)
def list_reports(*, session: SessionDep) -> ScheduledReportsPublic:
    reports = session.exec(
        select(ScheduledReport).order_by(ScheduledReport.created_at.desc())  # type: ignore[union-attr]
    ).all()
    return ScheduledReportsPublic(
        data=[_report_to_public(r) for r in reports], count=len(reports)
    )


@router.post(
    "/reports",
    dependencies=[Depends(get_current_active_superuser)],
)
def create_report(
    *, session: SessionDep, current_user: CurrentUser, body: ScheduledReportCreate
) -> ScheduledReportPublic:
    report = ScheduledReport.model_validate(
        body, update={"owner_id": current_user.id}
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return _report_to_public(report)


@router.patch(
    "/reports/{report_id}",
    dependencies=[Depends(get_current_active_superuser)],
)
def update_report(
    *, session: SessionDep, report_id: uuid.UUID, body: ScheduledReportUpdate
) -> ScheduledReportPublic:
    report = session.get(ScheduledReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    update = body.model_dump(exclude_unset=True)
    report.sqlmodel_update(update)
    report.updated_at = datetime.now(timezone.utc)
    session.add(report)
    session.commit()
    session.refresh(report)
    return _report_to_public(report)


@router.delete(
    "/reports/{report_id}",
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_report(*, session: SessionDep, report_id: uuid.UUID) -> Message:
    report = session.get(ScheduledReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    session.delete(report)
    session.commit()
    return Message(message="Report deleted")


def _build_report_html(report: ScheduledReport, week: int) -> str:
    """Render the report's stat cards into a simple HTML email body."""
    lid = _resolve_league(report.league_id)
    keys = [k.strip() for k in report.stat_keys.split(",") if k.strip()]
    titles = {m["key"]: m["title"] for m in STAT_META}
    sections: list[str] = [f"<h1>{report.name}</h1>", f"<p>Week {week}</p>"]
    for key in keys:
        try:
            fn, _ = _resolve_stat(key, lid)
            rows = fn(lid, week)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(rows, list) or not rows:
            continue
        sections.append(f"<h2>{titles.get(key, key)}</h2>")
        top = rows[:10]
        headers = [
            k
            for k in top[0]
            if not isinstance(top[0][k], list | dict)
            and k not in {"roster_id", "avatar", "player_id"}
        ]
        head_html = "".join(f"<th align='left'>{h}</th>" for h in headers)
        body_rows = ""
        for row in top:
            cells = "".join(f"<td>{row.get(h, '')}</td>" for h in headers)
            body_rows += f"<tr>{cells}</tr>"
        sections.append(
            f"<table border='1' cellpadding='6' cellspacing='0'>"
            f"<thead><tr>{head_html}</tr></thead><tbody>{body_rows}</tbody></table>"
        )
    return "\n".join(sections)


@router.post(
    "/reports/{report_id}/send",
    dependencies=[Depends(get_current_active_superuser)],
)
def send_report(*, session: SessionDep, report_id: uuid.UUID) -> Any:
    """Build a report and email it to its recipient (or preview if email off)."""
    report = session.get(ScheduledReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    lid = _resolve_league(report.league_id)
    week = _requested_week(lid, None)
    try:
        html = _build_report_html(report, week)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_sleeper_error(exc, lid)
        return  # unreachable

    subject = f"{report.name} — Week {week}"
    if not settings.emails_enabled:
        return {
            "sent": False,
            "reason": "Email is not configured (SMTP settings missing).",
            "preview_html": html,
        }
    send_email(
        email_to=report.recipient_email, subject=subject, html_content=html
    )
    report.last_sent_at = datetime.now(timezone.utc)
    session.add(report)
    session.commit()
    return {"sent": True, "recipient": report.recipient_email, "subject": subject}
