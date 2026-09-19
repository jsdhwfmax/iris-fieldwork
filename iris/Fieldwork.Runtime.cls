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

ClassMethod Collect(kind As %String) As %String [ Language = python ]
{
    import sys
    if '/opt/fieldwork' not in sys.path:
        sys.path.insert(0, '/opt/fieldwork')
    import fieldwork_runtime
    if kind == 'metrics':
        return fieldwork_runtime.metrics()
    if kind == 'logs':
        return fieldwork_runtime.logs()
    raise ValueError('Unknown collection')
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
