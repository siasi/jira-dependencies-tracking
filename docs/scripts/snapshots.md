# Snapshots Documentation 🧪

> **⚠️ EXPERIMENTAL FEATURE**
> Snapshot functionality is in alpha. The API and behavior may change. Use for exploration and feedback, not production workflows.

## Overview

The snapshot feature captures point-in-time copies of Jira data for comparison tracking. This helps engineering leadership measure plan churn, commitment drift, and delivery predictability over time.

**Key capabilities:**
- Capture timestamped snapshots with semantic labels
- List all available snapshots
- Compare two snapshots to identify changes
- Generate reports in text, markdown, or CSV format

## Quick Start

```bash
# Capture baseline snapshot
python scan.py snapshot --label "2026-Q2-baseline"

# Capture monthly checkpoint
python scan.py snapshot --label "2026-Q2-month1"

# List all snapshots
python scan.py snapshots list

# Compare two snapshots
python scan.py compare --from "2026-Q2-baseline" --to "2026-Q2-month1"
```

## Commands

### `snapshot` - Capture Snapshot

Capture a timestamped snapshot with a semantic label.

```bash
python scan.py snapshot --label LABEL [OPTIONS]
```

**Required:**
- `--label TEXT` - Semantic label for the snapshot (e.g., "2026-Q2-baseline")

**Options:**
- `--config PATH` - Path to config file (default: `config/jira_config.yaml`)
- `--quarter TEXT` - Filter by quarter (e.g., "26 Q2")
- `--status TEXT` - Filter by status
- `--verbose` - Enable verbose output

**Examples:**

```bash
# Capture baseline when plan stabilizes
python scan.py snapshot --label "2026-Q2-baseline"

# Capture monthly checkpoints
python scan.py snapshot --label "2026-Q2-month1"
python scan.py snapshot --label "2026-Q2-month2"

# Capture end-of-quarter snapshot
python scan.py snapshot --label "2026-Q2-end"

# Capture with quarter filter
python scan.py snapshot --label "2026-Q2-baseline" --quarter "26 Q2"
```

**Output:**

Snapshots are saved to `data/snapshots/` with naming convention:
```
snapshot_{label}_{timestamp}.json
```

**Snapshot Contents:**
- All Jira data (initiatives, epics, orphaned epics)
- Metadata (timestamp, configuration, totals)
- Same filtering rules as extract command

### `snapshots list` - List Snapshots

View all captured snapshots.

```bash
python scan.py snapshots list
```

**Output:**
```
Available snapshots:
- 2026-Q2-baseline (2026-04-01 10:30:15)
  company.atlassian.net | 42 initiatives, 156 epics, 5 teams

- 2026-Q2-month1 (2026-04-30 11:45:22)
  company.atlassian.net | 45 initiatives, 168 epics, 5 teams

- 2026-Q2-end (2026-06-30 16:00:00)
  company.atlassian.net | 48 initiatives, 180 epics, 5 teams
```

### `compare` - Compare Snapshots

Generate comparison reports between two snapshots.

```bash
python scan.py compare --from LABEL --to LABEL [OPTIONS]
```

**Required:**
- `--from TEXT` - Label of baseline snapshot
- `--to TEXT` - Label of comparison snapshot

**Options:**
- `--format [text|markdown|csv]` - Report format (default: `text`)
- `--output PATH` - Output file path (defaults to stdout for text, auto-generates for markdown/csv)

**Examples:**

```bash
# Compare baseline vs current month (text output to terminal)
python scan.py compare --from "2026-Q2-baseline" --to "2026-Q2-month1"

# Generate markdown report
python scan.py compare \
  --from "2026-Q2-baseline" \
  --to "2026-Q2-end" \
  --format markdown \
  --output ./reports/q2-final.md

# Generate CSV export
python scan.py compare \
  --from "2026-Q2-baseline" \
  --to "2026-Q2-end" \
  --format csv \
  --output ./reports/q2-comparison.csv
```

## Comparison Reports

The comparison generates 5 reports tracking different aspects of plan stability:

### Report 1: Commitment Drift

**Purpose:** Identify initiatives that dropped from commitment.

**Definition:** Initiatives that were "Planned" in baseline, now "Proposed" or "Cancelled"

**Why this matters:** Shows which commitments dropped during the quarter. High drift indicates planning instability or changing priorities.

**Example output:**
```
COMMITMENT DRIFT
Initiatives that were Planned, now Proposed/Cancelled:

INIT-123: Platform Upgrade
  Baseline: Planned | Current: Proposed
  Reason: De-prioritized due to resource constraints

INIT-456: Security Audit
  Baseline: Planned | Current: Cancelled
  Reason: Merged with INIT-789
```

### Report 2: New Work Injection

**Purpose:** Identify work added mid-quarter.

**Definition:** Initiatives that weren't "Planned" in baseline, now "Planned"

**Why this matters:** Shows what new work was added after initial planning. High injection indicates scope creep or reactive planning.

**Example output:**
```
NEW WORK INJECTION
Initiatives that weren't Planned, now Planned:

INIT-789: Emergency Security Fix
  Baseline: Proposed | Current: Planned
  Reason: Critical vulnerability discovered

INIT-234: Customer Escalation
  Baseline: Not present | Current: Planned
  Reason: New initiative created mid-quarter
```

### Report 3: Epic Churn

**Purpose:** Track epic-level changes within initiatives.

**Definition:** Epics added or removed within each initiative

**Why this matters:** Shows plan stability at epic level. High churn indicates unclear scope or emerging dependencies.

