"""Ho Chi Minh City: published figures around the two cross-checks (exploratory).

Prices over time, sales, credit, who buys. Every figure is read in a published source,
mostly press coverage of brokers' and official reports, and listed with its URL. Nothing is
estimated from transactions, and averages are not quality-adjusted: the same sources show
that the mix of flats sold moved sharply towards the top of the market.

Outputs: hcmc_prices.csv (points for the chart), hcmc_facts.csv (figures and sources),
hcmc_buyers.csv (borrowing capacity under other incomes and rates; computed here).
"""
from __future__ import annotations

import pandas as pd

from src.config import PROCESSED
from src.valuation.hcmc_checks import V, capacity_ratio

READ = "2026-11-20"
REALTIQUE_Q3 = "https://www.realtique.net/en/news/market-update/45639/ho-chi-minh-city-condo-prices-q3-2026/"
REALTIQUE_Q2 = "https://www.realtique.net/en/news/market-update/41851/vietnam-real-estate-market-2026-q2-outlook-forecast/"
BAODAUTU_2023 = "https://baodautu.vn/thi-truong-nha-o-dang-dan-dao-chieu-d207044.html"
VOV_Q3 = "https://vov.vn/kinh-te/thi-truong-can-ho-tai-tphcm-quy-iii2026-suc-mua-giam-thanh-khoan-thap-post1342202.vov"
STAR = "https://www.thestar.com.my/business/business-news/2026/03/03/rising-mortgage-rates-test-property-market"

# series, quarter, million VND per m2, source, url  (all: CBRE Vietnam averages as reported)
PRICES = [
    ("New-build, former city", "2023Q3", 60.6, "Doanh Nhan Plus", "https://doanhnhanplus.vn/thi-truong-bat-dong-san-tp-hcm-quy-3-2023-da-tro-nen-soi-dong-hon-623849.html"),
    ("New-build, former city", "2023Q4", 61.0, "Bao Dau Tu", BAODAUTU_2023),
    ("New-build, former city", "2024Q1", 61.0, "Cafeland", "https://cafeland.vn/tin-tuc/dau-hieu-cho-thay-thi-truong-bat-dong-san-nha-o-se-soi-dong-trong-quy-2-128224.html"),
    ("New-build, former city", "2024Q3", 69.0, "Tuoi Tre", "https://tuoitre.vn/gia-can-ho-o-tp-hcm-con-trung-binh-68-trieu-dong-m-20241003181312401.htm"),
    ("New-build, former city", "2025Q4", 90.0, "Lao Dong", "https://news.laodong.vn/bat-dong-san/lech-pha-cung-cau-khien-gia-bat-dong-san-o-nam-bo-kho-giam-1630491.ldo"),
    ("New-build, merged city", "2025Q3", 67.0, "Realtique", REALTIQUE_Q2),
    ("New-build, merged city", "2026Q2", 76.0, "Realtique", REALTIQUE_Q2),
    ("New-build, merged city", "2026Q3", 75.0, "Realtique", REALTIQUE_Q3),
    ("Resale", "2023Q4", 45.0, "Bao Dau Tu", BAODAUTU_2023),
    ("Resale", "2024Q4", 49.0, "VnBusiness", "https://vnbusiness.vn/gia-nha-ha-noi-da-tang-nhu-the-nao-trong-nam-2024.html"),
    ("Resale", "2026Q2", 62.0, "Vietnam.vn (VTV)", "https://www.vietnam.vn/en/da-tang-gia-can-ho-tai-tp-ho-chi-minh-cham-lai"),
    ("Resale", "2026Q3", 60.0, "Realtique", REALTIQUE_Q3),
]

