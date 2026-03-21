# src/snapshot.py
"""Snapshot management for quarterly tracking."""

import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, Any, List

from src.config import Config


class SnapshotError(Exception):
    """Snapshot-specific errors."""
    pass


@dataclass
class SnapshotMetadata:
    """Metadata captured at snapshot time."""
    label: str                      # User-provided semantic label
    timestamp: str                  # ISO8601 timestamp
    jira_instance: str             # Instance URL
    config_snapshot: Dict[str, Any]  # Custom fields, filters used
    total_initiatives: int
    total_epics: int
    total_teams: int


@dataclass
class Snapshot:
    """Complete snapshot with metadata and data."""
    metadata: SnapshotMetadata
    data: Dict[str, Any]  # Same structure as extract output


class SnapshotManager:
    """Manages snapshot operations - save, load, list."""

    def __init__(self, snapshots_directory: str = "./data/snapshots"):
        """Initialize snapshot manager.

        Args:
            snapshots_directory: Directory for snapshot files
        """
        self.snapshots_directory = Path(snapshots_directory)

    def save_snapshot(
        self,
        label: str,
        data: Dict[str, Any],
        config: Config
    ) -> Path:
        """Save snapshot with metadata.

        Args:
            label: User-provided semantic label (e.g., '2026-Q2-baseline')
            data: Complete extract data from OutputGenerator
            config: Configuration used for extraction

        Returns:
            Path to saved snapshot file

        Raises:
            SnapshotError: If save fails
        """
        # Create snapshot directory
        self.snapshots_directory.mkdir(parents=True, exist_ok=True)

        # Build metadata
        metadata = SnapshotMetadata(
            label=label,
            timestamp=datetime.utcnow().isoformat() + "Z",
            jira_instance=data["jira_instance"],
            config_snapshot={
                "custom_fields": config.custom_fields,
                "filters": asdict(config.filters) if config.filters else None
            },
            total_initiatives=data["summary"]["total_initiatives"],
            total_epics=data["summary"]["total_epics"],
            total_teams=len(data["summary"]["teams_involved"])
        )

        # Add metadata to data
        snapshot_data = {
            "snapshot_metadata": asdict(metadata),
            **data  # Include all extract data
        }

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snapshot_{label}_{timestamp}.json"
        snapshot_path = self.snapshots_directory / filename

        # Write file
        try:
            with open(snapshot_path, "w", encoding="utf-8") as f:
                json.dump(snapshot_data, f, indent=2, ensure_ascii=False)
        except (IOError, OSError) as e:
            raise SnapshotError(f"Failed to save snapshot: {e}")

        return snapshot_path

    def load_snapshot(self, label: str) -> Snapshot:
        """Load snapshot by label.

        Args:
            label: Snapshot label to load

        Returns:
            Snapshot object with metadata and data

        Raises:
            SnapshotError: If snapshot not found or invalid
        """
        if not self.snapshots_directory.exists():
            raise SnapshotError(f"Snapshot directory does not exist: {self.snapshots_directory}")

        # Find snapshot files matching label
        matches = list(self.snapshots_directory.glob(f"snapshot_{label}_*.json"))

        if not matches:
            raise SnapshotError(
                f"Snapshot not found: '{label}'\n"
                f"Run 'python jira_extract.py snapshots list' to see available snapshots."
            )

        if len(matches) > 1:
            raise SnapshotError(
                f"Multiple snapshots found for label '{label}':\n" +
                "\n".join(f"  - {m.name}" for m in matches) +
                f"\nPlease remove old snapshots or use a more specific label."
            )

        snapshot_path = matches[0]

        # Load and parse JSON
        try:
            with open(snapshot_path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise SnapshotError(
                f"Snapshot file corrupted: Invalid JSON at line {e.lineno}\n"
                f"Delete the file and recapture: {snapshot_path}"
            )
        except (IOError, OSError) as e:
            raise SnapshotError(f"Failed to read snapshot: {e}")

        # Extract metadata
        try:
            metadata = SnapshotMetadata(**data["snapshot_metadata"])
        except KeyError as e:
            raise SnapshotError(f"Snapshot missing required metadata field: {e}")
        except TypeError as e:
            raise SnapshotError(f"Snapshot metadata invalid: {e}")

        return Snapshot(metadata=metadata, data=data)

    def list_snapshots(self) -> List[SnapshotMetadata]:
        """List all available snapshots with metadata.

        Returns:
            List of snapshot metadata, sorted by timestamp (newest first)
        """
        if not self.snapshots_directory.exists():
            return []

        snapshots = []

        for file_path in self.snapshots_directory.glob("snapshot_*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                    metadata = SnapshotMetadata(**data["snapshot_metadata"])
                    snapshots.append(metadata)
            except (json.JSONDecodeError, KeyError, TypeError, IOError):
                # Skip corrupted files silently
                continue

        # Sort by timestamp, newest first
        return sorted(snapshots, key=lambda s: s.timestamp, reverse=True)
