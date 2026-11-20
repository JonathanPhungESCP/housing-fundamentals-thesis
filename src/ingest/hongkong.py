"""Hong Kong: official price and rent indices of private homes since 1979, market yields, the
banks' best lending rate since 1971, and consumer prices.

- Rating and Valuation Department (RVD), Property Market Statistics, through data.gov.hk:
  quarterly price indices and rental indices by class of flat (territory-wide, from the
  fourth quarter of 1979) and market yields by class (from 1990).
- Hong Kong Monetary Authority (HKMA) open API: Hong Kong dollar interest rates by effective
  date, including the best lending rate, the reference for mortgages.
- IMF International Financial Statistics through DBnomics: quarterly consumer price index.

Indices and rates only; no individual data. Output: data/processed/hk_series.csv.
"""
from __future__ import annotations

import io
import json
import re

import pandas as pd

from src.config import PROCESSED, RAW
from src.ingest.http import fetch_bytes, record

OUT = RAW / "hongkong"
RVD = "http://www.rvd.gov.hk/datagovhk/"
FILES = {"price_index": "1.4Q.csv", "rent_index": "1.3Q.csv", "yield": "5.1Q.csv"}
HKMA = ("https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/hkd-ir-effdates"
        "?pagesize=1000")
DBNOMICS = "https://api.db.nomics.world/v22/series/{sid}?observations=1"
CPI = {"hongkong": "IMF/IFS/Q.HK.PCPI_IX", "france": "IMF/IFS/Q.FR.PCPI_IX", "singapore": "IMF/IFS/Q.SG.PCPI_IX"}


def rvd_table(name: str) -> pd.DataFrame:
    """One RVD csv as a table indexed by quarter, numeric columns only (remark columns dropped)."""
    dest = OUT / name
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(fetch_bytes(RVD + name, retries=5))
        record(dest, RVD + name, "RVD Property Market Statistics (data.gov.hk)")
    lines = dest.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    start = next(i for i, ln in enumerate(lines) if re.match(r"\s*(Quarter|Period|Year)", ln, re.I))
    d = pd.read_csv(io.StringIO("\n".join(lines[start:])), dtype=str)
    q = d.iloc[:, 0].str.extract(r"(\d{2})\s*-\s*(\d{2})\s*/\s*(\d{4})")
    ok = q[2].notna()
    idx = pd.PeriodIndex([f"{y}Q{int(m) // 3}" for m, y in zip(q.loc[ok, 1], q.loc[ok, 2])], freq="Q")
    cols = [c for c in d.columns[1:] if "remark" not in c.lower() and not c.lower().startswith("unnamed")]
    t = d.loc[ok, cols].apply(pd.to_numeric, errors="coerce")
    t.index = idx
    print(name, "| header:", list(d.columns)[:14], "| rows", len(t), t.index.min(), t.index.max())
    return t[~t.index.duplicated(keep="last")].sort_index()


def all_classes(t: pd.DataFrame) -> pd.Series:
    """The 'all classes' column when there is one, otherwise the mean of classes A, B and C
    (flats under 100 m2, the bulk of the stock)."""
    col = [c for c in t.columns if re.search(r"all\s*class", c, re.I)]
    if col:
        return t[col[0]]
    abc = [c for c in t.columns if re.search(r"class\s*[ABC]\b", c, re.I)]
    return t[abc].mean(axis=1)


def best_lending_rate() -> pd.Series:
    dest = OUT / "hkma_hkd_interest_rates.json"
    if not dest.exists():
        dest.write_bytes(fetch_bytes(HKMA, retries=5))
        record(dest, HKMA, "HKMA: Hong Kong dollar interest rates by effective date")
    recs = json.loads(dest.read_text())["result"]["records"]
    s = pd.Series({pd.Timestamp(r["effect_date"]): r["best_lending_rate"] for r in recs if r.get("best_lending_rate") is not None}).sort_index()
    daily = s.reindex(pd.date_range(s.index[0], pd.Timestamp.today().normalize(), freq="D")).ffill()
    q = daily.groupby(daily.index.to_period("Q")).mean()
    print("best lending rate:", len(s), "changes,", s.index[0].date(), "to", s.index[-1].date())
    return q


def cpi(key: str) -> pd.Series:
    dest = RAW / "macro" / f"cpi_{key}.json"
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(fetch_bytes(DBNOMICS.format(sid=CPI[key]), retries=5))
        record(dest, DBNOMICS.format(sid=CPI[key]), f"IMF IFS consumer price index via DBnomics ({CPI[key]})")
    d = json.loads(dest.read_text())["series"]["docs"][0]
    s = pd.Series({p.replace("-", ""): v for p, v in zip(d["period"], d["value"]) if isinstance(v, (int, float))})
    s.index = pd.PeriodIndex(s.index, freq="Q")
    print("cpi", key, len(s), s.index.min(), s.index.max())
    return s.sort_index()


def main() -> None:
    t = {k: rvd_table(f) for k, f in FILES.items()}
    out = pd.DataFrame({"price_index": all_classes(t["price_index"]), "rent_index": all_classes(t["rent_index"]),
                        "yield_pct": all_classes(t["yield"]), "best_lending_rate_pct": best_lending_rate(), "cpi": cpi("hongkong")})
    out = out[out["price_index"].notna()]
    out.index.name = "period"
    out.round(4).to_csv(PROCESSED / "hk_series.csv")
    print(out.describe().round(2).to_string())
    print(out.head(3).to_string()); print(out.tail(3).to_string())
    macro = pd.DataFrame({f"cpi_{k}": cpi(k) for k in ("france", "singapore")})
    macro.index.name = "period"
    macro.round(4).to_csv(PROCESSED / "macro_cpi.csv")


if __name__ == "__main__":
    main()
