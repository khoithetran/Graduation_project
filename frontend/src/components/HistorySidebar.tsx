import appText from '../content/app-text.vi.json';
import { toApiAssetUrl } from '../services/api';

type HistoryEvent = {
  id: string;
  timestamp: string;
  source: string;
  type: 'VI_PHAM' | 'NGHI_NGO' | string;
  global_image_url: string;
  crop_image_urls: string[];
  num_violators: number;
};

const formatTimestamp = (value: string) =>
  new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));

interface HistorySidebarProps {
  history: HistoryEvent[];
  historyLoading: boolean;
}

export function HistorySidebar({ history, historyLoading }: HistorySidebarProps) {
  return (
    <aside className="rounded-[2rem] border border-white/10 bg-[#120f0d]/90 p-5 shadow-[0_30px_80px_rgba(0,0,0,0.45)] lg:w-80 xl:w-96">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.26em] text-stone-400">{appText.history.eyebrow}</p>
          <h2 className="mt-2 text-xl font-semibold text-white">{appText.history.title}</h2>
        </div>
        <span className="rounded-full bg-red-400/10 px-3 py-1 text-xs text-red-200">
          {history.length} {appText.history.itemsSuffix}
        </span>
      </div>

      <div className="space-y-4">
        {historyLoading ? (
          <div className="rounded-[1.25rem] border border-white/10 bg-white/5 px-4 py-6 text-sm text-stone-400">
            {appText.history.loading}
          </div>
        ) : history.length === 0 ? (
          <div className="rounded-[1.25rem] border border-white/10 bg-white/5 px-4 py-6 text-sm text-stone-400">
            {appText.history.empty}
          </div>
        ) : (
          history.map((item) => (
            <article
              key={item.id}
              className="overflow-hidden rounded-[1.35rem] border border-white/10 bg-white/[0.04]"
            >
              <div className="aspect-[16/10] bg-stone-950">
                {item.global_image_url ? (
                  <img
                    src={toApiAssetUrl(item.global_image_url)}
                    alt={item.source}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-stone-500">
                    {appText.history.noPreview}
                  </div>
                )}
              </div>

              <div className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">{item.source}</p>
                    <p className="mt-1 text-xs text-stone-400">{formatTimestamp(item.timestamp)}</p>
                  </div>
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      item.type === 'VI_PHAM'
                        ? 'bg-red-400/10 text-red-200'
                        : 'bg-amber-300/10 text-amber-200'
                    }`}
                  >
                    {item.type}
                  </span>
                </div>

                <div className="flex items-center justify-between text-sm text-stone-300">
                  <span>{item.num_violators} {appText.history.objectsSuffix}</span>
                  <span>{item.crop_image_urls.length} {appText.history.cropsSuffix}</span>
                </div>
              </div>
            </article>
          ))
        )}
      </div>
    </aside>
  );
}
