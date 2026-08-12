"""Human-readable Markdown report."""
import os


def _fmt_usd(v):
    if v is None:
        return "n/a"
    if v >= 1e9:
        return f"${v/1e9:.2f}B"
    if v >= 1e6:
        return f"${v/1e6:.2f}M"
    return f"${v:,.2f}"


def _fmt_pct(v):
    return "n/a" if v is None else f"{v:+.2f}%"


def render(report):
    net = report.get("network", {}) or {}
    votes = net.get("vote_accounts_summary", {}) or {}
    tvl = report.get("defillama", {}) or {}
    price = report.get("coingecko", {}) or {}
    dune = report.get("dune", {}) or {}
    twitter = report.get("twitter", {}) or {}
    site = report.get("solana_data_site", {}) or {}
    anomalies = report.get("anomalies", [])
    roadmap = report.get("roadmap", [])

    lines = []
    lines.append(f"# SolPulse — Solana Ecosystem Report")
    lines.append(f"_Generated {report.get('generated_at_utc')} UTC_\n")

    # --- Anomalies up top so they're impossible to miss ---
    if anomalies:
        lines.append("## ⚠️ Anomalies Detected")
        for a in anomalies:
            icon = "🔴" if a["severity"] == "critical" else "🟡"
            lines.append(f"- {icon} **[{a['severity'].upper()}]** {a['message']}")
        lines.append("")
    else:
        lines.append("## ✅ No anomalies detected this cycle\n")

    # --- Network performance ---
    lines.append("## Network Performance")
    lines.append(f"- Health: `{net.get('health')}`")
    lines.append(f"- Current slot: `{net.get('slot')}`")
    lines.append(f"- Block height: `{net.get('block_height')}`")
    epoch = net.get("epoch_info") or {}
    if epoch:
        progress = None
        if epoch.get("slotsInEpoch"):
            progress = 100 * epoch.get("slotIndex", 0) / epoch["slotsInEpoch"]
        lines.append(f"- Epoch: `{epoch.get('epoch')}` "
                     f"({progress:.1f}% complete)" if progress is not None else
                     f"- Epoch: `{epoch.get('epoch')}`")
    lines.append(f"- Avg TPS (recent samples): **{net.get('tps_avg_recent', 'n/a')}**")
    lines.append(f"- Latest TPS sample: **{net.get('tps_latest', 'n/a')}**")
    lines.append(f"- Avg slot time: **{net.get('avg_slot_time_ms', 'n/a')} ms**")
    if net.get("median_prioritization_fee_microlamports_per_cu") is not None:
        lines.append(f"- Base fee: **{net.get('base_fee_lamports_per_signature')} lamports/signature** "
                     f"+ median priority fee: **{net.get('median_prioritization_fee_microlamports_per_cu')} "
                     f"micro-lamports/CU** _(not collapsed into one SOL figure — see README)_")
    if net.get("errors"):
        lines.append(f"- ⚠️ Partial data — errors: {'; '.join(net['errors'])}")
    lines.append("")

    # --- Validators ---
    lines.append("## Validator Status")
    lines.append(f"- Active validators: **{votes.get('active_validator_count', 'n/a')}**")
    lines.append(f"- Delinquent validators: **{votes.get('delinquent_validator_count', 'n/a')}**")
    lines.append(f"- Delinquent stake: **{votes.get('delinquent_stake_pct', 'n/a')}%**")
    top = votes.get("top_validators_by_stake") or []
    if top:
        lines.append("\n| Rank | Vote Pubkey | Stake (SOL) | Commission % |")
        lines.append("|---|---|---|---|")
        for i, v in enumerate(top[:10], 1):
            lines.append(
                f"| {i} | `{v['votePubkey'][:10]}…` | {v['activatedStakeSol']:,.0f} | {v['commission']} |"
            )
    lines.append("")

    # --- Economic indicators ---
    lines.append("## Economic Indicators")
    lines.append(f"- SOL price: **${price.get('price_usd', 'n/a')}** "
                 f"(24h {_fmt_pct(price.get('change_24h_pct'))})")
    lines.append(f"- Market cap: **{_fmt_usd(price.get('market_cap_usd'))}**")
    lines.append(f"- 24h volume: **{_fmt_usd(price.get('volume_24h_usd'))}**")
    lines.append(f"- Chain TVL: **{_fmt_usd(tvl.get('tvl_latest_usd'))}**")
    lines.append(f"- Stablecoin supply on Solana: **{_fmt_usd(tvl.get('stablecoin_supply_usd'))}**")
    lines.append(f"- 24h DEX volume: **{_fmt_usd(tvl.get('dex_volume_24h_usd'))}**")
    if tvl.get("fees_24h_usd") is not None:
        lines.append(f"- 24h protocol fees: **{_fmt_usd(tvl.get('fees_24h_usd'))}** "
                     f"_(REV proxy — fees only, not fees + priority fees + issuance)_")
    lines.append("")

    # --- Ecosystem growth ---
    glassnode = report.get("glassnode", {}) or {}
    lines.append("## Ecosystem Growth")
    if glassnode.get("available"):
        lines.append(f"- Daily active addresses (Glassnode): **{glassnode.get('daily_active_addresses'):,}**"
                     if isinstance(glassnode.get("daily_active_addresses"), (int, float))
                     else f"- Daily active addresses (Glassnode): **{glassnode.get('daily_active_addresses')}**")
    else:
        lines.append(f"- Daily active addresses (Glassnode): _{glassnode.get('reason', 'unavailable')}_")
    if dune.get("available"):
        daa_dune = dune.get("results", {}).get("daily_active_addresses", {})
        dex_dune = dune.get("results", {}).get("dex_daily_active_users", {})
        if daa_dune.get("rows"):
            lines.append(f"- Daily active addresses (Dune, cross-check): {len(daa_dune['rows'])} rows returned "
                         f"— see report.json for raw figures (executed {daa_dune.get('executed_at')})")
        if dex_dune.get("rows"):
            lines.append(f"- DEX daily active users (Dune): {len(dex_dune['rows'])} rows returned "
                         f"— see report.json for raw figures (executed {dex_dune.get('executed_at')})")
    if tvl.get("rwa_tvl_usd") is not None:
        lines.append(f"- Tokenized RWA volume on Solana: **{_fmt_usd(tvl.get('rwa_tvl_usd'))}** "
                     f"across {tvl.get('rwa_protocol_count', 0)} protocol(s) "
                     f"_(DeFiLlama's broader RWA category — not verified equities-only)_")
        for p in (tvl.get("rwa_top_protocols") or [])[:5]:
            lines.append(f"  - {p['name']}: {_fmt_usd(p['tvl_usd'])}")
    lines.append("")

    # --- Ecosystem / community news ---
    lines.append("## Ecosystem & Community")
    if twitter.get("available"):
        for user, tweets in twitter.get("accounts", {}).items():
            lines.append(f"**@{user}**")
            for t in tweets[:3]:
                lines.append(f"  - {t.get('text', '')[:180]}")
    else:
        lines.append(f"_{twitter.get('reason', 'Twitter data unavailable.')}_")
        for url in twitter.get("watchlist", []):
            lines.append(f"  - {url}")
    lines.append("")

    if dune.get("available"):
        lines.append("**Dune Analytics**")
        for label, res in dune.get("results", {}).items():
            lines.append(f"  - `{label}`: {len(res.get('rows', []))} rows (executed {res.get('executed_at')})")
    else:
        lines.append(f"_Dune Analytics: {dune.get('reason', 'unavailable')}_")
    lines.append("")

    if site.get("available"):
        lines.append(f"_solana.com/data: page sections found — {site.get('extracted', {}).get('props_keys')}_")
    else:
        lines.append(f"_solana.com/data: {'; '.join(site.get('errors', ['unavailable']))}_")
    lines.append("")

    # --- Roadmap ---
    lines.append("## Upcoming Upgrades & Developments")
    for item in roadmap:
        lines.append(f"- **{item['name']}** ({item['status']}): {item['description']}")
    lines.append("")

    lines.append("---")
    lines.append("_SolPulse — autonomous Solana ecosystem monitor. "
                 "See README.md for data source notes and setup for optional Dune/Twitter keys._")

    return "\n".join(lines)


def write(report, out_path):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    content = render(report)
    with open(out_path, "w") as f:
        f.write(content)
    return out_path
