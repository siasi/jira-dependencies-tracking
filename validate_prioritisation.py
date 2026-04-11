#!/usr/bin/env python3
"""
Initiative Priority Validation

Validates team commitments to prioritised initiatives and ensures
teams respect relative initiative priorities.
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import yaml
import click

from lib.file_utils import find_most_recent_data_file
from lib.config_utils import get_jira_base_url
from lib.output_utils import generate_output_path
from lib.template_renderer import get_template_environment

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Priority types for action items
PRIORITY_TYPES = {
    'priority_conflict': {
        'priority': 1,
        'description': 'Review commitment priority alignment',
        'emoji': ':warning:'
    },
    'missing_commitment': {
        'priority': 2,
        'description': 'No green/yellow epics despite involvement',
        'emoji': ':raising_hand:'
    }
}


@dataclass
class PrioritisationResult:
    """Container for prioritisation validation results."""
    priority_conflicts: List[Dict[str, Any]]      # Teams committed to lower priority
    missing_commitments: List[Dict[str, Any]]     # Teams with no commitments
    initiative_health: List[Dict[str, Any]]       # Initiative-centric view
    data_quality_issues: List[Dict[str, Any]]     # Missing teams_involved
    unlisted_initiatives: List[Dict[str, Any]]    # Initiatives not in priority config
    metadata: Dict[str, Any]                      # Summary stats

    @property
    def has_issues(self) -> bool:
        """Check if validation found any issues."""
        return bool(self.priority_conflicts or self.missing_commitments)


def _load_prioritisation_priorities(
    config_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Load and validate priorities config.

    Args:
        config_path: Optional custom config path

    Returns:
        Dict with 'priorities' (ordered list)

    Raises:
        ValueError: If config missing, invalid
    """
    if config_path is None:
        config_path = Path(__file__).parent / 'config' / 'priorities.yaml'

    if not config_path.exists():
        raise ValueError(
            f"Priority config not found: {config_path}\n"
            f"Create config/priorities.yaml from the .example file."
        )

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in priority config: {e}")

    # Validate structure
    if not isinstance(config, dict):
        raise ValueError("Priority config must be a YAML dictionary")

    if 'priorities' not in config:
        raise ValueError("Priority config missing 'priorities' key")

    priorities = config['priorities']
    if not isinstance(priorities, list) or len(priorities) == 0:
        raise ValueError("'priorities' must be a non-empty list of initiative keys")

    return config


def _is_discovery_initiative(initiative: Dict) -> bool:
    """Check if initiative is a Discovery initiative.

    Discovery initiatives (prefix [Discovery]) are exempt from
    priority validation.

    Args:
        initiative: Initiative dict with 'summary' field

    Returns:
        True if summary starts with "[Discovery]", False otherwise
    """
    summary = initiative.get('summary', '')
    return summary.startswith('[Discovery]')


def _is_active_initiative(initiative: Dict) -> bool:
    """Check if initiative is active (not Done or Cancelled).

    Args:
        initiative: Initiative dict with 'status' field

    Returns:
        True if status is not Done or Cancelled, False otherwise
    """
    status = initiative.get('status', '')
    return status not in ['Done', 'Cancelled']


def _normalize_teams_involved(teams_involved: Any) -> List[str]:
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


def _filter_excluded_teams(teams: List[str], excluded_teams: List[str]) -> List[str]:
    """Filter out excluded teams from a list.

    Args:
        teams: List of team names
        excluded_teams: List of teams to exclude

    Returns:
        Filtered list with excluded teams removed
    """
    if not excluded_teams:
        return teams

    return [team for team in teams if team not in excluded_teams]


