# Scan Script Documentation

Scan Jira for initiatives and epics, extracting data to JSON/CSV format for analysis with other toolkit scripts.

## Purpose

The scan script pulls data from Jira and stores it locally for offline analysis. It supports:
- JSON and CSV output formats
- Custom field extraction
- Flexible filtering by quarter, status, or custom JQL
- Configuration validation
- Field discovery

> **Experimental Feature:** See [Snapshots](snapshots.md) for snapshot capture and comparison functionality.

## Quick Start

```bash
# Extract all data to JSON
python scan.py extract

# Extract to CSV format
python scan.py extract --format csv

# Extract both formats
python scan.py extract --format both
```

## Commands

### `extract`

Extract initiatives and epics from Jira.

```bash
python scan.py extract [OPTIONS]
```

**Options:**
- `--config PATH` - Path to config file (default: `config/jira_config.yaml`)
- `--format [json|csv|both]` - Output format (default: `json`)
- `--output PATH` - Custom output file path
- `--verbose` - Enable verbose output for debugging
- `--dry-run` - Show what would be fetched without writing output
- `--status TEXT` - Filter by status (e.g., "In Progress" or "!Done" to exclude Done)
- `--quarter TEXT` - Filter by quarter (e.g., "26 Q2"). Automatically excludes Done initiatives unless --status is specified
- `--jql TEXT` - Custom JQL filter for advanced queries. When set, overrides --quarter and --status

**Examples:**

```bash
# Extract to custom location
python scan.py extract --config config/custom.yaml --output ./report.json

# Extract only In Progress initiatives
python scan.py extract --status "In Progress"

# Extract Q2 2026 initiatives (excludes Done automatically)
python scan.py extract --quarter "26 Q2"

# Extract Q2 2026 Proposed initiatives only
python scan.py extract --quarter "26 Q2" --status "Proposed"

# Use custom JQL (overrides other filters)
python scan.py extract --jql "project = INIT AND status = Planned"

# Test extraction without writing files
python scan.py extract --dry-run --verbose
```

**Output Files:**

Default output locations:
- JSON: `data/jira_extract_YYYYMMDD_HHMMSS.json`
- CSV: `data/jira_extract_YYYYMMDD_HHMMSS.csv`

### `list-fields`

List all custom fields available in your Jira instance.

```bash
python scan.py list-fields
```

**Output:**
- Field ID (e.g., `customfield_12111`)
- Field name
- Field type

**Use case:** Find custom field IDs to configure in `jira_config.yaml`.

### `validate-config`

Validate your configuration without extracting data.

```bash
python scan.py validate-config
```

**Checks:**
- Jira connection is valid
- Credentials are correct
- Projects exist and are accessible
- Custom fields are configured correctly

**Exit codes:**
- `0` - Configuration valid
- `1` - Configuration error

### `snapshot`

Capture a timestamped snapshot for comparison tracking.

See [Snapshots Documentation](snapshots.md) for details.

## Output Format

### JSON Structure

```json
{
  "metadata": {
    "timestamp": "2026-04-10T15:20:30",
    "jira_instance": "company.atlassian.net",
    "total_initiatives": 42,
    "total_epics": 156
  },
  "initiatives": [
    {
      "key": "INIT-123",
      "summary": "Initiative Title",
      "status": "Planned",
      "assignee": "John Doe",
      "owner_team": "PLATFORM",
      "teams_involved": ["PLATFORM", "SECURITY"],
      "strategic_objective": "2026_fuel_regulated",
      "quarter": "26 Q2",
      "rag_status": "Green",
      "contributing_teams": [
        {
          "team": "PLATFORM",
          "epics": [
            {
              "key": "PLAT-100",
              "summary": "Epic Title",
              "status": "In Progress",
              "rag_status": "Green"
            }
          ]
        }
      ]
    }
  ],
  "orphaned_epics": [
    {
      "key": "TEAM-50",
      "summary": "Unlinked Epic",
      "status": "In Progress"
    }
  ]
}
```

### CSV Structure

Two CSV files are generated:

**initiatives.csv:**
- One row per initiative
- All initiative fields as columns
- Contributing teams as comma-separated list

**epics.csv:**
- One row per epic
- Parent initiative key included
- Team assignment included

