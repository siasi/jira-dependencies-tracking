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


def test_fetch_epics_with_empty_team_projects():
    """Test epic fetching with empty team projects list."""
    mock_client = Mock()
    mock_client.search_issues.return_value = []

    fetcher = DataFetcher(mock_client, "INIT", [], "customfield_10050")
    result = fetcher.fetch_epics()

    # Should handle gracefully and return empty results
    assert result.success is True
    assert len(result.items) == 0
    # Verify search_issues was not called with invalid JQL
    assert mock_client.search_issues.call_count == 0


def test_fetch_epics_with_multiple_teams():
    """Test epic fetching with multiple team projects."""
    mock_client = Mock()
    mock_client.search_issues.return_value = [
        {
            "key": "TEAM1-10",
            "fields": {
                "summary": "Epic 1",
                "status": {"name": "To Do"},
                "parent": {"key": "INIT-1"},
                "project": {"key": "TEAM1", "name": "Team One"},
                "customfield_10050": {"value": "Green"},
            },
        },
        {
            "key": "TEAM2-20",
            "fields": {
                "summary": "Epic 2",
                "status": {"name": "In Progress"},
                "parent": {"key": "INIT-1"},
                "project": {"key": "TEAM2", "name": "Team Two"},
                "customfield_10050": {"value": "Amber"},
            },
        },
    ]

    fetcher = DataFetcher(mock_client, "INIT", ["TEAM1", "TEAM2"], "customfield_10050")
    result = fetcher.fetch_epics()

    assert result.success is True
    assert len(result.items) == 2

    # Verify the JQL was constructed correctly with multiple projects
    call_args = mock_client.search_issues.call_args
    jql = call_args[0][0] if call_args[0] else call_args[1]['jql']
    assert "project = TEAM1 OR project = TEAM2" in jql
    assert "type = Epic" in jql


def test_data_fetcher_accepts_filter_params():
    """Test DataFetcher accepts quarter field and filter parameters."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()

    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["TEAM1"],
        rag_field_id="customfield_12111",
        quarter_field_id="customfield_12108",
        filter_quarter="25 Q1"
    )

    assert fetcher.quarter_field_id == "customfield_12108"
    assert fetcher.filter_quarter == "25 Q1"


def test_fetch_initiatives_jql_without_filters():
    """Test JQL construction without filters."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()
    mock_client.search_issues.return_value = []

    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["TEAM1"],
        rag_field_id="customfield_12111"
    )

    result = fetcher.fetch_initiatives()

    # Check JQL does not include filters
    call_args = mock_client.search_issues.call_args
    jql = call_args[0][0]

    assert "project = INIT" in jql
    assert "issuetype = Initiative" in jql
    assert "status !=" not in jql
    assert "customfield_12108" not in jql

    # NEW: Check JQL is returned in result
    assert result.jql is not None
    assert result.jql == jql


def test_fetch_initiatives_jql_with_quarter_filter():
    """Test JQL construction with quarter filter."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()
    mock_client.search_issues.return_value = []
    mock_client.base_url = "https://test.atlassian.net"

    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["TEAM1"],
        rag_field_id="customfield_12111",
        quarter_field_id="customfield_12108",
        filter_quarter="25 Q1"
    )

    result = fetcher.fetch_initiatives()

    # Check JQL includes filters
    call_args = mock_client.search_issues.call_args
    jql = call_args[0][0]

    assert "project = INIT" in jql
    assert "issuetype = Initiative" in jql
    assert 'status != "Done"' in jql
    assert 'customfield_12108 = "25 Q1"' in jql

    # Check JQL is returned in result
    assert result.jql is not None
    assert result.jql == jql


def test_fetch_result_includes_jql():
    """Test FetchResult includes jql field."""
    from src.fetcher import FetchResult

    result = FetchResult(
        success=True,
        items=[{"key": "TEST-1"}],
        jql="project = TEST AND issuetype = Epic"
    )

    assert result.jql == "project = TEST AND issuetype = Epic"

    # Test optional
    result_no_jql = FetchResult(success=True, items=[])
    assert result_no_jql.jql is None
