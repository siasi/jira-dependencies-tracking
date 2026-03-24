---
date: 2026-03-21
topic: initiative-status-validation
---

# Initiative Status Validation Tool

## What We're Building

A validation and reporting tool that analyzes Jira initiatives to determine readiness for status transitions from Proposed to Planned. The tool categorizes initiatives into three groups based on data quality and commitment readiness:

1. **Fix Data Quality** - Initiatives blocked by data issues (epic count mismatches, missing RAG status, no epics)
2. **Address Commitment Blockers** - Initiatives not ready due to risks (RED/YELLOW epics, missing assignee)
3. **Ready to Move to Planned** - Initiatives passing all validation checks

The tool produces a detailed terminal report showing epic-level issues and provides Jira-ready issue keys for bulk status updates.

## Why This Approach

**Approaches Considered:**

**A. Extend `validate_dependencies.py`** - Add RAG and assignee checks to existing script
- Rejected: Scope creep risk, script name becomes misleading

**B. Create new `validate_initiative_status.py` script** - Dedicated validation script ✅ **CHOSEN**
- Selected: Clear separation of concerns, fast to implement, reuses proven patterns from `validate_dependencies.py`

**C. Create validation framework** - Modular system with pluggable validators
- Deferred: Good long-term architecture but overkill for current need, can refactor later if more validators needed

## Key Decisions

### Validation Categories

**Fix Data Quality (blocks planning):**
- Epic count ≠ Teams Involved count
- Missing RAG status on any epic
- Initiative has zero epics

**Address Commitment Blockers (not ready):**
- Any epic has RED status
- Any epic has YELLOW status
- Initiative has no assignee

**Ready to Move to Planned:**
- All epics have GREEN RAG status
- Epic count matches Teams Involved count
- All epics have RAG status set
- Initiative has assignee
- At least one epic exists

### Bidirectional Checking

Check both directions:
- **Proposed → Planned**: Show initiatives ready to promote
- **Planned → Proposed**: Flag regressions (Planned initiatives that no longer meet criteria)

### Report Format

- **Epic-level detail**: Show specific epic keys, titles, and issues
- **Action-oriented sections**: "Fix Data Quality" vs "Data Validation Issues"
- **Simple ready list**: Just keys and titles, no extra detail
- **Bulk update support**: Comma-separated keys for Jira bulk operations

### Missing RAG Status Handling

Treat missing RAG status as RED (blocker) - conservative approach that requires explicit GREEN signal before moving to Planned.

### Tool Type

Validation/reporting tool only - shows recommendations, user manually updates Jira. Not an automatic updater.

## Open Questions

None - requirements are clear and validated.

## Next Steps

→ `/ce:plan` for implementation planning

**Implementation outline:**
1. Create `validate_initiative_status.py` following `validate_dependencies.py` structure
2. Add validation logic for all three categories
3. Implement epic-level reporting with clear issue descriptions
4. Add bidirectional checking (Proposed and Planned initiatives)
5. Test with real data
6. Update README with usage examples
