import { useState, useEffect } from 'react';
import api from '../api/client';
import Loader from './Loader';

function formatDateTime(dateString) {
  if (!dateString) return null;
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return String(dateString);
    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return String(dateString);
  }
}

export default function AdminComplaintCard({ complaint }) {
  const [imageSrc, setImageSrc] = useState(null);
  const [imageLoading, setImageLoading] = useState(true);
  const [imageFailed, setImageFailed] = useState(false);

  useEffect(() => {
    let active = true;
    let objectUrl = null;

    async function loadImage() {
      if (complaint?.image_path && (complaint.image_path.startsWith('http://') || complaint.image_path.startsWith('https://'))) {
        setImageSrc(complaint.image_path);
        setImageLoading(false);
        return;
      }
      try {
        setImageLoading(true);
        setImageFailed(false);
        const res = await api.get(`/admin/complaints/${complaint.id}/image`, {
          responseType: 'blob',
        });
        if (!active) return;
        objectUrl = URL.createObjectURL(res.data);
        setImageSrc(objectUrl);
      } catch (err) {
        if (active) {
          console.error('Failed to load complaint image:', err);
          setImageFailed(true);
        }
      } finally {
        if (active) setImageLoading(false);
      }
    }

    loadImage();

    return () => {
      active = false;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [complaint.id, complaint?.image_path]);

  const statusColor =
    complaint.status === 'accepted'
      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
      : complaint.status === 'rejected'
      ? 'bg-red-500/20 text-red-300 border-red-500/30'
      : 'bg-amber-500/20 text-amber-300 border-amber-500/30';

  const locationStr = [complaint.constituency, complaint.district, complaint.state]
    .filter(Boolean)
    .join(', ');

  const xpDisplay =
    complaint.status === 'accepted'
      ? complaint.xp_awarded
        ? `+${complaint.xp_awarded} XP`
        : '+50 XP'
      : null;

  return (
    <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl overflow-hidden shadow-lg flex flex-col justify-between transition-all hover:border-slate-600">
      {/* Photo Viewport */}
      <div className="w-full h-56 bg-slate-900 flex items-center justify-center relative overflow-hidden">
        {imageLoading ? (
          <div className="flex flex-col items-center justify-center space-y-2 text-slate-400">
            <Loader size="md" />
            <span className="text-xs">Loading complaint photo...</span>
          </div>
        ) : imageFailed || !imageSrc ? (
          <div className="flex flex-col items-center justify-center text-slate-500 p-4 text-center">
            <svg className="w-8 h-8 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
            <span className="text-xs">Image unavailable</span>
          </div>
        ) : (
          <img
            src={imageSrc}
            alt="Citizen complaint verification photo"
            className="w-full h-full object-cover"
          />
        )}

        {/* Top Badges */}
        <div className="absolute top-3 right-3 flex items-center space-x-2">
          {xpDisplay && (
            <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-500/90 text-slate-900 shadow-md">
              {xpDisplay}
            </span>
          )}
          <span
            className={`px-2.5 py-1 rounded-lg text-xs font-bold uppercase tracking-wider border backdrop-blur-md shadow-md ${statusColor}`}
          >
            {complaint.status}
          </span>
        </div>
      </div>

      {/* Details Container */}
      <div className="p-5 space-y-3 flex-1 flex flex-col justify-between">
        <div className="space-y-2">
          <div>
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Citizen Comment
            </span>
            <p className="text-sm font-medium text-white line-clamp-3">
              "{complaint.comment}"
            </p>
          </div>

          <div className="space-y-1 text-xs text-slate-400 pt-1">
            {locationStr && (
              <p className="flex items-center space-x-1.5">
                <svg className="w-3.5 h-3.5 text-slate-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                <span className="truncate">{locationStr}</span>
              </p>
            )}

            <p className="flex items-center space-x-1.5">
              <svg className="w-3.5 h-3.5 text-slate-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
              </svg>
              <span className="break-all text-slate-300 font-mono text-[11px]">{complaint.user_email}</span>
            </p>
          </div>

          {/* Auditor Comment Box if any */}
          {complaint.auditor_comment && (
            <div className="p-2.5 rounded-xl bg-blue-950/70 border border-blue-800 text-xs text-blue-200">
              <span className="font-semibold text-blue-300">Auditor comment:</span>{' '}
              {complaint.auditor_comment}
            </div>
          )}
        </div>

        {/* Submitted and Reviewed Dates */}
        <div className="pt-3 border-t border-slate-700/60 flex flex-wrap items-center justify-between gap-1 text-[11px] text-slate-400">
          <span>Filed: {formatDateTime(complaint.created_at)}</span>
          {complaint.reviewed_at && (
            <span>Reviewed: {formatDateTime(complaint.reviewed_at)}</span>
          )}
        </div>
      </div>
    </div>
  );
}
