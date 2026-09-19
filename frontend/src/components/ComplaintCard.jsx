import { useState, useEffect } from 'react';
import api from '../api/client';
import Loader from './Loader';

function formatDate(val) {
  if (!val) return 'Not recorded';
  try {
    const d = new Date(val);
    if (isNaN(d.getTime())) return String(val);
    return d.toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return String(val);
  }
}

export default function ComplaintCard({ item }) {
  const [imageUrl, setImageUrl] = useState(null);
  const [loadingImage, setLoadingImage] = useState(true);
  const [imageError, setImageError] = useState(false);

  useEffect(() => {
    let isMounted = true;
    let objectUrl = null;

    async function fetchImage() {
      if (!item?.id) return;
      try {
        setLoadingImage(true);
        setImageError(false);
        const res = await api.get(`/complaints/${item.id}/image`, {
          responseType: 'blob',
        });
        if (isMounted) {
          objectUrl = URL.createObjectURL(res.data);
          setImageUrl(objectUrl);
        }
      } catch (err) {
        if (isMounted) {
          setImageError(true);
        }
      } finally {
        if (isMounted) {
          setLoadingImage(false);
        }
      }
    }

    fetchImage();

    // Free the blob URL when the card unmounts
    return () => {
      isMounted = false;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [item?.id]);

  if (!item) return null;

  const status = (item.status || 'pending').toLowerCase();
  const isPending = status === 'pending';
  const isAccepted = status === 'accepted';
  const isRejected = status === 'rejected';

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-4 sm:p-5 shadow-xs hover:shadow-md transition-shadow">
      <div className="flex flex-col sm:flex-row gap-4 items-start">
        {/* Photo Thumbnail */}
        <div className="w-full sm:w-28 sm:h-28 h-44 shrink-0 rounded-xl overflow-hidden bg-slate-100 border border-slate-200 relative flex items-center justify-center">
          {loadingImage ? (
            <div className="flex flex-col items-center justify-center p-2 text-slate-400">
              <Loader size="sm" />
              <span className="text-[10px] mt-1 font-medium text-slate-500">Loading photo...</span>
            </div>
          ) : imageError || !imageUrl ? (
            <div className="flex flex-col items-center justify-center p-2 text-slate-400 text-center">
              <svg className="w-6 h-6 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span className="text-[10px] font-medium text-slate-500">No image</span>
            </div>
          ) : (
            <img
              src={imageUrl}
              alt="Complaint damage thumbnail"
              className="w-full h-full object-cover"
            />
          )}
        </div>

        {/* Content Body */}
        <div className="flex-1 min-w-0 w-full">
          {/* Header Row: Location and Status Badge */}
          <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
            <span className="text-xs font-semibold text-slate-600 truncate">
              {item.district}
              {item.constituency ? ` • ${item.constituency}` : ''}
              {item.state ? `, ${item.state}` : ''}
            </span>

            <div className="flex items-center space-x-2 shrink-0">
              {isPending && (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-300">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mr-1.5"></span>
                  Pending
                </span>
              )}
              {isAccepted && (
                <>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5"></span>
                    Accepted
                  </span>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-800 border border-amber-300">
                    ★ +{item.xp_awarded || 50} XP
                  </span>
                </>
              )}
              {isRejected && (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-50 text-red-800 border border-red-300">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500 mr-1.5"></span>
                  Rejected
                </span>
              )}
            </div>
          </div>

          {/* User's Comment */}
          <p className="text-sm font-medium text-slate-900 leading-relaxed break-words">
            {item.comment}
          </p>

          {/* Submission Date */}
          <div className="mt-2 text-xs text-slate-600 flex items-center gap-1.5">
            <svg className="w-3.5 h-3.5 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span>Submitted on {formatDate(item.created_at)}</span>
          </div>

          {/* Auditor's Comment (When reviewed) in a light box */}
          {item.auditor_comment && (
            <div className="mt-3 p-3 rounded-xl bg-slate-50 border border-slate-200/80 text-xs sm:text-sm">
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="font-semibold text-slate-700 uppercase tracking-wider text-[11px] flex items-center gap-1">
                  <svg className="w-3.5 h-3.5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  Auditor comment
                </span>
                {item.reviewed_at && (
                  <span className="text-[11px] text-slate-600 font-medium">
                    Reviewed on {formatDate(item.reviewed_at)}
                  </span>
                )}
              </div>
              <p className="text-slate-700 italic pl-1 leading-relaxed">
                "{item.auditor_comment}"
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
