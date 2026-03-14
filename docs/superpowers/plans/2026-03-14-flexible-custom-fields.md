# Flexible Custom Fields Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable adding custom fields to initiative extraction via config only, without code changes

**Architecture:** Replace hardcoded `CustomFields` dataclass with simple dictionary mapping output names to Jira field IDs. All custom fields are optional and treated uniformly.

**Tech Stack:** Python 3.9+, pytest, YAML config, dataclasses

---

## Chunk 1: Configuration Layer

### Task 1: Remove CustomFields dataclass and update Config

**Files:**
- Modify: `src/config.py:15-26` (CustomFields dataclass)
- Modify: `src/config.py:51-57` (Config dataclass)
- Modify: `src/config.py:73-148` (load_config function)

- [ ] **Step 1: Write test for loading config with custom_fields.initiatives dict**

```python
# In tests/test_config.py (add after test_load_config_without_filters)

def test_load_config_with_custom_fields_dict(tmp_path):
    """Test loading config with custom_fields.initiatives as dict."""
    config_content = """
jira:
  instance: "test.atlassian.net"

projects:
  initiatives: "INIT"
  teams:
    - "TEAM1"

custom_fields:
  initiatives:
    rag_status: "customfield_12111"
    quarter: "customfield_12108"
    objective: "customfield_12101"

output:
  directory: "./data"
  filename_pattern: "test_{timestamp}.json"
"""

    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)

    config = load_config(str(config_file))

    assert isinstance(config.custom_fields, dict)
    assert config.custom_fields["rag_status"] == "customfield_12111"
    assert config.custom_fields["quarter"] == "customfield_12108"
    assert config.custom_fields["objective"] == "customfield_12101"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_load_config_with_custom_fields_dict -v`

Expected: FAIL with "custom_fields.initiatives not found" or similar

- [ ] **Step 3: Write test for empty custom_fields section**

```python
# In tests/test_config.py (add after previous test)

def test_load_config_empty_custom_fields(tmp_path):
    """Test loading config with empty custom_fields.initiatives section."""
    config_content = """
jira:
  instance: "test.atlassian.net"

projects:
  initiatives: "INIT"
  teams:
    - "TEAM1"

custom_fields:
  initiatives: {}

output:
  directory: "./data"
  filename_pattern: "test_{timestamp}.json"
"""

    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)

    config = load_config(str(config_file))

    assert isinstance(config.custom_fields, dict)
    assert len(config.custom_fields) == 0
```

- [ ] **Step 4: Write test for missing custom_fields section**

```python
# In tests/test_config.py (add after previous test)

def test_load_config_missing_custom_fields(tmp_path):
    """Test loading config with missing custom_fields section defaults to empty dict."""
    config_content = """
jira:
  instance: "test.atlassian.net"

projects:
  initiatives: "INIT"
  teams:
    - "TEAM1"

output:
  directory: "./data"
  filename_pattern: "test_{timestamp}.json"
"""

    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)

    config = load_config(str(config_file))

    assert isinstance(config.custom_fields, dict)
    assert len(config.custom_fields) == 0
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `pytest tests/test_config.py::test_load_config_empty_custom_fields tests/test_config.py::test_load_config_missing_custom_fields -v`

Expected: FAIL

- [ ] **Step 6: Remove CustomFields dataclass**

```python
# In src/config.py, DELETE lines 22-26:
# @dataclass
# class CustomFields:
#     """Custom field IDs."""
#     rag_status: str
#     quarter: Optional[str] = None
```

- [ ] **Step 7: Update Config dataclass to use Dict**

```python
# In src/config.py, update Config dataclass (around line 51):
@dataclass
class Config:
    """Main configuration."""
    jira: JiraConfig
    projects: ProjectsConfig
    custom_fields: Dict[str, str]  # Changed from CustomFields
    output: OutputConfig
    filters: Optional[Filters] = None

    def validate(self) -> None:
        """Validate configuration.

        Raises:
            ConfigError: If configuration is invalid
        """
        # Check if filters.quarter is set but quarter field is missing
        if self.filters and self.filters.quarter:
            if "quarter" not in self.custom_fields:  # Changed from self.custom_fields.quarter
                raise ConfigError(
                    "Quarter filtering requires custom_fields.initiatives.quarter to be defined"
                )
