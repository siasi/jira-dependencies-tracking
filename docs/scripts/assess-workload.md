# Assess Workload Script Documentation

Assess the distribution of epic work across teams to identify imbalances and ensure fair resource allocation.

## Purpose

This script helps engineering leadership assess team workload distribution and identify:
- Teams with disproportionate workload (potential bottlenecks)
- Teams with capacity for additional work
- Cross-team coordination requirements
- Workload balance across the organization

## Quick Start

```bash
# Analyze latest extraction for Q2 2026
python assess_workload.py --quarter "26 Q2"

# Generate interactive HTML dashboard
python assess_workload.py --quarter "26 Q2" --html

# Generate Slack messages for managers
python assess_workload.py --quarter "26 Q2" --slack
```

## Scope

**Which initiatives are analyzed:**
- **Quarter:** Specified `--quarter` (required)
- **Status:** In Progress (any quarter) OR Planned (matches quarter)
- **Exclusions:**
  - Signed-off initiatives (`config/initiative_exceptions.yaml`)
  - Teams in `teams_excluded_from_workload_analysis` (`config/team_mappings.yaml`)

## Commands

### Basic Analysis

```bash
# Analyze latest extraction for Q2 2026
python assess_workload.py --quarter "26 Q2"

# Analyze specific file
python assess_workload.py --quarter "26 Q2" data/jira_extract_20260321.json

# Analyze snapshot
python assess_workload.py --quarter "26 Q2" data/snapshots/snapshot_baseline_*.json
```

### Detailed Output

```bash
# Show detailed data quality issues
python assess_workload.py --quarter "26 Q2" --show-quality

# Verbose output with detailed initiative lists
python assess_workload.py --quarter "26 Q2" --verbose
```

### Generate Reports

```bash
# Export to CSV (auto-generates filename)
python assess_workload.py --quarter "26 Q2" --csv

# Export to markdown with custom filename
python assess_workload.py --quarter "26 Q2" --markdown reports/workload_analysis.md

# Generate interactive HTML dashboard (auto-generates filename)
python assess_workload.py --quarter "26 Q2" --html
```

### Generate Slack Notifications

```bash
# Generate Slack messages for managers
python assess_workload.py --quarter "26 Q2" --slack
```

## Options

- `--quarter QUARTER` - **Required.** Quarter to analyze (e.g., "26 Q2"). Only initiatives with status="In Progress" or (quarter=QUARTER and status="Planned") are analyzed.
- `--html [FILENAME]` - Generate interactive HTML dashboard with charts and heatmaps. Auto-generates filename if omitted.
- `--markdown [FILENAME]` - Export detailed report to markdown format. Auto-generates filename if omitted.
- `--csv [FILENAME]` - Export initiative analysis as CSV file. Auto-generates filename if omitted.
- `--verbose` - Show detailed list of initiatives per team (leading and contributing)
- `--show-quality` - Show detailed data quality issues (missing owner, missing epics, missing objectives)
- `--slack` - Generate Slack bulk messages for workload quality action items
- `json_file` - Optional path to specific data file (defaults to latest extraction)

## What It Analyzes

### Epic Distribution

- Total epics per team across all initiatives
- Epic count per initiative per team
- Identifies teams with disproportionate workload

### Initiative Participation

- Which initiatives each team is involved in
- Number of epics committed per initiative
- Cross-team coordination requirements

### Workload Balance

- Teams with highest epic counts (potential bottlenecks)
- Teams with lowest epic counts (potential capacity)
- Variance in work distribution across the organization

## Output Sections

### 1. Team Workload Summary

Total epics per team, sorted by workload.

**Example:**
```
Team             Leading    Contributing    Total
────────────────────────────────────────────────
PLATFORM         15         8               23
SECURITY         8          5               13
NETWORKING       6          3               9
```

**Why this matters:** Quick overview of which teams have the most work committed.

### 2. Initiative Breakdown

Per-initiative epic distribution across teams.

**Example:**
```
INIT-123: Platform Upgrade
  PLATFORM (owner): 5 epics
  SECURITY: 3 epics
  NETWORKING: 2 epics
  Total: 10 epics
```

**Why this matters:** Shows coordination requirements and initiative complexity.

### 3. Workload Warnings

