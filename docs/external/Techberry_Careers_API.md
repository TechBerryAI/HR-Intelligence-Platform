# Techberry Careers API — Integration Guide

**For:** Techberry Infotech WordPress / external website team  
**Platform:** HR Intelligence Platform (HCIP)  
**Last updated:** September 2026

This document explains how to fetch **Techberry Infotech job postings** from the live HCIP API and display them on the company website (e.g. WordPress careers page). No login or API key is required for public job listings.

---

## Quick reference

| Item | Value |
|------|--------|
| **App URL (job board & apply)** | `https://job.techberryinfotech.com` |
| **API base URL** | `https://job.techberryinfotech.com` |
| **Organization name** | Techberry Infotech |
| **Organization slug** | `techberry-infotech` |
| **List all Techberry jobs** | `GET https://job.techberryinfotech.com/api/jobs?company=techberry-infotech` |
| **Single job** | `GET https://job.techberryinfotech.com/api/jobs/{jobId}?company=techberry-infotech` |
| **Apply redirect URL** | `https://job.techberryinfotech.com/c/techberry-infotech/jobs` |
| **Health check** | `GET https://job.techberryinfotech.com/health` |
| **Authentication** | None required for job listing endpoints |

> **Important:** Always include `?company=techberry-infotech` in production. This ensures only Techberry jobs are returned, even if more organizations are added to HCIP later.

---

## Overview

```text
┌─────────────────────────┐         ┌──────────────────────────────────┐
│  Techberry WordPress    │  GET    │  HCIP API                        │
│  www.techberryinfotech  │ ──────► │  job.techberryinfotech.com/api   │
│  .com/careers           │  JSON   │                                  │
└─────────────────────────┘         └──────────────────────────────────┘
            │
            │  User clicks "Apply"
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  HCIP Job Board — job.techberryinfotech.com/c/techberry-infotech/jobs │
│  Candidate selects job → Apply modal → resume upload → ATS          │
└─────────────────────────────────────────────────────────────────────┘
```

This is a **read + redirect** integration:

1. Your website **fetches** job data from the HCIP API.
2. Your website **displays** title, location, description, etc.
3. When a candidate clicks **Apply**, redirect them to the HCIP job board.
4. Application submission (resume, parsing, screening) happens **only on HCIP**.

There is **no webhook** that pushes job updates to your site. Poll the API periodically or on each page load (with short caching).

---

## Public API endpoints

All endpoints below are **public** — do not send an `Authorization` header.

### 1. List organizations (optional)

Use this to confirm the organization slug.

```http
GET https://job.techberryinfotech.com/api/companies/
```

**Example response:**

```json
{
  "companies": [
    {
      "id": "ccaa9cc6-4628-4089-a5cd-4ab65e9c7e78",
      "name": "Techberry Infotech",
      "slug": "techberry-infotech"
    }
  ]
}
```

Only organizations with at least one **enabled** (published) job are returned.

---

### 2. List Techberry jobs

```http
GET https://job.techberryinfotech.com/api/jobs?company=techberry-infotech
```

| Query parameter | Required | Description |
|-----------------|----------|-------------|
| `company` | **Yes (recommended)** | Organization slug: `techberry-infotech` |
| `slug` | Alias | Same as `company` |

**Example response:** JSON array of job objects.

```json
[
  {
    "id": "MWA001",
    "title": "Middleware WebLogic Administrator",
    "company": "Techberry Infotech",
    "location": "Mumbai Work from office",
    "salary": null,
    "experience": "1-5 years",
    "description": "Middleware Weblogic Admin JD:\nExperience- 1 to 5 yrs\n...",
    "keywords": "OHS, IBM, Weblogic, Websphere",
    "enabled": true,
    "postedOn": "Fri, 21 Aug 2026 05:29:51 GMT",
    "parsedJdId": "f965cc5a-19ce-4e1b-b637-bbb3abe9d0cb"
  }
]
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique job ID (e.g. `MWA001`). Use for single-job fetch. |
| `title` | string | Job title |
| `company` | string | Company display name (`Techberry Infotech`) |
| `location` | string | Job location |
| `salary` | string or null | Free-text salary range; may be empty |
| `experience` | string or null | Free-text experience requirement |
| `description` | string | Full job description (**plain text**, not HTML) |
| `keywords` | string | Comma-separated skills/tags |
| `enabled` | boolean | Always `true` in public listings |
| `postedOn` | string | Post date/time (HTTP date format) |
| `parsedJdId` | string or null | Internal reference — not needed for display |

**HTTP status codes:**

| Status | Meaning |
|--------|---------|
| `200` | Success — JSON array (may be empty if no open jobs) |
| `400` | Missing or invalid company configuration |
| `500` | Server error |

**Notes:**

- Only **published (enabled)** jobs are returned.
- When a job is paused or closed on HCIP, it disappears from this endpoint.
- New and updated jobs appear automatically — no manual sync step.

---

### 3. Single job detail

Use when your site has a dedicated page per job.

```http
GET https://job.techberryinfotech.com/api/jobs/{jobId}?company=techberry-infotech
```

**Example:**

```http
GET https://job.techberryinfotech.com/api/jobs/MWA001?company=techberry-infotech
```

Returns one job object (same shape as list items).

| Status | Meaning |
|--------|---------|
| `200` | Job found and published |
| `404` | Job not found, disabled, or not a Techberry job |

---

### 4. Health check (optional monitoring)

```http
GET https://job.techberryinfotech.com/health
```

Returns `200` when the API is running.

---

## Apply flow (redirect)

Send candidates to the HCIP job board. They find the role and submit an application there.

| URL | Purpose |
|-----|---------|
| `https://job.techberryinfotech.com/c/techberry-infotech/jobs` | **Recommended** — Techberry-branded job board |
| `https://job.techberryinfotech.com/jobs` | Default board (works if only one tenant) |

