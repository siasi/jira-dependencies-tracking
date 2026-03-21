# tests/test_reports.py
"""Tests for report generation."""

import pytest
from src.comparator import (
    ComparisonResult,
    InitiativeChange,
    EpicChurn,
    TeamStability,
    OrphanedEpicsChange
)
from src.reports import ReportGenerator


@pytest.fixture
def sample_comparison_result():
    """Sample comparison result for testing."""
    return ComparisonResult(
        baseline_label="2026-Q1-baseline",
        current_label="2026-Q1-end",
        baseline_timestamp="2026-01-01T10:00:00Z",
        current_timestamp="2026-03-31T10:00:00Z",
        dropped_initiatives=[
            InitiativeChange(
                initiative_key="INIT-1",
                summary="Dropped Initiative",
                change_type="dropped",
                baseline_status="Planned",
                current_status="Cancelled",
                team_contributions=["TEAM1", "TEAM2"],
                details={}
            )
        ],
        added_initiatives=[
            InitiativeChange(
                initiative_key="INIT-2",
                summary="Added Initiative",
                change_type="added",
                baseline_status=None,
                current_status="Planned",
                team_contributions=["TEAM3"],
                details={}
            )
        ],
        epic_churn=[
            EpicChurn(
                initiative_key="INIT-3",
                initiative_summary="Initiative with Churn",
                epics_added=[
                    {"key": "EPIC-5", "summary": "New Epic"}
                ],
                epics_removed=[
                    {"key": "EPIC-4", "summary": "Removed Epic"}
                ],
                net_change=0
            )
        ],
        overrun_initiatives=None,
        team_stability=[
            TeamStability(
                team_project_key="TEAM1",
                total_epics_baseline=10,
                epics_unchanged=8,
                epics_added=1,
                epics_removed=2,
                stability_percentage=80.0,
                eta_delivery_rate=None
            ),
            TeamStability(
                team_project_key="TEAM2",
                total_epics_baseline=5,
                epics_unchanged=5,
                epics_added=0,
                epics_removed=0,
                stability_percentage=100.0,
                eta_delivery_rate=None
            )
        ],
        orphaned_epics_change=OrphanedEpicsChange(
            resolved_count=2,
            resolved_epics=[],
            newly_orphaned_count=1,
            newly_orphaned_epics=[
                {"key": "ORPHAN-1", "summary": "New Orphan"}
            ],
            still_orphaned_count=3
        )
    )


def test_generate_text_report(sample_comparison_result):
    """Text report formatted correctly."""
    generator = ReportGenerator(sample_comparison_result)
    report = generator.generate_text()

    assert "SNAPSHOT COMPARISON REPORT" in report
    assert "2026-Q1-baseline" in report
    assert "2026-Q1-end" in report
    assert "REPORT 1: COMMITMENT DRIFT" in report
    assert "REPORT 2: NEW WORK INJECTION" in report
    assert "REPORT 3: EPIC CHURN" in report
    assert "REPORT 5: TEAM STABILITY" in report
    assert "ORPHANED EPICS TRACKING" in report

    # Check specific content
    assert "INIT-1" in report
    assert "Dropped Initiative" in report
    assert "INIT-2" in report
    assert "Added Initiative" in report


def test_generate_markdown_report(sample_comparison_result):
    """Markdown tables render correctly."""
    generator = ReportGenerator(sample_comparison_result)
    report = generator.generate_markdown()

    assert "# Snapshot Comparison Report" in report
    assert "## Report 1: Commitment Drift" in report
    assert "## Report 2: New Work Injection" in report
    assert "## Report 3: Epic Churn" in report
    assert "## Report 5: Team Stability" in report
    assert "## Orphaned Epics Tracking" in report

    # Check markdown tables
    assert "| Initiative |" in report
    assert "|------------|" in report
    assert "| Team |" in report


def test_generate_csv_report(sample_comparison_result):
    """CSV export with proper encoding."""
    generator = ReportGenerator(sample_comparison_result)
    csv_output = generator.generate_csv()

    assert "Report Type" in csv_output
    assert "Initiative/Epic Key" in csv_output
    assert "Commitment Drift" in csv_output
    assert "New Work Injection" in csv_output
    assert "Epic Churn" in csv_output
    assert "Team Stability" in csv_output
    assert "INIT-1" in csv_output
    assert "INIT-2" in csv_output


def test_text_report_no_changes():
    """Text report handles no changes gracefully."""
    empty_result = ComparisonResult(
        baseline_label="baseline",
        current_label="current",
        baseline_timestamp="2026-01-01T10:00:00Z",
        current_timestamp="2026-03-31T10:00:00Z",
        dropped_initiatives=[],
        added_initiatives=[],
        epic_churn=[],
        overrun_initiatives=None,
        team_stability=[],
        orphaned_epics_change=OrphanedEpicsChange(
            resolved_count=0,
            resolved_epics=[],
            newly_orphaned_count=0,
            newly_orphaned_epics=[],
            still_orphaned_count=0
        )
    )

    generator = ReportGenerator(empty_result)
    report = generator.generate_text()

    assert "No initiatives dropped" in report
    assert "No new initiatives added" in report
    assert "No epic churn detected" in report


def test_markdown_report_with_eta_tracking():
    """Markdown report includes overruns when ETA tracking enabled."""
    result_with_eta = ComparisonResult(
        baseline_label="baseline",
        current_label="current",
        baseline_timestamp="2026-01-01T10:00:00Z",
        current_timestamp="2026-03-31T10:00:00Z",
        dropped_initiatives=[],
        added_initiatives=[],
        epic_churn=[],
        overrun_initiatives=[],  # Not None, indicating ETA tracking
        team_stability=[],
        orphaned_epics_change=OrphanedEpicsChange(
            resolved_count=0,
            resolved_epics=[],
            newly_orphaned_count=0,
            newly_orphaned_epics=[],
            still_orphaned_count=0
        )
    )

    generator = ReportGenerator(result_with_eta)
    report = generator.generate_markdown()

    assert "## Report 4: Initiative Overruns" in report


def test_epic_churn_details_in_text_report(sample_comparison_result):
    """Epic churn shows added and removed epics."""
    generator = ReportGenerator(sample_comparison_result)
    report = generator.generate_text()

    assert "INIT-3" in report
    assert "Initiative with Churn" in report
    assert "EPIC-5" in report
    assert "New Epic" in report
    assert "EPIC-4" in report
    assert "Removed Epic" in report


def test_team_stability_sorted_by_stability(sample_comparison_result):
    """Team stability shows metrics in correct order."""
    generator = ReportGenerator(sample_comparison_result)
    report = generator.generate_text()

    # TEAM1 should appear before TEAM2 (80% before 100%)
    team1_pos = report.find("TEAM1")
    team2_pos = report.find("TEAM2")
    assert team1_pos < team2_pos
    assert "80.0%" in report
    assert "100.0%" in report
