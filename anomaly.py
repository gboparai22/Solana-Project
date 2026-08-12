"""
Lightweight anomaly detection — stdlib only (uses `statistics`).

Approach:
  * Keep a rolling window of past snapshots (config.ANOMALY_THRESHOLDS['rolling_history_window'])
    in data/history.json.
  * For metrics with enough history, flag values with |z-score| above a threshold.
  * For a few critical metrics, also apply hard floors/ceilings regardless of
    history (e.g. TPS below 500 is worth flagging even on day one, before any
    rolling baseline exists).
  * Percent-change checks (TVL, price) compare the latest two snapshots directly.
"""
import json
import os
import statistics

import config


def _load_history():
    if not os.path.exists(config.HISTORY_FILE):
        return []
    try:
        with open(config.HISTORY_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_history(history):
    os.makedirs(os.path.dirname(config.HISTORY_FILE) or ".", exist_ok=True)
    with open(config.HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def _zscore(value, series):
    if len(series) < 5 or value is None:
        return None
    mean = statistics.mean(series)
    try:
        stdev = statistics.stdev(series)
    except statistics.StatisticsError:
        return None
    if stdev == 0:
        return None
    return (value - mean) / stdev


def _extract_metrics(report):
    """Pull the flat set of numbers we track over time out of a full report dict."""
    net = report.get("network", {}) or {}
    votes = net.get("vote_accounts_summary", {}) or {}
    tvl = report.get("defillama", {}) or {}
    price = report.get("coingecko", {}) or {}

    return {
        "tps_avg_recent": net.get("tps_avg_recent"),
        "avg_slot_time_ms": net.get("avg_slot_time_ms"),
        "delinquent_stake_pct": votes.get("delinquent_stake_pct"),
        "tvl_latest_usd": tvl.get("tvl_latest_usd"),
        "price_usd": price.get("price_usd"),
    }


def detect(report):
    """
    Given the freshly-collected report dict, compare against rolling history
    and return a list of anomaly dicts: {metric, severity, message, value}.
    """
    th = config.ANOMALY_THRESHOLDS
    history = _load_history()
    current = _extract_metrics(report)
    anomalies = []

    # --- z-score based checks against rolling history ---
    for metric in ("tps_avg_recent", "avg_slot_time_ms", "delinquent_stake_pct"):
        series = [h[metric] for h in history if h.get(metric) is not None]
        z = _zscore(current[metric], series)
        if z is not None:
            if metric == "tps_avg_recent" and z <= -th["tps_zscore"]:
                anomalies.append({
                    "metric": metric, "severity": "warning",
                    "message": f"TPS ({current[metric]}) is {abs(z):.1f} std-devs below its recent average.",
                    "value": current[metric],
                })
            elif metric == "avg_slot_time_ms" and z >= th["tps_zscore"]:
                anomalies.append({
                    "metric": metric, "severity": "warning",
                    "message": f"Slot time ({current[metric]}ms) is {z:.1f} std-devs above its recent average.",
                    "value": current[metric],
                })
            elif metric == "delinquent_stake_pct" and z >= th["tps_zscore"]:
                anomalies.append({
                    "metric": metric, "severity": "warning",
                    "message": f"Delinquent stake ({current[metric]}%) is {z:.1f} std-devs above its recent average.",
                    "value": current[metric],
                })

    # --- hard floor/ceiling checks (work even without history) ---
    if current["tps_avg_recent"] is not None and current["tps_avg_recent"] < th["tps_min_hard_floor"]:
        anomalies.append({
            "metric": "tps_avg_recent", "severity": "critical",
            "message": f"TPS ({current['tps_avg_recent']}) is below the hard floor of {th['tps_min_hard_floor']}.",
            "value": current["tps_avg_recent"],
        })

    slot_ms = current["avg_slot_time_ms"]
    if slot_ms is not None:
        if slot_ms >= th["slot_time_ms_critical"]:
            anomalies.append({
                "metric": "avg_slot_time_ms", "severity": "critical",
                "message": f"Average slot time ({slot_ms}ms) exceeds critical threshold ({th['slot_time_ms_critical']}ms).",
                "value": slot_ms,
            })
        elif slot_ms >= th["slot_time_ms_warn"]:
            anomalies.append({
                "metric": "avg_slot_time_ms", "severity": "warning",
                "message": f"Average slot time ({slot_ms}ms) exceeds warning threshold ({th['slot_time_ms_warn']}ms).",
                "value": slot_ms,
            })

    delinq = current["delinquent_stake_pct"]
    if delinq is not None:
        if delinq >= th["delinquent_stake_pct_critical"]:
            anomalies.append({
                "metric": "delinquent_stake_pct", "severity": "critical",
                "message": f"Delinquent stake ({delinq}%) exceeds critical threshold ({th['delinquent_stake_pct_critical']}%).",
                "value": delinq,
            })
        elif delinq >= th["delinquent_stake_pct_warn"]:
            anomalies.append({
                "metric": "delinquent_stake_pct", "severity": "warning",
                "message": f"Delinquent stake ({delinq}%) exceeds warning threshold ({th['delinquent_stake_pct_warn']}%).",
                "value": delinq,
            })

    # --- pct-change checks vs. the immediately previous snapshot ---
    if history:
        prev = history[-1]
        for metric, warn_key, crit_key, label in [
            ("tvl_latest_usd", "tvl_pct_change_warn", "tvl_pct_change_critical", "TVL"),
            ("price_usd", "price_pct_change_warn", "price_pct_change_critical", "SOL price"),
        ]:
            prev_val = prev.get(metric)
            cur_val = current.get(metric)
            if prev_val and cur_val:
                pct = 100 * (cur_val - prev_val) / prev_val
                if abs(pct) >= th[crit_key]:
                    anomalies.append({
                        "metric": metric, "severity": "critical",
                        "message": f"{label} moved {pct:+.1f}% since the last snapshot (critical threshold {th[crit_key]}%).",
                        "value": cur_val,
                    })
                elif abs(pct) >= th[warn_key]:
                    anomalies.append({
                        "metric": metric, "severity": "warning",
                        "message": f"{label} moved {pct:+.1f}% since the last snapshot (warning threshold {th[warn_key]}%).",
                        "value": cur_val,
                    })

    # --- persist this snapshot into rolling history ---
    history.append(current)
    history = history[-th["rolling_history_window"]:]
    _save_history(history)

    return anomalies
