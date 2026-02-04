"""
Test SMTP connectivity and auth using backend .env. Run from repo root or backend:
  python backend/scripts/test_smtp.py
  cd backend && python scripts/test_smtp.py
"""
import os
import sys

# Ensure backend is on path and load .env
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from dotenv import load_dotenv
load_dotenv()

def main():
    host = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    port = int(os.getenv("MAIL_PORT", "587"))
    use_tls = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    use_ssl = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
    user = os.getenv("MAIL_USERNAME", "")
    password = os.getenv("MAIL_PASSWORD", "")

    print("SMTP config (password masked):")
    print(f"  MAIL_SERVER={host}")
    print(f"  MAIL_PORT={port}")
    print(f"  MAIL_USE_TLS={use_tls}, MAIL_USE_SSL={use_ssl}")
    print(f"  MAIL_USERNAME={user}")
    print(f"  MAIL_PASSWORD={'*' * min(16, len(password))} (len={len(password)})")
    if not user or not password:
        print("\nERROR: MAIL_USERNAME and MAIL_PASSWORD must be set in .env")
        return 1
    if "@" not in user:
        print("\nWARNING: MAIL_USERNAME should be the full email (e.g. you@gmail.com), not a label.")

    import smtplib
    try:
        if use_ssl:
            smtp = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            smtp = smtplib.SMTP(host, port, timeout=15)
            if use_tls:
                smtp.starttls()
        smtp.login(user, password)
        smtp.quit()
        print("\nOK: Connected and authenticated successfully.")
        return 0
    except smtplib.SMTPAuthenticationError as e:
        print(f"\nAUTH FAILED: {e}")
        print("  - For Gmail: use full email as MAIL_USERNAME and an App Password (16 chars, no spaces).")
        return 1
    except Exception as e:
        print(f"\nCONNECTION/SEND FAILED: {type(e).__name__}: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
