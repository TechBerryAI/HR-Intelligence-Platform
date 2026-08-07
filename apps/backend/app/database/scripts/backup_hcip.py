"""Automatic HCIP backup: Postgres catalog + MEDIA_ROOT bytes.

Usage::

  cd apps/backend
  python -m app.database.scripts.backup_hcip
  python -m app.database.scripts.backup_hcip --force
  python -m app.database.scripts.backup_hcip --db-only
  python -m app.database.scripts.backup_hcip --media-only

Writes under ``{HCIP_DATA_HOME}/backups/<timestamp>/`` (or ``BACKUP_DIR``).
Retention: ``BACKUP_KEEP_DAYS`` (default 14).

The Flask app also runs this in the background when ``BACKUP_ENABLED=true``
(default) if the last backup is older than ``BACKUP_INTERVAL_HOURS`` (default 24).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dotenv import load_dotenv

load_dotenv(_BACKEND / '.env')

from app.core import media_storage
from app.core.data_home import ensure_data_layout, get_backup_dir, get_data_home


def _env_bool(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _pg_env() -> dict[str, str]:
    env = os.environ.copy()
    password = (os.getenv('POSTGRES_PASSWORD') or '').strip()
    if password:
        env['PGPASSWORD'] = password
    return env


def _pg_conn_args() -> list[str]:
    host = (os.getenv('POSTGRES_HOST') or 'localhost').strip()
    port = (os.getenv('POSTGRES_PORT') or '5432').strip()
    user = (os.getenv('POSTGRES_USER') or 'postgres').strip()
    db = (os.getenv('POSTGRES_DB') or 'hrms').strip()
    url = (os.getenv('DATABASE_URL') or '').strip()
    if url and not os.getenv('POSTGRES_HOST'):
        # Prefer discrete POSTGRES_* when set; else pass URL to pg_dump
        return [url]
    return ['-h', host, '-p', port, '-U', user, '-d', db]


def _find_pg_dump() -> str | None:
    override = (os.getenv('PG_DUMP_PATH') or '').strip()
    if override and Path(override).is_file():
        return override

    candidates: list[str] = []
    which = shutil.which('pg_dump')
    if which:
        candidates.append(which)
    # Common locations (conda often newer than apt)
    for extra in (
        Path(sys.executable).resolve().parent / 'pg_dump',
        Path.home() / 'miniconda3' / 'bin' / 'pg_dump',
        Path.home() / 'anaconda3' / 'bin' / 'pg_dump',
        Path('/usr/lib/postgresql/17/bin/pg_dump'),
        Path('/usr/lib/postgresql/16/bin/pg_dump'),
    ):
        if extra.is_file():
            candidates.append(str(extra))

    best: str | None = None
    best_ver = (-1, -1)
    for path in candidates:
        try:
            proc = subprocess.run(
                [path, '--version'],
                capture_output=True,
                check=False,
                text=True,
            )
            # pg_dump (PostgreSQL) 17.9
            text = (proc.stdout or '') + (proc.stderr or '')
            major = minor = 0
            for part in text.replace('(', ' ').replace(')', ' ').split():
                if part[0:1].isdigit() and '.' in part:
                    bits = part.split('.')
                    major = int(bits[0])
                    minor = int(bits[1]) if len(bits) > 1 and bits[1].isdigit() else 0
                    break
            ver = (major, minor)
            if ver > best_ver:
                best_ver = ver
                best = path
        except OSError:
            continue
    return best


def last_backup_time(backup_root: Path | None = None) -> float | None:
    root = backup_root or get_backup_dir()
    stamp = root / 'LAST_BACKUP'
    if stamp.is_file():
        try:
            return float(stamp.read_text(encoding='utf-8').strip())
        except ValueError:
            pass
    latest = root / 'latest'
    if latest.is_dir() or latest.is_symlink():
        try:
            return latest.resolve().stat().st_mtime
        except OSError:
            pass
    return None


def needs_backup(*, interval_hours: int | None = None) -> bool:
    hours = interval_hours if interval_hours is not None else _env_int('BACKUP_INTERVAL_HOURS', 24)
    last = last_backup_time()
    if last is None:
        return True
    return (time.time() - last) >= max(1, hours) * 3600


def _write_manifest(dest: Path, payload: dict) -> None:
    (dest / 'MANIFEST.json').write_text(
        json.dumps(payload, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )


def _run_pg_dump(args: list[str], out: Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            args,
            env=_pg_env(),
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        return False, str(exc)
    if proc.returncode != 0:
        err = (proc.stderr or b'').decode('utf-8', errors='replace')
        out.unlink(missing_ok=True)
        return False, err
    if not out.is_file() or out.stat().st_size <= 0:
        out.unlink(missing_ok=True)
        return False, 'empty dump file'
    return True, ''


def _pg_dump_docker(out: Path) -> tuple[bool, str]:
    """Fallback when local pg_dump is older than the server (e.g. 16 vs 17)."""
    if not shutil.which('docker'):
        return False, 'docker not available'
    host = (os.getenv('POSTGRES_HOST') or 'localhost').strip()
    port = (os.getenv('POSTGRES_PORT') or '5432').strip()
    user = (os.getenv('POSTGRES_USER') or 'postgres').strip()
    db = (os.getenv('POSTGRES_DB') or 'hrms').strip()
    password = (os.getenv('POSTGRES_PASSWORD') or '').strip()
    image = (os.getenv('BACKUP_PG_DOCKER_IMAGE') or 'postgres:17').strip()
    # Mount parent so dump lands on host
    dest_dir = out.parent.resolve()
    args = [
        'docker',
        'run',
        '--rm',
        '-e',
        f'PGPASSWORD={password}',
        '-v',
        f'{dest_dir}:/backup',
        image,
        'pg_dump',
        '--format=custom',
        '--no-owner',
        '--no-acl',
        '-h',
        host,
        '-p',
        port,
        '-U',
        user,
        '-d',
        db,
        '-f',
        f'/backup/{out.name}',
    ]
    print(f'[backup] retrying pg_dump via {image}')
    try:
        proc = subprocess.run(args, capture_output=True, check=False)
    except OSError as exc:
        return False, str(exc)
    if proc.returncode != 0:
        err = (proc.stderr or b'').decode('utf-8', errors='replace')
        out.unlink(missing_ok=True)
        return False, err
    if not out.is_file() or out.stat().st_size <= 0:
        return False, 'empty dump from docker pg_dump'
    return True, ''


def backup_postgres(dest_dir: Path) -> Path | None:
    pg_dump = _find_pg_dump()
    out = dest_dir / 'postgres.dump'
    url = (os.getenv('DATABASE_URL') or '').strip()
    use_url = bool(url) and not (os.getenv('POSTGRES_HOST') or '').strip()

    ok = False
    err = ''
    if pg_dump:
        if use_url:
            args = [
                pg_dump,
                '--format=custom',
                '--no-owner',
                '--no-acl',
                '-f',
                str(out),
                url,
            ]
        else:
            args = [
                pg_dump,
                '--format=custom',
                '--no-owner',
                '--no-acl',
                '-f',
                str(out),
                *_pg_conn_args(),
            ]
        print(f'[backup] pg_dump → {out.name}')
        ok, err = _run_pg_dump(args, out)
    else:
        err = 'pg_dump not found on PATH'

    if not ok and 'version mismatch' in err.lower():
        ok, err = _pg_dump_docker(out)

    if not ok and not pg_dump:
        ok, err = _pg_dump_docker(out)

    if not ok:
        print(f'[backup] WARN: Postgres dump failed: {err[:500]}')
        print(
            '[backup] Fix: install a matching client (postgresql-client-17) '
            'or set BACKUP_PG_DOCKER_IMAGE=postgres:17 with Docker available'
        )
        return None
    print(f'[backup] Postgres dump OK ({out.stat().st_size} bytes)')
    return out


def backup_media(dest_dir: Path) -> Path | None:
    media_root = media_storage.get_media_root()
    if not media_root.is_dir():
        print(f'[backup] WARN: MEDIA_ROOT missing: {media_root}')
        return None
    out = dest_dir / 'media.tar.gz'
    print(f'[backup] tar MEDIA_ROOT={media_root} → {out.name}')
    with tarfile.open(out, 'w:gz') as tar:
        tar.add(str(media_root), arcname='media')
    print(f'[backup] Media archive OK ({out.stat().st_size} bytes)')
    return out


def prune_old_backups(backup_root: Path, *, keep_days: int) -> int:
    if keep_days <= 0:
        return 0
    cutoff = time.time() - keep_days * 86400
    removed = 0
    for child in sorted(backup_root.iterdir()):
        if not child.is_dir() or child.name in ('latest',):
            continue
        if child.name.startswith('.'):
            continue
        try:
            mtime = child.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
            print(f'[backup] pruned {child.name}')
    return removed


def run_backup(
    *,
    force: bool = False,
    db_only: bool = False,
    media_only: bool = False,
) -> Path | None:
    if not _env_bool('BACKUP_ENABLED', True) and not force:
        print('[backup] skipped (BACKUP_ENABLED=false)')
        return None
    if not force and not needs_backup():
        print('[backup] skipped (still within BACKUP_INTERVAL_HOURS)')
        return None

    layout = ensure_data_layout()
    backup_root = layout['backups']
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    dest = backup_root / stamp
    dest.mkdir(parents=True, exist_ok=True)
    lock = backup_root / '.backup.lock'
    if lock.is_file():
        try:
            age = time.time() - lock.stat().st_mtime
            if age < 3600:
                print('[backup] another backup appears in progress — abort')
                return None
        except OSError:
            pass
    lock.write_text(str(os.getpid()), encoding='utf-8')

    started = time.time()
    try:
        db_path = None if media_only else backup_postgres(dest)
        media_path = None if db_only else backup_media(dest)
        if db_path is None and media_path is None:
            shutil.rmtree(dest, ignore_errors=True)
            print('[backup] nothing written — abort')
            return None
        manifest = {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'data_home': str(get_data_home()),
            'media_root': str(media_storage.get_media_root()),
            'postgres_dump': db_path.name if db_path else None,
            'media_archive': media_path.name if media_path else None,
            'postgres_host': os.getenv('POSTGRES_HOST'),
            'postgres_db': os.getenv('POSTGRES_DB'),
            'duration_seconds': round(time.time() - started, 2),
        }
        _write_manifest(dest, manifest)
        latest = backup_root / 'latest'
        if latest.is_symlink() or latest.is_file():
            latest.unlink(missing_ok=True)
        elif latest.is_dir():
            shutil.rmtree(latest, ignore_errors=True)
        try:
            latest.symlink_to(dest.name, target_is_directory=True)
        except OSError:
            # Windows without symlink privilege — write a pointer file
            latest.write_text(dest.name + '\n', encoding='utf-8')
        (backup_root / 'LAST_BACKUP').write_text(str(time.time()), encoding='utf-8')
        keep = _env_int('BACKUP_KEEP_DAYS', 14)
        prune_old_backups(backup_root, keep_days=keep)
        print(f'[backup] done → {dest}')
        return dest
    finally:
        lock.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force', action='store_true', help='Ignore interval / BACKUP_ENABLED')
    parser.add_argument('--db-only', action='store_true')
    parser.add_argument('--media-only', action='store_true')
    args = parser.parse_args()
    dest = run_backup(force=args.force, db_only=args.db_only, media_only=args.media_only)
    raise SystemExit(0 if dest else 1)


if __name__ == '__main__':
    main()
