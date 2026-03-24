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
        custom_fields: Dict[str, str],
        filter_quarter: Optional[str] = None,
    ):
        """Initialize data fetcher.

        Args:
            client: JiraClient instance
            initiatives_project: Project key for initiatives (e.g., "INIT")
            team_projects: List of team project keys
            custom_fields: Dict mapping output field names to Jira field IDs
            filter_quarter: Quarter value to filter by (e.g., "25 Q1", optional)
        """
        self.client = client
        self.initiatives_project = initiatives_project
        self.team_projects = team_projects
        self.custom_fields = custom_fields
        self.filter_quarter = filter_quarter
        self._field_name_cache = None  # Cache for field ID -> name mapping

    def _get_field_name(self, field_id: str) -> str:
        """Get Jira field name from field ID for JQL queries.

        Args:
            field_id: Custom field ID (e.g., "customfield_12108")

        Returns:
            Field name for JQL (e.g., "Quarter[Dropdown]") or field ID if name not found
        """
        # Build cache on first use
        if self._field_name_cache is None:
            self._field_name_cache = {}
            try:
                fields = self.client.get_custom_fields()
                for field in fields:
                    self._field_name_cache[field.get("id")] = field.get("name", field.get("id"))
            except Exception:
                # If we can't get fields, fall back to using IDs
                pass

        # Return field name from cache, or fall back to ID
        return self._field_name_cache.get(field_id, field_id)

    def _extract_field_value(self, field_data: Any) -> Optional[str]:
        """Extract value from Jira custom field.

        Handles:
        - Select fields: {"value": "🟢"} → "🟢"
        - Text fields: "plain text" → "plain text"
        - Array fields: [{"value": "A"}, {"value": "B"}] → "A, B"
        - Single-item arrays: [{"value": "A"}] → "A"
        - Empty arrays: [] → None
        - Missing fields: None → None

        Args:
            field_data: Raw field data from Jira API

        Returns:
            Extracted string value or None
        """
        if field_data is None:
            return None

        # Handle array fields (multi-select, checkboxes, etc.)
        if isinstance(field_data, list):
            if not field_data:  # Empty array
                return None
            # Extract "value" from each item in the array
            values = [item.get("value") for item in field_data if isinstance(item, dict) and "value" in item]
            if not values:
                return None
            # Return single value if only one, otherwise comma-separated
            return values[0] if len(values) == 1 else ", ".join(values)

        # Handle single select fields and team objects
        if isinstance(field_data, dict):
            # Try "value" first (for select fields), then "name" (for team fields)
            return field_data.get("value") or field_data.get("name")

        # Handle plain text fields
        return field_data

    def fetch_initiatives(self) -> FetchResult:
        """Fetch all initiatives from the initiatives project.

        Returns:
            FetchResult with initiatives data
        """
        # Build base JQL
        jql = f"project = {self.initiatives_project} AND issuetype = Initiative"

        # Add filters if configured
        if self.filter_quarter and "quarter" in self.custom_fields:
            quarter_field_id = self.custom_fields["quarter"]
            # Use field name for JQL (not ID) - some fields like dropdowns require this
            quarter_field_name = self._get_field_name(quarter_field_id)
            jql += f' AND status != "Done" AND "{quarter_field_name}" = "{self.filter_quarter}"'

        # Build fields list - dynamic from config
        # NOTE: Fetches ALL configured custom fields, even if not used for filtering
        # This simplifies the code; Jira API batches field requests efficiently
        fields = ["summary", "status"] + list(self.custom_fields.values())

        try:
            issues = self.client.search_issues(jql, fields=fields)

            # Normalize initiative data
            initiatives = []
            for issue in issues:
                fields_data = issue.get("fields", {})

                # Build base initiative data
                initiative_data = {
                    "key": issue["key"],
                    "summary": fields_data.get("summary", ""),
                    "status": fields_data.get("status", {}).get("name", "Unknown"),
                    "url": f"{self.client.base_url}/browse/{issue['key']}",
                }

                # Add all custom fields dynamically
                for output_name, field_id in self.custom_fields.items():
                    field_data = fields_data.get(field_id)
                    initiative_data[output_name] = self._extract_field_value(field_data)

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

        # Get rag_field_id from custom_fields if present
        rag_field_id = self.custom_fields.get("rag_status")
        fields = ["summary", "status", "parent", "project"]
        if rag_field_id:
            fields.append(rag_field_id)

        try:
            issues = self.client.search_issues(jql, fields=fields)

            # Normalize epic data
            epics = []
            for issue in issues:
                fields_data = issue.get("fields", {})

                # Extract parent initiative key
                parent = fields_data.get("parent", {})
                parent_key = parent.get("key") if parent else None

                # Extract RAG status if field is configured
                rag_status = None
                if rag_field_id:
                    rag_field = fields_data.get(rag_field_id, {})
                    rag_status = self._extract_field_value(rag_field)

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