```

- [ ] **Step 8: Update load_config to extract custom_fields dict**

```python
# In src/config.py, update load_config function (around line 130):
        # In the try block, replace custom_fields creation:
        config = Config(
            jira=JiraConfig(
                instance=data["jira"]["instance"],
                email=email,
                api_token=api_token,
            ),
            projects=ProjectsConfig(
                initiatives=data["projects"]["initiatives"],
                teams=data["projects"]["teams"],
            ),
            custom_fields=data.get("custom_fields", {}).get("initiatives", {}),  # Changed
            output=OutputConfig(
                directory=data["output"]["directory"],
                filename_pattern=data["output"]["filename_pattern"],
            ),
            filters=filters,
        )
```

- [ ] **Step 9: Run new tests to verify they pass**

Run: `pytest tests/test_config.py::test_load_config_with_custom_fields_dict tests/test_config.py::test_load_config_empty_custom_fields tests/test_config.py::test_load_config_missing_custom_fields -v`

Expected: PASS (3 tests)

- [ ] **Step 10: Update existing test that references CustomFields**

```python
# In tests/test_config.py, DELETE or comment out test_custom_fields_with_quarter (lines 68-82)
# And test_config_with_filters (lines 84-107)
# These tests reference the removed CustomFields dataclass

# UPDATE test_validate_filters_requires_quarter_field (around line 109):
def test_validate_quarter_filter_requires_quarter_field():
    """Test that filters.quarter requires custom_fields['quarter']."""
    from src.config import Config, JiraConfig, ProjectsConfig, Filters, OutputConfig, ConfigError

    # Should raise error when filters.quarter is set but custom_fields['quarter'] is not
    config = Config(
        jira=JiraConfig(instance="test.atlassian.net", email="test@example.com", api_token="test-token"),
        projects=ProjectsConfig(initiatives="INIT", teams=["TEAM1"]),
        custom_fields={"rag_status": "customfield_12111"},  # Changed: No quarter field
        output=OutputConfig(directory="./data", filename_pattern="test_{timestamp}.json"),
        filters=Filters(quarter="25 Q1")  # But filter is set
    )

    with pytest.raises(ConfigError, match="Quarter filtering requires custom_fields.initiatives.quarter"):
        config.validate()


# UPDATE test_validate_filters_with_quarter_field_ok (around line 125):
def test_validate_filters_with_quarter_field_ok():
    """Test that filters work when quarter field is defined."""
    from src.config import Config, JiraConfig, ProjectsConfig, Filters, OutputConfig

    config = Config(
        jira=JiraConfig(instance="test.atlassian.net", email="test@example.com", api_token="test-token"),
        projects=ProjectsConfig(initiatives="INIT", teams=["TEAM1"]),
        custom_fields={"rag_status": "customfield_12111", "quarter": "customfield_12108"},  # Changed
        output=OutputConfig(directory="./data", filename_pattern="test_{timestamp}.json"),
        filters=Filters(quarter="25 Q1")
    )
    config.validate()  # Should not raise


# UPDATE test_load_config_with_filters (around line 139):
def test_load_config_with_filters(tmp_path):
    """Test loading config with filters section."""
    from src.config import load_config

    config_content = """
jira:
  instance: "test.atlassian.net"

projects:
  initiatives: "INIT"
  teams:
    - "TEAM1"
    - "TEAM2"

custom_fields:
  initiatives:
    rag_status: "customfield_12111"
    quarter: "customfield_12108"

filters:
  quarter: "25 Q1"

output:
  directory: "./data"
  filename_pattern: "test_{timestamp}.json"
"""

    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)

    config = load_config(str(config_file))

    assert config.filters is not None
    assert config.filters.quarter == "25 Q1"
    assert config.custom_fields["quarter"] == "customfield_12108"  # Changed
```

- [ ] **Step 11: Run all config tests to verify they pass**

Run: `pytest tests/test_config.py -v`

Expected: All tests PASS

- [ ] **Step 12: Commit configuration layer changes**

```bash
git add src/config.py tests/test_config.py
git commit -m "refactor: replace CustomFields dataclass with dict

Replace hardcoded CustomFields dataclass with Dict[str, str] to
enable flexible custom field configuration. All custom fields are
now optional and added via config.yaml without code changes.

