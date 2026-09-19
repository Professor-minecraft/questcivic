import { useState, useEffect } from 'react';
import api from '../api/client';
import Loader from './Loader';

function formatDate(dateString) {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return String(dateString);
    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return String(dateString);
  }
}

function formatShortDate(dateString) {
  if (!dateString) return '';
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return dateString;
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return dateString;
  }
}

export default function AuditorSummaryCard({ auditorId }) {
  const [range, setRange] = useState('30d'); // '7d' | '30d' | 'all'
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedDay, setSelectedDay] = useState(null);

  useEffect(() => {
    let active = true;

    async function loadSummary() {
      try {
        setLoading(true);
        setError('');
        const effectiveId = auditorId || 'builtin';
        const res = await api.get(`/admin/auditors/${effectiveId}/summary`, {
          params: { range },
        });
        if (active) {
          setSummary(res.data);
          // Default selected day to the last day if available
          if (res.data?.per_day?.length > 0) {
            setSelectedDay(res.data.per_day[res.data.per_day.length - 1]);
          }
        }
      } catch (err) {
        if (active) {
          setError(err.response?.data?.detail || 'Failed to load auditor summary.');
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    loadSummary();

    return () => {
      active = false;
    };
  }, [auditorId, range]);

  const rangeTabs = [
    { id: '7d', label: '7 days' },
    { id: '30d', label: '30 days' },
    { id: 'all', label: 'All' },
  ];

  const perDay = summary?.per_day || [];
  const maxCount = perDay.reduce((acc, curr) => Math.max(acc, curr.count), 0) || 1;

  return (
    <div className="bg-slate-800/90 border border-slate-700/80 rounded-2xl p-5 sm:p-6 shadow-xl space-y-6">
      {/* Top Header & Range Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-700/80 pb-4">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight">
            Auditor Performance
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Key metrics and review volume breakdown
          </p>
        </div>

        {/* Range Tabs */}
        <div className="inline-flex rounded-xl bg-slate-900/80 p-1 border border-slate-700/60 self-start sm:self-auto">
          {rangeTabs.map((tab) => {
            const isActive = range === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setRange(tab.id)}
                className={`min-h-[34px] px-3 py-1 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                  isActive
                    ? 'bg-purple-600 text-white shadow-sm shadow-purple-600/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="py-12 flex flex-col items-center justify-center space-y-2">
          <Loader size="md" />
          <span className="text-xs text-slate-400">Loading performance summary...</span>
        </div>
      ) : error ? (
        <div className="p-4 rounded-xl bg-red-950/70 border border-red-800 text-xs text-red-200">
          {error}
        </div>
      ) : summary ? (
        <div className="space-y-6">
          {/* Key Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 text-xs">
            {/* Total Reviews */}
            <div className="bg-slate-900/60 border border-slate-700/50 rounded-xl p-3.5 flex flex-col justify-between">
              <span className="text-slate-400 text-[11px] block font-medium">Total Reviews</span>
              <span className="text-xl sm:text-2xl font-black text-white mt-1">
                {summary.reviews_total}
              </span>
            </div>

            {/* Approval Rate */}
            <div className="bg-slate-900/60 border border-slate-700/50 rounded-xl p-3.5 flex flex-col justify-between">
              <span className="text-slate-400 text-[11px] block font-medium">Approval Rate</span>
              <span className="text-xl sm:text-2xl font-black text-emerald-400 mt-1">
                {summary.approval_rate !== null && summary.approval_rate !== undefined
                  ? `${Math.round(summary.approval_rate * 100)}%`
                  : 'N/A'}
              </span>
            </div>

            {/* Avg Review Time */}
            <div className="bg-slate-900/60 border border-slate-700/50 rounded-xl p-3.5 flex flex-col justify-between">
              <span className="text-slate-400 text-[11px] block font-medium">Avg Review Time</span>
              <span className="text-xl sm:text-2xl font-black text-purple-300 mt-1">
                {summary.avg_review_minutes !== null && summary.avg_review_minutes !== undefined
                  ? `${summary.avg_review_minutes} min`
                  : 'N/A'}
              </span>
            </div>

            {/* Photos & Complaints Quick Breakdowns */}
            <div className="bg-slate-900/60 border border-slate-700/50 rounded-xl p-3.5 flex flex-col justify-between col-span-2 sm:col-span-3 lg:col-span-1">
              <span className="text-slate-400 text-[11px] block font-medium">Decisions</span>
              <div className="mt-1 space-y-1 text-[11px]">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Photos:</span>
                  <span className="text-slate-200">
                    <span className="text-emerald-400 font-semibold">{summary.photos_approved} app</span>
                    {' / '}
                    <span className="text-red-400 font-semibold">{summary.photos_rejected} rej</span>
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Complaints:</span>
                  <span className="text-slate-200">
                    <span className="text-emerald-400 font-semibold">{summary.complaints_accepted} acc</span>
                    {' / '}
                    <span className="text-red-400 font-semibold">{summary.complaints_rejected} rej</span>
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* First and Last Review Dates */}
          <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
            <div className="flex items-center space-x-1.5">
              <span className="text-slate-500 font-medium">First review:</span>
              <span className="text-slate-200 font-medium">{formatDate(summary.first_review_at)}</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="text-slate-500 font-medium">Last review:</span>
              <span className="text-slate-200 font-medium">{formatDate(summary.last_review_at)}</span>
            </div>
          </div>

          {/* 30-Day Bar Chart */}
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                  Review Activity (Last 30 Days)
                </h4>
                <p className="text-[11px] text-slate-400">
                  Tap or hover over any bar to view the count
                </p>
              </div>

              {selectedDay && (
                <div className="bg-purple-950/60 border border-purple-800/80 px-2.5 py-1 rounded-lg text-right">
                  <span className="text-[11px] text-purple-300 font-semibold block">
                    {formatShortDate(selectedDay.date)}: {selectedDay.count} review{selectedDay.count === 1 ? '' : 's'}
                  </span>
                </div>
              )}
            </div>

            {/* Scrollable Bar Chart Row */}
            <div className="w-full overflow-x-auto pb-2 scrollbar-thin">
              <div className="min-w-[540px] h-36 bg-slate-900/80 border border-slate-700/60 rounded-xl p-3 flex items-end justify-between gap-1.5">
                {perDay.map((day, idx) => {
                  const isSelected = selectedDay?.date === day.date;
                  const barHeightPct = Math.max(
                    6,
                    Math.round((day.count / maxCount) * 100)
                  );

                  return (
                    <div
                      key={day.date || idx}
                      onClick={() => setSelectedDay(day)}
                      onMouseEnter={() => setSelectedDay(day)}
                      className="flex-1 min-w-[12px] h-full flex flex-col items-center justify-end group cursor-pointer relative"
                    >
                      {/* Interactive Bar */}
                      <div
                        style={{ height: `${barHeightPct}%` }}
                        className={`w-full rounded-t transition-all duration-150 ${
                          isSelected
                            ? 'bg-purple-400 shadow-md shadow-purple-500/50'
                            : day.count > 0
                            ? 'bg-purple-600/80 group-hover:bg-purple-500'
                            : 'bg-slate-800 group-hover:bg-slate-700'
                        }`}
                      />

                      {/* Tooltip on active bar */}
                      {isSelected && (
                        <div className="absolute -top-7 left-1/2 -translate-x-1/2 pointer-events-none z-10 whitespace-nowrap bg-slate-800 border border-purple-600/60 px-1.5 py-0.5 rounded shadow text-[10px] text-white font-bold">
                          {day.count}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Day Labels below chart: First, Mid, Last */}
              {perDay.length > 0 && (
                <div className="min-w-[540px] flex items-center justify-between text-[10px] text-slate-500 px-1 pt-1">
                  <span>{formatShortDate(perDay[0]?.date)}</span>
                  <span>{formatShortDate(perDay[Math.floor(perDay.length / 2)]?.date)}</span>
                  <span>{formatShortDate(perDay[perDay.length - 1]?.date)}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
