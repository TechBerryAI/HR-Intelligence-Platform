-- HCIP squashed baseline schema (captured from Alembic head 20260810_0014).
-- Applied only by alembic revision 20260810_s001. Do not edit for feature work;
-- add a new Alembic revision instead.
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;

--
-- PostgreSQL database dump
--


-- Dumped from database version 17.10
-- Dumped by pg_dump version 17.9

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', 'public', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;





--
-- Name: jobs_status_enabled_sync(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.jobs_status_enabled_sync() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
        NEW.enabled := (NEW.status = 'Published');
    ELSIF NEW.enabled IS DISTINCT FROM OLD.enabled THEN
        IF NEW.enabled THEN
            NEW.status := 'Published';
        ELSIF NEW.status = 'Published' THEN
            NEW.status := 'Paused';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;



--
-- Name: applications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.applications (
    id integer NOT NULL,
    candidate_id character varying(20) NOT NULL,
    job_id character varying(20) NOT NULL,
    status character varying(50) DEFAULT 'Applied'::character varying,
    applied_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    matching_percentage double precision DEFAULT 0,
    match_score double precision,
    shortlisted boolean DEFAULT false,
    ats_reasoning text,
    ats_analysis text,
    latest_match_id uuid,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_by character varying(20),
    created_by character varying(20),
    CONSTRAINT applications_status_check CHECK (((status)::text = ANY ((ARRAY['Applied'::character varying, 'Screening'::character varying, 'Matched'::character varying, 'Shortlisted'::character varying, 'Interview'::character varying, 'Rejected'::character varying, 'Offer'::character varying, 'Hired'::character varying, 'Withdrawn'::character varying])::text[])))
);


--
-- Name: applications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.applications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: applications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.applications_id_seq OWNED BY public.applications.id;


--
-- Name: auth_refresh_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_refresh_tokens (
    jti character varying(64) NOT NULL,
    user_id character varying(50) NOT NULL,
    token_hash character varying(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: bulk_parse_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bulk_parse_files (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    session_id uuid NOT NULL,
    raw_file_id uuid,
    parsed_resume_id uuid,
    original_filename character varying(255) NOT NULL,
    file_hash character varying(64),
    status character varying(20) DEFAULT 'Queued'::character varying NOT NULL,
    retry_count integer DEFAULT 0 NOT NULL,
    error_message text,
    processing_time_ms bigint,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT bulk_parse_files_status_check CHECK (((status)::text = ANY ((ARRAY['Queued'::character varying, 'Running'::character varying, 'Completed'::character varying, 'Failed'::character varying, 'Cancelled'::character varying])::text[])))
);


--
-- Name: bulk_parse_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bulk_parse_sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    created_by character varying(20) NOT NULL,
    status character varying(20) DEFAULT 'Queued'::character varying NOT NULL,
    progress integer DEFAULT 0 NOT NULL,
    total_files integer DEFAULT 0 NOT NULL,
    successful_files integer DEFAULT 0 NOT NULL,
    failed_files integer DEFAULT 0 NOT NULL,
    processing_time_ms bigint,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    error_summary text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_by character varying(20),
    CONSTRAINT bulk_parse_sessions_progress_check CHECK (((progress >= 0) AND (progress <= 100))),
    CONSTRAINT bulk_parse_sessions_status_check CHECK (((status)::text = ANY ((ARRAY['Queued'::character varying, 'Running'::character varying, 'Completed'::character varying, 'Failed'::character varying, 'Cancelled'::character varying])::text[])))
);


--
-- Name: candidate_certifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.candidate_certifications (
    candidate_id character varying(20) NOT NULL,
    certification character varying(255),
    issuer character varying(255),
    end_month character varying(50)
);


--
-- Name: candidate_cid_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.candidate_cid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: candidate_education; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.candidate_education (
    candidate_id character varying(20) NOT NULL,
    degree character varying(255),
    institution character varying(255),
    "cgpa/percentage" character varying(50),
    start_date character varying(50),
    end_date character varying(50)
);


--
-- Name: candidate_experiences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.candidate_experiences (
    candidate_id character varying(20) NOT NULL,
    company character varying(255),
    role character varying(255),
    start_date character varying(50),
    end_date character varying(50),
    present character varying(10)
);


--
-- Name: candidate_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.candidate_profiles (
    candidate_id character varying(20) NOT NULL,
    full_name character varying(255),
    email character varying(255),
    phone character varying(50),
    experience_level character varying(50),
    serving_notice character varying(10),
    notice_period character varying(50),
    last_working_day character varying(50),
    linkedin_url character varying(500),
    portfolio_url character varying(500),
    current_location character varying(255),
    preferred_location character varying(255),
    resume bytea,
    completed boolean DEFAULT false,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    created_by character varying(20),
    resume_raw_file_id uuid
);


--
-- Name: candidates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.candidates (
    cid character varying(20) DEFAULT ('CID'::text || lpad((nextval('public.candidate_cid_seq'::regclass))::text, 3, '0'::text)) NOT NULL,
    name character varying(255) NOT NULL,
    email character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE candidates; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.candidates IS 'Passwordless applicant identity (CID). Created on public job apply — not a login account.';


--
-- Name: employee_feedback; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employee_feedback (
    id integer NOT NULL,
    employee_name character varying(255) NOT NULL,
    employee_id character varying(50),
    department character varying(255),
    feedback_type character varying(50) NOT NULL,
    module character varying(255),
    severity character varying(20),
    description text NOT NULL,
    screenshot_path character varying(1000),
    status character varying(20) DEFAULT 'open'::character varying,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    submitted_by character varying(20),
    CONSTRAINT employee_feedback_feedback_type_check CHECK (((feedback_type)::text = ANY ((ARRAY['Bug Report'::character varying, 'Feature Request'::character varying, 'General Feedback'::character varying, 'Appreciation'::character varying])::text[]))),
    CONSTRAINT employee_feedback_severity_check CHECK ((((severity)::text = ANY ((ARRAY['Low'::character varying, 'Medium'::character varying, 'High'::character varying, 'Critical'::character varying])::text[])) OR (severity IS NULL))),
    CONSTRAINT employee_feedback_status_check CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'reviewed'::character varying, 'resolved'::character varying])::text[])))
);


