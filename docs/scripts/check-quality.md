# Check Quality Script Documentation

Check initiative data quality using comprehensive baseline checks. Reports missing owner teams, assignees, strategic objectives, epics, and RAG status.

## Purpose

This script checks data quality for initiatives using the shared validation library (`lib/validation.py`) for consistent validation across the toolkit. It helps identify:
- Missing critical fields (owner team, assignee, strategic objective)
- Incomplete team dependencies (missing epics)
- Missing RAG status on epics
- Status-specific validation with appropriate priority escalation

## Quick Start

```bash
# Validate current quarter
python check_quality.py --quarter "26 Q2"

# Validate specific status
python check_quality.py --quarter "26 Q2" --status Proposed

# Validate all active initiatives (Proposed, Planned, In Progress)
python check_quality.py --quarter "26 Q2" --all-active
```

## Scope

**Which initiatives are validated:**

The script supports flexible filtering with combinable flags:

- **Default (no filters):**
  - Status: In Progress (any quarter) + Planned (any quarter)

- **With `--quarter Q`:**
  - Status: In Progress (any quarter) + Planned (quarter Q)

- **With `--status X`:**
  - Status: X (any quarter)

- **With `--status X --quarter Q`:**
  - Status: X AND quarter: Q

- **With `--all-active`:**
  - Status: Proposed, Planned, In Progress (any quarter)

- **With `--all-active --quarter Q`:**
  - Status: Proposed, Planned, In Progress AND quarter: Q

- **Exclusions:**
  - Signed-off initiatives (`config/initiative_exceptions.yaml`)
  - Teams in `teams_excluded_from_validation` (`config/team_mappings.yaml`)

## Commands

### Basic Validation

```bash
# Validate current quarter
python check_quality.py --quarter "26 Q2"

# Validate specific status
python check_quality.py --quarter "26 Q2" --status Proposed

# Validate all active initiatives
python check_quality.py --quarter "26 Q2" --all-active
```

### Personal Filtering

```bash
# Show only my teams' action items
python check_quality.py --quarter "26 Q2" --me

# Generate Slack notifications (always includes all teams)
python check_quality.py --quarter "26 Q2" --slack
```

### Show Exemptions

```bash
# Show skipped initiatives (exceptions, excluded teams)
python check_quality.py --quarter "26 Q2" --show-exempt
```

## Options

- `--quarter "YY QN"` - Filter by quarter (e.g., "26 Q2"). Combines with other filters using AND logic.
- `--status STATUS` - Filter by specific status (e.g., "Proposed", "Planned", "In Progress")
- `--all-active` - Filter to active statuses (Proposed, Planned, In Progress)
- `--me` - Show only action items for my teams (configured in `team_mappings.yaml`)
- `--slack` - Generate Slack bulk messages for all managers (not affected by `--me`)
- `--show-exempt` - Show skipped initiatives (exceptions, excluded teams)

## Personal Filtering with --me

Configure your teams in `config/team_mappings.yaml`:

```yaml
my_teams:
  - "CONSOLE"
  - "PAYINS"
  # Add your team project keys here
```

When using `--me` flag:
- Console output shows only action items for your configured teams
- Summary displays: "Showing X action items for your teams (Y total)"
- Slack output (`--slack`) is not affected and always shows all teams
- Useful for engineering managers to self-check their teams proactively

## What Gets Validated

**Priority levels:** P1 (Critical), P2 (High), P3 (Medium), P4 (Low), P5 (Info)

### Owner Team
- **Priority:** P1 (Critical)
- **Rule:** All initiatives must have an owner team assigned
- **Why:** Critical for accountability and ownership

### Assignee
- **Priority:** Status-aware
  - Proposed: P3 (Medium) - Can assign later
  - Planned/In Progress: P1 (Critical) - Must have DRI
- **Rule:** Initiative must have an assignee
- **Why:** Ensures clear responsibility, especially for committed work

### Strategic Objective
- **Priority:** P1 (Critical)
- **Rule:** Must have valid strategic objective
- **Why:** Links work to organizational strategy

### Teams Involved
- **Priority:** P1 (Critical)
- **Rule:** All initiatives must list contributing teams
- **Why:** Essential for dependency tracking and coordination

### Missing Epics
- **Priority:** Status-aware
  - Proposed: P2 (High) - Important signal
  - Planned/In Progress: P1 (Critical) - Dependencies must be confirmed
- **Rule:** Teams in "teams_involved" must create epics
- **Exemption:** Owner team is automatically exempt
- **Why:** Confirms team commitment and scope understanding

### RAG Status
- **Priority:** Status-aware
  - Proposed: P2 (High) - Signal of confidence
  - Planned: P1 (Critical) - Teams must track health
- **Rule:** Epics must have RAG status (Proposed/Planned only)
- **Exemptions:**
  - Owner team automatically excluded
  - Exempt teams (configured in `teams_exempt_from_rag`)
  - In Progress initiatives (no RAG validation)
- **Why:** Tracks commitment confidence and delivery health

## Discovery Initiatives

Initiatives with `[Discovery]` prefix receive special handling:
- Skip epic and RAG validation
- Still required to have owner team and strategic objective
- Appropriate for exploratory or research initiatives

## Output

Terminal report grouped by manager with priority labels (P1-P5):
- Manager name and team
- Action item count per initiative
- Clickable Jira links
- Priority-sorted action items

**Example output:**
```
Manager: John Doe (@john)
Team: PLATFORM

INIT-123: Platform Upgrade
  - [P1] Missing assignee
  - [P1] Missing epics for teams: SECURITY
  - [P2] Missing RAG status on epics: PLAT-100, PLAT-101

Total action items: 3
```

## Exit Codes

- `0` - No validation issues found
- `1` - Data quality issues found

## Use Cases

### Proactive Team Check

Engineering managers can self-check their teams:

```bash
# Check my teams only
python check_quality.py --quarter "26 Q2" --me
```

### Comprehensive Data Audit

Validate all active work:

```bash
# Validate all active initiatives
python check_quality.py --quarter "26 Q2" --all-active

# Review exemptions
python check_quality.py --quarter "26 Q2" --all-active --show-exempt
```

### Status-Specific Validation

Target specific initiative status:

```bash
# Check proposed initiatives
python check_quality.py --status Proposed

# Check planned initiatives for specific quarter
python check_quality.py --quarter "26 Q2" --status Planned
```

## Related Documentation

- [Validation Rules](../specs/validation-rules.md) - Detailed validation rules and logic
- [Validation Library](../guides/validation-library.md) - Shared validation library documentation
- [Configuration Reference](../guides/configuration.md) - Advanced configuration options
- [Setup Guide](../guides/setup.md) - Initial configuration
