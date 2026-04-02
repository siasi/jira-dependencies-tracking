"""Tests for initiative status validation script."""

import json
import pytest
import yaml
from pathlib import Path
from validate_planning import (
    ValidationResult,
    validate_initiative_status,
    _check_data_quality,
    _has_red_epics,
    _has_yellow_epics,
    _is_ready_to_plan,
    _is_discovery_initiative,
    _load_teams_excluded_from_analysis,
    _load_team_managers,
    _validate_slack_config,
    _load_signed_off_initiatives,
    extract_manager_actions,
    generate_slack_messages,
    find_latest_extract,
    print_validation_report,
    generate_markdown_report
)


def test_validation_result_has_issues():
    """Test ValidationResult.has_issues property."""
    result = ValidationResult()
    assert not result.has_issues

    result.dependency_mapping.append({'key': 'INIT-1'})
    assert result.has_issues

    result2 = ValidationResult()
    result2.low_confidence_completion.append({'key': 'INIT-2'})
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
        "quarter": "26 Q2",
        "assignee": "user@example.com",
        "strategic_objective": "2026_fuel_regulated",
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
        "quarter": "26 Q2",
        "assignee": "user@example.com",
        "strategic_objective": "2026_fuel_regulated",
        "teams_involved": ["Team A"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "team_project_name": "Team One",
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
    assert len(issues[0]['teams']) == 1
    assert issues[0]['teams'][0]['team_name'] == 'Team One'
    assert issues[0]['teams'][0]['team_key'] == 'TEAM1'
    assert len(issues[0]['teams'][0]['epics']) == 2
    assert issues[0]['teams'][0]['epics'][0]['key'] == 'TEAM1-2'
    assert issues[0]['teams'][0]['epics'][1]['key'] == 'TEAM1-3'


def test_check_data_quality_no_epics():
    """Test data quality check with zero epics (reported as epic_count_mismatch)."""
    initiative = {
        "key": "INIT-789",
        "summary": "Test Initiative",
        "status": "Proposed",
        "quarter": "26 Q2",
        "assignee": "user@example.com",
        "strategic_objective": "2026_fuel_regulated",
        "teams_involved": ["TEAM1", "TEAM2"],
        "contributing_teams": []
    }

    issues = _check_data_quality(initiative)

    assert issues is not None
    assert len(issues) == 1
    assert issues[0]['type'] == 'epic_count_mismatch'
    assert issues[0]['teams_involved'] == ["TEAM1", "TEAM2"]
    assert issues[0]['teams_with_epics'] == []


def test_check_data_quality_missing_strategic_objective():
    """Test data quality check with missing strategic objective."""
    initiative = {
        "key": "INIT-888",
        "summary": "Test Initiative",
        "status": "Proposed",
        "quarter": "26 Q2",
        "assignee": "user@example.com",
        "strategic_objective": None,  # Missing
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [{"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"}]
            }
        ]
    }

    issues = _check_data_quality(initiative)

    assert issues is not None
    assert len(issues) == 1
    assert issues[0]['type'] == 'missing_strategic_objective'


def test_check_data_quality_all_good():
    """Test data quality check with no issues."""
    initiative = {
        "key": "INIT-100",
        "summary": "Test Initiative",
        "status": "Proposed",
        "quarter": "26 Q2",
        "assignee": "user@example.com",
        "strategic_objective": "2026_fuel_regulated",
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


def test_has_red_epics_with_red():
    """Test _has_red_epics with RED epic."""
    initiative = {
        "key": "INIT-200",
        "summary": "Test Initiative",
        "status": "Proposed",
        "quarter": "26 Q2",
        "assignee": "user@example.com",
        "strategic_objective": "2026_fuel_regulated",
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [{"key": "TEAM1-1", "summary": "Blocked Epic", "rag_status": "🔴"}]
            }
        ]
    }

    red_epics = _has_red_epics(initiative)

    assert red_epics is not None
    assert len(red_epics) == 1
    assert red_epics[0]['key'] == 'TEAM1-1'
    assert red_epics[0]['rag_status'] == '🔴'


def test_has_red_epics_with_owner_team():
    """Test _has_red_epics skips owner team epics."""
    initiative = {
        "key": "INIT-400",
        "summary": "Test Initiative",
        "status": "Proposed",
        "quarter": "26 Q2",
        "assignee": "user@example.com",
        "owner_team": "TEAM1",
        "teams_involved": ["TEAM1", "TEAM2"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [{"key": "TEAM1-1", "summary": "Owner Epic RED", "rag_status": "🔴"}]
            },
            {
                "team_project_key": "TEAM2",
                "epics": [{"key": "TEAM2-1", "summary": "Non-owner Epic RED", "rag_status": "🔴"}]
            }
        ]
    }

    red_epics = _has_red_epics(initiative)

    # Should only return TEAM2's epic (non-owner), not TEAM1's (owner)
    assert red_epics is not None
    assert len(red_epics) == 1
    assert red_epics[0]['key'] == 'TEAM2-1'
    assert red_epics[0]['rag_status'] == '🔴'


def test_has_red_epics_none():
    """Test _has_red_epics with no RED epics."""
    initiative = {
        "key": "INIT-600",
        "summary": "Test Initiative",
        "status": "Proposed",
        "quarter": "26 Q2",
        "assignee": "user@example.com",
        "strategic_objective": "2026_fuel_regulated",
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [{"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"}]
            }
        ]
    }

    red_epics = _has_red_epics(initiative)

    assert red_epics is None


def test_has_yellow_epics_with_yellow():
    """Test _has_yellow_epics with YELLOW epic."""
    initiative = {
        "key": "INIT-300",
        "summary": "Test Initiative",
        "status": "Proposed",
        "quarter": "26 Q2",
        "assignee": "user@example.com",
        "strategic_objective": "2026_fuel_regulated",
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [{"key": "TEAM1-1", "summary": "At Risk Epic", "rag_status": "⚠️"}]
            }
        ]
    }

    yellow_epics = _has_yellow_epics(initiative)

    assert yellow_epics is not None
    assert len(yellow_epics) == 1
    assert yellow_epics[0]['key'] == 'TEAM1-1'


def test_has_yellow_epics_none():
    """Test _has_yellow_epics with no YELLOW epics."""
    initiative = {
        "key": "INIT-500",
        "summary": "Test Initiative",
        "status": "Proposed",
        "quarter": "26 Q2",
        "assignee": None,
        "strategic_objective": "2026_fuel_regulated",
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [{"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"}]
            }
        ]
    }

    yellow_epics = _has_yellow_epics(initiative)

    assert yellow_epics is None


