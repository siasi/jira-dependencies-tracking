#!/usr/bin/env python3
"""Analyze team workload from Jira extraction data.

This script analyzes how many initiatives each team is involved in,
distinguishing between leading (owner) and contributing (has epics).
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
from collections import defaultdict
from datetime import datetime
import yaml

from lib.common_formatting import make_clickable_link
from lib.config_utils import get_jira_base_url


def load_team_mappings() -> Tuple[Dict[str, str], List[str], Dict[str, str], Dict[str, Dict[str, str]], Dict[str, str]]:
    """Load team mappings, exclusions, strategic objective mappings, and team managers from team_mappings.yaml.

    Returns:
        Tuple of (team_mappings dict, excluded_teams list, strategic_objective_mappings dict, team_managers dict, reverse_team_mappings dict)
    """
    # Try config/ directory first, then fall back to root
    mappings_file = Path(__file__).parent / 'config' / 'team_mappings.yaml'
    if not mappings_file.exists():
        # Fall back to root with warning
        root_file = Path(__file__).parent / 'team_mappings.yaml'
        if root_file.exists():
            print("Warning: Using team_mappings.yaml from root directory. Please move to config/")
            mappings_file = root_file
        else:
            return {}, [], {}, {}, {}

    try:
        with open(mappings_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            team_mappings = data.get('team_mappings', {})

            # Load workload-specific exclusions with fallback to generic list
            excluded_teams = data.get('teams_excluded_from_workload_analysis')
            if excluded_teams is None:
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


def is_discovery_initiative(initiative: Dict) -> bool:
    """Check if an initiative is a discovery initiative.

    Discovery initiatives (prefixed with [Discovery]) are exempt from
    certain validation checks like missing epics.

    Args:
        initiative: Initiative dict with 'summary' field

    Returns:
        True if summary starts with "[Discovery]", False otherwise
    """
    summary = initiative.get('summary', '')
    return summary.startswith('[Discovery]')


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
    """Load valid strategic objective values from config/jira_config.yaml.

    Returns:
        List of valid strategic objective values, or empty list if not found
    """
    config_file = Path(__file__).parent / 'config' / 'jira_config.yaml'
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
                     strategic_objective_mappings: Dict[str, str], quarter: str) -> Dict:
    """Analyze team workload from extraction data.

    Args:
        json_file: Path to extraction JSON file
        team_mappings: Mapping from display names to project keys
        excluded_teams: List of teams to exclude from analysis
        strategic_objective_mappings: Mapping from old strategic objectives to current ones
        quarter: Quarter to analyze (e.g., "26 Q2")

    Returns:
        Dict with workload analysis results
    """
    # Load extraction data
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    all_initiatives = data.get('initiatives', [])

    # Filter initiatives: only include In Progress OR (matching quarter AND Planned)
    initiatives = []
    filtered_count = 0
    for initiative in all_initiatives:
        status = initiative.get('status', '')
        initiative_quarter = initiative.get('quarter', '')

        if status == 'In Progress':
            initiatives.append(initiative)
        elif initiative_quarter == quarter and status == 'Planned':
            initiatives.append(initiative)
        else:
            filtered_count += 1

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

    # Engineering vs Product work tracking
    engineering_led_count = 0
    product_led_count = 0
    team_engineering_work = defaultdict(lambda: {'leading': set(), 'contributing': set()})  # Track engineering work per team
    team_product_work = defaultdict(lambda: {'leading': set(), 'contributing': set()})  # Track product work per team

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

        # Classify as engineering-led or product-led
        is_engineering_led = mapped_objective == 'engineering_pillars'
        if is_engineering_led:
            engineering_led_count += 1
        else:
            product_led_count += 1

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

                # Track engineering vs product work for leading team
                if is_engineering_led:
                    team_engineering_work[normalized_owner]['leading'].add(initiative_key)
                else:
                    team_product_work[normalized_owner]['leading'].add(initiative_key)

        # Check for missing epics based on teams_involved field
        # Only report as "without epics" if there are contributing teams expected but missing epics
        # (excluding the owner team, who doesn't need to create an epic)
        # Discovery initiatives are exempt from epic checks
        is_discovery = is_discovery_initiative(initiative)
        teams_involved = normalize_teams_involved(initiative.get('teams_involved'))
        teams_with_epics = {
            tc['team_project_key']
            for tc in contributing_teams_data
            if tc.get('epics')
        }

        # Check for epic count mismatch (only if owner is not in excluded teams and not a discovery initiative)
        if not is_discovery and teams_involved and (not normalized_owner or normalized_owner not in excluded_teams):
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

                    # Only include team if they have active epics and are not excluded
                    if has_active_epic and team_project_key not in excluded_teams:
                        # Add to contributing teams list for CSV export
                        contributing_teams_list.append(team_project_key)

                        # Count as "contributing" for non-owner teams
                        workload[team_project_key]['contributing'].add(initiative_key)

                        # Track engineering vs product work for contributing team
                        if is_engineering_led:
                            team_engineering_work[team_project_key]['contributing'].add(initiative_key)
                        else:
                            team_product_work[team_project_key]['contributing'].add(initiative_key)

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

    # Calculate engineering vs product stats per team
    team_work_type_stats = {}
    for team in workload.keys():
        eng_leading = len(team_engineering_work[team]['leading'])
        eng_contributing = len(team_engineering_work[team]['contributing'])
        prod_leading = len(team_product_work[team]['leading'])
        prod_contributing = len(team_product_work[team]['contributing'])

        team_work_type_stats[team] = {
            'engineering': {
                'leading': eng_leading,
                'contributing': eng_contributing,
                'total': eng_leading + eng_contributing
            },
            'product': {
                'leading': prod_leading,
                'contributing': prod_contributing,
                'total': prod_leading + prod_contributing
            }
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
        'total_initiatives_before_filter': len(all_initiatives),
        'filtered_out_count': filtered_count,
        'engineering_led_count': engineering_led_count,
        'product_led_count': product_led_count,
        'team_work_type_stats': team_work_type_stats,
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


def extract_workload_actions(analysis: Dict, team_managers: Dict[str, Dict[str, str]],
                             reverse_team_mappings: Dict[str, str]) -> List[Dict[str, Any]]:
    """Extract action items from workload analysis data quality issues.

    This function flattens the data quality issues into a list of
    individual action items, each annotated with all metadata needed for
    any output format (console, markdown, Slack, etc.).

    Args:
        analysis: Results from analyze_workload()
        team_managers: Mapping of team keys to manager information
        reverse_team_mappings: Mapping of project keys to display names

    Returns:
        List of action item dictionaries with structure:
        {
            'initiative_key': 'INIT-XXXX',
            'initiative_title': 'Initiative Title',
            'initiative_status': 'In Progress',
            'initiative_url': 'https://company.atlassian.net/browse/INIT-XXXX',
            'section': 'data_quality',
            'action_type': 'missing_owner',
            'priority': 1,  # lower = higher priority
            'responsible_team': 'Team Display Name',
            'responsible_team_key': 'TEAMKEY',
            'responsible_manager_name': 'Manager Name',
            'responsible_manager_notion': '@Manager Name',
            'responsible_manager_slack_id': 'UXXXXXXXXXX',
            'description': 'Set owner_team for initiative',
            'epic_key': None,
            'epic_title': None,
            'epic_rag': None
        }

    Action types included:
    - 'missing_owner': Initiative needs owner_team set
    - 'missing_strategic_objective': Initiative needs strategic objective
    - 'invalid_strategic_objective': Initiative has invalid strategic objective value
    - 'missing_epics': Team needs to create epic

    Priority ordering (1=highest):
    1. missing_owner (blocks everything)
    2. missing_strategic_objective (blocks planning)
    3. invalid_strategic_objective (blocks planning)
    4. missing_epics (blocks execution)
    """
    actions = []

    # Priority mapping
    PRIORITY = {
        'missing_owner': 1,
        'missing_strategic_objective': 2,
        'invalid_strategic_objective': 3,
        'missing_epics': 4
    }

    # Helper to build base initiative context
    jira_base_url = get_jira_base_url()
    def _base_context(initiative: Dict, section: str) -> Dict:
        return {
            'initiative_key': initiative['key'],
            'initiative_title': initiative['summary'],
            'initiative_status': initiative.get('status', 'Unknown'),
            'initiative_url': f"{jira_base_url}/browse/{initiative['key']}",
            'section': section
        }

    # Helper to add manager info
    def _add_manager_info(action: Dict, team_key: str, team_display: str) -> Dict:
        manager_info = team_managers.get(team_key, {})
        action['responsible_team'] = team_display
        action['responsible_team_key'] = team_key
        action['responsible_manager_name'] = manager_info.get('notion_handle', '').strip('@').strip()
        action['responsible_manager_notion'] = manager_info.get('notion_handle', '')
        action['responsible_manager_slack_id'] = manager_info.get('slack_id')
        return action

    # Extract data from analysis
    initiatives_without_owner = analysis.get('initiatives_without_owner', [])
    initiatives_missing_strategic_objective = analysis.get('initiatives_missing_strategic_objective', [])
    initiatives_invalid_strategic_objective = analysis.get('initiatives_invalid_strategic_objective', [])
    initiatives_without_epics = analysis.get('initiatives_without_epics', [])

    # Process initiatives without owner
    for initiative in initiatives_without_owner:
        base = _base_context(initiative, 'data_quality')
        action = {
            **base,
            'action_type': 'missing_owner',
            'priority': PRIORITY['missing_owner'],
            'description': 'Set owner_team for initiative',
            'epic_key': None,
            'epic_title': None,
            'epic_rag': None
        }
        # No specific team responsible - this is a general action
        # Use empty team info
        action['responsible_team'] = ''
        action['responsible_team_key'] = ''
        action['responsible_manager_name'] = ''
        action['responsible_manager_notion'] = ''
        action['responsible_manager_slack_id'] = None
        actions.append(action)

    # Process initiatives with missing strategic objective
    for initiative in initiatives_missing_strategic_objective:
        base = _base_context(initiative, 'data_quality')
        owner_team = initiative.get('owner_team', '')
        owner_display = reverse_team_mappings.get(owner_team, owner_team)

        action = {
            **base,
            'action_type': 'missing_strategic_objective',
            'priority': PRIORITY['missing_strategic_objective'],
            'description': 'Set strategic objective',
            'epic_key': None,
            'epic_title': None,
            'epic_rag': None
        }
        _add_manager_info(action, owner_team, owner_display)
        actions.append(action)

    # Process initiatives with invalid strategic objective
    for initiative in initiatives_invalid_strategic_objective:
        base = _base_context(initiative, 'data_quality')
        owner_team = initiative.get('owner_team', '')
        owner_display = reverse_team_mappings.get(owner_team, owner_team)

        action = {
            **base,
            'action_type': 'invalid_strategic_objective',
            'priority': PRIORITY['invalid_strategic_objective'],
            'description': 'Fix invalid strategic objective value',
            'epic_key': None,
            'epic_title': None,
            'epic_rag': None,
            'current_value': initiative.get('current_value', '')
        }
        _add_manager_info(action, owner_team, owner_display)
        actions.append(action)

    # Process initiatives with missing epics
    # Create forward mapping (display_name → project_key) for team lookup
    forward_team_mappings = {v: k for k, v in reverse_team_mappings.items()}

    for initiative in initiatives_without_epics:
        base = _base_context(initiative, 'data_quality')
        owner_team = initiative.get('owner_team', '')
        missing_teams = initiative.get('missing_teams', [])

        # Create an action for each missing team
        for team_display_name in missing_teams:
            # Convert display name to project key for manager lookup
            team_key = forward_team_mappings.get(team_display_name, team_display_name)
            team_display = team_display_name

            action = {
                **base,
                'action_type': 'missing_epics',
                'priority': PRIORITY['missing_epics'],
                'description': 'Create epic',
                'epic_key': None,
                'epic_title': None,
                'epic_rag': None
            }
            _add_manager_info(action, team_key, team_display)
            actions.append(action)

    # Sort by priority (1=highest)
    actions.sort(key=lambda x: x['priority'])

    return actions


def generate_workload_slack_messages(analysis: Dict, team_managers: Dict[str, Dict[str, str]],
                                     reverse_team_mappings: Dict[str, str], output_dir: Path) -> None:
    """Generate Slack-compatible bulk messages for workload quality action items.

    Extracts action items from workload analysis, groups by manager,
    and renders using Jinja2 template. Outputs to console and file.

    Args:
        analysis: Workload analysis results from analyze_workload()
        team_managers: Mapping of team keys to manager information
        reverse_team_mappings: Mapping of project keys to display names
        output_dir: Directory to save output file (typically data/)

    Raises:
        ValueError: If team_managers config is missing Slack IDs
    """
    from collections import defaultdict
    from datetime import datetime
    from lib.template_renderer import get_template_environment

    # Validate configuration
    def _validate_slack_config(team_managers: Dict[str, Dict]) -> None:
        """Validate all teams have slack_id configured."""
        missing_slack_ids = []
        for team_key, info in team_managers.items():
            if not info.get('slack_id'):
                missing_slack_ids.append(team_key)

        if missing_slack_ids:
            raise ValueError(
                f"The following teams are missing slack_id in team_mappings.yaml: "
                f"{', '.join(missing_slack_ids)}\n"
                f"Add slack_id for each team before generating Slack messages."
            )

    _validate_slack_config(team_managers)

    # Extract actions
    actions = extract_workload_actions(analysis, team_managers, reverse_team_mappings)

    if not actions:
        print("\nNo action items to generate Slack messages for.")
        return

    # Track skipped actions for reporting
    skipped_actions = []

    # Group by manager Slack ID → teams → initiatives
    manager_groups = defaultdict(lambda: {
        'manager_name': None,
        'slack_id': None,
        'teams': defaultdict(lambda: {
            'team_name': None,
            'team_key': None,
            'initiatives': defaultdict(lambda: {
                'key': None,
                'title': None,
                'url': None,
                'actions': []
            })
        })
    })

    for action in actions:
        slack_id = action['responsible_manager_slack_id']
        if not slack_id:
            # Track skipped actions for reporting
            skipped_actions.append(action)
            continue

        manager_name = action['responsible_manager_name']
        team_key = action['responsible_team_key']
        team_name = action['responsible_team']
        initiative_key = action['initiative_key']

        # Initialize manager entry
        if manager_groups[slack_id]['slack_id'] is None:
            manager_groups[slack_id]['manager_name'] = manager_name
            manager_groups[slack_id]['slack_id'] = slack_id

        # Initialize team entry
        if manager_groups[slack_id]['teams'][team_key]['team_key'] is None:
            manager_groups[slack_id]['teams'][team_key]['team_name'] = team_name
            manager_groups[slack_id]['teams'][team_key]['team_key'] = team_key

        # Initialize initiative entry
        team_initiatives = manager_groups[slack_id]['teams'][team_key]['initiatives']
        if team_initiatives[initiative_key]['key'] is None:
            team_initiatives[initiative_key]['key'] = initiative_key
            team_initiatives[initiative_key]['title'] = action['initiative_title']
            team_initiatives[initiative_key]['url'] = action['initiative_url']

        # Add action to initiative
        team_initiatives[initiative_key]['actions'].append({
            'action_type': action['action_type'],
            'description': action['description'],
            'epic_key': action.get('epic_key'),
            'epic_title': action.get('epic_title'),
            'priority': action['priority'],
            'current_value': action.get('current_value')  # For invalid_strategic_objective
        })

    # Convert to template-friendly structure
    messages = []
    for slack_id, manager_data in manager_groups.items():
        teams = []
        total_actions = 0
        total_initiatives = 0

        for team_key, team_data in manager_data['teams'].items():
            initiatives = []
            for init_key, init_data in team_data['initiatives'].items():
                # Sort actions by priority
                sorted_actions = sorted(init_data['actions'], key=lambda x: x['priority'])
                initiatives.append({
                    'key': init_key,
                    'title': init_data['title'],
                    'url': init_data['url'],
                    'actions': sorted_actions
                })
                total_actions += len(sorted_actions)
                total_initiatives += 1

            teams.append({
                'team_name': team_data['team_name'],
                'team_key': team_data['team_key'],
                'initiatives': initiatives
            })

        messages.append({
            'manager_name': manager_data['manager_name'],
            'slack_id': slack_id,
            'total_actions': total_actions,
            'total_initiatives': total_initiatives,
            'teams': teams
        })

    # Render template
    env = get_template_environment()
    template = env.get_template('notification_slack.j2')
    output = template.render(messages=messages, jira_base_url=get_jira_base_url())

    # Print to console
    print("\n" + "=" * 60)
    print("Slack Messages for Workload Quality Action Items")
    print("=" * 60 + "\n")
    print(output)

    # Save to file
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    output_file = output_dir / f'slack_messages_workload_{timestamp}.txt'
    output_file.write_text(output)

    print(f"\nSlack messages saved to: {output_file}")
    print(f"Total managers: {len(messages)}")
    print(f"Total action items: {sum(m['total_actions'] for m in messages)}")

    # Report skipped actions
    if skipped_actions:
        print(f"\n⚠️  Skipped {len(skipped_actions)} action item{'s' if len(skipped_actions) != 1 else ''} (no Slack ID configured):")
        # Group by reason
        missing_owner_count = sum(1 for a in skipped_actions if a['action_type'] == 'missing_owner')
        teams_without_slack = set(a['responsible_team_key'] for a in skipped_actions if a['responsible_team_key'])

        if missing_owner_count > 0:
            print(f"  - {missing_owner_count} initiative{'s' if missing_owner_count != 1 else ''} without owner_team")
        if teams_without_slack:
            print(f"  - Teams not in team_managers.yaml: {', '.join(sorted(teams_without_slack))}")


def print_workload_report(analysis: Dict, team_managers: Dict[str, Dict[str, str]] = None,
                         reverse_team_mappings: Dict[str, str] = None, verbose: bool = False,
                         show_quality: bool = False) -> None:
    """Print workload analysis report to console.

    Args:
        analysis: Results from analyze_workload()
        team_managers: Mapping of team keys to manager information
        reverse_team_mappings: Mapping of project keys to display names
        verbose: If True, show detailed list of initiatives per team
        show_quality: If True, show detailed data quality issues
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

    # Engineering vs Product Distribution
    engineering_led_count = analysis.get('engineering_led_count', 0)
    product_led_count = analysis.get('product_led_count', 0)
    if engineering_led_count + product_led_count > 0:
        eng_pct = round(engineering_led_count / (engineering_led_count + product_led_count) * 100)
        prod_pct = round(product_led_count / (engineering_led_count + product_led_count) * 100)
        print(f"\nWork Type Distribution:")
        print(f"  Engineering-led (engineering_pillars): {engineering_led_count} initiatives ({eng_pct}%)")
        print(f"  Product-led (all other objectives):    {product_led_count} initiatives ({prod_pct}%)")

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
        team_work_type_stats = analysis.get('team_work_type_stats', {})
        for team, stats in sorted_teams:
            eng_prod_str = ""
            if team in team_work_type_stats:
                eng_total = team_work_type_stats[team]['engineering']['total']
                prod_total = team_work_type_stats[team]['product']['total']
                if eng_total + prod_total > 0:
                    eng_pct = round(eng_total / (eng_total + prod_total) * 100)
                    eng_prod_str = f" | {eng_total} eng ({eng_pct}%), {prod_total} prod"
            print(f"{team}: {stats['total']} total ({stats['leading']} leading, {stats['contributing']} contributing){eng_prod_str}")
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

    # Data Quality section with action items
    # Count total issues
    total_issues = (
        len(initiatives_without_owner) +
        len(initiatives_without_epics) +
        len(initiatives_missing_strategic_objective) +
        len(initiatives_invalid_strategic_objective)
    )

    if show_quality:
        # Extract action items from data quality issues
        actions = extract_workload_actions(analysis, team_managers, reverse_team_mappings)

        # Show detailed issues section with action items
        print("\n" + "-" * 70)
        print("Data Quality Issues:")
        print("-" * 70)

        if actions:
            # Group actions by initiative
            from collections import defaultdict
            actions_by_initiative = defaultdict(list)
            for action in actions:
                actions_by_initiative[action['initiative_key']].append(action)

            # Process each initiative
            for init_key in sorted(actions_by_initiative.keys()):
                init_actions = sorted(actions_by_initiative[init_key], key=lambda x: x['priority'])
                first_action = init_actions[0]

                # Print initiative header
                clickable_key = make_clickable_link(init_key, first_action['initiative_url'])
                title = first_action['initiative_title']
                if len(title) > 70:
                    title = title[:67] + "..."

                print(f"\n{clickable_key}: {title}")

                # If initiative has owner, show it
                if first_action['action_type'] != 'missing_owner':
                    # Get actual owner from initiative_owner_teams
                    owner_key = initiative_owner_teams.get(init_key, '')
                    if owner_key:
                        owner_display = reverse_team_mappings.get(owner_key, owner_key)
                        print(f"   Owner: {owner_display}")

                # Print each action for this initiative
                for action in init_actions:
                    action_type = action['action_type']

                    if action_type == 'missing_owner':
                        print("\n   ⚠️  Missing owner_team - Action:")
                        print("       [ ] Set the owner_team for the initiative")

                    elif action_type == 'missing_strategic_objective':
                        manager_mention = f" {action['responsible_manager_notion']}" if action['responsible_manager_notion'] else ""
                        print("\n   ⚠️  Missing strategic objective - Action:")
                        print(f"       [ ] Set strategic objective{manager_mention}")

                    elif action_type == 'invalid_strategic_objective':
                        manager_mention = f" {action['responsible_manager_notion']}" if action['responsible_manager_notion'] else ""
                        current_value = action.get('current_value', '')
                        print("\n   ⚠️  Invalid strategic objective - Action:")
                        print(f"       [ ] Fix invalid strategic objective value{manager_mention}")
                        if current_value:
                            print(f"       Current value: \"{current_value}\"")

                    elif action_type == 'missing_epics':
                        team_display = action['responsible_team']
                        team_key = action['responsible_team_key']
                        manager_mention = f" {action['responsible_manager_notion']}" if action['responsible_manager_notion'] else ""
                        print(f"\n   ⚠️  Missing dependencies - Action:")
                        print(f"       [ ] {team_display} ({team_key}) to create epic{manager_mention}")

            print(f"\n{len(actions)} action item{'s' if len(actions) != 1 else ''} found across {len(actions_by_initiative)} initiative{'s' if len(actions_by_initiative) != 1 else ''}")
        else:
            print("\n✓ No data quality issues found")

    elif total_issues > 0:
        # Show summary line if issues exist but flag is not set
        print(f"\n⚠️  Data Quality: {total_issues} issue{'s' if total_issues != 1 else ''} detected - Run with --show-quality for details")

    print("\n" + "=" * 70 + "\n")


