# Synthetic preview

This directory is a standalone, read-only interface preview for IRIS Fieldwork.
Every example is manually authored in `fixtures.js`; no runtime output or instance
data was exported. It has no backend, account, credentials or API connection.
No contest bonus is asserted.

The preview reuses the original application's navigation, table filtering,
sorting, field inspection, metrics layout and task/process correlation UI. Its
REST reference cannot execute requests. All management commands, credential
entry and server-side log searches are removed. Audit and journal tables contain
two fixed sample metadata records each. Resetting a view reloads the same samples.

`index.html` sets `connect-src 'none'`, `form-action 'none'` and no external script
or asset origins. The preview transport is only an exact in-memory lookup; it has
no network fallback. Fixtures are frozen and cloned before rendering.

To rebuild the derived interface after an intentional source update, run
`python tools/build_preview.py` from the repository root. This reads only the
original static interface and keeps the authored fixtures unchanged. Serve this
directory with a static HTTP server for local review. The relative asset paths
also support GitHub Pages project URLs. Hosting is separate from the local app.

Use the repository's main README for installation and videos of actual IRIS
behavior. The preview does not demonstrate live API correctness or a production
deployment.
