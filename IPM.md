# Package-manager installation

The published `0.2.0` package includes the actual Python gateway, browser assets,
Embedded Python telemetry module and ObjectScript REST adapter. It is separate
from the synthetic browser preview. A clean consumer installed this version from
the public community registry on 24 September 2026; see
[registry verification](runtime/ipm-community-validation.json). No awarded
contest bonus or prize is claimed.

The current source is **0.3.0**, adding the [rotated message-log browser](ARCHIVES.md).
Its registry publication has not yet been verified. Use local source loading to
evaluate 0.3.0 until a new registry release is confirmed; the 0.2.0 evidence above
does not validate the new version.

## Requirements

- A disposable or deliberately selected Linux IRIS 2026.2 instance with IPM
  0.10.9 or later, installed in the `USER` namespace.
- Python 3.10 or later on the machine running the gateway; no Python packages
  beyond the standard library are required.
- An existing authorized IRIS account. The runtime adapter requires
  `%Admin_Operate:U`; other management operations retain their own privileges.
- A loopback IRIS web-gateway address. The Fieldwork gateway also listens only
  on loopback and has no visitor authentication; use it only on a trusted,
  single-user local environment. Do not publish either administrative port.

The package deliberately refuses to adopt an existing manually installed
`Fieldwork.Runtime` class or `/fieldwork/runtime` application. Use a separate
instance for evaluating this installation route. The existing Docker setup in
the README remains available and must not be overlaid with this package.

## Install the published package from the community registry

In the `USER` IRIS terminal, inspect the configured repositories:

```objectscript
zpm "repo -list"
```

The official IPM 0.10.9 XML client used in the clean test initially had no
repositories. For a fresh client in that state, initialize its community entry:

```objectscript
zpm "repo -r -n registry -reset-defaults"
```

This uses IPM's vendor defaults for `https://pm.community.intersystems.com`.
If repositories already exist, confirm the official community registry is
enabled rather than replacing a deliberately configured private entry.
The production endpoint is the domain root; the test registry's `/registry/`
path must not be copied onto the production domain.

Install the package by name:

```objectscript
zpm "install iris-fieldwork -v"
```

This command installed 0.2.0 with only the official community registry configured,
without a copied application source tree or a test/local repository.

## Load the 0.3.0 source

Clone this repository onto the IRIS host. In the `USER` IRIS terminal:

```objectscript
zpm "load /absolute/path/to/iris-fieldwork -v"
```

Use the current 0.3.0 checkout and stop the installed gateway before loading it.
The source package includes `iris/message_archives.py` alongside the existing
adapter and UI. The archive reader uses the fixed `/usr/irissys/mgr` directory
and supported Linux file-access primitives; it does not accept an alternative
log path. See [ARCHIVES.md](ARCHIVES.md) for format and read limits.

## Start the installed gateway

Either installation route prints the absolute path to `tools/start_installed.py`. It installs
the complete application beneath the IRIS manager directory's
`fieldwork-ipm/USER/` directory and creates a password-authenticated
`/fieldwork/runtime` application. It creates no accounts, credentials,
demonstration tasks, roles, resources or background gateway process.

Run the printed command in an operating-system terminal on that machine:

```sh
python3 /printed/installation/path/tools/start_installed.py
```

The terminal asks for an existing username and a hidden password. Credentials
remain in process memory. Alternatively, supply the existing
`IRIS_USERNAME`/`IRIS_PASSWORD` environment pair or `IRIS_BEARER_TOKEN`; mixed or
partial credentials are rejected. Avoid placing passwords in command history.

The default upstream address is `http://127.0.0.1:52773`; override it with
`--iris-url http://127.0.0.1:YOUR_PORT`. Open `http://127.0.0.1:8766` on the same
machine. Use `--port PORT` to choose a different local UI port. Ctrl+C stops the
gateway.

If IRIS runs in Docker, the printed path is inside that container. To run the
interface on the host, copy only the installed application directory out using
`docker cp CONTAINER:/printed/installation/path ./fieldwork-installed`, then run
`python3 ./fieldwork-installed/tools/start_installed.py --iris-url
http://127.0.0.1:YOUR_MAPPED_IRIS_PORT`. Keep the IRIS port mapping on loopback.
This directory contains application code, not credentials. Stop and remove or
replace a copied gateway explicitly when updating/uninstalling the container's
package; IPM cannot manage a copy made outside its installation directory.

## Update and uninstall

Stop every gateway process using the package before updating or uninstalling.
Keep your own files and credentials outside the package installation directory.
The installer checks ownership before changing its application or files and
refuses conflicting state instead of taking it over.

To remove the package from the `USER` IRIS terminal:

```objectscript
zpm "uninstall iris-fieldwork"
```

Package removal is intended to remove its own files, adapter classes,
configuration and web application. It does not undo administrative actions
previously performed through Fieldwork or alter the independent Docker setup.

Community-registry installation of **0.2.0** is verified for the platform and client above.
It does not establish suitability for a production environment or an awarded
contest bonus.

Updates must be performed with the gateway stopped. If an update changes the
Embedded Python telemetry or archive module, restart the IRIS instance during a planned
maintenance window so long-lived workers do not retain the previous import.
