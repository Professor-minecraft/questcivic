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
      if (role === 'admin') {
        navigate('/admin', { replace: true });
      } else if (role === 'auditor') {
        navigate('/auditor', { replace: true });
      } else {
        navigate('/works', { replace: true });
      }
    }
  }, [token, role, navigate]);

  // Tab state: 'login' or 'signup'
  const [activeTab, setActiveTab] = useState('login');

  // Shared state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isLegacyAccount, setIsLegacyAccount] = useState(false);
  const [successInfo, setSuccessInfo] = useState('');

  // Signup fields
  const [signupStep, setSignupStep] = useState(1); // 1 = form, 2 = otp verification
  const [signupName, setSignupName] = useState('');
  const [signupEmail, setSignupEmail] = useState('');
  const [signupPassword, setSignupPassword] = useState('');
  const [signupConfirmPassword, setSignupConfirmPassword] = useState('');
  const [showSignupPassword, setShowSignupPassword] = useState(false);
  const [showSignupConfirmPassword, setShowSignupConfirmPassword] = useState(false);
  const [termsAgreed, setTermsAgreed] = useState(false);
  const [signupOtp, setSignupOtp] = useState('');
  const [resendTimer, setResendTimer] = useState(0);

  // Login fields
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [showLoginPassword, setShowLoginPassword] = useState(false);

  // Resend code countdown timer
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
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((item) => item.msg || JSON.stringify(item)).join(', ');
    }
    if (typeof data.message === 'string') return data.message;
    return fallback;
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setError('');
    setIsLegacyAccount(false);
    setSuccessInfo('');
  };

  // 1) Create account: Step 1 Submit
  const handleSignupSubmit = async (e) => {
    if (e) e.preventDefault();
    if (loading) return;
    setError('');
    setIsLegacyAccount(false);
    setSuccessInfo('');

    const trimmedName = signupName.trim();
    const trimmedEmail = signupEmail.trim().toLowerCase();

    // Client-side validations before sending
    if (!trimmedName) {
      setError('Please enter your name.');
      return;
    }
    if (trimmedName.length < 2 || trimmedName.length > 60) {
      setError('Name must be between 2 and 60 characters long.');
      return;
    }

    if (!trimmedEmail) {
      setError('Please enter your Gmail address.');
      return;
    }
    if (!validateGmail(trimmedEmail)) {
      setError('Only @gmail.com email addresses are allowed.');
      return;
    }

    if (!signupPassword) {
      setError('Please enter a password.');
      return;
    }
    if (signupPassword.length < 8 || signupPassword.length > 64) {
      setError('Password must be between 8 and 64 characters long.');
      return;
    }
    const hasLetter = /[a-zA-Z]/.test(signupPassword);
    const hasDigit = /[0-9]/.test(signupPassword);
    if (!hasLetter || !hasDigit) {
      setError('Password must contain at least one letter and one digit.');
      return;
    }

    if (signupPassword !== signupConfirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    if (!termsAgreed) {
      setError('You must agree to the data collection terms to proceed.');
      return;
    }

    try {
      setLoading(true);
      await api.post('/auth/signup', {
        name: trimmedName,
        email: trimmedEmail,
        password: signupPassword,
      });
      setSignupStep(2);
      setResendTimer(60);
      setSignupOtp('');
      setSuccessInfo(`We sent a 6-digit verification code to ${trimmedEmail}.`);
    } catch (err) {
      const isLegacy = err.response?.data?.code === 'legacy_account';
      if (isLegacy) {
        setIsLegacyAccount(true);
      }
      const msg = extractErrorMessage(err, 'Failed to create account. Please try again.');
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // 1) Create account: Step 2 Verify OTP
  const handleVerifySignupOtp = async (e) => {
    if (e) e.preventDefault();
    if (loading) return;
    setError('');
    setIsLegacyAccount(false);
    setSuccessInfo('');

    const trimmedOtp = signupOtp.trim();
    if (trimmedOtp.length !== 6 || !/^\d{6}$/.test(trimmedOtp)) {
      setError('Please enter a valid 6-digit verification code.');
      return;
    }

    try {
      setLoading(true);
      const res = await api.post('/auth/signup/verify', {
        email: signupEmail.trim().toLowerCase(),
        otp: trimmedOtp,
      });

      login(res.data.access_token, 'user', res.data.user);
      navigate('/location', { state: { fromLogin: true } });
    } catch (err) {
      const msg = extractErrorMessage(err, 'Invalid or expired verification code.');
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // 1) Create account: Step 2 Resend OTP
  const handleResendSignupOtp = async () => {
    if (loading || resendTimer > 0) return;
    setError('');
    setIsLegacyAccount(false);
    setSuccessInfo('');

    try {
      setLoading(true);
      await api.post('/auth/signup/resend-otp', {
        email: signupEmail.trim().toLowerCase(),
      });
      setResendTimer(60);
      setSuccessInfo('A new 6-digit verification code has been sent to your email.');
    } catch (err) {
      const msg = extractErrorMessage(err, 'Failed to resend verification code.');
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // 2) Log in Submit
  const handleLoginSubmit = async (e) => {
    if (e) e.preventDefault();
    if (loading) return;
    setError('');
    setIsLegacyAccount(false);
    setSuccessInfo('');

    const trimmedEmail = loginEmail.trim().toLowerCase();
    if (!trimmedEmail) {
      setError('Please enter your Gmail address.');
      return;
    }
    if (!validateGmail(trimmedEmail)) {
      setError('Only @gmail.com email addresses are allowed.');
      return;
    }
    if (!loginPassword) {
      setError('Please enter your password.');
      return;
    }

    try {
      setLoading(true);
      const res = await api.post('/auth/login', {
        email: trimmedEmail,
        password: loginPassword,
      });

      login(res.data.access_token, 'user', res.data.user);
      navigate('/location', { state: { fromLogin: true } });
    } catch (err) {
      const msg = extractErrorMessage(err, 'Invalid email or password. Please try again.');
      setError(msg);
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
          className="mx-auto max-w-[260px] sm:max-w-[320px] w-full h-auto"
        />
        <h1 className="sr-only">CivicQuest</h1>
        <p className="mt-3 text-sm text-slate-600">
          Verify MPLADS development projects in your constituency
        </p>
      </div>

      {/* Main Card Container */}
      <div className="mt-8 mx-auto w-full max-w-md">
        <div className="bg-white py-8 px-6 shadow-sm border border-slate-200 rounded-2xl sm:px-10">
          {/* Tabs: Log in / Create account */}
          <div className="flex border-b border-slate-200 mb-6">
            <button
              type="button"
              id="tab-login"
              onClick={() => handleTabChange('login')}
              className={`flex-1 pb-3 text-center text-sm font-semibold border-b-2 transition-colors cursor-pointer ${
                activeTab === 'login'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              Log in
            </button>
            <button
              type="button"
              id="tab-create-account"
              onClick={() => handleTabChange('signup')}
              className={`flex-1 pb-3 text-center text-sm font-semibold border-b-2 transition-colors cursor-pointer ${
                activeTab === 'signup'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              Create account
            </button>
          </div>

          {/* Feedback Alerts */}
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
              {isLegacyAccount && (
                <div className="pl-7 pt-1">
                  <Link
                    to="/forgot-password"
                    className="font-semibold text-blue-600 hover:text-blue-700 underline"
                  >
                    Go to Forgot password &rarr;
                  </Link>
                </div>
              )}
            </div>
          )}

          {successInfo && (
            <div className="mb-5 p-3.5 rounded-xl bg-blue-50 border border-blue-200 text-sm text-blue-800 flex items-start space-x-2">
              <svg
                className="w-5 h-5 text-blue-500 shrink-0 mt-0.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span className="leading-snug">{successInfo}</span>
            </div>
          )}

          {/* TAB 1: CREATE ACCOUNT */}
          {activeTab === 'signup' && (
            <div>
              {signupStep === 1 ? (
                /* Step 1: Account Form */
                <form onSubmit={handleSignupSubmit} className="space-y-4">
                  <div>
                    <label
                      htmlFor="signup-name"
                      className="block text-sm font-semibold text-slate-800 mb-1.5"
                    >
                      Name
                    </label>
                    <input
                      id="signup-name"
                      type="text"
                      required
                      value={signupName}
                      onChange={(e) => setSignupName(e.target.value)}
                      placeholder="Your full name"
                      autoComplete="name"
                      className="w-full px-4 py-2.5 min-h-[44px] text-base rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-sm"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="signup-email"
                      className="block text-sm font-semibold text-slate-800 mb-1.5"
                    >
                      Gmail Address
                    </label>
                    <input
                      id="signup-email"
                      type="email"
                      required
                      value={signupEmail}
                      onChange={(e) => setSignupEmail(e.target.value)}
                      placeholder="citizen@gmail.com"
                      autoComplete="email"
                      className="w-full px-4 py-2.5 min-h-[44px] text-base rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-sm"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="signup-password"
                      className="block text-sm font-semibold text-slate-800 mb-1.5"
                    >
                      Password
                    </label>
                    <div className="relative">
                      <input
                        id="signup-password"
                        type={showSignupPassword ? 'text' : 'password'}
                        required
                        value={signupPassword}
                        onChange={(e) => setSignupPassword(e.target.value)}
                        placeholder="••••••••"
                        autoComplete="new-password"
                        className="w-full pl-4 pr-11 py-2.5 min-h-[44px] text-base rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-sm"
                      />
                      <button
                        type="button"
                        onClick={() => setShowSignupPassword((prev) => !prev)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 focus:outline-none cursor-pointer"
                        aria-label={showSignupPassword ? 'Hide password' : 'Show password'}
                      >
                        {showSignupPassword ? (
                          <svg
                            className="w-5 h-5"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="2"
                              d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18"
                            />
                          </svg>
                        ) : (
                          <svg
                            className="w-5 h-5"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
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
                      htmlFor="signup-confirm-password"
                      className="block text-sm font-semibold text-slate-800 mb-1.5"
                    >
                      Confirm password
                    </label>
                    <div className="relative">
                      <input
                        id="signup-confirm-password"
                        type={showSignupConfirmPassword ? 'text' : 'password'}
                        required
                        value={signupConfirmPassword}
                        onChange={(e) => setSignupConfirmPassword(e.target.value)}
                        placeholder="••••••••"
                        autoComplete="new-password"
                        className="w-full pl-4 pr-11 py-2.5 min-h-[44px] text-base rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-sm"
                      />
                      <button
                        type="button"
                        onClick={() => setShowSignupConfirmPassword((prev) => !prev)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 focus:outline-none cursor-pointer"
                        aria-label={showSignupConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                      >
                        {showSignupConfirmPassword ? (
                          <svg
                            className="w-5 h-5"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="2"
                              d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18"
                            />
                          </svg>
                        ) : (
                          <svg
                            className="w-5 h-5"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
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

                  <div className="pt-1">
                    <label className="flex items-start space-x-2.5 cursor-pointer">
                      <input
                        id="signup-consent"
                        type="checkbox"
                        checked={termsAgreed}
                        onChange={(e) => setTermsAgreed(e.target.checked)}
                        className="mt-1 h-4 w-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500 cursor-pointer shrink-0"
                      />
                      <span className="text-xs text-slate-600 leading-relaxed select-none">
                        I agree that CivicQuest collects my name, email, location and photos to verify public works, and that my full name may be shown on the public leaderboard (I can hide it later in my profile).
                      </span>
                    </label>
                  </div>

                  <button
                    type="submit"
                    disabled={loading || !signupName || !signupEmail || !signupPassword || !signupConfirmPassword || !termsAgreed}
                    className="w-full min-h-[44px] mt-2 flex items-center justify-center py-3 px-4 rounded-xl text-base font-medium text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm cursor-pointer"
                  >
                    {loading ? (
                      <span className="flex items-center space-x-2">
                        <Loader size="sm" />
                        <span>Creating account...</span>
                      </span>
                    ) : (
                      'Continue'
                    )}
                  </button>
                </form>
              ) : (
                /* Step 2: OTP Verification */
                <form onSubmit={handleVerifySignupOtp} className="space-y-5">
                  <div className="flex items-center justify-between p-3 bg-slate-50 border border-slate-100 rounded-xl">
                    <div className="overflow-hidden">
                      <span className="text-xs font-medium uppercase tracking-wider text-slate-500 block">
                        Code sent to
                      </span>
                      <p className="text-sm font-semibold text-slate-900 truncate max-w-[220px]">
                        {signupEmail}
                      </p>
                    </div>
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => {
                        setSignupStep(1);
                        setError('');
                        setIsLegacyAccount(false);
                        setSuccessInfo('');
                        setSignupOtp('');
                      }}
                      className="text-xs font-semibold text-blue-600 hover:text-blue-700 disabled:opacity-50 cursor-pointer underline shrink-0 ml-2"
                    >
                      Change email
                    </button>
                  </div>

                  <div>
                    <label
                      htmlFor="signup-otp-input"
                      className="block text-sm font-semibold text-slate-800 mb-1.5"
                    >
                      6-Digit Verification Code
                    </label>
                    <input
                      id="signup-otp-input"
                      type="text"
                      inputMode="numeric"
                      maxLength={6}
                      required
                      autoFocus
                      value={signupOtp}
                      onChange={(e) => {
                        const val = e.target.value.replace(/\D/g, '');
                        setSignupOtp(val);
                      }}
                      placeholder="123456"
                      className="w-full text-center tracking-widest text-2xl font-mono py-3 min-h-[44px] rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-sm"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={loading || signupOtp.length !== 6}
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

                  <div className="pt-1 flex items-center justify-center">
                    <button
                      type="button"
                      disabled={resendTimer > 0 || loading}
                      onClick={handleResendSignupOtp}
                      className="text-sm font-medium text-blue-600 hover:text-blue-700 disabled:text-slate-400 disabled:cursor-not-allowed cursor-pointer"
                    >
                      {resendTimer > 0
                        ? `Resend code in ${resendTimer}s`
                        : 'Resend code'}
                    </button>
                  </div>
                </form>
              )}
            </div>
          )}

          {/* TAB 2: LOG IN */}
          {activeTab === 'login' && (
            <form onSubmit={handleLoginSubmit} className="space-y-4">
              <div>
                <label
                  htmlFor="login-email"
                  className="block text-sm font-semibold text-slate-800 mb-1.5"
                >
                  Gmail Address
                </label>
                <input
                  id="login-email"
                  type="email"
                  required
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  placeholder="citizen@gmail.com"
                  autoComplete="email"
                  className="w-full px-4 py-2.5 min-h-[44px] text-base rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-sm"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label
                    htmlFor="login-password"
                    className="block text-sm font-semibold text-slate-800"
                  >
                    Password
                  </label>
                  <Link
                    to="/forgot-password"
                    className="text-xs font-semibold text-blue-600 hover:text-blue-700 hover:underline"
                  >
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <input
                    id="login-password"
                    type={showLoginPassword ? 'text' : 'password'}
                    required
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="••••••••"
                    autoComplete="current-password"
                    className="w-full pl-4 pr-11 py-2.5 min-h-[44px] text-base rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-sm"
                  />
                  <button
                    type="button"
                    onClick={() => setShowLoginPassword((prev) => !prev)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 focus:outline-none cursor-pointer"
                    aria-label={showLoginPassword ? 'Hide password' : 'Show password'}
                  >
                    {showLoginPassword ? (
                      <svg
                        className="w-5 h-5"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18"
                        />
                      </svg>
                    ) : (
                      <svg
                        className="w-5 h-5"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
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
                disabled={loading || !loginEmail || !loginPassword}
                className="w-full min-h-[44px] mt-2 flex items-center justify-center py-3 px-4 rounded-xl text-base font-medium text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm cursor-pointer"
              >
                {loading ? (
                  <span className="flex items-center space-x-2">
                    <Loader size="sm" />
                    <span>Logging in...</span>
                  </span>
                ) : (
                  'Log in'
                )}
              </button>
            </form>
          )}

          {/* Footer: Auditor / Admin login link */}
          <div className="mt-8 pt-6 border-t border-slate-100 text-center">
            <Link
              to="/auditor/login"
              className="text-sm font-medium text-slate-600 hover:text-blue-600 transition-colors"
            >
              Auditor / Admin login &rarr;
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
