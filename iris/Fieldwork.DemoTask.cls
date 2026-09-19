/// Local demonstration only: on-demand task increments its own counter.
Class Fieldwork.DemoTask Extends %SYS.Task.Definition
{
Parameter TaskName = "Fieldwork demonstration";

Method OnTask() As %Status
{
    Set count=$Increment(^FieldworkDemo("runs"))
    Set ^FieldworkDemo("lastRun")=$ZTIMESTAMP
    Quit 1
}

ClassMethod Ensure() As %Status
{
    Set rs=##class(%SQL.Statement).%ExecDirect(,"SELECT ID FROM %SYS.Task WHERE NameSpace = ? AND TaskClass = ?","USER","Fieldwork.DemoTask")
    If rs.%Next() { Write "FIELDWORK_DEMO_TASK_ID=",rs.ID,! Quit 1 }
    Set task=##class(%SYS.Task).%New()
    Set task.Name="Fieldwork demonstration"
    Set task.Description="Local on-demand example; only increments the FieldworkDemo counter."
    Set task.NameSpace="USER"
    Set task.TaskClass="Fieldwork.DemoTask"
    Set task.RunAsUser="_SYSTEM"
    Set task.TimePeriod=5
    Set task.DailyFrequency=0
    Set sc=task.%Save()
    If $SYSTEM.Status.IsError(sc) { Quit sc }
    Write "FIELDWORK_DEMO_TASK_ID=",task.%Id(),!
    Quit 1
}
}
