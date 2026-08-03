/**
 * Parsing API Integration Utilities
 */
import { BASE_URL as API_URL } from './api';

/**
 * Ensure a value is an array (for TOON list fields like education, experience, certifications).
 * LLM/API may return array, single object, string, or null/undefined.
 * @param {*} value - Raw value from TOON/API
 * @returns {Array} - Safe array for iteration (never null/undefined)
 */
function ensureArray(value) {
  if (value == null) return [];
  if (Array.isArray(value)) return value;
  return [value];
}

/**
 * Titles are filtered on the backend Intelligence Engine.
 * Frontend trusts TOON (no divergent re-filter).
 * @param {string} title
 * @returns {boolean}
 */
function isPlausibleJobTitle(title) {
  return Boolean(String(title || '').trim());
}

/**
 * Normalize a date value from parser/API to YYYY-MM for MonthYearPicker.
 * Parser may return: year only ("2025"), "Jan 2025", "2025-01", MM/YYYY, ranges, Present, or object.
 * @param {*} value - Raw date (string, number, or { year, month } object)
 * @returns {string} - "YYYY-MM" or ""
 */
function normalizeToYYYYMM(value) {
  if (value == null || value === '') return '';
  // Object form from parser e.g. { year: 2025, month: 3 } or { start_year, start_month }
  if (typeof value === 'object' && !Array.isArray(value)) {
    const y = value.year ?? value.start_year ?? value.end_year;
    let m = value.month ?? value.start_month ?? value.end_month;
    if (y != null) {
      const yy = String(y).trim();
      if (!/^\d{4}$/.test(yy)) return '';
      let mm = '01';
      if (m != null && m !== '') {
        const num = Number(m);
        if (!Number.isNaN(num) && num >= 1 && num <= 12) mm = String(num).padStart(2, '0');
        else {
          const monthNames = 'jan feb mar apr may jun jul aug sep oct nov dec'.split(' ');
          const idx = monthNames.indexOf(String(m).toLowerCase().slice(0, 3));
          if (idx >= 0) mm = String(idx + 1).padStart(2, '0');
        }
      }
      return `${yy}-${mm}`;
    }
    return '';
  }
  let s = String(value).trim();
  if (!s) return '';
  if (/^(present|current|now)$/i.test(s)) return '';

  // Take the start of a range like "2020-2024" or "Jan 2020 - Present"
  const rangeMatch = s.match(
    /^((?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}|\d{1,2}[/\-]\d{4}|\d{4}[/\-]\d{1,2}|\d{4}-\d{2}|\d{4})\s*(?:[-–—]|to)\s*/i
  );
  if (rangeMatch) {
    s = rangeMatch[1];
  }

  // Already YYYY-MM
  if (/^\d{4}-\d{2}$/.test(s)) return s;
  // Year only (e.g. "2025") -> mid-year for start-like; graduation end uses Dec via call-site
  if (/^\d{4}$/.test(s)) return `${s}-06`;
  // MM/YYYY or MM-YYYY
  const mmyyyy = s.match(/^(\d{1,2})[/\-](\d{4})$/);
  if (mmyyyy) {
    const month = Number(mmyyyy[1]);
    if (month >= 1 && month <= 12) return `${mmyyyy[2]}-${String(month).padStart(2, '0')}`;
  }
  // YYYY/MM or YYYY-M
  const yyyymm = s.match(/^(\d{4})[/\-](\d{1,2})$/);
  if (yyyymm) {
    const month = Number(yyyymm[2]);
    if (month >= 1 && month <= 12) return `${yyyymm[1]}-${String(month).padStart(2, '0')}`;
  }
  // Mon YYYY / Month YYYY
  const monYear = s.match(/^(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(\d{4})$/i);
  if (monYear) {
    const monthNames = 'jan feb mar apr may jun jul aug sep oct nov dec'.split(' ');
    const key = monYear[1].toLowerCase().startsWith('sept') ? 'sep' : monYear[1].toLowerCase().slice(0, 3);
    const idx = monthNames.indexOf(key);
    if (idx >= 0) return `${monYear[2]}-${String(idx + 1).padStart(2, '0')}`;
  }
  // Try parsing common formats (e.g. "Jan 2025", "January 2025", "2025-01")
  const d = new Date(s);
  if (!Number.isNaN(d.getTime())) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    return `${y}-${m}`;
  }
  return '';
}

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
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || 'Failed to parse resume');
  }

  return await response.json();
}

