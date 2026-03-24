"""Tests for authentication system."""

import pytest
from datetime import datetime, timedelta, timezone

from backend.api.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_token,
    JWT_ALGORITHM,
)
from backend.config import settings
from jose import jwt


class TestJWTHandler:
    def test_create_access_token(self):
        token = create_access_token("test-user-id")
        assert isinstance(token, str)
        payload = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
        assert payload["sub"] == "test-user-id"
        assert payload["type"] == "access"
        assert "jti" in payload
        assert "exp" in payload

    def test_create_refresh_token(self):
        token, jti = create_refresh_token("test-user-id")
        assert isinstance(token, str)
        assert isinstance(jti, str)
        payload = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
        assert payload["sub"] == "test-user-id"
        assert payload["type"] == "refresh"
        assert payload["jti"] == jti

    def test_verify_valid_token(self):
        token = create_access_token("test-user-id")
        payload = verify_token(token)
        assert payload["sub"] == "test-user-id"

    def test_verify_expired_token(self):
        """Expired tokens should raise 401."""
        payload = {
            "sub": "test-user-id",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=9),
            "jti": "test-jti",
            "type": "access",
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)
        with pytest.raises(Exception) as exc_info:
            verify_token(token)
        assert exc_info.value.status_code == 401

    def test_verify_invalid_signature(self):
        """Tokens signed with wrong key should raise 401."""
        payload = {
            "sub": "test-user-id",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "access",
        }
        token = jwt.encode(payload, "wrong-secret-key", algorithm=JWT_ALGORITHM)
        with pytest.raises(Exception) as exc_info:
            verify_token(token)
        assert exc_info.value.status_code == 401

    def test_verify_token_missing_subject(self):
        """Tokens without sub claim should raise 401."""
        payload = {
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "access",
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)
        with pytest.raises(Exception) as exc_info:
            verify_token(token)
        assert exc_info.value.status_code == 401

    def test_access_token_expiry_is_8_hours(self):
        token = create_access_token("test-user-id")
        payload = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        diff = exp - iat
        assert abs(diff.total_seconds() - 480 * 60) < 5  # Within 5 seconds

    def test_refresh_token_expiry_is_30_days(self):
        token, _ = create_refresh_token("test-user-id")
        payload = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        diff = exp - iat
        assert abs(diff.total_seconds() - 30 * 86400) < 5


class TestPasswordValidation:
    def test_valid_password(self):
        from backend.scripts.create_user import validate_password
        errors = validate_password("MyStr0ng!Pass")
        assert errors == []

    def test_short_password(self):
        from backend.scripts.create_user import validate_password
        errors = validate_password("Sh0rt!")
        assert "at least 12 characters" in errors

    def test_no_uppercase(self):
        from backend.scripts.create_user import validate_password
        errors = validate_password("alllowercase1!")
        assert "one uppercase letter" in errors

    def test_no_number(self):
        from backend.scripts.create_user import validate_password
        errors = validate_password("NoNumbersHere!")
        assert "one number" in errors

    def test_no_symbol(self):
        from backend.scripts.create_user import validate_password
        errors = validate_password("NoSymbolsHere1")
        assert any("symbol" in e for e in errors)
