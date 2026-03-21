# Jira Dependencies Tracking

Extract Jira initiatives and epics to analyze team contributions.

## Setup

1. **Prerequisites:** Python 3.9+, Jira Cloud access

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure:**
   ```bash
   cp config.yaml.example config.yaml
   cp .env.example .env
   ```

4. **Find your project keys:**

   **IMPORTANT:** Use project **KEYS**, not project names!

   - Project KEY: Short code like `RSK`, `INIT`, `PAY` (use this ✅)
   - Project Name: Full name like "Risk Team" (don't use ❌)

   **Where to find project keys:**
   - In Jira URLs: `https://your-company.atlassian.net/browse/RSK-123` → Key is `RSK`
   - In issue numbers: `INIT-1115` → Key is `INIT`
   - Browse all projects: `https://your-company.atlassian.net/jira/projects`

5. **Edit config.yaml:**
   - Update `jira.instance` with your Jira URL (without https://)
   - Update `projects.initiatives` with your initiatives project key (e.g., `INIT`)
   - Update `projects.teams` with your team project keys (e.g., `["RSK", "PAY", "PLATFORM"]`)
   - Find RAG custom field ID: `python jira_extract.py list-fields`

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

6. **Edit .env:**
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

1. Find the Jira field ID (use `python jira_extract.py list-fields` to list available fields)
2. Add to `custom_fields.initiatives` with your desired output name
3. Run extraction - the field will appear in the output JSON

**Field Types Supported:**
- **Select fields** (e.g., RAG status) - extracted as the selected value
- **Text fields** - extracted as-is
- **Multi-select fields** (e.g., strategic objectives) - extracted as comma-separated values if multiple selected, or single value if only one

All custom fields are optional. If a field is missing on an initiative, it will appear as `null` in the output.

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

## Usage

Extract data (JSON format):
```bash
python jira_extract.py extract
```

Extract as CSV:
```bash
python jira_extract.py extract --format csv
```

Extract both JSON and CSV:
```bash
python jira_extract.py extract --format both
```

List custom fields:
```bash
python jira_extract.py list-fields
```

Validate config:
```bash
python jira_extract.py validate-config
```

### Options

```bash
python jira_extract.py extract --config custom.yaml --output ./report.json --verbose
python jira_extract.py extract --format csv --output ./data/export.csv
```

**Available options:**
- `--config PATH` - Path to config file (default: `config.yaml`)
- `--format [json|csv|both]` - Output format (default: `json`)
- `--output PATH` - Custom output file path
- `--verbose` - Enable verbose output for debugging
- `--dry-run` - Show what would be fetched without writing output

## Snapshot Tracking

Track plan stability and delivery over time by capturing quarterly snapshots and comparing them. This helps engineering leadership measure plan churn, commitment drift, and delivery predictability.

### Capture Snapshots

Capture a timestamped snapshot with a semantic label:

```bash
# Capture baseline when plan stabilizes
python jira_extract.py snapshot --label "2026-Q2-baseline"

# Monthly checkpoints
python jira_extract.py snapshot --label "2026-Q2-month1"
python jira_extract.py snapshot --label "2026-Q2-month2"
python jira_extract.py snapshot --label "2026-Q2-end"
```

Snapshots are saved to `data/snapshots/` and include:
- All Jira data (initiatives, epics, orphaned epics)
- Metadata (timestamp, configuration, totals)
- Same filtering rules as extract command

### List Available Snapshots

View all captured snapshots:

```bash
python jira_extract.py snapshots list
```

Output shows:
- Label, timestamp, Jira instance
- Total initiatives, epics, teams

### Compare Snapshots

Generate comparison reports between two snapshots:

```bash
# Compare baseline vs current month (text output to terminal)
python jira_extract.py compare --from "2026-Q2-baseline" --to "2026-Q2-month1"

# Generate markdown report to file
python jira_extract.py compare \
  --from "2026-Q2-baseline" \
  --to "2026-Q2-end" \
  --format markdown \
  --output ./reports/q2-final.md

# Generate CSV export
python jira_extract.py compare \
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

### Configuration: ETA Tracking (Optional - Future Feature)

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
   python jira_extract.py snapshot --label "2026-Q2-baseline"
   ```

2. Capture monthly checkpoints:
   ```bash
   python jira_extract.py snapshot --label "2026-Q2-month1"
   python jira_extract.py snapshot --label "2026-Q2-month2"
   ```

3. Capture end-of-quarter snapshot:
   ```bash
   python jira_extract.py snapshot --label "2026-Q2-end"
   ```

4. Generate comparison reports:
   ```bash
   # Month 1 drift
   python jira_extract.py compare --from "2026-Q2-baseline" --to "2026-Q2-month1"

   # Final quarter report
   python jira_extract.py compare \
     --from "2026-Q2-baseline" \
     --to "2026-Q2-end" \
     --format markdown \
     --output ./reports/2026-Q2-final.md
   ```

**Success Metrics:**
- Capture snapshot in < 30 seconds
- Generate comparison in < 10 seconds (for 100 initiatives, 500 epics)
- Monthly leadership reports prepared in < 15 minutes

## Output

### JSON Format

JSON file in `./data/` directory with:
- Initiative → Team → Epics hierarchy
- Status and RAG indicators
- Completeness tracking
- Orphaned epics (no parent initiative)

### CSV Format

CSV file in `./data/` directory with denormalized structure:
- One row per epic with initiative data repeated
- Orphaned epics included with empty initiative columns
- UTF-8 encoding with BOM for Excel compatibility
- **Dynamic columns based on your configured custom fields**

**Column Structure:**

CSV columns adapt to your `custom_fields.initiatives` configuration. The column order is:

1. **Fixed initiative fields**: `initiative_key`, `initiative_summary`
2. **Custom fields** (alphabetically sorted): Whatever you configure in `config.yaml`
3. **Remaining fixed fields**: `initiative_status`, `team_project_key`, `epic_key`, `epic_summary`, `epic_rag_status`, `epic_status`

**Example with full custom fields:**

```yaml
# config.yaml
custom_fields:
  initiatives:
    quarter: "customfield_12108"
    rag_status: "customfield_12111"
    strategic_objective: "customfield_12101"
```

```csv
initiative_key,initiative_summary,quarter,rag_status,strategic_objective,initiative_status,team_project_key,epic_key,epic_summary,epic_rag_status,epic_status
INIT-1485,Initiative Title,26 Q2,🟢,growth,Proposed,CBPPE,CBPPE-529,Epic Title,🟡,Backlog
INIT-1485,Initiative Title,26 Q2,🟢,growth,Proposed,CBPPE,CBPPE-530,Another Epic,🟢,In Progress
,,,,,RSK,RSK-123,Orphaned Epic,🟡,Done
```

**Example with minimal custom fields:**

```yaml
# config.yaml
custom_fields:
  initiatives:
    rag_status: "customfield_12111"
```

```csv
initiative_key,initiative_summary,rag_status,initiative_status,team_project_key,epic_key,epic_summary,epic_rag_status,epic_status
INIT-1485,Initiative Title,🟢,Proposed,CBPPE,CBPPE-529,Epic Title,🟡,Backlog
```

**Note:** Only configured custom fields appear as columns. If a field isn't in your config, it won't be in the CSV.

**Excel Compatibility:**
- CSV files use UTF-8 with BOM encoding
- Opens correctly in Microsoft Excel, Google Sheets, and Numbers
- Emoji characters (🟢🟡🔴) preserved
- Special characters (commas, quotes, newlines) properly escaped

## Troubleshooting

**Authentication failed:**
- Verify API token is valid
- Check email matches Atlassian account

**JQL syntax error / "Expecting either a value, list or function":**
- Make sure you're using project **KEYS** (e.g., `RSK`) not project names (e.g., "Risk Team")
- Verify project keys exist: Check URLs like `https://your-company.atlassian.net/browse/RSK-1`
- Run `python jira_extract.py validate-config` to test configuration

**Custom field not found:**
- Run `list-fields` to find correct field ID
- Update `custom_fields.rag_status` in config.yaml

**Missing data:**
- Check `extraction_status` in output JSON
- Verify permissions to access all projects
- Tool continues with partial data but reports issues

## Data Validation

Validate data consistency with the included validation tools.

### Validate Team Dependencies

Check if "Teams Involved" field matches actual teams with epics:

```bash
# Validate latest extraction
python validate_dependencies.py

# Validate specific file
python validate_dependencies.py data/jira_extract_20260319.json

# Validate snapshot
python validate_dependencies.py data/snapshots/snapshot_baseline_*.json
```

**What it checks:**
- "Teams Involved" field count vs actual teams that have epics
- Identifies missing dependencies (teams in field but no epics)
- Identifies teams missing from Impacted Teams (have epics but not in field)

**Output:**
- ✅ Success: All team counts match
- ❌ Issues: Lists each initiative with mismatched counts
  - ⚠️  Missing dependencies: Teams listed but have no epics
  - ⚠️  Missing from Impacted Teams: Teams with epics not listed
- Recommendations for fixing data in Jira

**Exit codes:**
- `0` - All validations passed
- `1` - Validation issues found

**Use in CI/CD:**
```bash
# Fail build if data inconsistencies found
python jira_extract.py extract && python validate_dependencies.py
```
