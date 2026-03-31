"""File utilities for data file discovery and management."""

from pathlib import Path
from typing import Optional
import sys


def find_most_recent_data_file(data_dir: Path = Path('data'),
                                 pattern: str = 'jira_data_*.json') -> Optional[Path]:
    """Find the most recently created data file matching pattern.

    Args:
        data_dir: Directory to search in (default: data/)
        pattern: Glob pattern for files (default: jira_data_*.json)

    Returns:
        Path to most recent file, or None if no files found
    """
    if not data_dir.exists():
        return None

    files = sorted(data_dir.glob(pattern), reverse=True)
    return files[0] if files else None


def get_data_file_or_exit(data_file_arg: Optional[Path] = None,
                           data_dir: Path = Path('data'),
                           pattern: str = 'jira_data_*.json') -> Path:
    """Get data file from argument or auto-discover, exit if not found.

    Args:
        data_file_arg: Explicitly specified data file path (optional)
        data_dir: Directory to search in for auto-discovery
        pattern: Glob pattern for auto-discovery

    Returns:
        Path to data file

    Exits:
        If no data file found (either explicitly or via auto-discovery)
    """
    if data_file_arg:
        if not data_file_arg.exists():
            print(f"Error: Data file not found: {data_file_arg}")
            sys.exit(1)
        return data_file_arg

    # Auto-discover
    data_file = find_most_recent_data_file(data_dir, pattern)
    if not data_file:
        print(f"No data files found in {data_dir}/. Run extract.py first.")
        sys.exit(1)

    return data_file
