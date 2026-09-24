/// IPM lifecycle for the complete local gateway; no demo data or account creation.
Class Fieldwork.Package Extends %RegisteredObject
{
Parameter Owner = "iris-fieldwork|USER|ipm-v1";
Parameter WebApp = "/fieldwork/runtime";

ClassMethod Failure(message As %String) As %Status
{
    Quit $SYSTEM.Status.Error(5001,message)
}

ClassMethod Root() As %String
{
    Quit ##class(%File).NormalizeDirectory("fieldwork-ipm/USER/",##class(%File).ManagerDirectory())
}

ClassMethod IsLinux() As %Boolean [ Language = python ]
{
    import platform
    return platform.system() == 'Linux'
}

/// Inspect before IPM reloads Fieldwork.Runtime or changes any application files.
ClassMethod Preflight() As %Status
{
    If $Namespace'="USER" { Quit ..Failure("This package supports the USER namespace only; no adapter was loaded.") }
    If '..IsLinux() { Quit ..Failure("This IPM package is supported on Linux only; use the documented host setup elsewhere.") }
    Set owned=($Get(^FieldworkPackage("owner"))=..#Owner)
    If $Data(^FieldworkPackage),'owned { Quit ..Failure("Unrecognized Fieldwork package state; refusing to overwrite it.") }
    If owned,$Get(^FieldworkPackage("root"))'=..Root() { Quit ..Failure("Fieldwork installation path does not match this instance.") }
    If 'owned,##class(%Dictionary.ClassDefinition).%ExistsId("Fieldwork.Runtime") {
        Quit ..Failure("An unmanaged Fieldwork.Runtime class already exists. Use a separate instance; this installer will not adopt or replace it.")
    }
    Set problem=..RootProblem(..Root(),owned)
    If problem'="" { Quit ..Failure(problem) }
    Quit ..CheckWebApp(owned)
}

/// Validate both the OS marker and IRIS ownership state. Symlinks are refused.
ClassMethod RootProblem(root As %String, owned As %Boolean) As %String [ Language = python ]
{
    from pathlib import Path
    import hashlib
    import json
    target = Path(root)
    try:
        if target.is_symlink() or target.parent.is_symlink():
            return 'Fieldwork installation directories must not be symbolic links.'
        if not target.exists():
            return ''
        if not target.is_dir() or not owned:
            return 'The Fieldwork installation path already exists without package ownership.'
        if any(p.is_symlink() for p in target.rglob('*')):
            return 'The owned Fieldwork directory contains a symbolic link; refusing to modify it.'
        marker = target / '.fieldwork-owner'
        if marker.read_text(encoding='utf-8') != 'iris-fieldwork|USER|ipm-v1\n':
            return 'The Fieldwork ownership marker does not match.'
        recorded = json.loads((target / '.fieldwork-files.json').read_text(encoding='utf-8'))
        if not isinstance(recorded, dict) or not isinstance(recorded.get('files'), dict) or not isinstance(recorded.get('directories'), list):
            return 'The Fieldwork installed-file manifest is invalid.'
        actual, directories = {}, []
        for path in target.rglob('*'):
            relative = path.relative_to(target).as_posix()
            if relative in ('.fieldwork-owner', '.fieldwork-files.json'):
                continue
            if '__pycache__' in path.relative_to(target).parts:
                if path.is_dir() or path.suffix == '.pyc':
                    continue
                return 'A non-cache file was added inside a Python cache directory; refusing cleanup.'
            if path.is_dir():
                directories.append(relative)
            elif path.is_file():
                actual[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            else:
                return 'The Fieldwork installation contains a non-regular file; refusing cleanup.'
        if actual != recorded['files'] or sorted(directories) != sorted(recorded['directories']):
            return 'Installed Fieldwork files were modified, removed or added. Preserve those changes separately before reinstalling or uninstalling.'
        return ''
    except (OSError, UnicodeError, ValueError, TypeError):
        return 'The Fieldwork ownership marker or directory could not be verified.'
}

ClassMethod CheckWebApp(owned As %Boolean) As %Status
{
    New $Namespace
    Set $Namespace="%SYS"
    If '##class(Security.Applications).Exists(..#WebApp) { Quit 1 }
    If 'owned { Quit ..Failure("An unmanaged /fieldwork/runtime application already exists; it will not be replaced.") }
    Set sc=##class(Security.Applications).Get(..#WebApp,.props)
    If $SYSTEM.Status.IsError(sc) { Quit sc }
    If ($Get(props("Description"))'=..#Owner)||($Get(props("NameSpace"))'="USER")||($Get(props("DispatchClass"))'="Fieldwork.Runtime") {
        Quit ..Failure("The runtime application no longer matches package ownership; refusing to change it.")
    }
    If ($Get(props("AutheEnabled"))'=32)||($Get(props("Resource"))'="%Admin_Operate") {
        Quit ..Failure("The runtime application's authentication was changed; refusing to overwrite or delete it.")
    }
    Quit 1
}

ClassMethod Install(sourceRoot As %String) As %Status
{
    // Preflight already protected the original adapter before Reload. Recheck
    // ownership and application configuration immediately before filesystem writes.
    If $Namespace'="USER" { Quit ..Failure("Fieldwork installation requires USER.") }
    Set root=..Root(),owned=($Get(^FieldworkPackage("owner"))=..#Owner)
    Set problem=..RootProblem(root,owned)
    If problem'="" { Quit ..Failure(problem) }
    Set sc=..CheckWebApp(owned)
    If $SYSTEM.Status.IsError(sc) { Quit sc }
    Set problem=..CopyFiles(sourceRoot,root)
    If problem'="" {
        // A fresh failed copy has no prior adapter to preserve: Preflight
        // explicitly checked that it did not exist before this Reload.
        // Remove only that newly loaded adapter so a clean retry is possible.
        If 'owned {
            Set cleanup=$SYSTEM.OBJ.Delete("Fieldwork.Runtime.cls","-d")
            If $SYSTEM.Status.IsError(cleanup) { Quit $SYSTEM.Status.AppendStatus(..Failure(problem),cleanup) }
        }
        Quit ..Failure(problem)
    }
    Set ^FieldworkPackage("owner")=..#Owner,^FieldworkPackage("root")=root
    Set ^FieldworkPackage("pythonPath")=root_"iris/"
    Set ^FieldworkPackage("version")="0.2.0"
    Set sc=..ConfigureWebApp()
    If $SYSTEM.Status.IsError(sc) { Quit sc }
    Write !,"Start IRIS Fieldwork on this machine:",!,"  python3 ",root,"tools/start_installed.py",!
    Write "The launcher prompts for an existing account or uses credentials supplied through environment variables.",!
    Write "Only 127.0.0.1 is served. Stop the gateway before package update or uninstall.",!
    Quit 1
}

ClassMethod CopyFiles(sourceRoot As %String, root As %String) As %String [ Language = python ]
{
    from pathlib import Path
    import hashlib
    import json
    import shutil
    import tempfile
    import uuid
    source, target = Path(sourceRoot), Path(root)
    required = ['app/backend.py', 'app/static/index.html', 'iris/fieldwork_runtime.py',
                'tools/start_installed.py', 'README.md', 'IPM.md', 'LICENSE', 'NOTICE.md']
    staging = None
    backup = None
    swapped = False
    try:
        if any(not (source / item).is_file() for item in required):
            return 'The package is incomplete; required gateway, UI or adapter files are missing.'
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix='.fieldwork-stage-', dir=target.parent))
        (staging / '.fieldwork-owner').write_text('iris-fieldwork|USER|ipm-v1\n', encoding='utf-8')
        app = staging / 'app'
        shutil.copytree(source / 'app', app, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'test_*.py'))
        for item in required[2:]:
            destination = staging / item
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / item, destination)
        files, directories = {}, []
        for path in staging.rglob('*'):
            relative = path.relative_to(staging).as_posix()
            if relative in ('.fieldwork-owner', '.fieldwork-files.json') or '__pycache__' in path.relative_to(staging).parts:
                continue
            if path.is_dir():
                directories.append(relative)
            elif path.is_file():
                files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        (staging / '.fieldwork-files.json').write_text(json.dumps({'files': files, 'directories': sorted(directories)}, sort_keys=True), encoding='utf-8')
        if target.exists():
            backup = target.parent / ('.fieldwork-backup-' + uuid.uuid4().hex)
            target.rename(backup)
        try:
            staging.rename(target)
            staging = None
            swapped = True
        except OSError:
            if backup is not None:
                backup.rename(target)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
        return ''
    except OSError:
        if swapped:
            return 'The replacement files are complete, but the previous package backup could not be removed; preserve it and inspect filesystem permissions.'
        return 'Package staging failed; the existing installation files were preserved. Check filesystem permissions before retrying.'
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
}

