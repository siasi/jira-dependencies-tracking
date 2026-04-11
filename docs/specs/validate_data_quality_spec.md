# Data Quality Validation Script Specification

## Overview

Create a dedicated data quality validation script (`validate_data_quality.py`) that focuses exclusively on finding data quality issues and generating actionable items for managers. This script will use shared validation logic extracted to `lib/validation.py` to ensure consistency across all validation scripts.

## Goals

1. **Single Source of Truth**: Centralize all data quality validation logic
2. **Reusable Components**: Extract validation functions to shared library for use by all scripts
3. **Manager-Focused**: Generate clear, prioritized action items grouped by manager
4. **Flexible Filtering**: Support same filtering options as existing scripts (quarter, status)
5. **Status-Aware Validation**: Apply different validation rules based on initiative status

## Scope Filtering (Same as Existing Scripts)

The script should support the same filtering options as `analyze_workload.py`:

### Required Argument
- `--quarter <quarter>`: Quarter to validate (e.g., "26 Q2")

### Filter Logic
Include initiatives that match:
- **Status = "In Progress"** (any quarter), OR
- **Status = "Planned" AND Quarter = specified quarter**

Exclude:
- Initiatives in `config/initiative_exceptions.yaml` (manager-approved exceptions)
- Initiatives from excluded teams (configurable)
- Discovery initiatives: `[Discovery]` prefix (exempt from dependency checks only)

### Optional Filters
- `--status <status>`: Override default filter, validate only specific status (Proposed, Planned, In Progress, etc.)
- `--all-active`: Validate all active initiatives (not Done/Cancelled), ignore quarter filter

## Status-Aware Validation Rules

**Key Concept**: Validation severity **escalates** as initiatives progress through statuses. What's a minor issue in Proposed becomes critical in Planned/In Progress.

**Note**: DRI (Directly Responsible Individual) = the `assignee` field in Jira.

### All Statuses (Universal Checks)

These checks apply to all initiatives regardless of status:

| Check | Priority | Description |
|-------|----------|-------------|
| Missing owner_team | P1 | Blocks everything - initiative needs an owner team |
| Missing teams_involved | P1 | Blocks planning - must list contributing teams |
| Missing strategic_objective | P1 | Blocks planning - initiative needs strategic alignment |
| Invalid strategic_objective | P3 | Not in approved list - needs correction (typo/deprecated) |

**Rationale**: These are fundamental data quality requirements that never change priority regardless of status.

### Proposed Status (Planning Readiness)

Additional checks beyond universal:

| Check | Priority | Description |
|-------|----------|-------------|
| Missing assignee | P3 | Nice to have - can assign during planning |
| Missing epics from teams_involved | P2 | Important signal - teams confirm commitment via epics |
| Missing RAG status | P2 | Important signal - teams communicate confidence level |

**Rationale**: Proposed initiatives are being evaluated for readiness to move to Planned status. Priorities are moderate because:
- **Assignee (P3)**: Helpful but can be assigned later during planning
- **Epics (P2)**: Important for teams to signal commitment before we commit the quarter
- **RAG (P2)**: Important for teams to communicate confidence (Red/Amber/Green)

### Planned Status (Current Quarter Commitment) - **ESCALATED PRIORITIES**

Additional checks beyond universal:

| Check | Priority | Description |
|-------|----------|-------------|
| Missing assignee | P1 | **Critical** - must have DRI for committed work |
| Missing epics from teams_involved | P1 | **Critical** - dependencies must be confirmed |
| Missing RAG status | P1 | **Critical** - must track health for committed work |

**Rationale**: Planned initiatives are committed for the quarter. Priorities escalate to P1 because:
- **Assignee (P1)**: Work is committed - MUST have someone accountable
- **Epics (P1)**: Dependencies MUST be confirmed before quarter starts
- **RAG (P1)**: Teams MUST track health to signal risks early

By Planned status, these should have been resolved during Proposed phase.

### In Progress Status (Active Work) - **MAXIMUM SEVERITY**

Additional checks beyond universal:

| Check | Priority | Description |
|-------|----------|-------------|
| Missing assignee | P1 | **Critical** - active work must have owner coordinating execution |
| Missing epics from teams_involved | P1 | **Critical** - contributing teams must have epics tracking work |

