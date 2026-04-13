# Validation Library Developer Guide

Technical documentation for using the shared validation library (`lib/validation.py`) in scripts.

> **Business Context:** See [Validation Rules Specification](../specs/validation-rules.md) for the business rationale behind these checks.

## Overview

The validation library provides reusable, status-aware validation logic for checking initiative data quality. All validation scripts (`check_planning.py`, `check_quality.py`, `check_priorities.py`, `assess_workload.py`) use this library to ensure consistent validation rules.

**Key Features:**
- **Status-aware validation** - Rules escalate based on initiative status
- **Configurable checks** - Enable/disable specific validation types
- **Structured issues** - Consistent issue format with priority, description, and metadata
- **Special case handling** - Discovery initiatives, owner teams, RAG-exempt teams

## Quick Start

### Basic Usage

```python
from lib.validation import InitiativeValidator, ValidationConfig, Priority

# Create configuration
config = ValidationConfig(
    check_assignee=True,
    check_strategic_objective=True,
    check_missing_epics=True,
    check_rag_status=True,
    valid_strategic_objectives=["2026_fuel_regulated", "engineering_pillars"],
)

# Create validator
validator = InitiativeValidator(config)

# Validate an initiative
initiative = {
    "key": "INIT-123",
    "summary": "My Initiative",
    "status": "Planned",
    "owner_team": "PLATFORM",
    "assignee": None,  # Missing!
    "strategic_objective": "2026_fuel_regulated",
    # ... other fields
}

issues = validator.validate(initiative)

# Process issues
for issue in issues:
    print(f"{issue.priority.name} ({issue.type}): {issue.description}")
    # Output: CRITICAL (missing_assignee): Missing assignee - Assign DRI
```

### Integration Pattern

Typical integration in a script:

```python
from lib.validation import InitiativeValidator, ValidationConfig, ValidationIssue
from typing import List, Dict

def load_config() -> ValidationConfig:
    """Load validation config from jira_config.yaml."""
    with open("config/jira_config.yaml") as f:
        config = yaml.safe_load(f)

    return ValidationConfig(
        valid_strategic_objectives=config.get("validation", {})
            .get("strategic_objective", {})
            .get("valid_values", []),
        rag_exempt_teams=config.get("teams_exempt_from_rag", []),
    )

def validate_initiatives(initiatives: List[Dict]) -> Dict[str, List[ValidationIssue]]:
    """Validate all initiatives and group issues by initiative key."""
    config = load_config()
    validator = InitiativeValidator(config)

    issues_by_initiative = {}

    for initiative in initiatives:
        issues = validator.validate(initiative)
        if issues:
            issues_by_initiative[initiative["key"]] = issues

    return issues_by_initiative
```

## API Reference

### Classes

#### `ValidationConfig`

Configuration for validation rules.

**Attributes:**
```python
@dataclass
class ValidationConfig:
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
```

**Field Descriptions:**
- `check_assignee` - Validate assignee presence (status-aware priority)
- `check_strategic_objective` - Validate strategic objective presence and validity
- `check_teams_involved` - Validate teams_involved field presence
- `check_missing_epics` - Validate epic creation for teams_involved
- `check_rag_status` - Validate RAG status on epics (Proposed/Planned only)
- `owner_team_exempt` - Exempt owner team from epic/RAG checks (recommended: True)
- `skip_discovery` - Skip epic/RAG checks for `[Discovery]` initiatives (recommended: True)
- `valid_strategic_objectives` - List of approved strategic objectives for validation
- `team_mappings` - Dict mapping friendly names to project keys (optional)
- `rag_exempt_teams` - Teams exempt from RAG status requirements

#### `ValidationIssue`

Represents a single data quality issue.

**Attributes:**
```python
@dataclass
class ValidationIssue:
    type: str                           # 'missing_owner', 'missing_epic', etc.
    priority: Priority                  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    description: str                    # Human-readable description
    initiative_key: str                 # e.g., "INIT-123"
    initiative_summary: str             # Initiative title
    initiative_status: str              # "Proposed", "Planned", etc.
    owner_team: Optional[str]           # Owner team (if known)
    team_affected: Optional[str] = None # For team-specific issues
    epic_key: Optional[str] = None      # For epic-specific issues
    current_value: Optional[str] = None # For invalid value issues
    expected_value: Optional[str] = None
```

