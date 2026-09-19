import { API_BASE_URL } from '../api/client';

/**
 * Normalizes an image path or URL into an accessible URL for <img src> and fetch.
 * Handles:
 * - Full URLs (e.g. "https://...", "http://...", "blob:...", "data:...") -> returned unchanged.
 * - Local relative paths (e.g. "uploads/...", "/uploads/...") -> prepended with API_BASE_URL.
 * - null/undefined -> null
 */
export function getImageUrl(pathOrUrl) {
  if (!pathOrUrl) return null;
  const str = String(pathOrUrl).trim();
  if (
    str.startsWith('http://') ||
    str.startsWith('https://') ||
    str.startsWith('blob:') ||
    str.startsWith('data:')
  ) {
    return str;
  }
  const cleanBase = API_BASE_URL.replace(/\/+$/, '');
  const cleanPath = str.startsWith('/') ? str.slice(1) : str;
  return `${cleanBase}/${cleanPath}`;
}
