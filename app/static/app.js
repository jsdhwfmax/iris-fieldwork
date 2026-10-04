/* IRIS Fieldwork — dependency-free client. All instance data comes from the local API. */
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
  function loading(message='Loading live data…') {return `<div class="loading-state"><span class="spinner"></span><span>${esc(message)}</span></div>`;}
  async function api(path, options={}) {
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),30000);
    try {
      const response=await fetch(path,{credentials:'same-origin',cache:'no-store',...options,signal:controller.signal,headers:{Accept:'application/json',...options.headers}});
      const type=response.headers.get('content-type')||'';
      if(!type.includes('application/json')) throw new Error('The local service returned a non-JSON response.');
      const data=await response.json();
      if(!response.ok) {const error=new Error(data.message||data.error?.message||`The local service returned HTTP ${response.status}.`);error.payload=data;throw error;}
      return data;
    } catch(error) {if(error.name==='AbortError') throw new Error(path==='/api/action'?'The request timed out; the command may already have executed.':'The request timed out. Refresh to try again.');throw error;} finally {clearTimeout(timer);}
  }
  function renderNavigation() {
    $('section-nav').innerHTML=Object.entries(areas).map(([id,area])=>`<button class="nav-link" data-action="navigate" data-section="${id}" ${id===state.section?'aria-current="page"':''}>${svg(area.icon)}<span>${area.label}</span></button>`).join('');
    const area=areas[state.section];$('breadcrumb-current').textContent=area.label;$('section-eyebrow').textContent=`${area.label.toUpperCase()} / ${area.number}`;$('section-title').textContent=area.title;$('section-description').textContent=area.description;
    document.title=`${area.label} · IRIS Fieldwork`;
  }
  async function loadStatus() {
    try {state.status=await api('/api/status');renderStatus();return state.status;}
    catch(error) {
      $('connection-dot').className='state-dot error';$('connection-label').textContent='Service unavailable';$('instance-description').textContent=error.message;$('instance-version').textContent='No instance information received';
      notice(error.message,true);return null;
    }
  }
  function renderStatus() {
    const status=state.status;const upstream=status?.upstream;const data=upstream?.data||{};const connected=upstream?.state==='ok';
    $('connection-dot').className=`state-dot${connected?' ok':' error'}`;$('connection-label').textContent=connected?'IRIS connected':'IRIS unavailable';
    $('instance-description').textContent=connected?`${data.product||'InterSystems IRIS'}${data.systemMode?' · '+textValue(data.systemMode):''}`:(upstream?.error?.message||'The instance connection is not available.');
    $('instance-version').textContent=data.serverVersion?`Version ${textValue(data.serverVersion)}`:data.apiVersion?`Admin API ${textValue(data.apiVersion)}`:'Version not supplied by this instance';
    if(!connected) notice(upstream?.error?.message||'The instance did not return a successful status response. Source availability is shown separately.',true);else notice('');
  }
  function notice(message,isError=false) {const node=$('global-notice');node.hidden=!message;node.textContent=message;node.className=`notice${isError?' error':''}`;}
  function currentSection(){return state.sections[state.section];}
  function currentResource(){const resources=currentSection()?.resources||[];return resources.find(resource=>resource.key===state.resourceKeys[state.section])||resources[0];}
  function renderSectionLoading(id) {
    $('source-tabs').innerHTML='<span class="muted" style="font-size:11px">Loading this section’s sources…</span>';
    $('metric-sources').textContent='—';$('metric-records').textContent='—';$('metric-time').textContent='Requesting snapshot';
    $('snapshot-state').outerHTML='<span id="snapshot-state" class="badge badge-neutral">Loading</span>';
    $('resource-title').textContent=areas[id].label;$('resource-description').textContent='Requesting a fresh response from the connected instance.';
    $('source-context').innerHTML='<p class="muted">Source details will appear when this section finishes loading.</p>';$('section-limitations').innerHTML='';$('resource-actions').innerHTML='';
    $('resource-content').innerHTML=loading();$('resource-content').setAttribute('aria-busy','true');$('inspect-button').disabled=true;
    $('table-search').disabled=true;$('filter-count').textContent='';$('table-footer').textContent='Waiting for this section’s snapshot';
  }
  async function loadSection(id,force=false) {
    if(state.sections[id]&&!force) return state.sections[id];
    const version=(state.loadVersion[id]||0)+1;state.loadVersion[id]=version;
    if(id===state.section)renderSectionLoading(id);
    try {
      const payload=await api(`/api/section/${encodeURIComponent(id)}`);
      if(!Array.isArray(payload.resources)) throw new Error('This section returned an invalid source list.');
      if(state.loadVersion[id]!==version)return payload;
      state.sections[id]={...payload,loadedAt:new Date()};
      if(id===state.section) renderSection();return state.sections[id];
    } catch(error) {
      if(id===state.section&&state.loadVersion[id]===version){$('resource-content').innerHTML=empty('Section unavailable',error.message,'warning');$('resource-content').setAttribute('aria-busy','false');$('source-tabs').innerHTML='';$('metric-sources').textContent='—';$('metric-records').textContent='—';$('metric-time').textContent='No snapshot received';$('snapshot-state').outerHTML='<span id="snapshot-state" class="badge badge-error">Unavailable</span>';$('resource-title').textContent=areas[id].label;$('resource-description').textContent='The local service could not load this section.';$('table-footer').textContent='No snapshot loaded';$('source-context').innerHTML='<p class="muted">Refresh to request this section again.</p>';}
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
    $('metric-time').textContent=section.loadedAt.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});
    const snapshot=available===resources.length&&resources.length?'Live snapshot':resources.some(hasData)?'Partial snapshot':'Unavailable';
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
    $('resource-description').textContent=resource.state==='partial'?'Available measurements are retained; some values could not be read.':good(resource)?'Current response from the connected instance.':'This source could not supply a live response.';
    $('inspect-button').disabled=resource.data===null||resource.data===undefined;
    $('source-context').innerHTML=`<div class="context-row"><span class="context-label">Availability</span>${sourceBadge(resource)}</div><div class="context-row"><span class="context-label">Request</span><span class="method">${esc(resource.method||'GET')}</span><div class="context-value endpoint">${esc(resource.path||'Not supplied')}</div></div><div class="context-row"><span class="context-label">HTTP response</span><div class="context-value">${esc(resource.http_status??'No response')}</div></div><div class="context-row"><span class="context-label">Response shape</span><div class="context-value">${hasData(resource)?esc(shapeLabel(resource)):'Not available'}</div></div>${resource.error?`<div class="context-row"><span class="context-label">Source message</span><div class="context-value">${esc(resource.error.message||resource.error.code||'Request did not complete.')}</div></div>`:''}`;
    if(state.sourceActionNotes?.length)$('source-context').insertAdjacentHTML('beforeend',`<div class="context-row"><span class="context-label">Management availability</span>${state.sourceActionNotes.map(note=>`<p class="context-value">${esc(note)}</p>`).join('')}</div>`);
    if(!hasData(resource)) {
      const unsupported=['not_found','unsupported'].includes(resource.state);
      $('resource-content').innerHTML=empty(unsupported?'Endpoint not exposed':'Source unavailable',resource.error?.message||(unsupported?'The connected instance does not expose this endpoint. Other sources remain available.':'Review the source status and instance privileges, then refresh.'),'warning');
      $('filter-count').textContent='';$('table-footer').textContent='No data was substituted for this response.';return;
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
    if(!visible.length){$('resource-content').innerHTML=empty(state.query?'No matching records':'No records returned',state.query?'Try another name, identifier or nested field value.':'This endpoint returned an empty collection.');}
    else {$('resource-content').innerHTML=`<div class="table-scroll"><table><thead><tr>${columns.map(key=>`<th scope="col" aria-sort="${state.sort?.key===key?(state.sort.direction===1?'ascending':'descending'):'none'}"><button class="text-link" style="text-decoration:none;color:inherit" data-action="sort" data-key="${esc(key)}">${esc(human(key))}${state.sort?.key===key?(state.sort.direction===1?' ↑':' ↓'):''}</button></th>`).join('')}<th scope="col"><span class="visually-hidden">Inspect</span></th></tr></thead><tbody>${visible.map(({row,index})=>`<tr data-action="row" data-index="${index}" tabindex="0" aria-label="Inspect ${esc(textValue(valueAt(row,['Name','TaskName','ID','PID','Record'])??'record '+(index+1)))}">${columns.map(key=>`<td title="${esc(typeof row[key]==='object'?'Open record to inspect nested fields':textValue(row[key]))}" class="${['id','pid','taskid'].includes(normalize(key))?'cell-mono':''}">${displayCell(row[key])}</td>`).join('')}<td><span class="row-open">${svg('right')}</span></td></tr>`).join('')}</tbody></table></div>`;}
    const fieldCount=[...new Set(rows.flatMap(row=>Object.keys(row)))].length;
    $('table-footer').innerHTML=`<span>${filtered.length?`${start+1}–${Math.min(start+state.pageSize,filtered.length)} of ${filtered.length.toLocaleString()}`:'0 records'}${fieldCount>6?' · More fields in row details':''}</span><div class="pagination"><button class="icon-button" data-action="previous-page" aria-label="Previous page" ${state.page===0?'disabled':''}>${svg('left')}</button><span>${state.page+1} / ${pages}</span><button class="icon-button" data-action="next-page" aria-label="Next page" ${state.page>=pages-1?'disabled':''}>${svg('right')}</button></div>`;
  }
  function renderObject(data) {
    const fields=flatten(data).filter(field=>`${field.path} ${textValue(field.value)}`.toLowerCase().includes(state.query));
    $('filter-count').textContent=`${fields.length} ${fields.length===1?'field':'fields'}`;
    $('resource-content').innerHTML=fields.length?`<div class="object-summary">${fields.slice(0,80).map(field=>`<div class="object-field"><span class="field-label">${esc(field.path)}</span><span class="field-value">${displayCell(field.value)}</span></div>`).join('')}</div>`:empty('No matching fields','Try another field name or value.');
    $('table-footer').textContent=fields.length>80?'Showing 80 fields. Inspect the response to search all fields.':'Object response · Field values are shown as returned';
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
    $('filter-count').textContent='Measured values';
    $('resource-content').innerHTML=`<div class="runtime-overview"><div class="runtime-scope">${svg('compass')}<span>${esc(data.scope||'Measurement scope was not supplied.')}</span></div><div class="runtime-cards"><div class="runtime-card"><span class="metric-label">Kernel CPU busy</span><strong>${cpu===null?'—':cpu.toLocaleString(undefined,{maximumFractionDigits:1})+'<small>%</small>'}</strong>${meter(cpu,'Kernel CPU busy')}<p>${num(data.cpuSampleMilliseconds)?`Measured over ${esc(data.cpuSampleMilliseconds)} ms`:'Sampling period not supplied'}</p></div><div class="runtime-card"><span class="metric-label">Container memory used</span><strong>${num(memoryUsed)?esc(bytes(memoryUsed)):'—'}</strong>${meter(memoryPercent,'Container memory used')}<p>${num(memoryLimit)?'of '+esc(bytes(memoryLimit))+' limit':'Container limit not supplied'}</p></div><div class="runtime-card"><span class="metric-label">IRIS filesystem used</span><strong>${num(diskUsed)?esc(bytes(diskUsed)):'—'}</strong>${meter(diskPercent,'IRIS filesystem used')}<p>${num(diskAvailable)?esc(bytes(diskAvailable))+' available':'Availability not supplied'}</p></div></div><div class="runtime-facts"><div><span>Kernel memory available</span><strong>${esc(bytes(data.memoryAvailableBytes))}</strong></div><div><span>Kernel memory total</span><strong>${esc(bytes(data.memoryTotalBytes))}</strong></div><div><span>Container CPU limit</span><strong>${num(data.containerCpuLimitCores)?esc(data.containerCpuLimitCores)+' cores':'Not supplied'}</strong></div><div><span>IRIS filesystem size</span><strong>${esc(bytes(diskTotal))}</strong></div></div><p class="runtime-caption">A single sample, not a trend. Kernel CPU and memory describe the Linux environment visible to IRIS; container limits are shown separately.</p></div>`;
    $('table-footer').innerHTML=`<span>${sampled&&!Number.isNaN(sampled.getTime())?'Sampled '+esc(sampled.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'})):'Sample time not supplied'}</span><button class="text-link" data-action="inspect">Inspect raw fields</button>`;
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
    $('table-footer').textContent=`${sources.length} log sources · ${state.query?'Filtered excerpt':'Bounded live excerpts'} · Sensitive fields are scrubbed by the server`;
  }
  const actionDefinition = id => state.status?.capabilities?.actions?.find(action=>action.id===id);
  function actionButton(id,label,action,extra='') {const definition=actionDefinition(id);return `<button class="button button-small" data-action="${action}" ${extra} ${definition?.enabled?'':'disabled'} title="${esc(definition?.reason||'This command is not enabled by the connected server.')}">${esc(label)}</button>`;}
  function renderResourceActions(resource) {
    let content='';state.sourceActionNotes=[];
    if(state.section==='permissions')content=actionButton('resource.create','Create resource','create-resource');
    if(state.section==='security'&&resource.key==='wallet_collections')content=actionButton('wallet.collection.create','New collection','create-collection');
    if(state.section==='logs')content=`<button class="button button-small" data-action="message-archives">Browse older messages</button><button class="button button-small" data-action="log-query" data-kind="audit">Search audit records</button>${resource.key==='journal_files'?'<button class="button button-small" data-action="log-query" data-kind="journal">Search journal</button>':''}`;
    $('resource-actions').innerHTML=content;
    const ids=state.section==='permissions'?['resource.create']:state.section==='security'&&resource.key==='wallet_collections'?['wallet.collection.create']:[];
    state.sourceActionNotes=ids.map(actionDefinition).filter(definition=>definition&&!definition.enabled&&definition.reason).map(definition=>definition.reason);
  }
  function inspectDescriptor(row) {
    const key=currentResource()?.key;let kind,name=valueAt(row,['Name','Alias','ID','Record']);
    const kinds={roles:'role',users:'user',resources:'resource',wallet_collections:'wallet_collection',x509_credentials:'x509',ssl_configurations:'tls',oauth_servers:'oauth_server',oauth_clients:'oauth_registration'};
    kind=kinds[key];
    if(key==='oauth_servers')name=valueAt(row,['ServerId','ID','Name','Issuer']);
    if(key==='oauth_clients')name=valueAt(row,['ClientId','ID','Name']);
    return kind&&name!==undefined&&name!==null?{kind,name:String(name)}:null;
  }
  function safeSecurityMetadata(value) {
    if(Array.isArray(value))return value.map(safeSecurityMetadata);
    if(!value||typeof value!=='object')return value;
    return Object.fromEntries(Object.entries(value).filter(([key,child])=>(typeof child==='boolean'&&normalize(key).startsWith('has'))||!(/password|privatekey|clientsecret|secretvalue|accesstoken|refreshtoken/.test(normalize(key))||['secret','config','token'].includes(normalize(key)))).map(([key,child])=>[key,safeSecurityMetadata(child)]));
  }
  async function openInspection(kind,name,context='') {
    const requestKey=`${kind}:${name}:${context}:${Date.now()}`;state.inspectRequest=requestKey;
    openDrawer('inspection',name,`${human(kind).toUpperCase()} DETAILS`,true);$('drawer-body').innerHTML=loading('Loading current configuration…');
    try {
      const query=new URLSearchParams({kind,name});if(context)query.set('context',context);
      const resource=await api('/api/inspect?'+query);
      if(state.drawer!=='inspection'||state.inspectRequest!==requestKey)return;
      if(!['role','user','resource'].includes(kind))resource.data=safeSecurityMetadata(resource.data);
      state.inspection={kind,name,context,resource};
      if(kind==='wallet_collection'&&hasData(resource))state.walletCollection={name,data:resource.data};
      renderInspection();
    }catch(error){if(state.drawer==='inspection'&&state.inspectRequest===requestKey)$('drawer-body').innerHTML=empty('Inspection unavailable',error.message,'warning');}
  }
  function roleNames(value) {const rows=Array.isArray(value)?value:typeof value==='string'?value.split(','):[];return rows.map(row=>typeof row==='string'?row:valueAt(row,['Name','Role'])).filter(Boolean);}
  function grantTable(grants) {return `<div class="grant-display"><table><thead><tr><th>Resource</th><th>Permissions</th></tr></thead><tbody>${grants.length?grants.map(grant=>`<tr><td>${esc(grant.Name)}</td><td class="cell-mono">${esc(grant.Permissions||'None')}</td></tr>`).join(''):'<tr><td colspan="2">No direct resource grants.</td></tr>'}</tbody></table></div>`;}
  function renderInspection() {
    const {kind,name,resource}=state.inspection;const data=resource.data;
    if(!hasData(resource)){$('drawer-body').innerHTML=`<div class="detail-meta">${sourceBadge(resource)}</div>${empty('Configuration unavailable',resource.error?.message||'This endpoint did not supply details.','warning')}`;return;}
    let tools='',focused='';
    if(kind==='role') {
      if(data?.editable===true)tools+=actionButton('role.set_resources','Edit resource grants','edit-role');
      else tools+='<span class="badge badge-neutral">Protected or inherited role · Read only</span>';
      focused=`<h3 class="triage-heading">Direct resource grants</h3>${grantTable(Array.isArray(data.Resources)?data.Resources:[])}`;
    }
    if(kind==='user'||kind==='role') {
      const names=roleNames(kind==='user'?data.Roles:data.GrantedRoles);
      if(names.length)focused+=`<h3 class="triage-heading">${kind==='user'?'Assigned roles':'Granted roles'}</h3><div class="assignment-links">${names.map(role=>`<button class="button button-small" data-action="inspect-linked" data-kind="role" data-name="${esc(role)}">${esc(role)} ${svg('right')}</button>`).join('')}</div>`;
    }
    if(kind==='wallet_collection')tools+=`<button class="button button-small" data-action="inspect-linked" data-kind="wallet_secrets" data-name="${esc(name)}">Browse secret metadata</button>${actionButton('wallet.secret.create','Create secret','create-secret')}`;
    if(kind==='wallet_secrets') {
      tools+=actionButton('wallet.secret.create','Create secret','create-secret');
      const rows=resourceRows(data)||[];state.secretRows=rows;
      focused=`<p class="drawer-intro">Only secret names and types are returned. Stored values cannot be inspected here.</p><div class="secret-list">${rows.length?rows.map((row,index)=>{const target=resource.targets?.find(item=>item.name===valueAt(row,['Name','SecretName']));const controls=(target?.actions||[]).map(id=>id==='wallet.secret.update'?actionButton(id,'Replace','edit-secret',`data-index="${index}"`):id==='wallet.secret.delete'?actionButton(id,'Remove','delete-secret',`data-index="${index}"`):'').join('');return `<div class="secret-row"><div><strong>${esc(valueAt(row,['Name','SecretName'])||'Unnamed secret')}</strong><span>${esc(valueAt(row,['Type'])||'Type not supplied')}</span></div><div class="action-list">${controls||badge('Metadata only')}</div></div>`;}).join(''):empty('No secrets returned','This collection has no visible secret metadata.')}</div>`;
    }
    if(kind==='oauth_server')tools+='<button class="button button-small" data-action="oauth-client">Inspect an OAuth client</button>';
    $('drawer-body').innerHTML=`<div class="detail-meta">${sourceBadge(resource)}${badge('HTTP '+(resource.http_status??'—'))}<span class="endpoint">${esc(resource.path||'')}</span></div>${tools?`<div class="action-list">${tools}</div>`:''}${focused}${kind==='wallet_secrets'?'':`<h3 class="triage-heading">Configuration fields</h3><div class="drawer-toolbar"><label class="search-field">${svg('search')}<input id="inspection-search" type="search" placeholder="Search configuration fields…" aria-label="Search configuration fields"></label></div><div id="inspection-fields">${detailFields(data)}</div>`}${resource.limitations?.length?`<ul class="coverage-notes">${resource.limitations.map(note=>`<li>${esc(note)}</li>`).join('')}</ul>`:''}`;
    $('inspection-search')?.addEventListener('input',event=>{$('inspection-fields').innerHTML=detailFields(data,event.target.value);});
  }
  function formField(id,label,{value='',placeholder='',required=true,type='text',help='',pattern='',maxlength=128}={}) {return `<div class="form-field"><label class="form-label" for="${id}">${esc(label)}</label><input class="text-input" id="${id}" type="${type}" value="${esc(value)}" placeholder="${esc(placeholder)}" ${required?'required':''} ${pattern?`pattern="${esc(pattern)}"`:''} maxlength="${maxlength}" autocomplete="off">${help?`<p class="field-help">${esc(help)}</p>`:''}</div>`;}
  function formFooter(label='Review changes') {return `<div id="form-error" class="notice error" role="alert" hidden></div><div class="review-controls"><button class="button" type="button" data-action="close-drawer">Cancel</button><button class="button button-primary" type="submit">${esc(label)}</button></div>`;}
  function formError(message) {const node=$('form-error');if(node){node.hidden=false;node.textContent=message;}}
  function openManagedForm(title,intro,body,submit) {
    openDrawer('managed-form',title,'PREPARE A REVIEW');$('drawer-body').innerHTML=`<p class="drawer-intro">${esc(intro)}</p><form id="managed-form">${body}${formFooter()}</form>`;
    $('managed-form').addEventListener('submit',event=>{event.preventDefault();if(!event.target.reportValidity())return;Promise.resolve(submit()).catch(error=>formError(error.message||'The form could not be prepared.'));});
  }
  function showCreateResource() {
    if(!actionDefinition('resource.create')?.enabled){toast('Resource creation is not enabled.');return;}
    openManagedForm('Create a resource','Create a named resource with no public permissions. Assign it to a role separately.',formField('new-resource-name','Resource name',{placeholder:'OperationsReader',pattern:'[A-Za-z][A-Za-z0-9_.-]{0,63}',maxlength:64,help:'Use a custom name. System and administrative names are protected.'})+formField('new-resource-description','Description',{maxlength:240,help:'Describe the resource in 1–240 printable characters.'}),()=>{
      const target={name:$('new-resource-name').value.trim(),description:$('new-resource-description').value.trim()};
      reviewFormCommand('resource.create',target,{Resource:target.name,Description:target.description||'None','Public permissions':'None'},'permissions');
    });
  }
  function grantEditorRow(grant={Name:'',Permissions:''}) {
    const permissions=String(grant.Permissions||'');
    return `<div class="grant-editor-row"><input class="text-input grant-name" aria-label="Resource name" value="${esc(grant.Name||'')}" list="resource-names" placeholder="Resource name" required maxlength="128"><div class="permission-choices">${['R','W','U'].map(code=>`<label title="${{R:'Read',W:'Write',U:'Use'}[code]}"><input type="checkbox" value="${code}" ${permissions.includes(code)?'checked':''}>${code}</label>`).join('')}</div><button class="icon-button" type="button" data-action="remove-grant" aria-label="Remove grant">${svg('close')}</button></div>`;
  }
  function showRoleEditor() {
    const inspection=state.inspection;const data=inspection?.resource?.data;
    if(inspection?.kind!=='role'||data?.editable!==true||!actionDefinition('role.set_resources')?.enabled){toast('This role is not editable.');return;}
    const expected=Array.isArray(data.Resources)?data.Resources.map(grant=>({Name:grant.Name,Permissions:grant.Permissions})):[];
    state.roleResourceLimit=data.resource_limit||40;
    const names=(state.sections.permissions?.resources.find(resource=>resource.key==='resources')?.data||[]).map(row=>valueAt(row,['Name'])).filter(Boolean);
    openManagedForm('Edit resource grants',`Review direct grants for ${inspection.name}. Existing role inheritance is preserved. Removing all rows revokes all direct resource grants.`,
      `<datalist id="resource-names">${names.map(name=>`<option value="${esc(name)}"></option>`).join('')}</datalist><div class="grant-editor-labels"><span>Resource</span><span>Read · Write · Use</span></div><div id="grant-editor">${expected.map(grantEditorRow).join('')}</div><button class="button button-small" type="button" data-action="add-grant" style="margin:10px 0 20px">+ Add resource grant</button><p class="field-help">R = Read · W = Write · U = Use. Only enter permissions supported by the resource.</p>`,()=>{
      const resources=[...$('grant-editor').querySelectorAll('.grant-editor-row')].map(row=>({Name:row.querySelector('.grant-name').value.trim(),Permissions:[...row.querySelectorAll('input[type="checkbox"]:checked')].map(input=>input.value).join('')}));
      if(resources.some(grant=>!grant.Name||!grant.Permissions))throw new Error('Every grant needs a resource name and at least one permission. Remove empty rows to revoke a grant.');
      if(resources.length>state.roleResourceLimit)throw new Error(`This editor accepts at most ${state.roleResourceLimit} resource grants.`);
      if(new Set(resources.map(grant=>grant.Name)).size!==resources.length)throw new Error('Each resource can appear only once.');
      reviewFormCommand('role.set_resources',{name:inspection.name,resources,expected_resources:expected},{Role:inspection.name,Before:expected,After:resources},'permissions',{inspection:{kind:'role',name:inspection.name}});
    });
  }
  async function availableResourceNames() {
    const section=state.sections.permissions||await loadSection('permissions');
    return (resourceRows(section.resources.find(resource=>resource.key==='resources')?.data)||[]).map(row=>valueAt(row,['Name'])).filter(Boolean);
  }
  async function showCreateCollection() {
    if(!actionDefinition('wallet.collection.create')?.enabled){toast('Collection creation is not enabled.');return;}
    const names=await availableResourceNames();
    const options=names.map(name=>`<option value="${esc(name)}:U"></option>`).join('');
    openManagedForm('Create wallet collection','Choose the existing resource permissions that control editing and use of this collection.',formField('new-collection-name','Collection name',{pattern:'[A-Za-z][A-Za-z0-9_-]{0,63}',maxlength:64,placeholder:'OperationsKeys'})+`<datalist id="wallet-resource-permissions">${options}</datalist>`+formField('collection-edit','Edit permission',{placeholder:'ResourceName:U',help:'Existing resource plus permission: U (Use), R (Read), or W (Write). Exact names outside the current snapshot may be entered.'})+formField('collection-use','Use permission',{placeholder:'ResourceName:U'}),()=>{
      const target={name:$('new-collection-name').value.trim(),edit_resource:$('collection-edit').value.trim(),use_resource:$('collection-use').value.trim(),expected_absent:true};
      if(![target.edit_resource,target.use_resource].every(value=>/^%?[A-Za-z][A-Za-z0-9_.-]{0,95}:(?:USE|READ|WRITE|U|R|W)$/.test(value)))throw new Error('Enter an existing resource and permission in each field, such as ResourceName:U.');
      reviewFormCommand('wallet.collection.create',target,{Collection:target.name,'Edit resource':target.edit_resource,'Use resource':target.use_resource},'security');
    });
    $('collection-edit').setAttribute('list','wallet-resource-permissions');$('collection-use').setAttribute('list','wallet-resource-permissions');
  }
  async function collectionBindings() {
    const inspection=state.inspection;const name=inspection?.kind==='wallet_collection'||inspection?.kind==='wallet_secrets'?inspection.name:state.walletCollection?.name;
    if(!name)throw new Error('Open a wallet collection before preparing a secret change.');
    let data=state.walletCollection?.name===name?state.walletCollection.data:null;
    if(!data){const resource=await api('/api/inspect?'+new URLSearchParams({kind:'wallet_collection',name}));if(!good(resource))throw new Error(resource.error?.message||'Collection bindings are unavailable.');data=resource.data;state.walletCollection={name,data};}
    const edit=valueAt(data,['EditResource','edit_resource']);const use=valueAt(data,['UseResource','use_resource']);
    if(typeof edit!=='string'||typeof use!=='string'||!edit||!use)throw new Error('The collection did not return verifiable edit and use resources.');
    return {collection:name,edit_resource:edit,use_resource:use};
  }
  async function showSecretForm(index=null) {
    const existing=index===null?null:state.secretRows?.[index];const action=existing?'wallet.secret.update':'wallet.secret.create';
    if(!actionDefinition(action)?.enabled){toast('This secret operation is not enabled.');return;}
    const bindings=await collectionBindings();const secretName=existing?valueAt(existing,['Name','SecretName']):'';
    openManagedForm(existing?'Replace secret':'Create secret',`${bindings.collection} · %Wallet.KeyValue. ${existing?'Replace the complete key-value configuration. Existing values cannot be read or recovered here.':'Provide a key name and permitted hosts. You will enter the new value in a password field during review.'}`,
      formField('secret-name','Secret name',{value:secretName,pattern:'[A-Za-z][A-Za-z0-9_-]{0,63}',maxlength:64})+formField('secret-key','Key name',{placeholder:'Authorization',pattern:'[A-Za-z][A-Za-z0-9_-]{0,63}',maxlength:64})+formField('secret-hosts','Allowed hosts',{placeholder:'api.example.com',help:'1–16 distinct DNS names or IP addresses, separated by commas. HTTPS is required; usage is limited to HTTP.',maxlength:1024}),()=>{
      if(existing&&$('secret-name').value.trim()!==String(secretName))throw new Error('Replacing a secret cannot change its name. Create a separate secret to use another name.');
      const hosts=$('secret-hosts').value.split(',').map(host=>host.trim()).filter(Boolean);if(!hosts.length||hosts.length>16||new Set(hosts).size!==hosts.length)throw new Error('Specify 1–16 distinct allowed hosts.');
      const key=$('secret-key').value.trim();const target={...bindings,name:$('secret-name').value.trim(),type:'%Wallet.KeyValue',expected_type:existing?'%Wallet.KeyValue':null,config:{AllowedHosts:hosts,RequireTLS:true,Usage:['HTTP']}};
      reviewFormCommand(action,target,{Collection:bindings.collection,Secret:target.name,Type:target.type,Operation:existing?'Replace complete configuration':'Create new secret','Key name':key,'Allowed hosts':target.config.AllowedHosts,RequireTLS:target.config.RequireTLS,Usage:target.config.Usage,EditResource:target.edit_resource,UseResource:target.use_resource},'security',{secretKey:key,inspection:{kind:'wallet_secrets',name:bindings.collection}});
    });
    if(existing)$('secret-name').readOnly=true;
  }
  async function showDeleteSecret(index) {
    const row=state.secretRows?.[index];if(!row||!actionDefinition('wallet.secret.delete')?.enabled)return;
    const bindings=await collectionBindings();const target={...bindings,name:valueAt(row,['Name','SecretName']),expected_type:'%Wallet.KeyValue'};
    reviewFormCommand('wallet.secret.delete',target,{Collection:bindings.collection,Secret:target.name,Operation:'Remove stored secret'},'security',{warning:'Removal deletes the stored value. This workspace cannot recover it.',inspection:{kind:'wallet_secrets',name:bindings.collection}});
  }
  function reviewFormCommand(actionId,target,summary,section,options={}) {
    const definition=actionDefinition(actionId);if(!definition?.enabled){toast('This command is no longer enabled.');return;}
    state.pendingForm={actionId,target,summary,section,options};renderFormReview();
  }
  function renderFormReview() {
    const draft=state.pendingForm;if(!draft)return;const definition=actionDefinition(draft.actionId);
    openDrawer('form-review',definition?.label||'Review change','REVIEW MANAGEMENT COMMAND');
    const hasSecret=!!draft.options.secretKey;
    const summary=draft.actionId==='role.set_resources'?`<div class="drawer-block"><span class="context-label">Role</span><div class="review-target">${esc(draft.target.name)}</div></div><h3 class="triage-heading">Current grants</h3>${grantTable(draft.summary.Before)}<h3 class="triage-heading">Proposed grants</h3>${grantTable(draft.summary.After)}`:detailFields(draft.summary);
    $('drawer-body').innerHTML=`<p class="drawer-intro">Confirm this specific change. The server rechecks your permissions and the current target before writing.</p>${summary}${draft.options.warning?`<div class="notice" style="margin-top:18px">${esc(draft.options.warning)}</div>`:''}${hasSecret?`<div class="secret-entry">${formField('review-secret-value','New secret value',{type:'password',maxlength:4096,help:'Sent once over this local session. The field is cleared when the request is sent; the value is never included in review details or read back.'})}</div>`:''}${!state.review?'<div class="notice" style="margin-top:18px">This browser is in read-only mode.</div><button class="button" data-action="enable-form-review">Enable command review</button>':''}<label class="check-row"><input type="checkbox" id="form-review-confirm" ${state.review?'':'disabled'}><span>I reviewed this target and the proposed change.</span></label><div class="review-controls"><button class="button" data-action="close-drawer">Cancel</button><button class="button ${draft.actionId.endsWith('.delete')?'button-danger':'button-primary'}" id="execute-form-command" data-action="execute-form-command" disabled>Confirm ${draft.actionId.endsWith('.delete')?'removal':'change'}</button></div><div id="form-command-result" style="margin-top:20px" aria-live="polite"></div>`;
    const update=()=>{$('execute-form-command').disabled=!state.review||!$('form-review-confirm').checked||(hasSecret&&!$('review-secret-value')?.value);};
    $('form-review-confirm').addEventListener('change',update);$('review-secret-value')?.addEventListener('input',update);
  }
  async function executeFormCommand() {
    const draft=state.pendingForm;if(!draft||state.busy||!state.review||!$('form-review-confirm')?.checked)return;
    if(draft.options.secretKey&&!$('review-secret-value')?.value)return;
    state.busy=true;$('execute-form-command').disabled=true;$('form-review-confirm').disabled=true;
    const isSecret=draft.actionId.startsWith('wallet.secret.');
    const target={...draft.target};if(draft.options.secretKey)target.config={...draft.target.config,Secret:{[draft.options.secretKey]:$('review-secret-value').value}};
    const body=JSON.stringify({action:draft.actionId,target,reviewed:true});
    if($('review-secret-value')){$('review-secret-value').value='';$('review-secret-value').disabled=true;}
    if(target.config?.Secret)delete target.config.Secret;
    $('form-command-result').innerHTML=loading('Sending the reviewed change…');
    try {
      const result=await api('/api/action',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state.status?.csrf_token||''},body});
      const message=isSecret?(result.ok?'The request completed. Only the verification status and secret metadata are retained.':'The request did not complete successfully. Inspect the collection metadata before trying again.'):(result.message||result.state||'Review the verification result.');
      const verification=isSecret?safeSecurityMetadata(result.verification):result.verification;
      $('form-command-result').innerHTML=`<div class="result-panel${result.ok?'':' error'}"><strong>${result.ok?'Change accepted':'Change not completed'}</strong><br>${esc(message)}</div><div class="detail-meta" style="margin-top:14px">${badge(human(result.state||'Unknown'),result.state==='verified'?'ok':'warning')}</div>${verification?`<details class="verification-metadata"><summary>Verification metadata</summary>${detailFields(verification)}</details>`:''}${draft.options.inspection?`<button class="button button-small" style="margin-top:18px" data-action="inspect-linked" data-kind="${esc(draft.options.inspection.kind)}" data-name="${esc(draft.options.inspection.name)}">Inspect current metadata</button>`:''}`;
      if(result.ok){state.walletCollection=null;try{await loadSection(draft.section,true);}catch(_){/* retained result */}}
    }catch(error){$('form-command-result').innerHTML=`<div class="result-panel error"><strong>Result needs attention</strong><br>${esc(isSecret?'The secret request could not be confirmed. The value has been cleared. Inspect current metadata before another attempt.':error.message)}<br>No automatic retry was attempted.</div>`;}
    finally{state.busy=false;state.pendingForm=null;}
  }
  function showOAuthClientPrompt() {
    openDrawer('oauth-client-prompt','Inspect OAuth client','READ CONFIGURATION');
    $('drawer-body').innerHTML=`<p class="drawer-intro">Enter the configured client application name. Only permitted metadata will be returned.</p><form id="oauth-client-form">${formField('oauth-client-name','Client application name')}${formFooter('Inspect client')}</form>`;
    $('oauth-client-form').addEventListener('submit',event=>{event.preventDefault();if(event.target.reportValidity())openInspection('oauth_client',$('oauth-client-name').value.trim());});
  }
  function showMessageArchives() {
    openDrawer('message-archives','Older message logs','READ-ONLY ARCHIVE BROWSER',true);
    state.messageArchives={view:'inventory',request:0,busy:false,inventory:null,inventoryOffsets:[0],content:null,contentOffsets:[0],selected:null};
    return loadMessageInventory([0]);
  }
  function archiveActive(browser,request=browser.request) {
    return state.drawer==='message-archives'&&state.messageArchives===browser&&browser.request===request;
  }
  const archiveOffset = value => Number.isSafeInteger(value)&&value>=0;
  function archiveNext(data) {return archiveOffset(data?.nextOffset)&&data.nextOffset>data.offset?data.nextOffset:null;}
  function archivePageValid(data,offset) {return data.offset===offset&&(data.nextOffset===null||archiveNext(data)!==null);}
  function archiveInvalid() {return {state:'unavailable',error:{message:'The archive service returned an invalid page. Refresh the file list and try again.'},data:null};}
  function archiveFailure(error) {
    return error.payload||{state:'unavailable',error:{message:'The local archive service could not be reached. Check the connection, then try again.'},data:null};
  }
  async function loadMessageInventory(offsets) {
    const browser=state.messageArchives;if(!browser||state.drawer!=='message-archives')return;
    const offset=offsets.at(-1);if(!archiveOffset(offset))return;
    const request=++browser.request;
    browser.view='inventory';browser.busy=true;browser.inventory=null;browser.selected=null;browser.inventoryOffsets=[...offsets];
    renderMessageArchives(browser);
    try {
      let result=await api(`/api/message-archives?offset=${offset}`);
      if(!archiveActive(browser,request))return;
      if(good(result)&&result.data?.state==='ok'&&(!archivePageValid(result.data,offset)||!Array.isArray(result.data.files)||result.data.files.length>50||result.data.files.some(file=>!file||typeof file!=='object')))result=archiveInvalid();
      browser.inventory=result;
    } catch(error) {if(archiveActive(browser,request))browser.inventory=archiveFailure(error);}
    finally {if(archiveActive(browser,request)){browser.busy=false;renderMessageArchives(browser);}}
  }
  async function loadMessageArchive(file,offsets=[0]) {
    const browser=state.messageArchives;if(!browser||state.drawer!=='message-archives')return;
    const offset=offsets.at(-1);
    if(!file||typeof file.name!=='string'||!file.name||!/^[a-f0-9]{64}$/.test(file.revision||'')||!archiveOffset(offset))return;
    const request=++browser.request;
    browser.view='file';browser.busy=true;browser.selected=file;browser.content=null;browser.contentOffsets=[...offsets];
    renderMessageArchives(browser);
    try {
      const params=new URLSearchParams({name:file.name,revision:file.revision,offset:String(offset)});
      let result=await api(`/api/message-archive?${params}`);
      if(!archiveActive(browser,request))return;
      if(good(result)&&result.data?.state==='ok'&&(!archivePageValid(result.data,offset)||!Array.isArray(result.data.records)||result.data.records.some(record=>!record||typeof record.line!=='string')||result.data.name!==file.name||result.data.revision!==file.revision))result=archiveInvalid();
      browser.content=result;
    } catch(error) {if(archiveActive(browser,request))browser.content=archiveFailure(error);}
    finally {if(archiveActive(browser,request)){browser.busy=false;renderMessageArchives(browser);}}
  }
  function archiveError(result) {
    const status=good(result)?result.data?.state:result?.state;
    const titles={changed:'This file changed',not_found:'File no longer available',invalid:'Archive request rejected',unsupported:'Archive browsing is not supported',forbidden:'Archive access denied',unauthorized:'Authentication needed'};
    const fallback=status==='changed'?'Refresh the file list and select the file again. Pages from different revisions are not combined.':status==='not_found'?'The selected file may have been removed or rotated. Refresh the file list.':'The instance did not return a readable archive page. Check source availability and try again.';
    return empty(titles[status]||'Archive source unavailable',result?.data?.message||result?.error?.message||fallback,'warning');
  }
  function archiveTime(value) {
    const date=value?new Date(value):null;
    return date&&!Number.isNaN(date.getTime())?date.toISOString().replace('T',' ').replace('Z',' UTC'):'Modification time not supplied';
  }
  function archiveCoverage(result) {
    const notes=Array.isArray(result?.limitations)?result.limitations.filter(note=>typeof note==='string'):[];
    return `${typeof result?.data?.scope==='string'?`<p class="archive-caption">${esc(result.data.scope)}</p>`:''}${notes.length?`<ul class="coverage-notes">${notes.map(note=>`<li>${esc(note)}</li>`).join('')}</ul>`:''}`;
  }
  function archivePaging(kind,offsets,data) {
    return `<nav class="archive-paging" aria-label="${kind==='list'?'Archive file list':'Message content'} pages"><button class="button button-small" data-action="archive-${kind}-previous" ${offsets.length<2?'disabled':''}>${svg('left')}Previous</button><span>Page ${offsets.length}</span><button class="button button-small" data-action="archive-${kind}-next" ${archiveNext(data)===null?'disabled':''}>Next${svg('right')}</button></nav>`;
  }
  function renderMessageArchives(browser) {
    if(!archiveActive(browser))return;
    const viewingFile=browser.view==='file';
    $('drawer-title').textContent=viewingFile?browser.selected.name:'Older message logs';
    const toolbar=`<div class="archive-toolbar">${viewingFile?'<button class="text-link" data-action="archive-back">← File list</button>':'<span class="explorer-meta">Up to 50 files per page</span>'}<button class="button button-small" data-action="archive-list-refresh" ${browser.busy&&!viewingFile?'disabled':''}>Refresh file list</button></div>`;
    const intro='<p class="drawer-intro">Read bounded excerpts from the instance’s rotated message-log files. Only listed filenames can be opened; no file is changed.</p>';
    let content;
    if(browser.busy)content=loading(viewingFile?'Reading this file revision…':'Loading message-log files…');
    else {
      const result=viewingFile?browser.content:browser.inventory,data=result?.data;
      if(!good(result)||data?.state!=='ok')content=archiveError(result);
      else if(!viewingFile) {
        const files=data.files;
        const count=files.length?`${data.offset+1}–${data.offset+files.length}${archiveOffset(data.total)?' of '+data.total.toLocaleString():''} files`:'No files on this page';
        content=`<div class="detail-meta">${badge('Available','ok')}${badge(count)}</div>${archiveCoverage(result)}${files.length?`<div class="archive-list">${files.map((file,index)=>{const selectable=typeof file.name==='string'&&file.name&&/^[a-f0-9]{64}$/.test(file.revision||'');return `<button class="archive-file" data-action="archive-file" data-index="${index}" ${selectable?'':'disabled'}><span class="archive-file-name">${esc(file.name||'Unnamed file')}${svg('right')}</span><span class="archive-file-meta"><span>${esc(bytes(file.sizeBytes))}</span><time>${esc(archiveTime(file.modifiedAt))}</time></span>${selectable?'':'<span class="archive-caption">A current filename and revision are required to read this file.</span>'}</button>`;}).join('')}</div>`:empty('No message-log files returned','No matching files are available on this inventory page. Refresh the list to check again.')}${archivePaging('list',browser.inventoryOffsets,data)}`;
      } else {
        const records=data.records;
        const omissionLabels={oversizeSegments:'oversize segment',partialSegments:'partial segment',binaryRecords:'binary record'};
        const omitted=Object.entries(omissionLabels).filter(([key])=>num(data.omitted?.[key])&&data.omitted[key]>0).map(([key,label])=>`${data.omitted[key].toLocaleString()} ${label}${data.omitted[key]===1?'':'s'}`);
        if(num(data.skippedBytes)&&data.skippedBytes>0)omitted.push(`${data.skippedBytes.toLocaleString()} skipped ${data.skippedBytes===1?'byte':'bytes'}`);
        const boundary=archiveNext(data)===null?'End of this file revision.':`Next page begins at byte ${data.nextOffset.toLocaleString()}.`;
        content=`<div class="detail-meta">${badge('Revision checked','ok')}${badge(records.length+' returned '+(records.length===1?'record':'records'))}${badge(bytes(data.sizeBytes))}</div><p class="archive-caption">Read from byte ${data.offset.toLocaleString()}. ${boundary} Row numbers below apply only to this page.</p>${archiveCoverage(result)}${omitted.length?`<div class="notice archive-omissions"><strong>Content omitted from this bounded read:</strong> ${esc(omitted.join('; '))}. This excerpt is not a complete copy of the file.</div>`:''}${records.length?`<div class="archive-log log-lines" tabindex="0" role="region" aria-label="Message archive records">${records.map((record,index)=>`<div class="log-line"><span class="line-number" aria-hidden="true">${index+1}</span><code>${esc(record.line)}</code></div>`).join('')}</div>`:empty('No readable records on this page',archiveNext(data)!==null?'This byte page contains no returned records. Use Next to continue.':'This bounded read returned no records. Review any omissions reported above.')}${archivePaging('content',browser.contentOffsets,data)}`;
      }
    }
    $('drawer-body').innerHTML=`<div class="archive-browser">${toolbar}${intro}<div aria-live="polite" aria-busy="${browser.busy}">${content}</div></div>`;
  }
  function messageArchiveAction(action,index) {
    const browser=state.messageArchives;if(!browser||state.drawer!=='message-archives')return;
    if(action==='archive-list-refresh')return loadMessageInventory([0]);
    if(action==='archive-back')return loadMessageInventory(browser.inventoryOffsets);
    if(browser.busy)return;
    if(action==='archive-file'&&browser.view==='inventory')return loadMessageArchive(browser.inventory?.data?.files?.[index]);
    const kind=browser.view==='file'?'content':'list',offsets=kind==='content'?browser.contentOffsets:browser.inventoryOffsets;
    const resource=kind==='content'?browser.content:browser.inventory;
    if(!good(resource)||resource.data?.state!=='ok')return;
    let nextOffsets;
    if(action===`archive-${kind}-previous`&&offsets.length>1)nextOffsets=offsets.slice(0,-1);
    if(action===`archive-${kind}-next`&&archiveNext(resource.data)!==null)nextOffsets=[...offsets,resource.data.nextOffset];
    if(nextOffsets)return kind==='content'?loadMessageArchive(browser.selected,nextOffsets):loadMessageInventory(nextOffsets);
  }
  function showLogQuery(kind='audit',row=null) {
    if(!['audit','journal'].includes(kind))return;
    openDrawer('log-query',kind==='audit'?'Search audit records':'Search journal records','BOUNDED LOG SEARCH',true);
    const files=resourceRows(state.sections.logs?.resources.find(resource=>resource.key==='journal_files')?.data)||[];
    const selected=row?valueAt(row,['Name']):'';
    const filterFields=kind==='audit'?`<div class="form-grid">${formField('audit-begin','Begin time',{type:'datetime-local',required:false,help:'Use the timestamp convention of this IRIS instance.'})}${formField('audit-end','End time',{type:'datetime-local',required:false})}</div><div class="form-grid">${formField('audit-user','Username',{required:false,placeholder:'Optional exact username'})}${formField('audit-event','Event name',{required:false,value:row?valueAt(row,['EventName'])||'':'',placeholder:'Optional event'})}</div>`:`<div class="form-field"><label class="form-label" for="journal-file">Journal file</label><select id="journal-file" class="select-field" required><option value="">Select a file from this snapshot…</option>${files.map(file=>`<option value="${esc(file.Name)}" ${String(file.Name)===String(selected)?'selected':''}>${esc(file.Name)}</option>`).join('')}</select><p class="field-help">Uses the exact name returned by the journal file list.</p></div>`;
    $('drawer-body').innerHTML=`<p class="drawer-intro">Search the instance's ${kind} records. Results are bounded to 100 rows and include permitted metadata only.</p><form id="log-query-form">${filterFields}<div class="form-field compact-field"><label class="form-label" for="log-limit">Maximum records</label><input id="log-limit" class="text-input" type="number" min="1" max="100" value="50" required></div><div id="form-error" class="notice error" hidden role="alert"></div><div class="review-controls"><button class="button button-primary" id="submit-log-query" type="submit">Search records</button></div></form><div id="log-query-results" style="margin-top:24px" aria-live="polite"></div>`;
    $('log-query-form').addEventListener('submit',event=>{
      event.preventDefault();if(!event.target.reportValidity())return;
      const stamp=value=>value?value.replace('T',' ')+(value.length===16?':00':''):'';
      const limit=Number($('log-limit').value);
      const filters=kind==='audit'?{begin:stamp($('audit-begin').value),end:stamp($('audit-end').value),username:$('audit-user').value.trim(),event:$('audit-event').value.trim(),limit}:{file:$('journal-file').value,limit};
      runLogQuery({kind,filters});
    });
  }
  async function runLogQuery(payload) {
    if(state.logQueryBusy)return;state.logQueryBusy=true;$('submit-log-query').disabled=true;$('log-query-results').innerHTML=loading('Searching permitted log records…');
    try {
      const result=await api('/api/log-query',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state.status?.csrf_token||''},body:JSON.stringify(payload)});
      if(state.drawer!=='log-query')return;
      state.logQueryResult=result;
      const rows=resourceRows(result.data)||[];
      const completed=result.query_state==='complete';
      const refresh=result.query_id&&result.query_state==='pending'?`<button class="button button-small" data-action="refresh-log-query">Refresh search result</button>`:'';
      $('log-query-results').innerHTML=`<div class="detail-meta">${sourceBadge(result)}${badge(result.query_state||'Result')}${completed?badge(rows.length+' returned rows'):''}${refresh}</div>${result.message?`<p class="drawer-intro">${esc(result.message)}</p>`:''}${Array.isArray(result.limitations)&&result.limitations.length?`<ul class="coverage-notes">${result.limitations.map(note=>`<li>${esc(note)}</li>`).join('')}</ul>`:''}${result.query_state==='pending'?'<p class="drawer-intro">The instance is still processing this bounded search. Refresh its result explicitly; no automatic repeat search is started.</p>':completed&&hasData(result)?`<div class="drawer-toolbar"><label class="search-field">${svg('search')}<input id="log-result-search" type="search" placeholder="Filter returned metadata…" aria-label="Filter log record results"></label></div><div id="log-result-records">${logRecordCards(rows)}</div>`:`<p class="drawer-intro">${esc(result.error?.message||'This search has not returned a completed result.')}</p>`}`;
      $('log-result-search')?.addEventListener('input',event=>{$('log-result-records').innerHTML=logRecordCards(rows.filter(row=>rowMatches(row,event.target.value.toLowerCase())));});
    }catch(error){if(state.drawer==='log-query')$('log-query-results').innerHTML=empty('Log search unavailable',error.message,'warning');}
    finally{state.logQueryBusy=false;if($('submit-log-query'))$('submit-log-query').disabled=false;}
  }
  function logRecordCards(rows) {
    return rows.length?`<div class="log-record-cards">${rows.map((row,index)=>`<details class="log-record-card" ${index===0?'open':''}><summary><strong>${esc(valueAt(row,['Event','EventName','Type','Action','Operation'])||'Record '+(index+1))}</strong><span>${esc(valueAt(row,['TimeStamp','UTCTimeStamp','Timestamp','DateTime','Offset','Address','Index'])||'')}</span></summary>${detailFields(row)}</details>`).join('')}</div>`:empty('No records returned','This bounded result contains no matching metadata.');
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
  function rowTarget(row) {
    if(state.section==='web'&&currentResource()?.path?.match(/\/web-apps(?:\?|$)/)){const name=valueAt(row,['Name']);return currentSection()?.targets?.find(target=>target.type==='web_app'&&String(target.name)===String(name))||null;}
    if(state.section!=='tasks'||!currentResource()?.path?.match(/\/tasks(?:\?|$)/))return null;
    const id=valueAt(row,['ID','TaskID']);return currentSection()?.targets?.find(target=>target.type==='task'&&String(target.id)===String(id))||null;
  }
  function showDetails(data,title='Response details',target=null) {
    state.drawerData=data;openDrawer('details',title,'RECORD INSPECTOR');
    const resource=currentResource();
    const actions=target?(target.actions||[]).map(id=>(state.status?.capabilities?.actions||[]).find(action=>action.id===id)).filter(Boolean):[];
    $('drawer-body').innerHTML=`<p class="drawer-intro">${esc(resource?.label||'Live response')} · Search field names and values, including nested objects.</p>${actions.length?`<div class="action-list">${actions.map(action=>`<button class="button button-small" data-action="review-command" data-command="${esc(action.id)}" data-target="${esc(target.type==='web_app'?target.name:target.id)}" ${!action.enabled?'disabled':''} title="${esc(action.enabled?'Review before executing':action.reason||'Not enabled by the server')}">${esc(action.id==='web.set_enabled'?(target.enabled?'Disable application':'Enable application'):action.label)}</button>`).join('')}</div><p class="explorer-meta">${state.review?'Review mode is enabled in this browser.':'Commands require enabling review mode; opening a review does not execute a command.'}</p>`:''}<div class="drawer-toolbar"><label class="search-field">${svg('search')}<input id="detail-search" type="search" placeholder="Find a field or value…" aria-label="Search details"></label></div><div id="detail-fields">${detailFields(data)}</div>`;
    $('detail-search').addEventListener('input',event=>{$('detail-fields').innerHTML=detailFields(state.drawerData,event.target.value);});
  }
  function toggleReview() {state.review=!state.review;const button=$('review-toggle');button.setAttribute('aria-pressed',String(state.review));button.innerHTML=`${svg(state.review?'shield':'lock')}<span>${state.review?'Command review enabled':'Read-only mode'}</span>`;toast(state.review?'Command review enabled. Each command still needs a separate confirmation.':'Read-only mode restored.');}
  function showReview(actionId,targetId) {
    const action=state.status?.capabilities?.actions?.find(item=>item.id===actionId);
    const isWeb=actionId==='web.set_enabled';
    const target=state.sections[isWeb?'web':'tasks']?.targets?.find(item=>String(isWeb?item.name:item.id)===String(targetId));
    if(!action||!action.enabled||!target){toast('This command is not available for this target.');return;}
    const label=isWeb?(target.enabled?'Disable application':'Enable application'):action.label;
    const identity=isWeb?target.name:target.id;
    openDrawer('review',label,'REVIEW MANAGEMENT COMMAND');
    state.pendingAction={action,target};
    const isRun=action.id==='task.run';
    const changeDescription=isWeb?`${target.enabled?'Disable':'Enable'} this application. Other configuration fields are preserved. ${target.enabled?'Disabling may interrupt requests to this application.':'Enabling makes the application available under its existing authentication settings.'}`:action.id==='task.suspend'?'Suspend this task while leaving queued work in the queue.':'Resume this task through the task manager.';
    $('drawer-body').innerHTML=`<p class="drawer-intro">Review the exact ${isWeb?'application':'task'} and operation before sending a management request to IRIS.</p><div class="drawer-block"><span class="context-label">Target ${isWeb?'application':'task'}</span><div class="review-target">${esc(target.name||'Task '+target.id)}</div><div class="detail-meta">${isWeb?badge(target.enabled?'Enabled → Disabled':'Disabled → Enabled','warning'):badge('Task ID '+target.id)}${badge(action.id)}</div><p>${isWeb?'The server checks the current enabled state before writing and reads it back afterward. Another administrator could still change configuration concurrently.':'The server rechecks the task and allowed operation before execution.'}</p></div>${isRun?'<div class="notice">Running a task may change data or invoke external work. Starting a task cannot undo those effects. The application will not retry this command automatically.</div>':`<div class="drawer-block"><h3>What changes</h3><p>${esc(changeDescription)}</p><p>A successful response will be followed by a fresh status check.</p></div>`}${!state.review?'<div class="notice">This browser is in read-only mode. Enable command review before confirming.</div><button class="button" data-action="enable-review">Enable command review</button>':''}<label class="check-row"><input type="checkbox" id="review-confirm" ${!state.review?'disabled':''}><span>I reviewed <strong>${esc(identity)}</strong> and want to ${esc(label.toLowerCase())}${isRun?', including any effects of its execution':''}.</span></label><div class="review-controls"><button class="button" data-action="close-drawer">Cancel</button><button class="button ${isRun?'button-danger':'button-primary'}" id="execute-command" data-action="execute-command" disabled>${esc(label)}</button></div><div id="action-result" style="margin-top:20px" aria-live="polite"></div>`;
    $('review-confirm').addEventListener('change',event=>{$('execute-command').disabled=!event.target.checked||!state.review;});
  }
  async function executeCommand() {
    if(state.busy||!state.review||!$('review-confirm')?.checked||!state.pendingAction)return;
    const {action,target}=state.pendingAction;state.busy=true;$('execute-command').disabled=true;$('review-confirm').disabled=true;
    $('action-result').innerHTML=loading('Sending the reviewed command…');
    try {
      const payloadTarget=target.type==='web_app'?{name:target.name,enabled:!target.enabled,expected_enabled:target.enabled}:{id:Number(target.id)};
      const result=await api('/api/action',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state.status?.csrf_token||''},body:JSON.stringify({action:action.id,target:payloadTarget,reviewed:true})});
      $('action-result').innerHTML=`<div class="result-panel${result.ok?'':' error'}"><strong>${result.ok?'Command accepted':'Command not completed'}</strong><br>${esc(result.message||result.state||'Review the returned state.')}</div>${commandVerification(result,target)}`;
      if(result.ok){try{await loadSection(target.type==='web_app'?'web':'tasks',true);}catch(_){/* action response remains visible */}}
    } catch(error) {$('action-result').innerHTML=`<div class="result-panel error"><strong>Execution result needs attention</strong><br>${esc(error.message)}<br>No retry was attempted. Refresh task status before deciding whether to send another command.</div>`;}
    finally{state.busy=false;}
  }
  function commandVerification(result,target) {
    const isWeb=target.type==='web_app';const verification=result.verification;
    const data=verification?.data;
    const selected=Array.isArray(data)?data.find(row=>isWeb?String(valueAt(row,['Name']))===String(target.name):String(valueAt(row,['ID','TaskID']))===String(target.id)):data;
    const field=isWeb?'Enabled':'Suspended';const before=valueAt(result.before,[field]);
    const after=good(verification)?valueAt(selected,[field]):undefined;
    const showValue=value=>typeof value==='boolean'?(value?'Yes':'No'):value===undefined||value===null?'Not verified':textValue(value);
    const compactVerification=verification?{...verification,data:selected??null}:null;
    const metadata={action:result.action,target:result.target,state:result.state,upstream:result.upstream,verification:compactVerification};
    return `<h3 class="triage-heading">Selected target · ${esc(isWeb?target.name:'Task '+target.id)}</h3><div class="verification-comparison"><div><span class="context-label">Before · ${field.toLowerCase()}</span><strong>${esc(showValue(before))}</strong></div><span class="verification-arrow" aria-hidden="true">→</span><div><span class="context-label">After readback · ${field.toLowerCase()}</span><strong>${esc(showValue(after))}</strong></div></div>${isWeb&&typeof selected?.other_fields_unchanged==='boolean'?`<p class="explorer-meta">Other configuration fields: ${selected.other_fields_unchanged?'unchanged in readback':'preservation not confirmed'}.</p>`:''}<details class="verification-metadata"><summary>Response metadata</summary>${detailFields(metadata)}</details>`;
  }
  async function showExplorer() {
    openDrawer('explorer','REST explorer','MANAGEMENT API REFERENCE',true);$('drawer-body').innerHTML=loading('Loading the pinned API reference…');
    try {if(!state.explorer)state.explorer=await api('/api/explorer');if(state.drawer!=='explorer')return;
      const source=state.explorer.source||{};
      $('drawer-body').innerHTML=`<p class="drawer-intro">Explore management operations and inspect available live reads. Reference entries do not imply that this instance supports them.</p><div class="explorer-meta">Specification ${esc(String(source.commit||'').slice(0,10))}${source.repository&&/^https:\/\/github\.com\//.test(source.repository)?` · <a href="${esc(source.repository)}" target="_blank" rel="noopener noreferrer">View source ↗</a>`:''}</div><div class="drawer-toolbar"><label class="search-field">${svg('search')}<input id="explorer-search" type="search" placeholder="Search paths, methods or descriptions…" aria-label="Search API operations"></label></div><div id="explorer-results"></div>`;
      renderExplorer('');$('explorer-search').addEventListener('input',event=>renderExplorer(event.target.value));
    } catch(error){if(state.drawer==='explorer')$('drawer-body').innerHTML=empty('Reference unavailable',error.message,'warning');}
  }
  function renderExplorer(query) {
    const items=state.explorer?.items||[];const needle=query.toLowerCase();const filtered=items.map((item,index)=>({item,index})).filter(({item})=>`${item.method} ${item.path} ${item.summary} ${item.section}`.toLowerCase().includes(needle));
    $('explorer-results').innerHTML=`<p class="explorer-meta">${filtered.length} operations${filtered.length>150?' · Showing the first 150; narrow your search':''}</p><div class="explorer-list">${filtered.slice(0,150).map(({item,index})=>`<button class="explorer-item" data-action="explorer-item" data-index="${index}"><span class="explorer-item-head"><span class="method">${esc(item.method)}</span><span class="explorer-path">${esc(item.path)}</span>${badge(item.enabled?'Available read':'Reference',item.enabled?'ok':'neutral')}</span><p>${esc(item.summary||areas[item.section]?.label||'Management operation')}</p></button>`).join('')}</div>`;
  }
  async function inspectOperation(index) {
    const item=state.explorer?.items?.[index];if(!item)return;
    openDrawer('operation',item.summary||'API operation',`${item.method} ${item.path}`,true);state.selectedOperation=item;
    $('drawer-body').innerHTML=`<button class="text-link" data-action="explorer">← All operations</button><p class="drawer-intro" style="margin-top:20px">${esc(item.path)}</p><div class="detail-meta"><span class="method">${esc(item.method)}</span>${badge(item.enabled?'Available read':'Reference only',item.enabled?'ok':'neutral')}</div>${detailFields({summary:item.summary,privilege:item.privilege,parameters:item.parameters})}<div style="margin-top:20px">${item.method==='GET'&&item.enabled&&areas[item.section]?'<button class="button button-primary" data-action="explorer-load">Load live response</button>':'<p class="drawer-intro">This operation is reference-only in this workspace. It cannot be executed here.</p>'}</div><div id="explorer-live" style="margin-top:20px"></div>`;
  }
  async function loadExplorerResponse() {
    const item=state.selectedOperation;if(!item)return;$('explorer-live').innerHTML=loading('Requesting the mapped live source…');
    try{const section=await loadSection(item.section,true);if(state.drawer!=='operation')return;const path=item.path.split('?')[0].replace(/^\/api\/admin/,'');const resource=section.resources.find(resource=>resource.path?.split('?')[0].replace(/^\/api\/admin/,'')===path);$('explorer-live').innerHTML=resource?`${sourceBadge(resource)}${good(resource)?detailFields(resource.data):`<p class="drawer-intro">${esc(resource.error?.message||'This endpoint is unavailable on the connected instance.')}</p>`}`:empty('No mapped live source','This operation requires parameters or a read integration that is not available in this workspace.');}catch(error){if(state.drawer==='operation')$('explorer-live').innerHTML=empty('Live request unavailable',error.message,'warning');}
  }
  function findResources(section,expression) {return (section?.resources||[]).filter(resource=>expression.test(`${resource.key} ${resource.path}`));}
  async function showTriage() {
    openDrawer('triage','Task / process triage','INCIDENT WORKSPACE',true);$('drawer-body').innerHTML=loading('Loading task history and the current process snapshot…');
    const results=await Promise.allSettled([loadSection('tasks',true),loadSection('system',true)]);if(state.drawer!=='triage')return;
    const tasks=results[0].status==='fulfilled'?results[0].value:null;const system=results[1].status==='fulfilled'?results[1].value:null;
    const taskResource=findResources(tasks,/\/tasks(?:\?|$)/)[0];const historyResources=findResources(tasks,/history/);const processResources=findResources(system,/processes/);
    const taskRows=good(taskResource)?resourceRows(taskResource.data)||[]:[];
    state.triage={taskRows,history:historyResources.filter(good).flatMap(resource=>resourceRows(resource.data)||[]),processes:processResources.filter(good).flatMap(resource=>resourceRows(resource.data)||[]),historyReady:historyResources.some(good),processReady:processResources.some(good)};
    $('drawer-body').innerHTML=`<p class="drawer-intro">Choose a task to put its recorded activity beside the current process list. This view correlates identifiers; it does not infer a task's health.</p><label class="form-label" for="triage-task">Task to investigate</label><select class="select-field" id="triage-task"><option value="">Select a task…</option>${taskRows.map((row,index)=>`<option value="${index}">${esc(valueAt(row,['Name','TaskName'])||'Task')} · ID ${esc(valueAt(row,['ID','TaskID'])??'not supplied')}</option>`).join('')}</select>${!taskRows.length?'<div class="notice">No task records are available in the current response. Refresh the Task manager to inspect source availability.</div>':''}<div class="detail-meta">${badge(`${state.triage.history.length} history records`,state.triage.historyReady?'ok':'warning')}${badge(`${state.triage.processes.length} current processes`,state.triage.processReady?'ok':'warning')}</div><div id="triage-results"></div>`;
    $('triage-task').addEventListener('change',event=>renderTriage(event.target.value));
  }
  function renderTriage(index) {
    if(index===''){$('triage-results').innerHTML='';return;}
    const triage=state.triage;const task=triage.taskRows[Number(index)];const id=valueAt(task,['ID','TaskID']);
    const history=triage.history.filter(row=>String(valueAt(row,['TaskID','Task','ID']))===String(id));
    const pids=[...new Set(history.map(row=>valueAt(row,['PID','ProcessID','JobNumber'])).filter(value=>value!==undefined&&value!==null&&String(value)!=='0'))];
    const processes=triage.processes.filter(row=>pids.some(pid=>String(pid)===String(valueAt(row,['PID','ProcessID','ID']))));
    const summary=flatten(task).filter(field=>['id','name','taskname','type','status','state','suspended','nextrun','lastrun','namespace'].includes(normalize(field.path)));
    $('triage-results').innerHTML=`<div class="drawer-block"><h3>Selected task</h3>${detailFields(Object.fromEntries(summary.map(field=>[field.path,field.value])))}</div><h3 class="triage-heading">Recorded activity ${badge(history.length)}</h3>${!triage.historyReady?'<p class="drawer-intro">Task history could not be loaded. No execution conclusion is available.</p>':!history.length?'<p class="drawer-intro">No matching task history exists in this snapshot. This is not evidence that the task has never run.</p>':history.slice(0,25).map(row=>`<div class="triage-card"><div class="triage-card-header"><span>Task ${esc(id)}</span>${badge('PID '+(valueAt(row,['PID','ProcessID','JobNumber'])??'not supplied'))}</div>${detailFields(row)}</div>`).join('')}${history.length>25?'<p class="explorer-meta">Showing the first 25 matching history records.</p>':''}${pids.length?`<div class="pid-caveat"><strong>Correlation, not proof.</strong> A PID can be reused after a process exits. A current process with the same PID is not necessarily the historical activity. Compare the recorded times and process details before drawing a conclusion.</div><h3 class="triage-heading">Current processes with matching PIDs ${badge(processes.length)}</h3>${!triage.processReady?'<p class="drawer-intro">The current process source is unavailable.</p>':processes.length?processes.map(row=>`<div class="triage-card">${detailFields(row)}</div>`).join(''):'<p class="drawer-intro">No current process matches the recorded PIDs in this snapshot. Completed tasks may have no active process.</p>'}`:''}`;
  }
  async function refresh() {
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
    if(action==='row'){const row=resourceRows(currentResource()?.data)?.[Number(button.dataset.index)];if(row){if(state.section==='logs'&&currentResource()?.key==='journal_files')return showLogQuery('journal',row);if(state.section==='logs'&&currentResource()?.key==='audit_events')return showLogQuery('audit',row);const descriptor=inspectDescriptor(row);if(descriptor)return openInspection(descriptor.kind,descriptor.name,descriptor.context);showDetails(row,textValue(valueAt(row,['Name','TaskName','ID','PID','Record'])||'Record details'),rowTarget(row));}return;}
    if(action==='inspect'){if(currentResource())showDetails(currentResource().data,currentResource().label||'Source response');return;}
    if(action==='sort'){state.sort={key:button.dataset.key,direction:state.sort?.key===button.dataset.key?-state.sort.direction:1};renderResource();return;}
    if(action==='previous-page'){state.page=Math.max(0,state.page-1);renderResource();return;}
    if(action==='next-page'){state.page++;renderResource();return;}
    if(action==='close-drawer')return closeDrawer();
    if(action==='toggle-review')return toggleReview();
    if(action==='enable-review'){toggleReview();showReview(state.pendingAction.action.id,state.pendingAction.target.type==='web_app'?state.pendingAction.target.name:state.pendingAction.target.id);return;}
    if(action==='review-command')return showReview(button.dataset.command,button.dataset.target);
    if(action==='execute-command')return executeCommand();
    if(action==='inspect-linked')return openInspection(button.dataset.kind,button.dataset.name,button.dataset.context||'');
    if(action==='create-resource')return showCreateResource();
    if(action==='edit-role')return showRoleEditor();
    if(action==='add-grant'){if(($('grant-editor')?.children.length||0)>=(state.roleResourceLimit||40)){toast(`This editor accepts at most ${state.roleResourceLimit||40} resource grants.`);return;}$('grant-editor')?.insertAdjacentHTML('beforeend',grantEditorRow());return;}
    if(action==='remove-grant'){button.closest('.grant-editor-row')?.remove();return;}
    if(action==='create-collection')return showCreateCollection();
    if(action==='create-secret')return showSecretForm();
    if(action==='edit-secret')return showSecretForm(Number(button.dataset.index));
    if(action==='delete-secret')return showDeleteSecret(Number(button.dataset.index));
    if(action==='enable-form-review'){toggleReview();renderFormReview();return;}
    if(action==='execute-form-command')return executeFormCommand();
    if(action==='oauth-client')return showOAuthClientPrompt();
    if(action==='message-archives')return showMessageArchives();
    if(action.startsWith('archive-'))return messageArchiveAction(action,Number(button.dataset.index));
    if(action==='log-query')return showLogQuery(button.dataset.kind);
    if(action==='refresh-log-query'&&state.logQueryResult?.query_id)return runLogQuery({kind:'result',filters:{id:state.logQueryResult.query_id}});
    if(action==='explorer')return showExplorer();
    if(action==='explorer-item')return inspectOperation(Number(button.dataset.index));
    if(action==='explorer-load')return loadExplorerResponse();
    if(action==='triage')return showTriage();
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
