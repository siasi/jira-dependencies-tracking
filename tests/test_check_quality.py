"""Tests for data quality validation script."""

import json
import pytest
import yaml
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from io import StringIO


# Test CLI Argument Parsing
def test_parse_args_minimal():
    """Test CLI parsing with minimal required arguments."""
    from validate_data_quality import parse_args

    args = parse_args(['--quarter', '26 Q2'])

    assert args.quarter == '26 Q2'
    assert args.status is None
    assert args.all_active is False
    assert args.slack is False
    assert args.verbose is False


def test_parse_args_with_status_filter():
    """Test CLI parsing with status filter."""
    from validate_data_quality import parse_args

    args = parse_args(['--quarter', '26 Q2', '--status', 'Proposed'])

    assert args.quarter == '26 Q2'
    assert args.status == 'Proposed'


def test_parse_args_with_all_active():
    """Test CLI parsing with --all-active flag."""
    from validate_data_quality import parse_args

    args = parse_args(['--quarter', '26 Q2', '--all-active'])

    assert args.all_active is True


def test_parse_args_with_slack():
    """Test CLI parsing with --slack flag."""
    from validate_data_quality import parse_args

    args = parse_args(['--quarter', '26 Q2', '--slack'])

    assert args.slack is True


def test_parse_args_with_verbose():
    """Test CLI parsing with --verbose flag."""
    from validate_data_quality import parse_args

    args = parse_args(['--quarter', '26 Q2', '--verbose'])

    assert args.verbose is True


# Test Data Loading
def test_load_latest_extract():
    """Test finding latest data extract."""
    from validate_data_quality import find_latest_extract

    # Should find most recent file in data directory
    latest = find_latest_extract()

    if latest:
        assert latest.exists()
        assert latest.suffix == '.json'


def test_load_signed_off_initiatives():
    """Test loading initiative exceptions."""
    from validate_data_quality import load_signed_off_initiatives

    exceptions = load_signed_off_initiatives()

    assert isinstance(exceptions, set)
    # Should be empty or contain INIT keys
    for key in exceptions:
        assert key.startswith('INIT-') or key == ''


def test_load_excluded_teams():
    """Test loading excluded teams."""
    from validate_data_quality import load_excluded_teams

    excluded = load_excluded_teams()

    assert isinstance(excluded, list)
    # Should be a list of team names


