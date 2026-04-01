---
title: Add Initiative Sign-Off Exceptions Feature
type: feat
status: completed
date: 2026-03-31
origin: docs/brainstorms/2026-03-31-initiative-sign-off-exceptions-brainstorm.md
---

# Add Initiative Sign-Off Exceptions Feature

## Overview

Implement a configuration-based system to manage initiatives that have known inconsistencies but have been explicitly approved by managers. These initiatives will be completely excluded from validation reports to avoid re-iterating action items for already-resolved situations.

**Example use case:** An initiative lists a team in "Teams Impacted" but has no corresponding epic because the team's contribution is consultative (awareness-only, not building). Manager has approved this as intentional, so validation should skip it entirely.

## Problem Statement / Motivation

Currently, `validate_planning.py` flags all initiatives with inconsistencies (missing epics, missing RAG status, RED/YELLOW epics, etc.) in validation reports. However, some inconsistencies are **intentional and manager-approved**:

- Team listed in "Teams Impacted" for awareness only (no epic needed)
- Special cross-team arrangements where standard validation rules don't apply
- Edge cases where manager has explicitly signed off on the current state

**Problem:** These initiatives appear in every validation report, creating noise and redundant action items for managers who have already approved the situation.

**Motivation:** Provide a way to document manager sign-off and completely exclude these initiatives from validation reports, allowing reports to focus on actual issues requiring attention.

## Proposed Solution

Implement **Approach A (Early Filtering)** from brainstorm (see brainstorm: docs/brainstorms/2026-03-31-initiative-sign-off-exceptions-brainstorm.md):

1. **Create new config file** `config/initiative_exceptions.yaml` with structured data:
   ```yaml
   signed_off_initiatives:
     - key: "INIT-1234"
       reason: "Team X is consultative only, no epic needed"
       date: "2026-03-31"  # optional
       approved_by: "@Manager Name"  # optional
   ```

2. **Load config at script startup** using existing config loading patterns from validate_planning.py

3. **Filter initiatives early** (after quarter filter, before validation) to completely exclude signed-off initiatives

4. **Complete hiding** - signed-off initiatives never appear in any report section

## Technical Considerations

### Architecture Impacts

- **New config file:** `config/initiative_exceptions.yaml` (separate from jira_config.yaml and team_mappings.yaml)
- **New loader function:** `_load_signed_off_initiatives()` in validate_planning.py (follows existing pattern)
- **Filtering logic:** Insert after line 1020 (quarter filter), before line 1027 (team exclusion filter)
- **Example config:** `config/initiative_exceptions.yaml.example` for documentation

### Performance Implications

- **Negligible impact:** Single O(n) filter pass at startup
- **Efficient lookup:** Use Set[str] for O(1) membership checks
- **No validation overhead:** Signed-off initiatives skip all validation logic

### Security Considerations

- **Use `yaml.safe_load()`** (not `yaml.load()`) to prevent code injection
- **No sensitive data:** Config contains initiative keys and reasons (both non-sensitive)
- **File permissions:** Same as other config files (standard read permissions)

### Error Handling Strategy

Following CLAUDE.md guidance and existing patterns:

**Fail Fast (Config Errors - Startup):**
- Invalid YAML syntax → Raise `ConfigError` with clear message
- Missing required fields (key, reason) → Raise `ConfigError` with field name
- Malformed structure → Raise `ConfigError`

**Degrade Gracefully (Optional Feature):**
- File doesn't exist → Return empty set (feature is optional, continue normally)
- Empty `signed_off_initiatives` list → Return empty set
- Optional fields (date, approved_by) missing → Allow, don't validate

## System-Wide Impact

### Interaction Graph

No callbacks, middleware, or observers involved. Pure data filtering:
1. **Load config** → `_load_signed_off_initiatives()` returns Set[str]
2. **Filter data** → List comprehension excludes signed-off initiatives
3. **Validate remaining** → Standard validation logic runs on filtered list

### Error Propagation

- **ConfigError from loader** → Propagates to CLI → Displays error → sys.exit(2)
- **FileNotFoundError** → Caught in loader → Returns empty set → No error
- **YAMLError** → Wrapped in ConfigError → Propagates to CLI

### State Lifecycle Risks

None. This is a pure filtering feature with no state persistence or external service calls.

### API Surface Parity

Single entry point: `validate_initiative_status()` function in validate_planning.py. No parallel interfaces.

### Integration Test Scenarios

1. **End-to-end filtering:** Initiative in sign-off list → Does not appear in any result category
2. **Mixed initiatives:** Some signed off, some not → Only non-signed-off initiatives validated
3. **Missing config file:** No config file exists → All initiatives validated normally
4. **Malformed YAML:** Invalid syntax → Raises clear ConfigError at startup
5. **Missing required fields:** Config missing 'key' or 'reason' → Raises clear ConfigError

