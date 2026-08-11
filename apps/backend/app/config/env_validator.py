"""
Environment Variable Validator

Validates that all required environment variables are set before the application starts.
PostgreSQL: DATABASE_URL or POSTGRES_USER + POSTGRES_PASSWORD.
"""

import os
import sys
from typing import List, Tuple

_PLACEHOLDER_JWT = {
    '',
    'your-jwt-secret-change-in-production',
    'changeme',
    'secret',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZXhhbXBsZSJ9.lGrIa8yMwsB_ZSrgoniyr5FF34e9tE7TJboLqTfvifE',
    'dev-only-insecure-jwt-secret-do-not-use-in-prod',
}


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
        flask_debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
        allow_insecure = os.getenv('ALLOW_INSECURE_JWT', 'false').lower() in (
            '1', 'true', 'yes', 'on',
        )
        return not flask_debug and not allow_insecure

    @classmethod
    def validate(cls, strict: bool = False) -> Tuple[bool, List[str], List[str]]:
        errors = []
        warnings = []

        if not os.getenv('DATABASE_URL') and not (os.getenv('POSTGRES_USER') and os.getenv('POSTGRES_PASSWORD')):
            errors.append(f"  ❌ {cls.DB_REQUIRED}")

        jwt_secret = (os.getenv('JWT_SECRET') or '').strip()
        if cls._is_production_like():
            if not jwt_secret or jwt_secret in _PLACEHOLDER_JWT or len(jwt_secret) < 32:
                errors.append(
                    "  ❌ JWT_SECRET: required unique secret (≥32 chars); placeholders are blocked in production"
                )
            if not (os.getenv('N8N_CALLBACK_SECRET') or '').strip():
                # Only required if webhook URL is configured; otherwise warn
                if (os.getenv('N8N_WEBHOOK_URL') or '').strip():
                    errors.append(
                        "  ❌ N8N_CALLBACK_SECRET: required when N8N_WEBHOOK_URL is set"
                    )
                else:
                    warnings.append(
                        "  ⚠️  N8N_CALLBACK_SECRET: set before enabling ATS callbacks"
                    )
            integ = (os.getenv('INTEGRATION_SECRETS_KEY') or '').strip()
            if not integ or integ in ('dev-integration-secrets',):
                warnings.append(
                    "  ⚠️  INTEGRATION_SECRETS_KEY: set a dedicated Fernet key for provider credentials"
                )
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
            print("   4. Restart the application")

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
