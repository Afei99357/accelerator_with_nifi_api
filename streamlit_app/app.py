"""Streamlit web application for NiFi API Analyzer."""

import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from nifi_client.client import NiFiClient, NiFiConnectionConfig, AuthType
from nifi_client.converter import convert_nifi_json_to_template_dto


def main():
    st.set_page_config(
        page_title="NiFi API Analyzer",
        page_icon="🔄",
        layout="wide"
    )

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
            help="Authentication method"
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
            cert_path = st.text_input("Certificate Path", placeholder="/path/to/cert.pem")
            key_path = st.text_input("Key Path", placeholder="/path/to/key.pem")

        verify_ssl = st.checkbox("Verify SSL", value=True)
        timeout = st.slider("Timeout (seconds)", min_value=10, max_value=300, value=30)

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
                        timeout=timeout
                    )

                    client = NiFiClient(config)
                    result = client.test_connection()

                    if result["success"]:
                        st.success(f"✅ {result['message']}")
                        # Store client in session state
                        st.session_state["nifi_client"] = client
                        st.session_state["nifi_config"] = config
                    else:
                        st.error(f"❌ Connection failed: {result.get('error', 'Unknown error')}")

                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

    with col2:
        if st.button("📥 Fetch Flow", type="primary", use_container_width=True):
            if "nifi_client" not in st.session_state:
                st.warning("⚠️ Please test connection first")
            else:
                with st.spinner("Fetching flow..."):
                    try:
                        client = st.session_state["nifi_client"]
                        process_group_id = st.session_state.get("process_group_id", "root")

                        # Fetch flow from NiFi
                        flow_json = client.fetch_flow(process_group_id)

                        # Convert to template_dto
                        template_dto = convert_nifi_json_to_template_dto(
                            flow_json,
                            use_friendly_ids=False,
                            ignore_pass_through=True
                        )

                        # Store in session state
                        st.session_state["template_dto"] = template_dto
                        st.session_state["flow_json"] = flow_json

                        st.success("✅ Flow fetched successfully")

                        # Display summary
                        snippet = template_dto.get("snippet", {})
                        st.info(f"""
                        **Flow Summary:**
                        - Processors: {len(snippet.get('processors', []))}
                        - Connections: {len(snippet.get('connections', []))}
                        - Process Groups: {len(snippet.get('processGroups', []))}
                        """)

                    except Exception as e:
                        st.error(f"❌ Error fetching flow: {str(e)}")

    # Analysis Section
    if "template_dto" in st.session_state:
        st.divider()
        st.header("📊 Analysis")

        # Create tabs for different analyzers
        tabs = st.tabs([
            "Overview",
            "Classification",
            "Tables",
            "SQL Queries",
            "Lineage",
            "Variables"
        ])

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
                    processor_data.append({
                        "Name": proc.get("name", ""),
                        "Type": proc.get("type", "").split(".")[-1],
                        "State": proc.get("state", ""),
                        "ID": proc.get("id", "")
                    })

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
