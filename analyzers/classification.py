"""Processor classification analyzer.

Classifies NiFi processors into functional categories based on their type.
"""

from typing import Any, Dict, List
from analyzers.base import BaseAnalyzer


class ClassificationAnalyzer(BaseAnalyzer):
    """Classifies processors into functional categories."""

    # Processor type classifications
    CLASSIFICATIONS = {
        "database": [
            "ExecuteSQL",
            "PutSQL",
            "PutDatabaseRecord",
            "QueryDatabaseTable",
            "QueryDatabaseTableRecord",
            "ExecuteSQLRecord",
            "ConvertJSONToSQL",
        ],
        "transformation": [
            "ConvertRecord",
            "JoltTransformRecord",
            "UpdateRecord",
            "QueryRecord",
            "LookupRecord",
            "SplitRecord",
            "MergeRecord",
            "ConvertJSONToSQL",
            "EvaluateJsonPath",
            "UpdateAttribute",
            "RouteOnAttribute",
            "ReplaceText",
        ],
        "flow_control": [
            "RouteOnAttribute",
            "RouteOnContent",
            "ControlRate",
            "Wait",
            "Notify",
            "DistributeLoad",
        ],
        "file_system": [
            "GetFile",
            "PutFile",
            "FetchFile",
            "ListFile",
            "GetSFTP",
            "PutSFTP",
            "FetchSFTP",
            "ListSFTP",
        ],
        "messaging": [
            "ConsumeKafka",
            "PublishKafka",
            "GetJMSQueue",
            "PutJMS",
            "ConsumeMQTT",
            "PublishMQTT",
        ],
        "http": [
            "InvokeHTTP",
            "HandleHttpRequest",
            "HandleHttpResponse",
            "ListenHTTP",
            "PostHTTP",
        ],
        "cloud": [
            "PutS3Object",
            "FetchS3Object",
            "ListS3",
            "DeleteS3Object",
            "PutAzureBlobStorage",
            "FetchAzureBlobStorage",
        ],
        "parsing": [
            "ParseCEF",
            "ParseSyslog",
            "ParseEvtx",
            "ExtractText",
            "SplitText",
            "SplitJson",
            "SplitXml",
        ],
        "logging": [
            "LogAttribute",
            "LogMessage",
            "PutSyslog",
        ],
        "scripting": [
            "ExecuteScript",
            "ExecuteGroovyScript",
            "InvokeScriptedProcessor",
        ],
    }

    def analyze(self) -> Dict[str, Any]:
        """Classify all processors by functional category.

        Returns:
            Dict with keys:
                - by_category: Dict mapping category to list of processors
                - by_processor: Dict mapping processor ID to category
                - summary: Dict with counts per category
                - unclassified: List of processors that don't match any category
        """
        all_processors = self._get_all_processors()

        by_category = {category: [] for category in self.CLASSIFICATIONS.keys()}
        by_category["unclassified"] = []
        by_processor = {}

        for proc in all_processors:
            proc_type = proc.get("type", "")
            proc_type_short = proc_type.split(".")[-1]  # Get class name without package

            # Find matching category
            category = self._classify_processor(proc_type_short)

            # Store processor info
            proc_info = {
                "id": proc.get("id"),
                "name": proc.get("name"),
                "type": proc_type,
                "type_short": proc_type_short,
                "state": proc.get("state"),
            }

            by_category[category].append(proc_info)
            by_processor[proc.get("id")] = category

        # Calculate summary
        summary = {
            category: len(processors)
            for category, processors in by_category.items()
        }

        return {
            "by_category": by_category,
            "by_processor": by_processor,
            "summary": summary,
            "total_processors": len(all_processors),
        }

    def _classify_processor(self, proc_type_short: str) -> str:
        """Classify a processor by its short type name.

        Args:
            proc_type_short: Short processor type (class name only)

        Returns:
            Category name, or "unclassified" if no match
        """
        for category, type_patterns in self.CLASSIFICATIONS.items():
            for pattern in type_patterns:
                if pattern in proc_type_short:
                    return category

        return "unclassified"

    def get_processors_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all processors in a specific category.

        Args:
            category: Category name (e.g., "database", "transformation")

        Returns:
            List of processor info dicts
        """
        results = self.analyze()
        return results["by_category"].get(category, [])

    def get_processor_category(self, processor_id: str) -> str:
        """Get the category for a specific processor.

        Args:
            processor_id: Processor ID

        Returns:
            Category name
        """
        results = self.analyze()
        return results["by_processor"].get(processor_id, "unclassified")
