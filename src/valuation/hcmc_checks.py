"""Ho Chi Minh City: the two cross-checks, from published market averages (exploratory).

Vietnam has no public register of sales and no official rent or price index, so none of the
tests run on transaction data for Paris and Singapore can be run here: no quality-adjusted
index, no explosiveness test, no ratio history, no district cross-section. What can be done
is the pair of cross-checks, with city-wide averages read in published sources:

    check 1 (rent side)    g* = r_f + tau + delta + gamma - R/P, against long-run income growth
    check 2 (income side)  P / P_max, P_max = share x household income x annuity / (1 - down)

Every input is listed in INPUTS with its source and the date it was read, or marked as an
assumption. Prices and rents are asking figures and averages from brokers' reports, not
medians of sales; nothing here has the standing of the Paris or Singapore results. The
reading rules are those of src/valuation/cross_checks.py; because the inputs are loose, each
check is run over a range and the range is what is reported.
"""
from __future__ import annotations

import itertools

import pandas as pd

from src.config import PROCESSED
from src.valuation.cross_checks import GAMMAS, annuity, combine, read_check1, read_check2

READ = "2026-11-20"
# name: (value, unit, kind, description, source, url)
INPUTS = {
    "price_secondary": (60e6, "VND/m2", "source", "Average asking price of secondary apartments, Q3 2026",
                        "CBRE Vietnam Q3 2026 report, as reported by Realtique",
                        "https://www.realtique.net/en/news/market-update/45639/ho-chi-minh-city-condo-prices-q3-2026/"),
    "price_primary": (75e6, "VND/m2", "source", "Average primary (new-build) apartment price, Q3 2026",
                      "CBRE Vietnam Q3 2026 report, as reported by Realtique",
                      "https://www.realtique.net/en/news/market-update/45639/ho-chi-minh-city-condo-prices-q3-2026/"),
    "gross_yield": (0.0416, "ratio", "source", "Gross rental yield, asking rent over asking price, 1-3 bedrooms, H2 2025",
                    "Global Property Guide table, as quoted by Zagdim", "https://zagdim.com/en/?p=7245"),
    "rf": (0.04463, "ratio", "source", "10-year government bond yield, close of 11 November 2026",
           "AsianBondsOnline (Asian Development Bank)", "https://asianbondsonline.adb.org/economy/?economy=VN&page=3"),
    "income_per_head": (8.064e6, "VND/month", "source", "Average monthly income per person, HCMC, household living standards survey 2025",
                        "National Statistics Office survey, as reported by Znews",
                        "https://znews.vn/nguoi-viet-kiem-nhieu-tien-hon-nhung-khoang-cach-giau-ngheo-van-lon-post1668320.html"),
    "household_size": (3.5, "persons", "source", "Average household size, national (no HCMC figure read), 2025",
                       "National Statistics Office, press release on the 2025 survey",
                       "https://www.nso.gov.vn/wp-content/uploads/2026/07/Thong-cao-bao-chi-ksms2025.pdf"),
    "income_growth": (0.072, "ratio/year", "source", "Income per person in HCMC multiplied by 2.3 between 2010 and 2022 (compound rate computed here)",
                      "National Statistics Office figures, as reported by Tuoi Tre",
                      "https://tuoitre.vn/muc-song-toi-thieu-nguoi-dan-khoang-1-8-trieu-dong-thang-20250106130844534.htm"),
    "rate_low": (0.10, "ratio", "source", "Floating mortgage rate after the preferential period, state-owned banks (9.5-10%)",
                 "VietNamNet", "https://vietnamnet.vn/en/home-buyers-grow-cautious-amid-interest-rate-volatility-2498589.html"),
    "rate_base": (0.12, "ratio", "source", "Floating mortgage rate after the preferential period, lower bound of the 12-14% range",
                  "Viet Nam News via The Star, 3 March 2026",
                  "https://www.thestar.com.my/business/business-news/2026/03/03/rising-mortgage-rates-test-property-market"),
    "rate_high": (0.14, "ratio", "source", "Floating mortgage rate after the preferential period, upper bound of the 12-14% range",
                  "Viet Nam News via The Star, 3 March 2026",
                  "https://www.thestar.com.my/business/business-news/2026/03/03/rising-mortgage-rates-test-property-market"),
    "down": (0.30, "ratio", "source", "Down payment: loans commonly cover 50-70% of the value",
             "Viet Nam News via The Star, 3 March 2026",
             "https://www.thestar.com.my/business/business-news/2026/03/03/rising-mortgage-rates-test-property-market"),
    "tau_delta": (0.014, "ratio", "assumption", "Taxes and upkeep as a share of value: the Paris figure reused, no Vietnamese source read", "", ""),
    "area": (60.0, "m2", "assumption", "Size of the flat priced: two bedrooms, no source on the median size sold", "", ""),
    "share": (0.35, "ratio", "assumption", "Share of income paid to the lender: the French convention; Vietnam sets no cap in the sources read", "", ""),
    "share_high": (0.50, "ratio", "assumption", "Looser alternative for the share of income", "", ""),
    "years": (25, "years", "assumption", "Loan term for comparability with Paris; terms up to 30-35 years are advertised", "", ""),
    "years_long": (30, "years", "assumption", "Longer alternative for the loan term", "", ""),
}
V = {k: v[0] for k, v in INPUTS.items()}


