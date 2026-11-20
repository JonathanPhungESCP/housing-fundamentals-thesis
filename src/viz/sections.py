"""Static page sections built from data/processed: the quality-adjusted price index chart
(with the official index and sales volume) and the verdict table. Rendered server-side as
SVG and HTML; site/assets/sections.js adds the hover read-out."""
from __future__ import annotations

import json
import math

import pandas as pd

from src.config import PROCESSED

OFFICIAL = {"paris": "Notaires-INSEE index, existing apartments, Paris",
            "singapore": "HDB resale price index",
            "singapore_private": "URA price index, non-landed private homes"}
MARKET = {"paris": "Paris (existing apartments)", "singapore": "Singapore HDB resale",
          "singapore_private": "Singapore private (non-landed)"}
SERIES = [("hedonic_rolling", "Hedonic index (this project)", "var(--series-market)", ""),
          ("stratified", "Stratified median (this project)", "var(--series-strat)", ""),
          ("official", None, "var(--series-official)", "6 4")]
SIGNAL = {1: "points to a deviation (prices above)", 0: "no deviation signal",
          -1: "points the other way (prices below)"}


def _ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    step = 10 ** math.floor(math.log10((hi - lo) / n))
    for m in (1, 2, 2.5, 5, 10):
        if (hi - lo) / (step * m) <= n:
            step *= m
            break
    t0 = math.ceil(lo / step) * step
    return [round(t0 + k * step, 6) for k in range(int((hi - t0) / step) + 1)]


def _num(v, d=1):
    return "–" if v is None or pd.isna(v) else f"{v:,.{d}f}"


def index_section(city: str) -> str:
    f = PROCESSED / f"index_{city}.csv"
    if not f.exists():
        return ""
    d = pd.read_csv(f)
    if "official" not in d:
        d["official"] = float("nan")
    if d["n"].iloc[-1] < 0.6 * d["n"].median():  # running quarter: incomplete, not drawn
        d = d.iloc[:-1]
    d = d.reset_index(drop=True)
    N = len(d)
    W, H, HV = 920, 300, 120
    m = {"l": 52, "r": 16, "t": 14, "b": 26}
    X = lambda i: m["l"] + (i + 0.5) * (W - m["l"] - m["r"]) / N  # noqa: E731
    keys = [k for k, *_ in SERIES if d[k].notna().any()]
    vals = pd.concat([d[k] for k in keys]).dropna()
    ticks = _ticks(vals.min() - 1, vals.max() + 1)
    if len(ticks) > 1 and ticks[-1] < vals.max():  # close the scale above the highest value
        ticks.append(ticks[-1] + (ticks[1] - ticks[0]))
    lo, hi = min(ticks[0], vals.min() - 1), max(ticks[-1], vals.max() + 1)
    Y = lambda v: H - m["b"] - (v - lo) / (hi - lo) * (H - m["t"] - m["b"])  # noqa: E731
    g = [f'<line x1="{m["l"]}" x2="{W - m["r"]}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" stroke="var(--grid)"/>'
         f'<text x="{m["l"] - 8}" y="{Y(t) + 4:.1f}" text-anchor="end">{t:g}</text>' for t in ticks]
    if lo <= 100 <= hi:
        g.append(f'<line x1="{m["l"]}" x2="{W - m["r"]}" y1="{Y(100):.1f}" y2="{Y(100):.1f}" stroke="var(--axis)"/>')
    for i, p in enumerate(d["period"]):
        if p.endswith("Q1"):
            g.append(f'<text x="{X(i):.1f}" y="{H - 8}" text-anchor="middle">{p[:4]}</text>')
    for k, _, color, dash in SERIES:
        if k not in keys:
            continue
        pts = [(X(i), Y(v)) for i, v in enumerate(d[k]) if pd.notna(v)]
        path = "".join(f'{"L" if j else "M"}{x:.1f},{y:.1f}' for j, (x, y) in enumerate(pts))
        g.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2"'
                 + (f' stroke-dasharray="{dash}"' if dash else "") + "/>")
    g.append(f'<line class="xh" y1="{m["t"]}" y2="{H - m["b"]}" stroke="var(--axis)" stroke-dasharray="3 3" visibility="hidden"/>')
    g.append(f'<rect class="hit" x="{m["l"]}" y="{m["t"]}" width="{W - m["l"] - m["r"]}" height="{H - m["t"] - m["b"]}" fill="transparent"/>')
    price_svg = (f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="Quality-adjusted price indices and '
                 f'the official index, by quarter, first quarter = 100">{"".join(g)}</svg>')

    vmax = d["n"].max()
    vt = _ticks(0, vmax, 3)
    YV = lambda v: HV - m["b"] - v / max(vt[-1], vmax) * (HV - m["t"] - m["b"])  # noqa: E731
    bw = (W - m["l"] - m["r"]) / N - 2
    b = [f'<line x1="{m["l"]}" x2="{W - m["r"]}" y1="{YV(t):.1f}" y2="{YV(t):.1f}" stroke="var(--grid)"/>'
         f'<text x="{m["l"] - 8}" y="{YV(t) + 4:.1f}" text-anchor="end">{t:,.0f}</text>' for t in vt]
    for i, n in enumerate(d["n"]):
        h = YV(0) - YV(n)
        r = min(3, h / 2, bw / 2)
        x0, y0 = X(i) - bw / 2, YV(n)
        b.append(f'<path d="M{x0:.1f},{YV(0):.1f}V{y0 + r:.1f}Q{x0:.1f},{y0:.1f} {x0 + r:.1f},{y0:.1f}H{x0 + bw - r:.1f}'
                 f'Q{x0 + bw:.1f},{y0:.1f} {x0 + bw:.1f},{y0 + r:.1f}V{YV(0):.1f}Z" fill="var(--series-volume)"/>')
    for i, p in enumerate(d["period"]):
        if p.endswith("Q1"):
            b.append(f'<text x="{X(i):.1f}" y="{HV - 8}" text-anchor="middle">{p[:4]}</text>')
    b.append(f'<line class="xh" y1="{m["t"]}" y2="{HV - m["b"]}" stroke="var(--axis)" stroke-dasharray="3 3" visibility="hidden"/>')
    b.append(f'<rect class="hit" x="{m["l"]}" y="{m["t"]}" width="{W - m["l"] - m["r"]}" height="{HV - m["t"] - m["b"]}" fill="transparent"/>')
    vol_svg = (f'<svg class="chart" viewBox="0 0 {W} {HV}" role="img" aria-label="Number of retained sales per quarter">'
               f'{"".join(b)}</svg>')

    labels = {k: (OFFICIAL[city] if lab is None else lab) for k, lab, *_ in SERIES}
    def swatch(color: str, dash: str) -> str:
        da = f' stroke-dasharray="{dash}"' if dash else ""
        return (f'<svg width="26" height="10" aria-hidden="true"><line x1="1" x2="25" y1="5" y2="5" '
                f'stroke="{color}" stroke-width="2"{da}/></svg>')

    legend = "".join(f"<span>{swatch(c, dash)} {labels[k]}</span>" for k, _, c, dash in SERIES if k in keys)
    data = {"W": W, "l": m["l"], "r": m["r"], "periods": list(d["period"]),
            "series": [{"label": labels[k], "color": c, "values": [None if pd.isna(v) else round(v, 1) for v in d[k]]}
                       for k, _, c, _ in SERIES if k in keys],
            "n": [int(v) for v in d["n"]]}
    rs_kind = json.loads((PROCESSED / f"index_meta_{city}.json").read_text()).get("repeat_sales_kind", "repeat-sales")
    rows = "".join(
        f'<tr><td>{r.period}</td><td class="num">{r.n:,}</td><td class="num">{_num(r.hedonic_rolling)}</td>'
        f'<td class="num">{_num(r.stratified)}</td><td class="num">{_num(r.repeat_sales)}</td>'
        f'<td class="num">{_num(r.official)}</td></tr>' for r in d.itertuples())
    val = ""
    vf = PROCESSED / f"index_validation_{city}.csv"
    if vf.exists():
        v = pd.read_csv(vf).set_index("index")
        h, s = v.loc["hedonic_rolling"], v.loc["stratified"]
        val = (f'<p class="note">Check against the official index, {h["first"]} to {h["last"]}: hedonic '
               f'{h["cum_change_pct"]:+.1f}%, stratified median {s["cum_change_pct"]:+.1f}%, official '
               f'{h["official_cum_change_pct"]:+.1f}%. Correlation of quarterly changes with the official index: '
               f'{h["corr_quarterly_changes"]:.2f} (hedonic), {s["corr_quarterly_changes"]:.2f} (stratified). '
               f'Differences are reported, not adjusted away.</p>')
    return f"""
<h2>Price index, quality-adjusted</h2>
<div class="card">
  <p class="note" style="margin-top:0">A raw median moves with <em>which</em> homes happen to sell. These indices hold the mix
  constant: the hedonic index controls for size, type, location and age or lease; the stratified median fixes the weight of
  each segment. First quarter shown = 100.</p>
  <div class="legend">{legend}</div>
  <div class="chart-wrap schart" data-kind="index">{price_svg}{vol_svg}
  <script type="application/json">{json.dumps(data)}</script></div>
  <div class="legend"><span><span class="sw" style="background:var(--series-volume)"></span> Lower panel: number of retained
  sales per quarter. Falling volumes while prices hold is a classic sign of a stuck market.</span></div>
  {val}
  <details><summary>Table view</summary><div class="table-scroll"><table><thead><tr><th>Quarter</th><th class="num">Sales</th>
  <th class="num">Hedonic</th><th class="num">Stratified median</th><th class="num">{rs_kind.capitalize()}</th>
  <th class="num">Official</th></tr></thead><tbody>{rows}</tbody></table></div>
  <p class="meta-line">The {rs_kind} index is listed for completeness and is not drawn: see the limits on the method page.</p></details>
</div>"""


