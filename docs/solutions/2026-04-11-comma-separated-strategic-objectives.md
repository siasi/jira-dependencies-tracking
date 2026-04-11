# Comma-Separated Strategic Objectives Support

**Date**: 2026-04-11
**Status**: Completed
**Related TODO**: Multi-Objective Strategic Objective Support

## Summary

Implemented support for comma-separated strategic objectives in `validate_planning.py` to allow initiatives to have multiple strategic objectives validated individually, matching the behavior already present in `analyze_workload.py`.

## Problem

The `validate_planning.py` script was treating strategic objectives as a single string, which meant initiatives with multiple comma-separated objectives (e.g., "2026_fuel_regulated, 2026_network") would be flagged as invalid, even if all individual objectives were valid.

### Before
```python
# Old code (lines 92-103)
strategic_objective = initiative.get('strategic_objective')
if valid_objectives and strategic_objective not in valid_objectives:
    issues.append({
        'type': 'invalid_strategic_objective',
        'current_value': strategic_objective
    })
```

**Problem**: `"2026_fuel_regulated, 2026_network"` is not in the valid_objectives list as a single string, so it gets flagged as invalid, even though both "2026_fuel_regulated" and "2026_network" are individually valid.

## Solution

Updated `validate_planning.py` to split comma-separated strategic objectives and validate each one individually, following the same pattern as `analyze_workload.py`.

### Implementation

**File**: `validate_planning.py` (lines 92-107)

```python
# Check strategic objective (missing or invalid)
strategic_objective = initiative.get('strategic_objective')
if not strategic_objective or (isinstance(strategic_objective, str) and not strategic_objective.strip()):
    issues.append({'type': 'missing_strategic_objective'})
else:
    # Check if strategic objective is valid
    # Split by comma to handle multiple objectives (e.g., "objective1, objective2")
    valid_objectives = _load_valid_strategic_objectives()
    if valid_objectives:
        objectives = [obj.strip() for obj in strategic_objective.split(',')]
        invalid_objectives = [obj for obj in objectives if obj not in valid_objectives]

        if invalid_objectives:
            issues.append({
                'type': 'invalid_strategic_objective',
                'current_value': strategic_objective,
                'invalid_values': invalid_objectives
            })
```

### Key Changes

1. **Split by comma**: `strategic_objective.split(',')`
2. **Strip whitespace**: `[obj.strip() for obj in ...]` - handles extra spaces around commas
3. **Validate individually**: Check each objective against `valid_objectives`
4. **Report invalid ones**: Track which specific objectives are invalid in `invalid_values` field

## Behavior

### Single Objective (existing behavior maintained)
- `"2026_fuel_regulated"` → ✅ Valid (if in valid_objectives)
- `"invalid_objective"` → ❌ Invalid

### Multiple Objectives (new behavior)
- `"2026_fuel_regulated, 2026_network"` → ✅ Valid (both in valid_objectives)
- `"2026_fuel_regulated, invalid_obj"` → ❌ Invalid (reports `invalid_obj`)
- `"invalid1, invalid2"` → ❌ Invalid (reports both)

### Whitespace Handling
- `"  2026_fuel_regulated  ,  2026_network  "` → ✅ Valid (whitespace stripped)

## Testing

Added comprehensive test coverage (5 new tests):

1. **test_check_data_quality_invalid_strategic_objective**
   - Single invalid objective is caught
   - `invalid_values` field is populated

2. **test_check_data_quality_comma_separated_valid_objectives**
   - Multiple valid objectives pass validation
   - Example: `"2026_fuel_regulated, 2026_network"`

3. **test_check_data_quality_comma_separated_one_invalid**
   - Mixed valid/invalid objectives are caught
   - Only invalid ones reported in `invalid_values`

4. **test_check_data_quality_comma_separated_all_invalid**
   - All invalid objectives reported correctly

5. **test_check_data_quality_comma_separated_with_whitespace**
   - Whitespace around objectives is handled correctly
   - Example: `"  2026_fuel_regulated  ,  2026_network  "`

### Test Results
```bash
python3 -m pytest tests/test_validate_planning.py::test_check_data_quality_*strategic* -v
# 6 passed (including pre-existing test for missing strategic objective)
```

## Consistency with analyze_workload.py

The implementation now matches `analyze_workload.py` (lines 376-389), which already had this functionality:

```python
# analyze_workload.py
elif valid_strategic_objectives and strategic_objective:
    # Check each objective individually (handles comma-separated multiple objectives)
    objectives = [obj.strip() for obj in strategic_objective.split(',')]
    invalid_objectives = [obj for obj in objectives if obj not in valid_strategic_objectives]

    if invalid_objectives:
        initiatives_invalid_strategic_objective.append({
            'key': initiative_key,
            'summary': initiative_summary,
            'owner_team': normalized_owner or 'None',
            'current_value': strategic_objective,
            'invalid_values': invalid_objectives
        })
```

Both scripts now use the exact same pattern.

## validate_prioritisation.py

No changes needed for `validate_prioritisation.py` - this script doesn't validate strategic objectives at all (it focuses on priority conflicts and team commitments).

## Files Modified

- `validate_planning.py`: Updated `_check_data_quality()` to split and validate comma-separated objectives
- `tests/test_validate_planning.py`: Added 5 new tests for comma-separated objectives
- `TODO.md`: Marked task as completed

## Example Use Cases

### Product Initiative with Multiple Strategic Goals

An initiative might support multiple strategic objectives:

```yaml
strategic_objective: "2026_fuel_regulated, 2026_scale_ecom"
```

**Before**: ❌ Flagged as invalid
**After**: ✅ Validated individually, both objectives checked

### Engineering Initiative with Cross-Pillar Impact

Engineering work might span multiple pillars:

```yaml
strategic_objective: "engineering_pillars, 2026_network"
```

**Before**: ❌ Flagged as invalid
**After**: ✅ Both objectives validated

### Migration from Old Objectives

When transitioning between strategic objective naming:

```yaml
strategic_objective: "2025_scalability_and_reliability, 2026_scale_ecom"
```

**Before**: ❌ Flagged as invalid
**After**: ✅ Both validated (if both are in valid_values list)

## Design Decisions

1. **Backward Compatibility**: Single objectives still work exactly as before
2. **Whitespace Tolerance**: Extra spaces around commas are stripped automatically
3. **Partial Validation**: Reports only the invalid objectives, not all of them
4. **Same Error Structure**: Maintains `invalid_strategic_objective` error type, adds `invalid_values` array
5. **Consistent with analyze_workload.py**: Uses identical validation logic

## Related Documentation

- `config/jira_config.yaml`: Contains valid strategic objective values
- `analyze_workload.py` (lines 376-389): Original implementation pattern
- `validate_planning.py` (lines 92-107): Updated implementation
