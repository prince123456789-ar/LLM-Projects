import base64
import hashlib

from cryptography.fernet import Fernet


def fernet_from_secret(secret: str) -> Fernet:
    """
    Derive a stable Fernet key from the app SECRET_KEY.

    This avoids adding another required env var while still ensuring we never store
    publishable tokens in plaintext at rest.
    """
    digest = hashlib.sha256((secret or "").encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)

