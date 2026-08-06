# User Manual

Single enterprise deliverable for HR Intelligence Platform (implemented features only).

| Format | File |
|--------|------|
| **Word** | [HR_Intelligence_Platform_User_Manual.docx](HR_Intelligence_Platform_User_Manual.docx) |
| **PDF** | [HR_Intelligence_Platform_User_Manual.pdf](HR_Intelligence_Platform_User_Manual.pdf) |

Word and PDF are **always generated together** from the same DOCX (PDF is exported by Microsoft Word), so they stay in sync.

Screenshots (by module): [screenshots/](screenshots/)

## Regenerate

App must be running (`node start.js`). Requires Microsoft Word + `pywin32` for PDF export.

```bash
python docs/user-manual/capture.py
python docs/user-manual/build.py
```

`build.py` writes the Word manual, then exports the matching PDF in one step.

Seed accounts used by capture (override with env vars if needed):

| Role | Email |
|------|--------|
| HEAD_HR | `chetan.gore@techberryinfotech.com` |
| CEO | `unmesh.tari@techberryinfotech.com` |
| RECRUITER | `riya.gupta@techberryinfotech.com` |
