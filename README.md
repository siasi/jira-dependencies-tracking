# Jira Dependencies Tracking

A Python CLI tool to extract Jira initiatives and related epics for tracking dependencies across teams.

## Overview

This tool extracts data from Jira Cloud instances to help track:
- Initiatives from a dedicated project
- Epics linked to those initiatives across multiple team projects
- Custom field values (e.g., RAG status)
- Initiative-Epic relationships

## Prerequisites

- Python 3.9 or higher
- Jira Cloud instance access
- Jira API token with read permissions

## Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

   Or install in development mode:
   ```bash
   pip install -e .
   ```

## Configuration

### 1. Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-api-token-here
```

**Getting a Jira API Token:**
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a label and copy the token

### 2. Configuration File

Copy `config.yaml.example` to `config.yaml` and customize:

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml`:
```yaml
jira:
  instance: "your-company.atlassian.net"

projects:
  initiatives: "INIT"  # Your initiatives project key
  teams:
    - "TEAM1"
    - "TEAM2"
    # Add all team project keys

custom_fields:
  rag_status: "customfield_XXXXX"  # Find your custom field IDs

output:
  directory: "./data"
  filename_pattern: "jira_extract_{timestamp}.json"
```

**Finding Custom Field IDs:**
1. Open a Jira issue in your browser
2. Add `.json` to the URL (e.g., `https://company.atlassian.net/browse/INIT-123.json`)
3. Search for your custom field name in the JSON
4. Note the `customfield_XXXXX` ID

## Usage

Run the extraction:

```bash
python -m jira_extract
```

Or if installed:

```bash
jira-extract
```

The tool will:
1. Load configuration from `config.yaml` and `.env`
2. Authenticate with Jira
3. Extract all initiatives from the specified project
4. For each initiative, find linked epics across team projects
5. Save the data to a timestamped JSON file

## Output Format

The tool generates a JSON file with the following structure:

```json
{
  "extracted_at": "2024-01-15T10:30:00Z",
  "initiatives": [
    {
      "key": "INIT-123",
      "summary": "Initiative Title",
      "status": "In Progress",
      "custom_fields": {
        "rag_status": "Green"
      },
      "epics": [
        {
          "key": "TEAM1-456",
          "summary": "Epic Title",
          "status": "To Do",
          "project": "TEAM1"
        }
      ]
    }
  ]
}
```

## Project Structure

```
jira-dependencies-tracking/
├── src/
│   ├── __init__.py
│   ├── config.py       # Configuration loading
│   ├── jira_client.py  # Jira API client
│   └── extractor.py    # Main extraction logic
├── jira_extract.py     # CLI entry point
├── requirements.txt
├── setup.py
├── config.yaml.example
├── .env.example
└── README.md
```

## Development

To contribute or modify the tool:

1. Install in development mode:
   ```bash
   pip install -e .
   ```

2. Make your changes

3. Test manually:
   ```bash
   python -m jira_extract
   ```

## Troubleshooting

**Authentication Errors:**
- Verify your email and API token in `.env`
- Ensure the API token has not expired

**Custom Field Not Found:**
- Check the custom field ID in `config.yaml`
- Verify the field exists in your Jira instance

**Missing Epics:**
- Ensure epics are properly linked to initiatives using Jira's issue linking
- Verify your API token has access to all specified team projects

## License

MIT
