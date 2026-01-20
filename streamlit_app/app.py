"""Streamlit web application for NiFi API Analyzer."""

import sys
from pathlib import Path

import streamlit as st

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from nifi_client.client import AuthType, NiFiClient, NiFiConnectionConfig  # noqa: E402
from nifi_client.converter import convert_nifi_json_to_template_dto  # noqa: E402


def main():
    st.set_page_config(page_title="NiFi API Analyzer", page_icon="🔄", layout="wide")

    st.title("🔄 NiFi API Analyzer")
    st.markdown("API-first NiFi flow analysis tool")

    # Sidebar - Connection Configuration
    with st.sidebar:
        st.header("NiFi Connection")

        host = st.text_input("Host", value="localhost", help="NiFi host address")
        port = st.number_input("Port", value=8080, min_value=1, max_value=65535)
        protocol = st.selectbox("Protocol", ["https", "http"], index=0)

        st.subheader("Authentication")
        auth_type = st.selectbox(
            "Auth Type",
            ["none", "basic", "bearer", "certificate"],
            help="Authentication method",
        )

        username = None
        password = None
        token = None
        cert_path = None
        key_path = None

        if auth_type == "basic":
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
        elif auth_type == "bearer":
            token = st.text_input("Bearer Token", type="password")
        elif auth_type == "certificate":
            cert_path = st.text_input(
                "Certificate Path", placeholder="/path/to/cert.pem"
            )
            key_path = st.text_input("Key Path", placeholder="/path/to/key.pem")

        verify_ssl = st.checkbox("Verify SSL", value=True)
        timeout = st.slider("Timeout (seconds)", min_value=10, max_value=300, value=30)

        st.divider()
        st.subheader("Flow Selection")
        process_group_id = st.text_input(
            "Process Group ID",
            value="root",
            help="Process group ID to fetch (use 'root' for root process group)",
        )
        # Store in session state for use when fetching
        st.session_state["process_group_id"] = process_group_id

        filter_running = st.checkbox(
            "Filter RUNNING processors only",
            value=False,
            help="If checked, only include processors in RUNNING state",
        )
        st.session_state["filter_running_only"] = filter_running

        st.divider()
        st.subheader("Debug Options")
        debug_mode = st.checkbox(
            "Enable Debug Mode",
            value=False,
            help="Show detailed API response and conversion info",
        )
        st.session_state["debug_mode"] = debug_mode

    # Main content area
    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("🔌 Test Connection", type="primary", use_container_width=True):
            with st.spinner("Testing connection..."):
                try:
                    config = NiFiConnectionConfig(
                        host=host,
                        port=port,
                        protocol=protocol,
                        auth_type=AuthType(auth_type),
                        username=username,
                        password=password,
                        token=token,
                        cert_path=cert_path,
                        key_path=key_path,
                        verify_ssl=verify_ssl,
                        timeout=timeout,
                    )

                    client = NiFiClient(config)
                    result = client.test_connection()

                    if result["success"]:
                        st.success(f"✅ {result['message']}")
                        # Store client in session state
                        st.session_state["nifi_client"] = client
                        st.session_state["nifi_config"] = config
                    else:
                        st.error(
                            f"❌ Connection failed: {result.get('error', 'Unknown error')}"
                        )

                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

    with col2:
        if st.button("📥 Fetch Flow", type="primary", use_container_width=True):
            if "nifi_client" not in st.session_state:
                st.warning("⚠️ Please test connection first")
            else:
                with st.spinner("Fetching flow..."):
                    try:
                        import requests

                        client = st.session_state["nifi_client"]
                        process_group_id = st.session_state.get(
                            "process_group_id", "root"
                        )
                        filter_running_only = st.session_state.get(
                            "filter_running_only", False
                        )
                        debug_mode = st.session_state.get("debug_mode", False)

                        # Fetch flow from NiFi
                        flow_json = client.fetch_flow(process_group_id)

                        # Debug mode: Show raw response structure
                        if debug_mode:
                            import json
                            from datetime import datetime

                            with st.expander(
                                "🔍 Debug: Raw API Response", expanded=False
                            ):
                                # Show structure analysis
                                st.subheader("Response Structure")
                                pg_flow = flow_json.get("processGroupFlow", {})
                                flow_contents = pg_flow.get("flow", {})

                                st.write(f"- Has 'processGroupFlow': {bool(pg_flow)}")
                                st.write(f"- Has 'flow': {bool(flow_contents)}")

                                proc_count = len(flow_contents.get("processors", []))
                                pg_count = len(flow_contents.get("processGroups", []))
                                conn_count = len(flow_contents.get("connections", []))

                                st.write(f"- Processors in flow: {proc_count}")
                                st.write(f"- Process groups in flow: {pg_count}")
                                st.write(f"- Connections in flow: {conn_count}")

                                # Show processor states if any
                                processors = flow_contents.get("processors", [])
                                if processors:
                                    states = {}
                                    for p in processors:
                                        proc_data = p.get("component", p)
                                        state = proc_data.get("state", "UNKNOWN")
                                        states[state] = states.get(state, 0) + 1
                                    st.write("Processor states:", states)
                                else:
                                    st.warning("⚠️ No processors found in API response!")

                                # Save to file instead of displaying
                                st.divider()
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = f"debug_api_response_{process_group_id}_{timestamp}.json"
                                filepath = Path(__file__).parent.parent / filename

                                try:
                                    with open(filepath, "w") as f:
                                        json.dump(flow_json, f, indent=2)
                                    st.success(
                                        f"✅ Raw API response saved to: `{filename}`"
                                    )
                                    st.info(f"Full path: `{filepath}`")
                                except Exception as e:
                                    st.error(f"Failed to save file: {e}")

                        # Convert to template_dto
                        template_dto = convert_nifi_json_to_template_dto(
                            flow_json,
                            use_friendly_ids=False,
                            ignore_pass_through=True,
                            filter_running_only=filter_running_only,
                        )

                        # Debug mode: Show conversion result
                        if debug_mode:
                            with st.expander(
                                "🔍 Debug: Converted template_dto", expanded=False
                            ):
                                snippet = template_dto.get("snippet", {})
                                proc_after = len(snippet.get("processors", []))
                                conn_after = len(snippet.get("connections", []))
                                pg_after = len(snippet.get("processGroups", []))

                                st.write(f"- Processors after conversion: {proc_after}")
                                st.write(
                                    f"- Connections after conversion: {conn_after}"
                                )
                                st.write(
                                    f"- Process groups after conversion: {pg_after}"
                                )

                                if filter_running_only:
                                    msg = (
                                        "Note: filter_running_only enabled - "
                                        "only RUNNING processors included"
                                    )
                                    st.info(msg)

                                # Save converted template_dto to file
                                st.divider()
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = f"debug_template_dto_{process_group_id}_{timestamp}.json"
                                filepath = Path(__file__).parent.parent / filename

                                try:
                                    with open(filepath, "w") as f:
                                        json.dump(template_dto, f, indent=2)
                                    st.success(
                                        f"✅ Converted template_dto saved to: `{filename}`"
                                    )
                                    st.info(f"Full path: `{filepath}`")
                                except Exception as e:
                                    st.error(f"Failed to save file: {e}")

                        # Store in session state
                        st.session_state["template_dto"] = template_dto
                        st.session_state["flow_json"] = flow_json

                        # Display summary
                        snippet = template_dto.get("snippet", {})

                        # Helper function to count all processors recursively
                        def count_all_processors(snippet_data):
                            """Recursively count all processors including nested groups."""
                            count = len(snippet_data.get("processors", []))
                            for pg in snippet_data.get("processGroups", []):
                                count += count_all_processors(pg.get("contents", {}))
                            return count

                        # Helper function to count all connections recursively
                        def count_all_connections(snippet_data):
                            """Recursively count all connections including nested groups."""
                            count = len(snippet_data.get("connections", []))
                            for pg in snippet_data.get("processGroups", []):
                                count += count_all_connections(pg.get("contents", {}))
                            return count

                        processor_count = count_all_processors(snippet)
                        connection_count = count_all_connections(snippet)
                        root_processor_count = len(snippet.get("processors", []))

                        if processor_count == 0:
                            st.warning("⚠️ No processors found in the fetched flow")
                            st.info(
                                f"""
**Possible reasons:**
1. The selected Process Group is empty
2. Processors are in nested Process Groups (not shown at this level)
3. All processors are filtered out (check 'Filter RUNNING processors only')
4. Authentication has view access but not full flow access

**Try:**
- Enable 'Debug Mode' to see the raw API response
- Check if Process Group ID is correct (currently: '{process_group_id}')
- Uncheck 'Filter RUNNING processors only' if enabled
- Check nested process groups for processors
                            """
                            )
                        else:
                            st.success("✅ Flow fetched successfully")
                            nested_count = processor_count - root_processor_count
                            st.info(
                                f"""
**Flow Summary:**
- **Total Processors**: {processor_count} (root: {root_processor_count}, nested: {nested_count})
- **Total Connections**: {connection_count}
- **Process Groups**: {len(snippet.get('processGroups', []))}
                            """
                            )

                    except requests.exceptions.HTTPError as e:
                        st.error(
                            f"❌ HTTP Error fetching flow: {e.response.status_code}"
                        )
                        st.error(f"Response: {e.response.text[:500]}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"❌ Network error fetching flow: {str(e)}")
                    except ValueError as e:
                        st.error(f"❌ Invalid request: {str(e)}")
                    except PermissionError as e:
                        st.error(f"❌ Access denied: {str(e)}")
                    except TimeoutError as e:
                        st.error(f"❌ Timeout: {str(e)}")
                    except KeyError as e:
                        st.error(
                            f"❌ Unexpected API response structure - missing key: {e}"
                        )
                        if st.session_state.get("debug_mode", False):
                            st.json(flow_json)
                    except Exception as e:
                        st.error(f"❌ Error fetching flow: {str(e)}")
                        st.error(f"Error type: {type(e).__name__}")
                        import traceback

                        if st.session_state.get("debug_mode", False):
                            st.code(traceback.format_exc())

    # Analysis Section
    if "template_dto" in st.session_state:
        st.divider()
        st.header("📊 Analysis")

        # Create tabs for different analyzers
        tabs = st.tabs(
            [
                "Overview",
                "Tables",
                "SQL Queries",
                "Variables",
            ]
        )

        template_dto = st.session_state["template_dto"]
        snippet = template_dto.get("snippet", {})

        # Overview Tab
        with tabs[0]:
            st.subheader("Flow Overview")

            # Helper functions for recursive counting
            def count_all_processors(snippet_data):
                """Recursively count all processors including nested groups."""
                count = len(snippet_data.get("processors", []))
                for pg in snippet_data.get("processGroups", []):
                    count += count_all_processors(pg.get("contents", {}))
                return count

            def count_all_connections(snippet_data):
                """Recursively count all connections including nested groups."""
                count = len(snippet_data.get("connections", []))
                for pg in snippet_data.get("processGroups", []):
                    count += count_all_connections(pg.get("contents", {}))
                return count

            total_processors = count_all_processors(snippet)
            total_connections = count_all_connections(snippet)

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Processors (total)", total_processors)
                st.caption(f"Root level: {len(snippet.get('processors', []))}")

            with col2:
                st.metric("Connections (total)", total_connections)
                st.caption(f"Root level: {len(snippet.get('connections', []))}")

            with col3:
                st.metric("Process Groups", len(snippet.get("processGroups", [])))

            st.subheader("Processor List")

            # Recursively collect ALL processors including nested ones
            def get_all_processors(snippet_data):
                """Extract all processors from snippet including nested groups."""
                all_procs = []
                # Add root level processors
                all_procs.extend(snippet_data.get("processors", []))
                # Recursively add processors from nested process groups
                for pg in snippet_data.get("processGroups", []):
                    pg_contents = pg.get("contents", {})
                    all_procs.extend(get_all_processors(pg_contents))
                return all_procs

            processors = get_all_processors(snippet)

            if processors:
                processor_data = []
                for proc in processors:
                    processor_data.append(
                        {
                            "Name": proc.get("name", ""),
                            "Type": proc.get("type", "").split(".")[-1],
                            "Parent Group": proc.get("parentGroupId", ""),
                            "State": proc.get("state", ""),
                            "ID": proc.get("id", ""),
                        }
                    )

                st.dataframe(processor_data, use_container_width=True, hide_index=True)
                st.caption(
                    f"Total processors (including nested groups): {len(processors)}"
                )
            else:
                st.info("No processors found")

        # Tables Tab
        with tabs[1]:
            st.subheader("Database Tables")

            from analyzers import TableExtractionAnalyzer

            analyzer = TableExtractionAnalyzer(template_dto)
            results = analyzer.analyze()

            # Summary metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Tables", results["table_count"])
            with col2:
                st.metric("Source Tables", len(results["sources"]))
            with col3:
                st.metric("Target Tables", len(results["targets"]))

            # Tabs for different views
            table_tabs = st.tabs(
                ["All Tables", "Sources (Read)", "Targets (Write)", "By Processor"]
            )

            with table_tabs[0]:
                # All tables list
                if results["tables"]:
                    import pandas as pd

                    st.dataframe(
                        pd.DataFrame({"Table Name": results["tables"]}),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("No tables found")

            with table_tabs[1]:
                # Source tables
                if results["sources"]:
                    import pandas as pd

                    source_data = [
                        {
                            "Table": s["name"],
                            "Processor": s["processor"],
                            "Type": s["type"],
                        }
                        for s in results["sources"]
                    ]
                    st.dataframe(source_data, use_container_width=True, hide_index=True)
                else:
                    st.info("No source tables found")

            with table_tabs[2]:
                # Target tables
                if results["targets"]:
                    import pandas as pd

                    target_data = [
                        {
                            "Table": t["name"],
                            "Processor": t["processor"],
                            "Type": t["type"],
                        }
                        for t in results["targets"]
                    ]
                    st.dataframe(target_data, use_container_width=True, hide_index=True)
                else:
                    st.info("No target tables found")

            with table_tabs[3]:
                # By processor
                if results["by_processor"]:
                    import pandas as pd

                    proc_table_data = [
                        {"Processor ID": proc_id, "Tables": ", ".join(tables)}
                        for proc_id, tables in results["by_processor"].items()
                    ]
                    st.dataframe(
                        proc_table_data, use_container_width=True, hide_index=True
                    )
                else:
                    st.info("No processor-table mappings found")

            # Export button
            if results["tables"]:
                import pandas as pd

                csv = pd.DataFrame({"Table Name": results["tables"]}).to_csv(
                    index=False
                )
                st.download_button(
                    label="Download tables as CSV",
                    data=csv,
                    file_name="nifi_tables.csv",
                    mime="text/csv",
                )

        # SQL Queries Tab
        with tabs[2]:
            st.subheader("SQL Queries")

            from analyzers import SQLExtractionAnalyzer

            analyzer = SQLExtractionAnalyzer(template_dto)
            results = analyzer.analyze()

            # Summary metrics
            st.metric("Total Queries", results["total_count"])

            if results["total_count"] > 0:
                # By type summary
                st.subheader("Queries by Type")
                type_counts = {
                    sql_type: len(queries)
                    for sql_type, queries in results["by_type"].items()
                    if queries
                }
                col_count = min(len(type_counts), 4)
                cols = st.columns(col_count)
                for i, (sql_type, count) in enumerate(type_counts.items()):
                    with cols[i % col_count]:
                        st.metric(sql_type, count)

                # Query details
                st.subheader("Query Details")

                # Filter by type
                all_types = list(results["by_type"].keys())
                selected_type = st.selectbox(
                    "Filter by SQL type",
                    ["All"] + [t for t in all_types if results["by_type"][t]],
                )

                # Get queries to display
                if selected_type == "All":
                    queries_to_show = results["queries"]
                else:
                    queries_to_show = results["by_type"][selected_type]

                # Display queries
                for i, query in enumerate(queries_to_show):
                    with st.expander(
                        f"{query['type']} - Processor: {query['processor_id'][:8]}..."
                    ):
                        st.code(query["sql"], language="sql")

                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Property:** {query['property_name']}")
                            st.write(f"**Length:** {query['length']} chars")
                        with col2:
                            st.write(f"**Parameterized:** {query['is_parameterized']}")
                            if query["tables"]:
                                st.write(f"**Tables:** {', '.join(query['tables'])}")

                        if query["variables"]:
                            st.write(f"**Variables:** {', '.join(query['variables'])}")

                # Export button
                import pandas as pd

                export_data = [
                    {
                        "Processor": q["processor_id"],
                        "Type": q["type"],
                        "Property": q["property_name"],
                        "SQL": q["sql"],
                        "Tables": ", ".join(q["tables"]),
                        "Parameterized": q["is_parameterized"],
                    }
                    for q in results["queries"]
                ]
                csv = pd.DataFrame(export_data).to_csv(index=False)
                st.download_button(
                    label="Download queries as CSV",
                    data=csv,
                    file_name="nifi_sql_queries.csv",
                    mime="text/csv",
                )
            else:
                st.info("No SQL queries found in processors")

        # Variables Tab
        with tabs[3]:
            st.subheader("Variable Dependencies")

            from analyzers import VariablesAnalyzer

            analyzer = VariablesAnalyzer(template_dto)
            results = analyzer.analyze()

            # Summary metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Defined Variables", results["defined_count"])
            with col2:
                st.metric("Used Variables", results["used_count"])
            with col3:
                color = "normal" if results["undefined_count"] == 0 else "inverse"
                st.metric(
                    "Undefined Variables",
                    results["undefined_count"],
                    delta_color=color,
                )

            # Validation status
            validation = analyzer.validate_variables()
            if validation["is_valid"]:
                st.success("✅ All variables are properly defined")
            else:
                st.error(f"❌ {validation['message']}")

            # Variable tabs
            var_tabs = st.tabs(["Defined", "Used", "Undefined", "By Processor"])

            with var_tabs[0]:
                # Defined variables
                if results["defined_variables"]:
                    import pandas as pd

                    defined_data = [
                        {
                            "Variable": var_name,
                            "Value": var_info["value"],
                            "Process Group": var_info["process_group"],
                        }
                        for var_name, var_info in results["defined_variables"].items()
                    ]
                    st.dataframe(
                        defined_data, use_container_width=True, hide_index=True
                    )
                else:
                    st.info("No defined variables found")

            with var_tabs[1]:
                # Used variables
                if results["used_variables"]:
                    import pandas as pd

                    st.dataframe(
                        pd.DataFrame(
                            {"Variable": sorted(set(results["used_variables"]))}
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("No variable usage found")

            with var_tabs[2]:
                # Undefined variables (potential issues)
                if results["undefined"]:
                    import pandas as pd

                    st.warning(f"Found {len(results['undefined'])} undefined variables")
                    st.dataframe(
                        pd.DataFrame({"Undefined Variable": results["undefined"]}),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption(
                        "These variables are used but not defined in any process group"
                    )
                else:
                    st.success("No undefined variables!")

            with var_tabs[3]:
                # By processor
                if results["by_processor"]:
                    import pandas as pd

                    proc_var_data = [
                        {
                            "Processor ID": proc_id,
                            "Variables Used": ", ".join(sorted(variables)),
                        }
                        for proc_id, variables in results["by_processor"].items()
                    ]
                    st.dataframe(
                        proc_var_data, use_container_width=True, hide_index=True
                    )
                else:
                    st.info("No processor-variable mappings found")

            # Export button
            if results["defined_variables"] or results["used_variables"]:
                import pandas as pd

                export_data = {
                    "Defined": list(results["defined_variables"].keys()),
                    "Used": sorted(set(results["used_variables"])),
                    "Undefined": results["undefined"],
                }
                # Pad lists to same length for DataFrame
                max_len = max(len(v) for v in export_data.values())
                for key in export_data:
                    export_data[key] += [""] * (max_len - len(export_data[key]))

                csv = pd.DataFrame(export_data).to_csv(index=False)
                st.download_button(
                    label="Download variables as CSV",
                    data=csv,
                    file_name="nifi_variables.csv",
                    mime="text/csv",
                )

    else:
        st.info("👆 Configure connection and fetch a flow to begin analysis")


if __name__ == "__main__":
    main()
