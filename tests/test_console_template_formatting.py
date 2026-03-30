"""Tests for console template formatting - ensures proper indentation and newlines."""

import pytest
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from validate_initiative_status import ValidationResult


@pytest.fixture
def jinja_env():
    """Create Jinja2 environment for template rendering."""
    template_dir = Path(__file__).parent.parent / 'templates'
    return Environment(loader=FileSystemLoader(str(template_dir)))


@pytest.fixture
def sample_validation_result():
    """Create sample validation result with all issue types."""
    result = ValidationResult()

    # Add initiative to dependency_mapping with various issues
    result.dependency_mapping.append({
        'key': 'INIT-1',
        'summary': 'Test Initiative 1',
        'owner_team': 'TestTeam',
        'issues': [
            {'type': 'missing_assignee'},
            {'type': 'missing_strategic_objective'},
            {'type': 'invalid_strategic_objective', 'current_value': 'invalid_value'},
            {
                'type': 'epic_count_mismatch',
                'teams_involved': ['TEAM1', 'TEAM2'],
                'teams_with_epics': {'TEAM1'}
            },
            {
                'type': 'missing_rag_status',
                'teams': [
                    {
                        'team_name': 'Team1',
                        'epics': [
                            {'key': 'EPIC-1', 'summary': 'Epic 1'}
                        ]
                    },
                    {
                        'team_name': 'Team2',
                        'epics': [
                            {'key': 'EPIC-2', 'summary': 'Epic 2'}
                        ]
                    }
                ]
            }
        ],
        'contributing_teams': [
            {
                'team_project_key': 'TEAM1',
                'epics': [{'key': 'EPIC-1', 'summary': 'Epic 1', 'rag_status': None}]
            }
        ]
    })

    # Add initiative with epic status issues
    result.planned_regressions.append({
        'key': 'INIT-2',
        'summary': 'Test Initiative 2',
        'owner_team': 'TestTeam',
        'issues': [
            {
                'type': 'red_epics',
                'epics': [
                    {'key': 'EPIC-3', 'summary': 'Red Epic 1', 'rag_status': '🔴'},
                    {'key': 'EPIC-4', 'summary': 'Red Epic 2', 'rag_status': '🔴'}
                ]
            },
            {
                'type': 'yellow_epics',
                'epics': [
                    {'key': 'EPIC-5', 'summary': 'Yellow Epic 1', 'rag_status': '🟡'},
                    {'key': 'EPIC-6', 'summary': 'Yellow Epic 2', 'rag_status': '🟡'}
                ]
            }
        ],
        'contributing_teams': []
    })

    result.total_checked = 2
    result.total_filtered = 0

    return result


def test_action_labels_have_proper_indentation(jinja_env, sample_validation_result):
    """All Action: labels should have exactly 3 spaces of indentation."""
    template = jinja_env.get_template('console.j2')

    output = template.render(
        result=sample_validation_result,
        json_file=Path('test.json'),
        verbose=False,
        team_mappings={'TestTeam': 'TEST'},
        team_managers={'TEST': {'notion_handle': '@TestManager'}}
    )

    # Check all Action: labels have proper indentation
    action_lines = [line for line in output.split('\n') if 'Action:' in line and '⚠️' in line]

    for line in action_lines:
        # Each Action label should start with 3 spaces, then the emoji
        assert line.startswith('   ⚠️'), f"Action label not properly indented: '{line}'"
        # Should not have more than 3 leading spaces
        assert not line.startswith('    ⚠️'), f"Action label over-indented: '{line}'"


def test_action_labels_followed_by_newline(jinja_env, sample_validation_result):
    """Action: labels should be followed by a newline before checkbox items."""
    template = jinja_env.get_template('console.j2')

    output = template.render(
        result=sample_validation_result,
        json_file=Path('test.json'),
        verbose=False,
        team_mappings={'TestTeam': 'TEST'},
        team_managers={'TEST': {'notion_handle': '@TestManager'}}
    )

    lines = output.split('\n')

    for i, line in enumerate(lines):
        if 'Action:' in line and '⚠️' in line:
            # Next line should NOT be another Action label or initiative key
            # It should be either a checkbox or empty line followed by checkbox
            next_line = lines[i + 1] if i + 1 < len(lines) else ''

            # Action line should not immediately be followed by another section header
            assert not next_line.strip().startswith('INIT-'), \
                f"Action label not followed by newline: '{line}' -> '{next_line}'"
            assert not (next_line.strip().startswith('⚠️') and 'Action:' not in line), \
                f"Action label not followed by newline: '{line}' -> '{next_line}'"


