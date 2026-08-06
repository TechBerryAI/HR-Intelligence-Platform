"""
Professional HTML email templates for HR Intelligence.
All emails use a consistent branded layout for a premium experience.
"""
import html as html_module
from typing import Optional

BRAND_NAME = "HR Intelligence"
BRAND_SHORT = "HR Intelligence"
SUPPORT_EMAIL = "support@hrintelligence.com"


def _escape(s: Optional[str]) -> str:
    if s is None:
        return ""
    return html_module.escape(str(s).strip(), quote=True)


def _wrap_content(title: str, content_html: str, preheader: Optional[str] = None) -> str:
    """Wrap content in a responsive, professional layout with inline styles for email clients."""
    preheader_snippet = f'<div style="display:none;max-height:0;overflow:hidden;">{_escape(preheader or title)}</div>' if preheader else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_escape(title)}</title>
  {preheader_snippet}
</head>
<body style="margin:0; padding:0; background-color:#f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f1f5f9;">
    <tr>
      <td align="center" style="padding: 32px 16px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 560px; background-color:#ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.07); overflow: hidden;">
          <!-- Header -->
          <tr>
            <td style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 28px 32px; text-align: center;">
              <h1 style="margin:0; font-size: 22px; font-weight: 700; color: #ffffff; letter-spacing: -0.02em;">{_escape(BRAND_NAME)}</h1>
              <p style="margin: 6px 0 0 0; font-size: 13px; color: #94a3b8;">{_escape(BRAND_SHORT)}</p>
            </td>
          </tr>
          <!-- Content -->
          <tr>
            <td style="padding: 32px 28px; color: #334155; font-size: 15px; line-height: 1.6;">
              {content_html}
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 20px 28px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center;">
              <p style="margin:0; font-size: 12px; color: #64748b;">This is an automated message from {_escape(BRAND_NAME)}.</p>
              <p style="margin: 6px 0 0 0; font-size: 12px; color: #94a3b8;">© {BRAND_SHORT}. All rights reserved.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _row(label: str, value: str, last: bool = False) -> str:
    v = _escape(value) or "—"
    border = "" if last else " border-bottom: 1px solid #e2e8f0;"
    return f"""
    <tr>
      <td style="padding: 10px 0; font-weight: 600; color: #475569; font-size: 13px; width: 140px; vertical-align: top;{border}">{_escape(label)}</td>
      <td style="padding: 10px 0; color: #0f172a; font-size: 14px;{border}">{v}</td>
    </tr>"""


def support_request_html(name: str, email: str, user_type: str, priority: str, request_id, message: str) -> str:
    """Support / Contact Us submission."""
    rows = [
        _row("Name", name),
        _row("Email", email),
        _row("User type", user_type),
        _row("Priority", priority),
        _row("Request ID", f"#{request_id}"),
        _row("Message", message, last=True),
    ]
    table = f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse: collapse;">{"".join(rows)}</table>'
    content = f"""
    <h2 style="margin: 0 0 20px 0; font-size: 18px; font-weight: 700; color: #0f172a;">New Support Request</h2>
    <p style="margin: 0 0 20px 0; color: #64748b; font-size: 14px;">A new contact form submission has been received.</p>
    {table}
    """
    return _wrap_content("Support Request", content, preheader=f"Support request from {name}")


def hrms_feedback_html(
    employee_name: str,
    employee_id: Optional[str],
    department: Optional[str],
    feedback_type: str,
    module: Optional[str],
    severity: Optional[str],
    description: str,
    created_at: Optional[str],
    screenshot_path: Optional[str],
) -> str:
    """HRMS Testing Feedback submission."""
    rows = [
        _row("Employee Name", employee_name),
        _row("Employee ID", employee_id or "N/A"),
        _row("Department", department or "N/A"),
        _row("Feedback Type", feedback_type),
        _row("Module", module or "—"),
        _row("Severity", severity or "N/A"),
        _row("Submitted", created_at or "—"),
        _row("Description", description, last=not screenshot_path),
    ]
    if screenshot_path:
        rows.append(_row("Screenshot", screenshot_path, last=True))
    table = f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse: collapse;">{"".join(rows)}</table>'
    content = f"""
    <h2 style="margin: 0 0 20px 0; font-size: 18px; font-weight: 700; color: #0f172a;">HRMS Testing Feedback</h2>
    <p style="margin: 0 0 20px 0; color: #64748b; font-size: 14px;">New internal feedback has been submitted.</p>
    {table}
    """
    return _wrap_content("HRMS Feedback", content, preheader=f"{feedback_type} – {module or 'General'}")


