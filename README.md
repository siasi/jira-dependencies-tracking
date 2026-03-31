# Jira EM Toolkit

Engineering Management toolkit for Jira that helps you manage multi-team initiatives effectively.

## What is This?

A command-line toolkit that helps engineering managers:

- **Track cross-team dependencies** - Ensure all teams involved in an initiative have created their epics
- **Validate planning readiness** - Check if initiatives are ready to move from Proposed → Planned status
- **Monitor workload distribution** - Understand which teams are leading vs contributing to initiatives
- **Ensure strategic alignment** - Validate that all initiatives have valid strategic objectives
- **Measure plan stability** - Track how plans change over time with quarterly snapshots

**Built for multi-team environments** where initiatives span multiple engineering teams and coordination is critical.

## Quick Start

### Prerequisites
- Python 3.9+
- Jira Cloud access with API token

### Installation

```bash
# Clone and install dependencies
pip install -r requirements.txt

# Optional: Install as package for command aliases
pip install -e .
```

### Configure

1. **Copy configuration templates:**
   ```bash
   cp config/jira_config.yaml.example config/jira_config.yaml
   cp config/team_mappings.yaml.example config/team_mappings.yaml
   cp .env.example .env
   ```

2. **Edit `config/jira_config.yaml`:**
   - Set your Jira instance URL
   - Add your initiatives project key (e.g., `INIT`)
   - Add your team project keys (e.g., `["TEAM1", "TEAM2"]`)
   - Find custom field IDs: `python extract.py list-fields`

3. **Edit `.env`:**
   - Add your Jira email
   - Add API token from: https://id.atlassian.com/manage-profile/security/api-tokens

**Important:** Use project **KEYS** (like `RSK`, `INIT`) not project names (like "Risk Team").

## Main Scripts

The toolkit provides three main scripts for different workflows:

### 1. Extract Data (`extract.py`)

Extract initiatives and epics from Jira into JSON or CSV format.

```bash
# Extract to JSON
python extract.py extract

# Extract to CSV for spreadsheet analysis
python extract.py extract --format csv

# List available custom fields
python extract.py list-fields

# Validate your configuration
python extract.py validate-config
```

**What you get:**
- Initiative → Team → Epics hierarchy
- RAG status indicators
- Custom fields you configured
- Orphaned epics (no parent initiative)

**Output:** `data/jira_extract_YYYYMMDD_HHMMSS.json` or `.csv`

---

### 2. Validate Planning Readiness (`validate_planning.py`)

Check if initiatives are ready to move from **Proposed** → **Planned** status.

```bash
# Validate latest extraction
python validate_planning.py

# Validate specific file
python validate_planning.py data/jira_extract_20260321.json

# Only check multi-team initiatives (2+ teams)
python validate_planning.py --min-teams 2

# Export to markdown for Notion
python validate_planning.py --markdown planning-report.md

# Generate Slack DM messages via Dust
python validate_planning.py --dust
```

**What it checks:**

✅ **Data Quality (must fix first):**
- Epic count matches "Teams Involved" field
- All epics have RAG status set
- All initiatives have valid strategic objectives
- Initiative has at least one epic

✅ **Readiness for Planning (commitment blockers):**
- No RED or YELLOW epics (all must be GREEN)
- Initiative has an assignee
- No missing data

**Output:** Four sections in terminal:
1. 🔴 **Fix Data Quality** - Issues blocking validation
2. 🟡 **Address Commitment Blockers** - Not ready for planning
3. ✅ **Ready to Move to Planned** - Comma-separated Jira keys for bulk update
4. ⚠️  **Planned Initiatives with Issues** - Regressions needing attention

**Exit code:** `0` if all pass, `1` if issues found

---

### 3. Analyze Team Workload (`analyze_workload.py`)

Understand how work is distributed across teams.

```bash
# Analyze latest extraction
python analyze_workload.py

# Export to markdown
python analyze_workload.py --markdown workload-report.md

# Verbose output with initiative details
python analyze_workload.py --verbose
```

**What you get:**
- Which teams are **leading** initiatives (owner)
- Which teams are **contributing** to initiatives (have epics)
- Total initiative count per team
- Breakdown of all initiatives by team
- Data quality issues (missing owners, epics, strategic objectives)

**Use cases:**
- Capacity planning for quarterly reviews
- Identifying overloaded teams
- Finding initiatives without clear ownership
- Validating strategic objective alignment across the portfolio

**Output:** Console report or markdown file with team-by-team breakdown

---

## Advanced Features

### Snapshot Tracking

Track plan stability over time by capturing quarterly snapshots and comparing them.

**Capture a snapshot:**
```bash
python extract.py snapshot --label "2026-Q2-baseline"
```

**List snapshots:**
```bash
python extract.py snapshots list
```

**Compare two snapshots:**
```bash
python extract.py compare \
  --from "2026-Q2-baseline" \
  --to "2026-Q2-end" \
  --format markdown \
  --output reports/q2-final.md
```

