import { useEffect, useRef, useState, useMemo } from 'react';

import appText from '../content/app-text.vi.json';
import { API_BASE } from '../services/api';
import type { LiveAlert } from '../types';
import { getColor } from './BBoxCanvas';
import { ReportModal } from './ReportModal';

type Mode =
  | 'idle'
  | 'webcam-preview'   // getUserMedia done, video visible, inference NOT yet started
  | 'webcam-active'    // inference loop running
  | 'ipcam-ready'      // URL validated, stream NOT yet started
  | 'ipcam-active';    // MJPEG stream running

type FrameDetection = {
  class_name: string;
  confidence: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

type PersonBox = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  track_id?: number | null;
};

const HELMET_CLASSES = ['helmet', 'head', 'non-helmet'] as const;
const CLASS_LABELS: Record<string, string> = {
  helmet: appText.bboxControls.classHelmet,
  head: appText.bboxControls.classHead,
  'non-helmet': appText.bboxControls.classNonHelmet,
  person: appText.bboxControls.classPerson,
};
const PERSON_BOX_COLOR = '#ff8c00';

function drawBboxes(
  canvas: HTMLCanvasElement,
  video: HTMLVideoElement,
  detections: FrameDetection[],
  personBoxes: PersonBox[],
  sendW: number,
  sendH: number,
  activeClasses: Set<string>,
): void {
  const ctx = canvas.getContext('2d');
  if (!ctx || !video.videoWidth || !video.videoHeight) return;

  const dpr = window.devicePixelRatio || 1;
  canvas.width = video.clientWidth * dpr;
  canvas.height = video.clientHeight * dpr;
  canvas.style.width = `${video.clientWidth}px`;
  canvas.style.height = `${video.clientHeight}px`;

  // Bboxes are in sendW×sendH space — scale back to native video size first
  const toNativeX = video.videoWidth / sendW;
  const toNativeY = video.videoHeight / sendH;

  const scaleX = video.clientWidth / video.videoWidth;
  const scaleY = video.clientHeight / video.videoHeight;
  const s = Math.min(scaleX, scaleY) * dpr;
  const offsetX = (video.clientWidth - video.videoWidth * Math.min(scaleX, scaleY)) * dpr / 2;
  const offsetY = (video.clientHeight - video.videoHeight * Math.min(scaleX, scaleY)) * dpr / 2;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Draw person boxes (thin, distinct color)
  if (activeClasses.has('person')) {
    for (const pb of personBoxes) {
      const sx = pb.x1 * toNativeX * s + offsetX;
      const sy = pb.y1 * toNativeY * s + offsetY;
      const sw = (pb.x2 - pb.x1) * toNativeX * s;
      const sh = (pb.y2 - pb.y1) * toNativeY * s;

      ctx.strokeStyle = PERSON_BOX_COLOR;
      ctx.lineWidth = dpr;
      ctx.setLineDash([4 * dpr, 2 * dpr]);
      ctx.strokeRect(sx, sy, sw, sh);
      ctx.setLineDash([]);

      // Track ID label
      const pid = pb.track_id != null ? `P${pb.track_id}` : 'P?';
      const fontSize = Math.max(10 * dpr, canvas.width / 80);
      ctx.font = `${fontSize}px monospace`;
      const labelY = sy > fontSize + 2 ? sy - 2 : sy + sh + fontSize + 2;
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      ctx.fillRect(sx, labelY - fontSize, ctx.measureText(pid).width + 6, fontSize + 3);
      ctx.fillStyle = PERSON_BOX_COLOR;
      ctx.fillText(pid, sx + 3, labelY);
    }
  }

  // Draw helmet detections
  for (const det of detections) {
    if (!activeClasses.has(det.class_name)) continue;

    const sx = det.x1 * toNativeX * s + offsetX;
    const sy = det.y1 * toNativeY * s + offsetY;
    const sw = (det.x2 - det.x1) * toNativeX * s;
    const sh = (det.y2 - det.y1) * toNativeY * s;
    const color = getColor(det.class_name);

    ctx.strokeStyle = color;
    ctx.lineWidth = 2 * dpr;
    ctx.strokeRect(sx, sy, sw, sh);

    const label = `${det.class_name} ${(det.confidence * 100).toFixed(1)}%`;
    const fontSize = Math.max(12 * dpr, canvas.width / 60);
    ctx.font = `bold ${fontSize}px monospace`;
    const textW = ctx.measureText(label).width;
    const labelY = sy > fontSize + 4 ? sy - 4 : sy + sh + fontSize + 2;
    ctx.fillStyle = 'rgba(0,0,0,0.65)';
    ctx.fillRect(sx, labelY - fontSize, textW + 8, fontSize + 4);
    ctx.fillStyle = color;
    ctx.fillText(label, sx + 4, labelY);
  }
}

