"""
CoinMarketCap fetcher — OPTIONAL cross-check / fallback.

CoinGecko's free tier is the primary price source (see coingecko.py) and
needs no key. CMC only gets called by the orchestrator when CMC_API_KEY is
set AND CoinGecko's call came back empty — it exists purely as a fallback
for reliability, not a second primary source, so the report only shows one
price figure and notes which provider actually served it.
"""
import json
import urllib.request
import urllib.error

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def snapshot():
    if not config.CMC_API_KEY:
        return {"available": False, "reason": "No CMC_API_KEY configured.", "errors": []}

    try:
        req = urllib.request.Request(
            config.CMC_QUOTES_URL,
            headers={"X-CMC_PRO_API_KEY": config.CMC_API_KEY, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        sol = data.get("data", {}).get("SOL")
        # v2 quotes/latest returns a list per symbol
        sol = sol[0] if isinstance(sol, list) else sol
        quote = (sol or {}).get("quote", {}).get("USD", {})
        return {
            "available": True,
            "price_usd": quote.get("price"),
            "market_cap_usd": quote.get("market_cap"),
            "volume_24h_usd": quote.get("volume_24h"),
            "change_24h_pct": quote.get("percent_change_24h"),
            "errors": [],
        }
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError) as e:
        return {"available": False, "reason": f"CMC request failed: {e}", "errors": [str(e)]}
