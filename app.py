from flask import Flask, request, Response, stream_with_context, session, redirect, url_for
import anthropic
import time
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'meridianlink-secret-2026')

APP_PASSWORD = os.environ.get('APP_PASSWORD', 'meridianlink2026')

SYSTEM_PROMPT = """You are a sales intelligence analyst working for MeridianLink.
Your job is to research mortgage loan origination system (LOS) competitors and produce
battlecards for MeridianLink Mortgage sales reps selling into banks, credit unions, and mortgage lenders.

MeridianLink Mortgage key strengths you should always highlight in comparisons:
- Single unified platform covering LOS, POS, and reporting in one system
- Deep integrations with credit unions and community banks
- Modern cloud-based architecture vs legacy on-premise competitors
- Strong compliance and regulatory update track record
- Faster implementation timelines compared to enterprise competitors like Encompass
- Transparent pricing with no hidden per-loan fees
- Dedicated implementation and support teams
- Real-time loan tracking and borrower-facing portal built in
- Strong G2 and Capterra ratings from actual loan officers

When given a competitor LOS name:
1. Search for their current pricing and licensing model
2. Search for reviews from loan officers and mortgage operations teams
3. Search for complaints about implementation, support, or complexity
4. Search for "[competitor] vs MeridianLink" comparisons on G2, Capterra, and Google
5. Then write the battlecard based on what you found

Format the final battlecard using EXACTLY these section headers (include the emoji):

## [Competitor Name] vs MeridianLink Mortgage

### 🏢 Who they are
[2-3 sentence summary - who they serve, market position, parent company if any]

### 💰 Their pricing vs MeridianLink
[What they charge vs what MeridianLink offers - frame MeridianLink favorably where relevant]

### ⚠️ Their weaknesses
- [weakness 1 - tie back to a MeridianLink strength where possible]
- [weakness 2]
- [weakness 3]

### ✅ Why MeridianLink wins here
- [MeridianLink strength 1 that directly counters this competitor]
- [MeridianLink strength 2]
- [MeridianLink strength 3]

### 💬 Common objections and how to respond
- "We already use [competitor]" -> [response]
- "They have a feature we need" -> [response]
- "Switching costs are too high" -> [response]

### 👀 Watch out for
[Things this competitor genuinely does well - be honest so reps are prepared]
"""

