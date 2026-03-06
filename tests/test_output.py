# tests/test_output.py
import json
from pathlib import Path
from datetime import datetime
from src.output import OutputGenerator, ExtractionStatus


def test_generate_output_complete_success(tmp_path):
    """Test generating output with complete successful extraction."""
    data = {
        "initiatives": [
            {
                "key": "INIT-1",
                "summary": "Test",
                "contributing_teams": [],
            }
        ],
        "orphaned_epics": [],
        "summary": {
            "total_initiatives": 1,
            "total_epics": 0,
            "teams_involved": [],
        },
    }

    extraction_status = ExtractionStatus(
        complete=True,
        issues=[],
        initiatives_fetched=1,
        initiatives_failed=0,
        team_projects_fetched=3,
        team_projects_failed=0,
    )

    output_dir = tmp_path / "data"
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(output_dir),
        filename_pattern="test_{timestamp}.json",
    )

    output_path = generator.generate(data, extraction_status)

    assert output_path.exists()

    with open(output_path) as f:
        result = json.load(f)

    assert result["jira_instance"] == "test.atlassian.net"
    assert result["extraction_status"]["complete"] is True
    assert len(result["initiatives"]) == 1
    assert "extracted_at" in result


def test_generate_output_with_issues(tmp_path):
    """Test generating output with extraction issues."""
    data = {
        "initiatives": [],
        "orphaned_epics": [],
        "summary": {"total_initiatives": 0, "total_epics": 0, "teams_involved": []},
    }

    extraction_status = ExtractionStatus(
        complete=False,
        issues=[
            {
                "severity": "error",
                "message": "Failed to fetch from project RSK: 403 Forbidden",
                "impact": "Missing all epics from RSK team",
            }
        ],
        initiatives_fetched=10,
        initiatives_failed=2,
        team_projects_fetched=2,
        team_projects_failed=1,
    )

    output_dir = tmp_path / "data"
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(output_dir),
    )

    output_path = generator.generate(data, extraction_status)

    with open(output_path) as f:
        result = json.load(f)

    assert result["extraction_status"]["complete"] is False
    assert len(result["extraction_status"]["issues"]) == 1
    assert result["extraction_status"]["team_projects_failed"] == 1


def test_filename_pattern_with_timestamp(tmp_path):
    """Test filename pattern with timestamp replacement."""
    data = {
        "initiatives": [],
        "orphaned_epics": [],
        "summary": {"total_initiatives": 0, "total_epics": 0, "teams_involved": []},
    }

    extraction_status = ExtractionStatus(complete=True, issues=[])

    output_dir = tmp_path / "data"
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(output_dir),
        filename_pattern="jira_{timestamp}.json",
    )

    output_path = generator.generate(data, extraction_status)

    # Check timestamp is in filename
    assert output_path.name.startswith("jira_")
    assert output_path.name.endswith(".json")
    assert len(output_path.name) > len("jira_.json")