def test_is_ready_to_plan_all_criteria_met():
    """Test _is_ready_to_plan with all criteria met."""
    initiative = {
        "key": "INIT-700",
        "summary": "Ready Initiative",
        "status": "Proposed",
        "quarter": "26 Q2",
        "assignee": "user@example.com",
        "strategic_objective": "2026_fuel_regulated",
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
        "quarter": "26 Q2",
        "assignee": "user@example.com",
        "strategic_objective": "2026_fuel_regulated",
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
        "quarter": "26 Q2",
        "assignee": None,
        "strategic_objective": "2026_fuel_regulated",
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
        "quarter": "26 Q2",
        "assignee": "user@example.com",
        "strategic_objective": "2026_fuel_regulated",
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
    """Test _is_ready_to_plan with YELLOW epic (acceptable - low confidence)."""
    initiative = {
        "key": "INIT-1100",
        "summary": "Not All Green",
        "status": "Proposed",
        "quarter": "26 Q2",
        "assignee": "user@example.com",
        "strategic_objective": "2026_fuel_regulated",
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

    # Yellow epics are now acceptable (low confidence but planned)
    assert _is_ready_to_plan(initiative) is True


def test_is_ready_to_plan_with_red_epic():
    """Test _is_ready_to_plan with RED epic (blocks planning)."""
    initiative = {
        "key": "INIT-1101",
        "summary": "Has Red Epic",
        "status": "Proposed",
        "quarter": "26 Q2",
        "assignee": "user@example.com",
        "strategic_objective": "2026_fuel_regulated",
        "teams_involved": ["TEAM1"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM1",
                "epics": [
                    {"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"},
                    {"key": "TEAM1-2", "summary": "Epic 2", "rag_status": "🔴"}
                ]
            }
        ]
    }

    # Red epics block planning
    assert _is_ready_to_plan(initiative) is False


def test_validate_initiative_status_dependency_mapping(tmp_path):
    """Test full validation with data quality issues (Section 1: Dependency Mapping)."""
    data = {
        "initiatives": [{
            "key": "INIT-123",
            "summary": "Test Initiative",
            "status": "Proposed",
            "quarter": "26 Q2",
            "assignee": "user@example.com",
            "strategic_objective": "2026_fuel_regulated",
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

    result = validate_initiative_status(json_file, quarter="26 Q2")

    assert result.total_checked == 1
    assert len(result.dependency_mapping) == 1
    assert result.dependency_mapping[0]['key'] == "INIT-123"
    assert len(result.low_confidence_completion) == 0
    assert len(result.ready_to_plan) == 0


def test_validate_initiative_status_cannot_complete(tmp_path):
    """Test full validation with RED epics (Section 2: Low confidence for completion)."""
    data = {
        "initiatives": [{
            "key": "INIT-456",
            "summary": "Test Initiative",
            "status": "Proposed",
            "quarter": "26 Q2",
            "assignee": "user@example.com",
            "strategic_objective": "2026_fuel_regulated",
            "teams_involved": ["TEAM1", "TEAM2"],
            "contributing_teams": [
                {
                    "team_project_key": "TEAM1",
                    "epics": [{"key": "TEAM1-1", "summary": "Green Epic", "rag_status": "🟢"}]
                },
                {
                    "team_project_key": "TEAM2",
                    "epics": [{"key": "TEAM2-1", "summary": "Blocked Epic", "rag_status": "🔴"}]
                }
            ]
        }]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(data))

    result = validate_initiative_status(json_file, quarter="26 Q2")

    assert result.total_checked == 1
    assert len(result.dependency_mapping) == 0
    assert len(result.low_confidence_completion) == 1
    assert result.low_confidence_completion[0]['key'] == "INIT-456"
    assert len(result.ready_to_plan) == 0


def test_validate_initiative_status_low_confidence(tmp_path):
    """Test full validation with YELLOW epics (Section 2: Low confidence for completion)."""
    data = {
        "initiatives": [{
            "key": "INIT-457",
            "summary": "Test Initiative",
            "status": "Proposed",
            "quarter": "26 Q2",
            "assignee": "user@example.com",
            "strategic_objective": "2026_fuel_regulated",
            "teams_involved": ["TEAM1", "TEAM2"],
            "contributing_teams": [
                {
                    "team_project_key": "TEAM1",
                    "epics": [{"key": "TEAM1-1", "summary": "Green Epic", "rag_status": "🟢"}]
                },
                {
                    "team_project_key": "TEAM2",
                    "epics": [{"key": "TEAM2-1", "summary": "At Risk Epic", "rag_status": "⚠️"}]
                }
            ]
        }]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(data))

    result = validate_initiative_status(json_file, quarter="26 Q2")

    assert result.total_checked == 1
    assert len(result.dependency_mapping) == 0
    assert len(result.low_confidence_completion) == 1
    assert result.low_confidence_completion[0]['key'] == "INIT-457"
    assert len(result.ready_to_plan) == 0


def test_validate_initiative_status_awaiting_owner(tmp_path):
    """Test full validation with missing assignee (Section 1: Dependency Mapping)."""
    data = {
        "initiatives": [{
            "key": "INIT-458",
            "summary": "Test Initiative",
            "status": "Proposed",
            "quarter": "26 Q2",
            "assignee": None,
            "strategic_objective": "2026_fuel_regulated",
            "teams_involved": ["TEAM1", "TEAM2"],
            "contributing_teams": [
                {
                    "team_project_key": "TEAM1",
                    "epics": [{"key": "TEAM1-1", "summary": "Green Epic 1", "rag_status": "🟢"}]
                },
                {
                    "team_project_key": "TEAM2",
                    "epics": [{"key": "TEAM2-1", "summary": "Green Epic 2", "rag_status": "🟢"}]
                }
            ]
        }]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(data))

    result = validate_initiative_status(json_file, quarter="26 Q2")

    assert result.total_checked == 1
    # Missing assignee is now a data quality issue
    assert len(result.dependency_mapping) == 1
    assert result.dependency_mapping[0]['key'] == "INIT-458"
    assert len(result.low_confidence_completion) == 0
    assert len(result.ready_to_plan) == 0


def test_validate_initiative_status_ready_to_plan(tmp_path):
    """Test full validation with ready initiative (Section 3: Ready to Move to Planned)."""
    data = {
        "initiatives": [{
            "key": "INIT-789",
            "summary": "Ready Initiative",
            "status": "Proposed",
            "quarter": "26 Q2",
            "assignee": "user@example.com",
            "strategic_objective": "2026_fuel_regulated",
            "teams_involved": ["TEAM1", "TEAM2"],
            "contributing_teams": [
                {
                    "team_project_key": "TEAM1",
                    "epics": [{"key": "TEAM1-1", "summary": "Green Epic 1", "rag_status": "🟢"}]
                },
                {
                    "team_project_key": "TEAM2",
                    "epics": [{"key": "TEAM2-1", "summary": "Green Epic 2", "rag_status": "🟢"}]
                }
            ]
        }]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(data))

    result = validate_initiative_status(json_file, quarter="26 Q2")

    assert result.total_checked == 1
    assert len(result.dependency_mapping) == 0
    assert len(result.low_confidence_completion) == 0
    assert len(result.ready_to_plan) == 1
    assert result.ready_to_plan[0]['key'] == "INIT-789"


def test_validate_initiative_status_planned_regression(tmp_path):
    """Test full validation with Planned initiative regression."""
    data = {
        "initiatives": [{
            "key": "INIT-999",
            "summary": "Regressed Initiative",
            "status": "Planned",
            "quarter": "26 Q2",
            "assignee": "user@example.com",
            "strategic_objective": "2026_fuel_regulated",
            "teams_involved": ["TEAM1", "TEAM2"],
            "contributing_teams": [
                {
                    "team_project_key": "TEAM1",
                    "epics": [{"key": "TEAM1-1", "summary": "Green Epic", "rag_status": "🟢"}]
                },
                {
                    "team_project_key": "TEAM2",
                    "epics": [{"key": "TEAM2-1", "summary": "Now Red", "rag_status": "🔴"}]
                }
            ]
        }]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(data))

    result = validate_initiative_status(json_file, quarter="26 Q2")

    assert result.total_checked == 1
    assert len(result.dependency_mapping) == 0
    assert len(result.low_confidence_completion) == 0
    assert len(result.ready_to_plan) == 0
    assert len(result.planned_regressions) == 1
    assert result.planned_regressions[0]['key'] == "INIT-999"


def test_validate_initiative_status_planned_for_quarter(tmp_path):
    """Test full validation with healthy Planned initiative (Section 4: Planned for Quarter)."""
    data = {
        "initiatives": [{
            "key": "INIT-1000",
            "summary": "Healthy Planned Initiative",
            "status": "Planned",
            "quarter": "26 Q2",
            "assignee": "user@example.com",
            "strategic_objective": "2026_fuel_regulated",
            "teams_involved": ["TEAM1", "TEAM2"],
            "contributing_teams": [
                {
                    "team_project_key": "TEAM1",
                    "epics": [{"key": "TEAM1-1", "summary": "Green Epic", "rag_status": "🟢"}]
                },
                {
                    "team_project_key": "TEAM2",
                    "epics": [{"key": "TEAM2-1", "summary": "Also Green", "rag_status": "🟢"}]
                }
            ]
        }]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(data))

    result = validate_initiative_status(json_file, quarter="26 Q2")

    assert result.total_checked == 1
    assert len(result.dependency_mapping) == 0
    assert len(result.low_confidence_completion) == 0
    assert len(result.ready_to_plan) == 0
    assert len(result.planned_for_quarter) == 1
    assert result.planned_for_quarter[0]['key'] == "INIT-1000"
    assert len(result.planned_regressions) == 0


def test_load_teams_exempt_from_rag(tmp_path):
    """Test loading teams exempt from RAG checking from team_mappings.yaml."""
    from validate_planning import _load_teams_exempt_from_rag

    # Note: This test will use the actual team_mappings.yaml in the project if it exists
    # For a full test, you would need to mock the file path
    # For now, just verify the function returns a list
    exempt_teams = _load_teams_exempt_from_rag()
    assert isinstance(exempt_teams, list)


def test_validate_initiative_status_mixed_statuses(tmp_path):
    """Test full validation with mixed initiative statuses across all sections."""
    data = {
        "initiatives": [
            {
                "key": "INIT-001",
                "summary": "Data Quality Issue",
                "status": "Proposed",
                "quarter": "26 Q2",
                "assignee": "user@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "teams_involved": ["TEAM1", "TEAM2"],
                "contributing_teams": []
            },
            {
                "key": "INIT-002",
                "summary": "RED Epic",
                "status": "Proposed",
                "quarter": "26 Q2",
                "assignee": "user@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "teams_involved": ["TEAM1", "TEAM2"],
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM1",
                        "epics": [{"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"}]
                    },
                    {
                        "team_project_key": "TEAM2",
                        "epics": [{"key": "TEAM2-1", "summary": "Epic 2", "rag_status": "🔴"}]
                    }
                ]
            },
            {
                "key": "INIT-003",
                "summary": "YELLOW Epic",
                "status": "Proposed",
                "quarter": "26 Q2",
                "assignee": "user@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "teams_involved": ["TEAM1", "TEAM2"],
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM1",
                        "epics": [{"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"}]
                    },
                    {
                        "team_project_key": "TEAM2",
                        "epics": [{"key": "TEAM2-1", "summary": "Epic 2", "rag_status": "⚠️"}]
                    }
                ]
            },
            {
                "key": "INIT-004",
                "summary": "Awaiting Owner",
                "status": "Proposed",
                "quarter": "26 Q2",
                "assignee": None,
                "strategic_objective": "2026_fuel_regulated",
                "teams_involved": ["TEAM1", "TEAM2"],
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
            },
            {
                "key": "INIT-005",
                "summary": "Ready",
                "status": "Proposed",
                "quarter": "26 Q2",
                "assignee": "user@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "teams_involved": ["TEAM1", "TEAM2"],
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
            },
            {
                "key": "INIT-006",
                "summary": "Planned Regression",
                "status": "Planned",
                "quarter": "26 Q2",
                "assignee": "user@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "teams_involved": ["TEAM1", "TEAM2"],
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM1",
                        "epics": [{"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"}]
                    },
                    {
                        "team_project_key": "TEAM2",
                        "epics": [{"key": "TEAM2-1", "summary": "Epic 2", "rag_status": "🔴"}]
                    }
                ]
            }
        ]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(data))

    result = validate_initiative_status(json_file, quarter="26 Q2")

    assert result.total_checked == 6
    # INIT-001 (no epics) and INIT-004 (no assignee) both go to dependency_mapping
    assert len(result.dependency_mapping) == 2
    # INIT-002 (RED) and INIT-003 (YELLOW) both go to low_confidence_completion
    assert len(result.low_confidence_completion) == 2
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
    from validate_planning import _normalize_teams_involved

    assert _normalize_teams_involved(None) == []


