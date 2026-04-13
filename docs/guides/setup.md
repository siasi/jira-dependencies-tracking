# Setup Guide

This guide walks you through installing and configuring the Jira EM Toolkit.

## Prerequisites

- **Python 3.9 or higher**
- **Jira Cloud access** with appropriate permissions
- **API token** for Jira authentication

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs all required Python packages including:
- `jira` - Jira API client
- `pyyaml` - YAML configuration parsing
- `jinja2` - Template rendering
- `pytest` - Testing framework
- Additional utilities

### 2. Configure Jira Connection

Copy the example configuration files:

```bash
cp config/jira_config.yaml.example config/jira_config.yaml
cp config/.env.example config/.env
```

### 3. Set Up Jira Credentials

Edit `config/.env` and add your credentials:

```bash
JIRA_EMAIL=your.email@company.com
JIRA_API_TOKEN=your_jira_api_token
```

**Get your API token:**
1. Visit https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a descriptive name (e.g., "EM Toolkit")
4. Copy the token to your `.env` file

### 4. Configure Jira Instance and Projects

Edit `config/jira_config.yaml`:

#### Find Your Project Keys

**IMPORTANT:** Use project **KEYS**, not project names!

- Project KEY: Short code like `RSK`, `INIT`, `PAY` (use this ✅)
- Project Name: Full name like "Risk Team" (don't use ❌)

**Where to find project keys:**
- In Jira URLs: `https://your-company.atlassian.net/browse/RSK-123` → Key is `RSK`
- In issue numbers: `INIT-1115` → Key is `INIT`
- Browse all projects: `https://your-company.atlassian.net/jira/projects`

#### Basic Configuration

```yaml
jira:
  instance: "company.atlassian.net"  # Your Jira instance (without https://)

projects:
  initiatives: "INIT"  # Project key for initiatives
  teams:              # List of team project keys
    - "RSK"
    - "PAY"
    - "PLATFORM"
```

### 5. Configure Custom Fields

Find your custom field IDs using the list-fields command:

```bash
python scan.py list-fields
```

Add the field IDs to `config/jira_config.yaml`:

```yaml
custom_fields:
  initiatives:
    rag_status: "customfield_12111"      # RAG status indicator
    quarter: "customfield_12108"          # Planning quarter
    objective: "customfield_12101"        # Strategic objective
```

See [Configuration Reference](configuration.md) for advanced custom field configuration.

### 6. Validate Configuration

Test your configuration:

```bash
python scan.py validate-config
```

This checks:
- Jira connection is valid
- Credentials are correct
- Projects exist and are accessible
- Custom fields are configured correctly

### 7. Test Data Extraction

Try extracting data:

```bash
python scan.py extract --verbose
```

This should create a `data/jira_extract_YYYYMMDD_HHMMSS.json` file with your initiatives and epics.

## Optional: Package Installation

Install the toolkit as a Python package for easier command access:

```bash
pip install -e .
```

After installation, scripts are available as commands:

```bash
jem-scan               # Data extraction from Jira
jem-check-planning     # Planning readiness validation
jem-check-quality # Data quality validation
jem-check-priorities # Priority validation
jem-assess-workload      # Team workload analysis
```

Or continue using the scripts directly:

```bash
python scan.py
python check_planning.py
python assess_workload.py
```

## Output Directory Structure

The toolkit creates output files in organized subdirectories:

```
data/
├── jira_extract_20260410_152030.json       # Raw extractions
├── jira_extract_20260410_153045.csv
├── snapshots/                               # Snapshot files
│   ├── snapshot_baseline_20260410.json
│   └── snapshot_month1_20260410.json
└── output/                                  # Generated reports
    ├── workload_analysis/
    ├── planning_validation/
    └── prioritisation_validation/
```

## Common Setup Issues

### Issue: "Authentication failed"
- **Solution:** Verify your email and API token in `.env` are correct
- Check that your Jira account has access to the configured projects

### Issue: "Project not found"
- **Solution:** Use project **keys** (e.g., `RSK`), not names (e.g., "Risk Team")
- Verify project keys with `https://your-company.atlassian.net/jira/projects`

### Issue: "Custom field not found"
- **Solution:** Run `python scan.py list-fields` to find correct field IDs
- Update `custom_fields.initiatives` in `jira_config.yaml`

### Issue: "Permission denied"
- **Solution:** Ensure your Jira account has read access to:
  - Initiative project
  - All team projects listed in config
  - Custom fields configured

## Next Steps

1. **Configure team mappings:** See [Configuration Reference](configuration.md#team-mappings)
2. **Set up validation rules:** See [Validation Rules](../specs/validation-rules.md)
3. **Extract your first dataset:** See [Extract Script Documentation](../scripts/extract.md)
4. **Run your first validation:** See [Validate Planning Documentation](../scripts/validate-planning.md)

## Getting Help

- Check the [Configuration Reference](configuration.md) for advanced options
- Review [ARCHITECTURE.md](../ARCHITECTURE.md) for system design details
- See [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines
