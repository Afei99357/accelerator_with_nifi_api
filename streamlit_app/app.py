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
                            with st.expander(
                                "🔍 Debug: Raw API Response", expanded=False
                            ):
                                st.json(flow_json)

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

                        # Store in session state
                        st.session_state["template_dto"] = template_dto
                        st.session_state["flow_json"] = flow_json

                        # Display summary
                        snippet = template_dto.get("snippet", {})
                        processor_count = len(snippet.get("processors", []))

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
                            st.info(
                                f"""
**Flow Summary:**
- Processors: {processor_count}
- Connections: {len(snippet.get('connections', []))}
- Process Groups: {len(snippet.get('processGroups', []))}
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
                "Classification",
                "Tables",
                "SQL Queries",
                "Lineage",
                "Variables",
            ]
        )

        template_dto = st.session_state["template_dto"]
        snippet = template_dto.get("snippet", {})

        # Overview Tab
        with tabs[0]:
            st.subheader("Flow Overview")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Processors", len(snippet.get("processors", [])))

            with col2:
                st.metric("Connections", len(snippet.get("connections", [])))

            with col3:
                st.metric("Process Groups", len(snippet.get("processGroups", [])))

            st.subheader("Processor List")
            processors = snippet.get("processors", [])

            if processors:
                processor_data = []
                for proc in processors:
                    processor_data.append(
                        {
                            "Name": proc.get("name", ""),
                            "Type": proc.get("type", "").split(".")[-1],
                            "State": proc.get("state", ""),
                            "ID": proc.get("id", ""),
                        }
                    )

                st.dataframe(processor_data, use_container_width=True)
            else:
                st.info("No processors found")

        # Classification Tab
        with tabs[1]:
            st.subheader("Processor Classification")
            st.info("Classification analyzer not yet implemented. Coming soon!")

        # Tables Tab
        with tabs[2]:
            st.subheader("Database Tables")
            st.info("Table extraction analyzer not yet implemented. Coming soon!")

        # SQL Queries Tab
        with tabs[3]:
            st.subheader("SQL Queries")
            st.info("SQL extraction analyzer not yet implemented. Coming soon!")

        # Lineage Tab
        with tabs[4]:
            st.subheader("Table Lineage")
            st.info("Lineage analyzer not yet implemented. Coming soon!")

        # Variables Tab
        with tabs[5]:
            st.subheader("Variable Dependencies")
            st.info("Variables analyzer not yet implemented. Coming soon!")

    else:
        st.info("👆 Configure connection and fetch a flow to begin analysis")


if __name__ == "__main__":
    main()
