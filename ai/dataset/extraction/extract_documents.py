#!/usr/bin/env python3
"""Convenience entry point — delegates to cli/extract_documents.py."""

from dataset.extraction.cli.extract_documents import app

if __name__ == "__main__":
    app()
