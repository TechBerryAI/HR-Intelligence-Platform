#!/usr/bin/env python3
"""
Generate gold lake samples for Resume & JD Intelligence Engine benchmarking.

Produces ≥50 resumes + ≥50 JDs under:
  ai/dataset/lake/benchmark/parsing/v1/{resumes,jds}/

Each case: source.txt + expected_toon.json + expected_form.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dataset' / 'lake' / 'benchmark' / 'parsing' / 'v1'

SKILLS_POOL = [
    'Python', 'Java', 'JavaScript', 'TypeScript', 'React', 'Node.js',
    'SQL', 'PostgreSQL', 'MongoDB', 'Docker', 'Kubernetes', 'AWS',
    'Django', 'Flask', 'FastAPI', 'Go', 'Rust', 'C++', 'TensorFlow',
    'PyTorch', 'Spark', 'Kafka', 'Redis', 'GraphQL', 'Next.js',
]

TITLES = [
    'Software Engineer', 'Backend Developer', 'Frontend Developer',
    'Full Stack Developer', 'DevOps Engineer', 'Data Engineer',
    'Machine Learning Engineer', 'SRE', 'Platform Engineer',
    'Mobile Developer',
]

CITIES = [
    'Bengaluru', 'Hyderabad', 'Pune', 'Mumbai', 'Remote',
    'Austin, TX', 'San Francisco, CA', 'Seattle, WA', 'London', 'Berlin',
]

COMPANIES = [
    'Acme Corp', 'TechNova', 'DataPulse', 'CloudNine', 'BrightApps',
    'QuantumSoft', 'Nexlify', 'Orbit Labs', 'PixelForge', 'StackWright',
]


FIRST = [
    'Jane', 'John', 'Priya', 'Amit', 'Sarah', 'Michael', 'Ananya', 'Rahul',
    'Emily', 'David', 'Neha', 'Arjun', 'Olivia', 'James', 'Kavya', 'Rohan',
    'Sophia', 'Daniel', 'Meera', 'Vikram', 'Emma', 'Chris', 'Isha', 'Nikhil',
    'Ava', 'Ryan',
]
LAST = [
    'Doe', 'Smith', 'Patel', 'Sharma', 'Johnson', 'Williams', 'Reddy', 'Kumar',
    'Brown', 'Davis', 'Gupta', 'Mehta', 'Miller', 'Wilson', 'Iyer', 'Nair',
    'Taylor', 'Anderson', 'Joshi', 'Singh', 'Thomas', 'Moore', 'Desai', 'Rao',
    'Jackson', 'White',
]


def _resume_case(i: int) -> tuple[str, dict, dict]:
    first = FIRST[(i - 1) % len(FIRST)]
    last = LAST[(i - 1) % len(LAST)]
    name = f'{first} {last}'
    email = f'{first.lower()}.{last.lower()}{i:02d}@example.com'
    phone = f'+1 (555) {100 + i:03d}-{1000 + i:04d}'
    title = TITLES[i % len(TITLES)]
    company = COMPANIES[i % len(COMPANIES)]
    city = CITIES[i % len(CITIES)]
    skills = SKILLS_POOL[i % 8 : (i % 8) + 5]
    if len(skills) < 4:
        skills = SKILLS_POOL[:5]
    year = 2018 + (i % 5)

    text = f"""{name}
{email}
{phone}
{city}
LinkedIn: https://linkedin.com/in/{first.lower()}{last.lower()}{i:02d}
GitHub: https://github.com/{first.lower()}{last.lower()}{i:02d}

Professional Summary:
Experienced {title.lower()} with {3 + (i % 7)} years building production systems.

Skills:
{', '.join(skills)}

Experience:
{title} | {company} | Jan {year} - Present
Built APIs and services. Improved latency by {10 + i}%.

