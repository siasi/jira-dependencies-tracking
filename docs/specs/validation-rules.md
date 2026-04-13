# Validation Rules Specification

This document defines the business rules for validating initiative data quality. It explains **what** gets validated, **why**, and **who** is responsible for fixing issues.

> **For Developers:** See [Validation Library Guide](../guides/validation-library.md) for implementation details and API reference.

## Overview

The toolkit validates initiatives using status-aware rules. Different validation checks apply based on initiative status (Proposed, Planned, In Progress) to ensure data quality aligns with planning workflows.

**Key Principles:**
- **Status-aware:** Validation rules escalate as initiatives progress
- **Owner accountability:** Each check has a clear owner responsible for fixes
- **Priority-based:** Issues are prioritized (P1-P5) by business impact
- **Exemptions:** Special cases (Discovery initiatives, owner teams, exempt teams) are handled consistently

## Status-Aware Validation Rules

Different validation rules apply based on initiative status.

**Note:** DRI (Directly Responsible Individual) = the `assignee` field in Jira. This is the person accountable for driving the initiative forward.

### All Statuses (Universal Checks)

These checks apply to all initiatives regardless of status:

| Check | Priority | Description | Owner |
|-------|----------|-------------|-------|
| Missing owner_team | P1 | Blocks everything - initiative needs an owner team | None |
| Missing teams_involved | P1 | Data quality issue - should list contributing teams | Owner Team Manager |
| Missing strategic_objective | P1 | Blocks planning - initiative needs strategic alignment | Owner Team Manager |
| Invalid strategic_objective | P3 | Not in approved list - needs correction (see [definitions](#what-makes-a-strategic-objective-invalid)) | Owner Team Manager |

**Rationale:** These are fundamental data quality requirements. Without owner team (P1), we don't know who to hold accountable. Without strategic objective (P1), we can't prioritize or align work. Without teams_involved (P1), we can't track dependencies.

### Proposed Status (Planning Readiness)

Additional checks beyond universal:

| Check | Priority | Description | Owner |
|-------|----------|-------------|-------|
| Missing epics from teams_involved | P2 | Teams need to create epics to signal commitment | Dependent Team Manager |
| Missing RAG status | P2 | Teams need to communicate commitment level | Dependent Team Manager |
| Missing assignee | P3 | Blocks execution - needs person responsible | Owner Team Manager |

**Rationale:** Proposed initiatives are being evaluated for readiness to move to Planned status. Before committing to the quarter, we need:
- **Epics (P2):** Teams confirm dependencies by creating epics
- **RAG status (P2):** Teams signal confidence level (Red/Amber/Green)
- **Assignee (P3):** Someone to drive the initiative

All dependency and commitment signals are relevant at this stage.

### Planned Status (Current Quarter Commitment)

Additional checks beyond universal:

| Check | Priority | Description | Owner |
|-------|----------|-------------|-------|
| Missing assignee | P1 | Should have DRI by now - initiative is committed | Owner Team Manager |
| Missing epics from teams_involved | P1 | Teams should have created epics to confirm dependencies | Dependent Team Manager |
| Missing RAG status | P1 | Teams should be tracking and communicating health | Dependent Team Manager |

**Rationale:** Planned initiatives are committed for the quarter. By this stage:
- **Assignee (P1):** Must have someone accountable for delivery
- **Epics (P1):** Dependencies should be confirmed via epic creation
- **RAG status (P1):** Teams track health to signal risks early

### In Progress Status (Active Work)

Additional checks beyond universal:

| Check | Priority | Description | Owner |
|-------|----------|-------------|-------|
| Missing assignee | P1 | Active work must have owner to coordinate execution | Owner Team Manager |
| Missing epics from teams_involved | P1 | Contributing teams should have epics for active work | Dependent Team Manager |

**Rationale:** In Progress initiatives are actively being worked on. By this stage:
- **Assignee (P1):** Critical to have someone coordinating the work
- **Epics (P1):** Teams should have created epics to track their contributions
- **RAG status:** NOT validated - decision to proceed was already made, focus is on execution not planning signals

### Done/Cancelled Status (Cleanup Only)

Only checked if `--all-active` or explicit `--status Done` is used:

| Check | Priority | Description | Owner |
|-------|----------|-------------|-------|
| Missing strategic_objective | P3 | Historical data completeness for reporting | Owner Team Manager |
| Epics not marked Done | INFO | Cleanup opportunity - close completed work | Owner Team Manager |
| RAG status on Done epics | INFO | Cleanup opportunity - clear stale signals | Dependent Team Manager |

**Rationale:** Only validate if explicitly requested. Focus is on data completeness for historical analysis and cleanup opportunities.

---

## Validation Logic - Definitions

### What Makes a Strategic Objective Invalid?

A `strategic_objective` is flagged as **invalid** (P3) when:

1. **Not in approved list:** The value doesn't match any entry in `config/jira_config.yaml` under `validation.strategic_objective.valid_values`
2. **Typos:** Common mistakes like "customer_experiance" instead of "customer_experience"
3. **Deprecated values:** Old objectives like "2023_win_ecommerce" no longer in the approved list
4. **Multi-objective with invalid:** For comma-separated objectives (e.g., "2026_fuel_regulated, wrong_value"), if ANY objective is invalid

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
  ✗ TEAM2 - missing epic (P2 for Proposed, P1 for Planned/In Progress)
  ✗ TEAM3 - missing epic (P2 for Proposed, P1 for Planned/In Progress)
```

**Why this matters:** Epic creation signals team commitment and helps clarify dependencies before work begins.

---

## Validation Logic - Special Cases

### Owner Team Exemption

**Rule:** Owner team is exempt from creating epics and setting RAG status

**Rationale:** The owner team leads the initiative - they don't need to signal "commitment" to themselves. Pre-filtering the owner team from `teams_involved` is simpler and more maintainable than runtime checks. Owner team never appears in commitment matrices or health dashboards.

**Applies to:**
- Missing epics check: Owner team not expected to create epic
- Missing RAG check: Owner team not expected to set RAG status

**Implementation:** Filter out owner team from `teams_involved` before validation.

### Exempt Teams (RAG)

**Rule:** Teams in `config/team_mappings.yaml` under `teams_exempt_from_rag` are exempt from RAG status requirements

**Rationale:** Some support teams (like Documentation) provide best-effort support but don't influence go/no-go decisions for moving initiatives to Planned status. Their RAG status isn't needed for commitment tracking.

**Example:** `teams_exempt_from_rag: ["DOCS", "UX_RESEARCH"]`

**Configuration:** See [Configuration Reference](../guides/configuration.md#teams-exempt-from-rag-status)

### Discovery Initiatives

**Rule:** Initiatives with `[Discovery]` prefix in summary are exempt from dependency checks (missing epics, missing RAG)

**Rationale:** Discovery work is exploratory research, not building features. Dependency checks are meant to confirm that build work is properly planned. Discovery initiatives still need owner, assignee, and strategic objective.

**What's still checked:**
- ✓ Owner team (P1)
- ✓ Teams involved (P1)
- ✓ Strategic objective (P1)
- ✓ Invalid strategic objective (P3)
- ✓ Assignee (varies by status: P3 for Proposed, P1 for Planned/In Progress)

**What's skipped:**
- ✗ Missing epics
- ✗ Missing RAG status

### Multi-Objective Strategic Objectives

**Rule:** Strategic objectives can be a comma-separated list (e.g., `"2026_fuel_regulated, engineering_pillars"`)

**Rationale:** One initiative can contribute to multiple strategic objectives. Each objective in the list is validated independently.

**Validation:** Split by comma, trim whitespace, validate each objective against the approved list.

---

## Priority Level Meanings

| Priority | Label | Meaning | Example |
|----------|-------|---------|---------|
| P1 | Critical | Blocks everything - fundamental data missing or committed work not tracked | Missing owner_team, missing assignee (Planned/In Progress) |
| P2 | High | Blocks progression - can't proceed to next status without this | Missing epic (Proposed), RAG status (Proposed) |
| P3 | Medium | Data correction needed - fixable mistake that doesn't block immediate work | Invalid strategic objective (typo), missing assignee (Proposed) |
| P4 | Low | Nice to have - improves data quality but not critical | (Reserved for future use) |
| P5 | Info | Informational only - cleanup opportunities | Done epics with stale RAG status |

---

## Which Scripts Use These Rules?

| Script | Validation Rules Applied |
|--------|-------------------------|
| **validate_planning.py** | All rules for Proposed and Planned initiatives in specified quarter |
| **validate_data_quality.py** | All rules, status-aware, with flexible filtering options |
| **validate_prioritisation.py** | Baseline validation (owner, assignee, strategic objective, teams_involved) + commitment checks |
| **analyze_workload.py** | Baseline validation (owner, strategic objective, teams_involved) for quality warnings |

All scripts use the shared validation library (`lib/validation.py`) to ensure consistent rule application.

---

## Related Documentation

- [Validation Library](../guides/validation-library.md) - Developer guide for implementing validation
- [Configuration Reference](../guides/configuration.md) - Configure exemptions and special cases
- [Validate Planning](../scripts/validate-planning.md) - Planning readiness validation
- [Validate Data Quality](../scripts/validate-data-quality.md) - Comprehensive data quality checks
- [Validate Priorities](../scripts/validate-prioritisation.md) - Strategic priority validation
