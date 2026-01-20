# Experimental Features (experimental_test branch)

This branch contains experimental features for integrating Databricks LLM with NiFi analysis.

## What's New

### ✨ Databricks LLM Integration

You can now call Databricks LLM endpoints **from your local machine** to generate AI-powered insights about your NiFi flows!

**Key Point**: You don't need to be on a Databricks cluster. This works entirely locally with API calls to Databricks.

## New Files

### 1. `databricks_llm_client.py`
Complete client for calling Databricks Foundation Model APIs:
- ✅ Llama 3.1 (70B, 405B)
- ✅ DBRX Instruct
- ✅ Mixtral 8x7B
- ✅ Custom model serving endpoints
- ✅ Multi-turn conversations
- ✅ Environment variable configuration

### 2. `DATABRICKS_LLM_SETUP.md`
Comprehensive guide covering:
- How to get Databricks credentials
- Available models and pricing
- Setup instructions
- Troubleshooting
- Security best practices
- FAQ

### 3. `example_nifi_llm_analysis.py`
End-to-end workflow:
1. Connect to NiFi (locally)
2. Fetch and analyze flow
3. Call Databricks LLM (from local machine)
4. Generate AI insights about your flow

**Features**:
- Automated analysis mode
- Interactive Q&A mode
- Context-aware responses

### 4. `test_databricks_llm.py`
Test suite for validating Databricks connectivity:
- Environment variable test
- Direct configuration test
- Multi-turn conversation test
- Connection troubleshooting

### 5. `.env.example`
Template for environment variables configuration.

## Quick Start

### Step 1: Get Databricks Credentials

1. Log into your Databricks workspace
2. Go to: User Settings → Developer → Access Tokens
3. Generate a new token
4. Copy your workspace URL and token

### Step 2: Configure Environment

```bash
cd /home/eric/Projects/nifi_api_analyzer

# Copy template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Set these variables:
```bash
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi1234567890abcdef...
DATABRICKS_MODEL_NAME=databricks-meta-llama-3-1-70b-instruct
```

### Step 3: Install Dependencies

```bash
source .venv/bin/activate  # Or create new venv
pip install -r requirements.txt
```

### Step 4: Test Connection

```bash
python test_databricks_llm.py
```

Expected output:
```
✅ Client created
✅ API call successful
✅ Response received
🎉 Success! Databricks LLM is working correctly.
```

### Step 5: Run Full Analysis

```bash
python example_nifi_llm_analysis.py
```

This will:
1. Connect to your local NiFi instance
2. Fetch and analyze the flow
3. Call Databricks LLM with analysis context
4. Generate 3 AI-powered insights:
   - Flow summary
   - Data architecture description
   - Potential issues and improvements

### Step 6: Interactive Mode

```bash
python example_nifi_llm_analysis.py interactive
```

Ask questions about your NiFi flow in real-time!

## Usage Examples

### Basic LLM Call

```python
from databricks_llm_client import create_databricks_client_from_env

client = create_databricks_client_from_env()

response = client.call_foundation_model(
    prompt="Explain Apache NiFi in one sentence.",
    temperature=0.1,
    max_tokens=100
)

print(client.extract_text_response(response))
```

### With NiFi Analysis

```python
from nifi_client import NiFiClient, NiFiConnectionConfig, AuthType
from nifi_client import convert_nifi_json_to_template_dto
from analyzers import ClassificationAnalyzer
from databricks_llm_client import create_databricks_client_from_env

# Fetch NiFi flow
nifi_config = NiFiConnectionConfig(host="localhost", port=8080, auth_type=AuthType.NONE)
nifi_client = NiFiClient(nifi_config)
flow_json = nifi_client.fetch_flow("root")
template_dto = convert_nifi_json_to_template_dto(flow_json)

# Analyze
analyzer = ClassificationAnalyzer(template_dto)
results = analyzer.analyze()

# Generate LLM insights
llm_client = create_databricks_client_from_env()

prompt = f"""
This NiFi flow has {results['total_processors']} processors.
Categories: {results['summary']}

What does this flow do?
"""

response = llm_client.call_foundation_model(prompt)
print(llm_client.extract_text_response(response))
```

### Multi-turn Conversation

```python
messages = [
    {"role": "system", "content": "You are a NiFi expert."},
    {"role": "user", "content": "What is ExecuteSQL?"},
    {"role": "assistant", "content": "ExecuteSQL executes SQL queries..."},
    {"role": "user", "content": "How is it different from PutSQL?"}
]

