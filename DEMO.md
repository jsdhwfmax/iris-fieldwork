# IRIS Fieldwork walkthrough

This AI-assisted prototype was approved for the [Build Your Own Management Portal contest](https://openexchange.intersystems.com/contest/48) on 21 September 2026 and is listed on the public contest roster. This walkthrough documents the operations and their limits for review on a disposable local instance. No award is claimed.

The current local source is 0.3.0. Its new archive workflow is separate from the verified 0.2.0 registry release and the v0.1.0 recordings; 0.3.0 publication and entrant review are not asserted here.

For a quick interface tour, use the [synthetic browser preview](README.md#interactive-preview). It requires no IRIS installation and supports browsing, filtering, sorting and inspecting example records. Its data is fictional, it has no IRIS connection, and commands and secret entry are unavailable. The operations below apply only to the actual local installation.

Follow [README: Local installation](README.md#local-installation) from this directory. On a clean Docker installation with Linux containers and the documented CPU requirements:

```sh
python prepare_local.py
docker compose up --build -d
docker compose logs iris
```

Wait for `FIELDWORK_INSTALLED` and healthy IRIS, then run `python run_local.py` and open `http://127.0.0.1:8766`. The earlier fresh Linux Compose installation passed seven authenticated fixture checks and four unauthenticated-access checks; see [the recorded evidence](runtime/compose-validation.json). Those checks predate the archive feature. Docker Desktop on Windows and macOS remains untested.

1. **System.** Start with **Refresh data**. Explain the kernel CPU sample, container memory limits and IRIS filesystem measurements. Open processes and inspect a row. Missing measurements and unsupported sources remain visible; a single sample is not a trend.

2. **Task manager.** Search for `Fieldwork demonstration`. If suspended, review **Resume task**. Choose **Run task now** exactly once after reviewing its identity and enabling command review. This installed task increments only its own `FieldworkDemo` counter in USER. Inspect returned status and activity. In **Task triage**, explain that a historical PID can be reused; a matching current process is not identity proof. Do not repeat an uncertain execution automatically.

3. **Web applications.** Open the initially disabled `/fieldwork/demo`. Review **Enable application**, check readback, then **Disable application** to restore it. Visit **REST explorer** and **Load live response** on an available read. Reference entries do not guarantee instance support.

4. **Permissions.** Inspect a user and its assigned roles. Open `FieldworkDemoRole`, choose **Edit resource grants**, and **Add resource grant** for exact name `FieldworkDemoResource` with **U** selected. Use **Review changes**, then **Confirm change**. Verify the grant, remove that row, and confirm again to restore the original empty grants. Leave the role unassigned. **Create resource** remains disabled because the tested API rejected private-resource creation.

5. **Security & secrets.** Inspect available TLS/X.509/OAuth metadata. Use **New collection** with an unused name such as `WalkthroughWallet`; enter `FieldworkDemoResource:U` for both permissions. In that collection, **Create secret** named `DemoToken`, key `DemoKey`, allowed host `example.com`. Review `%Wallet.KeyValue`, TLS `true`, HTTP usage and bindings. Enter only synthetic `demo-value-1` in **New secret value**. Verify metadata, **Replace** using synthetic `demo-value-2`, then **Remove**. Values are never read back; replacement/removal cannot be undone here. The empty collection remains.

6. **Logs & activity.** Use **Search audit records** and **Search records** with a small limit. For journal records, select an actual journal-file row. If pending, use **Refresh search result**. Explain sample-limit notes: results are bounded metadata, not complete logs or payloads.

   In the local 0.3.0 UI, choose **Browse older messages**. Select a listed filename, then use **Next**, **Previous**, **File list** and **Refresh file list**. The fresh instance may have no eligible archives; that is a valid empty result. Read any omission notes. A changed revision requires refreshing the inventory and reselecting the file. This workflow is read-only and does not need command-review mode. See [ARCHIVES.md](ARCHIVES.md) for exact limits and the Community Opportunity attribution.

Keep both ports on loopback and credentials private. Read-only mode is a workflow guard over an administrative account. Fresh-state checks and readback do not provide an external concurrency lock. Restore demonstrated settings before finishing.
