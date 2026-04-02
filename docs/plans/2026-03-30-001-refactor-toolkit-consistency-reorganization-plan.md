---
title: Toolkit Consistency & Reorganization
type: refactor
status: active
date: 2026-03-30
origin: docs/brainstorms/2026-03-30-toolkit-consistency-brainstorm.md
---

# Toolkit Consistency & Reorganization

## Overview

Refactor the Jira analysis toolkit from organic flat structure into an intentionally-designed hierarchical organization with consistent naming, centralized configuration, extracted common code, and standardized output formats. This establishes a solid foundation before adding new capabilities like individual manager features.

**Origin:** See brainstorm document for complete context and decisions: docs/brainstorms/2026-03-30-toolkit-consistency-brainstorm.md

## Problem Statement / Motivation

The toolkit has evolved from a single script (jira_extract.py) into multiple analysis scripts serving different use cases (planning validation, workload analysis, dependency checking). This organic growth has created inconsistencies:

1. **Naming chaos**: No consistent pattern (jira_extract.py vs validate_initiative_status.py)
2. **Configuration sprawl**: Config files scattered in root directory
3. **Code duplication**: `make_clickable_link()` function duplicated in 4 files
4. **Output inconsistency**: Some scripts use --markdown to write files, others to change stdout
5. **Template gaps**: Some scripts use Jinja2, others have inline formatting
6. **Unclear structure**: New contributors can't easily understand organization

These issues will compound as new scripts are added. Cleaning up now prevents technical debt.

**Use cases affected:**
- Planning validation (validate_initiative_status.py) - includes dependency checking
- Workload analysis (analyze_team_workload.py)
- Strategic objective validation (validate_strategic_objective.py)
- Data extraction (jira_extract.py)

**Note:** validate_dependencies.py is being removed - its functionality is a subset of validate_initiative_status.py (dependency checking is already part of planning validation)

## Proposed Solution

Reorganize repository into clear hierarchy following established Python project conventions:

```
jira-em-toolkit/  (renamed from jira-dependencies-tracking)
├── config/                     # Centralized configuration
│   ├── jira_config.yaml       # Jira connection and project settings
│   ├── team_mappings.yaml     # Team and manager information
│   └── *.yaml.example         # Example configs for new users
├── lib/                        # Shared toolkit utilities
│   ├── __init__.py            # Package marker
│   ├── common_formatting.py   # Hyperlinks, formatting utils
│   ├── template_renderer.py   # Jinja2 setup and rendering
│   └── file_utils.py          # Data file discovery
├── src/                        # Core domain logic (unchanged)
│   ├── config.py              # Configuration loading
│   ├── jira_client.py         # Jira API wrapper
│   ├── fetcher.py             # Data fetching
│   ├── builder.py             # Hierarchy building
│   ├── output.py              # JSON/CSV output
│   ├── snapshot.py            # Snapshot management
│   ├── comparator.py          # Snapshot comparison
│   └── reports.py             # Report generation
├── templates/                  # Jinja2 templates (existing location)
│   ├── planning_console.j2    # Renamed from console.j2
│   ├── planning_markdown.j2   # Renamed from markdown.j2
│   ├── workload_console.j2    # New (extracted)
│   ├── workload_markdown.j2   # New (extracted)
│   └── notification_dust.j2   # Renamed from dust.j2
├── tests/                      # Test suite (update imports)
├── docs/                       # Documentation (existing)
├── data/                       # Output directory (existing, gitignored)
├── extract.py                  # Was jira_extract.py (renamed in place)
├── validate_planning.py        # Was validate_initiative_status.py (renamed in place)
├── analyze_workload.py         # Was analyze_team_workload.py (renamed in place)
├── validate_objective.py       # Was validate_strategic_objective.py (renamed in place)
├── setup.py                    # Updated for new structure
├── requirements.txt            # Dependencies (unchanged)
└── README.md                   # Updated documentation
```

**Key Changes:**
1. **Verb-noun script naming**: Scripts renamed in place (stay in root for usability)
2. **Config centralization**: All *.yaml files move to config/
3. **Common code extraction**: Duplicated code moves to lib/
4. **Remove redundant script**: validate_dependencies.py removed (functionality in validate_planning.py)
5. **Consistent outputs**: All scripts support --markdown FILE, all use hyperlinks
6. **Template standardization**: All scripts use Jinja2, descriptive template names

**Usability decision:** Scripts stay in root directory (not moved to scripts/) to avoid the `python scripts/` prefix. Clean organization is achieved through lib/ and config/ directories while keeping scripts easily accessible.

## Technical Approach

### Phase 1: Create Directory Structure (Low Risk)

**Goal:** Establish new directories without moving files yet

**Steps:**
```bash
# Create new directories
mkdir -p config lib

# Create package marker
touch lib/__init__.py

# Verify structure
tree -L 1 -d
```

**Files created:**
- `lib/__init__.py` (empty file to make lib/ a Python package)

**Tests:** None needed yet

**Success criteria:**
- [ ] config/ and lib/ directories exist
- [ ] lib/__init__.py exists

### Phase 2: Extract Common Code to lib/ (Medium Risk)

**Goal:** Consolidate duplicated code before moving scripts

This is done BEFORE moving scripts to avoid import path complexity.

#### 2.1: Extract Hyperlink Formatting

**Currently duplicated in:**
- validate_initiative_status.py:56-82
- analyze_team_workload.py:~similar location
- validate_strategic_objective.py:~similar location
- tests/test_console_template_formatting.py:11

**Action:** Create lib/common_formatting.py

```python
# lib/common_formatting.py
"""Common formatting utilities for console and markdown output."""

def make_clickable_link(text: str, url: str) -> str:
    """Create clickable hyperlink using ANSI escape codes for terminal output.

    Args:
        text: Display text for the link
        url: URL to link to

    Returns:
        String with ANSI escape codes for clickable terminal link

    Example:
        >>> make_clickable_link("INIT-123", "https://jira.example.com/browse/INIT-123")
        '\x1b]8;;https://jira.example.com/browse/INIT-123\x1b\\INIT-123\x1b]8;;\x1b\\'
    """
    if not url:
        return text
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def make_markdown_link(text: str, url: str) -> str:
    """Create markdown-formatted hyperlink.

    Args:
        text: Display text for the link
        url: URL to link to

    Returns:
        Markdown link string

    Example:
        >>> make_markdown_link("INIT-123", "https://jira.example.com/browse/INIT-123")
        '[INIT-123](https://jira.example.com/browse/INIT-123)'
    """
    if not url:
        return text
    return f"[{text}]({url})"
```

