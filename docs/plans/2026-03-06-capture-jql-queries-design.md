# Capture JQL Queries in Output Design

## Goal

Add the JQL queries used for extraction to the output JSON file, making it transparent what filters were applied.

## Requirements

- Capture both initiatives and epics JQL queries
- Include in output JSON at top level (not in extraction_status)
- Use nested structure: `"queries": {"initiatives": "...", "epics": "..."}`
- Maintain backward compatibility

## Approach

**Return JQL from Fetcher Methods** - Modify fetch methods to return the JQL query they constructed along with the results.

### Why This Approach?

- Clean design: the component that builds the query returns what it built
- Easy to test: JQL is directly available in return value
- Single source of truth: no duplication of JQL construction logic
- Transparent: always shows the actual query that was executed

## Architecture

### Data Structure Changes

**FetchResult Dataclass:**
Add optional `jql` field to capture the query:

```python
@dataclass
class FetchResult:
    """Result of a fetch operation."""
    success: bool
    items: List[Dict[str, Any]]
    error_message: Optional[str] = None
    project_key: Optional[str] = None
    jql: Optional[str] = None  # NEW: JQL query used
```

**Output JSON Structure:**
Add `queries` object at top level:

```json
{
  "extracted_at": "2026-03-06T18:54:11Z",
  "jira_instance": "example.atlassian.net/",
  "queries": {
    "initiatives": "project = INIT AND issuetype = Initiative AND status != \"Done\" AND customfield_12108 = \"25 Q1\"",
    "epics": "(project = RSK OR project = CBNK) AND issuetype = Epic"
  },
  "extraction_status": {...},
  "initiatives": [...],
  "orphaned_epics": [...],
  "summary": {...}
}
```

## Component Changes

### 1. src/fetcher.py

**FetchResult dataclass:**
- Add `jql: Optional[str] = None` field

**fetch_initiatives() method:**
- Store JQL in variable before executing
- Return JQL in FetchResult: `FetchResult(success=True, items=initiatives, jql=jql)`

**fetch_epics() method:**
- Store JQL in variable before executing (handle empty team projects case)
- Return JQL in FetchResult: `FetchResult(success=True, items=epics, jql=jql)`

### 2. jira_scan.py

**extract command:**
- After fetching, extract queries from results:
  ```python
  queries = {
      "initiatives": initiatives_result.jql,
      "epics": epics_result.jql
  }
  ```
- Pass queries to OutputGenerator.generate()

### 3. src/output.py

**OutputGenerator.generate() method:**
- Add `queries: Optional[Dict[str, str]] = None` parameter
- Include queries in output JSON at top level (after jira_instance, before extraction_status)

## Data Flow

```
1. DataFetcher.fetch_initiatives()
   - Builds JQL: "project = INIT AND issuetype = Initiative AND status != 'Done' ..."
   - Executes query
   - Returns: FetchResult(success=True, items=[...], jql="...")

2. DataFetcher.fetch_epics()
   - Builds JQL: "(project = RSK OR project = CBNK) AND issuetype = Epic"
   - Executes query
   - Returns: FetchResult(success=True, items=[...], jql="...")

3. jira_scan.py
   - Extracts: queries = {"initiatives": result.jql, "epics": result.jql}
   - Passes to: output_generator.generate(data, status, queries=queries)

4. OutputGenerator.generate()
   - Adds queries to output JSON at top level
   - Writes file
```

## Testing Strategy

### Unit Tests

**tests/test_fetcher.py:**
- Update all FetchResult assertions to handle new jql field
- Verify `test_fetch_initiatives_jql_without_filters` returns correct JQL
- Verify `test_fetch_initiatives_jql_with_quarter_filter` returns filtered JQL
- Verify `test_fetch_epics_with_empty_team_projects` returns None or empty JQL
- Verify `test_fetch_epics_with_multiple_teams` returns correct JQL

**tests/test_output.py:**
- Add test that queries object appears in output JSON
- Verify queries are at top level (not nested in extraction_status)
- Verify structure: `{"initiatives": "...", "epics": "..."}`
- Test with None queries (backward compatibility)

### Manual Testing

1. Run extraction with filters enabled
2. Check output JSON has queries object
3. Verify initiatives JQL includes filter
4. Verify epics JQL matches expected

## Backward Compatibility

- `FetchResult.jql` is optional (defaults to None)
- Existing code that creates FetchResult without jql continues to work
- Output JSON adds new field - parsers that ignore unknown fields are unaffected
- If queries is None, it won't be included in output (graceful degradation)

## Success Criteria

- Output JSON contains queries object at top level
- Queries show actual JQL executed for both initiatives and epics
- All existing tests pass with updated assertions
- New tests verify queries are captured correctly
- Manual testing confirms queries match filtering configuration
