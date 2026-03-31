# Jira EM Toolkit

Engineering Management toolkit for Jira that helps you manage multi-team initiatives effectively.

## Common EM Challenges This Solves

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

**Built for multi-team environments** where initiatives span multiple engineering teams and coordination is critical.

---

## Try It in 2 Minutes

**Prerequisites:** Python 3.9+, Jira Cloud access with API token

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure - Edit these 3 things:
cp config/jira_config.yaml.example config/jira_config.yaml
cp .env.example .env

# In config/jira_config.yaml: Set jira instance + project keys
# In .env: Add Jira email + API token

# 3. Run it
python extract.py extract
python validate_planning.py
```

**→ You now have a planning readiness report!**

> **Note:** Use project **KEYS** (like `RSK`, `INIT`) not names (like "Risk Team").
> See [Advanced Configuration](#advanced-configuration) section below for custom fields and detailed setup.

---

## The Workflow

```
┌─────────┐    ┌──────────┐    ┌─────────┐    ┌─────────┐
│ Extract │ →  │ Validate │ →  │ Analyze │ →  │ Report  │
└─────────┘    └──────────┘    └─────────┘    └─────────┘
   extract.py   validate_       analyze_       (markdown/
                planning.py    workload.py      dust msgs)
```

**Typical flow:**
1. **Extract** current Jira state
2. **Validate** planning readiness (are initiatives ready?)
3. **Analyze** workload distribution (who's overloaded?)
4. **Report** to stakeholders (markdown for Notion, Slack via Dust)

---

## The Three Scripts

### 1. Extract Data (`extract.py`)

**Use this when:** You need current Jira data for analysis

**What it does:** Pulls initiatives and epics from Jira, builds hierarchy, exports to JSON/CSV

**Scenario:** "I need to analyze our Q2 initiatives"

```bash
# Extract to JSON (default)
python extract.py extract

# Extract to CSV for spreadsheet analysis
python extract.py extract --format csv

# See what custom fields are available
python extract.py list-fields
```

**What you get:**
- `data/jira_extract_YYYYMMDD_HHMMSS.json` or `.csv`
- Initiative → Team → Epics hierarchy
- All configured custom fields (RAG status, strategic objective, quarter, etc.)
- Orphaned epics (no parent initiative)

---

### 2. Validate Planning Readiness (`validate_planning.py`)

**Use this when:** Before moving initiatives from "Proposed" → "Planned" status

**What it does:** Checks if initiatives are ready to commit to, identifies blockers

**Scenario 1:** "Can we commit to these initiatives in quarterly planning?"

```bash
python validate_planning.py
```

**Output:** Four sections
1. 🔴 **Fix Data Quality** - Missing epics, wrong team counts, no assignee
2. 🟡 **Address Commitment Blockers** - RED/YELLOW epics, missing RAG status
3. ✅ **Ready to Move to Planned** - Comma-separated Jira keys for bulk update
4. ⚠️  **Planned Initiatives Requiring Attention** - Regressions in committed work

**Scenario 2:** "I only care about multi-team initiatives (2+ teams)"

```bash
python validate_planning.py --min-teams 2
```

**Scenario 3:** "Generate a Notion-friendly report for leadership"

```bash
python validate_planning.py --markdown planning-report.md
```

**Scenario 4:** "Send action items to engineering managers via Slack (using Dust)"

```bash
python validate_planning.py --dust
# Outputs: data/dust_messages_YYYYMMDD_HHMMSS.txt
# Grouped by manager, ready to paste into Dust for bulk DMs
```

**What it checks:**

✅ **Data Quality Issues (blocking):**
- Epic count matches "Teams Involved" field
- All epics have RAG status set (except exempt teams)
- Initiatives have valid strategic objectives
- Each initiative has at least one epic

✅ **Commitment Blockers (not ready):**
- Any RED or YELLOW epics (all must be GREEN)
- Missing initiative assignee
- Missing RAG status (treated as blocker)

**Strategic objective validation:** Automatically checks against valid values from config. Reports missing or invalid objectives as data quality issues.

**Exit code:** `0` if ready, `1` if issues found (useful for CI/CD)

---

### 3. Analyze Team Workload (`analyze_workload.py`)

**Use this when:** Planning team capacity or reviewing workload distribution

**What it does:** Shows which teams are leading vs contributing to initiatives

**Scenario 1:** "Which teams are most loaded this quarter?"

```bash
python analyze_workload.py
```

**Output:**
- **Team Analysis Table:** Leading, Contributing, Total per team
- **Detailed Breakdown:** Every initiative listed by team
- **Issues Section:** Missing owners, missing epics, invalid strategic objectives

**Scenario 2:** "Generate a workload report for quarterly planning review"

```bash
python analyze_workload.py --markdown workload-report.md
```

**Scenario 3:** "Show me all the details - which specific initiatives each team owns"

```bash
python analyze_workload.py --verbose
```

**What you get:**
- **Leading count:** Initiatives where team is the owner
- **Contributing count:** Initiatives where team has epics but isn't owner
- **RAG status:** For contributing work (shows 🟢🟡🔴 health)
- **Data quality issues:** Same strategic objective validation as validate_planning.py

**Use cases:**
- Capacity planning: "Can this team take on more work?"
- Ownership gaps: "Which initiatives have no clear owner?"
- Strategic alignment: "Are all initiatives tied to company objectives?"
- Dependency visualization: "How many initiatives span multiple teams?"

**Strategic objective validation:** Same checks as validate_planning.py - reports missing/invalid objectives.

---

## Advanced Features

### Snapshot Tracking

**Use this when:** You want to measure plan stability over a quarter

**Scenario:** "How much did our Q2 plan change since we committed?"

```bash
# Beginning of quarter - capture baseline
python extract.py snapshot --label "2026-Q2-baseline"