def test_normalize_teams_involved_handles_string():
    """Test _normalize_teams_involved handles comma-separated strings."""
    from validate_planning import _normalize_teams_involved

    # Single team
    assert _normalize_teams_involved("Team A") == ["Team A"]

    # Multiple teams
    assert _normalize_teams_involved("Team A, Team B, Team C") == [
        "Team A", "Team B", "Team C"
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
    from validate_planning import _normalize_teams_involved

    # Normal list
    assert _normalize_teams_involved(["Team1", "Team2"]) == ["Team1", "Team2"]

    # Empty list
    assert _normalize_teams_involved([]) == []

    # Single item list
    assert _normalize_teams_involved(["Team1"]) == ["Team1"]


def test_count_teams_involved():
    """Test _count_teams_involved with various formats."""
    from validate_planning import _count_teams_involved

    # None/null
    assert _count_teams_involved(None) == 0

    # String formats
    assert _count_teams_involved("Team A, Team B, Team C") == 3
    assert _count_teams_involved("Single Team") == 1
    assert _count_teams_involved("") == 0

    # List formats
    assert _count_teams_involved(["Team1", "Team2", "Team3"]) == 3
    assert _count_teams_involved([]) == 0
    assert _count_teams_involved(["Team1"]) == 1


def test_validate_initiative_status_teams_filter(tmp_path):
    """Test that only multi-team initiatives (teams >= 2) are validated."""
    # Create test data with varying team counts
    test_data = {
        "initiatives": [
            {
                "key": "INIT-1",
                "summary": "One team initiative",
                "status": "Proposed",
                "quarter": "26 Q2",
                "assignee": "user1",
                "strategic_objective": "2026_fuel_regulated",
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
                "quarter": "26 Q2",
                "assignee": "user2",
                "strategic_objective": "2026_fuel_regulated",
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
                "quarter": "26 Q2",
                "assignee": "user3",
                "strategic_objective": "2026_fuel_regulated",
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

    # Filter is hardcoded to teams >= 2, so only INIT-2 and INIT-3 are validated
    result = validate_initiative_status(json_file, quarter="26 Q2")
    assert result.total_checked == 2
    assert result.total_filtered == 1
    assert len(result.ready_to_plan) == 2


def test_validate_initiative_status_teams_with_various_formats(tmp_path):
    """Test teams >= 2 filter with None, string, and list formats."""
    test_data = {
        "initiatives": [
            {
                "key": "INIT-1",
                "summary": "None teams",
                "status": "Proposed",
                "quarter": "26 Q2",
                "assignee": "user1",
                "strategic_objective": "2026_fuel_regulated",
                "teams_involved": None,  # Real data has this!
                "contributing_teams": []
            },
            {
                "key": "INIT-2",
                "summary": "String single team",
                "status": "Proposed",
                "quarter": "26 Q2",
                "assignee": "user2",
                "strategic_objective": "2026_fuel_regulated",
                "teams_involved": "Team A",
                "contributing_teams": [
                    {
                        "team_project_key": "Team A",
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
                "quarter": "26 Q2",
                "assignee": "user3",
                "strategic_objective": "2026_fuel_regulated",
                "teams_involved": "Team A, Team B, Team C",
                "contributing_teams": [
                    {
                        "team_project_key": "Team A",
                        "epics": [
                            {"key": "EPIC-2", "summary": "Epic 2", "rag_status": "🟢"}
                        ]
                    },
                    {
                        "team_project_key": "Team B",
                        "epics": [
                            {"key": "EPIC-3", "summary": "Epic 3", "rag_status": "🟢"}
                        ]
                    },
                    {
                        "team_project_key": "Team C",
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
                "quarter": "26 Q2",
                "assignee": "user4",
                "strategic_objective": "2026_fuel_regulated",
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

    # Filter is hardcoded to teams >= 2
    # Should include only INIT-3 (3 teams) and INIT-4 (2 teams)
    result = validate_initiative_status(json_file, quarter="26 Q2")
    assert result.total_checked == 2
    assert result.total_filtered == 2  # INIT-1 (None/0) and INIT-2 (1) filtered out
    # INIT-3 (3 teams) and INIT-4 (2 teams) should be included
    assert len(result.ready_to_plan) == 2


def test_console_output_includes_manager_tags_for_missing_epics(tmp_path, capsys):
    """Test that console output includes manager tags when teams need to create epics."""
    test_data = {
        "initiatives": [
            {
                "key": "INIT-100",
                "summary": "Test Initiative with Missing Epics",
                "status": "Proposed",
                "quarter": "26 Q2",
                "assignee": "test@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "owner_team": "Console",
                "teams_involved": ["Console", "Payments Risk"],
                "contributing_teams": [
                    {
                        "team_project_key": "CONSOLE",
                        "epics": [{"key": "CONSOLE-1", "summary": "Epic 1", "rag_status": "🟢"}]
                    }
                    # Missing RSK epic
                ]
            }
        ]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_data))

    result = validate_initiative_status(json_file, quarter="26 Q2")
    assert len(result.dependency_mapping) == 1

    # Print the report and capture output
    print_validation_report(result, json_file, verbose=False)
    captured = capsys.readouterr()

    # Verify manager tag appears in console output for RSK team
    # Use actual manager from config, not hardcoded test value
    assert "Payments Risk (RSK) to create epic" in captured.out
    assert "@" in captured.out  # Verify some manager tag is present


def test_markdown_output_includes_manager_tags_for_missing_epics(tmp_path):
    """Test that markdown output includes manager tags when teams need to create epics."""
    test_data = {
        "initiatives": [
            {
                "key": "INIT-101",
                "summary": "Test Initiative with Multiple Missing Epics",
                "status": "Proposed",
                "quarter": "26 Q2",
                "assignee": "test@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "owner_team": "Core Banking",
                "teams_involved": ["Core Banking", "Payments Risk", "PAYIN"],
                "contributing_teams": [
                    {
                        "team_project_key": "CBNK",
                        "epics": [{"key": "CBNK-1", "summary": "Epic 1", "rag_status": "🟢"}]
                    }
                    # Missing RSK and PAYINS epics
                ]
            }
        ]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_data))

    result = validate_initiative_status(json_file, quarter="26 Q2")
    assert len(result.dependency_mapping) == 1

    # Generate markdown report
    markdown = generate_markdown_report(result, json_file, verbose=False)

    # Verify manager tags appear in markdown for both missing teams
    # Use actual managers from config, not hardcoded test values
    assert "Payments Risk (RSK) to create epic" in markdown
    assert "PAYIN (PAYINS) to create epic" in markdown
    assert "@" in markdown  # Verify manager tags are present


def test_console_output_no_manager_tag_for_unmapped_team(tmp_path, capsys):
    """Test that console output has no manager tag for unmapped teams."""
    test_data = {
        "initiatives": [
            {
                "key": "INIT-102",
                "summary": "Test Initiative with Unmapped Team",
                "status": "Proposed",
                "quarter": "26 Q2",
                "assignee": "test@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "owner_team": "Console",
                "teams_involved": ["Console", "UnmappedTeam"],
                "contributing_teams": [
                    {
                        "team_project_key": "CONSOLE",
                        "epics": [{"key": "CONSOLE-1", "summary": "Epic 1", "rag_status": "🟢"}]
                    }
                    # Missing epic for unmapped team
                ]
            }
        ]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_data))

    result = validate_initiative_status(json_file, quarter="26 Q2")
    assert len(result.dependency_mapping) == 1

    # Print the report and capture output
    print_validation_report(result, json_file, verbose=False)
    captured = capsys.readouterr()

    # Verify unmapped team shows without manager tag
    assert "UnmappedTeam (unmapped) to create epic" in captured.out
    # Should not have any @ mention after unmapped team
    assert "UnmappedTeam (unmapped) to create epic @" not in captured.out


def test_is_discovery_initiative():
    """Test discovery initiative detection."""
    # Discovery initiative
    discovery_init = {"summary": "[Discovery] Test Initiative"}
    assert _is_discovery_initiative(discovery_init) is True

    # Non-discovery initiative
    normal_init = {"summary": "Test Initiative"}
    assert _is_discovery_initiative(normal_init) is False

    # Edge case: discovery text elsewhere
    other_init = {"summary": "Test [Discovery] Initiative"}
    assert _is_discovery_initiative(other_init) is False


def test_discovery_initiative_skips_epic_count_check():
    """Test that discovery initiatives skip epic count mismatch check."""
    initiative = {
        "key": "INIT-200",
        "summary": "[Discovery] Test Discovery Initiative",
        "status": "Proposed",
        "quarter": "26 Q2",
        "assignee": "test@example.com",
        "strategic_objective": "2026_fuel_regulated",
        "owner_team": "Console",
        "teams_involved": ["Console", "Payments Risk"],
        "contributing_teams": [
            {
                "team_project_key": "CONSOLE",
                "epics": [{"key": "CONSOLE-1", "summary": "Epic 1", "rag_status": "🟢"}]
            }
            # Missing RSK epic - but should be ignored for discovery
        ]
    }

    issues = _check_data_quality(initiative)

    # Should have no epic_count_mismatch issue
    if issues:
        issue_types = [issue['type'] for issue in issues]
        assert 'epic_count_mismatch' not in issue_types


def test_discovery_initiative_skips_missing_rag_check():
    """Test that discovery initiatives skip missing RAG status check."""
    initiative = {
        "key": "INIT-201",
        "summary": "[Discovery] Test Discovery Initiative",
        "status": "Proposed",
        "quarter": "26 Q2",
        "assignee": "test@example.com",
        "strategic_objective": "2026_fuel_regulated",
        "owner_team": "Console",
        "teams_involved": ["Console", "Payments Risk"],
        "contributing_teams": [
            {
                "team_project_key": "CONSOLE",
                "epics": [{"key": "CONSOLE-1", "summary": "Epic 1", "rag_status": "🟢"}]
            },
            {
                "team_project_key": "RSK",
                "epics": [{"key": "RSK-1", "summary": "Epic 2", "rag_status": None}]
            }
        ]
    }

    issues = _check_data_quality(initiative)

    # Should have no missing_rag_status issue
    if issues:
        issue_types = [issue['type'] for issue in issues]
        assert 'missing_rag_status' not in issue_types


def test_discovery_initiative_still_checks_assignee():
    """Test that discovery initiatives still require assignee."""
    initiative = {
        "key": "INIT-202",
        "summary": "[Discovery] Test Discovery Initiative",
        "status": "Proposed",
        "quarter": "26 Q2",
        "assignee": None,  # Missing assignee
        "strategic_objective": "2026_fuel_regulated",
        "owner_team": "Console",
        "teams_involved": ["Console"],
        "contributing_teams": [
            {
                "team_project_key": "CONSOLE",
                "epics": [{"key": "CONSOLE-1", "summary": "Epic 1", "rag_status": "🟢"}]
            }
        ]
    }

    issues = _check_data_quality(initiative)

    # Should still have missing_assignee issue
    assert issues is not None
    issue_types = [issue['type'] for issue in issues]
    assert 'missing_assignee' in issue_types


def test_discovery_initiative_still_checks_strategic_objective():
    """Test that discovery initiatives still require strategic objective."""
    initiative = {
        "key": "INIT-203",
        "summary": "[Discovery] Test Discovery Initiative",
        "status": "Proposed",
        "quarter": "26 Q2",
        "assignee": "test@example.com",
        "strategic_objective": "",  # Missing strategic objective
        "owner_team": "Console",
        "teams_involved": ["Console"],
        "contributing_teams": [
            {
                "team_project_key": "CONSOLE",
                "epics": [{"key": "CONSOLE-1", "summary": "Epic 1", "rag_status": "🟢"}]
            }
        ]
    }

    issues = _check_data_quality(initiative)

    # Should still have missing_strategic_objective issue
    assert issues is not None
    issue_types = [issue['type'] for issue in issues]
    assert 'missing_strategic_objective' in issue_types


def test_planned_discovery_initiative_console_warning(tmp_path, capsys):
    """Test that console output shows discovery warning for planned discovery initiatives."""
    test_data = {
        "initiatives": [
            {
                "key": "INIT-204",
                "summary": "[Discovery] Test Discovery Initiative",
                "status": "Planned",
                "quarter": "26 Q2",
                "assignee": "test@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "owner_team": "Console",
                "teams_involved": ["Console", "Payments Risk", "Core Banking"],
                "contributing_teams": [
                    {
                        "team_project_key": "CONSOLE",
                        "epics": [{"key": "CONSOLE-1", "summary": "Epic 1", "rag_status": "🟢"}]
                    }
                ]
            }
        ]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_data))

    result = validate_initiative_status(json_file, quarter="26 Q2")
    assert len(result.planned_for_quarter) == 1
    assert result.planned_for_quarter[0]['is_discovery'] is True

    # Print the report and capture output
    print_validation_report(result, json_file, verbose=False)
    captured = capsys.readouterr()

    # Verify discovery warning appears in console output
    assert "⚠️ Discovery impact for: Console, Payments Risk, Core Banking" in captured.out


def test_planned_discovery_initiative_markdown_warning(tmp_path):
    """Test that markdown output shows discovery warning for planned discovery initiatives."""
    test_data = {
        "initiatives": [
            {
                "key": "INIT-205",
                "summary": "[Discovery] Multi-team Discovery",
                "status": "Planned",
                "quarter": "26 Q2",
                "assignee": "test@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "owner_team": "MAP",
                "teams_involved": ["MAP", "PAYIN", "Console"],
                "contributing_teams": [
                    {
                        "team_project_key": "MAPS",
                        "epics": [{"key": "MAPS-1", "summary": "Epic 1", "rag_status": "🟢"}]
                    }
                ]
            }
        ]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_data))

    result = validate_initiative_status(json_file, quarter="26 Q2")
    assert len(result.planned_for_quarter) == 1
    assert result.planned_for_quarter[0]['is_discovery'] is True

    # Generate markdown report
    markdown = generate_markdown_report(result, json_file, verbose=False)

    # Verify discovery warning appears in markdown output
    assert "⚠️ **Discovery impact for**: MAP, PAYIN, Console" in markdown


def test_non_discovery_initiative_normal_validation(tmp_path):
    """Test that non-discovery initiatives still get normal validation."""
    test_data = {
        "initiatives": [
            {
                "key": "INIT-206",
                "summary": "Normal Initiative",
                "status": "Proposed",
                "quarter": "26 Q2",
                "assignee": "test@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "owner_team": "Console",
                "teams_involved": ["Console", "Payments Risk"],
                "contributing_teams": [
                    {
                        "team_project_key": "CONSOLE",
                        "epics": [{"key": "CONSOLE-1", "summary": "Epic 1", "rag_status": "🟢"}]
                    }
                    # Missing RSK epic - should be flagged for non-discovery
                ]
            }
        ]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_data))

    result = validate_initiative_status(json_file, quarter="26 Q2")

    # Should be in dependency_mapping due to missing epic
    assert len(result.dependency_mapping) == 1
    assert result.dependency_mapping[0]['key'] == 'INIT-206'

    # Should have epic_count_mismatch issue
    issues = result.dependency_mapping[0]['issues']
    issue_types = [issue['type'] for issue in issues]
    assert 'epic_count_mismatch' in issue_types


def test_in_progress_initiative_treated_as_planned(tmp_path):
    """Test that In Progress initiatives are treated the same as Planned initiatives."""
    test_data = {
        "initiatives": [
            {
                "key": "INIT-300",
                "summary": "In Progress Initiative",
                "status": "In Progress",
                "quarter": "26 Q2",
                "assignee": "test@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "owner_team": "Console",
                "teams_involved": ["Console", "Payments Risk"],
                "contributing_teams": [
                    {
                        "team_project_key": "CONSOLE",
                        "epics": [{"key": "CONSOLE-1", "summary": "Epic 1", "rag_status": "🟢"}]
                    },
                    {
                        "team_project_key": "RSK",
                        "epics": [{"key": "RSK-1", "summary": "Epic 2", "rag_status": "🟢"}]
                    }
                ]
            }
        ]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_data))

    result = validate_initiative_status(json_file, quarter="26 Q2")

    # Should be in planned_for_quarter (healthy initiatives)
    assert len(result.planned_for_quarter) == 1
    assert result.planned_for_quarter[0]['key'] == 'INIT-300'
    assert result.planned_for_quarter[0]['status'] == 'In Progress'


def test_in_progress_initiative_with_issues(tmp_path):
    """Test that In Progress initiatives with issues go to planned_regressions."""
    test_data = {
        "initiatives": [
            {
                "key": "INIT-301",
                "summary": "In Progress Initiative with Issues",
                "status": "In Progress",
                "quarter": "26 Q2",
                "assignee": "test@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "owner_team": "Console",
                "teams_involved": ["Console", "Payments Risk"],
                "contributing_teams": [
                    {
                        "team_project_key": "CONSOLE",
                        "epics": [{"key": "CONSOLE-1", "summary": "Epic 1", "rag_status": "🟢"}]
                    }
                    # Missing RSK epic - should cause regression
                ]
            }
        ]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_data))

    result = validate_initiative_status(json_file, quarter="26 Q2")

    # Should be in planned_regressions due to missing epic
    assert len(result.planned_regressions) == 1
    assert result.planned_regressions[0]['key'] == 'INIT-301'
    assert result.planned_regressions[0]['status'] == 'In Progress'


def test_load_teams_excluded_from_analysis():
    """Test loading teams excluded from analysis from team_mappings.yaml."""
    excluded_teams = _load_teams_excluded_from_analysis()
    # Should include IT team from the configuration
    assert 'IT' in excluded_teams


def test_excluded_team_initiative_filtered_out(tmp_path):
    """Test that initiatives with excluded owner teams are filtered out."""
    test_data = {
        "initiatives": [
            {
                "key": "INIT-400",
                "summary": "IT Integration Initiative",
                "status": "Proposed",
                "quarter": "26 Q2",
                "assignee": "test@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "owner_team": "IT",
                "teams_involved": ["IT", "Console"],
                "contributing_teams": [
                    {
                        "team_project_key": "IT",
                        "epics": [{"key": "IT-1", "summary": "Epic 1", "rag_status": "🟢"}]
                    }
                ]
            }
        ]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_data))

    result = validate_initiative_status(json_file, quarter="26 Q2")

    # Should not appear in any validation category
    assert len(result.dependency_mapping) == 0
    assert len(result.low_confidence_completion) == 0
    assert len(result.ready_to_plan) == 0
    assert len(result.planned_for_quarter) == 0
    assert len(result.planned_regressions) == 0

    # Should be in ignored_statuses with team excluded status
    assert len(result.ignored_statuses) == 1
    assert result.ignored_statuses[0]['key'] == 'INIT-400'
    assert result.ignored_statuses[0]['status'] == 'Proposed (team excluded)'


def test_non_excluded_team_initiative_processed(tmp_path):
    """Test that initiatives with non-excluded owner teams are processed normally."""
    test_data = {
        "initiatives": [
            {
                "key": "INIT-401",
                "summary": "Normal Initiative",
                "status": "Proposed",
                "quarter": "26 Q2",
                "assignee": "test@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "owner_team": "Console",
                "teams_involved": ["Console", "Payments Risk"],
                "contributing_teams": [
                    {
                        "team_project_key": "CONSOLE",
                        "epics": [{"key": "CONSOLE-1", "summary": "Epic 1", "rag_status": "🟢"}]
                    },
                    {
                        "team_project_key": "RSK",
                        "epics": [{"key": "RSK-1", "summary": "Epic 2", "rag_status": "🟢"}]
                    }
                ]
            }
        ]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_data))

    result = validate_initiative_status(json_file, quarter="26 Q2")

    # Should be processed normally and appear in ready_to_plan
    assert len(result.ready_to_plan) == 1
    assert result.ready_to_plan[0]['key'] == 'INIT-401'

    # Should not be in ignored_statuses
    ignored_keys = [item['key'] for item in result.ignored_statuses]
    assert 'INIT-401' not in ignored_keys


def test_mixed_excluded_and_non_excluded_teams(tmp_path):
    """Test filtering with mix of excluded and non-excluded team initiatives."""
    test_data = {
        "initiatives": [
            {
                "key": "INIT-402",
                "summary": "IT Initiative",
                "status": "Proposed",
                "quarter": "26 Q2",
                "assignee": "test@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "owner_team": "IT",
                "teams_involved": ["IT", "Console"],
                "contributing_teams": [
                    {
                        "team_project_key": "IT",
                        "epics": [{"key": "IT-1", "summary": "Epic 1", "rag_status": "🟢"}]
                    }
                ]
            },
            {
                "key": "INIT-403",
                "summary": "Console Initiative",
                "status": "Proposed",
                "quarter": "26 Q2",
                "assignee": "test@example.com",
                "strategic_objective": "2026_fuel_regulated",
                "owner_team": "Console",
                "teams_involved": ["Console", "Payments Risk"],
                "contributing_teams": [
                    {
                        "team_project_key": "CONSOLE",
                        "epics": [{"key": "CONSOLE-1", "summary": "Epic 1", "rag_status": "🟢"}]
                    },
                    {
                        "team_project_key": "RSK",
                        "epics": [{"key": "RSK-1", "summary": "Epic 2", "rag_status": "🟢"}]
                    }
                ]
            }
        ]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_data))

    result = validate_initiative_status(json_file, quarter="26 Q2")

    # IT initiative should be in ignored_statuses
    ignored_keys = [item['key'] for item in result.ignored_statuses]
    assert 'INIT-402' in ignored_keys
    # Verify it has the team excluded status
    it_item = [item for item in result.ignored_statuses if item['key'] == 'INIT-402'][0]
    assert '(team excluded)' in it_item['status']

    # Console initiative should be processed
    assert len(result.ready_to_plan) == 1
    assert result.ready_to_plan[0]['key'] == 'INIT-403'

