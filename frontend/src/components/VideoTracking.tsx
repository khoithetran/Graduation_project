import { useEffect, useRef, useState } from 'react';

import appText from '../content/app-text.vi.json';
import { API_BASE } from '../services/api';
import { formatTime } from '../utils/format';
import type { VideoAlert } from '../types';
import { getColor } from './BBoxCanvas';
import { AlertDetailModal } from './AlertDetailModal';
import { ReportModal } from './ReportModal';
import { LoadingOverlay } from './LoadingOverlay';

// Standard helmet-model classes + optional person class
const HELMET_CLASSES = ['helmet', 'head', 'non-helmet'] as const;
const CLASS_LABELS: Record<string, string> = {
  helmet: appText.bboxControls.classHelmet,
  head: appText.bboxControls.classHead,
  'non-helmet': appText.bboxControls.classNonHelmet,
  person: appText.bboxControls.classPerson,
};

type VideoState = 'idle' | 'uploaded' | 'streaming';

interface Props {
  personFirst: boolean;
}

export function VideoTracking({ personFirst }: Props) {
  const [videoState, setVideoState] = useState<VideoState>('idle');
  const [videoId, setVideoId] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [statusMessage, setStatusMessage] = useState(appText.videoTracking.defaultStatus);
  const [isPaused, setIsPaused] = useState(false);
  const [frozenFrame, setFrozenFrame] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<VideoAlert[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<VideoAlert | null>(null);
  const [reportAlert, setReportAlert] = useState<VideoAlert | null>(null);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);

  // Class filter — default all on; person added when personFirst is active
  const availableClasses = personFirst
    ? [...HELMET_CLASSES, 'person']
    : [...HELMET_CLASSES];
  const [activeClasses, setActiveClasses] = useState<Set<string>>(new Set(availableClasses));
  // Snapshot of activeClasses at the moment stream was started — used for badge display and alert filtering
  const [streamActiveClasses, setStreamActiveClasses] = useState<Set<string>>(new Set());

  // Sync availableClasses into activeClasses when personFirst changes (pre-start only)
  useEffect(() => {
    if (videoState !== 'streaming') {
      setActiveClasses(new Set(personFirst ? [...HELMET_CLASSES, 'person'] : [...HELMET_CLASSES]));
    }
  }, [personFirst, videoState]);

  const imgRef = useRef<HTMLImageElement>(null);

  // Poll for alerts while streaming
  useEffect(() => {
    if (!videoId || videoState !== 'streaming') return;

    let cancelled = false;

    const poll = async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/stream/video/alerts?video_id=${encodeURIComponent(videoId)}`,
          { cache: 'no-store' },
        );
        if (!res.ok) return;
        const data = (await res.json()) as VideoAlert[];
        if (!cancelled) {
          setAlerts(
            streamActiveClasses.size > 0
              ? data.filter((a) => streamActiveClasses.has(a.class_name))
              : data,
          );
        }
      } catch {
        // ignore poll errors silently
      }
    };

    poll();
    const id = window.setInterval(poll, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [videoId, videoState]);

  const handleStreamError = () => {
    setStreamUrl(null);
    setVideoState('idle');
    setStatusMessage(appText.videoTracking.failure);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setStreamUrl(null);
    setVideoState('idle');
    setIsPaused(false);
    setFrozenFrame(null);
    setAlerts([]);
    setVideoId(null);
    setFileName(null);
    setStatusMessage(appText.videoTracking.uploadLoading);

    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API_BASE}/api/upload-video`, { method: 'POST', body: form });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const { video_id, file_name } = (await res.json()) as {
        video_id: string;
        file_name: string;
      };
      setVideoId(video_id);
      setFileName(file_name);
      setVideoState('uploaded');
      setStatusMessage(appText.videoTracking.uploadedReady);
    } catch {
      setStatusMessage(appText.videoTracking.failure);
    } finally {
      setIsUploading(false);
      e.target.value = '';
    }
  };

  const handleStartDetection = () => {
    if (!videoId || !fileName) return;
    const classParam = [...activeClasses].join(',');
    const url =
      `${API_BASE}/api/stream/video` +
      `?video_id=${encodeURIComponent(videoId)}` +
      `&file_name=${encodeURIComponent(fileName)}` +
      `&classes=${encodeURIComponent(classParam)}` +
      `&person_first=${personFirst}`;
    setStreamActiveClasses(new Set(activeClasses));
    setStreamUrl(url);
    setVideoState('streaming');
    setStatusMessage(appText.videoTracking.streamingStatus);
  };

  const handleClear = () => {
    setStreamUrl(null);
    setIsPaused(false);
    setFrozenFrame(null);
    setAlerts([]);
    setVideoId(null);
    setFileName(null);
    setStreamActiveClasses(new Set());
    setVideoState('idle');
    setStatusMessage(appText.videoTracking.defaultStatus);
  };

  const togglePause = () => {
    if (!isPaused) {
      const img = imgRef.current;
      if (img) {
        try {
          const canvas = document.createElement('canvas');
          canvas.width = img.naturalWidth || img.clientWidth;
          canvas.height = img.naturalHeight || img.clientHeight;
          canvas.getContext('2d')?.drawImage(img, 0, 0);
          setFrozenFrame(canvas.toDataURL('image/jpeg', 0.92));
        } catch {
          // CORS blocked
        }
      }
    } else {
      setFrozenFrame(null);
    }
    setIsPaused((p) => !p);
  };

  const toggleClass = (cls: string) => {
    setActiveClasses((prev) => {
      const next = new Set(prev);
      if (next.has(cls)) {
        next.delete(cls);
      } else {
        next.add(cls);
      }
      return next;
    });
  };

  const handleAlertClick = (alert: VideoAlert) => {
    setSelectedAlert(alert);
  };

  const handleDownloadPdf = async () => {
    if (!alerts.length) return;
    setIsDownloadingPdf(true);
    try {
      const body = alerts.map((a) => ({
        id: a.id,
        timestamp: new Date(a.timestamp_sec * 1000).toLocaleString('vi-VN'),
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

  // ── Render helpers ─────────────────────────────────────────────────────────

  const ClassFilterPanel = () => (
    <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-stone-300">{appText.bboxControls.filterLabel}</p>
        <p className="text-[10px] text-stone-500">{appText.detection.filterPresetNote}</p>
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

  return (
    <div className="space-y-6">
      {/* Status bar */}
      {videoState !== 'idle' && (
        <p className="text-sm text-stone-300">
          {videoState === 'streaming' && isPaused ? 'Paused' : statusMessage}
        </p>
      )}

      {/* Video player / upload zone */}
      {isUploading ? (
        <div className="relative aspect-video overflow-hidden rounded-[1.75rem] border border-white/10 bg-stone-950">
          <LoadingOverlay label={appText.videoTracking.uploadLoading} />
        </div>
      ) : videoState === 'streaming' && streamUrl ? (
        <div className="overflow-hidden rounded-[1.75rem] border bg-stone-950 border-white/10 transition">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <p className="text-sm font-semibold text-white">{appText.videoTracking.sectionTitle}</p>
            <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs uppercase tracking-[0.2em] text-emerald-200">
              ByteTrack
            </span>
          </div>
          {streamActiveClasses.size > 0 && (
            <div className="flex flex-wrap items-center gap-2 border-b border-white/[0.06] px-4 py-2">
              <span className="text-[10px] text-stone-500">{appText.bboxControls.activeFilterLabel}</span>
              {[...streamActiveClasses].map((cls) => {
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

          <div className="group relative cursor-pointer" onClick={togglePause}>
            <img
              ref={imgRef}
              src={streamUrl}
              crossOrigin="anonymous"
              alt="Video tracking stream"
              className={`block w-full aspect-video object-contain${isPaused ? ' invisible' : ''}`}
              onError={handleStreamError}
            />

            {isPaused && (
              <div className="absolute inset-0">
                {frozenFrame ? (
                  <img src={frozenFrame} alt="Paused frame" className="h-full w-full object-contain" />
                ) : (
                  <div className="flex h-full items-center justify-center bg-stone-950">
                    <p className="text-sm text-stone-500">Paused</p>
                  </div>
                )}
              </div>
            )}

            {/* X button */}
            <button
              onClick={(e) => { e.stopPropagation(); handleClear(); }}
              aria-label="Stop stream"
              className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-full bg-stone-900/80 text-stone-300 backdrop-blur transition hover:bg-red-500 hover:text-white"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>

            {/* Play/pause icon */}
            <div className={`pointer-events-none absolute inset-0 flex items-center justify-center transition-opacity ${isPaused ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-black/60 backdrop-blur">
                {isPaused ? (
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-7 w-7 translate-x-0.5 text-white">
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-7 w-7 text-white">
                    <rect x="6" y="4" width="4" height="16" /><rect x="14" y="4" width="4" height="16" />
                  </svg>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : videoState === 'uploaded' ? (
        /* ── Uploaded: filter + start ─── */
        <div className="overflow-hidden rounded-[1.75rem] border border-amber-400/20 bg-stone-950">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <p className="text-sm font-semibold text-white">{appText.videoTracking.sectionTitle}</p>
            <div className="flex items-center gap-2">
              <span className="rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1 text-xs text-amber-200">
                {appText.videoTracking.uploadedReady.split('.')[0]}
              </span>
              <button
                onClick={handleClear}
                aria-label="Remove video"
                className="flex h-7 w-7 items-center justify-center rounded-full bg-stone-900/80 text-stone-400 backdrop-blur transition hover:bg-red-500 hover:text-white"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          </div>
          <div className="space-y-4 p-5">
            <p className="text-sm text-stone-400">{appText.videoTracking.uploadedReady}</p>
            <ClassFilterPanel />
            <button
              onClick={handleStartDetection}
              disabled={activeClasses.size === 0}
              className="w-full rounded-2xl bg-amber-300 py-3 text-sm font-bold text-stone-950 transition hover:bg-amber-200 disabled:opacity-40"
            >
              {appText.detection.startButton}
            </button>
          </div>
        </div>
      ) : (
        /* ── Idle: upload zone ─── */
        <label className="flex aspect-video cursor-pointer flex-col items-center justify-center gap-4 overflow-hidden rounded-[1.75rem] border border-dashed border-white/10 bg-stone-950 transition hover:border-amber-400/40 hover:bg-stone-900/60">
          <div className="flex h-14 w-14 items-center justify-center rounded-full border border-white/10 bg-white/5">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6 text-amber-300">
              <polygon points="23 7 16 12 23 17 23 7" />
              <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
            </svg>
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-stone-300">{appText.videoTracking.uploadIdle}</p>
            <p className="mt-1 text-xs text-stone-500">{appText.videoTracking.defaultStatus}</p>
          </div>
          <input type="file" accept="video/*" className="hidden" onChange={handleUpload} disabled={isUploading} />
        </label>
      )}

      {/* Violation alerts */}
      {alerts.length > 0 && (
        <section className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Violation Alerts</h2>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-red-500/20 px-3 py-1 text-xs text-red-300">
                {alerts.length} detected
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
              const isActive = selectedAlert?.id === alert.id;
              return (
                <button
                  key={alert.id}
                  onClick={() => handleAlertClick(alert)}
                  className={`group w-full rounded-[1.25rem] border text-left transition ${
                    isActive
                      ? 'border-amber-400/50 bg-amber-300/10 shadow-lg'
                      : 'border-white/10 bg-stone-950/70 hover:border-white/20 hover:bg-stone-900/80'
                  }`}
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
                        {formatTime(alert.timestamp_sec)}
                      </span>
                      <button
                        onClick={(e) => { e.stopPropagation(); setReportAlert(alert); }}
                        className="rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1 text-xs text-amber-200 transition hover:bg-amber-400/20"
                      >
                        Xem báo cáo
                      </button>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {selectedAlert && videoId && (
        <AlertDetailModal
          alert={selectedAlert}
          videoId={videoId}
          onClose={() => setSelectedAlert(null)}
        />
      )}

      {reportAlert && (
        <ReportModal
          alertId={reportAlert.id}
          className={reportAlert.class_name}
          timestamp={new Date(reportAlert.timestamp_sec * 1000).toISOString()}
          source="Video Upload"
          cropDataUrl={reportAlert.crop}
          onClose={() => setReportAlert(null)}
        />
      )}
    </div>
  );
}
