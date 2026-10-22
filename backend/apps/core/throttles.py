import hashlib

from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle


class AuthRateThrottle(ScopedRateThrottle):
    """Per-IP throttle for login/registration endpoints (view sets ``throttle_scope``)."""

    scope_attr = "throttle_scope"


class FamilyCodeThrottle(SimpleRateThrottle):
    """Throttle child-login attempts per (IP, family code) pair so one code cannot be brute-forced.

    The IP comes from DRF's ``get_ident`` which honours ``NUM_PROXIES``; the code is normalised the
    same way the lookup does, so ``abc-def`` and ``ABCDEF`` share a bucket.
    """

    scope = "child_login"

    def get_cache_key(self, request, view):
        from apps.accounts.services import normalize_family_code

        data = request.data if isinstance(getattr(request, "data", None), dict) else {}
        code = normalize_family_code(str(data.get("family_code", "")))
        digest = hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]
        return self.cache_format % {"scope": self.scope, "ident": f"{self.get_ident(request)}:{digest}"}
