import { useEffect, useRef, useState, useMemo } from 'react';

import appText from '../content/app-text.vi.json';
import { API_BASE } from '../services/api';
import type { LiveAlert } from '../types';
import { getColor } from './BBoxCanvas';
import { ReportModal } from './ReportModal';

type Mode = 'idle' | 'webcam' | 'ipcam';

type FrameDetection = {
  class_name: string;
  confidence: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

function drawBboxes(
  canvas: HTMLCanvasElement,
  video: HTMLVideoElement,
  detections: FrameDetection[],
  sendW: number,
  sendH: number,
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

  for (const det of detections) {
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

export function LiveStream() {
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

  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  // Store stream separately — videoRef.current becomes null when <video> is removed from DOM
  const activeStreamRef = useRef<MediaStream | null>(null);

  // ── Webcam mode ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (mode !== 'webcam') return;

    let cancelled = false;
    // Off-screen canvas for resizing frames before upload
    const captureCanvas = document.createElement('canvas');
    // Max width sent to backend — smaller = faster inference
    const MAX_SEND_W = 640;

    const start = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        activeStreamRef.current = stream;
        const video = videoRef.current;
        if (!video) return;
        video.srcObject = stream;
        await video.play();

        // Continuous loop: capture → infer → draw → repeat immediately.
        // Only 1 request in-flight at a time → no backpressure, minimal lag.
        const loop = async () => {
          if (cancelled) return;
          const v = videoRef.current;
          if (!v || !v.videoWidth) {
            setTimeout(loop, 50);
            return;
          }

          // Resize to MAX_SEND_W (keep aspect ratio) — reduces transfer + inference time
          const scale = Math.min(1, MAX_SEND_W / v.videoWidth);
          const sendW = Math.round(v.videoWidth * scale);
          const sendH = Math.round(v.videoHeight * scale);
          captureCanvas.width = sendW;
          captureCanvas.height = sendH;
          captureCanvas.getContext('2d')!.drawImage(v, 0, 0, sendW, sendH);

          const blob = await new Promise<Blob | null>((res) =>
            captureCanvas.toBlob(res, 'image/jpeg', 0.75),
          );
          if (!blob || cancelled) { loop(); return; }

          const form = new FormData();
          form.append('file', blob, 'frame.jpg');
          form.append('session_id', sessionId);

          try {
            const res = await fetch(`${API_BASE}/api/live/webcam/frame`, {
              method: 'POST',
              body: form,
            });
            if (cancelled) return;
            if (!res.ok) {
              console.error('Webcam frame error:', res.status, await res.text());
            } else {
              const data = (await res.json()) as {
                detections: FrameDetection[];
                alerts: LiveAlert[];
              };
              if (overlayRef.current && videoRef.current) {
                drawBboxes(overlayRef.current, videoRef.current, data.detections, sendW, sendH);
              }
              if (data.alerts.length > 0) {
                setAlerts((prev) => [...data.alerts, ...prev].slice(0, 50));
              }
            }
          } catch (err) {
            console.error('Webcam frame fetch failed:', err);
          }

          loop();
        };

        loop();
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
      // Use activeStreamRef — guaranteed non-null even after <video> is removed from DOM
      if (activeStreamRef.current) {
        activeStreamRef.current.getTracks().forEach((t) => t.stop());
        activeStreamRef.current = null;
      }
      if (overlayRef.current) {
        overlayRef.current.getContext('2d')?.clearRect(
          0,
          0,
          overlayRef.current.width,
          overlayRef.current.height,
        );
      }
    };
  }, [mode, sessionId]);

  // ── IP Camera — alert polling ────────────────────────────────────────────
  useEffect(() => {
    if (mode !== 'ipcam' || !liveId) return;

    let cancelled = false;

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/live/alerts/${liveId}`, {
          cache: 'no-store',
        });
        if (!res.ok || cancelled) return;
        const data = (await res.json()) as LiveAlert[];
        if (!cancelled) setAlerts([...data].reverse().slice(0, 50));
      } catch {
        // Backend unreachable — retry next interval
      }
    };

    poll();
    const id = window.setInterval(poll, 1000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [mode, liveId]);

  // ── Handlers ─────────────────────────────────────────────────────────────
  const handleWebcam = () => {
    setErrorMessage('');
    setAlerts([]);
    setMode('webcam');
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
      setStreamUrl(
        `${API_BASE}/api/live/stream?live_id=${encodeURIComponent(live_id)}`,
      );
      setMode('ipcam');
    } catch {
      setErrorMessage(appText.liveStream.ipcamError);
    } finally {
      setIsConnecting(false);
    }
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

  const handleStop = () => {
    setMode('idle');
    setStreamUrl(null);
    setLiveId(null);
    setAlerts([]);
    setErrorMessage('');
  };

  const isConnected = mode === 'webcam' || mode === 'ipcam';

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      {/* Feed container */}
      {isConnected ? (
        <div className="overflow-hidden rounded-[1.75rem] border border-white/10 bg-stone-950 transition">
          {/* Header bar */}
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <p className="text-sm font-semibold text-white">
              {appText.liveStream.sectionTitle}
            </p>
            <span className="rounded-full border border-red-400/20 bg-red-400/10 px-3 py-1 text-xs uppercase tracking-[0.2em] text-red-200">
              ● LIVE
            </span>
          </div>

          {/* Feed */}
          <div className="relative">
            {mode === 'webcam' && (
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

            {mode === 'ipcam' && streamUrl && (
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
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={2.5}
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-4 w-4"
              >
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>
      ) : (
        /* Idle / connect zone */
        <div className="flex aspect-video flex-col items-center justify-center gap-5 overflow-hidden rounded-[1.75rem] border border-dashed border-white/10 bg-stone-950 transition hover:border-amber-400/20">
          {/* Mode buttons */}
          <div className="flex gap-4">
            <button
              onClick={handleWebcam}
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
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleIpcamConnect();
              }}
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

          {/* Phone guide */}
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
                    <img
                      src={alert.crop}
                      alt={alert.class_name}
                      className="h-36 w-full object-contain"
                    />
                  </div>
                  <div className="flex items-center justify-between gap-3 p-4">
                    <div>
                      <p
                        className="text-sm font-semibold uppercase tracking-[0.2em]"
                        style={{ color }}
                      >
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
