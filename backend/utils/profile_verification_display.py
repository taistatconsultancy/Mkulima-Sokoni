"""
Effective verification label for UI: combines database status with mandatory profile completeness.
"""


def effective_verification_badge(
    db_status,
    profile_complete: bool,
) -> str:
    """
    - DB rejected -> Rejected
    - DB verified/approved AND profile_complete -> Verified (display as 'verified')
    - Otherwise -> Pending
    """
    db = str(db_status or "pending").strip().lower()
    if db == "rejected":
        return "rejected"
    if db in ("verified", "approved") and profile_complete:
        return "verified"
    return "pending"
