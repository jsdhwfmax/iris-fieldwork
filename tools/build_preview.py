#!/usr/bin/env python3
"""Build the isolated synthetic preview from selected read-only UI components.

Never imports the gateway, reads runtime output, or connects to an IRIS instance.
The manually authored fixtures live in docs/fixtures.js. Run from any directory.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app" / "static"
OUTPUT = ROOT / "docs"


def between(source, start, end):
    assert source.count(start) == 1 and source.count(end) == 1, (start, end)
    return source[source.index(start):source.index(end)]


def build():
    OUTPUT.mkdir(exist_ok=True)
    original = (SOURCE / "app.js").read_text(encoding="utf-8")
    parts = [original[:original.index("  async function api(")]]
    parts.append('''  // Exact in-memory fixture lookup. No transport, credentials or fallback.
  async function api(path, options={}) {
    if (Object.keys(options).length) throw new Error('Requests and commands are unavailable in this preview.');
    const source = window.FIELDWORK_PREVIEW.responses[path];
    if (!source) throw new Error('No authored sample is available for this view.');
    return JSON.parse(JSON.stringify(source));
  }
''')
    parts.append(between(original, "  function renderNavigation()", "  async function loadStatus()"))
    parts.append('''  async function loadStatus() {
    state.status=await api('/api/status');
    $('connection-dot').className='state-dot';
    $('connection-label').textContent='Synthetic preview';
    $('instance-description').textContent='No IRIS instance is connected. Every record and metric is manually authored.';
    $('instance-version').textContent='Static examples · no credentials';
    return state.status;
  }
''')
    parts.append(between(original, "  function notice(", "  const actionDefinition ="))
    parts.append('''  function renderResourceActions() {
    state.sourceActionNotes=[];
    $('resource-actions').innerHTML='';
  }
''')
    parts.append(between(original, "  function openDrawer(", "  function rowTarget("))
    parts.append('''  function showDetails(data,title='Sample details') {
    state.drawerData=data;openDrawer('details',title,'SYNTHETIC RECORD');
    $('drawer-body').innerHTML=`<p class="drawer-intro">Manually authored example. No API request, inspection or management action is performed.</p><div class="drawer-toolbar"><label class="search-field">${svg('search')}<input id="detail-search" type="search" placeholder="Find a field or value…" aria-label="Search sample details"></label></div><div id="detail-fields">${detailFields(data)}</div>`;
    $('detail-search').addEventListener('input',event=>{$('detail-fields').innerHTML=detailFields(state.drawerData,event.target.value);});
  }
  function showExplorer() {
    openDrawer('explorer','REST reference','REFERENCE ONLY',true);
    $('drawer-body').innerHTML=`<p class="drawer-intro">Examples of routes used by the local application. This preview cannot execute API requests. Install the local app to use the live explorer.</p><div class="drawer-toolbar"><label class="search-field">${svg('search')}<input id="explorer-search" type="search" placeholder="Filter route examples…" aria-label="Filter API reference"></label></div><div id="explorer-results"></div>`;
    renderExplorer('');
    $('explorer-search').addEventListener('input',event=>renderExplorer(event.target.value));
  }
  function renderExplorer(query) {
    const items=window.FIELDWORK_PREVIEW.operations.filter(item=>`${item.method} ${item.path} ${item.summary}`.toLowerCase().includes(query.toLowerCase()));
    $('explorer-results').innerHTML=`<p class="explorer-meta">${items.length} route examples · execution unavailable</p><div class="explorer-list">${items.map(item=>`<div class="explorer-item"><span class="explorer-item-head"><span class="method">${esc(item.method)}</span><span class="explorer-path">${esc(item.path)}</span>${badge('Reference only')}</span><p>${esc(item.summary)}</p></div>`).join('')}</div>`;
  }
''')
    parts.append(between(original, "  function findResources(", "  async function dispatch("))
    parts.append('''  async function dispatch(event) {
    const button=event.target.closest('[data-action]');if(!button||button.disabled)return;
    const action=button.dataset.action;
    if(action==='navigate')return navigate(button.dataset.section);
    if(action==='refresh')return refresh();
    if(action==='toggle-nav'){document.body.classList.toggle('nav-open');return;}
    if(action==='close-nav'){document.body.classList.remove('nav-open');return;}
    if(action==='source'){const resource=currentSection()?.resources[Number(button.dataset.index)];if(resource){state.resourceKeys[state.section]=resource.key;state.page=0;state.query='';state.sort=null;$('table-search').value='';renderSection();}return;}
    if(action==='row'){const row=resourceRows(currentResource()?.data)?.[Number(button.dataset.index)];if(row)showDetails(row,textValue(valueAt(row,['Name','TaskName','ID','PID','Record'])||'Sample details'));return;}
    if(action==='inspect'){if(currentResource())showDetails(currentResource().data,currentResource().label||'Sample data');return;}
    if(action==='sort'){state.sort={key:button.dataset.key,direction:state.sort?.key===button.dataset.key?-state.sort.direction:1};renderResource();return;}
    if(action==='previous-page'){state.page=Math.max(0,state.page-1);renderResource();return;}
    if(action==='next-page'){state.page++;renderResource();return;}
    if(action==='close-drawer')return closeDrawer();
    if(action==='explorer')return showExplorer();
    if(action==='triage')return showTriage();
    // Every other action is intentionally absent, including all writes/searches.
  }
''')
    parts.append(original[original.index("  document.addEventListener('click'"):])
    script = "".join(parts)
    replacements = {
        "/* IRIS Fieldwork — dependency-free client. All instance data comes from the local API. */": "/* IRIS Fieldwork synthetic preview. Generated from selected read-only UI components; no network transport. */",
        "Loading live data…": "Opening authored samples…",
        "Loading this section’s sources…": "Opening this section’s samples…",
        "Requesting snapshot": "Opening samples",
        "Requesting a fresh response from the connected instance.": "Opening fixed, manually authored examples.",
        "Waiting for this section’s snapshot": "Opening this section’s examples",
        "loadedAt:new Date()": "loadedAt:new Date('2026-09-01T10:00:00Z')",
        "section.loadedAt.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'})": "'Fixed examples'",
        "'Live snapshot'": "'Synthetic examples'",
        "'Partial snapshot'": "'Mixed examples'",
        "'Available measurements are retained; some values could not be read.'": "'Example of a partial result; values are synthetic.'",
        "'Current response from the connected instance.'": "'Manually authored sample. No API request was made.'",
        "'This source could not supply a live response.'": "'An intentionally unavailable sample source.'",
        "The connected instance does not expose this endpoint. Other sources remain available.": "This source intentionally has no authored records. Other samples remain available.",
        "Review the source status and instance privileges, then refresh.": "Inspect the sample coverage note for this source.",
        "<span class=\"context-label\">Request</span>": "<span class=\"context-label\">API route reference</span>",
        "<span class=\"context-label\">HTTP response</span>": "<span class=\"context-label\">Execution</span>",
        "${esc(resource.http_status??'No response')}": "Not executed",
        "'No data was substituted for this response.'": "'No sample records are included for this source.'",
        "'This endpoint returned an empty collection.'": "'This example intentionally contains an empty collection.'",
        "Object response · Field values are shown as returned": "Sample object · Every field is synthetic",
        "'Measured values'": "'Illustrative values'",
        "Measured over ${esc(data.cpuSampleMilliseconds)} ms": "Example ${esc(data.cpuSampleMilliseconds)} ms interval",
        "A single sample, not a trend. Kernel CPU and memory describe the Linux environment visible to IRIS; container limits are shown separately.": "Illustrative numbers only, not measurements. The local app distinguishes host measurements from container limits; this preview connects to neither.",
        "'Sampled '+esc(sampled.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'}))": "'Fixed synthetic example'",
        "'Bounded live excerpts'": "'Authored sample excerpts'",
        "Sensitive fields are scrubbed by the server": "No server, real logs or credentials",
        "Loading task history and the current process snapshot…": "Opening synthetic task and process examples…",
        "Choose a task to put its recorded activity beside the current process list. This view correlates identifiers; it does not infer a task's health.": "Choose a synthetic task to compare its sample history with sample processes. Matching a PID does not establish process identity. No task runs here.",
        " current processes": " sample processes",
        "No task records are available in the current response. Refresh the Task manager to inspect source availability.": "No task examples are included in this sample.",
        "Task history could not be loaded. No execution conclusion is available.": "No task-history sample is included. This is not execution evidence.",
        "No matching task history exists in this snapshot. This is not evidence that the task has never run.": "No history example is authored for this synthetic task. Nothing runs in this preview.",
        "The current process source is unavailable.": "The process sample is unavailable.",
        "No current process matches the recorded PIDs in this snapshot. Completed tasks may have no active process.": "No sample process matches these example history PIDs. In the local app, a completed task may have no active process.",
        "Current processes with matching PIDs": "Sample processes with matching PIDs",
        "Recorded activity ${badge(history.length)}": "Sample activity ${badge(history.length)}",
        "Inspect raw fields": "Inspect sample fields",
        "The local service": "The preview",
        "Refresh to request this section again.": "Reload the preview to open this sample again.",
    }
    for before, after in replacements.items():
        script = script.replace(before, after)
    script = script.replace("  async function refresh() {", "  async function refresh() {\n    state.query='';state.page=0;state.sort=null;$('table-search').value='';")
    # No mutation/credential workflow, HTTP transport or external resource loader survives.
    for forbidden in ("fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "/api/action", "/api/log-query", "type:'password'", "executeCommand", "showSecretForm", "showLogQuery"):
        assert forbidden not in script, forbidden
    (OUTPUT / "app.js").write_text(script, encoding="utf-8", newline="\n")
    html = (SOURCE / "index.html").read_text(encoding="utf-8")
    html = html.replace('<title>IRIS Fieldwork · Operations workspace</title>', '<title>IRIS Fieldwork · Synthetic preview</title>')
    html = html.replace('href="/static/styles.css"', 'href="./styles.css"')
    html = html.replace('<script src="/static/app.js" defer></script>', '<script src="./fixtures.js" defer></script>\n  <script src="./app.js" defer></script>')
    html = html.replace('<meta name="color-scheme"', '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'self\'; style-src \'self\' \'unsafe-inline\'; img-src \'self\' data:; font-src \'self\'; connect-src \'none\'; form-action \'none\'; object-src \'none\'; base-uri \'none\'">\n  <meta name="color-scheme"')
    html = html.replace('MANAGE YOUR INSTANCE', 'EXPLORE SYNTHETIC EXAMPLES').replace('REST explorer', 'REST reference')
    html = html.replace('Connecting to IRIS', 'Synthetic preview').replace('Checking instance availability.', 'No IRIS instance is connected.').replace('Instance information pending', 'Fixed, manually authored examples').replace('Credentials stay on the server', 'No credentials or API connection')
    html = re.sub(r'<button class="mode-pill".*?</button>', '<span class="mode-pill"><span data-icon="lock"></span><span>No IRIS connection</span></span>', html)
    html = html.replace('<span class="session-label">Instance session</span>', '<span class="session-label">Synthetic preview</span>')
    html = html.replace('<main id="workspace"', '<div class="preview-banner" role="note"><strong>Synthetic preview · no IRIS connection</strong><span>All data is manually authored. Explore views, filters and details; commands, secret entry and API searches are unavailable.</span></div>\n    <main id="workspace"')
    html = html.replace('Refresh data', 'Reset sample view').replace('Sources available', 'Sample sources').replace('Rows received', 'Example rows').replace('Last refreshed', 'Data provenance').replace('Waiting for data', 'Fixed examples').replace('>Connecting</span>', '>Synthetic</span>')
    html = html.replace('Requesting the current instance snapshot.', 'Opening fixed, manually authored examples.').replace('Loading live data…', 'Opening authored samples…').replace('Live instance data · Explicit command review', 'Synthetic examples · No backend or commands').replace('Inspect complete source response', 'Inspect complete sample data').replace('Inspect source response', 'Inspect sample data')
    (OUTPUT / "index.html").write_text(html, encoding="utf-8", newline="\n")
    styles = (SOURCE / "styles.css").read_text(encoding="utf-8")
    styles += '''\n/* Separate preview disclosure; original application styles above are unchanged. */
.preview-banner{position:sticky;top:0;z-index:15;display:flex;flex-wrap:wrap;gap:4px 18px;padding:14px 32px;background:#e4efe6;color:#183e29;border-bottom:1px solid #bad0bf;font-size:12px;line-height:1.6}
.preview-banner strong{font-size:13px}.preview-banner span{max-width:780px}
@media(max-width:700px){.preview-banner{padding:12px 20px;gap:3px}.topbar-right .mode-pill{display:none}}
'''
    (OUTPUT / "styles.css").write_text(styles, encoding="utf-8", newline="\n")
    (OUTPUT / ".nojekyll").touch()
    print("Built docs/index.html, app.js, styles.css and .nojekyll; authored fixtures unchanged.")


if __name__ == "__main__":
    build()
