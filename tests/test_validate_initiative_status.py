"""Tests for initiative status validation script."""

import json
import pytest
from pathlib import Path
from validate_initiative_status import (
    ValidationResult,
    validate_initiative_status,
    _check_data_quality,
    _check_commitment_blockers,
    _is_ready_to_plan,
    find_latest_extract
)


def test_validation_result_has_issues():
    """Test ValidationResult.has_issues property."""
    result = ValidationResult()
    assert not result.has_issues

    result.fix_data_quality.append({'key': 'INIT-1'})
    assert result.has_issues

    result2 = ValidationResult()
    result2.address_blockers.append({'key': 'INIT-2'})
    assert result2.has_issues

    result3 = ValidationResult()
    result3.planned_regressions.append({'key': 'INIT-3'})
    assert result3.has_issues


def test_check_data_quality_epic_count_mismatch():
    """Test data quality check with epic count != teams count."""
    initiative = {
        "key": "INIT-123",
        "summary": "Test Initiative",
        "status": "Proposed",
        "assignee": "user@example.com",
        "teams_involved": ["TEAM1", "TEAM2"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [{"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"}]
            },
            {
                "team_project_key": "TEAM2",
                "epics": [{"key": "TEAM2-1", "summary": "Epic 2", "rag_status": "🟢"}]
            },
            {
                "team_project_key": "TEAM3",  # Not in teams_involved
                "epics": [{"key": "TEAM3-1", "summary": "Epic 3", "rag_status": "🟢"}]
            }
        ]
    }

    issues = _check_data_quality(initiative)

    assert issues is not None
    assert len(issues) == 1
    assert issues[0]['type'] == 'epic_count_mismatch'
    assert set(issues[0]['teams_with_epics']) == {"TEAM1", "TEAM2", "TEAM3"}
    assert issues[0]['teams_involved'] == ["TEAM1", "TEAM2"]


def test_check_data_quality_missing_rag():
    """Test data quality check with missing RAG status."""
    initiative = {
        "key": "INIT-456",
        "summary": "Test Initiative",
        "status": "Proposed",
        "assignee": "user@example.com",
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [
                    {"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"},
                    {"key": "TEAM1-2", "summary": "Epic 2", "rag_status": None},
                    {"key": "TEAM1-3", "summary": "Epic 3", "rag_status": None}
                ]
            }
        ]
    }

    issues = _check_data_quality(initiative)

    assert issues is not None
    assert len(issues) == 1
    assert issues[0]['type'] == 'missing_rag_status'
    assert len(issues[0]['epics']) == 2
    assert issues[0]['epics'][0]['key'] == 'TEAM1-2'
    assert issues[0]['epics'][1]['key'] == 'TEAM1-3'


def test_check_data_quality_no_epics():
    """Test data quality check with zero epics."""
    initiative = {
        "key": "INIT-789",
        "summary": "Test Initiative",
        "status": "Proposed",
        "assignee": "user@example.com",
        "teams_involved": [],
        "contributing_teams": []
    }

    issues = _check_data_quality(initiative)

    assert issues is not None
    assert len(issues) == 1
    assert issues[0]['type'] == 'no_epics'


def test_check_data_quality_all_good():
    """Test data quality check with no issues."""
    initiative = {
        "key": "INIT-100",
        "summary": "Test Initiative",
        "status": "Proposed",
        "assignee": "user@example.com",
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [{"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"}]
            }
        ]
    }

    issues = _check_data_quality(initiative)

    assert issues is None


def test_check_commitment_blockers_red_epic():
    """Test commitment blockers check with RED epic."""
    initiative = {
        "key": "INIT-200",
        "summary": "Test Initiative",
        "status": "Proposed",
        "assignee": "user@example.com",
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [{"key": "TEAM1-1", "summary": "Blocked Epic", "rag_status": "🔴"}]
            }
        ]
    }

    issues = _check_commitment_blockers(initiative)

    assert issues is not None
    assert len(issues) == 1
    assert issues[0]['type'] == 'red_epics'
    assert len(issues[0]['epics']) == 1
    assert issues[0]['epics'][0]['key'] == 'TEAM1-1'
    assert issues[0]['epics'][0]['rag_status'] == '🔴'


def test_check_commitment_blockers_yellow_epic():
    """Test commitment blockers check with YELLOW epic."""
    initiative = {
        "key": "INIT-300",
        "summary": "Test Initiative",
        "status": "Proposed",
        "assignee": "user@example.com",
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [{"key": "TEAM1-1", "summary": "At Risk Epic", "rag_status": "⚠️"}]
            }
        ]
    }

    issues = _check_commitment_blockers(initiative)

    assert issues is not None
    assert len(issues) == 1
    assert issues[0]['type'] == 'yellow_epics'
    assert len(issues[0]['epics']) == 1
    assert issues[0]['epics'][0]['key'] == 'TEAM1-1'


