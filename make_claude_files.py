#!/usr/bin/env python3
"""
Tool for preparing project files for Claude integration.
Creates claude_core directory with flattened core files and full file listing.
"""

import os
import shutil
import subprocess
from pathlib import Path
from collections import defaultdict

# Core files that form the foundation layer
CORE_FILES = {
    # Database and models
    'src/common/database.py',
    'src/common/models.py',
    
    # Core utilities and configuration
    'src/common/logging_config.py',
    'src/common/telemetry.py',
    'src/common/auth.py',
    'src/common/colorscheme.py',
    'src/constants.py',
    
    # API integrations
    'src/common/openai_client.py',
    
    # Channel management
    'src/common/channel_config.py',
    'src/common/messages.py',

    # Core CSS files
    'src/web/css/common.css',
    'src/web/css/atacama.css',

    # Core JS files
    'src/web/js/atacama.js',
}

def ensure_clean_dir(directory: Path) -> None:
    """Create empty directory, removing old contents if necessary."""
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir()

def get_flat_filename(filepath: str) -> str:
    """
    Convert path to flat filename, using prefix for disambiguation.
    Removes 'src' prefix if present.
    
    Examples:
        src/common/auth.py -> common__auth.py
        migrations/env.py -> migrations__env.py
        src/constants.py -> constants.py
    """
    path = Path(filepath)
    parts = list(path.parts)
    
    # Remove 'src' if it's the first component
    if parts[0] == 'src':
        parts.pop(0)
        
    # If only filename remains, return it
    if len(parts) == 1:
        return parts[0]
        
    # Otherwise join all parts except filename with __, then add filename
    prefix = '__'.join(parts[:-1])
    return f"{prefix}__{parts[-1]}"

def check_name_collisions(filepaths: set[str]) -> dict[str, str]:
    """
    Check for filename collisions and return mapping of original paths to flat names.
    """
    # Map each path to its flat name
    path_to_name = {path: get_flat_filename(path) for path in filepaths}
    
    # Verify no collisions in the flat names
    used_names = defaultdict(list)
    for path, name in path_to_name.items():
        used_names[name].append(path)
        
    # Report any collisions found
    for name, paths in used_names.items():
        if len(paths) > 1:
            print(f"Warning: Name collision for {name}:")
            for path in paths:
                print(f"  {path}")
                
    return path_to_name

def get_project_files() -> str:
    """Get list of all tracked files in the git repository."""
    try:
        result = subprocess.run(
            ['git', 'ls-tree', '-r', '--name-only', 'HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running git command: {e}")
        return ""
    except FileNotFoundError:
        print("Error: git command not found")
        return ""

def update_claude_core() -> None:
    """Update claude_core directory with flattened core files and file listing."""
    claude_core = Path.cwd() / 'claude_core'
    ensure_clean_dir(claude_core)
    
    # Check for name collisions and get flat names
    path_to_name = check_name_collisions(CORE_FILES)
    
    # Copy core files with flattened names
    processed = set()
    for file_path in CORE_FILES:
        src_path = Path.cwd() / file_path
        if not src_path.exists():
            print(f"Warning: Core file not found: {file_path}")
            continue
            
        try:
            flat_name = path_to_name[file_path]
            dest_path = claude_core / flat_name
            shutil.copy2(src_path, dest_path)
            processed.add(src_path)
            if flat_name != src_path.name:
                print(f"Copied: {file_path} -> {flat_name}")
            else:
                print(f"Copied: {file_path}")
        except Exception as e:
            print(f"Error copying {file_path}: {str(e)}")
    
    # Create file listing
    file_list = get_project_files()
    if file_list:
        list_path = claude_core / 'project_files.txt'
        list_path.write_text(file_list)
        print(f"\nCreated file listing: {list_path}")
    
    print(f"\nSuccessfully copied {len(processed)} core files to {claude_core}")

if __name__ == '__main__':
    update_claude_core()
