# tests/test_fetcher.py
import pytest
from unittest.mock import Mock, patch
from src.fetcher import DataFetcher, FetchResult


def test_fetch_initiatives_success():
    """Test successful initiative fetching."""
    mock_client = Mock()
    mock_client.base_url = "https://test.atlassian.net"
    mock_client.search_issues.return_value = [
        {
            "key": "INIT-1",
            "fields": {
                "summary": "Test Initiative",
                "status": {"name": "In Progress"},
                "assignee": {"displayName": "John Doe", "emailAddress": "john@example.com"},
                "customfield_10050": {"value": "Green"},
            },
        },
    ]

    fetcher = DataFetcher(
        mock_client,
        "INIT",
        ["TEAM1"],
        custom_fields={"rag_status": "customfield_10050"}
    )
    result = fetcher.fetch_initiatives()

    assert result.success is True
    assert len(result.items) == 1
    assert result.items[0]["key"] == "INIT-1"
    assert result.items[0]["assignee"] == "John Doe"
    assert result.items[0]["rag_status"] == "Green"


def test_fetch_epics_success():
    """Test successful epic fetching."""
    mock_client = Mock()
    mock_client.base_url = "https://test.atlassian.net"
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

    fetcher = DataFetcher(
        mock_client,
        "INIT",
        ["TEAM1"],
        custom_fields={"rag_status": "customfield_10050"}
    )
    result = fetcher.fetch_epics()

    assert result.success is True
    assert len(result.items) == 1
    assert result.items[0]["key"] == "TEAM1-10"
    assert result.items[0]["parent_key"] == "INIT-1"
    assert result.items[0]["team_project_key"] == "TEAM1"


def test_fetch_all_parallel():
    """Test parallel fetching of initiatives and epics."""
    mock_client = Mock()
    mock_client.base_url = "https://test.atlassian.net"

    def mock_search(jql, fields):
        if "project = INIT" in jql:
            return [{"key": "INIT-1", "fields": {"summary": "Init"}}]
        else:
            return [{"key": "TEAM1-1", "fields": {"summary": "Epic", "project": {"key": "TEAM1"}}}]

    mock_client.search_issues.side_effect = mock_search

    fetcher = DataFetcher(
        mock_client,
        "INIT",
        ["TEAM1"],
        custom_fields={"rag_status": "customfield_10050"}
    )
    initiatives_result, epics_result = fetcher.fetch_all()

    assert initiatives_result.success is True
    assert epics_result.success is True
    # Verify assignee is None when not present in Jira data
    assert initiatives_result.items[0]["assignee"] is None
    assert len(initiatives_result.items) == 1
    assert len(epics_result.items) == 1


def test_fetch_with_api_error():
    """Test handling of API errors."""
    from src.jira_client import JiraAPIError

    mock_client = Mock()
    mock_client.search_issues.side_effect = JiraAPIError("403 Forbidden")

    fetcher = DataFetcher(
        mock_client,
        "INIT",
        ["TEAM1"],
        custom_fields={"rag_status": "customfield_10050"}
    )
    result = fetcher.fetch_initiatives()

    assert result.success is False
    assert "403" in result.error_message
    assert len(result.items) == 0


def test_fetch_epics_with_empty_team_projects():
    """Test epic fetching with empty team projects list."""
    mock_client = Mock()
    mock_client.search_issues.return_value = []

    fetcher = DataFetcher(
        mock_client,
        "INIT",
        [],
        custom_fields={"rag_status": "customfield_10050"}
    )
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

    fetcher = DataFetcher(
        mock_client,
        "INIT",
        ["TEAM1", "TEAM2"],
        custom_fields={"rag_status": "customfield_10050"}
    )
    result = fetcher.fetch_epics()

    assert result.success is True
    assert len(result.items) == 2

    # Verify the JQL was constructed correctly with multiple projects
    call_args = mock_client.search_issues.call_args
    jql = call_args[0][0] if call_args[0] else call_args[1]['jql']
    assert "project = TEAM1 OR project = TEAM2" in jql
    assert "type = Epic" in jql


