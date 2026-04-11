"""Tests for Tech Leadership priority validation script."""

import json
import pytest
import yaml
from pathlib import Path
from validate_prioritisation import (
    PrioritisationResult,
    _load_prioritisation_priorities,
    _is_discovery_initiative,
    _is_active_initiative,
    _normalize_teams_involved,
    _filter_excluded_teams,
    _get_team_epics_rag_statuses,
    _get_team_epics_data,
    _is_team_committed,
    _is_team_committed_with_epics,
    _build_commitment_matrix,
    _detect_priority_conflicts,
    _detect_missing_commitments,
    _build_initiative_health,
    _check_data_quality,
    _load_team_managers,
    _load_signed_off_initiatives,
    _validate_slack_config,
    extract_prioritisation_actions,
    validate_prioritisation
)


# ============================================================================
# Config Loading Tests
# ============================================================================

def test_load_prioritisation_priorities_valid(tmp_path):
    """Test loading valid priority config."""
    config_file = tmp_path / "priorities.yaml"
    config_file.write_text("""
priorities:
  - INIT-1234
  - INIT-5678
  - INIT-9012
""")

    config = _load_prioritisation_priorities(config_file)

    assert config['priorities'] == ["INIT-1234", "INIT-5678", "INIT-9012"]


def test_load_prioritisation_priorities_missing_file():
    """Test loading config from missing file raises ValueError."""
    with pytest.raises(ValueError, match="Priority config not found"):
        _load_prioritisation_priorities(Path("/nonexistent/config.yaml"))


def test_load_prioritisation_priorities_invalid_yaml(tmp_path):
    """Test loading invalid YAML raises ValueError."""
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text("invalid: yaml: content:")

    with pytest.raises(ValueError, match="Invalid YAML"):
        _load_prioritisation_priorities(config_file)


def test_load_prioritisation_priorities_missing_priorities_key(tmp_path):
    """Test loading config without 'priorities' key raises ValueError."""
    config_file = tmp_path / "no_priorities.yaml"
    config_file.write_text("other_key: value")

    with pytest.raises(ValueError, match="missing 'priorities' key"):
        _load_prioritisation_priorities(config_file)


def test_load_prioritisation_priorities_empty_list(tmp_path):
    """Test loading config with empty priorities list raises ValueError."""
    config_file = tmp_path / "empty.yaml"
    config_file.write_text("priorities: []")

    with pytest.raises(ValueError, match="non-empty list"):
        _load_prioritisation_priorities(config_file)


# ============================================================================
# Filtering Tests
# ============================================================================

def test_is_discovery_initiative():
    """Test Discovery initiative detection."""
    assert _is_discovery_initiative({"summary": "[Discovery] Research Project"})
    assert not _is_discovery_initiative({"summary": "Regular Initiative"})
    assert not _is_discovery_initiative({"summary": "Discovery (not at start)"})
    assert not _is_discovery_initiative({"summary": ""})



def test_is_active_initiative():
    """Test active initiative detection."""
    assert _is_active_initiative({"status": "In Progress"})
    assert _is_active_initiative({"status": "Proposed"})
    assert _is_active_initiative({"status": "Planned"})
    assert not _is_active_initiative({"status": "Done"})
    assert not _is_active_initiative({"status": "Cancelled"})
    # Empty status is treated as active (not explicitly Done/Cancelled)
    assert _is_active_initiative({"status": ""})


def test_normalize_teams_involved():
    """Test teams_involved normalization."""
    # None
    assert _normalize_teams_involved(None) == []

    # Empty list
    assert _normalize_teams_involved([]) == []

    # List of teams
    assert _normalize_teams_involved(["Team A", "Team B"]) == ["Team A", "Team B"]

    # Comma-separated string
    assert _normalize_teams_involved("Team A, Team B, Team C") == ["Team A", "Team B", "Team C"]

    # String with extra whitespace
    assert _normalize_teams_involved("Team A,  Team B  , Team C") == ["Team A", "Team B", "Team C"]

    # Empty string
    assert _normalize_teams_involved("") == []

    # Unexpected type (should return empty list)
    assert _normalize_teams_involved(123) == []


def test_filter_excluded_teams():
    """Test filtering out excluded teams from a list."""
    # No exclusions
    assert _filter_excluded_teams(["Team A", "Team B", "Team C"], []) == ["Team A", "Team B", "Team C"]

    # Exclude one team
    assert _filter_excluded_teams(["Team A", "Team B", "Team C"], ["Team B"]) == ["Team A", "Team C"]

    # Exclude multiple teams
    assert _filter_excluded_teams(["Team A", "Team B", "Team C", "Team D"], ["Team B", "Team D"]) == ["Team A", "Team C"]

    # Exclude all teams
    assert _filter_excluded_teams(["Team A", "Team B"], ["Team A", "Team B"]) == []

    # Empty team list
    assert _filter_excluded_teams([], ["Team A"]) == []

    # Exclusion list has teams not in team list (should be ignored)
    assert _filter_excluded_teams(["Team A"], ["Team B", "Team C"]) == ["Team A"]


# ============================================================================
# Commitment Logic Tests
# ============================================================================

