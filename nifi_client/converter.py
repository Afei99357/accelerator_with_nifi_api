"""Converter for NiFi REST API JSON responses to TemplateDTO format.

This module converts flow data fetched from NiFi REST API into the TemplateDTO
format expected by the analysis pipeline, preserving component IDs from the live system.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from nifi_client.models import IdMapper, _build_pass_through_connections

logger = logging.getLogger(__name__)


def convert_nifi_json_to_template_dto(
    nifi_json: Dict[str, Any],
    use_friendly_ids: bool = False,
    ignore_pass_through: bool = False
) -> Dict[str, Any]:
    """Convert NiFi REST API JSON response to TemplateDTO format.

    Args:
        nifi_json: JSON response from NiFi /process-groups/{id}/download endpoint
        use_friendly_ids: Whether to generate friendly IDs (default: False to preserve actual IDs)
        ignore_pass_through: Whether to ignore and bypass funnels, input/output ports

    Returns:
        Dict in TemplateDTO format compatible with existing analysis pipeline

    The NiFi API response structure:
    {
        "processGroupFlow": {
            "id": "root",
            "parentGroupId": null,
            "flow": {
                "processGroups": [...],
                "processors": [...],
                "connections": [...],
                "inputPorts": [...],
                "outputPorts": [...],
                "funnels": [...],
                "remoteProcessGroups": [...],
                "controllerServices": [...]
            },
            "parameterContext": {...},
            "flowfilesQueued": {...},
            ...
        }
    }
    """
    # Create ID mapper
    id_mapper = IdMapper(use_friendly_ids=use_friendly_ids)

    # Extract process group flow
    pg_flow = nifi_json.get("processGroupFlow", {})
    flow_contents = pg_flow.get("flow", {})

    # Get process group metadata
    pg_id_raw = pg_flow.get("id", "root")
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
        ignore_pass_through=ignore_pass_through
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
    ignore_pass_through: bool = False
) -> Dict[str, Any]:
    """Convert NiFi flow contents to TemplateDTO snippet format.

    Args:
        flow: Flow contents from NiFi API
        parent_group_id: Parent process group ID
        id_mapper: ID mapper for friendly ID generation
        ignore_pass_through: Whether to ignore and bypass pass-through components

    Returns:
        Snippet dict in TemplateDTO format
    """
    snippet: Dict[str, Any] = {}

    # Convert processors - filter to only RUNNING
    processors = []
    for proc in flow.get("processors", []):
        proc_dto = _convert_processor(proc, parent_group_id, id_mapper)
        if proc_dto.get("state") == "RUNNING":
            processors.append(proc_dto)
    snippet["processors"] = processors

    # Convert process groups (nested)
    process_groups = []
    for pg in flow.get("processGroups", []):
        process_groups.append(_convert_process_group(pg, parent_group_id, id_mapper, ignore_pass_through))
    snippet["processGroups"] = process_groups

    # Convert controller services
    controller_services = []
    for cs in flow.get("controllerServices", []):
        controller_services.append(_convert_controller_service(cs, parent_group_id, id_mapper))
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
            all_connections_raw,
            pass_through_ids,
            parent_group_id,
            id_mapper
        )
    else:
        connections = all_connections_raw

    snippet["connections"] = connections

    # Convert remote process groups
    remote_pgs = []
    for rpg in flow.get("remoteProcessGroups", []):
        remote_pgs.append(_convert_remote_process_group(rpg, parent_group_id, id_mapper))
    snippet["remoteProcessGroups"] = remote_pgs

    return snippet


def _convert_processor(
    proc_json: Dict[str, Any],
    parent_group_id: str,
    id_mapper: IdMapper
) -> Dict[str, Any]:
    """Convert NiFi processor JSON to TemplateDTO processor format.

    NiFi API processor structure:
    {
        "id": "uuid",
        "parentGroupId": "parent-uuid",
        "component": {
            "id": "uuid",
            "name": "ProcessorName",
            "type": "org.apache.nifi.processors.standard.LogAttribute",
            "config": {
                "properties": {"key": "value", ...},
                "comments": "...",
                "schedulingPeriod": "0 sec",
                "schedulingStrategy": "TIMER_DRIVEN",
                ...
            },
            "state": "RUNNING",
            ...
        },
        "status": {...},
        ...
    }
    """
    # NiFi API wraps data in "component" and uses "id" at top level
    component = proc_json.get("component", proc_json)

    proc_id_raw = component.get("id", "")
    proc_id = id_mapper.get_friendly_id(proc_id_raw, "processor")

    parent_group_id_raw = component.get("parentGroupId", parent_group_id)
    mapped_parent_group_id = id_mapper.get_friendly_id(parent_group_id_raw, "processGroup")

    # Parse config
    config_json = component.get("config", {})
    config = {
        "properties": config_json.get("properties", {}),
        "comments": config_json.get("comments"),
        "schedulingPeriod": config_json.get("schedulingPeriod"),
        "schedulingStrategy": config_json.get("schedulingStrategy"),
    }

    return {
        "componentType": "processor",
        "id": proc_id,
        "name": component.get("name", ""),
        "type": component.get("type", ""),
        "parentGroupId": mapped_parent_group_id,
        "config": config,
        "state": component.get("state", "STOPPED"),
    }


def _convert_connection(
    conn_json: Dict[str, Any],
    parent_group_id: str,
    id_mapper: IdMapper
) -> Dict[str, Any]:
    """Convert NiFi connection JSON to TemplateDTO connection format.

    NiFi API connection structure:
    {
        "id": "uuid",
        "component": {
            "id": "uuid",
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
    }
    """
    component = conn_json.get("component", conn_json)

    conn_id_raw = component.get("id", "")
    conn_id = id_mapper.get_friendly_id(conn_id_raw, "connection")

    parent_group_id_raw = component.get("parentGroupId", parent_group_id)
    mapped_parent_group_id = id_mapper.get_friendly_id(parent_group_id_raw, "processGroup")

    # Parse source
    source_json = component.get("source", {})
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
    source_group_id = id_mapper.get_friendly_id(source_group_id_raw, "processGroup") if source_group_id_raw else None

    source = {
        "id": source_id,
        "groupId": source_group_id,
        "type": source_type,
    }

    # Parse destination
    dest_json = component.get("destination", {})
    dest_id_raw = dest_json.get("id", "")
    dest_type = dest_json.get("type", "PROCESSOR")

    dest_component_type = type_map.get(dest_type, "processor")
    dest_id = id_mapper.lookup_or_map_by_type(dest_id_raw, dest_component_type)

    dest_group_id_raw = dest_json.get("groupId")
    dest_group_id = id_mapper.get_friendly_id(dest_group_id_raw, "processGroup") if dest_group_id_raw else None

    destination = {
        "id": dest_id,
        "groupId": dest_group_id,
        "type": dest_type,
    }

    return {
        "componentType": "connection",
        "id": conn_id,
        "parentGroupId": mapped_parent_group_id,
        "name": component.get("name"),
        "source": source,
        "destination": destination,
    }


def _convert_process_group(
    pg_json: Dict[str, Any],
    parent_group_id: str,
    id_mapper: IdMapper,
    ignore_pass_through: bool = False
) -> Dict[str, Any]:
    """Convert NiFi process group JSON to TemplateDTO process group format.

    NiFi API process group structure:
    {
        "id": "uuid",
        "component": {
            "id": "uuid",
            "name": "ProcessGroupName",
            "comments": "...",
            "contents": {
                "processors": [...],
                "connections": [...],
                ...
            },
            ...
        }
    }
    """
    component = pg_json.get("component", pg_json)

    pg_id_raw = component.get("id", "")
    pg_id = id_mapper.get_friendly_id(pg_id_raw, "processGroup")

    parent_group_id_raw = component.get("parentGroupId", parent_group_id)
    mapped_parent_group_id = id_mapper.get_friendly_id(parent_group_id_raw, "processGroup")

    # Parse variables
    variables = {}
    var_registry = component.get("variableRegistry", {})
    if var_registry:
        for var in var_registry.get("variables", []):
            var_name = var.get("name") or var.get("variable", {}).get("name")
            var_value = var.get("value") or var.get("variable", {}).get("value")
            if var_name:
                variables[var_name] = var_value

    # Parse contents (nested flow)
    contents = {}
    contents_json = component.get("contents", {})
    if contents_json:
        contents = _convert_flow_to_snippet(
            contents_json,
            parent_group_id=pg_id,
            id_mapper=id_mapper,
            ignore_pass_through=ignore_pass_through
        )

    return {
        "componentType": "processGroup",
        "id": pg_id,
        "name": component.get("name", ""),
        "parentGroupId": mapped_parent_group_id,
        "comments": component.get("comments"),
        "variables": variables if variables else None,
        "contents": contents,
    }


def _convert_controller_service(
    cs_json: Dict[str, Any],
    parent_group_id: str,
    id_mapper: IdMapper
) -> Dict[str, Any]:
    """Convert NiFi controller service JSON to TemplateDTO format."""
    component = cs_json.get("component", cs_json)

    cs_id = component.get("id", "")  # Controller services keep original IDs

    parent_group_id_raw = component.get("parentGroupId", parent_group_id)
    mapped_parent_group_id = id_mapper.get_friendly_id(parent_group_id_raw, "processGroup")

    return {
        "componentType": "controllerService",
        "id": cs_id,
        "name": component.get("name", ""),
        "type": component.get("type", ""),
        "parentGroupId": mapped_parent_group_id,
        "properties": component.get("properties", {}),
        "bulletinLevel": component.get("bulletinLevel"),
        "comments": component.get("comments"),
        "persistsState": component.get("persistsState"),
        "state": component.get("state", "DISABLED"),
    }


def _convert_input_port(
    ip_json: Dict[str, Any],
    parent_group_id: str,
    id_mapper: IdMapper
) -> Dict[str, Any]:
    """Convert NiFi input port JSON to TemplateDTO format."""
    component = ip_json.get("component", ip_json)

    ip_id_raw = component.get("id", "")
    ip_id = id_mapper.get_friendly_id(ip_id_raw, "inputPort")

    parent_group_id_raw = component.get("parentGroupId", parent_group_id)
    mapped_parent_group_id = id_mapper.get_friendly_id(parent_group_id_raw, "processGroup")

    return {
        "componentType": "inputPort",
        "id": ip_id,
        "name": component.get("name", ""),
        "parentGroupId": mapped_parent_group_id,
        "comments": component.get("comments"),
        "state": component.get("state", "STOPPED"),
        "type": component.get("type"),
    }


def _convert_output_port(
    op_json: Dict[str, Any],
    parent_group_id: str,
    id_mapper: IdMapper
) -> Dict[str, Any]:
    """Convert NiFi output port JSON to TemplateDTO format."""
    component = op_json.get("component", op_json)

    op_id_raw = component.get("id", "")
    op_id = id_mapper.get_friendly_id(op_id_raw, "outputPort")

    parent_group_id_raw = component.get("parentGroupId", parent_group_id)
    mapped_parent_group_id = id_mapper.get_friendly_id(parent_group_id_raw, "processGroup")

    return {
        "componentType": "outputPort",
        "id": op_id,
        "name": component.get("name", ""),
        "parentGroupId": mapped_parent_group_id,
        "comments": component.get("comments"),
        "state": component.get("state", "STOPPED"),
        "type": component.get("type"),
    }


def _convert_funnel(
    funnel_json: Dict[str, Any],
    parent_group_id: str,
    id_mapper: IdMapper
) -> Dict[str, Any]:
    """Convert NiFi funnel JSON to TemplateDTO format."""
    component = funnel_json.get("component", funnel_json)

    funnel_id_raw = component.get("id", "")
    funnel_id = id_mapper.get_friendly_id(funnel_id_raw, "funnel")

    parent_group_id_raw = component.get("parentGroupId", parent_group_id)
    mapped_parent_group_id = id_mapper.get_friendly_id(parent_group_id_raw, "processGroup")

    return {
        "componentType": "funnel",
        "id": funnel_id,
        "parentGroupId": mapped_parent_group_id,
    }


def _convert_remote_process_group(
    rpg_json: Dict[str, Any],
    parent_group_id: str,
    id_mapper: IdMapper
) -> Dict[str, Any]:
    """Convert NiFi remote process group JSON to TemplateDTO format."""
    component = rpg_json.get("component", rpg_json)

    rpg_id = component.get("id", "")  # Remote PGs keep original IDs

    parent_group_id_raw = component.get("parentGroupId", parent_group_id)
    mapped_parent_group_id = id_mapper.get_friendly_id(parent_group_id_raw, "processGroup")

    return {
        "componentType": "remoteProcessGroup",
        "id": rpg_id,
        "name": component.get("name", ""),
        "parentGroupId": mapped_parent_group_id,
    }
