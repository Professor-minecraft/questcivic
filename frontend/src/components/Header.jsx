import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs" style={{ paddingTop: 'env(safe-area-inset-top)' }}>
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo */}
          <div className="flex items-center">
            <Link to="/works" className="flex items-center">
              <img
                src="/civicquest-logo-compact.svg"
                alt="CivicQuest"
                className="h-[34px] sm:h-[40px] w-auto block"
              />
            </Link>
          </div>

          {/* User Actions & XP Badge */}
          <div className="flex items-center space-x-2 sm:space-x-3">
            {/* User XP Badge */}
            <div className="flex items-center space-x-1 sm:space-x-1.5 px-2 sm:px-3 py-1.5 rounded-full bg-amber-50 border border-amber-200 text-amber-900 font-semibold text-xs sm:text-sm shadow-2xs shrink-0">
              <span className="text-amber-500 text-base" role="img" aria-label="XP Star">
                ★
              </span>
              <span>{user?.xp ?? 0}</span>
              <span className="hidden xs:inline text-amber-600 font-medium">XP</span>
            </div>

            {/* Leaderboard Link */}
            <Link
              to="/leaderboard"
              className="inline-flex items-center min-h-[44px] px-2 sm:px-3 py-2 text-xs sm:text-sm font-medium text-slate-700 hover:text-blue-600 hover:bg-slate-50 rounded-lg transition-colors cursor-pointer"
              title="Leaderboard"
            >
              <svg
                className="w-4 h-4 sm:mr-1.5 text-slate-400 shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
              <span className="hidden sm:inline">Leaderboard</span>
            </Link>

            {/* Profile Link */}
            <Link
              to="/profile"
              className="inline-flex items-center min-h-[44px] px-2 sm:px-3 py-2 text-xs sm:text-sm font-medium text-slate-700 hover:text-blue-600 hover:bg-slate-50 rounded-lg transition-colors cursor-pointer"
              title="Profile"
            >
              <svg
                className="w-4 h-4 sm:mr-1.5 text-slate-400 shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                />
              </svg>
              <span className="hidden sm:inline">Profile</span>
            </Link>

            {/* Change Location Link — icon-only on phones, full label on sm+ */}
            <Link
              to="/location?change=true"
              className="inline-flex items-center min-h-[44px] px-2 sm:px-3 py-2 text-xs sm:text-sm font-medium text-slate-700 hover:text-blue-600 hover:bg-slate-50 rounded-lg transition-colors cursor-pointer"
              title="Change your selected district & constituency"
            >
              <svg
                className="w-4 h-4 sm:mr-1.5 text-slate-400 shrink-0"
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
              <span className="hidden sm:inline">Change location</span>
            </Link>

            {/* Logout Button — icon-only on phones */}
            <button
              onClick={handleLogout}
              className="inline-flex items-center justify-center min-h-[44px] px-2 sm:px-3 py-2 text-xs sm:text-sm font-medium text-slate-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors cursor-pointer"
              title="Logout from CivicQuest"
            >
              <svg
                className="w-4 h-4 sm:mr-1 text-slate-400 hover:text-red-500 shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                />
              </svg>
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
