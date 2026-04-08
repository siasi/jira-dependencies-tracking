#!/usr/bin/env python3
"""
Tech Leadership Initiative Priority Validation

Validates team commitments to Tech Leadership initiatives and ensures
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
class TechLeadershipResult:
    """Container for Tech Leadership validation results."""
    priority_conflicts: List[Dict[str, Any]]      # Teams committed to lower priority
    missing_commitments: List[Dict[str, Any]]     # Teams with no commitments
    initiative_health: List[Dict[str, Any]]       # Initiative-centric view
    data_quality_issues: List[Dict[str, Any]]     # Missing teams_involved
    unlisted_initiatives: List[Dict[str, Any]]    # Tech Leadership but not in config
    metadata: Dict[str, Any]                      # Summary stats

    @property
    def has_issues(self) -> bool:
        """Check if validation found any issues."""
        return bool(self.priority_conflicts or self.missing_commitments)


def _load_tech_leadership_priorities(
    config_path: Optional[Path] = None,
    quarter: Optional[str] = None
) -> Dict[str, Any]:
    """Load and validate Tech Leadership priorities config.

    Args:
        config_path: Optional custom config path
        quarter: Required quarter to validate against config

    Returns:
        Dict with 'quarter' and 'priorities' (ordered list)

    Raises:
        ValueError: If config missing, invalid, or quarter mismatch
    """
    if config_path is None:
        config_path = Path(__file__).parent / 'config' / 'tech_leadership_priorities.yaml'

    if not config_path.exists():
        raise ValueError(
            f"Priority config not found: {config_path}\n"
            f"Create config/tech_leadership_priorities.yaml from the .example file."
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

    # Validate quarter match (warning only)
    config_quarter = config.get('quarter')
    if quarter and config_quarter and config_quarter != quarter:
        logger.warning(
            f"Priority config quarter ({config_quarter}) doesn't match "
            f"requested quarter ({quarter}). Proceeding with config priorities."
        )

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


def _is_tech_leadership_initiative(initiative: Dict) -> bool:
    """Check if initiative is owned by Tech Leadership.

    Args:
        initiative: Initiative dict with 'owner_team' field

    Returns:
        True if owner_team is "Tech Leadership", False otherwise
    """
    owner_team = initiative.get('owner_team', '')
    return owner_team == 'Tech Leadership'


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

            # Load validation-specific exclusions with fallback
            excluded_teams = data.get('teams_excluded_from_validation')
            if excluded_teams is None:
                excluded_teams = data.get('teams_excluded_from_analysis', [])

            return team_mappings, reverse_team_mappings, excluded_teams
    except Exception as e:
        logger.warning(f"Could not load team mappings: {e}")
        return {}, {}, []


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


def _is_team_committed(rag_statuses: List[str]) -> bool:
    """Check if team is committed based on epic RAG statuses.

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


def _build_commitment_matrix(
    initiatives: List[Dict],
    priorities: List[str],
    team_mappings: Dict[str, str],
    reverse_team_mappings: Dict[str, str]
) -> Dict[str, Dict[str, Any]]:
    """Build commitment matrix for Tech Leadership initiatives.

    Args:
        initiatives: List of all initiative dicts
        priorities: Ordered list of initiative keys (highest priority first)
        team_mappings: Map display name → project key
        reverse_team_mappings: Map project key → display name

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

        # Get expected teams
        teams_involved = _normalize_teams_involved(initiative.get('teams_involved'))

        for team_display in teams_involved:
            team_key = team_mappings.get(team_display, team_display)

            # Set team display name
            if matrix[team_key]['team_display'] is None:
                matrix[team_key]['team_display'] = team_display

            # Get RAG statuses
            rag_statuses = _get_team_epics_rag_statuses(initiative, team_key)
            is_committed = _is_team_committed(rag_statuses)

            # Add to expected initiatives
            matrix[team_key]['expected_initiatives'].append({
                'key': init_key,
                'title': init_title,
                'priority_index': priority_idx,
                'is_committed': is_committed,
                'rag_statuses': rag_statuses
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

    Args:
        commitment_matrix: Output from _build_commitment_matrix

    Returns:
        List of missing commitment dicts
    """
    missing = []

    for team_key, team_data in commitment_matrix.items():
        # Has expected initiatives but no commitments
        if team_data['expected_initiatives'] and not team_data['committed_initiatives']:
            missing.append({
                'team_key': team_key,
                'team_display': team_data['team_display'],
                'expected_in': [
                    {'key': init['key'], 'title': init['title']}
                    for init in team_data['expected_initiatives']
                ]
            })

    return missing


