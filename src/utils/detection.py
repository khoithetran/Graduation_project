"""Detection-specific utility helpers."""

from __future__ import annotations

from src.api.schemas import DetectionBoxOut


def normalize_class_name(name: str) -> str:
    """Normalize class names so variants can be compared reliably."""
    return name.strip().lower().replace(" ", "").replace("_", "-")


def is_head_class(name: str) -> bool:
    """Return True when the class name refers to an uncovered head."""
    return normalize_class_name(name) == "head"


def is_nonhelmet_class(name: str) -> bool:
    """Return True when the class name refers to a suspected no-helmet class."""
    return normalize_class_name(name) in {
        "non-helmet",
        "nonhelmet",
        "no-helmet",
        "nohelmet",
    }


def classify_event(boxes: list[DetectionBoxOut]) -> str:
    """Classify an image event based on the detected classes."""
    if any(is_head_class(box.class_name) for box in boxes):
        return "VI_PHAM"
    if any(is_nonhelmet_class(box.class_name) for box in boxes):
        return "NGHI_NGO"
    return "NONE"


def detection_color(class_name: str) -> tuple[int, int, int]:
    """Return a BGR color for drawing a detection box."""
    if is_head_class(class_name):
        return (0, 0, 255)
    if is_nonhelmet_class(class_name):
        return (0, 215, 255)
    return (0, 255, 0)
