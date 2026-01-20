"""Data models and utilities for NiFi template conversion."""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class IdMapper:
    """Maps GUID IDs to user-friendly IDs and maintains reverse mapping."""

    def __init__(self, use_friendly_ids: bool = False):
        self.use_friendly_ids = use_friendly_ids
        self._counters = {
            "processor": 0,
            "processGroup": 0,
            "funnel": 0,
            "inputPort": 0,
            "outputPort": 0,
            "connection": 0,
        }
        self._forward_map: Dict[str, str] = {}  # original_id -> friendly_id
        self._reverse_map: Dict[str, str] = {}  # friendly_id -> original_id

    def get_friendly_id(self, original_id: str, component_type: str) -> str:
        """Get or create a friendly ID for the given original ID and component type."""
        if not original_id or not self.use_friendly_ids:
            return original_id

        # If already mapped, return existing friendly ID
        if original_id in self._forward_map:
            return self._forward_map[original_id]

        # Generate new friendly ID based on component type
        prefix_map = {
            "processor": "p",
            "processGroup": "g",
            "funnel": "f",
            "inputPort": "ip",
            "outputPort": "op",
            "connection": "c",
        }

        prefix = prefix_map.get(component_type)
        if prefix is None:
            # Unknown type, return original
            return original_id

        # Generate friendly ID
        counter = self._counters[component_type]
        friendly_id = f"{prefix}_{counter}"
        self._counters[component_type] += 1

        # Store mappings
        self._forward_map[original_id] = friendly_id
        self._reverse_map[friendly_id] = original_id

        return friendly_id

    def lookup(self, original_id: str) -> str:
        """Look up the friendly ID for an original ID, or return original if not found."""
        if not original_id:
            return original_id
        return self._forward_map.get(original_id, original_id)

    def lookup_or_map_by_type(self, original_id: str, component_type: str) -> str:
        """Look up or map an ID based on component type.

        Used for connections that reference components.
        """
        if not original_id:
            return original_id
        # If already mapped, return it
        if original_id in self._forward_map:
            return self._forward_map[original_id]
        # Map it based on type
        return self.get_friendly_id(original_id, component_type)

    def get_reverse_map(self) -> Dict[str, str]:
        """Get the reverse mapping (friendly_id -> original_id)."""
        return self._reverse_map.copy()


