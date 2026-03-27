# Slack Integration Design

This document captures the brainstorming and design decisions for adding Slack notifications to the initiative validation system.

## Goal

Send Slack DMs to engineering managers with actionable items from the initiative validation report, enabling them to quickly see what requires their attention.

## Design Decisions

### 1. Action Types to Notify

The following action types will be included in manager notifications:

1. **Missing dependencies** - Teams need to create epics for cross-team initiatives
2. **Missing RAG status** - Teams need to set RAG status on their epics
3. **Missing assignee** - Initiatives need an assignee before they can be planned
4. **Ready to move to PLANNED** - Proposed initiatives that meet all criteria and can be moved forward

### 2. Delivery Method

**Decision: Direct Messages (DMs)**

Managers will receive individual DMs containing only their team's action items. This provides:
- Privacy (managers only see their own team's items)
- Direct notification (Slack highlights DMs)
- Focused action lists (no clutter from other teams)

### 3. Message Format

**Decision: Simple text format**

Use plain text messages instead of Slack Block Kit for simplicity:
- Easier to compose and test
- Still readable and actionable
- Lower maintenance overhead
- Can be enhanced later if needed

Example message format:
```
Hello! Here are the action items for your team from the latest initiative validation:

**Missing Dependencies (2)**
• INIT-1234: "Project Alpha" - Create epic
• INIT-5678: "Project Beta" - Create epic

**Missing RAG Status (1)**
• CBPPE-456: "Feature X" - Set RAG status

**Ready to PLANNED (1)**
• INIT-9012: "Project Gamma" - All criteria met, can move to PLANNED
```

### 4. Architecture

**Decision: Separate script**

Create a new script `send_manager_notifications.py` that:
- Imports and reuses validation logic from `validate_initiative_status.py`
- Extracts action items from `ValidationResult`
- Groups actions by manager
- Sends Slack DMs to each manager
- Runs independently (can be scheduled separately)

Benefits:
- Separation of concerns (validation vs notification)
- Can run validation without sending Slack messages
- Can test Slack integration independently
- Different scheduling requirements (validation might run more frequently than notifications)

### 5. Configuration

Extend `team_mappings.yaml` with Slack-specific fields:

```yaml
# Existing structure
team_managers:
  "CBPPE": "@Manager B "
  # ... other teams

# New structure to add
slack_config:
  enabled: true  # Master switch for Slack notifications

  # Map project keys to Slack user IDs (for DMs)
  manager_slack_ids:
    "CBPPE": "U01ABC123"
    "CONSOLE": "U02DEF456"
    "CBNK": "U03GHI789"
    # ... other teams
```

Alternatively, map by email:
```yaml
slack_config:
  # Map project keys to email addresses (Slack can look up user by email)
  manager_emails:
    "CBPPE": "ariel@company.com"
    "CONSOLE": "karina@company.com"
    # ... other teams
```

### 6. Testing and Safety

**Decision: Implement dry-run mode**

Add `--dry-run` flag that:
- Performs all logic (validation, grouping, message composition)
- Prints messages to console instead of sending to Slack
- Shows exactly what would be sent to whom
- Safe for development and testing

Example usage:
```bash
# Test without sending
python send_manager_notifications.py --dry-run

# Send actual messages
python send_manager_notifications.py

# Verbose output with dry-run
python send_manager_notifications.py --dry-run --verbose
```

## Slack App Setup

### Required Permissions (OAuth Scopes)

The Slack app needs the following bot token scopes:
- `chat:write` - Send messages as the bot
- `im:write` - Open and write to direct message channels
- `users:read` - Look up user information
- `users:read.email` - Look up users by email address (if using email mapping)

### Installation Methods

#### Option 1: Create via Manifest File

Use the provided `slack-manifest.yaml`:

```yaml
display_information:
  name: Initiative Validator Bot
  description: Sends initiative validation notifications to engineering managers
  background_color: "#2c2d30"
features:
  bot_user:
    display_name: Initiative Validator
    always_online: false
oauth_config:
  scopes:
    bot:
      - chat:write
      - im:write
      - users:read
      - users:read.email
settings:
  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false
```

Steps:
1. Go to https://api.slack.com/apps
2. Click "Create New App"
3. Choose "From an app manifest"
4. Select your workspace
5. Paste the manifest YAML
6. Review and create

#### Option 2: Manual UI Configuration

1. Create app at https://api.slack.com/apps
2. Navigate to "OAuth & Permissions"
3. Add bot token scopes: `chat:write`, `im:write`, `users:read`, `users:read.email`
4. Install app to workspace
5. Copy bot token (starts with `xoxb-`)

### Admin Approval Process

If your Slack workspace requires admin approval for app installations:

1. **Request approval through Slack UI** - When you try to install, Slack will show an "Request Approval" button

2. **Information to provide to admin**:
   - **App name**: Initiative Validator Bot
   - **Purpose**: Sends DMs to engineering managers with action items from initiative validation reports
   - **Permissions needed**:
     - `chat:write` - To send messages
     - `im:write` - To send DMs
     - `users:read` - To look up manager user accounts
     - `users:read.email` - To find users by email address
   - **Data access**: The bot will only access:
     - Manager email addresses (to send DMs)
     - No channel messages
     - No file access
     - No sensitive workspace data
   - **Security**: Bot token will be stored securely in environment variables, not in code

3. **Alternative approaches while waiting**:
   - Ask admin to install the app directly
   - Request app installation permissions for your account
   - Add admin as a collaborator on the app
   - Develop mock functionality without Slack access (see below)

### Environment Variables

After installation, configure:

```bash
export SLACK_BOT_TOKEN="xoxb-your-token-here"
```

For testing, also set your own user ID:
```bash
export SLACK_USER_ID="U01ABC123"  # Your Slack user ID (for testing)
```

## MVP Test Script

Before implementing full functionality, test Slack connectivity with `test_slack.py`:

```python
#!/usr/bin/env python3
"""
Minimal Slack integration test - sends a test DM to yourself.

Usage:
    export SLACK_BOT_TOKEN="xoxb-your-token-here"
    export SLACK_USER_ID="U01ABC123"
    python test_slack.py
"""

import os
import sys
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

def send_test_message():
    """Send a simple test message to verify Slack integration works."""
    bot_token = os.environ.get('SLACK_BOT_TOKEN')
    user_id = os.environ.get('SLACK_USER_ID')

    # Validate environment variables
    if not bot_token:
        print("Error: SLACK_BOT_TOKEN environment variable not set")
        print("Export your bot token: export SLACK_BOT_TOKEN='xoxb-...'")
        sys.exit(1)

    if not user_id:
        print("Error: SLACK_USER_ID environment variable not set")
        print("Export your user ID: export SLACK_USER_ID='U01ABC123'")
        sys.exit(1)

    client = WebClient(token=bot_token)

    try:
        # Test 1: Verify bot token works
        print("Testing authentication...")
        auth_response = client.auth_test()
        print(f"✓ Authenticated as: {auth_response['user']}")

        # Test 2: Open DM channel
        print("Opening DM channel...")
        dm_response = client.conversations_open(users=user_id)
        channel_id = dm_response["channel"]["id"]
        print(f"✓ DM channel opened: {channel_id}")

        # Test 3: Send test message
        print("Sending test message...")
        test_message = """Hello! This is a test message from the Initiative Validator Bot.

If you're seeing this, the Slack integration is working correctly! 🎉"""

        client.chat_postMessage(channel=channel_id, text=test_message)
        print("✓ Message sent successfully!")
        print("\nSUCCESS! Check your Slack DMs")

    except SlackApiError as e:
        print(f"✗ Slack API Error: {e.response['error']}")
        if e.response['error'] == 'invalid_auth':
            print("  → Check your SLACK_BOT_TOKEN")
        elif e.response['error'] == 'user_not_found':
            print("  → Check your SLACK_USER_ID")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    send_test_message()
```

To run the test:
```bash
pip install slack-sdk
export SLACK_BOT_TOKEN="xoxb-your-token-here"
export SLACK_USER_ID="U01ABC123"
python test_slack.py
```

## Development Without Slack Access

While waiting for admin approval, you can:

1. **Build the action extraction logic** - Extract and group action items from `ValidationResult` without Slack
2. **Create mock sender** - Simulate message sending by printing to console
3. **Test message formatting** - Ensure messages are clear and actionable
4. **Write unit tests** - Test grouping and filtering logic independently

Example mock implementation:
```python
def send_manager_notification(manager_name, slack_id, actions, dry_run=True):
    """Send notification to manager (or print if dry_run)."""
    message = compose_message(manager_name, actions)

    if dry_run:
        print(f"\n{'='*60}")
        print(f"Would send to: {manager_name} ({slack_id})")
        print(f"{'='*60}")
        print(message)
    else:
        # Actual Slack sending code
        client.chat_postMessage(channel=slack_id, text=message)
```

## Implementation Plan

### Phase 1: Core Extraction Logic (No Slack needed)
1. Create `send_manager_notifications.py` skeleton
2. Implement action extraction from `ValidationResult`
3. Group actions by team/manager
4. Implement message composition
5. Add dry-run mode that prints to console
6. Write unit tests for grouping and formatting

### Phase 2: Slack Integration (After admin approval)
1. Implement Slack client initialization
2. Add user lookup logic (by ID or email)
3. Implement DM channel opening
4. Implement message sending
5. Add error handling for Slack API errors
6. Test with real Slack workspace

### Phase 3: Production Readiness
1. Add logging
2. Add retry logic for transient failures
3. Add rate limiting (Slack has API limits)
4. Document configuration in README
5. Create example configuration files
6. Add monitoring/alerting hooks

## Future Enhancements

Consider for later iterations:

1. **Rich formatting with Block Kit** - More structured, interactive messages
2. **Thread replies** - Send updates as thread replies to original message
3. **Interactive buttons** - "Mark as done", "Snooze", etc.
4. **Weekly digests** - Summary of all action items instead of individual notifications
5. **Slack channels** - Option to post to team channels instead of/in addition to DMs
6. **Configurable frequency** - Daily, weekly, or on-demand notifications
7. **Historical tracking** - Track which actions have been resolved vs. still open
8. **Escalation** - Notify senior leadership if actions remain unresolved for X days

## Questions to Resolve

Before full implementation:

1. **Notification frequency** - How often should managers receive these DMs?
   - Daily? (might be noisy)
   - Weekly digest? (might delay action)
   - On-demand only? (requires manual trigger)

2. **User mapping method** - How to map project keys to Slack users?
   - Store Slack user IDs in config? (requires one-time lookup)
   - Store email addresses? (requires `users:read.email` permission)
   - Manual mapping initially, then build UI for managers to self-register?

3. **Message threading** - Should subsequent notifications be:
   - New messages each time?
   - Replies to previous message thread?
   - Update/replace previous message?

4. **Error handling** - What if a manager can't be found in Slack?
   - Skip and log error?
   - Send to fallback channel?
   - Email notification instead?

## Resources

- Slack API documentation: https://api.slack.com/
- Slack SDK for Python: https://github.com/slackapi/python-slack-sdk
- Slack App Manifest reference: https://api.slack.com/reference/manifests
- Slack OAuth scopes: https://api.slack.com/scopes
