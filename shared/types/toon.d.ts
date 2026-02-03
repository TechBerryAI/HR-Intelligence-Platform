/**
 * TOON (Transfer Object Oriented Notation) Types
 * Standardized format for Resume and Job Description parsing
 */
export interface TOONBase {
    type: 'resume' | 'job_description';
}
export interface TOONPerson {
    name: string;
    email: string;
    phone: string;
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
    employment_type: string;
    min_experience_years: number;
    max_experience_years?: number;
    skills: string[];
    responsibilities: string[];
    keywords: string[];
    qualifications?: string[];
    salary_range?: string;
    company?: string;
}
export type TOON = ResumeTOON | JDTOON;
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
//# sourceMappingURL=toon.d.ts.map