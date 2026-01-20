"""Data lineage analyzer.

Analyzes data flow lineage between tables through processors.
"""

from typing import Any, Dict, List, Set, Tuple
from analyzers.base import BaseAnalyzer
from analyzers.table_extraction import TableExtractionAnalyzer


class LineageAnalyzer(BaseAnalyzer):
    """Analyzes table-to-table data lineage."""

    def __init__(self, template_dto: Dict[str, Any]):
        """Initialize lineage analyzer.

        Args:
            template_dto: NiFi flow in TemplateDTO format
        """
        super().__init__(template_dto)
        self.table_analyzer = TableExtractionAnalyzer(template_dto)

    def analyze(self) -> Dict[str, Any]:
        """Analyze data lineage between tables.

        Returns:
            Dict with keys:
                - lineages: List of lineage paths (source -> target)
                - by_source: Dict mapping source table to list of targets
                - by_target: Dict mapping target table to list of sources
                - graph: Dict representing the lineage graph
        """
        # Get table information
        table_info = self.table_analyzer.analyze()
        sources = table_info["sources"]  # Processors that read from tables
        targets = table_info["targets"]  # Processors that write to tables

        # Build lineage by following connections
        lineages = []
        by_source: Dict[str, Set[str]] = {}
        by_target: Dict[str, Set[str]] = {}

        # For each source processor, trace downstream to find target processors
        for source_proc in sources:
            source_id = source_proc["id"]
            source_tables = source_proc["tables"]

            # Find all downstream target processors
            downstream_targets = self._find_downstream_targets(source_id, targets)

            # Create lineage entries for each source-target pair
            for source_table in source_tables:
                for target_proc in downstream_targets:
                    target_tables = target_proc["tables"]

                    for target_table in target_tables:
                        # Create lineage record
                        lineage = {
                            "source_table": source_table,
                            "target_table": target_table,
                            "source_processor": {
                                "id": source_proc["id"],
                                "name": source_proc["name"],
                                "type": source_proc["type"],
                            },
                            "target_processor": {
                                "id": target_proc["id"],
                                "name": target_proc["name"],
                                "type": target_proc["type"],
                            },
                            "path": self._find_path(source_id, target_proc["id"]),
                        }

                        lineages.append(lineage)

                        # Update by_source and by_target mappings
                        if source_table not in by_source:
                            by_source[source_table] = set()
                        by_source[source_table].add(target_table)

                        if target_table not in by_target:
                            by_target[target_table] = set()
                        by_target[target_table].add(source_table)

        # Convert sets to lists for JSON serialization
        by_source_list = {k: sorted(list(v)) for k, v in by_source.items()}
        by_target_list = {k: sorted(list(v)) for k, v in by_target.items()}

        # Build graph representation
        graph = self._build_lineage_graph(lineages)

        return {
            "lineages": lineages,
            "by_source": by_source_list,
            "by_target": by_target_list,
            "graph": graph,
            "lineage_count": len(lineages),
        }

    def _find_downstream_targets(
        self,
        source_id: str,
        target_processors: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find all target processors downstream from a source processor.

        Args:
            source_id: Source processor ID
            target_processors: List of all target processor info dicts

        Returns:
            List of target processors that are downstream from source
        """
        target_ids = {proc["id"] for proc in target_processors}
        downstream_targets = []

        # BFS to find all reachable processors
        visited = set()
        queue = [source_id]

        while queue:
            current_id = queue.pop(0)

            if current_id in visited:
                continue
            visited.add(current_id)

            # If this is a target processor, add it
            if current_id in target_ids:
                for proc in target_processors:
                    if proc["id"] == current_id:
                        downstream_targets.append(proc)
                        break

            # Find downstream processors via connections
            downstream_ids = self._get_downstream_processor_ids(current_id)
            queue.extend(downstream_ids)

        return downstream_targets

    def _get_downstream_processor_ids(self, processor_id: str) -> List[str]:
        """Get IDs of processors directly downstream from given processor.

        Args:
            processor_id: Processor ID

        Returns:
            List of downstream processor IDs
        """
        downstream_ids = []
        all_connections = self._get_all_connections()

        for conn in all_connections:
            source = conn.get("source", {})
            dest = conn.get("destination", {})

            if source.get("id") == processor_id:
                dest_id = dest.get("id")
                if dest_id:
                    downstream_ids.append(dest_id)

        return downstream_ids

    def _find_path(self, source_id: str, target_id: str) -> List[str]:
        """Find path of processor IDs from source to target.

        Args:
            source_id: Source processor ID
            target_id: Target processor ID

        Returns:
            List of processor IDs in path (including source and target)
        """
        # BFS to find shortest path
        visited = set()
        queue = [(source_id, [source_id])]

        while queue:
            current_id, path = queue.pop(0)

            if current_id == target_id:
                return path

            if current_id in visited:
                continue
            visited.add(current_id)

            # Get downstream processors
            downstream_ids = self._get_downstream_processor_ids(current_id)

            for next_id in downstream_ids:
                if next_id not in visited:
                    queue.append((next_id, path + [next_id]))

        return []  # No path found

    def _build_lineage_graph(self, lineages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build graph representation of table lineage.

        Args:
            lineages: List of lineage records

        Returns:
            Dict with nodes and edges for graph visualization
        """
        nodes = set()
        edges = []

        for lineage in lineages:
            source = lineage["source_table"]
            target = lineage["target_table"]

            nodes.add(source)
            nodes.add(target)

            edges.append({
                "source": source,
                "target": target,
                "source_processor": lineage["source_processor"]["name"],
                "target_processor": lineage["target_processor"]["name"],
            })

        return {
            "nodes": [{"id": node, "label": node} for node in sorted(nodes)],
            "edges": edges,
        }

    def get_lineage_for_table(self, table_name: str) -> Dict[str, Any]:
        """Get lineage information for a specific table.

        Args:
            table_name: Table name

        Returns:
            Dict with upstream and downstream lineage for the table
        """
        results = self.analyze()

        upstream = results["by_target"].get(table_name, [])
        downstream = results["by_source"].get(table_name, [])

        # Find related lineage records
        related_lineages = [
            lineage for lineage in results["lineages"]
            if lineage["source_table"] == table_name or lineage["target_table"] == table_name
        ]

        return {
            "table": table_name,
            "upstream_tables": upstream,
            "downstream_tables": downstream,
            "lineages": related_lineages,
        }

    def get_source_tables(self) -> List[str]:
        """Get all tables that are sources (have no upstream dependencies).

        Returns:
            List of source table names
        """
        results = self.analyze()
        by_source = results["by_source"]
        by_target = results["by_target"]

        # Tables in by_source but not in by_target are source tables
        source_tables = set(by_source.keys()) - set(by_target.keys())
        return sorted(list(source_tables))

    def get_sink_tables(self) -> List[str]:
        """Get all tables that are sinks (have no downstream dependencies).

        Returns:
            List of sink table names
        """
        results = self.analyze()
        by_source = results["by_source"]
        by_target = results["by_target"]

        # Tables in by_target but not in by_source are sink tables
        sink_tables = set(by_target.keys()) - set(by_source.keys())
        return sorted(list(sink_tables))
