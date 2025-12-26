"""Utility functions for VixSrc downloader."""

import re
import subprocess
import sys
from typing import Optional

from .constants import INVALID_FILENAME_CHARS


def ensure_dependency(package_name: str, import_name: Optional[str] = None):
    """
    Ensure a dependency is installed, installing it if necessary.

    Args:
        package_name: Package name for pip install
        import_name: Import name if different from package_name

    Returns:
        The imported module
    """
    import_name = import_name or package_name
    try:
        return __import__(import_name)
    except ImportError:
        print(f"Error: '{package_name}' library not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name, "--break-system-packages"])
        return __import__(import_name)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters.

    Args:
        filename: The filename to sanitize

    Returns:
        Sanitized filename safe for filesystem use
    """
    # Remove invalid characters
    for char in INVALID_FILENAME_CHARS:
        filename = filename.replace(char, '')

    # Replace multiple spaces with single space
    filename = re.sub(r'\s+', ' ', filename)

    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')

    return filename
