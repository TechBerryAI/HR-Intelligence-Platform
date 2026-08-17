"""
Environment Variable Validator

Validates that all required environment variables are set before the application starts.
PostgreSQL: DATABASE_URL or POSTGRES_USER + POSTGRES_PASSWORD.
"""

from __future__ import annotations

import os
import sys
from typing import List, Tuple

_EXAMPLE_JWT = 'replace-with-a-unique-secret-at-least-32-chars'

_PLACEHOLDER_JWT = {
    '',
    'your-jwt-secret-change-in-production',
    'changeme',
    'secret',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZXhhbXBsZSJ9.lGrIa8yMwsB_ZSrgoniyr5FF34e9tE7TJboLqTfvifE',
    'dev-only-insecure-jwt-secret-do-not-use-in-prod',
    _EXAMPLE_JWT,
}

_PLACEHOLDER_INTEGRATION_KEYS = {
    '',
    'dev-integration-secrets',
}

_PLACEHOLDER_DB_PASSWORDS = {
    'your_postgres_password',
    'changeme',
    'password',
}


def _truthy(name: str, default: str = 'false') -> bool:
    return (os.getenv(name, default) or '').strip().lower() in ('1', 'true', 'yes', 'on')


def under_gunicorn() -> bool:
    if 'gunicorn' in sys.modules:
        return True
    return 'gunicorn' in (os.getenv('SERVER_SOFTWARE') or '').lower()


def is_production_like() -> bool:
    return not _truthy('FLASK_DEBUG') and not _truthy('ALLOW_INSECURE_JWT')


