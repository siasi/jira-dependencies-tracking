# Jira Dependencies Tracking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python CLI tool that extracts Jira initiatives and epics with their relationships, showing which teams contribute to which initiatives.

**Architecture:** Parallel fetch approach using ThreadPoolExecutor to concurrently fetch initiatives from INIT project and epics from team projects, then match relationships using parent links. Output structured JSON with hierarchy, completeness tracking, and orphaned epics.

**Tech Stack:** Python 3.9+, Click (CLI), requests (HTTP), python-dotenv (env vars), PyYAML (config)

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `setup.py`
- Create: `.env.example`
- Create: `config.yaml.example`
- Create: `src/__init__.py`
- Create: `README.md`

**Step 1: Create requirements.txt**

```txt
requests>=2.31.0
python-dotenv>=1.0.0
pyyaml>=6.0
click>=8.1.0
```

**Step 2: Create setup.py**

```python
from setuptools import setup, find_packages

setup(
    name="jira-dependencies-tracking",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
        "pyyaml>=6.0",
        "click>=8.1.0",
    ],
    entry_points={
        "console_scripts": [
            "jira-extract=jira_extract:cli",
        ],
    },
    python_requires=">=3.9",
)
```

**Step 3: Create .env.example**

```
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-api-token-here
```

**Step 4: Create config.yaml.example**

```yaml
jira:
  instance: "your-company.atlassian.net"

projects:
  initiatives: "INIT"
  teams:
    - "TEAM1"
    - "TEAM2"

custom_fields:
  rag_status: "customfield_XXXXX"

output:
  directory: "./data"
  filename_pattern: "jira_extract_{timestamp}.json"
```

**Step 5: Create src/__init__.py**

```python
"""Jira Dependencies Tracking Tool."""

__version__ = "0.1.0"
```

**Step 6: Create README.md**

```markdown
# Jira Dependencies Tracking

Extract Jira initiatives and epics to analyze team contributions.

## Setup

1. **Prerequisites:** Python 3.9+, Jira Cloud access

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure:**
   ```bash
   cp config.yaml.example config.yaml
   cp .env.example .env
   ```

4. **Edit config.yaml:**
   - Update `jira.instance` with your Jira URL
   - Update `projects.teams` with your team project keys
   - Find RAG custom field ID: `python jira_scan.py list-fields`

5. **Edit .env:**
   - Add your Jira email
   - Get API token from: https://id.atlassian.com/manage-profile/security/api-tokens

## Usage

Extract data:
```bash
python jira_scan.py extract
```

List custom fields:
```bash
python jira_scan.py list-fields
```

Validate config:
```bash
python jira_scan.py validate-config
```

Options:
```bash
python jira_scan.py extract --config custom.yaml --output ./report.json --verbose
```

## Output

JSON file in `./data/` directory with:
- Initiative → Team → Epics hierarchy
- Status and RAG indicators
- Completeness tracking
- Orphaned epics (no parent initiative)

## Troubleshooting

**Authentication failed:**
- Verify API token is valid
- Check email matches Atlassian account

**Custom field not found:**
- Run `list-fields` to find correct field ID
- Update `custom_fields.rag_status` in config.yaml

**Missing data:**
- Check `extraction_status` in output JSON
- Verify permissions to access all projects
- Tool continues with partial data but reports issues
```

**Step 7: Commit scaffolding**

```bash
git add requirements.txt setup.py .env.example config.yaml.example src/__init__.py README.md
git commit -m "chore: add project scaffolding and documentation"
```

---

## Task 2: Configuration Module

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
# tests/test_config.py
import os
import pytest
from pathlib import Path
from src.config import load_config, ConfigError


def test_load_config_success(tmp_path):
    """Test loading valid configuration."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
jira:
  instance: "test.atlassian.net"
projects:
  initiatives: "INIT"
  teams:
    - "TEAM1"
custom_fields:
  rag_status: "customfield_10050"
output:
  directory: "./data"
  filename_pattern: "jira_{timestamp}.json"
""")

    os.environ["JIRA_EMAIL"] = "test@example.com"
    os.environ["JIRA_API_TOKEN"] = "test-token"

    config = load_config(str(config_file))

    assert config["jira"]["instance"] == "test.atlassian.net"
    assert config["jira"]["email"] == "test@example.com"
    assert config["jira"]["api_token"] == "test-token"
    assert config["projects"]["initiatives"] == "INIT"
    assert "TEAM1" in config["projects"]["teams"]


