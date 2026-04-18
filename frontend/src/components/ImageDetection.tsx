import { useEffect, useRef, useState } from 'react';

import appText from '../content/app-text.vi.json';
import { API_BASE } from '../services/api';
import { BBoxCanvas, getColor, type Detection } from './BBoxCanvas';

export function ImageDetection() {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [cropUrls, setCropUrls] = useState<Record<string, string>>({});
  const [isUploading, setIsUploading] = useState(false);
  const [statusMessage, setStatusMessage] = useState(appText.upload.defaultStatus);
  const [bboxOpacity, setBboxOpacity] = useState(0.35);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);

  const imageContainerRef = useRef<HTMLDivElement>(null);
  const highlightTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  // Generate cropped images whenever detections change
  useEffect(() => {
    if (!previewUrl || detections.length === 0) {
      setCropUrls({});
      return;
    }

    const img = new Image();
    img.onload = () => {
      const crops: Record<string, string> = {};
      for (const det of detections) {
        const cw = det.x2 - det.x1;
        const ch = det.y2 - det.y1;
        if (cw <= 0 || ch <= 0) continue;
        const canvas = document.createElement('canvas');
        canvas.width = cw;
        canvas.height = ch;
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.drawImage(img, det.x1, det.y1, cw, ch, 0, 0, cw, ch);
          crops[det.id] = canvas.toDataURL('image/jpeg', 0.92);
        }
      }
      setCropUrls(crops);
    };
    img.src = previewUrl;
  }, [previewUrl, detections]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(file));
    setDetections([]);
    setCropUrls({});
    setHighlightedId(null);
    setIsUploading(true);
    setStatusMessage(appText.upload.sendingStatus);

    try {
      const form = new FormData();
      form.append('file', file);
      form.append('source', file.name);
      const res = await fetch(`${API_BASE}/api/detect/image`, { method: 'POST', body: form });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const payload = (await res.json()) as { boxes: Detection[] };
      setDetections(payload.boxes);
      setStatusMessage(
        payload.detections.length > 0
          ? `${appText.upload.successFoundPrefix} ${payload.detections.length} ${appText.upload.successFoundSuffix}`
          : appText.upload.successEmpty,
      );
    } catch {
      setStatusMessage(appText.upload.failure);
      setDetections([]);
    } finally {
      setIsUploading(false);
      e.target.value = '';
    }
  };

  const handleClear = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setDetections([]);
    setCropUrls({});
    setHighlightedId(null);
    setStatusMessage(appText.upload.defaultStatus);
  };

  const handleCardClick = (id: string) => {
    if (highlightTimerRef.current) clearTimeout(highlightTimerRef.current);
    setHighlightedId(id);
    imageContainerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    highlightTimerRef.current = setTimeout(() => setHighlightedId(null), 2500);
  };

  return (
    <div className="space-y-6">
      {/* Status bar */}
      {previewUrl && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-stone-300">{statusMessage}</p>
        </div>
      )}

      {/* Image preview / annotated canvas / empty drop zone */}
      {previewUrl ? (
        <div ref={imageContainerRef} className="relative overflow-hidden rounded-[1.75rem] border border-white/10 bg-stone-950">
          {/* X button */}
          <button
            onClick={handleClear}
            aria-label="Remove image"
            className="absolute right-3 top-3 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-stone-900/80 text-stone-300 backdrop-blur transition hover:bg-red-500 hover:text-white"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>

          {detections.length > 0 ? (
            <BBoxCanvas
              imageSrc={previewUrl}
              detections={detections}
              opacity={bboxOpacity}
              highlightedId={highlightedId}
            />
          ) : (
            <img
              src={previewUrl}
              alt="Uploaded preview"
              className="block w-full object-contain"
            />
          )}
        </div>
      ) : (
        <label className="flex aspect-video cursor-pointer flex-col items-center justify-center gap-4 overflow-hidden rounded-[1.75rem] border border-dashed border-white/10 bg-stone-950 transition hover:border-amber-400/40 hover:bg-stone-900/60">
          <div className="flex h-14 w-14 items-center justify-center rounded-full border border-white/10 bg-white/5">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6 text-amber-300">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-stone-300">{appText.actions.uploadIdle}</p>
            <p className="mt-1 text-xs text-stone-500">{appText.imagePreview.empty}</p>
          </div>
          <input
            type="file"
            accept="image/png,image/jpeg"
            className="hidden"
            onChange={handleUpload}
            disabled={isUploading}
          />
        </label>
      )}

      {/* Opacity slider */}
      {detections.length > 0 && (
        <div className="flex items-center gap-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
          <p className="shrink-0 text-xs text-stone-400">{appText.bboxControls.opacityLabel}</p>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={bboxOpacity}
            onChange={(e) => setBboxOpacity(parseFloat(e.target.value))}
            className="flex-1 accent-amber-300"
          />
          <span className="w-12 shrink-0 text-right font-mono text-xs text-stone-300">
            {Math.round(bboxOpacity * 100)}%
          </span>
        </div>
      )}

      {/* Detection result cards */}
      {detections.length > 0 && (
        <section className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">{appText.results.title}</h2>
            <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-stone-200">
              {appText.meta.detectionsLabel}: {detections.length}
            </span>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {detections.map((det) => {
              const color = getColor(det.class_name);
              const isHighlighted = highlightedId === det.id;
              return (
                <button
                  key={det.id}
                  onClick={() => handleCardClick(det.id)}
                  className={`group w-full rounded-[1.25rem] border text-left transition ${
                    isHighlighted
                      ? 'border-white/40 bg-white/10 shadow-lg'
                      : 'border-white/10 bg-stone-950/70 hover:border-white/20 hover:bg-stone-900/80'
                  }`}
                >
                  {/* Cropped image */}
                  <div className="overflow-hidden rounded-t-[1.25rem] bg-stone-900">
                    {cropUrls[det.id] ? (
                      <img
                        src={cropUrls[det.id]}
                        alt={det.class_name}
                        className="h-36 w-full object-contain"
                      />
                    ) : (
                      <div className="flex h-36 items-center justify-center">
                        <span className="text-xs text-stone-600">loading…</span>
                      </div>
                    )}
                  </div>

                  {/* Info row */}
                  <div className="flex items-center justify-between gap-3 p-4">
                    <div>
                      <p className="text-sm font-semibold uppercase tracking-[0.2em]" style={{ color }}>
                        {det.class_name}
                      </p>
                      <p className="mt-1 text-xl font-bold text-white">
                        {(det.confidence * 100).toFixed(1)}%
                      </p>
                    </div>
                    <div className="text-right">
                      <span className="rounded-full bg-amber-300/10 px-3 py-1 text-xs text-amber-200">
                        {det.id}
                      </span>
                      <p className="mt-2 text-xs text-stone-500 group-hover:text-stone-400">
                        Click to highlight ↑
                      </p>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
