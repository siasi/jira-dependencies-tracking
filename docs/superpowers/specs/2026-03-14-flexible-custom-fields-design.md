# Flexible Custom Fields Design

**Date:** 2026-03-14
**Status:** Approved
**Author:** Claude Code

## Problem Statement

Currently, adding a new custom field to initiative extraction requires code changes in multiple places:
1. Modify `CustomFields` dataclass in `src/config.py`
2. Update `load_config()` to extract the field
3. Add parameter to `DataFetcher.__init__()` in `src/fetcher.py`
4. Update CLI to pass the new parameter in `jira_extract.py`
5. Modify field extraction logic in `fetch_initiatives()`

This creates friction and violates the Open/Closed principle. Adding "objective" field highlighted this pain point.

## Goals

1. Enable adding custom fields via config only (no code changes)
2. Maintain type safety and validation where possible
3. Keep configuration simple and readable
4. Support existing features (quarter filtering)
5. Breaking changes acceptable for cleaner design

## Non-Goals

- Custom fields for epics (only initiatives)
- Multiple field types beyond select/text (current support)
- Field metadata or type hints in config
- Backward compatibility with existing config format

## Design Overview

Replace hardcoded `CustomFields` dataclass with a simple dictionary mapping output field names to Jira field IDs. All custom fields are optional and treated uniformly, with special behavior (like quarter filtering) handled separately.

## Architecture

### 1. Configuration Structure

**New config format:**
```yaml
custom_fields:
  initiatives:
    rag_status: "customfield_12111"
    quarter: "customfield_12108"
    objective: "customfield_12101"
    strategic_priority: "customfield_12999"
    # Add any field here without code changes

filters:
  quarter: "26 Q2"  # References 'quarter' field above
```

**Key changes:**
- Add `initiatives` sub-key under `custom_fields` for future extensibility
- All fields are key-value pairs: `output_name: "jira_field_id"`
- No hardcoded field names in code
- Empty dict is valid (all fields optional)

**Special field behaviors:**
- If `quarter` field exists and `filters.quarter` is set, quarter field is used for filtering
- No other fields have special behavior

### 2. Data Model Changes

**Remove CustomFields dataclass:**
```python
# BEFORE
@dataclass
class CustomFields:
    """Custom field IDs."""
    rag_status: str
    quarter: Optional[str] = None

# AFTER - removed entirely
```

**Update Config dataclass:**
```python
@dataclass
class Config:
    """Main configuration."""
    jira: JiraConfig
    projects: ProjectsConfig
    custom_fields: Dict[str, str]  # Simple dict: {output_name: field_id}
    output: OutputConfig
    filters: Optional[Filters] = None
```

**Config loading:**
```python
# In load_config() function
custom_fields = data.get("custom_fields", {}).get("initiatives", {})

config = Config(
    jira=JiraConfig(...),
    projects=ProjectsConfig(...),
    custom_fields=custom_fields,  # Just pass the dict
    output=OutputConfig(...),
    filters=filters,
)
```

### 3. DataFetcher Changes

**Constructor simplification:**
```python
# BEFORE
def __init__(
    self,
    client: JiraClient,
    initiatives_project: str,
    team_projects: List[str],
    rag_field_id: str,              # Hardcoded parameter
    quarter_field_id: Optional[str] = None,  # Hardcoded parameter
    filter_quarter: Optional[str] = None,
):

# AFTER
def __init__(
    self,
    client: JiraClient,
    initiatives_project: str,
    team_projects: List[str],
    custom_fields: Dict[str, str],  # Generic dict
    filter_quarter: Optional[str] = None,
):
    self.client = client
    self.initiatives_project = initiatives_project
    self.team_projects = team_projects
    self.custom_fields = custom_fields  # {output_name: field_id}
    self.filter_quarter = filter_quarter
```

**CLI instantiation:**
```python
# In jira_extract.py

# BEFORE
fetcher = DataFetcher(
    client=client,
    initiatives_project=cfg.projects.initiatives,
    team_projects=cfg.projects.teams,
    rag_field_id=cfg.custom_fields.rag_status,
    quarter_field_id=cfg.custom_fields.quarter,
    filter_quarter=cfg.filters.quarter if cfg.filters else None,
)

# AFTER
fetcher = DataFetcher(
    client=client,
    initiatives_project=cfg.projects.initiatives,
    team_projects=cfg.projects.teams,
    custom_fields=cfg.custom_fields,  # Just pass the whole dict
    filter_quarter=cfg.filters.quarter if cfg.filters else None,
)
```

### 4. Field Extraction Logic