**Example Apply button (HTML):**

```html
<a href="https://job.techberryinfotech.com/c/techberry-infotech/jobs"
   target="_blank"
   rel="noopener noreferrer">
  Apply on our careers portal
</a>
```

### No job-specific apply deep link

HCIP does **not** currently expose a public URL such as `/jobs/{jobId}/apply` that opens the apply form directly for one job. Redirect always goes to the job board listing. Show the job title on your Apply button so the candidate knows which role to select.

### Do not call the apply API from WordPress

`POST /api/jobs/{jobId}/apply` is a public endpoint but is intended for the HCIP apply UI only. It accepts multipart form data with a resume file and triggers parsing and ATS scoring. **Do not integrate this from an external website.**

---

## Recommended integration: WordPress (server-side)

Use **PHP on the WordPress server** (`wp_remote_get`). This avoids CORS issues and keeps the integration simple.

### Step 1 — Add to theme `functions.php` or a custom plugin

```php
<?php
/**
 * Fetch Techberry jobs from HCIP (cached 10 minutes).
 */
function techberry_fetch_jobs() {
    $cache_key = 'techberry_hcip_jobs';
    $cached = get_transient($cache_key);
    if ($cached !== false) {
        return $cached;
    }

    $url = 'https://job.techberryinfotech.com/api/jobs?company=techberry-infotech';

    $response = wp_remote_get($url, [
        'timeout' => 15,
        'headers' => ['Accept' => 'application/json'],
    ]);

    if (is_wp_error($response)) {
        return [];
    }

    if (wp_remote_retrieve_response_code($response) !== 200) {
        return [];
    }

    $jobs = json_decode(wp_remote_retrieve_body($response), true);
    if (!is_array($jobs)) {
        return [];
    }

    set_transient($cache_key, $jobs, 10 * MINUTE_IN_SECONDS);
    return $jobs;
}

/**
 * Shortcode: [techberry_jobs]
 * Add to your Careers page in the WordPress editor.
 */
function techberry_jobs_shortcode() {
    $jobs = techberry_fetch_jobs();
    $apply_url = 'https://job.techberryinfotech.com/c/techberry-infotech/jobs';

    if (empty($jobs)) {
        return '<p>No open positions at the moment. Please check back soon.</p>';
    }

    ob_start();
    echo '<div class="techberry-jobs-list">';

    foreach ($jobs as $job) {
        $title       = esc_html($job['title'] ?? '');
        $location    = esc_html($job['location'] ?? '');
        $experience  = esc_html($job['experience'] ?? '');
        $salary      = esc_html($job['salary'] ?? '');
        $posted      = esc_html($job['postedOn'] ?? '');
        $description = nl2br(esc_html($job['description'] ?? ''));

        echo '<article class="job-card">';
        echo '<h3>' . $title . '</h3>';
        if ($location)   echo '<p><strong>Location:</strong> ' . $location . '</p>';
        if ($experience) echo '<p><strong>Experience:</strong> ' . $experience . '</p>';
        if ($salary)     echo '<p><strong>Salary:</strong> ' . $salary . '</p>';
        if ($posted)     echo '<p><strong>Posted:</strong> ' . $posted . '</p>';
        echo '<div class="job-description">' . $description . '</div>';
        echo '<p><a href="' . esc_url($apply_url) . '" class="button" target="_blank" rel="noopener">Apply for this role</a></p>';
        echo '</article>';
    }

    echo '</div>';
    return ob_get_clean();
}
add_shortcode('techberry_jobs', 'techberry_jobs_shortcode');
```

### Step 2 — Create a Careers page

1. In WordPress: **Pages → Add New** (title e.g. “Careers”).
2. Add shortcode: `[techberry_jobs]`
3. Publish.

### Step 3 — Style (optional)