def _anchor_rows(city: str, v: pd.Series, ratios: pd.DataFrame, expl: pd.DataFrame) -> list[tuple[str, str, object]]:
    def ratio(label, what):
        r = ratios[ratios["series"] == label]
        if r.empty:
            return None
        r = r.iloc[0]
        return (f'{what}: {r["last_vs_mean_pct"]:+.0f}% against its {str(r["first"])[:4]}–{str(r["last"])[:4]} average, '
                f'{r["last_vs_max_pct"]:.0f}% against its peak ({r["period_of_max"]})')

    e = expl[expl["series"] == f"{city}_price"]
    ex = "not run" if e.empty else (
        f'official index {e.iloc[0]["first"]} to {e.iloc[0]["last"]}; explosive episodes: {e.iloc[0]["episodes"]}')
    pr = {"paris": ratio("paris_price_to_national_rent", "Paris price index over the national rent index"),
          "singapore": None,
          "singapore_private": ratio("singapore_private_price_to_rent", "URA price index over URA rental index")}[city]
    pi = ratio({"paris": "paris_price_to_national_income"}.get(city, f"{city}_price_to_income"),
               "official price index over " + ("national disposable income per head" if city == "paris"
                                                else "national median household income from work"))
    return [("Rent capitalisation (user cost)",
             f'valuation gap positive in {100 * v["user_cost_share_gap_positive"]:.0f}% of the sensitivity grid, '
             f'{int(v["valuation_year"])}', v["signal_user_cost"]),
            ("Explosive price dynamics (GSADF)", ex, v["signal_explosive"]),
            ("Price-to-rent against its history",
             pr or ("not run: no long rent index for this market" if pd.isna(v["signal_price_rent"])
                    else "latest ratio compared with its own history"), v["signal_price_rent"]),
            ("Price-to-income against its history", pi or "not run", v["signal_affordability"])]


def _load():
    v = pd.read_csv(PROCESSED / "verdict.csv").set_index("city")
    return v, pd.read_csv(PROCESSED / "ratio_history.csv"), pd.read_csv(PROCESSED / "explosive_summary.csv")