def test_load_config_missing_env_vars(tmp_path):
    """Test error when environment variables missing."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
jira:
  instance: "test.atlassian.net"
projects:
  initiatives: "INIT"
  teams: []
""")

    # Clear env vars
    os.environ.pop("JIRA_EMAIL", None)
    os.environ.pop("JIRA_API_TOKEN", None)

    with pytest.raises(ConfigError, match="JIRA_EMAIL"):
        load_config(str(config_file))


def test_load_config_missing_file():
    """Test error when config file doesn't exist."""
    with pytest.raises(ConfigError, match="not found"):
        load_config("/nonexistent/config.yaml")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.config'"

**Step 3: Write minimal implementation**

```python
# src/config.py
import os
from pathlib import Path
from typing import Dict, Any
import yaml
from dotenv import load_dotenv


class ConfigError(Exception):
    """Configuration error."""
    pass


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file and environment variables.

    Args:
        config_path: Path to config.yaml file

    Returns:
        Complete configuration dictionary

    Raises:
        ConfigError: If config is invalid or required values missing
    """
    # Load environment variables from .env if present
    load_dotenv()

    # Check config file exists
    config_file = Path(config_path)
    if not config_file.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    # Load YAML config
    with open(config_file) as f:
        config = yaml.safe_load(f)

    # Load credentials from environment
    email = os.environ.get("JIRA_EMAIL")
    api_token = os.environ.get("JIRA_API_TOKEN")

    if not email:
        raise ConfigError(
            "JIRA_EMAIL environment variable required. "
            "Create .env file or export JIRA_EMAIL=your-email@company.com"
        )

    if not api_token:
        raise ConfigError(
            "JIRA_API_TOKEN environment variable required. "
            "Get token from: https://id.atlassian.com/manage-profile/security/api-tokens"
        )

    # Add credentials to config
    config["jira"]["email"] = email
    config["jira"]["api_token"] = api_token

    return config
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add configuration loading module"
```

---

## Task 3: Jira API Client

**Files:**
- Create: `src/jira_client.py`
- Create: `tests/test_jira_client.py`

**Step 1: Write the failing test**

```python
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
    mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")

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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_jira_client.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.jira_client'"

**Step 3: Write minimal implementation**

```python
# src/jira_client.py
import time
from typing import List, Dict, Any
import requests


class JiraAPIError(Exception):
    """Jira API error."""
    pass


