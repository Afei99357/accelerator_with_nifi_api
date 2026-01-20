"""Quick test script for Databricks LLM connectivity."""

import os
from dotenv import load_dotenv
from databricks_llm_client import create_databricks_client_from_env, DatabricksLLMClient, DatabricksLLMConfig

# Load environment variables
load_dotenv()


def test_with_env_vars():
    """Test using environment variables."""
    print("=" * 70)
    print("Testing Databricks LLM Connection (Environment Variables)")
    print("=" * 70)

    # Check if environment variables are set
    required_vars = ["DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_MODEL_NAME"]
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        print(f"\n❌ Missing environment variables: {', '.join(missing)}")
        print("\nPlease set them in .env file or export them:")
        print("  export DATABRICKS_HOST='https://your-workspace.cloud.databricks.com'")
        print("  export DATABRICKS_TOKEN='dapi...'")
        print("  export DATABRICKS_MODEL_NAME='databricks-meta-llama-3-1-70b-instruct'")
        return False

    print(f"\n✅ Environment variables found")
    print(f"   Host: {os.getenv('DATABRICKS_HOST')}")
    print(f"   Model: {os.getenv('DATABRICKS_MODEL_NAME')}")
    print(f"   Token: {'*' * 20}...")

    try:
        print("\n[1/3] Creating client...")
        client = create_databricks_client_from_env()
        print("✅ Client created")

        print("\n[2/3] Calling model...")
        response = client.call_foundation_model(
            prompt="Say 'Hello from Databricks!' and nothing else.",
            temperature=0.1,
            max_tokens=20
        )
        print("✅ API call successful")

        print("\n[3/3] Extracting response...")
        text = client.extract_text_response(response)
        print(f"✅ Response received\n")
        print("-" * 70)
        print(f"Model response: {text}")
        print("-" * 70)

        print("\n🎉 Success! Databricks LLM is working correctly.")
        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Check your Databricks workspace URL is correct")
        print("  2. Verify your token hasn't expired")
        print("  3. Ensure you have access to the model")
        print("  4. Try a different model name")
        return False


def test_direct_config():
    """Test with direct configuration (for manual testing)."""
    print("\n" + "=" * 70)
    print("Testing with Direct Configuration")
    print("=" * 70)

    # Replace these with your actual values for testing
    workspace_url = input("\nEnter Databricks workspace URL: ").strip()
    if not workspace_url:
        print("Skipping direct config test")
        return False

    token = input("Enter your token: ").strip()
    model = input("Enter model name (or press Enter for default): ").strip()
    if not model:
        model = "databricks-meta-llama-3-1-70b-instruct"

    try:
        print("\nConnecting...")
        config = DatabricksLLMConfig(
            workspace_url=workspace_url,
            token=token,
            model_name=model
        )

        client = DatabricksLLMClient(config)

        print("Calling model...")
        response = client.call_foundation_model(
            prompt="Say 'Hello!' and nothing else.",
            temperature=0.1,
            max_tokens=10
        )

        text = client.extract_text_response(response)
        print(f"\n✅ Success! Response: {text}")
        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def test_conversation():
    """Test multi-turn conversation."""
    print("\n" + "=" * 70)
    print("Testing Multi-turn Conversation")
    print("=" * 70)

    try:
        client = create_databricks_client_from_env()

        messages = [
            {"role": "system", "content": "You are a helpful assistant. Be concise."},
            {"role": "user", "content": "What is Apache NiFi in one sentence?"}
        ]

        print("\nUser: What is Apache NiFi in one sentence?")
        response = client.chat_completion(messages, temperature=0.1, max_tokens=100)
        answer = client.extract_text_response(response)
        print(f"Assistant: {answer}")

        # Follow-up
        messages.append({"role": "assistant", "content": answer})
        messages.append({"role": "user", "content": "What's a processor?"})

        print("\nUser: What's a processor?")
        response = client.chat_completion(messages, temperature=0.1, max_tokens=100)
        answer = client.extract_text_response(response)
        print(f"Assistant: {answer}")

        print("\n✅ Multi-turn conversation works!")
        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("Databricks LLM Connection Test Suite")
    print("=" * 70)

    results = []

    # Test 1: Environment variables
    results.append(("Environment Variables", test_with_env_vars()))

    # Test 2: Conversation (only if env vars worked)
    if results[0][1]:
        results.append(("Multi-turn Conversation", test_conversation()))

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 All tests passed! You're ready to use Databricks LLM locally.")
        print("\nNext steps:")
        print("  1. Run: python example_nifi_llm_analysis.py")
        print("  2. Or integrate into your own scripts")
    else:
        print("⚠️  Some tests failed. Check your configuration.")
        print("\nHelp:")
        print("  1. Copy .env.example to .env")
        print("  2. Fill in your Databricks credentials")
        print("  3. Run this test again")
    print("=" * 70)


if __name__ == "__main__":
    main()
