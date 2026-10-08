import json, os, random, re, sys, time
from datetime import datetime
from bs4 import BeautifulSoup
import pandas as pd
import requests

# Full set (restore when you want the general roles again):
# QS = ['"Software Engineer"', '"AI Engineer"', '"Data Engineer"',
#       '"New Grad Software Engineer"', '"Entry Level Software Engineer"']
QS = ['"New Grad Software Engineer"', '"Entry Level Software Engineer"']

TARGETS = {
    "us":     {"geoId": "103644278"},
    "remote": {"geoId": "103644278", "f_WT": "2"},
    "bay":    {"geoId": "90000084"},
    "nyc":    {"geoId": "90000070"},
}

CFG = {"hrs": 4, "exp": "1,2,3", "pages": 15, "out": "li_jobs.xlsx",
       "miss": 3}

INC = ("software", "developer", "frontend", "backend", "full stack", "engineer",
       "sde", "swe", "ai", "ml", "machine learning", "llm", "data")

EXCRE = re.compile(
    r"\b(sr|senior|staff|principal|lead|manager|director|architect|vp|avp|svp|"
    r"chief|head|intern|phd|investor|gtm|devrel|qa|sales|civil|structural|"
    r"mechanical|nurse|oncology|hematology|mid)\b|\b(ii|iii|iv)\b|"
    r"vice[\s-]?president|mid[\s-]?level", re.I)

API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

S = requests.Session()
S.headers.update({
    "user-agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/122.0.0.0 Safari/537.36"),
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
})


def get(p, tries=4):
    for i in range(tries):
        try:
            r = S.get(API, params=p, timeout=15)
        except Exception as e:
            print(f"  net: {e}")
            time.sleep(2 ** i)
            continue
        if r.status_code == 200:
            return r
        if r.status_code in (429, 503, 999):
            w = 8 * 2 ** i + random.random() * 4
            print(f"  throttled {r.status_code}, sleep {w:.0f}s")
            time.sleep(w)
            continue
        return None
    return None


def ok(t):
    return any(k in t.lower() for k in INC) and not EXCRE.search(t)


def why_reject(t):
    if not any(k in t.lower() for k in INC):
        return "no software keyword"
    m = EXCRE.search(t)
    return "excluded: " + m.group(0) if m else "other"


def txt(e):
    return e.get_text(" ", strip=True) if e else ""


def jid(u):
    m = re.search(r"(\d{8,})$", u)
    return m.group(1) if m else ""


def sheet(rows):
    # Fresh rewrite every run: only this run's jobs, discard anything old.
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates("ID", keep="first")
        # Newest first — Fetched has minute precision; Posted is only a date.
        df = df.sort_values(["Fetched", "Posted"], ascending=False,
                            kind="mergesort")
        df["Open"] = df["Link"].map(lambda u: f'=HYPERLINK("{u}","open")')
    try:
        df.to_excel(CFG["out"], index=False)   # overwrite, not append
    except PermissionError:
        print("  ! close li_jobs.xlsx in Excel, nothing saved")


def run(tag, added, rows, dropped):
    t = TARGETS[tag]
    stamp = datetime.now().isoformat(timespec="minutes")
    n0 = len(rows)
    for q in QS:
        start, miss, qseen = 0, 0, set()
        while start < CFG["pages"] * 10:   # stop after CFG["pages"] pages
            p = {"keywords": q, "f_E": CFG["exp"], "sortBy": "DD",
                 "f_TPR": f"r{CFG['hrs'] * 3600}", "start": start, **t}
            r = get(p)
            if not r:
                break
            cards = BeautifulSoup(r.text, "html.parser").select("li")
            if not cards:
                break
            fresh = 0
            for c in cards:
                a = c.select_one("a.base-card__full-link")
                if not a:
                    continue
                u = (a.get("href") or "").split("?")[0]
                i = jid(u)
                if not i or i in qseen:
                    continue
                qseen.add(i)
                fresh += 1
                if i in added:            # already collected this run (other geo/query)
                    continue
                ti = txt(c.select_one("h3.base-search-card__title")) or txt(a)
                tm = c.select_one("time")
                if not ok(ti):
                    added.add(i)          # remember so we don't re-log it
                    dropped.append({
                        "Title": ti,
                        "Company": txt(c.select_one("h4.base-search-card__subtitle")),
                        "Location": txt(c.select_one(".job-search-card__location")),
                        "Posted": tm.get("datetime", "") if tm else "",
                        "Reason": why_reject(ti),
                        "Geo": tag,
                        "Query": q.strip('"'),
                        "Fetched": stamp,
                        "Link": u,
                        "ID": i,
                    })
                    continue
                added.add(i)
                rows.append({
                    "Title": ti,
                    "Company": txt(c.select_one("h4.base-search-card__subtitle")),
                    "Location": txt(c.select_one(".job-search-card__location")),
                    "Posted": tm.get("datetime", "") if tm else "",
                    "Geo": tag,
                    "Query": q.strip('"'),
                    "Fetched": stamp,
                    "Link": u,
                    "ID": i,
                })
            miss = miss + 1 if fresh == 0 else 0
            if miss >= CFG["miss"]:
                break
            start += 10
            time.sleep(random.uniform(1.5, 3.0))
        print(f"[{tag}] {q.strip(chr(34)):22} pages={start // 10:3} "
              f"pool={len(qseen):4} kept={len(rows)}")
    print(f"[{tag}] +{len(rows) - n0}\n")


if __name__ == "__main__":
    tags = sys.argv[1:] or list(TARGETS)
    added, rows, dropped = set(), [], []
    for x in tags:
        if x in TARGETS:
            run(x, added, rows, dropped)
        else:
            print(f"unknown: {x}")
    sheet(rows)   # kept jobs: fresh, newest-first
    # discarded jobs (title filter) -> separate file so you can review them
    dd = pd.DataFrame(dropped)
    if not dd.empty:
        dd = dd.drop_duplicates("ID", keep="first")
    try:
        dd.to_excel("li_jobs_discarded.xlsx", index=False)
    except PermissionError:
        print("  ! close li_jobs_discarded.xlsx in Excel, discards not saved")
    print(f"total {len(rows)} kept -> {CFG['out']}")
    print(f"      {len(dd) if not dd.empty else 0} discarded -> li_jobs_discarded.xlsx")