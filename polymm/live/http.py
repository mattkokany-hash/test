"""Tiny stdlib JSON-over-HTTP helper.

Kept dependency-free (``urllib``) so market discovery, book reads, and the spot
feed all work with a bare Python install. It honours the standard proxy
environment variables (``HTTPS_PROXY`` etc.) via ``urllib``'s default handling,
and an optional CA bundle from ``SSL_CERT_FILE`` / ``REQUESTS_CA_BUNDLE`` so it
works behind corporate / sandbox proxies.

Only GET and a minimal POST are provided -- authenticated order routing goes
through the CLOB client wrapper, not this helper.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request

__all__ = ["HttpError", "get_json", "post_json", "post_form", "make_ssl_context"]

_DEFAULT_TIMEOUT = 10.0


class HttpError(RuntimeError):
    def __init__(self, url: str, status: int | None, message: str):
        super().__init__(f"HTTP {status} for {url}: {message}")
        self.url = url
        self.status = status


def make_ssl_context() -> ssl.SSLContext:
    """SSL context that prefers an explicit CA bundle from the environment."""
    ca = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if ca and os.path.exists(ca):
        return ssl.create_default_context(cafile=ca)
    return ssl.create_default_context()


def _request(url: str, *, data: bytes | None, headers: dict[str, str],
             method: str, timeout: float) -> dict | list:
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    ctx = make_ssl_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        raise HttpError(url, e.code, body) from e
    except urllib.error.URLError as e:
        raise HttpError(url, None, str(e.reason)) from e
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise HttpError(url, 200, f"invalid JSON: {e}") from e


def get_json(url: str, params: dict | None = None, *,
             headers: dict[str, str] | None = None,
             timeout: float = _DEFAULT_TIMEOUT) -> dict | list:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    return _request(url, data=None, headers=headers or {}, method="GET",
                    timeout=timeout)


def post_json(url: str, payload: dict, *, headers: dict[str, str] | None = None,
              timeout: float = _DEFAULT_TIMEOUT) -> dict | list:
    body = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    return _request(url, data=body, headers=hdrs, method="POST", timeout=timeout)


def post_form(url: str, fields: dict, *, headers: dict[str, str] | None = None,
              timeout: float = _DEFAULT_TIMEOUT) -> dict | list:
    """POST application/x-www-form-urlencoded (OAuth token endpoints)."""
    body = urllib.parse.urlencode(fields).encode("utf-8")
    hdrs = {"Content-Type": "application/x-www-form-urlencoded", **(headers or {})}
    return _request(url, data=body, headers=hdrs, method="POST", timeout=timeout)
