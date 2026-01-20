"""Databricks LLM client for local usage.

This module allows you to call Databricks Foundation Model APIs
or Model Serving endpoints from your local machine.
"""

import os
import requests
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class DatabricksLLMConfig:
    """Configuration for Databricks LLM API."""
    workspace_url: str  # e.g., "https://your-workspace.cloud.databricks.com"
    token: str  # Personal Access Token
    endpoint_name: Optional[str] = None  # For custom model serving endpoints
    model_name: Optional[str] = None  # For foundation models (e.g., "databricks-meta-llama-3-70b-instruct")
    timeout: int = 120


class DatabricksLLMClient:
    """Client for calling Databricks LLM endpoints locally."""

    def __init__(self, config: DatabricksLLMConfig):
        """Initialize the client.

        Args:
            config: Databricks LLM configuration
        """
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {config.token}",
            "Content-Type": "application/json"
        })

    def call_foundation_model(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
        **kwargs
    ) -> Dict[str, Any]:
        """Call a Databricks Foundation Model API.

        Args:
            prompt: The prompt to send to the model
            model_name: Model name (overrides config if provided)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters for the API

        Returns:
            Dict containing the model response

        Example models:
            - databricks-meta-llama-3-1-70b-instruct
            - databricks-meta-llama-3-1-405b-instruct
            - databricks-dbrx-instruct
            - databricks-mixtral-8x7b-instruct
        """
        model = model_name or self.config.model_name
        if not model:
            raise ValueError("model_name must be provided in config or as argument")

        # Foundation Model API endpoint
        url = f"{self.config.workspace_url}/serving-endpoints/{model}/invocations"

        payload = {
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }

        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            error_detail = e.response.text if hasattr(e.response, 'text') else str(e)
            raise Exception(f"API call failed: {error_detail}")

    def call_custom_endpoint(
        self,
        data: Dict[str, Any],
        endpoint_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Call a custom Model Serving endpoint.

        Args:
            data: Payload to send to the endpoint
            endpoint_name: Endpoint name (overrides config if provided)

        Returns:
            Dict containing the endpoint response
        """
        endpoint = endpoint_name or self.config.endpoint_name
        if not endpoint:
            raise ValueError("endpoint_name must be provided in config or as argument")

        url = f"{self.config.workspace_url}/serving-endpoints/{endpoint}/invocations"

        try:
            response = self.session.post(
                url,
                json=data,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            error_detail = e.response.text if hasattr(e.response, 'text') else str(e)
            raise Exception(f"API call failed: {error_detail}")

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model_name: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
        **kwargs
    ) -> Dict[str, Any]:
        """Call with chat messages format (for multi-turn conversations).

        Args:
            messages: List of message dicts with 'role' and 'content'
            model_name: Model name (overrides config if provided)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Dict containing the model response

        Example:
            messages = [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi! How can I help?"},
                {"role": "user", "content": "Tell me about NiFi"}
            ]
        """
        model = model_name or self.config.model_name
        if not model:
            raise ValueError("model_name must be provided in config or as argument")

        url = f"{self.config.workspace_url}/serving-endpoints/{model}/invocations"

        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }

        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            error_detail = e.response.text if hasattr(e.response, 'text') else str(e)
            raise Exception(f"API call failed: {error_detail}")

    def extract_text_response(self, response: Dict[str, Any]) -> str:
        """Extract text from API response.

        Args:
            response: Response dict from API call

        Returns:
            Extracted text content
        """
        # Handle Foundation Model API format
        if "choices" in response:
            return response["choices"][0]["message"]["content"]

        # Handle other formats
        if "predictions" in response:
            predictions = response["predictions"]
            if isinstance(predictions, list) and len(predictions) > 0:
                return str(predictions[0])
            return str(predictions)

        # Fallback - return full response as string
        return str(response)


def create_databricks_client_from_env() -> DatabricksLLMClient:
    """Create Databricks LLM client from environment variables.

    Environment variables:
        DATABRICKS_HOST: Workspace URL (required)
        DATABRICKS_TOKEN: Personal Access Token (required)
        DATABRICKS_MODEL_NAME: Default model name (optional)
        DATABRICKS_ENDPOINT_NAME: Default endpoint name (optional)

    Returns:
        Configured DatabricksLLMClient

    Raises:
        ValueError: If required environment variables are missing
    """
    workspace_url = os.getenv("DATABRICKS_HOST")
    token = os.getenv("DATABRICKS_TOKEN")

    if not workspace_url:
        raise ValueError("DATABRICKS_HOST environment variable is required")
    if not token:
        raise ValueError("DATABRICKS_TOKEN environment variable is required")

    config = DatabricksLLMConfig(
        workspace_url=workspace_url,
        token=token,
        model_name=os.getenv("DATABRICKS_MODEL_NAME"),
        endpoint_name=os.getenv("DATABRICKS_ENDPOINT_NAME")
    )

    return DatabricksLLMClient(config)


# Example usage
if __name__ == "__main__":
    # Example 1: Using environment variables
    # export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
    # export DATABRICKS_TOKEN="dapi..."
    # export DATABRICKS_MODEL_NAME="databricks-meta-llama-3-1-70b-instruct"

    try:
        client = create_databricks_client_from_env()

        # Simple prompt
        response = client.call_foundation_model(
            prompt="Explain what Apache NiFi is in one sentence.",
            temperature=0.1,
            max_tokens=100
        )

        text = client.extract_text_response(response)
        print(f"Response: {text}")

    except Exception as e:
        print(f"Error: {e}")

    # Example 2: Direct configuration
    config = DatabricksLLMConfig(
        workspace_url="https://your-workspace.cloud.databricks.com",
        token="dapi...",
        model_name="databricks-meta-llama-3-1-70b-instruct"
    )

    client = DatabricksLLMClient(config)

    # Multi-turn conversation
    messages = [
        {"role": "system", "content": "You are a helpful assistant for NiFi analysis."},
        {"role": "user", "content": "What is a processor in NiFi?"}
    ]

    response = client.chat_completion(messages)
    print(client.extract_text_response(response))