LOGIN_PAGE = """<!DOCTYPE html>
<html>
<head>
    <title>MeridianLink Battlecard Generator</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: sans-serif; background: #f4f6f9; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
        .login-card { background: white; border-radius: 12px; border: 1px solid #ddd; padding: 40px; width: 100%; max-width: 380px; }
        .logo { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
        .logo h1 { font-size: 20px; margin: 0; color: #0057a8; }
        .badge { background: #0057a8; color: white; font-size: 11px; padding: 3px 8px; border-radius: 20px; }
        p { color: #666; font-size: 14px; margin-bottom: 24px; }
        label { font-size: 13px; font-weight: 500; color: #333; display: block; margin-bottom: 6px; }
        input[type=password] { width: 100%; padding: 10px 14px; font-size: 15px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 16px; }
        input[type=password]:focus { outline: none; border-color: #0057a8; }
        button { width: 100%; padding: 11px; background: #0057a8; color: white; border: none; border-radius: 8px; font-size: 15px; cursor: pointer; }
        button:hover { background: #004a91; }
        .error { color: #b91c1c; font-size: 13px; margin-bottom: 12px; }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="logo">
            <h1>MeridianLink</h1>
            <span class="badge">Internal Tool</span>
        </div>
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

HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
    <title>MeridianLink Battlecard Generator</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: sans-serif; max-width: 1200px; margin: 40px auto; padding: 0 20px; background: #f4f6f9; }
        .header { display: flex; align-items: center; gap: 16px; margin-bottom: 6px; }
        h1 { font-size: 24px; margin: 0; }
        .badge { background: #0057a8; color: white; font-size: 12px; padding: 4px 10px; border-radius: 20px; font-weight: 500; }
        .logout { margin-left: auto; font-size: 13px; color: #999; text-decoration: none; }
        .logout:hover { color: #333; }
        p.subtitle { color: #666; margin-bottom: 16px; }

        .competitors-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 16px; }
        .competitor-item { display: flex; align-items: center; gap: 8px; background: white; border: 1.5px solid #ddd; border-radius: 8px; padding: 10px 12px; cursor: pointer; transition: border-color 0.15s, background 0.15s; font-size: 14px; color: #333; user-select: none; }
        .competitor-item:hover { border-color: #0057a8; background: #f0f6ff; }
        .competitor-item.selected { border-color: #0057a8; background: #e6f0ff; color: #0057a8; font-weight: 500; }
        .competitor-item input[type=checkbox] { accent-color: #0057a8; width: 16px; height: 16px; flex-shrink: 0; }

        .or { text-align: center; color: #999; font-size: 13px; margin: 4px 0 12px; }
        .row { display: flex; gap: 10px; margin-bottom: 12px; }
        input[type=text] { flex: 1; padding: 10px 14px; font-size: 16px; border: 1px solid #ddd; border-radius: 8px; }
        .actions { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
        .select-all { font-size: 13px; color: #0057a8; cursor: pointer; text-decoration: underline; background: none; border: none; padding: 0; }
        .clear-all { font-size: 13px; color: #999; cursor: pointer; text-decoration: underline; background: none; border: none; padding: 0; }
        .selected-count { font-size: 13px; color: #666; margin-left: auto; }

        button#btn { padding: 10px 28px; background: #0057a8; color: white; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; width: 100%; margin-bottom: 16px; }
        button#btn:hover { background: #004a91; }
        button#btn:disabled { background: #999; cursor: default; }

        #status { color: #888; font-size: 14px; margin-bottom: 16px; min-height: 20px; }

        .toolbar { display: none; justify-content: flex-end; gap: 10px; margin-bottom: 12px; }
        .toolbar button { padding: 7px 16px; font-size: 13px; border: 1px solid #ddd; border-radius: 6px; background: white; cursor: pointer; color: #333; }
        .toolbar button:hover { background: #f0f6ff; border-color: #0057a8; color: #0057a8; }

        #output { display: none; }
        .cards-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }

        .battlecard { background: white; border: 1px solid #ddd; border-radius: 12px; overflow: hidden; }
        .battlecard-title { background: #0057a8; color: white; padding: 14px 18px; font-size: 14px; font-weight: 600; letter-spacing: 0.03em; }
        .battlecard-title.loading { background: #aaa; }

        .section { border-bottom: 1px solid #eee; overflow: hidden; }
        .section:last-child { border-bottom: none; }
        .section-header { display: flex; align-items: center; justify-content: space-between; padding: 11px 16px; cursor: pointer; user-select: none; font-size: 14px; font-weight: 600; }
        .section-header:hover { background: #f8f9fa; }
        .section-toggle { font-size: 12px; color: #999; transition: transform 0.2s; }
        .section-toggle.open { transform: rotate(180deg); }
        .section-body { padding: 0 16px 12px; font-size: 13px; line-height: 1.7; color: #333; display: none; white-space: pre-wrap; }
        .section-body.open { display: block; }

        .section-who .section-header { background: #eef6ff; color: #0057a8; }
        .section-pricing .section-header { background: #fff8e6; color: #b45309; }
        .section-weaknesses .section-header { background: #fff0f0; color: #b91c1c; }
        .section-wins .section-header { background: #f0fff4; color: #166534; }
        .section-objections .section-header { background: #f5f0ff; color: #6d28d9; }
        .section-watchout .section-header { background: #fff7ed; color: #c2410c; }

        .loading-body { padding: 20px 16px; color: #aaa; font-size: 13px; font-style: italic; }
        .footer { margin-top: 24px; font-size: 12px; color: #bbb; text-align: center; }

        @media print {
            body { background: white; }
            .controls-area, .toolbar button, #status { display: none !important; }
            .cards-grid { grid-template-columns: repeat(2, 1fr); }
            .section-body { display: block !important; }
            .section-toggle { display: none; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>MeridianLink Battlecard Generator</h1>
        <span class="badge">Internal Sales Tool</span>
        <a class="logout" href="/logout">Sign out</a>
    </div>
    <p class="subtitle">Select one or more competitor LOS platforms to generate battlecards comparing them to MeridianLink Mortgage.</p>

    <div class="controls-area">
        <div class="actions">
            <button class="select-all" onclick="selectAll()">Select all</button>
            <button class="clear-all" onclick="clearAll()">Clear all</button>
            <span class="selected-count" id="count">0 selected</span>
        </div>

        <div class="competitors-grid" id="grid">
            <label class="competitor-item"><input type="checkbox" value="Encompass by ICE Mortgage Technology" onchange="updateCount()"> Encompass (ICE)</label>
            <label class="competitor-item"><input type="checkbox" value="Calyx Point" onchange="updateCount()"> Calyx Point</label>
            <label class="competitor-item"><input type="checkbox" value="BytePro" onchange="updateCount()"> BytePro</label>
            <label class="competitor-item"><input type="checkbox" value="Mortgage Cadence" onchange="updateCount()"> Mortgage Cadence</label>
            <label class="competitor-item"><input type="checkbox" value="Vesta LOS" onchange="updateCount()"> Vesta</label>
            <label class="competitor-item"><input type="checkbox" value="BlueSage LOS" onchange="updateCount()"> BlueSage</label>
            <label class="competitor-item"><input type="checkbox" value="Wilqo LOS" onchange="updateCount()"> Wilqo</label>
            <label class="competitor-item"><input type="checkbox" value="Blend" onchange="updateCount()"> Blend</label>
            <label class="competitor-item"><input type="checkbox" value="LendingPad" onchange="updateCount()"> LendingPad</label>
            <label class="competitor-item"><input type="checkbox" value="Finastra Mortgagebot" onchange="updateCount()"> Finastra Mortgagebot</label>
            <label class="competitor-item"><input type="checkbox" value="Dark Matter Technologies" onchange="updateCount()"> Dark Matter Technologies</label>
        </div>

        <div class="or">or type a competitor name below</div>
        <div class="row">
            <input type="text" id="custom" placeholder="Type any other competitor name..." />
        </div>

        <button id="btn" onclick="generate()">Generate Battlecards</button>
    </div>

    <div id="status"></div>

    <div class="toolbar" id="toolbar">
        <button onclick="expandAll()">Expand all</button>
        <button onclick="collapseAll()">Collapse all</button>
        <button onclick="window.print()">🖨 Print</button>
        <button onclick="exportMarkdown()">⬇ Export</button>
    </div>

    <div id="output">
        <div class="cards-grid" id="cards-grid"></div>
    </div>

    <div class="footer">For internal MeridianLink sales use only. Always verify pricing and claims before sharing externally.</div>

    <script>
        const SECTIONS = [
            { key: 'who',        emoji: '🏢', label: 'Who they are',                  cls: 'section-who' },
            { key: 'pricing',    emoji: '💰', label: 'Their pricing vs MeridianLink', cls: 'section-pricing' },
            { key: 'weaknesses', emoji: '⚠️', label: 'Their weaknesses',             cls: 'section-weaknesses' },
            { key: 'wins',       emoji: '✅', label: 'Why MeridianLink wins here',    cls: 'section-wins' },
            { key: 'objections', emoji: '💬', label: 'Common objections',            cls: 'section-objections' },
            { key: 'watchout',   emoji: '👀', label: 'Watch out for',                cls: 'section-watchout' },
        ];

        function updateCount() {
            const checked = document.querySelectorAll('#grid input:checked');
            document.getElementById('count').textContent = checked.length + ' selected';
            document.querySelectorAll('.competitor-item').forEach(el => {
                el.classList.toggle('selected', el.querySelector('input').checked);
            });
        }

        function selectAll() {
            document.querySelectorAll('#grid input[type=checkbox]').forEach(cb => cb.checked = true);
            updateCount();
        }

        function clearAll() {
            document.querySelectorAll('#grid input[type=checkbox]').forEach(cb => cb.checked = false);
            document.getElementById('custom').value = '';
            updateCount();
        }

        function toggleSection(header) {
            const body = header.nextElementSibling;
            const toggle = header.querySelector('.section-toggle');
            body.classList.toggle('open');
            toggle.classList.toggle('open');
        }

        function expandAll() {
            document.querySelectorAll('.section-body').forEach(b => b.classList.add('open'));
            document.querySelectorAll('.section-toggle').forEach(t => t.classList.add('open'));
        }

        function collapseAll() {
            document.querySelectorAll('.section-body').forEach(b => b.classList.remove('open'));
            document.querySelectorAll('.section-toggle').forEach(t => t.classList.remove('open'));
        }

        function exportMarkdown() {
            const cards = document.querySelectorAll('.battlecard');
            let md = '';
            cards.forEach(card => {
                const title = card.querySelector('.battlecard-title').textContent;
                md += '# ' + title + '\\n\\n';
                card.querySelectorAll('.section').forEach(sec => {
                    const heading = sec.querySelector('.section-header').textContent.replace('▼','').trim();
                    const body = sec.querySelector('.section-body').textContent.trim();
                    md += '## ' + heading + '\\n' + body + '\\n\\n';
                });
                md += '---\\n\\n';
            });
            const blob = new Blob([md], {type: 'text/markdown'});
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'battlecards.md';
            a.click();
        }

        function parseAndRenderSections(cardEl, rawText) {
            const sectionData = {};
            let current = null;
            rawText.split('\\n').forEach(line => {
                const match = line.match(/^###\\s+(.*)/);
                if (match) {
                    const heading = match[1].trim();
                    if (heading.includes('Who they are')) current = 'who';
                    else if (heading.includes('pricing')) current = 'pricing';
                    else if (heading.includes('weaknesses')) current = 'weaknesses';
                    else if (heading.includes('wins here')) current = 'wins';
                    else if (heading.includes('objections')) current = 'objections';
                    else if (heading.includes('Watch out')) current = 'watchout';
                    else current = null;
                    if (current) sectionData[current] = '';
                } else if (current) {
                    sectionData[current] += line + '\\n';
                }
            });

            cardEl.querySelector('.loading-body')?.remove();

            SECTIONS.forEach((sec, i) => {
                const div = document.createElement('div');
                div.className = 'section ' + sec.cls;

                const header = document.createElement('div');
                header.className = 'section-header';
                header.innerHTML = sec.emoji + ' ' + sec.label + ' <span class="section-toggle">▼</span>';
                header.onclick = () => toggleSection(header);

                const body = document.createElement('div');
                body.className = 'section-body' + (i === 0 ? ' open' : '');
                body.textContent = (sectionData[sec.key] || 'No data found.').trim();

                if (i === 0) header.querySelector('.section-toggle').classList.add('open');

                div.appendChild(header);
                div.appendChild(body);
                cardEl.appendChild(div);
            });
        }

        function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

        document.getElementById('custom').addEventListener('keydown', e => { if (e.key === 'Enter') generate(); });

        async function generate() {
            const checked = [...document.querySelectorAll('#grid input:checked')].map(cb => cb.value);
            const custom = document.getElementById('custom').value.trim();
            if (custom) checked.push(custom);
            if (checked.length === 0) { alert('Please select at least one competitor or type a name.'); return; }

            const btn = document.getElementById('btn');
            const status = document.getElementById('status');
            const grid = document.getElementById('cards-grid');
            const output = document.getElementById('output');
            const toolbar = document.getElementById('toolbar');

            btn.disabled = true;
            grid.innerHTML = '';
            output.style.display = 'block';
            toolbar.style.display = 'none';

            for (let i = 0; i < checked.length; i++) {
                const competitor = checked[i];

                if (i > 0) {
                    for (let s = 15; s > 0; s--) {
                        status.textContent = 'Waiting ' + s + 's before next battlecard to avoid rate limits...';
                        await sleep(1000);
                    }
                }

                status.textContent = 'Generating ' + (i + 1) + ' of ' + checked.length + ': ' + competitor + '...';

                const card = document.createElement('div');
                card.className = 'battlecard';
                const title = document.createElement('div');
                title.className = 'battlecard-title loading';
                title.textContent = competitor + ' vs MeridianLink';
                card.appendChild(title);
                const loadingBody = document.createElement('div');
                loadingBody.className = 'loading-body';
                loadingBody.textContent = 'Researching...';
                card.appendChild(loadingBody);
                grid.appendChild(card);

                try {
                    const response = await fetch('/generate', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({competitor})
                    });
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder();
                    let result = '';

                    while (true) {
                        const {done, value} = await reader.read();
                        if (done) break;
                        const chunk = decoder.decode(value);
                        for (const line of chunk.split('\\n')) {
                            if (line.startsWith('data: ')) {
                                const data = line.slice(6);
                                if (data.startsWith('STATUS:')) {
                                    status.textContent = data.slice(7);
                                } else if (data === 'DONE') {
                                    title.classList.remove('loading');
                                    parseAndRenderSections(card, result);
                                } else {
                                    result += data + '\\n';
                                    loadingBody.textContent = 'Researching... (' + result.split('\\n').length + ' lines received)';
                                }
                            }
                        }
                    }
                } catch (err) {
                    loadingBody.textContent = 'Something went wrong. Check PowerShell.';
                }
            }

            status.textContent = 'All done! ' + checked.length + ' battlecard' + (checked.length > 1 ? 's' : '') + ' generated.';
            toolbar.style.display = 'flex';
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
    from flask import render_template_string
    return render_template_string(LOGIN_PAGE, error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return HTML_PAGE


@app.route('/generate', methods=['POST'])
def generate():
    if not session.get('logged_in'):
        return Response('Unauthorized', status=401)

    competitor = request.json.get('competitor', '')

    def stream():
        yield "data: STATUS:Researching " + competitor + "...\n\n"

        for attempt in range(5):
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=2000,
                    system=SYSTEM_PROMPT,
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                    messages=[{
                        "role": "user",
                        "content": f"Research the mortgage LOS {competitor} and generate a battlecard comparing it to MeridianLink Mortgage, highlighting where MeridianLink wins."
                    }]
                )
                break
            except anthropic.APIStatusError as e:
                if e.status_code in (429, 529) and attempt < 4:
                    wait = 30 if e.status_code == 429 else 10
                    yield f"data: STATUS:API busy, retrying in {wait}s... (attempt {attempt + 2} of 5)\n\n"
                    time.sleep(wait)
                else:
                    yield f"data: ERROR: API error {e.status_code}\n\n"
                    yield "data: DONE\n\n"
                    return

        for block in response.content:
            if hasattr(block, 'text'):
                for line in block.text.split('\n'):
                    yield f"data: {line}\n\n"

        yield "data: DONE\n\n"

    return Response(stream_with_context(stream()), mimetype='text/event-stream')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
