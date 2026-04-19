import { useEffect, useState } from 'react';
import { API_BASE } from '../services/api';

type EventReport = {
  event_id: string;
  description: string;
  risk_level: string;
  recommendations: string[];
  generated_at: string;
  status: string;
};

interface ReportModalProps {
  alertId: string;
  className: string;
  timestamp: string;
  source: string;
  cropDataUrl?: string;
  onClose: () => void;
}

const RISK_STYLES: Record<string, string> = {
  'THẤP': 'border-emerald-400/40 bg-emerald-400/15 text-emerald-200',
  'TRUNG BÌNH': 'border-amber-400/40 bg-amber-400/15 text-amber-200',
  'CAO': 'border-orange-400/40 bg-orange-400/15 text-orange-200',
  'NGHIÊM TRỌNG': 'border-red-400/40 bg-red-400/15 text-red-200',
};

function riskStyle(level: string): string {
  return RISK_STYLES[level] ?? 'border-white/20 bg-white/10 text-stone-300';
}

export function ReportModal({
  alertId,
  className,
  timestamp,
  source,
  cropDataUrl,
  onClose,
}: ReportModalProps) {
  const [report, setReport] = useState<EventReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();

    const fetchReport = async () => {
      try {
        const cropBase64 = cropDataUrl?.startsWith('data:')
          ? cropDataUrl.split(',')[1]
          : undefined;

        const body = {
          class_name: className,
          timestamp,
          source,
          num_violators: 1,
          ...(cropBase64 ? { crop_base64: cropBase64 } : {}),
        };

        const res = await fetch(
          `${API_BASE}/api/report/from-alert?alert_id=${encodeURIComponent(alertId)}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            signal: controller.signal,
          },
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setReport(await res.json() as EventReport);
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          setError('Không thể tải báo cáo. Vui lòng thử lại.');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchReport();
    return () => controller.abort();
  }, [alertId, className, timestamp, source, cropDataUrl]);

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
      <div className="relative w-full max-w-lg rounded-[1.75rem] overflow-hidden bg-stone-950 border border-white/10 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/10">
          <p className="text-sm font-semibold text-white">Báo cáo vi phạm AI</p>
          <button
            onClick={onClose}
            aria-label="Đóng"
            className="flex h-8 w-8 items-center justify-center rounded-full bg-stone-800 text-stone-400 hover:bg-red-500 hover:text-white transition"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4 max-h-[70vh] overflow-y-auto">
          {loading && (
            <div className="flex flex-col items-center gap-3 py-8 text-stone-400">
              <svg className="h-6 w-6 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
              <p className="text-sm">Đang tạo báo cáo AI...</p>
            </div>
          )}

          {error && !loading && (
            <p className="text-sm text-red-400 text-center py-6">{error}</p>
          )}

          {report && !loading && (
            <>
              {/* Risk badge */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-stone-500 uppercase tracking-wider">Mức độ rủi ro</span>
                <span className={`rounded-full border px-3 py-0.5 text-xs font-semibold uppercase tracking-[0.15em] ${riskStyle(report.risk_level)}`}>
                  {report.risk_level}
                </span>
                {report.status === 'failed' && (
                  <span className="rounded-full border border-stone-600 bg-stone-800 px-2 py-0.5 text-xs text-stone-500">
                    fallback
                  </span>
                )}
              </div>

              {/* Description */}
              <div>
                <p className="mb-1 text-xs text-stone-500 uppercase tracking-wider">Mô tả</p>
                <p className="text-sm text-stone-200 leading-relaxed">{report.description}</p>
              </div>

              {/* Recommendations */}
              <div>
                <p className="mb-2 text-xs text-stone-500 uppercase tracking-wider">Khuyến nghị</p>
                <ul className="space-y-1.5">
                  {report.recommendations.map((rec, i) => (
                    <li key={i} className="flex gap-2 text-sm text-stone-300">
                      <span className="mt-0.5 flex-shrink-0 text-amber-400">▸</span>
                      <span>{rec}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <p className="text-right text-xs text-stone-600">
                {new Date(report.generated_at).toLocaleString('vi-VN')}
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
