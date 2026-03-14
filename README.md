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

5. **Edit .env:**
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
- Select fields (e.g., RAG status) - extracted as the selected value
- Text fields - extracted as-is

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

Extract data:
```bash
python jira_extract.py extract
```

List custom fields:
```bash
python jira_extract.py list-fields
```

Validate config:
```bash
python jira_extract.py validate-config
```

Options:
```bash
python jira_extract.py extract --config custom.yaml --output ./report.json --verbose
```

## Output

JSON file in `./data/` directory with:
- Initiative → Team → Epics hierarchy
- Status and RAG indicators
- Completeness tracking
- Orphaned epics (no parent initiative)

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
