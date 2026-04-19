"""LLM violation report endpoints."""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from src.api.schemas import AlertReportRequest, EventReport, SimpleAlertItem
from src.core.history import load_all_history
from src.core.llm_reporter import (
    bulk_generate_reports,
    generate_from_alert,
    get_or_generate_report_for_event,
)
from src.core.pdf_builder import build_pdf, build_simple_pdf

router = APIRouter(tags=["report"])


@router.post("/api/report/from-alert", response_model=EventReport)
def report_from_alert(
    body: AlertReportRequest,
    alert_id: str = Query(..., description="Unique alert ID used for caching"),
) -> EventReport:
    """Generate (or return cached) report for a live/video alert."""
    return generate_from_alert(body, alert_id)


@router.get("/api/report/event/{event_id}", response_model=EventReport)
def report_for_event(event_id: str) -> EventReport:
    """Generate (or return cached) report for a HistoryEvent."""
    report = get_or_generate_report_for_event(event_id)
    if report is None:
        raise HTTPException(status_code=404, detail="History event not found.")
    return report


@router.post("/api/report/simple-pdf")
def download_simple_pdf(alerts: list[SimpleAlertItem]) -> FileResponse:
    """Generate and download a PDF from the current session's alert list (no LLM)."""
    if not alerts:
        raise HTTPException(status_code=400, detail="Danh sach vi pham trong.")

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    output_path = Path(tmp.name)
    tmp.close()

    build_simple_pdf(alerts=alerts, output_path=output_path)

    filename = f"vi_pham_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return FileResponse(path=str(output_path), media_type="application/pdf", filename=filename)


@router.get("/api/report/download")
def download_report(hours: int = Query(4, ge=1, le=168)) -> FileResponse:
    """Compile and download a PDF report for the last N hours of violations."""
    cutoff = datetime.now() - timedelta(hours=hours)
    events = [
        e for e in load_all_history()
        if datetime.fromisoformat(e.timestamp) >= cutoff
    ]

    if not events:
        raise HTTPException(
            status_code=404,
            detail=f"No events in the last {hours} hours.",
        )

    reports = bulk_generate_reports(events)
    period_label = f"{hours}h to {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    output_path = Path(tmp.name)
    tmp.close()

    build_pdf(events=events, reports=reports, period_label=period_label, output_path=output_path)

    filename = f"bao_cao_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return FileResponse(path=str(output_path), media_type="application/pdf", filename=filename)
