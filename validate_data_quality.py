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

    # Generate Slack messages
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

    # Required
    parser.add_argument(
        '--quarter',
        required=True,
        help='Quarter to validate (e.g., "26 Q2")'
    )

    # Filtering
    parser.add_argument(
        '--status',
        help='Validate only this status (overrides default filter)'
    )
    parser.add_argument(
        '--all-active',
        action='store_true',
        help='Validate all active initiatives (not Done/Cancelled)'
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


def filter_initiatives(
    initiatives: List[Dict],
    quarter: str,
    status_filter: Optional[str],
    all_active: bool,
    signed_off: Set[str],
    excluded_teams: Optional[List[str]] = None
) -> List[Dict]:
    """Filter initiatives based on criteria.

    Default filter (no --status or --all-active):
    - Status = "In Progress" (any quarter), OR
    - Status = "Planned" AND Quarter = specified quarter

    Args:
        initiatives: List of initiative dicts
        quarter: Quarter filter (e.g., "26 Q2")
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

        # Apply filters
        if status_filter:
            # Explicit status filter
            if status == status_filter:
                filtered.append(initiative)
        elif all_active:
            # All active (not Done/Cancelled)
            if status not in ['Done', 'Cancelled']:
                filtered.append(initiative)
        else:
            # Default: In Progress (any quarter) + Planned (matching quarter)
            if status == 'In Progress':
                filtered.append(initiative)
            elif status == 'Planned' and init_quarter == quarter:
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
            # Determine which team should act on this issue
            # Dependency issues: team_affected acts
            # Owner issues: owner_team acts
            if issue.type in ['missing_epic', 'missing_rag_status']:
                acting_team = issue.team_affected
            else:
                acting_team = issue.owner_team

            if not acting_team:
                # Can't group without a team to act
                continue

            # Map display name to project key if needed
            project_key = team_mappings.get(acting_team, acting_team)

            manager_info = team_managers.get(project_key, {})
            manager_name = manager_info.get('notion_handle', 'Unknown')
            slack_id = manager_info.get('slack_id', f'unknown_{acting_team}')

            # Remove @ prefix from manager name if present
            if manager_name.startswith('@'):
                manager_name = manager_name[1:].strip()

            # Initialize manager entry
            if grouped[slack_id]['slack_id'] is None:
                grouped[slack_id]['manager_name'] = manager_name
                grouped[slack_id]['slack_id'] = slack_id
                grouped[slack_id]['team'] = acting_team

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

            lines.append(f"  {init_key}: {summary}")
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

                # Action owner is always the manager viewing this (already routed correctly by grouping)
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

    Args:
        grouped_data: Grouped manager data

    Returns:
        List of message dicts for Slack template
    """
    messages = []
    jira_base_url = get_jira_base_url()

    for slack_id, manager_data in grouped_data.items():
        if not manager_data['slack_id'] or manager_data['slack_id'].startswith('unknown_'):
            # Skip managers without valid Slack ID
            continue

        # Calculate totals
        total_actions = sum(
            len(init_data['issues'])
            for init_data in manager_data['initiatives'].values()
        )
        total_initiatives = len(manager_data['initiatives'])

        # Build initiatives list
        initiatives = []
        for init_key, init_data in sorted(manager_data['initiatives'].items()):
            # Sort issues by priority
            sorted_issues = sorted(init_data['issues'], key=lambda i: i.priority)

            actions = []
            for issue in sorted_issues:
                action = {
                    'action_type': issue.type,
                    'description': issue.description,
                    'epic_key': issue.epic_key,
                    'priority': int(issue.priority),
                    'current_value': issue.current_value,
                }
                actions.append(action)

            initiatives.append({
                'key': init_key,
                'title': init_data['summary'],
                'url': f"{jira_base_url}/browse/{init_key}",
                'actions': actions,
            })

        messages.append({
            'manager_name': manager_data['manager_name'],
            'slack_id': slack_id,
            'total_actions': total_actions,
            'total_initiatives': total_initiatives,
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
    if args.status:
        filter_desc = f'{args.status} status'
    elif args.all_active:
        filter_desc = 'All active (not Done/Cancelled)'
    else:
        filter_desc = f'In Progress (all quarters) + Planned ({args.quarter})'

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

    # Prepare metadata
    metadata = {
        'quarter': args.quarter,
        'filter': filter_desc,
        'initiatives_analyzed': len(filtered),
        'initiatives_with_issues': len(issues_by_initiative),
        'exceptions_skipped': len(signed_off),
        'excluded_teams': excluded_teams,
    }

    # Generate console output
    console_output = format_console_output(grouped_data, metadata)
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
