import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

/**
 * Downloads a photo blob URL with an appropriate extension determined by its MIME type.
 * Extension mapping per D4:
 * - image/jpeg -> jpg
 * - image/png -> png
 * - image/webp -> webp
 * - anything else -> jpg
 * Does NOT revoke the provided src blob URL.
 */
export async function downloadPhoto(src, filename) {
  const res = await fetch(src);
  if (!res.ok) {
    throw new Error(`Failed to fetch blob: ${res.statusText}`);
  }
  const blob = await res.blob();
  let ext = 'jpg';
  if (blob.type === 'image/png') {
    ext = 'png';
  } else if (blob.type === 'image/webp') {
    ext = 'webp';
  } else if (blob.type === 'image/jpeg') {
    ext = 'jpg';
  } else {
    ext = 'jpg';
  }

  const a = document.createElement('a');
  a.href = src;
  a.download = `${filename}.${ext}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export default function PhotoViewer({ src, filename, title, alt, onClose }) {
  const [errorMessage, setErrorMessage] = useState(null);
  const closeButtonRef = useRef(null);

  useEffect(() => {
    const previousActiveElement = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    if (closeButtonRef.current) {
      closeButtonRef.current.focus();
    }

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
      if (previousActiveElement && typeof previousActiveElement.focus === 'function') {
        previousActiveElement.focus();
      }
    };
  }, [onClose]);

  const handleDownload = async (e) => {
    e.stopPropagation();
    try {
      setErrorMessage(null);
      await downloadPhoto(src, filename);
    } catch (err) {
      console.error('Download error:', err);
      setErrorMessage('Download failed. Try again.');
    }
  };

  if (!src) return null;

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title || 'Photo viewer'}
      className="fixed inset-0 z-[60] bg-black/95 overscroll-contain h-dvh flex flex-col justify-between select-none"
      style={{
        paddingTop: 'env(safe-area-inset-top, 0px)',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        paddingLeft: 'env(safe-area-inset-left, 0px)',
        paddingRight: 'env(safe-area-inset-right, 0px)',
      }}
      onClick={onClose}
    >
      {/* Top bar */}
      <header
        className="w-full flex items-center justify-between px-3 py-2 bg-slate-900/90 backdrop-blur-md border-b border-slate-800 text-white shrink-0 min-h-[52px]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center min-w-0 pr-2">
          {errorMessage ? (
            <span className="text-xs sm:text-sm text-rose-400 font-medium truncate">
              {errorMessage}
            </span>
          ) : (
            <h2 className="text-sm sm:text-base font-medium text-slate-200 truncate">
              {title}
            </h2>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={handleDownload}
            className="inline-flex items-center justify-center gap-1.5 min-w-[44px] min-h-[44px] px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-100 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 focus:ring-offset-slate-900 active:scale-95 transition-all cursor-pointer"
            aria-label="Download photo"
          >
            <svg
              className="w-4 h-4 shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
            <span>Download</span>
          </button>

          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] w-11 h-11 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-100 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 focus:ring-offset-slate-900 active:scale-95 transition-all cursor-pointer"
            aria-label="Close photo viewer"
          >
            <svg
              className="w-5 h-5 shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </header>

      {/* Photo container */}
      <main
        className="flex-1 w-full flex items-center justify-center p-2 sm:p-4 min-h-0 overflow-hidden"
        onClick={onClose}
      >
        <img
          src={src}
          alt={alt || title || 'Photo'}
          className="max-w-full max-h-full object-contain pointer-events-auto"
          onClick={(e) => e.stopPropagation()}
        />
      </main>
    </div>,
    document.body
  );
}
