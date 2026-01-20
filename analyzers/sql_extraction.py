"""SQL query extraction analyzer.

Extracts SQL queries from processor configurations.
"""

import re
from typing import Any, Dict, List

from analyzers.base import BaseAnalyzer


class SQLExtractionAnalyzer(BaseAnalyzer):
    """Extracts SQL queries from processors."""

    # Properties that commonly contain SQL queries
    SQL_PROPERTIES = [
        "SQL select query",
        "sql-select-query",
        "SQL Statement",
        "sql-statement",
        "SQL Query",
        "sql-query",
        "SQL Pre-Query",
        "SQL Post-Query",
    ]

    def analyze(self) -> Dict[str, Any]:
        """Extract all SQL queries from processors.

        Returns:
            Dict with keys:
                - queries: List of query info dicts
                - by_processor: Dict mapping processor ID to list of queries
                - by_type: Dict mapping SQL type (SELECT, INSERT, etc.) to queries
                - total_count: Total number of queries found
        """
        all_processors = self._get_all_processors()

        queries = []
        by_processor: Dict[str, List[Dict[str, Any]]] = {}
        by_type: Dict[str, List[Dict[str, Any]]] = {
            "SELECT": [],
            "INSERT": [],
            "UPDATE": [],
            "DELETE": [],
            "CREATE": [],
            "DROP": [],
            "UNKNOWN": [],
        }

        for proc in all_processors:
            proc_id = proc.get("id")
            proc_name = proc.get("name", "")
            proc_type = proc.get("type", "").split(".")[-1]

            # Extract SQL from this processor
            proc_queries = self._extract_sql_from_processor(proc)

            if proc_queries:
                by_processor[proc_id] = []

                for query_info in proc_queries:
                    # Add processor context
                    query_with_context = {
                        **query_info,
                        "processor_id": proc_id,
                        "processor_name": proc_name,
                        "processor_type": proc_type,
                    }

                    queries.append(query_with_context)
                    by_processor[proc_id].append(query_with_context)

                    # Categorize by SQL type
                    sql_type = query_info.get("type", "UNKNOWN")
                    by_type[sql_type].append(query_with_context)

        return {
            "queries": queries,
            "by_processor": by_processor,
            "by_type": by_type,
            "total_count": len(queries),
        }

    def _extract_sql_from_processor(
        self, processor: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract SQL queries from a single processor.

        Args:
            processor: Processor dict

        Returns:
            List of query info dicts
        """
        queries = []
        config = processor.get("config", {})
        properties = config.get("properties", {})

        # Check SQL properties
        for prop_name in self.SQL_PROPERTIES:
            value = properties.get(prop_name, "")
            if value and value.strip():
                query_info = self._parse_sql_query(value, prop_name)
                if query_info:
                    queries.append(query_info)

        return queries

    def _parse_sql_query(self, sql: str, property_name: str) -> Dict[str, Any]:
        """Parse SQL query to extract metadata.

        Args:
            sql: SQL query string
            property_name: Property name where SQL was found

        Returns:
            Dict with query metadata
        """
        # Clean SQL
        sql_clean = sql.strip()

        if not sql_clean:
            return None

        # Determine SQL type
        sql_type = self._determine_sql_type(sql_clean)

        # Extract tables referenced
        tables = self._extract_table_references(sql_clean)

        # Check if parameterized (contains variables)
        is_parameterized = "${" in sql_clean

        # Extract variables used
        variables = self._extract_variables(sql_clean)

        return {
            "sql": sql_clean,
            "type": sql_type,
            "property_name": property_name,
            "tables": list(tables),
            "is_parameterized": is_parameterized,
            "variables": variables,
            "length": len(sql_clean),
        }

    def _determine_sql_type(self, sql: str) -> str:
        """Determine the type of SQL statement.

        Args:
            sql: SQL query string

        Returns:
            SQL type (SELECT, INSERT, UPDATE, etc.)
        """
        sql_upper = sql.upper().strip()

        if sql_upper.startswith("SELECT"):
            return "SELECT"
        elif sql_upper.startswith("INSERT"):
            return "INSERT"
        elif sql_upper.startswith("UPDATE"):
            return "UPDATE"
        elif sql_upper.startswith("DELETE"):
            return "DELETE"
        elif sql_upper.startswith("CREATE"):
            return "CREATE"
        elif sql_upper.startswith("DROP"):
            return "DROP"
        elif sql_upper.startswith("TRUNCATE"):
            return "TRUNCATE"
        elif sql_upper.startswith("MERGE"):
            return "MERGE"
        elif sql_upper.startswith("WITH"):
            return "SELECT"  # CTE
        else:
            return "UNKNOWN"

    def _extract_table_references(self, sql: str) -> set:
        """Extract table names referenced in SQL.

        Args:
            sql: SQL query string

        Returns:
            Set of table names
        """
        tables = set()

        # Patterns for table references
        patterns = [
            r"FROM\s+([a-zA-Z0-9_\.]+)",
            r"JOIN\s+([a-zA-Z0-9_\.]+)",
            r"INTO\s+([a-zA-Z0-9_\.]+)",
            r"UPDATE\s+([a-zA-Z0-9_\.]+)",
            r"TABLE\s+([a-zA-Z0-9_\.]+)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, sql, re.IGNORECASE)
            for match in matches:
                table = match.group(1).strip()
                # Skip SQL keywords and variables
                if not self._is_sql_keyword(table) and not table.startswith("${"):
                    tables.add(table)

        return tables

    def _extract_variables(self, sql: str) -> List[str]:
        """Extract NiFi expression language variables from SQL.

        Args:
            sql: SQL query string

        Returns:
            List of variable names
        """
        # Match ${variable_name} pattern
        pattern = r"\$\{([a-zA-Z0-9_\.]+)\}"
        matches = re.findall(pattern, sql)
        return list(set(matches))  # Remove duplicates

    def _is_sql_keyword(self, word: str) -> bool:
        """Check if word is a common SQL keyword.

        Args:
            word: Word to check

        Returns:
            True if it's a SQL keyword
        """
        keywords = {
            "SELECT",
            "WHERE",
            "AND",
            "OR",
            "AS",
            "ON",
            "IN",
            "EXISTS",
            "NOT",
            "NULL",
            "IS",
            "LIKE",
            "BETWEEN",
            "CASE",
            "WHEN",
            "THEN",
            "ELSE",
            "END",
            "GROUP",
            "ORDER",
            "BY",
            "HAVING",
            "LIMIT",
            "INNER",
            "OUTER",
            "LEFT",
            "RIGHT",
            "FULL",
            "CROSS",
        }
        return word.upper() in keywords

    def get_queries_by_type(self, sql_type: str) -> List[Dict[str, Any]]:
        """Get all queries of a specific type.

        Args:
            sql_type: SQL type (SELECT, INSERT, UPDATE, etc.)

        Returns:
            List of query info dicts
        """
        results = self.analyze()
        return results["by_type"].get(sql_type.upper(), [])

    def get_queries_for_processor(self, processor_id: str) -> List[Dict[str, Any]]:
        """Get all queries from a specific processor.

        Args:
            processor_id: Processor ID

        Returns:
            List of query info dicts
        """
        results = self.analyze()
        return results["by_processor"].get(processor_id, [])

    def get_parameterized_queries(self) -> List[Dict[str, Any]]:
        """Get all queries that use NiFi expression language variables.

        Returns:
            List of query info dicts
        """
        results = self.analyze()
        return [q for q in results["queries"] if q.get("is_parameterized")]
