"""Video upload, offline analysis, and MJPEG stream helpers."""

from __future__ import annotations

import base64
from collections import deque, OrderedDict
from dataclasses import dataclass, field
import logging
from pathlib import Path
import time
from datetime import datetime
import uuid

import cv2
import numpy as np
from PIL import Image

from src.api.schemas import HistoryEvent, LiveStartResponse, UploadVideoResponse, VideoDetectResponse
from src.config.settings import get_settings
from src.core.history import persist_window_event
from src.core.person_first import PersonFirstPipeline, make_person_first_pipeline
from src.core.predictor import Predictor
from src.utils.detection import is_head_class, is_nonhelmet_class
from src.utils.image import clamp_bbox, draw_detection, encode_jpeg

logger = logging.getLogger(__name__)
settings = get_settings()
LIVE_STREAMS: dict[str, dict[str, str]] = {}

# Absolute path to the custom ByteTrack config for sparse video inference
_VIDEO_TRACKER_CFG = str(Path(__file__).parent / "bytetrack_video.yaml")

# Minimum IoU to associate a no-ID detection with an existing tracked object
_IOU_MATCH_THRESH = 0.30

# Memory caps for VIDEO_ALERTS
_MAX_VIDEO_IDS = 50       # max number of video sessions tracked simultaneously
_MAX_ALERTS_PER_VIDEO = 200  # max alerts stored per video session
_MAX_WEBCAM_SESSIONS = 20     # max concurrent webcam sessions in memory
_WEBCAM_SESSION_TTL = 60.0    # seconds before idle webcam session is evicted


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    """Intersection-over-Union for two (x1, y1, x2, y2) boxes."""
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)

# Keyed by video_id → list of violation alert dicts accumulated during streaming.
# Bounded OrderedDict: evicts the oldest entry when _MAX_VIDEO_IDS is reached.
VIDEO_ALERTS: OrderedDict[str, list[dict]] = OrderedDict()


def _reset_video_alerts(video_id: str) -> None:
    """Reset the alerts list for a video, evicting the oldest session if at capacity."""
    if len(VIDEO_ALERTS) >= _MAX_VIDEO_IDS and video_id not in VIDEO_ALERTS:
        VIDEO_ALERTS.popitem(last=False)
    VIDEO_ALERTS[video_id] = []
    VIDEO_ALERTS.move_to_end(video_id)


def _append_video_alert(video_id: str, alert: dict) -> None:
    """Append an alert for a video, respecting the per-video cap."""
    alerts = VIDEO_ALERTS.setdefault(video_id, [])
    if len(alerts) < _MAX_ALERTS_PER_VIDEO:
        alerts.append(alert)

# Run YOLO inference on 1 out of every N raw frames
INFERENCE_FRAME_INTERVAL = 30

# Rolling-window confirmation: trigger when MIN_HITS detections appear in WINDOW_SIZE cycles
_WINDOW_SIZE = 5
_MIN_HITS = 3
# Grace period: keep a track's history for this many absence cycles before purging it
_TRACK_PATIENCE = 3


