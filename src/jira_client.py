# src/jira_client.py
import time
from typing import List, Dict, Any
import requests


class JiraAPIError(Exception):
    """Jira API error."""
    pass


class JiraClient:
    """Jira Cloud REST API client."""

    def __init__(self, instance: str, email: str, api_token: str, timeout: int = 30):
        """Initialize Jira client.

        Args:
            instance: Jira instance URL (e.g., "company.atlassian.net")
            email: User email for authentication
            api_token: API token from Atlassian
            timeout: Request timeout in seconds
        """
        # Normalize instance URL
        if not instance.startswith("http"):
            instance = f"https://{instance}"
        self.base_url = instance.rstrip("/")

        self.auth = (email, api_token)
        self.timeout = timeout

        # Session for connection pooling
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def search_issues(
        self,
        jql: str,
        fields: List[str] = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search for issues using JQL.

        Args:
            jql: JQL query string
            fields: List of field names to return (None = all fields)
            max_results: Results per page (max 100)

        Returns:
            List of issue dictionaries

        Raises:
            JiraAPIError: If API request fails
        """
        all_issues = []
        next_page_token = None

        while True:
            params = {
                "jql": jql,
                "maxResults": min(max_results, 100),
            }

            if next_page_token:
                params["nextPageToken"] = next_page_token

            if fields:
                params["fields"] = ",".join(fields)

            try:
                url = f"{self.base_url}/rest/api/3/search/jql"

                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                )

                response.raise_for_status()
                data = response.json()

                # Get issues from response
                issues = data.get("issues", [])
                all_issues.extend(issues)

                # Check if more pages available using new pagination
                is_last = data.get("isLast", True)
                if is_last:
                    break

                # Get token for next page
                next_page_token = data.get("nextPageToken")
                if not next_page_token:
                    break

            except requests.HTTPError as e:
                raise JiraAPIError(f"Jira API error: {e.response.status_code} - {e.response.text}")
            except requests.RequestException as e:
                raise JiraAPIError(f"Request failed: {str(e)}")

        return all_issues

    def get_custom_fields(self) -> List[Dict[str, Any]]:
        """Get all custom fields.

        Returns:
            List of custom field dictionaries with id and name

        Raises:
            JiraAPIError: If API request fails
        """
        try:
            response = self.session.get(
                f"{self.base_url}/rest/api/3/field",
                timeout=self.timeout,
            )
            response.raise_for_status()

            all_fields = response.json()
            # Filter to custom fields only
            custom_fields = [
                f for f in all_fields
                if f.get("id", "").startswith("customfield_")
            ]

            return custom_fields

        except requests.HTTPError as e:
            raise JiraAPIError(f"Jira API error: {e.response.status_code} - {e.response.text}")
        except requests.RequestException as e:
            raise JiraAPIError(f"Request failed: {str(e)}")
