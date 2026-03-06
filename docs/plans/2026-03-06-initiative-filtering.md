# Initiative Filtering Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add optional quarter and status filtering to initiative extraction while maintaining backward compatibility.

**Architecture:** Extend config schema with optional filters section, modify DataFetcher to conditionally build JQL with filters at API level, add validation to ensure quarter field ID exists when filtering is configured.

**Tech Stack:** Python 3.9+, dataclasses, pytest, PyYAML

---

## Task 1: Add Filters Configuration Schema

**Files:**
- Modify: `src/config.py`
- Test: `tests/test_config.py`

**Step 1: Write failing test for Filters dataclass**

Add to `tests/test_config.py`:

```python
def test_filters_dataclass():
    """Test Filters dataclass."""
    from src.config import Filters

    filters = Filters(quarter="25 Q1")
    assert filters.quarter == "25 Q1"

    # Test optional
    filters_empty = Filters(quarter=None)
    assert filters_empty.quarter is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_filters_dataclass -v`
Expected: FAIL with "cannot import name 'Filters'"

**Step 3: Add Filters dataclass**

In `src/config.py`, add after CustomFields dataclass:

```python
@dataclass
class Filters:
    """Filtering configuration."""
    quarter: Optional[str] = None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_filters_dataclass -v`
Expected: PASS

**Step 5: Write failing test for quarter field in CustomFields**

Add to `tests/test_config.py`:

```python
def test_custom_fields_with_quarter():
    """Test CustomFields with quarter field."""
    from src.config import CustomFields

    fields = CustomFields(
        rag_status="customfield_12111",
        quarter="customfield_12108"
    )
    assert fields.rag_status == "customfield_12111"
    assert fields.quarter == "customfield_12108"

    # Test optional
    fields_no_quarter = CustomFields(rag_status="customfield_12111")
    assert fields_no_quarter.quarter is None
```

**Step 6: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_custom_fields_with_quarter -v`
Expected: FAIL with "unexpected keyword argument 'quarter'"

**Step 7: Add quarter field to CustomFields**

In `src/config.py`, modify CustomFields dataclass:

```python
@dataclass
class CustomFields:
    """Custom field IDs."""
    rag_status: str
    quarter: Optional[str] = None
```

**Step 8: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_custom_fields_with_quarter -v`
Expected: PASS

**Step 9: Write failing test for filters in Config**

Add to `tests/test_config.py`:

```python
def test_config_with_filters():
    """Test Config with filters section."""
    from src.config import Config, JiraConfig, ProjectsConfig, CustomFields, Filters, OutputConfig

    config = Config(
        jira=JiraConfig(instance="test.atlassian.net"),
        projects=ProjectsConfig(initiatives="INIT", teams=["TEAM1"]),
        custom_fields=CustomFields(rag_status="customfield_12111", quarter="customfield_12108"),
        output=OutputConfig(directory="./data", filename_pattern="test_{timestamp}.json"),
        filters=Filters(quarter="25 Q1")
    )

    assert config.filters is not None
    assert config.filters.quarter == "25 Q1"

    # Test optional
    config_no_filters = Config(
        jira=JiraConfig(instance="test.atlassian.net"),
        projects=ProjectsConfig(initiatives="INIT", teams=["TEAM1"]),
        custom_fields=CustomFields(rag_status="customfield_12111"),
        output=OutputConfig(directory="./data", filename_pattern="test_{timestamp}.json")
    )
    assert config_no_filters.filters is None
```

**Step 10: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_config_with_filters -v`
Expected: FAIL with "unexpected keyword argument 'filters'"

**Step 11: Add filters field to Config**

In `src/config.py`, modify Config dataclass:

```python
@dataclass
class Config:
    """Main configuration."""
    jira: JiraConfig
    projects: ProjectsConfig
    custom_fields: CustomFields
    output: OutputConfig
    filters: Optional[Filters] = None
```

**Step 12: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_config_with_filters -v`
Expected: PASS

**Step 13: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add filters configuration schema"
```

---

## Task 2: Add Config Validation for Filters

**Files:**
- Modify: `src/config.py`
- Test: `tests/test_config.py`

**Step 1: Write failing test for validation**

Add to `tests/test_config.py`:

```python
def test_validate_filters_requires_quarter_field():
    """Test that filters.quarter requires custom_fields.quarter."""
    from src.config import Config, JiraConfig, ProjectsConfig, CustomFields, Filters, OutputConfig, ConfigError

    # Should raise error when filters.quarter is set but custom_fields.quarter is not
    with pytest.raises(ConfigError, match="Quarter filtering requires custom_fields.quarter"):
        config = Config(
            jira=JiraConfig(instance="test.atlassian.net"),
            projects=ProjectsConfig(initiatives="INIT", teams=["TEAM1"]),
            custom_fields=CustomFields(rag_status="customfield_12111"),  # No quarter field
            output=OutputConfig(directory="./data", filename_pattern="test_{timestamp}.json"),
            filters=Filters(quarter="25 Q1")  # But filter is set
        )
        config.validate()


