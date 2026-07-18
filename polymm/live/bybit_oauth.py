"""Bybit OAuth connector (Python port of the bybit-exchange/skills OAuth flow).

Implements the same protocol the skill's ``modules/oauth.js`` describes, in pure
stdlib, so a polymm deployment can obtain and refresh Bybit AI-subaccount API
credentials via OAuth instead of hand-pasted keys.

Flow (headless / cloud path, which is what a server-run bot uses):

1. Generate a PKCE ``code_verifier`` + ``code_challenge`` (S256).
2. Build the authorization URL; the user opens it, authorizes, and pastes back
   the ``code`` (authorization codes expire in 10 minutes).
3. Exchange the code for tokens at ``POST /oauth/v1/public/access_token``
   (``client_id=ai-agent``, ``code``, ``code_verifier`` — no grant_type / no
   redirect_uri, per the spec).
4. Fetch AI sub-accounts (``GET /oauth/v1/resource/restrict/ai_accounts``) and
   let the user pick one explicitly (no auto-selection).
5. Persist ``{access_token, refresh_token, created_at, expires_in, ...,
   ai-account:{sub_member_id, api_key, api_secret}}`` to
   ``~/.bybit/oauth_token.json`` (or ``$BYBIT_CRED_DIR``) at mode 0600.
6. Refresh via ``POST /oauth/v1/public/refresh_token`` before expiry.

IMPORTANT: this cannot be exercised against Bybit from the polymm dev sandbox
(the venue CDN-blocks datacenter IPs), so the network paths here are written to
spec but untested against the live endpoint. The pure logic (PKCE, URL building,
credential file handling, expiry) is unit-tested offline. ``ret_code=20039`` (2FA
required) is treated as terminal. Tokens/secrets are never logged.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass

from .http import get_json, post_form, HttpError

__all__ = ["OAuthConfig", "BybitOAuth", "generate_pkce", "credential_path"]

_BASE = {
    "mainnet": "https://api2.bybit.com",
    "testnet": "https://api2-testnet.bybit.com",
    "unify-test-3": "https://api2.unify-test-3.bybit.com",
}
# Front-end authorization page. Configurable because it must match the skill's
# oauth.js build; override via OAuthConfig.authorize_url if Bybit changes it.
_AUTHORIZE = {
    "mainnet": "https://www.bybit.com/oauth/authorize",
    "testnet": "https://testnet.bybit.com/oauth/authorize",
}
_CLIENT_ID = "ai-agent"
_2FA_TERMINAL = 20039


def generate_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) using S256, per RFC 7636."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def credential_path() -> str:
    """Credential file location: $BYBIT_CRED_DIR/oauth_token.json or ~/.bybit/."""
    base = os.environ.get("BYBIT_CRED_DIR") or os.path.join(
        os.path.expanduser("~"), ".bybit")
    return os.path.join(base, "oauth_token.json")


@dataclass
class OAuthConfig:
    env: str = "testnet"                 # 'mainnet' | 'testnet' | 'unify-test-3'
    authorize_url: str | None = None     # override the front-end authorize page
    timeout: float = 15.0

    def base(self) -> str:
        if self.env not in _BASE:
            raise ValueError(f"unknown env: {self.env}")
        return _BASE[self.env]

    def authorize(self) -> str:
        return self.authorize_url or _AUTHORIZE.get(self.env, _AUTHORIZE["mainnet"])


class BybitOAuth:
    def __init__(self, cfg: OAuthConfig | None = None):
        self.cfg = cfg or OAuthConfig()

    # -- step 1/2: PKCE + authorization URL --------------------------------

    def start(self, *, redirect_uri: str = "http://localhost:9876/callback",
              scope: str = "trade") -> dict:
        """Begin a headless authorization. Returns the URL to open and the
        code_verifier to keep for the exchange step."""
        verifier, challenge = generate_pkce()
        state = secrets.token_urlsafe(16)
        from urllib.parse import urlencode
        params = {
            "client_id": _CLIENT_ID,
            "response_type": "code",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
        }
        return {
            "authorize_url": f"{self.cfg.authorize()}?{urlencode(params)}",
            "code_verifier": verifier,
            "state": state,
        }

    # -- step 3: exchange code --------------------------------------------

    def exchange_code(self, code: str, code_verifier: str) -> dict:
        """Exchange an authorization code for tokens. Raises on 2FA-required."""
        resp = post_form(
            f"{self.cfg.base()}/oauth/v1/public/access_token",
            {"client_id": _CLIENT_ID, "code": code, "code_verifier": code_verifier},
            timeout=self.cfg.timeout,
        )
        return self._unwrap(resp)

    # -- step 4: accounts --------------------------------------------------

    def fetch_ai_accounts(self, access_token: str) -> list[dict]:
        resp = get_json(
            f"{self.cfg.base()}/oauth/v1/resource/restrict/ai_accounts",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=self.cfg.timeout,
        )
        data = self._unwrap(resp)
        accts = data.get("list") or data.get("accounts") or []
        return accts if isinstance(accts, list) else []

    # -- step 6: refresh ---------------------------------------------------

    def refresh(self, refresh_token: str) -> dict:
        resp = post_form(
            f"{self.cfg.base()}/oauth/v1/public/refresh_token",
            {"client_id": _CLIENT_ID, "refresh_token": refresh_token},
            timeout=self.cfg.timeout,
        )
        return self._unwrap(resp)

    # -- credential file ---------------------------------------------------

    @staticmethod
    def load_credentials(path: str | None = None) -> dict | None:
        path = path or credential_path()
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def save_credentials(creds: dict, path: str | None = None) -> str:
        path = path or credential_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Write then chmod 0600 (owner-only), matching the skill's hygiene rule.
        with open(path, "w", encoding="utf-8") as f:
            json.dump(creds, f, indent=2)
        os.chmod(path, 0o600)
        return path

    @staticmethod
    def is_expired(creds: dict, *, skew_s: int = 60) -> bool:
        created = creds.get("created_at", 0)
        ttl = creds.get("expires_in", 0)
        return (int(time.time()) - int(created)) >= (int(ttl) - skew_s)

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _unwrap(resp) -> dict:
        """Bybit wraps payloads as {ret_code, ret_msg, result}. Enforce 2FA
        terminal rule and surface errors; return the ``result`` body."""
        if not isinstance(resp, dict):
            raise HttpError("bybit-oauth", None, f"unexpected response: {resp!r}")
        rc = resp.get("ret_code", resp.get("retCode", 0))
        if rc == _2FA_TERMINAL:
            raise HttpError("bybit-oauth", None,
                            "2FA required (ret_code=20039) — terminal, aborting")
        if rc not in (0, None):
            msg = resp.get("ret_msg") or resp.get("retMsg") or "error"
            raise HttpError("bybit-oauth", None, f"ret_code={rc}: {msg}")
        return resp.get("result", resp)