**Rationale**: In Progress initiatives are actively being worked on. Priorities remain P1 because:
- **Assignee (P1)**: Critical to have someone coordinating active execution
- **Epics (P1)**: Teams must have epics to track their contributions
- **RAG status**: NOT validated - decision to proceed was already made, focus shifted to execution not planning signals

By In Progress status, all planning issues should have been resolved weeks ago.

### Done/Cancelled Status (Cleanup Only)

If `--all-active` or explicit `--status Done` used:

| Check | Priority | Description |
|-------|----------|-------------|
| Missing strategic_objective | P2 | Historical data completeness |
| Epics not marked Done | INFO | Cleanup opportunity |
| RAG status on Done epics | INFO | Cleanup opportunity |

**Rationale**: Only check if explicitly requested. Focus on data completeness for historical analysis.

### Severity Escalation Summary

This table shows how priorities change as initiatives progress:

| Check | Universal | Proposed | Planned | In Progress | Escalation Pattern |
|-------|-----------|----------|---------|-------------|-------------------|
| Missing owner_team | P1 | P1 | P1 | P1 | Always critical |
| Missing teams_involved | P1 | P1 | P1 | P1 | Always critical |
| Missing strategic_objective | P1 | P1 | P1 | P1 | Always critical |
| Invalid strategic_objective | P3 | P3 | P3 | P3 | Always medium |
| Missing assignee | - | P3 | **P1** ⬆️ | P1 | Escalates when committed |
| Missing epics | - | P2 | **P1** ⬆️ | P1 | Escalates when committed |
| Missing RAG | - | P2 | **P1** ⬆️ | N/A ⬇️ | Escalates, then drops |

**Key Insight**: As initiatives move from planning to execution, missing data becomes more severe because it should have been fixed earlier.

## Validation Logic - Special Cases

### Owner Team Exemption

**Rule**: Owner team is exempt from creating epics and setting RAG status

**Implementation**:
```python
# Filter out owner team from teams_involved before validation
# This approach is used in validate_prioritisation.py (lines 462-469, 680-686)
teams_involved = _normalize_teams_involved(initiative.get('teams_involved'))
owner_team = initiative.get('owner_team')
if owner_team and owner_team in teams_involved:
    teams_involved = [team for team in teams_involved if team != owner_team]

# Now teams_involved contains only contributing teams, not owner
# All downstream validation (missing epics, RAG status) works correctly
```

**Rationale**: Pre-filtering is simpler and more maintainable than checking at validation time. Owner team never enters the commitment matrix or health dashboard.

**Applies to**:
- Missing epics check: Owner team not expected to create epic
- Missing RAG check: Owner team not expected to set RAG status

### Exempt Teams

**Rule**: Teams in `config/rag_exempt_teams.yaml` are exempt from RAG status requirements

**Implementation**:
```python
exempt_teams = load_teams_exempt_from_rag()
if team_key in exempt_teams:
    continue  # Skip RAG validation for this team
```

### Discovery Initiatives

**Rule**: Initiatives with `[Discovery]` prefix exempt from dependency checks

**Implementation**:
```python
if initiative['summary'].startswith('[Discovery]'):
    # Skip: missing epics, epic count mismatch, missing RAG
    # Still check: owner, assignee, strategic objective
```

### Multi-Objective Strategic Objectives

**Rule**: Strategic objectives can be comma-separated list

**Implementation**:
```python
# Split by comma and validate each objective individually
objectives = [obj.strip() for obj in strategic_objective.split(',')]
invalid = [obj for obj in objectives if obj not in valid_objectives]
if invalid:
    issues.append({
        'type': 'invalid_strategic_objective',
        'current_value': strategic_objective,  # Full comma-separated string
        'invalid_values': invalid              # List of specific invalid objectives
    })
```

**Current Implementation**: This pattern is used in `validate_planning.py` (lines 92-109) and `analyze_workload.py` (lines 376-389).

## Output Formats

### Console Output (Default)

