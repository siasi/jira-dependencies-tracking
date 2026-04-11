# TODO

## Future Development

### Exception Handling Consistency
- [ ] Make `validate_planning.py` respect `initiative_exceptions.yaml`
- [ ] Make `validate_prioritisation.py` respect `initiative_exceptions.yaml`
- **Rationale**: Manager-approved exceptions should apply consistently across all validation scripts, not just workload analysis

### Multi-Objective Strategic Objective Support
- [ ] Fix `validate_planning.py` to handle comma-separated strategic objectives
- **Issue**: `validate_planning.py` (lines 92-103) treats strategic objective as single string
- **Current behavior**: Flags initiatives with multiple objectives (e.g., "objective1, objective2") as invalid
- **Expected behavior**: Split by comma and validate each objective individually, like `analyze_workload.py` does
- **Files to update**:
  - `validate_planning.py`: Update `_check_data_quality()` function to split and validate each objective
  - Consider adding same logic to `validate_prioritisation.py` for consistency

### Owner Team Expectations Alignment
- [ ] Align `validate_prioritisation.py` owner team handling with other scripts
- **Issue**: Inconsistent treatment of owner teams across scripts
- **Current behavior**:
  - `analyze_workload.py`: Owner team exempt from creating epics ✓
  - `validate_planning.py`: Owner team exempt from creating epics and setting RAG ✓
  - `validate_prioritisation.py`: Owner team treated like any contributing team ✗
- **Decision needed**: Should owner teams:
  - Create epics for their own initiatives? (Currently: No in 2 scripts, Yes in 1)
  - Set RAG status on their epics? (Currently: No in planning, Yes in prioritisation)
- **Files to update**:
  - `validate_prioritisation.py`: Add owner team exemption logic to `_detect_missing_commitments()` and `_is_team_committed_with_epics()`
  - Document the decision in README or architecture docs
