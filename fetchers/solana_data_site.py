"""
solana.com/data — best-effort fetch.

There is no official public API behind this page; it renders client-side
via JavaScript, so a plain HTTP GET mostly returns an app shell. This module
attempts to pull any JSON blobs embedded in the initial HTML (common for
Next.js `__NEXT_DATA__` payloads) as a best-effort source of headline
figures. If the page structure changes (likely, since it's an SPA) this
will simply find nothing and report "unavailable" — it is explicitly
allowed to fail without breaking the rest of the report.

This is the most fragile fetcher in the project by design; treat any values
it returns as a bonus cross-check against the RPC/DeFiLlama/CoinGecko numbers,
not as a primary source.
"""
import json
import re
import urllib.request
import urllib.error

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)


def snapshot():
    out = {"available": False, "raw_next_data_found": False, "extracted": {}, "errors": []}
    try:
        req = urllib.request.Request(
            config.SOLANA_DATA_URL,
            headers={"User-Agent": "Mozilla/5.0 (SolPulse best-effort fetch)"},
        )
        with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT_SECONDS) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        match = NEXT_DATA_RE.search(html)
        if match:
            out["raw_next_data_found"] = True
            payload = json.loads(match.group(1))
            # Structure is undocumented/unstable — surface it raw (truncated) for
            # manual inspection rather than guessing a schema that will break.
            out["extracted"]["props_keys"] = list(
                payload.get("props", {}).get("pageProps", {}).keys()
            )
            out["available"] = True
        else:
            out["errors"].append(
                "No __NEXT_DATA__ payload found — page is likely fully client-rendered. "
                "Open solana.com/data manually for the latest headline figures."
            )
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        out["errors"].append(str(e))

    return out
