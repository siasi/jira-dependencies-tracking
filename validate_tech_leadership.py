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

    # Placeholder result for Phase 1
    result = TechLeadershipResult(
        priority_conflicts=[],
        missing_commitments=[],
        initiative_health=[],
        data_quality_issues=[],
        unlisted_initiatives=[],
        metadata={
            'quarter': quarter,
            'total_tech_leadership': len(tech_leadership_initiatives),
            'active_initiatives': len(active_initiatives),
            'validated_initiatives': len(non_discovery),
            'priorities_count': len(priorities),
            'teams_analyzed': 0,
            'missing_from_data': []
        }
    )

    return result


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

        # Print basic summary (Phase 1)
        click.echo("\n" + "=" * 80)
        click.echo("Tech Leadership Priority Validation Report")
        click.echo("=" * 80)
        click.echo(f"Quarter: {result.metadata['quarter']}")
        click.echo(f"Tech Leadership Initiatives: {result.metadata['total_tech_leadership']}")
        click.echo(f"Active (non-Done/Cancelled): {result.metadata['active_initiatives']}")
        click.echo(f"Validated (non-Discovery): {result.metadata['validated_initiatives']}")
        click.echo(f"Priorities Configured: {result.metadata['priorities_count']}")
        click.echo("=" * 80)
        click.echo("\n✅ Phase 1: Basic filtering complete!")
        click.echo("   Next phases will add commitment analysis and reporting.\n")

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