```
================================================================================
DATA QUALITY VALIDATION REPORT
Quarter: 26 Q2
Filter: In Progress (all quarters) + Planned (26 Q2)
================================================================================

Initiatives Analyzed: 47
Initiatives with Issues: 23
Exceptions Skipped: 3 (INIT-1301, INIT-1302, INIT-1303)

Action Items by Manager (5 managers, 38 action items):
--------------------------------------------------------------------------------

@Jane Smith - Platform Team
  6 action items across 3 initiatives

  INIT-456: Payment Gateway Integration
  Status: Planned
    P1 ⚠️  Assign initiative owner - @Jane Smith
    P3 ⚠️  Fix typo - @Jane Smith

  INIT-789: Customer Portal Redesign
  Status: In Progress
    P1 ⚠️  Set strategic objective - @Jane Smith

  INIT-901: Search Optimization (owned by Mobile Team)
  Status: Planned
    P1 ⚠️  Create epic (Platform) - @Jane Smith
    P1 ⚠️  Set RAG (Platform) - @Jane Smith
    P2 ⚠️  Set RAG (Platform) - @Jane Smith

--------------------------------------------------------------------------------

John Doe (@john.doe) - Mobile Team
  5 action items across 3 initiatives
  [... similar format ...]

================================================================================
Summary by Priority:
  P1 (Critical - blocks everything): 2 action items
  P2 (High - blocks planning): 12 action items
  P3 (Medium - data correction): 5 action items
  P4 (Low - missing dependencies): 15 action items
  P5 (Info - missing signals): 4 action items
================================================================================

Options:
  --verbose: Show detailed validation rules applied
  --slack: Generate Slack bulk messages
  --markdown <file>: Export as markdown report
  --json <file>: Export as JSON for automation
```

### Markdown Output

```markdown
# Data Quality Validation Report

**Quarter**: 26 Q2
**Filter**: In Progress (all quarters) + Planned (26 Q2)
**Date**: 2026-04-10

## Summary

- **Initiatives Analyzed**: 47
- **Initiatives with Issues**: 23
- **Total Action Items**: 38
- **Managers**: 5

## Action Items by Manager

### Jane Smith (@jane.smith) - Platform Team
8 action items across 4 initiatives

#### [INIT-456: Payment Gateway Integration](https://jira.example.com/browse/INIT-456)
**Status**: Planned | **Owner**: Platform | **Quarter**: 26 Q2

- ⚠️ **P2** Missing assignee - Assign initiative owner
- ⚠️ **P4** Missing epic from Mobile team - Create epic

[... continues ...]
```

### JSON Output (for automation)

```json
{
  "metadata": {
    "quarter": "26 Q2",
    "generated_at": "2026-04-10T21:30:00Z",
    "filter": "In Progress (all) + Planned (26 Q2)",
    "initiatives_analyzed": 47,
    "initiatives_with_issues": 23,
    "exceptions_skipped": ["INIT-1301", "INIT-1302", "INIT-1303"]
  },
  "action_items": [
    {
      "initiative_key": "INIT-456",
      "initiative_summary": "Payment Gateway Integration",
      "initiative_status": "Planned",
      "initiative_quarter": "26 Q2",
      "owner_team": "Platform",
      "manager": "jane.smith",
      "manager_slack_id": "U123456",
      "priority": 2,
      "priority_label": "P2",
      "type": "missing_assignee",
      "description": "Assign initiative owner",
      "action": "missing_assignee",
      "url": "https://jira.example.com/browse/INIT-456"
    }
  ],
  "summary_by_priority": {
    "P1": 2,
    "P2": 12,
    "P3": 5,
    "P4": 15,
    "P5": 4
  },
  "summary_by_manager": [
    {
      "manager": "jane.smith",
      "manager_name": "Jane Smith",
      "team": "Platform",
      "slack_id": "U123456",
      "total_actions": 8,
      "initiatives_count": 4
    }
  ]
}
```

### Slack Output

Same format as existing scripts - bulk messages grouped by manager.

## Script Interface

### Command Line Arguments

