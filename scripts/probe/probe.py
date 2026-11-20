"""Lists what a few public download locations expose (no data kept): used to decide how a
source can be fetched automatically. Output: data/processed/probe_report.txt."""
import json
import re
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) research-reproducibility-check"}
BOX = "https://cerema.app.box.com/v/dvfplus-opendata"
out = []


def get(url: str) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read().decode("utf-8", "ignore")


def items(html: str) -> list[dict]:
    m = re.search(r"Box\.postStreamData\s*=\s*(\{.*?\});\s*</script>", html, re.S)
    if not m:
        return []
    found = []

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("items"), list):
                found.extend(i for i in o["items"] if isinstance(i, dict) and "typedID" in i)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(json.loads(m.group(1)))
    return found


def box(url: str, depth: int, budget: list[int], path: str = "") -> None:
    for page in range(1, 6):
        try:
            html = get(url + (f"?page={page}" if page > 1 else ""))
        except Exception as e:
            out.append(f"{path} ERROR {e!r}")
            return
        its = items(html)
        if not its:
            if page == 1:
                out.append(f"{path} no items parsed; html {len(html)} chars; markers: "
                           + str([k for k in ("postStreamData", "shared-folder", "typedID") if k in html]))
            return
        for i in its:
            name, tid = i.get("name"), i.get("typedID")
            out.append(f"{path}/{name} | {tid} | {i.get('itemSize') or i.get('size')}")
            keep = depth < 1 or re.search(r"csv|75|ile|r11|idf|france|d\d\d|lisez|readme", str(name), re.I)
            if tid.startswith("d_") and depth < 3 and budget[0] > 0 and keep:
                budget[0] -= 1
                box(f"{BOX}/folder/{tid[2:]}", depth + 1, budget, f"{path}/{name}")
        if len(its) < 20:
            return


def listing(fid: str) -> list[tuple[str, str, object]]:
    res = []
    for page in range(1, 8):
        html = get(f"{BOX}/folder/{fid}" + (f"?page={page}" if page > 1 else ""))
        m = re.search(r"Box\.postStreamData\s*=\s*(\{.*?\});\s*</script>", html, re.S)
        sf = json.loads(m.group(1)).get("/app-api/enduserapp/shared-folder", {}) if m else {}
        res += [(i.get("name"), i.get("typedID"), i.get("itemSize")) for i in sf.get("items", [])]
        if page >= sf.get("pageCount", 1):
            break
    return res


import csv
import io

out.append("=== data.gov.hk: RVD property market statistics")
try:
    pkg = json.loads(get("https://data.gov.hk/en-data/api/3/action/package_show?id=hk-rvd-tsinfo_rvd-property-market-statistics"))["result"]
    out.append("licence/terms fields: " + json.dumps({k: pkg.get(k) for k in ("license_id", "license_title", "license_url")}))
    res = pkg.get("resources", [])
    out.append(f"{len(res)} resources")
    want = [r for r in res if re.search(r"Private Domestic - (Price|Rental) Indices by Class \(Territory-wide\)|Market Yields|Average (Prices|Rents) by Class", r.get("name", ""))]
    for r in want:
        out.append(f"{r.get('name')} | {r.get('format')} | {r.get('url')}")
    seen = set()
    for r in want:
        u = r.get("url", "")
        if not u.lower().endswith(".csv") or u in seen or len(seen) >= 6:
            continue
        seen.add(u)
        try:
            txt = get(u)
            lines = txt.splitlines()
            out.append(f"--- {u}: {len(lines)} lines")
            out += ["   " + ln[:260] for ln in lines[:7] + lines[-3:]]
        except Exception as e:
            out.append(f"--- {u} ERROR {e!r}")
except Exception as e:
    out.append(f"ERROR {e!r}")

out.append("=== DBnomics: IMF IFS, Hong Kong and France")
for sid in ("IMF/IFS/Q.HK.PCPI_IX", "IMF/IFS/Q.HK.FILR_PA", "IMF/IFS/Q.HK.FIMM_PA", "IMF/IFS/Q.HK.FIGB_PA", "IMF/IFS/Q.HK.FIDR_PA",
            "IMF/IFS/M.HK.PCPI_IX", "IMF/IFS/Q.FR.PCPI_IX", "IMF/IFS/Q.FR.FIGB_PA"):
    try:
        d = json.loads(get(f"https://api.db.nomics.world/v22/series/{sid}?observations=1"))["series"]["docs"][0]
        obs = [(p, v) for p, v in zip(d["period"], d["value"]) if v not in (None, "NA")]
        out.append(f"{sid} | {d.get('series_name')} | {len(obs)} obs | {obs[0]} .. {obs[-1]}")
    except Exception as e:
        out.append(f"{sid} ERROR {e!r}")

out.append("=== HKMA API")
for u in ("https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/hk-interbank-ir-endperiod?pagesize=1000&sortby=end_of_month&sortorder=asc",
          "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/hkd-ir-effdates?pagesize=1000",
          "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/hk-deposit-ir-endperiod?pagesize=1000&sortorder=asc"):
    try:
        d = json.loads(get(u))["result"]
        recs = d.get("records", [])
        out.append(f"{u.split('/')[-1].split('?')[0]} | {d.get('datasize')} records | keys {list(recs[0])[:14] if recs else None}")
        out += ["   " + json.dumps(r)[:300] for r in recs[:1] + recs[-1:]]
    except Exception as e:
        out.append(f"{u} ERROR {e!r}")
open(sys.argv[1], "w").write("\n".join(out) + "\n")
print("\n".join(out)[:5000])