**Comparison reports:**
1. **Commitment Drift** - Initiatives that dropped from "Planned"
2. **New Work Injection** - New initiatives added mid-quarter
3. **Epic Churn** - Epics added/removed per initiative
4. **Team Stability** - % of epics unchanged by team
5. **Orphaned Epics** - Tracking of unassigned epics

### Dust Manager Notifications

Generate Slack DM messages for engineering managers:

```bash
python validate_planning.py --dust
```

**Requirements:** Configure `team_mappings.yaml` with Slack member IDs:

```yaml
team_managers:
  "TEAM1":
    notion_handle: "@Manager Name"
    slack_id: "U01ABC123"
```

Messages are grouped by manager and ready to paste into Dust for bulk sending.

---

## Configuration Reference

### Project Structure

```
jira-em-toolkit/
├── config/          # Configuration files
│   ├── jira_config.yaml         # Jira connection and projects
│   ├── team_mappings.yaml       # Team names and managers
│   └── *.yaml.example           # Templates
├── lib/             # Shared utilities
├── src/             # Core domain logic
├── templates/       # Jinja2 report templates
├── tests/           # Test suite
├── docs/            # Documentation
├── data/            # Generated data (gitignored)
└── *.py             # Main scripts
```

### Configuration Files

**`config/jira_config.yaml`** - Jira connection and field mapping:
```yaml
jira:
  instance: "company.atlassian.net"

projects:
  initiatives: "INIT"
  teams:
    - "TEAM1"
    - "TEAM2"

custom_fields:
  initiatives:
    rag_status: "customfield_12111"
    strategic_objective: "customfield_12101"
    quarter: "customfield_12108"
```

**`config/team_mappings.yaml`** - Team names and managers:
```yaml
team_mappings:
  "Engineering Platform": "PLAT"
  "Risk Team": "RISK"

teams_excluded_from_analysis:
  - "IT"
  - "Security"

team_managers:
  "PLAT":
    notion_handle: "@Manager Name"
    slack_id: "U01ABC123"

teams_exempt_from_rag:
  - "DOCS"
  - "Integration Ops"
```

### Custom Fields

Add any Jira custom field to your extraction:

1. Find the field ID: `python extract.py list-fields`
2. Add to `custom_fields.initiatives` in config:
   ```yaml
   custom_fields:
     initiatives:
       my_field_name: "customfield_12345"
   ```
3. Run extraction - field appears in JSON/CSV output

**Supported field types:** Select, Text, Multi-select

### Strategic Objective Validation

Both `validate_planning.py` and `analyze_workload.py` check strategic objectives:

**Configure valid values in `config/jira_config.yaml`:**
```yaml
validation:
  strategic_objective:
    valid_values:
      - "Revenue Growth"
      - "Cost Reduction"
      - "Customer Experience"
```

**What's checked:**
- ❌ Missing strategic objective → Flagged as data quality issue
- ❌ Invalid value (not in valid_values list) → Flagged as data quality issue
- ✅ Valid objective from the list → Passes

### Teams Exempt from RAG Status

Some teams (documentation, integration ops) provide supporting work but don't need to report RAG status.

**Configure in `config/team_mappings.yaml`:**
```yaml
teams_exempt_from_rag:
  - "DOCS"
  - "Integration Ops"
```

**What this means:**
- They still need to create epics if listed in "Teams Involved"
- Their epics won't be checked for RED/YELLOW/missing RAG status
- Owner teams are automatically exempt (don't add them here)

---

## Troubleshooting

**Authentication failed:**
- Verify API token is valid and hasn't expired
- Check email matches your Atlassian account

**JQL syntax error / "Expecting either a value, list or function":**
- Use project **KEYS** (e.g., `RSK`) not names (e.g., "Risk Team")
- Verify keys exist: `https://your-company.atlassian.net/browse/RSK-1`
- Run: `python extract.py validate-config`

**Custom field not found:**
- Run: `python extract.py list-fields`
- Update field ID in `config/jira_config.yaml`

**Missing data in extraction:**
- Check `extraction_status` in output JSON
- Verify you have permissions to access all projects
- Tool continues with partial data but reports issues

---

## Migration from v1.x

If you're upgrading from an older version:

**Script names changed:**
- `jira_extract.py` → `extract.py`
- `validate_initiative_status.py` → `validate_planning.py`
- `analyze_team_workload.py` → `analyze_workload.py`

**Removed scripts (functionality merged):**
- `validate_strategic_objective.py` → Built into `validate_planning.py` and `analyze_workload.py`
- `validate_dependencies.py` → Built into `validate_planning.py`

**Configuration moved:**
```bash
mv config.yaml config/jira_config.yaml
mv team_mappings.yaml config/team_mappings.yaml
```

Scripts check root directory as fallback (with warning) if configs not in `config/`.

**Optional command aliases:**
```bash
pip install -e .

# Use short commands:
jem-extract
jem-validate-planning
jem-analyze-workload
```
