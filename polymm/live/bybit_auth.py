"""Bybit v5 REST authentication (HMAC-SHA256) and signed requests.

The AI-subaccount ``api_key``/``api_secret`` obtained via OAuth (or configured by
hand) are used with Bybit's standard v5 signing scheme:

    sign = HMAC_SHA256(secret, timestamp_ms + api_key + recv_window + payload)

where ``payload`` is the query string for GET or the raw JSON body for POST. The
signature and metadata go in ``X-BAPI-*`` headers. The trading host is
``api.bybit.com`` (mainnet) / ``api-testnet.bybit.com`` (testnet) — distinct from
the ``api2`` OAuth host.

The signing function is pure and unit-tested for determinism. Network calls
target the documented v5 endpoints but are untested against the live venue from
the polymm sandbox (Bybit CDN-blocks datacenter IPs). Testnet is the default.
"""

from __future__ import annotations

import hashlib
import hmac
import json as _json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .http import make_ssl_context, HttpError

__all__ = ["BybitAuth", "sign_v5"]

_HOST = {False: "https://api.bybit.com", True: "https://api-testnet.bybit.com"}


def sign_v5(secret: str, timestamp_ms: str, api_key: str, recv_window: str,
            payload: str) -> str:
    """Deterministic v5 signature. ``payload`` is the GET query string or POST
    JSON body (exactly as sent)."""
    pre = f"{timestamp_ms}{api_key}{recv_window}{payload}"
    return hmac.new(secret.encode(), pre.encode(), hashlib.sha256).hexdigest()


@dataclass
class BybitAuth:
    api_key: str
    api_secret: str
    testnet: bool = True
    recv_window: str = "5000"
    timeout: float = 10.0

    def host(self) -> str:
        return _HOST[self.testnet]

    def _headers(self, payload: str) -> dict[str, str]:
        ts = str(int(time.time() * 1000))
        sign = sign_v5(self.api_secret, ts, self.api_key, self.recv_window, payload)
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": self.recv_window,
            "X-BAPI-SIGN": sign,
        }

    def _send(self, method: str, path: str, payload: str, body: bytes | None,
              headers: dict[str, str]) -> dict:
        url = f"{self.host()}{path}"
        if method == "GET" and payload:
            url = f"{url}?{payload}"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout,
                                        context=make_ssl_context()) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
            raise HttpError(url, e.code, e.read().decode("utf-8", "replace")[:300])
        except Exception as e:  # noqa: BLE001
            raise HttpError(url, None, str(e))
        data = _json.loads(raw) if raw else {}
        rc = data.get("retCode", 0)
        if rc not in (0, None):
            raise HttpError(url, None, f"retCode={rc}: {data.get('retMsg')}")
        return data

    def get(self, path: str, params: dict | None = None) -> dict:
        payload = urllib.parse.urlencode(sorted((params or {}).items()))
        headers = {"Content-Type": "application/json", **self._headers(payload)}
        return self._send("GET", path, payload, None, headers)

    def post(self, path: str, body: dict | None = None) -> dict:
        payload = _json.dumps(body or {}, separators=(",", ":"))
        headers = {"Content-Type": "application/json", **self._headers(payload)}
        return self._send("POST", path, payload, payload.encode(), headers)

    @classmethod
    def from_oauth_credentials(cls, creds: dict, testnet: bool = True) -> "BybitAuth":
        acct = creds.get("ai-account", {})
        if not acct.get("api_key") or not acct.get("api_secret"):
            raise ValueError("credential file has no ai-account api_key/api_secret")
        return cls(api_key=acct["api_key"], api_secret=acct["api_secret"],
                   testnet=testnet)
