# src/builder.py
from typing import List, Dict, Any
from collections import defaultdict


def build_hierarchy(
    initiatives: List[Dict[str, Any]],
    epics: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build initiative → team → epics hierarchy.

    Args:
        initiatives: List of initiative dictionaries
        epics: List of epic dictionaries

    Returns:
        Dictionary with hierarchical structure including:
        - initiatives: List of initiatives with contributing teams and epics
        - orphaned_epics: List of epics without parent initiatives
        - summary: Statistics
    """
    # Group epics by parent initiative
    epics_by_initiative: Dict[str, List[Dict]] = defaultdict(list)
    orphaned_epics = []

    for epic in epics:
        parent_key = epic.get("parent_key")
        if parent_key:
            epics_by_initiative[parent_key].append(epic)
        else:
            orphaned_epics.append({
                "key": epic["key"],
                "summary": epic["summary"],
                "status": epic["status"],
                "rag_status": epic["rag_status"],
                "url": epic["url"],
                "team_project_key": epic["team_project_key"],
            })

    # Build initiative hierarchy
    result_initiatives = []
    all_teams = set()

    for initiative in initiatives:
        initiative_key = initiative["key"]
        initiative_epics = epics_by_initiative.get(initiative_key, [])

        # Group epics by team
        epics_by_team: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"epics": []})

        for epic in initiative_epics:
            team_key = epic["team_project_key"]
            all_teams.add(team_key)

            if not epics_by_team[team_key].get("team_project_name"):
                epics_by_team[team_key]["team_project_key"] = team_key
                epics_by_team[team_key]["team_project_name"] = epic["team_project_name"]

            epics_by_team[team_key]["epics"].append({
                "key": epic["key"],
                "summary": epic["summary"],
                "status": epic["status"],
                "rag_status": epic["rag_status"],
                "url": epic["url"],
            })

        # Convert to list and sort by team key
        contributing_teams = sorted(
            epics_by_team.values(),
            key=lambda t: t["team_project_key"]
        )

        result_initiatives.append({
            "key": initiative["key"],
            "summary": initiative["summary"],
            "status": initiative["status"],
            "rag_status": initiative["rag_status"],
            "url": initiative["url"],
            "contributing_teams": contributing_teams,
        })

    # Build summary
    total_epics = sum(
        len(init["contributing_teams"])
        for init in result_initiatives
        for team in init["contributing_teams"]
    )

    return {
        "initiatives": result_initiatives,
        "orphaned_epics": orphaned_epics,
        "summary": {
            "total_initiatives": len(result_initiatives),
            "total_epics": total_epics + len(orphaned_epics),
            "teams_involved": sorted(list(all_teams)),
        },
    }