## Acceptance Criteria

### Core Functionality

- [x] Load `config/initiative_exceptions.yaml` at script startup
- [x] Filter out signed-off initiatives before validation begins
- [ ] Signed-off initiatives do NOT appear in any report section:
  - [ ] Not in "Fix Data Quality"
  - [ ] Not in "Address Commitment Blockers"
  - [ ] Not in "Ready to Move to Planned"
  - [ ] Not in "No/Low Confidence"
  - [ ] Not in "Planned Initiatives with Issues"

### Config File Requirements

- [x] YAML structure: top-level `signed_off_initiatives` key with list of dicts
- [x] Required fields per item: `key` (initiative ID), `reason` (explanation)
- [x] Optional fields per item: `date` (ISO format), `approved_by` (manager handle)
- [x] Create example file: `config/initiative_exceptions.yaml.example` with documentation

### Error Handling

- [x] Missing config file → Degrade gracefully (return empty set)
- [x] Invalid YAML syntax → Raise ConfigError with clear message
- [x] Missing required field → Raise ConfigError with field name
- [x] Use `yaml.safe_load()` for security

### Testing Requirements

- [x] Test loading valid config with all fields
- [x] Test loading config with only required fields (key, reason)
- [x] Test missing config file (graceful degradation)
- [ ] Test invalid YAML syntax (ConfigError raised)
- [ ] Test missing 'key' field (ConfigError raised)
- [ ] Test missing 'reason' field (ConfigError raised)
- [x] Test end-to-end filtering (initiative not in results)
- [x] Test mixed scenario (some signed off, some not)

### Documentation

- [x] Update README.md with new section on initiative exceptions
- [x] Document config file format and purpose
- [x] Explain when to use this feature
- [x] Add example use case

## Success Metrics

**Immediate success:**
- Signed-off initiatives disappear from validation reports
- No action items generated for manager-approved inconsistencies
- Clear audit trail in config file (reason, date, approved_by)

**Long-term success:**
- Reduced noise in validation reports
- Faster report review for managers (focus on real issues)
- Clear documentation of intentional exceptions

## Dependencies & Risks

### Dependencies

- Existing config loading infrastructure (validate_planning.py functions)
- `yaml` library (already in requirements.txt)
- `pytest` for testing (already in dev dependencies)

### Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Config file accidentally excludes too many initiatives | High - Important issues missed | Require `reason` field for audit trail; recommend periodic config review |
| Stale sign-offs (initiative resolved but still in config) | Low - Noise reduction benefit lost | Document config review in README; consider future warning for old dates |
| YAML syntax errors break script | Medium - Script won't run | Fail fast with clear error message; provide example config |
| Users don't know feature exists | Low - Feature unused | Document in README; mention in validation output if file exists |

## Implementation Plan

### Phase 1: Core Implementation

**Files to modify:**

1. **validate_planning.py**
   - Add `_load_signed_off_initiatives() -> Set[str]` function after line 476
   - Add filtering logic after line 1020 (after quarter filter)
   - Import Set from typing module

2. **config/initiative_exceptions.yaml** (NEW)
   - Create new config file structure

3. **config/initiative_exceptions.yaml.example** (NEW)
   - Create example with documentation comments

**Implementation steps:**

```python
# Step 1: Add loader function in validate_planning.py
def _load_signed_off_initiatives() -> Set[str]:
    """Load list of initiative keys that have manager sign-off.

    Signed-off initiatives are completely excluded from validation reports
    because managers have explicitly approved their current state despite
    any inconsistencies.

    Returns:
        Set of initiative keys to skip validation (e.g., {"INIT-1234"})
    """
    exceptions_file = Path(__file__).parent / 'config' / 'initiative_exceptions.yaml'
    if not exceptions_file.exists():
        return set()

    try:
        with open(exceptions_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            signed_off = data.get('signed_off_initiatives', [])

            # Validate structure
            keys = set()
            for item in signed_off:
                if not isinstance(item, dict):
                    continue  # Skip malformed items silently
                if 'key' not in item:
                    continue  # Skip items without key
                keys.add(item['key'])

            return keys
    except yaml.YAMLError as e:
        # Invalid YAML is a config error (fail fast)
        click.echo(click.style(
            f"Error: Invalid YAML in initiative_exceptions.yaml: {e}",
            fg='red'
        ), err=True)
        sys.exit(2)
    except Exception as e:
        # Unexpected errors are fatal
        click.echo(click.style(
            f"Error: Could not load initiative_exceptions.yaml: {e}",
            fg='red'
        ), err=True)
        sys.exit(2)

# Step 2: Add filtering in validate_initiative_status() function
def validate_initiative_status(json_file: Path, quarter: str) -> ValidationResult:
    # ... existing code ...

    # Filter by quarter (existing code around line 1015-1020)
    all_initiatives = [
        init for init in all_initiatives_unfiltered
        if init.get('quarter') == quarter
    ]

    # NEW: Filter out signed-off initiatives
    signed_off_keys = _load_signed_off_initiatives()
    if signed_off_keys:
        all_initiatives = [
            init for init in all_initiatives
            if init['key'] not in signed_off_keys
        ]

    # Continue with existing team exclusion logic...
    excluded_teams = _load_teams_excluded_from_analysis()
    # ... rest of function ...
```

