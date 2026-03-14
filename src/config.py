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
class JiraConfig:
    """Jira connection configuration."""
    instance: str
    email: str
    api_token: str


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
    custom_fields: Dict[str, str]
    output: OutputConfig
    filters: Optional[Filters] = None

    def validate(self) -> None:
        """Validate configuration.

        Raises:
            ConfigError: If configuration is invalid
        """
        # Check if filters.quarter is set but quarter field is missing
        if self.filters and self.filters.quarter:
            if "quarter" not in self.custom_fields:
                raise ConfigError(
                    "Quarter filtering requires custom_fields.initiatives.quarter to be defined"
                )


def load_config(config_path: str = "config.yaml") -> Config:
    """Load configuration from YAML file and environment variables.

    Args:
        config_path: Path to config file

    Returns:
        Config object

    Raises:
        ConfigError: If config is invalid
    """
    # Load environment variables from .env if present
    load_dotenv()

    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {config_path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML: {e}")

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

    try:
        # Parse filters section (optional)
        filters = None
        if "filters" in data:
            filters = Filters(
                quarter=data["filters"].get("quarter")
            )

        config = Config(
            jira=JiraConfig(
                instance=data["jira"]["instance"],
                email=email,
                api_token=api_token,
            ),
            projects=ProjectsConfig(
                initiatives=data["projects"]["initiatives"],
                teams=data["projects"]["teams"],
            ),
            custom_fields=data.get("custom_fields", {}).get("initiatives", {}),
            output=OutputConfig(
                directory=data["output"]["directory"],
                filename_pattern=data["output"]["filename_pattern"],
            ),
            filters=filters,
        )

        # Validate configuration
        config.validate()

        return config

    except KeyError as e:
        raise ConfigError(f"Missing required config key: {e}")
