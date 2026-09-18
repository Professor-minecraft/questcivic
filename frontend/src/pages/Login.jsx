import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import Loader from '../components/Loader';

export default function Login() {
  const navigate = useNavigate();
  const { login, token, role } = useAuth();

  // If already logged in, redirect
  useEffect(() => {
    if (token) {
      if (role === 'auditor') {
        navigate('/auditor', { replace: true });
      } else {
        navigate('/works', { replace: true });
      }
    }
  }, [token, role, navigate]);

  const [step, setStep] = useState(1); // 1 = email, 2 = otp
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resendTimer, setResendTimer] = useState(0);

  // Countdown timer for Resend OTP
  useEffect(() => {
    let interval = null;
    if (resendTimer > 0) {
      interval = setInterval(() => {
        setResendTimer((prev) => prev - 1);
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [resendTimer]);

  const validateGmail = (val) => {
    const trimmed = val.trim().toLowerCase();
    return trimmed.endsWith('@gmail.com') && trimmed.length > '@gmail.com'.length;
  };

  const handleSendOtp = async (e) => {
    if (e) e.preventDefault();
    setError('');

    const trimmedEmail = email.trim().toLowerCase();
    if (!trimmedEmail) {
      setError('Please enter your email address.');
      return;
    }

    if (!validateGmail(trimmedEmail)) {
      setError('Only @gmail.com email addresses are allowed.');
      return;
    }

    try {
      setLoading(true);
      await api.post('/auth/request-otp', { email: trimmedEmail });
      setStep(2);
      setResendTimer(30);
      setOtp('');
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        'Failed to send OTP. Please check your network or try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e) => {
    if (e) e.preventDefault();
    setError('');

    const trimmedOtp = otp.trim();
    if (trimmedOtp.length !== 6 || !/^\d{6}$/.test(trimmedOtp)) {
      setError('Please enter a valid 6-digit OTP code.');
      return;
    }

    try {
      setLoading(true);
      const res = await api.post('/auth/verify-otp', {
        email: email.trim().toLowerCase(),
        otp: trimmedOtp,
      });

      // Save token and user into AuthContext and localStorage
      login(res.data.access_token, 'user', res.data.user);

      // Navigate to location setup
      navigate('/location');
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        'Invalid or expired OTP code. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8 px-4">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-600 text-white shadow-lg shadow-blue-500/30 mb-4">
          <svg
            className="w-8 h-8"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
            />
          </svg>
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
          CivicQuest
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Verify MPLADS development projects in your constituency
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-sm border border-slate-200 rounded-2xl sm:px-10">
          {error && (
            <div className="mb-5 p-3.5 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700 flex items-start space-x-2">
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
              <span>{error}</span>
            </div>
          )}

          {step === 1 ? (
            <form onSubmit={handleSendOtp} className="space-y-5">
              <div>
                <label
                  htmlFor="email-input"
                  className="block text-sm font-semibold text-slate-800 mb-1.5"
                >
                  Gmail Address
                </label>
                <div className="relative">
                  <input
                    id="email-input"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="citizen@gmail.com"
                    autoComplete="email"
                    className="w-full px-4 py-3 min-h-[44px] text-base rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-sm"
                  />
                </div>
                <p className="mt-1.5 text-xs text-slate-500">
                  Only personal or verified @gmail.com accounts are eligible.
                </p>
              </div>

              <button
                type="submit"
                disabled={loading || !email}
                className="w-full min-h-[44px] flex items-center justify-center py-3 px-4 rounded-xl text-base font-medium text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm cursor-pointer"
              >
                {loading ? (
                  <span className="flex items-center space-x-2">
                    <Loader size="sm" />
                    <span>Sending OTP...</span>
                  </span>
                ) : (
                  'Send OTP'
                )}
              </button>
            </form>
          ) : (
            <form onSubmit={handleVerifyOtp} className="space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
                    Sent code to
                  </span>
                  <p className="text-sm font-semibold text-slate-900 truncate max-w-[220px]">
                    {email}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setStep(1);
                    setError('');
                  }}
                  className="text-xs font-semibold text-blue-600 hover:text-blue-700 cursor-pointer underline"
                >
                  Change
                </button>
              </div>

              <div>
                <label
                  htmlFor="otp-input"
                  className="block text-sm font-semibold text-slate-800 mb-1.5"
                >
                  6-Digit OTP Code
                </label>
                <input
                  id="otp-input"
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  autoFocus
                  value={otp}
                  onChange={(e) => {
                    const val = e.target.value.replace(/\D/g, '');
                    setOtp(val);
                  }}
                  placeholder="123456"
                  className="w-full text-center tracking-widest text-2xl font-mono py-3 min-h-[44px] rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-sm"
                />
              </div>

              <button
                type="submit"
                disabled={loading || otp.length !== 6}
                className="w-full min-h-[44px] flex items-center justify-center py-3 px-4 rounded-xl text-base font-medium text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm cursor-pointer"
              >
                {loading ? (
                  <span className="flex items-center space-x-2">
                    <Loader size="sm" />
                    <span>Verifying...</span>
                  </span>
                ) : (
                  'Verify'
                )}
              </button>

              <div className="pt-2 flex items-center justify-center">
                <button
                  type="button"
                  disabled={resendTimer > 0 || loading}
                  onClick={handleSendOtp}
                  className="text-sm font-medium text-blue-600 hover:text-blue-700 disabled:text-slate-400 disabled:cursor-not-allowed cursor-pointer"
                >
                  {resendTimer > 0
                    ? `Resend OTP in ${resendTimer}s`
                    : 'Resend OTP'}
                </button>
              </div>
            </form>
          )}

          <div className="mt-8 pt-6 border-t border-slate-100 text-center">
            <Link
              to="/auditor/login"
              className="text-sm font-medium text-slate-600 hover:text-blue-600 transition-colors"
            >
              Auditor login &rarr;
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
