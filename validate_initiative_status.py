#!/usr/bin/env python3
"""Validate initiative readiness for Proposed → Planned status transitions.

This script analyzes Jira initiatives to determine readiness for status transitions
based on epic RAG status, team dependencies, and assignee presence. It categorizes
initiatives into three groups: Fix Data Quality, Address Commitment Blockers, and
Ready to Move to Planned.

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
        # Section 2: Can't be completed in the quarter
        self.cannot_complete_quarter: List[Dict[str, Any]] = []
        # Section 3: Low confidence for planning
        self.low_confidence: List[Dict[str, Any]] = []
        # Section 4: Ready - Awaiting Owner
        self.awaiting_owner: List[Dict[str, Any]] = []
        # Section 5: Ready to Move to Planned
        self.ready_to_plan: List[Dict[str, Any]] = []
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
                len(self.cannot_complete_quarter) > 0 or
                len(self.low_confidence) > 0 or
                len(self.awaiting_owner) > 0 or
                len(self.planned_regressions) > 0)


def _check_data_quality(initiative: dict) -> Optional[List[Dict[str, Any]]]:
    """Check for data quality blockers.

    Args:
        initiative: Initiative dictionary from JSON

    Returns:
        List of data quality issues, or None if no issues
    """
    issues = []

    # Check epic count vs teams count
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

    # Check for missing RAG status (skip owner team epics)
    owner_team = initiative.get('owner_team')
    team_mappings = _load_team_mappings()

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

        if not is_owner_team:
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

    # Check for zero epics
    total_epics = sum(len(tc.get('epics', [])) for tc in initiative.get('contributing_teams', []))
    if total_epics == 0:
        issues.append({'type': 'no_epics'})

    return issues if issues else None


def _has_red_epics(initiative: dict) -> Optional[List[Dict[str, Any]]]:
    """Check if initiative has RED epics (skip owner team).

    Args:
        initiative: Initiative dictionary from JSON

    Returns:
        List of RED epics, or None if no RED epics
    """
    owner_team = initiative.get('owner_team')
    team_mappings = _load_team_mappings()

    red_epics = []

    for tc in initiative.get('contributing_teams', []):
        team_key = tc.get('team_project_key', '')

        # Skip epics from owner team
        is_owner_team = False
        if owner_team:
            owner_project_key = team_mappings.get(owner_team, owner_team)
            if team_key.upper() == owner_project_key.upper():
                is_owner_team = True

        if not is_owner_team:
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
    """Check if initiative has YELLOW epics (skip owner team).

    Args:
        initiative: Initiative dictionary from JSON

    Returns:
        List of YELLOW epics, or None if no YELLOW epics
    """
    owner_team = initiative.get('owner_team')
    team_mappings = _load_team_mappings()

    yellow_epics = []

    for tc in initiative.get('contributing_teams', []):
        team_key = tc.get('team_project_key', '')

        # Skip epics from owner team
        is_owner_team = False
        if owner_team:
            owner_project_key = team_mappings.get(owner_team, owner_team)
            if team_key.upper() == owner_project_key.upper():
                is_owner_team = True

        if not is_owner_team:
            for epic in tc.get('epics', []):
                rag = epic.get('rag_status')
                if rag == '⚠️':
                    yellow_epics.append({
                        'key': epic['key'],
                        'summary': epic['summary']
                    })

    return yellow_epics if yellow_epics else None


def _is_ready_to_plan(initiative: dict) -> bool:
    """Check if initiative meets all criteria for Planned status.

    Args:
        initiative: Initiative dictionary from JSON

    Returns:
        True if ready for Planned status, False otherwise
    """
    # Load owner team info upfront (used for multiple checks)
    owner_team = initiative.get('owner_team')
    team_mappings = _load_team_mappings()

    # Must have at least one epic
    total_epics = sum(len(tc.get('epics', [])) for tc in initiative.get('contributing_teams', []))
    if total_epics == 0:
        return False

    # Must have assignee
    if not initiative.get('assignee'):
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

    # All epics must have GREEN RAG status (skip owner team epics)
    for tc in initiative.get('contributing_teams', []):
        team_key = tc.get('team_project_key', '')

        # Skip epics from owner team (they don't need to report RAG status)
        is_owner_team = False
        if owner_team:
            owner_project_key = team_mappings.get(owner_team, owner_team)
            if team_key.upper() == owner_project_key.upper():
                is_owner_team = True

        if not is_owner_team:
            for epic in tc.get('epics', []):
                if epic.get('rag_status') != '🟢':
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

    # Filter to multi-team initiatives only (teams >= 2)
    initiatives = []
    for init in all_initiatives:
        team_count = _count_teams_involved(init.get('teams_involved'))
        if team_count >= 2:
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

                if red_epics:
                    # Section 2: Can't be completed in the quarter
                    result.cannot_complete_quarter.append({
                        'key': initiative_key,
                        'summary': initiative_summary,
                        'status': initiative_status,
                        'assignee': initiative_assignee,
                        'url': initiative_url,
                        'contributing_teams': initiative.get('contributing_teams', []),
                        'issues': [{
                            'type': 'red_epics',
                            'epics': red_epics
                        }]
                    })
                elif yellow_epics:
                    # Section 3: Low confidence for planning
                    result.low_confidence.append({
                        'key': initiative_key,
                        'summary': initiative_summary,
                        'status': initiative_status,
                        'assignee': initiative_assignee,
                        'url': initiative_url,
                        'contributing_teams': initiative.get('contributing_teams', []),
                        'issues': [{
                            'type': 'yellow_epics',
                            'epics': yellow_epics
                        }]
                    })
                else:
                    # All epics GREEN, check assignee
                    if not initiative_assignee:
                        # Section 4: Ready - Awaiting Owner
                        result.awaiting_owner.append({
                            'key': initiative_key,
                            'summary': initiative_summary,
                            'status': initiative_status,
                            'url': initiative_url,
                            'contributing_teams': initiative.get('contributing_teams', []),
                            'issues': [{
                                'type': 'no_assignee'
                            }]
                        })
                    else:
                        # Section 5: Ready to Move to Planned
                        result.ready_to_plan.append({
                            'key': initiative_key,
                            'summary': initiative_summary,
                            'status': initiative_status,
                            'assignee': initiative_assignee,
                            'url': initiative_url
                        })

        elif initiative_status == 'Planned':
            # Check for regressions (Planned initiatives that no longer meet criteria)
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
                    all_issues.extend(red_epics)

                # Check for YELLOW epics
                yellow_epics = _has_yellow_epics(initiative)
                if yellow_epics:
                    all_issues.extend(yellow_epics)

                # Check for missing assignee
                if not initiative_assignee:
                    all_issues.append({
                        'type': 'Missing Assignee',
                        'details': 'Initiative has no assignee'
                    })

                result.planned_regressions.append({
                    'key': initiative_key,
                    'summary': initiative_summary,
                    'status': initiative_status,
                    'assignee': initiative_assignee,
                    'url': initiative_url,
                    'contributing_teams': initiative.get('contributing_teams', []),
                    'issues': all_issues if all_issues else []
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
    """Print formatted validation report with five sections.

    Args:
        result: ValidationResult with findings
        json_file: Path to validated JSON file
        verbose: Show detailed epic and team information
    """
    # Load team mappings for detailed action messages
    team_mappings = _load_team_mappings()

    print(f"\n{'=' * 80}")
    print("Initiative Planning Readiness Tracker")
    print(f"{'=' * 80}\n")

    print(f"Data source: {json_file}")
    print(f"Filter: Multi-team initiatives only (teams >= 2)")
    print(f"Total initiatives in file: {result.total_checked + result.total_filtered}")
    print(f"Multi-team initiatives analyzed: {result.total_checked}")
    if result.total_filtered > 0:
        print(f"Single-team initiatives skipped: {result.total_filtered}")
    print()

    print("Summary:")
    print(f"  📋 Dependency Mapping in Progress: {len(result.dependency_mapping)} initiatives")
    print(f"  🔴 Can't be completed in the quarter: {len(result.cannot_complete_quarter)} initiatives")
    print(f"  🟡 Low confidence for planning - require discussion: {len(result.low_confidence)} initiatives")
    print(f"  👤 Ready - Awaiting Owner: {len(result.awaiting_owner)} initiatives")
    print(f"  ✅ Ready to Move to Planned: {len(result.ready_to_plan)} initiatives")
    if verbose:
        if result.planned_regressions:
            print(f"  🔄 Planned Initiatives with Issues: {len(result.planned_regressions)} initiatives")
        if result.ignored_statuses:
            print(f"  ⏭️  Not Analyzed: {len(result.ignored_statuses)} initiatives")

    print(f"\n{'-' * 80}\n")

    # Section 1: Dependency Mapping in Progress
    if result.dependency_mapping:
        print(f"📋 DEPENDENCY MAPPING IN PROGRESS ({len(result.dependency_mapping)} initiatives)\n")
        print("Action required: Create missing epics and set initial RAG status\n")

        for item in result.dependency_mapping:
            print(f"{item['key']}: {item['summary']}")
            print()

            for issue in item['issues']:
                if issue['type'] == 'epic_count_mismatch':
                    # Show detailed epic count mismatch
                    epic_keys = [
                        epic['key']
                        for tc in item['contributing_teams']
                        for epic in tc.get('epics', [])
                    ]
                    teams_count = len(issue['teams_involved'])
                    epics_count = len(issue['teams_with_epics'])

                    print(f"   ⚠️  Missing dependencies - Action:")
                    if verbose:
                        print(f"       - Has {len(epic_keys)} epics: {', '.join(epic_keys)}")
                        print(f"       - Teams Involved: {', '.join(issue['teams_involved'])}")

                    if epics_count < teams_count:
                        # Find which teams are missing epics (excluding owner team)
                        teams_with_epics_set = set(issue['teams_with_epics'])
                        owner_team = item.get('owner_team')
                        missing_teams = []

                        for display_name in issue['teams_involved']:
                            # Skip owner team - they don't need to create epics
                            if owner_team and display_name == owner_team:
                                continue

                            # Look up project key from mapping
                            project_key = team_mappings.get(display_name)
                            if project_key and project_key not in teams_with_epics_set:
                                missing_teams.append(f"{display_name} ({project_key})")
                            elif not project_key and display_name not in teams_with_epics_set:
                                # No mapping found, show display name only
                                missing_teams.append(f"{display_name} (unmapped)")

                        if missing_teams:
                            for team in missing_teams:
                                print(f"       [ ] {team} to create epic")
                        else:
                            missing_count = teams_count - epics_count
                            print(f"       - Action: Create {missing_count} missing epic{'s' if missing_count > 1 else ''} or update Teams Involved field")
                    elif epics_count > teams_count:
                        # Find which teams have epics but aren't in Teams Involved
                        teams_involved_keys = set()
                        for display_name in issue['teams_involved']:
                            # Try mapping first, then fall back to display name (case-insensitive)
                            project_key = team_mappings.get(display_name)
                            if project_key:
                                teams_involved_keys.add(project_key.upper())
                            else:
                                teams_involved_keys.add(display_name.upper())

                        # Find teams with epics that aren't in the Teams Involved set
                        extra_teams = [key for key in issue['teams_with_epics']
                                      if key.upper() not in teams_involved_keys]

                        if extra_teams:
                            print(f"       - Action: Add {', '.join(extra_teams)} to Teams Involved field")
                        else:
                            print(f"       - Action: Update Teams Involved field to include all {epics_count} teams with epics")
                    print()

                elif issue['type'] == 'missing_rag_status':
                    print(f"   ⚠️  Missing RAG status - Action:")
                    for team_data in issue['teams']:
                        team_name = team_data['team_name']
                        epic_keys = [epic['key'] for epic in team_data['epics']]
                        epics_str = ', '.join(epic_keys)

                        if verbose:
                            print(f"       - {team_name}:")
                            for epic in team_data['epics']:
                                print(f"         {epic['key']}: \"{epic['summary']}\"")

                        print(f"       [ ] {team_name} to set RAG status for {epics_str}")
                    print()

        print(f"{'-' * 80}\n")

    # Section 2: Can't be completed in the quarter
    if result.cannot_complete_quarter:
        print(f"🔴 CAN'T BE COMPLETED IN THE QUARTER ({len(result.cannot_complete_quarter)} initiatives)\n")
        print("Teams cannot commit - deprioritize other work to proceed\n")

        for item in result.cannot_complete_quarter:
            print(f"{item['key']}: {item['summary']}")
            print()

            for issue in item['issues']:
                if issue['type'] == 'red_epics':
                    print(f"   ⚠️  Epics with RED status ({len(issue['epics'])})")
                    for epic in issue['epics']:
                        rag_display = "🔴" if epic['rag_status'] == '🔴' else "(missing - treated as RED)"
                        print(f"       - {epic['key']} {rag_display}: \"{epic['summary']}\"")
                    print()

        print(f"{'-' * 80}\n")

    # Section 3: Low confidence for planning - require discussion
    if result.low_confidence:
        print(f"🟡 LOW CONFIDENCE FOR PLANNING - REQUIRE DISCUSSION ({len(result.low_confidence)} initiatives)\n")
        print("Low confidence - evaluate re-sequencing or reprioritization\n")

        for item in result.low_confidence:
            print(f"{item['key']}: {item['summary']}")
            print()

            for issue in item['issues']:
                if issue['type'] == 'yellow_epics':
                    print(f"   ⚠️  Epics with YELLOW status ({len(issue['epics'])})")
                    for epic in issue['epics']:
                        print(f"       - {epic['key']} 🟡: \"{epic['summary']}\"")
                    print()

        print(f"{'-' * 80}\n")

    # Section 4: Ready - Awaiting Owner
    if result.awaiting_owner:
        print(f"👤 READY - AWAITING OWNER ({len(result.awaiting_owner)} initiatives)\n")
        print("Action required: Assign initiative owner to proceed\n")

        for item in result.awaiting_owner:
            print(f"{item['key']}: {item['summary']}")
            print()

        print(f"{'-' * 80}\n")

    # Section 5: Ready to Move to Planned (always show)
    print(f"✅ READY TO MOVE TO PLANNED ({len(result.ready_to_plan)} initiatives)\n")
    print("Action required: Update status to Planned in Jira (bulk keys provided below)\n")

    if result.ready_to_plan:
        for item in result.ready_to_plan:
            print(f"{item['key']}: {item['summary']}")

        print(f"\nBulk update - Copy these issue keys for Jira:")
        keys = [item['key'] for item in result.ready_to_plan]
        print(','.join(keys))
    else:
        print("No initiatives are ready to move to Planned status at this time.")

    print(f"\n{'-' * 80}\n")

    # Section 4: Planned Initiatives Requiring Attention (regressions) - verbose only
    if verbose and result.planned_regressions:
        print(f"🔄 PLANNED INITIATIVES REQUIRING ATTENTION ({len(result.planned_regressions)} initiatives)\n")
        print("To maintain quality: Review status changes for these planned initiatives")
        print("Help needed: Verify RAG status updates, confirm team commitment\n")

        for item in result.planned_regressions:
            print(f"{item['key']}: {item['summary']}")
            print(f"   Current Status: {item['status']}")
            if item.get('assignee'):
                print(f"   Assignee: {item['assignee']}")
            else:
                print(f"   Assignee: (none)")
            print()

            # Show detailed issues (same format as Sections 1 and 2)
            for issue in item.get('issues', []):
                if issue['type'] == 'epic_count_mismatch':
                    # Show detailed epic count mismatch
                    epic_keys = [
                        epic['key']
                        for tc in item['contributing_teams']
                        for epic in tc.get('epics', [])
                    ]
                    teams_count = len(issue['teams_involved'])
                    epics_count = len(issue['teams_with_epics'])

                    print(f"   ⚠️  Missing dependencies - Action:")
                    if verbose:
                        print(f"       - Has {len(epic_keys)} epics: {', '.join(epic_keys)}")
                        print(f"       - Teams Involved: {', '.join(issue['teams_involved'])}")

                    if epics_count < teams_count:
                        # Find which teams are missing epics (excluding owner team)
                        teams_with_epics_set = set(issue['teams_with_epics'])
                        owner_team = item.get('owner_team')
                        missing_teams = []

                        for display_name in issue['teams_involved']:
                            # Skip owner team - they don't need to create epics
                            if owner_team and display_name == owner_team:
                                continue

                            # Look up project key from mapping
                            project_key = team_mappings.get(display_name)
                            if project_key and project_key not in teams_with_epics_set:
                                missing_teams.append(f"{display_name} ({project_key})")
                            elif not project_key and display_name not in teams_with_epics_set:
                                # No mapping found, show display name only
                                missing_teams.append(f"{display_name} (unmapped)")

                        if missing_teams:
                            for team in missing_teams:
                                print(f"       [ ] {team} to create epic")
                        else:
                            missing_count = teams_count - epics_count
                            print(f"       - Action: Create {missing_count} missing epic{'s' if missing_count > 1 else ''} or update Teams Involved field")
                    elif epics_count > teams_count:
                        # Find which teams have epics but aren't in Teams Involved
                        teams_involved_keys = set()
                        for display_name in issue['teams_involved']:
                            # Try mapping first, then fall back to display name (case-insensitive)
                            project_key = team_mappings.get(display_name)
                            if project_key:
                                teams_involved_keys.add(project_key.upper())
                            else:
                                teams_involved_keys.add(display_name.upper())

                        # Find teams with epics that aren't in the Teams Involved set
                        extra_teams = [key for key in issue['teams_with_epics']
                                      if key.upper() not in teams_involved_keys]

                        if extra_teams:
                            print(f"       - Action: Add {', '.join(extra_teams)} to Teams Involved field")
                        else:
                            print(f"       - Action: Update Teams Involved field to include all {epics_count} teams with epics")
                    print()

                elif issue['type'] == 'missing_rag_status':
                    print(f"   ⚠️  Missing RAG status - Action:")
                    for team_data in issue['teams']:
                        team_name = team_data['team_name']
                        epic_keys = [epic['key'] for epic in team_data['epics']]
                        epics_str = ', '.join(epic_keys)

                        if verbose:
                            print(f"       - {team_name}:")
                            for epic in team_data['epics']:
                                print(f"         {epic['key']}: \"{epic['summary']}\"")

                        print(f"       [ ] {team_name} to set RAG status for {epics_str}")
                    print()

                elif issue['type'] == 'no_epics':
                    print(f"   ⚠️  No epics found")
                    print(f"       - Initiative has zero epics linked")
                    print(f"       - Cannot validate RAG status or team involvement")
                    print()

                elif issue['type'] == 'red_epics':
                    print(f"   ⚠️  Epics with RED status ({len(issue['epics'])})")
                    for epic in issue['epics']:
                        rag_display = "🔴" if epic['rag_status'] == '🔴' else "(missing - treated as RED)"
                        print(f"       - {epic['key']} {rag_display}: \"{epic['summary']}\"")
                    print()

                elif issue['type'] == 'yellow_epics':
                    print(f"   ⚠️  Epics with YELLOW status ({len(issue['epics'])})")
                    for epic in issue['epics']:
                        print(f"       - {epic['key']} 🟡: \"{epic['summary']}\"")
                    print()

                elif issue['type'] == 'no_assignee':
                    print(f"   ⚠️  No assignee set")
                    print(f"       - Initiative needs an owner before moving to Planned")
                    print()

        print(f"{'-' * 80}\n")

    # Section 5: Not Analyzed (other statuses) - verbose only
    if verbose and result.ignored_statuses:
        print(f"⏭️  NOT ANALYZED ({len(result.ignored_statuses)} initiatives)\n")
        print("These initiatives have statuses other than 'Proposed' or 'Planned'")
        print("and are not included in the readiness validation:\n")

        for item in result.ignored_statuses:
            print(f"{item['key']}: {item['summary']}")
            print(f"   Status: {item['status']}")
            print()

        print(f"{'-' * 80}\n")


def generate_markdown_report(result: ValidationResult, json_file: Path, verbose: bool = False) -> str:
    """Generate markdown-formatted validation report for Notion import.

    Args:
        result: ValidationResult with findings
        json_file: Path to validated JSON file
        verbose: Include verbose sections

    Returns:
        Markdown-formatted report string
    """
    # Load team mappings for detailed action messages
    team_mappings = _load_team_mappings()

    lines = []

    # Title
    lines.append("# Initiative Planning Readiness Tracker")
    lines.append("")

    # Metadata
    lines.append("## Report Metadata")
    lines.append("")
    lines.append(f"- **Data source**: `{json_file}`")
    lines.append(f"- **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **Filter**: Multi-team initiatives only (teams >= 2)")
    lines.append(f"- **Total initiatives in file**: {result.total_checked + result.total_filtered}")
    lines.append(f"- **Multi-team initiatives analyzed**: {result.total_checked}")
    if result.total_filtered > 0:
        lines.append(f"- **Single-team initiatives skipped**: {result.total_filtered}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- 📋 **Dependency Mapping in Progress**: {len(result.dependency_mapping)} initiatives")
    lines.append(f"- 🔴 **Can't be completed in the quarter**: {len(result.cannot_complete_quarter)} initiatives")
    lines.append(f"- 🟡 **Low confidence for planning - require discussion**: {len(result.low_confidence)} initiatives")
    lines.append(f"- 👤 **Ready - Awaiting Owner**: {len(result.awaiting_owner)} initiatives")
    lines.append(f"- ✅ **Ready to Move to Planned**: {len(result.ready_to_plan)} initiatives")
    if verbose:
        if result.planned_regressions:
            lines.append(f"- 🔄 **Planned Initiatives with Issues**: {len(result.planned_regressions)} initiatives")
        if result.ignored_statuses:
            lines.append(f"- ⏭️ **Not Analyzed**: {len(result.ignored_statuses)} initiatives")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 1: Dependency Mapping in Progress
    if result.dependency_mapping:
        lines.append(f"## 📋 Dependency Mapping in Progress ({len(result.dependency_mapping)} initiatives)")
        lines.append("")
        lines.append("**Action required**: Create missing epics and set initial RAG status")
        lines.append("")

        for item in result.dependency_mapping:
            lines.append(f"### [{item['key']}]({item.get('url', '#')}): {item['summary']}")
            lines.append("")

            for issue in item['issues']:
                if issue['type'] == 'epic_count_mismatch':
                    epic_keys = [
                        epic['key']
                        for tc in item['contributing_teams']
                        for epic in tc.get('epics', [])
                    ]
                    teams_count = len(issue['teams_involved'])
                    epics_count = len(issue['teams_with_epics'])

                    lines.append("**⚠️ Missing dependencies - Action:**")
                    lines.append("")

                    if epics_count < teams_count:
                        teams_with_epics_set = set(issue['teams_with_epics'])
                        owner_team = item.get('owner_team')
                        missing_teams = []
                        for display_name in issue['teams_involved']:
                            # Skip owner team - they don't need to create epics
                            if owner_team and display_name == owner_team:
                                continue

                            project_key = team_mappings.get(display_name)
                            if project_key and project_key not in teams_with_epics_set:
                                missing_teams.append(f"{display_name} ({project_key})")
                            elif not project_key and display_name not in teams_with_epics_set:
                                missing_teams.append(f"{display_name} (unmapped)")

                        if missing_teams:
                            for team in missing_teams:
                                lines.append(f"- [ ] {team} to create epic")
                        else:
                            missing_count = teams_count - epics_count
                            lines.append(f"- [ ] **Action**: Create {missing_count} missing epic{'s' if missing_count > 1 else ''} or update Teams Involved field")
                    elif epics_count > teams_count:
                        teams_involved_keys = set()
                        for display_name in issue['teams_involved']:
                            project_key = team_mappings.get(display_name)
                            if project_key:
                                teams_involved_keys.add(project_key.upper())
                            else:
                                teams_involved_keys.add(display_name.upper())

                        extra_teams = [key for key in issue['teams_with_epics']
                                      if key.upper() not in teams_involved_keys]

                        if extra_teams:
                            lines.append(f"- [ ] **Action**: Add {', '.join(extra_teams)} to Teams Involved field")
                        else:
                            lines.append(f"- [ ] **Action**: Update Teams Involved field to include all {epics_count} teams with epics")
                    lines.append("")

                elif issue['type'] == 'missing_rag_status':
                    lines.append("**⚠️ Missing RAG status - Action:**")
                    lines.append("")
                    for team_data in issue['teams']:
                        team_name = team_data['team_name']
                        # Create markdown links for each epic
                        epic_links = [f"[{epic['key']}]({epic['url']})" for epic in team_data['epics']]
                        epics_str = ', '.join(epic_links)
                        lines.append(f"- [ ] {team_name} to set RAG status for {epics_str}")
                    lines.append("")

        lines.append("---")
        lines.append("")

    # Section 2: Can't be completed in the quarter
    if result.cannot_complete_quarter:
        lines.append(f"## 🔴 Can't be completed in the quarter ({len(result.cannot_complete_quarter)} initiatives)")
        lines.append("")
        lines.append("**Teams cannot commit - deprioritize other work to proceed**")
        lines.append("")

        for item in result.cannot_complete_quarter:
            lines.append(f"### [{item['key']}]({item.get('url', '#')}): {item['summary']}")
            lines.append("")

            for issue in item['issues']:
                if issue['type'] == 'red_epics':
                    lines.append(f"**⚠️ Epics with RED status ({len(issue['epics'])})**")
                    lines.append("")
                    for epic in issue['epics']:
                        rag_display = "🔴" if epic['rag_status'] == '🔴' else "*(missing - treated as RED)*"
                        lines.append(f"- {epic['key']} {rag_display}: \"{epic['summary']}\"")
                    lines.append("")

        lines.append("---")
        lines.append("")

    # Section 3: Low confidence for planning - require discussion
    if result.low_confidence:
        lines.append(f"## 🟡 Low confidence for planning - require discussion ({len(result.low_confidence)} initiatives)")
        lines.append("")
        lines.append("**Low confidence - evaluate re-sequencing or reprioritization**")
        lines.append("")

        for item in result.low_confidence:
            lines.append(f"### [{item['key']}]({item.get('url', '#')}): {item['summary']}")
            lines.append("")

            for issue in item['issues']:
                if issue['type'] == 'yellow_epics':
                    lines.append(f"**⚠️ Epics with YELLOW status ({len(issue['epics'])})**")
                    lines.append("")
                    for epic in issue['epics']:
                        lines.append(f"- {epic['key']} 🟡: \"{epic['summary']}\"")
                    lines.append("")

        lines.append("---")
        lines.append("")

    # Section 4: Ready - Awaiting Owner
    if result.awaiting_owner:
        lines.append(f"## 👤 Ready - Awaiting Owner ({len(result.awaiting_owner)} initiatives)")
        lines.append("")
        lines.append("**Action required**: Assign initiative owner to proceed")
        lines.append("")

        for item in result.awaiting_owner:
            lines.append(f"- [{item['key']}]({item.get('url', '#')}): {item['summary']}")

        lines.append("---")
        lines.append("")

    # Section 5: Ready to Move to Planned
    lines.append(f"## ✅ Ready to Move to Planned ({len(result.ready_to_plan)} initiatives)")
    lines.append("")
    lines.append("**Action required**: Update status to Planned in Jira (bulk keys provided below)")
    lines.append("")

    if result.ready_to_plan:
        for item in result.ready_to_plan:
            lines.append(f"- [{item['key']}]({item.get('url', '#')}): {item['summary']}")
        lines.append("")
        lines.append("**Bulk update - Copy these issue keys for Jira:**")
        lines.append("")
        keys = [item['key'] for item in result.ready_to_plan]
        lines.append(f"`{','.join(keys)}`")
    else:
        lines.append("*No initiatives are ready to move to Planned status at this time.*")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 4: Planned Initiatives Requiring Attention (verbose only)
    if verbose and result.planned_regressions:
        lines.append(f"## 🔄 Planned Initiatives Requiring Attention ({len(result.planned_regressions)} initiatives)")
        lines.append("")
        lines.append("**To maintain quality**: Review status changes for these planned initiatives")
        lines.append("")
        lines.append("**Help needed**: Verify RAG status updates, confirm team commitment")
        lines.append("")

        for item in result.planned_regressions:
            lines.append(f"### [{item['key']}]({item.get('url', '#')}): {item['summary']}")
            lines.append("")
            lines.append(f"- **Status**: {item['status']}")
            lines.append(f"- **Assignee**: {item.get('assignee') or '*(none)*'}")
            lines.append("")

            # Show same detailed issues as text output
            for issue in item.get('issues', []):
                if issue['type'] == 'epic_count_mismatch':
                    lines.append("**⚠️ Missing dependencies - Action:**")
                    lines.append("")
                    # Similar logic as Section 1
                elif issue['type'] == 'missing_rag_status':
                    lines.append("**⚠️ Missing RAG status - Action:**")
                    lines.append("")
                    for team_data in issue['teams']:
                        team_name = team_data['team_name']
                        # Create markdown links for each epic
                        epic_links = [f"[{epic['key']}]({epic['url']})" for epic in team_data['epics']]
                        epics_str = ', '.join(epic_links)
                        lines.append(f"- [ ] {team_name} to set RAG status for {epics_str}")
                    lines.append("")
                elif issue['type'] == 'no_epics':
                    lines.append("**⚠️ No epics found**")
                    lines.append("")
                elif issue['type'] == 'red_epics':
                    lines.append(f"**⚠️ Epics with RED status ({len(issue['epics'])})**")
                    lines.append("")
                elif issue['type'] == 'yellow_epics':
                    lines.append(f"**⚠️ Epics with YELLOW status ({len(issue['epics'])})**")
                    lines.append("")
                elif issue['type'] == 'no_assignee':
                    lines.append("**⚠️ No assignee set**")
                    lines.append("")
                    lines.append("- [ ] **Action**: Initiative needs an owner before moving to Planned")
                    lines.append("")

        lines.append("---")
        lines.append("")

    # Section 5: Not Analyzed (verbose only)
    if verbose and result.ignored_statuses:
        lines.append(f"## ⏭️ Not Analyzed ({len(result.ignored_statuses)} initiatives)")
        lines.append("")
        lines.append("*These initiatives have statuses other than 'Proposed' or 'Planned' and are not included in the readiness validation:*")
        lines.append("")

        for item in result.ignored_statuses:
            lines.append(f"- **[{item['key']}]({item.get('url', '#')})**: {item['summary']}")
            lines.append(f"  - Status: `{item['status']}`")
        lines.append("")

    return "\n".join(lines)


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
