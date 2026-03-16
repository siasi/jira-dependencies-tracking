#!/usr/bin/env python3
"""Jira Dependencies Tracking CLI."""

import sys
import click
from pathlib import Path
from typing import Optional

from src.config import load_config, ConfigError
from src.jira_client import JiraClient, JiraAPIError
from src.fetcher import DataFetcher
from src.builder import build_hierarchy
from src.output import OutputGenerator, ExtractionStatus
from src.snapshot import SnapshotManager, SnapshotError


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Jira Dependencies Tracking Tool.

    Extract initiatives and epics to analyze team contributions.
    """
    pass


@cli.command()
@click.option(
    "--config",
    default="config.yaml",
    help="Path to config file",
    type=click.Path(exists=True),
)
@click.option(
    "--output",
    default=None,
    help="Custom output file path",
    type=click.Path(),
)
@click.option(
    "--format",
    type=click.Choice(["json", "csv", "both"], case_sensitive=False),
    default="json",
    help="Output format: json (default), csv, or both",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be fetched without writing output",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Verbose output for debugging",
)
def extract(config: str, output: Optional[str], format: str, dry_run: bool, verbose: bool):
    """Extract data from Jira."""
    try:
        # Load configuration
        if verbose:
            click.echo(f"Loading config from: {config}")

        cfg = load_config(config)

        # Initialize Jira client
        if verbose:
            click.echo(f"Connecting to: {cfg.jira.instance}")

        client = JiraClient(
            instance=cfg.jira.instance,
            email=cfg.jira.email,
            api_token=cfg.jira.api_token,
        )

        # Initialize fetcher
        fetcher = DataFetcher(
            client=client,
            initiatives_project=cfg.projects.initiatives,
            team_projects=cfg.projects.teams,
            custom_fields=cfg.custom_fields,
            filter_quarter=cfg.filters.quarter if cfg.filters else None,
        )

        if dry_run:
            click.echo("\nDry run - showing what would be fetched:\n")
            click.echo(f"  Initiatives project: {cfg.projects.initiatives}")
            click.echo(f"  Team projects: {', '.join(cfg.projects.teams)}")
            click.echo(f"  RAG field ID: {cfg.custom_fields.get('rag_status')}")
            return

        # Fetch data
        click.echo("Fetching data from Jira...")

        # Show filtering status
        if cfg.filters and cfg.filters.quarter:
            click.echo(f"Applying filters: quarter='{cfg.filters.quarter}', status!='Done'")

        with click.progressbar(length=2, label="Extracting") as bar:
            initiatives_result, epics_result = fetcher.fetch_all()
            bar.update(2)

        # Extract queries
        queries = {
            "initiatives": initiatives_result.jql,
            "epics": epics_result.jql
        }

        # Build extraction status
        issues = []

        if not initiatives_result.success:
            issues.append({
                "severity": "error",
                "message": f"Failed to fetch initiatives: {initiatives_result.error_message}",
                "impact": "Missing all initiatives data",
            })

        if not epics_result.success:
            issues.append({
                "severity": "error",
                "message": f"Failed to fetch epics: {epics_result.error_message}",
                "impact": "Missing all epics data",
            })

        # Check for orphaned epics warning
        if epics_result.success:
            orphaned_count = sum(1 for e in epics_result.items if not e.get("parent_key"))
            if orphaned_count > 0:
                issues.append({
                    "severity": "warning",
                    "message": f"{orphaned_count} epics found without parent initiative",
                    "impact": f"{orphaned_count} epics listed in orphaned_epics section",
                })

        extraction_status = ExtractionStatus(
            complete=initiatives_result.success and epics_result.success and len(issues) == 0,
            issues=issues,
            initiatives_fetched=len(initiatives_result.items) if initiatives_result.success else 0,
            initiatives_failed=0 if initiatives_result.success else 1,
            team_projects_fetched=len(cfg.projects.teams) if epics_result.success else 0,
            team_projects_failed=0 if epics_result.success else len(cfg.projects.teams),
        )

        # Build hierarchy
        if verbose:
            click.echo("Building relationships...")

        hierarchy_data = build_hierarchy(
            initiatives=initiatives_result.items if initiatives_result.success else [],
            epics=epics_result.items if epics_result.success else [],
        )

        # Generate output
        generator = OutputGenerator(
            jira_instance=cfg.jira.instance,
            output_directory=cfg.output.directory,
            filename_pattern=cfg.output.filename_pattern,
            custom_fields=cfg.custom_fields,
        )

        custom_path = Path(output) if output else None

        # Generate output based on format
        if format in ["json", "both"]:
            json_path = generator.generate(
                data=hierarchy_data,
                extraction_status=extraction_status,
                queries=queries,
                custom_path=custom_path,
            )
            click.echo(f"\n✓ JSON output: {json_path}")

        if format in ["csv", "both"]:
            csv_result = generator.generate_csv(
                data=hierarchy_data,
                extraction_status=extraction_status,
                queries=queries,
                custom_path=custom_path,
            )
            click.echo(f"✓ CSV output: {csv_result.csv_file}")

        # Print summary
        click.echo(f"\nSummary:")
        if cfg.filters and cfg.filters.quarter:
            click.echo(f"  Initiatives: {hierarchy_data['summary']['total_initiatives']} (filtered by quarter: {cfg.filters.quarter})")
        else:
            click.echo(f"  Initiatives: {hierarchy_data['summary']['total_initiatives']}")
        click.echo(f"  Epics: {hierarchy_data['summary']['total_epics']}")
        click.echo(f"  Teams: {len(hierarchy_data['summary']['teams_involved'])}")

        if not extraction_status.complete:
            click.echo(click.style("\n⚠ Warning: Extraction incomplete", fg="yellow", bold=True))
            for issue in extraction_status.issues:
                severity_color = "red" if issue["severity"] == "error" else "yellow"
                click.echo(click.style(f"  [{issue['severity'].upper()}] {issue['message']}", fg=severity_color))
            sys.exit(1)

    except ConfigError as e:
        click.echo(click.style(f"Configuration error: {e}", fg="red"), err=True)
        sys.exit(2)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(2)


@cli.command()
@click.option(
    "--config",
    default="config.yaml",
    help="Path to config file",
    type=click.Path(exists=True),
)
def list_fields(config: str):
    """List all custom fields in Jira."""
    try:
        cfg = load_config(config)

        client = JiraClient(
            instance=cfg.jira.instance,
            email=cfg.jira.email,
            api_token=cfg.jira.api_token,
        )

        click.echo("Fetching custom fields...")
        fields = client.get_custom_fields()

        click.echo(f"\nFound {len(fields)} custom fields:\n")

        for field in sorted(fields, key=lambda f: f["name"]):
            click.echo(f"  {field['id']:<25} {field['name']}")

        click.echo("\nUpdate config.yaml with the field ID for RAG status.")

    except ConfigError as e:
        click.echo(click.style(f"Configuration error: {e}", fg="red"), err=True)
        sys.exit(2)
    except JiraAPIError as e:
        click.echo(click.style(f"Jira API error: {e}", fg="red"), err=True)
        sys.exit(2)


@cli.command()
@click.option(
    "--config",
    default="config.yaml",
    help="Path to config file",
    type=click.Path(exists=True),
)
def validate_config(config: str):
    """Validate configuration file."""
    try:
        click.echo(f"Validating config: {config}")

        cfg = load_config(config)

        click.echo("\n✓ Configuration valid:\n")
        click.echo(f"  Jira instance: {cfg.jira.instance}")
        click.echo(f"  Initiatives project: {cfg.projects.initiatives}")
        click.echo(f"  Team projects: {', '.join(cfg.projects.teams)}")
        click.echo(f"  RAG field: {cfg.custom_fields.get('rag_status')}")
        click.echo(f"  Output directory: {cfg.output.directory}")

        # Test connection
        click.echo("\nTesting Jira connection...")
        client = JiraClient(
            instance=cfg.jira.instance,
            email=cfg.jira.email,
            api_token=cfg.jira.api_token,
        )

        # Simple test query
        client.search_issues("project = XYZ", fields=["key"], max_results=1)

        click.echo("✓ Connection successful")

        # Validate custom fields exist in Jira
        if cfg.custom_fields:
            click.echo("\nValidating custom fields...")
            all_fields = client.get_custom_fields()
            field_ids = {f["id"] for f in all_fields}

            for field_name, field_id in cfg.custom_fields.items():
                if field_id not in field_ids:
                    raise ConfigError(
                        f"Custom field '{field_name}' (ID: {field_id}) not found in Jira"
                    )
                click.echo(f"  ✓ {field_name}: {field_id}")

            click.echo("✓ All custom fields valid")

    except ConfigError as e:
        click.echo(click.style(f"\n✗ Configuration error: {e}", fg="red"), err=True)
        sys.exit(2)
    except JiraAPIError as e:
        click.echo(click.style(f"\n✗ Jira connection error: {e}", fg="red"), err=True)
        click.echo("\nCheck your credentials and network connection.")
        sys.exit(2)


@cli.command()
@click.option(
    "--config",
    default="config.yaml",
    help="Path to config file",
    type=click.Path(exists=True),
)
@click.option(
    "--label",
    required=True,
    help="Snapshot label (e.g., 2026-Q2-baseline)",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Verbose output for debugging",
)
def snapshot(config: str, label: str, verbose: bool):
    """Capture timestamped snapshot of current Jira data."""
    try:
        # Load configuration
        if verbose:
            click.echo(f"Loading config from: {config}")

        cfg = load_config(config)

        # Initialize Jira client
        if verbose:
            click.echo(f"Connecting to: {cfg.jira.instance}")

        client = JiraClient(
            instance=cfg.jira.instance,
            email=cfg.jira.email,
            api_token=cfg.jira.api_token,
        )

        # Initialize fetcher
        fetcher = DataFetcher(
            client=client,
            initiatives_project=cfg.projects.initiatives,
            team_projects=cfg.projects.teams,
            custom_fields=cfg.custom_fields,
            filter_quarter=cfg.filters.quarter if cfg.filters else None,
        )

        # Fetch data
        click.echo(f"Capturing snapshot: {label}")

        if cfg.filters and cfg.filters.quarter:
            click.echo(f"Applying filters: quarter='{cfg.filters.quarter}', status!='Done'")

        with click.progressbar(length=2, label="Extracting") as bar:
            initiatives_result, epics_result = fetcher.fetch_all()
            bar.update(2)

        # Extract queries
        queries = {
            "initiatives": initiatives_result.jql,
            "epics": epics_result.jql
        }

        # Build extraction status
        issues = []

        if not initiatives_result.success:
            issues.append({
                "severity": "error",
                "message": f"Failed to fetch initiatives: {initiatives_result.error_message}",
                "impact": "Missing all initiatives data",
            })

        if not epics_result.success:
            issues.append({
                "severity": "error",
                "message": f"Failed to fetch epics: {epics_result.error_message}",
                "impact": "Missing all epics data",
            })

        # Check for orphaned epics
        if epics_result.success:
            orphaned_count = sum(1 for e in epics_result.items if not e.get("parent_key"))
            if orphaned_count > 0 and verbose:
                click.echo(f"Note: {orphaned_count} orphaned epics found")

        extraction_status = ExtractionStatus(
            complete=initiatives_result.success and epics_result.success and len(issues) == 0,
            issues=issues,
            initiatives_fetched=len(initiatives_result.items) if initiatives_result.success else 0,
            initiatives_failed=0 if initiatives_result.success else 1,
            team_projects_fetched=len(cfg.projects.teams) if epics_result.success else 0,
            team_projects_failed=0 if epics_result.success else len(cfg.projects.teams),
        )

        # Build hierarchy
        if verbose:
            click.echo("Building relationships...")

        hierarchy_data = build_hierarchy(
            initiatives=initiatives_result.items if initiatives_result.success else [],
            epics=epics_result.items if epics_result.success else [],
        )

        # Generate output in memory (reuse OutputGenerator logic)
        generator = OutputGenerator(
            jira_instance=cfg.jira.instance,
            output_directory=cfg.output.directory,
            filename_pattern=cfg.output.filename_pattern,
            custom_fields=cfg.custom_fields,
        )

        # Build data structure
        from datetime import datetime
        output_data = {
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "jira_instance": cfg.jira.instance,
            "queries": queries,
            "extraction_status": extraction_status.__dict__,
            "initiatives": hierarchy_data["initiatives"],
            "orphaned_epics": hierarchy_data.get("orphaned_epics", []),
            "summary": hierarchy_data["summary"],
        }

        # Save snapshot
        snapshot_manager = SnapshotManager()
        snapshot_path = snapshot_manager.save_snapshot(
            label=label,
            data=output_data,
            config=cfg
        )

        # Print summary
        click.echo(f"\n✓ Snapshot saved: {snapshot_path}")
        click.echo(f"\nSnapshot summary:")
        click.echo(f"  Label: {label}")
        if cfg.filters and cfg.filters.quarter:
            click.echo(f"  Initiatives: {hierarchy_data['summary']['total_initiatives']} (filtered by quarter: {cfg.filters.quarter})")
        else:
            click.echo(f"  Initiatives: {hierarchy_data['summary']['total_initiatives']}")
        click.echo(f"  Epics: {hierarchy_data['summary']['total_epics']}")
        click.echo(f"  Teams: {len(hierarchy_data['summary']['teams_involved'])}")

        if not extraction_status.complete:
            click.echo(click.style("\n⚠ Warning: Snapshot captured with issues", fg="yellow", bold=True))
            for issue in extraction_status.issues:
                severity_color = "red" if issue["severity"] == "error" else "yellow"
                click.echo(click.style(f"  [{issue['severity'].upper()}] {issue['message']}", fg=severity_color))

    except ConfigError as e:
        click.echo(click.style(f"Configuration error: {e}", fg="red"), err=True)
        sys.exit(2)
    except SnapshotError as e:
        click.echo(click.style(f"Snapshot error: {e}", fg="red"), err=True)
        sys.exit(2)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(2)


@cli.group()
def snapshots():
    """Manage snapshots."""
    pass


@snapshots.command(name="list")
def snapshots_list():
    """List all available snapshots."""
    try:
        snapshot_manager = SnapshotManager()
        snapshot_list = snapshot_manager.list_snapshots()

        if not snapshot_list:
            click.echo("No snapshots found.")
            click.echo("\nCreate a snapshot with:")
            click.echo("  python jira_extract.py snapshot --label <label>")
            return

        click.echo(f"\nFound {len(snapshot_list)} snapshot(s):\n")

        # Display as table
        header = f"{'Label':<30} {'Timestamp':<25} {'Initiatives':<12} {'Epics':<8} {'Teams':<6}"
        click.echo(header)
        click.echo("-" * len(header))

        for snap in snapshot_list:
            click.echo(
                f"{snap.label:<30} {snap.timestamp:<25} "
                f"{snap.total_initiatives:<12} {snap.total_epics:<8} {snap.total_teams:<6}"
            )

        click.echo(f"\nSnapshots stored in: data/snapshots/")

    except SnapshotError as e:
        click.echo(click.style(f"Snapshot error: {e}", fg="red"), err=True)
        sys.exit(2)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(2)


if __name__ == "__main__":
    cli()
