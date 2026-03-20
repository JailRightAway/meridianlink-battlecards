from flask import Flask, request, Response, stream_with_context, session, redirect, url_for, render_template_string
import anthropic
import time
import os
import re

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'meridianlink-secret-2026')
APP_PASSWORD = os.environ.get('APP_PASSWORD', 'meridianlink2026')
client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a senior competitive intelligence analyst at MeridianLink Mortgage.
Research the given competitor and produce a battlecard using EXACTLY the section format below.
Each section starts with a header in square brackets on its own line.
Do not add any text before [OVERVIEW]. Do not skip any section.

MeridianLink key strengths to always reference:
- PriceMyLoan (PML): native built-in pricing engine, no extra PPE vendor cost
- Consumer + Mortgage on one platform: single sign-on, data pre-fill, cross-sell intelligence
- Insight for Mortgage: 60+ dashboards, 2000+ data points, peer benchmarking (launched 2025)
- TPO Portal built-in for wholesale and correspondent channels
- 300+ certified integrations across credit, verification, compliance, title, servicing
- SmartAudit compliance and data integrity engine
- Cloud-native, 100% browser-based, no local install, no VPN
- $2B Centerbridge acquisition (Aug 2025) - institutional stability
- Optimal Blue integration (Jan 2026) - real-time pricing across 150+ investors
- 25+ years serving credit unions and community banks

[OVERVIEW]
Write 2-3 sentences: who they are, market position, parent company if any.

[ALERT]
One sentence: the single most important piece of intel a rep needs before a deal.

[PROFILE]
Founded: XXXX
HQ: City, State
Funding: $XXX or status
Investors: Names
Key Clients: Notable clients
Channel Focus: What channels
Status: Public/Private/Startup

[POSITIONING]
Write 2-3 sentences on how they pitch themselves. Include their tagline if known.

[TAGS]
tag1, tag2, tag3, tag4, tag5

[MATRIX]
Write exactly 12 rows. Each row MUST have EXACTLY 4 columns separated by the | character.
Column 1: Feature name (short, e.g. Cloud Architecture)
Column 2: MeridianLink position on this feature (1-2 sentences)
Column 3: The competitor position on this feature (1-2 sentences)
Column 4: Winner - write ONLY one of: ML or Competitor or Tie

Do NOT skip any column. Do NOT add a header row. Every row needs all 4 columns.

Example rows:
Cloud Architecture|100% cloud-native browser-based SaaS, no local install|Cloud-native open API platform, modern infrastructure|Tie
Pricing Engine|Native PriceMyLoan PPE included, no extra vendor cost|Relies on third-party Lender Price integration|ML
AI Capabilities|SmartAudit compliance engine, rules-based automation|AI-native agent factory, autonomous document interpretation|Competitor

[WIN_SCENARIOS]
Write 6+ bullet points starting with - describing when MeridianLink wins

[LOSS_SCENARIOS]
Write 4+ bullet points starting with - describing when the competitor wins

[COMPETITOR_STRENGTHS]
Write 3+ items. Each item: **Title**: Explanation and how to counter it.

[ML_ADVANTAGES]
Write 4+ items. Each item: **Title**: How this directly beats the competitor.

[TALK_TRACK_1]
Scenario: Title of the scenario
Response: Full paragraph of what the rep should say.

[TALK_TRACK_2]
Scenario: Title of the scenario
Response: Full paragraph of what the rep should say.

[TALK_TRACK_3]
Scenario: Title of the scenario
Response: Full paragraph of what the rep should say.

[TALK_TRACK_4]
Scenario: Title of the scenario
Response: Full paragraph of what the rep should say.

[OBJECTION_1]
Question: The objection text
Answer: Full response the rep should give.

[OBJECTION_2]
Question: The objection text
Answer: Full response the rep should give.

[OBJECTION_3]
Question: The objection text
Answer: Full response the rep should give.

[OBJECTION_4]
Question: The objection text
Answer: Full response the rep should give.

