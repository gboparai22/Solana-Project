# SolPulse — Solana Ecosystem Dashboard

An automatically-updating report on the health and activity of the Solana
ecosystem: network performance, validator status, economic indicators, and
ecosystem news — output as an interactive dark-theme HTML dashboard, a
Markdown report, and machine-readable JSON.

Inspired by the "SolPulse" autonomous-agent concept: a low-maintenance
watcher that keeps a pulse on the network and flags anomalies before you
have to go looking for them.

## Why it needs (almost) no API keys

| Source | Key required? | Notes |
|---|---|---|
| Solana RPC (`getSlot`, `getEpochInfo`, `getVoteAccounts`, `getRecentPrioritizationFees`, etc.) | **No** | Public `api.mainnet-beta.solana.com` endpoint |
| DeFiLlama (TVL, stablecoins, DEX volume, fees/revenue, RWA-by-protocol) | **No** | Free public JSON API — the `/protocols` and `/overview/*` families, not the paid "downloads" product |
| CoinGecko (SOL price/market cap/volume) | **No** | Free public API, rate-limited |
| CoinMarketCap | **Yes (optional)** | Fallback only — called when CoinGecko's response is empty; set `CMC_API_KEY` to enable |
| Glassnode (daily active addresses) | **Yes (optional)** | No keyless equivalent exists; set `GLASSNODE_API_KEY` to enable |
| Dune Analytics | **Yes (optional)** | No keyless public API exists; set `DUNE_API_KEY` to enable |
| Twitter / X | **Yes (optional)** | X API v2 requires a bearer token; set `TWITTER_BEARER_TOKEN` to enable |
| solana.com/data | No key, but fragile | Best-effort HTML scrape of a JS-rendered SPA; treated as a bonus, not a primary source. The Foundation's own [solana-data-aggregator](https://github.com/solana-foundation/solana-data-aggregator) repo powers that page but needs its own separate provider keys, so it's cited as methodology rather than used as a shortcut |

Everything runs on the Python standard library — `urllib`, `json`,
`statistics`, `argparse` — no `pip install` needed for the core pipeline.
Secrets go in a git-ignored `.env` file (copy `.env.example`), loaded by a
~15-line stdlib parser in `config.py` — no `python-dotenv` dependency.

## Quick start

```bash
cd solana-pulse

# Optional: add keys for Dune / Twitter / Glassnode / CMC
cp .env.example .env && $EDITOR .env

# See it work end-to-end without hitting the network (bundled sample data):
python3 orchestrator.py --once --mock

# Run one real collection cycle against live sources:
python3 orchestrator.py --once

# Loop forever, refreshing every 5 minutes (Ctrl+C to stop):
python3 orchestrator.py --interval 300
```

Outputs land in `./output/`:
- `dashboard.html` — interactive dark-theme dashboard (open directly in a browser)
- `report.md` — human-readable Markdown report
- `report.json` — full structured data, for feeding into other tools

## Sample outputs

`samples/report.json` and `samples/report.md` are a point-in-time snapshot
I generated and committed directly. They're decoupled from the `output/`
folder, which regenerates on every run and is git-ignored so local test
runs don't pollute the commit history. The live dashboard reflects
real-time data; these two files are a fixed reference copy of what that
data looks like, so there's always a working example in the repo even if
the live version is mid-refresh or a data source is temporarily down.



## Automating it

A long-running `--interval` loop works but can die silently if the process
crashes or the machine reboots. For production use, prefer cron (or
systemd/launchd) calling `--once`:

```cron
*/5 * * * * cd /path/to/solana-pulse && /usr/bin/python3 orchestrator.py --once >> solpulse.log 2>&1
```

Every run appends the current snapshot to `data/history.json` (a rolling
window, default 50 snapshots — see `config.ANOMALY_THRESHOLDS["rolling_history_window"]`),
which is what the anomaly detector compares against.

## What's in each report

- **Network performance** — health, current slot, epoch progress, average
  TPS and slot time derived from `getRecentPerformanceSamples`.
- **Validator status** — active vs. delinquent counts, delinquent stake %,
  top validators by stake with commission, from `getVoteAccounts`.
- **Economic indicators** — SOL price/market cap/24h change (CoinGecko,
  with CMC as a fallback), chain TVL + trend, stablecoin supply, 24h DEX
  volume, and 24h protocol fees as a REV proxy (DeFiLlama) — plus a median
  transaction fee reported honestly as base fee + median priority fee
  (µ-lamports/CU) rather than a single fabricated SOL figure (see
  `fetchers/rpc.py` for why).
