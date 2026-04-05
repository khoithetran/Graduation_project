# Deep Link: Detection Alerts ↔ Video Player

**Date:** 2026-04-05  
**Status:** Approved  
**Approach:** Dual-mode — MJPEG stream for live processing, HTML5 `<video>` modal for alert inspection

---

## Problem

When a violation alert fires, the user can see a crop image and a timestamp but cannot inspect the exact moment in context. The current "seek" restarts the MJPEG stream from a new URL, losing native browser playback controls (seek bar, pause, end-of-playback state).

---

## Goal

Clicking an alert card opens a fullscreen modal with:
- An HTML5 `<video>` seeked to the alert's exact timestamp and paused.
- A canvas overlay drawing a glowing bounding box for that alert.
- A custom progress bar (current time / duration, draggable seek).
- A play/pause button that reflects end-of-playback state.

The MJPEG stream continues running behind the modal untouched.

---

## Architecture

```
User clicks alert card
        │
        ▼
VideoTracking: setSelectedAlert(alert)
        │
        ▼
AlertDetailModal renders (fullscreen overlay)
        │
        ├─► <video src="/api/video/file/{video_id}">
        │         ├─ onLoadedMetadata → seek to alert.timestamp_sec, pause()
        │         ├─ onTimeUpdate     → sync progress bar state
        │         └─ onEnded          → setIsPlaying(false)
        │
        ├─► <canvas> overlay (absolute, same dimensions as video)
        │         └─ glowing bbox drawn from alert.{x1, y1, x2, y2}
        │              • visible while paused
        │              • cleared while playing
        │
        └─► Custom progress bar (styled range input)
                  └─ onChange → videoRef.current.currentTime = value
```

---

## Backend

### New endpoint

```
GET /api/video/file/{video_id}
```

- File: `src/api/routes/stream.py`
- Scans `settings.videos_dir` for a file matching `{video_id}__*`.
- Returns `FileResponse(path, media_type="video/mp4")`.
- Starlette's `FileResponse` handles `Accept-Ranges / Range` headers natively — required for browser seek-to-position.
- Returns HTTP 404 if the file is not found.

### No other backend changes

`streaming.py` already stores `timestamp_sec`, `x1`, `y1`, `x2`, `y2` in every alert. No changes to predictor, tracker, or alert logic.

---

## Frontend

### New component: `AlertDetailModal.tsx`

**Props:**
```ts
{ alert: VideoAlert, videoId: string, onClose: () => void }
```

**Refs:**
| Ref | Element | Purpose |
|-----|---------|---------|
| `videoRef` | `<video>` | `currentTime`, `pause()`, `play()` |
| `canvasRef` | `<canvas>` | Bbox overlay drawing |

**State:**
| Name | Type | Initial | Purpose |
|------|------|---------|---------|
| `isPlaying` | `boolean` | `false` | Drive play/pause button |
| `currentTime` | `number` | `0` | Progress bar position |
| `duration` | `number` | `0` | Progress bar max |

**Video event handlers:**
- `onLoadedMetadata` → set `duration`, seek to `alert.timestamp_sec`, call `pause()`
- `onTimeUpdate` → `setCurrentTime(videoRef.current.currentTime)`
- `onPlay` → `setIsPlaying(true)`, clear canvas
- `onPause` → `setIsPlaying(false)`, draw bbox
- `onEnded` → `setIsPlaying(false)`

**Canvas bbox draw** (called on pause/mount, cleared on play):
- Outer glow: `ctx.shadowBlur = 12`, `ctx.shadowColor = "rgba(251,191,36,0.8)"`, `lineWidth = 3`
- Color: amber `#FCD34D`
- Coordinates scaled from video's natural size to rendered display size

**Custom progress bar:**
- `<input type="range">` styled to match the app's dark theme
- `min=0`, `max=duration`, `step=0.1`, `value=currentTime`
- `onChange` → `videoRef.current.currentTime = value`
- Displays `MM:SS.s / MM:SS.s` text alongside

**Video element attributes:**
- `loop={false}`
- `playsInline`
- `src={/api/video/file/${videoId}}`

### Changes to `VideoTracking.tsx`

- Add state: `selectedAlert: VideoAlert | null` (default `null`)
- `handleAlertClick(alert)` → `setSelectedAlert(alert)` only (remove stream URL restart)
- Render `<AlertDetailModal>` when `selectedAlert !== null`
- Pass `onClose={() => setSelectedAlert(null)}`
- MJPEG `<img>` stream is unaffected

---

## Styling

**Normal detections** (OpenCV, server-side): thin colored box, 2 px.

**Selected alert bbox** (canvas, client-side):
- 3 px amber stroke (`#FCD34D`)
- `shadowBlur = 12`, `shadowColor = rgba(251,191,36,0.8)` for glow
- Drawn twice: glow pass first, solid pass second

**Modal backdrop:** `fixed inset-0 bg-black/80 backdrop-blur-sm z-50`

---

## Out of Scope

- Live bounding box overlay while the video is playing (Approach B).
- Showing all detections across the full timeline (Approach B).
- Persisting the video file across container restarts.
