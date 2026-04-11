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

## Shared Validation Library

All validation scripts (`validate_planning.py`, `validate_prioritisation.py`, `analyze_workload.py`) now use a centralized validation library (`lib/validation.py`) that provides consistent data quality checks across the toolkit.

**What Gets Validated:**
- **Owner Team** - All initiatives must have an owner team assigned
- **Assignee** - Status-aware validation (P3 for Proposed, P1 for Planned/In Progress)
- **Strategic Objective** - Missing or invalid values (supports comma-separated multi-objective format)
- **Teams Involved** - All initiatives must list contributing teams
- **Missing Epics** - Teams listed in "teams_involved" must have epics (owner team exempt)
- **RAG Status** - Epics must have RAG status set (Proposed/Planned only, owner team and exempt teams excluded)

**Status-Aware Priority Escalation:**
- Proposed → Lower priority for assignee (P3) and dependencies (P2)
- Planned → Higher priority for assignee (P1) and dependencies (P1)
- In Progress → No RAG validation, but assignee and dependencies required (P1)

**Discovery Initiative Handling:**
- Initiatives with `[Discovery]` prefix skip epic and RAG validation
- Still required to have owner team and strategic objective

**Benefits:**
- Consistent validation rules across all scripts
- Single source of truth for data quality checks
- Easier to maintain and extend validation logic
- Comprehensive baseline validation (added to `validate_prioritisation.py`)

## Output Structure

All report-generating scripts (with `--html`, `--markdown`, or `--csv` options) follow a consistent output structure:

```
output/
├── workload_analysis/
│   ├── 001_workload_analysis_20260410_152030.html
│   ├── 002_workload_analysis_20260410_153045.md
│   └── 003_workload_analysis_20260410_154102.csv
├── planning_validation/
│   ├── 001_planning_validation_20260410_152030.md
│   └── 002_planning_validation_20260410_153100.md
└── prioritisation_validation/
    ├── 001_prioritisation_validation_20260410_152030.md
    └── 002_prioritisation_validation_20260410_153200.md
```

**Naming Convention:** `{progressive_number:03d}_{report_type}_{timestamp}.{extension}`

- **Progressive Number:** Auto-incremented for each report type (001, 002, 003...)
- **Report Type:** Identifier for the analysis type (e.g., `workload_analysis`, `planning_validation`)
- **Timestamp:** `YYYYMMDD_HHMMSS` format
- **Extension:** File format (`html`, `md`, `csv`, `txt`)

**Default Behavior:**
- When you use `--html`, `--markdown`, or `--csv` without specifying a filename, reports are automatically saved to the appropriate `output/` subdirectory
- You can still provide a custom filename to override the default location

**Examples:**
```bash
# Saves to output/workload_analysis/001_workload_analysis_20260410_152030.html
python analyze_workload.py --quarter "26 Q2" --html

# Saves to custom location
python analyze_workload.py --quarter "26 Q2" --html my_custom_report.html

# Generate multiple formats (each gets progressive numbering)
python analyze_workload.py --quarter "26 Q2" --html --markdown --csv
```

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
python validate_planning.py --quarter "26 Q2" --slack
```

Once Planning is done, extract data again and analyze workload per team:
```bash
python extract.py extract
python analyze_workload.py --quarter "26 Q2"
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
- `--status TEXT` - Filter by status (e.g., "In Progress" or "!Done" to exclude Done)
- `--quarter TEXT` - Filter by quarter (e.g., "26 Q2"). Automatically excludes Done initiatives unless --status is specified
- `--jql TEXT` - Custom JQL filter for advanced queries. When set, overrides --quarter and --status

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

# Validate snapshot
python validate_planning.py --quarter "26 Q2" data/snapshots/snapshot_baseline_*.json

# Generate Slack notifications for Q2 2026
python validate_planning.py --quarter "26 Q2" --slack

# Export markdown report
python validate_planning.py --quarter "26 Q2" --markdown
```

**Options:**
- `--quarter "YY QN"` - **Required.** Quarter to validate (e.g., "26 Q2"). Only initiatives matching this quarter will be validated.
- `--markdown [FILENAME]` - Export report to markdown format (Notion-compatible). Auto-generates filename if omitted.
- `--verbose` - Include verbose output with additional details
- `--slack` - Generate Slack bulk messages for manager notifications
- `json_file` - Optional path to specific data file (defaults to latest extraction)

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

## Validate Initiative Priorities

Validate team commitments to strategically prioritized initiatives and ensure teams respect relative initiative priorities. Identifies priority conflicts (teams committed to lower-priority work while skipping higher-priority initiatives) and missing commitments.

```bash
# Validate latest extraction
python validate_prioritisation.py

# Validate specific file
python validate_prioritisation.py data/jira_extract_20260408.json

# Use custom priority config
python validate_prioritisation.py --config custom_priorities.yaml

# Export markdown report (auto-generates filename)
python validate_prioritisation.py --markdown

# Export markdown with custom filename
python validate_prioritisation.py --markdown dashboard.md

