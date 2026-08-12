"""
DeFiLlama fetcher — free public JSON API, no key required.
Pulls Solana TVL (current + trend), stablecoin supply on Solana, and DEX volume.
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


def get_chain_tvl_history():
    """List of {date, tvl} for Solana; we only keep the tail for trend + latest."""
    data = _get_json(config.DEFILLAMA_CHAIN_TVL_URL)
    return data[-30:] if isinstance(data, list) else []


def get_chain_summary():
    """Cross-chain snapshot; filter down to Solana's row for extra context (rank, name)."""
    data = _get_json(config.DEFILLAMA_CHAINS_URL)
    for row in data:
        if row.get("name", "").lower() == "solana":
            return row
    return None


def get_stablecoin_supply():
    data = _get_json(config.DEFILLAMA_STABLECOINS_URL)
    for row in data:
        if row.get("name", "").lower() == "solana" or row.get("gecko_id") == "solana":
            return row
    return None


def get_dex_volume():
    return _get_json(config.DEFILLAMA_DEX_VOLUME_URL)


def get_fees_revenue():
    """
    Chain-level protocol fees/revenue, same free 'overview' family as DEX
    volume. This is a proxy for REV, not the strict definition (fees +
    priority fees + issuance) — flagged as such in the reports.
    """
    return _get_json(config.DEFILLAMA_FEES_URL)


def get_rwa_tvl_solana():
    """
    Tokenized real-world-asset volume on Solana. Uses the free /protocols
    endpoint (not DeFiLlama's paid 'RWA by Chain' download product) and
    filters client-side for category == RWA and chain == Solana, summing
    each matching protocol's current TVL as a proxy for tokenized asset
    volume (equities, treasuries, etc.) on the chain.
    """
    data = _get_json(config.DEFILLAMA_PROTOCOLS_URL)
    matches = [
        p for p in data
        if p.get("category") == config.RWA_CATEGORY_NAME
        and config.RWA_CHAIN_NAME in (p.get("chains") or [])
    ]
    total_tvl = sum(p.get("tvl") or 0 for p in matches)
    return {
        "protocol_count": len(matches),
        "total_tvl_usd": total_tvl,
        "protocols": [
            {"name": p.get("name"), "tvl_usd": p.get("tvl")}
            for p in sorted(matches, key=lambda p: p.get("tvl") or 0, reverse=True)[:10]
        ],
    }


def snapshot():
    out = {"tvl_history": None, "tvl_latest_usd": None, "chain_summary": None,
           "stablecoin_supply_usd": None, "dex_volume_24h_usd": None,
           "fees_24h_usd": None, "revenue_24h_usd": None,
           "rwa_tvl_usd": None, "rwa_protocol_count": None, "errors": []}
    try:
        hist = get_chain_tvl_history()
        out["tvl_history"] = hist
        if hist:
            out["tvl_latest_usd"] = hist[-1].get("tvl")
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"tvl_history: {e}")

    try:
        out["chain_summary"] = get_chain_summary()
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"chain_summary: {e}")

    try:
        sc = get_stablecoin_supply()
        if sc:
            out["stablecoin_supply_usd"] = sc.get("totalCirculatingUSD", {}).get("peggedUSD")
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"stablecoins: {e}")

    try:
        dex = get_dex_volume()
        out["dex_volume_24h_usd"] = dex.get("total24h")
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"dex_volume: {e}")

    try:
        fees = get_fees_revenue()
        out["fees_24h_usd"] = fees.get("total24h")
        out["revenue_24h_usd"] = fees.get("totalRevenue24h") or fees.get("total24h")
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"fees_revenue: {e}")

    try:
        rwa = get_rwa_tvl_solana()
        out["rwa_tvl_usd"] = rwa["total_tvl_usd"]
        out["rwa_protocol_count"] = rwa["protocol_count"]
        out["rwa_top_protocols"] = rwa["protocols"]
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"rwa_tvl: {e}")

    return out