def test_validate_filters_with_quarter_field_ok():
    """Test that filters work when quarter field is defined."""
    from src.config import Config, JiraConfig, ProjectsConfig, CustomFields, Filters, OutputConfig

    config = Config(
        jira=JiraConfig(instance="test.atlassian.net"),
        projects=ProjectsConfig(initiatives="INIT", teams=["TEAM1"]),
        custom_fields=CustomFields(rag_status="customfield_12111", quarter="customfield_12108"),
        output=OutputConfig(directory="./data", filename_pattern="test_{timestamp}.json"),
        filters=Filters(quarter="25 Q1")
    )
    config.validate()  # Should not raise
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_validate_filters_requires_quarter_field -v`
Expected: FAIL with "AttributeError: 'Config' object has no attribute 'validate'"

**Step 3: Add validate method to Config**

In `src/config.py`, add method to Config class:

```python
@dataclass
class Config:
    """Main configuration."""
    jira: JiraConfig
    projects: ProjectsConfig
    custom_fields: CustomFields
    output: OutputConfig
    filters: Optional[Filters] = None

    def validate(self) -> None:
        """Validate configuration.

        Raises:
            ConfigError: If configuration is invalid
        """
        # Check if filters.quarter is set but custom_fields.quarter is missing
        if self.filters and self.filters.quarter:
            if not self.custom_fields.quarter:
                raise ConfigError(
                    "Quarter filtering requires custom_fields.quarter to be defined"
                )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py::test_validate_filters_requires_quarter_field tests/test_config.py::test_validate_filters_with_quarter_field_ok -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add validation for filter configuration"
```

---

## Task 3: Update Config Loading to Parse Filters

**Files:**
- Modify: `src/config.py`
- Test: `tests/test_config.py`

**Step 1: Write failing test for loading config with filters**

Add to `tests/test_config.py`:

```python
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
    assert config.custom_fields.quarter == "customfield_12108"


