"""
Direct Solana JSON-RPC client using only the Python standard library.
No API key, no third-party SDK — talks straight to a public RPC endpoint.
"""
import json
import time
import urllib.request
import urllib.error

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class RPCError(Exception):
    pass


def _post(endpoint, method, params=None):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or [],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT_SECONDS) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if "error" in body:
        raise RPCError(f"{method} -> {body['error']}")
    return body.get("result")


def call(method, params=None):
    """Try each configured endpoint in order until one succeeds."""
    last_err = None
    for endpoint in config.RPC_ENDPOINTS:
        try:
            return _post(endpoint, method, params)
        except (urllib.error.URLError, RPCError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            continue
    raise RPCError(f"All RPC endpoints failed for {method}: {last_err}")


class SolanaRPC:
    """Thin wrapper around the RPC methods SolPulse cares about."""

    def get_health(self):
        try:
            return call("getHealth")
        except RPCError as e:
            return f"unhealthy ({e})"

    def get_slot(self):
        return call("getSlot")

    def get_block_height(self):
        """
        Distinct from slot: slot advances on every tick, block height only
        counts slots that actually produced a block. The brief asks for
        both as separate network-performance metrics.
        """
        return call("getBlockHeight")

    def get_block_time(self, slot):
        return call("getBlockTime", [slot])

    def get_epoch_info(self):
        return call("getEpochInfo")

    def get_recent_performance_samples(self, limit=None):
        limit = limit or config.PERFORMANCE_SAMPLE_LIMIT
        return call("getRecentPerformanceSamples", [limit])

    def get_vote_accounts(self):
        return call("getVoteAccounts")

    def get_balance(self, address):
        result = call("getBalance", [address])
        # lamports -> SOL
        if isinstance(result, dict) and "value" in result:
            return result["value"] / 1_000_000_000
        return result

    def get_signatures_for_address(self, address, limit=10):
        return call("getSignaturesForAddress", [address, {"limit": limit}])

    def get_supply(self):
        return call("getSupply")

    def get_recent_prioritization_fees(self, addresses=None):
        """
        getRecentPrioritizationFees needs no key and no third-party source —
        it's the cleanest keyless path to a "median transaction fee" figure
        for the brief's economic-indicators section. Passing no addresses
        returns a general recent sample across the network.
        """
        return call("getRecentPrioritizationFees", [addresses or []])

    # -- Derived / aggregate metrics -------------------------------------

    def network_snapshot(self):
        """
        One consolidated read of network health & performance.
        Each field is fetched independently and defaults to None on failure
        so a single flaky call doesn't take down the whole snapshot.
        """
        snap = {
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "health": None,
            "slot": None,
            "epoch_info": None,
            "performance": None,
            "vote_accounts_summary": None,
            "supply": None,
            "watched_balances": {},
            "errors": [],
        }

        for field, fn in [
            ("health", self.get_health),
            ("slot", self.get_slot),
            ("block_height", self.get_block_height),
            ("epoch_info", self.get_epoch_info),
            ("performance", lambda: self.get_recent_performance_samples()),
            ("supply", self.get_supply),
        ]:
            try:
                snap[field] = fn()
            except Exception as e:  # noqa: BLE001 - we want to keep going regardless of cause
                snap["errors"].append(f"{field}: {e}")

        # Vote accounts -> compact summary (avoid dumping thousands of validators)
        try:
            va = self.get_vote_accounts()
            current = va.get("current", [])
            delinquent = va.get("delinquent", [])
            total_stake = sum(v.get("activatedStake", 0) for v in current + delinquent)
            delinquent_stake = sum(v.get("activatedStake", 0) for v in delinquent)
            top = sorted(current, key=lambda v: v.get("activatedStake", 0), reverse=True)
            top = top[: config.VOTE_ACCOUNT_TOP_N]
            snap["vote_accounts_summary"] = {
                "active_validator_count": len(current),
                "delinquent_validator_count": len(delinquent),
                "total_activated_stake_lamports": total_stake,
                "delinquent_stake_pct": (
                    round(100 * delinquent_stake / total_stake, 3) if total_stake else None
                ),
                "top_validators_by_stake": [
                    {
                        "votePubkey": v.get("votePubkey"),
                        "nodePubkey": v.get("nodePubkey"),
                        "activatedStakeSol": round(v.get("activatedStake", 0) / 1e9, 2),
                        "commission": v.get("commission"),
                        "epochCredits_last": (v.get("epochCredits") or [[None, None, None]])[-1],
                    }
                    for v in top
                ],
            }
        except Exception as e:  # noqa: BLE001
            snap["errors"].append(f"vote_accounts: {e}")

        # Median transaction fee, keyless, straight from RPC. Note this is
        # deliberately NOT collapsed into a single "fee in SOL" number: the
        # base fee (5000 lamports/signature, a documented network constant)
        # is fixed, but converting the priority-fee component into SOL needs
        # an assumed compute-unit count per tx, which RPC doesn't give you.
        # Reporting both pieces honestly beats fabricating false precision.
        try:
            fee_samples = self.get_recent_prioritization_fees()
            fees = [f["prioritizationFee"] for f in fee_samples if "prioritizationFee" in f]
            if fees:
                fees.sort()
                mid = len(fees) // 2
                median_fee = fees[mid] if len(fees) % 2 else (fees[mid - 1] + fees[mid]) / 2
                snap["median_prioritization_fee_microlamports_per_cu"] = median_fee
                snap["base_fee_lamports_per_signature"] = 5000  # documented network constant
        except Exception as e:  # noqa: BLE001
            snap["errors"].append(f"prioritization_fees: {e}")

        # Watched wallet balances (only if configured)
        for label, address in config.WATCHED_ADDRESSES.items():
            try:
                snap["watched_balances"][label] = self.get_balance(address)
            except Exception as e:  # noqa: BLE001
                snap["errors"].append(f"balance:{label}: {e}")

        # TPS estimate from performance samples
        perf = snap.get("performance") or []
        if perf:
            samples = [
                p["numTransactions"] / p["samplePeriodSecs"]
                for p in perf
                if p.get("samplePeriodSecs")
            ]
            if samples:
                snap["tps_avg_recent"] = round(sum(samples) / len(samples), 1)
                snap["tps_latest"] = round(samples[0], 1)
            avg_slot_time_ms = None
            slot_time_samples = [
                (p["samplePeriodSecs"] / p["numSlots"]) * 1000
                for p in perf
                if p.get("numSlots")
            ]
            if slot_time_samples:
                avg_slot_time_ms = round(sum(slot_time_samples) / len(slot_time_samples), 1)
            snap["avg_slot_time_ms"] = avg_slot_time_ms

        return snap
