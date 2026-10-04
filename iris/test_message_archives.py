"""Synthetic archive fixtures only; no IRIS instance or production log access."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

import message_archives as archives


class FixtureDirectory:
    """Portable fixture transport; production never selects this implementation."""

    def __init__(self, root):
        self.root = root

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def names(self):
        return os.listdir(self.root)

    def metadata(self, name):
        metadata = os.stat(self.root / name, follow_symlinks=False)
        if os.name == "nt" and stat.S_ISREG(metadata.st_mode):
            # Windows stat(path) reports creation time as ctime while fstat(fd)
            # can report change time. Normalize synthetic fixture metadata to
            # descriptors; production Windows access remains unsupported.
            fd = self.open(name)
            try:
                return os.fstat(fd)
            finally:
                os.close(fd)
        return metadata

    def open(self, name):
        return os.open(self.root / name, os.O_RDONLY | getattr(os, "O_BINARY", 0))


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fieldwork-archive-test-")
        self.root = Path(self.temporary.name)
        self.directory = FixtureDirectory(self.root)
        self.transport = patch.object(archives, "ArchiveDirectory", return_value=self.directory)
        self.transport.start()

    def tearDown(self):
        self.transport.stop()
        self.temporary.cleanup()

    def fixture(self, data, name="messages.old_20260924"):
        path = self.root / name
        path.write_bytes(data)
        return name, archives._revision(self.directory.metadata(name))

    def test_inventory_sorted_pages_and_fixed_scope(self):
        for number in reversed(range(53)):
            self.fixture(b"line\n", f"messages.old_{number:03d}")
        for name in ("messages.log", "private.txt", "messages.old_.bad", "messages.old_x.gz"):
            (self.root / name).write_bytes(b"not an eligible archive\n")
        (self.root / "messages.old_directory").mkdir()
        first = archives.inventory()
        self.assertEqual(first["state"], "ok")
        self.assertEqual(first["total"], 53)
        self.assertEqual(len(first["files"]), 50)
        self.assertEqual(first["nextOffset"], 50)
        self.assertEqual(first["files"][0]["name"], "messages.old_000")
        self.assertRegex(first["files"][0]["revision"], r"^[a-f0-9]{64}$")
        self.assertTrue(first["files"][0]["modifiedAt"].endswith("+00:00"))
        second = archives.inventory("50")
        self.assertEqual([row["name"] for row in second["files"]],
                         [f"messages.old_{n:03d}" for n in range(50, 53)])
        self.assertIsNone(second["nextOffset"])
        self.assertEqual(archives.inventory("54")["state"], "invalid")

    def test_invalid_names_revisions_and_offsets_never_open_directory(self):
        bad_names = ("../messages.old_x", "/usr/irissys/mgr/messages.old_x", "messages.old_a/b",
                     "messages.old_a\\b", "messages.old_%2fprivate", "messages.old_a..b",
                     "messages.old_", "messages.log", "messages.old_a\x00", "messages.old_é")
        with patch.object(archives, "ArchiveDirectory") as factory:
            for name in bad_names:
                self.assertEqual(archives.read_archive(name, "a" * 64)["state"], "invalid")
            for token in ("", "a" * 63, "A" * 64, "g" * 64, None):
                self.assertEqual(archives.read_archive("messages.old_good", token)["state"], "invalid")
            for offset in ("-1", "01", "+1", " 1", "1.0", "1e3", "١", "", None, 0,
                           "9007199254740992", "9" * 100):
                self.assertEqual(archives.inventory(offset)["state"], "invalid")
                self.assertEqual(archives.read_archive("messages.old_good", "a" * 64, offset)["state"], "invalid")
            factory.assert_not_called()

    def test_complete_rows_traverse_without_duplicates_or_loss(self):
        lines = [f"record {index:03d}" for index in range(203)]
        name, revision = self.fixture(("\n".join(lines) + "\n").encode())
        offset, received = 0, []
        while offset is not None:
            page = archives.read_archive(name, revision, str(offset))
            self.assertEqual(page["state"], "ok")
            self.assertLessEqual(len(page["records"]), 80)
            self.assertEqual(sum(page["omitted"].values()), 0)
            received.extend(row["line"] for row in page["records"])
            next_offset = page["nextOffset"]
            if next_offset is not None:
                self.assertGreater(next_offset, offset)
            offset = next_offset
        self.assertEqual(received, lines)

    def test_byte_boundary_defers_whole_multibyte_line(self):
        lines = [("界" * 1000) + str(n) for n in range(30)]
        name, revision = self.fixture(("\n".join(lines) + "\n").encode())
        first = archives.read_archive(name, revision)
        self.assertIsNotNone(first["nextOffset"])
        second = archives.read_archive(name, revision, str(first["nextOffset"]))
        self.assertEqual([r["line"] for r in first["records"] + second["records"]], lines)
        self.assertEqual(first["skippedBytes"] + second["skippedBytes"], 0)

    def test_secret_assignments_are_withheld_as_entire_records(self):
        secrets = ['Authorization: Bearer archive_fixture_token',
                   'password="archive_fixture words with spaces"',
                   '{"access_token": "archive_fixture_json"}',
                   'Set-Cookie: sid=archive_fixture_session; HttpOnly']
        name, revision = self.fixture(("ordinary line\n" + "\n".join(secrets) + "\n").encode())
        page = archives.read_archive(name, revision)
        self.assertEqual(page["records"][0], {"line": "ordinary line"})
        self.assertEqual(page["records"][1:], [{"line": "[sensitive log line withheld]"}] * len(secrets))
        self.assertNotIn("archive_fixture", json.dumps(page))

    def test_oversize_record_is_not_clipped_before_redaction(self):
        content = "archive_fixture_prefix " + "x" * 3000 + " password=archive_fixture_secret\nnormal\n"
        name, revision = self.fixture(content.encode())
        page = archives.read_archive(name, revision)
        self.assertEqual(page["records"], [{"line": "normal"}])
        self.assertEqual(page["omitted"]["oversizeSegments"], 1)
        self.assertNotIn("archive_fixture", json.dumps(page))

    def test_large_secret_record_crossing_many_pages_never_leaks_or_loops(self):
        content = b"Authorization: Bearer " + b"archive_fixture_" * 14000 + b"\nfinal\n"
        name, revision = self.fixture(content)
        offset, pages, records, skipped = 0, 0, [], 0
        while offset is not None:
            page = archives.read_archive(name, revision, str(offset))
            self.assertEqual(page["state"], "ok")
            self.assertNotIn("archive_fixture", json.dumps(page))
            records.extend(page["records"])
            skipped += page["skippedBytes"]
            next_offset = page["nextOffset"]
            if next_offset is not None:
                self.assertGreater(next_offset, offset)
            offset = next_offset
            pages += 1
            self.assertLess(pages, 10)
        self.assertEqual(records, [{"line": "final"}])
        self.assertEqual(skipped, len(content) - len(b"final\n"))

    def test_offset_inside_line_and_unterminated_eof_are_withheld(self):
        name, revision = self.fixture(b"Authorization: Bearer archive_fixture_token\nokay\narchive_fixture_unfinished")
        page = archives.read_archive(name, revision, "22")
        self.assertEqual(page["records"], [{"line": "okay"}])
        self.assertEqual(page["omitted"]["partialSegments"], 2)
        self.assertIsNone(page["nextOffset"])
        self.assertNotIn("archive_fixture", json.dumps(page))

    def test_empty_file_and_end_cursor_are_valid(self):
        name, revision = self.fixture(b"")
        self.assertEqual(archives.read_archive(name, revision)["records"], [])
        name, revision = self.fixture(b"okay\n")
        page = archives.read_archive(name, revision, "5")
        self.assertEqual(page["state"], "ok")
        self.assertEqual(page["records"], [])
        self.assertIsNone(page["nextOffset"])
        self.assertEqual(archives.read_archive(name, revision, "6")["state"], "invalid")

    def test_missing_and_changed_archives_are_distinct(self):
        self.assertEqual(archives.read_archive("messages.old_absent", "a" * 64)["state"], "not_found")
        name, revision = self.fixture(b"before\n")
        (self.root / name).write_bytes(b"after with different size\n")
        page = archives.read_archive(name, revision)
        self.assertEqual(page["state"], "changed")
        self.assertEqual(page["records"], [])

    def test_revision_must_remain_same_for_later_pages(self):
        name, revision = self.fixture(b"record\n" * 100)
        first = archives.read_archive(name, revision)
        with (self.root / name).open("ab") as stream:
            stream.write(b"rotation writer appended\n")
        changed = archives.read_archive(name, revision, str(first["nextOffset"]))
        self.assertEqual(changed["state"], "changed")
        self.assertEqual(changed["records"], [])

    def test_restat_of_fd_discards_records_changed_during_read(self):
        name, revision = self.fixture(b"normal before mutation\n")
        original_read = os.read

        def concurrent_write(fd, count):
            data = original_read(fd, count)
            with (self.root / name).open("ab") as stream:
                stream.write(b"new line\n")
            return data

        with patch.object(archives.os, "read", side_effect=concurrent_write):
            page = archives.read_archive(name, revision)
        self.assertEqual(page["state"], "changed")
        self.assertEqual(page["records"], [])

    def test_path_replacement_after_open_discards_old_fd_records(self):
        name, revision = self.fixture(b"normal original\n")
        _, _ = self.fixture(b"other generation\n", "messages.old_replacement")
        replacement = (self.root / "messages.old_replacement").stat()
        with patch.object(self.directory, "metadata", return_value=replacement):
            page = archives.read_archive(name, revision)
        self.assertEqual(page["state"], "changed")
        self.assertEqual(page["records"], [])

    def test_binary_and_compressed_content_is_not_presented_as_text(self):
        for content in (b"okay\n\xff\xfe\n", b"okay\n\x00secret", b"\x1f\x8bcompressed fixture"):
            name, revision = self.fixture(content)
            page = archives.read_archive(name, revision)
            self.assertEqual(page["state"], "unsupported")
            self.assertEqual(page["records"], [])
            self.assertGreater(page["omitted"]["binaryRecords"], 0)
        with patch.object(archives, "ArchiveDirectory") as factory:
            self.assertEqual(archives.read_archive("messages.old_20260924.gz", "a" * 64)["state"], "unsupported")
            factory.assert_not_called()

    def test_read_budget_includes_boundary_validation_byte(self):
        name, revision = self.fixture(b"okay\n" + b"x" * (archives.PAGE_BYTES * 2))
        original_read = os.read
        counts = []

        def counted_read(fd, count):
            counts.append(count)
            return original_read(fd, count)

        with patch.object(archives.os, "read", side_effect=counted_read):
            page = archives.read_archive(name, revision, "5")
        self.assertEqual(sum(counts), archives.PAGE_BYTES)
        self.assertGreater(page["nextOffset"], 5)

    def test_crlf_and_full_redaction_length_boundary(self):
        name, revision = self.fixture(("x" * 2000 + "\r\n" + "y" * 2001 + "\n").encode())
        page = archives.read_archive(name, revision)
        self.assertEqual(page["records"], [{"line": "x" * 2000}])
        self.assertEqual(page["omitted"]["oversizeSegments"], 1)

    def test_unknown_or_duplicate_query_flag_is_invalid_without_reflection(self):
        with patch.object(archives, "ArchiveDirectory") as factory:
            for kind in ("inventory", "read"):
                payload = json.loads(archives.collect(kind, "PRIVATE_PATH_SENTINEL", "secret", "0", False))
                self.assertEqual(payload["status"]["errors"], [])
                self.assertEqual(payload["result"]["state"], "invalid")
                self.assertEqual(payload["result"]["message"], "Invalid archive request.")
                self.assertNotIn("PRIVATE_PATH_SENTINEL", json.dumps(payload))
            factory.assert_not_called()

    def test_generic_os_failure_does_not_expose_host_path(self):
        with patch.object(self.directory, "open", side_effect=PermissionError("PRIVATE_PATH_SENTINEL")):
            page = archives.read_archive("messages.old_good", "a" * 64)
        self.assertEqual(page["state"], "unavailable")
        self.assertNotIn("PRIVATE_PATH_SENTINEL", json.dumps(page))


@unittest.skipUnless(sys.platform.startswith("linux"), "Real no-follow descriptor checks require Linux")
class LinuxDescriptorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fieldwork-archive-linux-test-")
        self.root = Path(self.temporary.name)
        self.root_patch = patch.object(archives, "_ROOT", str(self.root))
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temporary.cleanup()

    def test_symlink_and_fifo_are_excluded_and_never_read(self):
        target = self.root / "private.txt"
        target.write_text("archive_fixture_secret\n", encoding="utf-8")
        (self.root / "messages.old_link").symlink_to(target)
        os.mkfifo(self.root / "messages.old_fifo")
        self.assertEqual(archives.inventory()["files"], [])
        for name in ("messages.old_link", "messages.old_fifo"):
            page = archives.read_archive(name, "a" * 64)
            self.assertEqual(page["state"], "unsupported")
            self.assertEqual(page["records"], [])

    def test_regular_file_uses_real_directory_relative_reader(self):
        target = self.root / "messages.old_20260924"
        target.write_bytes(b"real descriptor fixture\n")
        row = archives.inventory()["files"][0]
        page = archives.read_archive(row["name"], row["revision"])
        self.assertEqual(page["state"], "ok")
        self.assertEqual(page["records"], [{"line": "real descriptor fixture"}])

    def test_symlink_swap_before_open_fails_closed(self):
        target = self.root / "messages.old_20260924"
        target.write_bytes(b"original\n")
        revision = archives._revision(target.stat())
        private = self.root / "private.txt"
        private.write_bytes(b"archive_fixture_secret\n")
        original_open = archives.ArchiveDirectory.open

        def swap_then_open(directory, name):
            target.unlink()
            target.symlink_to(private)
            return original_open(directory, name)

        with patch.object(archives.ArchiveDirectory, "open", new=swap_then_open):
            page = archives.read_archive(target.name, revision)
        self.assertEqual(page["state"], "unsupported")
        self.assertNotIn("archive_fixture_secret", json.dumps(page))


if __name__ == "__main__":
    unittest.main()