Breaking change: config structure updated to custom_fields.initiatives.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Chunk 2: DataFetcher Layer

### Task 2: Add field extraction helper method

**Files:**
- Modify: `src/fetcher.py:18-46` (DataFetcher.__init__)
- Create test in: `tests/test_fetcher.py`

- [ ] **Step 1: Write test for _extract_field_value with select field**

```python
# In tests/test_fetcher.py (add at end of file)

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
```

- [ ] **Step 2: Write test for _extract_field_value with text field**

```python
# In tests/test_fetcher.py (add after previous test)

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
```

- [ ] **Step 3: Write test for _extract_field_value with None**

```python
# In tests/test_fetcher.py (add after previous test)

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
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_fetcher.py::test_extract_field_value_select_field tests/test_fetcher.py::test_extract_field_value_text_field tests/test_fetcher.py::test_extract_field_value_null -v`

Expected: FAIL with "_extract_field_value not found"

- [ ] **Step 5: Update DataFetcher.__init__ to accept custom_fields dict**

```python
# In src/fetcher.py, update __init__ method (around line 21):
    def __init__(
        self,
        client: JiraClient,
        initiatives_project: str,
        team_projects: List[str],
        custom_fields: Dict[str, str],  # Changed from rag_field_id, quarter_field_id
        filter_quarter: Optional[str] = None,
    ):
        """Initialize data fetcher.

        Args:
            client: JiraClient instance
            initiatives_project: Project key for initiatives (e.g., "INIT")
            team_projects: List of team project keys
            custom_fields: Dict mapping output field names to Jira field IDs
            filter_quarter: Quarter value to filter by (e.g., "25 Q1", optional)
        """
        self.client = client
        self.initiatives_project = initiatives_project
        self.team_projects = team_projects
        self.custom_fields = custom_fields  # Changed
        self.filter_quarter = filter_quarter
```

- [ ] **Step 6: Add _extract_field_value helper method**

```python
# In src/fetcher.py, add method after __init__ (around line 46):
    def _extract_field_value(self, field_data: Any) -> Optional[str]:
        """Extract value from Jira custom field.

        Handles:
        - Select fields: {"value": "🟢"} → "🟢"
        - Text fields: "plain text" → "plain text"
        - Missing fields: None → None

        Args:
            field_data: Raw field data from Jira API

        Returns:
            Extracted string value or None
        """
        if field_data is None:
            return None
        if isinstance(field_data, dict):
            return field_data.get("value")
        return field_data  # Plain string or other simple type
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_fetcher.py::test_extract_field_value_select_field tests/test_fetcher.py::test_extract_field_value_text_field tests/test_fetcher.py::test_extract_field_value_null -v`

Expected: PASS (3 tests)

- [ ] **Step 8: Commit field extraction helper**

