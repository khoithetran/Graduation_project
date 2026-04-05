import { useEffect, useRef, useState } from 'react';

import appText from '../content/app-text.vi.json';
import { API_BASE } from '../services/api';
import type { VideoAlert } from '../types';
import { getColor } from './BBoxCanvas';
import { AlertDetailModal } from './AlertDetailModal';

function formatTime(sec: number): string {
  const m = Math.floor(sec / 60).toString().padStart(2, '0');
  const s = (sec % 60).toFixed(1).padStart(4, '0');
  return `${m}:${s}`;
}

export function VideoTracking() {
  const [videoId, setVideoId] = useState<string | null>(null);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [statusMessage, setStatusMessage] = useState(appText.videoTracking.defaultStatus);
  const [isPaused, setIsPaused] = useState(false);
  const [frozenFrame, setFrozenFrame] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<VideoAlert[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<VideoAlert | null>(null);

  const imgRef = useRef<HTMLImageElement>(null);

  // Poll for alerts while a video is streaming
  useEffect(() => {
    if (!videoId || !streamUrl) return;

    let cancelled = false;

    const poll = async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/stream/video/alerts?video_id=${encodeURIComponent(videoId)}`,
          { cache: 'no-store' },   // prevent browser caching stale responses
        );
        if (!res.ok) {
          console.warn('[alerts] poll failed:', res.status);
          return;
        }
        const data = (await res.json()) as VideoAlert[];
        if (!cancelled) {
          // Always replace — even with 0 items — so state stays in sync
          setAlerts(data);
          if (data.length > 0) {
            console.log(`[alerts] received ${data.length} alert(s)`);
          }
        }
      } catch (err) {
        console.warn('[alerts] fetch error:', err);
      }
    };

    poll();
    const id = window.setInterval(poll, 1000);   // 1 s for faster feedback
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [videoId, streamUrl]);

  const handleStreamError = () => {
    setStreamUrl(null);
    setStatusMessage(appText.videoTracking.failure);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setStreamUrl(null);
    setIsPaused(false);
    setFrozenFrame(null);
    setAlerts([]);
    setVideoId(null);
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
      const url = `${API_BASE}/api/stream/video?video_id=${encodeURIComponent(video_id)}&file_name=${encodeURIComponent(file_name)}`;
      setStreamUrl(url);
      setStatusMessage(appText.videoTracking.streamingStatus);
    } catch {
      setStatusMessage(appText.videoTracking.failure);
    } finally {
      setIsUploading(false);
      e.target.value = '';
    }
  };

  const handleClear = () => {
    setStreamUrl(null);
    setIsPaused(false);
    setFrozenFrame(null);
    setAlerts([]);
    setVideoId(null);
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

  const handleAlertClick = (alert: VideoAlert) => {
    setSelectedAlert(alert);
  };

  return (
    <div className="space-y-6">
      {/* Status bar */}
      {streamUrl && (
        <p className="text-sm text-stone-300">
          {isPaused ? 'Paused' : statusMessage}
        </p>
      )}

      {/* Video player / upload zone */}
      {streamUrl ? (
        <div className="overflow-hidden rounded-[1.75rem] border bg-stone-950 border-white/10 transition">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <p className="text-sm font-semibold text-white">{appText.videoTracking.sectionTitle}</p>
            <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs uppercase tracking-[0.2em] text-emerald-200">
              ByteTrack
            </span>
          </div>

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
      ) : (
        <label className="flex aspect-video cursor-pointer flex-col items-center justify-center gap-4 overflow-hidden rounded-[1.75rem] border border-dashed border-white/10 bg-stone-950 transition hover:border-amber-400/40 hover:bg-stone-900/60">
          <div className="flex h-14 w-14 items-center justify-center rounded-full border border-white/10 bg-white/5">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6 text-amber-300">
              <polygon points="23 7 16 12 23 17 23 7" />
              <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
            </svg>
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-stone-300">
              {isUploading ? appText.videoTracking.uploadLoading : appText.videoTracking.uploadIdle}
            </p>
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
            <span className="rounded-full bg-red-500/20 px-3 py-1 text-xs text-red-300">
              {alerts.length} detected
            </span>
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
                  {/* Crop image */}
                  <div className="overflow-hidden rounded-t-[1.25rem] bg-stone-900">
                    <img
                      src={alert.crop}
                      alt={alert.class_name}
                      className="h-36 w-full object-contain"
                    />
                  </div>

                  {/* Info row */}
                  <div className="flex items-center justify-between gap-3 p-4">
                    <div>
                      <p className="text-sm font-semibold uppercase tracking-[0.2em]" style={{ color }}>
                        {alert.class_name}
                      </p>
                      <p className="mt-1 text-xl font-bold text-white">
                        {(alert.confidence * 100).toFixed(1)}%
                      </p>
                    </div>
                    <div className="text-right">
                      <span className="rounded-full bg-white/10 px-3 py-1 font-mono text-xs text-stone-200">
                        {formatTime(alert.timestamp_sec)}
                      </span>
                      <p className="mt-2 text-xs text-stone-500 group-hover:text-stone-400">
                        Click to view ↗
                      </p>
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
    </div>
  );
}