--
-- Name: employee_feedback_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employee_feedback_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employee_feedback_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employee_feedback_id_seq OWNED BY public.employee_feedback.id;


--
-- Name: external_applications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.external_applications (
    id integer NOT NULL,
    company_key character varying(255) NOT NULL,
    provider character varying(64) NOT NULL,
    job_id character varying(64),
    external_job_id character varying(128),
    external_application_id character varying(128) NOT NULL,
    candidate_email character varying(255),
    candidate_name character varying(255),
    mapped_status character varying(64),
    payload jsonb,
    last_synced_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    organization_id uuid
);


--
-- Name: external_applications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.external_applications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: external_applications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.external_applications_id_seq OWNED BY public.external_applications.id;


--
-- Name: external_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.external_jobs (
    id integer NOT NULL,
    company_key character varying(255) NOT NULL,
    job_id character varying(64) NOT NULL,
    provider character varying(64) NOT NULL,
    external_job_id character varying(128),
    external_status character varying(64),
    published_at timestamp with time zone,
    last_sync timestamp with time zone,
    sync_status character varying(32) DEFAULT 'pending'::character varying NOT NULL,
    error_message text,
    retry_count integer DEFAULT 0 NOT NULL,
    request_payload jsonb,
    response_payload jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    organization_id uuid
);


--
-- Name: external_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.external_jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: external_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.external_jobs_id_seq OWNED BY public.external_jobs.id;


--
-- Name: hr_signup; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hr_signup (
    hrid character varying(20) NOT NULL,
    full_name character varying(255) NOT NULL,
    email character varying(255) NOT NULL,
    company character varying(255) NOT NULL,
    password character varying(255),
    role character varying(20) DEFAULT 'RECRUITER'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_by character varying(20),
    organization_id uuid,
    account_status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    otp character varying(128),
    otp_expiry timestamp with time zone,
    CONSTRAINT hr_signup_account_status_check CHECK (((account_status)::text = ANY ((ARRAY['pending'::character varying, 'active'::character varying])::text[]))),
    CONSTRAINT hr_signup_role_check CHECK (((role)::text = ANY ((ARRAY['CEO'::character varying, 'HEAD_HR'::character varying, 'RECRUITER'::character varying])::text[])))
);


--
-- Name: integration_provider; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.integration_provider (
    id integer NOT NULL,
    company_key character varying(255) NOT NULL,
    company character varying(255),
    provider character varying(64) NOT NULL,
    enabled boolean DEFAULT false NOT NULL,
    status character varying(32) DEFAULT 'disconnected'::character varying NOT NULL,
    auth_type character varying(32) DEFAULT 'api_key'::character varying NOT NULL,
    auto_publish boolean DEFAULT false NOT NULL,
    auto_sync boolean DEFAULT false NOT NULL,
    client_id text,
    client_secret text,
    access_token text,
    refresh_token text,
    expires_at timestamp with time zone,
    settings_json jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    organization_id uuid
);


--
-- Name: integration_provider_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.integration_provider_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: integration_provider_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.integration_provider_id_seq OWNED BY public.integration_provider.id;