def test_load_config_without_filters(tmp_path):
    """Test loading config without filters section (backward compatibility)."""
    from src.config import load_config

    config_content = """
jira:
  instance: "test.atlassian.net"

projects:
  initiatives: "INIT"
  teams:
    - "TEAM1"

custom_fields:
  rag_status: "customfield_12111"

output:
  directory: "./data"
  filename_pattern: "test_{timestamp}.json"
"""

    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)

    config = load_config(str(config_file))

    assert config.filters is None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py::test_load_config_with_filters tests/test_config.py::test_load_config_without_filters -v`
Expected: FAIL (filters not being loaded)

**Step 3: Update load_config to parse filters**

In `src/config.py`, modify `load_config` function to parse filters:

```python
def load_config(config_path: str) -> Config:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file

    Returns:
        Config object

    Raises:
        ConfigError: If config is invalid
    """
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {config_path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML: {e}")

    try:
        # Parse filters section (optional)
        filters = None
        if "filters" in data:
            filters = Filters(
                quarter=data["filters"].get("quarter")
            )

        config = Config(
            jira=JiraConfig(
                instance=data["jira"]["instance"],
            ),
            projects=ProjectsConfig(
                initiatives=data["projects"]["initiatives"],
                teams=data["projects"]["teams"],
            ),
            custom_fields=CustomFields(
                rag_status=data["custom_fields"]["rag_status"],
                quarter=data["custom_fields"].get("quarter"),  # Optional
            ),
            output=OutputConfig(
                directory=data["output"]["directory"],
                filename_pattern=data["output"]["filename_pattern"],
            ),
            filters=filters,
        )

        # Validate configuration
        config.validate()

        return config

    except KeyError as e:
        raise ConfigError(f"Missing required config key: {e}")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py::test_load_config_with_filters tests/test_config.py::test_load_config_without_filters -v`
Expected: PASS

**Step 5: Run all config tests**

Run: `pytest tests/test_config.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: load filters from config file"
```

---

## Task 4: Modify DataFetcher to Accept Filter Parameters

**Files:**
- Modify: `src/fetcher.py`
- Test: `tests/test_fetcher.py`

**Step 1: Write failing test for new parameters**

Add to `tests/test_fetcher.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_fetcher.py::test_data_fetcher_accepts_filter_params -v`
Expected: FAIL with "unexpected keyword argument"

**Step 3: Add parameters to DataFetcher.__init__**

In `src/fetcher.py`, modify DataFetcher class:

```python
class DataFetcher:
    """Fetches initiatives and epics from Jira."""

    def __init__(
        self,
        client: JiraClient,
        initiatives_project: str,
        team_projects: List[str],
        rag_field_id: str,
        quarter_field_id: Optional[str] = None,
        filter_quarter: Optional[str] = None,
    ):
        """Initialize data fetcher.

        Args:
            client: JiraClient instance
            initiatives_project: Project key for initiatives (e.g., "INIT")
            team_projects: List of team project keys
            rag_field_id: Custom field ID for RAG status
            quarter_field_id: Custom field ID for quarter (optional)
            filter_quarter: Quarter value to filter by (e.g., "25 Q1", optional)
        """
        self.client = client
        self.initiatives_project = initiatives_project
        self.team_projects = team_projects
        self.rag_field_id = rag_field_id
        self.quarter_field_id = quarter_field_id
        self.filter_quarter = filter_quarter
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_fetcher.py::test_data_fetcher_accepts_filter_params -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/fetcher.py tests/test_fetcher.py
git commit -m "feat: add filter parameters to DataFetcher"
```

---

## Task 5: Implement JQL Filtering in fetch_initiatives

**Files:**
- Modify: `src/fetcher.py`
- Test: `tests/test_fetcher.py`

**Step 1: Write failing test for JQL without filters**

Add to `tests/test_fetcher.py`:

```python
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

    fetcher.fetch_initiatives()

    # Check JQL does not include filters
    call_args = mock_client.search_issues.call_args
    jql = call_args[0][0]

    assert "project = INIT" in jql
    assert "issuetype = Initiative" in jql
    assert "status !=" not in jql
    assert "customfield_12108" not in jql
```

**Step 2: Run test to verify it passes (no code change needed)**

Run: `pytest tests/test_fetcher.py::test_fetch_initiatives_jql_without_filters -v`
Expected: PASS (current implementation already does this)

**Step 3: Write failing test for JQL with filters**

Add to `tests/test_fetcher.py`:

```python
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

    fetcher.fetch_initiatives()

    # Check JQL includes filters
    call_args = mock_client.search_issues.call_args
    jql = call_args[0][0]

    assert "project = INIT" in jql
    assert "issuetype = Initiative" in jql
    assert 'status != "Done"' in jql
    assert 'customfield_12108 = "25 Q1"' in jql
```

**Step 4: Run test to verify it fails**

Run: `pytest tests/test_fetcher.py::test_fetch_initiatives_jql_with_quarter_filter -v`
Expected: FAIL (filters not in JQL)

**Step 5: Implement JQL filtering**

In `src/fetcher.py`, modify `fetch_initiatives` method:

```python
def fetch_initiatives(self) -> FetchResult:
    """Fetch all initiatives from the initiatives project.

    Returns:
        FetchResult with initiatives data
    """
    # Build base JQL
    jql = f"project = {self.initiatives_project} AND issuetype = Initiative"

    # Add filters if configured
    if self.filter_quarter:
        jql += f' AND status != "Done" AND {self.quarter_field_id} = "{self.filter_quarter}"'

    # Build fields list
    fields = ["summary", "status", self.rag_field_id]
    if self.quarter_field_id and self.filter_quarter:
        fields.append(self.quarter_field_id)

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

            initiative_data = {
                "key": issue["key"],
                "summary": fields_data.get("summary", ""),
                "status": fields_data.get("status", {}).get("name", "Unknown"),
                "rag_status": rag_status,
                "url": f"{self.client.base_url}/browse/{issue['key']}",
            }

            # Add quarter if present
            if self.quarter_field_id and self.filter_quarter:
                quarter_field = fields_data.get(self.quarter_field_id, {})
                quarter_value = None
                if isinstance(quarter_field, dict):
                    quarter_value = quarter_field.get("value")
                elif isinstance(quarter_field, str):
                    quarter_value = quarter_field
                initiative_data["quarter"] = quarter_value

            initiatives.append(initiative_data)

        return FetchResult(success=True, items=initiatives)

    except JiraAPIError as e:
        return FetchResult(
            success=False,
            items=[],
            error_message=str(e),
            project_key=self.initiatives_project,
        )
```

**Step 6: Run test to verify it passes**

Run: `pytest tests/test_fetcher.py::test_fetch_initiatives_jql_with_quarter_filter -v`
Expected: PASS

**Step 7: Run all fetcher tests**

Run: `pytest tests/test_fetcher.py -v`
Expected: All PASS

**Step 8: Commit**

```bash
git add src/fetcher.py tests/test_fetcher.py
git commit -m "feat: implement JQL filtering for initiatives"
```

---

## Task 6: Update CLI to Pass Filter Parameters

**Files:**
- Modify: `jira_extract.py`

**Step 1: Read current CLI code**

Read `jira_extract.py` to understand current DataFetcher initialization.

**Step 2: Modify DataFetcher initialization**

In `jira_extract.py`, update the DataFetcher initialization in the `extract` command:

```python
# Create fetcher
fetcher = DataFetcher(
    client=client,
    initiatives_project=config.projects.initiatives,
    team_projects=config.projects.teams,
    rag_field_id=config.custom_fields.rag_status,
    quarter_field_id=config.custom_fields.quarter,
    filter_quarter=config.filters.quarter if config.filters else None,
)
```

**Step 3: Add console output for filtering**

In `jira_extract.py`, add after "Fetching data from Jira...":

```python
# Show filtering status
if config.filters and config.filters.quarter:
    click.echo(f"Applying filters: quarter='{config.filters.quarter}', status!='Done'")
```

**Step 4: Update summary output**

In `jira_extract.py`, modify the summary section:

```python
# Show summary
click.echo("\nSummary:")
if config.filters and config.filters.quarter:
    click.echo(f"  Initiatives: {len(data['initiatives'])} (filtered by quarter: {config.filters.quarter})")
else:
    click.echo(f"  Initiatives: {len(data['initiatives'])}")
click.echo(f"  Epics: {summary['total_epics']}")
click.echo(f"  Teams: {len(summary['teams_involved'])}")
```

**Step 5: Test manually**

Run: `python jira_extract.py extract --verbose`
Expected: Should work without filters (backward compatible)

**Step 6: Commit**

```bash
git add jira_extract.py
git commit -m "feat: wire up filter parameters in CLI"
```

---

## Task 7: Update config.yaml.example

**Files:**
- Modify: `config.yaml.example`

**Step 1: Add quarter field and filters section**

In `config.yaml.example`, update to show new fields:

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
  quarter: "customfield_XXXXX"  # Required if using filters

# Optional: Filter initiatives by quarter and status
# If omitted, all initiatives are extracted
filters:
  quarter: "25 Q1"  # Format: "YY QN" (e.g., "25 Q1", "25 Q2")

output:
  directory: "./data"
  filename_pattern: "jira_extract_{timestamp}.json"
```

**Step 2: Commit**

```bash
git add config.yaml.example
git commit -m "docs: update config example with filters"
```

---

## Task 8: Update README

**Files:**
- Modify: `README.md`

**Step 1: Add filtering section to README**

In `README.md`, add section after configuration section:

```markdown
### Optional: Filter by Quarter

To extract only initiatives for a specific quarter:

1. Add the quarter custom field ID to your config:
   ```yaml
   custom_fields:
     rag_status: "customfield_12111"
     quarter: "customfield_12108"  # Add this
   ```

2. Add the filters section:
   ```yaml
   filters:
     quarter: "25 Q1"  # Format: "YY QN"
   ```

When filtering is enabled:
- Only initiatives matching the specified quarter are extracted
- Initiatives with status "Done" are excluded
- Epics are still extracted for all team projects, but only those linked to filtered initiatives appear in the output

To disable filtering, simply remove or comment out the `filters` section.
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add filtering documentation to README"
```

---

## Task 9: Integration Testing

**Files:**
- Test all components together

**Step 1: Create test config with filters**

Create `config.yaml` with filters section using your actual values.

**Step 2: Run extraction with filtering**

Run: `python jira_extract.py extract --verbose`
Expected:
- Console shows: "Applying filters: quarter='25 Q1', status!='Done'"
- Extracts only matching initiatives
- Summary shows filtered count

**Step 3: Test without filters**

Remove `filters` section from `config.yaml`.

Run: `python jira_extract.py extract --verbose`
Expected:
- No filter message shown
- Extracts all initiatives
- Summary shows total count

**Step 4: Test validation error**

Set `filters.quarter` but remove `custom_fields.quarter` in `config.yaml`.

Run: `python jira_extract.py extract`
Expected: Error: "Quarter filtering requires custom_fields.quarter to be defined"

**Step 5: Restore working config**

Restore `config.yaml` to working state with filters.

---

## Task 10: Run Full Test Suite

**Files:**
- All test files

**Step 1: Run all tests**

Run: `pytest -v`
Expected: All tests PASS

**Step 2: Check test coverage**

Run: `pytest --cov=src --cov-report=term-missing`
Expected: Good coverage on modified files

**Step 3: Final commit**

```bash
git add -A
git commit -m "test: verify filtering integration"
```

---

## Completion Checklist

- [ ] Config schema extended with Filters and quarter field
- [ ] Config validation ensures quarter field exists when filtering
- [ ] Config loading parses filters section
- [ ] DataFetcher accepts filter parameters
- [ ] JQL construction includes filters conditionally
- [ ] CLI wires up filter parameters
- [ ] Console output shows filtering status
- [ ] Config example updated
- [ ] README documents filtering feature
- [ ] All tests passing
- [ ] Manual testing with real Jira data successful
