---
title: Initiative Status Validation Tool
type: feat
status: completed
date: 2026-03-21
origin: docs/brainstorms/2026-03-21-initiative-status-validation-brainstorm.md
---

# Initiative Status Validation Tool

## Overview

Build a Python CLI validation script that analyzes Jira initiatives to determine readiness for status transitions from Proposed to Planned. The tool categorizes initiatives into three action-oriented groups based on data quality and commitment readiness, provides epic-level detail for all issues, and outputs Jira-ready bulk update keys.

## Problem Statement / Motivation

**Problem:** Engineering managers need to know which initiatives are ready to promote from Proposed to Planned status, but manual checking of epic RAG status, team dependencies, and assignee presence across dozens of initiatives is time-consuming and error-prone.

**Impact:** Without systematic validation:
- Initiatives move to Planned with incomplete data (missing RAG status, mismatched team counts)
- Commitment blockers go unnoticed (RED/YELLOW epics, missing assignees)
- Regression detection is manual (Planned initiatives that no longer meet criteria)
- Bulk status updates require manual key collection

**Goal:** Automate initiative readiness validation with epic-level detail to enable confident, fast status transitions during planning sessions.

## Proposed Solution

Create `validate_initiative_status.py` following the proven pattern from `validate_dependencies.py` (see brainstorm: docs/brainstorms/2026-03-21-initiative-status-validation-brainstorm.md).

**Key Decision (from brainstorm):** Chose dedicated script approach (Approach B) over extending `validate_dependencies.py` (scope creep risk) or building validation framework (overkill for current need).

**Tool Type:** Validation/reporting only - shows recommendations, user manually updates Jira. Not an automatic updater.

## Technical Approach

### File Structure

```
validate_initiative_status.py    # Main script (new file)
tests/
  test_validate_initiative_status.py  # Test suite (new file)
docs/
  plans/
    2026-03-21-001-feat-initiative-status-validation-plan.md  # This file
  brainstorms/
    2026-03-21-initiative-status-validation-brainstorm.md  # Origin document
```

### Data Structure

**Input:** JSON file from `jira_extract.py` or snapshots:

```json
{
  "initiatives": [
    {
      "key": "INIT-1497",
      "summary": "Initiative title",
      "status": "Proposed|Planned|In Progress|Done",
      "assignee": "user@email.com",  // May be null
      "team_contributions": [
        {
          "team_project_key": "CONSOLE",
          "epics": [
            {
              "key": "CONSOLE-806",
              "summary": "Epic title",
              "rag_status": null | "🟢" | "⚠️" | "🔴"
            }
          ]
        }
      ]
    }
  ]
}
```

### Validation Categories

**(from brainstorm: docs/brainstorms/2026-03-21-initiative-status-validation-brainstorm.md)**

#### 1. Fix Data Quality (blocks planning)

**Conditions:**
- Epic count ≠ Teams Involved count (reuse logic from `validate_dependencies.py:75-86`)
- Missing RAG status on any epic (treat as blocker)
- Initiative has zero epics

**Epic-level detail required:**
- Show all epic keys with titles
- Identify which teams are missing/extra
- List which specific epics lack RAG status

#### 2. Address Commitment Blockers (not ready)

**Conditions:**
- Any epic has RED status (🔴)
- Any epic has YELLOW status (⚠️)
- Initiative has no assignee
- Missing RAG status (treated as RED per brainstorm decision)

**Epic-level detail required:**
- List each RED epic with key and title
- List each YELLOW epic with key and title
- Show assignee field status

#### 3. Ready to Move to Planned

**Conditions:**
- All epics have GREEN RAG status (🟢)
- Epic count matches Teams Involved count
- All epics have RAG status set
- Initiative has assignee
- At least one epic exists

**Output format:**
- Simple list of initiative keys and titles
- Comma-separated keys for Jira bulk update

### Bidirectional Checking

**(from brainstorm: check both directions for completeness)**

Check two scenarios:
1. **Proposed → Planned**: Show initiatives in "Proposed" status that are ready to promote
2. **Planned → Proposed**: Flag regressions - initiatives in "Planned" status that no longer meet criteria

### Implementation Phases

#### Phase 1: Core Validation Logic

**Tasks:**
- [x] Create `validate_initiative_status.py` file
- [x] Copy `ValidationResult` class pattern from `validate_dependencies.py:24-46`
- [x] Extend `ValidationResult` to support three categories:
  ```python
  class ValidationResult:
      def __init__(self):
          self.fix_data_quality: List[Dict[str, Any]] = []
          self.address_blockers: List[Dict[str, Any]] = []
          self.ready_to_plan: List[Dict[str, Any]] = []
          self.planned_regressions: List[Dict[str, Any]] = []  # Planned→Proposed
          self.total_checked = 0
  ```
