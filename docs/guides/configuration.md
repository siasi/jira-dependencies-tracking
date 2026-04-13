# Configuration Reference

Advanced configuration options for customizing the Jira EM Toolkit behavior.

## Table of Contents

- [Custom Fields Configuration](#custom-fields-configuration)
- [Team Mappings](#team-mappings)
- [User ID Configuration](#user-id-configuration)
- [Quarter Filtering](#quarter-filtering)
- [Teams Exempt from RAG Status](#teams-exempt-from-rag-status)
- [Team Exclusions](#team-exclusions)
- [Initiative Sign-Off Exceptions](#initiative-sign-off-exceptions)
- [Output Structure](#output-structure)

## Custom Fields Configuration

Custom fields for initiatives are configured under `custom_fields.initiatives` in `config/jira_config.yaml`:

```yaml
custom_fields:
  initiatives:
    rag_status: "customfield_12111"      # RAG status indicator
    quarter: "customfield_12108"          # Planning quarter
    objective: "customfield_12101"        # Strategic objective
    # Add any custom field here without code changes
```

### Adding New Custom Fields

1. **Find the Jira field ID:**
   ```bash
   python extract.py list-fields
   ```
   This lists all available custom fields with their IDs and types.

2. **Add to configuration:**
   ```yaml
   custom_fields:
     initiatives:
       your_field_name: "customfield_XXXXX"
   ```

3. **Run extraction:**
   ```bash
   python extract.py extract
   ```
   The field will appear in the output JSON with the name you specified.

### Field Types Supported

- **Select fields** (e.g., RAG status) - extracted as the selected value
- **Text fields** - extracted as-is
- **Multi-select fields** (e.g., strategic objectives) - extracted as comma-separated values if multiple selected, or single value if only one
- **User fields** - extracted as user display name
- **Date fields** - extracted in ISO format

All custom fields are optional. If a field is missing on an initiative, it will appear as `null` in the output.

## Team Mappings

Configure team display names and manager information in `config/team_mappings.yaml`.

### Team Display Names

Map friendly team names to Jira project keys:

```yaml
team_mappings:
  "Engineering Platform": "PLATFORM"
  "Risk & Security": "RSK"
  "Payments": "PAY"
  "Design": "DESIGN"
```

**Note:** This file is optional. The toolkit works without it by using display names as-is. The mapping helps identify teams when display names differ from project keys.

### My Teams Configuration

Configure your teams to filter action items with the `--me` flag:

```yaml
my_teams:
  - "CONSOLE"
  - "PAYINS"
  # Add your team project keys here
```

**Usage:**
```bash
# Show only action items for your configured teams
python validate_data_quality.py --quarter "26 Q2" --me
```

See [Validate Data Quality documentation](../scripts/validate-data-quality.md#personal-filtering) for details.

## User ID Configuration

Configure manager information for Slack notifications in `config/team_mappings.yaml`:

```yaml
team_managers:
  "CBPPE":
    notion_handle: "@Thom Gray"
    slack_id: "U01F3QUH30B"
  "CONSOLE":
    notion_handle: "@Antony Red"
    slack_id: "U02ABC453"
  "PAYINS":
    notion_handle: "@Thom Gray"
    slack_id: "U01F3QUH30B"  # Same Slack ID if manager leads multiple teams
```

**Finding Slack Member IDs:**

1. Open Slack
2. Click on the person's profile
3. Click "More" → "Copy member ID"
4. Paste into configuration

**Note:** If a manager oversees multiple teams, use the same `slack_id` for each team. The toolkit will consolidate their notifications into a single message.

## Quarter Filtering

### Command-Line Filtering (Recommended)

Use the `--quarter` flag with scripts to filter at runtime:

```bash
python extract.py extract --quarter "26 Q2"
python validate_planning.py --quarter "26 Q2"
python analyze_workload.py --quarter "26 Q2"
```

This approach is flexible and doesn't modify configuration files.

### Configuration-Based Filtering (Legacy)

To extract only initiatives for a specific quarter by default:

1. **Ensure quarter custom field is configured:**
   ```yaml
   custom_fields:
     initiatives:
       quarter: "customfield_12108"  # Quarter field
   ```

2. **Add the filters section:**
   ```yaml
   filters:
     quarter: "26 Q2"  # Format: "YY QN"
   ```

**Behavior when filtering is enabled:**
- Only initiatives matching the specified quarter are extracted
- Initiatives with status "Done" are excluded automatically
- Epics are still extracted for all team projects, but only those linked to filtered initiatives appear in the output

**To disable filtering:** Remove or comment out the `filters` section.

## Teams Exempt from RAG Status

Some teams provide supporting work and don't need to report RAG status (e.g., Documentation, UX Research).

Configure in `config/team_mappings.yaml`:

```yaml
teams_exempt_from_rag:
  - "DOCS"
  - "UX_RESEARCH"
```

**Behavior:**
- These teams still need to create epics if listed in "Teams Involved"
- Their epics won't be checked for RED/YELLOW/missing RAG status
- Owner teams are automatically exempt (don't add them here)

**Why this exists:** Support teams provide best-effort assistance but don't influence go/no-go decisions for moving initiatives to Planned status.

## Team Exclusions

Different scripts have different exclusion needs. Configure separate exclusion lists for each use case.

### Workload Analysis Exclusions

Teams with different workload patterns should be excluded from workload analysis:

```yaml
teams_excluded_from_workload_analysis:
  - "IT"
  - "Security Engineering"
  - "DevOps"
  - "Integration Ops"
```

**Used by:** `analyze_workload.py`

**Why:** These teams have different work patterns than product delivery teams and would skew workload metrics.

### Validation Exclusions

Teams that don't follow standard epic creation process should be excluded from planning validation:

```yaml
teams_excluded_from_validation:
  - "IT"
  - "Security Engineering"
  - "SecOps"
```

**Used by:** `validate_planning.py`, `validate_data_quality.py`

**Why:** These teams don't need to create epics when listed in Teams Involved.

### Prioritisation Exclusions

Teams that don't participate in strategic priority tracking:

```yaml
teams_excluded_from_prioritisation:
  - "DevOps"
  - "Security Engineering"
  - "XD"
```

**Used by:** `validate_prioritisation.py`

**Why:** These teams work on operational/continuous work not tied to strategic initiatives.

**Backward compatibility:** If you don't specify these lists, scripts will fall back to `teams_excluded_from_analysis` (deprecated).

## Initiative Sign-Off Exceptions

Some initiatives have intentional inconsistencies that managers have explicitly approved. These are excluded from validation reports.

### Configuration

Edit `config/initiative_exceptions.yaml`:

```yaml
signed_off_initiatives:
  - key: "INIT-1234"
    reason: "Team X is consultative only, no epic needed"
    date: "2026-03-31"
    approved_by: "@Manager Name"

  - key: "INIT-5678"
    reason: "Discovery work - dependencies not yet clear"
    date: "2026-04-01"
    approved_by: "@Tech Lead"
```

### Field Definitions

**Required:**
- `key` - Initiative Jira key (e.g., "INIT-1234")
- `reason` - Explanation of why this is signed off

**Optional:**
- `date` - When approved (ISO format: "YYYY-MM-DD")
- `approved_by` - Manager who approved (e.g., "@Jane Smith")

### When to Use This

- Team listed for awareness only (no epic needed)
- Special cross-team arrangements
- Manager has explicitly approved the current state
- Temporary exceptions during planning phases

### Behavior

Run validation - signed-off initiatives will be completely hidden from reports:

```bash
python validate_planning.py --quarter "26 Q2"
# INIT-1234 will not appear in validation output
```

**Important:** Review this file periodically to remove resolved initiatives. Stale exceptions can hide real issues.

## Output Structure

All report-generating scripts follow a consistent output structure with auto-generated filenames.

### Directory Structure

```
output/
├── workload_analysis/
│   ├── 001_workload_analysis_20260410_152030.html
│   ├── 002_workload_analysis_20260410_153045.md
│   └── 003_workload_analysis_20260410_154102.csv
├── planning_validation/
│   ├── 001_planning_validation_20260410_152030.md
│   └── 002_planning_validation_20260410_153100.md
└── prioritisation_validation/
    ├── 001_prioritisation_validation_20260410_152030.md
    └── 002_prioritisation_validation_20260410_153200.md
```

### Naming Convention

Format: `{progressive_number:03d}_{report_type}_{timestamp}.{extension}`

- **Progressive Number:** Auto-incremented for each report type (001, 002, 003...)
- **Report Type:** Identifier for the analysis type (e.g., `workload_analysis`, `planning_validation`)
- **Timestamp:** `YYYYMMDD_HHMMSS` format
- **Extension:** File format (`html`, `md`, `csv`, `txt`)

### Usage Examples

```bash
# Auto-generates: output/workload_analysis/001_workload_analysis_YYYYMMDD_HHMMSS.html
python analyze_workload.py --quarter "26 Q2" --html

# Custom location (overrides default)
python analyze_workload.py --quarter "26 Q2" --html my_custom_report.html

# Generate multiple formats (each gets progressive numbering)
python analyze_workload.py --quarter "26 Q2" --html --markdown --csv
```

## Strategic Objectives

Configure valid strategic objectives in `config/jira_config.yaml`:

```yaml
validation:
  strategic_objective:
    valid_values:
      - "2026_fuel_regulated"
      - "2026_fuel_unregulated"
      - "engineering_pillars"
      - "tech_debt"
```

**Used by:** Validation scripts to detect invalid or typo'd objectives.

See [Validation Rules](../specs/validation-rules.md#what-makes-a-strategic-objective-invalid) for details.

## Related Documentation

- [Setup Guide](setup.md) - Initial installation and configuration
- [Validation Rules](../specs/validation-rules.md) - Business validation rules
- [Validation Library](validation-library.md) - Developer guide for validation library
