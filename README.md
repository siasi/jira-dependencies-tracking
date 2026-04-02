# Jira EM Toolkit

Engineering manager toolkit for Jira initiative and epic analysis, planning validation, and workload tracking.

## Project Structure

```
jira-em-toolkit/
├── config/          # Configuration files
│   ├── jira_config.yaml        # Jira connection and project settings
│   ├── team_mappings.yaml      # Team and manager information
│   ├── initiative_exceptions.yaml  # Manager-approved exceptions
│   └── *.yaml.example          # Example configs
├── lib/             # Shared toolkit utilities
│   ├── common_formatting.py    # Hyperlink formatting
│   ├── template_renderer.py    # Jinja2 rendering
│   └── file_utils.py          # File discovery
├── src/             # Core domain logic
│   ├── config.py              # Configuration loading
│   ├── jira_client.py         # Jira API wrapper
│   ├── fetcher.py             # Data fetching
│   ├── builder.py             # Hierarchy building
│   ├── output.py              # JSON/CSV output
│   ├── snapshot.py            # Snapshot management
│   ├── comparator.py          # Snapshot comparison
│   └── reports.py             # Report generation
├── templates/       # Jinja2 templates
├── tests/           # Test suite
├── docs/            # Documentation
├── data/            # Output directory (gitignored)
├── extract.py                 # Data extraction
├── validate_planning.py       # Planning validation
├── analyze_workload.py        # Workload analysis
└── README.md
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

## Setup

1. **Prerequisites:** Python 3.9+, Jira Cloud access

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure:**
   ```bash
   cp config/jira_config.yaml.example config/jira_config.yaml
   cp config/.env.example config/.env
   ```

4. **(Optional) Install as package:**
   ```bash
   pip install -e .

   # Scripts available as commands:
   jem-extract               # Data extraction from Jira
   jem-validate-planning     # Planning readiness validation
   jem-analyze-workload      # Team workload analysis
   ```

   Or use the scripts directly from the root directory:
   ```bash
   python extract.py
   python validate_planning.py
   python analyze_workload.py
   ```

## Usage

Extract data (JSON format):
```bash
python extract.py extract
```

Validate readiness for new initiatives in the quarter and track action items for Team Managers, so that initiatives can progress to Planned status:
```bash
python validate_planning.py --quarter "26 Q2" --min-teams 2 --slack
```

Once Planning is done, extract data again and analyze workload per team:
```bash
python extract.py extract
python analyze_workload.py
```

## Extract

This tool extracts data from Jira and stores it in a local file for further analysis with other scripts.

Extract as CSV:
```bash
python extract.py extract --format csv
```

Extract both JSON and CSV:
```bash
python extract.py extract --format both
```

List custom fields:
```bash
python extract.py list-fields
```

Validate config:
```bash
python extract.py validate-config
```

### Options

```bash
python extract.py extract --config config/custom.yaml --output ./report.json --verbose
python extract.py extract --format csv --output ./data/export.csv
```

**Available options:**
- `--config PATH` - Path to config file (default: `config/jira_config.yaml`)
- `--format [json|csv|both]` - Output format (default: `json`)
- `--output PATH` - Custom output file path
- `--verbose` - Enable verbose output for debugging
- `--dry-run` - Show what would be fetched without writing output

## Snapshots (alpha)

The extract.py script can also store data as snapshots to compare them. This helps engineering leadership measure plan churn, commitment drift, and delivery predictability.

### Capture Snapshots

Capture a timestamped snapshot with a semantic label:

```bash
# Capture baseline when plan stabilizes
python extract.py snapshot --label "2026-Q2-baseline"

# Monthly checkpoints
python extract.py snapshot --label "2026-Q2-month1"
python extract.py snapshot --label "2026-Q2-month2"
python extract.py snapshot --label "2026-Q2-end"
```

Snapshots are saved to `data/snapshots/` and include:
- All Jira data (initiatives, epics, orphaned epics)
- Metadata (timestamp, configuration, totals)
- Same filtering rules as extract command

### List Available Snapshots

View all captured snapshots:

```bash
python extract.py snapshots list
```

Output shows:
- Label, timestamp, Jira instance
- Total initiatives, epics, teams

### Compare Snapshots

Generate comparison reports between two snapshots:

```bash
# Compare baseline vs current month (text output to terminal)
python extract.py compare --from "2026-Q2-baseline" --to "2026-Q2-month1"

# Generate markdown report to file
python extract.py compare \
  --from "2026-Q2-baseline" \
  --to "2026-Q2-end" \
  --format markdown \
  --output ./reports/q2-final.md

# Generate CSV export
python extract.py compare \
  --from "2026-Q2-baseline" \
  --to "2026-Q2-end" \
  --format csv \
  --output ./reports/q2-comparison.csv