```bash
# Required
--quarter <quarter>          # Quarter to validate (e.g., "26 Q2")

# Filtering
--status <status>            # Override: validate only this status (Proposed, Planned, In Progress, etc.)
--all-active                 # Validate all active (not Done/Cancelled), ignore quarter

# Output formats
--markdown [filename]        # Generate markdown report (default: output/data_quality/NNN_data_quality_TIMESTAMP.md)
--json [filename]            # Export JSON (default: output/data_quality/NNN_data_quality_TIMESTAMP.json)
--slack                      # Generate Slack bulk messages (saves to output/data_quality/)

# Options
--verbose                    # Show detailed validation rules applied
--show-exempt                # Show skipped initiatives (exceptions, excluded teams)
--by-initiative              # Group by initiative instead of by manager
```

### Usage Examples

```bash
# Standard: validate current quarter planned + all in progress
python3 validate_data_quality.py --quarter "26 Q2"

# Only validate Proposed initiatives for planning readiness
python3 validate_data_quality.py --quarter "26 Q2" --status Proposed

# Validate all active initiatives regardless of quarter
python3 validate_data_quality.py --quarter "26 Q2" --all-active

# Generate Slack messages for manager action items
python3 validate_data_quality.py --quarter "26 Q2" --slack

# Export comprehensive markdown report
python3 validate_data_quality.py --quarter "26 Q2" --markdown

# Export JSON for automation/integration
python3 validate_data_quality.py --quarter "26 Q2" --json automation_feed.json

# Verbose output showing validation rules applied
python3 validate_data_quality.py --quarter "26 Q2" --verbose
```

## Shared Validation Library: `lib/validation.py`

**⚠️ FUTURE WORK**: This section describes a proposed shared validation library that **does not yet exist**. This is a design specification for future refactoring to consolidate validation logic from the three existing scripts (`validate_planning.py`, `validate_prioritisation.py`, `analyze_workload.py`) into a reusable library. Current implementation uses duplicated validation code across these scripts.

Extract all validation logic to a shared library that can be imported by all scripts.

### Module Structure

```python
# lib/validation.py

from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from enum import IntEnum

class Priority(IntEnum):
    """Action item priority levels"""
    CRITICAL = 1  # Blocks everything (missing owner)
    HIGH = 2      # Blocks planning (missing assignee, strategic objective)
    MEDIUM = 3    # Data correction (invalid values)
    LOW = 4       # Missing dependencies (epics)
    INFO = 5      # Missing signals (RAG status)

@dataclass
class ValidationIssue:
    """Represents a single data quality issue"""
    type: str                    # 'missing_owner', 'missing_epic', etc.
    priority: Priority
    description: str
    initiative_key: str
    initiative_summary: str
    initiative_status: str
    owner_team: Optional[str]
    team_affected: Optional[str]  # For team-specific issues
    epic_key: Optional[str]       # For epic-specific issues
    current_value: Optional[str]  # For invalid value issues
    expected_value: Optional[str]

@dataclass
class ValidationConfig:
    """Configuration for validation rules"""
    check_assignee: bool = True
    check_strategic_objective: bool = True
    check_teams_involved: bool = True
    check_missing_epics: bool = True
    check_rag_status: bool = True
    owner_team_exempt: bool = True
    skip_discovery: bool = True
    valid_strategic_objectives: List[str] = None
    team_mappings: Dict[str, str] = None
    rag_exempt_teams: List[str] = None

class InitiativeValidator:
    """Validates a single initiative for data quality issues"""

    def __init__(self, config: ValidationConfig):
        self.config = config

    def validate(self, initiative: Dict[str, Any]) -> List[ValidationIssue]:
        """
        Validate initiative and return list of issues.

        Applies status-aware validation rules:
        - All statuses: owner, strategic objective
        - Proposed/Planned: assignee, epics, RAG
        - In Progress: assignee, epics (no RAG)
        """
        issues = []

        # Universal checks (all statuses)
        issues.extend(self._check_owner_team(initiative))
        issues.extend(self._check_strategic_objective(initiative))
        issues.extend(self._check_teams_involved(initiative))

        # Status-specific checks
        status = initiative.get('status', '')

        if status in ['Proposed', 'Planned', 'In Progress']:
            issues.extend(self._check_assignee(initiative))
            issues.extend(self._check_missing_epics(initiative))

        if status in ['Proposed', 'Planned']:
            # RAG validation only for Proposed/Planned
            if self.config.check_rag_status:
                issues.extend(self._check_rag_status(initiative))

        return issues

    def _check_owner_team(self, initiative: Dict) -> List[ValidationIssue]:
        """Check for missing owner_team"""

    def _check_assignee(self, initiative: Dict) -> List[ValidationIssue]:
        """Check for missing assignee"""

    def _check_strategic_objective(self, initiative: Dict) -> List[ValidationIssue]:
        """
        Check strategic objective:
        - Missing
        - Invalid (not in valid list)
        - Multi-objective: split by comma and validate each
        """

    def _check_teams_involved(self, initiative: Dict) -> List[ValidationIssue]:
        """Check for missing or empty teams_involved field"""

    def _check_missing_epics(self, initiative: Dict) -> List[ValidationIssue]:
        """
        Check for missing epics from expected teams.

        Rules:
        - Compare teams_involved vs teams with epics
        - Exempt owner team (doesn't need epic)
        - Exempt discovery initiatives
        - Report which specific teams are missing epics
        """

    def _check_rag_status(self, initiative: Dict) -> List[ValidationIssue]:
        """
        Check for missing RAG status on epics.

        Rules:
        - Only for Proposed/Planned status
        - Skip owner team epics
        - Skip RAG-exempt teams
        - Report missing RAG by team
        """

# Helper functions
def is_owner_team(team_key: str, owner_team: str, team_mappings: Dict[str, str]) -> bool:
    """Check if team is the owner team"""

def is_discovery_initiative(initiative: Dict) -> bool:
    """Check if initiative is marked as Discovery"""

def load_validation_config(
    status_filter: str = None,
    include_rag_validation: bool = True
) -> ValidationConfig:
    """Load validation configuration based on filters"""

def create_action_item(issue: ValidationIssue, manager: str, slack_id: str) -> Dict:
    """Convert ValidationIssue to action item dict"""
```

