# Validate Prioritisation Script Documentation

Validate team commitments to strategically prioritized initiatives and ensure teams respect relative initiative priorities.

## Purpose

This script helps technical leadership ensure teams are committed to strategically important initiatives in the right order. It identifies:
- **Priority conflicts** - Teams committed to lower-priority work while skipping higher-priority initiatives
- **Missing commitments** - Teams expected to contribute but without proper commitment signals
- **Initiative health** - Overall view of which initiatives have proper team commitments

## Quick Start

```bash
# Validate latest extraction
python validate_prioritisation.py

# Generate Slack notifications
python validate_prioritisation.py --slack

# Export markdown report (auto-generates filename)
python validate_prioritisation.py --markdown
```

## Scope

**Which initiatives are validated:**
- **Initiatives:** Only those listed in `config/priorities.yaml`
- **Status:** No status filtering (validates all prioritized initiatives)
- **Quarter:** No quarter filtering (validates all prioritized initiatives)
- **Exclusions:**
  - Done/Cancelled initiatives
  - `[Discovery]` prefixed initiatives
  - Teams in `teams_excluded_from_prioritisation` (`config/team_mappings.yaml`)
    - By default: DevOps, Security Engineering, XD

## Commands

### Basic Validation

```bash
# Validate latest extraction
python validate_prioritisation.py

# Validate specific file
python validate_prioritisation.py data/jira_extract_20260408.json

# Use custom priority config
python validate_prioritisation.py --config custom_priorities.yaml
```

### Generate Reports

```bash
# Export markdown report (auto-generates filename)
python validate_prioritisation.py --markdown

# Export markdown with custom filename
python validate_prioritisation.py --markdown dashboard.md

# Verbose output with additional details
python validate_prioritisation.py --verbose
```

### Generate Slack Notifications

```bash
# Generate Slack notifications
python validate_prioritisation.py --slack
```

## Options

- `--config PATH` - Custom priority config path (default: `config/priorities.yaml`)
- `--markdown [FILENAME]` - Export Initiative Health Dashboard as markdown file. Auto-generates filename if omitted.
- `--verbose` - Include verbose output with additional details
- `--slack` - Generate Slack bulk messages for manager notifications
- `data_file` - Optional path to specific data file (defaults to latest extraction)

## Priority Configuration

Create `config/priorities.yaml` from the `.example` file:

```bash
cp config/priorities.yaml.example config/priorities.yaml
```

Edit the file to list initiatives in priority order (highest priority first):

```yaml
priorities:
  - INIT-1521  # Highest priority - Linkerd Team Adoption
  - INIT-1483  # High priority - Edge Metrics
  - INIT-1411  # Medium priority - Load Test Improvements
  - INIT-1388  # Lower priority - Retry Storms Phase 3
```

## What Gets Validated

### Commitment Definition

A team has a **commitment** to an initiative when they have epic(s) with ALL epics being either:
- Non-red RAG (green/yellow/amber), OR
- Status = Done (work already completed)

This definition ensures teams have confirmed their commitment through proper epic creation and health tracking.

## Report Sections

### 1. Priority Conflicts

Teams committed to lower-priority initiatives while skipping higher-priority ones.

**Example:**
```
PLATFORM team:
  Committed to: INIT-1411 (Priority #3)
  Skipped: INIT-1521 (Priority #1) - Higher priority initiative ignored
```

**Why this matters:** Indicates misalignment with technical leadership priorities. Teams may need to reprioritize or provide rationale for the exception.

### 2. Missing Commitments

Teams expected to contribute (`teams_involved`) but with no green/yellow epics.

**Example:**
```
INIT-1521: Linkerd Team Adoption
  Missing commitment from: SECURITY (expected in teams_involved)
```

**Why this matters:** Initiative may be blocked or scope may be unclear. Team needs to either create epics or be removed from `teams_involved`.

### 3. Initiative Health Dashboard

Initiative-centric view of expected vs actual team commitments.

**Example:**
```
INIT-1521: Linkerd Team Adoption (Priority #1)
  Expected teams: PLATFORM, SECURITY, NETWORKING
  Committed teams: PLATFORM ✅, NETWORKING ✅
  Missing teams: SECURITY ❌
```

**Why this matters:** Provides leadership visibility into which strategic initiatives have full team buy-in.

### 4. Action Items for Managers

Actionable checklist grouped by responsible team.

**Example:**
```
PLATFORM Team (@manager):
  - Review priority conflict: INIT-1411 vs INIT-1521
  - Confirm commitment to INIT-1521

SECURITY Team (@manager):
  - Create epics for INIT-1521
```

**Why this matters:** Clear action items for team managers to address priority alignment issues.

## Exit Codes

- `0` - No priority conflicts or missing commitments
- `1` - Conflicts or missing commitments found
- `2` - Configuration error (missing file, invalid format)

## Use Cases

### Strategic Initiative Planning

Validate team alignment before committing to strategic priorities:

```bash
# Extract latest data
python extract.py extract

# Configure priorities in config/priorities.yaml
# (List initiatives in priority order)

# Validate alignment
python validate_prioritisation.py

# Export dashboard for leadership review
python validate_prioritisation.py --markdown dashboard.md
```

### Quarterly Business Review

Generate initiative health dashboard for leadership:

```bash
# Generate markdown report
python validate_prioritisation.py --markdown

# Share report with leadership team
```

### Manager Follow-Up

Track action items for team managers:

```bash
# Generate Slack messages
python validate_prioritisation.py --slack

# Send messages to managers
# Review action items in output/prioritisation_validation/
```

## Configuration

### Set Up Priorities

1. Copy example file:
   ```bash
   cp config/priorities.yaml.example config/priorities.yaml
   ```

2. List initiatives in priority order (highest first):
   ```yaml
   priorities:
     - INIT-1521  # P1 - Most important
     - INIT-1483  # P2 - High priority
     - INIT-1411  # P3 - Medium priority
   ```

3. Run validation:
   ```bash
   python validate_prioritisation.py
   ```

### Exclude Teams from Validation

Configure teams that don't follow standard prioritization:

```yaml
teams_excluded_from_prioritisation:
  - "DevOps"
  - "Security Engineering"
  - "XD"
```

These teams will not be checked for priority conflicts or missing commitments.

## Related Documentation

- [Validation Rules](../specs/validation-rules.md) - Detailed validation rules and logic
- [Validation Library](../guides/validation-library.md) - Shared validation library documentation
- [Configuration Reference](../guides/configuration.md) - Advanced configuration options
- [Setup Guide](../guides/setup.md) - Initial configuration

## Design Documentation

See [brainstorm document](../brainstorms/2026-04-08-tech-leadership-priority-validation-brainstorm.md) and [implementation plan](../plans/2026-04-08-001-feat-tech-leadership-priority-validation-plan.md) for design decisions and approach rationale.
