# tests/test_jira_client.py
import pytest
import requests
from unittest.mock import Mock, patch
from src.jira_client import JiraClient, JiraAPIError


def test_jira_client_initialization():
    """Test JiraClient initialization."""
    client = JiraClient("test.atlassian.net", "test@example.com", "token123")

    assert client.base_url == "https://test.atlassian.net"
    assert client.auth == ("test@example.com", "token123")


def test_search_issues_success():
    """Test successful issue search."""
    client = JiraClient("test.atlassian.net", "test@example.com", "token123")

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "issues": [
            {"key": "INIT-1", "fields": {"summary": "Test"}},
            {"key": "INIT-2", "fields": {"summary": "Test 2"}},
        ],
        "total": 2,
        "maxResults": 100,
        "startAt": 0,
    }

    with patch.object(client.session, "get", return_value=mock_response):
        results = client.search_issues("project = INIT")

    assert len(results) == 2
    assert results[0]["key"] == "INIT-1"
    assert results[1]["key"] == "INIT-2"


def test_search_issues_pagination():
    """Test pagination handling."""
    client = JiraClient("test.atlassian.net", "test@example.com", "token123")

    # First page
    mock_response_1 = Mock()
    mock_response_1.status_code = 200
    mock_response_1.json.return_value = {
        "issues": [{"key": "INIT-1"}],
        "total": 2,
        "maxResults": 1,
        "startAt": 0,
    }

    # Second page
    mock_response_2 = Mock()
    mock_response_2.status_code = 200
    mock_response_2.json.return_value = {
        "issues": [{"key": "INIT-2"}],
        "total": 2,
        "maxResults": 1,
        "startAt": 1,
    }

    with patch.object(client.session, "get", side_effect=[mock_response_1, mock_response_2]):
        results = client.search_issues("project = INIT")

    assert len(results) == 2


def test_search_issues_api_error():
    """Test API error handling."""
    client = JiraClient("test.atlassian.net", "test@example.com", "token123")

    mock_response = Mock()
    mock_response.status_code = 403
    mock_response.text = "Forbidden"

    http_error = requests.HTTPError("403 Forbidden")
    http_error.response = mock_response
    mock_response.raise_for_status.side_effect = http_error

    with patch.object(client.session, "get", return_value=mock_response):
        with pytest.raises(JiraAPIError, match="403"):
            client.search_issues("project = INIT")


def test_get_custom_fields():
    """Test fetching custom fields."""
    client = JiraClient("test.atlassian.net", "test@example.com", "token123")

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"id": "customfield_10050", "name": "RAG Status"},
        {"id": "customfield_10051", "name": "Team"},
    ]

    with patch.object(client.session, "get", return_value=mock_response):
        fields = client.get_custom_fields()

    assert len(fields) == 2
    assert fields[0]["id"] == "customfield_10050"