**Update all scripts to use:**
```python
from lib.common_formatting import make_clickable_link

# Remove local make_clickable_link() function definitions
```

**Files modified:**
- lib/common_formatting.py (new)
- validate_initiative_status.py (import added, function removed)
- analyze_team_workload.py (import added, function removed)
- validate_strategic_objective.py (import added, function removed)
- tests/test_console_template_formatting.py (import updated)

**Tests:**
```bash
# Run existing tests to verify nothing broke
pytest tests/test_console_template_formatting.py -v
```

#### 2.2: Extract Template Rendering

**Currently repeated pattern:**
```python
from jinja2 import Environment, FileSystemLoader

template_dir = Path(__file__).parent / 'templates'
env = Environment(
    loader=FileSystemLoader(str(template_dir)),
    trim_blocks=True,
    lstrip_blocks=True
)
env.filters['hyperlink'] = make_clickable_link
template = env.get_template('console.j2')
```

**Action:** Create lib/template_renderer.py

```python
# lib/template_renderer.py
"""Jinja2 template rendering with common filters and configuration."""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from .common_formatting import make_clickable_link, make_markdown_link


def get_template_environment() -> Environment:
    """Create configured Jinja2 environment with toolkit-specific filters.

    Returns:
        Configured Jinja2 Environment instance
    """
    # Template directory is at project root
    template_dir = Path(__file__).parent.parent / 'templates'

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(['html', 'xml']),
        trim_blocks=True,
        lstrip_blocks=True
    )

    # Register custom filters
    env.filters['hyperlink'] = make_clickable_link
    env.filters['markdown_link'] = make_markdown_link

    return env


def render_console_template(template_name: str, **context) -> str:
    """Render a console template with provided context.

    Args:
        template_name: Name of template file (e.g., 'planning_console.j2')
        **context: Template variables

    Returns:
        Rendered template string
    """
    env = get_template_environment()
    template = env.get_template(template_name)
    return template.render(**context)


def render_markdown_template(template_name: str, **context) -> str:
    """Render a markdown template with provided context.

    Args:
        template_name: Name of template file (e.g., 'planning_markdown.j2')
        **context: Template variables

    Returns:
        Rendered template string
    """
    env = get_template_environment()
    template = env.get_template(template_name)
    return template.render(**context)
```

**Update scripts to use:**
```python
from lib.template_renderer import render_console_template, render_markdown_template

# Replace Jinja2 Environment setup with:
output = render_console_template('planning_console.j2',
                                  result=result,
                                  json_file=json_file,
                                  verbose=args.verbose)
```

**Files modified:**
- lib/template_renderer.py (new)
- All scripts using templates (simplified template rendering)

**Tests:**
```bash
# Run all tests
pytest tests/ -v
```

#### 2.3: Extract Data File Discovery

**Currently repeated pattern:**
```python
# Find most recent JSON file if not specified
if not data_file:
    json_files = sorted(Path('data').glob('jira_data_*.json'), reverse=True)
    if not json_files:
        print("No data files found. Run jira_extract.py first.")
        sys.exit(1)
    data_file = json_files[0]
```

**Action:** Create lib/file_utils.py

```python
# lib/file_utils.py
"""File utilities for data file discovery and management."""

from pathlib import Path
from typing import Optional
import sys


def find_most_recent_data_file(data_dir: Path = Path('data'),
                                 pattern: str = 'jira_data_*.json') -> Optional[Path]:
    """Find the most recently created data file matching pattern.

    Args:
        data_dir: Directory to search in (default: data/)
        pattern: Glob pattern for files (default: jira_data_*.json)

    Returns:
        Path to most recent file, or None if no files found
    """
    if not data_dir.exists():
        return None

    files = sorted(data_dir.glob(pattern), reverse=True)
    return files[0] if files else None


def get_data_file_or_exit(data_file_arg: Optional[Path] = None,
                           data_dir: Path = Path('data'),
                           pattern: str = 'jira_data_*.json') -> Path:
    """Get data file from argument or auto-discover, exit if not found.

    Args:
        data_file_arg: Explicitly specified data file path (optional)
        data_dir: Directory to search in for auto-discovery
        pattern: Glob pattern for auto-discovery

    Returns:
        Path to data file

    Exits:
        If no data file found (either explicitly or via auto-discovery)
    """
    if data_file_arg:
        if not data_file_arg.exists():
            print(f"Error: Data file not found: {data_file_arg}")
            sys.exit(1)
        return data_file_arg

    # Auto-discover
    data_file = find_most_recent_data_file(data_dir, pattern)
    if not data_file:
        print(f"No data files found in {data_dir}/. Run extract.py first.")
        sys.exit(1)

    return data_file
```

**Update scripts to use:**
```python
from lib.file_utils import get_data_file_or_exit

# Replace file discovery logic with:
data_file = get_data_file_or_exit(args.data_file)
```

**Files modified:**
- lib/file_utils.py (new)
- All scripts that discover data files

**Tests:**
```bash
pytest tests/ -v
```

**Success criteria for Phase 2:**
- [ ] lib/common_formatting.py created with make_clickable_link()
- [ ] lib/template_renderer.py created with template helpers
- [ ] lib/file_utils.py created with file discovery
- [ ] All scripts updated to import from lib/
- [ ] All local duplicate functions removed
- [ ] All tests pass (pytest tests/ -v)
- [ ] No import errors when running scripts

### Phase 3: Move Configuration Files (Low Risk)

**Goal:** Centralize all configuration in config/

**Steps:**
```bash
# Move config files
mv config.yaml config/jira_config.yaml
mv team_mappings.yaml config/team_mappings.yaml

# Copy examples
cp config/jira_config.yaml config/jira_config.yaml.example
cp config/team_mappings.yaml config/team_mappings.yaml.example

# Update .gitignore
echo "config/*.yaml" >> .gitignore
echo "!config/*.yaml.example" >> .gitignore
```