# quarter, title, text, source, url
EVENTS = [
    ("2025Q1", "Cheap introductory loans",
     "State-owned banks offer young buyers home loans at 5.5% fixed for three years; other banks advertise low rates for the first one to three years.",
     "Vietstock", "https://en.vietstock.vn/2025/12/banks-withdraw-preferential-housing-loans-aimed-at-young-buyers-37-625893.htm"),
    ("2025Q3", "The city is enlarged",
     "On 1 July 2025 the city merges with Binh Duong and Ba Ria-Vung Tau. Averages for the merged city include cheaper areas and cannot be compared with earlier ones.",
     "Realtique", REALTIQUE_Q2),
    ("2026Q1", "Mortgage rates reach 12% to 14%",
     "Rates climb to 12% to 14% once the introductory period ends; the cheap packages for young buyers are withdrawn.",
     "Viet Nam News via The Star", STAR),
    ("2026Q3", "Sales fall",
     "Only 45% of new supply finds a buyer in the city (90% a quarter earlier); nationwide sales of flats and houses are down about 29% on a year; the average resale asking price slips 4% in a quarter.",
     "VOV", VOV_Q3),
]

# theme, figure, value, source, url
FACTS = [
    ("Mix of flats sold", "Share of sales at or under 50 million VND/m², 2024 (2020: close to 50%)", "18%", "Nha Dau Tu", "https://nhadautu.vn/phat-sot-voi-gia-can-ho-o-tphcm-d93883.html"),
    ("Mix of flats sold", "Share of flats sold above 4 billion VND, first nine months of 2024 (2020: 2%)", "70%", "Tuoi Tre", "https://tuoitre.vn/gia-can-ho-o-tp-hcm-con-trung-binh-68-trieu-dong-m-20241003181312401.htm"),
    ("Sales", "Flats and houses sold nationwide, Q3 2026, change on a year", "22,847; about -28.9%", "Dien Dan Doanh Nghiep", "https://diendandoanhnghiep.vn/bat-dong-san-cuoi-nam-truoc-ap-luc-thanh-khoan-10187496.html"),
    ("Sales", "Unsold stock reported by developers, 27 of 34 provinces, Q3 2026, change on a year", "51,950; +94%", "24HMoney", "https://24hmoney.vn/news/ton-kho-bat-dong-san-tang-gan-gap-doi-len-52-ngan-can-trong-quy-3-c3a2846557.html"),
    ("Sales", "Share of new supply sold in the city, Q3 2026", "45%", "VOV", VOV_Q3),
    ("Credit", "Real-estate credit nationwide, end 2025, growth on a year (all credit: just over 19%)", "+36%", "SGGP", "https://www.sggp.org.vn/nan-dong-tin-dung-bat-dong-san-vao-nhu-cau-thuc-post858538.html"),
    ("Credit", "Real estate in total bank credit, HCMC and Dong Nai, Q1 2026", "about 27.5%", "Cafeland", "https://cafeland.vn/tin-tuc/sang-loc-tin-dung-bat-dong-san-152266.html"),
    ("Credit", "Loans to households for their own home in real-estate credit, HCMC, 2026", "about 66%", "SGGP", "https://www.sggp.org.vn/nan-dong-tin-dung-bat-dong-san-vao-nhu-cau-thuc-post858538.html"),
    ("Credit", "Bad-debt ratio of real-estate credit reported by the central bank, 2025", "2.43%", "Tuoi Tre News", "https://news.tuoitre.vn/vietnam-cbank-warns-of-real-estate-credit-risks-amid-rapid-loan-growth-10325092416011909.htm"),
    ("Buyers", "Flat buyers by purpose, portal survey, Q1 2026: own home / to let / quick resale", "67% / 30% / 4%", "Doanh Nghiep Hoi Nhap", "https://doanhnghiephoinhap.vn/chung-cu-dan-dat-dat-nen-nhay-voi-bien-dong-nha-rieng-phan-hoa-theo-ap-luc-gia-132750.html"),
    ("Buyers", "Buyers of a home to live in who say they need a loan, portal survey, Q2 2026", "84%", "Batdongsan", "https://wiki.batdongsan.com.vn/tin-tuc/nguoi-mua-bat-dong-san-chuyen-tu-ky-vong-tang-gia-sang-uu-tien-gia-tri-thuc-856184"),
    ("Buyers", "Homes acquired by foreigners nationwide since the 2023 Housing Law", "1,519", "Asia News Network", "https://asianews.network/?p=305337"),
    ("Buyers", "Flats built to date in the city (cumulative supply, CBRE)", "close to 460,000", "VOV", VOV_Q3),
    ("Buyers", "Remittances received in the city, 2025", "10.34 billion USD", "VnBusiness", "https://vnbusiness.vn/vuot-bao-bien-dong-toan-cau-hon-103-ty-usd-kieu-hoi-do-manh-ve-tphcm.html"),
    ("Buyers", "Share of remittances going to real estate (central bank's city branch)", "22%", "Bao Dau Tu", "https://baodautu.vn/kieu-hoi-duoc-ky-vong-gop-phan-lam-soi-dong-thi-truong-bat-dong-san-d213646.html"),
    ("Buyers", "Income per person of the richest fifth against the national average, 2025", "11.8 against 6.0 million VND a month", "Dai Bieu Nhan Dan", "https://daibieunhandan.vn/thu-nhap-binh-quan-cua-nguoi-viet-dat-6-trieu-dong-thang-10423417.html"),
    ("Housing", "Households without a home of their own, city survey, 2019", "about 476,000, close to a quarter", "Bao Phap Luat", "https://doanhnhan.baophapluat.vn/khoang-476-ngan-ho-gia-dinh-tai-tp-hcm-chua-co-nha-rieng-22829.html"),
    ("Housing", "Housing floor area per person, end 2024 (2010: 16.58 m²)", "22.61 m²", "PLO", "https://plo.vn/tphcm-can-tap-trung-giai-quyet-thu-tuc-cho-cac-du-an-de-phat-trien-nha-o-post828583.html"),
    ("Other estimates", "Price of a 60 m² resale flat in years of household income, former city (preprint, not peer-reviewed)", "12.1", "Preprints.org", "https://www.preprints.org/manuscript/202611.1445"),
    ("Other estimates", "Price-to-income ratio, Hanoi and HCMC, portal survey 2025", "about 11.5", "Tuoi Tre News", "https://news.tuoitre.vn/how-vietnams-young-buyers-navigate-a-housing-market-amid-widening-income-home-price-gap-10325121316172418.htm"),
]

