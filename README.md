# Jira EM Toolkit

Engineering Management toolkit for Jira that helps you manage multi-team initiatives effectively.

## What Problems Does This Solve?

❌ **"Are all teams ready to commit to this initiative?"**
✅ Run `validate_planning.py` → Get instant readiness report with specific blockers

❌ **"Which teams are overloaded this quarter?"**
✅ Run `analyze_workload.py` → See leading vs contributing workload distribution

❌ **"Is this initiative missing dependencies?"**
✅ Run `validate_planning.py` → Find teams that need to create epics

❌ **"Did our plan change since we committed?"**
✅ Compare snapshots → Measure commitment drift and epic churn

❌ **"Do all initiatives align with company strategy?"**
✅ Both validation scripts check strategic objectives automatically

---

## Setup

### Prerequisites
- Python 3.9+
- Jira Cloud access with API token

### Installation

```bash
pip install -r requirements.txt

# Optional: Install command aliases
pip install -e .
```

### Configure

1. **Copy templates:**
   ```bash
   cp config/jira_config.yaml.example config/jira_config.yaml
   cp config/team_mappings.yaml.example config/team_mappings.yaml
   cp .env.example .env
   ```

2. **Edit `config/jira_config.yaml`:**
   ```yaml
   jira:
     instance: "company.atlassian.net"  # No https://

   projects:
     initiatives: "INIT"     # Your initiatives project KEY
     teams:                  # Your team project KEYS
       - "TEAM1"
       - "TEAM2"

   custom_fields:
     initiatives:
       rag_status: "customfield_12111"
       strategic_objective: "customfield_12101"
       quarter: "customfield_12108"
   ```

3. **Edit `.env`:**
   ```bash
   JIRA_EMAIL=your.email@company.com
   JIRA_API_TOKEN=your_token_here
   ```

4. **Find custom field IDs:**
   ```bash
   python extract.py list-fields
   ```

> **Important:** Use project **KEYS** (like `RSK`, `INIT`) not project names (like "Risk Team").

---

## Usage

Three scripts that work together:

### Extract Data
```bash
python extract.py extract
```
**What you get:** JSON/CSV file with all initiatives, epics, custom fields, and team relationships.

### Validate Planning Readiness
```bash
python validate_planning.py
```
**What you get:** Report showing which initiatives have data quality issues, commitment blockers, or are ready to move to "Planned" status.

### Analyze Team Workload
```bash
python analyze_workload.py
```
**What you get:** Breakdown of which teams are leading vs contributing to initiatives, with workload distribution metrics.

**Typical workflow:**
```
Extract data → Validate readiness → Analyze workload → Report to stakeholders
```

---

## Extract

Extract initiatives and epics from Jira into JSON or CSV format.

### Basic Usage

```bash
# Extract to JSON (default)
python extract.py extract

# Extract to CSV for spreadsheet analysis
python extract.py extract --format csv

# Extract both formats
python extract.py extract --format both
```

### Utility Commands

```bash
# List available custom fields with IDs
python extract.py list-fields

# Validate your configuration
python extract.py validate-config
```

### Options

```bash
python extract.py extract --config custom.yaml    # Use custom config
python extract.py extract --output ./data.json    # Custom output path
python extract.py extract --verbose              # Detailed logging
python extract.py extract --dry-run              # Preview without writing
```

### Output Formats

**JSON:** Hierarchical structure
- Initiative → Team → Epics hierarchy
- All configured custom fields included
- Orphaned epics (no parent initiative) tracked separately
- Metadata: extraction timestamp, Jira instance, totals
- File: `data/jira_extract_YYYYMMDD_HHMMSS.json`

**CSV:** Flat structure for spreadsheets
- One row per epic (initiative data repeated)
- Dynamic columns based on your custom field configuration
- UTF-8 with BOM for Excel compatibility
- Emoji characters preserved (🟢🟡🔴)
- File: `data/jira_extract_YYYYMMDD_HHMMSS.csv`

### Snapshots

Track plan stability over time by capturing quarterly snapshots.

#### Capture a Snapshot