**Update config loading in src/config.py:**
```python
def get_config_dir() -> Path:
    """Get config directory relative to project root."""
    # From src/config.py, go up one level to root, then into config/
    return Path(__file__).parent.parent / 'config'


def load_config(config_name: str = 'jira_config.yaml') -> dict:
    """Load YAML config from config directory."""
    config_path = get_config_dir() / config_name
    if not config_path.exists():
        # Fallback to root directory for backwards compatibility
        fallback_path = Path(__file__).parent.parent / config_name
        if fallback_path.exists():
            print(f"Warning: Using config from root directory. Please move to config/")
            config_path = fallback_path
        else:
            raise ConfigError(f"Config file not found: {config_name}")

    # ... existing loading logic
```

**Update all scripts that load team_mappings.yaml:**
```python
from pathlib import Path

def load_team_mappings():
    """Load team mappings from config directory."""
    config_dir = Path(__file__).parent.parent / 'config'
    mappings_file = config_dir / 'team_mappings.yaml'

    # Fallback to root for backwards compatibility
    if not mappings_file.exists():
        mappings_file = Path(__file__).parent.parent / 'team_mappings.yaml'
        if mappings_file.exists():
            print("Warning: Using team_mappings.yaml from root. Please move to config/")

    # ... existing loading logic
```

