"""NiFi REST API client for fetching flow data from live NiFi instances.

This module provides a robust client for interacting with Apache NiFi REST API,
supporting multiple authentication methods and automatic retry logic.
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import backoff
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class AuthType(Enum):
    """Supported authentication types for NiFi API."""
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    CERTIFICATE = "certificate"


@dataclass
class NiFiConnectionConfig:
    """Configuration for NiFi API connection.

    Attributes:
        host: NiFi host (e.g., 'localhost', 'nifi.example.com')
        port: NiFi port (default: 8080)
        protocol: Connection protocol ('http' or 'https')
        auth_type: Authentication type (none, basic, bearer, certificate)
        username: Username for basic auth
        password: Password for basic auth
        token: Bearer token for token auth
        cert_path: Path to client certificate for mTLS
        key_path: Path to client private key for mTLS
        verify_ssl: Whether to verify SSL certificates
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
    """
    host: str
    port: int = 8080
    protocol: str = "https"
    auth_type: AuthType = AuthType.NONE
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    cert_path: Optional[str] = None
    key_path: Optional[str] = None
    verify_ssl: bool = True
    timeout: int = 30
    max_retries: int = 3

    @property
    def base_url(self) -> str:
        """Get the base URL for NiFi API."""
        return f"{self.protocol}://{self.host}:{self.port}/nifi-api"

    def validate(self) -> None:
        """Validate configuration parameters.

        Raises:
            ValueError: If configuration is invalid
        """
        if not self.host:
            raise ValueError("Host is required")

        if self.port < 1 or self.port > 65535:
            raise ValueError(f"Invalid port: {self.port}")

        if self.protocol not in ("http", "https"):
            raise ValueError(f"Protocol must be 'http' or 'https', got: {self.protocol}")

        if self.auth_type == AuthType.BASIC:
            if not self.username or not self.password:
                raise ValueError("Username and password required for basic auth")

        elif self.auth_type == AuthType.BEARER:
            if not self.token:
                raise ValueError("Token required for bearer auth")

        elif self.auth_type == AuthType.CERTIFICATE:
            if not self.cert_path or not self.key_path:
                raise ValueError("Certificate and key paths required for certificate auth")
            if not Path(self.cert_path).exists():
                raise ValueError(f"Certificate file not found: {self.cert_path}")
            if not Path(self.key_path).exists():
                raise ValueError(f"Key file not found: {self.key_path}")

        if self.timeout < 1 or self.timeout > 600:
            raise ValueError(f"Timeout must be between 1 and 600 seconds, got: {self.timeout}")

        if self.max_retries < 0 or self.max_retries > 10:
            raise ValueError(f"Max retries must be between 0 and 10, got: {self.max_retries}")


class NiFiClient:
    """Client for interacting with NiFi REST API.

    This client handles:
    - Multiple authentication methods (none, basic, bearer, certificate)
    - Automatic retries with exponential backoff
    - Session management and connection pooling
    - Proper error handling and logging
    """

    def __init__(self, config: NiFiConnectionConfig):
        """Initialize NiFi client.

        Args:
            config: Connection configuration

        Raises:
            ValueError: If configuration is invalid
        """
        config.validate()
        self.config = config
        self.session = self._create_session()
        logger.info(f"NiFi client initialized for {config.base_url}")

    def _create_session(self) -> requests.Session:
        """Create configured requests session with retry logic.

        Returns:
            Configured session object
        """
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=2,  # 2s, 4s, 8s delays
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD", "OPTIONS"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Configure authentication
        if self.config.auth_type == AuthType.BASIC:
            session.auth = (self.config.username, self.config.password)

        elif self.config.auth_type == AuthType.BEARER:
            session.headers.update({
                "Authorization": f"Bearer {self.config.token}"
            })

        elif self.config.auth_type == AuthType.CERTIFICATE:
            session.cert = (self.config.cert_path, self.config.key_path)

        # Configure SSL verification
        session.verify = self.config.verify_ssl

        return session

    @backoff.on_exception(
        backoff.expo,
        (requests.exceptions.Timeout, requests.exceptions.ConnectionError),
        max_tries=3,
        max_time=60
    )
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to NiFi instance.

        Returns:
            Dict containing connection test results with keys:
                - success: bool indicating if connection succeeded
                - version: NiFi version string (if successful)
                - error: Error message (if failed)

        Raises:
            requests.RequestException: If connection fails after retries
        """
        try:
            logger.info(f"Testing connection to {self.config.base_url}")
            response = self.session.get(
                f"{self.config.base_url}/flow/about",
                timeout=self.config.timeout
            )
            response.raise_for_status()

            about_data = response.json()
            version = about_data.get("about", {}).get("version", "unknown")

            logger.info(f"Successfully connected to NiFi {version}")
            return {
                "success": True,
                "version": version,
                "message": f"Connected to NiFi {version}"
            }

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
            logger.error(f"Connection test failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "status_code": e.response.status_code
            }

        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            logger.error(f"Connection test failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }

        except requests.exceptions.Timeout as e:
            error_msg = f"Connection timeout after {self.config.timeout}s"
            logger.error(f"Connection test failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Connection test failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }

    @backoff.on_exception(
        backoff.expo,
        (requests.exceptions.Timeout, requests.exceptions.ConnectionError),
        max_tries=3,
        max_time=300  # 5 minutes max for large flows
    )
    def fetch_flow(self, process_group_id: str = "root") -> Dict[str, Any]:
        """Fetch flow data from NiFi for a specific process group.

        This method uses the /process-groups/{id}/download endpoint which
        preserves component IDs from the live system (unlike template exports).

        Args:
            process_group_id: Process group ID to fetch (default: "root")

        Returns:
            Dict containing the flow data in NiFi JSON format

        Raises:
            ValueError: If process_group_id is invalid
            requests.RequestException: If fetch fails after retries
        """
        if not process_group_id:
            raise ValueError("Process group ID is required")

        # Use 'root' for the root process group
        endpoint = f"{self.config.base_url}/process-groups/{process_group_id}/download"

        try:
            logger.info(f"Fetching flow for process group: {process_group_id}")
            response = self.session.get(
                endpoint,
                timeout=self.config.timeout
            )
            response.raise_for_status()

            flow_data = response.json()
            logger.info(f"Successfully fetched flow for process group: {process_group_id}")

            return flow_data

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                error_msg = f"Process group not found: {process_group_id}"
                logger.error(error_msg)
                raise ValueError(error_msg) from e
            elif e.response.status_code == 403:
                error_msg = f"Access denied to process group: {process_group_id}"
                logger.error(error_msg)
                raise PermissionError(error_msg) from e
            else:
                error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
                logger.error(f"Failed to fetch flow: {error_msg}")
                raise

        except requests.exceptions.Timeout as e:
            error_msg = f"Fetch timeout after {self.config.timeout}s. Try increasing timeout for large flows."
            logger.error(error_msg)
            raise TimeoutError(error_msg) from e

        except Exception as e:
            logger.error(f"Failed to fetch flow: {str(e)}")
            raise

    def get_process_groups(self, parent_id: str = "root") -> Dict[str, Any]:
        """Get list of process groups under a parent process group.

        Args:
            parent_id: Parent process group ID (default: "root")

        Returns:
            Dict containing process group information

        Raises:
            requests.RequestException: If request fails
        """
        endpoint = f"{self.config.base_url}/process-groups/{parent_id}/process-groups"

        try:
            logger.info(f"Fetching process groups for parent: {parent_id}")
            response = self.session.get(
                endpoint,
                timeout=self.config.timeout
            )
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(f"Failed to fetch process groups: {str(e)}")
            raise

    def close(self) -> None:
        """Close the session and cleanup resources."""
        if self.session:
            self.session.close()
            logger.info("NiFi client session closed")


def create_nifi_client_from_env() -> NiFiClient:
    """Create NiFi client from environment variables.

    Environment variables:
        NIFI_HOST: NiFi host (required)
        NIFI_PORT: NiFi port (default: 8080)
        NIFI_PROTOCOL: Protocol http/https (default: https)
        NIFI_AUTH_TYPE: Auth type none/basic/bearer/certificate (default: none)
        NIFI_USERNAME: Username for basic auth
        NIFI_PASSWORD: Password for basic auth
        NIFI_TOKEN: Bearer token
        NIFI_CERT_PATH: Client certificate path
        NIFI_KEY_PATH: Client key path
        NIFI_VERIFY_SSL: Verify SSL (default: true)
        NIFI_TIMEOUT: Request timeout in seconds (default: 30)
        NIFI_MAX_RETRIES: Max retry attempts (default: 3)

    Returns:
        Configured NiFi client

    Raises:
        ValueError: If required environment variables are missing
    """
    host = os.getenv("NIFI_HOST")
    if not host:
        raise ValueError("NIFI_HOST environment variable is required")

    auth_type_str = os.getenv("NIFI_AUTH_TYPE", "none").lower()
    try:
        auth_type = AuthType(auth_type_str)
    except ValueError:
        raise ValueError(f"Invalid auth type: {auth_type_str}")

    config = NiFiConnectionConfig(
        host=host,
        port=int(os.getenv("NIFI_PORT", "8080")),
        protocol=os.getenv("NIFI_PROTOCOL", "https"),
        auth_type=auth_type,
        username=os.getenv("NIFI_USERNAME"),
        password=os.getenv("NIFI_PASSWORD"),
        token=os.getenv("NIFI_TOKEN"),
        cert_path=os.getenv("NIFI_CERT_PATH"),
        key_path=os.getenv("NIFI_KEY_PATH"),
        verify_ssl=os.getenv("NIFI_VERIFY_SSL", "true").lower() == "true",
        timeout=int(os.getenv("NIFI_TIMEOUT", "30")),
        max_retries=int(os.getenv("NIFI_MAX_RETRIES", "3"))
    )

    return NiFiClient(config)
