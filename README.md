# IRIS Fieldwork

A local operations workspace for InterSystems IRIS 2026.2. It brings web applications, permissions, wallet management, tasks, system telemetry and log searches into one interface. This is an original contest prototype under active development. InterSystems confirmed its approval for the [Build Your Own Management Portal contest](https://openexchange.intersystems.com/contest/48) on 21 September 2026; no award is claimed.

Version **0.2.0** is published on [InterSystems Open Exchange](https://openexchange.intersystems.com/package/IRIS-Fieldwork) and the public community IPM registry, confirmed on 24 September 2026. Three demonstration videos show the local prototype in action.

The browser talks to a Python gateway on loopback. IRIS credentials stay in the server process. Curated SysAdmin API calls supply instance data; an original Embedded Python/ObjectScript adapter adds Linux and container telemetry, bounded runtime logs and an independent task-state check.

## Current capabilities

| Area | Implemented | Current boundaries |
| --- | --- | --- |
| Web applications | Live inventory, reviewed enabled-state changes for eligible non-system apps, and a curated REST explorer | Other app configuration and automatic OpenAPI discovery are not exposed |
| Permissions | User, role and resource details; reviewed grants/revokes of existing application resources on eligible user roles | No system grants, inherited-role edits or user-account mutations; resource creation is disabled on the tested build |
| Security and secrets | Wallet collection creation; write-only KeyValue secret creation, replacement and removal; wallet, X.509, TLS and OAuth configuration inspection | Secret values are never fetched for display or verification; other secret types and X.509/TLS/OAuth writes are not exposed |
| Tasks | Inventory, activity/history, on-demand run, suspend/resume, selected-target verification and process correlation | Commands require verified user-task state; historical PID matches do not establish current identity |
| System | Processes, devices, databases, sampled Linux CPU/memory/disk and container limits | Process and device mutations are not exposed; host/kernel measurements can exceed container limits |
| Logs | Bounded runtime logs, task activity, and asynchronous audit/journal record metadata searches | Event payloads, session identifiers and journal global nodes/values are omitted; no complete log export or all-subsystem coverage claim |

Empty data is shown as empty. Unavailable endpoints and unsupported log sources remain visible. A matching PID in historical data is not proof that it is the same current process.

Role changes send only `Resources`, compare the reviewed grants with a fresh read, and verify both the new grants and unchanged role fields. Eligible roles have no inherited roles or escalation flag. Every referenced resource must appear as an `Application` resource in a fresh exact-name query. The resource editor can therefore use an exact name even when the general inventory's first 100 rows contain only system resources.

Wallet writes require a reviewed existing collection and its current edit/use resources. The supported secret configuration is `%Wallet.KeyValue` for HTTP use, with explicit allowed hosts and TLS required. Creation/replacement read back only name/type metadata; `accepted_metadata_verified` does **not** claim the stored value was verified. The app cannot recover a replaced or deleted secret. Supplied secret values are excluded from action responses.

Audit searches accept server-clock dates and single user/event filters; journal searches require an exact file from the current bounded inventory. Searches return at most 100 metadata rows. Pending searches are polled using a gateway-owned token, expire after ten minutes, and are never automatically resubmitted. A gateway holds at most 32 search tokens.

## Interactive preview

The [browser preview source](docs/) runs without installing IRIS. From this repository, run `python -m http.server 8771 --bind 127.0.0.1 --directory docs` and open `http://127.0.0.1:8771`. It uses deliberately synthetic fixtures for the six areas, with local filtering, sorting and record inspection. It has no IRIS connection, administrative commands or secret entry. Its values are examples, not measurements from the tested instance.

The preview helps explain the interface; the local installation and recorded demonstrations below show the actual IRIS integration. The static preview is maintained separately in `docs/` and does not change the local gateway. No online-demo bonus is claimed as awarded.

## Local installation

The complete **0.2.0 IPM package** supports Linux IRIS 2026.2 in `USER`: gateway,
UI and authenticated adapter. See the [package installation guide](IPM.md) for
registry setup, `zpm "install iris-fieldwork -v"` and the foreground launcher.
A clean consumer installed solely from the public community registry and passed
authenticated access, anonymous-denial and all six section checks; see the
[published verification](runtime/ipm-community-validation.json). The package
creates no demo data or credentials. Its ownership checks refuse existing manual
installations and preserve modified files. Publication does not establish an
awarded contest bonus or prize.

### Docker alternative

Requires Docker with Linux containers and Python 3.10 or newer. The host CPU must satisfy IRIS 2026.2's x86-64-v3 requirements (AVX/AVX2/BMI/BMI2). The IRIS image and Python gateway use separate processes; both HTTP ports bind to loopback.

```sh
python prepare_local.py
docker compose up --build -d
docker compose logs iris
# Wait for FIELDWORK_INSTALLED and healthy IRIS before opening the portal.
python run_local.py
```

Open **http://127.0.0.1:8766**. The IRIS gateway is at port 52773. `.secrets/` contains generated local credentials and is ignored by Git; never publish it. The initial account is deliberately administrative for this disposable development instance. Keep this local prototype off shared/untrusted machines and do not expose either port publicly.

On Linux, preparation creates the credential directory with mode `0700` and files with mode `0600`. A networkless initialization service copies the password into a protected volume owned by the IRIS runtime user with mode `0400`; IRIS mounts that volume read-only. Re-running preparation preserves existing credentials. To choose another IRIS host port, pass `--port PORT` to `prepare_local.py` and set `IRIS_HOST_PORT` to the same value when running Compose.

The Dockerfile pins the tested image digest and repairs two missing initialization paths using files already bundled in that image. It compiles the adapter and creates these local demonstration fixtures if absent:

- An on-demand `Fieldwork demonstration` task that increments only its own `FieldworkDemo` counter in USER.
- `FieldworkDemoResource`, with no public permissions, and an unassigned `FieldworkDemoRole` for grant/revoke demonstrations.
- A disabled `/fieldwork/demo` application for enable/disable demonstrations.

The installer does not assign the demonstration role to a user. The task has no email recipients or external effects. Existing demonstration fixtures are retained when the installer is run again.

Use the [owner and judge walkthrough](DEMO.md) to inspect the six areas and reproduce the bounded demonstration workflows.

Watch the edited walkthroughs of actual UI states from v0.1.0:

- [Overview — 2:58](https://www.youtube.com/watch?v=yzOxP8VXZPw): a web-app enable/disable cycle with verified restoration and a completed bounded audit search; permission, wallet and task examples stop at review.
- [Task lifecycle and triage — 2:22](https://www.youtube.com/watch?v=beluXt-UDZ0): verified suspension and resumption, one demonstration-task run with later completion evidence, and the limits of PID correlation. The initial unsuspended state and read-only workflow guard are restored.
- [REST exploration and bounded journal reads — 2:14](https://www.youtube.com/watch?v=KpxdD4lBYbw): a live journal-file inventory read, a reference-only write entry, and one bounded journal search that completes after refresh with two metadata records. Local filtering does not issue another search; global nodes and stored values remain withheld.

All three videos provide English captions and use a disposable administrative test account. They do not imply contest acceptance or an award.

For an existing instance, install the adapter deliberately and set `IRIS_BASE_URL`, `IRIS_USERNAME`, `IRIS_PASSWORD` (or `IRIS_BEARER_TOKEN`) before running `python app/backend.py`. Only loopback upstream origins are accepted. The optional adapter requires `%Admin_Operate:U`; management operations check their respective privileges. Read-only UI mode is a workflow guard, not a separate read-only IRIS credential.

Development validation used a disposable Linux container inside a QEMU VM. VM tooling, images, binaries and saved instance credentials are excluded from the published source. The optional metadata-only API probe is `runtime/probe.py`.

## Validation and known differences

At the latest 19 September validation, 105 application tests and six composed runtime-log tests passed. The application tests use isolated fake transports and local HTTP fixtures. Run them from this directory:

```sh
python -m unittest discover -s app -p "test_*.py" -v
python -m unittest discover -s iris -p "test_*.py" -v
```

One optional schema-reference test skips when `spec/mainspec_v2.json` is absent. The application and behavior tests run without that file. To include the reference check, fetch the pinned public specification and verify its recorded SHA-256; it remains ignored by Git:

```sh
python -c "from pathlib import Path; import hashlib,json,urllib.request; m=json.loads(Path('spec/SOURCE.json').read_text()); data=urllib.request.urlopen(m['raw_url'],timeout=30).read(); assert hashlib.sha256(data).hexdigest()==m['sha256'],'Specification checksum mismatch'; Path('spec/mainspec_v2.json').write_bytes(data)"
```

A separate source copy containing no credentials or vendor specification passed 110 tests with that single reference check skipped; see [`runtime/offline-source-validation.json`](runtime/offline-source-validation.json).

All 22 initial live management probes passed. Twelve further live checks in [`runtime/extended-validation.json`](runtime/extended-validation.json) cover permission and wallet inspection, a role grant/restore pair, wallet collection creation, secret create/replace/remove, and completed audit/journal metadata searches. The role was restored and the disposable secret removed. No secret-value readback was attempted.

Browser checks covered all six live views and a 390px mobile layout. UI task resume, a single on-demand execution and web-app enable/disable were verified against the disposable instance; see [`runtime/live-action-validation.json`](runtime/live-action-validation.json). The added role editor completed a grant and restore, both with verified readback. Wallet metadata and the replacement review were checked without submitting a wallet action through the UI. The review displays the proposed key name, hosts, TLS requirement, usage and resource bindings; its value input is a blank password field. Audit search completed after an explicit result refresh, and journal search returned five metadata records. The updated result view displays sample-limit and coverage notes. Live TLS detail inspection also returned HTTP 200. See [`runtime/extended-ui-validation.json`](runtime/extended-ui-validation.json).

A fresh Dockerfile build against a clean database compiled the expanded adapter automatically. Seven authenticated checks returned HTTP 200 without application errors: instance info, metrics, logs, task states, the private demonstration resource, the role without grants, and the disabled demonstration web application. The check container was stopped and retained for inspection; see [`runtime/reproduction-extended-validation.json`](runtime/reproduction-extended-validation.json).

The documented preparation and Compose startup also passed in a fresh Ubuntu 24.04 environment using Docker Compose 5.5.1, with a separate loopback port. All seven authenticated checks passed and four unauthenticated requests returned HTTP 401. The container reached healthy status; password ownership, file modes and read-only mounting were verified. The check container was stopped afterward. See [`runtime/compose-validation.json`](runtime/compose-validation.json). Docker Desktop on Windows and macOS has not been separately tested.

The tested IRIS image wraps `/api/admin/info` in `status/console/result` and uses lowercase `status.errors`. The supplied specification describes a different info shape. Fieldwork handles the observed response rather than treating HTTP 200 alone as success.

In this image, a successful task suspension changed `%SYS.Task.Suspended` while the v2 task-list response continued to report `false`. The optional task-state adapter reads the task objects directly. Commands must retain a visible unverified outcome when no reliable readback is available.

`runtime/web-toggle-validation.json` records a disposable app test: changing `Enabled` preserved the other 45 returned fields and restoring it reproduced the original response. This is not a guarantee of atomicity against another administrator editing the same field concurrently.

The role API similarly accepted a `Resources`-only update while preserving `Description`, `GrantedRoles` and `EscalationOnly`; restoring the grants reproduced the original role. Its resource inventory labels custom resources `Application`, and the API's `names` filter is necessary when system resources fill the first 100 rows. The resource-create endpoint returned HTTP 400 for the required empty public-permission value even though the specification describes creation. That control remains disabled; the installer creates the private demonstration resource through `Security.Resources.Create` instead.

Audit/journal POST searches return HTTP 202 with a `/v1/async-result?id=...` Location even when invoked through v2. Fieldwork validates that local route and numeric identifier, then polls the fixed v2 async-result endpoint. The live response omits `GUID`, despite that property appearing in the specification. The gateway checks the requested identifier and task kind; if a GUID is present, it must match. Failure details and console content are withheld.

Use the walkthrough to review each operation and its limits before running the demonstrations on a disposable instance. Broader app or operating-system management is a possible extension, not a completed feature or an asserted contest requirement.

## Sources and authorship

The project responds to the six operations areas in the official [Build Your Own Management Portal contest brief](https://community.intersystems.com/post/intersystems-programming-contest-build-your-own-management-portal). This is its motivation link; no Ideas Portal idea or bonus is claimed.

Original project code is available under the [MIT license](LICENSE). See [NOTICE.md](NOTICE.md) for the separate IRIS software terms, specification attribution and AI-assistance disclosure.

The gateway uses operation metadata from the [InterSystems SysAdmin API specification](https://github.com/intersystems-community/sysadmin-api-specification), reviewed at commit `f764aea427e5c0b1dd08a4c18a0457e0ff7b3b34`. The vendored working copy is excluded from publication because a redistribution license has not been established. No upstream source implementation is copied into the gateway.

This project was developed with AI coding assistance. The entrant confirmed review and understanding of the app and walkthrough before submitting and remains responsible for the work under the [official contest AI guidance](https://community.intersystems.com/post/guidelines-using-generative-ai-when-writing-posts-developer-community).
