#!/usr/bin/env python3
"""Validate initiative readiness for Proposed → Planned status transitions.

This script analyzes Jira initiatives to determine readiness for status transitions
based on epic RAG status, team dependencies, and assignee presence. It categorizes
initiatives into groups: Dependency Mapping in Progress, Low Confidence for Completion,
Ready - Awaiting Owner, Ready to Move to Planned, and Planned/In Progress for the Quarter.

Usage:
    # Validate latest extraction
    python validate_initiative_status.py

    # Validate specific JSON file
    python validate_initiative_status.py data/jira_extract_20260321.json

    # Validates only multi-team initiatives (teams >= 2)
    # Single-team initiatives are skipped automatically
"""

import argparse
import json
import sys
import yaml
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


class ValidationResult:
    """Results of initiative status validation."""

    def __init__(self):
        # Section 1: Dependency Mapping in Progress
        self.dependency_mapping: List[Dict[str, Any]] = []
        # Section 2: No/Low confidence for completion - require discussion
        self.low_confidence_completion: List[Dict[str, Any]] = []
        # Section 3: Ready to Move to Planned
        self.ready_to_plan: List[Dict[str, Any]] = []
        # Section 4: Planned/In Progress for the Quarter (healthy initiatives)
        self.planned_for_quarter: List[Dict[str, Any]] = []
        # Additional sections (verbose only)
        self.planned_regressions: List[Dict[str, Any]] = []
        self.ignored_statuses: List[Dict[str, Any]] = []
        # Metadata
        self.total_checked = 0
        self.total_filtered = 0

    @property
    def has_issues(self) -> bool:
        """Whether any issues were found."""
        return (len(self.dependency_mapping) > 0 or
                len(self.low_confidence_completion) > 0 or
                len(self.planned_regressions) > 0)


def _is_discovery_initiative(initiative: dict) -> bool:
    """Check if an initiative is a discovery initiative.

    Args:
        initiative: Initiative dictionary from JSON

    Returns:
        True if summary starts with "[Discovery]", False otherwise
    """
    summary = initiative.get('summary', '')
    return summary.startswith('[Discovery]')


def _check_data_quality(initiative: dict) -> Optional[List[Dict[str, Any]]]:
    """Check for data quality blockers.

    Args:
        initiative: Initiative dictionary from JSON

    Returns:
        List of data quality issues, or None if no issues
    """
    issues = []
    is_discovery = _is_discovery_initiative(initiative)

    # Check for missing assignee
    assignee = initiative.get('assignee')
    if not assignee:
        issues.append({'type': 'missing_assignee'})

    # Check for missing strategic objective
    strategic_objective = initiative.get('strategic_objective')
    if not strategic_objective or (isinstance(strategic_objective, str) and not strategic_objective.strip()):
        issues.append({'type': 'missing_strategic_objective'})

    # Skip dependency and RAG checks for discovery initiatives
    if is_discovery:
        return issues if issues else None

    # Check epic count vs teams count (including case where there are no epics)
    teams_involved = _normalize_teams_involved(initiative.get('teams_involved'))
    teams_with_epics = {
        tc['team_project_key']
        for tc in initiative.get('contributing_teams', [])
        if tc.get('epics')
    }

    if len(teams_involved) != len(teams_with_epics):
        # Check if the only missing team is the owner team
        # (Owner team doesn't need an epic since they're leading the initiative)
        owner_team = initiative.get('owner_team')
        team_mappings = _load_team_mappings()

        # Find which teams are missing epics
        teams_with_epics_set = set(teams_with_epics)
        missing_teams = []
        for display_name in teams_involved:
            project_key = team_mappings.get(display_name, display_name)
            if project_key.upper() not in {k.upper() for k in teams_with_epics_set}:
                missing_teams.append(display_name)

        # Only report mismatch if there are missing teams other than the owner
        # or if the only missing team is NOT the owner
        is_only_owner_missing = (
            owner_team and
            len(missing_teams) == 1 and
            missing_teams[0] == owner_team
        )

        if not is_only_owner_missing:
            issues.append({
                'type': 'epic_count_mismatch',
                'teams_involved': teams_involved,
                'teams_with_epics': list(teams_with_epics)
            })

    # Check for missing RAG status (skip owner team and exempt teams)
    owner_team = initiative.get('owner_team')
    team_mappings = _load_team_mappings()
    exempt_teams = _load_teams_exempt_from_rag()

    missing_rag_by_team = []
    for tc in initiative.get('contributing_teams', []):
        team_key = tc.get('team_project_key', '')
        team_name = tc.get('team_project_name', team_key)

        # Skip epics from owner team (they don't need to set RAG status)
        is_owner_team = False
        if owner_team:
            # Check if this team matches the owner team
            owner_project_key = team_mappings.get(owner_team, owner_team)
            if team_key.upper() == owner_project_key.upper():
                is_owner_team = True

        # Skip epics from teams exempt from RAG checking
        is_exempt_team = team_key in exempt_teams

        if not is_owner_team and not is_exempt_team:
            team_missing_epics = []
            for epic in tc.get('epics', []):
                if epic.get('rag_status') is None:
                    team_missing_epics.append({
                        'key': epic['key'],
                        'summary': epic['summary'],
                        'url': epic.get('url', '')
                    })

            if team_missing_epics:
                missing_rag_by_team.append({
                    'team_name': team_name,
                    'team_key': team_key,
                    'epics': team_missing_epics
                })

    if missing_rag_by_team:
        issues.append({
            'type': 'missing_rag_status',
            'teams': missing_rag_by_team
        })

    return issues if issues else None


