from flask import Flask, request, Response, stream_with_context, session, redirect, url_for, render_template_string
import anthropic
import time
import os
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'meridianlink-secret-2026')
APP_PASSWORD = os.environ.get('APP_PASSWORD', 'meridianlink2026')
client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a senior competitive intelligence analyst working for MeridianLink.
Produce a deeply researched sales battlecard for MeridianLink Mortgage sales reps.

MeridianLink Mortgage key facts to always use:
- PriceMyLoan® (PML): native PPE with underwriting, MI quotes, closing costs — no extra vendor cost
- Consumer + Mortgage on one platform: single SSO, data pre-fill, cross-sell intelligence
- Insight for Mortgage: 60+ dashboards, 2,000+ data points, peer benchmarking (launched 2025)
- TPO Portal built-in for wholesale and correspondent channels
- 300+ certified integrations (credit, verification, compliance, title, servicing)
- SmartAudit™ compliance and data integrity engine
- Cloud-native, 100% browser-based, no local install
- $2B Centerbridge acquisition (Aug 2025) — institutional stability
- Optimal Blue integration (Jan 2026) — real-time pricing across 150+ investors
- 25+ years serving credit unions, community banks, regulated institutions
- NYSE listed (MLNK)

Research the competitor thoroughly then respond with ONLY a valid JSON object — no markdown, no backticks, no explanation.

{
  "competitor": "Full competitor name",
  "competitor_color": "#hexcolor matching their brand",
  "competitor_color_dim": "rgba version at 0.15 opacity",
  "competitor_color_light": "#lighter hex variant",
  "tagline": "Their marketing tagline or positioning statement",
  "alert": "One key piece of intel reps must know going into a deal (e.g. a recent big win, funding, new feature)",
  "profile": {
    "founded": "Year",
    "hq": "City, State",
    "funding": "Amount or status",
    "investors": "Key investors",
    "key_clients": "Notable clients",
    "channel_focus": "What channels they serve",
    "market_position": "e.g. Challenger / Enterprise / Niche",
    "status": "Public / Private / Startup"
  },
  "positioning": "2-3 sentences on how they position themselves and their core pitch",
  "tags": ["tag1", "tag2", "tag3", "tag4"],
  "matrix": [
    {"category": "Category name", "meridianlink": "ML position", "competitor": "Their position", "winner": "ML or Competitor or Tie", "winner_label": "Short label e.g. MeridianLink or Vesta or Tie"},
    {"category": "Category name", "meridianlink": "ML position", "competitor": "Their position", "winner": "ML or Competitor or Tie", "winner_label": "Short label"}
  ],
  "win_scenarios": ["Scenario where ML wins", "Scenario", "Scenario", "Scenario", "Scenario"],
  "loss_scenarios": ["Scenario where competitor wins", "Scenario", "Scenario", "Scenario"],
  "competitor_strengths": [
    {"title": "Strength title", "detail": "What they do well and how to counter it"}
  ],
  "ml_advantages": [
    {"title": "Advantage title", "detail": "How this directly beats the competitor"}
  ],
  "talk_tracks": [
    {"scenario": "Scenario title e.g. They claim better AI", "body": "Full talk track text the rep should use"},
    {"scenario": "Scenario title", "body": "Full talk track text"},
    {"scenario": "Scenario title", "body": "Full talk track text"},
    {"scenario": "Scenario title", "body": "Full talk track text"}
  ],
  "objections": [
    {"question": "Objection text", "answer": "Full response with bold key points"},
    {"question": "Objection text", "answer": "Full response"},
    {"question": "Objection text", "answer": "Full response"},
    {"question": "Objection text", "answer": "Full response"}
  ],
  "landmine_questions": [
    "Discovery question that exposes a gap",
    "Discovery question",
    "Discovery question",
    "Discovery question",
    "Discovery question",
    "Discovery question"
  ],
  "ml_differentiators": [
    {"title": "Feature title", "detail": "Why this beats the competitor specifically"},
    {"title": "Feature title", "detail": "Why this beats the competitor specifically"},
    {"title": "Feature title", "detail": "Why this beats the competitor specifically"},
    {"title": "Feature title", "detail": "Why this beats the competitor specifically"},
    {"title": "Feature title", "detail": "Why this beats the competitor specifically"}
  ],
  "recent_releases": [
    {"date": "Month Year or Year", "title": "Release title", "detail": "What it does and why it matters"}
  ],
  "persona_cu_bank": [
    "Point for credit union / community bank leadership",
    "Point", "Point", "Point", "Point"
  ],
  "persona_ops_tech": [
    "Point for operations / technology leaders",
    "Point", "Point", "Point", "Point"
  ],
  "before_call": ["Prep tip", "Prep tip", "Prep tip", "Prep tip"],
  "during_discovery": ["Discovery tip", "Tip", "Tip", "Tip", "Tip"],
  "after_deal": ["Post-deal action", "Action", "Action", "Action"],
  "keep_fresh": ["Refresh cadence tip", "What to watch for", "What to watch for", "What to watch for"],
  "one_liner": "The single best one-sentence pitch against this competitor"
}