- [x] Implement `validate_initiative_status(json_file: Path) -> ValidationResult`
- [x] Load JSON data following `validate_dependencies.py:58-62` pattern
- [x] Loop through initiatives, check status field for filtering

**Validation Logic Functions:**

```python
def _check_data_quality(initiative: dict) -> Optional[Dict[str, Any]]:
    """Check for data quality blockers."""
    issues = []

    # Check epic count vs teams count (reuse validate_dependencies.py logic)
    teams_involved = initiative.get('teams_involved', [])
    teams_with_epics = {tc['team_project_key'] for tc in initiative.get('team_contributions', []) if tc.get('epics')}

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

def _check_commitment_blockers(initiative: dict) -> Optional[Dict[str, Any]]:
    """Check for commitment blockers."""
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
    """Check if initiative meets all criteria for Planned status."""
    # Must have at least one epic
    total_epics = sum(len(tc.get('epics', [])) for tc in initiative.get('team_contributions', []))
    if total_epics == 0:
        return False

    # Must have assignee
    if not initiative.get('assignee'):
        return False

    # Epic count must match teams count
    teams_involved = initiative.get('teams_involved', [])
    teams_with_epics = {tc['team_project_key'] for tc in initiative.get('team_contributions', []) if tc.get('epics')}
    if len(teams_involved) != len(teams_with_epics):
        return False

    # All epics must have GREEN RAG status
    for tc in initiative.get('team_contributions', []):
        for epic in tc.get('epics', []):
            if epic.get('rag_status') != '🟢':
                return False

    return True
```

#### Phase 2: Report Formatting

**Tasks:**
- [ ] Implement `print_validation_report(result: ValidationResult, json_file: Path)`
- [ ] Follow report formatting conventions from `src/reports.py:140-200`
- [ ] Use visual conventions: `'=' * 80`, `'-' * 80`, emoji indicators
- [ ] Implement epic-level detail sections

**Report Structure:**

```python
def print_validation_report(result: ValidationResult, json_file: Path):
    """Print formatted validation report with three sections."""

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
        print("🔴 FIX DATA QUALITY ({} initiatives - BLOCKS PLANNING)\n".format(len(result.fix_data_quality)))

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
                    # Show detailed epic count mismatch (like validate_dependencies.py)
                    epic_keys = [epic['key'] for tc in item['team_contributions'] for epic in tc.get('epics', [])]
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
        print("🟡 ADDRESS COMMITMENT BLOCKERS ({} initiatives - NOT READY)\n".format(len(result.address_blockers)))

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
        print("✅ READY TO MOVE TO PLANNED ({} initiatives)\n".format(len(result.ready_to_plan)))

        for item in result.ready_to_plan:
            print(f"{item['key']}: {item['summary']}")

        print(f"\nBulk update - Copy these issue keys for Jira:")
        keys = [item['key'] for item in result.ready_to_plan]
        print(','.join(keys))

        print(f"\n{'-' * 80}\n")

    # Section 4: Planned Initiatives with Issues (regressions)
    if result.planned_regressions:
        print("⚠️  PLANNED INITIATIVES WITH ISSUES ({} initiatives - REGRESSIONS)\n".format(len(result.planned_regressions)))
        print("These initiatives are currently 'Planned' but no longer meet the criteria:\n")

        for item in result.planned_regressions:
            print(f"{item['key']}: {item['summary']}")
            print(f"   Current Status: {item['status']}")
            print(f"   Issue: {item['reason']}")
            print()

        print(f"{'-' * 80}\n")
```

#### Phase 3: File Handling & CLI

**Tasks:**
- [ ] Copy `find_latest_extract()` from `validate_dependencies.py:166-185`
- [ ] Support both `jira_extract_*.json` and `snapshot_*.json` patterns
- [ ] Implement `main()` following `validate_dependencies.py:187-218`
- [ ] Handle CLI arguments (explicit file path or auto-detect latest)
- [ ] Add shebang and docstring following Python conventions

**File Finding Logic:**

```python
def find_latest_extract() -> Path:
    """Find the most recent extraction file."""
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
```

**Main Entry Point:**

```python
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
        has_issues = (len(result.fix_data_quality) > 0 or
                     len(result.address_blockers) > 0 or
                     len(result.planned_regressions) > 0)
        sys.exit(1 if has_issues else 0)

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
```

#### Phase 4: Testing

**Tasks:**
- [x] Create `tests/test_validate_initiative_status.py`
- [x] Follow test patterns from `tests/test_builder.py` and `tests/test_output.py`
- [x] Test each validation category independently
- [x] Test edge cases: zero epics, all missing RAG, mixed statuses
- [x] Test bidirectional checking (Proposed and Planned initiatives)
- [x] Test file finding logic
- [x] Ensure all tests pass before finalizing

