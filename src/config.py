# src/config.py
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import yaml
from dotenv import load_dotenv


class ConfigError(Exception):
    """Configuration error."""
    pass


@dataclass
class Filters:
    """Filtering configuration."""
    quarter: Optional[str] = None


@dataclass
class CustomFields:
    """Custom field IDs."""
    rag_status: str
    quarter: Optional[str] = None


@dataclass
class JiraConfig:
    """Jira connection configuration."""
    instance: str


@dataclass
class ProjectsConfig:
    """Projects configuration."""
    initiatives: str
    teams: List[str]


@dataclass
class OutputConfig:
    """Output configuration."""
    directory: str
    filename_pattern: str


@dataclass
class Config:
    """Main configuration."""
    jira: JiraConfig
    projects: ProjectsConfig
    custom_fields: CustomFields
    output: OutputConfig
    filters: Optional[Filters] = None


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file and environment variables.

    Args:
        config_path: Path to config.yaml file

    Returns:
        Complete configuration dictionary

    Raises:
        ConfigError: If config is invalid or required values missing
    """
    # Load environment variables from .env if present
    load_dotenv()

    # Check config file exists
    config_file = Path(config_path)
    if not config_file.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    # Load YAML config
    with open(config_file) as f:
        config = yaml.safe_load(f)

    # Load credentials from environment
    email = os.environ.get("JIRA_EMAIL")
    api_token = os.environ.get("JIRA_API_TOKEN")

    if not email:
        raise ConfigError(
            "JIRA_EMAIL environment variable required. "
            "Create .env file or export JIRA_EMAIL=your-email@company.com"
        )

    if not api_token:
        raise ConfigError(
            "JIRA_API_TOKEN environment variable required. "
            "Get token from: https://id.atlassian.com/manage-profile/security/api-tokens"
        )

    # Add credentials to config
    config["jira"]["email"] = email
    config["jira"]["api_token"] = api_token

    return config
