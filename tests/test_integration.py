# tests/test_integration.py
import pytest
from unittest.mock import Mock
from src.config import Config, JiraConfig, ProjectsConfig, OutputConfig, Filters
from src.fetcher import DataFetcher
from src.builder import build_hierarchy


def test_end_to_end_extraction_with_custom_fields():
    """Test full extraction flow with multiple custom fields."""
    # Setup mock Jira client
    mock_jira_client = Mock()
    mock_jira_client.base_url = "https://test.atlassian.net"

    # Configure mock responses
    mock_jira_client.search_issues.side_effect = [
        # Initiatives response
        [
            {
                "key": "INIT-1",
                "fields": {
                    "summary": "Test Initiative",
                    "status": {"name": "In Progress"},
                    "customfield_12111": {"value": "🟢"},
                    "customfield_12101": "Strategic Goal A",
                    "customfield_12108": {"value": "26 Q2"},
                },
            }
        ],
        # Epics response for INIT-1
        [
            {
                "key": "EPIC-1",
                "fields": {
                    "summary": "Test Epic",
                    "status": {"name": "In Progress"},
                    "parent": {"key": "INIT-1"},
                    "project": {"key": "TEAM1", "name": "Team One"},
                    "customfield_12111": {"value": "🟡"},
                },
            }
        ],
    ]

    config = Config(
        jira=JiraConfig(
            instance="test.atlassian.net",
            email="test@example.com",
            api_token="test-token"
        ),
        projects=ProjectsConfig(initiatives="INIT", teams=["TEAM1"]),
        custom_fields={
            "rag_status": "customfield_12111",
            "objective": "customfield_12101",
            "quarter": "customfield_12108",
        },
        output=OutputConfig(directory="./data", filename_pattern="test_{timestamp}.json"),
        filters=Filters(quarter="26 Q2"),
    )

    fetcher = DataFetcher(
        client=mock_jira_client,
        initiatives_project=config.projects.initiatives,
        team_projects=config.projects.teams,
        custom_fields=config.custom_fields,
        filter_quarter=config.filters.quarter,
    )

    # Fetch and build hierarchy
    initiatives_result = fetcher.fetch_initiatives()
    epics_result = fetcher.fetch_epics()
    hierarchy = build_hierarchy(initiatives_result.items, epics_result.items)

    # Verify custom fields in output
    assert len(hierarchy["initiatives"]) == 1
    initiative = hierarchy["initiatives"][0]

    assert initiative["key"] == "INIT-1"
    assert initiative["rag_status"] == "🟢"
    assert initiative["objective"] == "Strategic Goal A"
    assert initiative["quarter"] == "26 Q2"

    # Verify base initiative fields
    assert initiative["summary"] == "Test Initiative"
    assert initiative["status"] == "In Progress"
    assert "https://test.atlassian.net/browse/INIT-1" in initiative["url"]

    # Verify contributing teams structure
    assert "contributing_teams" in initiative
    assert len(initiative["contributing_teams"]) == 1

    # Verify epic appears in hierarchy with custom fields
    team = initiative["contributing_teams"][0]
    assert team["team_project_key"] == "TEAM1"
    assert team["team_project_name"] == "Team One"
    assert len(team["epics"]) == 1

    epic = team["epics"][0]
    assert epic["key"] == "EPIC-1"
    assert epic["summary"] == "Test Epic"
    assert epic["status"] == "In Progress"
    assert epic["rag_status"] == "🟡"  # Verify epic custom field extracted
    assert "https://test.atlassian.net/browse/EPIC-1" in epic["url"]

    # Verify fetch results indicate success
    assert initiatives_result.success is True
    assert epics_result.success is True

    # Verify hierarchy summary
    assert "summary" in hierarchy
    assert hierarchy["summary"]["total_initiatives"] == 1
    assert hierarchy["summary"]["total_epics"] == 1
    assert "TEAM1" in hierarchy["summary"]["teams_involved"]
