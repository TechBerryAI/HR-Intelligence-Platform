# JD Parse Evaluation Report

- Mode: `canonical_deterministic_plus_repair_no_llm_no_ocr`
- Files: 33
- Parsed OK: 33
- Failed/thin: 0
- Empty title: 0
- Empty skills: 0
- Thin description: 0
- Avg title overlap vs source: 1.0
- Avg title overlap vs filename: 0.691
- Avg skills precision vs source: 0.983
- Location in-source rate: 1.0
- Experience plausibility rate: 1.0
- Coverage recovered (total field hits): 0
- Coverage missing_with_evidence (total): 3

## Per-file (parsed vs expected-from-filename)

| File | Expected title | Parsed title | Loc | Exp | Skills | TitleΔ | SkillP | Status |
|---|---|---|---|---|---:|---:|---:|---|
| AI Engineer - JD.pdf | AI Engineer | AI Engineer | Remote support |  | 8 | 1.0 | 1.0 | ok |
| AI Generalist (Fresher) - JD.pdf | AI Generalist (Fresher) | AI Generalist (Fresher) | Mumbai | 0- | 4 | 1.0 | 1.0 | ok |
| AI_Trainer_JD_Mumbai.pdf | AI_Trainer Mumbai | AI Trainer | Mumbai (Vikhroli W | 2-3 | 32 | 1.0 | 0.96 | ok |
| AIX - L2 JD.pdf | AIX - L2 | AIX Admin (L2) | Navi Mumbai (Airol | 3- | 2 | 1.0 | 1.0 | ok |
| AWS JD.pdf | AWS | Cloud Engineer (AWS) |  | 2- | 9 | 1.0 | 1.0 | ok |
| BDM - Jd.pdf | BDM | Business Development Manager (IT | Vikhroli, Mumbai | 3- | 2 | 1.0 | 1.0 | ok |
| CISO_Job_Description_Banking.pdf | CISO_Job_Description_Banking | Chief Information Security Offic | Andheri, Mumbai | 12-18 | 20 | 1.0 | 1.0 | ok |
| Disaster Recovery Coordinator - JD.pdf | Disaster Recovery Coordinator | Disaster Recovery Coordinator | Mumbai | 2-4 | 4 | 1.0 | 1.0 | ok |
| Dot Net developer JD.pdf | Dot Net developer | .NET developer |  |  | 11 | 1.0 | 1.0 | ok |
| HR Manager JD.pdf | HR Manager | HR Manager/HR assistant manager | Vikhroli, Mumbai(O | 4-6 | 3 | 1.0 | 0.667 | ok |
| IT Network Audit & Compliance Executive -  | IT Network Audit & Compliance Ex | IT Network Audit & Compliance Ex |  |  | 3 | 1.0 | 1.0 | ok |
| JD - Storage Admin - L2 - Mumbai (1).pdf | Storage Admin - L2 - Mumbai | Storage Engineer | Navi Mumbai | 5- | 9 | 1.0 | 1.0 | ok |
| JD - Storage Admin - L2 - Mumbai.pdf | Storage Admin - L2 - Mumbai | Storage Engineer | Navi Mumbai | 5- | 9 | 1.0 | 1.0 | ok |
| JD for L2 - network Engineer_.pdf | for L2 - network Engineer | L2 Network Engineer |  |  | 3 | 1.0 | 1.0 | ok |
| JD java fullstack developer.pdf | java fullstack developer | Java Full Stack Developer | Mumbai | 3-5 | 20 | 1.0 | 1.0 | ok |
| JD MongoDB DBA .pdf | MongoDB DBA | MongoDB Database Administrator | Mumbai, Navi Mumba | 1-4 | 20 | 1.0 | 0.95 | ok |
| JD- Linux  Windows Administrator.pdf | Linux Windows Administrator | Linux Windows Administrator |  |  | 7 | 1.0 | 1.0 | ok |
| JD- SME(Multi Cloud) (1).pdf | SME(Multi Cloud) | SME(Subject Matter Expert) – Mul |  |  | 20 | 1.0 | 1.0 | ok |
| JD- SME(Multi Cloud).pdf | SME(Multi Cloud) | SME(Subject Matter Expert) – Mul |  |  | 20 | 1.0 | 1.0 | ok |
| JD_Junior_IT_Solutions_Associate.pdf | Junior_IT_Solutions_Associate | Jr. IT Solutions Associate | Vikhroli, Mumbai | 0-1 | 3 | 1.0 | 1.0 | ok |
| Job Description – IT Sales Executive.pdf | – IT Sales Executive | IT Sales Executive | Vikhroli West, Mum | 2-3 | 3 | 1.0 | 1.0 | ok |
| Linux System Administrator - JD.pdf | Linux System Administrator | Linux System Administrator | Navi Mumbai | 3-6 | 6 | 1.0 | 1.0 | ok |
| Marketing Lead - Data & AI Business Line - | Marketing Lead - Data & AI Busin | Marketing Lead | India (Mumbai, Pun | 15- | 8 | 1.0 | 1.0 | ok |
| Marketing Lead - Data & AI Business Line - | Marketing Lead - Data & AI Busin | Marketing Lead | India (Mumbai, Pun | 15- | 8 | 1.0 | 1.0 | ok |
| Middleware Admin JD.pdf | Middleware Admin | Middleware Admin |  |  | 40 | 1.0 | 1.0 | ok |
| Middleware WebLogic Administrator - JD.pdf | Middleware WebLogic Administrato | Middleware WebLogic Administrato |  | 1-5 | 3 | 1.0 | 1.0 | ok |
| MSSQL DBA - JD.pdf | MSSQL DBA | MSSQL DBA – L2 |  | 4- | 13 | 1.0 | 0.923 | ok |
| Open_Source_DBA_L2_Job_Description.pdf | Open_Source_DBA_L2_Job_Descripti | Open Source DBA (L2) | Mumbai / Navi Mumb | 3- | 11 | 1.0 | 1.0 | ok |
| Oracle_BDS_Specialist_JD.pdf | Oracle_BDS_Specialist | Oracle Big Data Service (BDS) Sp |  | 5-7 | 23 | 1.0 | 1.0 | ok |
| SRE JD Updated.pdf | SRE Updated | Site Reliability Engineer | Navi Mumbai - Maha | 5- | 13 | 1.0 | 1.0 | ok |
| Technical_Delivery_Manager_JD.pdf | Technical_Delivery_Manager | Technical Delivery Manager (IT I |  | 5-10 | 20 | 1.0 | 0.95 | ok |
| Video Editor JD.pdf | Video Editor | Video Editor | Vikhroli, Mumbai |  | 1 | 1.0 | 1.0 | ok |
| wireframing JD.pdf | wireframing | Wireframing and Figma Design |  | 2- | 3 | 1.0 | 1.0 | ok |

## Issues

- **AWS JD.pdf**: `coverage_missing_with_evidence` — ['location']
- **Middleware WebLogic Administrator - JD.pdf**: `coverage_missing_with_evidence` — ['location']
- **wireframing JD.pdf**: `coverage_missing_with_evidence` — ['location']