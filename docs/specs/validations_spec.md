## Status-Aware Validation Rules

Different validation rules apply based on initiative status.

**Note**: DRI (Directly Responsible Individual) = the `assignee` field in Jira. This is the person accountable for driving the initiative forward.

### All Statuses (Universal Checks)

These checks apply to all initiatives regardless of status:

| Check | Priority | Description |
|-------|----------|-------------|
| Missing owner_team | P1 | Blocks everything - initiative needs an owner team |
| Missing strategic_objective | P2 | Blocks planning - initiative needs strategic alignment |
| Invalid strategic_objective | P3 | Not in approved list - needs correction (see definitions below) |
| Missing teams_involved | P4 | Data quality issue - should list contributing teams |

**Rationale**: These are fundamental data quality requirements. Without owner team (P1), we don't know who to hold accountable. Without strategic objective (P2), we can't prioritize or align work.

### Proposed Status (Planning Readiness)

Additional checks beyond universal:

| Check | Priority | Description |
|-------|----------|-------------|
| Missing assignee | P2 | Blocks planning - needs DRI (person responsible) |
| Missing epics from teams_involved | P4 | Teams need to create epics to signal commitment |
| Missing RAG status | P5 | Teams need to communicate commitment level |

**Rationale**: Proposed initiatives are being evaluated for readiness to move to Planned status. Before committing to the quarter, we need:
- **Assignee (P2)**: Someone to drive the initiative
- **Epics (P4)**: Teams confirm dependencies by creating epics
- **RAG status (P5)**: Teams signal confidence level (Red/Amber/Green)

All dependency and commitment signals are relevant at this stage.

### Planned Status (Current Quarter Commitment)

Additional checks beyond universal:

| Check | Priority | Description |
|-------|----------|-------------|
| Missing assignee | P2 | Should have DRI by now - initiative is committed |
| Missing epics from teams_involved | P4 | Teams should have created epics to confirm dependencies |
| Missing RAG status | P5 | Teams should be tracking and communicating health |

**Rationale**: Planned initiatives are committed for the quarter. By this stage:
- **Assignee (P2)**: Must have someone accountable for delivery
- **Epics (P4)**: Dependencies should be confirmed via epic creation
- **RAG status (P5)**: Teams track health to signal risks early

### In Progress Status (Active Work)

Additional checks beyond universal:

| Check | Priority | Description |
|-------|----------|-------------|
| Missing assignee | P2 | Active work must have DRI to coordinate execution |
| Missing epics from teams_involved | P4 | Contributing teams should have epics for active work |

**Rationale**: In Progress initiatives are actively being worked on. By this stage:
- **Assignee (P2)**: Critical to have someone coordinating the work
- **Epics (P4)**: Teams should have created epics to track their contributions
- **RAG status**: NOT validated - decision to proceed was already made, focus is on execution not planning signals

### Done/Cancelled Status (Cleanup Only)

Only checked if `--all-active` or explicit `--status Done` is used:

| Check | Priority | Description |
|-------|----------|-------------|
| Missing strategic_objective | P2 | Historical data completeness for reporting |
| Epics not marked Done | INFO | Cleanup opportunity - close completed work |
| RAG status on Done epics | INFO | Cleanup opportunity - clear stale signals |

**Rationale**: Only validate if explicitly requested. Focus is on data completeness for historical analysis and cleanup opportunities.

---

## Validation Logic - Definitions

### What Makes a Strategic Objective Invalid?

A `strategic_objective` is flagged as **invalid** (P3) when:

1. **Not in approved list**: The value doesn't match any entry in `config/jira_config.yaml` under `validation.strategic_objective.valid_values`
2. **Typos**: Common mistakes like "customer_experiance" instead of "customer_experience"
3. **Deprecated values**: Old objectives like "2023_win_ecommerce" no longer in the approved list
4. **Multi-objective with invalid**: For comma-separated objectives (e.g., "2026_fuel_regulated, wrong_value"), if ANY objective is invalid

**Why P3 (Medium)?** Invalid objectives are usually typos or copy/paste errors that need correction but don't block work.

**Valid Examples:**
- `"2026_fuel_regulated"` ✓
- `"2026_fuel_regulated, engineering_pillars"` ✓ (both are valid)

**Invalid Examples:**
- `"2026_fuel_regulatted"` ✗ (typo)
- `"random_objective"` ✗ (not in list)
- `"2026_fuel_regulated, wrong_value"` ✗ (second objective invalid)

### What Does "Missing Epics from teams_involved" Mean?

This check validates that **all teams listed in `teams_involved`** (except owner team and exempt teams) have created at least one epic linked to the initiative.

**Example:**
```
Initiative INIT-123:
  owner_team: "TEAM1"
  teams_involved: ["TEAM1", "TEAM2", "TEAM3"]
  contributing_teams:
    - team: "TEAM1", epics: ["TEAM1-100"]
    - team: "TEAM2", epics: []

Result:
  ✓ TEAM1 - has epic (also exempt as owner)
  ✓ TEAM2 - has no epic BUT wait... actually ✗ missing epic (P4)
  ✗ TEAM3 - missing epic (P4)
```

**Why this matters:** Epic creation signals team commitment and helps clarify dependencies before work begins.

---

## Validation Logic - Special Cases

### Owner Team Exemption

**Rule**: Owner team is exempt from creating epics and setting RAG status

**Rationale**: The owner team leads the initiative - they don't need to signal "commitment" to themselves. Pre-filtering the owner team from `teams_involved` is simpler and more maintainable than runtime checks. Owner team never appears in commitment matrices or health dashboards.

**Applies to**:
- Missing epics check: Owner team not expected to create epic
- Missing RAG check: Owner team not expected to set RAG status

**Implementation**: Filter out owner team from `teams_involved` before validation.

### Exempt Teams (RAG)

**Rule**: Teams in `config/team_mappings.yaml` under `teams_exempt_from_rag` are exempt from RAG status requirements

**Rationale**: Some support teams (like Documentation) provide best-effort support but don't influence go/no-go decisions for moving initiatives to Planned status. Their RAG status isn't needed for commitment tracking.

**Example**: `teams_exempt_from_rag: ["DOCS"]`

### Discovery Initiatives

**Rule**: Initiatives with `[Discovery]` prefix in summary are exempt from dependency checks (missing epics, missing RAG)

**Rationale**: Discovery work is exploratory research, not building features. Dependency checks are meant to confirm that build work is properly planned. Discovery initiatives still need owner, assignee, and strategic objective.

**What's still checked:**
- ✓ Owner team (P1)
- ✓ Assignee (P2)
- ✓ Strategic objective (P2/P3)
- ✓ Teams involved (P4)

**What's skipped:**
- ✗ Missing epics
- ✗ Missing RAG status

### Multi-Objective Strategic Objectives

**Rule**: Strategic objectives can be a comma-separated list (e.g., `"2026_fuel_regulated, engineering_pillars"`)

**Rationale**: One initiative can contribute to multiple strategic objectives. Each objective in the list is validated independently.

**Validation**: Split by comma, trim whitespace, validate each objective against the approved list.

---

## Priority Level Meanings

| Priority | Label | Meaning | Example |
|----------|-------|---------|---------|
| P1 | Critical | Blocks everything - fundamental data missing | Missing owner_team |
| P2 | High | Blocks planning - can't proceed without this | Missing assignee, strategic objective |
| P3 | Medium | Data correction needed - fixable mistake | Invalid strategic objective (typo) |
| P4 | Low | Missing dependencies - quality issue | Missing epics, teams_involved |
| P5 | Info | Missing signals - nice to have | Missing RAG status |
