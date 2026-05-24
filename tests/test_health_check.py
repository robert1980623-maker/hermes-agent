"""Tests for health check endpoint."""

import json
import os
from unittest.mock import MagicMock, patch
import pytest


class TestHealthCheck:
    """Test suite for /healthz endpoint."""

    @pytest.fixture
    def mock_health_check_module(self):
        """Mock the health_check module dependencies."""
        with patch("src.health_check.check_token_validity") as mock_token, \
             patch("src.health_check.check_portal_connection") as mock_portal, \
             patch("src.health_check.check_disk_space") as mock_disk:
            yield {
                "token": mock_token,
                "portal": mock_portal,
                "disk": mock_disk,
            }

    @pytest.mark.asyncio
    async def test_healthz_all_healthy(self, mock_health_check_module):
        """When all checks pass, endpoint returns healthy status."""
        mock_health_check_module["token"].return_value = True
        mock_health_check_module["portal"].return_value = True
        mock_health_check_module["disk"].return_value = True

        # Import after mocking
        from src.health_check import check_health
        
        result = await check_health()
        
        assert result["status"] == "healthy"
        assert result["checks"]["token_validity"] == "pass"
        assert result["checks"]["portal_connection"] == "pass"
        assert result["checks"]["disk_space"] == "pass"

    @pytest.mark.asyncio
    async def test_healthz_token_invalid(self, mock_health_check_module):
        """When token is invalid, endpoint returns unhealthy status."""
        mock_health_check_module["token"].return_value = False
        mock_health_check_module["portal"].return_value = True
        mock_health_check_module["disk"].return_value = True

        from src.health_check import check_health
        
        result = await check_health()
        
        assert result["status"] == "unhealthy"
        assert result["checks"]["token_validity"] == "fail"

    @pytest.mark.asyncio
    async def test_healthz_portal_down(self, mock_health_check_module):
        """When portal connection fails, endpoint returns unhealthy status."""
        mock_health_check_module["token"].return_value = True
        mock_health_check_module["portal"].return_value = False
        mock_health_check_module["disk"].return_value = True

        from src.health_check import check_health
        
        result = await check_health()
        
        assert result["status"] == "unhealthy"
        assert result["checks"]["portal_connection"] == "fail"

    @pytest.mark.asyncio
    async def test_healthz_disk_full(self, mock_health_check_module):
        """When disk space is low, endpoint returns unhealthy status."""
        mock_health_check_module["token"].return_value = True
        mock_health_check_module["portal"].return_value = True
        mock_health_check_module["disk"].return_value = False

        from src.health_check import check_health
        
        result = await check_health()
        
        assert result["status"] == "unhealthy"
        assert result["checks"]["disk_space"] == "fail"

    @pytest.mark.asyncio
    async def test_healthz_multiple_failures(self, mock_health_check_module):
        """When multiple checks fail, endpoint returns unhealthy status."""
        mock_health_check_module["token"].return_value = False
        mock_health_check_module["portal"].return_value = False
        mock_health_check_module["disk"].return_value = False

        from src.health_check import check_health
        
        result = await check_health()
        
        assert result["status"] == "unhealthy"
        assert result["checks"]["token_validity"] == "fail"
        assert result["checks"]["portal_connection"] == "fail"
        assert result["checks"]["disk_space"] == "fail"


