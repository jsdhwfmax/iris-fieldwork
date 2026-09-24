# Package-manager installation

The `0.2.0` package candidate includes the actual Python gateway, browser assets,
Embedded Python telemetry module and ObjectScript REST adapter. It is separate
from the synthetic browser preview. Registry publication and contest bonus
approval are not established by the presence of `module.xml`.

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

## Load the source candidate

Clone this repository onto the IRIS host. In the `USER` IRIS terminal:

```objectscript
zpm "load /absolute/path/to/iris-fieldwork -v"
```

The installer prints the absolute path to `tools/start_installed.py`. It installs
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

The registry command `zpm "install iris-fieldwork"` must be verified after
publication before it is advertised as available. A local load or archive alone
does not establish community-registry availability or an awarded contest bonus.

Updates must be performed with the gateway stopped. If an update changes the
Embedded Python telemetry module, restart the IRIS instance during a planned
maintenance window so long-lived workers do not retain the previous import.