/**
 * Public resume parse for apply-form autofill (no auth).
 * @param {File} file
 * @returns {Promise<Object>}
 */
export async function uploadAndParseResumePublic(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_URL}/api/parse/resume/public`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || 'Failed to parse resume');
  }

  return await response.json();
}

/**
 * Parse SSE stream from Intelligence Engine.
 * @param {Response} response
 * @param {{ onStage?: (ev: object) => void }} options
 * @returns {Promise<Object>} final result payload
 */
async function consumeParseSSE(response, { onStage } = {}) {
  if (!response.ok || !response.body) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || 'Failed to parse document');
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let result = null;
  let errorPayload = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split('\n\n');
    buffer = chunks.pop() || '';
    for (const chunk of chunks) {
      const lines = chunk.split('\n');
      let eventName = 'message';
      let dataLine = '';
      for (const line of lines) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim();
        if (line.startsWith('data:')) dataLine += line.slice(5).trim();
      }
      if (!dataLine) continue;
      let data;
      try {
        data = JSON.parse(dataLine);
      } catch {
        continue;
      }
      if (eventName === 'stage' && onStage) onStage(data);
      if (eventName === 'result') result = data;
      if (eventName === 'error') errorPayload = data;
    }
  }
  if (errorPayload) {
    throw new Error(errorPayload.error || 'Parse failed');
  }
  if (!result) {
    throw new Error('Parse stream ended without result');
  }
  return result;
}

/**
 * Public resume parse with live stage events (SSE).
 * Falls back to sync endpoint if stream fails.
 * @param {File} file
 * @param {{ onStage?: (ev: object) => void }} options
 */
export async function uploadAndParseResumePublicStream(file, { onStage } = {}) {
  const formData = new FormData();
  formData.append('file', file);
  try {
    const response = await fetch(`${API_URL}/api/parse/resume/public/stream`, {
      method: 'POST',
      body: formData,
    });
    return await consumeParseSSE(response, { onStage });
  } catch (err) {
    // Fallback to blocking sync path
    return uploadAndParseResumePublic(file);
  }
}

/**
 * JD parse with live stage events (SSE), sync fallback.
 */
export async function uploadAndParseJDStream(file, jobId = null, { onStage } = {}) {
  const formData = new FormData();
  formData.append('file', file);
  if (jobId) formData.append('job_id', jobId);
  const token = localStorage.getItem('jwtToken');
  try {
    const response = await fetch(`${API_URL}/api/parse/jd/stream`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });
    return await consumeParseSSE(response, { onStage });
  } catch (err) {
    return uploadAndParseJD(file, jobId);
  }
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
  // Accept resume TOON even if type is missing (some LLM outputs omit it)
  if (!toon || (toon.type && toon.type !== 'resume' && toon.type !== 'Resume')) {
    throw new Error('Invalid resume TOON format');
  }
  if (!toon.person && !toon.education && !toon.experience && !toon.skills) {
    throw new Error('Invalid resume TOON format');
  }

  const person = toon.person || {};
  const otherUrls = ensureArray(person.otherUrls || person.urls || person.links);
  // Normalize to string (parser/API may return numbers for phone, etc.)
  const str = (v) => (v == null || v === '') ? '' : String(v).trim();

  const education = ensureArray(toon.education).map(edu => {
    if (edu == null || typeof edu !== 'object') {
      return { degree: '', institution: '', cgpa: '', startMonth: '', endMonth: '' };
    }
    const rawStart = edu.start ?? edu.start_date ?? edu.from ?? edu.startMonth;
    const rawEnd = edu.end ?? edu.end_date ?? edu.to ?? edu.endMonth ?? edu.year;
    const field = str(edu.field || edu.major);
    let degree = str(edu.degree || edu.qualification || edu.program);
    if (degree && field && !degree.toLowerCase().includes(field.toLowerCase())) {
      degree = `${degree} in ${field}`;
    } else if (!degree && field) {
      degree = field;
    }
    // Graduation year-only → December; other end dates via normalizer
    let endMonth = '';
    const endStr = rawEnd == null ? '' : String(rawEnd).trim();
    if (/^\d{4}$/.test(endStr) && (edu.year != null && String(edu.year).trim() === endStr)) {
      endMonth = `${endStr}-12`;
    } else {
      endMonth = normalizeToYYYYMM(rawEnd);
    }
    return {
      degree,
      institution: str(edu.institution || edu.school || edu.university),
      cgpa: str(edu.gpa || edu.cgpa || edu.percentage || edu.score),
      startMonth: normalizeToYYYYMM(rawStart),
      endMonth,
    };
  }).filter(e => e.degree || e.institution || e.cgpa || e.startMonth || e.endMonth);

  const experiences = ensureArray(toon.experience || toon.experiences || toon.work).map(exp => {
    if (exp == null || typeof exp !== 'object') {
      return { company: '', role: '', startMonth: '', endMonth: '', isCurrent: false };
    }
    const rawStart = exp.from ?? exp.start ?? exp.start_date ?? exp.startMonth;
    const rawEnd = exp.to ?? exp.end ?? exp.end_date ?? exp.endMonth;
    const endStr = rawEnd == null ? '' : String(rawEnd).trim();
    const isPresent =
      /^(present|current|now)$/i.test(endStr) ||
      exp.isCurrent === true ||
      exp.present === true ||
      exp.present === 'yes';
    return {
      company: str(exp.company || exp.employer || exp.organization),
      role: (() => {
        const raw = str(exp.title || exp.role || exp.position);
        return isPlausibleJobTitle(raw) ? raw : '';
      })(),
      startMonth: normalizeToYYYYMM(rawStart),
      endMonth: isPresent ? '' : normalizeToYYYYMM(rawEnd),
      isCurrent: !!isPresent,
      description: str(exp.description || exp.responsibilities || ''),
    };
  }).filter(e => e.company || e.role || e.startMonth);

  const certifications = ensureArray(toon.certifications).map(cert => {
    if (cert == null) {
      return { name: '', issuer: '', validTill: '', validationUrl: '', status: '' };
    }
    if (typeof cert === 'string') {
      return {
        name: str(cert),
        issuer: '',
        validTill: '',
        validationUrl: '',
        status: '',
      };
    }
    if (typeof cert !== 'object') {
      return { name: str(cert), issuer: '', validTill: '', validationUrl: '', status: '' };
    }
    return {
      name: str(cert.name || cert.title),
      issuer: str(cert.issuer || cert.organization),
      validTill: str(cert.validTill || cert.expiry),
      validationUrl: str(cert.url || cert.validationUrl),
      status: str(cert.status),
    };
  });

  // Calculate experience level from years or non-empty experience list
  const totalYears = Number(toon.total_experience_years || toon.years_of_experience || 0) || 0;
  const experienceLevel = (totalYears > 0 || experiences.length > 0) ? 'experienced' : 'fresher';

  // Extract URLs from person object
  // Map LinkedIn URL - check multiple possible fields
  let linkedinUrl = person.linkedin || '';
  if (!linkedinUrl && otherUrls.length > 0) {
    const linkedinMatch = otherUrls.find(url => 
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
    // Indian address abbreviations misread as domains (H.no, S.no)
    if (/\bh\.?\s*no\.?\b|\bs\.?\s*no\.?\b|plot\.?\s*no|flat\.?\s*no/i.test(urlLower)) {
      return false;
    }
    // Check if it's a proper domain (has TLD)
    const domainMatch = url.match(/https?:\/\/(?:www\.)?([^\/]+)/);
    if (domainMatch) {
      const domain = domainMatch[1];
      const parts = domain.split('.');
      // Reject single-letter hosts like h.no
      if (parts.length === 2 && parts[0].length <= 1 && parts[1].length <= 3) {
        return false;
      }
      // Should have a valid TLD (at least 2 characters)
      return parts.length >= 2 && parts[parts.length - 1].length >= 2;
    }
    return true; // If we can't parse it, assume it's valid
  };
  
  // Map portfolio and GitHub separately (do not overwrite portfolio with GitHub)
  const githubUrl = person.github || '';
  let portfolioUrl = '';
  const portfolioCandidate = person.portfolio || person.website || '';

  if (portfolioCandidate && isValidPortfolioUrl(portfolioCandidate)) {
    portfolioUrl = portfolioCandidate;
  } else if (otherUrls.length > 0) {
    const portfolioMatch = otherUrls.find(url =>
      url &&
      !url.toLowerCase().includes('linkedin') &&
      !url.toLowerCase().includes('github') &&
      !url.toLowerCase().includes('twitter') &&
      isValidPortfolioUrl(url)
    );
    if (portfolioMatch) {
      portfolioUrl = portfolioMatch;
    }
  }
  // If no portfolio but GitHub exists, use GitHub only as portfolio fallback for forms
  // that lack a separate github field — still expose githubUrl separately.
  if (!portfolioUrl && githubUrl) {
    portfolioUrl = githubUrl;
  }
  
  // Ensure URLs have proper protocol
  if (linkedinUrl && !linkedinUrl.startsWith('http')) {
    linkedinUrl = linkedinUrl.startsWith('//') ? `https:${linkedinUrl}` : `https://${linkedinUrl}`;
  }
  if (portfolioUrl && !portfolioUrl.startsWith('http')) {
    portfolioUrl = portfolioUrl.startsWith('//') ? `https:${portfolioUrl}` : `https://${portfolioUrl}`;
  }

  // Location: person.location, person.current_location, person.city, or from first experience
  const locationRaw =
    str(person.location) ||
    str(person.current_location) ||
    str(person.city) ||
    str(person.address) ||
    (ensureArray(toon.experience)[0] && typeof toon.experience[0] === 'object' ? str(toon.experience[0].location || toon.experience[0].city) : '') ||
    '';
  const currentLocation = locationRaw.trim();
  const preferredLocation = str(person.preferred_location) || currentLocation;

  const skillsList = ensureStringArray(toon.skills);
  const mappedData = {
    fullName: str(person.name || person.full_name || person.fullName),
    email: str(person.email || person.email_address),
    phone: str(person.phone || person.mobile || person.phone_number || person.contact),
    linkedinUrl: linkedinUrl ? str(linkedinUrl) : '',
    portfolioUrl: portfolioUrl ? str(portfolioUrl) : '',
    githubUrl: githubUrl ? str(githubUrl.startsWith('http') ? githubUrl : `https://${githubUrl}`) : '',
    currentLocation,
    preferredLocation,
    experienceLevel,
    skills: skillsList.join(', '),
    summary: str(toon.summary || ''),
    education: education.length > 0 ? education : [{ degree: '', institution: '', cgpa: '', startMonth: '', endMonth: '' }],
    experiences: experiences.length > 0 ? experiences : [{ company: '', role: '', startMonth: '', endMonth: '', isCurrent: false, description: '' }],
    certifications: certifications.length > 0 ? certifications : [{ name: '', issuer: '', validTill: '', validationUrl: '', status: '' }],
    _skills: skillsList,
    _summary: toon.summary || '',
  };

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
  if (toon.min_experience_years != null && toon.min_experience_years !== '') {
    experienceFrom = String(toon.min_experience_years);
  }
  if (toon.max_experience_years != null && toon.max_experience_years !== '') {
    experienceTo = String(toon.max_experience_years);
  }

  const mandatorySkills = ensureStringArray(
    toon.mandatory_skills?.length ? toon.mandatory_skills : toon.skills,
  );
  const preferredSkills = ensureStringArray(toon.preferred_skills);

  return {
    title: str(toon.title),
    location: str(toon.location),
    experienceFrom,
    experienceTo,
    description: formatJDDescription(toon),
    salary: str(toon.salary_range),
    company: str(toon.company),
    mandatorySkills,
    preferredSkills,
    employmentType: str(toon.employment_type || toon.employmentType),
    // Additional data for reference (normalized so downstream always gets arrays)
    _skills: ensureStringArray(toon.skills),
    _mandatorySkills: mandatorySkills,
    _preferredSkills: preferredSkills,
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
  const mandatory = ensureStringArray(
    toon?.mandatory_skills?.length ? toon.mandatory_skills : toon?.skills,
  );
  const preferred = ensureStringArray(toon?.preferred_skills);
  const skills = ensureStringArray(toon?.skills);
  const qualifications = ensureStringArray(toon?.qualifications);
  const benefits = ensureStringArray(toon?.benefits);
  const narrative = str(toon?.description);
  const employmentType = str(toon?.employment_type || toon?.employmentType);
  let description = '';

  if (employmentType) {
    description += `**Employment Type:** ${employmentType}\n\n`;
  }

  // Prefer structured sections; include narrative overview when present and not already covered.
  if (narrative) {
    const looksStructured =
      /\*\*Responsibilities:\*\*/i.test(narrative) ||
      /\*\*Required Skills:\*\*/i.test(narrative) ||
      /\*\*Mandatory Skills:\*\*/i.test(narrative) ||
      /\*\*Qualifications:\*\*/i.test(narrative);
    if (looksStructured) {
      description += narrative;
      if (preferred.length > 0 && !/\*\*Preferred Skills:\*\*/i.test(narrative)) {
        description += '\n\n**Preferred Skills:**\n';
        description += preferred.map((s) => str(s)).join(', ');
        description += '\n';
      }
      if (benefits.length > 0 && !/\*\*Benefits:\*\*/i.test(narrative)) {
        description += '\n\n**Benefits:**\n';
        benefits.forEach((b) => {
          description += `• ${str(b)}\n`;
        });
      }
      return description.trim();
    }
    description += `${narrative}\n\n`;
  }

  if (responsibilities.length > 0) {
    description += '**Responsibilities:**\n';
    responsibilities.forEach((resp) => {
      description += `• ${str(resp)}\n`;
    });
    description += '\n';
  }

  if (mandatory.length > 0) {
    description += '**Required Skills:**\n';
    description += mandatory.map((s) => str(s)).join(', ');
    description += '\n\n';
  } else if (skills.length > 0) {
    description += '**Required Skills:**\n';
    description += skills.map((s) => str(s)).join(', ');
    description += '\n\n';
  }

  if (preferred.length > 0) {
    description += '**Preferred Skills:**\n';
    description += preferred.map((s) => str(s)).join(', ');
    description += '\n\n';
  }

  if (qualifications.length > 0) {
    description += '**Qualifications:**\n';
    qualifications.forEach((qual) => {
      description += `• ${str(qual)}\n`;
    });
    description += '\n';
  }

  if (benefits.length > 0) {
    description += '**Benefits:**\n';
    benefits.forEach((b) => {
      description += `• ${str(b)}\n`;
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
  const allowedExtensions = ['pdf', 'docx', 'png', 'jpg', 'jpeg', 'webp'];
  const maxSize = 10 * 1024 * 1024; // 10MB

  const extension = file.name.split('.').pop().toLowerCase();

  if (extension === 'doc') {
    return {
      valid: false,
      error: 'Legacy .doc format is not supported. Please use DOCX or PDF.',
    };
  }

  if (!allowedExtensions.includes(extension)) {
    return {
      valid: false,
      error: 'Invalid file type. Please upload PDF, DOCX, PNG, JPG, or WEBP files only.',
    };
  }

  if (file.size > maxSize) {
    return {
      valid: false,
      error: 'File too large. Maximum size is 10MB.',
    };
  }

  return { valid: true, error: null };
}

