"""Update-pool review and auto-label helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import shutil

from src.api.schemas import (
    UpdateAutoLabelResponse,
    UpdateCandidatesResponse,
    UpdateMarkRequest,
    UpdateMarkResponse,
    UpdateStartResponse,
    UpdateStatusResponse,
)
from src.config.settings import get_settings
from src.core.history import get_history_event, load_all_history, resolve_history_image_path
from src.core.predictor import Predictor

logger = logging.getLogger(__name__)
settings = get_settings()

CLASS_NAME_TO_ID = {
    "helmet": 0,
    "head": 1,
    "non-helmet": 2,
}


def get_update_pool_images() -> list[Path]:
    """Return image files currently stored in the update pool."""
    extensions = {".jpg", ".jpeg", ".png"}
    if not settings.update_pool_images_dir.exists():
        return []
    return [
        path
        for path in settings.update_pool_images_dir.iterdir()
        if path.is_file() and path.suffix.lower() in extensions
    ]


def read_marked_event_ids() -> set[str]:
    """Return IDs that have already been reviewed for the update dataset."""
    event_ids: set[str] = set()
    if not settings.update_pool_meta_path.exists():
        return event_ids

    with settings.update_pool_meta_path.open("r", encoding="utf-8") as file_handle:
        for line in file_handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                event_id = payload.get("event_id")
                if event_id:
                    event_ids.add(event_id)
            except Exception:
                logger.warning("Skipping a malformed update-pool metadata row.", exc_info=True)
    return event_ids


def get_update_candidates(page: int, page_size: int) -> UpdateCandidatesResponse:
    """Return paged history events that still need review."""
    marked_ids = read_marked_event_ids()
    filtered = [
        event
        for event in load_all_history()
        if event.id not in marked_ids and event.type in {"VI_PHAM", "NGHI_NGO"}
    ]
    filtered.sort(key=lambda event: event.timestamp, reverse=True)

    start = (page - 1) * page_size
    end = start + page_size
    return UpdateCandidatesResponse(
        total=len(filtered),
        page=page,
        page_size=page_size,
        items=filtered[start:end],
    )


def get_auto_label(event_id: str, predictor: Predictor) -> UpdateAutoLabelResponse:
    """Run YOLO auto-labeling for a reviewed history event."""
    event = get_history_event(event_id)
    if event is None:
        raise FileNotFoundError(f"History event '{event_id}' was not found.")

    image_path = resolve_history_image_path(event.global_image_url)
    if not image_path.exists():
        raise FileNotFoundError(f"Global history image was not found: {image_path}")

    boxes, class_counts = predictor.build_update_labels(image_path)
    return UpdateAutoLabelResponse(
        event_id=event.id,
        image_url=event.global_image_url,
        boxes=boxes,
        class_counts=class_counts,
    )


def mark_update_request(req: UpdateMarkRequest, predictor: Predictor) -> UpdateMarkResponse:
    """Record a user's review decision for an update candidate."""
    event = get_history_event(req.event_id)
    if event is None:
        raise FileNotFoundError(f"History event '{req.event_id}' was not found.")

    image_path = resolve_history_image_path(event.global_image_url)
    if not image_path.exists():
        raise FileNotFoundError(f"Global history image was not found: {image_path}")

    with settings.update_pool_meta_path.open("a", encoding="utf-8") as file_handle:
        file_handle.write(
            json.dumps(
                {
                    "event_id": event.id,
                    "timestamp": event.timestamp,
                    "source": event.source,
                    "type": event.type,
                    "accepted": req.accepted,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    if not req.accepted:
        return UpdateMarkResponse(ok=True, accepted=False)

    boxes, _ = predictor.build_update_labels(image_path)
    destination_stem = f"{event.id}_{image_path.stem}"
    image_destination = settings.update_pool_images_dir / f"{destination_stem}{image_path.suffix}"
    label_destination = settings.update_pool_labels_dir / f"{destination_stem}.txt"

    shutil.copy2(image_path, image_destination)
    with label_destination.open("w", encoding="utf-8") as file_handle:
        for box in boxes:
            class_id = box.class_id
            if class_id is None:
                class_id = CLASS_NAME_TO_ID.get(box.class_name, 0)
            file_handle.write(
                f"{int(class_id)} {box.xc:.6f} {box.yc:.6f} {box.width:.6f} {box.height:.6f}\n"
            )

    return UpdateMarkResponse(
        ok=True,
        accepted=True,
        image_path=str(image_destination),
        label_path=str(label_destination),
        num_boxes=len(boxes),
    )


def start_update_finetune() -> UpdateStartResponse:
    """Return the current placeholder fine-tuning status."""
    image_count = len(get_update_pool_images())
    required = settings.update_required_count
    if image_count < required:
        return UpdateStartResponse(
            ok=False,
            started=False,
            message=(
                f"Chua du so luong anh de update "
                f"(hien co {image_count}/{required})."
            ),
            count=image_count,
            required=required,
        )

    return UpdateStartResponse(
        ok=False,
        started=False,
        message=(
            "Da du anh trong update_pool. Hien tai he thong chi gom dataset "
            "de fine-tune ben ngoai, chua ho tro qua trinh fine-tune tu dong trong app."
        ),
        count=image_count,
        required=required,
    )


def get_update_status() -> UpdateStatusResponse:
    """Return the current update-pool size and readiness state."""
    image_count = len(get_update_pool_images())
    return UpdateStatusResponse(
        num_images=image_count,
        threshold=settings.update_required_count,
        ready=image_count >= settings.update_required_count,
    )
