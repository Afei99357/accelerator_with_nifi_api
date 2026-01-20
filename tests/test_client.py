"""Basic tests for NiFi client."""

import pytest
from nifi_client.client import NiFiConnectionConfig, AuthType


def test_connection_config_validation():
    """Test that connection config validates properly."""
    # Valid config
    config = NiFiConnectionConfig(
        host="localhost",
        port=8080,
        protocol="https",
        auth_type=AuthType.NONE
    )
    config.validate()  # Should not raise

    # Invalid port
    with pytest.raises(ValueError):
        bad_config = NiFiConnectionConfig(host="localhost", port=99999)
        bad_config.validate()

    # Invalid protocol
    with pytest.raises(ValueError):
        bad_config = NiFiConnectionConfig(host="localhost", protocol="ftp")
        bad_config.validate()


def test_connection_config_base_url():
    """Test that base URL is constructed correctly."""
    config = NiFiConnectionConfig(
        host="example.com",
        port=9090,
        protocol="https"
    )
    assert config.base_url == "https://example.com:9090/nifi-api"


def test_basic_auth_validation():
    """Test that basic auth requires username and password."""
    with pytest.raises(ValueError):
        config = NiFiConnectionConfig(
            host="localhost",
            auth_type=AuthType.BASIC,
            username="admin"
            # Missing password
        )
        config.validate()


def test_bearer_auth_validation():
    """Test that bearer auth requires token."""
    with pytest.raises(ValueError):
        config = NiFiConnectionConfig(
            host="localhost",
            auth_type=AuthType.BEARER
            # Missing token
        )
        config.validate()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
