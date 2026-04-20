"""Singleton person detector (YOLOv8n/COCO) for the person-first pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock
from typing import ClassVar

import numpy as np
from ultralytics import YOLO

from src.config.settings import Settings, get_settings
from src.utils.image import clamp_bbox

logger = logging.getLogger(__name__)

# COCO class index for "person"
_PERSON_CLASS_ID = 0


class PersonDetector:
    """Load and serve a lightweight person-detection model exactly once.

    Mirrors the singleton pattern of ``Predictor``.  The underlying model
    (YOLOv8n by default) only detects COCO class 0 (person) and is always
    run on CPU for compatibility with ONNX / HF Spaces deployments.
    """

    _instance: ClassVar["PersonDetector | None"] = None
    _instance_lock: ClassVar[Lock] = Lock()

    def __new__(cls, settings: Settings | None = None) -> "PersonDetector":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, settings: Settings | None = None) -> None:
        if getattr(self, "_initialized", False):
            return
        self.settings = settings or get_settings()
        self._model: YOLO | None = None
        self._device: str | int = "cpu"
        self._model_lock = Lock()
        self._initialized = True

    @property
    def is_loaded(self) -> bool:
        """Return True if the person model is ready for inference."""
        return self._model is not None

    def load_model(self, force: bool = False) -> None:
        """Load the configured person-detection model into memory once."""
        with self._model_lock:
            if self._model is not None and not force:
                return
            path = self.settings.person_model_path
            self._device = self._select_device(path)
            logger.info("Loading person detector from %s on device %s", path, self._device)
            self._model = YOLO(str(path))
            logger.info("Person detector loaded (%s).", path)

    # ── Public inference helpers ──────────────────────────────────────────────

    def detect_persons(
        self, frame: np.ndarray
    ) -> list[tuple[int, int, int, int, float]]:
        """Detect persons in a BGR frame (no tracking).

        Returns a list of ``(x1, y1, x2, y2, confidence)`` tuples in pixel
        coordinates clamped to the frame bounds.
        """
        if self._model is None:
            self.load_model()
        assert self._model is not None  # noqa: S101

        results = self._model.predict(
            frame,
            conf=self.settings.person_confidence_threshold,
            classes=[_PERSON_CLASS_ID],
            verbose=False,
            device=self._device,
        )
        return self._extract_boxes(frame, results)

    def track_persons(
        self, frame: np.ndarray, tracker: str = "bytetrack.yaml"
    ) -> list[tuple[int, int, int, int, float, int | None]]:
        """Track persons in a BGR frame via ByteTrack (persistent state).

        Returns a list of ``(x1, y1, x2, y2, confidence, track_id)`` tuples.
        ``track_id`` is ``None`` when ByteTrack has not yet confirmed the track.

        Note: uses ``persist=True``, so tracker state is shared across calls
        (same single-user demo caveat as the main ``Predictor``).
        """
        if self._model is None:
            self.load_model()
        assert self._model is not None  # noqa: S101

        results = self._model.track(
            frame,
            tracker=tracker,
            persist=True,
            conf=self.settings.person_confidence_threshold,
            classes=[_PERSON_CLASS_ID],
            verbose=False,
            device=self._device,
        )
        return self._extract_tracked_boxes(frame, results)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _select_device(self, model_path: Path) -> str | int:
        """Choose the best available device for the person-detection model.

        Mirrors Predictor._select_device.  ONNX models prefer CUDAExecutionProvider
        when onnxruntime-gpu is installed; .pt models prefer torch CUDA; both fall
        back to CPU.  ONNX_EXECUTION_PROVIDER env var overrides auto-detection.
        """
        suffix = model_path.suffix.lower()
        if suffix == ".onnx":
            override = self.settings.onnx_execution_provider
            if override:
                return "cpu" if "CPU" in override.upper() else 0
            try:
                import onnxruntime as ort
                if "CUDAExecutionProvider" in ort.get_available_providers():
                    return 0
            except Exception:
                logger.debug("ONNX Runtime provider check failed for person model; using CPU.", exc_info=True)
            return "cpu"

        try:
            import torch
            if torch.cuda.is_available():
                return 0
        except Exception:
            logger.debug("CUDA detection failed for person model; using CPU.", exc_info=True)
        return "cpu"

    def _extract_boxes(
        self, frame: np.ndarray, results: list
    ) -> list[tuple[int, int, int, int, float]]:
        persons: list[tuple[int, int, int, int, float]] = []
        if not results:
            return persons
        result = results[0]
        if result.boxes is None:
            return persons
        h, w = frame.shape[:2]
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0].item())
            x1_i, y1_i, x2_i, y2_i = clamp_bbox(x1, y1, x2, y2, width=w, height=h)
            if x2_i - x1_i > 5 and y2_i - y1_i > 5:
                persons.append((x1_i, y1_i, x2_i, y2_i, conf))
        return persons

    def _extract_tracked_boxes(
        self, frame: np.ndarray, results: list
    ) -> list[tuple[int, int, int, int, float, int | None]]:
        persons: list[tuple[int, int, int, int, float, int | None]] = []
        if not results:
            return persons
        result = results[0]
        boxes = result.boxes
        if boxes is None:
            return persons
        has_ids = boxes.id is not None
        h, w = frame.shape[:2]
        for i in range(len(boxes)):
            box = boxes[i]
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0].item())
            x1_i, y1_i, x2_i, y2_i = clamp_bbox(x1, y1, x2, y2, width=w, height=h)
            if x2_i - x1_i <= 5 or y2_i - y1_i <= 5:
                continue
            track_id: int | None = None
            if has_ids:
                val = boxes.id[i].item()
                if val == val:  # NaN != NaN check
                    track_id = int(val)
            persons.append((x1_i, y1_i, x2_i, y2_i, conf, track_id))
        return persons


def get_person_detector() -> PersonDetector:
    """Return the singleton PersonDetector instance."""
    return PersonDetector(get_settings())
