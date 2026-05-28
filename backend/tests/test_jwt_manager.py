import sys
import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.auth.jwt_manager import jwt_manager


def _b64url_json(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

def test_create_and_verify_access_token():
    """Test standard access token creation and verification"""
    data = {"sub": "admin@bssn.go.id", "roles": ["admin_pusdatik"]}
    token = jwt_manager.create_access_token(data)
    
    assert token is not None
    assert isinstance(token, str)
    
    # Verify
    payload = jwt_manager.verify_token(token)
    assert payload is not None
    assert payload["sub"] == "admin@bssn.go.id"
    assert payload["roles"] == ["admin_pusdatik"]
    assert "exp" in payload
    assert "jti" in payload
    assert payload["type"] == "access"

def test_expired_token():
    """Test that an expired token is rejected"""
    data = {"sub": "test"}
    # Create token that expires immediately
    token = jwt_manager.create_access_token(data, expires_delta=timedelta(seconds=-1))
    
    # Verification should return None for expired tokens
    payload = jwt_manager.verify_token(token)
    assert payload is None


def test_alg_none_token_is_rejected():
    """OWASP: JWT header algorithm manipulation must be rejected"""
    header = {"alg": "none", "typ": "JWT"}
    payload = {
        "sub": "admin@bssn.go.id",
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "jti": "forged-jti",
        "type": "access",
        "roles": ["admin_pusdatik"],
    }
    unsigned_token = f"{_b64url_json(header)}.{_b64url_json(payload)}."

    assert jwt_manager.verify_token(unsigned_token) is None


def test_tampered_payload_token_is_rejected():
    """OWASP: modifying signed token payload must invalidate the signature"""
    token = jwt_manager.create_access_token({"sub": "admin@bssn.go.id", "roles": ["viewer"]})
    header, _payload, signature = token.split(".")
    forged_payload = {
        "sub": "attacker@bssn.go.id",
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "jti": "forged-jti",
        "type": "access",
        "roles": ["admin_pusdatik"],
    }
    tampered_token = f"{header}.{_b64url_json(forged_payload)}.{signature}"

    assert jwt_manager.verify_token(tampered_token) is None


def test_malformed_token_is_rejected():
    """Malformed JWT input must fail closed"""
    assert jwt_manager.verify_token("not-a-valid-jwt") is None


def test_token_missing_required_claims_is_rejected():
    """Tokens missing required identity/lifecycle claims must be rejected"""
    token = jwt_manager.create_access_token({"roles": ["admin_pusdatik"]})

    assert jwt_manager.verify_token(token) is None
