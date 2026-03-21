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

    # Only analyze initiatives with 2+ teams
    python validate_initiative_status.py --min-teams 2

    # Validate snapshot with team filter
    python validate_initiative_status.py data/snapshots/snapshot_baseline_*.json --min-teams 2
"""

import argparse
import json
import sys
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional


class ValidationResult:
    """Results of initiative status validation."""

    def __init__(self):
        self.fix_data_quality: List[Dict[str, Any]] = []
        self.address_blockers: List[Dict[str, Any]] = []
        self.ready_to_plan: List[Dict[str, Any]] = []
        self.planned_regressions: List[Dict[str, Any]] = []
        self.total_checked = 0
        self.total_filtered = 0  # Initiatives excluded by filters

    @property
    def has_issues(self) -> bool:
        """Whether any issues were found."""
        return (len(self.fix_data_quality) > 0 or
                len(self.address_blockers) > 0 or
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

    # Check for missing RAG status
    missing_rag_epics = []
    for tc in initiative.get('contributing_teams', []):
        for epic in tc.get('epics', []):
            if epic.get('rag_status') is None:
                missing_rag_epics.append({
                    'key': epic['key'],
                    'summary': epic['summary']
                })

    if missing_rag_epics:
        issues.append({
            'type': 'missing_rag_status',
            'epics': missing_rag_epics
        })

    # Check for zero epics
    total_epics = sum(len(tc.get('epics', [])) for tc in initiative.get('contributing_teams', []))
    if total_epics == 0:
        issues.append({'type': 'no_epics'})

    return issues if issues else None


def _check_commitment_blockers(initiative: dict) -> Optional[List[Dict[str, Any]]]:
    """Check for commitment blockers.

    Args:
        initiative: Initiative dictionary from JSON

    Returns:
        List of commitment blocker issues, or None if no issues
    """
    issues = []

    # Check for RED/YELLOW epics (and missing RAG treated as RED)
    red_epics = []
    yellow_epics = []

    for tc in initiative.get('contributing_teams', []):
        for epic in tc.get('epics', []):
            rag = epic.get('rag_status')
            if rag == '🔴' or rag is None:  # Missing treated as RED
                red_epics.append({
                    'key': epic['key'],
                    'summary': epic['summary'],
                    'rag_status': rag
                })
            elif rag == '⚠️':
                yellow_epics.append({
                    'key': epic['key'],
                    'summary': epic['summary']
                })

    if red_epics:
        issues.append({'type': 'red_epics', 'epics': red_epics})
    if yellow_epics:
        issues.append({'type': 'yellow_epics', 'epics': yellow_epics})

    # Check for missing assignee
    if not initiative.get('assignee'):
        issues.append({'type': 'no_assignee'})

    return issues if issues else None


def _is_ready_to_plan(initiative: dict) -> bool:
    """Check if initiative meets all criteria for Planned status.

    Args:
        initiative: Initiative dictionary from JSON

    Returns:
        True if ready for Planned status, False otherwise
    """
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
        owner_team = initiative.get('owner_team')
        team_mappings = _load_team_mappings()

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

    # All epics must have GREEN RAG status
    for tc in initiative.get('contributing_teams', []):
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
        # Handle comma-separated string (e.g., "Identity, Core Banking, MAP")
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


def validate_initiative_status(json_file: Path, min_teams: int = 1) -> ValidationResult:
    """Validate initiative readiness for Proposed → Planned transition.

    Args:
        json_file: Path to JSON file from jira_extract.py or snapshot
        min_teams: Minimum number of teams required (default: 1, all initiatives)

    Returns:
        ValidationResult with categorized findings
    """
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    result = ValidationResult()
    all_initiatives = data.get('initiatives', [])

    # Apply team count filter
    if min_teams > 1:
        initiatives = [
            init for init in all_initiatives
            if _count_teams_involved(init.get('teams_involved')) >= min_teams
        ]
        result.total_filtered = len(all_initiatives) - len(initiatives)
    else:
        initiatives = all_initiatives
        result.total_filtered = 0

    result.total_checked = len(initiatives)

    for initiative in initiatives:
        initiative_key = initiative['key']
        initiative_summary = initiative['summary']
        initiative_status = initiative.get('status', 'Unknown')
        initiative_assignee = initiative.get('assignee')

        # Check data quality issues first (highest priority)
        data_quality_issues = _check_data_quality(initiative)

        # Check commitment blockers
        commitment_blocker_issues = _check_commitment_blockers(initiative)

        # Bidirectional checking
        if initiative_status == 'Proposed':
            # Check if ready to move to Planned
            if data_quality_issues:
                result.fix_data_quality.append({
                    'key': initiative_key,
                    'summary': initiative_summary,
                    'status': initiative_status,
                    'assignee': initiative_assignee,
                    'contributing_teams': initiative.get('contributing_teams', []),
                    'issues': data_quality_issues
                })
            elif commitment_blocker_issues:
                result.address_blockers.append({
                    'key': initiative_key,
                    'summary': initiative_summary,
                    'status': initiative_status,
                    'assignee': initiative_assignee,
                    'contributing_teams': initiative.get('contributing_teams', []),
                    'issues': commitment_blocker_issues
                })
            elif _is_ready_to_plan(initiative):
                result.ready_to_plan.append({
                    'key': initiative_key,
                    'summary': initiative_summary
                })

        elif initiative_status == 'Planned':
            # Check for regressions (Planned initiatives that no longer meet criteria)
            if not _is_ready_to_plan(initiative):
                reason = []
                if data_quality_issues:
                    reason.append("Data quality issues")
                if commitment_blocker_issues:
                    reason.append("Commitment blockers")

                result.planned_regressions.append({
                    'key': initiative_key,
                    'summary': initiative_summary,
                    'status': initiative_status,
                    'reason': ", ".join(reason) if reason else "Does not meet criteria"
                })

    return result


def print_validation_report(result: ValidationResult, json_file: Path, min_teams: int = 1, verbose: bool = False):
    """Print formatted validation report with three sections.

    Args:
        result: ValidationResult with findings
        json_file: Path to validated JSON file
        min_teams: Minimum team count filter applied
        verbose: Show detailed epic and team information
    """
    # Load team mappings for detailed action messages
    team_mappings = _load_team_mappings()

    print(f"\n{'=' * 80}")
    print("Initiative Planning Readiness Tracker")
    print(f"{'=' * 80}\n")

    print(f"Data source: {json_file}")
    if min_teams > 1:
        print(f"Filter: Teams Involved >= {min_teams}")
        print(f"Total initiatives in file: {result.total_checked + result.total_filtered}")
        print(f"Initiatives analyzed: {result.total_checked}")
        print(f"Initiatives filtered out: {result.total_filtered}\n")
    else:
        print(f"Total initiatives checked: {result.total_checked}\n")

    print("Summary:")
    print(f"  📊 Initiative Setup in Progress: {len(result.fix_data_quality)} initiatives")
    print(f"  🤝 Commitment & Readiness Check: {len(result.address_blockers)} initiatives")
    print(f"  ✅ Cleared for Planning: {len(result.ready_to_plan)} initiatives")
    if result.planned_regressions:
        print(f"  🔄 Planned Initiatives Requiring Attention: {len(result.planned_regressions)} initiatives")

    print(f"\n{'-' * 80}\n")

    # Section 1: Initiative Setup in Progress
    if result.fix_data_quality:
        print(f"📊 INITIATIVE SETUP IN PROGRESS ({len(result.fix_data_quality)} initiatives)\n")
        print("To advance: Complete epic setup and team coordination")
        print("Help needed: Create missing epics, set initial RAG status\n")

        for item in result.fix_data_quality:
            print(f"{item['key']}: {item['summary']}")
            print(f"   Current Status: {item['status']}")
            if item.get('assignee'):
                print(f"   Assignee: {item['assignee']}")
            else:
                print(f"   Assignee: (none)")
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

                    print(f"   ⚠️  Epic count mismatch")
                    if verbose:
                        print(f"       - Has {len(epic_keys)} epics: {', '.join(epic_keys)}")
                        print(f"       - Teams Involved: {', '.join(issue['teams_involved'])}")

                    if epics_count < teams_count:
                        # Find which teams are missing epics
                        teams_with_epics_set = set(issue['teams_with_epics'])
                        missing_teams = []

                        for display_name in issue['teams_involved']:
                            # Look up project key from mapping
                            project_key = team_mappings.get(display_name)
                            if project_key and project_key not in teams_with_epics_set:
                                missing_teams.append(f"{display_name} ({project_key})")
                            elif not project_key and display_name not in teams_with_epics_set:
                                # No mapping found, show display name only
                                missing_teams.append(f"{display_name} (unmapped)")

                        if missing_teams:
                            epic_word = "epic" if len(missing_teams) == 1 else "epics"
                            print(f"       - Action: {', '.join(missing_teams)} to create {epic_word}")
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
                    epic_keys = [epic['key'] for epic in issue['epics']]
                    print(f"   ⚠️  Missing RAG status")
                    if verbose:
                        for epic in issue['epics']:
                            print(f"       - {epic['key']}: \"{epic['summary']}\"")
                    epic_word = "RAG status" if len(epic_keys) == 1 else "RAG status"
                    print(f"       - Action: {', '.join(epic_keys)} to set {epic_word}")
                    print()

                elif issue['type'] == 'no_epics':
                    print(f"   ⚠️  No epics found")
                    print(f"       - Initiative has zero epics linked")
                    print(f"       - Cannot validate RAG status or team involvement")
                    print()

        print(f"{'-' * 80}\n")

    # Section 2: Commitment & Readiness Check
    if result.address_blockers:
        print(f"🤝 COMMITMENT & READINESS CHECK ({len(result.address_blockers)} initiatives)\n")
        print("To advance: Confirm all teams are ready with green RAG")
        print("Help needed: Update RAG status, assign owner\n")

        for item in result.address_blockers:
            print(f"{item['key']}: {item['summary']}")
            print(f"   Current Status: {item['status']}")
            if item.get('assignee'):
                print(f"   Assignee: {item['assignee']}")
            else:
                print(f"   Assignee: (none)")
            print()

            for issue in item['issues']:
                if issue['type'] == 'red_epics':
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

    # Section 3: Cleared for Planning (always show)
    print(f"✅ CLEARED FOR PLANNING ({len(result.ready_to_plan)} initiatives)\n")

    if result.ready_to_plan:
        for item in result.ready_to_plan:
            print(f"{item['key']}: {item['summary']}")

        print(f"\nBulk update - Copy these issue keys for Jira:")
        keys = [item['key'] for item in result.ready_to_plan]
        print(','.join(keys))
    else:
        print("No initiatives are ready to move to Planned status at this time.")

    print(f"\n{'-' * 80}\n")

    # Section 4: Planned Initiatives Requiring Attention (regressions)
    if result.planned_regressions:
        print(f"🔄 PLANNED INITIATIVES REQUIRING ATTENTION ({len(result.planned_regressions)} initiatives)\n")
        print("To maintain quality: Review status changes for these planned initiatives")
        print("Help needed: Verify RAG status updates, confirm team commitment\n")

        for item in result.planned_regressions:
            print(f"{item['key']}: {item['summary']}")
            print(f"   Current Status: {item['status']}")
            print(f"   Issue: {item['reason']}")
            print()

        print(f"{'-' * 80}\n")


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
        '--min-teams',
        type=int,
        default=1,
        help='Minimum number of teams required (default: 1, all initiatives)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed epic and team information in validation output'
    )

    args = parser.parse_args()

    # Determine which file to validate
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

    # Run validation
    try:
        result = validate_initiative_status(json_file, min_teams=args.min_teams)
        print_validation_report(result, json_file, min_teams=args.min_teams, verbose=args.verbose)

        # Exit with error code if issues found
        sys.exit(1 if result.has_issues else 0)

    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
