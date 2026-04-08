from __future__ import annotations

import os

from app.config import Settings


def test_settings_default_to_dind_tls_host() -> None:
    original_host = os.environ.get("DOCKER_HOST")
    try:
        os.environ["DOCKER_HOST"] = "tcp://dind:2376"
        settings = Settings(
            DOCKER_TLS_VERIFY="1",
            DOCKER_CERT_PATH="/certs/client",
        )
    finally:
        if original_host is None:
            os.environ.pop("DOCKER_HOST", None)
        else:
            os.environ["DOCKER_HOST"] = original_host

    assert settings.docker_host == "tcp://dind:2376"
    assert settings.docker_tls_verify is True
    assert settings.docker_ca_cert == "/certs/client/ca.pem"
    assert settings.docker_client_cert == "/certs/client/cert.pem"
    assert settings.docker_client_key == "/certs/client/key.pem"