--
-- Name: interview_slots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.interview_slots (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    interview_id uuid NOT NULL,
    recruiter_hrid character varying(20) NOT NULL,
    start_time timestamp with time zone NOT NULL,
    end_time timestamp with time zone NOT NULL,
    is_booked boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: interviews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.interviews (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    application_id integer NOT NULL,
    assigned_to character varying(20),
    status character varying(20) DEFAULT 'Scheduled'::character varying NOT NULL,
    scheduled_at timestamp with time zone,
    completed_at timestamp with time zone,
    interview_type character varying(50),
    location character varying(255),
    notes text,
    feedback_toon text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    created_by character varying(20),
    updated_by character varying(20),
    interviewer_type character varying(20) DEFAULT 'ai'::character varying NOT NULL,
    duration_minutes integer DEFAULT 30,
    invite_token character varying(64),
    meeting_link text,
    questions_json jsonb,
    answers_json jsonb,
    overall_score numeric(5,2),
    score_summary text,
    calendar_event_id text,
    invite_expires_at timestamp with time zone,
    interviewer_hrid character varying(20),
    CONSTRAINT interviews_interviewer_type_check CHECK (((interviewer_type)::text = ANY ((ARRAY['human'::character varying, 'ai'::character varying])::text[]))),
    CONSTRAINT interviews_status_check CHECK (((status)::text = ANY ((ARRAY['Invited'::character varying, 'Scheduled'::character varying, 'InProgress'::character varying, 'Completed'::character varying, 'Cancelled'::character varying, 'Rescheduled'::character varying])::text[])))
);


--
-- Name: jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.jobs (
    jdid character varying(20) NOT NULL,
    title character varying(255) NOT NULL,
    company character varying(255) NOT NULL,
    location character varying(255) NOT NULL,
    salary character varying(255),
    experience character varying(100),
    description text NOT NULL,
    enabled boolean DEFAULT true,
    posted_by character varying(20),
    posted_on timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    status character varying(20) DEFAULT 'Draft'::character varying NOT NULL,
    created_by character varying(20),
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_by character varying(20),
    parsed_jd_id uuid,
    keywords text,
    organization_id uuid,
    CONSTRAINT jobs_status_check CHECK (((status)::text = ANY ((ARRAY['Draft'::character varying, 'Published'::character varying, 'Paused'::character varying, 'Closed'::character varying, 'Archived'::character varying, 'Expired'::character varying])::text[])))
);


--
-- Name: login_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.login_history (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    user_type character varying(20) NOT NULL,
    ip_address character varying(100),
    user_agent character varying(500),
    status character varying(20) NOT NULL,
    failure_reason character varying(255),
    attempted_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    user_id character varying(50),
    CONSTRAINT login_history_status_check CHECK (((status)::text = ANY ((ARRAY['success'::character varying, 'failed'::character varying])::text[]))),
    CONSTRAINT login_history_user_type_check CHECK (((user_type)::text = 'HR'::text))
);


--
-- Name: login_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.login_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: login_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.login_history_id_seq OWNED BY public.login_history.id;


--
-- Name: matches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.matches (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    candidate_id character varying(20) NOT NULL,
    job_id character varying(20) NOT NULL,
    parsed_resume_id uuid,
    parsed_jd_id uuid,
    match_score double precision,
    matching_percentage double precision,
    semantic_score double precision,
    match_type character varying(20) DEFAULT 'ats'::character varying NOT NULL,
    rationale text,
    analysis_toon text,
    model_version character varying(100),
    is_latest boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    created_by character varying(20),
    CONSTRAINT matches_match_type_check CHECK (((match_type)::text = ANY ((ARRAY['rules'::character varying, 'ats'::character varying, 'semantic'::character varying])::text[])))
);


--
-- Name: oauth_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.oauth_tokens (
    id integer NOT NULL,
    company_key character varying(255) NOT NULL,
    provider character varying(64) NOT NULL,
    access_token text,
    refresh_token text,
    token_type character varying(32),
    scope text,
    expires_at timestamp with time zone,
    raw_json jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    organization_id uuid
);


--
-- Name: oauth_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.oauth_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: oauth_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.oauth_tokens_id_seq OWNED BY public.oauth_tokens.id;


--
-- Name: organizations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organizations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    slug character varying(100) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: parsed_jds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parsed_jds (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    raw_file_id uuid NOT NULL,
    job_id character varying(20),
    toon text NOT NULL,
    full_text text NOT NULL,
    confidence double precision NOT NULL,
    model_version character varying(100) NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    parse_status character varying(20) DEFAULT 'Parsed'::character varying NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    embedding_metadata jsonb,
    CONSTRAINT parsed_jds_parse_status_check CHECK (((parse_status)::text = ANY ((ARRAY['Text Extracted'::character varying, 'Parsed'::character varying, 'Parse Failed'::character varying])::text[])))
);


--
-- Name: parsed_resumes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parsed_resumes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    raw_file_id uuid NOT NULL,
    candidate_id character varying(20),
    toon text NOT NULL,
    full_text text NOT NULL,
    confidence double precision NOT NULL,
    model_version character varying(100) NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    bulk_session_id uuid,
    parse_status character varying(20) DEFAULT 'Parsed'::character varying NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    embedding_metadata jsonb,
    CONSTRAINT parsed_resumes_parse_status_check CHECK (((parse_status)::text = ANY ((ARRAY['Text Extracted'::character varying, 'Parsed'::character varying, 'Parse Failed'::character varying])::text[])))
);


--
-- Name: raw_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.raw_files (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    uploader_id character varying(50) NOT NULL,
    uploader_role character varying(20) NOT NULL,
    original_filename character varying(255) NOT NULL,
    storage_url character varying(1000) NOT NULL,
    mime_type character varying(100) NOT NULL,
    file_hash character varying(64) NOT NULL,
    size_bytes bigint NOT NULL,
    file_data bytea,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    bulk_session_id uuid,
    storage_backend character varying(32) DEFAULT 'postgres'::character varying NOT NULL,
    CONSTRAINT raw_files_uploader_role_check CHECK (((uploader_role)::text = ANY ((ARRAY['candidate'::character varying, 'admin'::character varying, 'recruiter'::character varying, 'public'::character varying])::text[])))
);