```bash
git add src/fetcher.py tests/test_fetcher.py
git commit -m "feat: add generic field value extraction helper

Add _extract_field_value method to handle select and text field types.
Update DataFetcher constructor to accept custom_fields dict.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

### Task 3: Update fetch_initiatives to use dynamic fields

**Files:**
- Modify: `src/fetcher.py:47-111` (fetch_initiatives method)
- Test: `tests/test_fetcher.py`

- [ ] **Step 1: Write test for fetch_initiatives with multiple custom fields**

```python
# In tests/test_fetcher.py (add after test_extract_field_value_null)

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
```

- [ ] **Step 2: Write test for fetch_initiatives with no custom fields**

```python
# In tests/test_fetcher.py (add after previous test)

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
```

- [ ] **Step 3: Write test for partially missing custom field values**

```python
# In tests/test_fetcher.py (add after previous test)

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
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_fetcher.py::test_fetch_initiatives_with_multiple_custom_fields tests/test_fetcher.py::test_fetch_initiatives_with_no_custom_fields tests/test_fetcher.py::test_fetch_initiatives_with_partially_missing_custom_field_values -v`

Expected: FAIL

- [ ] **Step 5: Update fetch_initiatives to use dynamic custom fields**

```python
# In src/fetcher.py, replace fetch_initiatives method (around line 47):
    def fetch_initiatives(self) -> FetchResult:
        """Fetch all initiatives from the initiatives project.

        Returns:
            FetchResult with initiatives data
        """
        # Build base JQL
        jql = f"project = {self.initiatives_project} AND issuetype = Initiative"

        # Add filters if configured
        if self.filter_quarter and "quarter" in self.custom_fields:
            quarter_field_id = self.custom_fields["quarter"]
            jql += f' AND status != "Done" AND {quarter_field_id} = "{self.filter_quarter}"'

        # Build fields list - dynamic from config
        # NOTE: Fetches ALL configured custom fields, even if not used for filtering
        # This simplifies the code; Jira API batches field requests efficiently
        fields = ["summary", "status"] + list(self.custom_fields.values())

        try:
            issues = self.client.search_issues(jql, fields=fields)

            # Normalize initiative data
            initiatives = []
            for issue in issues:
                fields_data = issue.get("fields", {})

                # Build base initiative data
                initiative_data = {
                    "key": issue["key"],
                    "summary": fields_data.get("summary", ""),
                    "status": fields_data.get("status", {}).get("name", "Unknown"),
                    "url": f"{self.client.base_url}/browse/{issue['key']}",
                }

                # Add all custom fields dynamically
                for output_name, field_id in self.custom_fields.items():
                    field_data = fields_data.get(field_id)
                    initiative_data[output_name] = self._extract_field_value(field_data)

                initiatives.append(initiative_data)

            return FetchResult(success=True, items=initiatives, jql=jql)

        except JiraAPIError as e:
            return FetchResult(
                success=False,
                items=[],
                error_message=str(e),
                project_key=self.initiatives_project,
                jql=jql,
            )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_fetcher.py::test_fetch_initiatives_with_multiple_custom_fields tests/test_fetcher.py::test_fetch_initiatives_with_no_custom_fields tests/test_fetcher.py::test_fetch_initiatives_with_partially_missing_custom_field_values -v`

Expected: PASS (3 tests)

- [ ] **Step 7: Update existing fetch_initiatives tests to use new signature**

```python
# In tests/test_fetcher.py, update test_fetch_initiatives_success (around line 7):
def test_fetch_initiatives_success():
    """Test successful initiative fetching."""
    mock_client = Mock()
    mock_client.base_url = "https://test.atlassian.net"  # Add this
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

    fetcher = DataFetcher(
        mock_client,
        "INIT",
        ["TEAM1"],
        custom_fields={"rag_status": "customfield_10050"}  # Changed
    )
    result = fetcher.fetch_initiatives()

    assert result.success is True
    assert len(result.items) == 1
    assert result.items[0]["key"] == "INIT-1"
    assert result.items[0]["rag_status"] == "Green"


# Update test_fetch_epics_success (around line 30):
def test_fetch_epics_success():
    """Test successful epic fetching."""
    mock_client = Mock()
    mock_client.base_url = "https://test.atlassian.net"  # Add this
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

    # Update to use custom_fields parameter
    # NOTE: fetch_epics still uses rag_field_id internally, will update later
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
```

- [ ] **Step 8: Update other DataFetcher test instantiations**

```python
# In tests/test_fetcher.py, search for all "DataFetcher(" and update:

# test_fetch_all_parallel (around line 56):
fetcher = DataFetcher(
    mock_client,
    "INIT",
    ["TEAM1"],
    custom_fields={"rag_status": "customfield_10050"}
)

# test_fetch_with_api_error (around line 77):
fetcher = DataFetcher(
    mock_client,
    "INIT",
    ["TEAM1"],
    custom_fields={"rag_status": "customfield_10050"}
)

# test_fetch_epics_with_empty_team_projects (around line 92):
fetcher = DataFetcher(
    mock_client,
    "INIT",
    [],
    custom_fields={"rag_status": "customfield_10050"}
)

# test_fetch_epics_with_multiple_teams (around line 107):
fetcher = DataFetcher(
    mock_client,
    "INIT",
    ["TEAM1", "TEAM2"],
    custom_fields={"rag_status": "customfield_10050"}
)