**Files modified:**
- config/jira_config.yaml (moved from root)
- config/team_mappings.yaml (moved from root)
- config/*.yaml.example (new)
- src/config.py (updated paths with fallback)
- scripts/*.py (updated team_mappings.yaml loading)
- .gitignore (updated patterns)

**Tests:**
```bash
# Verify config loading still works
python -c "from src.config import load_config; print(load_config())"

# Run all tests
pytest tests/ -v
```

**Success criteria:**
- [ ] config/jira_config.yaml exists and loads correctly
- [ ] config/team_mappings.yaml exists and loads correctly
- [ ] config/*.yaml.example files created
- [ ] Backwards compatibility: root-level configs still work with warning
- [ ] All tests pass
- [ ] .gitignore updated

### Phase 4: Rename Scripts and Remove Redundant (Low Risk)

**Goal:** Rename scripts in place with verb-noun naming, remove validate_dependencies.py

**Important:** Scripts stay in root directory for usability - no import path changes needed!

#### 4.1: Remove Redundant Script First

**Action:** Remove validate_dependencies.py (functionality already in validate_initiative_status.py)

```bash
# Document why we're removing it
echo "validate_dependencies.py removed - functionality is subset of validate_initiative_status.py" > CHANGELOG.md

# Remove the file
git rm validate_dependencies.py

# Commit
git commit -m "refactor: remove validate_dependencies.py (redundant)

Functionality already exists in validate_initiative_status.py which checks
Teams Involved count vs actual teams with epics as part of planning validation.

No need to maintain duplicate script.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

#### 4.2: Update setup.py

**Action:** Update setup.py with new script names (but same locations - root directory)

```python
# setup.py
from setuptools import setup, find_packages

setup(
    name='jira-em-toolkit',  # Renamed from jira-dependencies-tracking
    version='2.0.0',  # Major version bump for restructure
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'requests>=2.31.0',
        'click>=8.1.7',
        'pyyaml>=6.0.1',
        'python-dotenv>=1.0.0',
        'Jinja2>=3.1.2',
    ],
    entry_points={
        'console_scripts': [
            # New script names (all in root directory)
            'jem-extract=extract:main',
            'jem-validate-planning=validate_planning:main',
            'jem-analyze-workload=analyze_workload:main',
            'jem-validate-objective=validate_objective:main',
        ],
    },
    python_requires='>=3.9',
)
```

**Note:** Added `jem-*` command prefix (Jira EM Toolkit) for consistency. Scripts reference root-level modules since they stay in root.

#### 4.3: Rename Scripts One at a Time

**Order:** Start with least critical script first (validate_strategic_objective.py)

**For each script:**

1. **Rename file:**
```bash
git mv validate_strategic_objective.py validate_objective.py
```

2. **Test:**
```bash
# Test direct execution
python validate_objective.py --help

# Run tests
pytest tests/ -v

# Test with real data
python validate_objective.py
```

3. **Commit:**
```bash
git commit -m "refactor: rename validate_strategic_objective.py to validate_objective.py

- Shorter, follows verb-noun pattern
- No import changes needed (stays in root)
- All tests passing

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

**Repeat for each script:**
- analyze_team_workload.py → analyze_workload.py
- validate_initiative_status.py → validate_planning.py
- jira_extract.py → extract.py

**Files renamed:**
- extract.py (was jira_extract.py)
- validate_planning.py (was validate_initiative_status.py)
- analyze_workload.py (was analyze_team_workload.py)
- validate_objective.py (was validate_strategic_objective.py)

**Files removed:**
- validate_dependencies.py (redundant functionality)

**Files modified:**
- setup.py (entry_points updated to new names)

**Tests after each rename:**
```bash
pytest tests/ -v
python <new_script_name>.py --help
```

**Success criteria:**
- [ ] validate_dependencies.py removed
- [ ] All scripts renamed to verb-noun pattern
- [ ] Scripts stay in root directory (easy to run)
- [ ] setup.py entry_points updated
- [ ] All tests pass after each rename
- [ ] Manual smoke test of each script passes

### Phase 5: Rename and Organize Templates (Low Risk)

**Goal:** Give templates descriptive names matching their usage

**Current templates:**
- templates/console.j2 (used by validate_initiative_status.py)
- templates/markdown.j2 (used by validate_initiative_status.py)
- templates/dust.j2 (used by validate_initiative_status.py)

**Actions:**
```bash
# Rename templates
git mv templates/console.j2 templates/planning_console.j2
git mv templates/markdown.j2 templates/planning_markdown.j2
git mv templates/dust.j2 templates/notification_dust.j2

# Check if analyze_workload.py needs templates extracted
# Currently uses inline formatting - extract to templates
```

**Extract analyze_workload.py formatting to templates:**

Create templates/workload_console.j2:
```jinja2
{# Template for workload analysis console output #}
Team Analysis
=============

{% for team, data in team_workload.items() %}
{{ team }} - @{{ managers[team].notion_handle }} - {{ data.total }} total initiatives
  Strategic Objectives:
  {% for obj, count in data.objectives.items() %}
  - {{ obj }}: {{ count }}
  {% endfor %}
{% endfor %}

{# ... rest of template #}
```

Create templates/workload_markdown.j2:
```jinja2
# Team Workload Analysis

| Team | Manager | Total Initiatives | Strategic Objectives |
|------|---------|-------------------|---------------------|
{% for team, data in team_workload.items() %}
| {{ team }} | {{ managers[team].notion_handle }} | {{ data.total }} | {{ data.objectives|join(', ') }} |
{% endfor %}

{# ... rest of template #}
```

**Update scripts to use new template names:**
```python
# validate_planning.py
output = render_console_template('planning_console.j2', ...)

# analyze_workload.py
output = render_console_template('workload_console.j2', ...)
```

**Files modified:**
- templates/planning_console.j2 (renamed from console.j2)
- templates/planning_markdown.j2 (renamed from markdown.j2)
- templates/notification_dust.j2 (renamed from dust.j2)
- templates/workload_console.j2 (new, extracted from analyze_workload.py)
- templates/workload_markdown.j2 (new, extracted from analyze_workload.py)
- validate_planning.py (template name updated)
- analyze_workload.py (converted to use templates)

**Tests:**
```bash
pytest tests/ -v

# Manual test each script
python validate_planning.py
python analyze_workload.py --markdown /tmp/test.md
```

**Success criteria:**
- [ ] All templates renamed descriptively
- [ ] analyze_workload.py uses templates (no inline formatting)
- [ ] All scripts reference correct template names
- [ ] All tests pass
- [ ] Manual smoke tests pass

### Phase 6: Standardize Output Options (Medium Risk)

**Goal:** Make --markdown behavior consistent across all scripts

**Current inconsistency:**
- Some scripts: --markdown FILE (writes to file)
- Some scripts: --markdown (changes stdout format)

**Standard behavior (from brainstorm):**
- Default: Console output with ANSI hyperlinks
- --markdown FILE: Write markdown to specified file
- Remove: Any --markdown flags that just change stdout format

**Scripts to update:**
- validate_planning.py
- analyze_workload.py
- validate_objective.py

**Note:** validate_dependencies.py was removed in Phase 4

**For each script:**

```python
import argparse

parser = argparse.ArgumentParser(description='...')
parser.add_argument('--markdown', type=str, metavar='FILE',
                   help='Write markdown report to FILE instead of console output')
parser.add_argument('--data-file', type=str,
                   help='Path to JSON data file (default: most recent in data/)')

args = parser.parse_args()

# Load data
data_file = get_data_file_or_exit(Path(args.data_file) if args.data_file else None)

# Generate output
if args.markdown:
    # Markdown mode
    output = render_markdown_template('planning_markdown.j2', ...)
    with open(args.markdown, 'w') as f:
        f.write(output)
    print(f"Markdown report written to {args.markdown}")
else:
    # Console mode (default)
    output = render_console_template('planning_console.j2', ...)
    print(output)
```

**Remove deprecated options:**
- Remove any flags that conflict with standardized behavior
- Update help text to reflect new standard
- Add deprecation warnings if removing user-facing options

**Files modified:**
- validate_planning.py (--markdown standardized)
- analyze_workload.py (--markdown standardized)
- validate_objective.py (--markdown standardized)

**Tests:**
```bash
# Test default console output
python validate_planning.py

# Test markdown output to file
python validate_planning.py --markdown /tmp/test.md
cat /tmp/test.md  # Verify markdown written

# Verify all tests pass
pytest tests/ -v
```

**Success criteria:**
- [ ] All scripts use --markdown FILE consistently
- [ ] Default output is console with hyperlinks
- [ ] Markdown writes to file, not stdout
- [ ] Help text consistent across all scripts
- [ ] All tests pass
- [ ] Manual tests verify behavior

### Phase 7: Repository Rename (Low Risk)

**Goal:** Rename repository to jira-em-toolkit

**Steps:**
```bash
# Update README.md
sed -i '' 's/jira-dependencies-tracking/jira-em-toolkit/g' README.md

# Update any documentation references
find docs/ -name '*.md' -exec sed -i '' 's/jira-dependencies-tracking/jira-em-toolkit/g' {} +

# Update setup.py (already done in Phase 4)

# Update git remote (if applicable)
# This is usually done via GitHub/GitLab UI for repository settings
```

**GitHub rename steps:**
1. Go to repository Settings
2. Rename repository to `jira-em-toolkit`
3. Update local remote:
```bash
git remote set-url origin https://github.com/YOUR_ORG/jira-em-toolkit.git
```

**Files modified:**
- README.md (all references updated)
- docs/**/*.md (all references updated)
- Any hardcoded paths in scripts (search for old name)

**Tests:**
```bash
# Grep for old name
rg "jira-dependencies-tracking" --type md

# Should only appear in historical context, not as current references
```

**Success criteria:**
- [ ] README.md references new name
- [ ] Documentation updated
- [ ] No stray references to old name (except in git history)
- [ ] Remote URL updated if applicable

### Phase 8: Update Documentation (Low Risk)

**Goal:** Document new structure and migration path

**Files to update:**

#### README.md

Add sections:
```markdown
## Project Structure

```
jira-em-toolkit/
├── config/          # Configuration files
├── lib/             # Shared toolkit utilities
├── src/             # Core domain logic
├── scripts/         # Executable analysis scripts
├── templates/       # Jinja2 templates
├── tests/           # Test suite
├── docs/            # Documentation
└── data/            # Generated data (gitignored)
```

## Installation

```bash
# Install in development mode
pip install -e .

