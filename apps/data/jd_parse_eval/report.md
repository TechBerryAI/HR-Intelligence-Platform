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
- Avg skills precision vs source: 1.0
- Location in-source rate: 1.0
- Experience plausibility rate: 1.0
- Coverage recovered (total field hits): 5
- Coverage missing_with_evidence (total): 10

## Per-file (parsed vs expected-from-filename)

| File | Expected title | Parsed title | Loc | Exp | Skills | TitleΔ | SkillP | Status |
|---|---|---|---|---|---:|---:|---:|---|
| AI Engineer - JD.pdf | AI Engineer | AI Engineer | Remote |  | 8 | 1.0 | 1.0 | ok |
| AI Generalist (Fresher) - JD.pdf | AI Generalist (Fresher) | AI Generalist (Fresher) | Mumbai | 0- | 4 | 1.0 | 1.0 | ok |
| AI_Trainer_JD_Mumbai.pdf | AI_Trainer Mumbai | AI Trainer | Vikhroli | 2-3 | 29 | 1.0 | 1.0 | ok |
| AIX - L2 JD.pdf | AIX - L2 | AIX Admin (L2) | Navi Mumbai (Airol | 3- | 2 | 1.0 | 1.0 | ok |
| AWS JD.pdf | AWS | Cloud Engineer (AWS) | Mumbai | 2- | 13 | 1.0 | 1.0 | ok |
| BDM - Jd.pdf | BDM | Business Development Manager (IT | Vikhroli, Mumbai | 3- | 2 | 1.0 | 1.0 | ok |
| CISO_Job_Description_Banking.pdf | CISO_Job_Description_Banking | Chief Information Security Offic | Andheri, Mumbai | 12-18 | 20 | 1.0 | 1.0 | ok |
| Disaster Recovery Coordinator - JD.pdf | Disaster Recovery Coordinator | Disaster Recovery Coordinator | Mumbai | 2-4 | 4 | 1.0 | 1.0 | ok |
| Dot Net developer JD.pdf | Dot Net developer | .NET developer |  |  | 11 | 1.0 | 1.0 | ok |
| HR Manager JD.pdf | HR Manager | HR Manager/HR assistant manager | Vikhroli, Mumbai(O | 4-6 | 3 | 1.0 | 1.0 | ok |
| IT Network Audit & Compliance Executive -  | IT Network Audit & Compliance Ex | IT Network Audit & Compliance Ex |  |  | 3 | 1.0 | 1.0 | ok |
| JD - Storage Admin - L2 - Mumbai (1).pdf | Storage Admin - L2 - Mumbai | Storage Engineer | Navi Mumbai | 5- | 9 | 1.0 | 1.0 | ok |
| JD - Storage Admin - L2 - Mumbai.pdf | Storage Admin - L2 - Mumbai | Storage Engineer | Navi Mumbai | 5- | 9 | 1.0 | 1.0 | ok |
| JD for L2 - network Engineer_.pdf | for L2 - network Engineer | L2 Network Engineer |  |  | 12 | 1.0 | 1.0 | ok |
| JD java fullstack developer.pdf | java fullstack developer | Java Full Stack Developer | Mumbai | 3-5 | 16 | 1.0 | 1.0 | ok |
| JD MongoDB DBA .pdf | MongoDB DBA | - MongoDB Database Administrator | Navi Mumbai | 1-4 | 17 | 1.0 | 1.0 | ok |
| JD- Linux  Windows Administrator.pdf | Linux Windows Administrator | Linux Windows Administrator |  |  | 6 | 1.0 | 1.0 | ok |
| JD- SME(Multi Cloud) (1).pdf | SME(Multi Cloud) | SME(Subject Matter Expert) – Mul |  |  | 20 | 1.0 | 1.0 | ok |
| JD- SME(Multi Cloud).pdf | SME(Multi Cloud) | SME(Subject Matter Expert) – Mul |  |  | 20 | 1.0 | 1.0 | ok |
| JD_Junior_IT_Solutions_Associate.pdf | Junior_IT_Solutions_Associate | Jr. IT Solutions Associate | Vikhroli, Mumbai | 0-1 | 2 | 1.0 | 1.0 | ok |
| Job Description – IT Sales Executive.pdf | – IT Sales Executive | IT Sales Executive | Vikhroli West, Mum | 2-3 | 3 | 1.0 | 1.0 | ok |
| Linux System Administrator - JD.pdf | Linux System Administrator | Linux System Administrator | Navi Mumbai | 3-6 | 5 | 1.0 | 1.0 | ok |
| Marketing Lead - Data & AI Business Line - | Marketing Lead - Data & AI Busin | Marketing Lead | Bangalore | 15- | 7 | 1.0 | 1.0 | ok |
| Marketing Lead - Data & AI Business Line - | Marketing Lead - Data & AI Busin | Marketing Lead | Bangalore | 15- | 7 | 1.0 | 1.0 | ok |
| Middleware Admin JD.pdf | Middleware Admin | Middleware Admin |  |  | 30 | 1.0 | 1.0 | ok |
| Middleware WebLogic Administrator - JD.pdf | Middleware WebLogic Administrato | Middleware WebLogic Administrato | Mumbai | 1-5 | 5 | 1.0 | 1.0 | ok |
| MSSQL DBA - JD.pdf | MSSQL DBA | MSSQL DBA – L2 |  | 4- | 13 | 1.0 | 1.0 | ok |
| Open_Source_DBA_L2_Job_Description.pdf | Open_Source_DBA_L2_Job_Descripti | Open Source DBA (L2) | Navi Mumbai | 3- | 3 | 1.0 | 1.0 | ok |
| Oracle_BDS_Specialist_JD.pdf | Oracle_BDS_Specialist | Oracle Big Data Service (BDS) Sp |  | 5-7 | 9 | 1.0 | 1.0 | ok |
| SRE JD Updated.pdf | SRE Updated | Site Reliability Engineer | Navi Mumbai - Maha | 5- | 13 | 1.0 | 1.0 | ok |
| Technical_Delivery_Manager_JD.pdf | Technical_Delivery_Manager | Technical Delivery Manager (IT I |  | 5-10 | 7 | 1.0 | 1.0 | ok |
| Video Editor JD.pdf | Video Editor | Video Editor | Vikhroli, Mumbai |  | 3 | 1.0 | 1.0 | ok |
| wireframing JD.pdf | wireframing | Wireframing and Figma Design | Mumbai | 2- | 9 | 1.0 | 1.0 | ok |

## Issues

- **CISO_Job_Description_Banking.pdf**: `coverage_missing_with_evidence` — ['salary']
- **Disaster Recovery Coordinator - JD.pdf**: `coverage_missing_with_evidence` — ['salary']
- **Dot Net developer JD.pdf**: `coverage_missing_with_evidence` — ['salary']
- **JD for L2 - network Engineer_.pdf**: `coverage_missing_with_evidence` — ['salary']
- **Marketing Lead - Data & AI Business Line - JD (1).pdf**: `coverage_missing_with_evidence` — ['salary']
- **Marketing Lead - Data & AI Business Line - JD.pdf**: `coverage_missing_with_evidence` — ['salary']
- **Middleware Admin JD.pdf**: `coverage_missing_with_evidence` — ['salary']
- **Open_Source_DBA_L2_Job_Description.pdf**: `coverage_missing_with_evidence` — ['salary']
- **SRE JD Updated.pdf**: `coverage_missing_with_evidence` — ['salary']
- **wireframing JD.pdf**: `coverage_missing_with_evidence` — ['salary']