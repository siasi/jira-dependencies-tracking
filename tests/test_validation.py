"""Tests for shared validation library."""

import pytest
from lib.validation import (
    Priority,
    ValidationIssue,
    ValidationConfig,
    InitiativeValidator,
    is_owner_team,
    is_discovery_initiative,
    normalize_teams_involved,
    load_validation_config,
    create_action_item,
)


# Test Priority Enum
def test_priority_enum_values():
    """Test Priority enum has correct values."""
    assert Priority.CRITICAL == 1
    assert Priority.HIGH == 2
    assert Priority.MEDIUM == 3
    assert Priority.LOW == 4
    assert Priority.INFO == 5


def test_priority_enum_ordering():
    """Test Priority enum supports ordering."""
    assert Priority.CRITICAL < Priority.HIGH
    assert Priority.HIGH < Priority.MEDIUM
    assert Priority.MEDIUM < Priority.LOW
    assert Priority.LOW < Priority.INFO


# Test ValidationIssue Dataclass
def test_validation_issue_creation():
    """Test ValidationIssue can be created with all fields."""
    issue = ValidationIssue(
        type="missing_owner",
        priority=Priority.CRITICAL,
        description="Missing owner team",
        initiative_key="INIT-123",
        initiative_summary="Test Initiative",
        initiative_status="Proposed",
        owner_team=None,
        team_affected=None,
        epic_key=None,
        current_value=None,
        expected_value=None,
    )
    assert issue.type == "missing_owner"
    assert issue.priority == Priority.CRITICAL
    assert issue.initiative_key == "INIT-123"


def test_validation_issue_optional_fields():
    """Test ValidationIssue works with minimal fields."""
    issue = ValidationIssue(
        type="missing_assignee",
        priority=Priority.HIGH,
        description="Missing assignee",
        initiative_key="INIT-456",
        initiative_summary="Another Test",
        initiative_status="Planned",
        owner_team="TEAM1",
        team_affected="TEAM2",
        epic_key="TEAM2-123",
        current_value="wrong_value",
        expected_value="right_value",
    )
    assert issue.team_affected == "TEAM2"
    assert issue.epic_key == "TEAM2-123"


# Test ValidationConfig Dataclass
def test_validation_config_defaults():
    """Test ValidationConfig has correct defaults."""
    config = ValidationConfig()
    assert config.check_assignee is True
    assert config.check_strategic_objective is True
    assert config.check_teams_involved is True
    assert config.check_missing_epics is True
    assert config.check_rag_status is True
    assert config.owner_team_exempt is True
    assert config.skip_discovery is True


def test_validation_config_custom_values():
    """Test ValidationConfig can be customized."""
    config = ValidationConfig(
        check_assignee=False,
        check_rag_status=False,
        valid_strategic_objectives=["obj1", "obj2"],
        team_mappings={"Team A": "TEAMA"},
        rag_exempt_teams=["DOCS"],
    )
    assert config.check_assignee is False
    assert config.check_rag_status is False
    assert config.valid_strategic_objectives == ["obj1", "obj2"]
    assert config.team_mappings == {"Team A": "TEAMA"}
    assert config.rag_exempt_teams == ["DOCS"]


# Test Helper Functions
def test_is_owner_team_simple_match():
    """Test is_owner_team with direct match."""
    assert is_owner_team("TEAM1", "TEAM1", {}) is True
    assert is_owner_team("TEAM1", "TEAM2", {}) is False


def test_is_owner_team_with_mapping():
    """Test is_owner_team with team mappings."""
    team_mappings = {"Team A": "TEAMA", "Team B": "TEAMB"}
    assert is_owner_team("TEAMA", "Team A", team_mappings) is True
    assert is_owner_team("TEAMB", "Team A", team_mappings) is False


def test_is_owner_team_none_values():
    """Test is_owner_team handles None values."""
    assert is_owner_team("TEAM1", None, {}) is False
    assert is_owner_team(None, "TEAM1", {}) is False
    assert is_owner_team(None, None, {}) is False


