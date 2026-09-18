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

  const isChangeMode =
    searchParams.get('change') === '1' ||
    searchParams.get('change') === 'true' ||
    Boolean(location.state?.change);

  // If user already has a location and didn't explicitly request to change it, redirect to /works
  useEffect(() => {
    if (user?.state && user?.district && !isChangeMode) {
      navigate('/works', { replace: true });
    }
  }, [user, isChangeMode, navigate]);

  const [states, setStates] = useState([]);
  const [districts, setDistricts] = useState([]);
  const [constituencies, setConstituencies] = useState([]);

  const [selectedState, setSelectedState] = useState(user?.state || '');
  const [selectedDistrict, setSelectedDistrict] = useState(user?.district || '');
  const [selectedConstituency, setSelectedConstituency] = useState(user?.constituency || '');

  const [geoStatus, setGeoStatus] = useState('detecting'); // 'detecting' | 'resolved' | 'manual'
  const [geoMessage, setGeoMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [loadingDistricts, setLoadingDistricts] = useState(false);
  const [loadingConstituencies, setLoadingConstituencies] = useState(false);

  // Fetch states list
  const fetchStates = useCallback(async () => {
    try {
      const res = await api.get('/location/options');
      setStates(res.data.states || []);
      return res.data.states || [];
    } catch (err) {
      console.error('Failed to load states:', err);
      setError('Failed to load location options. Please refresh or check connection.');
      return [];
    }
  }, []);

  // Fetch districts for a given state
  const fetchDistricts = useCallback(async (stateName) => {
    if (!stateName) {
      setDistricts([]);
      return [];
    }
    try {
      setLoadingDistricts(true);
      const res = await api.get(`/location/options?state=${encodeURIComponent(stateName)}`);
      setDistricts(res.data.districts || []);
      return res.data.districts || [];
    } catch (err) {
      console.error('Failed to load districts:', err);
      return [];
    } finally {
      setLoadingDistricts(false);
    }
  }, []);

  // Fetch constituencies for a given state & district
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
      setConstituencies(res.data.constituencies || []);
      return res.data.constituencies || [];
    } catch (err) {
      console.error('Failed to load constituencies:', err);
      return [];
    } finally {
      setLoadingConstituencies(false);
    }
  }, []);

  // GPS Resolution Flow on mount
  useEffect(() => {
    let isMounted = true;

    async function initLocation() {
      // Load initial states list
      await fetchStates();

      // If already in change mode and user has existing location, load dependent dropdowns
      if (isChangeMode && user?.state) {
        setGeoStatus('manual');
        const dList = await fetchDistricts(user.state);
        if (user.district && dList.includes(user.district)) {
          await fetchConstituencies(user.state, user.district);
        }
        return;
      }

      // Check geolocation support
      if (!navigator.geolocation) {
        if (isMounted) {
          setGeoStatus('manual');
          setGeoMessage('Select your location manually');
        }
        return;
      }

      // Prompt for geolocation
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
              setSelectedState(resolved.state);
              setSelectedDistrict(resolved.district);

              // Populate districts for resolved state
              await fetchDistricts(resolved.state);

              // Populate constituencies
              const cList = await fetchConstituencies(resolved.state, resolved.district);

              if (resolved.constituency) {
                setSelectedConstituency(resolved.constituency);
              } else if (resolved.constituency_options?.length > 0) {
                // If options suggested, choose the first or leave for user
                setConstituencies(resolved.constituency_options);
                if (resolved.constituency_options.length === 1) {
                  setSelectedConstituency(resolved.constituency_options[0]);
                }
              }

              setGeoStatus('resolved');
              setGeoMessage('Location detected automatically via GPS');
            } else {
              setGeoStatus('manual');
              setGeoMessage('Select your location manually');
            }
          } catch (err) {
            console.error('Error resolving GPS location:', err);
            if (isMounted) {
              setGeoStatus('manual');
              setGeoMessage('Select your location manually');
            }
          }
        },
        (geoError) => {
          console.warn('Geolocation permission denied or timed out:', geoError.message);
          if (isMounted) {
            setGeoStatus('manual');
            setGeoMessage('Select your location manually');
          }
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 30000,
        }
      );
    }

    initLocation();

    return () => {
      isMounted = false;
    };
  }, [fetchStates, fetchDistricts, fetchConstituencies, isChangeMode, user]);

  // Handle State Change
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

  // Handle District Change
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

  // Handle Confirm Submission
  const handleConfirm = async (e) => {
    e.preventDefault();
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

      // Update user in context & localStorage
      login(token, 'user', res.data);

      // Navigate to works list
      navigate('/works');
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        'Failed to save location. Please try again.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-10 px-4 sm:px-6 lg:px-8">
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
          {isChangeMode ? 'Change Your Location' : 'Select Your Location'}
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          MPLADS works are filtered by your parliamentary constituency and district.
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-lg">
        <div className="bg-white py-8 px-6 shadow-sm border border-slate-200 rounded-2xl sm:px-10">
          {/* GPS Status Indicator */}
          {geoStatus === 'detecting' && (
            <div className="mb-6 p-4 rounded-xl bg-blue-50 border border-blue-100 flex items-center space-x-3">
              <Loader size="sm" />
              <div className="text-sm text-blue-900 font-medium">
                Detecting your location via GPS...
              </div>
            </div>
          )}

          {geoStatus === 'resolved' && (
            <div className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center space-x-3 text-emerald-900 text-sm">
              <svg
                className="w-5 h-5 text-emerald-600 shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M5 13l4 4L19 7"
                />
              </svg>
              <div>
                <p className="font-semibold">Location detected automatically</p>
                <p className="text-xs text-emerald-700">
                  Values are pre-filled below. You can adjust them if needed.
                </p>
              </div>
            </div>
          )}

          {geoStatus === 'manual' && (
            <div className="mb-6 p-3.5 rounded-xl bg-slate-100 border border-slate-200 text-sm text-slate-700 flex items-center space-x-2.5">
              <svg
                className="w-5 h-5 text-slate-500 shrink-0"
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
              <span className="font-medium">
                {geoMessage || 'Select your location manually'}
              </span>
            </div>
          )}

          {/* Form Error Alert */}
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
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleConfirm} className="space-y-5">
            {/* State Selection */}
            <div>
              <label
                htmlFor="state-select"
                className="block text-sm font-semibold text-slate-800 mb-1.5"
              >
                State <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <select
                  id="state-select"
                  required
                  value={selectedState}
                  onChange={handleStateChange}
                  className="w-full px-4 py-3 min-h-[44px] text-base rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-sm"
                >
                  <option value="">-- Select State --</option>
                  {states.map((st) => (
                    <option key={st} value={st}>
                      {st}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* District Selection */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label
                  htmlFor="district-select"
                  className="block text-sm font-semibold text-slate-800"
                >
                  District <span className="text-red-500">*</span>
                </label>
                {loadingDistricts && (
                  <span className="text-xs text-blue-600 flex items-center space-x-1">
                    <Loader size="sm" />
                    <span>Loading...</span>
                  </span>
                )}
              </div>
              <div className="relative">
                <select
                  id="district-select"
                  required
                  disabled={!selectedState || loadingDistricts}
                  value={selectedDistrict}
                  onChange={handleDistrictChange}
                  className="w-full px-4 py-3 min-h-[44px] text-base rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-sm disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed"
                >
                  <option value="">
                    {!selectedState
                      ? '-- Select State first --'
                      : '-- Select District --'}
                  </option>
                  {districts.map((dst) => (
                    <option key={dst} value={dst}>
                      {dst}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Constituency Selection */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label
                  htmlFor="constituency-select"
                  className="block text-sm font-semibold text-slate-800"
                >
                  Constituency (Lok Sabha)
                </label>
                {loadingConstituencies && (
                  <span className="text-xs text-blue-600 flex items-center space-x-1">
                    <Loader size="sm" />
                    <span>Loading...</span>
                  </span>
                )}
              </div>
              <div className="relative">
                <select
                  id="constituency-select"
                  disabled={!selectedDistrict || loadingConstituencies}
                  value={selectedConstituency}
                  onChange={(e) => setSelectedConstituency(e.target.value)}
                  className="w-full px-4 py-3 min-h-[44px] text-base rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all shadow-sm disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed"
                >
                  <option value="">
                    {!selectedDistrict
                      ? '-- Select District first --'
                      : '-- Select Constituency (Optional) --'}
                  </option>
                  {constituencies.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <p className="mt-1.5 text-xs text-slate-500">
                Works nominated by Lok Sabha MPs match your constituency. Rajya Sabha works match your district.
              </p>
            </div>

            {/* Submit / Confirm Button */}
            <button
              type="submit"
              disabled={submitting || !selectedState || !selectedDistrict}
              className="w-full min-h-[44px] flex items-center justify-center py-3 px-4 rounded-xl text-base font-medium text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm cursor-pointer mt-6"
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
      </div>
    </div>
  );
}