```bash
# Capture baseline when plan stabilizes
python extract.py snapshot --label "2026-Q2-baseline"

# Monthly checkpoints
python extract.py snapshot --label "2026-Q2-month1"
python extract.py snapshot --label "2026-Q2-month2"
python extract.py snapshot --label "2026-Q2-end"
```

Snapshots are saved to `data/snapshots/` with:
- All Jira data (initiatives, epics, orphaned epics)
- Metadata (timestamp, configuration, totals)
- Same filtering rules as extract command

#### List Snapshots

```bash
python extract.py snapshots list
```

Shows: Label, timestamp, Jira instance, total initiatives/epics/teams

#### Compare Snapshots

Generate comparison reports between two snapshots:

```bash
# Text output to terminal
python extract.py compare --from "2026-Q2-baseline" --to "2026-Q2-month1"

# Markdown report
python extract.py compare \
  --from "2026-Q2-baseline" \
  --to "2026-Q2-end" \
  --format markdown \
  --output reports/q2-final.md

# CSV export
python extract.py compare \
  --from "2026-Q2-baseline" \
  --to "2026-Q2-end" \
  --format csv \
  --output reports/q2-comparison.csv
```

**Report formats:** `text` (default), `markdown`, `csv`

#### Comparison Reports

The comparison generates 5 reports:

1. **Commitment Drift** - Initiatives that were "Planned" in baseline, now "Proposed" or "Cancelled"
2. **New Work Injection** - Initiatives that weren't "Planned" in baseline, now "Planned"
3. **Epic Churn** - Epics added or removed within each initiative (net change per initiative)
4. **Initiative Overruns** *(future feature)* - Track initiatives delivered >20% beyond ETA
5. **Team Stability** - Per-team metrics: % of epics unchanged, added, removed (sorted by least stable)

Plus: **Orphaned Epics Tracking** (epics that became orphaned, got assigned, or stayed orphaned)

#### Typical Quarterly Workflow

```bash
# 1. Capture baseline when plan stabilizes
python extract.py snapshot --label "2026-Q2-baseline"

# 2. Capture monthly checkpoints
python extract.py snapshot --label "2026-Q2-month1"
python extract.py snapshot --label "2026-Q2-month2"

# 3. Capture end-of-quarter
python extract.py snapshot --label "2026-Q2-end"

# 4. Generate comparison reports
python extract.py compare --from "2026-Q2-baseline" --to "2026-Q2-month1"
python extract.py compare \
  --from "2026-Q2-baseline" \
  --to "2026-Q2-end" \
  --format markdown \
  --output reports/2026-Q2-final.md
```

---

## Validate Planning

Check if initiatives are ready to move from **Proposed** → **Planned** status.

### Basic Usage

```bash
# Validate latest extraction
python validate_planning.py

# Validate specific file
python validate_planning.py data/jira_extract_20260321.json

# Validate snapshot
python validate_planning.py data/snapshots/snapshot_baseline_*.json
```

### Options

```bash
# Only check multi-team initiatives (2+ teams)
python validate_planning.py --min-teams 2

# Export to markdown (Notion-compatible)
python validate_planning.py --markdown planning-report.md

# Verbose output with additional details
python validate_planning.py --verbose

# Generate Dust messages for Slack DMs
python validate_planning.py --dust
```

### What It Checks

#### Data Quality (must fix first):
- ✅ Epic count matches "Teams Involved" field
- ✅ All epics have RAG status set (except exempt teams)
- ✅ All initiatives have valid strategic objectives
- ✅ Each initiative has at least one epic
- ✅ Initiative has an assignee

#### Commitment Blockers (readiness):
- ✅ No RED or YELLOW epics (all must be GREEN)
- ✅ No missing RAG status (treated as blocker)
- ✅ Strategic objective is valid (checked against config)

### Output

Terminal report with four sections:

1. **🔴 Fix Data Quality** - Issues blocking validation (epic-level detail)
   - Missing epics for teams involved
   - Wrong team counts
   - No assignee
   - Missing/invalid strategic objectives

2. **🟡 Address Commitment Blockers** - Not ready for planning (epic-level detail)
   - RED or YELLOW epics
   - Missing RAG status

