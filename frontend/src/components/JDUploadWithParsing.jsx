import React, { useState, useRef } from 'react';
import { uploadAndParseJD, mapJDTOONToForm, validateFileForParsing } from '../utils/parsingApi';

/**
 * Job Description Upload Component with AI Parsing
 * Uploads JD, parses it, and autofills job form
 */
export default function JDUploadWithParsing({ onAutofill, currentJobId }) {
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

    // Start AI parsing
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
          setParseSuccess('✓ Job description recognized! Using previously parsed data.');
        } else {
          setParseSuccess('✓ Job description parsed successfully! Fields auto-filled below.');
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
    <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        🚀 Quick Create from Job Description
      </h3>
      
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.doc,.docx"
            onChange={handleFileChange}
            disabled={isUploading}
            className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100 disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>

        {isUploading && (
          <div className="flex items-center gap-2 text-purple-600 text-sm">
            <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Parsing job description with AI... This may take 10-30 seconds.</span>
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

        <div className="text-xs text-gray-500 space-y-1">
          <p>📄 Upload a PDF or DOCX job description</p>
          <p>🤖 AI will automatically extract title, location, skills, responsibilities, and requirements</p>
          <p>⚡ Saves time - just review and post!</p>
        </div>
      </div>
    </div>
  );
}

