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
  initiatives:
    rag_status: "customfield_10050"
output:
  directory: "./data"
  filename_pattern: "jira_{timestamp}.json"
""")

    config = load_config(str(config_file))

    assert config.jira.instance == "test.atlassian.net"
    assert config.projects.initiatives == "INIT"
    assert "TEAM1" in config.projects.teams
    assert config.custom_fields["rag_status"] == "customfield_10050"
    assert config.output.directory == "./data"
    assert config.output.filename_pattern == "jira_{timestamp}.json"


def test_load_config_missing_required_field(tmp_path):
    """Test error when required field is missing."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
jira:
  instance: "test.atlassian.net"
projects:
  initiatives: "INIT"
  teams: []
""")

    with pytest.raises(ConfigError, match="Missing required config key"):
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




def test_validate_filters_requires_quarter_field():
    """Test that filters.quarter requires custom_fields['quarter']."""
    from src.config import Config, JiraConfig, ProjectsConfig, Filters, OutputConfig, ConfigError

    # Should raise error when filters.quarter is set but custom_fields['quarter'] is not
    with pytest.raises(ConfigError, match="Quarter filtering requires custom_fields.initiatives.quarter"):
        config = Config(
            jira=JiraConfig(instance="test.atlassian.net", email="test@example.com", api_token="test-token"),
            projects=ProjectsConfig(initiatives="INIT", teams=["TEAM1"]),
            custom_fields={"rag_status": "customfield_12111"},  # No quarter field
            output=OutputConfig(directory="./data", filename_pattern="test_{timestamp}.json"),
            filters=Filters(quarter="25 Q1")  # But filter is set
        )
        config.validate()


def test_validate_filters_with_quarter_field_ok():
    """Test that filters work when quarter field is defined."""
    from src.config import Config, JiraConfig, ProjectsConfig, Filters, OutputConfig

    config = Config(
        jira=JiraConfig(instance="test.atlassian.net", email="test@example.com", api_token="test-token"),
        projects=ProjectsConfig(initiatives="INIT", teams=["TEAM1"]),
        custom_fields={"rag_status": "customfield_12111", "quarter": "customfield_12108"},
        output=OutputConfig(directory="./data", filename_pattern="test_{timestamp}.json"),
        filters=Filters(quarter="25 Q1")
    )
    config.validate()  # Should not raise


def test_load_config_with_filters(tmp_path):
    """Test loading config with filters section."""
    from src.config import load_config

    config_content = """
jira:
  instance: "test.atlassian.net"

projects:
  initiatives: "INIT"
  teams:
    - "TEAM1"
    - "TEAM2"

custom_fields:
  initiatives:
    rag_status: "customfield_12111"
    quarter: "customfield_12108"

filters:
  quarter: "25 Q1"

output:
  directory: "./data"
  filename_pattern: "test_{timestamp}.json"
"""

    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)

    config = load_config(str(config_file))

    assert config.filters is not None
    assert config.filters.quarter == "25 Q1"
    assert config.custom_fields["quarter"] == "customfield_12108"


def test_load_config_without_filters(tmp_path):
    """Test loading config without filters section (backward compatibility)."""
    from src.config import load_config

    config_content = """
jira:
  instance: "test.atlassian.net"

projects:
  initiatives: "INIT"
  teams:
    - "TEAM1"

custom_fields:
  initiatives:
    rag_status: "customfield_12111"

output:
  directory: "./data"
  filename_pattern: "test_{timestamp}.json"
"""

    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)

    config = load_config(str(config_file))

    assert config.filters is None


def test_load_config_with_custom_fields_dict(tmp_path):
    """Test loading config with custom_fields.initiatives as dict."""
    config_content = """
jira:
  instance: "test.atlassian.net"

projects:
  initiatives: "INIT"
  teams:
    - "TEAM1"

custom_fields:
  initiatives:
    rag_status: "customfield_12111"
    quarter: "customfield_12108"
    objective: "customfield_12101"

output:
  directory: "./data"
  filename_pattern: "test_{timestamp}.json"
"""

    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)

    config = load_config(str(config_file))

    assert isinstance(config.custom_fields, dict)
    assert config.custom_fields["rag_status"] == "customfield_12111"
    assert config.custom_fields["quarter"] == "customfield_12108"
    assert config.custom_fields["objective"] == "customfield_12101"


def test_load_config_empty_custom_fields(tmp_path):
    """Test loading config with empty custom_fields.initiatives section."""
    config_content = """
jira:
  instance: "test.atlassian.net"

projects:
  initiatives: "INIT"
  teams:
    - "TEAM1"

custom_fields:
  initiatives: {}

output:
  directory: "./data"
  filename_pattern: "test_{timestamp}.json"
"""

    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)

    config = load_config(str(config_file))

    assert isinstance(config.custom_fields, dict)
    assert len(config.custom_fields) == 0


def test_load_config_missing_custom_fields(tmp_path):
    """Test loading config with missing custom_fields section defaults to empty dict."""
    config_content = """
jira:
  instance: "test.atlassian.net"

projects:
  initiatives: "INIT"
  teams:
    - "TEAM1"

output:
  directory: "./data"
  filename_pattern: "test_{timestamp}.json"
"""

    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)

    config = load_config(str(config_file))

    assert isinstance(config.custom_fields, dict)
    assert len(config.custom_fields) == 0
