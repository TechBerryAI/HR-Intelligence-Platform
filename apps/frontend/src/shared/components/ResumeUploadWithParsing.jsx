import React, { useState, useRef, useEffect } from 'react';
import {
  uploadAndParseResumeStream,
  uploadAndParseResumePublicStream,
  takeResumeFormDTO,
  validateFileForParsing,
  extractParseErrorMessage,
  startParseClock,
  reportClientParseTiming,
} from '@/core/api/parsingApi.js';
import { hintForStage, isPipelineComplete, overlayCatchupMs, overlayStepIndex, progressPctForStage, createStageClock } from '@/shared/utils/parsePipelineProgress.js';
import PremiumUploadOverlay from './PremiumUploadOverlay';
import { motion, AnimatePresence } from 'framer-motion';
import { FiUpload, FiFile, FiCheck, FiAlertCircle, FiExternalLink, FiTrash2 } from 'react-icons/fi';
import { tokenService } from '@/core/auth/tokenService.js';
import { useTheme } from '@/core/context/ThemeContext.jsx';

function humanizeParseError(raw) {
  const detail = extractParseErrorMessage(raw, '').trim();
  if (!detail) {
    return 'Unable to parse this resume. Please try another file or fill the form manually.';
  }
  if (/^failed to parse resume\.?$/i.test(detail) || /^parse failed\.?$/i.test(detail)) {
    return 'Unable to parse this resume. Please try another file or fill the form manually.';
  }
  if (
    /failed to fetch/i.test(detail) ||
    /^network error$/i.test(detail) ||
    /networkerror/i.test(detail) ||
    /failed to reach parse api/i.test(detail)
  ) {
    return 'Could not reach the parser. Confirm the backend is running on port 3000, then try the resume again.';
  }
  return detail;
}

/**
 * Premium Resume Upload Component with Document Intelligence Engine parsing.
 * publicMode: use unauthenticated /api/parse/resume/public (apply form).
 * Autofill uses Form DTO only — never raw TOON.
 */
