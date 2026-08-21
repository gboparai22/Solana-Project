#!/usr/bin/env python3
"""
SolPulse orchestrator — collects data from all sources, runs anomaly
detection, and writes JSON / Markdown / HTML reports.

Usage:
    python3 orchestrator.py --once                # run a single cycle
    python3 orchestrator.py --interval 300         # loop forever, every 5 min
    python3 orchestrator.py --once --mock          # use bundled sample data
                                                    # (useful for demos / when
                                                    # outbound network is
                                                    # restricted, e.g. sandboxes)

Cron alternative to --interval looping (recommended for production, since a
long-lived Python loop can silently die):
    */5 * * * * cd /path/to/solana-pulse && python3 orchestrator.py --once
"""
import argparse
import json
import os
import time
import traceback

import config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
import anomaly
from fetchers import rpc, defillama, coingecko, twitter, solana_data_site, glassnode, cmc
from reporters import json_report, markdown_report, html_report


def collect_report(use_mock=False):
    if use_mock:
        with open(os.path.join(BASE_DIR, "data/sample_data.json")) as f:
            report = json.load(f)
        report["generated_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        report["refresh_interval_seconds"] = config.DEFAULT_REFRESH_INTERVAL_SECONDS
        report["anomalies"] = anomaly.detect(report)
        report["roadmap"] = config.ROADMAP_ITEMS
        return report

    report = {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "refresh_interval_seconds": config.DEFAULT_REFRESH_INTERVAL_SECONDS,
    }

    client = rpc.SolanaRPC()
    for name, fn in [
        ("network", client.network_snapshot),
        ("defillama", defillama.snapshot),
        ("coingecko", coingecko.snapshot),
        ("twitter", twitter.snapshot),
        ("solana_data_site", solana_data_site.snapshot),
        ("glassnode", glassnode.snapshot),
    ]:
        try:
            report[name] = fn()
        except Exception:  # noqa: BLE001 - a single failed source must not kill the run
            report[name] = {"error": traceback.format_exc(limit=2)}

    # CMC is a fallback only: skip the call entirely unless CoinGecko's
    # price came back empty, so we're not burning CMC quota on every run.
    cg = report.get("coingecko", {}) or {}
    if cg.get("price_usd") is None and config.CMC_API_KEY:
        try:
            cmc_data = cmc.snapshot()
            if cmc_data.get("available"):
                report["coingecko"] = {**cg, **{k: v for k, v in cmc_data.items()
                                                 if k not in ("available", "reason", "errors")}}
                report["coingecko"]["source"] = "coinmarketcap (fallback)"
        except Exception:  # noqa: BLE001
            pass

    report["roadmap"] = config.ROADMAP_ITEMS
    report["anomalies"] = anomaly.detect(report)
    return report


def write_reports(report):
    json_path = json_report.write(report, f"{config.OUTPUT_DIR}/report.json")
    md_path = markdown_report.write(report, f"{config.OUTPUT_DIR}/report.md")
    html_path = html_report.write(report, f"{config.OUTPUT_DIR}/dashboard.html")
    return json_path, md_path, html_path


def run_once(use_mock=False):
    report = collect_report(use_mock=use_mock)
    paths = write_reports(report)
    n_anomalies = len(report.get("anomalies", []))
    print(f"[{report['generated_at_utc']}] Report written -> {paths} "
          f"({n_anomalies} anomal{'y' if n_anomalies == 1 else 'ies'})")
    return report


def run_loop(interval_seconds, use_mock=False):
    print(f"SolPulse running every {interval_seconds}s. Ctrl+C to stop.")
    while True:
        try:
            run_once(use_mock=use_mock)
        except Exception:  # noqa: BLE001 - keep the loop alive across transient failures
            traceback.print_exc()
        time.sleep(interval_seconds)


def main():
    parser = argparse.ArgumentParser(description="SolPulse — Solana ecosystem monitor")
    parser.add_argument("--once", action="store_true", help="Run a single collection cycle and exit")
    parser.add_argument("--interval", type=int, default=config.DEFAULT_REFRESH_INTERVAL_SECONDS,
                         help="Seconds between cycles when looping (default: %(default)s)")
    parser.add_argument("--mock", action="store_true",
                         help="Use bundled sample data instead of hitting live network sources")
    args = parser.parse_args()

    if args.once:
        run_once(use_mock=args.mock)
    else:
        run_loop(args.interval, use_mock=args.mock)


if __name__ == "__main__":
    main()
