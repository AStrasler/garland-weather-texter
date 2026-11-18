"""Narrow HTTPS transport for the weather and messaging providers."""

from __future__ import annotations

import urllib.error
import urllib.request
from urllib.parse import urlsplit


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects so credentials and requests stay at the configured host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.URLError("redirects are disabled for provider requests")


def validate_https_url(
    url: str,
    *,
    allowed_hosts: set[str] | frozenset[str] | tuple[str, ...],
    allow_subdomains: bool = False,
) -> str:
    """Accept only HTTPS URLs for an explicit host allowlist."""
    if not isinstance(url, str) or not url:
        raise ValueError("URL must be a non-empty string")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as error:
        raise ValueError("URL is malformed") from error

    host = parts.hostname
    if (
        parts.scheme.lower() != "https"
        or not host
        or host.endswith(".")
        or parts.username is not None
        or parts.password is not None
        or parts.fragment
        or "#" in url
        or port not in (None, 443)
    ):
        raise ValueError("URL must be an HTTPS URL without credentials or a fragment")

    host = host.lower()
    allowed = {candidate.lower().rstrip(".") for candidate in allowed_hosts}
    if not any(
        host == candidate or (allow_subdomains and host.endswith("." + candidate))
        for candidate in allowed
    ):
        raise ValueError("URL host is not an approved provider")
    return url


def open_https_url(
    request: str | urllib.request.Request,
    *,
    allowed_hosts: set[str] | frozenset[str] | tuple[str, ...],
    timeout: float,
    allow_subdomains: bool = False,
):
    """Open an approved HTTPS request without following redirects."""
    url = request.full_url if isinstance(request, urllib.request.Request) else request
    validate_https_url(url, allowed_hosts=allowed_hosts, allow_subdomains=allow_subdomains)
    if isinstance(request, urllib.request.Request):
        request = urllib.request.Request(
            url,
            data=request.data,
            headers=dict(request.header_items()),
            method=request.get_method(),
        )
    opener = urllib.request.build_opener(NoRedirectHandler())
    return opener.open(request, timeout=timeout)