**Dynamic field fetching:**
```python
def fetch_initiatives(self) -> FetchResult:
    """Fetch all initiatives from the initiatives project."""

    # Build JQL
    jql = f"project = {self.initiatives_project} AND issuetype = Initiative"

    # Handle quarter filtering
    if self.filter_quarter and "quarter" in self.custom_fields:
        quarter_field_id = self.custom_fields["quarter"]
        jql += f' AND status != "Done" AND {quarter_field_id} = "{self.filter_quarter}"'

    # Build fields list - dynamic from config
    # NOTE: Fetches ALL configured custom fields, even if not used for filtering
    # This simplifies the code; Jira API batches field requests efficiently
    fields = ["summary", "status"] + list(self.custom_fields.values())

    issues = self.client.search_issues(jql, fields=fields)

    # Extract custom fields - generic helper
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

def _extract_field_value(self, field_data: Any) -> Optional[str]:
    """Extract value from Jira custom field.

    Handles:
    - Select fields: {"value": "🟢"} → "🟢"
    - Text fields: "plain text" → "plain text"
    - Missing fields: None → None
    """
    if field_data is None:
        return None
    if isinstance(field_data, dict):
        return field_data.get("value")
    return field_data  # Plain string or other simple type
```

### 5. Validation Logic

**Config validation:**
```python
# In Config.validate() method
def validate(self) -> None:
    """Validate configuration."""
    # Check quarter filtering dependency
    if self.filters and self.filters.quarter:
        if "quarter" not in self.custom_fields:
            raise ConfigError(
                "Quarter filtering requires custom_fields.initiatives.quarter to be defined"
            )
```

**Custom field validation in CLI:**
```python
# In validate_config command
@cli.command()
def validate_config(config: str):
    """Validate configuration file."""
    try:
        cfg = load_config(config)

        # ... existing validation ...

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

    except ConfigError as e:
        click.echo(click.style(f"\n✗ Configuration error: {e}", fg="red"), err=True)
        sys.exit(2)
```

### 6. Output Structure

**Before (limited fields):**
```json
{
  "initiatives": [
    {
      "key": "INIT-1485",
      "summary": "Deprecate EU connector",
      "status": "Proposed",
      "rag_status": "🟢",
      "url": "https://...",
      "contributing_teams": [...]
    }
  ]
}
```

**After (configurable fields):**
```json
{
  "initiatives": [
    {
      "key": "INIT-1485",
      "summary": "Deprecate EU connector",
      "status": "Proposed",
      "rag_status": "🟢",
      "objective": "Reduce technical debt",
      "quarter": "26 Q2",
      "strategic_priority": "High",
      "url": "https://...",
      "contributing_teams": [...]
    }
  ]
}
```

**With no custom fields configured (empty dict):**
```json
{
  "initiatives": [
    {
      "key": "INIT-1485",
      "summary": "Deprecate EU connector",
      "status": "Proposed",
      "url": "https://...",
      "contributing_teams": [...]
    }
  ]
}
```

**Key points:**
- Field names in output match config keys exactly
- Fields appear in initiative objects only (not epics)
- Missing/null fields appear as `null` in JSON

**How builder.py handles dynamic fields:**

The current `builder.py` code explicitly extracts known fields:
```python
result_initiatives.append({
    "key": initiative["key"],
    "summary": initiative["summary"],
    "status": initiative["status"],
    "rag_status": initiative["rag_status"],  # Hardcoded
    "url": initiative["url"],
    "contributing_teams": contributing_teams,
})
```

**After this change**, builder.py will pass through ALL fields from the initiative dict:
```python
# Build base initiative with known fields
initiative_output = {
    "key": initiative["key"],
    "summary": initiative["summary"],
    "status": initiative["status"],
    "url": initiative["url"],
}

# Add all custom fields dynamically
for field_name in initiative.keys():
    if field_name not in ["key", "summary", "status", "url", "contributing_teams"]:
        initiative_output[field_name] = initiative[field_name]

# Add contributing teams last
initiative_output["contributing_teams"] = contributing_teams

result_initiatives.append(initiative_output)
```

This approach:
- Preserves known field order (key, summary, status, url)
- Passes through any custom fields from fetcher
- Doesn't require builder.py to know about specific custom field names
- Works with zero, one, or many custom fields

## Error Handling

### Principles (Scripts Only)

1. **Fail fast on config errors** (startup/validation)
2. **Degrade gracefully on data issues** (runtime)
3. **Clear error messages with field names**
4. **No silent failures**

### Scenarios

**1. Missing custom_fields section in config:**
```python
custom_fields = data.get("custom_fields", {}).get("initiatives", {})
# Result: empty dict, no fields fetched (all optional)
```

