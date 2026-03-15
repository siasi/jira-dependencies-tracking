# tests/test_output.py
import csv
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


def test_generate_output_with_queries(tmp_path):
    """Test output includes queries object."""
    output_dir = tmp_path / "data"
    output_path = output_dir / "test_output.json"

    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(output_dir)
    )

    data = {
        "initiatives": [],
        "orphaned_epics": [],
        "summary": {
            "total_initiatives": 0,
            "total_epics": 0,
            "teams_involved": []
        }
    }

    extraction_status = ExtractionStatus(
        complete=True,
        issues=[]
    )

    queries = {
        "initiatives": "project = INIT AND issuetype = Initiative",
        "epics": "(project = RSK OR project = CBNK) AND issuetype = Epic"
    }

    # Execute
    result_path = generator.generate(data, extraction_status, queries=queries, custom_path=output_path)

    # Verify
    with open(result_path) as f:
        output = json.load(f)

    assert "queries" in output
    assert output["queries"]["initiatives"] == "project = INIT AND issuetype = Initiative"
    assert output["queries"]["epics"] == "(project = RSK OR project = CBNK) AND issuetype = Epic"

    # Verify queries is at top level, before extraction_status
    keys = list(output.keys())
    queries_index = keys.index("queries")
    status_index = keys.index("extraction_status")
    assert queries_index < status_index


# CSV Export Tests


def test_generate_csv_basic(tmp_path):
    """Test basic CSV generation with denormalized structure."""
    data = {
        "initiatives": [
            {
                "key": "INIT-1",
                "summary": "Test Initiative",
                "status": "Proposed",
                "url": "https://test.atlassian.net/browse/INIT-1",
                "rag_status": "🟢",
                "quarter": "26 Q2",
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM",
                        "team_project_name": "Test Team",
                        "epics": [
                            {
                                "key": "TEAM-1",
                                "summary": "Test Epic",
                                "status": "In Progress",
                                "rag_status": "🟡",
                                "url": "https://test.atlassian.net/browse/TEAM-1"
                            }
                        ]
                    }
                ]
            }
        ],
        "orphaned_epics": [],
        "summary": {"total_initiatives": 1, "total_epics": 1, "teams_involved": ["TEAM"]}
    }

    extraction_status = ExtractionStatus(complete=True, issues=[])

    output_dir = tmp_path / "data"
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(output_dir),
        filename_pattern="test_{timestamp}.json"
    )

    result = generator.generate_csv(data, extraction_status)

    # Verify file exists
    assert result.csv_file.exists()
    assert result.csv_file.suffix == ".csv"

    # Read and verify CSV content
    with open(result.csv_file, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["initiative_key"] == "INIT-1"
        assert rows[0]["initiative_summary"] == "Test Initiative"
        assert rows[0]["quarter"] == "26 Q2"
        assert rows[0]["initiative_status"] == "Proposed"
        assert rows[0]["epic_key"] == "TEAM-1"
        assert rows[0]["epic_summary"] == "Test Epic"
        assert rows[0]["epic_rag_status"] == "🟡"
        assert rows[0]["epic_status"] == "In Progress"


def test_generate_csv_utf8_bom(tmp_path):
    """Verify UTF-8 BOM is present for Excel compatibility."""
    data = {
        "initiatives": [{
            "key": "INIT-1",
            "summary": "Test",
            "status": "Proposed",
            "url": "https://test",
            "contributing_teams": []
        }],
        "orphaned_epics": [],
        "summary": {"total_initiatives": 1, "total_epics": 0, "teams_involved": []}
    }

    extraction_status = ExtractionStatus(complete=True, issues=[])

    output_dir = tmp_path / "data"
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(output_dir)
    )

    result = generator.generate_csv(data, extraction_status)

    # Read raw bytes
    with open(result.csv_file, "rb") as f:
        first_bytes = f.read(3)

    # Verify BOM is present (EF BB BF in hex)
    assert first_bytes == b'\xef\xbb\xbf', "UTF-8 BOM missing"


