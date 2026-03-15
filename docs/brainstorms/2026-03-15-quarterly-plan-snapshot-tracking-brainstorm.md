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
- **Optional ETA tracking**: If configured, initiatives can have a Due Date (ETA = Estimated Time of Arrival)
  - ETA field: `customfield_12204` ("Due Date" in Jira)
  - Add to `config.yaml`: `eta: "customfield_12204"` under `custom_fields.initiatives`
- Two dimensions to track:
  1. **Plan Stability** (always tracked): Did the set of Planned initiatives stay stable?
  2. **Delivery Predictability** (optional, requires ETA field): When ETAs set, did things ship when expected?

**Churn patterns to detect:**
- Initiatives drop from Planned → Proposed/Cancelled (consequence of #2 and #3 below)
- New initiatives added mid-quarter and fast-tracked to Planned
- Epic scope changes within initiatives (epics added/removed)
- Low predictability: initiatives systematically overrun their ETA by a substantial margin

### Diff Analysis Reports

**Five reports** generated when comparing two snapshots (Reports 1-3 always, Reports 4-5 only if ETA field configured):

1. **Commitment Drift Report**
   - Initiatives with status=Planned in baseline, now status=Proposed/Cancelled
   - Shows: initiative key, summary, team contributions, when dropped

2. **New Work Injection Report**
   - Initiatives that didn't exist (or weren't Planned) in baseline, now Planned
   - Shows: initiative key, summary, teams, when added

3. **Epic Churn Report**
   - For each initiative, list epics added/removed between snapshots
   - Shows: initiative context, epics added, epics removed, net change

4. **Initiative Overrun Report** *(requires ETA field)*
   - Initiatives delivered more than 20% beyond their original ETA
   - Compares: baseline ETA (Due Date) vs actual delivery (status = Done date)
   - Shows: initiative key, summary, % of lead time increase, epics status

5. **Team Stability Report**
   - Per-team metrics: % of planned epics that remained unchanged
   - Per-team metrics: % of initiatives delivered according to initial ETA *(requires ETA field)*
   - Shows: team ranking by stability, churn patterns

### Configuration Examples

**Mode 1: Plan Stability Only (no ETA tracking)**
```yaml
custom_fields:
  initiatives:
    rag_status: "customfield_12111"
    strategic_objective: "customfield_12101"
    quarter: "customfield_12108"
    # No ETA field - Reports 4-5 will be skipped
```
→ Generates Reports 1-3 (commitment drift, new work injection, epic churn)

**Mode 2: Plan Stability + Delivery Predictability (with ETA tracking)**
```yaml
custom_fields:
  initiatives:
    rag_status: "customfield_12111"
    strategic_objective: "customfield_12101"
    quarter: "customfield_12108"
    eta: "customfield_12204"  # Due Date field for ETA tracking
```
→ Generates all 5 reports (including overrun analysis and delivery metrics)

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

1. **ETA field handling**:
   - If `eta: "customfield_12204"` is NOT in config, skip Reports 4-5 entirely
   - If configured but some initiatives missing ETA value, how to handle?
     - Option A: Skip those initiatives in overrun analysis
     - Option B: Report them as "No ETA set"
   - How to capture "actual delivery date"?
     - Option A: Date when status changed to "Done" (need to track status change history)
     - Option B: Use "Completion Date" custom field if populated
     - Option C: Snapshot at quarter-end shows which initiatives are Done (binary: on-time vs late)

2. **Snapshot metadata**: Should we capture additional context at snapshot time?
   - Filter settings used (quarter filter)
   - Custom fields configuration
   - Number of initiatives/epics for quick sanity check

3. **Report output format**: Text to stdout? Markdown file? CSV? All of the above?

4. **Snapshot management**:
   - Should there be a `snapshots delete` command?
   - Archive old snapshots after quarter ends?
   - How to handle snapshot storage growth over time?

5. **Diff algorithm details**:
   - Match initiatives by key (obvious)
   - Match epics by key (obvious)
   - How to detect "renamed" initiatives (key changed but it's conceptually the same)?
   - Should we diff at team level or initiative level first?

6. **Edge cases**:
   - What if baseline snapshot used different custom fields than current config?
   - What if a team project was added/removed between snapshots?
   - Handle orphaned epics in diff analysis?

### Future Enhancements (Deferred)

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
