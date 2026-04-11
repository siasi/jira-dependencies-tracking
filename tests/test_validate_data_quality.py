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
    """Test filtering all active initiatives."""
    from validate_data_quality import filter_initiatives

    initiatives = [
        {'key': 'INIT-1', 'status': 'Proposed', 'quarter': '26 Q1', 'owner_team': 'TEAM1'},
        {'key': 'INIT-2', 'status': 'Planned', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
        {'key': 'INIT-3', 'status': 'In Progress', 'quarter': '26 Q3', 'owner_team': 'TEAM1'},
        {'key': 'INIT-4', 'status': 'Done', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
        {'key': 'INIT-5', 'status': 'Cancelled', 'quarter': '26 Q2', 'owner_team': 'TEAM1'},
    ]

    filtered = filter_initiatives(
        initiatives,
        quarter='26 Q2',
        status_filter=None,
        all_active=True,
        signed_off=set(),
        excluded_teams=[]
    )

    keys = {i['key'] for i in filtered}
    assert 'INIT-1' in keys
    assert 'INIT-2' in keys
    assert 'INIT-3' in keys
    assert 'INIT-4' not in keys  # Done excluded
    assert 'INIT-5' not in keys  # Cancelled excluded


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
    }

    team_mappings = {}  # No mappings needed for this test

    grouped = group_by_manager(issues_by_initiative, team_managers, team_mappings)

    # Should have 2 managers
    assert len(grouped) == 2

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
