# tests/test_comparator.py
"""Tests for snapshot comparison logic."""

import pytest
from src.snapshot import Snapshot, SnapshotMetadata
from src.comparator import SnapshotComparator


@pytest.fixture
def baseline_snapshot():
    """Baseline snapshot with known state."""
    return Snapshot(
        metadata=SnapshotMetadata(
            label="baseline",
            timestamp="2026-01-01T10:00:00Z",
            jira_instance="test.atlassian.net",
            config_snapshot={"custom_fields": {"initiatives": {}}},
            total_initiatives=3,
            total_epics=10,
            total_teams=2
        ),
        data={
            "jira_instance": "test.atlassian.net",
            "initiatives": [
                {
                    "key": "INIT-1",
                    "summary": "Planned Initiative 1",
                    "status": "Planned",
                    "contributing_teams": [
                        {
                            "team_project_key": "TEAM1",
                            "epics": [
                                {"key": "TEAM1-1", "summary": "Epic 1"},
                                {"key": "TEAM1-2", "summary": "Epic 2"}
                            ]
                        }
                    ]
                },
                {
                    "key": "INIT-2",
                    "summary": "Planned Initiative 2",
                    "status": "Planned",
                    "contributing_teams": [
                        {
                            "team_project_key": "TEAM2",
                            "epics": [
                                {"key": "TEAM2-1", "summary": "Epic 3"}
                            ]
                        }
                    ]
                },
                {
                    "key": "INIT-3",
                    "summary": "Proposed Initiative 3",
                    "status": "Proposed",
                    "contributing_teams": []
                }
            ],
            "orphaned_epics": [
                {"key": "ORPHAN-1", "summary": "Orphaned Epic 1"}
            ]
        }
    )


@pytest.fixture
def current_snapshot_with_drops(baseline_snapshot):
    """Current snapshot where INIT-2 dropped to Cancelled."""
    data = baseline_snapshot.data.copy()
    data["initiatives"] = [
        data["initiatives"][0],  # INIT-1 unchanged
        {
            "key": "INIT-2",
            "summary": "Planned Initiative 2",
            "status": "Cancelled",  # Changed from Planned
            "contributing_teams": [
                {
                    "team_project_key": "TEAM2",
                    "epics": [
                        {"key": "TEAM2-1", "summary": "Epic 3"}
                    ]
                }
            ]
        },
        data["initiatives"][2]  # INIT-3 unchanged
    ]

    return Snapshot(
        metadata=baseline_snapshot.metadata,
        data=data
    )


@pytest.fixture
def current_snapshot_with_additions(baseline_snapshot):
    """Current snapshot with new Planned initiative."""
    data = baseline_snapshot.data.copy()
    data["initiatives"] = data["initiatives"] + [
        {
            "key": "INIT-4",
            "summary": "New Planned Initiative",
            "status": "Planned",
            "contributing_teams": [
                {
                    "team_project_key": "TEAM1",
                    "epics": [{"key": "TEAM1-5", "summary": "New Epic"}]
                }
            ]
        }
    ]

    return Snapshot(
        metadata=baseline_snapshot.metadata,
        data=data
    )


def test_detect_dropped_initiatives(baseline_snapshot, current_snapshot_with_drops):
    """Correctly identifies dropped initiatives."""
    comparator = SnapshotComparator(baseline_snapshot, current_snapshot_with_drops)
    result = comparator._detect_dropped_initiatives()

    assert len(result) == 1
    assert result[0].initiative_key == "INIT-2"
    assert result[0].baseline_status == "Planned"
    assert result[0].current_status == "Cancelled"
    assert result[0].summary == "Planned Initiative 2"


def test_detect_added_initiatives(baseline_snapshot, current_snapshot_with_additions):
    """Identifies new Planned initiatives."""
    comparator = SnapshotComparator(baseline_snapshot, current_snapshot_with_additions)
    result = comparator._detect_added_initiatives()

    assert len(result) == 1
    assert result[0].initiative_key == "INIT-4"
    assert result[0].current_status == "Planned"
    assert result[0].baseline_status is None


def test_detect_epic_churn():
    """Detects epic additions/removals per initiative."""
    baseline = Snapshot(
        metadata=SnapshotMetadata(
            label="baseline",
            timestamp="2026-01-01T10:00:00Z",
            jira_instance="test.atlassian.net",
            config_snapshot={},
            total_initiatives=1,
            total_epics=2,
            total_teams=1
        ),
        data={
            "jira_instance": "test.atlassian.net",
            "initiatives": [
                {
                    "key": "INIT-1",
                    "summary": "Test Initiative",
                    "status": "Planned",
                    "contributing_teams": [
                        {
                            "team_project_key": "TEAM1",
                            "epics": [
                                {"key": "EPIC-1", "summary": "Epic 1"},
                                {"key": "EPIC-2", "summary": "Epic 2"}
                            ]
                        }
                    ]
                }
            ],
            "orphaned_epics": []
        }
    )

    current = Snapshot(
        metadata=baseline.metadata,
        data={
            "jira_instance": "test.atlassian.net",
            "initiatives": [
                {
                    "key": "INIT-1",
                    "summary": "Test Initiative",
                    "status": "Planned",
                    "contributing_teams": [
                        {
                            "team_project_key": "TEAM1",
                            "epics": [
                                {"key": "EPIC-1", "summary": "Epic 1"},  # Unchanged
                                {"key": "EPIC-3", "summary": "Epic 3"}   # Added
                                # EPIC-2 removed
                            ]
                        }
                    ]
                }
            ],
            "orphaned_epics": []
        }
    )

    comparator = SnapshotComparator(baseline, current)
    result = comparator._detect_epic_churn()

    assert len(result) == 1
    churn = result[0]
    assert churn.initiative_key == "INIT-1"
    assert len(churn.epics_added) == 1
    assert len(churn.epics_removed) == 1
    assert churn.net_change == 0
    assert churn.epics_added[0]["key"] == "EPIC-3"
    assert churn.epics_removed[0]["key"] == "EPIC-2"


