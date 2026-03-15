---
date: 2026-03-15
topic: quarterly-plan-snapshot-tracking
---

# Quarterly Plan Snapshot Tracking

## What We're Building

A **quarterly plan stability and delivery tracking system** that captures timestamped snapshots of Jira initiatives and epics at key milestones (baseline + monthly checkpoints), then analyzes changes over time to quantify plan churn and measure commitment drift.

The system will answer critical questions:
- Which "Planned" initiatives dropped during the quarter and when?
- What new work got injected mid-quarter?
- How did epic scope change within initiatives?
- Which teams have stable vs volatile plans?

**Primary user**: Engineering leadership preparing monthly reports showing plan stability trends and delivery patterns.

## Why This Approach

We evaluated three approaches:

### Approach A: Versioned Snapshots with Diff Analysis ✅ **CHOSEN**
- Extend existing tool to save timestamped JSON snapshots
- Build diff analyzer comparing two snapshots
- Simple, version-control friendly, extends current workflow
- Foundation for future evolution

### Approach B: Time-Series Database
- SQLite storage with multi-quarter trend analysis
- Rich historical patterns and predictability metrics
- Deferred: More complex, premature for initial need

### Approach C: Spreadsheet-Centric
- CSV snapshots merged into Excel workbook with analysis tabs
- Familiar tool for leadership consumption
- Deferred: Less programmatic, doesn't scale to many quarters

**Decision rationale**: Start simple with Approach A. It solves the immediate need (current quarter tracking), requires minimal extension to existing tool, and provides foundation to add database storage or spreadsheet generation later when needs evolve.

## Key Decisions

### Snapshot Capture

- **Event-driven timing**: Snapshots triggered manually when user decides plan is stable, not calendar-based
- **Labels for organization**: User provides semantic labels (`2026-Q2-baseline`, `2026-Q2-month1`) for clarity
- **Storage location**: `data/snapshots/` directory with timestamped JSON files
- **Format**: Same JSON structure as current extract output (no schema changes needed)

### Commitment Tracking Model

**What constitutes a "commitment":**
- Initiative status = "Planned" with all contributing teams committed (RAG status present)
- No ETA tracking initially (focus on plan stability, not delivery predictability)
- Two dimensions to track:
  1. **Plan Stability**: Did the set of Planned initiatives stay stable?
  2. **Delivery Predictability**: (Future) When ETAs added, did things ship when expected?

**Churn patterns to detect:**
- Initiatives drop from Planned → Proposed/Cancelled (consequence of #2 and #3 below)
- New initiatives added mid-quarter and fast-tracked to Planned
- Epic scope changes within initiatives (epics added/removed)

### Diff Analysis Reports

**Four core reports** generated when comparing two snapshots:

1. **Commitment Drift Report**
   - Initiatives with status=Planned in baseline, now status=Proposed/Cancelled
   - Shows: initiative key, summary, team contributions, when dropped

2. **New Work Injection Report**
   - Initiatives that didn't exist (or weren't Planned) in baseline, now Planned
   - Shows: initiative key, summary, teams, when added

3. **Epic Churn Report**
   - For each initiative, list epics added/removed between snapshots
   - Shows: initiative context, epics added, epics removed, net change

4. **Team Stability Report**
   - Per-team metrics: % of planned epics that remained unchanged
   - Shows: team ranking by stability, churn patterns

### Workflow

```bash
# Capture baseline when plan stabilizes
python jira_extract.py snapshot --label "2026-Q2-baseline"

# Monthly checkpoints
python jira_extract.py snapshot --label "2026-Q2-month1"
python jira_extract.py snapshot --label "2026-Q2-month2"
python jira_extract.py snapshot --label "2026-Q2-end"

# Generate comparison reports
python jira_extract.py compare --from "2026-Q2-baseline" --to "2026-Q2-month1"
python jira_extract.py compare --from "2026-Q2-baseline" --to "2026-Q2-end"

# List available snapshots
python jira_extract.py snapshots list
```

## Open Questions

### For Planning Phase

1. **Snapshot metadata**: Should we capture additional context at snapshot time?
   - Filter settings used (quarter filter)
   - Custom fields configuration
   - Number of initiatives/epics for quick sanity check

2. **Report output format**: Text to stdout? Markdown file? CSV? All of the above?

3. **Snapshot management**:
   - Should there be a `snapshots delete` command?
   - Archive old snapshots after quarter ends?
   - How to handle snapshot storage growth over time?

4. **Diff algorithm details**:
   - Match initiatives by key (obvious)
   - Match epics by key (obvious)
   - How to detect "renamed" initiatives (key changed but it's conceptually the same)?
   - Should we diff at team level or initiative level first?

5. **Edge cases**:
   - What if baseline snapshot used different custom fields than current config?
   - What if a team project was added/removed between snapshots?
   - Handle orphaned epics in diff analysis?

### Future Enhancements (Deferred)

- **ETA tracking**: When Jira has ETA custom field, add delivery predictability analysis
- **Multi-snapshot trends**: Compare baseline → month1 → month2 → end in single report
- **Visualization**: Charts showing churn over time (could add spreadsheet export per Approach C)
- **Database storage**: Migrate to SQLite for richer queries (per Approach B)
- **Automated snapshots**: Cron job or scheduled GitHub Actions for monthly captures

## Success Criteria

The snapshot system is working when:
- Can capture quarterly baseline snapshot in < 30 seconds
- Can generate comparison report in < 10 seconds for typical quarter (100 initiatives, 500 epics)
- Commitment drift report accurately identifies all initiatives that dropped from Planned status
- Team stability metrics help leadership identify teams with planning discipline issues
- Monthly leadership reports prepared in < 15 minutes using comparison output

## Next Steps

→ `/ce:plan` to design implementation:
- Snapshot storage schema and file naming
- `snapshot` command implementation
- `compare` command and diff algorithm
- Report formatting and output options
- Tests for diff edge cases