### Usage by Other Scripts

```python
# In analyze_workload.py
from lib.validation import InitiativeValidator, load_validation_config

# Configure validation for In Progress initiatives (no RAG check)
config = load_validation_config(
    status_filter='In Progress',
    include_rag_validation=False
)
validator = InitiativeValidator(config)

# Validate each initiative
for initiative in initiatives:
    issues = validator.validate(initiative)
    if issues:
        # Handle data quality issues
        # Could skip from analysis or just report
        pass
```

```python
# In validate_planning.py
from lib.validation import InitiativeValidator, load_validation_config

# Configure for Proposed initiatives (full validation)
config = load_validation_config(
    status_filter='Proposed',
    include_rag_validation=True
)
validator = InitiativeValidator(config)

# Use in existing validation flow
issues = validator.validate(initiative)
```

## Implementation Plan

### Phase 1: Extract Validation Library
1. Create `lib/validation.py` with core validation classes
2. Implement `InitiativeValidator` with all validation methods
3. Add comprehensive tests for validation logic
4. Extract common validation from existing scripts

### Phase 2: Create Data Quality Script
1. Create `validate_data_quality.py` with CLI interface
2. Implement filtering logic (quarter, status, all-active)
3. Implement output formats (console, markdown, JSON, Slack)
4. Add exception handling (initiative_exceptions.yaml)

### Phase 3: Integrate with Existing Scripts
1. Update `analyze_workload.py` to use `lib/validation.py`
2. Update `validate_planning.py` to use `lib/validation.py`
3. Update `validate_prioritisation.py` to use `lib/validation.py`
4. Remove duplicated validation code

### Phase 4: Documentation & Testing
1. Update README with new script documentation
2. Add examples and usage patterns
3. Create comprehensive test suite
4. Update TODO.md to check off completed items

## Success Criteria

1. ✅ All validation logic centralized in `lib/validation.py`
2. ✅ `validate_data_quality.py` provides comprehensive data quality view
3. ✅ All three existing scripts use shared validation library (no duplication)
4. ✅ Status-aware validation rules properly applied
5. ✅ Multi-objective support consistent across all scripts
6. ✅ Owner team exemption consistent across all scripts
7. ✅ Same filtering capabilities as existing scripts
8. ✅ Manager-focused action item output
9. ✅ Slack integration for action items
10. ✅ Tests cover all validation rules