def test_is_discovery_initiative():
    """Test is_discovery_initiative detection."""
    assert is_discovery_initiative({"summary": "[Discovery] Test"}) is True
    assert is_discovery_initiative({"summary": "Regular Initiative"}) is False
    assert is_discovery_initiative({"summary": ""}) is False
    assert is_discovery_initiative({}) is False


def test_normalize_teams_involved_list():
    """Test normalize_teams_involved with list input."""
    assert normalize_teams_involved(["TEAM1", "TEAM2"]) == ["TEAM1", "TEAM2"]
    assert normalize_teams_involved([]) == []


def test_normalize_teams_involved_string():
    """Test normalize_teams_involved with comma-separated string."""
    assert normalize_teams_involved("TEAM1, TEAM2") == ["TEAM1", "TEAM2"]
    assert normalize_teams_involved("TEAM1,TEAM2,TEAM3") == ["TEAM1", "TEAM2", "TEAM3"]
    assert normalize_teams_involved("Identity, PAYIN") == ["Identity", "PAYIN"]


def test_normalize_teams_involved_none():
    """Test normalize_teams_involved with None."""
    assert normalize_teams_involved(None) == []


def test_normalize_teams_involved_empty_string():
    """Test normalize_teams_involved with empty string."""
    assert normalize_teams_involved("") == []
    assert normalize_teams_involved("  ") == []


# Test InitiativeValidator - Universal Checks (All Statuses)
def test_check_owner_team_missing():
    """Test missing owner_team is detected (P1)."""
    config = ValidationConfig(valid_strategic_objectives=["obj1"])
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "Proposed",
        "owner_team": None,
        "strategic_objective": "obj1",
        "teams_involved": ["TEAM1"],
    }

    issues = validator.validate(initiative)

    owner_issues = [i for i in issues if i.type == "missing_owner_team"]
    assert len(owner_issues) == 1
    assert owner_issues[0].type == "missing_owner_team"
    assert owner_issues[0].priority == Priority.CRITICAL


def test_check_owner_team_empty_string():
    """Test empty string owner_team is detected."""
    config = ValidationConfig(valid_strategic_objectives=["obj1"])
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "Proposed",
        "owner_team": "",
        "strategic_objective": "obj1",
        "teams_involved": ["TEAM1"],
    }

    issues = validator.validate(initiative)

    owner_issues = [i for i in issues if i.type == "missing_owner_team"]
    assert len(owner_issues) == 1


def test_check_strategic_objective_missing():
    """Test missing strategic_objective is detected (P2)."""
    config = ValidationConfig(valid_strategic_objectives=["obj1"])
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "Proposed",
        "owner_team": "TEAM1",
        "strategic_objective": None,
        "teams_involved": ["TEAM1"],
    }

    issues = validator.validate(initiative)

    strategic_issues = [i for i in issues if i.type == "missing_strategic_objective"]
    assert len(strategic_issues) == 1
    assert strategic_issues[0].priority == Priority.HIGH


def test_check_strategic_objective_invalid():
    """Test invalid strategic_objective is detected (P3)."""
    config = ValidationConfig(valid_strategic_objectives=["obj1", "obj2"])
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "Proposed",
        "owner_team": "TEAM1",
        "strategic_objective": "invalid_obj",
        "teams_involved": ["TEAM1"],
    }

    issues = validator.validate(initiative)

    strategic_issues = [i for i in issues if i.type == "invalid_strategic_objective"]
    assert len(strategic_issues) == 1
    assert strategic_issues[0].priority == Priority.MEDIUM
    assert strategic_issues[0].current_value == "invalid_obj"


