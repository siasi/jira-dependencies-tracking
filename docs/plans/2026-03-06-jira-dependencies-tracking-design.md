# Jira Dependencies Tracking - Design Document

**Date:** 2026-03-06
**Status:** Approved

## Overview

A Python CLI tool to extract Jira data showing relationships between initiatives and contributing teams. The tool fetches initiatives from a portfolio project and their associated epics from team projects, enabling analysis of which teams contribute to which initiatives.

## Problem Statement

Need to understand initiative → team relationships in Jira where:
- Initiatives live in a dedicated project (INIT)
- Teams have their own Jira projects (e.g., RSK, PAYMENTS, PLATFORM)
- Teams contribute to initiatives through epics (parent-child relationship)
- Both initiatives and epics have status and RAG (Red/Amber/Green) indicators
- Data needs to be extracted on-demand for analysis and diagram generation

## Architecture

### Selected Approach: Parallel Fetch with Relationship Matching

**Core Flow:**
1. **Configuration Loading**: Read team project keys and Jira credentials from config file and environment
2. **API Client**: Jira Cloud REST API wrapper using `requests` library with connection pooling
3. **Data Fetcher**: Two parallel fetch operations using `concurrent.futures.ThreadPoolExecutor`:
   - Fetch all initiatives from INIT project (with status, RAG custom field)
   - Fetch all epics from configured team projects (with status, parent links)
4. **Relationship Builder**: Match epics to initiatives using parent field, group by team (project key)
5. **Output Generator**: Write structured JSON showing initiative → team → epics hierarchy

**Why this approach:**
- Fast: Concurrent API requests minimize wait time
- Scalable: Handles large datasets efficiently (hundreds of initiatives/epics)
- Robust: Handles missing relationships gracefully

**Key Libraries:**
- `requests` - Jira API calls
- `concurrent.futures` - Parallel fetching (thread pool of 10)
- `click` - CLI framework
- `python-dotenv` - Environment variable loading
- `pyyaml` - Configuration parsing
- Python 3.9+ - Type hints, modern syntax

## Data Model

### Output Structure

```json
{
  "extracted_at": "2026-03-06T16:30:00Z",
  "jira_instance": "your-company.atlassian.net",
  "extraction_status": {
    "complete": true,
    "issues": [],
    "initiatives_fetched": 50,
    "initiatives_failed": 0,
    "team_projects_fetched": 5,
    "team_projects_failed": 0
  },
  "initiatives": [
    {
      "key": "INIT-1115",
      "summary": "Initiative title",
      "status": "In Progress",
      "rag_status": "Green",
      "url": "https://your-company.atlassian.net/browse/INIT-1115",
      "contributing_teams": [
        {
          "team_project_key": "RSK",
          "team_project_name": "Risk Team",
          "epics": [
            {
              "key": "RSK-123",
              "summary": "Epic title",
              "status": "In Progress",
              "rag_status": "Amber",
              "url": "https://your-company.atlassian.net/browse/RSK-123"
            }
          ]
        }
      ]
    }
  ],
  "orphaned_epics": [
    {
      "key": "RSK-456",
      "summary": "Epic without parent initiative",
      "status": "To Do",
      "rag_status": "Green",
      "url": "https://your-company.atlassian.net/browse/RSK-456"
    }
  ],
  "summary": {
    "total_initiatives": 50,
    "total_epics": 200,
    "teams_involved": ["RSK", "PAYMENTS", "PLATFORM"]
  }
}
```

**Key Features:**
- Hierarchical: Initiative → Teams → Epics
- Complete URLs for navigation back to Jira
- Metadata: extraction timestamp, instance info
- Completeness tracking in `extraction_status`
- Orphaned epics section for epics without parent initiatives
- Summary statistics

## Configuration

### config.yaml (template in git as config.yaml.example)

```yaml
jira:
  instance: "your-company.atlassian.net"
  # Email and API token loaded from environment variables

projects:
  initiatives: "INIT"
  teams:
    - "RSK"
    - "PAYMENTS"
    - "PLATFORM"
    # Add more team project keys as needed

custom_fields:
  rag_status: "customfield_10050"  # Find using list-fields command

output:
  directory: "./data"
  filename_pattern: "jira_extract_{timestamp}.json"
```

### .env (gitignored, copied from .env.example)

```
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-api-token-here
```

**Security:**
- API token and email stored in environment variables (not in config)
- `config.yaml` and `.env` are gitignored
- Only `config.yaml.example` and `.env.example` committed to git with placeholder values

## CLI Interface

### Main Command

```bash
python jira_scan.py extract
```

