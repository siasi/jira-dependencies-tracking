# Scripts

Utility scripts for managing Jira dependencies tracking.

## fetch_notion_users.py

Fetches Notion user IDs to configure manager tagging in reports.

### Purpose

The validation reports can tag engineering managers in Notion for action items. This requires Notion user IDs (not just names or email addresses). This script helps you get those IDs.

### Prerequisites

1. **Create a Notion integration:**
   - Go to https://www.notion.so/my-integrations
   - Click "+ New integration"
   - Give it a name (e.g., "User ID Fetcher")
   - Select your workspace
   - Copy the "Internal Integration Token"

2. **Share workspace with integration:**
   - In Notion: Settings & Members → Connections
   - Find your integration and connect it to your workspace

### Usage

```bash
# Option 1: Set token as environment variable
export NOTION_API_TOKEN="your-integration-token-here"
python scripts/fetch_notion_users.py

# Option 2: Enter token when prompted
python scripts/fetch_notion_users.py
# (script will ask for token)
```

### Output

The script will:

1. **List all users** in your Notion workspace with their:
   - Name
   - Email
   - User ID

2. **Generate a template** for the `team_managers` section:
   ```yaml
   team_managers:
     "CBNK": "ed12a34b-5678-90cd-ef12-3456789abcde"
     "CONSOLE": "f2345678-90ab-cdef-1234-56789abcdef0"
     ...
   ```

3. **Optionally save** the template to `team_managers_template.yaml`

### Next Steps

After running the script:

1. Open the generated `team_managers_template.yaml`
2. Replace `REPLACE_WITH_USER_ID` with actual user IDs
3. Match each project key to the appropriate manager
4. Copy the `team_managers` section into `team_mappings.yaml`
5. Run validation script - managers will now be properly tagged!

### Example

```bash
$ python scripts/fetch_notion_users.py

================================================================================
NOTION USER ID FETCHER
================================================================================

Enter your Notion integration token: secret_abc123...

⏳ Fetching users from Notion...

================================================================================
NOTION USERS
================================================================================

Found 8 people and 1 bots

PEOPLE:
--------------------------------------------------------------------------------
  Name:  John Doe
  Email: john.doe@company.com
  ID:    ed12a34b-5678-90cd-ef12-3456789abcde

  Name:  Jane Smith
  Email: jane.smith@company.com
  ID:    f2345678-90ab-cdef-1234-56789abcdef0

  ...

================================================================================
TEAM_MANAGERS CONFIGURATION
================================================================================

Found 9 project keys in team_mappings.yaml

team_managers:
  # Available users:
  # John Doe (john.doe@company.com): "ed12a34b-5678-90cd-ef12-3456789abcde"
  # Jane Smith (jane.smith@company.com): "f2345678-90ab-cdef-1234-56789abcdef0"

  "CBNK": "REPLACE_WITH_USER_ID"  # Replace with actual manager's ID
  "CONSOLE": "REPLACE_WITH_USER_ID"
  ...

Save team_managers template to team_managers_template.yaml? [y/N]: y

✅ Saved to team_managers_template.yaml
   Edit this file and merge into team_mappings.yaml
```

### Troubleshooting

**Error: HTTP Error 401**
- Your integration token is invalid or expired
- Create a new integration at https://www.notion.so/my-integrations

**Error: HTTP Error 403**
- Integration doesn't have access to your workspace
- Go to Settings & Members → Connections and share workspace with integration

**No users found**
- Integration might not have proper permissions
- Try sharing a specific page with the integration

**PyYAML warning**
- The script works without PyYAML, but can't load existing project keys
- Install with: `pip install pyyaml`
