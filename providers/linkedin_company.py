"""LinkedIn provider variant for Company Page posting.

Uses the Community Management API app with organization scopes. Posts to
Company Pages the authenticated member administers via
``w_organization_social`` and ``rw_organization_admin``.
"""

from __future__ import annotations

from .linkedin import API_BASE, LinkedInProvider
from .types import AccountProfile


class LinkedInCompanyProvider(LinkedInProvider):
    """LinkedIn provider scoped to Company Page posting."""

    @property
    def platform_name(self) -> str:
        return "LinkedIn (Company Page)"

    @property
    def required_scopes(self) -> list[str]:
        return [
            "openid",
            "profile",
            "email",
            "w_member_social",
            "w_organization_social",
            "r_organization_social",
            "rw_organization_admin",
        ]

    def get_profile(self, access_token: str) -> AccountProfile:
        resp = self._request("GET", f"{API_BASE}/v2/userinfo", access_token=access_token)
        data = resp.json()
        return AccountProfile(
            platform_id=data.get("sub", ""),
            name=data.get("name", ""),
            avatar_url=data.get("picture"),
            extra=data,
        )
