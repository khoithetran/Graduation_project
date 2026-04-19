import { useState } from 'react';

import appText from './content/app-text.vi.json';
import { API_BASE } from './services/api';
import { ImageDetection } from './components/ImageDetection';
import { VideoTracking } from './components/VideoTracking';
import { LiveStream } from './components/LiveStream';

type Tab = 'image' | 'video' | 'live';

const TAB_LABELS: Record<Tab, string> = {
  image: appText.tabs.imageDetection,
  video: appText.tabs.videoTracking,
  live: appText.tabs.liveStream,
};

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('image');
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownloadPdf = async () => {
    setIsDownloading(true);
    try {
      const res = await fetch(`${API_BASE}/api/report/download?hours=4`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        alert(err.detail ?? 'Không thể tải PDF.');
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `bao_cao_${new Date().toISOString().slice(0, 16).replace(/[T:]/g, '_')}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert('Không thể kết nối backend.');
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="min-h-screen bg-app-pattern text-stone-100">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-4 py-6 lg:px-8">
        <main className="flex-1 rounded-[2rem] border border-white/10 bg-stone-950/70 p-5 shadow-[0_30px_80px_rgba(0,0,0,0.45)] backdrop-blur xl:p-7">
          {/* Header */}
          <div className="mb-6 border-b border-white/10 pb-5">
            <p className="mb-2 inline-flex rounded-full border border-amber-400/30 bg-amber-300/10 px-3 py-1 text-xs uppercase tracking-[0.28em] text-amber-200">
              {appText.header.badge}
            </p>
            <div className="flex items-start justify-between gap-4">
              <h1 className="text-3xl font-semibold tracking-tight text-white md:text-4xl">
                {appText.header.title}
              </h1>
              <button
                onClick={handleDownloadPdf}
                disabled={isDownloading}
                className="flex-shrink-0 rounded-xl border border-amber-400/30 bg-amber-400/10 px-4 py-2 text-sm font-semibold text-amber-200 transition hover:bg-amber-400/20 disabled:opacity-40"
              >
                {isDownloading ? '...' : appText.report.downloadPdf}
              </button>
            </div>
            <p className="mt-2 max-w-2xl text-sm text-stone-300">
              {appText.header.description.split('/predict')[0]}
              <span className="font-mono text-amber-200">/predict</span>.
            </p>
          </div>

          {/* Tab bar */}
          <div className="mb-6 flex gap-2 rounded-2xl border border-white/10 bg-white/5 p-1">
            {(['image', 'video', 'live'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 rounded-xl px-4 py-2 text-sm font-medium transition ${
                  activeTab === tab
                    ? 'bg-amber-300 text-stone-950'
                    : 'text-stone-400 hover:text-stone-200'
                }`}
              >
                {TAB_LABELS[tab]}
              </button>
            ))}
          </div>

          {/* Active tab */}
          {activeTab === 'image' && <ImageDetection />}
          {activeTab === 'video' && <VideoTracking />}
          {activeTab === 'live' && <LiveStream />}
        </main>
      </div>
    </div>
  );
}

export default App;
