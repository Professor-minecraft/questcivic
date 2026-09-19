import { useState, useEffect, useCallback } from 'react';
import api from '../api/client';
import Loader from './Loader';

function formatDateTime(dateString) {
  if (!dateString) return '—';
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

export default function ReviewActivityList({ auditorId, userId }) {
  const [kind, setKind] = useState('all'); // 'all' | 'submission' | 'complaint'
  const [decision, setDecision] = useState('all'); // 'all' | 'approved' | 'rejected' | 'accepted'
  const [range, setRange] = useState('all'); // 'today' | '7d' | '30d' | 'all'

  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');

  const fetchReviews = useCallback(
    async (pageToFetch = 1, isLoadMore = false) => {
      try {
        if (isLoadMore) {
          setLoadingMore(true);
        } else {
          setLoading(true);
          setError('');
        }

        const params = {
          kind,
          decision,
          range,
          page: pageToFetch,
          page_size: 20,
        };

        if (auditorId !== undefined && auditorId !== null && auditorId !== '') {
          params.auditor_id = auditorId;
        }

        if (userId !== undefined && userId !== null && userId !== '') {
          params.user_id = userId;
        }

        const res = await api.get('/admin/reviews', { params });
        const fetchedItems = res.data.items || [];
        const fetchedTotal = res.data.total ?? fetchedItems.length;

        if (isLoadMore) {
          setItems((prev) => [...prev, ...fetchedItems]);
        } else {
          setItems(fetchedItems);
        }
        setTotal(fetchedTotal);
        setPage(pageToFetch);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load review activity.');
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [auditorId, userId, kind, decision, range]
  );

  useEffect(() => {
    fetchReviews(1, false);
  }, [fetchReviews]);

  const handleLoadMore = () => {
    if (!loadingMore && items.length < total) {
      fetchReviews(page + 1, true);
    }
  };

  const kindOptions = [
    { value: 'all', label: 'All' },
    { value: 'submission', label: 'Photos' },
    { value: 'complaint', label: 'Complaints' },
  ];

  const decisionOptions = [
    { value: 'all', label: 'All' },
    { value: 'approved', label: 'Approved' },
    { value: 'rejected', label: 'Rejected' },
    { value: 'accepted', label: 'Accepted' },
  ];

  const rangeOptions = [
    { value: 'today', label: 'Today' },
    { value: '7d', label: '7 days' },
    { value: '30d', label: '30 days' },
    { value: 'all', label: 'All' },
  ];

  return (
    <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl p-4 sm:p-6 shadow-xl space-y-5">
      {/* Header & Filter Controls */}
      <div className="space-y-4 border-b border-slate-700/80 pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <h3 className="text-lg font-bold text-white tracking-tight">
              Review Activity
            </h3>
            <p className="text-xs text-slate-400">
              {total} review{total === 1 ? '' : 's'} recorded
            </p>
          </div>
        </div>

        {/* Responsive Filters */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* Kind Filter */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-400 mb-1">
              Kind
            </label>
            <div className="flex rounded-xl bg-slate-900/80 p-1 border border-slate-700/60 overflow-x-auto">
              {kindOptions.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setKind(opt.value)}
                  className={`flex-1 min-h-[32px] px-2.5 py-1 text-xs font-semibold rounded-lg transition-all cursor-pointer whitespace-nowrap text-center ${
                    kind === opt.value
                      ? 'bg-purple-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Decision Filter */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-400 mb-1">
              Decision
            </label>
            <div className="flex rounded-xl bg-slate-900/80 p-1 border border-slate-700/60 overflow-x-auto">
              {decisionOptions.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setDecision(opt.value)}
                  className={`flex-1 min-h-[32px] px-2 py-1 text-xs font-semibold rounded-lg transition-all cursor-pointer whitespace-nowrap text-center ${
                    decision === opt.value
                      ? 'bg-purple-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Range Filter */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-400 mb-1">
              Range
            </label>
            <div className="flex rounded-xl bg-slate-900/80 p-1 border border-slate-700/60 overflow-x-auto">
              {rangeOptions.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setRange(opt.value)}
                  className={`flex-1 min-h-[32px] px-2 py-1 text-xs font-semibold rounded-lg transition-all cursor-pointer whitespace-nowrap text-center ${
                    range === opt.value
                      ? 'bg-purple-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 rounded-xl bg-red-950/70 border border-red-800 text-xs text-red-200">
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading ? (
        <div className="py-12 flex flex-col items-center justify-center space-y-2">
          <Loader size="md" />
          <span className="text-xs text-slate-400">Loading reviews...</span>
        </div>
      ) : items.length === 0 ? (
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-8 text-center">
          <p className="text-sm font-medium text-slate-300">No review activity found.</p>
          <p className="text-xs text-slate-500 mt-1">
            Try adjusting your filter settings.
          </p>
        </div>
      ) : (
        /* Items List */
        <div className="space-y-3">
          {items.map((item) => {
            const isApprovedOrAccepted =
              item.decision === 'approved' || item.decision === 'accepted';
            const decisionBadgeClass = isApprovedOrAccepted
              ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
              : 'bg-red-500/20 text-red-300 border-red-500/30';

            const kindLabel = item.kind === 'submission' ? 'Photo' : 'Complaint';
            const kindBadgeClass =
              item.kind === 'submission'
                ? 'bg-blue-500/20 text-blue-300 border-blue-500/30'
                : 'bg-amber-500/20 text-amber-300 border-amber-500/30';

            const locationStr =
              item.constituency ||
              [item.district, item.state].filter(Boolean).join(', ') ||
              '—';

            return (
              <div
                key={item.review_id}
                className="bg-slate-900/70 border border-slate-700/60 hover:border-slate-600 rounded-xl p-4 transition-all space-y-2.5 text-xs"
              >
                {/* Top Row: Date/Time, Badges, Review Time */}
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                    <span className="text-slate-400 font-mono text-[11px]">
                      {formatDateTime(item.created_at)}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${kindBadgeClass}`}
                    >
                      {kindLabel}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${decisionBadgeClass}`}
                    >
                      {item.decision}
                    </span>
                  </div>

                  <div className="text-[11px] text-slate-400 font-medium">
                    {item.review_minutes !== null && item.review_minutes !== undefined ? (
                      <span>Reviewed in {item.review_minutes} min</span>
                    ) : null}
                  </div>
                </div>

                {/* Title */}
                <h4 className="text-sm font-semibold text-white break-words">
                  {item.title || (item.kind === 'submission' ? 'Photo verification' : 'Citizen complaint')}
                </h4>

                {/* User Info & Constituency */}
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400 pt-1 border-t border-slate-800">
                  <div>
                    <span className="text-slate-500">User: </span>
                    {item.user?.name ? (
                      <>
                        <span className="font-semibold text-slate-200">
                          {item.user.name}
                        </span>{' '}
                        <span className="text-slate-400 font-mono text-[11px]">
                          ({item.user.email})
                        </span>
                      </>
                    ) : (
                      <span className="text-slate-200 font-mono text-[11px]">
                        {item.user?.email || '—'}
                      </span>
                    )}
                  </div>

                  <div className="text-[11px]">
                    <span className="text-slate-500">Location: </span>
                    <span className="text-slate-300 font-medium">{locationStr}</span>
                  </div>
                </div>

                {/* Auditor Name (hidden when auditorId prop is provided) */}
                {!auditorId && (
                  <div className="text-[11px] text-slate-400 flex items-center space-x-1.5">
                    <span className="text-slate-500">Auditor:</span>
                    <span className="text-purple-300 font-medium">
                      {item.auditor?.name || (item.auditor?.builtin ? 'Built-in auditor' : 'Auditor')}
                    </span>
                    {item.auditor?.builtin && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-purple-950 text-purple-300 border border-purple-800 uppercase">
                        Built-in
                      </span>
                    )}
                  </div>
                )}

                {/* Comment / Reason */}
                {item.comment && (
                  <div className="mt-2 p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 text-[11px] text-slate-300">
                    <span className="font-semibold text-slate-400 block mb-0.5">
                      {item.decision === 'rejected' ? 'Reject reason:' : 'Auditor comment:'}
                    </span>
                    <p className="break-words italic">{item.comment}</p>
                  </div>
                )}
              </div>
            );
          })}

          {/* Load More Button */}
          {items.length < total && (
            <div className="pt-3 text-center">
              <button
                type="button"
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="min-h-[40px] px-5 py-2 rounded-xl bg-slate-900 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-white transition-colors disabled:opacity-50 cursor-pointer inline-flex items-center space-x-2"
              >
                {loadingMore ? (
                  <>
                    <Loader size="sm" />
                    <span>Loading more...</span>
                  </>
                ) : (
                  <span>Load more reviews</span>
                )}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