--
-- Name: COLUMN raw_files.file_data; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.raw_files.file_data IS 'Original uploaded file bytes (PDF/DOCX/…). Primary durable store.';


--
-- Name: site_assets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.site_assets (
    asset_key character varying(128) NOT NULL,
    filename character varying(255) NOT NULL,
    content_type character varying(100) NOT NULL,
    data bytea,
    byte_size bigint NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    storage_url character varying(1000),
    storage_backend character varying(32) DEFAULT 'postgres'::character varying NOT NULL,
    content_sha256 character varying(64),
    CONSTRAINT site_assets_byte_size_check CHECK ((byte_size >= 0))
);


--
-- Name: support_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.support_requests (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    email character varying(255) NOT NULL,
    user_id character varying(50),
    user_type character varying(20),
    subject character varying(500) NOT NULL,
    message text NOT NULL,
    status character varying(50) DEFAULT 'open'::character varying,
    priority character varying(20) DEFAULT 'medium'::character varying,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    resolved_at timestamp with time zone,
    admin_notes text,
    created_by character varying(50),
    updated_by character varying(50),
    CONSTRAINT support_requests_priority_check CHECK (((priority)::text = ANY ((ARRAY['low'::character varying, 'medium'::character varying, 'high'::character varying, 'urgent'::character varying])::text[]))),
    CONSTRAINT support_requests_status_check CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'in_progress'::character varying, 'resolved'::character varying, 'closed'::character varying])::text[]))),
    CONSTRAINT support_requests_user_type_check CHECK ((((user_type)::text = ANY ((ARRAY['candidate'::character varying, 'hr'::character varying, 'guest'::character varying])::text[])) OR (user_type IS NULL)))
);


--
-- Name: support_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.support_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: support_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.support_requests_id_seq OWNED BY public.support_requests.id;


--
-- Name: sync_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sync_logs (
    id integer NOT NULL,
    company_key character varying(255) NOT NULL,
    provider character varying(64) NOT NULL,
    operation character varying(64) NOT NULL,
    job_id character varying(64),
    external_job_id character varying(128),
    request_payload jsonb,
    response_payload jsonb,
    status character varying(32) NOT NULL,
    execution_time_ms integer,
    retry_count integer DEFAULT 0 NOT NULL,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    organization_id uuid
);


--
-- Name: sync_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sync_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sync_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sync_logs_id_seq OWNED BY public.sync_logs.id;


--
-- Name: applications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications ALTER COLUMN id SET DEFAULT nextval('public.applications_id_seq'::regclass);


--
-- Name: employee_feedback id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_feedback ALTER COLUMN id SET DEFAULT nextval('public.employee_feedback_id_seq'::regclass);


--
-- Name: external_applications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_applications ALTER COLUMN id SET DEFAULT nextval('public.external_applications_id_seq'::regclass);


--
-- Name: external_jobs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_jobs ALTER COLUMN id SET DEFAULT nextval('public.external_jobs_id_seq'::regclass);


--
-- Name: integration_provider id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integration_provider ALTER COLUMN id SET DEFAULT nextval('public.integration_provider_id_seq'::regclass);


--
-- Name: login_history id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_history ALTER COLUMN id SET DEFAULT nextval('public.login_history_id_seq'::regclass);


--
-- Name: oauth_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_tokens ALTER COLUMN id SET DEFAULT nextval('public.oauth_tokens_id_seq'::regclass);


--
-- Name: support_requests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_requests ALTER COLUMN id SET DEFAULT nextval('public.support_requests_id_seq'::regclass);


--
-- Name: sync_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_logs ALTER COLUMN id SET DEFAULT nextval('public.sync_logs_id_seq'::regclass);




--
-- Name: applications applications_candidate_id_job_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_candidate_id_job_id_key UNIQUE (candidate_id, job_id);


--
-- Name: applications applications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_pkey PRIMARY KEY (id);


--
-- Name: auth_refresh_tokens auth_refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_refresh_tokens
    ADD CONSTRAINT auth_refresh_tokens_pkey PRIMARY KEY (jti);


--
-- Name: bulk_parse_files bulk_parse_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bulk_parse_files
    ADD CONSTRAINT bulk_parse_files_pkey PRIMARY KEY (id);


--
-- Name: bulk_parse_sessions bulk_parse_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bulk_parse_sessions
    ADD CONSTRAINT bulk_parse_sessions_pkey PRIMARY KEY (id);


--
-- Name: candidate_profiles candidate_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_profiles
    ADD CONSTRAINT candidate_profiles_pkey PRIMARY KEY (candidate_id);


--
-- Name: candidates candidate_signup_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidates
    ADD CONSTRAINT candidate_signup_email_key UNIQUE (email);


--
-- Name: candidates candidate_signup_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidates
    ADD CONSTRAINT candidate_signup_pkey PRIMARY KEY (cid);


--
-- Name: employee_feedback employee_feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_feedback
    ADD CONSTRAINT employee_feedback_pkey PRIMARY KEY (id);


--
-- Name: external_applications external_applications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_applications
    ADD CONSTRAINT external_applications_pkey PRIMARY KEY (id);


--
-- Name: external_jobs external_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_jobs
    ADD CONSTRAINT external_jobs_pkey PRIMARY KEY (id);


