import React, { useState, useRef } from 'react';
import { uploadAndParseJD, mapJDTOONToForm, validateFileForParsing } from '@/core/api/parsingApi.js';
import PremiumUploadOverlay from './PremiumUploadOverlay';
import { motion } from 'framer-motion';
import { FiUpload, FiFile, FiCheck, FiAlertCircle, FiZap } from 'react-icons/fi';

/**
 * Premium Job Description Upload Component with AI Parsing
 * Uploads JD, parses it, and autofills job form
 */
export default function JDUploadWithParsing({ onAutofill, currentJobId }) {
  const [isUploading, setIsUploading] = useState(false);
  const [parseError, setParseError] = useState('');
  const [parseSuccess, setParseSuccess] = useState('');
  const [confidence, setConfidence] = useState(null);
  const fileInputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

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

    // Check if user is logged in (token stored as 'jwtToken')
    const token = localStorage.getItem('jwtToken');
    if (!token) {
      setParseError('🔒 Please log in first to use AI-powered job description parsing. You can still fill the form manually.');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
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

    // Start AI parsing - show premium overlay
    setIsUploading(true);
    
    try {
      // Call parsing API
      const result = await uploadAndParseJD(file, currentJobId);

      if (result.status === 'ok' && result.toon) {
        // Map TOON to form fields
        const formData = mapJDTOONToForm(result.toon);
        
        // Store confidence and parsed ID
        setConfidence(result.confidence);
        
        // Show success message
        if (result.is_duplicate) {
          setParseSuccess('✨ Job description recognized! Using previously parsed data.');
        } else {
          setParseSuccess('✨ Job description parsed successfully! Fields auto-filled below.');
        }

        // Autofill form
        if (onAutofill) {
          onAutofill({
            ...formData,
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
        setParseError('🔒 Your session has expired. Please log in again to use AI-powered job description parsing.');
      } else if (error.message.includes('Failed to parse job description')) {
        setParseError('❌ Unable to parse job description. The file may be corrupted or in an unsupported format. Please try another file or fill the form manually.');
      } else {
        setParseError(`❌ Parsing error: ${error.message}`);
      }
      console.error('JD parsing error:', error);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <>
      {/* Premium Upload Overlay */}
      <PremiumUploadOverlay isVisible={isUploading} type="jd" />

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-6 rounded-2xl border-2 border-purple-500/30 bg-gradient-to-br from-purple-500/10 to-blue-500/10 mb-6"
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 bg-gradient-to-r from-purple-600 to-blue-600 rounded-xl flex items-center justify-center shadow-glow">
            <FiZap className="w-6 h-6 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">
              Quick Create from Job Description
            </h3>
            <p className="text-sm text-zinc-400">
              Upload a JD and let AI extract all the details
            </p>
          </div>
        </div>
        
        <div className="space-y-4">
          {/* Premium drag & drop upload area */}
          <motion.div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            className={`relative group transition-all duration-300 ${
              isDragging
                ? 'scale-105 ring-4 ring-purple-500/50'
                : 'hover:scale-[1.01]'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx"
              onChange={handleFileChange}
              disabled={isUploading}
              className="hidden"
              id="jd-upload-input"
            />
            
            <label
              htmlFor="jd-upload-input"
              className={`
                block p-6 rounded-xl cursor-pointer
                border-2 border-dashed transition-all duration-300 bg-white/5
                ${isDragging 
                  ? 'border-purple-400 bg-purple-500/20' 
                  : 'border-zinc-700 hover:border-purple-500/50 hover:bg-white/10'
                }
                ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}
              `}
            >
              <div className="flex flex-col items-center justify-center space-y-3">
                {/* Animated upload icon */}
                <motion.div
                  animate={isDragging ? {
                    scale: [1, 1.2, 1],
                  } : {}}
                  transition={{ duration: 0.5 }}
                  className="relative"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-purple-600 to-blue-600 rounded-full blur-lg opacity-40 group-hover:opacity-60 transition-opacity" />
                  <div className="relative w-12 h-12 bg-gradient-to-r from-purple-600 to-blue-600 rounded-full flex items-center justify-center">
                    <FiUpload className="w-6 h-6 text-white" />
                  </div>
                </motion.div>

                <div className="text-center">
                  <p className="text-base font-semibold text-white mb-1">
                    {isDragging ? 'Drop JD file here' : 'Upload Job Description'}
                  </p>
                  <p className="text-xs text-zinc-400">
                    PDF, DOC, or DOCX • Max 10MB
                  </p>
                </div>
              </div>
            </label>
          </motion.div>

          {/* Success message */}
          {parseSuccess && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              className="glass-card border-2 border-green-500/30 bg-green-500/10 px-4 py-3 rounded-xl"
            >
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                  <FiCheck className="w-4 h-4 text-white" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-green-300">{parseSuccess}</p>
                  {confidence !== null && (
                    <div className="mt-2 flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${confidence * 100}%` }}
                          transition={{ duration: 1, ease: 'easeOut' }}
                          className="h-full bg-gradient-to-r from-green-400 to-emerald-500 rounded-full"
                        />
                      </div>
                      <span className="text-xs font-medium text-green-300 min-w-[45px] text-right">
                        {(confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}

          {/* Error message */}
          {parseError && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              className="glass-card border-2 border-yellow-500/30 bg-yellow-500/10 px-4 py-3 rounded-xl"
            >
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-8 h-8 bg-yellow-500 rounded-full flex items-center justify-center">
                  <FiAlertCircle className="w-4 h-4 text-white" />
                </div>
                <p className="text-sm text-yellow-300 flex-1">{parseError}</p>
              </div>
            </motion.div>
          )}

          {/* Feature highlights */}
          <div className="grid grid-cols-3 gap-3 pt-2">
            {[
              { icon: FiZap, text: 'Instant Extraction' },
              { icon: FiCheck, text: 'High Accuracy' },
              { icon: FiFile, text: 'All Formats' },
            ].map((feature, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                className="flex flex-col items-center gap-1 p-2 bg-white/5 rounded-lg"
              >
                <feature.icon className="w-4 h-4 text-purple-400" />
                <span className="text-xs text-zinc-400">{feature.text}</span>
              </motion.div>
            ))}
          </div>
        </div>
      </motion.div>
    </>
  );
}
