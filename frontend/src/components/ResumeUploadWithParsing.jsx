import React, { useState, useRef } from 'react';
import { uploadAndParseResume, mapResumeTOONToForm, validateFileForParsing } from '../utils/parsingApi';

/**
 * Resume Upload Component with AI Parsing
 * Uploads resume, parses it, and autofills form
 */
export default function ResumeUploadWithParsing({ onAutofill, onFileSelect, currentFileName }) {
  const [isUploading, setIsUploading] = useState(false);
  const [parseError, setParseError] = useState('');
  const [parseSuccess, setParseSuccess] = useState('');
  const [confidence, setConfidence] = useState(null);
  const fileInputRef = useRef(null);

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Clear previous messages
    setParseError('');
    setParseSuccess('');
    setConfidence(null);

    // Check if user is logged in (token stored as 'jwtToken')
    const token = localStorage.getItem('jwtToken');
    if (!token) {
      setParseError('🔒 Please log in first to use AI-powered resume parsing. You can still fill the form manually.');
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

    // Notify parent of file selection (for traditional upload)
    if (onFileSelect) {
      onFileSelect(file);
    }

    // Start AI parsing
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
          setParseSuccess('✓ Resume recognized! Using previously parsed data.');
        } else {
          setParseSuccess('✓ Resume parsed successfully! Fields auto-filled below.');
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
        setParseError('🔒 Your session has expired. Please log in again to use AI-powered resume parsing.');
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
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.doc,.docx"
          onChange={handleFileChange}
          disabled={isUploading}
          className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed"
        />
      </div>

      {isUploading && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 space-y-4">
          {/* Animated Header */}
          <div className="flex items-center gap-3">
            <div className="relative">
              <svg className="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-3 h-3 bg-blue-600 rounded-full animate-pulse"></div>
              </div>
            </div>
            <div>
              <h4 className="font-semibold text-blue-900">AI is Parsing Your Resume</h4>
              <p className="text-sm text-blue-700">This usually takes 10-30 seconds...</p>
            </div>
          </div>
          
          {/* Progress Steps */}
          <div className="space-y-2 pl-11">
            <div className="flex items-center gap-2 text-sm">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span className="text-gray-700">✓ Extracting text from document</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" style={{animationDelay: '0.2s'}}></div>
              <span className="text-gray-700">⚡ Analyzing with AI (Grok-4 Fast Reasoning)</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <div className="w-2 h-2 bg-purple-500 rounded-full animate-pulse" style={{animationDelay: '0.4s'}}></div>
              <span className="text-gray-700">📝 Preparing auto-fill data</span>
            </div>
          </div>
          
          {/* Progress Bar */}
          <div className="w-full bg-blue-200 rounded-full h-2 overflow-hidden">
            <div className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full animate-progress"></div>
          </div>
          
          <style jsx>{`
            @keyframes progress {
              0% { width: 0%; }
              100% { width: 100%; }
            }
            .animate-progress {
              animation: progress 25s ease-in-out infinite;
            }
          `}</style>
        </div>
      )}

      {parseSuccess && (
        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded-md text-sm flex items-start gap-2">
          <span className="font-semibold">{parseSuccess}</span>
          {confidence !== null && (
            <span className="ml-auto text-xs bg-green-100 px-2 py-1 rounded">
              Confidence: {(confidence * 100).toFixed(0)}%
            </span>
          )}
        </div>
      )}

      {parseError && (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-md text-sm">
          {parseError}
        </div>
      )}

      {currentFileName && !parseSuccess && (
        <div className="text-sm text-gray-600">
          Current file: <span className="font-medium">{currentFileName}</span>
        </div>
      )}

      <div className="text-xs text-gray-500 space-y-1">
        <p>📄 Supported formats: PDF, DOC, DOCX (max 10MB)</p>
        <p>🤖 AI will automatically extract and fill your information</p>
      </div>
    </div>
  );
}