response = llm_client.chat_completion(messages)
print(llm_client.extract_text_response(response))
```

## Architecture

```
┌─────────────────────┐
│   Your Local PC     │
│                     │
│  ┌───────────────┐ │
│  │  NiFi Client  │ │──┐
│  └───────────────┘ │  │
│                     │  │
│  ┌───────────────┐ │  │
│  │  Analyzers    │ │  │
│  └───────────────┘ │  │
│                     │  │
│  ┌───────────────┐ │  │
│  │ Databricks    │ │  │
│  │ LLM Client    │ │  │
│  └───────────────┘ │  │
└─────────────────────┘  │
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
  ┌──────────┐   ┌──────────┐   ┌──────────┐
  │  Local   │   │Databricks│   │   LLM    │
  │   NiFi   │   │  Cloud   │   │ Response │
  └──────────┘   └──────────┘   └──────────┘
```

## Key Benefits

### ✅ Works Locally
- No need to be on Databricks cluster
- Call from your laptop/desktop
- Works with local or remote NiFi

### ✅ Powerful AI Insights
- Automatically summarizes flows
- Identifies architecture patterns
- Suggests improvements
- Answers questions about your flow

### ✅ Multiple Models
- Choose from Llama, DBRX, Mixtral
- Balance cost vs. capability
- Use custom endpoints

### ✅ Easy Integration
- Simple Python API
- Environment variable config
- Multi-turn conversations
- Error handling built-in

## Cost Considerations

### Foundation Model APIs
Pay-per-token pricing:
- **Llama 3.1 70B**: ~$0.001/1K tokens (cheaper)
- **Llama 3.1 405B**: ~$0.005/1K tokens (more capable)
- **DBRX Instruct**: ~$0.0015/1K tokens

Example cost for analyzing a typical NiFi flow:
- Input: ~500 tokens (flow analysis context)
- Output: ~300 tokens (insights)
- Total: ~800 tokens ≈ **$0.001** per analysis (70B model)

### Tips to Minimize Cost
1. Use smaller models for simple tasks (70B instead of 405B)
2. Keep prompts concise
3. Limit max_tokens in responses
4. Cache results when possible

## Troubleshooting

### "401 Unauthorized"
- Token expired → Generate new one
- Wrong token → Check copy/paste
- Wrong workspace URL → Verify format

### "Model not found"
- Check spelling: `databricks-meta-llama-3-1-70b-instruct`
- Verify access to Foundation Model APIs
- Contact admin for permissions

### "Connection timeout"
- Check internet connection
- Increase timeout in config
- Verify workspace URL is accessible

### Import errors
```bash
# Make sure you're in the right directory
cd /home/eric/Projects/nifi_api_analyzer

# Activate venv
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

## Security

### ✅ DO
- Store tokens in `.env` file
- Add `.env` to `.gitignore`
- Use environment variables
- Rotate tokens regularly (90 days)
- Use minimal permissions

### ❌ DON'T
- Commit tokens to git
- Hardcode tokens in code
- Share tokens in Slack/email
- Use same token everywhere
- Set unlimited token lifetime

## Testing Checklist

Before using in production:

- [ ] Test Databricks connection with `test_databricks_llm.py`
- [ ] Verify NiFi connection works locally
- [ ] Run example analysis end-to-end
- [ ] Test error handling (wrong token, network issues)
- [ ] Check token permissions
- [ ] Estimate costs for your use case
- [ ] Set up proper token rotation

## Next Steps

1. **Test it**: Run `test_databricks_llm.py`
2. **Explore**: Try `example_nifi_llm_analysis.py interactive`
3. **Customize**: Modify prompts for your use case
4. **Integrate**: Add to your own workflows
5. **Share feedback**: What works? What's missing?

## Feedback & Issues

This is experimental! Please report:
- Connection issues
- Model errors
- Feature requests
- Documentation improvements

## Merge to Main

Once tested and stable, this will be merged to `main` branch.

For now, stay on `experimental_test` for these features:
```bash
git checkout experimental_test
git pull origin experimental_test
```

---

**Ready to try it?**

```bash
# 1. Set up credentials
cp .env.example .env
nano .env

# 2. Test connection
python test_databricks_llm.py

# 3. Run analysis
python example_nifi_llm_analysis.py

# 4. Interactive mode
python example_nifi_llm_analysis.py interactive
```

🚀 **Have fun exploring!**