def test_generate_csv_with_orphaned_epics(tmp_path):
    """Orphaned epics included in CSV with empty initiative columns."""
    data = {
        "initiatives": [
            {
                "key": "INIT-1",
                "summary": "Initiative",
                "status": "Active",
                "url": "https://test/INIT-1",
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM",
                        "team_project_name": "Team A",
                        "epics": [
                            {
                                "key": "TEAM-1",
                                "summary": "Linked Epic",
                                "status": "Done",
                                "url": "https://test/TEAM-1"
                            }
                        ]
                    }
                ]
            }
        ],
        "orphaned_epics": [
            {
                "team_project_key": "RSK",
                "key": "RSK-123",
                "summary": "Orphaned Epic",
                "status": "In Progress",
                "rag_status": "🟡",
                "url": "https://test/RSK-123"
            }
        ],
        "summary": {"total_initiatives": 1, "total_epics": 2, "teams_involved": ["TEAM", "RSK"]}
    }

    extraction_status = ExtractionStatus(complete=True, issues=[])

    output_dir = tmp_path / "data"
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(output_dir)
    )

    result = generator.generate_csv(data, extraction_status)

    with open(result.csv_file, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        # Should have 2 rows (1 linked epic + 1 orphaned epic)
        assert len(rows) == 2

        # First row: linked epic
        assert rows[0]["epic_key"] == "TEAM-1"
        assert rows[0]["initiative_key"] == "INIT-1"

        # Second row: orphaned epic with empty initiative fields
        assert rows[1]["epic_key"] == "RSK-123"
        assert rows[1]["initiative_key"] == ""
        assert rows[1]["initiative_summary"] == ""
        assert rows[1]["epic_rag_status"] == "🟡"


def test_generate_csv_special_characters(tmp_path):
    """CSV properly handles commas, quotes, newlines."""
    data = {
        "initiatives": [
            {
                "key": "INIT-1",
                "summary": 'Title with "quotes", commas, and\nnewlines',
                "status": "Proposed",
                "url": "https://test",
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM",
                        "team_project_name": "Test Team",
                        "epics": [
                            {
                                "key": "TEAM-1",
                                "summary": "Epic, with, commas",
                                "status": "In Progress",
                                "url": "https://test"
                            }
                        ]
                    }
                ]
            }
        ],
        "orphaned_epics": [],
        "summary": {"total_initiatives": 1, "total_epics": 1, "teams_involved": ["TEAM"]}
    }

    extraction_status = ExtractionStatus(complete=True, issues=[])

    output_dir = tmp_path / "data"
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(output_dir)
    )

    result = generator.generate_csv(data, extraction_status)

    # Read CSV and verify content preserved
    with open(result.csv_file, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        # CSV module should handle escaping automatically
        assert 'Title with "quotes", commas, and\nnewlines' in rows[0]["initiative_summary"]
        assert "Epic, with, commas" in rows[0]["epic_summary"]


def test_generate_csv_emoji_preservation(tmp_path):
    """Emoji characters preserved in CSV output."""
    data = {
        "initiatives": [
            {
                "key": "INIT-1",
                "summary": "Emoji test 🎉",
                "status": "Active",
                "url": "https://test",
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM",
                        "team_project_name": "Test Team",
                        "epics": [
                            {
                                "key": "TEAM-1",
                                "summary": "Epic 🚀",
                                "status": "Done",
                                "rag_status": "🔴",
                                "url": "https://test"
                            }
                        ]
                    }
                ]
            }
        ],
        "orphaned_epics": [],
        "summary": {"total_initiatives": 1, "total_epics": 1, "teams_involved": ["TEAM"]}
    }

    extraction_status = ExtractionStatus(complete=True, issues=[])

    output_dir = tmp_path / "data"
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(output_dir)
    )

    result = generator.generate_csv(data, extraction_status)

    with open(result.csv_file, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        assert "🎉" in rows[0]["initiative_summary"]
        assert "🚀" in rows[0]["epic_summary"]
        assert rows[0]["epic_rag_status"] == "🔴"


def test_generate_csv_empty_data(tmp_path):
    """CSV generation handles empty data gracefully."""
    data = {
        "initiatives": [],
        "orphaned_epics": [],
        "summary": {"total_initiatives": 0, "total_epics": 0, "teams_involved": []}
    }

    extraction_status = ExtractionStatus(complete=True, issues=[])

    output_dir = tmp_path / "data"
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(output_dir)
    )

    result = generator.generate_csv(data, extraction_status)

    # File should exist but be empty (or just headers)
    assert result.csv_file.exists()


def test_generate_csv_column_ordering(tmp_path):
    """CSV columns in exact specified order."""
    data = {
        "initiatives": [
            {
                "key": "INIT-1",
                "summary": "Test",
                "status": "Active",
                "url": "https://test",
                "quarter": "26 Q2",
                "strategic_objective": "growth",
                "contributing_teams": [
                    {
                        "team_project_key": "TEAM",
                        "team_project_name": "Test Team",
                        "epics": [
                            {
                                "key": "TEAM-1",
                                "summary": "Epic",
                                "status": "Done",
                                "url": "https://test"
                            }
                        ]
                    }
                ]
            }
        ],
        "orphaned_epics": [],
        "summary": {"total_initiatives": 1, "total_epics": 1, "teams_involved": ["TEAM"]}
    }

    extraction_status = ExtractionStatus(complete=True, issues=[])

    output_dir = tmp_path / "data"
    generator = OutputGenerator(
        jira_instance="test.atlassian.net",
        output_directory=str(output_dir)
    )

    result = generator.generate_csv(data, extraction_status)

    with open(result.csv_file, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        # Verify exact column order as specified
        expected_order = [
            "initiative_key",
            "initiative_summary",
            "strategic_objective",
            "quarter",
            "initiative_status",
            "team_project_key",
            "epic_key",
            "epic_summary",
            "epic_rag_status",
            "epic_status",
        ]
        assert fieldnames == expected_order
