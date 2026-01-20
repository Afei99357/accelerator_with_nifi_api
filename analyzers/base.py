"""Base analyzer class for NiFi flow analysis.

All analyzers inherit from BaseAnalyzer and work with template_dto structure.
"""

from typing import Any, Dict, List
from abc import ABC, abstractmethod


class BaseAnalyzer(ABC):
    """Base class for analyzers that work with template_dto."""

    def __init__(self, template_dto: Dict[str, Any]):
        """Initialize analyzer with template_dto.

        Args:
            template_dto: NiFi flow in TemplateDTO format with keys:
                - template: metadata (id, name, description, timestamp)
                - snippet: root snippet contents with processors, connections, etc.
        """
        self.template_dto = template_dto
        self.processors = template_dto.get("snippet", {}).get("processors", [])
        self.connections = template_dto.get("snippet", {}).get("connections", [])
        self.process_groups = template_dto.get("snippet", {}).get("processGroups", [])
        self.controller_services = template_dto.get("snippet", {}).get("controllerServices", [])

    @abstractmethod
    def analyze(self) -> Dict[str, Any]:
        """Run analysis and return results.

        Returns:
            Dict containing analysis results. Structure depends on analyzer type.
        """
        pass

    def _get_all_processors(self, snippet: Dict[str, Any] = None, collected: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Recursively get all processors from snippet including nested process groups.

        Args:
            snippet: Snippet to extract processors from (defaults to root snippet)
            collected: List to collect processors into (used for recursion)

        Returns:
            List of all processor dictionaries
        """
        if collected is None:
            collected = []

        if snippet is None:
            snippet = self.template_dto.get("snippet", {})

        # Add processors from this snippet
        collected.extend(snippet.get("processors", []))

        # Recursively process nested process groups
        for pg in snippet.get("processGroups", []):
            contents = pg.get("contents", {})
            if contents:
                self._get_all_processors(contents, collected)

        return collected

    def _get_all_connections(self, snippet: Dict[str, Any] = None, collected: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Recursively get all connections from snippet including nested process groups.

        Args:
            snippet: Snippet to extract connections from (defaults to root snippet)
            collected: List to collect connections into (used for recursion)

        Returns:
            List of all connection dictionaries
        """
        if collected is None:
            collected = []

        if snippet is None:
            snippet = self.template_dto.get("snippet", {})

        # Add connections from this snippet
        collected.extend(snippet.get("connections", []))

        # Recursively process nested process groups
        for pg in snippet.get("processGroups", []):
            contents = pg.get("contents", {})
            if contents:
                self._get_all_connections(contents, collected)

        return collected

    def _get_processor_by_id(self, processor_id: str) -> Dict[str, Any]:
        """Find a processor by ID.

        Args:
            processor_id: Processor ID to search for

        Returns:
            Processor dict if found, empty dict otherwise
        """
        all_processors = self._get_all_processors()
        for proc in all_processors:
            if proc.get("id") == processor_id:
                return proc
        return {}

    def _get_property_value(self, processor: Dict[str, Any], property_name: str) -> str:
        """Get property value from processor config.

        Args:
            processor: Processor dict
            property_name: Name of property to retrieve

        Returns:
            Property value as string, or empty string if not found
        """
        config = processor.get("config", {})
        properties = config.get("properties", {})
        return properties.get(property_name, "")
