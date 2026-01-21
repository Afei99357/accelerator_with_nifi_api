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

        # Search ALL properties for tables, but be smart about context
        all_properties = self._get_all_properties(processor)

        for prop_name, prop_value in all_properties.items():
            if prop_value and isinstance(prop_value, str):
                # Only extract tables if this looks like SQL content or table property
                if self._is_sql_or_table_property(prop_name, prop_value):
                    tables.update(self._extract_tables_from_text(prop_value))

                # Also try JDBC URL extraction
                tables.update(self._extract_from_jdbc_url(prop_value))

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

    def _is_sql_or_table_property(self, prop_name: str, prop_value: str) -> bool:
        """Check if a property likely contains SQL or table references.

        Args:
            prop_name: Property name
            prop_value: Property value

        Returns:
            True if this property should be scanned for tables
        """
        prop_name_lower = prop_name.lower()

        # Check for SQL-related property names
        sql_keywords = [
            "sql",
            "query",
            "statement",
            "table",
            "database",
            "schema",
            "metadata",
        ]
        if any(kw in prop_name_lower for kw in sql_keywords):
            return True

        # Check if value contains SQL keywords
        if not prop_value or not isinstance(prop_value, str):
            return False

        value_upper = prop_value.upper()
        sql_indicators = [
            "SELECT ",
            "INSERT ",
            "UPDATE ",
            "DELETE ",
            "CREATE TABLE",
            "DROP TABLE",
            "ALTER TABLE",
            "FROM ",
            "INVALIDATE METADATA",
            "REFRESH ",
        ]

        return any(indicator in value_upper for indicator in sql_indicators)

    def _extract_tables_from_text(self, text: str) -> Set[str]:
        """Extract table names from any text using multiple patterns.

        This method searches for tables in various formats:
        - schema.table or db.table patterns (only in SQL context)
        - SQL statements with keywords
        - Impala INVALIDATE METADATA statements

        Args:
            text: Text to search

        Returns:
            Set of table names found
        """
        if not text or not isinstance(text, str):
            return set()

        tables = set()

        # Only extract schema.table patterns if we're confident this is SQL
        # (not from generic Groovy/Java code)
        if self._looks_like_sql(text):
            # Pattern 1: schema.table or db.table (word boundaries)
            # Matches: be_aoi.bin_die_list_tbl, ${db_temp}.MES_${db_table}
            schema_table_pattern = r"\b([a-z_$][a-z0-9_$]*\.[a-z_$][a-z0-9_$]*)\b"
            matches = re.findall(schema_table_pattern, text, re.IGNORECASE)
            for match in matches:
                # Filter out common non-table patterns
                if not self._is_likely_false_positive(match):
                    tables.add(match)

        # Pattern 2: SQL keywords + table name (more reliable)
        sql_patterns = [
            r"FROM\s+([a-z_$][a-z0-9_.$]*)",
            r"INTO\s+([a-z_$][a-z0-9_.$]*)",
            r"TABLE\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?([a-z_$][a-z0-9_.$]*)",
            r"UPDATE\s+([a-z_$][a-z0-9_.$]*)\s+SET",
            r"OVERWRITE\s+TABLE\s+([a-z_$][a-z0-9_.$]*)",
            r"METADATA\s+([a-z_$][a-z0-9_.$]*)",  # For INVALIDATE METADATA
        ]

        for pattern in sql_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                table = match.strip()
                # Skip SQL keywords and apply filtering
                if not self._is_sql_keyword(
                    table
                ) and not self._is_likely_false_positive(table):
                    tables.add(table)

        return tables

    def _looks_like_sql(self, text: str) -> bool:
        """Check if text looks like SQL (not Java/Groovy code).

        Args:
            text: Text to check

        Returns:
            True if this looks like SQL
        """
        text_upper = text.upper()

        # If it contains Java/Groovy patterns, it's NOT SQL
        code_indicators = [
            "IMPORT ",
            "FLOWFILE",
            ".GETATTRIBUTE",
            ".PUTATTRIBUTE",
            "SESSION.",
            "BINDING.",
            "RESULTS.",
            "SCRIPT.",
            "EXECUTION.",
            "FUNCTION(",
            "DEF ",
            "PUBLIC ",
            "PRIVATE ",
            "CLASS ",
        ]

        if any(indicator in text_upper for indicator in code_indicators):
            return False

        # Check for SQL keywords
        sql_keywords = [
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "CREATE",
            "DROP",
            "ALTER",
            "FROM",
            "WHERE",
            "INVALIDATE",
        ]

        return any(keyword in text_upper for keyword in sql_keywords)

    def _extract_from_jdbc_url(self, text: str) -> Set[str]:
        """Extract schema/database names from JDBC URLs.

        Args:
            text: Text that may contain JDBC URL

        Returns:
            Set of schema/database names
        """
        if not text or "jdbc:" not in text.lower():
            return set()

        schemas = set()

        # Pattern: jdbc:oracle:thin:@host:port:SCHEMA
        oracle_match = re.search(
            r"jdbc:oracle:thin:@[^:]+:\d+:([^/\s;]+)", text, re.IGNORECASE
        )
        if oracle_match:
            schemas.add(oracle_match.group(1))

        # Pattern: jdbc:mysql://host:port/DATABASE
        mysql_match = re.search(r"jdbc:mysql://[^/]+/([^?\s;]+)", text, re.IGNORECASE)
        if mysql_match:
            schemas.add(mysql_match.group(1))

        # Pattern: jdbc:postgresql://host:port/DATABASE
        postgres_match = re.search(
            r"jdbc:postgresql://[^/]+/([^?\s;]+)", text, re.IGNORECASE
        )
        if postgres_match:
            schemas.add(postgres_match.group(1))

        return schemas

    def _is_likely_false_positive(self, table_name: str) -> bool:
        """Check if a table-like pattern is likely a false positive.

        Args:
            table_name: Potential table name

        Returns:
            True if likely not a real table name
        """
        table_lower = table_name.lower()

        # Filter out single character or very short names
        if len(table_name) <= 1:
            return True

        # Filter out Java/Groovy class and package prefixes
        java_prefixes = [
            "java.",
            "org.",
            "com.",
            "nifi.",
            "apache.",
            "system.",
            "file.",
            "localdate.",
            "localdatetime.",
            "datetimeformatter.",
            "string.",
            "integer.",
            "boolean.",
            "format.",
        ]
        if any(table_lower.startswith(fp) for fp in java_prefixes):
            return True

        # Filter out common NiFi/Groovy code patterns
        code_patterns = [
            "session.",
            "flowfile.",
            "binding.",
            "results.",
            "script.",
            "execution.",
            "e.",  # Exception handling (e.getCause, e.toString)
            "log.",
            "logger.",
            "context.",
        ]
        if any(table_lower.startswith(cp) for cp in code_patterns):
            return True

        # Filter out property/config references
        property_patterns = [
            "db.name",
            "db.table",
            "drop.table",
            "create.table",
            "temp.table",
            "table.create",
            "table.merge",
            "partition.sql",
            "create.sql",
            "drop.sql",
            "merge.sql",
            "root.nifi",
            "queue.name",
            "mapred.job",
            "hadoop_nifi_be_svc.keytab",
        ]
        if table_lower in property_patterns:
            return True

        # Filter out file extensions (*.sql, *.json, *.xml, *.jar, etc.)
        file_extensions = [
            ".sql",
            ".json",
            ".xml",
            ".jar",
            ".keytab",
            ".txt",
            ".csv",
            ".avro",
            ".parquet",
        ]
        if any(table_lower.endswith(ext) for ext in file_extensions):
            return True

        # Filter out common property suffixes
        if any(
            table_lower.endswith(suffix)
            for suffix in [".value", ".split", ".evaluateattributeexpressions"]
        ):
            return True

        # Filter out SQL keywords
        sql_keywords = {
            "insert",
            "select",
            "update",
            "delete",
            "refresh",
            "create",
            "drop",
            "alter",
            "truncate",
            "merge",
        }
        if table_lower in sql_keywords:
            return True

        # Filter out common generic words that appear in code
        generic_words = {
            "temp",
            "script",
            "create",
            "arc",  # Could be code/config
            "osd",  # Could be code/config
        }
        if table_lower in generic_words:
            return True

        # Filter out patterns with common variable/property naming
        # (dateName.value, dateYmd.value, etc.)
        if re.match(r"^date[a-z]+\.value$", table_lower):
            return True

        # Filter out Sqoop command patterns
        if "sqoop" in table_lower:
            return True

        # Filter out SQL table aliases (t1.column, t2.column, th.column, etc.)
        # These are alias.column references in SQL JOINs, not table names
        # Common SQL aliases are very short (1-2 chars): t1, t2, th, hm, etc.
        if "." in table_name:
            parts = table_name.split(".")
            if len(parts) == 2:
                prefix, suffix = parts
                prefix_lower = prefix.lower()

                # Very short prefixes (1-2 chars) are almost always aliases
                # Exception: allow common schema prefixes
                if len(prefix) <= 2 and prefix_lower not in ["db"]:
                    return True

                # 3-char prefixes that don't look like schema names
                if len(prefix) == 3:
                    # Real schemas usually have underscores or longer names
                    # Aliases are usually just letters (t1, th, hm, abc, etc.)
                    if "_" not in prefix and not prefix.endswith("_db"):
                        # If suffix doesn't have underscores, it's probably alias.column
                        if "_" not in suffix:
                            return True

        # Filter out specific known file/config patterns
        specific_false_positives = {
            "avro.schema",
            "site.xml",
            "tools.jar",
        }
        if table_lower in specific_false_positives:
            return True

        return False

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
