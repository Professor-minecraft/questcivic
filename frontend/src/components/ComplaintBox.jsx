import { useState, useRef } from 'react';
import api from '../api/client';
import Loader from './Loader';

const MAX_SIZE_MB = 8;
const MAX_BYTES = MAX_SIZE_MB * 1024 * 1024;

export default function ComplaintBox() {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [comment, setComment] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > MAX_BYTES) {
      setError(`Selected photo is too large (${(file.size / (1024 * 1024)).toFixed(1)}MB). Maximum allowed is ${MAX_SIZE_MB}MB.`);
      setSelectedFile(null);
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
      setPreviewUrl(null);
      return;
    }

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setError('');
    setSuccessMessage('');
  };

  const handleRetake = () => {
    if (uploading) return;
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
      fileInputRef.current.click();
    }
  };

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

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!selectedFile || comment.trim().length < 10 || uploading) return;

    setError('');
    setSuccessMessage('');
    setUploading(true);
    setUploadProgress(15);

    try {
      const coords = await getGpsPosition();
      setUploadProgress(30);

      const formData = new FormData();
      formData.append('photo', selectedFile);
      formData.append('comment', comment.trim());
      if (coords?.lat != null && coords?.lng != null) {
        formData.append('lat', coords.lat);
        formData.append('lng', coords.lng);
      }

      await api.post('/complaints', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percent = Math.round((progressEvent.loaded * 65) / progressEvent.total) + 30;
            setUploadProgress(Math.min(percent, 95));
          }
        },
      });

      setUploadProgress(100);

      // Clean up preview
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
      setSelectedFile(null);
      setPreviewUrl(null);
      setComment('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      setSuccessMessage('Complaint sent. You will get 50 XP if the auditor accepts it.');
      setIsOpen(false);
    } catch (err) {
      if (err.response?.status === 409) {
        setError(err.response?.data?.detail || 'You already have too many pending complaints. Maximum allowed is 3.');
      } else if (err.response?.status === 400) {
        setError(err.response?.data?.detail || 'Location not set or invalid photo file.');
      } else if (err.response?.status === 413) {
        setError('Photo is too large. Maximum size allowed is 8MB.');
      } else {
        setError(err.response?.data?.detail || 'Failed to submit complaint. Please try again.');
      }
    } finally {
      setUploading(false);
    }
  };

  const canSubmit = Boolean(selectedFile && comment.trim().length >= 10);

  const renderFormContent = (idPrefix = 'desktop') => (
    <form onSubmit={handleSubmit} className="flex flex-col flex-1">
      {/* Title & Description */}
      <div>
        <h2 className="text-lg sm:text-xl font-bold text-white tracking-tight">
          Report damaged infrastructure
        </h2>
        <p className="text-xs sm:text-sm text-red-100 mt-1 leading-relaxed">
          Upload a photo and tell us what needs repair. Earn 50 XP if accepted.
        </p>
      </div>

      {/* Success Notification */}
      {successMessage && (
        <div className="mt-3 p-3 bg-emerald-700/90 border border-emerald-400/50 rounded-xl text-white text-xs sm:text-sm flex items-start space-x-2 shadow-sm">
          <svg className="w-5 h-5 text-emerald-300 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
          </svg>
          <div className="flex-1">
            <p className="font-semibold">{successMessage}</p>
          </div>
          <button
            type="button"
            onClick={() => setSuccessMessage('')}
            className="text-emerald-200 hover:text-white p-0.5 cursor-pointer leading-none"
            aria-label="Dismiss message"
          >
            ✕
          </button>
        </div>
      )}

      {/* Error Notification */}
      {error && (
        <div className="mt-3 p-3 bg-red-800/90 border border-white/30 rounded-xl text-white text-xs sm:text-sm flex items-start space-x-2 shadow-sm">
          <svg className="w-4 h-4 text-white shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span className="flex-1">{error}</span>
          <button
            type="button"
            onClick={() => setError('')}
            className="text-white/80 hover:text-white p-0.5 cursor-pointer leading-none"
            aria-label="Dismiss error"
          >
            ✕
          </button>
        </div>
      )}

      {/* Photo Picker or Preview */}
      <div className="mt-4">
        {!selectedFile ? (
          <button
            type="button"
            onClick={() => {
              setError('');
              if (fileInputRef.current) {
                fileInputRef.current.value = '';
                fileInputRef.current.click();
              }
            }}
            disabled={uploading}
            className="w-full bg-white text-red-600 hover:bg-red-50 active:bg-red-100 font-semibold text-sm px-4 py-3 rounded-xl min-h-[44px] flex items-center justify-center space-x-2 shadow-xs transition-colors cursor-pointer disabled:opacity-50"
          >
            <svg className="w-5 h-5 text-red-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span>Take photo</span>
          </button>
        ) : (
          <div className="space-y-2">
            <div className="relative rounded-xl overflow-hidden border border-white/20 bg-red-700/60">
              <img
                src={previewUrl}
                alt="Damage preview"
                className="w-full h-36 object-cover"
              />
            </div>
            <button
              type="button"
              onClick={handleRetake}
              disabled={uploading}
              className="w-full bg-white text-red-600 hover:bg-red-50 font-semibold text-xs sm:text-sm py-2 px-3 rounded-xl min-h-[44px] flex items-center justify-center space-x-1.5 transition-colors cursor-pointer disabled:opacity-50 shadow-xs"
            >
              <svg className="w-4 h-4 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>Retake photo</span>
            </button>
          </div>
        )}
      </div>

      {/* Description Textarea */}
      <div className="mt-4">
        <label htmlFor={`${idPrefix}-comment`} className="block text-xs font-semibold text-white mb-1.5">
          Describe the damage and what should be repaired
        </label>
        <textarea
          id={`${idPrefix}-comment`}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Describe the damage and what should be repaired"
          rows={4}
          maxLength={500}
          disabled={uploading}
          className="w-full p-3 rounded-xl bg-white text-slate-800 placeholder-slate-400 text-xs sm:text-sm border-0 focus:ring-2 focus:ring-white focus:outline-none resize-none shadow-xs disabled:opacity-60"
        />
        <div className="flex justify-between items-center text-xs text-red-100 mt-1">
          <span>Min 10 characters</span>
          <span className={comment.trim().length >= 10 ? 'font-bold text-white' : 'text-red-200'}>
            {comment.length}/500
          </span>
        </div>
      </div>

      {/* Upload Progress Bar */}
      {uploading && (
        <div className="mt-4 space-y-1.5">
          <div className="flex justify-between text-xs font-medium text-white">
            <span>Uploading complaint...</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="w-full bg-red-800/80 rounded-full h-2 overflow-hidden">
            <div
              className="bg-white h-2 rounded-full transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Submit Button */}
      <div className="mt-5">
        <button
          type="submit"
          disabled={!canSubmit || uploading}
          className="w-full bg-white text-red-600 hover:bg-red-50 active:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed font-bold text-sm sm:text-base py-3 px-4 rounded-xl min-h-[44px] flex items-center justify-center space-x-2 shadow-md transition-all cursor-pointer"
        >
          {uploading ? (
            <>
              <Loader size="sm" />
              <span>Submitting... {uploadProgress}%</span>
            </>
          ) : (
            <span>Submit complaint</span>
          )}
        </button>
      </div>
    </form>
  );

  return (
    <>
      {/* Hidden File Input (shared for both desktop and mobile buttons) */}
      <input
        type="file"
        accept="image/*"
        capture="environment"
        ref={fileInputRef}
        onChange={handleFileChange}
        className="hidden"
      />

      {/* Desktop Panel: Fixed on the left, always visible on lg (>=1024px) */}
      <aside
        className="hidden lg:flex fixed top-20 left-4 xl:left-8 w-80 xl:w-88 max-h-[calc(100vh-6rem)] overflow-y-auto bg-red-600 text-white rounded-2xl shadow-xl p-5 sm:p-6 flex-col z-20"
        aria-label="Report damaged infrastructure panel"
      >
        {renderFormContent('desktop')}
      </aside>

      {/* Mobile & Tablet Tab: Fixed on left edge in middle of screen (<1024px) */}
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="lg:hidden fixed left-0 top-1/2 -translate-y-1/2 z-40 bg-red-600 hover:bg-red-700 active:bg-red-800 text-white font-bold text-xs sm:text-sm tracking-wider px-2.5 py-4 rounded-r-xl shadow-xl transition-all cursor-pointer flex items-center justify-center min-h-[44px] min-w-[44px]"
        style={{ writingMode: 'vertical-rl', textOrientation: 'mixed' }}
        aria-label="Complaint"
      >
        Complaint
      </button>

      {/* Mobile Drawer Overlay */}
      {isOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/60 backdrop-blur-xs z-40 transition-opacity"
          onClick={() => setIsOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Mobile Drawer */}
      <div
        className={`lg:hidden fixed inset-y-0 left-0 z-50 w-[90vw] max-w-[340px] sm:max-w-md bg-red-600 text-white shadow-2xl overflow-y-auto transition-transform duration-300 ease-in-out transform ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        } p-5 sm:p-6 flex flex-col`}
        role="dialog"
        aria-modal="true"
        aria-label="Report damaged infrastructure"
      >
        {/* Close Button Header for Mobile */}
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-white/20">
          <span className="text-xs font-semibold uppercase tracking-wider text-red-100">
            Citizen Complaint
          </span>
          <button
            type="button"
            onClick={() => setIsOpen(false)}
            className="min-h-[44px] min-w-[44px] -mr-2 p-2 text-white hover:text-red-100 hover:bg-red-700/50 rounded-lg flex items-center justify-center transition-colors cursor-pointer"
            aria-label="Close drawer"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {renderFormContent('mobile')}
      </div>
    </>
  );
}
