"""Converter for NiFi REST API JSON responses to TemplateDTO format.

This module converts flow data fetched from NiFi REST API into the TemplateDTO
format expected by the analysis pipeline, preserving component IDs from the live system.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from nifi_client.models import IdMapper, _build_pass_through_connections

logger = logging.getLogger(__name__)


def convert_nifi_json_to_template_dto(
    nifi_json: Dict[str, Any],
    use_friendly_ids: bool = False,
    ignore_pass_through: bool = False,
    filter_running_only: bool = False,
) -> Dict[str, Any]:
    """Convert NiFi REST API JSON response to TemplateDTO format.

    Args:
        nifi_json: JSON response from NiFi /process-groups/{id}/download endpoint
        use_friendly_ids: Whether to generate friendly IDs (default: False to preserve actual IDs)
        ignore_pass_through: Whether to ignore and bypass funnels, input/output ports
        filter_running_only: Whether to include only RUNNING processors
                             (default: False to include all)

    Returns:
        Dict in TemplateDTO format compatible with existing analysis pipeline

    The NiFi API /download endpoint response structure:
    {
        "flowContents": {
            "identifier": "...",
            "instanceIdentifier": "...",
            "name": "...",
            "processors": [...],
            "processGroups": [...],
            "connections": [...],
            "inputPorts": [...],
            "outputPorts": [...],
            "funnels": [...],
            "remoteProcessGroups": [...],
            "controllerServices": [...]
        },
        "parameterContexts": {...},
        "externalControllerServices": {...}
    }
    """
    # Create ID mapper
    id_mapper = IdMapper(use_friendly_ids=use_friendly_ids)

    # Extract flow contents from /download endpoint
    flow_contents = nifi_json.get("flowContents", {})

    # Validate response structure
    if not flow_contents:
        raise ValueError(
            "Invalid API response: missing 'flowContents'. "
            "Ensure using /process-groups/{id}/download endpoint"
        )

    # Log processor count from raw API
    raw_processor_count = len(flow_contents.get("processors", []))
    logger.info(
        f"Raw API response contains {raw_processor_count} processors at root level"
    )

    # Get process group metadata using instanceIdentifier
    pg_id_raw = flow_contents.get("instanceIdentifier", "root")
    pg_id = id_mapper.get_friendly_id(pg_id_raw, "processGroup")

    # Generate template metadata
    template_info = {
        "id": pg_id,
        "name": flow_contents.get("name") or f"Flow_{pg_id}",
        "description": f"Flow imported from NiFi API on {datetime.now().isoformat()}",
        "groupId": pg_id,
        "timestamp": datetime.now().isoformat(),
    }

    # Convert flow contents to snippet format
    snippet = _convert_flow_to_snippet(
        flow_contents,
        parent_group_id=pg_id,
        id_mapper=id_mapper,
        ignore_pass_through=ignore_pass_through,
        filter_running_only=filter_running_only,
    )

    result = {
        "template": template_info,
        "snippet": snippet,
        "_idReverseMap": id_mapper.get_reverse_map(),
    }

    return result


def _convert_flow_to_snippet(
    flow: Dict[str, Any],
    parent_group_id: str,
    id_mapper: IdMapper,
    ignore_pass_through: bool = False,
    filter_running_only: bool = False,
) -> Dict[str, Any]:
    """Convert NiFi flow contents to TemplateDTO snippet format.

    Args:
        flow: Flow contents from NiFi API
        parent_group_id: Parent process group ID
        id_mapper: ID mapper for friendly ID generation
        ignore_pass_through: Whether to ignore and bypass pass-through components
        filter_running_only: Whether to include only RUNNING processors

    Returns:
        Snippet dict in TemplateDTO format
    """
    snippet: Dict[str, Any] = {}

    # Convert processors
    processors = []
    for proc in flow.get("processors", []):
        proc_dto = _convert_processor(proc, parent_group_id, id_mapper)
        # Only filter if requested (scheduledState is now mapped to state field)
        if filter_running_only:
            # In /download format, ENABLED means the processor is scheduled to run
            if proc_dto.get("state") == "ENABLED":
                processors.append(proc_dto)
        else:
            processors.append(proc_dto)
    snippet["processors"] = processors

    # Convert process groups (nested)
    process_groups = []
    for pg in flow.get("processGroups", []):
        process_groups.append(
            _convert_process_group(
                pg, parent_group_id, id_mapper, ignore_pass_through, filter_running_only
            )
        )
    snippet["processGroups"] = process_groups

    # Convert controller services
    controller_services = []
    for cs in flow.get("controllerServices", []):
        controller_services.append(
            _convert_controller_service(cs, parent_group_id, id_mapper)
        )
    snippet["controllerServices"] = controller_services

    # Convert ports and funnels (parse first to track IDs)
    input_ports = []
    for ip in flow.get("inputPorts", []):
        input_ports.append(_convert_input_port(ip, parent_group_id, id_mapper))

    output_ports = []
    for op in flow.get("outputPorts", []):
        output_ports.append(_convert_output_port(op, parent_group_id, id_mapper))

    funnels = []
    for funnel in flow.get("funnels", []):
        funnels.append(_convert_funnel(funnel, parent_group_id, id_mapper))

    # Only include pass-through components if not ignoring them
    if not ignore_pass_through:
        snippet["inputPorts"] = input_ports
        snippet["outputPorts"] = output_ports
        snippet["funnels"] = funnels
    else:
        snippet["inputPorts"] = []
        snippet["outputPorts"] = []
        snippet["funnels"] = []

    # Convert connections
    connections = []
    all_connections_raw = []
    for conn in flow.get("connections", []):
        conn_dto = _convert_connection(conn, parent_group_id, id_mapper)
        all_connections_raw.append(conn_dto)

    if ignore_pass_through:
        # Build pass-through connectivity
        pass_through_ids = set()
        pass_through_ids.update(ip["id"] for ip in input_ports)
        pass_through_ids.update(op["id"] for op in output_ports)
        pass_through_ids.update(f["id"] for f in funnels)

        connections = _build_pass_through_connections(
            all_connections_raw, pass_through_ids, parent_group_id, id_mapper
        )
    else:
        connections = all_connections_raw

    snippet["connections"] = connections

    # Convert remote process groups
    remote_pgs = []
    for rpg in flow.get("remoteProcessGroups", []):
        remote_pgs.append(
            _convert_remote_process_group(rpg, parent_group_id, id_mapper)
        )
    snippet["remoteProcessGroups"] = remote_pgs

    return snippet


def _convert_processor(
    proc_json: Dict[str, Any], parent_group_id: str, id_mapper: IdMapper
) -> Dict[str, Any]:
    """Convert NiFi processor JSON to TemplateDTO processor format.

    NiFi /download endpoint processor structure:
    {
        "identifier": "uuid",
        "instanceIdentifier": "uuid",
        "groupIdentifier": "parent-uuid",
        "name": "ProcessorName",
        "type": "org.apache.nifi.processors.standard.LogAttribute",
        "properties": {"key": "value", ...},
        "comments": "...",
        "schedulingPeriod": "0 sec",
        "schedulingStrategy": "TIMER_DRIVEN",
        "scheduledState": "ENABLED",
        ...
    }
    """
    # Direct access - no component wrapper in /download format
    proc_id_raw = proc_json.get("identifier", "")
    proc_id = id_mapper.get_friendly_id(proc_id_raw, "processor")

    parent_group_id_raw = proc_json.get("groupIdentifier", parent_group_id)
    mapped_parent_group_id = id_mapper.get_friendly_id(
        parent_group_id_raw, "processGroup"
    )

    # Properties are at root level in /download format
    config = {
        "properties": proc_json.get("properties", {}),
        "comments": proc_json.get("comments"),
        "schedulingPeriod": proc_json.get("schedulingPeriod"),
        "schedulingStrategy": proc_json.get("schedulingStrategy"),
    }

    # Map scheduledState to state (ENABLED -> ENABLED for filtering)
    state = proc_json.get("scheduledState", "STOPPED")

    return {
        "componentType": "processor",
        "id": proc_id,
        "name": proc_json.get("name", ""),
        "type": proc_json.get("type", ""),
        "parentGroupId": mapped_parent_group_id,
        "config": config,
        "state": state,
    }


def _convert_connection(
    conn_json: Dict[str, Any], parent_group_id: str, id_mapper: IdMapper
) -> Dict[str, Any]:
    """Convert NiFi connection JSON to TemplateDTO connection format.

    NiFi /download endpoint connection structure:
    {
        "identifier": "uuid",
        "instanceIdentifier": "uuid",
        "groupIdentifier": "group-uuid",
        "name": "...",
        "source": {
            "id": "source-uuid",
            "groupId": "group-uuid",
            "type": "PROCESSOR"
        },
        "destination": {
            "id": "dest-uuid",
            "groupId": "group-uuid",
            "type": "PROCESSOR"
        },
        "selectedRelationships": ["success", "failure"],
        ...
    }
    """
    # Direct access - no component wrapper in /download format
    conn_id_raw = conn_json.get("identifier", "")
    conn_id = id_mapper.get_friendly_id(conn_id_raw, "connection")

    parent_group_id_raw = conn_json.get("groupIdentifier", parent_group_id)
    mapped_parent_group_id = id_mapper.get_friendly_id(
        parent_group_id_raw, "processGroup"
    )

    # Parse source
    source_json = conn_json.get("source", {})
    source_id_raw = source_json.get("id", "")
    source_type = source_json.get("type", "PROCESSOR")

    # Map source component type
    type_map = {
        "PROCESSOR": "processor",
        "INPUT_PORT": "inputPort",
        "OUTPUT_PORT": "outputPort",
        "FUNNEL": "funnel",
        "PROCESS_GROUP": "processGroup",
    }
    source_component_type = type_map.get(source_type, "processor")
    source_id = id_mapper.lookup_or_map_by_type(source_id_raw, source_component_type)

    source_group_id_raw = source_json.get("groupId")
    source_group_id = (
        id_mapper.get_friendly_id(source_group_id_raw, "processGroup")
        if source_group_id_raw
        else None
    )

    source = {
        "id": source_id,
        "groupId": source_group_id,
        "type": source_type,
    }

    # Parse destination
    dest_json = conn_json.get("destination", {})
    dest_id_raw = dest_json.get("id", "")
    dest_type = dest_json.get("type", "PROCESSOR")

    dest_component_type = type_map.get(dest_type, "processor")
    dest_id = id_mapper.lookup_or_map_by_type(dest_id_raw, dest_component_type)

    dest_group_id_raw = dest_json.get("groupId")
    dest_group_id = (
        id_mapper.get_friendly_id(dest_group_id_raw, "processGroup")
        if dest_group_id_raw
        else None
    )

    destination = {
        "id": dest_id,
        "groupId": dest_group_id,
        "type": dest_type,
    }

    return {
        "componentType": "connection",
        "id": conn_id,
        "parentGroupId": mapped_parent_group_id,
        "name": conn_json.get("name"),
        "source": source,
        "destination": destination,
    }


def _convert_process_group(
    pg_json: Dict[str, Any],
    parent_group_id: str,
    id_mapper: IdMapper,
    ignore_pass_through: bool = False,
    filter_running_only: bool = False,
) -> Dict[str, Any]:
    """Convert NiFi process group JSON to TemplateDTO process group format.

    NiFi /download endpoint process group structure:
    {
        "identifier": "uuid",
        "instanceIdentifier": "uuid",
        "groupIdentifier": "parent-uuid",
        "name": "ProcessGroupName",
        "comments": "...",
        "variables": {"key": "value", ...},
        "processors": [...],
        "connections": [...],
        "processGroups": [...],
        ...
    }
    """
    # Direct access - no component wrapper in /download format
    pg_id_raw = pg_json.get("identifier", "")
    pg_id = id_mapper.get_friendly_id(pg_id_raw, "processGroup")

    parent_group_id_raw = pg_json.get("groupIdentifier", parent_group_id)
    mapped_parent_group_id = id_mapper.get_friendly_id(
        parent_group_id_raw, "processGroup"
    )

    # Variables are a direct dict in /download format
    variables = pg_json.get("variables", {})

    # In /download format, pg_json itself contains processors, connections, etc.
    # Recursively convert the nested flow
    contents = _convert_flow_to_snippet(
        pg_json,  # Pass the PG itself as the flow
        parent_group_id=pg_id,
        id_mapper=id_mapper,
        ignore_pass_through=ignore_pass_through,
        filter_running_only=filter_running_only,
    )

    return {
        "componentType": "processGroup",
        "id": pg_id,
        "name": pg_json.get("name", ""),
        "parentGroupId": mapped_parent_group_id,
        "comments": pg_json.get("comments"),
        "variables": variables if variables else None,
        "contents": contents,
    }


def _convert_controller_service(
    cs_json: Dict[str, Any], parent_group_id: str, id_mapper: IdMapper
) -> Dict[str, Any]:
    """Convert NiFi controller service JSON to TemplateDTO format."""
    # Direct access - no component wrapper in /download format
    cs_id = cs_json.get("identifier", "")  # Controller services keep original IDs

    parent_group_id_raw = cs_json.get("groupIdentifier", parent_group_id)
    mapped_parent_group_id = id_mapper.get_friendly_id(
        parent_group_id_raw, "processGroup"
    )

    return {
        "componentType": "controllerService",
        "id": cs_id,
        "name": cs_json.get("name", ""),
        "type": cs_json.get("type", ""),
        "parentGroupId": mapped_parent_group_id,
        "properties": cs_json.get("properties", {}),
        "bulletinLevel": cs_json.get("bulletinLevel"),
        "comments": cs_json.get("comments"),
        "persistsState": cs_json.get("persistsState"),
        "state": cs_json.get("state", "DISABLED"),
    }


def _convert_input_port(
    ip_json: Dict[str, Any], parent_group_id: str, id_mapper: IdMapper
) -> Dict[str, Any]:
    """Convert NiFi input port JSON to TemplateDTO format."""
    # Direct access - no component wrapper in /download format
    ip_id_raw = ip_json.get("identifier", "")
    ip_id = id_mapper.get_friendly_id(ip_id_raw, "inputPort")

    parent_group_id_raw = ip_json.get("groupIdentifier", parent_group_id)
    mapped_parent_group_id = id_mapper.get_friendly_id(
        parent_group_id_raw, "processGroup"
    )

    return {
        "componentType": "inputPort",
        "id": ip_id,
        "name": ip_json.get("name", ""),
        "parentGroupId": mapped_parent_group_id,
        "comments": ip_json.get("comments"),
        "state": ip_json.get("scheduledState", "STOPPED"),
        "type": ip_json.get("type"),
    }


def _convert_output_port(
    op_json: Dict[str, Any], parent_group_id: str, id_mapper: IdMapper
) -> Dict[str, Any]:
    """Convert NiFi output port JSON to TemplateDTO format."""
    # Direct access - no component wrapper in /download format
    op_id_raw = op_json.get("identifier", "")
    op_id = id_mapper.get_friendly_id(op_id_raw, "outputPort")

    parent_group_id_raw = op_json.get("groupIdentifier", parent_group_id)
    mapped_parent_group_id = id_mapper.get_friendly_id(
        parent_group_id_raw, "processGroup"
    )

    return {
        "componentType": "outputPort",
        "id": op_id,
        "name": op_json.get("name", ""),
        "parentGroupId": mapped_parent_group_id,
        "comments": op_json.get("comments"),
        "state": op_json.get("scheduledState", "STOPPED"),
        "type": op_json.get("type"),
    }


def _convert_funnel(
    funnel_json: Dict[str, Any], parent_group_id: str, id_mapper: IdMapper
) -> Dict[str, Any]:
    """Convert NiFi funnel JSON to TemplateDTO format."""
    # Direct access - no component wrapper in /download format
    funnel_id_raw = funnel_json.get("identifier", "")
    funnel_id = id_mapper.get_friendly_id(funnel_id_raw, "funnel")

    parent_group_id_raw = funnel_json.get("groupIdentifier", parent_group_id)
    mapped_parent_group_id = id_mapper.get_friendly_id(
        parent_group_id_raw, "processGroup"
    )

    return {
        "componentType": "funnel",
        "id": funnel_id,
        "parentGroupId": mapped_parent_group_id,
    }


def _convert_remote_process_group(
    rpg_json: Dict[str, Any], parent_group_id: str, id_mapper: IdMapper
) -> Dict[str, Any]:
    """Convert NiFi remote process group JSON to TemplateDTO format."""
    # Direct access - no component wrapper in /download format
    rpg_id = rpg_json.get("identifier", "")  # Remote PGs keep original IDs

    parent_group_id_raw = rpg_json.get("groupIdentifier", parent_group_id)
    mapped_parent_group_id = id_mapper.get_friendly_id(
        parent_group_id_raw, "processGroup"
    )

    return {
        "componentType": "remoteProcessGroup",
        "id": rpg_id,
        "name": rpg_json.get("name", ""),
        "parentGroupId": mapped_parent_group_id,
    }