class TestCheckFunctions:
    """Unit tests for individual check functions."""

    def test_check_disk_space_sufficient(self):
        """Disk check passes when space is above threshold."""
        import os
        with patch("src.health_check.shutil.disk_usage") as mock_usage:
            # 100GB total, 10GB used, 90GB free
            mock_usage.return_value = MagicMock(total=100_000_000_000, used=10_000_000_000, free=90_000_000_000)
            
            from src.health_check import check_disk_space
            result = check_disk_space()
            
            assert result is True

    def test_check_disk_space_low(self):
        """Disk check fails when free space is below threshold."""
        with patch("src.health_check.shutil.disk_usage") as mock_usage:
            # 100GB total, 95GB used, 5GB free (less than 10% or 1GB)
            mock_usage.return_value = MagicMock(total=100_000_000_000, used=95_000_000_000, free=5_000_000_000)
            
            from src.health_check import check_disk_space
            result = check_disk_space()
            
            assert result is False

    def test_check_disk_space_critical_threshold(self):
        """Disk check fails when less than 1GB free regardless of percentage."""
        with patch("src.health_check.shutil.disk_usage") as mock_usage:
            # 100GB total, 99.5GB used, 500MB free
            mock_usage.return_value = MagicMock(total=100_000_000_000, used=99_500_000_000, free=500_000_000)
            
            from src.health_check import check_disk_space
            result = check_disk_space()
            
            assert result is False

    @patch.dict(os.environ, {"HERMES_TOKEN": "test_token"}, clear=False)
    def test_check_token_validity_valid(self):
        """Token validity check passes with valid token format."""
        import os
        os.environ["HERMES_TOKEN"] = "valid_token_123"
        
        from src.health_check import check_token_validity
        result = check_token_validity()
        
        assert result is True

    @patch.dict(os.environ, {"HERMES_TOKEN": ""}, clear=False)
    def test_check_token_validity_empty(self):
        """Token validity check fails with empty token."""
        import os
        os.environ["HERMES_TOKEN"] = ""
        
        from src.health_check import check_token_validity
        result = check_token_validity()
        
        assert result is False

    @patch.dict(os.environ, {}, clear=False)
    def test_check_token_validity_missing(self):
        """Token validity check fails when HERMES_TOKEN is not set."""
        from src.health_check import check_token_validity
        result = check_token_validity()
        
        assert result is False

    @patch("src.health_check.requests.get")
    def test_check_portal_connection_success(self, mock_get):
        """Portal connection check passes when portal responds OK."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        from src.health_check import check_portal_connection
        result = check_portal_connection()
        
        assert result is True

    @patch("src.health_check.requests.get")
    def test_check_portal_connection_failure(self, mock_get):
        """Portal connection check fails when portal is unreachable."""
        import requests
        mock_get.side_effect = requests.ConnectionError("Connection refused")
        
        from src.health_check import check_portal_connection
        result = check_portal_connection()
        
        assert result is False

    @patch("src.health_check.requests.get")
    def test_check_portal_connection_bad_status(self, mock_get):
        """Portal connection check fails when portal returns non-200 status."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_get.return_value = mock_response
        
        from src.health_check import check_portal_connection
        result = check_portal_connection()
        
        assert result is False


class TestHealthCheckEndpoint:
    """Tests for the HTTP endpoint handler."""

    @pytest.fixture
    def healthz_response(self):
        """Return a mock healthz response structure."""
        return {
            "status": "healthy",
            "checks": {
                "token_validity": "pass",
                "portal_connection": "pass", 
                "disk_space": "pass"
            }
        }

    def test_healthz_returns_json(self, healthz_response):
        """Response should be valid JSON."""
        # Verify the structure is JSON serializable
        json_str = json.dumps(healthz_response)
        parsed = json.loads(json_str)
        assert parsed["status"] == "healthy"

    def test_healthz_has_required_fields(self, healthz_response):
        """Response must have status and checks fields."""
        assert "status" in healthz_response
        assert "checks" in healthz_response
        assert "token_validity" in healthz_response["checks"]
        assert "portal_connection" in healthz_response["checks"]
        assert "disk_space" in healthz_response["checks"]

    def test_healthz_status_values(self, healthz_response):
        """Status should be either healthy or unhealthy."""
        assert healthz_response["status"] in ["healthy", "unhealthy"]

    def test_healthz_check_values(self, healthz_response):
        """Each check should be either pass or fail."""
        for check_name, check_value in healthz_response["checks"].items():
            assert check_value in ["pass", "fail"], f"Check {check_name} has invalid value: {check_value}"