# Scripts available as commands:
jem-extract               # Data extraction from Jira
jem-validate-planning     # Planning readiness validation
jem-analyze-workload      # Team workload analysis
jem-validate-objective    # Strategic objective validation
```

Or use the renamed scripts directly:
```bash
python extract.py
python validate_planning.py
python analyze_workload.py
python validate_objective.py
```

## Migration from v1.x

**Script names have changed:**
- `jira_extract.py` → `extract.py` (or use `jem-extract` command)
- `validate_initiative_status.py` → `validate_planning.py` (or use `jem-validate-planning`)
- `analyze_team_workload.py` → `analyze_workload.py` (or use `jem-analyze-workload`)
- `validate_strategic_objective.py` → `validate_objective.py` (or use `jem-validate-objective`)
- `validate_dependencies.py` → **Removed** (functionality included in `validate_planning.py`)

**Configuration files moved:**
```bash
mv config.yaml config/jira_config.yaml
mv team_mappings.yaml config/team_mappings.yaml
```

Scripts will check root directory as fallback with a warning if configs not found in config/.
```

#### docs/ARCHITECTURE.md (new file)

```markdown
# Architecture

## Directory Structure

### config/
Centralized configuration files:
- `jira_config.yaml` - Jira connection, projects, custom fields
- `team_mappings.yaml` - Team names, managers, exclusions
- `*.yaml.example` - Example configs for new users

### lib/
Shared toolkit utilities:
- `common_formatting.py` - Hyperlink formatting for console/markdown
- `template_renderer.py` - Jinja2 environment and rendering helpers
- `file_utils.py` - Data file discovery and management

### src/
Core domain logic (unchanged from v1.x):
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
- `extract.py` - Extract data from Jira API
- `validate_planning.py` - Validate planning readiness
- `analyze_workload.py` - Analyze team workload distribution
- `validate_objective.py` - Validate strategic objectives

### templates/
Jinja2 templates for output formatting:
- `planning_console.j2` / `planning_markdown.j2` - Planning validation
- `workload_console.j2` / `workload_markdown.j2` - Workload analysis
- `notification_dust.j2` - Dust bulk message format

## Design Principles

1. **Modularize by concern** - lib/ for utilities, src/ for domain, root for scripts
2. **Extract common code** - No duplication (DRY)
3. **Consistent interfaces** - All scripts: console default, --markdown FILE
4. **Template-driven output** - All formatting in Jinja2
5. **Configuration centralization** - All config in config/
6. **Clear naming** - Verb-noun for scripts, descriptive for everything else
7. **Usability first** - Scripts in root for easy execution without installation
```

#### docs/CONTRIBUTING.md (new file)

```markdown
# Contributing

## Adding a New Script

When adding a new analysis script:

1. **Naming**: Use verb-noun pattern (e.g., `report_blockers.py`, `track_velocity.py`)
2. **Location**: Place in root directory (for easy execution)
3. **Imports**: Use `from lib.X import Y` for shared utilities
4. **Templates**: Create `<name>_console.j2` and `<name>_markdown.j2` in templates/
5. **Output**: Support `--markdown FILE` option for markdown output
6. **Hyperlinks**: Use `make_clickable_link()` from `lib.common_formatting`
7. **Data loading**: Use `get_data_file_or_exit()` from `lib.file_utils`
8. **Tests**: Add tests in `tests/test_<name>.py`
9. **Documentation**: Update README.md with new command

## Code Standards

Follow guidelines in CLAUDE.md:
- Write tests for all code
- Use type hints
- Prefer functional style
- No code duplication
- Clear error messages
```

**Files created/modified:**
- README.md (updated with new structure and migration guide)
- docs/ARCHITECTURE.md (new, comprehensive architecture documentation)
- docs/CONTRIBUTING.md (new, contribution guidelines)

**Tests:**
```bash
# Verify docs render correctly (if using mkdocs or similar)
# Otherwise just manual review
```

**Success criteria:**
- [ ] README.md updated with new structure
- [ ] Migration guide added to README.md
- [ ] ARCHITECTURE.md created
- [ ] CONTRIBUTING.md created
- [ ] All links in documentation work
- [ ] No references to old structure (except in migration section)

### Phase 9: Final Testing and Cleanup (Critical)

**Goal:** Comprehensive end-to-end testing and cleanup

#### 9.1: Comprehensive Test Suite

```bash
# Run full test suite
pytest tests/ -v --tb=short

# Test each script manually with real data
python extract.py --help
python extract.py  # Extract fresh data

python validate_planning.py
python validate_planning.py --markdown /tmp/planning.md

python analyze_workload.py
python analyze_workload.py --markdown /tmp/workload.md

python validate_objective.py

# Test via installed commands (if pip install -e . done)
jem-extract --help
jem-validate-planning --help
jem-analyze-workload --help
jem-validate-objective --help
```

#### 9.2: Smoke Test Checklist

Create tests/smoke_test.sh:
```bash
#!/bin/bash
set -e

echo "=== Smoke Test Suite ==="

echo "1. Testing data extraction..."
python extract.py --help > /dev/null

echo "2. Testing planning validation..."
python validate_planning.py --help > /dev/null

echo "3. Testing workload analysis..."
python analyze_workload.py --help > /dev/null

echo "4. Testing objective validation..."
python validate_objective.py --help > /dev/null

echo "5. Testing installed commands (if available)..."
if command -v jem-extract &> /dev/null; then
    jem-extract --help > /dev/null
    echo "   jem-extract: OK"
fi

echo "7. Testing config loading..."
python -c "from src.config import load_config; load_config()"

echo "8. Testing template rendering..."
python -c "from lib.template_renderer import get_template_environment; get_template_environment()"

echo "9. Testing file utils..."
python -c "from lib.file_utils import find_most_recent_data_file; find_most_recent_data_file()"

echo "10. Testing common formatting..."
python -c "from lib.common_formatting import make_clickable_link; print(make_clickable_link('TEST', 'http://example.com'))"

echo ""
echo "=== All Smoke Tests Passed ==="
```

Run smoke tests:
```bash
chmod +x tests/smoke_test.sh
./tests/smoke_test.sh
```

#### 9.3: Code Quality Checks

