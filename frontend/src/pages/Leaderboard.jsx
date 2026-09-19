import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/client';
import Header from '../components/Header';
import Loader from '../components/Loader';
import LeaderboardRow from '../components/LeaderboardRow';
import '../styles/leaderboard.css';

export default function Leaderboard() {
  const [items, setItems] = useState([]);
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        setLoading(true);
        setError('');
        const res = await api.get('/leaderboard?limit=20');
        if (!active) return;
        setItems(res.data.items || []);
        setMe(res.data.me || null);
      } catch (err) {
        if (!active) return;
        setError(
          err.response?.data?.detail ||
            'Failed to load the leaderboard. Please try again.'
        );
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, []);

  // Is the current user already in the visible list?
  const meInList = items.some((i) => i.is_me);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Header />

      <main className="flex-1 mx-auto w-full max-w-md px-4 sm:max-w-2xl lg:max-w-3xl py-6 sm:py-8">
        {/* Back link */}
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

        {/* Page heading */}
        <div className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
            Leaderboard
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Top contributors ranked by XP earned from verified submissions.
          </p>
        </div>

        {/* Loading */}
        {loading && (
          <div className="py-20 flex flex-col items-center justify-center space-y-4">
            <Loader size="lg" color="text-blue-600" />
            <p className="text-sm font-medium text-slate-500">Loading leaderboard...</p>
          </div>
        )}

        {/* Error */}
        {!loading && error && (
          <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700 flex items-start space-x-3">
            <svg className="w-5 h-5 text-red-500 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
            <p>{error}</p>
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && items.length === 0 && (
          <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center shadow-xs">
            <div className="w-14 h-14 mx-auto rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mb-4">
              <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5"
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-slate-900 mb-1">No one on the leaderboard yet.</h3>
            <p className="text-sm text-slate-600">
              Be the first! Upload verification photos to earn XP.
            </p>
          </div>
        )}

        {/* Leaderboard rows */}
        {!loading && !error && items.length > 0 && (
          <div className="space-y-2">
            {items.map((item) => (
              <LeaderboardRow
                key={`${item.rank}-${item.name}`}
                item={item}
              />
            ))}
          </div>
        )}

        {/* "Your rank" card — only when user is NOT in the visible list */}
        {!loading && !error && !meInList && me && (
          <div className="mt-6">
            {me.xp > 0 ? (
              <div className="bg-blue-50 border-2 border-blue-400 rounded-xl px-4 py-3 flex items-center gap-3 shadow-xs">
                <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 font-bold text-xs shrink-0">
                  #{me.rank}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-blue-900 truncate">
                    Your rank: <span className="font-bold">#{me.rank}</span>
                  </p>
                  <p className="text-xs text-blue-700 truncate">{me.xp} XP earned</p>
                </div>
                <span className="shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-blue-600 text-white">
                  You
                </span>
              </div>
            ) : (
              <div className="bg-slate-100 border border-slate-200 rounded-xl px-4 py-3 text-center">
                <p className="text-sm text-slate-600 font-medium">
                  Earn XP to join the leaderboard.
                </p>
                <Link
                  to="/works"
                  className="mt-2 inline-flex items-center text-sm font-semibold text-blue-600 hover:text-blue-700 transition-colors"
                >
                  Browse works →
                </Link>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