--
-- Name: hr_signup hr_signup_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_signup
    ADD CONSTRAINT hr_signup_email_key UNIQUE (email);


--
-- Name: hr_signup hr_signup_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_signup
    ADD CONSTRAINT hr_signup_pkey PRIMARY KEY (hrid);


--
-- Name: integration_provider integration_provider_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integration_provider
    ADD CONSTRAINT integration_provider_pkey PRIMARY KEY (id);


--
-- Name: interview_slots interview_slots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interview_slots
    ADD CONSTRAINT interview_slots_pkey PRIMARY KEY (id);


--
-- Name: interviews interviews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interviews
    ADD CONSTRAINT interviews_pkey PRIMARY KEY (id);


--
-- Name: jobs jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_pkey PRIMARY KEY (jdid);


--
-- Name: login_history login_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_history
    ADD CONSTRAINT login_history_pkey PRIMARY KEY (id);


--
-- Name: matches matches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matches
    ADD CONSTRAINT matches_pkey PRIMARY KEY (id);


--
-- Name: oauth_tokens oauth_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_tokens
    ADD CONSTRAINT oauth_tokens_pkey PRIMARY KEY (id);


--
-- Name: organizations organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_pkey PRIMARY KEY (id);


--
-- Name: organizations organizations_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_slug_key UNIQUE (slug);


--
-- Name: parsed_jds parsed_jds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parsed_jds
    ADD CONSTRAINT parsed_jds_pkey PRIMARY KEY (id);


--
-- Name: parsed_resumes parsed_resumes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parsed_resumes
    ADD CONSTRAINT parsed_resumes_pkey PRIMARY KEY (id);


--
-- Name: raw_files raw_files_file_hash_uploader_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_files
    ADD CONSTRAINT raw_files_file_hash_uploader_id_key UNIQUE (file_hash, uploader_id);


--
-- Name: raw_files raw_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_files
    ADD CONSTRAINT raw_files_pkey PRIMARY KEY (id);


--
-- Name: site_assets site_assets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.site_assets
    ADD CONSTRAINT site_assets_pkey PRIMARY KEY (asset_key);


--
-- Name: support_requests support_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_requests
    ADD CONSTRAINT support_requests_pkey PRIMARY KEY (id);


--
-- Name: sync_logs sync_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_logs
    ADD CONSTRAINT sync_logs_pkey PRIMARY KEY (id);


--
-- Name: external_applications uq_external_applications_provider_app; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_applications
    ADD CONSTRAINT uq_external_applications_provider_app UNIQUE (company_key, provider, external_application_id);


--
-- Name: external_jobs uq_external_jobs_job_provider; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_jobs
    ADD CONSTRAINT uq_external_jobs_job_provider UNIQUE (job_id, provider);


--
-- Name: integration_provider uq_integration_provider_company_provider; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integration_provider
    ADD CONSTRAINT uq_integration_provider_company_provider UNIQUE (company_key, provider);


--
-- Name: oauth_tokens uq_oauth_tokens_company_provider; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_tokens
    ADD CONSTRAINT uq_oauth_tokens_company_provider UNIQUE (company_key, provider);


--
-- Name: idx_auth_refresh_tokens_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_refresh_tokens_user ON public.auth_refresh_tokens USING btree (user_id);


--
-- Name: idx_external_applications_company; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_external_applications_company ON public.external_applications USING btree (company_key, provider);


--
-- Name: idx_external_applications_job; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_external_applications_job ON public.external_applications USING btree (job_id);


--
-- Name: idx_external_jobs_company; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_external_jobs_company ON public.external_jobs USING btree (company_key);


--
-- Name: idx_external_jobs_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_external_jobs_provider ON public.external_jobs USING btree (provider);


--
-- Name: idx_external_jobs_sync_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_external_jobs_sync_status ON public.external_jobs USING btree (sync_status);


--
-- Name: idx_integration_provider_company; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_integration_provider_company ON public.integration_provider USING btree (company_key);


--
-- Name: idx_login_history_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_login_history_email ON public.login_history USING btree (email, user_type);


--
-- Name: idx_site_assets_updated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_site_assets_updated_at ON public.site_assets USING btree (updated_at DESC);


--
-- Name: idx_sync_logs_company_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sync_logs_company_created ON public.sync_logs USING btree (company_key, created_at DESC);


--
-- Name: idx_sync_logs_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sync_logs_provider ON public.sync_logs USING btree (provider);


--
-- Name: ix_applications_candidate_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_applications_candidate_status ON public.applications USING btree (candidate_id, status);


--
-- Name: ix_applications_job_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_applications_job_status ON public.applications USING btree (job_id, status);


--
-- Name: ix_applications_latest_match; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_applications_latest_match ON public.applications USING btree (latest_match_id);


--
-- Name: ix_applications_shortlisted; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_applications_shortlisted ON public.applications USING btree (shortlisted, match_score DESC NULLS LAST);


--
-- Name: ix_applications_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_applications_status ON public.applications USING btree (status, applied_at DESC);


--
-- Name: ix_bulk_parse_files_session_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bulk_parse_files_session_status ON public.bulk_parse_files USING btree (session_id, status);


