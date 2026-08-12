"""
Glassnode fetcher — OPTIONAL.

Fills the "daily active addresses" ecosystem-growth figure the brief asks
for, which has no free/keyless public source. Glassnode added SOL coverage
on their Active Addresses metric (unique senders + receivers per day), so
this is a direct fit — confirmed against Glassnode's metric catalog
(addresses/active_count, asset=SOL, resolutions down to 24h).

Setup (optional):
    1. Get a Glassnode API key: https://studio.glassnode.com/settings/api
    2. Put GLASSNODE_API_KEY=... in .env
    3. That's it — no query IDs to configure, unlike Dune.

If no key is set, snapshot() returns an "unavailable" marker (same pattern
as dune.py / twitter.py) rather than failing the whole report.
"""
import json
import urllib.request
import urllib.error
import urllib.parse

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def snapshot():
    if not config.GLASSNODE_API_KEY:
        return {
            "available": False,
            "reason": "No GLASSNODE_API_KEY configured — add one in .env to enable "
                      "daily active addresses.",
            "daily_active_addresses": None,
        }

    params = urllib.parse.urlencode({
        "a": config.GLASSNODE_ASSET,
        "i": "24h",
        "api_key": config.GLASSNODE_API_KEY,
    })
    url = f"{config.GLASSNODE_ACTIVE_ADDRESSES_URL}?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SolPulse/1.0"})
        with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # Glassnode returns a time series: [{"t": unix_ts, "v": value}, ...]
        # Take the most recent point as "today's" active addresses.
        if isinstance(data, list) and data:
            latest = data[-1]
            return {
                "available": True,
                "daily_active_addresses": latest.get("v"),
                "as_of_utc": latest.get("t"),
                "errors": [],
            }
        return {
            "available": False,
            "reason": "Glassnode returned no data points for this asset/resolution.",
            "daily_active_addresses": None,
        }
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        return {
            "available": False,
            "reason": f"Glassnode request failed: {e}",
            "daily_active_addresses": None,
        }