# ============================================================================
# Dust Integration Tests
# ============================================================================

def test_load_team_managers_dict_format():
    """Test _load_team_managers() handles new dict format."""
    managers = _load_team_managers()

    # Should return dict format
    assert isinstance(managers, dict)

    # Check a known team has both fields (using actual config values)
    if 'CBPPE' in managers:
        assert isinstance(managers['CBPPE'], dict)
        assert 'notion_handle' in managers['CBPPE']
        assert 'slack_id' in managers['CBPPE']
        # Just verify the fields exist and are strings, not specific values
        assert isinstance(managers['CBPPE']['notion_handle'], str)
        assert isinstance(managers['CBPPE']['slack_id'], str)


def test_validate_slack_config_all_ids_present():
    """Test _validate_slack_config() passes when all IDs present."""
    team_managers = {
        "CBPPE": {
            "notion_handle": "@Test",
            "slack_id": "U123"
        }
    }
    
    # Should not raise
    _validate_slack_config(team_managers)


def test_validate_slack_config_missing_ids():
    """Test _validate_slack_config() raises when IDs missing."""
    team_managers = {
        "CBPPE": {
            "notion_handle": "@Test",
            "slack_id": None
        },
        "RSK": {
            "notion_handle": "@Test2",
            "slack_id": "U456"
        }
    }
    
    with pytest.raises(ValueError) as exc_info:
        _validate_slack_config(team_managers)
    
    assert "Missing Slack IDs" in str(exc_info.value)
    assert "CBPPE" in str(exc_info.value)


