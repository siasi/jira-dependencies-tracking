---
title: Quarterly Snapshot Tracking System
type: feat
status: completed
date: 2026-03-15
origin: docs/brainstorms/2026-03-15-quarterly-plan-snapshot-tracking-brainstorm.md
---

# Quarterly Snapshot Tracking System

## Overview

Build a quarterly plan stability and delivery tracking system that captures timestamped snapshots of Jira data at key milestones, then compares snapshots to quantify plan churn and measure commitment drift. This extends the existing jira-dependencies-tracking tool with new CLI commands for snapshot management and comparison analysis.

**Origin**: [Quarterly Plan Snapshot Tracking Brainstorm](../brainstorms/2026-03-15-quarterly-plan-snapshot-tracking-brainstorm.md)

## Problem Statement / Motivation

Engineering leadership needs to track:
1. **Plan Stability**: Which "Planned" initiatives dropped during the quarter? What new work got injected mid-quarter?
2. **Delivery Predictability** (optional): When initiatives have ETAs, did they ship on time or overrun?

Currently, the tool extracts Jira data but provides no historical comparison. Leadership must manually compare exports to see what changed, making monthly reporting time-consuming and error-prone.

**Use Case**: Capture baseline snapshot at Q start, monthly checkpoints, and Q end. Generate reports showing commitment drift, new work injection, epic churn, and delivery overruns (if ETA field configured).

**Primary User**: Engineering leadership preparing monthly reports on plan stability trends.

## Proposed Solution

**Approach**: Versioned Snapshots with Diff Analysis (see brainstorm: Approach A chosen)

Extend existing tool to:
1. **Capture snapshots** - Save labeled, timestamped JSON snapshots to `data/snapshots/`
2. **List snapshots** - Show available snapshots with metadata
3. **Compare snapshots** - Load two snapshots, diff by initiative/epic keys, generate reports

**Key decisions from brainstorm**:
- Event-driven snapshot timing (manual, not calendar-based)
- User-provided semantic labels (`2026-Q2-baseline`, `2026-Q2-month1`)
- Same JSON structure as current extract (no schema changes)
- Five report types (3 always, 2 conditional on ETA field)

## Technical Approach

### Architecture

**New CLI Commands** (add to `jira_extract.py`):

```python
@cli.command()
@click.option("--config", default="config.yaml", type=click.Path(exists=True))
@click.option("--label", required=True, help="Snapshot label (e.g., 2026-Q2-baseline)")
@click.option("--verbose", is_flag=True)
def snapshot(config: str, label: str, verbose: bool):
    """Capture timestamped snapshot of current Jira data."""

@cli.command()
@click.option("--from", "from_label", required=True, help="Baseline snapshot label")
@click.option("--to", "to_label", required=True, help="Comparison snapshot label")
@click.option("--format", type=click.Choice(["text", "markdown", "csv"],
              case_sensitive=False), default="text")
@click.option("--output", type=click.Path(), help="Output file path")
def compare(from_label: str, to_label: str, format: str, output: Optional[str]):
    """Compare two snapshots and generate diff report."""

@cli.group()
def snapshots():
    """Manage snapshots."""

@snapshots.command(name="list")
def snapshots_list():
    """List all available snapshots."""
```

**New Modules**:

1. **`src/snapshot.py`** - Snapshot management
   - Save snapshot with label and metadata
   - Load snapshot from file
   - List available snapshots
   - Validate snapshot compatibility

2. **`src/comparator.py`** - Diff algorithm
   - Compare two snapshots
   - Detect dropped/added initiatives
   - Track epic churn per initiative
   - Calculate team stability metrics
   - Identify overruns (if ETA field present)

3. **`src/reports.py`** - Report generation
   - Format comparison results as text/markdown/CSV
   - Generate 5 report types (conditional on config)
   - Output to stdout or file

### Data Structures

```python
# src/snapshot.py

@dataclass
class SnapshotMetadata:
    """Metadata captured at snapshot time."""
    label: str                      # User-provided semantic label
    timestamp: str                  # ISO8601 timestamp
    jira_instance: str             # Instance URL
    config_snapshot: Dict[str, Any]  # Custom fields, filters used
    total_initiatives: int
    total_epics: int
    total_teams: int

@dataclass
class Snapshot:
    """Complete snapshot with metadata and data."""
    metadata: SnapshotMetadata
    data: Dict[str, Any]  # Same structure as extract output

# Snapshot file structure
{
    "snapshot_metadata": {
        "label": "2026-Q2-baseline",
        "timestamp": "2026-03-15T10:30:00Z",
        "jira_instance": "company.atlassian.net",
        "config_snapshot": {
            "custom_fields": {"quarter": "...", "rag_status": "...", "eta": "..."},
            "filters": {"quarter": "26 Q2"}
        },
        "total_initiatives": 22,
        "total_epics": 390,
        "total_teams": 6
    },
    "extracted_at": "2026-03-15T10:30:00Z",
    "jira_instance": "company.atlassian.net",
    "queries": {...},
    "extraction_status": {...},
    "initiatives": [...],  # Same as current extract
    "orphaned_epics": [...],
    "summary": {...}
}
```

