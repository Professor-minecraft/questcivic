import { useState, useEffect, useRef } from 'react';
import api from '../api/client';
import Loader from './Loader';
import PhotoViewer from './PhotoViewer';

function formatDateTime(val) {
  if (!val) return 'Unknown';
  try {
    const d = new Date(val);
    if (isNaN(d.getTime())) return String(val);
    return d.toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return String(val);
  }
}

export default function AuditorComplaintCard({ item, activeTab, onActionSuccess }) {
  const [photoSrc, setPhotoSrc] = useState(null);
  const [loadingPhoto, setLoadingPhoto] = useState(true);
  const [photoFailed, setPhotoFailed] = useState(false);
  const [isViewerOpen, setIsViewerOpen] = useState(false);

  // Pending action state
  const [comment, setComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isSubmittingRef = useRef(false);
  const [actionError, setActionError] = useState('');

  // Authenticated Photo Loading
  useEffect(() => {
    let isMounted = true;
    let objectUrl = null;

    async function loadPhoto() {
      if (item?.image_path && (item.image_path.startsWith('http://') || item.image_path.startsWith('https://'))) {
        setPhotoSrc(item.image_path);
        setLoadingPhoto(false);
        return;
      }
      try {
        setLoadingPhoto(true);
        setPhotoFailed(false);
        const res = await api.get(`/complaints/${item.id}/image`, {
          responseType: 'blob',
        });
        if (!isMounted) return;
        objectUrl = URL.createObjectURL(res.data);
        setPhotoSrc(objectUrl);
      } catch (err) {
        console.error('Failed to load complaint image:', err);
        if (isMounted) setPhotoFailed(true);
      } finally {
        if (isMounted) setLoadingPhoto(false);
      }
    }

    if (item?.id) {
      loadPhoto();
    }

    return () => {
      isMounted = false;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [item?.id, item?.image_path]);

  if (!item) return null;

  const isPending = activeTab === 'pending';
  const cleanComment = comment.trim();
  const isCommentValid = cleanComment.length >= 3 && cleanComment.length <= 500;

  // Handle Accept
  const handleAccept = async () => {
    if (isSubmittingRef.current || !isCommentValid) return;
    isSubmittingRef.current = true;
    setIsSubmitting(true);
    setActionError('');

    try {
      await api.post(`/auditor/complaints/${item.id}/accept`, {
        comment: cleanComment,
      });
      onActionSuccess(item.id, 'accept');
    } catch (err) {
      console.error('Accept failed:', err);
      const msg = err.response?.data?.detail || 'Failed to accept complaint.';
      setActionError(msg);
      isSubmittingRef.current = false;
      setIsSubmitting(false);
    }
  };

  // Handle Reject
  const handleReject = async () => {
    if (isSubmittingRef.current || !isCommentValid) return;
    isSubmittingRef.current = true;
    setIsSubmitting(true);
    setActionError('');

    try {
      await api.post(`/auditor/complaints/${item.id}/reject`, {
        comment: cleanComment,
      });
      onActionSuccess(item.id, 'reject');
    } catch (err) {
      console.error('Reject failed:', err);
      const msg = err.response?.data?.detail || 'Failed to reject complaint.';
      setActionError(msg);
      isSubmittingRef.current = false;
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-slate-800 rounded-2xl border border-slate-700/80 p-5 sm:p-6 shadow-md hover:border-slate-600 transition-colors flex flex-col justify-between">
      <div>
        {/* Photo Container */}
        <div className="w-full h-56 bg-slate-900 rounded-xl overflow-hidden border border-slate-700 mb-4 relative flex items-center justify-center">
          {loadingPhoto ? (
            <div className="flex flex-col items-center justify-center text-slate-400">
              <Loader size="md" />
              <span className="text-xs font-medium mt-2">Loading damage photo...</span>
            </div>
          ) : photoFailed || !photoSrc ? (
            <div className="flex flex-col items-center justify-center text-slate-400 p-4 text-center">
              <svg className="w-8 h-8 text-slate-500 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span className="text-xs text-slate-400 font-medium">Image preview unavailable</span>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setIsViewerOpen(true)}
              className="relative block w-full h-full cursor-zoom-in group focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 focus:ring-offset-slate-900"
              aria-label="View photo fullscreen"
            >
              <img
                src={photoSrc}
                alt="Complaint damage"
                className="w-full h-full object-cover"
              />
              <div
                className="absolute bottom-2 right-2 p-1.5 rounded-lg bg-black/60 text-white/90 shadow pointer-events-none group-hover:bg-black/80 transition-colors"
                aria-hidden="true"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 8V4m0 0h4M4 4l5 5m11-5h-4m4 0v4m0-4l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                </svg>
              </div>
            </button>
          )}

          {/* Status Badge Over Image */}
          <div className="absolute top-3 right-3 z-10 pointer-events-none">
            {item.status === 'accepted' && (
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-950/90 text-emerald-300 border border-emerald-700/80 shadow-md">
                Accepted • +50 XP
              </span>
            )}
            {item.status === 'rejected' && (
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-red-950/90 text-red-300 border border-red-700/80 shadow-md">
                Rejected
              </span>
            )}
            {item.status === 'pending' && (
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-950/90 text-amber-300 border border-amber-700/80 shadow-md">
                Pending Review
              </span>
            )}
          </div>
        </div>

        {/* User Info & Location Header */}
        <div className="space-y-1 mb-3">
          <div className="flex flex-wrap items-center justify-between gap-1 text-xs">
            <span className="text-blue-400 font-medium flex items-center gap-1 truncate" title={item.user_email}>
              <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
              {item.user_email}
            </span>
            <span className="text-slate-400">
              {formatDateTime(item.created_at)}
            </span>
          </div>

          <div className="text-xs text-slate-300 font-semibold flex items-center gap-1.5">
            <svg className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span>
              {item.district}
              {item.constituency ? `, ${item.constituency}` : ''}
              {item.state ? `, ${item.state}` : ''}
            </span>
          </div>
        </div>

        {/* User's Description / Comment */}
        <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-700/60 mb-4">
          <span className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
            Citizen Description
          </span>
          <p className="text-sm text-slate-200 leading-relaxed break-words">
            {item.comment}
          </p>
        </div>

        {/* Read-only Auditor Comment in Accepted / Rejected Tabs */}
        {!isPending && item.auditor_comment && (
          <div className="p-3.5 bg-slate-900/80 rounded-xl border border-slate-700 mb-4">
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-blue-400 flex items-center gap-1">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Auditor comment
              </span>
              {item.reviewed_at && (
                <span className="text-[11px] text-slate-400">
                  Reviewed {formatDateTime(item.reviewed_at)}
                </span>
              )}
            </div>
            <p className="text-sm text-slate-300 italic pl-1 leading-relaxed">
              "{item.auditor_comment}"
            </p>
          </div>
        )}
      </div>

      {/* Action Area in Pending Tab */}
      {isPending && (
        <div className="pt-3 border-t border-slate-700/80">
          {actionError && (
            <div className="mb-3 p-2.5 bg-red-950/80 border border-red-800 text-xs text-red-200 rounded-lg flex items-start space-x-1.5">
              <svg className="w-4 h-4 text-red-400 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <span>{actionError}</span>
            </div>
          )}

          <div className="mb-3">
            <label
              htmlFor={`comment-${item.id}`}
              className="block text-xs font-semibold text-slate-300 mb-1"
            >
              Your comment <span className="text-red-400">*</span>
            </label>
            <textarea
              id={`comment-${item.id}`}
              rows={3}
              maxLength={500}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              disabled={isSubmitting}
              placeholder="Your comment"
              className="w-full px-3 py-2 text-xs sm:text-sm bg-slate-900 border border-slate-700 rounded-xl text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none disabled:opacity-60"
            />
            <div className="flex justify-between items-center text-[11px] text-slate-400 mt-1">
              <span>Required (3 to 500 chars)</span>
              <span className={isCommentValid ? 'text-blue-400 font-semibold' : 'text-slate-400'}>
                {comment.length}/500
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            <button
              type="button"
              onClick={handleAccept}
              disabled={!isCommentValid || isSubmitting}
              className="min-h-[44px] px-3 py-2 rounded-xl text-xs sm:text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-1 shadow-sm"
            >
              {isSubmitting ? (
                <Loader size="sm" />
              ) : (
                <span>Accept (+50 XP)</span>
              )}
            </button>

            <button
              type="button"
              onClick={handleReject}
              disabled={!isCommentValid || isSubmitting}
              className="min-h-[44px] px-3 py-2 rounded-xl text-xs sm:text-sm font-semibold bg-red-600 hover:bg-red-500 active:bg-red-700 text-white transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-1 shadow-sm"
            >
              {isSubmitting ? (
                <Loader size="sm" />
              ) : (
                <span>Reject</span>
              )}
            </button>
          </div>
        </div>
      )}

      {isViewerOpen && (
        <PhotoViewer
          src={photoSrc}
          filename={`civicquest-complaint-${item.id}`}
          title={`Complaint photo #${item.id}`}
          alt="Complaint damage"
          onClose={() => setIsViewerOpen(false)}
        />
      )}
    </div>
  );
}