```bash
# Check for any remaining duplication
rg "def make_clickable_link" --type py
# Should only appear in lib/common_formatting.py and tests

# Check for old import patterns
rg "Path\(__file__\)\.parent / 'templates'" --type py
# Should not appear (all should use lib/template_renderer.py)

# Check for hardcoded old paths
rg "jira-dependencies-tracking" --type py
# Should not appear except in comments/documentation

# Check for TODO comments introduced during refactor
rg "TODO|FIXME|HACK" --type py
# Review and address any found
```

#### 9.4: Cleanup Temporary Files

```bash
# Remove any .pyc files
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +

# Remove any backup files created during refactor
find . -name "*.bak" -delete
find . -name "*~" -delete

# Verify .gitignore is correct
cat .gitignore
# Should include:
# data/
# config/*.yaml
# !config/*.yaml.example
# *.pyc
# __pycache__/
```

#### 9.5: Documentation Review

```bash
# Verify all docs render correctly
for file in docs/**/*.md README.md; do
    echo "Checking $file..."
    # Check for broken markdown links
    grep -n '\[.*\]()' "$file" && echo "  Warning: Empty link found"
done

# Verify examples in documentation are accurate
# Manually test command examples from README.md
```

**Success criteria:**
- [ ] All pytest tests pass
- [ ] All smoke tests pass
- [ ] No code duplication found
- [ ] No old import patterns found
- [ ] No hardcoded old paths found
- [ ] No unaddressed TODO/FIXME comments
- [ ] Cleanup complete (no .pyc, .bak files)
- [ ] .gitignore correct
- [ ] Documentation renders correctly
- [ ] Manual end-to-end test successful

### Phase 10: Remove Backwards Compatibility (Future)

**Goal:** Clean up symlinks and fallback logic after transition period

**When:** After 2-3 months, when users have migrated

**Steps:**
```bash
# Remove symlinks
rm jira_extract.py
rm validate_initiative_status.py
rm analyze_team_workload.py
rm validate_strategic_objective.py

# Remove fallback config loading in src/config.py
# Remove root directory checks and warnings

# Remove legacy entry_points from setup.py
# Keep only jem-* commands

# Update documentation to remove migration notes
```

**Not included in this plan** - this is future work

## System-Wide Impact

### Import Path Changes

**Critical interaction:** Scripts moving from root → scripts/ changes all import paths

**Files affected:**
- All scripts (5 files): Must update relative path references
- All tests (11 files): Must update import statements if they import scripts directly
- setup.py: Must update entry_points to point to scripts.module_name

**Mitigation:**
- Use sys.path.insert(0, parent_dir) temporarily in scripts during migration
- Test imports after each script move
- Run full test suite after each phase
- Commit after each successful script move (atomic changes)

### Configuration Loading

**Chain reaction:**
1. Config files move to config/
2. src/config.py must update paths
3. All scripts that load team_mappings.yaml must update
4. Tests that use config must update fixture paths

**Error propagation:**
- If config loading breaks, all scripts fail immediately (fail fast - good!)
- Fallback logic provides safety net during transition
- Clear error messages guide users to move configs

### Template Rendering

**State lifecycle:**
- Template paths change from ./templates to ../templates (relative to scripts/)
- lib/template_renderer.py centralizes path logic
- All scripts must switch from direct Jinja2 usage to lib/template_renderer

**Risks:**
- If template paths wrong, rendering fails silently or with Jinja2 error
- Must test rendering after template moves

**Mitigation:**
- Centralize template path logic in lib/template_renderer.py
- Test rendering in Phase 5 before proceeding
- Use absolute paths (project_root/templates) not relative

### API Surface Changes

**Entry points (console commands):**
- Old: `jira-extract`, `validate-initiative-status`, etc.
- New: `jem-extract`, `jem-validate-planning`, etc.
- Keep legacy aliases temporarily for backwards compatibility

**Direct script execution:**
- Old: `python validate_initiative_status.py`
- New: `python scripts/validate_planning.py`
- Symlinks provide compatibility

**No API parity issues** - all interfaces updated together in Phase 4

### Integration Test Scenarios

#### Scenario 1: Full Workflow After Refactor

```bash
# Extract data
jem-extract --quarter 2026-Q2

# Validate planning
jem-validate-planning --markdown planning_report.md

# Analyze workload
jem-analyze-workload --markdown workload_report.md

# Expected: All commands work, reports generated correctly
```

**What this catches:** Import errors, config loading issues, template rendering failures, file discovery problems

#### Scenario 2: Direct Script Execution

```bash
# Use renamed scripts directly (without pip install)
python extract.py --quarter 2026-Q2
python validate_planning.py --markdown test.md

# Expected: Works without any installation, scripts run from root directory
```

**What this catches:** Import paths work correctly from root, no sys.path hacks needed

#### Scenario 3: Config in Both Locations

```bash
# Have configs in both root and config/
cp config/jira_config.yaml jira_config.yaml

# Run script
jem-extract

# Expected: Uses config/ version with fallback warning for root version
```

**What this catches:** Config loading priority, fallback logic, warning messages

#### Scenario 4: Template Usage Across Scripts

```bash
# Test each script's template rendering
jem-validate-planning  # Uses planning_console.j2
jem-analyze-workload   # Uses workload_console.j2

jem-validate-planning --markdown test1.md  # Uses planning_markdown.j2
jem-analyze-workload --markdown test2.md   # Uses workload_markdown.j2

# Expected: All render correctly with hyperlinks
```

**What this catches:** Template path issues, filter registration, template naming consistency

#### Scenario 5: Data File Auto-Discovery

```bash
# Extract multiple times to create multiple data files
jem-extract --quarter 2026-Q1
jem-extract --quarter 2026-Q2

# Run analysis without specifying file
jem-validate-planning  # Should use most recent

# Expected: Auto-discovers newest data file correctly
```

**What this catches:** File discovery logic from lib/file_utils.py, path issues with data/ directory

## Acceptance Criteria

### Functional Requirements

- [ ] All scripts renamed to verb-noun pattern (stay in root for usability)
- [ ] validate_dependencies.py removed (redundant functionality)
- [ ] All configuration files in config/ directory
- [ ] Common code extracted to lib/ (no duplication)
- [ ] All templates in templates/ with descriptive names
- [ ] All scripts use Jinja2 templates (no inline formatting)
- [ ] --markdown FILE behavior consistent across all scripts
- [ ] All scripts support ANSI hyperlinks in console output
- [ ] setup.py updated with new entry_points (jem-* commands)
- [ ] Config loading supports both locations (config/ and root) with warnings