```

**Report Formats:**
- `text` - Terminal-friendly plain text (default)
- `markdown` - GitHub/docs formatted with tables
- `csv` - Spreadsheet-compatible export

### Comparison Reports

The comparison generates 5 reports (+ orphaned epics tracking):

**Report 1: Commitment Drift**
- Initiatives that were "Planned" in baseline, now "Proposed" or "Cancelled"
- Shows which commitments dropped during the quarter

**Report 2: New Work Injection**
- Initiatives that weren't "Planned" in baseline, now "Planned"
- Shows what new work was added mid-quarter

**Report 3: Epic Churn**
- Epics added or removed within each initiative
- Net change per initiative

**Report 4: Initiative Overruns** *(optional - not yet implemented)*
- **Planned:** Track initiatives delivered >20% beyond their ETA
- **Status:** Placeholder implementation - returns empty results for MVP
- **To enable:** Configure `eta` custom field and implement tracking logic
- **Note:** All other reports (1-3, 5) work without ETA tracking

**Report 5: Team Stability**
- Per-team metrics: % of epics unchanged, added, removed
- Sorted by least stable first

**Orphaned Epics Tracking:**
- Epics that were orphaned, now assigned
- Epics newly orphaned
- Epics still orphaned

### Configuration: ETA Tracking (Future Feature)

**Note:** ETA tracking is a planned feature for future implementation. The configuration below is documented for when the feature is completed.

To enable delivery predictability tracking (Reports 4-5), configure the ETA field:

```yaml
custom_fields:
  initiatives:
    rag_status: "customfield_12111"
    quarter: "customfield_12108"
    eta: "customfield_12204"  # Due Date field for ETA tracking (not yet implemented)
```

**When implemented:**
- Report 4 will show initiatives that overran their ETA
- Report 5 will include delivery rate metrics

**Current behavior:**
- Report 4 returns empty results (placeholder)
- Report 5 shows only plan stability (no delivery metrics)

### Typical Workflow

**Quarterly tracking:**

1. Capture baseline when plan stabilizes:
   ```bash
   python extract.py snapshot --label "2026-Q2-baseline"
   ```

2. Capture monthly checkpoints:
   ```bash
   python extract.py snapshot --label "2026-Q2-month1"
   python extract.py snapshot --label "2026-Q2-month2"
   ```

3. Capture end-of-quarter snapshot:
   ```bash
   python extract.py snapshot --label "2026-Q2-end"
   ```

4. Generate comparison reports:
   ```bash
   # Month 1 drift
   python extract.py compare --from "2026-Q2-baseline" --to "2026-Q2-month1"

   # Final quarter report
   python extract.py compare \
     --from "2026-Q2-baseline" \
     --to "2026-Q2-end" \
     --format markdown \
     --output ./reports/2026-Q2-final.md
   ```

**Success Metrics:**
- Capture snapshot in < 30 seconds
- Generate comparison in < 10 seconds (for 100 initiatives, 500 epics)
- Monthly leadership reports prepared in < 15 minutes

## Validate Planning

Validate initiative readiness for Proposed → Planned status transitions based on epic RAG status, team dependencies, and assignee presence.

```bash
# Validate latest extraction for Q2 2026
python validate_planning.py --quarter "26 Q2"

# Validate specific file for Q2 2026
python validate_planning.py --quarter "26 Q2" data/jira_extract_20260321.json

# Validate snapshot with multi-team filter
python validate_planning.py --quarter "26 Q2" --min-teams 2 data/snapshots/snapshot_baseline_*.json

# Generate Slack notifications for Q2 2026
python validate_planning.py --quarter "26 Q2" --slack
```

**Options:**
- `--quarter "YY QN"` - **Required.** Quarter to validate (e.g., "26 Q2"). Only initiatives matching this quarter will be validated.
- `--min-teams N` - Minimum number of teams required (default: 1, analyzes all initiatives)
  - Use this to focus on multi-team initiatives only
  - Report shows total initiatives and how many were filtered out
- `--markdown FILENAME` - Export report to markdown format (Notion-compatible)
- `--verbose` - Include verbose output with additional details
- `--slack` - Generate Slack bulk messages for manager notifications

### Slack Manager Notifications

Generate copy-paste ready messages for sending bulk Slack DMs:

```bash
# Generate Slack messages for Q2 2026
python validate_planning.py --quarter "26 Q2" --slack

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

**What It Checks:**

**Fix Data Quality (blocks planning):**
- Epic count matches Teams Involved count
- All epics have RAG status set
- Initiative has at least one epic

**Address Commitment Blockers (not ready):**
- No RED or YELLOW epics (all must be GREEN)
- Initiative has assignee
- Missing RAG status treated as RED

**Ready to Move to Planned:**
- All checks above pass
- Outputs Jira-ready issue keys for bulk update

