# Check Planning Script Documentation

Check initiative readiness for Proposed → Planned status transitions based on epic RAG status, team dependencies, and assignee presence.

## Purpose

This script helps engineering leadership ensure initiatives are ready to move from Proposed to Planned status by validating:
- Data quality (epic counts, RAG status presence)
- Commitment blockers (RED/YELLOW epics, missing assignees)
- Bidirectional status transitions (Proposed → Planned and regressions)

## Quick Start

```bash
# Validate latest extraction for Q2 2026
python check_planning.py --quarter "26 Q2"

# Generate Slack notifications for Q2 2026
python check_planning.py --quarter "26 Q2" --slack

# Export markdown report
python check_planning.py --quarter "26 Q2" --markdown
```

## Scope

**Which initiatives are validated:**
- **Quarter:** Matches specified `--quarter` (required)
- **Status:** Proposed OR Planned only
- **Exclusions:**
  - Signed-off initiatives (`config/initiative_exceptions.yaml`)
  - Teams in `teams_excluded_from_validation` (`config/team_mappings.yaml`)

## Commands

### Basic Validation

```bash
# Validate latest extraction for Q2 2026
python check_planning.py --quarter "26 Q2"

# Validate specific file for Q2 2026
python check_planning.py --quarter "26 Q2" data/jira_extract_20260321.json

# Validate snapshot
python check_planning.py --quarter "26 Q2" data/snapshots/snapshot_baseline_*.json
```

### Generate Reports

```bash
# Export markdown report
python check_planning.py --quarter "26 Q2" --markdown

# Verbose output with additional details
python check_planning.py --quarter "26 Q2" --verbose
```

### Generate Slack Notifications

```bash
# Generate Slack messages for Q2 2026
python check_planning.py --quarter "26 Q2" --slack
```

## Options

- `--quarter "YY QN"` - **Required.** Quarter to validate (e.g., "26 Q2"). Only initiatives matching this quarter will be validated.
- `--markdown [FILENAME]` - Export report to markdown format (Notion-compatible). Auto-generates filename if omitted.
- `--verbose` - Include verbose output with additional details
- `--slack` - Generate Slack bulk messages for manager notifications
- `json_file` - Optional path to specific data file (defaults to latest extraction)

## What It Checks

### Fix Data Quality (blocks planning)

Issues that prevent initiative from progressing:
- Epic count matches Teams Involved count
- All epics have RAG status set
- Initiative has at least one epic

### Address Commitment Blockers (not ready)

Issues that indicate initiative is not ready to commit:
- No RED or YELLOW epics (all must be GREEN)
- Initiative has assignee
- Missing RAG status treated as RED

### Ready to Move to Planned

Initiatives that pass all checks above:
- All validations passed
- Outputs Jira-ready issue keys for bulk update

### Bidirectional Checking

The script checks both directions:
- Checks Proposed → Planned transitions
- Flags Planned → Proposed regressions

## Slack Manager Notifications

Generate copy-paste ready messages for sending bulk Slack DMs:

```bash
# Generate Slack messages for Q2 2026
python check_planning.py --quarter "26 Q2" --slack

# Output: Console preview + file in extracts/slack_messages_YYYY-MM-DD_HHMMSS.txt
```

**Message Format:**
- Grouped by engineering manager
- Each message includes Slack member ID (Recipient:)
- Action items organized by initiative (and by team for multi-team managers)
- Ready to paste into Slack or bulk messaging tool

**Important:** If a manager oversees multiple teams, they receive one consolidated message with subsections for each team, rather than separate messages per team.

**Action Types Included:**
1. Missing dependencies - Teams need to create epics
2. Missing RAG status - Teams need to set RAG on epics
3. Missing assignee - Initiatives need assignees
4. Ready to PLANNED - Initiatives ready to move forward

## Output

Terminal report with four sections:
1. 🔴 **Fix Data Quality** - Initiatives with data issues (epic-level detail)
2. 🟡 **Address Commitment Blockers** - Initiatives not ready (epic-level detail)
3. ✅ **Ready to Move to Planned** - Comma-separated keys for bulk Jira update
4. ⚠️  **Planned Initiatives with Issues** - Regressions to fix

## Exit Codes

- `0` - All validations passed, initiatives ready
- `1` - Validation issues found (data quality or commitment blockers)

## Use Cases

### Quarterly Planning Validation

Validate readiness for new initiatives in the quarter:

```bash
# Extract latest data
python scan.py extract --quarter "26 Q2"

# Validate planning readiness
python check_planning.py --quarter "26 Q2" --slack
```

### Pre-Planning Meeting Check

Quick check before planning meetings:

```bash
# Check current state
python check_planning.py --quarter "26 Q2"

# Review markdown report
python check_planning.py --quarter "26 Q2" --markdown
```

### Team Manager Follow-Up

Track action items for team managers:

```bash
# Generate Slack messages
python check_planning.py --quarter "26 Q2" --slack

# Send messages to managers
# Review action items in output/planning_validation/
```

## Related Documentation

- [Validation Rules](../specs/validation-rules.md) - Detailed validation rules and logic
- [Validation Library](../guides/validation-library.md) - Shared validation library documentation
- [Configuration Reference](../guides/configuration.md) - Advanced configuration options
- [Setup Guide](../guides/setup.md) - Initial configuration

## Design Documentation

See [brainstorm document](../brainstorms/2026-03-21-initiative-status-validation-brainstorm.md) for design decisions and approach rationale.
