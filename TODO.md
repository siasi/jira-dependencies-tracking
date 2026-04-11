# TODO

## Future Development

### Exception Handling Consistency
- [x] Make `validate_planning.py` respect `initiative_exceptions.yaml` (completed 2026-04-01)
- [x] Make `validate_prioritisation.py` respect `initiative_exceptions.yaml` (completed 2026-04-11)
- **Rationale**: Manager-approved exceptions should apply consistently across all validation scripts, not just workload analysis

### Multi-Objective Strategic Objective Support
- [x] Fix `validate_planning.py` to handle comma-separated strategic objectives (completed 2026-04-11)
- **Issue**: `validate_planning.py` (lines 92-103) treats strategic objective as single string
- **Current behavior**: Flags initiatives with multiple objectives (e.g., "objective1, objective2") as invalid
- **Expected behavior**: Split by comma and validate each objective individually, like `analyze_workload.py` does
- **Files to update**:
  - `validate_planning.py`: Update `_check_data_quality()` function to split and validate each objective ✓
  - `validate_prioritisation.py`: Not needed - this script doesn't validate strategic objectives

### Owner Team Expectations Alignment
- [x] Align `validate_prioritisation.py` owner team handling with other scripts (completed 2026-04-11)
- **Issue**: Inconsistent treatment of owner teams across scripts
- **Current behavior**:
  - `analyze_workload.py`: Owner team exempt from creating epics ✓
  - `validate_planning.py`: Owner team exempt from creating epics and setting RAG ✓
  - `validate_prioritisation.py`: Owner team exempt from creating epics ✓ (now consistent)
- **Decision**: Owner teams do NOT need to:
  - Create epics for their own initiatives (they're leading, not contributing)
  - Set RAG status on their epics (they don't report to themselves)
- **Files updated**:
  - `validate_prioritisation.py`: Added owner team filtering in `_build_commitment_matrix()` and `_build_initiative_health()` ✓
