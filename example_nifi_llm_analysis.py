"""Example: NiFi Analysis with Databricks LLM.

This script demonstrates how to:
1. Fetch NiFi flow data locally
2. Analyze it with built-in analyzers
3. Use Databricks LLM (called from local machine) to generate insights
"""

import os

from dotenv import load_dotenv

from analyzers import (
    SQLExtractionAnalyzer,
    TableExtractionAnalyzer,
)
from databricks_llm_client import create_databricks_client_from_env
from nifi_client import (
    AuthType,
    NiFiClient,
    NiFiConnectionConfig,
    convert_nifi_json_to_template_dto,
)

# Load environment variables
load_dotenv()


def analyze_nifi_with_llm():
    """Complete workflow: NiFi analysis + LLM insights."""

    print("=" * 70)
    print("NiFi Flow Analysis with Databricks LLM")
    print("=" * 70)

    # Step 1: Connect to NiFi (local)
    print("\n[1/5] Connecting to NiFi...")
    nifi_config = NiFiConnectionConfig(
        host=os.getenv("NIFI_HOST", "localhost"),
        port=int(os.getenv("NIFI_PORT", "8080")),
        protocol=os.getenv("NIFI_PROTOCOL", "https"),
        auth_type=AuthType(os.getenv("NIFI_AUTH_TYPE", "none")),
        verify_ssl=os.getenv("NIFI_VERIFY_SSL", "false").lower() == "true",
        timeout=30,
    )

    nifi_client = NiFiClient(nifi_config)

    # Test connection
    result = nifi_client.test_connection()
    if not result["success"]:
        print(f"❌ NiFi connection failed: {result.get('error')}")
        return

    print(f"✅ Connected to NiFi {result['version']}")

    # Step 2: Fetch flow
    print("\n[2/5] Fetching NiFi flow...")
    try:
        flow_json = nifi_client.fetch_flow("root")
        template_dto = convert_nifi_json_to_template_dto(
            flow_json, ignore_pass_through=True
        )
        print("✅ Flow fetched and converted")
    except Exception as e:
        print(f"❌ Error fetching flow: {e}")
        return

    # Step 3: Analyze flow
    print("\n[3/5] Analyzing flow...")

    # Tables
    table_analyzer = TableExtractionAnalyzer(template_dto)
    table_results = table_analyzer.analyze()

    # SQL
    sql_analyzer = SQLExtractionAnalyzer(template_dto)
    sql_results = sql_analyzer.analyze()

    print("✅ Analysis complete")
    print(f"   - Tables: {table_results['table_count']}")
    print(f"   - SQL Queries: {sql_results['total_count']}")

    # Step 4: Connect to Databricks LLM
    print("\n[4/5] Connecting to Databricks LLM...")
    try:
        llm_client = create_databricks_client_from_env()
        print("✅ Databricks LLM client initialized")
    except Exception as e:
        print(f"❌ Error connecting to Databricks: {e}")
        print("\nMake sure you have set:")
        print("  - DATABRICKS_HOST")
        print("  - DATABRICKS_TOKEN")
        print("  - DATABRICKS_MODEL_NAME")
        return

    # Step 5: Generate insights with LLM
    print("\n[5/5] Generating insights with LLM...")
    print("-" * 70)

    # Build context for LLM
    context = build_analysis_context(table_results, sql_results)

    # Ask LLM multiple questions
    questions = [
        {
            "title": "Flow Summary",
            "prompt": f"""Based on this NiFi flow analysis:

{context}

Provide a concise 2-3 sentence summary of what this flow does.""",
        },
        {
            "title": "Data Architecture",
            "prompt": f"""Based on this NiFi flow analysis:

{context}

Describe the data architecture. What are the source systems,
transformations, and target systems?""",
        },
        {
            "title": "Potential Issues",
            "prompt": f"""Based on this NiFi flow analysis:

{context}

Identify any potential issues, bottlenecks, or areas for improvement.""",
        },
    ]

    for i, question in enumerate(questions, 1):
        print(f"\n{'='*70}")
        print(f"Insight {i}: {question['title']}")
        print("=" * 70)

        try:
            response = llm_client.call_foundation_model(
                prompt=question["prompt"], temperature=0.1, max_tokens=500
            )

            answer = llm_client.extract_text_response(response)
            print(f"\n{answer}\n")

        except Exception as e:
            print(f"❌ Error: {e}")

    print("=" * 70)
    print("Analysis complete!")
    nifi_client.close()


