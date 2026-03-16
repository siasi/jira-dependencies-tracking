# tests/test_snapshot.py
"""Tests for snapshot management."""

import json
import pytest
from pathlib import Path
from freezegun import freeze_time
from dataclasses import asdict

from src.snapshot import SnapshotManager, SnapshotMetadata, Snapshot, SnapshotError
from src.config import Config, JiraConfig, ProjectsConfig, OutputConfig, Filters


@pytest.fixture
def mock_config():
    """Fixture for test configuration."""
    return Config(
        jira=JiraConfig(
            instance="test.atlassian.net",
            email="test@example.com",
            api_token="test-token"
        ),
        projects=ProjectsConfig(
            initiatives="INIT",
            teams=["TEAM1", "TEAM2"]
        ),
        custom_fields={
            "rag_status": "customfield_12111",
            "quarter": "customfield_12108"
        },
        output=OutputConfig(
            directory="./data",
            filename_pattern="jira_extract_{timestamp}.json"
        ),
        filters=Filters(quarter="26 Q2")
    )


@pytest.fixture
def mock_snapshot_data():
    """Fixture factory for test snapshot data."""
    return {
        "jira_instance": "test.atlassian.net",
        "extracted_at": "2026-03-15T10:30:00Z",
        "queries": {},
        "extraction_status": {},
        "summary": {
            "total_initiatives": 10,
            "total_epics": 50,
            "teams_involved": ["TEAM1", "TEAM2"]
        },
        "initiatives": [
            {"key": "INIT-1", "summary": "Test Initiative 1", "status": "Planned"},
            {"key": "INIT-2", "summary": "Test Initiative 2", "status": "Planned"},
        ],
        "orphaned_epics": []
    }


@pytest.fixture
def snapshot_manager(tmp_path):
    """Fixture for SnapshotManager with temp directory."""
    return SnapshotManager(snapshots_directory=str(tmp_path / "snapshots"))


@freeze_time("2026-03-15 10:30:00")
def test_save_snapshot_creates_file(snapshot_manager, mock_snapshot_data, mock_config):
    """Snapshot saved with deterministic timestamp."""
    result = snapshot_manager.save_snapshot(
        label="test-label",
        data=mock_snapshot_data,
        config=mock_config
    )

    assert result.exists()
    assert result.name == "snapshot_test-label_20260315_103000.json"


def test_save_snapshot_preserves_data(snapshot_manager, mock_snapshot_data, mock_config):
    """All extract data included in snapshot."""
    result = snapshot_manager.save_snapshot(
        label="test-label",
        data=mock_snapshot_data,
        config=mock_config
    )

    with open(result, encoding="utf-8") as f:
        saved_data = json.load(f)

    # Check metadata exists
    assert "snapshot_metadata" in saved_data
    assert saved_data["snapshot_metadata"]["label"] == "test-label"
    assert saved_data["snapshot_metadata"]["total_initiatives"] == 10

    # Check original data preserved
    assert saved_data["jira_instance"] == "test.atlassian.net"
    assert saved_data["summary"]["total_initiatives"] == 10


def test_load_snapshot_success(snapshot_manager, mock_snapshot_data, mock_config):
    """Successfully loads existing snapshot."""
    # Save first
    snapshot_manager.save_snapshot(
        label="test-load",
        data=mock_snapshot_data,
        config=mock_config
    )

    # Load
    loaded = snapshot_manager.load_snapshot("test-load")

    assert loaded.metadata.label == "test-load"
    assert loaded.data["jira_instance"] == "test.atlassian.net"
    assert loaded.data["summary"]["total_initiatives"] == 10


def test_load_snapshot_nonexistent(snapshot_manager):
    """Clear error when snapshot doesn't exist."""
    # Create directory first so we test the "file not found" case, not "directory not found"
    snapshot_manager.snapshots_directory.mkdir(parents=True, exist_ok=True)

    with pytest.raises(SnapshotError, match="Snapshot not found: 'missing-label'"):
        snapshot_manager.load_snapshot("missing-label")


def test_load_snapshot_corrupted_json(snapshot_manager, tmp_path):
    """Handles corrupted JSON files gracefully."""
    # Create corrupted file
    corrupted_file = tmp_path / "snapshots" / "snapshot_corrupted_20260315_103000.json"
    corrupted_file.parent.mkdir(parents=True, exist_ok=True)
    corrupted_file.write_text("{ invalid json", encoding="utf-8")

    with pytest.raises(SnapshotError, match="Snapshot file corrupted"):
        snapshot_manager.load_snapshot("corrupted")


def test_list_snapshots_empty_directory(snapshot_manager):
    """Handles empty snapshots directory gracefully."""
    snapshots = snapshot_manager.list_snapshots()
    assert snapshots == []


def test_list_snapshots_sorted_by_timestamp(snapshot_manager, mock_snapshot_data, mock_config):
    """Snapshots listed newest first."""
    # Create multiple snapshots with different timestamps
    with freeze_time("2026-03-15 10:00:00"):
        snapshot_manager.save_snapshot("first", mock_snapshot_data, mock_config)

    with freeze_time("2026-03-15 11:00:00"):
        snapshot_manager.save_snapshot("second", mock_snapshot_data, mock_config)

    with freeze_time("2026-03-15 12:00:00"):
        snapshot_manager.save_snapshot("third", mock_snapshot_data, mock_config)

    snapshots = snapshot_manager.list_snapshots()

    assert len(snapshots) == 3
    assert snapshots[0].label == "third"  # Newest first
    assert snapshots[1].label == "second"
    assert snapshots[2].label == "first"


def test_snapshot_metadata_includes_config(snapshot_manager, mock_snapshot_data, mock_config):
    """Snapshot metadata includes configuration snapshot."""
    result = snapshot_manager.save_snapshot(
        label="config-test",
        data=mock_snapshot_data,
        config=mock_config
    )

    loaded = snapshot_manager.load_snapshot("config-test")

    assert loaded.metadata.config_snapshot["custom_fields"]["rag_status"] == "customfield_12111"
    assert loaded.metadata.config_snapshot["filters"]["quarter"] == "26 Q2"


def test_list_snapshots_skips_corrupted_files(snapshot_manager, mock_snapshot_data, mock_config, tmp_path):
    """Corrupted snapshots are skipped silently in list."""
    # Create valid snapshot
    snapshot_manager.save_snapshot("valid", mock_snapshot_data, mock_config)

    # Create corrupted file
    corrupted = tmp_path / "snapshots" / "snapshot_corrupted_20260315_103000.json"
    corrupted.write_text("{ invalid", encoding="utf-8")

    # List should skip corrupted
    snapshots = snapshot_manager.list_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].label == "valid"
