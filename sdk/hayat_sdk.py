"""
HAYAT v2.0 — Official Python SDK
For institutional clients, law firms, and universities.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import httpx


@dataclass
class HAYATConfig:
    """SDK configuration."""
    base_url: str = "https://api.hayat.legal"
    api_key: Optional[str] = None
    timeout: float = 30.0
    max_retries: int = 3


class HAYATError(Exception):
    """Base HAYAT SDK error."""
    pass


class HAYATAuthError(HAYATError):
    """Authentication error."""
    pass


class HAYATRateLimitError(HAYATError):
    """Rate limit exceeded."""
    pass


class HAYATClient:
    """
    Official HAYAT Python SDK.

    Usage:
        client = HAYATClient(api_key="your-key")
        cases = client.search_cases("mandatory injunction")
        for case in cases:
            print(case.citation)
    """

    def __init__(self, config: Optional[HAYATConfig] = None):
        self.config = config or HAYATConfig()
        self._client = httpx.Client(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            headers=self._auth_headers(),
        )

    def _auth_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.config.api_key:
            headers["X-API-Key"] = self.config.api_key
        return headers

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        response = self._client.request(method, f"/api/v1{path}", **kwargs)

        if response.status_code == 401:
            raise HAYATAuthError("Invalid API key or authentication failed")
        if response.status_code == 429:
            raise HAYATRateLimitError("Rate limit exceeded. Please retry after delay.")

        response.raise_for_status()
        return response.json()

    # Search
    def search_cases(self, query: str, **filters) -> List[Dict[str, Any]]:
        params = {"query": query, "search_type": "natural_language", **filters}
        result = self._request("POST", "/search/", json=params)
        return result.get("results", [])

    def search_statutes(self, query: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {"query": query}
        if year:
            params["year"] = year
        result = self._request("POST", "/search/", json={**params, "search_type": "act"})
        return result.get("results", [])

    def search_by_citation(self, citation: str) -> Optional[Dict[str, Any]]:
        result = self._request("POST", "/search/", json={"query": citation, "search_type": "citation", "size": 1})
        results = result.get("results", [])
        return results[0] if results else None

    # Cases
    def get_case(self, case_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/cases/{case_id}")

    def get_case_citation_network(self, case_id: str, depth: int = 2) -> List[Dict[str, Any]]:
        case = self.get_case(case_id)
        return case.get("citation_network", [])

    # Statutes
    def get_statute(self, statute_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/statutes/{statute_id}")

    def get_section(self, statute_id: str, section_number: str) -> Optional[Dict[str, Any]]:
        statute = self.get_statute(statute_id)
        for section in statute.get("sections", []):
            if section["number"] == section_number:
                return section
        return None

    # AI
    def ask(self, question: str, temperature: float = 0.1) -> Dict[str, Any]:
        return self._request("POST", "/ai/ask", json={"question": question, "temperature": temperature})

    def summarize_case(self, case_id: str, style: str = "detailed") -> Dict[str, Any]:
        return self._request("POST", "/ai/summarize", json={"document_id": case_id, "style": style})

    def explain_statute(self, statute: str, section: str, text: str) -> Dict[str, Any]:
        return self._request("POST", "/ai/explain", json={"statute": statute, "section": section, "text": text})

    def compare_cases(self, case_ids: List[str]) -> Dict[str, Any]:
        return self._request("POST", "/ai/compare", json={"case_ids": case_ids})

    def draft_assistance(self, document_type: str, facts: str, language: str = "english") -> Dict[str, Any]:
        return self._request("POST", "/ai/draft", json={"document_type": document_type, "facts": facts, "language": language})

    def check_conflicts(self, text: str) -> Dict[str, Any]:
        return self._request("POST", "/ai/conflict-check", json={"text": text})

    # Analytics
    def get_case_trends(self, area_of_law: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if area_of_law:
            params["area_of_law"] = area_of_law
        return self._request("GET", "/analytics/trends", params=params)

    def get_citation_analytics(self) -> Dict[str, Any]:
        return self._request("GET", "/analytics/citations")

    # Practice Tools
    def track_deadline(self, title: str, due_date: str, **kwargs) -> Dict[str, Any]:
        return self._request("POST", "/practice/deadlines", json={"title": title, "due_date": due_date, **kwargs})

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