def test_check_commitment_blockers_missing_rag_treated_as_red():
    """Test commitment blockers check treats missing RAG as RED."""
    initiative = {
        "key": "INIT-400",
        "summary": "Test Initiative",
        "status": "Proposed",
        "assignee": "user@example.com",
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [{"key": "TEAM1-1", "summary": "Epic No RAG", "rag_status": None}]
            }
        ]
    }

    issues = _check_commitment_blockers(initiative)

    assert issues is not None
    assert len(issues) == 1
    assert issues[0]['type'] == 'red_epics'
    assert len(issues[0]['epics']) == 1
    assert issues[0]['epics'][0]['rag_status'] is None


def test_check_commitment_blockers_no_assignee():
    """Test commitment blockers check with missing assignee."""
    initiative = {
        "key": "INIT-500",
        "summary": "Test Initiative",
        "status": "Proposed",
        "assignee": None,
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [{"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"}]
            }
        ]
    }

    issues = _check_commitment_blockers(initiative)

    assert issues is not None
    assert len(issues) == 1
    assert issues[0]['type'] == 'no_assignee'


def test_check_commitment_blockers_all_good():
    """Test commitment blockers check with no issues."""
    initiative = {
        "key": "INIT-600",
        "summary": "Test Initiative",
        "status": "Proposed",
        "assignee": "user@example.com",
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [{"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"}]
            }
        ]
    }

    issues = _check_commitment_blockers(initiative)

    assert issues is None


def test_is_ready_to_plan_all_criteria_met():
    """Test _is_ready_to_plan with all criteria met."""
    initiative = {
        "key": "INIT-700",
        "summary": "Ready Initiative",
        "status": "Proposed",
        "assignee": "user@example.com",
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [{"key": "TEAM1-1", "summary": "Green Epic", "rag_status": "🟢"}]
            }
        ]
    }

    assert _is_ready_to_plan(initiative) is True


def test_is_ready_to_plan_no_epics():
    """Test _is_ready_to_plan with no epics."""
    initiative = {
        "key": "INIT-800",
        "summary": "No Epics",
        "status": "Proposed",
        "assignee": "user@example.com",
        "teams_involved": [],
        "contributing_teams": []
    }

    assert _is_ready_to_plan(initiative) is False


def test_is_ready_to_plan_no_assignee():
    """Test _is_ready_to_plan with no assignee."""
    initiative = {
        "key": "INIT-900",
        "summary": "No Assignee",
        "status": "Proposed",
        "assignee": None,
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [{"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"}]
            }
        ]
    }

    assert _is_ready_to_plan(initiative) is False


def test_is_ready_to_plan_epic_count_mismatch():
    """Test _is_ready_to_plan with epic count mismatch."""
    initiative = {
        "key": "INIT-1000",
        "summary": "Count Mismatch",
        "status": "Proposed",
        "assignee": "user@example.com",
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [{"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"}]
            },
            {
                "team_project_key": "TEAM2",
                "epics": [{"key": "TEAM2-1", "summary": "Epic 2", "rag_status": "🟢"}]
            }
        ]
    }

    assert _is_ready_to_plan(initiative) is False


def test_is_ready_to_plan_not_all_green():
    """Test _is_ready_to_plan with non-GREEN epic."""
    initiative = {
        "key": "INIT-1100",
        "summary": "Not All Green",
        "status": "Proposed",
        "assignee": "user@example.com",
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [
                    {"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"},
                    {"key": "TEAM1-2", "summary": "Epic 2", "rag_status": "⚠️"}
                ]
            }
        ]
    }

    assert _is_ready_to_plan(initiative) is False


def test_validate_initiative_status_fix_data_quality(tmp_path):
    """Test full validation with data quality issues."""
    data = {
        "initiatives": [{
            "key": "INIT-123",
            "summary": "Test Initiative",
            "status": "Proposed",
            "assignee": "user@example.com",
            "teams_involved": ["TEAM1", "TEAM2"],
            "contributing_teams": [
                {
                    "team_project_key": "TEAM1",
                    "epics": [{"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"}]
                },
                {
                    "team_project_key": "TEAM2",
                    "epics": [{"key": "TEAM2-1", "summary": "Epic 2", "rag_status": "🟢"}]
                },
                {
                    "team_project_key": "TEAM3",
                    "epics": [{"key": "TEAM3-1", "summary": "Epic 3", "rag_status": "🟢"}]
                }
            ]
        }]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(data))

    result = validate_initiative_status(json_file)

    assert result.total_checked == 1
    assert len(result.fix_data_quality) == 1
    assert result.fix_data_quality[0]['key'] == "INIT-123"
    assert len(result.address_blockers) == 0
    assert len(result.ready_to_plan) == 0


