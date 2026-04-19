"""APScheduler job that auto-generates PDF reports every N hours."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from src.config.settings import get_settings

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _run_scheduled_report() -> None:
    settings = get_settings()
    from src.core.history import load_all_history
    from src.core.llm_reporter import bulk_generate_reports
    from src.core.pdf_builder import build_pdf

    hours = settings.report_interval_hours
    cutoff = datetime.now() - timedelta(hours=hours)
    events = [e for e in load_all_history() if datetime.fromisoformat(e.timestamp) >= cutoff]

    if not events:
        logger.info("Scheduled report: no events in last %d hours, skipping.", hours)
        return

    logger.info("Scheduled report: processing %d events.", len(events))
    reports = bulk_generate_reports(events)

    filename = f"auto_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    output_path = settings.reports_dir / filename
    period_label = f"Auto {hours}h to {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    build_pdf(events=events, reports=reports, period_label=period_label, output_path=output_path)
    logger.info("Scheduled report saved: %s", output_path)


def start_scheduler() -> None:
    global _scheduler
    settings = get_settings()
    _scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")
    _scheduler.add_job(
        _run_scheduled_report,
        trigger="interval",
        hours=settings.report_interval_hours,
        id="auto_report",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Report scheduler started (every %dh).", settings.report_interval_hours)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Report scheduler stopped.")
    _scheduler = None