**Test Structure:**

```python
# tests/test_validate_initiative_status.py
import json
import pytest
from pathlib import Path
from validate_initiative_status import (
    ValidationResult,
    validate_initiative_status,
    _check_data_quality,
    _check_commitment_blockers,
    _is_ready_to_plan
)

def test_fix_data_quality_epic_count_mismatch(tmp_path):
    """Test initiative with epic count != teams count."""
    data = {
        "initiatives": [{
            "key": "INIT-123",
            "summary": "Test Initiative",
            "status": "Proposed",
            "assignee": "user@example.com",
            "teams_involved": ["TEAM1", "TEAM2"],
            "team_contributions": [
                {
                    "team_project_key": "TEAM1",
                    "epics": [{"key": "TEAM1-1", "summary": "Epic 1", "rag_status": "🟢"}]
                },
                {
                    "team_project_key": "TEAM2",
                    "epics": [{"key": "TEAM2-1", "summary": "Epic 2", "rag_status": "🟢"}]
                },
                {
                    "team_project_key": "TEAM3",  # Not in teams_involved
                    "epics": [{"key": "TEAM3-1", "summary": "Epic 3", "rag_status": "🟢"}]
                }
            ]
        }]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(data))

    result = validate_initiative_status(json_file)

    assert len(result.fix_data_quality) == 1
    assert result.fix_data_quality[0]['key'] == "INIT-123"

def test_address_blockers_red_epic(tmp_path):
    """Test initiative with RED epic."""
    data = {
        "initiatives": [{
            "key": "INIT-456",
            "summary": "Test Initiative",
            "status": "Proposed",
            "assignee": "user@example.com",
            "teams_involved": ["TEAM1"],
            "team_contributions": [
                {
                    "team_project_key": "TEAM1",
                    "epics": [{"key": "TEAM1-1", "summary": "Blocked Epic", "rag_status": "🔴"}]
                }
            ]
        }]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(data))

    result = validate_initiative_status(json_file)

    assert len(result.address_blockers) == 1
    assert result.address_blockers[0]['key'] == "INIT-456"

def test_ready_to_plan(tmp_path):
    """Test initiative ready for Planned status."""
    data = {
        "initiatives": [{
            "key": "INIT-789",
            "summary": "Ready Initiative",
            "status": "Proposed",
            "assignee": "user@example.com",
            "teams_involved": ["TEAM1"],
            "team_contributions": [
                {
                    "team_project_key": "TEAM1",
                    "epics": [{"key": "TEAM1-1", "summary": "Green Epic", "rag_status": "🟢"}]
                }
            ]
        }]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(data))

    result = validate_initiative_status(json_file)

    assert len(result.ready_to_plan) == 1
    assert result.ready_to_plan[0]['key'] == "INIT-789"

def test_planned_regression(tmp_path):
    """Test Planned initiative with issues (regression)."""
    data = {
        "initiatives": [{
            "key": "INIT-999",
            "summary": "Regressed Initiative",
            "status": "Planned",  # Already Planned
            "assignee": "user@example.com",
            "teams_involved": ["TEAM1"],
            "team_contributions": [
                {
                    "team_project_key": "TEAM1",
                    "epics": [{"key": "TEAM1-1", "summary": "Now Red", "rag_status": "🔴"}]
                }
            ]
        }]
    }

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(data))

    result = validate_initiative_status(json_file)

    assert len(result.planned_regressions) == 1
    assert result.planned_regressions[0]['key'] == "INIT-999"
```

#### Phase 5: Documentation

**Tasks:**
- [x] Update `README.md` with new validation script usage
- [x] Add examples for common scenarios
- [x] Document exit codes (0 = success, 1 = issues found)
- [x] Link to brainstorm document for context

**README Section:**

