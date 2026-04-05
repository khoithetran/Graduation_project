import { useEffect, useRef, useState } from 'react';
import { API_BASE } from '../services/api';
import { getColor } from './BBoxCanvas';

type VideoAlert = {
  id: string;
  timestamp_sec: number;
  class_name: string;
  confidence: number;
  crop: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

interface AlertDetailModalProps {
  alert: VideoAlert;
  videoId: string;
  onClose: () => void;
}

function formatTime(sec: number): string {
  const m = Math.floor(sec / 60).toString().padStart(2, '0');
  const s = (sec % 60).toFixed(1).padStart(4, '0');
  return `${m}:${s}`;
}

function drawBbox(
  canvas: HTMLCanvasElement,
  video: HTMLVideoElement,
  alert: VideoAlert,
) {
  const ctx = canvas.getContext('2d');
  if (!ctx || !video.videoWidth || !video.videoHeight) return;

  // Match canvas pixel size to rendered video size
  canvas.width = video.clientWidth;
  canvas.height = video.clientHeight;

  const scaleX = video.clientWidth / video.videoWidth;
  const scaleY = video.clientHeight / video.videoHeight;

  // When the video uses object-fit: contain, black bars appear. Adjust for letterboxing.
  const renderedW = video.videoWidth * Math.min(scaleX, scaleY);
  const renderedH = video.videoHeight * Math.min(scaleX, scaleY);
  const offsetX = (video.clientWidth - renderedW) / 2;
  const offsetY = (video.clientHeight - renderedH) / 2;
  const s = Math.min(scaleX, scaleY);

  const sx = alert.x1 * s + offsetX;
  const sy = alert.y1 * s + offsetY;
  const sw = (alert.x2 - alert.x1) * s;
  const sh = (alert.y2 - alert.y1) * s;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Glow pass
  ctx.shadowColor = 'rgba(251, 191, 36, 0.8)';
  ctx.shadowBlur = 12;
  ctx.strokeStyle = '#FCD34D';
  ctx.lineWidth = 3;
  ctx.strokeRect(sx, sy, sw, sh);

  // Solid inner pass (no glow)
  ctx.shadowBlur = 0;
  ctx.strokeStyle = getColor(alert.class_name);
  ctx.lineWidth = 1.5;
  ctx.strokeRect(sx + 3, sy + 3, sw - 6, sh - 6);

  // Label
  const label = `${alert.class_name} ${(alert.confidence * 100).toFixed(1)}%`;
  const fontSize = Math.max(13, canvas.width / 55);
  ctx.font = `bold ${fontSize}px monospace`;
  const textW = ctx.measureText(label).width;
  const labelX = sx;
  const labelY = sy > fontSize + 6 ? sy - 6 : sy + sh + fontSize + 4;
  ctx.fillStyle = 'rgba(0,0,0,0.7)';
  ctx.beginPath();
  ctx.roundRect(labelX, labelY - fontSize, textW + 8, fontSize + 4, 4);
  ctx.fill();
  ctx.fillStyle = '#FCD34D';
  ctx.fillText(label, labelX + 4, labelY);
}

export function AlertDetailModal({ alert, videoId, onClose }: AlertDetailModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // Seek to alert timestamp and draw bbox once metadata is loaded
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const onMeta = () => {
      setDuration(video.duration);
      video.currentTime = alert.timestamp_sec;
    };
    video.addEventListener('loadedmetadata', onMeta);
    return () => video.removeEventListener('loadedmetadata', onMeta);
  }, [alert.timestamp_sec]);

  // Draw bbox after seek lands on the right frame
  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    const onSeeked = () => {
      if (!isPlaying) drawBbox(canvas, video, alert);
    };
    video.addEventListener('seeked', onSeeked);
    return () => video.removeEventListener('seeked', onSeeked);
  }, [alert, isPlaying]);

  const handleTimeUpdate = () => {
    if (videoRef.current) setCurrentTime(videoRef.current.currentTime);
  };

  const handlePlay = () => {
    setIsPlaying(true);
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext('2d');
      ctx?.clearRect(0, 0, canvas.width, canvas.height);
    }
  };

  const handlePause = () => {
    setIsPlaying(false);
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (video && canvas) drawBbox(canvas, video, alert);
  };

  const handleEnded = () => {
    setIsPlaying(false);
  };

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      video.play();
    } else {
      video.pause();
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const video = videoRef.current;
    if (!video) return;
    const t = parseFloat(e.target.value);
    video.currentTime = t;
    setCurrentTime(t);
  };

  // Close on Escape key
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="relative w-full max-w-4xl rounded-[1.75rem] overflow-hidden bg-stone-950 border border-white/10 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/10">
          <div className="flex items-center gap-3">
            <span
              className="text-sm font-bold uppercase tracking-[0.2em]"
              style={{ color: getColor(alert.class_name) }}
            >
              {alert.class_name}
            </span>
            <span className="text-stone-500 text-sm">·</span>
            <span className="font-mono text-sm text-stone-300">
              {formatTime(alert.timestamp_sec)}
            </span>
            <span className="text-stone-500 text-sm">·</span>
            <span className="text-sm text-stone-300">
              {(alert.confidence * 100).toFixed(1)}%
            </span>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="flex h-8 w-8 items-center justify-center rounded-full bg-stone-800 text-stone-400 hover:bg-red-500 hover:text-white transition"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Video + canvas overlay */}
        <div className="relative bg-black cursor-pointer" onClick={togglePlay}>
          <video
            ref={videoRef}
            src={`${API_BASE}/api/video/file/${videoId}`}
            className="block w-full aspect-video object-contain"
            loop={false}
            playsInline
            onTimeUpdate={handleTimeUpdate}
            onPlay={handlePlay}
            onPause={handlePause}
            onEnded={handleEnded}
          />
          <canvas
            ref={canvasRef}
            className="absolute inset-0 pointer-events-none"
            style={{ width: '100%', height: '100%' }}
          />
          {/* Play/pause overlay icon */}
          <div className={`pointer-events-none absolute inset-0 flex items-center justify-center transition-opacity ${isPlaying ? 'opacity-0' : 'opacity-100'}`}>
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-black/60 backdrop-blur">
              {isPlaying ? (
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-7 w-7 text-white">
                  <rect x="6" y="4" width="4" height="16" /><rect x="14" y="4" width="4" height="16" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-7 w-7 translate-x-0.5 text-white">
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
              )}
            </div>
          </div>
        </div>

        {/* Custom progress bar */}
        <div className="px-5 py-4 space-y-2 border-t border-white/10">
          <input
            type="range"
            min={0}
            max={duration || 1}
            step={0.1}
            value={currentTime}
            onChange={handleSeek}
            className="w-full h-1.5 rounded-full appearance-none bg-white/10 accent-amber-400 cursor-pointer"
          />
          <div className="flex justify-between font-mono text-xs text-stone-500">
            <span>{formatTime(currentTime)}</span>
            <span>{formatTime(duration)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
