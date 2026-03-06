# Capture JQL Queries in Output Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add JQL queries used during extraction to the output JSON file for transparency and debugging.

**Architecture:** Add `jql` field to FetchResult dataclass, modify fetch methods to return the JQL they construct, pass queries through to OutputGenerator, and include at top level of JSON output.

**Tech Stack:** Python 3.9+, dataclasses, pytest

---

## Task 1: Add JQL Field to FetchResult

**Files:**
- Modify: `src/fetcher.py`
- Test: `tests/test_fetcher.py`

**Step 1: Write failing test for jql field in FetchResult**

Add to `tests/test_fetcher.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_fetcher.py::test_fetch_result_includes_jql -v`
Expected: FAIL with "unexpected keyword argument 'jql'"

**Step 3: Add jql field to FetchResult**

In `src/fetcher.py`, modify FetchResult dataclass:

```python
@dataclass
class FetchResult:
    """Result of a fetch operation."""
    success: bool
    items: List[Dict[str, Any]]
    error_message: Optional[str] = None
    project_key: Optional[str] = None
    jql: Optional[str] = None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_fetcher.py::test_fetch_result_includes_jql -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/fetcher.py tests/test_fetcher.py
git commit -m "feat: add jql field to FetchResult dataclass"
```

---

## Task 2: Return JQL from fetch_initiatives

**Files:**
- Modify: `src/fetcher.py`
- Test: `tests/test_fetcher.py`

**Step 1: Update existing test to check jql is returned**

Modify `test_fetch_initiatives_jql_without_filters` in `tests/test_fetcher.py`:

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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_fetcher.py::test_fetch_initiatives_jql_without_filters -v`
Expected: FAIL with "assert None is not None" (jql not returned)

**Step 3: Modify fetch_initiatives to return jql**

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
            # ... existing normalization code ...

        return FetchResult(success=True, items=initiatives, jql=jql)

    except JiraAPIError as e:
        return FetchResult(
            success=False,
            items=[],
            error_message=str(e),
            project_key=self.initiatives_project,
            jql=jql,  # Include JQL even on error
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_fetcher.py::test_fetch_initiatives_jql_without_filters -v`
Expected: PASS

**Step 5: Update test with filters to check jql**

Modify `test_fetch_initiatives_jql_with_quarter_filter` in `tests/test_fetcher.py`:

Add at the end:

```python
    # Check JQL is returned in result
    assert result.jql is not None
    assert result.jql == jql
```

**Step 6: Run test to verify it passes**

Run: `pytest tests/test_fetcher.py::test_fetch_initiatives_jql_with_quarter_filter -v`
Expected: PASS

**Step 7: Commit**

```bash
git add src/fetcher.py tests/test_fetcher.py
git commit -m "feat: return jql from fetch_initiatives"
```

---

## Task 3: Return JQL from fetch_epics

**Files:**
- Modify: `src/fetcher.py`
- Test: `tests/test_fetcher.py`

**Step 1: Write failing test for epics jql**

Add to `tests/test_fetcher.py`:

```python
def test_fetch_epics_returns_jql():
    """Test fetch_epics returns JQL in result."""
    from src.fetcher import DataFetcher
    from unittest.mock import Mock

    mock_client = Mock()
    mock_client.search_issues.return_value = []
    mock_client.base_url = "https://test.atlassian.net"

    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=["RSK", "CBNK"],
        rag_field_id="customfield_12111"
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

    fetcher = DataFetcher(
        client=mock_client,
        initiatives_project="INIT",
        team_projects=[],
        rag_field_id="customfield_12111"
    )

    result = fetcher.fetch_epics()

    # Empty teams means no query executed
    assert result.success is True
    assert result.jql is None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fetcher.py::test_fetch_epics_returns_jql tests/test_fetcher.py::test_fetch_epics_empty_teams_returns_none_jql -v`
Expected: FAIL with "assert None is not None"