```python
# src/comparator.py

@dataclass
class InitiativeChange:
    """Change detected in an initiative."""
    initiative_key: str
    summary: str
    change_type: str  # "dropped", "added", "epic_churn"
    baseline_status: Optional[str]
    current_status: Optional[str]
    team_contributions: List[str]
    details: Dict[str, Any]  # Additional context

@dataclass
class EpicChurn:
    """Epic additions/removals within an initiative."""
    initiative_key: str
    initiative_summary: str
    epics_added: List[Dict[str, Any]]
    epics_removed: List[Dict[str, Any]]
    net_change: int

@dataclass
class TeamStability:
    """Stability metrics for a team."""
    team_project_key: str
    total_epics_baseline: int
    epics_unchanged: int
    epics_added: int
    epics_removed: int
    stability_percentage: float
    eta_delivery_rate: Optional[float]  # If ETA tracking enabled

@dataclass
class ComparisonResult:
    """Results of comparing two snapshots."""
    baseline_label: str
    current_label: str
    baseline_timestamp: str
    current_timestamp: str

    # Report 1: Commitment Drift
    dropped_initiatives: List[InitiativeChange]

    # Report 2: New Work Injection
    added_initiatives: List[InitiativeChange]

    # Report 3: Epic Churn
    epic_churn: List[EpicChurn]

    # Report 4: Initiative Overrun (optional, requires ETA)
    overrun_initiatives: Optional[List[Dict[str, Any]]]

    # Report 5: Team Stability
    team_stability: List[TeamStability]
```

### Implementation Phases

#### Phase 1: Snapshot Capture (MVP)

**Deliverables**:
- [x] `snapshot` command captures current Jira data with label
- [x] Snapshots saved to `data/snapshots/snapshot_{label}_{timestamp}.json`
- [x] Metadata includes label, timestamp, config, totals
- [x] Reuses existing extract flow (no new Jira API calls)

**Files to modify/create**:
- Modify: `jira_extract.py` (add `snapshot` command)
- Create: `src/snapshot.py` (SnapshotManager class)

**Implementation details**:

```python
# src/snapshot.py

class SnapshotManager:
    def __init__(self, snapshots_directory: str = "./data/snapshots"):
        self.snapshots_directory = Path(snapshots_directory)

    def save_snapshot(
        self,
        label: str,
        data: Dict[str, Any],
        config: Config
    ) -> Path:
        """Save snapshot with metadata."""
        # Create snapshot directory
        self.snapshots_directory.mkdir(parents=True, exist_ok=True)

        # Build metadata
        metadata = SnapshotMetadata(
            label=label,
            timestamp=datetime.utcnow().isoformat() + "Z",
            jira_instance=data["jira_instance"],
            config_snapshot={
                "custom_fields": config.custom_fields,
                "filters": asdict(config.filters) if config.filters else None
            },
            total_initiatives=data["summary"]["total_initiatives"],
            total_epics=data["summary"]["total_epics"],
            total_teams=len(data["summary"]["teams_involved"])
        )

        # Add metadata to data
        snapshot_data = {
            "snapshot_metadata": asdict(metadata),
            **data  # Include all extract data
        }

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snapshot_{label}_{timestamp}.json"
        snapshot_path = self.snapshots_directory / filename

        # Write file
        with open(snapshot_path, "w") as f:
            json.dump(snapshot_data, f, indent=2, ensure_ascii=False)

        return snapshot_path
```

**Success criteria**:
- Snapshot file created in correct location
- Contains all extract data + metadata
- Preserves UTF-8 encoding (emojis work)
- Command completes in < 30 seconds for typical dataset

#### Phase 2: Snapshot Listing

**Deliverables**:
- [x] `snapshots list` command shows available snapshots
- [x] Displays: label, timestamp, jira instance, totals
- [x] Sorted by timestamp (newest first)

**Files to modify/create**:
- Modify: `jira_extract.py` (add `snapshots` group with `list` command)
- Modify: `src/snapshot.py` (add `list_snapshots()` method)

**Implementation details**:

```python
# src/snapshot.py (continued)

def list_snapshots(self) -> List[SnapshotMetadata]:
    """List all available snapshots with metadata."""
    if not self.snapshots_directory.exists():
        return []

    snapshots = []
    for file_path in self.snapshots_directory.glob("snapshot_*.json"):
        with open(file_path) as f:
            data = json.load(f)
            metadata = SnapshotMetadata(**data["snapshot_metadata"])
            snapshots.append(metadata)

    # Sort by timestamp, newest first
    return sorted(snapshots, key=lambda s: s.timestamp, reverse=True)
```

**Success criteria**:
- Lists all snapshots in `data/snapshots/`
- Shows key metadata (label, timestamp, totals)
- Handles empty directory gracefully

#### Phase 3: Comparison Engine (Core Logic)

**Deliverables**:
- [x] Load two snapshots by label
- [x] Diff algorithm detects changes
- [x] Generate ComparisonResult with all 5 reports
- [x] Handle missing ETA field gracefully (skip Reports 4-5)

**Files to create**:
- Create: `src/comparator.py` (SnapshotComparator class)

**Implementation details**:

