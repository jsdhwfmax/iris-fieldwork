Class Fieldwork.Runtime Extends %CSP.REST
{
Parameter UseSession As INTEGER = 0;
Parameter CHARSET = "utf-8";

XData UrlMap
{
<Routes>
  <Route Url="/metrics" Method="GET" Call="Metrics"/>
  <Route Url="/logs" Method="GET" Call="Logs"/>
  <Route Url="/task-states" Method="GET" Call="TaskStates"/>
  <Route Url="/message-archives" Method="GET" Call="MessageArchives"/>
  <Route Url="/message-archive" Method="GET" Call="MessageArchive"/>
</Routes>
}

ClassMethod Metrics() As %Status
{
    If '$SYSTEM.Security.Check("%Admin_Operate","U") {
        Set %response.Status="403 Forbidden"
        Quit 1
    }
    Set %response.ContentType="application/json"
    Write ..Collect("metrics")
    Quit 1
}

ClassMethod Logs() As %Status
{
    If '$SYSTEM.Security.Check("%Admin_Operate","U") {
        Set %response.Status="403 Forbidden"
        Quit 1
    }
    Set %response.ContentType="application/json"
    Write ..Collect("logs")
    Quit 1
}

ClassMethod MessageArchives() As %Status
{
    Quit ..ArchiveReply("inventory")
}

ClassMethod MessageArchive() As %Status
{
    Quit ..ArchiveReply("read")
}

ClassMethod ArchiveReply(kind As %String) As %Status
{
    If '$SYSTEM.Security.Check("%Admin_Operate","U") {
        Set %response.Status="403 Forbidden"
        Quit 1
    }
    Set valid=1,key="",name="",revision="",offset="0"
    For {
        Set key=$Order(%request.Data(key))
        Quit:key=""
        If (key'="offset")&&((kind="inventory")||((key'="name")&&(key'="revision"))) Set valid=0
        If '$Data(%request.Data(key,1)) Set valid=0
        If $Order(%request.Data(key,1))'="" Set valid=0
    }
    If $Data(%request.Data("offset",1)) Set offset=%request.Data("offset",1)
    If $Data(%request.Data("name",1)) Set name=%request.Data("name",1)
    If $Data(%request.Data("revision",1)) Set revision=%request.Data("revision",1)
    Set %response.ContentType="application/json"
    Write ..CollectArchives(kind,name,revision,offset,valid)
    Quit 1
}

ClassMethod CollectArchives(kind As %String, name As %String, revision As %String, offset As %String, valid As %Integer) As %String [ Language = python ]
{
    import iris
    import sys
    python_path = iris.cls('Fieldwork.Runtime').PythonPath()
    if python_path not in sys.path:
        sys.path.insert(0, python_path)
    import message_archives
    return message_archives.collect(kind, name, revision, offset, bool(valid))
}

ClassMethod Collect(kind As %String) As %String [ Language = python ]
{
    import iris
    import sys
    python_path = iris.cls('Fieldwork.Runtime').PythonPath()
    if python_path not in sys.path:
        sys.path.insert(0, python_path)
    import fieldwork_runtime
    if kind == 'metrics':
        return fieldwork_runtime.metrics()
    if kind == 'logs':
        return fieldwork_runtime.logs()
    raise ValueError('Unknown collection')
}

/// IPM records its owned installation path; the Docker image retains its path.
ClassMethod PythonPath() As %String
{
    Quit $Get(^FieldworkPackage("pythonPath"),"/opt/fieldwork")
}

/// Cross-check state directly against task objects. The shipped v2 task list
/// was observed to return Suspended=false after a successful suspension.
ClassMethod TaskStates() As %Status
{
    If '$SYSTEM.Security.Check("%Admin_Operate","U") {
        Set %response.Status="403 Forbidden"
        Quit 1
    }
    Set %response.ContentType="application/json"
    Set rows=##class(%DynamicArray).%New()
    Set rs=##class(%SQL.Statement).%ExecDirect(,"SELECT TOP 100 ID FROM %SYS.Task ORDER BY ID")
    While rs.%Next() {
        Set task=##class(%SYS.Task).%OpenId(rs.ID)
        If $IsObject(task) {
            Set row=##class(%DynamicObject).%New()
            Set row.Id=+rs.ID,row.Name=task.Name,row.Namespace=task.NameSpace,row.TaskClass=task.TaskClass
            Do row.%Set("Suspended",+task.Suspended,"boolean")
            Set row.TimePeriod=+task.TimePeriod
            Do rows.%Push(row)
        }
    }
    Set answer={"status":{"errors":[]},"console":[]}
    Set answer.result=rows
    Write answer.%ToJSON()
    Quit 1
}
}