def test_extract_manager_actions_missing_dependencies(tmp_path):
    """Test extraction of missing dependencies actions."""
    result = ValidationResult()
    result.dependency_mapping = [{
        'key': 'INIT-1234',
        'summary': 'Test Initiative',
        'status': 'Proposed',
        'owner_team': 'Payments Risk',
        'url': 'https://test.com/INIT-1234',
        'issues': [{
            'type': 'epic_count_mismatch',
            'teams_involved': ['Payments Risk', 'Console'],
            'teams_with_epics': ['Payments Risk']
        }]
    }]
    
    actions = extract_manager_actions(result)
    
    # Should have action for Console to create epic
    assert len(actions) > 0
    console_actions = [a for a in actions if a['action_type'] == 'missing_dependencies']
    assert len(console_actions) == 1
    assert console_actions[0]['responsible_team'] == 'Console'
    assert console_actions[0]['description'] == 'Create epic'
    assert console_actions[0]['priority'] == 4


def test_extract_manager_actions_ready_to_planned(tmp_path):
    """Test extraction of ready to PLANNED actions."""
    result = ValidationResult()
    result.ready_to_plan = [{
        'key': 'INIT-5678',
        'summary': 'Ready Initiative',
        'status': 'Proposed',
        'owner_team': 'Payments Risk',
        'url': 'https://test.com/INIT-5678'
    }]
    
    actions = extract_manager_actions(result)
    
    # Should have ready_to_planned action
    assert len(actions) == 1
    assert actions[0]['action_type'] == 'ready_to_planned'
    assert actions[0]['priority'] == 7
    assert 'Move initiative to PLANNED status' in actions[0]['description']


