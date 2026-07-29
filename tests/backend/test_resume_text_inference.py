"""Unit tests for resume text inference helpers."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "apps" / "backend"

from resume_text_inference import (
    dedupe_skills,
    extract_skills_from_text,
    infer_resume_fields_from_text,
    split_list_items,
)


def test_split_list_items_bullets():
    text = "- Python\n• Java\n1. Go"
    assert split_list_items(text) == ["Python", "Java", "Go"]


def test_split_list_items_pipe_and_comma():
    assert split_list_items("Python|Java|Go") == ["Python", "Java", "Go"]
    assert split_list_items("Python, Java, Go") == ["Python", "Java", "Go"]


def test_dedupe_skills_case_insensitive():
    assert dedupe_skills(["Python", "python", "SQL"]) == ["Python", "SQL"]


def test_extract_skills_from_markdown_section():
    text = """
**Technical Skills:**
- Python
- TensorFlow
- Docker

Experience
"""
    skills = extract_skills_from_text(text)
    assert "Python" in skills
    assert "TensorFlow" in skills
    assert "Docker" in skills


def test_extract_skills_from_inline_header():
    text = "Skills: Python, SQL, React"
    skills = extract_skills_from_text(text)
    assert "Python" in skills
    assert "SQL" in skills
    assert "React" in skills


def test_infer_resume_fields_from_text_partial():
    text = """
Jane Doe
Skills: Python, SQL
Professional Summary: Experienced engineer.
"""
    inferred = infer_resume_fields_from_text(text)
    assert "Python" in inferred["skills"]
    assert inferred["summary"]