def test_validate_initiative_status_address_blockers(tmp_path):
    """Test full validation with commitment blockers."""
    data = {
        "initiatives": [{
            "key": "INIT-456",
            "summary": "Test Initiative",
            "status": "Proposed",
            "assignee": "user@example.com",
            "teams_involved": ["TEAM1"],
            "contributing_teams": [
                {
                    "team_project_key": "TEAM1",
                    "epics": [{"key": "TEAM1-1", "summary": "Blocked Epic", "rag_status": "🔴"}]
                }
            ]
        }]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(data))

    result = validate_initiative_status(json_file)

    assert result.total_checked == 1
    assert len(result.fix_data_quality) == 0
    assert len(result.address_blockers) == 1
    assert result.address_blockers[0]['key'] == "INIT-456"
    assert len(result.ready_to_plan) == 0


def test_validate_initiative_status_ready_to_plan(tmp_path):
    """Test full validation with ready initiative."""
    data = {
        "initiatives": [{
            "key": "INIT-789",
            "summary": "Ready Initiative",
            "status": "Proposed",
            "assignee": "user@example.com",
            "teams_involved": ["TEAM1"],
            "contributing_teams": [
                {
                    "team_project_key": "TEAM1",
                    "epics": [{"key": "TEAM1-1", "summary": "Green Epic", "rag_status": "🟢"}]
                }
            ]
        }]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(data))

    result = validate_initiative_status(json_file)

    assert result.total_checked == 1
    assert len(result.fix_data_quality) == 0
    assert len(result.address_blockers) == 0
    assert len(result.ready_to_plan) == 1
    assert result.ready_to_plan[0]['key'] == "INIT-789"


def test_validate_initiative_status_planned_regression(tmp_path):
    """Test full validation with Planned initiative regression."""
    data = {
        "initiatives": [{
            "key": "INIT-999",
            "summary": "Regressed Initiative",
            "status": "Planned",
            "assignee": "user@example.com",
            "teams_involved": ["TEAM1"],
            "contributing_teams": [
                {
                    "team_project_key": "TEAM1",
                    "epics": [{"key": "TEAM1-1", "summary": "Now Red", "rag_status": "🔴"}]
                }
            ]
        }]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(data))

    result = validate_initiative_status(json_file)

    assert result.total_checked == 1
    assert len(result.fix_data_quality) == 0
    assert len(result.address_blockers) == 0
    assert len(result.ready_to_plan) == 0
    assert len(result.planned_regressions) == 1
    assert result.planned_regressions[0]['key'] == "INIT-999"


def test_validate_initiative_status_mixed_statuses(tmp_path):
    """Test full validation with mixed initiative statuses."""
    data = {
        "initiatives": [
            {
                "key": "INIT-001",
                "summary": "Data Quality Issue",
                "status": "Proposed",
                "assignee": "user@example.com",
                "teams_involved": [],
                "contributing_teams": []
            },
            {
                "key": "INIT-002",
                "summary": "Commitment Blocker",
                "status": "Proposed",
                "assignee": None,
                "teams_involved": ["TEAM1"],
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM1",
                        "epics": [{"key": "TEAM1-1", "summary": "Epic", "rag_status": "🟢"}]
                    }
                ]
            },
            {
                "key": "INIT-003",
                "summary": "Ready",
                "status": "Proposed",
                "assignee": "user@example.com",
                "teams_involved": ["TEAM1"],
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM1",
                        "epics": [{"key": "TEAM1-1", "summary": "Epic", "rag_status": "🟢"}]
                    }
                ]
            },
            {
                "key": "INIT-004",
                "summary": "Planned Regression",
                "status": "Planned",
                "assignee": "user@example.com",
                "teams_involved": ["TEAM1"],
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM1",
                        "epics": [{"key": "TEAM1-1", "summary": "Epic", "rag_status": "🔴"}]
                    }
                ]
            }
        ]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(data))

    result = validate_initiative_status(json_file)

    assert result.total_checked == 4
    assert len(result.fix_data_quality) == 1
    assert len(result.address_blockers) == 1
    assert len(result.ready_to_plan) == 1
    assert len(result.planned_regressions) == 1


