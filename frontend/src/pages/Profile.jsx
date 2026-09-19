import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import Header from '../components/Header';
import SubmissionCard from '../components/SubmissionCard';
import ComplaintCard from '../components/ComplaintCard';
import Loader from '../components/Loader';
import { GLOW_XP_THRESHOLD } from '../constants';

export default function Profile() {
  const { user, refreshUser } = useAuth();

  const [stats, setStats] = useState(null);
  const [activeTab, setActiveTab] = useState('approved'); // 'approved' or 'rejected'
  const [submissions, setSubmissions] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  const [loadingInitial, setLoadingInitial] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');

  const abortControllerRef = useRef(null);
  const reqIdRef = useRef(0);

  // Refresh user data (so XP is fresh) on every mount
  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  // Fetch stats (Approved, Rejected, Pending, total XP)
  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get('/me/stats');
      setStats(res.data);
    } catch (err) {
      console.error('Failed to load user stats:', err);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // Fetch submissions for the selected tab
  const fetchSubmissions = useCallback(
    async (tab, targetPage = 1, append = false) => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      reqIdRef.current += 1;
      const currentReqId = reqIdRef.current;

      try {
        if (append) {
          setLoadingMore(true);
        } else {
          setLoadingInitial(true);
        }
        setError('');

        const res = await api.get('/me/submissions', {
          params: {
            status: tab,
            page: targetPage,
            page_size: pageSize,
          },
          signal: controller.signal,
        });

        if (currentReqId !== reqIdRef.current) return;

        const data = res.data;
        setTotal(data.total || 0);
        if (append) {
          setSubmissions((prev) => [...prev, ...(data.items || [])]);
        } else {
          setSubmissions(data.items || []);
        }
      } catch (err) {
        if (
          axios.isCancel(err) ||
          err.name === 'CanceledError' ||
          err.name === 'AbortError' ||
          currentReqId !== reqIdRef.current
        ) {
          return;
        }
        const msg =
          err.response?.data?.detail ||
          'Failed to load submissions. Please check your connection and try again.';
        setError(msg);
      } finally {
        if (currentReqId === reqIdRef.current) {
          setLoadingInitial(false);
          setLoadingMore(false);
        }
      }
    },
    [pageSize]
  );

  // When activeTab changes: clear list, reset page, and fetch new items
  useEffect(() => {
    setSubmissions([]);
    setPage(1);
    fetchSubmissions(activeTab, 1, false);
  }, [activeTab, fetchSubmissions]);

  // Cleanup abort controller on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // Tab change handler
  const handleTabChange = (newTab) => {
    if (newTab === activeTab) return;
    setActiveTab(newTab);
  };

  // Load More handler
  const handleLoadMore = () => {
    const nextPage = page + 1;
    setPage(nextPage);
    fetchSubmissions(activeTab, nextPage, true);
  };

  // Complaints State & Fetching
  const [complaints, setComplaints] = useState([]);
  const [complaintsTotal, setComplaintsTotal] = useState(0);
  const [complaintsPage, setComplaintsPage] = useState(1);
  const [complaintsLoadingInitial, setComplaintsLoadingInitial] = useState(true);
  const [complaintsLoadingMore, setComplaintsLoadingMore] = useState(false);
  const [complaintsError, setComplaintsError] = useState('');

  const fetchComplaints = useCallback(async (targetPage = 1, append = false) => {
    try {
      if (append) {
        setComplaintsLoadingMore(true);
      } else {
        setComplaintsLoadingInitial(true);
      }
      setComplaintsError('');

      const res = await api.get('/complaints/mine', {
        params: {
          page: targetPage,
          page_size: 20,
        },
      });

      const data = res.data;
      setComplaintsTotal(data.total || 0);
      setComplaintsPage(targetPage);
      if (append) {
        setComplaints((prev) => [...prev, ...(data.items || [])]);
      } else {
        setComplaints(data.items || []);
      }
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        'Failed to load complaints. Please check your connection and try again.';
      setComplaintsError(msg);
    } finally {
      setComplaintsLoadingInitial(false);
      setComplaintsLoadingMore(false);
    }
  }, []);

  // Refresh the list each time the page opens so newly reviewed complaints appear
  useEffect(() => {
    fetchComplaints(1, false);
  }, [fetchComplaints]);

  const handleLoadMoreComplaints = () => {
    const nextPage = complaintsPage + 1;
    fetchComplaints(nextPage, true);
  };
  const hasMoreComplaints = complaints.length < complaintsTotal;

  const avatarLetter = (user?.email || 'U').charAt(0).toUpperCase();
  const hasMore = submissions.length < total;

  // Gold glowing game-like effect for users with >= 1000 XP
  const userXP = Number(user?.xp ?? stats?.xp ?? 0);
  const isGlowing = userXP >= GLOW_XP_THRESHOLD;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Header />

      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {/* Back to works link */}
        <div className="mb-4">
          <Link
            to="/works"
            className="inline-flex items-center text-sm font-medium text-slate-600 hover:text-blue-600 transition-colors group cursor-pointer"
          >
            <svg
              className="w-4 h-4 mr-1.5 transform group-hover:-translate-x-0.5 transition-transform text-slate-400 group-hover:text-blue-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back to works
          </Link>
        </div>

        {/* Profile Card (Top Section) */}
        <div
          className={`bg-white rounded-2xl border p-6 sm:p-8 mb-8 transition-all duration-300 ${
            isGlowing
              ? 'border-[#facc15] glow-card'
              : 'border-slate-200 shadow-xs'
          }`}
        >
          <div className="flex flex-col sm:flex-row items-center sm:items-start gap-5 text-center sm:text-left">
            {/* Round Avatar */}
            <div
              className={`w-16 h-16 sm:w-20 sm:h-20 rounded-full bg-gradient-to-br from-blue-600 to-indigo-700 text-white font-bold text-2xl sm:text-3xl flex items-center justify-center shrink-0 transition-all duration-300 ${
                isGlowing
                  ? 'glow-avatar'
                  : 'shadow-md shadow-blue-500/20'
              }`}
            >
              {avatarLetter}
            </div>

            {/* Email, Location, Total XP */}
            <div className="flex-1 min-w-0">
              <h1 className="text-xl sm:text-2xl font-bold text-slate-900 break-words">
                {user?.email || 'Citizen User'}
              </h1>

              <p className="text-sm text-slate-600 mt-1 flex items-center justify-center sm:justify-start gap-1.5 flex-wrap">
                <svg
                  className="w-4 h-4 text-slate-400 shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
                <span>
                  {user?.constituency ? `${user.constituency} Constituency, ` : ''}
                  {user?.district ? `${user.district}, ` : ''}
                  {user?.state || 'Location not set'}
                </span>
              </p>

              <div className="mt-3">
                <div className="inline-flex items-center space-x-1.5 px-3.5 py-1.5 rounded-full bg-amber-50 border border-amber-200 text-amber-900 font-bold text-sm shadow-2xs">
                  <span className="text-amber-500 text-base" role="img" aria-label="XP Star">
                    ★
                  </span>
                  <span>{user?.xp ?? stats?.xp ?? 0}</span>
                  <span className="text-amber-600 font-medium">Total XP</span>
                </div>
              </div>
            </div>
          </div>

          {/* Three Small Counters: Approved, Rejected, Pending */}
          <div className="grid grid-cols-3 gap-3 sm:gap-4 mt-6 pt-6 border-t border-slate-100 text-center">
            <div className="bg-slate-50/80 rounded-xl p-3 border border-slate-100">
              <div className="text-2xl sm:text-3xl font-bold text-emerald-600">
                {stats?.approved ?? 0}
              </div>
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mt-1">
                Approved
              </div>
            </div>
            <div className="bg-slate-50/80 rounded-xl p-3 border border-slate-100">
              <div className="text-2xl sm:text-3xl font-bold text-red-600">
                {stats?.rejected ?? 0}
              </div>
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mt-1">
                Rejected
              </div>
            </div>
            <div className="bg-slate-50/80 rounded-xl p-3 border border-slate-100">
              <div className="text-2xl sm:text-3xl font-bold text-amber-600">
                {stats?.pending ?? 0}
              </div>
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mt-1">
                Pending
              </div>
            </div>
          </div>
        </div>

        {/* Two Tabs: Approved and Rejected (Default: Approved) */}
        <div className="mb-6">
          <div
            role="tablist"
            aria-label="Submission status tabs"
            className="inline-flex items-center p-1 bg-slate-200/80 rounded-xl border border-slate-200 w-full sm:w-auto"
          >
            <button
              type="button"
              role="tab"
              id="tab-approved"
              aria-selected={activeTab === 'approved'}
              aria-controls="submissions-list"
              onClick={() => handleTabChange('approved')}
              className={`flex-1 sm:flex-initial min-h-[44px] px-6 py-2.5 rounded-lg text-sm font-semibold transition-all flex items-center justify-center cursor-pointer ${
                activeTab === 'approved'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
              }`}
            >
              Approved
            </button>
            <button
              type="button"
              role="tab"
              id="tab-rejected"
              aria-selected={activeTab === 'rejected'}
              aria-controls="submissions-list"
              onClick={() => handleTabChange('rejected')}
              className={`flex-1 sm:flex-initial min-h-[44px] px-6 py-2.5 rounded-lg text-sm font-semibold transition-all flex items-center justify-center cursor-pointer ${
                activeTab === 'rejected'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
              }`}
            >
              Rejected
            </button>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700 flex items-start space-x-3">
            <svg
              className="w-5 h-5 text-red-500 shrink-0 mt-0.5"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
            <div className="flex-1">
              <p className="font-semibold">Unable to load submissions</p>
              <p className="mt-0.5">{error}</p>
            </div>
            <button
              type="button"
              onClick={() => fetchSubmissions(activeTab, page, false)}
              className="px-3 py-1 bg-red-100 hover:bg-red-200 text-red-800 text-xs font-semibold rounded-md cursor-pointer transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Tab Content */}
        {loadingInitial ? (
          <div className="py-20 flex flex-col items-center justify-center space-y-4">
            <Loader size="lg" />
            <p className="text-sm font-medium text-slate-500">
              Loading {activeTab} submissions...
            </p>
          </div>
        ) : submissions.length === 0 ? (
          /* Empty State per Tab */
          <div className="bg-white rounded-2xl border border-slate-200 p-10 sm:p-14 text-center max-w-xl mx-auto my-6 shadow-xs">
            <div className="w-14 h-14 mx-auto rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mb-4">
              <svg
                className="w-8 h-8"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="1.5"
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-slate-900 mb-1">
              {activeTab === 'approved'
                ? 'No approved uploads yet.'
                : 'No rejected uploads yet.'}
            </h3>
            <p className="text-sm text-slate-600 mb-6 max-w-sm mx-auto">
              {activeTab === 'approved'
                ? 'When your uploaded verification photos are approved by an auditor, they will appear here along with your earned XP.'
                : 'Any uploads that are reviewed and rejected with feedback will appear here so you can retake them.'}
            </p>
            <Link
              to="/works"
              className="inline-flex items-center min-h-[44px] px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors shadow-xs cursor-pointer"
            >
              Browse works to verify
            </Link>
          </div>
        ) : (
          /* Submissions List */
          <div id="submissions-list" className="space-y-4">
            <div className="grid grid-cols-1 gap-4">
              {submissions.map((item) => (
                <SubmissionCard key={item.submission_id} item={item} />
              ))}
            </div>

            {/* Load More Pagination */}
            {hasMore && (
              <div className="pt-6 pb-8 text-center">
                <button
                  type="button"
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  className="min-h-[44px] inline-flex items-center justify-center px-6 py-3 rounded-xl text-sm font-semibold text-blue-700 bg-blue-50 border border-blue-200 hover:bg-blue-100 active:bg-blue-200 disabled:opacity-60 disabled:cursor-not-allowed transition-colors shadow-2xs cursor-pointer"
                >
                  {loadingMore ? (
                    <span className="flex items-center space-x-2">
                      <Loader size="sm" />
                      <span>Loading more...</span>
                    </span>
                  ) : (
                    <span>
                      Load more ({submissions.length} of {total})
                    </span>
                  )}
                </button>
              </div>
            )}

            {!hasMore && submissions.length > 0 && (
              <div className="py-6 text-center text-xs font-medium text-slate-600">
                You have reached the end of the list ({total} total {activeTab} submissions).
              </div>
            )}
          </div>
        )}

        {/* ================= My Complaints Section ================= */}
        <section className="mt-12 pt-8 border-t border-slate-200">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
            <div>
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900">
                My Complaints
              </h2>
              <p className="text-xs sm:text-sm text-slate-600 mt-0.5">
                Track all damaged infrastructure reports and auditor reviews.
              </p>
            </div>
            <div className="inline-flex items-center text-xs font-semibold px-3 py-1.5 rounded-lg bg-red-50 text-red-800 border border-red-200 self-start sm:self-auto">
              {complaintsLoadingInitial ? (
                <span>Loading complaints...</span>
              ) : (
                <span>
                  {complaintsTotal} {complaintsTotal === 1 ? 'complaint' : 'complaints'}
                </span>
              )}
            </div>
          </div>

          {/* Error Alert */}
          {complaintsError && (
            <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700 flex items-start space-x-3">
              <svg className="w-5 h-5 text-red-500 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <div className="flex-1">
                <p className="font-semibold">Unable to load complaints</p>
                <p className="mt-0.5">{complaintsError}</p>
              </div>
              <button
                type="button"
                onClick={() => fetchComplaints(1, false)}
                className="px-3 py-1 bg-red-100 hover:bg-red-200 text-red-800 text-xs font-semibold rounded-md cursor-pointer transition-colors"
              >
                Retry
              </button>
            </div>
          )}

          {/* Loading State */}
          {complaintsLoadingInitial ? (
            <div className="py-12 flex flex-col items-center justify-center space-y-3">
              <Loader size="md" />
              <p className="text-sm font-medium text-slate-500">Loading your complaints...</p>
            </div>
          ) : complaints.length === 0 ? (
            /* Empty State */
            <div className="bg-white rounded-2xl border border-slate-200 p-8 sm:p-12 text-center max-w-xl mx-auto my-4 shadow-xs">
              <div className="w-12 h-12 mx-auto rounded-2xl bg-red-50 text-red-500 flex items-center justify-center mb-3">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h3 className="text-base sm:text-lg font-bold text-slate-900 mb-1">
                You have not filed any complaints yet.
              </h3>
              <p className="text-xs sm:text-sm text-slate-600 mb-5 max-w-sm mx-auto">
                Spot damaged public works or infrastructure? Report them from the Works page to earn 50 XP upon review.
              </p>
              <Link
                to="/works"
                className="inline-flex items-center min-h-[44px] px-5 py-2.5 rounded-xl bg-red-600 text-white text-sm font-semibold hover:bg-red-700 transition-colors shadow-xs cursor-pointer"
              >
                Go to Works page
              </Link>
            </div>
          ) : (
            /* Complaints List */
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-4">
                {complaints.map((c) => (
                  <ComplaintCard key={c.id} item={c} />
                ))}
              </div>

              {/* Load More Pagination */}
              {hasMoreComplaints && (
                <div className="pt-6 pb-4 text-center">
                  <button
                    type="button"
                    onClick={handleLoadMoreComplaints}
                    disabled={complaintsLoadingMore}
                    className="min-h-[44px] inline-flex items-center justify-center px-6 py-3 rounded-xl text-sm font-semibold text-red-700 bg-red-50 border border-red-200 hover:bg-red-100 active:bg-red-200 disabled:opacity-60 disabled:cursor-not-allowed transition-colors shadow-2xs cursor-pointer"
                  >
                    {complaintsLoadingMore ? (
                      <span className="flex items-center space-x-2">
                        <Loader size="sm" />
                        <span>Loading more complaints...</span>
                      </span>
                    ) : (
                      <span>
                        Load more ({complaints.length} of {complaintsTotal})
                      </span>
                    )}
                  </button>
                </div>
              )}

              {!hasMoreComplaints && complaints.length > 0 && (
                <div className="py-4 text-center text-xs font-medium text-slate-600">
                  You have reached the end of the complaints list ({complaintsTotal} total).
                </div>
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
