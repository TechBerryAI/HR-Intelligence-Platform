"""Restore candidates.cid to 3-digit padding and rewrite over-padded IDs.

Live DB default was incorrectly lpad(..., 8) producing CID00000014.
Baseline and product UI expect CID014 (lpad 3), matching CID001–CID010.

Revision ID: 20260814_cid_pad3
Revises: 20260812_ext_outbox
Create Date: 2026-08-14
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = '20260814_cid_pad3'
down_revision: Union[str, Sequence[str], None] = '20260812_ext_outbox'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# FKs to candidates.cid — none use ON UPDATE CASCADE, so drop/recreate around rewrite.
_FK_SPECS = (
    # (table, column, constraint, ondelete)
    ('applications', 'candidate_id', 'applications_candidate_id_fkey', None),
    ('applications', 'created_by', 'applications_created_by_fkey', None),
    ('candidate_certifications', 'candidate_id', 'candidate_certifications_candidate_id_fkey', 'CASCADE'),
    ('candidate_education', 'candidate_id', 'candidate_education_candidate_id_fkey', 'CASCADE'),
    ('candidate_experiences', 'candidate_id', 'candidate_experiences_candidate_id_fkey', 'CASCADE'),
    ('candidate_profiles', 'candidate_id', 'candidate_profiles_candidate_id_fkey', None),
    ('candidate_profiles', 'created_by', 'candidate_profiles_created_by_fkey', None),
    ('matches', 'candidate_id', 'matches_candidate_id_fkey', None),
    ('parsed_resumes', 'candidate_id', 'parsed_resumes_candidate_id_fkey', 'SET NULL'),
)

_CHILD_UPDATES = (
    ('applications', 'candidate_id'),
    ('applications', 'created_by'),
    ('candidate_certifications', 'candidate_id'),
    ('candidate_education', 'candidate_id'),
    ('candidate_experiences', 'candidate_id'),
    ('candidate_profiles', 'candidate_id'),
    ('candidate_profiles', 'created_by'),
    ('matches', 'candidate_id'),
    ('parsed_resumes', 'candidate_id'),
)


def _drop_fks(bind) -> None:
    for table, _col, name, _ondelete in _FK_SPECS:
        bind.execute(text(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}'))


def _add_fks(bind) -> None:
    for table, col, name, ondelete in _FK_SPECS:
        od = f' ON DELETE {ondelete}' if ondelete else ''
        bind.execute(
            text(
                f'ALTER TABLE {table} ADD CONSTRAINT {name} '
                f'FOREIGN KEY ({col}) REFERENCES candidates(cid){od}'
            )
        )


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Restore product default: CID + 3-digit zero pad
    bind.execute(
        text(
            """
            ALTER TABLE candidates
            ALTER COLUMN cid SET DEFAULT (
                'CID'::text || lpad(nextval('candidate_cid_seq'::regclass)::text, 3, '0'::text)
            )
            """
        )
    )

    # 2) Rewrite over-padded CIDs (CID00000012 → CID012) across parent + children
    rows = bind.execute(
        text(
            """
            SELECT cid
            FROM candidates
            WHERE cid ~ '^CID[0-9]+$'
              AND length(substring(cid from 4)) > 3
            ORDER BY cid
            """
        )
    ).fetchall()

    if not rows:
        return

    renames: list[tuple[str, str]] = []
    for (old,) in rows:
        num = int(old[3:])
        new = f'CID{num:03d}'
        if old == new:
            continue
        exists = bind.execute(
            text('SELECT 1 FROM candidates WHERE cid = :c'),
            {'c': new},
        ).fetchone()
        if exists:
            raise RuntimeError(
                f'Cannot rewrite {old} → {new}: target CID already exists'
            )
        renames.append((old, new))

    if not renames:
        return

    _drop_fks(bind)
    try:
        for old, new in renames:
            for table, col in _CHILD_UPDATES:
                bind.execute(
                    text(f'UPDATE {table} SET {col} = :new WHERE {col} = :old'),
                    {'new': new, 'old': old},
                )
            bind.execute(
                text('UPDATE candidates SET cid = :new WHERE cid = :old'),
                {'new': new, 'old': old},
            )
    finally:
        _add_fks(bind)


def downgrade() -> None:
    # Do not restore 8-digit padding; that was the bug.
    # Leave rewritten CIDs as-is (irreversible data fix).
    bind = op.get_bind()
    bind.execute(
        text(
            """
            ALTER TABLE candidates
            ALTER COLUMN cid SET DEFAULT (
                'CID'::text || lpad(nextval('candidate_cid_seq'::regclass)::text, 3, '0'::text)
            )
            """
        )
    )
