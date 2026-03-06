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
    "--dry-run",
    is_flag=True,
    help="Show what would be fetched without writing output",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Verbose output for debugging",
)
def extract(config: str, output: Optional[str], dry_run: bool, verbose: bool):
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
            rag_field_id=cfg.custom_fields.rag_status,
            quarter_field_id=cfg.custom_fields.quarter,
            filter_quarter=cfg.filters.quarter if cfg.filters else None,
        )

        if dry_run:
            click.echo("\nDry run - showing what would be fetched:\n")
            click.echo(f"  Initiatives project: {cfg.projects.initiatives}")
            click.echo(f"  Team projects: {', '.join(cfg.projects.teams)}")
            click.echo(f"  RAG field ID: {cfg.custom_fields.rag_status}")
            return

        # Fetch data
        click.echo("Fetching data from Jira...")

        # Show filtering status
        if cfg.filters and cfg.filters.quarter:
            click.echo(f"Applying filters: quarter='{cfg.filters.quarter}', status!='Done'")

        with click.progressbar(length=2, label="Extracting") as bar:
            initiatives_result, epics_result = fetcher.fetch_all()
            bar.update(2)

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
        )

        output_path = generator.generate(
            data=hierarchy_data,
            extraction_status=extraction_status,
            custom_path=Path(output) if output else None,
        )

        # Print summary
        click.echo(f"\n✓ Data extracted to: {output_path}")
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
        click.echo(f"  RAG field: {cfg.custom_fields.rag_status}")
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

    except ConfigError as e:
        click.echo(click.style(f"\n✗ Configuration error: {e}", fg="red"), err=True)
        sys.exit(2)
    except JiraAPIError as e:
        click.echo(click.style(f"\n✗ Jira connection error: {e}", fg="red"), err=True)
        click.echo("\nCheck your credentials and network connection.")
        sys.exit(2)


if __name__ == "__main__":
    cli()