def test_get_team_epics_rag_statuses():
    """Test extracting RAG statuses for a team's epics."""
    initiative = {
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [
                    {"key": "TEAM1-1", "rag_status": "🟢"},
                    {"key": "TEAM1-2", "rag_status": "🟡"}
                ]
            },
            {
                "team_project_key": "TEAM2",
                "epics": [
                    {"key": "TEAM2-1", "rag_status": "🔴"}
                ]
            }
        ]
    }

    assert _get_team_epics_rag_statuses(initiative, "TEAM1") == ["🟢", "🟡"]
    assert _get_team_epics_rag_statuses(initiative, "TEAM2") == ["🔴"]
    assert _get_team_epics_rag_statuses(initiative, "TEAM3") == []


def test_is_team_committed_all_green():
    """Test commitment with all green epics."""
    assert _is_team_committed(["🟢", "🟢"]) is True


def test_is_team_committed_green_and_yellow():
    """Test commitment with green and yellow epics."""
    assert _is_team_committed(["🟢", "🟡"]) is True


def test_is_team_committed_all_yellow():
    """Test commitment with all yellow epics."""
    assert _is_team_committed(["🟡", "🟡"]) is True


def test_is_team_committed_with_amber():
    """Test commitment with amber epic."""
    assert _is_team_committed(["🟢", "⚠️"]) is True


def test_is_team_committed_with_red():
    """Test NOT committed when any epic is red."""
    assert _is_team_committed(["🟢", "🔴"]) is False
    assert _is_team_committed(["🔴"]) is False


def test_is_team_committed_with_none():
    """Test NOT committed when any RAG is None."""
    assert _is_team_committed(["🟢", None]) is False
    assert _is_team_committed([None]) is False


def test_is_team_committed_no_epics():
    """Test NOT committed when no epics."""
    assert _is_team_committed([]) is False


def test_is_team_committed_all_non_red():
    """Test commitment requires ALL epics non-red (conservative)."""
    # All good
    assert _is_team_committed(["🟢", "🟡", "⚠️"]) is True

    # One red fails
    assert _is_team_committed(["🟢", "🟡", "🔴"]) is False

    # One None fails
    assert _is_team_committed(["🟢", "🟡", None]) is False


def test_is_team_committed_with_epics_done_status():
    """Test commitment with Done epics (work already completed)."""
    # Epic with Done status counts as committed, even if RAG is red
    assert _is_team_committed_with_epics([
        {"rag_status": "🔴", "status": "Done"}
    ]) is True

    # Epic with Done status and green RAG
    assert _is_team_committed_with_epics([
        {"rag_status": "🟢", "status": "Done"}
    ]) is True

    # Mix of Done and active green epics
    assert _is_team_committed_with_epics([
        {"rag_status": "🟢", "status": "Done"},
        {"rag_status": "🟢", "status": "In Progress"}
    ]) is True

    # Done epic with red RAG is OK (already completed)
    assert _is_team_committed_with_epics([
        {"rag_status": "🔴", "status": "Done"}
    ]) is True


def test_is_team_committed_with_epics_active_must_be_non_red():
    """Test active (non-Done) epics must still be non-red."""
    # Active red epic - not committed
    assert _is_team_committed_with_epics([
        {"rag_status": "🔴", "status": "In Progress"}
    ]) is False

    # Mix of Done and active red - not committed (active is red)
    assert _is_team_committed_with_epics([
        {"rag_status": "🟢", "status": "Done"},
        {"rag_status": "🔴", "status": "In Progress"}
    ]) is False

    # All Done - committed
    assert _is_team_committed_with_epics([
        {"rag_status": "🔴", "status": "Done"},
        {"rag_status": "🔴", "status": "Done"}
    ]) is True


def test_is_team_committed_with_epics_no_epics():
    """Test not committed when no epics."""
    assert _is_team_committed_with_epics([]) is False


def test_get_team_epics_data():
    """Test extracting full epic data for a team."""
    initiative = {
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [
                    {"key": "TEAM1-1", "rag_status": "🟢", "status": "In Progress"},
                    {"key": "TEAM1-2", "rag_status": "🔴", "status": "Done"}
                ]
            }
        ]
    }

    epics = _get_team_epics_data(initiative, "TEAM1")
    assert len(epics) == 2
    assert epics[0]["key"] == "TEAM1-1"
    assert epics[0]["status"] == "In Progress"
    assert epics[1]["key"] == "TEAM1-2"
    assert epics[1]["status"] == "Done"


# ============================================================================
# Commitment Matrix Tests
# ============================================================================

def test_build_commitment_matrix():
    """Test building commitment matrix."""
    initiatives = [
        {
            "key": "INIT-1",
            "summary": "Initiative 1",
            "teams_involved": ["Team A", "Team B"],
            "contributing_teams": [
                {
                    "team_project_key": "TEAMA",
                    "epics": [{"rag_status": "🟢"}]
                }
            ]
        },
        {
            "key": "INIT-2",
            "summary": "Initiative 2",
            "teams_involved": ["Team A"],
            "contributing_teams": [
                {
                    "team_project_key": "TEAMA",
                    "epics": [{"rag_status": "🔴"}]
                }
            ]
        }
    ]

    priorities = ["INIT-1", "INIT-2"]
    team_mappings = {"Team A": "TEAMA", "Team B": "TEAMB"}
    reverse_mappings = {"TEAMA": "Team A", "TEAMB": "Team B"}

    matrix = _build_commitment_matrix(initiatives, priorities, team_mappings, reverse_mappings, [])

    # Team A should be in matrix
    assert "TEAMA" in matrix
    assert matrix["TEAMA"]["team_display"] == "Team A"

    # Team A committed to INIT-1 (green) but not INIT-2 (red)
    assert len(matrix["TEAMA"]["committed_initiatives"]) == 1
    assert matrix["TEAMA"]["committed_initiatives"][0]["key"] == "INIT-1"

    # Team A expected in both initiatives
    assert len(matrix["TEAMA"]["expected_initiatives"]) == 2

    # Team B expected in INIT-1 but not committed (no epics)
    assert "TEAMB" in matrix
    assert len(matrix["TEAMB"]["expected_initiatives"]) == 1
    assert len(matrix["TEAMB"]["committed_initiatives"]) == 0


