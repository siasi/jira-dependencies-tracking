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

    # Validate snapshot
    python validate_initiative_status.py data/snapshots/snapshot_baseline_*.json
"""

import json
import sys
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
    teams_involved = initiative.get('teams_involved', [])
    teams_with_epics = {
        tc['team_project_key']
        for tc in initiative.get('team_contributions', [])
        if tc.get('epics')
    }

    if len(teams_involved) != len(teams_with_epics):
        issues.append({
            'type': 'epic_count_mismatch',
            'teams_involved': teams_involved,
            'teams_with_epics': list(teams_with_epics)
        })

    # Check for missing RAG status
    missing_rag_epics = []
    for tc in initiative.get('team_contributions', []):
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
    total_epics = sum(len(tc.get('epics', [])) for tc in initiative.get('team_contributions', []))
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

    for tc in initiative.get('team_contributions', []):
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
    total_epics = sum(len(tc.get('epics', [])) for tc in initiative.get('team_contributions', []))
    if total_epics == 0:
        return False

    # Must have assignee
    if not initiative.get('assignee'):
        return False

    # Epic count must match teams count
    teams_involved = initiative.get('teams_involved', [])
    teams_with_epics = {
        tc['team_project_key']
        for tc in initiative.get('team_contributions', [])
        if tc.get('epics')
    }
    if len(teams_involved) != len(teams_with_epics):
        return False

    # All epics must have GREEN RAG status
    for tc in initiative.get('team_contributions', []):
        for epic in tc.get('epics', []):
            if epic.get('rag_status') != '🟢':
                return False

    return True


def validate_initiative_status(json_file: Path) -> ValidationResult:
    """Validate initiative readiness for Proposed → Planned transition.

    Args:
        json_file: Path to JSON file from jira_extract.py or snapshot

    Returns:
        ValidationResult with categorized findings
    """
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    result = ValidationResult()
    initiatives = data.get('initiatives', [])
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
                    'team_contributions': initiative.get('team_contributions', []),
                    'issues': data_quality_issues
                })
            elif commitment_blocker_issues:
                result.address_blockers.append({
                    'key': initiative_key,
                    'summary': initiative_summary,
                    'status': initiative_status,
                    'assignee': initiative_assignee,
                    'team_contributions': initiative.get('team_contributions', []),
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


def print_validation_report(result: ValidationResult, json_file: Path):
    """Print formatted validation report with three sections.

    Args:
        result: ValidationResult with findings
        json_file: Path to validated JSON file
    """
    print(f"\n{'=' * 80}")
    print("Initiative Status Validation Report")
    print(f"{'=' * 80}\n")

    print(f"Data source: {json_file}")
    print(f"Total initiatives checked: {result.total_checked}\n")

    print("Summary:")
    print(f"  🔴 Fix Data Quality: {len(result.fix_data_quality)} initiatives (BLOCKS PLANNING)")
    print(f"  🟡 Address Commitment Blockers: {len(result.address_blockers)} initiatives (NOT READY)")
    print(f"  ✅ Ready to Move to Planned: {len(result.ready_to_plan)} initiatives")
    if result.planned_regressions:
        print(f"  ⚠️  Planned Initiatives with Issues: {len(result.planned_regressions)} initiatives (REGRESSIONS)")

    print(f"\n{'-' * 80}\n")

    # Section 1: Fix Data Quality
    if result.fix_data_quality:
        print(f"🔴 FIX DATA QUALITY ({len(result.fix_data_quality)} initiatives - BLOCKS PLANNING)\n")

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
                        for tc in item['team_contributions']
                        for epic in tc.get('epics', [])
                    ]
                    print(f"   ⚠️  Epic count mismatch")
                    print(f"       - Has {len(epic_keys)} epics: {', '.join(epic_keys)}")
                    print(f"       - Teams Involved field shows {len(issue['teams_involved'])} teams: {', '.join(issue['teams_involved'])}")
                    missing_from_field = set(issue['teams_with_epics']) - set(issue['teams_involved'])
                    extra_in_field = set(issue['teams_involved']) - set(issue['teams_with_epics'])
                    if missing_from_field:
                        print(f"       - Missing from field: {', '.join(missing_from_field)}")
                    if extra_in_field:
                        print(f"       - Extra in field: {', '.join(extra_in_field)}")
                    print()

                elif issue['type'] == 'missing_rag_status':
                    print(f"   ⚠️  Missing RAG status on {len(issue['epics'])} epics")
                    for epic in issue['epics']:
                        print(f"       - {epic['key']}: \"{epic['summary']}\" (no RAG status set)")
                    print()

                elif issue['type'] == 'no_epics':
                    print(f"   ⚠️  No epics found")
                    print(f"       - Initiative has zero epics linked")
                    print(f"       - Cannot validate RAG status or team involvement")
                    print()

        print(f"{'-' * 80}\n")

    # Section 2: Address Commitment Blockers
    if result.address_blockers:
        print(f"🟡 ADDRESS COMMITMENT BLOCKERS ({len(result.address_blockers)} initiatives - NOT READY)\n")

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

    # Section 3: Ready to Move to Planned
    if result.ready_to_plan:
        print(f"✅ READY TO MOVE TO PLANNED ({len(result.ready_to_plan)} initiatives)\n")

        for item in result.ready_to_plan:
            print(f"{item['key']}: {item['summary']}")

        print(f"\nBulk update - Copy these issue keys for Jira:")
        keys = [item['key'] for item in result.ready_to_plan]
        print(','.join(keys))

        print(f"\n{'-' * 80}\n")

    # Section 4: Planned Initiatives with Issues (regressions)
    if result.planned_regressions:
        print(f"⚠️  PLANNED INITIATIVES WITH ISSUES ({len(result.planned_regressions)} initiatives - REGRESSIONS)\n")
        print("These initiatives are currently 'Planned' but no longer meet the criteria:\n")

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
    # Determine which file to validate
    if len(sys.argv) > 1:
        json_file = Path(sys.argv[1])
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
        result = validate_initiative_status(json_file)
        print_validation_report(result, json_file)

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
