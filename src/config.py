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

    def validate(self) -> None:
        """Validate configuration.

        Raises:
            ConfigError: If configuration is invalid
        """
        # Check if filters.quarter is set but custom_fields.quarter is missing
        if self.filters and self.filters.quarter:
            if not self.custom_fields.quarter:
                raise ConfigError(
                    "Quarter filtering requires custom_fields.quarter to be defined"
                )


def load_config(config_path: str = "config.yaml") -> Config:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file

    Returns:
        Config object

    Raises:
        ConfigError: If config is invalid
    """
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {config_path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML: {e}")

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
            ),
            projects=ProjectsConfig(
                initiatives=data["projects"]["initiatives"],
                teams=data["projects"]["teams"],
            ),
            custom_fields=CustomFields(
                rag_status=data["custom_fields"]["rag_status"],
                quarter=data["custom_fields"].get("quarter"),  # Optional
            ),
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