[LANDMINE_QUESTIONS]
Write 6+ bullet points starting with - each being a discovery question that exposes a competitor weakness.

[ML_DIFFERENTIATORS]
Write 5+ items. Each item: **Title**: Why this beats the competitor specifically.

[RECENT_RELEASES]
Write 4+ items. Each item: DATE | Title | What it does and why it matters.

[PERSONA_CU_BANK]
Write 5+ bullet points starting with - for credit union / community bank leadership.

[PERSONA_OPS_TECH]
Write 5+ bullet points starting with - for operations / technology leaders.

[BEFORE_CALL]
Write 4+ bullet points starting with - on how to prep before the call.

[DURING_DISCOVERY]
Write 5+ bullet points starting with - on what to do during discovery.

[AFTER_DEAL]
Write 4+ bullet points starting with - on what to do after a win or loss.

[KEEP_FRESH]
Write 4+ bullet points starting with - on how to keep the battlecard current.

[ONE_LINER]
Write one powerful sentence that is the best pitch against this competitor.
"""

def parse_sections(text):
    """Parse the section-based text into a dictionary."""
    sections = {}
    current_key = None
    current_lines = []

    for line in text.split('\n'):
        header_match = re.match(r'^\[([A-Z_0-9]+)\]$', line.strip())
        if header_match:
            if current_key:
                sections[current_key] = '\n'.join(current_lines).strip()
            current_key = header_match.group(1)
            current_lines = []
        elif current_key:
            current_lines.append(line)

    if current_key:
        sections[current_key] = '\n'.join(current_lines).strip()

    return sections


def parse_profile(text):
    profile = {}
    for line in text.split('\n'):
        if ':' in line:
            key, _, val = line.partition(':')
            profile[key.strip()] = val.strip()
    return profile


def parse_matrix(text):
    rows = []
    for line in text.split('\n'):
        line = line.strip()
        if not line or '|' not in line:
            continue
        if line.lower().startswith('category') or line.lower().startswith('feature'):
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 4 and parts[0] and parts[1] and parts[2]:
            winner = parts[3].strip() if len(parts) > 3 else 'Tie'
            w = winner.lower()
            if 'ml' in w or 'meridian' in w:
                winner = 'ML'
            elif 'tie' in w or 'comparable' in w or 'equal' in w or 'both' in w:
                winner = 'Tie'
            else:
                winner = 'Competitor'
            rows.append({
                'feature': parts[0],
                'ml': parts[1],
                'comp': parts[2],
                'winner': winner
            })
    return rows


def parse_bullets(text):
    items = []
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith('- '):
            items.append(line[2:])
        elif line.startswith('• '):
            items.append(line[2:])
    return items


def parse_bold_items(text):
    items = []
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith('**'):
            match = re.match(r'\*\*(.+?)\*\*:?\s*(.*)', line)
            if match:
                items.append({'title': match.group(1), 'detail': match.group(2)})
        elif line and not line.startswith('#'):
            if items:
                items[-1]['detail'] += ' ' + line
    return items


def parse_releases(text):
    items = []
    for line in text.split('\n'):
        line = line.strip()
        if '|' in line:
            parts = [p.strip() for p in line.split('|', 2)]
            if len(parts) >= 3:
                items.append({'date': parts[0], 'title': parts[1], 'detail': parts[2]})
    return items


def parse_track(text):
    scenario = ''
    response = ''
    for line in text.split('\n'):
        if line.startswith('Scenario:'):
            scenario = line.replace('Scenario:', '').strip()
        elif line.startswith('Response:'):
            response = line.replace('Response:', '').strip()
        elif response:
            response += ' ' + line.strip()
    return {'scenario': scenario, 'response': response.strip()}


def parse_objection(text):
    question = ''
    answer = ''
    in_answer = False
    for line in text.split('\n'):
        if line.startswith('Question:'):
            question = line.replace('Question:', '').strip()
        elif line.startswith('Answer:'):
            answer = line.replace('Answer:', '').strip()
            in_answer = True
        elif in_answer and line.strip():
            answer += ' ' + line.strip()
    return {'question': question, 'answer': answer.strip()}


def build_battlecard_html(s, comp_name):
    """Build the full Vesta-style HTML for one competitor."""

    profile = parse_profile(s.get('PROFILE', ''))
    matrix = parse_matrix(s.get('MATRIX', ''))
    win_scenarios = parse_bullets(s.get('WIN_SCENARIOS', ''))
    loss_scenarios = parse_bullets(s.get('LOSS_SCENARIOS', ''))
    comp_strengths = parse_bold_items(s.get('COMPETITOR_STRENGTHS', ''))
    ml_advantages = parse_bold_items(s.get('ML_ADVANTAGES', ''))
    talk_tracks = [parse_track(s.get(f'TALK_TRACK_{i}', '')) for i in range(1, 5)]
    objections = [parse_objection(s.get(f'OBJECTION_{i}', '')) for i in range(1, 5)]
    landmines = parse_bullets(s.get('LANDMINE_QUESTIONS', ''))
    ml_diff = parse_bold_items(s.get('ML_DIFFERENTIATORS', ''))
    releases = parse_releases(s.get('RECENT_RELEASES', ''))
    persona_cu = parse_bullets(s.get('PERSONA_CU_BANK', ''))
    persona_ops = parse_bullets(s.get('PERSONA_OPS_TECH', ''))
    before_call = parse_bullets(s.get('BEFORE_CALL', ''))
    during_disc = parse_bullets(s.get('DURING_DISCOVERY', ''))
    after_deal = parse_bullets(s.get('AFTER_DEAL', ''))
    keep_fresh = parse_bullets(s.get('KEEP_FRESH', ''))
    tags = [t.strip() for t in s.get('TAGS', '').split(',') if t.strip()]
    alert = s.get('ALERT', '')
    overview = s.get('OVERVIEW', '')
    positioning = s.get('POSITIONING', '')
    one_liner = s.get('ONE_LINER', '')

    def esc(t):
        return str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

    def diff_list(items, dot_class):
        if not items:
            return '<li><span class="diff-dot ' + dot_class + '"></span>No data found.</li>'
        return ''.join(f'<li><span class="diff-dot {dot_class}"></span>{esc(i)}</li>' for i in items)

    def bold_list(items, dot_class):
        if not items:
            return '<li><span class="diff-dot ' + dot_class + '"></span>No data found.</li>'
        return ''.join(f'<li><span class="diff-dot {dot_class}"></span><div><strong>{esc(i["title"])}:</strong> {esc(i["detail"])}</div></li>' for i in items)

    # Matrix rows
    matrix_rows = ''
    for row in matrix:
        w = row['winner'].strip()
        if w == 'ML':
            pill = '<span class="win-pill pill-ml">MeridianLink</span>'
        elif w == 'Tie':
            pill = '<span class="win-pill pill-tie">Tie</span>'
        else:
            pill = f'<span class="win-pill pill-comp">{esc(comp_name)}</span>'
        matrix_rows += f'<tr><td>{esc(row["feature"])}</td><td>{esc(row["ml"])}</td><td>{esc(row["comp"])}</td><td>{pill}</td></tr>'

    # Talk tracks
    tracks_html = ''
    for i, t in enumerate(talk_tracks):
        if t['scenario']:
            open_class = ' open' if i == 0 else ''
            tracks_html += f'''<div class="track-card{open_class}">
  <div class="track-header" onclick="toggleTrack(this)">
    <h4>🎯 {esc(t["scenario"])}</h4>
    <span class="track-arrow">▼</span>
  </div>
  <div class="track-body"><p>{esc(t["response"])}</p></div>
</div>'''

    # Objections
    obj_html = ''
    for o in objections:
        if o['question']:
            obj_html += f'''<div class="obj-card">
  <div class="obj-q">{esc(o["question"])}</div>
  <div class="obj-a">{esc(o["answer"])}</div>
</div>'''

    # Landmines
    landmine_html = ''.join(f'<li><span class="lm-icon">💣</span><span>{esc(q)}</span></li>' for q in landmines)

    # Profile stats
    profile_html = ''
    for k, v in profile.items():
        profile_html += f'<div class="profile-stat"><div class="label">{esc(k)}</div><div class="value">{esc(v)}</div></div>'

    # Tags
    tags_html = ''.join(f'<span class="tag">{esc(t)}</span>' for t in tags)

    # Recent releases
    releases_html = ''
    for r in releases:
        releases_html += f'''<li class="release-item">
  <span class="release-date">{esc(r["date"])}</span>
  <div class="release-info"><h5>{esc(r["title"])}</h5><p>{esc(r["detail"])}</p></div>
</li>'''

    alert_html = f'<div class="alert alert-amber"><span class="alert-icon">⚡</span><div>{esc(alert)}</div></div>' if alert else ''

    uid = comp_name.replace(' ', '_').replace('/', '_')

    return f'''
<div class="inner-nav" id="nav-{uid}">
  <button class="tab-btn active" onclick="switchInnerTab('{uid}','matrix')">📊 Comparison Matrix</button>
  <button class="tab-btn" onclick="switchInnerTab('{uid}','deep')">🔍 {esc(comp_name)}</button>
  <button class="tab-btn" onclick="switchInnerTab('{uid}','mlwins')">🔵 MeridianLink Wins</button>
  <button class="tab-btn" onclick="switchInnerTab('{uid}','howto')">🎯 How to Use</button>
</div>

<!-- TAB: MATRIX -->
<section id="{uid}-matrix" class="tab-content active" data-panel="{uid}">
  {alert_html}
  <p class="section-title">Head-to-Head Feature Comparison</p>
  <table class="matrix-table">
    <thead>
      <tr>
        <th>Category</th>
        <th class="ml-header">🔵 MeridianLink Mortgage</th>
        <th class="comp-header">● {esc(comp_name)}</th>
        <th>Winner</th>
      </tr>
    </thead>
    <tbody>{matrix_rows}</tbody>
  </table>
  <p class="section-title">Quick Win / Loss Guide</p>
  <div class="win-lose-grid">
    <div class="win-box">
      <h4>✅ MeridianLink Wins When…</h4>
      <ul>{chr(10).join(f"<li>{esc(s)}</li>" for s in win_scenarios)}</ul>
    </div>
    <div class="lose-box">
      <h4>⚠️ Watch Out — {esc(comp_name)} May Win When…</h4>
      <ul>{chr(10).join(f"<li>{esc(s)}</li>" for s in loss_scenarios)}</ul>
    </div>
  </div>
</section>

<!-- TAB: DEEP DIVE -->
<section id="{uid}-deep" class="tab-content" data-panel="{uid}">
  {alert_html}
  <p class="section-title">Company Profile</p>
  <div class="profile-grid">{profile_html}</div>
  <p class="section-title">How They Position Themselves</p>
  <div class="card">
    <p style="color:var(--text-secondary);font-size:13px;line-height:1.7">{esc(positioning)}</p>
    <div style="margin-top:12px">{tags_html}</div>
  </div>
  <p class="section-title">Where They Win vs. Where You Win</p>
  <div class="two-col">
    <div class="card">
      <div class="card-title" style="color:#a78bfa">● Their Strengths — Acknowledge &amp; Counter</div>
      <ul class="diff-list">{bold_list(comp_strengths, "dot-lose")}</ul>
    </div>
    <div class="card">
      <div class="card-title" style="color:var(--ml-blue-light)">🔵 Your Advantages — Lead With These</div>
      <ul class="diff-list">{bold_list(ml_advantages, "dot-win")}</ul>
    </div>
  </div>
  <p class="section-title">Talk Tracks</p>
  {tracks_html}
  <p class="section-title">Objection Handling</p>
  {obj_html}
  <p class="section-title">💣 Landmine Questions — Plant These in Discovery</p>
  <ul class="landmine-list">{landmine_html}</ul>
</section>

<!-- TAB: ML WINS -->
<section id="{uid}-mlwins" class="tab-content" data-panel="{uid}">
  <p class="section-title">MeridianLink Mortgage — Your Differentiators</p>
  <div class="two-col">
    <div class="card">
      <div class="card-title" style="color:var(--ml-blue-light)">🔵 Unique to MeridianLink</div>
      <ul class="diff-list">{bold_list(ml_diff, "dot-win")}</ul>
    </div>
    <div class="card">
      <div class="card-title" style="color:var(--ml-blue-light)">📈 Recent Releases</div>
      <ul class="release-list">{releases_html}</ul>
    </div>
  </div>
  <p class="section-title">Proof Points by Persona</p>
  <div class="two-col">
    <div class="card">
      <div class="card-title">🏛️ For Credit Union / Community Bank Leadership</div>
      <ul class="diff-list">{diff_list(persona_cu, "dot-win")}</ul>
    </div>
    <div class="card">
      <div class="card-title">🛠️ For Operations / Technology Leaders</div>
      <ul class="diff-list">{diff_list(persona_ops, "dot-win")}</ul>
    </div>
  </div>
</section>

<!-- TAB: HOW TO USE -->
<section id="{uid}-howto" class="tab-content" data-panel="{uid}">
  <p class="section-title">How to Use This Battlecard</p>
  <div class="two-col">
    <div class="card">
      <div class="card-title">📞 Before the Call</div>
      <ul class="diff-list">{diff_list(before_call, "dot-win")}</ul>
    </div>
    <div class="card">
      <div class="card-title">🗣️ During Discovery</div>
      <ul class="diff-list">{diff_list(during_disc, "dot-win")}</ul>
    </div>
    <div class="card">
      <div class="card-title">📋 After a Win or Loss</div>
      <ul class="diff-list">{diff_list(after_deal, "dot-win")}</ul>
    </div>
    <div class="card">
      <div class="card-title">🔄 Keep It Fresh</div>
      <ul class="diff-list">{diff_list(keep_fresh, "dot-win")}</ul>
    </div>
  </div>
  <p class="section-title">The One-Liner for Every Deal</p>
  <div class="card" style="border-color:var(--ml-blue);background:var(--ml-blue-dim)">
    <p style="font-size:15px;color:var(--text-primary);line-height:1.7;font-style:italic">{esc(one_liner)}</p>
  </div>
</section>
'''


LOGIN_PAGE = """<!DOCTYPE html>
<html><head><title>MeridianLink Battlecard Generator</title>
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
</style></head><body>
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
</body></html>"""


GENERATOR_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>MeridianLink Battlecard Generator</title>
<style>
:root {
  --bg-primary: #0a0d14; --bg-elevated: #0f131c; --bg-surface: #161b28; --bg-hover: #1e2536;
  --border: rgba(255,255,255,0.08); --border-strong: rgba(255,255,255,0.15);
  --text-primary: #ffffff; --text-secondary: rgba(255,255,255,0.72); --text-muted: rgba(255,255,255,0.45);
  --ml-blue: #0071ce; --ml-blue-light: #3399ff; --ml-blue-dim: rgba(0,113,206,0.15);
  --win: #10b981; --win-dim: rgba(16,185,129,0.15);
  --lose: #ef4444; --lose-dim: rgba(239,68,68,0.15);
  --tie: #f59e0b; --tie-dim: rgba(245,158,11,0.15);
  --radius: 12px; --radius-sm: 8px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg-primary); color: var(--text-primary); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; line-height: 1.6; min-height: 100vh; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 3px; }

.site-header { background: var(--bg-elevated); border-bottom: 1px solid var(--border); padding: 20px 32px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100; }
.header-left h1 { font-size: 18px; font-weight: 700; letter-spacing: -0.3px; }
.header-left span { font-size: 13px; color: var(--text-muted); margin-top: 2px; display: block; }
.header-badge { background: var(--ml-blue-dim); border: 1px solid var(--ml-blue); color: var(--ml-blue-light); padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.header-right { display: flex; align-items: center; gap: 12px; }
.logout { color: var(--text-muted); font-size: 13px; text-decoration: none; }
.logout:hover { color: var(--text-secondary); }

.generator { background: var(--bg-elevated); border-bottom: 1px solid var(--border); padding: 24px 32px; }
.generator h2 { font-size: 13px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 16px; }
.competitors-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 16px; }
.comp-item { display: flex; align-items: center; gap: 8px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px; padding: 9px 12px; cursor: pointer; transition: border-color 0.15s, background 0.15s; font-size: 13px; color: var(--text-secondary); user-select: none; }
.comp-item:hover { border-color: var(--ml-blue); background: var(--ml-blue-dim); }
.comp-item.selected { border-color: var(--ml-blue); background: var(--ml-blue-dim); color: var(--ml-blue-light); font-weight: 500; }
.comp-item input[type=checkbox] { accent-color: var(--ml-blue); width: 14px; height: 14px; flex-shrink: 0; }
.gen-row { display: flex; gap: 10px; align-items: center; }
.gen-row input[type=text] { flex: 1; padding: 9px 14px; font-size: 14px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px; color: var(--text-primary); }
.gen-row input[type=text]:focus { outline: none; border-color: var(--ml-blue); }
.gen-actions { display: flex; gap: 10px; align-items: center; flex-shrink: 0; }
.btn-link { background: none; border: none; color: var(--ml-blue-light); font-size: 12px; cursor: pointer; text-decoration: underline; padding: 0; }
.btn-link.muted { color: var(--text-muted); }
.count-label { font-size: 12px; color: var(--text-muted); }
.btn-gen { padding: 9px 24px; background: var(--ml-blue); color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-gen:hover { background: #0062b3; }
.btn-gen:disabled { background: #2a2f3d; color: var(--text-muted); cursor: default; }

.status-bar { padding: 10px 32px; font-size: 13px; color: var(--text-muted); border-bottom: 1px solid var(--border); min-height: 38px; display: flex; align-items: center; }

#results { display: none; }
.comp-tabs { background: var(--bg-elevated); border-bottom: 1px solid var(--border); padding: 0 32px; display: flex; gap: 4px; overflow-x: auto; }
.comp-tab { padding: 14px 20px; background: none; border: none; border-bottom: 2px solid transparent; color: var(--text-muted); font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap; transition: all 0.2s; }
.comp-tab:hover { color: var(--text-secondary); }
.comp-tab.active { color: var(--ml-blue-light); border-bottom-color: var(--ml-blue-light); }
.comp-tab.loading { color: #444; cursor: default; }
.comp-panel { display: none; }
.comp-panel.active { display: block; }

.inner-nav { background: var(--bg-elevated); border-bottom: 1px solid var(--border); padding: 0 32px; display: flex; gap: 4px; overflow-x: auto; position: sticky; top: 65px; z-index: 90; }
.tab-btn { padding: 14px 20px; background: none; border: none; border-bottom: 2px solid transparent; color: var(--text-muted); font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap; transition: all 0.2s; }
.tab-btn:hover { color: var(--text-secondary); }
.tab-btn.active { color: var(--ml-blue-light); border-bottom-color: var(--ml-blue-light); }

.tab-content { display: none; padding: 32px; max-width: 1200px; margin: 0 auto; }
.tab-content.active { display: block; }

.section-title { font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 16px; margin-top: 32px; }
.section-title:first-child { margin-top: 0; }

.card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px 24px; margin-bottom: 16px; }
.card-title { font-size: 13px; font-weight: 700; margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }

.alert { border-radius: var(--radius-sm); padding: 12px 16px; font-size: 13px; margin-bottom: 16px; display: flex; gap: 10px; align-items: flex-start; }
.alert-amber { background: var(--tie-dim); border: 1px solid rgba(245,158,11,0.4); color: #fcd34d; }
.alert-icon { font-size: 16px; flex-shrink: 0; }

.profile-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin-bottom: 16px; }
.profile-stat { background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 14px 16px; }
.profile-stat .label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 4px; }
.profile-stat .value { font-size: 14px; font-weight: 600; color: var(--text-primary); }

.tag { display: inline-block; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 20px; padding: 3px 10px; font-size: 11px; color: var(--text-secondary); margin: 3px 2px; }

.matrix-table { width: 100%; border-collapse: separate; border-spacing: 0; border-radius: var(--radius); overflow: hidden; background: var(--bg-surface); border: 1px solid var(--border); margin-bottom: 16px; }
.matrix-table th { padding: 14px 20px; font-size: 12px; font-weight: 700; text-align: left; background: var(--bg-elevated); border-bottom: 1px solid var(--border); }
.matrix-table th.ml-header { background: var(--ml-blue-dim); color: var(--ml-blue-light); border-bottom-color: var(--ml-blue); }
.matrix-table th.comp-header { background: rgba(124,58,237,0.15); color: #a78bfa; border-bottom-color: #7c3aed; }
.matrix-table td { padding: 12px 20px; border-bottom: 1px solid var(--border); vertical-align: top; font-size: 13px; color: var(--text-secondary); }
.matrix-table td:first-child { font-weight: 600; color: var(--text-secondary); width: 22%; }
.matrix-table tr:last-child td { border-bottom: none; }
.matrix-table tr:hover td { background: var(--bg-hover); }
.win-pill { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; }
.pill-ml { background: var(--ml-blue-dim); color: var(--ml-blue-light); border: 1px solid var(--ml-blue); }
.pill-comp { background: rgba(124,58,237,0.15); color: #a78bfa; border: 1px solid #7c3aed; }
.pill-tie { background: var(--tie-dim); color: var(--tie); border: 1px solid var(--tie); }

.win-lose-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.win-box { background: var(--win-dim); border: 1px solid rgba(16,185,129,0.3); border-radius: var(--radius); padding: 18px; }
.lose-box { background: var(--lose-dim); border: 1px solid rgba(239,68,68,0.3); border-radius: var(--radius); padding: 18px; }
.win-box h4 { color: var(--win); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 12px; }
.lose-box h4 { color: var(--lose); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 12px; }
.win-lose-grid ul { list-style: none; }
.win-lose-grid ul li { padding: 5px 0; font-size: 13px; color: var(--text-secondary); padding-left: 16px; position: relative; }
.win-box ul li::before { content: '✓'; position: absolute; left: 0; color: var(--win); font-weight: 700; }
.lose-box ul li::before { content: '✗'; position: absolute; left: 0; color: var(--lose); font-weight: 700; }

.diff-list { list-style: none; }
.diff-list li { padding: 9px 0; border-bottom: 1px solid var(--border); font-size: 13px; color: var(--text-secondary); display: flex; gap: 10px; align-items: flex-start; }
.diff-list li:last-child { border-bottom: none; }
.diff-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-top: 5px; }
.dot-win { background: var(--win); }
.dot-lose { background: var(--lose); }

.track-card { background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; margin-bottom: 12px; }
.track-header { padding: 12px 18px; background: var(--bg-surface); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; cursor: pointer; user-select: none; }
.track-header:hover { background: var(--bg-hover); }
.track-header h4 { font-size: 13px; font-weight: 600; color: var(--text-secondary); }
.track-body { padding: 16px 18px; font-size: 13px; color: var(--text-secondary); line-height: 1.7; display: none; }
.track-card.open .track-body { display: block; }
.track-arrow { color: var(--text-muted); transition: transform 0.2s; font-size: 12px; }
.track-card.open .track-arrow { transform: rotate(180deg); }

.obj-card { border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden; margin-bottom: 10px; }
.obj-q { background: var(--bg-elevated); padding: 12px 16px; font-size: 13px; color: var(--text-muted); font-style: italic; border-bottom: 1px solid var(--border); }
.obj-q::before { content: '"'; }
.obj-q::after { content: '"'; }
.obj-a { background: var(--bg-surface); padding: 12px 16px; font-size: 13px; color: var(--text-secondary); line-height: 1.65; }

.landmine-list { list-style: none; }
.landmine-list li { display: flex; gap: 12px; padding: 12px 16px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); margin-bottom: 8px; font-size: 13px; color: var(--text-secondary); align-items: flex-start; }
.lm-icon { font-size: 16px; flex-shrink: 0; margin-top: 1px; }

.release-list { list-style: none; }
.release-item { display: flex; gap: 14px; padding: 14px 0; border-bottom: 1px solid var(--border); align-items: flex-start; }
.release-item:last-child { border-bottom: none; }
.release-date { font-size: 11px; color: var(--text-muted); white-space: nowrap; min-width: 70px; font-weight: 600; padding-top: 2px; }
.release-info h5 { font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 3px; }
.release-info p { font-size: 12px; color: var(--text-secondary); }

.loading-panel { padding: 60px 32px; text-align: center; color: var(--text-muted); font-size: 14px; }

@media (max-width: 768px) {
  .two-col, .win-lose-grid { grid-template-columns: 1fr; }
  .competitors-grid { grid-template-columns: repeat(2, 1fr); }
  .tab-content, .generator { padding: 16px; }
}
@media print {
  .generator, .site-header, .comp-tabs, .inner-nav { display: none !important; }
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

function switchInnerTab(uid, tab) {
  document.querySelectorAll('[data-panel="'+uid+'"]').forEach(t => t.classList.remove('active'));
  document.getElementById(uid+'-'+tab).classList.add('active');
  const nav = document.getElementById('nav-'+uid);
  if (nav) nav.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.getAttribute('onclick').includes("'"+tab+"'"));
  });
}

function toggleTrack(header) { header.parentElement.classList.toggle('open'); }

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
    const shortName = comp.replace(' LOS','').replace(' by ICE Mortgage Technology',' (ICE)');

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
      let html = '';

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
              panel.innerHTML = html;
              tab.classList.remove('loading');
              tab.textContent = shortName;
              status.textContent = '';
            } else {
              html += d + '\\n';
            }
          }
        }
      }
    } catch(e) {
      panel.innerHTML = '<div class="loading-panel">Error generating battlecard. Check PowerShell for details.</div>';
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
                    model="claude-haiku-4-5-20251001",
                    max_tokens=4000,
                    system=SYSTEM_PROMPT,
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                    messages=[{
                        "role": "user",
                        "content": f"Research the mortgage LOS '{competitor}' and produce the full battlecard using all the section headers as instructed. Compare everything to MeridianLink Mortgage."
                    }]
                )
                break
            except anthropic.APIStatusError as e:
                if e.status_code in (429, 529) and attempt < 4:
                    wait = 30 if e.status_code == 429 else 10
                    yield f"data: STATUS:API busy, retrying in {wait}s... (attempt {attempt + 2} of 5)\n\n"
                    time.sleep(wait)
                else:
                    yield "data: STATUS:API error — check PowerShell\n\n"
                    yield "data: DONE\n\n"
                    return

        # Collect full text response
        raw_text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                raw_text += block.text

        # Parse sections
        sections = {}
        current_key = None
        current_lines = []
        for line in raw_text.split('\n'):
            header_match = re.match(r'^\[([A-Z_0-9]+)\]$', line.strip())
            if header_match:
                if current_key:
                    sections[current_key] = '\n'.join(current_lines).strip()
                current_key = header_match.group(1)
                current_lines = []
            elif current_key:
                current_lines.append(line)
        if current_key:
            sections[current_key] = '\n'.join(current_lines).strip()

        # Build and stream HTML
        html = build_battlecard_html(sections, competitor)
        for line in html.split('\n'):
            yield f"data: {line}\n\n"

        yield "data: DONE\n\n"

    return Response(stream_with_context(stream()), mimetype='text/event-stream')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