def test_build_commitment_matrix_skips_unlisted_initiatives():
    """Test matrix only includes initiatives in priority list."""
    initiatives = [
        {
            "key": "INIT-1",
            "summary": "In priority list",
            "teams_involved": ["Team A"],
            "contributing_teams": []
        },
        {
            "key": "INIT-999",
            "summary": "Not in priority list",
            "teams_involved": ["Team A"],
            "contributing_teams": []
        }
    ]

    priorities = ["INIT-1"]
    team_mappings = {"Team A": "TEAMA"}
    reverse_mappings = {"TEAMA": "Team A"}

    matrix = _build_commitment_matrix(initiatives, priorities, team_mappings, reverse_mappings, [])

    # Team A should only have INIT-1 in expected initiatives
    assert len(matrix["TEAMA"]["expected_initiatives"]) == 1
    assert matrix["TEAMA"]["expected_initiatives"][0]["key"] == "INIT-1"


def test_build_commitment_matrix_excludes_teams():
    """Test that excluded teams are not included in matrix."""
    initiatives = [
        {
            "key": "INIT-1",
            "summary": "Initiative 1",
            "teams_involved": ["Team A", "DevOps", "XD"],
            "contributing_teams": [
                {"team_project_key": "TEAMA", "epics": [{"rag_status": "🟢"}]},
                {"team_project_key": "DEVOPS", "epics": [{"rag_status": "🟢"}]},
                {"team_project_key": "XD", "epics": [{"rag_status": "🟢"}]}
            ]
        }
    ]

    priorities = ["INIT-1"]
    team_mappings = {"Team A": "TEAMA", "DevOps": "DEVOPS", "XD": "XD"}
    reverse_mappings = {"TEAMA": "Team A", "DEVOPS": "DevOps", "XD": "XD"}
    excluded_teams = ["DevOps", "XD"]

    matrix = _build_commitment_matrix(initiatives, priorities, team_mappings, reverse_mappings, excluded_teams)

    # Only Team A should be in matrix
    assert "TEAMA" in matrix
    assert "DEVOPS" not in matrix
    assert "XD" not in matrix


# ============================================================================
# Conflict Detection Tests
# ============================================================================

def test_detect_priority_conflicts_basic():
    """Test detecting basic priority conflict."""
    # Team committed to #3 but not #1 or #2
    matrix = {
        "TEAM1": {
            "team_display": "Team 1",
            "committed_initiatives": [
                {"key": "INIT-3", "title": "Init 3", "priority_index": 2}
            ],
            "expected_initiatives": [
                {"key": "INIT-1", "title": "Init 1", "priority_index": 0, "is_committed": False},
                {"key": "INIT-2", "title": "Init 2", "priority_index": 1, "is_committed": False},
                {"key": "INIT-3", "title": "Init 3", "priority_index": 2, "is_committed": True}
            ]
        }
    }

    priorities = ["INIT-1", "INIT-2", "INIT-3"]
    conflicts = _detect_priority_conflicts(matrix, priorities)

    assert len(conflicts) == 1
    assert conflicts[0]["team_key"] == "TEAM1"
    assert len(conflicts[0]["missing_higher_priorities"]) == 2
    assert conflicts[0]["missing_higher_priorities"][0]["key"] == "INIT-1"
    assert conflicts[0]["missing_higher_priorities"][1]["key"] == "INIT-2"


def test_detect_priority_conflicts_no_conflict():
    """Test no conflict when team respects priorities."""
    # Team committed to #1 and #2, not #3 - no conflict
    matrix = {
        "TEAM1": {
            "team_display": "Team 1",
            "committed_initiatives": [
                {"key": "INIT-1", "title": "Init 1", "priority_index": 0},
                {"key": "INIT-2", "title": "Init 2", "priority_index": 1}
            ],
            "expected_initiatives": [
                {"key": "INIT-1", "title": "Init 1", "priority_index": 0, "is_committed": True},
                {"key": "INIT-2", "title": "Init 2", "priority_index": 1, "is_committed": True},
                {"key": "INIT-3", "title": "Init 3", "priority_index": 2, "is_committed": False}
            ]
        }
    }

    priorities = ["INIT-1", "INIT-2", "INIT-3"]
    conflicts = _detect_priority_conflicts(matrix, priorities)

    assert len(conflicts) == 0