def test_check_strategic_objective_multi_comma_separated():
    """Test comma-separated strategic objectives are validated individually."""
    config = ValidationConfig(valid_strategic_objectives=["obj1", "obj2", "obj3"])
    validator = InitiativeValidator(config)

    # All valid
    initiative_valid = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "Proposed",
        "owner_team": "TEAM1",
        "strategic_objective": "obj1, obj2",
        "teams_involved": ["TEAM1"],
    }

    issues = validator.validate(initiative_valid)
    strategic_issues = [i for i in issues if i.type == "invalid_strategic_objective"]
    assert len(strategic_issues) == 0

    # Mixed valid/invalid
    initiative_mixed = {
        "key": "INIT-456",
        "summary": "Test",
        "status": "Proposed",
        "owner_team": "TEAM1",
        "strategic_objective": "obj1, invalid_obj, obj2",
        "teams_involved": ["TEAM1"],
    }

    issues = validator.validate(initiative_mixed)
    strategic_issues = [i for i in issues if i.type == "invalid_strategic_objective"]
    assert len(strategic_issues) == 1
    assert strategic_issues[0].current_value == "obj1, invalid_obj, obj2"
    assert "invalid_obj" in strategic_issues[0].description


def test_check_teams_involved_missing():
    """Test missing teams_involved is detected (P4)."""
    config = ValidationConfig(valid_strategic_objectives=["obj1"])
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "Proposed",
        "owner_team": "TEAM1",
        "strategic_objective": "obj1",
        "teams_involved": None,
    }

    issues = validator.validate(initiative)

    teams_issues = [i for i in issues if i.type == "missing_teams_involved"]
    assert len(teams_issues) == 1
    assert teams_issues[0].priority == Priority.LOW


def test_check_teams_involved_empty_list():
    """Test empty teams_involved list is detected."""
    config = ValidationConfig(valid_strategic_objectives=["obj1"])
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "Proposed",
        "owner_team": "TEAM1",
        "strategic_objective": "obj1",
        "teams_involved": [],
    }

    issues = validator.validate(initiative)

    teams_issues = [i for i in issues if i.type == "missing_teams_involved"]
    assert len(teams_issues) == 1


# Test InitiativeValidator - Status-Specific Checks
def test_check_assignee_for_proposed():
    """Test assignee check for Proposed status (P2)."""
    config = ValidationConfig(valid_strategic_objectives=["obj1"])
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "Proposed",
        "owner_team": "TEAM1",
        "strategic_objective": "obj1",
        "teams_involved": ["TEAM1"],
        "assignee": None,
    }

    issues = validator.validate(initiative)

    assignee_issues = [i for i in issues if i.type == "missing_assignee"]
    assert len(assignee_issues) == 1
    assert assignee_issues[0].priority == Priority.HIGH


def test_check_assignee_for_planned():
    """Test assignee check for Planned status."""
    config = ValidationConfig(valid_strategic_objectives=["obj1"])
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "Planned",
        "owner_team": "TEAM1",
        "strategic_objective": "obj1",
        "teams_involved": ["TEAM1"],
        "assignee": None,
    }

    issues = validator.validate(initiative)

    assignee_issues = [i for i in issues if i.type == "missing_assignee"]
    assert len(assignee_issues) == 1


def test_check_assignee_for_in_progress():
    """Test assignee check for In Progress status."""
    config = ValidationConfig(valid_strategic_objectives=["obj1"])
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "In Progress",
        "owner_team": "TEAM1",
        "strategic_objective": "obj1",
        "teams_involved": ["TEAM1"],
        "assignee": None,
    }

    issues = validator.validate(initiative)

    assignee_issues = [i for i in issues if i.type == "missing_assignee"]
    assert len(assignee_issues) == 1


def test_no_assignee_check_for_done():
    """Test assignee NOT checked for Done status."""
    config = ValidationConfig(valid_strategic_objectives=["obj1"])
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "Done",
        "owner_team": "TEAM1",
        "strategic_objective": "obj1",
        "teams_involved": ["TEAM1"],
        "assignee": None,
    }

    issues = validator.validate(initiative)

    assignee_issues = [i for i in issues if i.type == "missing_assignee"]
    assert len(assignee_issues) == 0


