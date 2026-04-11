#!/usr/bin/env python3
"""Data Quality Validation Script.

This script validates initiative data quality and generates actionable items
for engineering managers. It uses shared validation logic from lib/validation.py.

Usage:
    # Validate current quarter planned + all in progress
    python3 validate_data_quality.py --quarter "26 Q2"

    # Only validate Proposed initiatives
    python3 validate_data_quality.py --quarter "26 Q2" --status Proposed

    # Validate all active initiatives
    python3 validate_data_quality.py --quarter "26 Q2" --all-active

    # Show only my teams' action items (configure my_teams in team_mappings.yaml)
    python3 validate_data_quality.py --quarter "26 Q2" --me

    # Generate Slack messages (always includes all teams)
    python3 validate_data_quality.py --quarter "26 Q2" --slack

    # Verbose output
    python3 validate_data_quality.py --quarter "26 Q2" --verbose
"""

import argparse
import json
import sys
import yaml
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from lib.validation import (
    InitiativeValidator,
    ValidationIssue,
    Priority,
    load_validation_config,
    create_action_item,
)
from lib.common_formatting import make_clickable_link
from lib.config_utils import get_jira_base_url
from lib.output_utils import generate_output_path
from lib.template_renderer import get_template_environment


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        args: Optional argument list (for testing)

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Validate initiative data quality and generate action items'
    )

    # Filtering (combinable with AND logic)
    parser.add_argument(
        '--quarter',
        help='Filter by quarter (e.g., "26 Q2"). Combines with other filters using AND.'
    )
    parser.add_argument(
        '--status',
        help='Filter by status (e.g., "Proposed", "Planned", "In Progress"). Combines with --quarter using AND.'
    )
    parser.add_argument(
        '--all-active',
        action='store_true',
        help='Filter to active statuses (Proposed, Planned, In Progress). Combines with --quarter using AND.'
    )

    # Output options
    parser.add_argument(
        '--slack',
        action='store_true',
        help='Generate Slack bulk messages'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed validation rules applied'
    )
    parser.add_argument(
        '--show-exempt',
        action='store_true',
        help='Show skipped initiatives (exceptions, excluded teams)'
    )
    parser.add_argument(
        '--me',
        action='store_true',
        help='Show only action items for my teams (configured in team_mappings.yaml)'
    )

    return parser.parse_args(args)


def find_latest_extract() -> Optional[Path]:
    """Find the most recent Jira extract JSON file.

    Returns:
        Path to latest extract, or None if not found
    """
    data_dir = Path('data')
    if not data_dir.exists():
        return None

    json_files = list(data_dir.glob('jira_extract_*.json'))
    if not json_files:
        return None

    # Sort by modification time, most recent first
    json_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return json_files[0]


