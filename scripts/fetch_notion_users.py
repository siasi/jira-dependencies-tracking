#!/usr/bin/env python3
"""
Fetch Notion user IDs and generate team_managers mapping.

This script helps you get Notion user IDs for all members in your workspace
and creates the team_managers section for team_mappings.yaml.

Usage:
    python scripts/fetch_notion_users.py

Requirements:
    - Notion integration token (get from https://www.notion.so/my-integrations)
    - Integration must be shared with your workspace
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List
import urllib.request
import urllib.error


def fetch_notion_users(api_token: str) -> List[Dict]:
    """Fetch all users from Notion workspace.

    Args:
        api_token: Notion integration token

    Returns:
        List of user dictionaries with id, name, email
    """
    url = "https://api.notion.com/v1/users"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            return data.get('results', [])
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"❌ HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        print(f"   Response: {error_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"❌ URL Error: {e.reason}", file=sys.stderr)
        sys.exit(1)


def display_users(users: List[Dict]) -> None:
    """Display users in a readable format.

    Args:
        users: List of user dictionaries
    """
    print("\n" + "="*80)
    print("NOTION USERS")
    print("="*80 + "\n")

    people = [u for u in users if u.get('type') == 'person']
    bots = [u for u in users if u.get('type') == 'bot']

    print(f"Found {len(people)} people and {len(bots)} bots\n")

    if people:
        print("PEOPLE:")
        print("-" * 80)
        for user in people:
            user_id = user.get('id', 'N/A')
            name = user.get('name', 'N/A')
            email = user.get('person', {}).get('email', 'No email')
            print(f"  Name:  {name}")
            print(f"  Email: {email}")
            print(f"  ID:    {user_id}")
            print()

    if bots:
        print("\nBOTS:")
        print("-" * 80)
        for bot in bots:
            bot_id = bot.get('id', 'N/A')
            name = bot.get('name', 'N/A')
            print(f"  Name: {name}")
            print(f"  ID:   {bot_id}")
            print()


def generate_team_managers_yaml(users: List[Dict], project_keys: List[str]) -> str:
    """Generate team_managers YAML section.

    Args:
        users: List of user dictionaries
        project_keys: List of project keys from team_mappings

    Returns:
        YAML formatted string for team_managers section
    """
    people = [u for u in users if u.get('type') == 'person']

    lines = [
        "# Engineering manager Notion user IDs for team notifications",
        "# Maps project keys to Notion user IDs (for @mentions in markdown)",
        "#",
        "# Format:",
        "#   \"PROJECT_KEY\": \"notion-user-id\"",
        "#",
        "# These IDs are used to tag managers in markdown reports for action items.",
        "team_managers:"
    ]

    # Show available users as comments
    lines.append("  # Available users:")
    for user in people:
        name = user.get('name', 'N/A')
        email = user.get('person', {}).get('email', 'No email')
        user_id = user.get('id', 'N/A')
        lines.append(f"  # {name} ({email}): \"{user_id}\"")

    lines.append("")
    lines.append("  # Map your project keys to manager IDs:")

    # Generate template mappings for each project key
    for key in project_keys:
        lines.append(f'  "{key}": "REPLACE_WITH_USER_ID"  # Replace with actual manager\'s ID from above')

    return "\n".join(lines)


def load_existing_project_keys() -> List[str]:
    """Load project keys from existing team_mappings.yaml.

    Returns:
        List of project keys
    """
    mappings_file = Path(__file__).parent.parent / 'team_mappings.yaml'

    if not mappings_file.exists():
        return []

    try:
        import yaml
        with open(mappings_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            team_mappings = data.get('team_mappings', {})
            # Get all project keys (the values in team_mappings)
            return list(set(team_mappings.values()))
    except ImportError:
        print("⚠️  PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
        return []
    except Exception as e:
        print(f"⚠️  Could not load team_mappings.yaml: {e}", file=sys.stderr)
        return []


def main():
    """Main function."""
    print("=" * 80)
    print("NOTION USER ID FETCHER")
    print("=" * 80)
    print()
    print("This script fetches Notion user IDs to configure manager tagging.")
    print()
    print("Prerequisites:")
    print("  1. Create a Notion integration at https://www.notion.so/my-integrations")
    print("  2. Share your workspace with the integration")
    print("  3. Copy the integration token")
    print()

    # Get API token
    api_token = os.environ.get('NOTION_API_TOKEN')

    if not api_token:
        print("Enter your Notion integration token:")
        print("(or set NOTION_API_TOKEN environment variable)")
        print()
        api_token = input("Token: ").strip()

    if not api_token:
        print("❌ No token provided. Exiting.", file=sys.stderr)
        sys.exit(1)

    # Fetch users
    print("\n⏳ Fetching users from Notion...\n")
    users = fetch_notion_users(api_token)

    # Display users
    display_users(users)

    # Generate team_managers YAML
    print("\n" + "="*80)
    print("TEAM_MANAGERS CONFIGURATION")
    print("="*80 + "\n")

    project_keys = load_existing_project_keys()

    if project_keys:
        print(f"Found {len(project_keys)} project keys in team_mappings.yaml")
        print()
        yaml_output = generate_team_managers_yaml(users, sorted(project_keys))
        print(yaml_output)
        print()
        print("-" * 80)
        print()
        print("📋 NEXT STEPS:")
        print()
        print("1. Copy the team_managers section above")
        print("2. Open team_mappings.yaml")
        print("3. Replace REPLACE_WITH_USER_ID with actual user IDs from the list")
        print("4. Save the file")
        print()
        print("💡 TIP: Match each project key to the appropriate manager's ID")
        print()

        # Offer to save to file
        save = input("Save team_managers template to team_managers_template.yaml? [y/N]: ").strip().lower()
        if save == 'y':
            output_file = Path(__file__).parent.parent / 'team_managers_template.yaml'
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(yaml_output)
            print(f"\n✅ Saved to {output_file}")
            print(f"   Edit this file and merge into team_mappings.yaml")
    else:
        print("⚠️  No project keys found in team_mappings.yaml")
        print("    Create team_mappings.yaml first, then run this script again")

    print()


if __name__ == '__main__':
    main()
