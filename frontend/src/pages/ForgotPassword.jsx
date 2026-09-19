import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/client';
import Loader from '../components/Loader';

export default function ForgotPassword() {
  const [step, setStep] = useState(1); // 1 = request reset code, 2 = enter code and new password, 3 = success

  // Form fields
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // States
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isExpiredError, setIsExpiredError] = useState(false);
  const [serverMessage, setServerMessage] = useState('');
  const [remainingRequests, setRemainingRequests] = useState(null);
  const [resendTimer, setResendTimer] = useState(0);

  // 60-second cooldown timer
  useEffect(() => {
    let interval = null;
    if (resendTimer > 0) {
      interval = setInterval(() => {
        setResendTimer((prev) => (prev > 0 ? prev - 1 : 0));
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

  const extractErrorMessage = (err, fallback) => {
    const data = err.response?.data;
    if (!data) return fallback;

    let baseMsg = data.message || data.detail;
    if (typeof baseMsg !== 'string') {
      if (Array.isArray(data.detail)) {
        baseMsg = data.detail.map((d) => d.msg || JSON.stringify(d)).join(', ');
      } else {
        baseMsg = fallback;
      }
    }

    // If 429 and retry_after_seconds is provided, compute and append local time
    if (err.response?.status === 429 && data.retry_after_seconds) {
      const retryDate = new Date(Date.now() + data.retry_after_seconds * 1000);
      const timeStr = retryDate.toLocaleTimeString([], {
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
      });
      return `${baseMsg} (You can try again at ${timeStr})`;
    }

    return baseMsg || fallback;
  };

  // Step 1: Send reset code
  const handleSendResetCode = async (e) => {
    if (e) e.preventDefault();
    if (loading || resendTimer > 0) return;
    setError('');
    setIsExpiredError(false);

    const trimmedEmail = email.trim().toLowerCase();
    if (!trimmedEmail) {
      setError('Please enter your Gmail address.');
      return;
    }
    if (!validateGmail(trimmedEmail)) {
      setError('Only @gmail.com email addresses are allowed.');
      return;
    }

    try {
      setLoading(true);
      const res = await api.post('/auth/forgot-password', { email: trimmedEmail });
      setServerMessage(res.data.message || 'If this email is registered, a reset code has been sent.');
      if (res.data.remaining_requests_today !== undefined) {
        setRemainingRequests(res.data.remaining_requests_today);
      }
      setResendTimer(60);
      setStep(2);
    } catch (err) {
      const msg = extractErrorMessage(err, 'Failed to send reset code. Please try again.');
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Reset password with OTP
  const handleResetPassword = async (e) => {
    if (e) e.preventDefault();
    if (loading) return;
    setError('');
    setIsExpiredError(false);

    const trimmedEmail = email.trim().toLowerCase();
    const trimmedOtp = otp.trim();

    if (!trimmedOtp || trimmedOtp.length !== 6 || !/^\d{6}$/.test(trimmedOtp)) {
      setError('Please enter a valid 6-digit code.');
      return;
    }

    if (!newPassword) {
      setError('Please enter a new password.');
      return;
    }
    if (newPassword.length < 8 || newPassword.length > 64) {
      setError('Password must be between 8 and 64 characters long.');
      return;
    }
    const hasLetter = /[a-zA-Z]/.test(newPassword);
    const hasDigit = /[0-9]/.test(newPassword);
    if (!hasLetter || !hasDigit) {
      setError('Password must contain at least one letter and one digit.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    try {
      setLoading(true);
      await api.post('/auth/reset-password', {
        email: trimmedEmail,
        otp: trimmedOtp,
        new_password: newPassword,
      });
      setStep(3); // Success step
    } catch (err) {
      const msg = extractErrorMessage(err, 'Failed to reset password.');
      if (msg.toLowerCase().includes('expired')) {
        setIsExpiredError(true);
        setError(msg);
      } else if (msg.toLowerCase().includes('invalid code')) {
        setError('Invalid code');
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 px-4">
      {/* Brand Header */}
      <div className="mx-auto w-full max-w-md text-center">
        <img
          src="/civicquest-logo.svg"
          alt="CivicQuest"
          className="mx-auto max-w-[260px] sm:max-w-[320px] w-full h-auto mb-4"
        />
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
          Reset Password
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Enter your registered Gmail to receive a password reset code
        </p>
      </div>

      {/* Main Card */}
      <div className="mt-8 mx-auto w-full max-w-md">
        <div className="bg-white py-8 px-6 shadow-sm border border-slate-200 rounded-2xl sm:px-10">
          {/* Error Message */}
          {error && (
            <div className="mb-5 p-3.5 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700 flex flex-col space-y-2">
              <div className="flex items-start space-x-2">
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
                <span className="leading-snug">{error}</span>
              </div>
              {isExpiredError && (
                <div className="pl-7 pt-1">
                  <button
                    type="button"
                    onClick={() => {
                      setStep(1);
                      setError('');
                      setIsExpiredError(false);
                      setOtp('');
                    }}
                    className="text-xs font-semibold text-blue-600 hover:text-blue-700 underline cursor-pointer"
                  >
                    Request a new reset code &rarr;
                  </button>
                </div>
              )}
            </div>
          )}

          {/* STEP 1: Enter email and send code */}
          {step === 1 && (
            <form onSubmit={handleSendResetCode} className="space-y-4">
              <div>
                <label
                  htmlFor="forgot-email"
                  className="block text-sm font-semibold text-slate-800 mb-1.5"
                >
                  Gmail Address
                </label>
                <input
                  id="forgot-email"
                  type="email"
                  required
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="citizen@gmail.com"
                  autoComplete="email"
                  className="w-full px-4 py-2.5 min-h-[44px] text-base rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-sm"
                />
              </div>

              <button
                type="submit"
                id="btn-send-reset-code"
                disabled={loading || resendTimer > 0 || !email}
                className="w-full min-h-[44px] mt-2 flex items-center justify-center py-3 px-4 rounded-xl text-base font-medium text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm cursor-pointer"
              >
                {loading ? (
                  <span className="flex items-center space-x-2">
                    <Loader size="sm" />
                    <span>Sending code...</span>
                  </span>
                ) : resendTimer > 0 ? (
                  `Send reset code in ${resendTimer}s`
                ) : (
                  'Send reset code'
                )}
              </button>

              <p className="mt-3 text-xs text-slate-500 text-center leading-relaxed">
                You can request a reset code only 2 times in 24 hours.
              </p>
            </form>
          )}

          {/* STEP 2: Enter code and new password */}
          {step === 2 && (
            <div className="space-y-5">
              {/* Server Info Notice */}
              <div className="p-3.5 rounded-xl bg-blue-50 border border-blue-200 text-sm text-blue-900 space-y-1">
                <p className="font-medium text-xs leading-relaxed">{serverMessage}</p>
                {remainingRequests !== null && (
                  <p className="text-xs font-semibold text-blue-700">
                    Requests left today: {remainingRequests}
                  </p>
                )}
              </div>

              <div className="flex items-center justify-between px-1">
                <span className="text-xs text-slate-500 truncate max-w-[200px]">
                  Sent to: <span className="font-semibold text-slate-800">{email}</span>
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setStep(1);
                    setError('');
                    setIsExpiredError(false);
                  }}
                  className="text-xs font-semibold text-blue-600 hover:text-blue-700 underline cursor-pointer"
                >
                  Change email
                </button>
              </div>

              <form onSubmit={handleResetPassword} className="space-y-4">
                <div>
                  <label
                    htmlFor="reset-otp"
                    className="block text-sm font-semibold text-slate-800 mb-1.5"
                  >
                    6-Digit Code
                  </label>
                  <input
                    id="reset-otp"
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
                    className="w-full text-center tracking-widest text-2xl font-mono py-2.5 min-h-[44px] rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-sm"
                  />
                </div>

                <div>
                  <label
                    htmlFor="new-password"
                    className="block text-sm font-semibold text-slate-800 mb-1.5"
                  >
                    New password
                  </label>
                  <div className="relative">
                    <input
                      id="new-password"
                      type={showNewPassword ? 'text' : 'password'}
                      required
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="••••••••"
                      autoComplete="new-password"
                      className="w-full pl-4 pr-11 py-2.5 min-h-[44px] text-base rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-sm"
                    />
                    <button
                      type="button"
                      onClick={() => setShowNewPassword((prev) => !prev)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 focus:outline-none cursor-pointer"
                      aria-label={showNewPassword ? 'Hide password' : 'Show password'}
                    >
                      {showNewPassword ? (
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
                  <p className="mt-1.5 text-xs text-slate-500">
                    8 to 64 characters, a letter, a digit
                  </p>
                </div>

                <div>
                  <label
                    htmlFor="confirm-password"
                    className="block text-sm font-semibold text-slate-800 mb-1.5"
                  >
                    Confirm password
                  </label>
                  <div className="relative">
                    <input
                      id="confirm-password"
                      type={showConfirmPassword ? 'text' : 'password'}
                      required
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="••••••••"
                      autoComplete="new-password"
                      className="w-full pl-4 pr-11 py-2.5 min-h-[44px] text-base rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-sm"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword((prev) => !prev)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 focus:outline-none cursor-pointer"
                      aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                    >
                      {showConfirmPassword ? (
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
                  id="btn-submit-reset-password"
                  disabled={loading || otp.length !== 6 || !newPassword || !confirmPassword}
                  className="w-full min-h-[44px] mt-2 flex items-center justify-center py-3 px-4 rounded-xl text-base font-medium text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm cursor-pointer"
                >
                  {loading ? (
                    <span className="flex items-center space-x-2">
                      <Loader size="sm" />
                      <span>Updating password...</span>
                    </span>
                  ) : (
                    'Reset password'
                  )}
                </button>

                <div className="pt-2 flex items-center justify-center">
                  <button
                    type="button"
                    disabled={resendTimer > 0 || loading}
                    onClick={handleSendResetCode}
                    className="text-xs font-semibold text-blue-600 hover:text-blue-700 disabled:text-slate-400 disabled:cursor-not-allowed cursor-pointer"
                  >
                    {resendTimer > 0
                      ? `Resend code in ${resendTimer}s`
                      : 'Resend reset code'}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* STEP 3: Success */}
          {step === 3 && (
            <div className="py-4 text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 mx-auto flex items-center justify-center">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-900">Password updated</h2>
                <p className="text-xs text-slate-500 mt-1">
                  Your password has been reset successfully. Please log in with your new credentials.
                </p>
              </div>
              <Link
                to="/login"
                id="btn-go-to-login"
                className="w-full min-h-[44px] flex items-center justify-center py-3 px-4 rounded-xl text-base font-medium text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 transition-colors shadow-sm cursor-pointer"
              >
                Go to Log in
              </Link>
            </div>
          )}

          {/* Back to login link on steps 1 and 2 */}
          {step !== 3 && (
            <div className="mt-8 pt-6 border-t border-slate-100 text-center">
              <Link
                to="/login"
                className="text-sm font-medium text-slate-600 hover:text-blue-600 transition-colors"
              >
                &larr; Back to login
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
