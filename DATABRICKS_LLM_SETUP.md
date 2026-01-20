# Using Databricks LLM Endpoints Locally

Yes! You can call Databricks LLM endpoints from your local machine. You don't need to be on a Databricks cluster.

## Quick Answer

✅ **You CAN** call Databricks LLM endpoints from your local machine
✅ **You DON'T NEED** to be on a Databricks cluster
✅ **You ONLY NEED** your workspace URL and an access token

## Prerequisites

1. **Databricks Workspace URL**
   - Example: `https://your-workspace.cloud.databricks.com`
   - Or: `https://adb-1234567890123456.7.azuredatabricks.net`

2. **Personal Access Token (PAT)**
   - Generate in Databricks: User Settings → Developer → Access Tokens
   - Or use a Service Principal token

3. **Model Access**
   - Access to Foundation Model APIs (Llama, DBRX, Mixtral, etc.)
   - Or access to custom Model Serving endpoints

## Setup

### Step 1: Get Your Credentials

#### Generate Personal Access Token
1. Log into your Databricks workspace
2. Click your username (top right) → Settings
3. Go to Developer → Access Tokens
4. Click "Generate new token"
5. Set lifetime (e.g., 90 days) and comment
6. Copy the token (you won't see it again!)

### Step 2: Set Environment Variables

Create a `.env` file in your project:

```bash
# .env file
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi1234567890abcdef...
DATABRICKS_MODEL_NAME=databricks-meta-llama-3-1-70b-instruct
```

Or export them in your shell:

```bash
export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
export DATABRICKS_TOKEN="dapi1234567890abcdef..."
export DATABRICKS_MODEL_NAME="databricks-meta-llama-3-1-70b-instruct"
```

### Step 3: Install Additional Dependencies

```bash
pip install python-dotenv  # For loading .env files
```

## Available Models

### Foundation Model APIs (Pay-per-token)

```python
# Llama 3.1 models
"databricks-meta-llama-3-1-70b-instruct"
"databricks-meta-llama-3-1-405b-instruct"

# DBRX
"databricks-dbrx-instruct"

# Mixtral
"databricks-mixtral-8x7b-instruct"

# BGE Embeddings
"databricks-bge-large-en"
```

### Custom Model Serving Endpoints
If you have deployed custom models, use the endpoint name instead.

## Usage Examples

### Example 1: Simple Text Generation

```python
from databricks_llm_client import DatabricksLLMClient, DatabricksLLMConfig

# Configure
config = DatabricksLLMConfig(
    workspace_url="https://your-workspace.cloud.databricks.com",
    token="dapi...",
    model_name="databricks-meta-llama-3-1-70b-instruct"
)

client = DatabricksLLMClient(config)

# Call the model
response = client.call_foundation_model(
    prompt="Explain Apache NiFi in one sentence.",
    temperature=0.1,
    max_tokens=100
)

# Extract text
text = client.extract_text_response(response)
print(text)
```

### Example 2: Using Environment Variables

```python
from databricks_llm_client import create_databricks_client_from_env

# Loads from environment variables
client = create_databricks_client_from_env()

response = client.call_foundation_model(
    prompt="What is a NiFi processor?",
    temperature=0.1
)

print(client.extract_text_response(response))
```

### Example 3: Multi-turn Conversation

```python
messages = [
    {"role": "system", "content": "You are a NiFi expert."},
    {"role": "user", "content": "What is ExecuteSQL processor?"},
    {"role": "assistant", "content": "ExecuteSQL executes SQL queries..."},
    {"role": "user", "content": "How is it different from PutSQL?"}
]

response = client.chat_completion(
    messages=messages,
    temperature=0.1,
    max_tokens=500
)

print(client.extract_text_response(response))
```

### Example 4: With NiFi Analysis

```python
from databricks_llm_client import create_databricks_client_from_env
from nifi_client import NiFiClient, NiFiConnectionConfig, AuthType
from nifi_client import convert_nifi_json_to_template_dto
from analyzers import ClassificationAnalyzer

# Get NiFi flow
nifi_config = NiFiConnectionConfig(host="localhost", port=8080, auth_type=AuthType.NONE)
nifi_client = NiFiClient(nifi_config)
flow_json = nifi_client.fetch_flow("root")
template_dto = convert_nifi_json_to_template_dto(flow_json)

# Analyze
analyzer = ClassificationAnalyzer(template_dto)
results = analyzer.analyze()

# Use LLM to summarize
llm_client = create_databricks_client_from_env()

prompt = f"""
Analyze this NiFi flow summary and provide insights:

Total Processors: {results['total_processors']}
Categories:
{results['summary']}

What are the main purposes of this flow?
"""

response = llm_client.call_foundation_model(prompt)
print(llm_client.extract_text_response(response))
```

## Using with Python dotenv

Install:
```bash
pip install python-dotenv
```

Load environment variables from .env file:
```python
from dotenv import load_dotenv
load_dotenv()  # Loads .env file

from databricks_llm_client import create_databricks_client_from_env
client = create_databricks_client_from_env()
```

## Cost Considerations

### Foundation Model APIs (Pay-per-token)
- Charged based on input + output tokens
- Check Databricks pricing for current rates
- Use smaller models for testing (Llama-70B cheaper than 405B)

### Custom Endpoints
- Charged based on compute (DBUs/hour)
- More cost-effective for high-volume use

## Testing Your Setup

Create `test_databricks_llm.py`:

```python
from databricks_llm_client import create_databricks_client_from_env

try:
    print("Creating client...")
    client = create_databricks_client_from_env()

    print("Calling model...")
    response = client.call_foundation_model(
        prompt="Say 'Hello from Databricks!'",
        temperature=0.1,
        max_tokens=20
    )

    text = client.extract_text_response(response)
    print(f"✅ Success! Response: {text}")

except Exception as e:
    print(f"❌ Error: {e}")
```

Run it:
```bash
python test_databricks_llm.py
```

## Troubleshooting

### Authentication Errors

**Error**: `401 Unauthorized`

**Solutions**:
1. Verify token is correct and not expired
2. Check workspace URL format (include https://)
3. Ensure token has proper permissions
4. Try regenerating the token

### Model Not Found

**Error**: `404 Not Found` or model not available

**Solutions**:
1. Verify model name spelling
2. Check if you have access to Foundation Model APIs
3. Try a different model (e.g., use `databricks-dbrx-instruct`)
4. Contact your Databricks admin for access

### Network Issues

**Error**: Connection timeout

**Solutions**:
1. Check your internet connection
2. Verify workspace URL is accessible
3. Check if firewall/VPN is blocking requests
4. Increase timeout in config

### Rate Limiting

**Error**: `429 Too Many Requests`

**Solutions**:
1. Add retry logic with exponential backoff
2. Reduce request frequency
3. Contact Databricks for rate limit increase

## Architecture

```
┌─────────────────┐
│  Your Local PC  │
│                 │
│  Python Script  │
└────────┬────────┘
         │
         │ HTTPS (REST API)
         │ Authentication: Bearer Token
         │
         ▼
┌─────────────────────────────┐
│   Databricks Cloud          │
│                             │
│  ┌─────────────────────┐   │
│  │ Foundation Model    │   │
│  │ APIs                │   │
│  │  - Llama 3.1        │   │
│  │  - DBRX             │   │
│  │  - Mixtral          │   │
│  └─────────────────────┘   │
│                             │
│  ┌─────────────────────┐   │
│  │ Custom Model        │   │
│  │ Serving Endpoints   │   │
│  └─────────────────────┘   │
└─────────────────────────────┘
```

## Security Best Practices

1. **Never commit tokens to git**
   - Add `.env` to `.gitignore`
   - Use environment variables or secrets manager

2. **Rotate tokens regularly**
   - Set expiration dates
   - Regenerate every 90 days

3. **Use minimal permissions**
   - Create tokens with only needed permissions
   - Use service principals for production

4. **Secure token storage**
   - Don't hardcode tokens in code
   - Use OS keyring or secrets manager

## Integration with Streamlit

Add to your Streamlit app:

```python
import streamlit as st
from databricks_llm_client import DatabricksLLMClient, DatabricksLLMConfig

# In sidebar
with st.sidebar:
    st.header("Databricks LLM")
    db_host = st.text_input("Databricks Host", type="password")
    db_token = st.text_input("Token", type="password")
    db_model = st.selectbox("Model", [
        "databricks-meta-llama-3-1-70b-instruct",
        "databricks-dbrx-instruct"
    ])

if st.button("Ask LLM"):
    config = DatabricksLLMConfig(
        workspace_url=db_host,
        token=db_token,
        model_name=db_model
    )
    client = DatabricksLLMClient(config)
    # Use client...
```

## FAQ

**Q: Do I need to be on a Databricks cluster?**
A: No! You can call from anywhere with internet access.

**Q: Will this work from my laptop?**
A: Yes, as long as you have the workspace URL and token.

**Q: What about the NiFi connection?**
A: NiFi and Databricks LLM are independent. You can:
- Call local NiFi + Databricks LLM ✅
- Call remote NiFi + Databricks LLM ✅
- Call local NiFi + local LLM ✅

**Q: Is this secure?**
A: Yes, using HTTPS with bearer token authentication.

**Q: What's the latency?**
A: Typically 1-5 seconds depending on model size and prompt length.

**Q: Can I use this in production?**
A: Yes, but consider using service principals instead of personal tokens.

## Next Steps

1. ✅ Set up your credentials
2. ✅ Test with `test_databricks_llm.py`
3. ✅ Integrate with your NiFi analyzer
4. ✅ Build intelligent analysis features!