def _has_red_epics(initiative: dict) -> Optional[List[Dict[str, Any]]]:
    """Check if initiative has RED epics (skip owner team and exempt teams).

    Args:
        initiative: Initiative dictionary from JSON

    Returns:
        List of RED epics, or None if no RED epics
    """
    owner_team = initiative.get('owner_team')
    team_mappings = _load_team_mappings()
    exempt_teams = _load_teams_exempt_from_rag()

    red_epics = []

    for tc in initiative.get('contributing_teams', []):
        team_key = tc.get('team_project_key', '')

        # Skip epics from owner team
        is_owner_team = False
        if owner_team:
            owner_project_key = team_mappings.get(owner_team, owner_team)
            if team_key.upper() == owner_project_key.upper():
                is_owner_team = True

        # Skip epics from teams exempt from RAG checking
        is_exempt_team = team_key in exempt_teams

        if not is_owner_team and not is_exempt_team:
            for epic in tc.get('epics', []):
                rag = epic.get('rag_status')
                if rag == '🔴':
                    red_epics.append({
                        'key': epic['key'],
                        'summary': epic['summary'],
                        'rag_status': rag
                    })

    return red_epics if red_epics else None


def _has_yellow_epics(initiative: dict) -> Optional[List[Dict[str, Any]]]:
    """Check if initiative has YELLOW epics (skip owner team and exempt teams).

    Args:
        initiative: Initiative dictionary from JSON

    Returns:
        List of YELLOW epics, or None if no YELLOW epics
    """
    owner_team = initiative.get('owner_team')
    team_mappings = _load_team_mappings()
    exempt_teams = _load_teams_exempt_from_rag()

    yellow_epics = []

    for tc in initiative.get('contributing_teams', []):
        team_key = tc.get('team_project_key', '')

        # Skip epics from owner team
        is_owner_team = False
        if owner_team:
            owner_project_key = team_mappings.get(owner_team, owner_team)
            if team_key.upper() == owner_project_key.upper():
                is_owner_team = True

        # Skip epics from teams exempt from RAG checking
        is_exempt_team = team_key in exempt_teams

        if not is_owner_team and not is_exempt_team:
            for epic in tc.get('epics', []):
                rag = epic.get('rag_status')
                # Check for yellow/amber status (both emoji types used in data)
                # Also treat None/missing RAG as yellow (needs attention)
                if rag in ['⚠️', '🟡', None]:
                    yellow_epics.append({
                        'key': epic['key'],
                        'summary': epic['summary'],
                        'rag_status': rag  # Include actual status for display
                    })

    return yellow_epics if yellow_epics else None


