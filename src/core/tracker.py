"""Simple tracking utilities for streamed detections."""

from __future__ import annotations

from dataclasses import dataclass, field


def iou_xyxy(
    box1: tuple[float, float, float, float],
    box2: tuple[float, float, float, float],
) -> float:
    """Calculate the intersection-over-union of two XYXY boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0

    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
    union = area1 + area2 - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


@dataclass
class Track:
    """A lightweight tracked object state."""

    id: int
    x1: float
    y1: float
    x2: float
    y2: float
    last_frame: int
    cls_counts: dict[str, int] = field(default_factory=dict)
    conf_sum: dict[str, float] = field(default_factory=dict)

    def update_box(self, x1: float, y1: float, x2: float, y2: float) -> None:
        """Update the current bounding box for the track."""
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2

    def update_class(self, cls_name: str, confidence: float) -> None:
        """Accumulate class votes for the track."""
        self.cls_counts[cls_name] = self.cls_counts.get(cls_name, 0) + 1
        self.conf_sum[cls_name] = self.conf_sum.get(cls_name, 0.0) + confidence

    @property
    def main_class(self) -> str:
        """Return the dominant class for the track."""
        if not self.cls_counts:
            return "unknown"
        items = sorted(
            self.cls_counts.items(),
            key=lambda item: (item[1], self.conf_sum.get(item[0], 0.0)),
            reverse=True,
        )
        return items[0][0]

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        """Return the current box as integer coordinates."""
        return int(self.x1), int(self.y1), int(self.x2), int(self.y2)


class SimpleIOUTracker:
    """A minimal IoU-based tracker that keeps lightweight IDs stable."""

    def __init__(self, iou_thresh: float = 0.3, max_age: int = 30) -> None:
        self.iou_thresh = iou_thresh
        self.max_age = max_age
        self.tracks: list[Track] = []
        self.next_id = 1

    def update(
        self,
        detections: list[tuple[float, float, float, float, str, float]],
        frame_idx: int,
    ) -> list[Track]:
        """Update active tracks using greedy IoU matching."""
        unmatched_tracks = set(range(len(self.tracks)))
        matched_dets: set[int] = set()
        matches: list[tuple[int, int]] = []

        for det_idx, (dx1, dy1, dx2, dy2, _, _) in enumerate(detections):
            best_iou = 0.0
            best_track_idx = -1
            for track_idx in unmatched_tracks:
                track = self.tracks[track_idx]
                iou_value = iou_xyxy(
                    (dx1, dy1, dx2, dy2),
                    (track.x1, track.y1, track.x2, track.y2),
                )
                if iou_value > best_iou:
                    best_iou = iou_value
                    best_track_idx = track_idx

            if best_track_idx >= 0 and best_iou >= self.iou_thresh:
                matches.append((best_track_idx, det_idx))
                unmatched_tracks.discard(best_track_idx)
                matched_dets.add(det_idx)

        for track_idx, det_idx in matches:
            dx1, dy1, dx2, dy2, class_name, confidence = detections[det_idx]
            track = self.tracks[track_idx]
            track.update_box(dx1, dy1, dx2, dy2)
            track.update_class(class_name, confidence)
            track.last_frame = frame_idx

        for det_idx, (dx1, dy1, dx2, dy2, class_name, confidence) in enumerate(detections):
            if det_idx in matched_dets:
                continue
            track = Track(
                id=self.next_id,
                x1=dx1,
                y1=dy1,
                x2=dx2,
                y2=dy2,
                last_frame=frame_idx,
            )
            track.update_class(class_name, confidence)
            self.tracks.append(track)
            self.next_id += 1

        self.tracks = [
            track for track in self.tracks if frame_idx - track.last_frame <= self.max_age
        ]
        return self.tracks
