"""Person-first two-stage detection pipeline.

Pipeline overview
-----------------
1. Detect (or track) persons in the full frame using a lightweight model.
2. For each person, extract an upper-body crop (configurable ratio + margin).
3. Run the existing helmet model on the crop.
4. Map detections back to full-frame coordinates.
5. Cache the last known helmet status per track ID so the helmet model is
   not run on every single frame (controlled by ``helmet_recheck_interval``).

The pipeline produces ``PersonHelmetResult`` objects and a normalised box
tuple list that is drop-in compatible with the existing streaming loop.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from src.config.settings import Settings, get_settings
from src.core.person_detector import PersonDetector, get_person_detector
from src.core.predictor import Predictor, get_predictor
from src.utils.detection import is_head_class, is_nonhelmet_class
from src.utils.image import clamp_bbox

logger = logging.getLogger(__name__)

# Reuse the sparse video ByteTrack config that the existing streaming code uses
_VIDEO_TRACKER_CFG = str(Path(__file__).parent / "bytetrack_video.yaml")

# BGR colour used to draw person bounding boxes on video/live streams
_PERSON_BOX_COLOR = (255, 140, 0)  # blue-orange


@dataclass(slots=True)
class PersonHelmetResult:
    """Detection result for a single person from the person-first pipeline."""

    person_x1: int
    person_y1: int
    person_x2: int
    person_y2: int
    person_conf: float
    person_track_id: int | None
    helmet_class: str       # "helmet", "head", or "non-helmet"
    helmet_conf: float
    helmet_x1: int          # full-frame pixel coordinates
    helmet_y1: int
    helmet_x2: int
    helmet_y2: int


class PersonFirstPipeline:
    """Two-stage detector: find persons first, then check helmet status on crops.

    One instance is created per stream so that the frame counter and helmet
    status cache are isolated between concurrent sessions.  The underlying
    ``PersonDetector`` and ``Predictor`` are singletons and are shared.
    """

    def __init__(
        self,
        person_detector: PersonDetector,
        helmet_predictor: Predictor,
        settings: Settings,
    ) -> None:
        self._detector = person_detector
        self._predictor = helmet_predictor
        self._settings = settings
        # track_id → (helmet_class, helmet_conf, (x1,y1,x2,y2), frame_no)
        self._cache: dict[int, tuple[str, float, tuple[int, int, int, int], int]] = {}
        self._frame_no: int = 0
        self._last_results: list[PersonHelmetResult] = []
        # Cached persons from the previous detection run (used for interval skipping)
        self._last_persons: list[tuple[int, int, int, int, float, int | None]] = []

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Clear per-stream state. Call at the start of each new video/live stream."""
        self._cache.clear()
        self._frame_no = 0
        self._last_results = []
        self._last_persons = []

    @property
    def last_results(self) -> list[PersonHelmetResult]:
        """The ``PersonHelmetResult`` list from the most recent ``process_frame`` call."""
        return self._last_results

    # ── Main entry points ─────────────────────────────────────────────────────

    def process_frame(
        self,
        frame: np.ndarray,
        use_tracking: bool = True,
    ) -> list[PersonHelmetResult]:
        """Detect persons → crop upper bodies → check helmet status.

        Args:
            frame: BGR frame from OpenCV.
            use_tracking: When *True* (video/live), use ByteTrack person IDs for
                          stable caching.  When *False* (webcam), run ``predict``
                          without persistent state so sessions stay isolated.

        Returns:
            One ``PersonHelmetResult`` per detected person.  Persons whose crop
            yields no helmet-model detection are silently omitted.
        """
        self._frame_no += 1

        # Re-run person detection every person_detection_interval frames.
        # Default interval=1 means every frame (no accuracy change).
        # Increase to 2–4 on weak CPU deployments: person boxes are reused between
        # runs; helmet re-checks still happen per frame via the helmet_recheck_interval
        # cache.  Set PERSON_DETECTION_INTERVAL=1 to restore full per-frame detection.
        interval = self._settings.person_detection_interval
        if self._frame_no % interval == 0 or not self._last_persons:
            if use_tracking:
                persons = self._detector.track_persons(frame, tracker=_VIDEO_TRACKER_CFG)
                # persons: (x1, y1, x2, y2, conf, track_id | None)
            else:
                raw = self._detector.detect_persons(frame)
                persons = [(x1, y1, x2, y2, conf, None) for x1, y1, x2, y2, conf in raw]
            self._last_persons = persons
        else:
            persons = self._last_persons

        results: list[PersonHelmetResult] = []

        for px1, py1, px2, py2, pconf, track_id in persons:
            cache_key = (
                track_id
                if track_id is not None
                else self._spatial_cache_key(px1, py1, px2, py2)
            )

            # Serve cached helmet status if fresh enough
            cached = self._cache.get(cache_key)
            if cached is not None:
                hclass, hconf, (hx1, hy1, hx2, hy2), stored_frame = cached
                if self._frame_no - stored_frame < self._settings.helmet_recheck_interval:
                    results.append(PersonHelmetResult(
                        person_x1=px1, person_y1=py1, person_x2=px2, person_y2=py2,
                        person_conf=pconf, person_track_id=track_id,
                        helmet_class=hclass, helmet_conf=hconf,
                        helmet_x1=hx1, helmet_y1=hy1, helmet_x2=hx2, helmet_y2=hy2,
                    ))
                    continue

            # Extract upper-body crop and run helmet model
            crop, ox, oy = self._upper_body_crop(frame, px1, py1, px2, py2)
            if crop is None:
                continue

            det = self._detect_helmet_in_crop(crop, ox, oy)
            if det is None:
                continue  # no detection → skip person (no false positives)

            hclass, hconf, hx1, hy1, hx2, hy2 = det
            self._cache[cache_key] = (
                hclass, hconf, (hx1, hy1, hx2, hy2), self._frame_no
            )
            results.append(PersonHelmetResult(
                person_x1=px1, person_y1=py1, person_x2=px2, person_y2=py2,
                person_conf=pconf, person_track_id=track_id,
                helmet_class=hclass, helmet_conf=hconf,
                helmet_x1=hx1, helmet_y1=hy1, helmet_x2=hx2, helmet_y2=hy2,
            ))

        self._purge_stale_cache()
        self._last_results = results
        return results

    def process_frame_as_boxes(
        self,
        frame: np.ndarray,
        use_tracking: bool = True,
    ) -> list[tuple[str, float, int, int, int, int, int | None]]:
        """Run the pipeline and return normalised box tuples.

        The returned format ``(class_name, conf, x1, y1, x2, y2, track_id)``
        is drop-in compatible with the existing streaming loop so no
        further changes to violation-tracking logic are required.
        """
        results = self.process_frame(frame, use_tracking=use_tracking)
        return [
            (
                r.helmet_class, r.helmet_conf,
                r.helmet_x1, r.helmet_y1, r.helmet_x2, r.helmet_y2,
                r.person_track_id,
            )
            for r in results
        ]

    def draw_person_boxes(self, frame: np.ndarray) -> None:
        """Draw thin person bounding boxes on *frame* for visual context.

        Draws ALL detected persons (not only those with a helmet result) so
        every person in the scene is visually annotated.  Call this after
        ``process_frame`` / ``process_frame_as_boxes``.
        """
        for px1, py1, px2, py2, _pconf, track_id in self._last_persons:
            cv2.rectangle(
                frame,
                (px1, py1),
                (px2, py2),
                _PERSON_BOX_COLOR,
                1,
            )
            pid = f"P{track_id}" if track_id is not None else "P?"
            cv2.putText(
                frame,
                pid,
                (px1, max(0, py1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                _PERSON_BOX_COLOR,
                1,
                cv2.LINE_AA,
            )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _upper_body_crop(
        self, frame: np.ndarray, x1: int, y1: int, x2: int, y2: int
    ) -> tuple[np.ndarray | None, int, int]:
        """Return (BGR crop, offset_x, offset_y) for the upper-body region."""
        fh, fw = frame.shape[:2]
        person_h = y2 - y1
        crop_h = max(20, int(person_h * self._settings.upper_body_crop_ratio))

        margin_x = max(2, int((x2 - x1) * self._settings.person_crop_margin))
        margin_y = max(2, int(crop_h * self._settings.person_crop_margin))

        cx1 = max(0, x1 - margin_x)
        cy1 = max(0, y1 - margin_y)
        cx2 = min(fw, x2 + margin_x)
        cy2 = min(fh, y1 + crop_h + margin_y)

        if cx2 - cx1 < 10 or cy2 - cy1 < 10:
            return None, 0, 0

        return frame[cy1:cy2, cx1:cx2].copy(), cx1, cy1

    def _detect_helmet_in_crop(
        self,
        crop: np.ndarray,
        ox: int,
        oy: int,
    ) -> tuple[str, float, int, int, int, int] | None:
        """Run the helmet predictor on a BGR crop.

        Returns ``(class_name, conf, frame_x1, frame_y1, frame_x2, frame_y2)``
        or ``None`` when no detection passes the confidence threshold.

        Selection policy: violations (head / non-helmet) are preferred over
        helmet detections.  Ties are broken by confidence score.
        """
        try:
            results = self._predictor.predict(crop)
        except Exception:
            logger.exception("person_first: helmet prediction on crop failed.")
            return None

        if not results:
            return None

        result = results[0]
        if result.boxes is None or len(result.boxes) == 0:
            return None

        ch, cw = crop.shape[:2]
        best_class: str | None = None
        best_conf: float = 0.0
        best_coords: tuple[int, int, int, int] = (0, 0, 0, 0)

        for box in result.boxes:
            class_id = int(box.cls[0].item())
            raw_name = str(result.names.get(class_id, str(class_id)))
            if is_head_class(raw_name):
                class_name = "head"
            elif is_nonhelmet_class(raw_name):
                class_name = "non-helmet"
            else:
                class_name = "helmet"
            conf = float(box.conf[0].item())
            bx1, by1, bx2, by2 = box.xyxy[0].tolist()
            bx1_i, by1_i, bx2_i, by2_i = clamp_bbox(bx1, by1, bx2, by2, width=cw, height=ch)

            is_viol = is_head_class(class_name) or is_nonhelmet_class(class_name)
            is_best_viol = best_class is not None and (
                is_head_class(best_class) or is_nonhelmet_class(best_class)
            )

            # Prefer violations; among same severity prefer higher confidence
            if (
                best_class is None
                or (is_viol and not is_best_viol)
                or (is_viol == is_best_viol and conf > best_conf)
            ):
                best_class = class_name
                best_conf = conf
                best_coords = (ox + bx1_i, oy + by1_i, ox + bx2_i, oy + by2_i)

        if best_class is None:
            return None

        hx1, hy1, hx2, hy2 = best_coords
        return best_class, best_conf, hx1, hy1, hx2, hy2

    def _spatial_cache_key(self, x1: int, y1: int, x2: int, y2: int) -> int:
        """Rough grid-cell key for persons without a stable ByteTrack ID."""
        # 20-pixel cells keep nearby positions in the same bucket while
        # distinguishing clearly separate persons.
        return hash(((x1 + x2) // 2 // 20, (y1 + y2) // 2 // 20))

    def _purge_stale_cache(self) -> None:
        """Remove helmet-status cache entries that are too old to be useful."""
        threshold = self._settings.helmet_recheck_interval * 4
        stale = [
            k for k, (_, _, _, fn) in self._cache.items()
            if self._frame_no - fn > threshold
        ]
        for k in stale:
            del self._cache[k]


def make_person_first_pipeline() -> PersonFirstPipeline:
    """Create a fresh ``PersonFirstPipeline`` backed by the shared singleton models."""
    return PersonFirstPipeline(
        person_detector=get_person_detector(),
        helmet_predictor=get_predictor(),
        settings=get_settings(),
    )