def print_markdown_report(analysis: Dict, team_managers: Dict[str, Dict[str, str]] = None,
                          reverse_team_mappings: Dict[str, str] = None) -> None:
    """Print workload analysis report in markdown format.

    Args:
        analysis: Results from analyze_workload()
        team_managers: Mapping of team keys to manager information
        reverse_team_mappings: Mapping of project keys to display names
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
    initiatives_without_owner = analysis['initiatives_without_owner']
    initiatives_without_epics = analysis['initiatives_without_epics']
    initiatives_missing_strategic_objective = analysis.get('initiatives_missing_strategic_objective', [])
    initiatives_invalid_strategic_objective = analysis.get('initiatives_invalid_strategic_objective', [])
    total_initiatives = analysis['total_initiatives']
    excluded_teams = analysis['excluded_teams']

    # Header
    print("# Team Workload Report\n")
    print(f"**Total initiatives analyzed:** {total_initiatives}\n")

    if excluded_teams:
        print(f"**Excluded teams:** {', '.join(excluded_teams)}\n")

    # Team Analysis - Table format
    print("## Team Analysis\n")
    print("| Team | Leading | Contributing | Total |")
    print("|------|---------|--------------|-------|")

    # Sort teams by total initiatives (descending)
    sorted_teams = sorted(
        team_stats.items(),
        key=lambda x: x[1]['total'],
        reverse=True
    )

    if sorted_teams:
        for team, stats in sorted_teams:
            team_display = reverse_team_mappings.get(team, team)
            print(f"| {team_display} | {stats['leading']} | {stats['contributing']} | {stats['total']} |")
    else:
        print("| No teams found | - | - | - |")

    print()

    # Detailed Breakdown by Team
    print("## Detailed Breakdown by Team\n")

    for team, stats in sorted_teams:
        details = team_details.get(team, {})
        leading_list = details.get('leading', [])
        contributing_list = details.get('contributing', [])

        # Get team display name
        team_display = reverse_team_mappings.get(team, team)

        # Get manager info
        manager_info = team_managers.get(team, {})
        manager_handle = manager_info.get('notion_handle', '')
        manager_part = f" - {manager_handle}" if manager_handle else ""

        print(f"### {team_display}{manager_part} - {stats['total']} total initiatives\n")

        # Leading initiatives
        if leading_list:
            print(f"**Leading ({stats['leading']} initiatives):**\n")
            for init_key in leading_list:
                summary = initiative_summaries.get(init_key, 'No summary')
                url = initiative_urls.get(init_key, '')
                # Truncate long summaries
                if len(summary) > 70:
                    summary = summary[:67] + "..."
                # Create markdown link
                if url:
                    link = f"[{init_key}]({url})"
                else:
                    link = init_key
                print(f"- {link}: {summary}")
            print()
        else:
            print("**Leading:** None\n")

        # Contributing initiatives
        if contributing_list:
            print(f"**Contributing ({stats['contributing']} initiatives):**\n")
            for init_key in contributing_list:
                summary = initiative_summaries.get(init_key, 'No summary')
                url = initiative_urls.get(init_key, '')
                # Truncate long summaries
                if len(summary) > 70:
                    summary = summary[:67] + "..."
                # Create markdown link
                if url:
                    link = f"[{init_key}]({url})"
                else:
                    link = init_key

                # Get RAG status
                team_rag_data = contributing_rag.get(team, {})
                rag_statuses = team_rag_data.get(init_key, [])
                rag_circle = aggregate_rag_status(rag_statuses)

                print(f"- {rag_circle} {link}: {summary}")
            print()
        else:
            print("**Contributing:** None\n")

    # Issues section
    print("## Issues\n")

    # Initiatives without owner
    if initiatives_without_owner:
        print(f"### Initiatives without owner_team ({len(initiatives_without_owner)})\n")
        for init in initiatives_without_owner:
            summary = init['summary']
            if len(summary) > 60:
                summary = summary[:57] + "..."
            url = initiative_urls.get(init['key'], '')
            if url:
                link = f"[{init['key']}]({url})"
            else:
                link = init['key']
            print(f"- {link}: \"{summary}\"")
        print()
    else:
        print("✓ All initiatives have owner_team\n")

    # Initiatives with missing epics
    if initiatives_without_epics:
        print(f"### Initiatives with missing contributing epics ({len(initiatives_without_epics)})\n")
        for init in initiatives_without_epics:
            summary = init['summary']
            if len(summary) > 45:
                summary = summary[:42] + "..."
            owner = init.get('owner_team', 'None')
            owner_display = reverse_team_mappings.get(owner, owner)
            missing_teams = init.get('missing_teams', [])
            url = initiative_urls.get(init['key'], '')
            if url:
                link = f"[{init['key']}]({url})"
            else:
                link = init['key']
            print(f"- {link} (owner: {owner_display}): \"{summary}\"")
            if missing_teams:
                print(f"  - Missing epics from: {', '.join(missing_teams)}")
        print()
    else:
        print("✓ All contributing teams have created their epics\n")

    # Initiatives with missing strategic objective
    if initiatives_missing_strategic_objective:
        print(f"### Initiatives without strategic objective ({len(initiatives_missing_strategic_objective)})\n")
        for init in initiatives_missing_strategic_objective:
            summary = init['summary']
            if len(summary) > 50:
                summary = summary[:47] + "..."
            owner = init.get('owner_team', 'None')
            owner_display = reverse_team_mappings.get(owner, owner)
            manager_info = team_managers.get(owner, {})
            manager_handle = manager_info.get('notion_handle', '')
            manager_display = f" {manager_handle}" if manager_handle else ""
            url = initiative_urls.get(init['key'], '')
            if url:
                link = f"[{init['key']}]({url})"
            else:
                link = init['key']
            print(f"- {link} (owner: {owner_display}{manager_display}): \"{summary}\"")
        print()
    else:
        print("✓ All initiatives have strategic objective set\n")

    # Initiatives with invalid strategic objective
    if initiatives_invalid_strategic_objective:
        print(f"### Initiatives with invalid strategic objective ({len(initiatives_invalid_strategic_objective)})\n")
        for init in initiatives_invalid_strategic_objective:
            summary = init['summary']
            if len(summary) > 40:
                summary = summary[:37] + "..."
            owner = init.get('owner_team', 'None')
            owner_display = reverse_team_mappings.get(owner, owner)
            current = init['current_value']
            manager_info = team_managers.get(owner, {})
            manager_handle = manager_info.get('notion_handle', '')
            manager_display = f" {manager_handle}" if manager_handle else ""
            url = initiative_urls.get(init['key'], '')
            if url:
                link = f"[{init['key']}]({url})"
            else:
                link = init['key']
            print(f"- {link} (owner: {owner_display}{manager_display}): \"{summary}\"")
            print(f"  - Current value: \"{current}\"")
        print()
    else:
        print("✓ All strategic objectives are valid\n")


def generate_dashboard_csv(analysis: Dict, initiative_summaries: Dict[str, str],
                            initiative_strategic_objectives: Dict[str, str],
                            initiative_owner_teams: Dict[str, str],
                            initiative_contributing_teams: Dict[str, List[str]]) -> str:
    """Generate CSV data for the HTML dashboard.

    CSV Format:
    initiative_key,initiative_name,strategic_objective,leading_team,contributing_teams

    Args:
        analysis: Workload analysis results from analyze_workload()
        initiative_summaries: Map of initiative key to summary
        initiative_strategic_objectives: Map of initiative key to strategic objective
        initiative_owner_teams: Map of initiative key to owner team
        initiative_contributing_teams: Map of initiative key to contributing teams list

    Returns:
        CSV string with header and data rows
    """
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(['initiative_key', 'initiative_name', 'strategic_objective',
                     'leading_team', 'contributing_teams'])

    # Collect all initiatives from workload analysis
    all_initiative_keys = set()
    for team_data in analysis['team_details'].values():
        all_initiative_keys.update(team_data['leading'])
        all_initiative_keys.update(team_data['contributing'])

    # Write data rows
    for init_key in sorted(all_initiative_keys):
        name = initiative_summaries.get(init_key, '')
        objective = initiative_strategic_objectives.get(init_key, '')
        owner = initiative_owner_teams.get(init_key, '')
        contrib = initiative_contributing_teams.get(init_key, [])
        contrib_str = ','.join(contrib) if contrib else ''

        writer.writerow([init_key, name, objective, owner, contrib_str])

    return output.getvalue()


def generate_html_dashboard(analysis: Dict, initiative_summaries: Dict[str, str],
                             initiative_urls: Dict[str, str],
                             initiative_strategic_objectives: Dict[str, str],
                             initiative_owner_teams: Dict[str, str],
                             initiative_contributing_teams: Dict[str, List[str]],
                             output_file: Path,
                             json_file: Path,
                             reverse_team_mappings: Dict[str, str] = None) -> None:
    """Generate interactive HTML dashboard for workload analysis.

    Args:
        analysis: Workload analysis results from analyze_workload()
        initiative_summaries: Map of initiative key to summary
        initiative_urls: Map of initiative key to Jira URL
        initiative_strategic_objectives: Map of initiative key to strategic objective
        initiative_owner_teams: Map of initiative key to owner team
        initiative_contributing_teams: Map of initiative key to contributing teams list
        output_file: Path to save HTML file
        json_file: Path to source JSON file (for snapshot description)
        reverse_team_mappings: Optional mapping from project keys to display names
    """
    from lib.template_renderer import get_template_environment
    from datetime import datetime

    # Generate CSV data for the dashboard
    csv_data = generate_dashboard_csv(
        analysis,
        initiative_summaries,
        initiative_strategic_objectives,
        initiative_owner_teams,
        initiative_contributing_teams
    )

    # Escape special characters in CSV data to prevent breaking JavaScript template literal
    # Must escape backslashes first, then other special chars
    csv_data = csv_data.replace('\\', '\\\\')  # Escape backslashes
    csv_data = csv_data.replace('`', '\\`')    # Escape backticks
    csv_data = csv_data.replace('${', '\\${')  # Escape template expressions

    # Extract Jira base URL from first initiative URL
    jira_base_url = 'https://your-org.atlassian.net/browse/'
    if initiative_urls:
        first_url = next(iter(initiative_urls.values()))
        if first_url and '/browse/' in first_url:
            jira_base_url = first_url.split('/browse/')[0] + '/browse/'

    # Generate snapshot description
    snapshot_desc = f"Workload analysis from {json_file.name} · Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    # Prepare team name mapping for JavaScript (default to empty dict if not provided)
    if reverse_team_mappings is None:
        reverse_team_mappings = {}

    # Convert to JSON string for template
    import json as json_lib
    team_names_json = json_lib.dumps(reverse_team_mappings)

    # Render template
    env = get_template_environment()
    template = env.get_template('workload_dashboard.j2')
    html_output = template.render(
        csv_data=csv_data,
        jira_base_url=jira_base_url,
        snapshot_description=snapshot_desc,
        team_names_json=team_names_json
    )

    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_output)

    print(f"\n✓ HTML dashboard generated: {output_file}")
    print(f"  Open in browser to view interactive charts and heatmaps")


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

    parser.add_argument(
        '--show-quality',
        action='store_true',
        help='Show detailed data quality issues (missing owner, missing epics, missing objectives)'
    )

    parser.add_argument(
        '--slack',
        action='store_true',
        help='Generate Slack bulk messages for workload quality action items'
    )

    parser.add_argument(
        '--markdown',
        type=str,
        nargs='?',
        const='auto',
        metavar='FILENAME',
        help='Export report as markdown file. '
             'Optionally specify filename, otherwise auto-generates with timestamp.'
    )

    parser.add_argument(
        '--html',
        type=str,
        nargs='?',
        const='auto',
        metavar='FILENAME',
        help='Generate interactive HTML dashboard. '
             'Optionally specify filename, otherwise auto-generates with timestamp.'
    )

    parser.add_argument(
        '--csv',
        type=str,
        nargs='?',
        const='auto',
        metavar='FILENAME',
        help='Export initiative analysis as CSV file. '
             'Optionally specify filename, otherwise auto-generates with timestamp.'
    )

    parser.add_argument(
        '--quarter',
        required=True,
        type=str,
        help='Quarter to analyze (e.g., "26 Q2"). Only initiatives with status="In Progress" '
             'or (quarter=QUARTER and status="Planned") will be analyzed.'
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

    # Normalize excluded teams to project keys (since normalize_team_name converts display names to project keys)
    normalized_excluded_teams = []
    for team in excluded_teams:
        normalized = team_mappings.get(team, team)  # Convert display name to project key if mapping exists
        normalized_excluded_teams.append(normalized)
    excluded_teams = normalized_excluded_teams

    if args.verbose:
        print(f"Loaded {len(team_mappings)} team mappings")
        if excluded_teams:
            print(f"Excluding teams: {', '.join(excluded_teams)}")
        if strategic_objective_mappings:
            print(f"Loaded {len(strategic_objective_mappings)} strategic objective mappings")
        if team_managers:
            print(f"Loaded {len(team_managers)} team managers")

    # Analyze workload
    analysis = analyze_workload(json_file, team_mappings, excluded_teams, strategic_objective_mappings, args.quarter)

    # Print console report
    print_workload_report(analysis, team_managers=team_managers, reverse_team_mappings=reverse_team_mappings,
                         verbose=args.verbose, show_quality=args.show_quality)

    # Generate Slack messages if requested
    if args.slack:
        output_dir = Path('data')
        output_dir.mkdir(exist_ok=True)
        generate_workload_slack_messages(analysis, team_managers, reverse_team_mappings, output_dir)

    # Generate markdown export if requested
    if args.markdown:
        if args.markdown == 'auto':
            # Auto-generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            markdown_file = Path(f"workload_analysis_report_{timestamp}.md")
        else:
            markdown_file = Path(args.markdown)

        # Capture markdown output to string
        import io
        markdown_buffer = io.StringIO()
        original_stdout = sys.stdout
        sys.stdout = markdown_buffer

        try:
            print_markdown_report(analysis, team_managers=team_managers, reverse_team_mappings=reverse_team_mappings)
        finally:
            sys.stdout = original_stdout

        markdown_content = markdown_buffer.getvalue()

        # Write to file
        with open(markdown_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        print(f"\n✅ Markdown report exported to: {markdown_file}")

    # Generate HTML dashboard if requested
    if args.html:
        if args.html == 'auto':
            # Auto-generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            html_file = Path(f"workload_dashboard_{timestamp}.html")
        else:
            html_file = Path(args.html)

        generate_html_dashboard(
            analysis,
            analysis['initiative_summaries'],
            analysis['initiative_urls'],
            analysis['initiative_strategic_objectives'],
            analysis['initiative_owner_teams'],
            analysis['initiative_contributing_teams'],
            html_file,
            json_file,
            reverse_team_mappings
        )

    # Export CSV if requested
    if args.csv:
        if args.csv == 'auto':
            # Auto-generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_file = Path(f"workload_analysis_{timestamp}.csv")
        else:
            csv_file = Path(args.csv)

        # Generate CSV data
        csv_data = generate_dashboard_csv(
            analysis,
            analysis['initiative_summaries'],
            analysis['initiative_strategic_objectives'],
            analysis['initiative_owner_teams'],
            analysis['initiative_contributing_teams']
        )

        # Write to file
        with open(csv_file, 'w', encoding='utf-8') as f:
            f.write(csv_data)

        print(f"\n✅ CSV exported to: {csv_file}")


if __name__ == '__main__':
    main()
