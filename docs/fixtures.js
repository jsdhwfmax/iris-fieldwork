/* Manually authored synthetic examples. No records were exported from IRIS. */
(() => {
  'use strict';
  const resource=(key,label,path,data,extra={})=>({key,label,path,method:'GET',state:'ok',http_status:null,data,count:Array.isArray(data)?data.length:Object.keys(data).length,sample_limit:100,provenance:'Manually authored synthetic example; never requested from an API.',...extra});
  const taskHistory=[
    {TaskId:2001,Name:'Example daily summary',Namespace:'DEMO',Pid:8101,LastStart:'2026-09-01 09:00:00',Completed:'2026-09-01 09:00:02',Status:1,Result:'Synthetic success example',ErrNumber:0},
    {TaskId:2002,Name:'Example inventory check',Namespace:'DEMO',Pid:8102,LastStart:'2026-09-01 09:15:00',Completed:'2026-09-01 09:15:01',Status:0,Result:'Synthetic failure: example input unavailable',ErrNumber:100},
    {TaskId:2001,Name:'Example daily summary',Namespace:'DEMO',Pid:8001,LastStart:'2026-08-31 09:00:00',Completed:'2026-08-31 09:00:02',Status:1,Result:'Earlier synthetic success example',ErrNumber:0}
  ];
  const resources={
    web:[resource('web_apps','Web applications','/api/admin/v2/web-apps',[
      {Name:'/demo/catalog',Namespace:'DEMO',Enabled:true,Type:'REST',Resource:'DemoCatalog',AuthenticationMethods:['Password'],IsSystemApp:false,DispatchClass:'Demo.Catalog'},
      {Name:'/demo/reports',Namespace:'DEMO',Enabled:false,Type:'REST',Resource:'DemoReports',AuthenticationMethods:['Password'],IsSystemApp:false,DispatchClass:'Demo.Reports'},
      {Name:'/demo/status',Namespace:'DEMO',Enabled:true,Type:'REST',Resource:'DemoStatus',AuthenticationMethods:['Password'],IsSystemApp:false,DispatchClass:'Demo.Status'}
    ])],
    permissions:[
      resource('roles','Roles','/api/admin/v2/security/roles',[
        {Name:'DemoReader',Description:'Synthetic read-only role',EscalationOnly:false,GrantedRoles:[],Resources:[{Name:'DemoCatalog',Permissions:'R'}]},
        {Name:'DemoReporter',Description:'Synthetic report role',EscalationOnly:false,GrantedRoles:[],Resources:[{Name:'DemoReports',Permissions:'RU'}]},
        {Name:'DemoUnassigned',Description:'Synthetic role with no grants',EscalationOnly:false,GrantedRoles:[],Resources:[]}
      ]),
      resource('users','Users','/api/admin/v2/security/users',[
        {Name:'sample.reader',Enabled:true,Type:'User',Namespace:'DEMO',Roles:['DemoReader'],Description:'Invented account; cannot sign in'},
        {Name:'sample.reporter',Enabled:true,Type:'User',Namespace:'DEMO',Roles:['DemoReporter'],Description:'Invented account; cannot sign in'},
        {Name:'sample.inactive',Enabled:false,Type:'User',Namespace:'DEMO',Roles:[],Description:'Invented disabled account'}
      ]),
      resource('resources','Security resources','/api/admin/v2/security/resources',[
        {Name:'DemoCatalog',Description:'Synthetic catalog permission',PublicPermission:'',ResourceType:'Application',AllowDelete:true},
        {Name:'DemoReports',Description:'Synthetic report permission',PublicPermission:'',ResourceType:'Application',AllowDelete:true},
        {Name:'DemoStatus',Description:'Synthetic status permission',PublicPermission:'',ResourceType:'Application',AllowDelete:true}
      ])
    ],
    security:[
      resource('wallet_collections','Wallet collection metadata','/api/admin/v2/wallet/collections',[
        {Name:'DemoIntegrations',EditResource:'DemoWalletEdit',UseResource:'DemoWalletUse',ExampleSecrets:[{Name:'sample-service',Type:'%Wallet.KeyValue'}],Note:'Invented metadata only; no secret value exists.'},
        {Name:'DemoEmptyCollection',EditResource:'DemoWalletEdit',UseResource:'DemoWalletUse',ExampleSecrets:[],Note:'An intentionally empty synthetic collection.'}
      ]),
      resource('x509_credentials','X.509 metadata','/api/admin/v2/security/x509-credentials',[
        {Alias:'sample-client-certificate',HasPrivateKey:false,Description:'Invented alias; no certificate or key is included.'}
      ]),
      resource('ssl_configurations','TLS configuration examples','/api/admin/v2/security/ssl-configurations',[
        {Name:'DemoOutboundTLS',Enabled:true,Type:'Client',VerifyPeer:true,Description:'Illustrative settings only; no TLS connection is made.'}
      ]),
      resource('oauth_servers','OAuth server examples','/api/admin/v2/security/oauth2/client/server-definitions',[
        {ID:'demo-provider',ClientCount:1,ResourceCount:0,IssuerEndpoint:'https://identity.example.invalid',Description:'Reserved invalid domain; not a configured identity service.'}
      ]),
      resource('oauth_clients','OAuth client examples','/api/admin/v2/security/oauth2/server/clients',[])
    ],
    tasks:[
      resource('tasks','Scheduled task examples','/api/admin/v2/tasks',[
        {Id:2001,Name:'Example daily summary',Type:'User',Namespace:'DEMO',TaskClass:'Demo.Summary',Suspended:false,LastFinished:'2026-09-01 09:00:02',NextScheduled:'2026-09-02 09:00:00'},
        {Id:2002,Name:'Example inventory check',Type:'User',Namespace:'DEMO',TaskClass:'Demo.Inventory',Suspended:true,LastFinished:'2026-09-01 09:15:01',NextScheduled:null},
        {Id:2003,Name:'Example on-demand task',Type:'User',Namespace:'DEMO',TaskClass:'Demo.Manual',Suspended:false,LastFinished:null,NextScheduled:null}
      ]),
      resource('task_states','Task-state examples','/fieldwork/runtime/task-states',[
        {Id:2001,Name:'Example daily summary',Namespace:'DEMO',Suspended:false,Source:'Synthetic example; not a verification result'},
        {Id:2002,Name:'Example inventory check',Namespace:'DEMO',Suspended:true,Source:'Synthetic example; not a verification result'}
      ]),
      resource('task_manager','Task-manager example','/api/admin/v2/task/manager',{Status:'Illustrative only',Note:'No scheduler runs in this preview.'}),
      resource('upcoming','Upcoming task example','/api/admin/v2/task/upcoming',[{Id:2001,Name:'Example daily summary',Namespace:'DEMO',Datetime:'2026-09-02 09:00:00',Suspended:false}]),
      resource('task_history','Task activity examples','/api/admin/v2/task/history',taskHistory)
    ],
    system:[
      resource('runtime_metrics','Illustrative host metrics','/fieldwork/runtime/metrics',{
        sampledAt:'2026-09-01T10:00:00Z',scope:'Synthetic illustration of host/container metrics. Not observed or measured on any machine.',availability:[],cpuBusyPercent:18.4,cpuSampleMilliseconds:250,memoryTotalBytes:8589934592,memoryAvailableBytes:5368709120,irisDiskTotalBytes:107374182400,irisDiskAvailableBytes:75161927680,containerMemoryLimitBytes:2147483648,containerMemoryUsedBytes:805306368,containerCpuLimitCores:2
      }),
      resource('processes','Process examples','/api/admin/v2/processes',[
        {Pid:8101,Nspace:'DEMO',Routine:'Demo.Interactive',State:'Running',Commands:420,Globals:120,CPUTime:0.4,Started:'2026-09-01 09:30:00',Note:'Starts after task completion: same PID does not prove identity.'},
        {Pid:8200,Nspace:'DEMO',Routine:'Demo.Worker',State:'Idle',Commands:200,Globals:80,CPUTime:0.2,Started:'2026-09-01 09:45:00'},
        {Pid:8201,Nspace:'DEMO',Routine:'Demo.Report',State:'Running',Commands:600,Globals:240,CPUTime:0.7,Started:'2026-09-01 09:50:00'}
      ]),
      resource('devices','Device examples','/api/admin/v2/devices',[{Name:'sample-console',Type:'Terminal',SubType:'Illustrative',Alias:'DemoConsole'},{Name:'sample-output',Type:'File',SubType:'Illustrative',Alias:'DemoOutput'}]),
      resource('databases','Database examples','/api/admin/v2/database-dirs',[{Directory:'/example/iris/demo',Size:128,MaxSize:1024,Status:'Mounted',Resource:'DemoDatabase',Encrypted:false,Mirrored:false,Note:'Invented path; no host directory is exposed.'}]),
      resource('system_usage','Illustrative usage counters','/api/admin/v2/monitor/system-usage',{AllGlobalReferences:120000,GlobalUpdateReferences:4000,RoutineCalls:18000,BlockReads:200,BlockWrites:35,LastUpdate:'2026-09-01 10:00:00',Note:'Fixed authored counters, not an activity measurement.'}),
      resource('shared_memory','Illustrative memory values','/api/admin/v2/monitor/system-usage/shared-memory',{SMHAllocated:67108864,SMHAvailable:50331648,SMHUsed:16777216,Note:'Fixed authored values in bytes.'})
    ],
    logs:[
      resource('runtime_logs','Authored runtime log examples','/fieldwork/runtime/logs',[
        {source:'Example application log',scope:'Three authored lines; no file was read.',truncated:false,state:'ok',records:[{line:'2026-09-01 09:00:00 INFO Synthetic summary task started.'},{line:'2026-09-01 09:00:02 INFO Synthetic summary task completed.'},{line:'2026-09-01 09:15:01 WARN Synthetic inventory input unavailable.'}]},
        {source:'Example unavailable source',scope:'Illustrates a source with no included sample lines.',truncated:false,state:'unavailable',records:[]}
      ]),
      resource('task_history','Task activity examples','/api/admin/v2/task/history',taskHistory),
      resource('journal_files','Journal file examples','/api/admin/v2/journal/files',[{Name:'/example/journal/20260901.001',Size:1048576,CreationTime:'2026-09-01 00:00:00',DataSize:524288,Note:'Invented file. No journal query can be submitted.'}]),
      resource('audit_records','Bounded audit metadata examples','/api/admin/v2/security/audit/records',[
        {AuditIndex:1,TimeStamp:'2026-09-01 09:00:00',Username:'sample.reader',EventSource:'Demo',EventType:'Example access',Event:'Example allowed access',Namespace:'DEMO',Pid:8101},
        {AuditIndex:2,TimeStamp:'2026-09-01 09:15:00',Username:'sample.inactive',EventSource:'Demo',EventType:'Example access',Event:'Example denied access',Namespace:'DEMO',Pid:8102}
      ],{method:'POST',sample_limit:2}),
      resource('journal_records','Bounded journal metadata examples','/api/admin/v2/journal/file/records',[
        {Address:1000,TypeName:'SET',ProcessID:8101,TimeStamp:'2026-09-01 09:00:01'},
        {Address:1040,TypeName:'KILL',ProcessID:8102,TimeStamp:'2026-09-01 09:15:01'}
      ],{method:'POST',sample_limit:2})
    ]
  };
  const limits={
    web:'Enabled values are illustrative. Enabling, disabling and all other configuration writes are absent.',
    permissions:'Open a role to inspect example nested grants. No accounts, resources or permissions can be changed.',
    security:'Metadata is invented; no key, certificate, token or secret value is included. No credential-entry control exists.',
    tasks:'These tasks never run. Task triage illustrates why matching a historical PID is not proof of process identity.',
    system:'All counters, paths and utilization values are invented. The preview reads no machine or container information.',
    logs:'Only fixed sample lines and two-record metadata examples are included. Filtering is local; no audit/journal search or polling occurs.'
  };
  const responses={'/api/status':{app:'IRIS Fieldwork',mode:'synthetic_preview',connected:false,capabilities:{actions:[]}}};
  for(const [id,items] of Object.entries(resources))responses['/api/section/'+id]={section:id,resources:items,targets:[],actions:[],limitations:['Synthetic examples only. There is no IRIS backend connection.',limits[id]]};
  const operations=[
    {method:'GET',path:'/api/admin/v2/web-apps',summary:'List web application metadata in the local app.'},
    {method:'PUT',path:'/api/admin/v2/web-app',summary:'Reviewed enable/disable operation in the local app; unavailable here.'},
    {method:'GET',path:'/api/admin/v2/security/roles',summary:'List roles and inspect selected resource grants.'},
    {method:'GET',path:'/api/admin/v2/wallet/collections',summary:'List wallet collection metadata, never secret values.'},
    {method:'GET',path:'/api/admin/v2/tasks',summary:'Inspect task inventory and suspension state.'},
    {method:'GET',path:'/fieldwork/runtime/metrics',summary:'Local adapter host/container metrics; all preview values are invented.'},
    {method:'GET',path:'/api/admin/v2/processes',summary:'Inspect process metadata and correlate task history cautiously.'},
    {method:'POST',path:'/api/admin/v2/security/audit/records',summary:'Bounded asynchronous metadata search in the local app; unavailable here.'}
  ];
  const freeze=value=>{if(value&&typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value);}return value;};
  window.FIELDWORK_PREVIEW=freeze({responses,operations});
})();