def test_check_missing_epics_owner_team_exempt():
    """Test owner team is exempt from creating epics."""
    config = ValidationConfig(
        valid_strategic_objectives=["obj1"],
        team_mappings={},
        owner_team_exempt=True,
    )
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "Proposed",
        "owner_team": "TEAM1",
        "assignee": "user@example.com",
        "strategic_objective": "obj1",
        "teams_involved": ["TEAM1", "TEAM2"],
        "contributing_teams": [
            {"team_project_key": "TEAM1", "epics": [{"key": "TEAM1-1", "rag_status": "🟢"}]}
        ],
    }

    issues = validator.validate(initiative)

    # Should only flag TEAM2 missing epic, not TEAM1 (owner)
    epic_issues = [i for i in issues if i.type == "missing_epic"]
    assert len(epic_issues) == 1
    assert epic_issues[0].team_affected == "TEAM2"


def test_check_missing_epics_discovery_exempt():
    """Test discovery initiatives are exempt from epic checks."""
    config = ValidationConfig(
        valid_strategic_objectives=["obj1"],
        skip_discovery=True,
    )
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "[Discovery] Test Initiative",
        "status": "Proposed",
        "owner_team": "TEAM1",
        "assignee": "user@example.com",
        "strategic_objective": "obj1",
        "teams_involved": ["TEAM1", "TEAM2"],
        "contributing_teams": [],
    }

    issues = validator.validate(initiative)

    # Discovery initiatives should not have missing epic issues
    epic_issues = [i for i in issues if i.type == "missing_epic"]
    assert len(epic_issues) == 0


def test_check_missing_epics_string_teams_involved():
    """Test teams_involved as comma-separated string is handled correctly."""
    config = ValidationConfig(
        valid_strategic_objectives=["obj1"],
        team_mappings={},
        owner_team_exempt=True,
    )
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "Proposed",
        "owner_team": "TEAM1",
        "assignee": "user@example.com",
        "strategic_objective": "obj1",
        "teams_involved": "Identity, PAYIN",  # String instead of list!
        "contributing_teams": [
            {"team_project_key": "TEAM1", "epics": [{"key": "TEAM1-1", "rag_status": "🟢"}]}
        ],
    }

    issues = validator.validate(initiative)

    # Should flag missing epics for Identity and PAYIN (not character by character!)
    epic_issues = [i for i in issues if i.type == "missing_epic"]
    assert len(epic_issues) == 2

    # Check the team names are correct (not single characters)
    teams_flagged = {issue.team_affected for issue in epic_issues}
    assert "Identity" in teams_flagged
    assert "PAYIN" in teams_flagged

    # Make sure we're not iterating character by character
    assert "I" not in teams_flagged
    assert "d" not in teams_flagged


def test_check_rag_status_for_proposed():
    """Test RAG status is checked for Proposed status."""
    config = ValidationConfig(
        valid_strategic_objectives=["obj1"],
        check_rag_status=True,
        rag_exempt_teams=[],
    )
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "Proposed",
        "owner_team": "TEAM1",
        "assignee": "user@example.com",
        "strategic_objective": "obj1",
        "teams_involved": ["TEAM1", "TEAM2"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM2",
                "epics": [{"key": "TEAM2-1", "rag_status": None}]
            }
        ],
    }

    issues = validator.validate(initiative)

    rag_issues = [i for i in issues if i.type == "missing_rag_status"]
    assert len(rag_issues) == 1
    assert rag_issues[0].priority == Priority.INFO
    assert rag_issues[0].team_affected == "TEAM2"


def test_check_rag_status_for_planned():
    """Test RAG status is checked for Planned status."""
    config = ValidationConfig(
        valid_strategic_objectives=["obj1"],
        check_rag_status=True,
        rag_exempt_teams=[],
    )
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "Planned",
        "owner_team": "TEAM1",
        "assignee": "user@example.com",
        "strategic_objective": "obj1",
        "teams_involved": ["TEAM1", "TEAM2"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM2",
                "epics": [{"key": "TEAM2-1", "rag_status": None}]
            }
        ],
    }

    issues = validator.validate(initiative)

    rag_issues = [i for i in issues if i.type == "missing_rag_status"]
    assert len(rag_issues) == 1