## Filtering Options

### By Quarter

Extract only initiatives for a specific quarter:

```bash
python scan.py extract --quarter "26 Q2"
```

**Behavior:**
- Filters initiatives where `quarter` field matches "26 Q2"
- Automatically excludes Done initiatives (unless `--status` is specified)
- Epics are extracted for all teams, but only those linked to filtered initiatives

### By Status

Extract initiatives with specific status:

```bash
# Single status
python scan.py extract --status "In Progress"

# Exclude status (using negation)
python scan.py extract --status "!Done"
```

### Combined Filters

Combine quarter and status filters:

```bash
# Q2 2026 Proposed initiatives
python scan.py extract --quarter "26 Q2" --status "Proposed"

# Q2 2026 including Done
python scan.py extract --quarter "26 Q2" --status "Planned,In Progress,Done"
```

### Custom JQL

For advanced filtering, use custom JQL:

```bash
python scan.py extract --jql "project = INIT AND labels = high-priority"
```

**Note:** When `--jql` is specified, `--quarter` and `--status` are ignored.

## Configuration

See [Configuration Reference](../guides/configuration.md#custom-fields-configuration) for detailed configuration options.

### Required Configuration

**config/jira_config.yaml:**
```yaml
jira:
  instance: "company.atlassian.net"

projects:
  initiatives: "INIT"
  teams:
    - "PLATFORM"
    - "SECURITY"
    - "PAYINS"

custom_fields:
  initiatives:
    rag_status: "customfield_12111"
    quarter: "customfield_12108"
    objective: "customfield_12101"
```

**config/.env:**
```bash
JIRA_EMAIL=your.email@company.com
JIRA_API_TOKEN=your_api_token_here
```

## Use Cases

### Quarterly Planning

Extract baseline for planning validation:

```bash
# Extract Q2 initiatives
python scan.py extract --quarter "26 Q2"

# Validate planning readiness
python check_planning.py --quarter "26 Q2"
```

### Workload Analysis

Extract current state for workload distribution:

```bash
# Extract all In Progress and Planned work
python scan.py extract

# Analyze workload for Q2
python assess_workload.py --quarter "26 Q2"
```

### Historical Analysis

Extract all initiatives including completed work:

```bash
# Include all statuses
python scan.py extract --status "Proposed,Planned,In Progress,Done"
```

### Data Quality Audits

Extract specific status for validation:

```bash
# Extract Proposed initiatives for quality check
python scan.py extract --status "Proposed"

# Validate data quality
python check_quality.py --status "Proposed"
```

## Troubleshooting

### Issue: "Authentication failed"
- **Solution:** Check `JIRA_EMAIL` and `JIRA_API_TOKEN` in `.env`
- Verify API token is valid at https://id.atlassian.com/manage-profile/security/api-tokens

### Issue: "Project not found"
- **Solution:** Verify project keys (not names) in `jira_config.yaml`
- Use project keys like `INIT`, not names like "Initiatives"

### Issue: "Custom field not found"
- **Solution:** Run `python scan.py list-fields` to find correct field IDs
- Update `custom_fields.initiatives` in `jira_config.yaml`

### Issue: "Rate limited"
- **Solution:** Jira API has rate limits. Add delays or extract less data
- Use filters (`--quarter`, `--status`) to reduce data volume

### Issue: "Empty output"
- **Solution:** Check filters - may be too restrictive
- Use `--verbose` flag to see what's being fetched
- Try `--dry-run` to preview without writing files

## Performance

**Extraction speed:**
- ~100 initiatives: 10-30 seconds
- ~500 initiatives: 30-90 seconds
- Network latency and Jira instance load affect speed

**Optimization tips:**
- Use filters to reduce data volume
- Extract during off-peak hours
- Cache extractions locally rather than re-extracting frequently

## Related Documentation

- [Snapshots](snapshots.md) - 🧪 Snapshot capture and comparison (experimental)
- [Setup Guide](../guides/setup.md) - Initial configuration
- [Configuration Reference](../guides/configuration.md) - Advanced config options
- [Check Planning](check-planning.md) - Use extracted data for planning validation
- [Assess Workload](assess-workload.md) - Use extracted data for workload analysis