def verdict_section(city: str) -> str:
    if not (PROCESSED / "verdict.csv").exists():
        return ""
    v, ratios, expl = _load()
    if city not in v.index:
        return ""
    rows = "".join(f"<tr><td>{a}</td><td>{txt}</td><td>{'Not run' if pd.isna(s) else SIGNAL[int(s)].capitalize()}</td></tr>"
                   for a, txt, s in _anchor_rows(city, v.loc[city], ratios, expl))
    n_up = sum(1 for *_, s in _anchor_rows(city, v.loc[city], ratios, expl) if s == 1)
    n_run = sum(1 for *_, s in _anchor_rows(city, v.loc[city], ratios, expl) if not pd.isna(s))
    return f"""
<h2>Are prices justified by fundamentals? The evidence so far</h2>
<div class="card">
  <div class="kpis"><div class="kpi"><div class="v">{v.loc[city, "verdict"].capitalize()}</div>
  <div class="k">Verdict under a rule fixed before the results</div>
  <div class="n">{n_up} of {n_run} anchors point to a deviation; three are required, one of them not based on rents</div></div></div>
  <div class="table-scroll"><table><thead><tr><th>Anchor</th><th>What the data show</th><th>Reading</th></tr></thead>
  <tbody>{rows}</tbody></table></div>
  <p class="note">No single anchor is decisive: rent capitalisation changes sign with the interest rate, ratios are judged
  against their own history only, and the explosive-root test dates episodes on a nominal city-level index. The rule and
  the limits of each anchor are on the <a href="methodology.html">method page</a>. Model-dependent hypotheses, not investment advice.</p>
</div>"""


def home_section() -> str:
    if not (PROCESSED / "verdict.csv").exists():
        return ""
    v, ratios, expl = _load()
    cities = [c for c in MARKET if c in v.index]
    table = {c: _anchor_rows(c, v.loc[c], ratios, expl) for c in cities}
    body = ""
    for i, name in enumerate(a for a, *_ in table[cities[0]]):
        body += f"<tr><td>{name}</td>" + "".join(
            f"<td>{'Not run' if pd.isna(table[c][i][2]) else SIGNAL[int(table[c][i][2])].capitalize()}</td>" for c in cities) + "</tr>"
    body += "<tr><th>Verdict</th>" + "".join(f'<th>{v.loc[c, "verdict"].capitalize()}</th>' for c in cities) + "</tr>"
    return f"""
<h2>Results so far</h2>
<div class="card">
  <div class="table-scroll"><table><thead><tr><th>Anchor</th>{"".join(f"<th>{MARKET[c]}</th>" for c in cities)}</tr></thead>
  <tbody>{body}</tbody></table></div>
  <p class="note">A verdict of "evidence of deviation" needs three anchors pointing the same way, one of them not based on
  rents; the rule was fixed before the results. No market reaches it. The anchors disagree, and rent capitalisation alone
  changes sign with the interest rate (Paris: 34% below its user-cost value in 2021, 64% above in 2023, baseline
  assumptions). Details on each city page and on the <a href="methodology.html">method page</a>.</p>
</div>"""


RULE_TEXT = {
    "paris": "35% of income, 25 years, 20% down payment (HCSF rule; the down payment is a convention), at the average "
             "rate on new French home loans",
    "singapore": "30% of income (mortgage servicing ratio), 25 years, 25% down payment, at the regulatory rate floor",
    "singapore_private": "55% of income (total debt servicing ratio), 30 years, 25% down payment, at the regulatory rate floor",
}
INCOME_TEXT = {
    "paris": "a couple at the median disposable income of the neighbourhood (INSEE Filosofi 2021, held at its 2021 level), 60 m²",
    "singapore": "the median household income from work of the planning area, 4-room flat",
    "singapore_private": "the median household income from work of the planning area",
}


def _pct(v, d=1):
    return "–" if pd.isna(v) else f"{100 * v:.{d}f}%"


def cross_section(city: str) -> str:
    f = PROCESSED / "cross_checks.csv"
    if not f.exists():
        return ""
    d = pd.read_csv(f)
    d = d[d["city"] == city].sort_values("year")
    if d.empty:
        return ""
    full = d.iloc[:-1] if len(d) > 1 else d  # the last year is still running
    r = full.iloc[-1]
    hist = [f"incomes {_pct(r['income_growth_20y'])} a year"]
    if not pd.isna(r["rent_growth_20y"]):
        hist.insert(0, f"rents {_pct(r['rent_growth_20y'])} a year")
    if pd.isna(r["g_star_gamma2"]):
        c1 = "Not run: no rent matched for this year."
    else:
        c1 = (f"Sale prices require rents to grow by <b>{_pct(r['g_star_gamma2'])} a year</b> "
              f"({_pct(r['g_star_gamma1'])} to {_pct(r['g_star_gamma4'])} for a risk premium of 1% to 4%). "
              f"Over the last 20 years: {' and '.join(hist)}.")
    c2 = (f"The median sale price is <b>{r['price_over_capacity']:.2f} times</b> what the reference household can finance "
          f"({r['price_over_capacity_rate_minus1']:.2f} to {r['price_over_capacity_rate_plus1']:.2f} with the rate one "
          f"point lower or higher; rate used {_pct(r['mortgage_rate'])}).")
    rows = "".join(
        f"<tr><td>{int(x.year)}</td><td class='num'>{_pct(x.gross_yield_median)}</td><td class='num'>{_pct(x.g_star_gamma1)}</td>"
        f"<td class='num'>{_pct(x.g_star_gamma2)}</td><td class='num'>{_pct(x.g_star_gamma4)}</td><td>{x.check1}</td>"
        f"<td class='num'>{_pct(x.mortgage_rate)}</td><td class='num'>{_num(x.price_over_capacity, 2)}</td><td>{x.check2}</td></tr>"
        for x in d.itertuples())
    return f"""
<h2>Two cross-checks of sale prices</h2>
<div class="card">
  <div class="kpis">
    <div class="kpi"><div class="v">{r['check1'].capitalize()}</div><div class="k">Check 1, rent side, {int(r['year'])}:
    is the rent growth the price requires plausible?</div><div class="n">{c1}</div></div>
    <div class="kpi"><div class="v">{r['check2'].capitalize()}</div><div class="k">Check 2, income side, {int(r['year'])}:
    can a local household finance the price?</div><div class="n">{c2}</div></div>
  </div>
  <p class="note">Check 1 solves the rent-capitalisation formula for the growth of rents instead of the value; incomes are
  the ceiling, since rents cannot outgrow them for ever. Check 2 ignores rents: it applies the lending rules
  ({RULE_TEXT[city]}) to {INCOME_TEXT[city]}. Read together for {int(r['year'])}: <b>{r['reading']}</b>. Both checks move with
  interest rates, and check 2 describes a median local household, not the people who actually buy. They are reported next
  to the verdict and are not part of its rule. Model-dependent hypotheses, not investment advice.</p>
  <details><summary>Table view, by year</summary><div class="table-scroll"><table><thead><tr><th>Year</th>
  <th class="num">Gross yield</th><th class="num">Required growth, premium 1%</th><th class="num">2%</th><th class="num">4%</th>
  <th>Check 1</th><th class="num">Loan rate</th><th class="num">Price / capacity</th><th>Check 2</th></tr></thead>
  <tbody>{rows}</tbody></table></div></details>
</div>"""


