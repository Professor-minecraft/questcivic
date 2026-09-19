import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import Loader from '../components/Loader';
import AuditorComplaintCard from '../components/AuditorComplaintCard';
import PhotoViewer from '../components/PhotoViewer';

// Component to load protected image via Bearer token and display as a blob URL
function AuthenticatedImage({ submissionId, alt }) {
  const [src, setSrc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [isViewerOpen, setIsViewerOpen] = useState(false);

  useEffect(() => {
    let active = true;
    let objectUrl = null;

    async function loadImage() {
      try {
        setLoading(true);
        setFailed(false);
        const res = await api.get(`/auditor/submissions/${submissionId}/image`, {
          responseType: 'blob',
        });
        if (!active) return;
        objectUrl = URL.createObjectURL(res.data);
        setSrc(objectUrl);
      } catch (err) {
        console.error('Failed to load authenticated submission image:', err);
        if (active) setFailed(true);
      } finally {
        if (active) setLoading(false);
      }
    }

    loadImage();

    return () => {
      active = false;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [submissionId]);

  if (loading) {
    return (
      <div className="w-full h-56 bg-slate-100 flex flex-col items-center justify-center text-slate-400 rounded-xl">
        <Loader size="md" />
        <span className="text-xs font-medium mt-2">Loading image...</span>
      </div>
    );
  }

  if (failed || !src) {
    return (
      <div className="w-full h-56 bg-slate-100 flex flex-col items-center justify-center text-slate-400 rounded-xl p-4 text-center">
        <svg className="w-8 h-8 text-slate-400 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <span className="text-xs text-slate-500 font-medium">Image preview unavailable</span>
      </div>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setIsViewerOpen(true)}
        className="relative block w-full rounded-xl overflow-hidden cursor-zoom-in group focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 focus:ring-offset-slate-900"
        aria-label="View photo fullscreen"
      >
        <img
          src={src}
          alt={alt || 'Verification Submission Photo'}
          className="w-full h-56 object-cover rounded-xl bg-slate-100"
        />
        <div
          className="absolute bottom-2 right-2 p-1.5 rounded-lg bg-black/60 text-white/90 shadow pointer-events-none group-hover:bg-black/80 transition-colors"
          aria-hidden="true"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 8V4m0 0h4M4 4l5 5m11-5h-4m4 0v4m0-4l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
          </svg>
        </div>
      </button>

      {isViewerOpen && (
        <PhotoViewer
          src={src}
          filename={`civicquest-work-${submissionId}`}
          title={`Work photo #${submissionId}`}
          alt={alt || `Work photo #${submissionId}`}
          onClose={() => setIsViewerOpen(false)}
        />
      )}
    </>
  );
}

export default function AuditorDashboard() {
  const navigate = useNavigate();
  const { logout } = useAuth();

  const [viewMode, setViewMode] = useState('photos'); // 'photos' | 'complaints'
  const [activeTab, setActiveTab] = useState('pending'); // 'pending' | 'approved' | 'rejected'
  const [submissions, setSubmissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toastMessage, setToastMessage] = useState('');
  const [actionLoadingId, setActionLoadingId] = useState(null);

  // Complaints State
  const [complaintsTab, setComplaintsTab] = useState('pending'); // 'pending' | 'accepted' | 'rejected'
  const [complaints, setComplaints] = useState([]);
  const [complaintsTotal, setComplaintsTotal] = useState(0);
  const [complaintsPage, setComplaintsPage] = useState(1);
  const [complaintsLoading, setComplaintsLoading] = useState(false);
  const [complaintsLoadingMore, setComplaintsLoadingMore] = useState(false);
  const [complaintsError, setComplaintsError] = useState('');

  // Reject modal state
  const [rejectModal, setRejectModal] = useState({
    isOpen: false,
    submissionId: null,
    reason: '',
    error: '',
    loading: false,
  });

  // Handle Logout
  const handleLogout = () => {
    logout();
    navigate('/auditor/login');
  };

  // Auto-dismiss toast after 4s
  useEffect(() => {
    if (toastMessage) {
      const timer = setTimeout(() => {
        setToastMessage('');
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [toastMessage]);

  // Fetch submissions by status tab
  const fetchSubmissions = useCallback(async (status) => {
    try {
      setLoading(true);
      setError('');
      const res = await api.get(`/auditor/submissions?status=${status}`);
      setSubmissions(res.data || []);
    } catch (err) {
      console.error('Failed to fetch auditor submissions:', err);
      const msg = err.response?.data?.detail || 'Failed to load submissions. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch on tab change
  useEffect(() => {
    fetchSubmissions(activeTab);
  }, [activeTab, fetchSubmissions]);

  // Handle Approve Submission
  const handleApprove = async (submissionId, userEmail) => {
    try {
      setActionLoadingId(submissionId);
      setError('');
      await api.post(`/auditor/submissions/${submissionId}/approve`);

      // Remove card from list
      setSubmissions((prev) => prev.filter((s) => s.id !== submissionId));

      // Show success message
      setToastMessage('150 XP given');
    } catch (err) {
      console.error('Approval failed:', err);
      const msg = err.response?.data?.detail || 'Failed to approve submission.';
      setError(msg);
    } finally {
      setActionLoadingId(null);
    }
  };

  // Open Reject Modal
  const openRejectModal = (submissionId) => {
    setRejectModal({
      isOpen: true,
      submissionId,
      reason: '',
      error: '',
      loading: false,
    });
  };

  // Close Reject Modal
  const closeRejectModal = () => {
    if (rejectModal.loading) return;
    setRejectModal({
      isOpen: false,
      submissionId: null,
      reason: '',
      error: '',
      loading: false,
    });
  };

  // Submit Rejection
  const handleConfirmReject = async (e) => {
    e.preventDefault();
    if (!rejectModal.reason.trim()) {
      setRejectModal((prev) => ({ ...prev, error: 'Please enter a rejection reason.' }));
      return;
    }

    try {
      setRejectModal((prev) => ({ ...prev, loading: true, error: '' }));
      await api.post(`/auditor/submissions/${rejectModal.submissionId}/reject`, {
        reason: rejectModal.reason.trim(),
      });

      // Remove card from list
      setSubmissions((prev) => prev.filter((s) => s.id !== rejectModal.submissionId));

      // Close modal and show success toast
      closeRejectModal();
      setToastMessage('Submission rejected');
    } catch (err) {
      console.error('Rejection failed:', err);
      const msg = err.response?.data?.detail || 'Failed to reject submission.';
      setRejectModal((prev) => ({ ...prev, error: msg, loading: false }));
    }
  };

  // Format date time
  const formatDateTime = (val) => {
    if (!val) return 'Unknown';
    try {
      const d = new Date(val);
      return d.toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return String(val);
    }
  };

  // Fetch complaints by status tab and page
  const fetchComplaints = useCallback(async (status, targetPage = 1, append = false) => {
    try {
      if (append) {
        setComplaintsLoadingMore(true);
      } else {
        setComplaintsLoading(true);
      }
      setComplaintsError('');
      const res = await api.get('/auditor/complaints', {
        params: {
          status,
          page: targetPage,
          page_size: 20,
        },
      });
      const data = res.data;
      setComplaintsTotal(data.total || 0);
      setComplaintsPage(targetPage);
      if (append) {
        setComplaints((prev) => [...prev, ...(data.items || [])]);
      } else {
        setComplaints(data.items || []);
      }
    } catch (err) {
      console.error('Failed to fetch auditor complaints:', err);
      const msg = err.response?.data?.detail || 'Failed to load complaints. Please try again.';
      setComplaintsError(msg);
    } finally {
      setComplaintsLoading(false);
      setComplaintsLoadingMore(false);
    }
  }, []);

  // Fetch complaints when viewMode is 'complaints' or complaintsTab changes
  useEffect(() => {
    if (viewMode === 'complaints') {
      fetchComplaints(complaintsTab, 1, false);
    }
  }, [viewMode, complaintsTab, fetchComplaints]);

  // Handle action success on a complaint
  const handleComplaintActionSuccess = (complaintId, actionType) => {
    setComplaints((prev) => prev.filter((c) => c.id !== complaintId));
    setComplaintsTotal((prev) => Math.max(0, prev - 1));
    setToastMessage(
      actionType === 'accept' ? 'Complaint accepted, 50 XP given' : 'Complaint rejected'
    );
  };

  const handleLoadMoreComplaints = () => {
    const nextPage = complaintsPage + 1;
    fetchComplaints(complaintsTab, nextPage, true);
  };
  const hasMoreComplaints = complaints.length < complaintsTotal;

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-emerald-600 text-white px-5 py-3 rounded-xl shadow-2xl flex items-center space-x-2.5 animate-in fade-in slide-in-from-bottom-5">
          <svg className="w-5 h-5 text-emerald-200 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
          </svg>
          <span className="font-semibold text-sm">{toastMessage}</span>
        </div>
      )}

      {/* Auditor Navigation Header */}
      <header className="bg-slate-800/90 border-b border-slate-700/80 sticky top-0 z-30 backdrop-blur-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-3">
              <div className="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-lg shadow-blue-500/20">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                  />
                </svg>
              </div>
              <div>
                <h1 className="text-lg font-bold text-white tracking-tight leading-none">
                  Auditor Dashboard
                </h1>
                <span className="text-xs text-blue-400 font-medium">MPLADS Photo Verification</span>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <span className="hidden sm:inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold bg-blue-950 text-blue-300 border border-blue-800">
                Auditor Role
              </span>
              <button
                onClick={handleLogout}
                className="min-h-[44px] px-3.5 py-2 text-xs sm:text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700 rounded-lg transition-colors cursor-pointer flex items-center space-x-1.5"
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
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {/* Top Switch: Photo checks (default) vs Complaints */}
        <div className="mb-6 flex items-center justify-between flex-wrap gap-4 border-b border-slate-800 pb-4">
          <div className="p-1 bg-slate-800 rounded-xl border border-slate-700 inline-flex shadow-inner">
            <button
              type="button"
              onClick={() => setViewMode('photos')}
              className={`min-h-[44px] px-5 py-2 rounded-lg text-sm font-semibold transition-all cursor-pointer flex items-center space-x-2 ${
                viewMode === 'photos'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span>Photo checks</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode('complaints')}
              className={`min-h-[44px] px-5 py-2 rounded-lg text-sm font-semibold transition-all cursor-pointer flex items-center space-x-2 ${
                viewMode === 'complaints'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>Complaints</span>
            </button>
          </div>
        </div>

        {viewMode === 'photos' ? (
          <>
            {/* Navigation Tabs: Pending, Approved, Rejected */}
            <div className="flex items-center space-x-2 border-b border-slate-700 pb-3 mb-6 overflow-x-auto">
          <button
            onClick={() => setActiveTab('pending')}
            className={`min-h-[44px] px-4 py-2 rounded-xl text-sm font-semibold transition-colors cursor-pointer flex items-center space-x-2 shrink-0 ${
              activeTab === 'pending'
                ? 'bg-blue-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            <span>Pending Review</span>
            {activeTab === 'pending' && submissions.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-xs bg-blue-700 text-white font-bold">
                {submissions.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('approved')}
            className={`min-h-[44px] px-4 py-2 rounded-xl text-sm font-semibold transition-colors cursor-pointer flex items-center space-x-2 shrink-0 ${
              activeTab === 'approved'
                ? 'bg-emerald-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            <span>Approved</span>
            {activeTab === 'approved' && submissions.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-xs bg-emerald-700 text-white font-bold">
                {submissions.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('rejected')}
            className={`min-h-[44px] px-4 py-2 rounded-xl text-sm font-semibold transition-colors cursor-pointer flex items-center space-x-2 shrink-0 ${
              activeTab === 'rejected'
                ? 'bg-red-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            <span>Rejected</span>
            {activeTab === 'rejected' && submissions.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-xs bg-red-700 text-white font-bold">
                {submissions.length}
              </span>
            )}
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 p-4 rounded-xl bg-red-950/70 border border-red-800 text-sm text-red-200 flex items-start space-x-2">
            <svg className="w-5 h-5 text-red-400 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
            <span>{error}</span>
          </div>
        )}

        {/* Loading State */}
        {loading ? (
          <div className="py-20 flex flex-col items-center justify-center space-y-4">
            <Loader size="lg" />
            <p className="text-sm font-medium text-slate-400">Loading {activeTab} submissions...</p>
          </div>
        ) : submissions.length === 0 ? (
          /* Empty State */
          <div className="bg-slate-800/60 rounded-2xl border border-slate-700/60 p-12 text-center max-w-md mx-auto my-12 shadow-sm">
            <div className="w-14 h-14 mx-auto rounded-2xl bg-slate-700/60 text-slate-400 flex items-center justify-center mb-4">
              <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
                />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-white mb-1">
              No {activeTab} submissions
            </h3>
            <p className="text-sm text-slate-400">
              There are currently no items in the {activeTab} queue.
            </p>
          </div>
        ) : (
          /* Submissions Cards Grid */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {submissions.map((item) => (
              <div
                key={item.id}
                className="bg-slate-800/80 rounded-2xl border border-slate-700/70 p-5 shadow-xl flex flex-col justify-between"
              >
                <div>
                  {/* Authenticated Image with Blob URL */}
                  <div className="mb-4">
                    <AuthenticatedImage submissionId={item.id} alt={item.work?.work_type} />
                  </div>

                  {/* Submission Header Metadata */}
                  <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                    <span className="font-medium text-slate-300">
                      Uploaded {formatDateTime(item.created_at)}
                    </span>
                    {item.lat && item.lng && (
                      <span className="inline-flex items-center text-[11px] text-emerald-400 font-mono bg-emerald-950/60 border border-emerald-800/80 px-1.5 py-0.5 rounded">
                        GPS: {item.lat.toFixed(2)}, {item.lng.toFixed(2)}
                      </span>
                    )}
                  </div>

                  {/* Citizen Email */}
                  <div className="mb-3">
                    <span className="text-[11px] text-slate-400 uppercase font-semibold tracking-wider block">
                      Citizen Submitter
                    </span>
                    <span className="text-sm font-semibold text-blue-400 break-words block">
                      {item.user_email}
                    </span>
                  </div>

                  {/* Work Description & Type */}
                  <h3 className="text-base font-bold text-white line-clamp-2 leading-snug mb-2">
                    {item.work?.work_type || item.work?.description || 'MPLADS Project'}
                  </h3>
                  <p className="text-xs text-slate-300 mb-4 line-clamp-3 leading-relaxed">
                    {item.work?.description}
                  </p>

                  {/* Work Meta: MP & District */}
                  <div className="pt-3 border-t border-slate-700/70 grid grid-cols-2 gap-2 text-xs mb-4">
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase font-semibold block">
                        Hon'ble MP
                      </span>
                      <span className="font-medium text-slate-200 truncate block mt-0.5">
                        {item.work?.mp_name || 'N/A'}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase font-semibold block">
                        District
                      </span>
                      <span className="font-medium text-slate-200 truncate block mt-0.5">
                        {item.work?.district || 'N/A'}
                      </span>
                    </div>
                  </div>

                  {/* If Rejected, show reason */}
                  {item.status === 'rejected' && item.reject_reason && (
                    <div className="mb-4 p-3 rounded-xl bg-red-950/60 border border-red-800/70 text-xs text-red-200">
                      <span className="font-bold block mb-0.5">Rejection Reason:</span>
                      <span>{item.reject_reason}</span>
                    </div>
                  )}

                  {/* If Reviewed, show reviewed timestamp */}
                  {item.reviewed_at && (
                    <div className="text-[11px] text-slate-400 mb-3">
                      Reviewed on: {formatDateTime(item.reviewed_at)}
                    </div>
                  )}
                </div>

                {/* Action Buttons for Pending Tab */}
                {activeTab === 'pending' && (
                  <div className="pt-3 border-t border-slate-700/70 flex items-center space-x-3">
                    <button
                      type="button"
                      onClick={() => handleApprove(item.id, item.user_email)}
                      disabled={actionLoadingId === item.id}
                      className="flex-1 min-h-[44px] flex items-center justify-center px-4 py-2.5 rounded-xl text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-emerald-600/20 transition-colors cursor-pointer"
                    >
                      {actionLoadingId === item.id ? (
                        <span className="flex items-center space-x-1.5">
                          <Loader size="sm" />
                          <span>Approving...</span>
                        </span>
                      ) : (
                        <span>Approve (+150 XP)</span>
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={() => openRejectModal(item.id)}
                      disabled={actionLoadingId === item.id}
                      className="min-h-[44px] px-4 py-2.5 rounded-xl text-sm font-semibold text-red-400 bg-red-950/60 border border-red-800 hover:bg-red-900/60 active:bg-red-800/60 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
          </>
        ) : (
          <div>
            {/* Complaints Navigation Tabs: Pending, Accepted, Rejected */}
            <div className="flex items-center space-x-2 border-b border-slate-700 pb-3 mb-6 overflow-x-auto">
              <button
                type="button"
                onClick={() => setComplaintsTab('pending')}
                className={`min-h-[44px] px-4 py-2 rounded-xl text-sm font-semibold transition-colors cursor-pointer flex items-center space-x-2 shrink-0 ${
                  complaintsTab === 'pending'
                    ? 'bg-blue-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                <span>Pending Review</span>
                {complaintsTab === 'pending' && complaints.length > 0 && (
                  <span className="px-2 py-0.5 rounded-full text-xs bg-blue-700 text-white font-bold">
                    {complaintsTotal}
                  </span>
                )}
              </button>

              <button
                type="button"
                onClick={() => setComplaintsTab('accepted')}
                className={`min-h-[44px] px-4 py-2 rounded-xl text-sm font-semibold transition-colors cursor-pointer flex items-center space-x-2 shrink-0 ${
                  complaintsTab === 'accepted'
                    ? 'bg-emerald-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                <span>Accepted</span>
                {complaintsTab === 'accepted' && complaints.length > 0 && (
                  <span className="px-2 py-0.5 rounded-full text-xs bg-emerald-700 text-white font-bold">
                    {complaintsTotal}
                  </span>
                )}
              </button>

              <button
                type="button"
                onClick={() => setComplaintsTab('rejected')}
                className={`min-h-[44px] px-4 py-2 rounded-xl text-sm font-semibold transition-colors cursor-pointer flex items-center space-x-2 shrink-0 ${
                  complaintsTab === 'rejected'
                    ? 'bg-red-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                <span>Rejected</span>
                {complaintsTab === 'rejected' && complaints.length > 0 && (
                  <span className="px-2 py-0.5 rounded-full text-xs bg-red-700 text-white font-bold">
                    {complaintsTotal}
                  </span>
                )}
              </button>
            </div>

            {/* Complaints Error Alert */}
            {complaintsError && (
              <div className="mb-6 p-4 rounded-xl bg-red-950/70 border border-red-800 text-sm text-red-200 flex items-start space-x-2">
                <svg className="w-5 h-5 text-red-400 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <div className="flex-1">
                  <span>{complaintsError}</span>
                </div>
                <button
                  type="button"
                  onClick={() => fetchComplaints(complaintsTab, 1, false)}
                  className="px-2.5 py-1 bg-red-900 hover:bg-red-800 text-white text-xs font-semibold rounded-md cursor-pointer transition-colors"
                >
                  Retry
                </button>
              </div>
            )}

            {/* Complaints Loading State */}
            {complaintsLoading ? (
              <div className="py-20 flex flex-col items-center justify-center space-y-4">
                <Loader size="lg" />
                <p className="text-sm font-medium text-slate-400">Loading {complaintsTab} complaints...</p>
              </div>
            ) : complaints.length === 0 ? (
              <div className="bg-slate-800/60 rounded-2xl border border-slate-700/60 p-12 text-center max-w-md mx-auto my-12">
                <div className="w-14 h-14 mx-auto rounded-2xl bg-slate-700/50 text-slate-400 flex items-center justify-center mb-4">
                  <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <h3 className="text-lg font-bold text-white mb-1">
                  {complaintsTab === 'pending'
                    ? 'No pending complaints.'
                    : complaintsTab === 'accepted'
                    ? 'No accepted complaints.'
                    : 'No rejected complaints.'}
                </h3>
                <p className="text-sm text-slate-400">
                  {complaintsTab === 'pending'
                    ? 'All submitted citizen complaints have been reviewed.'
                    : `There are currently no complaints in ${complaintsTab} status.`}
                </p>
              </div>
            ) : (
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {complaints.map((item) => (
                    <AuditorComplaintCard
                      key={item.id}
                      item={item}
                      activeTab={complaintsTab}
                      onActionSuccess={handleComplaintActionSuccess}
                    />
                  ))}
                </div>

                {hasMoreComplaints && (
                  <div className="pt-4 pb-8 text-center">
                    <button
                      type="button"
                      onClick={handleLoadMoreComplaints}
                      disabled={complaintsLoadingMore}
                      className="min-h-[44px] inline-flex items-center justify-center px-6 py-3 rounded-xl text-sm font-semibold text-blue-400 bg-slate-800 border border-slate-700 hover:bg-slate-700/80 active:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm cursor-pointer"
                    >
                      {complaintsLoadingMore ? (
                        <span className="flex items-center space-x-2">
                          <Loader size="sm" />
                          <span>Loading more...</span>
                        </span>
                      ) : (
                        <span>Load more ({complaints.length} of {complaintsTotal})</span>
                      )}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Small Rejection Modal asking for reason */}
      {rejectModal.isOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="bg-slate-800 rounded-2xl max-w-md w-full p-6 border border-slate-700 shadow-2xl animate-in fade-in zoom-in duration-150">
            <h3 className="text-lg font-bold text-white mb-1">Reject Submission</h3>
            <p className="text-xs text-slate-400 mb-4">
              Please provide a reason for rejecting this verification photo.
            </p>

            {rejectModal.error && (
              <div className="mb-4 p-3 rounded-xl bg-red-950/80 border border-red-800 text-xs text-red-200">
                {rejectModal.error}
              </div>
            )}

            <form onSubmit={handleConfirmReject} className="space-y-4">
              <div>
                <label htmlFor="reject-reason" className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Reason for rejection <span className="text-red-400">*</span>
                </label>
                <textarea
                  id="reject-reason"
                  rows={3}
                  required
                  autoFocus
                  value={rejectModal.reason}
                  onChange={(e) =>
                    setRejectModal((prev) => ({ ...prev, reason: e.target.value, error: '' }))
                  }
                  placeholder="e.g. Photo does not clearly show the completed work plaque or structure."
                  className="w-full px-3.5 py-2.5 text-sm rounded-xl border border-slate-600 bg-slate-900 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent transition-all shadow-inner"
                />
              </div>

              <div className="flex items-center justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={closeRejectModal}
                  disabled={rejectModal.loading}
                  className="min-h-[44px] px-4 py-2 text-sm font-semibold text-slate-400 hover:text-slate-200 hover:bg-slate-700/60 rounded-xl transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={rejectModal.loading || !rejectModal.reason.trim()}
                  className="min-h-[44px] px-5 py-2 text-sm font-semibold text-white bg-red-600 hover:bg-red-500 active:bg-red-700 rounded-xl shadow-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer flex items-center space-x-2"
                >
                  {rejectModal.loading ? (
                    <>
                      <Loader size="sm" />
                      <span>Rejecting...</span>
                    </>
                  ) : (
                    <span>Confirm Rejection</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
