# NiFi API Analyzer

A clean, API-first NiFi analysis tool that works directly with live NiFi instances via REST API.

## Features

- **API-First**: Fetches flow data directly from NiFi REST API (no XML files needed)
- **Live Analysis**: Works with running NiFi instances in real-time
- **Multiple Authentication**: Supports basic auth, bearer tokens, and certificate-based auth
- **Comprehensive Analysis**:
  - Processor classification
  - Table extraction (database operations)
  - SQL query extraction
  - Data lineage tracking
  - Variable dependency analysis

## Project Structure

```
nifi_api_analyzer/
├── nifi_client/           # NiFi REST API client
│   ├── client.py          # API client with auth support
│   ├── converter.py       # Convert API JSON to template_dto
│   └── models.py          # Data models and utilities
├── analyzers/             # Analysis modules
│   ├── base.py            # Base analyzer class
│   ├── classification.py  # Processor classification
│   ├── table_extraction.py # Extract database tables
│   ├── sql_extraction.py  # Extract SQL queries
│   ├── lineage.py         # Table lineage analysis
│   └── variables.py       # Variable dependencies
├── streamlit_app/         # Web UI
│   └── app.py             # Streamlit application
└── tests/                 # Unit tests
```

## Installation

1. Clone the repository:
```bash
cd /home/eric/Projects/nifi_api_analyzer
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

### Environment Variables

You can configure the NiFi connection using environment variables:

```bash
export NIFI_HOST=localhost
export NIFI_PORT=8080
export NIFI_PROTOCOL=https
export NIFI_AUTH_TYPE=basic  # Options: none, basic, bearer, certificate
export NIFI_USERNAME=your_username
export NIFI_PASSWORD=your_password
export NIFI_VERIFY_SSL=false  # For self-signed certificates
```

### Programmatic Configuration

```python
from nifi_client.client import NiFiClient, NiFiConnectionConfig, AuthType

config = NiFiConnectionConfig(
    host="localhost",
    port=8080,
    protocol="https",
    auth_type=AuthType.BASIC,
    username="admin",
    password="password",
    verify_ssl=False
)

client = NiFiClient(config)
```

## Usage

### Using the Streamlit UI

Run the web application:

```bash
streamlit run streamlit_app/app.py
```

Then open your browser to http://localhost:8501

### Using the API Client Directly

```python
from nifi_client.client import NiFiClient, NiFiConnectionConfig, AuthType
from nifi_client.converter import convert_nifi_json_to_template_dto

# Create client
config = NiFiConnectionConfig(
    host="localhost",
    port=8080,
    auth_type=AuthType.NONE
)
client = NiFiClient(config)

# Test connection
result = client.test_connection()
print(f"Connected: {result['success']}")

# Fetch flow
flow_json = client.fetch_flow("root")

# Convert to template_dto format
template_dto = convert_nifi_json_to_template_dto(flow_json)

# Analyze
from analyzers.classification import ClassificationAnalyzer
analyzer = ClassificationAnalyzer(template_dto)
results = analyzer.analyze()
```

### Using Analyzers

```python
from analyzers.classification import ClassificationAnalyzer
from analyzers.table_extraction import TableExtractionAnalyzer

# Classification
classifier = ClassificationAnalyzer(template_dto)
classification_results = classifier.analyze()

# Table extraction
table_analyzer = TableExtractionAnalyzer(template_dto)
table_results = table_analyzer.analyze()
```

## Authentication Methods

### No Authentication
```python
config = NiFiConnectionConfig(
    host="localhost",
    auth_type=AuthType.NONE
)
```

### Basic Authentication
```python
config = NiFiConnectionConfig(
    host="localhost",
    auth_type=AuthType.BASIC,
    username="admin",
    password="password"
)
```

### Bearer Token
```python
config = NiFiConnectionConfig(
    host="localhost",
    auth_type=AuthType.BEARER,
    token="your_bearer_token"
)
```

### Certificate-Based (mTLS)
```python
config = NiFiConnectionConfig(
    host="localhost",
    auth_type=AuthType.CERTIFICATE,
    cert_path="/path/to/client.crt",
    key_path="/path/to/client.key"
)
```

## Development

### Running Tests

```bash
pytest tests/
```

### Adding a New Analyzer

1. Create a new file in `analyzers/` (e.g., `my_analyzer.py`)
2. Inherit from `BaseAnalyzer`
3. Implement the `analyze()` method

```python
from analyzers.base import BaseAnalyzer
from typing import Any, Dict

class MyAnalyzer(BaseAnalyzer):
    def analyze(self) -> Dict[str, Any]:
        # Your analysis logic here
        processors = self._get_all_processors()

        results = {
            "processor_count": len(processors),
            # Add more analysis results
        }

        return results
```

## Architecture

### API-First Design

Unlike traditional XML-based NiFi analyzers, this tool:
- Fetches flow data directly from NiFi REST API
- Works with live, running flows
- Preserves actual component IDs from the system
- No file I/O required
- All analysis happens in-memory

### Template DTO Format

The converter transforms NiFi API JSON into a normalized `template_dto` format:

```python
{
    "template": {
        "id": "...",
        "name": "...",
        "description": "..."
    },
    "snippet": {
        "processors": [...],
        "connections": [...],
        "processGroups": [...],
        "controllerServices": [...]
    }
}
```

All analyzers work with this standardized format.

## Comparison with XML-Based Approach

| Aspect | XML-Based | API-Based (This Tool) |
|--------|-----------|----------------------|
| Input | XML template files | Live NiFi API |
| Setup | Export templates manually | Direct API connection |
| Data freshness | Static snapshots | Real-time |
| Component IDs | Lost in export | Preserved |
| File I/O | Required | Not required |
| Dependencies | XML parsers | REST client only |

## Troubleshooting

### SSL Certificate Errors

If you get SSL certificate errors with self-signed certificates:

```python
config = NiFiConnectionConfig(
    host="localhost",
    verify_ssl=False
)
```

### Connection Timeout

For large flows, increase the timeout:

```python
config = NiFiConnectionConfig(
    host="localhost",
    timeout=120  # 2 minutes
)
```

### Authentication Failures

1. Verify credentials are correct
2. Check if NiFi requires specific auth method
3. Ensure user has read permissions on process groups

## License

MIT

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request
