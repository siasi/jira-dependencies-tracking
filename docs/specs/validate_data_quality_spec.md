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

Different validation rules apply based on initiative status:

### All Statuses (Universal Checks)

| Check | Priority | Description |
|-------|----------|-------------|
| Missing owner_team | P1 | Blocks everything - initiative needs owner |
| Missing strategic_objective | P2 | Blocks planning - initiative needs strategic alignment |
| Invalid strategic_objective | P3 | Wrong value - needs correction |
| Missing teams_involved | P4 | Data quality issue - should list contributing teams |

### Proposed Status (Planning Readiness)

Additional checks beyond universal:

| Check | Priority | Description |
|-------|----------|-------------|
| Missing assignee | P2 | Blocks planning - needs DRI |
| Missing epics from teams_involved | P4 | Teams need to create epics to commit |
| Missing RAG status | P5 | Teams need to signal commitment level |
| Epic count vs teams_involved mismatch | P4 | Expected teams missing epics |

**Rationale**: Proposed initiatives are being evaluated for readiness to move to Planned status. All dependency and commitment signals (RAG) are relevant.

### Planned Status (Current Quarter Commitment)

Additional checks beyond universal:

| Check | Priority | Description |
|-------|----------|-------------|
| Missing assignee | P2 | Should have DRI by now |
| Missing epics from teams_involved | P4 | Teams should have created epics |
| Missing RAG status | P5 | Teams should be tracking health |
| Epic count vs teams_involved mismatch | P4 | Expected teams missing epics |

**Rationale**: Planned initiatives are committed for the quarter. Teams should have epics and be tracking RAG status.

### In Progress Status (Active Work)

Additional checks beyond universal:

| Check | Priority | Description |
|-------|----------|-------------|
| Missing assignee | P2 | Active work must have DRI |
| Missing epics from teams_involved | P4 | Contributing teams should have epics |
| Epic count vs teams_involved mismatch | P4 | Expected teams missing epics |

**Rationale**: In Progress initiatives are actively being worked on. RAG status is NOT validated because:
- Work is happening, RAG is less relevant for tracking commitment
- Focus is on execution, not planning signals
- User explicitly stated RAG is not relevant for In Progress

### Done/Cancelled Status (Cleanup Only)

If `--all-active` or explicit `--status Done` used:

| Check | Priority | Description |
|-------|----------|-------------|
| Missing strategic_objective | P2 | Historical data completeness |
| Epics not marked Done | INFO | Cleanup opportunity |
| RAG status on Done epics | INFO | Cleanup opportunity |

**Rationale**: Only check if explicitly requested. Focus on data completeness for historical analysis.

## Validation Logic - Special Cases

### Owner Team Exemption

**Rule**: Owner team is exempt from creating epics and setting RAG status

**Implementation**:
```python
# When checking for missing epics or missing RAG:
# Skip if team_project_key matches owner_team's project_key
if is_owner_team(team_key, owner_team, team_mappings):
    continue  # Owner team exempt
```

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
    # Report which specific objectives are invalid
```

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

Jane Smith (@jane.smith) - Platform Team
  8 action items across 4 initiatives

  INIT-456: Payment Gateway Integration
    Status: Planned | Owner: Platform | Quarter: 26 Q2
    P2 ⚠️  Missing assignee - Assign initiative owner
    P4 ⚠️  Missing epic from Mobile team - Create epic

  INIT-789: Customer Portal Redesign
    Status: In Progress | Owner: Platform | Quarter: 26 Q2
    P4 ⚠️  Missing epic from Frontend team - Create epic
    P4 ⚠️  Missing epic from API team - Create epic

  INIT-890: Analytics Dashboard
    Status: Planned | Owner: Platform | Quarter: 26 Q2
    P3 ⚠️  Invalid strategic objective: "customer_experiance" - Fix typo
    P5 ⚠️  Missing RAG status on EPIC-123 (Mobile team) - Set RAG

  INIT-901: Search Optimization
    Status: In Progress | Owner: Platform | Quarter: 26 Q2
    P2 ⚠️  Missing strategic objective - Set strategic objective

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

1. **RAG validation for In Progress**: Confirmed - NOT validated (user specified)
2. **Multi-objective format**: Comma-separated (current implementation)
3. **Owner team creates epic?**: No - owner team exempt (current implementation)
4. **Discovery initiative handling**: Exempt from dependency checks (current implementation)
5. **Default output format**: Console (with options for markdown/JSON/Slack)
6. **Validation priority levels**: P1-P5 as defined above

## Non-Goals

- Not replacing existing scripts - complementing them
- Not changing data model or Jira fields
- Not implementing auto-fix capabilities (read-only validation)
- Not adding new validation rules beyond current script capabilities