@dataclass
class _ViolationTracker:
    """
    Confirms violations using a rolling N-of-M window with a grace period
    and a spatial-IoU fallback for frames where ByteTrack returns no IDs.

    Each tracked object keeps a deque of the last _WINDOW_SIZE cycle results
    (1 = violation detected, 0 = missed).  A track is confirmed when the sum
    of its window reaches _MIN_HITS.  Tracks that disappear are retained for
    _TRACK_PATIENCE cycles (recording 0s) before being purged.

    When ByteTrack cannot assign an ID (boxes.id is None or the tracker is in
    its tentative warm-up state), resolve_id() matches the detection to an
    existing track via IoU, or mints a new negative pseudo-ID, so the rolling
    window keeps accumulating even without stable ByteTrack IDs.
    """
    # internal_id -> rolling hit history (1/0 per cycle)
    history: dict[int, deque] = field(default_factory=dict)
    # internal_id -> consecutive absence count
    absence: dict[int, int] = field(default_factory=dict)
    # internal_ids that have already triggered an alert this session
    confirmed: set[int] = field(default_factory=set)
    # internal_id -> last known (x1, y1, x2, y2) for spatial IoU matching
    last_box: dict[int, tuple[int, int, int, int]] = field(default_factory=dict)
    # counter for pseudo-IDs assigned when ByteTrack gives no ID (negative to
    # avoid collisions with real ByteTrack IDs which are always positive)
    _next_pseudo_id: int = field(default=-1)

    def resolve_id(
        self,
        bytetrack_id: int | None,
        bbox: tuple[int, int, int, int],
    ) -> int:
        """
        Return a stable internal ID for a detection.

        Priority:
          1. Use ``bytetrack_id`` directly when ByteTrack assigned one.
          2. Spatially match against ``last_box`` via IoU (fallback for
             frames where ByteTrack returns boxes.id = None).
          3. Mint a new negative pseudo-ID for genuinely new objects.
        """
        if bytetrack_id is not None:
            self.last_box[bytetrack_id] = bbox
            return bytetrack_id

        best_id: int | None = None
        best_iou = _IOU_MATCH_THRESH
        for tid, tbox in self.last_box.items():
            score = _iou(bbox, tbox)
            if score > best_iou:
                best_id, best_iou = tid, score

        if best_id is not None:
            self.last_box[best_id] = bbox
            return best_id

        pid = self._next_pseudo_id
        self._next_pseudo_id -= 1
        self.last_box[pid] = bbox
        return pid

    def record_hit(self, track_id: int) -> bool:
        """
        Record that a violation object WAS detected this cycle.
        Returns True the first time the rolling window reaches _MIN_HITS.
        """
        if track_id not in self.history:
            self.history[track_id] = deque(maxlen=_WINDOW_SIZE)
        self.absence[track_id] = 0
        self.history[track_id].append(1)
        if (
            sum(self.history[track_id]) >= _MIN_HITS
            and track_id not in self.confirmed
        ):
            self.confirmed.add(track_id)
            return True
        return False

    def tick_absences(self, hit_ids: set[int]) -> None:
        """
        Called once per cycle. Records misses for tracked objects not seen
        this cycle and purges those that exceed _TRACK_PATIENCE absences.
        """
        for tid in list(self.history):
            if tid in hit_ids:
                continue
            self.absence[tid] = self.absence.get(tid, 0) + 1
            if self.absence[tid] > _TRACK_PATIENCE:
                del self.history[tid]
                del self.absence[tid]
                self.last_box.pop(tid, None)
            else:
                self.history[tid].append(0)


@dataclass
class _WebcamSession:
    """In-memory state for a single browser webcam session."""

    tracker: _ViolationTracker = field(default_factory=_ViolationTracker)
    alerts: list[dict] = field(default_factory=list)
    last_active: float = field(default_factory=time.time)
    # Set to a PersonFirstPipeline instance when PERSON_FIRST_ENABLED=true
    person_pipeline: PersonFirstPipeline | None = field(default=None)


# Keyed by live_id → list of violation alert dicts for IP camera streams.
LIVE_ALERTS: OrderedDict[str, list[dict]] = OrderedDict()

# Keyed by session_id → _WebcamSession for browser webcam streams.
WEBCAM_SESSIONS: OrderedDict[str, _WebcamSession] = OrderedDict()


def _reset_live_alerts(live_id: str) -> None:
    """Reset the alerts list for a live stream, evicting oldest if at capacity."""
    if len(LIVE_ALERTS) >= _MAX_VIDEO_IDS and live_id not in LIVE_ALERTS:
        LIVE_ALERTS.popitem(last=False)
    LIVE_ALERTS[live_id] = []
    LIVE_ALERTS.move_to_end(live_id)


def _append_live_alert(live_id: str, alert: dict) -> None:
    """Append an alert for a live stream, respecting the per-stream cap."""
    alerts = LIVE_ALERTS.setdefault(live_id, [])
    if len(alerts) < _MAX_ALERTS_PER_VIDEO:
        alerts.append(alert)


