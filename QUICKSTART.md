# Quick Start Guide

## Setup

### Method 1: Using uv (Recommended - Fast!)

1. Navigate to the project directory:
```bash
cd /home/eric/Projects/nifi_api_analyzer
```

2. Install dependencies with uv:
```bash
uv sync
```

That's it! uv automatically creates the virtual environment and installs all dependencies.

3. Run commands with uv:
```bash
uv run streamlit run streamlit_app/app.py
uv run python example_usage.py
```

### Method 2: Using pip (Traditional)

1. Navigate to the project directory:
```bash
cd /home/eric/Projects/nifi_api_analyzer
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage Options

### Option 1: Streamlit Web UI (Recommended for exploration)

Start the web application:
```bash
streamlit run streamlit_app/app.py
```

Then open your browser to http://localhost:8501

**Features:**
- Visual connection configuration
- Test connection before fetching
- Tabbed interface for different analyses
- Interactive exploration

### Option 2: Python Script (Recommended for automation)

Run the example script:
```bash
python example_usage.py
```

Or create your own script:
```python
from nifi_client import NiFiClient, NiFiConnectionConfig, AuthType
from nifi_client import convert_nifi_json_to_template_dto
from analyzers import ClassificationAnalyzer

# Connect to NiFi
config = NiFiConnectionConfig(
    host="localhost",
    port=8080,
    auth_type=AuthType.NONE
)
client = NiFiClient(config)

# Fetch and convert flow
flow_json = client.fetch_flow("root")
template_dto = convert_nifi_json_to_template_dto(flow_json)

# Analyze
analyzer = ClassificationAnalyzer(template_dto)
results = analyzer.analyze()
print(results)
```

### Option 3: Interactive Python

```bash
python
```

```python
>>> from nifi_client import *
>>> config = NiFiConnectionConfig(host="localhost", port=8080, auth_type=AuthType.NONE)
>>> client = NiFiClient(config)
>>> result = client.test_connection()
>>> print(result)
```

## Configuration

### No Authentication
```python
config = NiFiConnectionConfig(
    host="localhost",
    port=8080,
    auth_type=AuthType.NONE,
    verify_ssl=False  # For self-signed certs
)
```

### Basic Authentication
```python
config = NiFiConnectionConfig(
    host="localhost",
    port=8080,
    auth_type=AuthType.BASIC,
    username="admin",
    password="your_password",
    verify_ssl=False
)
```

### Environment Variables
```bash
export NIFI_HOST=localhost
export NIFI_PORT=8080
export NIFI_AUTH_TYPE=basic
export NIFI_USERNAME=admin
export NIFI_PASSWORD=password
export NIFI_VERIFY_SSL=false
```

```python
from nifi_client import create_nifi_client_from_env
client = create_nifi_client_from_env()
```

## Available Analyzers

### 1. ClassificationAnalyzer
Categorizes processors by function (database, transformation, flow_control, etc.)
```python
from analyzers import ClassificationAnalyzer
analyzer = ClassificationAnalyzer(template_dto)
results = analyzer.analyze()
```

### 2. TableExtractionAnalyzer
Extracts database table references from processors
```python
from analyzers import TableExtractionAnalyzer
analyzer = TableExtractionAnalyzer(template_dto)
results = analyzer.analyze()
tables = results["tables"]  # List of all tables
```

### 3. SQLExtractionAnalyzer
Extracts SQL queries from processor configurations
```python
from analyzers import SQLExtractionAnalyzer
analyzer = SQLExtractionAnalyzer(template_dto)
results = analyzer.analyze()
select_queries = results["by_type"]["SELECT"]
```

### 4. LineageAnalyzer
Traces data lineage between tables through processors
```python
from analyzers import LineageAnalyzer
analyzer = LineageAnalyzer(template_dto)
results = analyzer.analyze()
lineages = results["lineages"]  # List of source -> target paths
```

### 5. VariablesAnalyzer
Analyzes NiFi variable definitions and usage
```python
from analyzers import VariablesAnalyzer
analyzer = VariablesAnalyzer(template_dto)
results = analyzer.analyze()
undefined = results["undefined"]  # Variables used but not defined
```

## Testing

Run tests with pytest:
```bash
pytest tests/
```

Run specific test:
```bash
pytest tests/test_client.py -v
```

## Common Issues

### SSL Certificate Errors
If you get SSL errors with self-signed certificates:
```python
config = NiFiConnectionConfig(
    host="localhost",
    verify_ssl=False
)
```

### Connection Timeout
For large flows, increase timeout:
```python
config = NiFiConnectionConfig(
    host="localhost",
    timeout=120  # 2 minutes
)
```

### Import Errors
Make sure you're in the project directory and have activated the virtual environment:
```bash
cd /home/eric/Projects/nifi_api_analyzer
source .venv/bin/activate
```

## Next Steps

1. **Test connection** - Start with `streamlit_app/app.py` to visually test your connection
2. **Fetch a flow** - Use "root" for the main process group
3. **Explore analyzers** - Try each analyzer to see what data you can extract
4. **Customize** - Extend BaseAnalyzer to create your own analysis logic

## Architecture Benefits

✅ **API-First** - No XML files needed
✅ **Real-time** - Works with live NiFi instances
✅ **Clean** - Minimal dependencies
✅ **Extensible** - Easy to add new analyzers
✅ **In-memory** - All analysis happens in memory

## Comparison with Old Approach

| Feature | Old (XML-based) | New (API-based) |
|---------|----------------|-----------------|
| Input | XML template files | Live NiFi API |
| Setup | Manual XML export | Direct connection |
| Real-time | No | Yes |
| Component IDs | Lost in export | Preserved |
| File I/O | Required | Not required |
| Dependencies | Many | Minimal |

## Help

For issues or questions:
- Check README.md for detailed documentation
- Review example_usage.py for complete workflow
- Run tests to verify installation
