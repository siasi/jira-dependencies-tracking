# Report Output Structure Implementation Summary

## Overview

Implemented a consistent output structure for all report-generating scripts with progressive numbering and organized subdirectories.

## Changes Made

### 1. New Utility Module: `lib/output_utils.py`

Created a new utility module that provides:

- **`generate_output_path(report_type, extension, custom_filename=None)`**
  - Generates standardized output paths with progressive numbering
  - Creates output directories automatically if they don't exist
  - Supports custom filenames when needed
  - Returns: `output/{report_type}/{NNN}_{report_type}_{timestamp}.{extension}`

- **`get_next_report_number(report_type)`**
  - Determines the next progressive number for a given report type
  - Scans existing files and increments the highest number found

- **`get_report_info(report_path)`**
  - Extracts metadata from report filenames (number, type, timestamp)

- **`list_reports(report_type=None)`**
  - Lists all reports, optionally filtered by type
  - Returns sorted list (newest first)

### 2. Updated Scripts

#### `analyze_workload.py`
- Added import: `from lib.output_utils import generate_output_path`
- Updated `--html` option:
  - Changed `const='auto'` → `const=None`
  - Updated help text to reference new output structure
  - Changed logic: `if args.html is not None` and use `generate_output_path('workload_analysis', 'html', args.html)`
- Updated `--markdown` option (same pattern)
- Updated `--csv` option (same pattern)

#### `validate_planning.py`
- Added import: `from lib.output_utils import generate_output_path`
- Updated `--markdown` option:
  - Changed `const='auto'` → `const=None`
  - Updated help text to reference new output structure
  - Changed logic: `if args.markdown is not None` and use `generate_output_path('planning_validation', 'md', args.markdown)`

#### `validate_prioritisation.py`
- Added import: `from lib.output_utils import generate_output_path`
- Updated `--markdown` Click option:
  - Added `is_flag=False` and `flag_value=''`
  - Updated help text to reference new output structure
  - Changed logic to use `generate_output_path('prioritisation_validation', 'md', markdown_filename)`

### 3. Updated Configuration

#### `.gitignore`
- Added `output/` to prevent committing generated reports

#### `README.md`
- Added new "Output Structure" section explaining:
  - Directory organization
  - Naming convention
  - Default behavior vs custom filenames
  - Usage examples

## Output Structure

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

## Naming Convention

**Format:** `{progressive_number:03d}_{report_type}_{timestamp}.{extension}`

- **Progressive Number:** 001, 002, 003... (auto-incremented per report type)
- **Report Type:** `workload_analysis`, `planning_validation`, `prioritisation_validation`
- **Timestamp:** `YYYYMMDD_HHMMSS` format
- **Extension:** `html`, `md`, `csv`, `txt`

## Usage Examples

### Default Behavior (New)
```bash
# Saves to output/workload_analysis/001_workload_analysis_20260410_152030.html
python analyze_workload.py --quarter "26 Q2" --html

# Saves to output/planning_validation/001_planning_validation_20260410_152030.md
python validate_planning.py --quarter "26 Q2" --markdown

# Saves to output/prioritisation_validation/001_prioritisation_validation_20260410_152030.md
python validate_prioritisation.py --markdown
```

### Custom Filenames (Still Supported)
```bash
# Saves to specified location
python analyze_workload.py --quarter "26 Q2" --html custom_report.html
python validate_planning.py --quarter "26 Q2" --markdown my_report.md
```

### Multiple Formats
```bash
# Each format gets its own progressive number
python analyze_workload.py --quarter "26 Q2" --html --markdown --csv
# Creates:
# - output/workload_analysis/001_workload_analysis_20260410_152030.html
# - output/workload_analysis/002_workload_analysis_20260410_152030.md
# - output/workload_analysis/003_workload_analysis_20260410_152030.csv
```

## Benefits

1. **Organization:** Reports are organized by type in separate subdirectories
2. **Traceability:** Progressive numbering makes it easy to track report history
3. **Timestamping:** Every report has a timestamp for reference
4. **Consistency:** All scripts follow the same naming convention
5. **Flexibility:** Custom filenames still supported when needed
6. **Automation:** No need to manually specify output filenames
7. **Clean Repository:** Output directory is gitignored to prevent committing company data

## Testing

The implementation has been tested with:
- Progressive numbering across multiple file creations
- Directory auto-creation
- Custom filename override
- Multiple report types

All three scripts have been verified to show updated help messages with the new output structure information.

## Backward Compatibility

The changes maintain backward compatibility:
- Custom filenames still work exactly as before
- The only change is the default behavior when no filename is specified
- All existing command-line options remain functional

## Migration of Existing Files

All existing report files (87 total) have been successfully migrated to the new structure:

**Migrated Files:**
- **workload_analysis/**: 75 files
  - HTML dashboards (workload_dashboard_*.html)
  - CSV exports (workload_analysis_*.csv)
  - Slack notification messages (*slack_messages*.txt)

- **prioritisation_validation/**: 12 files
  - Slack notification messages (slack_messages_prioritisation_*.txt)

**Migration Details:**
- Files were sorted by timestamp and assigned progressive numbers
- Original timestamps were preserved in the new filenames
- All files from both root directory and data/ directory were consolidated
- Root directory is now clean of report files
- User notes and planning docs (*.md) remain in root as intended

**Before Migration:**
```
.
├── workload_dashboard_20260408_182751.html
├── workload_analysis_20260403_000317.csv
├── output.csv
└── data/
    ├── slack_messages_*.txt
    └── dust_messages_*.txt
```

**After Migration:**
```
output/
├── workload_analysis/
│   ├── 001_workload_analysis_20260330_123337.txt
│   ├── 002_workload_analysis_20260330_123604.txt
│   ├── ...
│   └── 075_workload_analysis_20260410_152557.csv
└── prioritisation_validation/
    ├── 001_prioritisation_validation_20260409_094853.txt
    ├── ...
    └── 012_prioritisation_validation_20260410_150133.txt
```

The migration script (`migrate_reports.py`) has been added to `.gitignore` as it was a one-time operation.