```python
# src/comparator.py

class SnapshotComparator:
    def __init__(self, baseline: Snapshot, current: Snapshot):
        self.baseline = baseline
        self.current = current
        self.has_eta = "eta" in baseline.metadata.config_snapshot.get("custom_fields", {})

    def compare(self) -> ComparisonResult:
        """Generate complete comparison analysis."""
        return ComparisonResult(
            baseline_label=self.baseline.metadata.label,
            current_label=self.current.metadata.label,
            baseline_timestamp=self.baseline.metadata.timestamp,
            current_timestamp=self.current.metadata.timestamp,
            dropped_initiatives=self._detect_dropped_initiatives(),
            added_initiatives=self._detect_added_initiatives(),
            epic_churn=self._detect_epic_churn(),
            overrun_initiatives=self._detect_overruns() if self.has_eta else None,
            team_stability=self._calculate_team_stability()
        )

    def _detect_dropped_initiatives(self) -> List[InitiativeChange]:
        """Report 1: Initiatives that were Planned in baseline, now Proposed/Cancelled."""
        baseline_planned = {
            i["key"]: i for i in self.baseline.data["initiatives"]
            if i["status"] == "Planned"
        }

        current_initiatives = {i["key"]: i for i in self.current.data["initiatives"]}

        dropped = []
        for key, baseline_init in baseline_planned.items():
            current_init = current_initiatives.get(key)
            if current_init and current_init["status"] in ["Proposed", "Cancelled"]:
                dropped.append(InitiativeChange(
                    initiative_key=key,
                    summary=baseline_init["summary"],
                    change_type="dropped",
                    baseline_status="Planned",
                    current_status=current_init["status"],
                    team_contributions=[t["team_project_key"]
                                       for t in baseline_init["contributing_teams"]],
                    details={"current_initiative": current_init}
                ))

        return dropped

    def _detect_added_initiatives(self) -> List[InitiativeChange]:
        """Report 2: Initiatives that weren't Planned in baseline, now Planned."""
        baseline_planned_keys = {
            i["key"] for i in self.baseline.data["initiatives"]
            if i["status"] == "Planned"
        }

        current_planned = [
            i for i in self.current.data["initiatives"]
            if i["status"] == "Planned" and i["key"] not in baseline_planned_keys
        ]

        return [
            InitiativeChange(
                initiative_key=i["key"],
                summary=i["summary"],
                change_type="added",
                baseline_status=None,
                current_status="Planned",
                team_contributions=[t["team_project_key"]
                                   for t in i["contributing_teams"]],
                details={"initiative": i}
            )
            for i in current_planned
        ]

    def _detect_epic_churn(self) -> List[EpicChurn]:
        """Report 3: Epic additions/removals per initiative."""
        baseline_initiatives = {i["key"]: i for i in self.baseline.data["initiatives"]}
        current_initiatives = {i["key"]: i for i in self.current.data["initiatives"]}

        churn_results = []

        # Check initiatives that exist in both snapshots
        for key in set(baseline_initiatives.keys()) & set(current_initiatives.keys()):
            baseline_init = baseline_initiatives[key]
            current_init = current_initiatives[key]

            # Flatten epic lists per initiative
            baseline_epics = {
                epic["key"]: epic
                for team in baseline_init["contributing_teams"]
                for epic in team["epics"]
            }

            current_epics = {
                epic["key"]: epic
                for team in current_init["contributing_teams"]
                for epic in team["epics"]
            }

            # Detect changes
            baseline_keys = set(baseline_epics.keys())
            current_keys = set(current_epics.keys())

            added_keys = current_keys - baseline_keys
            removed_keys = baseline_keys - current_keys

            if added_keys or removed_keys:
                churn_results.append(EpicChurn(
                    initiative_key=key,
                    initiative_summary=baseline_init["summary"],
                    epics_added=[current_epics[k] for k in added_keys],
                    epics_removed=[baseline_epics[k] for k in removed_keys],
                    net_change=len(added_keys) - len(removed_keys)
                ))

        return churn_results

    def _detect_overruns(self) -> List[Dict[str, Any]]:
        """Report 4: Initiatives delivered >20% beyond ETA (requires ETA field)."""
        if not self.has_eta:
            return []

        overruns = []
        baseline_initiatives = {i["key"]: i for i in self.baseline.data["initiatives"]}
        current_initiatives = {i["key"]: i for i in self.current.data["initiatives"]}

        for key, baseline_init in baseline_initiatives.items():
            current_init = current_initiatives.get(key)
            if not current_init or current_init["status"] != "Done":
                continue

            baseline_eta = baseline_init.get("eta")
            if not baseline_eta:
                continue

            # TODO: Implement actual delivery date calculation
            # Options from brainstorm:
            # A) Track status change to Done (needs history)
            # B) Use Completion Date custom field
            # C) Binary on-time vs late from snapshot timing

            # Placeholder for now - will be resolved in Phase 4

        return overruns

    def _calculate_team_stability(self) -> List[TeamStability]:
        """Report 5: Per-team stability metrics."""
        baseline_teams = {}
        current_teams = {}

        # Build team epic mappings
        for init in self.baseline.data["initiatives"]:
            for team in init["contributing_teams"]:
                key = team["team_project_key"]
                if key not in baseline_teams:
                    baseline_teams[key] = set()
                baseline_teams[key].update(epic["key"] for epic in team["epics"])

        for init in self.current.data["initiatives"]:
            for team in init["contributing_teams"]:
                key = team["team_project_key"]
                if key not in current_teams:
                    current_teams[key] = set()
                current_teams[key].update(epic["key"] for epic in team["epics"])

        # Calculate stability
        stability_metrics = []
        all_teams = set(baseline_teams.keys()) | set(current_teams.keys())

        for team_key in all_teams:
            baseline_epics = baseline_teams.get(team_key, set())
            current_epics = current_teams.get(team_key, set())

            unchanged = len(baseline_epics & current_epics)
            added = len(current_epics - baseline_epics)
            removed = len(baseline_epics - current_epics)

            total_baseline = len(baseline_epics)
            stability_pct = (unchanged / total_baseline * 100) if total_baseline > 0 else 100.0

            stability_metrics.append(TeamStability(
                team_project_key=team_key,
                total_epics_baseline=total_baseline,
                epics_unchanged=unchanged,
                epics_added=added,
                epics_removed=removed,
                stability_percentage=stability_pct,
                eta_delivery_rate=None  # TODO: Calculate if ETA tracking enabled
            ))

        # Sort by stability (least stable first)
        return sorted(stability_metrics, key=lambda s: s.stability_percentage)
```