```markdown
## Initiative Status Validation

Validate initiative readiness for Proposed → Planned status transitions based on epic RAG status, team dependencies, and assignee presence.

### Usage

Validate latest extraction:
```bash
python validate_initiative_status.py
```

Validate specific file:
```bash
python validate_initiative_status.py data/jira_extract_20260321.json
```

Validate snapshot:
```bash
python validate_initiative_status.py data/snapshots/snapshot_baseline_*.json
```

### What It Checks

**Fix Data Quality (blocks planning):**
- Epic count matches Teams Involved count
- All epics have RAG status set
- Initiative has at least one epic

**Address Commitment Blockers (not ready):**
- No RED or YELLOW epics (all must be GREEN)
- Initiative has assignee
- Missing RAG status treated as RED

**Ready to Move to Planned:**
- All checks above pass
- Outputs Jira-ready issue keys for bulk update

**Bidirectional Checking:**
- Checks Proposed → Planned transitions
- Flags Planned → Proposed regressions

### Output

Terminal report with three sections:
1. 🔴 Fix Data Quality - Initiatives with data issues (epic-level detail)
2. 🟡 Address Commitment Blockers - Initiatives not ready (epic-level detail)
3. ✅ Ready to Move to Planned - Comma-separated keys for bulk Jira update

### Exit Codes

- `0` - All validations passed, initiatives ready
- `1` - Validation issues found (data quality or commitment blockers)

### Design Documentation

See [brainstorm document](docs/brainstorms/2026-03-21-initiative-status-validation-brainstorm.md) for design decisions and approach rationale.
```

## Alternative Approaches Considered

**(from brainstorm: docs/brainstorms/2026-03-21-initiative-status-validation-brainstorm.md)**

**Approach A: Extend `validate_dependencies.py`**
- **Rejected:** Scope creep risk, script name becomes misleading ("dependencies" vs "status validation")

**Approach C: Create validation framework**
- **Deferred:** Good long-term architecture but overkill for current need, can refactor later if more validators needed

**Approach B: Create new `validate_initiative_status.py` script** ✅ **CHOSEN**
- **Selected:** Clear separation of concerns, fast to implement, reuses proven patterns

## Acceptance Criteria

### Functional Requirements

- [ ] Script accepts optional file path argument or auto-detects latest extraction
- [ ] Validates all three categories: data quality, commitment blockers, ready list
- [ ] Shows epic-level detail for all issues (specific epic keys, titles, RAG status)
- [ ] Supports bidirectional checking (Proposed and Planned statuses)
- [ ] Outputs comma-separated Jira keys for bulk update
- [ ] Handles missing fields gracefully (assignee, RAG status, etc.)

### Non-Functional Requirements

- [ ] Follows existing patterns from `validate_dependencies.py`
- [ ] Exit code 0 for success, 1 for validation issues found
- [ ] Clear error messages for file not found, invalid JSON
- [ ] Report formatting follows `src/reports.py` conventions
- [ ] Action-oriented section names ("Fix Data Quality" vs "Data Validation Issues")

### Quality Gates

- [ ] All tests pass (pytest)
- [ ] Test coverage for each validation category
- [ ] Edge cases tested (zero epics, all missing RAG, mixed statuses)
- [ ] README updated with usage examples
- [ ] Code follows CLAUDE.md conventions (functional style, clear error messages)

## Dependencies & Risks

**Dependencies:**
- Existing `validate_dependencies.py` as template
- JSON structure from `jira_extract.py` output
- Python 3.9+ with standard library (json, sys, pathlib, typing)

**Risks:**
- **Low:** JSON structure changes - Mitigated by using `.get()` with defaults
- **Low:** Missing custom fields in data - Handled gracefully, treated as blockers
- **Low:** Large datasets - Script is read-only, performance should be acceptable

## Success Metrics

**Functional Success:**
- Engineering managers can run script and get actionable recommendations in < 10 seconds
- Bulk update keys copy-paste directly into Jira (no manual editing)
- Epic-level detail enables quick issue resolution

**Quality Success:**
- All tests pass
- Zero silent failures (clear error messages for all failure modes)
- Report output is scannable and actionable

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-03-21-initiative-status-validation-brainstorm.md](../brainstorms/2026-03-21-initiative-status-validation-brainstorm.md)
- **Key decisions carried forward:**
  1. Dedicated script approach (Approach B)
  2. Three-category validation system
  3. Epic-level detail in reports
  4. Bidirectional checking for regressions
  5. Missing RAG treated as RED (conservative)

### Internal References

- Validation pattern: [validate_dependencies.py](../validate_dependencies.py)
  - Lines 24-46: ValidationResult class pattern
  - Lines 49-110: Main validation loop
  - Lines 113-163: Report formatting
  - Lines 166-185: File finding logic
  - Lines 187-218: Main entry point and error handling
- Report formatting: [src/reports.py:140-200](../src/reports.py)
- Data structures: [src/output.py:11-18](../src/output.py)
- Coding standards: [CLAUDE.md](../CLAUDE.md)

### Institutional Learnings

- **CLI Error Handling:** [docs/solutions/code-quality/cli-error-handling-duplication.md](../docs/solutions/code-quality/cli-error-handling-duplication.md)
  - Centralize error handlers, avoid duplication
  - Use DRY principle for common error patterns

### Related Work

- PR #2: Quarterly Snapshot Tracking (provides snapshot data structure)
- `validate_dependencies.py`: Team count validation (template for this script)
