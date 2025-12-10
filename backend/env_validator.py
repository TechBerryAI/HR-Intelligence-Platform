"""
Environment Variable Validator

Validates that all required environment variables are set before the application starts.
Provides clear error messages to help developers set up their environment correctly.
"""

import os
import sys
from typing import Dict, List, Tuple


class EnvValidator:
    """Validates required environment variables on startup."""
    
    # Required variables that MUST be set (no defaults)
    REQUIRED_VARS = {
        'MSSQL_USER': 'SQL Server username (e.g., Test, sa)',
        'MSSQL_PASSWORD': 'SQL Server password',
    }
    
    # Optional but recommended variables
    RECOMMENDED_VARS = {
        'MAIL_USERNAME': 'Gmail address for OTP sending',
        'MAIL_PASSWORD': 'Gmail App Password (not regular password)',
        'XAI_API_KEY': 'X.AI API key for LLM features',
    }
    
    # Variables with safe defaults (don't need to be set)
    DEFAULTED_VARS = {
        'PORT': '3000',
        'FLASK_DEBUG': 'true',
        'MSSQL_SERVER': 'localhost',
        'MSSQL_PORT': '1433',
        'MSSQL_DATABASE': 'JobPortal',
        'MSSQL_ODBC_DRIVER': '{SQL Server}',
        'DB_POOL_SIZE': '5',
        'DB_CONNECTION_TIMEOUT': '10',
    }
    
    @classmethod
    def validate(cls, strict: bool = False) -> Tuple[bool, List[str], List[str]]:
        """
        Validate environment variables.
        
        Args:
            strict: If True, also requires recommended variables
            
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        # Check required variables
        for var, description in cls.REQUIRED_VARS.items():
            value = os.getenv(var)
            if not value:
                errors.append(f"  ❌ {var}: {description}")
            elif value.startswith('YOUR_'):
                errors.append(f"  ❌ {var}: Still has placeholder value. {description}")
        
        # Check recommended variables
        for var, description in cls.RECOMMENDED_VARS.items():
            value = os.getenv(var)
            if not value:
                warnings.append(f"  ⚠️  {var}: {description}")
            elif value.startswith('YOUR_'):
                warnings.append(f"  ⚠️  {var}: Still has placeholder value. {description}")
        
        # Check ODBC driver availability
        odbc_driver = os.getenv('MSSQL_ODBC_DRIVER', '{ODBC Driver 17 for SQL Server}')
        cls._check_odbc_driver(odbc_driver, errors, warnings)
        
        is_valid = len(errors) == 0
        if strict:
            is_valid = is_valid and len(warnings) == 0
            
        return is_valid, errors, warnings
    
    @classmethod
    def _check_odbc_driver(cls, driver: str, errors: List[str], warnings: List[str]):
        """Check if the specified ODBC driver is available."""
        try:
            import pyodbc
            available_drivers = pyodbc.drivers()
            
            # Extract driver name without braces
            driver_name = driver.strip('{}')
            
            if driver_name not in available_drivers:
                sql_drivers = [d for d in available_drivers if 'SQL' in d.upper()]
                if sql_drivers:
                    warnings.append(
                        f"  ⚠️  ODBC Driver '{driver_name}' not found. "
                        f"Available SQL drivers: {', '.join(sql_drivers)}"
                    )
                else:
                    errors.append(
                        f"  ❌ No SQL Server ODBC drivers found! "
                        f"Install 'ODBC Driver 17 for SQL Server' from Microsoft."
                    )
        except ImportError:
            warnings.append("  ⚠️  pyodbc not installed, cannot verify ODBC driver")
        except Exception as e:
            warnings.append(f"  ⚠️  Could not check ODBC drivers: {e}")
    
    @classmethod
    def print_report(cls, strict: bool = False) -> bool:
        """
        Print a validation report and return whether validation passed.
        """
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
            print("   1. Copy backend/.env.example to backend/.env")
            print("   2. Fill in all YOUR_* placeholders")
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
    """
    Validate environment variables and exit if required ones are missing.
    
    Args:
        strict: If True, also requires recommended variables
    """
    from dotenv import load_dotenv
    load_dotenv()
    
    if not EnvValidator.print_report(strict):
        print("💡 TIP: Copy backend/.env.example to backend/.env and configure it.\n")
        sys.exit(1)


if __name__ == '__main__':
    # Run validation standalone
    from dotenv import load_dotenv
    load_dotenv()
    
    success = EnvValidator.print_report()
    sys.exit(0 if success else 1)