**Success criteria**:
- Correctly identifies dropped/added initiatives
- Detects epic churn per initiative
- Calculates team stability metrics
- Completes in < 10 seconds for typical quarter (100 initiatives, 500 epics)

#### Phase 4: Report Generation

**Deliverables**:
- [x] Format ComparisonResult as text report
- [x] Format as markdown report (with tables)
- [x] Format as CSV export
- [x] Output to stdout or file

**Files to create**:
- Create: `src/reports.py` (ReportGenerator class)

**Implementation details**:

```python
# src/reports.py

class ReportGenerator:
    def __init__(self, comparison: ComparisonResult):
        self.comparison = comparison

    def generate_text(self) -> str:
        """Generate text report for terminal output."""
        sections = []

        sections.append(self._text_header())
        sections.append(self._text_commitment_drift())
        sections.append(self._text_new_work_injection())
        sections.append(self._text_epic_churn())

        if self.comparison.overrun_initiatives is not None:
            sections.append(self._text_overruns())

        sections.append(self._text_team_stability())

        return "\n\n".join(sections)

    def generate_markdown(self) -> str:
        """Generate markdown report with tables."""
        sections = []

        sections.append(self._md_header())
        sections.append(self._md_commitment_drift())
        sections.append(self._md_new_work_injection())
        sections.append(self._md_epic_churn())

        if self.comparison.overrun_initiatives is not None:
            sections.append(self._md_overruns())

        sections.append(self._md_team_stability())

        return "\n\n".join(sections)

    def generate_csv(self) -> str:
        """Generate CSV export of comparison data."""
        # Denormalized structure: one row per change/metric
        # Similar to existing CSV export pattern
        pass
```

**Success criteria**:
- Text report readable in terminal
- Markdown report renders correctly in GitHub/editors
- CSV export opens correctly in Excel/Sheets
- Reports include all 5 sections (conditional on ETA)

#### Phase 5: Integration & Testing

**Deliverables**:
- [x] All CLI commands integrated and working
- [x] Comprehensive test coverage
- [x] README updated with examples
- [x] Error handling for edge cases

**Files to modify/create**:
- Create: `tests/test_snapshot.py`
- Create: `tests/test_comparator.py`
- Create: `tests/test_reports.py`
- Modify: `README.md` (add snapshot commands documentation)

**Test scenarios**:

```python
# tests/test_snapshot.py

def test_save_snapshot_creates_file(tmp_path):
    """Snapshot saved to correct location with metadata."""

def test_save_snapshot_preserves_extract_data(tmp_path):
    """All extract data included in snapshot."""

def test_list_snapshots_empty_directory(tmp_path):
    """Handles empty snapshots directory gracefully."""

def test_list_snapshots_sorted_by_timestamp(tmp_path):
    """Snapshots listed newest first."""

# tests/test_comparator.py

def test_detect_dropped_initiatives():
    """Identifies initiatives that dropped from Planned."""

def test_detect_added_initiatives():
    """Identifies new Planned initiatives."""

def test_detect_epic_churn():
    """Detects epic additions/removals per initiative."""

def test_team_stability_calculation():
    """Calculates correct stability percentages."""

def test_comparison_without_eta_field():
    """Skips overrun report when ETA not configured."""

def test_comparison_different_jira_instances():
    """Warns when comparing snapshots from different instances."""

def test_comparison_incompatible_custom_fields():
    """Handles snapshots with different custom field configs."""

# tests/test_reports.py

def test_generate_text_report():
    """Text report formatted correctly."""

def test_generate_markdown_report():
    """Markdown tables render correctly."""

def test_generate_csv_report():
    """CSV export with proper encoding."""
```

**Success criteria**:
- All tests pass
- Test coverage > 80%
- README examples work as documented
- Error messages are clear and actionable

### Research Insights

**Best Practices:**
- Use `pytest.mark.parametrize` for testing multiple scenarios with same logic
- Create fixture factories for test data (snapshots, comparison results)
- Use `freezegun` to freeze time in tests (consistent timestamps)
- Test both success and failure paths for every public method
- Use `pytest.raises` with `match=` parameter to verify exact error messages

