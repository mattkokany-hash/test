"""Offline tests for the Bybit OAuth connector, v5 signer, and perps quoting.
No network; live endpoints are exercised only via monkeypatched HTTP."""

import base64
import hashlib
import os

from polymm.live import bybit_oauth as oauth_mod
from polymm.live.bybit_oauth import BybitOAuth, OAuthConfig, generate_pkce
from polymm.live.bybit_auth import BybitAuth, sign_v5
from polymm.perps import PerpsConfig, PerpsQuotingEngine
from polymm.live.http import HttpError

SCRATCH = "/tmp/claude-0/-home-user-test/7ccaa4a2-372e-5d4c-abee-b5eccb10a32e/scratchpad"


# --- PKCE + authorize URL -------------------------------------------------

def test_pkce_challenge_matches_verifier():
    verifier, challenge = generate_pkce()
    expect = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expect
    assert "=" not in verifier and "=" not in challenge


def test_authorize_url_has_pkce_and_client():
    start = BybitOAuth(OAuthConfig(env="testnet")).start()
    url = start["authorize_url"]
    assert "client_id=ai-agent" in url
    assert "code_challenge=" in url and "code_challenge_method=S256" in url
    assert start["code_verifier"]


# --- token exchange / refresh (mocked HTTP) -------------------------------

def test_exchange_code_unwraps_result(monkeypatch):
    monkeypatch.setattr(oauth_mod, "post_form", lambda *a, **k: {
        "ret_code": 0, "result": {"access_token": "AT", "refresh_token": "RT",
                                   "expires_in": 3600}})
    tok = BybitOAuth().exchange_code("code123", "verifier")
    assert tok["access_token"] == "AT" and tok["expires_in"] == 3600


def test_2fa_is_terminal(monkeypatch):
    monkeypatch.setattr(oauth_mod, "post_form",
                        lambda *a, **k: {"ret_code": 20039, "ret_msg": "2fa"})
    try:
        BybitOAuth().exchange_code("c", "v")
        assert False, "should have raised on 2FA"
    except HttpError as e:
        assert "20039" in str(e)


def test_error_ret_code_raises(monkeypatch):
    monkeypatch.setattr(oauth_mod, "post_form",
                        lambda *a, **k: {"ret_code": 10001, "ret_msg": "bad"})
    try:
        BybitOAuth().refresh("RT")
        assert False
    except HttpError as e:
        assert "10001" in str(e)


# --- credential file ------------------------------------------------------

def test_credentials_roundtrip_and_mode():
    path = os.path.join(SCRATCH, "oauth_token_test.json")
    if os.path.exists(path):
        os.remove(path)
    creds = {"access_token": "AT", "created_at": 1000, "expires_in": 3600,
             "ai-account": {"api_key": "K", "api_secret": "S"}}
    BybitOAuth.save_credentials(creds, path=path)
    assert (os.stat(path).st_mode & 0o777) == 0o600
    loaded = BybitOAuth.load_credentials(path=path)
    assert loaded["ai-account"]["api_key"] == "K"
    os.remove(path)


def test_is_expired():
    import time
    fresh = {"created_at": int(time.time()), "expires_in": 3600}
    old = {"created_at": 1000, "expires_in": 3600}
    assert not BybitOAuth.is_expired(fresh)
    assert BybitOAuth.is_expired(old)


def test_from_oauth_credentials_builds_auth():
    creds = {"ai-account": {"api_key": "K", "api_secret": "S"}}
    auth = BybitAuth.from_oauth_credentials(creds, testnet=True)
    assert auth.api_key == "K" and auth.testnet is True


# --- v5 signing -----------------------------------------------------------

def test_sign_v5_deterministic_and_sensitive():
    a = sign_v5("secret", "1700000000000", "APIKEY", "5000", "symbol=BTCUSDT")
    b = sign_v5("secret", "1700000000000", "APIKEY", "5000", "symbol=BTCUSDT")
    c = sign_v5("secret", "1700000000000", "APIKEY", "5000", "symbol=ETHUSDT")
    assert a == b                      # deterministic
    assert a != c                      # payload changes signature
    assert len(a) == 64                # sha256 hex


# --- perps quoting --------------------------------------------------------

def test_perps_two_sided_when_flat():
    q = PerpsQuotingEngine(PerpsConfig()).quote("BTCUSDT", 60000.0, 8e-5, 0.0)
    assert q.bid is not None and q.ask is not None
    assert q.bid < q.mid < q.ask
    assert q.bid_size > 0 and q.ask_size > 0


def test_perps_prices_on_tick():
    cfg = PerpsConfig(tick=0.5)
    q = PerpsQuotingEngine(cfg).quote("BTCUSDT", 60000.0, 8e-5, 0.0)
    assert abs((q.bid / 0.5) - round(q.bid / 0.5)) < 1e-9
    assert abs((q.ask / 0.5) - round(q.ask / 0.5)) < 1e-9


def test_perps_inventory_skews_reservation():
    eng = PerpsQuotingEngine(PerpsConfig())
    flat = eng.quote("BTCUSDT", 60000.0, 8e-5, 0.0)
    long = eng.quote("BTCUSDT", 60000.0, 8e-5, 0.15)
    assert long.reservation < flat.reservation   # long -> lean price down


def test_perps_size_capped_by_position_limit():
    cfg = PerpsConfig(max_position=0.10, max_order_size=0.05)
    eng = PerpsQuotingEngine(cfg)
    # Already near the long cap: buy size should shrink, sell side stays full.
    q = eng.quote("BTCUSDT", 60000.0, 8e-5, 0.08)
    assert q.bid_size <= 0.02 + 1e-9         # room = 0.10 - 0.08 = 0.02
    assert q.ask_size >= 0.05 - 1e-9


def test_perps_never_crossed():
    eng = PerpsQuotingEngine(PerpsConfig(tick=1.0, base_edge_bps=0.0, fee_bps=0.0,
                                         min_half_ticks=1.0))
    q = eng.quote("BTCUSDT", 100.0, 1e-9, 0.0)
    assert q.ask > q.bid
