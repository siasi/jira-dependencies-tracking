# src/fetcher.py
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
from src.jira_client import JiraClient, JiraAPIError


@dataclass
class FetchResult:
    """Result of a fetch operation."""
    success: bool
    items: List[Dict[str, Any]]
    error_message: Optional[str] = None
    project_key: Optional[str] = None
    jql: Optional[str] = None


class DataFetcher:
    """Fetches initiatives and epics from Jira."""

    def __init__(
        self,
        client: JiraClient,
        initiatives_project: str,
        team_projects: List[str],
        rag_field_id: str,
        quarter_field_id: Optional[str] = None,
        filter_quarter: Optional[str] = None,
    ):
        """Initialize data fetcher.

        Args:
            client: JiraClient instance
            initiatives_project: Project key for initiatives (e.g., "INIT")
            team_projects: List of team project keys
            rag_field_id: Custom field ID for RAG status
            quarter_field_id: Custom field ID for quarter (optional)
            filter_quarter: Quarter value to filter by (e.g., "25 Q1", optional)
        """
        self.client = client
        self.initiatives_project = initiatives_project
        self.team_projects = team_projects
        self.rag_field_id = rag_field_id
        self.quarter_field_id = quarter_field_id
        self.filter_quarter = filter_quarter

    def fetch_initiatives(self) -> FetchResult:
        """Fetch all initiatives from the initiatives project.

        Returns:
            FetchResult with initiatives data
        """
        # Build base JQL
        jql = f"project = {self.initiatives_project} AND issuetype = Initiative"

        # Add filters if configured
        if self.filter_quarter:
            jql += f' AND status != "Done" AND {self.quarter_field_id} = "{self.filter_quarter}"'

        # Build fields list
        fields = ["summary", "status", self.rag_field_id]
        if self.quarter_field_id and self.filter_quarter:
            fields.append(self.quarter_field_id)

        try:
            issues = self.client.search_issues(jql, fields=fields)

            # Normalize initiative data
            initiatives = []
            for issue in issues:
                fields_data = issue.get("fields", {})

                # Extract RAG status
                rag_field = fields_data.get(self.rag_field_id, {})
                rag_status = None
                if isinstance(rag_field, dict):
                    rag_status = rag_field.get("value")
                elif isinstance(rag_field, str):
                    rag_status = rag_field

                initiative_data = {
                    "key": issue["key"],
                    "summary": fields_data.get("summary", ""),
                    "status": fields_data.get("status", {}).get("name", "Unknown"),
                    "rag_status": rag_status,
                    "url": f"{self.client.base_url}/browse/{issue['key']}",
                }

                # Add quarter if present
                if self.quarter_field_id and self.filter_quarter:
                    quarter_field = fields_data.get(self.quarter_field_id, {})
                    quarter_value = None
                    if isinstance(quarter_field, dict):
                        quarter_value = quarter_field.get("value")
                    elif isinstance(quarter_field, str):
                        quarter_value = quarter_field
                    initiative_data["quarter"] = quarter_value

                initiatives.append(initiative_data)

            return FetchResult(success=True, items=initiatives, jql=jql)

        except JiraAPIError as e:
            return FetchResult(
                success=False,
                items=[],
                error_message=str(e),
                project_key=self.initiatives_project,
                jql=jql,
            )

    def fetch_epics(self) -> FetchResult:
        """Fetch all epics from team projects.

        Returns:
            FetchResult with epics data
        """
        # Handle empty team projects list
        if not self.team_projects:
            return FetchResult(success=True, items=[], jql=None)

        # Build JQL for all team projects
        project_filter = " OR ".join([f"project = {p}" for p in self.team_projects])
        jql = f"({project_filter}) AND issuetype = Epic"
        fields = ["summary", "status", "parent", "project", self.rag_field_id]

        try:
            issues = self.client.search_issues(jql, fields=fields)

            # Normalize epic data
            epics = []
            for issue in issues:
                fields_data = issue.get("fields", {})

                # Extract parent initiative key
                parent = fields_data.get("parent", {})
                parent_key = parent.get("key") if parent else None

                # Extract RAG status
                rag_field = fields_data.get(self.rag_field_id, {})
                rag_status = None
                if isinstance(rag_field, dict):
                    rag_status = rag_field.get("value")
                elif isinstance(rag_field, str):
                    rag_status = rag_field

                # Extract project info
                project = fields_data.get("project", {})

                epics.append({
                    "key": issue["key"],
                    "summary": fields_data.get("summary", ""),
                    "status": fields_data.get("status", {}).get("name", "Unknown"),
                    "rag_status": rag_status,
                    "parent_key": parent_key,
                    "team_project_key": project.get("key", ""),
                    "team_project_name": project.get("name", ""),
                    "url": f"{self.client.base_url}/browse/{issue['key']}",
                })

            return FetchResult(success=True, items=epics, jql=jql)

        except JiraAPIError as e:
            return FetchResult(
                success=False,
                items=[],
                error_message=str(e),
                jql=jql,
            )

    def fetch_all(self) -> Tuple[FetchResult, FetchResult]:
        """Fetch initiatives and epics in parallel.

        Returns:
            Tuple of (initiatives_result, epics_result)
        """
        with ThreadPoolExecutor(max_workers=2) as executor:
            initiatives_future = executor.submit(self.fetch_initiatives)
            epics_future = executor.submit(self.fetch_epics)

            initiatives_result = initiatives_future.result()
            epics_result = epics_future.result()

        return initiatives_result, epics_result