def _is_ready_to_plan(initiative: dict) -> bool:
    """Check if initiative meets all criteria for Planned status.

    Args:
        initiative: Initiative dictionary from JSON

    Returns:
        True if ready for Planned status, False otherwise
    """
    # Must have assignee
    if not initiative.get('assignee'):
        return False

    # Discovery initiatives skip epic and RAG checks
    is_discovery = _is_discovery_initiative(initiative)
    if is_discovery:
        # Discovery initiatives only need assignee
        return True

    # Load owner team info upfront (used for multiple checks)
    owner_team = initiative.get('owner_team')
    team_mappings = _load_team_mappings()

    # Must have at least one epic
    total_epics = sum(len(tc.get('epics', [])) for tc in initiative.get('contributing_teams', []))
    if total_epics == 0:
        return False

    # Epic count must match teams count (excluding owner team)
    teams_involved = _normalize_teams_involved(initiative.get('teams_involved'))
    teams_with_epics = {
        tc['team_project_key']
        for tc in initiative.get('contributing_teams', [])
        if tc.get('epics')
    }

    if len(teams_involved) != len(teams_with_epics):
        # Check if the only missing team is the owner team

        # Find which teams are missing epics
        teams_with_epics_set = set(teams_with_epics)
        missing_teams = []
        for display_name in teams_involved:
            project_key = team_mappings.get(display_name, display_name)
            if project_key.upper() not in {k.upper() for k in teams_with_epics_set}:
                missing_teams.append(display_name)

        # Only fail if there are missing teams other than the owner
        is_only_owner_missing = (
            owner_team and
            len(missing_teams) == 1 and
            missing_teams[0] == owner_team
        )

        if not is_only_owner_missing:
            return False

    # All epics must have GREEN RAG status (skip owner team and exempt teams)
    exempt_teams = _load_teams_exempt_from_rag()

    for tc in initiative.get('contributing_teams', []):
        team_key = tc.get('team_project_key', '')

        # Skip epics from owner team (they don't need to report RAG status)
        is_owner_team = False
        if owner_team:
            owner_project_key = team_mappings.get(owner_team, owner_team)
            if team_key.upper() == owner_project_key.upper():
                is_owner_team = True

        # Skip epics from teams exempt from RAG checking
        is_exempt_team = team_key in exempt_teams

        if not is_owner_team and not is_exempt_team:
            for epic in tc.get('epics', []):
                rag_status = epic.get('rag_status')
                # Only RED epics block readiness (yellow = low confidence but acceptable)
                if rag_status == '🔴':
                    return False

    return True