def test_checkbox_items_on_separate_lines(jinja_env, sample_validation_result):
    """Each checkbox item should be on its own line."""
    template = jinja_env.get_template('console.j2')

    output = template.render(
        result=sample_validation_result,
        json_file=Path('test.json'),
        verbose=False,
        team_mappings={'TestTeam': 'TEST', 'TEAM1': 'TEAM1', 'TEAM2': 'TEAM2'},
        team_managers={
            'TEST': {'notion_handle': '@TestManager'},
            'TEAM1': {'notion_handle': '@Team1Manager'},
            'TEAM2': {'notion_handle': '@Team2Manager'}
        }
    )

    lines = output.split('\n')

    # Find lines with checkboxes
    checkbox_lines = [line for line in lines if '[ ]' in line]

    # Each checkbox line should not contain multiple checkboxes
    for line in checkbox_lines:
        checkbox_count = line.count('[ ]')
        assert checkbox_count == 1, f"Multiple checkboxes on one line: '{line}'"


def test_epic_status_headers_have_proper_indentation(jinja_env, sample_validation_result):
    """Epic status headers should have exactly 3 spaces of indentation."""
    template = jinja_env.get_template('console.j2')

    output = template.render(
        result=sample_validation_result,
        json_file=Path('test.json'),
        verbose=False,
        team_mappings={'TestTeam': 'TEST'},
        team_managers={'TEST': {'notion_handle': '@TestManager'}}
    )

    # Check epic status headers have proper indentation
    epic_header_keywords = ['Epics with RED status', 'Epics with YELLOW status']
    lines = output.split('\n')

    for line in lines:
        if any(keyword in line for keyword in epic_header_keywords):
            # Each epic header should start with 3 spaces, then the emoji
            assert line.startswith('   ⚠️') or line.startswith('   🔴') or line.startswith('   🟡'), \
                f"Epic status header not properly indented: '{line}'"
            # Should not have more than 3 leading spaces (unless it's the epic item itself with 7 spaces)
            if not line.strip().startswith('-'):
                assert not line.startswith('    ⚠️'), f"Epic status header over-indented: '{line}'"


def test_epic_items_on_separate_lines(jinja_env, sample_validation_result):
    """Each epic item should be on its own line."""
    template = jinja_env.get_template('console.j2')

    output = template.render(
        result=sample_validation_result,
        json_file=Path('test.json'),
        verbose=False,
        team_mappings={'TestTeam': 'TEST'},
        team_managers={'TEST': {'notion_handle': '@TestManager'}}
    )

    lines = output.split('\n')

    # Find epic header lines
    for i, line in enumerate(lines):
        if 'Epics with RED status' in line or 'Epics with YELLOW status' in line:
            # Count how many epic items follow
            epic_count_match = line.split('(')[-1].split(')')[0] if '(' in line else '0'
            try:
                expected_count = int(epic_count_match)
            except ValueError:
                continue

            if expected_count > 0:
                # Check that the next few lines contain epic items, one per line
                epic_items_found = 0
                for j in range(i + 1, min(i + 10, len(lines))):
                    next_line = lines[j]
                    if next_line.strip().startswith('- ') and ('EPIC-' in next_line or 'TEAM' in next_line):
                        epic_items_found += 1
                        # This line should not contain multiple epic keys
                        epic_key_count = next_line.count('🔴') + next_line.count('🟡') + next_line.count('⚠️')
                        if epic_key_count == 0:
                            # Count by looking for epic key patterns
                            epic_key_count = len([word for word in next_line.split() if '-' in word and word[0].isupper()])
                        if epic_key_count > 1:
                            pytest.fail(f"Multiple epics on one line: '{next_line}'")
                    elif next_line.strip() and not next_line.strip().startswith('INIT-'):
                        # Continue looking
                        continue
                    else:
                        # Reached end of epic list or next initiative
                        break


