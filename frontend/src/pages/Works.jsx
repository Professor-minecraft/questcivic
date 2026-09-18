import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import Header from '../components/Header';
import WorkCard from '../components/WorkCard';
import UploadButton from '../components/UploadButton';
import Loader from '../components/Loader';

export default function Works() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [works, setWorks] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');

  const [loadingInitial, setLoadingInitial] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');

  // Check if location is set; if not redirect to /location
  useEffect(() => {
    if (user && (!user.state || !user.district || !user.constituency)) {
      navigate('/location', { replace: true });
    }
  }, [user, navigate]);

  // Debounce search input changes by 400ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 400);

    return () => clearTimeout(timer);
  }, [searchInput]);

  // Fetch works from API
  const fetchWorks = useCallback(
    async (targetPage, searchQuery, append = false) => {
      try {
        if (append) {
          setLoadingMore(true);
        } else {
          setLoadingInitial(true);
        }
        setError('');

        const params = {
          page: targetPage,
          page_size: pageSize,
        };
        if (searchQuery) {
          params.search = searchQuery;
        }

        const res = await api.get('/works', { params });
        const data = res.data;

        setTotal(data.total || 0);
        if (append) {
          setWorks((prev) => [...prev, ...(data.items || [])]);
        } else {
          setWorks(data.items || []);
        }
      } catch (err) {
        if (err.response?.status === 400 && err.response?.data?.detail === 'Location not set') {
          navigate('/location');
          return;
        }
        const msg =
          err.response?.data?.detail ||
          'Failed to load works. Please check your connection and try again.';
        setError(msg);
      } finally {
        setLoadingInitial(false);
        setLoadingMore(false);
      }
    },
    [pageSize, navigate]
  );

  // Initial load or search query change
  useEffect(() => {
    fetchWorks(1, search, false);
  }, [fetchWorks, search]);

  // Load More handler
  const handleLoadMore = () => {
    const nextPage = page + 1;
    setPage(nextPage);
    fetchWorks(nextPage, search, true);
  };

  // Handler when a verification photo upload succeeds
  const handleUploadSuccess = (workId, submission) => {
    setWorks((prev) =>
      prev.map((w) =>
        w.id === workId
          ? { ...w, my_submission_status: submission.status }
          : w
      )
    );
  };

  const hasMore = works.length < total;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Header />

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {/* Page Title & Location Context Banner */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
              MPLADS Works in Your Area
            </h1>
            <p className="mt-1 text-sm text-slate-600">
              Showing development projects verified and funded under MPLADS for{' '}
              <span className="font-semibold text-slate-800">
                {user?.constituency ? `${user.constituency} Constituency` : user?.district},{' '}
                {user?.state}
              </span>
            </p>
          </div>

          {/* Results Summary Counter */}
          <div className="inline-flex items-center text-xs font-semibold px-3 py-1.5 rounded-lg bg-blue-50 text-blue-800 border border-blue-200 self-start md:self-auto">
            {loadingInitial ? (
              <span>Loading works...</span>
            ) : (
              <span>
                {total} {total === 1 ? 'project found' : 'projects found'}
              </span>
            )}
          </div>
        </div>

        {/* Search Bar */}
        <div className="mb-6">
          <div className="relative max-w-lg">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
              <svg
                className="h-5 w-5 text-slate-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
            </div>
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search works by title or description..."
              className="w-full pl-10 pr-10 py-3 min-h-[44px] text-sm sm:text-base rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-xs"
            />
            {searchInput && (
              <button
                type="button"
                onClick={() => setSearchInput('')}
                className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 cursor-pointer"
                title="Clear search"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
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
              <p className="font-semibold">Unable to load works</p>
              <p className="mt-0.5">{error}</p>
            </div>
            <button
              onClick={() => fetchWorks(page, search, false)}
              className="px-3 py-1 bg-red-100 hover:bg-red-200 text-red-800 text-xs font-semibold rounded-md cursor-pointer transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Initial Loading Skeleton / Spinner */}
        {loadingInitial ? (
          <div className="py-20 flex flex-col items-center justify-center space-y-4">
            <Loader size="lg" />
            <p className="text-sm font-medium text-slate-500">
              Loading projects for {user?.district || 'your area'}...
            </p>
          </div>
        ) : works.length === 0 ? (
          /* Empty State */
          <div className="bg-white rounded-2xl border border-slate-200 p-10 sm:p-14 text-center max-w-xl mx-auto my-8 shadow-xs">
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
                  d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-slate-900 mb-1">
              {search ? 'No matching projects found' : 'No works found for this location'}
            </h3>
            <p className="text-sm text-slate-600 mb-6 max-w-sm mx-auto">
              {search
                ? `We couldn't find any development works matching "${search}". Try searching with a different term.`
                : 'There are no recorded MPLADS completed works in our dataset for the selected constituency or district.'}
            </p>
            {search ? (
              <button
                onClick={() => setSearchInput('')}
                className="min-h-[44px] px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors shadow-sm cursor-pointer"
              >
                Clear search query
              </button>
            ) : (
              <button
                onClick={() => navigate('/location?change=true')}
                className="min-h-[44px] px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors shadow-sm cursor-pointer"
              >
                Change Location
              </button>
            )}
          </div>
        ) : (
          /* Works Cards List */
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4">
              {works.map((work) => (
                <WorkCard
                  key={work.id}
                  work={work}
                  actionSlot={
                    <UploadButton
                      workId={work.id}
                      status={work.my_submission_status}
                      onSuccess={(sub) => handleUploadSuccess(work.id, sub)}
                    />
                  }
                />
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
                      <span>Loading more works...</span>
                    </span>
                  ) : (
                    <span>
                      Load more works ({works.length} of {total})
                    </span>
                  )}
                </button>
              </div>
            )}

            {!hasMore && works.length > 0 && (
              <div className="py-6 text-center text-xs font-medium text-slate-600">
                You have reached the end of the list ({total} total works).
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
