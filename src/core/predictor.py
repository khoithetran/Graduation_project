"""Singleton YOLO predictor used across the FastAPI application."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock
from typing import Any, ClassVar

import numpy as np
from ultralytics import YOLO

from src.api.schemas import AutoLabelBox, DetectionBoxOut
from src.config.settings import Settings, get_settings
from src.utils.detection import is_head_class, is_nonhelmet_class
from src.utils.image import clamp_bbox

logger = logging.getLogger(__name__)


class Predictor:
    """Load and serve a YOLO model exactly once for the application."""

    _instance: ClassVar["Predictor" | None] = None
    _instance_lock: ClassVar[Lock] = Lock()

    def __new__(cls, settings: Settings | None = None) -> "Predictor":
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
        self._device = "cpu"
        self._model_path = self.settings.model_path
        self._model_lock = Lock()
        self._initialized = True

    @property
    def is_loaded(self) -> bool:
        """Return True if a model is currently available for inference."""
        return self._model is not None

    @property
    def device(self) -> str:
        """Return the currently selected inference device."""
        return str(self._device)

    @property
    def model_path(self) -> str:
        """Return the resolved model path as a string."""
        return str(self._model_path)

    @property
    def model_format(self) -> str:
        """Return the model file extension."""
        return self._model_path.suffix.lower() or "unknown"

    def load_model(self, force: bool = False) -> None:
        """Load the configured YOLO model into memory once."""
        with self._model_lock:
            if self._model is not None and not force:
                return

            self._model_path = self.settings.model_path
            suffix = self._model_path.suffix.lower()
            if suffix not in self.settings.allowed_model_suffixes:
                raise ValueError(
                    f"Unsupported model format '{suffix}'. "
                    f"Supported formats: {self.settings.allowed_model_suffixes}"
                )

            self._device = self._select_device(self._model_path)
            logger.info(
                "Loading YOLO model from %s using device %s",
                self._model_path,
                self._device,
            )
            self._model = YOLO(str(self._model_path))

    def predict(self, image_source: str | Path | np.ndarray) -> list[Any]:
        """Run YOLO inference on an image source."""
        if self._model is None:
            self.load_model()
        if self._model is None:
            raise RuntimeError("Model could not be loaded.")

        return self._model.predict(
            image_source,
            conf=self.settings.confidence_threshold,
            imgsz=self.settings.image_size,
            verbose=False,
            device=self._device,
        )

    def track_frame(self, frame: np.ndarray, tracker: str = "bytetrack.yaml") -> list[Any]:
        """Run ByteTrack on a single BGR frame with persistent state.

        Uses Ultralytics' built-in ByteTrack. The ``persist=True`` flag keeps
        the tracker state alive between successive calls on the same generator,
        so track IDs remain stable across frames of one video stream.

        Pass a custom ``tracker`` YAML path to override the default ByteTrack
        configuration (e.g. to increase track_buffer for sparse inference).

        Note: because ``Predictor`` is a singleton the tracker state is shared
        if two streams run concurrently — acceptable for single-user demo use.
        """
        if self._model is None:
            self.load_model()
        if self._model is None:
            raise RuntimeError("Model could not be loaded.")
        return self._model.track(
            frame,
            tracker=tracker,
            persist=True,
            conf=self.settings.confidence_threshold,
            imgsz=self.settings.image_size,
            verbose=False,
            device=self._device,
        )


    def detect_image(self, image: np.ndarray) -> list[DetectionBoxOut]:
        """Run inference on an RGB image and return normalized boxes."""
        results = self.predict(image)
        if not results:
            return []
        height, width = image.shape[:2]
        return self._to_detection_boxes(results[0], width=width, height=height)

    def build_update_labels(
        self,
        image_source: str | Path | np.ndarray,
    ) -> tuple[list[AutoLabelBox], dict[str, int]]:
        """Run inference and return labels formatted for the update-pool flow."""
        results = self.predict(image_source)
        if not results:
            return [], {"helmet": 0, "head": 0, "non-helmet": 0}

        result = results[0]
        if result.boxes is None:
            return [], {"helmet": 0, "head": 0, "non-helmet": 0}

        xywhn = result.boxes.xywhn.cpu().numpy()
        class_ids = result.boxes.cls.cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()

        boxes: list[AutoLabelBox] = []
        class_counts = {"helmet": 0, "head": 0, "non-helmet": 0}

        for index in range(len(xywhn)):
            xc, yc, width, height = map(float, xywhn[index])
            raw_class_id = int(class_ids[index])
            confidence = float(confidences[index])
            raw_name = str(result.names.get(raw_class_id, str(raw_class_id)))

            if is_head_class(raw_name):
                class_name = "head"
                class_id = 1
            elif is_nonhelmet_class(raw_name):
                class_name = "non-helmet"
                class_id = 2
            else:
                class_name = "helmet"
                class_id = 0

            class_counts[class_name] += 1

            x1 = max(0.0, min(1.0, xc - width / 2))
            y1 = max(0.0, min(1.0, yc - height / 2))
            x2 = max(0.0, min(1.0, xc + width / 2))
            y2 = max(0.0, min(1.0, yc + height / 2))

            boxes.append(
                AutoLabelBox(
                    id=f"update_box_{index}",
                    class_name=class_name,
                    class_id=class_id,
                    confidence=confidence,
                    xc=xc,
                    yc=yc,
                    width=width,
                    height=height,
                    x=x1,
                    y=y1,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                )
            )

        return boxes, class_counts

    def _select_device(self, model_path: Path) -> str | int:
        """Choose the best available device for the configured model.

        For ONNX models, prefers CUDAExecutionProvider when onnxruntime-gpu is
        installed (returns device index 0).  Falls back to CPU transparently.
        Override via ONNX_EXECUTION_PROVIDER env var (e.g. 'CPUExecutionProvider').
        """
        if model_path.suffix.lower() == ".onnx":
            override = self.settings.onnx_execution_provider
            if override:
                return "cpu" if "CPU" in override.upper() else 0
            try:
                import onnxruntime as ort
                if "CUDAExecutionProvider" in ort.get_available_providers():
                    logger.info("ONNX Runtime: CUDAExecutionProvider available — using GPU.")
                    return 0
            except Exception:
                logger.debug("ONNX Runtime provider check failed; using CPU.", exc_info=True)
            return "cpu"

        try:
            import torch

            if torch.cuda.is_available():
                return 0
        except Exception:
            logger.debug("CUDA detection failed; falling back to CPU.", exc_info=True)

        return "cpu"

    def _to_detection_boxes(self, result: Any, width: int, height: int) -> list[DetectionBoxOut]:
        """Convert a YOLO result object into API-ready detection boxes."""
        if result.boxes is None:
            return []

        detections: list[DetectionBoxOut] = []
        for index, box in enumerate(result.boxes):
            class_id = int(box.cls[0].item())
            class_name = str(result.names.get(class_id, str(class_id)))
            confidence = float(box.conf[0].item())
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            x1_i, y1_i, x2_i, y2_i = clamp_bbox(x1, y1, x2, y2, width=width, height=height)
            box_width = x2_i - x1_i
            box_height = y2_i - y1_i
            if box_width <= 1 or box_height <= 1:
                continue

            detections.append(
                DetectionBoxOut(
                    id=f"box_{index}",
                    class_name=class_name,
                    confidence=confidence,
                    x=x1_i / width,
                    y=y1_i / height,
                    width=box_width / width,
                    height=box_height / height,
                    x1=x1_i,
                    y1=y1_i,
                    x2=x2_i,
                    y2=y2_i,
                )
            )

        return detections


def get_predictor() -> Predictor:
    """Return the singleton predictor instance."""
    return Predictor(get_settings())