def test_detect_priority_conflicts_no_commitments():
    """Test no conflict when team has no commitments."""
    matrix = {
        "TEAM1": {
            "team_display": "Team 1",
            "committed_initiatives": [],
            "expected_initiatives": [
                {"key": "INIT-1", "title": "Init 1", "priority_index": 0, "is_committed": False}
            ]
        }
    }

    priorities = ["INIT-1"]
    conflicts = _detect_priority_conflicts(matrix, priorities)

    assert len(conflicts) == 0  # Missing commitments, not conflicts


def test_detect_missing_commitments_basic():
    """Test detecting teams with no commitments."""
    matrix = {
        "TEAM1": {
            "team_display": "Team 1",
            "team_key": "TEAM1",
            "committed_initiatives": [],
            "expected_initiatives": [
                {
                    "key": "INIT-1",
                    "title": "Init 1",
                    "is_committed": False,
                    "rag_statuses": [],
                    "epic_keys": []
                },
                {
                    "key": "INIT-2",
                    "title": "Init 2",
                    "is_committed": False,
                    "rag_statuses": [None],
                    "epic_keys": ["TEAM1-123"]
                }
            ]
        },
        "TEAM2": {
            "team_display": "Team 2",
            "team_key": "TEAM2",
            "committed_initiatives": [
                {"key": "INIT-1", "title": "Init 1"}
            ],
            "expected_initiatives": [
                {
                    "key": "INIT-1",
                    "title": "Init 1",
                    "is_committed": True,
                    "rag_statuses": ["🟢"],
                    "epic_keys": ["TEAM2-456"]
                }
            ]
        }
    }

    missing = _detect_missing_commitments(matrix)

    assert len(missing) == 1
    assert missing[0]["team_key"] == "TEAM1"
    assert len(missing[0]["issues"]) == 2
    # First issue: no epic
    assert missing[0]["issues"][0]["key"] == "INIT-1"
    assert missing[0]["issues"][0]["reason"] == "no_epic"
    assert missing[0]["issues"][0]["epic_key"] is None
    # Second issue: missing RAG
    assert missing[0]["issues"][1]["key"] == "INIT-2"
    assert missing[0]["issues"][1]["reason"] == "missing_rag"
    assert missing[0]["issues"][1]["epic_key"] == "TEAM1-123"


# ============================================================================
# Initiative Health Tests
# ============================================================================

def test_build_initiative_health():
    """Test building initiative health dashboard."""
    initiatives = [
        {
            "key": "INIT-1",
            "summary": "Initiative 1",
            "teams_involved": ["Team A", "Team B", "Team C"],
            "contributing_teams": [
                {
                    "team_project_key": "TEAMA",
                    "epics": [{"rag_status": "🟢", "status": "In Progress"}]
                },
                {
                    "team_project_key": "TEAMC",
                    "epics": [{"rag_status": "🟢", "status": "Done"}]
                }
            ]
        }
    ]

    priorities = ["INIT-1"]
    team_mappings = {"Team A": "TEAMA", "Team B": "TEAMB", "Team C": "TEAMC"}

    health = _build_initiative_health(initiatives, priorities, team_mappings, [])

    assert len(health) == 1
    assert health[0]["key"] == "INIT-1"
    assert health[0]["priority"] == 1  # 1-indexed
    assert health[0]["expected_teams"] == ["Team A", "Team B", "Team C"]

    # Team A is active (In Progress)
    assert len(health[0]["active_teams"]) == 1
    assert health[0]["active_teams"][0]["team"] == "Team A"
    assert health[0]["active_teams"][0]["completed"] is False

    # Team C is completed (Done)
    assert len(health[0]["completed_teams"]) == 1
    assert health[0]["completed_teams"][0]["team"] == "Team C"
    assert health[0]["completed_teams"][0]["completed"] is True

    # Team B is missing (no epic)
    assert len(health[0]["missing_teams"]) == 1
    assert health[0]["missing_teams"][0]["team"] == "Team B"
    assert health[0]["missing_teams"][0]["reason"] == "no_epic"


def test_build_initiative_health_sorted_by_priority():
    """Test health dashboard is sorted by priority."""
    initiatives = [
        {"key": "INIT-2", "summary": "Low priority", "teams_involved": [], "contributing_teams": []},
        {"key": "INIT-1", "summary": "High priority", "teams_involved": [], "contributing_teams": []}
    ]

    priorities = ["INIT-1", "INIT-2"]
    team_mappings = {}

    health = _build_initiative_health(initiatives, priorities, team_mappings, [])

    assert health[0]["key"] == "INIT-1"
    assert health[0]["priority"] == 1
    assert health[1]["key"] == "INIT-2"
    assert health[1]["priority"] == 2


# ============================================================================
# Data Quality Tests
# ============================================================================

def test_check_data_quality_missing_teams_involved():
    """Test detecting missing teams_involved (now part of comprehensive validation)."""
    initiatives = [
        {"key": "INIT-1", "teams_involved": None},
        {"key": "INIT-2", "teams_involved": []},
        {"key": "INIT-3", "teams_involved": ["Team A"]}
    ]

    priorities = ["INIT-1", "INIT-2", "INIT-3"]
    issues = _check_data_quality(initiatives, priorities)

    # New structure: data_quality_issues contains comprehensive validation results
    # All 3 initiatives have data quality issues (missing owner_team, strategic_objective)
    assert len(issues["data_quality_issues"]) == 3

    # Find initiatives with missing_teams_involved
    initiatives_with_missing_teams = [
        item for item in issues["data_quality_issues"]
        if any(iss.type == "missing_teams_involved" for iss in item["issues"])
    ]

    # Only INIT-1 and INIT-2 have missing teams_involved
    assert len(initiatives_with_missing_teams) == 2
    assert initiatives_with_missing_teams[0]["key"] == "INIT-1"
    assert initiatives_with_missing_teams[1]["key"] == "INIT-2"


