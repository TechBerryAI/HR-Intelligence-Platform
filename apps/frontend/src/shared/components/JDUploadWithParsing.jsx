import React, { useState, useRef } from 'react';
import { uploadAndParseJDStream, takeJDFormDTO, validateFileForParsing } from '@/core/api/parsingApi.js';
import PremiumUploadOverlay from './PremiumUploadOverlay';
import { motion } from 'framer-motion';
import { FiUpload, FiFile, FiCheck, FiAlertCircle, FiZap } from 'react-icons/fi';

/**
 * Job Description Upload — Document Intelligence Engine.
 * Autofill uses Form DTO only — never raw TOON.
 */
export default function JDUploadWithParsing({ onAutofill, currentJobId }) {
  const [isUploading, setIsUploading] = useState(false);
  const [parseError, setParseError] = useState('');
  const [parseSuccess, setParseSuccess] = useState('');
  const [confidence, setConfidence] = useState(null);
  const [stageLabel, setStageLabel] = useState(null);
  const [progressPct, setProgressPct] = useState(null);
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
    setStageLabel('text');
    setProgressPct(10);
    
    try {
      const onStage = (ev) => {
        if (ev?.stage) setStageLabel(ev.stage);
        const order = ['cache', 'persist_raw', 'layout', 'text', 'sections', 'deterministic', 'semantic', 'knowledge', 'validate', 'persist'];
        const idx = order.indexOf(ev?.stage);
        if (idx >= 0) setProgressPct(Math.round(((idx + 1) / order.length) * 100));
      };

      const result = await uploadAndParseJDStream(file, currentJobId, { onStage });

      if (result.status === 'ok' && result.form) {
        const formData = takeJDFormDTO(result);
        
        // Store confidence and parsed ID
        setConfidence(result.confidence);
        setProgressPct(100);

        const coverage = Array.isArray(formData.coverage)
          ? formData.coverage
          : (Array.isArray(result.coverage) ? result.coverage : []);
        const missingFields = Array.isArray(result.missing_fields)
          ? result.missing_fields
          : coverage
              .filter((c) => c && c.status === 'missing_with_evidence')
              .map((c) => c.field);
        const coreGaps = missingFields.filter((f) =>
          ['title', 'location', 'experience', 'skills', 'description'].includes(f),
        );
        const gapLabels = {
          title: 'Title',
          location: 'Location',
          experience: 'Experience',
          skills: 'Skills',
          description: 'Description',
        };
        
        // Show success / review message based on coverage gaps
        if (coreGaps.length > 0) {
          const labels = coreGaps.map((f) => gapLabels[f] || f).join(', ');
          setParseSuccess('');
          setParseError(
            `Parsed with incomplete fields — please review: ${labels}. Other fields were auto-filled below.`,
          );
        } else if (result.is_duplicate) {
          setParseSuccess('Job description recognized! Using previously parsed data.');
        } else {
          setParseSuccess('Job description parsed successfully! Fields auto-filled below.');
        }

        // Autofill form from Form DTO only
        if (onAutofill) {
          onAutofill({
            ...formData,
            coverage,
            _parsedId: result.parsed_id,
            _rawFileId: result.raw_file_id,
            _confidence: result.confidence,
            _trace: formData.trace || [],
            _missingFields: coreGaps,
          });
        }

        // Show low confidence warning (only if no coverage gap message)
        if (coreGaps.length === 0 && result.confidence < 0.75) {
          setParseError('Parsing confidence is low. Please verify all auto-filled fields.');
        }
      } else {
        throw new Error(result.error || 'Parsing failed');
      }
    } catch (error) {
      if (error.message.includes('Invalid or expired token') || error.message.includes('Access token required')) {
        setParseError('Your session has expired. Please log in again to use AI-powered job description parsing.');
      } else {
        const detail = (error.message || '').trim();
        setParseError(
          detail && !/^failed to parse job description\.?$/i.test(detail)
            ? detail
            : 'Unable to parse this job description. Please try another file or fill the form manually.'
        );
      }
      console.error('JD parsing error:', error);
    } finally {
      setIsUploading(false);
      setStageLabel(null);
      setProgressPct(null);
    }
  };

  return (
    <>
      {/* Premium Upload Overlay */}
      <PremiumUploadOverlay
        isVisible={isUploading}
        type="jd"
        stageLabel={stageLabel}
        progressPct={progressPct}
      />

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="org-ai-panel p-6 mb-6"
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="w-11 h-11 bg-gradient-to-br from-[#7957FF] to-[#00A6FF] rounded-xl flex items-center justify-center shadow-[0_8px_24px_rgba(121,87,255,0.25)]">
            <FiZap className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-[var(--ei-text-primary)]">
              Quick Create from Job Description
            </h3>
            <p className="text-sm text-[var(--ei-text-secondary)]">
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
            className="relative group transition-all duration-200"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.png,.jpg,.jpeg,.webp"
              onChange={handleFileChange}
              disabled={isUploading}
              className="hidden"
              id="jd-upload-input"
            />
            
            <label
              htmlFor="jd-upload-input"
              className={`
                org-upload-zone block p-6 cursor-pointer
                ${isDragging ? 'org-upload-zone-active' : ''}
                ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}
              `}
            >
              <div className="flex flex-col items-center justify-center space-y-3">
                <motion.div
                  animate={isDragging ? {
                    scale: [1, 1.08, 1],
                  } : {}}
                  transition={{ duration: 0.5 }}
                  className="relative"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-[#7957FF] to-[#00A6FF] rounded-full blur-lg opacity-35 group-hover:opacity-55 transition-opacity" />
                  <div className="relative w-11 h-11 bg-gradient-to-br from-[#7957FF] to-[#00A6FF] rounded-full flex items-center justify-center">
                    <FiUpload className="w-5 h-5 text-white" />
                  </div>
                </motion.div>

                <div className="text-center">
                  <p className="text-base font-semibold text-[var(--ei-text-primary)] mb-1">
                    {isDragging ? 'Drop JD file here' : 'Upload Job Description'}
                  </p>
                  <p className="text-xs text-[var(--ei-text-secondary)]">
                    PDF, DOC, DOCX, PNG, JPG, or WEBP • Max 10MB
                  </p>
                  <p className="text-xs text-[var(--ei-text-muted)] mt-1.5">
                    Drag & drop your file here or click to browse
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
              className="border border-[rgba(54,214,160,0.3)] bg-[rgba(54,214,160,0.1)] px-4 py-3 rounded-xl"
            >
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-8 h-8 bg-[#36D6A0] rounded-full flex items-center justify-center">
                  <FiCheck className="w-4 h-4 text-[#0B1118]" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-[#9AE6C8]">{parseSuccess}</p>
                  {confidence !== null && (
                    <div className="mt-2 flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${confidence * 100}%` }}
                          transition={{ duration: 1, ease: 'easeOut' }}
                          className="h-full bg-gradient-to-r from-[#36D6A0] to-emerald-400 rounded-full"
                        />
                      </div>
                      <span className="text-xs font-medium text-[#9AE6C8] min-w-[45px] text-right">
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
              className="border border-amber-400 bg-amber-50 px-4 py-3 rounded-xl"
            >
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-8 h-8 bg-amber-500 rounded-full flex items-center justify-center">
                  <FiAlertCircle className="w-4 h-4 text-white" />
                </div>
                <p className="text-sm text-amber-950 font-medium flex-1">{parseError}</p>
              </div>
            </motion.div>
          )}

          {/* Feature highlights */}
          <div className="grid grid-cols-3 gap-3 pt-2">
            {[
              { icon: FiZap, text: 'Instant Extraction', color: 'text-[#00A6FF]' },
              { icon: FiCheck, text: 'High Accuracy', color: 'text-[#36D6A0]' },
              { icon: FiFile, text: 'Multiple Formats', color: 'text-[#A78BFA]' },
            ].map((feature, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                className="flex flex-col items-center gap-1.5 p-2"
              >
                <feature.icon className={`w-4 h-4 ${feature.color}`} />
                <span className="text-xs text-[var(--ei-text-secondary)] text-center">{feature.text}</span>
              </motion.div>
            ))}
          </div>
        </div>
      </motion.div>
    </>
  );
}