**Implementation Details:**
```python
# tests/test_snapshot.py - Enhanced testing patterns

import pytest
from freezegun import freeze_time
from pathlib import Path

@pytest.fixture
def mock_snapshot_data():
    """Fixture factory for test snapshot data."""
    return {
        "jira_instance": "test.atlassian.net",
        "summary": {
            "total_initiatives": 10,
            "total_epics": 50,
            "teams_involved": ["TEAM1", "TEAM2"]
        },
        "initiatives": [...]
    }

@pytest.fixture
def snapshot_manager(tmp_path):
    """Fixture for SnapshotManager with temp directory."""
    return SnapshotManager(snapshots_directory=str(tmp_path / "snapshots"))

@freeze_time("2026-03-15 10:30:00")
def test_save_snapshot_creates_file(snapshot_manager, mock_snapshot_data, mock_config):
    """Snapshot saved with deterministic timestamp."""
    result = snapshot_manager.save_snapshot(
        label="test-label",
        data=mock_snapshot_data,
        config=mock_config
    )

    assert result.exists()
    assert result.name == "snapshot_test-label_20260315_103000.json"

@pytest.mark.parametrize("invalid_label,expected_error", [
    ("label with spaces", "Invalid label"),
    ("label/with/slash", "Invalid label"),
    ("label$with$dollar", "Invalid label"),
])
def test_save_snapshot_validates_label(snapshot_manager, mock_snapshot_data, mock_config, invalid_label, expected_error):
    """Label validation prevents filesystem issues."""
    with pytest.raises(SnapshotError, match=expected_error):
        snapshot_manager.save_snapshot(
            label=invalid_label,
            data=mock_snapshot_data,
            config=mock_config
        )

def test_load_snapshot_nonexistent(snapshot_manager):
    """Clear error when snapshot doesn't exist."""
    with pytest.raises(SnapshotError, match="Snapshot not found: missing-label"):
        snapshot_manager.load_snapshot("missing-label")

def test_load_snapshot_too_large(snapshot_manager, tmp_path):
    """Reject snapshots exceeding size limit."""
    # Create large snapshot file
    large_file = tmp_path / "snapshots" / "snapshot_large_20260315_103000.json"
    large_file.parent.mkdir(parents=True, exist_ok=True)
    large_file.write_text("x" * (101 * 1024 * 1024))  # 101MB

    with pytest.raises(SnapshotError, match="Snapshot file too large"):
        snapshot_manager.load_snapshot("large")

# tests/test_comparator.py - Testing diff logic

@pytest.fixture
def baseline_snapshot():
    """Baseline snapshot with known state."""
    return Snapshot(
        metadata=SnapshotMetadata(...),
        data={
            "initiatives": [
                {"key": "INIT-1", "status": "Planned", ...},
                {"key": "INIT-2", "status": "Planned", ...},
            ]
        }
    )

@pytest.fixture
def current_snapshot_with_drops(baseline_snapshot):
    """Current snapshot where INIT-2 dropped."""
    data = baseline_snapshot.data.copy()
    data["initiatives"][1]["status"] = "Cancelled"
    return Snapshot(metadata=baseline_snapshot.metadata, data=data)

def test_detect_dropped_initiatives(baseline_snapshot, current_snapshot_with_drops):
    """Correctly identifies dropped initiatives."""
    comparator = SnapshotComparator(baseline_snapshot, current_snapshot_with_drops)
    result = comparator._detect_dropped_initiatives()

    assert len(result) == 1
    assert result[0].initiative_key == "INIT-2"
    assert result[0].baseline_status == "Planned"
    assert result[0].current_status == "Cancelled"

def test_comparison_no_changes(baseline_snapshot):
    """Handles identical snapshots."""
    comparator = SnapshotComparator(baseline_snapshot, baseline_snapshot)
    result = comparator.compare()

    assert len(result.dropped_initiatives) == 0
    assert len(result.added_initiatives) == 0
    assert len(result.epic_churn) == 0
```

**Test Coverage Targets:**
```
src/snapshot.py:
- save_snapshot: 100% (all branches: valid label, atomic write, error cases)
- load_snapshot: 100% (found, not found, multiple, too large)
- list_snapshots: 100% (empty dir, single, multiple, sorted correctly)

src/comparator.py:
- _detect_dropped_initiatives: 100% (no drops, single, multiple)
- _detect_added_initiatives: 100% (no adds, single, multiple)
- _detect_epic_churn: 100% (no churn, add only, remove only, both)
- _calculate_team_stability: 100% (0%, 50%, 100% stability)

src/reports.py:
- generate_text: 95% (all report sections, with/without ETA)
- generate_markdown: 95% (table formatting, edge cases)
- generate_csv: 95% (encoding, special characters, empty)
```

**Edge Cases to Test:**
- Snapshot with 0 initiatives (empty dataset)
- Snapshot with orphaned epics only (no initiatives)
- Comparison where all initiatives changed (100% churn)
- Unicode in labels, summaries, team names
- Very long initiative summaries (>1000 chars)
- Circular dependencies (if future versions support parent/child initiatives)

**References:**
- pytest fixtures: https://docs.pytest.org/en/latest/how-to/fixtures.html
- pytest parametrize: https://docs.pytest.org/en/latest/how-to/parametrize.html
- freezegun: https://pypi.org/project/freezegun/

### Edge Cases & Error Handling