def otp_html(otp: str, user_type: str = "User", *, purpose: str = "verification", minutes: int = 5) -> str:
    """OTP verification email."""
    greeting = "HR" if user_type.lower() == "hr" else "Candidate"
    if purpose == "password_reset":
        title = "Password reset code"
        lead = (
            f"Dear {_escape(greeting)}, use the code below to reset your HR Intelligence password. "
            f"It expires in <strong>{minutes} minutes</strong>."
        )
    else:
        title = "Your verification code"
        lead = (
            f"Dear {_escape(greeting)}, use the code below to complete your verification. "
            f"It expires in <strong>{minutes} minutes</strong>."
        )
    content = f"""
    <h2 style="margin: 0 0 16px 0; font-size: 18px; font-weight: 700; color: #0f172a;">{title}</h2>
    <p style="margin: 0 0 24px 0; color: #64748b;">{lead}</p>
    <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #fff; font-size: 28px; font-weight: 700; letter-spacing: 8px; text-align: center; padding: 20px 24px; border-radius: 10px; margin-bottom: 24px;">
      {_escape(otp)}
    </div>
    <p style="margin: 0; font-size: 13px; color: #94a3b8;">If you did not request this code, please ignore this email.</p>
    """
    return _wrap_content(title, content, preheader=f"Your OTP is {otp}")


def welcome_hr_html(full_name: str) -> str:
    """Welcome email after HR signup verification."""
    name = _escape(full_name) or "there"
    content = f"""
    <h2 style="margin: 0 0 16px 0; font-size: 18px; font-weight: 700; color: #0f172a;">Welcome to {_escape(BRAND_SHORT)}</h2>
    <p style="margin: 0 0 16px 0;">Hi {name},</p>
    <p style="margin: 0 0 16px 0;">Your HR account has been verified and is ready to use. You can now log in to manage jobs and applicants.</p>
    <p style="margin: 0; color: #64748b; font-size: 14px;">If you did not initiate this signup, please contact support immediately.</p>
    """
    return _wrap_content("Welcome to HR Intelligence", content, preheader="Your account is ready")


def password_changed_html(full_name: str) -> str:
    """Confirmation after password change."""
    name = _escape(full_name) or "there"
    content = f"""
    <h2 style="margin: 0 0 16px 0; font-size: 18px; font-weight: 700; color: #0f172a;">Password updated</h2>
    <p style="margin: 0 0 16px 0;">Hi {name},</p>
    <p style="margin: 0 0 16px 0;">This is a confirmation that the password for your {_escape(BRAND_SHORT)} account was just changed.</p>
    <p style="margin: 0; color: #dc2626; font-size: 14px;">If this wasn't you, please reset your password immediately or contact support.</p>
    """
    return _wrap_content("Password changed", content, preheader="Your password was changed")


def login_alert_html(full_name: str, ip_address: str, user_agent: str, login_time: str) -> str:
    """New login / new device notification."""
    name = _escape(full_name) or "there"
    ip = _escape(ip_address) or "Unavailable"
    ua = _escape(user_agent) or "Unavailable"
    content = f"""
    <h2 style="margin: 0 0 16px 0; font-size: 18px; font-weight: 700; color: #0f172a;">New login to your account</h2>
    <p style="margin: 0 0 16px 0;">Hi {name},</p>
    <p style="margin: 0 0 16px 0;">We noticed a login to your {_escape(BRAND_SHORT)} HR account.</p>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse: collapse; margin: 16px 0;">
      <tr><td style="padding: 8px 0; color: #475569; font-size: 13px;">Time (UTC)</td><td style="padding: 8px 0; color: #0f172a;">{_escape(login_time)}</td></tr>
      <tr><td style="padding: 8px 0; color: #475569; font-size: 13px;">IP Address</td><td style="padding: 8px 0; color: #0f172a;">{ip}</td></tr>
      <tr><td style="padding: 8px 0; color: #475569; font-size: 13px;">Device</td><td style="padding: 8px 0; color: #0f172a; font-size: 13px;">{ua}</td></tr>
    </table>
    <p style="margin: 0; color: #64748b; font-size: 14px;">If this was you, no action is needed. If you did not sign in, please reset your password immediately.</p>
    """
    return _wrap_content("New login to your account", content, preheader="New login detected")


def candidate_notification_html(
    candidate_name: str,
    job_title: str,
    company_name: str,
    subject_title: str,
    body_paragraphs: list,
) -> str:
    """Generic candidate notification (profile viewed, shortlisted, not shortlisted)."""
    name = _escape(candidate_name) or "there"
    job = _escape(job_title) or "the position"
    company = _escape(company_name) or "the company"
    paras = "".join(f'<p style="margin: 0 0 12px 0;">{_escape(p)}</p>' for p in body_paragraphs)
    content = f"""
    <h2 style="margin: 0 0 16px 0; font-size: 18px; font-weight: 700; color: #0f172a;">{_escape(subject_title)}</h2>
    <p style="margin: 0 0 16px 0;">Hi {name},</p>
    <p style="margin: 0 0 16px 0;">Regarding your application for <strong>{job}</strong> at <strong>{company}</strong>:</p>
    {paras}
    <p style="margin: 16px 0 0 0; color: #64748b; font-size: 14px;">— {_escape(BRAND_SHORT)} Team</p>
    """
    return _wrap_content(subject_title, content, preheader=subject_title)
