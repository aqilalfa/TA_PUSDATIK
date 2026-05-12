"""
Local Authenticator Fallback using Bcrypt directly
"""
import bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hashed version"""
    # bcrypt requires bytes
    password_byte_enc = plain_password.encode('utf-8')
    hashed_password_byte_enc = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_byte_enc, hashed_password_byte_enc)

def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash for a given password"""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password=pwd_bytes, salt=salt)
    return hashed_password.decode('utf-8')
