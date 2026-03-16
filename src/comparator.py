# src/comparator.py
"""Snapshot comparison and diff analysis."""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from src.snapshot import Snapshot


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
class OrphanedEpicsChange:
    """Changes in orphaned epics between snapshots."""
    resolved_count: int
    resolved_epics: List[Dict[str, Any]]
    newly_orphaned_count: int
    newly_orphaned_epics: List[Dict[str, Any]]
    still_orphaned_count: int


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

    # Orphaned Epics Tracking
    orphaned_epics_change: OrphanedEpicsChange


class SnapshotComparator:
    """Compares two snapshots and generates diff reports."""

    def __init__(self, baseline: Snapshot, current: Snapshot):
        """Initialize comparator with two snapshots.

        Args:
            baseline: Baseline snapshot (older)
            current: Current snapshot (newer)
        """
        self.baseline = baseline
        self.current = current
        self.has_eta = "eta" in baseline.metadata.config_snapshot.get("custom_fields", {}).get("initiatives", {})

    def compare(self) -> ComparisonResult:
        """Generate complete comparison analysis.

        Returns:
            ComparisonResult with all 5 reports + orphaned epics
        """
        return ComparisonResult(
            baseline_label=self.baseline.metadata.label,
            current_label=self.current.metadata.label,
            baseline_timestamp=self.baseline.metadata.timestamp,
            current_timestamp=self.current.metadata.timestamp,
            dropped_initiatives=self._detect_dropped_initiatives(),
            added_initiatives=self._detect_added_initiatives(),
            epic_churn=self._detect_epic_churn(),
            overrun_initiatives=self._detect_overruns() if self.has_eta else None,
            team_stability=self._calculate_team_stability(),
            orphaned_epics_change=self._compare_orphaned_epics()
        )

    def _detect_dropped_initiatives(self) -> List[InitiativeChange]:
        """Report 1: Initiatives that were Planned in baseline, now Proposed/Cancelled.

        Returns:
            List of initiatives that dropped from Planned status
        """
        baseline_planned = {
            i["key"]: i for i in self.baseline.data.get("initiatives", [])
            if i.get("status") == "Planned"
        }

        current_initiatives = {
            i["key"]: i for i in self.current.data.get("initiatives", [])
        }

        dropped = []
        for key, baseline_init in baseline_planned.items():
            current_init = current_initiatives.get(key)
            if current_init and current_init.get("status") in ["Proposed", "Cancelled"]:
                dropped.append(InitiativeChange(
                    initiative_key=key,
                    summary=baseline_init.get("summary", ""),
                    change_type="dropped",
                    baseline_status="Planned",
                    current_status=current_init.get("status"),
                    team_contributions=[
                        t.get("team_project_key", "")
                        for t in baseline_init.get("contributing_teams", [])
                    ],
                    details={"current_initiative": current_init}
                ))

        return dropped

    def _detect_added_initiatives(self) -> List[InitiativeChange]:
        """Report 2: Initiatives that weren't Planned in baseline, now Planned.

        Returns:
            List of newly planned initiatives
        """
        baseline_planned_keys = {
            i["key"] for i in self.baseline.data.get("initiatives", [])
            if i.get("status") == "Planned"
        }

        current_planned = [
            i for i in self.current.data.get("initiatives", [])
            if i.get("status") == "Planned" and i["key"] not in baseline_planned_keys
        ]

        return [
            InitiativeChange(
                initiative_key=i["key"],
                summary=i.get("summary", ""),
                change_type="added",
                baseline_status=None,
                current_status="Planned",
                team_contributions=[
                    t.get("team_project_key", "")
                    for t in i.get("contributing_teams", [])
                ],
                details={"initiative": i}
            )
            for i in current_planned
        ]

    def _detect_epic_churn(self) -> List[EpicChurn]:
        """Report 3: Epic additions/removals per initiative.

        Returns:
            List of initiatives with epic churn
        """
        baseline_initiatives = {
            i["key"]: i for i in self.baseline.data.get("initiatives", [])
        }
        current_initiatives = {
            i["key"]: i for i in self.current.data.get("initiatives", [])
        }

        churn_results = []

        # Check initiatives that exist in both snapshots
        for key in set(baseline_initiatives.keys()) & set(current_initiatives.keys()):
            baseline_init = baseline_initiatives[key]
            current_init = current_initiatives[key]

            # Flatten epic lists per initiative
            baseline_epics = {
                epic["key"]: epic
                for team in baseline_init.get("contributing_teams", [])
                for epic in team.get("epics", [])
            }

            current_epics = {
                epic["key"]: epic
                for team in current_init.get("contributing_teams", [])
                for epic in team.get("epics", [])
            }

            # Detect changes using set operations
            baseline_keys = set(baseline_epics.keys())
            current_keys = set(current_epics.keys())

            added_keys = current_keys - baseline_keys
            removed_keys = baseline_keys - current_keys

            if added_keys or removed_keys:
                churn_results.append(EpicChurn(
                    initiative_key=key,
                    initiative_summary=baseline_init.get("summary", ""),
                    epics_added=[current_epics[k] for k in added_keys],
                    epics_removed=[baseline_epics[k] for k in removed_keys],
                    net_change=len(added_keys) - len(removed_keys)
                ))

        return churn_results

    def _detect_overruns(self) -> List[Dict[str, Any]]:
        """Report 4: Initiatives delivered >20% beyond ETA (requires ETA field).

        Note: Placeholder implementation for MVP. Full ETA tracking deferred.

        Returns:
            List of overrun initiatives (empty for MVP)
        """
        # TODO: Implement ETA delivery tracking
        # Options from brainstorm:
        # A) Track status change to Done (needs history)
        # B) Use Completion Date custom field
        # C) Binary on-time vs late from snapshot timing
        return []

    def _calculate_team_stability(self) -> List[TeamStability]:
        """Report 5: Per-team stability metrics.

        Returns:
            List of team stability metrics, sorted by least stable first
        """
        baseline_teams: Dict[str, set] = {}
        current_teams: Dict[str, set] = {}

        # Build team epic mappings from baseline
        for init in self.baseline.data.get("initiatives", []):
            for team in init.get("contributing_teams", []):
                key = team.get("team_project_key")
                if not key:
                    continue
                if key not in baseline_teams:
                    baseline_teams[key] = set()
                baseline_teams[key].update(
                    epic["key"] for epic in team.get("epics", [])
                )

        # Build team epic mappings from current
        for init in self.current.data.get("initiatives", []):
            for team in init.get("contributing_teams", []):
                key = team.get("team_project_key")
                if not key:
                    continue
                if key not in current_teams:
                    current_teams[key] = set()
                current_teams[key].update(
                    epic["key"] for epic in team.get("epics", [])
                )

        # Calculate stability metrics
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

    def _compare_orphaned_epics(self) -> OrphanedEpicsChange:
        """Track changes in orphaned epics between snapshots.

        Returns:
            OrphanedEpicsChange with resolved, newly orphaned, and still orphaned counts
        """
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

        return OrphanedEpicsChange(
            resolved_count=len(resolved),
            resolved_epics=[baseline_orphaned[k] for k in resolved],
            newly_orphaned_count=len(newly_orphaned),
            newly_orphaned_epics=[current_orphaned[k] for k in newly_orphaned],
            still_orphaned_count=len(still_orphaned)
        )
