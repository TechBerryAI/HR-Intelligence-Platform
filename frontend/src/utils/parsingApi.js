/**
 * Parsing API Integration Utilities
 */
import { BASE_URL as API_URL } from './api';

/**
 * Normalize a value to an array of non-empty strings.
 * JD/LLM output can return qualifications, skills, or responsibilities as:
 * - array (expected), string (single or pipe/newline-separated), object, null/undefined.
 * @param {*} value - Raw value from TOON/API
 * @returns {string[]} - Safe array of strings for iteration
 */
function ensureStringArray(value) {
  if (value == null) return [];
  if (Array.isArray(value)) {
    return value.map((v) => (v != null && v !== '' ? String(v).trim() : '')).filter(Boolean);
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return [];
    // Pipe or newline separated (TOON/LLM style)
    const parts = trimmed.includes('|')
      ? trimmed.split('|').map((s) => s.trim()).filter(Boolean)
      : trimmed.split(/\n/).map((s) => s.trim()).filter(Boolean);
    return parts.length > 0 ? parts : [trimmed];
  }
  if (typeof value === 'object' && !Array.isArray(value)) {
    const vals = Object.values(value);
    return vals.map((v) => (v != null && v !== '' ? String(v).trim() : '')).filter(Boolean);
  }
  return [];
}

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
  // Normalize to string (parser/API may return numbers for phone, etc.)
  const str = (v) => (v == null || v === '') ? '' : String(v).trim();

  const education = (toon.education || []).map(edu => ({
    degree: str(edu.degree),
    institution: str(edu.institution || edu.field),
    cgpa: str(edu.gpa || edu.cgpa),
    startMonth: str(edu.start),
    endMonth: str(edu.year || edu.end),
  }));

  const experiences = (toon.experience || []).map(exp => ({
    company: str(exp.company),
    role: str(exp.title || exp.role),
    startMonth: str(exp.from || exp.start),
    endMonth: exp.to === 'Present' || exp.to === 'present' ? '' : str(exp.to || exp.end),
    isCurrent: exp.to === 'Present' || exp.to === 'present' || exp.isCurrent || false,
  }));

  const certifications = (toon.certifications || []).map(cert => {
    if (typeof cert === 'string') {
      return {
        name: str(cert),
        issuer: '',
        validTill: '',
        validationUrl: '',
        status: '',
      };
    }
    return {
      name: str(cert.name || cert.title),
      issuer: str(cert.issuer || cert.organization),
      validTill: str(cert.validTill || cert.expiry),
      validationUrl: str(cert.url || cert.validationUrl),
      status: str(cert.status),
    };
  });

  // Calculate experience level
  const totalYears = toon.total_experience_years || 0;
  const experienceLevel = totalYears > 0 ? 'experienced' : 'fresher';

  // Extract URLs from person object
  // Map LinkedIn URL - check multiple possible fields
  let linkedinUrl = person.linkedin || '';
  if (!linkedinUrl && person.otherUrls) {
    const linkedinMatch = person.otherUrls.find(url => 
      url && (url.toLowerCase().includes('linkedin') || url.toLowerCase().includes('linked.in'))
    );
    if (linkedinMatch) linkedinUrl = linkedinMatch;
  }
  
  // Helper function to validate if a URL looks like a real portfolio/website
  const isValidPortfolioUrl = (url) => {
    if (!url) return false;
    const urlLower = url.toLowerCase();
    // Exclude invalid domains
    const invalidDomains = ['loading', 'example', 'test', 'placeholder', 'data', 'localhost', 'gmail', 'yahoo', 'outlook', 'hotmail'];
    // Check if URL contains invalid domain patterns
    if (invalidDomains.some(domain => urlLower.includes(domain + '.'))) {
      return false;
    }
    // Check if it's a proper domain (has TLD)
    const domainMatch = url.match(/https?:\/\/(?:www\.)?([^\/]+)/);
    if (domainMatch) {
      const domain = domainMatch[1];
      // Should have a valid TLD (at least 2 characters)
      return domain.split('.').length >= 2 && domain.split('.').pop().length >= 2;
    }
    return true; // If we can't parse it, assume it's valid
  };
  
  // Map portfolio URL - prioritize GitHub, then portfolio/website, then otherUrls
  // Portfolio field can contain GitHub, portfolio, or personal website
  let portfolioUrl = '';
  
  // First, check if GitHub URL exists and portfolio is invalid - use GitHub as portfolio
  const githubUrl = person.github || '';
  const portfolioCandidate = person.portfolio || person.website || '';
  
  if (githubUrl && (!portfolioCandidate || !isValidPortfolioUrl(portfolioCandidate))) {
    // Use GitHub as portfolio if portfolio URL is invalid or missing
    portfolioUrl = githubUrl;
  } else if (portfolioCandidate && isValidPortfolioUrl(portfolioCandidate)) {
    // Use portfolio/website if it's valid
    portfolioUrl = portfolioCandidate;
  } else if (person.otherUrls && person.otherUrls.length > 0) {
    // Look for valid portfolio URLs in otherUrls (excluding social media)
    const portfolioMatch = person.otherUrls.find(url => 
      url && 
      !url.toLowerCase().includes('linkedin') && 
      !url.toLowerCase().includes('github') && 
      !url.toLowerCase().includes('twitter') &&
      isValidPortfolioUrl(url)
    );
    if (portfolioMatch) {
      portfolioUrl = portfolioMatch;
    } else if (githubUrl) {
      // Fallback to GitHub if no valid portfolio found
      portfolioUrl = githubUrl;
    }
  } else if (githubUrl) {
    // Last resort: use GitHub if nothing else is available
    portfolioUrl = githubUrl;
  }
  
  // Ensure URLs have proper protocol
  if (linkedinUrl && !linkedinUrl.startsWith('http')) {
    linkedinUrl = linkedinUrl.startsWith('//') ? `https:${linkedinUrl}` : `https://${linkedinUrl}`;
  }
  if (portfolioUrl && !portfolioUrl.startsWith('http')) {
    portfolioUrl = portfolioUrl.startsWith('//') ? `https:${portfolioUrl}` : `https://${portfolioUrl}`;
  }

  const mappedData = {
    fullName: str(person.name),
    email: str(person.email),
    phone: str(person.phone),
    linkedinUrl: linkedinUrl ? str(linkedinUrl) : '',
    portfolioUrl: portfolioUrl ? str(portfolioUrl) : '',
    experienceLevel,
    education: education.length > 0 ? education : [{ degree: '', institution: '', cgpa: '', startMonth: '', endMonth: '' }],
    experiences: experiences.length > 0 ? experiences : [{ company: '', role: '', startMonth: '', endMonth: '', isCurrent: false }],
    certifications: certifications.length > 0 ? certifications : [{ name: '', issuer: '', validTill: '', validationUrl: '', status: '' }],
    // Skills are extracted but not directly mapped to form (could be used for suggestions)
    _skills: ensureStringArray(toon.skills),
    _summary: toon.summary || '',
  };
  
  console.log('DEBUG: mapResumeTOONToForm returning:', {
    linkedinUrl: mappedData.linkedinUrl,
    portfolioUrl: mappedData.portfolioUrl,
    linkedinUrlLength: mappedData.linkedinUrl?.length,
    portfolioUrlLength: mappedData.portfolioUrl?.length,
    personLinkedin: person.linkedin,
    personGithub: person.github,
    personPortfolio: person.portfolio,
    personWebsite: person.website,
    personOtherUrls: person.otherUrls,
    fullPerson: person
  });
  
  return mappedData;
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

  const str = (v) => (v == null || v === '') ? '' : String(v).trim();
  let experienceFrom = '';
  let experienceTo = '';
  if (toon.min_experience_years !== undefined) experienceFrom = String(toon.min_experience_years);
  if (toon.max_experience_years !== undefined) experienceTo = String(toon.max_experience_years);

  return {
    title: str(toon.title),
    location: str(toon.location),
    experienceFrom,
    experienceTo,
    description: formatJDDescription(toon),
    salary: str(toon.salary_range),
    company: str(toon.company),
    // Additional data for reference (normalized so downstream always gets arrays)
    _skills: ensureStringArray(toon.skills),
    _responsibilities: ensureStringArray(toon.responsibilities),
    _qualifications: ensureStringArray(toon.qualifications),
    _keywords: ensureStringArray(toon.keywords),
  };
}

/**
 * Format JD description from TOON components
 * @param {Object} toon - JD TOON object
 * @returns {string} - Formatted description
 */
function formatJDDescription(toon) {
  const str = (v) => (v == null ? '' : String(v)).trim();
  const responsibilities = ensureStringArray(toon?.responsibilities);
  const skills = ensureStringArray(toon?.skills);
  const qualifications = ensureStringArray(toon?.qualifications);
  let description = '';

  if (responsibilities.length > 0) {
    description += '**Responsibilities:**\n';
    responsibilities.forEach((resp) => {
      description += `• ${str(resp)}\n`;
    });
    description += '\n';
  }

  if (skills.length > 0) {
    description += '**Required Skills:**\n';
    description += skills.map((s) => str(s)).join(', ');
    description += '\n\n';
  }

  if (qualifications.length > 0) {
    description += '**Qualifications:**\n';
    qualifications.forEach((qual) => {
      description += `• ${str(qual)}\n`;
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

