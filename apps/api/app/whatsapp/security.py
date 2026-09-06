import hashlib
import hmac


def verify_signature(*, payload: bytes, signature_header: str | None, app_secret: str) -> bool:
    """Verifies Meta's `X-Hub-Signature-256` header over the raw request
    body. Must run against the exact bytes received — re-serializing the
    parsed JSON would produce a different signature."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)
