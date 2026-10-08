import json
import re
import openpyxl

XLSX = "li_jobs.xlsx"
OUT = "jobs.html"

# Strong "this really is a software role" signals — a title matching any of
# these is always kept, even if it also hits a BLOCK word below.
SOFT = re.compile(
    r"software (engineer|developer|dev)|back[\s-]?end|front[\s-]?end|"
    r"full[\s-]?stack|\bsde\b|\bswe\b|web developer|java developer|"
    r"python developer|\.net developer|dotnet developer|golang|go developer|"
    r"\bml engineer\b|machine learning|\bai engineer\b|ai developer|"
    r"data engineer|devops|platform engineer|application developer|"
    r"mobile developer|ios developer|android developer|programmer", re.I)

# Seniority — a HARD exclude (checked first, before SOFT can override). Entry
# level only, so drop senior/lead/manager/VP/mid (II/III) titles outright.
SENIOR = re.compile(
    r"\bsenior\b|\bsr\.?\b|\bstaff\b|\bprincipal\b|\blead(?:er|ership)?\b|\bmanager\b|"
    r"\bdirector\b|\bhead\b|\barchitect\b|\bchief\b|distinguished|expert|"
    r"vice[\s-]?president|\bvp\b|\bavp\b|\bsvp\b|\bii\b|\biii\b|\biv\b|"
    r"\bmid\b|mid[\s-]?level", re.I)

# Non-software disciplines / IT-ops / consulting that the word "engineer"
# wrongly lets through. Dropped UNLESS the title also matches SOFT above.
BLOCK = re.compile(
    r"radio frequency|\brf\b|spacecraft|\bvalidation\b|chemical|kinetics|"
    r"mechanical|electrical|\bcivil\b|structural|hardware|firmware|\brfic\b|"
    r"windows 365|infrastructure|network engineer|cyber[\s-]?security|"
    r"security analytics|operational technology|\bot\b|salesforce|servicenow|"
    r"sharepoint|\bsap\b|financial systems|\btax\b|forward deploy|"
    r"service delivery|test engineer|field engineer|sales engineer|"
    r"solutions? engineer|support engineer|sysadmin|systems administrator|"
    r"desktop|help[\s-]?desk|\bqa\b|quality engineer|manufacturing|"
    r"automation engineer|\d(?:nd|rd|th) shift|night shift|"
    r"process engineer|facilities|biomedical|clinical|research scientist", re.I)


def keep_job(title):
    if SENIOR.search(title):          # senior/mid -> always drop
        return False
    return bool(SOFT.search(title)) or not BLOCK.search(title)

wb = openpyxl.load_workbook(XLSX, read_only=True)
ws = wb.active
rows = list(ws.iter_rows(values_only=True))
header = [str(h or "").strip() for h in rows[0]]
idx = {name: i for i, name in enumerate(header)}


def get(r, name):
    i = idx.get(name)
    v = r[i] if i is not None and i < len(r) else ""
    return str(v).strip() if v is not None else ""


jobs = []
raw_count = 0
for r in rows[1:]:
    if not any(r):
        continue
    raw_count += 1
    title = get(r, "Title")
    if not keep_job(title):           # drop senior + non-software roles
        continue
    jobs.append({
        "id": get(r, "ID") or get(r, "Link"),
        "title": title,
        "company": get(r, "Company"),
        "location": get(r, "Location"),
        "posted": get(r, "Posted"),
        "fetched": get(r, "Fetched"),
        "geo": get(r, "Geo"),
        "query": get(r, "Query"),
        "url": get(r, "Link"),
        "dupes": 0,
    })

# newest first — Fetched has minute precision, Posted is date-only
jobs.sort(key=lambda j: (j["fetched"], j["posted"]), reverse=True)

# Collapse reposts: same company + title posted across many cities -> one card.
deduped, seen = [], {}
for j in jobs:
    key = (j["company"].lower().strip(), " ".join(j["title"].lower().split()))
    if key in seen:
        seen[key]["dupes"] += 1
    else:
        seen[key] = j
        deduped.append(j)
filtered_out = raw_count - len(jobs)
collapsed = len(jobs) - len(deduped)
jobs = deduped
data = json.dumps(jobs, ensure_ascii=False)
print(f"raw={raw_count} filtered_out={filtered_out} "
      f"reposts_collapsed={collapsed} shown={len(jobs)}")

page = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Results</title>
<style>
  :root{
    --bg:#0f1115; --card:#181b22; --card2:#1f232c; --text:#e6e8ec; --muted:#9aa2af;
    --accent:#4f8cff; --border:#2a2f3a; --chip:#232833;
  }
  *{box-sizing:border-box}
  body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    background:var(--bg);color:var(--text);line-height:1.45}
  header{position:sticky;top:0;z-index:10;background:rgba(15,17,21,.92);backdrop-filter:blur(8px);
    border-bottom:1px solid var(--border);padding:18px 20px}
  h1{margin:0 0 4px;font-size:20px}
  .sub{color:var(--muted);font-size:13px}
  .controls{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
  input,select{background:var(--card2);color:var(--text);border:1px solid var(--border);
    border-radius:8px;padding:9px 12px;font-size:14px;outline:none}
  input:focus,select:focus{border-color:var(--accent)}
  #search{flex:1;min-width:200px}
  main{max-width:960px;margin:0 auto;padding:18px 20px 60px}
  .job{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px 18px;margin-bottom:12px;
    transition:opacity .2s, border-color .2s}
  .job.applied{opacity:.6;border-color:var(--good)}
  .job-top{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}
  .title{font-size:16px;font-weight:600;margin:0}
  .title a{color:var(--text);text-decoration:none}
  .title a:hover{color:var(--accent);text-decoration:underline}
  .meta{color:var(--muted);font-size:13px;margin-top:4px}
  .meta b{color:var(--text);font-weight:600}
  .chips{margin-top:8px;display:flex;gap:6px;flex-wrap:wrap;align-items:center}
  .chip{font-size:12px;color:var(--muted);background:var(--chip);border:1px solid var(--border);
    padding:3px 9px;border-radius:20px}
  .chip.tag-applied{color:var(--good);border-color:var(--good)}
  .apply-btn{flex:none;cursor:pointer;font-size:13px;font-weight:600;padding:7px 14px;border-radius:8px;
    border:1px solid var(--border);background:var(--card2);color:var(--text);white-space:nowrap}
  .apply-btn:hover{border-color:var(--accent)}
  .job.applied .apply-btn{background:var(--good);border-color:var(--good);color:#0f1115}
  .empty{text-align:center;color:var(--muted);padding:40px}
</style>
</head>
<body>
<header>
  <h1>Job Results</h1>
  <div class="sub" id="count"></div>
  <div class="controls">
    <input id="search" type="search" placeholder="Search title, company, location...">
    <select id="query"></select>
    <select id="geo"></select>
    <select id="company"></select>
    <select id="status">
      <option value="">All statuses</option>
      <option value="applied">Applied only</option>
      <option value="not">Not applied only</option>
    </select>
    <select id="sort">
      <option value="posted">Sort: Newest</option>
      <option value="company">Sort: Company A-Z</option>
      <option value="title">Sort: Title A-Z</option>
    </select>
  </div>
</header>
<main id="list"></main>
<script>
const JOBS = __DATA__;
const list = document.getElementById('list');
const search = document.getElementById('search');
const querySel = document.getElementById('query');
const geoSel = document.getElementById('geo');
const companySel = document.getElementById('company');
const statusSel = document.getElementById('status');
const sortSel = document.getElementById('sort');
const count = document.getElementById('count');

// Applied state persisted in the browser (localStorage)
const STORE_KEY = 'appliedJobs';
let applied = {};
try { applied = JSON.parse(localStorage.getItem(STORE_KEY) || '{}'); } catch(e){ applied = {}; }
function saveApplied(){ try { localStorage.setItem(STORE_KEY, JSON.stringify(applied)); } catch(e){} }

function opts(sel, values, label){
  const uniq = [...new Set(values.filter(Boolean))].sort((a,b)=>a.localeCompare(b));
  sel.innerHTML = `<option value="">All ${label}</option>` + uniq.map(v=>`<option>${esc(v)}</option>`).join('');
}
function esc(s){ const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }

opts(querySel, JOBS.map(j=>j.query), 'queries');
opts(geoSel, JOBS.map(j=>j.geo), 'locations');
opts(companySel, JOBS.map(j=>j.company), 'companies');

function render(){
  const q = search.value.toLowerCase().trim();
  const query = querySel.value, geo = geoSel.value, company = companySel.value, status = statusSel.value;
  let items = JOBS.filter(j=>{
    const isApplied = !!applied[j.id];
    if(query && j.query!==query) return false;
    if(geo && j.geo!==geo) return false;
    if(company && j.company!==company) return false;
    if(status==='applied' && !isApplied) return false;
    if(status==='not' && isApplied) return false;
    if(!q) return true;
    return (j.title+' '+j.company+' '+j.location).toLowerCase().includes(q);
  });
  const s = sortSel.value;
  items.sort((a,b)=> s==='company' ? a.company.localeCompare(b.company)
    : s==='title' ? a.title.localeCompare(b.title)
    : ((b.fetched||'')+(b.posted||'')).localeCompare((a.fetched||'')+(a.posted||'')));

  const appliedTotal = JOBS.filter(j=>applied[j.id]).length;
  count.textContent = `${items.length} of ${JOBS.length} jobs · ${appliedTotal} applied`;
  if(!items.length){ list.innerHTML='<div class="empty">No jobs match your filters.</div>'; return; }
  list.innerHTML = items.map(j=>{
    const isApplied = !!applied[j.id];
    return `
    <div class="job ${isApplied?'applied':''}" data-id="${esc(j.id)}">
      <div class="job-top">
        <p class="title"><a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a></p>
        <button class="apply-btn" data-id="${esc(j.id)}">${isApplied?'✓ Applied':'Mark applied'}</button>
      </div>
      <div class="meta"><b>${esc(j.company)||'—'}</b> · ${esc(j.location)||'—'} · ${esc(j.posted)||'—'}${j.dupes?` · <span style="color:#e0b341">+${j.dupes} more location${j.dupes>1?'s':''}</span>`:''}</div>
      <div class="chips">
        ${j.query?`<span class="chip">${esc(j.query)}</span>`:''}
        ${j.geo?`<span class="chip">${esc(j.geo)}</span>`:''}
        ${isApplied?'<span class="chip tag-applied">Applied</span>':''}
      </div>
    </div>`;
  }).join('');
}

list.addEventListener('click', e=>{
  const btn = e.target.closest('.apply-btn');
  if(!btn) return;
  const id = btn.dataset.id;
  if(applied[id]) delete applied[id]; else applied[id] = new Date().toISOString();
  saveApplied();
  render();
});

[search].forEach(el=>el.addEventListener('input', render));
[querySel,geoSel,companySel,statusSel,sortSel].forEach(el=>el.addEventListener('change', render));
render();
</script>
</body>
</html>
"""

page = page.replace("__DATA__", data)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(page)
print("wrote", OUT, "with", len(jobs), "jobs from", XLSX)
