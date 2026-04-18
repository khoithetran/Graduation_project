export function formatTime(sec: number): string {
  const m = Math.floor(sec / 60).toString().padStart(2, '0');
  const s = (sec % 60).toFixed(1).padStart(4, '0');
  return `${m}:${s}`;
}
