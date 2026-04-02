"""Tests for analyze_workload.py HTML dashboard generation."""

import pytest
from pathlib import Path
import tempfile
import json
from analyze_workload import generate_dashboard_csv, generate_html_dashboard, analyze_workload


def test_generate_dashboard_csv_basic():
    """Test CSV generation with basic workload data."""
    analysis = {
        'team_details': {
            'TeamA': {
                'leading': ['INIT-1', 'INIT-2'],
                'contributing': ['INIT-3']
            },
            'TeamB': {
                'leading': ['INIT-3'],
                'contributing': []
            }
        }
    }

    initiative_summaries = {
        'INIT-1': 'First initiative',
        'INIT-2': 'Second initiative',
        'INIT-3': 'Third initiative'
    }

    initiative_strategic_objectives = {
        'INIT-1': '2026_scale_ecom',
        'INIT-2': 'engineering_pillars',
        'INIT-3': '2026_network'
    }

    initiative_owner_teams = {
        'INIT-1': 'TeamA',
        'INIT-2': 'TeamA',
        'INIT-3': 'TeamB'
    }

    initiative_contributing_teams = {
        'INIT-1': [],
        'INIT-2': [],
        'INIT-3': ['TeamA']
    }

    csv_output = generate_dashboard_csv(
        analysis,
        initiative_summaries,
        initiative_strategic_objectives,
        initiative_owner_teams,
        initiative_contributing_teams
    )

    # Check header
    assert 'initiative_key,initiative_name,strategic_objective,leading_team,contributing_teams' in csv_output

    # Check data rows
    assert 'INIT-1,First initiative,2026_scale_ecom,TeamA,' in csv_output
    assert 'INIT-2,Second initiative,engineering_pillars,TeamA,' in csv_output
    assert 'INIT-3,Third initiative,2026_network,TeamB,TeamA' in csv_output


def test_generate_dashboard_csv_multiple_contributors():
    """Test CSV generation with multiple contributing teams."""
    analysis = {
        'team_details': {
            'TeamA': {
                'leading': ['INIT-1'],
                'contributing': []
            }
        }
    }

    initiative_summaries = {
        'INIT-1': 'Initiative with multiple contributors'
    }

    initiative_strategic_objectives = {
        'INIT-1': '2026_scale_ecom'
    }

    initiative_owner_teams = {
        'INIT-1': 'TeamA'
    }

    initiative_contributing_teams = {
        'INIT-1': ['TeamB', 'TeamC', 'TeamD']
    }

    csv_output = generate_dashboard_csv(
        analysis,
        initiative_summaries,
        initiative_strategic_objectives,
        initiative_owner_teams,
        initiative_contributing_teams
    )

    # Check contributing teams are comma-separated (CSV writer may quote)
    assert 'INIT-1,Initiative with multiple contributors,2026_scale_ecom,TeamA' in csv_output
    assert 'TeamB,TeamC,TeamD' in csv_output


def test_generate_dashboard_csv_empty_strategic_objective():
    """Test CSV generation with missing strategic objective."""
    analysis = {
        'team_details': {
            'TeamA': {
                'leading': ['INIT-1'],
                'contributing': []
            }
        }
    }

    initiative_summaries = {
        'INIT-1': 'Initiative without objective'
    }

    initiative_strategic_objectives = {
        'INIT-1': ''
    }

    initiative_owner_teams = {
        'INIT-1': 'TeamA'
    }

    initiative_contributing_teams = {
        'INIT-1': []
    }

    csv_output = generate_dashboard_csv(
        analysis,
        initiative_summaries,
        initiative_strategic_objectives,
        initiative_owner_teams,
        initiative_contributing_teams
    )

    # Check empty strategic objective is handled
    assert 'INIT-1,Initiative without objective,,TeamA,' in csv_output


