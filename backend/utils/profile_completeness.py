"""Shared profile completeness checks (mandatory fields only)."""


def farmer_profile_complete(row) -> bool:
    if not row:
        return False
    return bool(
        str(row.get('farm_name') or '').strip()
        and str(row.get('location') or '').strip()
        and str(row.get('county') or '').strip()
    )


def buyer_profile_complete(row) -> bool:
    if not row:
        return False
    return bool(
        str(row.get('company_name') or '').strip()
        and str(row.get('location') or '').strip()
        and str(row.get('county') or '').strip()
    )
