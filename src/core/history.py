"""History persistence helpers for detections and streams."""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import uuid

from PIL import Image

from src.api.schemas import DetectionBoxOut, HistoryEvent
from src.config.settings import get_settings
from src.utils.detection import is_head_class, is_nonhelmet_class
from src.utils.image import save_pil_image

logger = logging.getLogger(__name__)
settings = get_settings()


def generate_event_id() -> str:
    """Return a random event identifier."""
    return uuid.uuid4().hex


def append_history_record(record: HistoryEvent) -> None:
    """Append a history event to the JSONL log."""
    try:
        with settings.history_jsonl.open("a", encoding="utf-8") as file_handle:
            file_handle.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("Failed to append a history record.")


def load_all_history() -> list[HistoryEvent]:
    """Load all history events sorted newest first."""
    if not settings.history_jsonl.is_file():
        return []

    events: list[HistoryEvent] = []
    with settings.history_jsonl.open("r", encoding="utf-8") as file_handle:
        for line in file_handle:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(HistoryEvent(**json.loads(line)))
            except Exception:
                logger.warning("Skipping an unreadable history line.", exc_info=True)

    events.sort(key=lambda event: event.timestamp, reverse=True)
    return events


def get_history_event(event_id: str) -> HistoryEvent | None:
    """Return a single history event by ID if it exists."""
    for event in load_all_history():
        if event.id == event_id:
            return event
    return None


def get_latest_history_event(source: str | None = None, types: str | None = None) -> HistoryEvent | None:
    """Return the most recent history event matching optional filters."""
    if not settings.history_jsonl.exists():
        return None

    type_filter = None
    if types:
        type_filter = {item.strip().upper() for item in types.split(",") if item.strip()}

    with settings.history_jsonl.open("r", encoding="utf-8") as file_handle:
        lines = file_handle.readlines()

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            event = HistoryEvent(**json.loads(line))
        except Exception:
            logger.warning("Skipping an unreadable history line.", exc_info=True)
            continue

        if source is not None and event.source != source:
            continue
        if type_filter is not None and event.type not in type_filter:
            continue
        return event

    return None


def persist_image_event(
    image: Image.Image,
    boxes: list[DetectionBoxOut],
    source: str,
    event_type: str,
) -> HistoryEvent | None:
    """Persist an image detection event and its relevant crops."""
    crop_candidates = [
        (box.class_name, box.x1, box.y1, box.x2, box.y2)
        for box in boxes
        if is_head_class(box.class_name) or is_nonhelmet_class(box.class_name)
    ]
    return persist_window_event(
        image=image,
        source=source,
        event_type=event_type,
        crop_candidates=crop_candidates,
    )


def persist_window_event(
    image: Image.Image,
    source: str,
    event_type: str,
    crop_candidates: list[tuple[str, int, int, int, int]],
) -> HistoryEvent | None:
    """Persist a stream or video event plus its cropped violator images."""
    if event_type == "NONE":
        return None

    event_id = generate_event_id()
    timestamp = datetime.now().isoformat()
    global_filename = f"{event_id}.jpg"
    global_path = settings.history_global_dir / global_filename
    save_pil_image(image, global_path)

    crop_urls: list[str] = []
    crop_index = 0
    for class_name, x1, y1, x2, y2 in crop_candidates:
        if event_type == "VI_PHAM" and not is_head_class(class_name):
            continue
        if event_type == "NGHI_NGO" and not is_nonhelmet_class(class_name):
            continue
        if x2 <= x1 or y2 <= y1:
            continue

        crop = image.crop((x1, y1, x2, y2))
        crop_filename = f"{event_id}_{crop_index}.jpg"
        crop_path = settings.history_crops_dir / crop_filename
        save_pil_image(crop, crop_path)
        crop_urls.append(f"/static/history/crops/{crop_filename}")
        crop_index += 1

    history_record = HistoryEvent(
        id=event_id,
        timestamp=timestamp,
        source=source,
        type=event_type,
        global_image_url=f"/static/history/global/{global_filename}",
        crop_image_urls=crop_urls,
        num_violators=len(crop_urls) if crop_urls else 1,
    )
    append_history_record(history_record)
    return history_record


def resolve_history_image_path(image_reference: str) -> Path:
    """Resolve a stored image reference back to a local filesystem path."""
    normalized = image_reference.replace("\\", "/").strip()
    absolute = Path(normalized)
    if absolute.is_absolute() and absolute.exists():
        return absolute

    basename = Path(normalized).name
    history_candidate = settings.history_global_dir / basename
    if history_candidate.exists():
        return history_candidate

    relative = normalized.lstrip("/")
    candidate_in_data = settings.data_dir / relative
    candidate_from_root = settings.root_dir / relative
    if candidate_in_data.exists():
        return candidate_in_data
    if candidate_from_root.exists():
        return candidate_from_root

    return history_candidate
