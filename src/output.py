# src/output.py
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional


@dataclass
class ExtractionStatus:
    """Status of data extraction."""
    complete: bool
    issues: List[Dict[str, str]]
    initiatives_fetched: int = 0
    initiatives_failed: int = 0
    team_projects_fetched: int = 0
    team_projects_failed: int = 0


class OutputGenerator:
    """Generates JSON output files."""

    def __init__(
        self,
        jira_instance: str,
        output_directory: str = "./data",
        filename_pattern: str = "jira_extract_{timestamp}.json",
    ):
        """Initialize output generator.

        Args:
            jira_instance: Jira instance URL
            output_directory: Directory for output files
            filename_pattern: Filename pattern (use {timestamp} for current time)
        """
        self.jira_instance = jira_instance
        self.output_directory = Path(output_directory)
        self.filename_pattern = filename_pattern

    def generate(
        self,
        data: Dict[str, Any],
        extraction_status: ExtractionStatus,
        custom_path: Optional[Path] = None,
    ) -> Path:
        """Generate JSON output file.

        Args:
            data: Hierarchy data from builder
            extraction_status: Extraction status information
            custom_path: Optional custom output path (overrides directory/pattern)

        Returns:
            Path to generated file
        """
        # Prepare output
        output = {
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "jira_instance": self.jira_instance,
            "extraction_status": asdict(extraction_status),
            "initiatives": data["initiatives"],
            "orphaned_epics": data.get("orphaned_epics", []),
            "summary": data["summary"],
        }

        # Determine output path
        if custom_path:
            output_path = Path(custom_path)
        else:
            # Create output directory
            self.output_directory.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.filename_pattern.replace("{timestamp}", timestamp)
            output_path = self.output_directory / filename

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write JSON
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        return output_path