def check1(yield_: float, rf: float, tau_delta: float, ceiling: float) -> dict:
    g = {k: rf + tau_delta + gm - yield_ for k, gm in GAMMAS.items()}
    return {"gross_yield": yield_, "g_star_gamma1": g["lo"], "g_star_gamma2": g["base"], "g_star_gamma4": g["hi"],
            "income_growth": ceiling, "check1": read_check1(g["lo"], g["hi"], ceiling)}


def capacity_ratio(price_m2: float, area: float, income_month: float, rate: float, share: float, years: int, down: float) -> float:
    return price_m2 * area * (1 - down) / (share * income_month * annuity(rate, years))


def run() -> pd.DataFrame:
    income = V["income_per_head"] * V["household_size"]
    rows = []
    for (pname, price), (yname, y) in itertools.product(
            (("secondary", V["price_secondary"]), ("primary", V["price_primary"])),
            (("published", V["gross_yield"]), ("one point lower", V["gross_yield"] - 0.01), ("one point higher", V["gross_yield"] + 0.01))):
        c1 = check1(y, V["rf"], V["tau_delta"], V["income_growth"])
        for sname, share, years in (("35% of income, 25 years", V["share"], V["years"]), ("50% of income, 30 years", V["share_high"], V["years_long"])):
            r = [capacity_ratio(price, V["area"], income, V[k], share, years, V["down"]) for k in ("rate_low", "rate_base", "rate_high")]
            c2 = read_check2(*r)
            rows.append({"price_basis": pname, "price_m2_vnd": price, "yield_case": yname, **c1, "lending_case": sname,
                         "household_income_month_vnd": income, "price_to_income_years": price * V["area"] / (12 * income),
                         "price_over_capacity_rate10": r[0], "price_over_capacity_rate12": r[1], "price_over_capacity_rate14": r[2],
                         "check2": c2, "reading": combine(c1["check1"], c2)})
    out = pd.DataFrame(rows)
    out.round(4).to_csv(PROCESSED / "hcmc_checks.csv", index=False)
    pd.DataFrame([{"input": k, "value": v[0], "unit": v[1], "kind": v[2], "description": v[3], "source": v[4], "url": v[5],
                   "read_on": READ if v[2] == "source" else ""} for k, v in INPUTS.items()]).to_csv(PROCESSED / "hcmc_inputs.csv", index=False)
    return out


if __name__ == "__main__":
    pd.set_option("display.width", 250, "display.max_columns", 30)
    o = run()
    print(o[["price_basis", "yield_case", "g_star_gamma1", "g_star_gamma4", "check1", "lending_case", "price_to_income_years",
             "price_over_capacity_rate10", "price_over_capacity_rate12", "price_over_capacity_rate14", "check2", "reading"]].round(3).to_string(index=False))
