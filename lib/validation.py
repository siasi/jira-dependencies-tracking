"""Shared validation library for initiative data quality checks.

This module provides reusable validation logic for checking initiative data quality
across all validation scripts. It implements status-aware validation rules.
"""

import yaml
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional


class Priority(IntEnum):
    """Action item priority levels."""
    CRITICAL = 1  # Blocks everything (missing owner)
    HIGH = 2      # Blocks planning (missing assignee, strategic objective)
    MEDIUM = 3    # Data correction (invalid values)
    LOW = 4       # Missing dependencies (epics)
    INFO = 5      # Missing signals (RAG status)


@dataclass
class ValidationIssue:
    """Represents a single data quality issue."""
    type: str                           # 'missing_owner', 'missing_epic', etc.
    priority: Priority
    description: str
    initiative_key: str
    initiative_summary: str
    initiative_status: str
    owner_team: Optional[str]
    team_affected: Optional[str] = None  # For team-specific issues
    epic_key: Optional[str] = None       # For epic-specific issues
    current_value: Optional[str] = None  # For invalid value issues
    expected_value: Optional[str] = None


@dataclass
class ValidationConfig:
    """Configuration for validation rules."""
    check_assignee: bool = True
    check_strategic_objective: bool = True
    check_teams_involved: bool = True
    check_missing_epics: bool = True
    check_rag_status: bool = True
    owner_team_exempt: bool = True
    skip_discovery: bool = True
    valid_strategic_objectives: Optional[List[str]] = None
    team_mappings: Optional[Dict[str, str]] = None
    rag_exempt_teams: Optional[List[str]] = None