### Non-Functional Requirements

- [ ] All existing tests pass without modification (except import updates)
- [ ] No performance regression (scripts run same speed or faster)
- [ ] Clear deprecation warnings for old usage patterns
- [ ] Documentation complete and accurate
- [ ] Migration path clear for existing users

### Quality Gates

- [ ] All pytest tests pass (pytest tests/ -v)
- [ ] All smoke tests pass (./tests/smoke_test.sh)
- [ ] No code duplication detected (rg checks pass)
- [ ] No broken imports (manual test of all scripts)
- [ ] No broken templates (all output formats tested)
- [ ] No hardcoded old paths remaining
- [ ] Code review approval (self-review against checklist)
- [ ] Documentation review complete

## Success Metrics

**Quantitative:**
- Test coverage maintained or improved (currently high for src/ modules)
- Zero test failures after refactor
- All 4 scripts working correctly (extract, validate_planning, analyze_workload, validate_objective)
- All 4 output formats working (console, markdown, CSV where applicable, Dust)

**Qualitative:**
- New contributors can understand structure from README
- Clear where to add new scripts (root directory, verb-noun naming)
- Clear where shared code goes (lib/ directory)
- Consistent command-line interface across all tools
- Professional naming aligns with "engineering manager toolkit" branding

## Dependencies & Risks

### Dependencies

**None** - This is internal refactoring with no external dependencies

**Internal sequencing:**
- Phase 2 must complete before Phase 4 (extract common code before renaming scripts)
- Phase 3 must complete before Phase 4 (config paths must work before scripts renamed)
- Phase 4 must complete before Phase 5 (scripts renamed before template references updated)

### Risks & Mitigation

#### Risk 1: Import Path Breakage (LOW - mitigated by keeping scripts in root)

**Impact:** Scripts fail to import src/ or lib/ modules

**Probability:** Low (scripts stay in root, import paths unchanged)

**Mitigation:**
- Scripts stay in root directory - no import path changes needed
- Test imports after Phase 2 (lib/ creation)
- Keep commits atomic (one script renamed at a time)
- Have rollback plan (git revert)

**Contingency:**
If imports break:
1. Verify lib/__init__.py exists
2. Check sys.path includes current directory
3. Revert last commit if needed: `git revert HEAD`

#### Risk 2: Test Suite Breakage (MEDIUM)

**Impact:** Tests fail due to updated imports or paths

**Probability:** Medium during Phases 2-4

**Mitigation:**
- Run tests after each phase
- Update test imports as scripts move
- Keep test fixtures simple (minimal hardcoded paths)

**Contingency:**
If tests fail:
1. Identify which tests are failing
2. Update test imports/paths
3. Re-run until passing
4. Don't proceed to next phase until green

#### Risk 3: User Disruption (LOW)

**Impact:** Existing users' workflows break

**Probability:** Low (backwards compatibility provided)

**Mitigation:**
- Symlinks preserve old script names
- Legacy entry_points preserve old commands
- Config fallback logic supports root directory
- Clear migration documentation

**Contingency:**
If users report issues:
1. Extend backwards compatibility period
2. Add more detailed migration guide
3. Defer Phase 10 (symlink removal)

#### Risk 4: Template Rendering Failure (LOW)

**Impact:** Reports generate incorrectly or not at all

**Probability:** Low during Phase 5

**Mitigation:**
- Centralize template path logic in lib/template_renderer.py
- Test rendering after template moves
- Manual verification of output formats

**Contingency:**
If rendering breaks:
1. Check template paths in lib/template_renderer.py
2. Verify template files in correct location
3. Test Jinja2 environment setup
4. Revert template renames if needed

## Future Considerations

After this refactor is complete and stable, consider:

1. **Individual Manager Features (Theme 4 from brainstorm)**
   - Add --team option to filter by team
   - Personalized views for engineering managers
   - Already has strong foundation after this refactor

2. **Data Extraction Strategy (Theme 3 from brainstorm)**
   - Modify extract.py to always fetch all statuses
   - Move filtering logic into processing scripts
   - Single source of truth JSON file

3. **Configuration Splitting**
   - Split team_mappings.yaml into:
     - config/teams.yaml (team mappings)
     - config/managers.yaml (manager info)
     - config/strategic_objectives.yaml (objective mappings)
   - Cleaner separation of concerns

4. **Plugin Architecture**
   - Allow new scripts to be added as plugins
   - Standardized interfaces for analysis scripts
   - Discovery mechanism for available analyses

5. **Web Interface**
   - Flask/FastAPI web UI for non-technical users
   - Interactive reports with drill-down
   - Schedule automated report generation

## Documentation Plan

### Files to Create

1. **docs/ARCHITECTURE.md** - Complete architecture documentation (Phase 8)
2. **docs/CONTRIBUTING.md** - Contribution guidelines for new scripts (Phase 8)
3. **tests/smoke_test.sh** - Automated smoke test suite (Phase 9)

### Files to Update

1. **README.md** - New structure, installation, migration guide (Phase 8)
2. **CLAUDE.md** - Update if project conventions change (Phase 8)
3. **setup.py** - Entry points and package structure (Phase 4)
4. **.gitignore** - Config directory patterns (Phase 3)

### In-Code Documentation

1. **Docstrings** - All new lib/ modules need comprehensive docstrings (Phase 2)
2. **Comments** - Explain any non-obvious refactoring decisions (All phases)
3. **Type hints** - Maintain type hints throughout (All phases)

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-03-30-toolkit-consistency-brainstorm.md](docs/brainstorms/2026-03-30-toolkit-consistency-brainstorm.md)
  - Key decisions carried forward:
    - Rename to jira-em-toolkit
    - Verb-noun script naming pattern
    - Hierarchy: config/, lib/, scripts/, templates/
    - Extract common code to lib/ to eliminate duplication
    - Standardize --markdown FILE behavior
    - Defer individual manager features until after cleanup

### Internal References

