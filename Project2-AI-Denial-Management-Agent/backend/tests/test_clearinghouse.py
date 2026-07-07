from app import clearinghouse


def test_submit_returns_confirmation():
    submission = clearinghouse.submit("CLM-2026-04871")
    assert submission.confirmation_number.startswith("CH-")
    assert submission.status == "accepted"
    assert submission.clearinghouse_name
    assert submission.submitted_at
