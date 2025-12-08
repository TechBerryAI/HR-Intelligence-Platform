/**
 * Parsing API Integration Utilities
 */
import { BASE_URL as API_URL } from './api';

/**
 * Upload and parse resume file
 * @param {File} file - Resume file (PDF/DOCX)
 * @param {string} candidateId - Optional candidate ID
 * @returns {Promise<Object>} - Parsing result with TOON data
 */
export async function uploadAndParseResume(file, candidateId = null) {
  const formData = new FormData();
  formData.append('file', file);
  if (candidateId) {
    formData.append('candidate_id', candidateId);
  }

  const token = localStorage.getItem('jwtToken');
  
  const response = await fetch(`${API_URL}/api/parse/resume`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to parse resume');
  }

  return await response.json();
}

/**
 * Upload and parse job description file
 * @param {File} file - JD file (PDF/DOCX)
 * @param {string} jobId - Optional job ID
 * @returns {Promise<Object>} - Parsing result with TOON data
 */
export async function uploadAndParseJD(file, jobId = null) {
  const formData = new FormData();
  formData.append('file', file);
  if (jobId) {
    formData.append('job_id', jobId);
  }

  const token = localStorage.getItem('jwtToken');
  
  const response = await fetch(`${API_URL}/api/parse/jd`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to parse job description');
  }

  return await response.json();
}

/**
 * Map Resume TOON to form fields
 * @param {Object} toon - Resume TOON object
 * @returns {Object} - Form field mappings
 */
export function mapResumeTOONToForm(toon) {
  if (!toon || toon.type !== 'resume') {
    throw new Error('Invalid resume TOON format');
  }

  const person = toon.person || {};
  const education = (toon.education || []).map(edu => ({
    degree: edu.degree || '',
    institution: edu.institution || edu.field || '',
    cgpa: edu.gpa || edu.cgpa || '',
    startMonth: edu.start || '',
    endMonth: edu.year || edu.end || '',
  }));

  const experiences = (toon.experience || []).map(exp => ({
    company: exp.company || '',
    role: exp.title || exp.role || '',
    startMonth: exp.from || exp.start || '',
    endMonth: exp.to === 'Present' || exp.to === 'present' ? '' : (exp.to || exp.end || ''),
    isCurrent: exp.to === 'Present' || exp.to === 'present' || exp.isCurrent || false,
  }));

  const certifications = (toon.certifications || []).map(cert => {
    // Handle both string and object formats
    if (typeof cert === 'string') {
      return {
        name: cert,
        issuer: '',
        validTill: '',
        validationUrl: '',
        status: '',
      };
    }
    return {
      name: cert.name || cert.title || '',
      issuer: cert.issuer || cert.organization || '',
      validTill: cert.validTill || cert.expiry || '',
      validationUrl: cert.url || cert.validationUrl || '',
      status: cert.status || '',
    };
  });

  // Calculate experience level
  const totalYears = toon.total_experience_years || 0;
  const experienceLevel = totalYears > 0 ? 'experienced' : 'fresher';

  return {
    fullName: person.name || '',
    email: person.email || '',
    phone: person.phone || '',
    experienceLevel,
    education: education.length > 0 ? education : [{ degree: '', institution: '', cgpa: '', startMonth: '', endMonth: '' }],
    experiences: experiences.length > 0 ? experiences : [{ company: '', role: '', startMonth: '', endMonth: '', isCurrent: false }],
    certifications: certifications.length > 0 ? certifications : [{ name: '', issuer: '', validTill: '', validationUrl: '', status: '' }],
    // Skills are extracted but not directly mapped to form (could be used for suggestions)
    _skills: toon.skills || [],
    _summary: toon.summary || '',
  };
}

/**
 * Map JD TOON to form fields
 * @param {Object} toon - JD TOON object
 * @returns {Object} - Form field mappings
 */
export function mapJDTOONToForm(toon) {
  if (!toon || toon.type !== 'job_description') {
    throw new Error('Invalid job description TOON format');
  }

  // Parse experience range
  let experienceFrom = '';
  let experienceTo = '';
  
  if (toon.min_experience_years !== undefined) {
    experienceFrom = String(toon.min_experience_years);
  }
  if (toon.max_experience_years !== undefined) {
    experienceTo = String(toon.max_experience_years);
  }

  return {
    title: toon.title || '',
    location: toon.location || '',
    experienceFrom,
    experienceTo,
    description: formatJDDescription(toon),
    salary: toon.salary_range || '',
    company: toon.company || '',
    // Additional data for reference
    _skills: toon.skills || [],
    _responsibilities: toon.responsibilities || [],
    _qualifications: toon.qualifications || [],
    _keywords: toon.keywords || [],
  };
}

/**
 * Format JD description from TOON components
 * @param {Object} toon - JD TOON object
 * @returns {string} - Formatted description
 */
function formatJDDescription(toon) {
  let description = '';

  if (toon.responsibilities && toon.responsibilities.length > 0) {
    description += '**Responsibilities:**\n';
    toon.responsibilities.forEach(resp => {
      description += `• ${resp}\n`;
    });
    description += '\n';
  }

  if (toon.skills && toon.skills.length > 0) {
    description += '**Required Skills:**\n';
    description += toon.skills.join(', ');
    description += '\n\n';
  }

  if (toon.qualifications && toon.qualifications.length > 0) {
    description += '**Qualifications:**\n';
    toon.qualifications.forEach(qual => {
      description += `• ${qual}\n`;
    });
  }

  return description.trim();
}

/**
 * Validate file before upload
 * @param {File} file - File to validate
 * @returns {Object} - { valid: boolean, error: string }
 */
export function validateFileForParsing(file) {
  const allowedTypes = [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/msword',
  ];
  
  const allowedExtensions = ['pdf', 'docx', 'doc'];
  const maxSize = 10 * 1024 * 1024; // 10MB

  // Get file extension (always check extension as primary validation)
  const extension = file.name.split('.').pop().toLowerCase();
  
  // Check file extension first (more reliable than MIME type)
  if (!allowedExtensions.includes(extension)) {
    return {
      valid: false,
      error: 'Invalid file type. Please upload PDF, DOC, or DOCX files only.',
    };
  }

  // Check file size
  if (file.size > maxSize) {
    return {
      valid: false,
      error: 'File too large. Maximum size is 10MB.',
    };
  }

  return { valid: true, error: null };
}

