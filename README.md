# LinkedIn Job Tool

A small personal toolkit for finding and filtering entry-level / new-grad software
jobs on LinkedIn.

## Parts

| File | What it does |
|------|--------------|
| `linkedin_scraper.py` | Pulls recent job listings from LinkedIn's public guest API across several search terms and locations, filters by title (keeps software/AI/data roles, drops senior/non-software), and writes them newest-first to `li_jobs.xlsx`. Discarded titles go to `li_jobs_discarded.xlsx` with the reason. |
| `build_jobs_html.py` | Turns `li_jobs.xlsx` into a searchable, filterable `jobs.html` page — mark-as-applied, query/location/company filters, repost collapsing, and an extra title cleanup pass. |
| `linkedin-job-filter.user.js` | A Tampermonkey userscript. On an open LinkedIn job page it reads the description, matches it against your resume with the Claude API, and shows a skill-match % + APPLY/SKIP verdict. Reposted jobs are skipped without an API call. |

## Usage

```bash
# 1. Fetch fresh jobs (rewrites li_jobs.xlsx each run)
python linkedin_scraper.py            # all locations
python linkedin_scraper.py bay nyc    # specific ones

# 2. Build the browsable page
python build_jobs_html.py             # -> jobs.html
```

Then open `jobs.html` in a browser.

### Tampermonkey script
Install [Tampermonkey](https://www.tampermonkey.net/), add `linkedin-job-filter.user.js`,
and set your Anthropic API key via the Tampermonkey menu (stored only in your browser).
Edit the `RESUME`, `CRITERIA`, `AUTO_RUN`, and `CLOSE_ON_REPOST` constants at the top to taste.

## Requirements

```bash
pip install requests beautifulsoup4 pandas openpyxl
```

## Notes

- Scraped data (`*.xlsx`, `*.csv`, `jobs.html`) is git-ignored — it's personal and
  against LinkedIn's ToS to redistribute.
- The Tampermonkey script's API key is never stored in the file; it lives in the browser.