# End of quarter - capture final state
python extract.py snapshot --label "2026-Q2-end"

# Generate comparison report
python extract.py compare \
  --from "2026-Q2-baseline" \
  --to "2026-Q2-end" \
  --format markdown \
  --output reports/q2-final.md
```

**Comparison reports show:**
1. **Commitment Drift** - Initiatives that dropped from "Planned"
2. **New Work Injection** - New initiatives added mid-quarter
3. **Epic Churn** - Epics added/removed per initiative
4. **Team Stability** - % of epics unchanged by team
5. **Orphaned Epics** - Tracking of unassigned epics

**Use cases:**
- Quarterly retrospectives: "How stable was our planning?"
- Leadership reporting: "Did we deliver what we committed to?"
- Process improvement: "Are we getting better at planning?"

---

### Dust Manager Notifications

**Use this when:** You need to send action items to engineering managers via Slack

**Scenario:** "Send each manager a DM with action items for their team's initiatives"

```bash
python validate_planning.py --dust
# Output: data/dust_messages_YYYYMMDD_HHMMSS.txt
```

**What you get:**
- Messages grouped by engineering manager
- Each message includes Slack member ID (`Recipient: U01ABC123`)
- Action items organized by initiative
- Multi-team managers get subsections per team
- Ready to copy-paste into Dust chatbot for bulk sending

**Action types included:**
- Missing dependencies (teams need to create epics)
- Missing RAG status (teams need to update status)
- Missing assignee (initiative needs owner)
- Ready to move to PLANNED (green light for commitment)

**Setup required:** Configure `config/team_mappings.yaml` with Slack IDs:

```yaml
team_managers:
  "TEAM1":
    notion_handle: "@Manager Name"
    slack_id: "U01ABC123"
```

---

## Command Reference

### Extract Commands

```bash
# Basic extraction
python extract.py extract                    # JSON format
python extract.py extract --format csv       # CSV format
python extract.py extract --format both      # Both formats

# Utilities
python extract.py list-fields               # Show available custom fields
python extract.py validate-config           # Test your configuration

# Snapshots
python extract.py snapshot --label "Q2-baseline"
python extract.py snapshots list
python extract.py compare --from "label1" --to "label2"

# Options
--config PATH        # Custom config file
--output PATH        # Custom output location
--verbose           # Detailed logging
--dry-run           # Show what would be fetched
```

### Validation Commands

```bash
# Basic validation
python validate_planning.py                          # Latest extraction
python validate_planning.py data/extract.json        # Specific file

# Filters
python validate_planning.py --min-teams 2            # Only multi-team initiatives

# Output formats
python validate_planning.py --markdown report.md     # Markdown export
python validate_planning.py --dust                   # Dust messages for Slack
python validate_planning.py --verbose               # Detailed output
```

### Analysis Commands

```bash
# Basic analysis
python analyze_workload.py                    # Latest extraction
python analyze_workload.py data/extract.json  # Specific file

# Output formats
python analyze_workload.py --markdown workload.md
python analyze_workload.py --verbose
```

---

## Troubleshooting

**Authentication failed:**
- Verify API token is valid: https://id.atlassian.com/manage-profile/security/api-tokens
- Check email in `.env` matches your Atlassian account

**JQL syntax error / "Expecting either a value, list or function":**
- Use project **KEYS** (e.g., `RSK`) not names (e.g., "Risk Team")
- Verify keys: Visit `https://your-company.atlassian.net/browse/RSK-1`
- Test config: `python extract.py validate-config`

**Custom field not found:**
- List available fields: `python extract.py list-fields`
- Update field ID in `config/jira_config.yaml`

**Missing data:**
- Check `extraction_status` in output JSON
- Verify you have permissions to access all projects
- Tool continues with partial data but reports issues

**"No data files found":**
- Run `python extract.py extract` first to create data
- Or specify file: `python validate_planning.py data/your-file.json`

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
JIRA_API_TOKEN=your_api_token_here  # Get from: id.atlassian.com/manage-profile/security/api-tokens
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

### Output Formats

- **JSON:** Hierarchical (Initiative → Team → Epics), all custom fields, metadata
- **CSV:** One row per epic, Excel-compatible, dynamic columns based on config
- **Markdown:** Notion-compatible, generated by `--markdown` flag

---

## Migration from v1.x

If you're upgrading from an older version:

**Script names changed:**
```
jira_extract.py           → extract.py
validate_initiative_status.py → validate_planning.py
analyze_team_workload.py  → analyze_workload.py
```

**Removed scripts** (functionality now built-in):
- `validate_strategic_objective.py` - Now built into `validate_planning.py` and `analyze_workload.py`
- `validate_dependencies.py` - Now built into `validate_planning.py`

Both validation scripts automatically check strategic objectives against configured valid values.

**Configuration moved:**
```bash
mv config.yaml config/jira_config.yaml
mv team_mappings.yaml config/team_mappings.yaml
```

Scripts check root directory as fallback (with warning) if configs not in `config/`.

**Optional command aliases:**
```bash
pip install -e .

# Short commands now available:
jem-extract
jem-validate-planning
jem-analyze-workload
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

---

## Contributing

This toolkit follows test-driven development:
- All features have tests in `tests/`
- Run tests: `pytest tests/ -v`
- Current status: 149 tests passing

See `docs/` for architecture decisions and design documentation.