def test_generate_html_dashboard_escapes_special_chars():
    """Test HTML generation properly escapes backticks and other special chars in CSV data."""
    analysis = {
        'team_details': {
            'TeamA': {
                'leading': ['INIT-1'],
                'contributing': []
            }
        }
    }

    # Initiative name contains backticks, backslashes, and ${} that need escaping
    initiative_summaries = {
        'INIT-1': 'Test `backticks` and ${template} and \\backslash'
    }

    initiative_strategic_objectives = {
        'INIT-1': '2026_scale_ecom'
    }

    initiative_owner_teams = {
        'INIT-1': 'TeamA'
    }

    initiative_contributing_teams = {
        'INIT-1': []
    }

    initiative_urls = {
        'INIT-1': 'https://example.atlassian.net/browse/INIT-1'
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        output_file = Path(f.name)

    try:
        # Generate HTML
        generate_html_dashboard(
            analysis,
            initiative_summaries,
            initiative_urls,
            initiative_strategic_objectives,
            initiative_owner_teams,
            initiative_contributing_teams,
            output_file,
            Path('test.json')
        )

        # Read generated HTML
        with open(output_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Verify backticks are escaped
        assert '\\`backticks\\`' in html_content, "Backticks should be escaped"

        # Verify ${} is escaped
        assert '\\${template}' in html_content, "Template expressions should be escaped"

        # Verify backslashes are double-escaped (original backslash becomes \\\\)
        assert '\\\\backslash' in html_content, "Backslashes should be escaped"

        # Verify no unescaped backticks in the RAW constant
        import re
        # Find the RAW constant
        raw_match = re.search(r'const RAW = `(.+?)`;', html_content, re.DOTALL)
        assert raw_match, "RAW constant should exist"
        raw_content = raw_match.group(1)

        # Count backticks - should have none unescaped (all should be \`)
        unescaped_backticks = [m.start() for m in re.finditer(r'(?<!\\)`', raw_content)]
        assert len(unescaped_backticks) == 0, f"Found unescaped backticks at positions: {unescaped_backticks}"

    finally:
        # Clean up temp file
        if output_file.exists():
            output_file.unlink()


def test_csv_export_file_creation():
    """Test CSV export creates a valid file."""
    analysis = {
        'team_details': {
            'TeamA': {
                'leading': ['INIT-1', 'INIT-2'],
                'contributing': []
            },
            'TeamB': {
                'leading': [],
                'contributing': ['INIT-1']
            }
        }
    }

    initiative_summaries = {
        'INIT-1': 'First initiative',
        'INIT-2': 'Second initiative'
    }

    initiative_strategic_objectives = {
        'INIT-1': '2026_scale_ecom',
        'INIT-2': 'engineering_pillars'
    }

    initiative_owner_teams = {
        'INIT-1': 'TeamA',
        'INIT-2': 'TeamA'
    }

    initiative_contributing_teams = {
        'INIT-1': ['TeamB'],
        'INIT-2': []
    }

    csv_output = generate_dashboard_csv(
        analysis,
        initiative_summaries,
        initiative_strategic_objectives,
        initiative_owner_teams,
        initiative_contributing_teams
    )

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_file = Path(f.name)
        f.write(csv_output)

    try:
        # Verify file exists and is readable
        assert csv_file.exists(), "CSV file should exist"

        # Read and verify content
        with open(csv_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Check header
        assert lines[0].strip() == 'initiative_key,initiative_name,strategic_objective,leading_team,contributing_teams'

        # Check data rows exist
        assert len(lines) >= 3, "Should have header + at least 2 data rows"

        # Verify data content
        content = ''.join(lines)
        assert 'INIT-1' in content
        assert 'INIT-2' in content
        assert 'First initiative' in content
        assert 'Second initiative' in content

    finally:
        # Clean up
        if csv_file.exists():
            csv_file.unlink()


def test_initiative_filtering_by_status_and_quarter():
    """Test that analyze_workload filters initiatives by status and quarter."""
    # Create test data with various status and quarter combinations
    test_data = {
        'initiatives': [
            {'key': 'INIT-1', 'status': 'In Progress', 'quarter': '26 Q1', 'owner_team': 'TeamA', 'summary': 'Test 1'},
            {'key': 'INIT-2', 'status': 'Planned', 'quarter': '26 Q2', 'owner_team': 'TeamA', 'summary': 'Test 2'},
            {'key': 'INIT-3', 'status': 'Done', 'quarter': '26 Q2', 'owner_team': 'TeamB', 'summary': 'Test 3'},
            {'key': 'INIT-4', 'status': 'In Progress', 'quarter': '26 Q2', 'owner_team': 'TeamB', 'summary': 'Test 4'},
            {'key': 'INIT-5', 'status': 'Planned', 'quarter': '26 Q1', 'owner_team': 'TeamC', 'summary': 'Test 5'},
            {'key': 'INIT-6', 'status': 'Backlog', 'quarter': '26 Q3', 'owner_team': 'TeamC', 'summary': 'Test 6'},
        ]
    }

    # Write test data to temp JSON file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json_file = Path(f.name)
        json.dump(test_data, f)

    try:
        # Run analysis
        result = analyze_workload(json_file, {}, [], {})

        # Should only include:
        # - INIT-1: In Progress (any quarter)
        # - INIT-2: Planned + 26 Q2
        # - INIT-4: In Progress (any quarter)
        # Should exclude:
        # - INIT-3: Done (wrong status)
        # - INIT-5: Planned but wrong quarter (26 Q1)
        # - INIT-6: Backlog (wrong status)

        assert result['total_initiatives'] == 3, "Should include 3 initiatives"
        assert result['total_initiatives_before_filter'] == 6, "Should have 6 total before filter"
        assert result['filtered_out_count'] == 3, "Should filter out 3 initiatives"

        # Check that correct initiatives are included
        included_keys = set(result['initiative_summaries'].keys())
        assert 'INIT-1' in included_keys, "INIT-1 (In Progress) should be included"
        assert 'INIT-2' in included_keys, "INIT-2 (26 Q2 + Planned) should be included"
        assert 'INIT-4' in included_keys, "INIT-4 (In Progress) should be included"

        # Check that wrong initiatives are excluded
        assert 'INIT-3' not in included_keys, "INIT-3 (Done) should be excluded"
        assert 'INIT-5' not in included_keys, "INIT-5 (Planned + 26 Q1) should be excluded"
        assert 'INIT-6' not in included_keys, "INIT-6 (Backlog) should be excluded"

    finally:
        # Clean up
        if json_file.exists():
            json_file.unlink()