class InitiativeValidator:
    """Validates a single initiative for data quality issues."""

    def __init__(self, config: ValidationConfig):
        """Initialize validator with configuration.

        Args:
            config: Validation configuration
        """
        self.config = config

    def validate(self, initiative: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate initiative and return list of issues.

        Applies status-aware validation rules:
        - All statuses: owner, strategic objective
        - Proposed/Planned: assignee, epics, RAG
        - In Progress: assignee, epics (no RAG)

        Args:
            initiative: Initiative dictionary from JSON

        Returns:
            List of ValidationIssue objects
        """
        issues = []

        # Universal checks (all statuses)
        issues.extend(self._check_owner_team(initiative))
        issues.extend(self._check_strategic_objective(initiative))
        issues.extend(self._check_teams_involved(initiative))

        # Status-specific checks
        status = initiative.get('status', '')

        if status in ['Proposed', 'Planned', 'In Progress']:
            if self.config.check_assignee:
                issues.extend(self._check_assignee(initiative))
            if self.config.check_missing_epics:
                issues.extend(self._check_missing_epics(initiative))

        if status in ['Proposed', 'Planned']:
            # RAG validation only for Proposed/Planned
            if self.config.check_rag_status:
                issues.extend(self._check_rag_status(initiative))

        return issues

    def _check_owner_team(self, initiative: Dict) -> List[ValidationIssue]:
        """Check for missing owner_team.

        Args:
            initiative: Initiative dictionary

        Returns:
            List of ValidationIssue (0 or 1 item)
        """
        owner_team = initiative.get('owner_team')

        if not owner_team or (isinstance(owner_team, str) and not owner_team.strip()):
            return [ValidationIssue(
                type="missing_owner_team",
                priority=Priority.CRITICAL,
                description="Missing owner team - Assign owner team",
                initiative_key=initiative.get('key', ''),
                initiative_summary=initiative.get('summary', ''),
                initiative_status=initiative.get('status', ''),
                owner_team=None,
            )]

        return []

    def _check_assignee(self, initiative: Dict) -> List[ValidationIssue]:
        """Check for missing assignee with status-aware priority.

        Priority escalation:
        - Proposed: P3 (MEDIUM) - Nice to have, can assign later
        - Planned: P1 (CRITICAL) - Must have DRI for committed work
        - In Progress: P1 (CRITICAL) - Must have someone coordinating

        Args:
            initiative: Initiative dictionary

        Returns:
            List of ValidationIssue (0 or 1 item)
        """
        assignee = initiative.get('assignee')

        if not assignee or (isinstance(assignee, str) and not assignee.strip()):
            # Calculate status-aware priority
            status = initiative.get('status', '')
            if status == 'Proposed':
                priority = Priority.MEDIUM  # P3
            else:  # Planned or In Progress
                priority = Priority.CRITICAL  # P1

            return [ValidationIssue(
                type="missing_assignee",
                priority=priority,
                description="Assign initiative owner",
                initiative_key=initiative.get('key', ''),
                initiative_summary=initiative.get('summary', ''),
                initiative_status=initiative.get('status', ''),
                owner_team=initiative.get('owner_team'),
            )]

        return []

    def _check_strategic_objective(self, initiative: Dict) -> List[ValidationIssue]:
        """Check strategic objective: missing or invalid.

        Supports comma-separated multi-objective format.

        Args:
            initiative: Initiative dictionary

        Returns:
            List of ValidationIssue (0 or more items)
        """
        if not self.config.check_strategic_objective:
            return []

        issues = []
        strategic_objective = initiative.get('strategic_objective')

        # Check for missing (P1 - blocks planning)
        if not strategic_objective or (isinstance(strategic_objective, str) and not strategic_objective.strip()):
            return [ValidationIssue(
                type="missing_strategic_objective",
                priority=Priority.CRITICAL,
                description="Set strategic objective",
                initiative_key=initiative.get('key', ''),
                initiative_summary=initiative.get('summary', ''),
                initiative_status=initiative.get('status', ''),
                owner_team=initiative.get('owner_team'),
            )]

        # Check for invalid values (if valid list provided)
        if self.config.valid_strategic_objectives:
            # Split by comma to handle multiple objectives
            objectives = [obj.strip() for obj in strategic_objective.split(',')]
            invalid = [obj for obj in objectives if obj not in self.config.valid_strategic_objectives]

            if invalid:
                issues.append(ValidationIssue(
                    type="invalid_strategic_objective",
                    priority=Priority.MEDIUM,
                    description=f"Invalid strategic objective: {', '.join(invalid)} - Fix value",
                    initiative_key=initiative.get('key', ''),
                    initiative_summary=initiative.get('summary', ''),
                    initiative_status=initiative.get('status', ''),
                    owner_team=initiative.get('owner_team'),
                    current_value=strategic_objective,  # Full comma-separated string
                ))

        return issues

    def _check_teams_involved(self, initiative: Dict) -> List[ValidationIssue]:
        """Check for missing or empty teams_involved field.

        Args:
            initiative: Initiative dictionary

        Returns:
            List of ValidationIssue (0 or 1 item)
        """
        if not self.config.check_teams_involved:
            return []

        # Normalize and check if empty (P1 - data quality requirement)
        teams_involved = normalize_teams_involved(initiative.get('teams_involved'))

        if not teams_involved:
            return [ValidationIssue(
                type="missing_teams_involved",
                priority=Priority.CRITICAL,
                description="List contributing teams",
                initiative_key=initiative.get('key', ''),
                initiative_summary=initiative.get('summary', ''),
                initiative_status=initiative.get('status', ''),
                owner_team=initiative.get('owner_team'),
            )]

        return []

    def _check_missing_epics(self, initiative: Dict) -> List[ValidationIssue]:
        """Check for missing epics from expected teams with status-aware priority.

        Priority escalation:
        - Proposed: P2 (HIGH) - Important signal of commitment
        - Planned: P1 (CRITICAL) - Dependencies must be confirmed
        - In Progress: P1 (CRITICAL) - Teams should have epics for active work

        Rules:
        - Compare teams_involved vs teams with epics
        - Exempt owner team (doesn't need epic)
        - Exempt discovery initiatives
        - Report which specific teams are missing epics

        Args:
            initiative: Initiative dictionary

        Returns:
            List of ValidationIssue (0 or more items)
        """
        issues = []

        # Skip discovery initiatives
        if self.config.skip_discovery and is_discovery_initiative(initiative):
            return []

        # Normalize teams_involved (handles string or list format)
        teams_involved = normalize_teams_involved(initiative.get('teams_involved'))
        if not teams_involved:
            return []

        # Filter out owner team if exemption enabled
        owner_team = initiative.get('owner_team')
        if self.config.owner_team_exempt and owner_team:
            teams_involved = [
                team for team in teams_involved
                if not is_owner_team(team, owner_team, self.config.team_mappings or {})
            ]

        # Get teams with epics
        contributing_teams = initiative.get('contributing_teams', [])
        teams_with_epics = {ct['team_project_key'] for ct in contributing_teams if ct.get('epics')}

        # Calculate status-aware priority
        status = initiative.get('status', '')
        if status == 'Proposed':
            priority = Priority.HIGH  # P2
        else:  # Planned or In Progress
            priority = Priority.CRITICAL  # P1

        # Find missing teams
        for team in teams_involved:
            # Normalize team name using mappings if provided
            team_key = team
            if self.config.team_mappings and team in self.config.team_mappings:
                team_key = self.config.team_mappings[team]

            if team_key not in teams_with_epics:
                issues.append(ValidationIssue(
                    type="missing_epic",
                    priority=priority,
                    description=f"Missing epic from {team} team - Create epic",
                    initiative_key=initiative.get('key', ''),
                    initiative_summary=initiative.get('summary', ''),
                    initiative_status=initiative.get('status', ''),
                    owner_team=initiative.get('owner_team'),
                    team_affected=team_key,
                ))

        return issues

    def _check_rag_status(self, initiative: Dict) -> List[ValidationIssue]:
        """Check for missing RAG status on epics with status-aware priority.

        Priority escalation:
        - Proposed: P2 (HIGH) - Important signal of confidence
        - Planned: P1 (CRITICAL) - Teams must track health
        - In Progress: N/A (not validated - already in validate())

        Rules:
        - Only for Proposed/Planned status
        - Skip owner team epics
        - Skip RAG-exempt teams
        - Report missing RAG by team

        Args:
            initiative: Initiative dictionary

        Returns:
            List of ValidationIssue (0 or more items)
        """
        issues = []

        # Skip discovery initiatives
        if self.config.skip_discovery and is_discovery_initiative(initiative):
            return []

        owner_team = initiative.get('owner_team')
        contributing_teams = initiative.get('contributing_teams', [])

        # Calculate status-aware priority
        status = initiative.get('status', '')
        if status == 'Proposed':
            priority = Priority.HIGH  # P2
        else:  # Planned
            priority = Priority.CRITICAL  # P1

        for ct in contributing_teams:
            team_key = ct.get('team_project_key')

            # Skip owner team
            if self.config.owner_team_exempt and owner_team:
                if is_owner_team(team_key, owner_team, self.config.team_mappings or {}):
                    continue

            # Skip RAG-exempt teams
            if self.config.rag_exempt_teams and team_key in self.config.rag_exempt_teams:
                continue

            # Check each epic for RAG status
            for epic in ct.get('epics', []):
                rag_status = epic.get('rag_status')

                if not rag_status or (isinstance(rag_status, str) and not rag_status.strip()):
                    issues.append(ValidationIssue(
                        type="missing_rag_status",
                        priority=priority,
                        description=f"Missing RAG status on {epic.get('key', 'epic')} ({team_key} team) - Set RAG",
                        initiative_key=initiative.get('key', ''),
                        initiative_summary=initiative.get('summary', ''),
                        initiative_status=initiative.get('status', ''),
                        owner_team=initiative.get('owner_team'),
                        team_affected=team_key,
                        epic_key=epic.get('key'),
                    ))

        return issues


# Helper functions

def normalize_teams_involved(teams_involved: Any) -> List[str]:
    """Normalize teams_involved field to a list.

    Handles multiple formats:
    - None/null → []
    - Empty list → []
    - List of teams → list (unchanged)
    - Comma-separated string → split into list

    Args:
        teams_involved: Value from teams_involved field

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


def is_owner_team(team_key: str, owner_team: str, team_mappings: Dict[str, str]) -> bool:
    """Check if team is the owner team.

    Args:
        team_key: Team project key (e.g., "TEAM1")
        owner_team: Owner team name or key
        team_mappings: Mapping of display names to project keys

    Returns:
        True if team is the owner team
    """
    if not team_key or not owner_team:
        return False

    # Direct match
    if team_key == owner_team:
        return True

    # Check if owner_team is a display name that maps to team_key
    if owner_team in team_mappings and team_mappings[owner_team] == team_key:
        return True

    return False


def is_discovery_initiative(initiative: Dict) -> bool:
    """Check if initiative is marked as Discovery.

    Args:
        initiative: Initiative dictionary

    Returns:
        True if summary starts with "[Discovery]"
    """
    summary = initiative.get('summary', '')
    return summary.startswith('[Discovery]')


def load_validation_config(
    status_filter: Optional[str] = None,
    include_rag_validation: bool = True
) -> ValidationConfig:
    """Load validation configuration based on filters.

    Args:
        status_filter: Optional status filter (e.g., "In Progress")
        include_rag_validation: Whether to include RAG validation

    Returns:
        ValidationConfig instance
    """
    # Load strategic objectives from config
    config_path = Path('config/jira_config.yaml')
    valid_objectives = []

    if config_path.exists():
        with open(config_path) as f:
            jira_config = yaml.safe_load(f)
            valid_objectives = jira_config.get('validation', {}).get('strategic_objective', {}).get('valid_values', [])

    # Load team mappings
    team_mappings_path = Path('config/team_mappings.yaml')
    team_mappings = {}
    rag_exempt_teams = []

    if team_mappings_path.exists():
        with open(team_mappings_path) as f:
            mappings_config = yaml.safe_load(f)
            team_mappings = mappings_config.get('team_mappings', {})
            rag_exempt_teams = mappings_config.get('teams_exempt_from_rag', [])

    # Determine if RAG should be checked based on status
    check_rag = include_rag_validation
    if status_filter == 'In Progress':
        check_rag = False

    return ValidationConfig(
        check_assignee=True,
        check_strategic_objective=True,
        check_teams_involved=True,
        check_missing_epics=True,
        check_rag_status=check_rag,
        owner_team_exempt=True,
        skip_discovery=True,
        valid_strategic_objectives=valid_objectives,
        team_mappings=team_mappings,
        rag_exempt_teams=rag_exempt_teams,
    )


def create_action_item(issue: ValidationIssue, manager: str, slack_id: str) -> Dict:
    """Convert ValidationIssue to action item dict.

    Args:
        issue: ValidationIssue instance
        manager: Manager username
        slack_id: Manager Slack ID

    Returns:
        Action item dictionary
    """
    return {
        'initiative_key': issue.initiative_key,
        'initiative_summary': issue.initiative_summary,
        'initiative_status': issue.initiative_status,
        'owner_team': issue.owner_team,
        'manager': manager,
        'manager_slack_id': slack_id,
        'priority': int(issue.priority),
        'priority_label': f'P{int(issue.priority)}',
        'type': issue.type,
        'description': issue.description,
        'team_affected': issue.team_affected,
        'epic_key': issue.epic_key,
        'current_value': issue.current_value,
        'expected_value': issue.expected_value,
    }
