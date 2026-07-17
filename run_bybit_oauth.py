#!/usr/bin/env python3
"""Connect polymm to Bybit via OAuth (headless flow) — run this ON YOUR MACHINE.

Ports the bybit-exchange/skills OAuth flow. It cannot run from the polymm dev
sandbox (Bybit CDN-blocks datacenter IPs) and must not be handed secrets in a
chat — it is interactive by design: you open the link, authorize in your Bybit
account, and paste back the code.

    python3 run_bybit_oauth.py --env testnet     # start on testnet first

Steps: build PKCE + authorize URL -> you authorize -> paste code -> exchange for
tokens -> pick an AI sub-account -> credentials saved 0600 to ~/.bybit/. The
credential file (never chat) is then read by BybitAuth for signed trading.
"""

from __future__ import annotations

import argparse
import time

from polymm.live.bybit_oauth import BybitOAuth, OAuthConfig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="testnet",
                    choices=["testnet", "mainnet", "unify-test-3"])
    args = ap.parse_args()

    oauth = BybitOAuth(OAuthConfig(env=args.env))
    start = oauth.start()
    print("\n1) Open this URL in your browser and authorize:\n")
    print("   " + start["authorize_url"] + "\n")
    print("2) After authorizing you'll be redirected with a ?code=... value.")
    code = input("   Paste the authorization code here: ").strip()

    print("\nExchanging code for tokens…")
    tok = oauth.exchange_code(code, start["code_verifier"])

    print("Fetching your AI sub-accounts…")
    accounts = oauth.fetch_ai_accounts(tok["access_token"])
    if not accounts:
        raise SystemExit("No AI sub-accounts returned. Create one in Bybit first.")
    for i, a in enumerate(accounts):
        print(f"   [{i}] sub_member_id={a.get('sub_member_id')} "
              f"name={a.get('username') or a.get('name','')}")
    idx = int(input("   Select the sub-account to use [index]: ").strip())
    chosen = accounts[idx]

    creds = {
        "access_token": tok["access_token"],
        "refresh_token": tok.get("refresh_token"),
        "created_at": int(time.time()),
        "expires_in": tok.get("expires_in"),
        "refresh_token_expires_in": tok.get("refresh_token_expires_in"),
        "ai-account": {
            "sub_member_id": chosen.get("sub_member_id"),
            "api_key": chosen.get("api_key"),
            "api_secret": chosen.get("api_secret"),
        },
    }
    path = oauth.save_credentials(creds)
    ak = (chosen.get("api_key") or "")[:4]
    print(f"\nSaved credentials (0600) to {path}")
    print(f"  ai-account api_key: {ak}…  (never printed in full)")
    print("\nNext: python3 run_bybit_paper.py --dry-run   (then --testnet-live)")


if __name__ == "__main__":
    main()