# test_data_fetcher_accepts_filter_params (around line 146):
# UPDATE this test completely:
def test_data_fetcher_accepts_filter_params():
    """Test DataFetcher accepts custom_fields and filter parameters."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()

    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["TEAM1"],
        custom_fields={
            "rag_status": "customfield_12111",
            "quarter": "customfield_12108"
        },
        filter_quarter="25 Q1"
    )

    assert fetcher.custom_fields["quarter"] == "customfield_12108"
    assert fetcher.filter_quarter == "25 Q1"

# test_fetch_initiatives_jql_without_filters (around line 166):
fetcher = DataFetcher(
    client=mock_client,
    initiatives_project="INIT",
    team_projects=["TEAM1"],
    custom_fields={"rag_status": "customfield_12111"}
)

# test_fetch_initiatives_jql_with_quarter_filter (around line 197):
fetcher = DataFetcher(
    client=mock_client,
    initiatives_project="INIT",
    team_projects=["TEAM1"],
    custom_fields={
        "rag_status": "customfield_12111",
        "quarter": "customfield_12108"
    },
    filter_quarter="25 Q1"
)

# test_fetch_epics_returns_jql (around line 248):
fetcher = DataFetcher(
    client=mock_client,
    initiatives_project="INIT",
    team_projects=["RSK", "CBNK"],
    custom_fields={"rag_status": "customfield_12111"}
)

# test_fetch_epics_empty_teams_returns_none_jql (around line 272):
fetcher = DataFetcher(
    client=mock_client,
    initiatives_project="INIT",
    team_projects=[],
    custom_fields={"rag_status": "customfield_12111"}
)
```

- [ ] **Step 9: Update fetch_epics to extract rag_status from custom_fields**

```python
# In src/fetcher.py, update fetch_epics method (around line 112):
    def fetch_epics(self) -> FetchResult:
        """Fetch all epics from team projects.

        Returns:
            FetchResult with epics data
        """
        # Handle empty team projects list
        if not self.team_projects:
            return FetchResult(success=True, items=[], jql=None)

        # Build JQL for all team projects
        project_filter = " OR ".join([f"project = {p}" for p in self.team_projects])
        jql = f"({project_filter}) AND issuetype = Epic"

        # Get rag_field_id from custom_fields if present
        rag_field_id = self.custom_fields.get("rag_status")
        fields = ["summary", "status", "parent", "project"]
        if rag_field_id:
            fields.append(rag_field_id)

        try:
            issues = self.client.search_issues(jql, fields=fields)

            # Normalize epic data
            epics = []
            for issue in issues:
                fields_data = issue.get("fields", {})

                # Extract parent initiative key
                parent = fields_data.get("parent", {})
                parent_key = parent.get("key") if parent else None

                # Extract RAG status if field is configured
                rag_status = None
                if rag_field_id:
                    rag_field = fields_data.get(rag_field_id, {})
                    rag_status = self._extract_field_value(rag_field)

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

            return FetchResult(success=True, items=epics, jql=jql)

        except JiraAPIError as e:
            return FetchResult(
                success=False,
                items=[],
                error_message=str(e),
                jql=jql,
            )
```

- [ ] **Step 10: Run all fetcher tests to verify they pass**

Run: `pytest tests/test_fetcher.py -v`

Expected: All tests PASS

- [ ] **Step 11: Commit DataFetcher changes**

```bash
git add src/fetcher.py tests/test_fetcher.py
git commit -m "feat: implement dynamic custom field extraction

Update fetch_initiatives to dynamically extract all configured custom
fields. Fields are added to Jira API request and extracted using
generic helper method. Supports zero, one, or many custom fields.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Chunk 3: Builder and CLI Integration

### Task 4: Update builder to pass through custom fields

**Files:**
- Modify: `src/builder.py:40-81`
- Test: `tests/test_builder.py`

- [ ] **Step 1: Write test for build_hierarchy with custom fields**

```python
# In tests/test_builder.py (add at end of file)

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
```

- [ ] **Step 2: Write test for build_hierarchy with no custom fields**

```python
# In tests/test_builder.py (add after previous test)

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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_builder.py::test_build_hierarchy_with_custom_fields tests/test_builder.py::test_build_hierarchy_with_no_custom_fields -v`

Expected: FAIL (custom fields not present in output)

- [ ] **Step 4: Update build_hierarchy to pass through custom fields**

```python
# In src/builder.py, update the section that builds result_initiatives (around line 73):
        # Build base initiative with known fields
        initiative_output = {
            "key": initiative["key"],
            "summary": initiative["summary"],
            "status": initiative["status"],
            "url": initiative["url"],
        }

        # Add all custom fields dynamically
        # Pass through any field that isn't a known base field or contributing_teams
        for field_name, field_value in initiative.items():
            if field_name not in ["key", "summary", "status", "url", "contributing_teams"]:
                initiative_output[field_name] = field_value

        # Add contributing teams last
        initiative_output["contributing_teams"] = contributing_teams

        result_initiatives.append(initiative_output)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_builder.py::test_build_hierarchy_with_custom_fields tests/test_builder.py::test_build_hierarchy_with_no_custom_fields -v`

Expected: PASS (2 tests)

- [ ] **Step 6: Run all builder tests to ensure nothing broke**

Run: `pytest tests/test_builder.py -v`

Expected: All tests PASS

- [ ] **Step 7: Commit builder changes**

```bash
git add src/builder.py tests/test_builder.py
git commit -m "feat: pass through custom fields in builder

Update build_hierarchy to dynamically pass through all custom fields
from initiative data. No hardcoding of field names required.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

### Task 5: Update CLI to use new config structure

**Files:**
- Modify: `jira_extract.py:62-76` (extract command)
- Modify: `jira_extract.py:196-223` (validate_config command)

- [ ] **Step 1: Update extract command DataFetcher instantiation**

```python
# In jira_extract.py, update extract command (around line 69):
        # Initialize fetcher
        fetcher = DataFetcher(
            client=client,
            initiatives_project=cfg.projects.initiatives,
            team_projects=cfg.projects.teams,
            custom_fields=cfg.custom_fields,  # Changed: pass whole dict
            filter_quarter=cfg.filters.quarter if cfg.filters else None,
        )
```

- [ ] **Step 2: Update validate_config to validate custom field IDs**

```python
# In jira_extract.py, update validate_config command (around line 240):
        # Add after "Connection successful" message:

        # Validate custom fields exist in Jira
        if cfg.custom_fields:
            click.echo("\nValidating custom fields...")
            all_fields = client.get_custom_fields()
            field_ids = {f["id"] for f in all_fields}

            for field_name, field_id in cfg.custom_fields.items():
                if field_id not in field_ids:
                    raise ConfigError(
                        f"Custom field '{field_name}' (ID: {field_id}) not found in Jira"
                    )
                click.echo(f"  ✓ {field_name}: {field_id}")

            click.echo("✓ All custom fields valid")
```

- [ ] **Step 3: Test CLI manually with updated config**

Run: Update config.yaml to use new structure and test:

```bash
# First update config.yaml to new structure
# Then run:
python jira_extract.py validate-config
```

Expected: Validation passes with custom field validation output

- [ ] **Step 4: Test extraction with new config**

Run: `python jira_extract.py extract --dry-run`

Expected: Dry run completes without errors

- [ ] **Step 5: Commit CLI changes**

```bash
git add jira_extract.py
git commit -m "feat: wire up flexible custom fields in CLI

Update extract command to pass custom_fields dict to DataFetcher.
Add custom field validation to validate-config command.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Chunk 4: Testing and Documentation

### Task 6: Add integration tests

**Files:**
- Create: `tests/test_integration.py` (if doesn't exist) or modify existing

- [ ] **Step 1: Write end-to-end test with custom fields**

```python
# In tests/test_integration.py (create if needed, or add to existing)

import pytest
from unittest.mock import Mock, patch
from src.config import Config, JiraConfig, ProjectsConfig, OutputConfig
from src.fetcher import DataFetcher
from src.builder import build_hierarchy


def test_end_to_end_with_custom_fields():
    """Test full extraction flow with multiple custom fields."""
    mock_client = Mock()
    mock_client.base_url = "https://test.atlassian.net"

    # Mock initiatives response
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

    # Create fetcher with custom fields
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

    # Fetch initiatives
    initiatives_result, _ = fetcher.fetch_all()

    # Build hierarchy
    hierarchy = build_hierarchy(initiatives_result.items, [])

    # Verify structure
    assert len(hierarchy["initiatives"]) == 1
    initiative = hierarchy["initiatives"][0]

    # Base fields
    assert initiative["key"] == "INIT-1"
    assert initiative["summary"] == "Test Initiative"
    assert initiative["status"] == "In Progress"

    # Custom fields
    assert initiative["rag_status"] == "🟢"
    assert initiative["objective"] == "Reduce technical debt"
    assert initiative["quarter"] == "26 Q2"
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/test_integration.py::test_end_to_end_with_custom_fields -v`

Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v`

Expected: All tests PASS

- [ ] **Step 4: Commit integration test**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end test for flexible custom fields

Add integration test verifying full extraction flow with multiple
custom fields configured.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

### Task 7: Update config example and documentation

**Files:**
- Modify: `config.yaml` (user's config - migration)
- Modify: `README.md` (update examples)

- [ ] **Step 1: Update user's config.yaml to new structure**

```yaml
# In config.yaml, update custom_fields section:
custom_fields:
  initiatives:
    rag_status: "customfield_12111"
    strategic_objective: "customfield_12101"
    quarter: "customfield_12108"
    objective: "customfield_12101"
```

- [ ] **Step 2: Test with updated config**

Run: `python jira_extract.py validate-config`

Expected: Validation passes

Run: `python jira_extract.py extract --dry-run`

Expected: Dry run shows correct configuration

- [ ] **Step 3: Update README.md with new config structure**

```markdown
# In README.md, update the custom_fields section (around line 65):

### Optional: Filter by Quarter

To extract only initiatives for a specific quarter:

1. Add the quarter custom field ID to your config:
   ```yaml
   custom_fields:
     initiatives:
       rag_status: "customfield_12111"
       quarter: "customfield_12108"  # Add this
   ```

2. Add the filters section:
   ```yaml
   filters:
     quarter: "25 Q1"  # Format: "YY QN"
   ```

### Adding Custom Fields

To add additional custom fields to the output:

1. Find the field ID: `python jira_extract.py list-fields`

2. Add to your config under `custom_fields.initiatives`:
   ```yaml
   custom_fields:
     initiatives:
       rag_status: "customfield_12111"
       quarter: "customfield_12108"
       objective: "customfield_12101"      # Add any field
       strategic_priority: "customfield_12999"  # Multiple fields supported
   ```

3. Validate: `python jira_extract.py validate-config`

4. Extract: `python jira_extract.py extract`

Custom field values will appear in the output JSON using the key names from your config.
```

- [ ] **Step 4: Commit documentation and config updates**

```bash
git add config.yaml README.md
git commit -m "docs: update config and README for flexible custom fields

Update config.yaml to new custom_fields.initiatives structure.
Add documentation for adding custom fields without code changes.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

### Task 8: Final verification

**Files:**
- All modified files

- [ ] **Step 1: Run complete test suite**

Run: `pytest tests/ -v --tb=short`

Expected: All tests PASS

- [ ] **Step 2: Test actual extraction with real config**

Run: `python jira_extract.py extract`

Expected: Extraction completes successfully, output JSON contains custom fields

- [ ] **Step 3: Verify output JSON structure**

Run: `jq '.initiatives[0]' data/jira_extract_*.json`

Expected: Initiative object contains all configured custom fields

- [ ] **Step 4: Run validate-config**

Run: `python jira_extract.py validate-config`

Expected: All validation passes, custom fields validated

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "chore: final verification of flexible custom fields

All tests passing. Custom fields working end-to-end.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Summary

**Implementation complete when:**
- [ ] All tests pass (`pytest tests/ -v`)
- [ ] Config uses `custom_fields.initiatives` structure
- [ ] `validate-config` validates custom field IDs
- [ ] Extraction produces JSON with configured custom fields
- [ ] README documents how to add custom fields
- [ ] No hardcoded field names in code (except base fields: key, summary, status, url)

**Files modified:**
- `src/config.py` - Remove CustomFields dataclass, use Dict
- `src/fetcher.py` - Dynamic field extraction
- `src/builder.py` - Pass through custom fields
- `jira_extract.py` - Update CLI integration
- `tests/test_config.py` - Test new config loading
- `tests/test_fetcher.py` - Test field extraction
- `tests/test_builder.py` - Test field pass-through
- `tests/test_integration.py` - End-to-end test
- `config.yaml` - Migrate to new structure
- `README.md` - Document new feature

**Breaking changes:**
- Config structure: `custom_fields` → `custom_fields.initiatives`
- Users must update config.yaml after upgrading
