# src/reports.py
"""Report generation for snapshot comparisons."""

import csv
from io import StringIO
from typing import TextIO
from src.comparator import ComparisonResult


class ReportGenerator:
    """Generates comparison reports in multiple formats."""

    def __init__(self, comparison: ComparisonResult):
        """Initialize report generator.

        Args:
            comparison: ComparisonResult from SnapshotComparator
        """
        self.comparison = comparison

    def generate_text(self) -> str:
        """Generate text report for terminal output.

        Returns:
            Formatted text report
        """
        sections = []

        sections.append(self._text_header())
        sections.append(self._text_commitment_drift())
        sections.append(self._text_new_work_injection())
        sections.append(self._text_epic_churn())

        if self.comparison.overrun_initiatives is not None:
            sections.append(self._text_overruns())

        sections.append(self._text_team_stability())
        sections.append(self._text_orphaned_epics())

        return "\n\n".join(sections)

    def generate_markdown(self) -> str:
        """Generate markdown report with tables.

        Returns:
            Markdown formatted report
        """
        sections = []

        sections.append(self._md_header())
        sections.append(self._md_commitment_drift())
        sections.append(self._md_new_work_injection())
        sections.append(self._md_epic_churn())

        if self.comparison.overrun_initiatives is not None:
            sections.append(self._md_overruns())

        sections.append(self._md_team_stability())
        sections.append(self._md_orphaned_epics())

        return "\n\n".join(sections)

    def generate_csv(self) -> str:
        """Generate CSV export of comparison data.

        Returns:
            CSV formatted string
        """
        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "Report Type",
            "Initiative/Epic Key",
            "Summary",
            "Baseline Status",
            "Current Status",
            "Change Type",
            "Teams",
            "Details"
        ])

        # Commitment Drift
        for change in self.comparison.dropped_initiatives:
            writer.writerow([
                "Commitment Drift",
                change.initiative_key,
                change.summary,
                change.baseline_status,
                change.current_status,
                change.change_type,
                ", ".join(change.team_contributions),
                ""
            ])

        # New Work Injection
        for change in self.comparison.added_initiatives:
            writer.writerow([
                "New Work Injection",
                change.initiative_key,
                change.summary,
                change.baseline_status or "",
                change.current_status,
                change.change_type,
                ", ".join(change.team_contributions),
                ""
            ])

        # Epic Churn
        for churn in self.comparison.epic_churn:
            writer.writerow([
                "Epic Churn",
                churn.initiative_key,
                churn.initiative_summary,
                "",
                "",
                f"Net change: {churn.net_change}",
                "",
                f"Added: {len(churn.epics_added)}, Removed: {len(churn.epics_removed)}"
            ])

        # Team Stability
        for team in self.comparison.team_stability:
            writer.writerow([
                "Team Stability",
                team.team_project_key,
                "",
                "",
                "",
                f"Stability: {team.stability_percentage:.1f}%",
                "",
                f"Baseline: {team.total_epics_baseline}, Unchanged: {team.epics_unchanged}, Added: {team.epics_added}, Removed: {team.epics_removed}"
            ])

        return output.getvalue()

    # Text format helpers

    def _text_header(self) -> str:
        """Generate text report header."""
        return f"""SNAPSHOT COMPARISON REPORT
{'=' * 80}

Baseline:  {self.comparison.baseline_label} ({self.comparison.baseline_timestamp})
Current:   {self.comparison.current_label} ({self.comparison.current_timestamp})"""

    def _text_commitment_drift(self) -> str:
        """Generate commitment drift section (text)."""
        section = [f"REPORT 1: COMMITMENT DRIFT"]
        section.append("-" * 80)

        if not self.comparison.dropped_initiatives:
            section.append("No initiatives dropped from Planned status.")
            return "\n".join(section)

        section.append(f"\n{len(self.comparison.dropped_initiatives)} initiative(s) dropped from Planned:\n")

        for change in self.comparison.dropped_initiatives:
            section.append(f"  [{change.initiative_key}] {change.summary}")
            section.append(f"    Status change: {change.baseline_status} → {change.current_status}")
            section.append(f"    Teams: {', '.join(change.team_contributions)}")
            section.append("")

        return "\n".join(section)

    def _text_new_work_injection(self) -> str:
        """Generate new work injection section (text)."""
        section = [f"REPORT 2: NEW WORK INJECTION"]
        section.append("-" * 80)

        if not self.comparison.added_initiatives:
            section.append("No new initiatives added to Planned status.")
            return "\n".join(section)

        section.append(f"\n{len(self.comparison.added_initiatives)} new initiative(s) added to Planned:\n")

        for change in self.comparison.added_initiatives:
            section.append(f"  [{change.initiative_key}] {change.summary}")
            section.append(f"    Status: {change.current_status}")
            section.append(f"    Teams: {', '.join(change.team_contributions)}")
            section.append("")

        return "\n".join(section)

    def _text_epic_churn(self) -> str:
        """Generate epic churn section (text)."""
        section = [f"REPORT 3: EPIC CHURN"]
        section.append("-" * 80)

        if not self.comparison.epic_churn:
            section.append("No epic churn detected.")
            return "\n".join(section)

        section.append(f"\n{len(self.comparison.epic_churn)} initiative(s) with epic changes:\n")

        for churn in self.comparison.epic_churn:
            section.append(f"  [{churn.initiative_key}] {churn.initiative_summary}")
            section.append(f"    Epics added: {len(churn.epics_added)}")
            section.append(f"    Epics removed: {len(churn.epics_removed)}")
            section.append(f"    Net change: {churn.net_change:+d}")

            if churn.epics_added:
                section.append(f"    Added:")
                for epic in churn.epics_added:
                    section.append(f"      + [{epic['key']}] {epic.get('summary', '')}")

            if churn.epics_removed:
                section.append(f"    Removed:")
                for epic in churn.epics_removed:
                    section.append(f"      - [{epic['key']}] {epic.get('summary', '')}")

            section.append("")

        return "\n".join(section)

    def _text_overruns(self) -> str:
        """Generate overruns section (text)."""
        section = [f"REPORT 4: INITIATIVE OVERRUNS (ETA TRACKING)"]
        section.append("-" * 80)
        section.append("ETA delivery tracking not yet implemented.")
        return "\n".join(section)

    def _text_team_stability(self) -> str:
        """Generate team stability section (text)."""
        section = [f"REPORT 5: TEAM STABILITY"]
        section.append("-" * 80)

        if not self.comparison.team_stability:
            section.append("No team data available.")
            return "\n".join(section)

        section.append(f"\nTeam stability metrics (sorted by least stable):\n")

        for team in self.comparison.team_stability:
            section.append(f"  {team.team_project_key}")
            section.append(f"    Stability: {team.stability_percentage:.1f}%")
            section.append(f"    Baseline epics: {team.total_epics_baseline}")
            section.append(f"    Unchanged: {team.epics_unchanged}")
            section.append(f"    Added: {team.epics_added}")
            section.append(f"    Removed: {team.epics_removed}")
            section.append("")

        return "\n".join(section)

    def _text_orphaned_epics(self) -> str:
        """Generate orphaned epics section (text)."""
        section = [f"ORPHANED EPICS TRACKING"]
        section.append("-" * 80)

        change = self.comparison.orphaned_epics_change

        section.append(f"Resolved (assigned to initiatives): {change.resolved_count}")
        section.append(f"Newly orphaned: {change.newly_orphaned_count}")
        section.append(f"Still orphaned: {change.still_orphaned_count}")

        if change.newly_orphaned_count > 0:
            section.append(f"\nNewly orphaned epics:")
            for epic in change.newly_orphaned_epics:
                section.append(f"  [{epic['key']}] {epic.get('summary', '')}")

        return "\n".join(section)

    # Markdown format helpers

    def _md_header(self) -> str:
        """Generate markdown report header."""
        return f"""# Snapshot Comparison Report

**Baseline:** {self.comparison.baseline_label} (`{self.comparison.baseline_timestamp}`)
**Current:** {self.comparison.current_label} (`{self.comparison.current_timestamp}`)"""

    def _md_commitment_drift(self) -> str:
        """Generate commitment drift section (markdown)."""
        section = [f"## Report 1: Commitment Drift"]

        if not self.comparison.dropped_initiatives:
            section.append("\n✓ No initiatives dropped from Planned status.")
            return "\n".join(section)

        section.append(f"\n**{len(self.comparison.dropped_initiatives)} initiative(s) dropped from Planned:**\n")

        section.append("| Initiative | Summary | Status Change | Teams |")
        section.append("|------------|---------|---------------|-------|")

        for change in self.comparison.dropped_initiatives:
            teams = ", ".join(change.team_contributions)
            status_change = f"{change.baseline_status} → {change.current_status}"
            section.append(f"| {change.initiative_key} | {change.summary} | {status_change} | {teams} |")

        return "\n".join(section)

    def _md_new_work_injection(self) -> str:
        """Generate new work injection section (markdown)."""
        section = [f"## Report 2: New Work Injection"]

        if not self.comparison.added_initiatives:
            section.append("\n✓ No new initiatives added to Planned status.")
            return "\n".join(section)

        section.append(f"\n**{len(self.comparison.added_initiatives)} new initiative(s) added to Planned:**\n")

        section.append("| Initiative | Summary | Teams |")
        section.append("|------------|---------|-------|")

        for change in self.comparison.added_initiatives:
            teams = ", ".join(change.team_contributions)
            section.append(f"| {change.initiative_key} | {change.summary} | {teams} |")

        return "\n".join(section)

    def _md_epic_churn(self) -> str:
        """Generate epic churn section (markdown)."""
        section = [f"## Report 3: Epic Churn"]

        if not self.comparison.epic_churn:
            section.append("\n✓ No epic churn detected.")
            return "\n".join(section)

        section.append(f"\n**{len(self.comparison.epic_churn)} initiative(s) with epic changes:**\n")

        for churn in self.comparison.epic_churn:
            section.append(f"### {churn.initiative_key}: {churn.initiative_summary}")
            section.append(f"\n- **Epics added:** {len(churn.epics_added)}")
            section.append(f"- **Epics removed:** {len(churn.epics_removed)}")
            section.append(f"- **Net change:** {churn.net_change:+d}\n")

            if churn.epics_added:
                section.append("**Added:**")
                for epic in churn.epics_added:
                    section.append(f"- ➕ [{epic['key']}] {epic.get('summary', '')}")
                section.append("")

            if churn.epics_removed:
                section.append("**Removed:**")
                for epic in churn.epics_removed:
                    section.append(f"- ➖ [{epic['key']}] {epic.get('summary', '')}")
                section.append("")

        return "\n".join(section)

    def _md_overruns(self) -> str:
        """Generate overruns section (markdown)."""
        section = [f"## Report 4: Initiative Overruns"]
        section.append("\n*ETA delivery tracking not yet implemented.*")
        return "\n".join(section)

    def _md_team_stability(self) -> str:
        """Generate team stability section (markdown)."""
        section = [f"## Report 5: Team Stability"]

        if not self.comparison.team_stability:
            section.append("\n*No team data available.*")
            return "\n".join(section)

        section.append(f"\n**Team stability metrics (sorted by least stable):**\n")

        section.append("| Team | Stability | Baseline Epics | Unchanged | Added | Removed |")
        section.append("|------|-----------|----------------|-----------|-------|---------|")

        for team in self.comparison.team_stability:
            section.append(
                f"| {team.team_project_key} | {team.stability_percentage:.1f}% | "
                f"{team.total_epics_baseline} | {team.epics_unchanged} | "
                f"{team.epics_added} | {team.epics_removed} |"
            )

        return "\n".join(section)

    def _md_orphaned_epics(self) -> str:
        """Generate orphaned epics section (markdown)."""
        section = [f"## Orphaned Epics Tracking"]

        change = self.comparison.orphaned_epics_change

        section.append(f"\n- **Resolved (assigned to initiatives):** {change.resolved_count}")
        section.append(f"- **Newly orphaned:** {change.newly_orphaned_count}")
        section.append(f"- **Still orphaned:** {change.still_orphaned_count}")

        if change.newly_orphaned_count > 0:
            section.append(f"\n**Newly orphaned epics:**\n")
            for epic in change.newly_orphaned_epics:
                section.append(f"- [{epic['key']}] {epic.get('summary', '')}")

        return "\n".join(section)