## Questions / Decisions Needed

1. **RAG validation for In Progress**: Confirmed - NOT validated (user specified) ✓
2. **Multi-objective format**: Comma-separated (current implementation) ✓
3. **Owner team creates epic?**: No - owner team exempt (current implementation) ✓
4. **Discovery initiative handling**: Exempt from dependency checks (current implementation) ✓
5. **Default output format**: Console + Slack only (markdown/JSON deferred) ✓
6. **Validation priority levels**: P1-P5 as defined above ✓

## Implementation Status

**Completed: 2026-04-11**

### Phase 1: Extract Validation Library ✓
- Created `lib/validation.py` with all core validation classes and functions
- Implemented `Priority` enum (IntEnum 1-5)
- Implemented `ValidationIssue` dataclass with all required fields
- Implemented `ValidationConfig` dataclass with configuration options
- Implemented `InitiativeValidator` class with status-aware validation
- All validation methods implemented with severity escalation
- 40 comprehensive tests passing (includes escalation tests)

### Phase 2: Create Data Quality Script ✓
- Created `validate_data_quality.py` with CLI interface
- Implemented filtering logic (quarter, status, all-active)
- Implemented console output (manager-grouped action items)
- Implemented Slack output using existing `notification_slack.j2` template
- Exception handling for signed-off initiatives
- Output directory management using `lib/output_utils.py`
- 20 comprehensive tests passing

### Phase 3: Integrate with Existing Scripts
**Status**: Deferred for future work
- Existing scripts continue to use inline validation
- Shared library available for future refactoring

### Phase 4: Documentation & Testing ✓
- README not updated (existing validation scripts already documented)
- Comprehensive test suite implemented (TDD approach)
- TODO.md updated with implementation notes

## Implementation Notes

### Output Formats
**Implemented**: Console, Slack
**Deferred**: Markdown, JSON (per user request)

### Console Output Format
Matches spec with following structure:
- Header with quarter and filter description
- Summary statistics (initiatives analyzed, issues found, exceptions skipped)
- Action items grouped by manager
- Each manager shows team, action count, initiative count
- Each initiative shows key, summary, status
- Each issue shows priority label (P1-P5) and description
- Footer with priority summary

### Slack Output Format
Uses existing `notification_slack.j2` template for consistency with other scripts.
Messages only generated for managers with valid Slack IDs configured.

### Deviations from Spec
1. **Markdown/JSON output**: Not implemented (user requested console + Slack only)
2. **Verbose mode**: Implemented but minimal output (shows data loading steps)
3. **Show-exempt flag**: Implemented but not yet functional (low priority)
4. **By-initiative grouping**: Not implemented (default by-manager is sufficient)

### Key Features
1. **Severity escalation**: Priorities increase as initiatives progress (P3→P1 for assignee, P2→P1 for epics)
2. **Status-aware validation**: Different rules for Proposed/Planned/In Progress
3. **Owner team exemption**: Pre-filtering approach (cleaner than runtime checks)
4. **Discovery initiative exemption**: Skips dependency and RAG checks
5. **Multi-objective support**: Comma-separated strategic objectives validated individually
6. **Exception handling**: Respects `initiative_exceptions.yaml` signed-off initiatives
7. **RAG-exempt teams**: Respects `teams_exempt_from_rag` configuration
8. **Excluded teams support**: Respects `teams_excluded_from_validation` configuration
9. **Test coverage**: 40 validation library tests + 22 main script tests

### Severity Escalation ✅ IMPLEMENTED

**Status**: Fully implemented as of 2026-04-11. All validation methods now calculate status-aware priorities.

**Implementation Details**:
- `_check_assignee()`: Returns P3 for Proposed, P1 for Planned/In Progress
- `_check_strategic_objective()`: Returns P1 for missing (universal check)
- `_check_teams_involved()`: Returns P1 for missing (universal check)
- `_check_missing_epics()`: Returns P2 for Proposed, P1 for Planned/In Progress
- `_check_rag_status()`: Returns P2 for Proposed, P1 for Planned
- Invalid strategic objective: Always P3 (universal check)

