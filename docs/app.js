/* IRIS Fieldwork synthetic preview. Generated from selected read-only UI components; no network transport. */
(() => {
  'use strict';
  const icons = {
    web:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M7 6.5h.01M10 6.5h.01M7 13l-2 2 2 2m10-4 2 2-2 2m-4-4-2 4"/>',
    users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/><circle cx="9" cy="7" r="4"/>',
    shield:'<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    tasks:'<rect x="5" y="4" width="15" height="17" rx="2"/><path d="M9 4V2m7 2V2M9 10h7m-7 4h7m-7 4h4"/>',
    system:'<rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6.5h.01M7 17.5h.01m4-11h6m-6 11h6"/>',
    logs:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 12h8m-8 4h8m-8 4h5"/>',
    code:'<path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 16"/>',
    layers:'<path d="m12 3 9 5-9 5-9-5zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
    rows:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M3 14h18M8 9v11"/>',
    clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    refresh:'<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.09 7a7 7 0 0 1 11.55-2.61L20 7M4 17l2.36 2.61A7 7 0 0 0 17.91 17"/>',
    activity:'<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/>',
    braces:'<path d="M8 3H6a2 2 0 0 0-2 2v4a3 3 0 0 1-2 3 3 3 0 0 1 2 3v4a2 2 0 0 0 2 2h2m8-18h2a2 2 0 0 1 2 2v4a3 3 0 0 0 2 3 3 3 0 0 0-2 3v4a2 2 0 0 1-2 2h-2"/>',
    compass:'<circle cx="12" cy="12" r="9"/><path d="m16 8-2.5 5.5L8 16l2.5-5.5z"/>',
    lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 1 1 8 0v3m-4 5v2"/>',
    close:'<path d="m6 6 12 12M18 6 6 18"/>',
    menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',
    right:'<path d="m9 5 7 7-7 7"/>',
    left:'<path d="m15 5-7 7 7 7"/>',
    empty:'<path d="M3 8h18v12H3zM3 8l4-5h10l4 5M3 13h5l2 3h4l2-3h5"/>',
    warning:'<path d="m12 3 10 18H2zM12 9v4m0 4h.01"/>',
    check:'<path d="m5 12 4 4L19 6"/>'
  };
  const areas = {
    web:{label:'Web applications',title:'Web applications',description:'Inspect application settings and explore the management API.',icon:'web',number:'01'},
    permissions:{label:'Permissions',title:'Identity & permissions',description:'Review users, roles and the resources that connect them.',icon:'users',number:'02'},
    security:{label:'Security & secrets',title:'Security & secrets',description:'Inspect security configuration and available credential metadata.',icon:'shield',number:'03'},
    tasks:{label:'Task manager',title:'Task manager',description:'Follow scheduled work, inspect execution history and review task controls.',icon:'tasks',number:'04'},
    system:{label:'System',title:'System operations',description:'A clear view of processes, devices and instance resources.',icon:'system',number:'05'},
    logs:{label:'Logs & activity',title:'Logs & activity',description:'Explore task history, journals and the available audit sources.',icon:'logs',number:'06'}
  };
  const state = {section:'system',sections:{},loadVersion:{},status:null,resourceKeys:{},query:'',page:0,pageSize:40,sort:null,review:false,drawer:null,drawerData:null,focusBefore:null,explorer:null,triage:null,busy:false};
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const svg = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.rows}</svg>`;
  const hydrate = (root=document) => root.querySelectorAll('[data-icon]').forEach(el => {el.innerHTML=svg(el.dataset.icon);});
  const normalize = key => String(key).toLowerCase().replace(/[^a-z0-9]/g,'');
  const human = key => String(key).replace(/([a-z0-9])([A-Z])/g,'$1 $2').replace(/[_-]+/g,' ').replace(/^./, c=>c.toUpperCase());
  const textValue = value => value === null ? 'null' : value === undefined ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value);
  const good = resource => resource && ['ok','success'].includes(resource.state);
  const hasData = resource => good(resource)||(resource?.state==='partial'&&resource.data!==null&&resource.data!==undefined);
  const num = value => typeof value === 'number' && Number.isFinite(value);
  function valueAt(row, names) {
    if (!row || typeof row !== 'object') return undefined;
    const entries = Object.entries(row);
    for (const name of names) {const entry=entries.find(([key])=>normalize(key)===normalize(name)); if(entry) return entry[1];}
    return undefined;
  }
  function resourceRows(data) {
    if (Array.isArray(data)) return data.map(value => value && typeof value==='object' ? value : {Value:value});
    if (data && typeof data==='object') {
      const arrays=Object.values(data).filter(Array.isArray);
      if (arrays.length===1 && Object.keys(data).length<=3) return resourceRows(arrays[0]);
      const values=Object.values(data);
      if (values.length && values.every(value=>value && typeof value==='object' && !Array.isArray(value))) return Object.entries(data).map(([key,value])=>({Record:key,...value}));
    }
    return null;
  }
  function flatten(value, path='', output=[], depth=0) {
    if (output.length>=6000) return output;
    if (depth>18) {output.push({path:path||'Value',value:'Nested value exceeds inspector depth'});return output;}
    if(value && typeof value==='object' && Object.keys(value).length) {
      for(const [key,child] of Object.entries(value)) {flatten(child,Array.isArray(value)?`${path}[${key}]`:(path?`${path}.${key}`:key),output,depth+1); if(output.length>=6000) break;}
    } else output.push({path:path||'Value',value});
    return output;
  }
  function rowMatches(row, query) {
    if(!query) return true;
    return flatten(row).some(field=>`${field.path} ${textValue(field.value)}`.toLowerCase().includes(query));
  }
  function badge(label,type='neutral'){return `<span class="badge badge-${type}">${esc(label)}</span>`;}
  function sourceBadge(resource) {
    if(good(resource)) return badge('Available','ok');
    if(resource?.state==='partial')return badge('Partial data','warning');
    if(resource?.state==='pending')return badge('Search pending','neutral');
    const labels={not_found:'Not exposed',unsupported:'Unsupported',forbidden:'Access denied',unauthorized:'Authentication needed',unavailable:'Unavailable',application_error:'API error'};
    return badge(labels[resource?.state]||human(resource?.state||'Unavailable'),['not_found','unsupported'].includes(resource?.state)?'warning':'error');
  }
  function empty(title,body,icon='empty') {return `<div class="empty-state"><span class="empty-icon">${svg(icon)}</span><h3>${esc(title)}</h3><p>${esc(body)}</p></div>`;}
  function loading(message='Opening authored samples…') {return `<div class="loading-state"><span class="spinner"></span><span>${esc(message)}</span></div>`;}
  // Exact in-memory fixture lookup. No transport, credentials or fallback.
  async function api(path, options={}) {
    if (Object.keys(options).length) throw new Error('Requests and commands are unavailable in this preview.');
    const source = window.FIELDWORK_PREVIEW.responses[path];
    if (!source) throw new Error('No authored sample is available for this view.');
    return JSON.parse(JSON.stringify(source));
  }
  function renderNavigation() {
    $('section-nav').innerHTML=Object.entries(areas).map(([id,area])=>`<button class="nav-link" data-action="navigate" data-section="${id}" ${id===state.section?'aria-current="page"':''}>${svg(area.icon)}<span>${area.label}</span></button>`).join('');
    const area=areas[state.section];$('breadcrumb-current').textContent=area.label;$('section-eyebrow').textContent=`${area.label.toUpperCase()} / ${area.number}`;$('section-title').textContent=area.title;$('section-description').textContent=area.description;
    document.title=`${area.label} · IRIS Fieldwork`;
  }
  async function loadStatus() {
    state.status=await api('/api/status');
    $('connection-dot').className='state-dot';
    $('connection-label').textContent='Synthetic preview';
    $('instance-description').textContent='No IRIS instance is connected. Every record and metric is manually authored.';
    $('instance-version').textContent='Static examples · no credentials';
    return state.status;
  }
  function notice(message,isError=false) {const node=$('global-notice');node.hidden=!message;node.textContent=message;node.className=`notice${isError?' error':''}`;}
  function currentSection(){return state.sections[state.section];}
  function currentResource(){const resources=currentSection()?.resources||[];return resources.find(resource=>resource.key===state.resourceKeys[state.section])||resources[0];}
  function renderSectionLoading(id) {
    $('source-tabs').innerHTML='<span class="muted" style="font-size:11px">Opening this section’s samples…</span>';
    $('metric-sources').textContent='—';$('metric-records').textContent='—';$('metric-time').textContent='Opening samples';
    $('snapshot-state').outerHTML='<span id="snapshot-state" class="badge badge-neutral">Loading</span>';
    $('resource-title').textContent=areas[id].label;$('resource-description').textContent='Opening fixed, manually authored examples.';
    $('source-context').innerHTML='<p class="muted">Source details will appear when this section finishes loading.</p>';$('section-limitations').innerHTML='';$('resource-actions').innerHTML='';
    $('resource-content').innerHTML=loading();$('resource-content').setAttribute('aria-busy','true');$('inspect-button').disabled=true;
    $('table-search').disabled=true;$('filter-count').textContent='';$('table-footer').textContent='Opening this section’s examples';
  }
  async function loadSection(id,force=false) {
    if(state.sections[id]&&!force) return state.sections[id];
    const version=(state.loadVersion[id]||0)+1;state.loadVersion[id]=version;
    if(id===state.section)renderSectionLoading(id);
    try {
      const payload=await api(`/api/section/${encodeURIComponent(id)}`);
      if(!Array.isArray(payload.resources)) throw new Error('This section returned an invalid source list.');
      if(state.loadVersion[id]!==version)return payload;
      state.sections[id]={...payload,loadedAt:new Date('2026-09-01T10:00:00Z')};
      if(id===state.section) renderSection();return state.sections[id];
    } catch(error) {
      if(id===state.section&&state.loadVersion[id]===version){$('resource-content').innerHTML=empty('Section unavailable',error.message,'warning');$('resource-content').setAttribute('aria-busy','false');$('source-tabs').innerHTML='';$('metric-sources').textContent='—';$('metric-records').textContent='—';$('metric-time').textContent='No snapshot received';$('snapshot-state').outerHTML='<span id="snapshot-state" class="badge badge-error">Unavailable</span>';$('resource-title').textContent=areas[id].label;$('resource-description').textContent='The preview could not load this section.';$('table-footer').textContent='No snapshot loaded';$('source-context').innerHTML='<p class="muted">Reload the preview to open this sample again.</p>';}
      throw error;
    }
  }
  async function navigate(id) {
    if(!areas[id]) return;
    state.section=id;state.query='';state.page=0;state.sort=null;$('table-search').value='';document.body.classList.remove('nav-open');renderNavigation();
    if(location.hash!==`#${id}`) history.replaceState(null,'',`#${id}`);
    try{await loadSection(id,true);}catch(_){/* visible source error */}
  }
  function recordCount(resource) {if(num(resource.count))return resource.count;return resourceRows(resource.data)?.length||0;}
  function shapeLabel(resource) {const rows=resourceRows(resource.data);const count=rows?rows.length:resource.data&&typeof resource.data==='object'?Object.keys(resource.data).length:1;return `${count.toLocaleString()} ${rows?(count===1?'row':'rows'):(count===1?'field':'fields')}`;}
  function renderSection() {
    const section=currentSection();if(!section)return;
    const resources=section.resources;const available=resources.filter(good).length;
    $('metric-sources').textContent=`${available} / ${resources.length}`;
    $('metric-records').textContent=resources.filter(hasData).reduce((count,resource)=>count+(resourceRows(resource.data)?.length||0),0).toLocaleString();
    $('metric-time').textContent='Fixed examples';
    const snapshot=available===resources.length&&resources.length?'Synthetic examples':resources.some(hasData)?'Mixed examples':'Unavailable';
    $('snapshot-state').outerHTML=`<span id="snapshot-state" class="badge badge-${available===resources.length&&resources.length?'ok':resources.some(hasData)?'warning':'error'}">${snapshot}</span>`;
    $('source-tabs').innerHTML=resources.map((resource,index)=>`<button class="source-tab" data-action="source" data-index="${index}" aria-current="${resource===currentResource()}"><span class="state-dot ${good(resource)?'ok':'error'}"></span>${esc(resource.label||human(resource.key))}${hasData(resource)?`<span class="source-count">${resourceRows(resource.data)?recordCount(resource).toLocaleString():esc(shapeLabel(resource))}</span>`:''}</button>`).join('');
    const notes=(section.limitations||[]).filter(Boolean);
    $('section-limitations').innerHTML=notes.length?`<div class="context-divider"></div><span class="coverage-title">COVERAGE NOTES</span><ul class="coverage-notes">${notes.map(note=>`<li>${esc(note)}</li>`).join('')}</ul>`:'';
    renderResource();
  }
  function renderResource() {
    const resource=currentResource();$('resource-content').setAttribute('aria-busy','false');$('table-search').disabled=false;
    if(!resource){$('resource-title').textContent='No data sources';$('resource-content').innerHTML=empty('No sources configured','This section does not expose any data sources.');return;}
    renderResourceActions(resource);
    $('resource-title').textContent=resource.label||human(resource.key);
    $('resource-description').textContent=resource.state==='partial'?'Example of a partial result; values are synthetic.':good(resource)?'Manually authored sample. No API request was made.':'An intentionally unavailable sample source.';
    $('inspect-button').disabled=resource.data===null||resource.data===undefined;
    $('source-context').innerHTML=`<div class="context-row"><span class="context-label">Availability</span>${sourceBadge(resource)}</div><div class="context-row"><span class="context-label">API route reference</span><span class="method">${esc(resource.method||'GET')}</span><div class="context-value endpoint">${esc(resource.path||'Not supplied')}</div></div><div class="context-row"><span class="context-label">Execution</span><div class="context-value">Not executed</div></div><div class="context-row"><span class="context-label">Response shape</span><div class="context-value">${hasData(resource)?esc(shapeLabel(resource)):'Not available'}</div></div>${resource.error?`<div class="context-row"><span class="context-label">Source message</span><div class="context-value">${esc(resource.error.message||resource.error.code||'Request did not complete.')}</div></div>`:''}`;
    if(state.sourceActionNotes?.length)$('source-context').insertAdjacentHTML('beforeend',`<div class="context-row"><span class="context-label">Management availability</span>${state.sourceActionNotes.map(note=>`<p class="context-value">${esc(note)}</p>`).join('')}</div>`);
    if(!hasData(resource)) {
      const unsupported=['not_found','unsupported'].includes(resource.state);
      $('resource-content').innerHTML=empty(unsupported?'Endpoint not exposed':'Source unavailable',resource.error?.message||(unsupported?'This source intentionally has no authored records. Other samples remain available.':'Inspect the sample coverage note for this source.'),'warning');
      $('filter-count').textContent='';$('table-footer').textContent='No sample records are included for this source.';return;
    }
    if(resource.key==='runtime_metrics'&&resource.data&&typeof resource.data==='object'&&!Array.isArray(resource.data)){renderRuntimeMetrics(resource.data);return;}
    if(resource.key==='runtime_logs'&&Array.isArray(resource.data)){renderRuntimeLogs(resource.data);return;}
    const rows=resourceRows(resource.data);
    if(rows===null){renderObject(resource.data);return;}
    renderTable(rows);
  }
  function columnsFor(rows) {
    const all=[...new Set(rows.slice(0,80).flatMap(row=>Object.keys(row)))];
    const priorities=['id','name','record','taskname','username','rolename','pid','taskid','namespace','enabled','status','state','type','description','dispatchclass','nextrun','lastrun','cputime','starttime','endtime'];
    return all.sort((a,b)=>{const ai=priorities.indexOf(normalize(a)),bi=priorities.indexOf(normalize(b));return (ai<0?99:ai)-(bi<0?99:bi);}).slice(0,6);
  }
  function displayCell(value) {
    if(value===null||value===undefined)return '<span class="muted">—</span>';
    if(typeof value==='boolean')return badge(value?'True':'False',value?'ok':'neutral');
    if(typeof value==='object'){const count=Array.isArray(value)?value.length:Object.keys(value).length;return `<span class="cell-structure">${svg('braces')}${count} ${Array.isArray(value)?(count===1?'item':'items'):(count===1?'field':'fields')}</span>`;}
    if(typeof value==='string'&&['running','enabled','active','suspended','disabled','inactive','failed','error','success'].includes(value.toLowerCase()))return badge(value,['running','enabled','active','success'].includes(value.toLowerCase())?'ok':['failed','error'].includes(value.toLowerCase())?'error':'neutral');
    return esc(String(value));
  }
  function renderTable(rows) {
    let filtered=rows.map((row,index)=>({row,index})).filter(item=>rowMatches(item.row,state.query));
    const columns=columnsFor(rows);
    if(state.sort)filtered.sort((a,b)=>{const left=a.row[state.sort.key],right=b.row[state.sort.key];const comparison=typeof left==='number'&&typeof right==='number'?left-right:textValue(left).localeCompare(textValue(right),undefined,{numeric:true});return state.sort.direction*comparison;});
    const pages=Math.max(1,Math.ceil(filtered.length/state.pageSize));state.page=Math.min(state.page,pages-1);
    const start=state.page*state.pageSize;const visible=filtered.slice(start,start+state.pageSize);
    $('filter-count').textContent=state.query?`${filtered.length} matched`:`${rows.length.toLocaleString()} records`;
    if(!visible.length){$('resource-content').innerHTML=empty(state.query?'No matching records':'No records returned',state.query?'Try another name, identifier or nested field value.':'This example intentionally contains an empty collection.');}
    else {$('resource-content').innerHTML=`<div class="table-scroll"><table><thead><tr>${columns.map(key=>`<th scope="col" aria-sort="${state.sort?.key===key?(state.sort.direction===1?'ascending':'descending'):'none'}"><button class="text-link" style="text-decoration:none;color:inherit" data-action="sort" data-key="${esc(key)}">${esc(human(key))}${state.sort?.key===key?(state.sort.direction===1?' ↑':' ↓'):''}</button></th>`).join('')}<th scope="col"><span class="visually-hidden">Inspect</span></th></tr></thead><tbody>${visible.map(({row,index})=>`<tr data-action="row" data-index="${index}" tabindex="0" aria-label="Inspect ${esc(textValue(valueAt(row,['Name','TaskName','ID','PID','Record'])??'record '+(index+1)))}">${columns.map(key=>`<td title="${esc(typeof row[key]==='object'?'Open record to inspect nested fields':textValue(row[key]))}" class="${['id','pid','taskid'].includes(normalize(key))?'cell-mono':''}">${displayCell(row[key])}</td>`).join('')}<td><span class="row-open">${svg('right')}</span></td></tr>`).join('')}</tbody></table></div>`;}
    const fieldCount=[...new Set(rows.flatMap(row=>Object.keys(row)))].length;
    $('table-footer').innerHTML=`<span>${filtered.length?`${start+1}–${Math.min(start+state.pageSize,filtered.length)} of ${filtered.length.toLocaleString()}`:'0 records'}${fieldCount>6?' · More fields in row details':''}</span><div class="pagination"><button class="icon-button" data-action="previous-page" aria-label="Previous page" ${state.page===0?'disabled':''}>${svg('left')}</button><span>${state.page+1} / ${pages}</span><button class="icon-button" data-action="next-page" aria-label="Next page" ${state.page>=pages-1?'disabled':''}>${svg('right')}</button></div>`;
  }
  function renderObject(data) {
    const fields=flatten(data).filter(field=>`${field.path} ${textValue(field.value)}`.toLowerCase().includes(state.query));
    $('filter-count').textContent=`${fields.length} ${fields.length===1?'field':'fields'}`;
    $('resource-content').innerHTML=fields.length?`<div class="object-summary">${fields.slice(0,80).map(field=>`<div class="object-field"><span class="field-label">${esc(field.path)}</span><span class="field-value">${displayCell(field.value)}</span></div>`).join('')}</div>`:empty('No matching fields','Try another field name or value.');
    $('table-footer').textContent=fields.length>80?'Showing 80 fields. Inspect the response to search all fields.':'Sample object · Every field is synthetic';
  }
  function bytes(value) {if(!num(value)||value<0)return 'Not supplied';const units=['B','KiB','MiB','GiB','TiB'];let scaled=value,index=0;while(scaled>=1024&&index<units.length-1){scaled/=1024;index++;}return `${scaled.toLocaleString(undefined,{maximumFractionDigits:index?1:0})} ${units[index]}`;}
  function meter(value,label) {return num(value)?`<div class="usage-track" role="meter" aria-label="${esc(label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.max(0,Math.min(100,value)).toFixed(1)}"><span style="width:${Math.max(0,Math.min(100,value)).toFixed(1)}%"></span></div>`:'';}
  function renderRuntimeMetrics(data) {
    if(state.query){renderObject(data);return;}
    const cpu=num(data.cpuBusyPercent)?data.cpuBusyPercent:null;
    const memoryUsed=data.containerMemoryUsedBytes,memoryLimit=data.containerMemoryLimitBytes;
    const memoryPercent=num(memoryUsed)&&num(memoryLimit)&&memoryLimit>0?100*memoryUsed/memoryLimit:null;
    const diskTotal=data.irisDiskTotalBytes,diskAvailable=data.irisDiskAvailableBytes;
    const diskUsed=num(diskTotal)&&num(diskAvailable)?diskTotal-diskAvailable:null;
    const diskPercent=num(diskUsed)&&diskTotal>0?100*diskUsed/diskTotal:null;
    const sampled=data.sampledAt?new Date(data.sampledAt):null;
    $('filter-count').textContent='Illustrative values';
    $('resource-content').innerHTML=`<div class="runtime-overview"><div class="runtime-scope">${svg('compass')}<span>${esc(data.scope||'Measurement scope was not supplied.')}</span></div><div class="runtime-cards"><div class="runtime-card"><span class="metric-label">Kernel CPU busy</span><strong>${cpu===null?'—':cpu.toLocaleString(undefined,{maximumFractionDigits:1})+'<small>%</small>'}</strong>${meter(cpu,'Kernel CPU busy')}<p>${num(data.cpuSampleMilliseconds)?`Example ${esc(data.cpuSampleMilliseconds)} ms interval`:'Sampling period not supplied'}</p></div><div class="runtime-card"><span class="metric-label">Container memory used</span><strong>${num(memoryUsed)?esc(bytes(memoryUsed)):'—'}</strong>${meter(memoryPercent,'Container memory used')}<p>${num(memoryLimit)?'of '+esc(bytes(memoryLimit))+' limit':'Container limit not supplied'}</p></div><div class="runtime-card"><span class="metric-label">IRIS filesystem used</span><strong>${num(diskUsed)?esc(bytes(diskUsed)):'—'}</strong>${meter(diskPercent,'IRIS filesystem used')}<p>${num(diskAvailable)?esc(bytes(diskAvailable))+' available':'Availability not supplied'}</p></div></div><div class="runtime-facts"><div><span>Kernel memory available</span><strong>${esc(bytes(data.memoryAvailableBytes))}</strong></div><div><span>Kernel memory total</span><strong>${esc(bytes(data.memoryTotalBytes))}</strong></div><div><span>Container CPU limit</span><strong>${num(data.containerCpuLimitCores)?esc(data.containerCpuLimitCores)+' cores':'Not supplied'}</strong></div><div><span>IRIS filesystem size</span><strong>${esc(bytes(diskTotal))}</strong></div></div><p class="runtime-caption">Illustrative numbers only, not measurements. The local app distinguishes host measurements from container limits; this preview connects to neither.</p></div>`;
    $('table-footer').innerHTML=`<span>${sampled&&!Number.isNaN(sampled.getTime())?'Fixed synthetic example':'Sample time not supplied'}</span><button class="text-link" data-action="inspect">Inspect sample fields</button>`;
  }
  function renderRuntimeLogs(sources) {
    let matched=0,total=0;
    const output=sources.map((source,index)=>{
      const records=Array.isArray(source.records)?source.records:[];total+=records.length;
      const filtered=records.filter(record=>!state.query||`${source.source} ${textValue(record.line??record)}`.toLowerCase().includes(state.query));matched+=filtered.length;
      if(state.query&&!filtered.length)return '';
      return `<details class="log-group" ${index===0||state.query?'open':''}><summary><span class="log-source">${esc(source.source||'Log source')}</span>${badge(source.state||'unknown',source.state==='ok'?'ok':'warning')}<span class="log-count">${filtered.length} lines</span></summary><div class="log-scope">${esc(source.scope||'Scope not supplied')}${source.truncated?' · Bounded excerpt':''}</div>${filtered.length?`<div class="log-lines">${filtered.map((record,lineIndex)=>`<div class="log-line"><span class="line-number">${lineIndex+1}</span><code>${esc(textValue(record.line??record))}</code></div>`).join('')}</div>`:`<p class="log-empty">${source.state==='ok'?'No lines returned in this excerpt.':'This log source did not return a readable excerpt.'}</p>`}</details>`;
    }).join('');
    $('filter-count').textContent=state.query?`${matched} matched lines`:`${total} lines`;
    $('resource-content').innerHTML=output?`<div class="log-reader">${output}</div>`:empty('No matching log lines','Search another value or clear the filter.');
    $('table-footer').textContent=`${sources.length} log sources · ${state.query?'Filtered excerpt':'Authored sample excerpts'} · No server, real logs or credentials`;
  }
  function renderResourceActions() {
    state.sourceActionNotes=[];
    $('resource-actions').innerHTML='';
  }
  function openDrawer(type,title,eyebrow,wide=false) {
    if($('drawer-layer').hidden)state.focusBefore=document.activeElement;
    state.drawer=type;$('drawer-title').textContent=title;$('drawer-eyebrow').textContent=eyebrow;$('drawer').classList.toggle('wide',wide);$('drawer-layer').hidden=false;document.body.style.overflow='hidden';$('drawer-body').innerHTML='';$('drawer').focus();
  }
  function closeDrawer() {if(state.busy){toast('Wait for the action response before closing this review.');return;}state.drawer=null;$('drawer-layer').hidden=true;document.body.style.overflow='';if(state.focusBefore?.isConnected)state.focusBefore.focus();}
  function detailFields(data,query='') {
    const fields=flatten(data).filter(field=>`${field.path} ${textValue(field.value)}`.toLowerCase().includes(query.toLowerCase()));
    return `<div class="field-list">${fields.length?fields.map(field=>`<div class="detail-field"><span class="detail-path">${esc(field.path)}</span><span class="detail-value">${esc(textValue(field.value))}</span></div>`).join(''):'<div class="detail-empty">No matching fields.</div>'}</div>`;
  }
  function showDetails(data,title='Sample details') {
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
  function findResources(section,expression) {return (section?.resources||[]).filter(resource=>expression.test(`${resource.key} ${resource.path}`));}
  async function showTriage() {
    openDrawer('triage','Task / process triage','INCIDENT WORKSPACE',true);$('drawer-body').innerHTML=loading('Opening synthetic task and process examples…');
    const results=await Promise.allSettled([loadSection('tasks',true),loadSection('system',true)]);if(state.drawer!=='triage')return;
    const tasks=results[0].status==='fulfilled'?results[0].value:null;const system=results[1].status==='fulfilled'?results[1].value:null;
    const taskResource=findResources(tasks,/\/tasks(?:\?|$)/)[0];const historyResources=findResources(tasks,/history/);const processResources=findResources(system,/processes/);
    const taskRows=good(taskResource)?resourceRows(taskResource.data)||[]:[];
    state.triage={taskRows,history:historyResources.filter(good).flatMap(resource=>resourceRows(resource.data)||[]),processes:processResources.filter(good).flatMap(resource=>resourceRows(resource.data)||[]),historyReady:historyResources.some(good),processReady:processResources.some(good)};
    $('drawer-body').innerHTML=`<p class="drawer-intro">Choose a synthetic task to compare its sample history with sample processes. Matching a PID does not establish process identity. No task runs here.</p><label class="form-label" for="triage-task">Task to investigate</label><select class="select-field" id="triage-task"><option value="">Select a task…</option>${taskRows.map((row,index)=>`<option value="${index}">${esc(valueAt(row,['Name','TaskName'])||'Task')} · ID ${esc(valueAt(row,['ID','TaskID'])??'not supplied')}</option>`).join('')}</select>${!taskRows.length?'<div class="notice">No task examples are included in this sample.</div>':''}<div class="detail-meta">${badge(`${state.triage.history.length} history records`,state.triage.historyReady?'ok':'warning')}${badge(`${state.triage.processes.length} sample processes`,state.triage.processReady?'ok':'warning')}</div><div id="triage-results"></div>`;
    $('triage-task').addEventListener('change',event=>renderTriage(event.target.value));
  }
  function renderTriage(index) {
    if(index===''){$('triage-results').innerHTML='';return;}
    const triage=state.triage;const task=triage.taskRows[Number(index)];const id=valueAt(task,['ID','TaskID']);
    const history=triage.history.filter(row=>String(valueAt(row,['TaskID','Task','ID']))===String(id));
    const pids=[...new Set(history.map(row=>valueAt(row,['PID','ProcessID','JobNumber'])).filter(value=>value!==undefined&&value!==null&&String(value)!=='0'))];
    const processes=triage.processes.filter(row=>pids.some(pid=>String(pid)===String(valueAt(row,['PID','ProcessID','ID']))));
    const summary=flatten(task).filter(field=>['id','name','taskname','type','status','state','suspended','nextrun','lastrun','namespace'].includes(normalize(field.path)));
    $('triage-results').innerHTML=`<div class="drawer-block"><h3>Selected task</h3>${detailFields(Object.fromEntries(summary.map(field=>[field.path,field.value])))}</div><h3 class="triage-heading">Sample activity ${badge(history.length)}</h3>${!triage.historyReady?'<p class="drawer-intro">No task-history sample is included. This is not execution evidence.</p>':!history.length?'<p class="drawer-intro">No history example is authored for this synthetic task. Nothing runs in this preview.</p>':history.slice(0,25).map(row=>`<div class="triage-card"><div class="triage-card-header"><span>Task ${esc(id)}</span>${badge('PID '+(valueAt(row,['PID','ProcessID','JobNumber'])??'not supplied'))}</div>${detailFields(row)}</div>`).join('')}${history.length>25?'<p class="explorer-meta">Showing the first 25 matching history records.</p>':''}${pids.length?`<div class="pid-caveat"><strong>Correlation, not proof.</strong> A PID can be reused after a process exits. A current process with the same PID is not necessarily the historical activity. Compare the recorded times and process details before drawing a conclusion.</div><h3 class="triage-heading">Sample processes with matching PIDs ${badge(processes.length)}</h3>${!triage.processReady?'<p class="drawer-intro">The process sample is unavailable.</p>':processes.length?processes.map(row=>`<div class="triage-card">${detailFields(row)}</div>`).join(''):'<p class="drawer-intro">No sample process matches these example history PIDs. In the local app, a completed task may have no active process.</p>'}`:''}`;
  }
  async function refresh() {
    state.query='';state.page=0;state.sort=null;$('table-search').value='';
    const button=$('refresh-button');button.disabled=true;button.querySelector('svg')?.classList.add('spinning');
    await Promise.allSettled([loadStatus(),loadSection(state.section,true)]);button.disabled=false;button.querySelector('svg')?.classList.remove('spinning');
  }
  let toastTimer;
  function toast(message) {$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>{$('toast').hidden=true;},4500);}
  async function dispatch(event) {
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
  document.addEventListener('click',event=>{Promise.resolve(dispatch(event)).catch(()=>toast('The operation could not complete. Refresh the relevant source.'));});
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'){if(!$('drawer-layer').hidden)closeDrawer();else document.body.classList.remove('nav-open');}
    if(event.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)&&$('drawer-layer').hidden){event.preventDefault();$('table-search').focus();}
    if(event.key==='Enter'&&event.target.matches('tr[data-action="row"]')){event.preventDefault();event.target.click();}
    if(event.key==='Tab'&&!$('drawer-layer').hidden){const focusable=[...$('drawer').querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),a[href],[tabindex="0"]')].filter(el=>el.offsetParent!==null);const first=focusable[0],last=focusable.at(-1);if(event.shiftKey&&(document.activeElement===first||document.activeElement===$('drawer'))){event.preventDefault();last?.focus();}else if(!event.shiftKey&&(document.activeElement===last||document.activeElement===$('drawer'))){event.preventDefault();first?.focus();}}
  });
  $('table-search').addEventListener('input',event=>{state.query=event.target.value.trim().toLowerCase();state.page=0;renderResource();});
  window.addEventListener('hashchange',()=>{const id=location.hash.slice(1);if(areas[id]&&id!==state.section)navigate(id);});
  hydrate();state.section=areas[location.hash.slice(1)]?location.hash.slice(1):'system';renderNavigation();
  Promise.allSettled([loadStatus(),loadSection(state.section)]);
})();