def _load_team_mappings() -> tuple:
    """Load team mappings from config.

    Returns tuple of (team_mappings, reverse_team_mappings, excluded_teams)
    """
    mappings_file = Path(__file__).parent / 'config' / 'team_mappings.yaml'
    if not mappings_file.exists():
        logger.warning("team_mappings.yaml not found in config/")
        return {}, {}, []

    try:
        with open(mappings_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            team_mappings = data.get('team_mappings', {})

            # Create reverse mapping: project_key -> display_name
            reverse_team_mappings = {v: k for k, v in team_mappings.items()}

            # Load prioritisation-specific exclusions with fallback
            excluded_teams = data.get('teams_excluded_from_prioritisation')
            if excluded_teams is None:
                excluded_teams = data.get('teams_excluded_from_analysis', [])

            return team_mappings, reverse_team_mappings, excluded_teams
    except Exception as e:
        logger.warning(f"Could not load team mappings: {e}")
        return {}, {}, []


def _load_team_managers() -> Dict[str, Dict[str, Optional[str]]]:
    """Load team managers with Notion handles and Slack IDs.

    Returns:
        Dict mapping project keys to manager info:
        {
            "CBPPE": {
                "notion_handle": "@Manager B",
                "slack_id": "U01F3QUHP0B"
            }
        }

        Handles legacy string format for backward compatibility.
    """
    mappings_file = Path(__file__).parent / 'config' / 'team_mappings.yaml'
    if not mappings_file.exists():
        return {}

    try:
        with open(mappings_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            raw_managers = data.get('team_managers', {})

            # Normalize to dict format
            normalized = {}
            for project_key, value in raw_managers.items():
                if isinstance(value, str):
                    # Legacy format: just Notion handle
                    normalized[project_key] = {
                        'notion_handle': value,
                        'slack_id': None
                    }
                elif isinstance(value, dict):
                    # New format: structured data
                    normalized[project_key] = {
                        'notion_handle': value.get('notion_handle', ''),
                        'slack_id': value.get('slack_id')
                    }

            return normalized
    except Exception:
        return {}


def _load_signed_off_initiatives() -> set:
    """Load list of initiative keys that have manager sign-off.

    Signed-off initiatives are completely excluded from validation reports
    because managers have explicitly approved their current state despite
    any inconsistencies.

    Returns:
        Set of initiative keys to skip validation (e.g., {"INIT-1234"})
    """
    exceptions_file = Path(__file__).parent / 'config' / 'initiative_exceptions.yaml'
    if not exceptions_file.exists():
        return set()

    try:
        with open(exceptions_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            signed_off = data.get('signed_off_initiatives', [])

            # Extract keys from list of dicts
            keys = set()
            for item in signed_off:
                if not isinstance(item, dict):
                    continue  # Skip malformed items silently
                if 'key' not in item:
                    continue  # Skip items without key
                keys.add(item['key'])

            return keys
    except yaml.YAMLError as e:
        # Invalid YAML is a config error (fail fast)
        logger.error(f"Invalid YAML in initiative_exceptions.yaml: {e}")
        sys.exit(2)
    except Exception as e:
        # Unexpected errors are fatal
        logger.error(f"Could not load initiative_exceptions.yaml: {e}")
        sys.exit(2)


def _validate_slack_config(team_managers: Dict[str, Dict[str, Any]]) -> None:
    """Validate all teams have Slack IDs for Slack messaging.

    Args:
        team_managers: Dict of team manager info from _load_team_managers()

    Raises:
        ValueError: If any team is missing slack_id
    """
    missing = [
        key for key, info in team_managers.items()
        if not info.get('slack_id')
    ]
    if missing:
        raise ValueError(
            f"Missing Slack IDs for teams: {', '.join(missing)}\n"
            f"Update team_mappings.yaml with slack_id for each team"
        )


def _get_team_epics_rag_statuses(
    initiative: Dict,
    team_key: str
) -> List[str]:
    """Get all RAG statuses for a team's epics in an initiative.

    Args:
        initiative: Initiative dict with contributing_teams
        team_key: Team project key to look up

    Returns:
        List of RAG status strings (may include None)
    """
    contributing_teams = initiative.get('contributing_teams', [])

    for team in contributing_teams:
        if team.get('team_project_key') == team_key:
            epics = team.get('epics', [])
            return [epic.get('rag_status') for epic in epics]

    return []


def _get_team_epics_data(
    initiative: Dict,
    team_key: str
) -> List[Dict]:
    """Get all epic data for a team's epics in an initiative.

    Args:
        initiative: Initiative dict with contributing_teams
        team_key: Team project key to look up

    Returns:
        List of epic dicts with rag_status and status fields
    """
    contributing_teams = initiative.get('contributing_teams', [])

    for team in contributing_teams:
        if team.get('team_project_key') == team_key:
            return team.get('epics', [])

    return []


def _is_team_committed(rag_statuses: List[str]) -> bool:
    """Check if team is committed based on epic RAG statuses.

    DEPRECATED: Use _is_team_committed_with_epics instead.
    Kept for backward compatibility with existing tests.

    Commitment requires:
    - At least one epic exists
    - ALL epics must be non-red (green, yellow, or amber)
    - No red RAG statuses
    - No missing/None RAG statuses

    Args:
        rag_statuses: List of RAG status strings (may include None)

    Returns:
        True if committed, False otherwise
    """
    if not rag_statuses:
        return False

    # If ANY epic is red or missing RAG, not committed
    for rag in rag_statuses:
        if rag is None or rag == '🔴':
            return False

    # All epics are green/yellow/amber
    return True


def _is_team_committed_with_epics(epics: List[Dict]) -> bool:
    """Check if team is committed based on epic data.

    Commitment requires at least one epic AND all epics must be either:
    - Non-red RAG (green, yellow, or amber), OR
    - Status = Done (work already completed)

    A team with Done epics is considered committed even if RAG is red,
    since they've already completed their contribution.

    Args:
        epics: List of epic dicts with 'rag_status' and 'status' fields

    Returns:
        True if committed, False otherwise
    """
    if not epics:
        return False

    # Check each epic - must be either non-red OR Done
    for epic in epics:
        rag = epic.get('rag_status')
        status = epic.get('status', '')

        # Epic is Done - work completed, counts as committed
        if status == 'Done':
            continue

        # Epic is not Done - must have non-red RAG
        if rag is None or rag == '🔴':
            return False

    # All epics are either non-red OR Done
    return True


def _build_commitment_matrix(
    initiatives: List[Dict],
    priorities: List[str],
    team_mappings: Dict[str, str],
    reverse_team_mappings: Dict[str, str],
    excluded_teams: List[str]
) -> Dict[str, Dict[str, Any]]:
    """Build commitment matrix for prioritised initiatives.

    Args:
        initiatives: List of all initiative dicts
        priorities: Ordered list of initiative keys (highest priority first)
        team_mappings: Map display name → project key
        reverse_team_mappings: Map project key → display name
        excluded_teams: List of team names to exclude from analysis

    Returns:
        Dict mapping team_key to commitment data
    """
    from collections import defaultdict

    matrix = defaultdict(lambda: {
        'team_display': None,
        'committed_initiatives': [],
        'expected_initiatives': []
    })

    # Create priority index lookup
    priority_index = {key: idx for idx, key in enumerate(priorities)}

    for initiative in initiatives:
        init_key = initiative['key']
        init_title = initiative.get('summary', init_key)

        # Skip if not in priority list
        if init_key not in priority_index:
            continue

        priority_idx = priority_index[init_key]

        # Get expected teams and filter excluded ones
        teams_involved = _normalize_teams_involved(initiative.get('teams_involved'))
        teams_involved = _filter_excluded_teams(teams_involved, excluded_teams)

        # Filter out owner team (they don't need to create epics for their own initiatives)
        owner_team = initiative.get('owner_team')
        if owner_team and owner_team in teams_involved:
            teams_involved = [team for team in teams_involved if team != owner_team]

        for team_display in teams_involved:
            team_key = team_mappings.get(team_display, team_display)

            # Set team display name
            if matrix[team_key]['team_display'] is None:
                matrix[team_key]['team_display'] = team_display

            # Get epic data
            epics = _get_team_epics_data(initiative, team_key)
            rag_statuses = [epic.get('rag_status') for epic in epics]
            epic_keys = [epic.get('key') for epic in epics] if epics else []
            is_committed = _is_team_committed_with_epics(epics)

            # Add to expected initiatives
            matrix[team_key]['expected_initiatives'].append({
                'key': init_key,
                'title': init_title,
                'priority_index': priority_idx,
                'is_committed': is_committed,
                'rag_statuses': rag_statuses,
                'epic_keys': epic_keys
            })

            # Add to committed initiatives if committed
            if is_committed:
                matrix[team_key]['committed_initiatives'].append({
                    'key': init_key,
                    'title': init_title,
                    'priority_index': priority_idx,
                    'rag_statuses': rag_statuses
                })

    # Sort committed and expected initiatives by priority
    for team_data in matrix.values():
        team_data['committed_initiatives'].sort(key=lambda x: x['priority_index'])
        team_data['expected_initiatives'].sort(key=lambda x: x['priority_index'])

    return dict(matrix)


def _detect_priority_conflicts(
    commitment_matrix: Dict[str, Dict[str, Any]],
    priorities: List[str]
) -> List[Dict[str, Any]]:
    """Detect teams committed to lower-priority initiatives but not higher-priority ones.

    Args:
        commitment_matrix: Output from _build_commitment_matrix
        priorities: Ordered list of initiative keys

    Returns:
        List of conflict dicts
    """
    conflicts = []

    for team_key, team_data in commitment_matrix.items():
        committed = team_data['committed_initiatives']
        expected = team_data['expected_initiatives']

        # Skip if no commitments
        if not committed:
            continue

        # Find expected initiatives they're NOT committed to
        missing = [init for init in expected if not init['is_committed']]

        # Find higher-priority gaps
        # (missing initiatives with lower priority_index than any committed initiative)
        if committed and missing:
            lowest_committed_priority = min(init['priority_index'] for init in committed)
            higher_priority_gaps = [
                init for init in missing
                if init['priority_index'] < lowest_committed_priority
            ]

            if higher_priority_gaps:
                conflicts.append({
                    'team_key': team_key,
                    'team_display': team_data['team_display'],
                    'committed_to': [
                        {
                            'key': init['key'],
                            'title': init['title'],
                            'priority': init['priority_index'] + 1  # 1-indexed for display
                        }
                        for init in committed
                    ],
                    'missing_higher_priorities': [
                        {
                            'key': init['key'],
                            'title': init['title'],
                            'priority': init['priority_index'] + 1
                        }
                        for init in higher_priority_gaps
                    ]
                })

    return conflicts


def _detect_missing_commitments(
    commitment_matrix: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Detect teams expected to contribute but with zero commitments.

    Categorizes missing commitments by reason:
    - no_epic: Team has no epic created
    - missing_rag: Epic exists but has no RAG status
    - red_rag: Epic exists but has red RAG status

    Args:
        commitment_matrix: Output from _build_commitment_matrix

    Returns:
        List of missing commitment dicts with categorized issues
    """
    missing = []

    for team_key, team_data in commitment_matrix.items():
        # Has expected initiatives but no commitments
        if team_data['expected_initiatives'] and not team_data['committed_initiatives']:
            # Categorize each non-committed initiative by reason
            issues_by_initiative = []

            for init in team_data['expected_initiatives']:
                if not init['is_committed']:
                    # Determine the reason
                    rag_statuses = init.get('rag_statuses', [])
                    epic_keys = init.get('epic_keys', [])

                    if not epic_keys:
                        # No epic created at all
                        reason = 'no_epic'
                        epic_key = None
                    elif any(rag is None for rag in rag_statuses):
                        # Epic exists but has no RAG status
                        reason = 'missing_rag'
                        # Get the epic key(s) with None RAG
                        none_rag_epics = [
                            epic_keys[i] for i, rag in enumerate(rag_statuses)
                            if rag is None
                        ]
                        epic_key = none_rag_epics[0] if none_rag_epics else epic_keys[0]
                    elif any(rag == '🔴' for rag in rag_statuses):
                        # Epic exists but has red RAG
                        reason = 'red_rag'
                        # Get the epic key(s) with red RAG
                        red_rag_epics = [
                            epic_keys[i] for i, rag in enumerate(rag_statuses)
                            if rag == '🔴'
                        ]
                        epic_key = red_rag_epics[0] if red_rag_epics else epic_keys[0]
                    else:
                        # Shouldn't happen, but fallback
                        reason = 'no_epic'
                        epic_key = None

                    issues_by_initiative.append({
                        'key': init['key'],
                        'title': init['title'],
                        'reason': reason,
                        'epic_key': epic_key
                    })

            if issues_by_initiative:
                missing.append({
                    'team_key': team_key,
                    'team_display': team_data['team_display'],
                    'issues': issues_by_initiative
                })

    return missing


def _build_initiative_health(
    initiatives: List[Dict],
    priorities: List[str],
    team_mappings: Dict[str, str],
    excluded_teams: List[str]
) -> List[Dict[str, Any]]:
    """Build initiative health dashboard (initiative-centric view).

    Args:
        initiatives: List of all initiative dicts
        priorities: Ordered list of initiative keys
        team_mappings: Map display name → project key
        excluded_teams: List of team names to exclude from analysis

    Returns:
        List of initiative health dicts (in priority order)
    """
    health = []
    priority_index = {key: idx for idx, key in enumerate(priorities)}

    for initiative in initiatives:
        init_key = initiative['key']

        # Skip if not in priority list
        if init_key not in priority_index:
            continue

        init_title = initiative.get('summary', init_key)
        priority = priority_index[init_key] + 1  # 1-indexed

        # Get expected teams and filter excluded ones
        teams_involved = _normalize_teams_involved(initiative.get('teams_involved'))
        teams_involved = _filter_excluded_teams(teams_involved, excluded_teams)

        # Filter out owner team (they don't need to create epics for their own initiatives)
        owner_team = initiative.get('owner_team')
        if owner_team and owner_team in teams_involved:
            teams_involved = [team for team in teams_involved if team != owner_team]

        # Get committed teams
        committed = []
        missing = []

        for team_display in teams_involved:
            team_key = team_mappings.get(team_display, team_display)
            epics = _get_team_epics_data(initiative, team_key)
            rag_statuses = [epic.get('rag_status') for epic in epics]
            epic_keys = [epic.get('key') for epic in epics] if epics else []

            if _is_team_committed_with_epics(epics):
                # Check if all epics are Done (completed) vs active
                all_done = all(epic.get('status') == 'Done' for epic in epics)

                if all_done:
                    committed.append({
                        'team': team_display,
                        'completed': True
                    })
                else:
                    # Active - show RAG statuses for non-Done epics
                    active_rags = [
                        epic.get('rag_status')
                        for epic in epics
                        if epic.get('status') != 'Done'
                    ]
                    committed.append({
                        'team': team_display,
                        'completed': False,
                        'rag_statuses': active_rags
                    })
            else:
                # Determine reason for missing commitment
                if not epic_keys:
                    reason = 'no_epic'
                    epic_key = None
                elif any(rag is None for rag in rag_statuses):
                    reason = 'missing_rag'
                    none_rag_epics = [
                        epic_keys[i] for i, rag in enumerate(rag_statuses)
                        if rag is None
                    ]
                    epic_key = none_rag_epics[0] if none_rag_epics else epic_keys[0]
                elif any(rag == '🔴' for rag in rag_statuses):
                    reason = 'red_rag'
                    red_rag_epics = [
                        epic_keys[i] for i, rag in enumerate(rag_statuses)
                        if rag == '🔴'
                    ]
                    epic_key = red_rag_epics[0] if red_rag_epics else epic_keys[0]
                else:
                    reason = 'no_epic'
                    epic_key = None

                missing.append({
                    'team': team_display,
                    'reason': reason,
                    'epic_key': epic_key
                })

        # Separate completed from active teams
        completed_teams = [t for t in committed if t.get('completed')]
        active_teams = [t for t in committed if not t.get('completed')]

        health.append({
            'key': init_key,
            'title': init_title,
            'priority': priority,
            'expected_teams': teams_involved,
            'completed_teams': completed_teams,
            'active_teams': active_teams,
            'missing_teams': missing
        })

    # Sort by priority
    health.sort(key=lambda x: x['priority'])

    return health


def _check_data_quality(
    initiatives: List[Dict],
    priorities: List[str]
) -> Dict[str, List[Dict[str, Any]]]:
    """Check for data quality issues in Tech Leadership initiatives.

    Args:
        initiatives: List of all initiative dicts
        priorities: Ordered list of initiative keys

    Returns:
        Dict with missing_teams_involved and unlisted_initiatives
    """
    priority_set = set(priorities)
    missing_teams = []
    unlisted = []

    for initiative in initiatives:
        init_key = initiative['key']
        teams_involved = initiative.get('teams_involved')

        # In priority list, check for missing teams_involved
        if init_key in priority_set:
            if not teams_involved or (isinstance(teams_involved, list) and len(teams_involved) == 0):
                missing_teams.append(initiative)

        # Not in priority list
        elif init_key not in priority_set:
            unlisted.append(initiative)

    return {
        'missing_teams_involved': missing_teams,
        'unlisted_initiatives': unlisted
    }


def validate_prioritisation(
    data_file: Path,
    config_path: Optional[Path] = None
) -> PrioritisationResult:
    """Validate initiative priorities and team commitments.

    Args:
        data_file: Path to JSON extraction or snapshot file
        config_path: Optional custom priority config path

    Returns:
        PrioritisationResult with validation findings

    Raises:
        ValueError: If config invalid or missing
    """
    # Load priority config
    priority_config = _load_prioritisation_priorities(config_path)
    priorities = priority_config['priorities']

    logger.info(f"Loaded {len(priorities)} priorities from config")

    # Load data
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    initiatives = data.get('initiatives', [])
    logger.info(f"Loaded {len(initiatives)} total initiatives from {data_file}")

    # Filter out signed-off initiatives (manager-approved exceptions)
    signed_off_keys = _load_signed_off_initiatives()
    if signed_off_keys:
        signed_off_count = len([init for init in initiatives if init['key'] in signed_off_keys])
        initiatives = [init for init in initiatives if init['key'] not in signed_off_keys]
        logger.info(f"Filtered out {signed_off_count} signed-off initiatives")

    # Load team mappings
    team_mappings, reverse_team_mappings, excluded_teams = _load_team_mappings()

    # Filter to active (not Done/Cancelled)
    active_initiatives = [
        init for init in initiatives
        if _is_active_initiative(init)
    ]
    logger.info(f"Found {len(active_initiatives)} active initiatives")

    # Filter out Discovery initiatives
    non_discovery = [
        init for init in active_initiatives
        if not _is_discovery_initiative(init)
    ]
    logger.info(f"Found {len(non_discovery)} non-Discovery initiatives")

    # Filter to only initiatives in priority config
    priority_set = set(priorities)
    configured_initiatives = [
        init for init in non_discovery
        if init['key'] in priority_set
    ]
    logger.info(f"Found {len(configured_initiatives)} initiatives in priority config")

    # Check data quality
    quality_issues = _check_data_quality(configured_initiatives, priorities)

    # Warn about initiatives in config but not found in data (or filtered out)
    found_keys = {init['key'] for init in configured_initiatives}
    missing_from_data = [key for key in priorities if key not in found_keys]
    if missing_from_data:
        logger.warning(
            f"Priority config includes {len(missing_from_data)} initiatives not found or filtered out: "
            f"{', '.join(missing_from_data)}"
        )

    # Build commitment matrix
    commitment_matrix = _build_commitment_matrix(
        configured_initiatives,
        priorities,
        team_mappings,
        reverse_team_mappings,
        excluded_teams
    )
    logger.info(f"Built commitment matrix for {len(commitment_matrix)} teams")

    # Detect conflicts and missing commitments
    priority_conflicts = _detect_priority_conflicts(commitment_matrix, priorities)
    missing_commitments = _detect_missing_commitments(commitment_matrix)
    logger.info(f"Found {len(priority_conflicts)} priority conflicts and {len(missing_commitments)} missing commitments")

    # Build initiative health
    initiative_health = _build_initiative_health(
        configured_initiatives,
        priorities,
        team_mappings,
        excluded_teams
    )

    # Build result
    result = PrioritisationResult(
        priority_conflicts=priority_conflicts,
        missing_commitments=missing_commitments,
        initiative_health=initiative_health,
        data_quality_issues=quality_issues['missing_teams_involved'],
        unlisted_initiatives=quality_issues['unlisted_initiatives'],
        metadata={
            'total_initiatives': len(initiatives),
            'active_initiatives': len(active_initiatives),
            'validated_initiatives': len(configured_initiatives),
            'priorities_count': len(priorities),
            'teams_analyzed': len(commitment_matrix),
            'missing_from_data': missing_from_data
        }
    )

    return result


def print_prioritisation_report(
    result: PrioritisationResult,
    data_file: Path,
    verbose: bool = False
) -> None:
    """Print prioritisation validation report to console.

    Args:
        result: PrioritisationResult instance
        data_file: Path to data file (for reference)
        verbose: Include verbose output
    """
    env = get_template_environment()
    template = env.get_template('prioritisation_console.j2')
    jira_base_url = get_jira_base_url()

    # Load team mappings and managers for action item tagging
    team_mappings, reverse_team_mappings, _ = _load_team_mappings()
    team_managers = _load_team_managers()

    output = template.render(
        result=result,
        data_file=data_file,
        jira_base_url=jira_base_url,
        verbose=verbose,
        team_mappings=team_mappings,
        team_managers=team_managers
    )

    click.echo(output)


def extract_prioritisation_actions(
    result: PrioritisationResult,
    team_managers: Dict[str, Dict[str, Optional[str]]],
    reverse_team_mappings: Dict[str, str]
) -> List[Dict[str, Any]]:
    """Extract action items from validation result.

    Args:
        result: PrioritisationResult instance
        team_managers: Map team_key to manager info
        reverse_team_mappings: Map project key to display name

    Returns:
        Flat list of action item dicts with manager metadata
    """
    actions = []
    jira_base_url = get_jira_base_url()

    # Helper to build base context
    def _base_context(team_key: str, team_display: str, section: str) -> Dict:
        manager_info = team_managers.get(team_key, {})
        return {
            'section': section,
            'responsible_team': team_display,
            'responsible_team_key': team_key,
            'responsible_manager_name': manager_info.get('notion_handle', '').lstrip('@'),
            'responsible_manager_notion': manager_info.get('notion_handle', ''),
            'responsible_manager_slack_id': manager_info.get('slack_id', ''),
        }

    # 1. Priority conflicts
    for conflict in result.priority_conflicts:
        team_key = conflict['team_key']
        team_display = conflict['team_display']

        # Create action for each missing higher-priority initiative
        for missing in conflict['missing_higher_priorities']:
            base = _base_context(team_key, team_display, 'priority_conflicts')
            actions.append({
                **base,
                'initiative_key': missing['key'],
                'initiative_title': missing['title'],
                'initiative_url': f"{jira_base_url}/browse/{missing['key']}",
                'action_type': 'priority_conflict',
                'priority': PRIORITY_TYPES['priority_conflict']['priority'],
                'description': (
                    f"Review commitment to lower-priority initiatives while "
                    f"skipping priority #{missing['priority']} ({missing['key']})"
                ),
                'committed_to': conflict['committed_to'],  # Extra context
                'epic_key': None,
                'epic_title': None,
                'epic_rag': None
            })

    # 2. Missing commitments - create specific action per issue
    for missing in result.missing_commitments:
        team_key = missing['team_key']
        team_display = missing['team_display']
        base = _base_context(team_key, team_display, 'missing_commitments')

        # Create action for each issue with specific description
        for issue in missing['issues']:
            if issue['reason'] == 'no_epic':
                description = f"Create epic for {issue['key']}"
                action_type = 'missing_epic'
            elif issue['reason'] == 'missing_rag':
                description = f"Set RAG status for {issue['epic_key']} in {issue['key']}"
                action_type = 'missing_rag'
            elif issue['reason'] == 'red_rag':
                description = f"Resolve blocker for {issue['epic_key']} in {issue['key']} or deprioritize"
                action_type = 'red_rag'
            else:
                description = f"Review commitment to {issue['key']}"
                action_type = 'missing_commitment'

            actions.append({
                **base,
                'initiative_key': issue['key'],
                'initiative_title': issue['title'],
                'initiative_url': f"{jira_base_url}/browse/{issue['key']}",
                'action_type': action_type,
                'priority': PRIORITY_TYPES['missing_commitment']['priority'],
                'description': description,
                'reason': issue['reason'],
                'epic_key': issue.get('epic_key'),
                'epic_title': None,
                'epic_rag': None
            })

    # 3. Initiative-level missing commitments from health dashboard
    # Extract unique actions from initiative health (teams missing specific initiatives)
    for init in result.initiative_health:
        for missing_team in init.get('missing_teams', []):
            team_display = missing_team['team']
            # Map team display name to team key
            team_key = None
            for k, v in reverse_team_mappings.items():
                if v == team_display:
                    team_key = k
                    break
            if not team_key:
                team_key = team_display

            base = _base_context(team_key, team_display, 'missing_commitments')

            # Build description based on reason
            reason = missing_team['reason']
            if reason == 'no_epic':
                description = f"Create epic for {init['key']}"
                action_type = 'missing_epic'
            elif reason == 'missing_rag':
                description = f"Set RAG status for {missing_team['epic_key']} in {init['key']}"
                action_type = 'missing_rag'
            elif reason == 'red_rag':
                description = f"Resolve blocker for {missing_team['epic_key']} in {init['key']} or deprioritize"
                action_type = 'red_rag'
            else:
                description = f"Review commitment to {init['key']}"
                action_type = 'missing_commitment'

            actions.append({
                **base,
                'initiative_key': init['key'],
                'initiative_title': init['title'],
                'initiative_url': f"{jira_base_url}/browse/{init['key']}",
                'action_type': action_type,
                'priority': PRIORITY_TYPES['missing_commitment']['priority'],
                'description': description,
                'reason': reason,
                'epic_key': missing_team.get('epic_key'),
                'epic_title': None,
                'epic_rag': None
            })

    # Sort by priority
    actions.sort(key=lambda x: x['priority'])

    return actions


def generate_markdown_report(
    result: PrioritisationResult,
    data_file: Path
) -> str:
    """Generate markdown-formatted Initiative Health Dashboard.

    Args:
        result: PrioritisationResult instance
        data_file: Path to data file (for reference)

    Returns:
        Markdown-formatted report string
    """
    from datetime import datetime

    env = get_template_environment()
    template = env.get_template('prioritisation_markdown.j2')
    jira_base_url = get_jira_base_url()

    output = template.render(
        result=result,
        data_file=data_file,
        jira_base_url=jira_base_url,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

    return output


def generate_prioritisation_slack_messages(
    result: PrioritisationResult,
    team_managers: Dict[str, Dict[str, Optional[str]]],
    reverse_team_mappings: Dict[str, str]
) -> None:
    """Generate Slack bulk messages for Tech Leadership validation.

    Args:
        result: PrioritisationResult instance
        team_managers: Map team_key to manager info
        reverse_team_mappings: Map project key to display name

    Raises:
        ValueError: If any team missing slack_id in config
    """
    from collections import defaultdict
    from datetime import datetime

    # Validate Slack config
    _validate_slack_config(team_managers)

    # Extract actions
    actions = extract_prioritisation_actions(result, team_managers, reverse_team_mappings)

    if not actions:
        click.echo(click.style("No action items to send via Slack.", fg='green'))
        return

    # Group by manager (same pattern as validate_planning.py)
    manager_groups = defaultdict(lambda: {
        'manager_name': None,
        'slack_id': None,
        'total_actions': 0,
        'total_initiatives': 0,
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
        team_key = action['responsible_team_key']
        team_name = action['responsible_team']
        manager_name = action['responsible_manager_name']

        # Set manager info
        if manager_groups[slack_id]['manager_name'] is None:
            manager_groups[slack_id]['manager_name'] = manager_name
            manager_groups[slack_id]['slack_id'] = slack_id

        # Set team info
        if manager_groups[slack_id]['teams'][team_key]['team_name'] is None:
            manager_groups[slack_id]['teams'][team_key]['team_name'] = team_name
            manager_groups[slack_id]['teams'][team_key]['team_key'] = team_key

        # Add to initiative
        init_key = action.get('initiative_key') or 'MULTIPLE'
        init_group = manager_groups[slack_id]['teams'][team_key]['initiatives'][init_key]

        if init_group['key'] is None:
            init_group['key'] = action.get('initiative_key')
            init_group['title'] = action['initiative_title']
            init_group['url'] = action.get('initiative_url')

        init_group['actions'].append(action)
        manager_groups[slack_id]['total_actions'] += 1

    # Count unique initiatives per manager
    for slack_id, manager_data in manager_groups.items():
        unique_initiatives = set()
        for team_data in manager_data['teams'].values():
            for init_key in team_data['initiatives'].keys():
                if init_key != 'MULTIPLE':
                    unique_initiatives.add(init_key)
        manager_data['total_initiatives'] = len(unique_initiatives)

    # Convert to list and sort
    messages = []
    for slack_id, manager_data in sorted(manager_groups.items()):
        # Sort teams alphabetically
        teams_list = []
        for team_key, team_data in sorted(manager_data['teams'].items()):
            # Sort initiatives by key
            initiatives_list = []
            for init_key, init_data in sorted(team_data['initiatives'].items()):
                # Sort actions by priority
                init_data['actions'].sort(key=lambda x: x['priority'])
                initiatives_list.append(init_data)

            team_data['initiatives'] = initiatives_list
            teams_list.append(team_data)

        manager_data['teams'] = teams_list
        messages.append(manager_data)

    # Render template
    env = get_template_environment()
    template = env.get_template('notification_slack.j2')
    jira_base_url = get_jira_base_url()

    output = template.render(
        messages=messages,
        jira_base_url=jira_base_url,
        context='prioritisation'
    )

    # Save to timestamped file
    output_file = generate_output_path('prioritisation_validation', 'txt')

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(output)

    # Print to console
    click.echo("\n" + "=" * 80)
    click.echo(output)
    click.echo("=" * 80)
    click.echo(f"\n✅ Slack messages saved to: {output_file}")
    click.echo(f"Total managers: {len(messages)}, Total action items: {sum(m['total_actions'] for m in messages)}")


@click.command()
@click.option(
    '--config',
    type=click.Path(exists=True),
    help='Custom priority config path (default: config/priorities.yaml)'
)
@click.option(
    '--markdown',
    type=str,
    default=None,
    is_flag=False,
    flag_value='',  # Empty string when used as flag without value
    metavar='FILENAME',
    help='Export Initiative Health Dashboard as markdown file. '
         'Optionally specify filename, otherwise saves to output/prioritisation_validation/ with progressive numbering.'
)
@click.option(
    '--slack',
    is_flag=True,
    help='Generate Slack bulk messages for manager notifications'
)
@click.option(
    '--verbose',
    is_flag=True,
    help='Include verbose output with additional details'
)
@click.argument(
    'data_file',
    type=click.Path(exists=True),
    required=False
)
def main(config: Optional[str], markdown: Optional[str], slack: bool, verbose: bool, data_file: Optional[str]):
    """Validate initiative priorities and team commitments.

    Detects priority conflicts (teams committed to lower-priority initiatives
    while skipping higher-priority ones) and missing commitments (teams with
    no green/yellow epics despite being in teams_involved).

    Examples:

        # Validate using latest extraction
        python validate_prioritisation.py

        # Export markdown report
        python validate_prioritisation.py --markdown dashboard.md

        # Generate Slack messages
        python validate_prioritisation.py --slack

        # Use custom priority config
        python validate_prioritisation.py --config custom_priorities.yaml

        # Validate specific snapshot
        python validate_prioritisation.py data/snapshots/snapshot_*.json
    """
    # Setup logging level based on verbose flag
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Find data file
        if data_file:
            data_path = Path(data_file)
        else:
            data_path = find_most_recent_data_file(pattern='jira_extract_*.json')
            if not data_path:
                raise click.ClickException(
                    "No data file found. Run extract.py or provide path to data file."
                )

        logger.info(f"Using data file: {data_path}")

        # Parse config path
        config_path = Path(config) if config else None

        # Run validation
        result = validate_prioritisation(data_path, config_path)

        # Print report using template
        print_prioritisation_report(result, data_path, verbose)

        # Generate markdown report if requested
        if markdown is not None:
            # Use generate_output_path for default (empty string), or custom filename if provided
            markdown_filename = markdown if markdown else None
            markdown_file = generate_output_path('prioritisation_validation', 'md', markdown_filename)

            # Generate markdown content
            markdown_content = generate_markdown_report(result, data_path)

            # Write to file
            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            click.echo(f"\n✅ Markdown report exported to: {markdown_file}")

        # Generate Slack messages if requested
        if slack:
            team_managers = _load_team_managers()
            _, reverse_team_mappings, _ = _load_team_mappings()

            generate_prioritisation_slack_messages(
                result,
                team_managers,
                reverse_team_mappings
            )

        # Exit code based on findings
        if result.has_issues:
            sys.exit(1)
        else:
            sys.exit(0)

    except ValueError as e:
        click.echo(click.style(f"Configuration Error: {e}", fg='red'), err=True)
        sys.exit(2)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'), err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(2)


if __name__ == '__main__':
    main()
