"""Script to check project health and configuration."""

import sys
import os
from pathlib import Path
from typing import List, Tuple

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def check_file_exists(filepath: str) -> bool:
    """Check if file exists."""
    return Path(filepath).exists()


def check_env_file() -> Tuple[bool, str]:
    """Check .env file configuration."""
    if not check_file_exists('.env'):
        return False, ".env file not found. Copy .env.example to .env"
    
    with open('.env', 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'YOUR_BOT_TOKEN_HERE' in content:
        return False, "TELEGRAM_BOT_TOKEN not configured in .env"
    
    if 'TELEGRAM_BOT_TOKEN=' not in content:
        return False, "TELEGRAM_BOT_TOKEN not found in .env"
    
    return True, ".env file configured"


def check_python_version() -> Tuple[bool, str]:
    """Check Python version."""
    version = sys.version_info
    if version.major == 3 and version.minor >= 10:
        return True, f"Python {version.major}.{version.minor}.{version.micro}"
    return False, f"Python {version.major}.{version.minor} (requires 3.10+)"


def check_dependencies() -> Tuple[bool, str]:
    """Check if dependencies are installed."""
    try:
        import aiogram
        import sqlalchemy
        import pydantic
        import httpx
        return True, "Core dependencies installed"
    except ImportError as e:
        return False, f"Missing dependency: {e.name}"


def check_directory_structure() -> List[Tuple[bool, str]]:
    """Check project directory structure."""
    required_dirs = [
        'app',
        'app/database',
        'app/handlers',
        'app/middleware',
        'app/services',
        'tests',
        'tests/unit',
        'tests/integration',
        'migrations',
    ]
    
    results = []
    for dir_path in required_dirs:
        exists = Path(dir_path).is_dir()
        results.append((exists, f"Directory: {dir_path}"))
    
    return results


def check_required_files() -> List[Tuple[bool, str]]:
    """Check required files."""
    required_files = [
        'app/main.py',
        'app/config.py',
        'app/utils.py',
        'requirements.txt',
        'Dockerfile',
        'docker-compose.yml',
        'alembic.ini',
        'pytest.ini',
        'Makefile',
        '.pre-commit-config.yaml',
    ]
    
    results = []
    for file_path in required_files:
        exists = check_file_exists(file_path)
        results.append((exists, f"File: {file_path}"))
    
    return results


def check_database() -> Tuple[bool, str]:
    """Check database configuration."""
    data_dir = Path('data')
    if not data_dir.exists():
        return False, "data/ directory not found (will be created on first run)"
    
    db_file = data_dir / 'oleg.db'
    if db_file.exists():
        return True, f"Database exists ({db_file.stat().st_size} bytes)"
    
    return False, "Database not initialized (run 'make db-init')"


def print_check(passed: bool, message: str):
    """Print check result."""
    if passed:
        print(f"{GREEN}✓{RESET} {message}")
    else:
        print(f"{RED}✗{RESET} {message}")


def main():
    """Run all checks."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Oleg Bot - Project Health Check{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    all_passed = True
    
    # Python version
    print(f"{YELLOW}Python Environment:{RESET}")
    passed, msg = check_python_version()
    print_check(passed, msg)
    all_passed = all_passed and passed
    
    # Dependencies
    passed, msg = check_dependencies()
    print_check(passed, msg)
    all_passed = all_passed and passed
    
    print()
    
    # Configuration
    print(f"{YELLOW}Configuration:{RESET}")
    passed, msg = check_env_file()
    print_check(passed, msg)
    all_passed = all_passed and passed
    
    print()
    
    # Directory structure
    print(f"{YELLOW}Directory Structure:{RESET}")
    for passed, msg in check_directory_structure():
        print_check(passed, msg)
        all_passed = all_passed and passed
    
    print()
    
    # Required files
    print(f"{YELLOW}Required Files:{RESET}")
    for passed, msg in check_required_files():
        print_check(passed, msg)
        all_passed = all_passed and passed
    
    print()
    
    # Database
    print(f"{YELLOW}Database:{RESET}")
    passed, msg = check_database()
    print_check(passed, msg)
    # Don't fail if DB not initialized yet
    
    print(f"\n{BLUE}{'='*60}{RESET}")
    
    if all_passed:
        print(f"{GREEN}✓ All checks passed! Project is ready.{RESET}")
        print(f"\n{YELLOW}Next steps:{RESET}")
        print("  1. Run 'make db-init' to initialize database")
        print("  2. Run 'make run' to start the bot")
        print("  3. Run 'make test' to run tests")
        return 0
    else:
        print(f"{RED}✗ Some checks failed. Please fix the issues above.{RESET}")
        print(f"\n{YELLOW}Quick fixes:{RESET}")
        print("  - Install dependencies: pip install -r requirements.txt")
        print("  - Configure .env: cp .env.example .env && nano .env")
        print("  - Initialize database: make db-init")
        return 1


if __name__ == '__main__':
    sys.exit(main())
