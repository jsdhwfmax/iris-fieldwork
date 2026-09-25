# Rotated message-log browser

The local **0.3.0** source adds read-only browsing of older IRIS message logs.
This addresses the need described in [Option to show older message.log in IRIS SMP (DPI-I-966)](https://ideas.intersystems.com/ideas/DPI-I-966), marked Community Opportunity when checked on 24 September 2026,
inside **IRIS Fieldwork**. It does not change InterSystems System Management
Portal (SMP). No idea bonus, award, new video or entrant review is claimed.

Version 0.2.0 is the verified public Open Exchange/community-registry release.
For 0.3.0, use [IPM source loading](IPM.md#load-the-030-source) or the
[local Docker setup](README.md#docker-alternative) until its publication is
confirmed. Docker's existing `COPY iris/` includes the archive module.
The synthetic preview is separate and has no archive reader or IRIS connection.

## Browse the files

1. Open the real local portal, select **Logs & activity**, then **Browse older messages**.
2. The inventory shows up to **50 files**, sorted by filename, with size and UTC
   modification time. **Next** and **Previous** move through inventory pages.
   **Refresh file list** starts a fresh listing from its first page.
3. Choose an exact listed filename. The first excerpt starts at byte zero and
   includes only the records the server can return within its limits.
4. Use **Next** and **Previous** to read further excerpts. The UI follows the
   server's next-byte offset and keeps visited offsets for back navigation;
   it does not estimate offsets from row counts. Displayed row numbers are local
   to each page, not line numbers in the original file.
5. **File list** reloads the last inventory page. If a file changes, disappears
   or becomes unreadable, the excerpt is withheld and a fixed status message is
   shown. Refresh the inventory and select a current file revision to continue.

No filename/path input, upload, deletion, rotation or command is exposed.
Command-review mode is unnecessary. An instance with no eligible archives shows
an empty list; installation does not manufacture archived operational data.
The inventory is a fresh, non-atomic listing, so rotation can change the files
between inventory pages. Refreshing starts over with the current list.

## Exact read boundaries

| Boundary | Behavior |
| --- | --- |
| Location | Fixed `/usr/irissys/mgr` on the IRIS host; standard Linux layout only. No request-selected directory. |
| Filenames | Regular files matching `messages.old_*`, with the bounded ASCII suffix accepted by the reader. Path traversal and names containing `..` are rejected. |
| Excluded files | Symlinks, directories and other non-regular files. Known compressed extensions `.gz`, `.bz2`, `.xz`, `.zip`, `.zst`, `.lz4`, `.7z`, `.tgz`, `.lz` are excluded. |
| Inventory | At most 50 entries per response; each includes an opaque revision token. |
| Content page | At most **65,536 bytes (64 KiB)** read, including any preceding boundary-check byte, and at most **80 complete UTF-8 records** returned. |
| Record size | At most **8,000 raw bytes** before the newline and **2,000 decoded characters**. Larger records are withheld, not silently presented as complete. |
| Incomplete records | A short record crossing a byte-page boundary is deferred where possible. Partial segments and an unterminated final record are withheld and counted. |
| Binary/encoding errors | Disallowed control bytes or invalid UTF-8 make the page unsupported; records already collected for that page are discarded. Compressed content is not decoded. |
| Platform | Directory-relative, no-follow file access is required. Hosts without the necessary POSIX primitives fail closed as unsupported. |

Returned omission counters distinguish oversize segments, partial segments and
binary records; `skippedBytes` reports bytes excluded for those reasons. They are
segment diagnostics, not a count of unique missing lines. Successful excerpts
show positive omission counts. An unsupported/error page displays no records.
This reader is a bounded inspection tool, not a lossless log export or live tail.

## Revisions, credentials and sensitive content

Each read supplies the selected file's revision from the inventory. The token
is derived from filesystem identity, size and modification/change timestamps;
it is not a hash of the file's contents. The reader checks the opened file and
current directory entry before/after reading. A detected change discards the
page. These checks do not lock the filesystem or make separate pages an atomic
snapshot.

The adapter uses the existing authenticated runtime route and requires
`%Admin_Operate:U`. Credentials remain in the gateway process. Keep the gateway
and IRIS web port on loopback, with the trusted local access described in the
[installation guide](IPM.md).

The existing pattern-based filter replaces entire lines that match recognized
credential markers with `[sensitive log line withheld]`. It is **not universal
data-loss prevention**: unrecognized secrets and other personal or operational
information may remain. Review excerpts before copying or sharing them. The
browser renders returned records as escaped text.

## Verification status

On 25 September 2026, a disposable Linux IRIS 2026.2 instance loaded the complete
0.3.0 source package through IPM 0.10.9. Inventory/content paging, recognized
secret-line withholding, revision changes, missing files, invalid requests and
anonymous/limited-account denial passed. The installed gateway served all six
sections and the archive pages. Linux suites passed 174 tests, with one optional
schema-reference check skipped; Windows passed 168 with seven documented skips.
See the [archive validation record](runtime/archive-validation.json).

Live browser interaction remains unverified: the in-app browser blocked access
to the local test URL, and the connected Edge browser was unavailable. The code
is a draft update, not a released or newly submitted contest version. The existing
[0.2.0 registry verification](runtime/ipm-community-validation.json), earlier
Compose evidence and v0.1.0 videos remain historical; they do not validate this
new browser workflow. The test container and VM were stopped after verification;
the owner's original stopped instance was preserved.
