"""Short-lived signed QR tokens for visitor admission and departure."""

import base64
from io import BytesIO

import qrcode
from django.core import signing

VISITOR_QR_SALT = "operations.visitor-visit.qr.v1"
VISITOR_QR_MAX_AGE = 60 * 60 * 24


def make_visit_token(visit) -> str:
    """Create a token valid through the day after the expected arrival."""
    return signing.dumps({"visit": str(visit.pk)}, salt=VISITOR_QR_SALT)


def get_visit_qr_data_uri(visit) -> str:
    image = qrcode.make(make_visit_token(visit), box_size=5, border=2)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def read_visit_token(token: str):
    """Validate a token and return its visit primary key."""
    payload = signing.loads(
        token.strip(), salt=VISITOR_QR_SALT, max_age=VISITOR_QR_MAX_AGE,
    )
    return payload["visit"]