3. **✅ Ready to Move to Planned** - Comma-separated Jira keys for bulk update
   - All checks passed
   - Ready for commitment

4. **⚠️ Planned Initiatives Requiring Attention** - Regressions in committed work
   - Initiatives that moved from Planned back to Proposed
   - Planned initiatives with new blockers

**Exit code:** `0` if all pass, `1` if issues found (useful for CI/CD)

### Output Formats

**Console:** Terminal-friendly with ANSI hyperlinks (clickable Jira links)

**Markdown:** Notion-compatible format with tables and links
```bash
python validate_planning.py --markdown report.md
```

**Dust Messages:** Grouped by engineering manager for Slack DMs
```bash
python validate_planning.py --dust
# Output: data/dust_messages_YYYYMMDD_HHMMSS.txt
```

### Strategic Objective Validation

Automatically validates strategic objectives against configured values.

**Configuration required in `config/jira_config.yaml`:**
```yaml
validation:
  strategic_objective:
    valid_values:
      - "Revenue Growth"
      - "Cost Reduction"
      - "Customer Experience"
```

**What's checked:**
- ❌ Missing strategic objective → Data quality issue
- ❌ Invalid value (not in list) → Data quality issue
- ✅ Valid objective from list → Passes

### Dust Notifications

Generate Slack DM messages for engineering managers.

**Setup:** Configure `config/team_mappings.yaml` with Slack IDs:
```yaml
team_managers:
  "TEAM1":
    notion_handle: "@Manager Name"
    slack_id: "U01ABC123"
```

**Usage:**
```bash
python validate_planning.py --dust
```

**Output:**
- Messages grouped by manager
- Each message includes Slack member ID (`Recipient: U01ABC123`)
- Action items organized by initiative
- Multi-team managers get subsections per team
- Ready to paste into Dust chatbot

**Action types included:**
- Missing dependencies (teams need to create epics)
- Missing RAG status (teams need to update status)
- Missing assignee (initiative needs owner)
- Ready to PLANNED (green light for commitment)

---

## Analyze Workload

Understand team capacity and initiative distribution.

### Basic Usage

```bash
# Analyze latest extraction
python analyze_workload.py

# Analyze specific file
python analyze_workload.py data/jira_extract_20260321.json
```

### Options

```bash
# Export to markdown
python analyze_workload.py --markdown workload-report.md

# Verbose output with initiative details
python analyze_workload.py --verbose
```

### What You Get

#### Team Analysis Table
Shows for each team:
- **Leading count:** Initiatives where team is the owner
- **Contributing count:** Initiatives where team has epics but isn't owner
- **Total:** Sum of leading + contributing

Sorted by total (most loaded teams first)

#### Detailed Breakdown by Team
For each team:
- List of leading initiatives with summaries
- List of contributing initiatives with RAG status (🟢🟡🔴)
- Team manager information (if configured)

#### Issues Section
Data quality problems:
- Initiatives without owner_team
- Initiatives with missing epics for teams involved
- Missing strategic objectives
- Invalid strategic objectives

### Output Formats

**Console:** Terminal-friendly with tables and clickable links

**Markdown:** Notion-compatible report with tables
```bash
python analyze_workload.py --markdown workload.md
```

### Use Cases

**Capacity Planning:**
- "Can this team take on more work?"
- "Which teams are bottlenecks?"

**Ownership Gaps:**
- "Which initiatives have no clear owner?"
- "Are all teams engaged?"

**Strategic Alignment:**
- "Are all initiatives tied to company objectives?"
- "Which initiatives need strategic objective updates?"

**Dependency Visualization:**
- "How many initiatives span multiple teams?"
- "Which teams collaborate most?"

### Strategic Objective Validation

Same validation as `validate_planning.py`:
- Checks against configured valid values
- Reports missing objectives as data quality issues
- Reports invalid objectives as data quality issues

