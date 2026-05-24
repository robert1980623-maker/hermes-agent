"""Health check endpoint for daemon-agent.

Provides /healthz endpoint that checks:
- Token validity (HERMES_TOKEN environment variable)
- Portal connection (connectivity to portal service)
- Disk space (available disk space)
"""

import os
import shutil
from typing import Any

import requests


# Configuration
PORTAL_URL = os.environ.get("PORTAL_URL", "http://localhost:8080/health")
DISK_SPACE_THRESHOLD_PERCENT = 10  # Minimum 10% free disk space
DISK_SPACE_THRESHOLD_ABSOLUTE = 1024 * 1024 * 1024  # Minimum 1GB free


def check_token_validity() -> bool:
    """Check if HERMES_TOKEN is set and non-empty.
    
    Returns:
        True if HERMES_TOKEN exists and is non-empty, False otherwise.
    """
    token = os.environ.get("HERMES_TOKEN", "")
    return bool(token and token.strip())


def check_portal_connection() -> bool:
    """Check if the portal is reachable and responding.
    
    Returns:
        True if portal responds with status 200, False otherwise.
    """
    try:
        response = requests.get(PORTAL_URL, timeout=5)
        return response.status_code == 200
    except (requests.ConnectionError, requests.Timeout, requests.RequestException):
        return False


def check_disk_space(path: str = "/") -> bool:
    """Check if there's sufficient disk space available.
    
    Args:
        path: Path to check disk space for (default: root filesystem)
        
    Returns:
        True if disk space is above threshold, False otherwise.
    """
    try:
        usage = shutil.disk_usage(path)
        free_gb = usage.free / (1024 ** 3)
        free_percent = (usage.free / usage.total) * 100
        
        # Fail if either below percentage threshold or absolute threshold
        if free_percent < DISK_SPACE_THRESHOLD_PERCENT:
            return False
        if usage.free < DISK_SPACE_THRESHOLD_ABSOLUTE:
            return False
        return True
    except (OSError, PermissionError):
        # If we can't check disk space, assume it's OK
        return True


async def check_health() -> dict[str, Any]:
    """Run all health checks and return aggregated result.
    
    Returns:
        Dictionary with:
        - status: "healthy" or "unhealthy"
        - checks: dict of individual check results ("pass" or "fail")
    """
    token_ok = check_token_validity()
    portal_ok = check_portal_connection()
    disk_ok = check_disk_space()
    
    all_ok = token_ok and portal_ok and disk_ok
    
    return {
        "status": "healthy" if all_ok else "unhealthy",
        "checks": {
            "token_validity": "pass" if token_ok else "fail",
            "portal_connection": "pass" if portal_ok else "fail",
            "disk_space": "pass" if disk_ok else "fail",
        }
    }


# Expose FastAPI app for uvicorn if available
try:
    from fastapi import FastAPI
    import uvicorn
    
    app = FastAPI(title="daemon-agent health check")
    
    @app.get("/healthz")
    async def healthz():
        """Health check endpoint."""
        return await check_health()
    
    def run_server(host: str = "0.0.0.0", port: int = 8080):
        """Run the health check server."""
        uvicorn.run(app, host=host, port=port)
        
except ImportError:
    # FastAPI/uvicorn not available, provide standalone server mode
    import json
    from http.server import HTTPServer, BaseHTTPRequestHandler
    
    class HealthCheckHandler(BaseHTTPRequestHandler):
        """Simple HTTP handler for health check endpoint."""
        
        def do_GET(self):
            """Handle GET requests to /healthz."""
            import asyncio
            
            if self.path == "/healthz":
                # Run health check synchronously for simple HTTP server
                result = asyncio.run(check_health())
                
                self.send_response(200 if result["status"] == "healthy" else 503)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            else:
                self.send_response(404)
                self.end_headers()
        
        def log_message(self, format, *args):
            """Suppress log messages."""
            pass
    
    def run_server(host: str = "0.0.0.0", port: int = 8080):
        """Run the health check server using stdlib http.server."""
        server = HTTPServer((host, port), HealthCheckHandler)
        print(f"Health check server running on {host}:{port}")
        server.serve_forever()


if __name__ == "__main__":
    run_server()
