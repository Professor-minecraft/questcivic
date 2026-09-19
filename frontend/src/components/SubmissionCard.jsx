import { Link } from 'react-router-dom';

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
  if (!item) return null;

  const isApproved = item.status === 'approved';
  const isRejected = item.status === 'rejected';

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
