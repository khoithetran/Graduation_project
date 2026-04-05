import { useState } from 'react';

import appText from './content/app-text.vi.json';
import { ImageDetection } from './components/ImageDetection';
import { VideoTracking } from './components/VideoTracking';

type Tab = 'image' | 'video';

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('image');

  return (
    <div className="min-h-screen bg-app-pattern text-stone-100">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-4 py-6 lg:px-8">
        {/* Main content */}
        <main className="flex-1 rounded-[2rem] border border-white/10 bg-stone-950/70 p-5 shadow-[0_30px_80px_rgba(0,0,0,0.45)] backdrop-blur xl:p-7">
          {/* Header */}
          <div className="mb-6 border-b border-white/10 pb-5">
            <p className="mb-2 inline-flex rounded-full border border-amber-400/30 bg-amber-300/10 px-3 py-1 text-xs uppercase tracking-[0.28em] text-amber-200">
              {appText.header.badge}
            </p>
            <h1 className="text-3xl font-semibold tracking-tight text-white md:text-4xl">
              {appText.header.title}
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-stone-300">
              {appText.header.description.split('/predict')[0]}
              <span className="font-mono text-amber-200">/predict</span>.
            </p>
          </div>

          {/* Tab bar */}
          <div className="mb-6 flex gap-2 rounded-2xl border border-white/10 bg-white/5 p-1">
            {(['image', 'video'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 rounded-xl px-4 py-2 text-sm font-medium transition ${
                  activeTab === tab
                    ? 'bg-amber-300 text-stone-950'
                    : 'text-stone-400 hover:text-stone-200'
                }`}
              >
                {tab === 'image' ? appText.tabs.imageDetection : appText.tabs.videoTracking}
              </button>
            ))}
          </div>

          {/* Active tab content */}
          {activeTab === 'image' ? <ImageDetection /> : <VideoTracking />}
        </main>
      </div>
    </div>
  );
}

export default App;