**Bidirectional Checking:**
- Checks Proposed → Planned transitions
- Flags Planned → Proposed regressions

**Output:**

Terminal report with four sections:
1. 🔴 **Fix Data Quality** - Initiatives with data issues (epic-level detail)
2. 🟡 **Address Commitment Blockers** - Initiatives not ready (epic-level detail)
3. ✅ **Ready to Move to Planned** - Comma-separated keys for bulk Jira update
4. ⚠️  **Planned Initiatives with Issues** - Regressions to fix

**Exit codes:**
- `0` - All validations passed, initiatives ready
- `1` - Validation issues found (data quality or commitment blockers)

**Design Documentation:**

See [brainstorm document](docs/brainstorms/2026-03-21-initiative-status-validation-brainstorm.md) for design decisions and approach rationale.

## Analyze Workload

Analyze the distribution of epic work across teams to identify imbalances and ensure fair resource allocation.

```bash
# Analyze latest extraction
python analyze_workload.py

# Analyze specific file
python analyze_workload.py data/jira_extract_20260321.json

# Analyze snapshot
python analyze_workload.py data/snapshots/snapshot_baseline_*.json

# Only analyze initiatives with 2+ teams
python analyze_workload.py --min-teams 2

# Export to markdown (Notion-compatible)
python analyze_workload.py --markdown reports/workload_analysis.md

# Generate interactive HTML dashboard
python analyze_workload.py --html reports/workload_dashboard.html

# Generate Slack messages for managers
python analyze_workload.py --slack
```

**Options:**
- `--min-teams N` - Minimum number of teams required (default: 1, analyzes all initiatives)
  - Focus on multi-team initiatives where coordination is critical
  - Single-team initiatives are filtered out when N > 1
- `--markdown FILENAME` - Export detailed report to markdown format
- `--html FILENAME` - Generate interactive HTML dashboard with charts and heatmaps
- `--verbose` - Include verbose output with additional details
- `--slack` - Generate Slack bulk messages for manager notifications

### What It Analyzes

**Epic Distribution:**
- Total epics per team across all initiatives
- Epic count per initiative per team
- Identifies teams with disproportionate workload

**Initiative Participation:**
- Which initiatives each team is involved in
- Number of epics committed per initiative
- Cross-team coordination requirements

**Workload Balance:**
- Teams with highest epic counts (potential bottlenecks)
- Teams with lowest epic counts (potential capacity)
- Variance in work distribution across the organization

**Output Sections:**

1. **📊 Team Workload Summary** - Total epics per team, sorted by workload
2. **📋 Initiative Breakdown** - Per-initiative epic distribution across teams
3. **⚠️  Workload Warnings** - Teams significantly above/below average workload
4. **✅ Well-Balanced Teams** - Teams with workload close to organizational average

### Interactive HTML Dashboard

Generate a standalone HTML file with interactive visualizations:

```bash
# Generate dashboard with auto-generated filename
python analyze_workload.py --html

# Specify custom filename
python analyze_workload.py --html reports/workload_dashboard.html
```

**Dashboard Features:**
- **Interactive Bar Chart** - Team workload comparison (leading vs contributing)
  - Click bars to see initiative lists
  - Hover for detailed metrics
- **Heatmap Table** - Team contribution by strategic objective
  - Color-coded by involvement level
  - Click cells to drill down into specific initiatives
- **Summary Statistics** - Total initiatives, active teams, top contributors
- **Fully Standalone** - Single HTML file with embedded CSS and JavaScript (uses Chart.js CDN)

**Use Cases:**
- Share visual reports with stakeholders
- Present workload distribution in team meetings
- Track workload evolution over time (generate multiple snapshots)
- Identify cross-functional collaboration patterns

### Slack Manager Notifications

Generate workload summary messages for engineering managers:

```bash
python analyze_workload.py --slack
```

**Message Content:**
- Team's total epic count for the period
- Breakdown by initiative
- Comparison to organizational average
- Workload status (balanced, high, low)

**Use Cases:**
- **Quarterly Planning:** Validate work distribution before committing to plans
- **Mid-Quarter Check:** Identify teams at risk of overcommitment
- **Resource Planning:** Inform hiring and allocation decisions
- **Leadership Reports:** Provide data for executive summaries

## Advanced Configuration

### How to configure the basic properties