Add CSS in your theme for `.techberry-jobs-list` and `.job-card` to match the Techberry site design.

### Force refresh during testing

```php
delete_transient('techberry_hcip_jobs');
```

Run once (e.g. via a temporary admin hook or WP-CLI) to clear cached jobs.

---

## Alternative: fetch a single job (WordPress)

```php
function techberry_fetch_job($job_id) {
    $job_id = sanitize_text_field($job_id);
    $url = 'https://job.techberryinfotech.com/api/jobs/'
         . rawurlencode($job_id)
         . '?company=techberry-infotech';

    $response = wp_remote_get($url, ['timeout' => 15]);

    if (is_wp_error($response) || wp_remote_retrieve_response_code($response) !== 200) {
        return null;
    }

    return json_decode(wp_remote_retrieve_body($response), true);
}
```

---

## Alternative: Node.js / other backends

```javascript
const API_BASE = 'https://job.techberryinfotech.com';
const COMPANY_SLUG = 'techberry-infotech';

const res = await fetch(
  `${API_BASE}/api/jobs?company=${encodeURIComponent(COMPANY_SLUG)}`
);

if (!res.ok) {
  throw new Error(`Jobs API returned ${res.status}`);
}

const jobs = await res.json();
// jobs[i].id, .title, .location, .description, ...

const applyUrl = `${API_BASE}/c/${COMPANY_SLUG}/jobs`;
```

---

## Test with curl

```bash
# List Techberry jobs
curl "https://job.techberryinfotech.com/api/jobs?company=techberry-infotech"

# Single job
curl "https://job.techberryinfotech.com/api/jobs/MWA001?company=techberry-infotech"

# Health
curl "https://job.techberryinfotech.com/health"

# Confirm organization slug
curl "https://job.techberryinfotech.com/api/companies/"
```

---

## CORS (browser-side fetch only)

| Where the API is called from | CORS needed? |
|------------------------------|--------------|
| WordPress server (PHP `wp_remote_get`) | **No** |
| Node/Python/other backend | **No** |
| JavaScript in the visitor's browser | **Yes** |

If you call the API directly from browser JavaScript on `https://www.techberryinfotech.com`, the HCIP team must add that origin to the backend `FRONTEND_URLS` environment variable. **Server-side WordPress fetch is recommended** and does not require CORS changes.

---

## Caching and refresh

| Topic | Recommendation |
|-------|----------------|
| Cache duration | 5–15 minutes on your WordPress site |
| Job updates | Appear automatically after cache expires or page reload |
| Paused/closed jobs | Removed from API immediately; clear cache to reflect sooner |
| Webhook push | Not available — poll the API |

---

## What not to do

| Do not | Why |
|--------|-----|
| Omit `?company=techberry-infotech` | May return wrong tenant's jobs in future |
| Use staff APIs (`/api/jobs/all`, `/api/head-hr/*`) | Require login JWT |
| Call `POST /api/jobs/{id}/apply` from WordPress | Resume upload + ATS — HCIP UI only |
| Treat `description` as HTML | It is plain text — escape and use `nl2br` in PHP |
| Cache jobs for hours or days | Stale listings when jobs are closed |

---

## Integration checklist

- [ ] Confirm API responds: `curl https://job.techberryinfotech.com/api/jobs?company=techberry-infotech`
- [ ] Add PHP fetch + shortcode (or equivalent) to WordPress
- [ ] Create Careers page with `[techberry_jobs]`
- [ ] Wire Apply buttons to `https://job.techberryinfotech.com/c/techberry-infotech/jobs`
- [ ] Style job cards to match Techberry website
- [ ] Set cache to 10–15 minutes
- [ ] Test end-to-end: job visible on WordPress → Apply → submit on HCIP

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|--------------|-----|
| Empty job list | No published jobs on HCIP | Publish/enable jobs on job.techberryinfotech.com |
| `400` error | Invalid/missing company slug | Use `?company=techberry-infotech` |
| WordPress shows old jobs | Transient cache | `delete_transient('techberry_hcip_jobs')` or wait for expiry |
| Browser JS fetch fails | CORS not configured | Use server-side PHP instead, or ask HCIP team to add your origin to `FRONTEND_URLS` |
| Apply link wrong page | Wrong URL | Use `/c/techberry-infotech/jobs` |
| `404` on single job | Job closed or wrong ID | Job may have been paused; refresh list |

---

## Support

For integration issues (CORS, missing jobs, slug confirmation), contact the HCIP platform team with:

- Your WordPress careers page URL
- The API URL you are calling
- Organization slug: `techberry-infotech`
- Any error message or HTTP status code

**Internal reference:** Full platform API catalog — [GUIDE.md](../GUIDE.md#career-page-integration)

---

## Changelog

| Date | Change |
|------|--------|
| Sep 2026 | Initial Techberry WordPress integration guide |
