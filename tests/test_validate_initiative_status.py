"""Tests for initiative status validation script."""

import json
import pytest
from pathlib import Path
from validate_initiative_status import (
    ValidationResult,
    validate_initiative_status,
    _check_data_quality,
    _has_red_epics,
    _has_yellow_epics,
    _is_ready_to_plan,
    find_latest_extract
)


def test_validation_result_has_issues():
    """Test ValidationResult.has_issues property."""
    result = ValidationResult()
    assert not result.has_issues

    result.dependency_mapping.append({'key': 'INIT-1'})
    assert result.has_issues

    result2 = ValidationResult()
    result2.cannot_complete_quarter.append({'key': 'INIT-2'})
    assert result2.has_issues

    result3 = ValidationResult()
    result3.low_confidence.append({'key': 'INIT-3'})
    assert result3.has_issues

    result4 = ValidationResult()
    result4.awaiting_owner.append({'key': 'INIT-4'})
    assert result4.has_issues

    result5 = ValidationResult()
    result5.planned_regressions.append({'key': 'INIT-5'})
    assert result5.has_issues


def test_check_data_quality_epic_count_mismatch():
    """Test data quality check with epic count != teams count."""
    initiative = {
        "key": "INIT-123",
        "summary": "Test Initiative",
        "status": "Proposed",
        "assignee": "user@example.com",
        "strategic_objective": "Test Objective",
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
        "strategic_objective": "Test Objective",
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
    """Test data quality check with zero epics."""
    initiative = {
        "key": "INIT-789",
        "summary": "Test Initiative",
        "status": "Proposed",
        "assignee": "user@example.com",
        "strategic_objective": "Test Objective",
        "teams_involved": [],
        "contributing_teams": []
    }

    issues = _check_data_quality(initiative)

    assert issues is not None
    assert len(issues) == 1
    assert issues[0]['type'] == 'no_epics'


def test_check_data_quality_missing_strategic_objective():
    """Test data quality check with missing strategic objective."""
    initiative = {
        "key": "INIT-888",
        "summary": "Test Initiative",
        "status": "Proposed",
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
        "assignee": "user@example.com",
        "strategic_objective": "Improve customer satisfaction",
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
        "assignee": "user@example.com",
        "strategic_objective": "Test Objective",
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
        "assignee": "user@example.com",
        "strategic_objective": "Test Objective",
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
        "assignee": "user@example.com",
        "strategic_objective": "Test Objective",
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
        "assignee": None,
        "strategic_objective": "Test Objective",
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
        "assignee": "user@example.com",
        "strategic_objective": "Test Objective",
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
        "strategic_objective": "Test Objective",
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
        "strategic_objective": "Test Objective",
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
        "strategic_objective": "Test Objective",
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
        "strategic_objective": "Test Objective",
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


def test_validate_initiative_status_dependency_mapping(tmp_path):
    """Test full validation with data quality issues (Section 1: Dependency Mapping)."""
    data = {
        "initiatives": [{
            "key": "INIT-123",
            "summary": "Test Initiative",
            "status": "Proposed",
            "assignee": "user@example.com",
            "strategic_objective": "Test Objective",
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
    assert len(result.dependency_mapping) == 1
    assert result.dependency_mapping[0]['key'] == "INIT-123"
    assert len(result.cannot_complete_quarter) == 0
    assert len(result.low_confidence) == 0
    assert len(result.awaiting_owner) == 0
    assert len(result.ready_to_plan) == 0


def test_validate_initiative_status_cannot_complete(tmp_path):
    """Test full validation with RED epics (Section 2: Can't be completed)."""
    data = {
        "initiatives": [{
            "key": "INIT-456",
            "summary": "Test Initiative",
            "status": "Proposed",
            "assignee": "user@example.com",
            "strategic_objective": "Test Objective",
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

    result = validate_initiative_status(json_file)

    assert result.total_checked == 1
    assert len(result.dependency_mapping) == 0
    assert len(result.cannot_complete_quarter) == 1
    assert result.cannot_complete_quarter[0]['key'] == "INIT-456"
    assert len(result.low_confidence) == 0
    assert len(result.awaiting_owner) == 0
    assert len(result.ready_to_plan) == 0


def test_validate_initiative_status_low_confidence(tmp_path):
    """Test full validation with YELLOW epics (Section 3: Low confidence)."""
    data = {
        "initiatives": [{
            "key": "INIT-457",
            "summary": "Test Initiative",
            "status": "Proposed",
            "assignee": "user@example.com",
            "strategic_objective": "Test Objective",
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

    result = validate_initiative_status(json_file)

    assert result.total_checked == 1
    assert len(result.dependency_mapping) == 0
    assert len(result.cannot_complete_quarter) == 0
    assert len(result.low_confidence) == 1
    assert result.low_confidence[0]['key'] == "INIT-457"
    assert len(result.awaiting_owner) == 0
    assert len(result.ready_to_plan) == 0


def test_validate_initiative_status_awaiting_owner(tmp_path):
    """Test full validation with missing assignee (Section 4: Awaiting owner)."""
    data = {
        "initiatives": [{
            "key": "INIT-458",
            "summary": "Test Initiative",
            "status": "Proposed",
            "assignee": None,
            "strategic_objective": "Test Objective",
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

    result = validate_initiative_status(json_file)

    assert result.total_checked == 1
    assert len(result.dependency_mapping) == 0
    assert len(result.cannot_complete_quarter) == 0
    assert len(result.low_confidence) == 0
    assert len(result.awaiting_owner) == 1
    assert result.awaiting_owner[0]['key'] == "INIT-458"
    assert len(result.ready_to_plan) == 0


def test_validate_initiative_status_ready_to_plan(tmp_path):
    """Test full validation with ready initiative (Section 5: Ready to Move to Planned)."""
    data = {
        "initiatives": [{
            "key": "INIT-789",
            "summary": "Ready Initiative",
            "status": "Proposed",
            "assignee": "user@example.com",
            "strategic_objective": "Test Objective",
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

    result = validate_initiative_status(json_file)

    assert result.total_checked == 1
    assert len(result.dependency_mapping) == 0
    assert len(result.cannot_complete_quarter) == 0
    assert len(result.low_confidence) == 0
    assert len(result.awaiting_owner) == 0
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
            "strategic_objective": "Test Objective",
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

    result = validate_initiative_status(json_file)

    assert result.total_checked == 1
    assert len(result.dependency_mapping) == 0
    assert len(result.cannot_complete_quarter) == 0
    assert len(result.low_confidence) == 0
    assert len(result.awaiting_owner) == 0
    assert len(result.ready_to_plan) == 0
    assert len(result.planned_regressions) == 1
    assert result.planned_regressions[0]['key'] == "INIT-999"


def test_validate_initiative_status_planned_for_quarter(tmp_path):
    """Test full validation with healthy Planned initiative (Section 6: Planned for Quarter)."""
    data = {
        "initiatives": [{
            "key": "INIT-1000",
            "summary": "Healthy Planned Initiative",
            "status": "Planned",
            "assignee": "user@example.com",
            "strategic_objective": "Test Objective",
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

    result = validate_initiative_status(json_file)

    assert result.total_checked == 1
    assert len(result.dependency_mapping) == 0
    assert len(result.cannot_complete_quarter) == 0
    assert len(result.low_confidence) == 0
    assert len(result.awaiting_owner) == 0
    assert len(result.ready_to_plan) == 0
    assert len(result.planned_for_quarter) == 1
    assert result.planned_for_quarter[0]['key'] == "INIT-1000"
    assert len(result.planned_regressions) == 0


def test_load_teams_exempt_from_rag(tmp_path):
    """Test loading teams exempt from RAG checking from team_mappings.yaml."""
    from validate_initiative_status import _load_teams_exempt_from_rag

    # Note: This test will use the actual team_mappings.yaml in the project if it exists
    # For a full test, you would need to mock the file path
    # For now, just verify the function returns a list
    exempt_teams = _load_teams_exempt_from_rag()
    assert isinstance(exempt_teams, list)


def test_validate_initiative_status_mixed_statuses(tmp_path):
    """Test full validation with mixed initiative statuses across all 5 sections."""
    data = {
        "initiatives": [
            {
                "key": "INIT-001",
                "summary": "Data Quality Issue",
                "status": "Proposed",
                "assignee": "user@example.com",
                "strategic_objective": "Test Objective",
                "teams_involved": ["TEAM1", "TEAM2"],
                "contributing_teams": []
            },
            {
                "key": "INIT-002",
                "summary": "RED Epic",
                "status": "Proposed",
                "assignee": "user@example.com",
                "strategic_objective": "Test Objective",
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
                "assignee": "user@example.com",
                "strategic_objective": "Test Objective",
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
                "assignee": None,
                "strategic_objective": "Test Objective",
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
                "assignee": "user@example.com",
                "strategic_objective": "Test Objective",
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
                "assignee": "user@example.com",
                "strategic_objective": "Test Objective",
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

    result = validate_initiative_status(json_file)

    assert result.total_checked == 6
    assert len(result.dependency_mapping) == 1
    assert len(result.cannot_complete_quarter) == 1
    assert len(result.low_confidence) == 1
    assert len(result.awaiting_owner) == 1
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
                "assignee": "user1",
                "strategic_objective": "Test Objective",
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
                "strategic_objective": "Test Objective",
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
                "strategic_objective": "Test Objective",
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
    result = validate_initiative_status(json_file)
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
                "assignee": "user1",
                "strategic_objective": "Test Objective",
                "teams_involved": None,  # Real data has this!
                "contributing_teams": []
            },
            {
                "key": "INIT-2",
                "summary": "String single team",
                "status": "Proposed",
                "assignee": "user2",
                "strategic_objective": "Test Objective",
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
                "assignee": "user3",
                "strategic_objective": "Test Objective",
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
                "assignee": "user4",
                "strategic_objective": "Test Objective",
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
    result = validate_initiative_status(json_file)
    assert result.total_checked == 2
    assert result.total_filtered == 2  # INIT-1 (None/0) and INIT-2 (1) filtered out
    # INIT-3 (3 teams) and INIT-4 (2 teams) should be included
    assert len(result.ready_to_plan) == 2