ClassMethod ConfigureWebApp() As %Status
{
    New $Namespace
    Set $Namespace="%SYS"
    Set props("NameSpace")="USER",props("DispatchClass")="Fieldwork.Runtime"
    Set props("AutheEnabled")=32,props("Enabled")=1
    Set props("Resource")="%Admin_Operate",props("Description")=..#Owner
    If ##class(Security.Applications).Exists(..#WebApp) { Quit ##class(Security.Applications).Modify(..#WebApp,.props) }
    Quit ##class(Security.Applications).Create(..#WebApp,.props)
}

/// Runs before IPM deletes its classes. Never removes an unowned application/path.
ClassMethod Uninstall() As %Status
{
    If $Namespace'="USER" { Quit ..Failure("Fieldwork uninstall requires USER.") }
    Set owned=($Get(^FieldworkPackage("owner"))=..#Owner)
    If 'owned { Quit ..Failure("Fieldwork ownership is absent; refusing automatic cleanup.") }
    If $Get(^FieldworkPackage("root"))'=..Root() { Quit ..Failure("Fieldwork installation path does not match this instance.") }
    Set problem=..RootProblem(..Root(),owned)
    If problem'="" { Quit ..Failure(problem) }
    Set sc=..CheckWebApp(owned)
    If $SYSTEM.Status.IsError(sc) { Quit sc }
    Set sc=..DeleteWebApp()
    If $SYSTEM.Status.IsError(sc) { Quit sc }
    Set problem=..RemoveFiles(..Root())
    If problem'="" { Quit ..Failure(problem) }
    Kill ^FieldworkPackage
    Quit 1
}

ClassMethod DeleteWebApp() As %Status
{
    New $Namespace
    Set $Namespace="%SYS"
    If ##class(Security.Applications).Exists(..#WebApp) { Quit ##class(Security.Applications).Delete(..#WebApp) }
    Quit 1
}

ClassMethod RemoveFiles(root As %String) As %String [ Language = python ]
{
    from pathlib import Path
    import shutil
    try:
        target = Path(root)
        if target.exists():
            shutil.rmtree(target)
        return ''
    except OSError:
        return 'The owned Fieldwork directory could not be removed. Stop the gateway and retry uninstall.'
}
}
