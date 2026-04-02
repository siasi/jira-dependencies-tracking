"""Tests for analyze_workload.py HTML dashboard generation."""

import pytest
from pathlib import Path
import tempfile
from analyze_workload import generate_dashboard_csv, generate_html_dashboard


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
