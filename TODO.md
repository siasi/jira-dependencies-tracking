# TODO

## Future Development

### Data Quality Validation Script
- [x] Create shared validation library `lib/validation.py` (completed 2026-04-11)
- [x] Create `validate_data_quality.py` script with console and Slack output (completed 2026-04-11)
- [ ] Refactor existing scripts to use shared validation library (Phase 3 - future work)
- **Implementation**:
  - Created `lib/validation.py` with `Priority`, `ValidationIssue`, `ValidationConfig`, `InitiativeValidator`
  - Implemented status-aware validation rules (RAG not validated for "In Progress")
  - Owner team exempt from creating epics and setting RAG status
  - Discovery initiatives exempt from dependency checks
  - Comma-separated strategic objectives supported
  - Console output groups action items by manager with priority labels (P1-P5)
  - Slack output uses `notification_slack.j2` template
  - Comprehensive test coverage (52 tests total)
- **Usage**:
  - `./validate_data_quality.py --quarter "26 Q2"` - Standard validation
  - `./validate_data_quality.py --quarter "26 Q2" --status Proposed` - Specific status
  - `./validate_data_quality.py --quarter "26 Q2" --slack` - Generate Slack messages
  - `./validate_data_quality.py --quarter "26 Q2" --all-active` - All active initiatives

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