--
-- Name: ix_bulk_parse_sessions_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bulk_parse_sessions_owner ON public.bulk_parse_sessions USING btree (created_by, status, created_at DESC);


--
-- Name: ix_candidate_certifications_candidate; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_certifications_candidate ON public.candidate_certifications USING btree (candidate_id);


--
-- Name: ix_candidate_education_candidate; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_education_candidate ON public.candidate_education USING btree (candidate_id);


--
-- Name: ix_candidate_experiences_candidate; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_experiences_candidate ON public.candidate_experiences USING btree (candidate_id);


--
-- Name: ix_candidate_profiles_resume_raw_file; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_profiles_resume_raw_file ON public.candidate_profiles USING btree (resume_raw_file_id);


--
-- Name: ix_employee_feedback_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employee_feedback_created_at ON public.employee_feedback USING btree (created_at DESC);


--
-- Name: ix_employee_feedback_feedback_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employee_feedback_feedback_type ON public.employee_feedback USING btree (feedback_type);


--
-- Name: ix_employee_feedback_module; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employee_feedback_module ON public.employee_feedback USING btree (module);


--
-- Name: ix_employee_feedback_severity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employee_feedback_severity ON public.employee_feedback USING btree (severity);


--
-- Name: ix_employee_feedback_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employee_feedback_status ON public.employee_feedback USING btree (status);


--
-- Name: ix_external_applications_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_external_applications_organization_id ON public.external_applications USING btree (organization_id);


--
-- Name: ix_external_jobs_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_external_jobs_organization_id ON public.external_jobs USING btree (organization_id);


--
-- Name: ix_hr_signup_account_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hr_signup_account_status ON public.hr_signup USING btree (account_status);


--
-- Name: ix_hr_signup_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hr_signup_organization_id ON public.hr_signup USING btree (organization_id);


--
-- Name: ix_hr_signup_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hr_signup_role ON public.hr_signup USING btree (role);


--
-- Name: ix_integration_provider_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_integration_provider_organization_id ON public.integration_provider USING btree (organization_id);


--
-- Name: ix_interview_slots_interview_booked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_interview_slots_interview_booked ON public.interview_slots USING btree (interview_id, is_booked);


--
-- Name: ix_interview_slots_recruiter_start; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_interview_slots_recruiter_start ON public.interview_slots USING btree (recruiter_hrid, start_time);


--
-- Name: ix_interviews_application; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_interviews_application ON public.interviews USING btree (application_id);


--
-- Name: ix_interviews_assigned_scheduled; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_interviews_assigned_scheduled ON public.interviews USING btree (assigned_to, scheduled_at);


--
-- Name: ix_jobs_created_by_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_jobs_created_by_status ON public.jobs USING btree (created_by, status);


--
-- Name: ix_jobs_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_jobs_organization_id ON public.jobs USING btree (organization_id);


--
-- Name: ix_jobs_status_posted; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_jobs_status_posted ON public.jobs USING btree (status, posted_on DESC);


--
-- Name: ix_login_history_attempted_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_login_history_attempted_at ON public.login_history USING btree (attempted_at DESC);


--
-- Name: ix_matches_candidate_job_latest; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_matches_candidate_job_latest ON public.matches USING btree (candidate_id, job_id, is_latest);


--
-- Name: ix_matches_job_score; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_matches_job_score ON public.matches USING btree (job_id, match_score DESC NULLS LAST);


--
-- Name: ix_oauth_tokens_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_oauth_tokens_organization_id ON public.oauth_tokens USING btree (organization_id);


--
-- Name: ix_organizations_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_organizations_slug ON public.organizations USING btree (slug);


--
-- Name: ix_parsed_jds_confidence; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parsed_jds_confidence ON public.parsed_jds USING btree (confidence);


--
-- Name: ix_parsed_jds_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parsed_jds_created_at ON public.parsed_jds USING btree (created_at DESC);


--
-- Name: ix_parsed_jds_job; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parsed_jds_job ON public.parsed_jds USING btree (job_id);


--
-- Name: ix_parsed_jds_raw_file; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parsed_jds_raw_file ON public.parsed_jds USING btree (raw_file_id);


--
-- Name: ix_parsed_resumes_bulk_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parsed_resumes_bulk_session ON public.parsed_resumes USING btree (bulk_session_id);


--
-- Name: ix_parsed_resumes_candidate; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parsed_resumes_candidate ON public.parsed_resumes USING btree (candidate_id);


--
-- Name: ix_parsed_resumes_confidence; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parsed_resumes_confidence ON public.parsed_resumes USING btree (confidence);


--
-- Name: ix_parsed_resumes_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parsed_resumes_created_at ON public.parsed_resumes USING btree (created_at DESC);


--
-- Name: ix_parsed_resumes_raw_file; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_parsed_resumes_raw_file ON public.parsed_resumes USING btree (raw_file_id);


--
-- Name: ix_raw_files_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_raw_files_created_at ON public.raw_files USING btree (created_at DESC);


--
-- Name: ix_raw_files_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_raw_files_hash ON public.raw_files USING btree (file_hash);


--
-- Name: ix_raw_files_uploader; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_raw_files_uploader ON public.raw_files USING btree (uploader_id, uploader_role);


