"""Update-pool management endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import (
    UpdateAutoLabelResponse,
    UpdateCandidatesResponse,
    UpdateMarkRequest,
    UpdateMarkResponse,
    UpdateStartResponse,
    UpdateStatusResponse,
)
from src.core.predictor import get_predictor
from src.core.update_pool import (
    get_auto_label,
    get_update_candidates,
    get_update_status,
    mark_update_request,
    start_update_finetune,
)

router = APIRouter(tags=["update"])
logger = logging.getLogger(__name__)


@router.get("/api/update/candidates", response_model=UpdateCandidatesResponse)
def update_candidates(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
) -> UpdateCandidatesResponse:
    """Return paged update candidates."""
    return get_update_candidates(page=page, page_size=page_size)


@router.get("/api/update/auto-label/{event_id}", response_model=UpdateAutoLabelResponse)
def update_auto_label(event_id: str) -> UpdateAutoLabelResponse:
    """Return auto-label suggestions for a reviewed event."""
    predictor = get_predictor()
    try:
        return get_auto_label(event_id=event_id, predictor=predictor)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Auto-label generation failed.")
        raise HTTPException(status_code=500, detail="Auto-label generation failed.") from exc


@router.post("/api/update/mark", response_model=UpdateMarkResponse)
def update_mark(request: UpdateMarkRequest) -> UpdateMarkResponse:
    """Approve or reject an update candidate."""
    predictor = get_predictor()
    try:
        return mark_update_request(req=request, predictor=predictor)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to record update review.")
        raise HTTPException(status_code=500, detail="Failed to record update review.") from exc


@router.post("/api/update/start", response_model=UpdateStartResponse)
def update_start() -> UpdateStartResponse:
    """Return the placeholder status for the future fine-tuning workflow."""
    return start_update_finetune()


@router.get("/api/update/status", response_model=UpdateStatusResponse)
def update_status() -> UpdateStatusResponse:
    """Return update-pool readiness details."""
    return get_update_status()