def test_check_data_quality_unlisted_initiatives():
    """Test detecting unlisted initiatives."""
    initiatives = [
        {"key": "INIT-1"},
        {"key": "INIT-2"},
        {"key": "INIT-999"}
    ]

    priorities = ["INIT-1", "INIT-2"]
    issues = _check_data_quality(initiatives, priorities)

    assert len(issues["unlisted_initiatives"]) == 1
    assert issues["unlisted_initiatives"][0]["key"] == "INIT-999"


# ============================================================================
# Team Managers Tests
# ============================================================================

def test_load_team_managers_dict_format(tmp_path, monkeypatch):
    """Test loading team managers with new dict format."""
    # Create config directory and file
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "team_mappings.yaml"
    config_file.write_text("""
team_managers:
  TEAM1:
    notion_handle: "@Manager A"
    slack_id: "U123"
  TEAM2:
    notion_handle: "@Manager B"
    slack_id: "U456"
""")

    # Patch __file__ to point to tmp_path
    import validate_prioritisation
    monkeypatch.setattr(validate_prioritisation, '__file__', str(tmp_path / "validate_prioritisation.py"))

    managers = _load_team_managers()

    assert managers["TEAM1"]["notion_handle"] == "@Manager A"
    assert managers["TEAM1"]["slack_id"] == "U123"


def test_load_team_managers_legacy_string_format(tmp_path, monkeypatch):
    """Test loading team managers with legacy string format."""
    # Create config directory and file
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "team_mappings.yaml"
    config_file.write_text("""
team_managers:
  TEAM1: "@Manager A"
  TEAM2: "@Manager B"
""")

    import validate_prioritisation
    monkeypatch.setattr(validate_prioritisation, '__file__', str(tmp_path / "validate_prioritisation.py"))

    managers = _load_team_managers()

    assert managers["TEAM1"]["notion_handle"] == "@Manager A"
    assert managers["TEAM1"]["slack_id"] is None


def test_validate_slack_config_all_present():
    """Test Slack config validation passes when all IDs present."""
    team_managers = {
        "TEAM1": {"slack_id": "U123"},
        "TEAM2": {"slack_id": "U456"}
    }

    # Should not raise
    _validate_slack_config(team_managers)


def test_validate_slack_config_missing_ids():
    """Test Slack config validation fails when IDs missing."""
    team_managers = {
        "TEAM1": {"slack_id": "U123"},
        "TEAM2": {"slack_id": None},
        "TEAM3": {}
    }

    with pytest.raises(ValueError, match="Missing Slack IDs"):
        _validate_slack_config(team_managers)


# ============================================================================
# Action Item Extraction Tests
# ============================================================================

def test_extract_prioritisation_actions_priority_conflicts():
    """Test extracting action items from priority conflicts."""
    result = PrioritisationResult(
        priority_conflicts=[
            {
                "team_key": "TEAM1",
                "team_display": "Team 1",
                "committed_to": [],
                "missing_higher_priorities": [
                    {"key": "INIT-1", "title": "Init 1", "priority": 1}
                ]
            }
        ],
        missing_commitments=[],
        initiative_health=[],
        data_quality_issues=[],
        unlisted_initiatives=[],
        metadata={}
    )

    team_managers = {
        "TEAM1": {"notion_handle": "@Manager", "slack_id": "U123"}
    }
    reverse_mappings = {}

    actions = extract_prioritisation_actions(result, team_managers, reverse_mappings)

    assert len(actions) == 1
    assert actions[0]["action_type"] == "priority_conflict"
    assert actions[0]["responsible_team_key"] == "TEAM1"
    assert actions[0]["initiative_key"] == "INIT-1"


def test_extract_prioritisation_actions_missing_commitments():
    """Test extracting action items from missing commitments."""
    result = PrioritisationResult(
        priority_conflicts=[],
        missing_commitments=[
            {
                "team_key": "TEAM1",
                "team_display": "Team 1",
                "issues": [
                    {
                        "key": "INIT-1",
                        "title": "Init 1",
                        "reason": "no_epic",
                        "epic_key": None
                    },
                    {
                        "key": "INIT-2",
                        "title": "Init 2",
                        "reason": "missing_rag",
                        "epic_key": "TEAM1-123"
                    }
                ]
            }
        ],
        initiative_health=[],
        data_quality_issues=[],
        unlisted_initiatives=[],
        metadata={}
    )

    team_managers = {
        "TEAM1": {"notion_handle": "@Manager", "slack_id": "U123"}
    }
    reverse_mappings = {}

    actions = extract_prioritisation_actions(result, team_managers, reverse_mappings)

    assert len(actions) == 2
    # First action: no epic
    assert actions[0]["action_type"] == "missing_epic"
    assert actions[0]["initiative_key"] == "INIT-1"
    assert "Create epic" in actions[0]["description"]
    # Second action: missing RAG
    assert actions[1]["action_type"] == "missing_rag"
    assert actions[1]["initiative_key"] == "INIT-2"
    assert "Set RAG status" in actions[1]["description"]
    assert actions[1]["epic_key"] == "TEAM1-123"


