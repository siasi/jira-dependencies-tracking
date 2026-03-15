# src/output.py
import csv
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class ExtractionStatus:
    """Status of data extraction."""
    complete: bool
    issues: list[dict[str, str]]
    initiatives_fetched: int = 0
    initiatives_failed: int = 0
    team_projects_fetched: int = 0
    team_projects_failed: int = 0


@dataclass
class CSVOutput:
    """CSV export output path."""
    csv_file: Path


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
        data: dict[str, Any],
        extraction_status: ExtractionStatus,
        queries: dict[str, str] | None = None,
        custom_path: Path | None = None,
    ) -> Path:
        """Generate JSON output file.

        Args:
            data: Hierarchy data from builder
            extraction_status: Extraction status information
            queries: JQL queries used for extraction (initiatives and epics)
            custom_path: Optional custom output path (overrides directory/pattern)

        Returns:
            Path to generated file
        """
        # Prepare output
        output = {
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "jira_instance": self.jira_instance,
        }

        # Add queries if provided
        if queries:
            output["queries"] = queries

        output.update({
            "extraction_status": asdict(extraction_status),
            "initiatives": data["initiatives"],
            "orphaned_epics": data.get("orphaned_epics", []),
            "summary": data["summary"],
        })

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

    def generate_csv(
        self,
        data: dict[str, Any],
        extraction_status: ExtractionStatus,
        queries: dict[str, str] | None = None,
        custom_path: Path | None = None,
    ) -> CSVOutput:
        """Generate CSV output file.

        Args:
            data: Hierarchy data from builder
            extraction_status: Extraction status information
            queries: JQL queries used for extraction (not used in CSV)
            custom_path: Optional custom output path (overrides directory/pattern)

        Returns:
            CSVOutput containing path to generated CSV file
        """
        # Determine output path
        if custom_path:
            csv_path = Path(custom_path)
        else:
            # Create output directory
            self.output_directory.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.filename_pattern.replace("{timestamp}", timestamp)
            filename = filename.replace(".json", ".csv")
            csv_path = self.output_directory / filename

        # Ensure parent directory exists
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        # Flatten and write CSV
        rows = self._flatten_for_csv(data)
        self._write_csv(csv_path, rows)

        return CSVOutput(csv_file=csv_path)

    def _flatten_for_csv(self, data: dict[str, Any]) -> list[dict[str, str]]:
        """Flatten initiative -> team -> epic hierarchy to denormalized rows.

        Each epic becomes a row with all parent initiative data repeated.
        Orphaned epics are included with empty initiative columns.

        Args:
            data: Hierarchy data with initiatives and orphaned_epics

        Returns:
            List of flat dictionaries suitable for CSV writing
        """
        rows = []

        # Process linked epics (with parent initiatives)
        for initiative in data.get("initiatives", []):
            # Extract initiative fields
            base_fields = {
                "initiative_key": initiative["key"],
                "initiative_summary": initiative["summary"],
                "initiative_status": initiative["status"],
                "initiative_url": initiative["url"],
            }

            # Extract custom fields dynamically
            custom_fields = {
                k: str(v) if v is not None else ""
                for k, v in initiative.items()
                if k not in ["key", "summary", "status", "url", "contributing_teams"]
            }

            # Process each epic under this initiative
            for team in initiative.get("contributing_teams", []):
                team_fields = {
                    "team_project_key": team["team_project_key"],
                    "team_project_name": team["team_project_name"],
                }

                for epic in team.get("epics", []):
                    row = {
                        **base_fields,
                        **custom_fields,
                        **team_fields,
                        "epic_key": epic["key"],
                        "epic_summary": epic["summary"],
                        "epic_status": epic["status"],
                        "epic_rag_status": epic.get("rag_status") or "",
                        "epic_url": epic["url"],
                    }
                    rows.append(row)

        # Process orphaned epics (no parent initiative)
        for epic in data.get("orphaned_epics", []):
            row = {
                "initiative_key": "",
                "initiative_summary": "",
                "initiative_status": "",
                "initiative_url": "",
                "team_project_key": epic["team_project_key"],
                "team_project_name": epic["team_project_name"],
                "epic_key": epic["key"],
                "epic_summary": epic["summary"],
                "epic_status": epic["status"],
                "epic_rag_status": epic.get("rag_status") or "",
                "epic_url": epic["url"],
            }
            rows.append(row)

        return rows

    def _write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        """Write rows to CSV file with UTF-8 BOM encoding for Excel compatibility.

        Args:
            path: Output file path
            rows: List of dictionaries to write as CSV rows
        """
        # Determine column order
        # Fixed fields first, then custom fields, then team and epic fields
        fixed_fields = [
            "initiative_key",
            "initiative_summary",
            "initiative_status",
            "initiative_url",
        ]
        team_fields = ["team_project_key", "team_project_name"]
        epic_fields = [
            "epic_key",
            "epic_summary",
            "epic_status",
            "epic_rag_status",
            "epic_url",
        ]

        if rows:
            # Extract all keys from first row
            all_keys = set(rows[0].keys())

            # Identify custom fields (everything not in fixed/team/epic)
            known_fields = set(fixed_fields + team_fields + epic_fields)
            custom_fields = sorted(all_keys - known_fields)

            # Final column order
            fieldnames = fixed_fields + custom_fields + team_fields + epic_fields
        else:
            # No rows - use basic fieldnames (no custom fields)
            fieldnames = fixed_fields + team_fields + epic_fields

        # Write CSV with UTF-8 BOM for Excel compatibility
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=fieldnames, extrasaction="ignore", quoting=csv.QUOTE_MINIMAL
            )
            writer.writeheader()
            if rows:
                writer.writerows(rows)