- **Ecosystem growth** — daily active addresses (Glassnode, optional) and
  tokenized RWA volume on Solana (DeFiLlama `/protocols`, filtered to
  category=RWA, chain=Solana — free tier, no key).
- **Ecosystem & community** — Twitter/X posts from a configurable
  watchlist (if a bearer token is set) or a manual-check list if not; Dune
  query results (if configured); a best-effort read of solana.com/data.
- **Upcoming upgrades** — a manually-maintained list (`config.ROADMAP_ITEMS`)
  covering items like Alpenglow and SIMD proposals, since there's no single
  machine-readable roadmap feed. Update this list as items ship.
- **Anomaly detection** — flags TPS drops, slow slot times, high
  delinquency, and large TVL/price swings using rolling z-scores plus hard
  thresholds (works from the very first run, before any history exists).

## Configuring it

All tunables live in `config.py`:
- `RPC_ENDPOINTS` — public RPC URL(s), with fallback
- `WATCHED_ADDRESSES` — wallets to track balances/signatures for
- `ANOMALY_THRESHOLDS` — z-score sensitivity, hard floors/ceilings, %-change warn/critical levels
- `DUNE_QUERY_IDS` / `DUNE_API_KEY` — optional Dune integration
- `TWITTER_WATCHLIST` / `TWITTER_BEARER_TOKEN` — optional X integration
- `DEFAULT_REFRESH_INTERVAL_SECONDS`, `OUTPUT_DIR`, `HISTORY_FILE`

## Project layout

```
solana-pulse/
├── config.py                  # all tunables + stdlib .env loader
├── .env.example                # copy to .env, fill in what you have
├── orchestrator.py             # entry point: collect → detect → write
├── anomaly.py                  # rolling-history anomaly detection
├── fetchers/
│   ├── rpc.py                  # Solana JSON-RPC client (stdlib only) + median priority fee
│   ├── defillama.py            # TVL / stablecoins / DEX volume / fees-REV / RWA volume
│   ├── coingecko.py            # SOL price / market cap (primary)
│   ├── cmc.py                  # optional fallback, needs CMC_API_KEY
│   ├── glassnode.py            # optional, needs GLASSNODE_API_KEY — daily active addresses
│   ├── dune.py                 # optional, needs DUNE_API_KEY
│   ├── twitter.py               # optional, needs TWITTER_BEARER_TOKEN
│   └── solana_data_site.py     # best-effort solana.com/data scrape
├── reporters/
│   ├── json_report.py
│   ├── markdown_report.py
│   └── html_report.py          # self-contained, no CDN dependencies
└── data/
    ├── sample_data.json        # for --mock demo runs
    └── history.json            # rolling snapshot history (created at runtime)
```

## Deploying it (live, unattended)

`.github/workflows/solpulse.yml` runs the pipeline every 30 minutes on
GitHub's infrastructure and publishes `output/dashboard.html` to GitHub
Pages — no server, no laptop that has to stay on. One-time setup after
pushing this repo:

1. **Add secrets**: repo Settings → Secrets and variables → Actions → New
   repository secret. Add `DUNE_API_KEY`, `GLASSNODE_API_KEY`, `CMC_API_KEY`
   (and `TWITTER_BEARER_TOKEN` if you have one). Same values as your local
   `.env` — never commit `.env` itself.
2. **Enable Pages**: Settings → Pages → Source → set to the `gh-pages`
   branch (the workflow creates this branch on its first successful run).
3. **Trigger the first run**: Actions tab → SolPulse Refresh → Run workflow
   (don't wait for the schedule). Check it went green, then find your live
   URL at Settings → Pages.

Rolling anomaly detection needs continuity between runs, so the workflow
commits `data/history.json` back to `main` after each cycle — this is
expected and won't loop, since the workflow only triggers on a schedule or
manual dispatch, never on push.

## Extending it

- **More RPC metrics**: `getSignaturesForAddress` and `getBalance` are
  wired up for `WATCHED_ADDRESSES` but unused until you populate that dict
  — handy for tracking a foundation or treasury wallet.
- **Dune-backed REV / DAA precision**: the current REV figure is a
  DeFiLlama fees proxy and DAAs come from Glassnode — if you get real Dune
  query IDs configured (`config.DUNE_QUERY_IDS`), you can cross-check or
  replace either with a purpose-built Dune query.
- **Alerting**: `anomaly.detect()` returns a plain list of dicts — wiring
  it to Slack/Discord/email is a small addition to `orchestrator.py`'s
  `run_once()`.
