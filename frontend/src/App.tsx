import { useState } from 'react';

import appText from './content/app-text.vi.json';
import { ImageDetection } from './components/ImageDetection';
import { VideoTracking } from './components/VideoTracking';
import { LiveStream } from './components/LiveStream';

// Demo image — imported as Vite static asset (bundled into dist/assets/)
import demo1 from '../../demo/image_demo_1.jpg';

type Tab = 'image' | 'video' | 'live';

// ── SVG icons ─────────────────────────────────────────────────────────────────

const IconPhoto = ({ cls = 'h-5 w-5' }: { cls?: string }) => (
  <svg className={cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="2.5" />
    <circle cx="8.5" cy="8.5" r="1.5" />
    <path d="m21 15-5-5L5 21" />
  </svg>
);

const IconVideo = ({ cls = 'h-5 w-5' }: { cls?: string }) => (
  <svg className={cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
    <polygon points="23 7 16 12 23 17 23 7" />
    <rect x="1" y="5" width="15" height="14" rx="2" />
  </svg>
);

const IconLive = ({ cls = 'h-5 w-5' }: { cls?: string }) => (
  <svg className={cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="2.5" />
    <path d="M6.34 6.34a8 8 0 0 0 0 11.32M17.66 6.34a8 8 0 0 1 0 11.32" />
    <path d="M3.51 3.51a13 13 0 0 0 0 16.98M20.49 3.51a13 13 0 0 1 0 16.98" />
  </svg>
);

// ── Static data ───────────────────────────────────────────────────────────────

const PIPELINE_STEPS = [
  { title: appText.pipeline.step1Title, desc: appText.pipeline.step1Desc },
  { title: appText.pipeline.step2Title, desc: appText.pipeline.step2Desc },
  { title: appText.pipeline.step3Title, desc: appText.pipeline.step3Desc },
  { title: appText.pipeline.step4Title, desc: appText.pipeline.step4Desc },
  { title: appText.pipeline.step5Title, desc: appText.pipeline.step5Desc },
];

// 6-step pipeline when Person-First is toggled on (adds person detection before helmet check)
const PIPELINE_STEPS_PERSON_FIRST = [
  { title: appText.pipeline.step1Title, desc: appText.pipeline.step1Desc },
  { title: appText.pipeline.step2Title, desc: appText.pipeline.step2Desc },
  { title: appText.pipeline.personFirstExtraStepTitle, desc: appText.pipeline.personFirstExtraStepDesc },
  { title: appText.pipeline.step3Title, desc: appText.pipeline.step3PersonFirstDesc },
  { title: appText.pipeline.step4Title, desc: appText.pipeline.step4Desc },
  { title: appText.pipeline.step5Title, desc: appText.pipeline.step5Desc },
];

// Person-first sub-steps shown in the optional pipeline callout
const PERSON_FIRST_STEPS = [
  appText.pipeline.personFirstStep1,
  appText.pipeline.personFirstStep2,
  appText.pipeline.personFirstStep3,
  appText.pipeline.personFirstStep4,
];

const HERO_STATS: [string, string][] = [
  [appText.hero.stat1Value, appText.hero.stat1Label],
  [appText.hero.stat2Value, appText.hero.stat2Label],
  [appText.hero.stat3Value, appText.hero.stat3Label],
  [appText.hero.stat4Value, appText.hero.stat4Label],
];

type ModeInfo = { icon: (active: boolean) => React.ReactNode; title: string; desc: string; tags: string[] };

const MODE_INFO: Record<Tab, ModeInfo> = {
  image: {
    icon: (active) => <IconPhoto cls={`h-6 w-6 ${active ? 'text-white' : 'text-primary-600'}`} />,
    title: appText.modes.imageTitle,
    desc: appText.modes.imageDesc,
    tags: appText.modes.imageDetail.split(' · '),
  },
  video: {
    icon: (active) => <IconVideo cls={`h-6 w-6 ${active ? 'text-white' : 'text-primary-600'}`} />,
    title: appText.modes.videoTitle,
    desc: appText.modes.videoDesc,
    tags: appText.modes.videoDetail.split(' · '),
  },
  live: {
    icon: (active) => <IconLive cls={`h-6 w-6 ${active ? 'text-white' : 'text-primary-600'}`} />,
    title: appText.modes.liveTitle,
    desc: appText.modes.liveDesc,
    tags: appText.modes.liveDetail.split(' · '),
  },
};

const TAB_LABELS: Record<Tab, string> = {
  image: appText.tabs.imageDetection,
  video: appText.tabs.videoTracking,
  live: appText.tabs.liveStream,
};

// ── App ───────────────────────────────────────────────────────────────────────

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('image');
  const [personFirst, setPersonFirst] = useState(false);

  const handleModeSelect = (tab: Tab) => {
    setActiveTab(tab);
    setTimeout(() => {
      document.getElementById('demo-panel')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 60);
  };

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-7xl px-4 pb-20 pt-8 lg:px-8">

        {/* ── Hero ─────────────────────────────────────────────────────────── */}
        <header className="mb-14 text-center">
          {/* Badge */}
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-primary-200 bg-white/75 px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-primary-700 shadow-sm backdrop-blur-sm">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary-400" />
            {appText.hero.badge}
          </div>

          {/* Title — single line */}
          <h1 className="mb-4 text-4xl font-bold leading-tight tracking-tight md:text-5xl lg:text-6xl">
            <span className="bg-gradient-to-r from-primary-600 via-cyan-600 to-primary-700 bg-clip-text text-transparent">
              {appText.hero.title}
            </span>
          </h1>

          {/* Subtitle */}
          <p className="mx-auto mb-10 max-w-2xl text-base leading-relaxed text-slate-500 md:text-lg">
            {appText.hero.subtitle}
          </p>

          {/* Stat cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {HERO_STATS.map(([value, label]) => (
              <div
                key={label}
                className="rounded-2xl border border-primary-100 bg-white/80 px-4 py-4 text-left shadow-sm backdrop-blur-sm"
              >
                <p className="mb-0.5 text-sm font-semibold leading-snug text-slate-800">{value}</p>
                <p className="text-xs text-slate-400">{label}</p>
              </div>
            ))}
          </div>
        </header>

        {/* ── Pipeline ─────────────────────────────────────────────────────── */}
        <section className="mb-10 rounded-3xl border border-primary-100/70 bg-white/65 px-6 py-8 shadow-sm backdrop-blur-sm lg:px-10">
          <div className="mb-8 text-center">
            <h2 className="text-xl font-bold text-slate-800 md:text-2xl">
              {appText.pipeline.sectionTitle}
            </h2>
            <p className="mt-1.5 text-xs leading-relaxed text-slate-400 md:text-sm">
              {appText.pipeline.sectionSubtitle}
            </p>
          </div>

          <div className="overflow-x-auto pb-2">
            <div className="relative flex min-w-max items-start justify-center md:min-w-0">
              {/* Connecting line */}
              <div
                className="absolute inset-x-12 top-5 h-px lg:top-6"
                style={{ background: 'linear-gradient(to right, #9fe7f5, #1799b8, #9fe7f5)' }}
              />

              {(personFirst ? PIPELINE_STEPS_PERSON_FIRST : PIPELINE_STEPS).map((step, i) => (
                <div key={i} className="relative flex w-40 flex-col items-center px-2 text-center md:flex-1">
                  <div className="relative z-10 flex h-10 w-10 items-center justify-center rounded-full bg-white text-sm font-bold text-primary-700 shadow-md ring-2 ring-primary-300 lg:h-12 lg:w-12 lg:text-base">
                    {i + 1}
                  </div>
                  <div className="mt-3 px-1">
                    <p className="text-sm font-semibold text-slate-700">{step.title}</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-slate-400">{step.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* ── Person-first callout ─────────────────────────────────────── */}
          <div className={`mt-6 rounded-2xl border p-4 transition-colors duration-200 lg:p-5 ${personFirst ? 'border-primary-300 bg-primary-50' : 'border-primary-200 bg-primary-50/70'}`}>
            {/* Header: badge + title + toggle */}
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <span className="mb-1.5 inline-block rounded-full border border-primary-300 bg-white px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-primary-700">
                  {appText.pipeline.personFirstBadge}
                </span>
                <p className="text-sm font-semibold text-slate-800">{appText.pipeline.personFirstTitle}</p>
                <p className="text-[11px] text-slate-400">{appText.pipeline.personFirstToggleHint}</p>
              </div>
              {/* Toggle switch */}
              <button
                onClick={() => setPersonFirst(v => !v)}
                role="switch"
                aria-checked={personFirst}
                aria-label={appText.pipeline.personFirstToggleLabel}
                className={`mt-1 flex-shrink-0 inline-flex h-6 w-11 cursor-pointer items-center rounded-full border-2 transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400 ${personFirst ? 'border-primary-500 bg-primary-500' : 'border-slate-300 bg-slate-200'}`}
              >
                <span
                  className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${personFirst ? 'translate-x-[22px]' : 'translate-x-[2px]'}`}
                />
              </button>
            </div>

            {/* Description */}
            <p className="mt-2.5 text-xs leading-relaxed text-slate-500">
              {appText.pipeline.personFirstDesc}
            </p>

            {/* Toggle-on extras */}
            {personFirst && (
              <div className="mt-3 space-y-2.5">
                <p className="inline-flex items-center gap-1.5 rounded-full bg-primary-100 px-3 py-1 text-[10px] font-medium text-primary-700">
                  <span aria-hidden="true">✦</span>
                  {appText.pipeline.personFirstToggleNote}
                </p>
                <div className="flex flex-wrap items-center gap-1.5">
                  {PERSON_FIRST_STEPS.map((step, i) => (
                    <span key={i} className="contents">
                      <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-medium text-primary-800 shadow-sm ring-1 ring-primary-200">
                        {step}
                      </span>
                      {i < PERSON_FIRST_STEPS.length - 1 && (
                        <span className="text-xs text-primary-400" aria-hidden="true">→</span>
                      )}
                    </span>
                  ))}
                </div>
                <p className="text-[10px] text-slate-400">{appText.pipeline.personFirstApplies}</p>
              </div>
            )}
          </div>
        </section>

        {/* ── Demo image showcase ───────────────────────────────────────────── */}
        <section className="mb-14">
          <div className="mb-5 text-center">
            <p className="text-xs font-semibold uppercase tracking-widest text-primary-600">
              {appText.showcase.eyebrow}
            </p>
            <h2 className="mt-1 text-xl font-bold text-slate-800 md:text-2xl">
              {appText.showcase.title}
            </h2>
          </div>

          <figure className="mx-auto max-w-3xl overflow-hidden rounded-2xl border border-primary-100 bg-white shadow-sm transition-shadow hover:shadow-md">
            <div className="overflow-hidden bg-slate-100">
              <img
                src={demo1}
                alt={appText.showcase.demo1Caption}
                className="w-full object-cover"
                loading="lazy"
              />
            </div>
            <figcaption className="px-5 py-4">
              <p className="text-sm font-semibold text-slate-700">{appText.showcase.demo1Caption}</p>
              <p className="mt-0.5 text-xs text-slate-400">{appText.showcase.demo1Detail}</p>
            </figcaption>
          </figure>
        </section>

        {/* ── Mode selector cards ───────────────────────────────────────────── */}
        <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {(['image', 'video', 'live'] as const).map((tab) => {
            const info = MODE_INFO[tab];
            const isActive = activeTab === tab;
            return (
              <button
                key={tab}
                onClick={() => handleModeSelect(tab)}
                className={[
                  'rounded-2xl border p-5 text-left transition-all duration-200',
                  isActive
                    ? 'border-primary-400 bg-primary-500 shadow-lg shadow-primary-200/70 ring-1 ring-primary-400'
                    : 'border-primary-100 bg-white/70 hover:border-primary-300 hover:bg-white/90 hover:shadow-md',
                ].join(' ')}
              >
                {/* Icon */}
                <div className={[
                  'mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl',
                  isActive ? 'bg-white/20' : 'bg-primary-50',
                ].join(' ')}>
                  {info.icon(isActive)}
                </div>

                {/* Title */}
                <h3 className={[
                  'mb-1.5 text-base font-bold',
                  isActive ? 'text-white' : 'text-slate-800',
                ].join(' ')}>
                  {info.title}
                </h3>

                {/* Description */}
                <p className={[
                  'mb-3 text-xs leading-relaxed',
                  isActive ? 'text-primary-50' : 'text-slate-500',
                ].join(' ')}>
                  {info.desc}
                </p>

                {/* Tags */}
                <div className="flex flex-wrap gap-1.5">
                  {info.tags.map((tag) => (
                    <span
                      key={tag}
                      className={[
                        'rounded-full px-2 py-0.5 text-[10px] font-medium',
                        isActive ? 'bg-white/20 text-white' : 'bg-primary-50 text-primary-700',
                      ].join(' ')}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </button>
            );
          })}
        </div>

        {/* ── Demo panel (dark workbench) ───────────────────────────────────── */}
        <div
          id="demo-panel"
          className="overflow-hidden rounded-3xl border border-white/10 bg-stone-950/90 shadow-2xl backdrop-blur-sm"
        >
          {/* Tab bar */}
          <div className="flex gap-1 border-b border-white/[0.08] p-2">
            {(['image', 'video', 'live'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={[
                  'flex flex-1 items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-150',
                  activeTab === tab
                    ? 'bg-primary-300 text-stone-900 shadow-sm'
                    : 'text-stone-400 hover:bg-white/5 hover:text-stone-200',
                ].join(' ')}
              >
                <span className="hidden sm:block">
                  {tab === 'image' && <IconPhoto cls="h-4 w-4" />}
                  {tab === 'video' && <IconVideo cls="h-4 w-4" />}
                  {tab === 'live'  && <IconLive  cls="h-4 w-4" />}
                </span>
                <span>{TAB_LABELS[tab]}</span>
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="p-5 xl:p-7">
            {activeTab === 'image' && <ImageDetection personFirst={personFirst} />}
            {activeTab === 'video' && <VideoTracking personFirst={personFirst} />}
            {activeTab === 'live'  && <LiveStream personFirst={personFirst} />}
          </div>
        </div>

      </div>
    </div>
  );
}

export default App;