def test_data_fetcher_accepts_filter_params():
    """Test DataFetcher accepts filter parameters."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()

    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["TEAM1"],
        custom_fields={"rag_status": "customfield_12111", "quarter": "customfield_12108"},
        filter_quarter="25 Q1"
    )

    assert fetcher.filter_quarter == "25 Q1"
    assert fetcher.custom_fields["quarter"] == "customfield_12108"


def test_fetch_initiatives_jql_without_filters():
    """Test JQL construction without filters."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()
    mock_client.base_url = "https://test.atlassian.net"
    mock_client.search_issues.return_value = []

    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["TEAM1"],
        custom_fields={"rag_status": "customfield_12111"}
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
        custom_fields={"rag_status": "customfield_12111", "quarter": "customfield_12108"},
        filter_quarter="25 Q1"
    )

    result = fetcher.fetch_initiatives()

    # Check JQL includes filters
    call_args = mock_client.search_issues.call_args
    jql = call_args[0][0]

    assert "project = INIT" in jql
    assert "issuetype = Initiative" in jql
    assert 'status != "Done"' in jql
    # Field ID is quoted in JQL (field name lookup falls back to ID when mocked)
    assert '"customfield_12108" = "25 Q1"' in jql

    # Check JQL is returned in result
    assert result.jql is not None
    assert result.jql == jql


def test_fetch_initiatives_jql_uses_field_name():
    """Test JQL uses field name (not ID) when available from Jira."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()
    mock_client.search_issues.return_value = []
    mock_client.base_url = "https://test.atlassian.net"
    # Mock get_custom_fields to return field metadata
    mock_client.get_custom_fields.return_value = [
        {"id": "customfield_12108", "name": "Quarter[Dropdown]"},
        {"id": "customfield_12111", "name": "RAG Status"},
    ]

    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["TEAM1"],
        custom_fields={"quarter": "customfield_12108"},
        filter_quarter="26 Q2"
    )

    result = fetcher.fetch_initiatives()

    # Check JQL uses field name (not ID)
    call_args = mock_client.search_issues.call_args
    jql = call_args[0][0]

    assert '"Quarter[Dropdown]" = "26 Q2"' in jql
    assert 'customfield_12108' not in jql  # Should NOT use field ID


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


def test_fetch_epics_returns_jql():
    """Test fetch_epics returns JQL in result."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()
    mock_client.base_url = "https://test.atlassian.net"
    mock_client.search_issues.return_value = []

    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["RSK", "CBNK"],
        custom_fields={"rag_status": "customfield_12111"}
    )

    result = fetcher.fetch_epics()

    # Check JQL is returned
    assert result.jql is not None
    assert "project = RSK OR project = CBNK" in result.jql
    assert "issuetype = Epic" in result.jql


def test_fetch_epics_empty_teams_returns_none_jql():
    """Test fetch_epics with empty teams returns None for JQL."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()
    mock_client.base_url = "https://test.atlassian.net"

    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=[],
        custom_fields={"rag_status": "customfield_12111"}
    )

    result = fetcher.fetch_epics()

    # Empty teams means no query executed
    assert result.success is True
    assert result.jql is None


def test_extract_field_value_select_field():
    """Test extracting value from select field."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()
    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["TEAM1"],
        custom_fields={"rag_status": "customfield_12111"}
    )

    field_data = {"value": "🟢"}
    result = fetcher._extract_field_value(field_data)

    assert result == "🟢"


def test_extract_field_value_text_field():
    """Test extracting value from text field."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()
    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["TEAM1"],
        custom_fields={"objective": "customfield_12101"}
    )

    field_data = "Reduce technical debt"
    result = fetcher._extract_field_value(field_data)

    assert result == "Reduce technical debt"


def test_extract_field_value_null():
    """Test extracting value from None/missing field."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()
    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["TEAM1"],
        custom_fields={"rag_status": "customfield_12111"}
    )

    result = fetcher._extract_field_value(None)

    assert result is None


