"""What moved the price-to-rent ratio: interest rates, rents, or the rest?

The user-cost formula takes today's interest rate as if it held for ever. The dynamic
present-value relation of Campbell and Shiller (1988), applied to housing by Campbell,
Davis, Gallin and Martin (2009), does not. With rp the log rent-to-price ratio, dr the real
growth of rents and i the real interest rate, all per quarter, and rho = 1 / (1 + exp(mean rp)):

    rp_t = constant + sum_j rho^j E_t[i_{t+1+j}] + sum_j rho^j E_t[premium_{t+1+j}] - sum_j rho^j E_t[dr_{t+1+j}]

A home is dear relative to its rent (rp low) only if real rates are expected to be low, if
rents are expected to grow fast, or if buyers accept a low return above the interest rate.
Expected rates and rents are forecasts of a first-order vector autoregression on (rp, dr, i);
the premium term is what is left:

    R_t = e_i' A (I - rho A)^-1 x_t      G_t = e_dr' A (I - rho A)^-1 x_t      PREMIUM_t = rp_t - R_t + G_t

(x demeaned, A the VAR matrix). Reported: the share of the variance of rp carried by each
term, with a bootstrap interval, and the contribution of each term to the change in the
log price-to-rent ratio over two episodes fixed by the data (from its lowest to its highest
point, and from the highest point to the last quarter).

Fixed before the results: quarterly VAR(1); real rate = nominal rate minus inflation over the
previous four quarters; nominal rate = the 10-year government yield (Paris, Singapore) or the
banks' best lending rate (Hong Kong, where no long government yield exists before the 1990s
and mortgages are priced off that rate); an annual VAR(1) is run as a check.

A VAR estimated on a few decades understates how persistent rates and rents are, and what
their forecasts then fail to explain is booked as premium. To measure this, the same
procedure is run on simulated samples of the same length in which there is no premium at
all (`premium_share_without_premium`); the premium's share in the data is to be read against
the share the method reports in that case.

The premium is a residual. It contains the risk premium, but also credit conditions, taxes,
and every error of the forecasting model. It is not a measured quantity.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import INTERIM, N_BOOT, PROCESSED, SEED

COLS = ["rp", "dr", "i"]
TERMS = ["real_rates", "rent_growth", "premium"]


# ------------------------------------------------------------------------ model
def var1(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """OLS VAR(1) on demeaned data: x_{t+1} = A x_t + e. Returns A and the residuals."""
    Y, Z = X[1:], X[:-1]
    A = np.linalg.lstsq(Z, Y, rcond=None)[0].T
    return A, Y - Z @ A.T


def decompose(X: np.ndarray, rho: float, A: np.ndarray | None = None) -> dict:
    """X: demeaned array with columns rp, dr, i. Returns the three present-value terms."""
    if A is None:
        A, _ = var1(X)
    M = A @ np.linalg.inv(np.eye(3) - rho * A)
    R, G = X @ M[2], X @ M[1]
    P = X[:, 0] - R + G
    v = X[:, 0].var()
    shares = {"real_rates": np.cov(X[:, 0], R, bias=True)[0, 1] / v, "rent_growth": -np.cov(X[:, 0], G, bias=True)[0, 1] / v,
              "premium": np.cov(X[:, 0], P, bias=True)[0, 1] / v}
    return {"A": A, "R": R, "G": G, "P": P, "shares": shares, "max_root": float(np.abs(np.linalg.eigvals(A)).max())}


def bootstrap_shares(X: np.ndarray, rho: float, rng: np.random.Generator, n: int = N_BOOT) -> pd.DataFrame:
    A, E = var1(X)
    rows = []
    for _ in range(n):
        e = E[rng.integers(0, len(E), len(E))]
        Xb = np.empty_like(X)
        Xb[0] = X[0]
        for t in range(1, len(X)):
            Xb[t] = A @ Xb[t - 1] + e[t - 1]
        Xb = Xb - Xb.mean(axis=0)
        try:
            d = decompose(Xb, rho)
        except np.linalg.LinAlgError:
            continue
        if d["max_root"] < 1 / rho:
            rows.append(d["shares"])
    return pd.DataFrame(rows)


def premium_share_without_premium(X: np.ndarray, rho: float, rng: np.random.Generator, n: int = N_BOOT) -> np.ndarray:
    """What the method reports as the premium's share when there is none. Rents and rates are
    simulated from their own estimated dynamics, the rent-to-price ratio is set to the exact
    present value of their forecasts (no premium), and the decomposition is run on samples
    of the same length. A VAR estimated on a short sample understates persistence, and
    whatever expected rates and rents then fail to explain is booked as premium."""
    Z = X[:, 1:]
    B, E = var1(Z)
    M = B @ np.linalg.inv(np.eye(2) - rho * B)
    w = M[1] - M[0]                               # rp = PV(rates) - PV(rent growth); columns: dr, i
    out = []
    for _ in range(n):
        e = E[rng.integers(0, len(E), len(E))]
        z = np.empty_like(Z)
        z[0] = Z[0]
        for t in range(1, len(Z)):
            z[t] = B @ z[t - 1] + e[t - 1]
        Xs = np.column_stack([z @ w, z])
        Xs = Xs - Xs.mean(axis=0)
        try:
            d = decompose(Xs, rho)
        except np.linalg.LinAlgError:
            continue
        if d["max_root"] < 1 / rho:
            out.append(d["shares"]["premium"])
    return np.array(out)


def frame(rent_index: pd.Series, price_index: pd.Series, yield_anchor: pd.Series, nominal_pct: pd.Series, cpi: pd.Series) -> pd.DataFrame:
    """Quarterly model variables. `yield_anchor`: annual gross yield (fraction) on some of the
    quarters; it only sets the level of the rent-to-price ratio, the indices give its path."""
    d = pd.DataFrame({"rent": rent_index, "price": price_index, "nom": nominal_pct, "cpi": cpi, "y": yield_anchor})
    rel = np.log(d["rent"]) - np.log(d["price"])
    both = rel.notna() & d["y"].notna()
    level = (np.log(d.loc[both, "y"] / 4) - rel[both]).mean()
    infl = np.log(d["cpi"]) - np.log(d["cpi"].shift(4))
    out = pd.DataFrame({"rp": rel + level, "dr": np.log(d["rent"]).diff() - np.log(d["cpi"]).diff(), "i": (d["nom"] / 100 - infl) / 4})
    return out.dropna()


def annual(q: pd.DataFrame) -> pd.DataFrame:
    y = q.index.year
    a = pd.DataFrame({"rp": q["rp"].groupby(y).last() + np.log(4), "dr": q["dr"].groupby(y).sum(), "i": q["i"].groupby(y).sum()})
    return a[q["rp"].groupby(y).size() == 4]


def analyse(q: pd.DataFrame, rng: np.random.Generator) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    rho = 1 / (1 + np.exp(q["rp"].mean()))
    X = (q[COLS] - q[COLS].mean()).to_numpy()
    d = decompose(X, rho)
    boot = bootstrap_shares(X, rho, rng)
    null = premium_share_without_premium(X, rho, rng)
    a = annual(q)
    da = decompose((a[COLS] - a[COLS].mean()).to_numpy(), 1 / (1 + np.exp(a["rp"].mean())))
    # contributions to the log price-to-rent ratio (= -rp): lower expected rates and premia raise it, higher expected rents raise it
    path = pd.DataFrame({"log_price_to_rent": -X[:, 0], "real_rates": -d["R"], "rent_growth": d["G"], "premium": -d["P"]}, index=q.index)
    lo, hi, last = path["log_price_to_rent"].idxmin(), path["log_price_to_rent"].idxmax(), path.index[-1]
    spans = ([("lowest to highest", lo, hi)] if lo < hi else [("highest to lowest", hi, lo)]) + ([("highest to latest", hi, last)] if hi < last else [])
    episodes = pd.DataFrame([{"episode": n, "from": str(s), "to": str(e), "change_price_to_rent_pct": 100 * (np.exp(path.loc[e, "log_price_to_rent"] - path.loc[s, "log_price_to_rent"]) - 1),
                              **{f"{t}_log_points": 100 * (path.loc[e, t] - path.loc[s, t]) for t in ["log_price_to_rent"] + TERMS}} for n, s, e in spans])
    summary = {"first": str(q.index[0]), "last": str(q.index[-1]), "quarters": len(q), "rho": rho,
               "mean_yield_pct": 100 * 4 * np.exp(q["rp"].mean()), "max_root": d["max_root"], "stationary_enough": bool(d["max_root"] < 1 / rho),
               **{f"share_{t}": d["shares"][t] for t in TERMS},
               **{f"share_{t}_{k}": boot[t].quantile(p) if len(boot) else np.nan for t in TERMS for k, p in (("low", 0.05), ("high", 0.95))},
               "bootstrap_draws_kept": len(boot),
               **{f"premium_share_if_no_premium_{k}": float(np.quantile(null, p)) if len(null) else np.nan for k, p in (("p05", 0.05), ("p50", 0.5), ("p95", 0.95))},
               **{f"annual_share_{t}": da["shares"][t] for t in TERMS}, "annual_years": len(a)}
    return summary, path.reset_index(names="period"), episodes


# ------------------------------------------------------------------------- data
def _q(s: pd.Series) -> pd.Series:
    s.index = pd.PeriodIndex(s.index, freq="Q")
    return s.sort_index()


def _monthly_rate(path) -> pd.Series:
    r = pd.read_csv(path)
    s = pd.Series(r["rate_pct"].to_numpy(dtype=float), index=pd.PeriodIndex(r["month"].astype(str).str.slice(0, 7), freq="M"))
    return s.groupby(s.index.asfreq("Q")).mean()


def _from_ratio_series(city: str, key: str) -> tuple[pd.Series, pd.Series, pd.Series]:
    r = pd.read_csv(PROCESSED / "ratio_series.csv", dtype={"period": str})
    r = r[(r["city"] == city) & (r["period"].str.len() == 6)]
    price = _q(r[r["series"] == "price"].set_index("period")["value"])
    ptr = _q(r[r["series"] == "price_to_rent"].set_index("period")["value"])
    c = pd.read_csv(PROCESSED / "cross_checks.csv")
    y = c[(c["city"] == city) & c["gross_yield_median"].notna()].set_index("year")["gross_yield_median"]
    anchor = pd.Series({p: y.get(p.year, np.nan) for p in ptr.index}).dropna()
    return (price / ptr).dropna(), price, anchor


def markets() -> dict[str, pd.DataFrame]:
    out = {}
    cpi = pd.read_csv(PROCESSED / "macro_cpi.csv", dtype={"period": str}).set_index("period")
    cpi.index = pd.PeriodIndex(cpi.index, freq="Q")
    for city, rate_file, cpi_col in (("paris", "rf_paris.csv", "cpi_france"), ("singapore_private", "rf_singapore.csv", "cpi_singapore")):
        try:
            rent, price, anchor = _from_ratio_series(city, cpi_col)
            out[city] = frame(rent, price, anchor, _monthly_rate(INTERIM / rate_file), cpi[cpi_col])
        except Exception as e:  # one market failing must not stop the others
            print(city, "skipped:", repr(e)[:300])
    try:
        h = pd.read_csv(PROCESSED / "hk_series.csv", dtype={"period": str}).set_index("period")
        h.index = pd.PeriodIndex(h.index, freq="Q")
        out["hongkong"] = frame(h["rent_index"], h["price_index"], h["yield_pct"] / 100, h["best_lending_rate_pct"], h["cpi"])
    except Exception as e:
        print("hongkong skipped:", repr(e)[:300])
    return out


def run() -> None:
    rows, paths, eps = [], [], []
    for city, q in markets().items():
        if len(q) < 60:
            print(city, "skipped: only", len(q), "quarters")
            continue
        s, p, e = analyse(q, np.random.default_rng(SEED))
        rows.append({"market": city, **s})
        paths.append(p.assign(market=city, period=p["period"].astype(str)))
        eps.append(e.assign(market=city))
        print(city, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in s.items()})
        print(e.round(1).to_string(index=False))
    if rows:
        pd.DataFrame(rows).round(4).to_csv(PROCESSED / "dynamic_pv_summary.csv", index=False)
        pd.concat(paths).round(4).to_csv(PROCESSED / "dynamic_pv_paths.csv", index=False)
        pd.concat(eps).round(2).to_csv(PROCESSED / "dynamic_pv_episodes.csv", index=False)


if __name__ == "__main__":
    run()
