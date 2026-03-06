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
