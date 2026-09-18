import { useState, useRef } from 'react';
import api from '../api/client';
import Loader from './Loader';

const MAX_SIZE_MB = 8;
const MAX_BYTES = MAX_SIZE_MB * 1024 * 1024;

export default function UploadButton({ workId, status, onSuccess }) {
  const fileInputRef = useRef(null);

  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState('');

  // Hide button if status is pending or approved
  if (status === 'pending' || status === 'approved') {
    return null;
  }

  const isRetake = status === 'rejected';

  // Trigger file selection (back camera on mobile)
  const handleButtonClick = () => {
    setError('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
      fileInputRef.current.click();
    }
  };

  // Handle selected file
  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Check size limit
    if (file.size > MAX_BYTES) {
      setError(`Selected photo is too large (${(file.size / (1024 * 1024)).toFixed(1)}MB). Maximum allowed is ${MAX_SIZE_MB}MB.`);
      setShowModal(true);
      setSelectedFile(null);
      setPreviewUrl(null);
      return;
    }

    setSelectedFile(file);
    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);
    setError('');
    setShowModal(true);
  };

  // Close modal and clean up preview URL
  const handleClose = () => {
    if (uploading) return;
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setSelectedFile(null);
    setShowModal(false);
    setError('');
    setUploadProgress(0);
  };

  // Retake photo: open file picker again
  const handleRetake = () => {
    if (uploading) return;
    handleClose();
    setTimeout(() => {
      handleButtonClick();
    }, 100);
  };

  // Best-effort GPS capture
  const getGpsPosition = () => {
    return new Promise((resolve) => {
      if (!navigator.geolocation) {
        return resolve(null);
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        () => resolve(null),
        { timeout: 3000, enableHighAccuracy: true, maximumAge: 60000 }
      );
    });
  };

  // Upload submission
  const handleUpload = async () => {
    if (!selectedFile) return;

    setError('');
    setUploading(true);
    setUploadProgress(10);

    try {
      // 1. Best-effort GPS
      const coords = await getGpsPosition();
      setUploadProgress(25);

      // 2. Prepare FormData
      const formData = new FormData();
      formData.append('photo', selectedFile);
      if (coords?.lat != null && coords?.lng != null) {
        formData.append('lat', coords.lat);
        formData.append('lng', coords.lng);
      }

      // 3. Post to /works/{id}/submissions with progress tracking
      const res = await api.post(`/works/${workId}/submissions`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percent = Math.round((progressEvent.loaded * 70) / progressEvent.total) + 25;
            setUploadProgress(Math.min(percent, 95));
          }
        },
      });

      setUploadProgress(100);

      // Notify parent component
      if (onSuccess) {
        onSuccess(res.data);
      }

      // Close modal
      handleClose();
    } catch (err) {
      if (err.response?.status === 409) {
        setError('You have already submitted a verification photo for this project.');
      } else if (err.response?.status === 400) {
        setError(err.response?.data?.detail || 'Invalid photo format or file too large.');
      } else if (err.response?.status === 403) {
        setError(err.response?.data?.detail || 'This work does not match your location.');
      } else {
        setError(err.response?.data?.detail || 'Failed to upload photo. Please try again.');
      }
    } finally {
      setUploading(false);
    }
  };

  return (
    <>
      {/* Hidden file input with environment (back) camera capture for mobile phones */}
      <input
        type="file"
        ref={fileInputRef}
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={handleFileChange}
      />

      {/* Trigger Button */}
      <button
        type="button"
        onClick={handleButtonClick}
        className={`inline-flex items-center justify-center min-h-[44px] px-3.5 py-1.5 rounded-xl text-xs font-semibold shadow-xs transition-colors cursor-pointer ${
          isRetake
            ? 'bg-amber-50 text-amber-800 border border-amber-300 hover:bg-amber-100 active:bg-amber-200'
            : 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800'
        }`}
        title={isRetake ? 'Retake verification photo' : 'Upload proof photo for this work'}
      >
        <svg
          className="w-4 h-4 mr-1.5 shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
          />
        </svg>
        <span>{isRetake ? 'Retake' : 'Upload pic'}</span>
      </button>

      {/* Photo Preview & Submission Modal */}
      {showModal && (
        <div
          className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-headline"
        >
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-100 animate-in fade-in zoom-in duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <h3 id="modal-headline" className="text-base sm:text-lg font-bold text-slate-900 flex items-center">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-600 mr-2"></span>
                Verify Work Photo
              </h3>
              {!uploading && (
                <button
                  type="button"
                  onClick={handleClose}
                  className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
                  title="Close modal"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>

            {/* Error Message */}
            {error && (
              <div className="mb-4 p-3.5 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700 flex items-start space-x-2">
                <svg className="w-5 h-5 text-red-500 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                    clipRule="evenodd"
                  />
                </svg>
                <span>{error}</span>
              </div>
            )}

            {/* Image Preview */}
            {previewUrl && (
              <div className="mb-4">
                <div className="relative rounded-xl overflow-hidden bg-slate-100 border border-slate-200 aspect-4/3 flex items-center justify-center">
                  <img
                    src={previewUrl}
                    alt="Work verification preview"
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="flex items-center justify-between text-xs text-slate-500 mt-2 px-1">
                  <span className="truncate max-w-[200px]">{selectedFile?.name}</span>
                  <span>{(selectedFile?.size / (1024 * 1024)).toFixed(2)} MB</span>
                </div>
              </div>
            )}

            {/* Upload Progress Bar */}
            {uploading && (
              <div className="mb-4">
                <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1.5">
                  <span className="flex items-center space-x-1.5">
                    <Loader size="sm" />
                    <span>Uploading photo...</span>
                  </span>
                  <span>{uploadProgress}%</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
                  <div
                    className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  ></div>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex items-center justify-end space-x-3 pt-2">
              <button
                type="button"
                onClick={handleRetake}
                disabled={uploading}
                className="min-h-[44px] px-4 py-2 text-sm font-semibold text-slate-700 hover:text-slate-900 hover:bg-slate-100 rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                Retake
              </button>

              {previewUrl && (
                <button
                  type="button"
                  onClick={handleUpload}
                  disabled={uploading}
                  className="min-h-[44px] px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 rounded-xl shadow-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer flex items-center space-x-2"
                >
                  {uploading ? (
                    <>
                      <Loader size="sm" />
                      <span>Sending...</span>
                    </>
                  ) : (
                    <span>Send</span>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