interface Props {
  personFirst: boolean;
}

export function LiveStream({ personFirst }: Props) {
  const sessionId = useMemo(() => crypto.randomUUID(), []);

  const [mode, setMode] = useState<Mode>('idle');
  const [liveId, setLiveId] = useState<string | null>(null);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [alerts, setAlerts] = useState<LiveAlert[]>([]);
  const [reportAlert, setReportAlert] = useState<LiveAlert | null>(null);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [urlInput, setUrlInput] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const availableClasses = personFirst
    ? [...HELMET_CLASSES, 'person']
    : [...HELMET_CLASSES];
  const [activeClasses, setActiveClasses] = useState<Set<string>>(new Set(availableClasses));

  // Sync when personFirst changes and not yet active
  useEffect(() => {
    if (mode === 'idle' || mode === 'webcam-preview' || mode === 'ipcam-ready') {
      setActiveClasses(new Set(personFirst ? [...HELMET_CLASSES, 'person'] : [...HELMET_CLASSES]));
    }
  }, [personFirst, mode]);

  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const activeStreamRef = useRef<MediaStream | null>(null);
  // cancelRef controls whether the webcam inference loop is running
  const inferenceActiveRef = useRef(false);
  // Keep a ref so the inference loop always reads the latest filter without restart
  const activeClassesRef = useRef(activeClasses);
  useEffect(() => { activeClassesRef.current = activeClasses; }, [activeClasses]);

  // ── Webcam preview (getUserMedia, no inference yet) ──────────────────────
  useEffect(() => {
    if (mode !== 'webcam-preview') return;

    let cancelled = false;

    const start = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return; }
        activeStreamRef.current = stream;
        const video = videoRef.current;
        if (!video) return;
        video.srcObject = stream;
        await video.play();
      } catch {
        if (!cancelled) {
          setErrorMessage(appText.liveStream.webcamError);
          setMode('idle');
        }
      }
    };

    start();

    return () => {
      cancelled = true;
    };
  }, [mode]);

  // ── Webcam active (inference loop) ───────────────────────────────────────
  useEffect(() => {
    if (mode !== 'webcam-active') return;

    inferenceActiveRef.current = true;
    const captureCanvas = document.createElement('canvas');
    const MAX_SEND_W = 640;

    const loop = async () => {
      if (!inferenceActiveRef.current) return;
      const v = videoRef.current;
      if (!v || !v.videoWidth) {
        setTimeout(loop, 50);
        return;
      }

      const scale = Math.min(1, MAX_SEND_W / v.videoWidth);
      const sendW = Math.round(v.videoWidth * scale);
      const sendH = Math.round(v.videoHeight * scale);
      captureCanvas.width = sendW;
      captureCanvas.height = sendH;
      captureCanvas.getContext('2d')!.drawImage(v, 0, 0, sendW, sendH);

      const blob = await new Promise<Blob | null>((res) =>
        captureCanvas.toBlob(res, 'image/jpeg', 0.75),
      );
      if (!blob || !inferenceActiveRef.current) { loop(); return; }

      const form = new FormData();
      form.append('file', blob, 'frame.jpg');
      form.append('session_id', sessionId);
      form.append('person_first', String(personFirst));

      try {
        const res = await fetch(`${API_BASE}/api/live/webcam/frame`, {
          method: 'POST',
          body: form,
        });
        if (!inferenceActiveRef.current) return;
        if (res.ok) {
          const data = (await res.json()) as {
            detections: FrameDetection[];
            alerts: LiveAlert[];
            person_boxes: PersonBox[];
          };
          if (overlayRef.current && videoRef.current) {
            drawBboxes(
              overlayRef.current,
              videoRef.current,
              data.detections,
              data.person_boxes ?? [],
              sendW,
              sendH,
              activeClassesRef.current,
            );
          }
          const filteredAlerts = data.alerts.filter(
            (a) => activeClassesRef.current.has(a.class_name),
          );
          if (filteredAlerts.length > 0) {
            setAlerts((prev) => [...filteredAlerts, ...prev].slice(0, 50));
          }
        }
      } catch {
        // ignore frame errors
      }

      loop();
    };

    loop();

    return () => {
      inferenceActiveRef.current = false;
      if (overlayRef.current) {
        overlayRef.current.getContext('2d')?.clearRect(
          0, 0, overlayRef.current.width, overlayRef.current.height,
        );
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, sessionId]);

  // ── IP Camera alert polling ──────────────────────────────────────────────
  useEffect(() => {
    if (mode !== 'ipcam-active' || !liveId) return;

    let cancelled = false;

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/live/alerts/${liveId}`, { cache: 'no-store' });
        if (!res.ok || cancelled) return;
        const data = (await res.json()) as LiveAlert[];
        if (!cancelled) setAlerts([...data].reverse().slice(0, 50));
      } catch { /* retry next tick */ }
    };

    poll();
    const id = window.setInterval(poll, 1000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [mode, liveId]);

  // ── Handlers ─────────────────────────────────────────────────────────────

  const handleWebcamClick = () => {
    setErrorMessage('');
    setAlerts([]);
    setMode('webcam-preview');
  };

  const handleStartWebcam = () => {
    setMode('webcam-active');
  };

  const handleIpcamConnect = async () => {
    const url = urlInput.trim();
    if (!url) return;
    setIsConnecting(true);
    setErrorMessage('');
    setAlerts([]);
    try {
      const form = new FormData();
      form.append('stream_url', url);
      form.append('source', 'IP Camera');
      const res = await fetch(`${API_BASE}/api/live/start`, {
        method: 'POST',
        body: form,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const { live_id } = (await res.json()) as { live_id: string; source: string };
      setLiveId(live_id);
      setMode('ipcam-ready');
    } catch {
      setErrorMessage(appText.liveStream.ipcamError);
    } finally {
      setIsConnecting(false);
    }
  };

  const handleStartIpcam = () => {
    if (!liveId) return;
    const classParam = [...activeClasses].join(',');
    const url =
      `${API_BASE}/api/live/stream` +
      `?live_id=${encodeURIComponent(liveId)}` +
      `&classes=${encodeURIComponent(classParam)}`;
    setStreamUrl(url);
    setMode('ipcam-active');
  };

  const toggleClass = (cls: string) => {
    setActiveClasses((prev) => {
      const next = new Set(prev);
      if (next.has(cls)) { next.delete(cls); } else { next.add(cls); }
      return next;
    });
  };

  const handleStop = () => {
    inferenceActiveRef.current = false;
    if (activeStreamRef.current) {
      activeStreamRef.current.getTracks().forEach((t) => t.stop());
      activeStreamRef.current = null;
    }
    setMode('idle');
    setStreamUrl(null);
    setLiveId(null);
    setAlerts([]);
    setErrorMessage('');
  };

  const handleDownloadPdf = async () => {
    if (!alerts.length) return;
    setIsDownloadingPdf(true);
    try {
      const body = alerts.map((a) => ({
        id: a.id,
        timestamp: a.wall_time,
        class_name: a.class_name,
        confidence: a.confidence,
        crop_base64: a.crop?.startsWith('data:') ? a.crop.split(',')[1] : a.crop,
      }));
      const res = await fetch(`${API_BASE}/api/report/simple-pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) { alert('Không thể tạo PDF.'); return; }
      const blob = await res.blob();
      const disposition = res.headers.get('content-disposition') ?? '';
      const rfc5987 = disposition.match(/filename\*=utf-8''([^\s;]+)/i);
      const simple = disposition.match(/filename="([^"]+)"/);
      const filename = rfc5987 ? decodeURIComponent(rfc5987[1]) : simple ? simple[1] : 'bao_cao.pdf';
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setIsDownloadingPdf(false);
    }
  };

  // ── Filter panel (reused for webcam-preview, ipcam-ready) ────────────────
  const ClassFilterPanel = ({ note }: { note: string }) => (
    <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-stone-300">{appText.bboxControls.filterLabel}</p>
        <p className="text-[10px] text-stone-500">{note}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {availableClasses.map((cls) => {
          const active = activeClasses.has(cls);
          const color = getColor(cls);
          return (
            <button
              key={cls}
              onClick={() => toggleClass(cls)}
              className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition ${
                active
                  ? 'border-white/20 bg-white/10 text-stone-100'
                  : 'border-white/5 bg-stone-950/50 text-stone-500'
              }`}
            >
              <span
                className="h-2 w-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: active ? color : '#525252' }}
              />
              {CLASS_LABELS[cls]}
            </button>
          );
        })}
      </div>
    </div>
  );

  const isLiveActive = mode === 'webcam-active' || mode === 'ipcam-active';
  const isVideoVisible = mode === 'webcam-preview' || mode === 'webcam-active';
  const showFeed = isLiveActive || isVideoVisible;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">

      {/* ── Feed container (visible while webcam is running or ipcam active) ── */}
      {showFeed ? (
        <div className="overflow-hidden rounded-[1.75rem] border border-white/10 bg-stone-950 transition">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <p className="text-sm font-semibold text-white">
              {appText.liveStream.sectionTitle}
            </p>
            {isLiveActive ? (
              <span className="rounded-full border border-red-400/20 bg-red-400/10 px-3 py-1 text-xs uppercase tracking-[0.2em] text-red-200">
                ● LIVE
              </span>
            ) : (
              <span className="rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1 text-xs text-amber-200">
                {appText.liveStream.webcamConnecting}
              </span>
            )}
          </div>

          {/* Feed area */}
          <div className="relative">
            {isVideoVisible && (
              <>
                <video
                  ref={videoRef}
                  className="block w-full aspect-video object-contain bg-black"
                  muted
                  playsInline
                />
                <canvas
                  ref={overlayRef}
                  className="pointer-events-none absolute inset-0"
                  style={{ width: '100%', height: '100%' }}
                />
              </>
            )}

            {mode === 'ipcam-active' && streamUrl && (
              <img
                src={streamUrl}
                alt="IP Camera stream"
                className="block w-full aspect-video object-contain"
                onError={() => {
                  setErrorMessage(appText.liveStream.ipcamError);
                  handleStop();
                }}
              />
            )}

            {/* Stop button */}
            <button
              onClick={handleStop}
              aria-label="Stop stream"
              className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-full bg-stone-900/80 text-stone-300 backdrop-blur transition hover:bg-red-500 hover:text-white"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          {/* Active class indicator (shown when inference is live) */}
          {isLiveActive && activeClasses.size > 0 && (
            <div className="flex flex-wrap items-center gap-2 border-t border-white/[0.06] px-4 py-2">
              <span className="text-[10px] text-stone-500">{appText.bboxControls.activeFilterLabel}</span>
              {[...activeClasses].map((cls) => {
                const color = getColor(cls);
                return (
                  <span
                    key={cls}
                    className="flex items-center gap-1 rounded-full border border-white/10 bg-white/10 px-2.5 py-0.5 text-[10px] font-medium text-stone-200"
                  >
                    <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ backgroundColor: color }} />
                    {CLASS_LABELS[cls]}
                  </span>
                );
              })}
            </div>
          )}

          {/* Webcam preview: filter + start button */}
          {mode === 'webcam-preview' && (
            <div className="space-y-4 p-5 border-t border-white/10">
              <p className="text-sm text-stone-400">{appText.detection.previewReady}</p>
              <ClassFilterPanel note="Bộ lọc áp dụng realtime trên canvas — có thể thay đổi khi đang chạy" />
              <button
                onClick={handleStartWebcam}
                disabled={activeClasses.size === 0}
                className="w-full rounded-2xl bg-amber-300 py-3 text-sm font-bold text-stone-950 transition hover:bg-amber-200 disabled:opacity-40"
              >
                {appText.detection.startButton}
              </button>
            </div>
          )}
        </div>
      ) : mode === 'ipcam-ready' ? (
        /* ── IP camera ready: filter + start ─── */
        <div className="overflow-hidden rounded-[1.75rem] border border-amber-400/20 bg-stone-950">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <p className="text-sm font-semibold text-white">{appText.liveStream.sectionTitle}</p>
            <div className="flex items-center gap-2">
              <span className="rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1 text-xs text-amber-200">
                IP Camera
              </span>
              <button
                onClick={handleStop}
                aria-label="Cancel"
                className="flex h-7 w-7 items-center justify-center rounded-full bg-stone-900/80 text-stone-400 backdrop-blur transition hover:bg-red-500 hover:text-white"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          </div>
          <div className="space-y-4 p-5">
            <p className="text-sm text-stone-400">{appText.detection.ipcamReady}</p>
            <ClassFilterPanel note={appText.detection.filterPresetNote} />
            <button
              onClick={handleStartIpcam}
              disabled={activeClasses.size === 0}
              className="w-full rounded-2xl bg-amber-300 py-3 text-sm font-bold text-stone-950 transition hover:bg-amber-200 disabled:opacity-40"
            >
              {appText.detection.startButton}
            </button>
          </div>
        </div>
      ) : (
        /* ── Idle / connect zone ─── */
        <div className="flex aspect-video flex-col items-center justify-center gap-5 overflow-hidden rounded-[1.75rem] border border-dashed border-white/10 bg-stone-950 transition hover:border-amber-400/20">
          {/* Mode buttons */}
          <div className="flex gap-4">
            <button
              onClick={handleWebcamClick}
              className="flex flex-col items-center gap-2 rounded-[1.25rem] border border-white/10 bg-white/5 px-8 py-5 text-center transition hover:border-amber-400/40 hover:bg-stone-900/60"
            >
              <span className="text-3xl">📷</span>
              <span className="text-sm font-semibold text-stone-200">
                {appText.liveStream.webcamLabel}
              </span>
              <span className="text-xs text-stone-500">
                {appText.liveStream.webcamHint}
              </span>
            </button>

            <div className="flex flex-col items-center gap-2 rounded-[1.25rem] border border-white/10 bg-white/5 px-8 py-5 text-center opacity-60">
              <span className="text-3xl">📱</span>
              <span className="text-sm font-semibold text-stone-200">
                {appText.liveStream.ipcamLabel}
              </span>
              <span className="text-xs text-stone-500">
                {appText.liveStream.ipcamHint}
              </span>
            </div>
          </div>

          {/* URL input */}
          <div className="flex w-full max-w-md gap-2 px-6">
            <input
              type="text"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleIpcamConnect(); }}
              placeholder={appText.liveStream.urlPlaceholder}
              className="flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-200 placeholder-stone-600 outline-none focus:border-amber-400/40"
            />
            <button
              onClick={handleIpcamConnect}
              disabled={isConnecting || !urlInput.trim()}
              className="rounded-xl bg-amber-300 px-4 py-2 text-sm font-semibold text-stone-950 transition hover:bg-amber-200 disabled:opacity-40"
            >
              {isConnecting ? '...' : appText.liveStream.connectButton}
            </button>
          </div>

          <p className="px-6 text-center text-xs text-stone-600">
            {appText.liveStream.phoneGuide}
          </p>

          {errorMessage && (
            <p className="text-xs text-red-400">{errorMessage}</p>
          )}
        </div>
      )}

      {reportAlert && (
        <ReportModal
          alertId={reportAlert.id}
          className={reportAlert.class_name}
          timestamp={reportAlert.wall_time}
          source="Live Stream"
          cropDataUrl={reportAlert.crop}
          onClose={() => setReportAlert(null)}
        />
      )}

      {/* Violation alerts */}
      {alerts.length > 0 && (
        <section className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">
              {appText.liveStream.alertsTitle}
            </h2>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-red-500/20 px-3 py-1 text-xs text-red-300">
                {alerts.length} {appText.liveStream.alertsSuffix}
              </span>
              <button
                onClick={handleDownloadPdf}
                disabled={isDownloadingPdf}
                className="rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1 text-xs text-amber-200 transition hover:bg-amber-400/20 disabled:opacity-40"
              >
                {isDownloadingPdf ? '...' : appText.report.downloadPdf}
              </button>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {alerts.map((alert) => {
              const color = getColor(alert.class_name);
              return (
                <div
                  key={alert.id}
                  className="w-full rounded-[1.25rem] border border-white/10 bg-stone-950/70"
                >
                  <div className="overflow-hidden rounded-t-[1.25rem] bg-stone-900">
                    <img src={alert.crop} alt={alert.class_name} className="h-36 w-full object-contain" />
                  </div>
                  <div className="flex items-center justify-between gap-3 p-4">
                    <div>
                      <p className="text-sm font-semibold uppercase tracking-[0.2em]" style={{ color }}>
                        {alert.class_name}
                      </p>
                      <p className="mt-1 text-xl font-bold text-white">
                        {(alert.confidence * 100).toFixed(1)}%
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <span className="rounded-full bg-white/10 px-3 py-1 font-mono text-xs text-stone-200">
                        {alert.wall_time}
                      </span>
                      <button
                        onClick={() => setReportAlert(alert)}
                        className="rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1 text-xs text-amber-200 transition hover:bg-amber-400/20"
                      >
                        {appText.report.viewReport}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
