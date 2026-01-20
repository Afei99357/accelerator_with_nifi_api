"""Example usage of NiFi API Analyzer."""

from analyzers import (
    LineageAnalyzer,
    SQLExtractionAnalyzer,
    TableExtractionAnalyzer,
    VariablesAnalyzer,
)
from nifi_client import (
    AuthType,
    NiFiClient,
    NiFiConnectionConfig,
    convert_nifi_json_to_template_dto,
)


def main():
    """Example workflow for analyzing a NiFi flow."""

    # Step 1: Configure connection
    print("Configuring NiFi connection...")
    config = NiFiConnectionConfig(
        host="localhost",
        port=8080,
        protocol="https",
        auth_type=AuthType.NONE,
        verify_ssl=False,  # For self-signed certificates
        timeout=30,
    )

    # Step 2: Create client and test connection
    print("\nTesting connection...")
    client = NiFiClient(config)
    result = client.test_connection()

    if result["success"]:
        print(f"✓ Connected to NiFi {result['version']}")
    else:
        print(f"✗ Connection failed: {result.get('error')}")
        return

    # Step 3: Fetch flow from NiFi
    print("\nFetching flow from NiFi...")
    try:
        flow_json = client.fetch_flow("root")
        print("✓ Flow fetched successfully")
    except Exception as e:
        print(f"✗ Error fetching flow: {e}")
        return

    # Step 4: Convert to template_dto format
    print("\nConverting flow to template_dto format...")
    template_dto = convert_nifi_json_to_template_dto(
        flow_json, use_friendly_ids=False, ignore_pass_through=True
    )

    snippet = template_dto.get("snippet", {})
    print("✓ Flow converted:")
    print(f"  - Processors: {len(snippet.get('processors', []))}")
    print(f"  - Connections: {len(snippet.get('connections', []))}")
    print(f"  - Process Groups: {len(snippet.get('processGroups', []))}")

    # Step 5: Run analyzers
    print("\n" + "=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)

    # Table Extraction
    print("\n1. Database Tables")
    print("-" * 60)
    table_analyzer = TableExtractionAnalyzer(template_dto)
    table_results = table_analyzer.analyze()

    print(f"Total tables found: {table_results['table_count']}")
    if table_results["tables"]:
        print("\nTables:")
        for table in table_results["tables"][:10]:  # Show first 10
            print(f"  - {table}")
        if len(table_results["tables"]) > 10:
            print(f"  ... and {len(table_results['tables']) - 10} more")

    # SQL Extraction
    print("\n2. SQL Queries")
    print("-" * 60)
    sql_analyzer = SQLExtractionAnalyzer(template_dto)
    sql_results = sql_analyzer.analyze()

    print(f"Total queries found: {sql_results['total_count']}")
    print("\nBy type:")
    for sql_type, queries in sql_results["by_type"].items():
        if queries:
            print(f"  - {sql_type}: {len(queries)}")

    # Lineage Analysis
    print("\n3. Data Lineage")
    print("-" * 60)
    lineage_analyzer = LineageAnalyzer(template_dto)
    lineage_results = lineage_analyzer.analyze()

    print(f"Total lineage paths: {lineage_results['lineage_count']}")

    if lineage_results["lineages"]:
        print("\nSample lineages:")
        for lineage in lineage_results["lineages"][:5]:  # Show first 5
            print(f"  {lineage['source_table']} -> {lineage['target_table']}")

    source_tables = lineage_analyzer.get_source_tables()
    sink_tables = lineage_analyzer.get_sink_tables()
    print(f"\nSource tables (no upstream): {len(source_tables)}")
    print(f"Sink tables (no downstream): {len(sink_tables)}")

    # Variables Analysis
    print("\n4. Variables")
    print("-" * 60)
    var_analyzer = VariablesAnalyzer(template_dto)
    var_results = var_analyzer.analyze()

    print(f"Defined variables: {var_results['defined_count']}")
    print(f"Used variables: {var_results['used_count']}")
    print(f"Undefined variables: {var_results['undefined_count']}")

    if var_results["undefined"]:
        print("\n⚠ Warning: Undefined variables found:")
        for var in var_results["undefined"]:
            print(f"  - {var}")

    # Validation
    validation = var_analyzer.validate_variables()
    if validation["is_valid"]:
        print("\n✓ All variables are properly defined")
    else:
        print(f"\n✗ {validation['message']}")

    # Step 6: Cleanup
    print("\n" + "=" * 60)
    client.close()
    print("Analysis complete!")


if __name__ == "__main__":
    main()
