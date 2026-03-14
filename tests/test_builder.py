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


def test_build_hierarchy_with_custom_fields():
    """Test that custom fields from fetcher pass through to output."""
    initiatives = [
        {
            "key": "INIT-1",
            "summary": "Initiative 1",
            "status": "In Progress",
            "rag_status": "🟢",
            "objective": "Reduce technical debt",
            "quarter": "26 Q2",
            "url": "https://test.atlassian.net/browse/INIT-1",
        },
    ]

    epics = []

    result = build_hierarchy(initiatives, epics)

    assert len(result["initiatives"]) == 1
    initiative = result["initiatives"][0]

    # Check base fields
    assert initiative["key"] == "INIT-1"
    assert initiative["summary"] == "Initiative 1"
    assert initiative["status"] == "In Progress"
    assert initiative["url"] == "https://test.atlassian.net/browse/INIT-1"

    # Check custom fields pass through
    assert initiative["rag_status"] == "🟢"
    assert initiative["objective"] == "Reduce technical debt"
    assert initiative["quarter"] == "26 Q2"

    # Check contributing_teams present
    assert "contributing_teams" in initiative
    assert len(initiative["contributing_teams"]) == 0


def test_build_hierarchy_with_no_custom_fields():
    """Test build_hierarchy works with initiatives containing only base fields."""
    initiatives = [
        {
            "key": "INIT-1",
            "summary": "Initiative 1",
            "status": "Proposed",
            "url": "https://test.atlassian.net/browse/INIT-1",
        },
    ]

    epics = []

    result = build_hierarchy(initiatives, epics)

    assert len(result["initiatives"]) == 1
    initiative = result["initiatives"][0]

    # Check only base fields present
    assert initiative["key"] == "INIT-1"
    assert initiative["summary"] == "Initiative 1"
    assert initiative["status"] == "Proposed"
    assert initiative["url"] == "https://test.atlassian.net/browse/INIT-1"
    assert "contributing_teams" in initiative

    # No custom fields
    assert "rag_status" not in initiative
    assert "objective" not in initiative