See [Advanced Configuration](#advanced-configuration) for setup.

---

## Advanced Configuration

### Configuration Files

Two config files in `config/` directory:

#### 1. `config/jira_config.yaml` - Jira Connection & Fields

```yaml
jira:
  instance: "company.atlassian.net"  # Your Jira URL (no https://)

projects:
  initiatives: "INIT"                # Initiatives project key
  teams:                             # Team project keys
    - "TEAM1"
    - "TEAM2"
    - "PLATFORM"

custom_fields:
  initiatives:
    rag_status: "customfield_12111"           # RAG status indicator
    strategic_objective: "customfield_12101"  # Strategic objective
    quarter: "customfield_12108"              # Planning quarter
    # Add any custom field here

# Strategic objective validation
validation:
  strategic_objective:
    valid_values:
      - "Revenue Growth"
      - "Cost Reduction"
      - "Customer Experience"
      # Add your company's strategic objectives
```

**Finding custom field IDs:**
```bash
python extract.py list-fields
# Look for field names, copy the customfield_XXXXX ID
```

#### 2. `config/team_mappings.yaml` - Team Names & Managers

```yaml
# Map friendly team names to Jira project keys
team_mappings:
  "Engineering Platform": "PLAT"
  "Risk Team": "RISK"

# Teams to exclude from analysis (support teams, IT, etc.)
teams_excluded_from_analysis:
  - "IT"
  - "Security"

# Engineering managers (for Dust notifications)
team_managers:
  "PLAT":
    notion_handle: "@Manager Name"
    slack_id: "U01ABC123"           # Get from Slack user profile
  "RISK":
    notion_handle: "@Another Manager"
    slack_id: "U02DEF456"

# Teams that don't need RAG status (docs, integration ops, etc.)
teams_exempt_from_rag:
  - "DOCS"
  - "Integration Ops"
```

**Notes:**
- `team_mappings`: Optional, helps display friendly names
- `teams_excluded_from_analysis`: Won't appear in workload reports
- `team_managers`: Required for `--dust` notifications
- `teams_exempt_from_rag`: Supporting teams that provide work but don't need RAG status
- Owner teams are automatically exempt from RAG checks

#### 3. `.env` - Credentials

```bash
JIRA_EMAIL=your.email@company.com
JIRA_API_TOKEN=your_token_here  # Get from: id.atlassian.com/manage-profile/security/api-tokens
```

### Finding Project Keys

**Always use project KEYS** (`RSK`, `INIT`) **not names** ("Risk Team", "Initiatives").

Find keys in:
- Jira URLs: `company.atlassian.net/browse/RSK-123` → `RSK`
- Issue keys: `INIT-1115` → `INIT`
- All projects: `company.atlassian.net/jira/projects`

### Adding Custom Fields

1. `python extract.py list-fields` - Find field ID
2. Add to config: `my_field: "customfield_12345"`
3. Run extraction - appears in output

Supports: Select, Text, Multi-select fields. Missing fields = `null`.

### Optional: Command Aliases

```bash
pip install -e .

# Short commands:
jem-extract
jem-validate-planning
jem-analyze-workload
```

---

## Migration from v1.x

If upgrading from an older version:

**Script names changed:**
```
jira_extract.py           → extract.py
validate_initiative_status.py → validate_planning.py
analyze_team_workload.py  → analyze_workload.py
```

**Removed scripts** (functionality now built-in):
- `validate_strategic_objective.py` → Built into `validate_planning.py` and `analyze_workload.py`

**Configuration moved:**
```bash
mv config.yaml config/jira_config.yaml
mv team_mappings.yaml config/team_mappings.yaml
```

---

## Project Structure

```
jira-em-toolkit/
├── config/              # Configuration
│   ├── jira_config.yaml
│   ├── team_mappings.yaml
│   └── *.yaml.example   # Templates
├── lib/                 # Shared utilities
├── src/                 # Core domain logic
├── templates/           # Jinja2 report templates
├── tests/               # Test suite
├── docs/                # Documentation
├── data/                # Generated data (gitignored)
│   ├── jira_extract_*.json
│   ├── jira_extract_*.csv
│   └── snapshots/
├── extract.py           # Main scripts
├── validate_planning.py
└── analyze_workload.py
```
