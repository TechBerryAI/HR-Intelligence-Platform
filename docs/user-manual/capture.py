"""
Capture live screenshots for HR Intelligence Platform User Manual.
Organizes by module under docs/user-manual/screenshots/<module>/.

Usage (app running):
  python docs/user-manual/capture.py
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
SHOTS = ROOT / "screenshots"
BASE = os.environ.get("DOC_SHOT_BASE", "http://localhost:5173").rstrip("/")
API = os.environ.get("DOC_SHOT_API", "http://localhost:3000").rstrip("/")

HEAD_HR = (
    os.environ.get("DOC_SHOT_HEAD_HR_EMAIL", "chetan.gore@techberryinfotech.com"),
    os.environ.get("DOC_SHOT_HEAD_HR_PASSWORD", "P@ssw0rd"),
)
CEO = (
    os.environ.get("DOC_SHOT_CEO_EMAIL", "unmesh.tari@techberryinfotech.com"),
    os.environ.get("DOC_SHOT_CEO_PASSWORD", "P@ssw0rd"),
)
RECRUITER = (
    os.environ.get("DOC_SHOT_RECRUITER_EMAIL", "riya.gupta@techberryinfotech.com"),
    os.environ.get("DOC_SHOT_RECRUITER_PASSWORD", "P@ssw0rd"),
)

MANIFEST: list[dict] = []
VIEWPORT = {"width": 1440, "height": 900}


def api_login(email: str, password: str) -> dict:
    payload = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(
        f"{API}/api/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            data = json.loads(res.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:300]
        raise SystemExit(f"Login failed for {email}: HTTP {exc.code} {body}") from exc
    if not data.get("token"):
        raise SystemExit(f"Login failed for {email}: {data}")
    return data


def api_login_optional(email: str, password: str) -> dict | None:
    payload = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(
        f"{API}/api/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            data = json.loads(res.read().decode())
    except urllib.error.HTTPError:
        return None
    return data if data.get("token") else None


def api_get(token: str, path: str):
    req = urllib.request.Request(
        f"{API}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=45) as res:
        return json.loads(res.read().decode())


def annotate(path: Path, boxes: list[tuple[int, int, int, int]] | None = None) -> None:
    """Annotations disabled — screenshots stay clean (no red boxes/callouts)."""
    return


def force_dark_theme(page) -> None:
    """All manual screenshots use dark theme."""
    page.evaluate(
        """() => {
          localStorage.setItem('hcip-theme', 'dark');
          document.documentElement.setAttribute('data-theme', 'dark');
          document.documentElement.classList.add('dark');
          document.documentElement.classList.remove('light');
        }"""
    )


def inject_auth(page, token: str, user: dict, refresh: str | None = None) -> None:
    page.goto(BASE, wait_until="domcontentloaded")
    page.evaluate(
        """([token, user, refresh]) => {
          localStorage.setItem('jwtToken', token);
          if (refresh) localStorage.setItem('refreshToken', refresh);
          localStorage.setItem('authUser', JSON.stringify(user));
          localStorage.setItem('authState', JSON.stringify({
            isLoggedIn: true,
            role: user.role || 'RECRUITER',
            email: user.email || '',
            fullName: user.fullName || user.full_name || '',
            company: user.company || ''
          }));
          localStorage.setItem('user', JSON.stringify(user));
          localStorage.setItem('hcip-theme', 'dark');
          document.documentElement.setAttribute('data-theme', 'dark');
          document.documentElement.classList.add('dark');
          document.documentElement.classList.remove('light');
        }""",
        [token, user, refresh],
    )
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(400)


def clear_auth(page) -> None:
    page.goto(BASE, wait_until="domcontentloaded")
    page.evaluate(
        """() => {
          localStorage.clear();
          sessionStorage.clear();
          localStorage.setItem('hcip-theme', 'dark');
          document.documentElement.setAttribute('data-theme', 'dark');
          document.documentElement.classList.add('dark');
          document.documentElement.classList.remove('light');
        }"""
    )
    page.reload(wait_until="domcontentloaded")
    force_dark_theme(page)


def shot(
    page,
    module: str,
    name: str,
    *,
    title: str,
    action: str,
    expected: str,
    nav_path: str,
    roles: list[str],
    purpose: str,
    boxes: list[tuple[int, int, int, int]] | None = None,
    full_page: bool = False,
) -> None:
    folder = SHOTS / module
    folder.mkdir(parents=True, exist_ok=True)
    rel = f"{module}/{name}.png"
    path = SHOTS / rel
    page.wait_for_timeout(450)
    page.screenshot(path=str(path), full_page=full_page)
    annotate(path, boxes)
    MANIFEST.append(
        {
            "file": rel.replace("\\", "/"),
            "module": module,
            "name": name,
            "title": title,
            "action": action,
            "expected": expected,
            "nav_path": nav_path,
            "roles": roles,
            "purpose": purpose,
        }
    )
    print(f"  + {rel}")


def box_for(page, selector: str, pad: int = 6) -> tuple[int, int, int, int] | None:
    # Support "sel1 || sel2" fallbacks (Playwright CSS cannot mix text= with commas safely)
    selectors = [s.strip() for s in selector.split("||")]
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            if loc.count() == 0:
                continue
            if not loc.is_visible():
                continue
            b = loc.bounding_box()
            if not b:
                continue
            return (
                max(0, int(b["x"]) - pad),
                max(0, int(b["y"]) - pad),
                int(b["width"]) + pad * 2,
                int(b["height"]) + pad * 2,
            )
        except Exception:
            continue
    return None


def boxes(*items: tuple[int, int, int, int] | None) -> list[tuple[int, int, int, int]]:
    return [b for b in items if b]


def capture_public(page) -> None:
    print("== Public ==")
    clear_auth(page)

    page.goto(f"{BASE}/", wait_until="domcontentloaded")
    page.wait_for_selector("text=The Future of", timeout=20000)
    page.wait_for_timeout(1800)
    shot(
        page,
        "01-home",
        "01_landing",
        title="Home / Landing page",
        action="Open the application URL",
        expected=(
            "Dark cinematic landing with HR Intelligence nav (Features, Solutions, Pricing, Contact), "
            "hero copy, Get Started and Watch Demo"
        ),
        nav_path="/",
        roles=["Public"],
        purpose="Introduce the platform and route visitors to the jobs board via Get Started",
        boxes=boxes(box_for(page, "text=Get Started"), box_for(page, "text=Watch Demo")),
    )

    watch = page.get_by_role("button", name=re.compile(r"Watch Demo", re.I)).first
    if watch.count() and watch.is_visible():
        watch.click()
        page.wait_for_timeout(900)
        shot(
            page,
            "01-home",
            "02_watch_demo",
            title="Watch Demo modal",
            action="Click Watch Demo on the landing hero",
            expected="Platform Demo modal opens with the product walkthrough video",
            nav_path="/ → Watch Demo",
            roles=["Public"],
            purpose="Preview the product without leaving the landing page",
        )
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

    page.locator("#features").first.scroll_into_view_if_needed()
    page.wait_for_timeout(700)
    shot(
        page,
        "01-home",
        "03_landing_sections",
        title="Landing — Features, Solutions, Pricing, Contact",
        action="Scroll the landing page (or use Features / Solutions / Pricing / Contact in the nav)",
        expected="Intelligent Features, Solutions, Pricing tiers, and Contact Us CTA",
        nav_path="/#features",
        roles=["Public"],
        purpose="Describe product capabilities and how visitors can get in touch",
        full_page=True,
    )

    page.goto(f"{BASE}/jobs", wait_until="networkidle")
    shot(
        page,
        "03-public-jobs",
        "01_jobs_board",
        title="Public jobs board",
        action="Open Jobs from the navigation bar (or Get Started)",
        expected="List of published jobs with search/filter controls",
        nav_path="/jobs",
        roles=["Public", "RECRUITER", "HEAD_HR", "CEO"],
        purpose="Browse open roles and start an application",
        boxes=boxes(box_for(page, "input"), box_for(page, "button:has-text('Apply')")),
    )

    apply_btn = page.locator("button:has-text('Apply')").first
    if apply_btn.count() and apply_btn.is_visible():
        apply_btn.click()
        page.wait_for_timeout(800)
        shot(
            page,
            "03-public-jobs",
            "02_apply_modal",
            title="Apply to job modal",
            action="Click Apply on a job card",
            expected="Application modal opens with resume upload and profile fields",
            nav_path="/jobs → Apply",
            roles=["Public"],
            purpose="Submit a candidate application with optional AI resume autofill",
            boxes=boxes(box_for(page, "button:has-text('Submit')"), box_for(page, "input[type='file']")),
        )
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

    page.goto(f"{BASE}/support/faq", wait_until="networkidle")
    shot(
        page,
        "04-support",
        "01_faq",
        title="FAQ",
        action="Open Support → FAQ",
        expected="FAQ accordion page with common questions",
        nav_path="/support/faq",
        roles=["Public"],
        purpose="Answer common product questions without contacting support",
        boxes=boxes(box_for(page, "text=Contact Support"), box_for(page, "button || [role='button']")),
    )

    page.goto(f"{BASE}/support/contact", wait_until="networkidle")
    shot(
        page,
        "04-support",
        "02_contact",
        title="Contact Us",
        action="Open Support → Contact Us",
        expected="Support request form (name, email, subject, message, priority)",
        nav_path="/support/contact",
        roles=["Public"],
        purpose="Submit a support request to the operations team",
        boxes=boxes(box_for(page, "button:has-text('Submit')")),
    )

    page.goto(f"{BASE}/support/hrms-feedback", wait_until="networkidle")
    shot(
        page,
        "04-support",
        "03_hrms_feedback",
        title="HRMS Testing Feedback",
        action="Open Support → HRMS Testing Feedback",
        expected="Feedback form for type, module, severity, description, screenshot",
        nav_path="/support/hrms-feedback",
        roles=["Public"],
        purpose="Collect product testing feedback from users",
        boxes=boxes(box_for(page, "button[type='submit'] || button:has-text('Submit')")),
    )


def capture_auth(page) -> None:
    print("== Authentication ==")
    clear_auth(page)

    page.goto(f"{BASE}/login", wait_until="networkidle")
    shot(
        page,
        "02-authentication",
        "01_login_chooser",
        title="Login chooser",
        action="Open /login",
        expected="Split-screen login: product story on the left, HR / Admin Access card with Admin Login",
        nav_path="/login",
        roles=["Public"],
        purpose="Route staff users to admin authentication",
        boxes=boxes(box_for(page, "text=Admin Login || a:has-text('Admin') || button:has-text('Admin')")),
    )

    page.goto(f"{BASE}/login/admin", wait_until="networkidle")
    # Ensure clean empty form
    email = page.locator("input[type='email'], input[name='email']").first
    pwd = page.locator("input[type='password']").first
    if email.count():
        email.fill("")
    if pwd.count():
        pwd.fill("")
    shot(
        page,
        "02-authentication",
        "02_login_admin_empty",
        title="Admin login form (empty)",
        action="Open Admin Login",
        expected="Email and password fields with Sign in button",
        nav_path="/login/admin",
        roles=["Public → staff"],
        purpose="Authenticate Recruiter, Head HR, or CEO accounts",
        boxes=None,
    )

    if email.count():
        email.fill(HEAD_HR[0])
        if pwd.count():
            pwd.fill("")  # keep password empty for this step
        shot(
            page,
            "02-authentication",
            "03_login_email_filled",
            title="Email entered",
            action="Enter staff email address",
            expected="Email field shows the entered address; password still empty",
            nav_path="/login/admin",
            roles=["Public → staff"],
            purpose="Identify the staff account",
            boxes=None,
        )
    if pwd.count():
        pwd.fill(HEAD_HR[1])
        shot(
            page,
            "02-authentication",
            "04_login_password_filled",
            title="Password entered",
            action="Enter password",
            expected="Password field is filled (masked)",
            nav_path="/login/admin",
            roles=["Public → staff"],
            purpose="Prove account ownership",
            boxes=None,
        )

    page.goto(f"{BASE}/forgot-password/admin", wait_until="networkidle")
    shot(
        page,
        "02-authentication",
        "05_forgot_password",
        title="Forgot password — request OTP",
        action="From Admin Login, open Forgot password and enter work email",
        expected="Reset with OTP form: work email field, Send OTP, Back to login",
        nav_path="/forgot-password/admin",
        roles=["Public → staff"],
        purpose="Start staff password reset by emailing a 6-digit OTP (valid 10 minutes)",
        boxes=None,
    )

    forgot_email = page.locator("input[type='email']").first
    if forgot_email.count():
        forgot_email.fill(HEAD_HR[0])
        shot(
            page,
            "02-authentication",
            "05b_forgot_password_email",
            title="Forgot password — email entered",
            action="Enter the staff work email, then click Send OTP",
            expected="Work email filled; Send OTP ready; note that OTP is valid for 10 minutes",
            nav_path="/forgot-password/admin",
            roles=["Public → staff"],
            purpose="Identify the account that will receive the password-reset OTP",
            boxes=None,
        )

    page.goto(
        f"{BASE}/forgot-password/admin/verify?email={HEAD_HR[0]}",
        wait_until="networkidle",
    )
    shot(
        page,
        "02-authentication",
        "05c_forgot_password_verify",
        title="Forgot password — verify OTP",
        action="Open the email, copy the 6-digit OTP, enter it, optionally Resend OTP",
        expected="Verify OTP form with email (read-only), 6-digit OTP field, Verify OTP and Resend OTP",
        nav_path="/forgot-password/admin/verify",
        roles=["Public → staff"],
        purpose="Confirm ownership of the email before allowing a password change",
        boxes=None,
    )

    page.goto(
        f"{BASE}/forgot-password/admin/reset?email={HEAD_HR[0]}&otp=000000",
        wait_until="networkidle",
    )
    shot(
        page,
        "02-authentication",
        "05d_forgot_password_reset",
        title="Forgot password — set new password",
        action="After OTP verification, choose a strong new password and confirm it",
        expected="Create new password form with strength rules, Reset password button",
        nav_path="/forgot-password/admin/reset",
        roles=["Public → staff"],
        purpose="Complete password recovery and return to Admin Login",
        boxes=None,
    )



def capture_head_hr(page, token: str, user: dict, jdid: str, cid: str) -> None:
    print("== Head HR ==")
    inject_auth(page, token, user)

    page.goto(f"{BASE}/head-hr", wait_until="networkidle")
    page.wait_for_timeout(800)
    shot(
        page,
        "05-head-hr-overview",
        "01_dashboard",
        title="Head HR Overview Dashboard",
        action="Sign in as Head HR (or open /head-hr)",
        expected="Head of HR sidebar (Workspace / Tools), org snapshot, and job posting tools",
        nav_path="/head-hr",
        roles=["HEAD_HR"],
        purpose="Org-wide recruitment overview and job posting for Head of HR",
        boxes=boxes(box_for(page, "a:has-text('Overview')"), box_for(page, "a:has-text('Jobs')")),
        full_page=True,
    )

    page.goto(f"{BASE}/head-hr/admins", wait_until="networkidle")
    shot(
        page,
        "06-head-hr-admins",
        "01_admins",
        title="Admins management",
        action="Sidebar → Admins",
        expected="Table of HR admin/recruiter accounts with create/delete actions",
        nav_path="/head-hr/admins",
        roles=["HEAD_HR"],
        purpose="Provision and manage recruiter/admin users for the organization",
        boxes=boxes(box_for(page, "button:has-text('Create')"), box_for(page, "button:has-text('Refresh')")),
        full_page=True,
    )

    page.goto(f"{BASE}/head-hr/candidates", wait_until="networkidle")
    shot(
        page,
        "07-head-hr-candidates",
        "01_candidates",
        title="Candidates list",
        action="Sidebar → Candidates",
        expected="Org-wide candidate table with search and row actions",
        nav_path="/head-hr/candidates",
        roles=["HEAD_HR"],
        purpose="Browse all candidates known to the organization",
        boxes=boxes(box_for(page, "input"), box_for(page, "table || [role='table']")),
        full_page=True,
    )

    page.goto(f"{BASE}/head-hr/candidates/{cid}", wait_until="networkidle")
    page.wait_for_timeout(600)
    shot(
        page,
        "07-head-hr-candidates",
        "02_candidate_detail",
        title="Candidate detail",
        action=f"Open candidate {cid} from the candidates list",
        expected="Candidate profile detail for the selected CID",
        nav_path=f"/head-hr/candidates/{cid}",
        roles=["HEAD_HR"],
        purpose="Review a candidate’s stored profile information",
        boxes=boxes(box_for(page, "button:has-text('Back') || a:has-text('Back')")),
        full_page=True,
    )

    page.goto(f"{BASE}/head-hr/jobs", wait_until="networkidle")
    shot(
        page,
        "08-head-hr-jobs",
        "01_jobs_list",
        title="Head HR Jobs list",
        action="Sidebar → Jobs",
        expected="Organization job list with search, refresh, edit/delete (Head HR)",
        nav_path="/head-hr/jobs",
        roles=["HEAD_HR"],
        purpose="Manage all jobs across recruiters in the organization",
        boxes=boxes(box_for(page, "button:has-text('Refresh')"), box_for(page, "input")),
        full_page=True,
    )

    page.goto(f"{BASE}/head-hr/jobs/{jdid}", wait_until="networkidle")
    page.wait_for_timeout(800)
    shot(
        page,
        "09-head-hr-job-detail",
        "01_job_detail",
        title="Job details with applicants",
        action=f"Open job {jdid} from the jobs list",
        expected="Job Details / Candidates tabs with applicant rows",
        nav_path=f"/head-hr/jobs/{jdid}",
        roles=["HEAD_HR"],
        purpose="Inspect a job posting and its applied candidates",
        boxes=boxes(box_for(page, "button:has-text('Candidates') || [role='tab']:has-text('Candidates')")),
        full_page=True,
    )

    # Prefer Candidates tab (label includes count, e.g. "Candidates (2)")
    page.wait_for_timeout(1200)
    tab = page.get_by_role("button", name=re.compile(r"Candidates", re.I)).first
    if tab.count() == 0:
        tab = page.locator("text=/Candidates \\(/").first
    if tab.count() and tab.is_visible():
        tab.click()
        page.wait_for_timeout(800)
        shot(
            page,
            "09-head-hr-job-detail",
            "02_job_applicants",
            title="Applied candidates for job",
            action="Open the Candidates tab on job detail",
            expected="Table of applicants for this job",
            nav_path=f"/head-hr/jobs/{jdid} → Candidates",
            roles=["HEAD_HR"],
            purpose="Review who applied and open evaluation",
            boxes=boxes(box_for(page, "table || [role='table']")),
            full_page=True,
        )

    page.goto(f"{BASE}/head-hr/jobs/{jdid}/candidates/{cid}", wait_until="networkidle")
    page.wait_for_timeout(1000)
    shot(
        page,
        "10-candidate-evaluation",
        "01_profile_tab",
        title="Candidate Evaluation — Profile & Resume",
        action=f"Open applicant {cid} for job {jdid}",
        expected="Profile & Resume tab with candidate identity and resume actions",
        nav_path=f"/head-hr/jobs/{jdid}/candidates/{cid}",
        roles=["HEAD_HR", "CEO (read-only)"],
        purpose="Evaluate applicant profile against the job",
        boxes=boxes(box_for(page, "button:has-text('Profile') || text=Profile & Resume")),
        full_page=True,
    )

    page.goto(f"{BASE}/head-hr/jobs/{jdid}/candidates/{cid}?tab=application", wait_until="networkidle")
    page.wait_for_timeout(1000)
    shot(
        page,
        "10-candidate-evaluation",
        "02_match_tab",
        title="Candidate Evaluation — Application & Match",
        action="Open Application & Match tab",
        expected="ATS score, verdict, and match breakdown",
        nav_path=f"/head-hr/jobs/{jdid}/candidates/{cid}?tab=application",
        roles=["HEAD_HR", "CEO (read-only)"],
        purpose="Explain AI/ATS match scoring for the application",
        boxes=boxes(box_for(page, "text=Application & Match")),
        full_page=True,
    )

    page.goto(f"{BASE}/head-hr/bulk-parsing", wait_until="networkidle")
    shot(
        page,
        "11-bulk-parsing",
        "01_bulk_parsing",
        title="Bulk Resume Parser (Head HR)",
        action="Sidebar → Bulk Parsing",
        expected="Bulk upload workspace (ZIP/files, output, parse controls)",
        nav_path="/head-hr/bulk-parsing",
        roles=["HEAD_HR"],
        purpose="Parse many resumes in a batch for recruitment intake",
        boxes=boxes(box_for(page, "button:has-text('Upload') || button:has-text('Parse') || button:has-text('Browse')")),
        full_page=True,
    )
    _append_preserved_bulk_shots()

    page.goto(f"{BASE}/head-hr/integrations", wait_until="networkidle")
    shot(
        page,
        "12-integrations",
        "01_integrations",
        title="Integrations (Head HR)",
        action="Sidebar → Integrations",
        expected="External publishing / integrations dashboard",
        nav_path="/head-hr/integrations",
        roles=["HEAD_HR"],
        purpose="Monitor and configure job-board integrations",
        boxes=boxes(box_for(page, "button:has-text('Refresh') || a:has-text('Settings')")),
        full_page=True,
    )

    page.goto(f"{BASE}/head-hr/settings", wait_until="networkidle")
    shot(
        page,
        "13-settings",
        "01_head_hr_settings",
        title="Head HR Settings",
        action="Sidebar → Settings",
        expected="Settings page with Security / Integrations tabs",
        nav_path="/head-hr/settings",
        roles=["HEAD_HR"],
        purpose="Change password and manage integration settings",
        boxes=boxes(box_for(page, "button:has-text('Security') || [role='tab']:has-text('Security')")),
        full_page=True,
    )


def capture_recruiter(page, token: str, user: dict) -> None:
    print("== Recruiter ==")
    inject_auth(page, token, user)

    page.goto(f"{BASE}/dashboard", wait_until="networkidle")
    page.wait_for_timeout(900)
    shot(
        page,
        "14-recruiter-dashboard",
        "01_dashboard",
        title="Recruiter Dashboard",
        action="Sign in as Recruiter (lands on /dashboard)",
        expected="Recruiter stats, publishing section, and job create/list workspace",
        nav_path="/dashboard",
        roles=["RECRUITER"],
        purpose="Create, edit, publish, and manage the recruiter’s own jobs",
        boxes=boxes(box_for(page, "button:has-text('Post') || button:has-text('Preview')")),
        full_page=True,
    )

    page.goto(f"{BASE}/candidates", wait_until="networkidle")
    shot(
        page,
        "15-recruiter-candidates",
        "01_applied_candidates",
        title="Applied Candidates (Recruiter)",
        action="Navbar avatar menu → Candidates",
        expected="Applicants for recruiter jobs with shortlist/reject and match reason",
        nav_path="/candidates",
        roles=["RECRUITER"],
        purpose="Review and act on applications to the recruiter’s jobs",
        boxes=boxes(box_for(page, "select"), box_for(page, "button:has-text('Shortlist') || button:has-text('Reject')")),
        full_page=True,
    )

    page.goto(f"{BASE}/admin/bulk-resume-parser", wait_until="networkidle")
    shot(
        page,
        "16-recruiter-bulk",
        "01_bulk_parser",
        title="Bulk Resume Parser (Recruiter)",
        action="Navbar avatar menu → Bulk Resume Parser",
        expected="Same bulk parsing workspace under /admin/bulk-resume-parser",
        nav_path="/admin/bulk-resume-parser",
        roles=["RECRUITER"],
        purpose="Batch-parse resumes for the recruiter workflow",
        boxes=boxes(box_for(page, "button:has-text('Upload') || button:has-text('Parse')")),
        full_page=True,
    )

    page.goto(f"{BASE}/admin/feedback", wait_until="networkidle")
    shot(
        page,
        "17-feedback-admin",
        "01_feedback_admin",
        title="Feedback Admin",
        action="Navbar avatar menu → Feedback (Admin)",
        expected="Feedback inbox with filters and refresh",
        nav_path="/admin/feedback",
        roles=["RECRUITER"],
        purpose="Review submitted HRMS testing feedback",
        boxes=boxes(box_for(page, "button:has-text('Refresh') || button:has-text('Filter')")),
        full_page=True,
    )

    page.goto(f"{BASE}/integrations", wait_until="networkidle")
    shot(
        page,
        "18-recruiter-integrations",
        "01_integrations",
        title="Integrations (Recruiter)",
        action="Navbar avatar menu → Integrations",
        expected="Integrations dashboard for the recruiter session",
        nav_path="/integrations",
        roles=["RECRUITER", "HEAD_HR", "CEO"],
        purpose="View integration health and open settings",
        boxes=boxes(box_for(page, "button:has-text('Refresh')")),
        full_page=True,
    )

    page.goto(f"{BASE}/settings", wait_until="networkidle")
    shot(
        page,
        "19-recruiter-settings",
        "01_settings",
        title="Settings (Recruiter)",
        action="Navbar avatar menu → Settings",
        expected="Security password change and integrations settings tabs",
        nav_path="/settings",
        roles=["RECRUITER", "HEAD_HR", "CEO"],
        purpose="Manage account security settings",
        boxes=boxes(box_for(page, "button:has-text('Update') || button:has-text('password')")),
        full_page=True,
    )


def capture_ceo(page, token: str, user: dict, jdid: str, cid: str) -> None:
    print("== CEO ==")
    inject_auth(page, token, user)

    page.goto(f"{BASE}/ceo", wait_until="networkidle")
    page.wait_for_timeout(800)
    shot(
        page,
        "20-ceo-overview",
        "01_dashboard",
        title="CEO / Executive Overview",
        action="Sign in as CEO (lands on /ceo)",
        expected="Read-only Executive sidebar plus analytics (applications by status, match scores)",
        nav_path="/ceo",
        roles=["CEO"],
        purpose="Executive read-only view of organization recruitment health",
        boxes=boxes(box_for(page, "a:has-text('Overview')"), box_for(page, "a:has-text('Jobs')")),
        full_page=True,
    )

    page.goto(f"{BASE}/ceo/jobs", wait_until="networkidle")
    shot(
        page,
        "20-ceo-overview",
        "02_jobs_readonly",
        title="CEO Jobs (read-only)",
        action="Sidebar → Jobs",
        expected="Jobs list without destructive create/delete controls",
        nav_path="/ceo/jobs",
        roles=["CEO"],
        purpose="Inspect open jobs without modifying them",
        boxes=boxes(box_for(page, "a:has-text('Jobs')")),
        full_page=True,
    )

    page.goto(f"{BASE}/ceo/candidates", wait_until="networkidle")
    shot(
        page,
        "20-ceo-overview",
        "03_candidates_readonly",
        title="CEO Candidates (read-only)",
        action="Sidebar → Candidates",
        expected="Candidates list in read-only executive mode",
        nav_path="/ceo/candidates",
        roles=["CEO"],
        purpose="Inspect candidate pipeline without destructive actions",
        boxes=boxes(box_for(page, "a:has-text('Candidates')")),
        full_page=True,
    )

    page.goto(f"{BASE}/ceo/jobs/{jdid}/candidates/{cid}", wait_until="networkidle")
    page.wait_for_timeout(800)
    shot(
        page,
        "20-ceo-overview",
        "04_eval_readonly",
        title="CEO candidate evaluation (read-only)",
        action=f"Open /ceo/jobs/{jdid}/candidates/{cid}",
        expected="Same evaluation UI as Head HR, without write actions",
        nav_path=f"/ceo/jobs/{jdid}/candidates/{cid}",
        roles=["CEO"],
        purpose="Review match analysis for executive insight",
        full_page=True,
    )


def capture_logout(page, token: str, user: dict) -> None:
    print("== Logout ==")
    inject_auth(page, token, user)
    page.goto(f"{BASE}/head-hr", wait_until="networkidle")
    logout = page.get_by_role("button", name=re.compile(r"Logout", re.I)).first
    if logout.count() == 0:
        logout = page.locator("text=Logout").first
    if logout.count():
        try:
            logout.scroll_into_view_if_needed()
        except Exception:
            pass
        page.wait_for_timeout(300)
        shot(
            page,
            "21-logout",
            "01_logout_control",
            title="Logout control",
            action="Locate Logout in the Head HR sidebar",
            expected="Logout control is visible in the panel chrome",
            nav_path="/head-hr → Logout",
            roles=["HEAD_HR", "CEO", "RECRUITER"],
            purpose="End the authenticated staff session",
            boxes=boxes(box_for(page, "button:has-text('Logout') || text=Logout")),
        )
        logout.click()
        page.wait_for_timeout(1000)
        shot(
            page,
            "21-logout",
            "02_after_logout",
            title="After logout",
            action="Click Logout",
            expected="Session cleared; user returned to admin login (or public home for recruiter)",
            nav_path="/login/admin (Head HR / CEO)",
            roles=["HEAD_HR", "CEO", "RECRUITER"],
            purpose="Prevent unauthorized access after the user finishes work",
            boxes=boxes(box_for(page, "button:has-text('Sign') || input[type='email']")),
        )
    else:
        print("  ! Logout control not found — skipped")


# Manual extras not recaptured by Playwright (OS file dialog / live parse progress)
PRESERVE_SHOTS = (
    "11-bulk-parsing/02_browse_file_dialog.png",
    "11-bulk-parsing/03_bulk_parsing_progress.png",
)
RECRUITER_PRESERVE_SHOTS = (
    "14-recruiter-dashboard/01_dashboard.png",
    "15-recruiter-candidates/01_applied_candidates.png",
    "16-recruiter-bulk/01_bulk_parser.png",
    "17-feedback-admin/01_feedback_admin.png",
    "18-recruiter-integrations/01_integrations.png",
    "19-recruiter-settings/01_settings.png",
)
PRESERVE_META = {
    "11-bulk-parsing/02_browse_file_dialog.png": {
        "title": "Browse and select ZIP or resume files",
        "action": "Click Browse or Upload ZIP and choose files in the system file dialog",
        "expected": "Windows Open dialog appears so you can select a ZIP or resume files from your computer",
        "nav_path": "/head-hr/bulk-parsing → Browse / Upload ZIP",
        "purpose": "Select the resume ZIP or files to parse",
    },
    "11-bulk-parsing/03_bulk_parsing_progress.png": {
        "title": "Bulk parsing in progress",
        "action": "After selecting input and output, start Parse and watch progress",
        "expected": "Processing status, progress bar, processed/failed/queued counts, and file activity lists update live",
        "nav_path": "/head-hr/bulk-parsing → Parse",
        "purpose": "Monitor batch resume parsing until completion",
    },
}


def _append_preserved_recruiter_shots() -> None:
    meta_by_file = {
        "14-recruiter-dashboard/01_dashboard.png": (
            "14-recruiter-dashboard",
            "Recruiter Dashboard",
            "Sign in as Recruiter (lands on /dashboard)",
            "Recruiter stats, publishing section, and job create/list workspace",
            "/dashboard",
            "Create, edit, publish, and manage the recruiter’s own jobs",
        ),
        "15-recruiter-candidates/01_applied_candidates.png": (
            "15-recruiter-candidates",
            "Applied Candidates (Recruiter)",
            "Navbar avatar menu → Candidates",
            "Applicants for recruiter jobs with shortlist/reject and match reason",
            "/candidates",
            "Review and act on applications to the recruiter’s jobs",
        ),
        "16-recruiter-bulk/01_bulk_parser.png": (
            "16-recruiter-bulk",
            "Bulk Resume Parser (Recruiter)",
            "Navbar avatar menu → Bulk Resume Parser",
            "Same bulk parsing workspace under /admin/bulk-resume-parser",
            "/admin/bulk-resume-parser",
            "Batch-parse resumes for the recruiter workflow",
        ),
        "17-feedback-admin/01_feedback_admin.png": (
            "17-feedback-admin",
            "Feedback Admin",
            "Navbar avatar menu → Feedback (Admin)",
            "Feedback inbox with filters and refresh",
            "/admin/feedback",
            "Review submitted HRMS testing feedback",
        ),
        "18-recruiter-integrations/01_integrations.png": (
            "18-recruiter-integrations",
            "Integrations (Recruiter)",
            "Navbar avatar menu → Integrations",
            "Integrations dashboard for the recruiter session",
            "/integrations",
            "View integration health and open settings",
        ),
        "19-recruiter-settings/01_settings.png": (
            "19-recruiter-settings",
            "Settings (Recruiter)",
            "Navbar avatar menu → Settings",
            "Security password change and integrations settings tabs",
            "/settings",
            "Manage account security settings",
        ),
    }
    for rel, (module, title, action, expected, nav_path, purpose) in meta_by_file.items():
        if not (SHOTS / rel).is_file():
            continue
        MANIFEST.append(
            {
                "file": rel,
                "module": module,
                "name": Path(rel).stem,
                "title": title,
                "action": action,
                "expected": expected,
                "nav_path": nav_path,
                "roles": ["RECRUITER"],
                "purpose": purpose,
            }
        )
        print(f"  + {rel} (preserved)")


def _append_preserved_bulk_shots() -> None:
    for rel, meta in PRESERVE_META.items():
        path = SHOTS / rel
        if not path.is_file():
            continue
        MANIFEST.append(
            {
                "file": rel,
                "module": "11-bulk-parsing",
                "name": Path(rel).stem,
                "title": meta["title"],
                "action": meta["action"],
                "expected": meta["expected"],
                "nav_path": meta["nav_path"],
                "roles": ["HEAD_HR"],
                "purpose": meta["purpose"],
            }
        )
        print(f"  + {rel} (preserved)")


def main() -> None:
    head = api_login(*HEAD_HR)
    ceo = api_login(*CEO)
    recruiter = api_login_optional(*RECRUITER)
    if recruiter is None:
        print("! Recruiter login failed — keeping previous recruiter screenshots")

    preserved: dict[str, bytes] = {}
    keep = list(PRESERVE_SHOTS)
    if recruiter is None:
        keep.extend(RECRUITER_PRESERVE_SHOTS)
    if SHOTS.exists():
        for rel in dict.fromkeys(keep):
            p = SHOTS / rel
            if p.is_file():
                preserved[rel] = p.read_bytes()
        for p in SHOTS.rglob("*"):
            if p.is_file():
                p.unlink()
    SHOTS.mkdir(parents=True, exist_ok=True)
    for rel, data in preserved.items():
        dest = SHOTS / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    apps = api_get(head["token"], "/api/head-hr/applications").get("applications") or []
    jdid = "PDA001"
    cid = "CID007"
    for a in apps:
        jid = a.get("job_id") or a.get("jdid")
        c = a.get("candidate_id") or a.get("cid")
        if jid and c:
            jdid, cid = str(jid), str(c)
            if jid == "PDA001":
                break
    print(f"Using job={jdid} candidate={cid}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=1.5)
        page = context.new_page()
        page.set_default_timeout(45000)

        capture_public(page)
        capture_auth(page)
        capture_head_hr(page, head["token"], head.get("user") or head, jdid, cid)
        if recruiter:
            capture_recruiter(page, recruiter["token"], recruiter.get("user") or recruiter)
        else:
            _append_preserved_recruiter_shots()
        capture_ceo(page, ceo["token"], ceo.get("user") or ceo, jdid, cid)
        capture_logout(
            page,
            head["token"],
            head.get("user") or head,
        )

        browser.close()

    manifest_path = SHOTS / "manifest.json"
    manifest_path.write_text(json.dumps(MANIFEST, indent=2), encoding="utf-8")
    print(f"Wrote {len(MANIFEST)} figures → {manifest_path}")


if __name__ == "__main__":
    main()
