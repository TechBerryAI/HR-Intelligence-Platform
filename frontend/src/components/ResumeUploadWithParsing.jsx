import React, { useState, useRef, useEffect } from 'react';
import { uploadAndParseResume, mapResumeTOONToForm, validateFileForParsing } from '../utils/parsingApi';
import PremiumUploadOverlay from './PremiumUploadOverlay';
import { motion } from 'framer-motion';
import { FiUpload, FiFile, FiCheck, FiAlertCircle } from 'react-icons/fi';
import { useApp } from '../context/AppContext';
import { tokenService } from '../utils/tokenService';

/**
 * Premium Resume Upload Component with AI Parsing
 * Uploads resume, parses it, and autofills form
 */
export default function ResumeUploadWithParsing({ onAutofill, onFileSelect, currentFileName }) {
  const { applicantAuth } = useApp();
  const [isUploading, setIsUploading] = useState(false);
  const [parseError, setParseError] = useState('');
  const [parseSuccess, setParseSuccess] = useState('');
  const [confidence, setConfidence] = useState(null);
  const fileInputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  // Clear any stale error messages on mount
  useEffect(() => {
    // Clear login-related errors on mount
    setParseError('');
  }, []);

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    await processFile(file);
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      await processFile(file);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const processFile = async (file) => {
    // Clear previous messages
    setParseError('');
    setParseSuccess('');
    setConfidence(null);

    // Check if user is logged in using token service
    const token = tokenService.getToken();
    if (!token || !applicantAuth.isLoggedIn) {
      // Allow manual file selection even if not logged in (no AI parsing)
      if (onFileSelect) {
        onFileSelect(file);
      }
      // Silently allow manual upload without showing error
      return;
    }

    // Validate file
    const validation = validateFileForParsing(file);
    if (!validation.valid) {
      setParseError(validation.error);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      return;
    }

    // Notify parent of file selection (for traditional upload)
    if (onFileSelect) {
      onFileSelect(file);
    }

    // Start AI parsing - show premium overlay
    setIsUploading(true);
    
    try {
      // Call parsing API
      const result = await uploadAndParseResume(file);

      if (result.status === 'ok' && result.toon) {
        // Map TOON to form fields
        const formData = mapResumeTOONToForm(result.toon);
        
        // Store confidence and parsed ID
        setConfidence(result.confidence);
        
        // Show success message
        if (result.is_duplicate) {
          setParseSuccess('✨ Resume recognized! Using previously parsed data.');
        } else {
          setParseSuccess('✨ Resume parsed successfully! Fields auto-filled below.');
        }

        // Autofill form
        if (onAutofill) {
          onAutofill({
            ...formData,
            resumeFile: file,
            resumeFileName: file.name,
            _parsedId: result.parsed_id,
            _rawFileId: result.raw_file_id,
            _confidence: result.confidence,
          });
        }

        // Show low confidence warning
        if (result.confidence < 0.75) {
          setParseError('⚠️ Parsing confidence is low. Please verify all auto-filled fields.');
        }
      } else {
        throw new Error(result.error || 'Parsing failed');
      }
    } catch (error) {
      // Provide better error messages based on error type
      if (error.message.includes('Invalid or expired token') || error.message.includes('Access token required')) {
        // Don't show login errors - user can still upload manually
        console.warn('Session expired, allowing manual upload');
      } else if (error.message.includes('Failed to parse resume')) {
        setParseError('❌ Unable to parse resume. The file may be corrupted or in an unsupported format. Please try another file or fill the form manually.');
      } else {
        setParseError(`❌ Parsing error: ${error.message}`);
      }
      console.error('Resume parsing error:', error);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <>
      {/* Premium Upload Overlay */}
      <PremiumUploadOverlay isVisible={isUploading} type="resume" />

      <div className="space-y-4">
        {/* Premium drag & drop upload area */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={`relative group transition-all duration-300 ${
            isDragging
              ? 'scale-105 ring-4 ring-purple-500/50'
              : 'hover:scale-[1.02]'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.doc,.docx"
            onChange={handleFileChange}
            disabled={isUploading}
            className="hidden"
            id="resume-upload-input"
          />
          
          <label
            htmlFor="resume-upload-input"
            className={`
              block glass-card p-8 rounded-2xl cursor-pointer
              border-2 border-dashed transition-all duration-300
              ${isDragging 
                ? 'border-purple-500 bg-purple-500/10' 
                : 'border-zinc-700 hover:border-purple-500/50 hover:bg-white/10'
              }
              ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <div className="flex flex-col items-center justify-center space-y-4">
              {/* Animated upload icon */}
              <motion.div
                animate={isDragging ? {
                  scale: [1, 1.2, 1],
                  rotate: [0, 10, -10, 0],
                } : {}}
                transition={{ duration: 0.5 }}
                className="relative"
              >
                <div className="absolute inset-0 bg-gradient-to-r from-purple-600 to-blue-600 rounded-full blur-xl opacity-50 group-hover:opacity-75 transition-opacity" />
                <div className="relative w-16 h-16 bg-gradient-to-r from-purple-600 to-blue-600 rounded-full flex items-center justify-center shadow-glow">
                  <FiUpload className="w-8 h-8 text-white" />
                </div>
              </motion.div>

              <div className="text-center">
                <p className="text-lg font-semibold text-white mb-1">
                  {isDragging ? 'Drop your resume here' : 'Upload Your Resume'}
                </p>
                <p className="text-sm text-zinc-400">
                  Drag & drop or click to browse
                </p>
              </div>

              <div className="flex items-center gap-4 text-xs text-zinc-500">
                <div className="flex items-center gap-1">
                  <FiFile className="w-4 h-4" />
                  <span>PDF, DOC, DOCX</span>
                </div>
                <div className="w-1 h-1 bg-zinc-600 rounded-full" />
                <span>Max 10MB</span>
              </div>

              {/* AI Badge */}
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.2 }}
                className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600/20 to-blue-600/20 rounded-full border border-purple-500/30"
              >
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                <span className="text-xs font-medium text-purple-300">
                  AI-Powered Parsing
                </span>
              </motion.div>
            </div>
          </label>
        </motion.div>

        {/* Success message */}
        {parseSuccess && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className="glass-card border-2 border-green-500/30 bg-green-500/10 px-5 py-4 rounded-xl"
          >
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-10 h-10 bg-green-500 rounded-full flex items-center justify-center shadow-glow">
                <FiCheck className="w-5 h-5 text-white" />
              </div>
              <div className="flex-1">
                <p className="font-semibold text-green-300">{parseSuccess}</p>
                {confidence !== null && (
                  <div className="mt-2 flex items-center gap-2">
                    <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${confidence * 100}%` }}
                        transition={{ duration: 1, ease: 'easeOut' }}
                        className="h-full bg-gradient-to-r from-green-400 to-emerald-500 rounded-full"
                      />
                    </div>
                    <span className="text-xs font-medium text-green-300 min-w-[50px] text-right">
                      {(confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {/* Error message - only show if it's not a login prompt */}
        {parseError && !parseError.includes('log in') && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className="glass-card border-2 border-yellow-500/30 bg-yellow-500/10 px-5 py-4 rounded-xl"
          >
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-10 h-10 bg-yellow-500 rounded-full flex items-center justify-center">
                <FiAlertCircle className="w-5 h-5 text-white" />
              </div>
              <p className="text-sm text-yellow-300 flex-1">{parseError}</p>
            </div>
          </motion.div>
        )}

        {/* Current file indicator */}
        {currentFileName && !parseSuccess && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2 text-sm text-zinc-400"
          >
            <FiFile className="w-4 h-4" />
            <span>Current file: <span className="font-medium text-zinc-300">{currentFileName}</span></span>
          </motion.div>
        )}
      </div>
    </>
  );
}