--
-- Name: ix_site_assets_content_sha256; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_site_assets_content_sha256 ON public.site_assets USING btree (content_sha256) WHERE (content_sha256 IS NOT NULL);


--
-- Name: ix_support_requests_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_support_requests_created_at ON public.support_requests USING btree (created_at DESC);


--
-- Name: ix_support_requests_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_support_requests_email ON public.support_requests USING btree (email);


--
-- Name: ix_support_requests_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_support_requests_status ON public.support_requests USING btree (status);


--
-- Name: ix_support_requests_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_support_requests_user_id ON public.support_requests USING btree (user_id);


--
-- Name: ix_sync_logs_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sync_logs_organization_id ON public.sync_logs USING btree (organization_id);


--
-- Name: ux_interviews_invite_token; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_interviews_invite_token ON public.interviews USING btree (invite_token) WHERE (invite_token IS NOT NULL);


--
-- Name: ux_interviews_open_application; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_interviews_open_application ON public.interviews USING btree (application_id) WHERE ((status)::text = ANY ((ARRAY['Invited'::character varying, 'Scheduled'::character varying])::text[]));


--
-- Name: ux_matches_latest; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_matches_latest ON public.matches USING btree (candidate_id, job_id) WHERE is_latest;


--
-- Name: applications trg_applications_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_applications_updated_at BEFORE UPDATE ON public.applications FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: bulk_parse_files trg_bulk_parse_files_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_bulk_parse_files_updated_at BEFORE UPDATE ON public.bulk_parse_files FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: bulk_parse_sessions trg_bulk_parse_sessions_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_bulk_parse_sessions_updated_at BEFORE UPDATE ON public.bulk_parse_sessions FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: candidates trg_candidates_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_candidates_updated_at BEFORE UPDATE ON public.candidates FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: employee_feedback trg_employee_feedback_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_employee_feedback_updated_at BEFORE UPDATE ON public.employee_feedback FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: hr_signup trg_hr_signup_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_hr_signup_updated_at BEFORE UPDATE ON public.hr_signup FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: interviews trg_interviews_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_interviews_updated_at BEFORE UPDATE ON public.interviews FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: jobs trg_jobs_status_enabled_sync; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_jobs_status_enabled_sync BEFORE INSERT OR UPDATE ON public.jobs FOR EACH ROW EXECUTE FUNCTION public.jobs_status_enabled_sync();


--
-- Name: jobs trg_jobs_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_jobs_updated_at BEFORE UPDATE ON public.jobs FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: parsed_jds trg_parsed_jds_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_parsed_jds_updated_at BEFORE UPDATE ON public.parsed_jds FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: parsed_resumes trg_parsed_resumes_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_parsed_resumes_updated_at BEFORE UPDATE ON public.parsed_resumes FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: raw_files trg_raw_files_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_raw_files_updated_at BEFORE UPDATE ON public.raw_files FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: applications applications_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidates(cid);


--
-- Name: applications applications_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.candidates(cid);


--
-- Name: applications applications_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(jdid);


--
-- Name: applications applications_latest_match_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_latest_match_id_fkey FOREIGN KEY (latest_match_id) REFERENCES public.matches(id) ON DELETE SET NULL;


--
-- Name: bulk_parse_files bulk_parse_files_parsed_resume_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bulk_parse_files
    ADD CONSTRAINT bulk_parse_files_parsed_resume_id_fkey FOREIGN KEY (parsed_resume_id) REFERENCES public.parsed_resumes(id) ON DELETE SET NULL;


--
-- Name: bulk_parse_files bulk_parse_files_raw_file_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bulk_parse_files
    ADD CONSTRAINT bulk_parse_files_raw_file_id_fkey FOREIGN KEY (raw_file_id) REFERENCES public.raw_files(id) ON DELETE SET NULL;


--
-- Name: bulk_parse_files bulk_parse_files_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bulk_parse_files
    ADD CONSTRAINT bulk_parse_files_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.bulk_parse_sessions(id) ON DELETE CASCADE;


--
-- Name: bulk_parse_sessions bulk_parse_sessions_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bulk_parse_sessions
    ADD CONSTRAINT bulk_parse_sessions_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.hr_signup(hrid);


--
-- Name: bulk_parse_sessions bulk_parse_sessions_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bulk_parse_sessions
    ADD CONSTRAINT bulk_parse_sessions_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.hr_signup(hrid);


--
-- Name: candidate_certifications candidate_certifications_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_certifications
    ADD CONSTRAINT candidate_certifications_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidates(cid) ON DELETE CASCADE;


--
-- Name: candidate_education candidate_education_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_education
    ADD CONSTRAINT candidate_education_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidates(cid) ON DELETE CASCADE;


--
-- Name: candidate_experiences candidate_experiences_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_experiences
    ADD CONSTRAINT candidate_experiences_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidates(cid) ON DELETE CASCADE;


--
-- Name: candidate_profiles candidate_profiles_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_profiles
    ADD CONSTRAINT candidate_profiles_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidates(cid);


--
-- Name: candidate_profiles candidate_profiles_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_profiles
    ADD CONSTRAINT candidate_profiles_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.candidates(cid);


