"""Table extraction analyzer.

Extracts database table references from processor configurations.
"""

import re
from typing import Any, Dict, List, Set
from analyzers.base import BaseAnalyzer


class TableExtractionAnalyzer(BaseAnalyzer):
    """Extracts database table names from processors."""

    # Properties that commonly contain table names
    TABLE_PROPERTIES = [
        "Table Name",
        "table-name",
        "tableName",
        "Target Table",
        "target-table",
        "Source Table",
        "source-table",
    ]

    # Properties that contain SQL (may reference tables)
    SQL_PROPERTIES = [
        "SQL select query",
        "sql-select-query",
        "SQL Statement",
        "sql-statement",
        "SQL Query",
        "sql-query",
    ]

    def analyze(self) -> Dict[str, Any]:
        """Extract all table references from processors.

        Returns:
            Dict with keys:
                - tables: Set of all unique table names found
                - by_processor: Dict mapping processor ID to list of tables it references
                - by_table: Dict mapping table name to list of processors that reference it
                - sources: List of processors that read from tables
                - targets: List of processors that write to tables
        """
        all_processors = self._get_all_processors()

        tables: Set[str] = set()
        by_processor: Dict[str, List[str]] = {}
        by_table: Dict[str, List[Dict[str, Any]]] = {}
        sources = []
        targets = []

        for proc in all_processors:
            proc_id = proc.get("id")
            proc_type = proc.get("type", "").split(".")[-1]
            proc_name = proc.get("name", "")

            # Extract tables from this processor
            proc_tables = self._extract_tables_from_processor(proc)

            if proc_tables:
                tables.update(proc_tables)
                by_processor[proc_id] = list(proc_tables)

                # Categorize as source or target
                is_source = self._is_source_processor(proc_type)
                is_target = self._is_target_processor(proc_type)

                proc_info = {
                    "id": proc_id,
                    "name": proc_name,
                    "type": proc_type,
                    "tables": list(proc_tables),
                }

                if is_source:
                    sources.append(proc_info)

                if is_target:
                    targets.append(proc_info)

                # Map tables to processors
                for table in proc_tables:
                    if table not in by_table:
                        by_table[table] = []
                    by_table[table].append(proc_info)

        return {
            "tables": sorted(list(tables)),
            "by_processor": by_processor,
            "by_table": by_table,
            "sources": sources,
            "targets": targets,
            "table_count": len(tables),
        }

    def _extract_tables_from_processor(self, processor: Dict[str, Any]) -> Set[str]:
        """Extract table names from a single processor.

        Args:
            processor: Processor dict

        Returns:
            Set of table names
        """
        tables = set()
        config = processor.get("config", {})
        properties = config.get("properties", {})

        # Check table name properties
        for prop_name in self.TABLE_PROPERTIES:
            value = properties.get(prop_name, "")
            if value and value.strip():
                # Clean and add table name
                table = self._clean_table_name(value)
                if table:
                    tables.add(table)

        # Check SQL properties for table references
        for prop_name in self.SQL_PROPERTIES:
            value = properties.get(prop_name, "")
            if value:
                sql_tables = self._extract_tables_from_sql(value)
                tables.update(sql_tables)

        return tables

    def _clean_table_name(self, table_name: str) -> str:
        """Clean and normalize a table name.

        Args:
            table_name: Raw table name

        Returns:
            Cleaned table name
        """
        # Remove whitespace
        table = table_name.strip()

        # Remove quotes
        table = table.strip("'\"")

        # Handle schema.table format
        if "." in table:
            parts = table.split(".")
            # Return schema.table format
            if len(parts) == 2:
                return f"{parts[0]}.{parts[1]}"
            # For database.schema.table, return schema.table
            elif len(parts) == 3:
                return f"{parts[1]}.{parts[2]}"

        return table

    def _extract_tables_from_sql(self, sql: str) -> Set[str]:
        """Extract table names from SQL query.

        Args:
            sql: SQL query string

        Returns:
            Set of table names
        """
        tables = set()

        # Simple regex patterns for common SQL patterns
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

    def _is_sql_keyword(self, word: str) -> bool:
        """Check if word is a common SQL keyword.

        Args:
            word: Word to check

        Returns:
            True if it's a SQL keyword
        """
        keywords = {
            "SELECT", "WHERE", "AND", "OR", "AS", "ON", "IN", "EXISTS",
            "NOT", "NULL", "IS", "LIKE", "BETWEEN", "CASE", "WHEN", "THEN",
            "ELSE", "END", "GROUP", "ORDER", "BY", "HAVING", "LIMIT"
        }
        return word.upper() in keywords

    def _is_source_processor(self, proc_type: str) -> bool:
        """Check if processor reads from database (source).

        Args:
            proc_type: Short processor type name

        Returns:
            True if it's a source processor
        """
        source_types = [
            "ExecuteSQL",
            "QueryDatabaseTable",
            "QueryDatabaseTableRecord",
            "ExecuteSQLRecord",
        ]
        return any(t in proc_type for t in source_types)

    def _is_target_processor(self, proc_type: str) -> bool:
        """Check if processor writes to database (target).

        Args:
            proc_type: Short processor type name

        Returns:
            True if it's a target processor
        """
        target_types = [
            "PutSQL",
            "PutDatabaseRecord",
        ]
        return any(t in proc_type for t in target_types)

    def get_tables_for_processor(self, processor_id: str) -> List[str]:
        """Get tables referenced by a specific processor.

        Args:
            processor_id: Processor ID

        Returns:
            List of table names
        """
        results = self.analyze()
        return results["by_processor"].get(processor_id, [])

    def get_processors_for_table(self, table_name: str) -> List[Dict[str, Any]]:
        """Get all processors that reference a specific table.

        Args:
            table_name: Table name

        Returns:
            List of processor info dicts
        """
        results = self.analyze()
        return results["by_table"].get(table_name, [])