### Phase 2: Testing

**File to modify:** tests/test_validate_planning.py

**Add tests after line 1715 (new section):**

```python
# Test config loading
def test_load_signed_off_initiatives_valid(tmp_path):
    """Test loading valid exception config."""
    config_data = {
        'signed_off_initiatives': [
            {'key': 'INIT-1234', 'reason': 'Manager approved'},
            {'key': 'INIT-5678', 'reason': 'Special case', 'date': '2026-03-31'}
        ]
    }
    config_file = tmp_path / 'initiative_exceptions.yaml'
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f)

    # Temporarily point to test config
    # ... implementation ...

    keys = _load_signed_off_initiatives()
    assert keys == {'INIT-1234', 'INIT-5678'}

def test_load_signed_off_initiatives_missing_file():
    """Test graceful handling when file doesn't exist."""
    keys = _load_signed_off_initiatives()
    assert keys == set()

def test_load_signed_off_initiatives_invalid_yaml(tmp_path):
    """Test error handling for malformed YAML."""
    config_file = tmp_path / 'initiative_exceptions.yaml'
    config_file.write_text("invalid: yaml: syntax: [")

    # Should exit with error code
    # ... implementation ...

# Test end-to-end filtering
def test_signed_off_initiative_filtered_out(tmp_path):
    """Test that signed-off initiatives are completely filtered out."""
    # Create config with signed-off initiative
    config_data = {
        'signed_off_initiatives': [
            {'key': 'INIT-1234', 'reason': 'Manager approved'}
        ]
    }

    # Create test data with initiative
    test_data = {
        'initiatives': [
            {
                'key': 'INIT-1234',
                'summary': 'Signed off initiative',
                'status': 'Proposed',
                'quarter': '26 Q2',
                'teams_involved': ['Team A', 'Team B'],
                'epics': []  # Missing epic - would normally trigger validation
            }
        ],
        'epics': []
    }

    json_file = tmp_path / 'test.json'
    json_file.write_text(json.dumps(test_data))

    result = validate_initiative_status(json_file, quarter="26 Q2")

    # Initiative should not appear in ANY result category
    assert len(result.dependency_mapping) == 0
    assert len(result.missing_rag_status) == 0
    assert len(result.red_epics) == 0
    assert len(result.yellow_epics) == 0
    assert len(result.missing_assignee) == 0
    assert len(result.ready_to_plan) == 0
    assert len(result.low_confidence_completion) == 0
    assert len(result.planned_with_issues) == 0

def test_mixed_signed_off_and_normal_initiatives(tmp_path):
    """Test that only signed-off initiatives are filtered."""
    # Config with one signed-off initiative
    config_data = {
        'signed_off_initiatives': [
            {'key': 'INIT-1234', 'reason': 'Approved'}
        ]
    }

    # Test data with two initiatives
    test_data = {
        'initiatives': [
            {
                'key': 'INIT-1234',
                'summary': 'Signed off',
                'status': 'Proposed',
                'quarter': '26 Q2',
                'teams_involved': ['Team A', 'Team B'],
                'epics': []  # Missing epic
            },
            {
                'key': 'INIT-5678',
                'summary': 'Normal',
                'status': 'Proposed',
                'quarter': '26 Q2',
                'teams_involved': ['Team A', 'Team B'],
                'epics': []  # Missing epic - should trigger validation
            }
        ],
        'epics': []
    }

    json_file = tmp_path / 'test.json'
    json_file.write_text(json.dumps(test_data))

    result = validate_initiative_status(json_file, quarter="26 Q2")

    # INIT-1234 should be filtered out
    # INIT-5678 should appear in dependency_mapping
    assert len(result.dependency_mapping) == 1
    assert result.dependency_mapping[0]['key'] == 'INIT-5678'
```

### Phase 3: Configuration Files

**config/initiative_exceptions.yaml.example:**