HIST = [("price", "var(--series-market)"), ("price_to_income", "var(--series-strat)"),
        ("price_to_rent", "var(--series-official)")]
HIST_LABEL = {"price_to_income": "Price-to-income ratio", "price_to_rent": "Price-to-rent ratio"}


def _quarters(first: str, last: str) -> list[str]:
    out, (y, q) = [], (int(first[:4]), int(first[5]))
    while f"{y}Q{q}" <= last:
        out.append(f"{y}Q{q}")
        y, q = (y, q + 1) if q < 4 else (y + 1, 1)
    return out


def history_section(city: str) -> str:
    """Long-run official price index and valuation ratios (own average = 100), with the turning
    points numbered and the documented events of each date listed underneath."""
    from src.viz.events import EVENTS, KIND

    f = PROCESSED / "ratio_series.csv"
    if not f.exists() or city not in EVENTS:
        return ""
    d = pd.read_csv(f, dtype={"period": str})
    d = d[d["city"] == city]
    if d.empty:
        return ""
    raw = {k: g.set_index("period")["value"] for k, g in d.groupby("series")}
    annual = {k: len(v.index[0]) == 4 for k, v in raw.items()}
    qs = [p for k, v in raw.items() for p in (v.index if not annual[k] else [f"{y}Q1" for y in v.index] + [f"{y}Q4" for y in v.index])]
    periods = _quarters(min(qs), max(qs))
    pos = {p: i for i, p in enumerate(periods)}
    N = len(periods)
    W, m = 920, {"l": 52, "r": 16, "t": 34, "b": 26}
    X = lambda i: m["l"] + (i + 0.5) * (W - m["l"] - m["r"]) / N  # noqa: E731

    # values per quarter for the read-out; drawing points (annual figures sit mid-year)
    vals, pts = {}, {}
    for k, v in raw.items():
        s = v if k == "price" else v / v.mean() * 100
        if annual[k]:
            vals[k] = [float(s[p[:4]]) if p[:4] in s.index else None for p in periods]
            pts[k] = [(pos[f"{y}Q2"] + 0.5, float(x)) for y, x in s.items() if f"{y}Q2" in pos]
        else:
            vals[k] = [float(s[p]) if p in s.index else None for p in periods]
            pts[k] = [(pos[p], float(x)) for p, x in s.items()]
    events = [e for e in EVENTS[city] if e[0] in pos]
    years = [i for i, p in enumerate(periods) if p.endswith("Q1") and int(p[:4]) % 5 == 0]

    def panel(keys: list[str], H: int, title: str, ref: float | None, marks: bool) -> str:
        allv = [y for k in keys for _, y in pts[k]]
        ticks = _ticks(min(allv), max(allv))
        step = ticks[1] - ticks[0] if len(ticks) > 1 else 10
        lo, hi = min(ticks[0], math.floor(min(allv) / step) * step), max(ticks[-1], math.ceil(max(allv) / step) * step)
        ticks = [lo + k * step for k in range(int(round((hi - lo) / step)) + 1)]
        Y = lambda v: H - m["b"] - (v - lo) / (hi - lo) * (H - m["t"] - m["b"])  # noqa: E731
        g = [f'<text x="{m["l"]}" y="12" style="font-weight:600;fill:var(--text-primary)">{title}</text>']
        g += [f'<line x1="{m["l"]}" x2="{W - m["r"]}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" stroke="var(--grid)"/>'
              f'<text x="{m["l"] - 8}" y="{Y(t) + 4:.1f}" text-anchor="end">{t:g}</text>' for t in ticks]
        g += [f'<text x="{X(i):.1f}" y="{H - 8}" text-anchor="middle">{periods[i][:4]}</text>' for i in years]
        if ref is not None:
            g.append(f'<line x1="{m["l"]}" x2="{W - m["r"]}" y1="{Y(ref):.1f}" y2="{Y(ref):.1f}" stroke="var(--muted)" stroke-dasharray="2 3"/>')
        for n, e in enumerate(events, 1):
            x = X(pos[e[0]])
            g.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{m["t"] + (7 if marks else -12)}" y2="{H - m["b"]}" stroke="var(--muted)" stroke-dasharray="3 3" opacity="0.7"/>')
            if marks:
                g.append(f'<circle cx="{x:.1f}" cy="{m["t"] - 2}" r="9" fill="var(--surface-1)" stroke="var(--text-primary)"/>'
                         f'<text x="{x:.1f}" y="{m["t"] + 2}" text-anchor="middle" style="font-weight:600;fill:var(--text-primary);font-size:11px">{n}</text>')
        for k, color in HIST:
            if k in keys:
                path = " ".join(f"{'M' if j == 0 else 'L'}{X(i):.1f},{Y(y):.1f}" for j, (i, y) in enumerate(pts[k]))
                g.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>')
                if marks:
                    g += [f'<circle cx="{X(pos[e[0]]):.1f}" cy="{Y(vals[k][pos[e[0]]]):.1f}" r="3.5" fill="{color}" stroke="var(--surface-1)" stroke-width="1.5"/>'
                          for e in events if vals[k][pos[e[0]]] is not None]
        g.append(f'<line class="xh" y1="{m["t"]}" y2="{H - m["b"]}" stroke="var(--muted)" visibility="hidden"/>'
                 f'<rect class="hit" x="{m["l"]}" y="0" width="{W - m["l"] - m["r"]}" height="{H}" fill="transparent"/>')
        return f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{title}">{"".join(g)}</svg>'

    ratios = [k for k, _ in HIST if k in raw and k != "price"]
    svgs = panel(["price"], 250, OFFICIAL[city] + " (index, not adjusted for inflation)", None, True)
    if ratios:
        svgs += panel(ratios, 220, "Valuation ratios, each relative to its own average (average = 100)", 100, False)
    labels = {"price": "Official price index", **HIST_LABEL}
    data = {"W": W, "l": m["l"], "r": m["r"], "periods": periods,
            "series": [{"label": labels[k], "color": c, "values": [None if x is None else round(x, 1) for x in vals[k]]}
                       for k, c in HIST if k in raw]}
    swatch = lambda c: f'<span class="sw" style="background:{c};height:3px;vertical-align:middle"></span>'  # noqa: E731
    legend = "".join(f'<span class="cls">{swatch(c)} {labels[k]}</span>' for k, c in HIST if k in raw)
    items = "".join(
        f"<li><b>{e[0].replace('Q', ' Q')} · {e[2]}</b> <span class='ev-k'>({KIND[e[1]].lower()})</span><br>{e[3]}"
        + ("<br><span class='ev-k'>Sources: " + "; ".join(f'<a href="{u}">{t}</a>' for t, u in e[4]) + ".</span>" if e[4] else "")
        + "</li>" for e in events)
    rows = "".join(f"<tr><td>{p.replace('Q', ' Q')}</td>" + "".join(f"<td class='num'>{_num(vals[k][i])}</td>" for k, _ in HIST if k in raw) + "</tr>"
                   for i, p in enumerate(periods) if p.endswith("Q4") or i == N - 1)
    head = "".join(f"<th class='num'>{labels[k]}</th>" for k, _ in HIST if k in raw)
    return f"""
<h2>Prices and ratios through past cycles</h2>
<div class="card">
  <div class="legend">{legend}</div>
  <div class="schart">{svgs}<script type="application/json">{json.dumps(data)}</script></div>
  <ol class="events">{items}</ol>
  <p class="note">Numbers mark turning points of the series; the text gives what the sources say happened around each date.
  These are coincidences in time documented by the sources listed, not causal estimates of this project, and several
  explanations can hold at once. Ratios are divided by their own average over the period shown, so 100 means "usual for
  this market", not "fair value".</p>
  <details><summary>Table view, fourth quarter of each year</summary><div class="table-scroll"><table><thead><tr><th>Quarter</th>
  {head}</tr></thead><tbody>{rows}</tbody></table></div></details>
</div>"""