class JiraClient:
    """Jira Cloud REST API client."""

    def __init__(self, instance: str, email: str, api_token: str, timeout: int = 30):
        """Initialize Jira client.

        Args:
            instance: Jira instance URL (e.g., "company.atlassian.net")
            email: User email for authentication
            api_token: API token from Atlassian
            timeout: Request timeout in seconds
        """
        # Normalize instance URL
        if not instance.startswith("http"):
            instance = f"https://{instance}"
        self.base_url = instance.rstrip("/")

        self.auth = (email, api_token)
        self.timeout = timeout

        # Session for connection pooling
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def search_issues(
        self,
        jql: str,
        fields: List[str] = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search for issues using JQL.

        Args:
            jql: JQL query string
            fields: List of field names to return (None = all fields)
            max_results: Results per page (max 100)

        Returns:
            List of issue dictionaries

        Raises:
            JiraAPIError: If API request fails
        """
        all_issues = []
        start_at = 0

        while True:
            params = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": min(max_results, 100),
            }

            if fields:
                params["fields"] = ",".join(fields)

            try:
                response = self.session.get(
                    f"{self.base_url}/rest/api/3/search",
                    params=params,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

                issues = data.get("issues", [])
                all_issues.extend(issues)

                # Check if more results available
                total = data.get("total", 0)
                if start_at + len(issues) >= total:
                    break

                start_at += len(issues)

            except requests.HTTPError as e:
                raise JiraAPIError(f"Jira API error: {e.response.status_code} - {e.response.text}")
            except requests.RequestException as e:
                raise JiraAPIError(f"Request failed: {str(e)}")

        return all_issues

    def get_custom_fields(self) -> List[Dict[str, Any]]:
        """Get all custom fields.

        Returns:
            List of custom field dictionaries with id and name

        Raises:
            JiraAPIError: If API request fails
        """
        try:
            response = self.session.get(
                f"{self.base_url}/rest/api/3/field",
                timeout=self.timeout,
            )
            response.raise_for_status()

            all_fields = response.json()
            # Filter to custom fields only
            custom_fields = [
                f for f in all_fields
                if f.get("id", "").startswith("customfield_")
            ]

            return custom_fields

        except requests.HTTPError as e:
            raise JiraAPIError(f"Jira API error: {e.response.status_code} - {e.response.text}")
        except requests.RequestException as e:
            raise JiraAPIError(f"Request failed: {str(e)}")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_jira_client.py -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add src/jira_client.py tests/test_jira_client.py
git commit -m "feat: add Jira API client with pagination support"
```

---

## Task 4: Data Fetcher with Parallel Execution

**Files:**
- Create: `src/fetcher.py`
- Create: `tests/test_fetcher.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_fetcher.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.fetcher'"

**Step 3: Write minimal implementation**

```python
# src/fetcher.py
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
from src.jira_client import JiraClient, JiraAPIError


@dataclass
class FetchResult:
    """Result of a fetch operation."""
    success: bool
    items: List[Dict[str, Any]]
    error_message: Optional[str] = None
    project_key: Optional[str] = None


class DataFetcher:
    """Fetches initiatives and epics from Jira."""

    def __init__(
        self,
        client: JiraClient,
        initiatives_project: str,
        team_projects: List[str],
        rag_field_id: str,
    ):
        """Initialize data fetcher.

        Args:
            client: JiraClient instance
            initiatives_project: Project key for initiatives (e.g., "INIT")
            team_projects: List of team project keys
            rag_field_id: Custom field ID for RAG status
        """
        self.client = client
        self.initiatives_project = initiatives_project
        self.team_projects = team_projects
        self.rag_field_id = rag_field_id

    def fetch_initiatives(self) -> FetchResult:
        """Fetch all initiatives from the initiatives project.

        Returns:
            FetchResult with initiatives data
        """
        jql = f"project = {self.initiatives_project} AND type = Initiative"
        fields = ["summary", "status", self.rag_field_id]

        try:
            issues = self.client.search_issues(jql, fields=fields)

            # Normalize initiative data
            initiatives = []
            for issue in issues:
                fields_data = issue.get("fields", {})

                # Extract RAG status
                rag_field = fields_data.get(self.rag_field_id, {})
                rag_status = None
                if isinstance(rag_field, dict):
                    rag_status = rag_field.get("value")
                elif isinstance(rag_field, str):
                    rag_status = rag_field

                initiatives.append({
                    "key": issue["key"],
                    "summary": fields_data.get("summary", ""),
                    "status": fields_data.get("status", {}).get("name", "Unknown"),
                    "rag_status": rag_status,
                    "url": f"{self.client.base_url}/browse/{issue['key']}",
                })

            return FetchResult(success=True, items=initiatives)

        except JiraAPIError as e:
            return FetchResult(
                success=False,
                items=[],
                error_message=str(e),
                project_key=self.initiatives_project,
            )

    def fetch_epics(self) -> FetchResult:
        """Fetch all epics from team projects.

        Returns:
            FetchResult with epics data
        """
        # Build JQL for all team projects
        project_filter = " OR ".join([f"project = {p}" for p in self.team_projects])
        jql = f"({project_filter}) AND type = Epic"
        fields = ["summary", "status", "parent", "project", self.rag_field_id]

        try:
            issues = self.client.search_issues(jql, fields=fields)

            # Normalize epic data
            epics = []
            for issue in issues:
                fields_data = issue.get("fields", {})

                # Extract parent initiative key
                parent = fields_data.get("parent", {})
                parent_key = parent.get("key") if parent else None

                # Extract RAG status
                rag_field = fields_data.get(self.rag_field_id, {})
                rag_status = None
                if isinstance(rag_field, dict):
                    rag_status = rag_field.get("value")
                elif isinstance(rag_field, str):
                    rag_status = rag_field

                # Extract project info
                project = fields_data.get("project", {})

                epics.append({
                    "key": issue["key"],
                    "summary": fields_data.get("summary", ""),
                    "status": fields_data.get("status", {}).get("name", "Unknown"),
                    "rag_status": rag_status,
                    "parent_key": parent_key,
                    "team_project_key": project.get("key", ""),
                    "team_project_name": project.get("name", ""),
                    "url": f"{self.client.base_url}/browse/{issue['key']}",
                })

            return FetchResult(success=True, items=epics)

        except JiraAPIError as e:
            return FetchResult(
                success=False,
                items=[],
                error_message=str(e),
            )

    def fetch_all(self) -> Tuple[FetchResult, FetchResult]:
        """Fetch initiatives and epics in parallel.

        Returns:
            Tuple of (initiatives_result, epics_result)
        """
        with ThreadPoolExecutor(max_workers=2) as executor:
            initiatives_future = executor.submit(self.fetch_initiatives)
            epics_future = executor.submit(self.fetch_epics)

            initiatives_result = initiatives_future.result()
            epics_result = epics_future.result()

        return initiatives_result, epics_result
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_fetcher.py -v`
Expected: PASS (all 4 tests)

**Step 5: Commit**

```bash
git add src/fetcher.py tests/test_fetcher.py
git commit -m "feat: add parallel data fetcher for initiatives and epics"
```

---

## Task 5: Relationship Builder

**Files:**
- Create: `src/builder.py`
- Create: `tests/test_builder.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_builder.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.builder'"

**Step 3: Write minimal implementation**

```python
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_builder.py -v`
Expected: PASS (all 4 tests)

**Step 5: Commit**

```bash
git add src/builder.py tests/test_builder.py
git commit -m "feat: add hierarchy builder for initiative-team-epic relationships"
```

---

## Task 6: Output Generator

**Files:**
- Create: `src/output.py`
- Create: `tests/test_output.py`

**Step 1: Write the failing test**

```python
# tests/test_output.py
import json
from pathlib import Path
from datetime import datetime
from src.output import OutputGenerator, ExtractionStatus


def test_generate_output_complete_success(tmp_path):
    """Test generating output with complete successful extraction."""
    data = {
        "initiatives": [
            {
                "key": "INIT-1",
                "summary": "Test",
                "contributing_teams": [],
            }
        ],
        "orphaned_epics": [],
        "summary": {
            "total_initiatives": 1,
            "total_epics": 0,
            "teams_involved": [],
        },
    }

    extraction_status = ExtractionStatus(
        complete=True,
        issues=[],
        initiatives_fetched=1,
        initiatives_failed=0,
        team_projects_fetched=3,
        team_projects_failed=0,
    )

    output_dir = tmp_path / "data"
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(output_dir),
        filename_pattern="test_{timestamp}.json",
    )

    output_path = generator.generate(data, extraction_status)

    assert output_path.exists()

    with open(output_path) as f:
        result = json.load(f)

    assert result["jira_instance"] == "test.atlassian.net"
    assert result["extraction_status"]["complete"] is True
    assert len(result["initiatives"]) == 1
    assert "extracted_at" in result


def test_generate_output_with_issues(tmp_path):
    """Test generating output with extraction issues."""
    data = {
        "initiatives": [],
        "orphaned_epics": [],
        "summary": {"total_initiatives": 0, "total_epics": 0, "teams_involved": []},
    }

    extraction_status = ExtractionStatus(
        complete=False,
        issues=[
            {
                "severity": "error",
                "message": "Failed to fetch from project RSK: 403 Forbidden",
                "impact": "Missing all epics from RSK team",
            }
        ],
        initiatives_fetched=10,
        initiatives_failed=2,
        team_projects_fetched=2,
        team_projects_failed=1,
    )

    output_dir = tmp_path / "data"
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(output_dir),
    )

    output_path = generator.generate(data, extraction_status)

    with open(output_path) as f:
        result = json.load(f)

    assert result["extraction_status"]["complete"] is False
    assert len(result["extraction_status"]["issues"]) == 1
    assert result["extraction_status"]["team_projects_failed"] == 1


def test_filename_pattern_with_timestamp(tmp_path):
    """Test filename pattern with timestamp replacement."""
    data = {
        "initiatives": [],
        "orphaned_epics": [],
        "summary": {"total_initiatives": 0, "total_epics": 0, "teams_involved": []},
    }

    extraction_status = ExtractionStatus(complete=True, issues=[])

    output_dir = tmp_path / "data"
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(output_dir),
        filename_pattern="jira_{timestamp}.json",
    )

    output_path = generator.generate(data, extraction_status)

    # Check timestamp is in filename
    assert output_path.name.startswith("jira_")
    assert output_path.name.endswith(".json")
    assert len(output_path.name) > len("jira_.json")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_output.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.output'"

**Step 3: Write minimal implementation**

```python
# src/output.py
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional


@dataclass
class ExtractionStatus:
    """Status of data extraction."""
    complete: bool
    issues: List[Dict[str, str]]
    initiatives_fetched: int = 0
    initiatives_failed: int = 0
    team_projects_fetched: int = 0
    team_projects_failed: int = 0


class OutputGenerator:
    """Generates JSON output files."""

    def __init__(
        self,
        jira_instance: str,
        output_directory: str = "./data",
        filename_pattern: str = "jira_extract_{timestamp}.json",
    ):
        """Initialize output generator.

        Args:
            jira_instance: Jira instance URL
            output_directory: Directory for output files
            filename_pattern: Filename pattern (use {timestamp} for current time)
        """
        self.jira_instance = jira_instance
        self.output_directory = Path(output_directory)
        self.filename_pattern = filename_pattern

    def generate(
        self,
        data: Dict[str, Any],
        extraction_status: ExtractionStatus,
        custom_path: Optional[Path] = None,
    ) -> Path:
        """Generate JSON output file.

        Args:
            data: Hierarchy data from builder
            extraction_status: Extraction status information
            custom_path: Optional custom output path (overrides directory/pattern)

        Returns:
            Path to generated file
        """
        # Prepare output
        output = {
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "jira_instance": self.jira_instance,
            "extraction_status": asdict(extraction_status),
            "initiatives": data["initiatives"],
            "orphaned_epics": data.get("orphaned_epics", []),
            "summary": data["summary"],
        }

        # Determine output path
        if custom_path:
            output_path = Path(custom_path)
        else:
            # Create output directory
            self.output_directory.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.filename_pattern.replace("{timestamp}", timestamp)
            output_path = self.output_directory / filename

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write JSON
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        return output_path
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_output.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add src/output.py tests/test_output.py
git commit -m "feat: add JSON output generator with completeness tracking"
```

---

## Task 7: CLI Application

**Files:**
- Create: `jira_scan.py`

**Step 1: Write the implementation**

```python
#!/usr/bin/env python3
"""Jira Dependencies Tracking CLI."""

import sys
import click
from pathlib import Path
from typing import Optional

from src.config import load_config, ConfigError
from src.jira_client import JiraClient, JiraAPIError
from src.fetcher import DataFetcher
from src.builder import build_hierarchy
from src.output import OutputGenerator, ExtractionStatus


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Jira Dependencies Tracking Tool.

    Extract initiatives and epics to analyze team contributions.
    """
    pass


@cli.command()
@click.option(
    "--config",
    default="config.yaml",
    help="Path to config file",
    type=click.Path(exists=True),
)
@click.option(
    "--output",
    default=None,
    help="Custom output file path",
    type=click.Path(),
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be fetched without writing output",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Verbose output for debugging",
)
def extract(config: str, output: Optional[str], dry_run: bool, verbose: bool):
    """Extract data from Jira."""
    try:
        # Load configuration
        if verbose:
            click.echo(f"Loading config from: {config}")

        cfg = load_config(config)

        # Initialize Jira client
        if verbose:
            click.echo(f"Connecting to: {cfg['jira']['instance']}")

        client = JiraClient(
            instance=cfg["jira"]["instance"],
            email=cfg["jira"]["email"],
            api_token=cfg["jira"]["api_token"],
        )

        # Initialize fetcher
        fetcher = DataFetcher(
            client=client,
            initiatives_project=cfg["projects"]["initiatives"],
            team_projects=cfg["projects"]["teams"],
            rag_field_id=cfg["custom_fields"]["rag_status"],
        )

        if dry_run:
            click.echo("\nDry run - showing what would be fetched:\n")
            click.echo(f"  Initiatives project: {cfg['projects']['initiatives']}")
            click.echo(f"  Team projects: {', '.join(cfg['projects']['teams'])}")
            click.echo(f"  RAG field ID: {cfg['custom_fields']['rag_status']}")
            return

        # Fetch data
        click.echo("Fetching data from Jira...")
        with click.progressbar(length=2, label="Extracting") as bar:
            initiatives_result, epics_result = fetcher.fetch_all()
            bar.update(2)

        # Build extraction status
        issues = []

        if not initiatives_result.success:
            issues.append({
                "severity": "error",
                "message": f"Failed to fetch initiatives: {initiatives_result.error_message}",
                "impact": "Missing all initiatives data",
            })

        if not epics_result.success:
            issues.append({
                "severity": "error",
                "message": f"Failed to fetch epics: {epics_result.error_message}",
                "impact": "Missing all epics data",
            })

        # Check for orphaned epics warning
        if epics_result.success:
            orphaned_count = sum(1 for e in epics_result.items if not e.get("parent_key"))
            if orphaned_count > 0:
                issues.append({
                    "severity": "warning",
                    "message": f"{orphaned_count} epics found without parent initiative",
                    "impact": f"{orphaned_count} epics listed in orphaned_epics section",
                })

        extraction_status = ExtractionStatus(
            complete=initiatives_result.success and epics_result.success and len(issues) == 0,
            issues=issues,
            initiatives_fetched=len(initiatives_result.items) if initiatives_result.success else 0,
            initiatives_failed=0 if initiatives_result.success else 1,
            team_projects_fetched=len(cfg["projects"]["teams"]) if epics_result.success else 0,
            team_projects_failed=0 if epics_result.success else len(cfg["projects"]["teams"]),
        )

        # Build hierarchy
        if verbose:
            click.echo("Building relationships...")

        hierarchy_data = build_hierarchy(
            initiatives=initiatives_result.items if initiatives_result.success else [],
            epics=epics_result.items if epics_result.success else [],
        )

        # Generate output
        generator = OutputGenerator(
            jira_instance=cfg["jira"]["instance"],
            output_directory=cfg["output"]["directory"],
            filename_pattern=cfg["output"]["filename_pattern"],
        )

        output_path = generator.generate(
            data=hierarchy_data,
            extraction_status=extraction_status,
            custom_path=Path(output) if output else None,
        )

        # Print summary
        click.echo(f"\n✓ Data extracted to: {output_path}")
        click.echo(f"\nSummary:")
        click.echo(f"  Initiatives: {hierarchy_data['summary']['total_initiatives']}")
        click.echo(f"  Epics: {hierarchy_data['summary']['total_epics']}")
        click.echo(f"  Teams: {len(hierarchy_data['summary']['teams_involved'])}")

        if not extraction_status.complete:
            click.echo(click.style("\n⚠ Warning: Extraction incomplete", fg="yellow", bold=True))
            for issue in extraction_status.issues:
                severity_color = "red" if issue["severity"] == "error" else "yellow"
                click.echo(click.style(f"  [{issue['severity'].upper()}] {issue['message']}", fg=severity_color))
            sys.exit(1)

    except ConfigError as e:
        click.echo(click.style(f"Configuration error: {e}", fg="red"), err=True)
        sys.exit(2)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(2)


@cli.command()
@click.option(
    "--config",
    default="config.yaml",
    help="Path to config file",
    type=click.Path(exists=True),
)
def list_fields(config: str):
    """List all custom fields in Jira."""
    try:
        cfg = load_config(config)

        client = JiraClient(
            instance=cfg["jira"]["instance"],
            email=cfg["jira"]["email"],
            api_token=cfg["jira"]["api_token"],
        )

        click.echo("Fetching custom fields...")
        fields = client.get_custom_fields()

        click.echo(f"\nFound {len(fields)} custom fields:\n")

        for field in sorted(fields, key=lambda f: f["name"]):
            click.echo(f"  {field['id']:<25} {field['name']}")

        click.echo("\nUpdate config.yaml with the field ID for RAG status.")

    except ConfigError as e:
        click.echo(click.style(f"Configuration error: {e}", fg="red"), err=True)
        sys.exit(2)
    except JiraAPIError as e:
        click.echo(click.style(f"Jira API error: {e}", fg="red"), err=True)
        sys.exit(2)


@cli.command()
@click.option(
    "--config",
    default="config.yaml",
    help="Path to config file",
    type=click.Path(exists=True),
)
def validate_config(config: str):
    """Validate configuration file."""
    try:
        click.echo(f"Validating config: {config}")

        cfg = load_config(config)

        click.echo("\n✓ Configuration valid:\n")
        click.echo(f"  Jira instance: {cfg['jira']['instance']}")
        click.echo(f"  Initiatives project: {cfg['projects']['initiatives']}")
        click.echo(f"  Team projects: {', '.join(cfg['projects']['teams'])}")
        click.echo(f"  RAG field: {cfg['custom_fields']['rag_status']}")
        click.echo(f"  Output directory: {cfg['output']['directory']}")

        # Test connection
        click.echo("\nTesting Jira connection...")
        client = JiraClient(
            instance=cfg["jira"]["instance"],
            email=cfg["jira"]["email"],
            api_token=cfg["jira"]["api_token"],
        )

        # Simple test query
        client.search_issues("project = XYZ", fields=["key"], max_results=1)

        click.echo("✓ Connection successful")

    except ConfigError as e:
        click.echo(click.style(f"\n✗ Configuration error: {e}", fg="red"), err=True)
        sys.exit(2)
    except JiraAPIError as e:
        click.echo(click.style(f"\n✗ Jira connection error: {e}", fg="red"), err=True)
        click.echo("\nCheck your credentials and network connection.")
        sys.exit(2)


if __name__ == "__main__":
    cli()
```

**Step 2: Make executable**

Run: `chmod +x jira_scan.py`

**Step 3: Test help command**

Run: `python jira_scan.py --help`
Expected: Shows help text with all commands

**Step 4: Test version command**

Run: `python jira_scan.py --version`
Expected: Shows version "0.1.0"

**Step 5: Commit**

```bash
git add jira_scan.py
git commit -m "feat: add CLI application with extract, list-fields, and validate commands"
```

---

## Task 8: Integration Testing Setup

**Files:**
- Create: `tests/__init__.py`
- Create: `pytest.ini`

**Step 1: Create pytest.ini**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

**Step 2: Create tests/__init__.py**

```python
"""Tests for jira-dependencies-tracking."""
```

**Step 3: Run all tests**

Run: `pytest`
Expected: All tests pass

**Step 4: Commit**

```bash
git add pytest.ini tests/__init__.py
git commit -m "test: add pytest configuration"
```

---

## Task 9: Final Polish and Documentation

**Files:**
- Modify: `README.md`
- Create: `data/.gitkeep`

**Step 1: Create data directory placeholder**

Run: `mkdir -p data && touch data/.gitkeep`

**Step 2: Update README with complete instructions**

```bash
# Already created in Task 1 - verify it's complete
cat README.md
```

**Step 3: Run final test suite**

Run: `pytest -v`
Expected: All tests pass

**Step 4: Test end-to-end with dry-run**

Run: `python jira_scan.py extract --dry-run`
Expected: Shows what would be fetched (requires .env and config.yaml)

**Step 5: Commit**

```bash
git add data/.gitkeep
git commit -m "chore: add data directory placeholder"
```

---

## Task 10: Final Verification

**Step 1: Run all tests**

Run: `pytest -v`
Expected: All tests pass

**Step 2: Verify file structure**

Run: `tree -L 2 -I '__pycache__|*.pyc|.pytest_cache'`
Expected: Complete project structure

**Step 3: Check git status**

Run: `git status`
Expected: Clean working tree

**Step 4: Review all commits**

Run: `git log --oneline`
Expected: Clear commit history following conventional commits

**Step 5: Verify README instructions**

Manually review README.md to ensure all setup steps are clear and complete.

---

## Success Criteria

- [ ] All unit tests pass
- [ ] Configuration loads from YAML and .env
- [ ] Jira client fetches initiatives and epics with pagination
- [ ] Parallel fetching works correctly
- [ ] Hierarchy builder matches epics to initiatives
- [ ] Orphaned epics are tracked separately
- [ ] JSON output includes completeness tracking
- [ ] CLI commands work: extract, list-fields, validate-config
- [ ] Exit codes: 0 (success), 1 (partial), 2 (failure)
- [ ] README has complete setup instructions
- [ ] Example config files exist
- [ ] .gitignore protects credentials

## Next Steps After Implementation

1. Test with real Jira instance:
   - Copy config.yaml.example to config.yaml
   - Copy .env.example to .env
   - Add real credentials
   - Run `python jira_scan.py validate-config`
   - Run `python jira_scan.py list-fields` to find RAG field
   - Run `python jira_scan.py extract`

2. Verify output JSON structure matches requirements

3. Use output for analysis and diagram generation
