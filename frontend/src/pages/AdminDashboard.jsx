import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import Loader from '../components/Loader';
import AdminSubmissionCard from '../components/AdminSubmissionCard';
import AdminComplaintCard from '../components/AdminComplaintCard';
import AuditorSummaryCard from '../components/AuditorSummaryCard';
import ReviewActivityList from '../components/ReviewActivityList';

function formatDate(dateString) {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return String(dateString);
    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return String(dateString);
  }
}

function formatDateTime(dateString) {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return String(dateString);
    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return String(dateString);
  }
}

function getMaxDob() {
  const today = new Date();
  const year = today.getFullYear() - 18;
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function isAge18OrOlder(dobString) {
  if (!dobString) return false;
  const dob = new Date(dobString);
  if (isNaN(dob.getTime())) return false;
  const today = new Date();
  let age = today.getFullYear() - dob.getFullYear();
  const m = today.getMonth() - dob.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) {
    age--;
  }
  return age >= 18;
}

function isValidGmail(emailString) {
  const s = emailString.trim().toLowerCase();
  const suffix = '@gmail.com';
  if (!s.endsWith(suffix)) return false;
  const prefix = s.slice(0, -suffix.length);
  return prefix.length > 0 && !prefix.includes('@');
}

export default function AdminDashboard() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  // Active section tab: 'users' | 'auditors' | 'create_auditor' | 'photos' | 'complaints'
  const [activeTab, setActiveTab] = useState('users');

  // Selected item for detail view
  const [selectedUser, setSelectedUser] = useState(null);
  const [selectedAuditor, setSelectedAuditor] = useState(null);

  // ---------------------------------------------------------------------------
  // USERS STATE
  // ---------------------------------------------------------------------------
  const [users, setUsers] = useState([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [usersPage, setUsersPage] = useState(1);
  const [searchInput, setSearchInput] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [loadingMoreUsers, setLoadingMoreUsers] = useState(false);
  const [usersError, setUsersError] = useState('');

  // User detail states (Submissions & Complaints)
  const [userSubmissions, setUserSubmissions] = useState([]);
  const [userComplaints, setUserComplaints] = useState([]);
  const [loadingUserDetails, setLoadingUserDetails] = useState(false);
  const [userDetailsError, setUserDetailsError] = useState('');

  // ---------------------------------------------------------------------------
  // AUDITORS STATE
  // ---------------------------------------------------------------------------
  const [auditors, setAuditors] = useState([]);
  const [loadingAuditors, setLoadingAuditors] = useState(false);
  const [auditorsError, setAuditorsError] = useState('');

  // Auditor action state (Status update & Resend invite)
  const [actionLoadingId, setActionLoadingId] = useState(null);
  const [auditorActionMessage, setAuditorActionMessage] = useState(null);

  // Auditor detail state
  const [auditorReviewLogs, setAuditorReviewLogs] = useState([]);
  const [loadingAuditorLogs, setLoadingAuditorLogs] = useState(false);
  const [auditorLogsError, setAuditorLogsError] = useState('');

  // ---------------------------------------------------------------------------
  // CREATE AUDITOR STATE
  // ---------------------------------------------------------------------------
  const [createForm, setCreateForm] = useState({
    name: '',
    dob: '',
    email: '',
    state: '',
    district: '',
    constituency: '',
    status: 'active',
  });
  const [locationStates, setLocationStates] = useState([]);
  const [locationDistricts, setLocationDistricts] = useState([]);
  const [locationConstituencies, setLocationConstituencies] = useState([]);
  const [loadingLocations, setLoadingLocations] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState('');
  const [createSuccessMessage, setCreateSuccessMessage] = useState('');

  // ---------------------------------------------------------------------------
  // PHOTO CHECKS (SUBMISSIONS) STATE
  // ---------------------------------------------------------------------------
  const [photoTab, setPhotoTab] = useState('all'); // 'all' | 'pending' | 'approved' | 'rejected'
  const [adminSubmissions, setAdminSubmissions] = useState([]);
  const [submissionsTotal, setSubmissionsTotal] = useState(0);
  const [submissionsPage, setSubmissionsPage] = useState(1);
  const [loadingSubmissions, setLoadingSubmissions] = useState(false);
  const [loadingMoreSubmissions, setLoadingMoreSubmissions] = useState(false);
  const [submissionsError, setSubmissionsError] = useState('');

  // ---------------------------------------------------------------------------
  // COMPLAINTS STATE
  // ---------------------------------------------------------------------------
  const [complaintsTab, setComplaintsTab] = useState('all'); // 'all' | 'pending' | 'accepted' | 'rejected'
  const [adminComplaints, setAdminComplaints] = useState([]);
  const [complaintsTotal, setComplaintsTotal] = useState(0);
  const [complaintsPage, setComplaintsPage] = useState(1);
  const [loadingComplaints, setLoadingComplaints] = useState(false);
  const [loadingMoreComplaints, setLoadingMoreComplaints] = useState(false);
  const [complaintsError, setComplaintsError] = useState('');

  const abortControllerRef = useRef(null);

  const handleLogout = () => {
    logout();
    navigate('/auditor/login');
  };

  // Debounce search input
  useEffect(() => {
    const handler = setTimeout(() => {
      setSearchTerm(searchInput.trim());
    }, 350);
    return () => clearTimeout(handler);
  }, [searchInput]);

  // Reset detail selections when switching tabs
  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    setSelectedUser(null);
    setSelectedAuditor(null);
    setAuditorActionMessage(null);
  };

  // ---------------------------------------------------------------------------
  // Fetch Users
  // ---------------------------------------------------------------------------
  const fetchUsers = useCallback(async (pageToFetch = 1, query = '', isLoadMore = false) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      if (isLoadMore) {
        setLoadingMoreUsers(true);
      } else {
        setLoadingUsers(true);
        setUsersError('');
      }

      const res = await api.get('/admin/users', {
        params: {
          search: query || undefined,
          page: pageToFetch,
          page_size: 20,
        },
        signal: controller.signal,
      });

      const items = res.data.items || [];
      const total = res.data.total ?? items.length;

      if (isLoadMore) {
        setUsers((prev) => [...prev, ...items]);
      } else {
        setUsers(items);
      }
      setUsersTotal(total);
      setUsersPage(pageToFetch);
    } catch (err) {
      if (err.name !== 'CanceledError' && err.code !== 'ERR_CANCELED') {
        setUsersError(err.response?.data?.detail || 'Failed to load users.');
      }
    } finally {
      setLoadingUsers(false);
      setLoadingMoreUsers(false);
    }
  }, []);

  // Trigger users fetch on tab switch to 'users' or when search term changes
  useEffect(() => {
    if (activeTab === 'users' && !selectedUser) {
      fetchUsers(1, searchTerm, false);
    }
  }, [activeTab, searchTerm, selectedUser, fetchUsers]);

  const handleLoadMoreUsers = () => {
    if (!loadingMoreUsers && users.length < usersTotal) {
      fetchUsers(usersPage + 1, searchTerm, true);
    }
  };

  // ---------------------------------------------------------------------------
  // Fetch User Details (Submissions & Complaints)
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!selectedUser) return;

    let isMounted = true;
    async function loadUserData() {
      try {
        setLoadingUserDetails(true);
        setUserDetailsError('');
        setUserSubmissions([]);
        setUserComplaints([]);

        const [subsRes, compsRes] = await Promise.all([
          api.get('/admin/submissions', { params: { user_id: selectedUser.id, page_size: 50 } }),
          api.get('/admin/complaints', { params: { user_id: selectedUser.id, page_size: 50 } }),
        ]);

        if (isMounted) {
          setUserSubmissions(subsRes.data.items || []);
          setUserComplaints(compsRes.data.items || []);
        }
      } catch (err) {
        if (isMounted) {
          setUserDetailsError(err.response?.data?.detail || 'Failed to load user activity records.');
        }
      } finally {
        if (isMounted) {
          setLoadingUserDetails(false);
        }
      }
    }

    loadUserData();
    return () => {
      isMounted = false;
    };
  }, [selectedUser]);

  // ---------------------------------------------------------------------------
  // Fetch Auditors
  // ---------------------------------------------------------------------------
  const fetchAuditors = useCallback(async () => {
    try {
      setLoadingAuditors(true);
      setAuditorsError('');
      const res = await api.get('/admin/auditors', {
        params: { page: 1, page_size: 50 },
      });
      setAuditors(res.data.items || []);
    } catch (err) {
      setAuditorsError(err.response?.data?.detail || 'Failed to load auditors.');
    } finally {
      setLoadingAuditors(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'auditors' && !selectedAuditor) {
      fetchAuditors();
    }
  }, [activeTab, selectedAuditor, fetchAuditors]);

  // ---------------------------------------------------------------------------
  // Fetch Auditor Details (Logs for DB auditors)
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!selectedAuditor) return;

    // Built-in auditor has no detail call (id is null)
    if (selectedAuditor.builtin || selectedAuditor.id == null) {
      setAuditorReviewLogs([]);
      return;
    }

    let isMounted = true;
    async function loadAuditorLogs() {
      try {
        setLoadingAuditorLogs(true);
        setAuditorLogsError('');
        const res = await api.get(`/admin/auditors/${selectedAuditor.id}`);
        if (isMounted) {
          setAuditorReviewLogs(res.data.review_logs || []);
        }
      } catch (err) {
        if (isMounted) {
          setAuditorLogsError(err.response?.data?.detail || 'Failed to load auditor review logs.');
        }
      } finally {
        if (isMounted) {
          setLoadingAuditorLogs(false);
        }
      }
    }

    loadAuditorLogs();
    return () => {
      isMounted = false;
    };
  }, [selectedAuditor]);

  // ---------------------------------------------------------------------------
  // Auditor Actions: Status Toggle & Resend Invite
  // ---------------------------------------------------------------------------
  const handleToggleAuditorStatus = async (auditor, e) => {
    if (e) e.stopPropagation();
    if (auditor.builtin || auditor.id == null || actionLoadingId) return;

    const nextStatus = auditor.status === 'active' ? 'disabled' : 'active';
    const actionWord = nextStatus === 'disabled' ? 'disable' : 'activate';
    if (!window.confirm(`Are you sure you want to ${actionWord} auditor "${auditor.name}"?`)) {
      return;
    }

    try {
      setActionLoadingId(auditor.id);
      setAuditorActionMessage(null);
      const res = await api.patch(`/admin/auditors/${auditor.id}/status`, {
        status: nextStatus,
      });

      const updatedStatus = res.data.status;
      setAuditors((prev) =>
        prev.map((a) => (a.id === auditor.id ? { ...a, status: updatedStatus } : a))
      );
      if (selectedAuditor && selectedAuditor.id === auditor.id) {
        setSelectedAuditor((prev) => ({ ...prev, status: updatedStatus }));
      }
      setAuditorActionMessage({
        id: auditor.id,
        type: 'success',
        text: `Auditor "${auditor.name}" status updated to ${updatedStatus}.`,
      });
    } catch (err) {
      setAuditorActionMessage({
        id: auditor.id,
        type: 'error',
        text: err.response?.data?.detail || `Failed to update status for "${auditor.name}".`,
      });
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleResendInvite = async (auditor, e) => {
    if (e) e.stopPropagation();
    if (auditor.builtin || auditor.id == null || actionLoadingId) return;

    try {
      setActionLoadingId(auditor.id);
      setAuditorActionMessage(null);
      const res = await api.post(`/admin/auditors/${auditor.id}/resend-invite`);

      if (res.data.email_sent) {
        setAuditorActionMessage({
          id: auditor.id,
          type: 'success',
          text: `Invite link resent successfully to ${auditor.email}.`,
        });
      } else {
        setAuditorActionMessage({
          id: auditor.id,
          type: 'error',
          text: `Invite token refreshed, but email could not be sent.`,
        });
      }
    } catch (err) {
      setAuditorActionMessage({
        id: auditor.id,
        type: 'error',
        text: err.response?.data?.detail || `Failed to resend invite link.`,
      });
    } finally {
      setActionLoadingId(null);
    }
  };

  // ---------------------------------------------------------------------------
  // Load Location Options for Create Auditor
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (activeTab === 'create_auditor' && locationStates.length === 0) {
      async function loadStates() {
        try {
          setLoadingLocations(true);
          const res = await api.get('/admin/location/options');
          setLocationStates(res.data.states || []);
        } catch (err) {
          console.error('Failed to load states:', err);
        } finally {
          setLoadingLocations(false);
        }
      }
      loadStates();
    }
  }, [activeTab, locationStates.length]);

  const handleStateChange = async (newState) => {
    setCreateForm((prev) => ({
      ...prev,
      state: newState,
      district: '',
      constituency: '',
    }));
    setLocationDistricts([]);
    setLocationConstituencies([]);

    if (!newState) return;

    try {
      setLoadingLocations(true);
      const res = await api.get('/admin/location/options', {
        params: { state: newState },
      });
      setLocationDistricts(res.data.districts || []);
    } catch (err) {
      console.error('Failed to load districts:', err);
    } finally {
      setLoadingLocations(false);
    }
  };

  const handleDistrictChange = async (newDistrict) => {
    setCreateForm((prev) => ({
      ...prev,
      district: newDistrict,
      constituency: '',
    }));
    setLocationConstituencies([]);

    if (!newDistrict || !createForm.state) return;

    try {
      setLoadingLocations(true);
      const res = await api.get('/admin/location/options', {
        params: { state: createForm.state, district: newDistrict },
      });
      setLocationConstituencies(res.data.constituencies || []);
    } catch (err) {
      console.error('Failed to load constituencies:', err);
    } finally {
      setLoadingLocations(false);
    }
  };

  const handleCreateAuditorSubmit = async (e) => {
    e.preventDefault();
    setCreateError('');
    setCreateSuccessMessage('');

    const trimmedName = createForm.name.trim();
    const trimmedEmail = createForm.email.trim().toLowerCase();

    // Client-side validation: same rules as backend
    if (trimmedName.length < 2 || trimmedName.length > 100) {
      setCreateError('Name must be between 2 and 100 characters.');
      return;
    }

    if (!createForm.dob) {
      setCreateError('Please enter the date of birth.');
      return;
    }

    if (!isAge18OrOlder(createForm.dob)) {
      setCreateError('Auditor must be at least 18 years old.');
      return;
    }

    if (!isValidGmail(trimmedEmail)) {
      setCreateError('Email must be a valid @gmail.com address.');
      return;
    }

    if (!createForm.state) {
      setCreateError('Please select a state.');
      return;
    }

    if (!createForm.district) {
      setCreateError('Please select a district.');
      return;
    }

    if (!createForm.constituency) {
      setCreateError('Please select a constituency.');
      return;
    }

    try {
      setCreateLoading(true);
      const res = await api.post('/admin/auditors', {
        name: trimmedName,
        dob: createForm.dob,
        email: trimmedEmail,
        state: createForm.state,
        district: createForm.district,
        constituency: createForm.constituency,
        status: createForm.status,
      });

      // Clear the form
      setCreateForm({
        name: '',
        dob: '',
        email: '',
        state: '',
        district: '',
        constituency: '',
        status: 'active',
      });
      setLocationDistricts([]);
      setLocationConstituencies([]);

      if (res.data.email_sent) {
        setCreateSuccessMessage(
          `Auditor created. A link to set the password was sent to ${res.data.email}.`
        );
      } else {
        setCreateSuccessMessage(
          'Auditor created, but the email could not be sent. Use Resend link in the Auditors list.'
        );
      }

      // Refresh auditors list so the new auditor appears as "Invite pending"
      fetchAuditors();
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setCreateError(detail);
      } else if (Array.isArray(detail)) {
        setCreateError(detail.map((d) => d.msg || d).join(', '));
      } else if (err.response?.status === 409) {
        setCreateError('Auditor with this email already exists.');
      } else {
        setCreateError('Failed to create auditor. Please check the details and try again.');
      }
    } finally {
      setCreateLoading(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Photo Checks (Submissions) Fetch
  // ---------------------------------------------------------------------------
  const fetchSubmissions = useCallback(async (statusToFetch = 'all', pageToFetch = 1, isLoadMore = false) => {
    try {
      if (isLoadMore) {
        setLoadingMoreSubmissions(true);
      } else {
        setLoadingSubmissions(true);
        setSubmissionsError('');
      }

      const res = await api.get('/admin/submissions', {
        params: {
          status: statusToFetch,
          page: pageToFetch,
          page_size: 20,
        },
      });

      const items = res.data.items || [];
      const total = res.data.total ?? items.length;

      if (isLoadMore) {
        setAdminSubmissions((prev) => [...prev, ...items]);
      } else {
        setAdminSubmissions(items);
      }
      setSubmissionsTotal(total);
      setSubmissionsPage(pageToFetch);
    } catch (err) {
      setSubmissionsError(err.response?.data?.detail || 'Failed to load photo checks.');
    } finally {
      setLoadingSubmissions(false);
      setLoadingMoreSubmissions(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'photos') {
      fetchSubmissions(photoTab, 1, false);
    }
  }, [activeTab, photoTab, fetchSubmissions]);

  const handlePhotoTabChange = (newStatus) => {
    setPhotoTab(newStatus);
  };

  const handleLoadMoreSubmissions = () => {
    if (!loadingMoreSubmissions && adminSubmissions.length < submissionsTotal) {
      fetchSubmissions(photoTab, submissionsPage + 1, true);
    }
  };

  // ---------------------------------------------------------------------------
  // Complaints Fetch
  // ---------------------------------------------------------------------------
  const fetchComplaints = useCallback(async (statusToFetch = 'all', pageToFetch = 1, isLoadMore = false) => {
    try {
      if (isLoadMore) {
        setLoadingMoreComplaints(true);
      } else {
        setLoadingComplaints(true);
        setComplaintsError('');
      }

      const res = await api.get('/admin/complaints', {
        params: {
          status: statusToFetch,
          page: pageToFetch,
          page_size: 20,
        },
      });

      const items = res.data.items || [];
      const total = res.data.total ?? items.length;

      if (isLoadMore) {
        setAdminComplaints((prev) => [...prev, ...items]);
      } else {
        setAdminComplaints(items);
      }
      setComplaintsTotal(total);
      setComplaintsPage(pageToFetch);
    } catch (err) {
      setComplaintsError(err.response?.data?.detail || 'Failed to load complaints.');
    } finally {
      setLoadingComplaints(false);
      setLoadingMoreComplaints(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'complaints') {
      fetchComplaints(complaintsTab, 1, false);
    }
  }, [activeTab, complaintsTab, fetchComplaints]);

  const handleComplaintTabChange = (newStatus) => {
    setComplaintsTab(newStatus);
  };

  const handleLoadMoreComplaints = () => {
    if (!loadingMoreComplaints && adminComplaints.length < complaintsTotal) {
      fetchComplaints(complaintsTab, complaintsPage + 1, true);
    }
  };

  const tabs = [
    { id: 'users', label: 'Users' },
    { id: 'auditors', label: 'Auditors' },
    { id: 'create_auditor', label: 'Create auditor' },
    { id: 'photos', label: 'Photo checks' },
    { id: 'complaints', label: 'Complaints' },
    { id: 'reviews', label: 'Reviews' },
  ];

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col">
      {/* Header: Admin title and Logout button */}
      <header className="bg-slate-800/90 border-b border-slate-700/80 sticky top-0 z-30 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-3">
              <div className="w-9 h-9 rounded-xl bg-purple-600 text-white flex items-center justify-center shadow-lg shadow-purple-500/20">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                  />
                </svg>
              </div>
              <h1 className="text-xl font-bold text-white tracking-tight leading-none">
                Admin
              </h1>
            </div>

            <button
              onClick={handleLogout}
              className="min-h-[44px] px-3.5 py-2 text-xs sm:text-sm font-semibold text-slate-300 hover:text-white hover:bg-slate-700/80 rounded-xl transition-colors cursor-pointer flex items-center space-x-1.5"
            >
              <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                />
              </svg>
              <span>Logout</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Horizontally Scrollable Row of Section Tabs */}
        <div className="border-b border-slate-700/80 pb-3 mb-6">
          <div className="flex items-center space-x-2 overflow-x-auto pb-1 scrollbar-thin">
            {tabs.map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => handleTabChange(tab.id)}
                  className={`min-h-[44px] px-4 py-2 rounded-xl text-sm font-semibold whitespace-nowrap transition-all cursor-pointer ${
                    isActive
                      ? 'bg-purple-600 text-white shadow-md shadow-purple-600/20'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* ----------------------------------------------------------------- */}
        {/* USERS SECTION                                                     */}
        {/* ----------------------------------------------------------------- */}
        {activeTab === 'users' && (
          <div>
            {!selectedUser ? (
              // Users List View
              <div className="space-y-6">
                {/* Search Box */}
                <div className="relative max-w-md w-full">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
                    placeholder="Search users by email, state, district..."
                    className="w-full pl-10 pr-4 py-2.5 min-h-[44px] text-sm rounded-xl border border-slate-700 bg-slate-800/80 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all shadow-inner"
                  />
                  {searchInput && (
                    <button
                      onClick={() => setSearchInput('')}
                      className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-200"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>

                {/* Error Banner */}
                {usersError && (
                  <div className="p-4 rounded-xl bg-red-950/70 border border-red-800 text-sm text-red-200">
                    {usersError}
                  </div>
                )}

                {/* Loading Initial */}
                {loadingUsers ? (
                  <div className="py-16 flex flex-col items-center justify-center space-y-3">
                    <Loader size="lg" />
                    <p className="text-sm text-slate-400">Loading users...</p>
                  </div>
                ) : users.length === 0 ? (
                  /* Empty State */
                  <div className="bg-slate-800/50 border border-slate-700/60 rounded-2xl p-12 text-center max-w-md mx-auto">
                    <p className="text-slate-300 font-medium">No users found.</p>
                    <p className="text-xs text-slate-500 mt-1">
                      {searchTerm ? 'Try adjusting your search criteria.' : 'Users will appear here once registered.'}
                    </p>
                  </div>
                ) : (
                  /* Cards Grid */
                  <div className="space-y-4">
                    <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                      <span>
                        Showing {users.length} of {usersTotal} users
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {users.map((u) => (
                        <div
                          key={u.id}
                          onClick={() => setSelectedUser(u)}
                          className="bg-slate-800/70 hover:bg-slate-800 border border-slate-700/70 hover:border-slate-600 rounded-2xl p-5 transition-all shadow-md cursor-pointer flex flex-col justify-between space-y-4"
                        >
                          <div className="space-y-2">
                            <div className="flex items-start justify-between gap-2">
                              <div className="min-w-0 flex-1">
                                <h3 className="text-base font-bold text-white break-words leading-tight">
                                  {u.name || u.email}
                                </h3>
                                {u.name && (
                                  <p className="text-xs text-slate-400 break-all mt-0.5 font-mono">
                                    {u.email}
                                  </p>
                                )}
                              </div>
                              <span className="px-2 py-0.5 rounded-md text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 shrink-0">
                                {u.xp} XP
                              </span>
                            </div>

                            <p className="text-xs text-slate-400">
                              {u.state || u.district || u.constituency ? (
                                <span>
                                  {[u.constituency, u.district, u.state].filter(Boolean).join(', ') || ''}
                                </span>
                              ) : (
                                <span className="italic text-slate-500">Location not set</span>
                              )}
                            </p>
                          </div>

                          {/* Counters */}
                          <div className="pt-3 border-t border-slate-700/60 space-y-2 text-xs">
                            <div className="flex items-center justify-between">
                              <span className="text-slate-400">Photos:</span>
                              <div className="flex items-center space-x-2">
                                <span className="text-emerald-400 font-medium">
                                  Approved: {u.photos_approved}
                                </span>
                                <span className="text-slate-600">•</span>
                                <span className="text-red-400 font-medium">
                                  Rejected: {u.photos_rejected}
                                </span>
                                <span className="text-slate-600">•</span>
                                <span className="text-amber-400 font-medium">
                                  Pending: {u.photos_pending}
                                </span>
                              </div>
                            </div>

                            <div className="flex items-center justify-between">
                              <span className="text-slate-400">Complaints:</span>
                              <div className="flex items-center space-x-2">
                                <span className="text-slate-300 font-medium">
                                  Total: {u.complaints_total}
                                </span>
                                <span className="text-slate-600">•</span>
                                <span className="text-emerald-400 font-medium">
                                  Accepted: {u.complaints_accepted}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Load More Button */}
                    {users.length < usersTotal && (
                      <div className="pt-4 text-center">
                        <button
                          onClick={handleLoadMoreUsers}
                          disabled={loadingMoreUsers}
                          className="min-h-[44px] px-6 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-sm font-semibold text-white transition-colors disabled:opacity-50 cursor-pointer inline-flex items-center space-x-2"
                        >
                          {loadingMoreUsers ? (
                            <>
                              <Loader size="sm" />
                              <span>Loading more...</span>
                            </>
                          ) : (
                            <span>Load more</span>
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              // User Detail View
              <div className="space-y-6">
                <button
                  onClick={() => setSelectedUser(null)}
                  className="min-h-[44px] px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-sm font-semibold text-white transition-colors cursor-pointer inline-flex items-center space-x-2"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                  </svg>
                  <span>Back to Users</span>
                </button>

                {/* User Summary Card */}
                <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl p-6 shadow-xl space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-700 pb-4">
                    <div>
                      {selectedUser.name ? (
                        <>
                          <h2 className="text-xl font-bold text-white break-words">
                            {selectedUser.name}
                          </h2>
                          <p className="text-xs text-slate-400 break-all mt-0.5 font-mono">
                            {selectedUser.email}
                          </p>
                        </>
                      ) : (
                        <h2 className="text-xl font-bold text-white break-all">
                          {selectedUser.email}
                        </h2>
                      )}
                      <p className="text-xs text-slate-400 mt-1">
                        Member since {formatDate(selectedUser.created_at)}
                      </p>
                    </div>
                    <div className="inline-flex items-center px-3 py-1.5 rounded-xl bg-amber-500/20 text-amber-300 border border-amber-500/30 text-sm font-bold self-start sm:self-auto">
                      {selectedUser.xp} XP
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div>
                      <span className="text-slate-400 block mb-1">Assigned Location:</span>
                      <p className="text-sm font-medium text-slate-200">
                        {[selectedUser.constituency, selectedUser.district, selectedUser.state].filter(Boolean).join(', ') || 'Not set'}
                      </p>
                    </div>

                    <div className="space-y-1">
                      <span className="text-slate-400 block">Activity Counters:</span>
                      <p className="text-slate-300">
                        Photos: <span className="text-emerald-400 font-semibold">{selectedUser.photos_approved} approved</span>,{' '}
                        <span className="text-red-400 font-semibold">{selectedUser.photos_rejected} rejected</span>,{' '}
                        <span className="text-amber-400 font-semibold">{selectedUser.photos_pending} pending</span>
                      </p>
                      <p className="text-slate-300">
                        Complaints: <span className="font-semibold">{selectedUser.complaints_total} total</span>,{' '}
                        <span className="text-emerald-400 font-semibold">{selectedUser.complaints_accepted} accepted</span>,{' '}
                        <span className="text-red-400 font-semibold">{selectedUser.complaints_rejected ?? 0} rejected</span>,{' '}
                        <span className="text-amber-400 font-semibold">{selectedUser.complaints_pending ?? 0} pending</span>
                      </p>
                    </div>
                  </div>
                </div>

                {/* Submissions & Complaints Lists */}
                {userDetailsError && (
                  <div className="p-4 rounded-xl bg-red-950/70 border border-red-800 text-sm text-red-200">
                    {userDetailsError}
                  </div>
                )}

                {loadingUserDetails ? (
                  <div className="py-12 flex flex-col items-center justify-center space-y-3">
                    <Loader size="md" />
                    <p className="text-sm text-slate-400">Loading user submissions and complaints...</p>
                  </div>
                ) : (
                  <div className="space-y-6">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Submissions List */}
                    <div className="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-5 space-y-4">
                      <div className="flex items-center justify-between border-b border-slate-700 pb-3">
                        <h3 className="font-bold text-base text-white">
                          Submissions ({userSubmissions.length})
                        </h3>
                        <span className="text-xs text-slate-400">Photo verification checks</span>
                      </div>

                      {userSubmissions.length === 0 ? (
                        <p className="text-xs text-slate-500 italic py-4 text-center">
                          No submissions recorded for this user.
                        </p>
                      ) : (
                        <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
                          {userSubmissions.map((sub) => {
                            const statusColor =
                              sub.status === 'approved'
                                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                                : sub.status === 'rejected'
                                ? 'bg-red-500/20 text-red-300 border-red-500/30'
                                : 'bg-amber-500/20 text-amber-300 border-amber-500/30';

                            return (
                              <div
                                key={sub.id}
                                className="bg-slate-900/60 border border-slate-700/50 rounded-xl p-3.5 text-xs space-y-2"
                              >
                                <div className="flex items-center justify-between gap-2">
                                  <span className="font-semibold text-slate-200 truncate">
                                    {sub.work_type || 'Work Verification'}
                                  </span>
                                  <span
                                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${statusColor}`}
                                  >
                                    {sub.status}
                                  </span>
                                </div>

                                <p className="text-slate-300 text-xs line-clamp-2">
                                  {sub.description || 'No work description provided'}
                                </p>

                                <div className="flex flex-wrap items-center justify-between gap-1 text-[11px] text-slate-400 pt-1 border-t border-slate-800">
                                  <span>Submitted: {formatDateTime(sub.created_at)}</span>
                                  {sub.reviewed_by ? (
                                    <span className="text-slate-300">
                                      Reviewed by <span className="font-semibold text-white">{sub.reviewed_by.name || sub.reviewed_by.email}</span>
                                      {sub.reviewed_at ? ` on ${formatDate(sub.reviewed_at)}` : ''}
                                    </span>
                                  ) : sub.reviewed_at ? (
                                    <span>Reviewed: {formatDateTime(sub.reviewed_at)}</span>
                                  ) : null}
                                </div>

                                {sub.reject_reason && (
                                  <div className="p-2 rounded bg-red-950/60 border border-red-900 text-red-300 text-[11px]">
                                    <span className="font-semibold">Reject reason:</span> {sub.reject_reason}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    {/* Complaints List */}
                    <div className="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-5 space-y-4">
                      <div className="flex items-center justify-between border-b border-slate-700 pb-3">
                        <h3 className="font-bold text-base text-white">
                          Complaints ({userComplaints.length})
                        </h3>
                        <span className="text-xs text-slate-400">Citizen issue reports</span>
                      </div>

                      {userComplaints.length === 0 ? (
                        <p className="text-xs text-slate-500 italic py-4 text-center">
                          No complaints recorded for this user.
                        </p>
                      ) : (
                        <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
                          {userComplaints.map((comp) => {
                            const statusColor =
                              comp.status === 'accepted'
                                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                                : comp.status === 'rejected'
                                ? 'bg-red-500/20 text-red-300 border-red-500/30'
                                : 'bg-amber-500/20 text-amber-300 border-amber-500/30';

                            return (
                              <div
                                key={comp.id}
                                className="bg-slate-900/60 border border-slate-700/50 rounded-xl p-3.5 text-xs space-y-2"
                              >
                                <div className="flex items-center justify-between gap-2">
                                  <span className="text-slate-400 truncate">
                                    {[comp.constituency, comp.district].filter(Boolean).join(', ') || 'Local complaint'}
                                  </span>
                                  <div className="flex items-center space-x-1.5">
                                    {comp.xp_awarded > 0 && (
                                      <span className="text-amber-400 font-bold text-[10px]">
                                        +{comp.xp_awarded} XP
                                      </span>
                                    )}
                                    <span
                                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${statusColor}`}
                                    >
                                      {comp.status}
                                    </span>
                                  </div>
                                </div>

                                <p className="text-slate-200 text-xs">
                                  {comp.comment}
                                </p>

                                <div className="flex flex-wrap items-center justify-between gap-1 text-[11px] text-slate-400 pt-1 border-t border-slate-800">
                                  <span>Filed: {formatDateTime(comp.created_at)}</span>
                                  {comp.reviewed_by ? (
                                    <span className="text-slate-300">
                                      Reviewed by <span className="font-semibold text-white">{comp.reviewed_by.name || comp.reviewed_by.email}</span>
                                      {comp.reviewed_at ? ` on ${formatDate(comp.reviewed_at)}` : ''}
                                    </span>
                                  ) : comp.reviewed_at ? (
                                    <span>Reviewed: {formatDateTime(comp.reviewed_at)}</span>
                                  ) : null}
                                </div>

                                {comp.auditor_comment && (
                                  <div className="p-2 rounded bg-blue-950/60 border border-blue-900 text-blue-300 text-[11px]">
                                    <span className="font-semibold">Auditor comment:</span> {comp.auditor_comment}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Review Activity List under the user lists */}
                  <div className="pt-2">
                    <ReviewActivityList userId={selectedUser.id} />
                  </div>
                </div>
              )}
              </div>
            )}
          </div>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* AUDITORS SECTION                                                  */}
        {/* ----------------------------------------------------------------- */}
        {activeTab === 'auditors' && (
          <div>
            {!selectedAuditor ? (
              // Auditors List View
              <div className="space-y-6">
                {auditorsError && (
                  <div className="p-4 rounded-xl bg-red-950/70 border border-red-800 text-sm text-red-200">
                    {auditorsError}
                  </div>
                )}

                {/* Feedback message for Auditor Actions */}
                {auditorActionMessage && (
                  <div
                    className={`p-4 rounded-xl text-sm border flex items-center justify-between ${
                      auditorActionMessage.type === 'success'
                        ? 'bg-emerald-950/70 border-emerald-800 text-emerald-200'
                        : 'bg-red-950/70 border-red-800 text-red-200'
                    }`}
                  >
                    <span>{auditorActionMessage.text}</span>
                    <button
                      onClick={() => setAuditorActionMessage(null)}
                      className="ml-3 text-xs underline font-semibold cursor-pointer"
                    >
                      Dismiss
                    </button>
                  </div>
                )}

                {loadingAuditors ? (
                  <div className="py-16 flex flex-col items-center justify-center space-y-3">
                    <Loader size="lg" />
                    <p className="text-sm text-slate-400">Loading auditors...</p>
                  </div>
                ) : auditors.length === 0 ? (
                  <div className="bg-slate-800/50 border border-slate-700/60 rounded-2xl p-12 text-center max-w-md mx-auto">
                    <p className="text-slate-300 font-medium">No auditors found.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {auditors.map((auditor, idx) => (
                      <div
                        key={auditor.id || `builtin-${idx}`}
                        onClick={() => setSelectedAuditor(auditor)}
                        className="bg-slate-800/70 hover:bg-slate-800 border border-slate-700/70 hover:border-slate-600 rounded-2xl p-5 transition-all shadow-md cursor-pointer flex flex-col justify-between space-y-4"
                      >
                        <div className="space-y-2">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                                <h3 className="text-base font-bold text-white">
                                  {auditor.name}
                                </h3>
                                {auditor.builtin && (
                                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-purple-950 text-purple-300 border border-purple-800">
                                    Built-in
                                  </span>
                                )}
                              </div>
                              <p className="text-xs text-slate-400 break-all mt-0.5">
                                {auditor.email}
                              </p>
                            </div>

                            <span
                              className={`px-2 py-0.5 rounded-md text-xs font-semibold shrink-0 ${
                                auditor.status === 'active'
                                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                  : 'bg-red-500/20 text-red-300 border border-red-500/30'
                              }`}
                            >
                              {auditor.status === 'active' ? 'Active' : 'Disabled'}
                            </span>
                          </div>

                          <div className="flex items-center justify-between text-xs pt-1">
                            <span className="text-slate-400">
                              {[auditor.constituency, auditor.district, auditor.state].filter(Boolean).join(', ') || 'National'}
                            </span>
                            <span
                              className={`text-[11px] font-medium ${
                                auditor.password_set ? 'text-blue-400' : 'text-amber-400'
                              }`}
                            >
                              {auditor.password_set ? 'Password set' : 'Invite pending'}
                            </span>
                          </div>
                        </div>

                        {/* Counters */}
                        <div className="pt-3 border-t border-slate-700/60 space-y-2 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="text-slate-400">Reviews Total:</span>
                            <span className="text-white font-semibold">
                              {auditor.reviews_total}
                            </span>
                          </div>

                          <div className="flex items-center justify-between">
                            <span className="text-slate-400">Photos:</span>
                            <div className="flex items-center space-x-2">
                              <span className="text-emerald-400 font-medium">
                                Approved: {auditor.photos_approved}
                              </span>
                              <span className="text-slate-600">•</span>
                              <span className="text-red-400 font-medium">
                                Rejected: {auditor.photos_rejected}
                              </span>
                            </div>
                          </div>

                          <div className="flex items-center justify-between">
                            <span className="text-slate-400">Complaints:</span>
                            <div className="flex items-center space-x-2">
                              <span className="text-emerald-400 font-medium">
                                Accepted: {auditor.complaints_accepted}
                              </span>
                              <span className="text-slate-600">•</span>
                              <span className="text-red-400 font-medium">
                                Rejected: {auditor.complaints_rejected}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Action Buttons for non-built-in auditors */}
                        {!auditor.builtin && auditor.id != null && (
                          <div className="pt-3 border-t border-slate-700/60 flex items-center justify-end space-x-2 flex-wrap gap-y-2">
                            <button
                              type="button"
                              onClick={(e) => handleToggleAuditorStatus(auditor, e)}
                              disabled={Boolean(actionLoadingId)}
                              className={`min-h-[38px] px-3.5 py-1.5 rounded-xl text-xs font-semibold border transition-all cursor-pointer inline-flex items-center space-x-1.5 disabled:opacity-50 disabled:cursor-not-allowed ${
                                auditor.status === 'active'
                                  ? 'bg-red-950/60 hover:bg-red-900/80 border-red-800 text-red-300'
                                  : 'bg-emerald-950/60 hover:bg-emerald-900/80 border-emerald-800 text-emerald-300'
                              }`}
                            >
                              {actionLoadingId === auditor.id ? <Loader size="sm" /> : null}
                              <span>{auditor.status === 'active' ? 'Disable' : 'Activate'}</span>
                            </button>

                            {!auditor.password_set && (
                              <button
                                type="button"
                                onClick={(e) => handleResendInvite(auditor, e)}
                                disabled={Boolean(actionLoadingId)}
                                className="min-h-[38px] px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-blue-950/60 hover:bg-blue-900/80 border border-blue-800 text-blue-300 transition-all cursor-pointer inline-flex items-center space-x-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                {actionLoadingId === auditor.id ? <Loader size="sm" /> : null}
                                <span>Resend link</span>
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              // Auditor Detail View
              <div className="space-y-6">
                <button
                  onClick={() => setSelectedAuditor(null)}
                  className="min-h-[44px] px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-sm font-semibold text-white transition-colors cursor-pointer inline-flex items-center space-x-2"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                  </svg>
                  <span>Back to Auditors</span>
                </button>

                {/* Feedback message for Auditor Actions in Detail View */}
                {auditorActionMessage && (
                  <div
                    className={`p-4 rounded-xl text-sm border flex items-center justify-between ${
                      auditorActionMessage.type === 'success'
                        ? 'bg-emerald-950/70 border-emerald-800 text-emerald-200'
                        : 'bg-red-950/70 border-red-800 text-red-200'
                    }`}
                  >
                    <span>{auditorActionMessage.text}</span>
                    <button
                      onClick={() => setAuditorActionMessage(null)}
                      className="ml-3 text-xs underline font-semibold cursor-pointer"
                    >
                      Dismiss
                    </button>
                  </div>
                )}

                {/* Auditor Summary Card with Range Tabs & 30-Day Bar Chart */}
                <AuditorSummaryCard
                  auditorId={selectedAuditor.builtin || selectedAuditor.id == null ? 'builtin' : selectedAuditor.id}
                />

                {/* Auditor Summary Card (Includes Date of Birth ONLY here) */}
                <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl p-6 shadow-xl space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-700 pb-4">
                    <div>
                      <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                        <h2 className="text-xl font-bold text-white">
                          {selectedAuditor.name}
                        </h2>
                        {selectedAuditor.builtin && (
                          <span className="px-2.5 py-0.5 rounded text-xs font-bold uppercase tracking-wider bg-purple-950 text-purple-300 border border-purple-800">
                            Built-in
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-400 break-all mt-1">
                        {selectedAuditor.email}
                      </p>
                    </div>

                    <div className="flex items-center space-x-2 flex-wrap gap-2">
                      <span
                        className={`px-2.5 py-1 rounded-md text-xs font-semibold ${
                          selectedAuditor.status === 'active'
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                            : 'bg-red-500/20 text-red-300 border border-red-500/30'
                        }`}
                      >
                        {selectedAuditor.status === 'active' ? 'Active' : 'Disabled'}
                      </span>
                      <span
                        className={`px-2.5 py-1 rounded-md text-xs font-semibold border ${
                          selectedAuditor.password_set
                            ? 'bg-blue-500/10 text-blue-300 border-blue-500/30'
                            : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                        }`}
                      >
                        {selectedAuditor.password_set ? 'Password set' : 'Invite pending'}
                      </span>

                      {/* Detail View Action Buttons for non-built-in auditors */}
                      {!selectedAuditor.builtin && selectedAuditor.id != null && (
                        <div className="flex items-center space-x-2 pl-2 border-l border-slate-700">
                          <button
                            type="button"
                            onClick={(e) => handleToggleAuditorStatus(selectedAuditor, e)}
                            disabled={Boolean(actionLoadingId)}
                            className={`min-h-[38px] px-3.5 py-1.5 rounded-xl text-xs font-semibold border transition-all cursor-pointer inline-flex items-center space-x-1.5 disabled:opacity-50 disabled:cursor-not-allowed ${
                              selectedAuditor.status === 'active'
                                ? 'bg-red-950/60 hover:bg-red-900/80 border-red-800 text-red-300'
                                : 'bg-emerald-950/60 hover:bg-emerald-900/80 border-emerald-800 text-emerald-300'
                            }`}
                          >
                            {actionLoadingId === selectedAuditor.id ? <Loader size="sm" /> : null}
                            <span>{selectedAuditor.status === 'active' ? 'Disable' : 'Activate'}</span>
                          </button>

                          {!selectedAuditor.password_set && (
                            <button
                              type="button"
                              onClick={(e) => handleResendInvite(selectedAuditor, e)}
                              disabled={Boolean(actionLoadingId)}
                              className="min-h-[38px] px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-blue-950/60 hover:bg-blue-900/80 border border-blue-800 text-blue-300 transition-all cursor-pointer inline-flex items-center space-x-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {actionLoadingId === selectedAuditor.id ? <Loader size="sm" /> : null}
                              <span>Resend link</span>
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 text-xs">
                    {/* Date of Birth: Displayed ONLY in this detail view */}
                    <div>
                      <span className="text-slate-400 block mb-0.5">Date of Birth:</span>
                      <p className="text-sm font-semibold text-white">
                        {selectedAuditor.dob ? formatDate(selectedAuditor.dob) : '—'}
                      </p>
                    </div>

                    <div>
                      <span className="text-slate-400 block mb-0.5">Assigned Location:</span>
                      <p className="text-sm font-medium text-slate-200">
                        {[selectedAuditor.constituency, selectedAuditor.district, selectedAuditor.state].filter(Boolean).join(', ') || 'National'}
                      </p>
                    </div>

                    <div>
                      <span className="text-slate-400 block mb-0.5">Total Reviews:</span>
                      <p className="text-sm font-bold text-white">
                        {selectedAuditor.reviews_total}
                      </p>
                    </div>
                  </div>

                  {/* Counters detail */}
                  <div className="pt-2 border-t border-slate-700/60 grid grid-cols-2 sm:grid-cols-4 gap-3 text-center text-xs">
                    <div className="bg-slate-900/50 p-2.5 rounded-xl border border-slate-700/40">
                      <span className="text-slate-400 block text-[11px]">Photos Approved</span>
                      <span className="text-base font-bold text-emerald-400">
                        {selectedAuditor.photos_approved}
                      </span>
                    </div>
                    <div className="bg-slate-900/50 p-2.5 rounded-xl border border-slate-700/40">
                      <span className="text-slate-400 block text-[11px]">Photos Rejected</span>
                      <span className="text-base font-bold text-red-400">
                        {selectedAuditor.photos_rejected}
                      </span>
                    </div>
                    <div className="bg-slate-900/50 p-2.5 rounded-xl border border-slate-700/40">
                      <span className="text-slate-400 block text-[11px]">Complaints Accepted</span>
                      <span className="text-base font-bold text-emerald-400">
                        {selectedAuditor.complaints_accepted}
                      </span>
                    </div>
                    <div className="bg-slate-900/50 p-2.5 rounded-xl border border-slate-700/40">
                      <span className="text-slate-400 block text-[11px]">Complaints Rejected</span>
                      <span className="text-base font-bold text-red-400">
                        {selectedAuditor.complaints_rejected}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Latest Reviews (from GET /admin/auditors/{id}) */}
                {selectedAuditor.builtin || selectedAuditor.id == null ? (
                  <div className="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-6 text-center text-slate-400 text-xs">
                    Built-in legacy auditor account.
                  </div>
                ) : (
                  <div className="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-6 space-y-4">
                    <div className="flex items-center justify-between border-b border-slate-700 pb-3">
                      <h3 className="font-bold text-base text-white">
                        Latest Reviews
                      </h3>
                      <span className="text-xs text-slate-400">Auditor review history</span>
                    </div>

                    {auditorLogsError && (
                      <div className="p-3 rounded-xl bg-red-950/70 border border-red-800 text-xs text-red-200">
                        {auditorLogsError}
                      </div>
                    )}

                    {loadingAuditorLogs ? (
                      <div className="py-8 flex flex-col items-center justify-center space-y-2">
                        <Loader size="sm" />
                        <p className="text-xs text-slate-400">Loading review logs...</p>
                      </div>
                    ) : auditorReviewLogs.length === 0 ? (
                      <p className="text-xs text-slate-500 italic py-4 text-center">
                        No review logs recorded yet.
                      </p>
                    ) : (
                      <div className="space-y-2.5 max-h-[500px] overflow-y-auto pr-1">
                        {auditorReviewLogs.map((log, lIdx) => {
                          const isApprovedOrAccepted =
                            log.decision === 'approved' || log.decision === 'accepted';
                          const decisionColor = isApprovedOrAccepted
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                            : 'bg-red-500/20 text-red-300 border-red-500/30';

                          return (
                            <div
                              key={lIdx}
                              className="bg-slate-900/60 border border-slate-700/50 rounded-xl p-3 flex items-center justify-between gap-3 text-xs"
                            >
                              <div className="flex items-center space-x-2.5">
                                <span className="font-medium text-slate-300 capitalize">
                                  {log.kind === 'submission' ? 'Photo check' : 'Complaint'}
                                </span>
                                <span className="text-slate-500 text-[11px]">
                                  Target #{log.target_id}
                                </span>
                              </div>

                              <div className="flex items-center space-x-3 shrink-0">
                                <span
                                  className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${decisionColor}`}
                                >
                                  {log.decision}
                                </span>
                                <span className="text-[11px] text-slate-400">
                                  {formatDateTime(log.created_at)}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

                {/* Review Activity for this Auditor */}
                <ReviewActivityList
                  auditorId={selectedAuditor.builtin || selectedAuditor.id == null ? 'builtin' : selectedAuditor.id}
                />
              </div>
            )}
          </div>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* CREATE AUDITOR SECTION                                            */}
        {/* ----------------------------------------------------------------- */}
        {activeTab === 'create_auditor' && (
          <div className="max-w-2xl mx-auto space-y-6">
            <div className="bg-slate-800/80 border border-slate-700/80 rounded-2xl p-6 sm:p-8 shadow-xl space-y-6">
              <div>
                <h2 className="text-xl font-bold text-white mb-1">
                  Create Auditor
                </h2>
                <p className="text-xs text-slate-400">
                  Register a new auditor and send an invitation link to set their password.
                </p>
              </div>

              {createError && (
                <div className="p-4 rounded-xl bg-red-950/70 border border-red-800 text-sm text-red-200 flex items-start space-x-2">
                  <svg className="w-5 h-5 text-red-400 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <span>{createError}</span>
                </div>
              )}

              {createSuccessMessage && (
                <div className="p-4 rounded-xl bg-emerald-950/70 border border-emerald-800 text-sm text-emerald-200 flex items-start space-x-2">
                  <svg className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                  </svg>
                  <span>{createSuccessMessage}</span>
                </div>
              )}

              <form onSubmit={handleCreateAuditorSubmit} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Name */}
                  <div className="sm:col-span-2">
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                      Name
                    </label>
                    <input
                      type="text"
                      required
                      value={createForm.name}
                      onChange={(e) =>
                        setCreateForm((prev) => ({ ...prev, name: e.target.value }))
                      }
                      placeholder="e.g. Priya Sharma (2-100 chars)"
                      className="w-full px-3.5 py-2.5 min-h-[44px] text-sm rounded-xl border border-slate-700 bg-slate-900/80 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all shadow-inner"
                    />
                  </div>

                  {/* Date of Birth */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                      Date of birth
                    </label>
                    <input
                      type="date"
                      required
                      max={getMaxDob()}
                      value={createForm.dob}
                      onChange={(e) =>
                        setCreateForm((prev) => ({ ...prev, dob: e.target.value }))
                      }
                      className="w-full px-3.5 py-2.5 min-h-[44px] text-sm rounded-xl border border-slate-700 bg-slate-900/80 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all shadow-inner"
                    />
                    <span className="text-[11px] text-slate-500 mt-1 block">
                      Must be at least 18 years old
                    </span>
                  </div>

                  {/* Gmail */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                      Gmail
                    </label>
                    <input
                      type="email"
                      required
                      value={createForm.email}
                      onChange={(e) =>
                        setCreateForm((prev) => ({ ...prev, email: e.target.value }))
                      }
                      placeholder="auditor@gmail.com"
                      className="w-full px-3.5 py-2.5 min-h-[44px] text-sm rounded-xl border border-slate-700 bg-slate-900/80 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all shadow-inner"
                    />
                    <span className="text-[11px] text-slate-500 mt-1 block">
                      Must be a valid @gmail.com address
                    </span>
                  </div>

                  {/* Cascading Dropdowns: State, District, Constituency */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                      State
                    </label>
                    <select
                      required
                      value={createForm.state}
                      onChange={(e) => handleStateChange(e.target.value)}
                      className="w-full px-3.5 py-2.5 min-h-[44px] text-sm rounded-xl border border-slate-700 bg-slate-900/80 text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all shadow-inner cursor-pointer"
                    >
                      <option value="">Select State</option>
                      {locationStates.map((st) => (
                        <option key={st} value={st}>
                          {st}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                      District
                    </label>
                    <select
                      required
                      disabled={!createForm.state || loadingLocations}
                      value={createForm.district}
                      onChange={(e) => handleDistrictChange(e.target.value)}
                      className="w-full px-3.5 py-2.5 min-h-[44px] text-sm rounded-xl border border-slate-700 bg-slate-900/80 text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all shadow-inner disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                    >
                      <option value="">
                        {!createForm.state ? 'Select state first' : 'Select District'}
                      </option>
                      {locationDistricts.map((dist) => (
                        <option key={dist} value={dist}>
                          {dist}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                      Constituency
                    </label>
                    <select
                      required
                      disabled={!createForm.district || loadingLocations}
                      value={createForm.constituency}
                      onChange={(e) =>
                        setCreateForm((prev) => ({
                          ...prev,
                          constituency: e.target.value,
                        }))
                      }
                      className="w-full px-3.5 py-2.5 min-h-[44px] text-sm rounded-xl border border-slate-700 bg-slate-900/80 text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all shadow-inner disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                    >
                      <option value="">
                        {!createForm.district
                          ? 'Select district first'
                          : 'Select Constituency'}
                      </option>
                      {locationConstituencies.map((con) => (
                        <option key={con} value={con}>
                          {con}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Status: Active or Disabled, default Active */}
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                      Status
                    </label>
                    <select
                      value={createForm.status}
                      onChange={(e) =>
                        setCreateForm((prev) => ({ ...prev, status: e.target.value }))
                      }
                      className="w-full px-3.5 py-2.5 min-h-[44px] text-sm rounded-xl border border-slate-700 bg-slate-900/80 text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all shadow-inner cursor-pointer"
                    >
                      <option value="active">Active</option>
                      <option value="disabled">Disabled</option>
                    </select>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={createLoading}
                  className="w-full min-h-[44px] flex items-center justify-center py-3 px-4 rounded-xl text-base font-semibold text-white bg-purple-600 hover:bg-purple-500 active:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg shadow-purple-600/30 cursor-pointer mt-6"
                >
                  {createLoading ? (
                    <span className="flex items-center space-x-2">
                      <Loader size="sm" />
                      <span>Creating Auditor...</span>
                    </span>
                  ) : (
                    'Create Auditor'
                  )}
                </button>
              </form>
            </div>
          </div>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* PHOTO CHECKS (SUBMISSIONS) SECTION                                */}
        {/* ----------------------------------------------------------------- */}
        {activeTab === 'photos' && (
          <div className="space-y-6">
            {/* Status Tabs: All, Pending, Approved, Rejected */}
            <div className="flex items-center space-x-2 border-b border-slate-700/80 pb-3 overflow-x-auto scrollbar-thin">
              {[
                { id: 'all', label: 'All' },
                { id: 'pending', label: 'Pending' },
                { id: 'approved', label: 'Approved' },
                { id: 'rejected', label: 'Rejected' },
              ].map((tab) => {
                const isActive = photoTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => handlePhotoTabChange(tab.id)}
                    className={`min-h-[40px] px-4 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                      isActive
                        ? 'bg-purple-600 text-white shadow-md'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                    }`}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* Error Banner */}
            {submissionsError && (
              <div className="p-4 rounded-xl bg-red-950/70 border border-red-800 text-sm text-red-200">
                {submissionsError}
              </div>
            )}

            {/* Loading Initial */}
            {loadingSubmissions ? (
              <div className="py-16 flex flex-col items-center justify-center space-y-3">
                <Loader size="lg" />
                <p className="text-sm text-slate-400">Loading photo checks...</p>
              </div>
            ) : adminSubmissions.length === 0 ? (
              /* Empty State */
              <div className="bg-slate-800/50 border border-slate-700/60 rounded-2xl p-12 text-center max-w-md mx-auto">
                <p className="text-slate-300 font-medium">No submissions found.</p>
                <p className="text-xs text-slate-500 mt-1">
                  No photo verification checks match the "{photoTab}" filter.
                </p>
              </div>
            ) : (
              /* Submissions Grid */
              <div className="space-y-6">
                <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                  <span>
                    Showing {adminSubmissions.length} of {submissionsTotal} submissions
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {adminSubmissions.map((sub) => (
                    <AdminSubmissionCard key={sub.id} submission={sub} />
                  ))}
                </div>

                {/* Load More Button */}
                {adminSubmissions.length < submissionsTotal && (
                  <div className="pt-4 text-center">
                    <button
                      onClick={handleLoadMoreSubmissions}
                      disabled={loadingMoreSubmissions}
                      className="min-h-[44px] px-6 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-sm font-semibold text-white transition-colors disabled:opacity-50 cursor-pointer inline-flex items-center space-x-2"
                    >
                      {loadingMoreSubmissions ? (
                        <>
                          <Loader size="sm" />
                          <span>Loading more...</span>
                        </>
                      ) : (
                        <span>Load more</span>
                      )}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* COMPLAINTS SECTION                                                */}
        {/* ----------------------------------------------------------------- */}
        {activeTab === 'complaints' && (
          <div className="space-y-6">
            {/* Status Tabs: All, Pending, Accepted, Rejected */}
            <div className="flex items-center space-x-2 border-b border-slate-700/80 pb-3 overflow-x-auto scrollbar-thin">
              {[
                { id: 'all', label: 'All' },
                { id: 'pending', label: 'Pending' },
                { id: 'accepted', label: 'Accepted' },
                { id: 'rejected', label: 'Rejected' },
              ].map((tab) => {
                const isActive = complaintsTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => handleComplaintTabChange(tab.id)}
                    className={`min-h-[40px] px-4 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                      isActive
                        ? 'bg-purple-600 text-white shadow-md'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                    }`}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* Error Banner */}
            {complaintsError && (
              <div className="p-4 rounded-xl bg-red-950/70 border border-red-800 text-sm text-red-200">
                {complaintsError}
              </div>
            )}

            {/* Loading Initial */}
            {loadingComplaints ? (
              <div className="py-16 flex flex-col items-center justify-center space-y-3">
                <Loader size="lg" />
                <p className="text-sm text-slate-400">Loading complaints...</p>
              </div>
            ) : adminComplaints.length === 0 ? (
              /* Empty State */
              <div className="bg-slate-800/50 border border-slate-700/60 rounded-2xl p-12 text-center max-w-md mx-auto">
                <p className="text-slate-300 font-medium">No complaints found.</p>
                <p className="text-xs text-slate-500 mt-1">
                  No citizen complaints match the "{complaintsTab}" filter.
                </p>
              </div>
            ) : (
              /* Complaints Grid */
              <div className="space-y-6">
                <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                  <span>
                    Showing {adminComplaints.length} of {complaintsTotal} complaints
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {adminComplaints.map((comp) => (
                    <AdminComplaintCard key={comp.id} complaint={comp} />
                  ))}
                </div>

                {/* Load More Button */}
                {adminComplaints.length < complaintsTotal && (
                  <div className="pt-4 text-center">
                    <button
                      onClick={handleLoadMoreComplaints}
                      disabled={loadingMoreComplaints}
                      className="min-h-[44px] px-6 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-sm font-semibold text-white transition-colors disabled:opacity-50 cursor-pointer inline-flex items-center space-x-2"
                    >
                      {loadingMoreComplaints ? (
                        <>
                          <Loader size="sm" />
                          <span>Loading more...</span>
                        </>
                      ) : (
                        <span>Load more</span>
                      )}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* REVIEWS SECTION                                                   */}
        {/* ----------------------------------------------------------------- */}
        {activeTab === 'reviews' && (
          <div className="space-y-6">
            <ReviewActivityList />
          </div>
        )}
      </main>
    </div>
  );
}