def _load_team_mappings() -> Dict[str, str]:
    """Load team name mappings from team_mappings.yaml.

    Returns:
        Dict mapping display names to project keys, or empty dict if file not found
    """
    mappings_file = Path(__file__).parent / 'team_mappings.yaml'
    if not mappings_file.exists():
        return {}

    try:
        with open(mappings_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data.get('team_mappings', {})
    except Exception:
        return {}


def _load_team_managers() -> Dict[str, Dict[str, Optional[str]]]:
    """Load team managers with Notion handles and Slack IDs.

    Returns:
        Dict mapping project keys to manager info:
        {
            "CBPPE": {
                "notion_handle": "@Ariel Reanho ",
                "slack_id": "U01F3QUHP0B"
            }
        }

        Handles legacy string format for backward compatibility.
    """
    mappings_file = Path(__file__).parent / 'team_mappings.yaml'
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


def _validate_dust_config(team_managers: Dict[str, Dict]) -> None:
    """Validate all teams have Slack IDs for Dust messaging.

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


def _load_teams_exempt_from_rag() -> List[str]:
    """Load list of teams exempt from RAG status checking.

    Returns:
        List of project keys for teams that don't require RAG status, or empty list if not found
    """
    mappings_file = Path(__file__).parent / 'team_mappings.yaml'
    if not mappings_file.exists():
        return []

    try:
        with open(mappings_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            exempt_teams = data.get('teams_exempt_from_rag', [])
            # Return as set for O(1) lookups, but as list for type consistency
            return exempt_teams if exempt_teams else []
    except Exception:
        return []


def _load_teams_excluded_from_analysis() -> List[str]:
    """Load list of teams to exclude from analysis entirely.

    Returns:
        List of team names for teams whose initiatives should be filtered out, or empty list if not found
    """
    mappings_file = Path(__file__).parent / 'team_mappings.yaml'
    if not mappings_file.exists():
        return []

    try:
        with open(mappings_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            excluded_teams = data.get('teams_excluded_from_analysis', [])
            return excluded_teams if excluded_teams else []
    except Exception:
        return []


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


def _count_teams_involved(teams_involved: Any) -> int:
    """Count number of teams from teams_involved field.

    Args:
        teams_involved: Value from teams_involved field (can be None, list, or string)

    Returns:
        Number of teams
    """
    return len(_normalize_teams_involved(teams_involved))


def extract_manager_actions(result: ValidationResult) -> List[Dict[str, Any]]:
    """Extract action items from ValidationResult into flat, annotated list.

    This function flattens the hierarchical ValidationResult into a list of
    individual action items, each annotated with all metadata needed for
    any output format (console, markdown, Dust, etc.).

    Args:
        result: Validation result containing categorized initiatives

    Returns:
        List of action item dictionaries with structure:
        {
            'initiative_key': 'INIT-1234',
            'initiative_title': 'Project Alpha',
            'initiative_status': 'Planned',
            'initiative_url': 'https://truelayer.atlassian.net/browse/INIT-1234',
            'section': 'planned_regressions',  # which report section
            'action_type': 'missing_dependencies',
            'priority': 1,  # lower = higher priority
            'responsible_team': 'RSK',
            'responsible_team_key': 'RSK',
            'responsible_manager_name': 'Kevin Plattret',
            'responsible_manager_notion': '@Kevin Plattret',
            'responsible_manager_slack_id': 'U05MNO345',
            'description': 'Create epic',
            'epic_key': None,  # or epic key if action is about specific epic
            'epic_title': None,
            'epic_rag': None
        }

    Action types included:
    - 'missing_dependencies': Team needs to create epic
    - 'missing_rag': Team needs to set RAG status on epic
    - 'missing_assignee': Initiative needs assignee
    - 'ready_to_planned': Initiative ready to move to PLANNED status

    Priority ordering (1=highest):
    1. missing_assignee (blocks planning)
    2. missing_dependencies (blocks execution)
    3. missing_rag (blocks visibility)
    4. ready_to_planned (informational)
    """
    actions = []
    team_mappings = _load_team_mappings()
    team_managers = _load_team_managers()

    # Priority mapping
    PRIORITY = {
        'missing_assignee': 1,
        'missing_dependencies': 2,
        'missing_rag': 3,
        'ready_to_planned': 4
    }

    # Helper to build base initiative context
    def _base_context(initiative: Dict, section: str) -> Dict:
        return {
            'initiative_key': initiative['key'],
            'initiative_title': initiative['summary'],
            'initiative_status': initiative.get('status', 'Unknown'),
            'initiative_url': f"https://truelayer.atlassian.net/browse/{initiative['key']}",
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

    # Process each section of ValidationResult

    # Section 1: dependency_mapping (Proposed initiatives with issues)
    for initiative in result.dependency_mapping:
        base = _base_context(initiative, 'dependency_mapping')
        owner_team = initiative.get('owner_team')

        for issue in initiative.get('issues', []):
            if issue['type'] == 'missing_assignee':
                # Owner team responsible for assignee
                if owner_team:
                    owner_key = team_mappings.get(owner_team, owner_team)
                    action = {
                        **base,
                        'action_type': 'missing_assignee',
                        'priority': PRIORITY['missing_assignee'],
                        'description': 'Set assignee',
                        'epic_key': None,
                        'epic_title': None,
                        'epic_rag': None
                    }
                    _add_manager_info(action, owner_key, owner_team)
                    actions.append(action)

            elif issue['type'] == 'epic_count_mismatch':
                # Missing dependencies - teams need to create epics
                teams_involved = issue.get('teams_involved', [])
                teams_with_epics = set(issue.get('teams_with_epics', []))

                for team_display in teams_involved:
                    # Skip owner team
                    if owner_team and team_display == owner_team:
                        continue

                    team_key = team_mappings.get(team_display, team_display)
                    if team_key not in teams_with_epics:
                        action = {
                            **base,
                            'action_type': 'missing_dependencies',
                            'priority': PRIORITY['missing_dependencies'],
                            'description': 'Create epic',
                            'epic_key': None,
                            'epic_title': None,
                            'epic_rag': None
                        }
                        _add_manager_info(action, team_key, team_display)
                        actions.append(action)

            elif issue['type'] == 'missing_rag':
                # Missing RAG status - team needs to set it
                for epic_info in issue.get('epics', []):
                    epic_key = epic_info.get('key', '')
                    team_key = epic_key.split('-')[0] if '-' in epic_key else None

                    if team_key:
                        # Find team display name
                        team_display = next(
                            (k for k, v in team_mappings.items() if v == team_key),
                            team_key
                        )

                        action = {
                            **base,
                            'action_type': 'missing_rag',
                            'priority': PRIORITY['missing_rag'],
                            'description': 'Set RAG status',
                            'epic_key': epic_info.get('key'),
                            'epic_title': epic_info.get('summary'),
                            'epic_rag': None
                        }
                        _add_manager_info(action, team_key, team_display)
                        actions.append(action)

    # Section 2: ready_to_plan (Proposed initiatives ready to move)
    for initiative in result.ready_to_plan:
        base = _base_context(initiative, 'ready_to_plan')
        owner_team = initiative.get('owner_team')

        if owner_team:
            owner_key = team_mappings.get(owner_team, owner_team)
            action = {
                **base,
                'action_type': 'ready_to_planned',
                'priority': PRIORITY['ready_to_planned'],
                'description': 'All criteria met - ready to move to PLANNED',
                'epic_key': None,
                'epic_title': None,
                'epic_rag': None
            }
            _add_manager_info(action, owner_key, owner_team)
            actions.append(action)

    # Section 3: planned_regressions (Planned/In Progress with issues)
    for initiative in result.planned_regressions:
        base = _base_context(initiative, 'planned_regressions')
        owner_team = initiative.get('owner_team')

        for issue in initiative.get('issues', []):
            if issue['type'] == 'missing_assignee':
                if owner_team:
                    owner_key = team_mappings.get(owner_team, owner_team)
                    action = {
                        **base,
                        'action_type': 'missing_assignee',
                        'priority': PRIORITY['missing_assignee'],
                        'description': 'Set assignee',
                        'epic_key': None,
                        'epic_title': None,
                        'epic_rag': None
                    }
                    _add_manager_info(action, owner_key, owner_team)
                    actions.append(action)

            elif issue['type'] == 'epic_count_mismatch':
                teams_involved = issue.get('teams_involved', [])
                teams_with_epics = set(issue.get('teams_with_epics', []))

                for team_display in teams_involved:
                    if owner_team and team_display == owner_team:
                        continue

                    team_key = team_mappings.get(team_display, team_display)
                    if team_key not in teams_with_epics:
                        action = {
                            **base,
                            'action_type': 'missing_dependencies',
                            'priority': PRIORITY['missing_dependencies'],
                            'description': 'Create epic',
                            'epic_key': None,
                            'epic_title': None,
                            'epic_rag': None
                        }
                        _add_manager_info(action, team_key, team_display)
                        actions.append(action)

            elif issue['type'] == 'missing_rag':
                for epic_info in issue.get('epics', []):
                    epic_key = epic_info.get('key', '')
                    team_key = epic_key.split('-')[0] if '-' in epic_key else None

                    if team_key:
                        team_display = next(
                            (k for k, v in team_mappings.items() if v == team_key),
                            team_key
                        )

                        action = {
                            **base,
                            'action_type': 'missing_rag',
                            'priority': PRIORITY['missing_rag'],
                            'description': 'Set RAG status',
                            'epic_key': epic_info.get('key'),
                            'epic_title': epic_info.get('summary'),
                            'epic_rag': None
                        }
                        _add_manager_info(action, team_key, team_display)
                        actions.append(action)

    return actions


def generate_dust_messages(result: ValidationResult, output_dir: Path) -> None:
    """Generate Dust-compatible bulk messages for engineering managers.

    Extracts action items from validation result, groups by manager,
    and renders using Jinja2 template. Outputs to console and file.

    Args:
        result: Validation result containing initiatives and issues
        output_dir: Directory to save output file (typically extracts/)

    Raises:
        ValueError: If team_managers config is missing Slack IDs
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from collections import defaultdict
    from datetime import datetime

    # Validate configuration
    team_managers = _load_team_managers()
    _validate_dust_config(team_managers)

    # Extract actions
    actions = extract_manager_actions(result)

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
            # Skip actions for managers without Slack ID
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
            'priority': action['priority']
        })

    # Convert to template-friendly structure
    messages = []
    for slack_id, manager_data in manager_groups.items():
        teams = []
        total_actions = 0
        total_initiatives = 0

        for team_key, team_data in manager_data['teams'].items():
            initiatives = []

            for initiative_key, initiative_data in team_data['initiatives'].items():
                # Sort actions by priority within initiative
                sorted_actions = sorted(
                    initiative_data['actions'],
                    key=lambda a: a['priority']
                )
                total_actions += len(sorted_actions)
                total_initiatives += 1

                initiatives.append({
                    'key': initiative_data['key'],
                    'title': initiative_data['title'],
                    'url': initiative_data['url'],
                    'actions': sorted_actions
                })

            # Sort initiatives by key
            initiatives.sort(key=lambda i: i['key'])

            teams.append({
                'team_name': team_data['team_name'],
                'team_key': team_data['team_key'],
                'initiatives': initiatives
            })

        # Sort teams by team name
        teams.sort(key=lambda t: t['team_name'])

        messages.append({
            'manager_name': manager_data['manager_name'],
            'slack_id': slack_id,
            'total_actions': total_actions,
            'total_initiatives': total_initiatives,
            'teams': teams
        })

    # Sort messages by manager name for consistent output
    messages.sort(key=lambda m: m['manager_name'])

    # Setup Jinja2 environment
    template_dir = Path(__file__).parent / 'templates'
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(['html', 'xml']),
        trim_blocks=True,
        lstrip_blocks=True
    )

    # Render template
    template = env.get_template('dust.j2')
    output = template.render(messages=messages)

    # Print to console
    print("\n" + "="*60)
    print("DUST BULK MESSAGES")
    print("="*60)
    print("\nCopy the text below and paste into Dust chatbot:\n")
    print(output)
    print("="*60)

    # Save to file
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    output_file = output_dir / f'dust_messages_{timestamp}.txt'

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"\nDust messages saved to: {output_file}")
    print(f"Total managers: {len(messages)}")
    print(f"Total action items: {sum(m['total_actions'] for m in messages)}")