def test_extract_manager_actions_clarify_decision(tmp_path):
    """Test extraction of clarify decision actions for low confidence initiatives."""
    result = ValidationResult()
    result.low_confidence_completion = [{
        'key': 'INIT-9999',
        'summary': 'Low Confidence Initiative',
        'status': 'Proposed',
        'owner_team': 'Console',
        'url': 'https://test.com/INIT-9999',
        'contributing_teams': [],
        'issues': []
    }]

    actions = extract_manager_actions(result)

    # Should have clarify_decision action
    assert len(actions) == 1
    assert actions[0]['action_type'] == 'clarify_decision'
    assert actions[0]['priority'] == 6
    assert 'Clarify final decision (PLANNED or DEPRIORITISED)' in actions[0]['description']


def test_generate_slack_messages_creates_file(tmp_path):
    """Test Slack messages are saved to timestamped file."""
    result = ValidationResult()
    result.dependency_mapping = [{
        'key': 'INIT-1234',
        'summary': 'Test',
        'status': 'Proposed',
        'owner_team': 'Console',
        'url': 'https://test.com/INIT-1234',
        'issues': [{
            'type': 'missing_assignee'
        }]
    }]
    
    # Capture output
    import io
    import sys
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    
    try:
        generate_slack_messages(result, tmp_path)
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout
    
    # Check file was created
    slack_files = list(tmp_path.glob('slack_messages_*.txt'))
    assert len(slack_files) == 1
    
    # Check console output
    assert "SLACK BULK MESSAGES" in output
    assert "Recipient:" in output


