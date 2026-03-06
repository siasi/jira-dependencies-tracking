# tests/test_builder.py
from src.builder import build_hierarchy


def test_build_hierarchy_success():
    """Test building initiative-team-epic hierarchy."""
    initiatives = [
        {
            "key": "INIT-1",
            "summary": "Initiative 1",
            "status": "In Progress",
            "rag_status": "Green",
            "url": "https://test.atlassian.net/browse/INIT-1",
        },
    ]

    epics = [
        {
            "key": "TEAM1-10",
            "summary": "Epic 1",
            "status": "To Do",
            "rag_status": "Amber",
            "parent_key": "INIT-1",
            "team_project_key": "TEAM1",
            "team_project_name": "Team One",
            "url": "https://test.atlassian.net/browse/TEAM1-10",
        },
        {
            "key": "TEAM2-20",
            "summary": "Epic 2",
            "status": "Done",
            "rag_status": "Green",
            "parent_key": "INIT-1",
            "team_project_key": "TEAM2",
            "team_project_name": "Team Two",
            "url": "https://test.atlassian.net/browse/TEAM2-20",
        },
    ]

    result = build_hierarchy(initiatives, epics)

    assert len(result["initiatives"]) == 1
    assert result["initiatives"][0]["key"] == "INIT-1"

    teams = result["initiatives"][0]["contributing_teams"]
    assert len(teams) == 2

    # Check TEAM1
    team1 = next(t for t in teams if t["team_project_key"] == "TEAM1")
    assert len(team1["epics"]) == 1
    assert team1["epics"][0]["key"] == "TEAM1-10"

    # Check TEAM2
    team2 = next(t for t in teams if t["team_project_key"] == "TEAM2")
    assert len(team2["epics"]) == 1
    assert team2["epics"][0]["key"] == "TEAM2-20"


def test_build_hierarchy_with_orphaned_epics():
    """Test handling of epics without parent initiatives."""
    initiatives = [
        {
            "key": "INIT-1",
            "summary": "Initiative 1",
            "status": "In Progress",
            "rag_status": "Green",
            "url": "https://test.atlassian.net/browse/INIT-1",
        },
    ]

    epics = [
        {
            "key": "TEAM1-10",
            "summary": "Epic with parent",
            "status": "To Do",
            "rag_status": "Amber",
            "parent_key": "INIT-1",
            "team_project_key": "TEAM1",
            "team_project_name": "Team One",
            "url": "https://test.atlassian.net/browse/TEAM1-10",
        },
        {
            "key": "TEAM1-20",
            "summary": "Orphaned epic",
            "status": "Done",
            "rag_status": "Green",
            "parent_key": None,
            "team_project_key": "TEAM1",
            "team_project_name": "Team One",
            "url": "https://test.atlassian.net/browse/TEAM1-20",
        },
    ]

    result = build_hierarchy(initiatives, epics)

    assert len(result["initiatives"]) == 1
    assert len(result["orphaned_epics"]) == 1
    assert result["orphaned_epics"][0]["key"] == "TEAM1-20"


def test_build_hierarchy_empty():
    """Test with empty data."""
    result = build_hierarchy([], [])

    assert result["initiatives"] == []
    assert result["orphaned_epics"] == []
    assert result["summary"]["total_initiatives"] == 0
    assert result["summary"]["total_epics"] == 0


def test_build_hierarchy_initiative_without_epics():
    """Test initiative with no contributing epics."""
    initiatives = [
        {
            "key": "INIT-1",
            "summary": "Initiative 1",
            "status": "In Progress",
            "rag_status": "Green",
            "url": "https://test.atlassian.net/browse/INIT-1",
        },
    ]

    result = build_hierarchy(initiatives, [])

    assert len(result["initiatives"]) == 1
    assert result["initiatives"][0]["contributing_teams"] == []
