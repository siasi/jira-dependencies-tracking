# Architecture

## Directory Structure

### config/
Centralized configuration files:
- `jira_config.yaml` - Jira connection, projects, custom fields
- `team_mappings.yaml` - Team names, managers, exclusions
- `initiative_exceptions.yaml` - Manager-approved initiative exceptions
- `*.yaml.example` - Example configs for new users

### lib/
Shared toolkit utilities:
- `common_formatting.py` - Hyperlink formatting for console/markdown output
- `template_renderer.py` - Jinja2 environment and rendering helpers
- `file_utils.py` - Data file discovery and management

### src/
Core domain logic:
- `config.py` - Configuration loading with dataclasses
- `jira_client.py` - Jira API wrapper
- `fetcher.py` - Parallel data fetching
- `builder.py` - Initiative hierarchy building
- `output.py` - JSON/CSV generation
- `snapshot.py` - Quarterly snapshot management
- `comparator.py` - Snapshot comparison
- `reports.py` - Comparison reports

### Root-level Scripts
Executable analysis scripts with verb-noun naming (in root for easy access):
- `scan.py` - Extract data from Jira API
- `check_planning.py` - Validate planning readiness
- `assess_workload.py` - Analyze team workload distribution

### templates/
Jinja2 templates for output formatting:
- `planning_console.j2` / `planning_markdown.j2` - Planning validation
- `notification_dust.j2` - Dust bulk message format

## Design Principles

1. **Modularize by concern** - lib/ for utilities, src/ for domain, root for scripts
2. **Extract common code** - No duplication (DRY)
3. **Consistent interfaces** - All scripts: console default, --markdown FILENAME
4. **Template-driven output** - All formatting in Jinja2
5. **Configuration centralization** - All config in config/
6. **Clear naming** - Verb-noun for scripts, descriptive for everything else
7. **Usability first** - Scripts in root for easy execution without installation

## Data Flow

```
scan.py → data/jira_data_*.json → check_planning.py → Console/Markdown output
                                   → assess_workload.py → Console/Markdown output
```

## Testing

- Test suite: `tests/` directory with pytest
- Run tests: `pytest tests/ -v`
- 155 tests covering all modules
- Test coverage includes unit tests and integration tests

## Error Handling

- **Fail fast** on config errors (startup/validation)
- **Degrade gracefully** on data issues (runtime)
- Clear error messages with field names
- No silent failures