def test_generate_slack_messages_groups_by_manager(tmp_path):
    """Test Slack messages group actions by manager correctly."""
    result = ValidationResult()
    result.dependency_mapping = [
        {
            'key': 'INIT-1',
            'summary': 'Test 1',
            'status': 'Proposed',
            'owner_team': 'Console',
            'url': 'https://test.com/INIT-1',
            'issues': [{'type': 'missing_assignee'}]
        },
        {
            'key': 'INIT-2',
            'summary': 'Test 2',
            'status': 'Proposed',
            'owner_team': 'Console',
            'url': 'https://test.com/INIT-2',
            'issues': [{'type': 'missing_assignee'}]
        }
    ]
    
    # Suppress output
    import io
    import sys
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    
    try:
        generate_slack_messages(result, tmp_path)
    finally:
        sys.stdout = old_stdout
    
    # Read generated file
    slack_files = list(tmp_path.glob('slack_messages_*.txt'))
    content = slack_files[0].read_text()
    
    # Should have one recipient block for Console manager
    # Use actual Slack ID from config, not mock value
    recipient_count = content.count('Recipient: U050ECECBLK')
    assert recipient_count == 1
    
    # Should mention both initiatives
    assert 'INIT-1' in content
    assert 'INIT-2' in content


def test_generate_slack_messages_multi_team_manager(tmp_path):
    """Test manager with multiple teams gets one message with team subsections."""
    result = ValidationResult()
    result.dependency_mapping = [
        {
            'key': 'INIT-1',
            'summary': 'Console Initiative',
            'status': 'Proposed',
            'owner_team': 'Console',
            'url': 'https://test.com/INIT-1',
            'issues': [{'type': 'missing_assignee'}]
        },
        {
            'key': 'INIT-2',
            'summary': 'Payins Initiative',
            'status': 'Proposed',
            'owner_team': 'Payments Payins',
            'url': 'https://test.com/INIT-2',
            'issues': [{'type': 'missing_assignee'}]
        }
    ]

    # Suppress output
    import io
    import sys
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        generate_slack_messages(result, tmp_path)
    finally:
        sys.stdout = old_stdout

    # Read generated file
    slack_files = list(tmp_path.glob('slack_messages_*.txt'))
    content = slack_files[0].read_text()

    # Manager manages both Console and Payins, should have ONE recipient block
    # Use actual Slack ID from config, not mock value
    recipient_count = content.count('Recipient: U050ECECBLK')
    assert recipient_count == 1, f"Expected 1 recipient block, found {recipient_count}"

    # Should have team subsections
    assert '**Console:**' in content, "Should show Console team subsection"
    assert '**Payments Payins:**' in content, "Should show Payins team subsection"

    # Both initiatives should be present
    assert 'INIT-1' in content
    assert 'INIT-2' in content

    # Verify Console initiative appears after Console team header
    console_idx = content.find('**Console:**')
    init1_idx = content.find('INIT-1')
    payins_idx = content.find('**Payments Payins:**')
    init2_idx = content.find('INIT-2')

    assert console_idx < init1_idx < payins_idx < init2_idx, \
        "Initiatives should appear under their respective team headers"