1. **Find your project keys:**

   **IMPORTANT:** Use project **KEYS**, not project names!

   - Project KEY: Short code like `RSK`, `INIT`, `PAY` (use this ✅)
   - Project Name: Full name like "Risk Team" (don't use ❌)

   **Where to find project keys:**
   - In Jira URLs: `https://your-company.atlassian.net/browse/RSK-123` → Key is `RSK`
   - In issue numbers: `INIT-1115` → Key is `INIT`
   - Browse all projects: `https://your-company.atlassian.net/jira/projects`

2. **Edit config/jira_config.yaml:**
   - Update `jira.instance` with your Jira URL (without https://)
   - Update `projects.initiatives` with your initiatives project key (e.g., `INIT`)
   - Update `projects.teams` with your team project keys (e.g., `["RSK", "PAY", "PLATFORM"]`)
   - Find RAG custom field ID: `python extract.py list-fields`

   Example:
   ```yaml
   jira:
     instance: "company.atlassian.net"

   projects:
     initiatives: "INIT"       # Project key, not name
     teams:
       - "RSK"                 # Use keys like RSK, not "Risk Team"
       - "PAY"
       - "PLATFORM"
   ```

3. **Edit .env:**
   - Add your Jira email
   - Get API token from: https://id.atlassian.com/manage-profile/security/api-tokens

### Custom Fields Configuration

Custom fields for initiatives are configured under `custom_fields.initiatives`:

```yaml
custom_fields:
  initiatives:
    rag_status: "customfield_12111"      # RAG status indicator
    quarter: "customfield_12108"          # Planning quarter
    objective: "customfield_12101"        # Strategic objective
    # Add any custom field here without code changes
```

**Adding New Custom Fields:**

1. Find the Jira field ID (use `python extract.py list-fields` to list available fields)
2. Add to `custom_fields.initiatives` with your desired output name
3. Run extraction - the field will appear in the output JSON

**Field Types Supported:**
- **Select fields** (e.g., RAG status) - extracted as the selected value
- **Text fields** - extracted as-is
- **Multi-select fields** (e.g., strategic objectives) - extracted as comma-separated values if multiple selected, or single value if only one

All custom fields are optional. If a field is missing on an initiative, it will appear as `null` in the output.

### User Id Configuration

Update `config/team_mappings.yaml` with Slack member IDs:

```yaml
team_managers:
  "CBPPE":
    notion_handle: "@Thom Gray"
    slack_id: "U01F3QUH30B"
  "CONSOLE":
    notion_handle: "@Antony Red"
    slack_id: "U02ABC453"
  "PAYINS":
    notion_handle: "@Thom Gray"
    slack_id: "U01F3QUH30B"  # Same Slack ID for all of Karina's teams
```

### Optional: Filter by Quarter

To extract only initiatives for a specific quarter:

1. Add the quarter custom field ID to your config:
   ```yaml
   custom_fields:
     initiatives:
       rag_status: "customfield_12111"
       quarter: "customfield_12108"  # Add this
   ```

2. Add the filters section:
   ```yaml
   filters:
     quarter: "25 Q1"  # Format: "YY QN"
   ```

When filtering is enabled:
- Only initiatives matching the specified quarter are extracted
- Initiatives with status "Done" are excluded
- Epics are still extracted for all team projects, but only those linked to filtered initiatives appear in the output

To disable filtering, simply remove or comment out the `filters` section.

### Optional: Team Names

Create `config/team_mappings.yaml` to map friendly team names to project keys:

```bash
# Copy example and customize with your team names
cp config/team_mappings.yaml.example config/team_mappings.yaml
```

Example:
```yaml
team_mappings:
  "Engineering": "ENG"
  "Product": "PROD"
  "Design": "DESIGN"
```

**Note:** This file is optional. The script works without it by using display names as-is. The mapping helps identify teams when display names differ from project keys.

### Optional: Teams exempt from RAG status checking

Some teams (i.e. Documentation team) provide supporting work and don't need to report RAG status. Configure these in `teams_exempt_from_rag`:
- They still need to create epics if listed in Teams Involved
- Their epics won't be checked for RED/YELLOW/missing RAG status
- Owner teams are automatically exempt (don't add them here)

```yaml
teams_exempt_from_rag:
  - "DOCS"
```

### Optional: Initiative Sign-Off Exceptions

Some initiatives have intentional inconsistencies that managers have explicitly approved. To exclude these from validation reports:

1. Edit `config/initiative_exceptions.yaml`:
   ```yaml
   signed_off_initiatives:
     - key: "INIT-1234"
       reason: "Team X is consultative only, no epic needed"
       date: "2026-03-31"
       approved_by: "@Manager Name"
   ```

2. Run validation - signed-off initiatives will be completely hidden:
   ```bash
   python validate_planning.py --quarter "26 Q2"
   ```

**When to use this:**
- Team listed for awareness only (no epic needed)
- Special cross-team arrangements
- Manager has explicitly approved the current state

**Required fields:**
- `key`: Initiative Jira key (e.g., "INIT-1234")
- `reason`: Explanation of why this is signed off

**Optional fields:**
- `date`: When approved (ISO format: "YYYY-MM-DD")
- `approved_by`: Manager who approved (e.g., "@Jane Smith")

**Important:** Review this file periodically to remove resolved initiatives.
