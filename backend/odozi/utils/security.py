import hmac
import hashlib
import time
from django.conf import settings

MAX_SKEW = 60  # seconds

def verify_signature(timestamp: str, payload: str, signature: str) -> bool:
    try:
        ts = int(timestamp)
    except:
        return False

    # prevent replay attacks
    if abs(time.time() - ts) > MAX_SKEW:
        return False

    msg = f"{timestamp}.{payload}".encode()

    expected = hmac.new(
        settings.ODOZI_WEBHOOK_SECRET.encode(),
        msg,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)