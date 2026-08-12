"""
CoinGecko fetcher — free public API, no key required (subject to rate limits;
back off / cache if you drop the refresh interval below ~1 minute).
"""
import json
import urllib.request

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SolPulse/1.0"})
    with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode("utf-8"))


def snapshot():
    out = {
        "price_usd": None,
        "market_cap_usd": None,
        "volume_24h_usd": None,
        "change_24h_pct": None,
        "errors": [],
    }
    try:
        data = _get_json(config.COINGECKO_PRICE_URL)
        sol = data.get("solana", {})
        out["price_usd"] = sol.get("usd")
        out["market_cap_usd"] = sol.get("usd_market_cap")
        out["volume_24h_usd"] = sol.get("usd_24h_vol")
        out["change_24h_pct"] = sol.get("usd_24h_change")
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"price: {e}")
    return out
