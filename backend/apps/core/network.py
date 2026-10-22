"""Client IP resolution that trusts only the configured number of reverse proxies.

With ``NUM_PROXIES=0`` the client-controlled ``X-Forwarded-For`` header is ignored entirely;
with ``N`` proxies the N-th address from the right is used (the one appended by the first
trusted proxy). Anything that is not a valid IP address is discarded so a hostile header can
never reach ``inet`` columns or rate-limit keys.
"""

from __future__ import annotations

import ipaddress

from django.conf import settings


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if candidate.startswith("[") and "]" in candidate:  # [::1]:port
        candidate = candidate[1 : candidate.index("]")]
    elif candidate.count(":") == 1:  # 1.2.3.4:port
        candidate = candidate.split(":")[0]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def client_ip(request) -> str | None:
    if request is None:
        return None
    num_proxies = getattr(settings, "NUM_PROXIES", 0) or 0
    remote = _valid_ip(request.META.get("REMOTE_ADDR"))
    if num_proxies <= 0:
        return remote
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    hops = [hop for hop in (h.strip() for h in forwarded.split(",")) if hop]
    if not hops:
        return remote
    index = max(len(hops) - num_proxies, 0)
    return _valid_ip(hops[index]) or remote