**Example output:**
```
EPIC CHURN
Epics added or removed per initiative:

INIT-123: Platform Upgrade
  Removed: PLAT-50 (Database Migration)
  Added: PLAT-75 (API Refactor), PLAT-76 (Testing)
  Net change: +1 epic

INIT-456: Security Audit
  Removed: SEC-20, SEC-21
  Net change: -2 epics
```

### Report 4: Initiative Overruns

> **⚠️ NOT YET IMPLEMENTED**
> Placeholder implementation - returns empty results for MVP.

**Planned functionality:** Track initiatives delivered >20% beyond their ETA

**To enable:** Configure `eta` custom field in `jira_config.yaml`

**Current behavior:** Report returns empty results

### Report 5: Team Stability

**Purpose:** Measure plan stability at team level.

**Definition:** Per-team metrics showing % of epics unchanged, added, removed

**Why this matters:** Identifies which teams have stable plans vs. high churn. Helps target planning process improvements.

**Example output:**
```
TEAM STABILITY
Teams sorted by least stable first:

PLATFORM
  Total epics: 45
  Unchanged: 30 (67%)
  Added: 10 (22%)
  Removed: 5 (11%)

SECURITY
  Total epics: 20
  Unchanged: 18 (90%)
  Added: 2 (10%)
  Removed: 0 (0%)
```

### Orphaned Epics Tracking

**Purpose:** Track epics not linked to initiatives.

**Categories:**
- **Were orphaned, now assigned:** Epics that got linked to initiatives
- **Newly orphaned:** Epics that lost their initiative link
- **Still orphaned:** Epics that remain unlinked

## Report Formats

### Text (Terminal Output)

```bash
python scan.py compare --from "baseline" --to "current"
```

- Terminal-friendly plain text
- Color-coded output (if terminal supports)
- Suitable for quick checks

### Markdown (Documentation)

```bash
python scan.py compare --from "baseline" --to "current" --format markdown
```

- GitHub/docs formatted with tables
- Suitable for sharing in documentation
- Can be imported into Notion, Confluence, etc.

### CSV (Spreadsheet Export)

```bash
python scan.py compare --from "baseline" --to "current" --format csv
```

- Spreadsheet-compatible export
- One CSV per report type
- Suitable for further analysis in Excel/Google Sheets

## Typical Workflow

### Quarterly Tracking

1. **Capture baseline when plan stabilizes:**
   ```bash
   python scan.py snapshot --label "2026-Q2-baseline"
   ```

2. **Capture monthly checkpoints:**
   ```bash
   python scan.py snapshot --label "2026-Q2-month1"
   python scan.py snapshot --label "2026-Q2-month2"
   ```

3. **Capture end-of-quarter snapshot:**
   ```bash
   python scan.py snapshot --label "2026-Q2-end"
   ```

4. **Generate comparison reports:**
   ```bash
   # Month 1 drift
   python scan.py compare --from "2026-Q2-baseline" --to "2026-Q2-month1"

   # Final quarter report
   python scan.py compare \
     --from "2026-Q2-baseline" \
     --to "2026-Q2-end" \
     --format markdown \
     --output ./reports/2026-Q2-final.md
   ```

### Weekly Leadership Updates

```bash
# Capture weekly snapshots
python scan.py snapshot --label "2026-Q2-week14"
python scan.py snapshot --label "2026-Q2-week15"

# Generate weekly drift report
python scan.py compare \
  --from "2026-Q2-week14" \
  --to "2026-Q2-week15"
```

## Configuration

### ETA Tracking (Future Feature)

> **⚠️ NOT YET IMPLEMENTED**

To enable delivery predictability tracking (Reports 4-5), configure the ETA field:

```yaml
custom_fields:
  initiatives:
    eta: "customfield_12204"  # Due Date field for ETA tracking
```

**When implemented:**
- Report 4 will show initiatives that overran their ETA
- Report 5 will include delivery rate metrics

**Current behavior:**
- Report 4 returns empty results (placeholder)
- Report 5 shows only plan stability (no delivery metrics)

## Success Metrics

**Target performance:**
- Capture snapshot in < 30 seconds
- Generate comparison in < 10 seconds (for 100 initiatives, 500 epics)
- Monthly leadership reports prepared in < 15 minutes

**Actual performance (as of alpha):**
- Varies by network latency and data volume
- Performance optimizations planned for beta release

## Limitations & Known Issues

> **Alpha limitations:**

- **No incremental snapshots:** Each snapshot is full copy (no delta storage)
- **No snapshot pruning:** Manual cleanup required for old snapshots
- **Limited error handling:** May fail silently on Jira API errors
- **No snapshot validation:** Corrupted snapshots not detected
- **Report 4 not implemented:** Initiative overruns placeholder only

**Planned improvements:**
- Incremental snapshot support (beta)
- Automatic snapshot cleanup policies (beta)
- Snapshot integrity validation (beta)
- Report 4 full implementation (when ETA field configured)

## Troubleshooting

### Issue: "Snapshot not found"
- **Solution:** Run `python scan.py snapshots list` to see available snapshots
- Check label spelling (case-sensitive)

### Issue: "Comparison failed"
- **Solution:** Ensure both snapshots exist and are from same Jira instance
- Verify snapshots aren't corrupted (check file size > 0)

### Issue: "Empty comparison reports"
- **Solution:** This may be correct if no changes occurred
- Compare snapshots from different time periods for meaningful results

## Providing Feedback

Since this is an experimental feature, your feedback is valuable:

1. **Report issues:** File GitHub issues for bugs or unexpected behavior
2. **Suggest improvements:** Share ideas for report enhancements
3. **Share use cases:** Help us understand how you're using snapshots

## Related Documentation

- [Extract Script](extract.md) - Main extraction documentation
- [Configuration Reference](../guides/configuration.md) - Advanced configuration