**Repository research findings:**
- Current structure: src/ modules, root-level scripts, templates/ directory
- Already modular: src/ contains reusable library code
- Testing: pytest with 11 test files, comprehensive coverage
- Templates: Already using Jinja2 for console, markdown, Dust formats
- Configuration: Already externalized in YAML files
- CLI: Using Click framework in jira_extract.py

**Key patterns identified:**
- Hyperlink function duplicated in 4 files → Extract to lib/common_formatting.py
- Template setup repeated → Extract to lib/template_renderer.py
- File discovery repeated → Extract to lib/file_utils.py
- Config loading in multiple places → Centralize path logic

**Existing file locations:**
- Scripts: /Users/stefano.iasi/git/jira-dependencies-tracking/*.py (root level)
- Library: /Users/stefano.iasi/git/jira-dependencies-tracking/src/
- Templates: /Users/stefano.iasi/git/jira-dependencies-tracking/templates/
- Tests: /Users/stefano.iasi/git/jira-dependencies-tracking/tests/
- Docs: /Users/stefano.iasi/git/jira-dependencies-tracking/docs/

### Institutional Learnings

**CLI Error Handling Pattern:**
- Source: docs/solutions/code-quality/cli-error-handling-duplication.md
- Pattern: Extract common code to shared helpers during refactoring
- Validation: All 79 tests passed after refactor
- Principle: DRY when consolidating code into lib/

**Import Path Strategy:**
- No PYTHONPATH manipulation detected in current code
- setup.py uses find_packages() for package discovery
- Pattern: Absolute imports from packages, relative imports within packages

**Backwards Compatibility Decision (answered open question):**
- Use symlinks in root for transition period
- Add deprecation warnings pointing to new locations
- Keep legacy entry_points in setup.py temporarily
- Remove after 2-3 month transition (Phase 10 - future work)

### Tool Documentation

- Python packaging: [Python Packaging User Guide](https://packaging.python.org/)
- setuptools entry_points: [setuptools documentation](https://setuptools.pypa.io/en/latest/userguide/entry_point.html)
- Jinja2 templates: [Jinja2 Template Designer Documentation](https://jinja.palletsprojects.com/templates/)
- pytest: [pytest documentation](https://docs.pytest.org/)

### Related Work

**Current repository state:**
- README.md: 567 lines, comprehensive
- CLAUDE.md: Coding standards and workflow
- Tests: 11 files with good coverage of core modules

**Previous refactoring:**
- Already modularized src/ vs scripts
- Already using templates/ directory
- Already using dataclasses for config
- This refactor builds on existing good patterns

## Implementation Checklist

Use this as you work through the refactor:

### Phase 1: Create Structure
- [ ] mkdir config lib
- [ ] touch lib/__init__.py
- [ ] Verify directories created

### Phase 2: Extract Common Code
- [ ] Create lib/common_formatting.py with make_clickable_link()
- [ ] Create lib/template_renderer.py with template helpers
- [ ] Create lib/file_utils.py with file discovery
- [ ] Update all scripts to import from lib/
- [ ] Remove duplicate functions from scripts
- [ ] Run pytest tests/ -v (all pass)

### Phase 3: Move Configuration
- [ ] mv config.yaml config/jira_config.yaml
- [ ] mv team_mappings.yaml config/team_mappings.yaml
- [ ] Create config/*.yaml.example files
- [ ] Update src/config.py with fallback logic
- [ ] Update scripts for team_mappings.yaml loading
- [ ] Update .gitignore
- [ ] Run pytest tests/ -v (all pass)

### Phase 4: Rename Scripts and Remove Redundant
- [ ] Remove validate_dependencies.py (redundant), commit
- [ ] Update setup.py with new entry_points
- [ ] Rename validate_strategic_objective.py → validate_objective.py
- [ ] Test, commit
- [ ] Rename analyze_team_workload.py → analyze_workload.py
- [ ] Test, commit
- [ ] Rename validate_initiative_status.py → validate_planning.py
- [ ] Test, commit
- [ ] Rename jira_extract.py → extract.py
- [ ] Test, commit
- [ ] Run pytest tests/ -v (all pass)

### Phase 5: Organize Templates
- [ ] Rename console.j2 → planning_console.j2
- [ ] Rename markdown.j2 → planning_markdown.j2
- [ ] Rename dust.j2 → notification_dust.j2
- [ ] Create workload_console.j2
- [ ] Create workload_markdown.j2
- [ ] Update scripts to use new template names
- [ ] Update analyze_workload.py to use templates
- [ ] Run pytest tests/ -v (all pass)
- [ ] Manual smoke test each script

### Phase 6: Standardize Output
- [ ] Update validate_planning.py --markdown behavior
- [ ] Update analyze_workload.py --markdown behavior
- [ ] Update validate_objective.py --markdown behavior
- [ ] Remove deprecated output options
- [ ] Run pytest tests/ -v (all pass)
- [ ] Test markdown output for each script

### Phase 7: Rename Repository
- [ ] Update README.md references
- [ ] Update docs/ references
- [ ] Update setup.py name (already done in Phase 4)
- [ ] Rename on GitHub/GitLab (if applicable)
- [ ] Update git remote URL
- [ ] Search for stray old name references

### Phase 8: Update Documentation
- [ ] Update README.md with structure, installation, migration
- [ ] Create docs/ARCHITECTURE.md
- [ ] Create docs/CONTRIBUTING.md
- [ ] Verify documentation renders correctly
- [ ] Verify all examples are accurate

### Phase 9: Final Testing
- [ ] Run pytest tests/ -v (all pass)
- [ ] Create and run tests/smoke_test.sh
- [ ] Code quality checks (duplication, old patterns, hardcoded paths)
- [ ] Cleanup temporary files (.pyc, .bak)
- [ ] Verify .gitignore correct
- [ ] Documentation review
- [ ] Manual end-to-end workflow test
- [ ] Integration test scenarios (all 5 scenarios)

### Phase 10: Future Cleanup (Not in this plan)
- [ ] Remove symlinks after transition period
- [ ] Remove fallback config logic
- [ ] Remove legacy entry_points
- [ ] Update documentation to remove migration notes