**Verification**: All 40 validation tests passing, including status-specific priority escalation tests:
- `test_check_assignee_for_proposed` (P3)
- `test_check_assignee_for_planned` (P1)
- `test_check_assignee_for_in_progress` (P1)
- `test_check_missing_epics_proposed_priority` (P2)
- `test_check_missing_epics_planned_priority` (P1)
- `test_check_missing_epics_in_progress_priority` (P1)
- `test_check_rag_status_for_proposed` (P2)
- `test_check_rag_status_for_planned` (P1)

## Non-Goals

- Not replacing existing scripts - complementing them
- Not changing data model or Jira fields
- Not implementing auto-fix capabilities (read-only validation)
- Not adding new validation rules beyond current script capabilities

---

## Appendix: Configuration File Structures

### A. `config/initiative_exceptions.yaml`

Manager-approved exceptions to skip from validation. Used by all validation scripts.

```yaml
# Format
signed_off_initiatives:
  - key: "INIT-XXXX"
    reason: "Why this initiative is exempt from validation"
    date: "YYYY-MM-DD"
    approved_by: "@Manager Name"

# Example
signed_off_initiatives:
  - key: "INIT-1301"
    reason: "PayEx and UN have to consult, nothing to build"
    date: "2026-03-31"
    approved_by: "@Kevin Platter"
```

**Usage**: Initiatives in this list are filtered out early in validation scripts (after loading, before any checks).

### B. `config/team_mappings.yaml`

Maps display names to project keys, defines manager contacts, and lists exempt teams.

```yaml
# Team display name → Project key mapping
team_mappings:
  "Core Banking": "CBNK"
  "Payments Experience": "PX"
  "Console": "CONSOLE"
  # ... more teams

# Manager contacts for notifications
team_managers:
  "CBNK":
    notion_handle: "@Joel Oughton"
    slack_id: "U02GE9CFXGX"
  "PX":
    notion_handle: "@Prabodh Kakodkar"
    slack_id: "U013XJUFPCG"
  # ... more teams

# Teams exempt from RAG status requirements
teams_exempt_from_rag:
  - "DOCS"

# Teams excluded from workload analysis
teams_excluded_from_workload_analysis:
  - "IT"
  - "Security Engineering"
  - "DevOps"
  # ... more teams

# Teams excluded from planning validation
teams_excluded_from_validation:
  - "IT"
  - "Security Engineering"
  # ... more teams

# Teams excluded from prioritisation validation
teams_excluded_from_prioritisation:
  - "DevOps"
  - "Security Engineering"
  # ... more teams

# Strategic objective mappings (historical → current)
strategic_objective_mappings:
  "2025_increase_soc_conversion": "2026_scale_ecom"
  "2024_1 Scale iGaming and FS": "2026_fuel_regulated"
  # ... more mappings
```

**Usage**:
- `team_mappings`: Match "Teams Involved" display names to epic project keys
- `team_managers`: Send notifications and tag managers in reports
- `teams_exempt_from_rag`: Skip RAG validation for these teams
- `teams_excluded_from_*`: Filter teams from specific validation scripts
- `strategic_objective_mappings`: Consolidate historical objectives in reports

### C. `config/jira_config.yaml`

Jira instance settings, custom field mappings, and validation rules.

```yaml
jira:
  instance: "yourcompany.atlassian.net/"

projects:
  initiatives: "INIT"
  teams:
    - "CBNK"
    - "PX"
    - "CONSOLE"
    # ... more project keys

custom_fields:
  initiatives:
    rag_status: "customfield_12111"
    strategic_objective: "customfield_12101"
    quarter: "customfield_12108"
    owner_team: "customfield_10300"
    teams_involved: "customfield_12521"

validation:
  strategic_objective:
    valid_values:
      - "2026_fuel_regulated"
      - "2026_network"
      - "2026_scale_ecom"
      - "engineering_pillars"
      - "beyond_strategic"
      # ... more valid values

output:
  directory: "./data"
  filename_pattern: "jira_extract_{timestamp}.json"
```

**Usage**:
- Extract custom fields from Jira initiatives
- Validate strategic objectives against allowed values
- Configure data extraction output location
