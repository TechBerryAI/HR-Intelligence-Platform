/**
 * TOON (Token-Oriented Object Notation) Types
 * Canonical schemas for Resume, JD, and ATS Result across the ATS pipeline.
 */

export interface TOONBase {
  type: 'resume' | 'job_description';
}

export interface TOONPerson {
  name: string;
  email: string;
  phone: string;
  location?: string;
  preferred_location?: string;
  linkedin?: string;
  github?: string;
  portfolio?: string;
  website?: string;
  twitter?: string;
  otherUrls?: string[];
}

export interface TOONExperience {
  title: string;
  company: string;
  from: string;
  to: string;
  years: number;
  description?: string;
}

export interface TOONEducation {
  degree: string;
  field: string;
  institution?: string;
  year: string;
  gpa?: string;
}

export interface ResumeTOON extends TOONBase {
  type: 'resume';
  person: TOONPerson;
  summary: string;
  skills: string[];
  experience: TOONExperience[];
  education: TOONEducation[];
  certifications?: string[];
  languages?: string[];
  total_experience_years?: number;
}

export interface JDTOON extends TOONBase {
  type: 'job_description';
  title: string;
  location: string;
  employment_type?: string;
  min_experience_years?: number | null;
  max_experience_years?: number | null;
  skills: string[];
  /** ATS-critical required skills */
  mandatory_skills?: string[];
  /** Nice-to-have skills */
  preferred_skills?: string[];
  responsibilities: string[];
  keywords?: string[];
  qualifications?: string[];
  benefits?: string[];
  description?: string;
  salary_range?: string;
  company?: string;
  confidence?: number;
}

export type TOON = ResumeTOON | JDTOON;

/** ATS scoring/matching result; stored and exchanged as TOON. */
export interface ATSResultTOON {
  json_output: {
    final_score: number;
    overall_match_score?: number;
    decision: string;
    verdict: string;
    rationale?: string;
    final_reasoning?: string;
    evaluation_report?: Record<string, unknown>;
    mandatory_skills_match_pct?: number;
    score_breakdown?: Record<string, number>;
    key_strengths?: string[];
    key_gaps?: string[];
  };
  toon_output?: string;
}

export interface ParsingResponse {
  status: 'ok' | 'error';
  document_type: 'resume' | 'job_description' | 'unknown';
  confidence: number;
  toon: TOON | null;
  raw_text: string;
  model_version: string;
  error?: string;
  processing_time_ms?: number;
}

export interface UploadResponse {
  status: 'ok' | 'error';
  raw_file_id: string;
  parsed_id: string;
  confidence: number;
  toon: TOON;
  is_duplicate?: boolean;
  error?: string;
}

export interface ClassificationResult {
  type: 'resume' | 'job_description' | 'unknown';
  confidence: number;
}

