# TODO

## Future Development

### Data Quality Validation Script
- [x] Create shared validation library `lib/validation.py` (completed 2026-04-11)
- [x] Create `validate_data_quality.py` script with console and Slack output (completed 2026-04-11)
- [x] Refactor existing scripts to use shared validation library (completed 2026-04-11)
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

### Filter action items on --me
- [x] Implemented --me option in validate_data_quality.py (completed 2026-04-11)
- **Description**: When `--me` flag is set, only violations related to the user's teams are reported in the console report. This is intended to be used by individual managers that can self-check their own issues proactively.
- **Implementation**:
  - Added `--me` flag to `validate_data_quality.py`
  - Added `my_teams` configuration section to `config/team_mappings.yaml`
  - Filters console output to show only action items for configured teams
  - Slack output (`--slack`) is not affected and always shows all teams
  - Display shows "X action items for your teams (Y total)" when filtering
  - 6 comprehensive tests added
- **Usage**:
  - Configure your teams in `config/team_mappings.yaml`: `my_teams: ["CONSOLE", "PAYINS"]`
  - Run: `./validate_data_quality.py --quarter "26 Q2" --me`
  - Console shows only your teams' issues, Slack output unchanged 

### Makes --help option and README be more clear about the scope of the initiatives considered by each team
- [x] Improved --help and README documentation for script scope (completed 2026-04-11)
- **Implementation**:
  - Added detailed "Scope" sections to each script's --help epilog using argparse.RawDescriptionHelpFormatter
  - Added "Script Scope Quick Reference" table to README for easy comparison
  - Added detailed "Scope" sections to each script's README documentation
  - Clarified filtering logic for validate_data_quality.py (combinable flags with AND logic)
  - Documented quarter and status filtering for all scripts
  - Listed exclusions (signed-off initiatives, excluded teams) for each script
- **Scripts Updated**:
  - validate_data_quality.py: Comprehensive filtering combinations documented
  - validate_planning.py: Quarter-specific Proposed/Planned validation
  - validate_prioritisation.py: Priority config-based scope (no quarter/status filtering)
  - analyze_workload.py: In Progress + Planned (quarter-specific) scope
- **Documentation**:
  - README.md: Quick reference table + detailed scope sections for each script
  - All scripts: --help output now includes clear scope information

### Consolidate output format for action items
[] In the same way we consolidated the validation logic in a library is there a way to ensure the format of the output (console and slack) related to action items is consistent across the scripts? If so is there an opprotunity to reduce the number of templates we have?

### Makes script names more consistent 
[] Follow Mission Control metaphor                                                 
                                                                       
  Treats the toolkit as an engineering management control center. Clear, professional, and  familiar to technical audiences.                                                               
                                                                                                 
  Rename the script according to this naming pattern:                                                                                
  - scan - Extract raw data (radar scan)                                                         
  - check - Validate compliance (system checks)                                                  
  - assess - Analyze patterns (situation assessment)                                             
  - track - Monitor over time (trajectory tracking)                                              
                                                                                                 
  How to rename scripts:                                                                                      
  - scan.py (was extract.py) - "Scan Jira for initiative data"                                   
  - check_planning.py (was validate_planning.py) - "Check planning readiness"                    
  - check_priorities.py (was validate_prioritisation.py)                                         
  - check_quality.py (was validate_data_quality.py)                                              
  - assess_workload.py (was analyze_workload.py) - "Assess team workload distribution"           
                                                                                                 
  Why this works:                                                                                
  - Natural verb-noun combinations                                                               
  - Evokes precision, control, oversight                                                         
  - Works well for both technical and management audiences

  Ensure documentation and code comments are all consistent with this new nomenclature.