def validate_initiative_status(json_file: Path) -> ValidationResult:
    """Validate initiative readiness for Proposed → Planned transition.

    Only validates multi-team initiatives (teams_involved >= 2).
    Single-team initiatives are tracked in ignored_statuses.

    Args:
        json_file: Path to JSON file from jira_extract.py or snapshot

    Returns:
        ValidationResult with categorized findings
    """
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    result = ValidationResult()
    all_initiatives = data.get('initiatives', [])

    # Load excluded teams
    excluded_teams = _load_teams_excluded_from_analysis()

    # Filter to multi-team initiatives only (teams >= 2) and exclude certain teams
    initiatives = []
    for init in all_initiatives:
        team_count = _count_teams_involved(init.get('teams_involved'))
        owner_team = init.get('owner_team')

        # Check if owner team is excluded
        if owner_team and owner_team in excluded_teams:
            # Track excluded team initiatives in ignored_statuses
            result.ignored_statuses.append({
                'key': init['key'],
                'summary': init['summary'],
                'status': f"{init.get('status', 'Unknown')} (team excluded)",
                'url': init.get('url', '')
            })
        elif team_count >= 2:
            initiatives.append(init)
        else:
            # Track single-team initiatives as ignored
            result.ignored_statuses.append({
                'key': init['key'],
                'summary': init['summary'],
                'status': f"{init.get('status', 'Unknown')} (single-team)",
                'url': init.get('url', '')
            })

    result.total_checked = len(initiatives)
    result.total_filtered = len(all_initiatives) - len(initiatives)

    for initiative in initiatives:
        initiative_key = initiative['key']
        initiative_summary = initiative['summary']
        initiative_status = initiative.get('status', 'Unknown')
        initiative_assignee = initiative.get('assignee')
        initiative_url = initiative.get('url', '')

        # Classify Proposed initiatives into 5 sections
        if initiative_status == 'Proposed':
            # Check data quality first (Section 1)
            data_quality_issues = _check_data_quality(initiative)

            if data_quality_issues:
                # Section 1: Dependency Mapping in Progress
                result.dependency_mapping.append({
                    'key': initiative_key,
                    'summary': initiative_summary,
                    'status': initiative_status,
                    'assignee': initiative_assignee,
                    'url': initiative_url,
                    'owner_team': initiative.get('owner_team'),
                    'contributing_teams': initiative.get('contributing_teams', []),
                    'issues': data_quality_issues
                })
            else:
                # Data quality OK, check RAG status
                red_epics = _has_red_epics(initiative)
                yellow_epics = _has_yellow_epics(initiative)

                if red_epics or yellow_epics:
                    # Section 2: Low confidence for completion - require discussion
                    issues = []
                    if red_epics:
                        issues.append({
                            'type': 'red_epics',
                            'epics': red_epics
                        })
                    if yellow_epics:
                        issues.append({
                            'type': 'yellow_epics',
                            'epics': yellow_epics
                        })

                    result.low_confidence_completion.append({
                        'key': initiative_key,
                        'summary': initiative_summary,
                        'status': initiative_status,
                        'assignee': initiative_assignee,
                        'url': initiative_url,
                        'contributing_teams': initiative.get('contributing_teams', []),
                        'issues': issues
                    })
                else:
                    # All epics GREEN - ready to move to Planned
                    # Section 3: Ready to Move to Planned
                    result.ready_to_plan.append({
                        'key': initiative_key,
                        'summary': initiative_summary,
                        'status': initiative_status,
                        'assignee': initiative_assignee,
                        'url': initiative_url
                    })

        elif initiative_status in ['Planned', 'In Progress']:
            # Check for regressions (Planned/In Progress initiatives that no longer meet criteria)
            if not _is_ready_to_plan(initiative):
                # Collect all issues for detailed display
                all_issues = []

                # Check data quality
                quality_issues = _check_data_quality(initiative)
                if quality_issues:
                    all_issues.extend(quality_issues)

                # Check for RED epics
                red_epics = _has_red_epics(initiative)
                if red_epics:
                    all_issues.append({
                        'type': 'red_epics',
                        'epics': red_epics
                    })

                # Check for YELLOW epics
                yellow_epics = _has_yellow_epics(initiative)
                if yellow_epics:
                    all_issues.append({
                        'type': 'yellow_epics',
                        'epics': yellow_epics
                    })

                result.planned_regressions.append({
                    'key': initiative_key,
                    'summary': initiative_summary,
                    'status': initiative_status,
                    'assignee': initiative_assignee,
                    'url': initiative_url,
                    'owner_team': initiative.get('owner_team'),
                    'contributing_teams': initiative.get('contributing_teams', []),
                    'issues': all_issues if all_issues else []
                })
            else:
                # Section 5: Planned/In Progress for the Quarter (healthy initiatives)
                # Check if has red or yellow epics (no/low confidence)
                red_epics = _has_red_epics(initiative)
                yellow_epics = _has_yellow_epics(initiative)
                is_discovery = _is_discovery_initiative(initiative)

                result.planned_for_quarter.append({
                    'key': initiative_key,
                    'summary': initiative_summary,
                    'status': initiative_status,
                    'assignee': initiative_assignee,
                    'url': initiative_url,
                    'contributing_teams': initiative.get('contributing_teams', []),
                    'has_red_epics': red_epics is not None,
                    'red_epics': red_epics if red_epics else [],
                    'has_yellow_epics': yellow_epics is not None,
                    'yellow_epics': yellow_epics if yellow_epics else [],
                    'is_discovery': is_discovery,
                    'teams_involved': _normalize_teams_involved(initiative.get('teams_involved'))
                })

        else:
            # Track initiatives with other statuses (not analyzed)
            result.ignored_statuses.append({
                'key': initiative_key,
                'summary': initiative_summary,
                'status': initiative_status,
                'url': initiative_url
            })

    return result


