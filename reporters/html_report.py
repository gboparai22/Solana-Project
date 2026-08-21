"""
Interactive HTML dashboard — single self-contained file, no external
dependencies (all CSS/JS inline, no CDN calls), dark theme.

Design: "mission control for a heartbeat". Solana's own brand colors
(mint #14F195 / purple #9945FF) are used deliberately since the subject
*is* Solana — an EKG-style animated pulse line across the header ties
directly into the "SolPulse" concept (network health = heartbeat).
"""
import json
import os


def _fmt_usd(v):
    if v is None:
        return "—"
    if v >= 1e9:
        return f"${v/1e9:.2f}B"
    if v >= 1e6:
        return f"${v/1e6:.2f}M"
    if v >= 1e3:
        return f"${v/1e3:.1f}K"
    return f"${v:,.2f}"


def _sparkline_points(values, width=260, height=48):
    if not values or len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = width / (len(values) - 1)
    pts = []
    for i, v in enumerate(values):
        x = i * step
        y = height - ((v - lo) / span) * height
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts)


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SolPulse — Solana Ecosystem Report</title>
<style>
  :root {{
    --bg: #0a0d12;
    --bg-panel: #10151d;
    --bg-panel-raised: #151b25;
    --line: #232b38;
    --mint: #14f195;
    --purple: #9945ff;
    --amber: #f5a623;
    --red: #ff5c5c;
    --text: #e6ecf3;
    --text-dim: #8b98ab;
    --font-display: 'Space Grotesk', 'Segoe UI', system-ui, sans-serif;
    --font-body: 'Inter', 'Segoe UI', system-ui, sans-serif;
    --font-mono: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: radial-gradient(ellipse at top, #0d1420 0%, var(--bg) 55%);
    color: var(--text);
    font-family: var(--font-body);
    line-height: 1.5;
    padding-bottom: 60px;
  }}
  a {{ color: var(--mint); text-decoration: none; }}

  .pulse-header {{
    position: relative;
    padding: 28px 32px 20px;
    border-bottom: 1px solid var(--line);
    overflow: hidden;
  }}
  .pulse-header::before {{
    content: "";
    position: absolute; inset: 0;
    background: linear-gradient(90deg, rgba(20,241,149,0.06), rgba(153,69,255,0.06));
    pointer-events: none;
  }}
  .brand-row {{
    display: flex; align-items: baseline; justify-content: space-between;
    flex-wrap: wrap; gap: 12px; position: relative; z-index: 1;
  }}
  .brand {{
    font-family: var(--font-display);
    font-size: 28px; font-weight: 600; letter-spacing: -0.5px;
    background: linear-gradient(90deg, var(--mint), var(--purple));
    -webkit-background-clip: text; background-clip: text; color: transparent;
  }}
  .brand-sub {{ color: var(--text-dim); font-size: 13px; font-family: var(--font-mono); }}
  .timestamp {{ color: var(--text-dim); font-size: 12px; font-family: var(--font-mono); }}

  .ekg-wrap {{ position: relative; height: 64px; margin-top: 18px; z-index: 1; }}
  .ekg-wrap svg {{ width: 100%; height: 100%; display: block; }}
  .ekg-line {{
    fill: none; stroke: url(#pulseGrad); stroke-width: 2.5;
    stroke-dasharray: 1400; stroke-dashoffset: 1400;
    animation: draw 3.2s linear infinite;
    filter: drop-shadow(0 0 6px rgba(153,69,255,0.45)) drop-shadow(0 0 6px rgba(20,241,149,0.45));
  }}
  @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}

  .ticker {{
    display: flex; gap: 28px; flex-wrap: wrap; margin-top: 14px; position: relative; z-index: 1;
  }}
  .ticker-item {{ min-width: 110px; }}
  .ticker-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-dim); }}
  .ticker-value {{ font-family: var(--font-mono); font-size: 20px; font-weight: 600; margin-top: 2px; }}
  .sol-price {{
    font-size: 24px;
    background: linear-gradient(90deg, var(--mint), var(--purple));
    -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
  }}
  .sol-price span {{ -webkit-text-fill-color: initial; background: none; font-size: 14px; }}
  .up {{ color: var(--mint); }}
  .down {{ color: var(--red); }}

  .container {{ max-width: 1240px; margin: 0 auto; padding: 28px 32px; }}

  .alerts {{ margin-bottom: 28px; }}
  .alert {{
    display: flex; align-items: flex-start; gap: 10px;
    padding: 12px 16px; border-radius: 8px; margin-bottom: 8px;
    font-size: 14px; border: 1px solid;
  }}
  .alert.critical {{ background: rgba(255,92,92,0.08); border-color: rgba(255,92,92,0.35); color: #ffb3b3; }}
  .alert.warning {{ background: rgba(245,166,35,0.08); border-color: rgba(245,166,35,0.35); color: #ffd699; }}
  .alert.ok {{ background: rgba(20,241,149,0.08); border-color: rgba(20,241,149,0.35); color: #a8f7d6; }}

  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
  .card {{
    position: relative;
    background: var(--bg-panel); border: 1px solid var(--line); border-radius: 12px;
    padding: 22px 22px 20px;
    overflow: hidden;
  }}
  .card::before {{
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, var(--purple), var(--mint));
    opacity: 0.75;
  }}
  .card h2 {{
    font-family: var(--font-display); font-size: 15px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-dim);
    margin-bottom: 14px; display: flex; align-items: center; gap: 8px;
  }}
  .dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
  .metric-row {{ display: flex; justify-content: space-between; padding: 7px 0; border-bottom: 1px solid var(--line); font-size: 13.5px; }}
  .metric-row:last-child {{ border-bottom: none; }}
  .metric-row .k {{ color: var(--text-dim); }}
  .metric-row .v {{ font-family: var(--font-mono); font-weight: 600; }}

  table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px; }}
  th {{ text-align: left; color: var(--text-dim); font-size: 11px; text-transform: uppercase; padding: 6px 8px; border-bottom: 1px solid var(--line); }}
  td {{ padding: 6px 8px; border-bottom: 1px solid var(--line); font-family: var(--font-mono); }}
  tr:last-child td {{ border-bottom: none; }}

  .bar-track {{ background: var(--line); border-radius: 4px; height: 6px; width: 100%; overflow: hidden; margin-top: 4px; }}
  .bar-fill {{ height: 100%; background: linear-gradient(90deg, var(--mint), var(--purple)); }}

  .sparkline-wrap {{ margin-top: 10px; }}

  .news-item {{ padding: 8px 0; border-bottom: 1px solid var(--line); font-size: 13px; }}
  .news-item:last-child {{ border-bottom: none; }}
  .news-handle {{ color: var(--purple); font-family: var(--font-mono); font-size: 12px; }}

  .badge {{
    display: inline-block; font-size: 10px; padding: 2px 8px; border-radius: 999px;
    background: rgba(139,152,171,0.15); color: var(--text-dim); text-transform: uppercase;
    letter-spacing: 0.05em; margin-left: 6px;
  }}
  .footer {{ text-align: center; color: var(--text-dim); font-size: 12px; margin-top: 40px; font-family: var(--font-mono); }}

  .roadmap-item {{ padding: 10px 0; border-bottom: 1px solid var(--line); }}
  .roadmap-item:last-child {{ border-bottom: none; }}
  .roadmap-name {{ font-family: var(--font-display); font-weight: 600; font-size: 14px; }}
  .roadmap-status {{ font-size: 11px; color: var(--mint); font-family: var(--font-mono); }}
  .roadmap-desc {{ font-size: 13px; color: var(--text-dim); margin-top: 3px; }}
</style>
</head>
<body>

<header class="pulse-header">
  <div class="brand-row">
    <div>
      <div class="brand">SolPulse</div>
      <div class="brand-sub">Autonomous Solana ecosystem monitor</div>
    </div>
    <div class="timestamp">Generated {generated_at} UTC · refresh interval {refresh_interval}s</div>
  </div>
  <div class="ekg-wrap">
    <svg viewBox="0 0 1400 64" preserveAspectRatio="none">
      <defs>
        <linearGradient id="pulseGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#9945ff" />
          <stop offset="100%" stop-color="#14f195" />
        </linearGradient>
      </defs>
      <polyline class="ekg-line" points="0,32 60,32 90,10 120,54 150,32 400,32 430,14 460,50 490,32 800,32 830,8 860,56 890,32 1400,32" />
    </svg>
  </div>
  <div class="ticker">
    <div class="ticker-item">
      <div class="ticker-label">Health</div>
      <div class="ticker-value">{health}</div>
    </div>
    <div class="ticker-item">
      <div class="ticker-label">Current Slot</div>
      <div class="ticker-value">{slot}</div>
    </div>
    <div class="ticker-item">
      <div class="ticker-label">Epoch</div>
      <div class="ticker-value">{epoch}</div>
    </div>
    <div class="ticker-item">
      <div class="ticker-label">Avg TPS</div>
      <div class="ticker-value">{tps}</div>
    </div>
    <div class="ticker-item">
      <div class="ticker-label">Slot Time</div>
      <div class="ticker-value">{slot_time} ms</div>
    </div>
    <div class="ticker-item">
      <div class="ticker-label">SOL Price</div>
      <div class="ticker-value sol-price">${price}<span class="{price_class}"> {price_change}</span></div>
    </div>
    <div class="ticker-item">
      <div class="ticker-label">Chain TVL</div>
      <div class="ticker-value">{tvl}</div>
    </div>
  </div>
</header>

<div class="container">

  <div class="alerts">
    {alerts_html}
  </div>

  <div class="grid">

    <div class="card">
      <h2><span class="dot" style="background:var(--mint)"></span>Network Performance</h2>
      <div class="metric-row"><span class="k">Health</span><span class="v">{health}</span></div>
      <div class="metric-row"><span class="k">Current slot</span><span class="v">{slot}</span></div>
      <div class="metric-row"><span class="k">Block height</span><span class="v">{block_height}</span></div>
      <div class="metric-row"><span class="k">Epoch progress</span><span class="v">{epoch_progress}</span></div>
      <div class="metric-row"><span class="k">Avg TPS (recent)</span><span class="v">{tps}</span></div>
      <div class="metric-row"><span class="k">Latest TPS sample</span><span class="v">{tps_latest}</span></div>
      <div class="metric-row"><span class="k">Avg slot time</span><span class="v">{slot_time} ms</span></div>
    </div>

    <div class="card">
      <h2><span class="dot" style="background:var(--purple)"></span>Validator Status</h2>
      <div class="metric-row"><span class="k">Active validators</span><span class="v">{active_validators}</span></div>
      <div class="metric-row"><span class="k">Delinquent validators</span><span class="v">{delinquent_validators}</span></div>
      <div class="metric-row"><span class="k">Delinquent stake</span><span class="v">{delinquent_pct}%</span></div>
      <table>
        <tr><th>Vote Pubkey</th><th>Stake (SOL)</th><th>Commission</th></tr>
        {validator_rows}
      </table>
    </div>

    <div class="card">
      <h2><span class="dot" style="background:var(--amber)"></span>Economic Indicators</h2>
      <div class="metric-row"><span class="k">SOL price</span><span class="v">${price}</span></div>
      <div class="metric-row"><span class="k">24h change</span><span class="v {price_class}">{price_change}</span></div>
      <div class="metric-row"><span class="k">Market cap</span><span class="v">{market_cap}</span></div>
      <div class="metric-row"><span class="k">24h volume</span><span class="v">{cg_volume}</span></div>
      <div class="metric-row"><span class="k">Chain TVL</span><span class="v">{tvl}</span></div>
      <div class="metric-row"><span class="k">Stablecoin supply</span><span class="v">{stablecoin}</span></div>
      <div class="metric-row"><span class="k">24h DEX volume</span><span class="v">{dex_volume}</span></div>
      <div class="metric-row"><span class="k">24h protocol fees (REV proxy)</span><span class="v">{fees_24h}</span></div>
      <div class="sparkline-wrap">
        <div class="ticker-label" style="margin-bottom:4px;">TVL trend (last {tvl_points} snapshots)</div>
        <svg viewBox="0 0 260 48" width="100%" height="48">
          <polyline points="{tvl_sparkline}" fill="none" stroke="var(--mint)" stroke-width="2" />
        </svg>
      </div>
    </div>

    <div class="card">
      <h2><span class="dot" style="background:var(--purple)"></span>Ecosystem Growth</h2>
      <div class="metric-row"><span class="k">Daily active addresses (Glassnode)</span><span class="v">{daily_active_addresses}</span></div>
      <div class="metric-row"><span class="k">Median priority fee</span><span class="v">{median_priority_fee}</span></div>
      <div class="metric-row"><span class="k">Tokenized RWA volume (Solana)</span><span class="v">{rwa_tvl}</span></div>
      <div class="roadmap-desc" style="margin-top:8px;">RWA figure covers DeFiLlama's broader Real-World-Assets category (treasuries, private credit, real estate) — not verified equities-only, which is what the brief specifically names.</div>
    </div>

    <div class="card">
      <h2><span class="dot" style="background:var(--mint)"></span>Ecosystem &amp; Community</h2>
      {news_html}
    </div>

    <div class="card">
      <h2><span class="dot" style="background:var(--purple)"></span>Upcoming Upgrades</h2>
      {roadmap_html}
    </div>

    <div class="card">
      <h2><span class="dot" style="background:var(--amber)"></span>Data Source Status</h2>
      {source_status_html}
    </div>

  </div>

  <div class="footer">SolPulse · generated automatically · no API keys required for on-chain, DeFiLlama, or CoinGecko data</div>
</div>

</body>
</html>
"""


def _alert_html(a):
    icon = "🔴" if a["severity"] == "critical" else "🟡"
    return f'<div class="alert {a["severity"]}">{icon}&nbsp; <strong>{a["severity"].upper()}</strong>&nbsp; — {a["message"]}</div>'


def render(report):
    net = report.get("network", {}) or {}
    votes = net.get("vote_accounts_summary", {}) or {}
    tvl = report.get("defillama", {}) or {}
    price_data = report.get("coingecko", {}) or {}
    twitter = report.get("twitter", {}) or {}
    site = report.get("solana_data_site", {}) or {}
    glassnode = report.get("glassnode", {}) or {}
    anomalies = report.get("anomalies", [])
    roadmap = report.get("roadmap", [])

    epoch = net.get("epoch_info") or {}
    epoch_progress = "n/a"
    if epoch.get("slotsInEpoch"):
        pct = 100 * epoch.get("slotIndex", 0) / epoch["slotsInEpoch"]
        epoch_progress = f"{pct:.1f}% (epoch {epoch.get('epoch')})"

    change = price_data.get("change_24h_pct")
    price_class = "up" if (change or 0) >= 0 else "down"
    price_change = f"{change:+.2f}%" if change is not None else ""

    alerts_html = (
        "".join(_alert_html(a) for a in anomalies)
        if anomalies
        else '<div class="alert ok">✅&nbsp; No anomalies detected this cycle</div>'
    )

    validator_rows = "".join(
        f"<tr><td>{v['votePubkey'][:12]}…</td><td>{v['activatedStakeSol']:,.0f}</td><td>{v['commission']}%</td></tr>"
        for v in (votes.get("top_validators_by_stake") or [])[:8]
    ) or "<tr><td colspan='3'>No validator data available</td></tr>"

    # news
    news_parts = []
    if twitter.get("available"):
        for user, tweets in twitter.get("accounts", {}).items():
            for t in tweets[:2]:
                news_parts.append(
                    f'<div class="news-item"><span class="news-handle">@{user}</span><br>{t.get("text","")[:160]}</div>'
                )
    else:
        news_parts.append(
            f'<div class="news-item">{twitter.get("reason","Twitter data unavailable.")}</div>'
        )
        for url in twitter.get("watchlist", [])[:5]:
            news_parts.append(f'<div class="news-item"><a href="{url}">{url}</a></div>')
    news_html = "".join(news_parts)

    # roadmap
    roadmap_html = "".join(
        f'<div class="roadmap-item"><span class="roadmap-name">{r["name"]}</span>'
        f'<span class="roadmap-status"> · {r["status"]}</span>'
        f'<div class="roadmap-desc">{r["description"]}</div></div>'
        for r in roadmap
    )

    # data source status
    def status_row(name, ok, note=""):
        color = "var(--mint)" if ok else "var(--text-dim)"
        label = "live" if ok else "unavailable"
        return (f'<div class="metric-row"><span class="k">{name}</span>'
                f'<span class="v" style="color:{color}">{label}</span></div>'
                + (f'<div class="roadmap-desc" style="margin-top:-4px;margin-bottom:6px;">{note}</div>' if note else ""))

    source_status_html = "".join([
        status_row("Solana RPC", not net.get("errors"), "; ".join(net.get("errors", []))[:120]),
        status_row("DeFiLlama", not tvl.get("errors"), "; ".join(tvl.get("errors", []))[:120]),
        status_row("CoinGecko", not price_data.get("errors"), "; ".join(price_data.get("errors", []))[:120]),
        status_row("Twitter / X", twitter.get("available", False), twitter.get("reason", "")),
        status_row("solana.com/data", site.get("available", False), "; ".join(site.get("errors", []))[:120]),
        status_row("Glassnode", glassnode.get("available", False), glassnode.get("reason", "")),
    ])

    tvl_hist = tvl.get("tvl_history") or []
    tvl_values = [h.get("tvl") for h in tvl_hist if h.get("tvl") is not None]
    sparkline_pts = _sparkline_points(tvl_values) if len(tvl_values) >= 2 else "0,24 260,24"

    html = TEMPLATE.format(
        generated_at=report.get("generated_at_utc", ""),
        refresh_interval=report.get("refresh_interval_seconds", "—"),
        health=net.get("health", "n/a"),
        slot=net.get("slot", "n/a"),
        block_height=net.get("block_height", "n/a"),
        epoch=epoch.get("epoch", "n/a"),
        epoch_progress=epoch_progress,
        tps=net.get("tps_avg_recent", "n/a"),
        tps_latest=net.get("tps_latest", "n/a"),
        slot_time=net.get("avg_slot_time_ms", "n/a"),
        active_validators=votes.get("active_validator_count", "n/a"),
        delinquent_validators=votes.get("delinquent_validator_count", "n/a"),
        delinquent_pct=votes.get("delinquent_stake_pct", "n/a"),
        validator_rows=validator_rows,
        price=price_data.get("price_usd", "n/a"),
        price_class=price_class,
        price_change=price_change,
        market_cap=_fmt_usd(price_data.get("market_cap_usd")),
        cg_volume=_fmt_usd(price_data.get("volume_24h_usd")),
        tvl=_fmt_usd(tvl.get("tvl_latest_usd")),
        stablecoin=_fmt_usd(tvl.get("stablecoin_supply_usd")),
        dex_volume=_fmt_usd(tvl.get("dex_volume_24h_usd")),
        fees_24h=_fmt_usd(tvl.get("fees_24h_usd")),
        daily_active_addresses=(
            f"{glassnode.get('daily_active_addresses'):,}"
            if isinstance(glassnode.get("daily_active_addresses"), (int, float))
            else "n/a"
        ),
        median_priority_fee=(
            f"{net.get('median_prioritization_fee_microlamports_per_cu')} µ-lamports/CU"
            if net.get("median_prioritization_fee_microlamports_per_cu") is not None
            else "n/a"
        ),
        rwa_tvl=_fmt_usd(tvl.get("rwa_tvl_usd")),
        tvl_points=len(tvl_values),
        tvl_sparkline=sparkline_pts,
        alerts_html=alerts_html,
        news_html=news_html,
        roadmap_html=roadmap_html,
        source_status_html=source_status_html,
    )
    return html


def write(report, out_path):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    html = render(report)
    with open(out_path, "w") as f:
        f.write(html)
    return out_path