# ============================================================================
# Integration Tests
# ============================================================================

def test_validate_prioritisation_end_to_end(tmp_path, monkeypatch):
    """Test end-to-end validation with sample data."""
    # Create config
    config_file = tmp_path / "priorities.yaml"
    config_file.write_text("""
priorities:
  - INIT-1
  - INIT-2
""")

    # Create data file
    data_file = tmp_path / "data.json"
    data = {
        "initiatives": [
            {
                "key": "INIT-1",
                "summary": "High Priority Initiative",
                "owner_team": "Tech Leadership",
                "status": "In Progress",
                "teams_involved": ["Team A", "Team B"],
                "contributing_teams": [
                    {
                        "team_project_key": "TEAMA",
                        "epics": [{"rag_status": "🔴"}]
                    }
                ]
            },
            {
                "key": "INIT-2",
                "summary": "Low Priority Initiative",
                "owner_team": "Tech Leadership",
                "status": "In Progress",
                "teams_involved": ["Team A"],
                "contributing_teams": [
                    {
                        "team_project_key": "TEAMA",
                        "epics": [{"rag_status": "🟢"}]
                    }
                ]
            },
            {
                "key": "INIT-3",
                "summary": "Done Initiative",
                "owner_team": "Tech Leadership",
                "status": "Done",
                "teams_involved": [],
                "contributing_teams": []
            },
            {
                "key": "INIT-4",
                "summary": "[Discovery] Research",
                "owner_team": "Tech Leadership",
                "status": "In Progress",
                "teams_involved": [],
                "contributing_teams": []
            }
        ]
    }
    data_file.write_text(json.dumps(data))

    # Create config directory and team mappings
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    mappings_file = config_dir / "team_mappings.yaml"
    mappings_file.write_text("""
team_mappings:
  "Team A": "TEAMA"
  "Team B": "TEAMB"
""")

    # Patch config location
    import validate_prioritisation as vtl_module
    monkeypatch.setattr(vtl_module, '__file__', str(tmp_path / "validate_prioritisation.py"))

    # Import the function with a different name to avoid conflict
    from validate_prioritisation import validate_prioritisation as validate_fn

    # Run validation
    result = validate_fn(data_file, config_file)

    # Assertions
    assert result.metadata["total_initiatives"] == 4
    assert result.metadata["active_initiatives"] == 3  # Excludes Done
    assert result.metadata["validated_initiatives"] == 2  # Excludes Done and Discovery, only configured initiatives

    # Priority conflict: Team A committed to INIT-2 (priority #2) but not INIT-1 (priority #1)
    assert len(result.priority_conflicts) == 1
    assert result.priority_conflicts[0]["team_display"] == "Team A"

    # Missing commitment: Team B expected in INIT-1 but has no epics
    assert len(result.missing_commitments) == 1
    assert result.missing_commitments[0]["team_display"] == "Team B"


# ============================================================================
# Signed-Off Initiatives Tests
# ============================================================================

def test_load_signed_off_initiatives_returns_set():
    """Test that _load_signed_off_initiatives returns a set."""
    # The function should always return a set (empty if file missing, populated if exists)
    keys = _load_signed_off_initiatives()
    assert isinstance(keys, set)
    # Each item should be a string (initiative key)
    for key in keys:
        assert isinstance(key, str)
        assert key.startswith('INIT-')


def test_signed_off_initiative_filtered_out(tmp_path, monkeypatch):
    """Test that signed-off initiatives are completely filtered out."""
    # Create priority config
    config_file = tmp_path / "priorities.yaml"
    config_file.write_text("""
priorities:
  - INIT-1234
  - INIT-5678
""")

    # Create test data with signed-off initiative
    data_file = tmp_path / "test_data.json"
    data = {
        'initiatives': [
            {
                'key': 'INIT-1234',
                'summary': 'Signed Off Initiative',
                'owner_team': 'Team A',
                'status': 'Proposed',
                'teams_involved': ['Team A', 'Team B'],
                'contributing_teams': []
            },
            {
                'key': 'INIT-5678',
                'summary': 'Normal Initiative',
                'owner_team': 'Team A',
                'status': 'Proposed',
                'teams_involved': ['Team A'],
                'contributing_teams': []
            }
        ]
    }
    data_file.write_text(json.dumps(data))

    # Setup config directory in tmp_path
    test_config_dir = tmp_path / "config"
    test_config_dir.mkdir()

    # Write team mappings
    mappings_file = test_config_dir / "team_mappings.yaml"
    mappings_file.write_text("""
team_mappings:
  "Team A": "TEAMA"
  "Team B": "TEAMB"
""")

    # Write initiative exceptions with signed-off initiative
    exceptions_file = test_config_dir / "initiative_exceptions.yaml"
    config_data = {
        'signed_off_initiatives': [
            {'key': 'INIT-1234', 'reason': 'Manager approved', 'date': '2026-04-01', 'approved_by': '@Manager'}
        ]
    }
    with open(exceptions_file, 'w') as f:
        yaml.dump(config_data, f)

    # Patch config location
    import validate_prioritisation as vtl_module
    monkeypatch.setattr(vtl_module, '__file__', str(tmp_path / "validate_prioritisation.py"))

    # Run validation
    from validate_prioritisation import validate_prioritisation as validate_fn
    result = validate_fn(data_file, config_file)

    # Verify signed-off initiative is filtered out
    # total_initiatives is counted AFTER filtering signed-off initiatives
    assert result.metadata['total_initiatives'] == 1
    # After filtering signed-off, only 1 initiative remains, and it's active and non-discovery
    assert result.metadata['active_initiatives'] == 1
    assert result.metadata['validated_initiatives'] == 1

    # Verify INIT-1234 is not in any results
    all_keys = set()
    for init in result.initiative_health:
        all_keys.add(init['key'])
    for conflict in result.priority_conflicts:
        for committed in conflict.get('committed_to', []):
            all_keys.add(committed['key'])
    for missing in result.missing_commitments:
        for issue in missing.get('issues', []):
            all_keys.add(issue['key'])

    assert 'INIT-1234' not in all_keys
    assert 'INIT-5678' in all_keys