--
-- Name: candidate_profiles candidate_profiles_resume_raw_file_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_profiles
    ADD CONSTRAINT candidate_profiles_resume_raw_file_id_fkey FOREIGN KEY (resume_raw_file_id) REFERENCES public.raw_files(id) ON DELETE SET NULL;


--
-- Name: employee_feedback employee_feedback_submitted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_feedback
    ADD CONSTRAINT employee_feedback_submitted_by_fkey FOREIGN KEY (submitted_by) REFERENCES public.hr_signup(hrid);


--
-- Name: external_applications external_applications_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_applications
    ADD CONSTRAINT external_applications_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- Name: external_jobs external_jobs_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.external_jobs
    ADD CONSTRAINT external_jobs_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- Name: hr_signup hr_signup_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_signup
    ADD CONSTRAINT hr_signup_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- Name: hr_signup hr_signup_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hr_signup
    ADD CONSTRAINT hr_signup_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.hr_signup(hrid);


--
-- Name: integration_provider integration_provider_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integration_provider
    ADD CONSTRAINT integration_provider_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- Name: interview_slots interview_slots_interview_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interview_slots
    ADD CONSTRAINT interview_slots_interview_id_fkey FOREIGN KEY (interview_id) REFERENCES public.interviews(id) ON DELETE CASCADE;


--
-- Name: interview_slots interview_slots_recruiter_hrid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interview_slots
    ADD CONSTRAINT interview_slots_recruiter_hrid_fkey FOREIGN KEY (recruiter_hrid) REFERENCES public.hr_signup(hrid);


--
-- Name: interviews interviews_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interviews
    ADD CONSTRAINT interviews_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE CASCADE;


--
-- Name: interviews interviews_assigned_to_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interviews
    ADD CONSTRAINT interviews_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES public.hr_signup(hrid);


--
-- Name: interviews interviews_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interviews
    ADD CONSTRAINT interviews_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.hr_signup(hrid);


--
-- Name: interviews interviews_interviewer_hrid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interviews
    ADD CONSTRAINT interviews_interviewer_hrid_fkey FOREIGN KEY (interviewer_hrid) REFERENCES public.hr_signup(hrid);


--
-- Name: interviews interviews_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interviews
    ADD CONSTRAINT interviews_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.hr_signup(hrid);


--
-- Name: jobs jobs_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.hr_signup(hrid);


--
-- Name: jobs jobs_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- Name: jobs jobs_parsed_jd_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_parsed_jd_id_fkey FOREIGN KEY (parsed_jd_id) REFERENCES public.parsed_jds(id) ON DELETE SET NULL;


--
-- Name: jobs jobs_posted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_posted_by_fkey FOREIGN KEY (posted_by) REFERENCES public.hr_signup(hrid);


--
-- Name: jobs jobs_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.hr_signup(hrid);


--
-- Name: matches matches_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matches
    ADD CONSTRAINT matches_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidates(cid);


--
-- Name: matches matches_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matches
    ADD CONSTRAINT matches_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(jdid);


--
-- Name: matches matches_parsed_jd_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matches
    ADD CONSTRAINT matches_parsed_jd_id_fkey FOREIGN KEY (parsed_jd_id) REFERENCES public.parsed_jds(id) ON DELETE SET NULL;


--
-- Name: matches matches_parsed_resume_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matches
    ADD CONSTRAINT matches_parsed_resume_id_fkey FOREIGN KEY (parsed_resume_id) REFERENCES public.parsed_resumes(id) ON DELETE SET NULL;


--
-- Name: oauth_tokens oauth_tokens_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.oauth_tokens
    ADD CONSTRAINT oauth_tokens_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- Name: parsed_jds parsed_jds_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parsed_jds
    ADD CONSTRAINT parsed_jds_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(jdid) ON DELETE SET NULL;


--
-- Name: parsed_jds parsed_jds_raw_file_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parsed_jds
    ADD CONSTRAINT parsed_jds_raw_file_id_fkey FOREIGN KEY (raw_file_id) REFERENCES public.raw_files(id) ON DELETE CASCADE;


--
-- Name: parsed_resumes parsed_resumes_bulk_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parsed_resumes
    ADD CONSTRAINT parsed_resumes_bulk_session_id_fkey FOREIGN KEY (bulk_session_id) REFERENCES public.bulk_parse_sessions(id) ON DELETE SET NULL;


--
-- Name: parsed_resumes parsed_resumes_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parsed_resumes
    ADD CONSTRAINT parsed_resumes_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidates(cid) ON DELETE SET NULL;


--
-- Name: parsed_resumes parsed_resumes_raw_file_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parsed_resumes
    ADD CONSTRAINT parsed_resumes_raw_file_id_fkey FOREIGN KEY (raw_file_id) REFERENCES public.raw_files(id) ON DELETE CASCADE;


--
-- Name: raw_files raw_files_bulk_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_files
    ADD CONSTRAINT raw_files_bulk_session_id_fkey FOREIGN KEY (bulk_session_id) REFERENCES public.bulk_parse_sessions(id) ON DELETE SET NULL;


--
-- Name: sync_logs sync_logs_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_logs
    ADD CONSTRAINT sync_logs_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

-- Restore search_path for Alembic version tracking
SET search_path TO public;