**1. Missing/Invalid Snapshot Files**:
```python
class SnapshotError(Exception):
    """Snapshot-specific errors."""
    pass

# In SnapshotManager.load_snapshot()
def load_snapshot(self, label: str) -> Snapshot:
    matches = list(self.snapshots_directory.glob(f"snapshot_{label}_*.json"))
    if not matches:
        raise SnapshotError(f"Snapshot not found: {label}")
    if len(matches) > 1:
        raise SnapshotError(f"Multiple snapshots found for label: {label}")
```

**2. Incompatible Snapshots**:
```python
def validate_compatibility(baseline: Snapshot, current: Snapshot):
    """Check if snapshots can be compared."""
    if baseline.metadata.jira_instance != current.metadata.jira_instance:
        warnings.warn(
            f"Comparing snapshots from different Jira instances: "
            f"{baseline.metadata.jira_instance} vs {current.metadata.jira_instance}"
        )

    baseline_fields = set(baseline.metadata.config_snapshot["custom_fields"].keys())
    current_fields = set(current.metadata.config_snapshot["custom_fields"].keys())

    if baseline_fields != current_fields:
        warnings.warn(
            f"Custom fields differ between snapshots. "
            f"Baseline: {baseline_fields}, Current: {current_fields}"
        )
```

**3. Missing ETA Values**:
```python
# In _detect_overruns()
if not baseline_eta:
    # Option B from brainstorm: Report as "No ETA set"
    no_eta_initiatives.append({
        "initiative_key": key,
        "summary": baseline_init["summary"],
        "status": "No ETA set at baseline"
    })
```

**4. Orphaned Epics Handling**:
- Include orphaned epics in epic churn analysis
- Compare orphaned epic lists between snapshots
- Report orphaned epics that were assigned to initiatives (or vice versa)

**Orphaned epics handling:**
def _compare_orphaned_epics(self) -> List[Dict[str, Any]]:
    """Track changes in orphaned epics between snapshots."""
    baseline_orphaned = {
        epic["key"]: epic
        for epic in self.baseline.data.get("orphaned_epics", [])
    }

    current_orphaned = {
        epic["key"]: epic
        for epic in self.current.data.get("orphaned_epics", [])
    }

    baseline_keys = set(baseline_orphaned.keys())
    current_keys = set(current_orphaned.keys())

    # Epics that were orphaned, now assigned to initiative
    resolved = baseline_keys - current_keys

    # Epics newly orphaned (were in initiative, now orphaned)
    newly_orphaned = current_keys - baseline_keys

    # Still orphaned in both
    still_orphaned = baseline_keys & current_keys

    return {
        "resolved_count": len(resolved),
        "resolved_epics": [baseline_orphaned[k] for k in resolved],
        "newly_orphaned_count": len(newly_orphaned),
        "newly_orphaned_epics": [current_orphaned[k] for k in newly_orphaned],
        "still_orphaned_count": len(still_orphaned)
    }
