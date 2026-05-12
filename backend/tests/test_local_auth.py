import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.auth.local_authenticator import verify_password, get_password_hash

def test_password_hashing():
    """Test that a password can be hashed and then successfully verified"""
    password = "supersecretpassword"
    
    # Hash password
    hashed = get_password_hash(password)
    assert hashed != password
    assert isinstance(hashed, str)
    
    # Verify correct password
    assert verify_password(password, hashed) is True
    
    # Verify incorrect password
    assert verify_password("wrongpassword", hashed) is False