GROUPS = [("cheapest third", "Cheapest third of districts", "var(--series-market)"),
          ("middle third", "Middle third", "var(--series-strat)"),
          ("dearest third", "Dearest third", "var(--series-official)")]
CYCLE_NOTE = {
    "paris": "Quartiers are sorted once, on their 2014–2016 price level. Source: DVF+ open-data, sales of single apartments, 2014–2025.",
    "singapore": "HDB towns are sorted once, on their 2009–2011 price level. Source: registered resales, 1990–2026 (2026 incomplete).",
}


def cycle_section(city: str) -> str:
    """Quality-adjusted price index of the cheapest, middle and dearest thirds of districts,
    and the yearly effect of being dearer."""
    fg, fs = PROCESSED / "district_cycle_groups.csv", PROCESSED / "district_cycle_slopes.csv"
    if not fg.exists() or not fs.exists():
        return ""
    g, s = pd.read_csv(fg), pd.read_csv(fs)
    g, s = g[g["city"] == city], s[s["city"] == city]
    if g.empty:
        return ""
    p = g.pivot(index="year", columns="group", values="index").sort_index()
    if city == "singapore":
        p = p.loc[2000:]
    years, N = [int(y) for y in p.index], len(p)
    W, H, m = 920, 300, {"l": 52, "r": 16, "t": 16, "b": 26}
    X = lambda i: m["l"] + (i + 0.5) * (W - m["l"] - m["r"]) / N  # noqa: E731
    ticks = _ticks(float(p.min().min()), float(p.max().max()))
    step = ticks[1] - ticks[0]
    lo, hi = math.floor(p.min().min() / step) * step, math.ceil(p.max().max() / step) * step
    ticks = [lo + k * step for k in range(int(round((hi - lo) / step)) + 1)]
    Y = lambda v: H - m["b"] - (v - lo) / (hi - lo) * (H - m["t"] - m["b"])  # noqa: E731
    e = [f'<line x1="{m["l"]}" x2="{W - m["r"]}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" stroke="var(--grid)"/>'
         f'<text x="{m["l"] - 8}" y="{Y(t) + 4:.1f}" text-anchor="end">{t:g}</text>' for t in ticks]
    every = 1 if N <= 14 else 5
    e += [f'<text x="{X(i):.1f}" y="{H - 8}" text-anchor="middle">{y}</text>' for i, y in enumerate(years) if y % every == 0]
    e.append(f'<line x1="{m["l"]}" x2="{W - m["r"]}" y1="{Y(100):.1f}" y2="{Y(100):.1f}" stroke="var(--muted)" stroke-dasharray="2 3"/>')
    for key, _, color in GROUPS:
        path = " ".join(f"{'M' if i == 0 else 'L'}{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(p[key]))
        e.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>')
    e.append(f'<line class="xh" y1="{m["t"]}" y2="{H - m["b"]}" stroke="var(--muted)" visibility="hidden"/>'
             f'<rect class="hit" x="{m["l"]}" y="0" width="{W - m["l"] - m["r"]}" height="{H}" fill="transparent"/>')
    data = {"W": W, "l": m["l"], "r": m["r"], "periods": [str(y) for y in years],
            "series": [{"label": lab, "color": c, "values": [round(float(v), 1) for v in p[k]]} for k, lab, c in GROUPS]}
    swatch = lambda c: f'<span class="sw" style="background:{c};height:3px;vertical-align:middle"></span>'  # noqa: E731
    legend = "".join(f'<span class="cls">{swatch(c)} {lab}</span>' for _, lab, c in GROUPS)
    ref = int(g["reference_year"].iloc[0])
    s = s[s["year"] >= years[0]]
    rows = "".join(
        f"<tr><td>{int(r.year)}</td><td class='num'>{r.mean_change_pct:+.1f}%</td>"
        f"<td class='num'>{r.change_for_10pct_dearer:+.1f}</td><td class='num'>{r.t:.1f}</td>"
        f"<td>{'dearer districts did better' if r.t >= 2 else 'cheaper districts did better' if r.t <= -2 else 'no clear difference'}</td></tr>"
        for r in s.itertuples())
    table = "".join(f"<tr><td>{y}</td>" + "".join(f"<td class='num'>{p.loc[y, k]:.1f}</td>" for k, _, _ in GROUPS) + "</tr>" for y in years)
    return f"""
<h2>Cheaper districts amplify the cycle</h2>
<div class="card">
  <p>Prices by district over a long period, at constant quality (index, {ref} = 100). Cheaper districts rise more in a
  boom and fall more in a correction. {CYCLE_NOTE.get(city, "")}</p>
  <div class="legend">{legend}</div>
  <div class="schart"><svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="Price index by third of districts">{"".join(e)}</svg>
  <script type="application/json">{json.dumps(data)}</script></div>
  <details><summary>Year by year: did dearer districts do better?</summary><div class="table-scroll"><table><thead><tr><th>Year</th>
  <th class="num">Average price change</th><th class="num">Effect of being 10% dearer (points)</th><th class="num">t</th><th>Reading (|t| ≥ 2)</th></tr></thead>
  <tbody>{rows}</tbody></table></div></details>
  <details><summary>Table view of the chart</summary><div class="table-scroll"><table><thead><tr><th>Year</th>
  {"".join(f"<th class='num'>{lab}</th>" for _, lab, _ in GROUPS)}</tr></thead><tbody>{table}</tbody></table></div></details>
  <p class="note">For each year, the price change of a district is regressed on its price level two to three years earlier.
  The dated reversals coincide with tighter credit (higher mortgage rates in France from 2022, loan caps in Singapore in
  2013). The timing fits a credit channel but does not prove it; neighbouring districts move together, so the
  t-statistics overstate the precision. Details and limits on the methodology page.</p>
</div>"""


def hcmc_section() -> str:
    """Ho Chi Minh City: the two cross-checks computed from published averages, with every input listed."""
    fc, fi = PROCESSED / "hcmc_checks.csv", PROCESSED / "hcmc_inputs.csv"
    if not fc.exists() or not fi.exists():
        return ""
    c, i = pd.read_csv(fc), pd.read_csv(fi).fillna("")
    v = i.set_index("input")["value"]
    pub = c[c["yield_case"] == "published"]
    g = c["g_star_gamma1"].min(), c["g_star_gamma4"].max()
    rows = "".join(
        f"<tr><td>{'Secondary (resale)' if r.price_basis == 'secondary' else 'Primary (new-build)'}, {r.price_m2_vnd / 1e6:.0f} million VND/m²</td>"
        f"<td>{r.lending_case}</td><td class='num'>{r.price_to_income_years:.1f}</td>"
        f"<td class='num'>{r.price_over_capacity_rate10:.2f}</td><td class='num'>{r.price_over_capacity_rate12:.2f}</td>"
        f"<td class='num'>{r.price_over_capacity_rate14:.2f}</td></tr>" for r in pub.itertuples())

    def fmt(r) -> str:
        x = float(r.value)
        return (f"{100 * x:.2f}%" if r.unit.startswith("ratio") else f"{x / 1e6:.3g} million {r.unit}" if x >= 1e6 else f"{x:g} {r.unit}")
    inputs = "".join(
        f"<tr><td>{r.description}</td><td class='num'>{fmt(r)}</td>"
        f"<td>{f'<a href={chr(34)}{r.url}{chr(34)}>{r.source}</a>' if r.url else '<i>assumption</i>'}</td></tr>" for r in i.itertuples())
    rr = pd.read_csv(PROCESSED / "hcmc_check1_rates.csv")
    word = {"plausible": "under in every case", "implausible": "above in every case", "depends on the premium": "depends on the risk premium"}
    rate_rows = "".join(f"<tr><td>{r.discount_rate_is}<br><span class='ev-k' style='color:var(--muted);font-size:0.8rem'>{r.why}</span></td>"
                        f"<td class='num'>{100 * r.rate:.1f}%</td><td class='num'>{100 * r.g_star_gamma1:.1f}% to {100 * r.g_star_gamma4:.1f}%</td>"
                        f"<td>{word[r.check1]}</td></tr>" for r in rr.itertuples())
    return f"""
<h2>Two cross-checks from published averages</h2>
<div class="card">
  <p>The tests run on sales for Paris and Singapore need a register of transactions, which Vietnam does not publish.
  The two cross-checks can still be computed from city-wide averages read in brokers' and official publications.
  They use asking prices and averages, not medians of sales, and several assumptions; read them as orders of magnitude.</p>
  <p><b>Income side: beyond capacity, whatever the case.</b> A {v["area"]:.0f} m² flat costs {pub["price_to_income_years"].min():.0f} to
  {pub["price_to_income_years"].max():.0f} years of average household income, and
  {c[["price_over_capacity_rate10", "price_over_capacity_rate12", "price_over_capacity_rate14"]].min().min():.1f} to
  {c[["price_over_capacity_rate10", "price_over_capacity_rate12", "price_over_capacity_rate14"]].max().max():.1f} times what
  that household can borrow at mortgage rates of 10% to 14%. This result does not use the government yield.</p>
  <p><b>Rent side: it depends on the discount rate.</b> The check asks what else the buyer's money could earn. In Paris the
  government borrows at about the same rate as households, so the choice does not matter. In Vietnam the government borrows at
  {100 * v["rf"]:.1f}% and households at 10% to 14%, and the answer changes with the rate. Incomes per person in the city grew
  by about {100 * v["income_growth"]:.1f}% a year between 2010 and 2022; that is the ceiling for rents.</p>
  <div class="table-scroll"><table><thead><tr><th>Discount rate taken</th><th class="num">Rate</th>
  <th class="num">Rent growth the price requires (risk premium 1% to 4%)</th><th>Against the ceiling of {100 * v["income_growth"]:.1f}%</th></tr></thead>
  <tbody>{rate_rows}</tbody></table></div>
  <p>The price is defensible for a buyer who pays cash and compares with a deposit at a state-owned bank, and not for a buyer
  who borrows. With credit this dear, an average household cannot be the marginal buyer; who is (savings, family money,
  investors) cannot be told from these data.</p>
  <div class="table-scroll"><table><thead><tr><th>Price used</th><th>Lending case</th><th class="num">Price, in years of household income</th>
  <th class="num">Price / borrowing capacity at 10%</th><th class="num">at 12%</th><th class="num">at 14%</th></tr></thead><tbody>{rows}</tbody></table></div>
  <details><summary>Every input, with its source</summary><div class="table-scroll"><table><thead><tr><th>Input</th>
  <th class="num">Value</th><th>Source (read on 20 November 2026)</th></tr></thead><tbody>{inputs}</tbody></table></div></details>
  <p class="note">Not run for lack of data: quality-adjusted price index, explosiveness test, history of the ratios, sales
  volumes, cross-section of districts. Published averages differ widely with the definition (60 to 112 million VND/m² in 2026
  depending on the source and on resale, new-build or newly launched projects), the city's boundary changed in July 2025, and
  the income survey may not capture all informal income. Household income is income per person times the national household
  size. No verdict is given for this city.</p>
</div>"""


HCMC_SERIES = [("Resale", "var(--series-market)"), ("New-build, former city", "var(--series-strat)"),
               ("New-build, merged city", "var(--series-official)")]


def hcmc_context_section() -> str:
    """Ho Chi Minh City: published prices with dated events, the two signals, who buys, and the figures behind them."""
    from src.valuation.hcmc_context import EVENTS, remittance_flats

    fp, ff, fb = (PROCESSED / f"hcmc_{k}.csv" for k in ("prices", "facts", "buyers"))
    if not (fp.exists() and ff.exists() and fb.exists()):
        return ""
    p, facts, buyers = pd.read_csv(fp), pd.read_csv(ff), pd.read_csv(fb)
    periods = _quarters(p["quarter"].min(), p["quarter"].max())
    pos = {q: i for i, q in enumerate(periods)}
    N, W, H, m = len(periods), 920, 320, {"l": 52, "r": 16, "t": 34, "b": 26}
    X = lambda i: m["l"] + (i + 0.5) * (W - m["l"] - m["r"]) / N  # noqa: E731
    lo, hi = 40, 100
    Y = lambda v: H - m["b"] - (v - lo) / (hi - lo) * (H - m["t"] - m["b"])  # noqa: E731
    e = [f'<line x1="{m["l"]}" x2="{W - m["r"]}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" stroke="var(--grid)"/>'
         f'<text x="{m["l"] - 8}" y="{Y(t) + 4:.1f}" text-anchor="end">{t}</text>' for t in range(lo, hi + 1, 10)]
    e += [f'<text x="{X(i):.1f}" y="{H - 8}" text-anchor="middle">{q[:4]} Q{q[5]}</text>' for i, q in enumerate(periods) if q[5] in "13"]
    for n, ev in enumerate(EVENTS, 1):
        x = X(pos[ev[0]])
        e.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{m["t"] + 7}" y2="{H - m["b"]}" stroke="var(--muted)" stroke-dasharray="3 3" opacity="0.7"/>'
                 f'<circle cx="{x:.1f}" cy="{m["t"] - 2}" r="9" fill="var(--surface-1)" stroke="var(--text-primary)"/>'
                 f'<text x="{x:.1f}" y="{m["t"] + 2}" text-anchor="middle" style="font-weight:600;fill:var(--text-primary);font-size:11px">{n}</text>')
    series = []
    for name, color in HCMC_SERIES:
        s = p[p["series"] == name].sort_values("quarter")
        pts = [(pos[q], float(v)) for q, v in zip(s["quarter"], s["million_vnd_m2"])]
        e.append(f'<path d="{" ".join(f"{chr(77) if j == 0 else chr(76)}{X(i):.1f},{Y(v):.1f}" for j, (i, v) in enumerate(pts))}" fill="none" stroke="{color}" stroke-width="2"/>')
        e += [f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="4" fill="{color}" stroke="var(--surface-1)" stroke-width="1.5"/>' for i, v in pts]
        d = dict(pts)
        series.append({"label": name, "color": color, "values": [d.get(i) for i in range(N)]})
    e.append(f'<line class="xh" y1="{m["t"]}" y2="{H - m["b"]}" stroke="var(--muted)" visibility="hidden"/>'
             f'<rect class="hit" x="{m["l"]}" y="0" width="{W - m["l"] - m["r"]}" height="{H}" fill="transparent"/>')
    data = {"W": W, "l": m["l"], "r": m["r"], "periods": [q.replace("Q", " Q") for q in periods], "series": series}
    swatch = lambda c: f'<span class="sw" style="background:{c};height:3px;vertical-align:middle"></span>'  # noqa: E731
    legend = "".join(f'<span class="cls">{swatch(c)} {n}</span>' for n, c in HCMC_SERIES)
    events = "".join(f"<li><b>{q.replace('Q', ' Q')} · {t}</b><br>{txt}<br><span class='ev-k'>Source: <a href=\"{u}\">{s}</a>.</span></li>"
                     for q, t, txt, s, u in EVENTS)
    ptable = "".join(f"<tr><td>{r.series}</td><td>{r.quarter.replace('Q', ' Q')}</td><td class='num'>{r.million_vnd_m2:g}</td>"
                     f"<td><a href=\"{r.url}\">{r.source}</a></td></tr>" for r in p.sort_values(["series", "quarter"]).itertuples())
    f = facts.set_index("figure")["value"]
    val = lambda start: next(v for k, v in f.items() if k.startswith(start))  # noqa: E731
    brow = "".join(f"<tr><td>{r.buyer}</td><td>{r.rate_case}</td><td class='num'>{r.household_income_month_vnd / 1e6:.1f}</td>"
                   f"<td class='num'>{r.price_over_capacity:.2f}</td><td>{'within reach' if r.price_over_capacity <= 1 else 'out of reach'}</td></tr>"
                   for r in buyers.itertuples())
    frows, last = "", None
    for r in facts.itertuples():
        frows += (f"<tr><td>{r.theme if r.theme != last else ''}</td><td>{r.figure}</td><td class='num'>{r.value}</td>"
                  f"<td><a href=\"{r.url}\">{r.source}</a></td></tr>")
        last = r.theme
    return f"""
<h2>Prices, credit and sales since 2023</h2>
<div class="card">
  <p>Average prices of flats published by one broker (CBRE Vietnam), in million VND per m², with the dated events that the
  sources report. These are averages of what is on offer, not a quality-adjusted index, and the new-build series breaks when
  the city is enlarged in July 2025.</p>
  <div class="legend">{legend}</div>
  <div class="schart"><svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="Average flat prices in Ho Chi Minh City">{"".join(e)}</svg>
  <script type="application/json">{json.dumps(data)}</script></div>
  <ol class="events">{events}</ol>
  <p><b>The average overstates the rise.</b> Flats at or under 50 million VND/m² were close to half of sales in 2020 and
  {val("Share of sales at or under")} in 2024; flats above 4 billion VND went from 2% of sales in 2020 to {val("Share of flats sold above")}
  in the first nine months of 2024. Part of the increase in the average is a change in what is sold, which is what the
  quality-adjusted indices correct for in Paris and Singapore.</p>
  <details><summary>Table view of the chart, with sources</summary><div class="table-scroll"><table><thead><tr><th>Series</th><th>Quarter</th>
  <th class="num">Million VND/m²</th><th>As reported by</th></tr></thead><tbody>{ptable}</tbody></table></div></details>
</div>

<h2>The two signals, read on the latest figures</h2>
<div class="card">
  <div class="table-scroll"><table><thead><tr><th>Signal</th><th>Latest figure</th><th>Reading</th></tr></thead><tbody>
  <tr><td>Price against income</td><td>11 to 13 years of household income here; {val("Price-to-income ratio, Hanoi")} and {val("Price of a 60 m² resale flat")}
  in two outside estimates</td><td>High, but there is no history to score it against the city's own past, as is done for Paris and Singapore</td></tr>
  <tr><td>Sales</td><td>{val("Flats and houses sold nationwide")} nationwide; {val("Share of new supply sold in the city")} of new supply sold in the city;
  unsold stock {val("Unsold stock reported")}</td><td>Under the rule fixed for Singapore (sales 20% below a year earlier) the flag would be on, on a national figure</td></tr>
  </tbody></table></div>
  <p>Of the markets studied, this is the only one where a stretched price-to-income ratio and falling sales are seen together
  today. In the four past cases found in Singapore and Paris, that combination was followed once by a fall of at least 10%,
  twice by smaller declines and once by nothing; it is a description of where the market stands, not a forecast.</p>
</div>

<h2>Who buys, if the average household cannot?</h2>
<div class="card">
  <div class="table-scroll"><table><thead><tr><th>Buyer</th><th>Mortgage rate</th><th class="num">Household income, million VND a month</th>
  <th class="num">Price / borrowing capacity</th><th></th></tr></thead><tbody>{brow}</tbody></table></div>
  <p class="meta-line">60 m² resale flat at 60 million VND/m², 30% down, 35% of income over 25 years.</p>
  <ul>
  <li><b>Credit was cheap when prices rose.</b> At the introductory rates of 2025 a better-off household could finance the
  flat; at the rates applied once that period ends, it cannot. {val("Buyers of a home to live in")} of buyers of a home to live
  in say they need a loan.</li>
  <li><b>Foreign buyers are few:</b> {val("Homes acquired by foreigners")} homes acquired nationwide since the 2023 law, in a city
  with {val("Flats built to date")} flats.</li>
  <li><b>Money from abroad is large:</b> {val("Remittances received")} reached the city in 2025, of which about
  {val("Share of remittances going to real estate")} goes to real estate. That would pay for about {round(remittance_flats(), -3):,.0f} such flats a year
  (computed here, at about 26,000 VND per dollar); not all of it buys flats.</li>
  <li><b>About a third of buyers are investors:</b> {val("Flat buyers by purpose")} (own home / to let / quick resale).</li>
  </ul>
  <p>The buyers are therefore better-off households with savings, families pooling money including from abroad, investors, and
  households who borrowed at introductory rates. The share of each cannot be measured with these sources, and the gap between
  the richest fifth and the average is the national one, applied to the city.</p>
  <details><summary>All figures used on this page, with sources</summary><div class="table-scroll"><table><thead><tr><th>Theme</th><th>Figure</th>
  <th class="num">Value</th><th>As reported by (read on 20 November 2026)</th></tr></thead><tbody>{frows}</tbody></table></div></details>
  <p class="note">Most figures are read in press coverage of brokers' and official reports, not in the reports themselves. Sales
  and unsold stock are national. Survey shares come from a property portal. The household count without a home dates from 2019.</p>
</div>"""