class EnvValidator:
    # Required for database (PostgreSQL)
    DB_REQUIRED = "Set DATABASE_URL or POSTGRES_USER and POSTGRES_PASSWORD"

    # Optional but recommended for local OTP / notifications
    RECOMMENDED_VARS = {
        'MAIL_USERNAME': 'Gmail address for OTP sending',
        'MAIL_PASSWORD': 'Gmail App Password (not regular password)',
    }

    DEFAULTED_VARS = {
        'PORT': '3000',
        'FLASK_DEBUG': 'false',
        'POSTGRES_HOST': 'localhost',
        'POSTGRES_PORT': '5432',
        'POSTGRES_DB': 'JobPortal',
        'DB_POOL_SIZE': '5',
        'DB_CONNECTION_TIMEOUT': '10',
    }

    @classmethod
    def _is_production_like(cls) -> bool:
        return is_production_like()

    @classmethod
    def _parse_int_env(cls, name: str) -> Tuple[int | None, str | None]:
        raw = (os.getenv(name) or '').strip()
        if not raw:
            return None, None
        try:
            return int(raw), None
        except ValueError:
            return None, f"  ❌ {name}: must be an integer (got {raw!r})"

    @classmethod
    def _worker_count(cls) -> Tuple[int | None, str | None]:
        n, err = cls._parse_int_env('GUNICORN_WORKERS')
        if err:
            return None, err
        if n is not None:
            if n < 1:
                return None, "  ❌ GUNICORN_WORKERS: must be >= 1"
            return n, None
        if under_gunicorn():
            return 4, None
        return 1, None

    @classmethod
    def _ping_redis(cls, url: str) -> str | None:
        try:
            import redis

            client = redis.Redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
            return None
        except Exception as exc:
            return f"  ❌ REDIS_URL: Redis is not reachable ({exc})"

    @classmethod
    def validate(cls, strict: bool = False) -> Tuple[bool, List[str], List[str]]:
        errors = []
        warnings = []

        db_url = (os.getenv('DATABASE_URL') or '').strip()
        pg_user = (os.getenv('POSTGRES_USER') or '').strip()
        pg_password = (os.getenv('POSTGRES_PASSWORD') or '').strip()
        if not db_url and not (pg_user and pg_password):
            errors.append(f"  ❌ {cls.DB_REQUIRED}")

        port_val, port_err = cls._parse_int_env('POSTGRES_PORT')
        if port_err:
            errors.append(port_err)
        elif port_val is not None and not (1 <= port_val <= 65535):
            errors.append("  ❌ POSTGRES_PORT: must be between 1 and 65535")

        workers, workers_err = cls._worker_count()
        if workers_err:
            errors.append(workers_err)

        gunicorn = under_gunicorn()
        flask_debug = _truthy('FLASK_DEBUG')
        developer_mode = _truthy('DEVELOPER_MODE')

        if gunicorn and flask_debug:
            errors.append(
                "  ❌ FLASK_DEBUG: must be false when running under Gunicorn"
            )
        if gunicorn and developer_mode:
            errors.append(
                "  ❌ DEVELOPER_MODE: must be false when running under Gunicorn"
            )

        jwt_secret = (os.getenv('JWT_SECRET') or '').strip()
        if cls._is_production_like():
            if developer_mode:
                errors.append(
                    "  ❌ DEVELOPER_MODE: must be false in production (FLASK_DEBUG=false)"
                )
            if not jwt_secret or jwt_secret in _PLACEHOLDER_JWT or len(jwt_secret) < 32:
                errors.append(
                    "  ❌ JWT_SECRET: required unique secret (≥32 chars); placeholders are blocked in production"
                )
            if pg_password and pg_password.lower() in _PLACEHOLDER_DB_PASSWORDS:
                errors.append(
                    "  ❌ POSTGRES_PASSWORD: placeholder/weak default is not allowed in production"
                )
            if not (os.getenv('N8N_CALLBACK_SECRET') or '').strip():
                if (os.getenv('N8N_WEBHOOK_URL') or '').strip():
                    errors.append(
                        "  ❌ N8N_CALLBACK_SECRET: required when N8N_WEBHOOK_URL is set"
                    )
                else:
                    warnings.append(
                        "  ⚠️  N8N_CALLBACK_SECRET: set before enabling ATS callbacks"
                    )
            integ = (os.getenv('INTEGRATION_SECRETS_KEY') or '').strip()
            if not integ or integ in _PLACEHOLDER_INTEGRATION_KEYS:
                errors.append(
                    "  ❌ INTEGRATION_SECRETS_KEY: required dedicated key for provider credentials in production"
                )

            redis_url = (os.getenv('REDIS_URL') or '').strip()
            if workers and workers > 1 and not redis_url:
                errors.append(
                    "  ❌ REDIS_URL: required when GUNICORN_WORKERS>1 "
                    "(cross-worker parse join; Gunicorn default is 4). "
                    "Set REDIS_URL or GUNICORN_WORKERS=1."
                )
            elif redis_url:
                ping_err = cls._ping_redis(redis_url)
                if ping_err:
                    errors.append(ping_err)
        else:
            if not jwt_secret or jwt_secret in _PLACEHOLDER_JWT or len(jwt_secret) < 32:
                warnings.append(
                    "  ⚠️  JWT_SECRET: using insecure/dev secret (set a strong secret before production)"
                )

        for var, description in cls.RECOMMENDED_VARS.items():
            value = os.getenv(var)
            if not value:
                warnings.append(f"  ⚠️  {var}: {description}")
            elif value.startswith('YOUR_') or (var == 'MAIL_USERNAME' and value.startswith('your-')):
                warnings.append(f"  ⚠️  {var}: Still has placeholder value. {description}")

        is_valid = len(errors) == 0
        if strict:
            is_valid = is_valid and len(warnings) == 0
        return is_valid, errors, warnings

    @classmethod
    def print_report(cls, strict: bool = False) -> bool:
        is_valid, errors, warnings = cls.validate(strict)

        print("\n" + "=" * 60)
        print("🔍 ENVIRONMENT VALIDATION")
        print("=" * 60)

        if errors:
            print("\n❌ MISSING REQUIRED CONFIGURATION:")
            print("-" * 40)
            for error in errors:
                print(error)
            print("\n📋 To fix:")
            print("   1. Copy apps/backend/.env.example to apps/backend/.env")
            print("   2. Set DATABASE_URL or POSTGRES_* variables")
            print("   3. Set a unique JWT_SECRET (≥32 chars)")
            print("   4. Set INTEGRATION_SECRETS_KEY (production)")
            print("   5. Restart the application")

        if warnings:
            print("\n⚠️  RECOMMENDED CONFIGURATION:")
            print("-" * 40)
            for warning in warnings:
                print(warning)

        if is_valid and not warnings:
            print("\n✅ All environment variables are configured correctly!")
        elif is_valid:
            print("\n✅ Required configuration complete (with warnings above)")
        else:
            print("\n❌ STARTUP BLOCKED - Fix required configuration first!")

        print("=" * 60 + "\n")
        return is_valid


def validate_env_or_exit(strict: bool = False):
    from dotenv import load_dotenv
    load_dotenv()

    if not EnvValidator.print_report(strict):
        print("💡 TIP: Copy apps/backend/.env.example to apps/backend/.env and configure it.\n")
        sys.exit(1)


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    success = EnvValidator.print_report()
    sys.exit(0 if success else 1)
