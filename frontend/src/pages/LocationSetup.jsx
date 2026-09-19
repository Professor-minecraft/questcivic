import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import Loader from '../components/Loader';

export default function LocationSetup() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { user, token, login } = useAuth();

  const fromLogin = Boolean(location.state?.fromLogin);
  const isChangeMode =
    searchParams.get('change') === '1' ||
    searchParams.get('change') === 'true' ||
    Boolean(location.state?.change);

  // User details and lock state from GET /me
  const [currentUser, setCurrentUser] = useState(user);
  const [isLocked, setIsLocked] = useState(false);
  const [lockedUntil, setLockedUntil] = useState(null);

  // Dropdown states
  const [states, setStates] = useState([]);
  const [districts, setDistricts] = useState([]);
  const [constituencies, setConstituencies] = useState([]);

  const [selectedState, setSelectedState] = useState(user?.state || '');
  const [selectedDistrict, setSelectedDistrict] = useState(user?.district || '');
  const [selectedConstituency, setSelectedConstituency] = useState(user?.constituency || '');

  // Geolocation states: 'detecting' | 'resolved' | 'failed'
  const [geoStatus, setGeoStatus] = useState('detecting');
  const [geoMessage, setGeoMessage] = useState('');
  const [detectedLocation, setDetectedLocation] = useState(null);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [loadingDistricts, setLoadingDistricts] = useState(false);
  const [loadingConstituencies, setLoadingConstituencies] = useState(false);

  // Guard against redirect if opened fromLogin or in isChangeMode
  useEffect(() => {
    if (user?.state && user?.district && !isChangeMode && !fromLogin) {
      navigate('/works', { replace: true });
    }
  }, [user, isChangeMode, fromLogin, navigate]);

  const extractErrorMessage = (err, fallback = 'Failed to save location. Please try again.') => {
    const data = err.response?.data;
    if (!data) return fallback;
    if (typeof data.message === 'string') return data.message;
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((item) => item.msg || JSON.stringify(item)).join(', ');
    }
    return fallback;
  };

  const isDateInFuture = (dateStr) => {
    if (!dateStr) return false;
    const todayStr = new Date().toISOString().split('T')[0];
    return dateStr >= todayStr;
  };

  const norm = (s) => (s || '').trim().toLowerCase().replace(/\s+/g, ' ');

  const isSameLocation = (saved, detected) => {
    if (!saved || !detected) return false;
    if (!saved.state || !saved.district || !detected.state || !detected.district) return false;
    const stateSame = norm(saved.state) === norm(detected.state);
    const districtSame = norm(saved.district) === norm(detected.district);
    if (!stateSame || !districtSame) return false;
    if (saved.constituency && detected.constituency) {
      return norm(saved.constituency) === norm(detected.constituency);
    }
    return true;
  };

  // Fetch states list
  const fetchStates = useCallback(async () => {
    try {
      const res = await api.get('/location/options');
      const sList = res.data.states || [];
      setStates(sList);
      return sList;
    } catch (err) {
      console.error('Failed to load states:', err);
      setError('Failed to load location options. Please check connection.');
      return [];
    }
  }, []);

  // Fetch districts for a state
  const fetchDistricts = useCallback(async (stateName) => {
    if (!stateName) {
      setDistricts([]);
      return [];
    }
    try {
      setLoadingDistricts(true);
      const res = await api.get(`/location/options?state=${encodeURIComponent(stateName)}`);
      const dList = res.data.districts || [];
      setDistricts(dList);
      return dList;
    } catch (err) {
      console.error('Failed to load districts:', err);
      return [];
    } finally {
      setLoadingDistricts(false);
    }
  }, []);

  // Fetch constituencies for state & district
  const fetchConstituencies = useCallback(async (stateName, districtName) => {
    if (!stateName || !districtName) {
      setConstituencies([]);
      return [];
    }
    try {
      setLoadingConstituencies(true);
      const res = await api.get(
        `/location/options?state=${encodeURIComponent(stateName)}&district=${encodeURIComponent(districtName)}`
      );
      const cList = res.data.constituencies || [];
      setConstituencies(cList);
      return cList;
    } catch (err) {
      console.error('Failed to load constituencies:', err);
      return [];
    } finally {
      setLoadingConstituencies(false);
    }
  }, []);

  // Main init: Fetch /me for lock status and run GPS resolution
  useEffect(() => {
    let isMounted = true;

    async function init() {
      // 1. Fetch current user and lock status via GET /me
      let latestUser = user;
      try {
        const meRes = await api.get('/me');
        if (!isMounted) return;
        latestUser = meRes.data;
        setCurrentUser(latestUser);

        if (latestUser.location_locked_until && isDateInFuture(latestUser.location_locked_until)) {
          setIsLocked(true);
          setLockedUntil(latestUser.location_locked_until);
        } else {
          setIsLocked(false);
          setLockedUntil(null);
        }

        if (latestUser.state) setSelectedState(latestUser.state);
        if (latestUser.district) setSelectedDistrict(latestUser.district);
        if (latestUser.constituency) setSelectedConstituency(latestUser.constituency);
      } catch (err) {
        console.error('Error fetching /me:', err);
      }

      // 2. Load dropdown states options
      await fetchStates();

      // If change mode and user already has state, pre-load dependent dropdowns
      if (isChangeMode && latestUser?.state) {
        const dList = await fetchDistricts(latestUser.state);
        if (latestUser.district && dList.includes(latestUser.district)) {
          await fetchConstituencies(latestUser.state, latestUser.district);
        }
      }

      // 3. Detect location with browser and call POST /location/resolve
      if (!navigator.geolocation) {
        if (isMounted) {
          setGeoStatus('failed');
          setGeoMessage('Geolocation is not supported by your browser.');
        }
        return;
      }

      navigator.geolocation.getCurrentPosition(
        async (position) => {
          if (!isMounted) return;
          try {
            const { latitude, longitude } = position.coords;
            const res = await api.post('/location/resolve', {
              lat: latitude,
              lng: longitude,
            });

            if (!isMounted) return;
            const resolved = res.data;

            if (resolved.state && resolved.district) {
              const detected = {
                state: resolved.state,
                district: resolved.district,
                constituency:
                  resolved.constituency ||
                  (resolved.constituency_options?.length === 1 ? resolved.constituency_options[0] : ''),
                constituency_options: resolved.constituency_options || [],
              };
              setDetectedLocation(detected);
              setGeoStatus('resolved');

              // If user has no saved location or in change mode, pre-fill dropdowns
              const hasSaved = Boolean(latestUser?.state && latestUser?.district);
              if (!hasSaved || isChangeMode) {
                setSelectedState(detected.state);
                setSelectedDistrict(detected.district);
                await fetchDistricts(detected.state);
                await fetchConstituencies(detected.state, detected.district);
                if (detected.constituency) {
                  setSelectedConstituency(detected.constituency);
                } else if (resolved.constituency_options?.length > 0) {
                  setConstituencies(resolved.constituency_options);
                  if (resolved.constituency_options.length === 1) {
                    setSelectedConstituency(resolved.constituency_options[0]);
                  }
                }
              }
            } else {
              setGeoStatus('failed');
              setGeoMessage('Select your location manually.');
            }
          } catch (err) {
            console.error('Error in /location/resolve:', err);
            if (isMounted) {
              setGeoStatus('failed');
              setGeoMessage('Select your location manually.');
            }
          }
        },
        (geoErr) => {
          console.warn('Geolocation failed or denied:', geoErr.message);
          if (isMounted) {
            setGeoStatus('failed');
            setGeoMessage('Select your location manually.');
          }
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 30000,
        }
      );
    }

    init();

    return () => {
      isMounted = false;
    };
  }, [fetchStates, fetchDistricts, fetchConstituencies, isChangeMode, user]);

  // Dropdown event handlers
  const handleStateChange = async (e) => {
    const newState = e.target.value;
    setSelectedState(newState);
    setSelectedDistrict('');
    setSelectedConstituency('');
    setConstituencies([]);

    if (newState) {
      await fetchDistricts(newState);
    } else {
      setDistricts([]);
    }
  };

  const handleDistrictChange = async (e) => {
    const newDistrict = e.target.value;
    setSelectedDistrict(newDistrict);
    setSelectedConstituency('');

    if (selectedState && newDistrict) {
      await fetchConstituencies(selectedState, newDistrict);
    } else {
      setConstituencies([]);
    }
  };

  // Submit dropdown selection
  const handleConfirm = async (e) => {
    if (e) e.preventDefault();
    if (submitting || isLocked) return;
    setError('');

    if (!selectedState || !selectedDistrict) {
      setError('Please select both State and District.');
      return;
    }

    try {
      setSubmitting(true);
      const res = await api.put('/me/location', {
        state: selectedState,
        district: selectedDistrict,
        constituency: selectedConstituency || null,
      });

      login(token, 'user', res.data);
      navigate('/works');
    } catch (err) {
      const msg = extractErrorMessage(err, 'Failed to save location. Please try again.');
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  // "Use detected location" button action
  const handleUseDetectedLocation = async () => {
    if (submitting || isLocked || !detectedLocation) return;
    setError('');

    try {
      setSubmitting(true);
      const res = await api.put('/me/location', {
        state: detectedLocation.state,
        district: detectedLocation.district,
        constituency: detectedLocation.constituency || null,
      });

      login(token, 'user', res.data);
      navigate('/works');
    } catch (err) {
      const msg = extractErrorMessage(err, 'Failed to update to detected location.');
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const hasSavedLocation = Boolean(currentUser?.state && currentUser?.district);
  const isDetectedSame = hasSavedLocation && detectedLocation && isSameLocation(currentUser, detectedLocation);
  const isDetectedDifferent = hasSavedLocation && detectedLocation && !isDetectedSame;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-10 px-4">
      {/* Header / Brand */}
      <div className="mx-auto w-full max-w-md text-center">
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
              d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
            />
          </svg>
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
          {isChangeMode ? 'Change Your Location' : 'Location Setup'}
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          MPLADS works are filtered by your parliamentary constituency and district.
        </p>
      </div>

      {/* Main Container */}
      <div className="mt-8 mx-auto w-full max-w-md">
        <div className="bg-white py-8 px-6 shadow-sm border border-slate-200 rounded-2xl sm:px-10">
          {/* Locked Notice */}
          {isLocked && lockedUntil && (
            <div className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-200 text-sm text-amber-800 flex items-start space-x-2.5">
              <svg
                className="w-5 h-5 text-amber-600 shrink-0 mt-0.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                />
              </svg>
              <div>
                <p className="font-semibold">Location is locked until {lockedUntil}</p>
                <p className="text-xs text-amber-700 mt-0.5">
                  You cannot change your constituency or district while the lock is active.
                </p>
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mb-6 p-3.5 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700 flex items-start space-x-2">
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
          )}

          {/* Detecting State */}
          {geoStatus === 'detecting' && (
            <div className="py-6 flex flex-col items-center justify-center text-center space-y-3">
              <Loader size="md" color="text-blue-600" />
              <p className="text-sm font-semibold text-slate-800">Detecting location via GPS...</p>
              <p className="text-xs text-slate-500 max-w-xs">
                Please allow browser location access if prompted.
              </p>
            </div>
          )}

          {/* CASE 1: Returning user from login whose detected location is the SAME */}
          {geoStatus !== 'detecting' && fromLogin && hasSavedLocation && isDetectedSame && (
            <div className="space-y-6">
              <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 flex items-start space-x-3">
                <svg
                  className="w-6 h-6 text-emerald-600 shrink-0 mt-0.5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <div>
                  <h3 className="text-base font-bold text-emerald-900">Location confirmed</h3>
                  <p className="text-xs text-emerald-700 mt-0.5">
                    Your current location matches your saved constituency.
                  </p>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Saved Location
                </span>
                <p className="text-base font-bold text-slate-900 mt-1">
                  {currentUser.district}, {currentUser.state}
                </p>
                {currentUser.constituency && (
                  <p className="text-sm text-slate-600 mt-0.5">
                    Constituency: <span className="font-medium text-slate-800">{currentUser.constituency}</span>
                  </p>
                )}
              </div>

              <button
                type="button"
                id="btn-continue-works"
                onClick={() => navigate('/works')}
                className="w-full min-h-[44px] flex items-center justify-center py-3 px-4 rounded-xl text-base font-medium text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 transition-colors shadow-sm cursor-pointer"
              >
                Continue to Works &rarr;
              </button>
            </div>
          )}

          {/* CASE 2: Returning user from login whose detected location is DIFFERENT */}
          {geoStatus !== 'detecting' && fromLogin && hasSavedLocation && isDetectedDifferent && (
            <div className="space-y-6">
              <div className="p-3.5 rounded-xl bg-blue-50 border border-blue-200 text-sm text-blue-900">
                <p className="font-semibold">Different location detected</p>
                <p className="text-xs text-blue-700 mt-0.5">
                  Your detected GPS position differs from your saved location.
                </p>
              </div>

              <div className="space-y-3">
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block">
                    Saved
                  </span>
                  <p className="text-sm font-bold text-slate-800 mt-0.5">
                    {currentUser.district}, {currentUser.state}
                    {currentUser.constituency ? ` (${currentUser.constituency})` : ''}
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-blue-50/50 border border-blue-200">
                  <span className="text-xs font-semibold uppercase tracking-wider text-blue-600 block">
                    Detected
                  </span>
                  <p className="text-sm font-bold text-blue-900 mt-0.5">
                    {detectedLocation.district}, {detectedLocation.state}
                    {detectedLocation.constituency ? ` (${detectedLocation.constituency})` : ''}
                  </p>
                </div>
              </div>

              <div className="space-y-3 pt-2">
                {/* Default button: Keep saved location */}
                <button
                  type="button"
                  id="btn-keep-saved-location"
                  onClick={() => navigate('/works')}
                  className="w-full min-h-[44px] flex items-center justify-center py-3 px-4 rounded-xl text-base font-medium text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 transition-colors shadow-sm cursor-pointer"
                >
                  Keep saved location
                </button>

                {/* Secondary button: Use detected location */}
                <button
                  type="button"
                  id="btn-use-detected-location"
                  disabled={submitting || isLocked}
                  onClick={handleUseDetectedLocation}
                  className="w-full min-h-[44px] flex items-center justify-center py-3 px-4 rounded-xl text-base font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 active:bg-slate-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
                >
                  {submitting ? (
                    <span className="flex items-center space-x-2">
                      <Loader size="sm" color="text-slate-700" />
                      <span>Updating location...</span>
                    </span>
                  ) : (
                    'Use detected location'
                  )}
                </button>
              </div>
            </div>
          )}

          {/* CASE 3: Returning user from login whose browser location DENIED / FAILED */}
          {geoStatus !== 'detecting' && fromLogin && hasSavedLocation && geoStatus === 'failed' && (
            <div className="space-y-6">
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Saved Location
                </span>
                <p className="text-base font-bold text-slate-900 mt-1">
                  {currentUser.district}, {currentUser.state}
                </p>
                {currentUser.constituency && (
                  <p className="text-sm text-slate-600 mt-0.5">
                    Constituency: <span className="font-medium text-slate-800">{currentUser.constituency}</span>
                  </p>
                )}
                <p className="text-xs text-slate-500 mt-2">
                  Could not verify GPS location. You can proceed with your saved location.
                </p>
              </div>

              <button
                type="button"
                id="btn-continue-saved-works"
                onClick={() => navigate('/works')}
                className="w-full min-h-[44px] flex items-center justify-center py-3 px-4 rounded-xl text-base font-medium text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 transition-colors shadow-sm cursor-pointer"
              >
                Continue to Works &rarr;
              </button>

              {/* Show dropdowns only if not locked */}
              {!isLocked && (
                <div className="pt-4 border-t border-slate-100">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
                    Or select another location manually
                  </h3>
                  {/* Render the dropdowns form */}
                  <form onSubmit={handleConfirm} className="space-y-4">
                    <div>
                      <label htmlFor="state-select-fallback" className="block text-xs font-semibold text-slate-700 mb-1">
                        State
                      </label>
                      <select
                        id="state-select-fallback"
                        required
                        value={selectedState}
                        onChange={handleStateChange}
                        disabled={isLocked}
                        className="w-full px-3 py-2.5 min-h-[44px] text-sm rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 disabled:bg-slate-100 disabled:cursor-not-allowed"
                      >
                        <option value="">-- Select State --</option>
                        {states.map((st) => (
                          <option key={st} value={st}>
                            {st}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label htmlFor="district-select-fallback" className="block text-xs font-semibold text-slate-700 mb-1">
                        District
                      </label>
                      <select
                        id="district-select-fallback"
                        required
                        disabled={isLocked || !selectedState || loadingDistricts}
                        value={selectedDistrict}
                        onChange={handleDistrictChange}
                        className="w-full px-3 py-2.5 min-h-[44px] text-sm rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 disabled:bg-slate-100 disabled:cursor-not-allowed"
                      >
                        <option value="">
                          {!selectedState ? '-- Select State first --' : '-- Select District --'}
                        </option>
                        {districts.map((dst) => (
                          <option key={dst} value={dst}>
                            {dst}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label htmlFor="constituency-select-fallback" className="block text-xs font-semibold text-slate-700 mb-1">
                        Constituency (Optional)
                      </label>
                      <select
                        id="constituency-select-fallback"
                        disabled={isLocked || !selectedDistrict || loadingConstituencies}
                        value={selectedConstituency}
                        onChange={(e) => setSelectedConstituency(e.target.value)}
                        className="w-full px-3 py-2.5 min-h-[44px] text-sm rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 disabled:bg-slate-100 disabled:cursor-not-allowed"
                      >
                        <option value="">
                          {!selectedDistrict ? '-- Select District first --' : '-- Select Constituency (Optional) --'}
                        </option>
                        {constituencies.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>

                    <button
                      type="submit"
                      disabled={submitting || isLocked || !selectedState || !selectedDistrict}
                      className="w-full min-h-[44px] flex items-center justify-center py-2.5 px-4 rounded-xl text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 active:bg-slate-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
                    >
                      {submitting ? 'Saving...' : 'Update Location'}
                    </button>
                  </form>
                </div>
              )}
            </div>
          )}

          {/* CASE 4: User has NO saved location OR accessed via "Change location" in header */}
          {geoStatus !== 'detecting' && (!hasSavedLocation || isChangeMode) && (
            <div>
              {/* Geolocation status header banner */}
              {geoStatus === 'resolved' && (
                <div className="mb-5 p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center space-x-2.5 text-emerald-900 text-sm">
                  <svg className="w-5 h-5 text-emerald-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                  </svg>
                  <div>
                    <p className="font-semibold">Location detected automatically</p>
                    <p className="text-xs text-emerald-700">Pre-filled below. Adjust if necessary.</p>
                  </div>
                </div>
              )}

              {geoStatus === 'failed' && (
                <div className="mb-5 p-3 rounded-xl bg-slate-100 border border-slate-200 text-xs text-slate-600 flex items-center space-x-2">
                  <svg className="w-4 h-4 text-slate-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span>{geoMessage || 'Select your location manually'}</span>
                </div>
              )}

              <form onSubmit={handleConfirm} className="space-y-4">
                {/* State Dropdown */}
                <div>
                  <label htmlFor="state-select" className="block text-sm font-semibold text-slate-800 mb-1.5">
                    State <span className="text-red-500">*</span>
                  </label>
                  <select
                    id="state-select"
                    required
                    disabled={isLocked}
                    value={selectedState}
                    onChange={handleStateChange}
                    className="w-full px-4 py-2.5 min-h-[44px] text-base rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 transition-all shadow-sm disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed"
                  >
                    <option value="">-- Select State --</option>
                    {states.map((st) => (
                      <option key={st} value={st}>
                        {st}
                      </option>
                    ))}
                  </select>
                </div>

                {/* District Dropdown */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label htmlFor="district-select" className="block text-sm font-semibold text-slate-800">
                      District <span className="text-red-500">*</span>
                    </label>
                    {loadingDistricts && (
                      <span className="text-xs text-blue-600 flex items-center space-x-1">
                        <Loader size="sm" />
                        <span>Loading...</span>
                      </span>
                    )}
                  </div>
                  <select
                    id="district-select"
                    required
                    disabled={isLocked || !selectedState || loadingDistricts}
                    value={selectedDistrict}
                    onChange={handleDistrictChange}
                    className="w-full px-4 py-2.5 min-h-[44px] text-base rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 transition-all shadow-sm disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed"
                  >
                    <option value="">
                      {!selectedState ? '-- Select State first --' : '-- Select District --'}
                    </option>
                    {districts.map((dst) => (
                      <option key={dst} value={dst}>
                        {dst}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Constituency Dropdown */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label htmlFor="constituency-select" className="block text-sm font-semibold text-slate-800">
                      Constituency (Lok Sabha)
                    </label>
                    {loadingConstituencies && (
                      <span className="text-xs text-blue-600 flex items-center space-x-1">
                        <Loader size="sm" />
                        <span>Loading...</span>
                      </span>
                    )}
                  </div>
                  <select
                    id="constituency-select"
                    disabled={isLocked || !selectedDistrict || loadingConstituencies}
                    value={selectedConstituency}
                    onChange={(e) => setSelectedConstituency(e.target.value)}
                    className="w-full px-4 py-2.5 min-h-[44px] text-base rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 transition-all shadow-sm disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed"
                  >
                    <option value="">
                      {!selectedDistrict ? '-- Select District first --' : '-- Select Constituency (Optional) --'}
                    </option>
                    {constituencies.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                  <p className="mt-1.5 text-xs text-slate-500">
                    Works nominated by Lok Sabha MPs match your constituency. Rajya Sabha works match your district.
                  </p>
                </div>

                {/* Submit button */}
                <button
                  type="submit"
                  disabled={submitting || isLocked || !selectedState || !selectedDistrict}
                  className="w-full min-h-[44px] mt-4 flex items-center justify-center py-3 px-4 rounded-xl text-base font-medium text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm cursor-pointer"
                >
                  {submitting ? (
                    <span className="flex items-center space-x-2">
                      <Loader size="sm" />
                      <span>Saving location...</span>
                    </span>
                  ) : (
                    'Confirm Location'
                  )}
                </button>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
