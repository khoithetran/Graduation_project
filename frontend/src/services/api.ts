export const API_BASE = import.meta.env.VITE_API_BASE || window.location.origin;

export const toApiAssetUrl = (path: string) => {
  if (!path) {
    return '';
  }

  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }

  return `${API_BASE}${path}`;
};