def print_validation_report(result: ValidationResult, json_file: Path, verbose: bool = False):
    """Print formatted validation report using template.

    Args:
        result: ValidationResult with findings
        json_file: Path to validated JSON file
        verbose: Show detailed epic and team information
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    # Load config for template
    team_mappings = _load_team_mappings()
    team_managers = _load_team_managers()

    # Setup Jinja2 environment
    template_dir = Path(__file__).parent / 'templates'
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(['html', 'xml']),
        trim_blocks=True,
        lstrip_blocks=True
    )

    # Render template
    template = env.get_template('console.j2')
    output = template.render(
        result=result,
        json_file=json_file,
        verbose=verbose,
        team_mappings=team_mappings,
        team_managers=team_managers
    )

    # Print output
    print(output)


def generate_markdown_report(result: ValidationResult, json_file: Path, verbose: bool = False) -> str:
    """Generate markdown-formatted validation report using template.

    Args:
        result: ValidationResult with findings
        json_file: Path to validated JSON file
        verbose: Include verbose sections

    Returns:
        Markdown-formatted report string
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from datetime import datetime

    # Load config for template
    team_mappings = _load_team_mappings()
    team_managers = _load_team_managers()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Setup Jinja2 environment
    template_dir = Path(__file__).parent / 'templates'
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(['html', 'xml']),
        trim_blocks=True,
        lstrip_blocks=True
    )

    # Render template
    template = env.get_template('markdown.j2')
    output = template.render(
        result=result,
        json_file=json_file,
        verbose=verbose,
        team_mappings=team_mappings,
        team_managers=team_managers,
        timestamp=timestamp
    )

    return output


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