def _crop_b64(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> str:
    """Return a base64-encoded JPEG data URL for a cropped region."""
    crop = frame[y1:y2, x1:x2]
    ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def _extract_frame_boxes_standard(
    frame: np.ndarray,
    predictor: Predictor,
    tracker_cfg: str,
    frame_label: int = 0,
) -> list[tuple[str, float, int, int, int, int, int | None]]:
    """Run standard single-stage ByteTrack inference and return normalised boxes.

    Returns a list of ``(class_name, conf, x1, y1, x2, y2, track_id)`` tuples
    using the same format produced by ``PersonFirstPipeline.process_frame_as_boxes``
    so both code paths share one unified processing loop downstream.
    """
    try:
        results = predictor.track_frame(frame, tracker=tracker_cfg)
    except Exception:
        logger.exception("ByteTrack failed for frame %d", frame_label)
        return []

    if not results:
        return []

    result = results[0]
    boxes = result.boxes
    if boxes is None:
        return []

    has_ids = boxes.id is not None
    height, width = frame.shape[:2]
    frame_boxes: list[tuple[str, float, int, int, int, int, int | None]] = []

    for i in range(len(boxes)):
        box = boxes[i]
        class_id = int(box.cls[0].item())
        class_name = str(result.names.get(class_id, str(class_id)))
        confidence = float(box.conf[0].item())
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        x1_i, y1_i, x2_i, y2_i = clamp_bbox(x1, y1, x2, y2, width=width, height=height)
        if x2_i - x1_i <= 1 or y2_i - y1_i <= 1:
            continue

        raw_bt_id: int | None = None
        if has_ids:
            val = boxes.id[i].item()
            if val == val:  # NaN check: NaN != NaN
                raw_bt_id = int(val)

        frame_boxes.append((class_name, confidence, x1_i, y1_i, x2_i, y2_i, raw_bt_id))

    return frame_boxes


@dataclass(slots=True)
class FrameDetection:
    """Raw detection extracted from a video frame."""

    class_name: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int


def process_webcam_frame(
    frame_bytes: bytes,
    session_id: str,
    predictor: Predictor,
) -> dict:
    """Process a single JPEG webcam frame and return detections + any new alerts.

    Uses ``predictor.predict()`` (not ``track_frame``) to avoid sharing
    ByteTrack internal state across concurrent sessions.
    """
    now = time.time()

    # Lazy cleanup: remove sessions that have been idle longer than the TTL
    expired = [
        sid for sid, sess in list(WEBCAM_SESSIONS.items())
        if now - sess.last_active > _WEBCAM_SESSION_TTL
    ]
    for sid in expired:
        del WEBCAM_SESSIONS[sid]

    # Get or create session with capacity cap
    if session_id not in WEBCAM_SESSIONS:
        if len(WEBCAM_SESSIONS) >= _MAX_WEBCAM_SESSIONS:
            WEBCAM_SESSIONS.popitem(last=False)
        sess = _WebcamSession()
        if settings.person_first_enabled:
            sess.person_pipeline = make_person_first_pipeline()
        WEBCAM_SESSIONS[session_id] = sess

    session = WEBCAM_SESSIONS[session_id]
    session.last_active = now
    WEBCAM_SESSIONS.move_to_end(session_id)

    # Decode JPEG bytes to BGR numpy frame
    img_array = np.frombuffer(frame_bytes, np.uint8)
    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if frame is None:
        logger.warning("process_webcam_frame: could not decode JPEG for session %s", session_id)
        return {"detections": [], "alerts": []}

    height, width = frame.shape[:2]

    # --- inference: person-first or standard single-stage ---
    detections_out: list[dict] = []
    new_alerts: list[dict] = []
    violation_hit_ids: set[int] = set()

    if settings.person_first_enabled and session.person_pipeline is not None:
        frame_boxes = session.person_pipeline.process_frame_as_boxes(
            frame, use_tracking=False
        )
    else:
        # Standard single-stage inference (no ByteTrack to keep sessions isolated)
        try:
            results = predictor.predict(frame)
        except Exception:
            logger.exception("process_webcam_frame: prediction failed for session %s.", session_id)
            return {"detections": [], "alerts": []}
        frame_boxes = []
        if results:
            result = results[0]
            if result.boxes is not None:
                for box in result.boxes:
                    class_id = int(box.cls[0].item())
                    class_name = str(result.names.get(class_id, str(class_id)))
                    confidence = float(box.conf[0].item())
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    x1_i, y1_i, x2_i, y2_i = clamp_bbox(x1, y1, x2, y2, width=width, height=height)
                    if x2_i - x1_i <= 1 or y2_i - y1_i <= 1:
                        continue
                    frame_boxes.append((class_name, float(box.conf[0].item()), x1_i, y1_i, x2_i, y2_i, None))

    for class_name, confidence, x1_i, y1_i, x2_i, y2_i, _track_id in frame_boxes:
        detections_out.append({
            "class_name": class_name,
            "confidence": round(confidence, 4),
            "x1": x1_i,
            "y1": y1_i,
            "x2": x2_i,
            "y2": y2_i,
        })

        if is_head_class(class_name) or is_nonhelmet_class(class_name):
            # IoU-only pseudo-ID matching (no ByteTrack IDs for webcam)
            resolved_id = session.tracker.resolve_id(None, (x1_i, y1_i, x2_i, y2_i))
            violation_hit_ids.add(resolved_id)
            if session.tracker.record_hit(resolved_id):
                logger.info(
                    "Webcam alert: session=%s class=%s", session_id, class_name
                )
                crop_data = _crop_b64(frame, x1_i, y1_i, x2_i, y2_i)
                if crop_data:
                    alert = {
                        "id": uuid.uuid4().hex,
                        "wall_time": datetime.now().strftime("%H:%M:%S"),
                        "class_name": class_name,
                        "confidence": round(confidence, 4),
                        "crop": crop_data,
                    }
                    if len(session.alerts) < _MAX_ALERTS_PER_VIDEO:
                        session.alerts.append(alert)
                    new_alerts.append(alert)

    session.tracker.tick_absences(violation_hit_ids)

    return {"detections": detections_out, "alerts": new_alerts}


def register_uploaded_video(filename: str, raw_bytes: bytes) -> UploadVideoResponse:
    """Persist an uploaded video and return its lookup identifiers."""
    video_id = uuid.uuid4().hex
    safe_name = Path(filename or "uploaded_video.mp4").name
    save_path = settings.videos_dir / f"{video_id}__{safe_name}"
    save_path.write_bytes(raw_bytes)
    return UploadVideoResponse(video_id=video_id, file_name=safe_name)


def register_live_stream(stream_url: str, source: str | None) -> LiveStartResponse:
    """Register a live stream URL after verifying it can be opened."""
    live_id = uuid.uuid4().hex
    inferred_source = source or f"Camera {live_id[:6]}"

    cap = cv2.VideoCapture(stream_url)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise ValueError("Khong doc duoc stream tu URL da cung cap.")

    LIVE_STREAMS[live_id] = {"url": stream_url, "source": inferred_source}
    return LiveStartResponse(live_id=live_id, source=inferred_source)


def analyze_uploaded_video(
    temp_path: Path,
    predictor: Predictor,
    source: str,
) -> VideoDetectResponse:
    """Process a full video offline and save threshold-triggered events."""
    cap = cv2.VideoCapture(str(temp_path))
    if not cap.isOpened():
        raise ValueError("Khong mo duoc video.")

    fps_input = cap.get(cv2.CAP_PROP_FPS)
    if not fps_input or fps_input <= 0:
        fps_input = 25.0

    target_fps = settings.target_stream_fps
    frame_interval = max(int(round(fps_input / target_fps)), 1)

    window_head = deque(maxlen=settings.stream_window_size)
    window_nonhelmet = deque(maxlen=settings.stream_window_size)
    current_frame_idx = 0
    processed_idx = 0
    prev_head_count = 0
    prev_nonhelmet_count = 0
    violation_events = 0
    suspicion_events = 0
    events_out: list[HistoryEvent] = []

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            current_frame_idx += 1
            if current_frame_idx % frame_interval != 0:
                continue

            processed_idx += 1
            frame_detections = extract_frame_detections(frame, predictor)
            frame_has_head, frame_has_nonhelmet, crop_candidates = classify_frame(frame_detections)

            window_head.append(1 if frame_has_head else 0)
            window_nonhelmet.append(1 if frame_has_nonhelmet else 0)
            head_count = sum(window_head)
            nonhelmet_count = sum(window_nonhelmet)

            _pil_frame: Image.Image | None = None
            if prev_nonhelmet_count < settings.stream_event_threshold <= nonhelmet_count:
                _pil_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                event = persist_window_event(
                    image=_pil_frame,
                    source=source,
                    event_type="NGHI_NGO",
                    crop_candidates=crop_candidates,
                )
                if event is not None:
                    events_out.append(event)
                    suspicion_events += 1

            if prev_head_count < settings.stream_event_threshold <= head_count:
                if _pil_frame is None:
                    _pil_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                event = persist_window_event(
                    image=_pil_frame,
                    source=source,
                    event_type="VI_PHAM",
                    crop_candidates=crop_candidates,
                )
                if event is not None:
                    events_out.append(event)
                    violation_events += 1

            prev_head_count = head_count
            prev_nonhelmet_count = nonhelmet_count
    finally:
        cap.release()

    return VideoDetectResponse(
        total_frames=processed_idx,
        fps_input=float(fps_input),
        fps_used=float(target_fps),
        window_size=settings.stream_window_size,
        violation_events=violation_events,
        suspicion_events=suspicion_events,
        events=events_out,
    )


def generate_processed_video_stream(
    video_path: Path,
    predictor: Predictor,
    source: str,
    video_id: str,
    start_sec: float = 0.0,
):
    """Yield an MJPEG stream for a processed video file using ByteTrack."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.error("Could not open uploaded video stream: %s", video_path)
        return

    fps_input = cap.get(cv2.CAP_PROP_FPS)
    if not fps_input or fps_input <= 0:
        fps_input = 25.0

    # Seek to requested start position
    if start_sec > 0:
        cap.set(cv2.CAP_PROP_POS_MSEC, start_sec * 1000.0)

    current_frame_idx = int(start_sec * fps_input)

    target_fps = settings.target_stream_fps
    # Inference runs on every INFERENCE_FRAME_INTERVAL-th raw frame
    frame_interval = INFERENCE_FRAME_INTERVAL
    window_head: deque[int] = deque(maxlen=settings.stream_window_size)
    window_nonhelmet: deque[int] = deque(maxlen=settings.stream_window_size)
    processed_idx = 0
    prev_head_count = 0
    prev_nonhelmet_count = 0
    last_send_time = time.perf_counter()
    target_dt = 1.0 / target_fps

    # Reset alerts and confirmation state for this video_id on each (re)stream
    _reset_video_alerts(video_id)
    violation_tracker = _ViolationTracker()

    # Create a fresh person-first pipeline instance for this stream (if enabled)
    _person_pipeline: PersonFirstPipeline | None = None
    if settings.person_first_enabled:
        _person_pipeline = make_person_first_pipeline()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            current_frame_idx += 1
            if current_frame_idx % frame_interval != 0:
                continue

            processed_idx += 1
            timestamp_sec = current_frame_idx / fps_input
            frame_has_head = False
            frame_has_nonhelmet = False
            crop_candidates: list[tuple[str, int, int, int, int]] = []

            # --- inference: person-first or standard ByteTrack ---
            if _person_pipeline is not None:
                frame_boxes = _person_pipeline.process_frame_as_boxes(
                    frame, use_tracking=True
                )
                _person_pipeline.draw_person_boxes(frame)
            else:
                frame_boxes = _extract_frame_boxes_standard(
                    frame, predictor, _VIDEO_TRACKER_CFG, processed_idx
                )

            # resolved IDs of violation objects seen this cycle (used by tick_absences)
            violation_hit_ids: set[int] = set()

            for class_name, confidence, x1_i, y1_i, x2_i, y2_i, raw_bt_id in frame_boxes:
                if is_head_class(class_name):
                    frame_has_head = True
                if is_nonhelmet_class(class_name):
                    frame_has_nonhelmet = True
                if is_head_class(class_name) or is_nonhelmet_class(class_name):
                    crop_candidates.append((class_name, x1_i, y1_i, x2_i, y2_i))
                    resolved_id = violation_tracker.resolve_id(
                        raw_bt_id, (x1_i, y1_i, x2_i, y2_i)
                    )
                    violation_hit_ids.add(resolved_id)
                    window = violation_tracker.history.get(resolved_id)
                    logger.debug(
                        "[TRACK] frame=%d class=%s bt_id=%s resolved_id=%d window=%s sum=%d",
                        processed_idx, class_name, raw_bt_id, resolved_id,
                        list(window) if window else [],
                        sum(window) if window else 0,
                    )
                    if violation_tracker.record_hit(resolved_id):
                        logger.info(
                            "Alert triggered: resolved_id=%d class=%s t=%.2fs",
                            resolved_id, class_name, timestamp_sec,
                        )
                        crop_data = _crop_b64(frame, x1_i, y1_i, x2_i, y2_i)
                        if crop_data:
                            _append_video_alert(video_id, {
                                "id": uuid.uuid4().hex,
                                "timestamp_sec": round(timestamp_sec, 2),
                                "class_name": class_name,
                                "confidence": round(confidence, 4),
                                "crop": crop_data,
                                "x1": x1_i,
                                "y1": y1_i,
                                "x2": x2_i,
                                "y2": y2_i,
                            })
                            logger.debug(
                                "Alert stored: video_id=%s total=%d",
                                video_id, len(VIDEO_ALERTS.get(video_id, [])),
                            )
                draw_detection(
                    frame,
                    class_name=class_name,
                    confidence=confidence,
                    x1=x1_i,
                    y1=y1_i,
                    x2=x2_i,
                    y2=y2_i,
                    track_id=raw_bt_id,
                )

            # Record misses and apply grace-period logic for absent tracks
            violation_tracker.tick_absences(violation_hit_ids)

            window_head.append(1 if frame_has_head else 0)
            window_nonhelmet.append(1 if frame_has_nonhelmet else 0)
            head_count = sum(window_head)
            nonhelmet_count = sum(window_nonhelmet)

            # Convert to PIL only when a threshold crossing actually triggers
            # persist_window_event — avoids BGR→RGB copy on every processed frame.
            _pil_frame: Image.Image | None = None
            if prev_nonhelmet_count < settings.stream_event_threshold <= nonhelmet_count:
                _pil_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                persist_window_event(
                    image=_pil_frame,
                    source=source,
                    event_type="NGHI_NGO",
                    crop_candidates=crop_candidates,
                )

            if prev_head_count < settings.stream_event_threshold <= head_count:
                if _pil_frame is None:
                    _pil_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                persist_window_event(
                    image=_pil_frame,
                    source=source,
                    event_type="VI_PHAM",
                    crop_candidates=crop_candidates,
                )

            prev_head_count = head_count
            prev_nonhelmet_count = nonhelmet_count

            elapsed = time.perf_counter() - last_send_time
            if elapsed < target_dt:
                time.sleep(target_dt - elapsed)
            last_send_time = time.perf_counter()

            frame_bytes = encode_jpeg(frame)
            if frame_bytes is None:
                continue
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
    finally:
        cap.release()


def generate_live_stream(live_id: str, predictor: Predictor):
    """Yield an MJPEG stream for a registered live source using ByteTrack."""
    live_cfg = LIVE_STREAMS.get(live_id)
    if live_cfg is None:
        raise KeyError(f"Live stream '{live_id}' was not found.")

    cap = cv2.VideoCapture(live_cfg["url"])
    if not cap.isOpened():
        raise ValueError(f"Khong mo duoc live stream: {live_cfg['url']}")

    _reset_live_alerts(live_id)
    violation_tracker = _ViolationTracker()

    # Fresh person-first pipeline for this live stream (if enabled)
    _person_pipeline: PersonFirstPipeline | None = None
    if settings.person_first_enabled:
        _person_pipeline = make_person_first_pipeline()

    last_send_time = time.perf_counter()
    target_dt = 1.0 / settings.target_stream_fps
    frame_idx = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.warning("Live stream frame was lost for %s.", live_id)
                break

            elapsed = time.perf_counter() - last_send_time
            if elapsed < target_dt:
                continue
            last_send_time = time.perf_counter()
            frame_idx += 1

            # --- inference: person-first or standard ByteTrack ---
            if _person_pipeline is not None:
                frame_boxes = _person_pipeline.process_frame_as_boxes(
                    frame, use_tracking=True
                )
                _person_pipeline.draw_person_boxes(frame)
            else:
                frame_boxes = _extract_frame_boxes_standard(
                    frame, predictor, _VIDEO_TRACKER_CFG, frame_idx
                )

            violation_hit_ids: set[int] = set()

            for class_name, confidence, x1_i, y1_i, x2_i, y2_i, raw_bt_id in frame_boxes:
                if is_head_class(class_name) or is_nonhelmet_class(class_name):
                    resolved_id = violation_tracker.resolve_id(
                        raw_bt_id, (x1_i, y1_i, x2_i, y2_i)
                    )
                    violation_hit_ids.add(resolved_id)
                    if violation_tracker.record_hit(resolved_id):
                        logger.info(
                            "Live alert: live_id=%s class=%s", live_id, class_name
                        )
                        crop_data = _crop_b64(frame, x1_i, y1_i, x2_i, y2_i)
                        if crop_data:
                            _append_live_alert(live_id, {
                                "id": uuid.uuid4().hex,
                                "wall_time": datetime.now().strftime("%H:%M:%S"),
                                "class_name": class_name,
                                "confidence": round(confidence, 4),
                                "crop": crop_data,
                            })

                draw_detection(
                    frame,
                    class_name=class_name,
                    confidence=confidence,
                    x1=x1_i,
                    y1=y1_i,
                    x2=x2_i,
                    y2=y2_i,
                    track_id=raw_bt_id,
                )

            violation_tracker.tick_absences(violation_hit_ids)

            frame_bytes = encode_jpeg(frame)
            if frame_bytes is None:
                continue
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
    finally:
        cap.release()


def extract_frame_detections(frame: np.ndarray, predictor: Predictor) -> list[FrameDetection]:
    """Run inference on a BGR frame and convert it to simplified detections."""
    try:
        results = predictor.predict(frame)
    except Exception:
        logger.exception("YOLO prediction failed for a video frame.")
        return []

    if not results:
        return []

    result = results[0]
    if result.boxes is None:
        return []

    height, width = frame.shape[:2]
    detections: list[FrameDetection] = []
    for box in result.boxes:
        class_id = int(box.cls[0].item())
        class_name = str(result.names.get(class_id, str(class_id)))
        confidence = float(box.conf[0].item())
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        x1_i, y1_i, x2_i, y2_i = clamp_bbox(x1, y1, x2, y2, width=width, height=height)
        if x2_i - x1_i <= 1 or y2_i - y1_i <= 1:
            continue
        detections.append(
            FrameDetection(
                class_name=class_name,
                confidence=confidence,
                x1=x1_i,
                y1=y1_i,
                x2=x2_i,
                y2=y2_i,
            )
        )
    return detections


def classify_frame(
    detections: list[FrameDetection],
) -> tuple[bool, bool, list[tuple[str, int, int, int, int]]]:
    """Classify a frame and build crop candidates from its detections."""
    frame_has_head = any(is_head_class(det.class_name) for det in detections)
    frame_has_nonhelmet = any(is_nonhelmet_class(det.class_name) for det in detections)
    crop_candidates = [
        (det.class_name, det.x1, det.y1, det.x2, det.y2)
        for det in detections
        if is_head_class(det.class_name) or is_nonhelmet_class(det.class_name)
    ]
    return frame_has_head, frame_has_nonhelmet, crop_candidates