def _build_initiative_health(
    initiatives: List[Dict],
    priorities: List[str],
    team_mappings: Dict[str, str]
) -> List[Dict[str, Any]]:
    """Build initiative health dashboard (initiative-centric view).

    Args:
        initiatives: List of all initiative dicts
        priorities: Ordered list of initiative keys
        team_mappings: Map display name → project key

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

        # Get expected teams
        teams_involved = _normalize_teams_involved(initiative.get('teams_involved'))

        # Get committed teams
        committed = []
        missing = []

        for team_display in teams_involved:
            team_key = team_mappings.get(team_display, team_display)
            rag_statuses = _get_team_epics_rag_statuses(initiative, team_key)

            if _is_team_committed(rag_statuses):
                committed.append({
                    'team': team_display,
                    'rag_statuses': rag_statuses
                })
            else:
                missing.append(team_display)

        health.append({
            'key': init_key,
            'title': init_title,
            'priority': priority,
            'expected_teams': teams_involved,
            'committed_teams': committed,
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


def validate_tech_leadership(
    data_file: Path,
    quarter: str,
    config_path: Optional[Path] = None
) -> TechLeadershipResult:
    """Validate Tech Leadership initiative priorities and team commitments.

    Args:
        data_file: Path to JSON extraction or snapshot file
        quarter: Quarter to validate (e.g., "26 Q2")
        config_path: Optional custom priority config path

    Returns:
        TechLeadershipResult with validation findings

    Raises:
        ValueError: If config invalid or missing
    """
    # Load priority config
    priority_config = _load_tech_leadership_priorities(config_path, quarter)
    priorities = priority_config['priorities']

    logger.info(f"Loaded {len(priorities)} Tech Leadership priorities for quarter {quarter}")

    # Load data
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    initiatives = data.get('initiatives', [])
    logger.info(f"Loaded {len(initiatives)} total initiatives from {data_file}")

    # Load team mappings
    team_mappings, reverse_team_mappings, excluded_teams = _load_team_mappings()

    # Filter to Tech Leadership initiatives
    tech_leadership_initiatives = [
        init for init in initiatives
        if _is_tech_leadership_initiative(init)
    ]
    logger.info(f"Found {len(tech_leadership_initiatives)} Tech Leadership initiatives")

    # Filter to active (not Done/Cancelled)
    active_initiatives = [
        init for init in tech_leadership_initiatives
        if _is_active_initiative(init)
    ]
    logger.info(f"Found {len(active_initiatives)} active Tech Leadership initiatives")

    # Filter out Discovery initiatives
    non_discovery = [
        init for init in active_initiatives
        if not _is_discovery_initiative(init)
    ]
    logger.info(f"Found {len(non_discovery)} non-Discovery Tech Leadership initiatives")

    # Check data quality
    quality_issues = _check_data_quality(non_discovery, priorities)

    # Warn about initiatives in config but not found
    found_keys = {init['key'] for init in non_discovery}
    missing_from_data = [key for key in priorities if key not in found_keys]
    if missing_from_data:
        logger.warning(
            f"Priority config includes {len(missing_from_data)} initiatives not found in quarter data: "
            f"{', '.join(missing_from_data)}"
        )

    # Build commitment matrix
    commitment_matrix = _build_commitment_matrix(
        non_discovery,
        priorities,
        team_mappings,
        reverse_team_mappings
    )
    logger.info(f"Built commitment matrix for {len(commitment_matrix)} teams")

    # Detect conflicts and missing commitments
    priority_conflicts = _detect_priority_conflicts(commitment_matrix, priorities)
    missing_commitments = _detect_missing_commitments(commitment_matrix)
    logger.info(f"Found {len(priority_conflicts)} priority conflicts and {len(missing_commitments)} missing commitments")

    # Build initiative health
    initiative_health = _build_initiative_health(
        non_discovery,
        priorities,
        team_mappings
    )

    # Build result
    result = TechLeadershipResult(
        priority_conflicts=priority_conflicts,
        missing_commitments=missing_commitments,
        initiative_health=initiative_health,
        data_quality_issues=quality_issues['missing_teams_involved'],
        unlisted_initiatives=quality_issues['unlisted_initiatives'],
        metadata={
            'quarter': quarter,
            'total_tech_leadership': len(tech_leadership_initiatives),
            'active_initiatives': len(active_initiatives),
            'validated_initiatives': len(non_discovery),
            'priorities_count': len(priorities),
            'teams_analyzed': len(commitment_matrix),
            'missing_from_data': missing_from_data
        }
    )

    return result


def print_tech_leadership_report(
    result: TechLeadershipResult,
    data_file: Path,
    verbose: bool = False
) -> None:
    """Print Tech Leadership validation report to console.

    Args:
        result: TechLeadershipResult instance
        data_file: Path to data file (for reference)
        verbose: Include verbose output
    """
    env = get_template_environment()
    template = env.get_template('tech_leadership_console.j2')
    jira_base_url = get_jira_base_url()

    output = template.render(
        result=result,
        data_file=data_file,
        jira_base_url=jira_base_url,
        verbose=verbose
    )

    click.echo(output)


@click.command()
@click.option(
    '--quarter',
    required=True,
    help='Quarter to validate (e.g., "26 Q2")'
)
@click.option(
    '--config',
    type=click.Path(exists=True),
    help='Custom priority config path (default: config/tech_leadership_priorities.yaml)'
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
def main(quarter: str, config: Optional[str], verbose: bool, data_file: Optional[str]):
    """Validate Tech Leadership initiative priorities and team commitments.

    Detects priority conflicts (teams committed to lower-priority initiatives
    while skipping higher-priority ones) and missing commitments (teams with
    no green/yellow epics despite being in teams_involved).

    Examples:

        # Validate current quarter using latest extraction
        python validate_tech_leadership.py --quarter "26 Q2"

        # Use custom priority config
        python validate_tech_leadership.py --quarter "26 Q2" --config custom_priorities.yaml

        # Validate specific snapshot
        python validate_tech_leadership.py --quarter "26 Q2" data/snapshots/snapshot_*.json
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
        result = validate_tech_leadership(data_path, quarter, config_path)

        # Print report using template
        print_tech_leadership_report(result, data_path, verbose)

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
