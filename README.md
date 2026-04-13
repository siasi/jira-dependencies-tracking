# Jira EM Toolkit

Engineering manager toolkit for Jira initiative and epic analysis, planning validation, and workload tracking.

## Overview

This toolkit helps engineering leadership manage quarterly planning, validate initiative readiness, track team workload, and monitor plan stability. It extracts data from Jira and provides automated validation, reports, and manager notifications.

## Key Features

- **Data Extraction** - Pull initiatives and epics from Jira with custom field support
- **Planning Validation** - Validate readiness for Proposed → Planned transitions
- **Data Quality Checks** - Comprehensive baseline validation with status-aware rules
- **Priority Validation** - Ensure teams respect strategic initiative priorities
- **Workload Analysis** - Analyze epic distribution and identify team imbalances
- **Snapshot Tracking** - Measure plan churn and commitment drift (experimental)
- **Manager Notifications** - Generate Slack messages with actionable items

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Jira connection:**
   ```bash
   cp config/jira_config.yaml.example config/jira_config.yaml
   cp config/.env.example config/.env
   # Edit both files with your Jira instance and credentials
   ```

3. **Extract and analyze:**
   ```bash
   # Extract data from Jira
   python extract.py extract

   # Validate planning readiness for Q2 2026
   python validate_planning.py --quarter "26 Q2"

   # Analyze team workload
   python analyze_workload.py --quarter "26 Q2"
   ```

See [Setup Guide](docs/guides/setup.md) for detailed installation instructions.

## Scripts Overview

| Script | Purpose | Documentation |
|--------|---------|---------------|
| **extract.py** | Extract initiatives and epics from Jira to JSON/CSV | [Docs](docs/scripts/extract.md) |
| **validate_planning.py** | Validate initiative readiness for Proposed → Planned status | [Docs](docs/scripts/validate-planning.md) |
| **validate_data_quality.py** | Comprehensive data quality checks with status-aware rules | [Docs](docs/scripts/validate-data-quality.md) |
| **validate_prioritisation.py** | Ensure teams respect strategic initiative priorities | [Docs](docs/scripts/validate-prioritisation.md) |
| **analyze_workload.py** | Analyze epic distribution and team workload balance | [Docs](docs/scripts/analyze-workload.md) |

## Script Scope Quick Reference

Each script validates/analyzes a specific subset of initiatives. Use this reference to understand which initiatives each script considers:

| Script | Quarter Filter | Status Filter | Notes |
|--------|---------------|---------------|-------|
| **validate_planning.py** | Required (`--quarter`) | Proposed OR Planned | Planning readiness for specific quarter |
| **validate_data_quality.py** | Optional, combinable | Flexible (see docs) | Supports complex filtering combinations |
| **validate_prioritisation.py** | None | No filtering | Only initiatives in `priorities.yaml` |
| **analyze_workload.py** | Required (`--quarter`) | In Progress OR Planned (matching quarter) | Active workload for specific quarter |

**validate_data_quality.py Filtering Options:**
- Default: In Progress (any quarter) + Planned (any quarter)
- `--quarter Q`: In Progress (any quarter) + Planned (quarter Q)
- `--status X`: Status X (any quarter)
- `--status X --quarter Q`: Status X AND quarter Q
- `--all-active`: Proposed, Planned, In Progress (any quarter)
- `--all-active --quarter Q`: Proposed, Planned, In Progress AND quarter Q

**Common Exclusions (all scripts):**
- Signed-off initiatives (`config/initiative_exceptions.yaml`)
- Teams in various `teams_excluded_from_*` lists (`config/team_mappings.yaml`)

For detailed scope information, see each script's documentation.

## Documentation

### Getting Started
- [Setup Guide](docs/guides/setup.md) - Installation and configuration
- [Configuration Reference](docs/guides/configuration.md) - Advanced config options
- [Architecture Overview](docs/ARCHITECTURE.md) - System design and structure

### Validation System
- [Validation Rules](docs/specs/validation-rules.md) - Business rules and rationale (for managers)
- [Validation Library](docs/guides/validation-library.md) - Developer guide for shared validation library

### Scripts
- [Extract Data](docs/scripts/extract.md) - Data extraction from Jira
- [Snapshots](docs/scripts/snapshots.md) - 🧪 **EXPERIMENTAL** - Snapshot tracking and comparison
- [Validate Planning](docs/scripts/validate-planning.md) - Planning readiness validation
- [Validate Data Quality](docs/scripts/validate-data-quality.md) - Comprehensive data quality checks
- [Validate Priorities](docs/scripts/validate-prioritisation.md) - Strategic priority validation
- [Analyze Workload](docs/scripts/analyze-workload.md) - Team workload analysis

### Additional Resources
- [Contributing Guide](docs/CONTRIBUTING.md) - Development guidelines
- [Strategic Objective Mappings](docs/strategic_objective_mappings.md) - Objective definitions

## Project Structure

```
jira-em-toolkit/
├── config/          # Configuration files
│   ├── jira_config.yaml        # Jira connection and project settings
│   ├── team_mappings.yaml      # Team and manager information
│   ├── initiative_exceptions.yaml  # Manager-approved exceptions
│   └── priorities.yaml         # Strategic priority order
├── lib/             # Shared toolkit utilities
│   ├── validation.py           # Shared validation library
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
│   └── comparator.py          # Snapshot comparison
├── templates/       # Jinja2 templates
├── tests/           # Test suite
├── docs/            # Documentation
│   ├── guides/     # User guides
│   ├── scripts/    # Script-specific docs
│   └── specs/      # Specifications
├── data/            # Output directory (gitignored)
├── extract.py                 # Data extraction script
├── validate_planning.py       # Planning validation script
├── validate_data_quality.py   # Data quality validation script
├── validate_prioritisation.py # Priority validation script
├── analyze_workload.py        # Workload analysis script
└── README.md
```

## Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for development guidelines and best practices.

## License

This project is internal tooling. See your organization's policies for usage guidelines.