def build_analysis_context(table_results, sql_results):
    """Build structured context for LLM from analysis results."""

    context_parts = []

    # Tables
    if table_results["tables"]:
        context_parts.append(f"\nDatabase Tables ({table_results['table_count']}):")
        for table in table_results["tables"][:10]:  # Limit to first 10
            context_parts.append(f"  - {table}")
        if len(table_results["tables"]) > 10:
            context_parts.append(f"  ... and {len(table_results['tables']) - 10} more")

        if table_results["sources"]:
            context_parts.append("\nSource Tables (reading from):")
            for src in table_results["sources"][:5]:
                context_parts.append(f"  - {src['name']} ({src['type']})")

        if table_results["targets"]:
            context_parts.append("\nTarget Tables (writing to):")
            for tgt in table_results["targets"][:5]:
                context_parts.append(f"  - {tgt['name']} ({tgt['type']})")

    # SQL queries
    if sql_results["total_count"] > 0:
        context_parts.append(f"\nSQL Queries ({sql_results['total_count']}):")
        for sql_type, queries in sql_results["by_type"].items():
            if queries:
                context_parts.append(f"  - {sql_type}: {len(queries)}")

    return "\n".join(context_parts)


def interactive_llm_query():
    """Interactive mode: Ask questions about your NiFi flow."""

    print("\n" + "=" * 70)
    print("Interactive LLM Query Mode")
    print("=" * 70)

    # Load NiFi analysis
    print("\nLoading NiFi flow...")
    nifi_config = NiFiConnectionConfig(
        host=os.getenv("NIFI_HOST", "localhost"),
        port=int(os.getenv("NIFI_PORT", "8080")),
        auth_type=AuthType.NONE,
        verify_ssl=False,
    )

    nifi_client = NiFiClient(nifi_config)
    flow_json = nifi_client.fetch_flow("root")
    template_dto = convert_nifi_json_to_template_dto(flow_json)

    # Analyze
    table_analyzer = TableExtractionAnalyzer(template_dto)
    table_results = table_analyzer.analyze()

    context = build_analysis_context(table_results, {})

    # Initialize LLM
    llm_client = create_databricks_client_from_env()

    print("\n✅ Ready! Ask questions about your NiFi flow (type 'exit' to quit)")
    print("\nFlow Summary:")
    print(f"  - {table_results['table_count']} tables")

    # Interactive loop
    conversation = [
        {
            "role": "system",
            "content": (
                f"You are a NiFi expert. Here's the flow analysis:\n\n"
                f"{context}\n\nAnswer questions about this flow."
            ),
        }
    ]

    while True:
        print("\n" + "-" * 70)
        user_question = input("Your question: ").strip()

        if user_question.lower() in ["exit", "quit", "q"]:
            print("Goodbye!")
            break

        if not user_question:
            continue

        # Add to conversation
        conversation.append({"role": "user", "content": user_question})

        try:
            # Call LLM
            response = llm_client.chat_completion(
                messages=conversation, temperature=0.1, max_tokens=500
            )

            answer = llm_client.extract_text_response(response)

            # Add to conversation history
            conversation.append({"role": "assistant", "content": answer})

            print(f"\n{answer}")

        except Exception as e:
            print(f"❌ Error: {e}")

    nifi_client.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        interactive_llm_query()
    else:
        analyze_nifi_with_llm()

        print("\n" + "=" * 70)
        print("💡 Tip: Run in interactive mode with:")
        print("   python example_nifi_llm_analysis.py interactive")
        print("=" * 70)