**Issue Types:**
- `missing_owner_team` - Initiative has no owner team
- `missing_assignee` - Initiative has no assignee
- `missing_strategic_objective` - Initiative has no strategic objective
- `invalid_strategic_objective` - Strategic objective not in approved list
- `missing_teams_involved` - Initiative has no teams_involved
- `missing_epic` - Team in teams_involved has no epic
- `missing_rag_status` - Epic has no RAG status

#### `Priority`

Enum for issue priority levels.

```python
class Priority(IntEnum):
    CRITICAL = 1  # Blocks everything (missing owner)
    HIGH = 2      # Blocks planning (missing assignee for Planned)
    MEDIUM = 3    # Data correction (invalid values)
    LOW = 4       # Missing dependencies (epics)
    INFO = 5      # Missing signals (RAG status)
```

See [Validation Rules](../specs/validation-rules.md#priority-level-meanings) for business meanings.

#### `InitiativeValidator`

Validates initiatives for data quality issues.

**Constructor:**
```python
def __init__(self, config: ValidationConfig):
    """Initialize validator with configuration."""
```

**Methods:**

##### `validate(initiative: Dict) -> List[ValidationIssue]`

Validate an initiative and return list of issues.

Applies status-aware validation rules:
- **All statuses:** owner team, strategic objective, teams_involved
- **Proposed/Planned/In Progress:** assignee, missing epics
- **Proposed/Planned only:** RAG status

**Args:**
- `initiative` - Initiative dictionary from JSON extract

**Returns:**
- List of `ValidationIssue` objects (empty if no issues)

**Example:**
```python
validator = InitiativeValidator(config)
issues = validator.validate(initiative)

if issues:
    print(f"Found {len(issues)} issues:")
    for issue in issues:
        print(f"  {issue.priority.name}: {issue.description}")
```

## Status-Aware Validation

The library implements different validation rules based on initiative status:

| Status | Checks Applied |
|--------|---------------|
| **All** | owner_team, strategic_objective, teams_involved |
| **Proposed** | + assignee (P3), missing_epics (P2), RAG (P2) |
| **Planned** | + assignee (P1), missing_epics (P1), RAG (P1) |
| **In Progress** | + assignee (P1), missing_epics (P1) |
| **Done/Cancelled** | Only universal checks |

**Note:** Priority escalates for assignee and epic checks as status progresses.

See [Validation Rules](../specs/validation-rules.md#status-aware-validation-rules) for detailed business logic.

## Special Cases

### Discovery Initiatives

Initiatives with `[Discovery]` prefix in summary skip epic and RAG validation:

```python
initiative = {
    "summary": "[Discovery] Research user authentication options",
    "teams_involved": ["PLATFORM", "SECURITY"],
    # No epics created yet - this is OK for Discovery
}

config = ValidationConfig(skip_discovery=True)
validator = InitiativeValidator(config)
issues = validator.validate(initiative)
# No "missing_epic" issues for Discovery initiatives
```

### Owner Team Exemption

Owner team is automatically filtered from epic/RAG checks:

```python
initiative = {
    "owner_team": "PLATFORM",
    "teams_involved": ["PLATFORM", "SECURITY"],
    "contributing_teams": [
        {"team": "PLATFORM", "epics": []},  # OK - owner team
        {"team": "SECURITY", "epics": []},   # NOT OK - missing epic
    ]
}

config = ValidationConfig(owner_team_exempt=True)
validator = InitiativeValidator(config)
issues = validator.validate(initiative)
# Only SECURITY flagged for missing epic, not PLATFORM
```

### RAG-Exempt Teams

Configure teams that don't need RAG status:

```python
config = ValidationConfig(
    rag_exempt_teams=["DOCS", "UX_RESEARCH"]
)

initiative = {
    "status": "Planned",
    "teams_involved": ["PLATFORM", "DOCS"],
    "contributing_teams": [
        {"team": "PLATFORM", "epics": [{"key": "PLAT-1", "rag_status": None}]},
        {"team": "DOCS", "epics": [{"key": "DOCS-1", "rag_status": None}]},
    ]
}

validator = InitiativeValidator(config)
issues = validator.validate(initiative)
# Only PLATFORM flagged for missing RAG, not DOCS
```

## Testing Patterns

### Unit Testing Validators

```python
import pytest
from lib.validation import InitiativeValidator, ValidationConfig, Priority

def test_missing_assignee_priority_escalation():
    """Test that assignee priority escalates with status."""
    config = ValidationConfig(check_assignee=True)
    validator = InitiativeValidator(config)

    # Proposed - lower priority
    initiative = {"status": "Proposed", "assignee": None, ...}
    issues = validator.validate(initiative)
    assert issues[0].priority == Priority.MEDIUM  # P3

    # Planned - higher priority
    initiative["status"] = "Planned"
    issues = validator.validate(initiative)
    assert issues[0].priority == Priority.CRITICAL  # P1

def test_discovery_initiative_exemption():
    """Test that Discovery initiatives skip epic checks."""
    config = ValidationConfig(skip_discovery=True)
    validator = InitiativeValidator(config)

    initiative = {
        "summary": "[Discovery] Research options",
        "teams_involved": ["TEAM1", "TEAM2"],
        "contributing_teams": [
            {"team": "TEAM1", "epics": []},
            {"team": "TEAM2", "epics": []},
        ],
        ...
    }

    issues = validator.validate(initiative)
    epic_issues = [i for i in issues if i.type == "missing_epic"]
    assert len(epic_issues) == 0  # No epic issues for Discovery
```

### Integration Testing

```python
def test_validate_full_dataset():
    """Test validation against real dataset."""
    # Load config
    config = ValidationConfig(
        valid_strategic_objectives=["2026_fuel_regulated"],
        rag_exempt_teams=["DOCS"],
    )
    validator = InitiativeValidator(config)

    # Load test data
    with open("tests/fixtures/initiatives.json") as f:
        initiatives = json.load(f)

    # Validate all
    all_issues = []
    for initiative in initiatives:
        issues = validator.validate(initiative)
        all_issues.extend(issues)

    # Assertions
    assert len(all_issues) > 0
    assert all(isinstance(i.priority, Priority) for i in all_issues)
```

## Extending the Library

### Adding a New Validation Check

1. **Add issue type to `ValidationIssue`:**
   ```python
   # No changes needed - type is a string field
   ```

2. **Add config flag to `ValidationConfig`:**
   ```python
   @dataclass
   class ValidationConfig:
       check_new_field: bool = True  # Add flag
   ```

3. **Implement check method in `InitiativeValidator`:**
   ```python
   def _check_new_field(self, initiative: Dict) -> List[ValidationIssue]:
       """Check for new field validation."""
       if not self.config.check_new_field:
           return []

       if not initiative.get("new_field"):
           return [ValidationIssue(
               type="missing_new_field",
               priority=Priority.HIGH,
               description="Missing new field - Add value",
               initiative_key=initiative.get('key', ''),
               initiative_summary=initiative.get('summary', ''),
               initiative_status=initiative.get('status', ''),
               owner_team=initiative.get('owner_team'),
           )]

       return []
   ```

4. **Call check in `validate()` method:**
   ```python
   def validate(self, initiative: Dict) -> List[ValidationIssue]:
       issues = []

       # Existing checks...

       if self.config.check_new_field:
           issues.extend(self._check_new_field(initiative))

       return issues
   ```

5. **Write tests:**
   ```python
   def test_new_field_validation():
       config = ValidationConfig(check_new_field=True)
       validator = InitiativeValidator(config)

       initiative = {"new_field": None, ...}
       issues = validator.validate(initiative)

       assert any(i.type == "missing_new_field" for i in issues)
   ```

## Related Documentation

- [Validation Rules](../specs/validation-rules.md) - Business validation rules and rationale
- [Configuration Reference](configuration.md) - Configure validation behavior
- [Validate Data Quality](../scripts/validate-data-quality.md) - Script using this library
- [Validate Planning](../scripts/validate-planning.md) - Script using this library