def test_mixed_signed_off_and_normal_initiatives(tmp_path, monkeypatch):
    """Test that only signed-off initiatives are filtered."""
    # Create priority config with three initiatives
    config_file = tmp_path / "priorities.yaml"
    config_file.write_text("""
priorities:
  - INIT-1111
  - INIT-2222
  - INIT-3333
""")

    # Create test data
    data_file = tmp_path / "test_data.json"
    data = {
        'initiatives': [
            {
                'key': 'INIT-1111',
                'summary': 'Signed Off',
                'owner_team': 'Team A',
                'status': 'Proposed',
                'teams_involved': ['Team A'],
                'contributing_teams': []
            },
            {
                'key': 'INIT-2222',
                'summary': 'Normal Initiative 1',
                'owner_team': 'Team B',
                'status': 'Proposed',
                'teams_involved': ['Team B'],
                'contributing_teams': []
            },
            {
                'key': 'INIT-3333',
                'summary': 'Normal Initiative 2',
                'owner_team': 'Team C',
                'status': 'Proposed',
                'teams_involved': ['Team C'],
                'contributing_teams': []
            }
        ]
    }
    data_file.write_text(json.dumps(data))

    # Setup config directory
    test_config_dir = tmp_path / "config"
    test_config_dir.mkdir()

    # Write team mappings
    mappings_file = test_config_dir / "team_mappings.yaml"
    mappings_file.write_text("""
team_mappings:
  "Team A": "TEAMA"
  "Team B": "TEAMB"
  "Team C": "TEAMC"
""")

    # Write initiative exceptions with one signed-off initiative
    exceptions_file = test_config_dir / "initiative_exceptions.yaml"
    config_data = {
        'signed_off_initiatives': [
            {'key': 'INIT-1111', 'reason': 'Approved', 'date': '2026-04-01', 'approved_by': '@Manager'}
        ]
    }
    with open(exceptions_file, 'w') as f:
        yaml.dump(config_data, f)

    # Patch config location
    import validate_prioritisation as vtl_module
    monkeypatch.setattr(vtl_module, '__file__', str(tmp_path / "validate_prioritisation.py"))

    # Run validation
    from validate_prioritisation import validate_prioritisation as validate_fn
    result = validate_fn(data_file, config_file)

    # Verify counts (total_initiatives is counted AFTER filtering signed-off)
    assert result.metadata['total_initiatives'] == 2
    assert result.metadata['active_initiatives'] == 2  # INIT-1111 filtered out
    assert result.metadata['validated_initiatives'] == 2  # Only INIT-2222 and INIT-3333

    # Verify INIT-1111 is filtered but others are not
    all_keys = set()
    for init in result.initiative_health:
        all_keys.add(init['key'])

    assert 'INIT-1111' not in all_keys
    assert 'INIT-2222' in all_keys
    assert 'INIT-3333' in all_keys


# ============================================================================
# Owner Team Exemption Tests
# ============================================================================

def test_owner_team_not_required_to_commit(tmp_path, monkeypatch):
    """Test that owner teams are not required to create epics for their own initiatives."""
    # Create priority config
    config_file = tmp_path / "priorities.yaml"
    config_file.write_text("""
priorities:
  - INIT-1
""")

    # Create test data where owner team is in teams_involved but has no epic
    data_file = tmp_path / "test_data.json"
    data = {
        'initiatives': [
            {
                'key': 'INIT-1',
                'summary': 'Test Initiative',
                'owner_team': 'Team A',  # Owner team
                'status': 'In Progress',
                'teams_involved': ['Team A', 'Team B'],  # Owner team is involved
                'contributing_teams': [
                    {
                        'team_project_key': 'TEAMB',
                        'epics': [{'key': 'TEAMB-1', 'rag_status': '🟢', 'status': 'In Progress'}]
                    }
                    # Team A (owner) has NO epic - this should be OK
                ]
            }
        ]
    }
    data_file.write_text(json.dumps(data))

    # Setup config
    test_config_dir = tmp_path / "config"
    test_config_dir.mkdir()
    mappings_file = test_config_dir / "team_mappings.yaml"
    mappings_file.write_text("""
team_mappings:
  "Team A": "TEAMA"
  "Team B": "TEAMB"
""")

    # Patch config location
    import validate_prioritisation as vtl_module
    monkeypatch.setattr(vtl_module, '__file__', str(tmp_path / "validate_prioritisation.py"))

    # Run validation
    from validate_prioritisation import validate_prioritisation as validate_fn
    result = validate_fn(data_file, config_file)

    # Team A (owner) should NOT appear in missing commitments
    missing_teams = [missing['team_display'] for missing in result.missing_commitments]
    assert 'Team A' not in missing_teams

    # Team B should have commitment (has green epic)
    # Initiative should be in health dashboard with Team A filtered out
    assert len(result.initiative_health) == 1
    health = result.initiative_health[0]
    assert health['key'] == 'INIT-1'

    # Only Team B should be in expected teams (Team A filtered out as owner)
    assert 'Team B' in [t['team'] for t in health['active_teams']]
    assert 'Team A' not in [t['team'] for t in health['active_teams']]
    assert 'Team A' not in [t['team'] for t in health['missing_teams']]


