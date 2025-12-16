import base64
from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings
from app.services.oauth import OAuthService
from app.services.state_store import StateStore


@pytest.mark.asyncio
async def test_oauth_service_encrypts_tokens_with_aes_gcm(monkeypatch, tmp_path):
    """AES-256-GCM でトークンを暗号化・復号できること。"""
    aes_key = AESGCM.generate_key(bit_length=256)
    aes_key_b64 = base64.urlsafe_b64encode(aes_key).decode()

    # Fernet キーは未設定扱いにし、AES-GCM キーを優先する。
    monkeypatch.setattr(settings, "oauth_token_encryption_key", "placeholder")
    monkeypatch.setattr(settings, "credential_encryption_key", aes_key_b64)

    store = StateStore(str(tmp_path / "state.db"))
    store.init_schema()

    service = OAuthService(state_store=store)

    expires_at = datetime.now(timezone.utc)
    token_ref = service._encrypt_tokens(  # noqa: SLF001
        access_token="access-token",
        refresh_token="refresh-token",
        scopes=["scope1"],
        expires_at=expires_at,
    )

    assert token_ref["algo"] == "aes-gcm"
    assert "blob" in token_ref and "nonce" in token_ref

    payload = service._decrypt_token_ref(token_ref)  # noqa: SLF001
    assert payload["access_token"] == "access-token"
    assert payload["refresh_token"] == "refresh-token"
    assert payload["scope"] == ["scope1"]
