"""Simulated clearinghouse submission for demo purposes.

No real clearinghouse is contacted here - this exists to make the
approve -> generate -> submit workflow demoable end-to-end without a
real clearinghouse account/contract.
"""
import random
import string
from datetime import datetime, timezone
from app.models import ClearinghouseSubmission

MOCK_CLEARINGHOUSE_NAME = "Clearinghouse Gateway"


def submit(claim_id: str) -> ClearinghouseSubmission:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return ClearinghouseSubmission(
        confirmation_number=f"CH-{suffix}",
        submitted_at=datetime.now(timezone.utc).isoformat(),
        clearinghouse_name=MOCK_CLEARINGHOUSE_NAME,
        status="accepted",
    )
