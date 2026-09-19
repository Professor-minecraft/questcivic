import { useState } from 'react';
import { Link } from 'react-router-dom';
import PhotoViewer from './PhotoViewer';
import { getImageUrl } from '../utils/imageUrl';

function formatINR(val) {
  if (val === null || val === undefined || isNaN(val)) return 'Not specified';
  const num = Number(val);
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(num);
}

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

export default function SubmissionCard({ item }) {
  const [viewerOpen, setViewerOpen] = useState(false);
  if (!item) return null;

  const isApproved = item.status === 'approved';
  const isRejected = item.status === 'rejected';
  const imageUrl = getImageUrl(item.image_path);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 shadow-xs hover:shadow-md transition-shadow relative">
      {/* Top Header: Source, Location & Status / XP Badge */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-3">
        <div className="flex flex-wrap items-center gap-2">
          {item.source && (
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-semibold uppercase tracking-wider ${
                item.source === 'LS'
                  ? 'bg-blue-50 text-blue-700 border border-blue-200'
                  : 'bg-purple-50 text-purple-700 border border-purple-200'
              }`}
            >
              {item.source === 'LS' ? 'Lok Sabha' : 'Rajya Sabha'}
            </span>
          )}

          <span className="text-xs font-medium text-slate-500">
            {item.district}
            {item.constituency ? ` • ${item.constituency}` : ''}
          </span>
        </div>

        {/* Status Badge & XP pill */}
        <div className="flex items-center space-x-2 shrink-0 self-start">
          {isApproved && (
            <>
              <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5"></span>
                Approved
              </span>
              <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-800 border border-amber-300">
                ★ +{item.xp_earned || 150} XP
              </span>
            </>
          )}
          {isRejected && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-red-50 text-red-800 border border-red-300">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 mr-1.5"></span>
              Rejected
            </span>
          )}
        </div>
      </div>

      {/* Work Type Title */}
      <h3 className="text-base sm:text-lg font-bold text-slate-900 line-clamp-2 leading-snug mb-2">
        {item.work_type || item.description || 'Public Development Work'}
      </h3>

      {/* Work Description */}
      <p className="text-sm text-slate-600 mb-4 line-clamp-3 leading-relaxed">
        {item.description || 'No detailed description recorded.'}
      </p>

      {/* Uploaded Verification Photo */}
      {imageUrl && (
        <div className="mb-4">
          <button
            type="button"
            onClick={() => setViewerOpen(true)}
            className="group relative inline-flex items-center justify-center h-28 w-44 rounded-xl overflow-hidden border border-slate-200 bg-slate-100 hover:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all cursor-pointer"
            aria-label="View uploaded photo"
          >
            <img
              src={imageUrl}
              alt="Verification submission photo"
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
            />
            <div className="absolute inset-0 bg-slate-900/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white text-xs font-semibold gap-1">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
              <span>View photo</span>
            </div>
          </button>
          {viewerOpen && (
            <PhotoViewer
              src={imageUrl}
              filename={`submission-${item.submission_id}`}
              title={`Verification Photo #${item.submission_id}`}
              alt={`Verification Photo #${item.submission_id}`}
              onClose={() => setViewerOpen(false)}
            />
          )}
        </div>
      )}

      {/* Metadata Grid */}
      <div className="pt-3 border-t border-slate-100 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs text-slate-600">
        <div>
          <span className="block text-slate-600 uppercase font-semibold tracking-wider text-[10px]">
            Hon'ble MP
          </span>
          <span className="font-semibold text-slate-800 truncate block mt-0.5" title={item.mp_name}>
            {item.mp_name || 'Not specified'}
          </span>
        </div>

        <div>
          <span className="block text-slate-600 uppercase font-semibold tracking-wider text-[10px]">
            Amount Disbursed
          </span>
          <span className="font-bold text-slate-900 mt-0.5 block text-sm">
            {formatINR(item.amount)}
          </span>
        </div>

        <div>
          <span className="block text-slate-600 uppercase font-semibold tracking-wider text-[10px]">
            Completion Date
          </span>
          <span className="font-medium text-slate-700 mt-0.5 block">
            {formatDate(item.completion_date)}
          </span>
        </div>

        <div>
          <span className="block text-slate-600 uppercase font-semibold tracking-wider text-[10px]">
            Review Date
          </span>
          <span className="font-medium text-slate-700 mt-0.5 block">
            {formatDate(item.reviewed_at)}
          </span>
        </div>
      </div>

      {/* Rejection Details & Retake Link */}
      {isRejected && (
        <div className="mt-4 p-3.5 rounded-xl bg-red-50 border border-red-200 text-sm">
          <div className="font-semibold text-red-900 mb-1 flex items-center text-xs uppercase tracking-wider">
            <svg
              className="w-4 h-4 mr-1.5 text-red-500 shrink-0"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
            Auditor Reason
          </div>
          <p className="text-red-800 text-sm leading-relaxed mb-2.5">
            {item.reject_reason || 'No specific reason provided.'}
          </p>
          <div>
            <Link
              to="/works"
              className="inline-flex items-center min-h-[36px] px-3 py-1.5 text-xs font-semibold text-red-800 bg-red-100 hover:bg-red-200 rounded-lg transition-colors cursor-pointer"
            >
              Retake on works page
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
