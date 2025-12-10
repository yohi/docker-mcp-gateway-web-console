"""署名検証で利用するモデルと例外。"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SignatureVerificationError(Exception):
    """署名検証失敗を表す例外。"""

    def __init__(
        self, *, error_code: str, message: str, remediation: Optional[str] = None
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.remediation = remediation


class PermitUnsignedEntry(BaseModel):
    """署名検証をスキップする例外条件。"""

    type: Literal["none", "any", "sha256", "thumbprint", "image"]
    digest: Optional[str] = Field(default=None, description="sha256 ダイジェスト")
    cert: Optional[str] = Field(default=None, description="証明書サムプリント")
    name: Optional[str] = Field(default=None, description="許可するイメージ名")


class SignaturePolicy(BaseModel):
    """署名検証ポリシー。"""

    verify_signatures: bool = Field(default=True, description="署名検証を実施するか")
    mode: Literal["enforcement", "audit-only"] = Field(
        default="enforcement", description="失敗時のモード"
    )
    permit_unsigned: List[PermitUnsignedEntry] = Field(
        default_factory=list, description="検証をスキップする例外リスト"
    )
    allowed_algorithms: List[str] = Field(
        default_factory=list, description="許可する署名アルゴリズム"
    )
    jwks_url: Optional[str] = Field(
        default=None, description="公開鍵取得用の JWKS URL（任意）"
    )