**Step 3: Modify fetch_epics to return jql**

In `src/fetcher.py`, modify `fetch_epics` method:

```python
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
    fields = ["summary", "status", "parent", "project", self.rag_field_id]

    try:
        issues = self.client.search_issues(jql, fields=fields)

        # Normalize epic data
        epics = []
        for issue in issues:
            # ... existing normalization code ...

        return FetchResult(success=True, items=epics, jql=jql)

    except JiraAPIError as e:
        return FetchResult(
            success=False,
            items=[],
            error_message=str(e),
            jql=jql,  # Include JQL even on error
        )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fetcher.py::test_fetch_epics_returns_jql tests/test_fetcher.py::test_fetch_epics_empty_teams_returns_none_jql -v`
Expected: PASS

**Step 5: Run all fetcher tests**

Run: `pytest tests/test_fetcher.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/fetcher.py tests/test_fetcher.py
git commit -m "feat: return jql from fetch_epics"
```

---

## Task 4: Add Queries Parameter to OutputGenerator

**Files:**
- Modify: `src/output.py`
- Test: `tests/test_output.py`

**Step 1: Write failing test for queries in output**

Add to `tests/test_output.py`:

```python
def test_generate_output_with_queries():
    """Test output includes queries object."""
    from src.output import OutputGenerator, ExtractionStatus
    import json
    import tempfile
    from pathlib import Path

    # Setup
    temp_dir = tempfile.mkdtemp()
    output_path = Path(temp_dir) / "test_output.json"

    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=temp_dir
    )

    data = {
        "initiatives": [],
        "orphaned_epics": [],
        "summary": {
            "total_initiatives": 0,
            "total_epics": 0,
            "teams_involved": []
        }
    }

    status = ExtractionStatus(
        complete=True,
        issues=[]
    )

    queries = {
        "initiatives": "project = INIT AND issuetype = Initiative",
        "epics": "(project = RSK OR project = CBNK) AND issuetype = Epic"
    }

    # Execute
    result_path = generator.generate(data, status, queries=queries, custom_path=output_path)

    # Verify
    with open(result_path) as f:
        output = json.load(f)

    assert "queries" in output
    assert output["queries"]["initiatives"] == "project = INIT AND issuetype = Initiative"
    assert output["queries"]["epics"] == "(project = RSK OR project = CBNK) AND issuetype = Epic"

    # Verify queries is at top level, before extraction_status
    keys = list(output.keys())
    queries_index = keys.index("queries")
    status_index = keys.index("extraction_status")
    assert queries_index < status_index
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_output.py::test_generate_output_with_queries -v`
Expected: FAIL with "unexpected keyword argument 'queries'" or "assert 'queries' in output"

**Step 3: Add queries parameter to generate method**

In `src/output.py`, modify `generate` method:

```python
def generate(
    self,
    data: Dict[str, Any],
    extraction_status: ExtractionStatus,
    queries: Optional[Dict[str, str]] = None,
    custom_path: Optional[Path] = None,
) -> Path:
    """Generate JSON output file.

    Args:
        data: Hierarchy data from builder
        extraction_status: Extraction status information
        queries: JQL queries used for extraction (initiatives and epics)
        custom_path: Optional custom output path (overrides directory/pattern)

    Returns:
        Path to generated file
    """
    # Prepare output
    output = {
        "extracted_at": datetime.utcnow().isoformat() + "Z",
        "jira_instance": self.jira_instance,
    }

    # Add queries if provided
    if queries:
        output["queries"] = queries

    output.update({
        "extraction_status": asdict(extraction_status),
        "initiatives": data["initiatives"],
        "orphaned_epics": data.get("orphaned_epics", []),
        "summary": data["summary"],
    })

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

Run: `pytest tests/test_output.py::test_generate_output_with_queries -v`
Expected: PASS

**Step 5: Run all output tests**

Run: `pytest tests/test_output.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/output.py tests/test_output.py
git commit -m "feat: add queries parameter to OutputGenerator"
```

---

## Task 5: Wire Up Queries in CLI

**Files:**
- Modify: `jira_extract.py`

**Step 1: Extract queries from fetch results**

In `jira_extract.py`, find where `fetch_all()` is called (around line 90-95) and modify:

```python
# Fetch data
click.echo("Fetching data from Jira...")

