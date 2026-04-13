# Owner Team Exemption Alignment

**Date**: 2026-04-11
**Status**: Completed
**Related TODO**: Owner Team Expectations Alignment

## Summary

Aligned `check_priorities.py` with `assess_workload.py` and `check_planning.py` to exempt owner teams from creating epics and setting RAG status for their own initiatives. This resolves inconsistent treatment of owner teams across validation scripts.

## Problem

There was an inconsistency in how different validation scripts treated owner teams:

| Script | Owner Team Treatment |
|--------|---------------------|
| `assess_workload.py` | ✅ Exempt from creating epics |
| `check_planning.py` | ✅ Exempt from creating epics and setting RAG |
| `check_priorities.py` | ❌ Treated like any contributing team |

This meant that initiatives led by a team would incorrectly flag that team for "missing commitments" even though they're the ones leading the initiative.

### Example of the Problem

**Before:**
```yaml
Initiative: INIT-123
Owner Team: Platform Team
Teams Involved: [Platform Team, Payments Team, API Team]
Contributing Teams:
  - Payments Team: PAYMENTS-456 (🟢)
  - API Team: API-789 (🟢)
  - Platform Team: (no epic)  # ❌ Incorrectly flagged as missing
```

**Issue**: Platform Team is leading the initiative, so they shouldn't need to create an epic to "commit" to their own work.

## Solution

Updated `check_priorities.py` to filter out owner teams from commitment validation in two functions:

### 1. _build_commitment_matrix() (lines 462-469)

```python
# Get expected teams and filter excluded ones
teams_involved = _normalize_teams_involved(initiative.get('teams_involved'))
teams_involved = _filter_excluded_teams(teams_involved, excluded_teams)

# Filter out owner team (they don't need to create epics for their own initiatives)
owner_team = initiative.get('owner_team')
if owner_team and owner_team in teams_involved:
    teams_involved = [team for team in teams_involved if team != owner_team]

for team_display in teams_involved:
    # ... build commitment matrix only for non-owner teams
```

### 2. _build_initiative_health() (lines 680-686)

```python
# Get expected teams and filter excluded ones
teams_involved = _normalize_teams_involved(initiative.get('teams_involved'))
teams_involved = _filter_excluded_teams(teams_involved, excluded_teams)

# Filter out owner team (they don't need to create epics for their own initiatives)
owner_team = initiative.get('owner_team')
if owner_team and owner_team in teams_involved:
    teams_involved = [team for team in teams_involved if team != owner_team]

# Get committed teams
for team_display in teams_involved:
    # ... build health dashboard only for non-owner teams
```

### Why This Approach Works

By filtering the owner team from `teams_involved` early in both functions:
- Owner teams never enter the commitment matrix
- They don't appear in missing commitments
- They don't appear in priority conflicts
- The initiative health dashboard doesn't expect them to commit
- All downstream logic automatically handles it correctly

## Behavior

### Before (Incorrect)
```
Initiative owned by Platform Team:
- Expected Commitments: Platform Team, Payments Team, API Team
- Actual Commitments: Payments Team (🟢), API Team (🟢)
- Missing: Platform Team ❌ (incorrectly flagged)
```

### After (Correct)
```
Initiative owned by Platform Team:
- Expected Commitments: Payments Team, API Team (owner filtered out)
- Actual Commitments: Payments Team (🟢), API Team (🟢)
- Missing: None ✅ (owner team not expected to commit)
```

## Rationale: Why Owner Teams Don't Need Epics

1. **They're Leading, Not Contributing**: The owner team is driving the initiative, they don't "commit" to it in the same way contributing teams do

2. **No Self-Reporting**: Owner teams don't need to set RAG status to report to themselves

3. **Already Tracked**: The initiative itself tracks the owner team's work - they don't need a separate epic

4. **Consistency**: All three validation scripts now treat owner teams the same way

## Edge Cases Handled

### Owner Team Also a Contributor
If an owner team happens to create an epic (e.g., for tracking sub-work):
- The epic is not required
- If present, it's not validated for RAG status
- No penalties if missing

### Multiple Initiatives, Different Owners
- Team A owns INIT-1 → not required to commit to INIT-1
- Team A contributes to INIT-2 (owned by Team B) → required to commit
- Works correctly because filtering is per-initiative

### Owner Team Not in teams_involved
If owner team is not listed in teams_involved:
- No filtering happens (nothing to filter)
- Other teams still validated normally

## Testing

Added comprehensive test coverage (3 new tests):

1. **test_owner_team_not_required_to_commit**
   - Owner team in teams_involved but has no epic
   - Verifies owner team NOT flagged for missing commitment
   - Verifies other teams still validated normally

2. **test_owner_team_mixed_with_contributing_teams**
   - Multiple initiatives with different owners
   - Verifies Team A exempt when they own an initiative
   - Verifies Team A flagged when they contribute to others' initiatives

3. **test_non_owner_team_required_to_commit**
   - Non-owner team with no epic
   - Verifies they ARE flagged (normal validation still works)

### Test Results
```bash
python3 -m pytest tests/test_check_priorities.py -v
# 46 passed in 0.10s (3 new tests for owner team exemption)
```

## Consistency Across Scripts

All three scripts now handle owner teams identically:

### assess_workload.py
- Filters owner team from workload calculations
- Owner team doesn't contribute to their own initiative count

### check_planning.py
- Owner team exempt from creating epics (lines 119-143)
- Owner team exempt from RAG status checks (lines 156-168, 208-227, 252-267, 340-356)

### check_priorities.py ✨ (Now Updated)
- Owner team filtered from commitment matrix (lines 462-469)
- Owner team filtered from initiative health (lines 680-686)

## Files Modified

- `check_priorities.py`: Added owner team filtering in 2 functions
- `tests/test_check_priorities.py`: Added 3 comprehensive tests
- `TODO.md`: Marked task as completed, documented decision

## Design Decision

**Decision**: Owner teams do NOT need to create epics or set RAG status for their own initiatives.

**Reasoning**:
1. They're leading the initiative, not contributing to someone else's
2. They don't report to themselves
3. The initiative itself tracks their work
4. Simpler mental model: "owner leads, contributors contribute"

This decision is now codified and consistently implemented across all validation scripts.

## Examples

### Product Initiative
```yaml
INIT-123: "Improve checkout flow"
Owner Team: Payments Team
Teams Involved: [Payments Team, Frontend Team, API Team]

Expected Commitments:
  - Frontend Team: FRONTEND-456 (required)
  - API Team: API-789 (required)
  - Payments Team: (owner, not required)
```

### Cross-Team Infrastructure Work
```yaml
INIT-456: "Database migration"
Owner Team: Platform Team
Teams Involved: [Platform Team, Payments Team, Core Banking Team]

Expected Commitments:
  - Payments Team: PAYMENTS-123 (required - they need to migrate)
  - Core Banking Team: CBNK-456 (required - they need to migrate)
  - Platform Team: (owner, not required - they're leading the migration)
```

### Engineering Pillar Initiative
```yaml
INIT-789: "Improve observability"
Owner Team: Platform Team
Teams Involved: [Platform Team, All Product Teams]

Expected Commitments:
  - Product Team A, B, C, etc: Epics required (they adopt the improvements)
  - Platform Team: (owner, not required - they're building the infrastructure)
```

## Related Documentation

- `assess_workload.py`: First implementation of owner team exemption
- `check_planning.py` (lines 119-143, 156-168): Owner team exemption in planning validation
- `docs/ARCHITECTURE.md`: Should be updated to document this design decision
