"""Variable dependency analyzer.

Analyzes NiFi expression language variables and their usage across processors.
"""

import re
from typing import Any, Dict, List, Set

from analyzers.base import BaseAnalyzer


class VariablesAnalyzer(BaseAnalyzer):
    """Analyzes variable definitions and usage."""

    def analyze(self) -> Dict[str, Any]:
        """Analyze variable definitions and usage across the flow.

        Returns:
            Dict with keys:
                - defined_variables: Dict of variables defined in process groups
                - used_variables: Set of all variables used in processors
                - by_processor: Dict mapping processor ID to variables it uses
                - by_variable: Dict mapping variable name to processors that use it
                - undefined: Set of variables used but not defined
        """
        # Get defined variables from process groups
        defined_variables = self._get_defined_variables()

        # Find variable usage in processors
        used_variables: Set[str] = set()
        by_processor: Dict[str, List[str]] = {}
        by_variable: Dict[str, List[Dict[str, Any]]] = {}

        all_processors = self._get_all_processors()

        for proc in all_processors:
            proc_id = proc.get("id")
            proc_name = proc.get("name", "")
            proc_type = proc.get("type", "").split(".")[-1]

            # Extract variables used by this processor
            proc_variables = self._extract_variables_from_processor(proc)

            if proc_variables:
                used_variables.update(proc_variables)
                by_processor[proc_id] = sorted(list(proc_variables))

                proc_info = {
                    "id": proc_id,
                    "name": proc_name,
                    "type": proc_type,
                }

                for var in proc_variables:
                    if var not in by_variable:
                        by_variable[var] = []
                    by_variable[var].append(proc_info)

        # Find undefined variables (used but not defined)
        undefined = used_variables - set(defined_variables.keys())

        return {
            "defined_variables": defined_variables,
            "used_variables": sorted(list(used_variables)),
            "by_processor": by_processor,
            "by_variable": by_variable,
            "undefined": sorted(list(undefined)),
            "defined_count": len(defined_variables),
            "used_count": len(used_variables),
            "undefined_count": len(undefined),
        }

    def _get_defined_variables(
        self, snippet: Dict[str, Any] = None, collected: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Recursively collect variable definitions from process groups.

        Args:
            snippet: Snippet to extract variables from (defaults to root snippet)
            collected: Dict to collect variables into (used for recursion)

        Returns:
            Dict mapping variable name to definition info
        """
        if collected is None:
            collected = {}

        if snippet is None:
            snippet = self.template_dto.get("snippet", {})

        # Process nested process groups
        for pg in snippet.get("processGroups", []):
            pg_name = pg.get("name", "")
            pg_id = pg.get("id", "")
            variables = pg.get("variables", {})

            if variables:
                for var_name, var_value in variables.items():
                    if var_name not in collected:
                        collected[var_name] = {
                            "value": var_value,
                            "process_group": pg_name,
                            "process_group_id": pg_id,
                        }

            # Recurse into nested process groups
            contents = pg.get("contents", {})
            if contents:
                self._get_defined_variables(contents, collected)

        return collected

    def _extract_variables_from_processor(self, processor: Dict[str, Any]) -> Set[str]:
        """Extract NiFi expression language variables from processor config.

        Args:
            processor: Processor dict

        Returns:
            Set of variable names
        """
        variables = set()
        config = processor.get("config", {})
        properties = config.get("properties", {})

        # Check all property values for variables
        for prop_name, prop_value in properties.items():
            if prop_value and isinstance(prop_value, str):
                vars_in_value = self._extract_variables_from_text(prop_value)
                variables.update(vars_in_value)

        # Also check comments
        comments = config.get("comments", "")
        if comments:
            vars_in_comments = self._extract_variables_from_text(comments)
            variables.update(vars_in_comments)

        return variables

    def _extract_variables_from_text(self, text: str) -> Set[str]:
        """Extract NiFi expression language variables from text.

        Matches patterns like:
        - ${variable_name}
        - ${var.with.dots}
        - ${var:function()}

        Args:
            text: Text to search

        Returns:
            Set of variable names
        """
        variables = set()

        # Pattern for ${...} expressions
        pattern = r"\$\{([a-zA-Z0-9_\.]+)(?::[^\}]*)?\}"
        matches = re.findall(pattern, text)

        for match in matches:
            # Remove any function calls or modifiers
            var_name = match.split(":")[0].strip()
            if var_name:
                variables.add(var_name)

        return variables

    def get_variables_for_processor(self, processor_id: str) -> List[str]:
        """Get all variables used by a specific processor.

        Args:
            processor_id: Processor ID

        Returns:
            List of variable names
        """
        results = self.analyze()
        return results["by_processor"].get(processor_id, [])

    def get_processors_using_variable(self, variable_name: str) -> List[Dict[str, Any]]:
        """Get all processors that use a specific variable.

        Args:
            variable_name: Variable name

        Returns:
            List of processor info dicts
        """
        results = self.analyze()
        return results["by_variable"].get(variable_name, [])

    def get_variable_definition(self, variable_name: str) -> Dict[str, Any]:
        """Get definition information for a variable.

        Args:
            variable_name: Variable name

        Returns:
            Dict with variable definition info, or empty dict if not found
        """
        results = self.analyze()
        return results["defined_variables"].get(variable_name, {})

    def get_undefined_variables(self) -> List[str]:
        """Get list of variables that are used but not defined.

        Returns:
            List of undefined variable names
        """
        results = self.analyze()
        return results["undefined"]

    def validate_variables(self) -> Dict[str, Any]:
        """Validate that all used variables are defined.

        Returns:
            Dict with validation results
        """
        results = self.analyze()
        undefined = results["undefined"]

        is_valid = len(undefined) == 0

        return {
            "is_valid": is_valid,
            "undefined_variables": undefined,
            "message": (
                "All variables are defined"
                if is_valid
                else f"Found {len(undefined)} undefined variables"
            ),
        }