# Generate Slack notifications
python validate_prioritisation.py --slack
```

**Options:**
- `--config PATH` - Custom priority config path (default: `config/priorities.yaml`)
- `--markdown [FILENAME]` - Export Initiative Health Dashboard as markdown file. Auto-generates filename if omitted.
- `--verbose` - Include verbose output with additional details
- `--slack` - Generate Slack bulk messages for manager notifications
- `data_file` - Optional path to specific data file (defaults to latest extraction)

**Priority Configuration:**

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

**What Gets Validated:**

- **Configured Initiatives:** Only initiatives listed in the priority config file
- **Active Initiatives:** Excludes Done/Cancelled initiatives
- **Non-Discovery:** Excludes `[Discovery]` prefixed initiatives
- **Excluded Teams:** Teams in `teams_excluded_from_prioritisation` (from `config/team_mappings.yaml`) are excluded from analysis
  - By default: DevOps, Security Engineering, XD
- **Commitment Definition:** Team has epic(s) with ALL epics being either:
  - Non-red RAG (green/yellow/amber), OR
  - Status = Done (work already completed)

**Report Sections:**

1. **Priority Conflicts:** Teams committed to lower-priority initiatives while skipping higher-priority ones
2. **Missing Commitments:** Teams expected to contribute (`teams_involved`) but with no green/yellow epics
3. **Initiative Health Dashboard:** Initiative-centric view of expected vs actual team commitments
4. **Action Items for Managers:** Actionable checklist grouped by responsible team

**Exit Codes:**
- `0` - No priority conflicts or missing commitments
- `1` - Conflicts or missing commitments found
- `2` - Configuration error (missing file, invalid format)

**Design Documentation:**

See [brainstorm document](docs/brainstorms/2026-04-08-tech-leadership-priority-validation-brainstorm.md) and [implementation plan](docs/plans/2026-04-08-001-feat-tech-leadership-priority-validation-plan.md) for design decisions and approach rationale.

## Analyze Workload

Analyze the distribution of epic work across teams to identify imbalances and ensure fair resource allocation.

```bash
# Analyze latest extraction for Q2 2026
python analyze_workload.py --quarter "26 Q2"

# Analyze specific file
python analyze_workload.py --quarter "26 Q2" data/jira_extract_20260321.json

# Analyze snapshot
python analyze_workload.py --quarter "26 Q2" data/snapshots/snapshot_baseline_*.json

# Show detailed data quality issues
python analyze_workload.py --quarter "26 Q2" --show-quality

# Export to CSV (auto-generates filename)
python analyze_workload.py --quarter "26 Q2" --csv

# Export to markdown with custom filename
python analyze_workload.py --quarter "26 Q2" --markdown reports/workload_analysis.md

# Generate interactive HTML dashboard (auto-generates filename)
python analyze_workload.py --quarter "26 Q2" --html

# Generate Slack messages for managers
python analyze_workload.py --quarter "26 Q2" --slack

# Verbose output with detailed initiative lists
python analyze_workload.py --quarter "26 Q2" --verbose
```

**Options:**
- `--quarter QUARTER` - **Required.** Quarter to analyze (e.g., "26 Q2"). Only initiatives with status="In Progress" or (quarter=QUARTER and status="Planned") are analyzed.
- `--html [FILENAME]` - Generate interactive HTML dashboard with charts and heatmaps. Auto-generates filename if omitted.
- `--markdown [FILENAME]` - Export detailed report to markdown format. Auto-generates filename if omitted.
- `--csv [FILENAME]` - Export initiative analysis as CSV file. Auto-generates filename if omitted.
- `--verbose` - Show detailed list of initiatives per team (leading and contributing)
- `--show-quality` - Show detailed data quality issues (missing owner, missing epics, missing objectives)
- `--slack` - Generate Slack bulk messages for workload quality action items
- `json_file` - Optional path to specific data file (defaults to latest extraction)

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
python analyze_workload.py --quarter "26 Q2" --html

# Specify custom filename
python analyze_workload.py --quarter "26 Q2" --html reports/workload_dashboard.html
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
python analyze_workload.py --quarter "26 Q2" --slack
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

### Optional: Team Exclusions

Different scripts have different exclusion needs. Configure separate exclusion lists for each use case:

#### Workload Analysis Exclusions

Teams with different workload patterns (DevOps, Integration Ops) should be excluded from workload analysis but included in validation:

```yaml
teams_excluded_from_workload_analysis:
  - "IT"
  - "Security Engineering"
  - "DevOps"
  - "Integration Ops"
```

**Used by:** `analyze_workload.py`

**Why:** These teams have different work patterns than product delivery teams and would skew workload metrics.

#### Validation Exclusions

Teams that don't follow standard epic creation process should be excluded from planning validation:

```yaml
teams_excluded_from_validation:
  - "IT"
  - "Security Engineering"
  - "SecOps"
```

**Used by:** `validate_planning.py`

**Why:** These teams don't need to create epics when listed in Teams Involved.

**Backward compatibility:** If you don't specify these lists, scripts will fall back to `teams_excluded_from_analysis` (deprecated).

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
