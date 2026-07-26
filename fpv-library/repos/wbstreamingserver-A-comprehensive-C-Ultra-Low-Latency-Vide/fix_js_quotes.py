#!/usr/bin/env python3
"""
Fix JavaScript single quotes in web_interface.cpp to make them valid C++ string literals.
"""

import re

def fix_javascript_quotes(input_file, output_file):
    with open(input_file, 'r') as f:
        content = f.read()
    
    # Find script sections and replace single quotes with double quotes
    # Pattern to match JavaScript content within script tags
    def replace_script_quotes(match):
        script_content = match.group(1)
        # Replace single quotes with double quotes, but preserve single quotes in specific contexts
        # This is a simple approach - replace all single quotes with double quotes
        # since JavaScript supports both
        fixed_content = script_content.replace("'", '"')
        return f"<script>\n{fixed_content}\n    </script>"
    
    # Pattern to match content between <script> and </script> tags
    script_pattern = r'<script>\n(.*?)\n    </script>'
    content = re.sub(script_pattern, replace_script_quotes, content, flags=re.DOTALL)
    
    with open(output_file, 'w') as f:
        f.write(content)
    
    print(f"Fixed JavaScript quotes in {output_file}")

if __name__ == "__main__":
    fix_javascript_quotes('src/web/web_interface.cpp', 'src/web/web_interface.cpp')
    print("JavaScript quote fix completed")