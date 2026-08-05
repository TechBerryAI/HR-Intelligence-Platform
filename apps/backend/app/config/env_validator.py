"""
Environment Variable Validator

Validates that all required environment variables are set before the application starts.
PostgreSQL: DATABASE_URL or POSTGRES_USER + POSTGRES_PASSWORD.
"""

import os
import sys
from typing import List, Tuple


class EnvValidator:
    # Required for database (PostgreSQL)
    DB_REQUIRED = "Set DATABASE_URL or POSTGRES_USER and POSTGRES_PASSWORD"

    # Optional but recommended for local OTP / notifications
    RECOMMENDED_VARS = {
        'MAIL_USERNAME': 'Gmail address for OTP sending',
        'MAIL_PASSWORD': 'Gmail App Password (not regular password)',
        'JWT_SECRET': 'JWT signing secret (change from placeholder in production)',
    }

    DEFAULTED_VARS = {
        'PORT': '3000',
        'FLASK_DEBUG': 'true',
        'POSTGRES_HOST': 'localhost',
        'POSTGRES_PORT': '5432',
        'POSTGRES_DB': 'JobPortal',
        'DB_POOL_SIZE': '5',
        'DB_CONNECTION_TIMEOUT': '10',
    }

    @classmethod
    def validate(cls, strict: bool = False) -> Tuple[bool, List[str], List[str]]:
        errors = []
        warnings = []

        if not os.getenv('DATABASE_URL') and not (os.getenv('POSTGRES_USER') and os.getenv('POSTGRES_PASSWORD')):
            errors.append(f"  ❌ {cls.DB_REQUIRED}")

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
            print("   3. Restart the application")

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
