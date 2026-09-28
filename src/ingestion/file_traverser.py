"""
Traverse a local repository directory and collect source files
matching the supported extensions.
"""

import os
from typing import List
from src.config import SUPPORTED_EXTENSIONS, IGNORED_DIRS


def collect_source_files(root_dir: str) -> List[str]:
    """
    Walk *root_dir* recursively and return absolute paths to all files
    whose extension is in SUPPORTED_EXTENSIONS, skipping IGNORED_DIRS.
    """
    file_paths: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):
        # Exclude ignored directories in-place
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for fname in filenames:
            if os.path.splitext(fname)[1].lower() in SUPPORTED_EXTENSIONS:
                file_paths.append(os.path.join(dirpath, fname))
    return file_paths
