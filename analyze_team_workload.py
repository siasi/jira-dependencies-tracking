#!/usr/bin/env python3
"""Analyze team workload from Jira extraction data.

This script analyzes how many initiatives each team is involved in,
distinguishing between leading (owner) and contributing (has epics).
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
from collections import defaultdict
import yaml


def load_team_mappings() -> Tuple[Dict[str, str], List[str], Dict[str, str], Dict[str, Dict[str, str]], Dict[str, str]]:
    """Load team mappings, exclusions, strategic objective mappings, and team managers from team_mappings.yaml.

    Returns:
        Tuple of (team_mappings dict, excluded_teams list, strategic_objective_mappings dict, team_managers dict, reverse_team_mappings dict)
    """
    mappings_file = Path(__file__).parent / 'team_mappings.yaml'
    if not mappings_file.exists():
        return {}, [], {}, {}, {}

    try:
        with open(mappings_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            team_mappings = data.get('team_mappings', {})
            excluded_teams = data.get('teams_excluded_from_analysis', [])
            strategic_objective_mappings = data.get('strategic_objective_mappings', {})
            raw_managers = data.get('team_managers', {})

            # Create reverse mapping: project_key -> display_name
            reverse_team_mappings = {v: k for k, v in team_mappings.items()}
            # For teams not in team_mappings, use the project key as display name
            # This handles teams like "Tech Leadership" that don't have a mapping

            # Normalize team_managers to dict format
            team_managers = {}
            for project_key, value in raw_managers.items():
                if isinstance(value, str):
                    # Legacy format: just Notion handle
                    team_managers[project_key] = {
                        'notion_handle': value,
                        'slack_id': None
                    }
                elif isinstance(value, dict):
                    # New format: structured data
                    team_managers[project_key] = {
                        'notion_handle': value.get('notion_handle', ''),
                        'slack_id': value.get('slack_id')
                    }

            return team_mappings, excluded_teams, strategic_objective_mappings, team_managers, reverse_team_mappings
    except Exception as e:
        print(f"Warning: Could not load team mappings: {e}", file=sys.stderr)
        return {}, [], {}, {}, {}


def make_clickable_link(text: str, url: str) -> str:
    """Create a clickable hyperlink for terminal output.

    Uses ANSI escape codes supported by modern terminals:
    - iTerm2 (macOS)
    - Terminal.app (macOS 10.14+)
    - GNOME Terminal (Linux)
    - Windows Terminal
    - VS Code integrated terminal
    - Alacritty, Kitty, and other modern terminals

    Note: In terminals without hyperlink support, the text will display normally
    without the link functionality.

    Args:
        text: The text to display
        url: The URL to link to

    Returns:
        ANSI-formatted string with hyperlink
    """
    if not url:
        return text
    # ANSI escape code format: \033]8;;URL\033\\TEXT\033]8;;\033\\
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def get_rag_circle(rag_status: str) -> str:
    """Get colored circle emoji for RAG status.

    Args:
        rag_status: RAG status (red, yellow, green, or None)

    Returns:
        Colored circle emoji
    """
    rag_map = {
        '🔴': '🔴',  # Red circle
        '🟡': '🟡',  # Yellow circle
        '🟢': '🟢',  # Green circle
        'RED': '🔴',
        'YELLOW': '🟡',
        'AMBER': '🟡',
        'GREEN': '🟢',
    }
    if not rag_status:
        return '🔴'  # Missing RAG status is treated as red
    return rag_map.get(rag_status, '🔴')


def aggregate_rag_status(rag_statuses: List[str]) -> str:
    """Aggregate multiple RAG statuses into a single status.

    Rules:
    - Red: if at least one epic is red OR missing RAG status
    - Yellow: if no red, but at least one yellow
    - Green: if all epics are green

    Args:
        rag_statuses: List of RAG status values (can include None)

    Returns:
        Aggregated RAG status emoji (🔴, 🟡, or 🟢)
    """
    if not rag_statuses:
        return '🔴'  # No epics = red

    # Normalize statuses
    normalized = []
    for status in rag_statuses:
        if not status:  # None or empty = red
            normalized.append('RED')
        elif status in ['🔴', 'RED']:
            normalized.append('RED')
        elif status in ['🟡', 'YELLOW', 'AMBER']:
            normalized.append('YELLOW')
        elif status in ['🟢', 'GREEN']:
            normalized.append('GREEN')
        else:
            normalized.append('RED')  # Unknown = red

    # Apply aggregation rules
    if 'RED' in normalized:
        return '🔴'
    elif 'YELLOW' in normalized:
        return '🟡'
    else:
        return '🟢'


def normalize_team_name(team_name: str, team_mappings: Dict[str, str]) -> str:
    """Normalize team name using team_mappings.

    Args:
        team_name: Display name from Jira
        team_mappings: Mapping from display names to project keys

    Returns:
        Project key if mapped, otherwise original name
    """
    if not team_name:
        return None
    return team_mappings.get(team_name, team_name)


def load_valid_strategic_objectives() -> List[str]:
    """Load valid strategic objective values from config.yaml.

    Returns:
        List of valid strategic objective values, or empty list if not found
    """
    config_file = Path(__file__).parent / 'config.yaml'
    if not config_file.exists():
        return []

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            valid_values = data.get('validation', {}).get('strategic_objective', {}).get('valid_values', [])
            return valid_values if valid_values else []
    except Exception:
        return []


def normalize_teams_involved(teams_involved: Any) -> List[str]:
    """Normalize teams_involved field to a list.

    Handles multiple formats:
    - None/null → []
    - Empty list → []
    - List of teams → list (unchanged)
    - Comma-separated string → split into list

    Args:
        teams_involved: Value from teams_involved field (can be None, list, or string)

    Returns:
        List of team names
    """
    if teams_involved is None:
        return []

    if isinstance(teams_involved, list):
        return teams_involved

    if isinstance(teams_involved, str):
        # Handle comma-separated string (e.g., "Team A, Team B, Team C")
        return [t.strip() for t in teams_involved.split(',') if t.strip()]

    # Fallback for unexpected types
    return []


def analyze_workload(json_file: Path, team_mappings: Dict[str, str], excluded_teams: List[str],
                     strategic_objective_mappings: Dict[str, str]) -> Dict:
    """Analyze team workload from extraction data.

    Args:
        json_file: Path to extraction JSON file
        team_mappings: Mapping from display names to project keys
        excluded_teams: List of teams to exclude from analysis
        strategic_objective_mappings: Mapping from old strategic objectives to current ones

    Returns:
        Dict with workload analysis results
    """
    # Load extraction data
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    initiatives = data.get('initiatives', [])

    # Data structures for analysis
    workload = defaultdict(lambda: {'leading': set(), 'contributing': set()})
    contributing_rag = defaultdict(lambda: defaultdict(list))  # Map team -> initiative -> [rag statuses]
    initiatives_without_owner = []
    initiatives_without_epics = []
    initiatives_missing_strategic_objective = []
    initiatives_invalid_strategic_objective = []
    initiative_summaries = {}  # Map initiative key to summary
    initiative_urls = {}  # Map initiative key to Jira URL
    initiative_strategic_objectives = {}  # Map initiative key to strategic objective
    initiative_owner_teams = {}  # Map initiative key to owner team
    initiative_contributing_teams = {}  # Map initiative key to list of contributing teams

    # Load valid strategic objectives for validation
    valid_strategic_objectives = load_valid_strategic_objectives()

    # Analyze each initiative
    for initiative in initiatives:
        initiative_key = initiative.get('key')
        initiative_summary = initiative.get('summary', '')
        owner_team = initiative.get('owner_team')
        contributing_teams_data = initiative.get('contributing_teams', [])
        strategic_objective = initiative.get('strategic_objective')

        # Store summary and URL for verbose output
        initiative_summaries[initiative_key] = initiative_summary
        initiative_urls[initiative_key] = initiative.get('url', '')

        # Apply strategic objective mapping (consolidate old objectives to current ones)
        mapped_objective = strategic_objective or ''
        if mapped_objective and strategic_objective_mappings:
            mapped_objective = strategic_objective_mappings.get(strategic_objective, strategic_objective)
        initiative_strategic_objectives[initiative_key] = mapped_objective

        # Normalize owner team
        normalized_owner = normalize_team_name(owner_team, team_mappings)
        initiative_owner_teams[initiative_key] = normalized_owner or ''

        # Validate strategic objective (skip if owner is excluded team)
        if not normalized_owner or normalized_owner not in excluded_teams:
            if not strategic_objective or (isinstance(strategic_objective, str) and not strategic_objective.strip()):
                # Missing strategic objective
                initiatives_missing_strategic_objective.append({
                    'key': initiative_key,
                    'summary': initiative_summary,
                    'owner_team': normalized_owner or 'None'
                })
            elif valid_strategic_objectives and strategic_objective not in valid_strategic_objectives:
                # Invalid strategic objective
                initiatives_invalid_strategic_objective.append({
                    'key': initiative_key,
                    'summary': initiative_summary,
                    'owner_team': normalized_owner or 'None',
                    'current_value': strategic_objective
                })

        # Track initiatives without owner
        if not normalized_owner:
            initiatives_without_owner.append({
                'key': initiative_key,
                'summary': initiative_summary
            })
        else:
            # Count as "leading" if not excluded
            if normalized_owner not in excluded_teams:
                workload[normalized_owner]['leading'].add(initiative_key)

        # Check for missing epics based on teams_involved field
        # Only report as "without epics" if there are contributing teams expected but missing epics
        # (excluding the owner team, who doesn't need to create an epic)
        teams_involved = normalize_teams_involved(initiative.get('teams_involved'))
        teams_with_epics = {
            tc['team_project_key']
            for tc in contributing_teams_data
            if tc.get('epics')
        }

        # Check for epic count mismatch (only if owner is not in excluded teams)
        if teams_involved and (not normalized_owner or normalized_owner not in excluded_teams):
            # Skip if teams_involved only contains the owner team
            non_owner_teams = [t for t in teams_involved if t != owner_team]
            if not non_owner_teams:
                # Teams involved only has the owner, no contributing teams expected
                pass
            else:
                # Find which teams are missing epics
                teams_with_epics_set = set(teams_with_epics)
                missing_teams = []
                for display_name in teams_involved:
                    # Skip owner team - they don't need to create an epic
                    if display_name == owner_team:
                        continue
                    project_key = team_mappings.get(display_name, display_name)
                    if project_key.upper() not in {k.upper() for k in teams_with_epics_set}:
                        missing_teams.append(display_name)

                # Only report if there are actually missing contributing teams
                if missing_teams:
                    initiatives_without_epics.append({
                        'key': initiative_key,
                        'summary': initiative_summary,
                        'owner_team': normalized_owner or 'None',
                        'missing_teams': missing_teams
                    })

        # Track contributing teams (teams with epics that are not the owner)
        # Only include teams with at least one epic that is NOT Done or Won't Do
        contributing_teams_list = []
        if teams_with_epics:
            # Identify teams contributing (have epics but are not owner)
            for team_data in contributing_teams_data:
                team_project_key = team_data.get('team_project_key')
                if team_project_key and team_project_key != normalized_owner:
                    epics = team_data.get('epics', [])

                    # Check if this team has at least one active epic (not Done or Won't Do)
                    has_active_epic = False
                    for epic in epics:
                        epic_status = epic.get('status', '')
                        if epic_status not in ['Done', "Won't Do"]:
                            has_active_epic = True
                            break

                    # Only include team if they have active epics
                    if has_active_epic:
                        # Add to contributing teams list (regardless of excluded status for CSV export)
                        contributing_teams_list.append(team_project_key)

                        # Count as "contributing" for non-owner teams (if not excluded)
                        if team_project_key not in excluded_teams:
                            workload[team_project_key]['contributing'].add(initiative_key)

                            # Track RAG statuses for this team's epics
                            for epic in epics:
                                rag_status = epic.get('rag_status')
                                contributing_rag[team_project_key][initiative_key].append(rag_status)

        # Store contributing teams for this initiative
        initiative_contributing_teams[initiative_key] = contributing_teams_list

    # Convert sets to counts and calculate totals
    team_stats = {}
    team_details = {}

    for team, data in workload.items():
        leading_list = sorted(data['leading'])
        contributing_list = sorted(data['contributing'])

        leading_count = len(leading_list)
        contributing_count = len(contributing_list)
        total_count = leading_count + contributing_count

        team_stats[team] = {
            'leading': leading_count,
            'contributing': contributing_count,
            'total': total_count
        }

        # Store detailed lists for verbose mode
        team_details[team] = {
            'leading': leading_list,
            'contributing': contributing_list
        }

    return {
        'team_stats': team_stats,
        'team_details': team_details,
        'contributing_rag': dict(contributing_rag),  # Convert defaultdict to dict
        'initiative_summaries': initiative_summaries,
        'initiative_urls': initiative_urls,
        'initiative_strategic_objectives': initiative_strategic_objectives,
        'initiative_owner_teams': initiative_owner_teams,
        'initiative_contributing_teams': initiative_contributing_teams,
        'initiatives_without_owner': initiatives_without_owner,
        'initiatives_without_epics': initiatives_without_epics,
        'initiatives_missing_strategic_objective': initiatives_missing_strategic_objective,
        'initiatives_invalid_strategic_objective': initiatives_invalid_strategic_objective,
        'total_initiatives': len(initiatives),
        'excluded_teams': excluded_teams
    }


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


def print_workload_report(analysis: Dict, team_managers: Dict[str, Dict[str, str]] = None,
                         reverse_team_mappings: Dict[str, str] = None, verbose: bool = False) -> None:
    """Print workload analysis report to console.

    Args:
        analysis: Results from analyze_workload()
        team_managers: Mapping of team keys to manager information
        reverse_team_mappings: Mapping of project keys to display names
        verbose: If True, show detailed list of initiatives per team
    """
    if team_managers is None:
        team_managers = {}
    if reverse_team_mappings is None:
        reverse_team_mappings = {}
    team_stats = analysis['team_stats']
    team_details = analysis.get('team_details', {})
    contributing_rag = analysis.get('contributing_rag', {})
    initiative_summaries = analysis.get('initiative_summaries', {})
    initiative_urls = analysis.get('initiative_urls', {})
    initiative_strategic_objectives = analysis.get('initiative_strategic_objectives', {})
    initiative_owner_teams = analysis.get('initiative_owner_teams', {})
    initiative_contributing_teams = analysis.get('initiative_contributing_teams', {})
    initiatives_without_owner = analysis['initiatives_without_owner']
    initiatives_without_epics = analysis['initiatives_without_epics']
    initiatives_missing_strategic_objective = analysis.get('initiatives_missing_strategic_objective', [])
    initiatives_invalid_strategic_objective = analysis.get('initiatives_invalid_strategic_objective', [])
    total_initiatives = analysis['total_initiatives']
    excluded_teams = analysis['excluded_teams']

    # Header
    print("\n" + "=" * 70)
    print("Team Workload Report")
    print("=" * 70)
    print(f"\nTotal initiatives analyzed: {total_initiatives}")

    if excluded_teams:
        print(f"Excluded teams: {', '.join(excluded_teams)}")

    # Initiative Analysis - CSV Export
    print("\n" + "-" * 70)
    print("Initiative Analysis (CSV format):")
    print("-" * 70)
    print("initiative_key,initiative_name,strategic_objective,leading_team,contributing_teams")

    # Get all initiative keys and sort them
    all_initiative_keys = sorted(initiative_summaries.keys())

    for init_key in all_initiative_keys:
        leading_team = initiative_owner_teams.get(init_key, '')

        # Skip initiatives owned by excluded teams
        if leading_team in excluded_teams:
            continue

        init_name = initiative_summaries.get(init_key, '').replace('"', '""')  # Escape quotes
        strategic_obj = initiative_strategic_objectives.get(init_key, '').replace('"', '""')
        contributing = initiative_contributing_teams.get(init_key, [])

        # Format contributing teams: comma-separated in double quotes, or empty quotes if none
        if contributing:
            contributing_str = f'"{",".join(contributing)}"'
        else:
            contributing_str = '""'

        # Print CSV row with all fields properly quoted
        print(f'{init_key},"{init_name}","{strategic_obj}",{leading_team},{contributing_str}')

    print("\n" + "-" * 70)
    print("Team Analysis (sorted by total initiatives, descending):")
    print("-" * 70)

    # Sort teams by total initiatives (descending)
    sorted_teams = sorted(
        team_stats.items(),
        key=lambda x: x[1]['total'],
        reverse=True
    )

    if sorted_teams:
        for team, stats in sorted_teams:
            print(f"{team}: {stats['total']} total ({stats['leading']} leading, {stats['contributing']} contributing)")
    else:
        print("No teams found in analysis.")

    # Verbose detailed section
    if verbose and sorted_teams:
        print("\n" + "-" * 70)
        print("Detailed Breakdown by Team:")
        print("-" * 70)

        for team, stats in sorted_teams:
            details = team_details.get(team, {})
            leading_list = details.get('leading', [])
            contributing_list = details.get('contributing', [])

            # Get team display name (use reverse mapping or fall back to project key)
            team_display = reverse_team_mappings.get(team, team)

            # Get manager info for this team
            manager_info = team_managers.get(team, {})
            manager_handle = manager_info.get('notion_handle', '')
            manager_part = f" - {manager_handle}" if manager_handle else ""

            print("\n" + "=" * 70)
            print(f"{team_display}{manager_part} - {stats['total']} total initiatives")
            print("=" * 70)

            # Leading initiatives
            if leading_list:
                print(f"\nLeading ({stats['leading']} initiatives):")
                for init_key in leading_list:
                    summary = initiative_summaries.get(init_key, 'No summary')
                    url = initiative_urls.get(init_key, '')
                    # Truncate long summaries
                    if len(summary) > 70:
                        summary = summary[:67] + "..."
                    # Make initiative key clickable if URL available
                    clickable_key = make_clickable_link(init_key, url)
                    print(f"  - {clickable_key}: {summary}")
            else:
                print(f"\nLeading: None")

            # Contributing initiatives
            if contributing_list:
                print(f"\nContributing ({stats['contributing']} initiatives):")
                for init_key in contributing_list:
                    summary = initiative_summaries.get(init_key, 'No summary')
                    url = initiative_urls.get(init_key, '')
                    # Truncate long summaries
                    if len(summary) > 70:
                        summary = summary[:67] + "..."
                    # Make initiative key clickable if URL available
                    clickable_key = make_clickable_link(init_key, url)

                    # Get RAG status for this team's contribution
                    team_rag_data = contributing_rag.get(team, {})
                    rag_statuses = team_rag_data.get(init_key, [])
                    rag_circle = aggregate_rag_status(rag_statuses)

                    print(f"  {rag_circle} {clickable_key}: {summary}")
            else:
                print(f"\nContributing: None")

    # Issues section
    print("\n" + "-" * 70)
    print("Issues:")
    print("-" * 70)

    # Initiatives without owner
    if initiatives_without_owner:
        print(f"\nInitiatives without owner_team: {len(initiatives_without_owner)}")
        for init in initiatives_without_owner:
            # Truncate long summaries
            summary = init['summary']
            if len(summary) > 60:
                summary = summary[:57] + "..."
            # Make key clickable
            url = initiative_urls.get(init['key'], '')
            clickable_key = make_clickable_link(init['key'], url)
            print(f"  - {clickable_key}: \"{summary}\"")
    else:
        print("\n✓ All initiatives have owner_team")

    # Initiatives with missing epics (from contributing teams)
    if initiatives_without_epics:
        print(f"\nInitiatives with missing contributing epics: {len(initiatives_without_epics)}")
        for init in initiatives_without_epics:
            # Truncate long summaries
            summary = init['summary']
            if len(summary) > 45:
                summary = summary[:42] + "..."
            owner = init.get('owner_team', 'None')
            missing_teams = init.get('missing_teams', [])
            # Get team display name
            owner_display = reverse_team_mappings.get(owner, owner)
            # Make key clickable
            url = initiative_urls.get(init['key'], '')
            clickable_key = make_clickable_link(init['key'], url)
            print(f"  - {clickable_key} (owner: {owner_display}): \"{summary}\"")
            if missing_teams:
                print(f"    Missing epics from: {', '.join(missing_teams)}")
    else:
        print("\n✓ All contributing teams have created their epics")

    # Initiatives with missing strategic objective
    if initiatives_missing_strategic_objective:
        print(f"\nInitiatives without strategic objective: {len(initiatives_missing_strategic_objective)}")
        for init in initiatives_missing_strategic_objective:
            # Truncate long summaries
            summary = init['summary']
            if len(summary) > 50:
                summary = summary[:47] + "..."
            owner = init.get('owner_team', 'None')
            # Get team display name
            owner_display = reverse_team_mappings.get(owner, owner)
            # Get manager info
            manager_info = team_managers.get(owner, {})
            manager_handle = manager_info.get('notion_handle', '')
            manager_display = f" {manager_handle}" if manager_handle else ""
            # Make key clickable
            url = initiative_urls.get(init['key'], '')
            clickable_key = make_clickable_link(init['key'], url)
            print(f"  - {clickable_key} (owner: {owner_display}{manager_display}): \"{summary}\"")
    else:
        print("\n✓ All initiatives have strategic objective set")

    # Initiatives with invalid strategic objective
    if initiatives_invalid_strategic_objective:
        print(f"\nInitiatives with invalid strategic objective: {len(initiatives_invalid_strategic_objective)}")
        for init in initiatives_invalid_strategic_objective:
            # Truncate long summaries
            summary = init['summary']
            if len(summary) > 40:
                summary = summary[:37] + "..."
            owner = init.get('owner_team', 'None')
            current = init['current_value']
            # Get manager info
            manager_info = team_managers.get(owner, {})
            manager_handle = manager_info.get('notion_handle', '')
            manager_display = f" {manager_handle}" if manager_handle else ""
            # Make key clickable
            url = initiative_urls.get(init['key'], '')
            clickable_key = make_clickable_link(init['key'], url)
            print(f"  - {clickable_key} (owner: {owner}{manager_display}): \"{summary}\"")
            print(f"    Current value: \"{current}\"")
    else:
        print("\n✓ All strategic objectives are valid")

    print("\n" + "=" * 70 + "\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Analyze team workload from Jira extraction data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze workload from latest extraction
  python3 analyze_team_workload.py

  # Analyze specific extraction
  python3 analyze_team_workload.py data/jira_extract_2024-01-15.json

  # Analyze with verbose output
  python3 analyze_team_workload.py --verbose

The script distinguishes between:
  - Leading: Team is the owner_team of the initiative
  - Contributing: Team has epics in an initiative they don't own
  - Total: Leading + Contributing

Teams listed in teams_excluded_from_analysis (team_mappings.yaml) are filtered out.
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
        help='Show detailed list of initiatives per team (leading and contributing)'
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

    # Load team mappings and exclusions
    team_mappings, excluded_teams, strategic_objective_mappings, team_managers, reverse_team_mappings = load_team_mappings()

    if args.verbose:
        print(f"Loaded {len(team_mappings)} team mappings")
        if excluded_teams:
            print(f"Excluding teams: {', '.join(excluded_teams)}")
        if strategic_objective_mappings:
            print(f"Loaded {len(strategic_objective_mappings)} strategic objective mappings")
        if team_managers:
            print(f"Loaded {len(team_managers)} team managers")

    # Analyze workload
    analysis = analyze_workload(json_file, team_mappings, excluded_teams, strategic_objective_mappings)

    # Print report
    print_workload_report(analysis, team_managers=team_managers, reverse_team_mappings=reverse_team_mappings,
                         verbose=args.verbose)


if __name__ == '__main__':
    main()
