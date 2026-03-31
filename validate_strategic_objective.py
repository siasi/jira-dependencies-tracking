#!/usr/bin/env python3
"""Validate strategic objective field for Jira initiatives.

This script checks that all initiatives have a valid strategic objective
set from a predefined list of acceptable values in config.yaml.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Set
import yaml

from lib.common_formatting import make_clickable_link


def load_validation_rules() -> List[str]:
    """Load valid strategic objective values from config.yaml.

    Returns:
        List of valid strategic objective values, or empty list if not found
    """
    config_file = Path(__file__).parent / 'config' / 'jira_config.yaml'
    if not config_file.exists():
        print(f"Warning: {config_file} not found. Create it to define valid values.", file=sys.stderr)
        return []

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            valid_values = data.get('validation', {}).get('strategic_objective', {}).get('valid_values', [])
            return valid_values
    except Exception as e:
        print(f"Warning: Could not load validation rules: {e}", file=sys.stderr)
        return []


def load_excluded_teams() -> List[str]:
    """Load list of teams to exclude from analysis.

    Returns:
        List of team names to exclude, or empty list if not found
    """
    mappings_file = Path(__file__).parent / 'config' / 'team_mappings.yaml'
    if not mappings_file.exists():
        return []

    try:
        with open(mappings_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            excluded_teams = data.get('teams_excluded_from_analysis', [])
            return excluded_teams
    except Exception as e:
        print(f"Warning: Could not load team exclusions: {e}", file=sys.stderr)
        return []


def find_latest_extract() -> Path:
    """Find the most recent extraction file.

    Returns:
        Path to most recent JSON file

    Raises:
        FileNotFoundError: If no data directory or no extraction files found
    """
    data_dir = Path('data')

    if not data_dir.exists():
        raise FileNotFoundError(
            "No data directory found. Run 'python jira_extract.py extract' first."
        )

    # Support both extraction files and snapshots
    json_files = list(data_dir.glob('jira_extract_*.json'))
    snapshot_files = list(data_dir.glob('snapshots/snapshot_*.json'))
    all_files = json_files + snapshot_files

    if not all_files:
        raise FileNotFoundError(
            "No extraction files found in data/. Run 'python jira_extract.py extract' first."
        )

    return max(all_files, key=lambda p: p.stat().st_mtime)


def validate_strategic_objectives(
    json_file: Path,
    valid_values: List[str],
    excluded_teams: List[str]
) -> Dict:
    """Validate strategic objectives for all initiatives.

    Args:
        json_file: Path to extraction JSON file
        valid_values: List of valid strategic objective values
        excluded_teams: List of teams to exclude from validation

    Returns:
        Dict with validation results
    """
    # Load extraction data
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    initiatives = data.get('initiatives', [])

    # Track issues
    missing_objective = []
    invalid_objective = []
    valid_count = 0

    # Convert valid_values to set for faster lookup
    valid_set = set(valid_values) if valid_values else set()

    # Validate each initiative
    for initiative in initiatives:
        owner_team = initiative.get('owner_team')

        # Skip if owned by excluded team
        if owner_team in excluded_teams:
            continue

        initiative_key = initiative.get('key')
        initiative_summary = initiative.get('summary', '')
        initiative_url = initiative.get('url', '')
        strategic_objective = initiative.get('strategic_objective')

        # Treat empty string as None
        if strategic_objective == '':
            strategic_objective = None

        # Check if strategic objective is missing
        if not strategic_objective:
            missing_objective.append({
                'key': initiative_key,
                'summary': initiative_summary,
                'url': initiative_url,
                'owner_team': owner_team or 'None'
            })
        # Check if strategic objective is invalid
        elif strategic_objective not in valid_set:
            invalid_objective.append({
                'key': initiative_key,
                'summary': initiative_summary,
                'url': initiative_url,
                'owner_team': owner_team or 'None',
                'current_value': strategic_objective
            })
        else:
            valid_count += 1

    total_validated = valid_count + len(missing_objective) + len(invalid_objective)

    return {
        'total_validated': total_validated,
        'valid_count': valid_count,
        'missing_objective': missing_objective,
        'invalid_objective': invalid_objective,
        'valid_values': valid_values,
        'excluded_teams': excluded_teams
    }


def print_validation_report(results: Dict) -> None:
    """Print validation report to console.

    Args:
        results: Results from validate_strategic_objectives()
    """
    total_validated = results['total_validated']
    valid_count = results['valid_count']
    missing_objective = results['missing_objective']
    invalid_objective = results['invalid_objective']
    valid_values = results['valid_values']
    excluded_teams = results['excluded_teams']

    issues_count = len(missing_objective) + len(invalid_objective)

    # Header
    print("\n" + "=" * 70)
    print("Strategic Objective Validation Report")
    print("=" * 70)
    print(f"\nTotal initiatives analyzed: {total_validated}")
    print(f"Valid: {valid_count}")
    print(f"Issues found: {issues_count}")

    if excluded_teams:
        print(f"\nExcluded teams: {', '.join(excluded_teams)}")

    if valid_values:
        print(f"\nValid strategic objectives:")
        for value in valid_values:
            print(f"  - {value}")
    else:
        print("\n⚠ Warning: No valid values configured in config.yaml")

    # Issues section
    print("\n" + "-" * 70)
    print("Issues:")
    print("-" * 70)

    # Missing strategic objective
    if missing_objective:
        print(f"\nMissing strategic objective ({len(missing_objective)} initiatives):")
        for init in missing_objective:
            # Truncate long summaries
            summary = init['summary']
            if len(summary) > 50:
                summary = summary[:47] + "..."
            owner = init.get('owner_team', 'None')
            # Make key clickable
            clickable_key = make_clickable_link(init['key'], init['url'])
            print(f"  - {clickable_key} (owner: {owner}): {summary}")
    else:
        print("\n✓ All initiatives have strategic objective set")

    # Invalid strategic objective
    if invalid_objective:
        print(f"\nInvalid strategic objective ({len(invalid_objective)} initiatives):")
        for init in invalid_objective:
            # Truncate long summaries
            summary = init['summary']
            if len(summary) > 40:
                summary = summary[:37] + "..."
            owner = init.get('owner_team', 'None')
            current = init['current_value']
            # Make key clickable
            clickable_key = make_clickable_link(init['key'], init['url'])
            print(f"  - {clickable_key} (owner: {owner}): {summary}")
            print(f"    Current value: \"{current}\"")
    else:
        if valid_values:  # Only show this if we have valid values to check against
            print("\n✓ All set strategic objectives are valid")

    print("\n" + "=" * 70 + "\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Validate strategic objective field for Jira initiatives',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate latest extraction
  python3 validate_strategic_objective.py

  # Validate specific extraction
  python3 validate_strategic_objective.py data/jira_extract_2024-01-15.json

Configuration:
  Valid strategic objective values are defined in config.yaml:

  validation:
    strategic_objective:
      valid_values:
        - "Revenue Growth"
        - "Cost Reduction"
        - "Customer Experience"

  Teams to exclude are defined in team_mappings.yaml (teams_excluded_from_analysis).
        """
    )

    parser.add_argument(
        'json_file',
        nargs='?',
        type=Path,
        help='Path to extraction JSON file (optional, uses latest if omitted)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output for debugging'
    )

    args = parser.parse_args()

    # Determine which JSON file to use
    if args.json_file:
        json_file = args.json_file
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

    if args.verbose:
        print(f"Loading extraction data from: {json_file}")

    # Load validation rules
    valid_values = load_validation_rules()

    if args.verbose:
        print(f"Loaded {len(valid_values)} valid strategic objective values")

    # Load team exclusions
    excluded_teams = load_excluded_teams()

    if args.verbose and excluded_teams:
        print(f"Excluding teams: {', '.join(excluded_teams)}")

    # Validate strategic objectives
    results = validate_strategic_objectives(json_file, valid_values, excluded_teams)

    # Print report
    print_validation_report(results)

    # Exit with error code if issues found
    issues_count = len(results['missing_objective']) + len(results['invalid_objective'])
    if issues_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
