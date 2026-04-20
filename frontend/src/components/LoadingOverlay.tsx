interface LoadingOverlayProps {
  label?: string;
}

export function LoadingOverlay({ label }: LoadingOverlayProps) {
  return (
    <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-4 rounded-[1.75rem] bg-stone-950/70 backdrop-blur-sm">
      {label && (
        <p className="text-sm text-stone-300">{label}</p>
      )}
      <div className="relative h-1 w-48 overflow-hidden rounded-full bg-stone-700/60">
        <div className="loading-bar absolute inset-y-0 w-1/3 rounded-full bg-amber-400" />
      </div>
    </div>
  );
}