**2. Invalid field ID (Jira API doesn't recognize it):**
- Jira API silently returns empty/null for unknown fields
- Output will show `null` for that field
- `validate-config` command will catch this and report error (checks field exists in Jira)
- **Validation limitation:** validate-config only checks field ID exists globally, not whether it's accessible on Initiative issue type
- Normal extraction continues (degraded, not failing) if field exists but isn't on initiatives

**3. Quarter filtering without quarter field:**
```python
def validate(self) -> None:
    if self.filters and self.filters.quarter:
        if "quarter" not in self.custom_fields:
            raise ConfigError(
                "Quarter filtering requires custom_fields.initiatives.quarter"
            )
# Fails at config load time with clear message
```

**4. Malformed field value from Jira:**
```python
def _extract_field_value(self, field_data):
    if field_data is None:
        return None
    if isinstance(field_data, dict):
        return field_data.get("value")  # Returns None if "value" key missing
    return field_data  # Handles strings or other simple types
# Always returns something (None if can't extract)
```

**5. Field exists in config but missing on some initiatives:**
- Field returns `null` for those initiatives
- No error, extraction continues
- Inconsistent data is visible in output

## Testing Strategy

### Test Coverage

**1. Config loading tests** (`tests/test_config.py`):
- `test_load_config_with_custom_fields()` - Multiple custom fields load correctly
- `test_load_config_empty_custom_fields()` - Empty custom_fields section defaults to empty dict
- `test_load_config_missing_custom_fields()` - Missing custom_fields section defaults to empty dict
- `test_validate_quarter_filter_requires_quarter_field()` - Validation fails if filtering by quarter without quarter field

**2. Field extraction tests** (`tests/test_fetcher.py`):
- `test_extract_field_value_select_field()` - Handles `{"value": "🟢"}` → `"🟢"`
- `test_extract_field_value_text_field()` - Handles `"plain text"` → `"plain text"`
- `test_extract_field_value_null()` - Handles `None` → `None`
- `test_fetch_initiatives_with_multiple_custom_fields()` - All configured fields appear in output
- `test_fetch_initiatives_with_no_custom_fields()` - Works with empty custom_fields dict
- `test_fetch_initiatives_with_partially_missing_custom_field_values()` - Some initiatives have field, others don't (returns null)

**3. Builder tests** (`tests/test_builder.py`):
- `test_build_hierarchy_with_custom_fields()` - Custom fields from fetcher pass through to output
- `test_build_hierarchy_with_no_custom_fields()` - Works with initiatives containing only base fields

**4. Validation tests** (`tests/test_config.py` or `tests/test_cli.py`):
- `test_validate_config_checks_custom_field_exists()` - validate-config command detects invalid field IDs
- `test_validate_config_passes_with_valid_custom_fields()` - validate-config succeeds with valid fields

**5. Integration tests** (`tests/test_integration.py`):
- `test_end_to_end_with_custom_fields()` - Full extraction with custom fields produces correct JSON

### Testing Principles

- Test the generic extraction function (handles any field)
- Test with 0, 1, and multiple custom fields
- Test field value type handling (dict vs string)
- Test quarter filtering dependency validation
- Mock Jira API responses as before

## Migration Path

**Old config:**
```yaml
custom_fields:
  rag_status: "customfield_12111"
  quarter: "customfield_12108"
```

**New config:**
```yaml
custom_fields:
  initiatives:
    rag_status: "customfield_12111"
    quarter: "customfield_12108"
```

**Migration steps:**
1. Nest existing fields under `initiatives` key
2. Update any scripts/documentation referencing old structure
3. Run `validate-config` to ensure all fields are valid

## Benefits

1. **Zero code changes for new fields** - just edit config.yaml
2. **Simpler codebase** - no dataclass to maintain, fewer parameters
3. **Flexible** - any number of custom fields supported
4. **Type-safe where it matters** - validation at config load and runtime
5. **Self-documenting** - config shows exactly what fields are extracted
6. **Testable** - generic extraction logic with clear contracts

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking change for existing configs | Users must update config | Document migration, provide clear error messages |
| Loss of type safety for field names | Typos in config won't be caught at compile time | Validation command checks field IDs exist in Jira |
| Field ID typos in config | Silent failures (null values) | Validation command required before first extraction |
| Performance with many fields | More API overhead | Jira API already batches field requests efficiently |

## Future Enhancements

Potential future work (out of scope for this design):

1. Support custom fields for epics (add `epics` section alongside `initiatives`)
2. Field metadata in config (type hints, required/optional flags)
3. Field value transformations (e.g., date formatting)
4. Generic filtering (filter by any custom field, not just quarter)
5. Field aliases (multiple output names for same Jira field)

## Alternatives Considered

### Alternative 1: Grouped by Purpose
```yaml
custom_fields:
  initiatives:
    display:
      rag_status: "customfield_12111"
    filtering:
      quarter: "customfield_12108"
```
**Rejected:** Adds complexity without clear benefit. A field could be used for both display and filtering.

### Alternative 2: Rich Field Definitions
```yaml
custom_fields:
  initiatives:
    rag_status:
      id: "customfield_12111"
      type: select
      required: true
```
**Rejected:** Overkill for current needs. Simple dict is sufficient and more readable.

## Decision

Proceed with **Simple Dictionary** approach as designed above.
