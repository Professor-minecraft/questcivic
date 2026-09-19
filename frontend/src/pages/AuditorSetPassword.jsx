import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import api from '../api/client';
import Loader from '../components/Loader';

export default function AuditorSetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [loadingInvite, setLoadingInvite] = useState(true);
  const [inviteError, setInviteError] = useState('');
  const [auditorInfo, setAuditorInfo] = useState(null);

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function verifyToken() {
      if (!token || !token.trim()) {
        if (isMounted) {
          setInviteError('This link is invalid or has expired. Ask the admin for a new link.');
          setLoadingInvite(false);
        }
        return;
      }

      try {
        setLoadingInvite(true);
        const res = await api.get(`/auth/auditor-invite/${encodeURIComponent(token.trim())}`);
        if (isMounted) {
          setAuditorInfo(res.data);
          setInviteError('');
        }
      } catch {
        if (isMounted) {
          setInviteError('This link is invalid or has expired. Ask the admin for a new link.');
        }
      } finally {
        if (isMounted) {
          setLoadingInvite(false);
        }
      }
    }

    verifyToken();

    return () => {
      isMounted = false;
    };
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');

    if (!password || !confirmPassword) {
      setFormError('Please fill in both password fields.');
      return;
    }

    // Rules: at least 8 characters, one letter and one digit; both fields must match.
    if (password.length < 8) {
      setFormError('Password must be at least 8 characters long.');
      return;
    }

    if (!/[a-zA-Z]/.test(password) || !/\d/.test(password)) {
      setFormError('Password must contain at least one letter and one digit.');
      return;
    }

    if (password !== confirmPassword) {
      setFormError('Passwords do not match.');
      return;
    }

    try {
      setSubmitting(true);
      await api.post('/auth/auditor-set-password', {
        token: token.trim(),
        password: password,
      });
      setSuccess(true);
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        'Failed to set password. The link may have expired or is invalid.';
      setFormError(msg);
    } finally {
      setSubmitting(false);
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
          Auditor Account Setup
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Set up your auditor credentials to access the portal
        </p>
      </div>

      <div className="mt-8 mx-auto w-full max-w-md">
        <div className="bg-slate-800/90 backdrop-blur-xs py-8 px-6 shadow-2xl border border-slate-700/60 rounded-2xl sm:px-10">
          {loadingInvite ? (
            <div className="py-12 flex flex-col items-center justify-center space-y-3">
              <Loader size="lg" />
              <p className="text-sm text-slate-400">Verifying invitation link...</p>
            </div>
          ) : inviteError ? (
            <div className="space-y-6 text-center">
              <div className="p-4 rounded-xl bg-red-950/70 border border-red-800 text-sm text-red-200">
                <p className="font-medium">{inviteError}</p>
              </div>
              <div>
                <Link
                  to="/auditor/login"
                  className="inline-flex items-center justify-center px-4 py-2.5 rounded-xl text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 transition-colors"
                >
                  Go to Auditor / Admin login
                </Link>
              </div>
            </div>
          ) : success ? (
            <div className="space-y-6 text-center">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 mb-2">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div>
                <h2 className="text-xl font-bold text-white mb-2">Password set</h2>
                <p className="text-sm text-slate-300">
                  Your auditor account is now ready. You can log in using your email and the password you just created.
                </p>
              </div>
              <div className="pt-2">
                <Link
                  to="/auditor/login"
                  className="w-full inline-flex items-center justify-center min-h-[44px] py-3 px-4 rounded-xl text-base font-semibold text-white bg-blue-600 hover:bg-blue-500 transition-colors shadow-lg shadow-blue-600/30"
                >
                  Proceed to Auditor / Admin login &rarr;
                </Link>
              </div>
            </div>
          ) : (
            <div>
              <div className="mb-6 pb-5 border-b border-slate-700/80">
                <h2 className="text-xl font-bold text-white mb-1">
                  Hello {auditorInfo?.name}
                </h2>
                <p className="text-xs text-slate-400">
                  Create a password to complete your account activation.
                </p>
              </div>

              {formError && (
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
                  <span>{formError}</span>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label className="block text-sm font-semibold text-slate-300 mb-1.5">
                    Email
                  </label>
                  <input
                    type="email"
                    readOnly
                    value={auditorInfo?.email || ''}
                    className="w-full px-4 py-3 min-h-[44px] text-base rounded-xl border border-slate-700 bg-slate-900/50 text-slate-400 cursor-not-allowed shadow-inner focus:outline-none"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label
                      htmlFor="new-password"
                      className="block text-sm font-semibold text-slate-200"
                    >
                      New password
                    </label>
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="text-xs font-medium text-blue-400 hover:text-blue-300 cursor-pointer"
                    >
                      {showPassword ? 'Hide password' : 'Show password'}
                    </button>
                  </div>
                  <div className="relative">
                    <input
                      id="new-password"
                      type={showPassword ? 'text' : 'password'}
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="At least 8 characters, letter & digit"
                      autoComplete="new-password"
                      className="w-full px-4 py-3 min-h-[44px] text-base rounded-xl border border-slate-600 bg-slate-900/80 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all shadow-inner"
                    />
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="confirm-password"
                    className="block text-sm font-semibold text-slate-200 mb-1.5"
                  >
                    Confirm password
                  </label>
                  <div className="relative">
                    <input
                      id="confirm-password"
                      type={showPassword ? 'text' : 'password'}
                      required
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Re-enter your password"
                      autoComplete="new-password"
                      className="w-full px-4 py-3 min-h-[44px] text-base rounded-xl border border-slate-600 bg-slate-900/80 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all shadow-inner"
                    />
                  </div>
                </div>

                <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-700/50 text-xs text-slate-400 space-y-1">
                  <p className="font-medium text-slate-300">Password requirements:</p>
                  <ul className="list-disc list-inside space-y-0.5">
                    <li className={password.length >= 8 ? 'text-emerald-400' : ''}>
                      At least 8 characters
                    </li>
                    <li className={/[a-zA-Z]/.test(password) && /\d/.test(password) ? 'text-emerald-400' : ''}>
                      Must include at least one letter and one digit
                    </li>
                    <li className={password && confirmPassword && password === confirmPassword ? 'text-emerald-400' : ''}>
                      Both fields must match
                    </li>
                  </ul>
                </div>

                <button
                  type="submit"
                  disabled={submitting || !password || !confirmPassword}
                  className="w-full min-h-[44px] flex items-center justify-center py-3 px-4 rounded-xl text-base font-semibold text-white bg-blue-600 hover:bg-blue-500 active:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg shadow-blue-600/30 cursor-pointer mt-6"
                >
                  {submitting ? (
                    <span className="flex items-center space-x-2">
                      <Loader size="sm" />
                      <span>Saving password...</span>
                    </span>
                  ) : (
                    'Set Password'
                  )}
                </button>
              </form>

              <div className="mt-8 pt-6 border-t border-slate-700/80 text-center">
                <Link
                  to="/auditor/login"
                  className="text-sm font-medium text-slate-400 hover:text-blue-400 transition-colors"
                >
                  Already set your password? Sign in &rarr;
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
