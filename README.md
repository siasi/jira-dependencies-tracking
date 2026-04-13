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
   python scan.py extract

   # Validate planning readiness for Q2 2026
   python check_planning.py --quarter "26 Q2"

   # Analyze team workload
   python assess_workload.py --quarter "26 Q2"
   ```

See [Setup Guide](docs/guides/setup.md) for detailed installation instructions.

## Scripts Overview

| Script | Purpose | Documentation |
|--------|---------|---------------|
| **scan.py** | Extract initiatives and epics from Jira to JSON/CSV | [Docs](docs/scripts/scan.md) |
| **check_planning.py** | Validate initiative readiness for Proposed → Planned status | [Docs](docs/scripts/check-planning.md) |
| **check_quality.py** | Comprehensive data quality checks with status-aware rules | [Docs](docs/scripts/check-quality.md) |
| **check_priorities.py** | Ensure teams respect strategic initiative priorities | [Docs](docs/scripts/check-priorities.md) |
| **assess_workload.py** | Analyze epic distribution and team workload balance | [Docs](docs/scripts/assess-workload.md) |

## Script Scope Quick Reference

Each script validates/analyzes a specific subset of initiatives. Use this reference to understand which initiatives each script considers:

| Script | Quarter Filter | Status Filter | Notes |
|--------|---------------|---------------|-------|
| **check_planning.py** | Required (`--quarter`) | Proposed OR Planned | Planning readiness for specific quarter |
| **check_quality.py** | Optional, combinable | Flexible (see docs) | Supports complex filtering combinations |
| **check_priorities.py** | None | No filtering | Only initiatives in `priorities.yaml` |
| **assess_workload.py** | Required (`--quarter`) | In Progress OR Planned (matching quarter) | Active workload for specific quarter |

**check_quality.py Filtering Options:**
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
- [Scan Data](docs/scripts/scan.md) - Data extraction from Jira
- [Snapshots](docs/scripts/snapshots.md) - 🧪 **EXPERIMENTAL** - Snapshot tracking and comparison
- [Check Planning](docs/scripts/check-planning.md) - Planning readiness validation
- [Check Quality](docs/scripts/check-quality.md) - Comprehensive data quality checks
- [Check Priorities](docs/scripts/check-priorities.md) - Strategic priority validation
- [Assess Workload](docs/scripts/assess-workload.md) - Team workload analysis

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
├── scan.py                    # Data extraction script
├── check_planning.py          # Planning validation script
├── check_quality.py           # Data quality validation script
├── check_priorities.py        # Priority validation script
├── assess_workload.py         # Workload analysis script
└── README.md
```

## Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for development guidelines and best practices.

## License

This project is internal tooling. See your organization's policies for usage guidelines.