Teams significantly above/below average workload.

**Example:**
```
⚠️ High Workload:
  PLATFORM: 23 epics (avg: 15, +53%)

⚠️ Low Workload:
  NETWORKING: 9 epics (avg: 15, -40%)
```

**Why this matters:** Highlights potential bottlenecks and capacity opportunities.

### 4. Well-Balanced Teams

Teams with workload close to organizational average.

**Example:**
```
✅ Balanced:
  SECURITY: 13 epics (avg: 15, -13%)
```

**Why this matters:** Shows which teams have appropriate workload allocation.

## Interactive HTML Dashboard

Generate a standalone HTML file with interactive visualizations:

```bash
# Generate dashboard with auto-generated filename
python assess_workload.py --quarter "26 Q2" --html

# Specify custom filename
python assess_workload.py --quarter "26 Q2" --html reports/workload_dashboard.html
```

### Dashboard Features

**Interactive Bar Chart:**
- Team workload comparison (leading vs contributing)
- Click bars to see initiative lists
- Hover for detailed metrics

**Heatmap Table:**
- Team contribution by strategic objective
- Color-coded by involvement level
- Click cells to drill down into specific initiatives

**Summary Statistics:**
- Total initiatives
- Active teams
- Top contributors

**Fully Standalone:**
- Single HTML file with embedded CSS and JavaScript
- Uses Chart.js CDN for visualizations
- No external dependencies needed

### Use Cases for Dashboard

- Share visual reports with stakeholders
- Present workload distribution in team meetings
- Track workload evolution over time (generate multiple snapshots)
- Identify cross-functional collaboration patterns

## Slack Manager Notifications

Generate workload summary messages for engineering managers:

```bash
python assess_workload.py --quarter "26 Q2" --slack
```

**Message Content:**
- Team's total epic count for the period
- Breakdown by initiative
- Comparison to organizational average
- Workload status (balanced, high, low)

**Example output:**
```
Recipient: @manager (U01ABC123)

PLATFORM Team Workload Summary (26 Q2)

Total epics: 23 (avg: 15, +53% above average)

Leading initiatives:
  - INIT-123: Platform Upgrade (5 epics)
  - INIT-456: Security Enhancement (4 epics)

Contributing to:
  - INIT-789: Network Optimization (3 epics)

⚠️ Status: High workload - consider rebalancing
```

## Use Cases

### Quarterly Planning

Validate work distribution before committing to plans:

```bash
# Extract Q2 initiatives
python scan.py extract --quarter "26 Q2"

# Analyze workload distribution
python assess_workload.py --quarter "26 Q2" --html

# Review dashboard and adjust plans
```

### Mid-Quarter Check

Identify teams at risk of overcommitment:

```bash
# Extract current state
python scan.py extract

# Analyze workload
python assess_workload.py --quarter "26 Q2" --verbose

# Generate manager notifications
python assess_workload.py --quarter "26 Q2" --slack
```

### Resource Planning

Inform hiring and allocation decisions:

```bash
# Generate detailed analysis
python assess_workload.py --quarter "26 Q2" --csv --markdown

# Review team capacity trends
# Use data to justify resource requests
```

### Leadership Reports

Provide data for executive summaries:

```bash
# Generate HTML dashboard
python assess_workload.py --quarter "26 Q2" --html

# Share dashboard with leadership team
```

## Configuration

### Exclude Teams from Analysis

Some teams have different workload patterns and should be excluded:

```yaml
teams_excluded_from_workload_analysis:
  - "IT"
  - "Security Engineering"
  - "DevOps"
  - "Integration Ops"
```

**Why:** These teams have different work patterns than product delivery teams and would skew workload metrics.

### Configure Team Names

Map friendly team names to project keys:

```yaml
team_mappings:
  "Engineering": "ENG"
  "Product": "PROD"
  "Design": "DESIGN"
```

This makes reports more readable by using friendly names instead of project keys.

## Related Documentation

- [Validation Rules](../specs/validation-rules.md) - Detailed validation rules and logic
- [Validation Library](../guides/validation-library.md) - Shared validation library documentation
- [Configuration Reference](../guides/configuration.md) - Advanced configuration options
- [Setup Guide](../guides/setup.md) - Initial configuration
