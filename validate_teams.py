#!/usr/bin/env python3
"""Validate that Teams Involved count matches actual teams with epics.

This script checks data consistency between the "teams_involved" field
and the actual teams that have epics linked to each initiative.

Usage:
    # Validate latest extraction
    python validate_teams.py

    # Validate specific JSON file
    python validate_teams.py data/jira_extract_20260316.json

    # Validate snapshot
    python validate_teams.py data/snapshots/snapshot_baseline_*.json
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any


class ValidationResult:
    """Results of team count validation."""

    def __init__(self):
        self.mismatches: List[Dict[str, Any]] = []
        self.total_initiatives = 0
        self.perfect_matches = 0

    def add_mismatch(self, mismatch: Dict[str, Any]):
        """Add a validation mismatch."""
        self.mismatches.append(mismatch)

    @property
    def has_issues(self) -> bool:
        """Whether any mismatches were found."""
        return len(self.mismatches) > 0

    @property
    def match_percentage(self) -> float:
        """Percentage of initiatives with correct team counts."""
        if self.total_initiatives == 0:
            return 0.0
        return (self.perfect_matches / self.total_initiatives) * 100


def validate_team_epic_counts(json_file: Path) -> ValidationResult:
    """Validate Teams Involved count matches actual teams with epics.

    Args:
        json_file: Path to JSON file from jira_extract.py

    Returns:
        ValidationResult with any mismatches found
    """
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    result = ValidationResult()
    initiatives = data.get('initiatives', [])
    result.total_initiatives = len(initiatives)

    for initiative in initiatives:
        initiative_key = initiative['key']
        initiative_summary = initiative['summary']
        initiative_status = initiative.get('status', 'Unknown')

        # Get teams from "teams_involved" field
        teams_involved = initiative.get('teams_involved', [])
        teams_involved_count = len(teams_involved)

        # Get teams that actually have epics
        teams_with_epics = set()
        total_epics = 0

        for team_contrib in initiative.get('team_contributions', []):
            team_key = team_contrib.get('team_project_key')
            epics = team_contrib.get('epics', [])

            if epics and team_key:
                teams_with_epics.add(team_key)
                total_epics += len(epics)

        actual_team_count = len(teams_with_epics)

        # Check for mismatch
        if teams_involved_count != actual_team_count:
            # Identify which teams are missing/extra
            teams_involved_set = set(teams_involved)
            missing_teams = teams_with_epics - teams_involved_set
            extra_teams = teams_involved_set - teams_with_epics

            result.add_mismatch({
                'key': initiative_key,
                'summary': initiative_summary,
                'status': initiative_status,
                'teams_involved_count': teams_involved_count,
                'teams_with_epics_count': actual_team_count,
                'total_epics': total_epics,
                'teams_involved': sorted(teams_involved),
                'teams_with_epics': sorted(teams_with_epics),
                'missing_from_field': sorted(missing_teams),  # In epics but not in field
                'extra_in_field': sorted(extra_teams),  # In field but no epics
            })
        else:
            result.perfect_matches += 1

    return result


def print_validation_report(result: ValidationResult, json_file: Path):
    """Print formatted validation report."""
    print(f"\n{'=' * 80}")
    print(f"Team Count Validation Report")
    print(f"{'=' * 80}\n")

    print(f"Data source: {json_file}")
    print(f"Total initiatives checked: {result.total_initiatives}")
    print(f"Perfect matches: {result.perfect_matches} ({result.match_percentage:.1f}%)")
    print(f"Mismatches found: {len(result.mismatches)}\n")

    if not result.has_issues:
        print("✅ All initiatives have matching team counts!")
        print("\nNo action needed - all 'Teams Involved' fields accurately reflect")
        print("the teams that have epics linked to each initiative.")
        return

    print(f"❌ Found {len(result.mismatches)} initiatives with mismatched team counts:\n")
    print(f"{'-' * 80}\n")

    for idx, item in enumerate(result.mismatches, 1):
        print(f"{idx}. {item['key']}: {item['summary']}")
        print(f"   Status: {item['status']}")
        print(f"   Teams Involved field: {item['teams_involved_count']} teams")
        print(f"   Teams with epics: {item['teams_with_epics_count']} teams")
        print(f"   Total epics: {item['total_epics']}")

        if item['teams_involved']:
            print(f"   Teams in field: {', '.join(item['teams_involved'])}")
        else:
            print(f"   Teams in field: (none)")

        if item['teams_with_epics']:
            print(f"   Teams with epics: {', '.join(item['teams_with_epics'])}")
        else:
            print(f"   Teams with epics: (none)")

        if item['missing_from_field']:
            print(f"   ⚠️  Missing from field: {', '.join(item['missing_from_field'])}")

        if item['extra_in_field']:
            print(f"   ⚠️  Extra in field (no epics): {', '.join(item['extra_in_field'])}")

        print()

    print(f"{'-' * 80}\n")
    print("Recommendations:")
    print("1. Review each initiative in Jira")
    print("2. Update 'Teams Involved' field to match actual teams with epics")
    print("3. Or add/remove epics to match the intended team involvement")
    print()


def find_latest_extract() -> Path:
    """Find the most recent extraction file."""
    data_dir = Path('data')

    if not data_dir.exists():
        raise FileNotFoundError(
            "No data directory found. Run 'python jira_extract.py extract' first."
        )

    # Look for JSON files
    json_files = list(data_dir.glob('jira_extract_*.json'))

    if not json_files:
        raise FileNotFoundError(
            "No extraction files found in data/. Run 'python jira_extract.py extract' first."
        )

    # Return most recent
    return max(json_files, key=lambda p: p.stat().st_mtime)


def main():
    """Main validation workflow."""
    # Determine which file to validate
    if len(sys.argv) > 1:
        json_file = Path(sys.argv[1])
        if not json_file.exists():
            print(f"Error: File not found: {json_file}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            json_file = find_latest_extract()
            print(f"Using latest extraction: {json_file}")
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Run validation
    try:
        result = validate_team_epic_counts(json_file)
        print_validation_report(result, json_file)

        # Exit with error code if issues found
        sys.exit(1 if result.has_issues else 0)

    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
