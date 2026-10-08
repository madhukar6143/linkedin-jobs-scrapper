// ==UserScript==
// @name         LinkedIn Job Filter (Claude)
// @namespace    https://github.com/local/linkedin-job-filter
// @version      2.3
// @description  Reads the open LinkedIn job description, matches it against your resume with Claude, and shows a short APPLY / SKIP verdict on the left of the screen. Can auto-run on each job.
// @author       you
// @match        https://www.linkedin.com/jobs/*
// @match        https://www.linkedin.com/job/*
// @run-at       document-idle
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_registerMenuCommand
// @connect      api.anthropic.com
// ==/UserScript==

(function () {
  'use strict';

  // ---- CONFIG -------------------------------------------------------------
  const MODEL = 'claude-haiku-4-5';   // fast + cheap, good for per-job checks
  const MAX_TOKENS = 500;

  // Auto-run when you open a job. Set to false to only run on button click.
  const AUTO_RUN = true;

  // When a job is reposted: true = try to close the tab, and if the browser
  // blocks that (normal tabs), go back to the job list instead.
  // false = just show the SKIP panel and stay on the page.
  const CLOSE_ON_REPOST = true;

  // Your resume — the job is matched against this. Replace with your own details.
  var RESUME = "Your Name, your degree and university. Your role (e.g. full-stack + AI engineer). " +
    "Languages: list yours. Frameworks: list yours. ML/AI: list yours. " +
    "Databases, cloud, and tools: list yours. Your years of experience.";

  // What makes a job a bad fit for this candidate.
  const CRITERIA = `The candidate above needs visa sponsorship (international MEng student).
BLOCKERS (verdict must be SKIP if the job requires any):
- U.S. citizenship, green card, or permanent residency
- an active/eligible security clearance (Secret, TS/SCI, Public Trust, etc.)
- clearly a staffing-agency / bench / reposted placeholder listing
GOOD fit (APPLY): a real software / full-stack / AI / data engineering role whose skills
overlap the resume and that does NOT have the blockers above. Otherwise MAYBE.`;

  // ---- API KEY ------------------------------------------------------------
  function getKey() { return GM_getValue('anthropic_api_key', ''); }
  function setKey() {
    const k = prompt('Paste your Anthropic API key (starts with sk-ant-). Stored only in your browser via Tampermonkey.', getKey());
    if (k !== null) { GM_setValue('anthropic_api_key', k.trim()); alert('Saved. Reload the job page.'); }
  }
  GM_registerMenuCommand('Set / change Anthropic API key', setKey);

  // ---- EXTRACT DESCRIPTION FROM PAGE -------------------------------------
  function grab() {
    const selText = (sels) => {
      for (const s of sels) {
        const el = document.querySelector(s);
        if (el && el.innerText.trim().length > 20) return el.innerText.trim();
      }
      return '';
    };
    const longestText = (sels) => {
      let best = '';
      for (const s of sels) {
        document.querySelectorAll(s).forEach((el) => {
          const t = (el.innerText || '').trim();
          if (t.length > best.length) best = t;
        });
      }
      return best;
    };

    const desc = longestText([
      '[data-testid="expandable-text-box"]',
      '#job-details',
      '.jobs-description-content__text',
      '.jobs-description__content',
      '.jobs-box__html-content',
      '.show-more-less-html__markup',
      '.description__text'
    ]);

    let title = '', company = '';
    const raw = document.title
      .replace(/^\(\d+\+?\)\s*/, '')
      .replace(/\s*\|\s*LinkedIn\s*$/i, '');
    let parts = raw.split('|').map((p) => p.trim()).filter(Boolean);
    if (parts.length < 2 && raw.includes(' - ')) {
      parts = raw.split(' - ').map((p) => p.trim()).filter(Boolean);
    }
    if (parts[0]) title = parts[0];
    if (parts[1]) company = parts[1];

    if (!title) title = selText([
      '.job-details-jobs-unified-top-card__job-title',
      '.jobs-unified-top-card__job-title', '.topcard__title'
    ]);
    if (!company) company = selText([
      '.job-details-jobs-unified-top-card__company-name',
      '.jobs-unified-top-card__company-name',
      '.topcard__org-name-link', '.topcard__flavor'
    ]);
    return { title, company, desc };
  }

  // ---- UI PANEL (LEFT side) ----------------------------------------------
  let panel;
  function ensurePanel() {
    if (panel) return panel;
    panel = document.createElement('div');
    panel.style.cssText = `position:fixed;left:18px;bottom:18px;z-index:999999;width:260px;
      font:13px/1.45 -apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#e6e8ec;
      background:#181b22;border:1px solid #2a2f3a;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,.5);
      padding:14px 16px`;
    document.body.appendChild(panel);
    return panel;
  }
  function show(html) { ensurePanel().innerHTML = html; }
  function verdictColor(v) {
    v = (v || '').toUpperCase();
    if (v.includes('APPLY') || v === 'GOOD') return '#2ec16b';
    if (v.includes('SKIP') || v === 'BAD') return '#e06c6c';
    return '#e0b341';
  }

  function pctColor(p) { return p >= 75 ? '#2ec16b' : p >= 50 ? '#e0b341' : '#e06c6c'; }

  function renderResult(job, r) {
    const flag = (label, val) => {
      const bad = !!val;
      return `<div style="display:flex;gap:6px;margin:1px 0;font-size:12px">
        <span style="color:${bad ? '#e06c6c' : '#2ec16b'}">${bad ? '✗' : '✓'}</span>
        <span style="color:#9aa2af">${label}</span></div>`;
    };
    const p = Math.max(0, Math.min(100, parseInt(r.match_percent, 10) || 0));
    const skillLine = (label, val, color) => {
      const v = (val || '').trim();
      if (!v || v.toLowerCase() === 'none') return label === 'Missing' ? '' : '';
      return `<div style="font-size:11px;margin-top:4px"><span style="color:${color}">${label}:</span>
        <span style="color:#9aa2af">${v.slice(0, 120)}</span></div>`;
    };
    show(`
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <b style="font-size:18px;color:${verdictColor(r.verdict)}">${r.verdict || '—'}</b>
        <button id="ljf-close" style="background:none;border:none;color:#9aa2af;cursor:pointer;font-size:16px">×</button>
      </div>
      <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:4px">
        <span style="font-size:30px;font-weight:700;color:${pctColor(p)}">${p}%</span>
        <span style="font-size:11px;color:#9aa2af">skill match</span>
      </div>
      <div style="height:6px;background:#2a2f3a;border-radius:4px;overflow:hidden;margin-bottom:8px">
        <div style="height:100%;width:${p}%;background:${pctColor(p)}"></div>
      </div>
      <div style="color:#e6e8ec;font-size:14px;margin-bottom:6px">${(r.reason || '').slice(0, 60)}</div>
      <div style="color:#9aa2af;font-size:11px;margin-bottom:6px">${(job.title || '').slice(0, 70)}</div>
      ${skillLine('Matched', r.matched_skills, '#2ec16b')}
      ${skillLine('Missing', r.missing_skills, '#e0b341')}
      <div style="margin-top:8px">
      ${flag('Citizenship / green card', r.citizenship_required)}
      ${flag('Security clearance', r.clearance_required)}
      ${flag('5+ yrs required', r.years_required)}
      ${flag('Staffing / repost', r.staffing_or_repost)}
      </div>
      <button id="ljf-again" style="margin-top:10px;background:#1f232c;border:1px solid #2a2f3a;color:#e6e8ec;border-radius:8px;padding:6px 12px;cursor:pointer;font-size:12px">Re-check</button>
    `);
    document.getElementById('ljf-close').onclick = () => { panel.remove(); panel = null; };
    document.getElementById('ljf-again').onclick = run;
  }

  // ---- REPOST DETECTION ---------------------------------------------------
  // The job header shows "Reposted 10 hours ago". Detect it in the DETAIL pane
  // (a <p>/<span>, not inside an <li>) so left-list items don't false-trigger.
  function isReposted() {
    const els = document.querySelectorAll('strong, span, p');
    for (const el of els) {
      const t = (el.textContent || '').trim();
      if (/^reposted\b/i.test(t) && t.length < 40 && !el.closest('li')) return true;
    }
    return false;
  }

  function renderSkip(job) {
    show(`
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
        <b style="font-size:18px;color:#e06c6c">SKIP</b>
        <button id="ljf-close" style="background:none;border:none;color:#9aa2af;cursor:pointer;font-size:16px">×</button>
      </div>
      <div style="color:#e6e8ec;font-size:14px;margin-bottom:8px">Reposted — not checked</div>
      <div style="color:#9aa2af;font-size:11px;margin-bottom:8px">${(job.title || '').slice(0, 70)}</div>
      <button id="ljf-anyway" style="margin-top:4px;background:#1f232c;border:1px solid #2a2f3a;color:#e6e8ec;border-radius:8px;padding:6px 12px;cursor:pointer;font-size:12px">Check anyway</button>
    `);
    document.getElementById('ljf-close').onclick = () => { panel.remove(); panel = null; };
    document.getElementById('ljf-anyway').onclick = () => ask(job);
  }

  // ---- CALL CLAUDE --------------------------------------------------------
  function ask(job) {
    const key = getKey();
    if (!key) { show('No API key set. Tampermonkey menu → "Set / change Anthropic API key".'); return; }

    show('Checking with Claude…');

    const prompt = `MY RESUME:
${RESUME}

${CRITERIA}

Judge ONLY from the DESCRIPTION body. Base "staffing_or_repost" on the description
(bench/staffing-agency/third-party recruiter language), not the title. Do not infer
seniority from pay band or title alone.

TITLE: ${job.title}
COMPANY: ${job.company}
DESCRIPTION:
${job.desc.slice(0, 7000)}

"match_percent" = how well the job's REQUIRED SKILLS/technologies overlap MY RESUME
skills (0-100). Judge skills only, NOT years of experience. 100 = every key skill the
job asks for is on my resume; lower it for each required skill I am missing.

Respond with ONLY a JSON object, no markdown:
{"verdict":"APPLY" or "SKIP" or "MAYBE",
 "match_percent": 0 to 100,
 "reason":"5 to 6 words max, e.g. 'Strong Python/React match'",
 "matched_skills":"comma list of my skills the job wants",
 "missing_skills":"comma list of job skills I lack, or 'none'",
 "citizenship_required": true or false,
 "clearance_required": true or false,
 "years_required": true or false,
 "staffing_or_repost": true or false}`;

    GM_xmlhttpRequest({
      method: 'POST',
      url: 'https://api.anthropic.com/v1/messages',
      headers: {
        'content-type': 'application/json',
        'x-api-key': key,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-direct-browser-access': 'true'
      },
      data: JSON.stringify({
        model: MODEL,
        max_tokens: MAX_TOKENS,
        messages: [{ role: 'user', content: prompt }]
      }),
      onload: (resp) => {
        try {
          const body = JSON.parse(resp.responseText);
          if (body.error) { show('API error: ' + body.error.message); return; }
          const text = (body.content || []).filter(b => b.type === 'text').map(b => b.text).join('');
          const m = text.match(/\{[\s\S]*\}/);
          const r = JSON.parse(m ? m[0] : text);
          renderResult(job, r);
        } catch (e) {
          show('Could not parse response: ' + e.message);
        }
      },
      onerror: () => show('Network error calling the API.')
    });
  }

  function run() {
    const job = grab();
    if (!job.desc) { show('No job description found on this page. Open a specific job first.'); return; }
    lastKey = jobKey();
    if (isReposted()) {                // reposted -> never sent to Claude
      renderSkip(job);
      if (CLOSE_ON_REPOST) {
        window.close();                // works only for script-opened tabs
        setTimeout(() => { if (!window.closed) history.back(); }, 500);
      }
      return;
    }
    ask(job);
  }

  // ---- TRIGGERS -----------------------------------------------------------
  function jobKey() {
    const m = location.href.match(/currentJobId=(\d+)/) || location.href.match(/\/view\/(\d+)/);
    return m ? m[1] : (grab().desc || '').slice(0, 80);
  }

  // Wait for the description to load (LinkedIn renders it async), then auto-run once.
  function autoRun(tries) {
    if (!AUTO_RUN) return;
    tries = tries || 0;
    const job = grab();
    if (job.desc && jobKey() !== lastKey) { run(); return; }
    if (tries < 12) setTimeout(() => autoRun(tries + 1), 600);
  }

  function addButton() {
    if (document.getElementById('ljf-btn')) return;
    const b = document.createElement('button');
    b.id = 'ljf-btn';
    b.textContent = '✓ Check job';
    b.style.cssText = `position:fixed;left:18px;bottom:18px;z-index:999998;
      background:#2563eb;color:#fff;border:none;border-radius:20px;padding:10px 16px;
      font:13px -apple-system,Segoe UI,Roboto,Arial,sans-serif;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.4)`;
    b.onclick = run;
    document.body.appendChild(b);
  }

  let lastKey = '';
  addButton();
  autoRun();

  // LinkedIn is a single-page app — detect job navigation, reset, and re-run.
  let lastUrl = location.href;
  setInterval(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      if (panel) { panel.remove(); panel = null; }
      addButton();
      autoRun();
    }
  }, 1000);
})();