RICH_OVER_AVERAGE = 11.8 / 6.0      # national ratio, applied to the city: an assumption
TEASER = 0.06                       # introductory rates of 5.5% to 6.5% advertised in 2025
REMITTANCES_USD, TO_PROPERTY, VND_PER_USD = 10.34e9, 0.22, 26_000  # exchange rate rounded, about the 2025 level


def buyers() -> pd.DataFrame:
    income = V["income_per_head"] * V["household_size"]
    rows = []
    for who, mult in (("Average household", 1.0), ("Household of the richest fifth (national gap applied, assumption)", RICH_OVER_AVERAGE)):
        for label, rate in (("introductory rate of 2025, 6%", TEASER), ("rate after the introductory period, 12%", V["rate_base"])):
            rows.append({"buyer": who, "rate_case": label, "household_income_month_vnd": income * mult,
                         "price_over_capacity": capacity_ratio(V["price_secondary"], V["area"], income * mult, rate, V["share"], V["years"], V["down"])})
    return pd.DataFrame(rows)


def remittance_flats() -> float:
    """Flats of the reference size and resale price that one year of remittances going to real estate would pay for."""
    return REMITTANCES_USD * TO_PROPERTY * VND_PER_USD / (V["price_secondary"] * V["area"])


def run() -> None:
    pd.DataFrame(PRICES, columns=["series", "quarter", "million_vnd_m2", "source", "url"]).to_csv(PROCESSED / "hcmc_prices.csv", index=False)
    pd.DataFrame(FACTS, columns=["theme", "figure", "value", "source", "url"]).assign(read_on=READ).to_csv(PROCESSED / "hcmc_facts.csv", index=False)
    b = buyers()
    b.round(3).to_csv(PROCESSED / "hcmc_buyers.csv", index=False)
    print(b.round(2).to_string(index=False))
    print("flats one year of remittances to real estate would pay for:", round(remittance_flats()))


if __name__ == "__main__":
    run()