def test_owner_team_mixed_with_contributing_teams(tmp_path, monkeypatch):
    """Test owner team exemption with multiple contributing teams."""
    # Create priority config
    config_file = tmp_path / "priorities.yaml"
    config_file.write_text("""
priorities:
  - INIT-1
  - INIT-2
""")

    # Create test data
    data_file = tmp_path / "test_data.json"
    data = {
        'initiatives': [
            {
                'key': 'INIT-1',
                'summary': 'Initiative owned by Team A',
                'owner_team': 'Team A',
                'status': 'In Progress',
                'teams_involved': ['Team A', 'Team B', 'Team C'],
                'contributing_teams': [
                    {'team_project_key': 'TEAMB', 'epics': [{'key': 'TEAMB-1', 'rag_status': '🟢', 'status': 'In Progress'}]},
                    {'team_project_key': 'TEAMC', 'epics': [{'key': 'TEAMC-1', 'rag_status': '🟢', 'status': 'In Progress'}]}
                    # Team A has no epic - OK since they're the owner
                ]
            },
            {
                'key': 'INIT-2',
                'summary': 'Initiative owned by Team B',
                'owner_team': 'Team B',
                'status': 'In Progress',
                'teams_involved': ['Team A', 'Team B'],
                'contributing_teams': [
                    # Team A has no epic - should be flagged
                    # Team B has no epic - OK since they're the owner
                ]
            }
        ]
    }
    data_file.write_text(json.dumps(data))

    # Setup config
    test_config_dir = tmp_path / "config"
    test_config_dir.mkdir()
    mappings_file = test_config_dir / "team_mappings.yaml"
    mappings_file.write_text("""
team_mappings:
  "Team A": "TEAMA"
  "Team B": "TEAMB"
  "Team C": "TEAMC"
""")

    # Patch config location
    import validate_prioritisation as vtl_module
    monkeypatch.setattr(vtl_module, '__file__', str(tmp_path / "validate_prioritisation.py"))

    # Run validation
    from validate_prioritisation import validate_prioritisation as validate_fn
    result = validate_fn(data_file, config_file)

    # INIT-1: Team A (owner) not flagged, Team B and C have commitments
    # INIT-2: Team B (owner) not flagged, Team A should be flagged

    # Only Team A for INIT-2 should be in missing commitments
    assert len(result.missing_commitments) == 1
    missing = result.missing_commitments[0]
    assert missing['team_display'] == 'Team A'
    assert len(missing['issues']) == 1
    assert missing['issues'][0]['key'] == 'INIT-2'


def test_non_owner_team_required_to_commit(tmp_path, monkeypatch):
    """Test that non-owner teams are still required to create epics."""
    # Create priority config
    config_file = tmp_path / "priorities.yaml"
    config_file.write_text("""
priorities:
  - INIT-1
""")

    # Create test data where non-owner team has no epic
    data_file = tmp_path / "test_data.json"
    data = {
        'initiatives': [
            {
                'key': 'INIT-1',
                'summary': 'Test Initiative',
                'owner_team': 'Team A',  # Owner team
                'status': 'In Progress',
                'teams_involved': ['Team A', 'Team B'],
                'contributing_teams': [
                    # Team A (owner) has no epic - OK
                    # Team B (non-owner) has no epic - should be flagged
                ]
            }
        ]
    }
    data_file.write_text(json.dumps(data))

    # Setup config
    test_config_dir = tmp_path / "config"
    test_config_dir.mkdir()
    mappings_file = test_config_dir / "team_mappings.yaml"
    mappings_file.write_text("""
team_mappings:
  "Team A": "TEAMA"
  "Team B": "TEAMB"
""")

    # Patch config location
    import validate_prioritisation as vtl_module
    monkeypatch.setattr(vtl_module, '__file__', str(tmp_path / "validate_prioritisation.py"))

    # Run validation
    from validate_prioritisation import validate_prioritisation as validate_fn
    result = validate_fn(data_file, config_file)

    # Team B should be flagged for missing commitment
    assert len(result.missing_commitments) == 1
    missing = result.missing_commitments[0]
    assert missing['team_display'] == 'Team B'
    assert missing['issues'][0]['reason'] == 'no_epic'
