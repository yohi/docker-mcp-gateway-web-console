"""署名検証サービスのインターフェースとデフォルト実装。"""

from app.models.signature import SignaturePolicy, SignatureVerificationError


class SignatureVerifier:
    """署名検証を行うためのインターフェース。"""

    async def verify_image(
        self, *, image: str, policy: SignaturePolicy, correlation_id: str
    ) -> None:
        """イメージの署名を検証する。"""
        raise NotImplementedError


class NoopSignatureVerifier(SignatureVerifier):
    """検証を行わないスタブ実装。"""

    async def verify_image(
        self, *, image: str, policy: SignaturePolicy, correlation_id: str
    ) -> None:
        return None
