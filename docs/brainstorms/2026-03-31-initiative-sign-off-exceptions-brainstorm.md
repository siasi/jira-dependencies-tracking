---
date: 2026-03-31
topic: initiative-sign-off-exceptions
---

# Initiative Sign-Off Exceptions

## What We're Building

A configuration-based system to manage initiatives that have known inconsistencies but have been explicitly approved by managers. These initiatives should be completely excluded from validation reports to avoid re-iterating action items for already-resolved situations.

**Example use case:** An initiative lists a team in "Teams Impacted" but has no corresponding epic because the team's contribution is consultative (awareness-only, not building). Manager has approved this as intentional, so validation should skip it entirely.

## Why This Approach

**Chosen: Approach A (Early Filtering)**

Load signed-off initiatives at script startup and filter them out before any validation logic runs. This ensures they're completely invisible in all report sections.

**Why this works best:**
- **Simplicity:** Single filtering step at the start, no conditional logic scattered throughout
- **Complete hiding:** Initiatives never appear in any section (not even with "signed off" tags)
- **Performance:** No repeated checks during validation loops
- **Clear semantics:** Sign-off means "trust the manager, don't validate"

**Alternatives considered:**
- **Approach B (Soft markers):** Show initiatives with "✅ Signed off" tags but still validate them
  - Rejected: Creates noise in reports, defeats purpose of sign-off
- **Approach C (Per-check exemptions):** Configure which checks to skip per initiative
  - Rejected: Too complex for the use case - managers sign off on the whole situation, not individual checks

## Key Decisions

### 1. Configuration Structure

**File:** `config/initiative_exceptions.yaml` (new file)

**Format:**
```yaml
signed_off_initiatives:
  - key: "INIT-1234"
    reason: "Team X is consultative only, no epic needed"
    date: "2026-03-31"  # optional
    approved_by: "@Manager Name"  # optional

  - key: "INIT-5678"
    reason: "Special cross-team arrangement confirmed"
```

**Rationale:**
- List of dicts allows structured data with metadata
- `key` is required (initiative identifier)
- `reason` is required (documents why it's signed off)
- `date` and `approved_by` are optional but useful for audit trails

### 2. Exemption Scope

**Decision:** Skip ALL validation checks for signed-off initiatives

When an initiative is in the sign-off list:
- Not checked for epic count mismatches
- Not checked for missing RAG status
- Not checked for RED/YELLOW epics
- Not checked for missing assignee
- Never appears in any report section

**Rationale:** Sign-off is a manager decision to accept the current state as-is. Partial checking would create confusion about what was actually approved.

### 3. Visibility in Reports

**Decision:** Completely hidden from all report sections

Signed-off initiatives:
- Do NOT appear in "Fix Data Quality"
- Do NOT appear in "Address Commitment Blockers"
- Do NOT appear in "Ready to Move to Planned"
- Do NOT appear in "No/Low Confidence"
- Do NOT appear in "Planned Initiatives with Issues"

**Rationale:** Reports are action-oriented. If no action is needed (manager signed off), showing the initiative creates noise. Users can reference the config file if they need to see what's been signed off.

### 4. Implementation Location

**Decision:** Filter in early data processing (Approach A)

```python
# Load signed-off initiatives at startup
signed_off = load_initiative_exceptions()

# Filter before validation
initiatives_to_validate = [
    init for init in all_initiatives
    if init['key'] not in signed_off
]

# Run validation on filtered list
validate(initiatives_to_validate)
```

**Rationale:**
- Single filtering point reduces bugs
- Clear separation: config loading → filtering → validation
- Easy to test: "Is initiative in sign-off list? Skip it."

### 5. Config File Location

**Decision:** Create new file `config/initiative_exceptions.yaml` alongside existing config files

**Why not add to existing config:**
- `jira_config.yaml` is for Jira connection and field mappings
- `team_mappings.yaml` is for team/manager lookup data
- Exceptions are a distinct concern (validation rules, not data mappings)
- Keeps each config file focused on one responsibility

## Open Questions

1. **Should we add a report summary showing what was signed off?**
   - e.g., "Note: 3 initiatives signed off by managers (see config/initiative_exceptions.yaml)"
   - Tradeoff: Transparency vs. report simplicity

2. **Should we validate the config file?**
   - Check if signed-off initiative keys actually exist in Jira?
   - Check if required fields (key, reason) are present?
   - Warn about stale sign-offs (initiatives now resolved)?

3. **Should signed-off initiatives still appear in --verbose output?**
   - Could be useful for debugging: "Why isn't INIT-1234 showing up? Oh, it's signed off."
   - Default behavior: completely hidden
   - Verbose behavior: show with annotation?

4. **Should this integrate with existing exemption systems?**
   - We already have: `teams_exempt_from_rag`, `teams_excluded_from_analysis`
   - Should this be unified or kept separate?
   - Current design: Keep separate (different exemption levels)

## Next Steps

→ Run `/ce:plan` to design the implementation with:
- Config loading function
- Schema validation for YAML structure
- Early filtering logic integration
- Tests for filtering behavior
- Documentation updates (README.md)
