"""
Dune Analytics fetcher — OPTIONAL.

Dune does not offer a keyless public API for pulling arbitrary query results,
so this module only activates if you set DUNE_API_KEY and point
config.DUNE_QUERY_IDS at query IDs you already own (or that are public and
you've forked/saved). If no key is configured, snapshot() returns an
"unavailable" marker rather than failing the whole report.

Setup (optional):
    1. Create a free/paid Dune API key: https://dune.com/settings/api
    2. export DUNE_API_KEY=...
    3. In config.py, set DUNE_QUERY_IDS = {"solana_daily_active_addresses": 1234567, ...}
       (the query must already exist under your Dune account)
    4. SolPulse calls the "get latest result" endpoint — it does not execute
       queries on your behalf, so you stay in control of Dune credit usage.
"""
import json
import urllib.request
import urllib.error

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

DUNE_LATEST_RESULT_URL = "https://api.dune.com/api/v1/query/{query_id}/results"


def _get_latest_result(query_id):
    req = urllib.request.Request(
        DUNE_LATEST_RESULT_URL.format(query_id=query_id),
        headers={"X-Dune-API-Key": config.DUNE_API_KEY},
    )
    with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode("utf-8"))


def snapshot():
    if not config.DUNE_API_KEY or not config.DUNE_QUERY_IDS:
        return {
            "available": False,
            "reason": "No DUNE_API_KEY / DUNE_QUERY_IDS configured — add a key and "
                      "query IDs in config.py to enable Dune-sourced metrics.",
            "results": {},
        }

    results = {}
    errors = []
    for label, query_id in config.DUNE_QUERY_IDS.items():
        try:
            raw = _get_latest_result(query_id)
            rows = raw.get("result", {}).get("rows", [])
            results[label] = {
                "rows": rows,
                "executed_at": raw.get("execution_started_at"),
            }
        except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
            errors.append(f"{label} ({query_id}): {e}")

    return {"available": True, "results": results, "errors": errors}
