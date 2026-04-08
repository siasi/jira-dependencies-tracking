"""Configuration utilities for accessing environment and config file settings."""

import os
from pathlib import Path
import yaml


def get_jira_base_url() -> str:
    """Get Jira base URL from config or environment variable.

    Checks in order:
    1. JIRA_BASE_URL environment variable
    2. config/jira_config.yaml file
    3. Safe fallback placeholder

    Returns:
        Jira base URL (e.g., 'https://company.atlassian.net')
    """
    # Try environment variable first
    if env_url := os.getenv('JIRA_BASE_URL'):
        return env_url.rstrip('/')

    # Fall back to config file
    config_file = Path(__file__).parent.parent / 'config' / 'jira_config.yaml'
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if instance := config.get('jira', {}).get('instance'):
                    # Instance may have trailing slash, normalize it
                    base = instance.rstrip('/')
                    # Add https:// if not present
                    if not base.startswith('http'):
                        base = f'https://{base}'
                    return base
        except Exception:
            pass

    # Fallback to generic placeholder for safety
    return 'https://your-company.atlassian.net'