def test_missing_rag_status_items_on_separate_lines(jinja_env, sample_validation_result):
    """Missing RAG status action items should be on separate lines."""
    template = jinja_env.get_template('console.j2')

    output = template.render(
        result=sample_validation_result,
        json_file=Path('test.json'),
        verbose=False,
        team_mappings={'TestTeam': 'TEST'},
        team_managers={'TEST': {'notion_handle': '@TestManager'}}
    )

    lines = output.split('\n')

    # Find Missing RAG status sections
    for i, line in enumerate(lines):
        if 'Missing RAG status - Action:' in line:
            # Check next lines for RAG status checkboxes
            for j in range(i + 1, min(i + 10, len(lines))):
                next_line = lines[j]
                if '[ ]' in next_line and 'RAG status' in next_line:
                    # Should only have one checkbox per line
                    assert next_line.count('[ ]') == 1, \
                        f"Multiple RAG status items on one line: '{next_line}'"
                elif next_line.strip() and next_line.strip().startswith('⚠️') and 'Action:' not in next_line:
                    # Reached next section
                    break


def test_no_excessive_blank_lines(jinja_env, sample_validation_result):
    """Should not have more than 3 consecutive blank lines."""
    template = jinja_env.get_template('console.j2')

    output = template.render(
        result=sample_validation_result,
        json_file=Path('test.json'),
        verbose=False,
        team_mappings={'TestTeam': 'TEST'},
        team_managers={'TEST': {'notion_handle': '@TestManager'}}
    )

    lines = output.split('\n')
    consecutive_blank = 0

    for line in lines:
        if not line.strip():
            consecutive_blank += 1
            assert consecutive_blank <= 3, \
                f"More than 3 consecutive blank lines found in output"
        else:
            consecutive_blank = 0


def test_consistent_indentation_throughout(jinja_env, sample_validation_result):
    """All issue sections should use consistent indentation."""
    template = jinja_env.get_template('console.j2')

    output = template.render(
        result=sample_validation_result,
        json_file=Path('test.json'),
        verbose=False,
        team_mappings={'TestTeam': 'TEST'},
        team_managers={'TEST': {'notion_handle': '@TestManager'}}
    )

    lines = output.split('\n')

    # Collect all indentation levels for section headers (with emoji warnings)
    section_indents = []
    for line in lines:
        if ('⚠️' in line or '🔴' in line or '🟡' in line) and \
           ('Action:' in line or 'Epics with' in line):
            # Count leading spaces
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            section_indents.append(indent)

    # All section headers should have the same indentation (3 spaces)
    if section_indents:
        assert all(indent == 3 for indent in section_indents), \
            f"Inconsistent indentation found. Indents: {set(section_indents)}"


def test_missing_dependencies_checkboxes_properly_formatted(jinja_env, sample_validation_result):
    """Missing dependencies checkboxes should each be on their own line with proper indentation."""
    template = jinja_env.get_template('console.j2')

    output = template.render(
        result=sample_validation_result,
        json_file=Path('test.json'),
        verbose=False,
        team_mappings={'TestTeam': 'TEST', 'TEAM1': 'TEAM1', 'TEAM2': 'TEAM2'},
        team_managers={
            'TEST': {'notion_handle': '@TestManager'},
            'TEAM1': {'notion_handle': '@Team1Manager'},
            'TEAM2': {'notion_handle': '@Team2Manager'}
        }
    )

    lines = output.split('\n')

    # Find Missing dependencies sections
    for i, line in enumerate(lines):
        if 'Missing dependencies - Action:' in line:
            # Check the next few lines for checkboxes about creating epics
            for j in range(i + 1, min(i + 10, len(lines))):
                next_line = lines[j]
                if '[ ]' in next_line and 'to create epic' in next_line:
                    # Should be properly indented (7 spaces for checkbox content)
                    assert next_line.startswith('       [ ]'), \
                        f"Missing dependencies checkbox not properly indented: '{next_line}'"
                    # Should not have multiple teams on same line
                    assert next_line.count('to create epic') == 1, \
                        f"Multiple create epic actions on one line: '{next_line}'"
                elif next_line.strip() and next_line.strip().startswith('⚠️'):
                    # Reached next section
                    break