# ===== Initiative Sign-Off Exceptions Tests =====

def test_generate_slack_messages_includes_clarify_decision(tmp_path):
    """Test Slack messages include clarify decision actions for low confidence initiatives."""
    result = ValidationResult()
    result.low_confidence_completion = [{
        'key': 'INIT-8888',
        'summary': 'Low Confidence Initiative',
        'status': 'Proposed',
        'owner_team': 'Console',
        'url': 'https://test.com/INIT-8888',
        'contributing_teams': [],
        'issues': []
    }]

    # Capture output
    import io
    import sys
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        generate_slack_messages(result, tmp_path)
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    # Verify clarify decision action appears in output
    assert 'INIT-8888' in output
    assert 'Clarify final decision (PLANNED or DEPRIORITISED)' in output
    assert ':thinking_face:' in output


def test_load_signed_off_initiatives_returns_set():
    """Test that _load_signed_off_initiatives returns a set."""
    # The function should always return a set (empty if file missing, populated if exists)
    keys = _load_signed_off_initiatives()
    assert isinstance(keys, set)
    # Each item should be a string (initiative key)
    for key in keys:
        assert isinstance(key, str)
        assert key.startswith('INIT-')


def test_signed_off_initiative_filtered_out(tmp_path):
    """Test that signed-off initiatives are completely filtered out."""
    # Create config with signed-off initiative
    config_data = {
        'signed_off_initiatives': [
            {'key': 'INIT-1234', 'reason': 'Manager approved'}
        ]
    }

    config_dir = Path(__file__).parent.parent / 'config'
    test_config_file = config_dir / 'initiative_exceptions.yaml'
    original_content = None

    try:
        # Backup original if it exists
        if test_config_file.exists():
            original_content = test_config_file.read_text()

        # Write test config
        with open(test_config_file, 'w') as f:
            yaml.dump(config_data, f)

        # Create test data with initiative that should be filtered
        test_data = {
            'initiatives': [
                {
                    'key': 'INIT-1234',
                    'summary': 'Signed off initiative',
                    'status': 'Proposed',
                    'quarter': '26 Q2',
                    'assignee': 'user@example.com',
                    'strategic_objective': '2026_fuel_regulated',
                    'teams_involved': ['Team A', 'Team B'],
                    'owner_team': 'Team A',
                    'contributing_teams': []  # Missing epics - would normally trigger validation
                }
            ],
            'epics': []
        }

        json_file = tmp_path / 'test.json'
        json_file.write_text(json.dumps(test_data))

        result = validate_initiative_status(json_file, quarter="26 Q2")

        # Initiative should not appear in ANY result category
        assert len(result.dependency_mapping) == 0
        assert len(result.ready_to_plan) == 0
        assert len(result.low_confidence_completion) == 0
        assert len(result.planned_for_quarter) == 0
        assert len(result.planned_regressions) == 0
        # Verify it was actually filtered (not counted as checked)
        assert result.total_checked == 0
    finally:
        # Restore original config
        if original_content is not None:
            test_config_file.write_text(original_content)
        elif test_config_file.exists():
            test_config_file.unlink()


def test_mixed_signed_off_and_normal_initiatives(tmp_path):
    """Test that only signed-off initiatives are filtered."""
    # Create config with one signed-off initiative
    config_data = {
        'signed_off_initiatives': [
            {'key': 'INIT-1234', 'reason': 'Approved'}
        ]
    }

    config_dir = Path(__file__).parent.parent / 'config'
    test_config_file = config_dir / 'initiative_exceptions.yaml'
    original_content = None

    try:
        # Backup original if it exists
        if test_config_file.exists():
            original_content = test_config_file.read_text()

        # Write test config
        with open(test_config_file, 'w') as f:
            yaml.dump(config_data, f)

        # Test data with two initiatives
        test_data = {
            'initiatives': [
                {
                    'key': 'INIT-1234',
                    'summary': 'Signed off',
                    'status': 'Proposed',
                    'quarter': '26 Q2',
                    'assignee': 'user@example.com',
                    'strategic_objective': '2026_fuel_regulated',
                    'teams_involved': ['Team A', 'Team B'],
                    'owner_team': 'Team A',
                    'contributing_teams': []  # Missing epics
                },
                {
                    'key': 'INIT-5678',
                    'summary': 'Normal',
                    'status': 'Proposed',
                    'quarter': '26 Q2',
                    'assignee': 'user@example.com',
                    'strategic_objective': '2026_fuel_regulated',
                    'teams_involved': ['Team A', 'Team B'],
                    'owner_team': 'Team A',
                    'contributing_teams': []  # Missing epics - should trigger validation
                }
            ],
            'epics': []
        }

        json_file = tmp_path / 'test.json'
        json_file.write_text(json.dumps(test_data))

        result = validate_initiative_status(json_file, quarter="26 Q2")

        # INIT-1234 should be filtered out
        # INIT-5678 should appear in dependency_mapping
        assert len(result.dependency_mapping) == 1
        assert result.dependency_mapping[0]['key'] == 'INIT-5678'
    finally:
        # Restore original config
        if original_content is not None:
            test_config_file.write_text(original_content)
        elif test_config_file.exists():
            test_config_file.unlink()