```

**Edge cases:**
- Snapshot directory doesn't exist: Create automatically in `save`, return `[]` in `list`
- Multiple snapshots with same label: Raise clear error with file paths
- Corrupted JSON: Catch `json.JSONDecodeError`, provide clear error message
- Snapshot from different Jira instance: Warn but allow (user might be migrating)
- Missing custom fields in old snapshot: Default to empty string, log warning

## System-Wide Impact

**Interaction Graph**:
- `snapshot` command calls existing `extract` flow → reuses `DataFetcher`, `OutputGenerator`
- `compare` command loads JSON files → no Jira API calls
- Reports output via `click.echo()` or file write → standard output pattern

**Error Propagation**:
- Config errors (missing file, invalid YAML) → fail fast with `ConfigError` (exit code 2)
- Snapshot errors (file not found, invalid JSON) → fail with `SnapshotError` (exit code 2)
- Comparison warnings (incompatible snapshots) → log warning but continue
- Report generation errors → fail with clear message (exit code 1)

**State Lifecycle Risks**:
- **Low risk** - Snapshots are read-only after creation
- No database, no concurrent writes
- Snapshot files are immutable (never updated, only created)

**API Surface Parity**:
- New commands follow existing CLI patterns (`--config`, `--verbose`, `--output`)
- JSON structure preserved (snapshot is extract + metadata)
- No breaking changes to existing commands

**Integration Test Scenarios**:
1. **End-to-end snapshot flow**: capture baseline → capture month1 → compare → verify reports
2. **ETA tracking toggle**: compare with/without ETA field, verify Reports 4-5 skipped
3. **Custom fields evolution**: capture with fields A,B → add field C → compare → verify handling
4. **Large dataset**: 100 initiatives, 500 epics → verify performance < 10s
5. **Error recovery**: invalid snapshot label → clear error message, no crash

## Acceptance Criteria

### Functional Requirements

- [ ] `snapshot` command captures Jira data with user-provided label
- [ ] Snapshots saved to `data/snapshots/` with metadata
- [ ] `snapshots list` shows all available snapshots with key info
- [ ] `compare` command loads two snapshots and generates diff reports
- [ ] Five report types generated (3 always, 2 conditional on ETA field)
- [ ] Reports available in text, markdown, and CSV formats
- [ ] Reports output to stdout or file (user's choice)

### Non-Functional Requirements

- [ ] Snapshot capture completes in < 30 seconds for typical dataset
- [ ] Comparison completes in < 10 seconds for typical quarter (100 initiatives, 500 epics)
- [ ] UTF-8 encoding preserved (emojis work in snapshots and reports)
- [ ] Error messages are clear and actionable
- [ ] No breaking changes to existing `extract` command

### Quality Gates

- [ ] Test coverage > 80%
- [ ] All tests passing
- [ ] README updated with snapshot commands and examples
- [ ] Edge cases handled (missing files, incompatible snapshots, missing ETA)

## Success Metrics

**From brainstorm**:
- Can capture quarterly baseline snapshot in < 30 seconds
- Can generate comparison report in < 10 seconds for typical quarter (100 initiatives, 500 epics)
- Commitment drift report accurately identifies all initiatives that dropped from Planned status
- Team stability metrics help leadership identify teams with planning discipline issues
- **Monthly leadership reports prepared in < 15 minutes using comparison output**

## Dependencies & Risks

**Dependencies**:
- No new external dependencies required
- Reuses existing libraries (click, pathlib, json, dataclasses)
- Relies on existing `extract` flow (no new Jira API integration)

**Risks**:

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Custom fields differ between snapshots | High | Medium | Warn user, handle missing fields gracefully (default to empty) |
| Large snapshot files (>10MB) | Medium | Low | JSON compression acceptable for quarterly scale; defer optimization |
| ETA delivery date calculation ambiguity | High | Medium | Resolve in Phase 4; document Open Question #1 decision |
| Snapshot label collisions (same label used twice) | Low | Low | Append timestamp to filename for uniqueness |

**Open questions to resolve** (from brainstorm):

1. **ETA delivery date calculation** (Priority: High)
   - Option A: Track status change to "Done" date (requires history tracking)
   - Option B: Use "Completion Date" custom field if populated
   - Option C: Binary on-time vs late from snapshot timing
   - **Decision needed before Phase 4**

2. **Report output format** (Priority: Medium)
   - Text (terminal), Markdown (GitHub/docs), CSV (spreadsheet)
   - **Decision: Support all three, default to text**

3. **Snapshot management** (Priority: Low, deferred)
   - Delete command?
   - Archive after quarter ends?
   - Storage growth management?
   - **Decision: Defer to future enhancement**

## Implementation Phases Summary

| Phase | Description | Files | Effort |
|-------|-------------|-------|--------|
| 1 | Snapshot capture | `jira_extract.py`, `src/snapshot.py` | 1-2 days |
| 2 | Snapshot listing | `jira_extract.py`, `src/snapshot.py` | 0.5 day |
| 3 | Comparison engine | `src/comparator.py` | 2-3 days |
| 4 | Report generation | `src/reports.py` | 1-2 days |
| 5 | Integration & testing | `tests/*`, `README.md` | 1-2 days |

**Total estimated effort**: 6-10 days

### Research Insights

**Best Practices:**
- Start with Phase 1 (snapshot capture) and validate end-to-end before continuing
- Use feature flags to enable incomplete phases (e.g., comparison without all 5 reports)
- Create smoke tests after each phase (manual testing checklist)
- Document known limitations in each phase's deliverables
- Get user feedback after Phase 1 and 3 (before investing in reports)

**Risk Mitigation:**
- **Phase 3 complexity risk**: Build `_detect_dropped_initiatives` first (simplest), validate, then tackle `_detect_epic_churn` (most complex)
- **ETA calculation ambiguity**: Implement Phase 4 with placeholder ETA logic, mark as "TODO" in code, resolve separately
- **Performance risk**: Add benchmarking script early (Phase 2) to validate <10s target with realistic data
- **Scope creep risk**: Explicitly defer Phase 6 features (delete command, multi-snapshot trends, visualization)

**Performance Benchmarks:**
```python
# tests/test_performance.py - Performance benchmarks

import pytest
import time
from pathlib import Path

@pytest.mark.performance
def test_snapshot_capture_performance(benchmark_data_100_initiatives):
    """Benchmark: Capture snapshot with 100 initiatives, 500 epics."""
    manager = SnapshotManager()
    config = load_config("config.yaml")

    start = time.time()
    result = manager.save_snapshot("perf-test", benchmark_data_100_initiatives, config)
    elapsed = time.time() - start

    assert elapsed < 30.0, f"Snapshot capture took {elapsed:.2f}s (target: <30s)"
    assert result.exists()

@pytest.mark.performance
def test_comparison_performance(baseline_snapshot_100, current_snapshot_100):
    """Benchmark: Compare snapshots with 100 initiatives, 500 epics."""
    comparator = SnapshotComparator(baseline_snapshot_100, current_snapshot_100)

    start = time.time()
    result = comparator.compare()
    elapsed = time.time() - start

    assert elapsed < 10.0, f"Comparison took {elapsed:.2f}s (target: <10s)"
    assert isinstance(result, ComparisonResult)
```

**Implementation Order:**
```
Phase 1: snapshot capture
  → Validate: Can create snapshots, files exist, metadata correct
  → Smoke test: Run extract, capture snapshot, verify JSON structure

Phase 2: snapshots list
  → Validate: Lists snapshots sorted correctly
  → Smoke test: Capture 3 snapshots, list shows all in order

Phase 3: comparison engine (incremental)
  → Step 1: Implement _detect_dropped_initiatives only
  → Validate: Test with known drop scenarios
  → Step 2: Implement _detect_added_initiatives
  → Validate: Test with known addition scenarios
  → Step 3: Implement _detect_epic_churn (most complex)
  → Validate: Test with complex churn scenarios
  → Step 4: Implement _calculate_team_stability
  → Validate: Test with various stability levels
  → Smoke test: Compare 2 real snapshots, verify all reports generated

Phase 4: report generation
  → Start with text format (simplest)
  → Then markdown (uses text as base)
  → Finally CSV (different structure)
  → Smoke test: Generate all 3 formats, verify readability

Phase 5: integration & testing
  → Add missing tests to reach 80% coverage
  → Update README
  → Final smoke test: End-to-end workflow from docs/plans
```

**References:**
- Incremental development: https://martinfowler.com/articles/continuousIntegration.html#MakeYourBuildSelf-testing
- Performance testing with pytest-benchmark: https://pytest-benchmark.readthedocs.io/

## Documentation Plan

**README Updates**:

Add new section: "Snapshot Tracking" with:
- Overview of snapshot commands
- Usage examples for typical workflow
- Configuration examples (with/without ETA)
- Sample report output
- Troubleshooting common issues

**Example documentation**:

```markdown
### Snapshot Tracking

Track plan stability and delivery over time by capturing quarterly snapshots and comparing them.

#### Capture Snapshots

```bash
# Capture baseline when plan stabilizes
python jira_extract.py snapshot --label "2026-Q2-baseline"

# Monthly checkpoints
python jira_extract.py snapshot --label "2026-Q2-month1"
python jira_extract.py snapshot --label "2026-Q2-month2"
python jira_extract.py snapshot --label "2026-Q2-end"
```

#### List Available Snapshots

```bash
python jira_extract.py snapshots list
```

#### Compare Snapshots

```bash
# Compare baseline vs current month
python jira_extract.py compare --from "2026-Q2-baseline" --to "2026-Q2-month1"

# Generate markdown report
python jira_extract.py compare --from "2026-Q2-baseline" --to "2026-Q2-end" --format markdown --output ./reports/q2-final.md

# Generate CSV export
python jira_extract.py compare --from "2026-Q2-baseline" --to "2026-Q2-end" --format csv --output ./reports/q2-comparison.csv
```

#### Configuration

**Mode 1: Plan Stability Only**
```yaml
custom_fields:
  initiatives:
    rag_status: "customfield_12111"
    quarter: "customfield_12108"
```
Generates 3 reports: commitment drift, new work injection, epic churn

**Mode 2: Plan Stability + Delivery Predictability**
```yaml
custom_fields:
  initiatives:
    rag_status: "customfield_12111"
    quarter: "customfield_12108"
    eta: "customfield_12204"  # Due Date field
```
Generates 5 reports: including initiative overruns and delivery metrics
```

## Sources & References

### Origin

- **Brainstorm document**: [docs/brainstorms/2026-03-15-quarterly-plan-snapshot-tracking-brainstorm.md](../brainstorms/2026-03-15-quarterly-plan-snapshot-tracking-brainstorm.md)
- **Key decisions carried forward**:
  - Approach A (Versioned Snapshots) chosen over database/spreadsheet approaches
  - Event-driven snapshot timing with semantic labels
  - Five report types (3 always, 2 conditional on ETA)
  - Same JSON structure as extract (no schema changes)
  - Storage location: `data/snapshots/`

### Internal References

- Similar patterns: `src/output.py` (JSON file I/O with timestamps)
- CLI structure: `jira_extract.py` (Click command patterns)
- Data structures: `src/builder.py` (hierarchy format)
- Testing patterns: `tests/test_output.py` (file operations with tmp_path)

### External References

- Click documentation: https://click.palletsprojects.com/
- Python dataclasses: https://docs.python.org/3/library/dataclasses.html#frozen-instances
- JSON best practices: https://jsonapi.org/
- Python set operations (performance): https://docs.python.org/3/library/stdtypes.html#set
- Atomic file operations: https://docs.python.org/3/library/tempfile.html
- OWASP Path Traversal Prevention: https://owasp.org/www-community/attacks/Path_Traversal_Attack
- pytest fixtures: https://docs.pytest.org/en/latest/how-to/fixtures.html
- freezegun (time mocking): https://pypi.org/project/freezegun/

### Related Work

- CSV export feature (PR #1): Dynamic column structure pattern
- Config-driven custom fields: Extensibility without code changes

### Enhancement Research

**Testing Patterns (MVP):**
- Fixture factories for test data generation
- Parametrized tests for multiple scenarios
- Time freezing with `freezegun` for deterministic timestamps
- Performance benchmarks with `pytest.mark.performance`
- Target: >80% test coverage across all modules

**Incremental Development Strategy (MVP):**
- Build and validate one phase at a time with smoke tests
- Document risks and mitigations upfront per phase
- Keep phases small and independently testable

**Edge Cases Handling (MVP):**
- Orphaned epics tracking in diff analysis
- Corrupted JSON file detection and clear error messages
- Missing field handling with sensible defaults

**Deferred Enhancements (Post-MVP):**
- Immutability (frozen dataclasses)
- Schema versioning for future compatibility
- O(n) algorithmic optimizations (acceptable for <50 initiatives)
- Path traversal prevention and security hardening
- Custom exception hierarchy
- Atomic file writes