def test_find_latest_extract_with_json_files(tmp_path, monkeypatch):
    """Test find_latest_extract with JSON extraction files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create test files with different timestamps
    file1 = data_dir / "jira_extract_20260319.json"
    file2 = data_dir / "jira_extract_20260320.json"
    file3 = data_dir / "jira_extract_20260321.json"

    file1.write_text("{}")
    file2.write_text("{}")
    file3.write_text("{}")

    # Change to tmp directory
    monkeypatch.chdir(tmp_path)

    latest = find_latest_extract()
    assert latest.name == "jira_extract_20260321.json"


def test_find_latest_extract_with_snapshots(tmp_path, monkeypatch):
    """Test find_latest_extract with snapshot files."""
    data_dir = tmp_path / "data"
    snapshots_dir = data_dir / "snapshots"
    data_dir.mkdir()
    snapshots_dir.mkdir()

    # Create test files
    file1 = snapshots_dir / "snapshot_old.json"
    file2 = snapshots_dir / "snapshot_new.json"

    file1.write_text("{}")
    file2.write_text("{}")

    # Change to tmp directory
    monkeypatch.chdir(tmp_path)

    latest = find_latest_extract()
    assert latest.name == "snapshot_new.json"


def test_find_latest_extract_no_data_dir(tmp_path, monkeypatch):
    """Test find_latest_extract with no data directory."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError, match="No data directory found"):
        find_latest_extract()


