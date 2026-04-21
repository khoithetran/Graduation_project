import { useEffect, useRef } from 'react';

export type Detection = {
  id: string;
  class_name: string;
  confidence: number;
  /** Normalized left edge (0–1) relative to original image width */
  x: number;
  /** Normalized top edge (0–1) relative to original image height */
  y: number;
  /** Normalized box width (0–1) relative to original image width */
  width: number;
  /** Normalized box height (0–1) relative to original image height */
  height: number;
  /** Absolute pixel coordinates from the API */
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

export const CLASS_COLORS: Record<string, string> = {
  helmet: '#22c55e',
  head: '#ef4444',
  'non-helmet': '#eab308',
  person: '#ff8c00',
};

export function getColor(className: string): string {
  const lower = className.toLowerCase();
  const exact = CLASS_COLORS[lower];
  if (exact) return exact;
  // Fuzzy match for common dataset naming variations
  if (lower.includes('helmet')) {
    if (lower.includes('no') || lower.includes('non') || lower.includes('without')) {
      return CLASS_COLORS['non-helmet']; // yellow
    }
    return CLASS_COLORS['helmet']; // green
  }
  if (lower.includes('head')) return CLASS_COLORS['head']; // red
  return '#94a3b8';
}

interface BBoxCanvasProps {
  imageSrc: string;
  detections: Detection[];
  /** Fill opacity 0–1. Stroke and label are always fully opaque. */
  opacity: number;
  highlightedId?: string | null;
  className?: string;
  /** When set, only detections whose class_name is in this set are drawn. */
  filteredClasses?: Set<string>;
}

function drawBox(
  ctx: CanvasRenderingContext2D,
  det: Detection,
  w: number,
  h: number,
  opacity: number,
  highlighted: boolean,
) {
  const x = det.x * w;
  const y = det.y * h;
  const bw = det.width * w;
  const bh = det.height * h;
  const color = getColor(det.class_name);
  const strokeWidth = highlighted ? Math.max(4, w / 200) : Math.max(2, w / 400);

  // Fill
  ctx.globalAlpha = highlighted ? Math.min(opacity + 0.15, 1) : opacity;
  ctx.fillStyle = color;
  ctx.fillRect(x, y, bw, bh);
  ctx.globalAlpha = 1;

  // Glow for highlighted box
  if (highlighted) {
    ctx.shadowColor = color;
    ctx.shadowBlur = 18;
  }

  ctx.strokeStyle = highlighted ? '#ffffff' : color;
  ctx.lineWidth = strokeWidth;
  ctx.strokeRect(x, y, bw, bh);
  ctx.shadowBlur = 0;

  // Inner colored border for highlighted
  if (highlighted) {
    ctx.strokeStyle = color;
    ctx.lineWidth = Math.max(2, w / 500);
    ctx.strokeRect(x + strokeWidth, y + strokeWidth, bw - strokeWidth * 2, bh - strokeWidth * 2);
  }

  // Label
  const fontSize = Math.max(14, w / 60);
  const label = `${det.class_name} ${(det.confidence * 100).toFixed(1)}%`;
  ctx.font = `bold ${fontSize}px monospace`;
  const textW = ctx.measureText(label).width;
  const textH = fontSize;
  const textY = y > textH + 4 ? y - 4 : y + bh + textH;

  ctx.fillStyle = 'rgba(0,0,0,0.65)';
  ctx.beginPath();
  ctx.roundRect(x, textY - textH, textW + 8, textH + 4, 4);
  ctx.fill();

  ctx.fillStyle = highlighted ? '#ffffff' : color;
  ctx.fillText(label, x + 4, textY);
}

export function BBoxCanvas({ imageSrc, detections, opacity, highlightedId, className, filteredClasses }: BBoxCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const img = new Image();
    img.onload = () => {
      const w = img.naturalWidth;
      const h = img.naturalHeight;
      canvas.width = w;
      canvas.height = h;

      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      ctx.drawImage(img, 0, 0, w, h);

      const visible = filteredClasses
        ? detections.filter((d) => filteredClasses.has(d.class_name))
        : detections;

      // Draw non-highlighted boxes first, highlighted on top
      for (const det of visible) {
        if (det.id !== highlightedId) drawBox(ctx, det, w, h, opacity, false);
      }
      for (const det of visible) {
        if (det.id === highlightedId) drawBox(ctx, det, w, h, opacity, true);
      }
    };
    img.src = imageSrc;
  }, [imageSrc, detections, opacity, highlightedId, filteredClasses]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{ width: '100%', height: 'auto', display: 'block' }}
    />
  );
}