export default function ResumeUploadWithParsing({
  onAutofill,
  onFileSelect,
  onParseComplete,
  currentFileName,
  onRemove,
  onOpenResume,
  onParseError,
  publicMode = false,
}) {
  const [isUploading, setIsUploading] = useState(false);
  const [parseError, setParseError] = useState('');
  const [parseSuccess, setParseSuccess] = useState('');
  const [confidence, setConfidence] = useState(null);
  const [stageLabel, setStageLabel] = useState(null);
  const [stageMessage, setStageMessage] = useState(null);
  const [progressPct, setProgressPct] = useState(null);
  const [overlayGroupMs, setOverlayGroupMs] = useState([0, 0, 0, 0]);
  const fileInputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const { theme } = useTheme();

  useEffect(() => {
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

  const handleRemove = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setParseSuccess('');
    setParseError('');
    setConfidence(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    onRemove?.();
  };

  const processFile = async (file) => {
    setParseError('');
    setParseSuccess('');
    setConfidence(null);

    const token = tokenService.getToken();
    if (!publicMode && !token) {
      if (onFileSelect) onFileSelect(file);
      return;
    }

    const validation = validateFileForParsing(file);
    if (!validation.valid) {
      setParseError(validation.error);
      onParseError?.(validation.error);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      return;
    }

    if (onFileSelect) {
      onFileSelect(file);
    }

    setIsUploading(true);
    setOverlayGroupMs([0, 0, 0, 0]);
    setStageLabel('upload');
    setStageMessage('Uploading resume');
    setProgressPct(4);
    let lastStage = 'upload';
    const clock = startParseClock();
    const stageClock = createStageClock();
    
    try {
      const onStage = (ev) => {
        stageClock.onEvent(ev);
        if (ev?.stage) {
          lastStage = ev.stage;
          setStageLabel(ev.stage);
          setStageMessage(hintForStage(ev.stage, ev.message));
          const g = overlayStepIndex('resume', ev.stage);
          const ms = Number(ev.duration_ms ?? ev.detail?.duration_ms);
          if (
            g >= 0 &&
            Number.isFinite(ms) &&
            ['completed', 'failed', 'skipped'].includes(String(ev.status || '').toLowerCase())
          ) {
            setOverlayGroupMs((prev) => {
              const next = [...prev];
              next[g] = (Number(next[g]) || 0) + ms;
              return next;
            });
          }
        }
        const pct = progressPctForStage('resume', ev?.stage);
        if (pct != null) setProgressPct((prev) => Math.max(prev ?? 0, pct));
        if (isPipelineComplete(ev)) setProgressPct(100);
      };

      clock.markFetch();
      const result = publicMode
        ? await uploadAndParseResumePublicStream(file, { onStage, onFirstChunk: clock.markFirstChunk })
        : await uploadAndParseResumeStream(file, null, { onStage, onFirstChunk: clock.markFirstChunk });
      clock.markResult();

      if (result.status === 'ok' && result.form) {
        const formData = takeResumeFormDTO(result);
        setConfidence(result.confidence);
        setProgressPct(100);
        setStageLabel('persist');
        setStageMessage(hintForStage('persist'));
        await new Promise((r) => setTimeout(r, overlayCatchupMs('resume', lastStage)));

        const coverage = Array.isArray(formData.coverage)
          ? formData.coverage
          : (Array.isArray(result.coverage) ? result.coverage : []);
        const missingFields = Array.isArray(result.missing_fields)
          ? result.missing_fields
          : coverage
              .filter((c) => c && c.status === 'missing_with_evidence')
              .map((c) => c.field);
        const coreGaps = missingFields.filter((f) =>
          ['fullName', 'email', 'phone', 'location', 'education', 'experience'].includes(f),
        );
        const gapLabels = {
          fullName: 'Name',
          email: 'Email',
          phone: 'Phone',
          location: 'Location',
          education: 'Education',
          experience: 'Experience',
        };

        onParseComplete?.(result, null);

        if (coreGaps.length > 0) {
          const labels = coreGaps.map((f) => gapLabels[f] || f).join(', ');
          setParseSuccess('');
          setParseError(
            `Parsed with incomplete fields — please review: ${labels}. Other fields were auto-filled below.`,
          );
          onParseError?.(
            `Parsed with incomplete fields — please review: ${labels}. Other fields were auto-filled below.`,
          );
        } else if (result.is_duplicate) {
          setParseSuccess('Resume recognized! Using previously parsed data.');
          setParseError('');
          onParseError?.(null);
        } else {
          const modelInfo = result.model_version ? ` (${result.model_version})` : '';
          setParseSuccess(`Resume parsed successfully! Fields auto-filled below.${modelInfo}`);
          setParseError('');
          onParseError?.(null);
        }

        if (onAutofill) {
          onAutofill({
            ...formData,
            coverage,
            resumeFile: file,
            resumeFileName: file.name,
            _parsedId: result.parsed_id,
            _rawFileId: result.raw_file_id,
            _publicUploaderId: result.public_uploader_id || null,
            _confidence: result.confidence,
            _modelVersion: result.model_version,
            _trace: formData.trace || [],
          });
        }
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        clock.addStageSpans(stageClock.getSpans());
        await reportClientParseTiming(result, clock);

        // Low-confidence warning only when no named coverage gaps (JD parity)
        if (coreGaps.length === 0 && (result.partial || result.confidence < 0.75)) {
          const mv = String(result.model_version || '');
          if (mv.includes('text-fallback')) {
            setParseError(
              'AI model unavailable; used rules-based parse — please verify all auto-filled fields.'
            );
          } else if (result.partial) {
            setParseError('Parsing was partial. Please verify all auto-filled fields.');
          } else {
            setParseError('Parsing confidence is low. Please verify all auto-filled fields.');
          }
        }
      } else {
        onParseComplete?.(result, result.error || 'Parsing failed');
        throw new Error(extractParseErrorMessage(result, 'Parsing failed'));
      }
    } catch (error) {
      const raw = error?.message || String(error || '');
      onParseComplete?.(null, raw);
      if (raw.includes('Invalid or expired token') || raw.includes('Access token required')) {
        console.warn('Session expired, allowing manual upload');
        if (onFileSelect) onFileSelect(file);
      } else {
        const message = humanizeParseError(raw);
        setParseSuccess('');
        setParseError(message);
        onParseError?.(message);
        // Clear selected file so Apply doesn't look successful without a parsedId
        if (fileInputRef.current) fileInputRef.current.value = '';
        onRemove?.();
      }
      console.error('Resume parsing error:', error);
    } finally {
      setIsUploading(false);
      setStageLabel(null);
      setStageMessage(null);
      setProgressPct(null);
    }
  };

  const hasResume = currentFileName && currentFileName.trim() && !isUploading;
  const light = theme === 'light';

  return (
    <>
      <PremiumUploadOverlay
        isVisible={isUploading}
        type="resume"
        stageLabel={stageLabel}
        stageMessage={stageMessage}
        progressPct={progressPct}
        stepMs={overlayGroupMs}
      />

      <div className="space-y-4">
        <AnimatePresence mode="wait">
          {hasResume ? (
            /* Resume present: show only file card with Open and Remove */
            <motion.div
              key="resume-card"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
              className={
                light
                  ? 'rounded-2xl border-2 border-emerald-200 bg-emerald-50 p-5 flex flex-col sm:flex-row sm:items-center gap-4'
                  : 'glass-card border-2 border-green-500/30 rounded-2xl p-5 flex flex-col sm:flex-row sm:items-center gap-4'
              }
            >
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <div
                  className={
                    light
                      ? 'flex-shrink-0 w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center border border-emerald-200'
                      : 'flex-shrink-0 w-12 h-12 bg-green-500/20 rounded-xl flex items-center justify-center border border-green-500/40'
                  }
                >
                  <FiFile className={`w-6 h-6 ${light ? 'text-emerald-600' : 'text-green-400'}`} />
                </div>
                <div className="min-w-0">
                  <p className={`text-sm font-medium ${light ? 'text-emerald-800' : 'text-green-300'}`}>Resume uploaded</p>
                  <p className={`text-sm truncate ${light ? 'text-slate-600' : 'text-zinc-300'}`} title={currentFileName}>{currentFileName}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {onOpenResume && (
                  <button
                    type="button"
                    onClick={(e) => { e.preventDefault(); onOpenResume(); }}
                    className={
                      light
                        ? 'inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white hover:bg-slate-50 text-slate-700 text-sm font-medium transition-colors border border-slate-200'
                        : 'inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-zinc-200 text-sm font-medium transition-colors border border-zinc-600'
                    }
                  >
                    <FiExternalLink className="w-4 h-4" />
                    View resume
                  </button>
                )}
                <button
                  type="button"
                  onClick={handleRemove}
                  className={
                    light
                      ? 'inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-red-50 hover:bg-red-100 text-red-600 text-sm font-medium transition-colors border border-red-200'
                      : 'inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-red-500/20 hover:bg-red-500/30 text-red-300 text-sm font-medium transition-colors border border-red-500/40'
                  }
                >
                  <FiTrash2 className="w-4 h-4" />
                  Remove
                </button>
              </div>
            </motion.div>
          ) : (
            /* No resume: show full upload area to parse a new resume */
            <motion.div
              key="upload-area"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              className={`relative group transition-all duration-300 ${
                isDragging ? 'scale-105 ring-4 ring-purple-500/50' : 'hover:scale-[1.02]'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.png,.jpg,.jpeg,.webp"
                onChange={handleFileChange}
                disabled={isUploading}
                className="hidden"
                id="resume-upload-input"
              />
              <label
                htmlFor="resume-upload-input"
                className={`
                  block p-8 rounded-2xl cursor-pointer
                  border-2 border-dashed transition-all duration-300
                  ${light ? 'bg-slate-50' : 'glass-card'}
                  ${isDragging
                    ? 'border-purple-500 bg-purple-500/10'
                    : light
                      ? 'border-slate-300 hover:border-purple-400 hover:bg-purple-50/50'
                      : 'border-zinc-700 hover:border-purple-500/50 hover:bg-white/10'}
                  ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}
                `}
              >
                <div className="flex flex-col items-center justify-center space-y-4">
                  <motion.div
                    animate={isDragging ? { scale: [1, 1.2, 1], rotate: [0, 10, -10, 0] } : {}}
                    transition={{ duration: 0.5 }}
                    className="relative"
                  >
                    <div className="absolute inset-0 bg-gradient-to-r from-purple-600 to-blue-600 rounded-full blur-xl opacity-50 group-hover:opacity-75 transition-opacity" />
                    <div className="relative w-16 h-16 bg-gradient-to-r from-purple-600 to-blue-600 rounded-full flex items-center justify-center shadow-glow">
                      <FiUpload className="w-8 h-8 text-white" />
                    </div>
                  </motion.div>
                  <div className="text-center">
                    <p className={`text-lg font-semibold mb-1 ${light ? 'text-slate-900' : 'text-white'}`}>
                      {isDragging ? 'Drop your resume here' : 'Upload Your Resume'}
                    </p>
                    <p className={`text-sm ${light ? 'text-slate-500' : 'text-zinc-400'}`}>Drag & drop or click to browse</p>
                  </div>
                  <div className={`flex items-center gap-4 text-xs ${light ? 'text-slate-500' : 'text-zinc-500'}`}>
                    <div className="flex items-center gap-1">
                      <FiFile className="w-4 h-4" />
                      <span>PDF, DOC, DOCX, PNG, JPG, WEBP</span>
                    </div>
                    <div className={`w-1 h-1 rounded-full ${light ? 'bg-slate-300' : 'bg-zinc-600'}`} />
                    <span>Max 10MB</span>
                  </div>
                  <motion.div
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.2 }}
                    className={
                      light
                        ? 'inline-flex items-center gap-2 px-4 py-2 bg-purple-50 rounded-full border border-purple-200'
                        : 'inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600/20 to-blue-600/20 rounded-full border border-purple-500/30'
                    }
                  >
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                    <span className={`text-xs font-medium ${light ? 'text-purple-700' : 'text-purple-300'}`}>AI-Powered Parsing</span>
                  </motion.div>
                </div>
              </label>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Success message (e.g. after parsing) */}
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
            className="border-2 border-amber-400 bg-amber-50 px-5 py-4 rounded-xl"
          >
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-10 h-10 bg-amber-500 rounded-full flex items-center justify-center">
                <FiAlertCircle className="w-5 h-5 text-white" />
              </div>
              <p className="text-sm text-amber-950 font-medium flex-1">{parseError}</p>
            </div>
          </motion.div>
        )}

      </div>
    </>
  );
}
