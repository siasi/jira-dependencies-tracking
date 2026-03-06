# tests/test_config.py
import os
import pytest
from pathlib import Path
from src.config import load_config, ConfigError


def test_load_config_success(tmp_path):
    """Test loading valid configuration."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
jira:
  instance: "test.atlassian.net"
projects:
  initiatives: "INIT"
  teams:
    - "TEAM1"
custom_fields:
  rag_status: "customfield_10050"
output:
  directory: "./data"
  filename_pattern: "jira_{timestamp}.json"
""")

    os.environ["JIRA_EMAIL"] = "test@example.com"
    os.environ["JIRA_API_TOKEN"] = "test-token"

    config = load_config(str(config_file))

    assert config["jira"]["instance"] == "test.atlassian.net"
    assert config["jira"]["email"] == "test@example.com"
    assert config["jira"]["api_token"] == "test-token"
    assert config["projects"]["initiatives"] == "INIT"
    assert "TEAM1" in config["projects"]["teams"]


def test_load_config_missing_env_vars(tmp_path):
    """Test error when environment variables missing."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
jira:
  instance: "test.atlassian.net"
projects:
  initiatives: "INIT"
  teams: []
""")

    # Clear env vars
    os.environ.pop("JIRA_EMAIL", None)
    os.environ.pop("JIRA_API_TOKEN", None)

    with pytest.raises(ConfigError, match="JIRA_EMAIL"):
        load_config(str(config_file))


def test_load_config_missing_file():
    """Test error when config file doesn't exist."""
    with pytest.raises(ConfigError, match="not found"):
        load_config("/nonexistent/config.yaml")


def test_filters_dataclass():
    """Test Filters dataclass."""
    from src.config import Filters

    filters = Filters(quarter="25 Q1")
    assert filters.quarter == "25 Q1"

    # Test optional
    filters_empty = Filters(quarter=None)
    assert filters_empty.quarter is None


def test_custom_fields_with_quarter():
    """Test CustomFields with quarter field."""
    from src.config import CustomFields

    fields = CustomFields(
        rag_status="customfield_12111",
        quarter="customfield_12108"
    )
    assert fields.rag_status == "customfield_12111"
    assert fields.quarter == "customfield_12108"

    # Test optional
    fields_no_quarter = CustomFields(rag_status="customfield_12111")
    assert fields_no_quarter.quarter is None


def test_config_with_filters():
    """Test Config with filters section."""
    from src.config import Config, JiraConfig, ProjectsConfig, CustomFields, Filters, OutputConfig

    config = Config(
        jira=JiraConfig(instance="test.atlassian.net"),
        projects=ProjectsConfig(initiatives="INIT", teams=["TEAM1"]),
        custom_fields=CustomFields(rag_status="customfield_12111", quarter="customfield_12108"),
        output=OutputConfig(directory="./data", filename_pattern="test_{timestamp}.json"),
        filters=Filters(quarter="25 Q1")
    )

    assert config.filters is not None
    assert config.filters.quarter == "25 Q1"

    # Test optional
    config_no_filters = Config(
        jira=JiraConfig(instance="test.atlassian.net"),
        projects=ProjectsConfig(initiatives="INIT", teams=["TEAM1"]),
        custom_fields=CustomFields(rag_status="customfield_12111"),
        output=OutputConfig(directory="./data", filename_pattern="test_{timestamp}.json")
    )
    assert config_no_filters.filters is None