# Test Filtering Logic
def test_filter_initiatives_by_quarter():
    """Test filtering by quarter (Planned + In Progress)."""
    from validate_data_quality import filter_initiatives

    initiatives = [
        {'key': 'INIT-1', 'status': 'Planned', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
        {'key': 'INIT-2', 'status': 'Planned', 'quarter': '26 Q1', 'owner_team': 'TEAM1'},
        {'key': 'INIT-3', 'status': 'In Progress', 'quarter': '26 Q1', 'owner_team': 'TEAM1'},
        {'key': 'INIT-4', 'status': 'Done', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
    ]

    filtered = filter_initiatives(
        initiatives,
        quarter='26 Q2',
        status_filter=None,
        all_active=False,
        signed_off=set(),
        excluded_teams=[]
    )

    keys = {i['key'] for i in filtered}
    assert 'INIT-1' in keys  # Planned + matching quarter
    assert 'INIT-2' not in keys  # Planned but wrong quarter
    assert 'INIT-3' in keys  # In Progress (any quarter)
    assert 'INIT-4' not in keys  # Done (excluded unless specified)


def test_filter_initiatives_by_status():
    """Test filtering by specific status."""
    from validate_data_quality import filter_initiatives

    initiatives = [
        {'key': 'INIT-1', 'status': 'Proposed', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
        {'key': 'INIT-2', 'status': 'Planned', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
        {'key': 'INIT-3', 'status': 'In Progress', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
    ]

    filtered = filter_initiatives(
        initiatives,
        quarter='26 Q2',
        status_filter='Proposed',
        all_active=False,
        signed_off=set(),
        excluded_teams=[]
    )

    keys = {i['key'] for i in filtered}
    assert 'INIT-1' in keys
    assert 'INIT-2' not in keys
    assert 'INIT-3' not in keys


def test_filter_initiatives_all_active():
    """Test filtering all active initiatives (any quarter)."""
    from validate_data_quality import filter_initiatives

    initiatives = [
        {'key': 'INIT-1', 'status': 'Proposed', 'quarter': '26 Q1', 'owner_team': 'TEAM1'},
        {'key': 'INIT-2', 'status': 'Planned', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
        {'key': 'INIT-3', 'status': 'In Progress', 'quarter': '26 Q3', 'owner_team': 'TEAM1'},
        {'key': 'INIT-4', 'status': 'Done', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
        {'key': 'INIT-5', 'status': 'Cancelled', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
    ]

    # Test 1: --all-active without quarter (any quarter)
    filtered = filter_initiatives(
        initiatives,
        quarter=None,  # No quarter filter
        status_filter=None,
        all_active=True,
        signed_off=set(),
        excluded_teams=[]
    )

    keys = {i['key'] for i in filtered}
    assert 'INIT-1' in keys  # Proposed, any quarter
    assert 'INIT-2' in keys  # Planned, any quarter
    assert 'INIT-3' in keys  # In Progress, any quarter
    assert 'INIT-4' not in keys  # Done excluded
    assert 'INIT-5' not in keys  # Cancelled excluded


def test_filter_initiatives_all_active_with_quarter():
    """Test filtering all active initiatives with quarter filter (AND logic)."""
    from validate_data_quality import filter_initiatives

    initiatives = [
        {'key': 'INIT-1', 'status': 'Proposed', 'quarter': '26 Q1', 'owner_team': 'TEAM1'},
        {'key': 'INIT-2', 'status': 'Planned', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
        {'key': 'INIT-3', 'status': 'In Progress', 'quarter': '26 Q3', 'owner_team': 'TEAM1'},
        {'key': 'INIT-4', 'status': 'Done', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
        {'key': 'INIT-5', 'status': 'Cancelled', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
    ]

    # Test 2: --all-active --quarter "26 Q2" (AND logic)
    filtered = filter_initiatives(
        initiatives,
        quarter='26 Q2',
        status_filter=None,
        all_active=True,
        signed_off=set(),
        excluded_teams=[]
    )

    keys = {i['key'] for i in filtered}
    assert 'INIT-1' not in keys  # Q1, not Q2
    assert 'INIT-2' in keys  # Planned AND Q2
    assert 'INIT-3' not in keys  # Q3, not Q2
    assert 'INIT-4' not in keys  # Done excluded
    assert 'INIT-5' not in keys  # Cancelled excluded


def test_filter_initiatives_status_with_quarter():
    """Test filtering by status with quarter filter (AND logic)."""
    from validate_data_quality import filter_initiatives

    initiatives = [
        {'key': 'INIT-1', 'status': 'Proposed', 'quarter': '26 Q1', 'owner_team': 'TEAM1'},
        {'key': 'INIT-2', 'status': 'Proposed', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
        {'key': 'INIT-3', 'status': 'Planned', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
        {'key': 'INIT-4', 'status': 'In Progress', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
    ]

    # Test: --status Proposed --quarter "26 Q2" (AND logic)
    filtered = filter_initiatives(
        initiatives,
        quarter='26 Q2',
        status_filter='Proposed',
        all_active=False,
        signed_off=set(),
        excluded_teams=[]
    )

    keys = {i['key'] for i in filtered}
    assert 'INIT-1' not in keys  # Proposed but Q1
    assert 'INIT-2' in keys  # Proposed AND Q2
    assert 'INIT-3' not in keys  # Q2 but not Proposed
    assert 'INIT-4' not in keys  # Q2 but not Proposed


def test_filter_initiatives_exclude_signed_off():
    """Test filtering excludes signed-off exceptions."""
    from validate_data_quality import filter_initiatives

    initiatives = [
        {'key': 'INIT-1', 'status': 'Planned', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
        {'key': 'INIT-2', 'status': 'Planned', 'quarter': '26 Q2', 'owner_team': 'TEAM2'},
    ]

    filtered = filter_initiatives(
        initiatives,
        quarter='26 Q2',
        status_filter=None,
        all_active=False,
        signed_off={'INIT-1'}  # INIT-1 is signed off
    )

    keys = {i['key'] for i in filtered}
    assert 'INIT-1' not in keys
    assert 'INIT-2' in keys


def test_filter_initiatives_exclude_teams():
    """Test filtering excludes initiatives from excluded teams."""
    from validate_data_quality import filter_initiatives

    initiatives = [
        {'key': 'INIT-1', 'status': 'Planned', 'quarter': '26 Q2', 'owner_team': 'IT'},
        {'key': 'INIT-2', 'status': 'Planned', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
        {'key': 'INIT-3', 'status': 'Planned', 'quarter': '26 Q2', 'owner_team': 'Security Engineering'},
    ]

    filtered = filter_initiatives(
        initiatives,
        quarter='26 Q2',
        status_filter=None,
        all_active=False,
        signed_off=set(),
        excluded_teams=['IT', 'Security Engineering']
    )

    keys = {i['key'] for i in filtered}
    assert 'INIT-1' not in keys  # IT excluded
    assert 'INIT-2' in keys      # TEAM1 not excluded
    assert 'INIT-3' not in keys  # Security Engineering excluded


# Test Validation Integration
def test_validate_initiatives():
    """Test validating initiatives using shared validation library."""
    from validate_data_quality import validate_initiatives
    from lib.validation import load_validation_config

    config = load_validation_config(status_filter='Proposed')

    initiatives = [
        {
            'key': 'INIT-1',
            'summary': 'Test Initiative',
            'status': 'Proposed',
            'owner_team': None,  # Missing owner
            'assignee': 'user@example.com',
            'strategic_objective': '2026_fuel_regulated',
            'teams_involved': ['TEAM1'],
        },
        {
            'key': 'INIT-2',
            'summary': 'Good Initiative',
            'status': 'Proposed',
            'owner_team': 'TEAM1',
            'assignee': 'user@example.com',
            'strategic_objective': '2026_fuel_regulated',
            'teams_involved': ['TEAM1'],
        },
    ]

    results = validate_initiatives(initiatives, config)

    # Should have issues for INIT-1 only
    assert 'INIT-1' in results
    assert len(results['INIT-1']) > 0
    assert results['INIT-1'][0].type == 'missing_owner_team'

    # INIT-2 might have other issues but should have an owner
    if 'INIT-2' in results:
        owner_issues = [i for i in results['INIT-2'] if i.type == 'missing_owner_team']
        assert len(owner_issues) == 0


# Test Manager Grouping
def test_group_by_manager():
    """Test grouping action items by manager."""
    from validate_data_quality import group_by_manager
    from lib.validation import ValidationIssue, Priority

    issues_by_initiative = {
        'INIT-1': [
            ValidationIssue(
                type='missing_assignee',
                priority=Priority.HIGH,
                description='Assign owner',
                initiative_key='INIT-1',
                initiative_summary='Test 1',
                initiative_status='Proposed',
                owner_team='TEAM1',
            )
        ],
        'INIT-2': [
            ValidationIssue(
                type='missing_epic',
                priority=Priority.LOW,
                description='Create epic',
                initiative_key='INIT-2',
                initiative_summary='Test 2',
                initiative_status='Planned',
                owner_team='TEAM2',
                team_affected='TEAM3',
            )
        ],
    }

    team_managers = {
        'TEAM1': {'notion_handle': '@Manager A', 'slack_id': 'U111'},
        'TEAM2': {'notion_handle': '@Manager B', 'slack_id': 'U222'},
        'TEAM3': {'notion_handle': '@Manager C', 'slack_id': 'U333'},
    }

    team_mappings = {}  # No mappings needed for this test

    grouped = group_by_manager(issues_by_initiative, team_managers, team_mappings)

    # Should have 2 managers (TEAM1 for INIT-1, TEAM2 for INIT-2)
    # All issues for an initiative go to the owner team's manager
    assert len(grouped) == 2
    assert 'U111' in grouped  # TEAM1 manager gets issues for INIT-1 (they own it)
    assert 'U222' in grouped  # TEAM2 manager gets issues for INIT-2 (they own it)
    assert 'U333' not in grouped  # TEAM3 manager gets nothing (dependency issue appears under owner)

    # Check structure
    for manager_id, data in grouped.items():
        assert 'manager_name' in data
        assert 'slack_id' in data
        assert 'initiatives' in data
        assert isinstance(data['initiatives'], dict)


# Test Console Output Formatting
def test_format_console_output():
    """Test console output formatting."""
    from validate_data_quality import format_console_output
    from lib.validation import ValidationIssue, Priority

    grouped_data = {
        'U111': {
            'manager_name': 'Manager A',
            'slack_id': 'U111',
            'team': 'TEAM1',
            'initiatives': {
                'INIT-1': {
                    'summary': 'Test Initiative',
                    'status': 'Proposed',
                    'quarter': '26 Q2',
                    'issues': [
                        ValidationIssue(
                            type='missing_assignee',
                            priority=Priority.HIGH,
                            description='Assign owner',
                            initiative_key='INIT-1',
                            initiative_summary='Test Initiative',
                            initiative_status='Proposed',
                            owner_team='TEAM1',
                        )
                    ]
                }
            }
        }
    }

    metadata = {
        'quarter': '26 Q2',
        'filter': 'In Progress (all) + Planned (26 Q2)',
        'initiatives_analyzed': 10,
        'initiatives_with_issues': 5,
        'exceptions_skipped': 2,
    }

    output = format_console_output(grouped_data, metadata)

    assert 'DATA QUALITY VALIDATION REPORT' in output
    assert 'Quarter: 26 Q2' in output
    assert 'Manager A' in output
    assert 'INIT-1' in output
    assert 'Test Initiative' in output
    assert 'P2' in output  # Priority HIGH = 2


# Test Slack Message Generation
def test_generate_slack_messages():
    """Test Slack message generation."""
    from validate_data_quality import generate_slack_messages
    from lib.validation import ValidationIssue, Priority

    grouped_data = {
        'U111': {
            'manager_name': 'Manager A',
            'slack_id': 'U111',
            'team': 'TEAM1',
            'initiatives': {
                'INIT-1': {
                    'summary': 'Test Initiative',
                    'status': 'Proposed',
                    'quarter': '26 Q2',
                    'issues': [
                        ValidationIssue(
                            type='missing_assignee',
                            priority=Priority.HIGH,
                            description='Assign owner',
                            initiative_key='INIT-1',
                            initiative_summary='Test Initiative',
                            initiative_status='Proposed',
                            owner_team='TEAM1',
                        )
                    ]
                }
            }
        }
    }

    messages = generate_slack_messages(grouped_data)

    assert len(messages) == 1
    assert messages[0]['slack_id'] == 'U111'
    assert messages[0]['manager_name'] == 'Manager A'
    assert messages[0]['total_actions'] >= 1
    assert messages[0]['total_initiatives'] == 1


def test_generate_slack_messages_filters_by_responsibility():
    """Test that Slack messages are filtered by who is responsible for the action."""
    from validate_data_quality import generate_slack_messages
    from lib.validation import ValidationIssue, Priority

    grouped_data = {
        'U111': {
            'manager_name': 'Manager A',
            'slack_id': 'U111',
            'team': 'TEAM1',
            'initiatives': {
                'INIT-1': {
                    'summary': 'Test Initiative',
                    'status': 'Proposed',
                    'quarter': '26 Q2',
                    'issues': [
                        # Owner action - Manager A should receive this
                        ValidationIssue(
                            type='missing_assignee',
                            priority=Priority.HIGH,
                            description='Assign owner',
                            initiative_key='INIT-1',
                            initiative_summary='Test Initiative',
                            initiative_status='Proposed',
                            owner_team='TEAM1',
                        ),
                        # Dependency action for TEAM2 - Manager A should NOT receive this
                        ValidationIssue(
                            type='missing_epic',
                            priority=Priority.LOW,
                            description='Create epic',
                            initiative_key='INIT-1',
                            initiative_summary='Test Initiative',
                            initiative_status='Proposed',
                            owner_team='TEAM1',
                            team_affected='TEAM2',  # Different team
                        ),
                    ]
                }
            }
        }
    }

    messages = generate_slack_messages(grouped_data)

    # Should only have 1 message for Manager A
    assert len(messages) == 1
    assert messages[0]['slack_id'] == 'U111'

    # Should only have 1 action (missing_assignee), not 2
    # The missing_epic for TEAM2 should not be included
    assert messages[0]['total_actions'] == 1

    # Verify the action is the owner action
    initiative = messages[0]['teams'][0]['initiatives'][0]
    assert len(initiative['actions']) == 1
    assert initiative['actions'][0]['action_type'] == 'missing_assignee'


# Test Output File Generation
def test_save_slack_output(tmp_path):
    """Test saving Slack output to file."""
    from validate_data_quality import save_slack_output

    messages_content = """Recipient: U111
Message: Test message

---
"""

    output_dir = tmp_path / "output" / "data_quality"
    output_dir.mkdir(parents=True, exist_ok=True)

    filepath = save_slack_output(messages_content, output_dir)

    assert filepath.exists()
    assert filepath.suffix == '.txt'
    assert 'data_quality' in filepath.name

    content = filepath.read_text()
    assert 'Recipient: U111' in content


# Test Priority Summary
def test_calculate_priority_summary():
    """Test calculating priority summary from grouped data."""
    from validate_data_quality import calculate_priority_summary
    from lib.validation import ValidationIssue, Priority

    grouped_data = {
        'U111': {
            'initiatives': {
                'INIT-1': {
                    'issues': [
                        ValidationIssue(
                            type='missing_owner_team',
                            priority=Priority.CRITICAL,
                            description='',
                            initiative_key='INIT-1',
                            initiative_summary='',
                            initiative_status='',
                            owner_team=None,
                        ),
                        ValidationIssue(
                            type='missing_assignee',
                            priority=Priority.HIGH,
                            description='',
                            initiative_key='INIT-1',
                            initiative_summary='',
                            initiative_status='',
                            owner_team='TEAM1',
                        ),
                    ]
                }
            }
        },
        'U222': {
            'initiatives': {
                'INIT-2': {
                    'issues': [
                        ValidationIssue(
                            type='missing_epic',
                            priority=Priority.LOW,
                            description='',
                            initiative_key='INIT-2',
                            initiative_summary='',
                            initiative_status='',
                            owner_team='TEAM2',
                        ),
                    ]
                }
            }
        }
    }

    summary = calculate_priority_summary(grouped_data)

    assert summary['P1'] == 1  # CRITICAL
    assert summary['P2'] == 1  # HIGH
    assert summary['P4'] == 1  # LOW


# Test Edge Cases
def test_filter_initiatives_empty_list():
    """Test filtering with empty initiative list."""
    from validate_data_quality import filter_initiatives

    filtered = filter_initiatives([], '26 Q2', None, False, set(), [])

    assert len(filtered) == 0


def test_validate_initiatives_empty_list():
    """Test validating empty initiative list."""
    from validate_data_quality import validate_initiatives
    from lib.validation import load_validation_config

    config = load_validation_config()
    results = validate_initiatives([], config)

    assert len(results) == 0


def test_group_by_manager_no_managers():
    """Test grouping when manager info is missing."""
    from validate_data_quality import group_by_manager
    from lib.validation import ValidationIssue, Priority

    issues_by_initiative = {
        'INIT-1': [
            ValidationIssue(
                type='missing_assignee',
                priority=Priority.HIGH,
                description='',
                initiative_key='INIT-1',
                initiative_summary='',
                initiative_status='',
                owner_team='UNKNOWN_TEAM',
            )
        ],
    }

    team_managers = {}  # No managers defined
    team_mappings = {}  # No mappings

    grouped = group_by_manager(issues_by_initiative, team_managers, team_mappings)

    # Should handle gracefully (might skip or use default)
    assert isinstance(grouped, dict)


def test_group_by_manager_with_team_mappings():
    """Test that display names are mapped to project keys before manager lookup."""
    from validate_data_quality import group_by_manager
    from lib.validation import ValidationIssue, Priority

    issues_by_initiative = {
        'INIT-1': [
            ValidationIssue(
                type='missing_assignee',
                priority=Priority.MEDIUM,
                description='Assign owner',
                initiative_key='INIT-1',
                initiative_summary='Test Initiative',
                initiative_status='Proposed',
                owner_team='MAP',  # Display name
            )
        ],
    }

    # Manager info uses project keys
    team_managers = {
        'MAPS': {'notion_handle': '@Kevin Plattern', 'slack_id': 'U013U600TT9'},
    }

    # Mapping from display name to project key
    team_mappings = {
        'MAP': 'MAPS',
    }

    grouped = group_by_manager(issues_by_initiative, team_managers, team_mappings)

    # Should find the manager via the mapping
    assert len(grouped) == 1
    assert 'U013U600TT9' in grouped
    assert grouped['U013U600TT9']['manager_name'] == 'Kevin Plattern'
    assert grouped['U013U600TT9']['team'] == 'MAP'  # Original display name preserved


def test_is_owned_initiative():
    """Test initiative ownership determination."""
    from validate_data_quality import is_owned_initiative
    from lib.validation import ValidationIssue, Priority

    team_mappings = {}  # No mappings for simple test

    # Manager owns initiative
    owner_issue = ValidationIssue(
        type='missing_assignee',
        priority=Priority.CRITICAL,
        description='Assign owner',
        initiative_key='INIT-1',
        initiative_summary='Test',
        initiative_status='Planned',
        owner_team='TEAM1',
    )
    assert is_owned_initiative(owner_issue, 'TEAM1', team_mappings) is True

    # Manager doesn't own initiative
    dependency_issue = ValidationIssue(
        type='missing_epic',
        priority=Priority.CRITICAL,
        description='Create epic',
        initiative_key='INIT-1',
        initiative_summary='Test',
        initiative_status='Planned',
        owner_team='TEAM1',
        team_affected='TEAM2',
    )
    assert is_owned_initiative(dependency_issue, 'TEAM2', team_mappings) is False


# Test --me flag functionality
def test_parse_args_with_me_flag():
    """Test CLI parsing with --me flag."""
    from validate_data_quality import parse_args

    args = parse_args(['--quarter', '26 Q2', '--me'])

    assert args.me is True
    assert args.quarter == '26 Q2'


def test_load_my_teams_from_config(tmp_path):
    """Test loading my_teams from configuration."""
    from validate_data_quality import load_my_teams

    # Create temporary config
    config_dir = tmp_path / 'config'
    config_dir.mkdir()
    config_file = config_dir / 'team_mappings.yaml'
    
    config_data = {
        'my_teams': ['CONSOLE', 'PAYINS']
    }
    
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f)
    
    # Test with patched config path
    with patch('validate_data_quality.Path') as mock_path:
        mock_path.return_value = config_file
        teams = load_my_teams()
    
    assert teams == ['CONSOLE', 'PAYINS']


def test_load_my_teams_missing_config():
    """Test loading my_teams when config doesn't exist."""
    from validate_data_quality import load_my_teams
    
    with patch('validate_data_quality.Path') as mock_path:
        mock_path.return_value.exists.return_value = False
        teams = load_my_teams()
    
    assert teams == []


def test_filter_grouped_data_by_teams():
    """Test filtering grouped data by my teams."""
    from validate_data_quality import filter_grouped_data_by_teams
    from lib.validation import ValidationIssue, Priority
    
    # Create test data with two managers
    grouped_data = {
        'U123': {
            'manager_name': 'Manager A',
            'team': 'CONSOLE',
            'initiatives': {
                'INIT-1': {
                    'summary': 'Test Initiative 1',
                    'status': 'Proposed',
                    'issues': [
                        ValidationIssue(
                            type='missing_assignee',
                            priority=Priority.HIGH,
                            description='Missing assignee',
                            initiative_key='INIT-1',
                            initiative_summary='Test Initiative 1',
                            initiative_status='Proposed',
                            owner_team='CONSOLE'
                        )
                    ]
                }
            }
        },
        'U456': {
            'manager_name': 'Manager B',
            'team': 'PAYINS',
            'initiatives': {
                'INIT-2': {
                    'summary': 'Test Initiative 2',
                    'status': 'Planned',
                    'issues': [
                        ValidationIssue(
                            type='missing_epic',
                            priority=Priority.CRITICAL,
                            description='Missing epic',
                            initiative_key='INIT-2',
                            initiative_summary='Test Initiative 2',
                            initiative_status='Planned',
                            owner_team='PAYINS'
                        )
                    ]
                }
            }
        }
    }
    
    # Filter to only CONSOLE team
    my_teams = ['CONSOLE']
    filtered, filtered_count, total_count = filter_grouped_data_by_teams(grouped_data, my_teams)
    
    # Should only have Manager A (CONSOLE team)
    assert len(filtered) == 1
    assert 'U123' in filtered
    assert 'U456' not in filtered
    
    # Counts should be correct
    assert filtered_count == 1  # Only CONSOLE issues
    assert total_count == 2  # Total issues across all teams


def test_filter_grouped_data_with_empty_teams():
    """Test filtering with empty my_teams list returns all data."""
    from validate_data_quality import filter_grouped_data_by_teams
    from lib.validation import ValidationIssue, Priority
    
    grouped_data = {
        'U123': {
            'manager_name': 'Manager A',
            'team': 'CONSOLE',
            'initiatives': {
                'INIT-1': {
                    'summary': 'Test',
                    'status': 'Proposed',
                    'issues': [
                        ValidationIssue(
                            type='missing_assignee',
                            priority=Priority.HIGH,
                            description='Missing assignee',
                            initiative_key='INIT-1',
                            initiative_summary='Test',
                            initiative_status='Proposed',
                            owner_team='CONSOLE'
                        )
                    ]
                }
            }
        }
    }
    
    # Empty teams list should return all data
    filtered, filtered_count, total_count = filter_grouped_data_by_teams(grouped_data, [])
    
    assert filtered == grouped_data
    assert filtered_count == total_count == 1


def test_console_output_shows_filtered_count():
    """Test that console output displays filtered vs total counts."""
    from validate_data_quality import format_console_output
    
    grouped_data = {}
    metadata = {
        'quarter': '26 Q2',
        'filter': 'Status: Proposed',
        'initiatives_analyzed': 10,
        'initiatives_with_issues': 5,
        'exceptions_skipped': 0,
        'excluded_teams': [],
        'filtered_count': 3,
        'total_count': 10,
    }
    
    output = format_console_output(grouped_data, metadata)
    
    # Should show filtered count
    assert '3 action items for your teams' in output
    assert '10 total' in output


def test_console_output_without_filtering():
    """Test that console output shows normal count when not filtering."""
    from validate_data_quality import format_console_output
    
    grouped_data = {}
    metadata = {
        'quarter': '26 Q2',
        'filter': 'Status: Proposed',
        'initiatives_analyzed': 10,
        'initiatives_with_issues': 5,
        'exceptions_skipped': 0,
        'excluded_teams': [],
        'filtered_count': None,
        'total_count': None,
    }
    
    output = format_console_output(grouped_data, metadata)
    
    # Should not show filtered count
    assert 'for your teams' not in output
    assert '0 action items):' in output  # Normal count (0 because grouped_data is empty)