Include at least 10 matrix rows, 5 win scenarios, 4 loss scenarios, 4 talk tracks, 4 objections, 6 landmine questions.
"""

LOGIN_PAGE = """<!DOCTYPE html>
<html>
<head>
    <title>MeridianLink Battlecard Generator</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0a0d14; color: #fff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
        .card { background: #0f131c; border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 40px; width: 100%; max-width: 380px; }
        .logo { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
        .logo h1 { font-size: 20px; color: #3399ff; }
        .badge { background: rgba(0,113,206,0.15); border: 1px solid #0071ce; color: #3399ff; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
        p { color: rgba(255,255,255,0.55); font-size: 14px; margin-bottom: 24px; }
        label { font-size: 13px; font-weight: 500; color: rgba(255,255,255,0.72); display: block; margin-bottom: 6px; }
        input[type=password] { width: 100%; padding: 10px 14px; font-size: 15px; background: #161b28; border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; color: #fff; margin-bottom: 16px; }
        input[type=password]:focus { outline: none; border-color: #0071ce; }
        button { width: 100%; padding: 11px; background: #0071ce; color: white; border: none; border-radius: 8px; font-size: 15px; cursor: pointer; font-weight: 600; }
        button:hover { background: #0062b3; }
        .error { color: #ef4444; font-size: 13px; margin-bottom: 12px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="logo"><h1>MeridianLink</h1><span class="badge">Internal Tool</span></div>
        <p>Enter the team password to access the Battlecard Generator.</p>
        {% if error %}<div class="error">Incorrect password. Please try again.</div>{% endif %}
        <form method="POST" action="/login">
            <label>Password</label>
            <input type="password" name="password" placeholder="Enter password" autofocus />
            <button type="submit">Sign in</button>
        </form>
    </div>
</body>
</html>"""

GENERATOR_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>MeridianLink Battlecard Generator</title>
<style>
:root {
  --bg: #0a0d14; --bg-el: #0f131c; --bg-surf: #161b28; --bg-hov: #1e2536;
  --border: rgba(255,255,255,0.08); --border-strong: rgba(255,255,255,0.15);
  --text: #ffffff; --text-sec: rgba(255,255,255,0.72); --text-muted: rgba(255,255,255,0.45);
  --blue: #0071ce; --blue-light: #3399ff; --blue-dim: rgba(0,113,206,0.15);
  --win: #10b981; --win-dim: rgba(16,185,129,0.15);
  --lose: #ef4444; --lose-dim: rgba(239,68,68,0.15);
  --tie: #f59e0b; --tie-dim: rgba(245,158,11,0.15);
  --radius: 12px; --radius-sm: 8px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; line-height: 1.6; min-height: 100vh; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 3px; }

.site-header { background: var(--bg-el); border-bottom: 1px solid var(--border); padding: 20px 32px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100; }
.header-left h1 { font-size: 18px; font-weight: 700; letter-spacing: -0.3px; }
.header-left span { font-size: 13px; color: var(--text-muted); margin-top: 2px; display: block; }
.header-badge { background: var(--blue-dim); border: 1px solid var(--blue); color: var(--blue-light); padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.header-right { display: flex; align-items: center; gap: 12px; }
.logout { color: var(--text-muted); font-size: 13px; text-decoration: none; }
.logout:hover { color: var(--text-sec); }

.generator { background: var(--bg-el); border-bottom: 1px solid var(--border); padding: 24px 32px; }
.generator h2 { font-size: 13px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 16px; }
.competitors-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 16px; }
.comp-item { display: flex; align-items: center; gap: 8px; background: var(--bg-surf); border: 1px solid var(--border); border-radius: 8px; padding: 9px 12px; cursor: pointer; transition: border-color 0.15s, background 0.15s; font-size: 13px; color: var(--text-sec); user-select: none; }
.comp-item:hover { border-color: var(--blue); background: var(--blue-dim); }
.comp-item.selected { border-color: var(--blue); background: var(--blue-dim); color: var(--blue-light); font-weight: 500; }
.comp-item input[type=checkbox] { accent-color: var(--blue); width: 14px; height: 14px; flex-shrink: 0; }
.gen-row { display: flex; gap: 10px; align-items: center; }
.gen-row input[type=text] { flex: 1; padding: 9px 14px; font-size: 14px; background: var(--bg-surf); border: 1px solid var(--border); border-radius: 8px; color: var(--text); }
.gen-row input[type=text]:focus { outline: none; border-color: var(--blue); }
.gen-actions { display: flex; gap: 10px; align-items: center; flex-shrink: 0; }
.btn-link { background: none; border: none; color: var(--blue-light); font-size: 12px; cursor: pointer; text-decoration: underline; padding: 0; }
.btn-link.muted { color: var(--text-muted); }
.count-label { font-size: 12px; color: var(--text-muted); }
.btn-gen { padding: 9px 24px; background: var(--blue); color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-gen:hover { background: #0062b3; }
.btn-gen:disabled { background: #2a2f3d; color: var(--text-muted); cursor: default; }

.status-bar { padding: 10px 32px; font-size: 13px; color: var(--text-muted); border-bottom: 1px solid var(--border); min-height: 38px; display: flex; align-items: center; }

#results { display: none; }
.comp-tabs { background: var(--bg-el); border-bottom: 1px solid var(--border); padding: 0 32px; display: flex; gap: 4px; overflow-x: auto; }
.comp-tab { padding: 14px 20px; background: none; border: none; border-bottom: 2px solid transparent; color: var(--text-muted); font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap; transition: all 0.2s; }
.comp-tab:hover { color: var(--text-sec); }
.comp-tab.active { color: var(--blue-light); border-bottom-color: var(--blue-light); }
.comp-tab.loading { color: #444; cursor: default; }

.comp-panel { display: none; }
.comp-panel.active { display: block; }

.inner-nav { background: var(--bg-el); border-bottom: 1px solid var(--border); padding: 0 32px; display: flex; gap: 4px; overflow-x: auto; position: sticky; top: 65px; z-index: 90; }
.tab-btn { padding: 14px 20px; background: none; border: none; border-bottom: 2px solid transparent; color: var(--text-muted); font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap; transition: all 0.2s; }
.tab-btn:hover { color: var(--text-sec); }
.tab-btn.active { color: var(--blue-light); border-bottom-color: var(--blue-light); }

.tab-content { display: none; padding: 32px; max-width: 1200px; margin: 0 auto; }
.tab-content.active { display: block; }

.section-title { font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 16px; margin-top: 32px; }
.section-title:first-child { margin-top: 0; }

.card { background: var(--bg-surf); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px 24px; margin-bottom: 16px; }
.card-title { font-size: 13px; font-weight: 700; margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }

.alert { border-radius: var(--radius-sm); padding: 12px 16px; font-size: 13px; margin-bottom: 16px; display: flex; gap: 10px; align-items: flex-start; }
.alert-blue { background: var(--blue-dim); border: 1px solid rgba(0,113,206,0.4); color: #93c5fd; }
.alert-amber { background: var(--tie-dim); border: 1px solid rgba(245,158,11,0.4); color: #fcd34d; }
.alert-icon { font-size: 16px; flex-shrink: 0; }

.profile-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin-bottom: 16px; }
.profile-stat { background: var(--bg-el); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 14px 16px; }
.profile-stat .label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 4px; }
.profile-stat .value { font-size: 14px; font-weight: 600; color: var(--text); }

.tag { display: inline-block; background: var(--bg-el); border: 1px solid var(--border); border-radius: 20px; padding: 3px 10px; font-size: 11px; color: var(--text-sec); margin: 3px 2px; }

.matrix-table { width: 100%; border-collapse: separate; border-spacing: 0; border-radius: var(--radius); overflow: hidden; background: var(--bg-surf); border: 1px solid var(--border); margin-bottom: 16px; }
.matrix-table th { padding: 14px 20px; font-size: 12px; font-weight: 700; text-align: left; background: var(--bg-el); border-bottom: 1px solid var(--border); }
.matrix-table th.ml-header { background: var(--blue-dim); color: var(--blue-light); border-bottom-color: var(--blue); }
.matrix-table th.comp-header { border-bottom-color: var(--comp-color, #7c3aed); }
.matrix-table td { padding: 12px 20px; border-bottom: 1px solid var(--border); vertical-align: top; font-size: 13px; color: var(--text-sec); }
.matrix-table td:first-child { font-weight: 600; color: var(--text-sec); width: 22%; }
.matrix-table tr:last-child td { border-bottom: none; }
.matrix-table tr:hover td { background: var(--bg-hov); }
.win-pill { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; }
.pill-ml { background: var(--blue-dim); color: var(--blue-light); border: 1px solid var(--blue); }
.pill-comp { border: 1px solid var(--comp-color, #7c3aed); }
.pill-tie { background: var(--tie-dim); color: var(--tie); border: 1px solid var(--tie); }

.win-lose-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.win-box { background: var(--win-dim); border: 1px solid rgba(16,185,129,0.3); border-radius: var(--radius); padding: 18px; }
.lose-box { background: var(--lose-dim); border: 1px solid rgba(239,68,68,0.3); border-radius: var(--radius); padding: 18px; }
.win-box h4 { color: var(--win); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 12px; }
.lose-box h4 { color: var(--lose); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 12px; }
.win-lose-grid ul { list-style: none; }
.win-lose-grid ul li { padding: 5px 0; font-size: 13px; color: var(--text-sec); padding-left: 16px; position: relative; }
.win-box ul li::before { content: '✓'; position: absolute; left: 0; color: var(--win); font-weight: 700; }
.lose-box ul li::before { content: '✗'; position: absolute; left: 0; color: var(--lose); font-weight: 700; }

.diff-list { list-style: none; }
.diff-list li { padding: 9px 0; border-bottom: 1px solid var(--border); font-size: 13px; color: var(--text-sec); display: flex; gap: 10px; align-items: flex-start; }
.diff-list li:last-child { border-bottom: none; }
.diff-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-top: 5px; }
.dot-win { background: var(--win); }
.dot-lose { background: var(--lose); }

.track-card { background: var(--bg-el); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; margin-bottom: 12px; }
.track-header { padding: 12px 18px; background: var(--bg-surf); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; cursor: pointer; user-select: none; }
.track-header:hover { background: var(--bg-hov); }
.track-header h4 { font-size: 13px; font-weight: 600; color: var(--text-sec); }
.track-body { padding: 16px 18px; font-size: 13px; color: var(--text-sec); line-height: 1.7; display: none; }
.track-card.open .track-body { display: block; }
.track-arrow { color: var(--text-muted); transition: transform 0.2s; font-size: 12px; }
.track-card.open .track-arrow { transform: rotate(180deg); }

.obj-card { border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden; margin-bottom: 10px; }
.obj-q { background: var(--bg-el); padding: 12px 16px; font-size: 13px; color: var(--text-muted); font-style: italic; border-bottom: 1px solid var(--border); }
.obj-q::before { content: '"'; }
.obj-q::after { content: '"'; }
.obj-a { background: var(--bg-surf); padding: 12px 16px; font-size: 13px; color: var(--text-sec); line-height: 1.65; }

.landmine-list { list-style: none; }
.landmine-list li { display: flex; gap: 12px; padding: 12px 16px; background: var(--bg-el); border: 1px solid var(--border); border-radius: var(--radius-sm); margin-bottom: 8px; font-size: 13px; color: var(--text-sec); align-items: flex-start; }
.lm-icon { font-size: 16px; flex-shrink: 0; margin-top: 1px; }

.release-list { list-style: none; }
.release-item { display: flex; gap: 14px; padding: 14px 0; border-bottom: 1px solid var(--border); align-items: flex-start; }
.release-item:last-child { border-bottom: none; }
.release-date { font-size: 11px; color: var(--text-muted); white-space: nowrap; min-width: 70px; font-weight: 600; padding-top: 2px; }
.release-info h5 { font-size: 13px; font-weight: 600; color: var(--text); margin-bottom: 3px; }
.release-info p { font-size: 12px; color: var(--text-sec); }

.one-liner-card { background: var(--blue-dim); border: 1px solid var(--blue); border-radius: var(--radius); padding: 20px 24px; margin-bottom: 16px; font-size: 15px; font-style: italic; line-height: 1.7; color: var(--text); }

.loading-panel { padding: 60px 32px; text-align: center; color: var(--text-muted); font-size: 14px; }

@media (max-width: 768px) {
  .two-col, .win-lose-grid { grid-template-columns: 1fr; }
  .competitors-grid { grid-template-columns: repeat(2, 1fr); }
  .tab-content, .generator { padding: 16px; }
}
@media print {
  .generator, .site-header, .comp-tabs { display: none !important; }
  .tab-content { display: block !important; }
  .track-body { display: block !important; }
}
</style>
</head>
<body>

<header class="site-header">
  <div class="header-left">
    <h1>🏦 MeridianLink Mortgage — Battlecard Generator</h1>
    <span>Competitive intelligence for LOS sales</span>
  </div>
  <div class="header-right">
    <span class="header-badge">MeridianLink Internal Use Only</span>
    <a class="logout" href="/logout">Sign out</a>
  </div>
</header>

<div class="generator">
  <h2>Select competitors to research</h2>
  <div class="competitors-grid" id="grid">
    <label class="comp-item"><input type="checkbox" value="Encompass by ICE Mortgage Technology" onchange="updateCount()"> Encompass (ICE)</label>
    <label class="comp-item"><input type="checkbox" value="Calyx Point" onchange="updateCount()"> Calyx Point</label>
    <label class="comp-item"><input type="checkbox" value="BytePro" onchange="updateCount()"> BytePro</label>
    <label class="comp-item"><input type="checkbox" value="Mortgage Cadence" onchange="updateCount()"> Mortgage Cadence</label>
    <label class="comp-item"><input type="checkbox" value="Vesta LOS" onchange="updateCount()"> Vesta</label>
    <label class="comp-item"><input type="checkbox" value="BlueSage LOS" onchange="updateCount()"> BlueSage</label>
    <label class="comp-item"><input type="checkbox" value="Wilqo LOS" onchange="updateCount()"> Wilqo</label>
    <label class="comp-item"><input type="checkbox" value="Blend" onchange="updateCount()"> Blend</label>
    <label class="comp-item"><input type="checkbox" value="LendingPad" onchange="updateCount()"> LendingPad</label>
    <label class="comp-item"><input type="checkbox" value="Finastra Mortgagebot" onchange="updateCount()"> Finastra Mortgagebot</label>
    <label class="comp-item"><input type="checkbox" value="Dark Matter Technologies" onchange="updateCount()"> Dark Matter Technologies</label>
  </div>
  <div class="gen-row">
    <input type="text" id="custom" placeholder="Or type any other competitor name..."/>
    <div class="gen-actions">
      <button class="btn-link" onclick="selectAll()">Select all</button>
      <button class="btn-link muted" onclick="clearAll()">Clear</button>
      <span class="count-label" id="count">0 selected</span>
      <button class="btn-gen" id="btn" onclick="generate()">Generate Battlecards</button>
    </div>
  </div>
</div>

<div class="status-bar" id="status"></div>

<div id="results">
  <div class="comp-tabs" id="comp-tabs"></div>
  <div id="comp-panels"></div>
</div>

<script>
function updateCount() {
  const n = document.querySelectorAll('#grid input:checked').length;
  document.getElementById('count').textContent = n + ' selected';
  document.querySelectorAll('.comp-item').forEach(el => el.classList.toggle('selected', el.querySelector('input').checked));
}
function selectAll() { document.querySelectorAll('#grid input').forEach(cb => cb.checked = true); updateCount(); }
function clearAll() { document.querySelectorAll('#grid input').forEach(cb => cb.checked = false); document.getElementById('custom').value=''; updateCount(); }
document.getElementById('custom').addEventListener('keydown', e => { if(e.key==='Enter') generate(); });

function switchComp(id) {
  document.querySelectorAll('.comp-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.comp-panel').forEach(p => p.classList.remove('active'));
  document.querySelector('[data-comp="'+id+'"]').classList.add('active');
  document.getElementById('cpanel-'+id).classList.add('active');
}

function switchTab(panelId, tabId, btn) {
  const panel = document.getElementById('cpanel-'+panelId);
  panel.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  panel.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  panel.querySelector('#tc-'+tabId).classList.add('active');
  btn.classList.add('active');
}

function toggleTrack(header) { header.parentElement.classList.toggle('open'); }

function esc(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function buildCard(id, d) {
  const cc = d.competitor_color || '#7c3aed';
  const ccDim = d.competitor_color_dim || 'rgba(124,58,237,0.15)';
  const ccLight = d.competitor_color_light || '#a78bfa';
  const cName = esc(d.competitor);

  // ── TAB 1: MATRIX ──
  let matrixHTML = '';
  if (d.alert) {
    matrixHTML += `<div class="alert alert-amber"><span class="alert-icon">⚡</span><div>${esc(d.alert)}</div></div>`;
  }
  matrixHTML += `<p class="section-title">Head-to-Head Feature Comparison</p>`;
  matrixHTML += `<table class="matrix-table" style="--comp-color:${cc}">
    <thead><tr>
      <th>Category</th>
      <th class="ml-header">🔵 MeridianLink Mortgage</th>
      <th class="comp-header" style="background:${ccDim};color:${ccLight}">● ${cName}</th>
      <th>Winner</th>
    </tr></thead><tbody>`;
  (d.matrix||[]).forEach(row => {
    let pillClass, pillStyle, pillLabel;
    if (row.winner === 'ML') {
      pillClass = 'win-pill pill-ml'; pillStyle = ''; pillLabel = 'MeridianLink';
    } else if (row.winner === 'Tie') {
      pillClass = 'win-pill pill-tie'; pillStyle = ''; pillLabel = row.winner_label || 'Tie';
    } else {
      pillClass = 'win-pill pill-comp'; pillStyle = `style="background:${ccDim};color:${ccLight}"`;
      pillLabel = row.winner_label || cName;
    }
    matrixHTML += `<tr><td>${esc(row.category)}</td><td>${esc(row.meridianlink)}</td><td>${esc(row.competitor)}</td><td><span class="${pillClass}" ${pillStyle}>${esc(pillLabel)}</span></td></tr>`;
  });
  matrixHTML += `</tbody></table>`;
  matrixHTML += `<p class="section-title">Quick Win / Loss Guide</p><div class="win-lose-grid">
    <div class="win-box"><h4>✅ MeridianLink Wins When…</h4><ul>`;
  (d.win_scenarios||[]).forEach(s => { matrixHTML += `<li>${esc(s)}</li>`; });
  matrixHTML += `</ul></div><div class="lose-box"><h4>⚠️ Watch Out — ${cName} May Win When…</h4><ul>`;
  (d.loss_scenarios||[]).forEach(s => { matrixHTML += `<li>${esc(s)}</li>`; });
  matrixHTML += `</ul></div></div>`;

  // ── TAB 2: COMPETITOR DEEP DIVE ──
  let compHTML = '';
  if (d.alert) {
    compHTML += `<div class="alert alert-amber"><span class="alert-icon">⚡</span><div>${esc(d.alert)}</div></div>`;
  }
  compHTML += `<p class="section-title">Company Profile</p><div class="profile-grid">`;
  const pf = d.profile || {};
  ['founded','hq','funding','investors','key_clients','channel_focus','market_position','status'].forEach(k => {
    const label = k.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
    compHTML += `<div class="profile-stat"><div class="label">${label}</div><div class="value">${esc(pf[k]||'N/A')}</div></div>`;
  });
  compHTML += `</div>`;
  compHTML += `<p class="section-title">How They Position Themselves</p>
    <div class="card"><p style="color:var(--text-sec);font-size:13px;line-height:1.7">${esc(d.positioning)}</p>
    <div style="margin-top:12px">`;
  (d.tags||[]).forEach(t => { compHTML += `<span class="tag">${esc(t)}</span>`; });
  compHTML += `</div></div>`;
  compHTML += `<p class="section-title">Where They Win vs. Where You Win</p><div class="two-col">
    <div class="card"><div class="card-title" style="color:${ccLight}">● Their Strengths — Acknowledge &amp; Counter</div><ul class="diff-list">`;
  (d.competitor_strengths||[]).forEach(s => {
    compHTML += `<li><span class="diff-dot dot-lose"></span><div><strong>${esc(s.title)}:</strong> ${esc(s.detail)}</div></li>`;
  });
  compHTML += `</ul></div><div class="card"><div class="card-title" style="color:var(--blue-light)">🔵 Your Advantages — Lead With These</div><ul class="diff-list">`;
  (d.ml_advantages||[]).forEach(s => {
    compHTML += `<li><span class="diff-dot dot-win"></span><div><strong>${esc(s.title)}:</strong> ${esc(s.detail)}</div></li>`;
  });
  compHTML += `</ul></div></div>`;
  compHTML += `<p class="section-title">Talk Tracks</p>`;
  (d.talk_tracks||[]).forEach((t,i) => {
    compHTML += `<div class="track-card${i===0?' open':''}"><div class="track-header" onclick="toggleTrack(this)"><h4>🎯 ${esc(t.scenario)}</h4><span class="track-arrow">▼</span></div><div class="track-body"><p>${esc(t.body)}</p></div></div>`;
  });
  compHTML += `<p class="section-title">Objection Handling</p>`;
  (d.objections||[]).forEach(o => {
    compHTML += `<div class="obj-card"><div class="obj-q">${esc(o.question)}</div><div class="obj-a">${esc(o.answer)}</div></div>`;
  });
  compHTML += `<p class="section-title">💣 Landmine Questions — Plant These in Discovery</p><ul class="landmine-list">`;
  (d.landmine_questions||[]).forEach(q => {
    compHTML += `<li><span class="lm-icon">💣</span><span>${esc(q)}</span></li>`;
  });
  compHTML += `</ul>`;

  // ── TAB 3: ML WINS ──
  let mlHTML = `<p class="section-title">MeridianLink Mortgage — Your Differentiators</p><div class="two-col">
    <div class="card"><div class="card-title" style="color:var(--blue-light)">🔵 Unique to MeridianLink</div><ul class="diff-list">`;
  (d.ml_differentiators||[]).forEach(s => {
    mlHTML += `<li><span class="diff-dot dot-win"></span><div><strong>${esc(s.title)}:</strong> ${esc(s.detail)}</div></li>`;
  });
  mlHTML += `</ul></div><div class="card"><div class="card-title" style="color:var(--blue-light)">📈 Recent Releases</div><ul class="release-list">`;
  (d.recent_releases||[]).forEach(r => {
    mlHTML += `<li class="release-item"><span class="release-date">${esc(r.date)}</span><div class="release-info"><h5>${esc(r.title)}</h5><p>${esc(r.detail)}</p></div></li>`;
  });
  mlHTML += `</ul></div></div>`;
  mlHTML += `<p class="section-title">Proof Points by Persona</p><div class="two-col">
    <div class="card"><div class="card-title">🏛️ For Credit Union / Community Bank Leadership</div><ul class="diff-list">`;
  (d.persona_cu_bank||[]).forEach(p => { mlHTML += `<li><span class="diff-dot dot-win"></span>${esc(p)}</li>`; });
  mlHTML += `</ul></div><div class="card"><div class="card-title">🛠️ For Operations / Technology Leaders</div><ul class="diff-list">`;
  (d.persona_ops_tech||[]).forEach(p => { mlHTML += `<li><span class="diff-dot dot-win"></span>${esc(p)}</li>`; });
  mlHTML += `</ul></div></div>`;

  // ── TAB 4: HOW TO USE ──
  let howHTML = `<p class="section-title">How to Use This Battlecard</p><div class="two-col">
    <div class="card"><div class="card-title">📞 Before the Call</div><ul class="diff-list">`;
  (d.before_call||[]).forEach(p => { howHTML += `<li><span class="diff-dot dot-win"></span>${esc(p)}</li>`; });
  howHTML += `</ul></div><div class="card"><div class="card-title">🗣️ During Discovery</div><ul class="diff-list">`;
  (d.during_discovery||[]).forEach(p => { howHTML += `<li><span class="diff-dot dot-win"></span>${esc(p)}</li>`; });
  howHTML += `</ul></div><div class="card"><div class="card-title">📋 After a Win or Loss</div><ul class="diff-list">`;
  (d.after_deal||[]).forEach(p => { howHTML += `<li><span class="diff-dot dot-win"></span>${esc(p)}</li>`; });
  howHTML += `</ul></div><div class="card"><div class="card-title">🔄 Keep It Fresh</div><ul class="diff-list">`;
  (d.keep_fresh||[]).forEach(p => { howHTML += `<li><span class="diff-dot dot-win"></span>${esc(p)}</li>`; });
  howHTML += `</ul></div></div>`;
  howHTML += `<p class="section-title">The One-Liner for Every Deal</p>
    <div class="one-liner-card">${esc(d.one_liner)}</div>`;

  return `
    <div class="inner-nav">
      <button class="tab-btn active" onclick="switchTab('${id}','matrix-${id}',this)">📊 Comparison Matrix</button>
      <button class="tab-btn" onclick="switchTab('${id}','comp-${id}',this)">● ${cName}</button>
      <button class="tab-btn" onclick="switchTab('${id}','ml-${id}',this)">🔵 MeridianLink Wins</button>
      <button class="tab-btn" onclick="switchTab('${id}','how-${id}',this)">🎯 How to Use</button>
    </div>
    <section id="tc-matrix-${id}" class="tab-content active">${matrixHTML}</section>
    <section id="tc-comp-${id}" class="tab-content">${compHTML}</section>
    <section id="tc-ml-${id}" class="tab-content">${mlHTML}</section>
    <section id="tc-how-${id}" class="tab-content">${howHTML}</section>
  `;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function generate() {
  const checked = [...document.querySelectorAll('#grid input:checked')].map(cb => cb.value);
  const custom = document.getElementById('custom').value.trim();
  if (custom) checked.push(custom);
  if (!checked.length) { alert('Select at least one competitor.'); return; }

  const btn = document.getElementById('btn');
  const status = document.getElementById('status');
  const results = document.getElementById('results');
  const tabsEl = document.getElementById('comp-tabs');
  const panelsEl = document.getElementById('comp-panels');

  btn.disabled = true;
  tabsEl.innerHTML = '';
  panelsEl.innerHTML = '';
  results.style.display = 'block';

  checked.forEach((comp, i) => {
    const id = 'c' + i;
    const shortName = comp.replace(' LOS','').replace(' by ICE Mortgage Technology',' (ICE)');
    const tab = document.createElement('button');
    tab.className = 'comp-tab loading' + (i===0?' active':'');
    tab.dataset.comp = id;
    tab.textContent = shortName;
    tab.onclick = () => switchComp(id);
    tabsEl.appendChild(tab);

    const panel = document.createElement('div');
    panel.id = 'cpanel-' + id;
    panel.className = 'comp-panel' + (i===0?' active':'');
    panel.innerHTML = '<div class="loading-panel">Researching ' + shortName + '...</div>';
    panelsEl.appendChild(panel);
  });

  for (let i = 0; i < checked.length; i++) {
    const comp = checked[i];
    const id = 'c' + i;
    const tab = document.querySelector('[data-comp="'+id+'"]');
    const panel = document.getElementById('cpanel-'+id);

    if (i > 0) {
      for (let s = 15; s > 0; s--) {
        status.textContent = 'Waiting ' + s + 's before next card...';
        await sleep(1000);
      }
    }

    status.textContent = 'Researching ' + comp + '...';

    try {
      const resp = await fetch('/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({competitor: comp})
      });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let raw = '';

      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        for (const line of chunk.split('\\n')) {
          if (line.startsWith('data: ')) {
            const d = line.slice(6);
            if (d.startsWith('STATUS:')) {
              status.textContent = d.slice(7);
            } else if (d === 'DONE') {
              try {
                const parsed = JSON.parse(raw);
                panel.innerHTML = buildCard(id, parsed);
                tab.classList.remove('loading');
                tab.textContent = parsed.competitor || comp;
              } catch(e) {
                panel.innerHTML = '<div class="loading-panel">Could not parse response. Try again.</div>';
              }
            } else {
              raw += d + '\\n';
            }
          }
        }
      }
    } catch(e) {
      panel.innerHTML = '<div class="loading-panel">Error generating battlecard. Check PowerShell.</div>';
    }
  }

  status.textContent = 'All done! ' + checked.length + ' battlecard' + (checked.length > 1 ? 's' : '') + ' generated.';
  btn.disabled = false;
}
</script>
</body>
</html>"""


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = False
    if request.method == 'POST':
        if request.form.get('password') == APP_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        error = True
    return render_template_string(LOGIN_PAGE, error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return GENERATOR_PAGE


@app.route('/generate', methods=['POST'])
def generate():
    if not session.get('logged_in'):
        return Response('Unauthorized', status=401)

    competitor = request.json.get('competitor', '')

    def stream():
        yield f"data: STATUS:Researching {competitor}...\n\n"

        for attempt in range(5):
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=4000,
                    system=SYSTEM_PROMPT,
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                    messages=[{
                        "role": "user",
                        "content": f"Research the mortgage LOS competitor '{competitor}' vs MeridianLink Mortgage and produce the battlecard JSON."
                    }]
                )
                break
            except anthropic.APIStatusError as e:
                if e.status_code in (429, 529) and attempt < 4:
                    wait = 30 if e.status_code == 429 else 10
                    yield f"data: STATUS:API busy, retrying in {wait}s... (attempt {attempt + 2} of 5)\n\n"
                    time.sleep(wait)
                else:
                    yield "data: {}\n\n"
                    yield "data: DONE\n\n"
                    return

        raw = ""
        for block in response.content:
            if hasattr(block, 'text'):
                raw += block.text

        # Strip any markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3].strip()

        for line in raw.split('\n'):
            yield f"data: {line}\n\n"

        yield "data: DONE\n\n"

    return Response(stream_with_context(stream()), mimetype='text/event-stream')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
