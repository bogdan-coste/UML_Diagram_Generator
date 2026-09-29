import os

from src.config import IGNORED_DIRS, SUPPORTED_EXTENSIONS


def collect_source_files(root_dir: str) -> list[str]:
    """
        Walk the root directory recursively and return absolute paths to all files
        whose extension is in SUPPORTED_EXTENSIONS, skipping IGNORED_DIRS.
    """
    file_paths: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):

        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
        for fname in sorted(filenames):
            if os.path.splitext(fname)[1].lower() in SUPPORTED_EXTENSIONS:
                file_paths.append(os.path.join(dirpath, fname))
    return file_paths