Education:
B.Tech Computer Science, State University, {year - 4}
"""

    toon = {
        'type': 'resume',
        'person': {
            'name': name,
            'email': email,
            'phone': phone,
            'location': city,
            'linkedin': f'https://linkedin.com/in/{first.lower()}{last.lower()}{i:02d}',
            'github': f'https://github.com/{first.lower()}{last.lower()}{i:02d}',
            'portfolio': '',
        },
        'skills': skills,
        'experience': [
            {
                'title': title,
                'company': company,
                'from': f'{year}-01',
                'to': 'Present',
                'description': f'Built APIs and services. Improved latency by {10 + i}%.',
            }
        ],
        'education': [
            {
                'degree': 'B.Tech Computer Science',
                'institution': 'State University',
                'field': 'Computer Science',
                'year': str(year - 4),
            }
        ],
        'summary': f'Experienced {title.lower()} with {3 + (i % 7)} years building production systems.',
        'certifications': [],
        'languages': [],
        'projects': [],
        'total_experience_years': float(3 + (i % 7)),
    }

    form = {
        'fullName': name,
        'email': email,
        'phone': phone,
        'currentLocation': city,
        'linkedinUrl': f'https://linkedin.com/in/{first.lower()}{last.lower()}{i:02d}',
        'githubUrl': f'https://github.com/{first.lower()}{last.lower()}{i:02d}',
        'skills': ', '.join(skills),
        'experienceLevel': 'experienced',
    }
    return text, toon, form


def _jd_case(i: int) -> tuple[str, dict, dict]:
    title = TITLES[i % len(TITLES)]
    company = COMPANIES[i % len(COMPANIES)]
    city = CITIES[i % len(CITIES)]
    mandatory = SKILLS_POOL[i % 6 : (i % 6) + 4]
    preferred = SKILLS_POOL[(i + 4) % 10 : (i + 4) % 10 + 2]
    if len(mandatory) < 3:
        mandatory = SKILLS_POOL[:4]
    if len(preferred) < 1:
        preferred = ['AWS']
    min_y = 2 + (i % 4)
    max_y = min_y + 2

    text = f"""Job Title: {title}
Company: {company}
Location: {city}
Employment Type: Full-time
Experience: {min_y}-{max_y} years
Salary: {10 + i}-{15 + i} LPA

**Responsibilities:**
• Design and build scalable services
• Collaborate with product and design
• Mentor junior engineers

**Required Skills:**
{', '.join(mandatory)}

**Preferred Skills:**
{', '.join(preferred)}

**Qualifications:**
• Bachelor's degree in Computer Science or related field
"""

    toon = {
        'type': 'job_description',
        'title': title,
        'company': company,
        'location': city,
        'employment_type': 'Full-time',
        'mandatory_skills': mandatory,
        'preferred_skills': preferred,
        'skills': list(dict.fromkeys(mandatory + preferred)),
        'responsibilities': [
            'Design and build scalable services',
            'Collaborate with product and design',
            'Mentor junior engineers',
        ],
        'qualifications': [
            "Bachelor's degree in Computer Science or related field",
        ],
        'benefits': [],
        'keywords': [],
        'description': '',
        'min_experience_years': min_y,
        'max_experience_years': max_y,
        'salary_range': f'{10 + i}-{15 + i} LPA',
    }

    form = {
        'title': title,
        'location': city,
        'company': company,
        'experienceFrom': str(min_y),
        'experienceTo': str(max_y),
        'salary': f'{10 + i}-{15 + i} LPA',
        'mandatorySkills': mandatory,
        'preferredSkills': preferred,
    }
    return text, toon, form


def main() -> None:
    resumes = OUT / 'resumes'
    jds = OUT / 'jds'
    resumes.mkdir(parents=True, exist_ok=True)
    jds.mkdir(parents=True, exist_ok=True)

    for i in range(1, 51):
        text, toon, form = _resume_case(i)
        case_dir = resumes / f'resume_{i:03d}'
        case_dir.mkdir(exist_ok=True)
        (case_dir / 'source.txt').write_text(text, encoding='utf-8')
        (case_dir / 'expected_toon.json').write_text(
            json.dumps(toon, indent=2), encoding='utf-8'
        )
        (case_dir / 'expected_form.json').write_text(
            json.dumps(form, indent=2), encoding='utf-8'
        )

    for i in range(1, 51):
        text, toon, form = _jd_case(i)
        case_dir = jds / f'jd_{i:03d}'
        case_dir.mkdir(exist_ok=True)
        (case_dir / 'source.txt').write_text(text, encoding='utf-8')
        (case_dir / 'expected_toon.json').write_text(
            json.dumps(toon, indent=2), encoding='utf-8'
        )
        (case_dir / 'expected_form.json').write_text(
            json.dumps(form, indent=2), encoding='utf-8'
        )

    manifest = {
        'version': 'parsing/v1',
        'resumes': 50,
        'jds': 50,
        'accuracy_target': 0.99,
        'notes': 'Synthetic gold set for Intelligence Engine regression; extend with real docs over time.',
    }
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Wrote 50 resumes + 50 JDs to {OUT}')


if __name__ == '__main__':
    main()