def test_extract_field_value_array_single_item():
    """Test extracting value from array field with single item."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()
    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["TEAM1"],
        custom_fields={"strategic_objective": "customfield_12101"}
    )

    # Array with single object (like multi-select field with one selection)
    field_data = [
        {
            "self": "https://test.atlassian.net/rest/api/3/customFieldOption/12697",
            "value": "2025_FR_DE_payments",
            "id": "12697"
        }
    ]
    result = fetcher._extract_field_value(field_data)

    assert result == "2025_FR_DE_payments"


def test_extract_field_value_array_multiple_items():
    """Test extracting values from array field with multiple items."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()
    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["TEAM1"],
        custom_fields={"strategic_objective": "customfield_12101"}
    )

    # Array with multiple objects (multi-select with multiple selections)
    field_data = [
        {"value": "2025_FR_DE_payments", "id": "12697"},
        {"value": "engineering_excellence", "id": "12698"}
    ]
    result = fetcher._extract_field_value(field_data)

    # Should return comma-separated values
    assert result == "2025_FR_DE_payments, engineering_excellence"


def test_extract_field_value_empty_array():
    """Test extracting value from empty array field."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()
    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["TEAM1"],
        custom_fields={"strategic_objective": "customfield_12101"}
    )

    result = fetcher._extract_field_value([])

    assert result is None


def test_fetch_initiatives_with_multiple_custom_fields():
    """Test fetching initiatives with multiple custom fields configured."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()
    mock_client.base_url = "https://test.atlassian.net"
    mock_client.search_issues.return_value = [
        {
            "key": "INIT-1",
            "fields": {
                "summary": "Test Initiative",
                "status": {"name": "In Progress"},
                "customfield_12111": {"value": "🟢"},
                "customfield_12101": "Reduce technical debt",
                "customfield_12108": {"value": "26 Q2"},
            },
        },
    ]

    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["TEAM1"],
        custom_fields={
            "rag_status": "customfield_12111",
            "objective": "customfield_12101",
            "quarter": "customfield_12108"
        }
    )
    result = fetcher.fetch_initiatives()

    assert result.success is True
    assert len(result.items) == 1

    initiative = result.items[0]
    assert initiative["key"] == "INIT-1"
    assert initiative["summary"] == "Test Initiative"
    assert initiative["status"] == "In Progress"
    assert initiative["rag_status"] == "🟢"
    assert initiative["objective"] == "Reduce technical debt"
    assert initiative["quarter"] == "26 Q2"
    assert "https://test.atlassian.net/browse/INIT-1" in initiative["url"]


def test_fetch_initiatives_with_no_custom_fields():
    """Test fetching initiatives with empty custom_fields dict."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()
    mock_client.base_url = "https://test.atlassian.net"
    mock_client.search_issues.return_value = [
        {
            "key": "INIT-1",
            "fields": {
                "summary": "Test Initiative",
                "status": {"name": "Proposed"},
            },
        },
    ]

    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["TEAM1"],
        custom_fields={}  # Empty dict
    )
    result = fetcher.fetch_initiatives()

    assert result.success is True
    assert len(result.items) == 1

    initiative = result.items[0]
    assert initiative["key"] == "INIT-1"
    assert initiative["summary"] == "Test Initiative"
    assert initiative["status"] == "Proposed"
    # No custom fields should be present
    assert "rag_status" not in initiative
    assert "objective" not in initiative


def test_fetch_initiatives_with_partially_missing_custom_field_values():
    """Test when some initiatives have custom field, others don't."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()
    mock_client.base_url = "https://test.atlassian.net"
    mock_client.search_issues.return_value = [
        {
            "key": "INIT-1",
            "fields": {
                "summary": "Init 1",
                "status": {"name": "In Progress"},
                "customfield_12111": {"value": "🟢"},
            },
        },
        {
            "key": "INIT-2",
            "fields": {
                "summary": "Init 2",
                "status": {"name": "Proposed"},
                # customfield_12111 is missing
            },
        },
    ]

    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["TEAM1"],
        custom_fields={"rag_status": "customfield_12111"}
    )
    result = fetcher.fetch_initiatives()

    assert result.success is True
    assert len(result.items) == 2

    assert result.items[0]["rag_status"] == "🟢"
    assert result.items[1]["rag_status"] is None  # Missing field returns None
