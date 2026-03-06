# tests/test_fetcher.py
import pytest
from unittest.mock import Mock, patch
from src.fetcher import DataFetcher, FetchResult


def test_fetch_initiatives_success():
    """Test successful initiative fetching."""
    mock_client = Mock()
    mock_client.search_issues.return_value = [
        {
            "key": "INIT-1",
            "fields": {
                "summary": "Test Initiative",
                "status": {"name": "In Progress"},
                "customfield_10050": {"value": "Green"},
            },
        },
    ]

    fetcher = DataFetcher(mock_client, "INIT", ["TEAM1"], "customfield_10050")
    result = fetcher.fetch_initiatives()

    assert result.success is True
    assert len(result.items) == 1
    assert result.items[0]["key"] == "INIT-1"
    assert result.items[0]["rag_status"] == "Green"


def test_fetch_epics_success():
    """Test successful epic fetching."""
    mock_client = Mock()
    mock_client.search_issues.return_value = [
        {
            "key": "TEAM1-10",
            "fields": {
                "summary": "Test Epic",
                "status": {"name": "To Do"},
                "parent": {"key": "INIT-1"},
                "project": {"key": "TEAM1", "name": "Team One"},
                "customfield_10050": {"value": "Amber"},
            },
        },
    ]

    fetcher = DataFetcher(mock_client, "INIT", ["TEAM1"], "customfield_10050")
    result = fetcher.fetch_epics()

    assert result.success is True
    assert len(result.items) == 1
    assert result.items[0]["key"] == "TEAM1-10"
    assert result.items[0]["parent_key"] == "INIT-1"
    assert result.items[0]["team_project_key"] == "TEAM1"


def test_fetch_all_parallel():
    """Test parallel fetching of initiatives and epics."""
    mock_client = Mock()

    def mock_search(jql, fields):
        if "project = INIT" in jql:
            return [{"key": "INIT-1", "fields": {"summary": "Init"}}]
        else:
            return [{"key": "TEAM1-1", "fields": {"summary": "Epic", "project": {"key": "TEAM1"}}}]

    mock_client.search_issues.side_effect = mock_search

    fetcher = DataFetcher(mock_client, "INIT", ["TEAM1"], "customfield_10050")
    initiatives_result, epics_result = fetcher.fetch_all()

    assert initiatives_result.success is True
    assert epics_result.success is True
    assert len(initiatives_result.items) == 1
    assert len(epics_result.items) == 1


def test_fetch_with_api_error():
    """Test handling of API errors."""
    from src.jira_client import JiraAPIError

    mock_client = Mock()
    mock_client.search_issues.side_effect = JiraAPIError("403 Forbidden")

    fetcher = DataFetcher(mock_client, "INIT", ["TEAM1"], "customfield_10050")
    result = fetcher.fetch_initiatives()

    assert result.success is False
    assert "403" in result.error_message
    assert len(result.items) == 0
