export function formatINR(val) {
  if (val === null || val === undefined || isNaN(val)) return 'Not specified';
  const num = Number(val);
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(num);
}

export function formatDate(val) {
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

export default function WorkCard({ work, actionSlot = null }) {
  if (!work) return null;

  const status = work.my_submission_status;

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 shadow-xs hover:shadow-md transition-shadow relative">
      {/* Top Header: Source, Location & Action/Status */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-3">
        <div className="flex flex-wrap items-center gap-2">
          {/* House Source Badge */}
          <span
            className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-semibold uppercase tracking-wider ${
              work.source === 'LS'
                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                : 'bg-purple-50 text-purple-700 border border-purple-200'
            }`}
          >
            {work.source === 'LS' ? 'Lok Sabha' : 'Rajya Sabha'}
          </span>

          {/* District & Constituency */}
          <span className="text-xs font-medium text-slate-500">
            {work.district}
            {work.constituency ? ` • ${work.constituency}` : ''}
          </span>
        </div>

        {/* Top-Right Corner: Status Badge & Upload Action Slot */}
        <div className="flex items-center space-x-2 shrink-0 self-start">
          {status === 'pending' && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-300">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mr-1.5 animate-pulse"></span>
              Pending Review
            </span>
          )}
          {status === 'approved' && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5"></span>
              Approved (+150 XP)
            </span>
          )}
          {status === 'rejected' && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-red-50 text-red-800 border border-red-300">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 mr-1.5"></span>
              Rejected
            </span>
          )}

          {/* Slot for UploadButton (Step F5) */}
          {actionSlot}
        </div>
      </div>

      {/* Work Type Title */}
      <h2 className="text-base sm:text-lg font-bold text-slate-900 line-clamp-2 leading-snug mb-2">
        {work.work_type || work.description || 'Public Development Work'}
      </h2>

      {/* Description */}
      <p className="text-sm text-slate-600 mb-4 line-clamp-3 leading-relaxed">
        {work.description || 'No detailed description recorded.'}
      </p>

      {/* Metadata Grid */}
      <div className="pt-3 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-slate-600">
        <div>
          <span className="block text-slate-600 uppercase font-semibold tracking-wider text-[10px]">
            Hon'ble MP
          </span>
          <span className="font-semibold text-slate-800 truncate block mt-0.5" title={work.mp_name}>
            {work.mp_name || 'Not specified'}
          </span>
        </div>

        <div>
          <span className="block text-slate-600 uppercase font-semibold tracking-wider text-[10px]">
            Amount Disbursed
          </span>
          <span className="font-bold text-slate-900 mt-0.5 block text-sm">
            {formatINR(work.amount)}
          </span>
        </div>

        <div>
          <span className="block text-slate-600 uppercase font-semibold tracking-wider text-[10px]">
            Completion Date
          </span>
          <span className="font-medium text-slate-700 mt-0.5 block">
            {formatDate(work.completion_date)}
          </span>
        </div>
      </div>
    </div>
  );
}
