"""Utilities for managing report output paths and filenames.

Provides consistent output directory structure and filename generation
across all report-generating scripts.
"""

from pathlib import Path
from datetime import datetime
import re
from typing import Tuple


def get_next_report_number(report_type: str) -> int:
    """Get the next progressive number for a given report type.

    Args:
        report_type: Type of report (e.g., 'workload_analysis', 'planning_validation')

    Returns:
        Next progressive number (starting from 1)
    """
    output_dir = Path('output') / report_type

    if not output_dir.exists():
        return 1

    # Find all files matching the pattern: NNN_reporttype_*
    pattern = re.compile(r'^(\d{3})_')
    max_number = 0

    for file in output_dir.iterdir():
        if file.is_file():
            match = pattern.match(file.name)
            if match:
                number = int(match.group(1))
                max_number = max(max_number, number)

    return max_number + 1


def generate_output_path(report_type: str, extension: str, custom_filename: str = None) -> Path:
    """Generate standardized output path for a report.

    Creates output directory structure if it doesn't exist:
        output/<report_type>/<progressive_number>_<report_type>_<timestamp>.<extension>

    Args:
        report_type: Type of report (e.g., 'workload_analysis', 'planning_validation')
        extension: File extension without dot (e.g., 'html', 'md', 'csv')
        custom_filename: Optional custom filename (if provided, ignores standard naming)

    Returns:
        Path object for the output file

    Examples:
        >>> generate_output_path('workload_analysis', 'html')
        Path('output/workload_analysis/001_workload_analysis_20260410_152030.html')

        >>> generate_output_path('planning_validation', 'md', 'custom_report.md')
        Path('custom_report.md')
    """
    # If custom filename provided, use it as-is
    if custom_filename:
        return Path(custom_filename)

    # Create output directory structure
    output_dir = Path('output') / report_type
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get next progressive number
    number = get_next_report_number(report_type)

    # Generate timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Build filename: NNN_reporttype_timestamp.extension
    filename = f"{number:03d}_{report_type}_{timestamp}.{extension}"

    return output_dir / filename


def get_report_info(report_path: Path) -> Tuple[int, str, str]:
    """Extract information from a report filename.

    Args:
        report_path: Path to a report file

    Returns:
        Tuple of (progressive_number, report_type, timestamp_str)
        Returns (0, '', '') if filename doesn't match pattern

    Examples:
        >>> get_report_info(Path('output/workload/001_workload_analysis_20260410_152030.html'))
        (1, 'workload_analysis', '20260410_152030')
    """
    pattern = re.compile(r'^(\d{3})_(.+)_(\d{8}_\d{6})\.')
    match = pattern.match(report_path.name)

    if match:
        return int(match.group(1)), match.group(2), match.group(3)

    return 0, '', ''


def list_reports(report_type: str = None) -> list[Path]:
    """List all reports, optionally filtered by type.

    Args:
        report_type: Optional report type to filter by

    Returns:
        List of Path objects sorted by progressive number (newest first)
    """
    output_dir = Path('output')

    if not output_dir.exists():
        return []

    reports = []

    if report_type:
        # List reports for specific type
        type_dir = output_dir / report_type
        if type_dir.exists():
            reports = [f for f in type_dir.iterdir() if f.is_file()]
    else:
        # List all reports across all types
        for subdir in output_dir.iterdir():
            if subdir.is_dir():
                reports.extend([f for f in subdir.iterdir() if f.is_file()])

    # Sort by progressive number (descending)
    def sort_key(path: Path) -> int:
        number, _, _ = get_report_info(path)
        return -number  # Negative for descending order

    return sorted(reports, key=sort_key)
