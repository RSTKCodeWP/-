"""Script to replace utc_now() with utc_now() across the codebase."""

import os
import re
from pathlib import Path

def fix_file(filepath):
    """Fix utc_now() usage in a single file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Replace utc_now() with utc_now()
    content = re.sub(r'datetime\.utcnow\(\)', 'utc_now()', content)
    
    # Add import if needed and not already present
    if 'utc_now()' in content and 'from app.utils import utc_now' not in content:
        # Find the last import statement
        import_pattern = r'(from .+ import .+|import .+)'
        imports = list(re.finditer(import_pattern, content))
        
        if imports:
            last_import = imports[-1]
            insert_pos = last_import.end()
            # Insert new import after last import
            content = content[:insert_pos] + '\nfrom app.utils import utc_now' + content[insert_pos:]
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {filepath}")
        return True
    return False

def main():
    """Fix all Python files in the project."""
    project_root = Path(__file__).parent
    python_files = list(project_root.rglob('*.py'))
    
    fixed_count = 0
    for filepath in python_files:
        # Skip virtual environments and migrations
        if 'venv' in str(filepath) or '__pycache__' in str(filepath) or 'migrations' in str(filepath):
            continue
        
        if fix_file(filepath):
            fixed_count += 1
    
    print(f"\nTotal files fixed: {fixed_count}")

if __name__ == '__main__':
    main()