def load_signed_off_initiatives() -> Set[str]:
    """Load signed-off initiative exceptions.

    Returns:
        Set of initiative keys to exclude from validation
    """
    exceptions_file = Path('config/initiative_exceptions.yaml')
    if not exceptions_file.exists():
        return set()

    try:
        with open(exceptions_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            signed_off = data.get('signed_off_initiatives', [])
            return {item['key'] for item in signed_off if 'key' in item}
    except Exception:
        return set()


def load_excluded_teams() -> List[str]:
    """Load list of teams to exclude from validation checks.

    Returns:
        List of team names whose initiatives should be filtered out
    """
    mappings_file = Path('config/team_mappings.yaml')
    if not mappings_file.exists():
        return []

    try:
        with open(mappings_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

            # Load validation-specific exclusions with fallback to generic list
            excluded_teams = data.get('teams_excluded_from_validation')
            if excluded_teams is None:
                excluded_teams = data.get('teams_excluded_from_analysis', [])

            return excluded_teams if excluded_teams else []
    except Exception:
        return []


def load_team_mappings() -> Dict[str, str]:
    """Load team name to project key mappings.

    Returns:
        Dict mapping display names to project keys (e.g., "MAP" -> "MAPS")
    """
    mappings_file = Path('config/team_mappings.yaml')
    if not mappings_file.exists():
        return {}

    try:
        with open(mappings_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data.get('team_mappings', {})
    except Exception:
        return {}


def load_team_managers() -> Dict[str, Dict[str, Optional[str]]]:
    """Load team managers with Notion handles and Slack IDs.

    Returns:
        Dict mapping project keys to manager info
    """
    mappings_file = Path('config/team_mappings.yaml')
    if not mappings_file.exists():
        return {}

    try:
        with open(mappings_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            raw_managers = data.get('team_managers', {})

            # Normalize to dict format
            team_managers = {}
            for project_key, value in raw_managers.items():
                if isinstance(value, str):
                    team_managers[project_key] = {
                        'notion_handle': value,
                        'slack_id': None
                    }
                elif isinstance(value, dict):
                    team_managers[project_key] = {
                        'notion_handle': value.get('notion_handle', ''),
                        'slack_id': value.get('slack_id')
                    }

            return team_managers
    except Exception:
        return {}


def load_my_teams() -> List[str]:
    """Load my teams from configuration.

    Returns:
        List of project keys for teams I manage
    """
    mappings_file = Path('config/team_mappings.yaml')
    if not mappings_file.exists():
        return []

    try:
        with open(mappings_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            my_teams = data.get('my_teams', [])
            return my_teams if isinstance(my_teams, list) else []
    except Exception:
        return []


def filter_grouped_data_by_teams(grouped_data: Dict, my_teams: List[str]) -> tuple[Dict, int, int]:
    """Filter grouped manager data to show only my teams' action items.

    Args:
        grouped_data: Grouped manager data
        my_teams: List of my team project keys

    Returns:
        Tuple of (filtered_data, filtered_count, total_count)
    """
    if not my_teams:
        # If no teams configured, return all data
        total_count = sum(
            len(init_data['issues'])
            for manager_data in grouped_data.values()
            for init_data in manager_data['initiatives'].values()
        )
        return grouped_data, total_count, total_count

    my_teams_set = set(my_teams)
    filtered_data = {}
    filtered_count = 0
    total_count = 0

    for slack_id, manager_data in grouped_data.items():
        team_key = manager_data['team']

        # Count all action items (for total)
        for init_data in manager_data['initiatives'].values():
            total_count += len(init_data['issues'])

        # Only include if team matches
        if team_key in my_teams_set:
            filtered_data[slack_id] = manager_data
            for init_data in manager_data['initiatives'].values():
                filtered_count += len(init_data['issues'])

    return filtered_data, filtered_count, total_count


def filter_initiatives(
    initiatives: List[Dict],
    quarter: Optional[str],
    status_filter: Optional[str],
    all_active: bool,
    signed_off: Set[str],
    excluded_teams: Optional[List[str]] = None
) -> List[Dict]:
    """Filter initiatives based on criteria using AND logic.

    Filters can be combined:
    - --status X --quarter Q: status == X AND quarter == Q
    - --all-active --quarter Q: status in [Proposed, Planned, In Progress] AND quarter == Q
    - --status X: status == X (any quarter)
    - --all-active: status in [Proposed, Planned, In Progress] (any quarter)
    - --quarter Q: In Progress (any quarter) + Planned (quarter Q)
    - No filters: In Progress (any quarter) + Planned (any quarter)

    Args:
        initiatives: List of initiative dicts
        quarter: Optional quarter filter (e.g., "26 Q2")
        status_filter: Optional status to filter by
        all_active: If True, include all active statuses
        signed_off: Set of initiative keys to exclude
        excluded_teams: List of team names to exclude

    Returns:
        Filtered list of initiatives
    """
    filtered = []
    excluded_teams_set = set(excluded_teams) if excluded_teams else set()

    for initiative in initiatives:
        key = initiative.get('key', '')
        status = initiative.get('status', '')
        init_quarter = initiative.get('quarter', '')
        owner_team = initiative.get('owner_team', '')

        # Exclude signed-off exceptions
        if key in signed_off:
            continue

        # Exclude initiatives from excluded teams
        if owner_team in excluded_teams_set:
            continue

        # Determine which statuses to include
        if status_filter:
            # Explicit status filter
            status_match = (status == status_filter)
        elif all_active:
            # All active statuses
            status_match = status in ['Proposed', 'Planned', 'In Progress']
        else:
            # Default: In Progress (any quarter) + Planned
            status_match = status in ['In Progress', 'Planned']

        # Apply status filter
        if not status_match:
            continue

        # Apply quarter filter if provided
        if quarter:
            # For default filter: In Progress passes for any quarter, Planned must match quarter
            if status_filter or all_active:
                # Explicit filters: quarter must match
                if init_quarter != quarter:
                    continue
            else:
                # Default filter: only Planned needs to match quarter
                if status == 'Planned' and init_quarter != quarter:
                    continue

        # Passed all filters
        filtered.append(initiative)

    return filtered


def validate_initiatives(
    initiatives: List[Dict],
    config
) -> Dict[str, List[ValidationIssue]]:
    """Validate initiatives using shared validation library.

    Args:
        initiatives: List of initiative dicts
        config: ValidationConfig instance

    Returns:
        Dict mapping initiative keys to list of issues
    """
    validator = InitiativeValidator(config)
    issues_by_initiative = {}

    for initiative in initiatives:
        issues = validator.validate(initiative)
        if issues:
            issues_by_initiative[initiative['key']] = issues

    return issues_by_initiative


def group_by_manager(
    issues_by_initiative: Dict[str, List[ValidationIssue]],
    team_managers: Dict[str, Dict[str, Optional[str]]],
    team_mappings: Dict[str, str]
) -> Dict[str, Dict]:
    """Group action items by manager.

    Args:
        issues_by_initiative: Dict of initiative key to list of issues
        team_managers: Dict of project key to manager info
        team_mappings: Dict mapping display names to project keys

    Returns:
        Dict mapping manager Slack ID to grouped data
    """
    grouped = defaultdict(lambda: {
        'manager_name': None,
        'slack_id': None,
        'team': None,
        'initiatives': {}
    })

    for init_key, issues in issues_by_initiative.items():
        for issue in issues:
            # Always group by owner team (not by who needs to act)
            owner_team = issue.owner_team
            if not owner_team:
                # Can't group without owner team
                continue

            # Map display name to project key if needed
            project_key = team_mappings.get(owner_team, owner_team)

            manager_info = team_managers.get(project_key, {})
            manager_name = manager_info.get('notion_handle', 'Unknown')
            slack_id = manager_info.get('slack_id', f'unknown_{owner_team}')

            # Remove @ prefix from manager name if present
            if manager_name.startswith('@'):
                manager_name = manager_name[1:].strip()

            # Initialize manager entry
            if grouped[slack_id]['slack_id'] is None:
                grouped[slack_id]['manager_name'] = manager_name
                grouped[slack_id]['slack_id'] = slack_id
                grouped[slack_id]['team'] = owner_team

            # Add initiative if not already present
            if init_key not in grouped[slack_id]['initiatives']:
                grouped[slack_id]['initiatives'][init_key] = {
                    'summary': issue.initiative_summary,
                    'status': issue.initiative_status,
                    'quarter': None,  # Would need to pass through from initiative
                    'issues': []
                }

            # Add issue to initiative
            grouped[slack_id]['initiatives'][init_key]['issues'].append(issue)

    return dict(grouped)


def calculate_priority_summary(grouped_data: Dict) -> Dict[str, int]:
    """Calculate summary of issues by priority.

    Args:
        grouped_data: Grouped manager data

    Returns:
        Dict mapping priority labels (P1-P5) to counts
    """
    summary = {'P1': 0, 'P2': 0, 'P3': 0, 'P4': 0, 'P5': 0}

    for manager_data in grouped_data.values():
        for initiative_data in manager_data['initiatives'].values():
            for issue in initiative_data['issues']:
                label = f'P{int(issue.priority)}'
                summary[label] += 1

    return summary


def is_owned_initiative(issue: ValidationIssue, manager_team: str, team_mappings: Dict[str, str]) -> bool:
    """Check if this initiative is owned by the manager's team.

    Args:
        issue: ValidationIssue instance
        manager_team: The team of the manager
        team_mappings: Team name to project key mappings

    Returns:
        True if manager owns this initiative
    """
    # Normalize team names for comparison
    manager_key = team_mappings.get(manager_team, manager_team)
    owner_key = team_mappings.get(issue.owner_team or '', issue.owner_team or '')

    return manager_key == owner_key


def format_console_output(grouped_data: Dict, metadata: Dict) -> str:
    """Format console output showing action items by manager.

    Args:
        grouped_data: Grouped manager data
        metadata: Report metadata (quarter, filter, counts, etc.)

    Returns:
        Formatted console output string
    """
    lines = []
    jira_base_url = get_jira_base_url()
    team_mappings = load_team_mappings()
    team_managers = load_team_managers()

    # Header
    lines.append('=' * 80)
    lines.append('DATA QUALITY VALIDATION REPORT')
    lines.append(f"Quarter: {metadata['quarter']}")
    lines.append(f"Filter: {metadata['filter']}")
    lines.append('=' * 80)
    lines.append('')

    # Summary
    lines.append(f"Initiatives Analyzed: {metadata['initiatives_analyzed']}")
    lines.append(f"Initiatives with Issues: {metadata['initiatives_with_issues']}")
    if metadata.get('exceptions_skipped', 0) > 0:
        lines.append(f"Exceptions Skipped: {metadata['exceptions_skipped']}")
    excluded_teams = metadata.get('excluded_teams', [])
    if excluded_teams:
        lines.append(f"Excluded Teams: {', '.join(excluded_teams)}")
    lines.append('')

    # Count managers and action items
    total_managers = len(grouped_data)
    total_actions = sum(
        len(init_data['issues'])
        for manager_data in grouped_data.values()
        for init_data in manager_data['initiatives'].values()
    )

    # Show filtered vs total if filtering is active
    if metadata.get('filtered_count') is not None and metadata.get('total_count') is not None:
        filtered_count = metadata['filtered_count']
        total_count = metadata['total_count']
        lines.append(f"Action Items by Manager ({total_managers} managers, {filtered_count} action items for your teams, {total_count} total):")
    else:
        lines.append(f"Action Items by Manager ({total_managers} managers, {total_actions} action items):")

    lines.append('-' * 80)
    lines.append('')

    # Sort managers by name
    sorted_managers = sorted(
        grouped_data.items(),
        key=lambda x: x[1]['manager_name'] or ''
    )

    for slack_id, manager_data in sorted_managers:
        manager_name = manager_data['manager_name'] or 'Unknown'
        team = manager_data['team'] or 'Unknown'

        # Count action items for this manager
        manager_actions = sum(
            len(init_data['issues'])
            for init_data in manager_data['initiatives'].values()
        )
        manager_initiatives = len(manager_data['initiatives'])

        # Add @ prefix if not already present
        if not manager_name.startswith('@'):
            manager_name = f'@{manager_name}'

        lines.append(f"{manager_name} - {team}")
        lines.append(f"  {manager_actions} action items across {manager_initiatives} initiatives")
        lines.append('')

        # Sort initiatives by key
        sorted_initiatives = sorted(manager_data['initiatives'].items())

        for init_key, init_data in sorted_initiatives:
            summary = init_data['summary']
            status = init_data['status']
            init_url = f"{jira_base_url}/browse/{init_key}"

            lines.append(f"  {make_clickable_link(init_key, init_url)}: {summary}")
            lines.append(f"  Status: {status}")

            # Sort issues by priority
            sorted_issues = sorted(init_data['issues'], key=lambda i: i.priority)

            for issue in sorted_issues:
                priority_label = f'P{int(issue.priority)}'

                # Extract action-only description (part after " - " if present)
                description = issue.description
                if ' - ' in description:
                    # Take the action part (after " - ")
                    action_description = description.split(' - ', 1)[1]
                else:
                    # Use full description if no " - " separator
                    action_description = description

                # If issue has an epic key, add clickable link to the description
                if issue.epic_key:
                    epic_url = f"{jira_base_url}/browse/{issue.epic_key}"
                    epic_link = make_clickable_link(issue.epic_key, epic_url)

                    # Replace "Set RAG (TEAM)" with "Set RAG for EPIC-123"
                    # Team name is redundant since it's in the epic key
                    if 'Set RAG' in action_description:
                        action_description = f"Set RAG for {epic_link}"

                # Determine who needs to take action
                if issue.type in ['missing_epic', 'missing_rag_status']:
                    # Dependency action - team_affected manager needs to act
                    acting_team = issue.team_affected
                    acting_project_key = team_mappings.get(acting_team, acting_team)
                    acting_manager_info = team_managers.get(acting_project_key, {})
                    acting_manager_name = acting_manager_info.get('notion_handle', 'Unknown')
                    if not acting_manager_name.startswith('@'):
                        acting_manager_name = f'@{acting_manager_name}'
                    action_owner = acting_manager_name
                else:
                    # Owner action - current manager needs to act
                    action_owner = manager_name

                lines.append(f"    {priority_label} ⚠️  {action_description} - {action_owner}")

            lines.append('')

        lines.append('-' * 80)
        lines.append('')

    # Priority summary
    priority_summary = calculate_priority_summary(grouped_data)
    lines.append('=' * 80)
    lines.append('Summary by Priority:')
    lines.append(f"  P1 (Critical - blocks everything): {priority_summary['P1']} action items")
    lines.append(f"  P2 (High - blocks planning): {priority_summary['P2']} action items")
    lines.append(f"  P3 (Medium - data correction): {priority_summary['P3']} action items")
    lines.append(f"  P4 (Low - missing dependencies): {priority_summary['P4']} action items")
    lines.append(f"  P5 (Info - missing signals): {priority_summary['P5']} action items")
    lines.append('=' * 80)
    lines.append('')

    return '\n'.join(lines)


def generate_slack_messages(grouped_data: Dict) -> List[Dict]:
    """Generate Slack messages from grouped data.

    Each manager only receives actions they're responsible for:
    - Owner actions (missing assignee, strategic objective, etc.) for their own initiatives
    - Dependency actions (create epic, set RAG) for their team as a dependent

    Args:
        grouped_data: Grouped manager data (grouped by initiative owner)

    Returns:
        List of message dicts for Slack template
    """
    messages = []
    jira_base_url = get_jira_base_url()
    team_mappings = load_team_mappings()
    team_managers = load_team_managers()

    # Regroup actions by who is responsible (not by initiative owner)
    actions_by_manager = defaultdict(lambda: {
        'manager_name': None,
        'slack_id': None,
        'team': None,
        'initiatives': defaultdict(lambda: {
            'key': None,
            'title': None,
            'url': None,
            'actions': []
        })
    })

    # Iterate through all issues and assign to responsible manager
    for owner_slack_id, owner_manager_data in grouped_data.items():
        for init_key, init_data in owner_manager_data['initiatives'].items():
            for issue in init_data['issues']:
                # Determine who is responsible for this action
                if issue.type in ['missing_epic', 'missing_rag_status']:
                    # Dependency action - team_affected manager is responsible
                    responsible_team = issue.team_affected
                    responsible_key = team_mappings.get(responsible_team, responsible_team) if team_mappings else responsible_team
                else:
                    # Owner action - initiative owner manager is responsible
                    responsible_team = issue.owner_team
                    responsible_key = team_mappings.get(responsible_team, responsible_team) if team_mappings else responsible_team

                if not responsible_key:
                    continue

                # Get manager info for responsible team
                if team_managers and responsible_key in team_managers:
                    # Use loaded team_managers config
                    manager_info = team_managers.get(responsible_key, {})
                    responsible_slack_id = manager_info.get('slack_id')
                    responsible_manager_name = manager_info.get('notion_handle', 'Unknown')
                elif responsible_key == owner_manager_data.get('team'):
                    # Fall back to owner manager data if team matches
                    responsible_slack_id = owner_slack_id
                    responsible_manager_name = owner_manager_data['manager_name']
                else:
                    # Can't find manager info, skip this action
                    continue

                if not responsible_slack_id or responsible_slack_id.startswith('unknown_'):
                    continue

                # Remove @ prefix
                if responsible_manager_name and responsible_manager_name.startswith('@'):
                    responsible_manager_name = responsible_manager_name[1:].strip()

                # Initialize manager entry
                if actions_by_manager[responsible_slack_id]['slack_id'] is None:
                    actions_by_manager[responsible_slack_id]['manager_name'] = responsible_manager_name
                    actions_by_manager[responsible_slack_id]['slack_id'] = responsible_slack_id
                    actions_by_manager[responsible_slack_id]['team'] = responsible_team

                # Initialize initiative entry
                if actions_by_manager[responsible_slack_id]['initiatives'][init_key]['key'] is None:
                    actions_by_manager[responsible_slack_id]['initiatives'][init_key]['key'] = init_key
                    actions_by_manager[responsible_slack_id]['initiatives'][init_key]['title'] = init_data['summary']
                    actions_by_manager[responsible_slack_id]['initiatives'][init_key]['url'] = f"{jira_base_url}/browse/{init_key}"

                # Add action
                action = {
                    'action_type': issue.type,
                    'description': issue.description,
                    'epic_key': issue.epic_key,
                    'priority': int(issue.priority),
                    'current_value': issue.current_value,
                }
                actions_by_manager[responsible_slack_id]['initiatives'][init_key]['actions'].append(action)

    # Convert to message format
    for slack_id, manager_data in actions_by_manager.items():
        # Build initiatives list
        initiatives = []
        total_actions = 0

        for init_key, init_data in sorted(manager_data['initiatives'].items()):
            # Sort actions by priority
            sorted_actions = sorted(init_data['actions'], key=lambda a: a['priority'])
            total_actions += len(sorted_actions)

            initiatives.append({
                'key': init_data['key'],
                'title': init_data['title'],
                'url': init_data['url'],
                'actions': sorted_actions,
            })

        messages.append({
            'manager_name': manager_data['manager_name'],
            'slack_id': slack_id,
            'total_actions': total_actions,
            'total_initiatives': len(initiatives),
            'teams': [{
                'team_name': manager_data['team'],
                'team_key': manager_data['team'],
                'initiatives': initiatives,
            }],
        })

    # Sort by manager name
    messages.sort(key=lambda m: m['manager_name'])

    return messages


def save_slack_output(content: str, output_dir: Path = None) -> Path:
    """Save Slack messages to output file.

    Args:
        content: Rendered Slack messages
        output_dir: Optional output directory (ignored, uses generate_output_path)

    Returns:
        Path to saved file
    """
    # Generate filename with sequence and timestamp
    filepath = generate_output_path(
        report_type='data_quality',
        extension='txt'
    )

    filepath.write_text(content, encoding='utf-8')
    return filepath


def main():
    """Main entry point."""
    args = parse_args()

    # Load data
    extract_file = find_latest_extract()
    if not extract_file:
        print('Error: No Jira extract found in data/ directory', file=sys.stderr)
        return 1

    if args.verbose:
        print(f'Loading data from: {extract_file}')

    with open(extract_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    initiatives = data.get('initiatives', [])
    if args.verbose:
        print(f'Loaded {len(initiatives)} initiatives')

    # Load exceptions
    signed_off = load_signed_off_initiatives()
    if args.verbose and signed_off:
        print(f'Loaded {len(signed_off)} signed-off exceptions')

    # Load excluded teams
    excluded_teams = load_excluded_teams()
    if args.verbose and excluded_teams:
        print(f'Loaded {len(excluded_teams)} excluded teams: {", ".join(excluded_teams)}')

    # Filter initiatives
    filtered = filter_initiatives(
        initiatives,
        quarter=args.quarter,
        status_filter=args.status,
        all_active=args.all_active,
        signed_off=signed_off,
        excluded_teams=excluded_teams
    )

    if args.verbose:
        print(f'Filtered to {len(filtered)} initiatives')

    # Determine filter description
    parts = []

    # Status/Active filter
    if args.status:
        parts.append(f'Status: {args.status}')
    elif args.all_active:
        parts.append('Status: Proposed, Planned, In Progress')
    else:
        parts.append('Status: In Progress (any quarter) + Planned')

    # Quarter filter
    if args.quarter:
        if args.status or args.all_active:
            parts.append(f'Quarter: {args.quarter}')
        else:
            # Default filter: only Planned uses quarter
            parts[-1] = f'Status: In Progress (any quarter) + Planned ({args.quarter})'

    filter_desc = ' AND '.join(parts) if len(parts) > 1 else parts[0]

    # Load validation config
    config = load_validation_config(
        status_filter=args.status if args.status else None,
        include_rag_validation=True
    )

    # Validate initiatives
    issues_by_initiative = validate_initiatives(filtered, config)

    if args.verbose:
        print(f'Found issues in {len(issues_by_initiative)} initiatives')

    # Load manager info and team mappings
    team_managers = load_team_managers()
    team_mappings = load_team_mappings()

    # Group by manager
    grouped_data = group_by_manager(issues_by_initiative, team_managers, team_mappings)

    # Filter by my teams if --me flag is set (console output only, not Slack)
    filtered_count = None
    total_count = None
    console_grouped_data = grouped_data

    if args.me:
        my_teams = load_my_teams()
        if my_teams:
            console_grouped_data, filtered_count, total_count = filter_grouped_data_by_teams(
                grouped_data, my_teams
            )
            if args.verbose:
                print(f'Filtering to {len(my_teams)} teams: {", ".join(my_teams)}')
                print(f'Showing {filtered_count} of {total_count} action items')
        else:
            print('Warning: --me flag used but no my_teams configured in team_mappings.yaml')

    # Prepare metadata
    metadata = {
        'quarter': args.quarter if args.quarter else 'All quarters',
        'filter': filter_desc,
        'initiatives_analyzed': len(filtered),
        'initiatives_with_issues': len(issues_by_initiative),
        'exceptions_skipped': len(signed_off),
        'excluded_teams': excluded_teams,
        'filtered_count': filtered_count,
        'total_count': total_count,
    }

    # Generate console output (filtered if --me flag set)
    console_output = format_console_output(console_grouped_data, metadata)
    print(console_output)

    # Generate Slack messages if requested
    if args.slack:
        messages = generate_slack_messages(grouped_data)

        # Render using template
        env = get_template_environment()
        template = env.get_template('notification_slack.j2')
        slack_content = template.render(
            messages=messages,
            jira_base_url=get_jira_base_url()
        )

        # Save to file
        output_dir = Path('output/data_quality')
        filepath = save_slack_output(slack_content, output_dir)

        print(f'\nSlack messages saved to: {filepath}')
        print(f'Total messages: {len(messages)}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