def main():
    """Main validation workflow."""
    parser = argparse.ArgumentParser(
        description='Validate initiative readiness for Proposed → Planned status transitions'
    )
    parser.add_argument(
        'json_file',
        nargs='?',
        type=Path,
        help='Path to JSON file from jira_extract.py or snapshot (optional, uses latest if omitted)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed epic and team information in validation output'
    )
    parser.add_argument(
        '--markdown',
        type=str,
        nargs='?',
        const='auto',
        metavar='FILENAME',
        help='Export report as markdown file (Notion-friendly format). '
             'Optionally specify filename, otherwise auto-generates with timestamp.'
    )
    parser.add_argument(
        '--dust',
        action='store_true',
        help='Generate Dust bulk messages for manager notifications'
    )

    args = parser.parse_args()

    # Determine which file to validate
    if args.json_file:
        json_file = args.json_file
        if not json_file.exists():
            print(f"Error: File not found: {json_file}", file=sys.stderr)
            sys.exit(0)
    else:
        try:
            json_file = find_latest_extract()
            print(f"Using latest extraction: {json_file}")
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(0)

    # Run validation
    try:
        result = validate_initiative_status(json_file)

        # Print console report
        print_validation_report(result, json_file, verbose=args.verbose)

        # Generate markdown export if requested
        if args.markdown:
            if args.markdown == 'auto':
                # Auto-generate filename with timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                markdown_file = Path(f"initiative_validation_report_{timestamp}.md")
            else:
                markdown_file = Path(args.markdown)

            # Generate markdown content
            markdown_content = generate_markdown_report(
                result, json_file, verbose=args.verbose
            )

            # Write to file
            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            print(f"\n✅ Markdown report exported to: {markdown_file}")

        # Generate Dust messages if requested
        if args.dust:
            output_dir = json_file.parent
            generate_dust_messages(result, output_dir)

        # Always exit successfully (validation issues are informational, not failures)
        sys.exit(0)

    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON file: {e}", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(0)


if __name__ == '__main__':
    main()