# Show filtering status
if cfg.filters and cfg.filters.quarter:
    click.echo(f"Applying filters: quarter='{cfg.filters.quarter}', status!='Done'")

click.echo("Extracting")
initiatives_result, epics_result = fetcher.fetch_all()

# Extract queries
queries = {
    "initiatives": initiatives_result.jql,
    "epics": epics_result.jql
}
```

**Step 2: Pass queries to OutputGenerator**

Find where `output_generator.generate()` is called (around line 150) and modify:

```python
# Generate output
output_path = output_generator.generate(
    data=hierarchy_data,
    extraction_status=extraction_status,
    queries=queries,
    custom_path=output_file,
)
```

**Step 3: Test manually**

Run: `python jira_extract.py extract --verbose`
Expected: Command runs successfully

**Step 4: Verify output contains queries**

Run: `cat data/jira_extract_*.json | grep -A 3 '"queries"'`
Expected: Should see queries object with initiatives and epics JQL

**Step 5: Commit**

```bash
git add jira_extract.py
git commit -m "feat: wire up queries in CLI output"
```

---

## Task 6: Integration Testing

**Files:**
- Manual testing only

**Step 1: Test with filtering enabled**

Add to `config.yaml`:
```yaml
filters:
  quarter: "25 Q1"
```

Run: `python jira_extract.py extract`

**Step 2: Verify output has filtered JQL**

Check output file:
```bash
cat data/jira_extract_*.json | python -m json.tool | grep -A 5 '"queries"'
```

Expected output:
```json
  "queries": {
    "initiatives": "project = INIT AND issuetype = Initiative AND status != \"Done\" AND customfield_12108 = \"25 Q1\"",
    "epics": "(project = RSK OR project = CBNK) AND issuetype = Epic"
  },
```

**Step 3: Test without filtering**

Remove `filters` section from `config.yaml`

Run: `python jira_extract.py extract`

**Step 4: Verify output has unfiltered JQL**

Check output file:
```bash
cat data/jira_extract_*.json | python -m json.tool | grep -A 5 '"queries"'
```

Expected:
```json
  "queries": {
    "initiatives": "project = INIT AND issuetype = Initiative",
    "epics": "(project = RSK OR project = CBNK) AND issuetype = Epic"
  },
```

**Step 5: Verify queries placement**

Check that queries comes after jira_instance and before extraction_status:

```bash
cat data/jira_extract_*.json | python -m json.tool | head -20
```

Expected order:
1. extracted_at
2. jira_instance
3. queries
4. extraction_status
5. initiatives
6. ...

---

## Task 7: Run Full Test Suite

**Files:**
- All test files

**Step 1: Run all tests**

Run: `pytest -v`
Expected: All tests PASS (except pre-existing pagination test)

**Step 2: Verify test count**

Expected: At least 34 tests (30 existing + 4 new)

**Step 3: Final commit if needed**

If any loose ends:
```bash
git add -A
git commit -m "test: verify queries integration"
```

---

## Completion Checklist

- [ ] FetchResult has jql field
- [ ] fetch_initiatives returns JQL in result
- [ ] fetch_epics returns JQL in result
- [ ] OutputGenerator accepts queries parameter
- [ ] Queries appear in output JSON at top level
- [ ] CLI passes queries from fetcher to output
- [ ] Tests verify JQL is captured correctly
- [ ] Manual testing confirms queries in output
- [ ] All tests passing (except pre-existing failures)