### Options

```bash
# Specify custom config file
python jira_scan.py extract --config custom_config.yaml

# Custom output path
python jira_scan.py extract --output ./reports/my_export.json

# Dry run (show what would be fetched without writing)
python jira_scan.py extract --dry-run

# Verbose output for debugging
python jira_scan.py extract --verbose
```

### Helper Commands

```bash
# List available custom fields (helps find RAG field ID)
python jira_scan.py list-fields

# Validate configuration
python jira_scan.py validate-config

# Show version and help
python jira_scan.py --version
python jira_scan.py --help
```

### Output Behavior

- Progress indicators during fetch (spinner or progress bar)
- Summary stats printed to console upon completion
- JSON file written to configured location
- Clear warnings if extraction incomplete

## Error Handling

### Authentication Errors

- Missing credentials → Clear error message with setup instructions
- Invalid API token → Message to check token and regenerate if needed
- 401/403 responses → Verify permissions to access INIT and team projects

### Data Issues

- Custom field not found → Warning with instructions to run `list-fields`
- Epic missing parent link → Log warning, include in `orphaned_epics` section
- Missing team project → Skip with warning, continue with others
- Empty results → Inform user (no initiatives or no matching epics)

### API Issues

- Rate limiting → Implement exponential backoff, retry up to 3 times
- Network timeout → Configurable timeout (default 30s), clear error message
- Partial failures → Continue with successful fetches, report failures in summary

### Completeness Tracking

The tool explicitly tracks and reports extraction completeness:

**JSON Output includes `extraction_status`:**
```json
{
  "extraction_status": {
    "complete": false,
    "issues": [
      {
        "severity": "error",
        "message": "Failed to fetch from project RSK: 403 Forbidden",
        "impact": "Missing all epics from RSK team"
      },
      {
        "severity": "warning",
        "message": "5 epics found without parent initiative",
        "impact": "5 epics listed in orphaned_epics section"
      }
    ],
    "initiatives_fetched": 48,
    "initiatives_failed": 2,
    "team_projects_fetched": 4,
    "team_projects_failed": 1
  }
}
```

**Exit Codes:**
- `0` = Complete success (all data extracted)
- `1` = Partial success (some data missing, warnings present)
- `2` = Critical failure (no data extracted)

**Console Output:**
- Bold warning at end if extraction incomplete
- Summary of what was missed and why

**Strategy:** The tool prioritizes completing the extraction even with partial data rather than failing completely, but always makes it clear when data is incomplete.

## Implementation Details

### Project Structure

```
jira-dependencies-tracking/
├── README.md
├── requirements.txt
├── .env.example
├── config.yaml.example
├── .gitignore
├── jira_scan.py           # Main CLI entry point
├── src/
│   ├── __init__.py
│   ├── config.py             # Config loading
│   ├── jira_client.py        # API wrapper
│   ├── fetcher.py            # Parallel data fetching
│   ├── builder.py            # Relationship matching
│   └── output.py             # JSON generation
├── data/                     # Output directory (gitignored)
└── docs/
    └── plans/                # Design docs
```

### Dependencies

```
requests>=2.31.0              # HTTP client
python-dotenv>=1.0.0          # Environment variables
pyyaml>=6.0                   # Config parsing
click>=8.1.0                  # CLI framework
```

### Key Technical Decisions

- **Thread pool size:** 10 concurrent requests (balance speed vs rate limits)
- **Pagination:** Handle Jira's max 100 results per request
- **Caching:** None (always fetch fresh data)
- **Python version:** 3.9+ (for type hints, modern syntax)
- **Jira API:** REST API v3 (Cloud)

### Testing Considerations

- Mock Jira API responses for unit tests
- Sample config files for integration tests
- Real API testing with test credentials (optional)

## README Requirements

The README.md must include clear setup instructions:

1. **Prerequisites:** Python 3.9+, Jira Cloud access
2. **Setup Steps:**
   - Copy `config.yaml.example` to `config.yaml`
   - Update with your Jira instance URL and project keys
   - Copy `.env.example` to `.env`
   - Add your Jira email and API token
   - Install dependencies: `pip install -r requirements.txt`
3. **Getting API Token:** Link to Atlassian documentation
4. **Finding Custom Field IDs:** Use `python jira_scan.py list-fields`
5. **Usage Examples:** Basic extract command and common options
6. **Troubleshooting:** Common errors and solutions

## Next Steps

1. Create implementation plan using writing-plans skill
2. Implement core components
3. Add comprehensive error handling
4. Write README with setup instructions
5. Create example config files
6. Test with real Jira instance
