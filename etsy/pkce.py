import base64
import hashlib
import secrets

def generate_code_verifier(length: int = 64) -> str:
    # URL-safe random string
    return secrets.token_urlsafe(length)[:length]

def generate_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

def generate_state() -> str:
    return secrets.token_urlsafe(32)
