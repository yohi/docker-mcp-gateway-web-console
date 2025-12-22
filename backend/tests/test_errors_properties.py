
import pytest
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient
from hypothesis import given, settings, HealthCheck, strategies as st
from app.main import (
    auth_error_handler,
    catalog_error_handler,
    config_error_handler,
    container_error_handler,
    inspector_error_handler,
    secret_error_handler,
    general_exception_handler,
)
from app.services.auth import AuthError
from app.services.catalog import CatalogError
from app.services.config import ConfigError
from app.services.containers import ContainerError
from app.services.inspector import InspectorError
from app.services.secrets import SecretError
import logging

# Setup a test app with the same exception handlers
def create_test_app():
    app = FastAPI()
    
    app.add_exception_handler(AuthError, auth_error_handler)
    app.add_exception_handler(CatalogError, catalog_error_handler)
    app.add_exception_handler(ConfigError, config_error_handler)
    app.add_exception_handler(ContainerError, container_error_handler)
    app.add_exception_handler(InspectorError, inspector_error_handler)
    app.add_exception_handler(SecretError, secret_error_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    return app

error_test_app = create_test_app()
client = TestClient(error_test_app, raise_server_exceptions=False)

# Helper route to trigger exceptions
@error_test_app.get("/raise/{error_type}")
def raise_error(error_type: str, message: str = "Test error"):
    if error_type == "AuthError":
        raise AuthError(message)
    elif error_type == "CatalogError":
        raise CatalogError(message)
    elif error_type == "ConfigError":
        raise ConfigError(message)
    elif error_type == "ContainerError":
        raise ContainerError(message)
    elif error_type == "InspectorError":
        raise InspectorError(message)
    elif error_type == "SecretError":
        raise SecretError(message)
    elif error_type == "Exception":
        raise Exception(message)
    return {"status": "ok"}

class TestErrorProperties:
    """
    Property-based tests for error handling.
    Covers Requirements: 10.1, 10.2, 10.5
    """

    @given(st.text(min_size=1))
    def test_property_34_error_message_display_auth(self, message):
        """
        Property 34: Error message display (Req 10.1)
        Test that AuthError results in a structured error response.
        """
        response = client.get(f"/raise/AuthError", params={"message": message})
        assert response.status_code == 401
        data = response.json()
        assert "error_code" in data
        assert data["error_code"] == "AUTH_ERROR"
        assert "message" in data
        assert data["message"] == message
        assert "detail" in data
        # Req 10.2: Content should be helpful
        assert len(data["detail"]) > 0

    @given(st.text(min_size=1))
    def test_property_34_error_message_display_catalog(self, message):
        """
        Property 34: Error message display (Req 10.1)
        Test that CatalogError results in a structured error response.
        """
        response = client.get(f"/raise/CatalogError", params={"message": message})
        assert response.status_code == 503
        data = response.json()
        assert data["error_code"] == "CATALOG_ERROR"
        assert data["message"] == message
        assert len(data["detail"]) > 0

    @given(st.text(min_size=1))
    def test_property_34_error_message_display_config(self, message):
        """
        Property 34: Error message display (Req 10.1)
        Test that ConfigError results in a structured error response.
        """
        response = client.get(f"/raise/ConfigError", params={"message": message})
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "CONFIG_ERROR"
        assert data["message"] == message
        assert len(data["detail"]) > 0

    @given(st.text(min_size=1))
    def test_property_34_error_message_display_container(self, message):
        """
        Property 34: Error message display (Req 10.1)
        Test that ContainerError results in a structured error response.
        """
        response = client.get(f"/raise/ContainerError", params={"message": message})
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "CONTAINER_ERROR"
        assert data["message"] == message
        assert len(data["detail"]) > 0

    @given(st.text(min_size=1))
    def test_property_34_error_message_display_inspector(self, message):
        """
        Property 34: Error message display (Req 10.1)
        Test that InspectorError results in a structured error response.
        """
        response = client.get(f"/raise/InspectorError", params={"message": message})
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "INSPECTOR_ERROR"
        assert data["message"] == message
        assert len(data["detail"]) > 0

    @given(st.text(min_size=1))
    def test_property_34_error_message_display_secret(self, message):
        """
        Property 34: Error message display (Req 10.1)
        Test that SecretError results in a structured error response.
        """
        response = client.get(f"/raise/SecretError", params={"message": message})
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "SECRET_ERROR"
        assert data["message"] == message
        assert len(data["detail"]) > 0

    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(st.text(min_size=1))
    def test_property_36_fatal_error_logging(self, caplog, message):
        caplog.clear()
        """
        Property 36: Fatal error logging (Req 10.5)
        Test that generic Exceptions result in 500 and are logged.
        """
        # We verify that it logs at ERROR level
        with caplog.at_level(logging.ERROR):
            response = client.get(f"/raise/Exception", params={"message": message})
            
        assert response.status_code == 500
        data = response.json()
        assert data["error_code"] == "INTERNAL_ERROR"
        # The user should NOT see the raw exception message for security/usability in 500s
        # according to typical best practices, but Requirement 10.5 says:
        # "display a concise message to the user" and "log detailed error"
        assert data["message"] == "An unexpected error occurred"
        
        # Check logs
        assert len(caplog.records) > 0
        # Search for the message in logs
        found = False
        for record in caplog.records:
            if message in str(record.exc_info) or message in record.message:
                found = True
                break
        
        # Note: In main.py, it logs `exc` which is the exception object.
        # formatting `exc` usually gives the message.
        assert found, "Fatal error should be logged with details"
