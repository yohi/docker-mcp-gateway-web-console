"""Authentication models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class AuthMethod(str, Enum):
    """Authentication method enum."""
    API_KEY = "api_key"
    MASTER_PASSWORD = "master_password"


class LoginRequest(BaseModel):
    """Login request model."""
    method: AuthMethod
    email: EmailStr
    api_key: Optional[str] = None
    master_password: Optional[str] = None
    
    def validate_credentials(self) -> None:
        """Validate that appropriate credentials are provided for the method."""
        if self.method == AuthMethod.API_KEY and not self.api_key:
            raise ValueError("API key is required for api_key authentication method")
        if self.method == AuthMethod.MASTER_PASSWORD and not self.master_password:
            raise ValueError("Master password is required for master_password authentication method")


class LoginResponse(BaseModel):
    """Login response model."""
    session_id: str
    expires_at: datetime


class LogoutResponse(BaseModel):
    """Logout response model."""
    success: bool
    message: str = "Successfully logged out"


class SessionValidationResponse(BaseModel):
    """Session validation response model."""
    valid: bool
    expires_at: Optional[datetime] = None


class Session(BaseModel):
    """Session model for internal use."""
    session_id: str
    user_email: str
    bw_session_key: str
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