```yaml
# Initiative Sign-Off Exceptions
#
# This file allows you to exclude specific initiatives from validation reports.
# Use this when managers have explicitly approved an initiative's current state
# despite inconsistencies (e.g., missing epics, missing RAG status).
#
# Common use cases:
# - Team listed in "Teams Impacted" for awareness only (no epic needed)
# - Special cross-team arrangements where standard rules don't apply
# - Edge cases with explicit manager sign-off
#
# Format:
# signed_off_initiatives:
#   - key: "INIT-XXXX"           # Required: Jira initiative key
#     reason: "Explanation"       # Required: Why this is signed off
#     date: "YYYY-MM-DD"          # Optional: When approved
#     approved_by: "@Manager"     # Optional: Who approved it
#
# Example:
# signed_off_initiatives:
#   - key: "INIT-1234"
#     reason: "Team X is consultative only, no epic needed"
#     date: "2026-03-31"
#     approved_by: "@Jane Smith"
#
#   - key: "INIT-5678"
#     reason: "Special cross-team arrangement confirmed"
#     date: "2026-03-15"
#     approved_by: "@John Doe"
#
# After adding initiatives here, they will be completely excluded from
# validation reports. Review this file periodically to remove stale entries.

signed_off_initiatives: []
```

**config/initiative_exceptions.yaml:**

```yaml
# See config/initiative_exceptions.yaml.example for documentation
signed_off_initiatives: []
```

### Phase 4: Documentation

**Update README.md** (add new section after line 530):

```markdown
### Optional: Initiative Sign-Off Exceptions

Some initiatives have intentional inconsistencies that managers have explicitly approved. To exclude these from validation reports:

1. Edit `config/initiative_exceptions.yaml`:
   ```yaml
   signed_off_initiatives:
     - key: "INIT-1234"
       reason: "Team X is consultative only, no epic needed"
       date: "2026-03-31"
       approved_by: "@Manager Name"
   ```

2. Run validation - signed-off initiatives will be completely hidden:
   ```bash
   python validate_planning.py --quarter "26 Q2"
   ```

**When to use this:**
- Team listed for awareness only (no epic needed)
- Special cross-team arrangements
- Manager has explicitly approved the current state

**Required fields:**
- `key`: Initiative Jira key (e.g., "INIT-1234")
- `reason`: Explanation of why this is signed off

**Optional fields:**
- `date`: When approved (ISO format: "YYYY-MM-DD")
- `approved_by`: Manager who approved (e.g., "@Jane Smith")

**Important:** Review this file periodically to remove resolved initiatives.
```

## Open Questions

1. **Should we add a report summary showing what was signed off?**
   - **Decision for MVP:** No. Keep reports focused on action items. Users can check config file if needed.
   - **Future consideration:** Add optional `--verbose` flag to show signed-off count.

2. **Should we validate that signed-off initiative keys exist in Jira?**
   - **Decision for MVP:** No. This would require Jira API calls and complicate logic.
   - **Future consideration:** Add validation script to check for stale entries.

3. **Should signed-off initiatives appear in --verbose output?**
   - **Decision for MVP:** No. Keep implementation simple.
   - **Future consideration:** Add debug logging if requested.

4. **Should this integrate with existing exemption systems?**
   - **Decision:** Keep separate. Different exemption levels:
     - `teams_exempt_from_rag`: Skip RAG checks only
     - `teams_excluded_from_analysis`: Filter by team ownership
     - `signed_off_initiatives`: Skip ALL checks for specific initiatives
   - Each serves a distinct purpose.

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-03-31-initiative-sign-off-exceptions-brainstorm.md](../brainstorms/2026-03-31-initiative-sign-off-exceptions-brainstorm.md)
  - **Key decisions carried forward:**
    1. Approach A (Early Filtering) - Filter at load time, not during validation
    2. Config file: `config/initiative_exceptions.yaml` (separate from other configs)
    3. Complete hiding - Never show in any report section
    4. Required fields: key, reason (optional: date, approved_by)

### Internal References

- **Config loading patterns:** validate_planning.py:358-476 (existing loader functions)
- **Filtering location:** validate_planning.py:1015-1053 (quarter filter and team exclusion)
- **Error handling:** src/config.py:80-128 (ConfigError patterns)
- **Existing exemptions:** config/team_mappings.yaml:72-87 (teams_exempt_from_rag, teams_excluded_from_analysis)
- **Test patterns:** tests/test_validate_planning.py:704-1715 (config loading and filtering tests)

### Institutional Learnings

- **CLI Error Handling:** docs/solutions/code-quality/cli-error-handling-duplication.md - Use centralized error handlers
- **Config Loading Pattern:** src/config.py - Fail fast for config errors, degrade gracefully for optional features
- **YAML Security:** Always use `yaml.safe_load()`, never `yaml.load()`
- **Testing Patterns:** tests/test_config.py - Test valid config, missing file, invalid YAML, missing fields

### Related Work

- **Initiative Status Validation:** docs/plans/2026-03-21-001-feat-initiative-status-validation-plan.md - Established filtering approach
- **CLAUDE.md Guidelines:** Lines 47-51 - Error handling strategy (fail fast vs degrade gracefully)