def test_find_latest_extract_no_files(tmp_path, monkeypatch):
    """Test find_latest_extract with empty data directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError, match="No extraction files found"):
        find_latest_extract()


def test_normalize_teams_involved_handles_none():
    """Test _normalize_teams_involved handles None/null values."""
    from validate_initiative_status import _normalize_teams_involved

    assert _normalize_teams_involved(None) == []


def test_normalize_teams_involved_handles_string():
    """Test _normalize_teams_involved handles comma-separated strings."""
    from validate_initiative_status import _normalize_teams_involved

    # Single team
    assert _normalize_teams_involved("Identity") == ["Identity"]

    # Multiple teams
    assert _normalize_teams_involved("Identity, Core Banking, MAP") == [
        "Identity", "Core Banking", "MAP"
    ]

    # Teams with extra whitespace
    assert _normalize_teams_involved(" Team1 ,  Team2  , Team3 ") == [
        "Team1", "Team2", "Team3"
    ]

    # Empty string
    assert _normalize_teams_involved("") == []

    # String with only commas and spaces
    assert _normalize_teams_involved(" , , ") == []


def test_normalize_teams_involved_handles_list():
    """Test _normalize_teams_involved handles list values."""
    from validate_initiative_status import _normalize_teams_involved

    # Normal list
    assert _normalize_teams_involved(["Team1", "Team2"]) == ["Team1", "Team2"]

    # Empty list
    assert _normalize_teams_involved([]) == []

    # Single item list
    assert _normalize_teams_involved(["Team1"]) == ["Team1"]


def test_count_teams_involved():
    """Test _count_teams_involved with various formats."""
    from validate_initiative_status import _count_teams_involved

    # None/null
    assert _count_teams_involved(None) == 0

    # String formats
    assert _count_teams_involved("Identity, Core Banking, MAP") == 3
    assert _count_teams_involved("Single Team") == 1
    assert _count_teams_involved("") == 0

    # List formats
    assert _count_teams_involved(["Team1", "Team2", "Team3"]) == 3
    assert _count_teams_involved([]) == 0
    assert _count_teams_involved(["Team1"]) == 1


def test_validate_initiative_status_min_teams_filter(tmp_path):
    """Test min_teams parameter filters initiatives correctly."""
    # Create test data with varying team counts
    test_data = {
        "initiatives": [
            {
                "key": "INIT-1",
                "summary": "One team initiative",
                "status": "Proposed",
                "assignee": "user1",
                "teams_involved": ["TEAM1"],
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM1",
                        "epics": [
                            {"key": "EPIC-1", "summary": "Epic 1", "rag_status": "🟢"}
                        ]
                    }
                ]
            },
            {
                "key": "INIT-2",
                "summary": "Two team initiative",
                "status": "Proposed",
                "assignee": "user2",
                "teams_involved": ["TEAM1", "TEAM2"],
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM1",
                        "epics": [
                            {"key": "EPIC-2", "summary": "Epic 2", "rag_status": "🟢"}
                        ]
                    },
                    {
                        "team_project_key": "TEAM2",
                        "epics": [
                            {"key": "EPIC-3", "summary": "Epic 3", "rag_status": "🟢"}
                        ]
                    }
                ]
            },
            {
                "key": "INIT-3",
                "summary": "Three team initiative",
                "status": "Proposed",
                "assignee": "user3",
                "teams_involved": ["TEAM1", "TEAM2", "TEAM3"],
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM1",
                        "epics": [
                            {"key": "EPIC-4", "summary": "Epic 4", "rag_status": "🟢"}
                        ]
                    },
                    {
                        "team_project_key": "TEAM2",
                        "epics": [
                            {"key": "EPIC-5", "summary": "Epic 5", "rag_status": "🟢"}
                        ]
                    },
                    {
                        "team_project_key": "TEAM3",
                        "epics": [
                            {"key": "EPIC-6", "summary": "Epic 6", "rag_status": "🟢"}
                        ]
                    }
                ]
            }
        ]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_data))

    # Test with min_teams=1 (default) - should include all 3 initiatives
    result = validate_initiative_status(json_file, min_teams=1)
    assert result.total_checked == 3
    assert result.total_filtered == 0
    assert len(result.ready_to_plan) == 3

    # Test with min_teams=2 - should include only 2 initiatives
    result = validate_initiative_status(json_file, min_teams=2)
    assert result.total_checked == 2
    assert result.total_filtered == 1
    assert len(result.ready_to_plan) == 2

    # Test with min_teams=3 - should include only 1 initiative
    result = validate_initiative_status(json_file, min_teams=3)
    assert result.total_checked == 1
    assert result.total_filtered == 2
    assert len(result.ready_to_plan) == 1

    # Test with min_teams=4 - should filter out all initiatives
    result = validate_initiative_status(json_file, min_teams=4)
    assert result.total_checked == 0
    assert result.total_filtered == 3
    assert len(result.ready_to_plan) == 0


def test_validate_initiative_status_min_teams_with_various_formats(tmp_path):
    """Test min_teams filter with None, string, and list formats."""
    test_data = {
        "initiatives": [
            {
                "key": "INIT-1",
                "summary": "None teams",
                "status": "Proposed",
                "assignee": "user1",
                "teams_involved": None,  # Real data has this!
                "contributing_teams": []
            },
            {
                "key": "INIT-2",
                "summary": "String single team",
                "status": "Proposed",
                "assignee": "user2",
                "teams_involved": "Identity",
                "contributing_teams": [
                    {
                        "team_project_key": "Identity",
                        "epics": [
                            {"key": "EPIC-1", "summary": "Epic 1", "rag_status": "🟢"}
                        ]
                    }
                ]
            },
            {
                "key": "INIT-3",
                "summary": "String multiple teams",
                "status": "Proposed",
                "assignee": "user3",
                "teams_involved": "Identity, Core Banking, MAP",
                "contributing_teams": [
                    {
                        "team_project_key": "Identity",
                        "epics": [
                            {"key": "EPIC-2", "summary": "Epic 2", "rag_status": "🟢"}
                        ]
                    },
                    {
                        "team_project_key": "Core Banking",
                        "epics": [
                            {"key": "EPIC-3", "summary": "Epic 3", "rag_status": "🟢"}
                        ]
                    },
                    {
                        "team_project_key": "MAP",
                        "epics": [
                            {"key": "EPIC-4", "summary": "Epic 4", "rag_status": "🟢"}
                        ]
                    }
                ]
            },
            {
                "key": "INIT-4",
                "summary": "List format",
                "status": "Proposed",
                "assignee": "user4",
                "teams_involved": ["Team1", "Team2"],
                "contributing_teams": [
                    {
                        "team_project_key": "Team1",
                        "epics": [
                            {"key": "EPIC-5", "summary": "Epic 5", "rag_status": "🟢"}
                        ]
                    },
                    {
                        "team_project_key": "Team2",
                        "epics": [
                            {"key": "EPIC-6", "summary": "Epic 6", "rag_status": "🟢"}
                        ]
                    }
                ]
            }
        ]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_data))

    # Test with min_teams=1 - should include all except None
    result = validate_initiative_status(json_file, min_teams=1)
    assert result.total_checked == 4
    assert result.total_filtered == 0

    # Test with min_teams=2 - should include only string(3 teams) and list(2 teams)
    result = validate_initiative_status(json_file, min_teams=2)
    assert result.total_checked == 2
    assert result.total_filtered == 2
    # INIT-3 (3 teams) and INIT-4 (2 teams) should be included
    assert len(result.ready_to_plan) == 2

    # Test with min_teams=3 - should include only string with 3 teams
    result = validate_initiative_status(json_file, min_teams=3)
    assert result.total_checked == 1
    assert result.total_filtered == 3
    assert len(result.ready_to_plan) == 1