def test_no_rag_check_for_in_progress():
    """Test RAG status is NOT checked for In Progress status."""
    config = ValidationConfig(
        valid_strategic_objectives=["obj1"],
        check_rag_status=True,
        rag_exempt_teams=[],
    )
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "In Progress",
        "owner_team": "TEAM1",
        "assignee": "user@example.com",
        "strategic_objective": "obj1",
        "teams_involved": ["TEAM1", "TEAM2"],
        "contributing_teams": [
            {
                "team_project_key": "TEAM2",
                "epics": [{"key": "TEAM2-1", "rag_status": None}]
            }
        ],
    }

    issues = validator.validate(initiative)

    # RAG should NOT be validated for In Progress
    rag_issues = [i for i in issues if i.type == "missing_rag_status"]
    assert len(rag_issues) == 0


def test_rag_exempt_teams_skipped():
    """Test RAG-exempt teams are skipped."""
    config = ValidationConfig(
        valid_strategic_objectives=["obj1"],
        check_rag_status=True,
        rag_exempt_teams=["DOCS"],
    )
    validator = InitiativeValidator(config)

    initiative = {
        "key": "INIT-123",
        "summary": "Test",
        "status": "Proposed",
        "owner_team": "TEAM1",
        "assignee": "user@example.com",
        "strategic_objective": "obj1",
        "teams_involved": ["TEAM1", "DOCS"],
        "contributing_teams": [
            {
                "team_project_key": "DOCS",
                "epics": [{"key": "DOCS-1", "rag_status": None}]
            }
        ],
    }

    issues = validator.validate(initiative)

    # DOCS team should be exempt from RAG validation
    rag_issues = [i for i in issues if i.type == "missing_rag_status"]
    assert len(rag_issues) == 0


# Test load_validation_config
def test_load_validation_config_default():
    """Test load_validation_config with defaults."""
    config = load_validation_config()

    assert config.check_assignee is True
    assert config.check_rag_status is True
    assert config.valid_strategic_objectives is not None
    assert len(config.valid_strategic_objectives) > 0


def test_load_validation_config_status_filter_in_progress():
    """Test load_validation_config for In Progress disables RAG."""
    config = load_validation_config(status_filter="In Progress")

    assert config.check_rag_status is False


def test_load_validation_config_explicit_rag_off():
    """Test load_validation_config can explicitly disable RAG."""
    config = load_validation_config(include_rag_validation=False)

    assert config.check_rag_status is False


# Test create_action_item
def test_create_action_item():
    """Test create_action_item converts ValidationIssue to action item dict."""
    issue = ValidationIssue(
        type="missing_assignee",
        priority=Priority.HIGH,
        description="Assign initiative owner",
        initiative_key="INIT-123",
        initiative_summary="Test Initiative",
        initiative_status="Proposed",
        owner_team="TEAM1",
        team_affected=None,
        epic_key=None,
        current_value=None,
        expected_value=None,
    )

    action = create_action_item(issue, "jane.smith", "U123456")

    assert action["initiative_key"] == "INIT-123"
    assert action["manager"] == "jane.smith"
    assert action["manager_slack_id"] == "U123456"
    assert action["priority"] == 2
    assert action["priority_label"] == "P2"
    assert action["type"] == "missing_assignee"
    assert action["description"] == "Assign initiative owner"


def test_create_action_item_with_team():
    """Test create_action_item includes team information."""
    issue = ValidationIssue(
        type="missing_epic",
        priority=Priority.LOW,
        description="Create epic",
        initiative_key="INIT-456",
        initiative_summary="Another Test",
        initiative_status="Planned",
        owner_team="TEAM1",
        team_affected="TEAM2",
        epic_key=None,
        current_value=None,
        expected_value=None,
    )

    action = create_action_item(issue, "john.doe", "U789012")

    assert action["team_affected"] == "TEAM2"
    assert action["priority_label"] == "P4"
