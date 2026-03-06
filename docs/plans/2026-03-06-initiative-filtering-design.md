# Initiative Filtering Design

## Goal

Add optional filtering to extract only initiatives matching a specific quarter and exclude "Done" initiatives, while maintaining backward compatibility with existing configs.

## Requirements

- Filter initiatives by quarter field (customfield_12108) when configured
- Exclude initiatives with status "Done"
- Make filtering optional - if not configured, extract all initiatives (current behavior)
- No filtering on epics - show all epics belonging to filtered initiatives
- Maintain backward compatibility with existing config files

## Approach

**JQL-based filtering** - Add filters directly to the JQL query at API level for maximum efficiency.

### Why This Approach?

- Most efficient - filters at API level, minimal data transfer
- Fastest performance - Jira does the filtering
- Clean implementation - JQL is the native way to filter Jira data
- Follows Jira best practices

## Architecture

### Configuration Schema

Add optional filtering configuration to `config.yaml`:

```yaml
jira:
  instance: "your-company.atlassian.net"

projects:
  initiatives: "INIT"
  teams:
    - "RSK"
    - "CBNK"

custom_fields:
  rag_status: "customfield_12111"
  quarter: "customfield_12108"  # New field

filters:  # New section - optional
  quarter: "25 Q1"  # If omitted, no filtering applied
```

**Backward Compatibility:**
- If `custom_fields.quarter` not defined → error if `filters.quarter` is set
- If `filters.quarter` not defined → extract all initiatives (current behavior)
- No breaking changes to existing configs

### JQL Construction

**Without filtering (current):**
```jql
project = INIT AND issuetype = Initiative
```

**With filtering:**
```jql
project = INIT AND issuetype = Initiative AND status != "Done" AND customfield_12108 = "25 Q1"
```

### Data Flow

1. **Config Loading** - Parse config, validate filter settings
2. **Fetch Initiatives** - Build JQL with optional filters, fetch from Jira
3. **Fetch Epics** - No filtering, fetch all epics from team projects (unchanged)
4. **Build Relationships** - Link epics to initiatives (builder automatically excludes epics without matching parent)
5. **Output** - JSON with filtered data

## Component Changes

### 1. src/config.py
- Add `quarter_field_id: Optional[str]` to CustomFields dataclass
- Add new `Filters` dataclass with `quarter: Optional[str]`
- Add `filters: Optional[Filters]` to Config dataclass
- Add validation: if `filters.quarter` is set, `custom_fields.quarter` must exist

### 2. src/fetcher.py
- Add `quarter_field_id: Optional[str]` parameter to `DataFetcher.__init__()`
- Add `filter_quarter: Optional[str]` parameter to `DataFetcher.__init__()`
- Modify `fetch_initiatives()`:
  - Build base JQL: `project = X AND issuetype = Initiative`
  - If `filter_quarter` is set, append: `AND status != "Done" AND {quarter_field_id} = "{filter_quarter}"`
  - Add quarter field to fields list when filtering active
  - Include quarter value in normalized initiative data
- No changes to `fetch_epics()` - epics remain unfiltered

### 3. jira_extract.py
- Pass `quarter_field_id` and `filter_quarter` from config to `DataFetcher` initialization
- Add console output when filtering is active: "Applying filters: quarter='25 Q1', status!='Done'"
- Update summary to indicate filtering: "Initiatives: 150 (filtered by quarter: 25 Q1)"

### 4. Tests
- **tests/test_config.py:**
  - Test valid config with filters
  - Test config with filter but missing quarter field ID (should error)
  - Test config without filters (should work)
  - Test backward compatible configs

- **tests/test_fetcher.py:**
  - Test JQL construction with quarter filter
  - Test JQL construction without filter
  - Test fields list includes quarter when filtering
  - Test integration with mock data

## Error Handling

### Configuration Validation
- `filters.quarter` set but `custom_fields.quarter` missing → Error: "Quarter filtering requires custom_fields.quarter to be defined"
- Invalid quarter field ID format → Error: "Invalid quarter field ID format"

### Runtime Behavior
- No initiatives match filters → Success with 0 initiatives (valid result, not error)
- Jira API rejects JQL → JiraAPIError with the failing JQL in message
- Quarter field doesn't exist in Jira → API error caught and reported

### User Feedback
- When filtering active: "Applying filters: quarter='25 Q1', status!='Done'"
- Summary with filtering: "Initiatives: 150 (filtered by quarter: 25 Q1)"
- Summary without filtering: "Initiatives: 1293 (no filters applied)"

## Testing Strategy

### Unit Tests
1. Config validation with various filter combinations
2. JQL construction with and without filters
3. Fields list includes quarter field when filtering
4. Integration test with mocked Jira API

### Manual Testing
1. Test with actual Jira instance using "25 Q1" quarter
2. Verify filtered results are correct
3. Test with `filters` section removed (backward compatibility)
4. Verify error messages are helpful

## Success Criteria

- Filtering reduces dataset to only relevant initiatives for planning
- Existing configs without filters continue working unchanged
- Clear user feedback about what filtering is applied
- Fast performance through API-level filtering
- All tests passing
