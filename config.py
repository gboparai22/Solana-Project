"""
SolPulse — configuration.

Everything here is a plain constant so the whole project stays stdlib-only.
Override any of these with environment variables at run time, e.g.:

    SOLPULSE_RPC_URL=https://my-rpc.example.com python3 orchestrator.py --once

Secrets (DUNE_API_KEY, TWITTER_BEARER_TOKEN, GLASSNODE_API_KEY, CMC_API_KEY)
should go in a `.env` file next to this one (copy `.env.example` -> `.env`),
NOT hardcoded here. `.env` is loaded below with zero third-party deps and is
git-ignored — see .gitignore.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(path=None):
    """
    Minimal stdlib .env loader: KEY=VALUE per line, '#' comments, blank
    lines ignored. Existing real environment variables always win — this
    only fills in gaps, so `SOME_KEY=x python3 orchestrator.py` still
    overrides whatever is in .env.
    """
    path = path or os.path.join(BASE_DIR, ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


_load_dotenv()

# ---------------------------------------------------------------------------
# Solana RPC — public mainnet-beta endpoint by default. No key required.
# A short fallback list is tried in order if the primary endpoint is down.
# ---------------------------------------------------------------------------
RPC_ENDPOINTS = [
    os.environ.get("SOLPULSE_RPC_URL", "https://api.mainnet-beta.solana.com"),
    "https://solana-api.projectserum.com",
]

# How many validators/samples to pull per RPC call (keeps payloads small)
VOTE_ACCOUNT_TOP_N = 15
PERFORMANCE_SAMPLE_LIMIT = 20  # ~ last 20 * 60s of slots

# Wallets to watch for getBalance / getSignaturesForAddress (optional).
# Add addresses you care about, e.g. treasury wallets, foundation wallet, etc.
WATCHED_ADDRESSES = {
    # "label": "base58-address",
}

# ---------------------------------------------------------------------------
# DeFiLlama — free public API, no key.
# ---------------------------------------------------------------------------
DEFILLAMA_CHAIN_TVL_URL = "https://api.llama.fi/v2/historicalChainTvl/Solana"
DEFILLAMA_CHAINS_URL = "https://api.llama.fi/v2/chains"
DEFILLAMA_STABLECOINS_URL = "https://stablecoins.llama.fi/stablecoinchains"
DEFILLAMA_DEX_VOLUME_URL = "https://api.llama.fi/overview/dexs/Solana?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true"
# Fees + revenue overview, free tier, same shape/endpoint family as the DEX
# volume call above. This is DeFiLlama's "protocol fees" number for the
# chain, not a strict REV definition (fees + priority fees + issuance) -
# treat it as a defensible, keyless proxy for REV and say so in the report.
DEFILLAMA_FEES_URL = "https://api.llama.fi/overview/fees/Solana?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true"
# Free /protocols endpoint (NOT the paid "RWA by Chain" download product) -
# filtered client-side for category == RWA and chain == Solana.
DEFILLAMA_PROTOCOLS_URL = "https://api.llama.fi/protocols"
RWA_CATEGORY_NAME = "RWA"
RWA_CHAIN_NAME = "Solana"

# ---------------------------------------------------------------------------
# CoinGecko — free public API, no key (rate limited, ~10-30 calls/min).
# ---------------------------------------------------------------------------
COINGECKO_PRICE_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=solana&vs_currencies=usd&include_market_cap=true"
    "&include_24hr_vol=true&include_24hr_change=true"
)
COINGECKO_MARKET_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&ids=solana"
)

# ---------------------------------------------------------------------------
# CoinMarketCap — OPTIONAL cross-check / fallback for price data. CoinGecko's
# free tier rate-limits fairly aggressively, so if CMC_API_KEY is set,
# SolPulse backfills price/market cap/volume from CMC whenever CoinGecko's
# call fails, and flags in the report which source actually served the data.
# ---------------------------------------------------------------------------
CMC_API_KEY = os.environ.get("CMC_API_KEY", "")
CMC_QUOTES_URL = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest?symbol=SOL"

# ---------------------------------------------------------------------------
# Glassnode — OPTIONAL. Requires GLASSNODE_API_KEY. Confirmed to support SOL
# on the Active Addresses metric (addresses/active_count). Used for the
# "daily active addresses" ecosystem-growth figure the brief asks for, which
# has no free/keyless public source.
# ---------------------------------------------------------------------------
GLASSNODE_API_KEY = os.environ.get("GLASSNODE_API_KEY", "")
GLASSNODE_ASSET = "SOL"
GLASSNODE_ACTIVE_ADDRESSES_URL = "https://api.glassnode.com/v1/metrics/addresses/active_count"

# ---------------------------------------------------------------------------
# Twitter / X — OPTIONAL. Requires TWITTER_BEARER_TOKEN env var (X API v2).
# Without a token this section is skipped gracefully.
# ---------------------------------------------------------------------------
TWITTER_BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN", "")
TWITTER_WATCHLIST = [
    "solana", "SolanaFndn", "aeyakovenko", "heliuslabs", "SolanaStatus",
]

# ---------------------------------------------------------------------------
# solana.com/data — best-effort HTML scrape (no official public API).
# This is fragile by nature (the page is a JS SPA); treated as optional
# and allowed to fail silently. See fetchers/solana_data_site.py.
# ---------------------------------------------------------------------------
SOLANA_DATA_URL = "https://solana.com/data"

# ---------------------------------------------------------------------------
# Anomaly detection thresholds
# ---------------------------------------------------------------------------
ANOMALY_THRESHOLDS = {
    "tps_zscore": 2.5,             # flag if current TPS z-score vs rolling history exceeds this
    "tps_min_hard_floor": 500,     # flag regardless of history if TPS falls below this
    "slot_time_ms_warn": 500,      # normal slot time ~400ms; warn above this
    "slot_time_ms_critical": 800,
    "delinquent_stake_pct_warn": 5.0,
    "delinquent_stake_pct_critical": 10.0,
    "tvl_pct_change_warn": 8.0,    # % change vs previous snapshot
    "tvl_pct_change_critical": 15.0,
    "price_pct_change_warn": 7.0,
    "price_pct_change_critical": 15.0,
    "rolling_history_window": 50,  # number of past snapshots kept for z-score calcs
}

# ---------------------------------------------------------------------------
# Output / scheduling
# ---------------------------------------------------------------------------
OUTPUT_DIR = os.environ.get("SOLPULSE_OUTPUT_DIR", "./output")
HISTORY_FILE = os.environ.get("SOLPULSE_HISTORY_FILE", "./data/history.json")
DEFAULT_REFRESH_INTERVAL_SECONDS = int(os.environ.get("SOLPULSE_INTERVAL", "300"))  # 5 min
HTTP_TIMEOUT_SECONDS = 10

# Known / commonly-cited upcoming Solana upgrades — maintained manually since
# there is no single machine-readable feed for roadmap items. Update this
# list as items ship or new ones are announced.
ROADMAP_ITEMS = [
    {
        "name": "Alpenglow",
        "description": "Proposed consensus overhaul (Votor + Rotor) targeting ~150ms "
                        "finality, replacing TowerBFT/Turbine's block-based finality model.",
        "status": "Proposed / in community & validator review",
    },
    {
        "name": "SIMD-525",
        "description": "SIMD-based Solana Improvement Document — check the solana-foundation "
                        "SIMD GitHub repo for current status and vote tally before citing "
                        "as accepted; proposal specifics change during review.",
        "status": "See github.com/solana-foundation/solana-improvement-documents",
    },
]
