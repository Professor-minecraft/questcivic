import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import Loader from '../components/Loader';

export default function AuditorLogin() {
  const navigate = useNavigate();
  const { login, token, role } = useAuth();

  // If already logged in as auditor or admin, navigate to appropriate dashboard
  useEffect(() => {
    if (token) {
      if (role === 'admin') {
        navigate('/admin', { replace: true });
      } else if (role === 'auditor') {
        navigate('/auditor', { replace: true });
      }
    }
  }, [token, role, navigate]);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    const trimmedUsername = username.trim();
    if (!trimmedUsername || !password) {
      setError('Please enter both ID or Gmail and password.');
      return;
    }

    try {
      setLoading(true);
      const res = await api.post('/auth/staff-login', {
        username: trimmedUsername,
        password: password,
      });

      const { access_token, role: staffRole } = res.data;

      // Save token and role
      login(access_token, staffRole, null);

      // Navigate to auditor or admin dashboard
      if (staffRole === 'admin') {
        navigate('/admin');
      } else {
        navigate('/auditor');
      }
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Invalid ID or password');
      } else if (err.response?.status === 403) {
        setError(err.response?.data?.detail || 'This account is disabled. Contact the admin.');
      } else if (err.response?.status === 429) {
        setError('Too many attempts. Try again in 15 minutes.');
      } else {
        setError(err.response?.data?.detail || 'Invalid credentials or network error.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col justify-center py-12 px-4">
      <div className="mx-auto w-full max-w-md text-center">
        <img
          src="/civicquest-logo.svg"
          alt="CivicQuest"
          className="mx-auto max-w-[260px] sm:max-w-[320px] w-full h-auto mb-4"
        />
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
          Auditor / Admin login
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Administrative sign-in for auditors and system administrators
        </p>
      </div>

      <div className="mt-8 mx-auto w-full max-w-md">
        <div className="bg-slate-800/90 backdrop-blur-xs py-8 px-6 shadow-2xl border border-slate-700/60 rounded-2xl sm:px-10">
          {error && (
            <div className="mb-6 p-3.5 rounded-xl bg-red-950/70 border border-red-800 text-sm text-red-200 flex items-start space-x-2">
              <svg
                className="w-5 h-5 text-red-400 shrink-0 mt-0.5"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label
                htmlFor="username-input"
                className="block text-sm font-semibold text-slate-200 mb-1.5"
              >
                ID or Gmail
              </label>
              <input
                id="username-input"
                type="text"
                required
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter ID or Gmail"
                autoComplete="username"
                className="w-full px-4 py-3 min-h-[44px] text-base rounded-xl border border-slate-600 bg-slate-900/80 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all shadow-inner"
              />
            </div>

            <div>
              <label
                htmlFor="password-input"
                className="block text-sm font-semibold text-slate-200 mb-1.5"
              >
                Password
              </label>
              <div className="relative">
                <input
                  id="password-input"
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter auditor password"
                  autoComplete="current-password"
                  className="w-full pl-4 pr-11 py-3 min-h-[44px] text-base rounded-xl border border-slate-600 bg-slate-900/80 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all shadow-inner"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-200 cursor-pointer"
                  title={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18"
                      />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                      />
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                      />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !username || !password}
              className="w-full min-h-[44px] flex items-center justify-center py-3 px-4 rounded-xl text-base font-semibold text-white bg-blue-600 hover:bg-blue-500 active:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg shadow-blue-600/30 cursor-pointer mt-6"
            >
              {loading ? (
                <span className="flex items-center space-x-2">
                  <Loader size="sm" />
                  <span>Authenticating...</span>
                </span>
              ) : (
                'Sign In'
              )}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-slate-700/80 text-center">
            <Link
              to="/login"
              className="text-sm font-medium text-slate-400 hover:text-blue-400 transition-colors"
            >
              &larr; Citizen verification portal
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