def test_calculate_team_stability():
    """Calculates correct stability percentages."""
    baseline = Snapshot(
        metadata=SnapshotMetadata(
            label="baseline",
            timestamp="2026-01-01T10:00:00Z",
            jira_instance="test.atlassian.net",
            config_snapshot={},
            total_initiatives=1,
            total_epics=4,
            total_teams=2
        ),
        data={
            "jira_instance": "test.atlassian.net",
            "initiatives": [
                {
                    "key": "INIT-1",
                    "summary": "Test",
                    "status": "Planned",
                    "contributing_teams": [
                        {
                            "team_project_key": "TEAM1",
                            "epics": [
                                {"key": "T1-E1", "summary": "Epic 1"},
                                {"key": "T1-E2", "summary": "Epic 2"}
                            ]
                        },
                        {
                            "team_project_key": "TEAM2",
                            "epics": [
                                {"key": "T2-E1", "summary": "Epic 3"},
                                {"key": "T2-E2", "summary": "Epic 4"}
                            ]
                        }
                    ]
                }
            ],
            "orphaned_epics": []
        }
    )

    current = Snapshot(
        metadata=baseline.metadata,
        data={
            "jira_instance": "test.atlassian.net",
            "initiatives": [
                {
                    "key": "INIT-1",
                    "summary": "Test",
                    "status": "Planned",
                    "contributing_teams": [
                        {
                            "team_project_key": "TEAM1",
                            "epics": [
                                {"key": "T1-E1", "summary": "Epic 1"},  # Unchanged
                                # T1-E2 removed
                                {"key": "T1-E3", "summary": "Epic 5"}   # Added
                            ]
                        },
                        {
                            "team_project_key": "TEAM2",
                            "epics": [
                                {"key": "T2-E1", "summary": "Epic 3"},  # Unchanged
                                {"key": "T2-E2", "summary": "Epic 4"}   # Unchanged
                            ]
                        }
                    ]
                }
            ],
            "orphaned_epics": []
        }
    )

    comparator = SnapshotComparator(baseline, current)
    result = comparator._calculate_team_stability()

    # Sort by team name for predictable order
    result_dict = {t.team_project_key: t for t in result}

    team1 = result_dict["TEAM1"]
    assert team1.total_epics_baseline == 2
    assert team1.epics_unchanged == 1  # T1-E1
    assert team1.epics_added == 1      # T1-E3
    assert team1.epics_removed == 1    # T1-E2
    assert team1.stability_percentage == 50.0  # 1 unchanged / 2 baseline

    team2 = result_dict["TEAM2"]
    assert team2.total_epics_baseline == 2
    assert team2.epics_unchanged == 2
    assert team2.epics_added == 0
    assert team2.epics_removed == 0
    assert team2.stability_percentage == 100.0


def test_comparison_no_changes(baseline_snapshot):
    """Handles identical snapshots."""
    comparator = SnapshotComparator(baseline_snapshot, baseline_snapshot)
    result = comparator.compare()

    assert len(result.dropped_initiatives) == 0
    assert len(result.added_initiatives) == 0
    assert len(result.epic_churn) == 0


def test_comparison_without_eta_field(baseline_snapshot):
    """Skips overrun report when ETA not configured."""
    comparator = SnapshotComparator(baseline_snapshot, baseline_snapshot)
    result = comparator.compare()

    assert result.overrun_initiatives is None


def test_compare_orphaned_epics():
    """Tracks changes in orphaned epics."""
    baseline = Snapshot(
        metadata=SnapshotMetadata(
            label="baseline",
            timestamp="2026-01-01T10:00:00Z",
            jira_instance="test.atlassian.net",
            config_snapshot={},
            total_initiatives=0,
            total_epics=2,
            total_teams=0
        ),
        data={
            "jira_instance": "test.atlassian.net",
            "initiatives": [],
            "orphaned_epics": [
                {"key": "ORPHAN-1", "summary": "Orphan 1"},
                {"key": "ORPHAN-2", "summary": "Orphan 2"}
            ]
        }
    )

    current = Snapshot(
        metadata=baseline.metadata,
        data={
            "jira_instance": "test.atlassian.net",
            "initiatives": [],
            "orphaned_epics": [
                {"key": "ORPHAN-2", "summary": "Orphan 2"},  # Still orphaned
                {"key": "ORPHAN-3", "summary": "Orphan 3"}   # Newly orphaned
                # ORPHAN-1 resolved (assigned to initiative)
            ]
        }
    )

    comparator = SnapshotComparator(baseline, current)
    result = comparator._compare_orphaned_epics()

    assert result.resolved_count == 1
    assert result.newly_orphaned_count == 1
    assert result.still_orphaned_count == 1
    assert result.resolved_epics[0]["key"] == "ORPHAN-1"
    assert result.newly_orphaned_epics[0]["key"] == "ORPHAN-3"
