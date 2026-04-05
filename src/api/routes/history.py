"""History endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import HistoryEvent, HistoryLatestResponse
from src.core.history import get_history_event, get_latest_history_event, load_all_history

router = APIRouter(tags=["history"])


@router.get("/api/history/latest", response_model=HistoryLatestResponse)
def latest_history(
    source: str | None = Query(None, description="Optional source filter."),
    types: str | None = Query(None, description="Comma-separated event types."),
) -> HistoryLatestResponse:
    """Return the most recent history event matching the filters."""
    return HistoryLatestResponse(event=get_latest_history_event(source=source, types=types))


@router.get("/api/history", response_model=list[HistoryEvent])
def history_list() -> list[HistoryEvent]:
    """Return the full history newest first."""
    return load_all_history()


@router.get("/api/history/{event_id}", response_model=HistoryEvent)
def history_detail(event_id: str) -> HistoryEvent:
    """Return a single history event by ID."""
    event = get_history_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="History event was not found.")
    return event