def _build_pass_through_connections(
    all_connections: List[Dict[str, Any]],
    pass_through_ids: set,
    parent_group_id: str,
    id_mapper: IdMapper,
) -> List[Dict[str, Any]]:
    """
    Build pass-through connectivity by bypassing funnels, input ports, and output ports.

    For connections that go through pass-through components, creates direct connections
    that bypass them. Handles chains of pass-through components.
    """
    # Build adjacency maps for tracing through pass-through components
    # incoming[component_id] = list of connections that end at this component
    # outgoing[component_id] = list of connections that start from this component
    incoming: Dict[str, List[Dict[str, Any]]] = {}
    outgoing: Dict[str, List[Dict[str, Any]]] = {}

    for conn in all_connections:
        source_id = conn.get("source", {}).get("id")
        dest_id = conn.get("destination", {}).get("id")

        if source_id:
            if source_id not in outgoing:
                outgoing[source_id] = []
            outgoing[source_id].append(conn)

        if dest_id:
            if dest_id not in incoming:
                incoming[dest_id] = []
            incoming[dest_id].append(conn)

    def find_ultimate_sources(
        component_id: str, visited: set = None
    ) -> List[Dict[str, Any]]:
        """Find all ultimate sources (non-pass-through) that feed into this component."""
        if visited is None:
            visited = set()

        if component_id in visited:
            return []
        visited.add(component_id)

        # If this is not a pass-through component, it's an ultimate source
        if component_id not in pass_through_ids:
            # Get the source info from a connection where this component is the source (outgoing)
            # This gives us the correct type and groupId for this component as a source
            source_info = None
            for conn in outgoing.get(component_id, []):
                source_info = conn.get("source", {}).copy()
                source_info["id"] = component_id  # Ensure ID matches
                break
            # If no outgoing connection, try to infer from incoming (where it's destination)
            if not source_info:
                for conn in incoming.get(component_id, []):
                    # Use the destination info but with this component's ID
                    dest_info = conn.get("destination", {})
                    source_info = {
                        "id": component_id,
                        "groupId": dest_info.get("groupId"),
                        "type": dest_info.get("type", "PROCESSOR"),
                    }
                    break
            if not source_info:
                source_info = {"id": component_id, "groupId": None, "type": "PROCESSOR"}
            return [{"id": component_id, "source": source_info}]

        # Otherwise, trace back through incoming connections
        sources = []
        for conn in incoming.get(component_id, []):
            source_id = conn.get("source", {}).get("id")
            if source_id:
                sources.extend(find_ultimate_sources(source_id, visited.copy()))

        return sources

    def find_ultimate_destinations(
        component_id: str, visited: set = None
    ) -> List[Dict[str, Any]]:
        """Find all ultimate destinations (non-pass-through) that this component feeds into."""
        if visited is None:
            visited = set()

        if component_id in visited:
            return []
        visited.add(component_id)

        # If this is not a pass-through component, it's an ultimate destination
        if component_id not in pass_through_ids:
            # Get the destination info from a connection where this component
            # is the destination (incoming). This gives us the correct type
            # and groupId for this component as a destination
            dest_info = None
            for conn in incoming.get(component_id, []):
                dest_info = conn.get("destination", {}).copy()
                dest_info["id"] = component_id  # Ensure ID matches
                break
            # If no incoming connection, try to infer from outgoing (where it's source)
            if not dest_info:
                for conn in outgoing.get(component_id, []):
                    # Use the source info but with this component's ID
                    source_info = conn.get("source", {})
                    dest_info = {
                        "id": component_id,
                        "groupId": source_info.get("groupId"),
                        "type": source_info.get("type", "PROCESSOR"),
                    }
                    break
            if not dest_info:
                dest_info = {"id": component_id, "groupId": None, "type": "PROCESSOR"}
            return [{"id": component_id, "destination": dest_info}]

        # Otherwise, trace forward through outgoing connections
        destinations = []
        for conn in outgoing.get(component_id, []):
            dest_id = conn.get("destination", {}).get("id")
            if dest_id:
                destinations.extend(find_ultimate_destinations(dest_id, visited.copy()))

        return destinations

    # Build new connections that bypass pass-through components
    new_connections = []
    connection_keys = set()  # Track (source_id, dest_id) pairs to avoid duplicates

    for conn in all_connections:
        source_id = conn.get("source", {}).get("id")
        dest_id = conn.get("destination", {}).get("id")

        if not source_id or not dest_id:
            continue

        # If neither source nor destination is pass-through, keep the connection as-is
        if source_id not in pass_through_ids and dest_id not in pass_through_ids:
            new_connections.append(conn)
            continue

        # If source is pass-through, find ultimate sources
        if source_id in pass_through_ids:
            ultimate_sources = find_ultimate_sources(source_id)
        else:
            ultimate_sources = [{"id": source_id, "source": conn.get("source", {})}]

        # If destination is pass-through, find ultimate destinations
        if dest_id in pass_through_ids:
            ultimate_destinations = find_ultimate_destinations(dest_id)
        else:
            ultimate_destinations = [
                {"id": dest_id, "destination": conn.get("destination", {})}
            ]

        # Create connections from all ultimate sources to all ultimate destinations
        for src_info in ultimate_sources:
            for dst_info in ultimate_destinations:
                src_id = src_info["id"]
                dst_id = dst_info["id"]

                # Skip self-connections
                if src_id == dst_id:
                    continue

                # Skip if we've already created this connection
                conn_key = (src_id, dst_id)
                if conn_key in connection_keys:
                    continue

                connection_keys.add(conn_key)

                # Get source and destination info
                source_dict = src_info.get("source", {})
                dest_dict = dst_info.get("destination", {})

                # Preserve groupId and type from original connection if available
                if "groupId" not in source_dict or source_dict["groupId"] is None:
                    source_dict["groupId"] = conn.get("source", {}).get("groupId")
                if "type" not in source_dict or not source_dict["type"]:
                    source_dict["type"] = conn.get("source", {}).get(
                        "type", "PROCESSOR"
                    )

                if "groupId" not in dest_dict or dest_dict["groupId"] is None:
                    dest_dict["groupId"] = conn.get("destination", {}).get("groupId")
                if "type" not in dest_dict or not dest_dict["type"]:
                    dest_dict["type"] = conn.get("destination", {}).get(
                        "type", "PROCESSOR"
                    )

                # Create new connection
                new_conn = {
                    "componentType": "connection",
                    "id": id_mapper.get_friendly_id(
                        f"{src_id}->{dst_id}", "connection"
                    ),
                    "parentGroupId": parent_group_id,
                    "name": None,
                    "source": source_dict,
                    "destination": dest_dict,
                }
                new_connections.append(new_conn)

    return new_connections
