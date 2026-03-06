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

4. **Edit config.yaml:**
   - Update `jira.instance` with your Jira URL
   - Update `projects.teams` with your team project keys
   - Find RAG custom field ID: `python jira_extract.py list-fields`

5. **Edit .env:**
   - Add your Jira email
   - Get API token from: https://id.atlassian.com/manage-profile/security/api-tokens

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

**Custom field not found:**
- Run `list-fields` to find correct field ID
- Update `custom_fields.rag_status` in config.yaml

**Missing data:**
- Check `extraction_status` in output JSON
- Verify permissions to access all projects
- Tool continues with partial data but reports issues
